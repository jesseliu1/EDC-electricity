<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  ElDatePicker,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElTimeline,
  ElTimelineItem,
} from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import type { EChartsOption } from 'echarts'
import { useBaselineStore } from '@/stores/baseline'
import PageHeader from '@/components/common/PageHeader.vue'
import SystemReadinessBanner from '@/components/common/SystemReadinessBanner.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import {
  formatTimestamp,
  pickerDateToPlantTimestamp,
  timestampToPlantPickerDate,
} from '@/utils/time'

use([CanvasRenderer, LineChart, GridComponent, LegendComponent, TooltipComponent])

type ChartRuntimeSeriesSummary = {
  name: string
  type: string
  pointCount: number
}

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
  selectedEndTime: null as Date | null,
})

const baselineId = computed(() => String(route.params.id || ''))
const baseline = computed(() => baselineStore.current)
const isDefaultBaseline = computed(() => baselineStore.activeBaselineId === baseline.value?.id)
const showtimeMode = computed(() => {
  const raw = route.query.showtime
  const values = Array.isArray(raw) ? raw : [raw]
  return values.some((value) =>
    ['1', 'true', 'yes', 'on'].includes(
      String(value || '')
        .trim()
        .toLowerCase()
    )
  )
})
const isDemoCurveSource = computed(() => baseline.value?.curveSource === 'demo_curve')

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
  const labels = firstCurve.map((point) => formatTimestamp(point.timestamp, 'HH:mm'))
  const series =
    current.curvesData.length > 0
      ? current.curvesData.map((item) => ({
          name: `${item.metric_name} (${item.unit})`,
          type: 'line' as const,
          smooth: true,
          showSymbol: false,
          lineStyle: { color: item.color, width: 2 },
          data: item.points.map((point) => point.value),
        }))
      : [
          {
            name: t('dashboard.chart.power'),
            type: 'line' as const,
            smooth: true,
            showSymbol: false,
            lineStyle: { color: '#1152d4', width: 2 },
            data: current.powerCurve.map((point) => point.value),
          },
          {
            name: t('dashboard.chart.voltage'),
            type: 'line' as const,
            smooth: true,
            showSymbol: false,
            lineStyle: { color: '#f59e0b', width: 2, type: 'dashed' as const },
            data: current.voltageCurve.map((point) => point.value),
          },
        ]
  return {
    grid: { left: 45, right: 20, top: 30, bottom: 30 },
    tooltip: { trigger: 'axis' },
    legend: {
      data: series.map((item) => item.name),
      top: 0,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: labels,
    },
    yAxis: { type: 'value' },
    series,
  }
})

function summarizeChartSeries(option: EChartsOption): ChartRuntimeSeriesSummary[] {
  const rawSeries = option.series
  const seriesList = Array.isArray(rawSeries) ? rawSeries : rawSeries ? [rawSeries] : []

  return seriesList.map((series) => {
    const candidate = series as { name?: string; type?: string; data?: unknown[] }
    return {
      name: String(candidate.name || ''),
      type: String(candidate.type || ''),
      pointCount: Array.isArray(candidate.data) ? candidate.data.length : 0,
    }
  })
}

const curveRuntimeSeriesSummary = computed(() =>
  JSON.stringify(summarizeChartSeries(curveOption.value))
)

const curveBindingSummary = computed(() => {
  const curves = baseline.value?.curvesData || []
  const bound = curves.filter((item) => Boolean(item.edc_channel_id))
  const unbound = curves.filter((item) => !item.edc_channel_id)
  return {
    total: curves.length,
    boundCount: bound.length,
    unboundCount: unbound.length,
    items: curves.map((item) => ({
      metricId: item.metric_id,
      metricName: item.metric_name,
      unit: item.unit,
      bound: Boolean(item.edc_channel_id),
      sourceLabel: item.source_channel_label || item.source_channel_name || '',
    })),
  }
})

const curveSourceLabel = computed(() => {
  if (!baseline.value) return t('heat.dataSource.none')
  if (baseline.value.curveSource === 'live_edc') return t('heat.dataSource.liveEdc')
  if (baseline.value.curveSource === 'demo_curve') return t('heat.dataSource.demoCurve')
  return t('heat.dataSource.none')
})

const curveSourceHint = computed(() => {
  if (!baseline.value) return t('baseline.detail.curveSourceNoneHint')
  if (baseline.value.curveSource === 'live_edc') return t('baseline.detail.curveSourceLiveHint')
  if (baseline.value.curveSource === 'demo_curve') return t('baseline.detail.curveSourceDemoHint')
  return t('baseline.detail.curveSourceNoneHint')
})

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
    ? timestampToPlantPickerDate(baseline.value.selectedStartTime)
    : null
  editForm.selectedEndTime = baseline.value.selectedEndTime
    ? timestampToPlantPickerDate(baseline.value.selectedEndTime)
    : null
  editVisible.value = true
}

async function handleOpenSourceHeat() {
  const sourceHeatId = baseline.value?.sourceHeatId
  if (!sourceHeatId) return
  await router.push({
    name: 'HeatDetail',
    params: {
      id: sourceHeatId,
    },
  })
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
      ? pickerDateToPlantTimestamp(editForm.selectedStartTime) || undefined
      : undefined,
    selected_end_time: editForm.selectedEndTime
      ? pickerDateToPlantTimestamp(editForm.selectedEndTime) || undefined
      : undefined,
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

async function handleActivateDefault() {
  if (!baseline.value) return
  const ok = await baselineStore.activateBaseline(baseline.value.id)
  if (!ok) {
    ElMessage.error(t('common.error'))
    return
  }
  ElMessage.success(t('baseline.defaultSetSuccess'))
}

function handleCreateVersion() {
  ElMessage.info(t('baseline.detail.newVersionHint'))
}

onMounted(async () => {
  if (!baselineId.value) return
  await Promise.all([
    baselineStore.fetchDetail(baselineId.value),
    baselineStore.fetchVersionHistory(),
    baselineStore.fetchActiveBaseline(),
  ])
})
</script>

<template>
  <div class="flex flex-col gap-6" data-testid="baseline-detail-page">
    <SystemReadinessBanner section="baselines" test-id="baseline-detail-runtime-banner" />

    <!-- 页面头部 -->
    <PageHeader
      :title="baseline?.name || '--'"
      :subtitle="`ID: ${baselineId}`"
      :description="baseline?.description || t('common.noDescription')"
    >
      <template #actions>
        <StatusBadge :type="statusType" class="mr-2">
          {{ statusLabel }}
        </StatusBadge>
        <StatusBadge v-if="isDefaultBaseline" type="warning" class="mr-2">
          {{ t('baseline.defaultBadge') }}
        </StatusBadge>
        <button
          data-testid="baseline-detail-edit-button"
          class="flex items-center gap-2 bg-white border border-border-light text-slate-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors"
          @click="handleEdit"
        >
          <span class="material-symbols-outlined text-[18px]">edit</span>
          {{ t('common.edit') }}
        </button>
        <button
          v-if="baseline?.status === 'published' && !isDefaultBaseline"
          class="flex items-center gap-2 bg-white border border-border-light text-slate-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors"
          @click="handleActivateDefault"
        >
          <span class="material-symbols-outlined text-[18px]">star</span>
          {{ t('baseline.setDefault') }}
        </button>
        <button
          v-if="baseline?.status === 'published' || baseline?.status === 'draft'"
          class="flex items-center gap-2 bg-white border border-border-light text-slate-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors"
          @click="handleToggleStatus"
        >
          <span class="material-symbols-outlined text-[18px]">
            {{ baseline?.status === 'published' ? 'block' : 'publish' }}
          </span>
          {{ baseline?.status === 'published' ? t('common.disable') : t('baseline.publish') }}
        </button>
        <button
          data-testid="baseline-detail-new-version-button"
          class="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary-dark transition-colors"
          @click="handleCreateVersion"
        >
          <span class="material-symbols-outlined text-[18px]">add_circle</span>
          {{ t('baseline.detail.newVersion') }}
        </button>
      </template>
    </PageHeader>

    <div v-if="baseline" class="grid grid-cols-1 gap-6 xl:grid-cols-3">
      <!-- 主内容区：曲线图 -->
      <div class="xl:col-span-2 bg-white rounded-xl border border-border-light shadow-card p-5">
        <div class="flex items-center justify-between mb-4 pb-4 border-b border-border-light">
          <h3 class="text-sm font-bold text-slate-800 flex items-center gap-2">
            <span class="material-symbols-outlined text-primary text-[20px]">ssid_chart</span>
            {{ t('baseline.detail.curveTitle') }}
          </h3>
        </div>
        <div
          v-if="showtimeMode && isDemoCurveSource"
          class="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700"
        >
          <div class="font-semibold">
            {{ t('baseline.detail.curveSourceDemoBanner') }}
          </div>
          <div class="mt-1 text-xs text-amber-600">
            {{ t('baseline.detail.curveSourceDemoBannerHint') }}
          </div>
        </div>
        <v-chart
          :option="curveOption"
          autoresize
          class="h-96"
          data-testid="baseline-detail-chart"
          :data-runtime-series-summary="curveRuntimeSeriesSummary"
          :data-baseline-id="baseline?.id || ''"
          :data-baseline-name="baseline?.name || ''"
        />
      </div>

      <!-- 右侧信息栏 -->
      <div class="space-y-6">
        <!-- 基础信息卡片 -->
        <div class="bg-white rounded-xl border border-border-light shadow-card p-5">
          <div class="flex items-center justify-between mb-4 pb-4 border-b border-border-light">
            <h3 class="text-sm font-bold text-slate-800 flex items-center gap-2">
              <span class="material-symbols-outlined text-primary text-[20px]">info</span>
              {{ t('baseline.detail.infoTitle') }}
            </h3>
          </div>
          <div class="space-y-4 text-sm text-slate-700">
            <div class="flex justify-between items-center">
              <span class="text-slate-500">{{ t('baseline.definitionName') }}</span>
              <span class="font-semibold">{{ baseline.definitionName }}</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-slate-500">{{ t('baseline.version') }}</span>
              <span class="font-semibold bg-slate-100 px-2 py-0.5 rounded text-xs"
                >v{{ baseline.version }}</span
              >
            </div>
            <div class="flex justify-between items-center">
              <span class="text-slate-500">{{ t('baseline.tolerance') }}</span>
              <span class="font-semibold">{{ baseline.tolerancePercent }}%</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-slate-500">{{ t('baseline.detail.sourceHeat') }}</span>
              <button
                type="button"
                class="font-semibold text-primary transition-colors hover:underline focus:outline-none focus:ring-2 focus:ring-primary/20"
                data-testid="baseline-detail-source-heat-button"
                @click="handleOpenSourceHeat"
              >
                {{ baseline.sourceHeatId }}
              </button>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-slate-500">{{ t('baseline.detail.bindingStatus') }}</span>
              <span class="font-semibold">
                {{ curveBindingSummary.boundCount }}/{{ curveBindingSummary.total }}
              </span>
            </div>
            <div class="flex justify-between items-start gap-4">
              <span class="text-slate-500">{{ t('baseline.detail.curveSource') }}</span>
              <div class="text-right">
                <div class="font-semibold">
                  {{ curveSourceLabel }}
                </div>
                <div class="mt-1 max-w-[220px] text-xs text-slate-500">
                  {{ curveSourceHint }}
                </div>
              </div>
            </div>
            <div class="pt-4 border-t border-border-light">
              <span class="text-slate-500 block mb-1 flex items-center gap-1">
                <span class="material-symbols-outlined text-[16px]">schedule</span>
                {{ t('baseline.wizard.pointRange') }}
              </span>
              <span class="font-mono text-xs text-slate-600 bg-slate-50 p-2 rounded block">
                {{
                  baseline.selectedStartTime
                    ? formatTimestamp(baseline.selectedStartTime, 'YYYY-MM-DD HH:mm:ss')
                    : '--'
                }}
                <br /><span class="text-slate-400">to</span><br />
                {{
                  baseline.selectedEndTime
                    ? formatTimestamp(baseline.selectedEndTime, 'YYYY-MM-DD HH:mm:ss')
                    : '--'
                }}
              </span>
            </div>
          </div>
        </div>

        <div class="bg-white rounded-xl border border-border-light shadow-card p-5">
          <div class="flex items-center justify-between mb-4 pb-4 border-b border-border-light">
            <h3 class="text-sm font-bold text-slate-800 flex items-center gap-2">
              <span class="material-symbols-outlined text-primary text-[20px]">route</span>
              {{ t('baseline.detail.metricSourcesTitle') }}
            </h3>
            <span class="text-xs text-slate-500">
              {{ curveBindingSummary.boundCount }}/{{ curveBindingSummary.total }}
            </span>
          </div>
          <div class="space-y-3">
            <div
              v-for="item in curveBindingSummary.items"
              :key="item.metricId"
              class="rounded-lg border border-border-light bg-slate-50 p-3"
            >
              <div class="flex items-center justify-between gap-3">
                <div class="text-sm font-semibold text-slate-800">
                  {{ item.metricName }} ({{ item.unit }})
                </div>
                <span
                  class="inline-flex rounded-full px-2 py-0.5 text-xs font-medium"
                  :class="
                    item.bound ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                  "
                >
                  {{
                    item.bound
                      ? t('baseline.wizard.metricBound')
                      : t('baseline.wizard.metricUnboundShort')
                  }}
                </span>
              </div>
              <div class="mt-2 text-xs text-slate-500">
                {{ item.bound ? item.sourceLabel : t('baseline.wizard.metricUnbound') }}
              </div>
            </div>
          </div>
        </div>

        <!-- 版本历史卡片 -->
        <div class="bg-white rounded-xl border border-border-light shadow-card p-5">
          <div class="flex items-center justify-between mb-4 pb-4 border-b border-border-light">
            <h3 class="text-sm font-bold text-slate-800 flex items-center gap-2">
              <span class="material-symbols-outlined text-primary text-[20px]">history</span>
              {{ t('baseline.detail.versionHistory') }}
            </h3>
          </div>
          <div
            v-if="baselineStore.versionHistory.length === 0"
            class="py-8 flex flex-col items-center justify-center"
          >
            <span class="material-symbols-outlined text-slate-300 text-4xl">inventory_2</span>
            <p class="text-sm text-slate-400 mt-2">
              {{ t('common.noData') }}
            </p>
          </div>
          <el-timeline v-else class="pl-2">
            <el-timeline-item
              v-for="version in baselineStore.versionHistory"
              :key="version.id"
              :timestamp="formatTimestamp(version.createdAt, 'MM-DD HH:mm')"
              placement="top"
              :color="version.id === baseline.id ? '#1152d4' : '#e2e8f0'"
            >
              <div class="bg-slate-50 p-3 rounded-lg border border-border-light mt-1">
                <div class="flex items-center justify-between mb-1">
                  <span class="font-bold text-sm text-slate-800">{{ version.name }}</span>
                  <StatusBadge
                    :type="
                      version.status === 'published'
                        ? 'success'
                        : version.status === 'draft'
                          ? 'info'
                          : 'danger'
                    "
                    size="sm"
                  >
                    {{
                      version.status === 'published'
                        ? t('baseline.statusPublished')
                        : version.status === 'draft'
                          ? t('baseline.statusDraft')
                          : t('baseline.statusDisabled')
                    }}
                  </StatusBadge>
                </div>
                <div class="text-xs text-slate-500 font-medium">
                  v{{ version.version }} · 阈值 {{ version.tolerancePercent }}%
                </div>
              </div>
            </el-timeline-item>
          </el-timeline>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div
      v-else
      class="py-16 flex flex-col items-center justify-center bg-white rounded-xl border border-border-light shadow-card"
    >
      <span class="material-symbols-outlined text-slate-300 text-5xl">pending</span>
      <p class="text-sm text-slate-400 mt-3">
        {{ t('common.loading') }}
      </p>
    </div>

    <!-- 编辑对话框 -->
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
        <div class="flex justify-end gap-3">
          <button
            class="px-4 py-2 bg-white border border-border-light text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors"
            @click="editVisible = false"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            class="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-dark transition-colors"
            @click="handleSaveEdit"
          >
            {{ t('common.save') }}
          </button>
        </div>
      </template>
    </ElDialog>
  </div>
</template>
