import { defineStore } from 'pinia'
import { settingApi } from '@/api/setting'

export interface SystemSettings {
  defaultTolerancePercent: number
  edcBaseUrl: string
  edcApiKey: string
  reportGenerationHour: number
  timeTolerancePercent: number
  majorIssueDurationMinutes: number
  workStartTime: string
  workEndTime: string
  breakPeriods: string
  baselineLengthScopeMode: 'definition' | 'system' | 'production_line'
}

export interface HostConnectivitySummary {
  isConnected: boolean
  machineName: string
  lastSyncLabel: string
  source: string
  sensorCount: number
  channelCount: number
  enabledChannelCount: number
}

const defaultSettings: SystemSettings = {
  defaultTolerancePercent: 15,
  edcBaseUrl: 'http://localhost:8080',
  edcApiKey: '',
  reportGenerationHour: 2,
  timeTolerancePercent: 10,
  majorIssueDurationMinutes: 8,
  workStartTime: '08:00',
  workEndTime: '18:00',
  breakPeriods: '12:00-13:00',
  baselineLengthScopeMode: 'definition'
}

const defaultHostConnectivity: HostConnectivitySummary = {
  isConnected: false,
  machineName: '--',
  lastSyncLabel: '--',
  source: '--',
  sensorCount: 0,
  channelCount: 0,
  enabledChannelCount: 0
}

export const useSettingStore = defineStore('setting', {
  state: () => ({
    data: { ...defaultSettings },
    hostConnectivity: { ...defaultHostConnectivity },
    loading: false
  }),
  actions: {
    async fetchSettings() {
      this.loading = true
      try {
        const [settingsResult, hostConnectivityResult] = await Promise.allSettled([
          settingApi.getAll(),
          settingApi.getHostConnectivityStatus()
        ])

        if (settingsResult.status === 'fulfilled') {
          const map = Object.fromEntries(settingsResult.value.items.map(item => [item.key, item.value]))
          this.data.defaultTolerancePercent = Number(map.default_tolerance_percent || 15)
          this.data.edcBaseUrl = map.edc_base_url || 'http://localhost:8080'
          this.data.edcApiKey = map.edc_api_key || ''
          this.data.reportGenerationHour = Number(map.report_generation_hour || 2)
          this.data.timeTolerancePercent = Number(map.time_tolerance_percent || 10)
          this.data.majorIssueDurationMinutes = Number(map.major_issue_duration_minutes || 8)
          this.data.workStartTime = map.work_start_time || '08:00'
          this.data.workEndTime = map.work_end_time || '18:00'
          this.data.breakPeriods = map.break_periods || '12:00-13:00'
          const mode = map.baseline_length_scope_mode
          this.data.baselineLengthScopeMode =
            mode === 'system' || mode === 'production_line' ? mode : 'definition'
        }

        if (hostConnectivityResult.status === 'fulfilled') {
          this.hostConnectivity = {
            isConnected: hostConnectivityResult.value.is_connected,
            machineName: hostConnectivityResult.value.machine_name,
            lastSyncLabel: hostConnectivityResult.value.last_sync_label,
            source: hostConnectivityResult.value.meta.source,
            sensorCount: hostConnectivityResult.value.meta.sensor_count,
            channelCount: hostConnectivityResult.value.meta.channel_count,
            enabledChannelCount: hostConnectivityResult.value.meta.enabled_channel_count
          }
        } else {
          this.hostConnectivity = { ...defaultHostConnectivity }
        }
      } catch (error) {
        console.warn('Settings fallback to default.', error)
      } finally {
        this.loading = false
      }
    },
    async saveTolerance() {
      await settingApi.updateTolerance(this.data.defaultTolerancePercent)
    },
    async saveReport() {
      await settingApi.updateReport(this.data.reportGenerationHour)
    },
    async saveCutting() {
      await settingApi.updateCutting({
        time_tolerance_percent: this.data.timeTolerancePercent,
        major_issue_duration_minutes: this.data.majorIssueDurationMinutes,
        work_start_time: this.data.workStartTime,
        work_end_time: this.data.workEndTime,
        break_periods: this.data.breakPeriods
          .split(',')
          .map(item => item.trim())
          .filter(Boolean)
      })
      await settingApi.updateBaselineLengthScope(this.data.baselineLengthScopeMode)
    }
  }
})
