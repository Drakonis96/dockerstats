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

    /// Retrieve container metrics from the server.
    func fetchMetrics(url: URL, username: String?, password: String?, completion: @escaping (Result<[ContainerStats], Error>) -> Void) {
        var request = URLRequest(url: url.appendingPathComponent("api/metrics"))
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
}
