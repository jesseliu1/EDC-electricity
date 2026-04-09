import { client } from './client'

export interface DailyReportSummary {
  date: string
  total_heats: number
  normal_heats: number
  abnormal_heats: number
  avg_deviation_score: number
  pending_tasks: number
  completed_tasks: number
  generated_at: string | null
}

export interface DailyReportListResponse {
  items: DailyReportSummary[]
  total: number
}

export interface DailyReportDetail extends DailyReportSummary {
  normal_rate: number
  effective_hours: number
  top_deviations: Array<{ heat_no: string; deviation_score: number }>
}

export const reportApi = {
  list: (params: { page?: number; page_size?: number; start_date?: string; end_date?: string }) =>
    client.get<DailyReportListResponse>('/reports/daily', { params }),
  get: (date: string) => client.get<DailyReportDetail>(`/reports/daily/${date}`),
  generate: (date: string) => client.post<DailyReportDetail>(`/reports/daily/${date}/generate`),
  exportPdfUrl: (date: string) => `${import.meta.env.VITE_API_BASE_URL || '/api'}/reports/daily/${date}/pdf`
}
