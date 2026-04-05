import { defineStore } from 'pinia'
import { baselineApi } from '@/api/baseline'
import type {
  BaselineCreatePayload,
  BaselineCurveSource,
  BaselineUpdatePayload,
  CurveData,
  CurvePoint,
  BaselineListResponse,
  BaselineResponse,
  BaselineStatus,
  BaselineSummary
} from '@/api/baseline'

export interface BaselineItem {
  id: string
  name: string
  description: string | null
  definitionId: string
  definitionName: string
  status: BaselineStatus
  version: number
  tolerancePercent: number
  createdAt: number
  publishedAt: number | null
  curveSource: BaselineCurveSource
  sourceHeatId: string | null
  selectedStartTime: number | null
  selectedEndTime: number | null
}

export interface BaselineDetail extends BaselineItem {
  curvesData: CurveData[]
  powerCurve: CurvePoint[]
  voltageCurve: CurvePoint[]
  temperature: number | null
}

function mapBaseline(item: BaselineResponse): BaselineItem {
  return {
    id: item.id,
    name: item.name,
    description: item.description,
    definitionId: item.definition_id,
    definitionName: item.definition_name,
    status: item.status,
    version: item.version,
    tolerancePercent: item.tolerance_percent,
    createdAt: item.created_at,
    publishedAt: item.published_at,
    curveSource: item.curve_source,
    sourceHeatId: item.source_heat_id,
    selectedStartTime: item.selected_start_time ?? null,
    selectedEndTime: item.selected_end_time ?? null
  }
}

function mapBaselineList(data: BaselineListResponse): BaselineItem[] {
  return data.items.map(mapBaseline)
}

function mapBaselineSummary(data: BaselineSummary | null) {
  return data?.id || null
}

function mapBaselineDetail(item: BaselineResponse): BaselineDetail {
  return {
    ...mapBaseline(item),
    curvesData: item.curves_data || [],
    powerCurve: item.power_curve || [],
    voltageCurve: item.voltage_curve || [],
    temperature: item.temperature ?? null
  }
}

type BaselineFilter = 'all' | BaselineStatus

export const useBaselineStore = defineStore('baseline', {
  state: () => ({
    list: [] as BaselineItem[],
    current: null as BaselineDetail | null,
    versionHistory: [] as BaselineItem[],
    currentFilter: 'all' as BaselineFilter,
    activeBaselineId: null as string | null,
    loading: false
  }),
  getters: {
    filteredList: state => {
      if (state.currentFilter === 'all') {
        return state.list
      }
      return state.list.filter(item => item.status === state.currentFilter)
    }
  },
  actions: {
    async fetchList() {
      this.loading = true
      try {
        const data = await baselineApi.list(
          this.currentFilter === 'all' ? undefined : this.currentFilter
        )
        this.list = mapBaselineList(data)
      } catch (error) {
        console.error('Baseline list request failed.', error)
        this.list = []
      } finally {
        this.loading = false
      }
    },
    async fetchActiveBaseline() {
      try {
        const data = await baselineApi.getActive()
        this.activeBaselineId = mapBaselineSummary(data)
      } catch (error) {
        console.error('Active baseline request failed.', error)
        this.activeBaselineId = null
      }
    },
    async setFilter(filter: BaselineFilter) {
      this.currentFilter = filter
      await this.fetchList()
    },
    async activateBaseline(id: string) {
      try {
        const summary = await baselineApi.activate(id)
        this.activeBaselineId = summary.id
      } catch (error) {
        console.warn('Activate baseline failed.', error)
        return false
      }
      return true
    },
    async publishBaseline(id: string) {
      try {
        const updated = await baselineApi.publish(id)
        const index = this.list.findIndex(item => item.id === id)
        if (index >= 0) this.list[index] = mapBaseline(updated)
        await this.fetchActiveBaseline()
      } catch (error) {
        console.error('Publish baseline failed.', error)
        throw error
      }
    },
    async disableBaseline(id: string) {
      try {
        const updated = await baselineApi.disable(id)
        const index = this.list.findIndex(item => item.id === id)
        if (index >= 0) this.list[index] = mapBaseline(updated)
        await this.fetchActiveBaseline()
      } catch (error) {
        console.error('Disable baseline failed.', error)
        throw error
      }
    },
    async deleteBaseline(id: string) {
      try {
        await baselineApi.remove(id)
      } catch (error) {
        console.error('Delete baseline failed.', error)
        throw error
      }
      this.list = this.list.filter(item => item.id !== id)
    },
    async createBaseline(payload: BaselineCreatePayload, mode: 'draft' | 'publish') {
      try {
        const created = await baselineApi.create(payload)
        if (mode === 'publish') {
          const published = await baselineApi.publish(created.id)
          this.list.unshift(mapBaseline(published))
          await this.fetchActiveBaseline()
          return true
        }
        this.list.unshift(mapBaseline(created))
        return true
      } catch (error) {
        console.error('Create baseline failed.', error)
        return false
      }
    },
    async fetchDetail(id: string) {
      this.loading = true
      try {
        const data = await baselineApi.get(id)
        this.current = mapBaselineDetail(data)
      } catch (error) {
        console.error('Baseline detail request failed.', error)
        this.current = null
      } finally {
        this.loading = false
      }
    },
    async updateBaseline(id: string, payload: BaselineUpdatePayload) {
      try {
        const updated = await baselineApi.update(id, payload)
        const mapped = mapBaseline(updated)
        const listIndex = this.list.findIndex(item => item.id === id)
        if (listIndex >= 0) {
          this.list[listIndex] = mapped
        }
        if (this.current && this.current.id === id) {
          this.current = {
            ...this.current,
            ...mapped
          }
        }
        return true
      } catch (error) {
        console.warn('Update baseline failed.', error)
        return false
      }
    },
    async fetchVersionHistory() {
      try {
        const list = await baselineApi.list()
        const matched = list.items.filter(item =>
          item.name.replace(/\sv\d+$/i, '') ===
          (this.current?.name || '').replace(/\sv\d+$/i, '')
        )
        this.versionHistory = (matched.length ? matched : list.items)
          .map(mapBaseline)
          .sort((a, b) => b.version - a.version)
      } catch (error) {
        console.error('Baseline version history request failed.', error)
        this.versionHistory = []
      }
    }
  }
})
