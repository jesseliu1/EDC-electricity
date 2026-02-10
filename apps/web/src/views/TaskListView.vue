<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElCard, ElPagination, ElRadioButton, ElRadioGroup, ElTag, ElButton } from 'element-plus'
import { useTaskStore } from '@/stores/task'
import type { TaskStatus } from '@/api/task'

const { t } = useI18n()
const router = useRouter()
const taskStore = useTaskStore()

function statusType(status: TaskStatus) {
  if (status === 'completed') return 'success'
  if (status === 'in_progress') return 'warning'
  if (status === 'cancelled') return 'info'
  return 'danger'
}

function statusText(status: TaskStatus) {
  if (status === 'pending') return t('task.statusPending')
  if (status === 'in_progress') return t('task.statusInProgress')
  if (status === 'completed') return t('task.statusCompleted')
  return t('task.statusCancelled')
}

function handleStatusChange(value: string | number | boolean) {
  void taskStore.setStatus(value as 'all' | TaskStatus)
}

function handleViewDetail(id: string) {
  router.push(`/tasks/${id}`)
}

onMounted(() => {
  void taskStore.fetchList()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between gap-4 flex-wrap">
      <h1 class="text-2xl font-bold text-gray-900">
        {{ t('task.title') }}
      </h1>
      <div class="text-sm text-gray-500">
        {{ t('heat.totalCount') }}: {{ taskStore.total }}
      </div>
    </div>

    <el-card>
      <div class="flex items-center justify-between gap-4 flex-wrap">
        <div class="text-sm text-gray-500">
          {{ t('task.status') }}
        </div>
        <el-radio-group
          :model-value="taskStore.statusFilter"
          @change="handleStatusChange"
        >
          <el-radio-button label="all">
            {{ t('common.viewAll') }}
          </el-radio-button>
          <el-radio-button label="pending">
            {{ t('task.statusPending') }}
          </el-radio-button>
          <el-radio-button label="in_progress">
            {{ t('task.statusInProgress') }}
          </el-radio-button>
          <el-radio-button label="completed">
            {{ t('task.statusCompleted') }}
          </el-radio-button>
          <el-radio-button label="cancelled">
            {{ t('task.statusCancelled') }}
          </el-radio-button>
        </el-radio-group>
      </div>
    </el-card>

    <el-card>
      <div
        v-if="taskStore.list.length > 0"
        class="space-y-3"
      >
        <div
          v-for="item in taskStore.list"
          :key="item.id"
          class="rounded-lg border border-gray-200 p-4 hover:border-primary transition"
        >
          <div class="flex items-center justify-between gap-4 flex-wrap">
            <div class="space-y-1">
              <div class="text-base font-semibold text-gray-900">
                {{ item.taskNo }}
              </div>
              <div class="text-sm text-gray-500">
                Heat: {{ item.heatId }}
              </div>
            </div>
            <div class="flex items-center gap-4 flex-wrap">
              <div class="text-sm text-gray-600">
                {{ t('task.deviation') }}: {{ item.deviationPercent }}%
              </div>
              <el-tag :type="statusType(item.status)">
                {{ statusText(item.status) }}
              </el-tag>
              <el-button
                type="primary"
                link
                @click="handleViewDetail(item.id)"
              >
                {{ t('inbox.viewDetail') }}
              </el-button>
            </div>
          </div>
        </div>

        <div class="pt-2 flex justify-end">
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

      <el-empty
        v-else
        :description="t('common.noData')"
      />
    </el-card>
  </div>
</template>
