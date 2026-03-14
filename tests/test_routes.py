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
    assert b"Docker Control Plane" in login_response.data

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
            "cpu_threshold": 55,
            "ram_threshold": 65,
            "window_seconds": 25,
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["settings"]["cpu_threshold"] == 55

    get_response = client.get("/api/notification-settings")
    assert get_response.status_code == 200
    assert get_response.get_json()["window_seconds"] == 25


def test_notification_test_reports_missing_configuration(client, monkeypatch):
    set_auth_mode(client, "page")
    monkeypatch.setattr(routes, "send_notification", lambda *args, **kwargs: {
        "ok": False,
        "configured_any": False,
        "successful_channels": [],
        "channels": {
            "pushover": {"configured": False, "ok": False, "skipped": "missing env vars"},
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


def test_system_status_exposes_backend_diagnostics(client, monkeypatch):
    set_auth_mode(client, "page")
    set_page_session(client, username="admin")
    monkeypatch.setattr(routes, "get_configured_services", lambda: {
        "pushover": {"configured": True},
        "slack": {"configured": False},
        "telegram": {"configured": False},
        "discord": {"configured": False},
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
