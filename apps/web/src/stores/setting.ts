import { defineStore } from 'pinia'
import { heatApi } from '@/api/heat'
import { settingApi } from '@/api/setting'
import { normalizeTimezone, setPlantTimezone } from '@/utils/time'

export interface SystemSettings {
  defaultTolerancePercent: number
  reportGenerationHour: number
  cuttingMode: 'signal_inference' | 'fixed_interval'
  fixedIntervalMinutes: number | null
  timeTolerancePercent: number
  majorIssueDurationMinutes: number
  plantTimezone: string
  workStartTime: string
  workEndTime: string
  breakPeriods: string
  baselineLengthScopeMode: 'definition' | 'system' | 'production_line'
}

const defaultSettings: SystemSettings = {
  defaultTolerancePercent: 15,
  reportGenerationHour: 2,
  cuttingMode: 'signal_inference',
  fixedIntervalMinutes: null,
  timeTolerancePercent: 10,
  majorIssueDurationMinutes: 8,
  plantTimezone: 'Asia/Shanghai',
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
        const cuttingMode = map.cutting_mode === 'fixed_interval' ? 'fixed_interval' : 'signal_inference'
        const fixedIntervalText = map.fixed_interval_minutes?.trim() || ''
        const nextData: SystemSettings = {
          defaultTolerancePercent: Number(map.default_tolerance_percent || 15),
          reportGenerationHour: Number(map.report_generation_hour || 2),
          cuttingMode,
          fixedIntervalMinutes: fixedIntervalText ? Number(fixedIntervalText) : null,
          timeTolerancePercent: Number(map.time_tolerance_percent || 10),
          majorIssueDurationMinutes: Number(map.major_issue_duration_minutes || 8),
          plantTimezone: normalizeTimezone(map.plant_timezone || 'Asia/Shanghai'),
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
        setPlantTimezone(nextData.plantTimezone)
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
        cutting_mode: this.data.cuttingMode,
        fixed_interval_minutes:
          this.data.cuttingMode === 'fixed_interval' ? this.data.fixedIntervalMinutes : null,
        time_tolerance_percent: this.data.timeTolerancePercent,
        major_issue_duration_minutes: this.data.majorIssueDurationMinutes,
        plant_timezone: this.data.plantTimezone,
        work_start_time: this.data.workStartTime,
        work_end_time: this.data.workEndTime,
        break_periods: this.data.breakPeriods
          .split(',')
          .map(item => item.trim())
          .filter(Boolean)
      })
      await settingApi.updateBaselineLengthScope(this.data.baselineLengthScopeMode)
      try {
        await heatApi.refreshRuntime()
      } catch (error) {
        console.warn('Heat runtime refresh after cutting save failed.', error)
      }
      this.savedData.cuttingMode = this.data.cuttingMode
      this.savedData.fixedIntervalMinutes = this.data.fixedIntervalMinutes
      this.savedData.timeTolerancePercent = this.data.timeTolerancePercent
      this.savedData.majorIssueDurationMinutes = this.data.majorIssueDurationMinutes
      this.savedData.plantTimezone = this.data.plantTimezone
      this.savedData.workStartTime = this.data.workStartTime
      this.savedData.workEndTime = this.data.workEndTime
      this.savedData.breakPeriods = this.data.breakPeriods
      this.savedData.baselineLengthScopeMode = this.data.baselineLengthScopeMode
      setPlantTimezone(this.data.plantTimezone)
    },
    resetTolerance() {
      this.data.defaultTolerancePercent = this.savedData.defaultTolerancePercent
      this.data.reportGenerationHour = this.savedData.reportGenerationHour
    }
  }
})
