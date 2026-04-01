import { escapeHtml, setStatusMessage } from './helpers.js';

function formatTimestamp(value) {
  if (!value) {
    return 'Not checked yet';
  }
  const date = new Date(Number(value) * 1000);
  if (Number.isNaN(date.getTime())) {
    return 'Unknown time';
  }
  return date.toLocaleString();
}

function formatStateLabel(value) {
  switch (String(value || '').toLowerCase()) {
    case 'ready':
      return 'Ready';
    case 'blocked':
      return 'Blocked';
    case 'success':
      return 'Success';
    case 'failure':
      return 'Failed';
    default:
      return 'Pending';
  }
}

function formatTargetType(value) {
  return String(value || '').toLowerCase() === 'project' ? 'Compose project' : 'Container';
}

function renderVersion(value) {
  const safe = escapeHtml(value || 'Unknown');
  return `<code class="update-version-code">${safe}</code>`;
}

function renderEntries(entries = []) {
  if (!Array.isArray(entries) || entries.length === 0) {
    return '';
  }
  const items = entries.map((entry) => `
    <div class="update-entry-row">
      <div class="update-entry-service">${escapeHtml(entry.service || entry.container_id || 'service')}</div>
      <div class="update-entry-versions">
        <span>${renderVersion(entry.current_version)}</span>
        <span class="update-entry-arrow"><i class="bi bi-arrow-right" aria-hidden="true"></i></span>
        <span>${renderVersion(entry.latest_version || entry.new_version)}</span>
      </div>
    </div>
  `).join('');
  return `<div class="update-entry-list">${items}</div>`;
}

function renderTargetCard(item) {
  const state = String(item.update_state || '').toLowerCase();
  const buttonDisabled = state !== 'ready' ? 'disabled' : '';
  const reason = item.state_reason
    ? `<p class="update-target-reason mb-0">${escapeHtml(item.state_reason)}</p>`
    : '';
  const lastChecked = formatTimestamp(item.last_checked_at);

  return `
    <article class="update-target-card" data-target-type="${escapeHtml(item.type)}" data-update-state="${escapeHtml(state || 'pending')}">
      <div class="update-target-head">
        <div>
          <p class="update-target-eyebrow">${escapeHtml(formatTargetType(item.type))}</p>
          <h6 class="update-target-title">${escapeHtml(item.name)}</h6>
        </div>
        <span class="update-target-state" data-state="${escapeHtml(state || 'pending')}">${escapeHtml(formatStateLabel(state))}</span>
      </div>
      <div class="update-target-grid">
        <div>
          <span class="update-target-label">Name</span>
          <strong>${escapeHtml(item.name)}</strong>
        </div>
        <div>
          <span class="update-target-label">Type</span>
          <strong>${escapeHtml(item.type)}</strong>
        </div>
        <div>
          <span class="update-target-label">Current version</span>
          ${renderVersion(item.current_version)}
        </div>
        <div>
          <span class="update-target-label">Latest version</span>
          ${renderVersion(item.latest_version)}
        </div>
        <div>
          <span class="update-target-label">Update status</span>
          <strong>${escapeHtml(formatStateLabel(state))}</strong>
        </div>
        <div>
          <span class="update-target-label">Last check</span>
          <strong>${escapeHtml(lastChecked)}</strong>
        </div>
      </div>
      ${renderEntries(item.entries)}
      <div class="update-target-actions">
        <button type="button" class="btn btn-primary btn-sm update-target-btn" data-update-target-type="${escapeHtml(item.type)}" data-update-target-id="${escapeHtml(item.target_id)}" ${buttonDisabled}>
          <i class="bi bi-arrow-repeat" aria-hidden="true"></i>
          <span>Update now</span>
        </button>
        ${reason}
      </div>
    </article>
  `;
}

function renderHistoryCard(entry) {
  const action = String(entry.action || '').toLowerCase();
  const result = String(entry.result || '').toLowerCase();
  const actionLabel = action === 'rollback' ? 'Rollback' : 'Update';
  const notes = entry.notes ? `<p class="update-history-notes">${escapeHtml(entry.notes)}</p>` : '';
  const rollbackButton = entry.can_rollback
    ? `
      <button
        type="button"
        class="btn btn-outline-secondary btn-sm update-rollback-btn"
        data-rollback-history-id="${escapeHtml(entry.id)}"
      >
        <i class="bi bi-arrow-counterclockwise" aria-hidden="true"></i>
        <span>Rollback</span>
      </button>
    `
    : '';

  return `
    <article class="update-history-card" data-result="${escapeHtml(result || 'pending')}">
      <div class="update-history-head">
        <div>
          <p class="update-target-eyebrow">${escapeHtml(actionLabel)} • ${escapeHtml(formatTargetType(entry.target_type))}</p>
          <h6 class="update-target-title">${escapeHtml(entry.target_name)}</h6>
        </div>
        <span class="update-target-state" data-state="${escapeHtml(result || 'pending')}">${escapeHtml(formatStateLabel(result))}</span>
      </div>
      <div class="update-history-grid">
        <div>
          <span class="update-target-label">Previous version</span>
          ${renderVersion(entry.previous_version)}
        </div>
        <div>
          <span class="update-target-label">New version</span>
          ${renderVersion(entry.new_version)}
        </div>
        <div>
          <span class="update-target-label">Updated at</span>
          <strong>${escapeHtml(formatTimestamp(entry.created_at))}</strong>
        </div>
        <div>
          <span class="update-target-label">Result</span>
          <strong>${escapeHtml(formatStateLabel(result))}</strong>
        </div>
      </div>
      ${notes}
      <div class="update-target-actions">
        ${rollbackButton}
      </div>
    </article>
  `;
}

function renderPlaceholder(message) {
  return `<div class="update-manager-empty">${escapeHtml(message)}</div>`;
}

export function createUpdateManagerController(ctx, deps) {
  let requestToken = 0;

  function updateBadgeFromMetrics(items = []) {
    const count = (Array.isArray(items) ? items : []).filter((item) => Boolean(item.update_available)).length;
    if (!ctx.elements.updateManagerBadge) {
      return;
    }
    if (count > 0) {
      ctx.elements.updateManagerBadge.textContent = count;
      ctx.elements.updateManagerBadge.style.display = 'inline-block';
    } else {
      ctx.elements.updateManagerBadge.style.display = 'none';
    }
  }

  function setManagerStatus(message, tone = 'info') {
    const target = ctx.elements.updateManagerStatus;
    if (!target) {
      return;
    }
    if (!message) {
      target.className = 'alert d-none';
      target.textContent = '';
      return;
    }
    const toneMap = {
      info: 'alert-secondary',
      success: 'alert-success',
      warning: 'alert-warning',
      danger: 'alert-danger',
    };
    target.className = `alert ${toneMap[tone] || toneMap.info}`;
    target.textContent = message;
  }

  function setListsLoading(message) {
    ctx.elements.updateManagerProjectList.innerHTML = renderPlaceholder(message);
    ctx.elements.updateManagerContainerList.innerHTML = renderPlaceholder(message);
    ctx.elements.updateManagerHistoryList.innerHTML = renderPlaceholder('Loading update history...');
  }

  function renderPayload(payload) {
    ctx.state.updateManagerPayload = payload;
    const projects = Array.isArray(payload.projects) ? payload.projects : [];
    const containers = Array.isArray(payload.containers) ? payload.containers : [];
    const history = Array.isArray(payload.history) ? payload.history : [];

    ctx.elements.updateManagerMeta.textContent = `${projects.length} project(s), ${containers.length} standalone container(s), ${history.length} history entr${history.length === 1 ? 'y' : 'ies'}`;
    ctx.elements.updateManagerProjectList.innerHTML = projects.length > 0
      ? projects.map(renderTargetCard).join('')
      : renderPlaceholder('No Compose stacks currently have a confirmed update available.');
    ctx.elements.updateManagerContainerList.innerHTML = containers.length > 0
      ? containers.map(renderTargetCard).join('')
      : renderPlaceholder('No standalone containers currently have a confirmed update available.');
    ctx.elements.updateManagerHistoryList.innerHTML = history.length > 0
      ? history.map(renderHistoryCard).join('')
      : renderPlaceholder('No updates or rollbacks have been recorded yet.');
  }

  async function loadTargets(options = {}) {
    const token = ++requestToken;
    const refresh = options.refresh === true;
    ctx.state.updateManagerLoading = true;
    ctx.elements.refreshUpdateManagerBtn.disabled = true;
    ctx.elements.refreshUpdateManagerBtn.textContent = refresh ? 'Refreshing...' : 'Refresh list';
    ctx.elements.updateManagerMeta.textContent = refresh ? 'Refreshing update inventory...' : 'Loading update inventory...';
    setManagerStatus('');
    setListsLoading(refresh ? 'Refreshing available updates...' : 'Loading available updates...');

    try {
      const response = await fetch(`/api/update-manager?history_limit=25${refresh ? '&refresh=1' : ''}`, { credentials: 'include' });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.message || `Unable to load update manager (${response.status}).`);
      }
      if (token !== requestToken) {
        return;
      }
      renderPayload(payload);
    } catch (error) {
      if (token !== requestToken) {
        return;
      }
      ctx.elements.updateManagerMeta.textContent = 'Update manager unavailable';
      ctx.elements.updateManagerProjectList.innerHTML = renderPlaceholder('Unable to load update candidates.');
      ctx.elements.updateManagerContainerList.innerHTML = renderPlaceholder('Unable to load update candidates.');
      ctx.elements.updateManagerHistoryList.innerHTML = renderPlaceholder('Unable to load update history.');
      setManagerStatus(error.message || 'Unable to load update manager.', 'danger');
    } finally {
      if (token === requestToken) {
        ctx.state.updateManagerLoading = false;
        ctx.elements.refreshUpdateManagerBtn.disabled = false;
        ctx.elements.refreshUpdateManagerBtn.textContent = 'Refresh list';
      }
    }
  }

  async function executeUpdate(targetType, targetId, button) {
    const typeLabel = formatTargetType(targetType);
    const confirmed = await deps.confirmAction({
      title: 'Apply update',
      message: `Update ${typeLabel.toLowerCase()} "${targetId}" with the experimental safe workflow? Docker Stats will preserve volumes, configuration, networks and environment where possible, but you should still review the change carefully before continuing.`,
      confirmLabel: 'Apply update',
      cancelLabel: 'Cancel',
      tone: 'warning',
    });
    if (!confirmed) {
      return;
    }

    const originalMarkup = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<i class="bi bi-arrow-repeat spin-inline" aria-hidden="true"></i><span>Updating...</span>';
    setManagerStatus(`Applying update for ${targetId}...`, 'info');

    try {
      const response = await fetch('/api/update-manager/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_type: targetType, target_id: targetId }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message || `Update failed for ${targetId}.`);
      }
      const successMessage = payload.message || 'Update completed.';
      setManagerStatus(successMessage, 'success');
      setStatusMessage(ctx, successMessage, 'success');
      await deps.fetchMetrics();
      await loadTargets();
      setManagerStatus(successMessage, 'success');
    } catch (error) {
      button.disabled = false;
      button.innerHTML = originalMarkup;
      setManagerStatus(error.message || 'Update failed.', 'danger');
      setStatusMessage(ctx, error.message || 'Update failed.', 'danger');
    }
  }

  async function executeRollback(historyId, button) {
    const confirmed = await deps.confirmAction({
      title: 'Rollback update',
      message: 'Rollback will restore the previously recorded version using the persistent update history. This is also experimental and should be reviewed carefully before applying it.',
      confirmLabel: 'Run rollback',
      cancelLabel: 'Cancel',
      tone: 'warning',
    });
    if (!confirmed) {
      return;
    }

    const originalMarkup = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<i class="bi bi-arrow-counterclockwise spin-inline" aria-hidden="true"></i><span>Rolling back...</span>';
    setManagerStatus(`Running rollback for history entry #${historyId}...`, 'info');

    try {
      const response = await fetch('/api/update-manager/rollback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ history_id: Number(historyId) }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message || 'Rollback failed.');
      }
      const successMessage = payload.message || 'Rollback completed.';
      setManagerStatus(successMessage, 'success');
      setStatusMessage(ctx, successMessage, 'success');
      await deps.fetchMetrics();
      await loadTargets();
      setManagerStatus(successMessage, 'success');
    } catch (error) {
      button.disabled = false;
      button.innerHTML = originalMarkup;
      setManagerStatus(error.message || 'Rollback failed.', 'danger');
      setStatusMessage(ctx, error.message || 'Rollback failed.', 'danger');
    }
  }

  function openModal() {
    if (ctx.elements.notifPanel) {
      ctx.elements.notifPanel.style.display = 'none';
    }
    ctx.state.updateManagerModal.show();
    loadTargets();
  }

  function handleModalClick(event) {
    const updateButton = event.target.closest('[data-update-target-type][data-update-target-id]');
    if (updateButton) {
      executeUpdate(updateButton.dataset.updateTargetType, updateButton.dataset.updateTargetId, updateButton);
      return;
    }

    const rollbackButton = event.target.closest('[data-rollback-history-id]');
    if (rollbackButton) {
      executeRollback(rollbackButton.dataset.rollbackHistoryId, rollbackButton);
    }
  }

  function init() {
    if (ctx.elements.updateManagerModalEl && !ctx.state.updateManagerModal) {
      ctx.state.updateManagerModal = new bootstrap.Modal(ctx.elements.updateManagerModalEl);
    }

    ctx.elements.updateManagerToggle?.addEventListener('click', openModal);
    ctx.elements.sidebarUpdateManagerToggle?.addEventListener('click', () => {
      deps.closeMobileMenu?.();
      openModal();
    });
    ctx.elements.refreshUpdateManagerBtn?.addEventListener('click', () => loadTargets({ refresh: true }));
    ctx.elements.updateManagerModalEl?.addEventListener('click', handleModalClick);
    ctx.elements.updateManagerModalEl?.addEventListener('shown.bs.modal', () => {
      if (!ctx.state.updateManagerPayload) {
        loadTargets();
      }
    });
  }

  return {
    init,
    loadTargets,
    openModal,
    updateBadgeFromMetrics,
  };
}
