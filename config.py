# -*- coding: utf-8 -*-
import os

# --- Configuración ---
DOCKER_SOCKET_URL = os.environ.get('DOCKER_SOCKET_URL', 'unix:///var/run/docker.sock') # Permite override por variable de entorno, usa el socket estándar si no se define
SAMPLE_INTERVAL = 5      # segundos
MAX_SECONDS     = 86400  # Mantener hasta 24h de historial (86400 segundos)
APP_HOST = '0.0.0.0'
APP_PORT = 5000
WAITRESS_THREADS = 8

# Authentication credentials (set via environment variables)
AUTH_USER = os.environ.get('AUTH_USER', 'admin')
AUTH_PASSWORD = os.environ.get('AUTH_PASSWORD', 'admin')
AUTH_PASSWORD_FILE = os.environ.get('AUTH_PASSWORD_FILE', '')

# Login mode: 'popup' (default) or 'page'
LOGIN_MODE = os.environ.get('LOGIN_MODE', 'popup')

if AUTH_PASSWORD_FILE:
    try:
        with open(AUTH_PASSWORD_FILE, 'r') as f:
            AUTH_PASSWORD = f.read().strip()
    except FileNotFoundError:
        print(f"Warning: AUTH_PASSWORD_FILE specified but not found at {AUTH_PASSWORD_FILE}")
        AUTH_PASSWORD = '' # Or handle error as appropriate

# Puedes añadir más configuraciones aquí si es necesario