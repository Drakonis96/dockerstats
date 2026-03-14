# pushover_client.py
import logging
import os

import requests

PUSHOVER_URL = "https://api.pushover.net/1/messages.json"


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


def send(message, title="Docker-Stats", priority=0):
    """Send a notification to all configured services and return per-channel status."""
    configured = get_configured_services()
    channel_results = {}
    successful_channels = []

    pushover_token = os.getenv("PUSHOVER_TOKEN")
    pushover_user = os.getenv("PUSHOVER_USER")
    if configured["pushover"]["configured"]:
        try:
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
            channel_results["pushover"] = _ok_result(True, resp.status_code)
            successful_channels.append("pushover")
        except Exception as exc:
            logging.error("Pushover send failed: %s", exc)
            channel_results["pushover"] = _error_result(True, error=str(exc))
    else:
        logging.warning("Pushover disabled (missing env vars)")
        channel_results["pushover"] = _error_result(False, skipped="missing env vars")

    slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if configured["slack"]["configured"]:
        try:
            resp = requests.post(
                slack_webhook_url,
                timeout=5,
                json={"text": f"*{title}*\n{message}"},
            )
            resp.raise_for_status()
            channel_results["slack"] = _ok_result(True, resp.status_code)
            successful_channels.append("slack")
        except Exception as exc:
            logging.error("Slack send failed: %s", exc)
            channel_results["slack"] = _error_result(True, error=str(exc))
    else:
        channel_results["slack"] = _error_result(False, skipped="missing env vars")

    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if configured["telegram"]["configured"]:
        try:
            url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
            resp = requests.post(
                url,
                timeout=5,
                data={"chat_id": telegram_chat_id, "text": f"{title}\n{message}"},
            )
            resp.raise_for_status()
            channel_results["telegram"] = _ok_result(True, resp.status_code)
            successful_channels.append("telegram")
        except Exception as exc:
            logging.error("Telegram send failed: %s", exc)
            channel_results["telegram"] = _error_result(True, error=str(exc))
    else:
        channel_results["telegram"] = _error_result(False, skipped="missing env vars")

    discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if configured["discord"]["configured"]:
        try:
            resp = requests.post(
                discord_webhook_url,
                timeout=5,
                json={"content": f"**{title}**\n{message}"},
            )
            resp.raise_for_status()
            channel_results["discord"] = _ok_result(True, resp.status_code)
            successful_channels.append("discord")
        except Exception as exc:
            logging.error("Discord send failed: %s", exc)
            channel_results["discord"] = _error_result(True, error=str(exc))
    else:
        channel_results["discord"] = _error_result(False, skipped="missing env vars")

    return {
        "ok": bool(successful_channels),
        "configured_any": any(info["configured"] for info in configured.values()),
        "successful_channels": successful_channels,
        "channels": channel_results,
    }
