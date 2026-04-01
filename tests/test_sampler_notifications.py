import time

import sampler


def reset_notification_runtime():
    sampler.recent_notification_cooldowns.clear()
    sampler.recent_notification_dedupes.clear()
    sampler.previous_security_findings.clear()


class DummyContainer:
    def __init__(self, attrs, cid="web123", name="web"):
        self.id = cid
        self.name = name
        self.attrs = attrs


def test_normalize_notification_settings_includes_advanced_defaults():
    settings = sampler.normalize_notification_settings({})

    assert settings["security_enabled"] is True
    assert settings["security_privileged_enabled"] is True
    assert settings["security_public_ports_enabled"] is True
    assert settings["security_latest_enabled"] is True
    assert settings["security_docker_socket_enabled"] is True
    assert settings["project_rule_mode"] == "all"
    assert settings["container_rule_mode"] == "all"
    assert settings["cooldown_seconds"] == 0
    assert settings["silence_enabled"] is False
    assert settings["silence_start"] == "22:00"
    assert settings["silence_end"] == "07:00"
    assert settings["dedupe_enabled"] is True
    assert settings["dedupe_window_seconds"] == 120


def test_should_emit_notification_applies_project_and_container_rules():
    reset_notification_runtime()
    settings = sampler.normalize_notification_settings({
        "project_rule_mode": "include",
        "project_rules": "demo\njobs-*",
        "container_rule_mode": "exclude",
        "container_rules": "db\nworker-*",
    })

    assert sampler.should_emit_notification({
        "type": "cpu",
        "cid": "web123",
        "container": "web",
        "project": "demo",
        "msg": "CPU high",
        "timestamp": 1000,
    }, settings=settings) is True

    reset_notification_runtime()
    assert sampler.should_emit_notification({
        "type": "cpu",
        "cid": "api123",
        "container": "api",
        "project": "other",
        "msg": "CPU high",
        "timestamp": 1000,
    }, settings=settings) is False

    reset_notification_runtime()
    assert sampler.should_emit_notification({
        "type": "cpu",
        "cid": "db123",
        "container": "db",
        "project": "demo",
        "msg": "CPU high",
        "timestamp": 1000,
    }, settings=settings) is False


def test_should_emit_notification_enforces_cooldown_and_deduplication():
    reset_notification_runtime()
    settings = sampler.normalize_notification_settings({
        "cooldown_seconds": 60,
        "dedupe_enabled": True,
        "dedupe_window_seconds": 300,
    })
    event = {
        "type": "cpu",
        "cid": "web123",
        "container": "web",
        "project": "demo",
        "msg": "CPU high",
    }

    assert sampler.should_emit_notification({**event, "timestamp": 1000}, settings=settings) is True
    assert sampler.should_emit_notification({**event, "timestamp": 1020}, settings=settings) is False
    assert sampler.should_emit_notification({**event, "timestamp": 1070}, settings=settings) is False
    assert sampler.should_emit_notification({**event, "timestamp": 1070, "msg": "CPU recovered then high again"}, settings=settings) is True


def test_should_emit_notification_respects_silence_window(monkeypatch):
    reset_notification_runtime()
    settings = sampler.normalize_notification_settings({
        "silence_enabled": True,
        "silence_start": "22:00",
        "silence_end": "07:00",
        "dedupe_enabled": False,
    })
    event = {
        "type": "status",
        "cid": "worker123",
        "container": "worker",
        "project": "jobs",
        "msg": "worker restarted",
        "timestamp": 2000,
    }

    monkeypatch.setattr(sampler.time, "localtime", lambda _ts: time.struct_time((2026, 1, 1, 23, 30, 0, 3, 1, -1)))
    assert sampler.should_emit_notification(event, settings=settings) is False

    reset_notification_runtime()
    monkeypatch.setattr(sampler.time, "localtime", lambda _ts: time.struct_time((2026, 1, 1, 12, 0, 0, 3, 1, -1)))
    assert sampler.should_emit_notification(event, settings=settings) is True


def test_should_emit_notification_uses_scope_for_security_cooldown():
    reset_notification_runtime()
    settings = sampler.normalize_notification_settings({
        "cooldown_seconds": 120,
        "dedupe_enabled": False,
    })

    assert sampler.should_emit_notification({
        "type": "security",
        "scope": "privileged",
        "cid": "web123",
        "container": "web",
        "msg": "web is privileged",
        "timestamp": 1000,
    }, settings=settings) is True

    assert sampler.should_emit_notification({
        "type": "security",
        "scope": "docker_socket",
        "cid": "web123",
        "container": "web",
        "msg": "web mounts docker.sock",
        "timestamp": 1000,
    }, settings=settings) is True


def test_collect_security_findings_reports_basic_container_risks():
    reset_notification_runtime()
    container = DummyContainer({
        "Config": {
            "Image": "nginx:latest",
            "Labels": {"com.docker.compose.project": "demo"},
        },
        "HostConfig": {"Privileged": True},
        "NetworkSettings": {
            "Ports": {
                "80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}],
            },
        },
        "Mounts": [
            {"Source": "/var/run/docker.sock", "Destination": "/var/run/docker.sock"},
        ],
    })

    findings = sampler.collect_security_findings(container)
    finding_ids = {finding["finding"] for finding in findings}

    assert finding_ids == {"privileged", "public_ports", "latest_tag", "docker_socket"}
    assert any("0.0.0.0:8080->80/tcp" in finding["msg"] for finding in findings if finding["finding"] == "public_ports")


def test_get_new_security_notifications_only_emits_new_findings_and_respects_toggles():
    reset_notification_runtime()
    base_attrs = {
        "Config": {
            "Image": "nginx:latest",
            "Labels": {"com.docker.compose.project": "demo"},
        },
        "HostConfig": {"Privileged": True},
        "NetworkSettings": {"Ports": {}},
        "Mounts": [],
    }
    container = DummyContainer(base_attrs)

    first = sampler.get_new_security_notifications(container)
    second = sampler.get_new_security_notifications(container)
    muted = sampler.collect_security_findings(container, settings={
        "security_enabled": True,
        "security_privileged_enabled": False,
        "security_latest_enabled": True,
    })

    assert {finding["finding"] for finding in first} == {"privileged", "latest_tag"}
    assert second == []
    assert {finding["finding"] for finding in muted} == {"latest_tag"}
