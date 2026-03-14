import pushover_client


class DummyResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def raise_for_status(self):
        return None


def test_send_reports_missing_configuration(monkeypatch):
    for env_var in [
        "PUSHOVER_TOKEN",
        "PUSHOVER_USER",
        "SLACK_WEBHOOK_URL",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "DISCORD_WEBHOOK_URL",
    ]:
        monkeypatch.delenv(env_var, raising=False)

    result = pushover_client.send("hello")

    assert result["ok"] is False
    assert result["configured_any"] is False
    assert result["channels"]["pushover"]["configured"] is False
    assert result["channels"]["pushover"]["skipped"] == "missing env vars"


def test_send_posts_to_configured_pushover(monkeypatch):
    monkeypatch.setenv("PUSHOVER_TOKEN", "token-123")
    monkeypatch.setenv("PUSHOVER_USER", "user-123")
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)

    captured = {}

    def fake_post(url, timeout, data=None, json=None):
        captured["url"] = url
        captured["timeout"] = timeout
        captured["data"] = data
        captured["json"] = json
        return DummyResponse(status_code=200)

    monkeypatch.setattr(pushover_client.requests, "post", fake_post)

    result = pushover_client.send("CPU high", title="Alert", priority=1)

    assert result["ok"] is True
    assert result["successful_channels"] == ["pushover"]
    assert captured["url"] == pushover_client.PUSHOVER_URL
    assert captured["data"]["token"] == "token-123"
    assert captured["data"]["user"] == "user-123"
    assert captured["data"]["message"] == "CPU high"
