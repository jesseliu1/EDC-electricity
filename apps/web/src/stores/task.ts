import { defineStore } from 'pinia'
import dayjs from 'dayjs'
import { taskApi } from '@/api/task'
import type {
  TaskCompletePayload,
  TaskDetailResponse,
  TaskItemResponse,
  TaskStatus,
  TaskUpdatePayload
} from '@/api/task'

export interface TaskItem {
  id: string
  taskNo: string
  heatId: string
  deviationPercent: number
  status: TaskStatus
  createdAt: string
  updatedAt: string
  completedAt: string | null
}

export interface TaskDetail extends TaskItem {
  heatNo: string
  causeAnalysis: string
  improvement: string
  prevention: string
  deviationSnapshot: Record<string, unknown>
}

function mapTask(item: TaskItemResponse): TaskItem {
  return {
    id: item.id,
    taskNo: item.task_no,
    heatId: item.heat_id,
    deviationPercent: item.deviation_percent,
    status: item.status,
    createdAt: dayjs(item.created_at).format('YYYY-MM-DD HH:mm'),
    updatedAt: dayjs(item.updated_at).format('YYYY-MM-DD HH:mm'),
    completedAt: item.completed_at ? dayjs(item.completed_at).format('YYYY-MM-DD HH:mm') : null
  }
}

function mapTaskDetail(item: TaskDetailResponse): TaskDetail {
  return {
    ...mapTask(item),
    heatNo: item.heat_no,
    causeAnalysis: item.cause_analysis || '',
    improvement: item.improvement || '',
    prevention: item.prevention || '',
    deviationSnapshot: item.deviation_snapshot
  }
}

function mockTaskList(status: 'all' | TaskStatus, page: number, pageSize: number): { items: TaskItem[]; total: number } {
  const statuses: TaskStatus[] = ['pending', 'in_progress', 'completed', 'cancelled']
  const all = Array.from({ length: 36 }).map((_, idx) => {
    const taskStatus = statuses[idx % statuses.length]
    const now = dayjs().subtract(idx, 'day')
    return {
      id: `mock-task-${idx + 1}`,
      taskNo: `T${dayjs().format('YYYYMMDD')}-${String(idx + 1).padStart(3, '0')}`,
      heatId: `heat-${String(idx + 1).padStart(3, '0')}`,
      deviationPercent: Number((10 + (idx % 8) * 1.7).toFixed(2)),
      status: taskStatus,
      createdAt: now.format('YYYY-MM-DD HH:mm'),
      updatedAt: now.add(2, 'hour').format('YYYY-MM-DD HH:mm'),
      completedAt: taskStatus === 'completed' ? now.add(6, 'hour').format('YYYY-MM-DD HH:mm') : null
    } as TaskItem
  })
  const filtered = status === 'all' ? all : all.filter(item => item.status === status)
  const start = (page - 1) * pageSize
  return { items: filtered.slice(start, start + pageSize), total: filtered.length }
}

function mockTaskDetail(id: string): TaskDetail {
  return {
    id,
    taskNo: `T${dayjs().format('YYYYMMDD')}-001`,
    heatId: 'heat-001',
    heatNo: `H${dayjs().format('YYYYMMDD')}-001`,
    deviationPercent: 18.2,
    status: 'in_progress',
    createdAt: dayjs().subtract(1, 'day').format('YYYY-MM-DD HH:mm'),
    updatedAt: dayjs().format('YYYY-MM-DD HH:mm'),
    completedAt: null,
    causeAnalysis: '温度波动导致功率偏差持续上升',
    improvement: '调整加热曲线并稳定投料节奏',
    prevention: '增加关键段采样与班组复核',
    deviationSnapshot: {
      max_deviation: 21.5,
      avg_deviation: 8.6,
      deviation_ranges: [
        { start: 20000, end: 35000, deviation: 18.5 },
        { start: 60000, end: 76000, deviation: 21.5 }
      ]
    }
  }
}

export const useTaskStore = defineStore('task', {
  state: () => ({
    list: [] as TaskItem[],
    current: null as TaskDetail | null,
    loading: false,
    page: 1,
    pageSize: 10,
    total: 0,
    statusFilter: 'all' as 'all' | TaskStatus
  }),
  actions: {
    async fetchList() {
      this.loading = true
      try {
        const data = await taskApi.list({
          status: this.statusFilter === 'all' ? undefined : this.statusFilter,
          page: this.page,
          page_size: this.pageSize
        })
        this.list = data.items.map(mapTask)
        this.total = data.total
      } catch (error) {
        console.warn('Task list fallback to mock.', error)
        const mock = mockTaskList(this.statusFilter, this.page, this.pageSize)
        this.list = mock.items
        this.total = mock.total
      } finally {
        this.loading = false
      }
    },
    async setStatus(status: 'all' | TaskStatus) {
      this.statusFilter = status
      this.page = 1
      await this.fetchList()
    },
    async setPage(page: number) {
      this.page = page
      await this.fetchList()
    },
    async setPageSize(pageSize: number) {
      this.pageSize = pageSize
      this.page = 1
      await this.fetchList()
    },
    async fetchDetail(id: string) {
      this.loading = true
      try {
        const data = await taskApi.get(id)
        this.current = mapTaskDetail(data)
      } catch (error) {
        console.warn('Task detail fallback to mock.', error)
        this.current = mockTaskDetail(id)
      } finally {
        this.loading = false
      }
    },
    async saveDetail(id: string, payload: TaskUpdatePayload) {
      await taskApi.update(id, payload)
      await this.fetchDetail(id)
    },
    async completeTask(id: string, payload: TaskCompletePayload) {
      await taskApi.complete(id, payload)
      await this.fetchDetail(id)
    }
  }
})
