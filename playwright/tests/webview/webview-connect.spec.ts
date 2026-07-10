import { expect, test } from '@playwright/test';
import { connectToWebView } from '../../helpers/webview';

test('WebView 连接检查', async () => {
  const { browser, page } = await connectToWebView();
  try {
    await page.waitForLoadState('domcontentloaded');
    const title = await page.title();
    const url = page.url();
    const bodyTextLength = await page.evaluate(() => document.body.innerText.length);

    console.log(`WebView title: ${title}`);
    console.log(`WebView url: ${url}`);
    console.log(`WebView text length: ${bodyTextLength}`);

    expect(url).toBeTruthy();
    expect(bodyTextLength).toBeGreaterThan(0);
  } finally {
    await browser.close();
  }
});
