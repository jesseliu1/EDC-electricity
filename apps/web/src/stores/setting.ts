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

function cloneSettings(settings: SystemSettings): SystemSettings {
  return { ...settings }
}

export const useSettingStore = defineStore('setting', {
  state: () => ({
    data: cloneSettings(defaultSettings),
    savedData: cloneSettings(defaultSettings),
    loading: false
  }),
  actions: {
    async fetchSettings() {
      this.loading = true
      try {
        const settingsResult = await settingApi.getAll()

        const map = Object.fromEntries(settingsResult.items.map(item => [item.key, item.value]))
        const nextData: SystemSettings = {
          defaultTolerancePercent: Number(map.default_tolerance_percent || 15),
          edcBaseUrl: map.edc_base_url || 'http://localhost:8080',
          edcApiKey: map.edc_api_key || '',
          reportGenerationHour: Number(map.report_generation_hour || 2),
          timeTolerancePercent: Number(map.time_tolerance_percent || 10),
          majorIssueDurationMinutes: Number(map.major_issue_duration_minutes || 8),
          workStartTime: map.work_start_time || '08:00',
          workEndTime: map.work_end_time || '18:00',
          breakPeriods: map.break_periods || '12:00-13:00',
          baselineLengthScopeMode: 'definition'
        }
        const mode = map.baseline_length_scope_mode
        nextData.baselineLengthScopeMode =
          mode === 'system' || mode === 'production_line' ? mode : 'definition'
        this.data = cloneSettings(nextData)
        this.savedData = cloneSettings(nextData)
      } catch (error) {
        console.warn('Settings fallback to default.', error)
      } finally {
        this.loading = false
      }
    },
    async saveTolerance() {
      await settingApi.updateTolerance(this.data.defaultTolerancePercent)
      this.savedData.defaultTolerancePercent = this.data.defaultTolerancePercent
    },
    async saveReport() {
      await settingApi.updateReport(this.data.reportGenerationHour)
      this.savedData.reportGenerationHour = this.data.reportGenerationHour
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
      this.savedData.timeTolerancePercent = this.data.timeTolerancePercent
      this.savedData.majorIssueDurationMinutes = this.data.majorIssueDurationMinutes
      this.savedData.workStartTime = this.data.workStartTime
      this.savedData.workEndTime = this.data.workEndTime
      this.savedData.breakPeriods = this.data.breakPeriods
      this.savedData.baselineLengthScopeMode = this.data.baselineLengthScopeMode
    },
    resetTolerance() {
      this.data.defaultTolerancePercent = this.savedData.defaultTolerancePercent
      this.data.reportGenerationHour = this.savedData.reportGenerationHour
    }
  }
})
