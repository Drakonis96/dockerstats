import users_db


def test_user_crud_and_password_change(temp_db):
    assert users_db.validate_user("admin", "adminpass") is True
    assert users_db.change_password("admin", "new-admin-pass") is True
    assert users_db.validate_user("admin", "new-admin-pass") is True

    created = users_db.create_user_with_columns("alice", "alice-pass", ["cpu", "ram"])
    assert created is True
    assert users_db.user_exists("alice") is True

    users = users_db.list_users_with_columns()
    alice = next(user for user in users if user["username"] == "alice")
    assert alice["columns"] == ["cpu", "ram"]
    assert alice["role"] == "user"

    users_db.update_user_columns("alice", ["cpu", "status"])
    assert users_db.get_user_columns("alice") == ["cpu", "status"]

    users_db.delete_user("alice")
    assert users_db.user_exists("alice") is False


def test_notification_settings_are_persisted(temp_db):
    settings = {
        "cpu_enabled": False,
        "ram_enabled": True,
        "status_enabled": False,
        "update_enabled": True,
        "cpu_threshold": 65.0,
        "ram_threshold": 75.0,
        "window_seconds": 30,
    }

    users_db.set_notification_settings(settings)
    stored = users_db.get_notification_settings()

    assert stored == settings


def test_audit_events_are_persisted(temp_db):
    event_id = users_db.record_audit_event(
        action="user.create",
        target_type="user",
        status="success",
        actor_username="admin",
        actor_role="admin",
        target_id="alice",
        remote_addr="127.0.0.1",
        details={"columns": ["cpu", "ram"]},
    )

    events = users_db.list_audit_events(limit=5)

    assert event_id > 0
    assert events[0]["action"] == "user.create"
    assert events[0]["details"]["columns"] == ["cpu", "ram"]
