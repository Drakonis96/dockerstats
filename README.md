<div align="center">
  <img src="static/logo.png" alt="Docker Stats" width="140">
  <h1>Docker Stats</h1>
  <p><strong>A focused dashboard for container monitoring, safe updates, notifications, and Compose-aware operations.</strong></p>
</div>

## Overview

Docker Stats is a lightweight web UI for Docker hosts. It combines live container metrics, Compose project grouping, configurable alerts, update discovery, rollback history, and day-to-day container controls in one interface.

It is designed for self-hosted environments where you want fast operational visibility without giving up practical controls.

## What It Does Well

### Monitoring
- Live CPU, RAM, network I/O, block I/O, uptime, restart count, process count, ports, image, and status visibility.
- Table and chart views for individual containers and top-N comparisons.
- Compose project summaries with grouped container states.
- Optional GPU metrics when NVIDIA tooling is available.

### Operations
- Start, stop, and restart containers from the UI.
- Open exposed container endpoints directly from the dashboard.
- Inspect container logs without leaving the app.
- Persist filters, visible columns, chart mode, theme, refresh interval, and layout preferences locally.

### Updates
- Detect update-ready containers and Compose stacks.
- Run Quick Update for individual targets.
- Run `Update selected` or `Update all` from the Update Manager.
- Show blocked stacks with explicit guidance when original Compose files are missing or externally managed.
- Keep a persistent update and rollback history.

### Notifications
- CPU, RAM, status, and image update alerts.
- Browser-side notification center with pending event history.
- External delivery through Pushover, Slack, Telegram, Discord, ntfy, and generic webhooks.

## Screenshots

<div align="center">
  <img src="screenshots/Screenshot 1.png" alt="Dashboard" width="720">
  <img src="screenshots/Screenshot 2.png" alt="Charts" width="720">
  <img src="screenshots/Screenshot 3.png" alt="Notifications" width="720">
  <img src="screenshots/Screenshot 4.png" alt="Update Manager" width="720">
</div>

## Quick Start

### Requirements
- Docker
- Docker Compose plugin
- Access to the Docker socket on the host

### Start With Docker Compose

```bash
git clone https://github.com/Drakonis96/dockerstats
cd dockerstats
docker compose up --build -d
```

Once started, open:

```text
http://localhost:5001
```

## Default Deployment Notes

The bundled [docker-compose.yml](docker-compose.yml) exposes:

- Docker Stats on `5001`
- cAdvisor on `8080`

It also mounts:

- Docker socket as read-only
- Local app data into `./data`

## Configuration

### Core Environment Variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `AUTH_ENABLED` | Enables authentication | `true` |
| `AUTH_USER` | Admin username | empty |
| `AUTH_PASSWORD` | Admin password | empty |
| `AUTH_PASSWORD_FILE` | Password file alternative | empty |
| `APP_SECRET_KEY` | Session secret | generated if missing |
| `APP_SECRET_KEY_FILE` | Secret file alternative | empty |
| `LOGIN_MODE` | Login flow: `popup` or `page` | `popup` |
| `APP_VERSION` | Version shown in the UI footer | `v0.9.9` |
| `DOCKER_SOCKET_URL` | Docker socket URL | `unix:///var/run/docker.sock` |
| `CADVISOR_URL` | cAdvisor endpoint | `http://cadvisor:8080` |
| `GPU_METRICS_ENABLED` | Enables GPU collection | `true` in bundled compose |

### Authentication Recommendations

- There are no built-in credentials.
- Set `AUTH_USER` and either `AUTH_PASSWORD` or `AUTH_PASSWORD_FILE` before exposing the app.
- Set `APP_SECRET_KEY` or `APP_SECRET_KEY_FILE` to keep sessions stable across restarts.
- If you want no authentication, set `AUTH_ENABLED=false` explicitly.

### Login Mode

Choose the login experience with:

```yaml
LOGIN_MODE: "page"
```

Available values:

- `popup`
- `page`

## Dashboard Capabilities

### Table and Filters
- Filter by container name, status, and Compose project.
- Sort by CPU, RAM, uptime, restarts, image, I/O, update availability, and more.
- Toggle visible columns per user.
- Export current metrics to CSV.

### Charts
- Line, bar, and pie visualizations.
- Top-N comparison views for CPU, RAM, and uptime.
- Zoom and pan support where applicable.

### Compose Awareness
- Group containers by Compose project.
- Inspect project summaries alongside per-container rows.
- Switch between `Containers` and `Compose Stacks` views from the dashboard tabs.

## Update Manager

The Update Manager is designed around safety and operator visibility.

### Available Actions
- `Quick Update` for a single target.
- `Update selected` for checked stacks or containers.
- `Update all` for all ready targets in a tab.

### Selection Workflow
- Each update-ready stack or standalone container exposes a checkbox.
- You can select a range with `Shift` to batch multiple adjacent targets.
- Batch operations run sequentially to avoid overlapping recreations.

### History and Rollback
- Every successful or failed managed update is recorded in history.
- Eligible successful updates expose rollback actions.
- History is persistent and survives modal reloads.

### Externally Managed Stacks

If a stack was originally created by another tool, Docker Stats may not have the original Compose files available on disk. In that case the app can:

- mark the stack as blocked when it cannot safely manage it
- explain why the Compose files are unavailable
- use a safe external recreate workflow when runtime metadata is sufficient

This is especially relevant for stacks created through tools such as Portainer, Yacht, or similar management layers.

## Notifications

### Supported Providers

| Provider | Required Variables |
| --- | --- |
| Pushover | `PUSHOVER_TOKEN`, `PUSHOVER_USER` |
| Slack | `SLACK_WEBHOOK_URL` |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| Discord | `DISCORD_WEBHOOK_URL` |
| ntfy | `NTFY_TOPIC` |
| Generic webhook | `GENERIC_WEBHOOK_URL` |

### Common Workflow

1. Set the provider environment variables.
2. Restart Docker Stats.
3. Open the notification panel as an admin user.
4. Enable the event types you want.
5. Save the configuration.
6. Use `Send test` before relying on the provider in production.

### Events That Can Trigger Alerts
- CPU threshold exceeded
- RAM threshold exceeded
- Container status changed
- Update available

### Provider Examples

<details>
  <summary>Pushover</summary>

```env
PUSHOVER_TOKEN=your-application-token
PUSHOVER_USER=your-user-key
```

</details>

<details>
  <summary>Slack</summary>

```env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

</details>

<details>
  <summary>Telegram</summary>

```env
TELEGRAM_BOT_TOKEN=123456:abcde...
TELEGRAM_CHAT_ID=123456789
```

</details>

<details>
  <summary>Discord</summary>

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

</details>

<details>
  <summary>ntfy</summary>

Basic public ntfy setup:

```env
NTFY_TOPIC=dockerstats-home
NTFY_SERVER_URL=https://ntfy.sh
```

Protected or self-hosted ntfy examples:

```env
NTFY_TOPIC=dockerstats-prod
NTFY_SERVER_URL=https://ntfy.example.com
NTFY_TOKEN=tk_your_token_here
```

```env
NTFY_TOPIC=dockerstats-prod
NTFY_SERVER_URL=https://ntfy.example.com
NTFY_USERNAME=myuser
NTFY_PASSWORD=mysecret
NTFY_TAGS=docker,monitoring,prod
NTFY_MARKDOWN=false
```

</details>

<details>
  <summary>Generic webhook</summary>

Simple JSON webhook:

```env
GENERIC_WEBHOOK_URL=https://example.com/hooks/dockerstats
```

Plain-text body example:

```env
GENERIC_WEBHOOK_URL=https://example.com/hooks/dockerstats
GENERIC_WEBHOOK_METHOD=POST
GENERIC_WEBHOOK_CONTENT_TYPE=text/plain; charset=utf-8
GENERIC_WEBHOOK_BODY_TEMPLATE=[{event_type}] {title}\n{message}
```

Custom headers:

```env
GENERIC_WEBHOOK_URL=https://example.com/hooks/dockerstats
GENERIC_WEBHOOK_HEADERS={"Authorization":"Bearer super-secret-token","X-Environment":"prod"}
```

Available placeholders:

- `{app}`
- `{host}`
- `{title}`
- `{message}`
- `{priority}`
- `{priority_label}`
- `{event_type}`
- `{container}`
- `{container_id}`
- `{value}`
- `{prev_value}`
- `{timestamp}`
- `{timestamp_iso}`
- `{event_json}`

</details>

## Metrics Backends

Docker Stats can work with:

- Docker API only
- Docker API plus cAdvisor

The Docker API path is usually enough. cAdvisor is useful if you want broader metric compatibility or a more established metrics source for some host environments.

## GPU Metrics

GPU metrics are available for NVIDIA-enabled hosts.

### Requirements
- NVIDIA drivers on the host
- `nvidia-smi` available in the runtime environment
- GPU-enabled container access where applicable

### Enablement

```yaml
environment:
  GPU_METRICS_ENABLED: true
```

If GPU data is available, Docker Stats surfaces GPU load and memory usage per container in the dashboard.

## Runtime Notes

### CPU Usage

CPU percentage is calculated per core. On multi-core systems the effective ceiling is:

```text
100% x number of available CPU cores
```

### Exited Containers

Exited containers stay visible in the main table so you can:

- inspect their last known state
- review recent resource usage
- restart them directly from the UI

## Safety Notice

Docker Stats requires access to your Docker environment to inspect containers, operate on them, and evaluate updates. Use it only on systems where you understand the implications of Docker socket access and trust the deployment.

Managed updates are designed to preserve volumes, configuration, environment, networks, and other persistent state whenever possible, but you should still review updates before applying them in production.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
