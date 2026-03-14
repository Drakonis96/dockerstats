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
  - **Pushover, Slack, Telegram & Discord integration:** Receive alerts on your mobile device or chat apps when containers exceed CPU/RAM thresholds or change status. (See configuration below)
- 💬 **Status messages:** Visual feedback for actions like saving settings, checking updates, or errors

---

## ⚡ Backend Options: Docker API & cAdvisor

You can choose on the WebUI how metrics are collected:
- **Docker API only:** Default, works for most setups.
- **Docker API + cAdvisor:** For advanced metrics and compatibility, you can enable cAdvisor support. This is useful if you want more detailed stats or run Docker in environments where the API alone is limited.

---

## 🔔 Pushover Notifications Setup

To receive push notifications on your phone or device:
1. Create a free account at [Pushover](https://pushover.net/) and install the app on your device.
2. Get your **User Key** and create an **Application/API Token**.
3. Set these values as environment variables:
   - `PUSHOVER_TOKEN` *(application token)*
   - `PUSHOVER_USER` *(user key)*
4. Enable Pushover notifications in the settings.

You will now receive alerts for CPU/RAM thresholds and container status changes directly to your device.

---

## 🔔 Slack Notifications Setup

To send alerts to Slack:
1. Create an **Incoming Webhook** at <https://slack.com/apps> and copy the webhook URL.
2. Set the environment variable `SLACK_WEBHOOK_URL` with this URL.
3. Enable notifications in the settings.

Messages will appear in the channel you selected for the webhook.

---

## 🔔 Telegram Notifications Setup

To send alerts to Telegram:
1. Create a bot with [@BotFather](https://t.me/BotFather) and obtain the **bot token**.
2. Get your chat ID (you can message the bot and check `https://api.telegram.org/bot<token>/getUpdates`).
3. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` as environment variables.
4. Enable notifications in the settings.

The bot will send messages to your chosen chat.

---

## 🔔 Discord Notifications Setup

To send alerts to Discord:
1. Create a **Webhook** in your Discord channel settings and copy its URL.
2. Set `DISCORD_WEBHOOK_URL` as an environment variable.
3. Enable notifications in the settings.

Notifications will show up in that Discord channel.

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
- `APP_VERSION` controls the version string shown in the UI footer and defaults to `v0.8.1`.
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
