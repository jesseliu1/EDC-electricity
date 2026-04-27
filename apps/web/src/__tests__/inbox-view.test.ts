import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

vi.mock('@/utils/time', () => ({
  formatTimestamp: () => '2026-04-23 12:30',
}))

vi.mock('@/api/heat', () => ({
  heatApi: {
    list: vi.fn(),
  },
}))

import { heatApi } from '@/api/heat'
import InboxView from '@/views/InboxView.vue'

describe('InboxView', () => {
  it('loads inbox heats without mutating the shared heat status filter', async () => {
    vi.mocked(heatApi.list).mockResolvedValue({
      items: [
        {
          id: 'heat-001',
          heat_no: 'H20260423-1230',
          start_time: 1713846600000,
          deviation_score: 12.5,
          status: 'abnormal',
        },
        {
          id: 'heat-002',
          heat_no: 'H20260423-1200',
          start_time: 1713844800000,
          deviation_score: null,
          status: 'pending',
        },
        {
          id: 'heat-003',
          heat_no: 'H20260423-1130',
          start_time: 1713843000000,
          deviation_score: 1.2,
          status: 'normal',
        },
      ],
      total: 3,
      page: 1,
      page_size: 100,
      snapshot_status: 'ready',
      snapshot_watermark: null,
      last_refresh_started_at: null,
      last_refresh_completed_at: null,
      refresh_error: null,
      refresh_failure_count: 0,
    })

    const wrapper = mount(InboxView, {
      global: {
        stubs: {
          PageHeader: {
            template: '<div><slot name="actions" /></div>',
          },
          SystemReadinessBanner: true,
        },
      },
    })

    await flushPromises()

    expect(heatApi.list).toHaveBeenCalledWith({
      page: 1,
      page_size: 100,
    })
    expect(wrapper.text()).toContain('2 异常需要处理')
    expect(wrapper.text()).toContain('H20260423-1230')
    expect(wrapper.text()).toContain('H20260423-1200')
    expect(wrapper.text()).not.toContain('H20260423-1130')
  })
})
