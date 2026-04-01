import pytest

import app as app_module
import routes
import sampler
import users_db


DEFAULT_NOTIFICATION_SETTINGS = {
    'cpu_enabled': True,
    'ram_enabled': True,
    'status_enabled': True,
    'update_enabled': True,
    'security_enabled': True,
    'security_privileged_enabled': True,
    'security_public_ports_enabled': True,
    'security_latest_enabled': True,
    'security_docker_socket_enabled': True,
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


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "users.db"
    monkeypatch.setenv("USERS_DB_PATH", str(db_path))
    users_db.migrate_add_columns_and_role_and_settings()
    users_db.init_db("admin", "adminpass")
    sampler.notification_settings.clear()
    sampler.notification_settings.update(DEFAULT_NOTIFICATION_SETTINGS)
    return db_path


@pytest.fixture
def flask_app(temp_db, monkeypatch):
    test_app = app_module.create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "APP_VERSION": "test-version",
        "AUTH_ENABLED": True,
        "AUTH_USER": "admin",
        "AUTH_PASSWORD": "adminpass",
        "LOGIN_MODE": "page",
    })
    return test_app


@pytest.fixture
def client(flask_app):
    return flask_app.test_client()
