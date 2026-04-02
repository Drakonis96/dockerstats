import base64

import routes
import sampler
import users_db


def set_page_session(client, username="admin", csrf_token="test-csrf"):
    with client.session_transaction() as sess:
        sess["authenticated"] = True
        sess["username"] = username
        sess["csrf_token"] = csrf_token
    return csrf_token


def basic_auth_header(username, password):
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def set_auth_mode(client, mode="page", enabled=True):
    client.application.config["AUTH_ENABLED"] = enabled
    client.application.config["LOGIN_MODE"] = mode


def test_change_password_works_with_page_login_session(client, monkeypatch):
    set_auth_mode(client, "page")
    csrf_token = set_page_session(client)

    response = client.post(
        "/api/change-password",
        json={"current_password": "adminpass", "new_password": "better-pass"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert users_db.validate_user("admin", "better-pass") is True


def test_login_and_index_pages_render(client, monkeypatch):
    set_auth_mode(client, "page")

    login_response = client.get("/login")
    assert login_response.status_code == 200
    assert b"statainer" in login_response.data

    set_page_session(client)
    index_response = client.get("/")
    assert index_response.status_code == 200
    assert b"One cockpit for containers, updates and alerts." in index_response.data


def test_logout_clears_session_and_redirects_to_login(client):
    set_auth_mode(client, "page")
    set_page_session(client, username="admin")

    response = client.get("/logout")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert "no-cache" in response.headers["Cache-Control"]
    with client.session_transaction() as sess:
        assert "authenticated" not in sess
        assert "username" not in sess


def test_whoami_returns_authenticated_user_context(client):
    set_auth_mode(client, "page")
    set_page_session(client, username="admin")

    response = client.get("/whoami")

    assert response.status_code == 200
    assert response.get_json() == {"username": "admin", "role": "admin"}


def test_change_password_supports_basic_auth(client, monkeypatch):
    set_auth_mode(client, "popup")
    with client.session_transaction() as sess:
        sess["csrf_token"] = "popup-csrf"
    csrf_token = "popup-csrf"

    response = client.post(
        "/api/change-password",
        json={"current_password": "adminpass", "new_password": "popup-pass"},
        headers={
            "X-CSRFToken": csrf_token,
            **basic_auth_header("admin", "adminpass"),
        },
    )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert users_db.validate_user("admin", "popup-pass") is True


def test_user_management_requires_admin(client, monkeypatch):
    users_db.create_user_with_columns("alice", "alice-pass", ["cpu"])
    set_auth_mode(client, "page")
    csrf_token = set_page_session(client, username="alice")

    response = client.get("/api/users")
    assert response.status_code == 403

    delete_response = client.delete(
        "/api/users/alice",
        headers={"X-CSRFToken": csrf_token},
    )
    assert delete_response.status_code == 403


def test_notification_settings_roundtrip_for_admin(client, monkeypatch):
    set_auth_mode(client, "page")
    csrf_token = set_page_session(client)

    response = client.post(
        "/api/notification-settings",
        json={
            "cpu_enabled": False,
            "ram_enabled": True,
            "status_enabled": True,
            "update_enabled": False,
            "security_enabled": True,
            "security_privileged_enabled": True,
            "security_public_ports_enabled": False,
            "security_latest_enabled": False,
            "security_docker_socket_enabled": True,
            "cpu_threshold": 55,
            "ram_threshold": 65,
            "window_seconds": 25,
            "cooldown_seconds": 90,
            "project_rule_mode": "include",
            "project_rules": "demo\njobs-*",
            "container_rule_mode": "exclude",
            "container_rules": "db\nworker-*",
            "silence_enabled": True,
            "silence_start": "23:00",
            "silence_end": "06:30",
            "dedupe_enabled": True,
            "dedupe_window_seconds": 300,
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["settings"]["cpu_threshold"] == 55
    assert payload["settings"]["cooldown_seconds"] == 90
    assert payload["settings"]["project_rule_mode"] == "include"
    assert payload["settings"]["container_rule_mode"] == "exclude"
    assert payload["settings"]["security_public_ports_enabled"] is False
    assert payload["settings"]["security_latest_enabled"] is False
    assert payload["settings"]["silence_enabled"] is True
    assert payload["settings"]["dedupe_window_seconds"] == 300

    get_response = client.get("/api/notification-settings")
    assert get_response.status_code == 200
    assert get_response.get_json()["window_seconds"] == 25
    assert get_response.get_json()["project_rules"] == "demo\njobs-*"
    assert get_response.get_json()["security_public_ports_enabled"] is False


def test_notification_settings_defaults_disable_security_advisories(client, monkeypatch):
    set_auth_mode(client, "page")
    set_page_session(client)

    response = client.get("/api/notification-settings")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["security_enabled"] is False
    assert payload["security_privileged_enabled"] is False
    assert payload["security_public_ports_enabled"] is False
    assert payload["security_latest_enabled"] is False
    assert payload["security_docker_socket_enabled"] is False


def test_notification_test_reports_missing_configuration(client, monkeypatch):
    set_auth_mode(client, "page")
    monkeypatch.setattr(routes, "send_notification", lambda *args, **kwargs: {
        "ok": False,
        "configured_any": False,
        "successful_channels": [],
        "channels": {
            "pushover": {"configured": False, "ok": False, "skipped": "missing env vars"},
            "ntfy": {"configured": False, "ok": False, "skipped": "missing env vars"},
            "webhook": {"configured": False, "ok": False, "skipped": "missing env vars"},
        },
    })
    csrf_token = set_page_session(client)

    response = client.post(
        "/api/notification-test",
        json={"message": "hello"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["configured_any"] is False


def test_update_manager_list_endpoint_returns_inventory_for_admin(client, monkeypatch):
    set_auth_mode(client, "page")
    set_page_session(client)

    monkeypatch.setattr(routes.update_manager, "list_update_targets", lambda history_limit=20, force_refresh=False: {
        "experimental_notice": "Experimental feature.",
        "projects": [{"target_id": "demo", "name": "demo", "type": "project"}],
        "containers": [{"target_id": "cache", "name": "cache", "type": "container"}],
        "history": [],
        "history_limit": history_limit,
        "force_refresh": force_refresh,
    })

    response = client.get("/api/update-manager?history_limit=15&refresh=1")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["projects"][0]["name"] == "demo"
    assert payload["containers"][0]["name"] == "cache"
    assert payload["force_refresh"] is True


def test_update_manager_update_endpoint_executes_target(client, monkeypatch):
    set_auth_mode(client, "page")
    csrf_token = set_page_session(client)

    monkeypatch.setattr(routes.update_manager, "update_target", lambda target_type, target_id, actor_username=None: {
        "ok": True,
        "message": f"{target_type}:{target_id} updated",
        "history_entry": {"id": 7, "target_type": target_type, "target_id": target_id},
    })

    response = client.post(
        "/api/update-manager/update",
        json={"target_type": "project", "target_id": "demo"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["history_entry"]["id"] == 7


def test_update_manager_update_endpoint_emits_success_notification(client, monkeypatch):
    set_auth_mode(client, "page")
    csrf_token = set_page_session(client)
    emitted = []

    monkeypatch.setattr(routes.update_manager, "update_target", lambda target_type, target_id, actor_username=None: {
        "ok": True,
        "message": f"{target_type}:{target_id} updated",
        "history_entry": {"id": 11, "target_type": target_type, "target_id": target_id},
    })
    monkeypatch.setattr(routes.sampler, "emit_notification", lambda event: emitted.append(event))

    response = client.post(
        "/api/update-manager/update",
        json={"target_type": "project", "target_id": "demo"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert emitted == [{
        "type": "update",
        "scope": "update_success",
        "timestamp": emitted[0]["timestamp"],
        "cid": None,
        "container": "",
        "project": "demo",
        "msg": "project:demo updated",
    }]


def test_update_manager_update_endpoint_emits_failure_notification(client, monkeypatch):
    set_auth_mode(client, "page")
    csrf_token = set_page_session(client)
    emitted = []

    monkeypatch.setattr(routes.update_manager, "update_target", lambda target_type, target_id, actor_username=None: {
        "ok": False,
        "message": f"{target_type}:{target_id} failed",
        "history_entry": {"id": 12, "target_type": target_type, "target_id": target_id},
    })
    monkeypatch.setattr(routes.sampler, "emit_notification", lambda event: emitted.append(event))

    response = client.post(
        "/api/update-manager/update",
        json={"target_type": "container", "target_id": "cache-standalone"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 409
    assert emitted == [{
        "type": "update",
        "scope": "update_failure",
        "timestamp": emitted[0]["timestamp"],
        "cid": "cache-standalone",
        "container": "cache-standalone",
        "project": "",
        "msg": "container:cache-standalone failed",
    }]


def test_update_manager_rollback_endpoint_reports_failure_state(client, monkeypatch):
    set_auth_mode(client, "page")
    csrf_token = set_page_session(client)

    monkeypatch.setattr(routes.update_manager, "rollback_update", lambda history_id, actor_username=None: {
        "ok": False,
        "message": f"Rollback {history_id} failed",
        "history_entry": {"id": 9, "result": "failure"},
    })

    response = client.post(
        "/api/update-manager/rollback",
        json={"history_id": 9},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 409
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["message"] == "Rollback 9 failed"


def test_system_status_exposes_backend_diagnostics(client, monkeypatch):
    set_auth_mode(client, "page")
    set_page_session(client, username="admin")
    monkeypatch.setattr(routes, "get_configured_services", lambda: {
        "pushover": {"configured": True},
        "slack": {"configured": False},
        "telegram": {"configured": False},
        "discord": {"configured": False},
        "ntfy": {"configured": False},
        "webhook": {"configured": False},
    })
    monkeypatch.setattr(routes, "get_docker_status", lambda: {
        "connected": False,
        "base_url": "unix:///var/run/docker.sock",
        "error": "daemon unavailable",
    })

    response = client.get("/api/system-status")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["docker"]["connected"] is False
    assert payload["notifications"]["pushover"]["configured"] is True
    assert payload["auth"]["role"] == "admin"
    assert payload["app"]["version"] == "test-version"


def test_projects_endpoint_returns_sorted_unique_compose_projects(client, monkeypatch):
    set_auth_mode(client, "page")
    set_page_session(client)

    class DummyContainer:
        def __init__(self, project):
            self.attrs = {
                "Config": {
                    "Labels": {"com.docker.compose.project": project} if project else {},
                },
            }

    class DummyContainers:
        def list(self, all=True):
            assert all is True
            return [
                DummyContainer("demo"),
                DummyContainer("jobs"),
                DummyContainer("demo"),
                DummyContainer(None),
            ]

    class DummyClient:
        containers = DummyContainers()

    monkeypatch.setattr(routes, "get_docker_client", lambda: DummyClient())

    response = client.get("/api/projects")

    assert response.status_code == 200
    assert response.get_json() == ["demo", "jobs"]


def test_metrics_summary_mode_returns_project_dashboard_payload(client, monkeypatch):
    set_auth_mode(client, "page")
    set_page_session(client)

    rows = [
        {
            "id": "web123",
            "name": "web",
            "status": "running",
            "cpu": 72.5,
            "mem": 64.2,
            "mem_usage": 657.4,
            "mem_limit": 1024.0,
            "restarts": 1,
            "update_available": False,
            "compose_project": "demo",
        },
        {
            "id": "db123",
            "name": "db",
            "status": "running",
            "cpu": 24.0,
            "mem": 52.0,
            "mem_usage": 1102.2,
            "mem_limit": 2048.0,
            "restarts": 0,
            "update_available": True,
            "compose_project": "demo",
        },
        {
            "id": "worker123",
            "name": "worker",
            "status": "exited",
            "cpu": 0.0,
            "mem": 0.0,
            "mem_usage": 0.0,
            "mem_limit": 512.0,
            "restarts": 2,
            "update_available": False,
            "compose_project": "jobs",
        },
    ]

    def fake_collect_metrics_rows(query):
        assert query["max_items"] == 0
        return rows

    monkeypatch.setattr(routes, "collect_metrics_rows", fake_collect_metrics_rows)

    response = client.get("/api/metrics?summary=1&max=1")

    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["id"] == "web123"
    assert len(payload["project_summaries"]) == 2
    assert payload["project_summaries"][0]["project"] == "demo"
    assert payload["project_summaries"][0]["container_count"] == 2
    assert payload["project_summaries"][0]["running_count"] == 2
    assert payload["project_summaries"][0]["update_count"] == 1
    assert payload["project_summaries"][0]["status"] == "healthy"
    assert payload["project_summaries"][1]["project"] == "jobs"
    assert payload["project_summaries"][1]["status"] == "stopped"


def test_notifications_endpoint_supports_since_and_limit(client, monkeypatch):
    set_auth_mode(client, "page")
    set_page_session(client)

    def fake_get_notifications(since_ts=None, max_items=50):
        assert since_ts == 10.0
        assert max_items == 5
        return [{"timestamp": 12.5, "msg": "worker restarted", "type": "status"}]

    monkeypatch.setattr(sampler, "get_notifications", fake_get_notifications)

    response = client.get("/api/notifications?since=10&max=5")

    assert response.status_code == 200
    assert response.get_json() == [{"timestamp": 12.5, "msg": "worker restarted", "type": "status"}]


def test_audit_log_records_password_and_user_management_actions(client):
    set_auth_mode(client, "page")
    csrf_token = set_page_session(client)

    password_response = client.post(
        "/api/change-password",
        json={"current_password": "adminpass", "new_password": "new-pass"},
        headers={"X-CSRFToken": csrf_token},
    )
    assert password_response.status_code == 200

    create_response = client.post(
        "/api/users",
        json={"username": "bob", "password": "bob-pass", "columns": ["cpu"]},
        headers={"X-CSRFToken": csrf_token},
    )
    assert create_response.status_code == 200

    audit_response = client.get("/api/audit?limit=10")
    assert audit_response.status_code == 200
    events = audit_response.get_json()
    assert any(event["action"] == "user.password_change" and event["status"] == "success" for event in events)
    assert any(event["action"] == "user.create" and event["target_id"] == "bob" for event in events)


def test_container_actions_are_audited(client, monkeypatch):
    set_auth_mode(client, "page")
    csrf_token = set_page_session(client)

    class DummyContainer:
        name = "web"

        def start(self):
            return None

    class DummyContainers:
        def get(self, container_id):
            assert container_id == "abc123"
            return DummyContainer()

    class DummyClient:
        containers = DummyContainers()

    monkeypatch.setattr(routes, "get_docker_client", lambda: DummyClient())

    response = client.post(
        "/api/containers/abc123/start",
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    audit_events = users_db.list_audit_events(limit=10)
    assert any(event["action"] == "container.start" and event["target_id"] == "abc123" for event in audit_events)


def test_container_update_action_emits_update_notification(client, monkeypatch):
    set_auth_mode(client, "page")
    csrf_token = set_page_session(client)
    emitted = []

    class DummyContainer:
        name = "cache"

    class DummyContainers:
        def get(self, container_id):
            assert container_id == "abc123"
            return DummyContainer()

    class DummyClient:
        containers = DummyContainers()

    monkeypatch.setattr(routes, "get_docker_client", lambda: DummyClient())
    monkeypatch.setattr(routes.update_manager, "update_container_target", lambda container_id, actor_username=None: {
        "ok": True,
        "message": "Container cache updated safely.",
        "history_entry": {"id": 14, "target_type": "container", "target_id": container_id},
    })
    monkeypatch.setattr(routes.sampler, "emit_notification", lambda event: emitted.append(event))

    response = client.post(
        "/api/containers/abc123/update",
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert emitted == [{
        "type": "update",
        "scope": "update_success",
        "timestamp": emitted[0]["timestamp"],
        "cid": "abc123",
        "container": "cache",
        "project": "",
        "msg": "Container cache updated safely.",
    }]


def test_metrics_stream_can_emit_single_snapshot(client, monkeypatch):
    set_auth_mode(client, "page")
    set_page_session(client)
    monkeypatch.setattr(routes, "collect_metrics_rows", lambda query: [{"id": "abc", "name": "web", "status": "running"}])
    monkeypatch.setattr(routes.sampler, "get_metrics_sequence", lambda: 1)
    monkeypatch.setattr(routes.sampler, "get_notification_sequence", lambda: 0)
    monkeypatch.setattr(routes.sampler, "get_notifications", lambda since_ts=None, max_items=200: [])

    response = client.get("/api/stream?once=1")

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "event: connected" in body
    assert "event: metrics" in body
    assert '"name": "web"' in body


def test_logs_snapshot_returns_downloadable_text_file(client, monkeypatch):
    set_auth_mode(client, "page")
    set_page_session(client)

    class DummyContainer:
        name = "db primary"

        def logs(self, tail=100, timestamps=True):
            assert tail == 2
            assert timestamps is True
            return b"log line 1\nlog line 2\n"

    class DummyContainers:
        def get(self, container_id):
            assert container_id == "abc123"
            return DummyContainer()

    class DummyClient:
        containers = DummyContainers()

    monkeypatch.setattr(routes, "get_docker_client", lambda: DummyClient())

    response = client.get("/api/logs/abc123?tail=2&download=1")

    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    assert response.get_data(as_text=True) == "log line 1\nlog line 2\n"
    assert response.headers["Content-Disposition"] == 'attachment; filename="db-primary-abc123-logs.txt"'


def test_logs_stream_emits_connected_snapshot_and_live_lines(client, monkeypatch):
    set_auth_mode(client, "page")
    set_page_session(client)

    class DummyContainer:
        name = "db"

        def logs(self, tail=100, timestamps=True, stream=False, follow=False):
            assert timestamps is True
            if stream:
                assert tail == 0
                assert follow is True
                return iter([
                    b"2026-01-01T10:00:20.000000000Z db | live line 1\n",
                    b"2026-01-01T10:00:21.000000000Z db | live line 2\n",
                ])
            assert tail == 2
            return b"2026-01-01T10:00:00.000000000Z db | snapshot line 1\n2026-01-01T10:00:10.000000000Z db | snapshot line 2\n"

    class DummyContainers:
        def get(self, container_id):
            assert container_id == "abc123"
            return DummyContainer()

    class DummyClient:
        containers = DummyContainers()

    monkeypatch.setattr(routes, "get_docker_client", lambda: DummyClient())

    response = client.get("/api/logs/abc123/stream?tail=2")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    assert "event: connected" in body
    assert "event: snapshot" in body
    assert "event: line" in body
    assert '"container_name": "db"' in body
    assert "snapshot line 1" in body
    assert "live line 2" in body


def test_export_csv_returns_downloadable_csv(client):
    set_auth_mode(client, "page")
    csrf_token = set_page_session(client)

    response = client.post(
        "/api/export/csv",
        json={"metrics": [{"name": "web", "cpu": 12.5}, {"name": "db", "cpu": 8.0}]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "attachment; filename=metrics.csv" == response.headers["Content-Disposition"]
    body = response.get_data(as_text=True).splitlines()
    assert body[0] in {"name,cpu", "cpu,name"}
    assert set(body[1:]) == {"web,12.5", "db,8.0"} or set(body[1:]) == {"12.5,web", "8.0,db"}
