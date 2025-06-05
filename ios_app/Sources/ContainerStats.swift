import Foundation

/// Representation of a container row from `/api/metrics`.
struct ContainerStats: Identifiable, Decodable {
    let id: String
    let name: String
    let pid_count: Int?
    let mem_limit: Double?
    let mem_usage: Double?
    let cpu: Double?
    let mem: Double?
    let combined: Double?
    let status: String?
    let uptime: String?
    let net_io_rx: Double?
    let net_io_tx: Double?
    let block_io_r: Double?
    let block_io_w: Double?
    let image: String?
    let ports: String?
    let restarts: Int?
    let update_available: Bool?
    let compose_project: String?
    let compose_service: String?
    let gpu: String?
    let gpu_max: Double?
}
