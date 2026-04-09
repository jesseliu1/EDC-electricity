import { expect, test, type Page, type Route } from '@playwright/test'

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body)
  })
}

async function fulfillPdf(route: Route, filename: string) {
  await route.fulfill({
    status: 200,
    contentType: 'application/pdf',
    headers: {
      'content-disposition': `attachment; filename="${filename}"`
    },
    body: '%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF'
  })
}

async function mockRuntimeStatus(page: Page, body?: Record<string, unknown>) {
  await page.route('**/api/settings/runtime-status**', async route => {
    await fulfillJson(route, {
      overall_code: 'ready',
      host: {
        is_connected: true,
        machine_name: 'EDC Test Gateway',
        last_sync_label: '2026-03-20 15:30:00',
        meta: {
          source: 'http://60.251.229.32',
          sensor_count: 26,
          channel_count: 2286,
          enabled_channel_count: 6
        }
      },
      edc: {
        configured: true,
        base_url: 'http://60.251.229.32',
        username_present: true,
        host_channel_total: 6,
        enabled_channel_count: 6
      },
      active_baseline: {
        id: 'baseline-001',
        name: '标准基线 v2.1',
        status: 'published'
      },
      runtime: {
        showtime_enabled: false,
        live_heat_inference_enabled: true,
        baseline_length_scope_mode: 'definition',
        plant_timezone: 'Asia/Shanghai',
        cutting_mode: 'signal_inference',
        fixed_interval_minutes: null
      },
      pipelines: {
        dashboard: { code: 'ready', ready: true },
        heats: { code: 'ready', ready: true },
        inbox: { code: 'ready', ready: true },
        tasks: { code: 'ready', ready: true },
        reports: { code: 'ready', ready: true },
        baselines: { code: 'ready', ready: true },
        settings: { code: 'ready', ready: true }
      },
      ...body
    })
  })
}

async function mockBaselineDefinitionMutations(page: Page) {
  await page.route('**/api/baseline-definitions', async route => {
    if (route.request().method() === 'GET') {
      await fulfillJson(route, {
        items: [
          {
            id: 'def-001',
            definition_name: '标准熔炼基线',
            description: '中频炉标准熔炼过程，适用于常规铸铁生产',
            expected_duration_minutes: 30,
            status: 'active',
            metrics: [
              { id: 'metric-001', name: '功率', unit: 'kW', color: '#409EFF', sort_order: 1, edc_channel_id: null },
              { id: 'metric-002', name: '电压', unit: 'V', color: '#67C23A', sort_order: 2, edc_channel_id: null },
              { id: 'metric-003', name: '炉温', unit: '°C', color: '#E6A23C', sort_order: 3, edc_channel_id: null }
            ],
            instance_count: 0,
            created_at: '2026-03-12T08:00:00Z',
            updated_at: '2026-03-12T08:00:00Z'
          }
        ]
      })
      return
    }

    if (route.request().method() !== 'POST') {
      await route.fallback()
      return
    }

    await fulfillJson(route, {
      id: 'def-e2e',
      definition_name: 'E2E 基线定义',
      description: '用于自动化测试',
      expected_duration_minutes: 55,
      status: 'active',
      metrics: [],
      instance_count: 0,
      created_at: '2026-03-12T08:00:00Z',
      updated_at: '2026-03-12T08:00:00Z'
    })
  })

  await page.route('**/api/baseline-definitions/def-001/metrics', async route => {
    if (route.request().method() !== 'POST') {
      await route.fallback()
      return
    }

    await fulfillJson(route, {
      id: 'def-001',
      definition_name: '标准熔炼基线',
      description: '中频炉标准熔炼过程，适用于常规铸铁生产',
      expected_duration_minutes: 30,
      status: 'active',
      metrics: [
        { id: 'metric-001', name: '功率', unit: 'kW', color: '#409EFF', sort_order: 1, edc_channel_id: null },
        { id: 'metric-002', name: '电压', unit: 'V', color: '#67C23A', sort_order: 2, edc_channel_id: null },
        { id: 'metric-003', name: '炉温', unit: '°C', color: '#E6A23C', sort_order: 3, edc_channel_id: null },
        { id: 'metric-e2e', name: '氧含量', unit: '%', color: '#7c3aed', sort_order: 4, edc_channel_id: null }
      ],
      instance_count: 0,
      created_at: '2026-03-12T08:00:00Z',
      updated_at: '2026-03-12T08:30:00Z'
    })
  })

  await page.route('**/api/settings/host-channels**', async route => {
    await fulfillJson(route, {
      items: [
        {
          id: '2349-199',
          device_name: 'SSTW 380V-220V電力 · 三相智能电表',
          device_type: '三相智能电表',
          area: 'SSTW 380V-220V電力',
          suid: '2349',
          cuid: '199',
          channel_name: '总有功功率',
          unit: 'kW',
          last_value: '--',
          status: 'online'
        },
        {
          id: '2349-128',
          device_name: 'SSTW 380V-220V電力 · 三相智能电表',
          device_type: '三相智能电表',
          area: 'SSTW 380V-220V電力',
          suid: '2349',
          cuid: '128',
          channel_name: 'A相电压',
          unit: 'V',
          last_value: '--',
          status: 'online'
        },
        {
          id: '2349-130',
          device_name: 'SSTW 380V-220V電力 · 三相智能电表',
          device_type: '三相智能电表',
          area: 'SSTW 380V-220V電力',
          suid: '2349',
          cuid: '130',
          channel_name: 'B相电压',
          unit: 'V',
          last_value: '--',
          status: 'online'
        },
        {
          id: '2054-128',
          device_name: 'A-1溫度 · 热电偶温度采集器',
          device_type: '热电偶温度采集器',
          area: 'A-1溫度',
          suid: '2054',
          cuid: '128',
          channel_name: '热电偶温度采集通道',
          unit: '℃',
          last_value: '--',
          status: 'online'
        }
      ],
      total: 2
    })
  })
}

async function mockReportsAndInbox(page: Page) {
  await page.route('**/api/reports/daily?**', async route => {
    await fulfillJson(route, {
      items: [
        {
          date: '2026-03-19',
          total_heats: 8,
          normal_heats: 6,
          abnormal_heats: 2,
          avg_deviation: 12.4,
          pending_tasks: 2,
          completed_tasks: 3,
          generated_at: '2026-03-19T23:00:00Z'
        }
      ],
      total: 1
    })
  })

  await page.route('**/api/reports/daily/2026-03-19', async route => {
    await fulfillJson(route, {
      date: '2026-03-19',
      total_heats: 8,
      normal_heats: 6,
      abnormal_heats: 2,
      avg_deviation: 12.4,
      pending_tasks: 2,
      completed_tasks: 3,
      generated_at: '2026-03-19T23:00:00Z',
      normal_rate: 75,
      effective_hours: 6,
      top_deviations: []
    })
  })

  await page.route('**/api/heats?**', async route => {
    await fulfillJson(route, {
      items: [
        {
          id: 'inbox-heat-1',
          heat_no: 'H20260319-007',
          description: null,
          start_time: '2026-03-19T13:15:00Z',
          end_time: '2026-03-19T14:00:00Z',
          baseline_id: 'baseline-001',
          deviation_score: 24.6,
          avg_deviation_score: 11.2,
          abnormal_duration_minutes: 4,
          schedule_tag: 'work',
          cut_reason: 'time_offset_exceed',
          cut_status: 'normal',
          major_issue: false,
          blocked_by_issue: false,
          status: 'abnormal',
          temperature: 1458,
          created_at: '2026-03-19T13:15:00Z',
          record_source: 'historical_import',
          current_curve_source: 'live_edc',
          baseline_curve_source: 'none'
        }
      ],
      total: 1,
      page: 1,
      page_size: 10
    })
  })

  await page.route('**/api/heats/inbox-heat-1/compare', async route => {
    await fulfillJson(route, {
      heat: {
        id: 'inbox-heat-1',
        heat_no: 'H20260319-007',
        description: null,
        start_time: '2026-03-19T13:15:00Z',
        end_time: '2026-03-19T14:00:00Z',
        baseline_id: 'baseline-001',
        deviation_score: 24.6,
        avg_deviation_score: 11.2,
        abnormal_duration_minutes: 4,
        schedule_tag: 'work',
        cut_reason: 'time_offset_exceed',
        cut_status: 'normal',
        major_issue: false,
        blocked_by_issue: false,
        status: 'abnormal',
        temperature: 1458,
        created_at: '2026-03-19T13:15:00Z',
        power_curve: [],
        voltage_curve: []
      },
      baselines: [],
      deviation_ranges: [],
      max_deviation: 24.6,
      avg_deviation: 11.2
    })
  })

  await page.route('**/api/heats/inbox-heat-1/cutting-timeline', async route => {
    await fulfillJson(route, {
      heat_id: 'inbox-heat-1',
      events: []
    })
  })
}

async function mockBaselineLibrary(page: Page) {
  await page.route(/\/api\/baselines\/active$/, async route => {
    await fulfillJson(route, {
      id: 'baseline-001',
      name: '标准基线 v2.1',
      status: 'published',
      version: 2
    })
  })

  await page.route(/\/api\/baselines(\?.*)?$/, async route => {
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
          published_at: '2026-03-20T08:45:00Z'
        },
        {
          id: 'baseline-002',
          name: '高功率基线',
          description: '用于高功率工艺的对比基线',
          definition_id: 'def-002',
          definition_name: '高功率熔炼基线',
          source_heat_id: 'heat-002',
          selected_start_time: '2026-03-20T09:00:00Z',
          selected_end_time: '2026-03-20T09:45:00Z',
          tolerance_percent: 10,
          status: 'draft',
          version: 1,
          curve_source: 'live_edc',
          created_at: '2026-03-20T09:50:00Z',
          updated_at: '2026-03-20T09:50:00Z',
          published_at: null
        },
        {
          id: 'baseline-003',
          name: '压力监控基线',
          description: '包含炉压监控的对比基线',
          definition_id: 'def-002',
          definition_name: '高功率熔炼基线',
          source_heat_id: 'heat-003',
          selected_start_time: '2026-03-20T10:00:00Z',
          selected_end_time: '2026-03-20T10:40:00Z',
          tolerance_percent: 14,
          status: 'disabled',
          version: 3,
          curve_source: 'live_edc',
          created_at: '2026-03-20T10:45:00Z',
          updated_at: '2026-03-20T10:45:00Z',
          published_at: '2026-03-20T10:50:00Z'
        }
      ],
      total: 3
    })
  })
}

async function mockBaselineDetail(page: Page) {
  await mockBaselineLibrary(page)

  await page.route(/\/api\/baselines\/baseline-001$/, async route => {
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
      temperature: null
    })
  })
}

async function mockBaselineLibraryWithRefreshCounters(
  page: Page,
  counters: { list: number; active: number }
) {
  await page.route(/\/api\/baselines\/active$/, async route => {
    counters.active += 1
    await fulfillJson(route, {
      id: 'baseline-001',
      name: '标准基线 v2.1',
      status: 'published',
      version: 2
    })
  })

  await page.route(/\/api\/baselines(\?.*)?$/, async route => {
    counters.list += 1
    await new Promise(resolve => setTimeout(resolve, 200))
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
          published_at: '2026-03-20T08:45:00Z'
        }
      ],
      total: 1
    })
  })
}

async function mockTaskWorkflow(page: Page) {
  const detailBody = {
    id: 'mock-task-1',
    task_no: 'T20260312-001',
    heat_id: 'heat-001',
    heat_no: 'H20260312-001',
    deviation_score: 18.2,
    status: 'in_progress',
    created_at: '2026-03-11T10:00:00Z',
    updated_at: '2026-03-12T10:00:00Z',
    completed_at: null,
    cause_analysis: '',
    improvement: '',
    prevention: '',
    analysis_snapshot: {}
  }

  const taskListBodies = {
    all: {
      items: [
        {
          id: 'mock-task-1',
          task_no: 'T20260312-001',
          heat_id: 'heat-001',
          deviation_score: 18.2,
          cause_analysis: null,
          improvement: null,
          prevention: null,
          status: 'pending',
          created_at: '2026-03-11T10:00:00Z',
          updated_at: '2026-03-12T10:00:00Z',
          completed_at: null
        },
        {
          id: 'mock-task-2',
          task_no: 'T20260312-002',
          heat_id: 'heat-002',
          deviation_score: 12.4,
          cause_analysis: null,
          improvement: null,
          prevention: null,
          status: 'in_progress',
          created_at: '2026-03-11T11:00:00Z',
          updated_at: '2026-03-12T11:00:00Z',
          completed_at: null
        },
        {
          id: 'mock-task-3',
          task_no: 'T20260312-003',
          heat_id: 'heat-special-003',
          deviation_score: null,
          cause_analysis: null,
          improvement: null,
          prevention: null,
          status: 'cancelled',
          created_at: '2026-03-11T12:00:00Z',
          updated_at: '2026-03-12T12:00:00Z',
          completed_at: null
        }
      ],
      total: 10,
      page: 1,
      page_size: 10
    },
    pending: {
      items: [
        {
          id: 'mock-task-1',
          task_no: 'T20260312-001',
          heat_id: 'heat-001',
          deviation_score: 18.2,
          cause_analysis: null,
          improvement: null,
          prevention: null,
          status: 'pending',
          created_at: '2026-03-11T10:00:00Z',
          updated_at: '2026-03-12T10:00:00Z',
          completed_at: null
        }
      ],
      total: 1,
      page: 1,
      page_size: 1
    },
    in_progress: {
      items: [],
      total: 2,
      page: 1,
      page_size: 1
    },
    completed: {
      items: [],
      total: 3,
      page: 1,
      page_size: 1
    },
    cancelled: {
      items: [],
      total: 4,
      page: 1,
      page_size: 1
    }
  } as const

  await page.route('**/api/tasks?**', async route => {
    const url = new URL(route.request().url())
    const status = url.searchParams.get('status')
    if (status === 'pending' || status === 'in_progress' || status === 'completed' || status === 'cancelled') {
      await fulfillJson(route, taskListBodies[status])
      return
    }

    await fulfillJson(route, taskListBodies.all)
  })

  await page.route('**/api/tasks/mock-task-1', async route => {
    if (route.request().method() === 'PATCH') {
      await fulfillJson(route, {
        ...detailBody,
        ...JSON.parse(route.request().postData() || '{}')
      })
      return
    }

    await fulfillJson(route, detailBody)
  })

  await page.route('**/api/tasks/mock-task-1/complete', async route => {
    const payload = JSON.parse(route.request().postData() || '{}')
    await fulfillJson(route, {
      ...detailBody,
      ...payload,
      status: 'completed',
      completed_at: '2026-03-12T12:00:00Z'
    })
  })
}

async function mockDashboardOverview(page: Page) {
  await page.route('**/api/dashboard/stats', async route => {
    await fulfillJson(route, {
      today_heats: 8,
      avg_deviation: 12.4,
      pending_tasks: 3,
      active_baseline: '标准基线 v2.1',
      normal_rate: 75
    })
  })

  await page.route('**/api/dashboard/realtime?**', async route => {
    await fulfillJson(route, {
      timestamp: '2026-03-20T08:30:00Z',
      baseline_id: 'baseline-001',
      baseline_name: '标准基线 v2.1',
      power_source_label: '总有功功率',
      voltage_source_label: 'A相电压',
      power: [],
      voltage: [],
      baseline_power: [],
      baseline_voltage: []
    })
  })

  await page.route('**/api/dashboard/recent-heats?**', async route => {
    await fulfillJson(route, {
      items: [
        {
          id: 'heat-001',
          heat_no: 'H20260320-001',
          start_time: '2026-03-20T08:00:00Z',
          end_time: '2026-03-20T08:35:00Z',
          status: 'abnormal',
          deviation_score: 18.2
        }
      ]
    })
  })
}

async function mockSettingsWorkflow(page: Page) {
  await page.route('**/api/settings', async route => {
    if (route.request().method() !== 'GET') {
      await route.fallback()
      return
    }

    await fulfillJson(route, {
      items: [
        { key: 'default_tolerance_percent', value: '15', description: null },
        { key: 'edc_base_url', value: 'http://localhost:8080', description: null },
        { key: 'edc_api_key', value: '', description: null },
        { key: 'report_generation_hour', value: '2', description: null },
        { key: 'cutting_mode', value: 'signal_inference', description: null },
        { key: 'fixed_interval_minutes', value: '', description: null },
        { key: 'time_tolerance_percent', value: '10', description: null },
        { key: 'major_issue_duration_minutes', value: '8', description: null },
        { key: 'plant_timezone', value: 'Asia/Shanghai', description: null },
        { key: 'work_start_time', value: '08:00', description: null },
        { key: 'work_end_time', value: '18:00', description: null },
        { key: 'break_periods', value: '12:00-13:00', description: null },
        { key: 'baseline_length_scope_mode', value: 'definition', description: null }
      ]
    })
  })

  await page.route('**/api/settings/host-connectivity-status', async route => {
    await fulfillJson(route, {
      is_connected: true,
      machine_name: 'EDC Test Gateway',
      last_sync_label: '2026-03-20 15:30:00',
      meta: {
        source: 'http://60.251.229.32',
        sensor_count: 26,
        channel_count: 2286,
        enabled_channel_count: 6
      }
    })
  })

  await page.route('**/api/settings/**', async route => {
    const method = route.request().method()
    if (method === 'PUT' || method === 'POST') {
      await fulfillJson(route, { ok: true })
      return
    }
    await route.fallback()
  })

  await page.route('**/api/heats/runtime/refresh', async route => {
    await fulfillJson(route, {
      success: true,
      refresh_status: 'running',
      snapshot_status: 'warming'
    })
  })
}

test.describe('EDC web extended coverage', () => {
  const latestSuccessMessage = (page: Page) =>
    page.locator('.el-message__content').filter({ hasText: '成功' }).last()

  test('dashboard quick links and sidebar routes are reachable', async ({ page }) => {
    await mockRuntimeStatus(page)
    await page.goto('')
    await expect(page.getByTestId('dashboard-page')).toBeVisible()

    await page.getByTestId('dashboard-quick-link-reports').click()
    await expect(page.getByTestId('report-list-page')).toBeVisible()

    await page.getByRole('button', { name: /基线定义/ }).click()
    await expect(page.getByTestId('baseline-definition-page')).toBeVisible()

    await page.getByRole('button', { name: /系统设置/ }).click()
    await expect(page.getByTestId('settings-page')).toBeVisible()
  })

  test('dashboard reads unified runtime status and surfaces host sync attention', async ({ page }) => {
    await mockRuntimeStatus(page, {
      overall_code: 'host_disconnected',
      host: {
        is_connected: false,
        machine_name: '--',
        last_sync_label: '--',
        meta: {
          source: '--',
          sensor_count: 0,
          channel_count: 0,
          enabled_channel_count: 0
        }
      },
      edc: {
        configured: true,
        base_url: 'http://60.251.229.32',
        username_present: true,
        host_channel_total: 0,
        enabled_channel_count: 0
      },
      pipelines: {
        dashboard: { code: 'host_disconnected', ready: false },
        heats: { code: 'host_disconnected', ready: false },
        inbox: { code: 'host_disconnected', ready: false },
        tasks: { code: 'host_disconnected', ready: false },
        reports: { code: 'host_disconnected', ready: false },
        baselines: { code: 'host_disconnected', ready: false },
        settings: { code: 'host_disconnected', ready: false }
      }
    })

    await page.goto('')
    await expect(page.getByTestId('dashboard-page')).toBeVisible()
    await expect(page.getByTestId('dashboard-runtime-banner')).toContainText('宿主尚未同步真实连接状态')
    await expect(page.getByText('等待宿主同步')).toBeVisible()
  })

  test('reports page reuses unified runtime attention state', async ({ page }) => {
    await mockRuntimeStatus(page, {
      overall_code: 'host_disconnected',
      host: {
        is_connected: false,
        machine_name: '--',
        last_sync_label: '--',
        meta: {
          source: '--',
          sensor_count: 0,
          channel_count: 0,
          enabled_channel_count: 0
        }
      },
      edc: {
        configured: true,
        base_url: 'http://60.251.229.32',
        username_present: true,
        host_channel_total: 0,
        enabled_channel_count: 0
      },
      pipelines: {
        dashboard: { code: 'host_disconnected', ready: false },
        heats: { code: 'host_disconnected', ready: false },
        inbox: { code: 'host_disconnected', ready: false },
        tasks: { code: 'host_disconnected', ready: false },
        reports: { code: 'host_disconnected', ready: false },
        baselines: { code: 'host_disconnected', ready: false }
      }
    })
    await page.route('**/api/reports/daily?**', async route => {
      await fulfillJson(route, { items: [], total: 0 })
    })

    await page.goto('reports')
    await expect(page.getByTestId('report-list-page')).toBeVisible()
    await expect(page.getByTestId('report-list-runtime-banner')).toContainText('宿主尚未同步真实连接状态')
  })

  test('can create a baseline definition and add a metric', async ({ page }) => {
    await mockRuntimeStatus(page)
    await mockBaselineDefinitionMutations(page)
    await page.goto('baseline-definitions')

    await expect(page.getByTestId('baseline-definition-page')).toBeVisible()
    await expect(page.getByTestId('baseline-definition-runtime-banner')).toHaveCount(0)
    await page.getByTestId('baseline-definition-create-button').click()
    await page.getByTestId('baseline-definition-name-input').fill('E2E 基线定义')
    await page.getByTestId('baseline-definition-submit').click()

    await expect(page.getByText('定义已创建')).toBeVisible()
    await expect(page.getByText('E2E 基线定义')).toBeVisible()

    await page.getByTestId('baseline-definition-manage-metrics-def-001').click()
    await page.getByTestId('baseline-definition-source-channel-select').click()
    await page.getByRole('option', { name: /B相电压/ }).click()
    await expect(page.getByTestId('baseline-definition-metric-name-input')).toHaveValue('B相电压')
    await expect(page.getByTestId('baseline-definition-metric-unit-input')).toHaveValue('V')
    await page.getByTestId('baseline-definition-metric-name-input').fill('氧含量')
    await page.getByTestId('baseline-definition-metric-unit-input').fill('%')
    await page.getByTestId('baseline-definition-add-metric').click()

    await expect(page.getByText('指标已添加')).toBeVisible()
    await expect(
      page.getByTestId('baseline-definition-metric-dialog').getByText('氧含量', { exact: true })
    ).toBeVisible()
  })

  test('baseline list refresh button triggers a real reload with visible loading feedback', async ({ page }) => {
    const counters = { list: 0, active: 0 }
    await mockRuntimeStatus(page)
    await mockBaselineLibraryWithRefreshCounters(page, counters)

    await page.goto('baselines')
    await expect(page.getByTestId('baseline-list-page')).toBeVisible()
    await expect.poll(() => counters.list).toBe(1)
    await expect.poll(() => counters.active).toBe(1)

    const refreshButton = page.getByTestId('baseline-refresh-button')
    await expect(refreshButton).toContainText('刷新数据')
    await refreshButton.click()

    await expect(refreshButton).toContainText('刷新中...')
    await expect(refreshButton).toBeDisabled()
    await expect.poll(() => counters.list).toBe(2)
    await expect.poll(() => counters.active).toBe(2)
    await expect(refreshButton).toContainText('刷新数据')
  })

  test('baseline list export button shows explicit placeholder feedback instead of staying silent', async ({ page }) => {
    await mockRuntimeStatus(page)
    await mockBaselineLibrary(page)

    await page.goto('baselines')
    await expect(page.getByTestId('baseline-list-page')).toBeVisible()
    await page.getByTestId('baseline-export-button').click()
    await expect(
      page.locator('.el-message__content').filter({ hasText: '黄金基线导出入口开发中' })
    ).toBeVisible()
    await expect(page).toHaveURL(/\/edc\/baselines$/)
  })

  test('baseline list search input filters cards immediately for matching and missing names', async ({ page }) => {
    await mockRuntimeStatus(page)
    await mockBaselineLibrary(page)

    await page.goto('baselines')
    await expect(page.getByTestId('baseline-list-page')).toBeVisible()
    await expect(page.getByTestId('baseline-list-count')).toContainText('共 3 条记录')
    await expect(page.getByTestId('baseline-card-baseline-001')).toBeVisible()
    await expect(page.getByTestId('baseline-card-baseline-002')).toBeVisible()
    await expect(page.getByTestId('baseline-card-baseline-003')).toBeVisible()

    const searchInput = page.getByTestId('baseline-search-input')
    await searchInput.fill('高功率')
    await expect(page.getByTestId('baseline-list-count')).toContainText('共 1 条记录')
    await expect(page.getByTestId('baseline-card-baseline-002')).toBeVisible()
    await expect(page.getByTestId('baseline-card-baseline-001')).toHaveCount(0)
    await expect(page.getByTestId('baseline-card-baseline-003')).toHaveCount(0)

    await searchInput.fill('不存在的基线')
    await expect(page.getByTestId('baseline-list-count')).toContainText('共 0 条记录')
    await expect(page.getByTestId('baseline-empty-state')).toBeVisible()
    await expect(page.getByTestId('baseline-card-baseline-001')).toHaveCount(0)
    await expect(page.getByTestId('baseline-card-baseline-002')).toHaveCount(0)
    await expect(page.getByTestId('baseline-card-baseline-003')).toHaveCount(0)

    await searchInput.fill('标准基线')
    await expect(page.getByTestId('baseline-list-count')).toContainText('共 1 条记录')
    await expect(page.getByTestId('baseline-card-baseline-001')).toBeVisible()
  })

  test('baseline detail action buttons provide visible feedback instead of staying silent', async ({ page }) => {
    await mockRuntimeStatus(page)
    await mockBaselineDetail(page)

    await page.goto('baselines/baseline-001')
    await expect(page.getByTestId('baseline-detail-page')).toBeVisible()

    await page.getByTestId('baseline-detail-edit-button').click()
    await expect(
      page.locator('.el-message__content').filter({ hasText: '仅草稿状态可编辑' })
    ).toBeVisible()
    await expect(page).toHaveURL(/\/edc\/baselines\/baseline-001$/)

    await page.getByTestId('baseline-detail-new-version-button').click()
    await expect(
      page.locator('.el-message__content').filter({ hasText: '创建新版本功能开发中' })
    ).toBeVisible()
    await expect(page).toHaveURL(/\/edc\/baselines\/baseline-001$/)
  })

  test('dashboard shell does not emit i18n missing-key warnings for nav and search labels', async ({ page }) => {
    await mockRuntimeStatus(page)
    await mockDashboardOverview(page)
    await mockTaskWorkflow(page)

    const consoleWarnings: string[] = []
    page.on('console', message => {
      if (message.type() === 'warning' || message.type() === 'error') {
        consoleWarnings.push(message.text())
      }
    })

    await page.goto('')
    await expect(page.getByTestId('dashboard-page')).toBeVisible()
    await expect(page.getByText('生产概览')).toBeVisible()
    await expect(page.getByText('监控与分析')).toBeVisible()
    await expect(page.getByPlaceholder('搜索炉次 ID...')).toBeVisible()
    await expect(page.getByTestId('dashboard-page')).toContainText('H20260320-001')

    const i18nWarningKeys = [
      'nav.groupOverview',
      'nav.groupMonitor',
      'nav.groupManage',
      'common.searchHeatId',
      'common.detail',
    ]
    expect(
      consoleWarnings.filter(item =>
        i18nWarningKeys.some(key => item.includes(key))
      )
    ).toEqual([])
  })

  test('task list shows real status counts and can open detail and complete a task', async ({ page }) => {
    await mockRuntimeStatus(page)
    await mockTaskWorkflow(page)
    await page.goto('tasks')

    await expect(page.getByTestId('task-list-page')).toBeVisible()
    await expect(page.getByTestId('task-status-filter-all')).toContainText('全部 (10)')
    await expect(page.getByTestId('task-status-filter-pending')).toContainText('新建 (1)')
    await expect(page.getByTestId('task-status-filter-in_progress')).toContainText('进行中 (2)')
    await expect(page.getByTestId('task-status-filter-completed')).toContainText('已完成 (3)')
    await expect(page.getByTestId('task-status-filter-cancelled')).toContainText('已驳回 (4)')
    await page.getByTestId('task-row-mock-task-1').click()

    await expect(page.getByTestId('task-detail-page')).toBeVisible()
    await page.getByTestId('task-cause-analysis').fill('氧气流量波动导致偏差上升')
    await page.getByTestId('task-improvement').fill('调整加热段参数并稳定投料')
    await page.getByTestId('task-prevention').fill('增加班前检查和参数复核')
    await page.getByTestId('task-submit-button').click()

    await expect(page.getByText('已完成')).toBeVisible()
  })

  test('task list create button shows explicit placeholder feedback instead of staying silent', async ({ page }) => {
    await mockRuntimeStatus(page)
    await mockTaskWorkflow(page)
    await page.goto('tasks')

    await expect(page.getByTestId('task-list-page')).toBeVisible()
    await page.getByTestId('task-create-button').click()
    await expect(page.locator('.el-message__content').filter({ hasText: '新建纠偏任务入口开发中' })).toBeVisible()
    await expect(page).toHaveURL(/\/edc\/tasks$/)
  })

  test('task detail export downloads the pdf instead of opening a blank popup', async ({ page }) => {
    await mockRuntimeStatus(page)
    await mockTaskWorkflow(page)
    await page.route('**/api/tasks/mock-task-1/pdf', async route => {
      await fulfillPdf(route, 'T20260312-001.pdf')
    })

    await page.goto('tasks/mock-task-1')
    await expect(page.getByTestId('task-detail-page')).toBeVisible()

    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: '导出PDF' }).click()
    const download = await downloadPromise

    expect(download.suggestedFilename()).toBe('T20260312-001.pdf')
  })

  test('task list search input filters the loaded rows by task number and related heat id', async ({ page }) => {
    await mockRuntimeStatus(page)
    await mockTaskWorkflow(page)
    await page.goto('tasks')

    await expect(page.getByTestId('task-list-page')).toBeVisible()
    await expect(page.getByTestId('task-row-mock-task-1')).toBeVisible()
    await expect(page.getByTestId('task-row-mock-task-2')).toBeVisible()
    await expect(page.getByTestId('task-row-mock-task-3')).toBeVisible()

    const searchInput = page.getByTestId('task-search-input')

    await searchInput.fill('T20260312-002')
    await expect(page.getByTestId('task-row-mock-task-2')).toBeVisible()
    await expect(page.getByTestId('task-row-mock-task-1')).toHaveCount(0)
    await expect(page.getByTestId('task-row-mock-task-3')).toHaveCount(0)

    await searchInput.fill('heat-special')
    await expect(page.getByTestId('task-row-mock-task-3')).toBeVisible()
    await expect(page.getByTestId('task-row-mock-task-1')).toHaveCount(0)
    await expect(page.getByTestId('task-row-mock-task-2')).toHaveCount(0)

    await searchInput.fill('not-found-task')
    await expect(page.getByTestId('task-empty-state')).toBeVisible()
    await expect(page.getByTestId('task-row-mock-task-1')).toHaveCount(0)
    await expect(page.getByTestId('task-row-mock-task-2')).toHaveCount(0)
    await expect(page.getByTestId('task-row-mock-task-3')).toHaveCount(0)
  })

  test('report list placeholder buttons show explicit feedback instead of staying silent', async ({ page }) => {
    await mockRuntimeStatus(page)
    await mockReportsAndInbox(page)
    await page.goto('reports')

    await expect(page.getByTestId('report-list-page')).toBeVisible()

    await page.getByTestId('report-history-query-button').click()
    await expect(page.locator('.el-message__content').filter({ hasText: '历史查询入口开发中' })).toBeVisible()
    await expect(page).toHaveURL(/\/edc\/reports$/)

    await page.getByTestId('report-export-pdf-button').click()
    await expect(page.locator('.el-message__content').filter({ hasText: '昨日报告 PDF 导出入口开发中' })).toBeVisible()
    await expect(page).toHaveURL(/\/edc\/reports$/)
  })

  test('reports and inbox pages can navigate into detail pages', async ({ page }) => {
    await mockRuntimeStatus(page)
    await mockReportsAndInbox(page)
    await page.goto('reports')
    await expect(page.getByTestId('report-list-page')).toBeVisible()
    await page.getByTestId(/^report-row-/).first().click()
    await expect(page.getByTestId('report-detail-page')).toBeVisible()
    await expect(page.getByTestId('report-detail-success')).toBeVisible()
    await expect(page.getByTestId('report-detail-page')).toContainText('8')
    await expect(page.getByTestId('report-detail-empty-top-deviations')).toBeVisible()
    await expect(page.getByTestId('report-detail-loading')).toHaveCount(0)

    await page.goto('inbox')
    await expect(page.getByTestId('inbox-page')).toBeVisible()
    await page.getByTestId(/^inbox-row-/).first().click()
    await expect(page.getByTestId('heat-detail-page')).toBeVisible()
  })

  test('report detail export downloads the pdf instead of opening a blank popup', async ({ page }) => {
    await mockRuntimeStatus(page)
    await mockReportsAndInbox(page)
    await page.route('**/api/reports/daily/2026-03-19/pdf', async route => {
      await fulfillPdf(route, '2026-03-19.pdf')
    })

    await page.goto('reports/2026-03-19')
    await expect(page.getByTestId('report-detail-page')).toBeVisible()
    await expect(page.getByTestId('report-detail-success')).toBeVisible()

    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: '导出PDF' }).click()
    const download = await downloadPromise

    expect(download.suggestedFilename()).toBe('2026-03-19.pdf')
  })

  test('inbox shows a pending-copy fallback instead of misleading empty deviation percent', async ({ page }) => {
    await mockRuntimeStatus(page)
    await page.route('**/api/heats?**', async route => {
      await fulfillJson(route, {
        items: [
          {
            id: 'inbox-null-001',
            heat_no: 'H20260325-001',
            description: null,
            start_time: '2026-03-25T08:00:00Z',
            end_time: '2026-03-25T08:40:00Z',
            baseline_id: 'baseline-001',
            deviation_score: null,
            avg_deviation_score: null,
            abnormal_duration_minutes: null,
            schedule_tag: 'work',
            cut_reason: null,
            cut_status: 'normal',
            major_issue: false,
            blocked_by_issue: false,
            status: 'abnormal',
            temperature: 1450,
            created_at: '2026-03-25T08:00:00Z',
            record_source: 'live_inferred',
            current_curve_source: 'live_edc',
            baseline_curve_source: 'none'
          }
        ],
        total: 1,
        page: 1,
        page_size: 10
      })
    })

    await page.goto('inbox')

    await expect(page.getByTestId('inbox-page')).toBeVisible()
    await expect(page.getByTestId('inbox-deviation-inbox-null-001')).toHaveText('待计算')
    await expect(page.getByTestId('inbox-row-inbox-null-001')).not.toContainText('--%')
  })

  test('heat list and dashboard recent heats show pending copy for null deviation instead of bare dashes', async ({ page }) => {
    await mockRuntimeStatus(page)
    await page.route('**/api/dashboard/stats', async route => {
      await fulfillJson(route, {
        today_heats: 3,
        avg_deviation: 0,
        pending_tasks: 0,
        active_baseline: '标准基线 v2.1',
        normal_rate: 66.7
      })
    })
    await page.route('**/api/dashboard/realtime?**', async route => {
      await fulfillJson(route, {
        timestamp: '2026-03-25T08:30:00Z',
        baseline_id: 'baseline-001',
        baseline_name: '标准基线 v2.1',
        power_source_label: '总有功功率',
        voltage_source_label: 'A相电压',
        power: [],
        voltage: [],
        baseline_power: [],
        baseline_voltage: []
      })
    })
    await page.route('**/api/dashboard/recent-heats?**', async route => {
      await fulfillJson(route, {
        items: [
          {
            id: 'dashboard-null-heat-001',
            heat_no: 'H20260325-101',
            start_time: '2026-03-25T08:00:00Z',
            end_time: '2026-03-25T08:40:00Z',
            status: 'abnormal',
            deviation_score: null
          }
        ]
      })
    })
    await page.route('**/api/tasks?**', async route => {
      await fulfillJson(route, {
        items: [],
        total: 0,
        page: 1,
        page_size: 10
      })
    })
    await page.route('**/api/heats?**', async route => {
      await fulfillJson(route, {
        items: [
          {
            id: 'heat-null-001',
            heat_no: 'H20260325-001',
            description: null,
            start_time: '2026-03-25T08:00:00Z',
            end_time: '2026-03-25T08:40:00Z',
            baseline_id: 'baseline-001',
            deviation_score: null,
            avg_deviation_score: null,
            abnormal_duration_minutes: null,
            schedule_tag: 'work',
            cut_reason: 'live_inferred',
            cut_status: 'normal',
            major_issue: false,
            blocked_by_issue: false,
            status: 'abnormal',
            temperature: 1450,
            created_at: '2026-03-25T08:00:00Z',
            record_source: 'live_inferred',
            current_curve_source: 'live_edc',
            baseline_curve_source: 'none'
          }
        ],
        total: 1,
        page: 1,
        page_size: 10
      })
    })

    await page.goto('')
    await expect(page.getByTestId('dashboard-page')).toBeVisible()
    await expect(page.getByTestId('dashboard-recent-heat-deviation-dashboard-null-heat-001')).toHaveText('待计算')
    await expect(page.getByTestId('dashboard-recent-heat-deviation-dashboard-null-heat-001')).not.toHaveText('--')

    await page.goto('heats')
    await expect(page.getByTestId('heat-list-page')).toBeVisible()
    await expect(page.getByTestId('heat-deviation-heat-null-001')).toHaveText('待计算')
    await expect(page.getByTestId('heat-deviation-heat-null-001')).not.toHaveText('--')

    await page.goto('inbox')
    await expect(page.getByTestId('inbox-page')).toBeVisible()
    await expect(page.getByTestId('inbox-deviation-heat-null-001')).toHaveText('待计算')
    await expect(page.getByTestId('inbox-row-heat-null-001')).not.toContainText('--%')
  })

  test('default zh-CN pages do not leak English subtitles or labels', async ({ page }) => {
    await mockRuntimeStatus(page)
    await mockDashboardOverview(page)
    await mockTaskWorkflow(page)
    await mockBaselineLibrary(page)
    await mockReportsAndInbox(page)
    await mockSettingsWorkflow(page)

    await page.goto('')
    await expect(page.getByTestId('dashboard-page')).toBeVisible()
    await expect(page.getByTestId('dashboard-page')).toContainText('关联炉次: heat-001')
    await expect(page.getByTestId('dashboard-page')).not.toContainText('Heat:')

    await page.goto('baselines')
    await expect(page.getByTestId('baseline-list-page')).toBeVisible()
    await expect(page.getByTestId('baseline-list-page')).toContainText('基线管理')
    await expect(page.getByTestId('baseline-list-page')).not.toContainText('Baseline Library')

    await page.goto('tasks')
    await expect(page.getByTestId('task-list-page')).toBeVisible()
    await expect(page.getByTestId('task-list-page')).toContainText('任务执行')
    await expect(page.getByTestId('task-list-page')).toContainText('关联炉次: heat-001')
    await expect(page.getByTestId('task-list-page')).not.toContainText('Action Orders')
    await expect(page.getByTestId('task-list-page')).not.toContainText('Heat:')

    await page.goto('reports')
    await expect(page.getByTestId('report-list-page')).toBeVisible()
    await expect(page.getByTestId('report-list-page')).toContainText('报表审计')
    await expect(page.getByTestId('report-list-page')).not.toContainText('Reports & Audit')

    await page.goto('inbox')
    await expect(page.getByTestId('inbox-page')).toBeVisible()
    await expect(page.getByTestId('inbox-page')).toContainText('需要立即关注并分析的工艺偏差项。')
    await expect(page.getByTestId('inbox-page')).toContainText('高优先级')
    await expect(page.getByTestId('inbox-page')).not.toContainText('Require immediate attention and analysis for process deviations.')
    await expect(page.getByTestId('inbox-page')).not.toContainText('High Priority')

    await page.goto('settings')
    await expect(page.getByTestId('settings-page')).toBeVisible()
    await expect(page.getByTestId('settings-page')).toContainText('全局参数')
    await expect(page.getByTestId('settings-page')).toContainText('影响提示')
    await expect(page.getByTestId('settings-page')).not.toContainText('System Configuration')
    await expect(page.getByTestId('settings-page')).not.toContainText('Impact Warning')
  })

  test('report detail shows explicit error state when detail request fails', async ({ page }) => {
    await mockRuntimeStatus(page)
    await page.route('**/api/reports/daily?**', async route => {
      await fulfillJson(route, {
        items: [
          {
            date: '2026-03-19',
            total_heats: 8,
            normal_heats: 6,
            abnormal_heats: 2,
            avg_deviation: 12.4,
            pending_tasks: 2,
            completed_tasks: 3,
            generated_at: '2026-03-19T23:00:00Z'
          }
        ],
        total: 1
      })
    })
    await page.route('**/api/reports/daily/2026-03-19', async route => {
      await fulfillJson(route, { detail: '日报不存在' }, 404)
    })

    await page.goto('reports')
    await expect(page.getByTestId('report-list-page')).toBeVisible()
    await page.getByTestId(/^report-row-/).first().click()

    await expect(page.getByTestId('report-detail-error')).toBeVisible()
    await expect(page.getByTestId('report-detail-error')).toContainText('日报不存在')
    await expect(page.getByTestId('report-detail-loading')).toHaveCount(0)
  })

  test('settings page shows host connectivity and can save tolerance and cutting configuration', async ({ page }) => {
    await mockRuntimeStatus(page)
    await mockSettingsWorkflow(page)
    const consoleWarnings: string[] = []
    page.on('console', message => {
      if (message.type() === 'warning') {
        consoleWarnings.push(message.text())
      }
    })
    await page.goto('settings')

    await expect(page.getByTestId('settings-page')).toBeVisible()
    await expect(page.getByTestId('settings-runtime-banner')).toHaveCount(0)
    await expect(page.getByTestId('settings-host-connectivity-card')).toBeVisible()
    await expect(
      page.getByTestId('settings-host-connectivity-card').getByRole('heading', {
        name: '宿主系统连接'
      })
    ).toBeVisible()
    await expect(page.getByText('EDC Test Gateway')).toBeVisible()
    await expect(
      page.getByTestId('settings-host-connectivity-card').getByText('宿主已连入')
    ).toBeVisible()

    await page.getByTestId('settings-save-report-time').click()
    await expect(latestSuccessMessage(page)).toBeVisible()

    await page.getByTestId('settings-save-tolerance').click()
    await expect(latestSuccessMessage(page)).toBeVisible()

    await page.getByTestId('settings-cutting-mode-fixed').click()
    await page.getByTestId('settings-fixed-interval-input').locator('input').fill('20')
    await page.getByText('按系统全局', { exact: true }).click()
    await page.getByText('按生产线（预留）', { exact: true }).click()
    await page.getByText('按基线定义', { exact: true }).click()
    await page.getByTestId('settings-save-cutting').click()
    await expect(latestSuccessMessage(page)).toBeVisible()
    expect(
      consoleWarnings.some((item) =>
        item.includes('[el-radio] [API] label act as value has been deprecated')
      )
    ).toBe(false)
  })

  test('settings cancel resets unsaved tolerance fields back to the last saved snapshot', async ({ page }) => {
    await mockRuntimeStatus(page)
    await mockSettingsWorkflow(page)
    await page.goto('settings')

    const reportHourInput = page
      .getByTestId('settings-report-generation-hour-input')
      .locator('input')
    const toleranceInput = page.getByTestId('settings-default-tolerance-input').locator('input')

    await expect(reportHourInput).toHaveValue('2')
    await expect(toleranceInput).toHaveValue('15')

    await reportHourInput.fill('5')
    await toleranceInput.fill('13.5')
    await page.getByTestId('settings-reset-tolerance').click()

    await expect(reportHourInput).toHaveValue('2')
    await expect(toleranceInput).toHaveValue('15')
  })

  test('settings side navigation scrolls to matching sections and updates active state', async ({ page }) => {
    await mockRuntimeStatus(page)
    await mockSettingsWorkflow(page)
    await page.goto('settings')

    await expect(page.getByTestId('settings-page')).toBeVisible()
    await expect(page.getByTestId('settings-nav-hostConnectivity')).toHaveAttribute('aria-current', 'true')

    await page.getByTestId('settings-nav-cutting').click()
    await expect(page.getByTestId('settings-nav-cutting')).toHaveAttribute('aria-current', 'true')
    await expect(page.getByTestId('settings-section-cutting')).toBeInViewport()

    await page.getByTestId('settings-nav-tolerance').click()
    await expect(page.getByTestId('settings-nav-tolerance')).toHaveAttribute('aria-current', 'true')
    await expect(page.getByTestId('settings-section-tolerance')).toBeInViewport()

    await page.getByTestId('settings-nav-hostConnectivity').click()
    await expect(page.getByTestId('settings-nav-hostConnectivity')).toHaveAttribute('aria-current', 'true')
    await expect(page.getByTestId('settings-host-connectivity-card')).toBeInViewport()
  })

  test('baseline definitions and settings pages reuse unified runtime attention state', async ({ page }) => {
    await mockRuntimeStatus(page, {
      overall_code: 'host_disconnected',
      host: {
        is_connected: false,
        machine_name: '--',
        last_sync_label: '--',
        meta: {
          source: '--',
          sensor_count: 0,
          channel_count: 0,
          enabled_channel_count: 0
        }
      },
      edc: {
        configured: true,
        base_url: 'http://60.251.229.32',
        username_present: true,
        host_channel_total: 0,
        enabled_channel_count: 0
      },
      pipelines: {
        dashboard: { code: 'host_disconnected', ready: false },
        heats: { code: 'host_disconnected', ready: false },
        inbox: { code: 'host_disconnected', ready: false },
        tasks: { code: 'host_disconnected', ready: false },
        reports: { code: 'host_disconnected', ready: false },
        baselines: { code: 'host_disconnected', ready: false },
        settings: { code: 'host_disconnected', ready: false }
      }
    })
    await mockSettingsWorkflow(page)

    await page.goto('baseline-definitions')
    await expect(page.getByTestId('baseline-definition-page')).toBeVisible()
    await expect(page.getByTestId('baseline-definition-runtime-banner')).toContainText('宿主尚未同步真实连接状态')

    await page.goto('settings')
    await expect(page.getByTestId('settings-page')).toBeVisible()
    await expect(page.getByTestId('settings-runtime-banner')).toContainText('宿主尚未同步真实连接状态')
  })
})
