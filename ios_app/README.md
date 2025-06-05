# DockerStats iOS Client

This directory contains a minimal SwiftUI application that can be used as a client for the DockerStats backend.

The app lets the user configure the backend URL and optional reverse proxy credentials. It verifies the connection and stores the configuration in the Keychain/`UserDefaults`. After a successful connection it displays the list of containers with all reported statistics.

## Building

1. Open Xcode and choose **File > Open...**. Select the `ios_app` folder.
2. Build and run the `DockerStatsApp` target on iOS 15 or later.
3. Enter your backend URL and credentials. Once connected, the container list will appear.

The project does not include any external dependencies.
