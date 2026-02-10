import { defineStore } from 'pinia'
import dayjs from 'dayjs'
import { heatApi } from '@/api/heat'
import type { HeatListQuery, HeatResponseItem, HeatStatus } from '@/api/heat'

export interface HeatItem {
  id: string
  heatNo: string
  startTime: string
  endTime: string
  baselineId: string | null
  deviationPercent: number | null
  avgDeviationPercent: number | null
  status: HeatStatus
  temperature: number | null
}

interface HeatFilters {
  status: 'all' | HeatStatus
  dateRange: [Date, Date] | null
}

function mapHeat(item: HeatResponseItem): HeatItem {
  return {
    id: item.id,
    heatNo: item.heat_no,
    startTime: dayjs(item.start_time).format('YYYY-MM-DD HH:mm'),
    endTime: dayjs(item.end_time).format('YYYY-MM-DD HH:mm'),
    baselineId: item.baseline_id,
    deviationPercent: item.deviation_percent,
    avgDeviationPercent: item.avg_deviation_percent,
    status: item.status,
    temperature: item.temperature
  }
}

function mockHeats(page: number, pageSize: number, status: 'all' | HeatStatus): { items: HeatItem[]; total: number } {
  const total = 42
  const all = Array.from({ length: total }).map((_, idx) => {
    const now = dayjs().subtract(idx + 1, 'hour')
    const currentStatus: HeatStatus = idx % 5 === 0 ? 'abnormal' : idx % 7 === 0 ? 'pending' : 'normal'
    return {
      id: `mock-heat-${idx + 1}`,
      heatNo: `H${dayjs().format('YYYYMMDD')}-${String(idx + 1).padStart(3, '0')}`,
      startTime: now.format('YYYY-MM-DD HH:mm'),
      endTime: now.add(45, 'minute').format('YYYY-MM-DD HH:mm'),
      baselineId: idx % 2 === 0 ? 'baseline-001' : null,
      deviationPercent: currentStatus === 'pending' ? null : Number((3 + (idx % 8) * 1.7).toFixed(1)),
      avgDeviationPercent: currentStatus === 'pending' ? null : Number((2 + (idx % 6) * 1.2).toFixed(1)),
      status: currentStatus,
      temperature: 1450 + (idx % 5) * 6
    }
  })

  const filtered = status === 'all' ? all : all.filter(item => item.status === status)
  const start = (page - 1) * pageSize
  const end = start + pageSize
  return {
    items: filtered.slice(start, end),
    total: filtered.length
  }
}

export const useHeatStore = defineStore('heat', {
  state: () => ({
    list: [] as HeatItem[],
    loading: false,
    page: 1,
    pageSize: 10,
    total: 0,
    filters: {
      status: 'all',
      dateRange: null
    } as HeatFilters
  }),
  actions: {
    async fetchList() {
      this.loading = true
      try {
        const query: HeatListQuery = {
          page: this.page,
          page_size: this.pageSize,
          status: this.filters.status === 'all' ? undefined : this.filters.status,
          start_date: this.filters.dateRange?.[0]
            ? dayjs(this.filters.dateRange[0]).toISOString()
            : undefined,
          end_date: this.filters.dateRange?.[1]
            ? dayjs(this.filters.dateRange[1]).toISOString()
            : undefined
        }
        const data = await heatApi.list(query)
        this.list = data.items.map(mapHeat)
        this.total = data.total
      } catch (error) {
        console.warn('Heat list fallback to mock.', error)
        const mock = mockHeats(this.page, this.pageSize, this.filters.status)
        this.list = mock.items
        this.total = mock.total
      } finally {
        this.loading = false
      }
    },
    async setStatus(status: 'all' | HeatStatus) {
      this.filters.status = status
      this.page = 1
      await this.fetchList()
    },
    async setDateRange(dateRange: [Date, Date] | null) {
      this.filters.dateRange = dateRange
      this.page = 1
      await this.fetchList()
    },
    async setPage(page: number) {
      this.page = page
      await this.fetchList()
    },
    async setPageSize(pageSize: number) {
      this.pageSize = pageSize
      this.page = 1
      await this.fetchList()
    }
  }
})
