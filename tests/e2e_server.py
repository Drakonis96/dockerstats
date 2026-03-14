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

DEFAULT_PASSWORD = 'adminpass'
CURRENT_PASSWORD = DEFAULT_PASSWORD
NOTIFICATION_SETTINGS = {
    'cpu_enabled': True,
    'ram_enabled': True,
    'status_enabled': True,
    'update_enabled': True,
    'cpu_threshold': 80.0,
    'ram_threshold': 80.0,
    'window_seconds': 10,
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
            'compose_project': 'jobs',
            'compose_service': 'worker',
            'gpu_max': None,
        },
    }


CONTAINERS = initial_containers()


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


@app.route('/')
def index():
    return render_template(
        'index.html',
        app_version='test-version',
        csrf_token='e2e-token',
        cpu_cores=8,
        max_cpu_percent=800,
        max_ram_mb=16384,
    )


@app.route('/login', methods=['GET'])
def login():
    return render_template('login.html', app_version='test-version', csrf_token='e2e-token', error=None)


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
        },
        'auth': {'mode': 'page', 'username': 'admin', 'role': 'admin'},
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

    for row in rows:
        row['combined'] = (row.get('cpu') or 0) + (row.get('mem') or 0)

    if project:
        rows = [row for row in rows if row.get('compose_project') == project]
    if name:
        rows = [row for row in rows if name in row['name'].lower()]
    if status:
        rows = [row for row in rows if row.get('status') == status]

    rows = sort_rows(rows, sort_by, sort_dir)
    if max_items > 0:
        rows = rows[:max_items]
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
            rows = metrics().get_json()
        return {'rows': rows, 'timestamp': time.time()}

    def generate():
        nonlocal last_metrics_seq, last_notification_seq
        yield format_event('connected', {'transport': 'sse', 'version': 'test-version'})
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
    global CURRENT_PASSWORD, METRICS_SEQUENCE, NOTIFICATION_SEQUENCE
    CURRENT_PASSWORD = DEFAULT_PASSWORD
    NOTIFICATION_SETTINGS.clear()
    NOTIFICATION_SETTINGS.update({
        'cpu_enabled': True,
        'ram_enabled': True,
        'status_enabled': True,
        'update_enabled': True,
        'cpu_threshold': 80.0,
        'ram_threshold': 80.0,
        'window_seconds': 10,
    })
    NOTIFICATION_EVENTS.clear()
    USERS.clear()
    USERS.extend([
        {'username': 'admin', 'columns': [], 'role': 'admin'},
        {'username': 'viewer', 'columns': ['cpu', 'ram', 'status'], 'role': 'user'},
    ])
    CONTAINERS.clear()
    CONTAINERS.update(initial_containers())
    with STREAM_CONDITION:
        METRICS_SEQUENCE += 1
        NOTIFICATION_SEQUENCE = 0
        STREAM_CONDITION.notify_all()
    return jsonify({'ok': True})


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
