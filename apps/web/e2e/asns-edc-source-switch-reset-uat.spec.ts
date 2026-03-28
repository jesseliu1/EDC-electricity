import { expect, test, type Page } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = fileURLToPath(new URL('.', import.meta.url))
const issueSlug = '2026-03-27-edc-source-switch-reset-uat'
const assetRoot = path.resolve(__dirname, `../../../docs/test-reports/assets/${issueSlug}`)
const publicScreenshotDir = path.join(assetRoot, 'public')
const publicHostUrl = 'https://hopeofthepantheon.me/asns/'
const publicApiBase = 'https://hopeofthepantheon.me/api'

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
    path: path.join(publicScreenshotDir, file),
    fullPage: true,
  })
  records.push({ file, step, action, note })
}

test('uat verifies source-switch reset clears stale host groups and old edc runtime bindings', async ({
  page,
  request,
}) => {
  test.setTimeout(120000)
  await mkdir(publicScreenshotDir, { recursive: true })

  const screenshots: ScreenshotRecord[] = []

  const runtimeStatusResponse = await request.get(`${publicApiBase}/settings/runtime-status`)
  expect(runtimeStatusResponse.ok()).toBeTruthy()
  const runtimeStatus = await runtimeStatusResponse.json()

  const hostChannelsResponse = await request.get(`${publicApiBase}/settings/host-channels`)
  expect(hostChannelsResponse.ok()).toBeTruthy()
  const hostChannels = await hostChannelsResponse.json()

  const activeBaselineResponse = await request.get(`${publicApiBase}/baselines/active`)
  expect(activeBaselineResponse.ok()).toBeTruthy()
  const activeBaseline = await activeBaselineResponse.json()

  const definitionResponse = await request.get(
    `${publicApiBase}/baseline-definitions?include_disabled=true`
  )
  expect(definitionResponse.ok()).toBeTruthy()
  const definitions = await definitionResponse.json()

  const dashboardRealtimeResponse = await request.get(`${publicApiBase}/dashboard/realtime?duration=1h`)
  const dashboardRealtimeBody = await dashboardRealtimeResponse.json()

  expect(runtimeStatus.overall_code).toBe('host_disconnected')
  expect(runtimeStatus.edc.host_channel_total).toBe(0)
  expect(hostChannels.total).toBe(0)
  expect(activeBaseline).toBeNull()
  expect(
    (definitions.items as Array<{ metrics: Array<{ edc_channel_id: string | null }> }>).every((item) =>
      item.metrics.every((metric) => metric.edc_channel_id === null)
    )
  ).toBeTruthy()

  await page.goto(publicHostUrl, { waitUntil: 'networkidle' })
  await captureScreenshot(
    page,
    screenshots,
    '01-home-before-open-settings.png',
    '进入 ASNS 宿主页',
    'goto',
    '宿主首页加载完成，准备进入连线设置验证切源后的清空状态。'
  )

  await page.locator('button').nth(6).click()
  await expect(page.getByText('已添加通道清单', { exact: true })).toBeVisible()
  await expect(page.locator('input[type="text"]').first()).toHaveValue(runtimeStatus.edc.base_url)
  await captureScreenshot(
    page,
    screenshots,
    '02-after-click-open-settings.png',
    '点击 Dock 中的连线设置',
    'click',
    '连线设置窗口已打开，当前 EDC 地址与后端运行态一致。'
  )

  const emptyHostChannelsState = page.getByText('目前还没有加入任何硬件通道。', { exact: true })
  await expect(emptyHostChannelsState).toBeVisible()
  await emptyHostChannelsState.scrollIntoViewIfNeeded()
  await expect(emptyHostChannelsState).toBeInViewport()
  await expect(page.getByText('SSTW 380V-220V電力 · 三相智能电表', { exact: true })).toHaveCount(0)
  await captureScreenshot(
    page,
    screenshots,
    '03-settings-reset-empty-state.png',
    '连线设置结果态',
    'state-check',
    '已添加通道清单为空，旧服务器组信息不再显示。'
  )

  const edcPage = await page.context().newPage()
  await edcPage.goto(publicHostUrl, { waitUntil: 'networkidle' })
  await captureScreenshot(
    edcPage,
    screenshots,
    '04-home-before-open-edc-app.png',
    '重新进入宿主页，准备打开智慧熔炉',
    'goto',
    '使用新页面从宿主首页直接打开智慧熔炉。'
  )

  await edcPage.locator('button').nth(7).click()
  await expect(edcPage.locator('iframe')).toHaveCount(1)
  await captureScreenshot(
    edcPage,
    screenshots,
    '05-after-click-open-edc-app-shell.png',
    '点击 Dock 中的 EDC electricity',
    'click',
    '智慧熔炉容器窗口已打开。'
  )

  const edcFrame = edcPage.frames().find((frame) => frame.url().includes('/edc/'))
  expect(edcFrame).toBeTruthy()
  await expect(edcFrame!.getByTestId('dashboard-runtime-banner')).toBeVisible({ timeout: 20000 })
  await expect(edcFrame!.locator('body')).toContainText('宿主尚未同步真实连接状态')
  await expect(edcFrame!.locator('body')).toContainText('待重新配置')
  await captureScreenshot(
    edcPage,
    screenshots,
    '06-edc-dashboard-reset-state.png',
    '智慧熔炉结果态',
    'state-check',
    '智慧熔炉显示等待宿主同步的运行态提示，旧激活基线已清空为待重新配置。'
  )

  const edcFrameText = await edcFrame!.locator('body').innerText()

  const evidence = {
    issue: issueSlug,
    environment: 'public',
    script_path: 'apps/web/e2e/asns-edc-source-switch-reset-uat.spec.ts',
    screenshot_dir: `docs/test-reports/assets/${issueSlug}/public`,
    screenshots,
    runtime_status: runtimeStatus,
    host_channels: hostChannels,
    active_baseline: activeBaseline,
    baseline_definitions: definitions,
    dashboard_realtime: {
      status: dashboardRealtimeResponse.status(),
      body: dashboardRealtimeBody,
    },
    visual_findings: {
      asns_reset_empty_text: '目前还没有加入任何硬件通道。',
      asns_current_source: runtimeStatus.edc.base_url,
      asns_old_group_removed: 'SSTW 380V-220V電力 · 三相智能电表',
      edc_runtime_banner: '宿主尚未同步真实连接状态',
      edc_baseline_card: '待重新配置',
      edc_frame_contains_runtime_banner: edcFrameText.includes('宿主尚未同步真实连接状态'),
      edc_frame_contains_pending_baseline: edcFrameText.includes('待重新配置'),
    },
  }

  await writeFile(path.join(assetRoot, 'evidence.json'), JSON.stringify(evidence, null, 2), 'utf-8')
})
