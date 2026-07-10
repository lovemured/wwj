import { test, expect, chromium } from '@playwright/test';

test('WebView 连接验证 - 工作台页面', async () => {
  // 连接到 Android WebView
  const browser = await chromium.connectOverCDP('http://localhost:9222');

  // 获取所有页面
  const contexts = browser.contexts();
  const page = contexts[0].pages()[0];

  console.log('✅ 已连接到 WebView');
  console.log(`当前页面: ${page.url()}`);
  console.log(`页面标题: ${await page.title()}`);

  // 验证当前在工作台页面
  expect(await page.title()).toContain('工作台');

  // 截图验证
  await page.screenshot({ path: 'test-results/webview-dashboard.png' });

  // 关闭连接
  await browser.close();
});

// 需要先设置端口转发：
// adb forward tcp:9222 localabstract:webview_devtools_remote_24833