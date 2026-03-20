import { client } from './client'

export interface SettingItemResponse {
  key: string
  value: string
  description: string | null
}

export interface SettingsResponse {
  items: SettingItemResponse[]
}

export interface HostChannelItemResponse {
  id: string
  device_name: string
  device_type: string
  area: string
  suid: string
  cuid: string
  channel_name: string
  unit: string
  last_value: string
  status: string
}

export interface HostChannelCollectionResponse {
  items: HostChannelItemResponse[]
  total: number
}

export interface HostConnectivityMetaResponse {
  source: string
  sensor_count: number
  channel_count: number
  enabled_channel_count: number
}

export interface HostConnectivityStatusResponse {
  is_connected: boolean
  machine_name: string
  last_sync_label: string
  meta: HostConnectivityMetaResponse
}

export const settingApi = {
  getAll: () => client.get<SettingsResponse>('/settings'),
  getHostChannels: () => client.get<HostChannelCollectionResponse>('/settings/host-channels'),
  getHostConnectivityStatus: () =>
    client.get<HostConnectivityStatusResponse>('/settings/host-connectivity-status'),
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
  }) => client.put('/settings/cutting', payload),
  updateBaselineLengthScope: (scope_mode: 'definition' | 'system' | 'production_line') =>
    client.put('/settings/baseline-length-scope', { scope_mode })
}
