import SwiftUI

struct ContentView: View {
    @State private var serverURL: String = UserDefaults.standard.string(forKey: "serverURL") ?? "http://localhost:5001/"
    @State private var username: String = UserDefaults.standard.string(forKey: "username") ?? ""
    @State private var password: String = KeychainManager.loadPassword(account: "dockerstats_password") ?? ""
    @State private var statusMessage: String = ""
    @State private var connecting = false
    @State private var showMetrics = false
    @State private var showSettings = false

    var body: some View {
        NavigationView {
            if showMetrics {
                ContainerListView(serverURL: URL(string: serverURL)!, username: username, password: password)
                    .toolbar {
                        ToolbarItem(placement: .navigationBarTrailing) {
                            Button(action: { showSettings = true }) { Image(systemName: "bell") }
                        }
                    }
                    .sheet(isPresented: $showSettings) {
                        NotificationSettingsView()
                    }
            } else {
                Form {
                    Section(header: Text("Server")) {
                        TextField("URL", text: $serverURL)
                            .keyboardType(.URL)
                            .autocapitalization(.none)
                    }
                    Section(header: Text("Credentials (optional)")) {
                        TextField("Username", text: $username)
                            .autocapitalization(.none)
                        SecureField("Password", text: $password)
                    }
                    Section {
                        Button(action: connect) {
                            if connecting {
                                ProgressView()
                            } else {
                                Text("Connect")
                            }
                        }
                    }
                    if !statusMessage.isEmpty {
                        Section {
                            Text(statusMessage).foregroundColor(.red)
                        }
                    }
                    Section {
                        HStack { Spacer(); Image("logo", bundle: .module).resizable().scaledToFit().frame(width: 120); Spacer() }
                    }
                }
                .navigationTitle("DockerStats Setup")
            }
        }
    }

    private func connect() {
        guard let url = URL(string: serverURL) else {
            statusMessage = "Invalid URL"
            return
        }
        connecting = true
        NetworkManager.shared.verifyConnection(url: url, username: username, password: password) { result in
            connecting = false
            switch result {
            case .success:
                UserDefaults.standard.set(serverURL, forKey: "serverURL")
                UserDefaults.standard.set(username, forKey: "username")
                if !password.isEmpty { _ = KeychainManager.save(password: password, for: "dockerstats_password") }
                statusMessage = "Connection successful"
                showMetrics = true
            case .failure(let error):
                statusMessage = error.localizedDescription
            }
        }
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
