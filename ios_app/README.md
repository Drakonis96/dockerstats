# DockerStats iOS Client

This directory contains a SwiftUI application that acts as a mobile companion for the DockerStats backend.

The user can configure the backend URL and optional reverse proxy credentials directly in the app. Once verified, the configuration is stored securely using the Keychain and `UserDefaults`. After a successful connection the app lists your containers and shows all available metrics with CPU and RAM charts, search and filter controls, and actions to start/stop/restart containers. Notification preferences and CSV export are also available.

The colour scheme matches the web dashboard for a consistent look. Add your own `logo.png` file under `Resources/` if you wish to show the logo in the setup screen.

## Building

1. Open Xcode and choose **File > Open...**. Select the `ios_app` folder. Xcode will load the Swift Package.
2. Edit `Package.swift` and set the `teamIdentifier` field to your Apple Developer Team ID if you plan to run on a real device.
3. Build and run the `DockerStatsApp` target on iOS 15 or later.
4. Enter your backend URL and credentials. Once connected you can browse containers, control them, and tweak notification settings. Use the refresh interval picker to adjust how often stats are fetched. Export metrics to CSV or trigger an update check from the toolbar.

The project does not include any external dependencies. `Info.plist` contains minimal configuration for the app bundle and can be customised if needed.
