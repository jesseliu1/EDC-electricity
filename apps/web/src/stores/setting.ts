import { defineStore } from 'pinia'
import { settingApi } from '@/api/setting'

export interface SystemSettings {
  defaultTolerancePercent: number
  edcBaseUrl: string
  edcApiKey: string
  reportGenerationHour: number
}

const defaultSettings: SystemSettings = {
  defaultTolerancePercent: 15,
  edcBaseUrl: 'http://localhost:8080',
  edcApiKey: '',
  reportGenerationHour: 2
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
    }
  }
})
