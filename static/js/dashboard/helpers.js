export function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function setStatusMessage(ctx, message, tone = 'info') {
  const tones = {
    info: '#156f63',
    success: '#156f63',
    warning: '#a75d18',
    danger: '#bb3e3e',
  };
  ctx.elements.statusMessageArea.textContent = message;
  ctx.elements.statusMessageArea.style.color = tones[tone] || tones.info;
}

export function normalizeStatus(status) {
  return String(status || 'unknown').toLowerCase().replace(/[^a-z0-9]+/g, '-');
}

export function getHotThresholds(ctx) {
  return {
    cpu: Number(ctx.elements.notifCpuThreshold?.value || 80),
    ram: Number(ctx.elements.notifRamThreshold?.value || 80),
  };
}

export function matchesQuickFilter(ctx, item) {
  const status = String(item.status || '').toLowerCase();
  const cpu = Number(item.cpu) || 0;
  const ram = Number(item.mem) || 0;
  const thresholds = getHotThresholds(ctx);

  switch (ctx.state.currentQuickFilter) {
    case 'running':
      return status === 'running';
    case 'exited':
      return status === 'exited';
    case 'hot':
      return cpu >= thresholds.cpu || ram >= thresholds.ram;
    case 'updates':
      return Boolean(item.update_available);
    default:
      return true;
  }
}

export function countActiveFilters(ctx) {
  let count = 0;
  if (ctx.elements.filterName.value.trim()) count++;
  if (ctx.elements.filterStatus.value) count++;
  if (ctx.elements.filterProject.value) count++;
  if ((ctx.elements.maxItems.value || '').trim() && ctx.elements.maxItems.value !== '25') count++;
  if (ctx.state.currentQuickFilter !== 'all') count++;
  return count;
}

export function updateQuickFilterUI(ctx) {
  ctx.elements.quickFilterButtons.forEach((button) => {
    button.classList.toggle('active', button.dataset.quickFilter === ctx.state.currentQuickFilter);
  });
  ctx.elements.activeFiltersValue.textContent = `${countActiveFilters(ctx)} active filters`;
}

export function updateSummaryCards(ctx, data) {
  const items = Array.isArray(data) ? data : [];
  const thresholds = getHotThresholds(ctx);
  const running = items.filter((item) => String(item.status || '').toLowerCase() === 'running');
  const exited = items.filter((item) => String(item.status || '').toLowerCase() === 'exited');
  const hot = items.filter((item) => (Number(item.cpu) || 0) >= thresholds.cpu || (Number(item.mem) || 0) >= thresholds.ram);
  const updates = items.filter((item) => Boolean(item.update_available));
  const peak = items.reduce((best, item) => {
    const combined = (Number(item.cpu) || 0) + (Number(item.mem) || 0);
    if (!best || combined > best.combined) {
      return { item, combined };
    }
    return best;
  }, null);

  ctx.elements.summaryTotal.textContent = items.length;
  ctx.elements.summaryRunning.textContent = running.length;
  ctx.elements.summaryExited.textContent = exited.length;
  ctx.elements.summaryHot.textContent = hot.length;
  ctx.elements.summaryUpdates.textContent = updates.length;
  ctx.elements.summaryUpdatesMeta.textContent = updates.length > 0
    ? 'Click to inspect update-ready containers'
    : 'No pending image updates';

  if (peak && peak.item) {
    ctx.elements.summaryPeak.textContent = `${peak.combined.toFixed(0)}%`;
    ctx.elements.summaryPeakMeta.textContent = `${peak.item.name || 'Unknown'} • CPU ${(Number(peak.item.cpu) || 0).toFixed(1)}% / RAM ${(Number(peak.item.mem) || 0).toFixed(1)}%`;
  } else {
    ctx.elements.summaryPeak.textContent = '--';
    ctx.elements.summaryPeakMeta.textContent = 'No metrics yet';
  }
}

export function updateRefreshUi(ctx) {
  const paused = ctx.state.autoRefreshPaused === true;
  const connected = ctx.state.streamConnected === true;
  ctx.elements.toggleRefreshBtn.dataset.paused = paused ? 'true' : 'false';
  ctx.elements.toggleRefreshBtn.textContent = paused ? 'Resume refresh' : 'Pause refresh';
  ctx.elements.refreshStatusChip.dataset.state = paused ? 'warning' : (connected ? 'healthy' : 'danger');
  ctx.elements.refreshStatusChip.textContent = paused
    ? 'Refresh: paused'
    : connected
      ? `Realtime: SSE every ${Math.max(1, Math.round(ctx.state.refreshIntervalMs / 1000))}s`
      : 'Realtime: reconnecting';
}

function getThemeToggleMarkup(theme, withLabel = false) {
  const icon = theme === 'dark' ? 'bi-sun' : 'bi-moon-stars';
  if (withLabel) {
    return `<i class="bi ${icon}" aria-hidden="true"></i><span>Toggle Theme</span>`;
  }
  return `<i class="bi ${icon}" aria-hidden="true"></i>`;
}

export function applyTheme(ctx, theme) {
  document.body.setAttribute('data-bs-theme', theme);
  ctx.elements.themeToggleButton.innerHTML = getThemeToggleMarkup(theme, false);
  ctx.elements.sidebarThemeToggle.innerHTML = getThemeToggleMarkup(theme, true);
}

export function getInitialTheme() {
  const preferred = localStorage.getItem('theme')
    || (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  return preferred === 'dark' ? 'dark' : 'light';
}
