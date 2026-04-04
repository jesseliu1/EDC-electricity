<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, type ComponentPublicInstance } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElOption,
  ElRadioButton,
  ElRadioGroup,
  ElSelect,
} from 'element-plus'
import PageHeader from '@/components/common/PageHeader.vue'
import SystemReadinessBanner from '@/components/common/SystemReadinessBanner.vue'
import { useRuntimeStatusStore } from '@/stores/runtimeStatus'
import { useSettingStore } from '@/stores/setting'

const { t } = useI18n()
const settingStore = useSettingStore()
const runtimeStatusStore = useRuntimeStatusStore()

const hostConnectivity = computed(() => runtimeStatusStore.data.host)
const edcSummary = computed(() => runtimeStatusStore.data.edc)
const pageRef = ref<HTMLElement | null>(null)
type SettingsSectionId = 'hostConnectivity' | 'tolerance' | 'cutting'

const activeSection = ref<SettingsSectionId>('hostConnectivity')
const scrollContainer = ref<HTMLElement | null>(null)
const sectionRefs: Record<SettingsSectionId, HTMLElement | null> = {
  hostConnectivity: null,
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
    .filter(
      (item): item is { id: SettingsSectionId; distance: number } => item !== null
    )

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
  await settingStore.fetchSettings()
  await nextTick()
  syncActiveSection()
})

onBeforeUnmount(() => {
  scrollContainer.value?.removeEventListener('scroll', handleViewportChange)
  window.removeEventListener('resize', handleViewportChange)
})
</script>

<template>
  <div
    ref="pageRef"
    class="flex flex-col gap-6"
    data-testid="settings-page"
  >
    <!-- 页面头部 -->
    <PageHeader
      :title="t('settings.title')"
      :subtitle="t('settings.subtitle')"
    />

    <SystemReadinessBanner
      section="settings"
      test-id="settings-runtime-banner"
    />

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
                hostConnectivity.isConnected
                  ? t('settings.hostOnline')
                  : t('settings.hostOffline')
              }}
            </span>
          </div>

          <div class="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 mb-6">
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

          <!-- 警告提示 -->
          <div class="bg-orange-50 border border-orange-200 rounded-lg p-4 mb-6 flex items-start gap-3">
            <span class="material-symbols-outlined text-orange-500 text-[20px] mt-0.5">info</span>
            <div>
              <p class="text-sm font-semibold text-orange-700">
                {{ t('settings.impactWarningTitle') }}
              </p>
              <p class="text-xs text-orange-600 mt-0.5">
                收紧阈值可能导致过渡态下出现更多的误报。
              </p>
            </div>
          </div>

          <el-form label-position="top">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <el-form-item :label="t('settings.reportTime')">
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
              </el-form-item>
              <el-form-item :label="t('settings.defaultTolerance')">
                <el-input-number
                  v-model="settingStore.data.defaultTolerancePercent"
                  :min="0"
                  :max="100"
                  data-testid="settings-default-tolerance-input"
                />
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

          <el-form
            label-position="top"
            class="grid grid-cols-1 gap-4 md:grid-cols-2"
          >
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
              <el-input
                v-model="settingStore.data.workStartTime"
                placeholder="08:00"
              />
            </el-form-item>
            <el-form-item :label="t('settings.workEndTime')">
              <el-input
                v-model="settingStore.data.workEndTime"
                placeholder="18:00"
              />
            </el-form-item>
            <el-form-item
              :label="t('settings.breakPeriods')"
              class="md:col-span-2"
            >
              <el-input
                v-model="settingStore.data.breakPeriods"
                :placeholder="t('settings.breakPeriodsPlaceholder')"
              />
            </el-form-item>
            <el-form-item
              :label="t('settings.baselineLengthScopeMode')"
              class="md:col-span-2"
            >
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
