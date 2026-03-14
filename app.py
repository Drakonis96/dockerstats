#!/usr/bin/env python
# -*- coding: utf-8 -*-

print("***********************************")
print("*** Docker Monitor APP STARTING ***")
print("***********************************")

import threading
import time
import warnings

from flask import Flask

try:
    from waitress import serve

    HAS_WAITRESS = True
except ImportError:  # waitress not installed
    serve = None
    HAS_WAITRESS = False

from config import (
    APP_HOST,
    APP_PORT,
    APP_SECRET_KEY,
    APP_SECRET_KEY_EPHEMERAL,
    APP_VERSION,
    AUTH_ENABLED,
    AUTH_PASSWORD,
    AUTH_USER,
    CADVISOR_URL,
    DOCKER_SOCKET_URL,
    LOGIN_MODE,
    MAX_SECONDS,
    SAMPLE_INTERVAL,
    STREAM_HEARTBEAT_SECONDS,
    WAITRESS_THREADS,
)
from docker_client import get_docker_status, initialize_docker_clients
from routes import main_routes
from sampler import sample_metrics
from users_db import count_users, init_db


def create_app(test_config=None):
    """Application factory used by runtime and tests."""
    flask_app = Flask(__name__, static_url_path='/static', static_folder='static')
    flask_app.config.from_mapping(
        SECRET_KEY=APP_SECRET_KEY,
        APP_VERSION=APP_VERSION,
        APP_SECRET_KEY_EPHEMERAL=APP_SECRET_KEY_EPHEMERAL,
        AUTH_ENABLED=AUTH_ENABLED,
        AUTH_USER=AUTH_USER,
        AUTH_PASSWORD=AUTH_PASSWORD,
        CADVISOR_URL=CADVISOR_URL,
        DOCKER_SOCKET_URL=DOCKER_SOCKET_URL,
        LOGIN_MODE=LOGIN_MODE,
        SAMPLE_INTERVAL=SAMPLE_INTERVAL,
        MAX_SECONDS=MAX_SECONDS,
        STREAM_HEARTBEAT_SECONDS=STREAM_HEARTBEAT_SECONDS,
    )
    if test_config:
        flask_app.config.update(test_config)

    flask_app.secret_key = flask_app.config["SECRET_KEY"]
    flask_app.register_blueprint(main_routes)

    @flask_app.context_processor
    def inject_template_globals():
        return {
            "app_version": flask_app.config.get("APP_VERSION", "dev"),
        }

    return flask_app


app = create_app()


def start_sampler_thread():
    print("Starting metrics sampling thread...")
    sampler_thread = threading.Thread(target=sample_metrics, daemon=True)
    sampler_thread.start()
    print("Sampling thread started.")


def initialize_runtime():
    """Prepare auth DB and Docker connectivity without failing the whole app."""
    bootstrap_user = app.config.get("AUTH_USER", "")
    bootstrap_password = app.config.get("AUTH_PASSWORD", "")
    auth_enabled = bool(app.config.get("AUTH_ENABLED", True))

    if bootstrap_user and bootstrap_password:
        init_db(bootstrap_user, bootstrap_password)

    user_count = count_users()
    if auth_enabled and user_count == 0:
        raise RuntimeError(
            "AUTH_ENABLED is true but no users exist. Set AUTH_USER/AUTH_PASSWORD (or *_FILE) for the first startup."
        )

    if app.config.get("APP_SECRET_KEY_EPHEMERAL"):
        warnings.warn(
            "APP_SECRET_KEY is not set. A temporary secret key was generated for this process; sessions will be reset on restart.",
            RuntimeWarning,
        )

    docker_ready = initialize_docker_clients(force=True)
    docker_status = get_docker_status()

    if docker_ready:
        print(f"Docker connection established via: {DOCKER_SOCKET_URL}")
    else:
        print("WARN: Docker client not available at startup. The UI will run in degraded mode.")
        if docker_status.get("error"):
            print(f"      {docker_status['error']}")

    print(f"Sampler interval: {SAMPLE_INTERVAL} seconds")
    print(f"History retention: {MAX_SECONDS / 3600} hours")
    print(f"App version: {app.config.get('APP_VERSION')}")
    return docker_ready


if __name__ == '__main__':
    print("-------------------------------------")
    print(" Docker Monitor ")
    print("-------------------------------------")
    print("Starting Flask server...")

    docker_ready = initialize_runtime()
    start_sampler_thread()

    if docker_ready:
        time.sleep(1)

    print(f"Access the monitor at: http://{APP_HOST}:{APP_PORT} (or your machine's IP:{APP_PORT})")
    print("-------------------------------------")

    if HAS_WAITRESS:
        print(f"Using Waitress server with {WAITRESS_THREADS} threads...")
        serve(app, host=APP_HOST, port=APP_PORT, threads=WAITRESS_THREADS)
    else:
        print("Waitress not found, using Flask development server (WARNING: Not recommended for production).")
        app.run(host=APP_HOST, port=APP_PORT, debug=False)
