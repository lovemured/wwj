import { test, expect } from '@playwright/test';

const BASE_URL = 'https://lxcrm-test.weiwenjia.com';

// 生成随机线索名称
function generateRandomLeadName(): string {
  const timestamp = Date.now();
  return `测试线索_${timestamp}`;
}

// 生成随机客户名称
function generateRandomCustomerName(): string {
  const timestamp = Date.now();
  return `客户_${timestamp}`;
}

// 生成随机联系人姓名
function generateRandomContactName(): string {
  const timestamp = Date.now();
  return `联系人_${timestamp}`;
}

// 生成随机手机号
function generateRandomPhone(): string {
  const prefixes = ['138', '139', '187', '188', '189'];
  const prefix = prefixes[Math.floor(Math.random() * prefixes.length)];
  const suffix = Math.floor(Math.random() * 100000000).toString().padStart(8, '0');
  return prefix + suffix;
}

// 测试配置
test.use({
  baseURL: BASE_URL,
  screenshot: 'only-on-failure',
  video: 'retain-on-failure',
  viewport: null, 
  launchOptions: {
    args: ['--start-maximized'],
  },
});

// 设置单个测试超时时间为5分钟
test.setTimeout(300000);

test.describe('CRM线索管理', () => {

  test('线索完整流程：创建-查看-转客户-编辑-删除', async ({ page }) => {
    // 登录流程
    await test.step('登录系统', async () => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      await page.locator('#account').fill((process as any).env.CRM_USERNAME || '18217038858');
      await page.locator('#password').fill((process as any).env.CRM_PASSWORD || 'Ik123456');
      await page.getByLabel('', { exact: true }).check();
      await page.getByRole('button', { name: '登 录' }).click();
      await page.waitForURL(/.*workbench/);
    });

    // ===================== 线索1：测试转客户流程 =====================
    const leadNameForConvert = generateRandomLeadName();
    const phoneForConvert = generateRandomPhone();

    // 创建线索1（用于转客户）
    await test.step('创建线索（用于转客户）', async () => {
      await page.getByRole('link', { name: '线索' }).first().click();
      await page.waitForLoadState('networkidle');
      await page.locator('a').filter({ hasText: '新增线索' }).click();
      await page.waitForLoadState('networkidle');
      await page.locator('#lead_market_activity').click();
      await page.getByTitle('yy新增市场活动1').click();
      await page.locator('#content_undefined').first().fill(leadNameForConvert);
      await page.locator('#lead_source').click();
      await page.waitForTimeout(500);
      await page.getByTitle('搜客宝', { exact: true }).click();
      await page.getByText('展开更多信息').click();
      await page.locator('[id="lead_address.phone"]').fill(phoneForConvert);
      await page.screenshot({ path: 'test-results/leads-form-filled.png' });
      await page.getByRole('button', { name: '保存' }).click();
      await page.waitForLoadState('networkidle');
      await page.screenshot({ path: 'test-results/leads-created-success.png' });
    });

    // 查看线索详情并转客户
    const customerName = generateRandomCustomerName();
    const contactName = generateRandomContactName();
    const customerPhone = generateRandomPhone();
    const contactPhone = generateRandomPhone();

    await test.step('查看线索详情', async () => {
      await page.getByRole('link', { name: '线索' }).first().click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      await page.getByText(leadNameForConvert, { exact: true }).click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'test-results/leads-detail.png' });
    });

    await test.step('线索转客户', async () => {
      // 点击基本信息 tab
      await page.getByText('基本信息').click();
      await page.waitForTimeout(2000);
      // 点击转换按钮，等待下拉菜单展开
      await page.getByRole('button', { name: '转换' }).click();
      await page.waitForTimeout(1000);
      // 选择"转成新客户KH" - 下拉菜单中的选项是第2个
      await page.getByText('转成新客户KH').nth(1).click();
      await page.waitForTimeout(1000);
      // 点击下一步
      await page.getByRole('button', { name: '下一步' }).click();
      await page.waitForTimeout(1000);
      // 填写客户名称
      await page.getByRole('textbox', { name: '请输入客户名称' }).click();
      await page.getByRole('textbox', { name: '请输入客户名称' }).fill(customerName);
      // 选择地区
      await page.locator('#customer_address_region_info').click();
      await page.waitForTimeout(300);
      await page.getByText('贵州').click();
      await page.getByText('铜仁市').click();
      await page.getByRole('menuitemcheckbox', { name: '沿河土家族自治县' }).click();
      // 展开更多信息
      await page.getByText('展开更多信息').first().click();
      await page.waitForTimeout(300);
      // 选择上级客户
      await page.locator('#customer_parent').click();
      await page.waitForTimeout(300);
      await page.getByText('test', { exact: true }).click();
      // 选择客户状态
      await page.locator('#customer_status').click();
      await page.waitForTimeout(300);
      await page.getByText('初访').click();
      // 选择行业
      await page.locator('#customer_industry').click();
      await page.waitForTimeout(300);
      await page.getByText('金融').click();
      // 选择企业规模
      await page.locator('#customer_staff_size').click();
      await page.waitForTimeout(300);
      await page.getByText('-20人').click();
      // 填写联系人姓名
      await page.getByRole('textbox', { name: '请输入姓名' }).click();
      await page.getByRole('textbox', { name: '请输入姓名' }).fill(contactName);
      // 展开联系人更多信息
      await page.getByText('展开更多信息').click();
      await page.waitForTimeout(300);
      // 填写联系人手机（第二个手机输入框）
      const phoneInputs = await page.getByRole('textbox', { name: '请输入手机' }).all();
      if (phoneInputs.length > 1) {
        await phoneInputs[1].fill(contactPhone);
      }
      // 保存
      await page.getByRole('button', { name: '保存' }).click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'test-results/leads-convert-success.png' });
    });

    // 验证客户创建成功
    await test.step('验证客户创建成功', async () => {
      await page.getByRole('link', { name: '客户' }).first().click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      // 搜索新创建的客户 - 使用更精确的定位器
      await page.getByRole('textbox', { name: '搜索', exact: true }).fill(customerName);
      await page.keyboard.press('Enter');
      await page.waitForTimeout(3000);
      // 验证客户存在
      await expect(page.getByText(customerName)).toBeVisible();
      await page.screenshot({ path: 'test-results/customer-created-verified.png' });
    });

    // ===================== 线索2：测试编辑和删除流程 =====================
    const leadNameForEdit = generateRandomLeadName();
    const phoneForEdit = generateRandomPhone();

    // 创建线索2（用于编辑和删除）
    await test.step('创建线索（用于编辑删除）', async () => {
      await page.getByRole('link', { name: '线索' }).first().click();
      await page.waitForLoadState('networkidle');
      await page.locator('a').filter({ hasText: '新增线索' }).click();
      await page.waitForLoadState('networkidle');
      await page.locator('#lead_market_activity').click();
      await page.getByTitle('yy新增市场活动1').click();
      await page.locator('#content_undefined').first().fill(leadNameForEdit);
      await page.locator('#lead_source').click();
      await page.waitForTimeout(500);
      await page.getByTitle('搜客宝', { exact: true }).click();
      await page.getByText('展开更多信息').click();
      await page.locator('[id="lead_address.phone"]').fill(phoneForEdit);
      await page.getByRole('button', { name: '保存' }).click();
      await page.waitForLoadState('networkidle');
    });

    // 编辑线索
    let editedLeadName = leadNameForEdit;
    await test.step('编辑线索', async () => {
      await page.getByRole('link', { name: '线索' }).first().click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      await page.getByText(editedLeadName, { exact: true }).click();
      await page.waitForTimeout(2000);
      await page.getByRole('button', { name: '更多', exact: true }).click();
      await page.waitForTimeout(500);
      await page.locator('div').filter({ hasText: /^编辑$/ }).nth(4).click();
      await page.waitForTimeout(2000);
      // 更新线索名称
      editedLeadName = generateRandomLeadName();
      await page.locator('#content_undefined').first().fill(editedLeadName);
      await page.getByRole('button', { name: '保存' }).click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'test-results/leads-edit-success.png' });
    });

    // 删除线索
    await test.step('删除线索', async () => {
      await page.getByRole('link', { name: '线索' }).first().click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      await page.getByText(editedLeadName, { exact: true }).click();
      await page.waitForTimeout(2000);
      await page.getByRole('button', { name: '更多', exact: true }).click();
      await page.waitForTimeout(500);
      await page.getByTitle('删除').click();
      await page.waitForTimeout(500);
      await page.getByRole('button', { name: '确定' }).click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'test-results/leads-delete-success.png' });
    });

    // ===================== 线索3：测试转已有客户流程 =====================
    const leadNameForExisting = generateRandomLeadName();
    const phoneForExisting = generateRandomPhone();
    const opportunityTitle = `商机_${Date.now()}`;

    // 创建线索3（用于转已有客户）
    await test.step('创建线索（用于转已有客户）', async () => {
      await page.getByRole('link', { name: '线索' }).first().click();
      await page.waitForLoadState('networkidle');
      await page.locator('a').filter({ hasText: '新增线索' }).click();
      await page.waitForLoadState('networkidle');
      await page.locator('#lead_market_activity').click();
      await page.getByTitle('yy新增市场活动1').click();
      await page.locator('#content_undefined').first().fill(leadNameForExisting);
      await page.locator('#lead_source').click();
      await page.waitForTimeout(500);
      await page.getByTitle('搜客宝', { exact: true }).click();
      await page.getByText('展开更多信息').click();
      await page.locator('[id="lead_address.phone"]').fill(phoneForExisting);
      await page.getByRole('button', { name: '保存' }).click();
      await page.waitForLoadState('networkidle');
    });

    // 线索转已有客户
    await test.step('线索转已有客户', async () => {
      // 进入线索列表并点击线索
      await page.getByRole('link', { name: '线索' }).first().click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      await page.getByText(leadNameForExisting, { exact: true }).click();
      await page.waitForTimeout(2000);
      // 点击基本信息 tab
      await page.getByText('基本信息').click();
      await page.waitForTimeout(2000);
      // 点击转换按钮
      await page.getByRole('button', { name: '转换' }).click();
      await page.waitForTimeout(1000);
      // 选择"转成已有客户KH"
      await page.getByText('转成已有客户KH').nth(1).click();
      await page.waitForTimeout(1000);
      // 选择已有客户
      await page.locator('#customer_customer').click();
      await page.waitForTimeout(500);
      await page.getByText('勿动-测试上海市大上海艺术有限公司', { exact: true }).click();
      await page.waitForTimeout(500);
      // 选择联系人
      await page.locator('#contact_contact').click();
      await page.waitForTimeout(500);
      await page.getByText('67', { exact: true }).click();
      await page.waitForTimeout(500);
      // 勾选同步创建商机
      await page.getByRole('checkbox', { name: '同步创建商机SJ' }).check();
      await page.waitForTimeout(300);
      // 填写商机标题
      await page.getByRole('textbox', { name: 'asdf' }).fill(opportunityTitle);
      await page.waitForTimeout(300);
      // 选择商机阶段
      await page.locator('#opportunity_stage').click();
      await page.waitForTimeout(300);
      await page.getByText('需求确定', { exact: true }).click();
      await page.waitForTimeout(300);
      // 选择预计签单日期（选择下月25日）
      await page.locator('#opportunity_expect_sign_date').click();
      await page.waitForTimeout(500);
      // 点击下一月按钮
      await page.getByRole('button').filter({ hasText: /^$/ }).nth(4).click();
      await page.waitForTimeout(300);
      await page.getByText('25', { exact: true }).click();
      await page.waitForTimeout(500);
      // 保存
      await page.getByRole('button', { name: '保存' }).click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'test-results/leads-convert-existing-success.png' });
    });

    // 验证商机创建成功
    await test.step('验证商机创建成功', async () => {
      await page.getByRole('link', { name: '商机SJ' }).first().click();
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(3000);
      // 搜索新创建的商机
      await page.getByRole('textbox', { name: '搜索', exact: true }).fill(opportunityTitle);
      await page.keyboard.press('Enter');
      await page.waitForTimeout(3000);
      // 验证商机存在 - 使用 contains 文本匹配
      const opportunityLink = page.locator(`text=${opportunityTitle}`).first();
      await expect(opportunityLink).toBeVisible();
      await page.screenshot({ path: 'test-results/opportunity-created-verified.png' });
    });
  });
});

//显示浏览器窗口执行
// npx playwright test playwright/crm-leads-e2e.spec.ts --headed

// 单独测试：线索转已有客户
test.describe('线索转已有客户', () => {
  test('线索转已有客户流程', async ({ page }) => {
    // 登录流程
    await test.step('登录系统', async () => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      await page.locator('#account').fill((process as any).env.CRM_USERNAME || '18217038858');
      await page.locator('#password').fill((process as any).env.CRM_PASSWORD || 'Ik123456');
      await page.getByLabel('', { exact: true }).check();
      await page.getByRole('button', { name: '登 录' }).click();
      await page.waitForURL(/.*workbench/);
    });

    const leadNameForExisting = generateRandomLeadName();
    const phoneForExisting = generateRandomPhone();
    const opportunityTitle = `商机_${Date.now()}`;

    // 创建线索
    await test.step('创建线索', async () => {
      await page.getByRole('link', { name: '线索' }).first().click();
      await page.waitForLoadState('networkidle');
      await page.locator('a').filter({ hasText: '新增线索' }).click();
      await page.waitForLoadState('networkidle');
      await page.locator('#lead_market_activity').click();
      await page.getByTitle('yy新增市场活动1').click();
      await page.locator('#content_undefined').first().fill(leadNameForExisting);
      await page.locator('#lead_source').click();
      await page.waitForTimeout(500);
      await page.getByTitle('搜客宝', { exact: true }).click();
      await page.getByText('展开更多信息').click();
      await page.locator('[id="lead_address.phone"]').fill(phoneForExisting);
      await page.getByRole('button', { name: '保存' }).click();
      await page.waitForLoadState('networkidle');
    });

    // 线索转已有客户
    await test.step('线索转已有客户', async () => {
      // 进入线索列表并点击线索
      await page.getByRole('link', { name: '线索' }).first().click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      await page.getByText(leadNameForExisting, { exact: true }).click();
      await page.waitForTimeout(2000);
      // 点击基本信息 tab
      await page.getByText('基本信息').click();
      await page.waitForTimeout(2000);
      // 点击转换按钮
      await page.getByRole('button', { name: '转换' }).click();
      await page.waitForTimeout(1000);
      // 选择"转成已有客户KH"
      await page.getByText('转成已有客户KH').nth(1).click();
      await page.waitForTimeout(1000);
      // 选择已有客户
      await page.locator('#customer_customer').click();
      await page.waitForTimeout(500);
      await page.getByText('勿动-测试上海市大上海艺术有限公司', { exact: true }).click();
      await page.waitForTimeout(500);
      // 选择联系人
      await page.locator('#contact_contact').click();
      await page.waitForTimeout(500);
      await page.getByText('67', { exact: true }).click();
      await page.waitForTimeout(500);
      // 勾选同步创建商机
      await page.getByRole('checkbox', { name: '同步创建商机SJ' }).check();
      await page.waitForTimeout(300);
      // 填写商机标题
      await page.getByRole('textbox', { name: 'asdf' }).fill(opportunityTitle);
      await page.waitForTimeout(300);
      // 选择商机阶段
      await page.locator('#opportunity_stage').click();
      await page.waitForTimeout(300);
      await page.getByText('需求确定', { exact: true }).click();
      await page.waitForTimeout(300);
      // 选择预计签单日期
      await page.locator('#opportunity_expect_sign_date').click();
      await page.waitForTimeout(500);
      await page.getByRole('button').filter({ hasText: /^$/ }).nth(4).click();
      await page.waitForTimeout(300);
      await page.getByText('25', { exact: true }).click();
      await page.waitForTimeout(500);
      // 保存
      await page.getByRole('button', { name: '保存' }).click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'test-results/leads-convert-existing-success.png' });
    });

    // 验证商机创建成功
    await test.step('验证商机创建成功', async () => {
      await page.getByRole('link', { name: '商机SJ' }).first().click();
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(3000);
      // 搜索新创建的商机
      await page.getByRole('textbox', { name: '搜索', exact: true }).fill(opportunityTitle);
      await page.keyboard.press('Enter');
      await page.waitForTimeout(3000);
      // 验证商机存在
      const opportunityLink = page.locator(`text=${opportunityTitle}`).first();
      await expect(opportunityLink).toBeVisible();
      await page.screenshot({ path: 'test-results/opportunity-created-verified.png' });
    });
  });
});

// 单独运行线索转已有客户测试
// npx playwright test playwright/crm-leads-e2e.spec.ts --headed -g "线索转已有客户流程"