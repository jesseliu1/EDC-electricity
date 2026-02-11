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
  breakPeriods: '12:00-13:00'
}

export const useSettingStore = defineStore('setting', {
  state: () => ({
    data: { ...defaultSettings },
    loading: false
  }),
  actions: {
    async fetchSettings() {
      this.loading = true
      try {
        const response = await settingApi.getAll()
        const map = Object.fromEntries(response.items.map(item => [item.key, item.value]))
        this.data.defaultTolerancePercent = Number(map.default_tolerance_percent || 15)
        this.data.edcBaseUrl = map.edc_base_url || 'http://localhost:8080'
        this.data.edcApiKey = map.edc_api_key || ''
        this.data.reportGenerationHour = Number(map.report_generation_hour || 2)
        this.data.timeTolerancePercent = Number(map.time_tolerance_percent || 10)
        this.data.majorIssueDurationMinutes = Number(map.major_issue_duration_minutes || 8)
        this.data.workStartTime = map.work_start_time || '08:00'
        this.data.workEndTime = map.work_end_time || '18:00'
        this.data.breakPeriods = map.break_periods || '12:00-13:00'
      } catch (error) {
        console.warn('Settings fallback to default.', error)
      } finally {
        this.loading = false
      }
    },
    async saveTolerance() {
      await settingApi.updateTolerance(this.data.defaultTolerancePercent)
    },
    async saveEdc() {
      await settingApi.updateEdc(this.data.edcBaseUrl, this.data.edcApiKey)
    },
    async testEdc() {
      await settingApi.testEdc()
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
    }
  }
})
