import { expect, test, type Page } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = fileURLToPath(new URL('.', import.meta.url))
const evidenceDir = path.resolve(
  __dirname,
  '../../../docs/test-reports/assets/2026-03-29-uat-export-followup'
)
const webOrigin = (process.env.UAT_WEB_ORIGIN ?? 'http://127.0.0.1:3000').replace(/\/$/, '')
const edcBaseUrl = `${webOrigin}/edc`
const apiBaseUrl = (process.env.UAT_API_BASE ?? 'http://127.0.0.1:8000/api').replace(/\/$/, '')

type ExportState = {
  taskId: string
  taskNo: string
  reportDate: string
}

const state: ExportState = {
  taskId: '',
  taskNo: '',
  reportDate: ''
}

async function capture(page: Page, fileName: string) {
  await mkdir(evidenceDir, { recursive: true })
  await page.screenshot({
    path: path.join(evidenceDir, fileName),
    fullPage: true
  })
}

function edcUrl(pathname = '/') {
  return `${edcBaseUrl}${pathname.startsWith('/') ? pathname : `/${pathname}`}`
}

test.describe('uat export followup', () => {
  test.beforeAll(async ({ request }) => {
    const heatsResponse = await request.get(`${apiBaseUrl}/heats?page=1&page_size=10`)
    expect(heatsResponse.ok()).toBeTruthy()
    const heatsJson = await heatsResponse.json()
    const heatItem =
      heatsJson.items?.find((item: { status?: string }) => item.status === 'abnormal') ??
      heatsJson.items?.[0]

    if (!heatItem?.id) {
      throw new Error('UAT 导出回归初始化失败：未找到可用于建任务的炉次')
    }

    const createTaskResponse = await request.post(`${apiBaseUrl}/tasks`, {
      data: {
        heat_id: heatItem.id
      }
    })
    expect(createTaskResponse.ok()).toBeTruthy()
    const taskJson = await createTaskResponse.json()

    const reportsResponse = await request.get(`${apiBaseUrl}/reports/daily?page=1&page_size=5`)
    expect(reportsResponse.ok()).toBeTruthy()
    const reportsJson = await reportsResponse.json()
    const reportItem = reportsJson.items?.[0]

    if (!taskJson?.id || !taskJson?.task_no || !reportItem?.date) {
      throw new Error('UAT 导出回归初始化失败：缺少任务或日报数据')
    }

    state.taskId = String(taskJson.id)
    state.taskNo = String(taskJson.task_no)
    state.reportDate = String(reportItem.date)
  })

  test('S07-TC02 task export downloads pdf from real backend', async ({ page }) => {
    await page.goto(edcUrl(`/tasks/${state.taskId}`))
    await expect(page.getByTestId('task-detail-page')).toBeVisible({ timeout: 15000 })
    await expect(page.getByRole('button', { name: '导出PDF' })).toBeVisible()
    await capture(page, 's07-tc02-task-detail-before-export.png')

    const responsePromise = page.waitForResponse(response => {
      return response.url().includes(`/api/tasks/${state.taskId}/pdf`) && response.status() === 200
    })
    const downloadPromise = page.waitForEvent('download')

    await page.getByRole('button', { name: '导出PDF' }).click()

    const [, download] = await Promise.all([responsePromise, downloadPromise])
    expect(download.suggestedFilename()).toBe(`${state.taskNo}.pdf`)
    await capture(page, 's07-tc02-task-detail-after-export.png')
  })

  test('S07-TC03 report export downloads pdf from real backend', async ({ page }) => {
    await page.goto(edcUrl(`/reports/${state.reportDate}`))
    await expect(page.getByTestId('report-detail-page')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('report-detail-success')).toBeVisible({ timeout: 15000 })
    await expect(page.getByRole('button', { name: '导出PDF' })).toBeVisible()
    await capture(page, 's07-tc03-report-detail-before-export.png')

    const responsePromise = page.waitForResponse(response => {
      return (
        response.url().includes(`/api/reports/daily/${state.reportDate}/pdf`) &&
        response.status() === 200
      )
    })
    const downloadPromise = page.waitForEvent('download')

    await page.getByRole('button', { name: '导出PDF' }).click()

    const [, download] = await Promise.all([responsePromise, downloadPromise])
    expect(download.suggestedFilename()).toBe(`daily-${state.reportDate}.pdf`)
    await capture(page, 's07-tc03-report-detail-after-export.png')
  })
})
