import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/setting', () => ({
  settingApi: {
    getAll: vi.fn()
  }
}))

vi.mock('@/api/heat', () => ({
  heatApi: {
    refreshRuntime: vi.fn()
  }
}))

vi.mock('@/utils/time', () => ({
  normalizeTimezone: (value: string) => value,
  setPlantTimezone: vi.fn()
}))

import { settingApi } from '@/api/setting'
import { useSettingStore } from '@/stores/setting'

describe('setting store defaults', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(settingApi.getAll).mockReset()
  })

  it('defaults to fixed interval 30 minutes before loading', () => {
    const store = useSettingStore()

    expect(store.data.cuttingMode).toBe('fixed_interval')
    expect(store.data.fixedIntervalMinutes).toBe(30)
  })

  it('keeps fixed interval 30 minutes when backend returns empty cutting config', async () => {
    vi.mocked(settingApi.getAll).mockResolvedValue({
      items: []
    })

    const store = useSettingStore()
    await store.fetchSettings()

    expect(store.data.cuttingMode).toBe('fixed_interval')
    expect(store.data.fixedIntervalMinutes).toBe(30)
  })
})
