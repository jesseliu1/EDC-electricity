import { expect, test } from '@playwright/test'

test.describe('EDC web smoke flows', () => {
  test('can create and publish a baseline from the wizard', async ({ page }) => {
    await page.goto('baselines')

    await expect(page.getByTestId('baseline-create-button')).toBeVisible()
    await page.getByTestId('baseline-create-button').click()

    await expect(page.getByTestId('baseline-wizard')).toBeVisible()
    await expect(page.getByText('设置基线')).toBeVisible()
    await expect(page.getByText(/条曲线 ·/)).toBeVisible()
    await expect(page.getByTestId('baseline-wizard-binding-warning')).toBeVisible()

    await page.getByTestId('baseline-wizard-name-input').fill('E2E 基线回归样例')
    await page.getByTestId('baseline-wizard-next').click()
    await expect(page.getByTestId('baseline-wizard-point-range-panel')).toBeVisible()
    await expect(page.getByTestId('baseline-wizard-selection-state')).toHaveAttribute('data-start', /.+/)
    await expect(page.getByTestId('baseline-wizard-selection-state')).toHaveAttribute('data-end', /.+/)
    await page.getByTestId('baseline-wizard-next').click()
    await expect(page.getByTestId('baseline-wizard-publish')).toBeVisible()
    await page.getByTestId('baseline-wizard-publish').click()

    await expect(page.getByRole('heading', { name: 'E2E 基线回归样例' }).first()).toBeVisible()
    await expect(page.locator('.el-message').filter({ hasText: '基线已发布' })).toBeVisible()
  })

  test('can expand a heat row and navigate to detail', async ({ page }) => {
    await page.goto('heats')

    const firstExpandButton = page.getByTestId('heat-row-expand').first()
    await expect(firstExpandButton).toBeVisible()
    await firstExpandButton.click()

    const expandedCard = page.getByTestId('heat-expanded-panel').first()
    await expect(expandedCard).toBeVisible()
    await expect(expandedCard.getByText('功率微缩曲线')).toBeVisible()

    await expandedCard.getByTestId('heat-view-report-button').click()
    await expect(page).toHaveURL(/\/edc\/heats\/.+/)
    await expect(page.getByTestId('heat-detail-page')).toBeVisible()
  })

  test('can open and save the manual adjust dialog', async ({ page }) => {
    await page.goto('heats/mock-heat-1')

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
})
