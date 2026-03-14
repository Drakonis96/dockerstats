import { expect, test } from '@playwright/test';

test.beforeEach(async ({ request }) => {
  await request.post('http://127.0.0.1:5100/api/test/reset');
});

test('renders table, summaries and filters', async ({ page }) => {
  await page.goto('/');

  await expect(page.locator('#summaryTotal')).toHaveText('3');
  await expect(page.locator('#summaryRunning')).toHaveText('2');
  await expect(page.locator('#summaryExited')).toHaveText('1');
  await expect(page.locator('#summaryUpdates')).toHaveText('1');

  await expect(page.locator('#heroShell')).toBeVisible();
  await expect(page.locator('#heroToggleBtn')).toBeVisible();
  await page.locator('#heroToggleBtn').click();
  await expect(page.locator('#heroShell')).toBeHidden();
  await expect(page.locator('#heroToggleBtn')).toHaveText('Show overview');
  await page.locator('#heroToggleBtn').click();
  await expect(page.locator('#heroShell')).toBeVisible();

  await page.getByRole('button', { name: 'Exited' }).click();
  await expect(page.locator('#metricsTable tbody tr')).toHaveCount(1);
  await expect(page.locator('#metricsTable tbody tr')).toContainText('worker');

  await page.locator('#quickFilterBar').getByRole('button', { name: 'All', exact: true }).click();
  await page.locator('#filterName').fill('db');
  await expect(page.locator('#metricsTable tbody tr')).toHaveCount(1);
  await expect(page.locator('#metricsTable tbody tr')).toContainText('db');
  await expect(page.locator('#activeFiltersValue')).toContainText('1 active filters');
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
