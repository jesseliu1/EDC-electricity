<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  title: string
  value: string | number
  unit?: string
  trend?: number
  description?: string
  icon?: string // Material Symbols icon name
  accentColor?: 'primary' | 'orange' | 'red' | 'green'
}

const props = withDefaults(defineProps<Props>(), {
  trend: 0,
  unit: '',
  description: '',
  icon: 'monitoring',
  accentColor: 'primary',
})



// 底部指示条颜色映射
const accentColorClass = computed(() => {
  const map: Record<string, string> = {
    primary: 'bg-primary',
    orange: 'bg-orange-400',
    red: 'bg-red-500',
    green: 'bg-green-500',
  }
  return map[props.accentColor] || 'bg-primary'
})

// 装饰图标背景色映射
const iconBgClass = computed(() => {
  const map: Record<string, string> = {
    primary: 'text-primary/15',
    orange: 'text-orange-500/15',
    red: 'text-red-500/15',
    green: 'text-green-500/15',
  }
  return map[props.accentColor] || 'text-primary/15'
})

// 趋势标签颜色
const trendBadgeClass = computed(() => {
  if (props.trend > 0) return 'bg-orange-50 text-orange-600 border-orange-200'
  if (props.trend < 0) return 'bg-green-50 text-green-600 border-green-200'
  return ''
})
</script>

<template>
  <div
    class="stat-card relative overflow-hidden h-full"
    data-testid="stat-card"
  >
    <!-- 底部彩色指示条 -->
    <div
      :class="['absolute bottom-0 left-0 right-0 h-1 rounded-b-xl', accentColorClass]"
      data-testid="accent-bar"
    />

    <!-- 右上角装饰图标 -->
    <div
      class="absolute top-4 right-4"
      data-testid="decorative-icon"
    >
      <span
        class="material-symbols-outlined !text-4xl"
        :class="iconBgClass"
      >{{ icon }}</span>
    </div>

    <!-- 标题 -->
    <p class="text-sm font-medium text-slate-500 mb-2">
      {{ title }}
    </p>

    <!-- 数值 + 单位 -->
    <div class="flex items-baseline gap-2 mt-1">
      <span class="text-3xl font-bold text-slate-900 tracking-tight">{{
        value
      }}</span>
      <span
        v-if="unit"
        class="text-sm text-slate-500 font-medium"
      >{{
        unit
      }}</span>
    </div>

    <!-- 趋势标签 -->
    <div class="flex items-center gap-2 mt-3">
      <span
        v-if="trend !== 0"
        :class="[
          'inline-flex items-center text-xs font-semibold px-2 py-0.5 rounded-full border',
          trendBadgeClass,
        ]"
        data-testid="trend-badge"
      >
        <span class="material-symbols-outlined !text-sm mr-0.5">{{
          trend > 0 ? 'trending_up' : 'trending_down'
        }}</span>
        {{ trend > 0 ? '+' : '' }}{{ trend }}%
      </span>
      <span
        v-if="description"
        class="text-xs text-slate-400"
      >{{
        description
      }}</span>
    </div>
  </div>
</template>

<style scoped>
.stat-card {
  @apply bg-white rounded-xl p-5 pb-6 shadow-card border border-border-light transition-all duration-300 hover:shadow-lg;
}
</style>
