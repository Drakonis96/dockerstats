# -*- coding: utf-8 -*-

import threading
import time
import collections
import docker.errors
from docker_client import get_docker_client, get_api_client
from config import SAMPLE_INTERVAL, MAX_SECONDS
from metrics_utils import (
    calc_cpu_percent,
    calc_mem_percent_usage,
    calc_net_io,
    calc_block_io
)

# Buffer de historial en memoria (almacena métricas calculadas)
history = {}
# Almacena estadísticas crudas previas para cálculo delta de CPU
previous_stats = {}

# Asegura que los clientes se obtienen después de la inicialización
client = None
api_client = None

def initialize_sampler_clients():
    """Obtiene las instancias del cliente para el sampler."""
    global client, api_client
    client = get_docker_client()
    api_client = get_api_client()

def sample_metrics():
    """Thread en segundo plano para muestrear periódicamente métricas de contenedores."""
    global history, previous_stats # Asegurar que modificamos globales

    # Esperar un poco al inicio para que los clientes estén listos si se llama muy rápido
    time.sleep(1)
    initialize_sampler_clients() # Obtener los clientes inicializados

    while True:
        containers_to_sample = []
        current_running_ids = set()
        try:
            # Asegurar que los clientes Docker están inicializados antes de proceder
            if not client or not api_client:
                print("ERROR: Clientes Docker no inicializados en sample_metrics. Esperando...")
                time.sleep(SAMPLE_INTERVAL * 2)
                initialize_sampler_clients() # Intentar reinicializar
                continue

            running_containers = client.containers.list(all=False, filters={'status': 'running'})
            containers_to_sample = [(c.id, c.name) for c in running_containers] # Obtener ID y Nombre juntos
            current_running_ids = {c.id for c in running_containers}
            # ### DEBUG: Comprobar si se encuentran contenedores
            # if not containers_to_sample:
            #      print("### DEBUG [Sampler]: No se encontraron contenedores corriendo en este ciclo.")

        except docker.errors.DockerException as e:
            print(f"ERROR listando contenedores corriendo en sampler: {e}")
            time.sleep(SAMPLE_INTERVAL * 2) # Esperar más si falla el listado
            continue
        except Exception as e:
             print(f"Error inesperado listando contenedores en sampler: {e}")
             time.sleep(SAMPLE_INTERVAL * 2)
             continue

        processed_cids = set()
        for cid, container_name in containers_to_sample:
            processed_cids.add(cid) # Marcar como procesado en este ciclo
            cpu = 0.0 # Valor CPU por defecto
            mem_percent = 0.0 # Valor Mem por defecto
            status = "running" # Asumir corriendo ya que filtramos por ello

            try:
                # Obtener snapshot de estadísticas actuales
                # one_shot=True es más eficiente que dejar el stream abierto
                current_stats_raw = api_client.stats(container=cid, stream=False, one_shot=True)
                if not isinstance(current_stats_raw, dict): # Validación básica
                     # print(f"Warning: Recibidas estadísticas no-dict para {container_name}. Saltando.")
                     continue

                # Comprobar si tenemos estadísticas previas para este contenedor
                last_stats_raw = previous_stats.get(cid)

                # --- Calcular CPU ---
                if last_stats_raw and isinstance(last_stats_raw, dict):
                    cpu = calc_cpu_percent(current_stats_raw, last_stats_raw)

                # --- Calcular Memoria (solo necesita estadísticas actuales) ---
                mem_percent, mem_usage_mib = calc_mem_percent_usage(current_stats_raw)

                # --- Actualizar caché previous_stats con la lectura actual ---
                previous_stats[cid] = current_stats_raw

                # --- Obtener otras métricas (Net/Block IO) de estadísticas actuales ---
                net_rx, net_tx = calc_net_io(current_stats_raw)
                blk_r, blk_w = calc_block_io(current_stats_raw)

                # --- Obtener estado actual (comprobación rápida, menos crítico si falla) ---
                # Nota: Ya filtramos por 'running', así que obtener el estado de nuevo es redundante
                # a menos que queramos detectar cambios rápidos. Lo omitimos por rendimiento.
                status = "running" # Mantenemos el estado asumido

                # Asegurar que existe deque para el ID del contenedor en history
                dq = history.setdefault(cid, collections.deque(maxlen=MAX_SECONDS // SAMPLE_INTERVAL))
                # Almacenar las métricas *calculadas* en history
                # Orden: time, cpu%, mem%, status, name, net_rx, net_tx, blk_r, blk_w
                dq.append((time.time(), cpu, mem_percent, status, container_name, net_rx, net_tx, blk_r, blk_w))
                # ### DEBUG: Confirmar datos añadidos
                # print(f"### DEBUG [Sampler]: Añadidos datos para {container_name[:20]} (CPU: {cpu:.1f}%, Mem: {mem_percent:.1f}%, Status: {status})")

            except docker.errors.NotFound:
                 # Contenedor parado entre list() y stats()
                 # print(f"Warning: Contenedor {cid[:12]} (Nombre: {container_name}) no encontrado durante llamada api_client.stats (parado).")
                 if cid in history: del history[cid] # Limpiar historial
                 if cid in previous_stats: del previous_stats[cid] # Limpiar caché de stats previas
                 continue # Saltar procesamiento de este contenedor

            except Exception as e:
                # Registrar otros errores durante obtención o cálculo de stats
                print(f"ERROR muestreando métricas para contenedor {cid[:12]} (Nombre: {container_name}): {e}")
                # Registrar un estado de error en el historial
                dq = history.setdefault(cid, collections.deque(maxlen=MAX_SECONDS // SAMPLE_INTERVAL))
                dq.append((time.time(), 0.0, 0.0, "error-sample", container_name, 0, 0, 0, 0))


        # --- Limpiar cachés para contenedores que ya no están corriendo ---
        # Limpiar caché previous_stats
        removed_ids_prev = set(previous_stats.keys()) - current_running_ids
        for cid_removed in removed_ids_prev:
            # print(f"Info: Eliminando caché de stats previas para contenedor parado {cid_removed[:12]}")
            if cid_removed in previous_stats: del previous_stats[cid_removed]

        # Limpiar caché de historial (para contenedores completamente eliminados)
        try:
            # Usar client aquí es seguro porque está inicializado o el bucle habría continuado
            all_containers_ids = {c.id for c in client.containers.list(all=True)}
            history_ids_to_remove = set(history.keys()) - all_containers_ids
            for cid_hist_removed in history_ids_to_remove:
                last_known_name = "Desconocido"
                # Acceso seguro al item de historial y datos de muestra
                try:
                    if cid_hist_removed in history and history[cid_hist_removed]:
                        last_known_name = history[cid_hist_removed][-1][4] # Índice 4 es nombre
                except (IndexError, TypeError): pass
                # print(f"Info: Eliminando historial para contenedor eliminado {cid_hist_removed[:12]} (Último nombre conocido: {last_known_name})")
                if cid_hist_removed in history: del history[cid_hist_removed]
                # También asegurar que se elimina de previous_stats si se omitió antes
                if cid_hist_removed in previous_stats:
                     del previous_stats[cid_hist_removed]

        except docker.errors.DockerException as e:
             print(f"Warning: Error Docker durante limpieza de historial: {e}")
        except Exception as e:
            print(f"Warning: Error genérico durante limpieza de historial: {e}")

        # Esperar para el siguiente intervalo de muestreo
        time.sleep(SAMPLE_INTERVAL)