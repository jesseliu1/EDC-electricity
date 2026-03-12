<script setup lang="ts">
/**
 * PageContainer - 页面内容容器组件
 * 提供统一的页面内边距和最大宽度限制
 */

interface Props {
  // 是否使用最大宽度限制
  maxWidth?: boolean
  // 是否移除内边距
  noPadding?: boolean
}

withDefaults(defineProps<Props>(), {
  maxWidth: true,
  noPadding: false,
})
</script>

<template>
  <div
    class="flex-1 overflow-y-auto bg-background-light"
    :class="noPadding ? '' : 'p-6 lg:p-8'"
  >
    <div :class="maxWidth ? 'max-w-[1600px] mx-auto flex flex-col gap-6' : ''">
      <slot />
    </div>
  </div>
</template>

<style scoped>
/* 自定义滚动条 */
div::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

div::-webkit-scrollbar-track {
  background: transparent;
}

div::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 4px;
}

div::-webkit-scrollbar-thumb:hover {
  background: #c0c4cc;
}
</style>
