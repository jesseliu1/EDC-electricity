<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ElButton,
  ElCard,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElRadioButton,
  ElRadioGroup
} from 'element-plus'
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

async function saveCutting() {
  await settingStore.saveCutting()
  ElMessage.success(t('common.success'))
}

onMounted(() => {
  void settingStore.fetchSettings()
})
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold text-gray-900">
      {{ t('settings.title') }}
    </h1>

    <el-card>
      <template #header>
        <span>{{ t('settings.defaultTolerance') }}</span>
      </template>
      <el-form label-position="top">
        <el-form-item :label="t('settings.defaultTolerance')">
          <el-input-number
            v-model="settingStore.data.defaultTolerancePercent"
            :min="0"
            :max="100"
          />
        </el-form-item>
      </el-form>
      <div class="flex justify-end">
        <el-button
          type="primary"
          @click="saveTolerance"
        >
          {{ t('common.save') }}
        </el-button>
      </div>
    </el-card>

    <el-card>
      <template #header>
        <span>{{ t('settings.edcConnection') }}</span>
      </template>
      <el-form label-position="top">
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
      </el-form>
      <div class="flex justify-end gap-2">
        <el-button @click="testEdc">
          {{ t('settings.testConnection') }}
        </el-button>
        <el-button
          type="primary"
          @click="saveEdc"
        >
          {{ t('common.save') }}
        </el-button>
      </div>
    </el-card>

    <el-card>
      <template #header>
        <span>{{ t('settings.reportTime') }}</span>
      </template>
      <el-form label-position="top">
        <el-form-item :label="t('settings.reportTime')">
          <el-input-number
            v-model="settingStore.data.reportGenerationHour"
            :min="0"
            :max="23"
          />
        </el-form-item>
      </el-form>
      <div class="flex justify-end">
        <el-button
          type="primary"
          @click="saveReport"
        >
          {{ t('common.save') }}
        </el-button>
      </div>
    </el-card>

    <el-card>
      <template #header>
        <span>{{ t('settings.cuttingConfig') }}</span>
      </template>
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
      <div class="flex justify-end">
        <el-button type="primary" @click="saveCutting">
          {{ t('common.save') }}
        </el-button>
      </div>
    </el-card>
  </div>
</template>
