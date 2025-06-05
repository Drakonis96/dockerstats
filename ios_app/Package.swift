// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "DockerStatsApp",
    platforms: [.iOS(.v15)],
    products: [
        .iOSApplication(
            name: "DockerStatsApp",
            targets: ["DockerStatsApp"],
            bundleIdentifier: "com.example.dockerstats",
            teamIdentifier: "",
            displayVersion: "1.0",
            bundleVersion: "1",
            supportedDeviceFamilies: [.phone],
            supportedInterfaceOrientations: [
                .portrait,
                .portraitUpsideDown,
                .landscapeLeft,
                .landscapeRight
            ],
            additionalInfoPlistContentFilePath: "Info.plist"
        )
    ],
    targets: [
        .executableTarget(
            name: "DockerStatsApp",
            path: "Sources",
            resources: [
                .process("Resources")
            ]
        )
    ]
)
