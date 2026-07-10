import { expect, test } from '@playwright/test';
import { getEnv, getOptionalEnv } from '../../helpers/env';

test.describe('CRM PC 线索冒烟', () => {
  test.setTimeout(180_000);

  test('登录后可以进入线索列表', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const accountInput = page.locator('#account');
    const initialState = await Promise.race([
      accountInput.waitFor({ state: 'visible', timeout: 60_000 }).then(() => 'login').catch(() => 'login-timeout'),
      page.waitForURL(/workbench|dashboard|pioneers/i, { timeout: 60_000 }).then(() => 'crm').catch(() => 'crm-timeout'),
    ]);

    expect(initialState, `应进入登录页或 CRM 页面，当前 URL: ${page.url()}`).not.toMatch(/timeout$/);

    if (initialState === 'login') {
      await page.locator('#account').click();
      await page.locator('#account').fill(getEnv('CRM_USERNAME', getOptionalEnv('TEST_USERNAME')));
      await page.locator('#password').click();
      await page.locator('#password').fill(getEnv('CRM_PASSWORD', getOptionalEnv('TEST_PASSWORD')));

      const checkboxes = page.locator('input[type="checkbox"]');
      const checkboxCount = await checkboxes.count();
      for (let index = 0; index < checkboxCount; index += 1) {
        const checkbox = checkboxes.nth(index);
        if (!(await checkbox.isChecked())) {
          await checkbox.click();
        }
        await expect(checkbox).toBeChecked();
      }
      let loginSuccess = false;
      for (let attempt = 0; attempt < 3; attempt += 1) {
        await page.getByRole('button', { name: '登 录' }).click();
        loginSuccess = await page
          .waitForURL(/workbench|dashboard|pioneers/i, { timeout: 30_000 })
          .then(() => true)
          .catch(() => false);
        if (loginSuccess) {
          break;
        }
      }

      expect(loginSuccess, `登录后应跳转 CRM，当前 URL: ${page.url()}`).toBe(true);
    }

    await page.goto('/pioneers#/leads/list');
    await page.waitForLoadState('domcontentloaded');

    await expect(page).toHaveURL(/leads\/list/);
    await expect(page.getByText('姓名').first()).toBeVisible();
  });
});
