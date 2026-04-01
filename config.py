# -*- coding: utf-8 -*-
import os
import secrets


def _get_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name, default):
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def _read_secret(env_name, file_env_name=None, default=""):
    file_path = os.environ.get(file_env_name or f"{env_name}_FILE", "").strip()
    if file_path:
        with open(file_path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    return os.environ.get(env_name, default).strip()


APP_VERSION = os.environ.get("APP_VERSION", "v0.9.2").strip() or "v0.9.2"
APP_HOST = os.environ.get("APP_HOST", "0.0.0.0")
APP_PORT = _get_int("APP_PORT", 5000)
WAITRESS_THREADS = _get_int("WAITRESS_THREADS", 8)

DOCKER_SOCKET_URL = os.environ.get("DOCKER_SOCKET_URL", "unix:///var/run/docker.sock")
CADVISOR_URL = os.environ.get("CADVISOR_URL", "http://cadvisor:8080")
SAMPLE_INTERVAL = _get_int("SAMPLE_INTERVAL", 5)
MAX_SECONDS = _get_int("MAX_SECONDS", 86400)
STREAM_HEARTBEAT_SECONDS = _get_int("STREAM_HEARTBEAT_SECONDS", 15)

AUTH_ENABLED = _get_bool("AUTH_ENABLED", True)
LOGIN_MODE = os.environ.get("LOGIN_MODE", "popup").strip().lower() or "popup"
AUTH_USER = os.environ.get("AUTH_USER", "").strip()
AUTH_PASSWORD = _read_secret("AUTH_PASSWORD", "AUTH_PASSWORD_FILE", default="")

APP_SECRET_KEY = _read_secret("APP_SECRET_KEY", "APP_SECRET_KEY_FILE", default="")
APP_SECRET_KEY_EPHEMERAL = False
if not APP_SECRET_KEY:
    APP_SECRET_KEY = secrets.token_urlsafe(32)
    APP_SECRET_KEY_EPHEMERAL = True
