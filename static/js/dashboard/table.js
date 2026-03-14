import { escapeHtml, normalizeStatus, setStatusMessage } from './helpers.js';

export function createTableController(ctx, deps) {
  function calculateVisibleColumns() {
    let visibleColumnCount = 0;
    const tableClasses = ctx.elements.metricsTable.classList;
    document.querySelectorAll('#metricsTable thead th').forEach((th) => {
      const colClassIdentifier = [...th.classList].find((className) => className.startsWith('col-'));
      if (colClassIdentifier && !tableClasses.contains(`hide-${colClassIdentifier}`)) {
        visibleColumnCount++;
      }
    });
    return Math.max(1, visibleColumnCount);
  }

  function updateProjectRowColspans() {
    const currentVisibleCols = calculateVisibleColumns();
    document.querySelectorAll('.project-row td[colspan]').forEach((cell) => {
      cell.setAttribute('colspan', currentVisibleCols);
    });
  }

  function applyColumnVisibility() {
    ctx.elements.columnToggleInputs.forEach((toggle) => {
      ctx.elements.metricsTable.classList.toggle(`hide-col-${toggle.value}`, !toggle.checked);
    });
    updateProjectRowColspans();
    if (ctx.state.allMetricsData.length > 0) {
      ctx.elements.tableStatusDiv.textContent = '';
    }
  }

  function renderContainerRow(item, projectName, collapsed) {
    const row = document.createElement('tr');
    if (projectName) {
      row.classList.add('child-row', `project-${projectName}`);
      row.style.display = collapsed ? 'none' : '';
    }

    let nameCellClass = '';
    if (!projectName && String(item.status || '').toLowerCase() === 'exited') {
      nameCellClass = 'exited-container-name';
    }

    const imageName = escapeHtml(item.image || 'N/A');
    const portInfo = escapeHtml(item.ports || 'N/A');
    const hostPort = (item.ports || '').split('->')[0].split(':').pop();
    let baseHost = 'localhost';
    if (localStorage.getItem('useCustomIP') === 'true') {
      let raw = (localStorage.getItem('serverIP') || '').trim();
      raw = raw.split(/[,\s]+/)[0];
      raw = raw.replace(/\/$/, '').replace(/^https?:\/\//i, '');
      baseHost = raw || 'localhost';
    }

    const uptimeText = item.uptime || 'N/A';
    const restartsText = item.restarts ?? 'N/A';
    const netRxText = item.net_io_rx !== null && item.net_io_rx !== undefined ? Number(item.net_io_rx).toFixed(2) : '-';
    const netTxText = item.net_io_tx !== null && item.net_io_tx !== undefined ? Number(item.net_io_tx).toFixed(2) : '-';
    const blockRText = item.block_io_r !== null && item.block_io_r !== undefined ? Number(item.block_io_r).toFixed(2) : '-';
    const blockWText = item.block_io_w !== null && item.block_io_w !== undefined ? Number(item.block_io_w).toFixed(2) : '-';
    const cpuNum = item.cpu !== null && item.cpu !== undefined ? Number(item.cpu) : Number.NaN;
    const memNum = item.mem !== null && item.mem !== undefined ? Number(item.mem) : Number.NaN;
    const maxCpuPercent = ctx.config.maxCpuPercent ?? 100;
    const cpuProgress = !Number.isNaN(cpuNum) ? Math.min(100, (cpuNum / maxCpuPercent) * 100) : 0;
    const memProgress = !Number.isNaN(memNum) ? Math.max(0, Math.min(100, memNum)) : 0;
    const statusValue = escapeHtml(item.status || 'N/A');
    const statusClass = normalizeStatus(item.status || 'unknown');
    const hasUiLink = /^\d+$/.test(hostPort);
    const isRunning = String(item.status || '').toLowerCase() === 'running';
    const canStart = !isRunning;
    const canStop = isRunning;
    const canRestart = Boolean(item.status);

    let cpuClass = 'bg-success';
    if (!Number.isNaN(cpuNum) && cpuNum >= 80) cpuClass = 'bg-danger';
    else if (!Number.isNaN(cpuNum) && cpuNum >= 50) cpuClass = 'bg-warning';

    let ramClass = 'bg-success';
    if (!Number.isNaN(memNum) && memNum >= 80) ramClass = 'bg-danger';
    else if (!Number.isNaN(memNum) && memNum >= 50) ramClass = 'bg-warning';

    const gpuCell = (() => {
      if (item.gpu_max !== undefined && item.gpu_max !== null) {
        const gpuValue = Number(item.gpu_max);
        if (!Number.isNaN(gpuValue)) {
          return `<td class="col-gpu"><div class="progress"><div class="progress-bar bg-info" style="width:${gpuValue.toFixed(2)}%">${gpuValue.toFixed(2)}%</div></div></td>`;
        }
      }
      return '<td class="col-gpu">N/A</td>';
    })();

    row.innerHTML =
      `<td class="col-name${nameCellClass ? ` ${nameCellClass}` : ''}">${escapeHtml(item.name || 'N/A')}</td>`
      + `<td class="col-cpu"><span>${!Number.isNaN(cpuNum) ? `${cpuNum.toFixed(2)}%` : 'N/A'}</span><div class="progress" role="progressbar" aria-valuenow="${cpuProgress}" aria-valuemin="0" aria-valuemax="100"><div class="progress-bar ${cpuClass}" style="width:${cpuProgress}%"></div></div></td>`
      + `<td class="col-ram"><span>${!Number.isNaN(memNum) ? `${memNum.toFixed(2)}%` : 'N/A'}</span><div class="progress" role="progressbar" aria-valuenow="${memProgress}" aria-valuemin="0" aria-valuemax="100"><div class="progress-bar ${ramClass}" style="width:${memProgress}%"></div></div></td>`
      + gpuCell
      + `<td class="col-pid">${item.pid_count ?? 'N/A'}</td>`
      + `<td class="col-memlimit">${
        (item.mem_usage !== null && item.mem_usage !== undefined && item.mem_limit !== null && item.mem_limit !== undefined && Number(item.mem_limit) > 0)
          ? `${Number(item.mem_usage).toFixed(2)} / ${Number(item.mem_limit).toFixed(2)} MB`
          : (item.mem_limit === 0 || item.mem_limit === null || item.mem_limit === undefined || Number(item.mem_limit) === 0)
            ? ((item.mem_usage !== null && item.mem_usage !== undefined) ? `${Number(item.mem_usage).toFixed(2)} / NL` : 'NL')
            : (item.mem_limit !== null && item.mem_limit !== undefined)
              ? `${Number(item.mem_limit).toFixed(2)} MB`
              : (item.mem_usage !== null && item.mem_usage !== undefined)
                ? `${Number(item.mem_usage).toFixed(2)} MB`
                : 'N/A'
      }</td>`
      + `<td class="col-status"><span class="status-pill status-${statusClass}">${statusValue}</span></td>`
      + `<td class="col-uptime">${escapeHtml(uptimeText)}</td>`
      + `<td class="col-netio">${netRxText} / ${netTxText}<span class="metric-callout">Rx / Tx MB</span></td>`
      + `<td class="col-blockio">${blockRText} / ${blockWText}<span class="metric-callout">Read / Write MB</span></td>`
      + `<td class="col-image" title="${imageName}" style="max-width:200px;overflow:hidden;text-overflow:ellipsis;">${imageName}</td>`
      + `<td class="col-ports" title="${portInfo}" style="max-width:250px;overflow:hidden;text-overflow:ellipsis;">${portInfo}</td>`
      + `<td class="col-restarts">${restartsText}</td>`
      + `<td class="col-logs text-center"><a href="/logs/${item.id}" target="_blank" class="btn btn-link btn-sm p-0"><img src="/static/icons/table_logs.svg" alt="Logs" width="18" height="18"></a></td>`
      + `<td class="col-charts text-center"><button class="btn btn-link btn-sm p-0 show-chart-btn" data-container-id="${item.id}" data-container-name="${escapeHtml(item.name || 'Unknown')}"><img src="/static/icons/table_charts.svg" alt="Chart" width="18" height="18"></button></td>`
      + `<td class="col-ui text-center">${hasUiLink ? `<a href="http://${baseHost}:${hostPort}" target="_blank" class="btn btn-link btn-sm p-0"><img src="/static/icons/table_ui.svg" alt="UI" width="18" height="18"></a>` : '<span class="text-muted small">No UI</span>'}</td>`
      + `<td class="col-update text-center">${item.update_available ? '<img src="/static/icons/table_updates.svg" alt="Update Available" width="18" height="18">' : ''}</td>`
      + `<td class="col-actions text-center">`
      + `<button class="btn btn-outline-success btn-sm start-btn" ${canStart ? '' : 'disabled'} title="${canStart ? 'Start container' : 'Container already running'}"><img src="/static/icons/table_play.svg" alt="Start" width="24" height="24"></button>`
      + `<button class="btn btn-outline-warning btn-sm stop-btn" ${canStop ? '' : 'disabled'} title="${canStop ? 'Stop container' : 'Container is not running'}"><img src="/static/icons/table_stop.svg" alt="Stop" width="14" height="14" style="margin:1px;"></button>`
      + `<button class="btn btn-outline-danger btn-sm restart-btn" ${canRestart ? '' : 'disabled'} title="Restart container"><img src="/static/icons/table_restart.svg" alt="Restart" width="24" height="24"></button>`
      + `</td>`;

    ctx.elements.metricsTableBody.appendChild(row);
  }

  function renderTable(data) {
    ctx.elements.metricsTableBody.innerHTML = '';
    ctx.elements.tableStatusDiv.textContent = '';

    const filteredData = ctx.elements.filterProject.value
      ? data.filter((item) => item.compose_project === ctx.elements.filterProject.value || (!item.compose_project && ctx.elements.filterProject.value === ''))
      : data;
    const quickFilteredData = filteredData.filter((item) => deps.matchesQuickFilter(item));

    if (quickFilteredData.length === 0) {
      ctx.elements.tableStatusDiv.innerHTML = '<div class="table-empty">No containers match the active filters.</div>';
      return 0;
    }

    let updateAvailableCount = 0;
    if (ctx.elements.sortBy.value === 'name') {
      const projectGroups = {};
      const standaloneContainers = [];

      quickFilteredData.forEach((item) => {
        if (item.compose_project) {
          projectGroups[item.compose_project] ||= [];
          projectGroups[item.compose_project].push(item);
        } else {
          standaloneContainers.push(item);
        }
      });

      const blocks = [];
      Object.entries(projectGroups).forEach(([projectName, containers]) => {
        blocks.push({ type: 'project', name: projectName, containers, sortKey: projectName });
      });
      standaloneContainers.forEach((container) => {
        blocks.push({ type: 'single', name: container.name || '', container, sortKey: container.name || '' });
      });

      const direction = ctx.elements.sortDir.value;
      blocks.sort((a, b) => (
        direction === 'asc'
          ? a.sortKey.localeCompare(b.sortKey, undefined, { sensitivity: 'base' })
          : b.sortKey.localeCompare(a.sortKey, undefined, { sensitivity: 'base' })
      ));

      blocks.forEach((block) => {
        if (block.type === 'project') {
          block.containers.forEach((item) => {
            if (item.update_available) updateAvailableCount++;
          });

          const saved = localStorage.getItem(`projectToggle-${block.name}`);
          const collapsed = saved === 'closed';
          const allExited = block.containers.every((container) => String(container.status || '').toLowerCase() === 'exited');
          const projectRow = document.createElement('tr');
          projectRow.classList.add('project-row');
          projectRow.innerHTML = `
            <td class="col-name${allExited ? ' exited-project-name' : ''}" colspan="${calculateVisibleColumns()}">
              <button class="btn btn-sm btn-link project-toggle" data-project="${block.name}">${collapsed ? '[+]' : '[-]'}</button>
              <span>${block.name} (${block.containers.length})</span>
            </td>`;
          ctx.elements.metricsTableBody.appendChild(projectRow);
          block.containers.forEach((item) => renderContainerRow(item, block.name, collapsed));
        } else {
          if (block.container.update_available) updateAvailableCount++;
          renderContainerRow(block.container, null, false);
        }
      });
    } else {
      quickFilteredData.forEach((item) => {
        if (item.update_available) updateAvailableCount++;
        renderContainerRow(item, null, false);
      });
    }

    ctx.elements.updateInfoText.textContent = updateAvailableCount > 0 ? `(${updateAvailableCount} updates available)` : '';
    return quickFilteredData.length;
  }

  function getSelectedMetrics() {
    return Array.from(ctx.elements.metricsTableBody.querySelectorAll('tr')).map((row) => ({
      id: row.querySelector('.show-chart-btn')?.dataset.containerId || '',
      name: row.querySelector('.col-name')?.textContent || '',
      cpu: row.querySelector('.col-cpu span')?.textContent.replace('%', '') || '',
      ram: row.querySelector('.col-ram span')?.textContent.replace('%', '') || '',
      status: row.querySelector('.col-status')?.textContent || '',
      uptime: row.querySelector('.col-uptime')?.textContent || '',
    }));
  }

  async function handleAction(button, action, containerId, containerName) {
    if (!containerId || !action) {
      return;
    }

    const url = `/api/containers/${containerId}/${action}`;
    button.disabled = true;
    setStatusMessage(ctx, `Starting '${action}' for ${containerName}...`, 'info');

    try {
      const response = await fetch(url, { method: 'POST' });
      if (action === 'update' && response.ok && response.headers.get('content-type')?.includes('text/plain')) {
        ctx.elements.statusMessageArea.textContent = `Updating ${containerName}...\n`;
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let hadOutput = false;
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          if (chunk) {
            ctx.elements.statusMessageArea.textContent += chunk;
            ctx.elements.statusMessageArea.scrollTop = ctx.elements.statusMessageArea.scrollHeight;
            hadOutput = true;
          }
        }
        if (!hadOutput) {
          ctx.elements.statusMessageArea.textContent += '\nNo output received from update operation.';
        }
        ctx.elements.statusMessageArea.textContent += '\nUpdate process finished.';
        setTimeout(deps.fetchMetrics, 1000);
        return;
      }

      const responseText = await response.text();
      let payload = null;
      try {
        payload = JSON.parse(responseText);
      } catch (error) {
        payload = null;
      }

      if (!response.ok) {
        setStatusMessage(ctx, payload?.error ? `Error: ${payload.error}` : `Error: ${responseText || 'Unknown error'}`, 'danger');
      } else {
        setStatusMessage(ctx, payload?.status || responseText || `Action '${action}' completed successfully.`, 'success');
        deps.fetchMetrics();
      }
    } catch (error) {
      setStatusMessage(ctx, `Network or server error: ${error.message}`, 'danger');
    } finally {
      button.disabled = false;
    }
  }

  function handleTableClick(event) {
    const projectToggle = event.target.closest('.project-toggle');
    if (projectToggle) {
      const project = projectToggle.dataset.project;
      const childRows = document.querySelectorAll(`.project-${project}`);
      const isCollapsed = projectToggle.textContent === '[+]';
      projectToggle.textContent = isCollapsed ? '[-]' : '[+]';
      childRows.forEach((row) => {
        row.style.display = isCollapsed ? '' : 'none';
      });
      localStorage.setItem(`projectToggle-${project}`, isCollapsed ? 'open' : 'closed');
      return;
    }

    const chartButton = event.target.closest('.show-chart-btn');
    if (chartButton) {
      deps.showHistoryChart(chartButton.dataset.containerId, chartButton.dataset.containerName);
      return;
    }

    const actionButton = event.target.closest('.update-btn, .start-btn, .stop-btn, .restart-btn, .action-btn');
    if (!actionButton) {
      return;
    }

    let action = actionButton.dataset.action;
    let containerId = actionButton.dataset.id;
    let containerName = actionButton.dataset.name;
    const row = actionButton.closest('tr');

    if (actionButton.classList.contains('start-btn')) {
      action = 'start';
      containerId = row.querySelector('.show-chart-btn')?.dataset.containerId;
      containerName = row.querySelector('.col-name')?.textContent || containerId?.substring(0, 12) || '';
    } else if (actionButton.classList.contains('stop-btn')) {
      action = 'stop';
      containerId = row.querySelector('.show-chart-btn')?.dataset.containerId;
      containerName = row.querySelector('.col-name')?.textContent || containerId?.substring(0, 12) || '';
    } else if (actionButton.classList.contains('restart-btn')) {
      action = 'restart';
      containerId = row.querySelector('.show-chart-btn')?.dataset.containerId;
      containerName = row.querySelector('.col-name')?.textContent || containerId?.substring(0, 12) || '';
    } else if (actionButton.classList.contains('update-btn')) {
      action = 'update';
      containerId = actionButton.dataset.containerId;
      containerName = row.querySelector('.col-name')?.textContent || containerId?.substring(0, 12) || '';
    }

    handleAction(actionButton, action, containerId, containerName);
  }

  function getAllTableColumns() {
    const columns = [];
    document.querySelectorAll('#metricsTable thead th').forEach((header) => {
      const colClass = [...header.classList].find((className) => className.startsWith('col-'));
      if (!colClass) return;
      const key = colClass.replace('col-', '');
      if (key === 'name') return;
      columns.push({ key, label: header.textContent.trim() });
    });
    return columns;
  }

  function updateColumnCheckboxesForUser(allowedColumns) {
    if (!Array.isArray(allowedColumns)) {
      return;
    }

    ctx.elements.columnToggleInputs.forEach((checkbox) => {
      const columnName = checkbox.value;
      if (columnName === 'name') {
        checkbox.checked = true;
        checkbox.disabled = true;
        return;
      }

      const isAllowed = allowedColumns.includes(columnName);
      if (!isAllowed) {
        checkbox.checked = false;
        checkbox.disabled = true;
        checkbox.parentElement.classList.add('text-muted');
        ctx.elements.metricsTable.classList.add(`hide-col-${columnName}`);
        checkbox.title = 'You do not have permission to view this column';
      }
    });
    updateProjectRowColspans();
  }

  function populateTable(data) {
    if (!Array.isArray(data)) {
      ctx.elements.tableStatusDiv.textContent = 'Error: No valid data was received';
      return;
    }

    const visibleCount = renderTable(data);
    const now = new Date().toLocaleTimeString();
    ctx.elements.lastRefreshValue.textContent = now;
    ctx.elements.lastRefreshMeta.textContent = `${data.length} containers in latest snapshot`;
    ctx.elements.metricsSourceValue.textContent = ctx.elements.metricsSource.selectedOptions[0].textContent;
    if (visibleCount > 0) {
      ctx.elements.tableStatusDiv.style.color = '';
      ctx.elements.tableStatusDiv.textContent = `${visibleCount} visible container(s) - Updated at ${now}`;
    }
  }

  function init() {
    ctx.elements.columnToggleInputs.forEach((toggle) => {
      const savedState = localStorage.getItem(`colVisible-${toggle.value}`);
      const defaultChecked = !['ui', 'update'].includes(toggle.value);
      if (toggle.value === 'name') {
        toggle.checked = true;
        toggle.disabled = true;
      } else {
        toggle.checked = savedState ? savedState === 'true' : defaultChecked;
      }
      toggle.addEventListener('change', () => {
        localStorage.setItem(`colVisible-${toggle.value}`, toggle.checked);
        applyColumnVisibility();
      });
    });

    if (!ctx.state.tableClickBound) {
      ctx.elements.metricsTableBody.addEventListener('click', handleTableClick);
      document.querySelectorAll('.compare-action').forEach((actionLink) => {
        actionLink.addEventListener('click', (event) => {
          event.preventDefault();
          deps.openComparison(event.currentTarget.dataset.compareType);
        });
      });
      ctx.state.tableClickBound = true;
    }

    if (!ctx.state.exportBound) {
      ctx.elements.exportCsvBtn.addEventListener('click', () => {
        fetch('/api/export/csv', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ metrics: getSelectedMetrics() }),
          credentials: 'include',
        })
          .then((response) => response.blob())
          .then((blob) => {
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            anchor.href = url;
            anchor.download = 'metrics.csv';
            anchor.click();
            URL.revokeObjectURL(url);
          });
      });
      ctx.state.exportBound = true;
    }
  }

  return {
    init,
    applyColumnVisibility,
    calculateVisibleColumns,
    updateProjectRowColspans,
    renderTable,
    populateTable,
    updateColumnCheckboxesForUser,
    getAllTableColumns,
  };
}
