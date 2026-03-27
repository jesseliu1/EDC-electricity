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
        last_sync_label: '2026-03-25 15:30:00',
        meta: {
          source: 'http://60.251.229.32',
          sensor_count: 26,
          channel_count: 2286,
          enabled_channel_count: 6,
        },
      },
      edc: {
        configured: true,
        base_url: 'http://60.251.229.32',
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

function buildCurvePoints(
  startIso: string,
  count: number,
  stepMinutes: number,
  base: number,
  delta: number
) {
  const start = new Date(startIso).getTime()
  return Array.from({ length: count }).map((_, index) => ({
    timestamp: start + index * stepMinutes * 60 * 1000,
    value: Number((base + ((index % 6) - 2) * delta).toFixed(base < 2 ? 2 : 1)),
  }))
}

async function mockDashboardRecentHeatToDetail(page: Page) {
  await mockRuntimeStatus(page)

  const powerCurve = buildCurvePoints('2026-03-20T08:36:00Z', 46, 1, 438, 6)
  const voltageCurve = buildCurvePoints('2026-03-20T08:36:00Z', 46, 1, 386, 1.5)

  await page.route('**/api/dashboard/stats**', async (route) => {
    await fulfillJson(route, {
      today_heats: 8,
      avg_deviation: 12.4,
      pending_tasks: 2,
      baseline_status: 'normal',
    })
  })

  await page.route('**/api/dashboard/recent-heats?**', async (route) => {
    await fulfillJson(route, {
      items: [
        {
          id: 'dashboard-heat-001-id',
          heat_no: 'H20260320-001',
          start_time: '2026-03-20T08:36:00Z',
          duration_minutes: 45,
          deviation_percent: 18.5,
          status: 'abnormal',
        },
      ],
    })
  })

  await page.route('**/api/heats/dashboard-heat-001-id/compare', async (route) => {
    await fulfillJson(route, {
      heat: {
        id: 'dashboard-heat-001-id',
        heat_no: 'H20260320-001',
        description: null,
        start_time: '2026-03-20T08:36:00Z',
        end_time: '2026-03-20T09:21:00Z',
        baseline_id: 'baseline-001',
        deviation_percent: 18.5,
        avg_deviation_percent: 9.2,
        time_offset_percent: 4.8,
        mismatch_duration_minutes: 4,
        schedule_tag: 'work',
        cut_reason: 'time_offset_exceed',
        cut_status: 'normal',
        major_issue: false,
        blocked_by_issue: false,
        status: 'abnormal',
        temperature: 1458,
        created_at: '2026-03-20T08:36:00Z',
        power_curve: powerCurve,
        voltage_curve: voltageCurve,
      },
      baselines: [
        {
          baseline: {
            id: 'baseline-001',
            name: '标准基线 v2.1',
            power_curve: powerCurve.map((item) => ({ ...item, value: 460 })),
            voltage_curve: voltageCurve.map((item) => ({ ...item, value: 385 })),
            tolerance_percent: 15,
          },
          metric_curves: [
            {
              metric_key: 'power',
              metric_name: '功率',
              unit: 'kW',
              color: '#409EFF',
              baseline_curve: powerCurve.map((item) => ({ ...item, value: 460 })),
              current_curve: powerCurve,
            },
            {
              metric_key: 'voltage',
              metric_name: '电压',
              unit: 'V',
              color: '#67C23A',
              baseline_curve: voltageCurve.map((item) => ({ ...item, value: 385 })),
              current_curve: voltageCurve,
            },
          ],
          deviation_ranges: [],
          max_deviation: 18.5,
          avg_deviation: 9.2,
        },
      ],
      deviation_ranges: [],
      max_deviation: 18.5,
      avg_deviation: 9.2,
    })
  })

  await page.route('**/api/heats/dashboard-heat-001-id/cutting-timeline', async (route) => {
    await fulfillJson(route, {
      heat_id: 'dashboard-heat-001-id',
      events: [
        {
          timestamp: '2026-03-20T08:36:00Z',
          event_type: 'stream_in',
          title: '实时流入',
          detail: '炉次进入切割判定队列',
        },
      ],
    })
  })
}

async function mockBaselineListToDetail(page: Page) {
  await mockRuntimeStatus(page)

  await page.route(/\/api\/baselines\/active$/, async (route) => {
    await fulfillJson(route, {
      id: 'baseline-001',
      name: '标准基线 v2.1',
      status: 'published',
      version: 2,
    })
  })

  await page.route(/\/api\/baselines(\?.*)?$/, async (route) => {
    await fulfillJson(route, {
      items: [
        {
          id: 'baseline-001',
          name: '标准基线 v2.1',
          description: '用于正式回归的标准曲线',
          definition_id: 'def-001',
          definition_name: '标准熔炼基线',
          source_heat_id: 'heat-001',
          selected_start_time: '2026-03-20T08:00:00Z',
          selected_end_time: '2026-03-20T08:35:00Z',
          tolerance_percent: 12,
          status: 'published',
          version: 2,
          curve_source: 'live_edc',
          created_at: '2026-03-20T08:40:00Z',
          updated_at: '2026-03-20T08:40:00Z',
          published_at: '2026-03-20T08:45:00Z',
        },
      ],
      total: 1,
    })
  })

  await page.route(/\/api\/baselines\/baseline-001$/, async (route) => {
    await fulfillJson(route, {
      id: 'baseline-001',
      name: '标准基线 v2.1',
      description: '用于正式回归的标准曲线',
      definition_id: 'def-001',
      definition_name: '标准熔炼基线',
      source_heat_id: 'heat-001',
      selected_start_time: '2026-03-20T08:00:00Z',
      selected_end_time: '2026-03-20T08:35:00Z',
      tolerance_percent: 12,
      status: 'published',
      version: 2,
      curve_source: 'live_edc',
      created_at: '2026-03-20T08:40:00Z',
      updated_at: '2026-03-20T08:40:00Z',
      published_at: '2026-03-20T08:45:00Z',
      curves_data: [],
      power_curve: [],
      voltage_curve: [],
      temperature: null,
    })
  })
}

test.describe('full review acceptance supplements', () => {
  test('dashboard recent heat row opens heat detail', async ({ page }) => {
    await mockDashboardRecentHeatToDetail(page)

    await page.goto('')
    await expect(page.getByTestId('dashboard-page')).toBeVisible()
    await page.locator('tbody tr').filter({ hasText: 'H20260320-001' }).first().click()

    await expect(page).toHaveURL(/\/edc\/heats\/dashboard-heat-001-id$/)
    await expect(page.getByTestId('heat-detail-page')).toBeVisible()
  })

  test('baseline list edit action opens detail page and keeps detail actions usable', async ({
    page,
  }) => {
    await mockBaselineListToDetail(page)

    await page.goto('baselines')
    await expect(page.getByTestId('baseline-list-page')).toBeVisible()

    await page.getByTestId('baseline-card-baseline-001').getByRole('button').click()
    await page.getByRole('menuitem', { name: '编辑' }).click()

    await expect(page).toHaveURL(/\/edc\/baselines\/baseline-001$/)
    await expect(page.getByTestId('baseline-detail-page')).toBeVisible()

    await page.getByTestId('baseline-detail-edit-button').click()
    await expect(
      page.locator('.el-message__content').filter({ hasText: '仅草稿状态可编辑' })
    ).toBeVisible()

    await page.getByTestId('baseline-detail-new-version-button').click()
    await expect(
      page.locator('.el-message__content').filter({ hasText: '创建新版本功能开发中' })
    ).toBeVisible()
  })
})
