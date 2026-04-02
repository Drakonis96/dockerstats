import { flashButtonSuccess, getHotThresholds, setStatusMessage, updateQuickFilterUI, updateSummaryCards } from './helpers.js';

const DEFAULT_NOTIFICATION_SETTINGS = {
  cpu_enabled: true,
  ram_enabled: true,
  status_enabled: true,
  update_enabled: true,
  security_enabled: false,
  security_privileged_enabled: false,
  security_public_ports_enabled: false,
  security_latest_enabled: false,
  security_docker_socket_enabled: false,
  cpu_threshold: 80,
  ram_threshold: 80,
  window_seconds: 10,
  cooldown_seconds: 0,
  project_rule_mode: 'all',
  project_rules: '',
  container_rule_mode: 'all',
  container_rules: '',
  silence_enabled: false,
  silence_start: '22:00',
  silence_end: '07:00',
  dedupe_enabled: true,
  dedupe_window_seconds: 120,
};

function normalizeNotifType(type) {
  return String(type || '').toLowerCase();
}

function titleCaseType(type) {
  const normalized = normalizeNotifType(type);
  return normalized ? normalized.charAt(0).toUpperCase() + normalized.slice(1) : 'Notification';
}

function boolFromStorage(key, fallback) {
  const value = localStorage.getItem(key);
  if (value === null) {
    return fallback;
  }
  return value === 'true';
}

function stringFromStorage(key, fallback) {
  const value = localStorage.getItem(key);
  return value === null ? fallback : value;
}

function splitDuration(totalSeconds, minimum = 0) {
  const total = Math.max(minimum, Number(totalSeconds) || 0);
  return {
    minutes: Math.floor(total / 60),
    seconds: total % 60,
  };
}

function durationInputsToSeconds(minutesInput, secondsInput, fallback, minimum = 0) {
  const minutes = Math.max(0, parseInt(minutesInput?.value, 10) || 0);
  const seconds = Math.max(0, Math.min(59, parseInt(secondsInput?.value, 10) || 0));
  const total = (minutes * 60) + seconds;
  if (total === 0 && minimum > 0) {
    return fallback;
  }
  return Math.max(minimum, total);
}

export function createNotificationController(ctx) {
  let tooltipInstances = [];

  function ensureNotifSettingsModal() {
    if (!ctx.elements.notifSettingsModalEl) {
      return null;
    }
    ctx.state.notifSettingsModal = bootstrap.Modal.getOrCreateInstance(ctx.elements.notifSettingsModalEl);
    return ctx.state.notifSettingsModal;
  }

  function ensureClearNotificationsModal() {
    if (!ctx.elements.clearNotificationsModalEl) {
      return null;
    }
    ctx.state.clearNotificationsModal = bootstrap.Modal.getOrCreateInstance(ctx.elements.clearNotificationsModalEl);
    return ctx.state.clearNotificationsModal;
  }

  function getCurrentSettings() {
    return {
      cpu_enabled: Boolean(ctx.elements.notifEnableCPU?.checked),
      ram_enabled: Boolean(ctx.elements.notifEnableRAM?.checked),
      status_enabled: Boolean(ctx.elements.notifEnableStatus?.checked),
      update_enabled: Boolean(ctx.elements.notifEnableUpdate?.checked),
      security_enabled: Boolean(ctx.elements.notifEnableSecurity?.checked),
      security_privileged_enabled: Boolean(ctx.elements.notifSecurityPrivilegedEnabled?.checked),
      security_public_ports_enabled: Boolean(ctx.elements.notifSecurityPublicPortsEnabled?.checked),
      security_latest_enabled: Boolean(ctx.elements.notifSecurityLatestEnabled?.checked),
      security_docker_socket_enabled: Boolean(ctx.elements.notifSecurityDockerSocketEnabled?.checked),
      cpu_threshold: Number(ctx.elements.notifCpuThreshold?.value || DEFAULT_NOTIFICATION_SETTINGS.cpu_threshold),
      ram_threshold: Number(ctx.elements.notifRamThreshold?.value || DEFAULT_NOTIFICATION_SETTINGS.ram_threshold),
      window_seconds: durationInputsToSeconds(
        ctx.elements.notifWindowMinutes,
        ctx.elements.notifWindowSeconds,
        DEFAULT_NOTIFICATION_SETTINGS.window_seconds,
        1,
      ),
      cooldown_seconds: durationInputsToSeconds(
        ctx.elements.notifCooldownMinutes,
        ctx.elements.notifCooldownSeconds,
        DEFAULT_NOTIFICATION_SETTINGS.cooldown_seconds,
        0,
      ),
      project_rule_mode: ctx.elements.notifProjectRuleMode?.value || DEFAULT_NOTIFICATION_SETTINGS.project_rule_mode,
      project_rules: ctx.elements.notifProjectRules?.value || '',
      container_rule_mode: ctx.elements.notifContainerRuleMode?.value || DEFAULT_NOTIFICATION_SETTINGS.container_rule_mode,
      container_rules: ctx.elements.notifContainerRules?.value || '',
      silence_enabled: Boolean(ctx.elements.notifSilenceEnabled?.checked),
      silence_start: ctx.elements.notifSilenceStart?.value || DEFAULT_NOTIFICATION_SETTINGS.silence_start,
      silence_end: ctx.elements.notifSilenceEnd?.value || DEFAULT_NOTIFICATION_SETTINGS.silence_end,
      dedupe_enabled: Boolean(ctx.elements.notifDedupeEnabled?.checked),
      dedupe_window_seconds: durationInputsToSeconds(
        ctx.elements.notifDedupeWindowMinutes,
        ctx.elements.notifDedupeWindowSeconds,
        DEFAULT_NOTIFICATION_SETTINGS.dedupe_window_seconds,
        0,
      ),
    };
  }

  function syncSilenceInputsState() {
    const disabled = !ctx.elements.notifSilenceEnabled?.checked;
    if (ctx.elements.notifSilenceStart) {
      ctx.elements.notifSilenceStart.disabled = disabled;
    }
    if (ctx.elements.notifSilenceEnd) {
      ctx.elements.notifSilenceEnd.disabled = disabled;
    }
  }

  function syncSecurityInputsState() {
    const disabled = !ctx.elements.notifEnableSecurity?.checked;
    [
      ctx.elements.notifSecurityPrivilegedEnabled,
      ctx.elements.notifSecurityPublicPortsEnabled,
      ctx.elements.notifSecurityLatestEnabled,
      ctx.elements.notifSecurityDockerSocketEnabled,
    ].forEach((element) => {
      if (element) {
        element.disabled = disabled;
      }
    });
  }

  function writeSettingsToInputs(settings = {}) {
    const merged = { ...DEFAULT_NOTIFICATION_SETTINGS, ...settings };
    const windowDuration = splitDuration(merged.window_seconds, 1);
    const cooldownDuration = splitDuration(merged.cooldown_seconds, 0);
    const dedupeDuration = splitDuration(merged.dedupe_window_seconds, 0);
    ctx.elements.notifCpuThreshold.value = merged.cpu_threshold;
    ctx.elements.notifRamThreshold.value = merged.ram_threshold;
    ctx.elements.notifWindowMinutes.value = windowDuration.minutes;
    ctx.elements.notifWindowSeconds.value = windowDuration.seconds;
    ctx.elements.notifCooldownMinutes.value = cooldownDuration.minutes;
    ctx.elements.notifCooldownSeconds.value = cooldownDuration.seconds;
    ctx.elements.notifEnableCPU.checked = Boolean(merged.cpu_enabled);
    ctx.elements.notifEnableRAM.checked = Boolean(merged.ram_enabled);
    ctx.elements.notifEnableStatus.checked = Boolean(merged.status_enabled);
    ctx.elements.notifEnableUpdate.checked = Boolean(merged.update_enabled);
    ctx.elements.notifEnableSecurity.checked = Boolean(merged.security_enabled);
    ctx.elements.notifSecurityPrivilegedEnabled.checked = Boolean(merged.security_privileged_enabled);
    ctx.elements.notifSecurityPublicPortsEnabled.checked = Boolean(merged.security_public_ports_enabled);
    ctx.elements.notifSecurityLatestEnabled.checked = Boolean(merged.security_latest_enabled);
    ctx.elements.notifSecurityDockerSocketEnabled.checked = Boolean(merged.security_docker_socket_enabled);
    ctx.elements.notifProjectRuleMode.value = merged.project_rule_mode;
    ctx.elements.notifProjectRules.value = merged.project_rules || '';
    ctx.elements.notifContainerRuleMode.value = merged.container_rule_mode;
    ctx.elements.notifContainerRules.value = merged.container_rules || '';
    ctx.elements.notifSilenceEnabled.checked = Boolean(merged.silence_enabled);
    ctx.elements.notifSilenceStart.value = merged.silence_start || DEFAULT_NOTIFICATION_SETTINGS.silence_start;
    ctx.elements.notifSilenceEnd.value = merged.silence_end || DEFAULT_NOTIFICATION_SETTINGS.silence_end;
    ctx.elements.notifDedupeEnabled.checked = Boolean(merged.dedupe_enabled);
    ctx.elements.notifDedupeWindowMinutes.value = dedupeDuration.minutes;
    ctx.elements.notifDedupeWindowSeconds.value = dedupeDuration.seconds;
    syncSilenceInputsState();
    syncSecurityInputsState();
  }

  function persistSettingsToLocalStorage(settings) {
    localStorage.setItem('notifCpuThreshold', settings.cpu_threshold);
    localStorage.setItem('notifRamThreshold', settings.ram_threshold);
    localStorage.setItem('notifWindowSeconds', settings.window_seconds);
    localStorage.setItem('notifCooldownSeconds', settings.cooldown_seconds);
    localStorage.setItem('notifEnableCPU', settings.cpu_enabled);
    localStorage.setItem('notifEnableRAM', settings.ram_enabled);
    localStorage.setItem('notifEnableStatus', settings.status_enabled);
    localStorage.setItem('notifEnableUpdate', settings.update_enabled);
    localStorage.setItem('notifEnableSecurity', settings.security_enabled);
    localStorage.setItem('notifSecurityPrivilegedEnabled', settings.security_privileged_enabled);
    localStorage.setItem('notifSecurityPublicPortsEnabled', settings.security_public_ports_enabled);
    localStorage.setItem('notifSecurityLatestEnabled', settings.security_latest_enabled);
    localStorage.setItem('notifSecurityDockerSocketEnabled', settings.security_docker_socket_enabled);
    localStorage.setItem('notifProjectRuleMode', settings.project_rule_mode);
    localStorage.setItem('notifProjectRules', settings.project_rules || '');
    localStorage.setItem('notifContainerRuleMode', settings.container_rule_mode);
    localStorage.setItem('notifContainerRules', settings.container_rules || '');
    localStorage.setItem('notifSilenceEnabled', settings.silence_enabled);
    localStorage.setItem('notifSilenceStart', settings.silence_start || DEFAULT_NOTIFICATION_SETTINGS.silence_start);
    localStorage.setItem('notifSilenceEnd', settings.silence_end || DEFAULT_NOTIFICATION_SETTINGS.silence_end);
    localStorage.setItem('notifDedupeEnabled', settings.dedupe_enabled);
    localStorage.setItem('notifDedupeWindowSeconds', settings.dedupe_window_seconds);
  }

  function restoreSettingsFromLocalStorage() {
    writeSettingsToInputs({
      cpu_threshold: stringFromStorage('notifCpuThreshold', DEFAULT_NOTIFICATION_SETTINGS.cpu_threshold),
      ram_threshold: stringFromStorage('notifRamThreshold', DEFAULT_NOTIFICATION_SETTINGS.ram_threshold),
      window_seconds: stringFromStorage('notifWindowSeconds', DEFAULT_NOTIFICATION_SETTINGS.window_seconds),
      cooldown_seconds: stringFromStorage('notifCooldownSeconds', DEFAULT_NOTIFICATION_SETTINGS.cooldown_seconds),
      cpu_enabled: boolFromStorage('notifEnableCPU', DEFAULT_NOTIFICATION_SETTINGS.cpu_enabled),
      ram_enabled: boolFromStorage('notifEnableRAM', DEFAULT_NOTIFICATION_SETTINGS.ram_enabled),
      status_enabled: boolFromStorage('notifEnableStatus', DEFAULT_NOTIFICATION_SETTINGS.status_enabled),
      update_enabled: boolFromStorage('notifEnableUpdate', DEFAULT_NOTIFICATION_SETTINGS.update_enabled),
      security_enabled: boolFromStorage('notifEnableSecurity', DEFAULT_NOTIFICATION_SETTINGS.security_enabled),
      security_privileged_enabled: boolFromStorage('notifSecurityPrivilegedEnabled', DEFAULT_NOTIFICATION_SETTINGS.security_privileged_enabled),
      security_public_ports_enabled: boolFromStorage('notifSecurityPublicPortsEnabled', DEFAULT_NOTIFICATION_SETTINGS.security_public_ports_enabled),
      security_latest_enabled: boolFromStorage('notifSecurityLatestEnabled', DEFAULT_NOTIFICATION_SETTINGS.security_latest_enabled),
      security_docker_socket_enabled: boolFromStorage('notifSecurityDockerSocketEnabled', DEFAULT_NOTIFICATION_SETTINGS.security_docker_socket_enabled),
      project_rule_mode: stringFromStorage('notifProjectRuleMode', DEFAULT_NOTIFICATION_SETTINGS.project_rule_mode),
      project_rules: stringFromStorage('notifProjectRules', DEFAULT_NOTIFICATION_SETTINGS.project_rules),
      container_rule_mode: stringFromStorage('notifContainerRuleMode', DEFAULT_NOTIFICATION_SETTINGS.container_rule_mode),
      container_rules: stringFromStorage('notifContainerRules', DEFAULT_NOTIFICATION_SETTINGS.container_rules),
      silence_enabled: boolFromStorage('notifSilenceEnabled', DEFAULT_NOTIFICATION_SETTINGS.silence_enabled),
      silence_start: stringFromStorage('notifSilenceStart', DEFAULT_NOTIFICATION_SETTINGS.silence_start),
      silence_end: stringFromStorage('notifSilenceEnd', DEFAULT_NOTIFICATION_SETTINGS.silence_end),
      dedupe_enabled: boolFromStorage('notifDedupeEnabled', DEFAULT_NOTIFICATION_SETTINGS.dedupe_enabled),
      dedupe_window_seconds: stringFromStorage('notifDedupeWindowSeconds', DEFAULT_NOTIFICATION_SETTINGS.dedupe_window_seconds),
    });
  }

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

    if (ctx.elements.clearNotifsBtn) {
      ctx.elements.clearNotifsBtn.disabled = count === 0;
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

  function removeNotificationsByType(type) {
    ctx.state.notifications = ctx.state.notifications.filter((notification) => notification.type !== type);
    updateNotifBadge();
    renderNotifList();
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
      security: ctx.elements.notifEnableSecurity.checked,
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

    ctx.elements.dockerStatusChip.dataset.state = dockerStatus.connected ? 'healthy' : 'danger';
    ctx.elements.dockerStatusChip.textContent = dockerStatus.connected
      ? 'Docker status: connected'
      : `Docker status: ${dockerStatus.error ? 'degraded' : 'offline'}`;
    ctx.elements.dockerStatusChip.title = dockerStatus.error || dockerStatus.base_url || '';

    if (configuredChannels.length > 0) {
      ctx.elements.notifyStatusChip.dataset.state = 'healthy';
      ctx.elements.notifyStatusChip.textContent = configuredChannels.length === 1
        ? `Notifications: ${configuredChannels[0]} ready`
        : `Notifications: ${configuredChannels.length} channels ready`;
    } else {
      ctx.elements.notifyStatusChip.dataset.state = 'danger';
      ctx.elements.notifyStatusChip.textContent = 'Notifications: not configured';
    }

    ctx.elements.notifChannelStatus.textContent = configuredChannels.length > 0
      ? `Configured channels: ${configuredChannels.join(', ')}`
      : 'No notification channels configured. Supported env vars include PUSHOVER_*, SLACK_WEBHOOK_URL, TELEGRAM_*, DISCORD_WEBHOOK_URL, NTFY_TOPIC, and GENERIC_WEBHOOK_URL.';
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
        flashButtonSuccess(ctx.elements.testNotifBtn, { label: 'Sent' });
        setStatusMessage(ctx, `Test notification sent through ${payload.successful_channels.join(', ')}.`, 'success');
      } else if (!payload.configured_any) {
        setStatusMessage(ctx, 'No notification channels are configured. Add any supported provider env vars and try again.', 'warning');
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

  function confirmClearNotifications() {
    clearNotifications();
    const modal = ensureClearNotificationsModal();
    modal?.hide();
    requestAnimationFrame(() => {
      if (!ctx.elements.clearNotificationsModalEl?.classList.contains('show')) {
        return;
      }
      ctx.elements.clearNotificationsModalEl.classList.remove('show');
      ctx.elements.clearNotificationsModalEl.style.display = 'none';
      ctx.elements.clearNotificationsModalEl.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('modal-open');
      document.body.style.removeProperty('padding-right');
      document.querySelectorAll('.modal-backdrop').forEach((element) => element.remove());
    });
  }

  async function saveSettings() {
    const settings = getCurrentSettings();
    persistSettingsToLocalStorage(settings);
    ctx.state.prevMetricsData = [];

    try {
      const response = await fetch('/api/notification-settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      });
      if (!response.ok) {
        throw new Error(`Unable to save notification settings: ${response.status}`);
      }
      const payload = await response.json();
      writeSettingsToInputs(payload.settings || settings);
      persistSettingsToLocalStorage(payload.settings || settings);
      flashButtonSuccess(ctx.elements.saveNotifSettingsBtn, { label: 'Saved' });
      setStatusMessage(ctx, 'Notification settings saved.', 'success');
    } catch (error) {
      console.error('Unable to save notification settings:', error);
      setStatusMessage(ctx, 'Unable to save notification settings.', 'danger');
    } finally {
      updateSummaryCards(ctx, ctx.state.allMetricsData);
      updateQuickFilterUI(ctx);
    }
  }

  async function loadSettings() {
    restoreSettingsFromLocalStorage();

    try {
      const response = await fetch('/api/notification-settings');
      if (!response.ok) {
        return;
      }
      const settings = await response.json();
      if (!settings) {
        return;
      }

      writeSettingsToInputs(settings);
      persistSettingsToLocalStorage({ ...DEFAULT_NOTIFICATION_SETTINGS, ...settings });
    } catch (error) {
      console.error('Unable to load notification settings:', error);
    }
  }

  function hidePanel() {
    ctx.elements.notifPanel.style.display = 'none';
  }

  function openPanel() {
    const isVisible = ctx.elements.notifPanel.style.display === 'block';
    ctx.elements.notifPanel.style.display = isVisible ? 'none' : 'block';
    if (!isVisible) {
      renderNotifList();
      updateNotifBadge();
    }
  }

  function resetPanelInlineStyle() {
    Object.assign(ctx.elements.notifPanel.style, {
      position: '',
      top: '',
      left: '',
      right: '',
      marginTop: '',
      transform: '',
      width: '',
      maxWidth: '',
      maxHeight: '',
      overflowY: '',
      zIndex: '',
    });
  }

  function openSettingsModal(event) {
    event?.preventDefault();
    event?.stopPropagation();
    hidePanel();
    const mobileOverlay = document.getElementById('mobileNotifOverlay');
    if (mobileOverlay) {
      mobileOverlay.style.display = 'none';
    }
    resetPanelInlineStyle();
    requestAnimationFrame(() => ensureNotifSettingsModal()?.show());
  }

  function openClearNotificationsModal(event) {
    event?.preventDefault();
    event?.stopPropagation();
    if (ctx.state.notifications.length === 0) {
      return;
    }
    hidePanel();
    const mobileOverlay = document.getElementById('mobileNotifOverlay');
    if (mobileOverlay) {
      mobileOverlay.style.display = 'none';
    }
    resetPanelInlineStyle();
    requestAnimationFrame(() => ensureClearNotificationsModal()?.show());
  }

  function initBootstrapWidgets() {
    ensureNotifSettingsModal();
    ensureClearNotificationsModal();

    tooltipInstances.forEach((instance) => instance.dispose());
    tooltipInstances = Array.from(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
      .map((element) => new bootstrap.Tooltip(element));
  }

  function init() {
    initBootstrapWidgets();

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
        hidePanel();
      }
    });

    ctx.elements.notifSettingsBtn?.addEventListener('click', openSettingsModal);
    ctx.elements.clearNotifsBtn?.addEventListener('click', openClearNotificationsModal);
    ctx.elements.confirmClearNotifsBtn?.addEventListener('click', confirmClearNotifications);
    ctx.elements.saveNotifSettingsBtn?.addEventListener('click', saveSettings);
    ctx.elements.testNotifBtn?.addEventListener('click', triggerNotificationTest);
    ctx.elements.notifSilenceEnabled?.addEventListener('change', () => {
      localStorage.setItem('notifSilenceEnabled', ctx.elements.notifSilenceEnabled.checked);
      syncSilenceInputsState();
    });

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
        removeNotificationsByType('update');
      }
    });
    ctx.elements.notifEnableSecurity?.addEventListener('change', (event) => {
      localStorage.setItem('notifEnableSecurity', event.target.checked);
      syncSecurityInputsState();
      if (!event.target.checked) {
        removeNotificationsByType('security');
      }
    });

    [
      ctx.elements.notifEnableSecurity,
      ctx.elements.notifSecurityPrivilegedEnabled,
      ctx.elements.notifSecurityPublicPortsEnabled,
      ctx.elements.notifSecurityLatestEnabled,
      ctx.elements.notifSecurityDockerSocketEnabled,
      ctx.elements.notifWindowMinutes,
      ctx.elements.notifWindowSeconds,
      ctx.elements.notifCpuThreshold,
      ctx.elements.notifRamThreshold,
      ctx.elements.notifCooldownMinutes,
      ctx.elements.notifCooldownSeconds,
      ctx.elements.notifProjectRuleMode,
      ctx.elements.notifProjectRules,
      ctx.elements.notifContainerRuleMode,
      ctx.elements.notifContainerRules,
      ctx.elements.notifSilenceStart,
      ctx.elements.notifSilenceEnd,
      ctx.elements.notifDedupeEnabled,
      ctx.elements.notifDedupeWindowMinutes,
      ctx.elements.notifDedupeWindowSeconds,
    ].forEach((element) => {
      element?.addEventListener('change', () => persistSettingsToLocalStorage(getCurrentSettings()));
      element?.addEventListener('input', () => persistSettingsToLocalStorage(getCurrentSettings()));
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
    openSettingsModal,
  };
}
