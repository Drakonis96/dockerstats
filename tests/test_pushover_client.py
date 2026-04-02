import pushover_client


ALL_NOTIFICATION_ENV_VARS = [
    "PUSHOVER_TOKEN",
    "PUSHOVER_USER",
    "SLACK_WEBHOOK_URL",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "DISCORD_WEBHOOK_URL",
    "NTFY_SERVER_URL",
    "NTFY_TOPIC",
    "NTFY_TOKEN",
    "NTFY_USERNAME",
    "NTFY_PASSWORD",
    "NTFY_TAGS",
    "NTFY_MARKDOWN",
    "NTFY_TIMEOUT",
    "GENERIC_WEBHOOK_URL",
    "GENERIC_WEBHOOK_METHOD",
    "GENERIC_WEBHOOK_HEADERS",
    "GENERIC_WEBHOOK_CONTENT_TYPE",
    "GENERIC_WEBHOOK_BODY_TEMPLATE",
    "GENERIC_WEBHOOK_TIMEOUT",
]


class DummyResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def raise_for_status(self):
        return None


def clear_notification_env(monkeypatch):
    for env_var in ALL_NOTIFICATION_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


def test_send_reports_missing_configuration(monkeypatch):
    clear_notification_env(monkeypatch)

    result = pushover_client.send("hello")

    assert result["ok"] is False
    assert result["configured_any"] is False
    assert result["channels"]["pushover"]["configured"] is False
    assert result["channels"]["ntfy"]["configured"] is False
    assert result["channels"]["webhook"]["configured"] is False
    assert result["channels"]["pushover"]["skipped"] == "missing env vars"
    assert result["channels"]["ntfy"]["skipped"] == "missing env vars"
    assert result["channels"]["webhook"]["skipped"] == "missing env vars"


def test_send_posts_to_configured_pushover(monkeypatch):
    clear_notification_env(monkeypatch)
    monkeypatch.setenv("PUSHOVER_TOKEN", "token-123")
    monkeypatch.setenv("PUSHOVER_USER", "user-123")

    captured = {}

    def fake_post(url, timeout, data=None, json=None, headers=None, auth=None):
        captured["url"] = url
        captured["timeout"] = timeout
        captured["data"] = data
        captured["json"] = json
        captured["headers"] = headers
        captured["auth"] = auth
        return DummyResponse(status_code=200)

    monkeypatch.setattr(pushover_client.requests, "post", fake_post)

    result = pushover_client.send("CPU high", title="Alert", priority=1)

    assert result["ok"] is True
    assert result["successful_channels"] == ["pushover"]
    assert captured["url"] == pushover_client.PUSHOVER_URL
    assert captured["data"]["token"] == "token-123"
    assert captured["data"]["user"] == "user-123"
    assert captured["data"]["message"] == "CPU high"
    assert captured["headers"] is None
    assert captured["auth"] is None


def test_send_posts_to_configured_ntfy(monkeypatch):
    clear_notification_env(monkeypatch)
    monkeypatch.setenv("NTFY_SERVER_URL", "https://ntfy.example.com")
    monkeypatch.setenv("NTFY_TOPIC", "statainer")
    monkeypatch.setenv("NTFY_TOKEN", "tk_secret")
    monkeypatch.setenv("NTFY_TAGS", "prod,ops")

    captured = {}

    def fake_post(url, timeout, data=None, json=None, headers=None, auth=None):
        captured["url"] = url
        captured["timeout"] = timeout
        captured["data"] = data
        captured["json"] = json
        captured["headers"] = headers
        captured["auth"] = auth
        return DummyResponse(status_code=202)

    monkeypatch.setattr(pushover_client.requests, "post", fake_post)

    result = pushover_client.send(
        "CPU high",
        title="Alert",
        priority=1,
        event={"type": "cpu", "container": "api", "cid": "abc123", "timestamp": 42.0},
    )

    assert result["ok"] is True
    assert result["successful_channels"] == ["ntfy"]
    assert captured["url"] == "https://ntfy.example.com/statainer"
    assert captured["timeout"] == 5
    assert captured["data"] == b"CPU high"
    assert captured["headers"]["Title"] == "Alert"
    assert captured["headers"]["Priority"] == "4"
    assert captured["headers"]["Authorization"] == "Bearer tk_secret"
    assert captured["headers"]["Tags"] == "prod,ops,statainer,cpu"
    assert captured["auth"] is None


def test_send_posts_default_json_to_generic_webhook(monkeypatch):
    clear_notification_env(monkeypatch)
    monkeypatch.setenv("GENERIC_WEBHOOK_URL", "https://hooks.example.com/statainer")
    monkeypatch.setenv("GENERIC_WEBHOOK_HEADERS", '{"Authorization":"Bearer 123","X-Source":"tests"}')

    captured = {}

    def fake_request(**kwargs):
        captured.update(kwargs)
        return DummyResponse(status_code=204)

    monkeypatch.setattr(pushover_client.requests, "request", fake_request)

    result = pushover_client.send(
        "Status changed",
        title="statainer STATUS",
        priority=1,
        event={
            "type": "status",
            "container": "worker",
            "cid": "cid-1",
            "value": "running",
            "prev_value": "restarting",
            "timestamp": 123.5,
            "msg": "worker: Status changed from restarting to running",
        },
    )

    assert result["ok"] is True
    assert result["successful_channels"] == ["webhook"]
    assert captured["method"] == "POST"
    assert captured["url"] == "https://hooks.example.com/statainer"
    assert captured["timeout"] == 5
    assert captured["headers"]["Authorization"] == "Bearer 123"
    assert captured["headers"]["X-Source"] == "tests"
    assert captured["json"]["title"] == "statainer STATUS"
    assert captured["json"]["message"] == "Status changed"
    assert captured["json"]["event_type"] == "status"
    assert captured["json"]["container"] == "worker"
    assert captured["json"]["container_id"] == "cid-1"
    assert captured["json"]["value"] == "running"
    assert captured["json"]["prev_value"] == "restarting"
    assert captured["json"]["timestamp"] == 123.5


def test_send_supports_custom_generic_webhook_body_template(monkeypatch):
    clear_notification_env(monkeypatch)
    monkeypatch.setenv("GENERIC_WEBHOOK_URL", "https://hooks.example.com/plain")
    monkeypatch.setenv("GENERIC_WEBHOOK_METHOD", "PUT")
    monkeypatch.setenv("GENERIC_WEBHOOK_CONTENT_TYPE", "text/plain; charset=utf-8")
    monkeypatch.setenv("GENERIC_WEBHOOK_BODY_TEMPLATE", "[{event_type}] {container}: {message}")

    captured = {}

    def fake_request(**kwargs):
        captured.update(kwargs)
        return DummyResponse(status_code=200)

    monkeypatch.setattr(pushover_client.requests, "request", fake_request)

    result = pushover_client.send(
        "Container restarted",
        title="statainer STATUS",
        priority=0,
        event={"type": "status", "container": "worker", "timestamp": 88.0},
    )

    assert result["ok"] is True
    assert result["successful_channels"] == ["webhook"]
    assert captured["method"] == "PUT"
    assert captured["headers"]["Content-Type"] == "text/plain; charset=utf-8"
    assert captured["data"] == b"[status] worker: Container restarted"
    assert "json" not in captured
