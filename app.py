#!/usr/bin/env python
# -*- coding: utf-8 -*-

print("***********************************")
print("*** Docker Monitor APP STARTING ***")
print("***********************************")

import threading
import time
from flask import Flask
try:
    from waitress import serve
    HAS_WAITRESS = True
except ImportError:  # waitress not installed
    serve = None
    HAS_WAITRESS = False

# Importar configuración, clientes y rutas
from config import APP_HOST, APP_PORT, WAITRESS_THREADS, DOCKER_SOCKET_URL, SAMPLE_INTERVAL, MAX_SECONDS, AUTH_USER, AUTH_PASSWORD
from docker_client import client as docker_client, api_client as docker_api_client # Importar las instancias directamente para comprobar
from sampler import sample_metrics, history # Importar función sampler y el historial
from routes import main_routes # Importar el Blueprint
from users_db import init_db

# Crear la instancia de la aplicación Flask
# Definir static_folder y template_folder explícitamente si no están en el Blueprint
# o si se usan rutas definidas directamente aquí. El Blueprint ya los define.
app = Flask(__name__, static_url_path='/static', static_folder='static')

# Set a secret key for session and CSRF protection
app.secret_key = 'replace_this_with_a_random_secret_key_2025'

# Registrar el Blueprint que contiene las rutas
app.register_blueprint(main_routes)

# --- Función para iniciar el thread de muestreo ---
def start_sampler_thread():
    print("Starting metrics sampling thread...")
    sampler_thread = threading.Thread(target=sample_metrics, daemon=True)
    sampler_thread.start()
    print("Sampling thread started.")

# --- Ejecución Principal ---
if __name__ == '__main__':
    print("-------------------------------------")
    print(" Docker Monitor ")
    print("-------------------------------------")
    print("Starting Flask server...")

    # Initialize the database with environment user and password
    if AUTH_USER and AUTH_PASSWORD:
        init_db(AUTH_USER, AUTH_PASSWORD)

    # Check that Docker clients were initialized correctly in docker_client.py
    if docker_client and docker_api_client:
        print(f"Docker connection established via: {DOCKER_SOCKET_URL}")
    else:
        # This should not happen because docker_client.py exits if it fails
        print("FATAL: Docker client failed to initialize at startup.")
        exit(1)

    print(f"Sampler interval: {SAMPLE_INTERVAL} seconds")
    print(f"History retention: {MAX_SECONDS / 3600} hours")

    # Start the background sampling thread
    start_sampler_thread()

    # Wait a second so the sampler can start before accepting requests
    time.sleep(1)

    print(f"Access the monitor at: http://{APP_HOST}:{APP_PORT} (or your machine's IP:{APP_PORT})")
    print("-------------------------------------")

    if HAS_WAITRESS:
        print(f"Using Waitress server with {WAITRESS_THREADS} threads...")
        serve(app, host=APP_HOST, port=APP_PORT, threads=WAITRESS_THREADS)
    else:
        print("Waitress not found, using Flask development server (WARNING: Not recommended for production).")
        app.run(host=APP_HOST, port=APP_PORT, debug=False)
