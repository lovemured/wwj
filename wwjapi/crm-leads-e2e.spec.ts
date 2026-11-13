import { test, expect, Page, Locator } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

// ===================== 工具函数 =====================

function generateRandomName(prefix: string): string {
  return `${prefix}_${Date.now()}`;
}

function generateRandomPhone(): string {
  const prefixes = ['138', '139', '187', '188', '189'];
  const prefix = prefixes[Math.floor(Math.random() * prefixes.length)];
  const suffix = Math.floor(Math.random() * 100000000).toString().padStart(8, '0');
  return prefix + suffix;
}

function formatDateTime(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hour = String(date.getHours()).padStart(2, '0');
  const minute = String(date.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day} ${hour}:${minute}`;
}

async function fillIfEmpty(locator: Locator, value: string): Promise<void> {
  if (!(await locator.count())) return;
  const target = locator.first();
  if (!(await target.isEditable().catch(() => false))) return;
  const currentValue = await target.inputValue().catch(() => '');
  const inputType = await target.getAttribute('type');
  if (inputType === 'email' && currentValue && !currentValue.includes('@')) {
    await target.fill(`${Date.now()}@example.com`);
    return;
  }
  if (!currentValue) {
    await target.fill(value);
  }
}

async function fillVisibleLeadFields(modal: Locator, name: string, phone: string): Promise<void> {
  const values = [
    name,
    `${name}科技有限公司`,
    '销售部',
    '销售经理',
  ];
  const genericFields = modal.locator('#content_undefined:visible');
  for (let i = 0; i < Math.min(values.length, await genericFields.count()); i++) {
    await fillIfEmpty(genericFields.nth(i), values[i]);
  }

  const knownFields: Array<[string, string]> = [
    ['[id="lead_address.tel"]:visible', `021-${phone.slice(-8)}`],
    ['[id="lead_address.phone"]:visible', phone],
    ['[id="lead_address.email"]:visible', `${phone}@example.com`],
    ['#lead_numeric_asset_3160c3:visible', '200'],
    ['#lead_numeric_asset_493a2f:visible', '1'],
    ['#lead_numeric_asset_63be61:visible', '0'],
    ['#lead_text_asset_71ce4b:visible', `线索摘要_${name}`],
    ['#lead_text_asset_33b4ba:visible', `field${Date.now()}@example.com`],
  ];
  for (const [selector, value] of knownFields) {
    await fillIfEmpty(modal.locator(selector), value);
  }

  const dateValues: Array<[string, string]> = [
    ['#lead_datetime_asset_5d3cd9:visible', formatDateTime(new Date())],
    ['#lead_datetime_asset_beca71:visible', formatDateTime(new Date(Date.now() + 86400000))],
    ['#lead_revisit_remind_at:visible', formatDateTime(new Date(Date.now() + 86400000))],
  ];
  for (const [selector, value] of dateValues) {
    await fillIfEmpty(modal.locator(selector), value);
  }

  // Fill any additional text fields exposed by this enterprise's template.
  const fields = modal.locator('input:visible, textarea:visible');
  const fieldCount = await fields.count();
  for (let i = 0; i < fieldCount; i++) {
    const field = fields.nth(i);
    const type = await field.getAttribute('type');
    const id = await field.getAttribute('id') || '';
    if (type === 'hidden' || type === 'search' || type === 'file' || id === 'lead_market_activity' || id === 'lead_source' || id.includes('datetime_asset') || id.includes('revisit_remind')) continue;
    if (!(await field.isEditable().catch(() => false))) continue;
    if ((await field.inputValue().catch(() => '')).trim()) continue;
    const value = type === 'number' || id.includes('numeric_asset') ? '1' : `自动化字段_${name}`;
    await field.fill(value);
  }
}

async function fillDateField(locator: Locator, value: string): Promise<void> {
  if (!(await locator.count())) return;
  const target = locator.first();
  if ((await target.inputValue().catch(() => '')).trim()) return;
  await target.click();
  await target.press('ControlOrMeta+a');
  await target.type(value);
  await target.press('Tab');
}

async function uploadLeadAttachments(modal: Locator): Promise<void> {
  const files = fs.readdirSync('/Users/mured/Pictures')
    .map(file => path.join('/Users/mured/Pictures', file))
    .filter(file => fs.statSync(file).isFile());
  const image = files.find(file => /\.(jpe?g|png|gif|webp)$/i.test(file));
  const attachment = files.find(file => !/\.(jpe?g|png|gif|webp)$/i.test(file)) || image;
  const inputs = modal.locator('input[type="file"]');
  const count = await inputs.count();
  if (count > 0 && attachment) await inputs.nth(0).setInputFiles(attachment);
  if (count > 1 && image) await inputs.nth(1).setInputFiles(image);
}

async function selectFirstOptionIfAvailable(page: Page, field: Locator): Promise<void> {
  if (!(await field.count())) return;
  const select = field.locator('xpath=ancestor::div[contains(@class, "ant-select")][1]');
  if (!(await select.count())) return;
  if (await select.locator('.ant-select-selection-item').count()) return;
  await select.click();
  await page.waitForTimeout(300);
  const options = page.locator('[role="option"]:visible');
  const optionCount = await options.count();
  for (let i = 0; i < optionCount; i++) {
    const option = options.nth(i);
    const label = (await option.innerText().catch(() => '')).trim();
    if (label && label !== '请选择' && label !== '全部') {
      await option.click();
      return;
    }
  }
}

async function selectRandomOptionsIfAvailable(page: Page, field: Locator, amount: number): Promise<void> {
  if (!(await field.count())) return;
  const select = field.locator('xpath=ancestor::div[contains(@class, "ant-select")][1]');
  if (!(await select.count())) return;
  await select.click();
  await page.waitForTimeout(300);
  const options = page.locator('[role="option"]:visible');
  const labels: string[] = [];
  for (let i = 0; i < await options.count(); i++) {
    const label = (await options.nth(i).innerText().catch(() => '')).trim();
    if (label && label !== '请选择' && label !== '全部') labels.push(label);
  }
  const selected = labels.sort(() => Math.random() - 0.5).slice(0, amount);
  for (const label of selected) {
    const option = page.getByRole('option', { name: label, exact: true });
    if (await option.count()) await option.click();
  }
  await page.keyboard.press('Escape');
}

async function selectLabeledOptions(page: Page, modal: Locator, label: string, amount: number): Promise<void> {
  const labelLocator = modal.getByText(label, { exact: true });
  if (!(await labelLocator.count())) return;
  const field = labelLocator.locator('xpath=../..')
    .locator('input[type="search"]:visible, [role="combobox"]:visible');
  if (await field.count()) await selectRandomOptionsIfAvailable(page, field, amount);
}

async function selectLabeledCascader(page: Page, modal: Locator, label: string, amount: number): Promise<void> {
  const labelLocator = modal.getByText(label, { exact: true });
  if (!(await labelLocator.count())) return;
  const field = labelLocator.locator('xpath=../..')
    .locator('input[type="search"]:visible, [role="combobox"]:visible');
  if (!(await field.count())) return;
  await field.click();
  await page.waitForTimeout(250);
  const parents = page.getByRole('menuitemcheckbox', { name: /right/ });
  const parentCount = await parents.count();
  if (!parentCount) return;
  await parents.nth(Math.floor(Math.random() * parentCount)).click();
  await page.waitForTimeout(200);
  const children = page.locator('[role="menuitemcheckbox"]:visible').filter({ hasNotText: 'right' });
  const childCount = await children.count();
  for (let i = 0; i < Math.min(amount, childCount); i++) await children.nth(i).click();
  await page.keyboard.press('Escape');
}

async function selectLabeledTreeOptions(page: Page, modal: Locator, label: string, amount: number): Promise<void> {
  const placeholder = modal.getByText(`请选择${label}`, { exact: true });
  if (!(await placeholder.count())) return;
  await placeholder.click();
  await page.waitForTimeout(250);
  const tree = page.getByRole('tree');
  if (!(await tree.count())) return;
  const checkboxes = tree.getByRole('checkbox');
  const checkboxCount = await checkboxes.count();
  if (checkboxCount) {
    for (let i = 0; i < Math.min(amount, checkboxCount); i++) await checkboxes.nth(i).check();
  } else {
    const switchers = tree.locator('.ant-tree-switcher');
    if (await switchers.count()) await switchers.first().click();
    await page.waitForTimeout(150);
    const treeCheckboxes = tree.locator('.ant-tree-checkbox');
    const treeCheckboxCount = await treeCheckboxes.count();
    const indexes = Array.from({ length: Math.max(0, treeCheckboxCount - 1) }, (_, i) => i + 1)
      .sort(() => Math.random() - 0.5)
      .slice(0, amount);
    for (const index of indexes) await treeCheckboxes.nth(index).click();
  }
  await page.keyboard.press('Escape');
}

async function fillLeadRegion(page: Page): Promise<void> {
  const regionField = page.locator('#lead_address_region_info');
  if (!(await regionField.count())) return;
  await regionField.click();
  await page.waitForTimeout(300);
  await page.getByText('中国', { exact: true }).click();
  await page.waitForTimeout(200);
  const province = Math.random() < 0.5 ? '上海' : '贵州';
  const provinceOption = page.getByText(province, { exact: true });
  if (!(await provinceOption.count())) return;
  await provinceOption.click();
  await page.waitForTimeout(200);
  const city = page.getByText(province === '上海' ? '徐汇' : '铜仁市', { exact: true });
  if (!(await city.count())) return;
  await city.click();
  await page.waitForTimeout(200);
  const district = page.getByRole('menuitemcheckbox', { name: province === '上海' ? '徐汇' : '沿河土家族自治县' });
  if (await district.count()) await district.click();
  await page.keyboard.press('Escape');
}

// ===================== 页面操作函数 =====================

async function login(page: Page): Promise<void> {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.locator('#account').fill(process.env.TEST_USERNAME || '18217038858');
  await page.locator('#password').fill(process.env.TEST_PASSWORD || 'Ik123456');
  const checkboxes = page.getByRole('checkbox');
  for (let i = 0; i < await checkboxes.count(); i++) {
    const checkbox = checkboxes.nth(i);
    if (!(await checkbox.isChecked())) await checkbox.check();
  }
  await page.getByRole('button', { name: '登 录' }).click();
  await expect(page.locator('#account')).toBeHidden({ timeout: 30000 });
  await page.waitForURL(/.*workbench/, { timeout: 30000 });
  await page.waitForLoadState('networkidle');

  const reloadSession = page.getByText('重新加载', { exact: true });
  if (await reloadSession.isVisible().catch(() => false)) {
    await reloadSession.click();
    await page.waitForLoadState('networkidle');
  }
  const organizationLink = page.locator('a[href="/"]').first();
  await expect(organizationLink).toBeVisible();
  await expect(organizationLink).toContainText('独立版回归企业');
}

async function selectCustomerAndContact(page: Page): Promise<void> {
  const customerField = page.locator('#customer_customer');
  await customerField.click();
  const customerOption = page.getByRole('option').first();
  const customerName = await customerOption.getAttribute('aria-label');
  if (!customerName) throw new Error('客户下拉没有可用选项');
  await page.getByText(customerName, { exact: true }).last().click();

  const newContact = page.getByRole('checkbox', { name: '新增联系人' });
  await newContact.check();
  const contactNameInput = page.getByRole('textbox', { name: '请输入姓名' }).first();
  if (await contactNameInput.isVisible().catch(() => false)) {
    await contactNameInput.fill(generateRandomName('联系人'));
  } else {
    await page.getByRole('textbox').last().fill(generateRandomName('联系人'));
  }
  const phoneInputs = await page.getByRole('textbox', { name: '请输入手机' }).all();
  if (phoneInputs.length) {
    await phoneInputs[phoneInputs.length - 1].fill(generateRandomPhone());
  }
}

// 选择市场活动：有数据随机选一行，无数据直接点确定关闭弹窗
async function selectLeadMarketActivity(page: Page): Promise<void> {
  const selectButton = page.getByText('选择', { exact: true }).first();
  if (!(await selectButton.count())) return;
  await selectButton.click();
  const activityModal = page.locator('.lxy-modal-wrap')
    .filter({ hasText: '请选择对应市场活动' }).last();
  await expect(activityModal).toBeVisible();
  await page.waitForTimeout(500);

  const rows = activityModal.locator('table tbody tr');
  const rowCount = await rows.count();
  if (rowCount > 0) {
    await rows.nth(Math.floor(Math.random() * rowCount)).click();
  }
  // 点击弹窗右下角的确定按钮
  await activityModal.getByRole('button', { name: '确定' }).click();
  await page.waitForTimeout(500);
}

async function selectLeadSourceIfAvailable(page: Page): Promise<void> {
  const sourceField = page.locator('#lead_source');
  if (!(await sourceField.count())) return;
  await selectFirstOptionIfAvailable(page, sourceField);
}

// 点击新增线索并等待表单加载完成
async function clickAddLead(page: Page): Promise<void> {
  await page.getByText(/^新增线索/).first().click();
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(3000);
  // 等待名称输入框出现（id 固定为 content_undefined）
  await page.locator('#content_undefined').first().waitFor({ state: 'attached', timeout: 15000 }).catch(() => {});
}

// 创建线索
async function createLead(page: Page, name: string, phone: string): Promise<void> {
  await page.getByRole('link', { name: '线索' }).first().click();
  await page.waitForLoadState('networkidle');
  await clickAddLead(page);
  await page.waitForLoadState('networkidle');

  const modal = page.locator('.lxy-modal-wrap:visible').last();
  await selectLeadMarketActivity(page);
  await selectLeadSourceIfAvailable(page);
  const expandMore = page.getByText('展开更多信息', { exact: true }).first();
  if (await expandMore.count()) await expandMore.click();
  await fillVisibleLeadFields(modal, name, phone);
  await fillLeadRegion(page);
  await fillDateField(modal.locator('#lead_datetime_asset_beca71:visible'), formatDateTime(new Date()));
  await fillDateField(modal.locator('#lead_revisit_remind_at:visible'), formatDateTime(new Date(Date.now() + 31 * 86400000)));
  await uploadLeadAttachments(modal);
  await selectFirstOptionIfAvailable(page, page.locator('#lead_status'));
  await selectLabeledOptions(page, modal, '新增单选下拉', 1);
  await selectLabeledOptions(page, modal, '新增多选下拉', 2);
  await selectLabeledTreeOptions(page, modal, '新增用户单选', 1);
  await selectLabeledTreeOptions(page, modal, '新增用户多选', 2);
  await selectLabeledTreeOptions(page, modal, '新增部门单选', 1);
  await selectLabeledTreeOptions(page, modal, '新增部门多选', 2);
  await selectLabeledOptions(page, modal, '客户类型', 1);
  await selectLabeledOptions(page, modal, '所属行业', 1);
  await selectLabeledCascader(page, modal, '新增级联', 1);
  await selectLabeledCascader(page, modal, '级联多选', 2);
  await selectFirstOptionIfAvailable(page, page.locator('#lead_custom_relation_asset_4bed23'));
  await selectFirstOptionIfAvailable(page, page.locator('#lead_user'));
  await selectFirstOptionIfAvailable(page, page.locator('#lead_owned_department'));
  const saveButton = page.getByText('保存', { exact: true }).last();
  await expect(saveButton).toBeVisible();
  await saveButton.click();
  await expect(page.locator('.lxy-modal-mask:visible')).toHaveCount(0, { timeout: 15000 });
  await page.waitForLoadState('networkidle').catch(() => {});
}

// 选择下月25日
async function pickNextMonthDay25(page: Page): Promise<void> {
  // 直接点击日期输入框，然后用键盘输入
  await page.locator('#opportunity_expect_sign_date').click();
  await page.waitForTimeout(500);
  // 清除已有的日期
  await page.locator('#opportunity_expect_sign_date').fill('');
  // 直接输入下个月的日期 2026/08/25
  const now = new Date();
  let month = now.getMonth() + 2; // 当前7月→8月 (getMonth() 0-indexed: 6→7)
  let year = now.getFullYear();
  if (month > 11) { month = 0; year += 1; }
  const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-25`;
  await page.locator('#opportunity_expect_sign_date').fill(dateStr);
  // 点击其他地方关闭日期选择器
  await page.keyboard.press('Tab');
  await page.waitForTimeout(300);
}

// 从线索列表进入详情并执行转换
async function convertLead(page: Page, leadName: string, action: '转成新客户' | '转成已有客户'): Promise<void> {
  await page.getByRole('link', { name: '线索' }).first().click();
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(2000);
  await page.getByText(leadName, { exact: true }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(2000);
  await page.getByRole('tab', { name: '基本信息' }).click();
  await page.waitForTimeout(2000);
  await page.getByRole('button', { name: '转换' }).click();
  await page.waitForTimeout(1000);
  await page.getByText(new RegExp(`^${action}`)).last().click();
  await page.waitForTimeout(1000);
  const nextButton = page.getByRole('button', { name: '下一步' });
  if (await nextButton.isVisible().catch(() => false)) {
    await nextButton.click();
    await page.waitForTimeout(1000);
  }
}

// 从详情页删除创建时间最早的一条已通过数据
async function deleteEarliestApprovedLead(page: Page): Promise<void> {
  await page.getByRole('link', { name: '线索' }).first().click();
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(2000);

  // 筛选已通过
  const approvalFilter = page.locator('[title="审批状态"]').first();
  if (await approvalFilter.count()) {
    await approvalFilter.locator('xpath=following-sibling::*[1]').click();
    await page.waitForTimeout(300);
    await page.getByText('已通过', { exact: true }).last().click();
    await page.waitForTimeout(2000);
  }

  // 取当前页创建时间最早（最后一行）的已通过线索，进入详情页
  const rows = page.locator('.lxt-table-row');
  await expect(rows.first()).toBeVisible({ timeout: 10000 });
  const rowCount = await rows.count();
  const lastRow = rows.nth(rowCount - 1);
  const leadLink = lastRow.locator('[class*="cell"] a, [class*="cell"] span, td a').first();
  const leadText = await leadLink.innerText().catch(() => '');
  if (!leadText) throw new Error('未找到可删除的已通过线索');
  await leadLink.click();
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(2000);

  // 在详情页点"更多"→"删除"
  await page.getByRole('button', { name: '更多', exact: true }).click();
  await page.waitForTimeout(500);

  // 删除按钮可能在菜单列表中，匹配文本"删除"
  const deleteAction = page.getByText('删除', { exact: true }).last();
  if (await deleteAction.isVisible().catch(() => false)) {
    await deleteAction.click();
    await page.waitForTimeout(500);
  }

  // 确认删除
  const confirmBtn = page.getByRole('button', { name: '确定' });
  if (await confirmBtn.isVisible().catch(() => false)) {
    await confirmBtn.click();
  }
  await page.waitForLoadState('networkidle');
}

// ===================== 测试配置 =====================

test.use({
  baseURL: process.env.CRM_BASE_URL || 'https://lxcrm-staging.weiwenjia.com',
  screenshot: 'only-on-failure',
  video: 'retain-on-failure',
  viewport: null,
  launchOptions: {
    args: ['--start-maximized'],
  },
});

test.setTimeout(300000);

// ===================== 主测试套件 =====================

test.describe('CRM线索管理', () => {

  test('线索完整流程：创建-查看-转客户-编辑-删除', async ({ page }) => {
    await test.step('登录系统', async () => {
      await login(page);
    });

    // ===================== 线索1：转客户 =====================
    const leadNameForConvert = generateRandomName('测试线索');
    const phoneForConvert = generateRandomPhone();

    await test.step('创建线索（用于转客户）', async () => {
      await createLead(page, leadNameForConvert, phoneForConvert);
      await page.screenshot({ path: 'test-results/leads-created-success.png' });
    });

    const customerName = generateRandomName('客户');
    const contactName = generateRandomName('联系人');
    const contactPhone = generateRandomPhone();

    await test.step('查看线索详情', async () => {
      await page.getByRole('link', { name: '线索' }).first().click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      const leadSearch = page.getByRole('textbox', { name: '请输入搜索内容', exact: true });
      if (await leadSearch.count()) {
        await leadSearch.fill(leadNameForConvert);
        await page.keyboard.press('Enter');
        await page.waitForTimeout(2000);
      }
      await page.getByText(leadNameForConvert, { exact: true }).click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'test-results/leads-detail.png' });
    });

    await test.step('线索转客户', async () => {
      await page.getByRole('tab', { name: '基本信息' }).click();
      await page.waitForTimeout(2000);
      await page.getByRole('button', { name: '转换' }).click();
      await page.waitForTimeout(1000);
      await page.getByText(/^转成新客户/).last().click();
      await page.waitForTimeout(1000);
      const nextButton = page.getByRole('button', { name: '下一步' });
      if (await nextButton.isVisible().catch(() => false)) {
        await nextButton.click();
        await page.waitForTimeout(1000);
      }
      const conversionForm = page.locator('.lxy-modal-wrap')
        .filter({ hasText: '客户2信息' }).last();
      await expect(conversionForm).toBeVisible();

      await conversionForm.getByRole('textbox').first().fill(customerName);
      await conversionForm.getByText('展开更多信息', { exact: true }).first().click();
      await page.waitForTimeout(300);

      // 选择地区
      await page.locator('#customer_address_region_info').click();
      await page.waitForTimeout(300);
      await page.getByText('中国', { exact: true }).click();
      await page.waitForTimeout(300);
      await page.getByText('贵州').click();
      await page.getByText('铜仁市').click();
      await page.getByRole('menuitemcheckbox', { name: '沿河土家族自治县' }).click();

      // 选择上级客户
      await page.locator('#customer_parent').click();
      await page.waitForTimeout(500);
      const parentOptions = page.getByRole('option');
      const parentOptionCount = await parentOptions.count();
      if (parentOptionCount) {
        await parentOptions.nth(parentOptionCount > 1 ? 1 : 0).click({ force: true }).catch(() => {});
      }

      await page.locator('#customer_status').click();
      await page.waitForTimeout(300);
      await page.getByText('初访').click();
      await page.locator('#customer_industry').click();
      await page.waitForTimeout(300);
      await page.getByText('金融').click();
      await page.locator('#customer_staff_size').click();
      await page.waitForTimeout(300);
      await page.getByText('-20人').click();

      const formInputs = conversionForm.locator('input');
      const contactNameIndex = await formInputs.evaluateAll(
        (inputs, name) => inputs.findIndex(input => (input as HTMLInputElement).value === name),
        leadNameForConvert,
      );
      if (contactNameIndex < 0) throw new Error('转换表单没有找到联系人姓名输入框');
      await formInputs.nth(contactNameIndex).fill(contactName);
      await conversionForm.getByText('展开更多信息', { exact: true }).last().click();
      await page.waitForTimeout(300);
      const contactPhoneLabel = conversionForm.getByText('手机', { exact: true }).last();
      const contactPhoneInput = contactPhoneLabel.locator('xpath=..').locator('input').first();
      if (await contactPhoneInput.count()) await contactPhoneInput.fill(contactPhone);

      await page.getByRole('button', { name: '保存' }).click();
      await page.waitForLoadState('networkidle');
      await page.screenshot({ path: 'test-results/leads-convert-success.png' });
    });

    await test.step('验证客户创建成功', async () => {
      await page.getByRole('link', { name: '客户' }).first().click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      await page.getByRole('textbox', { name: '请输入搜索内容', exact: true }).fill(customerName);
      await page.keyboard.press('Enter');
      await page.waitForTimeout(3000);
      await expect(page.getByText(customerName)).toBeVisible();
      await page.screenshot({ path: 'test-results/customer-created-verified.png' });
    });

    // ===================== 线索2：编辑 + 删除 =====================
    const leadNameForEdit = generateRandomName('测试线索');
    const phoneForEdit = generateRandomPhone();

    await test.step('创建线索（用于编辑删除）', async () => {
      await createLead(page, leadNameForEdit, phoneForEdit);
    });

    let editedLeadName = leadNameForEdit;
    await test.step('编辑线索', async () => {
      await page.getByRole('link', { name: '线索' }).first().click();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);

      const approvalFilter = page.locator('[title="审批状态"]').first();
      if (await approvalFilter.count()) {
        await approvalFilter.locator('xpath=following-sibling::*[1]').click();
        await page.waitForTimeout(300);
        await page.getByText('已通过', { exact: true }).last().click();
        await page.waitForTimeout(1500);
      }
      const approvedLead = page.getByText(/^测试线索_/).first();
      await expect(approvedLead).toBeVisible();
      editedLeadName = (await approvedLead.innerText()).trim();
      await approvedLead.click();
      await page.waitForTimeout(2000);

      await page.getByRole('button', { name: '更多', exact: true }).click();
      await page.getByRole('tab', { name: '基本信息' }).click();
      await page.getByRole('button', { name: '更多', exact: true }).click();
      await page.getByRole('button', { name: '编辑', exact: true }).click();
      const editModal = page.locator('.lxy-modal-wrap:visible')
        .filter({ hasText: '编辑线索' }).last();
      await expect(editModal).toBeVisible();
      editedLeadName = generateRandomName('测试线索');
      await editModal.locator('#content_undefined').first().fill(editedLeadName);
      await editModal.getByRole('button', { name: '保存' }).click();
      await page.waitForLoadState('networkidle');
      await page.screenshot({ path: 'test-results/leads-edit-success.png' });
    });

    await test.step('删除线索（从详情页删除最早的已通过数据）', async () => {
      await deleteEarliestApprovedLead(page);
      await page.screenshot({ path: 'test-results/leads-delete-success.png' });
    });

    // ===================== 线索3：转已有客户 =====================
    const leadNameForExisting = generateRandomName('测试线索');
    const phoneForExisting = generateRandomPhone();
    const opportunityTitle = `商机_${Date.now()}`;

    await test.step('创建线索（用于转已有客户）', async () => {
      await createLead(page, leadNameForExisting, phoneForExisting);
    });

    await test.step('线索转已有客户', async () => {
      await convertLead(page, leadNameForExisting, '转成已有客户');
      await selectCustomerAndContact(page);
      await page.waitForTimeout(500);
      await page.getByRole('checkbox', { name: /^同步创建商机/ }).check();
      await page.waitForTimeout(300);
      await page.locator('#content_undefined').last().fill(opportunityTitle);
      await page.locator('#opportunity_expect_amount').fill('1000');
      await page.waitForTimeout(300);
      const opportunityStage = page.locator('#opportunity_stage');
      if (await opportunityStage.isVisible().catch(() => false)) {
        await opportunityStage.click();
        await page.waitForTimeout(300);
        await page.getByText('需求确定', { exact: true }).last().click();
        await page.waitForTimeout(300);
      }
      await pickNextMonthDay25(page);
      await page.getByRole('button', { name: '保存' }).click();
      await page.waitForTimeout(2000);
      // 等待弹窗关闭（遮罩层消失）
      await page.locator('.lxy-modal-mask').waitFor({ state: 'hidden', timeout: 10000 }).catch(() => {});
      await page.screenshot({ path: 'test-results/leads-convert-existing-success.png' });
    });

    await test.step('验证商机创建成功', async () => {
      await page.getByRole('link', { name: /^商机/ }).first().click({ force: true });
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(3000);
      await page.getByRole('textbox', { name: '请输入搜索内容', exact: true }).fill(opportunityTitle);
      await page.keyboard.press('Enter');
      await page.waitForTimeout(3000);
      await expect(page.locator(`text=${opportunityTitle}`).first()).toBeVisible();
      await page.screenshot({ path: 'test-results/opportunity-created-verified.png' });
    });
  });
});

// ===================== 单独测试：线索转已有客户 =====================

test.describe('线索转已有客户', () => {
  test('线索转已有客户流程', async ({ page }) => {
    await test.step('登录系统', async () => {
      await login(page);
    });

    const leadNameForExisting = generateRandomName('测试线索');
    const phoneForExisting = generateRandomPhone();
    const opportunityTitle = `商机_${Date.now()}`;

    await test.step('创建线索', async () => {
      await createLead(page, leadNameForExisting, phoneForExisting);
    });

    await test.step('线索转已有客户', async () => {
      await convertLead(page, leadNameForExisting, '转成已有客户');
      await selectCustomerAndContact(page);
      await page.waitForTimeout(500);
      await page.getByRole('checkbox', { name: /^同步创建商机/ }).check();
      await page.waitForTimeout(300);
      await page.locator('#content_undefined').last().fill(opportunityTitle);
      await page.locator('#opportunity_expect_amount').fill('1000');
      await page.waitForTimeout(300);
      const opportunityStage = page.locator('#opportunity_stage');
      if (await opportunityStage.isVisible().catch(() => false)) {
        await opportunityStage.click();
        await page.waitForTimeout(300);
        await page.getByText('需求确定', { exact: true }).last().click();
        await page.waitForTimeout(300);
      }
      await pickNextMonthDay25(page);
      await page.getByRole('button', { name: '保存' }).click();
      await page.waitForTimeout(2000);
      // 等待弹窗关闭（遮罩层消失）
      await page.locator('.lxy-modal-mask').waitFor({ state: 'hidden', timeout: 10000 }).catch(() => {});
      await page.screenshot({ path: 'test-results/leads-convert-existing-success.png' });
    });

    await test.step('验证商机创建成功', async () => {
      await page.getByRole('link', { name: /^商机/ }).first().click({ force: true });
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(3000);
      await page.getByRole('textbox', { name: '请输入搜索内容', exact: true }).fill(opportunityTitle);
      await page.keyboard.press('Enter');
      await page.waitForTimeout(3000);
      await expect(page.locator(`text=${opportunityTitle}`).first()).toBeVisible();
      await page.screenshot({ path: 'test-results/opportunity-created-verified.png' });
    });
  });
});
