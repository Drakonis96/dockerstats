import Foundation

struct NotificationSettings: Codable {
    var cpuThreshold: Double = 80
    var ramThreshold: Double = 80
    var alertOnStateChange: Bool = true
    var alertOnUpdates: Bool = true
}

class NotificationSettingsManager {
    static let shared = NotificationSettingsManager()
    private let key = "NotificationSettings"

    func load() -> NotificationSettings {
        guard let data = UserDefaults.standard.data(forKey: key),
              let settings = try? JSONDecoder().decode(NotificationSettings.self, from: data) else {
            return NotificationSettings()
        }
        return settings
    }

    func save(_ settings: NotificationSettings) {
        if let data = try? JSONEncoder().encode(settings) {
            UserDefaults.standard.set(data, forKey: key)
        }
    }
}
