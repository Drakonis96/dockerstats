// swift-tools-version:5.5
import PackageDescription

let package = Package(
    name: "DockerStatsApp",
    platforms: [.iOS(.v15)],
    products: [
        .executable(name: "DockerStatsApp", targets: ["DockerStatsApp"])
    ],
    targets: [
        .executableTarget(
            name: "DockerStatsApp",
            path: "Sources"
        )
    ]
)
