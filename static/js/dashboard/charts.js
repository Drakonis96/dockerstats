export function createChartController(ctx) {
  Chart.register(ChartZoom);

  function renderChart(historyData) {
    const { chartCanvas, chartStatus } = ctx.elements;

    if (!historyData || !historyData.timestamps || historyData.timestamps.length === 0) {
      chartStatus.textContent = 'No historical data available for the selected range.';
      if (ctx.state.usageChart) {
        ctx.state.usageChart.destroy();
        ctx.state.usageChart = null;
      }
      return;
    }

    chartStatus.textContent = '';
    const labels = historyData.timestamps.map((ts) => new Date(ts * 1000).toLocaleString());
    const datasets = [
      {
        label: 'CPU Usage (%)',
        data: historyData.cpu_usage,
        borderColor: 'rgb(54, 162, 235)',
        backgroundColor: 'rgba(54, 162, 235, 0.5)',
        tension: 0.1,
        fill: ctx.state.currentChartType !== 'line',
      },
      {
        label: 'RAM Usage (%)',
        data: historyData.ram_usage,
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75, 192, 192, 0.5)',
        tension: 0.1,
        fill: ctx.state.currentChartType !== 'line',
      },
    ];

    const config = {
      type: ctx.state.currentChartType,
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 500 },
        scales: {
          y: {
            beginAtZero: true,
            min: 0,
            max: 100,
            title: { display: true, text: 'Usage (%)' },
          },
          x: {
            title: { display: true, text: 'Time' },
            ticks: {
              maxRotation: 70,
              minRotation: 0,
              autoSkip: true,
              maxTicksLimit: 20,
            },
          },
        },
        plugins: {
          legend: { position: 'top' },
          tooltip: { mode: 'index', intersect: false },
          zoom: {
            zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'xy' },
            pan: { enabled: true, mode: 'xy' },
          },
        },
        hover: { mode: 'nearest', intersect: true },
      },
    };

    if (ctx.state.usageChart) {
      ctx.state.usageChart.destroy();
    }
    ctx.state.usageChart = new Chart(chartCanvas, config);
  }

  async function fetchAndRenderChart() {
    if (!ctx.state.currentChartContainerId) {
      return;
    }

    const { filterRange, chartStatus } = ctx.elements;
    const url = `/api/history/${ctx.state.currentChartContainerId}?range=${filterRange.value}`;
    chartStatus.textContent = 'Loading chart data...';
    chartStatus.style.color = 'var(--bs-secondary-color)';

    try {
      const response = await fetch(url, { credentials: 'include' });
      if (!response.ok) {
        chartStatus.textContent = `Error loading chart data (Status: ${response.status}).`;
        chartStatus.style.color = 'var(--bs-danger)';
        if (ctx.state.usageChart) {
          ctx.state.usageChart.destroy();
          ctx.state.usageChart = null;
        }
        return;
      }
      renderChart(await response.json());
    } catch (error) {
      console.error('Error fetching chart data:', error);
      chartStatus.textContent = 'Network or processing error loading chart data.';
      chartStatus.style.color = 'var(--bs-danger)';
      if (ctx.state.usageChart) {
        ctx.state.usageChart.destroy();
        ctx.state.usageChart = null;
      }
    }
  }

  function showHistoryChart(containerId, containerName) {
    ctx.state.currentChartContainerId = containerId;
    ctx.elements.chartTitle.textContent = `Historical Usage for ${containerName} (${containerId.substring(0, 12)})`;
    ctx.elements.chartContainer.style.display = 'block';
    ctx.elements.chartControls.style.display = 'block';
    fetchAndRenderChart();
    ctx.elements.chartContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function openComparison(compareType) {
    const topN = ctx.elements.compareTopN.value || 5;
    window.open(`/compare/${compareType}?topN=${topN}`, '_blank');
  }

  function init() {
    ctx.elements.chartTypeRadios.forEach((radio) => {
      radio.addEventListener('change', (event) => {
        ctx.state.currentChartType = event.target.value;
        localStorage.setItem('chartType', event.target.value);
        if (ctx.state.usageChart) {
          fetchAndRenderChart();
        }
      });
    });
  }

  return {
    init,
    fetchAndRenderChart,
    showHistoryChart,
    openComparison,
  };
}
