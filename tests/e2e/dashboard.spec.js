import { expect, test } from '@playwright/test';

test.beforeEach(async ({ request }) => {
  await request.post('http://127.0.0.1:5100/api/test/reset');
});

test('renders table, summaries and filters', async ({ page }) => {
  await page.goto('/');

  const tabOrder = await page.locator('.dashboard-view-tabs .nav-link').evaluateAll((nodes) => nodes.map((node) => node.id));
  expect(tabOrder).toEqual(['dashboardContainersTab', 'dashboardComposeTab']);

  const layoutMetrics = await page.evaluate(() => {
    const tableView = document.getElementById('tableView');
    return {
      docClientWidth: document.documentElement.clientWidth,
      docScrollWidth: document.documentElement.scrollWidth,
      tableClientWidth: tableView?.clientWidth ?? 0,
      tableScrollWidth: tableView?.scrollWidth ?? 0,
    };
  });

  expect(layoutMetrics.docScrollWidth).toBe(layoutMetrics.docClientWidth);
  expect(layoutMetrics.tableScrollWidth).toBeGreaterThan(layoutMetrics.tableClientWidth);

  for (const id of ['toggleColNetIO', 'toggleColBlockIO', 'toggleColImage', 'toggleColPorts', 'toggleColRestarts', 'toggleColUI', 'toggleColUpdate']) {
    await page.locator(`#${id}`).check();
  }

  const expandedLayoutMetrics = await page.evaluate(() => {
    const tableView = document.getElementById('tableView');
    if (tableView) {
      tableView.scrollLeft = 320;
    }
    return {
      docClientWidth: document.documentElement.clientWidth,
      docScrollWidth: document.documentElement.scrollWidth,
      tableClientWidth: tableView?.clientWidth ?? 0,
      tableScrollWidth: tableView?.scrollWidth ?? 0,
      tableScrollLeft: tableView?.scrollLeft ?? 0,
      windowScrollX: window.scrollX,
    };
  });

  expect(expandedLayoutMetrics.docScrollWidth).toBe(expandedLayoutMetrics.docClientWidth);
  expect(expandedLayoutMetrics.tableScrollWidth).toBeGreaterThan(expandedLayoutMetrics.tableClientWidth);
  expect(expandedLayoutMetrics.tableScrollLeft).toBeGreaterThan(0);
  expect(expandedLayoutMetrics.windowScrollX).toBe(0);

  await expect(page.locator('#summaryTotal')).toHaveText('3');
  await expect(page.locator('#summaryRunning')).toHaveText('2');
  await expect(page.locator('#summaryExited')).toHaveText('1');
  await expect(page.locator('#summaryUpdates')).toHaveText('1');

  await expect(page.locator('.hero-shell')).toBeVisible();
  await expect(page.locator('.hero-shell')).toContainText('One cockpit for containers, updates and alerts.');
  await expect(page.locator('#projectDashboardGrid')).toContainText('demo');
  await expect(page.locator('#projectDashboardGrid')).toContainText('jobs');
  await expect(page.locator('[data-project-summary="demo"]')).toContainText('2 containers');
  await expect(page.locator('[data-project-summary="demo"]')).toContainText('2 running');
  await expect(page.locator('[data-project-summary="jobs"]')).toContainText('Stopped');
  await expect(page.locator('#dashboardContainersPane')).toBeVisible();
  await expect(page.locator('#dashboardComposePane')).not.toBeVisible();

  await page.locator('#dashboardComposeTab').click();
  await expect(page.locator('#dashboardComposePane')).toBeVisible();
  await expect(page.locator('#dashboardContainersPane')).not.toBeVisible();

  await page.locator('#dashboardContainersTab').click();
  await expect(page.locator('#dashboardContainersPane')).toBeVisible();
  await expect(page.locator('#dashboardComposePane')).not.toBeVisible();

  await page.getByRole('button', { name: 'Exited' }).click();
  await expect(page.locator('#metricsTable tbody tr')).toHaveCount(1);
  await expect(page.locator('#metricsTable tbody tr')).toContainText('worker');

  await page.locator('#quickFilterBar').getByRole('button', { name: 'All', exact: true }).click();
  await page.locator('#filterName').fill('db');
  await expect(page.locator('#metricsTable tbody tr')).toHaveCount(1);
  await expect(page.locator('#metricsTable tbody tr')).toContainText('db');
  await expect(page.locator('#activeFiltersValue')).toContainText('1 active filters');

  const saveSettingsButton = page.locator('#saveSettingsBtn');
  await saveSettingsButton.click();
  await expect(saveSettingsButton).toHaveAttribute('data-feedback-state', 'success');
  await expect(saveSettingsButton).toContainText('Saved');
  await expect(page.locator('#statusMessageArea')).toContainText('Settings saved.');
  await expect(saveSettingsButton).not.toHaveAttribute('data-feedback-state', 'success');
  await expect(saveSettingsButton).toContainText('Save Settings');
});

test('keeps themed buttons readable and modals centered with internal scroll', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/');

  const activeTabBackgroundBeforeHover = await page.locator('#dashboardContainersTab').evaluate((el) => getComputedStyle(el).backgroundImage);
  await page.locator('#dashboardContainersTab').hover();
  const activeTabStylesOnHover = await page.locator('#dashboardContainersTab').evaluate((el) => {
    const styles = getComputedStyle(el);
    const tabs = document.getElementById('dashboardViewTabs');
    const tabStyles = tabs ? getComputedStyle(tabs) : null;
    return {
      color: styles.color,
      backgroundImage: styles.backgroundImage,
      alignSelf: tabStyles?.alignSelf ?? '',
      marginTop: tabStyles?.marginTop ?? '',
      marginBottom: tabStyles?.marginBottom ?? '',
    };
  });
  expect(activeTabBackgroundBeforeHover).not.toBe('none');
  expect(activeTabStylesOnHover.backgroundImage).not.toBe('none');
  expect(activeTabStylesOnHover.color).toBe('rgb(247, 250, 248)');
  expect(activeTabStylesOnHover.alignSelf).toBe('center');
  expect(activeTabStylesOnHover.marginTop).toBe(activeTabStylesOnHover.marginBottom);

  await page.locator('#themeToggle').click();
  await expect.poll(async () => page.locator('body').evaluate((node) => node.getAttribute('data-bs-theme'))).toBe('dark');

  const darkButtonStyles = await page.evaluate(() => {
    const ids = [
      'resetFiltersBtn',
      'toggleRefreshBtn',
      'notifToggle',
      'updateManagerToggle',
      'userInfoBtn',
      'settingsBtn',
      'themeToggle',
    ];
    return ids.map((id) => {
      const node = document.getElementById(id);
      const styles = node ? getComputedStyle(node) : null;
      return {
        id,
        color: styles?.color ?? '',
        backgroundColor: styles?.backgroundColor ?? '',
        borderColor: styles?.borderColor ?? '',
      };
    });
  });

  for (const button of darkButtonStyles) {
    expect(button.color).not.toBe('rgb(108, 117, 125)');
    expect(button.color).not.toBe('rgb(148, 176, 162)');
    expect(button.backgroundColor).not.toBe('rgba(0, 0, 0, 0)');
    expect(button.borderColor).not.toBe('rgba(0, 0, 0, 0)');
  }

  await page.locator('#notifToggle').click();
  await page.locator('#notifSettingsBtn').click();
  await expect(page.locator('#notifSettingsModal')).toHaveClass(/show/);
  const modalMetrics = await page.locator('#notifSettingsModal .modal-dialog').evaluate((dialog) => {
    const body = dialog.querySelector('.modal-body');
    const footer = dialog.querySelector('.modal-footer');
    const rect = dialog.getBoundingClientRect();
    const bodyStyles = body ? getComputedStyle(body) : null;
    if (body) {
      body.scrollTop = body.scrollHeight;
    }
    return {
      dialogCenterX: rect.left + (rect.width / 2),
      dialogCenterY: rect.top + (rect.height / 2),
      viewportCenterX: window.innerWidth / 2,
      viewportCenterY: window.innerHeight / 2,
      bodyOverflowY: bodyStyles?.overflowY ?? '',
      bodyScrollable: body ? body.scrollHeight > body.clientHeight : false,
      footerBottom: footer ? footer.getBoundingClientRect().bottom : 0,
      windowScrollY: window.scrollY,
    };
  });

  expect(Math.abs(modalMetrics.dialogCenterX - modalMetrics.viewportCenterX)).toBeLessThan(32);
  expect(Math.abs(modalMetrics.dialogCenterY - modalMetrics.viewportCenterY)).toBeLessThan(32);
  expect(['auto', 'scroll']).toContain(modalMetrics.bodyOverflowY);
  expect(modalMetrics.bodyScrollable).toBeTruthy();
  expect(modalMetrics.footerBottom).toBeLessThanOrEqual(720);
  expect(modalMetrics.windowScrollY).toBe(0);
});

test('uses four-tab mobile navigation and keeps mobile modals inside the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 780 });
  await page.goto('/');

  await expect(page.locator('#mobileSectionNavShell')).toBeVisible();
  await expect(page.locator('#mobileSectionNav .mobile-section-tab')).toHaveCount(4);

  const mobileTabState = await page.locator('#mobileSectionNav .mobile-section-tab').evaluateAll((nodes) => nodes.map((node) => {
    const label = node.querySelector('.mobile-section-label');
    return {
      id: node.id,
      selected: node.getAttribute('aria-selected'),
      labelOpacity: label ? getComputedStyle(label).opacity : '',
    };
  }));

  expect(mobileTabState.map((tab) => tab.id)).toEqual([
    'mobileInfoTab',
    'mobileWorkspaceTab',
    'mobileContainersTab',
    'mobileStacksTab',
  ]);
  expect(mobileTabState.find((tab) => tab.id === 'mobileContainersTab')?.selected).toBe('true');
  expect(Number(mobileTabState.find((tab) => tab.id === 'mobileContainersTab')?.labelOpacity || 0)).toBeGreaterThan(0.9);
  expect(Number(mobileTabState.find((tab) => tab.id === 'mobileInfoTab')?.labelOpacity || 1)).toBeLessThan(0.2);

  await expect(page.locator('#dashboardContainersPane')).toBeVisible();
  await expect(page.locator('#overviewShell')).not.toBeVisible();
  await expect(page.locator('#workspaceShell')).not.toBeVisible();

  await page.locator('#mobileInfoTab').click();
  await expect(page.locator('#overviewShell')).toBeVisible();
  await expect(page.locator('#workspaceShell')).not.toBeVisible();
  await expect(page.locator('#dashboardContainersPane')).not.toBeVisible();

  await page.locator('#mobileWorkspaceTab').click();
  await expect(page.locator('#workspaceShell')).toBeVisible();
  await expect(page.locator('#overviewShell')).not.toBeVisible();

  await page.locator('#mobileStacksTab').click();
  await expect(page.locator('#dashboardComposePane')).toBeVisible();
  await expect(page.locator('#projectDashboardGrid')).toContainText('demo');
  await expect(page.locator('#dashboardContainersPane')).not.toBeVisible();

  await page.locator('#mobileContainersTab').click();
  await expect(page.locator('#dashboardContainersPane')).toBeVisible();
  await expect(page.locator('#dashboardComposePane')).not.toBeVisible();

  await page.locator('#mobileMenuToggle').click();
  await page.locator('#sidebarUpdateManagerToggle').click();
  await expect(page.locator('#updateManagerModal')).toHaveClass(/show/);

  const mobileUpdateTabState = await page.locator('#updateManagerTabs .nav-link').evaluateAll((nodes) => nodes.map((node) => {
    const label = node.querySelector('.update-manager-tab-label');
    return {
      id: node.id,
      selected: node.getAttribute('aria-selected'),
      labelOpacity: label ? Number(getComputedStyle(label).opacity) : 0,
    };
  }));

  expect(mobileUpdateTabState.find((tab) => tab.id === 'updateManagerProjectsTab')?.selected).toBe('true');
  expect(mobileUpdateTabState.find((tab) => tab.id === 'updateManagerProjectsTab')?.labelOpacity ?? 0).toBeGreaterThan(0.9);
  expect(mobileUpdateTabState.find((tab) => tab.id === 'updateManagerContainersTab')?.labelOpacity ?? 1).toBeLessThan(0.2);

  await page.locator('#updateManagerAutoUpdatesTab').click();
  await expect(page.locator('#updateManagerAutoUpdatesTab')).toHaveAttribute('aria-selected', 'true');
  await expect.poll(async () => page.locator('#updateManagerAutoUpdatesTab .update-manager-tab-label').evaluate((node) => Number(getComputedStyle(node).opacity))).toBeGreaterThan(0.9);
  await expect.poll(async () => page.locator('#updateManagerProjectsTab .update-manager-tab-label').evaluate((node) => Number(getComputedStyle(node).opacity))).toBeLessThan(0.2);

  const mobileModalMetrics = await page.locator('#updateManagerModal .modal-dialog').evaluate((dialog) => {
    const body = dialog.querySelector('.modal-body');
    const footer = dialog.querySelector('.modal-footer');
    const closeButton = footer?.querySelector('button');

    if (body) {
      body.scrollTop = body.scrollHeight;
    }

    return {
      dialogBottom: dialog.getBoundingClientRect().bottom,
      footerBottom: footer ? footer.getBoundingClientRect().bottom : 0,
      closeButtonBottom: closeButton ? closeButton.getBoundingClientRect().bottom : 0,
      viewportHeight: window.visualViewport?.height ?? window.innerHeight,
      bodyOverflowY: body ? getComputedStyle(body).overflowY : '',
      bodyScrollable: body ? body.scrollHeight > body.clientHeight : false,
    };
  });

  expect(mobileModalMetrics.dialogBottom).toBeLessThanOrEqual(mobileModalMetrics.viewportHeight + 1);
  expect(mobileModalMetrics.footerBottom).toBeLessThanOrEqual(mobileModalMetrics.viewportHeight + 1);
  expect(mobileModalMetrics.closeButtonBottom).toBeLessThanOrEqual(mobileModalMetrics.viewportHeight + 1);
  expect(['auto', 'scroll']).toContain(mobileModalMetrics.bodyOverflowY);
  expect(mobileModalMetrics.bodyScrollable).toBeTruthy();
});

test('supports container actions and chart loading', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/');

  const webRow = page.locator('#metricsTable tbody tr').filter({ hasText: 'web' });
  await webRow.locator('.stop-btn').click();
  await expect(page.locator('#statusMessageArea')).toContainText('stopped');
  await expect(webRow.locator('.col-status')).toContainText('exited');

  await webRow.locator('.start-btn').click();
  await expect(page.locator('#statusMessageArea')).toContainText('started');
  await expect(webRow.locator('.col-status')).toContainText('running');

  const dbRow = page.locator('#metricsTable tbody tr').filter({ hasText: 'db' });
  await dbRow.locator('.show-chart-btn').click();
  await expect(page.locator('#historyChartModal')).toHaveClass(/show/);
  await expect(page.locator('#chartTitle')).toContainText('db');
  await expect(page.locator('#chartStatus')).toHaveText('');

  const historyModalMetrics = await page.locator('#historyChartModal .modal-dialog').evaluate((dialog) => {
    const rect = dialog.getBoundingClientRect();
    const footer = dialog.querySelector('.modal-footer');
    const canvas = dialog.querySelector('#usageChart');
    return {
      dialogCenterX: rect.left + (rect.width / 2),
      dialogCenterY: rect.top + (rect.height / 2),
      viewportCenterX: window.innerWidth / 2,
      viewportCenterY: window.innerHeight / 2,
      footerBottom: footer ? footer.getBoundingClientRect().bottom : 0,
      canvasWidth: canvas?.clientWidth ?? 0,
      canvasHeight: canvas?.clientHeight ?? 0,
    };
  });
  expect(Math.abs(historyModalMetrics.dialogCenterX - historyModalMetrics.viewportCenterX)).toBeLessThan(32);
  expect(Math.abs(historyModalMetrics.dialogCenterY - historyModalMetrics.viewportCenterY)).toBeLessThan(32);
  expect(historyModalMetrics.footerBottom).toBeLessThanOrEqual(720);
  expect(historyModalMetrics.canvasWidth).toBeGreaterThan(0);
  expect(historyModalMetrics.canvasHeight).toBeGreaterThan(0);

  await page.locator('#historyChartModal .modal-footer .btn').click();
  await expect(page.locator('#historyChartModal')).not.toHaveClass(/show/);

  await page.locator('#compareDropdown').click();
  await page.locator('.compare-action[data-compare-type="cpu"]').click();
  await expect(page.locator('#comparisonChartModal')).toHaveClass(/show/);
  await expect(page.locator('#comparisonChartTitle')).toContainText('CPU usage');
  await expect(page.locator('#comparisonChartStatus')).toHaveText('');

  await page.locator('#comparisonChartTopN').fill('2');
  await page.locator('#comparisonChartRefreshBtn').click();
  await expect(page.locator('#comparisonChartStatus')).toHaveText('');

  await page.locator('#comparisonRamTab').click();
  await expect(page.locator('#comparisonChartTitle')).toContainText('RAM usage');
  await expect(page.locator('#comparisonChartStatus')).toHaveText('');

  await page.locator('#comparisonUptimeTab').click();
  await expect(page.locator('#comparisonChartTitle')).toContainText('Uptime');
  await expect(page.locator('#comparisonChartStatus')).toHaveText('');

  const comparisonModalMetrics = await page.locator('#comparisonChartModal .modal-dialog').evaluate((dialog) => {
    const rect = dialog.getBoundingClientRect();
    const footer = dialog.querySelector('.modal-footer');
    const canvas = dialog.querySelector('#comparisonChartCanvas');
    return {
      dialogCenterX: rect.left + (rect.width / 2),
      dialogCenterY: rect.top + (rect.height / 2),
      viewportCenterX: window.innerWidth / 2,
      viewportCenterY: window.innerHeight / 2,
      footerBottom: footer ? footer.getBoundingClientRect().bottom : 0,
      canvasWidth: canvas?.clientWidth ?? 0,
      canvasHeight: canvas?.clientHeight ?? 0,
    };
  });
  expect(Math.abs(comparisonModalMetrics.dialogCenterX - comparisonModalMetrics.viewportCenterX)).toBeLessThan(32);
  expect(Math.abs(comparisonModalMetrics.dialogCenterY - comparisonModalMetrics.viewportCenterY)).toBeLessThan(32);
  expect(comparisonModalMetrics.footerBottom).toBeLessThanOrEqual(720);
  expect(comparisonModalMetrics.canvasWidth).toBeGreaterThan(0);
  expect(comparisonModalMetrics.canvasHeight).toBeGreaterThan(0);
});

test('updates the table through realtime SSE without polling', async ({ page, request }) => {
  await page.goto('/');
  await expect(page.locator('#refreshStatusChip')).toContainText('5s');
  await page.selectOption('#refreshInterval', '1000');
  await expect(page.locator('#refreshStatusChip')).toContainText('1s');

  const workerRow = page.locator('#metricsTable tbody tr').filter({ hasText: 'worker' });
  await expect(workerRow.locator('.col-status')).toContainText('exited');

  await request.post('http://127.0.0.1:5100/api/test/containers/worker12345678/mutate', {
    data: { status: 'running', cpu: 9.5, mem: 12.0, uptime: '0d 0h 0m 8s' },
  });

  await expect(workerRow.locator('.col-status')).toContainText('running');
});

test('keeps version text consistent across footer, system status, and SSE', async ({ page, request }) => {
  await page.goto('/');
  await expect(page.locator('#appVersionText')).toHaveText('test-version');

  const systemStatusResponse = await request.get('http://127.0.0.1:5100/api/system-status');
  const systemStatus = await systemStatusResponse.json();
  expect(systemStatus.app.version).toBe('test-version');

  const streamVersion = await page.evaluate(() => new Promise((resolve, reject) => {
    const source = new EventSource('/api/stream');
    const timeoutId = window.setTimeout(() => {
      source.close();
      reject(new Error('Timed out waiting for the SSE connected event.'));
    }, 5000);

    source.addEventListener('connected', (event) => {
      window.clearTimeout(timeoutId);
      source.close();
      resolve(JSON.parse(event.data).version);
    }, { once: true });

    source.addEventListener('error', () => {
      window.clearTimeout(timeoutId);
      source.close();
      reject(new Error('Unable to connect to the SSE stream.'));
    }, { once: true });
  }));

  expect(streamVersion).toBe(systemStatus.app.version);
});

test('handles password change and user creation from settings modal', async ({ page }) => {
  await page.goto('/');

  await page.locator('#settingsBtn').click();
  await expect(page.locator('#settingsModal')).toHaveClass(/show/);

  await page.locator('#currentPassword').fill('adminpass');
  await page.locator('#newPassword').fill('changed-pass');
  await page.locator('#confirmPassword').fill('changed-pass');
  await page.locator('#savePasswordBtn').click();
  await expect(page.locator('#statusMessageArea')).toContainText('Password changed successfully.');
  await expect(page.locator('#settingsModal')).not.toHaveClass(/show/);
  await expect.poll(async () => page.locator('body').evaluate((node) => node.classList.contains('modal-open'))).toBe(false);

  await page.locator('#settingsBtn').click();
  await page.locator('#tab-manageuser').click();
  await expect(page.locator('#manageUserTabPane')).toHaveClass(/show/);

  await page.locator('#newUsername').fill('analyst');
  await page.locator('#newUserPassword').fill('analyst-pass');
  await page.locator('#confirmUserPassword').fill('analyst-pass');
  await page.locator('#createUserForm button[type="submit"]').click();

  await expect(page.locator('#usersList')).toContainText('analyst');
});

test('opens pending notifications panel and edits advanced notification settings in modal', async ({ page, request }) => {
  await request.post('http://127.0.0.1:5100/api/notification-test', { data: {} });

  await page.goto('/');

  await page.locator('#notifToggle').click();
  await expect(page.locator('#notifPanel')).toBeVisible();
  await expect(page.locator('#notifPanel')).toContainText('Pending notifications');
  await expect(page.locator('#notifList')).toContainText('Test notification delivered');

  await page.locator('#clearNotifsBtn').hover();
  await expect(page.locator('.tooltip.show')).toContainText('Clear Notifications');

  await page.locator('#notifSettingsBtn').click();
  await expect(page.locator('#notifSettingsModal')).toHaveClass(/show/);
  await expect(page.locator('#notifEnableSecurity')).not.toBeChecked();
  await expect(page.locator('#notifSecurityPrivilegedEnabled')).toBeDisabled();
  await expect(page.locator('#notifSecurityPublicPortsEnabled')).toBeDisabled();

  await page.selectOption('#notifProjectRuleMode', 'include');
  await page.locator('#notifProjectRules').fill('demo\njobs-*');
  await page.selectOption('#notifContainerRuleMode', 'exclude');
  await page.locator('#notifContainerRules').fill('db');
  await page.locator('#notifWindowMinutes').fill('1');
  await page.locator('#notifWindowSeconds').fill('5');
  await page.locator('#notifCooldownMinutes').fill('2');
  await page.locator('#notifCooldownSeconds').fill('45');
  await page.locator('#notifSilenceEnabled').check();
  await page.locator('#notifSilenceStart').fill('23:00');
  await page.locator('#notifSilenceEnd').fill('06:30');
  await page.locator('#notifDedupeWindowMinutes').fill('4');
  await page.locator('#notifDedupeWindowSeconds').fill('0');
  await page.locator('#notifEnableSecurity').check();
  await page.locator('#notifSecurityPublicPortsEnabled').uncheck();
  await page.locator('#notifSecurityLatestEnabled').uncheck();
  const saveNotifSettingsButton = page.locator('#saveNotifSettingsBtn');
  await saveNotifSettingsButton.click();

  await expect(saveNotifSettingsButton).toHaveAttribute('data-feedback-state', 'success');
  await expect(saveNotifSettingsButton).toContainText('Saved');
  await expect(page.locator('#statusMessageArea')).toContainText('Notification settings saved.');
  await expect(saveNotifSettingsButton).not.toHaveAttribute('data-feedback-state', 'success');
  await expect(saveNotifSettingsButton).toContainText('Save settings');

  const settingsResponse = await request.get('http://127.0.0.1:5100/api/notification-settings');
  const settingsPayload = await settingsResponse.json();
  expect(settingsPayload.project_rule_mode).toBe('include');
  expect(settingsPayload.project_rules).toBe('demo\njobs-*');
  expect(settingsPayload.container_rule_mode).toBe('exclude');
  expect(settingsPayload.container_rules).toBe('db');
  expect(settingsPayload.window_seconds).toBe(65);
  expect(settingsPayload.cooldown_seconds).toBe(165);
  expect(settingsPayload.silence_enabled).toBe(true);
  expect(settingsPayload.silence_start).toBe('23:00');
  expect(settingsPayload.silence_end).toBe('06:30');
  expect(settingsPayload.dedupe_window_seconds).toBe(240);
  expect(settingsPayload.security_enabled).toBe(true);
  expect(settingsPayload.security_public_ports_enabled).toBe(false);
  expect(settingsPayload.security_latest_enabled).toBe(false);

  await page.locator('#notifSettingsModal .btn-close').click();
  if (!(await page.locator('#notifPanel').isVisible())) {
    await page.locator('#notifToggle').click();
  }
  await page.locator('#notifSettingsBtn').click();
  await expect(page.locator('#notifWindowMinutes')).toHaveValue('1');
  await expect(page.locator('#notifWindowSeconds')).toHaveValue('5');
  await expect(page.locator('#notifCooldownMinutes')).toHaveValue('2');
  await expect(page.locator('#notifCooldownSeconds')).toHaveValue('45');
  await expect(page.locator('#notifDedupeWindowMinutes')).toHaveValue('4');
  await expect(page.locator('#notifDedupeWindowSeconds')).toHaveValue('0');

  const testNotifButton = page.locator('#testNotifBtn');
  await testNotifButton.click();
  await expect(testNotifButton).toHaveAttribute('data-feedback-state', 'success');
  await expect(testNotifButton).toContainText('Sent');
  await expect(page.locator('#statusMessageArea')).toContainText('Test notification sent through');
  await expect(testNotifButton).not.toHaveAttribute('data-feedback-state', 'success');

  await page.locator('#notifSettingsModal .btn-close').click();
  await page.locator('#notifToggle').click();
  await page.locator('#clearNotifsBtn').click();
  await expect(page.locator('#clearNotificationsModal')).toHaveClass(/show/);
  await expect(page.locator('#clearNotificationsModal')).toContainText('Clear notifications');
  await page.locator('#confirmClearNotifsBtn').click();
  await expect(page.locator('#clearNotificationsModal')).not.toHaveClass(/show/);
  await page.locator('#notifToggle').click();
  await expect(page.locator('#notifList')).toContainText('No notifications');
});

test('streams logs in a modal with configurable limits, download, and auto-scroll controls', async ({ page, request }) => {
  for (let index = 1; index <= 110; index += 1) {
    await request.post('http://127.0.0.1:5100/api/test/logs/db123456789012/append', {
      data: { line: `2026-01-01T10:01:${String(index).padStart(2, '0')}.000000000Z db | seeded log line ${index}` },
    });
  }

  await page.goto('/');

  const dbRow = page.locator('#metricsTable tbody tr').filter({ hasText: 'db' });
  await dbRow.locator('.show-logs-btn').click();
  await expect(page.locator('#logsModal')).toHaveClass(/show/);
  await expect(page.locator('#logsStatus')).toContainText('Live stream connected.');
  await expect(page.locator('#logsMeta')).toContainText('latest 100 lines');
  await expect(page.locator('#logsOutput')).toContainText('seeded log line 110');
  const defaultLogLines = await page.locator('#logsOutput').evaluate((node) => node.textContent.split('\n'));
  expect(defaultLogLines.some((line) => line.endsWith('seeded log line 1'))).toBe(false);
  await expect(page.locator('#logsAutoScrollToggle')).toBeChecked();

  const downloadPromise = page.waitForEvent('download');
  await page.locator('#downloadLogsBtn').click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^db-.*-logs\.txt$/);

  await page.selectOption('#logsLineLimitSelect', 'custom');
  await page.locator('#logsCustomLimitInput').fill('110');
  await page.locator('#logsApplyLimitBtn').click();
  await expect(page.locator('#logsMeta')).toContainText('latest 110 lines');
  const expandedLogLines = await page.locator('#logsOutput').evaluate((node) => node.textContent.split('\n'));
  expect(expandedLogLines.some((line) => line.endsWith('seeded log line 1'))).toBe(true);

  await page.locator('#logsAutoScrollToggle').uncheck();
  await page.locator('#logsOutput').evaluate((node) => {
    node.scrollTop = 0;
  });
  await expect.poll(async () => page.locator('#logsOutput').evaluate((node) => node.scrollTop)).toBe(0);
  await request.post('http://127.0.0.1:5100/api/test/logs/db123456789012/append', {
    data: { line: '2026-01-01T10:05:00.000000000Z db | live line while auto-scroll is paused' },
  });
  await expect(page.locator('#logsOutput')).toContainText('live line while auto-scroll is paused');

  const pausedScrollMetrics = await page.locator('#logsOutput').evaluate((node) => ({
    scrollTop: node.scrollTop,
    maxScrollTop: node.scrollHeight - node.clientHeight,
  }));
  expect(pausedScrollMetrics.maxScrollTop).toBeGreaterThan(0);
  expect(pausedScrollMetrics.scrollTop).toBeLessThan(24);

  await page.locator('#logsAutoScrollToggle').check();
  await request.post('http://127.0.0.1:5100/api/test/logs/db123456789012/append', {
    data: { line: '2026-01-01T10:05:10.000000000Z db | live line after auto-scroll resumed' },
  });
  await expect(page.locator('#logsOutput')).toContainText('live line after auto-scroll resumed');
  await expect.poll(async () => page.locator('#logsOutput').evaluate((node) => {
    const maxScrollTop = node.scrollHeight - node.clientHeight;
    return Math.abs(maxScrollTop - node.scrollTop) <= 2;
  })).toBe(true);
});

test('shows success and failure update notifications and auto-cleans stale history entries', async ({ page, request }) => {
  await request.post('http://127.0.0.1:5100/api/test/update-history/add', {
    data: {
      age_days: 16,
      target_id: 'stale-history-entry',
      target_name: 'stale history entry',
    },
  });
  await request.post('http://127.0.0.1:5100/api/test/update-history/add', {
    data: {
      age_days: 1,
      target_id: 'fresh-history-entry',
      target_name: 'fresh history entry',
    },
  });
  await request.post('http://127.0.0.1:5100/api/test/update-manager/fail-target', {
    data: { target_id: 'jobs', enabled: true },
  });

  await page.goto('/');
  await page.locator('#updateManagerToggle').click();
  await expect(page.locator('#updateManagerModal')).toHaveClass(/show/);

  const demoEntry = page.locator('#updateManagerProjectList .update-entry').filter({ hasText: 'demo' });
  await demoEntry.locator('.update-target-btn--quick').click();
  await expect(page.locator('#appDialogModal')).toHaveClass(/show/);
  await page.locator('#appDialogConfirm').click();
  await expect(page.locator('#updateManagerActionState')).toContainText('Success');
  await expect(page.locator('#updateManagerActionModal')).not.toHaveClass(/show/);

  const jobsEntry = page.locator('#updateManagerProjectList .update-entry').filter({ hasText: 'jobs' });
  await jobsEntry.locator('.update-target-btn--quick').click();
  await expect(page.locator('#appDialogModal')).toHaveClass(/show/);
  await page.locator('#appDialogConfirm').click();
  await expect(page.locator('#updateManagerActionState')).toContainText('Failed');
  await expect(page.locator('#updateManagerActionMessage')).toContainText('Update failed');
  await expect(page.locator('#updateManagerActionCloseBtn')).toBeEnabled();
  await page.locator('#updateManagerActionCloseBtn').click();
  await expect(page.locator('#updateManagerActionModal')).not.toHaveClass(/show/);
  await page.locator('#updateManagerModal .btn-close').click();
  await expect(page.locator('#updateManagerModal')).not.toHaveClass(/show/);

  await page.locator('#notifToggle').click();
  await expect(page.locator('#notifList')).toContainText('Project demo updated with a safe compose workflow.');
  await expect(page.locator('#notifList')).toContainText('Update failed for jobs.');

  await page.locator('#updateManagerToggle').click();
  await page.locator('#updateManagerHistoryTab').click();
  await expect(page.locator('#updateHistoryRetentionNotice')).toContainText('15 days');
  await expect(page.locator('#updateManagerHistoryList')).toContainText('fresh history entry');
  await expect(page.locator('#updateManagerHistoryList')).not.toContainText('stale history entry');
});

test('keeps chart and log modals inside the mobile viewport', async ({ page, request }) => {
  for (let index = 1; index <= 90; index += 1) {
    await request.post('http://127.0.0.1:5100/api/test/logs/db123456789012/append', {
      data: { line: `2026-01-01T10:02:${String(index).padStart(2, '0')}.000000000Z db | mobile line ${index}` },
    });
  }

  await page.setViewportSize({ width: 390, height: 780 });
  await page.goto('/');

  const dbRow = page.locator('#metricsTable tbody tr').filter({ hasText: 'db' });
  await dbRow.locator('.show-chart-btn').click();
  await expect(page.locator('#historyChartModal')).toHaveClass(/show/);

  const chartModalMetrics = await page.locator('#historyChartModal .modal-dialog').evaluate((dialog) => {
    const footer = dialog.querySelector('.modal-footer');
    return {
      dialogBottom: dialog.getBoundingClientRect().bottom,
      footerBottom: footer ? footer.getBoundingClientRect().bottom : 0,
      viewportHeight: window.visualViewport?.height ?? window.innerHeight,
    };
  });
  expect(chartModalMetrics.dialogBottom).toBeLessThanOrEqual(chartModalMetrics.viewportHeight + 1);
  expect(chartModalMetrics.footerBottom).toBeLessThanOrEqual(chartModalMetrics.viewportHeight + 1);

  await page.locator('#historyChartModal .modal-footer .btn').click();
  await expect(page.locator('#historyChartModal')).not.toHaveClass(/show/);

  await dbRow.locator('.show-logs-btn').click();
  await expect(page.locator('#logsModal')).toHaveClass(/show/);
  await expect(page.locator('#logsStatus')).toContainText('Live stream connected.');

  const logsModalMetrics = await page.locator('#logsModal .modal-dialog').evaluate((dialog) => {
    const footer = dialog.querySelector('.modal-footer');
    const output = dialog.querySelector('#logsOutput');
    return {
      dialogBottom: dialog.getBoundingClientRect().bottom,
      footerBottom: footer ? footer.getBoundingClientRect().bottom : 0,
      viewportHeight: window.visualViewport?.height ?? window.innerHeight,
      outputScrollable: output ? output.scrollHeight > output.clientHeight : false,
      outputOverflowY: output ? getComputedStyle(output).overflowY : '',
    };
  });
  expect(logsModalMetrics.dialogBottom).toBeLessThanOrEqual(logsModalMetrics.viewportHeight + 1);
  expect(logsModalMetrics.footerBottom).toBeLessThanOrEqual(logsModalMetrics.viewportHeight + 1);
  expect(logsModalMetrics.outputScrollable).toBeTruthy();
  expect(['auto', 'scroll']).toContain(logsModalMetrics.outputOverflowY);
});

test('opens the update manager, runs update and rollback, and shows load errors', async ({ page, request }) => {
  await page.goto('/');

  await page.locator('#updateManagerToggle').click();
  await expect(page.locator('#updateManagerModal')).toHaveClass(/show/);
  await expect(page.locator('#updateManagerModal')).toContainText('Experimental');
  await expect(page.locator('#updateManagerProjectList')).toContainText('demo');
  await expect(page.locator('#updateManagerProjectList')).toContainText('jobs');
  await expect(page.locator('#updateManagerProjectList')).toContainText('broken');
  await expect(page.locator('#updateManagerContainerList')).toContainText('cache');
  await page.locator('#updateManagerHideBlocked').check();
  await expect(page.locator('#updateManagerProjectList')).not.toContainText('broken');
  await expect(page.locator('#updateManagerProjectList')).toContainText('jobs');
  await page.locator('#updateManagerHideBlocked').uncheck();

  const blockedProjectEntry = page.locator('#updateManagerProjectList .update-entry').filter({ hasText: 'broken' });
  await blockedProjectEntry.locator('[data-update-entry-toggle]').click();
  await expect(blockedProjectEntry).toContainText('Compose metadata is incomplete or inconsistent across services.');
  await expect(blockedProjectEntry).toContainText('Project updates are disabled until the stack is relinked to a single Compose project on disk.');
  await expect(blockedProjectEntry.locator('.update-target-btn')).toHaveCount(0);

  const projectEntry = page.locator('#updateManagerProjectList .update-entry').filter({ hasText: 'jobs' });
  const projectToggle = projectEntry.locator('[data-update-entry-toggle]');
  const projectPanel = projectEntry.locator('.update-entry-panel');
  const quickUpdateButton = projectEntry.locator('.update-target-btn--quick');
  await expect(projectToggle).toContainText('jobs');
  await expect(projectToggle).toContainText('New version');
  await expect(quickUpdateButton).toContainText('Quick Update');
  await expect(projectPanel).toBeHidden();

  await projectToggle.click();
  await expect(projectToggle).toHaveAttribute('aria-expanded', 'true');
  await expect(projectPanel).toBeVisible();
  await expect(projectPanel).toContainText('Portainer');
  await expect(projectPanel).toContainText('External safe recreate');
  await expect(projectPanel).toContainText('Current version');
  await expect(projectPanel).toContainText('Ready');
  await expect(projectPanel).toContainText('/data/compose/42/docker-compose.yml');
  await expect(projectPanel).toContainText('Compose files are unavailable, so statainer will update the running services directly.');

  const updateButton = projectPanel.locator('.update-target-btn').first();
  await updateButton.click();
  await expect(page.locator('#appDialogModal')).toHaveClass(/show/);
  await page.locator('#appDialogConfirm').click();
  await expect(page.locator('#appDialogModal')).toBeHidden();
  await expect(page.locator('#updateManagerActionModal')).toHaveClass(/show/);
  await expect(page.locator('#updateManagerActionState')).toContainText('Success');
  await expect(page.locator('#updateManagerActionMessage')).toContainText('Update completed');
  await expect(page.locator('#updateManagerActionDetail')).toContainText('Project jobs updated safely by recreating the running services without compose files.');
  await expect(page.locator('#updateManagerStatus')).toContainText('Project jobs updated safely by recreating the running services without compose files.');
  const actionDetailFits = await page.locator('#updateManagerActionDetail').evaluate((el) => el.scrollWidth <= el.clientWidth + 1);
  expect(actionDetailFits).toBeTruthy();
  await expect(page.locator('#updateManagerActionModal')).not.toHaveClass(/show/);

  await page.locator('#updateManagerHistoryTab').click();
  await expect(page.locator('#updateManagerHistoryPane')).toBeVisible();
  const historyEntry = page.locator('#updateManagerHistoryList .update-entry').first();
  const historyToggle = historyEntry.locator('[data-update-entry-toggle]');
  const historyPanel = historyEntry.locator('.update-entry-panel');
  await expect(historyToggle).toContainText('jobs');
  await expect(historyToggle).toContainText('New version');
  await expect(historyPanel).toBeHidden();

  await historyToggle.click();
  await expect(historyToggle).toHaveAttribute('aria-expanded', 'true');
  await expect(historyPanel).toBeVisible();
  await expect(historyPanel).toContainText('Previous version');
  await expect(historyPanel).toContainText('Rollback');

  const rollbackButton = historyPanel.locator('.update-rollback-btn').first();
  await rollbackButton.click();
  await expect(page.locator('#appDialogModal')).toHaveClass(/show/);
  await page.locator('#appDialogConfirm').click();
  await expect(page.locator('#appDialogModal')).toBeHidden();
  await expect(page.locator('#updateManagerActionModal')).toHaveClass(/show/);
  await expect(page.locator('#updateManagerActionState')).toContainText('Success');
  await expect(page.locator('#updateManagerActionMessage')).toContainText('Rollback completed');
  await expect(page.locator('#updateManagerStatus')).toContainText('Rollback completed.');
  await expect(page.locator('#updateManagerActionModal')).not.toHaveClass(/show/);

  await request.post('http://127.0.0.1:5100/api/test/update-manager/error-mode', {
    data: { enabled: true },
  });
  await page.locator('#refreshUpdateManagerBtn').click();
  await expect(page.locator('#updateManagerStatus')).toContainText('Unable to load update manager.');
});

test('updates all stacks and standalone containers sequentially from the update manager', async ({ page }) => {
  await page.goto('/');

  await page.locator('#updateManagerToggle').click();
  await expect(page.locator('#updateManagerModal')).toHaveClass(/show/);
  await expect(page.locator('#updateAllProjectsBtn')).toContainText('Update all stacks (2)');
  await expect(page.locator('#updateAllContainersBtn')).toContainText('Update all containers (1)');

  await page.locator('#updateAllProjectsBtn').click();
  await expect(page.locator('#appDialogModal')).toHaveClass(/show/);
  await page.locator('#appDialogConfirm').click();
  await expect(page.locator('#updateManagerActionModal')).toHaveClass(/show/);
  await expect(page.locator('#updateManagerActionState')).toContainText('Success');
  await expect(page.locator('#updateManagerActionMessage')).toContainText('Updated 2 stacks successfully.');
  await expect(page.locator('#updateManagerActionDetail')).toContainText('Sequential mode completed 2 stacks.');
  await expect(page.locator('#updateManagerActionDetail')).toContainText('Updated: demo, jobs');
  await expect(page.locator('#updateManagerActionModal')).not.toHaveClass(/show/);
  await expect(page.locator('#updateManagerProjectList')).not.toContainText('demo');
  await expect(page.locator('#updateManagerProjectList')).not.toContainText('jobs');
  await expect(page.locator('#updateManagerProjectList')).toContainText('broken');
  await expect(page.locator('#updateAllProjectsBtn')).toBeDisabled();
  await expect(page.locator('#updateAllProjectsBtn')).toContainText('Update all stacks');

  await page.locator('#updateManagerContainersTab').click();
  await expect(page.locator('#updateManagerContainerList')).toContainText('cache');
  await page.locator('#updateAllContainersBtn').click();
  await expect(page.locator('#appDialogModal')).toHaveClass(/show/);
  await page.locator('#appDialogConfirm').click();
  await expect(page.locator('#updateManagerActionModal')).toHaveClass(/show/);
  await expect(page.locator('#updateManagerActionState')).toContainText('Success');
  await expect(page.locator('#updateManagerActionDetail')).toContainText('Sequential mode completed 1 container.');
  await expect(page.locator('#updateManagerActionDetail')).toContainText('Updated: cache');
  await expect(page.locator('#statusMessageArea')).toContainText('Updated 1 container successfully.');
  await expect(page.locator('#updateManagerActionModal')).not.toHaveClass(/show/);
  await expect(page.locator('#updateManagerContainerList')).toContainText('No standalone containers');
  await expect(page.locator('#updateAllContainersBtn')).toBeDisabled();
  await expect(page.locator('#updateAllContainersBtn')).toContainText('Update all containers');
});

test('updates selected stacks and containers with shift-range selection in the update manager', async ({ page }) => {
  await page.goto('/');

  await page.locator('#updateManagerToggle').click();
  await expect(page.locator('#updateManagerModal')).toHaveClass(/show/);
  await expect(page.locator('#updateSelectedProjectsBtn')).toBeDisabled();
  await expect(page.locator('#updateSelectedContainersBtn')).toBeDisabled();

  const projectCheckboxes = page.locator('#updateManagerProjectList .update-entry-select[data-update-select-type="project"]');
  await expect(projectCheckboxes).toHaveCount(2);
  await projectCheckboxes.nth(0).click();
  await expect(page.locator('#updateSelectedProjectsBtn')).toContainText('Update selected stacks (1)');
  await projectCheckboxes.nth(1).click({ modifiers: ['Shift'] });
  await expect(projectCheckboxes.nth(0)).toBeChecked();
  await expect(projectCheckboxes.nth(1)).toBeChecked();
  await expect(page.locator('#updateSelectedProjectsBtn')).toContainText('Update selected stacks (2)');

  await page.locator('#updateSelectedProjectsBtn').click();
  await expect(page.locator('#appDialogModal')).toHaveClass(/show/);
  await page.locator('#appDialogConfirm').click();
  await expect(page.locator('#updateManagerActionModal')).toHaveClass(/show/);
  await expect(page.locator('#updateManagerActionState')).toContainText('Success');
  await expect(page.locator('#updateManagerActionMessage')).toContainText('Updated 2 stacks successfully.');
  await expect(page.locator('#updateManagerActionDetail')).toContainText('Updated: demo, jobs');
  await expect(page.locator('#updateManagerActionModal')).not.toHaveClass(/show/);
  await expect(page.locator('#updateManagerProjectList')).not.toContainText('demo');
  await expect(page.locator('#updateManagerProjectList')).not.toContainText('jobs');
  await expect(page.locator('#updateSelectedProjectsBtn')).toBeDisabled();

  await page.locator('#updateManagerHistoryTab').click();
  await expect(page.locator('#updateManagerHistoryList')).toContainText('demo');
  await expect(page.locator('#updateManagerHistoryList')).toContainText('jobs');

  await page.locator('#updateManagerContainersTab').click();
  const containerCheckbox = page.locator('#updateManagerContainerList .update-entry-select[data-update-select-type="container"]').first();
  await expect(containerCheckbox).toBeVisible();
  await containerCheckbox.click();
  await expect(containerCheckbox).toBeChecked();
  await expect(page.locator('#updateSelectedContainersBtn')).toContainText('Update selected containers (1)');

  await page.locator('#updateSelectedContainersBtn').click();
  await expect(page.locator('#appDialogModal')).toHaveClass(/show/);
  await page.locator('#appDialogConfirm').click();
  await expect(page.locator('#updateManagerActionModal')).toHaveClass(/show/);
  await expect(page.locator('#updateManagerActionState')).toContainText('Success');
  await expect(page.locator('#updateManagerActionDetail')).toContainText('Updated: cache');
  await expect(page.locator('#statusMessageArea')).toContainText('Updated 1 container successfully.');
  await expect(page.locator('#updateManagerActionModal')).not.toHaveClass(/show/);
  await expect(page.locator('#updateManagerContainerList')).toContainText('No standalone containers');
  await expect(page.locator('#updateSelectedContainersBtn')).toBeDisabled();

  await page.locator('#updateManagerHistoryTab').click();
  await expect(page.locator('#updateManagerHistoryList')).toContainText('cache');
});

test('filters sorts and bulk-enables auto-update targets without resizing the action buttons', async ({ page }) => {
  await page.goto('/');

  await page.locator('#updateManagerToggle').click();
  await expect(page.locator('#updateManagerModal')).toHaveClass(/show/);
  await page.locator('#updateManagerAutoUpdatesTab').click();
  await expect(page.locator('#updateManagerAutoList')).toContainText('demo');
  await expect(page.locator('#updateManagerAutoList')).toContainText('jobs');
  await expect(page.locator('#updateManagerAutoList')).toContainText('cache');
  await expect(page.locator('#updateManagerAutoList')).toContainText('observer');

  await expect(page.locator('#updateManagerAutoUpdatesTab')).toHaveAttribute('aria-selected', 'true');
  await expect.poll(async () => page.locator('#updateManagerAutoUpdatesTab .update-manager-tab-label').evaluate((node) => Number(getComputedStyle(node).opacity))).toBeGreaterThan(0.9);
  await expect.poll(async () => page.locator('#updateManagerProjectsTab .update-manager-tab-label').evaluate((node) => Number(getComputedStyle(node).opacity))).toBeLessThan(0.2);

  const buttonWidths = await page.locator('#updateManagerAutoList .auto-update-toggle-btn').evaluateAll((nodes) => (
    nodes.map((node) => Math.round(node.getBoundingClientRect().width))
  ));
  expect(Math.max(...buttonWidths) - Math.min(...buttonWidths)).toBeLessThanOrEqual(2);

  const observerSummaryTruncates = await page.locator('#updateManagerAutoList .update-entry').filter({ hasText: 'observer' }).locator('.update-version-code--summary').evaluate((node) => node.scrollWidth > node.clientWidth);
  expect(observerSummaryTruncates).toBeTruthy();

  await page.selectOption('#updateManagerSortSelect', 'desc');
  await page.locator('#updateManagerSearchInput').fill('o');
  const filteredNames = await page.locator('#updateManagerAutoList .update-entry .update-entry-summary-name').evaluateAll((nodes) => nodes.map((node) => node.textContent.trim()));
  expect(filteredNames).toEqual(['observer', 'jobs', 'demo']);
  await expect(page.locator('#updateManagerAutoList')).not.toContainText('cache');

  await page.locator('#updateManagerSearchInput').fill('');
  await page.selectOption('#updateManagerSortSelect', 'asc');

  const demoEntry = page.locator('#updateManagerAutoList .update-entry').filter({ hasText: 'demo' });
  const cacheEntry = page.locator('#updateManagerAutoList .update-entry').filter({ hasText: 'cache' });
  await demoEntry.locator('.update-entry-select').click();
  await cacheEntry.locator('.update-entry-select').click();
  await expect(page.locator('#autoupdateSelectedBtn')).toContainText('Autoupdate Selected (2)');

  await page.locator('#autoupdateSelectedBtn').click();
  await expect(page.locator('#appDialogModal')).toHaveClass(/show/);
  await page.locator('#appDialogConfirm').click();
  await expect(page.locator('#updateManagerActionModal')).toHaveClass(/show/);
  await expect(page.locator('#updateManagerActionState')).toContainText('Success');
  await expect(page.locator('#updateManagerActionMessage')).toContainText('Enabled auto-update for 2 targets.');
  await expect(page.locator('#updateManagerActionDetail')).toContainText('Enabled: demo, cache');
  await expect(page.locator('#statusMessageArea')).toContainText('Enabled auto-update for 2 targets.');
  await expect(page.locator('#updateManagerActionModal')).not.toHaveClass(/show/);
  await expect(demoEntry.locator('.auto-update-toggle-btn')).toContainText('Disable auto-update');
  await expect(cacheEntry.locator('.auto-update-toggle-btn')).toContainText('Disable auto-update');
  await expect(page.locator('#autoupdateSelectedBtn')).toBeDisabled();
});
