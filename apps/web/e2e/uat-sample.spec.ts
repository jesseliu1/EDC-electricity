import { expect, test, type Page } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = fileURLToPath(new URL('.', import.meta.url))
const evidenceDir = path.resolve(
  __dirname,
  '../../../docs/test-reports/assets/2026-03-28-uat-sample'
)

async function capture(page: Page, fileName: string) {
  await mkdir(evidenceDir, { recursive: true })
  await page.screenshot({
    path: path.join(evidenceDir, fileName),
    fullPage: true,
  })
}

test('uat sample 001 dashboard can navigate to heats page', async ({ page }) => {
  await page.goto('http://127.0.0.1:3001/edc/')
  await expect(page.getByRole('heading', { name: '总览' })).toBeVisible()
  await expect(
    page.getByRole('navigation').getByRole('button', { name: /炉次浏览/ })
  ).toBeVisible()
  await capture(page, 'uat-sample-001-step-01-dashboard-entry.png')

  await page.getByRole('navigation').getByRole('button', { name: /炉次浏览/ }).click()
  await expect(page).toHaveURL(/\/edc\/heats$/)
  await expect(page.getByRole('heading', { name: '炉次浏览', exact: true })).toBeVisible()
  await expect(page.getByText('日期范围')).toBeVisible()
  await expect(page.getByRole('button', { name: '导出 Excel' })).toBeVisible()
  await capture(page, 'uat-sample-001-step-02-click-heat-browser.png')
})
