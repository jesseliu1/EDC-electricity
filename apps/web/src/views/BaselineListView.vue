<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ElButton, ElRadioGroup, ElRadioButton, ElEmpty, ElMessage, ElDialog } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import BaselineCard from '@/components/baseline/BaselineCard.vue'
import BaselineWizard from '@/components/baseline/BaselineWizard.vue'
import { useBaselineStore } from '@/stores/baseline'
import type { BaselineStatus } from '@/api/baseline'

const { t } = useI18n()
const router = useRouter()
const baselineStore = useBaselineStore()
const wizardVisible = ref(false)

type BaselineFilter = 'all' | BaselineStatus

async function handleFilterChange(value: string | number | boolean) {
  const filter = value as BaselineFilter
  await baselineStore.setFilter(filter)
}

function handleCreate() {
  wizardVisible.value = true
}

function handleEdit(id: string) {
  router.push(`/baselines/${id}`)
}

async function handleDelete(id: string) {
  await baselineStore.deleteBaseline(id)
  ElMessage.success(t('baseline.deleteSuccess'))
}

async function handlePublish(id: string) {
  await baselineStore.publishBaseline(id)
  ElMessage.success(t('baseline.publishSuccess'))
}

async function handleDisable(id: string) {
  await baselineStore.disableBaseline(id)
  ElMessage.success(t('baseline.disableSuccess'))
}

async function handleWizardSubmit(payload: {
  name: string
  description: string
  sourceHeatId: string
  tolerancePercent: number
  mode: 'draft' | 'publish'
}) {
  await baselineStore.createBaseline(
    {
      name: payload.name,
      description: payload.description,
      source_heat_id: payload.sourceHeatId,
      tolerance_percent: payload.tolerancePercent
    },
    payload.mode
  )
  wizardVisible.value = false
  ElMessage.success(
    payload.mode === 'publish' ? t('baseline.publishSuccess') : t('baseline.saveDraftSuccess')
  )
}

onMounted(() => {
  baselineStore.fetchList()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-gray-900">
        {{ t('baseline.title') }}
      </h1>
      <el-button
        type="primary"
        :icon="Plus"
        @click="handleCreate"
      >
        {{ t('baseline.createBaseline') }}
      </el-button>
    </div>

    <div class="rounded-xl border border-gray-200 bg-white p-4">
      <div class="flex items-center justify-between gap-4 flex-wrap">
        <div class="text-sm text-gray-500">
          {{ t('baseline.status') }}
        </div>
        <el-radio-group
          :model-value="baselineStore.currentFilter"
          @change="handleFilterChange"
        >
          <el-radio-button label="all">
            {{ t('common.viewAll') }}
          </el-radio-button>
          <el-radio-button label="published">
            {{ t('baseline.statusPublished') }}
          </el-radio-button>
          <el-radio-button label="draft">
            {{ t('baseline.statusDraft') }}
          </el-radio-button>
          <el-radio-button label="disabled">
            {{ t('baseline.statusDisabled') }}
          </el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <div
      v-if="baselineStore.filteredList.length > 0"
      class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
    >
      <BaselineCard
        v-for="baseline in baselineStore.filteredList"
        :key="baseline.id"
        :baseline="baseline"
        @edit="handleEdit"
        @delete="handleDelete"
        @publish="handlePublish"
        @disable="handleDisable"
      />
    </div>

    <div
      v-else
      class="rounded-xl border border-dashed border-gray-300 bg-white py-16"
    >
      <el-empty :description="t('common.noData')" />
    </div>

    <ElDialog
      v-model="wizardVisible"
      :title="t('baseline.createBaseline')"
      width="900px"
      destroy-on-close
      append-to-body
    >
      <BaselineWizard
        @cancel="wizardVisible = false"
        @submit="handleWizardSubmit"
      />
    </ElDialog>
  </div>
</template>
