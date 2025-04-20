#!/usr/bin/env python
# -*- coding: utf-8 -*-

print("***********************************")
print("*** Docker Monitor APP STARTING ***")
print("***********************************")

import threading
import time
from flask import Flask
from waitress import serve

# Importar configuración, clientes y rutas
from config import APP_HOST, APP_PORT, WAITRESS_THREADS, DOCKER_SOCKET_URL, SAMPLE_INTERVAL, MAX_SECONDS
from docker_client import client as docker_client, api_client as docker_api_client # Importar las instancias directamente para comprobar
from sampler import sample_metrics, history # Importar función sampler y el historial
from routes import main_routes # Importar el Blueprint

# Crear la instancia de la aplicación Flask
# Definir static_folder y template_folder explícitamente si no están en el Blueprint
# o si se usan rutas definidas directamente aquí. El Blueprint ya los define.
app = Flask(__name__, static_url_path='/static', static_folder='static')

# Registrar el Blueprint que contiene las rutas
app.register_blueprint(main_routes)

# --- Función para iniciar el thread de muestreo ---
def start_sampler_thread():
    print("Iniciando el thread de muestreo de métricas...")
    sampler_thread = threading.Thread(target=sample_metrics, daemon=True)
    sampler_thread.start()
    print("Thread de muestreo iniciado.")

# --- Ejecución Principal ---
if __name__ == '__main__':
    print("-------------------------------------")
    print(" Docker Monitor ")
    print("-------------------------------------")
    print("Iniciando servidor Flask...")

    # Verificar que los clientes Docker se inicializaron correctamente en docker_client.py
    if docker_client and docker_api_client:
        print(f"Conexión Docker establecida vía: {DOCKER_SOCKET_URL}")
    else:
        # Esto no debería ocurrir porque docker_client.py sale si falla
        print("FATAL: Cliente Docker falló al inicializar al inicio.")
        exit(1)

    print(f"Intervalo del Sampler: {SAMPLE_INTERVAL} segundos")
    print(f"Retención de Historial: {MAX_SECONDS / 3600} horas")

    # Iniciar el thread de muestreo en segundo plano
    start_sampler_thread()

    # Esperar un segundo para que el sampler pueda iniciarse antes de aceptar peticiones
    time.sleep(1)

    print(f"Accede al monitor en: http://{APP_HOST}:{APP_PORT} (o la IP de tu máquina:{APP_PORT})")
    print("-------------------------------------")

    try:
        print(f"Usando servidor Waitress con {WAITRESS_THREADS} threads...")
        serve(app, host=APP_HOST, port=APP_PORT, threads=WAITRESS_THREADS)
    except ImportError:
        print("Waitress no encontrado, usando servidor de desarrollo de Flask (ADVERTENCIA: No recomendado para producción).")
        # debug=False es importante para producción y para evitar que el reloader interfiera con el thread
        app.run(host=APP_HOST, port=APP_PORT, debug=False)