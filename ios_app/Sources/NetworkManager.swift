import Foundation

/// Handles communication with the DockerStats backend.
class NetworkManager: ObservableObject {
    /// Shared instance for use across views.
    static let shared = NetworkManager()

    /// Test connection to the server using the provided URL and credentials.
    func verifyConnection(url: URL, username: String?, password: String?, completion: @escaping (Result<Void, Error>) -> Void) {
        var request = URLRequest(url: url.appendingPathComponent("api/metrics"))
        if let user = username, let pass = password, !user.isEmpty, !pass.isEmpty {
            let credential = "\(user):\(pass)".data(using: .utf8)!.base64EncodedString()
            request.setValue("Basic \(credential)", forHTTPHeaderField: "Authorization")
        }

        URLSession.shared.dataTask(with: request) { _, response, error in
            if let error = error {
                DispatchQueue.main.async { completion(.failure(error)) }
                return
            }
            guard let http = response as? HTTPURLResponse else {
                DispatchQueue.main.async { completion(.failure(NSError(domain: "No response", code: -1, userInfo: nil))) }
                return
            }
            if http.statusCode == 200 {
                DispatchQueue.main.async { completion(.success(())) }
            } else if http.statusCode == 401 {
                let err = NSError(domain: "InvalidCredentials", code: 401, userInfo: [NSLocalizedDescriptionKey: "Invalid credentials"])
                DispatchQueue.main.async { completion(.failure(err)) }
            } else {
                let err = NSError(domain: "HTTP", code: http.statusCode, userInfo: [NSLocalizedDescriptionKey: "Server responded with status \(http.statusCode)"])
                DispatchQueue.main.async { completion(.failure(err)) }
            }
        }.resume()
    }

    /// Retrieve container metrics from the server. Set `forceUpdate` to true to force the backend to check for updates immediately.
    func fetchMetrics(url: URL, username: String?, password: String?, forceUpdate: Bool = false, completion: @escaping (Result<[ContainerStats], Error>) -> Void) {
        var components = URLComponents(url: url.appendingPathComponent("api/metrics"), resolvingAgainstBaseURL: false)!
        if forceUpdate { components.queryItems = [URLQueryItem(name: "force", value: "true")] }
        var request = URLRequest(url: components.url!)
        if let user = username, let pass = password, !user.isEmpty, !pass.isEmpty {
            let credential = "\(user):\(pass)".data(using: .utf8)!.base64EncodedString()
            request.setValue("Basic \(credential)", forHTTPHeaderField: "Authorization")
        }

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                DispatchQueue.main.async { completion(.failure(error)) }
                return
            }
            guard let data = data else {
                DispatchQueue.main.async { completion(.failure(NSError(domain: "No data", code: -1, userInfo: nil))) }
                return
            }
            do {
                let decoder = JSONDecoder()
                let metrics = try decoder.decode([ContainerStats].self, from: data)
                DispatchQueue.main.async { completion(.success(metrics)) }
            } catch {
                DispatchQueue.main.async { completion(.failure(error)) }
            }
        }.resume()
    }

    /// Perform a start/stop/restart action on a container.
    func containerAction(id: String, action: String, baseURL: URL, username: String?, password: String?, completion: @escaping (Result<Void, Error>) -> Void) {
        var request = URLRequest(url: baseURL.appendingPathComponent("api/containers/\(id)/\(action)"))
        request.httpMethod = "POST"
        if let user = username, let pass = password, !user.isEmpty, !pass.isEmpty {
            let credential = "\(user):\(pass)".data(using: .utf8)!.base64EncodedString()
            request.setValue("Basic \(credential)", forHTTPHeaderField: "Authorization")
        }

        URLSession.shared.dataTask(with: request) { _, response, error in
            if let error = error {
                DispatchQueue.main.async { completion(.failure(error)) }
                return
            }
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                let code = (response as? HTTPURLResponse)?.statusCode ?? -1
                let err = NSError(domain: "HTTP", code: code, userInfo: [NSLocalizedDescriptionKey: "Action failed with status \(code)"])
                DispatchQueue.main.async { completion(.failure(err)) }
                return
            }
            DispatchQueue.main.async { completion(.success(())) }
        }.resume()
    }

    /// Request a CSV export from the backend. Returns the CSV data.
    func exportCSV(metrics: [ContainerStats], baseURL: URL, username: String?, password: String?, completion: @escaping (Result<Data, Error>) -> Void) {
        var request = URLRequest(url: baseURL.appendingPathComponent("api/export/csv"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let user = username, let pass = password, !user.isEmpty, !pass.isEmpty {
            let credential = "\(user):\(pass)".data(using: .utf8)!.base64EncodedString()
            request.setValue("Basic \(credential)", forHTTPHeaderField: "Authorization")
        }
        let encoder = JSONEncoder()
        request.httpBody = try? encoder.encode(["metrics": metrics.map { $0.dictionaryRepresentation }])

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                DispatchQueue.main.async { completion(.failure(error)) }
                return
            }
            guard let data = data else {
                DispatchQueue.main.async { completion(.failure(NSError(domain: "No data", code: -1, userInfo: nil))) }
                return
            }
            DispatchQueue.main.async { completion(.success(data)) }
        }.resume()
    }
}

private extension ContainerStats {
    /// Convert to dictionary for JSON encoding when exporting CSV.
    var dictionaryRepresentation: [String: Any] {
        let mirror = Mirror(reflecting: self)
        var dict: [String: Any] = [:]
        for child in mirror.children {
            if let key = child.label {
                dict[key] = child.value
            }
        }
        return dict
    }
}
