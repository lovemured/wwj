/**
 * 禅道需求抓取脚本 - 需求 #23683
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

// 配置
const ZENTAO_URL = 'https://zentao.weiwenjia.com';
const STORY_URL = 'https://zentao.weiwenjia.com/story-view-23683-2-project-2104.html';
const USERNAME = '2152';
const PASSWORD = 'xh123';

async function fetchZentaoStory() {
  console.log('🚀 启动浏览器...');
  const browser = await chromium.launch({
    headless: false,
    slowMo: 300
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
    const hasLoginForm = await page.locator('input[name="account"]').count() > 0;

    if (hasLoginForm || currentUrl.includes('login')) {
      console.log('🔐 正在登录...');
      await page.locator('input[name="account"]').fill(USERNAME);
      await page.locator('input[name="password"]').fill(PASSWORD);
      await page.locator('button[type="submit"]').click();
      await page.waitForTimeout(3000);
      console.log('登录后URL:', page.url());
    }

    // 3. 访问需求页面
    console.log('📋 访问需求页面 #23683...');
    await page.goto(STORY_URL, { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);

    // 4. 获取页面标题
    const pageTitle = await page.title();
    console.log('页面标题:', pageTitle);

    // 5. 获取截图
    const screenshotPath = path.join(__dirname, 'zentao-story-23683-screenshot.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log('📸 截图已保存:', screenshotPath);

    // 6. 提取需求结构化信息
    const storyData = await page.evaluate(() => {
      const data = {
        title: '',
        id: '',
        content: '',
        fields: {}
      };

      // 获取表格数据
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

      // 获取标题
      const titleEl = document.querySelector('h1, h2.title, .page-title');
      if (titleEl) {
        data.title = titleEl.textContent?.trim() || '';
      }

      return data;
    });

    console.log('\n📊 需求数据:');
    console.log(JSON.stringify(storyData, null, 2));

    // 7. 保存HTML
    const htmlPath = path.join(__dirname, 'zentao-story-23683-page.html');
    const htmlContent = await page.content();
    fs.writeFileSync(htmlPath, htmlContent);
    console.log('📄 HTML已保存:', htmlPath);

    // 8. 保存结果JSON
    const resultPath = path.join(__dirname, 'zentao-story-23683-result.json');
    fs.writeFileSync(resultPath, JSON.stringify({
      url: STORY_URL,
      pageTitle: pageTitle,
      structuredData: storyData,
      fetchedAt: new Date().toISOString()
    }, null, 2));
    console.log('💾 结果已保存:', resultPath);

    return { success: true, data: storyData };

  } catch (error) {
    console.error('❌ 错误:', error.message);
    return { success: false, error: error.message };
  } finally {
    console.log('\n🏁 关闭浏览器...');
    await browser.close();
  }
}

fetchZentaoStory();