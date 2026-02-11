import { client } from './client'

export interface SettingItemResponse {
  key: string
  value: string
  description: string | null
}

export interface SettingsResponse {
  items: SettingItemResponse[]
}

export const settingApi = {
  getAll: () => client.get<SettingsResponse>('/settings'),
  updateBatch: (settings: Record<string, string>) => client.patch('/settings', { settings }),
  updateTolerance: (tolerance_percent: number) =>
    client.put('/settings/tolerance', { tolerance_percent }),
  updateEdc: (base_url: string, api_key?: string) =>
    client.put('/settings/edc-connection', { base_url, api_key }),
  testEdc: () => client.post('/settings/edc-connection/test'),
  updateReport: (generation_hour: number) => client.put('/settings/report', { generation_hour }),
  updateCutting: (payload: {
    time_tolerance_percent: number
    major_issue_duration_minutes: number
    work_start_time: string
    work_end_time: string
    break_periods: string[]
  }) => client.put('/settings/cutting', payload)
}
