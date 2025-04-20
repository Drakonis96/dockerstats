# -*- coding: utf-8 -*-

import datetime
import time  # Add time import
from flask import Blueprint, jsonify, request, render_template, Response, stream_with_context  # Quitado escape
from markupsafe import escape  # Añadido para compatibilidad Flask >=2.3
from docker import errors

# Importar estado compartido y clientes/utilidades necesarias
from sampler import history # Necesario para /api/metrics y /api/compare
from docker_client import get_docker_client, get_api_client # Necesario para ambas APIs
from metrics_utils import parse_datetime, format_uptime # Necesario para /api/metrics

# Crear un Blueprint para las rutas
main_routes = Blueprint('main_routes', __name__, template_folder='templates', static_folder='static')

# --- Ruta Index ---
@main_routes.route('/')
def index():
    """Sirve la página HTML principal."""
    # render_template buscará 'index.html' en la carpeta 'templates' asociada al blueprint
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
    name_filter   = request.args.get('name','').lower().strip()
    status_filter = request.args.get('status','').strip()
    sort_by  = request.args.get('sort','combined')
    sort_dir = request.args.get('dir','desc')
    max_items = int(request.args.get('max', 0))

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
                 # Orden: time, cpu%, mem%, status, name, net_rx, net_tx, blk_r, blk_w
                ts, cpu, mem, status_hist, name_hist, net_rx, net_tx, blk_r, blk_w = latest_sample
                # Asegurar que cpu y mem son números o None para la API
                cpu = float(cpu) if cpu is not None else None
                mem = float(mem) if cpu is not None else None

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
        size_rw_mb = None
        size_rootfs_mb = None
        current_status = status_hist # Fallback status

        try:
            # Intentar obtener el objeto contenedor completo
            container = client.containers.get(cid)
            current_status = container.status # Obtener estado más reciente

            # --- Aplicar Filtro de Estado (sobre el estado más reciente) ---
            if status_filter and current_status != status_filter:
                continue

            # --- Extraer Detalles ---
            attrs = container.attrs or {}
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
            # Tamaño RW: usar inspect con size=True para obtener SizeRw
            try:
                inspect_data = client.api.inspect_container(cid, size=True)
                size_rw_bytes = inspect_data.get('SizeRw')
                size_rw_mb = round(size_rw_bytes / (1024*1024), 2) if size_rw_bytes is not None else None
                # Add total filesystem size (layers + RW)
                size_rootfs_bytes = inspect_data.get('SizeRootFs')
                size_rootfs_mb = round(size_rootfs_bytes / (1024*1024), 2) if size_rootfs_bytes is not None else None
            except Exception:
                size_rw_mb = None
                size_rootfs_mb = None

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
             # Otros datos ya vienen del historial (cpu, mem, net, blk, name)

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
            top_info = container.top()
            processes = top_info.get('Processes', []) if isinstance(top_info, dict) else []
            pid_count = len(processes)
        except Exception:
            pid_count = None

        # Get memory limit in MB: si no hay límite, usar memoria total del host
        mem_limit_bytes = container.attrs.get('HostConfig', {}).get('Memory', 0)
        if not mem_limit_bytes:
            try:
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
            'size_rw': size_rw_mb, # Puede ser None
            'size_rootfs': size_rootfs_mb, # Total FS size en MB
            'net_io_rx': net_rx,
            'net_io_tx': net_tx,
            'block_io_r': blk_r,
            'block_io_w': blk_w,
            'image': image_name,
            'ports': ports_str,
            'restarts': restart_count
        })

    # --- Ordenación ---
    reverse_sort = (sort_dir == 'desc')
    numeric_keys = ['cpu', 'mem', 'combined', 'uptime_sec', 'restarts', 'size_rw', 'size_rootfs', 'net_io_rx', 'net_io_tx', 'block_io_r', 'block_io_w', 'pid_count', 'mem_limit']
    string_keys = ['name', 'status', 'image', 'ports', 'uptime']

    def sort_key(item):
        key_value = item.get(sort_by)
        if sort_by in numeric_keys:
             # Tratar None como -infinito para que se ordene consistentemente
             return key_value if key_value is not None else float('-inf')
        elif sort_by in string_keys:
             # Tratar None como string vacío
             return str(key_value) if key_value is not None else ''
        # Fallback (no debería pasar si sort_by es válido)
        return key_value if key_value is not None else ''

    try:
        # Usar una clave lambda segura que maneje None
        rows.sort(key=sort_key, reverse=reverse_sort)
    except TypeError as e:
        print(f"WARN API: Error durante ordenación (key '{sort_by}', type: {type(e)}): {e}. Usando orden por nombre.")
        rows.sort(key=lambda x: str(x.get('name', '')).lower(), reverse=False) # Fallback a nombre

    # --- Limitar Resultados ---
    if max_items > 0:
        rows = rows[:max_items]

    print(f"DEBUG API: Retornando {len(rows)} filas.")
    return jsonify(rows)


# --- Ruta API para Historial del Contenedor (para Gráficos) ---
@main_routes.route('/api/history/<container_id>')
def api_container_history(container_id):
    """Devuelve datos históricos de CPU y RAM para un contenedor específico."""
    print(f"DEBUG HISTORY: Petición recibida para historial de {container_id[:12]}")
    try:
        # Verificar que el cliente Docker esté inicializado (aunque no se use directamente aquí)
        get_docker_client()
    except RuntimeError as e:
         print(f"ERROR API: /api/history llamado pero el cliente Docker no está inicializado: {e}")
         return jsonify({"error": "Docker client not initialized"}), 500

    # Obtener parámetro de rango (en segundos)
    try:
        range_seconds = int(request.args.get('range', 86400)) # Default a 24 horas
        if range_seconds <= 0: range_seconds = 86400 # Asegurar rango positivo
    except ValueError:
        range_seconds = 86400 # Default si el parámetro no es un entero válido

    print(f"DEBUG HISTORY: Rango solicitado: {range_seconds} segundos para {container_id[:12]}")

    # Obtener historial para el CID
    if container_id not in history:
        print(f"WARN HISTORY: No se encontró historial para {container_id[:12]}")
        return jsonify({"error": "No history found for this container ID"}), 404

    dq = history[container_id]
    now = time.time()
    cutoff_time = now - range_seconds

    # Filtrar datos dentro del rango de tiempo
    # Formato muestra: (timestamp, cpu%, mem%, status, name, net_rx, net_tx, blk_r, blk_w)
    timestamps = []
    cpu_usage = []
    ram_usage = []

    # Iterar sobre una copia para evitar problemas de concurrencia si el deque cambia
    try:
        dq_copy = list(dq) # Crear una copia para iteración segura
        print(f"DEBUG HISTORY: Procesando {len(dq_copy)} muestras para {container_id[:12]}")
        for sample in dq_copy:
            try:
                ts, cpu, mem, _, _, _, _, _, _ = sample # Desempaquetar, ignorando lo no necesario
                if ts >= cutoff_time:
                    timestamps.append(ts)
                    # Convertir a float, manejar None como 0 para el gráfico
                    cpu_usage.append(float(cpu) if cpu is not None else 0)
                    ram_usage.append(float(mem) if mem is not None else 0)
            except (ValueError, TypeError, IndexError) as sample_err:
                # Saltar muestras malformadas
                print(f"WARN HISTORY: Saltando muestra inválida para {container_id[:12]}: {sample_err} - Muestra: {sample}")
                continue

        print(f"DEBUG HISTORY: Encontradas {len(timestamps)} muestras dentro del rango para {container_id[:12]}")

        # Preparar respuesta JSON
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
    """Devuelve los logs de un contenedor específico, formateados para el navegador."""
    print(f"DEBUG LOGS: Petición recibida para logs de {container_id[:12]}") # Añadido para depuración
    try:
        client = get_docker_client()
        container = client.containers.get(container_id)
        container_name = escape(container.name) # Obtener nombre para título
    except errors.NotFound:
        print(f"WARN LOGS: Contenedor {container_id[:12]} no encontrado.")
        return f"<html><body><h1>Error 404</h1><p>Container '{escape(container_id)}' not found.</p></body></html>", 404
    except Exception as e:
        print(f"ERROR LOGS: Error accediendo al contenedor {container_id[:12]}: {e}")
        return f"<html><body><h1>Error 500</h1><p>Error accessing container: {escape(str(e))}</p></body></html>", 500

    def generate_logs():
        # Encabezado HTML
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

        # Obtener y streamear logs
        log_stream = None
        try:
            print(f"DEBUG LOGS: Obteniendo stream de logs para {container_id[:12]}")
            log_stream = container.logs(stream=True, follow=False, tail=200, timestamps=True) # Obtener últimas 200 líneas
            processed_lines = 0
            for chunk in log_stream:
                try:
                    decoded_line = chunk.decode('utf-8', errors='replace')
                    yield escape(decoded_line) # Escapar para seguridad
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
             # Cerrar las etiquetas HTML
             yield '</pre></body></html>'
             # Aunque follow=False, cerrar explícitamente si es posible (puede no ser necesario)
             if hasattr(log_stream, 'close'):
                 try: log_stream.close()
                 except Exception: pass
             print(f"DEBUG LOGS: Stream de logs cerrado para {container_id[:12]}")

    # Devolver una respuesta que streamea el contenido HTML
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
    """Sirve la página HTML para los gráficos de comparación."""
    top_n = request.args.get('topN', 5, type=int) # Default a 5
    valid_types = {
        "usage": "CPU/RAM Usage",
        "size": "Size (RW)",
        "uptime": "Uptime"
    }
    if compare_type not in valid_types:
        return "Invalid comparison type", 404

    title = valid_types[compare_type]
    print(f"DEBUG COMPARE PAGE: Sirviendo página de comparación para '{title}' (Top {top_n})")
    return render_template('compare.html', compare_type=compare_type, top_n=top_n, title=title)

# --- Ruta API para datos de comparación ---
@main_routes.route('/api/compare/<compare_type>')
def api_compare_data(compare_type):
    """Endpoint API para obtener datos para los gráficos de comparación."""
    print(f"DEBUG COMPARE API: Petición recibida para /api/compare/{compare_type}")
    try:
        client = get_docker_client()
        get_api_client() # Verificar inicialización
    except RuntimeError as e:
         print(f"ERROR API: /api/compare llamado pero el cliente Docker no está inicializado: {e}")
         return jsonify({"error": "Docker client not initialized"}), 500

    try:
        top_n = int(request.args.get('topN', 5)) # Default a 5
        if top_n <= 0: top_n = 5 # Asegurar valor positivo
    except ValueError:
        top_n = 5

    valid_types = ["usage", "size", "uptime"]
    if compare_type not in valid_types:
        return jsonify({"error": "Invalid comparison type"}), 400

    # --- Lógica similar a /api/metrics para obtener datos actuales ---
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
                ts, cpu, mem, status_hist, name_hist, net_rx, net_tx, blk_r, blk_w = latest_sample
                cpu = float(cpu) if cpu is not None else None
                mem = float(mem) if cpu is not None else None
            except (ValueError, IndexError, TypeError): continue
        else: continue

        container_name = name_hist
        size_rw_mb = None
        size_rootfs_mb = None
        uptime_sec = None
        formatted_uptime = "N/A"
        current_status = status_hist

        # Obtener detalles adicionales necesarios para size y uptime
        if compare_type in ["size", "uptime"]:
            try:
                container = client.containers.get(cid)
                current_status = container.status # Actualizar estado
                attrs = container.attrs or {}
                state = attrs.get('State', {})

                # Tamaño RW: usar inspect con size=True para obtener SizeRw
                try:
                    inspect_data = client.api.inspect_container(cid, size=True)
                    size_rw_bytes = inspect_data.get('SizeRw')
                    size_rw_mb = round(size_rw_bytes / (1024*1024), 2) if size_rw_bytes is not None else None
                    # Add total filesystem size (layers + RW)
                    size_rootfs_bytes = inspect_data.get('SizeRootFs')
                    size_rootfs_mb = round(size_rootfs_bytes / (1024*1024), 2) if size_rootfs_bytes is not None else None
                except Exception:
                    size_rw_mb = None
                    size_rootfs_mb = None

                # Uptime
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
                # Contenedor no existe, no se puede obtener size/uptime
                size_rw_mb = None
                size_rootfs_mb = None
                uptime_sec = None
                formatted_uptime = "N/A (Removed)"
                current_status = status_hist # Usar estado histórico
            except Exception as e:
                print(f"WARN COMPARE API: Error obteniendo detalles para {cid[:6]}..: {e}")
                size_rw_mb = None
                size_rootfs_mb = None
                uptime_sec = None
                formatted_uptime = "Error Fetching"
                current_status = status_hist

        # Añadir datos relevantes para la comparación
        rows.append({
            'id': cid,
            'name': container_name,
            'cpu': cpu,
            'mem': mem,
            'combined': (cpu or 0) + (mem or 0),
            'size_rw': size_rw_mb,
            'size_rootfs': size_rootfs_mb,
            'uptime_sec': uptime_sec,
            'uptime': formatted_uptime, # Incluir formateado para tooltip
            'status': current_status # Incluir estado por si acaso
        })

    # --- Ordenación específica para la comparación ---
    sort_key_map = {
        "usage": "combined",
        "size": "size_rw",
        "uptime": "uptime_sec"
    }
    sort_field = sort_key_map.get(compare_type, "combined")

    def compare_sort_key(item):
        key_value = item.get(sort_field)
        # Tratar None como -infinito para ordenar consistentemente
        return key_value if key_value is not None else float('-inf')

    try:
        rows.sort(key=compare_sort_key, reverse=True) # Siempre descendente para Top N
    except TypeError as e:
        print(f"WARN COMPARE API: Error durante ordenación (key '{sort_field}'): {e}. Usando orden por nombre.")
        rows.sort(key=lambda x: str(x.get('name', '')).lower(), reverse=False)

    # --- Limitar a Top N ---
    top_rows = rows[:top_n]

    print(f"DEBUG COMPARE API: Retornando {len(top_rows)} filas para comparación '{compare_type}'.")
    return jsonify(top_rows)