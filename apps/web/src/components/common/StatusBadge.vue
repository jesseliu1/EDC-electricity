<script setup lang="ts">
/**
 * StatusBadge — 状态胶囊组件 (替代 el-tag)
 * 圆角胶囊 + 可选色点 + 文字
 */

interface Props {
  type?: 'success' | 'warning' | 'danger' | 'info' | 'primary'
  showDot?: boolean
  size?: 'sm' | 'md'
}

withDefaults(defineProps<Props>(), {
  type: 'info',
  showDot: true,
  size: 'sm',
})

const colorMap: Record<string, { bg: string; text: string; dot: string; border: string }> = {
  success: {
    bg: 'bg-green-50',
    text: 'text-green-700',
    dot: 'bg-green-500',
    border: 'border-green-200',
  },
  warning: {
    bg: 'bg-orange-50',
    text: 'text-orange-700',
    dot: 'bg-orange-500',
    border: 'border-orange-200',
  },
  danger: {
    bg: 'bg-red-50',
    text: 'text-red-700',
    dot: 'bg-red-500',
    border: 'border-red-200',
  },
  info: {
    bg: 'bg-slate-50',
    text: 'text-slate-600',
    dot: 'bg-slate-400',
    border: 'border-slate-200',
  },
  primary: {
    bg: 'bg-blue-50',
    text: 'text-blue-700',
    dot: 'bg-blue-500',
    border: 'border-blue-200',
  },
}
</script>

<template>
  <span
    :class="[
      'inline-flex items-center gap-1.5 rounded-full border font-medium',
      colorMap[type]?.bg,
      colorMap[type]?.text,
      colorMap[type]?.border,
      size === 'sm' ? 'px-2.5 py-0.5 text-xs' : 'px-3 py-1 text-sm',
    ]"
  >
    <span
      v-if="showDot"
      :class="['w-1.5 h-1.5 rounded-full', colorMap[type]?.dot]"
    />
    <slot />
  </span>
</template>
