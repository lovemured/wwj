import { defineConfig } from '@playwright/test';
import dotenv from 'dotenv';
import path from 'path';

dotenv.config({ path: path.resolve(__dirname, 'playwright/.env') });

export default defineConfig({
  testDir: './playwright/tests',
  timeout: 120_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  use: {
    baseURL: process.env.CRM_BASE_URL || 'https://lxcrm-staging.weiwenjia.com',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'pc-chromium',
      testMatch: /pc\/.*\.spec\.ts/,
      use: {
        viewport: null,
        launchOptions: { args: ['--start-maximized'] },
      },
    },
    {
      name: 'webview-cdp',
      testMatch: /webview\/.*\.spec\.ts/,
      use: { viewport: null },
    },
  ],
  outputDir: 'test-results',
});
