import { defineStore } from 'pinia'
import { reportApi } from '@/api/report'
import type { DailyReportDetail, DailyReportSummary } from '@/api/report'

export interface ReportItem {
  date: string
  totalHeats: number
  normalHeats: number
  abnormalHeats: number
  avgDeviationScore: number
  pendingTasks: number
  completedTasks: number
  generatedAt: string | null
}

export interface ReportDetail extends ReportItem {
  normalRate: number
  effectiveHours: number
  topDeviations: Array<{ heatNo: string; deviationScore: number }>
}

function resolveErrorMessage(error: unknown): string {
  if (!error || typeof error !== 'object') {
    return '报表详情加载失败'
  }

  const response = (error as { response?: { data?: { message?: string; detail?: string } } }).response
  const message = response?.data?.message
  if (typeof message === 'string' && message.trim()) {
    return message
  }

  const detail = response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }

  return '报表详情加载失败'
}

function mapSummary(item: DailyReportSummary): ReportItem {
  return {
    date: item.date,
    totalHeats: item.total_heats,
    normalHeats: item.normal_heats,
    abnormalHeats: item.abnormal_heats,
    avgDeviationScore: item.avg_deviation_score,
    pendingTasks: item.pending_tasks,
    completedTasks: item.completed_tasks,
    generatedAt: item.generated_at
  }
}

function mapDetail(item: DailyReportDetail): ReportDetail {
  const topDeviationRows = Array.isArray(item.top_deviations) ? item.top_deviations : []

  return {
    ...mapSummary(item),
    normalRate: Number(item.normal_rate ?? 0),
    effectiveHours: Number(item.effective_hours ?? 0),
    topDeviations: topDeviationRows
      .filter(row => typeof row?.heat_no === 'string')
      .map(row => ({
        heatNo: row.heat_no,
        deviationScore: Number(row.deviation_score ?? 0)
      }))
  }
}

export const useReportStore = defineStore('report', {
  state: () => ({
    list: [] as ReportItem[],
    current: null as ReportDetail | null,
    listLoading: false,
    detailLoading: false,
    detailLoaded: false,
    detailError: null as string | null,
    detailRequestToken: 0
  }),
  actions: {
    async fetchList() {
      this.listLoading = true
      try {
        const data = await reportApi.list({ page: 1, page_size: 14 })
        this.list = data.items.map(mapSummary)
      } catch (error) {
        console.error('Report list request failed.', error)
        this.list = []
      } finally {
        this.listLoading = false
      }
    },
    clearDetail() {
      this.detailRequestToken += 1
      this.current = null
      this.detailLoading = false
      this.detailLoaded = false
      this.detailError = null
    },
    async fetchDetail(date: string) {
      const requestToken = this.detailRequestToken + 1
      this.detailRequestToken = requestToken
      this.current = null
      this.detailError = null
      this.detailLoaded = false
      this.detailLoading = true
      try {
        const data = await reportApi.get(date)
        if (requestToken !== this.detailRequestToken) {
          return
        }
        this.current = mapDetail(data)
        this.detailLoaded = true
      } catch (error) {
        if (requestToken !== this.detailRequestToken) {
          return
        }
        console.error('Report detail request failed.', error)
        this.current = null
        this.detailError = resolveErrorMessage(error)
      } finally {
        if (requestToken === this.detailRequestToken) {
          this.detailLoading = false
        }
      }
    }
  }
})
