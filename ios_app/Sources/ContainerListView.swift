import SwiftUI

/// Displays a list of containers with all metrics from the server.
struct ContainerListView: View {
    let serverURL: URL
    let username: String?
    let password: String?

    @State private var containers: [ContainerStats] = []
    @State private var loading = true
    @State private var errorMessage: String?

    var body: some View {
        List {
            if loading {
                ProgressView().frame(maxWidth: .infinity, alignment: .center)
            }
            ForEach(containers) { item in
                ContainerRow(stats: item)
            }
            if let msg = errorMessage {
                Text(msg).foregroundColor(.red)
            }
        }
        .navigationTitle("Containers")
        .onAppear(perform: fetch)
    }

    private func fetch() {
        loading = true
        NetworkManager.shared.fetchMetrics(url: serverURL, username: username, password: password) { result in
            loading = false
            switch result {
            case .success(let rows):
                containers = rows
            case .failure(let err):
                errorMessage = err.localizedDescription
            }
        }
    }
}

/// Displays metrics for a single container.
struct ContainerRow: View {
    let stats: ContainerStats

    var body: some View {
        VStack(alignment: .leading) {
            Text(stats.name).font(.headline)
            HStack {
                Text("CPU: \(format(stats.cpu))%")
                Text("RAM: \(format(stats.mem))%")
                Text("PIDs: \(stats.pid_count ?? 0)")
            }
            HStack {
                Text("Net RX: \(format(stats.net_io_rx))MB")
                Text("Net TX: \(format(stats.net_io_tx))MB")
                Text("Restarts: \(stats.restarts ?? 0)")
            }
            HStack {
                Text("Image: \(stats.image ?? "")")
            }
        }
    }

    private func format(_ value: Double?) -> String {
        guard let v = value else { return "-" }
        return String(format: "%.2f", v)
    }
}

struct ContainerListView_Previews: PreviewProvider {
    static var previews: some View {
        ContainerListView(serverURL: URL(string: "http://localhost:5001")!, username: nil, password: nil)
    }
}
