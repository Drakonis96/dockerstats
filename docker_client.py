# -*- coding: utf-8 -*-

import docker
import requests_unixsocket
import sys
from config import DOCKER_SOCKET_URL

# Parchear requests para soporte http+docker:// (o manejo de unix://)
# Es bueno mantenerlo por si acaso requests se usa internamente sobre el socket.
requests_unixsocket.monkeypatch()

# --- Inicialización del Cliente Docker ---
client = None
api_client = None

try:
    print(f"Intentando conectar al daemon Docker vía {DOCKER_SOCKET_URL}...")
    # Usar explícitamente la ruta del socket Unix estándar para ambos clientes
    # Establecer un timeout razonable (ej. 10 segundos)
    client = docker.DockerClient(base_url=DOCKER_SOCKET_URL, timeout=10)
    api_client = docker.APIClient(base_url=DOCKER_SOCKET_URL, timeout=10)

    # Probar conexión
    client.ping()
    print(f"Cliente Docker conectado exitosamente vía {DOCKER_SOCKET_URL}.")

except docker.errors.DockerException as e:
    print(f"ERROR: Fallo al conectar al daemon Docker en {DOCKER_SOCKET_URL}.")
    print(f"       Por favor, asegúrate que el daemon Docker está corriendo y el socket es accesible.")
    print(f"       (En Linux/macOS, revisa que '{DOCKER_SOCKET_URL}' existe y tiene los permisos correctos).")
    print(f"       Detalles del error: {e}")
    sys.exit(1) # Salir si la conexión falla
except Exception as e:
    print(f"ERROR: Ocurrió un error inesperado al conectar con Docker: {e}")
    sys.exit(1) # Salir si la conexión falla

def get_docker_client():
    """Retorna la instancia del cliente Docker."""
    if not client:
        raise RuntimeError("El cliente Docker no está inicializado.")
    return client

def get_api_client():
    """Retorna la instancia del cliente API de Docker."""
    if not api_client:
        raise RuntimeError("El cliente API de Docker no está inicializado.")
    return api_client

# --- Fin Inicialización Cliente Docker ---