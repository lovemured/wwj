import { test, expect, chromium } from '@playwright/test';

test('WebView 录制测试 - 线索添加完整流程', async () => {
  test.setTimeout(180000); // 3 分钟超时

  // 连接到 Android WebView
  const browser = await chromium.connectOverCDP('http://localhost:9222');
  const context = browser.contexts()[0];
  const page = context.pages()[0];

  console.log(`✅ 已连接到 WebView: ${await page.title()}`);

  // ===== 业务流程测试 =====

  // 步骤 1：导航到线索列表
  await page.getByRole('listitem').filter({ hasText: '线索XS' }).click();
  await page.waitForTimeout(2000);
  console.log('✓ 已点击线索XS菜单');

  // 步骤 2：点击新增按钮
  await page.getByText('新增', { exact: true }).click();
  await page.waitForTimeout(3000);
  console.log('✓ 已点击新增按钮');

  // 步骤 3：填写线索基本信息

  // 线索姓名（必填）
  const testName = `测试线索_${Date.now()}`;
  await page.locator('input[name="name"]').fill(testName);
  await page.waitForTimeout(500);
  console.log(`✓ 已填写线索姓名: ${testName}`);

  // 线索来源
  await page.getByText('线索的来源，可以下拉选择也可以添加其他的来源').click();
  await page.waitForTimeout(500);
  await page.getByText('搜客宝', { exact: true }).click();
  await page.waitForTimeout(500);
  console.log('✓ 已选择线索来源: 搜客宝');

  // 跟进状态
  await page.getByText('跟进状态线索的跟进状态').click();
  await page.waitForTimeout(500);
  await page.getByText('需求确定').click();
  await page.waitForTimeout(500);
  console.log('✓ 已选择跟进状态: 需求确定');

  // 步骤 4：展开更多信息
  await page.getByText('展开').click();
  await page.waitForTimeout(1000);
  console.log('✓ 已展开更多信息');

  // 步骤 5：填写联系方式

  // 电话号码
  const testPhone = `138${Math.floor(Math.random() * 100000000).toString().padStart(8, '0')}`;
  await page.locator('input[name="address.phone"]').fill(testPhone);
  await page.waitForTimeout(500);
  console.log(`✓ 已填写电话: ${testPhone}`);

  // 步骤 6：保存线索
  // 注意：录制中没有保存操作，需要添加
  await page.getByText('保存', { exact: true }).click();
  await page.waitForTimeout(5000);
  console.log('✓ 已点击保存按钮');

  // 步骤 7：验证保存成功
  const successIndicator = await page.evaluate(() => {
    const bodyText = document.body.innerText;
    return {
      hasSuccessMessage: bodyText.includes('成功') || bodyText.includes('添加成功'),
      returnUrl: window.location.href.includes('common-list'),
      currentTitle: document.title
    };
  });

  console.log('\n=== 验证结果 ===');
  console.log(`页面标题: ${successIndicator.currentTitle}`);
  console.log(`是否返回列表: ${successIndicator.returnUrl ? '是' : '否'}`);
  console.log(`成功提示: ${successIndicator.hasSuccessMessage ? '有' : '无'}`);

  // 截图保存结果
  await page.screenshot({
    path: '/Users/mured/wwj/test-results/webview-test-result.png',
    fullPage: false,
    timeout: 5000
  }).catch(() => console.log('⚠️  截图失败'));

  console.log('✅ 测试完成');

  // 关闭连接
  await browser.close();
});