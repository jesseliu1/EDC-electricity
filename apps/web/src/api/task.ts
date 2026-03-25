import { client } from './client'

export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'cancelled'

export interface TaskItemResponse {
  id: string
  task_no: string
  heat_id: string
  deviation_percent: number | null
  cause_analysis: string | null
  improvement: string | null
  prevention: string | null
  status: TaskStatus
  created_at: string
  updated_at: string
  completed_at: string | null
}

export interface TaskListResponse {
  items: TaskItemResponse[]
  total: number
  page: number
  page_size: number
}

export interface TaskDetailResponse extends TaskItemResponse {
  deviation_snapshot: Record<string, unknown>
  heat_no: string
}

export interface TaskUpdatePayload {
  cause_analysis?: string
  improvement?: string
  prevention?: string
}

export interface TaskCompletePayload {
  cause_analysis: string
  improvement: string
  prevention: string
}

export const taskApi = {
  list: (params: { status?: TaskStatus; page?: number; page_size?: number }) =>
    client.get<TaskListResponse>('/tasks', { params }),
  get: (id: string) => client.get<TaskDetailResponse>(`/tasks/${id}`),
  create: (payload: { heat_id: string }) => client.post<TaskItemResponse>('/tasks', payload),
  update: (id: string, payload: TaskUpdatePayload) =>
    client.patch<TaskItemResponse>(`/tasks/${id}`, payload),
  complete: (id: string, payload: TaskCompletePayload) =>
    client.post<TaskItemResponse>(`/tasks/${id}/complete`, payload),
  cancel: (id: string) => client.post<TaskItemResponse>(`/tasks/${id}/cancel`),
  exportPdfUrl: (id: string) => `${import.meta.env.VITE_API_BASE_URL || '/api'}/tasks/${id}/pdf`
}
