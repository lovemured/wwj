import { test, expect, chromium } from '@playwright/test';

test('线索管理 - 新增线索完整流程', async () => {
  test.setTimeout(180000);

  // 连接 Android WebView
  const browser = await chromium.connectOverCDP('http://localhost:9222');
  const context = browser.contexts()[0];
  const page = context.pages()[0];

  // 生成测试数据
  const testName = `测试线索_${Date.now()}`;
  const testPhone = `138${Math.floor(Math.random() * 100000000).toString().padStart(8, '0')}`;

  console.log(`测试数据: 姓名=${testName}, 电话=${testPhone}`);

  // 导航到线索列表（从工作台点击线索 tab）
  await page.getByText('线索XS', { exact: true }).click();
  await page.waitForTimeout(2000);

  // 点击新增
  await page.getByText('新增', { exact: true }).click();
  await page.waitForTimeout(3000);

  // 填写基本信息
  await page.locator('input[name="name"]').fill(testName);
  await page.waitForTimeout(500);

  // 选择线索来源
  await page.getByText('线索的来源，可以下拉选择也可以添加其他的来源').click();
  await page.waitForTimeout(500);
  await page.getByText('搜客宝', { exact: true }).click();
  await page.waitForTimeout(500);

  // 选择跟进状态
  await page.getByText('跟进状态线索的跟进状态').click();
  await page.waitForTimeout(500);
  await page.getByText('需求确定').click();
  await page.waitForTimeout(500);

  // 展开更多信息
  await page.getByText('展开').click();
  await page.waitForTimeout(1000);

  // 填写电话
  await page.locator('input[name="address.phone"]').fill(testPhone);
  await page.waitForTimeout(500);

  // 保存
  await page.getByText('保存', { exact: true }).click();
  await page.waitForTimeout(5000);

  // 验证
  expect(page.url()).toContain('common-list');

  // 截图
  await page.screenshot({
    path: 'test-results/lead-added.png',
    fullPage: false,
    timeout: 5000
  });

  await browser.close();

  console.log('✅ 线索添加成功');
});