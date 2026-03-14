import { getHotThresholds, setStatusMessage, updateQuickFilterUI, updateSummaryCards } from './helpers.js';

function normalizeNotifType(type) {
  return String(type || '').toLowerCase();
}

function titleCaseType(type) {
  const normalized = normalizeNotifType(type);
  return normalized ? normalized.charAt(0).toUpperCase() + normalized.slice(1) : 'Notification';
}

export function createNotificationController(ctx) {
  function updateNotifBadge() {
    const count = ctx.state.notifications.length;
    if (count > 0) {
      ctx.elements.notifBadge.textContent = count;
      ctx.elements.notifBadge.style.display = 'inline-block';
      if (ctx.elements.sidebarNotifBadge) {
        ctx.elements.sidebarNotifBadge.textContent = count;
        ctx.elements.sidebarNotifBadge.style.display = 'inline-block';
      }
    } else {
      ctx.elements.notifBadge.style.display = 'none';
      if (ctx.elements.sidebarNotifBadge) {
        ctx.elements.sidebarNotifBadge.style.display = 'none';
      }
    }
  }

  function renderNotifList(targetList = ctx.elements.notifList) {
    if (ctx.state.notifications.length === 0) {
      targetList.innerHTML = '<p class="small text-muted">No notifications</p>';
      return;
    }
    targetList.innerHTML = ctx.state.notifications.map((notification) => {
      const timestamp = notification.timestamp instanceof Date
        ? notification.timestamp.toLocaleTimeString()
        : new Date((notification.timestamp || 0) * 1000).toLocaleTimeString();
      const label = titleCaseType(notification.type);
      const message = notification.message || notification.containerName || '';
      return `<div class="notif-item mb-2"><strong>${label}</strong> ${message} <span class="text-muted small">at ${timestamp}</span></div>`;
    }).join('');
  }

  function addNotification(type, message, containerId) {
    ctx.state.notifications.push({
      type: normalizeNotifType(type),
      message,
      containerId,
      timestamp: new Date(),
    });
    updateNotifBadge();
    if (ctx.elements.notifPanel.style.display === 'block') {
      renderNotifList();
    }
  }

  function checkNotifications(data) {
    const cpuEnabled = ctx.elements.notifEnableCPU.checked;
    const ramEnabled = ctx.elements.notifEnableRAM.checked;
    const statusEnabled = ctx.elements.notifEnableStatus.checked;
    const updateEnabled = ctx.elements.notifEnableUpdate.checked;
    const thresholds = getHotThresholds(ctx);

    data.forEach((item) => {
      const prev = ctx.state.prevMetricsData.find((entry) => entry.id === item.id);
      const cpu = Number(item.cpu) || 0;
      const prevCpu = prev ? (Number(prev.cpu) || 0) : 0;
      const mem = Number(item.mem) || 0;
      const prevMem = prev ? (Number(prev.mem) || 0) : 0;

      if (cpuEnabled && cpu >= thresholds.cpu && prevCpu < thresholds.cpu) {
        addNotification('cpu', `${item.name} exceeded CPU threshold (${cpu.toFixed(1)}% > ${thresholds.cpu}%)`, item.id);
      }
      if (ramEnabled && mem >= thresholds.ram && prevMem < thresholds.ram) {
        addNotification('ram', `${item.name} exceeded RAM threshold (${mem.toFixed(1)}% > ${thresholds.ram}%)`, item.id);
      }
      if (prev && statusEnabled && item.status !== prev.status) {
        addNotification('status', `${item.name} status changed: ${prev.status} → ${item.status}`, item.id);
      }
      if (updateEnabled && item.update_available && (!prev || !prev.update_available)) {
        addNotification('update', `${item.name}: update available for this container`, item.id);
      }
    });

    ctx.state.prevMetricsData = JSON.parse(JSON.stringify(data));
  }

  function ingestNotifications(items = []) {
    const enabledByType = {
      cpu: ctx.elements.notifEnableCPU.checked,
      ram: ctx.elements.notifEnableRAM.checked,
      status: ctx.elements.notifEnableStatus.checked,
      update: ctx.elements.notifEnableUpdate.checked,
    };

    if (!Array.isArray(items) || items.length === 0) {
      return;
    }

    items.forEach((notification) => {
      const type = normalizeNotifType(notification.type);
      if (!enabledByType[type]) {
        return;
      }

      const timestamp = notification.timestamp || 0;
      ctx.state.lastNotifTimestamp = Math.max(ctx.state.lastNotifTimestamp, timestamp);
      ctx.state.notifications.push({
        type,
        message: notification.msg || notification.message || notification.container || '',
        containerId: notification.cid,
        timestamp,
      });
    });

    updateNotifBadge();
    renderNotifList();
  }

  function renderSystemStatus(systemStatus) {
    if (!systemStatus) {
      return;
    }

    const dockerStatus = systemStatus.docker || {};
    const notificationStatus = systemStatus.notifications || {};
    const configuredChannels = Object.entries(notificationStatus)
      .filter(([, details]) => details && details.configured)
      .map(([channel]) => channel);
    const pushoverReady = Boolean(notificationStatus.pushover?.configured);

    ctx.elements.dockerStatusChip.dataset.state = dockerStatus.connected ? 'healthy' : 'danger';
    ctx.elements.dockerStatusChip.textContent = dockerStatus.connected
      ? 'Docker status: connected'
      : `Docker status: ${dockerStatus.error ? 'degraded' : 'offline'}`;
    ctx.elements.dockerStatusChip.title = dockerStatus.error || dockerStatus.base_url || '';

    if (pushoverReady) {
      ctx.elements.notifyStatusChip.dataset.state = 'healthy';
      ctx.elements.notifyStatusChip.textContent = 'Pushover: configured';
    } else if (configuredChannels.length > 0) {
      ctx.elements.notifyStatusChip.dataset.state = 'warning';
      ctx.elements.notifyStatusChip.textContent = `Notifications: ${configuredChannels.join(', ')}`;
    } else {
      ctx.elements.notifyStatusChip.dataset.state = 'danger';
      ctx.elements.notifyStatusChip.textContent = 'Notifications: not configured';
    }

    ctx.elements.notifChannelStatus.textContent = configuredChannels.length > 0
      ? `Configured channels: ${configuredChannels.join(', ')}`
      : 'No notification channels configured. Pushover requires PUSHOVER_TOKEN and PUSHOVER_USER.';
  }

  async function fetchSystemStatus() {
    try {
      const response = await fetch('/api/system-status', { credentials: 'include' });
      if (!response.ok) {
        return;
      }
      renderSystemStatus(await response.json());
    } catch (error) {
      console.error('Error fetching system status:', error);
    }
  }

  async function triggerNotificationTest() {
    try {
      const response = await fetch('/api/notification-test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      const payload = await response.json();
      if (response.ok && payload.ok) {
        setStatusMessage(ctx, `Test notification sent through ${payload.successful_channels.join(', ')}.`, 'success');
      } else if (!payload.configured_any) {
        setStatusMessage(ctx, 'No notification channels are configured. Pushover is disabled until env vars are set.', 'warning');
      } else {
        setStatusMessage(ctx, 'Notification test failed on configured channels. Check server logs for provider errors.', 'danger');
      }
      fetchSystemStatus();
    } catch (error) {
      console.error('Error triggering notification test:', error);
      setStatusMessage(ctx, 'Notification test failed due to a network error.', 'danger');
    }
  }

  function clearNotifications() {
    ctx.state.notifications.length = 0;
    renderNotifList();
    updateNotifBadge();
  }

  async function saveSettings() {
    localStorage.setItem('notifCpuThreshold', ctx.elements.notifCpuThreshold.value);
    localStorage.setItem('notifRamThreshold', ctx.elements.notifRamThreshold.value);
    localStorage.setItem('notifEnableCPU', ctx.elements.notifEnableCPU.checked);
    localStorage.setItem('notifEnableRAM', ctx.elements.notifEnableRAM.checked);
    localStorage.setItem('notifEnableStatus', ctx.elements.notifEnableStatus.checked);
    localStorage.setItem('notifEnableUpdate', ctx.elements.notifEnableUpdate.checked);
    localStorage.setItem('notifWindowSeconds', ctx.elements.notifWindowSeconds.value);

    ctx.state.prevMetricsData = [];
    setStatusMessage(ctx, 'Notification settings saved.', 'success');

    try {
      await fetch('/api/notification-settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cpu_enabled: ctx.elements.notifEnableCPU.checked,
          ram_enabled: ctx.elements.notifEnableRAM.checked,
          status_enabled: ctx.elements.notifEnableStatus.checked,
          update_enabled: ctx.elements.notifEnableUpdate.checked,
          cpu_threshold: +ctx.elements.notifCpuThreshold.value,
          ram_threshold: +ctx.elements.notifRamThreshold.value,
          window_seconds: +ctx.elements.notifWindowSeconds.value,
        }),
      });
    } finally {
      updateSummaryCards(ctx, ctx.state.allMetricsData);
      updateQuickFilterUI(ctx);
    }
  }

  async function loadSettings() {
    ctx.elements.notifCpuThreshold.value = localStorage.getItem('notifCpuThreshold') || 80;
    ctx.elements.notifRamThreshold.value = localStorage.getItem('notifRamThreshold') || 80;
    ctx.elements.notifEnableCPU.checked = localStorage.getItem('notifEnableCPU') === 'true';
    ctx.elements.notifEnableRAM.checked = localStorage.getItem('notifEnableRAM') === 'true';
    ctx.elements.notifEnableStatus.checked = localStorage.getItem('notifEnableStatus') === 'true';
    ctx.elements.notifEnableUpdate.checked = localStorage.getItem('notifEnableUpdate') === 'true';
    ctx.elements.notifWindowSeconds.value = localStorage.getItem('notifWindowSeconds') || 10;

    try {
      const response = await fetch('/api/notification-settings');
      if (!response.ok) {
        return;
      }
      const settings = await response.json();
      if (!settings) {
        return;
      }

      if (settings.cpu_threshold !== undefined) {
        ctx.elements.notifCpuThreshold.value = settings.cpu_threshold;
        localStorage.setItem('notifCpuThreshold', settings.cpu_threshold);
      }
      if (settings.ram_threshold !== undefined) {
        ctx.elements.notifRamThreshold.value = settings.ram_threshold;
        localStorage.setItem('notifRamThreshold', settings.ram_threshold);
      }
      if (settings.window_seconds !== undefined) {
        ctx.elements.notifWindowSeconds.value = settings.window_seconds;
        localStorage.setItem('notifWindowSeconds', settings.window_seconds);
      }
      ctx.elements.notifEnableCPU.checked = settings.cpu_enabled;
      ctx.elements.notifEnableRAM.checked = settings.ram_enabled;
      ctx.elements.notifEnableStatus.checked = settings.status_enabled;
      ctx.elements.notifEnableUpdate.checked = settings.update_enabled;
      localStorage.setItem('notifEnableCPU', settings.cpu_enabled);
      localStorage.setItem('notifEnableRAM', settings.ram_enabled);
      localStorage.setItem('notifEnableStatus', settings.status_enabled);
      localStorage.setItem('notifEnableUpdate', settings.update_enabled);
    } catch (error) {
      console.error('Unable to load notification settings:', error);
    }
  }

  function openPanel() {
    const isVisible = ctx.elements.notifPanel.style.display === 'block';
    ctx.elements.notifPanel.style.display = isVisible ? 'none' : 'block';
    if (!isVisible) {
      renderNotifList();
      ctx.state.notifications.length = 0;
      updateNotifBadge();
    }
  }

  function init() {
    ctx.elements.notifToggle?.addEventListener('click', (event) => {
      event.stopPropagation();
      openPanel();
    });

    document.addEventListener('click', (event) => {
      if (
        ctx.elements.notifPanel
        && ctx.elements.notifToggle
        && !ctx.elements.notifPanel.contains(event.target)
        && !ctx.elements.notifToggle.contains(event.target)
      ) {
        ctx.elements.notifPanel.style.display = 'none';
      }
    });

    ctx.elements.clearNotifsBtn?.addEventListener('click', clearNotifications);
    ctx.elements.saveNotifSettingsBtn?.addEventListener('click', saveSettings);
    ctx.elements.testNotifBtn?.addEventListener('click', triggerNotificationTest);

    ctx.elements.notifEnableCPU?.addEventListener('change', (event) => {
      localStorage.setItem('notifEnableCPU', event.target.checked);
      if (!event.target.checked) {
        ctx.state.notifications = ctx.state.notifications.filter((notification) => notification.type !== 'cpu');
        updateNotifBadge();
        renderNotifList();
      }
    });
    ctx.elements.notifEnableRAM?.addEventListener('change', (event) => {
      localStorage.setItem('notifEnableRAM', event.target.checked);
      if (!event.target.checked) {
        ctx.state.notifications = ctx.state.notifications.filter((notification) => notification.type !== 'ram');
        updateNotifBadge();
        renderNotifList();
      }
    });
    ctx.elements.notifEnableStatus?.addEventListener('change', (event) => {
      localStorage.setItem('notifEnableStatus', event.target.checked);
      if (!event.target.checked) {
        ctx.state.notifications = ctx.state.notifications.filter((notification) => notification.type !== 'status');
        updateNotifBadge();
        renderNotifList();
      }
    });
    ctx.elements.notifEnableUpdate?.addEventListener('change', (event) => {
      localStorage.setItem('notifEnableUpdate', event.target.checked);
      if (!event.target.checked) {
        ctx.state.notifications = ctx.state.notifications.filter((notification) => notification.type !== 'update');
        updateNotifBadge();
        renderNotifList();
      }
    });
    ctx.elements.notifWindowSeconds?.addEventListener('change', (event) => {
      localStorage.setItem('notifWindowSeconds', event.target.value);
    });

  }

  return {
    init,
    ingestNotifications,
    loadSettings,
    checkNotifications,
    fetchSystemStatus,
    renderNotifList,
    updateNotifBadge,
    openPanel,
    clearNotifications,
  };
}
