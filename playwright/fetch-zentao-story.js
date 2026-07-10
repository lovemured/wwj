/**
 * 禅道需求抓取脚本
 * 登录禅道系统并获取需求详情
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

// 配置
const ZENTAO_URL = 'https://zentao.weiwenjia.com';
const STORY_URL = 'https://zentao.weiwenjia.com/story-view-23684-3-project-2104.html';
const USERNAME = '2152';
const PASSWORD = 'xh123';

async function fetchZentaoStory() {
  console.log('🚀 启动浏览器...');
  const browser = await chromium.launch({
    headless: false, // 显示浏览器方便调试
    slowMo: 500 // 放慢操作速度
  });

  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });

  const page = await context.newPage();

  try {
    // 1. 访问禅道首页
    console.log('📍 访问禅道首页...');
    await page.goto(ZENTAO_URL, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);

    // 检查是否已登录
    const currentUrl = page.url();
    console.log('当前URL:', currentUrl);

    // 2. 检查是否在登录页面
    const hasLoginForm = await page.locator('input[name="account"], input[name="username"], #account, #username').count() > 0;

    if (hasLoginForm || currentUrl.includes('login')) {
      console.log('🔐 正在登录...');

      // 尝试多种可能的登录表单选择器
      const accountSelectors = [
        'input[name="account"]',
        'input[name="username"]',
        '#account',
        '#username',
        'input[placeholder*="账号"]',
        'input[placeholder*="用户名"]'
      ];

      const passwordSelectors = [
        'input[name="password"]',
        '#password',
        'input[type="password"]',
        'input[placeholder*="密码"]'
      ];

      const submitSelectors = [
        'button[type="submit"]',
        'input[type="submit"]',
        '#submit',
        '.btn-primary',
        'button:has-text("登录")',
        'a:has-text("登录")'
      ];

      // 找到并填写账号
      for (const selector of accountSelectors) {
        const input = page.locator(selector);
        if (await input.count() > 0) {
          console.log(`找到账号输入框: ${selector}`);
          await input.fill(USERNAME);
          break;
        }
      }

      // 找到并填写密码
      for (const selector of passwordSelectors) {
        const input = page.locator(selector);
        if (await input.count() > 0) {
          console.log(`找到密码输入框: ${selector}`);
          await input.fill(PASSWORD);
          break;
        }
      }

      // 点击登录按钮
      for (const selector of submitSelectors) {
        const button = page.locator(selector);
        if (await button.count() > 0) {
          console.log(`找到登录按钮: ${selector}`);
          await button.click();
          break;
        }
      }

      // 等待登录完成
      await page.waitForTimeout(3000);
      console.log('登录后URL:', page.url());
    }

    // 3. 访问需求页面
    console.log('📋 访问需求页面...');
    await page.goto(STORY_URL, { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);

    // 4. 提取需求内容
    console.log('📝 提取需求内容...');

    // 获取页面标题
    const pageTitle = await page.title();
    console.log('页面标题:', pageTitle);

    // 获取需求内容 - 禅道常见的内容区域选择器
    const contentSelectors = [
      '.detail-content',
      '.story-content',
      '#content',
      '.main-content',
      '.table-data',
      '.panel-body',
      '.article-content',
      '.detail',
      'article',
      '.story-detail',
      '.view-content'
    ];

    let storyContent = '';

    // 获取页面截图
    const screenshotPath = path.join(__dirname, 'zentao-story-screenshot.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log('📸 截图已保存:', screenshotPath);

    // 获取需求标题
    let storyTitle = '';
    const titleSelectors = [
      '.story-title',
      'h1',
      'h2.title',
      '.page-title',
      '.header-title',
      '#title'
    ];

    for (const selector of titleSelectors) {
      const element = page.locator(selector).first();
      if (await element.count() > 0) {
        storyTitle = await element.textContent() || '';
        if (storyTitle.trim()) {
          console.log('需求标题:', storyTitle);
          break;
        }
      }
    }

    // 获取主要内容
    for (const selector of contentSelectors) {
      const element = page.locator(selector).first();
      if (await element.count() > 0) {
        const text = await element.textContent();
        if (text && text.trim().length > 50) {
          storyContent = text.trim();
          console.log(`找到内容区域: ${selector}`);
          break;
        }
      }
    }

    // 如果没有找到内容，获取整个页面的主体内容
    if (!storyContent) {
      storyContent = await page.locator('body').textContent() || '';
    }

    // 获取页面HTML以便后续分析
    const htmlPath = path.join(__dirname, 'zentao-story-page.html');
    const htmlContent = await page.content();
    fs.writeFileSync(htmlPath, htmlContent);
    console.log('📄 HTML已保存:', htmlPath);

    // 尝试提取更结构化的信息
    const storyData = await page.evaluate(() => {
      const data = {
        title: '',
        id: '',
        status: '',
        priority: '',
        content: '',
        acceptance: '',
        fields: {}
      };

      // 禅道常见字段提取
      const fieldMappings = {
        'ID': ['story-id', 'id'],
        '标题': ['story-title', 'title'],
        '状态': ['status', 'story-status'],
        '优先级': ['pri', 'priority'],
        '所属模块': ['module', 'product'],
        '需求类型': ['type', 'story-type'],
        '验收标准': ['spec', 'acceptance'],
        '需求描述': ['desc', 'description', 'content']
      };

      // 尝试获取表格数据
      document.querySelectorAll('tr, .row, .field').forEach(row => {
        const th = row.querySelector('th, .label, .field-label');
        const td = row.querySelector('td, .value, .field-value');
        if (th && td) {
          const label = th.textContent?.trim() || '';
          const value = td.textContent?.trim() || '';
          if (label && value) {
            data.fields[label] = value;
          }
        }
      });

      // 获取主要内容区域
      const contentEl = document.querySelector('.detail-content, .story-content, .article-content, #content');
      if (contentEl) {
        data.content = contentEl.textContent?.trim() || '';
      }

      return data;
    });

    console.log('\n📊 需求数据:');
    console.log(JSON.stringify(storyData, null, 2));

    // 保存结果
    const resultPath = path.join(__dirname, 'zentao-story-result.json');
    fs.writeFileSync(resultPath, JSON.stringify({
      url: STORY_URL,
      title: storyTitle,
      pageTitle: pageTitle,
      content: storyContent,
      structuredData: storyData,
      fetchedAt: new Date().toISOString()
    }, null, 2));
    console.log('💾 结果已保存:', resultPath);

    return {
      success: true,
      title: storyTitle,
      content: storyContent,
      structuredData: storyData,
      screenshotPath,
      htmlPath
    };

  } catch (error) {
    console.error('❌ 错误:', error.message);
    const errorScreenshot = path.join(__dirname, 'zentao-error-screenshot.png');
    await page.screenshot({ path: errorScreenshot, fullPage: true });
    console.log('📸 错误截图已保存:', errorScreenshot);
    return {
      success: false,
      error: error.message
    };
  } finally {
    console.log('\n🏁 关闭浏览器...');
    await browser.close();
  }
}

// 执行
fetchZentaoStory().then(result => {
  console.log('\n✅ 完成!');
}).catch(err => {
  console.error('执行失败:', err);
});