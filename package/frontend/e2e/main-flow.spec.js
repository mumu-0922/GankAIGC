import { expect, test } from '@playwright/test';

const fulfillJson = (route, data) =>
  route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(data),
  });

async function mockUserApis(page) {
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    if (!url.pathname.startsWith('/api/')) {
      return route.continue();
    }

    if (url.pathname === '/api/auth/me') {
      return fulfillJson(route, {
        id: 1,
        username: 'alice',
        nickname: 'Alice',
        credit_balance: 12,
        is_unlimited: false,
      });
    }

    if (url.pathname === '/api/user/credits') {
      return fulfillJson(route, { credit_balance: 12, is_unlimited: false });
    }

    if (url.pathname === '/api/user/provider-config') {
      return fulfillJson(route, null);
    }

    if (url.pathname === '/api/user/projects') {
      return fulfillJson(route, []);
    }

    if (url.pathname === '/api/optimization/status') {
      return fulfillJson(route, {
        online_users: 1,
        current_users: 0,
        max_users: 20,
        queue_length: 0,
      });
    }

    if (url.pathname === '/api/optimization/sessions') {
      return fulfillJson(route, []);
    }

    return fulfillJson(route, {});
  });
}

test('home page exposes current product entry points', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: '让论文原创更简单' })).toBeVisible();
  await expect(page.getByRole('button', { name: /登录 \/ 注册/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /邀请码注册/ })).toBeVisible();
  await expect(page.locator('[data-home-github-star="footer"]')).toBeVisible();
  await expect(page.getByText(/Word 排版|论文排版/)).toHaveCount(0);
});

test('authenticated user can reach workspace credit controls', async ({ page }) => {
  await mockUserApis(page);
  await page.addInitScript(() => {
    window.localStorage.setItem('userToken', 'mock-user-token');
  });

  await page.goto('/workspace');

  await expect(page.getByRole('heading', { name: '新建任务' })).toBeVisible();
  await expect(page.getByText('兑换啤酒')).toBeVisible();
  await expect(page.getByLabel('剩余啤酒')).toContainText('12 啤酒');
  await expect(page.getByText('自带 API 模式')).toBeVisible();
  await expect(page.getByText('1 啤酒 = 1000 非空白字符')).toBeVisible();
  await expect(page.getByText(/Word 排版|论文排版/)).toHaveCount(0);
});
