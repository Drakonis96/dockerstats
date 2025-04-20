<div align="center">
  <img src="logo.png" alt="Docker Monitor" width="150">
</div>

# Docker Monitor

**Docker Monitor** is a lightweight and responsive web application for real-time monitoring of Docker container resource usage.

It displays **CPU and RAM consumption** per container in a simple, visual interface, allowing you to switch between table view and several types of charts (bar, line, and pie).

---

## 🚀 Features

- 🟢 Real-time container monitoring
- 📊 Multiple visualization modes: Table, Bar Chart, Line Chart
- 🧠 Advanced filters: 
  - Name CPU % RAM % Status Size (RW) Uptime (D H M S) Net I/O Block I/O Image Ports Restarts Logs Charts UI Total FS Procs Mem Limit (MB)
- 🌗 Light / Dark mode toggle (☀️ / 🌙)
- 🔝 Scroll-to-top button for long lists
- 🌐 UI Button: opens container’s exposed port in a new browser tab
- 🆔 Custom Server IP: choose between localhost or custom IP for UI links
- 🛠️ Persisted settings: remembers filters, theme, chart type, and column visibility via localStorage
- 🔄 Dynamic column toggles: show or hide any column on demand

---

## 📦 Installation

- Clone the repository:
  ```bash
  git clone https://github.com/Drakonis96/dockerstats
  cd docker-monitor
  ```
- Start the service via Docker Compose:
  ```bash
  docker compose up --build -d
  ```

## 🖥️ Access
Once running, open your browser and go to:

```
http://localhost:5001
```

Use the **Server IP** field (and "Use Custom IP" checkbox) in the UI controls to point the UI buttons to a different host if needed.

---

## 📝 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.