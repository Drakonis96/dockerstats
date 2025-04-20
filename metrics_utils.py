# -*- coding: utf-8 -*-

import datetime
from dateutil import parser
import math

# --- Funciones Auxiliares ---
def parse_datetime(dt_str):
    """Parsea de forma segura varios formatos datetime tipo ISO."""
    if not dt_str or dt_str == "0001-01-01T00:00:00Z":
        return None
    try:
        # Manejar potenciales nanosegundos con los que dateutil.parser podría tener problemas
        if '.' in dt_str:
            parts = dt_str.split('.')
            fractional = parts[1].replace('Z', '') # Quitar Z si está aquí
            if len(fractional) > 6: # Mantener solo hasta 6 dígitos fraccionales (microsegundos)
                fractional = fractional[:6]
            dt_str = parts[0] + '.' + fractional
        # Manejar 'Z' para UTC que podría quedar si no hay segundos fraccionales
        if dt_str.endswith('Z'):
            dt_str = dt_str[:-1] + '+00:00' # Reemplazar Z con offset UTC
        # dateutil.parser debería manejar strings con timezone correctamente
        return parser.isoparse(dt_str)
    except Exception as e:
        # print(f"Warning: No se pudo parsear la cadena datetime '{dt_str}': {e}") # Verbosidad reducida
        return None

def format_uptime(total_seconds):
    """Formatea segundos totales en una cadena 'Xd Yh Zm Ws'."""
    if total_seconds is None or not isinstance(total_seconds, (int, float)) or total_seconds < 0:
        return "N/A"

    total_seconds = int(total_seconds) # Trabajar con enteros

    if total_seconds < 1:
        return "0d 0h 0m 0s"

    days, remainder = divmod(total_seconds, 86400) # 86400 segundos en un día
    hours, remainder = divmod(remainder, 3600)    # 3600 segundos en una hora
    minutes, seconds = divmod(remainder, 60)      # 60 segundos en un minuto

    return f"{days}d {hours}h {minutes}m {seconds}s"


def calc_cpu_percent(current_stats, prev_stats):
    """
    Calcula el porcentaje de CPU usando el delta entre estadísticas actuales y previas.
    Args:
        current_stats (dict): El diccionario de estadísticas de la lectura actual.
        prev_stats (dict): El diccionario de estadísticas de la lectura previa.
    Returns:
        float: Porcentaje de uso de CPU.
    """
    try:
        cpu_percent = 0.0
        if not isinstance(current_stats, dict) or not isinstance(prev_stats, dict):
            return 0.0 # Necesita diccionarios válidos

        # Asegurar que 'cpu_stats' existe en ambas lecturas
        if "cpu_stats" not in current_stats or "cpu_stats" not in prev_stats:
            return 0.0

        cpu_stats = current_stats["cpu_stats"]
        precpu_stats = prev_stats["cpu_stats"] # Usar estadísticas previas aquí

        # Comprobar claves esenciales de uso en ambos
        if not cpu_stats.get("cpu_usage") or not precpu_stats.get("cpu_usage") or \
           "total_usage" not in cpu_stats["cpu_usage"] or \
           "total_usage" not in precpu_stats["cpu_usage"]:
            return 0.0

        # Comprobar claves de uso del sistema (pueden faltar en algunas plataformas/versiones)
        system_cpu_usage = cpu_stats.get("system_cpu_usage")
        pre_system_cpu_usage = precpu_stats.get("system_cpu_usage")

        if system_cpu_usage is None or pre_system_cpu_usage is None:
            return 0.0 # No se puede calcular con precisión sin el uso del sistema

        # Número de CPUs (usar lectura actual)
        cpu_count = cpu_stats.get("online_cpus")
        if cpu_count is None:
            percpu_usage = cpu_stats.get("cpu_usage", {}).get("percpu_usage")
            cpu_count = len(percpu_usage) if percpu_usage else 1
        if cpu_count == 0:
             return 0.0


        # Valores de estadísticas actuales y previas
        cpu_total_usage = float(cpu_stats["cpu_usage"].get("total_usage", 0))
        precpu_total_usage = float(precpu_stats["cpu_usage"].get("total_usage", 0)) # De previas
        system_usage = float(system_cpu_usage or 0)
        pre_system_usage = float(pre_system_cpu_usage or 0) # De previas

        # Cálculo usando deltas
        cpu_delta = cpu_total_usage - precpu_total_usage
        system_delta = system_usage - pre_system_usage

        if system_delta > 0.0 and cpu_delta >= 0.0: # cpu_delta puede ser 0 o positivo
            cpu_percent = (cpu_delta / system_delta) * float(cpu_count) * 100.0

        return max(0.0, cpu_percent) # Retornar porcentaje no negativo

    except (KeyError, TypeError, ValueError, ZeroDivisionError, AttributeError) as e:
        # print(f"Warning: Error calculando porcentaje CPU: {e}") # Verbosidad reducida
        return 0.0 # Retornar 0 en cualquier error de cálculo

def calc_mem_percent_usage(d):
    """Calcula porcentaje y uso de Memoria desde las estadísticas Docker."""
    try:
        if not isinstance(d, dict): return 0.0, 0 # Asegurar que la entrada es un dict

        mem_stats = d.get("memory_stats", {})
        usage = mem_stats.get("usage") # Esto incluye caché en Linux
        limit = mem_stats.get("limit")

        if usage is None or limit is None or limit <= 0: # También comprobar limit > 0
            return 0.0, 0 # Retornar 0 porciento y 0 uso

        mem_percent = (usage / limit) * 100.0
        usage_mib = round(usage / (1024 * 1024), 2)

        # Limitar resultado 0-100
        mem_percent = max(0.0, min(mem_percent, 100.0))
        return mem_percent, usage_mib # Retorna % y Uso en MiB

    except (KeyError, TypeError, ValueError, ZeroDivisionError, AttributeError) as e:
        # print(f"Warning: Error calculando porcentaje Memoria: {e}") # Verbosidad reducida
        return 0.0, 0 # Retornar 0 en error

def calc_net_io(stats):
    """Calcula I/O de red acumulativa en MB."""
    rx_b = 0
    tx_b = 0
    try:
        if not isinstance(stats, dict): return 0, 0
        networks = stats.get('networks', {})
        if networks and isinstance(networks, dict):
             for if_name, data in networks.items():
                 if isinstance(data, dict):
                    rx_b += data.get('rx_bytes', 0)
                    tx_b += data.get('tx_bytes', 0)
        return round(rx_b / (1024*1024), 2), round(tx_b / (1024*1024), 2)
    except Exception as e:
        # print(f"Warning: Error calculando Net I/O: {e}") # Verbosidad reducida
        return 0, 0

def calc_block_io(stats):
    """Calcula I/O de bloque acumulativa en MB."""
    read_b = 0
    write_b = 0
    try:
        if not isinstance(stats, dict): return 0, 0
        blkio_stats = stats.get('blkio_stats', {})
        if blkio_stats and isinstance(blkio_stats, dict):
             io_bytes = blkio_stats.get('io_service_bytes_recursive', [])
             if io_bytes and isinstance(io_bytes, list):
                 for entry in io_bytes:
                     if isinstance(entry, dict) and 'op' in entry and 'value' in entry:
                         if entry['op'].lower() == 'read':
                             read_b += entry.get('value', 0)
                         elif entry['op'].lower() == 'write':
                             write_b += entry.get('value', 0)
        return round(read_b / (1024*1024), 2), round(write_b / (1024*1024), 2)
    except Exception as e:
        # print(f"Warning: Error calculando Block I/O: {e}") # Verbosidad reducida
        return 0, 0