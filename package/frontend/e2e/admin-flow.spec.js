import { expect, test } from '@playwright/test';

const fulfillJson = (route, data) =>
  route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(data),
  });

const statistics = {
  users: {
    total: 1,
    active: 1,
    inactive: 0,
    used: 1,
    unused: 0,
    today_new: 0,
    today_active: 0,
    recent_active_7days: 1,
  },
  sessions: {
    total: 0,
    completed: 0,
    processing: 0,
    queued: 0,
    failed: 0,
    today: 0,
  },
  segments: {
    total: 0,
    completed: 0,
    pending: 0,
  },
  processing: {
    total_chars_processed: 0,
    avg_processing_time: 0,
    paper_polish_count: 0,
    paper_enhance_count: 0,
    paper_polish_enhance_count: 0,
    emotion_polish_count: 0,
  },
};

const adminConfig = {
  polish: {
    model: 'gpt-5.5',
    api_key: '',
    base_url: 'https://api.openai.com/v1',
  },
  enhance: {
    model: 'gpt-5.5',
    api_key: '',
    base_url: 'https://api.openai.com/v1',
  },
  emotion: {
    model: '',
    api_key: '',
    base_url: '',
  },
  compression: {
    model: 'gpt-5.5',
    api_key: '',
    base_url: 'https://api.openai.com/v1',
  },
  thinking: {
    enabled: true,
    effort: 'high',
  },
  system: {
    max_concurrent_users: 20,
    history_compression_threshold: 11998,
    default_usage_limit: 1,
    segment_skip_threshold: 15,
    use_streaming: false,
    max_upload_file_size_mb: 0,
    api_request_interval: 6,
    registration_enabled: true,
  },
};

async function mockAdminApis(page, options = {}) {
  const users = options.users || [];
  const creditTransactionsStatus = options.creditTransactionsStatus || 200;

  await page.route('**/api/admin/**', async (route) => {
    const url = new URL(route.request().url());

    if (url.pathname === '/api/admin/login') {
      return fulfillJson(route, { access_token: 'mock-admin-token', token_type: 'bearer' });
    }

    if (url.pathname === '/api/admin/verify-token') {
      return fulfillJson(route, { valid: true });
    }

    if (url.pathname === '/api/admin/statistics') {
      return fulfillJson(route, statistics);
    }

    if (url.pathname === '/api/admin/config') {
      return fulfillJson(route, adminConfig);
    }

    if (url.pathname === '/api/admin/users') {
      return fulfillJson(route, users);
    }

    if (url.pathname === '/api/admin/credit-transactions') {
      if (creditTransactionsStatus === 404) {
        return route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Not found' }),
        });
      }
      return fulfillJson(route, []);
    }

    if (
      url.pathname === '/api/admin/sessions' ||
      url.pathname === '/api/admin/sessions/active' ||
      url.pathname === '/api/admin/invites' ||
      url.pathname === '/api/admin/credit-codes' ||
      url.pathname === '/api/admin/provider-configs'
    ) {
      return fulfillJson(route, []);
    }

    return fulfillJson(route, {});
  });
}

test('admin can log in and switch core sections', async ({ page }) => {
  await mockAdminApis(page);
  await page.goto('/admin');

  await expect(page.getByRole('heading', { name: '管理后台' })).toBeVisible();
  await page.getByPlaceholder('请输入用户名').fill('admin');
  await page.getByPlaceholder('请输入密码').fill('admin-password');
  await page.getByRole('button', { name: /登录/ }).click();

  await expect(page.locator('[data-admin-nav="sidebar"]')).toBeVisible();
  await expect(page.getByRole('button', { name: /数据面板/ })).toBeVisible();

  await page.getByRole('button', { name: /会话监控/ }).click();
  await expect(page).toHaveURL(/tab=sessions/);

  await page.getByRole('button', { name: /账号啤酒/ }).click();
  await expect(page).toHaveURL(/tab=accounts/);
  await expect(page.getByRole('heading', { name: '啤酒兑换码' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '最近啤酒流水' })).toBeVisible();

  await page.getByRole('button', { name: /系统配置/ }).click();
  await expect(page).toHaveURL(/tab=config/);
  await expect(page.getByRole('heading', { name: '润色模型配置', exact: true })).toBeVisible();

  await expect(page.getByText(/卡密|Word 排版任务|论文排版/)).toHaveCount(0);
});

test('admin account data remains visible if beer history endpoint is missing', async ({ page }) => {
  await mockAdminApis(page, {
    creditTransactionsStatus: 404,
    users: [{
      id: 7,
      username: 'alice',
      nickname: 'Alice',
      is_active: true,
      is_unlimited: false,
      credit_balance: 18,
      created_at: '2026-04-30T00:00:00',
      last_login_at: null,
      last_used: null,
      usage_limit: 0,
      usage_count: 0,
      access_link: 'account://alice',
    }],
  });
  await page.goto('/admin?tab=accounts');

  await page.getByPlaceholder('请输入用户名').fill('admin');
  await page.getByPlaceholder('请输入密码').fill('admin-password');
  await page.getByRole('button', { name: /登录/ }).click();

  await expect(page.getByText('alice')).toBeVisible();
  await expect(page.getByText('18')).toBeVisible();
  await expect(page.getByText('暂无啤酒流水')).toBeVisible();
});
