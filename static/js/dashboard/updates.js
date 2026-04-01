import { escapeHtml, setStatusMessage } from './helpers.js';

const UPDATE_MANAGER_TAB_IDS = {
  projects: 'updateManagerProjectsTab',
  containers: 'updateManagerContainersTab',
  history: 'updateManagerHistoryTab',
};

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
  return String(value || '').toLowerCase() === 'project' ? 'Compose stack' : 'Container';
}

function renderVersion(value) {
  const safe = escapeHtml(value || 'Unknown');
  return `<code class="update-version-code">${safe}</code>`;
}

function renderListHead(includeActions = true) {
  return `
    <div class="update-target-list-head">
      <div>Name</div>
      <div>Type</div>
      <div>Current version</div>
      <div>Latest version</div>
      <div>Status</div>
      <div>Last check</div>
      ${includeActions ? '<div>Action</div>' : '<div>Result</div>'}
    </div>
  `;
}

function renderEntryDetails(entries = []) {
  if (!Array.isArray(entries) || entries.length === 0) {
    return '';
  }

  return `
    <div class="update-target-row-details">
      ${entries.map((entry) => `
        <div class="update-target-row-detail">
          <span class="update-target-row-detail-service">${escapeHtml(entry.service || entry.container_id || 'service')}</span>
          <span class="update-target-row-detail-versions">
            ${renderVersion(entry.current_version)}
            <span class="update-entry-arrow"><i class="bi bi-arrow-right" aria-hidden="true"></i></span>
            ${renderVersion(entry.latest_version || entry.new_version)}
          </span>
        </div>
      `).join('')}
    </div>
  `;
}

function renderTargetRow(item) {
  const state = String(item.update_state || '').toLowerCase();
  const buttonDisabled = state !== 'ready' ? 'disabled' : '';
  const serviceSummary = Array.isArray(item.entries) && item.entries.length > 0
    ? `<div class="update-target-row-meta">${escapeHtml(item.entries.map((entry) => entry.service || entry.container_id || 'service').join(', '))}</div>`
    : '';
  const reason = item.state_reason
    ? `<div class="update-target-row-note">${escapeHtml(item.state_reason)}</div>`
    : '';

  return `
    <div class="update-target-list-row" data-target-type="${escapeHtml(item.type)}" data-update-state="${escapeHtml(state || 'pending')}">
      <div class="update-target-list-cell update-target-list-cell--name">
        <strong>${escapeHtml(item.name)}</strong>
        ${serviceSummary}
        ${reason}
      </div>
      <div class="update-target-list-cell">${escapeHtml(formatTargetType(item.type))}</div>
      <div class="update-target-list-cell">${renderVersion(item.current_version)}</div>
      <div class="update-target-list-cell">${renderVersion(item.latest_version)}</div>
      <div class="update-target-list-cell">
        <span class="update-target-state" data-state="${escapeHtml(state || 'pending')}">${escapeHtml(formatStateLabel(state))}</span>
      </div>
      <div class="update-target-list-cell">${escapeHtml(formatTimestamp(item.last_checked_at))}</div>
      <div class="update-target-list-cell update-target-list-cell--actions">
        <button type="button" class="btn btn-primary btn-sm update-target-btn" data-update-target-type="${escapeHtml(item.type)}" data-update-target-id="${escapeHtml(item.target_id)}" ${buttonDisabled}>
          <i class="bi bi-arrow-repeat" aria-hidden="true"></i>
          <span>Update</span>
        </button>
      </div>
    </div>
    ${renderEntryDetails(item.entries)}
  `;
}

function renderHistoryRow(entry) {
  const action = String(entry.action || '').toLowerCase();
  const result = String(entry.result || '').toLowerCase();
  const rollbackButton = entry.can_rollback
    ? `
      <button type="button" class="btn btn-outline-secondary btn-sm update-rollback-btn" data-rollback-history-id="${escapeHtml(entry.id)}">
        <i class="bi bi-arrow-counterclockwise" aria-hidden="true"></i>
        <span>Rollback</span>
      </button>
    `
    : '<span class="update-target-row-meta">No rollback available</span>';
  const notes = entry.notes
    ? `<div class="update-target-row-note">${escapeHtml(entry.notes)}</div>`
    : '';

  return `
    <div class="update-target-list-row" data-target-type="${escapeHtml(entry.target_type)}" data-update-state="${escapeHtml(result || 'pending')}">
      <div class="update-target-list-cell update-target-list-cell--name">
        <strong>${escapeHtml(entry.target_name)}</strong>
        <div class="update-target-row-meta">${escapeHtml(action === 'rollback' ? 'Rollback' : 'Update')}</div>
        ${notes}
      </div>
      <div class="update-target-list-cell">${escapeHtml(formatTargetType(entry.target_type))}</div>
      <div class="update-target-list-cell">${renderVersion(entry.previous_version)}</div>
      <div class="update-target-list-cell">${renderVersion(entry.new_version)}</div>
      <div class="update-target-list-cell">
        <span class="update-target-state" data-state="${escapeHtml(result || 'pending')}">${escapeHtml(formatStateLabel(result))}</span>
      </div>
      <div class="update-target-list-cell">${escapeHtml(formatTimestamp(entry.created_at))}</div>
      <div class="update-target-list-cell update-target-list-cell--actions">
        ${rollbackButton}
      </div>
    </div>
  `;
}

function renderPlaceholder(message) {
  return `<div class="update-manager-empty">${escapeHtml(message)}</div>`;
}

function renderTargetList(items = [], emptyMessage) {
  if (!Array.isArray(items) || items.length === 0) {
    return renderPlaceholder(emptyMessage);
  }
  return `
    <div class="update-target-list-shell">
      ${renderListHead(true)}
      <div class="update-target-list-body">
        ${items.map(renderTargetRow).join('')}
      </div>
    </div>
  `;
}

function renderHistoryList(items = [], emptyMessage) {
  if (!Array.isArray(items) || items.length === 0) {
    return renderPlaceholder(emptyMessage);
  }
  return `
    <div class="update-target-list-shell">
      ${renderListHead(true)}
      <div class="update-target-list-body">
        ${items.map(renderHistoryRow).join('')}
      </div>
    </div>
  `;
}

export function createUpdateManagerController(ctx, deps) {
  let requestToken = 0;

  function ensureModal() {
    if (!ctx.elements.updateManagerModalEl) {
      return null;
    }
    ctx.state.updateManagerModal = bootstrap.Modal.getOrCreateInstance(ctx.elements.updateManagerModalEl);
    return ctx.state.updateManagerModal;
  }

  function showTab(tabKey) {
    const elementName = UPDATE_MANAGER_TAB_IDS[tabKey];
    const tabButton = elementName ? ctx.elements[elementName] : null;
    if (!tabButton) {
      return;
    }
    bootstrap.Tab.getOrCreateInstance(tabButton).show();
  }

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

  function setListsLoading(message, { keepExisting = false } = {}) {
    if (keepExisting && ctx.state.updateManagerPayload) {
      return;
    }
    ctx.elements.updateManagerProjectList.innerHTML = renderPlaceholder(message);
    ctx.elements.updateManagerContainerList.innerHTML = renderPlaceholder(message);
    ctx.elements.updateManagerHistoryList.innerHTML = renderPlaceholder('Loading update history...');
  }

  function renderPayload(payload) {
    ctx.state.updateManagerPayload = payload;
    const projects = Array.isArray(payload.projects) ? payload.projects : [];
    const containers = Array.isArray(payload.containers) ? payload.containers : [];
    const history = Array.isArray(payload.history) ? payload.history : [];

    ctx.elements.updateManagerMeta.textContent = `${projects.length} Compose stack(s), ${containers.length} standalone container(s), ${history.length} history entr${history.length === 1 ? 'y' : 'ies'}`;
    ctx.elements.updateManagerProjectList.innerHTML = renderTargetList(projects, 'No Compose stacks currently have a confirmed update available.');
    ctx.elements.updateManagerContainerList.innerHTML = renderTargetList(containers, 'No standalone containers currently have a confirmed update available.');
    ctx.elements.updateManagerHistoryList.innerHTML = renderHistoryList(history, 'No updates or rollbacks have been recorded yet.');
  }

  async function loadTargets(options = {}) {
    const token = ++requestToken;
    const refresh = options.refresh === true;
    ctx.state.updateManagerLoading = true;
    ctx.elements.refreshUpdateManagerBtn.disabled = true;
    ctx.elements.refreshUpdateManagerBtn.textContent = refresh ? 'Refreshing...' : 'Refresh list';
    ctx.elements.updateManagerMeta.textContent = refresh ? 'Refreshing update inventory...' : 'Loading update inventory...';
    setManagerStatus(refresh ? 'Refreshing update inventory…' : '');
    setListsLoading(refresh ? 'Refreshing available updates...' : 'Loading available updates...', {
      keepExisting: refresh,
    });

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
      setManagerStatus('');
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

  function openModal(event) {
    event?.preventDefault();
    event?.stopPropagation();
    if (ctx.elements.notifPanel) {
      ctx.elements.notifPanel.style.display = 'none';
    }
    requestAnimationFrame(() => {
      ensureModal()?.show();
      showTab('projects');
      if (!ctx.state.updateManagerPayload && !ctx.state.updateManagerLoading) {
        loadTargets();
      }
    });
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
    ensureModal();
    ctx.elements.updateManagerToggle?.addEventListener('click', openModal);
    ctx.elements.sidebarUpdateManagerToggle?.addEventListener('click', (event) => {
      deps.closeMobileMenu?.();
      openModal(event);
    });
    ctx.elements.refreshUpdateManagerBtn?.addEventListener('click', () => loadTargets({ refresh: true }));
    ctx.elements.updateManagerModalEl?.addEventListener('click', handleModalClick);
    ctx.elements.updateManagerModalEl?.addEventListener('hidden.bs.modal', () => {
      setManagerStatus('');
    });
  }

  return {
    init,
    loadTargets,
    openModal,
    updateBadgeFromMetrics,
  };
}
