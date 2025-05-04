# -*- coding: utf-8 -*-

import threading
import time
import collections
import docker.errors
import logging
import subprocess, json, os
try:
    import pynvml
    pynvml.nvmlInit()
    _NVML_OK = True
except Exception:
    _NVML_OK = False

from docker_client import get_docker_client, get_api_client
from config import SAMPLE_INTERVAL, MAX_SECONDS
from metrics_utils import (
    calc_cpu_percent,
    calc_mem_percent_usage,
    calc_net_io,
    calc_block_io
)
from pushover_client import send as push_notify

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Buffer de historial en memoria (almacena métricas calculadas)
history = {}
# Almacena estadísticas crudas previas para cálculo delta de CPU
previous_stats = {}
# Registro de estados anterior para todos los contenedores
previous_states = {}

# --- NUEVO: Control de cacheo de update_available ---
# Diccionario para cachear el resultado de check_image_update por contenedor
update_check_cache = {}
# Timestamp del último chequeo por contenedor
update_check_time = {}
# Intervalo mínimo entre chequeos automáticos (segundos)
UPDATE_CHECK_MIN_INTERVAL = 24 * 3600  # 24 horas
# Flag global para forzar chequeo inmediato en todos los contenedores
force_update_check_all = False
# Set de IDs de contenedores a forzar chequeo inmediato (tras pull manual)
force_update_check_ids = set()

# --- Notification System ---
notifications = collections.deque(maxlen=500)  # Store recent notification events
notification_settings = {
    'cpu_enabled': True,
    'ram_enabled': True,
    'status_enabled': True,
    'update_enabled': True,
    'cpu_threshold': 80.0,
    'ram_threshold': 80.0,
    'window_seconds': 10,  # How long the threshold must be exceeded
}
# Track when each container last exceeded threshold
cpu_exceed_start = {}
ram_exceed_start = {}

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
    Comprueba si hay una actualización disponible para la imagen del contenedor.
    Retorna: True si hay actualización, False si no, None si no se pudo comprobar.
    Busca el digest real de la imagen local tal como está referenciada en el registro (por ejemplo, "nginx@sha256:...").
    Así, evita problemas si hay varias imágenes locales con el mismo id pero diferentes referencias.
    """
    try:
        image_ref = container.attrs['Config']['Image']  # p. ej. 'nginx:latest' o 'nginx@sha256:...'
        # Si la imagen ya está fijada por digest, no tiene sentido buscar updates
        if '@sha256:' in image_ref:
            logging.info(f"[UpdateCheck] Imagen fijada por digest ({image_ref}), no se comprueba update.")
            return None

        local_img = client.images.get(image_ref)
        repo_digests = local_img.attrs.get('RepoDigests', [])
        # Busca el digest real de la imagen local tal como está referenciada en el registro
        # Ejemplo: si image_ref es 'nginx:latest', busca 'nginx@sha256:...'
        repo = image_ref.split(':')[0] if ':' in image_ref else image_ref
        local_digest_ref = None
        for d in repo_digests:
            if d.startswith(f'{repo}@'):
                local_digest_ref = d
                break
        if not local_digest_ref:
            logging.warning(f"[UpdateCheck] No se encontró RepoDigest para {image_ref} en {repo_digests}")
            return None
        local_manifest_digest = local_digest_ref.split('@')[1]
        # Obtiene el digest remoto del registro
        remote_manifest_digest = client.images.get_registry_data(image_ref).id
        logging.info(f"[UpdateCheck] {image_ref} local_digest={local_manifest_digest} remote_digest={remote_manifest_digest}")
        return local_manifest_digest != remote_manifest_digest

    except (docker.errors.ImageNotFound, StopIteration):
        logging.warning(f"[UpdateCheck] No se pudo comparar update para {container.name} ({image_ref}) - imagen no encontrada o sin digest.")
        return None
    except docker.errors.APIError as e:
        logging.warning(f"[UpdateCheck] APIError comprobando update para {container.name}: {e}")
        return None
    except Exception as e:
        logging.warning(f"[UpdateCheck] Error inesperado comprobando update para {container.name}: {e}")
        return None

def get_gpu_usage():
    """
    Devuelve una lista de dicts [{'index':0,'gpu_util':34,'mem_used':1024,'mem_total':8192}, …]
    Requiere que el contenedor se ejecute con `--gpus all` y tenga drivers.
    """
    if _NVML_OK:
        gpus = []
        for i in range(pynvml.nvmlDeviceGetCount()):
            h = pynvml.nvmlDeviceGetHandleByIndex(i)
            util = pynvml.nvmlDeviceGetUtilizationRates(h)
            mem  = pynvml.nvmlDeviceGetMemoryInfo(h)
            gpus.append({
                'index'    : i,
                'gpu_util' : util.gpu,
                'mem_used' : mem.used//1048576,
                'mem_total': mem.total//1048576
            })
        return gpus
    # fallback: shell out
    out = subprocess.check_output([
        'nvidia-smi',
        '--query-gpu=index,utilization.gpu,memory.used,memory.total',
        '--format=csv,noheader,nounits'
    ], text=True)
    gpus=[]
    for line in out.strip().splitlines():
        idx, util, used, total = map(int, line.split(','))
        gpus.append({'index':idx,'gpu_util':util,'mem_used':used,'mem_total':total})
    return gpus

def sample_metrics():
    """Thread en segundo plano para muestrear periódicamente métricas y comprobar actualizaciones."""
    global history, previous_stats, update_check_cache, update_check_time, force_update_check_all, force_update_check_ids

    time.sleep(1)
    initialize_sampler_clients()

    while True:
        containers_to_sample = []
        current_running_ids = set()
        all_container_ids = set()
        try:
            if not client or not api_client:
                logging.error("Clientes Docker no inicializados en sample_metrics. Esperando...")
                time.sleep(SAMPLE_INTERVAL * 2)
                initialize_sampler_clients()
                continue

            # Get running containers for active metrics sampling
            running_containers = client.containers.list(all=False, filters={'status': 'running'})
            containers_to_sample = [(c.id, c.name) for c in running_containers]
            current_running_ids = {c.id for c in running_containers}
            
            # Get ALL containers (including stopped, exited, etc.) for display
            all_containers = client.containers.list(all=True)
            all_container_ids = {c.id for c in all_containers}
            
            # Add non-running containers to history with appropriate status
            for container in all_containers:
                if container.id not in current_running_ids:
                    # This is a non-running container, add it to history with its status
                    cid = container.id
                    container_name = container.name
                    current_status = container.status
                    dq = history.setdefault(cid, collections.deque(maxlen=MAX_SECONDS // SAMPLE_INTERVAL))
                    
                    # Comprobar si ha cambiado el estado
                    previous_status = None
                    status_changed = False
                    
                    if dq and len(dq) > 0:
                        try:
                            previous_status = dq[-1][3]  # Status is at index 3
                            if previous_status != current_status:
                                status_changed = True
                        except (IndexError, TypeError):
                            pass
                    
                    # Si hay cambio de estado o no hay entrada en el historial, añadir nueva muestra
                    if not dq or status_changed:
                        # Add a minimal stats entry for non-running containers
                        # time, cpu, mem, status, name, net_rx, net_tx, blk_r, blk_w, update_available, pid_count, mem_limit_mb, gpu_stats, gpu_max
                        dq.append((
                            time.time(),  # timestamp
                            0.0,          # cpu
                            0.0,          # memory percentage
                            current_status,  # status (exited, created, paused, etc.)
                            container_name,  # container name
                            0,            # net rx
                            0,            # net tx
                            0,            # block read
                            0,            # block write
                            None,         # update available
                            0,            # pid count
                            None,         # memory limit
                            None,         # gpu stats
                            None          # gpu max
                        ))
                        
                        # Enviar notificación de cambio de estado si estaba en ejecución antes
                        if status_changed and previous_status and notification_settings.get('status_enabled', True):
                            # Solo notificar cambios significativos, especialmente de running a otro estado
                            if previous_status == "running" or current_status == "running":
                                now = time.time()
                                n = {
                                    'type': 'status',
                                    'cid': cid,
                                    'container': container_name,
                                    'value': current_status,
                                    'prev_value': previous_status,
                                    'timestamp': now,
                                    'msg': f"{container_name}: Status changed from {previous_status} to {current_status}"
                                }
                                notifications.append(n)
                                push_notify(n['msg'])

        except docker.errors.DockerException as e:
            logging.error(f"ERROR listando contenedores en sampler: {e}")
            time.sleep(SAMPLE_INTERVAL * 2)
            continue
        except Exception as e:
            logging.error(f"Error inesperado listando contenedores en sampler: {e}")
            time.sleep(SAMPLE_INTERVAL * 2)
            continue

        processed_cids = set()
        now = time.time()
        for cid, container_name in containers_to_sample:
            processed_cids.add(cid)
            cpu = 0.0
            mem_percent = 0.0
            status = "running"
            update_available = None
            gpu_stats = None
            gpu_max = None

            try:
                container = client.containers.get(cid)
                # --- NUEVO: Lógica de chequeo de actualización con cache y forzado ---
                force_check = force_update_check_all or (cid in force_update_check_ids)
                last_check = update_check_time.get(cid, 0)
                # Si forzado o nunca chequeado o pasado el intervalo, hacer chequeo
                if force_check or (now - last_check > UPDATE_CHECK_MIN_INTERVAL) or (cid not in update_check_cache):
                    update_available = check_image_update(container)
                    update_check_cache[cid] = update_available
                    update_check_time[cid] = now
                    if cid in force_update_check_ids:
                        force_update_check_ids.discard(cid)
                else:
                    update_available = update_check_cache.get(cid)

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

                # --- Añadir pid_count y mem_limit_mb ---
                pid_count = current_stats_raw.get('pids_stats', {}).get('current')
                mem_limit_mb = round(current_stats_raw.get('memory_stats', {}).get('limit', 0) / 1048576, 2) or None

                # GPU metrics
                if os.getenv('GPU_METRICS_ENABLED','false').lower() == 'true':
                    try:
                        gpu_stats = get_gpu_usage()
                        gpu_max = max((g['gpu_util'] for g in gpu_stats), default=None)
                    except Exception as e:
                        logging.warning(f"GPU metrics failed: {e}")
                        gpu_stats = None
                        gpu_max = None

                # Check for status change BEFORE adding new data to history
                previous_status = None
                status_changed = False
                dq = history.setdefault(cid, collections.deque(maxlen=MAX_SECONDS // SAMPLE_INTERVAL))
                
                if dq and len(dq) > 0:
                    try:
                        previous_status = dq[-1][3]  # Status is at index 3 in the history tuple
                        if previous_status != status:
                            status_changed = True
                    except (IndexError, TypeError):
                        pass
                
                # Now add the new status to history
                dq.append((time.time(), cpu, mem_percent, status, container_name, net_rx, net_tx, blk_r, blk_w, update_available, pid_count, mem_limit_mb, gpu_stats, gpu_max))

                # --- Notification logic ---
                now = time.time()
                # CPU notification
                if notification_settings.get('cpu_enabled', True):
                    if cpu >= notification_settings['cpu_threshold']:
                        if cid not in cpu_exceed_start:
                            cpu_exceed_start[cid] = now
                        elif now - cpu_exceed_start[cid] >= notification_settings['window_seconds']:
                            # Only notify once per window
                            if not any(n for n in notifications if n['type']=='cpu' and n['cid']==cid and now-n['timestamp']<notification_settings['window_seconds']*2):
                                n = {
                                    'type': 'cpu',
                                    'cid': cid,
                                    'container': container_name,
                                    'value': cpu,
                                    'timestamp': now,
                                    'msg': f"{container_name}: CPU usage {cpu:.1f}% exceeded {notification_settings['cpu_threshold']}% for {notification_settings['window_seconds']}s"
                                }
                                notifications.append(n)
                                push_notify(n['msg'])
                    else:
                        cpu_exceed_start.pop(cid, None)
                # RAM notification
                if notification_settings.get('ram_enabled', True):
                    if mem_percent >= notification_settings['ram_threshold']:
                        if cid not in ram_exceed_start:
                            ram_exceed_start[cid] = now
                        elif now - ram_exceed_start[cid] >= notification_settings['window_seconds']:
                            if not any(n for n in notifications if n['type']=='ram' and n['cid']==cid and now-n['timestamp']<notification_settings['window_seconds']*2):
                                n = {
                                    'type': 'ram',
                                    'cid': cid,
                                    'container': container_name,
                                    'value': mem_percent,
                                    'timestamp': now,
                                    'msg': f"{container_name}: RAM usage {mem_percent:.1f}% exceeded {notification_settings['ram_threshold']}% for {notification_settings['window_seconds']}s"
                                }
                                notifications.append(n)
                                push_notify(n['msg'])
                    else:
                        ram_exceed_start.pop(cid, None)

                # Send status change notification if enabled
                if status_changed and previous_status and notification_settings.get('status_enabled', True):
                    n = {
                        'type': 'status',
                        'cid': cid,
                        'container': container_name,
                        'value': status,
                        'prev_value': previous_status,
                        'timestamp': now,
                        'msg': f"{container_name}: Status changed from {previous_status} to {status}"
                    }
                    notifications.append(n)
                    push_notify(n['msg'])
                
                # Update notification
                if notification_settings.get('update_enabled', True) and update_available is True:
                    # Check if this is a new discovery of an update
                    is_new_update = True
                    if dq and len(dq) > 1:
                        try:
                            previous_update_available = dq[-2][9]  # update_available is at index 9
                            if previous_update_available is True:
                                is_new_update = False  # Was already available
                        except (IndexError, TypeError):
                            pass
                    
                    if is_new_update:
                        n = {
                            'type': 'update',
                            'cid': cid,
                            'container': container_name,
                            'value': True,
                            'timestamp': now,
                            'msg': f"{container_name}: Update available for this container"
                        }
                        notifications.append(n)
                        push_notify(n['msg'])

                time.sleep(0.2)  # Stagger requests para evitar throttling

            except docker.errors.NotFound:
                if cid in history: del history[cid]
                if cid in previous_stats: del previous_stats[cid]
                if cid in update_check_cache: del update_check_cache[cid]
                if cid in update_check_time: del update_check_time[cid]
                continue

            except Exception as e:
                logging.error(f"ERROR muestreando métricas para contenedor {cid[:12]} (Nombre: {container_name}): {e}")
                dq = history.setdefault(cid, collections.deque(maxlen=MAX_SECONDS // SAMPLE_INTERVAL))
                dq.append((time.time(), 0.0, 0.0, "error-sample", container_name, 0, 0, 0, 0, None, None, None, None, None))

        removed_ids_prev = set(previous_stats.keys()) - current_running_ids
        for cid_removed in removed_ids_prev:
            if cid_removed in previous_stats: del previous_stats[cid_removed]

        try:
            # Remove containers from history that don't exist anymore (not even in stopped state)
            history_ids_to_remove = set(history.keys()) - all_container_ids
            for cid_hist_removed in history_ids_to_remove:
                last_known_name = "Desconocido"
                try:
                    if cid_hist_removed in history and history[cid_hist_removed]:
                        last_known_name = history[cid_hist_removed][-1][4]
                except (IndexError, TypeError): pass
                if cid_hist_removed in history: del history[cid_hist_removed]
                if cid_hist_removed in previous_stats:
                    del previous_stats[cid_hist_removed]
                if cid_hist_removed in update_check_cache:
                    del update_check_cache[cid_hist_removed]
                if cid_hist_removed in update_check_time:
                    del update_check_time[cid_hist_removed]

        except docker.errors.DockerException as e:
            logging.warning(f"Error Docker durante limpieza de historial: {e}")
        except Exception as e:
            logging.warning(f"Error genérico durante limpieza de historial: {e}")

        time.sleep(SAMPLE_INTERVAL)
        force_update_check_all = False  # Reset global force after ciclo

# API helper for notifications (to be imported in routes.py)
def get_notifications(since_ts=None, max_items=50):
    now = time.time()
    if since_ts is not None:
        return [n for n in list(notifications)[-max_items:] if n['timestamp'] > since_ts]
    return list(notifications)[-max_items:]