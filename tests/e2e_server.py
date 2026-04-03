import csv
import io
import json
import os
import threading
import time
from copy import deepcopy

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
TEMPLATES_DIR = os.path.join(ROOT_DIR, 'templates')
STATIC_DIR = os.path.join(ROOT_DIR, 'static')

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)
app.secret_key = 'e2e-secret'

E2E_APP_VERSION = 'test-version'
DEFAULT_PASSWORD = 'adminpass'
CURRENT_PASSWORD = DEFAULT_PASSWORD
NOTIFICATION_SETTINGS = {
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
USERS = [
    {'username': 'admin', 'columns': [], 'role': 'admin'},
    {'username': 'viewer', 'columns': ['cpu', 'ram', 'status'], 'role': 'user'},
]
NOTIFICATION_EVENTS = []
BASE_TS = int(time.time())
STREAM_CONDITION = threading.Condition()
METRICS_SEQUENCE = 0
NOTIFICATION_SEQUENCE = 0
UPDATE_HISTORY = []
UPDATE_HISTORY_COUNTER = 0
UPDATE_MANAGER_ERROR_MODE = False
UPDATE_MANAGER_FAIL_TARGETS = set()
UPDATE_HISTORY_RETENTION_DAYS = 15
UPDATE_HISTORY_RETENTION_SECONDS = UPDATE_HISTORY_RETENTION_DAYS * 24 * 60 * 60
UPDATE_HISTORY_NOTICE = f'Update history entries are removed automatically {UPDATE_HISTORY_RETENTION_DAYS} days after they are recorded.'
LOG_CONDITION = threading.Condition()
LOG_SEQUENCE = 0
LOG_EVENTS = []
EXPERIMENTAL_UPDATE_NOTICE = (
    'Experimental feature. It is designed to preserve user data, volumes, '
    'configuration, networks and environment, but every update should still '
    'be reviewed carefully before applying it.'
)


def initial_containers():
    return {
        'web1234567890': {
            'id': 'web1234567890',
            'name': 'web',
            'cpu': 72.5,
            'mem': 64.2,
            'status': 'running',
            'uptime_sec': 5400,
            'uptime': '0d 1h 30m 0s',
            'net_io_rx': 123.4,
            'net_io_tx': 45.6,
            'block_io_r': 12.3,
            'block_io_w': 9.8,
            'image': 'nginx:latest',
            'ports': '8080->80/tcp',
            'restarts': 1,
            'pid_count': 24,
            'mem_limit': 1024.0,
            'mem_usage': 657.4,
            'update_available': False,
            'current_version': 'nginx:1.25 @ web-current',
            'latest_version': 'nginx:1.25 @ web-current',
            'last_checked_at': BASE_TS - 90,
            'compose_project': 'demo',
            'compose_service': 'web',
            'gpu_max': None,
        },
        'db123456789012': {
            'id': 'db123456789012',
            'name': 'db',
            'cpu': 24.0,
            'mem': 52.0,
            'status': 'running',
            'uptime_sec': 8200,
            'uptime': '0d 2h 16m 40s',
            'net_io_rx': 87.0,
            'net_io_tx': 61.2,
            'block_io_r': 16.0,
            'block_io_w': 14.4,
            'image': 'postgres:16',
            'ports': '5432->5432/tcp',
            'restarts': 0,
            'pid_count': 18,
            'mem_limit': 2048.0,
            'mem_usage': 1102.2,
            'update_available': True,
            'current_version': 'postgres:16 @ db-old',
            'latest_version': 'postgres:17 @ db-new',
            'last_checked_at': BASE_TS - 45,
            'compose_project': 'demo',
            'compose_service': 'db',
            'gpu_max': None,
        },
        'worker12345678': {
            'id': 'worker12345678',
            'name': 'worker',
            'cpu': 0.0,
            'mem': 0.0,
            'status': 'exited',
            'uptime_sec': None,
            'uptime': 'N/A (Exited)',
            'net_io_rx': 0.0,
            'net_io_tx': 0.0,
            'block_io_r': 0.0,
            'block_io_w': 0.0,
            'image': 'python:3.12',
            'ports': 'N/A',
            'restarts': 2,
            'pid_count': 0,
            'mem_limit': 512.0,
            'mem_usage': 0.0,
            'update_available': False,
            'current_version': 'python:3.12 @ worker-current',
            'latest_version': 'python:3.12 @ worker-current',
            'last_checked_at': BASE_TS - 120,
            'compose_project': 'jobs',
            'compose_service': 'worker',
            'gpu_max': None,
        },
    }


CONTAINERS = initial_containers()


def initial_container_logs():
    return {
        'web1234567890': [
            '2026-01-01T10:00:00.000000000Z web | Listening on :80',
            '2026-01-01T10:00:10.000000000Z web | Health check passed',
            '2026-01-01T10:00:20.000000000Z web | Accepted connection from 172.18.0.10',
        ],
        'db123456789012': [
            '2026-01-01T10:00:00.000000000Z db | database system is ready to accept connections',
            '2026-01-01T10:00:15.000000000Z db | checkpoint complete',
            '2026-01-01T10:00:30.000000000Z db | autovacuum launcher started',
        ],
        'worker12345678': [
            '2026-01-01T10:00:00.000000000Z worker | worker booted',
            '2026-01-01T10:00:12.000000000Z worker | no pending jobs',
        ],
    }


CONTAINER_LOGS = initial_container_logs()


def initial_standalone_update_targets():
    return {
        'cache-standalone': {
            'id': 'cache-standalone',
            'target_id': 'cache-standalone',
            'name': 'cache',
            'type': 'container',
            'current_version': 'redis:7 @ cache-old',
            'latest_version': 'redis:7 @ cache-new',
            'update_available': True,
            'update_state': 'ready',
            'state_reason': None,
            'last_checked_at': BASE_TS - 60,
            'entries': [],
        },
        'observer-standalone': {
            'id': 'observer-standalone',
            'target_id': 'observer-standalone',
            'name': 'observer',
            'type': 'container',
            'current_version': 'ghcr.io/example/observer:2026.03.1 @ observer-current',
            'latest_version': 'ghcr.io/example/observer:2026.04.0-build.145+sha.1234567890abcdef',
            'update_available': False,
            'update_state': 'ready',
            'state_reason': None,
            'last_checked_at': BASE_TS - 30,
            'entries': [],
        },
    }


STANDALONE_UPDATE_TARGETS = initial_standalone_update_targets()


def initial_external_project_targets():
    return {
        'jobs': {
            'id': 'project:jobs',
            'target_id': 'jobs',
            'name': 'jobs',
            'type': 'project',
            'current_version': 'worker=python:3.12 @ worker-current',
            'latest_version': 'worker=python:3.13 @ worker-new',
            'update_available': True,
            'update_state': 'ready',
            'state_reason': None,
            'last_checked_at': BASE_TS - 120,
            'entries': [
                {
                    'service': 'worker',
                    'container_id': 'worker12345678',
                    'container_name': 'worker',
                    'current_version': 'python:3.12 @ worker-current',
                    'latest_version': 'python:3.13 @ worker-new',
                },
            ],
            'meta': {
                'management_mode': 'external',
                'manager_key': 'portainer',
                'manager_name': 'Portainer',
                'block_kind': 'missing_compose_files',
                'missing_files': ['/data/compose/42/docker-compose.yml'],
                'guidance': [
                    'statainer can still update the running services directly with its safe container recreation workflow, which preserves the current mounts, networks, environment, restart policy, and other materialized runtime settings from Docker.',
                    'statainer can only run project updates when it can read the original Compose files from the host filesystem.',
                    'statainer does not reconstruct Compose projects from running containers alone because Docker metadata does not preserve override merge order, env files, build contexts, secrets, configs, or services that are not currently running.',
                ],
                'action_hint': 'Compose files are unavailable, so statainer will update the running services directly.',
                'recovery_hint': 'Export the stack from Portainer or recover it from the original Git repository, then redeploy it from a host path that is mounted into statainer if you want this application to manage updates.',
                'auto_recovery_supported': True,
                'update_strategy': 'external_project_safe_recreate',
                'update_mode_label': 'External safe recreate',
            },
        },
    }


EXTERNAL_PROJECT_TARGETS = initial_external_project_targets()


def initial_auto_update_settings():
    return {
        'projects': {'jobs': True},
        'containers': {},
    }


def initial_auto_update_last_updated():
    return {
        ('project', 'jobs'): BASE_TS - 3600,
        ('container', 'cache'): BASE_TS - 7200,
    }


AUTO_UPDATE_SETTINGS = initial_auto_update_settings()
AUTO_UPDATE_LAST_UPDATED = initial_auto_update_last_updated()


def list_containers():
    return list(CONTAINERS.values())


def publish_metrics():
    global METRICS_SEQUENCE
    with STREAM_CONDITION:
        METRICS_SEQUENCE += 1
        STREAM_CONDITION.notify_all()


def publish_notification(event):
    global NOTIFICATION_SEQUENCE
    NOTIFICATION_EVENTS.append(event)
    with STREAM_CONDITION:
        NOTIFICATION_SEQUENCE += 1
        STREAM_CONDITION.notify_all()


def next_update_history_id():
    global UPDATE_HISTORY_COUNTER
    UPDATE_HISTORY_COUNTER += 1
    return UPDATE_HISTORY_COUNTER


def append_update_history(entry):
    UPDATE_HISTORY.insert(0, entry)
    return entry


def purge_expired_update_history(now_ts=None):
    effective_now = float(now_ts if now_ts is not None else time.time())
    cutoff = effective_now - UPDATE_HISTORY_RETENTION_SECONDS
    UPDATE_HISTORY[:] = [entry for entry in UPDATE_HISTORY if entry.get('created_at', 0) >= cutoff]


def publish_update_notification(target_type, target_id, target_name, ok, message):
    publish_notification({
        'type': 'update',
        'scope': 'update_success' if ok else 'update_failure',
        'timestamp': time.time(),
        'cid': target_id if target_type == 'container' else None,
        'container': target_name if target_type == 'container' else '',
        'project': target_name if target_type == 'project' else '',
        'msg': message,
    })


def publish_log(container_id, line):
    global LOG_SEQUENCE
    text = str(line or '').rstrip('\n')
    if not text:
        return
    CONTAINER_LOGS.setdefault(container_id, []).append(text)
    CONTAINER_LOGS[container_id] = CONTAINER_LOGS[container_id][-5000:]
    LOG_SEQUENCE += 1
    LOG_EVENTS.append({
        'seq': LOG_SEQUENCE,
        'container_id': container_id,
        'text': text,
    })
    if len(LOG_EVENTS) > 5000:
        del LOG_EVENTS[:-5000]
    with LOG_CONDITION:
        LOG_CONDITION.notify_all()


def auto_update_key_for_candidate(candidate):
    if str(candidate.get('type') or '').lower() == 'project':
        return str(candidate.get('target_id') or candidate.get('name') or '').strip()
    return str(candidate.get('name') or candidate.get('target_id') or '').strip()


def attach_auto_update_metadata(candidate):
    item = dict(candidate)
    target_type = 'project' if str(item.get('type') or '').lower() == 'project' else 'container'
    settings_key = 'projects' if target_type == 'project' else 'containers'
    auto_update_key = auto_update_key_for_candidate(item)
    item['auto_update_key'] = auto_update_key
    item['auto_update_enabled'] = bool(AUTO_UPDATE_SETTINGS.get(settings_key, {}).get(auto_update_key))
    item['last_updated_at'] = AUTO_UPDATE_LAST_UPDATED.get((target_type, auto_update_key))
    return item


def build_update_manager_payload():
    purge_expired_update_history()
    rollback_sources = {entry['rollback_of'] for entry in UPDATE_HISTORY if entry.get('rollback_of')}
    projects = []
    standalone = []
    grouped = {}

    for container in list_containers():
        if not container.get('update_available'):
            continue
        project = container.get('compose_project')
        if project:
            grouped.setdefault(project, []).append(container)
        else:
            standalone.append({
                'id': f"container:{container['id']}",
                'target_id': container['id'],
                'name': container['name'],
                'type': 'container',
                'current_version': container.get('current_version') or container.get('image'),
                'latest_version': container.get('latest_version') or container.get('image'),
                'update_available': True,
                'update_state': 'ready',
                'state_reason': None,
                'last_checked_at': container.get('last_checked_at') or BASE_TS,
                'entries': [],
            })

    ready_standalone_targets = [
        dict(target)
        for target in sorted(STANDALONE_UPDATE_TARGETS.values(), key=lambda item: item['name'])
        if str(target.get('update_state') or '').lower() == 'ready'
    ]
    standalone.extend([
        dict(target)
        for target in ready_standalone_targets
        if target.get('update_available')
    ])

    for project_name in sorted(grouped):
        containers = grouped[project_name]
        entries = sorted([
            {
                'service': container.get('compose_service') or container['name'],
                'container_id': container['id'],
                'current_version': container.get('current_version') or container.get('image'),
                'latest_version': container.get('latest_version') or container.get('image'),
            }
            for container in containers
        ], key=lambda item: item['service'])
        projects.append({
            'id': f'project:{project_name}',
            'target_id': project_name,
            'name': project_name,
            'type': 'project',
            'current_version': '; '.join(f"{entry['service']}={entry['current_version']}" for entry in entries),
            'latest_version': '; '.join(f"{entry['service']}={entry['latest_version']}" for entry in entries),
            'update_available': True,
            'update_state': 'ready',
            'state_reason': None,
            'last_checked_at': max(container.get('last_checked_at') or BASE_TS for container in containers),
            'entries': entries,
        })

    projects.extend([
        dict(target)
        for target in sorted(EXTERNAL_PROJECT_TARGETS.values(), key=lambda item: item['name'])
        if str(target.get('update_state') or '').lower() == 'ready'
    ])
    projects.append({
        'id': 'project:broken',
        'target_id': 'broken',
        'name': 'broken',
        'type': 'project',
        'current_version': 'api=my-api:1.0 @ api-current',
        'latest_version': 'api=my-api:1.1 @ api-new',
        'update_available': True,
        'update_state': 'blocked',
        'state_reason': 'Compose metadata is incomplete or inconsistent across services.',
        'last_checked_at': BASE_TS - 75,
        'entries': [
            {
                'service': 'api',
                'container_id': 'brokenapi123',
                'container_name': 'broken-api',
                'current_version': 'my-api:1.0 @ api-current',
                'latest_version': 'my-api:1.1 @ api-new',
            },
        ],
        'meta': {
            'management_mode': 'unknown',
            'manager_key': None,
            'manager_name': None,
            'block_kind': 'inconsistent_metadata',
            'missing_files': [],
            'guidance': [
                'statainer could not resolve one canonical Compose project directory and file set from the running services.',
            ],
            'action_hint': 'Project updates are disabled until the stack is relinked to a single Compose project on disk.',
            'recovery_hint': 'Redeploy or import the stack from one canonical Compose project directory so every service advertises the same working directory and config file set.',
            'auto_recovery_supported': False,
            'update_strategy': None,
            'update_mode_label': None,
        },
    })
    auto_update_targets = sorted(
        [
            attach_auto_update_metadata(item)
            for item in [*projects, *ready_standalone_targets]
            if str(item.get('update_state') or '').lower() == 'ready'
        ],
        key=lambda item: (0 if item.get('type') == 'project' else 1, str(item.get('name') or '').lower()),
    )
    projects = [attach_auto_update_metadata(item) for item in projects]
    standalone = [attach_auto_update_metadata(item) for item in standalone]

    history = []
    for entry in UPDATE_HISTORY:
        payload = dict(entry)
        payload['can_rollback'] = (
            payload.get('action') == 'update'
            and payload.get('result') == 'success'
            and payload.get('metadata', {}).get('rollback_ready')
            and payload['id'] not in rollback_sources
        )
        history.append(payload)

    return {
        'experimental_notice': EXPERIMENTAL_UPDATE_NOTICE,
        'history_notice': UPDATE_HISTORY_NOTICE,
        'history_retention_days': UPDATE_HISTORY_RETENTION_DAYS,
        'projects': projects,
        'containers': standalone,
        'auto_updates': auto_update_targets,
        'history': history,
    }


def sort_rows(rows, sort_by, sort_dir):
    reverse = sort_dir == 'desc'
    numeric_keys = {
        'cpu',
        'mem',
        'combined',
        'uptime_sec',
        'restarts',
        'net_io_rx',
        'net_io_tx',
        'block_io_r',
        'block_io_w',
        'pid_count',
        'mem_limit',
        'update_available',
        'gpu_max',
        'mem_usage_limit',
    }

    def key(item):
        if sort_by == 'mem_usage_limit':
            return item.get('mem') if item.get('mem') is not None else float('-inf')
        value = item.get(sort_by)
        if sort_by in numeric_keys:
            return value if value is not None else float('-inf')
        return str(value or '')

    rows.sort(key=key, reverse=reverse)
    return rows


def build_project_summaries(rows):
    buckets = {}
    for row in rows:
        project = row.get('compose_project')
        if not project:
            continue
        bucket = buckets.setdefault(project, {
            'project': project,
            'container_count': 0,
            'running_count': 0,
            'exited_count': 0,
            'other_count': 0,
            'update_count': 0,
            'restart_count': 0,
            'cpu_total': 0.0,
            'mem_usage_total': 0.0,
            'mem_limit_total': 0.0,
            'mem_avg_percent': 0.0,
            '_mem_samples': 0,
        })
        bucket['container_count'] += 1
        status = str(row.get('status') or '').lower()
        if status == 'running':
            bucket['running_count'] += 1
        elif status == 'exited':
            bucket['exited_count'] += 1
        else:
            bucket['other_count'] += 1
        if row.get('update_available') is True:
            bucket['update_count'] += 1
        bucket['restart_count'] += int(row.get('restarts') or 0)
        bucket['cpu_total'] += float(row.get('cpu') or 0)
        bucket['mem_usage_total'] += float(row.get('mem_usage') or 0)
        mem_limit = float(row.get('mem_limit') or 0)
        if mem_limit > 0:
            bucket['mem_limit_total'] += mem_limit
        mem_percent = row.get('mem')
        if mem_percent is not None:
            bucket['mem_avg_percent'] += float(mem_percent)
            bucket['_mem_samples'] += 1

    summaries = []
    for project in sorted(buckets):
        bucket = buckets[project]
        mem_avg_percent = (bucket['mem_avg_percent'] / bucket['_mem_samples']) if bucket['_mem_samples'] else 0.0
        mem_pressure_percent = (
            (bucket['mem_usage_total'] / bucket['mem_limit_total']) * 100
            if bucket['mem_limit_total'] > 0
            else None
        )
        if bucket['container_count'] and bucket['running_count'] == bucket['container_count'] and bucket['other_count'] == 0:
            status = 'healthy'
        elif bucket['running_count'] == 0 and bucket['exited_count'] == bucket['container_count']:
            status = 'stopped'
        else:
            status = 'degraded'
        summaries.append({
            'project': project,
            'container_count': bucket['container_count'],
            'running_count': bucket['running_count'],
            'exited_count': bucket['exited_count'],
            'other_count': bucket['other_count'],
            'update_count': bucket['update_count'],
            'restart_count': bucket['restart_count'],
            'cpu_total': round(bucket['cpu_total'], 2),
            'mem_usage_total': round(bucket['mem_usage_total'], 2),
            'mem_limit_total': round(bucket['mem_limit_total'], 2),
            'mem_avg_percent': round(mem_avg_percent, 2),
            'mem_pressure_percent': round(mem_pressure_percent, 2) if mem_pressure_percent is not None else None,
            'status': status,
        })
    return summaries


@app.route('/')
def index():
    return render_template(
        'index.html',
        app_version=E2E_APP_VERSION,
        csrf_token='e2e-token',
        cpu_cores=8,
        max_cpu_percent=800,
        max_ram_mb=16384,
    )


@app.route('/login', methods=['GET'])
def login():
    return render_template('login.html', app_version=E2E_APP_VERSION, csrf_token='e2e-token', error=None)


@app.route('/logout')
def logout():
    return redirect(url_for('login'))


@app.route('/whoami')
def whoami():
    return jsonify({'username': 'admin', 'role': 'admin'})


@app.route('/api/system-status')
def system_status():
    return jsonify({
        'docker': {'connected': True, 'base_url': 'unix:///var/run/docker.sock', 'error': None},
        'notifications': {
            'pushover': {'configured': True},
            'slack': {'configured': False},
            'telegram': {'configured': False},
            'discord': {'configured': False},
            'ntfy': {'configured': False},
            'webhook': {'configured': False},
        },
        'auth': {'mode': 'page', 'username': 'admin', 'role': 'admin'},
        'app': {'version': E2E_APP_VERSION, 'ephemeral_secret_key': False},
    })


@app.route('/api/projects')
def projects():
    return jsonify(sorted({container['compose_project'] for container in list_containers() if container.get('compose_project')}))


@app.route('/api/metrics')
def metrics():
    rows = deepcopy(list_containers())
    project = request.args.get('project', '').strip()
    name = request.args.get('name', '').lower().strip()
    status = request.args.get('status', '').strip()
    sort_by = request.args.get('sort', 'combined')
    sort_dir = request.args.get('dir', 'desc')
    max_items = int(request.args.get('max', 0) or 0)
    include_summary = request.args.get('summary', '0') == '1'

    for row in rows:
        row['combined'] = (row.get('cpu') or 0) + (row.get('mem') or 0)

    if project:
        rows = [row for row in rows if row.get('compose_project') == project]
    if name:
        rows = [row for row in rows if name in row['name'].lower()]
    if status:
        rows = [row for row in rows if row.get('status') == status]

    rows = sort_rows(rows, sort_by, sort_dir)
    project_summaries = build_project_summaries(rows)
    if max_items > 0:
        rows = rows[:max_items]
    if include_summary:
        return jsonify({'rows': rows, 'project_summaries': project_summaries})
    return jsonify(rows)


@app.route('/api/stream')
def stream():
    stream_interval_ms = max(1000, int(request.args.get('stream_interval', 5000) or 5000))
    last_metrics_seq = METRICS_SEQUENCE
    last_notification_seq = NOTIFICATION_SEQUENCE
    query_string = request.query_string.decode('utf-8')

    def format_event(event_name, payload):
        return f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"

    def snapshot_payload():
        with app.test_request_context(f"/api/metrics?{query_string}"):
            payload = metrics().get_json()
        if isinstance(payload, list):
            payload = {'rows': payload, 'project_summaries': build_project_summaries(payload)}
        return {**payload, 'timestamp': time.time()}

    def generate():
        nonlocal last_metrics_seq, last_notification_seq
        yield format_event('connected', {'transport': 'sse', 'version': E2E_APP_VERSION})
        yield format_event('metrics', snapshot_payload())
        if NOTIFICATION_EVENTS:
            yield format_event('notifications', {'items': list(NOTIFICATION_EVENTS)})
        last_emit = time.time()

        while True:
            with STREAM_CONDITION:
                timed_out = not STREAM_CONDITION.wait_for(
                    lambda: METRICS_SEQUENCE != last_metrics_seq or NOTIFICATION_SEQUENCE != last_notification_seq,
                    timeout=15,
                )
                metrics_seq = METRICS_SEQUENCE
                notification_seq = NOTIFICATION_SEQUENCE

            now = time.time()
            if metrics_seq != last_metrics_seq and (now - last_emit) >= (stream_interval_ms / 1000.0):
                last_metrics_seq = metrics_seq
                last_emit = now
                yield format_event('metrics', snapshot_payload())

            if notification_seq != last_notification_seq:
                last_notification_seq = notification_seq
                yield format_event('notifications', {'items': list(NOTIFICATION_EVENTS)})

            if timed_out:
                yield format_event('heartbeat', {'timestamp': now})

    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/history/<container_id>')
def history(container_id):
    if container_id not in CONTAINERS:
        return jsonify({'error': 'Not found'}), 404
    base = BASE_TS - 300
    cpu_values = [15, 22, 28, 35, 30, 25]
    mem_values = [40, 43, 45, 46, 48, 50]
    if container_id.startswith('db'):
        cpu_values = [18, 24, 26, 24, 22, 20]
        mem_values = [50, 51, 52, 53, 52, 52]
    if container_id.startswith('worker'):
        cpu_values = [0, 0, 0, 0, 0, 0]
        mem_values = [0, 0, 0, 0, 0, 0]
    return jsonify({
        'container_id': container_id,
        'range_seconds': int(request.args.get('range', 300)),
        'timestamps': [base + i * 60 for i in range(6)],
        'cpu_usage': cpu_values,
        'ram_usage': mem_values,
    })


@app.route('/api/compare/<compare_type>')
def compare(compare_type):
    top_n = max(1, int(request.args.get('topN', 5) or 5))
    valid_types = {'cpu', 'ram', 'uptime'}
    if compare_type not in valid_types:
        return jsonify({'error': 'Invalid comparison type'}), 400

    rows = []
    for container in list_containers():
        if compare_type == 'cpu':
            metric_value = container.get('cpu')
        elif compare_type == 'ram':
            metric_value = container.get('mem')
        else:
            metric_value = container.get('uptime_sec')
        rows.append({
            'id': container['id'],
            'name': container['name'],
            'cpu': container.get('cpu'),
            'mem': container.get('mem'),
            'uptime_sec': container.get('uptime_sec'),
            'uptime': container.get('uptime'),
            'status': container.get('status'),
            '_metric_value': metric_value if metric_value is not None else float('-inf'),
        })

    rows.sort(key=lambda item: item.get('_metric_value', float('-inf')), reverse=True)
    trimmed = []
    for row in rows[:top_n]:
        item = dict(row)
        item.pop('_metric_value', None)
        trimmed.append(item)
    return jsonify(trimmed)


@app.route('/api/logs/<container_id>')
def logs_snapshot(container_id):
    if container_id not in CONTAINERS:
        return jsonify({'error': 'Container not found'}), 404

    tail = max(1, min(int(request.args.get('tail', 100) or 100), 5000))
    lines = CONTAINER_LOGS.get(container_id, [])[-tail:]
    text = '\n'.join(lines)
    if text:
        text += '\n'
    response = Response(text, mimetype='text/plain; charset=utf-8')
    if request.args.get('download', '0') == '1':
        response.headers['Content-Disposition'] = f'attachment; filename="{CONTAINERS[container_id]["name"]}-{container_id[:12]}-logs.txt"'
    return response


@app.route('/api/logs/<container_id>/stream')
def logs_stream(container_id):
    if container_id not in CONTAINERS:
        return jsonify({'error': 'Container not found'}), 404

    tail = max(1, min(int(request.args.get('tail', 100) or 100), 5000))

    def format_event(event_name, payload):
        return f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"

    def generate():
        last_sequence = LOG_SEQUENCE
        yield format_event('connected', {
            'container_id': container_id,
            'container_name': CONTAINERS[container_id]['name'],
            'tail': tail,
        })
        yield format_event('snapshot', {
            'container_id': container_id,
            'container_name': CONTAINERS[container_id]['name'],
            'tail': tail,
            'lines': CONTAINER_LOGS.get(container_id, [])[-tail:],
        })

        while True:
            with LOG_CONDITION:
                timed_out = not LOG_CONDITION.wait_for(lambda: LOG_SEQUENCE != last_sequence, timeout=15)
                current_sequence = LOG_SEQUENCE

            if current_sequence != last_sequence:
                new_events = [
                    event for event in LOG_EVENTS
                    if event['seq'] > last_sequence and event['container_id'] == container_id
                ]
                last_sequence = current_sequence
                for event in new_events:
                    yield format_event('line', {'text': event['text']})

            if timed_out:
                yield format_event('heartbeat', {'timestamp': time.time()})

    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/containers/<container_id>/<action>', methods=['POST'])
def container_action(container_id, action):
    container = CONTAINERS.get(container_id)
    if not container:
        return jsonify({'error': 'Container not found'}), 404

    if action == 'stop':
        container['status'] = 'exited'
        container['cpu'] = 0.0
        container['mem'] = 0.0
        container['uptime'] = 'N/A (Exited)'
        publish_metrics()
        return jsonify({'status': f"Container {container['name']} stopped"})
    if action == 'start':
        container['status'] = 'running'
        container['cpu'] = 12.5
        container['mem'] = 18.0
        container['uptime'] = '0d 0h 0m 5s'
        publish_metrics()
        return jsonify({'status': f"Container {container['name']} started"})
    if action == 'restart':
        container['status'] = 'running'
        container['restarts'] += 1
        container['uptime'] = '0d 0h 0m 1s'
        publish_metrics()
        return jsonify({'status': f"Container {container['name']} restarted"})
    if action == 'update':
        container['update_available'] = False
        publish_metrics()
        return Response('Pulled image\nRestarted container\n', mimetype='text/plain')
    return jsonify({'error': 'Invalid action'}), 400


@app.route('/api/export/csv', methods=['POST'])
def export_csv():
    metrics = (request.get_json(silent=True) or {}).get('metrics', [])
    output = io.StringIO()
    writer = csv.writer(output)
    if metrics:
        headers = list(metrics[0].keys())
        writer.writerow(headers)
        for row in metrics:
            writer.writerow([row.get(header) for header in headers])
    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=metrics.csv'})


@app.route('/api/notifications')
def notifications():
    since = float(request.args.get('since', 0) or 0)
    rows = [event for event in NOTIFICATION_EVENTS if event['timestamp'] > since]
    return jsonify(rows)


@app.route('/api/notification-settings', methods=['GET', 'POST'])
def notification_settings():
    if request.method == 'GET':
        return jsonify(NOTIFICATION_SETTINGS)
    payload = request.get_json(silent=True) or {}
    NOTIFICATION_SETTINGS.update(payload)
    return jsonify({'ok': True, 'settings': NOTIFICATION_SETTINGS})


@app.route('/api/notification-test', methods=['POST'])
def notification_test():
    publish_notification({
        'type': 'status',
        'timestamp': time.time(),
        'msg': 'Test notification delivered',
        'cid': 'web1234567890',
    })
    return jsonify({
        'ok': True,
        'configured_any': True,
        'successful_channels': ['pushover'],
        'channels': {
            'pushover': {'configured': True, 'ok': True, 'status_code': 200},
            'ntfy': {'configured': False, 'ok': False, 'skipped': 'missing env vars'},
            'webhook': {'configured': False, 'ok': False, 'skipped': 'missing env vars'},
        },
    })


@app.route('/api/update-manager')
def update_manager_inventory():
    if UPDATE_MANAGER_ERROR_MODE:
        return jsonify({'message': 'Unable to load update manager.'}), 500
    return jsonify(build_update_manager_payload())


@app.route('/api/update-manager/update', methods=['POST'])
def update_manager_update():
    payload = request.get_json(silent=True) or {}
    target_type = payload.get('target_type')
    target_id = payload.get('target_id')
    time.sleep(0.15)

    if target_id in UPDATE_MANAGER_FAIL_TARGETS:
        history_entry = append_update_history({
            'id': next_update_history_id(),
            'created_at': time.time(),
            'actor_username': 'admin',
            'action': 'update',
            'target_type': target_type,
            'target_id': target_id,
            'target_name': target_id,
            'previous_version': 'unknown',
            'new_version': 'unknown',
            'result': 'failure',
            'notes': f'Update failed for {target_id}.',
            'metadata': {'rollback_ready': False},
            'rollback_of': None,
        })
        publish_update_notification(target_type or 'container', target_id, target_id, False, f'Update failed for {target_id}.')
        return jsonify({
            'ok': False,
            'message': f'Update failed for {target_id}.',
            'history_entry': history_entry,
        }), 409

    if target_type == 'container' and target_id in STANDALONE_UPDATE_TARGETS:
        target = STANDALONE_UPDATE_TARGETS[target_id]
        target['current_version'] = target.get('latest_version') or target.get('current_version')
        target['update_state'] = 'success'
        target['state_reason'] = None
        target['last_checked_at'] = time.time()
        history_entry = append_update_history({
            'id': next_update_history_id(),
            'created_at': time.time(),
            'actor_username': 'admin',
            'action': 'update',
            'target_type': 'container',
            'target_id': target_id,
            'target_name': target['name'],
            'previous_version': 'redis:7 @ cache-old',
            'new_version': target['current_version'],
            'result': 'success',
            'notes': 'Standalone container updated with safe container recreation.',
            'metadata': {'rollback_ready': True, 'strategy': 'safe_container_recreate'},
            'rollback_of': None,
        })
        publish_metrics()
        publish_update_notification('container', target_id, target['name'], True, 'Container cache updated safely.')
        return jsonify({
            'ok': True,
            'message': 'Container cache updated safely.',
            'history_entry': history_entry,
        })

    if target_type == 'project' and target_id == 'demo':
        matching = [container for container in list_containers() if container.get('compose_project') == 'demo']
        previous_version = '; '.join(
            f"{container['compose_service']}={container.get('current_version') or container.get('image')}"
            for container in matching
        )
        new_version = '; '.join(
            f"{container['compose_service']}={container.get('latest_version') or container.get('image')}"
            for container in matching
        )
        for container in matching:
            container['current_version'] = container.get('latest_version') or container.get('current_version')
            container['update_available'] = False
            container['last_checked_at'] = time.time()
        history_entry = append_update_history({
            'id': next_update_history_id(),
            'created_at': time.time(),
            'actor_username': 'admin',
            'action': 'update',
            'target_type': 'project',
            'target_id': 'demo',
            'target_name': 'demo',
            'previous_version': previous_version,
            'new_version': new_version,
            'result': 'success',
            'notes': 'docker compose pull && docker compose up -d completed safely.',
            'metadata': {'rollback_ready': True},
            'rollback_of': None,
        })
        publish_metrics()
        publish_update_notification('project', 'demo', 'demo', True, 'Project demo updated with a safe compose workflow.')
        return jsonify({
            'ok': True,
            'message': 'Project demo updated with a safe compose workflow.',
            'history_entry': history_entry,
        })

    if target_type == 'project' and target_id == 'jobs':
        target = EXTERNAL_PROJECT_TARGETS.get('jobs')
        matching = [container for container in list_containers() if container.get('compose_project') == 'jobs']
        previous_version = '; '.join(
            f"{container['compose_service']}={container.get('current_version') or container.get('image')}"
            for container in matching
        )
        new_version = '; '.join(
            f"{container['compose_service']}={container.get('latest_version') or container.get('image')}"
            for container in matching
        )
        for container in matching:
            container['current_version'] = container.get('latest_version') or container.get('current_version')
            container['update_available'] = False
            container['last_checked_at'] = time.time()
        if target:
            target['current_version'] = target.get('latest_version') or target.get('current_version')
            target['update_state'] = 'success'
            target['state_reason'] = None
            target['last_checked_at'] = time.time()
            for entry in target.get('entries', []):
                entry['current_version'] = entry.get('latest_version') or entry.get('current_version')
        history_entry = append_update_history({
            'id': next_update_history_id(),
            'created_at': time.time(),
            'actor_username': 'admin',
            'action': 'update',
            'target_type': 'project',
            'target_id': 'jobs',
            'target_name': 'jobs',
            'previous_version': previous_version,
            'new_version': new_version,
            'result': 'success',
            'notes': 'Compose files were unavailable, so statainer updated the running services directly with safe container recreation.',
            'metadata': {
                'rollback_ready': True,
                'strategy': 'external_project_safe_recreate',
                'services': [
                    {
                        'service': 'worker',
                        'container_name': 'worker',
                        'previous_image_id': 'sha256:worker-current',
                    },
                ],
            },
            'rollback_of': None,
        })
        publish_metrics()
        publish_update_notification('project', 'jobs', 'jobs', True, 'Project jobs updated safely by recreating the running services without compose files.')
        return jsonify({
            'ok': True,
            'message': 'Project jobs updated safely by recreating the running services without compose files.',
            'history_entry': history_entry,
        })

    publish_update_notification(target_type or 'container', target_id or 'unknown', target_id or 'unknown', False, 'Update target not supported in the E2E mock.')
    return jsonify({'ok': False, 'message': 'Update target not supported in the E2E mock.'}), 409


@app.route('/api/update-manager/auto-update', methods=['POST'])
def update_manager_auto_update():
    payload = request.get_json(silent=True) or {}
    target_type = 'project' if str(payload.get('target_type') or '').strip().lower() == 'project' else 'container'
    target_name = str(payload.get('target_name') or '').strip()
    enabled = bool(payload.get('enabled'))
    if not target_name:
        return jsonify({'ok': False, 'message': 'target_type and target_name are required.'}), 400

    eligible_targets = {
        (str(item.get('type') or '').lower(), str(item.get('auto_update_key') or '').strip()): item
        for item in build_update_manager_payload().get('auto_updates', [])
    }
    selected = eligible_targets.get((target_type, target_name))
    if not selected:
        return jsonify({
            'ok': False,
            'message': f'{target_type.title()} "{target_name}" does not currently support auto-updates.',
        }), 409

    settings_key = 'projects' if target_type == 'project' else 'containers'
    if enabled:
        AUTO_UPDATE_SETTINGS[settings_key][target_name] = True
    else:
        AUTO_UPDATE_SETTINGS[settings_key].pop(target_name, None)

    item = attach_auto_update_metadata(selected)
    state_label = 'enabled' if item['auto_update_enabled'] else 'disabled'
    return jsonify({
        'ok': True,
        'item': item,
        'message': f'Auto-update {state_label} for {target_type} "{item["name"]}".',
    })


@app.route('/api/update-manager/rollback', methods=['POST'])
def update_manager_rollback():
    payload = request.get_json(silent=True) or {}
    history_id = int(payload.get('history_id', 0) or 0)
    source = next((entry for entry in UPDATE_HISTORY if entry['id'] == history_id), None)
    time.sleep(0.15)

    if not source:
        return jsonify({'ok': False, 'message': 'Update history entry not found.'}), 404

    if source.get('target_type') == 'project' and source.get('target_name') == 'demo':
        matching = [container for container in list_containers() if container.get('compose_project') == 'demo']
        for container in matching:
            service = container.get('compose_service')
            if service == 'db':
                container['current_version'] = 'postgres:16 @ db-old'
                container['latest_version'] = 'postgres:17 @ db-new'
            else:
                container['current_version'] = 'nginx:1.25 @ web-old'
                container['latest_version'] = 'nginx:1.25 @ web-new'
            container['update_available'] = True
            container['last_checked_at'] = time.time()
        history_entry = append_update_history({
            'id': next_update_history_id(),
            'created_at': time.time(),
            'actor_username': 'admin',
            'action': 'rollback',
            'target_type': 'project',
            'target_id': 'demo',
            'target_name': 'demo',
            'previous_version': source.get('new_version'),
            'new_version': source.get('previous_version'),
            'result': 'success',
            'notes': 'Rollback completed using the recorded previous image versions.',
            'metadata': {'rollback_ready': False},
            'rollback_of': history_id,
        })
        publish_metrics()
        return jsonify({
            'ok': True,
            'message': 'Rollback completed.',
            'history_entry': history_entry,
        })

    if source.get('target_type') == 'project' and source.get('target_name') == 'jobs':
        target = EXTERNAL_PROJECT_TARGETS.get('jobs')
        matching = [container for container in list_containers() if container.get('compose_project') == 'jobs']
        for container in matching:
            container['current_version'] = 'python:3.12 @ worker-current'
            container['latest_version'] = 'python:3.13 @ worker-new'
            container['update_available'] = True
            container['last_checked_at'] = time.time()
        if target:
            target['current_version'] = 'worker=python:3.12 @ worker-current'
            target['latest_version'] = 'worker=python:3.13 @ worker-new'
            target['update_state'] = 'ready'
            target['state_reason'] = None
            target['last_checked_at'] = time.time()
            for entry in target.get('entries', []):
                entry['current_version'] = 'python:3.12 @ worker-current'
                entry['latest_version'] = 'python:3.13 @ worker-new'
        history_entry = append_update_history({
            'id': next_update_history_id(),
            'created_at': time.time(),
            'actor_username': 'admin',
            'action': 'rollback',
            'target_type': 'project',
            'target_id': 'jobs',
            'target_name': 'jobs',
            'previous_version': source.get('new_version'),
            'new_version': source.get('previous_version'),
            'result': 'success',
            'notes': 'Rollback completed using safe container recreation.',
            'metadata': {'rollback_ready': False},
            'rollback_of': history_id,
        })
        publish_metrics()
        return jsonify({
            'ok': True,
            'message': 'Rollback completed.',
            'history_entry': history_entry,
        })

    return jsonify({'ok': False, 'message': 'Rollback target not supported in the E2E mock.'}), 409
    return jsonify({
        'ok': True,
        'configured_any': True,
        'successful_channels': ['pushover'],
        'channels': {
            'pushover': {'configured': True, 'ok': True, 'status_code': 200},
            'ntfy': {'configured': False, 'ok': False, 'skipped': 'missing env vars'},
            'webhook': {'configured': False, 'ok': False, 'skipped': 'missing env vars'},
        },
    })


@app.route('/api/change-password', methods=['POST'])
def change_password():
    global CURRENT_PASSWORD
    payload = request.get_json(silent=True) or {}
    if payload.get('current_password') != CURRENT_PASSWORD:
        return jsonify({'ok': False, 'error': 'Current password is incorrect.'}), 403
    CURRENT_PASSWORD = payload.get('new_password', CURRENT_PASSWORD)
    return jsonify({'ok': True})


@app.route('/api/users', methods=['GET', 'POST'])
def users():
    if request.method == 'GET':
        return jsonify(USERS)

    payload = request.get_json(silent=True) or {}
    username = payload.get('username', '').strip()
    if not username:
        return jsonify({'error': 'Missing username'}), 400
    if any(user['username'] == username for user in USERS):
        return jsonify({'error': 'User already exists'}), 409
    USERS.append({
        'username': username,
        'columns': payload.get('columns', []),
        'role': 'user',
    })
    return jsonify({'ok': True})


@app.route('/api/users/<username>', methods=['PUT', 'DELETE'])
def user_detail(username):
    user = next((user for user in USERS if user['username'] == username), None)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if request.method == 'DELETE':
        USERS.remove(user)
        return jsonify({'ok': True})
    payload = request.get_json(silent=True) or {}
    user['columns'] = payload.get('columns', user['columns'])
    return jsonify({'ok': True})


@app.route('/api/test/reset', methods=['POST'])
def test_reset():
    global CURRENT_PASSWORD, METRICS_SEQUENCE, NOTIFICATION_SEQUENCE, UPDATE_HISTORY_COUNTER, UPDATE_MANAGER_ERROR_MODE, LOG_SEQUENCE
    CURRENT_PASSWORD = DEFAULT_PASSWORD
    NOTIFICATION_SETTINGS.clear()
    NOTIFICATION_SETTINGS.update({
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
    })
    NOTIFICATION_EVENTS.clear()
    UPDATE_HISTORY.clear()
    UPDATE_HISTORY_COUNTER = 0
    UPDATE_MANAGER_ERROR_MODE = False
    UPDATE_MANAGER_FAIL_TARGETS.clear()
    LOG_EVENTS.clear()
    LOG_SEQUENCE = 0
    USERS.clear()
    USERS.extend([
        {'username': 'admin', 'columns': [], 'role': 'admin'},
        {'username': 'viewer', 'columns': ['cpu', 'ram', 'status'], 'role': 'user'},
    ])
    CONTAINERS.clear()
    CONTAINERS.update(initial_containers())
    STANDALONE_UPDATE_TARGETS.clear()
    STANDALONE_UPDATE_TARGETS.update(initial_standalone_update_targets())
    EXTERNAL_PROJECT_TARGETS.clear()
    EXTERNAL_PROJECT_TARGETS.update(initial_external_project_targets())
    AUTO_UPDATE_SETTINGS.clear()
    AUTO_UPDATE_SETTINGS.update(initial_auto_update_settings())
    AUTO_UPDATE_LAST_UPDATED.clear()
    AUTO_UPDATE_LAST_UPDATED.update(initial_auto_update_last_updated())
    CONTAINER_LOGS.clear()
    CONTAINER_LOGS.update(initial_container_logs())
    with STREAM_CONDITION:
        METRICS_SEQUENCE += 1
        NOTIFICATION_SEQUENCE = 0
        STREAM_CONDITION.notify_all()
    with LOG_CONDITION:
        LOG_CONDITION.notify_all()
    return jsonify({'ok': True})


@app.route('/api/test/update-manager/error-mode', methods=['POST'])
def test_update_manager_error_mode():
    global UPDATE_MANAGER_ERROR_MODE
    payload = request.get_json(silent=True) or {}
    UPDATE_MANAGER_ERROR_MODE = bool(payload.get('enabled'))
    return jsonify({'ok': True, 'enabled': UPDATE_MANAGER_ERROR_MODE})


@app.route('/api/test/update-manager/fail-target', methods=['POST'])
def test_update_manager_fail_target():
    payload = request.get_json(silent=True) or {}
    target_id = str(payload.get('target_id') or '').strip()
    enabled = bool(payload.get('enabled'))
    if not target_id:
        return jsonify({'error': 'target_id is required'}), 400
    if enabled:
        UPDATE_MANAGER_FAIL_TARGETS.add(target_id)
    else:
        UPDATE_MANAGER_FAIL_TARGETS.discard(target_id)
    return jsonify({'ok': True, 'target_id': target_id, 'enabled': enabled})


@app.route('/api/test/update-history/add', methods=['POST'])
def test_add_update_history():
    payload = request.get_json(silent=True) or {}
    age_days = float(payload.get('age_days', 0) or 0)
    created_at = time.time() - (age_days * 24 * 60 * 60)
    entry = append_update_history({
        'id': next_update_history_id(),
        'created_at': created_at,
        'actor_username': 'admin',
        'action': payload.get('action', 'update'),
        'target_type': payload.get('target_type', 'container'),
        'target_id': payload.get('target_id', f'history-{UPDATE_HISTORY_COUNTER}'),
        'target_name': payload.get('target_name', 'history item'),
        'previous_version': payload.get('previous_version', 'old'),
        'new_version': payload.get('new_version', 'new'),
        'result': payload.get('result', 'success'),
        'notes': payload.get('notes', 'Synthetic history entry for tests.'),
        'metadata': payload.get('metadata', {'rollback_ready': False}),
        'rollback_of': payload.get('rollback_of'),
    })
    return jsonify({'ok': True, 'entry': entry})


@app.route('/api/test/logs/<container_id>/append', methods=['POST'])
def test_append_log_line(container_id):
    if container_id not in CONTAINERS:
        return jsonify({'error': 'Container not found'}), 404
    payload = request.get_json(silent=True) or {}
    line = payload.get('line')
    if not line:
        return jsonify({'error': 'line is required'}), 400
    publish_log(container_id, line)
    return jsonify({'ok': True, 'container_id': container_id, 'line': line})


@app.route('/api/test/containers/<container_id>/mutate', methods=['POST'])
def test_mutate_container(container_id):
    container = CONTAINERS.get(container_id)
    if not container:
        return jsonify({'error': 'Container not found'}), 404
    payload = request.get_json(silent=True) or {}
    container.update(payload)
    publish_metrics()
    return jsonify({'ok': True, 'container': container})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5100'))
    app.run(host='127.0.0.1', port=port, debug=False)
