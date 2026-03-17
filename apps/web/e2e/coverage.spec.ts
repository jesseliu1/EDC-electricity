import { expect, test, type Page, type Route } from '@playwright/test'

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body)
  })
}

async function mockBaselineDefinitionMutations(page: Page) {
  await page.route('**/api/baseline-definitions', async route => {
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

  await page.route('**/api/settings/host-channels', async route => {
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

async function mockTaskWorkflow(page: Page) {
  const detailBody = {
    id: 'mock-task-1',
    task_no: 'T20260312-001',
    heat_id: 'heat-001',
    heat_no: 'H20260312-001',
    deviation_percent: 18.2,
    status: 'in_progress',
    created_at: '2026-03-11T10:00:00Z',
    updated_at: '2026-03-12T10:00:00Z',
    completed_at: null,
    cause_analysis: '',
    improvement: '',
    prevention: '',
    deviation_snapshot: {}
  }

  await page.route('**/api/tasks?**', async route => {
    await fulfillJson(route, {
      items: [
        {
          id: 'mock-task-1',
          task_no: 'T20260312-001',
          heat_id: 'heat-001',
          deviation_percent: 18.2,
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
      page_size: 10
    })
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
        { key: 'time_tolerance_percent', value: '10', description: null },
        { key: 'major_issue_duration_minutes', value: '8', description: null },
        { key: 'work_start_time', value: '08:00', description: null },
        { key: 'work_end_time', value: '18:00', description: null },
        { key: 'break_periods', value: '12:00-13:00', description: null },
        { key: 'baseline_length_scope_mode', value: 'definition', description: null }
      ]
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
}

test.describe('EDC web extended coverage', () => {
  const latestSuccessMessage = (page: Page) =>
    page.locator('.el-message__content').filter({ hasText: '成功' }).last()

  test('dashboard quick links and sidebar routes are reachable', async ({ page }) => {
    await page.goto('')
    await expect(page.getByTestId('dashboard-page')).toBeVisible()

    await page.getByTestId('dashboard-quick-link-reports').click()
    await expect(page.getByTestId('report-list-page')).toBeVisible()

    await page.getByRole('button', { name: /基线定义/ }).click()
    await expect(page.getByTestId('baseline-definition-page')).toBeVisible()

    await page.getByRole('button', { name: /系统设置/ }).click()
    await expect(page.getByTestId('settings-page')).toBeVisible()
  })

  test('can create a baseline definition and add a metric', async ({ page }) => {
    await mockBaselineDefinitionMutations(page)
    await page.goto('baseline-definitions')

    await expect(page.getByTestId('baseline-definition-page')).toBeVisible()
    await page.getByTestId('baseline-definition-create-button').click()
    await page.getByTestId('baseline-definition-name-input').fill('E2E 基线定义')
    await page.getByTestId('baseline-definition-submit').click()

    await expect(page.getByText('定义已创建')).toBeVisible()
    await expect(page.getByText('E2E 基线定义')).toBeVisible()

    await page.getByTestId('baseline-definition-manage-metrics-def-001').click()
    await page.getByTestId('baseline-definition-source-channel-select').click()
    await page.getByRole('option', { name: /总有功功率/ }).click()
    await expect(page.getByTestId('baseline-definition-metric-name-input')).toHaveValue('总有功功率')
    await expect(page.getByTestId('baseline-definition-metric-unit-input')).toHaveValue('kW')
    await page.getByTestId('baseline-definition-metric-name-input').fill('氧含量')
    await page.getByTestId('baseline-definition-metric-unit-input').fill('%')
    await page.getByTestId('baseline-definition-add-metric').click()

    await expect(page.getByText('指标已添加')).toBeVisible()
    await expect(
      page.getByTestId('baseline-definition-metric-dialog').getByText('氧含量', { exact: true })
    ).toBeVisible()
  })

  test('task list can open detail and complete a task', async ({ page }) => {
    await mockTaskWorkflow(page)
    await page.goto('tasks')

    await expect(page.getByTestId('task-list-page')).toBeVisible()
    await page.getByTestId('task-row-mock-task-1').click()

    await expect(page.getByTestId('task-detail-page')).toBeVisible()
    await page.getByTestId('task-cause-analysis').fill('氧气流量波动导致偏差上升')
    await page.getByTestId('task-improvement').fill('调整加热段参数并稳定投料')
    await page.getByTestId('task-prevention').fill('增加班前检查和参数复核')
    await page.getByTestId('task-submit-button').click()

    await expect(page.getByText('已完成')).toBeVisible()
  })

  test('reports and inbox pages can navigate into detail pages', async ({ page }) => {
    await page.goto('reports')
    await expect(page.getByTestId('report-list-page')).toBeVisible()
    await page.getByTestId(/^report-row-/).first().click()
    await expect(page.getByTestId('report-detail-page')).toBeVisible()

    await page.goto('inbox')
    await expect(page.getByTestId('inbox-page')).toBeVisible()
    await page.getByTestId(/^inbox-row-/).first().click()
    await expect(page.getByTestId('heat-detail-page')).toBeVisible()
  })

  test('settings page can save edc, tolerance and cutting configuration', async ({ page }) => {
    await mockSettingsWorkflow(page)
    await page.goto('settings')

    await expect(page.getByTestId('settings-page')).toBeVisible()

    await page.getByTestId('settings-test-edc').click()
    await expect(page.getByText('EDC 连接测试成功')).toBeVisible()

    await page.getByTestId('settings-save-edc').click()
    await expect(latestSuccessMessage(page)).toBeVisible()

    await page.getByTestId('settings-save-report-time').click()
    await expect(latestSuccessMessage(page)).toBeVisible()

    await page.getByTestId('settings-save-tolerance').click()
    await expect(latestSuccessMessage(page)).toBeVisible()

    await page.getByTestId('settings-save-cutting').click()
    await expect(latestSuccessMessage(page)).toBeVisible()
  })
})
