<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElDialog } from 'element-plus'
import PageHeader from '@/components/common/PageHeader.vue'
import BaselineCard from '@/components/baseline/BaselineCard.vue'
import BaselineWizard from '@/components/baseline/BaselineWizard.vue'
import { useBaselineStore } from '@/stores/baseline'
import type { BaselineStatus } from '@/api/baseline'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const baselineStore = useBaselineStore()
const wizardVisible = ref(false)
const wizardPrefill = ref<{
  sourceHeatId?: string
  selectedStartTime?: string
  selectedEndTime?: string
  name?: string
} | null>(null)

type BaselineFilter = 'all' | BaselineStatus

const filters: { key: BaselineFilter; label: string }[] = [
  { key: 'all', label: '全部范围' },
  { key: 'published', label: '已发布' },
  { key: 'draft', label: '草稿' },
  { key: 'disabled', label: '已停用' },
]

async function handleFilterChange(filter: BaselineFilter) {
  await baselineStore.setFilter(filter)
}

function handleCreate() {
  wizardPrefill.value = null
  wizardVisible.value = true
}

function getQueryStringValue(value: unknown): string {
  if (typeof value === 'string') return value
  if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
  return ''
}

function handlePrefillFromRoute() {
  const sourceHeatId = getQueryStringValue(route.query.sourceHeatId)
  if (!sourceHeatId) return

  const selectedStartTime = getQueryStringValue(route.query.selectedStartTime)
  const selectedEndTime = getQueryStringValue(route.query.selectedEndTime)
  const name = getQueryStringValue(route.query.name)

  wizardPrefill.value = {
    sourceHeatId,
    selectedStartTime,
    selectedEndTime,
    name,
  }
  wizardVisible.value = true
  void router.replace({ path: '/baselines' })
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
  definitionId: string
  sourceHeatId: string
  selectedStartTime?: string
  selectedEndTime?: string
  tolerancePercent: number
  mode: 'draft' | 'publish'
}) {
  await baselineStore.createBaseline(
    {
      name: payload.name,
      description: payload.description,
      definition_id: payload.definitionId,
      source_heat_id: payload.sourceHeatId,
      selected_start_time: payload.selectedStartTime,
      selected_end_time: payload.selectedEndTime,
      tolerance_percent: payload.tolerancePercent,
    },
    payload.mode
  )
  wizardVisible.value = false
  ElMessage.success(
    payload.mode === 'publish'
      ? t('baseline.publishSuccess')
      : t('baseline.saveDraftSuccess')
  )
}

onMounted(() => {
  baselineStore.fetchList()
  handlePrefillFromRoute()
})
</script>

<template>
  <div class="flex flex-col gap-6">
    <!-- 页面头部 -->
    <PageHeader
      :title="t('baseline.title')"
      subtitle="Baseline Library"
      description="沉淀与管理经过专家验证的最佳熔炼曲线，作为系统偏差分析的对比基准。"
    >
      <template #actions>
        <button
          class="flex items-center gap-2 bg-white border border-border-light text-slate-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors"
        >
          <span class="material-symbols-outlined text-[18px]">sync</span>
          刷新数据
        </button>
        <button
          class="flex items-center gap-2 bg-white border border-border-light text-slate-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors"
        >
          <span class="material-symbols-outlined text-[18px]">download</span>
          导出
        </button>
        <button
          data-testid="baseline-create-button"
          class="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary-dark transition-colors"
          @click="handleCreate"
        >
          <span class="material-symbols-outlined text-[18px]">add</span>
          {{ t('baseline.createBaseline') }}
        </button>
      </template>
    </PageHeader>

    <!-- 筛选区 -->
    <div
      class="bg-white rounded-xl border border-border-light shadow-card p-5"
    >
      <div class="flex items-center gap-6">
        <span
          class="material-symbols-outlined text-slate-400 text-[20px]"
        >filter_list</span>
        <span class="text-sm text-slate-500 font-medium">基线列表</span>
        <span class="text-xs text-slate-400">共 {{ baselineStore.filteredList.length }} 条记录</span>
        <div class="flex-1" />
        <!-- 筛选按钮组 -->
        <div class="flex bg-slate-100 p-1 rounded-lg">
          <button
            v-for="f in filters"
            :key="f.key"
            :class="[
              'px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200',
              baselineStore.currentFilter === f.key
                ? 'bg-white text-primary shadow-sm font-bold'
                : 'text-slate-500 hover:text-slate-700',
            ]"
            @click="handleFilterChange(f.key)"
          >
            {{ f.label }}
          </button>
        </div>
        <!-- 搜索 -->
        <div
          class="flex items-center bg-slate-100 rounded-lg px-3 py-1.5 w-48 border border-transparent focus-within:border-primary/30 transition-all"
        >
          <span
            class="material-symbols-outlined text-slate-400 text-[18px]"
          >search</span>
          <input
            type="text"
            class="bg-transparent border-none focus:ring-0 focus:outline-none text-sm text-slate-700 w-full placeholder:text-slate-400 ml-2 p-0"
            placeholder="搜索名称..."
          >
        </div>
      </div>
    </div>

    <!-- 基线卡片列表 -->
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

    <!-- 空状态 -->
    <div
      v-else
      class="rounded-xl border border-dashed border-border-light bg-white py-16 flex flex-col items-center justify-center"
    >
      <span class="material-symbols-outlined text-slate-300 text-5xl">library_books</span>
      <p class="text-sm text-slate-400 mt-3">
        {{ t('common.noData') }}
      </p>
    </div>

    <!-- 创建基线对话框 -->
    <ElDialog
      v-model="wizardVisible"
      :title="t('baseline.createBaseline')"
      width="900px"
      destroy-on-close
      append-to-body
      data-testid="baseline-wizard-dialog"
    >
      <BaselineWizard
        :initial-source-heat-id="wizardPrefill?.sourceHeatId"
        :initial-selected-start-time="wizardPrefill?.selectedStartTime"
        :initial-selected-end-time="wizardPrefill?.selectedEndTime"
        :initial-name="wizardPrefill?.name"
        @cancel="wizardVisible = false"
        @submit="handleWizardSubmit"
      />
    </ElDialog>
  </div>
</template>
