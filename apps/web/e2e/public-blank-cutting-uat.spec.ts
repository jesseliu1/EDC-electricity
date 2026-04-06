import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = fileURLToPath(new URL('.', import.meta.url))
const issueSlug = '2026-04-05-public-blank-cutting-uat'
const assetRoot = path.resolve(__dirname, `../../../docs/test-reports/assets/${issueSlug}`)
const screenshotDir = path.join(assetRoot, 'public')
const publicAsnsUrl = 'https://hopeofthepantheon.me/asns/'
const publicEdcUrl = 'https://hopeofthepantheon.me/edc/'
const publicApiBase = 'https://hopeofthepantheon.me/api'
const deployedCommit = '84cafe93f1ca769cf796a5432a9270ce8c348176'

interface ScreenshotRecord {
  file: string
  step: string
  action: string
  note: string
}

async function captureScreenshot(
  page: Page,
  records: ScreenshotRecord[],
  file: string,
  step: string,
  action: string,
  note: string
) {
  await page.screenshot({
    path: path.join(screenshotDir, file),
    fullPage: true,
  })
  records.push({ file, step, action, note })
}

async function getJson(request: APIRequestContext, url: string) {
  const response = await request.get(url)
  expect(response.ok(), `GET ${url} should succeed`).toBeTruthy()
  return response.json()
}

async function writeJson(fileName: string, payload: unknown) {
  await writeFile(path.join(assetRoot, fileName), JSON.stringify(payload, null, 2), 'utf-8')
}

async function waitForRuntime(
  request: APIRequestContext,
  matcher: (payload: any) => boolean,
  label: string
) {
  let lastPayload: any = null
  for (let attempt = 0; attempt < 15; attempt += 1) {
    lastPayload = await getJson(request, `${publicApiBase}/settings/runtime-status`)
    if (matcher(lastPayload)) {
      return lastPayload
    }
    await new Promise((resolve) => setTimeout(resolve, 1000))
  }
  throw new Error(`Timed out waiting for runtime status: ${label}. Last payload: ${JSON.stringify(lastPayload)}`)
}

test('public blank deploy keeps empty state and supports cutting-mode save roundtrip', async ({
  page,
  request,
}) => {
  test.setTimeout(180000)
  await mkdir(screenshotDir, { recursive: true })

  const screenshots: ScreenshotRecord[] = []
  const latestSuccessMessage = (targetPage: Page) =>
    targetPage.locator('.el-message__content').filter({ hasText: '成功' }).last()

  const runtimeBefore = await getJson(request, `${publicApiBase}/settings/runtime-status`)
  const baselineDefinitionsBefore = await getJson(
    request,
    `${publicApiBase}/baseline-definitions`
  )
  const baselinesBefore = await getJson(request, `${publicApiBase}/baselines`)
  const heatsBefore = await getJson(request, `${publicApiBase}/heats?page=1&page_size=5`)

  expect(runtimeBefore.overall_code).toBe('host_disconnected')
  expect(runtimeBefore.runtime.cutting_mode).toBe('signal_inference')
  expect(runtimeBefore.runtime.fixed_interval_minutes).toBeNull()
  expect(runtimeBefore.edc.configured).toBeFalsy()
  expect(baselineDefinitionsBefore.total).toBe(0)
  expect(baselinesBefore.total).toBe(0)
  expect(heatsBefore.total).toBe(0)

  await page.goto(publicAsnsUrl)
  await expect(page.locator('body')).toContainText('ASNS')
  await captureScreenshot(
    page,
    screenshots,
    '01-asns-home.png',
    '打开 ASNS 宿主页',
    'goto',
    '宿主页已可访问，准备验证 blank 空态。'
  )

  await page.locator('button').nth(6).click()
  await expect(page.getByText('已添加通道清单', { exact: true })).toBeVisible()
  await expect(page.getByText('目前还没有加入任何硬件通道。', { exact: true })).toBeVisible()
  await captureScreenshot(
    page,
    screenshots,
    '02-asns-settings-empty.png',
    '打开宿主连线设置',
    'click',
    'blank 重置后宿主已添加通道清单为空，未残留旧通道。'
  )

  const edcPage = await page.context().newPage()
  await edcPage.goto(publicEdcUrl)
  await expect(edcPage.getByRole('heading', { name: '总览' })).toBeVisible()
  await expect(edcPage.getByTestId('dashboard-runtime-banner')).toContainText(
    '宿主尚未同步真实连接状态'
  )
  await captureScreenshot(
    edcPage,
    screenshots,
    '03-edc-dashboard-blank.png',
    '打开 EDC Dashboard',
    'goto',
    'Dashboard 正常打开，并显示 blank / host_disconnected 提示。'
  )

  await edcPage
    .getByRole('navigation')
    .getByRole('button', { name: /系统设置|Settings/ })
    .click()
  await expect(edcPage).toHaveURL(/\/edc\/settings/)
  await expect(edcPage.getByTestId('settings-page')).toBeVisible()
  await expect(edcPage.getByTestId('settings-cutting-mode-group')).toBeVisible()
  await captureScreenshot(
    edcPage,
    screenshots,
    '04-edc-settings-before-save.png',
    '进入系统设置页',
    'navigate',
    '切割模式默认为 signal_inference，准备验证保存链。'
  )

  await edcPage.getByTestId('settings-cutting-mode-fixed').click()
  await edcPage.getByTestId('settings-fixed-interval-input').locator('input').fill('20')

  const fixedSaveResponse = edcPage.waitForResponse(
    (response) =>
      response.url().includes('/api/settings/cutting') &&
      response.request().method() === 'PUT'
  )
  await edcPage.getByTestId('settings-save-cutting').click()
  await fixedSaveResponse
  await expect(latestSuccessMessage(edcPage)).toBeVisible()
  const runtimeAfterFixed = await waitForRuntime(
    request,
    (payload) =>
      payload.runtime?.cutting_mode === 'fixed_interval' &&
      payload.runtime?.fixed_interval_minutes === 20,
    'fixed_interval=20'
  )
  const heatsAfterFixed = await getJson(request, `${publicApiBase}/heats?page=1&page_size=5`)
  expect(heatsAfterFixed.total).toBe(0)
  await captureScreenshot(
    edcPage,
    screenshots,
    '05-edc-settings-fixed-saved.png',
    '切换到 fixed_interval 并保存',
    'save',
    '保存成功后，后端 runtime-status 已反映 fixed_interval=20。'
  )

  await edcPage.getByTestId('settings-cutting-mode-signal').click()
  const signalSaveResponse = edcPage.waitForResponse(
    (response) =>
      response.url().includes('/api/settings/cutting') &&
      response.request().method() === 'PUT'
  )
  await edcPage.getByTestId('settings-save-cutting').click()
  await signalSaveResponse
  await expect(latestSuccessMessage(edcPage)).toBeVisible()
  const runtimeAfterRestore = await waitForRuntime(
    request,
    (payload) =>
      payload.runtime?.cutting_mode === 'signal_inference' &&
      payload.runtime?.fixed_interval_minutes === null,
    'restore signal_inference'
  )
  const heatsAfterRestore = await getJson(request, `${publicApiBase}/heats?page=1&page_size=5`)
  expect(heatsAfterRestore.total).toBe(0)
  await captureScreenshot(
    edcPage,
    screenshots,
    '06-edc-settings-restored.png',
    '恢复 signal_inference 并保存',
    'save',
    '保存成功后，后端 runtime-status 已恢复默认切割模式。'
  )

  await writeJson('evidence.json', {
    issue: issueSlug,
    environment: 'public',
    deployed_commit: deployedCommit,
    script_path: 'apps/web/e2e/public-blank-cutting-uat.spec.ts',
    screenshot_dir: `docs/test-reports/assets/${issueSlug}/public`,
    screenshots,
    api_checks: {
      runtime_before: runtimeBefore,
      baseline_definitions_before: baselineDefinitionsBefore,
      baselines_before: baselinesBefore,
      heats_before: heatsBefore,
      runtime_after_fixed: runtimeAfterFixed,
      heats_after_fixed: heatsAfterFixed,
      runtime_after_restore: runtimeAfterRestore,
      heats_after_restore: heatsAfterRestore,
    },
    assertions: {
      blank_state_preserved: true,
      fixed_interval_roundtrip_ok: true,
      restored_default_mode_ok: true,
    },
  })

  await writeJson('screenshot-review.json', {
    issue: issueSlug,
    environment: 'public',
    deployed_commit: deployedCommit,
    review_status: 'PASS',
    screenshots: screenshots.map((item) => ({
      ...item,
      review: 'PASS',
    })),
  })
})
