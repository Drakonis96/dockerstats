# -*- coding: utf-8 -*-

import json
import logging
import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import docker.errors
from docker.types import DeviceRequest, LogConfig, Mount, Ulimit

import sampler
from docker_client import get_api_client, get_docker_client
from users_db import (
    get_update_history_entry,
    list_update_history,
    record_update_history,
)


EXPERIMENTAL_NOTICE = (
    "Experimental feature. It is designed to preserve user data, volumes, "
    "configuration, networks and environment, but every update should still "
    "be reviewed carefully before applying it."
)
UPDATE_REFRESH_MAX_WORKERS = 8
COMPOSE_RECONSTRUCTION_LIMITATION = (
    "Docker Stats does not reconstruct Compose projects from running "
    "containers alone because Docker metadata does not preserve override "
    "merge order, env files, build contexts, secrets, configs, or services "
    "that are not currently running."
)
KNOWN_EXTERNAL_COMPOSE_MANAGERS = (
    {
        'key': 'portainer',
        'name': 'Portainer',
        'path_fragments': ('/data/compose/',),
        'reason': (
            "This stack appears to be managed by Portainer. Docker labels point "
            "to compose files in Portainer's data directory, which Docker Stats "
            "cannot access directly from this host."
        ),
        'action_hint': 'Project updates are disabled here because Portainer owns the compose definition.',
        'recovery_hint': (
            "Export the stack from Portainer or recover it from the original Git "
            "repository, then redeploy it from a host path that is mounted into "
            "Docker Stats if you want this application to manage updates."
        ),
    },
    {
        'key': 'yacht',
        'name': 'Yacht',
        'path_fragments': ('/config/compose/', 'config/compose/'),
        'reason': (
            "This stack appears to be managed by Yacht. Docker labels point to "
            "compose files inside Yacht's COMPOSE_DIR, which Docker Stats "
            "cannot access directly from this host."
        ),
        'action_hint': 'Project updates are disabled here because Yacht owns the compose definition.',
        'recovery_hint': (
            "Mount Yacht's COMPOSE_DIR into Docker Stats or export the project "
            "and redeploy it from a host path accessible to this application."
        ),
    },
)


def _data_dir():
    path = os.path.join(os.path.dirname(__file__), 'data', 'update_manager')
    os.makedirs(path, exist_ok=True)
    return path


def _rollback_dir():
    path = os.path.join(_data_dir(), 'rollback_overrides')
    os.makedirs(path, exist_ok=True)
    return path


def _short_image_token(value):
    raw = str(value or '').strip()
    if raw.startswith('sha256:'):
        raw = raw.split(':', 1)[1]
    return raw[:12] if raw else 'unknown'


def _repo_name_from_image_ref(image_ref):
    normalized = str(image_ref or '').strip()
    if '@' in normalized:
        return normalized.split('@', 1)[0]
    last_segment = normalized.rsplit('/', 1)[-1]
    if ':' in last_segment:
        return normalized.rsplit(':', 1)[0]
    return normalized


def _container_image_ref(container):
    try:
        image_ref = str(container.attrs.get('Config', {}).get('Image') or '').strip()
    except Exception:
        image_ref = ''
    if image_ref:
        return image_ref
    tags = getattr(getattr(container, 'image', None), 'tags', None) or []
    return str(tags[0]).strip() if tags else ''


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
        return repo_digests[0].split('@', 1)[1] if '@' in repo_digests[0] else repo_digests[0]
    image_id = getattr(image, 'id', None)
    return image_id.split(':', 1)[1] if isinstance(image_id, str) and ':' in image_id else image_id


def _remote_digest_for_image(client, image_ref):
    if not image_ref or '@sha256:' in image_ref:
        return None
    try:
        registry_data = client.images.get_registry_data(image_ref)
        return registry_data.id
    except Exception as exc:
        logging.warning("Unable to resolve registry digest for %s: %s", image_ref, exc)
        return None


def _format_version(image_ref, token):
    if token:
        return f'{image_ref} @ {_short_image_token(token)}'
    return image_ref or 'Unknown image'


def _container_version_info(container, client):
    image_ref = _container_image_ref(container)
    current_image = getattr(container, 'image', None)
    current_token = _local_digest_for_image(current_image, image_ref)
    latest_token = _remote_digest_for_image(client, image_ref)
    return {
        'image_ref': image_ref,
        'current_token': current_token,
        'latest_token': latest_token,
        'current_version': _format_version(image_ref, current_token),
        'latest_version': _format_version(image_ref, latest_token),
        'current_image_id': getattr(current_image, 'id', None),
    }


def _container_version_info_for_list(container, client):
    cached_details = getattr(sampler, 'update_check_details_cache', {}).get(container.id)
    if not cached_details:
        return _container_version_info(container, client)

    image_ref = cached_details.get('image_ref') or _container_image_ref(container)
    current_image = getattr(container, 'image', None)
    current_token = cached_details.get('current_token') or _local_digest_for_image(current_image, image_ref)
    latest_token = cached_details.get('latest_token')
    update_available = sampler.update_check_cache.get(container.id)
    latest_version = cached_details.get('latest_version')
    if not latest_version:
        latest_version = _format_version(
            image_ref,
            latest_token or ('update-available' if update_available is True else current_token),
        )

    return {
        'image_ref': image_ref,
        'current_token': current_token,
        'latest_token': latest_token,
        'current_version': cached_details.get('current_version') or _format_version(image_ref, current_token),
        'latest_version': latest_version,
        'current_image_id': cached_details.get('current_image_id') or getattr(current_image, 'id', None),
        'error': cached_details.get('error'),
    }


def _serialize_mount(mount):
    mount_type = str(mount.get('Type') or 'volume').strip().lower()
    if mount_type == 'tmpfs':
        source = ''
    else:
        source = mount.get('Name') or mount.get('Source') or ''
    return {
        'target': mount.get('Destination') or mount.get('Target') or '',
        'source': source,
        'type': mount_type,
        'read_only': not bool(mount.get('RW', True)),
        'propagation': mount.get('Propagation'),
        'no_copy': bool(mount.get('VolumeOptions', {}).get('NoCopy', False)),
    }


def _serialize_networks(networks):
    serialized = {}
    for network_name, config in (networks or {}).items():
        aliases = list(config.get('Aliases') or [])
        serialized[network_name] = {
            'aliases': aliases,
            'ipv4_address': config.get('IPAddress') or None,
            'ipv6_address': config.get('GlobalIPv6Address') or None,
            'link_local_ips': list(config.get('LinkLocalIPv6Address', []) or []),
        }
    return serialized


def _build_snapshot(container):
    attrs = container.attrs or {}
    config = attrs.get('Config', {}) or {}
    host_config = attrs.get('HostConfig', {}) or {}
    network_settings = attrs.get('NetworkSettings', {}) or {}
    state = attrs.get('State', {}) or {}

    snapshot = {
        'name': container.name,
        'image_ref': _container_image_ref(container),
        'image_id': getattr(getattr(container, 'image', None), 'id', None),
        'was_running': str(getattr(container, 'status', None) or state.get('Status') or '').lower() == 'running',
        'config': {
            'command': config.get('Cmd'),
            'hostname': config.get('Hostname') or None,
            'user': config.get('User') or None,
            'detach': True,
            'stdin_open': bool(config.get('OpenStdin')),
            'tty': bool(config.get('Tty')),
            'ports': sorted((config.get('ExposedPorts') or {}).keys()),
            'environment': list(config.get('Env') or []),
            'volumes': sorted((config.get('Volumes') or {}).keys()),
            'entrypoint': config.get('Entrypoint'),
            'working_dir': config.get('WorkingDir') or None,
            'domainname': config.get('Domainname') or None,
            'labels': dict(config.get('Labels') or {}),
            'stop_signal': config.get('StopSignal') or None,
            'healthcheck': config.get('Healthcheck') or None,
            'stop_timeout': config.get('StopTimeout'),
            'runtime': host_config.get('Runtime') or config.get('Runtime') or None,
        },
        'host_config': {
            'auto_remove': bool(host_config.get('AutoRemove', False)),
            'blkio_weight': host_config.get('BlkioWeight'),
            'blkio_weight_device': host_config.get('BlkioWeightDevice'),
            'cap_add': list(host_config.get('CapAdd') or []),
            'cap_drop': list(host_config.get('CapDrop') or []),
            'cpu_period': host_config.get('CpuPeriod'),
            'cpu_quota': host_config.get('CpuQuota'),
            'cpu_shares': host_config.get('CpuShares'),
            'cpuset_cpus': host_config.get('CpusetCpus'),
            'cpuset_mems': host_config.get('CpusetMems'),
            'device_cgroup_rules': list(host_config.get('DeviceCgroupRules') or []),
            'device_read_bps': host_config.get('BlkioDeviceReadBps'),
            'device_read_iops': host_config.get('BlkioDeviceReadIOps'),
            'device_write_bps': host_config.get('BlkioDeviceWriteBps'),
            'device_write_iops': host_config.get('BlkioDeviceWriteIOps'),
            'devices': list(host_config.get('Devices') or []),
            'device_requests': list(host_config.get('DeviceRequests') or []),
            'dns': list(host_config.get('Dns') or []),
            'dns_opt': list(host_config.get('DnsOptions') or []),
            'dns_search': list(host_config.get('DnsSearch') or []),
            'extra_hosts': dict(host_config.get('ExtraHosts') or {}),
            'group_add': list(host_config.get('GroupAdd') or []),
            'init': host_config.get('Init'),
            'ipc_mode': host_config.get('IpcMode'),
            'links': host_config.get('Links'),
            'log_config': host_config.get('LogConfig'),
            'mem_limit': host_config.get('Memory'),
            'mem_reservation': host_config.get('MemoryReservation'),
            'mem_swappiness': host_config.get('MemorySwappiness'),
            'memswap_limit': host_config.get('MemorySwap'),
            'mounts': [_serialize_mount(mount) for mount in attrs.get('Mounts', []) or []],
            'nano_cpus': host_config.get('NanoCpus'),
            'network_mode': host_config.get('NetworkMode'),
            'oom_kill_disable': host_config.get('OomKillDisable'),
            'oom_score_adj': host_config.get('OomScoreAdj'),
            'pid_mode': host_config.get('PidMode'),
            'pids_limit': host_config.get('PidsLimit'),
            'port_bindings': host_config.get('PortBindings'),
            'privileged': bool(host_config.get('Privileged', False)),
            'publish_all_ports': bool(host_config.get('PublishAllPorts', False)),
            'read_only': bool(host_config.get('ReadonlyRootfs', False)),
            'restart_policy': host_config.get('RestartPolicy'),
            'security_opt': list(host_config.get('SecurityOpt') or []),
            'shm_size': host_config.get('ShmSize'),
            'storage_opt': host_config.get('StorageOpt'),
            'sysctls': host_config.get('Sysctls'),
            'tmpfs': host_config.get('Tmpfs'),
            'ulimits': host_config.get('Ulimits'),
            'userns_mode': host_config.get('UsernsMode'),
            'uts_mode': host_config.get('UTSMode'),
            'volumes_from': list(host_config.get('VolumesFrom') or []),
            'runtime': host_config.get('Runtime'),
        },
        'networks': _serialize_networks(network_settings.get('Networks') or {}),
    }
    return snapshot


def _mounts_from_snapshot(snapshot_mounts):
    mounts = []
    for mount in snapshot_mounts or []:
        target = mount.get('target')
        source = mount.get('source') or ''
        mount_type = mount.get('type') or 'volume'
        if not target:
            continue
        kwargs = {
            'target': target,
            'source': source,
            'type': mount_type,
            'read_only': bool(mount.get('read_only', False)),
        }
        if mount.get('propagation'):
            kwargs['propagation'] = mount['propagation']
        if mount.get('type') == 'volume':
            kwargs['no_copy'] = bool(mount.get('no_copy', False))
        mounts.append(Mount(**kwargs))
    return mounts


def _ulimits_from_snapshot(ulimits):
    return [Ulimit(**item) for item in (ulimits or []) if isinstance(item, dict)]


def _device_requests_from_snapshot(device_requests):
    return [DeviceRequest(**item) for item in (device_requests or []) if isinstance(item, dict)]


def _log_config_from_snapshot(log_config):
    if not isinstance(log_config, dict):
        return None
    if not log_config.get('Type'):
        return None
    return LogConfig(type=log_config.get('Type'), config=log_config.get('Config') or {})


def _coerce_extra_hosts(extra_hosts):
    if isinstance(extra_hosts, dict):
        return extra_hosts
    result = {}
    for item in extra_hosts or []:
        if not isinstance(item, str) or ':' not in item:
            continue
        host, ip = item.split(':', 1)
        result[host] = ip
    return result


def _host_config_kwargs(snapshot):
    host = dict(snapshot.get('host_config') or {})
    kwargs = {
        'auto_remove': host.get('auto_remove', False),
        'blkio_weight': host.get('blkio_weight'),
        'blkio_weight_device': host.get('blkio_weight_device'),
        'cap_add': host.get('cap_add') or None,
        'cap_drop': host.get('cap_drop') or None,
        'cpu_period': host.get('cpu_period'),
        'cpu_quota': host.get('cpu_quota'),
        'cpu_shares': host.get('cpu_shares'),
        'cpuset_cpus': host.get('cpuset_cpus'),
        'cpuset_mems': host.get('cpuset_mems'),
        'device_cgroup_rules': host.get('device_cgroup_rules') or None,
        'device_read_bps': host.get('device_read_bps'),
        'device_read_iops': host.get('device_read_iops'),
        'device_write_bps': host.get('device_write_bps'),
        'device_write_iops': host.get('device_write_iops'),
        'devices': host.get('devices') or None,
        'device_requests': _device_requests_from_snapshot(host.get('device_requests')),
        'dns': host.get('dns') or None,
        'dns_opt': host.get('dns_opt') or None,
        'dns_search': host.get('dns_search') or None,
        'extra_hosts': _coerce_extra_hosts(host.get('extra_hosts')),
        'group_add': host.get('group_add') or None,
        'init': host.get('init'),
        'ipc_mode': host.get('ipc_mode'),
        'links': host.get('links'),
        'log_config': _log_config_from_snapshot(host.get('log_config')),
        'mem_limit': host.get('mem_limit'),
        'mem_reservation': host.get('mem_reservation'),
        'mem_swappiness': host.get('mem_swappiness'),
        'memswap_limit': host.get('memswap_limit'),
        'mounts': _mounts_from_snapshot(host.get('mounts')),
        'nano_cpus': host.get('nano_cpus'),
        'network_mode': host.get('network_mode'),
        'oom_kill_disable': host.get('oom_kill_disable'),
        'oom_score_adj': host.get('oom_score_adj'),
        'pid_mode': host.get('pid_mode'),
        'pids_limit': host.get('pids_limit'),
        'port_bindings': host.get('port_bindings'),
        'privileged': host.get('privileged', False),
        'publish_all_ports': host.get('publish_all_ports', False),
        'read_only': host.get('read_only', False),
        'restart_policy': host.get('restart_policy'),
        'security_opt': host.get('security_opt') or None,
        'shm_size': host.get('shm_size'),
        'storage_opt': host.get('storage_opt'),
        'sysctls': host.get('sysctls'),
        'tmpfs': host.get('tmpfs'),
        'ulimits': _ulimits_from_snapshot(host.get('ulimits')),
        'userns_mode': host.get('userns_mode'),
        'uts_mode': host.get('uts_mode'),
        'volumes_from': host.get('volumes_from') or None,
        'runtime': host.get('runtime'),
    }
    return {key: value for key, value in kwargs.items() if value not in (None, [], {}, ())}


def _restore_networks(client, container_id, snapshot):
    networks = snapshot.get('networks') or {}
    host_config = snapshot.get('host_config') or {}
    primary_network = host_config.get('network_mode')
    skip_networks = {'default', 'bridge', 'nat', 'host', 'none', 'container'}

    for network_name, config in networks.items():
        if primary_network and primary_network.split(':', 1)[0] not in skip_networks and network_name == primary_network:
            continue
        if primary_network in skip_networks and network_name == 'bridge':
            continue
        try:
            network = client.networks.get(network_name)
            connect_kwargs = {}
            aliases = [alias for alias in (config.get('aliases') or []) if alias]
            if aliases:
                connect_kwargs['aliases'] = aliases
            if config.get('ipv4_address'):
                connect_kwargs['ipv4_address'] = config['ipv4_address']
            if config.get('ipv6_address'):
                connect_kwargs['ipv6_address'] = config['ipv6_address']
            if config.get('link_local_ips'):
                connect_kwargs['link_local_ips'] = config['link_local_ips']
            network.connect(container_id, **connect_kwargs)
        except docker.errors.APIError as exc:
            logging.warning("Unable to connect container %s to network %s: %s", container_id, network_name, exc)


def _create_container_from_snapshot(api_client, client, snapshot, image, start_container=True):
    host_config = api_client.create_host_config(**_host_config_kwargs(snapshot))
    config = snapshot.get('config') or {}
    created = api_client.create_container(
        image=image,
        command=config.get('command'),
        hostname=config.get('hostname'),
        user=config.get('user'),
        detach=True,
        stdin_open=config.get('stdin_open', False),
        tty=config.get('tty', False),
        ports=config.get('ports') or None,
        environment=config.get('environment') or None,
        volumes=config.get('volumes') or None,
        name=snapshot.get('name'),
        entrypoint=config.get('entrypoint'),
        working_dir=config.get('working_dir'),
        domainname=config.get('domainname'),
        host_config=host_config,
        labels=config.get('labels') or None,
        stop_signal=config.get('stop_signal'),
        healthcheck=config.get('healthcheck'),
        stop_timeout=config.get('stop_timeout'),
        runtime=config.get('runtime'),
    )
    new_container_id = created['Id']
    _restore_networks(client, new_container_id, snapshot)
    if start_container:
        api_client.start(new_container_id)
    return new_container_id


def _refresh_update_checks(container_ids):
    for container_id in container_ids:
        try:
            sampler.force_update_check_ids.add(container_id)
        except Exception:
            logging.warning("Unable to schedule update re-check for %s", container_id)


def _backup_name(base_name):
    return f'{base_name}-dockerstats-backup-{int(time.time())}'


def _rename_back(container, original_name):
    try:
        container.rename(original_name)
    except Exception as exc:
        logging.error("Unable to restore backup container name %s: %s", original_name, exc)


def _safe_remove_container(container):
    try:
        container.remove(v=False, force=False)
    except Exception as exc:
        logging.warning("Unable to remove backup container %s: %s", getattr(container, 'name', 'unknown'), exc)


def _recreate_single_container(container, target_image, actor_username=None, history_action='update', rollback_of=None):
    client = get_docker_client()
    api_client = get_api_client()
    version_info = _container_version_info(container, client)
    snapshot = _build_snapshot(container)
    original_name = snapshot['name']
    original_running_state = snapshot['was_running']
    backup_name = _backup_name(original_name)
    backup_container = container
    new_container_id = None
    notes = []

    try:
        stop_timeout = snapshot.get('config', {}).get('stop_timeout')
        if original_running_state:
            backup_container.stop(timeout=stop_timeout)
        backup_container.rename(backup_name)
        new_container_id = _create_container_from_snapshot(
            api_client,
            client,
            snapshot,
            target_image,
            start_container=original_running_state,
        )
        _safe_remove_container(backup_container)
        client.containers.get(new_container_id)
        _refresh_update_checks([new_container_id])
        return {
            'ok': True,
            'target_name': original_name,
            'previous_version': version_info['current_version'],
            'new_version': _format_version(snapshot['image_ref'], target_image),
            'result': 'success',
            'notes': '\n'.join(notes) if notes else None,
            'metadata': {
                'strategy': 'safe_container_recreate',
                'snapshot': snapshot,
                'container_name': original_name,
                'previous_image_id': version_info['current_image_id'],
                'new_image_id': target_image,
                'current_container_id': new_container_id,
            },
            'rollback_of': rollback_of,
        }
    except Exception as exc:
        logging.error("Container recreate failed for %s: %s", original_name, exc)
        notes.append(f'Update failed and the previous container was restored: {exc}')
        if new_container_id:
            try:
                client.containers.get(new_container_id).remove(v=False, force=True)
            except Exception:
                pass
        try:
            restored = client.containers.get(backup_name)
            _rename_back(restored, original_name)
            if original_running_state:
                restored.start()
        except Exception as restore_exc:
            notes.append(f'Automatic restore also failed: {restore_exc}')
        return {
            'ok': False,
            'target_name': original_name,
            'previous_version': version_info['current_version'],
            'new_version': _format_version(snapshot['image_ref'], target_image),
            'result': 'failure',
            'notes': '\n'.join(notes),
            'metadata': {
                'strategy': 'safe_container_recreate',
                'snapshot': snapshot,
                'container_name': original_name,
                'previous_image_id': version_info['current_image_id'],
                'attempted_image_id': target_image,
            },
            'rollback_of': rollback_of,
        }


def _container_candidate(container, client):
    version_info = _container_version_info_for_list(container, client)
    checked_at = sampler.update_check_time.get(container.id)
    supported, support_reason = _container_support_check(container)
    ready = supported and sampler.update_check_cache.get(container.id) is True
    return {
        'id': f'container:{container.id}',
        'target_id': container.id,
        'name': container.name,
        'type': 'container',
        'current_version': version_info['current_version'],
        'latest_version': version_info['latest_version'],
        'update_state': 'ready' if ready else 'blocked',
        'state_reason': None if ready else support_reason or 'This container cannot be updated safely with the current metadata.',
        'last_checked_at': checked_at,
        'entries': [],
        'meta': {
            'image_ref': version_info['image_ref'],
            'current_image_id': version_info['current_image_id'],
        },
    }


def _build_refresh_details(container, remote_digests):
    image_ref = _container_image_ref(container)
    current_image = getattr(container, 'image', None)
    current_token = _local_digest_for_image(current_image, image_ref)
    details = {
        'image_ref': image_ref,
        'current_token': current_token,
        'latest_token': None,
        'current_version': _format_version(image_ref, current_token),
        'latest_version': _format_version(image_ref, None),
        'current_image_id': getattr(current_image, 'id', None),
        'update_available': None,
        'error': None,
    }

    if not image_ref:
        details['error'] = 'missing-image-reference'
        return details
    if '@sha256:' in image_ref:
        details['current_version'] = image_ref
        details['latest_version'] = image_ref
        details['error'] = 'pinned-digest-image'
        return details
    if not current_token:
        details['error'] = 'missing-local-digest'
        return details

    latest_token = remote_digests.get(image_ref)
    details['latest_token'] = latest_token
    details['latest_version'] = _format_version(image_ref, latest_token)
    if not latest_token:
        details['error'] = 'registry-unavailable'
        return details

    details['update_available'] = current_token != latest_token
    return details


def _refresh_candidate_checks(containers):
    if not containers:
        return []

    client = get_docker_client()
    image_refs = sorted({
        image_ref
        for image_ref in (_container_image_ref(container) for container in containers)
        if image_ref and '@sha256:' not in image_ref
    })
    remote_digests = {}

    if image_refs:
        max_workers = min(UPDATE_REFRESH_MAX_WORKERS, len(image_refs))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(_remote_digest_for_image, client, image_ref): image_ref
                for image_ref in image_refs
            }
            for future in as_completed(future_map):
                image_ref = future_map[future]
                try:
                    remote_digests[image_ref] = future.result()
                except Exception as exc:
                    logging.warning("Unable to refresh registry digest for %s: %s", image_ref, exc)
                    remote_digests[image_ref] = None

    refreshed = []
    now = time.time()
    for container in containers:
        details = _build_refresh_details(container, remote_digests)
        result = details.get('update_available')
        sampler.update_check_details_cache[container.id] = details
        sampler.update_check_cache[container.id] = result
        sampler.update_check_time[container.id] = now
        refreshed.append((container, result))
    return refreshed


def _detect_external_compose_manager(paths):
    normalized = [str(path or '').strip() for path in (paths or []) if str(path or '').strip()]
    for manager in KNOWN_EXTERNAL_COMPOSE_MANAGERS:
        for path in normalized:
            if any(fragment in path for fragment in manager['path_fragments']):
                return manager
    return None


def _compose_blocked_metadata(
    reason,
    *,
    block_kind,
    working_dir=None,
    config_files=None,
    missing_files=None,
    manager=None,
    guidance=None,
    action_hint=None,
    recovery_hint=None,
):
    return {
        'ready': False,
        'reason': reason,
        'block_kind': block_kind,
        'management_mode': 'external' if manager else 'unknown',
        'manager_key': manager.get('key') if manager else None,
        'manager_name': manager.get('name') if manager else None,
        'working_dir': working_dir,
        'config_files': list(config_files or []),
        'missing_files': list(missing_files or []),
        'guidance': list(guidance or []),
        'action_hint': action_hint,
        'recovery_hint': recovery_hint,
        'auto_recovery_supported': False,
    }


def _compose_paths_from_labels(project_name, containers):
    working_dirs = set()
    config_files = set()
    services = set()

    for container in containers:
        labels = container.attrs.get('Config', {}).get('Labels', {}) or {}
        services.add(labels.get('com.docker.compose.service') or container.name)
        working_dir = str(labels.get('com.docker.compose.project.working_dir') or '').strip()
        config_label = str(labels.get('com.docker.compose.project.config_files') or '').strip()
        if working_dir:
            working_dirs.add(working_dir)
        if config_label:
            config_files.add(config_label)

    if len(working_dirs) != 1 or len(config_files) != 1:
        return _compose_blocked_metadata(
            'Compose metadata is incomplete or inconsistent across services.',
            block_kind='inconsistent_metadata',
            guidance=[
                (
                    "Docker Stats could not resolve one canonical Compose "
                    "project directory and file set from the running services."
                ),
                (
                    "This usually means the stack was recreated or partially "
                    "managed outside a single docker compose project."
                ),
                COMPOSE_RECONSTRUCTION_LIMITATION,
            ],
            action_hint='Project updates are disabled until the stack is relinked to a single Compose project on disk.',
            recovery_hint=(
                "Redeploy or import the stack from one canonical Compose project "
                "directory so every service advertises the same working directory "
                "and config file set."
            ),
        )

    working_dir = next(iter(working_dirs))
    raw_files = next(iter(config_files))
    files = []
    for entry in raw_files.split(','):
        entry = entry.strip()
        if not entry:
            continue
        files.append(entry if os.path.isabs(entry) else os.path.join(working_dir, entry))

    missing = [path for path in files if not os.path.exists(path)]
    if missing:
        manager = _detect_external_compose_manager([working_dir, *files, *missing])
        if manager:
            guidance = [
                (
                    "Docker Stats can only run project updates when it can read "
                    "the original Compose files from the host filesystem."
                ),
                COMPOSE_RECONSTRUCTION_LIMITATION,
            ]
            return _compose_blocked_metadata(
                manager['reason'],
                block_kind='missing_compose_files',
                working_dir=working_dir,
                config_files=files,
                missing_files=missing,
                manager=manager,
                guidance=guidance,
                action_hint=manager['action_hint'],
                recovery_hint=manager['recovery_hint'],
            )

        return _compose_blocked_metadata(
            'Compose files referenced by Docker labels are missing on this host.',
            block_kind='missing_compose_files',
            working_dir=working_dir,
            config_files=files,
            missing_files=missing,
            guidance=[
                (
                    "Docker Stats can only run project updates when the compose "
                    "files advertised by Docker labels still exist on disk."
                ),
                (
                    "This usually means the stack was deployed from another "
                    "management tool, a temporary checkout, or a path that is no "
                    "longer mounted here."
                ),
                (
                    "If you use OpenMediaVault Compose, restore or remount the "
                    "plugin's compose shared folder so the recorded project path "
                    "exists again before retrying."
                ),
                COMPOSE_RECONSTRUCTION_LIMITATION,
            ],
            action_hint='Project updates are disabled until the original Compose files are accessible on this host.',
            recovery_hint=(
                "Restore the original compose directory, remount the missing "
                "path, or redeploy/import the stack from its compose files."
            ),
        )

    return {
        'ready': True,
        'working_dir': working_dir,
        'config_files': files,
        'services': sorted(services),
        'management_mode': 'host',
        'manager_key': 'docker-compose',
        'manager_name': 'Docker Compose',
        'block_kind': None,
        'missing_files': [],
        'guidance': [],
        'action_hint': None,
        'recovery_hint': None,
        'auto_recovery_supported': False,
    }


def _project_candidate(project_name, containers, client):
    metadata = _compose_paths_from_labels(project_name, containers)
    entries = []
    checked_at = None

    for container in containers:
        version_info = _container_version_info_for_list(container, client)
        labels = container.attrs.get('Config', {}).get('Labels', {}) or {}
        service_name = labels.get('com.docker.compose.service') or container.name
        checked_value = sampler.update_check_time.get(container.id)
        if checked_value is not None:
            checked_at = checked_value if checked_at is None else max(checked_at, checked_value)
        entries.append({
            'service': service_name,
            'container_id': container.id,
            'current_version': version_info['current_version'],
            'latest_version': version_info['latest_version'],
            'image_ref': version_info['image_ref'],
            'current_image_id': version_info['current_image_id'],
        })

    return {
        'id': f'project:{project_name}',
        'target_id': project_name,
        'name': project_name,
        'type': 'project',
        'current_version': '; '.join(f"{entry['service']}={entry['current_version']}" for entry in entries),
        'latest_version': '; '.join(f"{entry['service']}={entry['latest_version']}" for entry in entries),
        'update_state': 'ready' if metadata.get('ready') else 'blocked',
        'state_reason': None if metadata.get('ready') else metadata.get('reason'),
        'last_checked_at': checked_at,
        'entries': entries,
        'meta': metadata,
    }


def _sanitize_repo_fragment(value):
    token = ''.join(ch if ch.isalnum() or ch in '-._' else '-' for ch in str(value or '').lower())
    return token.strip('-._') or 'item'


def _tag_for_rollback(client, image_id, project_name, service_name, history_id):
    repository = f"dockerstats-rollback/{_sanitize_repo_fragment(project_name)}-{_sanitize_repo_fragment(service_name)}"
    tag = f'history-{history_id}'
    image = client.images.get(image_id)
    image.tag(repository, tag=tag)
    return f'{repository}:{tag}'


def _write_override_file(project_name, service_tags, history_id):
    override_path = os.path.join(
        _rollback_dir(),
        f'{_sanitize_repo_fragment(project_name)}-history-{history_id}.override.yml',
    )
    lines = ['services:']
    for service_name, image_ref in service_tags.items():
        lines.append(f'  {service_name}:')
        lines.append(f'    image: {image_ref}')
    with open(override_path, 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')
    return override_path


def _compose_command(metadata, project_name, extra_args, override_file=None):
    command = [
        'docker',
        'compose',
        '--ansi',
        'never',
        '--project-name',
        project_name,
        '--project-directory',
        metadata['working_dir'],
    ]
    for config_file in metadata['config_files']:
        command.extend(['-f', config_file])
    if override_file:
        command.extend(['-f', override_file])
    command.extend(extra_args)
    return command


def _run_compose(metadata, project_name, extra_args, override_file=None):
    command = _compose_command(metadata, project_name, extra_args, override_file=override_file)
    return subprocess.run(
        command,
        cwd=metadata['working_dir'],
        capture_output=True,
        text=True,
        check=False,
    )


def list_update_targets(history_limit=20, force_refresh=False):
    client = get_docker_client()
    containers = client.containers.list(all=True)
    project_groups = {}
    container_items = []

    if force_refresh:
        refreshed = _refresh_candidate_checks(containers)
    else:
        refreshed = [(container, sampler.update_check_cache.get(container.id)) for container in containers]

    for container, update_available in refreshed:
        if update_available is not True:
            continue
        labels = container.attrs.get('Config', {}).get('Labels', {}) or {}
        project_name = labels.get('com.docker.compose.project')
        if project_name:
            project_groups.setdefault(project_name, []).append(container)
        else:
            container_items.append(_container_candidate(container, client))

    project_items = [
        _project_candidate(project_name, grouped_containers, client)
        for project_name, grouped_containers in sorted(project_groups.items())
    ]

    rollback_sources = {entry['rollback_of'] for entry in list_update_history(limit=history_limit * 3) if entry.get('rollback_of')}
    history_entries = []
    for entry in list_update_history(limit=history_limit):
        metadata = entry.get('metadata') or {}
        entry['can_rollback'] = (
            entry.get('action') == 'update'
            and entry.get('result') == 'success'
            and metadata.get('rollback_ready', False)
            and entry['id'] not in rollback_sources
        )
        history_entries.append(entry)

    return {
        'experimental_notice': EXPERIMENTAL_NOTICE,
        'projects': project_items,
        'containers': container_items,
        'history': history_entries,
    }


def _container_support_check(container):
    image_ref = _container_image_ref(container)
    if not image_ref:
        return False, 'Container image reference is missing.'
    if '@sha256:' in image_ref:
        return False, 'Pinned digest images are already fixed to a specific version.'
    return True, None


def update_container_target(container_id, actor_username=None):
    client = get_docker_client()
    container = client.containers.get(container_id)
    supported, reason = _container_support_check(container)
    version_info = _container_version_info(container, client)

    if not supported:
        history_id = record_update_history(
            action='update',
            target_type='container',
            target_id=container.id,
            target_name=container.name,
            previous_version=version_info['current_version'],
            new_version=version_info['latest_version'],
            result='failure',
            notes=reason,
            metadata={'rollback_ready': False, 'strategy': 'blocked_container_update'},
            actor_username=actor_username,
        )
        return {'ok': False, 'message': reason, 'history_entry': get_update_history_entry(history_id)}

    if not version_info['latest_token'] or version_info['latest_token'] == version_info['current_token']:
        message = 'No newer image digest is currently available.'
        history_id = record_update_history(
            action='update',
            target_type='container',
            target_id=container.id,
            target_name=container.name,
            previous_version=version_info['current_version'],
            new_version=version_info['latest_version'],
            result='failure',
            notes=message,
            metadata={'rollback_ready': False, 'strategy': 'safe_container_recreate'},
            actor_username=actor_username,
        )
        return {'ok': False, 'message': message, 'history_entry': get_update_history_entry(history_id)}

    client.images.pull(version_info['image_ref'])
    pulled_image = client.images.get(version_info['image_ref'])
    new_image_id = getattr(pulled_image, 'id', None)
    if not new_image_id or new_image_id == version_info['current_image_id']:
        message = 'The image pull completed, but Docker is still reporting the same local image.'
        history_id = record_update_history(
            action='update',
            target_type='container',
            target_id=container.id,
            target_name=container.name,
            previous_version=version_info['current_version'],
            new_version=version_info['latest_version'],
            result='failure',
            notes=message,
            metadata={'rollback_ready': False, 'strategy': 'safe_container_recreate'},
            actor_username=actor_username,
        )
        return {'ok': False, 'message': message, 'history_entry': get_update_history_entry(history_id)}

    result = _recreate_single_container(container, new_image_id, actor_username=actor_username)
    result['metadata']['rollback_ready'] = bool(result['ok'])
    result['metadata']['image_ref'] = version_info['image_ref']
    history_id = record_update_history(
        action='update',
        target_type='container',
        target_id=container.id,
        target_name=container.name,
        previous_version=result['previous_version'],
        new_version=result['new_version'],
        result=result['result'],
        notes=result.get('notes'),
        metadata=result['metadata'],
        actor_username=actor_username,
    )
    return {
        'ok': result['ok'],
        'message': 'Container updated safely.' if result['ok'] else result.get('notes') or 'Container update failed.',
        'history_entry': get_update_history_entry(history_id),
    }


def update_project_target(project_name, actor_username=None):
    client = get_docker_client()
    all_containers = client.containers.list(all=True)
    project_containers = []
    for container in all_containers:
        labels = container.attrs.get('Config', {}).get('Labels', {}) or {}
        if labels.get('com.docker.compose.project') == project_name and sampler.update_check_cache.get(container.id) is True:
            project_containers.append(container)

    if not project_containers:
        return {'ok': False, 'message': f'No update-ready services were found for project {project_name}.', 'history_entry': None}

    candidate = _project_candidate(project_name, project_containers, client)
    metadata = candidate.get('meta') or {}
    if not metadata.get('ready'):
        history_id = record_update_history(
            action='update',
            target_type='project',
            target_id=project_name,
            target_name=project_name,
            previous_version=candidate['current_version'],
            new_version=candidate['latest_version'],
            result='failure',
            notes=metadata.get('reason'),
            metadata={'rollback_ready': False, 'strategy': 'compose_project_update'},
            actor_username=actor_username,
        )
        return {'ok': False, 'message': metadata.get('reason'), 'history_entry': get_update_history_entry(history_id)}

    services = [entry['service'] for entry in candidate['entries']]
    previous_services = []
    for entry in candidate['entries']:
        previous_services.append({
            'service': entry['service'],
            'container_id': entry['container_id'],
            'previous_version': entry['current_version'],
            'latest_version': entry['latest_version'],
            'image_ref': entry['image_ref'],
            'previous_image_id': entry['current_image_id'],
        })

    pull_result = _run_compose(metadata, project_name, ['pull', *services])
    if pull_result.returncode != 0:
        notes = (pull_result.stderr or pull_result.stdout or 'Compose pull failed.').strip()
        history_id = record_update_history(
            action='update',
            target_type='project',
            target_id=project_name,
            target_name=project_name,
            previous_version=candidate['current_version'],
            new_version=candidate['latest_version'],
            result='failure',
            notes=notes,
            metadata={'rollback_ready': False, 'strategy': 'compose_project_update', 'services': previous_services},
            actor_username=actor_username,
        )
        return {'ok': False, 'message': notes, 'history_entry': get_update_history_entry(history_id)}

    up_result = _run_compose(metadata, project_name, ['up', '-d', *services])
    if up_result.returncode != 0:
        service_tags = {}
        for service in previous_services:
            if service.get('previous_image_id'):
                service_tags[service['service']] = _tag_for_rollback(client, service['previous_image_id'], project_name, service['service'], int(time.time()))
        override_file = _write_override_file(project_name, service_tags, int(time.time())) if service_tags else None
        rollback_notes = ''
        if override_file:
            rollback_result = _run_compose(metadata, project_name, ['up', '-d', *service_tags.keys()], override_file=override_file)
            rollback_notes = (rollback_result.stderr or rollback_result.stdout or '').strip()
        notes = (up_result.stderr or up_result.stdout or 'Compose up failed.').strip()
        if rollback_notes:
            notes = f'{notes}\nAutomatic rollback attempt:\n{rollback_notes}'
        history_id = record_update_history(
            action='update',
            target_type='project',
            target_id=project_name,
            target_name=project_name,
            previous_version=candidate['current_version'],
            new_version=candidate['latest_version'],
            result='failure',
            notes=notes,
            metadata={'rollback_ready': False, 'strategy': 'compose_project_update', 'services': previous_services},
            actor_username=actor_username,
        )
        return {'ok': False, 'message': notes, 'history_entry': get_update_history_entry(history_id)}

    refreshed_containers = client.containers.list(all=True)
    service_versions = []
    touched_container_ids = []
    for refreshed in refreshed_containers:
        labels = refreshed.attrs.get('Config', {}).get('Labels', {}) or {}
        if labels.get('com.docker.compose.project') != project_name:
            continue
        service_name = labels.get('com.docker.compose.service') or refreshed.name
        if service_name not in services:
            continue
        touched_container_ids.append(refreshed.id)
        version_info = _container_version_info(refreshed, client)
        service_versions.append({
            'service': service_name,
            'new_version': version_info['current_version'],
        })

    _refresh_update_checks(touched_container_ids)
    previous_version = '; '.join(f"{entry['service']}={entry['previous_version']}" for entry in previous_services)
    new_version = '; '.join(f"{entry['service']}={entry['new_version']}" for entry in sorted(service_versions, key=lambda item: item['service']))
    history_id = record_update_history(
        action='update',
        target_type='project',
        target_id=project_name,
        target_name=project_name,
        previous_version=previous_version,
        new_version=new_version,
        result='success',
        notes=(pull_result.stdout or '') + (up_result.stdout or ''),
        metadata={
            'rollback_ready': True,
            'strategy': 'compose_project_update',
            'working_dir': metadata['working_dir'],
            'config_files': metadata['config_files'],
            'services': previous_services,
        },
        actor_username=actor_username,
    )
    return {
        'ok': True,
        'message': f'Project {project_name} updated with docker compose pull/up -d.',
        'history_entry': get_update_history_entry(history_id),
    }


def update_target(target_type, target_id, actor_username=None):
    if target_type == 'container':
        return update_container_target(target_id, actor_username=actor_username)
    if target_type == 'project':
        return update_project_target(target_id, actor_username=actor_username)
    return {'ok': False, 'message': 'Unknown update target type.', 'history_entry': None}


def rollback_update(history_id, actor_username=None):
    client = get_docker_client()
    entry = get_update_history_entry(history_id)
    if not entry:
        return {'ok': False, 'message': 'Update history entry not found.', 'history_entry': None}
    if entry.get('action') != 'update' or entry.get('result') != 'success':
        return {'ok': False, 'message': 'Only successful update entries can be rolled back.', 'history_entry': None}

    metadata = entry.get('metadata') or {}
    if not metadata.get('rollback_ready'):
        return {'ok': False, 'message': 'Rollback data is not available for this entry.', 'history_entry': None}

    if entry['target_type'] == 'container':
        snapshot = metadata.get('snapshot')
        previous_image_id = metadata.get('previous_image_id')
        if not snapshot or not previous_image_id:
            return {'ok': False, 'message': 'Rollback snapshot for the container is incomplete.', 'history_entry': None}
        container_lookup = metadata.get('container_name') or entry.get('target_name') or entry.get('target_id')
        container = client.containers.get(container_lookup)
        result = _recreate_single_container(container, previous_image_id, actor_username=actor_username, history_action='rollback', rollback_of=entry['id'])
        rollback_entry_id = record_update_history(
            action='rollback',
            target_type='container',
            target_id=entry['target_id'],
            target_name=entry['target_name'],
            previous_version=entry['new_version'],
            new_version=entry['previous_version'],
            result='success' if result['ok'] else 'failure',
            notes=result.get('notes') or ('Rollback completed.' if result['ok'] else 'Rollback failed.'),
            metadata={'rollback_ready': False, 'strategy': 'safe_container_recreate'},
            rollback_of=entry['id'],
            actor_username=actor_username,
        )
        return {
            'ok': result['ok'],
            'message': 'Rollback completed.' if result['ok'] else result.get('notes') or 'Rollback failed.',
            'history_entry': get_update_history_entry(rollback_entry_id),
        }

    if entry['target_type'] == 'project':
        services = metadata.get('services') or []
        working_dir = metadata.get('working_dir')
        config_files = metadata.get('config_files')
        if not services or not working_dir or not config_files:
            return {'ok': False, 'message': 'Project rollback metadata is incomplete.', 'history_entry': None}

        compose_metadata = {
            'working_dir': working_dir,
            'config_files': config_files,
        }
        service_tags = {}
        for service in services:
            previous_image_id = service.get('previous_image_id')
            if not previous_image_id:
                return {'ok': False, 'message': f"Missing previous image for service {service.get('service')}.", 'history_entry': None}
            service_tags[service['service']] = _tag_for_rollback(client, previous_image_id, entry['target_name'], service['service'], entry['id'])

        override_file = _write_override_file(entry['target_name'], service_tags, entry['id'])
        rollback_result = _run_compose(compose_metadata, entry['target_name'], ['up', '-d', *service_tags.keys()], override_file=override_file)
        success = rollback_result.returncode == 0
        notes = (rollback_result.stderr or rollback_result.stdout or '').strip()
        rollback_entry_id = record_update_history(
            action='rollback',
            target_type='project',
            target_id=entry['target_id'],
            target_name=entry['target_name'],
            previous_version=entry['new_version'],
            new_version=entry['previous_version'],
            result='success' if success else 'failure',
            notes=notes or ('Rollback completed.' if success else 'Rollback failed.'),
            metadata={'rollback_ready': False, 'strategy': 'compose_project_update'},
            rollback_of=entry['id'],
            actor_username=actor_username,
        )
        return {
            'ok': success,
            'message': 'Rollback completed.' if success else (notes or 'Rollback failed.'),
            'history_entry': get_update_history_entry(rollback_entry_id),
        }

    return {'ok': False, 'message': 'Unsupported rollback target type.', 'history_entry': None}
