# pushover_client.py
import os, requests, logging

PUSHOVER_TOKEN = os.getenv("PUSHOVER_TOKEN")
PUSHOVER_USER  = os.getenv("PUSHOVER_USER")
PUSHOVER_URL   = "https://api.pushover.net/1/messages.json"

def send(message, title="Docker‑Stats", priority=0):
    if not (PUSHOVER_TOKEN and PUSHOVER_USER):
        logging.warning("Pushover disabled (missing env vars)")
        return
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
