import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  fullyParallel: false,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5100',
    headless: true,
    viewport: { width: 1440, height: 1100 },
  },
  webServer: {
    command: '.venv/bin/python tests/e2e_server.py',
    url: 'http://127.0.0.1:5100',
    timeout: 30_000,
    reuseExistingServer: false,
  },
});
