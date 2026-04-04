import { defineStore } from 'pinia'
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
  createdAt: number
  updatedAt: number
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
    createdAt: item.created_at,
    updatedAt: item.updated_at
  }
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
        console.error('BaselineDefinition list request failed.', error)
        this.list = []
        this.total = 0
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
        console.error('BaselineDefinition detail request failed.', error)
        this.current = null
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
