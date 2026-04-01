# Changelog

## v0.9.4

### Fixed
- Contained the containers table horizontal scroll inside the `Containers` panel again so the page no longer expands sideways with the table width.
- Added explicit width/min-width guards around the dashboard tab content and table shell to prevent document-level horizontal overflow regressions.

### Testing
- Added an end-to-end layout regression check to verify the document width stays equal to the viewport while `#tableView` keeps its own horizontal scrolling area.

## v0.9.3

### Changed
- Redesigned the Update Manager inventory into a compact, collapsed-by-default layout so Compose stacks, standalone containers, and history entries show only the item name plus the new target version until expanded.
- Added smooth expand/collapse transitions and a shared chevron-driven interaction model across Projects, Containers, and History tabs for higher information density and better visual consistency.

### Testing
- Updated the end-to-end Update Manager coverage to validate the collapsed-by-default behavior, on-demand expansion, and update/rollback actions from the expanded details panel.

## v0.9.2

### Changed
- Split the main dashboard into properly tabbed `Compose Stacks` and `Containers` views so only one view is displayed at a time.
- Moved update manager history into its own modal tab and switched the update inventory from block cards to a clearer list layout with columns for name, type, versions, state, last check, and action.
- Aligned the clear-notifications flow with the notification settings UX by using a dedicated confirmation modal and matching icon-button styling.

### Fixed
- Disabled security advisory notifications by default across backend defaults, frontend defaults, and test fixtures to stop noisy startup alerts.
- Hardened notification settings modal opening so it opens reliably on the first interaction.
- Hardened update manager modal opening and removed duplicate first-load work so the first interaction is responsive.
- Reduced false `blocked` update candidates by reusing sampler-cached update details when building the update manager inventory.
- Improved mobile overlay cleanup when opening notification actions from the pending notifications panel.

### Testing
- Added and updated route, sampler, update manager, and end-to-end tests for tab exclusivity, notification default states, clear-notification confirmation flow, update manager tabbed history, and cached update candidate rendering.

## v0.9.1

### Fixed
- Fixed Docker image packaging so all top-level Python modules are copied into the container image, including `update_manager.py`.
- Prevented the `ModuleNotFoundError: No module named 'update_manager'` crash on startup in Docker deployments.

### Testing
- Added a regression test to ensure the Dockerfile keeps copying all root Python modules.

## v0.9.0

### Added
- Notification delivery via `ntfy.sh` and generic HTTP webhooks, including authentication, tags, Markdown support, and structured event payloads.
- Step-by-step README documentation for `ntfy` and generic webhook notification setup.
- Notification management modal from the top bar, with advanced rules for project/container targeting, cooldowns, silencing windows, and deduplication.
- Basic security advisories that can be toggled from the UI for privileged containers, publicly exposed ports, `latest` image usage, and `/var/run/docker.sock` mounts.
- Compose project dashboard cards with per-stack CPU, RAM, status, updates, and restart totals.
- Experimental update manager with dedicated top-bar entry, separate views for standalone containers and Compose projects, safe update planning, persisted update history, and rollback support.
- Persistent update history storage and backend safety checks for update/rollback flows.
- Expanded automated coverage for notifications, security advisories, update manager flows, persistence, and end-to-end UI behavior.

### Changed
- Notifications entry in the top bar now opens the pending list and exposes gear/broom actions instead of in-panel settings controls.
- Notification configuration moved into a centered modal and the clear action now uses an icon-first interaction with tooltip text.
- Dashboard layout simplified by removing the overview visibility controls so the top panels keep matching heights.
- Container update endpoints now delegate to the new guarded update manager logic instead of performing a direct image refresh.
- Release version defaults updated to `v0.9.0`.

### Fixed
- Rollback targeting now resolves the correct container by stable container name instead of transient container IDs.
- Update manager refresh behavior now forces synchronous availability checks so the UI reflects newly detected updates reliably.
- Update status messaging persists correctly after refresh, and the E2E mock server returns consistent notification/update responses.

## v0.8.2

- Fixed database path resolution on fresh Docker installs and legacy bind mounts.

## v0.8.1

- Minor fixes.

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
