import SwiftUI

struct NotificationSettingsView: View {
    @Environment(\.dismiss) var dismiss
    @State private var settings = NotificationSettingsManager.shared.load()

    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Thresholds")) {
                    Stepper(value: $settings.cpuThreshold, in: 10...100, step: 5) {
                        Text("CPU Alert Threshold: \(Int(settings.cpuThreshold))%")
                    }
                    Stepper(value: $settings.ramThreshold, in: 10...100, step: 5) {
                        Text("RAM Alert Threshold: \(Int(settings.ramThreshold))%")
                    }
                }
                Section(header: Text("Events")) {
                    Toggle("Container state changes", isOn: $settings.alertOnStateChange)
                    Toggle("Update availability", isOn: $settings.alertOnUpdates)
                }
            }
            .navigationTitle("Notifications")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        NotificationSettingsManager.shared.save(settings)
                        dismiss()
                    }
                }
            }
        }
    }
}
