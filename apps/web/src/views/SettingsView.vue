<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElRadioButton,
  ElRadioGroup,
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

onMounted(() => {
  void settingStore.fetchSettings()
})
</script>

<template>
  <div
    class="flex flex-col gap-6"
    data-testid="settings-page"
  >
    <!-- 页面头部 -->
    <PageHeader
      :title="t('settings.title')"
      subtitle="System Configuration"
    />

    <SystemReadinessBanner
      section="settings"
      test-id="settings-runtime-banner"
    />

    <!-- 两栏布局: 左侧导航 + 右侧内容 -->
    <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
      <!-- 左侧设置分类导航 -->
      <div class="lg:col-span-1">
        <nav class="bg-white rounded-xl border border-border-light shadow-card p-3 space-y-1 sticky top-8">
          <p class="text-xs font-bold text-slate-400 uppercase tracking-wider px-3 py-2">
            全局设置
          </p>
          <button class="w-full text-left px-3 py-2.5 rounded-lg bg-primary/10 text-primary text-sm font-bold flex items-center gap-2">
            <span class="material-symbols-outlined text-[18px]">database</span>
            EDC 配置
          </button>
          <button class="w-full text-left px-3 py-2.5 rounded-lg text-slate-600 text-sm hover:bg-slate-100 transition-colors flex items-center gap-2">
            <span class="material-symbols-outlined text-[18px]">tune</span>
            阈值设置
          </button>
          <button class="w-full text-left px-3 py-2.5 rounded-lg text-slate-600 text-sm hover:bg-slate-100 transition-colors flex items-center gap-2">
            <span class="material-symbols-outlined text-[18px]">notifications</span>
            通知管理
          </button>
          <div class="h-px bg-border-light mx-2 my-2" />
          <p class="text-xs font-bold text-slate-400 uppercase tracking-wider px-3 py-2">
            系统
          </p>
          <button class="w-full text-left px-3 py-2.5 rounded-lg text-slate-600 text-sm hover:bg-slate-100 transition-colors flex items-center gap-2">
            <span class="material-symbols-outlined text-[18px]">group</span>
            用户管理
          </button>
        </nav>
      </div>

      <!-- 右侧设置内容 -->
      <div class="lg:col-span-3 space-y-6">
        <!-- EDC 数据提取配置 -->
        <div
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
                {{ edcSummary.baseUrl || settingStore.data.edcBaseUrl || '--' }}
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
        <div class="bg-white rounded-xl border border-border-light shadow-card p-6">
          <h3 class="text-lg font-bold text-slate-800 mb-1">
            偏差阈值
          </h3>
          <p class="text-sm text-slate-500 mb-6">
            设置黄金基线对比的敏感度
          </p>

          <!-- 警告提示 -->
          <div class="bg-orange-50 border border-orange-200 rounded-lg p-4 mb-6 flex items-start gap-3">
            <span class="material-symbols-outlined text-orange-500 text-[20px] mt-0.5">info</span>
            <div>
              <p class="text-sm font-semibold text-orange-700">
                Impact Warning
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
                />
              </el-form-item>
            </div>
          </el-form>
          <div class="flex justify-end gap-3 mt-4">
            <button
              type="button"
              class="px-4 py-2 bg-white border border-border-light text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors"
            >
              取消修改
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
        <div class="bg-white rounded-xl border border-border-light shadow-card p-6">
          <h3 class="text-lg font-bold text-slate-800 mb-1">
            {{ t('settings.cuttingConfig') }}
          </h3>
          <p class="text-sm text-slate-500 mb-6">
            配置生产切割和排班相关参数
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
