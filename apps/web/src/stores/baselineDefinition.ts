import { defineStore } from 'pinia'
import dayjs from 'dayjs'
import {
  baselineDefinitionApi,
  type BaselineDefinitionCreatePayload,
  type BaselineDefinitionResponse,
  type BaselineDefinitionUpdatePayload,
  type MetricDefinitionCreate,
  type MetricDefinitionUpdatePayload
} from '@/api/baselineDefinition'

export interface MetricItem {
  id: string
  name: string
  unit: string
  color: string
  sortOrder: number
  edcChannelId: string | null
}

export interface DefinitionItem {
  id: string
  definitionName: string
  description: string | null
  expectedDurationMinutes: number
  status: 'active' | 'disabled'
  metrics: MetricItem[]
  instanceCount: number
  createdAt: string
  updatedAt: string
}

function mapDefinition(item: BaselineDefinitionResponse): DefinitionItem {
  return {
    id: item.id,
    definitionName: item.definition_name,
    description: item.description,
    expectedDurationMinutes: item.expected_duration_minutes,
    status: item.status,
    metrics: item.metrics.map(m => ({
      id: m.id,
      name: m.name,
      unit: m.unit,
      color: m.color,
      sortOrder: m.sort_order,
      edcChannelId: m.edc_channel_id
    })),
    instanceCount: item.instance_count,
    createdAt: dayjs(item.created_at).format('YYYY-MM-DD HH:mm'),
    updatedAt: dayjs(item.updated_at).format('YYYY-MM-DD HH:mm')
  }
}

function mockDefinitions(): DefinitionItem[] {
  return [
    {
      id: 'def-001',
      definitionName: '标准熔炼基线',
      description: '中频炉标准熔炼过程，适用于常规铸铁生产',
      expectedDurationMinutes: 30,
      status: 'active',
      metrics: [
        { id: 'metric-001', name: '功率', unit: 'kW', color: '#409EFF', sortOrder: 1, edcChannelId: null },
        { id: 'metric-002', name: '电压', unit: 'V', color: '#67C23A', sortOrder: 2, edcChannelId: null },
        { id: 'metric-003', name: '炉温', unit: '°C', color: '#E6A23C', sortOrder: 3, edcChannelId: null }
      ],
      instanceCount: 0,
      createdAt: dayjs().format('YYYY-MM-DD HH:mm'),
      updatedAt: dayjs().format('YYYY-MM-DD HH:mm')
    },
    {
      id: 'def-002',
      definitionName: '高功率熔炼基线',
      description: '高强度钢生产专用，包含压力监控',
      expectedDurationMinutes: 45,
      status: 'active',
      metrics: [
        { id: 'metric-004', name: '功率', unit: 'kW', color: '#409EFF', sortOrder: 1, edcChannelId: null },
        { id: 'metric-005', name: '电压', unit: 'V', color: '#67C23A', sortOrder: 2, edcChannelId: null },
        { id: 'metric-006', name: '炉温', unit: '°C', color: '#E6A23C', sortOrder: 3, edcChannelId: null },
        { id: 'metric-007', name: '炉压', unit: 'MPa', color: '#F56C6C', sortOrder: 4, edcChannelId: null }
      ],
      instanceCount: 0,
      createdAt: dayjs().format('YYYY-MM-DD HH:mm'),
      updatedAt: dayjs().format('YYYY-MM-DD HH:mm')
    }
  ]
}

export const useBaselineDefinitionStore = defineStore('baselineDefinition', {
  state: () => ({
    list: [] as DefinitionItem[],
    current: null as DefinitionItem | null,
    loading: false,
    total: 0
  }),
  actions: {
    async fetchList(status?: string) {
      this.loading = true
      try {
        const data = await baselineDefinitionApi.list({ status })
        this.list = data.items.map(mapDefinition)
        this.total = data.total
      } catch (error) {
        console.warn('BaselineDefinition list fallback to mock.', error)
        this.list = mockDefinitions()
        this.total = this.list.length
      } finally {
        this.loading = false
      }
    },
    async fetchDetail(id: string) {
      this.loading = true
      try {
        const data = await baselineDefinitionApi.get(id)
        this.current = mapDefinition(data)
      } catch (error) {
        console.warn('BaselineDefinition detail fallback to mock.', error)
        this.current = mockDefinitions().find(d => d.id === id) || null
      } finally {
        this.loading = false
      }
    },
    async createDefinition(payload: BaselineDefinitionCreatePayload) {
      const data = await baselineDefinitionApi.create(payload)
      const item = mapDefinition(data)
      this.list.unshift(item)
      this.total += 1
      return item
    },
    async updateDefinition(id: string, payload: BaselineDefinitionUpdatePayload) {
      const data = await baselineDefinitionApi.update(id, payload)
      const updated = mapDefinition(data)
      const idx = this.list.findIndex(d => d.id === id)
      if (idx >= 0) this.list[idx] = updated
      if (this.current?.id === id) this.current = updated
      return updated
    },
    async deleteDefinition(id: string) {
      await baselineDefinitionApi.remove(id)
      this.list = this.list.filter(d => d.id !== id)
      this.total -= 1
    },
    async disableDefinition(id: string) {
      const data = await baselineDefinitionApi.disable(id)
      const updated = mapDefinition(data)
      const idx = this.list.findIndex(d => d.id === id)
      if (idx >= 0) this.list[idx] = updated
    },
    async enableDefinition(id: string) {
      const data = await baselineDefinitionApi.enable(id)
      const updated = mapDefinition(data)
      const idx = this.list.findIndex(d => d.id === id)
      if (idx >= 0) this.list[idx] = updated
    },
    async addMetric(definitionId: string, metric: MetricDefinitionCreate) {
      const data = await baselineDefinitionApi.addMetric(definitionId, metric)
      const updated = mapDefinition(data)
      const idx = this.list.findIndex(d => d.id === definitionId)
      if (idx >= 0) this.list[idx] = updated
      if (this.current?.id === definitionId) this.current = updated
      return updated
    },
    async updateMetric(
      definitionId: string,
      metricId: string,
      payload: MetricDefinitionUpdatePayload
    ) {
      const data = await baselineDefinitionApi.updateMetric(definitionId, metricId, payload)
      const updated = mapDefinition(data)
      const idx = this.list.findIndex(d => d.id === definitionId)
      if (idx >= 0) this.list[idx] = updated
      if (this.current?.id === definitionId) this.current = updated
      return updated
    },
    async removeMetric(definitionId: string, metricId: string) {
      const data = await baselineDefinitionApi.removeMetric(definitionId, metricId)
      const updated = mapDefinition(data)
      const idx = this.list.findIndex(d => d.id === definitionId)
      if (idx >= 0) this.list[idx] = updated
      if (this.current?.id === definitionId) this.current = updated
      return updated
    }
  }
})
