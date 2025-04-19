import threading
import time
import collections
from flask import Flask, jsonify, request, render_template_string
import docker
import requests_unixsocket

# Patch requests for http+docker:// support
requests_unixsocket.monkeypatch()

app = Flask(__name__, static_url_path='', static_folder='.')

# Docker client via Unix socket
client = docker.DockerClient(base_url='unix://var/run/docker.sock')

# In-memory history buffer
history = {}
SAMPLE_INTERVAL = 5      # seconds
MAX_SECONDS     = 86400  # keep up to 24h of history

def calc_cpu_percent(stats):
    try:
        cpu_delta    = stats["cpu_stats"]["cpu_usage"]["total_usage"]     - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"]["system_cpu_usage"]             - stats["precpu_stats"]["system_cpu_usage"]
        if system_delta > 0 and cpu_delta > 0:
            cpus = len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [])) or 1
            return (cpu_delta / system_delta) * cpus * 100.0
    except:
        pass
    return 0.0

def sample_metrics():
    while True:
        for c in client.containers.list(all=True):
            try:
                stats = c.stats(stream=False)
                cpu   = calc_cpu_percent(stats)
                mu    = stats["memory_stats"]["usage"]
                ml    = stats["memory_stats"].get("limit",1)
                mem   = (mu/ml)*100 if ml else 0
            except:
                cpu = mem = 0.0
            dq = history.setdefault(c.id, collections.deque(maxlen=MAX_SECONDS//SAMPLE_INTERVAL))
            dq.append((time.time(), cpu, mem, c.status, c.name))
        time.sleep(SAMPLE_INTERVAL)

threading.Thread(target=sample_metrics, daemon=True).start()

INDEX_HTML = '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"> 
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Docker Monitor</title>
  <link rel="icon" href="/logo.png">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    /* Transparent header matching body */
    nav.navbar { background: transparent !important; padding: 0; }
    /* Container with fixed height to hold logo */
    nav.navbar .container {
      height: 100px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    /* Logo slightly larger */
    nav.navbar img {
      width: 120px;
      height: 120px;
    }
    /* Adjust page content down by header height + margin */
    body {
      padding-top: calc(100px + 1rem);
      transition: background .3s, color .3s;
    }

    /* Controls & table styling */
    .form-control, .form-select {
      transition: background .3s, color .3s, border-color .3s;
    }
    .form-control::placeholder { color: #666; transition: color .3s; }
    .table, .table th, .table td {
      transition: background .3s, color .3s;
    }

    /* Dark mode */
    .dark-mode body {
      background: #121212;
      color: #eee;
    }
    .dark-mode .form-control, .dark-mode .form-select {
      background: #2a2a2a;
      color: #eee;
      border-color: #444;
    }
    .dark-mode .form-control::placeholder { color: #bbb; }
    .dark-mode .table, .dark-mode th, .dark-mode td {
      background-color: #2a2a2a;
      color: #eee;
    }
    .dark-mode .table-striped tbody tr:nth-of-type(odd) {
      background-color: #1f1f1f;
    }

    /* Floating buttons */
    #themeToggle, #scrollTop {
      position: fixed;
      bottom: 1rem;
      width: 3rem;
      height: 3rem;
      font-size: 1.5rem;
      line-height: 3rem;
      text-align: center;
      border-radius: 50%;
      background: rgba(255,255,255,0.8);
      cursor: pointer;
      z-index: 1000;
      transition: background .3s, color .3s;
    }
    #scrollTop { right: 1rem; }
    #themeToggle { right: 5rem; }
    .dark-mode #themeToggle, .dark-mode #scrollTop {
      background: rgba(0,0,0,0.6);
      color: #ffd;
    }
  </style>
</head>
<body>
  <!-- Header with transparent background -->
  <nav class="navbar fixed-top">
    <div class="container">
      <img src="/logo.png" alt="logo">
    </div>
  </nav>

  <!-- Floating buttons -->
  <div id="themeToggle">🌙</div>
  <div id="scrollTop">⬆️</div>

  <!-- Filters & view controls -->
  <div class="container">
    <div class="row g-3 mb-3">
      <div class="col-md-2"><input id="filterName" class="form-control" placeholder="Filter by name"></div>
      <div class="col-md-2">
        <select id="filterStatus" class="form-select">
          <option value="">All statuses</option>
          <option value="running">Running</option>
          <option value="exited">Exited</option>
        </select>
      </div>
      <div class="col-md-3">
        <select id="filterRange" class="form-select">
          <option value="300">Last 5 minutes</option>
          <option value="900">Last 15 minutes</option>
          <option value="1800">Last 30 minutes</option>
          <option value="3600">Last 1 hour</option>
          <option value="7200">Last 2 hours</option>
          <option value="14400">Last 4 hours</option>
          <option value="21600">Last 6 hours</option>
          <option value="43200">Last 12 hours</option>
          <option value="86400" selected>Last 24 hours</option>
        </select>
      </div>
      <div class="col-md-2">
        <select id="sortBy" class="form-select">
          <option value="name">Sort by Name</option>
          <option value="cpu">Sort by CPU %</option>
          <option value="mem">Sort by RAM %</option>
          <option value="combined">Sort by Combined %</option>
          <option value="status">Sort by Status</option>
        </select>
      </div>
      <div class="col-md-1">
        <select id="sortDir" class="form-select">
          <option value="asc">Asc</option>
          <option value="desc">Desc</option>
        </select>
      </div>
      <div class="col-md-2"><input id="maxItems" type="number" min="1" value="10" class="form-control" placeholder="Max items"></div>
    </div>

    <div class="mb-3">
      <select id="viewType" class="form-select w-auto">
        <option value="table" selected>Table</option>
        <option value="bar">Bar Chart</option>
        <option value="line">Line Chart</option>
        <option value="pie">Pie Chart</option>
      </select>
    </div>

    <div id="tableView" class="table-responsive mb-4">
      <table id="metricsTable" class="table table-striped">
        <thead>
          <tr><th>Name</th><th>CPU %</th><th>RAM %</th><th>Status</th></tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>
    <canvas id="chartView" style="display:none; max-height:480px;"></canvas>
  </div>

  <script>
    // Toggle dark/light mode
    const themeToggle = document.getElementById('themeToggle');
    themeToggle.onclick = () => {
      document.documentElement.classList.toggle('dark-mode');
      themeToggle.textContent = document.documentElement.classList.contains('dark-mode') ? '☀️' : '🌙';
    };

    // Scroll to top
    document.getElementById('scrollTop').onclick = () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    let chart = null;
    async function fetchMetrics() {
      const name_f   = document.getElementById('filterName').value.toLowerCase();
      const status   = document.getElementById('filterStatus').value;
      const range    = document.getElementById('filterRange').value;
      const sortBy   = document.getElementById('sortBy').value;
      const sortDir  = document.getElementById('sortDir').value;
      const maxItems = parseInt(document.getElementById('maxItems').value) || 0;

      let url = `/api/metrics?range=${range}&sort=${sortBy}&dir=${sortDir}&max=${maxItems}`;
      if (name_f) url += `&name=${encodeURIComponent(name_f)}`;
      if (status) url += `&status=${status}`;

      const res = await fetch(url);
      const data = await res.json();
      renderTable(data);
      renderChart(data);
    }

    function renderTable(data) {
      const tbody = document.querySelector('#metricsTable tbody');
      tbody.innerHTML = '';
      data.forEach(d => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${d.name}</td><td>${d.cpu.toFixed(2)}</td><td>${d.mem.toFixed(2)}</td><td>${d.status}</td>`;
        tbody.appendChild(tr);
      });
    }

    function renderChart(data) {
      const view = document.getElementById('viewType').value;
      const ctx  = document.getElementById('chartView');
      if (view === 'table') { ctx.style.display = 'none'; return; }
      ctx.style.display = 'block';
      if (chart) chart.destroy();

      const labels = data.map(d => d.name),
            cpu    = data.map(d => d.cpu),
            mem    = data.map(d => d.mem);
      let cfg;
      if (view === 'bar') {
        cfg = { type:'bar', data:{ labels, datasets:[
          { label:'CPU %', data:cpu },
          { label:'RAM %', data:mem }
        ]}};
      } else if (view === 'line') {
        cfg = { type:'line', data:{ labels, datasets:[
          { label:'CPU %', data:cpu, fill:false },
          { label:'RAM %', data:mem, fill:false }
        ]}};
      } else {
        cfg = { type:'pie', data:{ labels, datasets:[
          { label:'CPU %', data:cpu }
        ]}};
      }
      chart = new Chart(ctx, cfg);
    }

    document.querySelectorAll('select,input').forEach(el => el.onchange = fetchMetrics);
    setInterval(fetchMetrics, 5000);
    fetchMetrics();
  </script>
</body>
</html>'''

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route('/api/metrics')
def api_metrics():
    name_f   = request.args.get('name','').lower()
    status   = request.args.get('status','')
    rng      = int(request.args.get('range',300))
    sort_by  = request.args.get('sort','name')
    sort_dir = request.args.get('dir','asc')
    max_i    = int(request.args.get('max',0))

    cutoff = time.time() - rng
    rows   = []
    for cid, dq in history.items():
        samp = next((s for s in reversed(dq) if s[0]>=cutoff), None)
        if not samp:
            continue
        ts, cpu, mem, st, name = samp
        if name_f and name_f not in name.lower():
            continue
        if status and st != status:
            continue
        rows.append({'name':name,'cpu':cpu,'mem':mem,'combined':cpu+mem,'status':st})

    rows.sort(key=lambda x: x.get(sort_by, x['name']))
    if sort_dir == 'desc':
        rows.reverse()
    if max_i > 0:
        rows = rows[:max_i]

    return jsonify(rows)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
