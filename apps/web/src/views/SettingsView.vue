<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  type ComponentPublicInstance,
} from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ElDatePicker,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElOption,
  ElRadio,
  ElRadioButton,
  ElRadioGroup,
  ElSelect,
} from 'element-plus'
import PageHeader from '@/components/common/PageHeader.vue'
import SystemReadinessBanner from '@/components/common/SystemReadinessBanner.vue'
import { baselineApi, type BaselineResponse } from '@/api/baseline'
import { heatApi, type HeatReplayJobResponse } from '@/api/heat'
import { useRuntimeStatusStore } from '@/stores/runtimeStatus'
import { useSettingStore } from '@/stores/setting'

const { t } = useI18n()
const settingStore = useSettingStore()
const runtimeStatusStore = useRuntimeStatusStore()

const hostConnectivity = computed(() => runtimeStatusStore.data.host)
const edcSummary = computed(() => runtimeStatusStore.data.edc)
const pageRef = ref<HTMLElement | null>(null)
type SettingsSectionId = 'hostConnectivity' | 'replayInitialization' | 'tolerance' | 'cutting'

const activeSection = ref<SettingsSectionId>('hostConnectivity')
const scrollContainer = ref<HTMLElement | null>(null)
const sectionRefs: Record<SettingsSectionId, HTMLElement | null> = {
  hostConnectivity: null,
  replayInitialization: null,
  tolerance: null,
  cutting: null,
}
const timezoneOptions = [
  'Asia/Shanghai',
  'UTC',
  'Asia/Tokyo',
  'Asia/Singapore',
  'America/Los_Angeles',
  'America/New_York',
]
const navigationItems = computed(() => [
  {
    id: 'hostConnectivity' as const,
    icon: 'database',
    label: t('settings.hostManagedConnection'),
  },
  {
    id: 'replayInitialization' as const,
    icon: 'history_toggle_off',
    label: t('settings.replayInitializationTitle'),
  },
  {
    id: 'tolerance' as const,
    icon: 'tune',
    label: t('settings.toleranceSectionTitle'),
  },
  {
    id: 'cutting' as const,
    icon: 'content_cut',
    label: t('settings.cuttingConfig'),
  },
])
const replayBaselineOptions = ref<BaselineResponse[]>([])
const replayInitializationSubmitting = ref(false)
const replayInitializationJob = ref<HeatReplayJobResponse | null>(null)
const replayInitializationForm = reactive({
  startTime: '',
  primaryBaselineId: '',
  baselineIds: [] as string[],
})
const cuttingModeOptions = computed(() => [
  {
    value: 'signal_inference' as const,
    testId: 'settings-cutting-mode-signal',
    label: t('settings.cuttingModeSignalInference'),
    description: t('settings.cuttingModeSignalInferenceHint'),
  },
  {
    value: 'fixed_interval' as const,
    testId: 'settings-cutting-mode-fixed',
    label: t('settings.cuttingModeFixedInterval'),
    description: t('settings.cuttingModeFixedIntervalHint'),
  },
])

function formatReplayBaselineLabel(baseline: BaselineResponse | null | undefined) {
  if (!baseline) return ''
  const description = baseline.description?.trim()
  return description ? `${baseline.name} / ${description}` : baseline.name
}

const replayPrimaryBaseline = computed(
  () =>
    replayBaselineOptions.value.find(
      (item) => item.id === replayInitializationForm.primaryBaselineId
    ) ?? null
)

const replayPrimaryBaselineDisplayLabel = computed(() =>
  formatReplayBaselineLabel(replayPrimaryBaseline.value)
)

const replaySelectableBaselineOptions = computed(() => {
  const expectedDuration = replayPrimaryBaseline.value?.expected_duration_minutes
  if (!expectedDuration) {
    return replayBaselineOptions.value
  }
  return replayBaselineOptions.value.filter(
    (item) => item.expected_duration_minutes === expectedDuration
  )
})

function syncReplaySelectionToPrimaryDefinition() {
  const allowedIds = new Set(replaySelectableBaselineOptions.value.map((item) => item.id))
  replayInitializationForm.baselineIds = replayInitializationForm.baselineIds.filter((id) =>
    allowedIds.has(id)
  )
  ensureReplayPrimaryInSelection()
}

function ensureReplayPrimaryInSelection() {
  const primaryId = replayInitializationForm.primaryBaselineId
  if (!primaryId) return
  if (!replayInitializationForm.baselineIds.includes(primaryId)) {
    replayInitializationForm.baselineIds = [...replayInitializationForm.baselineIds, primaryId]
  }
}

function handleReplayBaselineSelectionChange(value: string[]) {
  const allowedIds = new Set(replaySelectableBaselineOptions.value.map((item) => item.id))
  replayInitializationForm.baselineIds = value.filter((id) => allowedIds.has(id))
  ensureReplayPrimaryInSelection()
}

async function loadReplayBaselineOptions() {
  const response = await baselineApi.list('published')
  replayBaselineOptions.value = response.items
  const baselineIds = response.items.map((item) => item.id)
  replayInitializationForm.baselineIds = replayInitializationForm.baselineIds.filter((id) =>
    baselineIds.includes(id)
  )
  if (
    replayInitializationForm.primaryBaselineId &&
    !baselineIds.includes(replayInitializationForm.primaryBaselineId)
  ) {
    replayInitializationForm.primaryBaselineId = ''
  }

  const defaultBaseline = response.items.find((item) => item.is_default) ?? response.items[0]
  if (defaultBaseline) {
    replayInitializationForm.primaryBaselineId = defaultBaseline.id
  } else {
    replayInitializationForm.primaryBaselineId = ''
  }
  syncReplaySelectionToPrimaryDefinition()
}

async function pollReplayInitializationJob(jobId: string) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const job = await heatApi.getReplayJob(jobId)
    replayInitializationJob.value = job
    if (['completed', 'failed', 'cancelled'].includes(job.status)) {
      return job
    }
    await new Promise((resolve) => window.setTimeout(resolve, 1000))
  }
  return replayInitializationJob.value
}

async function submitReplayInitialization() {
  if (!replayInitializationForm.startTime) {
    ElMessage.warning(t('settings.replayInitializationStartRequired'))
    return
  }
  if (!replayInitializationForm.primaryBaselineId) {
    ElMessage.warning(t('settings.replayInitializationPrimaryRequired'))
    return
  }
  ensureReplayPrimaryInSelection()
  if (replayInitializationForm.baselineIds.length === 0) {
    ElMessage.warning(t('settings.replayInitializationBaselineRequired'))
    return
  }

  replayInitializationSubmitting.value = true
  try {
    const createdJob = await heatApi.createReplayJob({
      start_time: Number(replayInitializationForm.startTime),
      primary_baseline_id: replayInitializationForm.primaryBaselineId,
      baseline_ids: replayInitializationForm.baselineIds,
      force_replace: true,
    })
    replayInitializationJob.value = createdJob
    ElMessage.success(t('settings.replayInitializationStarted'))
    const finalJob = await pollReplayInitializationJob(createdJob.id)
    if (finalJob?.status === 'completed') {
      await runtimeStatusStore.fetchRuntimeStatus()
      ElMessage.success(t('settings.replayInitializationCompleted'))
    } else if (finalJob?.status === 'failed') {
      ElMessage.error(finalJob.error_message || t('settings.replayInitializationFailed'))
    } else if (finalJob?.status === 'cancelled') {
      ElMessage.info(t('settings.replayInitializationCancelled'))
    }
  } finally {
    replayInitializationSubmitting.value = false
  }
}

function setSectionRef(
  sectionId: SettingsSectionId,
  element: Element | ComponentPublicInstance | null
) {
  sectionRefs[sectionId] = element instanceof HTMLElement ? element : null
}

function findScrollContainer(element: HTMLElement | null) {
  let current = element?.parentElement ?? null

  while (current) {
    const style = window.getComputedStyle(current)
    if (
      ['auto', 'scroll'].includes(style.overflowY) &&
      current.scrollHeight > current.clientHeight
    ) {
      return current
    }
    current = current.parentElement
  }

  return null
}

function syncActiveSection() {
  const candidates = navigationItems.value
    .map((item) => {
      const element = sectionRefs[item.id]
      if (!element) return null
      return {
        id: item.id,
        distance: Math.abs(element.getBoundingClientRect().top - 144),
      }
    })
    .filter((item): item is { id: SettingsSectionId; distance: number } => item !== null)

  if (!candidates.length) return

  candidates.sort((left, right) => left.distance - right.distance)
  const nextSection = candidates[0]
  if (!nextSection) return
  activeSection.value = nextSection.id
}

function handleSectionNavigate(sectionId: SettingsSectionId) {
  const element = sectionRefs[sectionId]
  if (!element) return

  activeSection.value = sectionId
  element.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function saveTolerance() {
  await settingStore.saveTolerance()
  ElMessage.success(t('common.success'))
}

async function saveReport() {
  await settingStore.saveReport()
  ElMessage.success(t('common.success'))
}

async function saveCutting() {
  if (
    settingStore.data.cuttingMode === 'fixed_interval' &&
    (settingStore.data.fixedIntervalMinutes === null || settingStore.data.fixedIntervalMinutes <= 0)
  ) {
    ElMessage.warning(t('settings.fixedIntervalRequired'))
    return
  }
  await settingStore.saveCutting()
  ElMessage.success(t('common.success'))
}

function resetTolerance() {
  settingStore.resetTolerance()
}

function handleViewportChange() {
  syncActiveSection()
}

onMounted(async () => {
  scrollContainer.value = findScrollContainer(pageRef.value)
  scrollContainer.value?.addEventListener('scroll', handleViewportChange, {
    passive: true,
  })
  window.addEventListener('resize', handleViewportChange)
  await Promise.all([settingStore.fetchSettings(), loadReplayBaselineOptions()])
  await nextTick()
  syncActiveSection()
})

onBeforeUnmount(() => {
  scrollContainer.value?.removeEventListener('scroll', handleViewportChange)
  window.removeEventListener('resize', handleViewportChange)
})
</script>

<template>
  <div ref="pageRef" class="flex flex-col gap-6" data-testid="settings-page">
    <!-- 页面头部 -->
    <PageHeader :title="t('settings.title')" :subtitle="t('settings.subtitle')" />

    <SystemReadinessBanner section="settings" test-id="settings-runtime-banner" />

    <!-- 两栏布局: 左侧导航 + 右侧内容 -->
    <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
      <!-- 左侧设置分类导航 -->
      <div class="lg:col-span-1">
        <nav
          class="bg-white rounded-xl border border-border-light shadow-card p-3 space-y-1 sticky top-8"
          data-testid="settings-section-nav"
        >
          <p class="text-xs font-bold text-slate-400 uppercase tracking-wider px-3 py-2">
            {{ t('settings.pageNavigation') }}
          </p>
          <p class="px-3 pb-2 text-xs text-slate-500">
            {{ t('settings.pageNavigationHint') }}
          </p>
          <button
            v-for="item in navigationItems"
            :key="item.id"
            type="button"
            :data-testid="`settings-nav-${item.id}`"
            class="w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors flex items-center gap-2"
            :class="
              activeSection === item.id
                ? 'bg-primary/10 text-primary font-bold'
                : 'text-slate-600 hover:bg-slate-100'
            "
            :aria-current="activeSection === item.id ? 'true' : 'false'"
            @click="handleSectionNavigate(item.id)"
          >
            <span class="material-symbols-outlined text-[18px]">{{ item.icon }}</span>
            {{ item.label }}
          </button>
        </nav>
      </div>

      <!-- 右侧设置内容 -->
      <div class="lg:col-span-3 space-y-6">
        <!-- EDC 数据提取配置 -->
        <div
          id="settings-section-host-connectivity"
          :ref="(element) => setSectionRef('hostConnectivity', element)"
          class="bg-white rounded-xl border border-border-light shadow-card p-6"
          data-testid="settings-host-connectivity-card"
        >
          <div class="flex items-center justify-between mb-6">
            <div>
              <h3 class="text-lg font-bold text-slate-800">
                {{ t('settings.hostManagedConnection') }}
              </h3>
              <p class="text-sm text-slate-500 mt-0.5">
                {{ t('settings.hostManagedConnectionDesc') }}
              </p>
            </div>
            <span
              class="text-xs px-2.5 py-1 rounded-full border font-medium"
              :class="
                hostConnectivity.isConnected
                  ? 'bg-green-50 text-green-700 border-green-200'
                  : 'bg-slate-100 text-slate-600 border-slate-200'
              "
            >
              {{
                hostConnectivity.isConnected ? t('settings.hostOnline') : t('settings.hostOffline')
              }}
            </span>
          </div>

          <div
            class="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 mb-6"
          >
            {{ t('settings.hostManagedConnectionNotice') }}
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="rounded-lg border border-border-light bg-slate-50 px-4 py-3">
              <p class="text-xs font-semibold text-slate-500">
                {{ t('settings.edcBaseUrl') }}
              </p>
              <p class="mt-1 font-mono text-sm text-slate-800 break-all">
                {{ edcSummary.baseUrl || '--' }}
              </p>
            </div>
            <div class="rounded-lg border border-border-light bg-slate-50 px-4 py-3">
              <p class="text-xs font-semibold text-slate-500">
                {{ t('settings.hostMachineName') }}
              </p>
              <p class="mt-1 text-sm text-slate-800">
                {{ hostConnectivity.machineName || '--' }}
              </p>
            </div>
            <div class="rounded-lg border border-border-light bg-slate-50 px-4 py-3">
              <p class="text-xs font-semibold text-slate-500">
                {{ t('settings.hostLastSync') }}
              </p>
              <p class="mt-1 text-sm text-slate-800">
                {{ hostConnectivity.lastSyncLabel || '--' }}
              </p>
            </div>
            <div class="rounded-lg border border-border-light bg-slate-50 px-4 py-3">
              <p class="text-xs font-semibold text-slate-500">
                {{ t('settings.hostSource') }}
              </p>
              <p class="mt-1 text-sm text-slate-800 break-all">
                {{ hostConnectivity.source || '--' }}
              </p>
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
            <div class="rounded-lg border border-border-light bg-white px-4 py-3">
              <p class="text-xs font-semibold text-slate-500">
                {{ t('settings.hostSensorCount') }}
              </p>
              <p class="mt-1 text-lg font-bold text-slate-800">
                {{ hostConnectivity.sensorCount }}
              </p>
            </div>
            <div class="rounded-lg border border-border-light bg-white px-4 py-3">
              <p class="text-xs font-semibold text-slate-500">
                {{ t('settings.hostChannelCount') }}
              </p>
              <p class="mt-1 text-lg font-bold text-slate-800">
                {{ hostConnectivity.channelCount }}
              </p>
            </div>
            <div class="rounded-lg border border-border-light bg-white px-4 py-3">
              <p class="text-xs font-semibold text-slate-500">
                {{ t('settings.hostEnabledChannelCount') }}
              </p>
              <p class="mt-1 text-lg font-bold text-slate-800">
                {{ hostConnectivity.enabledChannelCount }}
              </p>
            </div>
          </div>
        </div>

        <div
          id="settings-section-replay-initialization"
          :ref="(element) => setSectionRef('replayInitialization', element)"
          class="bg-white rounded-xl border border-border-light shadow-card p-6"
          data-testid="settings-replay-initialization-card"
        >
          <div class="flex items-start justify-between gap-4 mb-6">
            <div>
              <h3 class="text-lg font-bold text-slate-800">
                {{ t('settings.replayInitializationTitle') }}
              </h3>
              <p class="text-sm text-slate-500 mt-0.5">
                {{ t('settings.replayInitializationDescription') }}
              </p>
            </div>
            <span
              class="text-xs px-2.5 py-1 rounded-full border border-slate-200 bg-slate-50 text-slate-600"
            >
              {{ t('settings.replayInitializationModeLabel') }}
            </span>
          </div>

          <div
            class="rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-700 mb-6"
          >
            {{ t('settings.replayInitializationNotice') }}
          </div>

          <el-form label-position="top" class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <el-form-item :label="t('settings.replayInitializationStartTime')">
              <el-date-picker
                v-model="replayInitializationForm.startTime"
                type="datetime"
                format="YYYY-MM-DD HH:mm:ss"
                value-format="x"
                class="!w-full"
                :placeholder="t('settings.replayInitializationStartPlaceholder')"
                data-testid="settings-replay-start-time"
              />
            </el-form-item>
            <el-form-item :label="t('settings.replayInitializationPrimaryBaseline')">
              <el-input
                :model-value="replayPrimaryBaselineDisplayLabel"
                class="!w-full"
                :placeholder="t('settings.replayInitializationPrimaryPlaceholder')"
                data-testid="settings-replay-primary-baseline"
                readonly
              />
            </el-form-item>
            <el-form-item
              :label="t('settings.replayInitializationBaselines')"
              class="md:col-span-2"
            >
              <el-select
                v-model="replayInitializationForm.baselineIds"
                multiple
                collapse-tags
                collapse-tags-tooltip
                class="!w-full"
                :placeholder="t('settings.replayInitializationBaselinesPlaceholder')"
                data-testid="settings-replay-baseline-ids"
                @change="handleReplayBaselineSelectionChange"
              >
                <el-option
                  v-for="baseline in replaySelectableBaselineOptions"
                  :key="baseline.id"
                  :label="formatReplayBaselineLabel(baseline)"
                  :value="baseline.id"
                />
              </el-select>
              <div class="mt-1 text-xs text-slate-400">
                {{ t('settings.replayInitializationBaselinesHint') }}
              </div>
            </el-form-item>
          </el-form>

          <div
            v-if="replayInitializationJob"
            class="mt-4 rounded-lg border border-border-light bg-slate-50 px-4 py-3 text-sm text-slate-700"
            data-testid="settings-replay-job-status"
          >
            <div class="flex flex-wrap items-center gap-x-4 gap-y-1">
              <span
                >{{ t('settings.replayInitializationJobId') }}:
                {{ replayInitializationJob.id }}</span
              >
              <span
                >{{ t('settings.replayInitializationJobStatus') }}:
                {{ replayInitializationJob.status }}</span
              >
              <span>
                {{ t('settings.replayInitializationJobProgress') }}:
                {{ replayInitializationJob.generated_heat_count }}
              </span>
            </div>
            <div v-if="replayInitializationJob.error_message" class="mt-2 text-xs text-red-600">
              {{ replayInitializationJob.error_message }}
            </div>
          </div>

          <div class="flex justify-end mt-4">
            <button
              type="button"
              data-testid="settings-replay-submit"
              class="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-dark transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              :disabled="replayInitializationSubmitting"
              @click="submitReplayInitialization"
            >
              {{
                replayInitializationSubmitting
                  ? t('settings.replayInitializationRunning')
                  : t('settings.replayInitializationSubmit')
              }}
            </button>
          </div>
        </div>

        <!-- 偏差阈值 -->
        <div
          id="settings-section-tolerance"
          :ref="(element) => setSectionRef('tolerance', element)"
          class="bg-white rounded-xl border border-border-light shadow-card p-6"
          data-testid="settings-section-tolerance"
        >
          <h3 class="text-lg font-bold text-slate-800 mb-1">
            {{ t('settings.toleranceSectionTitle') }}
          </h3>
          <p class="text-sm text-slate-500 mb-6">
            {{ t('settings.toleranceSectionDescription') }}
          </p>

          <div
            class="bg-slate-50 border border-slate-200 rounded-lg p-4 mb-6 flex items-start gap-3"
          >
            <span class="material-symbols-outlined text-slate-500 text-[20px] mt-0.5">info</span>
            <div>
              <p class="text-sm font-semibold text-slate-700">
                {{ t('settings.unusedSettingTitle') }}
              </p>
              <p class="text-xs text-slate-500 mt-0.5">
                {{ t('settings.unusedSettingDescription') }}
              </p>
            </div>
          </div>

          <el-form label-position="top">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <el-form-item>
                <template #label>
                  <div class="flex items-center gap-2">
                    <span>{{ t('settings.reportTime') }}</span>
                    <span
                      class="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500"
                    >
                      {{ t('settings.unusedSettingBadge') }}
                    </span>
                  </div>
                </template>
                <div class="flex items-center gap-3 w-full">
                  <el-input-number
                    v-model="settingStore.data.reportGenerationHour"
                    :min="0"
                    :max="23"
                    data-testid="settings-report-generation-hour-input"
                  />
                  <button
                    type="button"
                    data-testid="settings-save-report-time"
                    class="px-4 py-1.5 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-dark transition-colors"
                    @click="saveReport"
                  >
                    保存报表时间
                  </button>
                </div>
                <div class="mt-1 text-xs text-slate-400">
                  {{ t('settings.reportTimeUnusedHint') }}
                </div>
              </el-form-item>
              <el-form-item>
                <template #label>
                  <div class="flex items-center gap-2">
                    <span>{{ t('settings.defaultTolerance') }}</span>
                    <span
                      class="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500"
                    >
                      {{ t('settings.unusedSettingBadge') }}
                    </span>
                  </div>
                </template>
                <el-input-number
                  v-model="settingStore.data.defaultTolerancePercent"
                  :min="0"
                  :max="100"
                  data-testid="settings-default-tolerance-input"
                />
                <div class="mt-1 text-xs text-slate-400">
                  {{ t('settings.defaultToleranceUnusedHint') }}
                </div>
              </el-form-item>
            </div>
          </el-form>
          <div class="flex justify-end gap-3 mt-4">
            <button
              type="button"
              data-testid="settings-reset-tolerance"
              class="px-4 py-2 bg-white border border-border-light text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors"
              @click="resetTolerance"
            >
              {{ t('common.cancel') }}
            </button>
            <button
              type="button"
              data-testid="settings-save-tolerance"
              class="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-dark transition-colors"
              @click="saveTolerance"
            >
              保存偏差阈值
            </button>
          </div>
        </div>

        <!-- 切割配置 -->
        <div
          id="settings-section-cutting"
          :ref="(element) => setSectionRef('cutting', element)"
          class="bg-white rounded-xl border border-border-light shadow-card p-6"
          data-testid="settings-section-cutting"
        >
          <h3 class="text-lg font-bold text-slate-800 mb-1">
            {{ t('settings.cuttingConfig') }}
          </h3>
          <p class="text-sm text-slate-500 mb-6">
            {{ t('settings.cuttingConfigDescription') }}
          </p>

          <el-form label-position="top" class="grid grid-cols-1 gap-4 md:grid-cols-2">
            <el-form-item :label="t('settings.cuttingMode')" class="md:col-span-2">
              <el-radio-group
                v-model="settingStore.data.cuttingMode"
                data-testid="settings-cutting-mode-group"
                class="grid grid-cols-1 gap-3 md:grid-cols-2"
              >
                <el-radio
                  v-for="option in cuttingModeOptions"
                  :key="option.value"
                  :value="option.value"
                  :data-testid="option.testId"
                  border
                  class="cutting-mode-card !mr-0"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="flex flex-col items-start gap-1">
                      <span class="text-sm font-semibold text-slate-800">
                        {{ option.label }}
                      </span>
                      <span class="text-xs leading-5 text-slate-500">
                        {{ option.description }}
                      </span>
                    </div>
                    <span
                      class="material-symbols-outlined text-[20px]"
                      :class="
                        settingStore.data.cuttingMode === option.value
                          ? 'text-primary'
                          : 'text-slate-300'
                      "
                    >
                      {{
                        settingStore.data.cuttingMode === option.value
                          ? 'radio_button_checked'
                          : 'radio_button_unchecked'
                      }}
                    </span>
                  </div>
                </el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item
              v-if="settingStore.data.cuttingMode === 'fixed_interval'"
              :label="t('settings.fixedIntervalMinutes')"
            >
              <el-input-number
                v-model="settingStore.data.fixedIntervalMinutes"
                :min="1"
                :max="1440"
                data-testid="settings-fixed-interval-input"
              />
              <div class="mt-1 text-xs text-slate-400">
                {{ t('settings.fixedIntervalHint') }}
              </div>
            </el-form-item>
            <el-form-item :label="t('settings.timeTolerancePercent')">
              <el-input-number
                v-model="settingStore.data.timeTolerancePercent"
                :min="0"
                :max="100"
              />
            </el-form-item>
            <el-form-item :label="t('settings.majorIssueDurationMinutes')">
              <el-input-number
                v-model="settingStore.data.majorIssueDurationMinutes"
                :min="1"
                :max="120"
              />
            </el-form-item>
            <el-form-item :label="t('settings.plantTimezone')">
              <el-select
                v-model="settingStore.data.plantTimezone"
                filterable
                allow-create
                default-first-option
                class="!w-full"
                :placeholder="t('settings.plantTimezonePlaceholder')"
              >
                <el-option
                  v-for="option in timezoneOptions"
                  :key="option"
                  :label="option"
                  :value="option"
                />
              </el-select>
              <div class="mt-1 text-xs text-slate-400">
                {{ t('settings.plantTimezoneHint') }}
              </div>
            </el-form-item>
            <el-form-item :label="t('settings.workStartTime')">
              <el-input v-model="settingStore.data.workStartTime" placeholder="08:00" />
            </el-form-item>
            <el-form-item :label="t('settings.workEndTime')">
              <el-input v-model="settingStore.data.workEndTime" placeholder="18:00" />
            </el-form-item>
            <el-form-item :label="t('settings.breakPeriods')" class="md:col-span-2">
              <el-input
                v-model="settingStore.data.breakPeriods"
                :placeholder="t('settings.breakPeriodsPlaceholder')"
              />
            </el-form-item>
            <el-form-item :label="t('settings.baselineLengthScopeMode')" class="md:col-span-2">
              <el-radio-group v-model="settingStore.data.baselineLengthScopeMode">
                <el-radio-button value="definition">
                  {{ t('settings.scopeDefinition') }}
                </el-radio-button>
                <el-radio-button value="system">
                  {{ t('settings.scopeSystem') }}
                </el-radio-button>
                <el-radio-button value="production_line">
                  {{ t('settings.scopeProductionLine') }}
                </el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-form>
          <div class="flex justify-end mt-4">
            <button
              type="button"
              data-testid="settings-save-cutting"
              class="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-dark transition-colors"
              @click="saveCutting"
            >
              {{ t('common.save') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
:deep(.cutting-mode-card.el-radio.is-bordered) {
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
  border-radius: 1rem;
  border-color: rgb(226 232 240);
  background: rgb(255 255 255);
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background-color 0.2s ease;
}

:deep(.cutting-mode-card.el-radio.is-bordered:hover) {
  border-color: rgb(147 197 253);
}

:deep(.cutting-mode-card .el-radio__input) {
  display: none;
}

:deep(.cutting-mode-card .el-radio__label) {
  display: block;
  width: 100%;
  padding: 1rem 1.125rem;
  white-space: normal;
}

:deep(.cutting-mode-card.is-checked) {
  border-color: rgb(59 130 246);
  background: rgb(239 246 255);
  box-shadow: 0 0 0 3px rgb(219 234 254);
}
</style>
