import { test, expect, type Locator, type Page } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = fileURLToPath(new URL('.', import.meta.url))
const evidenceDir = path.resolve(
  __dirname,
  '../../../docs/test-reports/assets/2026-03-28-uat-full'
)

type UatState = {
  heatId: string
  heatNo: string
  baselineId: string
  baselineName: string
  baselineSourceHeatId: string
  altBaselineName: string | null
  reportDate: string
  taskId: string | null
}

const state: UatState = {
  heatId: '',
  heatNo: '',
  baselineId: '',
  baselineName: '',
  baselineSourceHeatId: '',
  altBaselineName: null,
  reportDate: '',
  taskId: null,
}

async function capture(page: Page, fileName: string) {
  await mkdir(evidenceDir, { recursive: true })
  await page.screenshot({
    path: path.join(evidenceDir, fileName),
    fullPage: true,
  })
}

async function isVisible(locator: Locator, timeout = 12000) {
  try {
    await locator.first().waitFor({ state: 'visible', timeout })
    return true
  } catch {
    return false
  }
}

async function waitForHeatDetailReady(page: Page, heatNo: string) {
  await page.waitForLoadState('domcontentloaded')
  await expect(page.getByRole('heading', { name: '炉次详情' })).toBeVisible()
  await expect(page.getByRole('heading', { name: new RegExp(heatNo) })).toBeVisible({
    timeout: 20000,
  })
  await page.waitForTimeout(6000)
}

async function waitForBaselineDetailReady(page: Page, baselineName: string) {
  await page.waitForLoadState('domcontentloaded')
  await expect(page.getByRole('heading', { name: '基线详情' })).toBeVisible()
  await expect(
    page.getByRole('heading', { name: new RegExp(baselineName) })
  ).toBeVisible({ timeout: 20000 })
  await page.waitForTimeout(4000)
}

test.describe('full local uat', () => {
  test.beforeAll(async ({ request }) => {
    const heats = await request.get('http://127.0.0.1:8000/api/heats?page=1&page_size=5')
    const heatsJson = await heats.json()
    const heatItem = heatsJson.items?.[1] ?? heatsJson.items?.[0]

    const baselines = await request.get('http://127.0.0.1:8000/api/baselines?page=1&page_size=10')
    const baselinesJson = await baselines.json()
    const baselineItems = baselinesJson.items ?? []
    const publishedBaseline =
      baselineItems.find((item: { status: string }) => item.status === 'published') ?? baselineItems[0]
    const currentHeatBaseline =
      baselineItems.find((item: { id: string }) => item.id === heatItem.baseline_id) ?? publishedBaseline
    const altBaseline =
      baselineItems.find(
        (item: { name: string; id: string }) =>
          item.id !== currentHeatBaseline.id && item.name !== currentHeatBaseline.name
      ) ?? null

    const reports = await request.get('http://127.0.0.1:8000/api/reports/daily')
    const reportsJson = await reports.json()
    const reportItem = reportsJson.items?.[0]

    if (!heatItem || !publishedBaseline || !reportItem) {
      throw new Error('UAT 初始化失败：缺少炉次、基线或日报数据')
    }

    state.heatId = heatItem.id
    state.heatNo = heatItem.heat_no
    state.baselineId = currentHeatBaseline.id
    state.baselineName = currentHeatBaseline.name
    state.baselineSourceHeatId = currentHeatBaseline.source_heat_id
    state.altBaselineName = altBaseline?.name ?? null
    state.reportDate = reportItem.date
  })

  test('UAT-001 Dashboard 总览与时间范围按钮', async ({ page }) => {
    await page.goto('http://127.0.0.1:3001/edc/')
    await expect(page.getByRole('heading', { name: '总览' })).toBeVisible()
    await page.waitForTimeout(3000)
    await capture(page, 'uat-full-step-01-dashboard-entry.png')

    await page.getByRole('button', { name: '24小时' }).click()
    await page.waitForTimeout(1500)
    await capture(page, 'uat-full-step-02-dashboard-click-24h.png')

    await page.getByRole('button', { name: '1小时' }).click()
    await page.waitForTimeout(1500)
    await capture(page, 'uat-full-step-03-dashboard-click-1h.png')
  })

  test('UAT-002 炉次浏览列表页', async ({ page }) => {
    await page.goto('http://127.0.0.1:3001/edc/heats')
    await expect(page.getByRole('heading', { name: '炉次浏览', exact: true })).toBeVisible()
    await page.waitForTimeout(6000)
    await capture(page, 'uat-full-step-04-heats-list-page.png')

    const heatRow = page.getByText(state.heatNo).first()
    if (await isVisible(heatRow, 12000)) {
      await heatRow.click()
      await waitForHeatDetailReady(page, state.heatNo)
      await capture(page, 'uat-full-step-05-heats-click-latest-row.png')
    }
  })

  test('UAT-003 炉次详情与任务创建', async ({ page }) => {
    await page.goto(`http://127.0.0.1:3001/edc/heats/${state.heatId}`)
    await waitForHeatDetailReady(page, state.heatNo)
    await capture(page, 'uat-full-step-06-heat-detail-entry.png')

    if (state.altBaselineName) {
      await page.getByRole('tab', { name: state.altBaselineName }).click()
      await page.waitForTimeout(1500)
      await capture(page, 'uat-full-step-07-heat-detail-click-alt-baseline-tab.png')
    }

    await page.getByRole('button', { name: '手动调整' }).click()
    await expect(page.getByRole('dialog', { name: '手动调整' })).toBeVisible()
    await page.waitForTimeout(1500)
    await capture(page, 'uat-full-step-08-heat-detail-open-manual-adjust.png')

    await page.getByRole('button', { name: '取消' }).click()
    await page.waitForTimeout(1000)
    await capture(page, 'uat-full-step-09-heat-detail-close-manual-adjust.png')

    await page.getByRole('button', { name: '生成纠偏任务' }).click()
    await page.waitForTimeout(2500)
    if (/\/edc\/tasks\/[^/]+$/.test(page.url())) {
      state.taskId = page.url().split('/').pop() ?? null
    }
    await capture(page, 'uat-full-step-10-heat-detail-create-task.png')
  })

  test('UAT-004 纠偏任务单列表与详情', async ({ page }) => {
    await page.goto('http://127.0.0.1:3001/edc/tasks')
    await expect(page.getByRole('heading', { name: '纠偏任务单', exact: true })).toBeVisible()
    await page.waitForTimeout(2000)
    await capture(page, 'uat-full-step-11-task-list-page.png')

    const taskItem = page.locator('text=/T\\d{8}-\\d{6}/').first()
    if (await isVisible(taskItem, 10000)) {
      await taskItem.click()
      await expect(page).toHaveURL(/\/edc\/tasks\/[^/]+$/)
      await page.waitForTimeout(1500)
      await capture(page, 'uat-full-step-12-task-list-open-detail.png')
    }
  })

  test('UAT-005 黄金基线库列表页', async ({ page }) => {
    await page.goto('http://127.0.0.1:3001/edc/baselines')
    await expect(page.getByRole('heading', { name: '黄金基线库', exact: true })).toBeVisible()
    await page.waitForTimeout(6000)
    await capture(page, 'uat-full-step-13-baseline-list-page.png')
  })

  test('UAT-006 基线详情与来源炉次跳转', async ({ page }) => {
    await page.goto(`http://127.0.0.1:3001/edc/baselines/${state.baselineId}`)
    await waitForBaselineDetailReady(page, state.baselineName)
    await capture(page, 'uat-full-step-14-baseline-detail-entry.png')

    const sourceHeatLink = page.getByText(state.baselineSourceHeatId).first()
    if (await isVisible(sourceHeatLink, 10000)) {
      await sourceHeatLink.click()
      await page.waitForTimeout(6000)
      await capture(page, 'uat-full-step-15-baseline-detail-click-source-heat.png')
    }
  })

  test('UAT-007 偏差收件箱空态', async ({ page }) => {
    await page.goto('http://127.0.0.1:3001/edc/inbox')
    await expect(page.getByRole('heading', { name: '偏差收件箱' }).last()).toBeVisible()
    await page.waitForTimeout(2000)
    await capture(page, 'uat-full-step-16-inbox-page.png')
  })

  test('UAT-008 日报与审计列表页与详情页', async ({ page }) => {
    await page.goto('http://127.0.0.1:3001/edc/reports')
    await expect(page.getByRole('heading', { name: '日报与审计', exact: true })).toBeVisible()
    await page.waitForTimeout(3000)
    await capture(page, 'uat-full-step-17-report-list-page.png')

    await page.goto(`http://127.0.0.1:3001/edc/reports/${state.reportDate}`)
    await expect(page.getByTestId('report-detail-page')).toBeVisible({ timeout: 15000 })
    await page.waitForTimeout(3000)
    await capture(page, 'uat-full-step-18-report-detail-page.png')
  })

  test('UAT-009 系统设置与保存偏差阈值', async ({ page }) => {
    await page.goto('http://127.0.0.1:3001/edc/settings')
    await expect(page.getByRole('heading', { name: '系统设置', exact: true })).toBeVisible()
    await page.waitForTimeout(2000)
    await capture(page, 'uat-full-step-19-settings-page.png')

    await page.getByTestId('settings-nav-tolerance').click()
    await page.waitForTimeout(1000)
    await capture(page, 'uat-full-step-20-settings-click-tolerance-nav.png')

    const saveResponsePromise = page.waitForResponse((response) => {
      return response.url().includes('/api/settings/tolerance') && response.request().method() === 'PUT'
    })
    await page.getByTestId('settings-save-tolerance').click()
    await saveResponsePromise
    await page.waitForTimeout(1500)
    await capture(page, 'uat-full-step-21-settings-save-tolerance.png')
  })
})
