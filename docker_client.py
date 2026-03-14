# -*- coding: utf-8 -*-

import logging

import docker
import requests_unixsocket

from config import DOCKER_SOCKET_URL

# Patch requests for http+docker:// support (or unix:// handling)
requests_unixsocket.monkeypatch()

client = None
api_client = None
init_error = None
init_attempted = False


def initialize_docker_clients(force=False):
    """Initialize Docker clients lazily so the app can start in degraded mode."""
    global client, api_client, init_error, init_attempted

    if init_attempted and not force and client and api_client:
        return True

    init_attempted = True

    try:
        logging.info("Attempting to connect to Docker daemon via %s", DOCKER_SOCKET_URL)
        client = docker.DockerClient(base_url=DOCKER_SOCKET_URL, timeout=10)
        api_client = docker.APIClient(base_url=DOCKER_SOCKET_URL, timeout=10)
        client.ping()
        init_error = None
        logging.info("Docker client successfully connected via %s", DOCKER_SOCKET_URL)
        return True
    except docker.errors.DockerException as exc:
        client = None
        api_client = None
        init_error = (
            f"Failed to connect to Docker daemon at {DOCKER_SOCKET_URL}: {exc}. "
            "Make sure the daemon is running and the socket is accessible."
        )
        logging.error(init_error)
        return False
    except Exception as exc:
        client = None
        api_client = None
        init_error = f"Unexpected Docker initialization error at {DOCKER_SOCKET_URL}: {exc}"
        logging.error(init_error)
        return False


def get_docker_status():
    """Return the current Docker connectivity status for diagnostics."""
    if not init_attempted:
        initialize_docker_clients()

    return {
        "connected": bool(client and api_client),
        "base_url": DOCKER_SOCKET_URL,
        "error": init_error,
    }


def get_docker_client():
    """Return the Docker client instance, retrying initialization if needed."""
    if not client:
        initialize_docker_clients(force=True)
    if not client:
        raise RuntimeError(init_error or "Docker client is not initialized.")
    return client


def get_api_client():
    """Return the low-level Docker API client instance, retrying if needed."""
    if not api_client:
        initialize_docker_clients(force=True)
    if not api_client:
        raise RuntimeError(init_error or "Docker API client is not initialized.")
    return api_client
