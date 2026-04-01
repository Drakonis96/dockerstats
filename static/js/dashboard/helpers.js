const actionFeedbackTimers = new WeakMap();

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

export function flashButtonSuccess(button, {
  label = 'Saved',
  duration = 1100,
  icon = 'bi-check2',
} = {}) {
  if (!button) {
    return;
  }

  const existing = actionFeedbackTimers.get(button);
  if (existing?.timer) {
    window.clearTimeout(existing.timer);
  }

  const originalHtml = existing?.originalHtml || button.innerHTML;
  const originalMinWidth = button.style.minWidth;
  const width = Math.ceil(button.getBoundingClientRect().width);
  if (width > 0) {
    button.style.minWidth = `${width}px`;
  }

  button.dataset.feedbackState = 'success';
  button.classList.add('action-feedback-btn', 'is-success');
  button.innerHTML = `<span class="action-feedback-icon" aria-hidden="true"><i class="bi ${icon}"></i></span><span>${escapeHtml(label)}</span>`;

  const timer = window.setTimeout(() => {
    button.innerHTML = originalHtml;
    button.classList.remove('action-feedback-btn', 'is-success');
    button.style.minWidth = originalMinWidth;
    delete button.dataset.feedbackState;
    actionFeedbackTimers.delete(button);
  }, duration);

  actionFeedbackTimers.set(button, { timer, originalHtml });
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

export function buildProjectSummaries(items) {
  const rows = Array.isArray(items) ? items : [];
  const buckets = new Map();

  rows.forEach((item) => {
    const project = String(item.compose_project || '').trim();
    if (!project) {
      return;
    }

    if (!buckets.has(project)) {
      buckets.set(project, {
        project,
        container_count: 0,
        running_count: 0,
        exited_count: 0,
        other_count: 0,
        update_count: 0,
        restart_count: 0,
        cpu_total: 0,
        mem_usage_total: 0,
        mem_limit_total: 0,
        mem_avg_percent: 0,
        mem_pressure_percent: null,
        _mem_samples: 0,
      });
    }

    const bucket = buckets.get(project);
    bucket.container_count += 1;

    const status = String(item.status || '').toLowerCase();
    if (status === 'running') {
      bucket.running_count += 1;
    } else if (status === 'exited') {
      bucket.exited_count += 1;
    } else {
      bucket.other_count += 1;
    }

    if (item.update_available) {
      bucket.update_count += 1;
    }

    bucket.restart_count += Number(item.restarts) || 0;
    bucket.cpu_total += Number(item.cpu) || 0;
    bucket.mem_usage_total += Number(item.mem_usage) || 0;

    const memLimit = Number(item.mem_limit) || 0;
    if (memLimit > 0) {
      bucket.mem_limit_total += memLimit;
    }

    const memPercent = Number(item.mem);
    if (!Number.isNaN(memPercent)) {
      bucket.mem_avg_percent += memPercent;
      bucket._mem_samples += 1;
    }
  });

  return Array.from(buckets.values())
    .sort((left, right) => left.project.localeCompare(right.project, undefined, { sensitivity: 'base' }))
    .map((bucket) => {
      const memAvgPercent = bucket._mem_samples > 0 ? bucket.mem_avg_percent / bucket._mem_samples : 0;
      const memPressurePercent = bucket.mem_limit_total > 0
        ? (bucket.mem_usage_total / bucket.mem_limit_total) * 100
        : null;

      let status = 'degraded';
      if (bucket.container_count > 0 && bucket.running_count === bucket.container_count && bucket.other_count === 0) {
        status = 'healthy';
      } else if (bucket.running_count === 0 && bucket.exited_count === bucket.container_count) {
        status = 'stopped';
      }

      return {
        project: bucket.project,
        container_count: bucket.container_count,
        running_count: bucket.running_count,
        exited_count: bucket.exited_count,
        other_count: bucket.other_count,
        update_count: bucket.update_count,
        restart_count: bucket.restart_count,
        cpu_total: Number(bucket.cpu_total.toFixed(2)),
        mem_usage_total: Number(bucket.mem_usage_total.toFixed(2)),
        mem_limit_total: Number(bucket.mem_limit_total.toFixed(2)),
        mem_avg_percent: Number(memAvgPercent.toFixed(2)),
        mem_pressure_percent: memPressurePercent === null ? null : Number(memPressurePercent.toFixed(2)),
        status,
      };
    });
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
