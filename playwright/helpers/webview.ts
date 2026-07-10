import { chromium, type Browser, type Page } from '@playwright/test';
import { getOptionalEnv } from './env';

export async function connectToWebView(): Promise<{ browser: Browser; page: Page }> {
  const endpoint = getOptionalEnv('WEBVIEW_CDP_ENDPOINT', 'http://localhost:9222');
  const browser = await chromium.connectOverCDP(endpoint);
  const context = browser.contexts()[0];
  if (!context) {
    await browser.close();
    throw new Error(`No browser context found from WebView endpoint: ${endpoint}`);
  }
  const page = context.pages()[0];
  if (!page) {
    await browser.close();
    throw new Error(`No page found from WebView endpoint: ${endpoint}`);
  }
  return { browser, page };
}
