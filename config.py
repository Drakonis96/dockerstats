# -*- coding: utf-8 -*-
import os

# --- Configuración ---
DOCKER_SOCKET_URL = 'unix:///var/run/docker.sock' # Ruta estándar en Linux/macOS
SAMPLE_INTERVAL = 5      # segundos
MAX_SECONDS     = 86400  # Mantener hasta 24h de historial (86400 segundos)
APP_HOST = '0.0.0.0'
APP_PORT = 5000
WAITRESS_THREADS = 8

# Authentication credentials (set via environment variables)
AUTH_USER = os.environ.get('AUTH_USER', '')
AUTH_PASSWORD = os.environ.get('AUTH_PASSWORD', '')
AUTH_PASSWORD_FILE = os.environ.get('AUTH_PASSWORD_FILE', '')

if AUTH_PASSWORD_FILE:
    try:
        with open(AUTH_PASSWORD_FILE, 'r') as f:
            AUTH_PASSWORD = f.read().strip()
    except FileNotFoundError:
        print(f"Warning: AUTH_PASSWORD_FILE specified but not found at {AUTH_PASSWORD_FILE}")
        AUTH_PASSWORD = '' # Or handle error as appropriate

# Puedes añadir más configuraciones aquí si es necesario