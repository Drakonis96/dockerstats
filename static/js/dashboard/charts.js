const COMPARISON_TYPES = {
  cpu: {
    title: 'CPU usage',
    axisLabel: 'CPU usage (%)',
    dataKey: 'cpu',
    tooltipSuffix: '%',
    datasetLabel: 'CPU usage',
    max: 100,
  },
  ram: {
    title: 'RAM usage',
    axisLabel: 'RAM usage (%)',
    dataKey: 'mem',
    tooltipSuffix: '%',
    datasetLabel: 'RAM usage',
    max: 100,
  },
  uptime: {
    title: 'Uptime',
    axisLabel: 'Uptime',
    dataKey: 'uptime_sec',
    tooltipSuffix: '',
    datasetLabel: 'Uptime',
    max: null,
  },
};

function cssVar(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

function getChartTheme() {
  return {
    text: cssVar('--ds-text', '#163329'),
    muted: cssVar('--ds-muted', '#5d7268'),
    grid: cssVar('--ds-border', 'rgba(22, 51, 41, 0.12)'),
    panel: cssVar('--ds-panel', '#ffffff'),
    accent: cssVar('--ds-accent', '#156f63'),
    accentSoft: 'rgba(21, 111, 99, 0.18)',
    accentAlt: '#1f8f7f',
    accentAltSoft: 'rgba(31, 143, 127, 0.18)',
    compare: [
      '#156f63',
      '#1f8f7f',
      '#3f9d71',
      '#6cb66d',
      '#92c85c',
      '#d4b04c',
      '#d47f4c',
      '#bb3e3e',
      '#805ad5',
      '#2563eb',
    ],
  };
}

function formatDurationLabel(totalSeconds) {
  const seconds = Math.max(0, Number(totalSeconds) || 0);
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const parts = [];
  if (days > 0) parts.push(`${days}d`);
  if (hours > 0 || parts.length > 0) parts.push(`${hours}h`);
  if (minutes > 0 || parts.length > 0) parts.push(`${minutes}m`);
  parts.push(`${secs}s`);
  return parts.join(' ');
}

function buildTooltipColors(theme) {
  return {
    backgroundColor: theme.panel,
    borderColor: theme.grid,
    borderWidth: 1,
    titleColor: theme.text,
    bodyColor: theme.text,
    footerColor: theme.muted,
    padding: 12,
    displayColors: true,
    boxPadding: 4,
  };
}

export function createChartController(ctx) {
  Chart.register(ChartZoom);

  function ensureHistoryModal() {
    if (!ctx.elements.historyChartModalEl) {
      return null;
    }
    ctx.state.historyChartModal = bootstrap.Modal.getOrCreateInstance(ctx.elements.historyChartModalEl);
    return ctx.state.historyChartModal;
  }

  function ensureComparisonModal() {
    if (!ctx.elements.comparisonChartModalEl) {
      return null;
    }
    ctx.state.comparisonChartModal = bootstrap.Modal.getOrCreateInstance(ctx.elements.comparisonChartModalEl);
    return ctx.state.comparisonChartModal;
  }

  function destroyUsageChart() {
    if (ctx.state.usageChart) {
      ctx.state.usageChart.destroy();
      ctx.state.usageChart = null;
    }
  }

  function destroyComparisonChart() {
    if (ctx.state.comparisonChart) {
      ctx.state.comparisonChart.destroy();
      ctx.state.comparisonChart = null;
    }
  }

  function renderHistoryChart(historyData) {
    const theme = getChartTheme();
    const { chartCanvas, chartStatus } = ctx.elements;
    ctx.state.lastHistoryChartData = historyData;

    if (!historyData || !Array.isArray(historyData.timestamps) || historyData.timestamps.length === 0) {
      chartStatus.textContent = 'No historical data is available for the selected container and time range.';
      chartStatus.dataset.state = 'idle';
      destroyUsageChart();
      return;
    }

    chartStatus.textContent = '';
    chartStatus.dataset.state = 'ready';
    const labels = historyData.timestamps.map((timestamp) => new Date(timestamp * 1000).toLocaleString());
    const datasets = [
      {
        label: 'CPU usage (%)',
        data: historyData.cpu_usage,
        borderColor: theme.accent,
        backgroundColor: theme.accentSoft,
        pointBackgroundColor: theme.accent,
        pointBorderColor: theme.panel,
        borderWidth: 2,
        pointRadius: ctx.state.currentChartType === 'line' ? 2.5 : 0,
        pointHoverRadius: 4,
        tension: 0.25,
        fill: ctx.state.currentChartType !== 'line',
      },
      {
        label: 'RAM usage (%)',
        data: historyData.ram_usage,
        borderColor: theme.accentAlt,
        backgroundColor: theme.accentAltSoft,
        pointBackgroundColor: theme.accentAlt,
        pointBorderColor: theme.panel,
        borderWidth: 2,
        pointRadius: ctx.state.currentChartType === 'line' ? 2.5 : 0,
        pointHoverRadius: 4,
        tension: 0.25,
        fill: ctx.state.currentChartType !== 'line',
      },
    ];

    destroyUsageChart();
    ctx.state.usageChart = new Chart(chartCanvas, {
      type: ctx.state.currentChartType,
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 260 },
        interaction: {
          mode: 'index',
          intersect: false,
        },
        hover: {
          mode: 'nearest',
          intersect: false,
        },
        scales: {
          y: {
            beginAtZero: true,
            min: 0,
            max: 100,
            title: {
              display: true,
              text: 'Usage (%)',
              color: theme.muted,
              font: { weight: '700' },
            },
            ticks: {
              color: theme.muted,
              callback: (value) => `${value}%`,
            },
            grid: {
              color: theme.grid,
              drawBorder: false,
            },
          },
          x: {
            title: {
              display: true,
              text: 'Captured at',
              color: theme.muted,
              font: { weight: '700' },
            },
            ticks: {
              color: theme.muted,
              autoSkip: true,
              maxTicksLimit: 8,
              maxRotation: 0,
            },
            grid: {
              color: theme.grid,
              drawBorder: false,
            },
          },
        },
        plugins: {
          legend: {
            position: 'top',
            align: 'start',
            labels: {
              color: theme.text,
              usePointStyle: true,
              boxWidth: 10,
              boxHeight: 10,
            },
          },
          tooltip: {
            ...buildTooltipColors(theme),
            callbacks: {
              label: (tooltipItem) => `${tooltipItem.dataset.label}: ${Number(tooltipItem.parsed.y || 0).toFixed(1)}%`,
            },
          },
          zoom: {
            limits: {
              y: { min: 0, max: 100 },
            },
            pan: {
              enabled: true,
              mode: 'x',
              modifierKey: null,
            },
            zoom: {
              drag: { enabled: false },
              wheel: { enabled: true },
              pinch: { enabled: true },
              mode: 'x',
            },
          },
        },
      },
    });
  }

  async function fetchAndRenderChart() {
    if (!ctx.state.currentChartContainerId) {
      return;
    }

    const { filterRange, chartStatus } = ctx.elements;
    const url = `/api/history/${ctx.state.currentChartContainerId}?range=${filterRange.value}`;
    chartStatus.textContent = 'Loading chart data…';
    chartStatus.dataset.state = 'loading';

    try {
      const response = await fetch(url, { credentials: 'include' });
      if (!response.ok) {
        chartStatus.textContent = `Unable to load chart data (${response.status}).`;
        chartStatus.dataset.state = 'error';
        destroyUsageChart();
        return;
      }
      renderHistoryChart(await response.json());
      requestAnimationFrame(() => ctx.state.usageChart?.resize());
    } catch (error) {
      console.error('Error fetching chart data:', error);
      chartStatus.textContent = 'Network error while loading chart data.';
      chartStatus.dataset.state = 'error';
      destroyUsageChart();
    }
  }

  function showHistoryChart(containerId, containerName) {
    ctx.state.currentChartContainerId = containerId;
    ctx.state.currentChartContainerName = containerName;
    ctx.elements.chartTitle.textContent = `Historical usage for ${containerName}`;
    ctx.elements.chartMeta.textContent = `Container ${containerId.substring(0, 12)} • Range follows the main workspace filter.`;

    const modal = ensureHistoryModal();
    if (!modal) {
      return;
    }

    const modalElement = ctx.elements.historyChartModalEl;
    const runFetch = () => {
      fetchAndRenderChart();
      requestAnimationFrame(() => ctx.state.usageChart?.resize());
    };

    if (modalElement?.classList.contains('show')) {
      runFetch();
      return;
    }

    modalElement?.addEventListener('shown.bs.modal', runFetch, { once: true });
    requestAnimationFrame(() => modal.show());
  }

  function setComparisonType(compareType) {
    const normalizedType = COMPARISON_TYPES[compareType] ? compareType : 'cpu';
    ctx.state.currentComparisonType = normalizedType;
    ctx.elements.comparisonChartTabs.forEach((tab) => {
      const isActive = tab.dataset.compareType === normalizedType;
      tab.classList.toggle('is-active', isActive);
      tab.setAttribute('aria-selected', String(isActive));
    });
    ctx.elements.comparisonChartTitle.textContent = `${COMPARISON_TYPES[normalizedType].title} comparison`;
  }

  function renderComparisonChart(items, compareType) {
    const theme = getChartTheme();
    const { comparisonChartCanvas, comparisonChartStatus } = ctx.elements;
    const config = COMPARISON_TYPES[compareType] || COMPARISON_TYPES.cpu;
    ctx.state.lastComparisonChartData = items;
    ctx.state.currentComparisonType = compareType;

    if (!Array.isArray(items) || items.length === 0) {
      comparisonChartStatus.textContent = 'No containers are available for this comparison yet.';
      comparisonChartStatus.dataset.state = 'idle';
      destroyComparisonChart();
      return;
    }

    comparisonChartStatus.textContent = '';
    comparisonChartStatus.dataset.state = 'ready';
    destroyComparisonChart();

    ctx.state.comparisonChart = new Chart(comparisonChartCanvas, {
      type: 'bar',
      data: {
        labels: items.map((item) => item.name),
        datasets: [
          {
            label: config.datasetLabel,
            data: items.map((item) => Number(item[config.dataKey]) || 0),
            borderRadius: 10,
            borderSkipped: false,
            backgroundColor: items.map((_, index) => theme.compare[index % theme.compare.length]),
            hoverBackgroundColor: items.map((_, index) => theme.compare[index % theme.compare.length]),
          },
        ],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 260 },
        interaction: {
          mode: 'nearest',
          intersect: true,
        },
        scales: {
          x: {
            beginAtZero: true,
            max: config.max,
            title: {
              display: true,
              text: config.axisLabel,
              color: theme.muted,
              font: { weight: '700' },
            },
            ticks: {
              color: theme.muted,
              callback: (value) => (compareType === 'uptime' ? formatDurationLabel(value) : `${value}${config.tooltipSuffix}`),
            },
            grid: {
              color: theme.grid,
              drawBorder: false,
            },
          },
          y: {
            ticks: {
              color: theme.text,
            },
            grid: {
              display: false,
              drawBorder: false,
            },
          },
        },
        plugins: {
          legend: {
            display: false,
          },
          tooltip: {
            ...buildTooltipColors(theme),
            callbacks: {
              label: (tooltipItem) => {
                const value = Number(tooltipItem.parsed.x || 0);
                return compareType === 'uptime'
                  ? `${config.datasetLabel}: ${formatDurationLabel(value)}`
                  : `${config.datasetLabel}: ${value.toFixed(1)}${config.tooltipSuffix}`;
              },
              footer: (tooltipItems) => {
                const item = items[tooltipItems[0]?.dataIndex ?? -1];
                return item?.status ? `Status: ${item.status}` : '';
              },
            },
          },
          zoom: {
            pan: {
              enabled: true,
              mode: 'x',
            },
            zoom: {
              wheel: { enabled: true },
              pinch: { enabled: true },
              mode: 'x',
            },
          },
        },
      },
    });
  }

  async function fetchComparisonData() {
    const compareType = ctx.state.currentComparisonType || 'cpu';
    const topN = Math.max(1, parseInt(ctx.elements.comparisonChartTopN.value, 10) || parseInt(ctx.elements.compareTopN.value, 10) || 10);
    ctx.elements.comparisonChartTopN.value = String(topN);
    ctx.elements.compareTopN.value = String(topN);
    ctx.elements.comparisonChartStatus.textContent = 'Loading comparison data…';
    ctx.elements.comparisonChartStatus.dataset.state = 'loading';

    try {
      const response = await fetch(`/api/compare/${compareType}?topN=${topN}`, { credentials: 'include' });
      if (!response.ok) {
        ctx.elements.comparisonChartStatus.textContent = `Unable to load comparison data (${response.status}).`;
        ctx.elements.comparisonChartStatus.dataset.state = 'error';
        destroyComparisonChart();
        return;
      }
      renderComparisonChart(await response.json(), compareType);
      requestAnimationFrame(() => ctx.state.comparisonChart?.resize());
    } catch (error) {
      console.error('Error fetching comparison data:', error);
      ctx.elements.comparisonChartStatus.textContent = 'Network error while loading comparison data.';
      ctx.elements.comparisonChartStatus.dataset.state = 'error';
      destroyComparisonChart();
    }
  }

  function openComparison(compareType) {
    setComparisonType(compareType);
    const modal = ensureComparisonModal();
    if (!modal) {
      return;
    }

    const modalElement = ctx.elements.comparisonChartModalEl;
    const runFetch = () => {
      fetchComparisonData();
      requestAnimationFrame(() => ctx.state.comparisonChart?.resize());
    };

    if (modalElement?.classList.contains('show')) {
      runFetch();
      return;
    }

    ctx.elements.comparisonChartTopN.value = ctx.elements.compareTopN.value || '10';
    modalElement?.addEventListener('shown.bs.modal', runFetch, { once: true });
    requestAnimationFrame(() => modal.show());
  }

  function refreshOpenCharts() {
    if (ctx.elements.historyChartModalEl?.classList.contains('show') && ctx.state.lastHistoryChartData) {
      renderHistoryChart(ctx.state.lastHistoryChartData);
    }
    if (ctx.elements.comparisonChartModalEl?.classList.contains('show') && ctx.state.lastComparisonChartData) {
      renderComparisonChart(ctx.state.lastComparisonChartData, ctx.state.currentComparisonType || 'cpu');
    }
  }

  function resizeOpenCharts() {
    ctx.state.usageChart?.resize();
    ctx.state.comparisonChart?.resize();
  }

  function init() {
    ensureHistoryModal();
    ensureComparisonModal();

    ctx.elements.chartTypeRadios.forEach((radio) => {
      radio.addEventListener('change', (event) => {
        ctx.state.currentChartType = event.target.value;
        localStorage.setItem('chartType', event.target.value);
        if (ctx.state.lastHistoryChartData) {
          renderHistoryChart(ctx.state.lastHistoryChartData);
        }
      });
    });

    ctx.elements.resetHistoryChartZoomBtn?.addEventListener('click', () => {
      ctx.state.usageChart?.resetZoom?.();
    });

    ctx.elements.comparisonChartResetZoomBtn?.addEventListener('click', () => {
      ctx.state.comparisonChart?.resetZoom?.();
    });

    ctx.elements.comparisonChartRefreshBtn?.addEventListener('click', fetchComparisonData);

    ctx.elements.comparisonChartTabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        setComparisonType(tab.dataset.compareType);
        fetchComparisonData();
      });
    });

    ctx.elements.historyChartModalEl?.addEventListener('shown.bs.modal', () => {
      requestAnimationFrame(() => ctx.state.usageChart?.resize());
    });
    ctx.elements.comparisonChartModalEl?.addEventListener('shown.bs.modal', () => {
      requestAnimationFrame(() => ctx.state.comparisonChart?.resize());
    });

    window.addEventListener('resize', resizeOpenCharts);
  }

  return {
    init,
    fetchAndRenderChart,
    showHistoryChart,
    openComparison,
    refreshOpenCharts,
  };
}
