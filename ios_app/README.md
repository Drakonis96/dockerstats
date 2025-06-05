# DockerStats iOS Client

This directory contains a minimal SwiftUI application that can be used as a client for the DockerStats backend.

The app lets the user configure the backend URL and optional reverse proxy credentials. It verifies the connection and stores the configuration in the Keychain/`UserDefaults`. After a successful connection it displays the list of containers with all reported statistics.

## Building

1. Open Xcode and choose **File > Open...**. Select the `ios_app` folder. Xcode will load the Swift Package.
2. Edit `Package.swift` and set the `teamIdentifier` field to your Apple Developer Team ID if you plan to run on a real device.
3. Build and run the `DockerStatsApp` target on iOS 15 or later.
4. Enter your backend URL and credentials. Once connected, the container list will appear.

The project does not include any external dependencies. `Info.plist` contains minimal configuration for the app bundle and can be customised if needed.
