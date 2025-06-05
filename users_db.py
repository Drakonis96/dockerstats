import os
import sqlite3
import json
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.environ.get('USERS_DB_PATH', os.path.join(os.path.dirname(__file__), 'users.db'))

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def migrate_add_columns_and_role_and_settings():
    conn = get_db()
    c = conn.cursor()
    # Add columns field if not exists
    try:
        c.execute('ALTER TABLE users ADD COLUMN columns TEXT')
    except sqlite3.OperationalError:
        pass  # Already exists
    # Add role field if not exists
    try:
        c.execute('ALTER TABLE users ADD COLUMN role TEXT')
    except sqlite3.OperationalError:
        pass  # Already exists

    # Create global settings table if missing
    try:
        c.execute('CREATE TABLE IF NOT EXISTS global_settings (key TEXT PRIMARY KEY, value TEXT)')
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

# Call migration at import
migrate_add_columns_and_role_and_settings()

def init_db(default_user, default_password):
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        columns TEXT,
        role TEXT
    )''')
    conn.commit()
    c.execute('SELECT id FROM users WHERE username=?', (default_user,))
    if not c.fetchone():
        c.execute('INSERT INTO users (username, password_hash, role, columns) VALUES (?, ?, ?, ?)',
                  (default_user, generate_password_hash(default_password), 'admin', None))
        conn.commit()
    conn.close()

def validate_user(username, password):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT password_hash FROM users WHERE username=?', (username,))
    row = c.fetchone()
    conn.close()
    if row and check_password_hash(row['password_hash'], password):
        return True
    return False

def change_password(username, new_password):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET password_hash=? WHERE username=?',
              (generate_password_hash(new_password), username))
    conn.commit()
    conn.close()

def user_exists(username):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT 1 FROM users WHERE username=?', (username,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def create_user_with_columns(username, password, columns, role="user"):
    conn = get_db()
    c = conn.cursor()
    columns_json = json.dumps(list(columns))
    try:
        c.execute('INSERT INTO users (username, password_hash, columns, role) VALUES (?, ?, ?, ?)',
                  (username, generate_password_hash(password), columns_json, role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def list_users_with_columns():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT username, columns, role FROM users')
    users = []
    for row in c.fetchall():
        try:
            cols = json.loads(row['columns']) if row['columns'] else []
        except Exception:
            cols = []
        users.append({
            'username': row['username'],
            'columns': cols,
            'role': row['role'] or ('admin' if row['username'] == 'admin' else 'user')
        })
    conn.close()
    return users

def update_user_columns(username, columns):
    conn = get_db()
    c = conn.cursor()
    columns_json = json.dumps(list(columns))
    c.execute('UPDATE users SET columns=? WHERE username=?', (columns_json, username))
    conn.commit()
    conn.close()

def delete_user(username):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE username=?', (username,))
    conn.commit()
    conn.close()

def get_user_columns(username):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT columns FROM users WHERE username=?', (username,))
    row = c.fetchone()
    conn.close()
    if row and row['columns']:
        try:
            return json.loads(row['columns'])
        except Exception:
            return []
    return []

def get_user_role(username):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT role FROM users WHERE username=?', (username,))
    row = c.fetchone()
    conn.close()
    if row and row['role']:
        return row['role']
    return 'admin' if username == 'admin' else 'user'

# --- Global Settings Helpers ---
def set_global_setting(key, value):
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO global_settings (key, value) VALUES (?, ?)',
              (key, json.dumps(value)))
    conn.commit()
    conn.close()

def get_global_setting(key, default=None):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT value FROM global_settings WHERE key=?', (key,))
    row = c.fetchone()
    conn.close()
    if row:
        try:
            return json.loads(row['value'])
        except Exception:
            return row['value']
    return default

def get_notification_settings(default=None):
    return get_global_setting('notification_settings', default)

def set_notification_settings(settings):
    set_global_setting('notification_settings', settings)
