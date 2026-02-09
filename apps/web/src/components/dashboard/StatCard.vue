<script setup lang="ts">
import type { Component } from 'vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { CaretTop, CaretBottom, Minus } from '@element-plus/icons-vue'

interface Props {
  title: string
  value: string | number
  unit?: string
  trend?: number
  status?: 'success' | 'warning' | 'danger' | 'info'
  icon?: Component
}

const props = withDefaults(defineProps<Props>(), {
  status: 'info',
  trend: 0,
  unit: '',
  icon: undefined
})

const { t } = useI18n()

const trendColor = computed(() => {
  if (props.trend > 0) return 'text-red-500'
  if (props.trend < 0) return 'text-green-500'
  return 'text-gray-400'
})

const trendIcon = computed(() => {
  if (props.trend > 0) return CaretTop
  if (props.trend < 0) return CaretBottom
  return Minus
})
</script>

<template>
  <div class="stat-card h-full">
    <div class="flex items-start justify-between mb-2">
      <span class="text-sm text-gray-500 font-medium">{{ title }}</span>
      <el-icon
        v-if="icon"
        class="text-gray-400"
        :size="16"
      >
        <component :is="icon" />
      </el-icon>
    </div>
    
    <div class="flex items-baseline gap-2 mt-2">
      <span class="text-3xl font-bold text-gray-900">{{ value }}</span>
      <span
        v-if="unit"
        class="text-sm text-gray-500"
      >{{ unit }}</span>
    </div>

    <div
      v-if="trend !== 0"
      class="flex items-center mt-2 text-xs"
    >
      <span :class="['flex items-center font-medium', trendColor]">
        <el-icon class="mr-0.5"><component :is="trendIcon" /></el-icon>
        {{ Math.abs(trend) }}%
      </span>
      <span class="text-gray-400 ml-1.5">{{ t('dashboard.trendFromYesterday') }}</span>
    </div>
  </div>
</template>

<style scoped>
.stat-card {
  @apply bg-white rounded-xl p-5 shadow-sm border border-gray-100 transition-all duration-300 hover:shadow-md;
}
</style>
