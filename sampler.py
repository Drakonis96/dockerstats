# -*- coding: utf-8 -*-

import threading
import time
import collections
import docker.errors
import logging
from docker_client import get_docker_client, get_api_client
from config import SAMPLE_INTERVAL, MAX_SECONDS
from metrics_utils import (
    calc_cpu_percent,
    calc_mem_percent_usage,
    calc_net_io,
    calc_block_io
)

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

def check_image_update(container):
    """
    Devuelve True si hay una nueva imagen en el registry,
    False si la que corre es la última, None si no se pudo comprobar.
    """
    try:
        image_ref = container.attrs['Config']['Image']           # p. ej. 'nginx:latest'
        if '@' in image_ref:                                     # imagen fijada por digest → no tiene sentido comprobar
            return None

        local_img = client.images.get(image_ref)
        # Busca el digest de la misma repo en RepoDigests
        repo = image_ref.split(':')[0]                           # 'nginx'
        local_manifest_digest = next(
            d.split('@')[1] for d in local_img.attrs['RepoDigests']
            if d.startswith(f'{repo}@')
        )

        remote_manifest_digest = client.images.get_registry_data(image_ref).id
        return local_manifest_digest != remote_manifest_digest

    except (docker.errors.ImageNotFound, StopIteration):
        return None                                              # No se pudo comparar
    except docker.errors.APIError:
        return None
    except Exception:
        return None

def sample_metrics():
    """Thread en segundo plano para muestrear periódicamente métricas y comprobar actualizaciones."""
    global history, previous_stats

    time.sleep(1)
    initialize_sampler_clients()

    while True:
        containers_to_sample = []
        current_running_ids = set()
        try:
            if not client or not api_client:
                logging.error("Clientes Docker no inicializados en sample_metrics. Esperando...")
                time.sleep(SAMPLE_INTERVAL * 2)
                initialize_sampler_clients()
                continue

            running_containers = client.containers.list(all=False, filters={'status': 'running'})
            containers_to_sample = [(c.id, c.name) for c in running_containers]
            current_running_ids = {c.id for c in running_containers}

        except docker.errors.DockerException as e:
            logging.error(f"ERROR listando contenedores corriendo en sampler: {e}")
            time.sleep(SAMPLE_INTERVAL * 2)
            continue
        except Exception as e:
            logging.error(f"Error inesperado listando contenedores en sampler: {e}")
            time.sleep(SAMPLE_INTERVAL * 2)
            continue

        processed_cids = set()
        for cid, container_name in containers_to_sample:
            processed_cids.add(cid)
            cpu = 0.0
            mem_percent = 0.0
            status = "running"
            update_available = None

            try:
                container = client.containers.get(cid)
                update_available = check_image_update(container)

                current_stats_raw = api_client.stats(container=cid, stream=False, one_shot=True)
                if not isinstance(current_stats_raw, dict):
                    continue

                last_stats_raw = previous_stats.get(cid)

                if last_stats_raw and isinstance(last_stats_raw, dict):
                    cpu = calc_cpu_percent(current_stats_raw, last_stats_raw)

                mem_percent, mem_usage_mib = calc_mem_percent_usage(current_stats_raw)
                previous_stats[cid] = current_stats_raw

                net_rx, net_tx = calc_net_io(current_stats_raw)
                blk_r, blk_w = calc_block_io(current_stats_raw)

                status = "running"

                dq = history.setdefault(cid, collections.deque(maxlen=MAX_SECONDS // SAMPLE_INTERVAL))
                dq.append((time.time(), cpu, mem_percent, status, container_name, net_rx, net_tx, blk_r, blk_w, update_available))

            except docker.errors.NotFound:
                if cid in history: del history[cid]
                if cid in previous_stats: del previous_stats[cid]
                continue

            except Exception as e:
                logging.error(f"ERROR muestreando métricas para contenedor {cid[:12]} (Nombre: {container_name}): {e}")
                dq = history.setdefault(cid, collections.deque(maxlen=MAX_SECONDS // SAMPLE_INTERVAL))
                dq.append((time.time(), 0.0, 0.0, "error-sample", container_name, 0, 0, 0, 0, None))

        removed_ids_prev = set(previous_stats.keys()) - current_running_ids
        for cid_removed in removed_ids_prev:
            if cid_removed in previous_stats: del previous_stats[cid_removed]

        try:
            all_containers_ids = {c.id for c in client.containers.list(all=True)}
            history_ids_to_remove = set(history.keys()) - all_containers_ids
            for cid_hist_removed in history_ids_to_remove:
                last_known_name = "Desconocido"
                try:
                    if cid_hist_removed in history and history[cid_hist_removed]:
                        last_known_name = history[cid_hist_removed][-1][4]
                except (IndexError, TypeError): pass
                if cid_hist_removed in history: del history[cid_hist_removed]
                if cid_hist_removed in previous_stats:
                    del previous_stats[cid_hist_removed]

        except docker.errors.DockerException as e:
            logging.warning(f"Error Docker durante limpieza de historial: {e}")
        except Exception as e:
            logging.warning(f"Error genérico durante limpieza de historial: {e}")

        time.sleep(SAMPLE_INTERVAL)