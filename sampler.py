# -*- coding: utf-8 -*-

import threading
import time
import collections
import docker.errors
import logging
import subprocess, json, os, fnmatch

try:
    from pynvml import (
        nvmlDeviceGetCount,
        nvmlDeviceGetHandleByIndex,
        nvmlDeviceGetMemoryInfo,
        nvmlDeviceGetUtilizationRates,
        nvmlInit,
    )
    nvmlInit()
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
from update_notifications import build_update_available_message, build_update_result_event
from users_db import get_auto_update_settings, get_notification_settings, set_notification_settings

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
update_check_details_cache = {}
# Timestamp del último chequeo por contenedor
update_check_time = {}
# Intervalo mínimo entre chequeos automáticos (segundos)
UPDATE_CHECK_MIN_INTERVAL = 24 * 3600  # 24 horas
# Flag global para forzar chequeo inmediato en todos los contenedores
force_update_check_all = False
# Set de IDs de contenedores a forzar chequeo inmediato (tras pull manual)
force_update_check_ids = set()

# --- Notification System ---
NOTIFICATION_SETTINGS_DEFAULTS = {
    'cpu_enabled': True,
    'ram_enabled': True,
    'status_enabled': True,
    'update_enabled': True,
    'security_enabled': False,
    'security_privileged_enabled': False,
    'security_public_ports_enabled': False,
    'security_latest_enabled': False,
    'security_docker_socket_enabled': False,
    'cpu_threshold': 80.0,
    'ram_threshold': 80.0,
    'window_seconds': 10,
    'cooldown_seconds': 0,
    'project_rule_mode': 'all',
    'project_rules': '',
    'container_rule_mode': 'all',
    'container_rules': '',
    'silence_enabled': False,
    'silence_start': '22:00',
    'silence_end': '07:00',
    'dedupe_enabled': True,
    'dedupe_window_seconds': 120,
}

notifications = collections.deque(maxlen=500)  # Store recent notification events
auto_update_in_progress = set()
auto_update_lock = threading.Lock()


def _to_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(value)


def _to_int(value, default=0, minimum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    return parsed


def _to_float(value, default=0.0, minimum=None, maximum=None):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _normalize_rule_mode(value):
    normalized = str(value or '').strip().lower()
    if normalized in {'all', 'include', 'exclude'}:
        return normalized
    return 'all'


def _normalize_time_value(value, default):
    raw = str(value or '').strip()
    try:
        hour_text, minute_text = raw.split(':', 1)
        hour = int(hour_text)
        minute = int(minute_text)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f'{hour:02d}:{minute:02d}'
    except (ValueError, AttributeError):
        pass
    return default


def _normalize_rule_text(value):
    if value is None:
        return ''
    if isinstance(value, (list, tuple, set)):
        tokens = []
        for entry in value:
            tokens.extend(str(entry).replace(',', '\n').splitlines())
    else:
        tokens = str(value).replace(',', '\n').splitlines()
    cleaned = [token.strip() for token in tokens if token.strip()]
    return '\n'.join(cleaned)


def normalize_notification_settings(settings=None):
    raw = settings or {}
    normalized = dict(NOTIFICATION_SETTINGS_DEFAULTS)
    normalized['cpu_enabled'] = _to_bool(raw.get('cpu_enabled'), normalized['cpu_enabled'])
    normalized['ram_enabled'] = _to_bool(raw.get('ram_enabled'), normalized['ram_enabled'])
    normalized['status_enabled'] = _to_bool(raw.get('status_enabled'), normalized['status_enabled'])
    normalized['update_enabled'] = _to_bool(raw.get('update_enabled'), normalized['update_enabled'])
    normalized['security_enabled'] = _to_bool(raw.get('security_enabled'), normalized['security_enabled'])
    normalized['security_privileged_enabled'] = _to_bool(raw.get('security_privileged_enabled'), normalized['security_privileged_enabled'])
    normalized['security_public_ports_enabled'] = _to_bool(raw.get('security_public_ports_enabled'), normalized['security_public_ports_enabled'])
    normalized['security_latest_enabled'] = _to_bool(raw.get('security_latest_enabled'), normalized['security_latest_enabled'])
    normalized['security_docker_socket_enabled'] = _to_bool(raw.get('security_docker_socket_enabled'), normalized['security_docker_socket_enabled'])
    normalized['cpu_threshold'] = _to_float(raw.get('cpu_threshold'), normalized['cpu_threshold'], minimum=0.0, maximum=100.0)
    normalized['ram_threshold'] = _to_float(raw.get('ram_threshold'), normalized['ram_threshold'], minimum=0.0, maximum=100.0)
    normalized['window_seconds'] = _to_int(raw.get('window_seconds'), normalized['window_seconds'], minimum=1)
    normalized['cooldown_seconds'] = _to_int(raw.get('cooldown_seconds'), normalized['cooldown_seconds'], minimum=0)
    normalized['project_rule_mode'] = _normalize_rule_mode(raw.get('project_rule_mode'))
    normalized['project_rules'] = _normalize_rule_text(raw.get('project_rules'))
    normalized['container_rule_mode'] = _normalize_rule_mode(raw.get('container_rule_mode'))
    normalized['container_rules'] = _normalize_rule_text(raw.get('container_rules'))
    normalized['silence_enabled'] = _to_bool(raw.get('silence_enabled'), normalized['silence_enabled'])
    normalized['silence_start'] = _normalize_time_value(raw.get('silence_start'), normalized['silence_start'])
    normalized['silence_end'] = _normalize_time_value(raw.get('silence_end'), normalized['silence_end'])
    normalized['dedupe_enabled'] = _to_bool(raw.get('dedupe_enabled'), normalized['dedupe_enabled'])
    normalized['dedupe_window_seconds'] = _to_int(raw.get('dedupe_window_seconds'), normalized['dedupe_window_seconds'], minimum=0)
    return normalized


notification_settings = normalize_notification_settings(get_notification_settings(NOTIFICATION_SETTINGS_DEFAULTS))

# Track when each container last exceeded threshold
cpu_exceed_start = {}
ram_exceed_start = {}
recent_notification_cooldowns = {}
recent_notification_dedupes = {}
previous_security_findings = {}

stream_condition = threading.Condition()
metrics_sequence = 0
notification_sequence = 0

# Asegura que los clientes se obtienen después de la inicialización
client = None
api_client = None


def apply_notification_settings(new_settings):
    normalized = normalize_notification_settings(new_settings)
    notification_settings.clear()
    notification_settings.update(normalized)
    recent_notification_cooldowns.clear()
    recent_notification_dedupes.clear()
    previous_security_findings.clear()
    set_notification_settings(notification_settings)
    return dict(notification_settings)


def _rule_patterns(raw_value):
    return [token.strip().lower() for token in _normalize_rule_text(raw_value).splitlines() if token.strip()]


def _matches_patterns(value, patterns):
    normalized_value = str(value or '').strip().lower()
    if not normalized_value:
        return False
    return any(fnmatch.fnmatch(normalized_value, pattern) for pattern in patterns)


def _is_silence_window_active(settings, timestamp):
    if not settings.get('silence_enabled'):
        return False

    start_text = settings.get('silence_start', NOTIFICATION_SETTINGS_DEFAULTS['silence_start'])
    end_text = settings.get('silence_end', NOTIFICATION_SETTINGS_DEFAULTS['silence_end'])
    start_hour, start_minute = map(int, start_text.split(':'))
    end_hour, end_minute = map(int, end_text.split(':'))
    start_minutes = start_hour * 60 + start_minute
    end_minutes = end_hour * 60 + end_minute

    if start_minutes == end_minutes:
        return False

    local_time = time.localtime(timestamp)
    current_minutes = local_time.tm_hour * 60 + local_time.tm_min
    if start_minutes < end_minutes:
        return start_minutes <= current_minutes < end_minutes
    return current_minutes >= start_minutes or current_minutes < end_minutes


def _passes_notification_scope_rules(event, settings):
    project_patterns = _rule_patterns(settings.get('project_rules'))
    project_mode = settings.get('project_rule_mode', 'all')
    project_value = event.get('project')
    if project_mode == 'include' and project_patterns and not _matches_patterns(project_value, project_patterns):
        return False
    if project_mode == 'exclude' and project_patterns and _matches_patterns(project_value, project_patterns):
        return False

    container_patterns = _rule_patterns(settings.get('container_rules'))
    container_mode = settings.get('container_rule_mode', 'all')
    container_value = event.get('container')
    if container_mode == 'include' and container_patterns and not _matches_patterns(container_value, container_patterns):
        return False
    if container_mode == 'exclude' and container_patterns and _matches_patterns(container_value, container_patterns):
        return False
    return True


def _cleanup_notification_runtime(now_ts, max_age):
    expiry_cutoff = now_ts - max(max_age, 0) - 60
    for state_map in (recent_notification_cooldowns, recent_notification_dedupes):
        for key, ts in list(state_map.items()):
            if ts < expiry_cutoff:
                state_map.pop(key, None)


def _repo_name_from_image_ref(image_ref):
    normalized = str(image_ref or '').strip()
    if '@' in normalized:
        return normalized.split('@', 1)[0]
    last_segment = normalized.rsplit('/', 1)[-1]
    if ':' in last_segment:
        return normalized.rsplit(':', 1)[0]
    return normalized


def _local_digest_for_image(image, image_ref):
    if image is None:
        return None
    try:
        repo_digests = image.attrs.get('RepoDigests', []) or []
    except Exception:
        repo_digests = []

    repo_name = _repo_name_from_image_ref(image_ref)
    for digest_ref in repo_digests:
        if digest_ref.startswith(f'{repo_name}@'):
            return digest_ref.split('@', 1)[1]
    if repo_digests:
        first_digest = repo_digests[0]
        return first_digest.split('@', 1)[1] if '@' in first_digest else first_digest
    image_id = getattr(image, 'id', None)
    return image_id.split(':', 1)[1] if isinstance(image_id, str) and ':' in image_id else image_id


def _format_version(image_ref, token, *, pending_label='pending'):
    if token:
        return f'{image_ref} @ {str(token)[:12]}'
    if image_ref:
        return f'{image_ref} @ {pending_label}'
    return 'Unknown image'


def should_emit_notification(event, settings=None):
    effective_settings = normalize_notification_settings(settings or notification_settings)
    event_timestamp = float(event.get('timestamp') or time.time())

    if not _passes_notification_scope_rules(event, effective_settings):
        return False
    if _is_silence_window_active(effective_settings, event_timestamp):
        return False

    event_type = str(event.get('type') or '').lower()
    event_container_id = str(event.get('cid') or event.get('container') or '')
    scope_suffix = str(event.get('scope') or event.get('finding') or '').strip().lower()
    base_signature = f'{event_type}:{event_container_id}:{scope_suffix}'
    cooldown_seconds = int(effective_settings.get('cooldown_seconds', 0) or 0)
    if cooldown_seconds > 0:
        last_cooldown_ts = recent_notification_cooldowns.get(base_signature)
        if last_cooldown_ts and (event_timestamp - last_cooldown_ts) < cooldown_seconds:
            return False

    dedupe_window_seconds = int(effective_settings.get('dedupe_window_seconds', 0) or 0)
    dedupe_signature = f"{base_signature}:{event.get('msg', '')}"
    if effective_settings.get('dedupe_enabled') and dedupe_window_seconds > 0:
        last_dedupe_ts = recent_notification_dedupes.get(dedupe_signature)
        if last_dedupe_ts and (event_timestamp - last_dedupe_ts) < dedupe_window_seconds:
            return False

    if cooldown_seconds > 0:
        recent_notification_cooldowns[base_signature] = event_timestamp
    if effective_settings.get('dedupe_enabled') and dedupe_window_seconds > 0:
        recent_notification_dedupes[dedupe_signature] = event_timestamp
    _cleanup_notification_runtime(event_timestamp, max(cooldown_seconds, dedupe_window_seconds))
    return True


def emit_notification(event):
    if not should_emit_notification(event):
        return False
    publish_notification(event)
    dispatch_external_notification(event)
    return True


def extract_compose_project(container):
    try:
        labels = container.attrs.get('Config', {}).get('Labels', {}) or {}
    except Exception:
        labels = {}
    return labels.get('com.docker.compose.project')


def _container_image_ref(container):
    try:
        config = container.attrs.get('Config', {}) or {}
    except Exception:
        config = {}
    image_ref = str(config.get('Image') or '').strip()
    if image_ref:
        return image_ref
    tags = getattr(getattr(container, 'image', None), 'tags', None) or []
    return str(tags[0]).strip() if tags else ''


def _uses_latest_image_tag(image_ref):
    normalized = str(image_ref or '').strip()
    if not normalized or '@sha256:' in normalized:
        return False
    image_name = normalized.rsplit('/', 1)[-1]
    if ':' not in image_name:
        return True
    return image_name.rsplit(':', 1)[1].strip().lower() == 'latest'


def _collect_public_port_bindings(container):
    try:
        ports = container.attrs.get('NetworkSettings', {}).get('Ports', {}) or {}
    except Exception:
        ports = {}

    bindings = []
    for container_port, host_bindings in ports.items():
        if not host_bindings:
            continue
        if isinstance(host_bindings, dict):
            host_bindings = [host_bindings]
        for binding in host_bindings:
            if not isinstance(binding, dict):
                continue
            host_ip = str(binding.get('HostIp') or '').strip()
            host_port = str(binding.get('HostPort') or '').strip()
            if host_ip in {'', '0.0.0.0', '::', '[::]'}:
                public_host = host_ip or '0.0.0.0'
                bindings.append(f'{public_host}:{host_port}->{container_port}')
    return bindings


def _has_docker_socket_mount(container):
    try:
        mounts = container.attrs.get('Mounts', []) or []
    except Exception:
        mounts = []
    for mount in mounts:
        if not isinstance(mount, dict):
            continue
        source = str(mount.get('Source') or '').strip()
        destination = str(mount.get('Destination') or mount.get('Target') or '').strip()
        if source == '/var/run/docker.sock' or destination == '/var/run/docker.sock':
            return True
    return False


def collect_security_findings(container, settings=None):
    effective_settings = normalize_notification_settings(settings or notification_settings)
    if not effective_settings.get('security_enabled', True):
        return []

    try:
        container_id = container.id
        container_name = container.name
    except Exception:
        return []

    try:
        state = container.attrs.get('State', {}) or {}
    except Exception:
        state = {}
    runtime_status = str(
        getattr(container, 'status', None)
        or state.get('Status')
        or 'running'
    ).strip().lower()
    if runtime_status != 'running':
        return []

    timestamp = time.time()
    project = extract_compose_project(container)
    findings = []

    try:
        host_config = container.attrs.get('HostConfig', {}) or {}
    except Exception:
        host_config = {}

    if effective_settings.get('security_privileged_enabled', True) and host_config.get('Privileged'):
        findings.append({
            'type': 'security',
            'scope': 'privileged',
            'finding': 'privileged',
            'cid': container_id,
            'container': container_name,
            'project': project,
            'value': True,
            'timestamp': timestamp,
            'msg': f'{container_name}: Security warning - container is running in privileged mode',
        })

    if effective_settings.get('security_public_ports_enabled', True):
        public_bindings = _collect_public_port_bindings(container)
        if public_bindings:
            findings.append({
                'type': 'security',
                'scope': 'public_ports',
                'finding': 'public_ports',
                'cid': container_id,
                'container': container_name,
                'project': project,
                'value': public_bindings,
                'timestamp': timestamp,
                'msg': f"{container_name}: Security warning - publicly exposes {', '.join(public_bindings)}",
            })

    if effective_settings.get('security_latest_enabled', True):
        image_ref = _container_image_ref(container)
        if _uses_latest_image_tag(image_ref):
            findings.append({
                'type': 'security',
                'scope': 'latest_tag',
                'finding': 'latest_tag',
                'cid': container_id,
                'container': container_name,
                'project': project,
                'value': image_ref,
                'timestamp': timestamp,
                'msg': f'{container_name}: Security warning - image reference {image_ref} uses latest or an implicit latest tag',
            })

    if effective_settings.get('security_docker_socket_enabled', True) and _has_docker_socket_mount(container):
        findings.append({
            'type': 'security',
            'scope': 'docker_socket',
            'finding': 'docker_socket',
            'cid': container_id,
            'container': container_name,
            'project': project,
            'value': '/var/run/docker.sock',
            'timestamp': timestamp,
            'msg': f'{container_name}: Security warning - mounts /var/run/docker.sock inside the container',
        })

    return findings


def get_new_security_notifications(container, settings=None):
    effective_settings = normalize_notification_settings(settings or notification_settings)
    container_id = getattr(container, 'id', None)
    if not container_id:
        return []

    findings = collect_security_findings(container, settings=effective_settings)
    current_ids = {finding['finding'] for finding in findings}
    previous_ids = previous_security_findings.get(container_id, set())
    previous_security_findings[container_id] = current_ids
    new_ids = current_ids - previous_ids
    return [finding for finding in findings if finding['finding'] in new_ids]

def initialize_sampler_clients():
    """Obtiene las instancias del cliente para el sampler."""
    global client, api_client
    client = get_docker_client()
    api_client = get_api_client()


def publish_metrics_snapshot():
    global metrics_sequence
    with stream_condition:
        metrics_sequence += 1
        stream_condition.notify_all()


def publish_notification(event):
    global notification_sequence
    notifications.append(event)
    with stream_condition:
        notification_sequence += 1
        stream_condition.notify_all()


def dispatch_external_notification(event):
    """Forward a notification event to all configured outbound channels."""
    event_type = str(event.get('type') or '').lower()
    priority = 1 if event_type in {'cpu', 'ram', 'status', 'security'} else 0
    title = f"statainer {event_type.upper()}" if event_type else "statainer"
    push_notify(event.get('msg', 'statainer notification'), title=title, priority=priority, event=event)


def resolve_auto_update_target(container, settings=None):
    effective_settings = settings or {'containers': {}, 'projects': {}}
    project_name = extract_compose_project(container)
    if project_name and effective_settings.get('projects', {}).get(project_name):
        return ('project', project_name, project_name)

    container_name = str(getattr(container, 'name', '') or '').strip()
    container_id = getattr(container, 'id', None)
    if container_name and container_id and effective_settings.get('containers', {}).get(container_name):
        return ('container', container_id, container_name)
    return None


def build_update_available_event(container, details=None, timestamp=None):
    update_details = details or {}
    container_name = str(getattr(container, 'name', '') or '').strip() or 'unknown'
    return {
        'type': 'update',
        'scope': 'update_available',
        'cid': getattr(container, 'id', None),
        'container': container_name,
        'project': extract_compose_project(container),
        'target_type': 'container',
        'target_name': container_name,
        'previous_version': update_details.get('current_version'),
        'new_version': update_details.get('latest_version'),
        'timestamp': float(timestamp if timestamp is not None else time.time()),
        'msg': build_update_available_message(
            'container',
            container_name,
            previous_version=update_details.get('current_version'),
            new_version=update_details.get('latest_version'),
        ),
    }


def _run_auto_update_job(target_type, target_id, target_name, job_key):
    try:
        import update_manager

        result = update_manager.update_target(target_type, target_id, actor_username='auto-update')
        emit_notification(build_update_result_event(
            target_type,
            target_id,
            target_name,
            bool(result.get('ok')),
            history_entry=result.get('history_entry'),
            fallback_message=result.get('message'),
        ))
    except Exception as exc:
        logging.exception("Auto-update worker failed for %s %s", target_type, target_name)
        emit_notification(build_update_result_event(
            target_type,
            target_id,
            target_name,
            False,
            fallback_message=str(exc),
        ))
    finally:
        with auto_update_lock:
            auto_update_in_progress.discard(job_key)


def queue_auto_update(target_type, target_id, target_name):
    normalized_type = 'project' if str(target_type or '').strip().lower() == 'project' else 'container'
    normalized_name = str(target_name or '').strip()
    if not normalized_name or not target_id:
        return False

    job_key = (normalized_type, normalized_name)
    with auto_update_lock:
        if job_key in auto_update_in_progress:
            return False
        auto_update_in_progress.add(job_key)

    worker = threading.Thread(
        target=_run_auto_update_job,
        args=(normalized_type, target_id, normalized_name, job_key),
        daemon=True,
    )
    worker.start()
    return True


def get_metrics_sequence():
    with stream_condition:
        return metrics_sequence


def get_notification_sequence():
    with stream_condition:
        return notification_sequence


def wait_for_stream_event(last_metrics_seq, last_notification_seq, timeout=15):
    with stream_condition:
        timed_out = not stream_condition.wait_for(
            lambda: metrics_sequence != last_metrics_seq or notification_sequence != last_notification_seq,
            timeout=timeout,
        )
        return metrics_sequence, notification_sequence, timed_out


def get_update_check_details(container):
    image_ref = ''
    current_image = getattr(container, 'image', None)
    try:
        image_ref = container.attrs['Config']['Image']
    except Exception:
        image_ref = ''

    details = {
        'image_ref': image_ref,
        'current_token': None,
        'latest_token': None,
        'current_version': _format_version(image_ref, None, pending_label='local-unavailable'),
        'latest_version': _format_version(image_ref, None, pending_label='registry-pending'),
        'current_image_id': getattr(current_image, 'id', None),
        'update_available': None,
        'error': None,
    }

    try:
        if '@sha256:' in image_ref:
            logging.info(f"[UpdateCheck] Image pinned by digest ({image_ref}); skipping update check.")
            details['current_version'] = image_ref
            details['latest_version'] = image_ref
            details['error'] = 'pinned-digest-image'
            return details

        if current_image is None:
            current_image = client.images.get(image_ref)
            details['current_image_id'] = getattr(current_image, 'id', None)

        current_token = _local_digest_for_image(current_image, image_ref)
        details['current_token'] = current_token
        details['current_version'] = _format_version(image_ref, current_token, pending_label='local-unavailable')

        if not current_token:
            details['latest_version'] = _format_version(image_ref, None, pending_label='registry-unavailable')
            details['error'] = 'missing-local-digest'
            logging.warning(f"[UpdateCheck] RepoDigest not found for {image_ref}")
            return details

        remote_manifest_digest = client.images.get_registry_data(image_ref).id
        details['latest_token'] = remote_manifest_digest
        details['latest_version'] = _format_version(image_ref, remote_manifest_digest)
        details['update_available'] = current_token != remote_manifest_digest
        logging.info(f"[UpdateCheck] {image_ref} local_digest={current_token} remote_digest={remote_manifest_digest}")
        return details

    except (docker.errors.ImageNotFound, StopIteration):
        details['latest_version'] = _format_version(image_ref, None, pending_label='registry-unavailable')
        details['error'] = 'image-not-found-or-missing-digest'
        logging.warning(f"[UpdateCheck] Could not compare updates for {container.name} ({image_ref}) - image not found or missing digest.")
        return details
    except docker.errors.APIError as e:
        details['latest_version'] = _format_version(image_ref, None, pending_label='registry-unavailable')
        details['error'] = f'api-error:{e}'
        logging.warning(f"[UpdateCheck] API error while checking updates for {container.name}: {e}")
        return details
    except Exception as e:
        details['latest_version'] = _format_version(image_ref, None, pending_label='registry-unavailable')
        details['error'] = f'unexpected-error:{e}'
        logging.warning(f"[UpdateCheck] Unexpected error while checking updates for {container.name}: {e}")
        return details

def check_image_update(container):
    """
    Comprueba si hay una actualización disponible para la imagen del contenedor.
    Retorna: True si hay actualización, False si no, None si no se pudo comprobar.
    Busca el digest real de la imagen local tal como está referenciada en el registro (por ejemplo, "nginx@sha256:...").
    Así, evita problemas si hay varias imágenes locales con el mismo id pero diferentes referencias.
    """
    details = get_update_check_details(container)
    container_id = getattr(container, 'id', None)
    if container_id:
        update_check_details_cache[container_id] = details
    return details.get('update_available')

def get_gpu_usage():
    """
    Devuelve una lista de dicts [{'index':0,'gpu_util':34,'mem_used':1024,'mem_total':8192}, …]
    Requiere que el contenedor se ejecute con `--gpus all` y tenga drivers.
    Si `nvidia-smi` no está disponible se registra una advertencia y se devuelve
    una lista vacía.
    """
    if _NVML_OK:
        gpus = []
        for i in range(nvmlDeviceGetCount()):
            h = nvmlDeviceGetHandleByIndex(i)
            util = nvmlDeviceGetUtilizationRates(h)
            mem  = nvmlDeviceGetMemoryInfo(h)
            gpus.append({
                'index'    : i,
                'gpu_util' : util.gpu,
                'mem_used' : mem.used//1048576,
                'mem_total': mem.total//1048576
            })
        return gpus
    # fallback: shell out
    try:
        out = subprocess.check_output([
            'nvidia-smi',
            '--query-gpu=index,utilization.gpu,memory.used,memory.total',
            '--format=csv,noheader,nounits'
        ], text=True)
        gpus = []
        for line in out.strip().splitlines():
            idx, util, used, total = map(int, line.split(','))
            gpus.append({'index': idx, 'gpu_util': util, 'mem_used': used, 'mem_total': total})
        return gpus
    except FileNotFoundError:
        logging.warning("nvidia-smi not found")
        return []

def sample_metrics():
    """Background thread to periodically sample metrics and check for updates."""
    global history, previous_stats, update_check_cache, update_check_details_cache, update_check_time, force_update_check_all, force_update_check_ids

    time.sleep(1)
    initialize_sampler_clients()

    while True:
        containers_to_sample = []
        current_running_ids = set()
        all_container_ids = set()
        try:
            if not client or not api_client:
                logging.error("Docker clients not initialized in sample_metrics. Waiting...")
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
                for security_event in get_new_security_notifications(container):
                    emit_notification(security_event)

                if container.id not in current_running_ids:
                    # This is a non-running container, add it to history with its status
                    cid = container.id
                    container_name = container.name
                    current_status = container.status
                    container_project = extract_compose_project(container)
                    dq = history.setdefault(cid, collections.deque(maxlen=MAX_SECONDS // SAMPLE_INTERVAL))
                    
                    # Check if status has changed
                    previous_status = None
                    status_changed = False
                    
                    if dq and len(dq) > 0:
                        try:
                            previous_status = dq[-1][3]  # Status is at index 3
                            if previous_status != current_status:
                                status_changed = True
                        except (IndexError, TypeError):
                            pass
                    # If status changed or no entry in history, add new sample
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
                        # Send status change notification if it was running before
                        if status_changed and previous_status and notification_settings.get('status_enabled', True):
                            # Only notify significant changes, especially from running to another state
                            if previous_status == "running" or current_status == "running":
                                now = time.time()
                                n = {
                                    'type': 'status',
                                    'cid': cid,
                                    'container': container_name,
                                    'project': container_project,
                                    'value': current_status,
                                    'prev_value': previous_status,
                                    'timestamp': now,
                                    'msg': f"{container_name}: Status changed from {previous_status} to {current_status}"
                                }
                                emit_notification(n)
        except docker.errors.DockerException as e:
            logging.error(f"ERROR listing containers in sampler: {e}")
            time.sleep(SAMPLE_INTERVAL * 2)
            continue
        except Exception as e:
            logging.error(f"Unexpected error listing containers in sampler: {e}")
            time.sleep(SAMPLE_INTERVAL * 2)
            continue

        processed_cids = set()
        now = time.time()
        try:
            auto_update_settings = get_auto_update_settings()
        except Exception as exc:
            logging.warning("Unable to load auto-update settings: %s", exc)
            auto_update_settings = {'containers': {}, 'projects': {}}
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
                container_project = extract_compose_project(container)
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

                # --- NUEVO: Guardar mem_usage_mib en la tupla de historial ---
                # Añadir mem_usage_mib después de mem_limit_mb para mantener orden lógico
                # (time, cpu, mem_percent, status, name, net_rx, net_tx, blk_r, blk_w, update_available, pid_count, mem_limit_mb, mem_usage_mib, gpu_stats, gpu_max)

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
                dq.append((time.time(), cpu, mem_percent, status, container_name, net_rx, net_tx, blk_r, blk_w, update_available, pid_count, mem_limit_mb, mem_usage_mib, gpu_stats, gpu_max))

                # --- Notification logic ---
                now = time.time()
                # CPU notification
                if notification_settings.get('cpu_enabled', True):
                    if cpu >= notification_settings['cpu_threshold']:
                        if cid not in cpu_exceed_start:
                            cpu_exceed_start[cid] = now
                        elif now - cpu_exceed_start[cid] >= notification_settings['window_seconds']:
                            n = {
                                'type': 'cpu',
                                'cid': cid,
                                'container': container_name,
                                'project': container_project,
                                'value': cpu,
                                'timestamp': now,
                                'msg': f"{container_name}: CPU usage {cpu:.1f}% exceeded {notification_settings['cpu_threshold']}% for {notification_settings['window_seconds']}s"
                            }
                            emit_notification(n)
                    else:
                        cpu_exceed_start.pop(cid, None)
                # RAM notification
                if notification_settings.get('ram_enabled', True):
                    if mem_percent >= notification_settings['ram_threshold']:
                        if cid not in ram_exceed_start:
                            ram_exceed_start[cid] = now
                        elif now - ram_exceed_start[cid] >= notification_settings['window_seconds']:
                            n = {
                                'type': 'ram',
                                'cid': cid,
                                'container': container_name,
                                'project': container_project,
                                'value': mem_percent,
                                'timestamp': now,
                                'msg': f"{container_name}: RAM usage {mem_percent:.1f}% exceeded {notification_settings['ram_threshold']}% for {notification_settings['window_seconds']}s"
                            }
                            emit_notification(n)
                    else:
                        ram_exceed_start.pop(cid, None)

                # Send status change notification if enabled
                if status_changed and previous_status and notification_settings.get('status_enabled', True):
                    n = {
                        'type': 'status',
                        'cid': cid,
                        'container': container_name,
                        'project': container_project,
                        'value': status,
                        'prev_value': previous_status,
                        'timestamp': now,
                        'msg': f"{container_name}: Status changed from {previous_status} to {status}"
                    }
                    emit_notification(n)
                
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
                        auto_update_target = resolve_auto_update_target(container, settings=auto_update_settings)
                        if auto_update_target:
                            queue_auto_update(*auto_update_target)
                        else:
                            details = update_check_details_cache.get(cid) or {}
                            emit_notification(build_update_available_event(container, details=details, timestamp=now))

                time.sleep(0.2)  # Stagger requests to avoid throttling

            except docker.errors.NotFound:
                if cid in history: del history[cid]
                if cid in previous_stats: del previous_stats[cid]
                if cid in update_check_cache: del update_check_cache[cid]
                if cid in update_check_details_cache: del update_check_details_cache[cid]
                if cid in update_check_time: del update_check_time[cid]
                previous_security_findings.pop(cid, None)
                continue

            except Exception as e:
                logging.error(f"ERROR sampling metrics for container {cid[:12]} (Name: {container_name}): {e}")
                dq = history.setdefault(cid, collections.deque(maxlen=MAX_SECONDS // SAMPLE_INTERVAL))
                dq.append((time.time(), 0.0, 0.0, "error-sample", container_name, 0, 0, 0, 0, None, None, None, None, None))

        removed_ids_prev = set(previous_stats.keys()) - current_running_ids
        for cid_removed in removed_ids_prev:
            if cid_removed in previous_stats: del previous_stats[cid_removed]

        try:
            # Remove containers from history that don't exist anymore (not even in stopped state)
            history_ids_to_remove = set(history.keys()) - all_container_ids
            for cid_hist_removed in history_ids_to_remove:
                last_known_name = "Unknown"
                try:
                    if cid_hist_removed in history and history[cid_hist_removed]:
                        last_known_name = history[cid_hist_removed][-1][4]
                except (IndexError, TypeError): pass
                if cid_hist_removed in history: del history[cid_hist_removed]
                if cid_hist_removed in previous_stats:
                    del previous_stats[cid_hist_removed]
                if cid_hist_removed in update_check_cache:
                    del update_check_cache[cid_hist_removed]
                if cid_hist_removed in update_check_details_cache:
                    del update_check_details_cache[cid_hist_removed]
                if cid_hist_removed in update_check_time:
                    del update_check_time[cid_hist_removed]
                previous_security_findings.pop(cid_hist_removed, None)

        except docker.errors.DockerException as e:
            logging.warning(f"Docker error during history cleanup: {e}")
        except Exception as e:
            logging.warning(f"Generic error during history cleanup: {e}")

        publish_metrics_snapshot()
        time.sleep(SAMPLE_INTERVAL)
        force_update_check_all = False  # Reset global force after cycle

# API helper for notifications (to be imported in routes.py)
def get_notifications(since_ts=None, max_items=50):
    now = time.time()
    if since_ts is not None:
        return [n for n in list(notifications)[-max_items:] if n['timestamp'] > since_ts]
    return list(notifications)[-max_items:]
