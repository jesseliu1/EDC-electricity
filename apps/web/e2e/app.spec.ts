import { expect, test, type Page, type Route } from '@playwright/test'

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
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

async function mockBaselineWizardSmoke(page: Page) {
  const powerCurve = buildCurvePoints('2026-03-19T08:00:00Z', 40, 1, 438, 6)
  const voltageCurve = buildCurvePoints('2026-03-19T08:00:00Z', 40, 1, 386, 1.5)

  await page.route('**/api/baselines/active', async (route) => {
    await fulfillJson(route, null)
  })
  await page.route('**/api/baselines', async (route) => {
    if (route.request().method() === 'GET') {
      await fulfillJson(route, { items: [], total: 0 })
      return
    }
    await fulfillJson(
      route,
      {
        id: 'baseline-e2e',
        name: 'E2E 基线回归样例',
        description: null,
        definition_id: 'def-real',
        definition_name: '真实数据基线定义',
        status: 'draft',
        version: 1,
        tolerance_percent: 15,
        source_heat_id: 'heat-real-001',
        selected_start_time: '2026-03-19T08:05:00Z',
        selected_end_time: '2026-03-19T08:35:00Z',
        created_at: '2026-03-19T08:45:00Z',
        updated_at: '2026-03-19T08:45:00Z',
        published_at: null,
        curves_data: [],
        power_curve: [],
        voltage_curve: [],
        temperature: null,
      },
      201
    )
  })
  await page.route('**/api/baselines/baseline-e2e/publish', async (route) => {
    await fulfillJson(route, {
      id: 'baseline-e2e',
      name: 'E2E 基线回归样例',
      description: null,
      definition_id: 'def-real',
      definition_name: '真实数据基线定义',
      status: 'published',
      version: 1,
      tolerance_percent: 15,
      source_heat_id: 'heat-real-001',
      selected_start_time: '2026-03-19T08:05:00Z',
      selected_end_time: '2026-03-19T08:35:00Z',
      created_at: '2026-03-19T08:45:00Z',
      updated_at: '2026-03-19T08:46:00Z',
      published_at: '2026-03-19T08:46:00Z',
      curves_data: [],
      power_curve: [],
      voltage_curve: [],
      temperature: null,
    })
  })
  await page.route('**/api/baseline-definitions?status=active', async (route) => {
    await fulfillJson(route, {
      items: [
        {
          id: 'def-real',
          definition_name: '真实数据基线定义',
          description: '只允许真实数据预览',
          expected_duration_minutes: 40,
          status: 'active',
          metrics: [
            {
              id: 'metric-power',
              name: '功率',
              unit: 'kW',
              color: '#409EFF',
              sort_order: 1,
              edc_channel_id: '2349-199',
            },
            {
              id: 'metric-voltage',
              name: '电压',
              unit: 'V',
              color: '#67C23A',
              sort_order: 2,
              edc_channel_id: '2349-128',
            },
          ],
          instance_count: 0,
          created_at: '2026-03-19T00:00:00Z',
          updated_at: '2026-03-19T00:00:00Z',
        },
      ],
      total: 1,
    })
  })
  await page.route('**/api/heats?page=1&page_size=50', async (route) => {
    await fulfillJson(route, {
      items: [
        {
          id: 'heat-real-001',
          heat_no: 'H20260319-001',
          description: null,
          start_time: '2026-03-19T08:00:00Z',
          end_time: '2026-03-19T08:40:00Z',
          baseline_id: null,
          deviation_percent: null,
          avg_deviation_percent: null,
          time_offset_percent: null,
          mismatch_duration_minutes: null,
          schedule_tag: 'work',
          cut_reason: null,
          cut_status: 'normal',
          major_issue: false,
          blocked_by_issue: false,
          status: 'normal',
          temperature: 1458,
          created_at: '2026-03-19T08:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      page_size: 50,
    })
  })
  await page.route('**/api/baseline-definitions/def-real/preview-curves?*', async (route) => {
    await fulfillJson(route, {
      definition_id: 'def-real',
      source_heat_id: 'heat-real-001',
      range_start: '2026-03-19T08:00:00Z',
      range_end: '2026-03-19T08:40:00Z',
      curves_data: [
        {
          metric_id: 'metric-power',
          metric_name: '功率',
          unit: 'kW',
          color: '#409EFF',
          edc_channel_id: '2349-199',
          source_channel_name: '总有功功率',
          source_channel_label: 'SSTW / 总有功功率 / kW',
          points: powerCurve,
        },
        {
          metric_id: 'metric-voltage',
          metric_name: '电压',
          unit: 'V',
          color: '#67C23A',
          edc_channel_id: '2349-128',
          source_channel_name: 'A相电压',
          source_channel_label: 'SSTW / A相电压 / V',
          points: voltageCurve,
        },
      ],
    })
  })
}

async function mockHeatSmoke(page: Page) {
  const powerCurve = buildCurvePoints('2026-03-13T08:36:00Z', 46, 1, 438, 6)
  const voltageCurve = buildCurvePoints('2026-03-13T08:36:00Z', 46, 1, 386, 1.5)
  const temperatureCurve = buildCurvePoints('2026-03-13T08:36:00Z', 46, 1, 1462, 6)
  const pressureCurve = buildCurvePoints('2026-03-13T08:36:00Z', 46, 1, 0.82, 0.03)

  await page.route('**/api/heats?page=1&page_size=10', async (route) => {
    await fulfillJson(route, {
      items: [
        {
          id: 'issue-heat',
          heat_no: 'H20260313-001',
          description: null,
          start_time: '2026-03-13T08:36:00Z',
          end_time: '2026-03-13T09:21:00Z',
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
          created_at: '2026-03-13T08:36:00Z',
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    })
  })
  await page.route('**/api/heats/issue-heat', async (route) => {
    if (route.request().method() === 'PATCH') {
      const payload = JSON.parse(route.request().postData() || '{}')
      await fulfillJson(route, {
        id: 'issue-heat',
        heat_no: 'H20260313-001',
        description: payload.description || null,
        start_time: payload.start_time || '2026-03-13T08:36:00Z',
        end_time: payload.end_time || '2026-03-13T09:21:00Z',
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
        created_at: '2026-03-13T08:36:00Z',
      })
      return
    }

    await fulfillJson(route, {
      id: 'issue-heat',
      heat_no: 'H20260313-001',
      description: null,
      start_time: '2026-03-13T08:36:00Z',
      end_time: '2026-03-13T09:21:00Z',
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
      created_at: '2026-03-13T08:36:00Z',
    })
  })
  await page.route('**/api/heats/issue-heat/curve', async (route) => {
    await fulfillJson(route, {
      id: 'issue-heat',
      heat_no: 'H20260313-001',
      description: null,
      start_time: '2026-03-13T08:36:00Z',
      end_time: '2026-03-13T09:21:00Z',
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
      created_at: '2026-03-13T08:36:00Z',
      power_curve: powerCurve,
      voltage_curve: voltageCurve,
      temperature_curve: temperatureCurve,
      baseline_power_curve: powerCurve.map((item) => ({ ...item, value: 460 })),
      baseline_voltage_curve: voltageCurve.map((item) => ({ ...item, value: 385 })),
    })
  })
  await page.route('**/api/heats/issue-heat/compare', async (route) => {
    await fulfillJson(route, {
      heat: {
        id: 'issue-heat',
        heat_no: 'H20260313-001',
        description: null,
        start_time: '2026-03-13T08:36:00Z',
        end_time: '2026-03-13T09:21:00Z',
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
        created_at: '2026-03-13T08:36:00Z',
        power_curve: powerCurve,
        voltage_curve: voltageCurve,
        temperature_curve: temperatureCurve,
      },
      baselines: [
        {
          baseline: {
            id: 'baseline-001',
            name: '标准基线 v2.1',
            status: 'published',
            version: 2,
          },
          deviation_percent: 18.5,
          avg_deviation_percent: 9.2,
          deviation_ranges: [
            {
              metric_key: 'power',
              metric_name: '功率',
              start_time: '2026-03-13T08:52:00Z',
              end_time: '2026-03-13T08:57:00Z',
              max_deviation_percent: 18.5,
              avg_deviation_percent: 12.1,
            },
          ],
          metric_curves: [
            {
              metric_key: 'power',
              metric_name: '功率',
              unit: 'kW',
              color: '#409EFF',
              baseline_curve: powerCurve.map((item) => ({ ...item, value: 460 })),
              current_curve: powerCurve,
              source_channel_name: '总有功功率',
              source_channel_label: 'SSTW / 总有功功率 / kW',
            },
            {
              metric_key: 'voltage',
              metric_name: '电压',
              unit: 'V',
              color: '#67C23A',
              baseline_curve: voltageCurve.map((item) => ({ ...item, value: 385 })),
              current_curve: voltageCurve,
              source_channel_name: 'A相电压',
              source_channel_label: 'SSTW / A相电压 / V',
            },
            {
              metric_key: 'temperature',
              metric_name: '炉温',
              unit: '°C',
              color: '#E6A23C',
              baseline_curve: temperatureCurve.map((item) => ({ ...item, value: 1455 })),
              current_curve: temperatureCurve,
              source_channel_name: '热电偶温度采集通道',
              source_channel_label: 'SSTW / 热电偶温度采集通道 / ℃',
            },
            {
              metric_key: 'pressure',
              metric_name: '炉压',
              unit: 'MPa',
              color: '#F56C6C',
              baseline_curve: pressureCurve.map((item) => ({ ...item, value: 0.84 })),
              current_curve: pressureCurve,
              source_channel_name: '炉压采集通道',
              source_channel_label: 'SSTW / 炉压采集通道 / MPa',
            },
          ],
        },
      ],
    })
  })
  await page.route('**/api/heats/issue-heat/cutting-timeline', async (route) => {
    await fulfillJson(route, {
      heat_id: 'issue-heat',
      events: [
        {
          timestamp: '2026-03-13T08:36:00Z',
          event_type: 'stream_in',
          title: '实时流入',
          detail: '炉次进入切割判定队列',
        },
        {
          timestamp: '2026-03-13T09:21:00Z',
          event_type: 'abnormal',
          title: '判定异常',
          detail: '与默认黄金基线比对后偏差超阈值',
        },
      ],
    })
  })
}

test.describe('EDC web smoke flows', () => {
  test('can create and publish a baseline from the wizard', async ({ page }) => {
    await mockBaselineWizardSmoke(page)
    await page.goto('baselines')

    await expect(page.getByTestId('baseline-create-button')).toBeVisible()
    await page.getByTestId('baseline-create-button').click()

    await expect(page.getByTestId('baseline-wizard')).toBeVisible()
    await expect(page.getByText('设置基线')).toBeVisible()
    await expect(page.getByText(/条曲线 ·/)).toBeVisible()
    await expect(page.getByTestId('baseline-wizard-definition-select')).toBeVisible()

    await page.getByTestId('baseline-wizard-name-input').fill('E2E 基线回归样例')
    await page.getByTestId('baseline-wizard-next').click()
    await expect(page.getByTestId('baseline-wizard-point-range-panel')).toBeVisible()
    await expect(page.getByTestId('baseline-wizard-selection-state')).toHaveAttribute(
      'data-start',
      /.+/
    )
    await expect(page.getByTestId('baseline-wizard-selection-state')).toHaveAttribute(
      'data-end',
      /.+/
    )
    await page.getByTestId('baseline-wizard-next').click()
    await expect(page.getByTestId('baseline-wizard-publish')).toBeVisible()
    await page.getByTestId('baseline-wizard-publish').click()

    await expect(page.getByRole('heading', { name: 'E2E 基线回归样例' }).first()).toBeVisible()
    await expect(page.getByText('真实数据基线定义').first()).toBeVisible()
  })

  test('expanded heat row uses a detail CTA that matches the detail navigation target', async ({ page }) => {
    await mockHeatSmoke(page)
    await page.goto('heats')

    const firstExpandButton = page.getByTestId('heat-row-expand').first()
    await expect(firstExpandButton).toBeVisible()
    await firstExpandButton.click()

    const expandedCard = page.getByTestId('heat-expanded-panel').first()
    await expect(expandedCard).toBeVisible()
    await expect(expandedCard.getByText('功率微缩曲线')).toBeVisible()

    const detailButton = expandedCard.getByTestId('heat-view-report-button')
    await expect(detailButton).toHaveText(/查看炉次详情/)
    await expect(detailButton).not.toHaveText(/报告/)
    await detailButton.click()
    await expect(page).toHaveURL(/\/edc\/heats\/issue-heat/)
    await expect(page.getByTestId('heat-detail-page')).toBeVisible()
  })

  test('heat list export button shows explicit placeholder feedback instead of staying silent', async ({ page }) => {
    await mockHeatSmoke(page)
    await page.goto('heats')

    await expect(page.getByTestId('heat-export-button')).toBeVisible()
    await page.getByTestId('heat-export-button').click()
    await expect(page.locator('.el-message__content').filter({ hasText: '导出 Excel 入口开发中' })).toBeVisible()
    await expect(page).toHaveURL(/\/edc\/heats$/)
  })

  test('heat list unsupported device and alloy filters are explicitly disabled', async ({ page }) => {
    await mockHeatSmoke(page)
    await page.goto('heats')

    await expect(page.getByTestId('heat-row-issue-heat')).toBeVisible()

    const deviceFilter = page.getByTestId('heat-device-filter-input')
    const alloyFilter = page.getByTestId('heat-alloy-filter-input')

    await expect(deviceFilter).toBeDisabled()
    await expect(alloyFilter).toBeDisabled()
    await expect(page.getByTestId('heat-device-filter-hint')).toHaveText('当前数据源暂不支持按设备 ID 筛选。')
    await expect(page.getByTestId('heat-alloy-filter-hint')).toHaveText('当前数据源暂不支持按合金号筛选。')
  })

  test('heat detail create task button posts to tasks api and opens the created task detail', async ({
    page,
  }) => {
    await mockHeatSmoke(page)
    await page.route('**/api/settings/runtime-status**', async (route) => {
      await fulfillJson(route, {
        overall_code: 'ready',
        host: { is_connected: true, machine_name: 'EDC Test Gateway', last_sync_label: '2026-03-25 10:00:00' },
        edc: { configured: true, base_url: 'http://60.251.229.32', username_present: true },
        active_baseline: { id: 'baseline-001', name: '标准基线 v2.1', status: 'published' },
        runtime: { showtime_enabled: false, live_heat_inference_enabled: true, baseline_length_scope_mode: 'definition' },
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

    let createPayload: Record<string, unknown> | null = null
    await page.route('**/api/tasks', async (route) => {
      if (route.request().method() !== 'POST') {
        await route.fallback()
        return
      }

      createPayload = JSON.parse(route.request().postData() || '{}')
      await fulfillJson(
        route,
        {
          id: 'task-from-heat-001',
          task_no: 'T20260325-001',
          heat_id: 'issue-heat',
          deviation_percent: 18.5,
          cause_analysis: null,
          improvement: null,
          prevention: null,
          status: 'pending',
          created_at: '2026-03-25T10:00:00Z',
          updated_at: '2026-03-25T10:00:00Z',
          completed_at: null,
        },
        201
      )
    })
    await page.route('**/api/tasks/task-from-heat-001', async (route) => {
      await fulfillJson(route, {
        id: 'task-from-heat-001',
        task_no: 'T20260325-001',
        heat_id: 'issue-heat',
        heat_no: 'H20260313-001',
        deviation_percent: 18.5,
        deviation_snapshot: {
          max_deviation: 18.5,
          avg_deviation: 9.2,
          deviation_ranges: [],
        },
        cause_analysis: null,
        improvement: null,
        prevention: null,
        status: 'pending',
        created_at: '2026-03-25T10:00:00Z',
        updated_at: '2026-03-25T10:00:00Z',
        completed_at: null,
      })
    })

    await page.goto('heats/issue-heat')

    await expect(page.getByTestId('heat-detail-page')).toBeVisible()
    await page.getByTestId('heat-create-task-button').click()

    expect(createPayload).toEqual({ heat_id: 'issue-heat' })
    await expect(page).toHaveURL(/\/edc\/tasks\/task-from-heat-001$/)
    await expect(page.getByTestId('task-detail-page')).toBeVisible()
    await expect(page.getByTestId('task-detail-page')).toContainText('H20260313-001')
  })

  test('can open and save the manual adjust dialog', async ({ page }) => {
    await mockHeatSmoke(page)
    await page.goto('heats/issue-heat')

    await expect(page.getByTestId('heat-detail-page')).toBeVisible()
    await page.getByRole('button', { name: /手动调整/ }).click()

    const dialog = page.getByTestId('manual-adjust-dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog.getByText('展示当前炉次所在当天的完整数据流')).toBeVisible()

    await page.getByTestId('manual-adjust-save').click()
    await page.getByRole('button', { name: '仅调整当前' }).click()

    await expect(dialog).toBeHidden()
    await expect(page.locator('.el-message').filter({ hasText: '成功' })).toBeVisible()
  })

  test('heat detail replaces legacy live heat urls with the canonical heat id returned by the api', async ({
    page,
  }) => {
    const legacyHeatId = 'live-heat-0ef1bbda-1774314300000-30'
    const canonicalHeatId = 'live-heat-0ef1bbda-1774314600000-30'
    const powerCurve = buildCurvePoints('2026-03-22T08:50:00Z', 46, 1, 438, 6)
    const voltageCurve = buildCurvePoints('2026-03-22T08:50:00Z', 46, 1, 386, 1.5)
    const compareCounts = {
      legacy: 0,
      canonical: 0,
    }

    const comparePayload = {
      heat: {
        id: canonicalHeatId,
        heat_no: 'H20260322-001',
        description: null,
        start_time: '2026-03-22T08:53:00Z',
        end_time: '2026-03-22T09:25:00Z',
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
        created_at: '2026-03-22T08:53:00Z',
        record_source: 'live_inferred',
        current_curve_source: 'live_edc',
        baseline_curve_source: 'none',
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
          metric_curves: [],
          deviation_ranges: [],
          max_deviation: 18.5,
          avg_deviation: 9.2,
        },
      ],
      deviation_ranges: [],
      max_deviation: 18.5,
      avg_deviation: 9.2,
    }

    const timelinePayload = {
      heat_id: canonicalHeatId,
      events: [
        {
          timestamp: '2026-03-22T08:53:00Z',
          event_type: 'stream_in',
          title: '实时流入',
          detail: '炉次进入切割判定队列',
        },
      ],
    }

    await page.route('**/api/settings/runtime-status**', async (route) => {
      await fulfillJson(route, {
        overall_code: 'ready',
        host: {
          is_connected: true,
          machine_name: 'EDC Test Gateway',
          last_sync_label: '2026-03-25 07:00:00',
        },
        edc: {
          configured: true,
          base_url: 'http://127.0.0.1:8080',
          username_present: true,
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
    await page.route(`**/api/heats/${legacyHeatId}/compare`, async (route) => {
      compareCounts.legacy += 1
      await fulfillJson(route, comparePayload)
    })
    await page.route(`**/api/heats/${canonicalHeatId}/compare`, async (route) => {
      compareCounts.canonical += 1
      await fulfillJson(route, comparePayload)
    })
    await page.route(`**/api/heats/${legacyHeatId}/cutting-timeline`, async (route) => {
      await fulfillJson(route, timelinePayload)
    })
    await page.route(`**/api/heats/${canonicalHeatId}/cutting-timeline`, async (route) => {
      await fulfillJson(route, timelinePayload)
    })

    await page.goto(`heats/${legacyHeatId}`)
    await expect(page.getByTestId('heat-detail-page')).toBeVisible()
    await expect(page).toHaveURL(new RegExp(`/edc/heats/${canonicalHeatId}$`))
    await expect(page.getByText(`ID: ${canonicalHeatId}`)).toBeVisible()

    await page.goto(`heats/${legacyHeatId}`)
    await expect(page).toHaveURL(new RegExp(`/edc/heats/${canonicalHeatId}$`))
    await expect(page.getByText(`ID: ${canonicalHeatId}`)).toBeVisible()

    expect(compareCounts).toEqual({
      legacy: 2,
      canonical: 2,
    })
  })
})
