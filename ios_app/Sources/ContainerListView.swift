import SwiftUI
import UniformTypeIdentifiers

/// Filtering options for container list.
enum StatusFilter: String, CaseIterable, Identifiable {
    case all, running, stopped, highUsage
    var id: String { rawValue }
    var label: String {
        switch self {
        case .all: return "All"
        case .running: return "Running"
        case .stopped: return "Stopped"
        case .highUsage: return "High Usage"
        }
    }

    func matches(_ stats: ContainerStats) -> Bool {
        switch self {
        case .all: return true
        case .running: return stats.status?.lowercased() == "running"
        case .stopped: return stats.status?.lowercased() != "running"
        case .highUsage:
            let settings = NotificationSettingsManager.shared.load()
            return (stats.cpu ?? 0) > settings.cpuThreshold || (stats.mem ?? 0) > settings.ramThreshold
        }
    }
}

/// Refresh intervals for automatic updates.
enum RefreshInterval: Double, CaseIterable, Identifiable {
    case s1 = 1
    case s15 = 15
    case s30 = 30
    case s60 = 60
    var id: Double { rawValue }
    var label: String {
        switch self {
        case .s1: return "1s"
        case .s15: return "15s"
        case .s30: return "30s"
        case .s60: return "60s"
        }
    }
}

/// Displays a list of containers with all metrics from the server.
struct ContainerListView: View {
    let serverURL: URL
    let username: String?
    let password: String?

    @State private var containers: [ContainerStats] = []
    @State private var loading = true
    @State private var errorMessage: String?
    @State private var searchText = ""
    @State private var statusFilter: StatusFilter = .all
    @State private var refresh: RefreshInterval = .s15
    @State private var timer = Timer.publish(every: 15, on: .main, in: .common).autoconnect()
    @State private var exporting = false
    @State private var exportData: Data?
    @State private var showExporter = false

    var body: some View {
        List {
            if loading {
                ProgressView().frame(maxWidth: .infinity, alignment: .center)
            }
            ForEach(filteredContainers) { item in
                ContainerRow(stats: item, serverURL: serverURL, username: username, password: password)
            }
            if let msg = errorMessage {
                Text(msg).foregroundColor(.red)
            }
        }
        .searchable(text: $searchText)
        .navigationTitle("Containers")
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Picker("Filter", selection: $statusFilter) {
                    ForEach(StatusFilter.allCases) { f in Text(f.label).tag(f) }
                }
                .pickerStyle(.menu)
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                Menu {
                    Picker("Refresh", selection: $refresh) {
                        ForEach(RefreshInterval.allCases) { r in Text(r.label).tag(r) }
                    }
                    Button("Check Updates", action: { fetch(force: true) })
                    Button("Export CSV", action: exportCSV)
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
            }
        }
        .onReceive(timer) { _ in fetch() }
        .onChange(of: refresh) { _ in restartTimer() }
        .onAppear { fetch() }
        .fileExporter(isPresented: $showExporter, document: CSVDocument(data: exportData ?? Data()), contentType: .commaSeparatedText, defaultFilename: "metrics") { _ in }
    }

    private func fetch(force: Bool = false) {
        loading = true
        NetworkManager.shared.fetchMetrics(url: serverURL, username: username, password: password, forceUpdate: force) { result in
            loading = false
            switch result {
            case .success(let rows):
                containers = rows
            case .failure(let err):
                errorMessage = err.localizedDescription
            }
        }
    }

    private var filteredContainers: [ContainerStats] {
        containers.filter { item in
            (searchText.isEmpty || item.name.lowercased().contains(searchText.lowercased())) &&
            statusFilter.matches(item)
        }
    }

    private func restartTimer() {
        timer.upstream.connect().cancel()
        timer = Timer.publish(every: refresh.rawValue, on: .main, in: .common).autoconnect()
    }

    private func exportCSV() {
        exporting = true
        NetworkManager.shared.exportCSV(metrics: containers, baseURL: serverURL, username: username, password: password) { result in
            exporting = false
            switch result {
            case .success(let data):
                exportData = data
                showExporter = true
            case .failure(let err):
                errorMessage = err.localizedDescription
            }
        }
    }
}

/// Displays metrics for a single container.
struct ContainerRow: View {
    let stats: ContainerStats
    let serverURL: URL
    let username: String?
    let password: String?
    
    @State private var performing = false

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(stats.name)
                    .font(.headline)
                    .foregroundColor(isRunning ? .primary : .red)
                Spacer()
                HStack(spacing: 8) {
                    Button(action: { action("start") }) { Image(systemName: "play.fill") }
                    Button(action: { action("stop") }) { Image(systemName: "stop.fill") }
                    Button(action: { action("restart") }) { Image(systemName: "arrow.clockwise") }
                }.buttonStyle(BorderlessButtonStyle())
                .disabled(performing)
            }
            ProgressView(value: (stats.cpu ?? 0)/100) {
                Text("CPU \(format(stats.cpu))%")
            }
            .tint(Theme.accent)
            ProgressView(value: (stats.mem ?? 0)/100) {
                Text("RAM \(format(stats.mem))%")
            }
            .tint(.blue)
            if let gpu = stats.gpu, let max = stats.gpu_max {
                ProgressView(value: gpu / max) {
                    Text("GPU \(format(gpu))%")
                }
                .tint(.green)
            }
            details
        }
    }

    private var isRunning: Bool {
        stats.status?.lowercased() == "running"
    }

    private func format(_ value: Double?) -> String {
        guard let v = value else { return "-" }
        return String(format: "%.1f", v)
    }

    private func action(_ a: String) {
        performing = true
        NetworkManager.shared.containerAction(id: stats.id, action: a, baseURL: serverURL, username: username, password: password) { _ in
            performing = false
        }
    }

    /// Column values shown below the progress bars.
    private var details: some View {
        VStack(alignment: .leading, spacing: 2) {
            statRow("Status", stats.status)
            statRow("Uptime", stats.uptime)
            if let usage = stats.mem_usage, let limit = stats.mem_limit {
                statRow("Mem Usage", String(format: "%.0f / %.0f MiB", usage, limit))
            }
            statRow("Processes", stats.pid_count.map { String($0) })
            if stats.net_io_rx != nil || stats.net_io_tx != nil {
                let rx = formatBytes(stats.net_io_rx)
                let tx = formatBytes(stats.net_io_tx)
                statRow("Net I/O", "\(rx) / \(tx)")
            }
            if stats.block_io_r != nil || stats.block_io_w != nil {
                let r = formatBytes(stats.block_io_r)
                let w = formatBytes(stats.block_io_w)
                statRow("Block I/O", "\(r) / \(w)")
            }
            statRow("Image", stats.image)
            statRow("Ports", stats.ports)
            statRow("Restarts", stats.restarts.map { String($0) })
            if stats.update_available == true {
                Text("Update available").foregroundColor(.orange).font(.caption)
            }
            statRow("Project", stats.compose_project)
            statRow("Service", stats.compose_service)
        }
        .font(.caption)
    }

    private func statRow(_ label: String, _ value: String?) -> some View {
        HStack {
            Text(label + ":").bold()
            Spacer()
            Text(value ?? "-")
        }
    }

    private func formatBytes(_ value: Double?) -> String {
        guard let v = value else { return "-" }
        if v > 1024 * 1024 {
            return String(format: "%.1f GB", v / 1024 / 1024)
        } else if v > 1024 {
            return String(format: "%.1f MB", v / 1024)
        } else {
            return String(format: "%.0f kB", v)
        }
    }
}

struct ContainerListView_Previews: PreviewProvider {
    static var previews: some View {
        ContainerListView(serverURL: URL(string: "http://localhost:5001")!, username: nil, password: nil)
    }
}

/// Simple FileDocument used for exporting CSV data.
struct CSVDocument: FileDocument {
    static var readableContentTypes: [UTType] { [.commaSeparatedText] }
    var data: Data

    init(data: Data) {
        self.data = data
    }

    init(configuration: ReadConfiguration) throws {
        data = configuration.file.regularFileContents ?? Data()
    }

    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper {
        FileWrapper(regularFileWithContents: data)
    }
}
