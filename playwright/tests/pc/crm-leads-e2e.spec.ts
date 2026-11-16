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

function nextMonthSameDay(): Date {
  const current = new Date();
  const next = new Date(current);
  next.setDate(1);
  next.setMonth(next.getMonth() + 1);
  const lastDay = new Date(next.getFullYear(), next.getMonth() + 1, 0).getDate();
  next.setDate(Math.min(current.getDate(), lastDay));
  return next;
}

async function waitForSelectOptions(page: Page): Promise<Locator> {
  const options = page.locator('[role="option"]:visible, .ant-select-item-option:visible, .ant-select-dropdown-menu-item:visible');
  for (let attempt = 0; attempt < 10; attempt += 1) {
    if (await options.count()) return options;
    await page.waitForTimeout(500);
  }
  return options;
}

async function fillIfEmpty(locator: Locator, value: string): Promise<void> {
  if (!(await locator.count())) return;
  const target = locator.first();
  if (await target.getAttribute('readonly')) return;
  if (!(await target.isEditable().catch(() => false))) return;
  const currentValue = await target.inputValue().catch(() => '');
  if (!currentValue) {
    await target.fill(value);
  }
}

async function fillField(locator: Locator, value: string): Promise<void> {
  if (!(await locator.count())) return;
  const target = locator.first();
  if (await target.getAttribute('readonly')) return;
  if (!(await target.isEditable().catch(() => false))) return;
  await target.fill(value);
}

async function getFieldContext(field: Locator): Promise<string> {
  return field.evaluate((element) => {
    const texts: string[] = [];
    let node: HTMLElement | null = element.parentElement;
    for (let depth = 0; node && depth < 8; depth += 1, node = node.parentElement) {
      texts.push(node.textContent || '');
    }
    return texts.join('|');
  }).catch(() => '');
}

async function fillVisibleLeadFields(modal: Locator, name: string, phone: string): Promise<void> {
  const genericValues = [name, `${name}科技有限公司`, '销售部', '销售经理'];
  const genericFields = modal.locator('#content_undefined:visible');
  for (let i = 0; i < Math.min(genericValues.length, await genericFields.count()); i++) {
    await fillIfEmpty(genericFields.nth(i), genericValues[i]);
  }
  if (!(await genericFields.count())) {
    const fallbackFields = modal.locator('input:visible, textarea:visible');
    let fallbackIndex = 0;
    for (let i = 0; i < await fallbackFields.count() && fallbackIndex < genericValues.length; i++) {
      const field = fallbackFields.nth(i);
      const type = await field.getAttribute('type');
      const id = await field.getAttribute('id') || '';
      if (['hidden', 'search', 'file', 'checkbox', 'radio'].includes(type || '') || id.includes('datetime_asset') || id.includes('revisit_remind')) continue;
      if (!(await field.isEditable().catch(() => false)) || (await field.inputValue().catch(() => '')).trim()) continue;
      await field.fill(genericValues[fallbackIndex++]);
    }
  }

  const fields: Array<[string, string]> = [
    ['[id="lead_address.tel"]:visible', `021-${phone.slice(-8)}`],
    ['[id="lead_address.phone"]:visible', phone],
    ['[id="lead_address.email"]:visible', `${phone}@163.com`],
    ['[id="lead_address.url"]:visible', 'www.baidu.com'],
    ['#lead_numeric_asset_3160c3:visible', '200'],
    ['#lead_numeric_asset_493a2f:visible', '1'],
    ['#lead_numeric_asset_63be61:visible', '0'],
  ];
  for (const [selector, value] of fields) await fillIfEmpty(modal.locator(selector), value);

  const dateFields: Array<[string, string]> = [
    ['#lead_datetime_asset_5d3cd9:visible', formatDateTime(new Date())],
    ['#lead_datetime_asset_beca71:visible', formatDateTime(new Date(Date.now() + 86400000))],
    ['#lead_revisit_remind_at:visible', formatDateTime(new Date(Date.now() + 86400000))],
  ];
  for (const [selector, value] of dateFields) await fillIfEmpty(modal.locator(selector), value);

  const editableFields = modal.locator('input:visible, textarea:visible');
  for (let i = 0; i < await editableFields.count(); i++) {
    const field = editableFields.nth(i);
    const type = await field.getAttribute('type');
    const id = await field.getAttribute('id') || '';
    if (type === 'hidden' || type === 'search' || type === 'file' || type === 'checkbox' || type === 'radio' || id === 'lead_market_activity' || id === 'lead_source' || id.includes('datetime_asset') || id.includes('revisit_remind')) continue;
    if (!(await field.isEditable().catch(() => false)) || (await field.inputValue().catch(() => '')).trim()) continue;
    const context = await getFieldContext(field);
    const value = type === 'email' || context.includes('邮箱')
      ? `${Date.now()}@163.com`
      : id.includes('url') || context.includes('链接') || context.includes('网址')
        ? 'www.baidu.com'
        : type === 'number' || id.includes('numeric_asset') ? '1' : `自动化字段_${name}`;
    await fillField(field, value);
  }
}

async function fillDateField(locator: Locator, value: string): Promise<void> {
  if (!(await locator.count())) return;
  const target = locator.first();
  if ((await target.inputValue().catch(() => '')).trim()) return;
  if (await target.isEditable().catch(() => false)) {
    await target.fill(value);
    await target.press('Tab').catch(() => {});
  } else {
    await target.evaluate((element, nextValue) => {
      const input = element as HTMLInputElement;
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
      setter?.call(input, nextValue);
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }, value);
  }
}

async function fillLabeledDateField(page: Page, modal: Locator, label: string, value: string): Promise<void> {
  const labels = modal.getByText(label, { exact: true });
  for (let index = 0; index < await labels.count(); index += 1) {
    const labelNode = labels.nth(index);
    if (!(await labelNode.isVisible().catch(() => false))) continue;
    const container = labelNode.locator('xpath=ancestor::div[.//input][1]');
    const input = container.locator('input:visible').first();
    if (await input.count()) {
      await input.click({ force: true });
      await page.waitForTimeout(300);
      await fillDateField(input, value);
      const confirm = page.getByRole('button', { name: '确 定', exact: true }).filter({ visible: true }).last();
      if (await confirm.count()) await confirm.click({ force: true, timeout: 3000 }).catch(() => {});
      return;
    }
  }
}

async function selectLabeledDateToday(page: Page, modal: Locator, label: string): Promise<void> {
  const labels = modal.getByText(label, { exact: true });
  for (let index = 0; index < await labels.count(); index += 1) {
    const labelNode = labels.nth(index);
    if (!(await labelNode.isVisible().catch(() => false))) continue;
    const container = labelNode.locator('xpath=ancestor::div[.//input][1]');
    const input = container.locator('input:visible').first();
    if (!(await input.count())) continue;
    await input.click({ force: true });
    await page.waitForTimeout(300);
    const today = page.getByText('今天', { exact: true }).filter({ visible: true }).last();
    if (await today.count()) await today.click({ force: true, timeout: 3000 }).catch(() => {});
    return;
  }
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
  const select = field.first().locator('xpath=ancestor::*[contains(@class, "ant-select")][1]');
  const trigger = field.first();
  if (!(await trigger.count())) return;
  if (await select.locator('.ant-select-selection-item').count()) return;
  await trigger.click({ force: true });
  const options = await waitForSelectOptions(page);
  const optionCount = await options.count();
  if (!optionCount) {
    await field.first().focus().catch(() => {});
    await field.first().press('ArrowDown', { timeout: 2000 }).catch(() => {});
    await field.first().press('Enter', { timeout: 2000 }).catch(() => {});
    await trigger.press('ArrowDown', { timeout: 2000 }).catch(() => {});
    await trigger.press('Enter', { timeout: 2000 }).catch(() => {});
    return;
  }
  for (let i = 0; i < optionCount; i++) {
    const option = options.nth(i);
    const label = (await option.innerText().catch(() => '')).trim();
    if (label && label !== '请选择' && label !== '全部') {
      await option.click({ timeout: 3000 }).then(() => undefined).catch(() => {});
      if (!(await option.isVisible().catch(() => false))) return;
    }
  }
}

async function selectRandomOptionsIfAvailable(page: Page, field: Locator, amount: number): Promise<void> {
  if (!(await field.count())) return;
  const select = field.first().locator('xpath=ancestor::*[contains(@class, "ant-select")][1]');
  const trigger = field.first();
  if (!(await trigger.count())) return;
  await trigger.click({ force: true });
  const options = await waitForSelectOptions(page);
  const optionIndexes: number[] = [];
  for (let i = 0; i < await options.count(); i++) {
    const label = (await options.nth(i).innerText().catch(() => '')).trim();
    if (label && label !== '请选择' && label !== '全部') optionIndexes.push(i);
  }
  if (!optionIndexes.length) {
    for (let index = 0; index < amount; index += 1) {
      await field.first().focus().catch(() => {});
      await field.first().press('ArrowDown', { timeout: 2000 }).catch(() => {});
      await field.first().press('Enter', { timeout: 2000 }).catch(() => {});
      await trigger.press('ArrowDown', { timeout: 2000 }).catch(() => {});
      await trigger.press('Enter', { timeout: 2000 }).catch(() => {});
    }
    await page.keyboard.press('Escape');
    return;
  }
  const selected = optionIndexes.sort(() => Math.random() - 0.5).slice(0, amount);
  for (const index of selected) await options.nth(index).click();
  if (await page.locator('[role="option"]:visible').count()) await page.keyboard.press('Escape');
}

async function findLabeledControl(modal: Locator, label: string): Promise<Locator | null> {
  const labels = modal.getByText(label, { exact: true });
  for (let index = 0; index < await labels.count(); index += 1) {
    const labelNode = labels.nth(index);
    if (!(await labelNode.isVisible().catch(() => false))) continue;
    const fieldWrapper = labelNode.locator('xpath=parent::*').locator('xpath=following-sibling::*[1]');
    const siblingControl = fieldWrapper.locator('input[type="search"]:visible, [role="combobox"]:visible').first();
    if (await siblingControl.count()) return siblingControl;
    const siblingPlaceholder = fieldWrapper.getByText(`请选择${label}`, { exact: true });
    if (await siblingPlaceholder.count()) return fieldWrapper;
    const container = labelNode.locator('xpath=ancestor::div[.//input or .//*[@role="combobox"]][1]');
    const control = container.locator('input[type="search"]:visible, [role="combobox"]:visible').first();
    if (await control.count()) return control;
  }
  const placeholder = modal.getByText(`请选择${label}`, { exact: true });
  for (let index = 0; index < await placeholder.count(); index += 1) {
    if (await placeholder.nth(index).isVisible().catch(() => false)) return placeholder.nth(index);
  }
  return null;
}

async function selectLabeledOptions(page: Page, modal: Locator, label: string, amount: number): Promise<void> {
  const field = await findLabeledControl(modal, label);
  if (field) {
    await selectRandomOptionsIfAvailable(page, field, amount);
  }
}

async function selectLabeledCascader(page: Page, modal: Locator, label: string, amount: number): Promise<void> {
  const field = await findLabeledControl(modal, label);
  if (!field) return;
  await field.click();
  await page.waitForTimeout(250);
  const menus = page.locator('.ant-cascader-menu:visible');
  for (let level = 0; level < 3; level += 1) {
    const limit = level === 2 ? amount : 1;
    for (let index = 0; index < limit; index += 1) {
      const options = menus.last().locator('.ant-cascader-menu-item:visible');
      const optionCount = await options.count();
      if (!optionCount) break;
      await options.nth(Math.floor(Math.random() * optionCount))
        .click({ timeout: 5000 })
        .catch(() => {});
      await page.waitForTimeout(200);
    }
  }
  if (await menus.count()) await page.keyboard.press('Escape');
}

async function selectLabeledTreeOptions(page: Page, modal: Locator, label: string, amount: number): Promise<void> {
  const field = await findLabeledControl(modal, label);
  if (!field) return;
  await field.click();
  await page.waitForTimeout(250);
  const tree = page.locator('[role="tree"]:visible, .ant-tree:visible').last();
  if (!(await tree.count())) {
    const names = label.includes('用户')
      ? ['徐弘', '王乐']
      : ['部门1', '部门3'];
    const selectedNames = names.slice(0, amount);
    for (const name of selectedNames) {
      const option = page.getByText(name, { exact: true }).filter({ visible: true }).last();
      if (await option.count()) await option.click();
      await page.waitForTimeout(150);
    }
    const confirm = page.getByRole('button', { name: '确定', exact: true }).filter({ visible: true }).last();
    if (await confirm.count()) await confirm.click();
    else await page.keyboard.press('Escape');
    return;
  }
  const checkboxes = tree.locator('.ant-tree-checkbox:visible');
  const checkboxCount = await checkboxes.count();
  if (checkboxCount) {
    const start = checkboxCount > amount ? 1 : 0;
    const indexes = Array.from({ length: checkboxCount - start }, (_, index) => index + start)
      .sort(() => Math.random() - 0.5)
      .slice(0, amount);
    for (const index of indexes) await checkboxes.nth(index).click();
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
  await page.waitForTimeout(150);
  if (await tree.isVisible().catch(() => false)) await field.click({ force: true }).catch(() => {});
}

async function fillLeadRegion(page: Page): Promise<void> {
  const regionField = page.locator('#lead_address_region_info');
  if (!(await regionField.count())) return;
  await regionField.click();
  const popup = page.locator('.ant-cascader-dropdown:visible, .ant-picker-dropdown:visible').last();
  await popup.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
  const visibleText = page.locator('text=中国:visible').last();
  if (await visibleText.count()) {
    await visibleText.click();
    await page.waitForTimeout(250);
  }
  for (let level = 0; level < 3; level += 1) {
    const menus = page.locator('.ant-cascader-menu:visible').last();
    const options = menus.locator('.ant-cascader-menu-item:visible');
    const optionCount = await options.count();
    if (!optionCount) break;
    const index = Math.floor(Math.random() * Math.min(5, optionCount));
    const option = options.nth(index);
    await option.scrollIntoViewIfNeeded({ timeout: 3000 }).catch(() => {});
    await option.click({ force: true, timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(250);
  }
  await expect(regionField).not.toHaveValue('请选择地区', { timeout: 3000 }).catch(() => {});
}

// ===================== 页面操作函数 =====================

async function login(page: Page): Promise<void> {
  for (let attempt = 1; attempt <= 5; attempt += 1) {
    await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await expect(page.locator('#account')).toBeVisible({ timeout: 30000 });
    await page.locator('#account').fill(process.env.TEST_USERNAME || '18217038858');
    await page.locator('#password').fill(process.env.TEST_PASSWORD || 'Ik123456');
    const checkboxes = page.locator('input[type="checkbox"]');
    for (let index = 0; index < await checkboxes.count(); index += 1) {
      const checkbox = checkboxes.nth(index);
      for (let retry = 0; retry < 3 && !(await checkbox.isChecked()); retry += 1) {
        await checkbox.click({ force: true });
        if (!(await checkbox.isChecked())) await checkbox.locator('xpath=..').click({ force: true });
        await page.waitForTimeout(150);
      }
      await expect(checkbox).toBeChecked({ timeout: 3000 });
    }
    await page.waitForTimeout(1000);
    await page.getByRole('button', { name: '登 录' }).click({ force: true });

    const dashboardReady = page.locator('main').first().waitFor({ state: 'visible', timeout: 20000 })
      .then(() => true).catch(() => false);
    const workbenchReady = page.waitForURL(/.*workbench/, { timeout: 20000 })
      .then(() => true).catch(() => false);
    if (await Promise.race([dashboardReady, workbenchReady])) {
      await page.waitForLoadState('domcontentloaded').catch(() => {});
      await page.waitForTimeout(1500);
      break;
    }
    if (attempt === 5) {
      throw new Error(`登录失败，连续 ${attempt} 次未进入 CRM，页面提示：${(await page.locator('body').innerText()).slice(0, 300)}`);
    }
    await page.waitForTimeout(1500);
  }

  for (let attempt = 0; attempt < 3; attempt += 1) {
    const reloadSession = page.getByText('重新加载', { exact: true }).last();
    if (!(await reloadSession.isVisible().catch(() => false))) break;
    await reloadSession.click();
    await page.waitForLoadState('domcontentloaded').catch(() => {});
    await page.waitForTimeout(1500);
  }
  await expect(page.locator('main').first()).toBeVisible({ timeout: 30000 });
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
  await page.waitForTimeout(300);

  const rows = activityModal.locator('table tbody tr');
  let rowCount = 0;
  for (let attempt = 0; attempt < 10 && rowCount === 0; attempt += 1) {
    rowCount = await rows.count();
    if (rowCount === 0) await page.waitForTimeout(500);
  }
  if (rowCount > 0) {
    const row = rows.nth(Math.floor(Math.random() * rowCount));
    const choice = row.locator('.lxy-radio-wrap, .ant-radio-wrapper, .ant-checkbox-wrapper').first();
    if (await choice.count()) {
      await choice.click({ force: true });
      const input = row.locator('input[type="checkbox"], input[type="radio"]').first();
      if (await input.count() && !(await input.isChecked().catch(() => false))) {
        await row.locator('.lxy-radio-dot').click({ force: true }).catch(() => {});
      }
    }
    else await row.click();
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

// 点击可见新增入口，并确认当前新增弹窗已经打开
async function clickAddLead(page: Page): Promise<Locator> {
  const addEntry = page.locator('main').getByText(/^新增线索/).first();
  await expect(addEntry).toBeVisible({ timeout: 15000 });

  for (let attempt = 0; attempt < 2; attempt += 1) {
    await addEntry.click({ force: true });
    const formFields = page.locator('.lxy-modal-wrap:visible input:visible, .lxy-modal-wrap:visible textarea:visible');
    try {
      await formFields.first().waitFor({ state: 'visible', timeout: 12000 });
      return page.locator('.lxy-modal-wrap:visible').last();
    } catch (error) {
      if (attempt === 1) throw error;
      await page.goto('/pioneers#/leads/list', { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(1500);
      await expect(page.locator('main').getByText('线索1', { exact: true }).first()).toBeVisible({ timeout: 30000 });
    }
  }
  throw new Error('新增线索弹窗未打开');
}

// 创建线索
async function createLead(page: Page, name: string, phone: string): Promise<void> {
  await page.goto('/pioneers#/leads/list', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(1500);
  await expect(page.locator('main').getByText('线索1', { exact: true }).first()).toBeVisible({ timeout: 30000 });
  const modal = await clickAddLead(page);
  await selectLeadMarketActivity(page);
  const expandMore = page.getByText('展开更多信息', { exact: true }).first();
  if (await expandMore.count()) await expandMore.click();
  await selectLeadSourceIfAvailable(page);
  await fillVisibleLeadFields(modal, name, phone);
  await fillLeadRegion(page);
  await selectLabeledDateToday(page, modal, '新增日期');
  await fillDateField(modal.locator('#lead_revisit_remind_at:visible'), formatDateTime(nextMonthSameDay()));
  await fillLabeledDateField(page, modal, '下次跟进时间', formatDateTime(nextMonthSameDay()));
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
  const saveEntries = modal.getByText('保存', { exact: true });
  let saved = false;
  for (let index = 0; index < await saveEntries.count(); index += 1) {
    const entry = saveEntries.nth(index);
    if (await entry.isVisible().catch(() => false)) {
      await entry.click({ force: true });
      saved = true;
      break;
    }
  }
  if (!saved) throw new Error('当前新增弹窗未找到可见的保存按钮');
  await page.locator('.lxy-modal-mask').waitFor({ state: 'hidden', timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(1000);
}

// 通过日期面板选择下个月同一天
async function pickNextMonthDay25(page: Page): Promise<void> {
  const target = nextMonthSameDay();
  const dateStr = `${target.getFullYear()}-${String(target.getMonth() + 1).padStart(2, '0')}-${String(target.getDate()).padStart(2, '0')}`;
  const field = page.locator('#opportunity_expect_sign_date').first();
  await field.click({ force: true });
  const picker = page.locator('.ant-picker-dropdown:visible').last();
  await picker.waitFor({ state: 'visible', timeout: 5000 });

  for (let attempt = 0; attempt < 12; attempt += 1) {
    const targetCell = picker.locator(`td[title="${dateStr}"]:visible`).first();
    if (await targetCell.count()) {
      await targetCell.click({ force: true });
      await expect(field).toHaveValue(dateStr, { timeout: 3000 });
      return;
    }
    await picker.locator('.ant-picker-header-next-btn').click({ force: true });
    await page.waitForTimeout(150);
  }
  throw new Error(`日期面板未找到目标日期: ${dateStr}`);
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

// 从详情页删除目标已通过线索，未指定目标时回退到最早数据
async function deleteEarliestApprovedLead(page: Page, targetName?: string): Promise<void> {
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

  let leadLink: Locator | null = null;
  if (targetName) {
    const target = page.locator('main').getByText(targetName, { exact: true }).first();
    if (await target.isVisible().catch(() => false)) leadLink = target;
  }

  if (!leadLink) {
    // 目标不存在时，取当前页创建时间最早（最后一行）的已通过线索。
    const rows = page.locator('.lxt-table-row');
    await expect(rows.first()).toBeVisible({ timeout: 10000 });
    const rowCount = await rows.count();
    const lastRow = rows.nth(rowCount - 1);
    leadLink = lastRow.locator('[class*="cell"] a, [class*="cell"] span, td a').first();
  }

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
  await page.waitForLoadState('domcontentloaded').catch(() => {});
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
      await page.locator('#customer_address_region_info')
        .locator('xpath=ancestor::*[contains(@class, "ant-select")][1]')
        .click({ force: true });
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

      await selectFirstOptionIfAvailable(page, page.locator('#customer_status'));
      await selectFirstOptionIfAvailable(page, page.locator('#customer_industry'));
      await selectFirstOptionIfAvailable(page, page.locator('#customer_staff_size'));

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

    await test.step('删除线索（删除本流程创建的已通过线索）', async () => {
      await deleteEarliestApprovedLead(page, editedLeadName);
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
      const opportunityTitleLabel = page.getByText(/^商机标题/).last();
      const opportunityTitleInput = opportunityTitleLabel
        .locator('xpath=ancestor::div[.//input][1]')
        .locator('input')
        .first();
      await opportunityTitleInput.fill(opportunityTitle);
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
