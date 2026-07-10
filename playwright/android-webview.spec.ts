import { test, expect } from '@playwright/test';
import { chromium } from '@playwright/test';
import dotenv from 'dotenv';
import path from 'path';

// 提前加载环境变量
const envPath = path.join(__dirname, '.env');
dotenv.config({ path: envPath });

// 全局变量
let browser: any = null;
let page: any = null;
const APP_PACKAGE = process.env.APP_PACKAGE || 'com.lixiaoyun.aike';
const TEST_USERNAME = process.env.TEST_USERNAME || '';
const TEST_PASSWORD = process.env.TEST_PASSWORD || '';

test.beforeAll(async () => {
  try {
    console.log('=== 配置 WebView 调试 ===');

    // 1. 启动 APP 并启用 WebView 调试
    console.log(`启动 APP: ${APP_PACKAGE}`);

    // 2. 设置 adb 端口转发（将设备的 Chrome DevTools 端口转发到本地）
    // WebView 通常使用 9222 端口
    console.log('设置端口转发: adb forward tcp:9222 localabstract:chrome_devtools_remote');

    // 3. 连接到 WebView
    console.log('尝试连接 WebView...');

    // 注意：需要先手动执行 adb 命令设置端口转发
    // 这里提供两种连接方式

    // 方式 1：通过 CDP 连接（如果 WebView 已启用调试）
    try {
      browser = await chromium.connectOverCDP('http://localhost:9222');
      console.log('✅ 成功连接到 WebView (CDP)');

      // 获取所有页面
      const contexts = browser.contexts();
      if (contexts.length > 0) {
        page = contexts[0].pages()[0];
        console.log('✅ 获取到页面');
      }
    } catch (error) {
      console.log('⚠️ CDP 连接失败，尝试其他方式...');
    }

    // 方式 2：如果连接失败，启动本地 Chrome 并提示用户
    if (!browser) {
      console.log('❌ 无法连接 WebView，请确保：');
      console.log('1. APP 已启用 WebView 调试');
      console.log('2. 已执行端口转发命令：');
      console.log('   adb forward tcp:9222 localabstract:chrome_devtools_remote');
      throw new Error('WebView 连接失败');
    }

  } catch (error) {
    console.error('测试初始化失败:', error);
    throw error;
  }
});

// 合并测试：登录 + 业务流程
test('WebView 录制模式 - 登录并执行业务流程', async () => {
  test.setTimeout(300000); // 5 分钟

  if (!page) {
    throw new Error('页面未初始化');
  }

  // ===== 第一阶段：登录 =====
  console.log('=== 开始登录流程（录制模式）===');

  // 使用传统的 Playwright 选择器（可以录制生成）
  await page.fill('input[type="text"]', TEST_USERNAME); // 用户名输入框
  await page.fill('input[type="password"]', TEST_PASSWORD); // 密码输入框
  await page.click('button[type="submit"]'); // 登录按钮

  // 等待登录完成
  await page.waitForTimeout(3000);

  // 验证登录成功
  const hasWelcome = await page.isVisible('text=工作台') || await page.isVisible('text=主页');
  expect(hasWelcome).toBe(true);
  console.log('✅ 登录成功');

  // ===== 第二阶段：业务流程 =====
  console.log('=== 开始业务流程 ===');

  // 生成随机测试数据
  const timestamp = Date.now();
  const leadTitle = `测试线索_${timestamp}`;

  // 导航到线索管理
  await page.click('text=线索');
  await page.waitForTimeout(2000);

  // 点击新增
  await page.click('text=新增');
  await page.waitForTimeout(2000);

  // 填写线索标题
  await page.fill('input[name="title"]', leadTitle);
  await page.waitForTimeout(1000);

  // 保存
  await page.click('text=保存');
  await page.waitForTimeout(3000);

  // 验证
  const successMessage = await page.isVisible('text=成功') || await page.isVisible('text=线索列表');
  expect(successMessage).toBe(true);
  console.log(`✓ 已完成线索添加: "${leadTitle}"`);
});

test.afterAll(async () => {
  // 关闭浏览器连接
  if (browser) {
    await browser.close();
  }
});