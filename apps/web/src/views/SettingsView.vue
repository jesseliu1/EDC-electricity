<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElButton, ElCard, ElForm, ElFormItem, ElInput, ElInputNumber, ElMessage } from 'element-plus'
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
  </div>
</template>
