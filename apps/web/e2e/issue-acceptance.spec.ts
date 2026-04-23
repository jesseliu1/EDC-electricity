import { expect, test, type Page, type Route } from '@playwright/test'

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

function toTimestampMs(iso: string) {
  return new Date(iso).getTime()
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

async function readChartRuntimeSeriesSummary(page: Page, testId: string) {
  const raw = (await page.getByTestId(testId).getAttribute('data-runtime-series-summary')) || '[]'
  return JSON.parse(raw) as Array<{ name: string; type: string; pointCount: number }>
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

async function mockDashboardCurrentHeat(
  page: Page,
  options?: {
    noCurrentHeat?: boolean
    compareFailure?: boolean
    noBaselineCompare?: boolean
  }
) {
  await page.route('**/api/dashboard/stats', async (route) => {
    await fulfillJson(route, {
      today_heats: 3,
      avg_deviation_score: 8.2,
      pending_tasks: 2,
      active_baseline: '标准基线 v2.1',
      normal_rate: 66.7,
    })
  })

  await page.route('**/api/dashboard/recent-heats?*', async (route) => {
    await fulfillJson(route, {
      items: [
        {
          id: 'issue-heat',
          heat_no: 'H20260313-001',
          start_time: toTimestampMs('2026-03-13T08:36:00Z'),
          end_time: toTimestampMs('2026-03-13T09:21:00Z'),
          status: 'abnormal',
          deviation_score: 18.5,
        },
        {
          id: 'completed-heat',
          heat_no: 'H20260313-000',
          start_time: toTimestampMs('2026-03-13T07:30:00Z'),
          end_time: toTimestampMs('2026-03-13T08:10:00Z'),
          status: 'normal',
          deviation_score: 3.2,
        },
      ],
    })
  })

  await page.route('**/api/tasks?*', async (route) => {
    const url = new URL(route.request().url())
    const status = url.searchParams.get('status')
    if (status === 'pending') {
      await fulfillJson(route, {
        items: [
          {
            id: 'task-pending-001',
            task_no: 'T20260313-001',
            heat_id: 'issue-heat',
            deviation_score: 18.5,
            cause_analysis: null,
            improvement: null,
            prevention: null,
            status: 'pending',
            created_at: toTimestampMs('2026-03-13T09:25:00Z'),
            updated_at: toTimestampMs('2026-03-13T09:28:00Z'),
            completed_at: null,
          },
        ],
        total: 1,
        page: 1,
        page_size: 3,
      })
      return
    }

    await fulfillJson(route, {
      items: [],
      total: 0,
      page: 1,
      page_size: 3,
    })
  })

  await page.route('**/api/heats?*', async (route) => {
    await fulfillJson(route, {
      items: options?.noCurrentHeat
        ? [
            {
              id: 'completed-heat',
              heat_no: 'H20260313-000',
              description: null,
              start_time: toTimestampMs('2026-03-13T07:30:00Z'),
              end_time: toTimestampMs('2026-03-13T08:10:00Z'),
              context_start_time: toTimestampMs('2026-03-13T07:00:00Z'),
              context_end_time: toTimestampMs('2026-03-13T08:20:00Z'),
              actual_context_start_time: toTimestampMs('2026-03-13T07:00:00Z'),
              actual_context_end_time: toTimestampMs('2026-03-13T08:20:00Z'),
              completion_status: 'completed',
              last_point_at: toTimestampMs('2026-03-13T08:10:00Z'),
              runtime_snapshot_status: 'ready',
              realtime_current: false,
              baseline_id: 'baseline-001',
              baseline_version_id: 'baseline-001',
              baseline_effective_from: null,
              deviation_score: 3.2,
              avg_deviation_score: 2.1,
              abnormal_duration_minutes: 0,
              schedule_tag: 'work',
              cut_reason: 'within_tolerance',
              cut_status: 'normal',
              major_issue: false,
              blocked_by_issue: false,
              status: 'normal',
              temperature: 1452,
              record_source: 'sealed_history',
              current_curve_source: 'sealed_history',
              baseline_curve_source: 'sealed_history',
              created_at: toTimestampMs('2026-03-13T07:30:00Z'),
            },
          ]
        : [
            {
              id: 'issue-heat',
              heat_no: 'H20260313-001',
              description: null,
              start_time: toTimestampMs('2026-03-13T08:36:00Z'),
              end_time: toTimestampMs('2026-03-13T09:21:00Z'),
              context_start_time: toTimestampMs('2026-03-13T07:36:00Z'),
              context_end_time: toTimestampMs('2026-03-13T10:21:00Z'),
              actual_context_start_time: toTimestampMs('2026-03-13T07:36:00Z'),
              actual_context_end_time: toTimestampMs('2026-03-13T10:21:00Z'),
              completion_status: 'in_progress',
              last_point_at: toTimestampMs('2026-03-13T09:21:00Z'),
              runtime_snapshot_status: 'ready',
              realtime_current: true,
              baseline_id: 'baseline-001',
              baseline_version_id: 'baseline-001',
              baseline_effective_from: null,
              deviation_score: 18.5,
              avg_deviation_score: 9.2,
              abnormal_duration_minutes: 4,
              schedule_tag: 'work',
              cut_reason: 'time_offset_exceed',
              cut_status: 'normal',
              major_issue: false,
              blocked_by_issue: false,
              status: 'abnormal',
              temperature: 1458,
              record_source: 'active_runtime',
              current_curve_source: 'active_runtime',
              baseline_curve_source: 'sealed_history',
              created_at: toTimestampMs('2026-03-13T08:36:00Z'),
            },
          ],
      total: 1,
      page: 1,
      page_size: 20,
      snapshot_status: 'ready',
      snapshot_watermark: toTimestampMs('2026-03-13T09:21:00Z'),
      last_refresh_started_at: toTimestampMs('2026-03-13T09:21:00Z'),
      last_refresh_completed_at: toTimestampMs('2026-03-13T09:21:05Z'),
      refresh_error: null,
      refresh_failure_count: 0,
    })
  })

  if (options?.noCurrentHeat) {
    return
  }

  await mockHeatAcceptance(page, { useExtendedCompareCurrentCurve: true })

  if (options?.compareFailure) {
    await page.route('**/api/heats/issue-heat/compare', async (route) => {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: '当前炉次 compare 服务暂不可用' }),
      })
    })
    return
  }

  if (options?.noBaselineCompare) {
    await page.route('**/api/heats/issue-heat/compare', async (route) => {
      const heatStart = toTimestampMs('2026-03-13T08:36:00Z')
      const heatEnd = toTimestampMs('2026-03-13T09:21:00Z')
      await fulfillJson(route, {
        heat: {
          id: 'issue-heat',
          heat_no: 'H20260313-001',
          description: null,
          start_time: heatStart,
          end_time: heatEnd,
          context_start_time: toTimestampMs('2026-03-13T07:36:00Z'),
          context_end_time: toTimestampMs('2026-03-13T10:21:00Z'),
          actual_context_start_time: toTimestampMs('2026-03-13T07:36:00Z'),
          actual_context_end_time: toTimestampMs('2026-03-13T10:21:00Z'),
          completion_status: 'in_progress',
          last_point_at: heatEnd,
          runtime_snapshot_status: 'ready',
          realtime_current: true,
          baseline_id: 'baseline-001',
          baseline_version_id: 'baseline-001',
          baseline_effective_from: null,
          deviation_score: 18.5,
          avg_deviation_score: 9.2,
          abnormal_duration_minutes: 4,
          schedule_tag: 'work',
          cut_reason: 'time_offset_exceed',
          cut_status: 'normal',
          major_issue: false,
          blocked_by_issue: false,
          status: 'abnormal',
          temperature: 1458,
          record_source: 'active_runtime',
          current_curve_source: 'active_runtime',
          baseline_curve_source: 'sealed_history',
          created_at: heatStart,
          power_curve: buildCurvePoints('2026-03-13T08:36:00Z', 46, 1, 438, 6),
          voltage_curve: buildCurvePoints('2026-03-13T08:36:00Z', 46, 1, 386, 1.5),
        },
        baseline: null,
        baselines: [],
        deviation_ranges: [],
        deviation_score: null,
        avg_deviation_score: null,
      })
    })
  }
}

async function mockBaselineWizardAcceptance(
  page: Page,
  options?: { previewUnavailable?: boolean }
) {
  const powerCurve = buildCurvePoints('2026-03-19T08:00:00Z', 40, 1, 438, 6)
  const voltageCurve = buildCurvePoints('2026-03-19T08:00:00Z', 40, 1, 386, 1.5)
  let previewPollCount = 0

  const buildPreviewJobPayload = (status: 'running' | 'succeeded' | 'failed') => ({
    job_key: 'def-real:2026-03-19',
    definition_id: 'def-real',
    source_heat_id: null,
    status,
    range_start: toTimestampMs('2026-03-19T00:00:00Z'),
    range_end: toTimestampMs('2026-03-20T00:00:00Z'),
    curves_data:
      status === 'succeeded'
        ? [
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
          ]
        : [],
    last_error: status === 'failed' ? '未获取到真实预览数据，请检查宿主连接和通道绑定' : null,
    created_at: toTimestampMs('2026-03-19T08:00:00Z'),
    started_at: toTimestampMs('2026-03-19T08:00:01Z'),
    updated_at:
      status === 'succeeded'
        ? toTimestampMs('2026-03-19T08:00:05Z')
        : toTimestampMs('2026-03-19T08:00:02Z'),
    completed_at:
      status === 'succeeded'
        ? toTimestampMs('2026-03-19T08:00:05Z')
        : status === 'failed'
          ? toTimestampMs('2026-03-19T08:00:03Z')
          : null,
  })

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
          created_at: toTimestampMs('2026-03-19T00:00:00Z'),
          updated_at: toTimestampMs('2026-03-19T00:00:00Z'),
        },
      ],
      total: 1,
    })
  })
  await page.route('**/api/heats?*', async (route) => {
    await fulfillJson(route, {
      items: [
        {
          id: 'heat-real-001',
          heat_no: 'H20260319-001',
          description: null,
          start_time: toTimestampMs('2026-03-19T08:00:00Z'),
          end_time: toTimestampMs('2026-03-19T08:40:00Z'),
          completion_status: 'completed',
          last_point_at: toTimestampMs('2026-03-19T08:40:00Z'),
          baseline_version_id: null,
          baseline_effective_from: null,
          baseline_id: null,
          deviation_score: null,
          avg_deviation_score: null,
          abnormal_duration_minutes: null,
          schedule_tag: 'work',
          cut_reason: null,
          cut_status: 'normal',
          major_issue: false,
          blocked_by_issue: false,
          status: 'normal',
          temperature: 1458,
          created_at: toTimestampMs('2026-03-19T08:00:00Z'),
        },
      ],
      total: 1,
      page: 1,
      page_size: 50,
      snapshot_status: 'ready',
    })
  })
  await page.route('**/api/baseline-definitions/def-real/preview-jobs?*', async (route) => {
    if (route.request().method() === 'POST') {
      await fulfillJson(
        route,
        buildPreviewJobPayload(options?.previewUnavailable ? 'failed' : 'running')
      )
      return
    }

    if (options?.previewUnavailable) {
      await fulfillJson(route, buildPreviewJobPayload('failed'))
      return
    }

    previewPollCount += 1
    await fulfillJson(
      route,
      buildPreviewJobPayload(previewPollCount >= 2 ? 'succeeded' : 'running')
    )
  })
}

async function mockHeatAcceptance(
  page: Page,
  options?: { cutReason?: string; useExtendedCompareCurrentCurve?: boolean }
) {
  const heatStart = toTimestampMs('2026-03-13T08:36:00Z')
  const heatEnd = toTimestampMs('2026-03-13T09:21:00Z')
  const powerCurve = buildCurvePoints('2026-03-13T08:36:00Z', 46, 1, 438, 6)
  const voltageCurve = buildCurvePoints('2026-03-13T08:36:00Z', 46, 1, 386, 1.5)
  const temperatureCurve = buildCurvePoints('2026-03-13T08:36:00Z', 46, 1, 1462, 6)
  const pressureCurve = buildCurvePoints('2026-03-13T08:36:00Z', 46, 1, 0.82, 0.03)
  const comparePowerCurve = options?.useExtendedCompareCurrentCurve
    ? buildCurvePoints('2026-03-13T07:36:00Z', 166, 1, 438, 6)
    : powerCurve
  const compareVoltageCurve = options?.useExtendedCompareCurrentCurve
    ? buildCurvePoints('2026-03-13T07:36:00Z', 166, 1, 386, 1.5)
    : voltageCurve
  const compareTemperatureCurve = options?.useExtendedCompareCurrentCurve
    ? buildCurvePoints('2026-03-13T07:36:00Z', 166, 1, 1462, 6)
    : temperatureCurve
  const comparePressureCurve = options?.useExtendedCompareCurrentCurve
    ? buildCurvePoints('2026-03-13T07:36:00Z', 166, 1, 0.82, 0.03)
    : pressureCurve
  const contextStart = comparePowerCurve[0]?.timestamp ?? heatStart
  const contextEnd = comparePowerCurve[comparePowerCurve.length - 1]?.timestamp ?? heatEnd
  const cutReason = options?.cutReason || 'time_offset_exceed'

  await page.route('**/api/heats/issue-heat', async (route) => {
    await fulfillJson(route, {
      id: 'issue-heat',
      heat_no: 'H20260313-001',
      description: null,
      start_time: heatStart,
      end_time: heatEnd,
      context_start_time: contextStart,
      context_end_time: contextEnd,
      baseline_id: 'baseline-001',
      deviation_score: 18.5,
      avg_deviation_score: 9.2,
      abnormal_duration_minutes: 4,
      schedule_tag: 'work',
      cut_reason: cutReason,
      cut_status: 'normal',
      major_issue: false,
      blocked_by_issue: false,
      status: 'abnormal',
      temperature: 1458,
      created_at: heatStart,
    })
  })

  await page.route('**/api/heats/issue-heat/curve', async (route) => {
    await fulfillJson(route, {
      id: 'issue-heat',
      heat_no: 'H20260313-001',
      description: null,
      start_time: heatStart,
      end_time: heatEnd,
      context_start_time: contextStart,
      context_end_time: contextEnd,
      baseline_id: 'baseline-001',
      deviation_score: 18.5,
      avg_deviation_score: 9.2,
      abnormal_duration_minutes: 4,
      schedule_tag: 'work',
      cut_reason: cutReason,
      cut_status: 'normal',
      major_issue: false,
      blocked_by_issue: false,
      status: 'abnormal',
      temperature: 1458,
      created_at: heatStart,
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
        start_time: heatStart,
        end_time: heatEnd,
        context_start_time: contextStart,
        context_end_time: contextEnd,
        baseline_id: 'baseline-001',
        deviation_score: 18.5,
        avg_deviation_score: 9.2,
        abnormal_duration_minutes: 4,
        schedule_tag: 'work',
        cut_reason: cutReason,
        cut_status: 'normal',
        major_issue: false,
        blocked_by_issue: false,
        status: 'abnormal',
        temperature: 1458,
        created_at: heatStart,
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
              current_curve: comparePowerCurve,
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
              current_curve: compareVoltageCurve,
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
              current_curve: compareTemperatureCurve,
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
              current_curve: comparePowerCurve,
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
              current_curve: compareVoltageCurve,
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
              current_curve: compareTemperatureCurve,
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
              current_curve: comparePressureCurve,
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
          detail: `异常原因：${cutReason}`,
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
        start_time: payload.start_time || heatStart,
        end_time: payload.end_time || heatEnd,
        context_start_time: contextStart,
        context_end_time: contextEnd,
        baseline_id: 'baseline-001',
        deviation_score: 18.5,
        avg_deviation_score: 9.2,
        abnormal_duration_minutes: 4,
        schedule_tag: 'work',
        cut_reason: cutReason,
        cut_status: 'normal',
        major_issue: false,
        blocked_by_issue: false,
        status: 'abnormal',
        temperature: 1458,
        created_at: heatStart,
      })
      return
    }

    await route.fallback()
  })
}

test.describe('EDC issue acceptance checks', () => {
  test('dashboard renders the current heat compare chart instead of realtime range controls', async ({
    page,
  }) => {
    await mockDashboardCurrentHeat(page)

    await page.goto('')
    await expect(page.getByTestId('dashboard-page')).toBeVisible()
    await expect(page.getByTestId('dashboard-current-heat-card')).toBeVisible()
    await expect(page.getByTestId('dashboard-current-heat-badge')).toHaveText('当前炉次')
    await expect(page.getByTestId('dashboard-current-heat-subtitle')).toContainText(
      '炉次 H20260313-001'
    )
    await expect(page.getByTestId('dashboard-current-heat-subtitle')).toContainText(
      '开始时间 2026-03-13 16:36'
    )
    await expect(page.getByTestId('dashboard-current-heat-subtitle')).toContainText(
      '对比基线 标准基线 v2.1'
    )
    await expect(page.getByTestId('dashboard-current-heat-chart')).toBeVisible()
    await expect(page.getByTestId('dashboard-current-heat-chart')).toHaveAttribute(
      'data-series-count',
      '6'
    )
    await expect(page.getByTestId('dashboard-current-heat-chart')).toHaveAttribute(
      'data-active-baseline-name',
      '标准基线 v2.1'
    )
    await expect(page.getByTestId('dashboard-current-heat-chart')).toHaveAttribute(
      'data-display-start',
      String(toTimestampMs('2026-03-13T07:36:00Z'))
    )
    await expect(page.getByTestId('dashboard-range-1h')).toHaveCount(0)
    await expect(page.getByRole('tab', { name: '标准基线 v2.1' })).toHaveCount(0)
  })

  test('dashboard shows an empty state when there is no current heat', async ({ page }) => {
    await mockDashboardCurrentHeat(page, { noCurrentHeat: true })

    await page.goto('')
    await expect(page.getByTestId('dashboard-page')).toBeVisible()
    await expect(page.getByTestId('dashboard-current-heat-empty')).toContainText(
      '当前无进行中的炉次'
    )
    await expect(page.getByTestId('dashboard-current-heat-chart')).toHaveCount(0)
    await expect(page.getByTestId('dashboard-load-warning')).toHaveCount(0)
  })

  test('dashboard shows a compare error state when current heat compare fails', async ({
    page,
  }) => {
    await mockDashboardCurrentHeat(page, { compareFailure: true })

    await page.goto('')
    await expect(page.getByTestId('dashboard-page')).toBeVisible()
    await expect(page.getByTestId('dashboard-current-heat-error')).toContainText(
      '当前炉次对比加载失败'
    )
    await expect(page.getByTestId('dashboard-current-heat-error')).toContainText(
      '当前炉次 compare 服务暂不可用'
    )
    await expect(page.getByTestId('dashboard-load-warning')).toContainText(
      '当前炉次 compare 服务暂不可用'
    )
  })

  test('dashboard shows a no-baseline empty state when compare returns no baseline data', async ({
    page,
  }) => {
    await mockDashboardCurrentHeat(page, { noBaselineCompare: true })

    await page.goto('')
    await expect(page.getByTestId('dashboard-page')).toBeVisible()
    await expect(page.getByTestId('dashboard-current-heat-empty')).toContainText(
      '当前炉次尚未绑定可对比基线'
    )
    await expect(page.getByTestId('dashboard-current-heat-chart')).toHaveCount(0)
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
    await expect(page.getByTestId('baseline-wizard-preview-loading')).toBeVisible()
    await expect(page.getByTestId('baseline-wizard-refresh-candidates')).toBeDisabled()
    await expect(page.getByText(/正在读取所选日期的整天真实曲线/)).toBeVisible()

    const startItem = page.getByTestId('baseline-wizard-start-form-item')
    const endItem = page.getByTestId('baseline-wizard-end-form-item')
    const startBox = await startItem.boundingBox()
    const endBox = await endItem.boundingBox()
    expect(startBox).not.toBeNull()
    expect(endBox).not.toBeNull()
    expect(endBox?.y || 0).toBeGreaterThan(startBox?.y || 0)
    await expect(page.getByTestId('baseline-wizard-refresh-candidates')).toBeEnabled()
    await expect(page.getByText(/整天真实曲线最近一次成功更新时间/)).toBeVisible()

    await expect(page.getByText(/峰值功率/)).toBeVisible()
    const selectionState = page.getByTestId('baseline-wizard-selection-state')
    await expect(selectionState).toHaveAttribute('data-start', '')
    await expect(selectionState).toHaveAttribute('data-end', '')
    await expect(page.getByTestId('baseline-wizard-selected-duration-value')).toHaveText(
      '0天 0小时 0分钟 0秒'
    )
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
    await expect(page.getByTestId('baseline-wizard-selected-duration-value')).not.toHaveText(
      '0天 0小时 0分钟 0秒'
    )

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

  test('baseline wizard keeps minute duration stable when end boundary shifts by one second', async ({
    page,
  }) => {
    await mockBaselineWizardAcceptance(page)
    await page.goto('baselines')
    await page.getByTestId('baseline-create-button').click()
    await page.getByTestId('baseline-wizard-name-input').fill('分钟时长稳定性')
    await page.getByTestId('baseline-wizard-next').click()
    const heatCandidate = page.getByTestId('baseline-wizard-heat-candidate-list').getByText('H20260319-001')
    await expect(heatCandidate).toBeVisible()
    await heatCandidate.click()

    const durationValue = page.getByTestId('baseline-wizard-selected-duration-value')
    await expect(durationValue).toHaveText('0天 0小时 40分钟 0秒', { timeout: 15000 })

    await page.getByTestId('baseline-wizard-range-end-plus-second').click()
    await expect(durationValue).toHaveText('0天 0小时 40分钟 0秒')

    await page.getByTestId('baseline-wizard-range-end-minus-second').click()
    await expect(durationValue).toHaveText('0天 0小时 40分钟 0秒')
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
    await expect(page.getByTestId('baseline-wizard-next')).toBeDisabled()
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
    await expect(page.getByTestId('heat-detail-time-window-card')).toContainText('当前炉次时间')
    await expect(page.getByTestId('heat-detail-time-window-card')).toContainText('曲线覆盖窗口时间')
    await expect(page.getByText('声明上下文窗口')).toHaveCount(0)
    await expect(page.getByText('按实际覆盖范围展示')).toHaveCount(0)
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

  test('heat detail compare panel keeps fullscreen state and baseline selection in sync', async ({
    page,
  }) => {
    await mockHeatAcceptance(page, { useExtendedCompareCurrentCurve: true })
    await page.goto('heats/issue-heat')

    await expect(page.getByTestId('heat-detail-page')).toBeVisible()
    await page.getByRole('tab', { name: '高功率基线' }).click()
    await expect(page.getByTestId('heat-compare-chart')).toHaveAttribute(
      'data-active-baseline-name',
      '高功率基线'
    )

    await page.getByTestId('heat-compare-fullscreen-button').click()
    const dialog = page.getByTestId('heat-compare-fullscreen-dialog')
    const fullscreenChart = dialog.getByTestId('heat-compare-fullscreen-chart')
    await expect(dialog).toBeVisible()
    await expect(fullscreenChart).toHaveAttribute('data-active-baseline-name', '高功率基线')
    await expect(fullscreenChart).toHaveAttribute(
      'data-display-start',
      String(toTimestampMs('2026-03-13T07:36:00Z'))
    )
    await expect(fullscreenChart).toHaveAttribute(
      'data-core-start',
      String(toTimestampMs('2026-03-13T08:36:00Z'))
    )

    await dialog.getByRole('tab', { name: '标准基线 v2.1' }).click()
    await expect(fullscreenChart).toHaveAttribute('data-active-baseline-name', '标准基线 v2.1')
    await expect(page.getByTestId('heat-compare-chart')).toHaveAttribute(
      'data-active-baseline-name',
      '标准基线 v2.1'
    )

    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    await expect(page.getByTestId('heat-compare-chart')).toHaveAttribute(
      'data-active-baseline-name',
      '标准基线 v2.1'
    )
  })

  test('heat detail compare chart keeps extended current curves and exposes context window', async ({
    page,
  }) => {
    await mockHeatAcceptance(page, { useExtendedCompareCurrentCurve: true })
    await page.goto('heats/issue-heat')

    await expect(page.getByTestId('heat-detail-page')).toBeVisible()
    await expect(page.getByTestId('heat-compare-chart')).toHaveAttribute(
      'data-display-start',
      String(toTimestampMs('2026-03-13T07:36:00Z'))
    )
    await expect(page.getByTestId('heat-compare-chart')).toHaveAttribute(
      'data-display-end',
      String(toTimestampMs('2026-03-13T10:21:00Z'))
    )
    await expect(page.getByTestId('heat-compare-chart')).toHaveAttribute(
      'data-core-start',
      String(toTimestampMs('2026-03-13T08:36:00Z'))
    )
    await expect(page.getByTestId('heat-compare-chart')).toHaveAttribute(
      'data-core-end',
      String(toTimestampMs('2026-03-13T09:21:00Z'))
    )

    const defaultSeries = await readChartRuntimeSeriesSummary(page, 'heat-compare-chart')
    expect(defaultSeries[0]?.pointCount).toBe(46)
    expect(defaultSeries[1]?.pointCount).toBe(166)

    await page.getByRole('tab', { name: '高功率基线' }).click()
    const alternateSeries = await readChartRuntimeSeriesSummary(page, 'heat-compare-chart')
    expect(alternateSeries[0]?.pointCount).toBe(46)
    expect(alternateSeries[1]?.pointCount).toBe(166)
  })

  test('heat detail localizes abnormal range labels and inferred cut reasons', async ({ page }) => {
    await mockHeatAcceptance(page, { cutReason: 'live_inferred' })
    await page.goto('heats/issue-heat')

    const abnormalRangeItem = page.getByTestId('heat-abnormal-range-item').first()
    await expect(abnormalRangeItem).toContainText('偏差')
    await expect(abnormalRangeItem).not.toContainText('Deviation')
    await expect(page.getByTestId('heat-detail-cut-reason')).toContainText('由实时曲线推断')
    await expect(page.getByTestId('heat-detail-cut-reason')).not.toContainText(
      'heat.cutReason.live_inferred'
    )
    await expect(page.getByText('异常原因：由实时曲线推断')).toBeVisible()
  })
})
