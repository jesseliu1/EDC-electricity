<script setup lang="ts">
import { computed, onMounted, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElButton, ElCard, ElForm, ElFormItem, ElInput, ElMessage } from 'element-plus'
import { useTaskStore } from '@/stores/task'
import { taskApi } from '@/api/task'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
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

function handleBack() {
  router.push('/tasks')
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
  <div class="space-y-6">
    <div class="flex items-center justify-between gap-4 flex-wrap">
      <h1 class="text-2xl font-bold text-gray-900">
        {{ t('task.title') }} - {{ task?.taskNo || '--' }}
      </h1>
      <div class="flex items-center gap-2">
        <el-button @click="handleBack">
          {{ t('common.back') }}
        </el-button>
        <el-button @click="handleExportPdf">
          {{ t('task.exportPdf') }}
        </el-button>
      </div>
    </div>

    <el-card v-if="task">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div class="text-sm text-gray-600">
          {{ t('task.relatedHeat') }}: {{ task.heatNo }}
        </div>
        <div class="text-sm text-gray-600">
          {{ t('task.deviation') }}: {{ task.deviationPercent }}%
        </div>
      </div>
    </el-card>

    <el-card>
      <el-form label-position="top">
        <el-form-item :label="t('task.causeAnalysis')">
          <el-input
            v-model="form.causeAnalysis"
            type="textarea"
            :rows="4"
          />
        </el-form-item>
        <el-form-item :label="t('task.improvement')">
          <el-input
            v-model="form.improvement"
            type="textarea"
            :rows="4"
          />
        </el-form-item>
        <el-form-item :label="t('task.prevention')">
          <el-input
            v-model="form.prevention"
            type="textarea"
            :rows="4"
          />
        </el-form-item>
      </el-form>

      <div class="flex justify-end gap-2">
        <el-button @click="handleSave">
          {{ t('common.save') }}
        </el-button>
        <el-button
          type="primary"
          @click="handleComplete"
        >
          {{ t('common.submit') }}
        </el-button>
      </div>
    </el-card>
  </div>
</template>
