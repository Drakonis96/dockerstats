# pushover_client.py
import datetime
import json
import logging
import os
import socket

import requests

PUSHOVER_URL = "https://api.pushover.net/1/messages.json"
DEFAULT_HOST = socket.gethostname()


def get_configured_services():
    """Return a structured view of which notification channels are configured."""
    return {
        "pushover": {
            "configured": bool(os.getenv("PUSHOVER_TOKEN") and os.getenv("PUSHOVER_USER")),
        },
        "slack": {
            "configured": bool(os.getenv("SLACK_WEBHOOK_URL")),
        },
        "telegram": {
            "configured": bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID")),
        },
        "discord": {
            "configured": bool(os.getenv("DISCORD_WEBHOOK_URL")),
        },
        "ntfy": {
            "configured": bool(os.getenv("NTFY_TOPIC")),
        },
        "webhook": {
            "configured": bool(os.getenv("GENERIC_WEBHOOK_URL")),
        },
    }


def _ok_result(configured, status_code):
    return {
        "configured": configured,
        "ok": True,
        "status_code": status_code,
    }


def _error_result(configured, error=None, skipped=None):
    result = {
        "configured": configured,
        "ok": False,
    }
    if error:
        result["error"] = error
    if skipped:
        result["skipped"] = skipped
    return result


def _safe_text(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    return str(value)


class _FormatDict(dict):
    def __missing__(self, key):
        return ""


def _env_truthy(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_timeout(name, default=5):
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        timeout = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if timeout <= 0:
        raise ValueError(f"{name} must be greater than 0")
    return timeout


def _priority_label(priority):
    try:
        numeric = int(priority)
    except (TypeError, ValueError):
        numeric = 0
    if numeric >= 2:
        return "urgent"
    if numeric == 1:
        return "high"
    if numeric == 0:
        return "normal"
    if numeric == -1:
        return "low"
    return "lowest"


def _build_context(message, title, priority, event=None):
    event = dict(event or {})
    timestamp = float(event.get("timestamp", datetime.datetime.now(datetime.timezone.utc).timestamp()))
    timestamp_iso = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc).isoformat()
    return {
        "app": "Docker Stats",
        "host": DEFAULT_HOST,
        "title": _safe_text(title),
        "message": _safe_text(message),
        "priority": _safe_text(priority),
        "priority_label": _priority_label(priority),
        "event_type": _safe_text(event.get("type")),
        "container": _safe_text(event.get("container")),
        "container_id": _safe_text(event.get("cid")),
        "value": _safe_text(event.get("value")),
        "prev_value": _safe_text(event.get("prev_value")),
        "timestamp": _safe_text(timestamp),
        "timestamp_iso": timestamp_iso,
        "event_json": json.dumps(event, ensure_ascii=True, sort_keys=True),
        "event": event,
    }


def _render_template(template, context):
    try:
        return template.format_map(_FormatDict(context))
    except Exception as exc:
        raise ValueError(f"invalid template: {exc}") from exc


def _parse_header_mapping(raw_value, env_name):
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{env_name} must be a valid JSON object") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{env_name} must be a JSON object")

    headers = {}
    for key, value in parsed.items():
        headers[str(key)] = _safe_text(value)
    return headers


def _merge_csv_values(*value_sets):
    seen = set()
    merged = []
    for value_set in value_sets:
        for value in (value_set or "").split(","):
            normalized = value.strip()
            if normalized and normalized not in seen:
                merged.append(normalized)
                seen.add(normalized)
    return ",".join(merged)


def _map_ntfy_priority(priority):
    try:
        numeric = int(priority)
    except (TypeError, ValueError):
        numeric = 0
    if numeric >= 2:
        return "5"
    if numeric == 1:
        return "4"
    if numeric == 0:
        return "3"
    if numeric == -1:
        return "2"
    return "1"


def _send_pushover(message, title, priority):
    pushover_token = os.getenv("PUSHOVER_TOKEN")
    pushover_user = os.getenv("PUSHOVER_USER")
    resp = requests.post(
        PUSHOVER_URL,
        timeout=5,
        data={
            "token": pushover_token,
            "user": pushover_user,
            "title": title,
            "message": message,
            "priority": priority,
        },
    )
    resp.raise_for_status()
    return resp


def _send_slack(message, title):
    resp = requests.post(
        os.getenv("SLACK_WEBHOOK_URL"),
        timeout=5,
        json={"text": f"*{title}*\n{message}"},
    )
    resp.raise_for_status()
    return resp


def _send_telegram(message, title):
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
    resp = requests.post(
        url,
        timeout=5,
        data={"chat_id": telegram_chat_id, "text": f"{title}\n{message}"},
    )
    resp.raise_for_status()
    return resp


def _send_discord(message, title):
    resp = requests.post(
        os.getenv("DISCORD_WEBHOOK_URL"),
        timeout=5,
        json={"content": f"**{title}**\n{message}"},
    )
    resp.raise_for_status()
    return resp


def _send_ntfy(message, title, priority, context):
    topic = (os.getenv("NTFY_TOPIC") or "").strip().strip("/")
    if not topic:
        raise ValueError("NTFY_TOPIC is required")

    server_url = (os.getenv("NTFY_SERVER_URL") or "https://ntfy.sh").strip().rstrip("/")
    headers = {
        "Title": title,
        "Priority": _map_ntfy_priority(priority),
    }
    if _env_truthy("NTFY_MARKDOWN", False):
        headers["Markdown"] = "yes"

    headers["Tags"] = _merge_csv_values(
        os.getenv("NTFY_TAGS"),
        "dockerstats",
        context.get("event_type"),
    )

    token = os.getenv("NTFY_TOKEN")
    username = os.getenv("NTFY_USERNAME")
    password = os.getenv("NTFY_PASSWORD")
    auth = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif username or password:
        if not (username and password):
            raise ValueError("NTFY_USERNAME and NTFY_PASSWORD must be set together")
        auth = (username, password)

    resp = requests.post(
        f"{server_url}/{topic}",
        timeout=_parse_timeout("NTFY_TIMEOUT", default=5),
        data=message.encode("utf-8"),
        headers=headers,
        auth=auth,
    )
    resp.raise_for_status()
    return resp


def _build_generic_webhook_payload(context):
    event = context.get("event") or {}
    return {
        "app": context["app"],
        "host": context["host"],
        "title": context["title"],
        "message": context["message"],
        "priority": context["priority"],
        "priority_label": context["priority_label"],
        "event_type": context["event_type"],
        "container": context["container"],
        "container_id": context["container_id"],
        "value": event.get("value"),
        "prev_value": event.get("prev_value"),
        "timestamp": float(context.get("timestamp") or 0),
        "timestamp_iso": context["timestamp_iso"],
        "event": event,
    }


def _send_generic_webhook(context):
    webhook_url = (os.getenv("GENERIC_WEBHOOK_URL") or "").strip()
    if not webhook_url:
        raise ValueError("GENERIC_WEBHOOK_URL is required")

    method = (os.getenv("GENERIC_WEBHOOK_METHOD") or "POST").strip().upper()
    headers = _parse_header_mapping(os.getenv("GENERIC_WEBHOOK_HEADERS"), "GENERIC_WEBHOOK_HEADERS")
    content_type = (os.getenv("GENERIC_WEBHOOK_CONTENT_TYPE") or "").strip()
    body_template = os.getenv("GENERIC_WEBHOOK_BODY_TEMPLATE")

    request_kwargs = {
        "method": method,
        "url": webhook_url,
        "timeout": _parse_timeout("GENERIC_WEBHOOK_TIMEOUT", default=5),
        "headers": headers,
    }

    if body_template:
        if content_type and "Content-Type" not in headers:
            headers["Content-Type"] = content_type
        elif "Content-Type" not in headers:
            headers["Content-Type"] = "text/plain; charset=utf-8"
        request_kwargs["data"] = _render_template(body_template, context).encode("utf-8")
    else:
        if content_type and "Content-Type" not in headers:
            headers["Content-Type"] = content_type
        request_kwargs["json"] = _build_generic_webhook_payload(context)

    resp = requests.request(**request_kwargs)
    resp.raise_for_status()
    return resp


def send(message, title="Docker-Stats", priority=0, event=None):
    """Send a notification to all configured services and return per-channel status."""
    configured = get_configured_services()
    context = _build_context(message, title, priority, event=event)
    channel_results = {}
    successful_channels = []

    channels = [
        ("pushover", configured["pushover"]["configured"], lambda: _send_pushover(message, title, priority)),
        ("slack", configured["slack"]["configured"], lambda: _send_slack(message, title)),
        ("telegram", configured["telegram"]["configured"], lambda: _send_telegram(message, title)),
        ("discord", configured["discord"]["configured"], lambda: _send_discord(message, title)),
        ("ntfy", configured["ntfy"]["configured"], lambda: _send_ntfy(message, title, priority, context)),
        ("webhook", configured["webhook"]["configured"], lambda: _send_generic_webhook(context)),
    ]

    for channel_name, is_configured, sender in channels:
        if not is_configured:
            channel_results[channel_name] = _error_result(False, skipped="missing env vars")
            continue

        try:
            resp = sender()
            channel_results[channel_name] = _ok_result(True, resp.status_code)
            successful_channels.append(channel_name)
        except Exception as exc:
            logging.error("%s send failed: %s", channel_name.capitalize(), exc)
            channel_results[channel_name] = _error_result(True, error=str(exc))

    return {
        "ok": bool(successful_channels),
        "configured_any": any(info["configured"] for info in configured.values()),
        "successful_channels": successful_channels,
        "channels": channel_results,
    }
