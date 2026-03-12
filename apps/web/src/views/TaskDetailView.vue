<script setup lang="ts">
import { computed, onMounted, reactive } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useTaskStore } from '@/stores/task'
import { taskApi } from '@/api/task'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()
const route = useRoute()
const taskStore = useTaskStore()

const taskId = computed(() => String(route.params.id || ''))
const task = computed(() => taskStore.current)

const form = reactive({
  causeAnalysis: '',
  improvement: '',
  prevention: ''
})

async function loadDetail() {
  if (!taskId.value) return
  await taskStore.fetchDetail(taskId.value)
  form.causeAnalysis = taskStore.current?.causeAnalysis || ''
  form.improvement = taskStore.current?.improvement || ''
  form.prevention = taskStore.current?.prevention || ''
}

async function handleSave() {
  if (!taskId.value) return
  await taskStore.saveDetail(taskId.value, {
    cause_analysis: form.causeAnalysis,
    improvement: form.improvement,
    prevention: form.prevention
  })
  ElMessage.success(t('common.save'))
}

async function handleComplete() {
  if (!taskId.value) return
  if (!form.causeAnalysis || !form.improvement || !form.prevention) {
    ElMessage.warning(t('task.completeRequired'))
    return
  }
  await taskStore.completeTask(taskId.value, {
    cause_analysis: form.causeAnalysis,
    improvement: form.improvement,
    prevention: form.prevention
  })
  ElMessage.success(t('task.statusCompleted'))
}

function handleExportPdf() {
  if (!taskId.value) return
  window.open(taskApi.exportPdfUrl(taskId.value), '_blank')
}

onMounted(() => {
  void loadDetail()
})
</script>

<template>
  <div
    class="flex flex-col gap-6"
    data-testid="task-detail-page"
  >
    <PageHeader
      :title="`${t('task.title')} - ${task?.taskNo || '--'}`"
      :subtitle="`ID: ${taskId}`"
    >
      <template #actions>
        <button
          class="flex items-center gap-2 bg-white border border-border-light text-slate-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors"
          @click="handleExportPdf"
        >
          <span class="material-symbols-outlined text-[18px]">picture_as_pdf</span>
          {{ t('task.exportPdf') }}
        </button>
      </template>
    </PageHeader>

    <div v-if="task" class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <!-- 任务概览 -->
      <div class="bg-white rounded-xl border border-border-light shadow-card p-5 space-y-4">
        <h3 class="text-sm font-bold text-slate-800 flex items-center gap-2 mb-4 pb-4 border-b border-border-light">
           <span class="material-symbols-outlined text-primary text-[20px]">info</span>
           任务基本信息
        </h3>
        <div class="flex justify-between items-center py-1">
          <span class="text-slate-500">{{ t('task.relatedHeat') }}</span>
          <span class="font-semibold text-primary cursor-pointer hover:underline">{{ task.heatNo }}</span>
        </div>
        <div class="flex justify-between items-center py-1 border-t border-slate-50 pt-3 mt-1">
          <span class="text-slate-500">{{ t('task.deviation') }}</span>
          <span class="font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded">{{ task.deviationPercent }}%</span>
        </div>
      </div>

      <!-- 任务表单 -->
      <div class="bg-white rounded-xl border border-border-light shadow-card p-5 md:col-span-2">
         <h3 class="text-sm font-bold text-slate-800 flex items-center gap-2 mb-4 pb-4 border-b border-border-light">
           <span class="material-symbols-outlined text-primary text-[20px]">assignment</span>
           纠偏处理记录
        </h3>
        <div class="space-y-6 max-w-4xl">
          <div class="flex flex-col gap-2">
            <label class="text-sm font-semibold text-slate-700">{{ t('task.causeAnalysis') }}</label>
            <textarea
              v-model="form.causeAnalysis"
              rows="4"
              data-testid="task-cause-analysis"
              class="w-full px-3 py-2 border border-border-light rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary resize-y text-sm bg-slate-50"
              placeholder="请输入问题原因分析..."
            />
          </div>
          <div class="flex flex-col gap-2">
            <label class="text-sm font-semibold text-slate-700">{{ t('task.improvement') }}</label>
            <textarea
              v-model="form.improvement"
              rows="4"
              data-testid="task-improvement"
              class="w-full px-3 py-2 border border-border-light rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary resize-y text-sm bg-slate-50"
              placeholder="请输入改善措施建议..."
            />
          </div>
          <div class="flex flex-col gap-2">
            <label class="text-sm font-semibold text-slate-700">{{ t('task.prevention') }}</label>
            <textarea
              v-model="form.prevention"
              rows="4"
              data-testid="task-prevention"
              class="w-full px-3 py-2 border border-border-light rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary resize-y text-sm bg-slate-50"
              placeholder="请输入预防再发措施..."
            />
          </div>
        </div>

        <div class="flex justify-end gap-3 mt-8 pt-6 border-t border-border-light">
          <button
            data-testid="task-save-button"
            class="px-5 py-2.5 bg-white border border-border-light text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors"
            @click="handleSave"
          >
            {{ t('common.save') }}
          </button>
          <button
            data-testid="task-submit-button"
            class="px-5 py-2.5 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-dark transition-colors flex items-center gap-2 shadow-sm"
            @click="handleComplete"
          >
            <span class="material-symbols-outlined text-[18px]">verified</span>
            {{ t('common.submit') }}
          </button>
        </div>
      </div>
    </div>
    
    <!-- 空状态 -->
    <div v-else class="py-16 flex flex-col items-center justify-center bg-white rounded-xl border border-border-light shadow-card">
      <span class="material-symbols-outlined text-slate-300 text-5xl">pending</span>
      <p class="text-sm text-slate-400 mt-3">{{ t('common.loading') }}</p>
    </div>
  </div>
</template>
