<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElPagination } from 'element-plus'
import PageHeader from '@/components/common/PageHeader.vue'
import SystemReadinessBanner from '@/components/common/SystemReadinessBanner.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import { useTaskStore } from '@/stores/task'
import type { TaskStatus } from '@/api/task'

const { t } = useI18n()
const router = useRouter()
const taskStore = useTaskStore()

const statusFilters: { key: 'all' | TaskStatus; label: string; count?: number }[] = [
  { key: 'all', label: '全部' },
  { key: 'pending', label: '新建' },
  { key: 'in_progress', label: '进行中' },
  { key: 'completed', label: '已完成' },
  { key: 'cancelled', label: '已驳回' },
]

function statusBadgeType(status: TaskStatus) {
  if (status === 'completed') return 'success' as const
  if (status === 'in_progress') return 'warning' as const
  if (status === 'cancelled') return 'info' as const
  return 'danger' as const
}

function statusText(status: TaskStatus) {
  if (status === 'pending') return t('task.statusPending')
  if (status === 'in_progress') return t('task.statusInProgress')
  if (status === 'completed') return t('task.statusCompleted')
  return t('task.statusCancelled')
}

function handleStatusChange(value: 'all' | TaskStatus) {
  void taskStore.setStatus(value)
}

function handleViewDetail(id: string) {
  router.push(`/tasks/${id}`)
}

onMounted(() => {
  void taskStore.fetchList()
})
</script>

<template>
  <div
    class="flex flex-col gap-6"
    data-testid="task-list-page"
  >
    <SystemReadinessBanner
      section="tasks"
      test-id="task-list-runtime-banner"
    />

    <!-- 页面头部 -->
    <PageHeader
      :title="t('task.title')"
      subtitle="Action Orders"
      description="管理由 AI 生成或人工创建的纠偏任务单，跟踪执行进度。"
    >
      <template #actions>
        <button
          class="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary-dark transition-colors"
        >
          <span class="material-symbols-outlined text-[18px]">add</span>
          新建纠偏任务
        </button>
      </template>
    </PageHeader>

    <!-- 状态 Tab 栏 -->
    <div class="flex items-center gap-6 border-b border-border-light">
      <button
        v-for="f in statusFilters"
        :key="f.key"
        :class="[
          'pb-3 text-sm font-medium transition-colors relative',
          taskStore.statusFilter === f.key
            ? 'text-primary'
            : 'text-slate-500 hover:text-slate-700',
        ]"
        @click="handleStatusChange(f.key)"
      >
        {{ f.label }} ({{ f.key === 'all' ? taskStore.total : '...' }})
        <div
          v-if="taskStore.statusFilter === f.key"
          class="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-t-full"
        />
      </button>
      <div class="flex-1" />
      <!-- 搜索 -->
      <div
        class="flex items-center bg-slate-100 rounded-lg px-3 py-1.5 w-56 mb-2 border border-transparent focus-within:border-primary/30 transition-all"
      >
        <span class="material-symbols-outlined text-slate-400 text-[18px]">search</span>
        <input
          type="text"
          class="bg-transparent border-none focus:ring-0 focus:outline-none text-sm text-slate-700 w-full placeholder:text-slate-400 ml-2 p-0"
          placeholder="搜索订单号/任务描述..."
        >
      </div>
    </div>

    <!-- 任务列表 -->
    <div class="bg-white rounded-xl border border-border-light shadow-card overflow-hidden">
      <div v-if="taskStore.list.length > 0">
        <div
          v-for="item in taskStore.list"
          :key="item.id"
          :data-testid="`task-row-${item.id}`"
          class="border-b border-border-light last:border-0 p-5 hover:bg-slate-50 transition-colors cursor-pointer group flex items-center justify-between gap-4"
          @click="handleViewDetail(item.id)"
        >
          <!-- 左侧: 彩色边框 + 任务信息 -->
          <div class="flex items-start gap-4">
            <div
              :class="[
                'w-1 h-12 rounded-full shrink-0',
                item.status === 'pending' ? 'bg-red-400' :
                item.status === 'in_progress' ? 'bg-primary' :
                item.status === 'completed' ? 'bg-green-400' :
                'bg-slate-300'
              ]"
            />
            <div>
              <div class="flex items-center gap-3 mb-1">
                <span class="text-xs text-red-500 font-mono font-bold">{{ item.taskNo }}</span>
                <span class="text-xs text-slate-400">{{ item.heatId ? `Heat: ${item.heatId}` : '' }}</span>
              </div>
              <p class="text-sm font-semibold text-slate-800">
                {{ item.taskNo }} : 纠偏任务
              </p>
              <p class="text-xs text-slate-400 mt-1">
                偏差: {{ item.deviationPercent }}%
              </p>
            </div>
          </div>

          <!-- 右侧: 状态 + 箭头 -->
          <div class="flex items-center gap-4 shrink-0">
            <StatusBadge :type="statusBadgeType(item.status)">
              {{ statusText(item.status) }}
            </StatusBadge>
            <span class="material-symbols-outlined text-slate-400 group-hover:text-primary transition-colors text-[20px]">chevron_right</span>
          </div>
        </div>

        <!-- 分页 -->
        <div class="px-6 py-4 border-t border-border-light flex justify-end">
          <el-pagination
            background
            layout="total, sizes, prev, pager, next"
            :current-page="taskStore.page"
            :page-size="taskStore.pageSize"
            :page-sizes="[10, 20, 50]"
            :total="taskStore.total"
            @update:current-page="taskStore.setPage"
            @update:page-size="taskStore.setPageSize"
          />
        </div>
      </div>

      <!-- 空状态 -->
      <div
        v-else
        class="py-16 flex flex-col items-center justify-center"
      >
        <span class="material-symbols-outlined text-slate-300 text-5xl">assignment</span>
        <p class="text-sm text-slate-400 mt-3">
          {{ t('common.noData') }}
        </p>
      </div>
    </div>
  </div>
</template>
