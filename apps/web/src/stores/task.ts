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

function resolveDetailErrorMessage(error: unknown): string {
  if (!error || typeof error !== 'object') {
    return '任务详情加载失败'
  }

  const response = (error as { response?: { data?: { message?: string; detail?: string } } }).response
  const message = response?.data?.message
  if (typeof message === 'string' && message.trim()) {
    return message
  }

  const detail = response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }

  return '任务详情加载失败'
}

export interface TaskItem {
  id: string
  taskNo: string
  heatId: string
  deviationPercent: number | null
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

export type TaskFilterKey = 'all' | TaskStatus

export interface TaskStatusCounts {
  all: number | null
  pending: number | null
  in_progress: number | null
  completed: number | null
  cancelled: number | null
}

function createEmptyStatusCounts(): TaskStatusCounts {
  return {
    all: null,
    pending: null,
    in_progress: null,
    completed: null,
    cancelled: null
  }
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

export const useTaskStore = defineStore('task', {
  state: () => ({
    list: [] as TaskItem[],
    current: null as TaskDetail | null,
    loading: false,
    detailLoading: false,
    detailLoaded: false,
    detailError: null as string | null,
    detailRequestToken: 0,
    page: 1,
    pageSize: 10,
    total: 0,
    statusFilter: 'all' as TaskFilterKey,
    statusCounts: createEmptyStatusCounts() as TaskStatusCounts
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
        this.statusCounts[this.statusFilter] = data.total
      } catch (error) {
        console.error('Task list request failed.', error)
        this.list = []
        this.total = 0
        if (this.statusFilter === 'all') {
          this.statusCounts.all = 0
        }
      } finally {
        this.loading = false
      }
    },
    async fetchStatusCounts() {
      const previousCounts = { ...this.statusCounts }
      try {
        const [pending, inProgress, completed, cancelled] = await Promise.all([
          taskApi.list({ status: 'pending', page: 1, page_size: 1 }),
          taskApi.list({ status: 'in_progress', page: 1, page_size: 1 }),
          taskApi.list({ status: 'completed', page: 1, page_size: 1 }),
          taskApi.list({ status: 'cancelled', page: 1, page_size: 1 })
        ])
        this.statusCounts = {
          all: pending.total + inProgress.total + completed.total + cancelled.total,
          pending: pending.total,
          in_progress: inProgress.total,
          completed: completed.total,
          cancelled: cancelled.total
        }
      } catch (error) {
        console.error('Task status count request failed.', error)
        this.statusCounts = {
          ...previousCounts,
          [this.statusFilter]: this.total
        }
      }
    },
    async setStatus(status: 'all' | TaskStatus) {
      this.statusFilter = status
      this.page = 1
      await Promise.all([this.fetchList(), this.fetchStatusCounts()])
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
    clearDetail() {
      this.detailRequestToken += 1
      this.current = null
      this.detailLoading = false
      this.detailLoaded = false
      this.detailError = null
    },
    async fetchDetail(id: string) {
      const requestToken = this.detailRequestToken + 1
      this.detailRequestToken = requestToken
      this.current = null
      this.detailError = null
      this.detailLoaded = false
      this.detailLoading = true
      try {
        const data = await taskApi.get(id)
        if (requestToken !== this.detailRequestToken) {
          return
        }
        this.current = mapTaskDetail(data)
        this.detailLoaded = true
      } catch (error) {
        if (requestToken !== this.detailRequestToken) {
          return
        }
        console.error('Task detail request failed.', error)
        this.current = null
        this.detailError = resolveDetailErrorMessage(error)
      } finally {
        if (requestToken === this.detailRequestToken) {
          this.detailLoading = false
        }
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
