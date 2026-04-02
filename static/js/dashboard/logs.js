export function createLogController(ctx) {
  function ensureModal() {
    if (!ctx.elements.logsModalEl) {
      return null;
    }
    ctx.state.logsModal = bootstrap.Modal.getOrCreateInstance(ctx.elements.logsModalEl);
    return ctx.state.logsModal;
  }

  function closeStream() {
    if (ctx.state.logsEventSource) {
      ctx.state.logsEventSource.close();
      ctx.state.logsEventSource = null;
    }
  }

  function getRequestedLineLimit() {
    if (ctx.elements.logsLineLimitSelect?.value === 'custom') {
      return Math.max(1, parseInt(ctx.elements.logsCustomLimitInput?.value, 10) || ctx.state.logsLineLimit || 100);
    }
    return Math.max(1, parseInt(ctx.elements.logsLineLimitSelect?.value, 10) || ctx.state.logsLineLimit || 100);
  }

  function syncLimitInputs() {
    const isCustom = ctx.elements.logsLineLimitSelect?.value === 'custom';
    if (ctx.elements.logsCustomLimitWrap) {
      ctx.elements.logsCustomLimitWrap.hidden = !isCustom;
    }
    if (isCustom && ctx.elements.logsCustomLimitInput) {
      ctx.elements.logsCustomLimitInput.focus();
      ctx.elements.logsCustomLimitInput.select();
    }
  }

  function trimBuffer() {
    const limit = Math.max(1, ctx.state.logsLineLimit || 100);
    if (ctx.state.logsBuffer.length > limit) {
      ctx.state.logsBuffer = ctx.state.logsBuffer.slice(-limit);
    }
  }

  function scrollLogsToBottom() {
    if (!ctx.state.logsAutoScroll || !ctx.elements.logsOutput) {
      return;
    }
    requestAnimationFrame(() => {
      ctx.elements.logsOutput.scrollTop = ctx.elements.logsOutput.scrollHeight;
    });
  }

  function renderLogs() {
    if (!ctx.elements.logsOutput) {
      return;
    }
    ctx.elements.logsOutput.textContent = ctx.state.logsBuffer.join('\n');
    scrollLogsToBottom();
  }

  function updateMeta(message) {
    if (ctx.elements.logsMeta) {
      ctx.elements.logsMeta.textContent = message;
    }
  }

  function updateStatus(message, state = 'idle') {
    if (!ctx.elements.logsStatus) {
      return;
    }
    ctx.elements.logsStatus.textContent = message;
    ctx.elements.logsStatus.dataset.state = state;
  }

  function applyLineLimit() {
    ctx.state.logsLineLimit = getRequestedLineLimit();
    if (ctx.elements.logsLineLimitSelect?.value !== 'custom') {
      ctx.elements.logsCustomLimitInput.value = String(ctx.state.logsLineLimit);
    }
    if (ctx.state.logsContainerId) {
      connectStream();
    }
  }

  function appendLine(line) {
    if (typeof line !== 'string') {
      return;
    }
    ctx.state.logsBuffer.push(line);
    trimBuffer();
    renderLogs();
  }

  function connectStream() {
    if (!ctx.state.logsContainerId) {
      return;
    }

    closeStream();
    ctx.state.logsLineLimit = getRequestedLineLimit();
    ctx.state.logsBuffer = [];
    renderLogs();
    updateMeta(`Loading the latest ${ctx.state.logsLineLimit} log lines for ${ctx.state.logsContainerName || ctx.state.logsContainerId}…`);
    updateStatus('Connecting to the live log stream…', 'loading');

    const source = new EventSource(`/api/logs/${ctx.state.logsContainerId}/stream?tail=${ctx.state.logsLineLimit}`);
    ctx.state.logsEventSource = source;

    source.addEventListener('connected', () => {
      updateStatus('Live stream connected.', 'ready');
      updateMeta(`Streaming the latest ${ctx.state.logsLineLimit} lines for ${ctx.state.logsContainerName || ctx.state.logsContainerId}.`);
    });

    source.addEventListener('snapshot', (event) => {
      try {
        const payload = JSON.parse(event.data);
        ctx.state.logsBuffer = Array.isArray(payload.lines) ? payload.lines.slice(-ctx.state.logsLineLimit) : [];
        renderLogs();
        updateMeta(`Showing the latest ${ctx.state.logsLineLimit} lines for ${payload.container_name || ctx.state.logsContainerName || ctx.state.logsContainerId}.`);
        updateStatus('Live stream connected.', 'ready');
      } catch (error) {
        console.error('Unable to process log snapshot payload:', error);
        updateStatus('Unable to read the initial log snapshot.', 'error');
      }
    });

    source.addEventListener('line', (event) => {
      try {
        const payload = JSON.parse(event.data);
        appendLine(payload.text || '');
      } catch (error) {
        console.error('Unable to process log line payload:', error);
      }
    });

    source.addEventListener('error', () => {
      updateStatus('Log stream disconnected. Waiting to reconnect…', 'warning');
    });
  }

  function openLogs(containerId, containerName) {
    ctx.state.logsContainerId = containerId;
    ctx.state.logsContainerName = containerName || containerId;
    updateMeta(`Preparing the log stream for ${ctx.state.logsContainerName}.`);
    updateStatus('Preparing the live log stream…', 'loading');
    const builtInValues = new Set(['100', '500', '1000']);
    const storedLimit = String(ctx.state.logsLineLimit || 100);
    ctx.elements.logsLineLimitSelect.value = builtInValues.has(storedLimit) ? storedLimit : 'custom';
    ctx.elements.logsCustomLimitInput.value = String(ctx.state.logsLineLimit || 100);
    syncLimitInputs();

    const modal = ensureModal();
    if (!modal) {
      return;
    }

    const showAndConnect = () => connectStream();
    if (ctx.elements.logsModalEl?.classList.contains('show')) {
      showAndConnect();
      return;
    }

    ctx.elements.logsModalEl?.addEventListener('shown.bs.modal', showAndConnect, { once: true });
    requestAnimationFrame(() => modal.show());
  }

  function downloadLogs() {
    if (!ctx.state.logsContainerId) {
      return;
    }
    const limit = getRequestedLineLimit();
    const link = document.createElement('a');
    link.href = `/api/logs/${ctx.state.logsContainerId}?tail=${limit}&download=1`;
    link.download = '';
    link.click();
  }

  function init() {
    ensureModal();
    syncLimitInputs();
    ctx.state.logsAutoScroll = true;

    ctx.elements.logsLineLimitSelect?.addEventListener('change', syncLimitInputs);
    ctx.elements.logsApplyLimitBtn?.addEventListener('click', applyLineLimit);
    ctx.elements.logsCustomLimitInput?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        applyLineLimit();
      }
    });
    ctx.elements.logsAutoScrollToggle?.addEventListener('change', (event) => {
      ctx.state.logsAutoScroll = Boolean(event.target.checked);
      if (ctx.state.logsAutoScroll) {
        scrollLogsToBottom();
      }
    });
    ctx.elements.downloadLogsBtn?.addEventListener('click', downloadLogs);

    ctx.elements.logsModalEl?.addEventListener('hidden.bs.modal', () => {
      closeStream();
      ctx.state.logsContainerId = null;
      ctx.state.logsContainerName = '';
      ctx.state.logsBuffer = [];
      renderLogs();
      updateMeta('Waiting for the first log request.');
      updateStatus('Choose a container log button to start streaming.', 'idle');
    });
  }

  return {
    init,
    openLogs,
  };
}
