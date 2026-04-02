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

test('supports container actions and chart loading', async ({ page }) => {
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
  await expect(page.locator('#chartContainer')).toBeVisible();
  await expect(page.locator('#chartTitle')).toContainText('db');
  await expect(page.locator('#chartStatus')).toHaveText('');
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

test('handles password change and user creation from settings modal', async ({ page }) => {
  await page.goto('/');

  await page.locator('#settingsBtn').click();
  await expect(page.locator('#settingsModal')).toHaveClass(/show/);

  await page.locator('#currentPassword').fill('adminpass');
  await page.locator('#newPassword').fill('changed-pass');
  await page.locator('#confirmPassword').fill('changed-pass');
  await page.locator('#savePasswordBtn').click();
  await expect(page.locator('#statusMessageArea')).toContainText('Password changed successfully.');
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
  await page.locator('#notifCooldownSeconds').fill('45');
  await page.locator('#notifSilenceEnabled').check();
  await page.locator('#notifSilenceStart').fill('23:00');
  await page.locator('#notifSilenceEnd').fill('06:30');
  await page.locator('#notifDedupeWindowSeconds').fill('240');
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
  expect(settingsPayload.cooldown_seconds).toBe(45);
  expect(settingsPayload.silence_enabled).toBe(true);
  expect(settingsPayload.silence_start).toBe('23:00');
  expect(settingsPayload.silence_end).toBe('06:30');
  expect(settingsPayload.dedupe_window_seconds).toBe(240);
  expect(settingsPayload.security_enabled).toBe(true);
  expect(settingsPayload.security_public_ports_enabled).toBe(false);
  expect(settingsPayload.security_latest_enabled).toBe(false);

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

test('opens the update manager, runs update and rollback, and shows load errors', async ({ page, request }) => {
  await page.goto('/');

  await page.locator('#updateManagerToggle').click();
  await expect(page.locator('#updateManagerModal')).toHaveClass(/show/);
  await expect(page.locator('#updateManagerModal')).toContainText('Experimental');
  await expect(page.locator('#updateManagerProjectList')).toContainText('demo');
  await expect(page.locator('#updateManagerProjectList')).toContainText('jobs');
  await expect(page.locator('#updateManagerProjectList')).toContainText('broken');
  await expect(page.locator('#updateManagerContainerList')).toContainText('No standalone containers');
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
  await expect(projectPanel).toContainText('Compose files are unavailable, so Docker Stats will update the running services directly.');

  const updateButton = projectPanel.locator('.update-target-btn').first();
  await updateButton.click();
  await expect(page.locator('#appDialogModal')).toHaveClass(/show/);
  await page.locator('#appDialogConfirm').click();
  await expect(page.locator('#appDialogModal')).not.toHaveClass(/show/);
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
  await expect(page.locator('#appDialogModal')).not.toHaveClass(/show/);
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
