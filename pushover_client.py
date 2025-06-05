# pushover_client.py
import os, requests, logging

# Optional integrations
SLACK_WEBHOOK_URL   = os.getenv("SLACK_WEBHOOK_URL")
TELEGRAM_BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

PUSHOVER_TOKEN = os.getenv("PUSHOVER_TOKEN")
PUSHOVER_USER  = os.getenv("PUSHOVER_USER")
PUSHOVER_URL   = "https://api.pushover.net/1/messages.json"

def send(message, title="Docker‑Stats", priority=0):
    """Send a notification to all configured services."""
    # Pushover
    if PUSHOVER_TOKEN and PUSHOVER_USER:
        try:
            resp = requests.post(PUSHOVER_URL, timeout=5, data={
                "token":    PUSHOVER_TOKEN,
                "user":     PUSHOVER_USER,
                "title":    title,
                "message":  message,
                "priority": priority,
            })
            resp.raise_for_status()
        except Exception as e:
            logging.error(f"Pushover send failed: {e}")
    else:
        logging.warning("Pushover disabled (missing env vars)")

    # Slack
    if SLACK_WEBHOOK_URL:
        try:
            resp = requests.post(
                SLACK_WEBHOOK_URL,
                timeout=5,
                json={"text": f"*{title}*\n{message}"},
            )
            resp.raise_for_status()
        except Exception as e:
            logging.error(f"Slack send failed: {e}")

    # Telegram
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            resp = requests.post(
                url,
                timeout=5,
                data={"chat_id": TELEGRAM_CHAT_ID, "text": f"{title}\n{message}"},
            )
            resp.raise_for_status()
        except Exception as e:
            logging.error(f"Telegram send failed: {e}")

    # Discord
    if DISCORD_WEBHOOK_URL:
        try:
            resp = requests.post(
                DISCORD_WEBHOOK_URL,
                timeout=5,
                json={"content": f"**{title}**\n{message}"},
            )
            resp.raise_for_status()
        except Exception as e:
            logging.error(f"Discord send failed: {e}")
