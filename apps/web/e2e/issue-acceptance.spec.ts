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

async function clickChartAt(page: Page, testId: string, xRatio: number, yRatio: number) {
  const canvas = page.getByTestId(testId).locator('canvas').first()
  const box = await canvas.boundingBox()
  expect(box).not.toBeNull()

  await page.mouse.click(
    (box?.x || 0) + (box?.width || 0) * xRatio,
    (box?.y || 0) + (box?.height || 0) * yRatio
  )
}

async function dragChartAt(
  page: Page,
  testId: string,
  from: { xRatio: number; yRatio: number },
  to: { xRatio: number; yRatio: number }
) {
  const canvas = page.getByTestId(testId).locator('canvas').first()
  const box = await canvas.boundingBox()
  expect(box).not.toBeNull()

  await page.mouse.move(
    (box?.x || 0) + (box?.width || 0) * from.xRatio,
    (box?.y || 0) + (box?.height || 0) * from.yRatio
  )
  await page.mouse.down()
  await page.mouse.move(
    (box?.x || 0) + (box?.width || 0) * to.xRatio,
    (box?.y || 0) + (box?.height || 0) * to.yRatio,
    { steps: 12 }
  )
  await page.mouse.up()
}

async function wheelChartAt(
  page: Page,
  testId: string,
  xRatio: number,
  yRatio: number,
  deltaY: number
) {
  const canvas = page.getByTestId(testId).locator('canvas').first()
  const box = await canvas.boundingBox()
  expect(box).not.toBeNull()

  await page.mouse.move(
    (box?.x || 0) + (box?.width || 0) * xRatio,
    (box?.y || 0) + (box?.height || 0) * yRatio
  )
  await page.mouse.wheel(0, deltaY)
}

async function mockDashboardRanges(page: Page) {
  await page.route('**/api/dashboard/realtime?duration=*', async (route) => {
    const url = new URL(route.request().url())
    const duration = url.searchParams.get('duration') || '1h'
    const pointsByDuration = {
      '5m': 8,
      '1h': 12,
      '6h': 18,
      '24h': 24,
    }
    const count = pointsByDuration[duration as keyof typeof pointsByDuration] || 12
    const power = buildCurvePoints(
      '2026-03-13T00:00:00Z',
      count,
      duration === '24h' ? 60 : 10,
      440,
      5
    )

    await fulfillJson(route, {
      timestamp: '2026-03-13T09:30:00Z',
      baseline_id: 'baseline-001',
      baseline_name: '标准基线 v2.1',
      power_source_label: 'SSTW 380V-220V電力 · 三相智能电表 / 总有功功率 / kW',
      voltage_source_label: 'SSTW 380V-220V電力 · 三相智能电表 / A相电压 / V',
      power,
      voltage: buildCurvePoints(
        '2026-03-13T00:00:00Z',
        count,
        duration === '24h' ? 60 : 10,
        382,
        1
      ),
      baseline_power: power.map((item) => ({ ...item, value: 460 })),
      baseline_voltage: power.map((item) => ({ ...item, value: 385 })),
    })
  })
}

async function mockBaselineWizardAcceptance(
  page: Page,
  options?: { previewUnavailable?: boolean }
) {
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
    await route.fallback()
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
    if (options?.previewUnavailable) {
      await fulfillJson(
        route,
        { detail: '未获取到真实预览数据，请检查宿主连接和通道绑定' },
        503
      )
      return
    }

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

async function mockHeatAcceptance(page: Page) {
  const powerCurve = buildCurvePoints('2026-03-13T08:36:00Z', 46, 1, 438, 6)
  const voltageCurve = buildCurvePoints('2026-03-13T08:36:00Z', 46, 1, 386, 1.5)
  const temperatureCurve = buildCurvePoints('2026-03-13T08:36:00Z', 46, 1, 1462, 6)
  const pressureCurve = buildCurvePoints('2026-03-13T08:36:00Z', 46, 1, 0.82, 0.03)

  await page.route('**/api/heats/issue-heat', async (route) => {
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
      },
      baseline: null,
      baselines: [
        {
          baseline: {
            id: 'baseline-001',
            name: '标准基线 v2.1',
            power_curve: powerCurve.map((item) => ({
              ...item,
              value: Number((item.value + 8).toFixed(1)),
            })),
            voltage_curve: voltageCurve.map((item) => ({
              ...item,
              value: Number((item.value + 1).toFixed(1)),
            })),
            tolerance_percent: 15,
          },
          metric_curves: [
            {
              metric_key: 'power',
              metric_name: '功率',
              unit: 'kW',
              color: '#409EFF',
              edc_channel_id: '2349-199',
              source_channel_name: '总有功功率',
              source_channel_label: 'SSTW 380V-220V電力 · 三相智能电表 / 总有功功率 / kW',
              baseline_curve: powerCurve.map((item) => ({
                ...item,
                value: Number((item.value + 8).toFixed(1)),
              })),
              current_curve: powerCurve,
            },
            {
              metric_key: 'voltage',
              metric_name: '电压',
              unit: 'V',
              color: '#67C23A',
              edc_channel_id: '2349-128',
              source_channel_name: 'A相电压',
              source_channel_label: 'SSTW 380V-220V電力 · 三相智能电表 / A相电压 / V',
              baseline_curve: voltageCurve.map((item) => ({
                ...item,
                value: Number((item.value + 1).toFixed(1)),
              })),
              current_curve: voltageCurve,
            },
            {
              metric_key: 'temperature',
              metric_name: '炉温',
              unit: '°C',
              color: '#E6A23C',
              edc_channel_id: '2054-128',
              source_channel_name: '热电偶温度采集通道',
              source_channel_label: 'A-1溫度 · 热电偶温度采集器 / 热电偶温度采集通道 / ℃',
              baseline_curve: temperatureCurve.map((item) => ({
                ...item,
                value: Number((item.value + 6).toFixed(1)),
              })),
              current_curve: temperatureCurve,
            },
          ],
          deviation_ranges: [
            {
              start: powerCurve[10]?.timestamp,
              end: powerCurve[16]?.timestamp,
              deviation: 18.5,
            },
          ],
          max_deviation: 18.5,
          avg_deviation: 9.2,
        },
        {
          baseline: {
            id: 'baseline-002',
            name: '高功率基线',
            power_curve: powerCurve.map((item) => ({
              ...item,
              value: Number((item.value + 12).toFixed(1)),
            })),
            voltage_curve: voltageCurve.map((item) => ({
              ...item,
              value: Number((item.value + 2).toFixed(1)),
            })),
            tolerance_percent: 15,
          },
          metric_curves: [
            {
              metric_key: 'power',
              metric_name: '功率',
              unit: 'kW',
              color: '#409EFF',
              edc_channel_id: '2349-199',
              source_channel_name: '总有功功率',
              source_channel_label: 'SSTW 380V-220V電力 · 三相智能电表 / 总有功功率 / kW',
              baseline_curve: powerCurve.map((item) => ({
                ...item,
                value: Number((item.value + 12).toFixed(1)),
              })),
              current_curve: powerCurve,
            },
            {
              metric_key: 'voltage',
              metric_name: '电压',
              unit: 'V',
              color: '#67C23A',
              edc_channel_id: '2349-128',
              source_channel_name: 'A相电压',
              source_channel_label: 'SSTW 380V-220V電力 · 三相智能电表 / A相电压 / V',
              baseline_curve: voltageCurve.map((item) => ({
                ...item,
                value: Number((item.value + 2).toFixed(1)),
              })),
              current_curve: voltageCurve,
            },
            {
              metric_key: 'temperature',
              metric_name: '炉温',
              unit: '°C',
              color: '#E6A23C',
              edc_channel_id: '2054-128',
              source_channel_name: '热电偶温度采集通道',
              source_channel_label: 'A-1溫度 · 热电偶温度采集器 / 热电偶温度采集通道 / ℃',
              baseline_curve: temperatureCurve.map((item) => ({
                ...item,
                value: Number((item.value + 10).toFixed(1)),
              })),
              current_curve: temperatureCurve,
            },
            {
              metric_key: 'pressure',
              metric_name: '炉压',
              unit: 'MPa',
              color: '#F56C6C',
              edc_channel_id: '769-128',
              source_channel_name: 'AD_CH1',
              source_channel_label: '防水型智慧電流信號轉換器 / AD_CH1 / 外部传感器决定',
              baseline_curve: pressureCurve.map((item) => ({
                ...item,
                value: Number((item.value + 0.04).toFixed(2)),
              })),
              current_curve: pressureCurve,
            },
          ],
          deviation_ranges: [
            {
              start: powerCurve[20]?.timestamp,
              end: powerCurve[28]?.timestamp,
              deviation: 14.2,
            },
          ],
          max_deviation: 14.2,
          avg_deviation: 7.1,
        },
      ],
      deviation_ranges: [
        {
          start: powerCurve[10]?.timestamp,
          end: powerCurve[16]?.timestamp,
          deviation: 18.5,
        },
      ],
      max_deviation: 18.5,
      avg_deviation: 9.2,
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
          timestamp: '2026-03-13T08:37:00Z',
          event_type: 'window_check',
          title: '窗口判定',
          detail: '连续不一致 4 分钟，阈值 8 分钟',
        },
        {
          timestamp: '2026-03-13T08:39:00Z',
          event_type: 'abnormal',
          title: '判定异常',
          detail: '异常原因：time_offset_exceed',
        },
      ],
    })
  })

  await page.route('**/api/heats/issue-heat', async (route) => {
    if (route.request().method() === 'PATCH') {
      const payload = JSON.parse(route.request().postData() || '{}')
      await fulfillJson(route, {
        id: 'issue-heat',
        heat_no: 'H20260313-001',
        description: null,
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

    await route.fallback()
  })
}

test.describe('EDC issue acceptance checks', () => {
  test('dashboard range buttons request the target durations and update active state', async ({
    page,
  }) => {
    const durations: string[] = []
    await mockDashboardRanges(page)
    await page.route('**/api/dashboard/realtime?duration=*', async (route) => {
      const url = new URL(route.request().url())
      durations.push(url.searchParams.get('duration') || '')
      await route.fallback()
    })

    await page.goto('')
    await expect(page.getByTestId('dashboard-page')).toBeVisible()

    await page.getByTestId('dashboard-range-6h').click()
    await expect(page.getByTestId('dashboard-range-6h')).toHaveClass(/bg-white/)
    await expect(page.getByText(/标准基线 v2\.1 · 6小时/)).toBeVisible()

    await page.getByTestId('dashboard-range-24h').click()
    await expect(page.getByTestId('dashboard-range-24h')).toHaveClass(/bg-white/)
    await expect(page.getByText(/标准基线 v2\.1 · 24小时/)).toBeVisible()
    await expect(page.getByTestId('dashboard-source-summary')).toBeVisible()
    await expect.poll(() => durations.filter((item) => item === '6h').length).toBeGreaterThan(0)
    await expect.poll(() => durations.filter((item) => item === '24h').length).toBeGreaterThan(0)
  })

  test('baseline wizard keeps chart picking, zoom dragging, and fullscreen state in sync', async ({
    page,
  }) => {
    await mockBaselineWizardAcceptance(page)
    await page.goto('baselines')
    await page.getByTestId('baseline-create-button').click()
    await expect(page.getByTestId('baseline-wizard-definition-select')).toContainText(
      '真实数据基线定义'
    )
    await page.getByTestId('baseline-wizard-name-input').fill('Issue 验收基线')
    await page.getByTestId('baseline-wizard-next').click()

    const startItem = page.getByTestId('baseline-wizard-start-form-item')
    const endItem = page.getByTestId('baseline-wizard-end-form-item')
    const startBox = await startItem.boundingBox()
    const endBox = await endItem.boundingBox()
    expect(startBox).not.toBeNull()
    expect(endBox).not.toBeNull()
    expect(endBox?.y || 0).toBeGreaterThan(startBox?.y || 0)

    await expect(page.getByText(/峰值功率/)).toBeVisible()
    await expect(page.getByText(/\d+\s?kW/).first()).toBeVisible()
    await expect(page.getByText(/天 .*小时 .*分钟 .*秒/)).toBeVisible()

    const selectionState = page.getByTestId('baseline-wizard-selection-state')
    const originalStart = await selectionState.getAttribute('data-start')
    const originalEnd = await selectionState.getAttribute('data-end')

    await page.getByTestId('baseline-wizard-pick-start').click()
    await clickChartAt(page, 'baseline-wizard-chart', 0.2, 0.35)
    await expect(selectionState).toHaveAttribute('data-boundary', 'end')
    await expect
      .poll(async () => await selectionState.getAttribute('data-start'))
      .not.toBe(originalStart)

    await page.getByTestId('baseline-wizard-pick-end').click()
    await clickChartAt(page, 'baseline-wizard-chart', 0.72, 0.35)
    await expect(selectionState).toHaveAttribute('data-boundary', 'start')
    await expect
      .poll(async () => await selectionState.getAttribute('data-end'))
      .not.toBe(originalEnd)

    const startAfterPick = await selectionState.getAttribute('data-start')
    const endAfterPick = await selectionState.getAttribute('data-end')
    await wheelChartAt(page, 'baseline-wizard-chart', 0.5, 0.4, -600)
    await expect
      .poll(async () => Number(await selectionState.getAttribute('data-zoom-start')))
      .toBeGreaterThan(0)
    await expect
      .poll(async () => Number(await selectionState.getAttribute('data-zoom-end')))
      .toBeLessThan(100)

    const zoomStartBeforeDrag = Number(await selectionState.getAttribute('data-zoom-start'))
    await dragChartAt(
      page,
      'baseline-wizard-chart',
      { xRatio: 0.7, yRatio: 0.38 },
      { xRatio: 0.56, yRatio: 0.38 }
    )
    await expect
      .poll(async () => Number(await selectionState.getAttribute('data-zoom-start')))
      .not.toBe(zoomStartBeforeDrag)
    await expect(selectionState).toHaveAttribute('data-start', startAfterPick || '')
    await expect(selectionState).toHaveAttribute('data-end', endAfterPick || '')

    await page.getByTestId('baseline-wizard-fullscreen-button').click()
    const dialog = page.getByTestId('baseline-wizard-fullscreen-dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog.getByRole('button', { name: '选起点' })).toBeVisible()
    await expect(dialog.getByRole('button', { name: '选终点' })).toBeVisible()
    await expect(dialog.getByText(/选点区间/)).toBeVisible()
    await expect(dialog.getByText(/先选起点再选终点/)).toBeVisible()
    await expect(dialog.getByTestId('baseline-wizard-fullscreen-start-form-item')).toBeVisible()
    await expect(dialog.getByTestId('baseline-wizard-fullscreen-end-form-item')).toBeVisible()
    await expect(selectionState).toHaveAttribute('data-fullscreen', 'true')

    const endBeforeFullscreenPick = await selectionState.getAttribute('data-end')
    await dialog.getByTestId('baseline-wizard-fullscreen-pick-end').click()
    await clickChartAt(page, 'baseline-wizard-fullscreen-chart', 0.82, 0.35)
    await expect
      .poll(async () => await selectionState.getAttribute('data-end'))
      .not.toBe(endBeforeFullscreenPick)
  })

  test('baseline wizard does not fallback to local preview when real data is unavailable', async ({
    page,
  }) => {
    await mockBaselineWizardAcceptance(page, { previewUnavailable: true })

    await page.goto('baselines')
    await page.getByTestId('baseline-create-button').click()
    await expect(page.getByTestId('baseline-wizard-definition-select')).toContainText(
      '真实数据基线定义'
    )
    await page.getByTestId('baseline-wizard-name-input').fill('真实预览校验')
    await page.getByTestId('baseline-wizard-next').click()

    await expect(page.getByTestId('baseline-wizard-preview-empty')).toBeVisible()
    await expect(page.getByTestId('baseline-wizard-preview-empty')).toContainText(
      '未获取到真实预览数据'
    )
    await expect(page.getByTestId('baseline-wizard-selection-state')).toHaveAttribute('data-start', '')
    await expect(page.getByTestId('baseline-wizard-selection-state')).toHaveAttribute('data-end', '')

    await page.getByTestId('baseline-wizard-next').click()
    await expect(page.getByTestId('baseline-wizard-publish')).toHaveCount(0)
  })

  test('heat detail renders multi-metric comparison, abnormal ranges, and stable manual adjust interactions', async ({
    page,
  }) => {
    await mockHeatAcceptance(page)
    await page.goto('heats/issue-heat')

    await expect(page.getByTestId('heat-detail-page')).toBeVisible()
    await expect(page.getByText('异常', { exact: true }).first()).toBeVisible()
    await expect(page.getByTestId('heat-detail-deviation-status')).toContainText('偏差状态')
    await expect(page.getByTestId('heat-detail-deviation-status')).toContainText('异常')
    await expect(page.getByTestId('heat-detail-cut-status')).toContainText('切割执行状态')
    await expect(page.getByTestId('heat-detail-cut-status')).toContainText('正常')
    await expect(page.getByTestId('heat-compare-chart')).toHaveAttribute('data-series-count', '6')
    await expect(page.getByTestId('heat-source-binding-list')).toHaveCount(0)
    await page.getByRole('tab', { name: '高功率基线' }).click()
    await expect(page.getByTestId('heat-compare-chart')).toHaveAttribute('data-series-count', '8')

    await expect(page.getByTestId('heat-abnormal-range-list')).toBeVisible()
    await expect(page.getByTestId('heat-abnormal-range-item')).toHaveCount(1)
    await expect(page.getByText('判定异常')).toBeVisible()
    await expect(page.getByText('判定正常')).toHaveCount(0)

    await page.getByTestId('heat-manual-adjust-button').click()
    const dialog = page.getByTestId('manual-adjust-dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog.getByTestId('manual-adjust-baseline-tabs')).toBeVisible()
    await expect(dialog.getByRole('tab', { name: '高功率基线' })).toBeVisible()
    await expect(dialog.getByRole('button', { name: '选基线起点' })).toHaveCount(0)
    await expect(dialog.getByRole('button', { name: '选基线终点' })).toHaveCount(0)
    const chartRoot = dialog.getByTestId('manual-adjust-chart')
    const selectionState = dialog.getByTestId('manual-adjust-selection-state')
    await expect(chartRoot).toHaveAttribute('data-series-count', '8')
    await expect(chartRoot).toHaveAttribute('data-baseline-filled', 'true')
    await expect
      .poll(async () => Number(await selectionState.getAttribute('data-zoom-start')))
      .toBeGreaterThan(0)
    await expect
      .poll(async () => Number(await selectionState.getAttribute('data-zoom-end')))
      .toBeLessThan(100)
    const contextStart = Number(await selectionState.getAttribute('data-context-start'))
    const contextEnd = Number(await selectionState.getAttribute('data-context-end'))
    expect(contextEnd - contextStart).toBeGreaterThan(23 * 60 * 60 * 1000)

    await dialog.getByRole('tab', { name: '标准基线 v2.1' }).click()
    await expect(chartRoot).toHaveAttribute('data-series-count', '6')
    await dialog.getByRole('tab', { name: '高功率基线' }).click()
    await expect(chartRoot).toHaveAttribute('data-series-count', '8')

    const startInput = dialog.getByTestId('manual-adjust-start-field').locator('input').first()
    const endInput = dialog.getByTestId('manual-adjust-end-field').locator('input').first()
    const originalStart = await startInput.inputValue()
    const originalEnd = await endInput.inputValue()

    await clickChartAt(page, 'manual-adjust-chart', 0.12, 0.35)
    await expect.poll(async () => await startInput.inputValue()).not.toBe(originalStart)

    const pickedStart = await selectionState.getAttribute('data-start')
    const pickedEnd = await selectionState.getAttribute('data-end')
    await wheelChartAt(page, 'manual-adjust-chart', 0.5, 0.35, -800)
    await expect
      .poll(async () => Number(await selectionState.getAttribute('data-zoom-start')))
      .toBeGreaterThan(0)
    await expect
      .poll(async () => Number(await selectionState.getAttribute('data-zoom-end')))
      .toBeLessThan(100)

    const zoomStartBeforeDrag = Number(await selectionState.getAttribute('data-zoom-start'))
    await dragChartAt(
      page,
      'manual-adjust-chart',
      { xRatio: 0.68, yRatio: 0.35 },
      { xRatio: 0.54, yRatio: 0.35 }
    )
    await expect
      .poll(async () => Number(await selectionState.getAttribute('data-zoom-start')))
      .not.toBe(zoomStartBeforeDrag)
    await expect(selectionState).toHaveAttribute('data-start', pickedStart || '')
    await expect(selectionState).toHaveAttribute('data-end', pickedEnd || '')

    const originalRangeEnd = await chartRoot.getAttribute('data-range-end')
    const updatedEnd = '2026-03-13 17:12:00'
    await endInput.fill(updatedEnd)
    await endInput.press('Enter')
    await expect(endInput).toHaveValue(updatedEnd)
    await expect(endInput).not.toHaveValue(originalEnd)
    await expect(chartRoot).not.toHaveAttribute('data-range-end', originalRangeEnd || '')
    await expect(chartRoot).toHaveAttribute('data-series-count', '8')
  })
})
