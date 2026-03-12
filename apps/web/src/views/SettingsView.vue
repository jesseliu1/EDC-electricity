<script setup lang="ts">
import { onMounted } from 'vue'
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
import { useSettingStore } from '@/stores/setting'

const { t } = useI18n()
const settingStore = useSettingStore()

async function saveTolerance() {
  await settingStore.saveTolerance()
  ElMessage.success(t('common.success'))
}

async function saveEdc() {
  await settingStore.saveEdc()
  ElMessage.success(t('common.success'))
}

async function testEdc() {
  await settingStore.testEdc()
  ElMessage.success(t('settings.edcTestSuccess'))
}

async function saveReport() {
  await settingStore.saveReport()
  ElMessage.success(t('common.success'))
}

/* eslint-disable @typescript-eslint/no-unused-vars -- saveReport 在模板中通过 tolerance 区域调用 */

async function saveCutting() {
  await settingStore.saveCutting()
  ElMessage.success(t('common.success'))
}

onMounted(() => {
  void settingStore.fetchSettings()
})
</script>

<template>
  <div class="flex flex-col gap-6">
    <!-- 页面头部 -->
    <PageHeader
      :title="t('settings.title')"
      subtitle="System Configuration"
    />

    <!-- 两栏布局: 左侧导航 + 右侧内容 -->
    <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
      <!-- 左侧设置分类导航 -->
      <div class="lg:col-span-1">
        <nav class="bg-white rounded-xl border border-border-light shadow-card p-3 space-y-1 sticky top-8">
          <p class="text-xs font-bold text-slate-400 uppercase tracking-wider px-3 py-2">全局设置</p>
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
          <p class="text-xs font-bold text-slate-400 uppercase tracking-wider px-3 py-2">系统</p>
          <button class="w-full text-left px-3 py-2.5 rounded-lg text-slate-600 text-sm hover:bg-slate-100 transition-colors flex items-center gap-2">
            <span class="material-symbols-outlined text-[18px]">group</span>
            用户管理
          </button>
        </nav>
      </div>

      <!-- 右侧设置内容 -->
      <div class="lg:col-span-3 space-y-6">
        <!-- EDC 数据提取配置 -->
        <div class="bg-white rounded-xl border border-border-light shadow-card p-6">
          <div class="flex items-center justify-between mb-6">
            <div>
              <h3 class="text-lg font-bold text-slate-800">EDC 数据提取</h3>
              <p class="text-sm text-slate-500 mt-0.5">
                配置工程数据采集系统的连接参数
              </p>
            </div>
            <span class="text-xs px-2.5 py-1 rounded-full bg-green-50 text-green-700 border border-green-200 font-medium">Active</span>
          </div>
          <el-form label-position="top">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <el-form-item :label="t('settings.edcBaseUrl')">
                <el-input v-model="settingStore.data.edcBaseUrl" />
              </el-form-item>
              <el-form-item :label="t('settings.edcApiKey')">
                <el-input
                  v-model="settingStore.data.edcApiKey"
                  type="password"
                  show-password
                />
              </el-form-item>
            </div>
          </el-form>
          <div class="flex justify-end gap-3 mt-4">
            <button
              class="px-4 py-2 bg-white border border-border-light text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors"
              @click="testEdc"
            >
              {{ t('settings.testConnection') }}
            </button>
            <button
              class="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-dark transition-colors"
              @click="saveEdc"
            >
              {{ t('common.save') }}
            </button>
          </div>
        </div>

        <!-- 偏差阈值 -->
        <div class="bg-white rounded-xl border border-border-light shadow-card p-6">
          <h3 class="text-lg font-bold text-slate-800 mb-1">偏差阈值</h3>
          <p class="text-sm text-slate-500 mb-6">设置黄金基线对比的敏感度</p>

          <!-- 警告提示 -->
          <div class="bg-orange-50 border border-orange-200 rounded-lg p-4 mb-6 flex items-start gap-3">
            <span class="material-symbols-outlined text-orange-500 text-[20px] mt-0.5">info</span>
            <div>
              <p class="text-sm font-semibold text-orange-700">Impact Warning</p>
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
              class="px-4 py-2 bg-white border border-border-light text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors"
            >
              取消修改
            </button>
            <button
              class="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-dark transition-colors"
              @click="saveTolerance"
            >
              保存偏差阈值
            </button>
          </div>
        </div>

        <!-- 切割配置 -->
        <div class="bg-white rounded-xl border border-border-light shadow-card p-6">
          <h3 class="text-lg font-bold text-slate-800 mb-1">{{ t('settings.cuttingConfig') }}</h3>
          <p class="text-sm text-slate-500 mb-6">配置生产切割和排班相关参数</p>

          <el-form label-position="top" class="grid grid-cols-1 gap-4 md:grid-cols-2">
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
                <el-radio-button label="definition">{{ t('settings.scopeDefinition') }}</el-radio-button>
                <el-radio-button label="system">{{ t('settings.scopeSystem') }}</el-radio-button>
                <el-radio-button label="production_line">{{ t('settings.scopeProductionLine') }}</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-form>
          <div class="flex justify-end mt-4">
            <button
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
