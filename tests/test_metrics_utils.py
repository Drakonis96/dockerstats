import metrics_utils


def test_parse_datetime_handles_nanoseconds_and_zero_dates():
    parsed = metrics_utils.parse_datetime("2024-05-01T10:11:12.123456789Z")
    assert parsed is not None
    assert parsed.year == 2024
    assert parsed.microsecond == 123456
    assert metrics_utils.parse_datetime("0001-01-01T00:00:00Z") is None


def test_format_uptime_and_memory_helpers():
    assert metrics_utils.format_uptime(3661) == "0d 1h 1m 1s"
    assert metrics_utils.format_uptime(-1) == "N/A"

    mem_percent, mem_usage = metrics_utils.calc_mem_percent_usage({
        "memory_stats": {
            "usage": 256 * 1024 * 1024,
            "limit": 1024 * 1024 * 1024,
        }
    })
    assert mem_percent == 25.0
    assert mem_usage == 256.0


def test_cpu_network_and_block_io_calculations():
    current = {
        "cpu_stats": {
            "cpu_usage": {
                "total_usage": 400,
                "percpu_usage": [1, 1],
            },
            "system_cpu_usage": 1000,
            "online_cpus": 2,
        }
    }
    previous = {
        "cpu_stats": {
            "cpu_usage": {
                "total_usage": 200,
                "percpu_usage": [1, 1],
            },
            "system_cpu_usage": 600,
            "online_cpus": 2,
        }
    }
    assert metrics_utils.calc_cpu_percent(current, previous) == 100.0

    net_rx, net_tx = metrics_utils.calc_net_io({
        "networks": {
            "eth0": {"rx_bytes": 3 * 1024 * 1024, "tx_bytes": 2 * 1024 * 1024},
            "eth1": {"rx_bytes": 1024 * 1024, "tx_bytes": 1024 * 1024},
        }
    })
    assert (net_rx, net_tx) == (4.0, 3.0)

    block_r, block_w = metrics_utils.calc_block_io({
        "blkio_stats": {
            "io_service_bytes_recursive": [
                {"op": "Read", "value": 2 * 1024 * 1024},
                {"op": "Write", "value": 5 * 1024 * 1024},
            ]
        }
    })
    assert (block_r, block_w) == (2.0, 5.0)
