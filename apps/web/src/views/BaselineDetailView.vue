<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  ElButton,
  ElCard,
  ElDatePicker,
  ElDialog,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElTag,
  ElTimeline,
  ElTimelineItem
} from 'element-plus'
import { Edit, Plus, VideoPause, VideoPlay } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import type { EChartsOption } from 'echarts'
import dayjs from 'dayjs'
import { useBaselineStore } from '@/stores/baseline'

use([CanvasRenderer, LineChart, GridComponent, LegendComponent, TooltipComponent])

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const baselineStore = useBaselineStore()
const editVisible = ref(false)

const editForm = reactive({
  name: '',
  description: '',
  tolerancePercent: 15,
  selectedStartTime: null as Date | null,
  selectedEndTime: null as Date | null
})

const baselineId = computed(() => String(route.params.id || ''))
const baseline = computed(() => baselineStore.current)

const statusType = computed(() => {
  if (!baseline.value) return 'info'
  switch (baseline.value.status) {
    case 'published':
      return 'success'
    case 'draft':
      return 'info'
    case 'disabled':
      return 'danger'
    default:
      return 'info'
  }
})

const statusLabel = computed(() => {
  if (!baseline.value) return ''
  if (baseline.value.status === 'published') return t('baseline.statusPublished')
  if (baseline.value.status === 'draft') return t('baseline.statusDraft')
  return t('baseline.statusDisabled')
})

const curveOption = computed<EChartsOption>(() => {
  const current = baseline.value
  if (!current) return {}
  const firstCurve = current.curvesData[0]?.points || current.powerCurve
  const labels = firstCurve.map(point => dayjs(point.timestamp).format('HH:mm'))
  const series =
    current.curvesData.length > 0
      ? current.curvesData.map(item => ({
          name: `${item.metric_name} (${item.unit})`,
          type: 'line' as const,
          smooth: true,
          showSymbol: false,
          lineStyle: { color: item.color, width: 2 },
          data: item.points.map(point => point.value)
        }))
      : [
          {
            name: t('dashboard.chart.power'),
            type: 'line' as const,
            smooth: true,
            showSymbol: false,
            lineStyle: { color: '#409EFF', width: 2 },
            data: current.powerCurve.map(point => point.value)
          },
          {
            name: t('dashboard.chart.voltage'),
            type: 'line' as const,
            smooth: true,
            showSymbol: false,
            lineStyle: { color: '#67C23A', width: 2, type: 'dashed' as const },
            data: current.voltageCurve.map(point => point.value)
          }
        ]
  return {
    grid: { left: 45, right: 20, top: 30, bottom: 30 },
    tooltip: { trigger: 'axis' },
    legend: {
      data: series.map(item => item.name),
      top: 0
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: labels
    },
    yAxis: { type: 'value' },
    series
  }
})

function handleBack() {
  router.push('/baselines')
}

function handleEdit() {
  if (!baseline.value) return
  if (baseline.value.status !== 'draft') {
    ElMessage.warning(t('baseline.detail.editDraftOnly'))
    return
  }
  editForm.name = baseline.value.name
  editForm.description = baseline.value.description || ''
  editForm.tolerancePercent = baseline.value.tolerancePercent
  editForm.selectedStartTime = baseline.value.selectedStartTime
    ? dayjs(baseline.value.selectedStartTime).toDate()
    : null
  editForm.selectedEndTime = baseline.value.selectedEndTime
    ? dayjs(baseline.value.selectedEndTime).toDate()
    : null
  editVisible.value = true
}

async function handleSaveEdit() {
  if (!baseline.value) return
  if (!editForm.name.trim()) {
    ElMessage.warning(t('baseline.wizard.nameRequired'))
    return
  }
  const ok = await baselineStore.updateBaseline(baseline.value.id, {
    name: editForm.name.trim(),
    description: editForm.description.trim() || undefined,
    tolerance_percent: editForm.tolerancePercent,
    selected_start_time: editForm.selectedStartTime
      ? dayjs(editForm.selectedStartTime).toISOString()
      : undefined,
    selected_end_time: editForm.selectedEndTime ? dayjs(editForm.selectedEndTime).toISOString() : undefined
  })
  if (!ok) {
    ElMessage.error(t('common.error'))
    return
  }
  editVisible.value = false
  await baselineStore.fetchDetail(baseline.value.id)
  ElMessage.success(t('common.success'))
}

async function handleToggleStatus() {
  if (!baseline.value) return
  if (baseline.value.status === 'published') {
    await baselineStore.disableBaseline(baseline.value.id)
    ElMessage.success(t('baseline.disableSuccess'))
  } else if (baseline.value.status === 'draft') {
    await baselineStore.publishBaseline(baseline.value.id)
    ElMessage.success(t('baseline.publishSuccess'))
  }
  await baselineStore.fetchDetail(baseline.value.id)
}

function handleCreateVersion() {
  ElMessage.info(t('baseline.detail.newVersionHint'))
}

onMounted(async () => {
  if (!baselineId.value) return
  await Promise.all([
    baselineStore.fetchDetail(baselineId.value),
    baselineStore.fetchVersionHistory(baselineId.value)
  ])
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between gap-4 flex-wrap">
      <div class="space-y-2">
        <div class="text-sm text-gray-500">
          {{ t('baseline.detail.title') }}
        </div>
        <div class="flex items-center gap-3">
          <h1 class="text-2xl font-bold text-gray-900">
            {{ baseline?.name || '--' }}
          </h1>
          <el-tag
            :type="statusType"
            effect="light"
          >
            {{ statusLabel }}
          </el-tag>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <el-button @click="handleBack">
          {{ t('common.back') }}
        </el-button>
        <el-button
          :icon="Edit"
          @click="handleEdit"
        >
          {{ t('common.edit') }}
        </el-button>
        <el-button
          v-if="baseline?.status === 'published' || baseline?.status === 'draft'"
          :icon="baseline?.status === 'published' ? VideoPause : VideoPlay"
          @click="handleToggleStatus"
        >
          {{ baseline?.status === 'published' ? t('common.disable') : t('baseline.publish') }}
        </el-button>
        <el-button
          type="primary"
          :icon="Plus"
          @click="handleCreateVersion"
        >
          {{ t('baseline.detail.newVersion') }}
        </el-button>
      </div>
    </div>

    <div
      v-if="baseline"
      class="grid grid-cols-1 gap-4 xl:grid-cols-3"
    >
      <el-card class="xl:col-span-2">
        <template #header>
          <span>{{ t('baseline.detail.curveTitle') }}</span>
        </template>
        <v-chart
          :option="curveOption"
          autoresize
          class="h-80"
        />
      </el-card>

      <el-card>
        <template #header>
          <span>{{ t('baseline.detail.infoTitle') }}</span>
        </template>
        <div class="space-y-3 text-sm text-gray-700">
          <div>
            <span class="text-gray-500">{{ t('baseline.definitionName') }}:</span>
            <span class="ml-2 font-medium">{{ baseline.definitionName }}</span>
          </div>
          <div>
            <span class="text-gray-500">{{ t('baseline.version') }}:</span>
            <span class="ml-2 font-medium">v{{ baseline.version }}</span>
          </div>
          <div>
            <span class="text-gray-500">{{ t('baseline.tolerance') }}:</span>
            <span class="ml-2 font-medium">{{ baseline.tolerancePercent }}%</span>
          </div>
          <div>
            <span class="text-gray-500">{{ t('baseline.createTime') }}:</span>
            <span class="ml-2 font-medium">{{ dayjs(baseline.createdAt).format('YYYY-MM-DD HH:mm') }}</span>
          </div>
          <div>
            <span class="text-gray-500">{{ t('baseline.publishTime') }}:</span>
            <span class="ml-2 font-medium">{{ baseline.publishedAt ? dayjs(baseline.publishedAt).format('YYYY-MM-DD HH:mm') : '--' }}</span>
          </div>
          <div>
            <span class="text-gray-500">{{ t('baseline.detail.sourceHeat') }}:</span>
            <span class="ml-2 font-medium">{{ baseline.sourceHeatId }}</span>
          </div>
          <div>
            <span class="text-gray-500">{{ t('baseline.wizard.pointRange') }}:</span>
            <span class="ml-2 font-medium">
              {{ baseline.selectedStartTime ? dayjs(baseline.selectedStartTime).format('YYYY-MM-DD HH:mm:ss') : '--' }}
              ~
              {{ baseline.selectedEndTime ? dayjs(baseline.selectedEndTime).format('YYYY-MM-DD HH:mm:ss') : '--' }}
            </span>
          </div>
          <div>
            <span class="text-gray-500">{{ t('baseline.detail.temperature') }}:</span>
            <span class="ml-2 font-medium">{{ baseline.temperature ?? '--' }}</span>
          </div>
          <div class="pt-2 border-t border-gray-100">
            <div class="text-gray-500 mb-1">
              {{ t('baseline.detail.description') }}
            </div>
            <p>{{ baseline.description || t('common.noDescription') }}</p>
          </div>
        </div>
      </el-card>
    </div>

    <el-card>
      <template #header>
        <span>{{ t('baseline.detail.versionHistory') }}</span>
      </template>
      <el-empty
        v-if="baselineStore.versionHistory.length === 0"
        :description="t('common.noData')"
      />
      <el-timeline v-else>
        <el-timeline-item
          v-for="version in baselineStore.versionHistory"
          :key="version.id"
          :timestamp="dayjs(version.createdAt).format('YYYY-MM-DD HH:mm')"
          placement="top"
        >
          <div class="flex items-center justify-between">
            <div>
              <div class="font-medium text-gray-800">
                {{ version.name }}
              </div>
              <div class="text-xs text-gray-500">
                v{{ version.version }} · {{ version.tolerancePercent }}%
              </div>
            </div>
            <el-tag
              size="small"
              :type="version.status === 'published' ? 'success' : version.status === 'draft' ? 'info' : 'danger'"
            >
              {{ version.status === 'published' ? t('baseline.statusPublished') : version.status === 'draft' ? t('baseline.statusDraft') : t('baseline.statusDisabled') }}
            </el-tag>
          </div>
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <ElDialog v-model="editVisible" :title="t('common.edit')" width="620px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item :label="t('baseline.name')">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item :label="t('baseline.wizard.description')">
          <el-input v-model="editForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item :label="t('baseline.tolerance')">
          <el-input-number v-model="editForm.tolerancePercent" :min="0" :max="100" :step="0.5" />
        </el-form-item>
        <el-form-item :label="t('baseline.wizard.rangeStart')">
          <el-date-picker
            v-model="editForm.selectedStartTime"
            type="datetime"
            format="YYYY-MM-DD HH:mm:ss"
            class="w-full"
          />
        </el-form-item>
        <el-form-item :label="t('baseline.wizard.rangeEnd')">
          <el-date-picker
            v-model="editForm.selectedEndTime"
            type="datetime"
            format="YYYY-MM-DD HH:mm:ss"
            class="w-full"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleSaveEdit">{{ t('common.save') }}</el-button>
      </template>
    </ElDialog>
  </div>
</template>
