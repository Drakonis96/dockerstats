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

function formatManagementLabel(meta = {}) {
  const managerName = String(meta.manager_name || '').trim();
  const managementMode = String(meta.management_mode || '').toLowerCase();
  if (managementMode === 'external') {
    return managerName ? `${managerName} (external)` : 'Externally managed';
  }
  if (managementMode === 'host') {
    return managerName || 'Compose files on host';
  }
  if (String(meta.block_kind || '').trim()) {
    return 'Compose files unavailable';
  }
  return '';
}

function renderManagementBadge(meta = {}) {
  const managementMode = String(meta.management_mode || '').toLowerCase();
  const managerName = String(meta.manager_name || '').trim();
  if (managementMode === 'external') {
    return `<span class="update-entry-summary-badge" data-kind="external">${escapeHtml(managerName || 'Externally managed')}</span>`;
  }
  if (managementMode === 'host') {
    return '<span class="update-entry-summary-badge" data-kind="host">Host compose</span>';
  }
  return '';
}

function renderVersion(value, className = 'update-version-code') {
  const safe = escapeHtml(value || 'Unknown');
  return `<code class="${className}">${safe}</code>`;
}

function renderPlaceholder(message) {
  return `<div class="update-manager-empty">${escapeHtml(message)}</div>`;
}

function renderKeyValue(label, value, valueClass = '') {
  return `
    <div class="update-entry-detail">
      <span class="update-entry-detail-label">${escapeHtml(label)}</span>
      <span class="update-entry-detail-value ${valueClass}">${value}</span>
    </div>
  `;
}

function renderServiceEntries(entries = []) {
  if (!Array.isArray(entries) || entries.length === 0) {
    return '';
  }

  return `
    <div class="update-entry-section">
      <div class="update-entry-section-title">Services</div>
      <div class="update-entry-service-list">
        ${entries.map((entry) => `
          <div class="update-entry-service-row">
            <span class="update-entry-service-name">${escapeHtml(entry.service || entry.container_id || 'service')}</span>
            <span class="update-entry-service-versions">
              ${renderVersion(entry.current_version, 'update-version-code update-version-code--inline')}
              <i class="bi bi-arrow-right" aria-hidden="true"></i>
              ${renderVersion(entry.latest_version || entry.new_version, 'update-version-code update-version-code--inline')}
            </span>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

function renderGuidance(meta = {}) {
  const guidance = Array.isArray(meta.guidance) ? meta.guidance.filter(Boolean) : [];
  const missingFiles = Array.isArray(meta.missing_files) ? meta.missing_files.filter(Boolean) : [];
  const recoveryHint = String(meta.recovery_hint || '').trim();

  if (guidance.length === 0 && missingFiles.length === 0 && !recoveryHint) {
    return '';
  }

  const missingMarkup = missingFiles.length > 0
    ? `
      <div class="update-entry-section">
        <div class="update-entry-section-title">Missing files</div>
        <ul class="update-entry-guidance-list update-entry-guidance-list--paths">
          ${missingFiles.map((path) => `<li>${renderVersion(path)}</li>`).join('')}
        </ul>
      </div>
    `
    : '';

  const guidanceMarkup = guidance.length > 0
    ? `
      <div class="update-entry-section">
        <div class="update-entry-section-title">Guidance</div>
        <ul class="update-entry-guidance-list">
          ${guidance.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}
        </ul>
      </div>
    `
    : '';

  const recoveryMarkup = recoveryHint
    ? `
      <div class="update-entry-section">
        <div class="update-entry-section-title">Recovery</div>
        <div class="update-entry-note update-entry-note--recovery">${escapeHtml(recoveryHint)}</div>
      </div>
    `
    : '';

  return `${missingMarkup}${guidanceMarkup}${recoveryMarkup}`;
}

function renderSummaryVersion(value) {
  return `
    <span class="update-entry-summary-version-copy">
      <span class="update-entry-summary-version-label">New version</span>
      ${renderVersion(value, 'update-version-code update-version-code--summary')}
    </span>
  `;
}

function renderTargetEntry(item, index, groupKey, options = {}) {
  const {
    selected = false,
  } = options;
  const state = String(item.update_state || '').toLowerCase() || 'pending';
  const meta = item.meta || {};
  const panelId = `update-entry-panel-${groupKey}-${index}`;
  const isExternalSafeUpdate = meta.update_strategy === 'external_project_safe_recreate';
  const selectionControl = state === 'ready'
    ? `
      <div class="update-entry-select-slot">
        <input
          type="checkbox"
          class="form-check-input update-entry-select"
          data-update-select-type="${escapeHtml(item.type)}"
          data-update-select-id="${escapeHtml(item.target_id)}"
          aria-label="Select ${escapeHtml(formatTargetType(item.type).toLowerCase())} ${escapeHtml(item.name)} for batch update"
          ${selected ? 'checked' : ''}
        >
      </div>
    `
    : '<div class="update-entry-select-slot" aria-hidden="true"></div>';
  const quickAction = state === 'ready'
    ? `
      <button type="button" class="btn btn-outline-primary btn-sm update-target-btn update-target-btn--quick" data-update-target-type="${escapeHtml(item.type)}" data-update-target-id="${escapeHtml(item.target_id)}" data-update-strategy="${escapeHtml(meta.update_strategy || '')}">
        <i class="bi bi-lightning-charge" aria-hidden="true"></i>
        <span>Quick Update</span>
      </button>
    `
    : '';
  const reason = item.state_reason
    ? `<div class="update-entry-note">${escapeHtml(item.state_reason)}</div>`
    : '';
  const managementLabel = formatManagementLabel(meta);
  const managementBadge = renderManagementBadge(meta);
  const actionMarkup = state === 'ready'
    ? `
      <button type="button" class="btn btn-primary btn-sm update-target-btn" data-update-target-type="${escapeHtml(item.type)}" data-update-target-id="${escapeHtml(item.target_id)}" data-update-strategy="${escapeHtml(meta.update_strategy || '')}">
        <i class="bi bi-arrow-repeat" aria-hidden="true"></i>
        <span>${isExternalSafeUpdate ? 'Update safely' : 'Update'}</span>
      </button>
    `
    : `<span class="update-entry-actions-note update-entry-actions-note--blocked">${escapeHtml(meta.action_hint || 'Update is unavailable for this target.')}</span>`;
  const actionNote = state === 'ready' && meta.action_hint
    ? `<span class="update-entry-actions-note">${escapeHtml(meta.action_hint)}</span>`
    : '';

  return `
    <article class="update-entry ${selected ? 'is-selected' : ''}" data-target-type="${escapeHtml(item.type)}" data-target-id="${escapeHtml(item.target_id)}" data-update-state="${escapeHtml(state)}">
      <div class="update-entry-head">
        ${selectionControl}
        <button
          type="button"
          class="update-entry-toggle"
          data-update-entry-toggle
          aria-expanded="false"
          aria-controls="${panelId}"
        >
          <span class="update-entry-summary">
            <span class="update-entry-summary-copy">
              <span class="update-entry-summary-name-row">
                <span class="update-entry-summary-name">${escapeHtml(item.name)}</span>
                ${managementBadge}
              </span>
              <span class="update-entry-summary-version">${renderSummaryVersion(item.latest_version)}</span>
            </span>
          </span>
          <span class="update-entry-chevron" aria-hidden="true">
            <i class="bi bi-chevron-down"></i>
          </span>
        </button>
        ${quickAction}
      </div>
      <div id="${panelId}" class="update-entry-panel" aria-hidden="true" hidden>
        <div class="update-entry-panel-inner">
          <div class="update-entry-details-grid">
            ${renderKeyValue('Type', escapeHtml(formatTargetType(item.type)))}
            ${renderKeyValue('Current version', renderVersion(item.current_version))}
            ${renderKeyValue('Latest version', renderVersion(item.latest_version))}
            ${renderKeyValue('Status', `<span class="update-target-state" data-state="${escapeHtml(state)}">${escapeHtml(formatStateLabel(state))}</span>`)}
            ${renderKeyValue('Last check', escapeHtml(formatTimestamp(item.last_checked_at)))}
            ${managementLabel ? renderKeyValue('Management', escapeHtml(managementLabel)) : ''}
            ${meta.update_mode_label ? renderKeyValue('Update mode', escapeHtml(meta.update_mode_label)) : ''}
          </div>
          ${reason}
          ${renderGuidance(meta)}
          ${renderServiceEntries(item.entries)}
          <div class="update-entry-actions">
            ${actionNote}
            ${actionMarkup}
          </div>
        </div>
      </div>
    </article>
  `;
}

function renderHistoryEntry(entry, index) {
  const action = String(entry.action || '').toLowerCase();
  const result = String(entry.result || '').toLowerCase() || 'pending';
  const panelId = `update-entry-panel-history-${index}`;
  const notes = entry.notes
    ? `<div class="update-entry-note">${escapeHtml(entry.notes)}</div>`
    : '';
  const rollbackButton = entry.can_rollback
    ? `
      <button type="button" class="btn btn-outline-secondary btn-sm update-rollback-btn" data-rollback-history-id="${escapeHtml(entry.id)}">
        <i class="bi bi-arrow-counterclockwise" aria-hidden="true"></i>
        <span>Rollback</span>
      </button>
    `
    : '<span class="update-entry-actions-note">No rollback available</span>';

  return `
    <article class="update-entry" data-target-type="${escapeHtml(entry.target_type)}" data-update-state="${escapeHtml(result)}">
      <div class="update-entry-head">
        <button
          type="button"
          class="update-entry-toggle"
          data-update-entry-toggle
          aria-expanded="false"
          aria-controls="${panelId}"
        >
          <span class="update-entry-summary">
            <span class="update-entry-summary-copy">
              <span class="update-entry-summary-name">${escapeHtml(entry.target_name)}</span>
              <span class="update-entry-summary-version">${renderSummaryVersion(entry.new_version)}</span>
            </span>
          </span>
          <span class="update-entry-chevron" aria-hidden="true">
            <i class="bi bi-chevron-down"></i>
          </span>
        </button>
      </div>
      <div id="${panelId}" class="update-entry-panel" aria-hidden="true" hidden>
        <div class="update-entry-panel-inner">
          <div class="update-entry-details-grid">
            ${renderKeyValue('Type', escapeHtml(formatTargetType(entry.target_type)))}
            ${renderKeyValue('Action', escapeHtml(action === 'rollback' ? 'Rollback' : 'Update'))}
            ${renderKeyValue('Previous version', renderVersion(entry.previous_version))}
            ${renderKeyValue('New version', renderVersion(entry.new_version))}
            ${renderKeyValue('Result', `<span class="update-target-state" data-state="${escapeHtml(result)}">${escapeHtml(formatStateLabel(result))}</span>`)}
            ${renderKeyValue('Date', escapeHtml(formatTimestamp(entry.created_at)))}
          </div>
          ${notes}
          <div class="update-entry-actions">
            ${rollbackButton}
          </div>
        </div>
      </div>
    </article>
  `;
}

function renderTargetList(items = [], emptyMessage, groupKey, options = {}) {
  const {
    isSelected = () => false,
  } = options;
  if (!Array.isArray(items) || items.length === 0) {
    return renderPlaceholder(emptyMessage);
  }
  return `
    <div class="update-entry-stack">
      ${items.map((item, index) => renderTargetEntry(item, index, groupKey, {
        selected: isSelected(item),
      })).join('')}
    </div>
  `;
}

function renderHistoryList(items = [], emptyMessage) {
  if (!Array.isArray(items) || items.length === 0) {
    return renderPlaceholder(emptyMessage);
  }
  return `
    <div class="update-entry-stack">
      ${items.map((entry, index) => renderHistoryEntry(entry, index)).join('')}
    </div>
  `;
}

export function createUpdateManagerController(ctx, deps) {
  let requestToken = 0;
  let actionModalHideTimer = null;
  let activeBatchButtons = new Set();
  const selectionState = {
    project: new Set(),
    container: new Set(),
  };
  const selectionAnchors = {
    project: null,
    container: null,
  };

  function getCollectionLabel(targetType, { plural = false } = {}) {
    if (targetType === 'project') {
      return plural ? 'stacks' : 'stack';
    }
    return plural ? 'containers' : 'container';
  }

  function getSelectionSet(targetType) {
    return selectionState[targetType === 'project' ? 'project' : 'container'];
  }

  function getSelectionAnchor(targetType) {
    return selectionAnchors[targetType === 'project' ? 'project' : 'container'];
  }

  function setSelectionAnchor(targetType, targetId) {
    selectionAnchors[targetType === 'project' ? 'project' : 'container'] = targetId || null;
  }

  function clearSelection(targetType) {
    getSelectionSet(targetType).clear();
    setSelectionAnchor(targetType, null);
  }

  function ensureModal() {
    if (!ctx.elements.updateManagerModalEl) {
      return null;
    }
    ctx.state.updateManagerModal = bootstrap.Modal.getOrCreateInstance(ctx.elements.updateManagerModalEl);
    return ctx.state.updateManagerModal;
  }

  function ensureActionModal() {
    if (!ctx.elements.updateManagerActionModalEl) {
      return null;
    }
    ctx.state.updateManagerActionModal = bootstrap.Modal.getOrCreateInstance(ctx.elements.updateManagerActionModalEl, {
      backdrop: 'static',
      keyboard: false,
    });
    return ctx.state.updateManagerActionModal;
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

  function getReadyTargets(targetType) {
    const payload = ctx.state.updateManagerPayload || {};
    const source = targetType === 'project' ? payload.projects : payload.containers;
    return (Array.isArray(source) ? source : []).filter((item) => String(item.update_state || '').toLowerCase() === 'ready');
  }

  function getSelectedTargets(targetType) {
    const selectedIds = getSelectionSet(targetType);
    return getReadyTargets(targetType).filter((item) => selectedIds.has(item.target_id));
  }

  function pruneSelections() {
    ['project', 'container'].forEach((targetType) => {
      const validIds = new Set(getReadyTargets(targetType).map((item) => item.target_id));
      const selection = getSelectionSet(targetType);
      Array.from(selection).forEach((targetId) => {
        if (!validIds.has(targetId)) {
          selection.delete(targetId);
        }
      });
      if (!validIds.has(getSelectionAnchor(targetType))) {
        setSelectionAnchor(targetType, null);
      }
    });
  }

  function renderBulkButtonMarkup(targetType, count) {
    const pluralLabel = getCollectionLabel(targetType, { plural: true });
    const suffix = count > 0 ? ` (${count})` : '';
    return `
      <i class="bi bi-arrow-repeat" aria-hidden="true"></i>
      <span>Update all ${escapeHtml(pluralLabel)}${escapeHtml(suffix)}</span>
    `;
  }

  function renderSelectedButtonMarkup(targetType, count) {
    const pluralLabel = getCollectionLabel(targetType, { plural: true });
    const suffix = count > 0 ? ` (${count})` : '';
    return `
      <i class="bi bi-check2-square" aria-hidden="true"></i>
      <span>Update selected ${escapeHtml(pluralLabel)}${escapeHtml(suffix)}</span>
    `;
  }

  function syncBatchActionButtons({ activeButtons = new Set() } = {}) {
    const lockedButtons = activeButtons.size > 0 ? activeButtons : activeBatchButtons;
    const buttonMap = [
      ['project', 'all', ctx.elements.updateAllProjectsBtn],
      ['project', 'selected', ctx.elements.updateSelectedProjectsBtn],
      ['container', 'all', ctx.elements.updateAllContainersBtn],
      ['container', 'selected', ctx.elements.updateSelectedContainersBtn],
    ];

    buttonMap.forEach(([targetType, mode, button]) => {
      if (!button || lockedButtons.has(button)) {
        return;
      }
      const count = mode === 'selected'
        ? getSelectedTargets(targetType).length
        : getReadyTargets(targetType).length;
      button.innerHTML = mode === 'selected'
        ? renderSelectedButtonMarkup(targetType, count)
        : renderBulkButtonMarkup(targetType, count);
      button.disabled = count === 0 || ctx.state.updateManagerLoading || ctx.state.updateManagerActionBusy;
    });
  }

  function syncActionLockState(options = {}) {
    if (ctx.elements.refreshUpdateManagerBtn && !ctx.state.updateManagerLoading) {
      ctx.elements.refreshUpdateManagerBtn.disabled = ctx.state.updateManagerActionBusy;
    }
    if (ctx.elements.updateManagerHideBlocked) {
      ctx.elements.updateManagerHideBlocked.disabled = ctx.state.updateManagerActionBusy;
    }
    syncBatchActionButtons(options);
  }

  function setActionModalClosable(enabled) {
    if (ctx.elements.updateManagerActionCloseBtn) {
      ctx.elements.updateManagerActionCloseBtn.disabled = !enabled;
    }
    if (ctx.elements.updateManagerActionCloseIcon) {
      ctx.elements.updateManagerActionCloseIcon.disabled = !enabled;
    }
  }

  function clearActionModalAutoHide() {
    if (actionModalHideTimer) {
      window.clearTimeout(actionModalHideTimer);
      actionModalHideTimer = null;
    }
  }

  function scheduleActionModalAutoHide() {
    clearActionModalAutoHide();
    actionModalHideTimer = window.setTimeout(() => {
      ctx.state.updateManagerActionModal?.hide();
      actionModalHideTimer = null;
    }, 1600);
  }

  function setActionModalState({ title, state = 'pending', message = '', detail = '' }) {
    const stateLabelMap = {
      pending: 'In progress',
      success: 'Success',
      failure: 'Failed',
    };
    const stateIconMap = {
      pending: '<i class="bi bi-arrow-repeat spin-inline" aria-hidden="true"></i>',
      success: '<i class="bi bi-check-circle-fill" aria-hidden="true"></i>',
      failure: '<i class="bi bi-exclamation-octagon-fill" aria-hidden="true"></i>',
    };
    if (ctx.elements.updateManagerActionModalLabel) {
      ctx.elements.updateManagerActionModalLabel.textContent = title;
    }
    if (ctx.elements.updateManagerActionState) {
      ctx.elements.updateManagerActionState.dataset.state = state;
      ctx.elements.updateManagerActionState.innerHTML = `${stateIconMap[state] || stateIconMap.pending}<span>${stateLabelMap[state] || stateLabelMap.pending}</span>`;
    }
    if (ctx.elements.updateManagerActionMessage) {
      ctx.elements.updateManagerActionMessage.textContent = message;
    }
    if (ctx.elements.updateManagerActionDetail) {
      ctx.elements.updateManagerActionDetail.textContent = detail;
      ctx.elements.updateManagerActionDetail.hidden = !detail;
    }
    setActionModalClosable(state !== 'pending');
    if (state === 'success') {
      scheduleActionModalAutoHide();
    } else {
      clearActionModalAutoHide();
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
    if (ctx.elements.updateHistoryRetentionNotice && payload?.history_notice) {
      ctx.elements.updateHistoryRetentionNotice.textContent = payload.history_notice;
    }
    pruneSelections();
    const projects = Array.isArray(payload.projects) ? payload.projects : [];
    const containers = Array.isArray(payload.containers) ? payload.containers : [];
    const history = Array.isArray(payload.history) ? payload.history : [];
    const visibleProjects = ctx.state.updateManagerHideBlocked
      ? projects.filter((item) => String(item.update_state || '').toLowerCase() !== 'blocked')
      : projects;
    const visibleContainers = ctx.state.updateManagerHideBlocked
      ? containers.filter((item) => String(item.update_state || '').toLowerCase() !== 'blocked')
      : containers;
    const hiddenBlockedCount = (projects.length - visibleProjects.length) + (containers.length - visibleContainers.length);
    const metaSuffix = ctx.state.updateManagerHideBlocked && hiddenBlockedCount > 0
      ? ` • ${hiddenBlockedCount} blocked entr${hiddenBlockedCount === 1 ? 'y hidden' : 'ies hidden'}`
      : '';

    ctx.elements.updateManagerMeta.textContent = `${visibleProjects.length} Compose stack(s), ${visibleContainers.length} standalone container(s), ${history.length} history entr${history.length === 1 ? 'y' : 'ies'}${metaSuffix}`;
    ctx.elements.updateManagerProjectList.innerHTML = renderTargetList(
      visibleProjects,
      ctx.state.updateManagerHideBlocked
        ? 'No unblocked Compose stacks currently have a confirmed update available.'
        : 'No Compose stacks currently have a confirmed update available.',
      'projects',
      {
        isSelected: (item) => getSelectionSet('project').has(item.target_id),
      },
    );
    ctx.elements.updateManagerContainerList.innerHTML = renderTargetList(
      visibleContainers,
      ctx.state.updateManagerHideBlocked
        ? 'No unblocked standalone containers currently have a confirmed update available.'
        : 'No standalone containers currently have a confirmed update available.',
      'containers',
      {
        isSelected: (item) => getSelectionSet('container').has(item.target_id),
      },
    );
    ctx.elements.updateManagerHistoryList.innerHTML = renderHistoryList(history, 'No updates or rollbacks have been recorded yet.');
    syncActionLockState();
  }

  async function requestUpdateTarget(targetType, targetId) {
    const response = await fetch('/api/update-manager/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_type: targetType, target_id: targetId }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.ok) {
      const error = new Error(payload.message || `Update failed for ${targetId}.`);
      error.historyEntry = payload.history_entry || null;
      throw error;
    }
    return payload;
  }

  function normalizeHistoryEntry(entry = {}) {
    const metadata = entry.metadata || {};
    return {
      ...entry,
      can_rollback: (
        entry.action === 'update'
        && entry.result === 'success'
        && Boolean(metadata.rollback_ready)
        && !entry.rollback_of
      ),
    };
  }

  function removeTargetFromPayload(targetType, targetId) {
    const payload = ctx.state.updateManagerPayload;
    if (!payload) {
      return;
    }
    const collectionKey = targetType === 'project' ? 'projects' : 'containers';
    payload[collectionKey] = (Array.isArray(payload[collectionKey]) ? payload[collectionKey] : [])
      .filter((item) => item.target_id !== targetId);
    getSelectionSet(targetType).delete(targetId);
    if (getSelectionAnchor(targetType) === targetId) {
      setSelectionAnchor(targetType, null);
    }
  }

  function prependHistoryEntry(entry) {
    if (!entry || !ctx.state.updateManagerPayload) {
      return;
    }
    const payload = ctx.state.updateManagerPayload;
    payload.history = [
      normalizeHistoryEntry(entry),
      ...(Array.isArray(payload.history) ? payload.history : []),
    ].slice(0, 25);
  }

  function applyLocalManagedActionUpdate(targetType, targetId, historyEntry) {
    if (!ctx.state.updateManagerPayload) {
      return;
    }
    if (historyEntry) {
      prependHistoryEntry(historyEntry);
    }
    removeTargetFromPayload(targetType, targetId);
    renderPayload(ctx.state.updateManagerPayload);
  }

  async function refreshAfterManagedAction(title, detail) {
    setActionModalState({
      title,
      state: 'pending',
      message: 'Refreshing dashboard metrics…',
      detail,
    });
    await deps.fetchMetrics();
    setActionModalState({
      title,
      state: 'pending',
      message: 'Reloading update inventory…',
      detail,
    });

    try {
      await loadTargets({ throwOnError: true });
      return '';
    } catch (error) {
      return error.message || 'Unable to reload the update inventory after the action completed.';
    }
  }

  function formatBulkResultDetail(targetType, successes, failures, refreshWarning = '') {
    const total = successes.length + failures.length;
    const lines = [
      `Sequential mode completed ${total} ${getCollectionLabel(targetType, { plural: total !== 1 })}.`,
      `${successes.length} succeeded, ${failures.length} failed.`,
    ];

    if (successes.length > 0) {
      lines.push(`Updated: ${successes.map((item) => item.name).join(', ')}`);
    }

    if (failures.length > 0) {
      failures.slice(0, 5).forEach((item) => {
        lines.push(`Failed: ${item.name} - ${item.message}`);
      });
      if (failures.length > 5) {
        lines.push(`${failures.length - 5} additional failure(s) omitted.`);
      }
    }

    if (refreshWarning) {
      lines.push(`Inventory refresh warning: ${refreshWarning}`);
    }

    return lines.join('\n');
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
      if (options.throwOnError) {
        throw error;
      }
    } finally {
      if (token === requestToken) {
        ctx.state.updateManagerLoading = false;
        ctx.elements.refreshUpdateManagerBtn.disabled = false;
        ctx.elements.refreshUpdateManagerBtn.textContent = 'Refresh list';
        syncActionLockState();
      }
    }
  }

  function setEntryExpanded(toggleButton, expanded) {
    const entry = toggleButton?.closest('.update-entry');
    const panel = entry?.querySelector('.update-entry-panel');
    if (!entry || !panel) {
      return;
    }

    toggleButton.setAttribute('aria-expanded', String(expanded));
    panel.setAttribute('aria-hidden', String(!expanded));
    entry.classList.toggle('is-expanded', expanded);

    if (expanded) {
      panel.hidden = false;
      panel.style.maxHeight = '0px';
      const onTransitionEnd = () => {
        if (entry.classList.contains('is-expanded')) {
          panel.style.maxHeight = 'none';
        }
        panel.removeEventListener('transitionend', onTransitionEnd);
      };
      panel.addEventListener('transitionend', onTransitionEnd);
      requestAnimationFrame(() => {
        panel.style.maxHeight = `${panel.scrollHeight}px`;
      });
      return;
    }

    if (panel.style.maxHeight === 'none') {
      panel.style.maxHeight = `${panel.scrollHeight}px`;
    }
    panel.style.maxHeight = `${panel.scrollHeight}px`;
    requestAnimationFrame(() => {
      panel.style.maxHeight = '0px';
    });

    const onTransitionEnd = () => {
      if (!entry.classList.contains('is-expanded')) {
        panel.hidden = true;
      }
      panel.removeEventListener('transitionend', onTransitionEnd);
    };
    panel.addEventListener('transitionend', onTransitionEnd);
  }

  function toggleEntry(toggleButton) {
    const expanded = toggleButton.getAttribute('aria-expanded') === 'true';
    setEntryExpanded(toggleButton, !expanded);
  }

  function getListElementForType(targetType) {
    return targetType === 'project'
      ? ctx.elements.updateManagerProjectList
      : ctx.elements.updateManagerContainerList;
  }

  function getVisibleSelectableIds(targetType) {
    const listElement = getListElementForType(targetType);
    if (!listElement) {
      return [];
    }
    return Array.from(listElement.querySelectorAll(`.update-entry-select[data-update-select-type="${targetType}"]`))
      .filter((checkbox) => !checkbox.disabled)
      .map((checkbox) => checkbox.dataset.updateSelectId)
      .filter(Boolean);
  }

  function handleSelectionToggle(checkbox, shiftKey) {
    const targetType = checkbox.dataset.updateSelectType;
    const targetId = checkbox.dataset.updateSelectId;
    if (!targetType || !targetId) {
      return;
    }

    const selection = getSelectionSet(targetType);
    const shouldSelect = checkbox.checked;

    if (shiftKey) {
      const anchorId = getSelectionAnchor(targetType);
      const visibleIds = getVisibleSelectableIds(targetType);
      const anchorIndex = visibleIds.indexOf(anchorId);
      const targetIndex = visibleIds.indexOf(targetId);
      if (anchorIndex !== -1 && targetIndex !== -1) {
        const [start, end] = anchorIndex < targetIndex
          ? [anchorIndex, targetIndex]
          : [targetIndex, anchorIndex];
        visibleIds.slice(start, end + 1).forEach((visibleId) => {
          if (shouldSelect) {
            selection.add(visibleId);
          } else {
            selection.delete(visibleId);
          }
        });
      } else if (shouldSelect) {
        selection.add(targetId);
      } else {
        selection.delete(targetId);
      }
    } else if (shouldSelect) {
      selection.add(targetId);
    } else {
      selection.delete(targetId);
    }

    setSelectionAnchor(targetType, targetId);
    renderPayload(ctx.state.updateManagerPayload || {});
  }

  async function executeManagedAction({
    title,
    button,
    busyMarkup,
    pendingMessage,
    successHeading,
    failureHeading,
    request,
    afterSuccess,
  }) {
    if (ctx.state.updateManagerActionBusy) {
      return;
    }

    const originalMarkup = button.innerHTML;
    ctx.state.updateManagerActionBusy = true;
    button.disabled = true;
    button.innerHTML = busyMarkup;
    syncActionLockState();
    setManagerStatus(pendingMessage, 'info');
    setActionModalState({
      title,
      state: 'pending',
      message: pendingMessage,
      detail: 'Waiting for the server to finish the requested action.',
    });
    ensureActionModal()?.show();

    try {
      const payload = await request();
      if (typeof afterSuccess === 'function') {
        afterSuccess(payload);
      }
      const successMessage = payload.message || successHeading;
      setStatusMessage(ctx, successMessage, 'success');
      const refreshWarning = await refreshAfterManagedAction(title, successMessage);

      const detail = refreshWarning
        ? `${successMessage}\nInventory refresh warning: ${refreshWarning}`
        : successMessage;
      setActionModalState({
        title,
        state: 'success',
        message: successHeading,
        detail,
      });
      setManagerStatus(successMessage, refreshWarning ? 'warning' : 'success');
    } catch (error) {
      if (error.historyEntry) {
        prependHistoryEntry(error.historyEntry);
        renderPayload(ctx.state.updateManagerPayload || {});
      }
      const failureMessage = error.message || failureHeading;
      setActionModalState({
        title,
        state: 'failure',
        message: failureHeading,
        detail: failureMessage,
      });
      setManagerStatus(failureMessage, 'danger');
      setStatusMessage(ctx, failureMessage, 'danger');
    } finally {
      ctx.state.updateManagerActionBusy = false;
      if (button.isConnected) {
        button.disabled = false;
        button.innerHTML = originalMarkup;
      }
      syncActionLockState();
    }
  }

  async function executeUpdate(targetType, targetId, button, strategy = '') {
    const typeLabel = formatTargetType(targetType);
    const safeExternalMode = String(strategy || '').toLowerCase() === 'external_project_safe_recreate';
    const confirmed = await deps.confirmAction({
      title: safeExternalMode ? 'Apply safe external update' : 'Apply update',
      message: safeExternalMode
        ? `Update ${typeLabel.toLowerCase()} "${targetId}" without compose files? statainer will recreate only the running services that have a newer image available while preserving their current volumes, configuration, networks and environment where possible.`
        : `Update ${typeLabel.toLowerCase()} "${targetId}" with the experimental safe workflow? statainer will preserve volumes, configuration, networks and environment where possible, but you should still review the change carefully before continuing.`,
      confirmLabel: safeExternalMode ? 'Update safely' : 'Apply update',
      cancelLabel: 'Cancel',
      tone: 'warning',
    });
    if (!confirmed) {
      return;
    }

    await executeManagedAction({
      title: `Updating ${targetId}`,
      button,
      busyMarkup: '<i class="bi bi-arrow-repeat spin-inline" aria-hidden="true"></i><span>Updating...</span>',
      pendingMessage: safeExternalMode
        ? `Applying safe external update for ${targetId}…`
        : `Applying update for ${targetId}…`,
      successHeading: 'Update completed',
      failureHeading: 'Update failed',
      request: () => requestUpdateTarget(targetType, targetId),
      afterSuccess: (payload) => applyLocalManagedActionUpdate(targetType, targetId, payload.history_entry),
    });
  }

  async function executeBatchUpdate(targetType, button, targets, options = {}) {
    if (ctx.state.updateManagerActionBusy) {
      return;
    }

    const selectionMode = options.selectionMode === 'selected' ? 'selected' : 'all';
    const pluralLabel = getCollectionLabel(targetType, { plural: true });
    const singularLabel = getCollectionLabel(targetType);
    const completedLabel = getCollectionLabel(targetType, { plural: targets.length !== 1 });
    const actionLabel = selectionMode === 'selected'
      ? `selected ${pluralLabel}`
      : `all ${pluralLabel}`;

    if (targets.length === 0) {
      const emptyLabel = selectionMode === 'selected'
        ? `No ${pluralLabel} are currently selected.`
        : `No update-ready ${pluralLabel} are available right now.`;
      setManagerStatus(emptyLabel, 'warning');
      return;
    }

    const confirmed = await deps.confirmAction({
      title: `Update ${selectionMode === 'selected' ? 'selected' : 'all'} ${pluralLabel}`,
      message: `statainer will update ${targets.length} ${selectionMode === 'selected' ? 'selected ' : ''}${pluralLabel} sequentially for safety. Each ${singularLabel} keeps its normal safe update workflow, and failures will be recorded while the remaining targets continue.`,
      confirmLabel: `Update ${selectionMode === 'selected' ? 'selected' : 'all'} ${pluralLabel}`,
      cancelLabel: 'Cancel',
      tone: 'warning',
    });
    if (!confirmed) {
      return;
    }

    const originalMarkup = button.innerHTML;
    const successes = [];
    const failures = [];
    ctx.state.updateManagerActionBusy = true;
    button.disabled = true;
    button.innerHTML = `
      <i class="bi bi-arrow-repeat spin-inline" aria-hidden="true"></i>
      <span>Updating ${escapeHtml(actionLabel)}...</span>
    `;
    activeBatchButtons = new Set([button]);
    syncActionLockState({ activeButtons: activeBatchButtons });
    setManagerStatus(`Preparing sequential update for ${targets.length} ${selectionMode === 'selected' ? 'selected ' : ''}${pluralLabel}…`, 'info');
    ensureActionModal()?.show();

    try {
      for (let index = 0; index < targets.length; index += 1) {
        const target = targets[index];
        setActionModalState({
          title: `Updating ${actionLabel}`,
          state: 'pending',
          message: `Updating ${index + 1} of ${targets.length}: ${target.name}`,
          detail: [
            'Sequential mode for safety.',
            `${successes.length} completed successfully.`,
            `${failures.length} failed so far.`,
          ].join('\n'),
        });

        try {
          const payload = await requestUpdateTarget(target.type, target.target_id);
          successes.push({
            name: target.name,
            message: payload.message || `${formatTargetType(target.type)} updated successfully.`,
          });
          applyLocalManagedActionUpdate(target.type, target.target_id, payload.history_entry);
        } catch (error) {
          failures.push({
            name: target.name,
            message: error.message || `Update failed for ${target.name}.`,
          });
          if (error.historyEntry) {
            prependHistoryEntry(error.historyEntry);
            renderPayload(ctx.state.updateManagerPayload || {});
          }
          setManagerStatus(
            `Batch update hit a failure on ${target.name}. statainer will continue with the remaining ${pluralLabel}.`,
            'warning',
          );
        }
      }

      const refreshWarning = await refreshAfterManagedAction(
        `Updating ${actionLabel}`,
        `${successes.length} succeeded, ${failures.length} failed.`,
      );
      const detail = formatBulkResultDetail(targetType, successes, failures, refreshWarning);
      const hadFailures = failures.length > 0;
      const summaryMessage = hadFailures
        ? `Batch update finished with ${failures.length} failure(s).`
        : `Updated ${targets.length} ${completedLabel} successfully.`;

      setActionModalState({
        title: hadFailures ? 'Batch update finished with errors' : 'Batch update completed',
        state: hadFailures ? 'failure' : 'success',
        message: summaryMessage,
        detail,
      });
      setManagerStatus(summaryMessage, hadFailures ? 'warning' : 'success');
      setStatusMessage(ctx, summaryMessage, hadFailures ? 'warning' : 'success');
    } catch (error) {
      const failureMessage = error.message || `Unable to update ${actionLabel}.`;
      setActionModalState({
        title: `Updating ${actionLabel}`,
        state: 'failure',
        message: 'Batch update failed',
        detail: failureMessage,
      });
      setManagerStatus(failureMessage, 'danger');
      setStatusMessage(ctx, failureMessage, 'danger');
    } finally {
      ctx.state.updateManagerActionBusy = false;
      activeBatchButtons = new Set();
      if (button.isConnected) {
        button.disabled = false;
        button.innerHTML = originalMarkup;
      }
      syncActionLockState();
    }
  }

  async function executeBulkUpdate(targetType, button) {
    await executeBatchUpdate(targetType, button, getReadyTargets(targetType), {
      selectionMode: 'all',
    });
  }

  async function executeSelectedUpdate(targetType, button) {
    await executeBatchUpdate(targetType, button, getSelectedTargets(targetType), {
      selectionMode: 'selected',
    });
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

    await executeManagedAction({
      title: `Rolling back #${historyId}`,
      button,
      busyMarkup: '<i class="bi bi-arrow-counterclockwise spin-inline" aria-hidden="true"></i><span>Rolling back...</span>',
      pendingMessage: `Running rollback for history entry #${historyId}…`,
      successHeading: 'Rollback completed',
      failureHeading: 'Rollback failed',
      request: async () => {
        const response = await fetch('/api/update-manager/rollback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ history_id: Number(historyId) }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !payload.ok) {
          throw new Error(payload.message || 'Rollback failed.');
        }
        return payload;
      },
    });
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
    const selectionInput = event.target.closest('[data-update-select-type][data-update-select-id]');
    if (selectionInput) {
      event.stopPropagation();
      handleSelectionToggle(selectionInput, event.shiftKey);
      return;
    }

    const toggleButton = event.target.closest('[data-update-entry-toggle]');
    if (toggleButton) {
      toggleEntry(toggleButton);
      return;
    }

    const updateButton = event.target.closest('[data-update-target-type][data-update-target-id]');
    if (updateButton) {
      executeUpdate(
        updateButton.dataset.updateTargetType,
        updateButton.dataset.updateTargetId,
        updateButton,
        updateButton.dataset.updateStrategy,
      );
      return;
    }

    const rollbackButton = event.target.closest('[data-rollback-history-id]');
    if (rollbackButton) {
      executeRollback(rollbackButton.dataset.rollbackHistoryId, rollbackButton);
    }
  }

  function init() {
    ensureModal();
    ensureActionModal();
    ctx.state.updateManagerHideBlocked = localStorage.getItem('updateManagerHideBlocked') === 'true';
    if (ctx.elements.updateManagerHideBlocked) {
      ctx.elements.updateManagerHideBlocked.checked = ctx.state.updateManagerHideBlocked;
    }
    ctx.elements.updateManagerToggle?.addEventListener('click', openModal);
    ctx.elements.sidebarUpdateManagerToggle?.addEventListener('click', (event) => {
      deps.closeMobileMenu?.();
      openModal(event);
    });
    ctx.elements.refreshUpdateManagerBtn?.addEventListener('click', () => loadTargets({ refresh: true }));
    ctx.elements.updateSelectedProjectsBtn?.addEventListener('click', () => executeSelectedUpdate('project', ctx.elements.updateSelectedProjectsBtn));
    ctx.elements.updateAllProjectsBtn?.addEventListener('click', () => executeBulkUpdate('project', ctx.elements.updateAllProjectsBtn));
    ctx.elements.updateSelectedContainersBtn?.addEventListener('click', () => executeSelectedUpdate('container', ctx.elements.updateSelectedContainersBtn));
    ctx.elements.updateAllContainersBtn?.addEventListener('click', () => executeBulkUpdate('container', ctx.elements.updateAllContainersBtn));
    ctx.elements.updateManagerHideBlocked?.addEventListener('change', () => {
      ctx.state.updateManagerHideBlocked = ctx.elements.updateManagerHideBlocked.checked;
      localStorage.setItem('updateManagerHideBlocked', String(ctx.state.updateManagerHideBlocked));
      if (ctx.state.updateManagerPayload) {
        renderPayload(ctx.state.updateManagerPayload);
      }
    });
    ctx.elements.updateManagerActionCloseBtn?.addEventListener('click', () => {
      clearActionModalAutoHide();
      ctx.state.updateManagerActionModal?.hide();
    });
    ctx.elements.updateManagerActionCloseIcon?.addEventListener('click', () => {
      clearActionModalAutoHide();
      ctx.state.updateManagerActionModal?.hide();
    });
    ctx.elements.updateManagerActionModalEl?.addEventListener('hidden.bs.modal', () => {
      clearActionModalAutoHide();
    });
    ctx.elements.updateManagerModalEl?.addEventListener('click', handleModalClick);
    ctx.elements.updateManagerModalEl?.addEventListener('hidden.bs.modal', () => {
      clearSelection('project');
      clearSelection('container');
      if (ctx.state.updateManagerPayload) {
        renderPayload(ctx.state.updateManagerPayload);
      }
      setManagerStatus('');
    });
    syncActionLockState();
  }

  return {
    init,
    loadTargets,
    openModal,
    updateBadgeFromMetrics,
  };
}
