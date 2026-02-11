<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ElButton,
  ElCard,
  ElDatePicker,
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
  ElStep
} from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import type { EChartsOption } from 'echarts'
import { useBaselineDefinitionStore } from '@/stores/baselineDefinition'

use([CanvasRenderer, LineChart, GridComponent, LegendComponent, TooltipComponent])

interface HeatCandidate {
  id: string
  heatNo: string
  date: string
  power: number[]
  voltage: number[]
}

interface WizardSubmitPayload {
  name: string
  description: string
  definitionId: string
  sourceHeatId: string
  tolerancePercent: number
  mode: 'draft' | 'publish'
}

interface Emits {
  (e: 'cancel'): void
  (e: 'submit', payload: WizardSubmitPayload): void
}

const emit = defineEmits<Emits>()
const { t } = useI18n()
const baselineDefinitionStore = useBaselineDefinitionStore()

const activeStep = ref(0)
const dateRange = ref<[Date, Date] | null>(null)
const selectedHeatId = ref('')

const formData = ref({
  name: '',
  description: '',
  definitionId: '',
  tolerancePercent: 15
})

const heatCandidates = ref<HeatCandidate[]>([
  {
    id: 'heat-101',
    heatNo: 'H20260209-101',
    date: '2026-02-09 09:30',
    power: [420, 435, 450, 448, 452, 460, 455],
    voltage: [378, 380, 382, 381, 383, 384, 383]
  },
  {
    id: 'heat-102',
    heatNo: 'H20260209-102',
    date: '2026-02-09 11:15',
    power: [405, 418, 436, 446, 451, 458, 462],
    voltage: [376, 378, 381, 382, 382, 383, 384]
  },
  {
    id: 'heat-103',
    heatNo: 'H20260209-103',
    date: '2026-02-09 14:40',
    power: [430, 442, 449, 455, 460, 465, 468],
    voltage: [379, 381, 383, 384, 384, 385, 386]
  }
])

const filteredCandidates = computed(() => {
  if (!dateRange.value) {
    return heatCandidates.value
  }
  const [start, end] = dateRange.value
  return heatCandidates.value.filter(item => {
    const date = new Date(item.date)
    return date >= start && date <= end
  })
})

const selectedHeat = computed(() =>
  heatCandidates.value.find(item => item.id === selectedHeatId.value) || null
)

const compareOption = computed<EChartsOption>(() => {
  const xAxis = ['T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7']
  const baselinePower = [415, 430, 445, 450, 455, 460, 462]
  const currentPower = selectedHeat.value?.power || []
  return {
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    tooltip: { trigger: 'axis' },
    legend: {
      data: [t('baseline.wizard.goldenBaseline'), t('baseline.wizard.currentHeat')],
      top: 0
    },
    xAxis: { type: 'category', data: xAxis },
    yAxis: { type: 'value' },
    series: [
      {
        name: t('baseline.wizard.goldenBaseline'),
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { color: '#67C23A', type: 'dashed', width: 2 },
        data: baselinePower
      },
      {
        name: t('baseline.wizard.currentHeat'),
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { color: '#409EFF', width: 2 },
        data: currentPower
      }
    ]
  }
})

const summaryStats = computed(() => {
  const values = selectedHeat.value?.power || []
  if (!values.length) {
    return { avg: 0, peak: 0 }
  }
  const avg = values.reduce((acc, value) => acc + value, 0) / values.length
  const peak = Math.max(...values)
  return {
    avg: Number(avg.toFixed(1)),
    peak
  }
})

function nextStep() {
  if (activeStep.value === 0 && !selectedHeatId.value) {
    ElMessage.warning(t('baseline.wizard.selectHeatRequired'))
    return
  }
  if (activeStep.value === 2 && !formData.value.name.trim()) {
    ElMessage.warning(t('baseline.wizard.nameRequired'))
    return
  }
  if (activeStep.value === 2 && !formData.value.definitionId) {
    ElMessage.warning(t('baseline.wizard.definitionRequired'))
    return
  }
  if (activeStep.value < 3) {
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
    tolerancePercent: formData.value.tolerancePercent,
    mode
  })
}

onMounted(async () => {
  await baselineDefinitionStore.fetchList('active')
  if (!formData.value.definitionId && baselineDefinitionStore.list.length > 0) {
    formData.value.definitionId = baselineDefinitionStore.list[0].id
  }
})
</script>

<template>
  <div class="space-y-6">
    <el-steps
      :active="activeStep"
      finish-status="success"
    >
      <el-step :title="t('baseline.wizard.step1')" />
      <el-step :title="t('baseline.wizard.step2')" />
      <el-step :title="t('baseline.wizard.step3')" />
      <el-step :title="t('baseline.wizard.step4')" />
    </el-steps>

    <div
      v-if="activeStep === 0"
      class="space-y-4"
    >
      <el-card>
        <div class="space-y-4">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            unlink-panels
            :range-separator="t('baseline.wizard.to')"
            :start-placeholder="t('baseline.wizard.startDate')"
            :end-placeholder="t('baseline.wizard.endDate')"
            class="w-full"
          />
          <div
            v-if="filteredCandidates.length > 0"
            class="grid grid-cols-1 gap-3 md:grid-cols-2"
          >
            <label
              v-for="item in filteredCandidates"
              :key="item.id"
              class="cursor-pointer rounded-lg border p-4 transition hover:border-primary"
              :class="selectedHeatId === item.id ? 'border-primary bg-blue-50' : 'border-gray-200'"
            >
              <el-radio
                v-model="selectedHeatId"
                :value="item.id"
              >{{ item.heatNo }}</el-radio>
              <div class="mt-2 text-xs text-gray-500">{{ item.date }}</div>
            </label>
          </div>
          <el-empty
            v-else
            :description="t('common.noData')"
          />
        </div>
      </el-card>
    </div>

    <div
      v-if="activeStep === 1"
      class="space-y-4"
    >
      <el-card>
        <v-chart
          :option="compareOption"
          autoresize
          class="h-80"
        />
      </el-card>
      <el-card>
        <div class="grid grid-cols-2 gap-4 text-sm">
          <div class="rounded-lg bg-gray-50 p-3">
            <div class="text-gray-500">
              {{ t('baseline.wizard.avgPower') }}
            </div>
            <div class="mt-1 text-lg font-semibold">
              {{ summaryStats.avg }} kW
            </div>
          </div>
          <div class="rounded-lg bg-gray-50 p-3">
            <div class="text-gray-500">
              {{ t('baseline.wizard.peakPower') }}
            </div>
            <div class="mt-1 text-lg font-semibold">
              {{ summaryStats.peak }} kW
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <div
      v-if="activeStep === 2"
      class="space-y-4"
    >
      <el-card>
        <el-form label-position="top">
          <el-form-item :label="t('baseline.name')">
            <el-input
              v-model="formData.name"
              :placeholder="t('baseline.wizard.namePlaceholder')"
            />
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
            <el-input-number
              v-model="formData.tolerancePercent"
              :min="0"
              :max="100"
              :step="0.5"
            />
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

    <div
      v-if="activeStep === 3"
      class="space-y-4"
    >
      <el-card>
        <div class="space-y-2 text-sm text-gray-700">
          <div><span class="text-gray-500">{{ t('baseline.name') }}:</span> {{ formData.name }}</div>
          <div>
            <span class="text-gray-500">{{ t('baseline.selectHeat') }}:</span>
            {{ selectedHeat?.heatNo || '--' }}
          </div>
          <div>
            <span class="text-gray-500">{{ t('baseline.wizard.definition') }}:</span>
            {{
              baselineDefinitionStore.list.find(item => item.id === formData.definitionId)?.definitionName ||
              '--'
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
      <el-button @click="emit('cancel')">
        {{ t('common.cancel') }}
      </el-button>
      <div class="flex items-center gap-2">
        <el-button
          v-if="activeStep > 0"
          @click="prevStep"
        >
          {{ t('common.back') }}
        </el-button>
        <el-button
          v-if="activeStep < 3"
          type="primary"
          @click="nextStep"
        >
          {{ t('common.next') }}
        </el-button>
        <template v-else>
          <el-button @click="submit('draft')">
            {{ t('baseline.wizard.saveDraft') }}
          </el-button>
          <el-button
            type="primary"
            @click="submit('publish')"
          >
            {{ t('baseline.publish') }}
          </el-button>
        </template>
      </div>
    </div>
  </div>
</template>
