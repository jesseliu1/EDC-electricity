import { defineStore } from 'pinia'
import dayjs from 'dayjs'
import { baselineApi } from '@/api/baseline'
import type {
  BaselineCreatePayload,
  CurveData,
  CurvePoint,
  BaselineListResponse,
  BaselineResponse,
  BaselineStatus
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
  createdAt: string
  publishedAt: string | null
  sourceHeatId: string
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
    sourceHeatId: item.source_heat_id
  }
}

function mapBaselineList(data: BaselineListResponse): BaselineItem[] {
  return data.items.map(mapBaseline)
}

function mockBaselines(): BaselineItem[] {
  const now = dayjs()
  return [
    {
      id: 'baseline-001',
      name: '标准铸铁基线 v1',
      description: '适用于标准铸铁生产，包含功率与电压稳定段。',
      definitionId: 'def-001',
      definitionName: '标准熔炼基线',
      status: 'published',
      version: 1,
      tolerancePercent: 5,
      createdAt: now.subtract(10, 'day').toISOString(),
      publishedAt: now.subtract(9, 'day').toISOString(),
      sourceHeatId: 'heat-001'
    },
    {
      id: 'baseline-002',
      name: '高强度钢基线 v2',
      description: '用于高强度钢生产，偏差阈值更严格。',
      definitionId: 'def-002',
      definitionName: '高功率熔炼基线',
      status: 'draft',
      version: 2,
      tolerancePercent: 3,
      createdAt: now.subtract(3, 'day').toISOString(),
      publishedAt: null,
      sourceHeatId: 'heat-014'
    },
    {
      id: 'baseline-003',
      name: '旧版铸铁基线',
      description: '旧工艺基线，已停用。',
      definitionId: 'def-001',
      definitionName: '标准熔炼基线',
      status: 'disabled',
      version: 1,
      tolerancePercent: 8,
      createdAt: now.subtract(60, 'day').toISOString(),
      publishedAt: now.subtract(55, 'day').toISOString(),
      sourceHeatId: 'heat-089'
    }
  ]
}

function mockBaselineDetail(id: string): BaselineDetail {
  const mockList = mockBaselines()
  const base = mockList.find(item => item.id === id) || mockList[0] || {
    id: 'baseline-local',
    name: '默认基线',
    description: null,
    definitionId: 'def-001',
    definitionName: '标准熔炼基线',
    status: 'draft' as BaselineStatus,
    version: 1,
    tolerancePercent: 15,
    createdAt: dayjs().toISOString(),
    publishedAt: null,
    sourceHeatId: 'heat-001'
  }
  const powerCurve: CurvePoint[] = Array.from({ length: 20 }).map((_, idx) => ({
    timestamp: dayjs().subtract(20 - idx, 'minute').valueOf(),
    value: Number((420 + Math.sin(idx / 3) * 35 + idx * 0.8).toFixed(1))
  }))
  const voltageCurve: CurvePoint[] = Array.from({ length: 20 }).map((_, idx) => ({
    timestamp: dayjs().subtract(20 - idx, 'minute').valueOf(),
    value: Number((378 + Math.cos(idx / 4) * 6 + idx * 0.2).toFixed(1))
  }))

  return {
    ...base,
    curvesData: [
      {
        metric_id: 'metric-001',
        metric_name: '功率',
        unit: 'kW',
        color: '#409EFF',
        points: powerCurve
      },
      {
        metric_id: 'metric-002',
        metric_name: '电压',
        unit: 'V',
        color: '#67C23A',
        points: voltageCurve
      }
    ],
    powerCurve,
    voltageCurve,
    temperature: 1465
  }
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
        console.warn('Baseline list fallback to mock.', error)
        const mock = mockBaselines()
        this.list =
          this.currentFilter === 'all'
            ? mock
            : mock.filter(item => item.status === this.currentFilter)
      } finally {
        this.loading = false
      }
    },
    async setFilter(filter: BaselineFilter) {
      this.currentFilter = filter
      await this.fetchList()
    },
    async publishBaseline(id: string) {
      try {
        const updated = await baselineApi.publish(id)
        const index = this.list.findIndex(item => item.id === id)
        if (index >= 0) this.list[index] = mapBaseline(updated)
      } catch (error) {
        console.warn('Publish baseline fallback to local update.', error)
        const target = this.list.find(item => item.id === id)
        if (target) target.status = 'published'
      }
    },
    async disableBaseline(id: string) {
      try {
        const updated = await baselineApi.disable(id)
        const index = this.list.findIndex(item => item.id === id)
        if (index >= 0) this.list[index] = mapBaseline(updated)
      } catch (error) {
        console.warn('Disable baseline fallback to local update.', error)
        const target = this.list.find(item => item.id === id)
        if (target) target.status = 'disabled'
      }
    },
    async deleteBaseline(id: string) {
      try {
        await baselineApi.remove(id)
      } catch (error) {
        console.warn('Delete baseline fallback to local update.', error)
      }
      this.list = this.list.filter(item => item.id !== id)
    },
    async createBaseline(payload: BaselineCreatePayload, mode: 'draft' | 'publish') {
      try {
        const created = await baselineApi.create(payload)
        if (mode === 'publish') {
          const published = await baselineApi.publish(created.id)
          this.list.unshift(mapBaseline(published))
          return
        }
        this.list.unshift(mapBaseline(created))
      } catch (error) {
        console.warn('Create baseline fallback to local mock.', error)
        const now = dayjs().toISOString()
        this.list.unshift({
          id: `local-${Date.now()}`,
          name: payload.name,
          description: payload.description || null,
          definitionId: payload.definition_id,
          definitionName: '本地定义',
          status: mode === 'publish' ? 'published' : 'draft',
          version: 1,
          tolerancePercent: payload.tolerance_percent,
          createdAt: now,
          publishedAt: mode === 'publish' ? now : null,
          sourceHeatId: payload.source_heat_id
        })
      }
    },
    async fetchDetail(id: string) {
      this.loading = true
      try {
        const data = await baselineApi.get(id)
        this.current = mapBaselineDetail(data)
      } catch (error) {
        console.warn('Baseline detail fallback to mock.', error)
        this.current = mockBaselineDetail(id)
      } finally {
        this.loading = false
      }
    },
    async fetchVersionHistory(id: string) {
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
        console.warn('Baseline version history fallback to mock.', error)
        const all = mockBaselines()
        this.versionHistory = all
          .filter(item => item.id === id || item.name.includes('基线'))
          .sort((a, b) => b.version - a.version)
      }
    }
  }
})
