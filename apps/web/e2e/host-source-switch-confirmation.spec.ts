import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

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

interface SettingsItem {
  key: string
  value: string
}

test.describe.configure({ mode: 'serial' })

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
}

async function restoreSourceAReadyRuntime(request: APIRequestContext) {
  await putHostSync(request, `${apiBase}/settings/edc-connection`, {
    base_url: sourceA.endpoint,
    username: sourceA.username,
    password: sourceA.password,
  })
  await putHostSync(request, `${apiBase}/settings/host-channels`, {
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
        status: 'online',
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
        status: 'online',
      },
    ],
  })
  await putHostSync(request, `${apiBase}/settings/host-connectivity-status`, {
    is_connected: true,
    machine_name: 'EDC Test Gateway',
    last_sync_label: '2026-03-30 12:00:00',
    meta: {
      source: sourceA.endpoint,
      sensor_count: 26,
      channel_count: 2286,
      enabled_channel_count: 6,
    },
  })
}

async function openSettings(page: Page) {
  await page.goto(hostOrigin, { waitUntil: 'networkidle' })
  await page.locator('button').nth(6).click()
  await expect(page.getByText('已添加通道清单', { exact: true })).toBeVisible()
}

async function fillSourceB(page: Page) {
  await page.locator('input[type="text"]').nth(0).fill(sourceB.endpoint)
  await page.locator('input[type="text"]').nth(1).fill(sourceB.username)
  await page.locator('input[type="password"]').nth(0).fill(sourceB.password)
}

async function expectSourceSwitchDialog(page: Page) {
  await expect(page.getByText('切换新的 EDC 数据源', { exact: true })).toBeVisible()
  await expect(page.getByText('这会清掉当前源下的宿主已添加通道', { exact: false })).toBeVisible()
}

test('host source switch confirmation guards cancel and confirm flows', async ({ page, request }) => {
  test.setTimeout(180000)

  await restoreSourceAReadyRuntime(request)
  const settingsResponse = (await getJson(request, `${apiBase}/settings`)) as { items: SettingsItem[] }
  const initialRuntime = await getJson(request, `${apiBase}/settings/runtime-status`)

  const settingsMap = new Map(settingsResponse.items.map(item => [item.key, item.value]))

  try {
    expect(initialRuntime.overall_code).toBe('ready')
    expect(settingsMap.get('edc_base_url')).toBe(sourceA.endpoint)

    await openSettings(page)
    await fillSourceB(page)
    await page.getByRole('button', { name: '测试连接' }).click()

    await expectSourceSwitchDialog(page)

    await page.getByRole('button', { name: '取消' }).click()
    await expect(page.getByText('切换新的 EDC 数据源', { exact: true })).toHaveCount(0)
    await expect(page.locator('body')).toContainText('已取消换源，本次操作未执行。')

    const runtimeAfterCancel = await getJson(request, `${apiBase}/settings/runtime-status`)
    expect(runtimeAfterCancel.overall_code).toBe('ready')
    expect(runtimeAfterCancel.edc.base_url).toBe(sourceA.endpoint)

    const testConnectionResponsePromise = page.waitForResponse(response => {
      return response.url().includes('/host-api/edc/test-connection') && response.status() === 200
    })

    await page.getByRole('button', { name: '测试连接' }).click()
    await expectSourceSwitchDialog(page)
    await page.getByRole('button', { name: '确认切换' }).click()
    await testConnectionResponsePromise

    await expect(page.getByText('EDC 连接就绪')).toBeVisible({ timeout: 30000 })
    await expect(page.locator('body')).toContainText('连接成功，已读取 3 台设备 / 788 通道。')

    const runtimeAfterConfirm = await getJson(request, `${apiBase}/settings/runtime-status`)
    expect(runtimeAfterConfirm.overall_code).toBe('no_enabled_channels')
    expect(runtimeAfterConfirm.edc.base_url).toBe(sourceB.endpoint)
    expect(runtimeAfterConfirm.host.meta.source).toBe(sourceB.endpoint)
  } finally {
    await restoreSourceAReadyRuntime(request)
    const finalRuntime = await getJson(request, `${apiBase}/settings/runtime-status`)
    expect(finalRuntime.overall_code).toBe('ready')
  }
})

test('host source switch confirmation continues into sync channels after confirm', async ({
  page,
  request,
}) => {
  test.setTimeout(180000)

  await restoreSourceAReadyRuntime(request)

  try {
    await openSettings(page)
    await fillSourceB(page)

    const syncResponsePromise = page.waitForResponse(response => {
      return response.url().includes('/host-api/edc/sync-channels') && response.status() === 200
    })

    await page.getByRole('button', { name: '同步通道' }).click()
    await expectSourceSwitchDialog(page)
    await page.getByRole('button', { name: '确认切换' }).click()
    await syncResponsePromise

    await expect(page.locator('body')).toContainText('同步完成，已刷新 788 条通道目录。')
    await expect(page.getByText('EDC 连接就绪')).toBeVisible({ timeout: 30000 })
    await expect(page.locator('body')).toContainText('3 devices / 788 channels')

    const runtimeAfterSync = await getJson(request, `${apiBase}/settings/runtime-status`)
    const hostStatusAfterSync = await getJson(request, `${apiBase}/settings/host-connectivity-status`)
    const hostChannelsAfterSync = await getJson(request, `${apiBase}/settings/host-channels`)

    expect(runtimeAfterSync.overall_code).toBe('no_enabled_channels')
    expect(runtimeAfterSync.edc.base_url).toBe(sourceB.endpoint)
    expect(hostStatusAfterSync.is_connected).toBe(true)
    expect(hostStatusAfterSync.meta.source).toBe(sourceB.endpoint)
    expect(hostChannelsAfterSync.total).toBe(0)
  } finally {
    await restoreSourceAReadyRuntime(request)
    const finalRuntime = await getJson(request, `${apiBase}/settings/runtime-status`)
    expect(finalRuntime.overall_code).toBe('ready')
  }
})

test('host source switch confirmation continues into save settings after confirm', async ({
  page,
  request,
}) => {
  test.setTimeout(180000)

  await restoreSourceAReadyRuntime(request)

  try {
    await openSettings(page)
    await fillSourceB(page)

    await page.getByRole('button', { name: '保存设置' }).click()
    await expectSourceSwitchDialog(page)
    await page.getByRole('button', { name: '确认切换' }).click()

    await expect(page.locator('body')).toContainText('设置已保存，时间：')

    const runtimeAfterApply = await getJson(request, `${apiBase}/settings/runtime-status`)
    const hostStatusAfterApply = await getJson(request, `${apiBase}/settings/host-connectivity-status`)
    const hostChannelsAfterApply = await getJson(request, `${apiBase}/settings/host-channels`)
    const settingsAfterApply = (await getJson(request, `${apiBase}/settings`)) as { items: SettingsItem[] }
    const settingsMap = new Map(settingsAfterApply.items.map(item => [item.key, item.value]))

    expect(runtimeAfterApply.overall_code).toBe('host_disconnected')
    expect(runtimeAfterApply.edc.base_url).toBe(sourceB.endpoint)
    expect(hostStatusAfterApply.is_connected).toBe(false)
    expect(hostStatusAfterApply.meta.source).toBe(sourceB.endpoint)
    expect(hostChannelsAfterApply.total).toBe(0)
    expect(settingsMap.get('edc_base_url')).toBe(sourceB.endpoint)
    expect(settingsMap.get('edc_username')).toBe(sourceB.username)
  } finally {
    await restoreSourceAReadyRuntime(request)
    const finalRuntime = await getJson(request, `${apiBase}/settings/runtime-status`)
    expect(finalRuntime.overall_code).toBe('ready')
  }
})
