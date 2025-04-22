# -*- coding: utf-8 -*-

import datetime
import time  # Add time import
from flask import Blueprint, jsonify, request, render_template, Response, stream_with_context  # Quitado escape
from markupsafe import escape  # Añadido para compatibilidad Flask >=2.3
import docker
import json  # Add json import for embedding data
errors = docker.errors

# Importar estado compartido y clientes/utilidades necesarias
from sampler import history # Necesario para /api/metrics y /api/compare
from docker_client import get_docker_client, get_api_client # Necesario para ambas APIs
from metrics_utils import parse_datetime, format_uptime # Necesario para /api/metrics

# Crear un Blueprint para las rutas
main_routes = Blueprint('main_routes', __name__, template_folder='templates', static_folder='static')

# --- Simple HTTP Basic Authentication ---
from config import AUTH_USER, AUTH_PASSWORD
@main_routes.before_request
def require_auth():
    # If credentials not set, skip authentication
    if not AUTH_USER or not AUTH_PASSWORD:
        return
    auth = request.authorization
    if not auth or auth.username != AUTH_USER or auth.password != AUTH_PASSWORD:
        return Response('Authentication required', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})

# --- Ruta Index ---
@main_routes.route('/')
def index():
    """Sirve la página HTML principal."""
    print("DEBUG: Sirviendo página index.html") # Añadido para depuración
    return render_template('index.html')

# --- Ruta API Metrics ---
@main_routes.route('/api/metrics')
def api_metrics():
    """Endpoint API para obtener métricas de contenedores filtradas y ordenadas."""
    print("DEBUG: Petición recibida en /api/metrics") # Añadido para depuración
    try:
        client = get_docker_client()
        get_api_client() # Verificar que está inicializado
    except RuntimeError as e:
         print(f"ERROR API: /api/metrics llamado pero el cliente Docker no está inicializado: {e}")
         return jsonify({"error": "Docker client not initialized"}), 500

    # Obtener parámetros de consulta
    project_filter = request.args.get('project','').strip()  # Nuevo filtro de proyecto
    name_filter   = request.args.get('name','').lower().strip()
    status_filter = request.args.get('status','').strip()
    sort_by  = request.args.get('sort','combined')
    sort_dir = request.args.get('dir','desc')
    max_items = int(request.args.get('max', 0))
    # --- NUEVO: Forzar chequeo de updates si force=true ---
    force_update = request.args.get('force', 'false').lower() == 'true'
    if force_update:
        try:
            from sampler import force_update_check_all
            force_update_check_all = True
        except Exception as e:
            print(f"ERROR: No se pudo forzar chequeo de updates: {e}")

    rows = []
    # Copiar claves para evitar problemas si history cambia durante la iteración
    current_history_keys = list(history.keys())
    print(f"DEBUG API: Procesando {len(current_history_keys)} CIDs del historial.")

    for cid in current_history_keys:
        # Doble chequeo por si fue eliminado entre list() y aquí
        if cid not in history:
            print(f"DEBUG API: CID {cid[:6]}.. no encontrado en history (eliminado?)")
            continue

        # Obtener la última muestra válida del deque
        dq = history[cid]
        latest_sample = None
        if dq:
            try:
                # Tomar la última muestra; si falla, el contenedor puede estar en error
                latest_sample = dq[-1]
                 # Orden: time, cpu%, mem%, status, name, net_rx, net_tx, blk_r, blk_w, update_available
                if len(latest_sample) == 10:
                    ts, cpu, mem, status_hist, name_hist, net_rx, net_tx, blk_r, blk_w, update_available = latest_sample
                else:
                    ts, cpu, mem, status_hist, name_hist, net_rx, net_tx, blk_r, blk_w = latest_sample
                    update_available = None

                # Asegurar que cpu y mem son números o None para la API
                cpu = float(cpu) if cpu is not None else None
                mem = float(mem) if mem is not None else None

            except (ValueError, IndexError, TypeError) as sample_err:
                 print(f"DEBUG API: Error procesando última muestra para {cid[:6]}..: {sample_err}")
                 continue # Saltar este contenedor si la última muestra es inválida
        else:
            print(f"DEBUG API: Deque vacío para {cid[:6]}..")
            continue # Saltar si no hay historial para este CID


        container_name = name_hist # Usar nombre del historial como base

        # --- Filtrar basado en nombre muestreado ---
        if name_filter and name_filter not in container_name.lower():
            continue

        # --- Obtener detalles completos desde la API Docker ---
        image_name = "N/A"
        ports_str = "N/A"
        restart_count = 0
        uptime_sec = None
        formatted_uptime = "N/A"
        current_status = status_hist # Fallback status
        compose_project = None
        compose_service = None

        try:
            # Intentar obtener el objeto contenedor completo
            container = client.containers.get(cid)
            current_status = container.status # Obtener estado más reciente

            # Extraer etiquetas de Compose
            attrs = container.attrs or {}
            labels = attrs.get('Config',{}).get('Labels',{}) or {}
            compose_project = labels.get('com.docker.compose.project')
            compose_service = labels.get('com.docker.compose.service')
            # Filtrar por proyecto si se ha seleccionado uno
            if project_filter and project_filter != compose_project:
                continue

            # --- Aplicar Filtro de Estado (sobre el estado más reciente) ---
            if status_filter and current_status != status_filter:
                continue

            # --- Extraer Detalles ---
            state = attrs.get('State', {})

            # Imagen
            try:
                if container.image and container.image.tags: image_name = container.image.tags[0]
                elif container.image: image_name = str(container.image.id).replace("sha256:", "")[:12]
            except Exception: image_name = "Error"

            # Puertos
            try:
                ports_list = []
                if container.ports:
                    for c_port, h_bind in sorted(container.ports.items()):
                        if h_bind:
                            h_info = [f"{b.get('HostIp', '')}:{b.get('HostPort', '')}"
                                      if b.get('HostIp') and b.get('HostIp') not in ['0.0.0.0', '::'] and b.get('HostPort')
                                      else b.get('HostPort', '')
                                      for b in h_bind if b.get('HostPort')]
                            if h_info: ports_list.append(f"{', '.join(h_info)}->{c_port}")
                ports_str = ', '.join(ports_list) if ports_list else "None"
            except Exception: ports_str = "Error"

            # Contador de Reinicios
            restart_count = attrs.get('RestartCount', 0)

            # Uptime (basado en estado actual)
            started_at_str = state.get('StartedAt')
            finished_at_str = state.get('FinishedAt')

            if current_status == 'running' and started_at_str:
                 started_dt = parse_datetime(started_at_str)
                 if started_dt:
                     now_utc = datetime.datetime.now(datetime.timezone.utc)
                     if started_dt.tzinfo is None: started_dt = started_dt.replace(tzinfo=datetime.timezone.utc)
                     uptime_sec = max(0, int((now_utc - started_dt).total_seconds()))
                     formatted_uptime = format_uptime(uptime_sec)
                 else: formatted_uptime = "Error Parse Start"; uptime_sec = None
            elif current_status == 'exited': formatted_uptime = "N/A (Exited)"; uptime_sec = None
            else: formatted_uptime = "N/A"; uptime_sec = None

        except errors.NotFound:
             # Contenedor no existe más, usar datos históricos si pasan filtro de estado histórico
             if status_filter and status_hist != status_filter: continue
             current_status = status_hist # Usar estado histórico
             formatted_uptime = "N/A (Removed)"
             uptime_sec = None

        except errors.DockerException as e:
            print(f"WARN API: Docker error obteniendo detalles para {cid[:6]}.. ({container_name}): {e}")
            if status_filter and status_hist != status_filter: continue # Filtrar por estado histórico
            current_status = status_hist # Fallback a estado histórico
            formatted_uptime = "Error Fetching"
            uptime_sec = None

        except Exception as e:
             print(f"ERROR API: Error inesperado procesando {cid[:6]}.. ({container_name}): {e}")
             if status_filter and status_hist != status_filter: continue
             current_status = status_hist
             formatted_uptime = "Error"
             uptime_sec = None

        # Get process count
        pid_count = None
        try:
            if 'container' in locals() and container:
                top_info = container.top()
                processes = top_info.get('Processes', []) if isinstance(top_info, dict) else []
                pid_count = len(processes)
        except Exception:
            pid_count = None

        # Get memory limit in MB: si no hay límite, usar memoria total del host
        mem_limit_bytes = 0
        try:
            if 'container' in locals() and container:
                mem_limit_bytes = container.attrs.get('HostConfig', {}).get('Memory', 0)
            if not mem_limit_bytes:
                host_info = client.info()
                mem_limit_bytes = host_info.get('MemTotal', 0)
        except Exception:
            mem_limit_bytes = 0
        mem_limit_mb = round(mem_limit_bytes / (1024*1024), 2) if mem_limit_bytes > 0 else None

        # --- Añadir Fila ---
        rows.append({
            'id': cid,
            'name': container_name,
            'pid_count': pid_count,  # Number of processes in the container
            'cpu': cpu, # Valor numérico o None
            'mem': mem, # Valor numérico o None
            'mem_limit': mem_limit_mb,  # Memory limit in MB
            'combined': (cpu or 0) + (mem or 0), # Asegurar números para suma
            'status': current_status,
            'uptime_sec': uptime_sec, # Puede ser None
            'uptime': formatted_uptime,
            'net_io_rx': net_rx,
            'net_io_tx': net_tx,
            'block_io_r': blk_r,
            'block_io_w': blk_w,
            'image': image_name,
            'ports': ports_str,
            'restarts': restart_count,
            'update_available': update_available,  # Indica si hay nueva versión de imagen
            'compose_project': compose_project,    # Proyecto de Compose
            'compose_service': compose_service     # Servicio de Compose
        })

    # --- Ordenación ---
    reverse_sort = (sort_dir == 'desc')
    numeric_keys = ['cpu', 'mem', 'combined', 'uptime_sec', 'restarts', 'net_io_rx', 'net_io_tx', 'block_io_r', 'block_io_w', 'pid_count', 'mem_limit', 'update_available']
    string_keys = ['name', 'status', 'image', 'ports', 'uptime']

    def sort_key(item):
        key_value = item.get(sort_by)
        if sort_by in numeric_keys:
             if isinstance(key_value, bool):
                 return int(key_value)
             if sort_by == 'update_available' and key_value is None:
                 return -1
             return key_value if key_value is not None else float('-inf')
        elif sort_by in string_keys:
             return str(key_value) if key_value is not None else ''
        return key_value if key_value is not None else ''

    try:
        rows.sort(key=sort_key, reverse=reverse_sort)
    except TypeError as e:
        print(f"WARN API: Error durante ordenación (key '{sort_by}', type: {type(e)}): {e}. Usando orden por nombre.")
        rows.sort(key=lambda x: str(x.get('name', '')).lower(), reverse=False)

    if max_items > 0:
        rows = rows[:max_items]

    print(f"DEBUG API: Retornando {len(rows)} filas.")
    return jsonify(rows)

# --- Ruta API para proyectos de Compose ---
@main_routes.route('/api/projects')
def api_projects():
    """Devuelve la lista de proyectos de Compose activos."""
    try:
        client = get_docker_client()
    except RuntimeError as e:
        print(f"ERROR API: /api/projects cliente Docker no inicializado: {e}")
        return jsonify([]), 500
    projects = set()
    for c in client.containers.list(all=True):
        lbls = c.attrs.get('Config', {}).get('Labels', {}) or {}
        proj = lbls.get('com.docker.compose.project')
        if proj:
            projects.add(proj)
    return jsonify(sorted(projects))

# --- Ruta API para Historial del Contenedor (para Gráficos) ---
@main_routes.route('/api/history/<container_id>')
def api_container_history(container_id):
    """Devuelve datos históricos de CPU y RAM para un contenedor específico."""
    print(f"DEBUG HISTORY: Petición recibida para historial de {container_id[:12]}")
    try:
        get_docker_client()
    except RuntimeError as e:
         print(f"ERROR API: /api/history llamado pero el cliente Docker no está inicializado: {e}")
         return jsonify({"error": "Docker client not initialized"}), 500

    try:
        range_seconds = int(request.args.get('range', 86400))
        if range_seconds <= 0: range_seconds = 86400
    except ValueError:
        range_seconds = 86400

    print(f"DEBUG HISTORY: Rango solicitado: {range_seconds} segundos para {container_id[:12]}")

    if container_id not in history:
        print(f"WARN HISTORY: No se encontró historial para {container_id[:12]}")
        return jsonify({"error": "No history found for this container ID"}), 404

    dq = history[container_id]
    now = time.time()
    cutoff_time = now - range_seconds

    timestamps = []
    cpu_usage = []
    ram_usage = []

    try:
        dq_copy = list(dq)
        print(f"DEBUG HISTORY: Procesando {len(dq_copy)} muestras para {container_id[:12]}")
        for sample in dq_copy:
            try:
                if len(sample) == 10:
                    ts, cpu, mem, _, _, _, _, _, _, _ = sample
                else:
                    ts, cpu, mem, _, _, _, _, _, _ = sample

                if ts >= cutoff_time:
                    timestamps.append(ts)
                    cpu_usage.append(float(cpu) if cpu is not None else 0)
                    ram_usage.append(float(mem) if mem is not None else 0)
            except (ValueError, TypeError, IndexError) as sample_err:
                print(f"WARN HISTORY: Saltando muestra inválida para {container_id[:12]}: {sample_err} - Muestra: {sample}")
                continue

        print(f"DEBUG HISTORY: Encontradas {len(timestamps)} muestras dentro del rango para {container_id[:12]}")

        response_data = {
            "container_id": container_id,
            "range_seconds": range_seconds,
            "timestamps": timestamps,
            "cpu_usage": cpu_usage,
            "ram_usage": ram_usage
        }
        return jsonify(response_data)

    except Exception as e:
        print(f"ERROR HISTORY: Error inesperado procesando historial para {container_id[:12]}: {e}")
        return jsonify({"error": "Internal server error processing history"}), 500

# --- Ruta API para Logs del Contenedor ---
@main_routes.route('/api/logs/<container_id>')
def stream_container_logs(container_id):
    print(f"DEBUG LOGS: Petición recibida para logs de {container_id[:12]}")
    try:
        client = get_docker_client()
        container = client.containers.get(container_id)
        container_name = escape(container.name)
    except errors.NotFound:
        print(f"WARN LOGS: Contenedor {container_id[:12]} no encontrado.")
        return f"<html><body><h1>Error 404</h1><p>Container '{escape(container_id)}' not found.</p></body></html>", 404
    except Exception as e:
        print(f"ERROR LOGS: Error accediendo al contenedor {container_id[:12]}: {e}")
        return f"<html><body><h1>Error 500</h1><p>Error accessing container: {escape(str(e))}</p></body></html>", 500

    def generate_logs():
        yield '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
        yield f'<title>Logs: {container_name} ({container_id[:12]})</title>'
        yield '''<style>
            body { font-family: monospace; background-color: #f8f9fa; color: #212529; line-height: 1.4; margin: 0; padding: 15px; }
            pre { white-space: pre-wrap; word-wrap: break-word; margin: 0; border: 1px solid #dee2e6; padding: 10px; border-radius: 4px; background-color: #fff;}
            h2 { margin-top: 0; color: #343a40; }
            @media (prefers-color-scheme: dark) {
                body { background-color: #1c1c1c; color: #e0e0e0; }
                pre { background-color: #2a2a2a; border-color: #444; }
                h2 { color: #adb5bd; }
            }
        </style></head><body>'''
        yield f'<h2>Logs for {container_name}</h2><pre>'

        log_stream = None
        try:
            print(f"DEBUG LOGS: Obteniendo stream de logs para {container_id[:12]}")
            log_stream = container.logs(stream=True, follow=False, tail=200, timestamps=True)
            processed_lines = 0
            for chunk in log_stream:
                try:
                    decoded_line = chunk.decode('utf-8', errors='replace')
                    yield escape(decoded_line)
                    processed_lines += 1
                except UnicodeDecodeError:
                    yield "[log decode error]\n"
            print(f"DEBUG LOGS: Procesadas {processed_lines} líneas de log para {container_id[:12]}")

        except errors.APIError as api_e:
             print(f"ERROR LOGS: Docker API Error obteniendo logs para {container_id[:12]}: {api_e}")
             yield f"\n--- Docker API Error fetching logs: {escape(str(api_e))} ---"
        except Exception as log_e:
             print(f"ERROR LOGS: Error inesperado streameando logs para {container_id[:12]}: {log_e}")
             yield f"\n--- Error streaming logs: {escape(str(log_e))} ---"
        finally:
             yield '</pre></body></html>'
             if hasattr(log_stream, 'close'):
                 try: log_stream.close()
                 except Exception: pass
             print(f"DEBUG LOGS: Stream de logs cerrado para {container_id[:12]}")

    return Response(stream_with_context(generate_logs()), mimetype='text/html')

# --- Ruta para obtener logs de un contenedor ---
@main_routes.route('/logs/<container_id>')
def get_container_logs(container_id):
    try:
        client = get_docker_client()
        container = client.containers.get(container_id)
        logs = container.logs(tail=1000).decode('utf-8')
        return render_template('logs.html', logs=logs, container_name=container.name)
    except Exception as e:
        return f"Error al obtener logs: {str(e)}", 500

# --- Ruta para la página de comparación ---
@main_routes.route('/compare/<compare_type>')
def compare_page(compare_type):
    try:
        top_n = int(request.args.get('topN', 5))
        if top_n <= 0: top_n = 5
    except ValueError:
        top_n = 5

    valid_types = {
        "usage": "CPU/RAM Usage",
        "uptime": "Uptime"
    }
    if compare_type not in valid_types:
        return "Invalid comparison type", 404

    title = valid_types[compare_type]
    print(f"DEBUG COMPARE PAGE: Sirviendo página de comparación para '{title}' (Top {top_n}) con datos embebidos.")

    comparison_data = []
    try:
        client = get_docker_client()
        get_api_client()

        rows = []
        current_history_keys = list(history.keys())

        for cid in current_history_keys:
            if cid not in history: continue
            dq = history[cid]
            latest_sample = None
            if dq:
                try:
                    latest_sample = dq[-1]
                    sample_len = len(latest_sample)
                    ts = latest_sample[0] if sample_len > 0 else None
                    cpu = float(latest_sample[1]) if sample_len > 1 and latest_sample[1] is not None else None
                    mem = float(latest_sample[2]) if sample_len > 2 and latest_sample[2] is not None else None
                    status_hist = latest_sample[3] if sample_len > 3 else "unknown"
                    name_hist = latest_sample[4] if sample_len > 4 else f"container_{cid[:6]}"
                except (ValueError, IndexError, TypeError): continue
            else: continue

            container_name = name_hist
            uptime_sec = None
            formatted_uptime = "N/A"
            current_status = status_hist

            if compare_type == "uptime":
                try:
                    container = client.containers.get(cid)
                    current_status = container.status
                    attrs = container.attrs or {}
                    state = attrs.get('State', {})

                    started_at_str = state.get('StartedAt')
                    if current_status == 'running' and started_at_str:
                        started_dt = parse_datetime(started_at_str)
                        if started_dt:
                            now_utc = datetime.datetime.now(datetime.timezone.utc)
                            if started_dt.tzinfo is None: started_dt = started_dt.replace(tzinfo=datetime.timezone.utc)
                            uptime_sec = max(0, int((now_utc - started_dt).total_seconds()))
                            formatted_uptime = format_uptime(uptime_sec)
                        else: uptime_sec = None; formatted_uptime = "Error Parse"
                    else: uptime_sec = None; formatted_uptime = "N/A"

                except errors.NotFound:
                    uptime_sec = None; formatted_uptime = "N/A (Removed)"; current_status = status_hist
                except Exception as e:
                    print(f"WARN COMPARE PAGE: Error obteniendo detalles para {cid[:6]}..: {e}")
                    uptime_sec = None; formatted_uptime = "Error Fetching"; current_status = status_hist

            row_data = {
                'id': cid,
                'name': container_name,
                'cpu': cpu,
                'mem': mem,
                'combined': (cpu or 0) + (mem or 0),
                'uptime_sec': uptime_sec,
                'uptime': formatted_uptime,
                'status': current_status
            }
            keys_to_keep = {'id', 'name'}
            if compare_type == 'usage':
                keys_to_keep.update({'cpu', 'mem'})
            elif compare_type == 'uptime':
                keys_to_keep.update({'uptime_sec', 'uptime'})

            filtered_row_data = {k: v for k, v in row_data.items() if k in keys_to_keep}
            rows.append(filtered_row_data)

        sort_key_map = {
            "usage": "combined",
            "uptime": "uptime_sec"
        }
        primary_sort_field = sort_key_map.get(compare_type)

        def compare_sort_key(item):
            primary_value = item.get(primary_sort_field) if primary_sort_field else None
            name_value = item.get('name', '')

            numeric_primary = primary_value if primary_value is not None else float('-inf')

            return (-numeric_primary, name_value.lower())

        try:
             rows.sort(key=compare_sort_key, reverse=False)
        except TypeError as e:
            print(f"WARN COMPARE PAGE: Error durante ordenación (key '{primary_sort_field}'): {e}. Usando orden por nombre.")
            rows.sort(key=lambda x: str(x.get('name', '')).lower(), reverse=False)

        comparison_data = rows[:top_n]
        print(f"DEBUG COMPARE PAGE: Datos preparados para {len(comparison_data)} contenedores.")

    except RuntimeError as e:
         print(f"ERROR COMPARE PAGE: Cliente Docker no inicializado: {e}")
         comparison_data = []
    except Exception as e:
        print(f"ERROR COMPARE PAGE: Error inesperado preparando datos: {e}")
        comparison_data = []

    return render_template('compare.html',
                           compare_type=compare_type,
                           top_n=top_n,
                           title=title,
                           comparison_data=comparison_data)

# --- Ruta API para datos de comparación ---
@main_routes.route('/api/compare/<compare_type>')
def api_compare_data(compare_type):
    print(f"DEBUG COMPARE API: Petición recibida para /api/compare/{compare_type}")
    try:
        client = get_docker_client()
        get_api_client()
    except RuntimeError as e:
         print(f"ERROR API: /api/compare llamado pero el cliente Docker no está inicializado: {e}")
         return jsonify({"error": "Docker client not initialized"}), 500

    try:
        top_n = int(request.args.get('topN', 5))
        if top_n <= 0: top_n = 5
    except ValueError:
        top_n = 5

    valid_types = ["usage", "uptime"]
    if compare_type not in valid_types:
        return jsonify({"error": "Invalid comparison type"}), 400

    rows = []
    current_history_keys = list(history.keys())
    print(f"DEBUG COMPARE API: Procesando {len(current_history_keys)} CIDs para comparación '{compare_type}' (Top {top_n})")

    for cid in current_history_keys:
        if cid not in history: continue
        dq = history[cid]
        latest_sample = None
        if dq:
            try:
                latest_sample = dq[-1]
                if len(latest_sample) == 10:
                    ts, cpu, mem, status_hist, name_hist, net_rx, net_tx, blk_r, blk_w, update_available = latest_sample
                else:
                    ts, cpu, mem, status_hist, name_hist, net_rx, net_tx, blk_r, blk_w = latest_sample
                    update_available = None
                cpu = float(cpu) if cpu is not None else None
                mem = float(mem) if mem is not None else None
            except (ValueError, IndexError, TypeError): continue
        else: continue

        container_name = name_hist
        uptime_sec = None
        formatted_uptime = "N/A"
        current_status = status_hist

        if compare_type == "uptime":
            try:
                container = client.containers.get(cid)
                current_status = container.status
                attrs = container.attrs or {}
                state = attrs.get('State', {})

                started_at_str = state.get('StartedAt')
                if current_status == 'running' and started_at_str:
                    started_dt = parse_datetime(started_at_str)
                    if started_dt:
                        now_utc = datetime.datetime.now(datetime.timezone.utc)
                        if started_dt.tzinfo is None: started_dt = started_dt.replace(tzinfo=datetime.timezone.utc)
                        uptime_sec = max(0, int((now_utc - started_dt).total_seconds()))
                        formatted_uptime = format_uptime(uptime_sec)
                    else: uptime_sec = None; formatted_uptime = "Error Parse"
                else: uptime_sec = None; formatted_uptime = "N/A"

            except errors.NotFound:
                uptime_sec = None
                formatted_uptime = "N/A (Removed)"
                current_status = status_hist
            except Exception as e:
                print(f"WARN COMPARE API: Error obteniendo detalles para {cid[:6]}..: {e}")
                uptime_sec = None
                formatted_uptime = "Error Fetching"
                current_status = status_hist

        rows.append({
            'id': cid,
            'name': container_name,
            'cpu': cpu,
            'mem': mem,
            'combined': (cpu or 0) + (mem or 0),
            'uptime_sec': uptime_sec,
            'uptime': formatted_uptime,
            'status': current_status
        })

    sort_key_map = {
        "usage": "combined",
        "uptime": "uptime_sec"
    }
    sort_field = sort_key_map.get(compare_type, "combined")

    def compare_sort_key(item):
        key_value = item.get(sort_field)
        return key_value if key_value is not None else float('-inf')

    try:
        rows.sort(key=compare_sort_key, reverse=True)
    except TypeError as e:
        print(f"WARN COMPARE API: Error durante ordenación (key '{sort_field}'): {e}. Usando orden por nombre.")
        rows.sort(key=lambda x: str(x.get('name', '')).lower(), reverse=False)

    top_rows = rows[:top_n]

    print(f"DEBUG COMPARE API: Retornando {len(top_rows)} filas para comparación '{compare_type}'.")
    return jsonify(top_rows)

# --- CSV Export Endpoint ---
@main_routes.route('/api/export/csv', methods=['POST'])
def export_csv():
    data = request.get_json() or {}
    metrics = data.get('metrics', [])
    import csv, io
    si = io.StringIO()
    writer = csv.writer(si)
    if metrics:
        headers = list(metrics[0].keys())
        writer.writerow(headers)
        for row in metrics:
            writer.writerow([row.get(h) for h in headers])
    output = si.getvalue()
    return Response(output, mimetype='text/csv', headers={
        'Content-Disposition': 'attachment; filename=metrics.csv'
    })

# --- Container Control Endpoints ---
@main_routes.route('/api/containers/<container_id>/<action>', methods=['POST'])
def container_action(container_id, action):
    """Start, stop, restart or update a Docker container"""
    try:
        client = get_docker_client()
        container = client.containers.get(container_id)
        container_name = escape(container.name)

        if action == 'start':
            container.start()
            return jsonify({'status': f'Container {container_name} started'})
        elif action == 'stop':
            container.stop()
            return jsonify({'status': f'Container {container_name} stopped'})
        elif action == 'restart':
            container.restart()
            return jsonify({'status': f'Container {container_name} restarted'})
        elif action == 'update':
            def generate_update_logs():
                try:
                    yield f"Starting update for {container_name} ({container_id[:12]})...\n"
                    if container.image and container.image.tags:
                        latest_tag = container.image.tags[0]
                        yield f"Pulling latest image: {latest_tag}...\n"
                        try:
                            pull_stream = client.api.pull(latest_tag, stream=True, decode=True)
                            for chunk in pull_stream:
                                status = chunk.get('status', '')
                                progress = chunk.get('progress', '')
                                line = f"{status} {progress}\n" if progress else f"{status}\n"
                                yield escape(line)
                            yield f"Image {latest_tag} pulled successfully.\n"
                        except errors.APIError as pull_err:
                            yield f"ERROR pulling image {latest_tag}: {escape(str(pull_err))}\n"
                            yield "Update aborted due to pull error.\n"
                            return
                        except Exception as pull_ex:
                            yield f"UNEXPECTED ERROR during pull: {escape(str(pull_ex))}\n"
                            yield "Update aborted due to unexpected pull error.\n"
                            return
                    else:
                        yield "No image tag found. Cannot pull/update image from registry. Skipping pull.\n"

                    yield f"Restarting container {container_name}...\n"
                    try:
                        container.restart()
                        yield f"Container {container_name} restarted successfully.\n"
                        yield "Update process completed.\n"
                    except errors.APIError as restart_err:
                        yield f"ERROR restarting container: {escape(str(restart_err))}\n"
                        yield "Update failed during restart.\n"
                    except Exception as restart_ex:
                        yield f"UNEXPECTED ERROR during restart: {escape(str(restart_ex))}\n"
                        yield "Update failed due to unexpected restart error.\n"

                    # Al finalizar el update, forzar chequeo inmediato de update_available para este contenedor
                    try:
                        from sampler import force_update_check_ids
                        force_update_check_ids.add(container_id)
                    except Exception as e:
                        print(f"ERROR: No se pudo forzar chequeo de update tras pull: {e}")

                except errors.NotFound:
                    yield f"ERROR: Container {container_id[:12]} not found during update.\n"
                except Exception as e:
                    yield f"FATAL ERROR during update process: {escape(str(e))}\n"

            # Return a streaming response
            return Response(stream_with_context(generate_update_logs()), mimetype='text/plain')
        else:
            return jsonify({'error': 'Invalid action'}), 400

    except errors.NotFound:
        return jsonify({'error': f'Container {container_id} not found'}), 404
    except Exception as e:
        print(f"ERROR in container_action ({action} for {container_id[:12]}): {e}")
        return jsonify({'error': f'An unexpected error occurred: {escape(str(e))}'}), 500