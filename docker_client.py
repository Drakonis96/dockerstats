# -*- coding: utf-8 -*-

import docker
import requests_unixsocket
import sys
from config import DOCKER_SOCKET_URL

# Patch requests for http+docker:// support (or unix:// handling)
# It's good to keep it just in case requests is used internally over the socket.
requests_unixsocket.monkeypatch()

# --- Docker Client Initialization ---
client = None
api_client = None

try:
    print(f"Attempting to connect to Docker daemon via {DOCKER_SOCKET_URL}...")
    # Explicitly use the standard Unix socket path for both clients
    # Set a reasonable timeout (e.g. 10 seconds)
    client = docker.DockerClient(base_url=DOCKER_SOCKET_URL, timeout=10)
    api_client = docker.APIClient(base_url=DOCKER_SOCKET_URL, timeout=10)

    # Test connection
    client.ping()
    print(f"Docker client successfully connected via {DOCKER_SOCKET_URL}.")

except docker.errors.DockerException as e:
    print(f"ERROR: Failed to connect to Docker daemon at {DOCKER_SOCKET_URL}.")
    print(f"       Please make sure the Docker daemon is running and the socket is accessible.")
    print(f"       (On Linux/macOS, check that '{DOCKER_SOCKET_URL}' exists and has the correct permissions).")
    print(f"       Error details: {e}")
    sys.exit(1) # Exit if connection fails
except Exception as e:
    print(f"ERROR: An unexpected error occurred while connecting to Docker: {e}")
    sys.exit(1) # Exit if connection fails

def get_docker_client():
    """Returns the Docker client instance."""
    if not client:
        raise RuntimeError("Docker client is not initialized.")
    return client

def get_api_client():
    """Returns the Docker API client instance."""
    if not api_client:
        raise RuntimeError("Docker API client is not initialized.")
    return api_client

# --- End Docker Client Initialization ---