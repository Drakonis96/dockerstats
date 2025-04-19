<div align="center">
  <img src="logo.png" alt="Docker Monitor" width="150">
</div>

# Docker Monitor

**Docker Monitor** is a lightweight and responsive web application for real-time monitoring of Docker container resource usage.

It displays **CPU and RAM consumption** per container in a simple, visual interface, allowing you to switch between table view and several types of charts (bar, line, and pie).

---

## 🚀 Features

- 🟢 Real-time or near real-time container monitoring
- 📊 Multiple visualization modes: Table, Bar Chart, Line Chart, Pie Chart
- 🧠 Advanced filters:
  - By container name
  - By status (running, exited)
  - By time range: 5 minutes to 24 hours
  - By sorting: name, CPU, RAM, combined usage
- 🌗 Light / Dark mode toggle (☀️ / 🌙)
- 🔝 Scroll-to-top button for long lists
- 📁 Simple Docker-based deployment

---

## 📦 Installation

1. Clone the repository:

2. Build and run using Docker Compose:

## 🖥️ Access
Once running, open your browser and go to:

http://localhost:5001
docker compose up --build -d

## 📝 License
MIT License