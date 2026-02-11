<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElCard, ElTag, ElButton, ElDropdown, ElDropdownMenu, ElDropdownItem, ElIcon } from 'element-plus'
import { MoreFilled, Edit, Delete, VideoPlay, VideoPause } from '@element-plus/icons-vue'
import type { BaselineItem } from '@/stores/baseline'
import dayjs from 'dayjs'

const { t } = useI18n()

interface Props {
  baseline: BaselineItem
}

const props = defineProps<Props>()

interface Emits {
  (e: 'edit', id: string): void
  (e: 'delete', id: string): void
  (e: 'publish', id: string): void
  (e: 'disable', id: string): void
}

const emit = defineEmits<Emits>()

const statusType = computed(() => {
  switch (props.baseline.status) {
    case 'published':
      return 'success'
    case 'draft':
      return 'info'
    case 'disabled':
      return 'danger'
    default:
      return 'info'
  }
})

const statusText = computed(() => {
  switch (props.baseline.status) {
    case 'published':
      return t('baseline.statusPublished')
    case 'draft':
      return t('baseline.statusDraft')
    case 'disabled':
      return t('baseline.statusDisabled')
    default:
      return props.baseline.status
  }
})

const formattedDate = computed(() => {
  return dayjs(props.baseline.createdAt).format('YYYY-MM-DD HH:mm')
})

function handleCommand(command: string) {
  switch (command) {
    case 'edit':
      emit('edit', props.baseline.id)
      break
    case 'delete':
      emit('delete', props.baseline.id)
      break
    case 'publish':
      emit('publish', props.baseline.id)
      break
    case 'disable':
      emit('disable', props.baseline.id)
      break
  }
}
</script>

<template>
  <el-card class="baseline-card hover:shadow-md transition-shadow duration-300">
    <div class="p-4">
      <div class="flex justify-between items-start mb-4">
        <div class="flex-1 min-w-0 mr-4">
          <div class="flex items-center gap-2 mb-1">
            <h3
              class="text-lg font-semibold text-gray-900 truncate"
              :title="baseline.name"
            >
              {{ baseline.name }}
            </h3>
            <el-tag
              size="small"
              :type="statusType"
              effect="light"
              class="shrink-0"
            >
              {{ statusText }}
            </el-tag>
          </div>
          <p class="text-sm text-gray-500 line-clamp-2 h-10">
            {{ baseline.description || t('common.noDescription') }}
          </p>
        </div>
      
        <el-dropdown
          trigger="click"
          @command="handleCommand"
        >
          <el-button
            link
            class="p-1"
          >
            <el-icon
              :size="20"
              class="text-gray-400 hover:text-gray-600"
            >
              <MoreFilled />
            </el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                command="edit"
                :icon="Edit"
              >
                {{ t('common.edit') }}
              </el-dropdown-item>
              <el-dropdown-item 
                v-if="baseline.status === 'draft'" 
                command="publish" 
                :icon="VideoPlay"
              >
                {{ t('baseline.publish') }}
              </el-dropdown-item>
              <el-dropdown-item 
                v-if="baseline.status === 'published'" 
                command="disable" 
                :icon="VideoPause"
              >
                {{ t('common.disable') }}
              </el-dropdown-item>
              <el-dropdown-item 
                v-if="baseline.status === 'draft'" 
                command="delete" 
                :icon="Delete" 
                class="text-red-500"
              >
                {{ t('common.delete') }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>

        <div class="grid grid-cols-2 gap-4 text-sm text-gray-600 bg-gray-50 p-3 rounded-lg">
        <div class="flex flex-col col-span-2">
          <span class="text-xs text-gray-400 mb-1">{{ t('baseline.definitionName') }}</span>
          <span class="font-medium">{{ baseline.definitionName }}</span>
        </div>
        <div class="flex flex-col">
          <span class="text-xs text-gray-400 mb-1">{{ t('baseline.version') }}</span>
          <span class="font-medium">v{{ baseline.version }}</span>
        </div>
        <div class="flex flex-col">
          <span class="text-xs text-gray-400 mb-1">{{ t('baseline.tolerance') }}</span>
          <span class="font-medium">{{ baseline.tolerancePercent }}%</span>
        </div>
        <div class="flex flex-col col-span-2">
          <span class="text-xs text-gray-400 mb-1">{{ t('baseline.createTime') }}</span>
          <span class="font-medium">{{ formattedDate }}</span>
        </div>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.baseline-card {
  border: 1px solid var(--el-border-color-light);
}
</style>
