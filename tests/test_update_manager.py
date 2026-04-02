from types import SimpleNamespace

import sampler
import update_manager
import users_db


class FakeImage:
    def __init__(self, image_id, tags=None):
        self.id = image_id
        self.tags = list(tags or [])
        self.attrs = {'RepoDigests': []}


class FakeContainer:
    def __init__(self, container_id, name, image_ref, *, labels=None, image_id=None, status='running'):
        self.id = container_id
        self.name = name
        self.status = status
        self.image = FakeImage(image_id or f'sha256:{name}-image', [image_ref])
        self.attrs = {
            'Config': {
                'Image': image_ref,
                'Labels': dict(labels or {}),
            },
            'State': {'Status': status},
            'HostConfig': {},
            'NetworkSettings': {'Networks': {}},
            'Mounts': [],
        }


class FakeContainersManager:
    def __init__(self, list_sequences=None, lookup_map=None):
        self.list_sequences = list(list_sequences or [[]])
        self.lookup_map = dict(lookup_map or {})
        self.lookup_calls = []
        self.list_calls = 0

    def list(self, all=True):
        self.list_calls += 1
        index = min(self.list_calls - 1, len(self.list_sequences) - 1)
        return list(self.list_sequences[index])

    def get(self, identifier):
        self.lookup_calls.append(identifier)
        if identifier not in self.lookup_map:
          raise KeyError(identifier)
        return self.lookup_map[identifier]


class FakeImagesManager:
    def __init__(self, pulled=None, get_map=None):
        self.pulled = pulled if pulled is not None else []
        self.get_map = dict(get_map or {})

    def pull(self, image_ref):
        self.pulled.append(image_ref)

    def get(self, image_ref):
        return self.get_map[image_ref]


class FakeDockerClient:
    def __init__(self, containers_manager, images_manager=None):
        self.containers = containers_manager
        self.images = images_manager or FakeImagesManager()


def test_list_update_targets_groups_projects_and_standalone_containers(temp_db, monkeypatch, tmp_path):
    compose_file = tmp_path / 'docker-compose.yml'
    compose_file.write_text('services: {}\n', encoding='utf-8')

    common_labels = {
        'com.docker.compose.project': 'demo',
        'com.docker.compose.project.working_dir': str(tmp_path),
        'com.docker.compose.project.config_files': 'docker-compose.yml',
    }
    web = FakeContainer('cid-web', 'web', 'nginx:1.25', labels={**common_labels, 'com.docker.compose.service': 'web'})
    db = FakeContainer('cid-db', 'db', 'postgres:16', labels={**common_labels, 'com.docker.compose.service': 'db'})
    cache = FakeContainer('cid-cache', 'cache', 'redis:7')
    client = FakeDockerClient(FakeContainersManager(list_sequences=[[web, db, cache]]))

    monkeypatch.setattr(update_manager, 'get_docker_client', lambda: client)
    monkeypatch.setattr(update_manager, '_container_version_info', lambda container, _client: {
        'image_ref': container.attrs['Config']['Image'],
        'current_token': f'{container.name}-old',
        'latest_token': f'{container.name}-new',
        'current_version': f"{container.attrs['Config']['Image']} @ {container.name}-old",
        'latest_version': f"{container.attrs['Config']['Image']} @ {container.name}-new",
        'current_image_id': f'sha256:{container.name}-old',
    })
    monkeypatch.setattr(sampler, 'update_check_cache', {'cid-web': True, 'cid-db': True, 'cid-cache': True})
    monkeypatch.setattr(sampler, 'update_check_time', {'cid-web': 101.0, 'cid-db': 102.0, 'cid-cache': 103.0})

    history_id = users_db.record_update_history(
        action='update',
        target_type='project',
        target_id='demo',
        target_name='demo',
        previous_version='db=postgres:16',
        new_version='db=postgres:17',
        result='success',
        metadata={'rollback_ready': True},
        actor_username='admin',
    )
    users_db.set_auto_update_target('project', 'demo', True)
    users_db.set_auto_update_target('container', 'cache', True)

    payload = update_manager.list_update_targets(history_limit=5)
    auto_updates = {(item['type'], item['name']): item for item in payload['auto_updates']}

    assert payload['experimental_notice'] == update_manager.EXPERIMENTAL_NOTICE
    assert payload['history_notice'] == update_manager.UPDATE_HISTORY_NOTICE
    assert payload['history_retention_days'] == update_manager.UPDATE_HISTORY_RETENTION_DAYS
    assert len(payload['projects']) == 1
    assert payload['projects'][0]['name'] == 'demo'
    assert payload['projects'][0]['type'] == 'project'
    assert len(payload['projects'][0]['entries']) == 2
    assert len(payload['containers']) == 1
    assert payload['containers'][0]['name'] == 'cache'
    assert payload['containers'][0]['type'] == 'container'
    assert len(payload['auto_updates']) == 2
    assert auto_updates[('project', 'demo')]['auto_update_enabled'] is True
    assert auto_updates[('project', 'demo')]['last_updated_at'] is not None
    assert auto_updates[('container', 'cache')]['auto_update_enabled'] is True
    assert payload['history'][0]['id'] == history_id
    assert payload['history'][0]['can_rollback'] is True


def test_list_update_targets_uses_cached_details_without_marking_ready_updates_blocked(temp_db, monkeypatch):
    container = FakeContainer('cid-cache', 'cache', 'redis:7')
    client = FakeDockerClient(FakeContainersManager(list_sequences=[[container]]))

    monkeypatch.setattr(update_manager, 'get_docker_client', lambda: client)
    monkeypatch.setattr(sampler, 'update_check_cache', {'cid-cache': True})
    monkeypatch.setattr(sampler, 'update_check_time', {'cid-cache': 150.0})
    monkeypatch.setattr(sampler, 'update_check_details_cache', {
        'cid-cache': {
            'image_ref': 'redis:7',
            'current_token': 'cache-old',
            'latest_token': None,
            'current_version': 'redis:7 @ cache-old',
            'latest_version': None,
            'current_image_id': 'sha256:cache-old',
        },
    })

    payload = update_manager.list_update_targets(history_limit=5)

    assert len(payload['containers']) == 1
    candidate = payload['containers'][0]
    assert candidate['name'] == 'cache'
    assert candidate['update_state'] == 'ready'
    assert candidate['state_reason'] is None
    assert candidate['latest_version'].startswith('redis:7 @ ')


def test_container_version_info_for_list_avoids_live_lookup_on_cache_miss(temp_db, monkeypatch):
    container = FakeContainer('cid-cache', 'cache', 'redis:7', image_id='sha256:cache-old')

    def fail_live_lookup(*_args, **_kwargs):
        raise AssertionError('inventory rendering should not trigger live registry lookups')

    monkeypatch.setattr(update_manager, '_container_version_info', fail_live_lookup)
    monkeypatch.setattr(sampler, 'update_check_cache', {'cid-cache': True})
    monkeypatch.setattr(sampler, 'update_check_details_cache', {})

    details = update_manager._container_version_info_for_list(container, client=None)

    assert details['current_version'] == 'redis:7 @ cache-old'
    assert details['latest_version'].startswith('redis:7 @ update-avail')
    assert details['current_image_id'] == 'sha256:cache-old'
    assert details['error'] == 'cache-miss'


def test_list_update_targets_reuses_candidate_inventory_for_auto_updates(temp_db, monkeypatch):
    container = FakeContainer('cid-cache', 'cache', 'redis:7')
    client = FakeDockerClient(FakeContainersManager(list_sequences=[[container]]))
    build_calls = []

    def fake_build(containers, _client, only_update_available=False):
        build_calls.append({
            'containers': [item.id for item in containers],
            'only_update_available': only_update_available,
        })
        return (
            [
                {
                    'id': 'project:demo',
                    'target_id': 'demo',
                    'name': 'demo',
                    'type': 'project',
                    'current_version': 'web=nginx:1.25 @ old',
                    'latest_version': 'web=nginx:1.25 @ new',
                    'update_available': True,
                    'update_state': 'ready',
                    'state_reason': None,
                    'last_checked_at': 100.0,
                    'entries': [],
                    'meta': {},
                },
                {
                    'id': 'project:blocked',
                    'target_id': 'blocked',
                    'name': 'blocked',
                    'type': 'project',
                    'current_version': 'api=my-api:1.0 @ old',
                    'latest_version': 'api=my-api:1.1 @ new',
                    'update_available': True,
                    'update_state': 'blocked',
                    'state_reason': 'missing compose files',
                    'last_checked_at': 99.0,
                    'entries': [],
                    'meta': {},
                },
            ],
            [
                {
                    'id': 'container:cid-cache',
                    'target_id': 'cid-cache',
                    'name': 'cache',
                    'type': 'container',
                    'current_version': 'redis:7 @ old',
                    'latest_version': 'redis:7 @ new',
                    'update_available': True,
                    'update_state': 'ready',
                    'state_reason': None,
                    'last_checked_at': 101.0,
                    'entries': [],
                    'meta': {},
                },
                {
                    'id': 'container:cid-monitor',
                    'target_id': 'cid-monitor',
                    'name': 'monitor',
                    'type': 'container',
                    'current_version': 'busybox:1.36 @ old',
                    'latest_version': 'busybox:1.36 @ old',
                    'update_available': False,
                    'update_state': 'ready',
                    'state_reason': None,
                    'last_checked_at': 98.0,
                    'entries': [],
                    'meta': {},
                },
            ],
        )

    monkeypatch.setattr(update_manager, 'get_docker_client', lambda: client)
    monkeypatch.setattr(update_manager, '_build_candidate_collections', fake_build)
    monkeypatch.setattr(update_manager, 'get_auto_update_settings', lambda: {'containers': {}, 'projects': {}})
    monkeypatch.setattr(update_manager, 'list_latest_successful_update_timestamps', lambda: {})
    monkeypatch.setattr(update_manager, 'list_update_history', lambda limit=100: [])

    payload = update_manager.list_update_targets(history_limit=5)

    assert build_calls == [{'containers': ['cid-cache'], 'only_update_available': False}]
    assert [item['name'] for item in payload['projects']] == ['demo', 'blocked']
    assert [item['name'] for item in payload['containers']] == ['cache']
    assert [item['name'] for item in payload['auto_updates']] == ['demo', 'cache', 'monitor']


def test_list_update_targets_marks_portainer_managed_projects_as_ready_for_external_safe_recreate(temp_db, monkeypatch):
    labels = {
        'com.docker.compose.project': 'portainer-demo',
        'com.docker.compose.project.working_dir': '/data/compose/42',
        'com.docker.compose.project.config_files': 'docker-compose.yml',
        'com.docker.compose.service': 'web',
    }
    container = FakeContainer('cid-web', 'portainer-demo-web-1', 'nginx:1.25', labels=labels)
    client = FakeDockerClient(FakeContainersManager(list_sequences=[[container]]))

    monkeypatch.setattr(update_manager, 'get_docker_client', lambda: client)
    monkeypatch.setattr(sampler, 'update_check_cache', {'cid-web': True})
    monkeypatch.setattr(sampler, 'update_check_time', {'cid-web': 120.0})
    monkeypatch.setattr(sampler, 'update_check_details_cache', {
        'cid-web': {
            'image_ref': 'nginx:1.25',
            'current_token': 'web-old',
            'latest_token': 'web-new',
            'current_version': 'nginx:1.25 @ web-old',
            'latest_version': 'nginx:1.25 @ web-new',
            'current_image_id': 'sha256:web-old',
        },
    })

    payload = update_manager.list_update_targets(history_limit=5)

    assert len(payload['projects']) == 1
    candidate = payload['projects'][0]
    assert candidate['update_state'] == 'ready'
    assert candidate['state_reason'] is None
    assert candidate['meta']['management_mode'] == 'external'
    assert candidate['meta']['manager_key'] == 'portainer'
    assert candidate['meta']['missing_files'] == ['/data/compose/42/docker-compose.yml']
    assert candidate['meta']['auto_recovery_supported'] is True
    assert candidate['meta']['update_strategy'] == 'external_project_safe_recreate'
    assert candidate['meta']['update_mode_label'] == 'External safe recreate'
    assert any('safe container recreation workflow' in item for item in candidate['meta']['guidance'])
    assert 'Export the stack from Portainer' in candidate['meta']['recovery_hint']


def test_configure_auto_update_target_persists_supported_container(temp_db, monkeypatch):
    container = FakeContainer('cid-cache', 'cache', 'redis:7')
    client = FakeDockerClient(FakeContainersManager(list_sequences=[[container]]))

    monkeypatch.setattr(update_manager, 'get_docker_client', lambda: client)
    monkeypatch.setattr(sampler, 'update_check_cache', {})
    monkeypatch.setattr(sampler, 'update_check_time', {'cid-cache': 150.0})
    monkeypatch.setattr(sampler, 'update_check_details_cache', {
        'cid-cache': {
            'image_ref': 'redis:7',
            'current_token': 'cache-old',
            'latest_token': 'cache-new',
            'current_version': 'redis:7 @ cache-old',
            'latest_version': 'redis:7 @ cache-new',
            'current_image_id': 'sha256:cache-old',
        },
    })

    enabled = update_manager.configure_auto_update_target('container', 'cache', True)

    assert enabled['ok'] is True
    assert enabled['item']['auto_update_enabled'] is True
    assert users_db.get_auto_update_settings()['containers']['cache'] is True

    disabled = update_manager.configure_auto_update_target('container', 'cache', False)

    assert disabled['ok'] is True
    assert disabled['item']['auto_update_enabled'] is False
    assert users_db.get_auto_update_settings()['containers'] == {}


def test_refresh_candidate_checks_deduplicates_registry_lookups_by_image_ref(temp_db, monkeypatch):
    web_a = FakeContainer('cid-web-a', 'web-a', 'nginx:1.25', image_id='sha256:web-old')
    web_b = FakeContainer('cid-web-b', 'web-b', 'nginx:1.25', image_id='sha256:web-old')
    db = FakeContainer('cid-db', 'db', 'postgres:16', image_id='sha256:db-old')
    client = FakeDockerClient(FakeContainersManager(list_sequences=[[web_a, web_b, db]]))
    remote_calls = []

    def fake_remote_digest(_client, image_ref):
        remote_calls.append(image_ref)
        return f'sha256:{image_ref.replace(":", "-")}-new'

    monkeypatch.setattr(update_manager, 'get_docker_client', lambda: client)
    monkeypatch.setattr(update_manager, '_remote_digest_for_image', fake_remote_digest)
    monkeypatch.setattr(sampler, 'update_check_cache', {})
    monkeypatch.setattr(sampler, 'update_check_time', {})
    monkeypatch.setattr(sampler, 'update_check_details_cache', {})

    refreshed = update_manager._refresh_candidate_checks([web_a, web_b, db])

    assert len(refreshed) == 3
    assert set(remote_calls) == {'nginx:1.25', 'postgres:16'}
    assert len(remote_calls) == 2
    assert sampler.update_check_cache['cid-web-a'] is True
    assert sampler.update_check_cache['cid-web-b'] is True
    assert sampler.update_check_cache['cid-db'] is True
    assert sampler.update_check_details_cache['cid-web-a']['latest_version'].startswith('nginx:1.25 @ ')


def test_update_container_target_records_previous_version_and_history(temp_db, monkeypatch):
    container = FakeContainer('cid-cache', 'cache', 'redis:7', image_id='sha256:cache-old')
    images = FakeImagesManager(get_map={'redis:7': FakeImage('sha256:cache-new', ['redis:7'])})
    client = FakeDockerClient(FakeContainersManager(lookup_map={'cid-cache': container}), images)

    monkeypatch.setattr(update_manager, 'get_docker_client', lambda: client)
    monkeypatch.setattr(update_manager, '_container_version_info', lambda *_args: {
        'image_ref': 'redis:7',
        'current_token': 'cache-old',
        'latest_token': 'cache-new',
        'current_version': 'redis:7 @ cache-old',
        'latest_version': 'redis:7 @ cache-new',
        'current_image_id': 'sha256:cache-old',
    })
    monkeypatch.setattr(update_manager, '_recreate_single_container', lambda *_args, **_kwargs: {
        'ok': True,
        'target_name': 'cache',
        'previous_version': 'redis:7 @ cache-old',
        'new_version': 'redis:7 @ cache-new',
        'result': 'success',
        'notes': 'Container recreated safely.',
        'metadata': {
            'strategy': 'safe_container_recreate',
            'snapshot': {'name': 'cache'},
            'container_name': 'cache',
            'previous_image_id': 'sha256:cache-old',
            'new_image_id': 'sha256:cache-new',
        },
    })

    result = update_manager.update_container_target('cid-cache', actor_username='admin')

    assert result['ok'] is True
    assert client.images.pulled == ['redis:7']
    assert result['history_entry']['previous_version'] == 'redis:7 @ cache-old'
    assert result['history_entry']['new_version'] == 'redis:7 @ cache-new'
    assert result['history_entry']['metadata']['rollback_ready'] is True
    assert result['history_entry']['metadata']['image_ref'] == 'redis:7'


def test_update_project_target_success_records_previous_images_for_rollback(temp_db, monkeypatch, tmp_path):
    compose_file = tmp_path / 'docker-compose.yml'
    compose_file.write_text('services: {}\n', encoding='utf-8')
    common_labels = {
        'com.docker.compose.project': 'demo',
        'com.docker.compose.project.working_dir': str(tmp_path),
        'com.docker.compose.project.config_files': 'docker-compose.yml',
    }
    db_old = FakeContainer('cid-db-old', 'demo-db-1', 'postgres:16', labels={**common_labels, 'com.docker.compose.service': 'db'}, image_id='sha256:db-old')
    web_old = FakeContainer('cid-web-old', 'demo-web-1', 'nginx:1.25', labels={**common_labels, 'com.docker.compose.service': 'web'}, image_id='sha256:web-old')
    db_new = FakeContainer('cid-db-new', 'demo-db-1', 'postgres:16', labels={**common_labels, 'com.docker.compose.service': 'db'}, image_id='sha256:db-new')
    web_new = FakeContainer('cid-web-new', 'demo-web-1', 'nginx:1.25', labels={**common_labels, 'com.docker.compose.service': 'web'}, image_id='sha256:web-new')

    containers = FakeContainersManager(list_sequences=[[db_old, web_old], [db_new, web_new]])
    client = FakeDockerClient(containers)
    compose_calls = []

    def fake_version_info(container, _client):
        mapping = {
            'cid-db-old': {
                'image_ref': 'postgres:16',
                'current_token': 'db-old',
                'latest_token': 'db-new',
                'current_version': 'postgres:16 @ db-old',
                'latest_version': 'postgres:16 @ db-new',
                'current_image_id': 'sha256:db-old',
            },
            'cid-web-old': {
                'image_ref': 'nginx:1.25',
                'current_token': 'web-old',
                'latest_token': 'web-new',
                'current_version': 'nginx:1.25 @ web-old',
                'latest_version': 'nginx:1.25 @ web-new',
                'current_image_id': 'sha256:web-old',
            },
            'cid-db-new': {
                'image_ref': 'postgres:16',
                'current_token': 'db-new',
                'latest_token': 'db-new',
                'current_version': 'postgres:16 @ db-new',
                'latest_version': 'postgres:16 @ db-new',
                'current_image_id': 'sha256:db-new',
            },
            'cid-web-new': {
                'image_ref': 'nginx:1.25',
                'current_token': 'web-new',
                'latest_token': 'web-new',
                'current_version': 'nginx:1.25 @ web-new',
                'latest_version': 'nginx:1.25 @ web-new',
                'current_image_id': 'sha256:web-new',
            },
        }
        return mapping[container.id]

    def fake_run_compose(metadata, project_name, extra_args, override_file=None):
        compose_calls.append((project_name, tuple(extra_args), override_file))
        return SimpleNamespace(returncode=0, stdout='compose ok\n', stderr='')

    monkeypatch.setattr(update_manager, 'get_docker_client', lambda: client)
    monkeypatch.setattr(update_manager, '_container_version_info', fake_version_info)
    monkeypatch.setattr(update_manager, '_run_compose', fake_run_compose)
    monkeypatch.setattr(sampler, 'update_check_cache', {'cid-db-old': True, 'cid-web-old': True})

    result = update_manager.update_project_target('demo', actor_username='admin')

    assert result['ok'] is True
    assert compose_calls[0][1][0] == 'pull'
    assert compose_calls[1][1][:2] == ('up', '-d')
    assert result['history_entry']['result'] == 'success'
    assert result['history_entry']['metadata']['rollback_ready'] is True
    assert {service['service'] for service in result['history_entry']['metadata']['services']} == {'db', 'web'}
    assert 'db=postgres:16 @ db-old' in result['history_entry']['previous_version']
    assert 'db=postgres:16 @ db-new' in result['history_entry']['new_version']


def test_update_project_target_records_failure_on_compose_up_error(temp_db, monkeypatch, tmp_path):
    compose_file = tmp_path / 'docker-compose.yml'
    compose_file.write_text('services: {}\n', encoding='utf-8')
    common_labels = {
        'com.docker.compose.project': 'demo',
        'com.docker.compose.project.working_dir': str(tmp_path),
        'com.docker.compose.project.config_files': 'docker-compose.yml',
    }
    db_old = FakeContainer('cid-db-old', 'demo-db-1', 'postgres:16', labels={**common_labels, 'com.docker.compose.service': 'db'}, image_id='sha256:db-old')
    client = FakeDockerClient(FakeContainersManager(list_sequences=[[db_old]]))
    compose_calls = []

    monkeypatch.setattr(update_manager, 'get_docker_client', lambda: client)
    monkeypatch.setattr(update_manager, '_container_version_info', lambda *_args: {
        'image_ref': 'postgres:16',
        'current_token': 'db-old',
        'latest_token': 'db-new',
        'current_version': 'postgres:16 @ db-old',
        'latest_version': 'postgres:16 @ db-new',
        'current_image_id': 'sha256:db-old',
    })
    monkeypatch.setattr(sampler, 'update_check_cache', {'cid-db-old': True})
    monkeypatch.setattr(update_manager, '_tag_for_rollback', lambda *_args: 'rollback/demo-db:history-1')
    monkeypatch.setattr(update_manager, '_write_override_file', lambda *_args: str(tmp_path / 'rollback.override.yml'))

    def fake_run_compose(metadata, project_name, extra_args, override_file=None):
        compose_calls.append((project_name, tuple(extra_args), override_file))
        if extra_args[0] == 'pull':
            return SimpleNamespace(returncode=0, stdout='pulled\n', stderr='')
        if override_file:
            return SimpleNamespace(returncode=0, stdout='rollback ok\n', stderr='')
        return SimpleNamespace(returncode=1, stdout='', stderr='compose up failed')

    monkeypatch.setattr(update_manager, '_run_compose', fake_run_compose)

    result = update_manager.update_project_target('demo', actor_username='admin')

    assert result['ok'] is False
    assert compose_calls[0][1][0] == 'pull'
    assert compose_calls[1][1][0] == 'up'
    assert compose_calls[2][2]
    assert result['history_entry']['result'] == 'failure'
    assert 'compose up failed' in result['history_entry']['notes']
    assert 'Automatic rollback attempt' in result['history_entry']['notes']


def test_update_project_target_uses_external_safe_recreate_when_compose_files_are_missing(temp_db, monkeypatch):
    labels = {
        'com.docker.compose.project': 'portainer-demo',
        'com.docker.compose.project.working_dir': '/data/compose/42',
        'com.docker.compose.project.config_files': 'docker-compose.yml',
        'com.docker.compose.service': 'web',
    }
    container = FakeContainer('cid-web', 'portainer-demo-web-1', 'nginx:1.25', labels=labels, image_id='sha256:web-old')
    images = FakeImagesManager(
        get_map={'nginx:1.25': FakeImage('sha256:web-new', ['nginx:1.25'])},
    )
    client = FakeDockerClient(
        FakeContainersManager(list_sequences=[[container], [container]], lookup_map={'cid-web': container}),
        images,
    )

    monkeypatch.setattr(update_manager, 'get_docker_client', lambda: client)
    monkeypatch.setattr(sampler, 'update_check_cache', {'cid-web': True})
    monkeypatch.setattr(sampler, 'update_check_details_cache', {
        'cid-web': {
            'image_ref': 'nginx:1.25',
            'current_token': 'web-old',
            'latest_token': 'web-new',
            'current_version': 'nginx:1.25 @ web-old',
            'latest_version': 'nginx:1.25 @ web-new',
            'current_image_id': 'sha256:web-old',
        },
    })
    monkeypatch.setattr(update_manager, '_container_version_info', lambda *_args: {
        'image_ref': 'nginx:1.25',
        'current_token': 'web-old',
        'latest_token': 'web-new',
        'current_version': 'nginx:1.25 @ web-old',
        'latest_version': 'nginx:1.25 @ web-new',
        'current_image_id': 'sha256:web-old',
    })
    monkeypatch.setattr(update_manager, '_recreate_single_container', lambda container_obj, target_image, **_kwargs: {
        'ok': container_obj.id == 'cid-web' and target_image == 'sha256:web-new',
        'target_name': container_obj.name,
        'previous_version': 'nginx:1.25 @ web-old',
        'new_version': 'nginx:1.25 @ web-new',
        'result': 'success',
        'notes': None,
        'metadata': {
            'strategy': 'safe_container_recreate',
            'current_container_id': 'cid-web-new',
        },
    })

    result = update_manager.update_project_target('portainer-demo', actor_username='admin')

    assert result['ok'] is True
    assert 'without compose files' in result['message']
    assert result['history_entry']['result'] == 'success'
    assert result['history_entry']['metadata']['strategy'] == 'external_project_safe_recreate'
    assert result['history_entry']['metadata']['rollback_ready'] is True
    assert client.images.pulled == ['nginx:1.25']


def test_rollback_update_for_external_project_uses_safe_recreate(temp_db, monkeypatch):
    history_id = users_db.record_update_history(
        action='update',
        target_type='project',
        target_id='jobs',
        target_name='jobs',
        previous_version='worker=python:3.12 @ worker-old',
        new_version='worker=python:3.13 @ worker-new',
        result='success',
        metadata={
            'rollback_ready': True,
            'strategy': 'external_project_safe_recreate',
            'services': [
                {
                    'service': 'worker',
                    'container_name': 'jobs-worker-1',
                    'previous_image_id': 'sha256:worker-old',
                },
            ],
        },
        actor_username='admin',
    )
    labels = {
        'com.docker.compose.project': 'jobs',
        'com.docker.compose.service': 'worker',
    }
    container = FakeContainer('cid-worker-current', 'jobs-worker-1', 'python:3.13', labels=labels, image_id='sha256:worker-new')
    client = FakeDockerClient(FakeContainersManager(list_sequences=[[container]]))

    monkeypatch.setattr(update_manager, 'get_docker_client', lambda: client)
    monkeypatch.setattr(update_manager, '_recreate_single_container', lambda container_obj, target_image, **_kwargs: {
        'ok': container_obj.name == 'jobs-worker-1' and target_image == 'sha256:worker-old',
        'target_name': container_obj.name,
        'previous_version': 'python:3.13 @ worker-new',
        'new_version': 'python:3.12 @ worker-old',
        'result': 'success',
        'notes': 'Rollback completed.',
        'metadata': {'strategy': 'safe_container_recreate'},
    })

    result = update_manager.rollback_update(history_id, actor_username='admin')

    assert result['ok'] is True
    assert result['history_entry']['action'] == 'rollback'
    assert result['history_entry']['rollback_of'] == history_id


def test_rollback_update_for_container_uses_stable_container_name(temp_db, monkeypatch):
    container = FakeContainer('cid-current', 'cache', 'redis:7', image_id='sha256:new')
    containers = FakeContainersManager(lookup_map={'cache': container})
    client = FakeDockerClient(containers)

    history_id = users_db.record_update_history(
        action='update',
        target_type='container',
        target_id='cid-old',
        target_name='cache',
        previous_version='redis:7 @ old',
        new_version='redis:7 @ new',
        result='success',
        metadata={
            'rollback_ready': True,
            'snapshot': {'name': 'cache'},
            'container_name': 'cache',
            'previous_image_id': 'sha256:old',
        },
        actor_username='admin',
    )

    monkeypatch.setattr(update_manager, 'get_docker_client', lambda: client)
    monkeypatch.setattr(update_manager, '_recreate_single_container', lambda container_obj, target_image, **_kwargs: {
        'ok': container_obj.name == 'cache' and target_image == 'sha256:old',
        'target_name': container_obj.name,
        'previous_version': 'redis:7 @ new',
        'new_version': 'redis:7 @ old',
        'result': 'success',
        'notes': 'Rollback completed.',
        'metadata': {'strategy': 'safe_container_recreate'},
    })

    result = update_manager.rollback_update(history_id, actor_username='admin')

    assert result['ok'] is True
    assert containers.lookup_calls == ['cache']
    assert result['history_entry']['action'] == 'rollback'
    assert result['history_entry']['rollback_of'] == history_id


def test_rollback_update_for_project_uses_recorded_previous_images(temp_db, monkeypatch, tmp_path):
    history_id = users_db.record_update_history(
        action='update',
        target_type='project',
        target_id='demo',
        target_name='demo',
        previous_version='db=postgres:16 @ old',
        new_version='db=postgres:16 @ new',
        result='success',
        metadata={
            'rollback_ready': True,
            'working_dir': str(tmp_path),
            'config_files': [str(tmp_path / 'docker-compose.yml')],
            'services': [
                {'service': 'db', 'previous_image_id': 'sha256:db-old'},
                {'service': 'web', 'previous_image_id': 'sha256:web-old'},
            ],
        },
        actor_username='admin',
    )

    client = FakeDockerClient(FakeContainersManager())
    rollback_tags = []
    compose_calls = []

    monkeypatch.setattr(update_manager, 'get_docker_client', lambda: client)
    monkeypatch.setattr(update_manager, '_tag_for_rollback', lambda _client, image_id, project_name, service_name, _history_id: rollback_tags.append((project_name, service_name, image_id)) or f'rollback/{project_name}-{service_name}:tag')
    monkeypatch.setattr(update_manager, '_write_override_file', lambda *_args: str(tmp_path / 'rollback.override.yml'))
    monkeypatch.setattr(update_manager, '_run_compose', lambda metadata, project_name, extra_args, override_file=None: compose_calls.append((project_name, tuple(extra_args), override_file)) or SimpleNamespace(returncode=0, stdout='rollback ok\n', stderr=''))

    result = update_manager.rollback_update(history_id, actor_username='admin')

    assert result['ok'] is True
    assert rollback_tags == [('demo', 'db', 'sha256:db-old'), ('demo', 'web', 'sha256:web-old')]
    assert compose_calls[0][0] == 'demo'
    assert compose_calls[0][1][:2] == ('up', '-d')
    assert result['history_entry']['action'] == 'rollback'
