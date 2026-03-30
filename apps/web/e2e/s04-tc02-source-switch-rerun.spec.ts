import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = fileURLToPath(new URL('.', import.meta.url))
const issueSlug = '2026-03-29-s04-tc02-rerun'
const assetRoot = path.resolve(__dirname, `../../../docs/test-reports/assets/${issueSlug}`)
const screenshotDir = path.join(assetRoot, 'local')
const hostOrigin = (process.env.UAT_HOST_ORIGIN ?? 'http://127.0.0.1:3001').replace(/\/$/, '')
const apiBase = (process.env.UAT_RUNTIME_API_BASE ?? 'http://127.0.0.1:8001/api').replace(/\/$/, '')

const sourceA = {
  endpoint: 'http://60.251.229.32',
  username: 'volapu',
  password: 'admin',
}

const sourceB = {
  endpoint: 'http://61.216.55.133',
  username: 'admin',
  password: 'admin',
}

interface ScreenshotRecord {
  file: string
  step: string
  action: string
  note: string
}

interface SettingsItem {
  key: string
  value: string
}

interface InitialState {
  connectionPayload: {
    base_url: string
    username: string
    password: string
  }
  hostChannels: { items: Array<Record<string, unknown>>; total: number }
  hostStatus: Record<string, unknown>
  activeBaselineId: string
}

async function captureScreenshot(
  page: Page,
  screenshots: ScreenshotRecord[],
  file: string,
  step: string,
  action: string,
  note: string
) {
  await mkdir(screenshotDir, { recursive: true })
  await page.screenshot({
    path: path.join(screenshotDir, file),
    fullPage: true,
  })
  screenshots.push({ file, step, action, note })
}

async function getJson(request: APIRequestContext, url: string) {
  const response = await request.get(url)
  expect(response.ok()).toBeTruthy()
  return response.json()
}

async function putHostSync(
  request: APIRequestContext,
  url: string,
  data: Record<string, unknown>
) {
  const response = await request.put(url, {
    headers: {
      'Content-Type': 'application/json',
      'X-ASNS-Host-Sync': 'true',
    },
    data,
  })
  expect(response.ok()).toBeTruthy()
  return response.json()
}

async function patchSettings(
  request: APIRequestContext,
  settings: Record<string, string>
) {
  const response = await request.patch(`${apiBase}/settings`, {
    headers: {
      'Content-Type': 'application/json',
    },
    data: {
      settings,
    },
  })
  expect(response.ok()).toBeTruthy()
  return response.json()
}

async function restoreInitialState(request: APIRequestContext, initialState: InitialState) {
  await putHostSync(request, `${apiBase}/settings/edc-connection`, initialState.connectionPayload)
  await putHostSync(request, `${apiBase}/settings/host-channels`, {
    items: initialState.hostChannels.items,
  })
  await putHostSync(request, `${apiBase}/settings/host-connectivity-status`, initialState.hostStatus)
  await patchSettings(request, {
    active_baseline_id: initialState.activeBaselineId,
  })
}

test('S04-TC02 rerun passes on current host build', async ({ page, request }) => {
  test.setTimeout(180000)

  const screenshots: ScreenshotRecord[] = []
  const settingsResponse = (await getJson(request, `${apiBase}/settings`)) as { items: SettingsItem[] }
  const initialHostChannels = (await getJson(request, `${apiBase}/settings/host-channels`)) as {
    items: Array<Record<string, unknown>>
    total: number
  }
  const initialHostStatus = (await getJson(request, `${apiBase}/settings/host-connectivity-status`)) as Record<
    string,
    unknown
  >
  const initialRuntime = await getJson(request, `${apiBase}/settings/runtime-status`)

  const settingsMap = new Map(settingsResponse.items.map(item => [item.key, item.value]))
  const initialState: InitialState = {
    connectionPayload: {
      base_url: settingsMap.get('edc_base_url') ?? '',
      username: settingsMap.get('edc_username') ?? '',
      password: settingsMap.get('edc_password') ?? '',
    },
    hostChannels: initialHostChannels,
    hostStatus: initialHostStatus,
    activeBaselineId: settingsMap.get('active_baseline_id') ?? '',
  }

  try {
    expect(initialRuntime.overall_code).toBe('ready')
    expect(initialRuntime.edc.base_url).toBe(sourceA.endpoint)

    await page.goto(hostOrigin, { waitUntil: 'networkidle' })
    await page.locator('button').nth(6).click()
    await expect(page.getByText('已添加通道清单', { exact: true })).toBeVisible()
    await captureScreenshot(
      page,
      screenshots,
      's04-tc02-step-01-open-settings-rerun.png',
      '步骤 01：进入设置页',
      'open-settings',
      '宿主设置页已打开，准备切换到 source B。'
    )

    const endpointInput = page.locator('input[type="text"]').nth(0)
    const usernameInput = page.locator('input[type="text"]').nth(1)
    const passwordInput = page.locator('input[type="password"]').nth(0)

    await endpointInput.fill(sourceB.endpoint)
    await captureScreenshot(
      page,
      screenshots,
      's04-tc02-step-02-fill-new-endpoint-rerun.png',
      '步骤 02：填入新地址后',
      'fill-endpoint',
      '新源 B 地址已填入。'
    )

    await usernameInput.fill(sourceB.username)
    await passwordInput.fill(sourceB.password)
    await captureScreenshot(
      page,
      screenshots,
      's04-tc02-step-03-fill-credentials-rerun.png',
      '步骤 03：填写完整',
      'fill-credentials',
      '新源 B 账号与密码已填写。'
    )

    const testConnectionResponsePromise = page.waitForResponse(response => {
      return response.url().includes('/host-api/edc/test-connection') && response.status() === 200
    })

    await page.getByRole('button', { name: '测试连接' }).click()
    await testConnectionResponsePromise
    await expect(page.getByText('EDC 连接就绪')).toBeVisible({ timeout: 30000 })
    await expect(page.locator('body')).toContainText('连接成功，已读取 3 台设备 / 788 通道。')
    await captureScreenshot(
      page,
      screenshots,
      's04-tc02-step-04-test-connection-result-rerun.png',
      '步骤 04：测试连接结果',
      'test-connection',
      '页面已显示在线与连接就绪，新源连接成功证据可见。'
    )

    await expect
      .poll(async () => {
        const hostStatus = (await getJson(
          request,
          `${apiBase}/settings/host-connectivity-status`
        )) as {
          is_connected: boolean
          meta: { source: string }
        }
        return `${hostStatus.is_connected}-${hostStatus.meta.source}`
      })
      .toBe(`true-${sourceB.endpoint}`)

    const runtimeAfterTest = await getJson(request, `${apiBase}/settings/runtime-status`)
    expect(runtimeAfterTest.overall_code).toBe('no_enabled_channels')

    await page.getByRole('button', { name: '保存设置' }).click()
    await expect(page.locator('body')).toContainText('设置已保存，时间：')
    await captureScreenshot(
      page,
      screenshots,
      's04-tc02-step-05-save-after-rerun.png',
      '步骤 05：保存后',
      'save-settings',
      '保存反馈可见，页面仍保持新源在线状态。'
    )

    const settingsAfterSave = (await getJson(request, `${apiBase}/settings`)) as { items: SettingsItem[] }
    const settingsAfterSaveMap = new Map(settingsAfterSave.items.map(item => [item.key, item.value]))
    const hostConnectivityAfterSave = (await getJson(
      request,
      `${apiBase}/settings/host-connectivity-status`
    )) as {
      is_connected: boolean
      machine_name: string
      meta: { source: string; sensor_count: number; channel_count: number; enabled_channel_count: number }
    }
    const runtimeAfterSave = await getJson(request, `${apiBase}/settings/runtime-status`)

    expect(settingsAfterSaveMap.get('edc_base_url')).toBe(sourceB.endpoint)
    expect(settingsAfterSaveMap.get('edc_username')).toBe(sourceB.username)
    expect(hostConnectivityAfterSave.is_connected).toBe(true)
    expect(hostConnectivityAfterSave.meta.source).toBe(sourceB.endpoint)
    expect(runtimeAfterSave.overall_code).toBe('no_enabled_channels')

    const evidence = {
      issue: issueSlug,
      environment: 'local',
      script_path: 'apps/web/e2e/s04-tc02-source-switch-rerun.spec.ts',
      host_origin: hostOrigin,
      api_base: apiBase,
      screenshots,
      initial_runtime: initialRuntime,
      runtime_after_test_connection: runtimeAfterTest,
      settings_after_save: {
        edc_base_url: settingsAfterSaveMap.get('edc_base_url'),
        edc_username: settingsAfterSaveMap.get('edc_username'),
      },
      host_connectivity_after_save: hostConnectivityAfterSave,
      runtime_after_save: runtimeAfterSave,
      verdict: 'PASS',
      observation:
        '当前新构建宿主下，source B 测试连接成功，保存后仍维持在线；运行态为 no_enabled_channels，而非 host_disconnected。',
    }

    await mkdir(assetRoot, { recursive: true })
    await writeFile(path.join(assetRoot, 'evidence.json'), JSON.stringify(evidence, null, 2), 'utf-8')
  } finally {
    await restoreInitialState(request, initialState)
    const finalRuntime = await getJson(request, `${apiBase}/settings/runtime-status`)
    expect(finalRuntime.overall_code).toBe('ready')
  }
})
