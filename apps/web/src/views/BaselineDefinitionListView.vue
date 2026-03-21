<script setup lang="ts">
import { onMounted, ref, reactive, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ElButton,
  ElRadioGroup,
  ElRadioButton,
  ElEmpty,
  ElMessage,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElTag,
  ElPopconfirm,
  ElColorPicker,
  ElCard,
  ElDescriptions,
  ElDescriptionsItem,
  ElMessageBox,
  ElSelect,
  ElOption,
  ElOptionGroup
} from 'element-plus'
import { Plus, Delete, Edit, CircleClose, CircleCheck } from '@element-plus/icons-vue'
import SystemReadinessBanner from '@/components/common/SystemReadinessBanner.vue'
import { useBaselineDefinitionStore } from '@/stores/baselineDefinition'
import type { MetricItem } from '@/stores/baselineDefinition'
import type { MetricDefinitionCreate } from '@/api/baselineDefinition'
import { settingApi, type HostChannelItemResponse } from '@/api/setting'

const { t } = useI18n()
const store = useBaselineDefinitionStore()

// 状态筛选
type StatusFilter = 'all' | 'active' | 'disabled'
const currentFilter = ref<StatusFilter>('all')

const filteredList = computed(() => {
  if (currentFilter.value === 'all') return store.list
  return store.list.filter(d => d.status === currentFilter.value)
})

async function handleFilterChange(value: string | number | boolean | undefined) {
  if (value === undefined) return
  currentFilter.value = value as StatusFilter
}

// 新建/编辑 定义 对话框
const dialogVisible = ref(false)
const editingId = ref<string | null>(null)
const dialogTitle = computed(() =>
  editingId.value
    ? t('baselineDefinition.editDefinition')
    : t('baselineDefinition.createDefinition')
)

interface DefinitionForm {
  definitionName: string
  description: string
  expectedDurationMinutes: number
}

const definitionForm = reactive<DefinitionForm>({
  definitionName: '',
  description: '',
  expectedDurationMinutes: 30
})

// 新建指标表单
const newMetricForm = reactive<MetricDefinitionCreate>({
  name: '',
  unit: '',
  color: '#409EFF',
  edc_channel_id: null
})

// 编辑指标
const editingMetricId = ref<string | null>(null)
const editMetricForm = reactive<MetricDefinitionCreate>({
  name: '',
  unit: '',
  color: '#409EFF',
  edc_channel_id: null
})

// 当前管理指标的定义
const metricDialogVisible = ref(false)
const metricDefinitionId = ref<string | null>(null)
const hostChannels = ref<HostChannelItemResponse[]>([])
const hostChannelsLoading = ref(false)
const hostChannelsLoaded = ref(false)

const metricDefinitionItem = computed(() => {
  if (!metricDefinitionId.value) return null
  return store.list.find(d => d.id === metricDefinitionId.value) || null
})

const hostChannelMap = computed(() => {
  return new Map(hostChannels.value.map(item => [item.id, item]))
})

const hostChannelGroups = computed(() => {
  const groups = new Map<
    string,
    { label: string; area: string; options: HostChannelItemResponse[] }
  >()

  hostChannels.value.forEach(item => {
    if (!groups.has(item.device_name)) {
      groups.set(item.device_name, {
        label: item.device_name,
        area: item.area,
        options: []
      })
    }
    groups.get(item.device_name)?.options.push(item)
  })

  return Array.from(groups.values())
})

function resetForm() {
  definitionForm.definitionName = ''
  definitionForm.description = ''
  definitionForm.expectedDurationMinutes = 30
  editingId.value = null
}

function handleCreate() {
  resetForm()
  dialogVisible.value = true
}

function handleEdit(item: { id: string; definitionName: string; description: string | null; expectedDurationMinutes: number }) {
  editingId.value = item.id
  definitionForm.definitionName = item.definitionName
  definitionForm.description = item.description || ''
  definitionForm.expectedDurationMinutes = item.expectedDurationMinutes
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!definitionForm.definitionName.trim()) {
    ElMessage.warning(t('baselineDefinition.nameRequired'))
    return
  }
  try {
    if (editingId.value) {
      await store.updateDefinition(editingId.value, {
        definition_name: definitionForm.definitionName.trim(),
        description: definitionForm.description.trim() || null,
        expected_duration_minutes: definitionForm.expectedDurationMinutes
      })
      ElMessage.success(t('baselineDefinition.updateSuccess'))
    } else {
      await store.createDefinition({
        definition_name: definitionForm.definitionName.trim(),
        description: definitionForm.description.trim() || null,
        expected_duration_minutes: definitionForm.expectedDurationMinutes
      })
      ElMessage.success(t('baselineDefinition.createSuccess'))
    }
    dialogVisible.value = false
  } catch {
    ElMessage.error(t('common.error'))
  }
}

async function handleDelete(id: string) {
  try {
    await store.deleteDefinition(id)
    ElMessage.success(t('baselineDefinition.deleteSuccess'))
  } catch {
    ElMessage.error(t('common.error'))
  }
}

async function handleDisable(id: string) {
  try {
    await store.disableDefinition(id)
    ElMessage.success(t('baselineDefinition.disableSuccess'))
  } catch {
    ElMessage.error(t('common.error'))
  }
}

async function handleEnable(id: string) {
  try {
    await store.enableDefinition(id)
    ElMessage.success(t('baselineDefinition.enableSuccess'))
  } catch {
    ElMessage.error(t('common.error'))
  }
}

// 指标管理
function openMetricManager(definitionId: string) {
  metricDefinitionId.value = definitionId
  resetNewMetricForm()
  editingMetricId.value = null
  metricDialogVisible.value = true
  void ensureHostChannels()
}

function resetNewMetricForm() {
  newMetricForm.name = ''
  newMetricForm.unit = ''
  newMetricForm.color = '#409EFF'
  newMetricForm.edc_channel_id = null
}

async function ensureHostChannels() {
  if (hostChannelsLoaded.value || hostChannelsLoading.value) return
  hostChannelsLoading.value = true
  try {
    const data = await settingApi.getHostChannels()
    hostChannels.value = data.items
    hostChannelsLoaded.value = true
  } catch {
    ElMessage.error(t('baselineDefinition.hostChannelsLoadFailed'))
  } finally {
    hostChannelsLoading.value = false
  }
}

function applySourceChannelDefaults(
  channelId: string | null | undefined,
  form: MetricDefinitionCreate
) {
  form.edc_channel_id = channelId || null
  if (!channelId) return

  const channel = hostChannelMap.value.get(channelId)
  if (!channel) return

  form.name = channel.channel_name
  form.unit = channel.unit
}

function formatHostChannelLabel(channel: HostChannelItemResponse) {
  return `${channel.channel_name} · ${channel.unit || '--'}`
}

function getMetricBoundCount(metrics: MetricItem[]) {
  return metrics.filter(metric => Boolean(metric.edcChannelId)).length
}

function getSelectableHostChannelGroups(currentMetricId?: string | null) {
  const currentMetric = currentMetricId
    ? metricDefinitionItem.value?.metrics.find(metric => metric.id === currentMetricId)
    : null
  const currentChannelId = currentMetric?.edcChannelId ?? null
  const usedIds = new Set(
    (metricDefinitionItem.value?.metrics || [])
      .filter(metric => metric.id !== currentMetricId)
      .map(metric => metric.edcChannelId)
      .filter((channelId): channelId is string => Boolean(channelId))
  )

  return hostChannelGroups.value
    .map(group => ({
      ...group,
      options: group.options.filter(
        channel => !usedIds.has(channel.id) || channel.id === currentChannelId
      )
    }))
    .filter(group => group.options.length > 0)
}

function resolveHostChannelSummary(channelId: string | null) {
  if (!channelId) return ''
  const channel = hostChannelMap.value.get(channelId)
  if (!channel) return channelId
  return `${channel.device_name} / ${channel.channel_name} / ${channel.unit || '--'}`
}

async function handleAddMetric() {
  if (!metricDefinitionId.value) return
  if (!newMetricForm.name.trim() || !newMetricForm.unit.trim()) {
    ElMessage.warning(t('baselineDefinition.metricFieldRequired'))
    return
  }
  try {
    await store.addMetric(metricDefinitionId.value, {
      name: newMetricForm.name.trim(),
      unit: newMetricForm.unit.trim(),
      color: newMetricForm.color,
      edc_channel_id: newMetricForm.edc_channel_id
    })
    resetNewMetricForm()
    ElMessage.success(t('baselineDefinition.metricAddSuccess'))
  } catch {
    ElMessage.error(t('common.error'))
  }
}

function startEditMetric(metric: MetricItem) {
  editingMetricId.value = metric.id
  editMetricForm.name = metric.name
  editMetricForm.unit = metric.unit
  editMetricForm.color = metric.color
  editMetricForm.edc_channel_id = metric.edcChannelId
  void ensureHostChannels()
}

function cancelEditMetric() {
  editingMetricId.value = null
  editMetricForm.edc_channel_id = null
}

async function saveEditMetric() {
  if (!metricDefinitionId.value || !editingMetricId.value) return
  if (!editMetricForm.name.trim() || !editMetricForm.unit.trim()) {
    ElMessage.warning(t('baselineDefinition.metricFieldRequired'))
    return
  }
  try {
    await store.updateMetric(metricDefinitionId.value, editingMetricId.value, {
      name: editMetricForm.name.trim(),
      unit: editMetricForm.unit.trim(),
      color: editMetricForm.color,
      edc_channel_id: editMetricForm.edc_channel_id
    })
    editingMetricId.value = null
    ElMessage.success(t('baselineDefinition.metricUpdateSuccess'))
  } catch {
    ElMessage.error(t('common.error'))
  }
}

async function handleRemoveMetric(metricId: string) {
  if (!metricDefinitionId.value) return
  try {
    await ElMessageBox.confirm(
      t('baselineDefinition.metricDeleteConfirm'),
      t('common.warning'),
      { type: 'warning' }
    )
    await store.removeMetric(metricDefinitionId.value, metricId)
    ElMessage.success(t('baselineDefinition.metricDeleteSuccess'))
  } catch {
    // 用户取消确认
  }
}

// 状态颜色映射
function statusType(status: string): 'success' | 'info' {
  return status === 'active' ? 'success' : 'info'
}

function statusLabel(status: string): string {
  return status === 'active'
    ? t('baselineDefinition.statusActive')
    : t('baselineDefinition.statusDisabled')
}

onMounted(() => {
  store.fetchList()
})
</script>

<template>
  <div
    class="space-y-6"
    data-testid="baseline-definition-page"
  >
    <!-- 标题栏 -->
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-gray-900">
        {{ t('baselineDefinition.title') }}
      </h1>
      <el-button
        type="primary"
        :icon="Plus"
        data-testid="baseline-definition-create-button"
        @click="handleCreate"
      >
        {{ t('baselineDefinition.createDefinition') }}
      </el-button>
    </div>

    <SystemReadinessBanner
      section="baselines"
      test-id="baseline-definition-runtime-banner"
    />

    <!-- 筛选栏 -->
    <div class="rounded-xl border border-gray-200 bg-white p-4">
      <div class="flex items-center justify-between gap-4 flex-wrap">
        <div class="text-sm text-gray-500">
          {{ t('baselineDefinition.status') }}
        </div>
        <el-radio-group
          :model-value="currentFilter"
          @change="handleFilterChange"
        >
          <el-radio-button label="all">
            {{ t('common.viewAll') }}
          </el-radio-button>
          <el-radio-button label="active">
            {{ t('baselineDefinition.statusActive') }}
          </el-radio-button>
          <el-radio-button label="disabled">
            {{ t('baselineDefinition.statusDisabled') }}
          </el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <!-- 定义卡片列表 -->
    <div
      v-if="filteredList.length > 0"
      class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
    >
      <el-card
        v-for="item in filteredList"
        :key="item.id"
        shadow="hover"
        class="relative"
        :data-testid="`baseline-definition-card-${item.id}`"
      >
        <template #header>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2 min-w-0">
              <span class="font-semibold text-gray-900 truncate">
                {{ item.definitionName }}
              </span>
              <el-tag
                :type="statusType(item.status)"
                size="small"
              >
                {{ statusLabel(item.status) }}
              </el-tag>
            </div>
          </div>
        </template>

        <!-- 描述 -->
        <p class="text-sm text-gray-500 mb-3 line-clamp-2">
          {{ item.description || t('common.noDescription') }}
        </p>

        <!-- 基本信息 -->
        <el-descriptions
          :column="1"
          size="small"
          border
        >
          <el-descriptions-item :label="t('baselineDefinition.expectedDuration')">
            {{ item.expectedDurationMinutes }} {{ t('baselineDefinition.minutes') }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('baselineDefinition.metricCount')">
            {{ item.metrics.length }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('baselineDefinition.boundChannelCount')">
            {{ getMetricBoundCount(item.metrics) }}/{{ item.metrics.length }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('baselineDefinition.instanceCount')">
            {{ item.instanceCount }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- 指标标签 -->
        <div class="mt-3 flex flex-wrap gap-1.5">
          <el-tag
            v-for="metric in item.metrics"
            :key="metric.id"
            size="small"
            :color="metric.color + '20'"
            :style="{ color: metric.color, borderColor: metric.color + '40' }"
          >
            {{ metric.name }} ({{ metric.unit }})
          </el-tag>
        </div>

        <!-- 操作按钮 -->
        <div class="mt-4 flex items-center gap-2 border-t border-gray-100 pt-3">
          <el-button
            size="small"
            :icon="Edit"
            @click="handleEdit(item)"
          >
            {{ t('common.edit') }}
          </el-button>
          <el-button
            size="small"
            :data-testid="`baseline-definition-manage-metrics-${item.id}`"
            @click="openMetricManager(item.id)"
          >
            {{ t('baselineDefinition.manageMetrics') }}
          </el-button>
          <div class="flex-1" />
          <el-button
            v-if="item.status === 'active'"
            size="small"
            type="warning"
            text
            @click="handleDisable(item.id)"
          >
            {{ t('common.disable') }}
          </el-button>
          <el-button
            v-else
            size="small"
            type="success"
            text
            @click="handleEnable(item.id)"
          >
            {{ t('baselineDefinition.enable') }}
          </el-button>
          <el-popconfirm
            :title="t('baselineDefinition.deleteConfirm')"
            @confirm="handleDelete(item.id)"
          >
            <template #reference>
              <el-button
                size="small"
                type="danger"
                text
                :icon="Delete"
              >
                {{ t('common.delete') }}
              </el-button>
            </template>
          </el-popconfirm>
        </div>

        <!-- 创建时间 -->
        <div class="mt-2 text-xs text-gray-400">
          {{ t('baselineDefinition.createdAt') }}: {{ item.createdAt }}
        </div>
      </el-card>
    </div>

    <!-- 空状态 -->
    <div
      v-else
      class="rounded-xl border border-dashed border-gray-300 bg-white py-16"
    >
      <el-empty :description="t('common.noData')" />
    </div>

    <!-- 新建/编辑定义对话框 -->
    <ElDialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="560px"
      destroy-on-close
      append-to-body
      data-testid="baseline-definition-dialog"
    >
      <el-form
        label-width="120px"
        label-position="right"
      >
        <el-form-item
          :label="t('baselineDefinition.definitionName')"
          required
        >
          <el-input
            v-model="definitionForm.definitionName"
            :placeholder="t('baselineDefinition.namePlaceholder')"
            maxlength="100"
            show-word-limit
            data-testid="baseline-definition-name-input"
          />
        </el-form-item>
        <el-form-item :label="t('baselineDefinition.description')">
          <el-input
            v-model="definitionForm.description"
            type="textarea"
            :rows="3"
            :placeholder="t('baselineDefinition.descriptionPlaceholder')"
          />
        </el-form-item>
        <el-form-item
          :label="t('baselineDefinition.expectedDuration')"
          required
        >
          <el-input-number
            v-model="definitionForm.expectedDurationMinutes"
            :min="1"
            :max="480"
            :step="5"
          />
          <span class="ml-2 text-sm text-gray-500">
            {{ t('baselineDefinition.minutes') }}
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">
          {{ t('common.cancel') }}
        </el-button>
        <el-button
          type="primary"
          data-testid="baseline-definition-submit"
          @click="handleSubmit"
        >
          {{ t('common.confirm') }}
        </el-button>
      </template>
    </ElDialog>

    <!-- 指标管理对话框 -->
    <ElDialog
      v-model="metricDialogVisible"
      :title="t('baselineDefinition.manageMetrics')"
      width="680px"
      destroy-on-close
      append-to-body
      data-testid="baseline-definition-metric-dialog"
    >
      <template v-if="metricDefinitionItem">
        <p class="text-sm text-gray-500 mb-4">
          {{ t('baselineDefinition.metricsFor') }}: {{ metricDefinitionItem.definitionName }}
        </p>

        <!-- 现有指标列表 -->
        <div class="space-y-2 mb-6">
          <div
            v-for="metric in metricDefinitionItem.metrics"
            :key="metric.id"
            class="flex items-center gap-3 p-3 rounded-lg border border-gray-200 bg-gray-50"
          >
            <template v-if="editingMetricId === metric.id">
              <!-- 编辑模式 -->
              <el-select
                v-model="editMetricForm.edc_channel_id"
                size="small"
                class="w-64"
                clearable
                filterable
                :loading="hostChannelsLoading"
                :placeholder="t('baselineDefinition.sourceChannelPlaceholder')"
                @change="value => applySourceChannelDefaults(value, editMetricForm)"
              >
                <el-option-group
                  v-for="group in getSelectableHostChannelGroups(metric.id)"
                  :key="group.label"
                  :label="group.label"
                >
                  <el-option
                    v-for="channel in group.options"
                    :key="channel.id"
                    :label="formatHostChannelLabel(channel)"
                    :value="channel.id"
                  />
                </el-option-group>
              </el-select>
              <el-input
                v-model="editMetricForm.name"
                size="small"
                class="w-28"
              />
              <el-input
                v-model="editMetricForm.unit"
                size="small"
                class="w-20"
              />
              <el-color-picker
                v-model="editMetricForm.color"
                size="small"
              />
              <div class="flex-1" />
              <el-button
                size="small"
                :icon="CircleCheck"
                type="success"
                @click="saveEditMetric"
              />
              <el-button
                size="small"
                :icon="CircleClose"
                @click="cancelEditMetric"
              />
            </template>
            <template v-else>
              <!-- 显示模式 -->
              <div
                class="w-4 h-4 rounded-full shrink-0"
                :style="{ backgroundColor: metric.color }"
              />
              <span class="font-medium text-gray-800">{{ metric.name }}</span>
              <el-tag
                size="small"
                type="info"
              >
                {{ metric.unit }}
              </el-tag>
              <span
                v-if="metric.edcChannelId"
                class="text-xs text-gray-400"
              >
                {{ t('baselineDefinition.sourceChannelBound') }}:
                {{ resolveHostChannelSummary(metric.edcChannelId) }}
              </span>
              <span
                v-else
                class="text-xs text-amber-500"
              >
                {{ t('baselineDefinition.sourceChannelMissing') }}
              </span>
              <span class="text-xs text-gray-400">#{{ metric.sortOrder }}</span>
              <div class="flex-1" />
              <el-button
                size="small"
                text
                :icon="Edit"
                @click="startEditMetric(metric)"
              />
              <el-button
                size="small"
                text
                type="danger"
                :icon="Delete"
                @click="handleRemoveMetric(metric.id)"
              />
            </template>
          </div>

          <div
            v-if="metricDefinitionItem.metrics.length === 0"
            class="text-center py-6 text-gray-400 text-sm"
          >
            {{ t('baselineDefinition.noMetrics') }}
          </div>
        </div>

        <!-- 添加新指标 -->
        <div class="border-t border-gray-200 pt-4">
          <p class="text-sm font-medium text-gray-700 mb-3">
            {{ t('baselineDefinition.addMetric') }}
          </p>
          <div class="space-y-3">
            <el-select
              v-model="newMetricForm.edc_channel_id"
              size="small"
              clearable
              filterable
              class="w-full"
              :loading="hostChannelsLoading"
              :placeholder="t('baselineDefinition.sourceChannelPlaceholder')"
              data-testid="baseline-definition-source-channel-select"
              @change="value => applySourceChannelDefaults(value, newMetricForm)"
            >
              <el-option-group
                v-for="group in getSelectableHostChannelGroups()"
                :key="group.label"
                :label="group.label"
              >
                <el-option
                  v-for="channel in group.options"
                  :key="channel.id"
                  :label="formatHostChannelLabel(channel)"
                  :value="channel.id"
                />
              </el-option-group>
            </el-select>
            <p
              v-if="newMetricForm.edc_channel_id"
              class="text-xs text-gray-500"
            >
              {{ t('baselineDefinition.sourceChannelBound') }}:
              {{ resolveHostChannelSummary(newMetricForm.edc_channel_id ?? null) }}
            </p>
          </div>
          <div class="mt-3 flex items-center gap-3">
            <el-input
              v-model="newMetricForm.name"
              size="small"
              :placeholder="t('baselineDefinition.metricName')"
              class="w-32"
              data-testid="baseline-definition-metric-name-input"
            />
            <el-input
              v-model="newMetricForm.unit"
              size="small"
              :placeholder="t('baselineDefinition.metricUnit')"
              class="w-24"
              data-testid="baseline-definition-metric-unit-input"
            />
            <el-color-picker
              v-model="newMetricForm.color"
              size="small"
            />
            <el-button
              size="small"
              type="primary"
              :icon="Plus"
              data-testid="baseline-definition-add-metric"
              @click="handleAddMetric"
            >
              {{ t('common.create') }}
            </el-button>
          </div>
        </div>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
