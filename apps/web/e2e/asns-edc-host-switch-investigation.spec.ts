import { expect, test, type Page } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = fileURLToPath(new URL('.', import.meta.url))
const issueSlug = '2026-03-27-edc-server-switch-stale-groups'
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

function decodeSensorPayload(rawText: string) {
  const trimmed = rawText.trim()
  if (!trimmed) {
    return []
  }
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    const parsed = JSON.parse(trimmed)
    return parsed.value || parsed.data || parsed
  }
  const numericTokens = trimmed.split(/\s+/).filter((token) => /^\d+$/.test(token))
  const decoded = Buffer.from(numericTokens.map((token) => Number(token))).toString('utf-8')
  const parsed = JSON.parse(decoded)
  return parsed.value || parsed.data || parsed
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

async function collectCurrentEdcSensorSummary(baseUrl: string, username: string, password: string) {
  const loginResponse = await fetch(`${baseUrl}/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  const loginPayload = (await loginResponse.json()) as { code?: number; token?: string; data?: string }
  const token = loginPayload.token || loginPayload.data
  if (!loginResponse.ok || loginPayload.code !== 0 || !token) {
    throw new Error(`EDC login failed for ${baseUrl}`)
  }

  const sensorResponse = await fetch(`${baseUrl}/systemcfg`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      request: 'getAllSensorList',
      value: '',
      token: String(token),
    }),
  })
  const sensorPayload = decodeSensorPayload(await sensorResponse.text()) as Array<Record<string, unknown>>
  const sensorIds = sensorPayload.map((sensor) => String(sensor.uid || sensor.suid || ''))
  return {
    sensorCount: sensorPayload.length,
    sensorIds,
    sampleSensors: sensorPayload.slice(0, 8).map((sensor) => ({
      uid: String(sensor.uid || sensor.suid || ''),
      name: String(sensor.sensorName || sensor.name || ''),
      nickname: String(sensor.sensorNickName || ''),
    })),
  }
}

test('investigates stale host groups after EDC server switch and resulting no-data dashboard', async ({
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

  const dashboardRealtimeResponse = await request.get(`${publicApiBase}/dashboard/realtime?duration=1h`)
  const dashboardRealtimeBody = await dashboardRealtimeResponse.json()

  const currentEdcSummary = await collectCurrentEdcSensorSummary(
    String(runtimeStatus.edc.base_url),
    'admin',
    'admin'
  )

  const staleHostChannelIds = (hostChannels.items as Array<{ id: string; suid: string; cuid: string }>).map(
    (item) => item.id
  )
  const staleHostSuids = Array.from(
    new Set((hostChannels.items as Array<{ suid: string }>).map((item) => item.suid))
  )
  const missingFromCurrentEdc = staleHostSuids.filter(
    (suid) => !currentEdcSummary.sensorIds.includes(suid)
  )

  await page.goto(publicHostUrl, { waitUntil: 'networkidle' })
  await captureScreenshot(
    page,
    screenshots,
    '01-home-before-open-settings.png',
    '进入 ASNS 宿主页',
    'goto',
    '宿主首页已加载，准备进入连线设置。'
  )

  await page.locator('button').nth(6).click()
  await expect(page.getByText('已添加通道清单', { exact: true })).toBeVisible()
  await captureScreenshot(
    page,
    screenshots,
    '02-after-click-open-settings.png',
    '点击 Dock 中的连线设置',
    'click',
    '连线设置窗口已打开，可见旧组信息仍在已添加通道清单中。'
  )

  const visibleOldGroupTexts = [
    'SSTW 380V-220V電力 · 三相智能电表',
    'A-1溫度 · 热电偶温度采集器',
    'A-2溫度 · 热电偶温度采集器',
    '防水型智慧電流信號轉換器 · General 4-20 mA to CAN Converter',
  ]
  for (const text of visibleOldGroupTexts) {
    await expect(page.getByText(text, { exact: true }).first()).toBeVisible()
  }
  await page.getByText('suid 2349 / cuid 199 · kW', { exact: true }).scrollIntoViewIfNeeded()
  await expect(page.getByText('suid 2349 / cuid 199 · kW', { exact: true })).toBeVisible()
  await captureScreenshot(
    page,
    screenshots,
    '03-settings-old-groups-still-visible.png',
    '连线设置结果态',
    'state-check',
    '已添加通道清单仍显示旧服务器的组和通道。'
  )

  const edcPage = await page.context().newPage()
  await edcPage.goto(publicHostUrl, { waitUntil: 'networkidle' })
  await captureScreenshot(
    edcPage,
    screenshots,
    '04-home-before-open-edc-app.png',
    '重新进入宿主页，准备打开智慧熔炉',
    'goto',
    '为避免窗口遮挡，使用新页面从宿主首页直接打开智慧熔炉。'
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
  await expect
    .poll(async () => edcFrame!.locator('body').innerText(), {
      timeout: 20000,
    })
    .toContain('实时曲线当前不可用')
  await expect
    .poll(async () => edcFrame!.locator('body').innerText(), {
      timeout: 20000,
    })
    .toContain('未获取到真实实时数据，请检查宿主连接和通道绑定')
  await captureScreenshot(
    edcPage,
    screenshots,
    '06-edc-dashboard-no-data-visible.png',
    '智慧熔炉结果态',
    'state-check',
    '智慧熔炉首页显示未获取到真实实时数据和实时曲线当前不可用。'
  )

  const edcFrameText = await edcFrame!.locator('body').innerText()

  const evidence = {
    issue: issueSlug,
    environment: 'public',
    script_path: 'apps/web/e2e/asns-edc-host-switch-investigation.spec.ts',
    screenshot_dir: `docs/test-reports/assets/${issueSlug}/public`,
    screenshots,
    runtime_status: runtimeStatus,
    host_channels: hostChannels,
    dashboard_realtime: {
      status: dashboardRealtimeResponse.status(),
      body: dashboardRealtimeBody,
    },
    current_edc_summary: currentEdcSummary,
    stale_host_channel_check: {
      host_channel_ids: staleHostChannelIds,
      host_suids: staleHostSuids,
      missing_from_current_edc: missingFromCurrentEdc,
    },
    visual_findings: {
      settings_visible_old_groups: visibleOldGroupTexts,
      edc_dashboard_messages: [
        '未获取到真实实时数据，请检查宿主连接和通道绑定',
        '实时曲线当前不可用',
      ],
      edc_frame_contains_no_data_message: edcFrameText.includes(
        '未获取到真实实时数据，请检查宿主连接和通道绑定'
      ),
      edc_frame_contains_realtime_error_title: edcFrameText.includes('实时曲线当前不可用'),
    },
  }

  await writeFile(path.join(assetRoot, 'evidence.json'), JSON.stringify(evidence, null, 2), 'utf-8')
})
