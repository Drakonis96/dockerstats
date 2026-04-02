<div align="center">
  <img src="logo.png" alt="Docker Monitor" width="150">
</div>

---

## ⚠️ Disclaimer

This application requires access to your Docker environment in order to read container statistics, start, stop, and restart containers, and check for image updates. Use with caution and only on systems where you trust the source and understand the implications. The authors are not responsible for any unintended consequences, data loss, or security issues that may arise from its use.

---

# Docker Monitor

**Docker Monitor** is a lightweight and responsive web application for real-time monitoring of Docker container resource usage.

It displays **CPU and RAM consumption** per container in a simple visual interface, allowing you to switch between table view and several types of charts (bar, line, and pie).

---

## 🚀 Main Features

### Visualization & Monitoring
- 🟢 **Real-time monitoring** of containers
- 📊 **Visualization modes:**
  - **Table view:** Detailed metrics with progress bars
  - **Historical charts:** CPU/RAM per container (line/bar, zoom/pan)
  - **Comparison charts:** Top N containers by CPU, RAM, or Uptime
- 🎮 **GPU metrics with NVIDIA support** (see below)
- 📄 **View container logs** directly from the UI
- 🏗️ **Group by Docker Compose project** with collapse/expand
- 🔍 **Quick search** by name from the navigation bar

---

### Control & Management
- ⚙️ **Control buttons:** Start, stop, and restart containers from the UI
- 🌐 **Quick access to exposed ports** (opens in a new tab)
- ⬆️ **Update check:** Manually check for new image versions on Docker Hub
- 🆔 **Custom server IP** for UI links
- 🔑 **Change password:** The admin user can change their password from the settings menu (recommended on first use)
- 👥 **User management:** Add new users and manage their permissions (choose which columns each user can see)

### Customization & Usability
- 🧠 **Advanced filtering and sorting:**
  - Filters by name, status, and project
  - Sort by any column (name, CPU, RAM, processes, status, uptime, restarts, memory limit, I/O, update availability)
- 🌗 **Light/Dark mode** (☀️ / 🌙)
- 🔝 **Scroll-to-top button** for long lists
- ⏱️ **Realtime SSE refresh control** (5s, 10s, 30s, etc. without browser polling)
- 🛠️ **Settings persistence:** Remembers filters, theme, chart type, visible columns, interval, IP, and project collapse states (localStorage)

### Export & Notifications
- 📥 **Export selected metrics to CSV**
- 🔔 **Configurable notifications:**
  - Desktop notifications for CPU/RAM thresholds or status changes (notification window in the browser)
  - **Pushover, Slack, Telegram, Discord, ntfy.sh and generic webhooks:** Receive alerts on your mobile device, chat apps, or any HTTP endpoint when containers exceed CPU/RAM thresholds or change status. (See configuration below)
- 💬 **Status messages:** Visual feedback for actions like saving settings, checking updates, or errors

---

## ⚡ Backend Options: Docker API & cAdvisor

You can choose on the WebUI how metrics are collected:
- **Docker API only:** Default, works for most setups.
- **Docker API + cAdvisor:** For advanced metrics and compatibility, you can enable cAdvisor support. This is useful if you want more detailed stats or run Docker in environments where the API alone is limited.

---

## 🔔 Notification Setup

All outbound providers use environment variables. Once you configure any provider:
1. Add the variables to your `.env` file or `docker-compose.yml`.
2. Restart the app:
   ```bash
   docker compose up -d
   ```
3. Open Docker Stats as an admin user.
4. Click the bell icon, enable the event types you want, and click **Save**.
5. Click **Send test** to verify delivery before relying on production alerts.

The same alert events are sent to every configured provider:
- CPU threshold exceeded
- RAM threshold exceeded
- Container status changed
- Update available

---

## 🔔 Pushover Notifications Setup

To receive push notifications on your phone or device:
1. Create a free account at [Pushover](https://pushover.net/) and install the app on your device.
2. Get your **User Key** and create an **Application/API Token**.
3. Add these variables:
   ```env
   PUSHOVER_TOKEN=your-application-token
   PUSHOVER_USER=your-user-key
   ```
4. Restart Docker Stats.
5. Use **Send test** in the notification panel.

You will now receive alerts for CPU/RAM thresholds, container status changes, and image updates directly on your device.

---

## 🔔 Slack Notifications Setup

To send alerts to Slack:
1. Create an **Incoming Webhook** at <https://slack.com/apps>.
2. Copy the webhook URL for the target channel.
3. Add this variable:
   ```env
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
   ```
4. Restart Docker Stats.
5. Use **Send test** in the notification panel.

Messages will appear in the Slack channel bound to that webhook.

---

## 🔔 Telegram Notifications Setup

To send alerts to Telegram:
1. Create a bot with [@BotFather](https://t.me/BotFather) and obtain the **bot token**.
2. Get your chat ID by sending the bot a message and inspecting `https://api.telegram.org/bot<token>/getUpdates`.
3. Add these variables:
   ```env
   TELEGRAM_BOT_TOKEN=123456:abcde...
   TELEGRAM_CHAT_ID=123456789
   ```
4. Restart Docker Stats.
5. Use **Send test** in the notification panel.

The bot will send messages to your chosen chat.

---

## 🔔 Discord Notifications Setup

To send alerts to Discord:
1. Create a **Webhook** in your Discord channel settings.
2. Copy the webhook URL.
3. Add this variable:
   ```env
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
   ```
4. Restart Docker Stats.
5. Use **Send test** in the notification panel.

Notifications will show up in that Discord channel.

---

## 🔔 ntfy Notifications Setup

Docker Stats can publish directly to [ntfy](https://docs.ntfy.sh/). This works with the public `ntfy.sh` service or a self-hosted ntfy server.

### Basic ntfy.sh setup
1. Install the ntfy mobile app or open the web app.
2. Choose a topic name, for example `dockerstats-home`.
3. Subscribe to that topic from your phone or browser.
4. Add these variables:
   ```env
   NTFY_TOPIC=dockerstats-home
   NTFY_SERVER_URL=https://ntfy.sh
   ```
5. Restart Docker Stats.
6. Use **Send test** in the notification panel.

That is equivalent to sending this manually:
```bash
curl -H "Title: Docker Stats Test" -d "Test notification from Docker Stats" https://ntfy.sh/dockerstats-home
```

### Self-hosted ntfy server
1. Deploy or use your own ntfy instance, for example `https://ntfy.example.com`.
2. Create or choose a topic on that server.
3. Point Docker Stats to it:
   ```env
   NTFY_TOPIC=dockerstats-prod
   NTFY_SERVER_URL=https://ntfy.example.com
   ```
4. Restart Docker Stats.
5. Use **Send test**.

### ntfy authentication

If your ntfy topic is protected, configure one of these methods:

Use a bearer token:
```env
NTFY_TOPIC=dockerstats-prod
NTFY_SERVER_URL=https://ntfy.example.com
NTFY_TOKEN=tk_your_token_here
```

Or use username/password:
```env
NTFY_TOPIC=dockerstats-prod
NTFY_SERVER_URL=https://ntfy.example.com
NTFY_USERNAME=myuser
NTFY_PASSWORD=mysecret
```

### Optional ntfy extras

You can also configure:
```env
NTFY_TAGS=docker,monitoring,prod
NTFY_MARKDOWN=false
```

- `NTFY_TAGS` adds extra tags to every notification. Docker Stats also appends `dockerstats` and the event type automatically.
- `NTFY_MARKDOWN=true` tells ntfy to render the message as Markdown.

---

## 🔔 Generic Webhook / curl Notifications Setup

If you do not want a built-in provider, Docker Stats can send a generic HTTP request to any endpoint. This covers the "basic curl request" use case without executing shell commands inside the container.

### Option A: zero-config JSON webhook
1. Create or choose an HTTP endpoint that accepts JSON.
2. Add the webhook URL:
   ```env
   GENERIC_WEBHOOK_URL=https://example.com/hooks/dockerstats
   ```
3. Restart Docker Stats.
4. Use **Send test**.

When `GENERIC_WEBHOOK_BODY_TEMPLATE` is not set, Docker Stats sends JSON by default. The payload looks like this:

```json
{
  "app": "Docker Stats",
  "host": "docker-host",
  "title": "Docker Stats CPU",
  "message": "nginx: CPU usage 92.3% exceeded 80.0% for 10s",
  "priority": "1",
  "priority_label": "high",
  "event_type": "cpu",
  "container": "nginx",
  "container_id": "abc123",
  "value": 92.3,
  "prev_value": null,
  "timestamp": 1712345678.123,
  "timestamp_iso": "2024-04-05T12:34:38.123000+00:00",
  "event": {
    "type": "cpu",
    "cid": "abc123",
    "container": "nginx",
    "value": 92.3,
    "timestamp": 1712345678.123,
    "msg": "nginx: CPU usage 92.3% exceeded 80.0% for 10s"
  }
}
```

Equivalent manual test:
```bash
curl -X POST https://example.com/hooks/dockerstats \
  -H "Content-Type: application/json" \
  -d '{"message":"Test notification from Docker Stats"}'
```

### Option B: plain-text body, similar to `curl -d "..."`

If your endpoint expects raw text instead of JSON:
1. Add the webhook URL.
2. Define a body template.
3. Set the content type.

Example:
```env
GENERIC_WEBHOOK_URL=https://example.com/hooks/dockerstats
GENERIC_WEBHOOK_METHOD=POST
GENERIC_WEBHOOK_CONTENT_TYPE=text/plain; charset=utf-8
GENERIC_WEBHOOK_BODY_TEMPLATE=[{event_type}] {title}\n{message}
```

Equivalent manual test:
```bash
curl -X POST https://example.com/hooks/dockerstats \
  -H "Content-Type: text/plain; charset=utf-8" \
  -d "[cpu] Docker Stats CPU\nnginx: CPU usage 92.3% exceeded 80.0% for 10s"
```

### Option C: custom headers for tokens or routing

`GENERIC_WEBHOOK_HEADERS` accepts a JSON object:

```env
GENERIC_WEBHOOK_URL=https://example.com/hooks/dockerstats
GENERIC_WEBHOOK_HEADERS={"Authorization":"Bearer super-secret-token","X-Environment":"prod"}
```

This is useful for services such as n8n, Home Assistant, custom APIs, or internal webhook collectors.

### Available placeholders for `GENERIC_WEBHOOK_BODY_TEMPLATE`

You can use these placeholders in the body template:
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

Example with more context:
```env
GENERIC_WEBHOOK_BODY_TEMPLATE={timestamp_iso} {host} [{event_type}] {container}: {message}
```

---

## 🎮 GPU Metrics Support

Docker Monitor supports NVIDIA GPU metrics for containers.

**How to enable GPU metrics:**
1. Run your container with GPU access (e.g. add `--gpus all` to `docker run` or use the appropriate Docker Compose option).
2. Make sure NVIDIA drivers are installed on the host and `nvidia-smi` is available inside the container.
3. Set the environment variable `GPU_METRICS_ENABLED=true` when starting the app or in your environment file.
   - Example for Docker Compose:
     ```yaml
     environment:
       - GPU_METRICS_ENABLED=true
     ```
4. (Optional) For more accurate readings, keep `nvidia-ml-py` available in the container.

If available, GPU usage and memory stats will be displayed in the UI for each container.

---

## 🛡️ Authentication & Secrets

- There are **no built-in default credentials** anymore.
- On first startup with `AUTH_ENABLED=true`, you must provide:
  - `AUTH_USER`
  - `AUTH_PASSWORD` or `AUTH_PASSWORD_FILE`
- Set `APP_SECRET_KEY` or `APP_SECRET_KEY_FILE` to keep sessions stable across restarts.
- `APP_VERSION` controls the version string shown in the UI footer and defaults to `v0.9.8`.
- If you want to run the app without authentication, set `AUTH_ENABLED=false` explicitly.

---

## ℹ️ CPU Usage Calculation & Exited Containers

- **CPU usage percentage** is calculated **per core** and the total number of available cores is displayed. This means the maximum possible usage is `100% × number of cores`, allowing you to interpret the percentage correctly on multi-core systems.
- The **CPU usage bar** treats the combined usage of all available cores as 100%, automatically adjusting the visualization for systems with different core counts.
- **Exited containers** (stopped containers) are now shown in the main table. You can restart them directly from the interface, and their names are highlighted in red for easy identification.

---

## 📦 Installation

- Clone the repository:
  ```bash
  git clone https://github.com/Drakonis96/dockerstats
  cd dockerstats
  ```
- Start the service with Docker Compose:
  ```bash
  docker compose up --build -d
  ```

## 🖥️ Access
Once running, open your browser and go to:

```
http://localhost:5001
```

Use the **Server IP** field (and "Use Custom IP" checkbox) in the UI to point the links to another host if needed.

---

### 🔑 Login Screen Mode

You can choose between a **dedicated login page** (see screenshots) or a **simple popup** for user/password authentication.  
This is controlled by the `LOGIN_MODE` environment variable in your Docker Compose file:

```yaml
LOGIN_MODE: "page"  # Login mode - 'popup' or 'page'
```

Set to `"page"` for a full login screen, or `"popup"` for a simple authentication dialog.

---

## 📸 Screenshots
<div align="center">
  <img src="screenshots/Screenshot 1.png" alt="Screenshot 1" width="600">
  <img src="screenshots/Screenshot 2.png" alt="Screenshot 2" width="600">
  <img src="screenshots/Screenshot 3.png" alt="Screenshot 3" width="600">
  <img src="screenshots/Screenshot 4.png" alt="Screenshot 4" width="600">
</div>

---

## 📝 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
