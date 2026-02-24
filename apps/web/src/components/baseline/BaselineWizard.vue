<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ElButton,
  ElCard,
  ElDialog,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElOption,
  ElRadio,
  ElSelect,
  ElSteps,
  ElStep,
  ElDatePicker
} from 'element-plus'
import { FullScreen } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import type { EChartsOption } from 'echarts'
import dayjs from 'dayjs'
import { useBaselineDefinitionStore } from '@/stores/baselineDefinition'

use([CanvasRenderer, LineChart, GridComponent, LegendComponent, TooltipComponent])

interface HeatPoint {
  timestamp: number
  power: number
  voltage: number
}

interface HeatCandidate {
  id: string
  heatNo: string
  date: string
  startTime: number
  endTime: number
}

interface WizardSubmitPayload {
  name: string
  description: string
  definitionId: string
  sourceHeatId: string
  selectedStartTime?: string
  selectedEndTime?: string
  tolerancePercent: number
  mode: 'draft' | 'publish'
}

interface Props {
  initialSourceHeatId?: string
  initialSelectedStartTime?: string
  initialSelectedEndTime?: string
  initialName?: string
}

interface Emits {
  (e: 'cancel'): void
  (e: 'submit', payload: WizardSubmitPayload): void
}

const emit = defineEmits<Emits>()
const props = withDefaults(defineProps<Props>(), {
  initialSourceHeatId: '',
  initialSelectedStartTime: '',
  initialSelectedEndTime: '',
  initialName: ''
})
const { t } = useI18n()
const baselineDefinitionStore = useBaselineDefinitionStore()

const activeStep = ref(0)
const selectedHeatId = ref('')
const selectingBoundary = ref<'start' | 'end'>('start')
const fullscreenVisible = ref(false)

const formData = ref({
  name: '',
  description: '',
  definitionId: '',
  tolerancePercent: 15
})

const fullCurvePoints = ref<HeatPoint[]>([])

const heatCandidates = ref<HeatCandidate[]>([])

const selectedHeat = computed(() =>
  heatCandidates.value.find(item => item.id === selectedHeatId.value) || null
)

const selectedStart = ref<number | null>(null)
const selectedEnd = ref<number | null>(null)

const selectedStartDate = ref<Date | null>(null)
const selectedEndDate = ref<Date | null>(null)

watch(() => selectedStart.value, (val) => {
  selectedStartDate.value = val ? new Date(val) : null
})

watch(() => selectedEnd.value, (val) => {
  selectedEndDate.value = val ? new Date(val) : null
})

watch(selectedStartDate, (val) => {
  const ts = val ? dayjs(val).valueOf() : null
  if (ts !== selectedStart.value) {
    selectedStart.value = ts
    normalizeRange()
  }
})

watch(selectedEndDate, (val) => {
  const ts = val ? dayjs(val).valueOf() : null
  if (ts !== selectedEnd.value) {
    selectedEnd.value = ts
    normalizeRange()
  }
})

function normalizeRange() {
  if (!selectedStart.value || !selectedEnd.value) return
  if (selectedStart.value > selectedEnd.value) {
    const temp = selectedStart.value
    selectedStart.value = selectedEnd.value
    selectedEnd.value = temp
  }
}

function resetRangeByHeat() {
  if (!selectedHeat.value) {
    selectedStart.value = null
    selectedEnd.value = null
    return
  }
  selectedStart.value = selectedHeat.value.startTime || null
  selectedEnd.value = selectedHeat.value.endTime || null
}

const compareOption = computed<EChartsOption>(() => {
  if (fullCurvePoints.value.length === 0) return {}

  const labels = fullCurvePoints.value.map(point => dayjs(point.timestamp).format('HH:mm:ss'))
  const rangeStart = selectedStart.value ? dayjs(selectedStart.value).format('HH:mm:ss') : null
  const rangeEnd = selectedEnd.value ? dayjs(selectedEnd.value).format('HH:mm:ss') : null

  return {
    grid: { left: 50, right: 20, top: 40, bottom: 40 },
    tooltip: { trigger: 'axis' },
    legend: {
      data: [t('baseline.wizard.currentHeatPower'), t('baseline.wizard.currentHeatVoltage')],
      top: 0
    },
    xAxis: { type: 'category', data: labels },
    yAxis: [
      { type: 'value', name: 'kW' },
      { type: 'value', name: 'V' }
    ],
    series: [
      {
        name: t('baseline.wizard.currentHeatPower'),
        type: 'line' as const,
        smooth: true,
        showSymbol: false,
        lineStyle: { color: '#409EFF', width: 2 },
        data: fullCurvePoints.value.map(point => point.power),
        markArea:
          rangeStart && rangeEnd
            ? {
                itemStyle: { color: 'rgba(64, 158, 255, 0.15)' },
                data: [[{ xAxis: rangeStart }, { xAxis: rangeEnd }]]
              }
            : undefined
      },
      {
        name: t('baseline.wizard.currentHeatVoltage'),
        type: 'line' as const,
        smooth: true,
        showSymbol: false,
        yAxisIndex: 1,
        lineStyle: { color: '#67C23A', width: 2, type: 'dashed' as const },
        data: fullCurvePoints.value.map(point => point.voltage)
      }
    ]
  }
})

function handleChartClick(params: { dataIndex?: number }) {
  if (params.dataIndex === undefined || fullCurvePoints.value.length === 0) return
  const point = fullCurvePoints.value[params.dataIndex]
  if (!point) return

  if (selectingBoundary.value === 'start') {
    selectedStart.value = point.timestamp
    selectingBoundary.value = 'end'
  } else {
    selectedEnd.value = point.timestamp
    selectingBoundary.value = 'start'
  }
  normalizeRange()
}

function adjustBoundary(boundary: 'start' | 'end', deltaSecond: number) {
  if (boundary === 'start' && selectedStart.value) {
    selectedStart.value += deltaSecond * 1000
  }
  if (boundary === 'end' && selectedEnd.value) {
    selectedEnd.value += deltaSecond * 1000
  }
  normalizeRange()
}

const summaryStats = computed(() => {
  if (!selectedStart.value || !selectedEnd.value) {
    return { avg: 0, peak: 0, durationSecond: 0 }
  }
  const selected = fullCurvePoints.value.filter(
    point => point.timestamp >= selectedStart.value! && point.timestamp <= selectedEnd.value!
  )
  if (selected.length === 0) {
    return { avg: 0, peak: 0, durationSecond: 0 }
  }
  const values = selected.map(point => point.power)
  const avg = values.reduce((acc, value) => acc + value, 0) / values.length
  const peak = Math.max(...values)
  return {
    avg: Number(avg.toFixed(1)),
    peak,
    durationSecond: Math.floor((selectedEnd.value - selectedStart.value) / 1000)
  }
})

function nextStep() {
  if (activeStep.value === 0 && !selectedHeatId.value) {
    ElMessage.warning(t('baseline.wizard.selectHeatRequired'))
    return
  }
  if (activeStep.value === 0 && (!selectedStart.value || !selectedEnd.value)) {
    ElMessage.warning(t('baseline.wizard.pointRangeRequired'))
    return
  }
  if (activeStep.value === 1 && !formData.value.name.trim()) {
    ElMessage.warning(t('baseline.wizard.nameRequired'))
    return
  }
  if (activeStep.value === 1 && !formData.value.definitionId) {
    ElMessage.warning(t('baseline.wizard.definitionRequired'))
    return
  }
  if (activeStep.value < 2) {
    activeStep.value += 1
  }
}

function prevStep() {
  if (activeStep.value > 0) {
    activeStep.value -= 1
  }
}

function submit(mode: 'draft' | 'publish') {
  if (!selectedHeatId.value || !formData.value.name.trim() || !formData.value.definitionId) {
    ElMessage.warning(t('baseline.wizard.incompleteForm'))
    return
  }

  emit('submit', {
    name: formData.value.name.trim(),
    description: formData.value.description.trim(),
    definitionId: formData.value.definitionId,
    sourceHeatId: selectedHeatId.value,
    selectedStartTime: selectedStart.value ? dayjs(selectedStart.value).toISOString() : undefined,
    selectedEndTime: selectedEnd.value ? dayjs(selectedEnd.value).toISOString() : undefined,
    tolerancePercent: formData.value.tolerancePercent,
    mode
  })
}

function handleSelectHeat(id: string) {
  selectedHeatId.value = id
  selectingBoundary.value = 'start'
  resetRangeByHeat()
}

function ensurePrefillHeatCandidate() {
  if (!props.initialSourceHeatId) return
  const exists = heatCandidates.value.some(item => item.id === props.initialSourceHeatId)
  if (exists) return

  const start = props.initialSelectedStartTime ? dayjs(props.initialSelectedStartTime) : dayjs().subtract(1, 'hour')
  const points = Array.from({ length: 360 }).map((_, index) => {
    const ts = start.add(index * 10, 'second').valueOf()
    return {
      timestamp: ts,
      power: Number((425 + Math.sin(index / 16) * 22 + (index % 4)).toFixed(1)),
      voltage: Number((381 + Math.cos(index / 21) * 5).toFixed(1))
    }
  })

  heatCandidates.value.unshift({
    id: props.initialSourceHeatId,
    heatNo: props.initialName || `H-PREFILL-${props.initialSourceHeatId}`,
    date: dayjs(points[0]?.timestamp || Date.now()).format('YYYY-MM-DD HH:mm:ss'),
    startTime: points[0]?.timestamp || Date.now(),
    endTime: points[points.length - 1]?.timestamp || Date.now()
  })
}

function applyPrefillRange() {
  if (!props.initialSelectedStartTime || !props.initialSelectedEndTime) return
  selectedStart.value = dayjs(props.initialSelectedStartTime).valueOf()
  selectedEnd.value = dayjs(props.initialSelectedEndTime).valueOf()
  normalizeRange()
}

onMounted(async () => {
  const now = dayjs()
  let curveStart = dayjs().hour(6).minute(0).second(0).millisecond(0)
  if (now.isBefore(curveStart)) {
    curveStart = now.startOf('day')
  }
  const stepSeconds = 10
  const totalSeconds = Math.max(0, now.diff(curveStart, 'second'))
  const totalPoints = Math.max(1, Math.floor(totalSeconds / stepSeconds))
  fullCurvePoints.value = Array.from({ length: totalPoints + 1 }).map((_, index) => {
    const ts = curveStart.add(index * stepSeconds, 'second').valueOf()
    return {
      timestamp: ts,
      power: Number((418 + Math.sin(index / 18) * 26 + (index % 6)).toFixed(1)),
      voltage: Number((382 + Math.cos(index / 22) * 6).toFixed(1))
    }
  })

  const candidateSeed = [
    { id: 'heat-101', heatNo: 'H20260223-101', offsetMinutes: 90, durationMinutes: 30 },
    { id: 'heat-102', heatNo: 'H20260223-102', offsetMinutes: 210, durationMinutes: 28 },
    { id: 'heat-103', heatNo: 'H20260223-103', offsetMinutes: 360, durationMinutes: 32 }
  ]
  heatCandidates.value = candidateSeed.map(item => {
    let start = curveStart.add(item.offsetMinutes, 'minute')
    if (start.isAfter(now)) {
      start = now.subtract(item.durationMinutes, 'minute')
    }
    let end = start.add(item.durationMinutes, 'minute')
    if (end.isAfter(now)) {
      end = now
    }
    return {
      id: item.id,
      heatNo: item.heatNo,
      date: start.format('YYYY-MM-DD HH:mm:ss'),
      startTime: start.valueOf(),
      endTime: end.valueOf()
    }
  })

  ensurePrefillHeatCandidate()

  await baselineDefinitionStore.fetchList('active')
  const firstDefinition = baselineDefinitionStore.list[0]
  if (!formData.value.definitionId && firstDefinition) {
    formData.value.definitionId = firstDefinition.id
  }
  if (props.initialName) {
    formData.value.name = props.initialName
  }

  if (props.initialSourceHeatId) {
    selectedHeatId.value = props.initialSourceHeatId
  }

  if (!selectedHeatId.value && heatCandidates.value[0]) {
    selectedHeatId.value = heatCandidates.value[0].id
  }

  if (props.initialSelectedStartTime && props.initialSelectedEndTime) {
    applyPrefillRange()
  } else {
    resetRangeByHeat()
  }
})
</script>

<template>
  <div class="space-y-6">
    <el-steps :active="activeStep" finish-status="success">
      <el-step :title="t('baseline.wizard.step1')" />
      <el-step :title="t('baseline.wizard.step2')" />
      <el-step :title="t('baseline.wizard.step3')" />
    </el-steps>

    <div v-if="activeStep === 0" class="space-y-4">
      <el-card>
        <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
          <label
            v-for="item in heatCandidates"
            :key="item.id"
            class="cursor-pointer rounded-lg border p-4 transition hover:border-primary"
            :class="selectedHeatId === item.id ? 'border-primary bg-blue-50' : 'border-gray-200'"
          >
            <el-radio :model-value="selectedHeatId" :value="item.id" @change="handleSelectHeat(item.id)">
              {{ item.heatNo }}
            </el-radio>
            <div class="mt-2 text-xs text-gray-500">{{ item.date }}</div>
          </label>
        </div>
      </el-card>

      <el-card>
        <template #header>
          <div class="flex items-center justify-between">
            <span>{{ t('baseline.wizard.chartPickTitle') }}</span>
            <el-button :icon="FullScreen" @click="fullscreenVisible = true">
              {{ t('baseline.wizard.fullscreen') }}
            </el-button>
          </div>
        </template>

        <div v-if="fullCurvePoints.length > 0" class="space-y-4">
          <v-chart :option="compareOption" autoresize class="h-80" @click="handleChartClick" />

          <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div class="space-y-2">
              <div class="text-sm text-gray-500">{{ t('baseline.wizard.pointRange') }}</div>
              <div class="flex items-center gap-2">
                <el-button
                  :type="selectingBoundary === 'start' ? 'primary' : 'default'"
                  @click="selectingBoundary = 'start'"
                >
                  {{ t('baseline.wizard.pickStart') }}
                </el-button>
                <el-button
                  :type="selectingBoundary === 'end' ? 'primary' : 'default'"
                  @click="selectingBoundary = 'end'"
                >
                  {{ t('baseline.wizard.pickEnd') }}
                </el-button>
              </div>
              <div class="text-xs text-gray-500">
                {{ t('baseline.wizard.pickHint') }}
              </div>
            </div>

            <div class="grid grid-cols-1 gap-3">
              <el-form-item :label="t('baseline.wizard.rangeStart')">
                <div class="flex w-full items-center gap-2">
                  <el-date-picker
                    v-model="selectedStartDate"
                    type="datetime"
                    format="YYYY-MM-DD HH:mm:ss"
                    class="w-full"
                  />
                  <el-button @click="adjustBoundary('start', -1)">-1s</el-button>
                  <el-button @click="adjustBoundary('start', 1)">+1s</el-button>
                </div>
              </el-form-item>
              <el-form-item :label="t('baseline.wizard.rangeEnd')">
                <div class="flex w-full items-center gap-2">
                  <el-date-picker
                    v-model="selectedEndDate"
                    type="datetime"
                    format="YYYY-MM-DD HH:mm:ss"
                    class="w-full"
                  />
                  <el-button @click="adjustBoundary('end', -1)">-1s</el-button>
                  <el-button @click="adjustBoundary('end', 1)">+1s</el-button>
                </div>
              </el-form-item>
            </div>
          </div>
        </div>
        <el-empty v-else :description="t('common.noData')" />
      </el-card>

      <el-card>
        <div class="grid grid-cols-3 gap-4 text-sm">
          <div class="rounded-lg bg-gray-50 p-3">
            <div class="text-gray-500">{{ t('baseline.wizard.avgPower') }}</div>
            <div class="mt-1 text-lg font-semibold">{{ summaryStats.avg }} kW</div>
          </div>
          <div class="rounded-lg bg-gray-50 p-3">
            <div class="text-gray-500">{{ t('baseline.wizard.peakPower') }}</div>
            <div class="mt-1 text-lg font-semibold">{{ summaryStats.peak }} kW</div>
          </div>
          <div class="rounded-lg bg-gray-50 p-3">
            <div class="text-gray-500">{{ t('baseline.wizard.selectedDuration') }}</div>
            <div class="mt-1 text-lg font-semibold">{{ summaryStats.durationSecond }}s</div>
          </div>
        </div>
      </el-card>
    </div>

    <div v-if="activeStep === 1" class="space-y-4">
      <el-card>
        <el-form label-position="top">
          <el-form-item :label="t('baseline.name')">
            <el-input v-model="formData.name" :placeholder="t('baseline.wizard.namePlaceholder')" />
          </el-form-item>
          <el-form-item :label="t('baseline.wizard.definition')">
            <el-select
              v-model="formData.definitionId"
              class="w-full"
              :placeholder="t('baseline.wizard.definitionPlaceholder')"
            >
              <el-option
                v-for="item in baselineDefinitionStore.list"
                :key="item.id"
                :label="item.definitionName"
                :value="item.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('baseline.tolerance')">
            <el-input-number v-model="formData.tolerancePercent" :min="0" :max="100" :step="0.5" />
          </el-form-item>
          <el-form-item :label="t('baseline.wizard.description')">
            <el-input
              v-model="formData.description"
              type="textarea"
              :rows="4"
              :placeholder="t('baseline.wizard.descriptionPlaceholder')"
            />
          </el-form-item>
        </el-form>
      </el-card>
    </div>

    <div v-if="activeStep === 2" class="space-y-4">
      <el-card>
        <div class="space-y-2 text-sm text-gray-700">
          <div><span class="text-gray-500">{{ t('baseline.name') }}:</span> {{ formData.name }}</div>
          <div>
            <span class="text-gray-500">{{ t('baseline.selectHeat') }}:</span>
            {{ selectedHeat?.heatNo || '--' }}
          </div>
          <div>
            <span class="text-gray-500">{{ t('baseline.wizard.pointRange') }}:</span>
            {{ selectedStart ? dayjs(selectedStart).format('YYYY-MM-DD HH:mm:ss') : '--' }}
            ~
            {{ selectedEnd ? dayjs(selectedEnd).format('YYYY-MM-DD HH:mm:ss') : '--' }}
          </div>
          <div>
            <span class="text-gray-500">{{ t('baseline.wizard.definition') }}:</span>
            {{
              baselineDefinitionStore.list.find(item => item.id === formData.definitionId)?.definitionName || '--'
            }}
          </div>
          <div>
            <span class="text-gray-500">{{ t('baseline.tolerance') }}:</span>
            {{ formData.tolerancePercent }}%
          </div>
          <div>
            <span class="text-gray-500">{{ t('baseline.wizard.description') }}:</span>
            {{ formData.description || t('common.noDescription') }}
          </div>
        </div>
      </el-card>
      <div class="rounded-lg border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-700">
        {{ t('baseline.wizard.confirmHint') }}
      </div>
    </div>

    <div class="flex items-center justify-between">
      <el-button @click="emit('cancel')">{{ t('common.cancel') }}</el-button>
      <div class="flex items-center gap-2">
        <el-button v-if="activeStep > 0" @click="prevStep">{{ t('common.back') }}</el-button>
        <el-button v-if="activeStep < 2" type="primary" @click="nextStep">
          {{ t('common.next') }}
        </el-button>
        <template v-else>
          <el-button @click="submit('draft')">{{ t('baseline.wizard.saveDraft') }}</el-button>
          <el-button type="primary" @click="submit('publish')">{{ t('baseline.publish') }}</el-button>
        </template>
      </div>
    </div>

    <el-dialog v-model="fullscreenVisible" :title="t('baseline.wizard.fullscreenTitle')" fullscreen>
      <div class="h-[78vh]">
        <v-chart :option="compareOption" autoresize class="h-full" @click="handleChartClick" />
      </div>
      <template #footer>
        <el-button @click="fullscreenVisible = false">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>
