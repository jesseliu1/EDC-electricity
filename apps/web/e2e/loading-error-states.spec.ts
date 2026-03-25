import { expect, test, type Page, type Route } from '@playwright/test'

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

async function mockRuntimeStatus(page: Page) {
  await page.route('**/api/settings/runtime-status**', async (route) => {
    await fulfillJson(route, {
      overall_code: 'ready',
      host: {
        is_connected: true,
        machine_name: 'EDC Test Gateway',
        last_sync_label: '2026-03-24 12:00:00',
        meta: {
          source: 'http://127.0.0.1:8080',
          sensor_count: 26,
          channel_count: 2286,
          enabled_channel_count: 6,
        },
      },
      edc: {
        configured: true,
        base_url: 'http://127.0.0.1:8080',
        username_present: true,
        host_channel_total: 6,
        enabled_channel_count: 6,
      },
      active_baseline: {
        id: 'baseline-001',
        name: '标准基线 v2.1',
        status: 'published',
      },
      runtime: {
        showtime_enabled: false,
        live_heat_inference_enabled: true,
        baseline_length_scope_mode: 'definition',
      },
      pipelines: {
        dashboard: { code: 'ready', ready: true },
        heats: { code: 'ready', ready: true },
        inbox: { code: 'ready', ready: true },
        tasks: { code: 'ready', ready: true },
        reports: { code: 'ready', ready: true },
        baselines: { code: 'ready', ready: true },
        settings: { code: 'ready', ready: true },
      },
    })
  })
}

async function mockDashboardTaskLists(page: Page) {
  await page.route('**/api/tasks?**', async (route) => {
    await fulfillJson(route, {
      items: [],
      total: 0,
      page: 1,
      page_size: 3,
    })
  })
}

test.describe('EDC loading error states', () => {
  test('dashboard shows explicit warning instead of fake empty stats and empty recent heats', async ({
    page,
  }) => {
    await mockRuntimeStatus(page)
    await mockDashboardTaskLists(page)

    await page.route('**/api/dashboard/stats', async (route) => {
      await fulfillJson(route, { detail: '仪表盘统计接口超时' }, 504)
    })
    await page.route('**/api/dashboard/recent-heats?**', async (route) => {
      await fulfillJson(route, { detail: '最近炉次接口超时' }, 504)
    })
    await page.route('**/api/dashboard/realtime?duration=*', async (route) => {
      await fulfillJson(route, {
        timestamp: '2026-03-24T12:00:00Z',
        baseline_id: 'baseline-001',
        baseline_name: '标准基线 v2.1',
        power_source_label: 'SSTW / 总有功功率 / kW',
        voltage_source_label: 'SSTW / A相电压 / V',
        power: [],
        voltage: [],
        baseline_power: [],
        baseline_voltage: [],
      })
    })

    await page.goto('')

    await expect(page.getByTestId('dashboard-load-warning')).toBeVisible()
    await expect(page.getByTestId('dashboard-load-warning')).toContainText('仪表盘统计接口超时')
    await expect(page.getByTestId('dashboard-recent-heats-error')).toBeVisible()
    await expect(page.getByTestId('dashboard-recent-heats-error')).toContainText(
      '最近炉次接口超时'
    )
    await expect(page.getByTestId('dashboard-recent-heats-error')).toContainText(
      '请刷新页面或检查后端炉次接口状态。'
    )
    await expect(page.locator('[data-testid="stat-card"]').first()).toContainText('--')
  })

  test('heat detail exits loading state, disables manual adjust, and shows explicit error when compare request fails', async ({
    page,
  }) => {
    await mockRuntimeStatus(page)

    await page.route('**/api/heats/issue-heat/compare', async (route) => {
      await fulfillJson(route, { detail: '炉次详情接口超时' }, 504)
    })
    await page.route('**/api/heats/issue-heat/cutting-timeline', async (route) => {
      await fulfillJson(route, {
        heat_id: 'issue-heat',
        events: [],
      })
    })

    await page.goto('heats/issue-heat')

    await expect(page.getByTestId('heat-detail-error')).toBeVisible()
    await expect(page.getByTestId('heat-detail-error')).toContainText('炉次详情接口超时')
    await expect(page.getByTestId('heat-detail-error')).toContainText(
      '请刷新页面或检查后端炉次接口状态。'
    )
    await expect(page.getByTestId('heat-manual-adjust-button')).toBeDisabled()
    await expect(page.getByTestId('heat-manual-adjust-button')).toHaveAttribute(
      'title',
      '当前无可用炉次数据，无法手动调整。'
    )
    await expect(page.getByTestId('heat-detail-manual-adjust-unavailable')).toContainText(
      '当前无可用炉次数据，无法手动调整。'
    )
    await expect(page.getByTestId('heat-detail-loading')).toHaveCount(0)
  })

  test('task detail exits loading state and shows explicit error when detail request fails', async ({
    page,
  }) => {
    await mockRuntimeStatus(page)

    await page.route('**/api/tasks/nonexistent-task', async (route) => {
      await fulfillJson(route, { detail: '任务不存在' }, 404)
    })

    await page.goto('tasks/nonexistent-task')

    await expect(page.getByTestId('task-detail-error')).toBeVisible()
    await expect(page.getByTestId('task-detail-error')).toContainText('任务不存在')
    await expect(page.getByTestId('task-detail-error')).toContainText(
      '请刷新页面或检查后端任务接口状态。'
    )
    await expect(page.getByTestId('task-detail-loading')).toHaveCount(0)
  })
})
