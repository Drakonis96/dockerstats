# Changelog

## v0.8.0

### Added
- New dashboard interface with operational summary, quick filters, refresh pause/resume control, and Docker/notifications status indicators.
- Notification test feature available directly from the UI.
- Diagnostic endpoints: `/api/system-status` and `/api/notification-test`.
- Automated test suite covering routes, user database, metrics utilities, and Pushover client (`tests/test_routes.py`, `tests/test_users_db.py`, `tests/test_metrics_utils.py`, `tests/test_pushover_client.py`).
- End-to-end browser tests using Playwright for dashboard table, filters, container actions, and settings/user modals (`tests/e2e/dashboard.spec.js`).
- Deterministic E2E test server (`tests/e2e_server.py`).
- Playwright configuration and JS test tooling (`playwright.config.mjs`, `package.json`).
- Persistent audit log system with `audit_log` table and helpers for tracking sensitive actions (`users_db.py`).
- Admin endpoint to query audit logs (`routes.py`).
- Server-Sent Events (SSE) stream for real-time dashboard updates and notifications.

### Changed
- Full modernization of the main dashboard UI and login interface (`templates/index.html`, `static/dashboard-modern.css`, `templates/login.html`, `static/login-modern.css`).
- Backend refactored to use an app factory and allow startup in degraded mode when Docker is unavailable (`app.py`, `docker_client.py`).
- Dashboard JavaScript refactored: logic extracted from the template and organized into ES modules under `static/js/dashboard`, with `app.js` as the entry point.
- `templates/index.html` now loads Bootstrap and the dashboard module with global configuration.
- Frontend updated to consume a real-time SSE stream instead of browser polling, with automatic reconnection.
- Sampler synchronized with SSE using sequence counters and `Condition` signaling (`sampler.py`).
- Application configuration centralized in `config.py`, including versioning, authentication, and secrets management.
- Deployment configuration updated (`docker-compose.yml`).
- NVML integration migrated from `pynvml` to `nvidia-ml-py` (`requirements.txt`, `sampler.py`).

### Fixed
- Resolved password change bug when `LOGIN_MODE=page`.
- Removed deprecated NVML warning by migrating to `nvidia-ml-py`.

### Security
- Removed dependency on default `admin/admin` credentials.
- Added support for secrets via files and explicit ephemeral fallback for `APP_SECRET_KEY`.
- Added CSRF validation to the login flow.
- Restricted user and notification management to admin role.
- Application startup validation when `AUTH_ENABLED=true` to ensure bootstrap or existing users are present.
- Sensitive actions (password changes, user management, container operations) now recorded in the audit log.
