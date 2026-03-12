<script setup lang="ts">
/**
 * PageHeader — 页面级标题组件 (对齐 stitch_dashboard 原型)
 * 包含: 面包屑 + 大标题 + 英文副标题 + 描述文案 + 右侧操作按钮区
 */
import Breadcrumb from './Breadcrumb.vue'

interface Props {
  title: string
  subtitle?: string
  description?: string
  showBreadcrumb?: boolean
}

withDefaults(defineProps<Props>(), {
  subtitle: '',
  description: '',
  showBreadcrumb: true,
})
</script>

<template>
  <div class="flex flex-col gap-3">
    <!-- 面包屑 -->
    <Breadcrumb v-if="showBreadcrumb" />

    <!-- 标题行 + 操作按钮 -->
    <div class="flex items-start justify-between gap-4 flex-wrap">
      <div>
        <h1 class="text-2xl font-bold text-slate-900 tracking-tight">
          {{ title }}
          <span
            v-if="subtitle"
            class="text-base font-normal text-slate-400 ml-3"
          >
            {{ subtitle }}
          </span>
        </h1>
        <p v-if="description" class="text-sm text-slate-500 mt-1">
          {{ description }}
        </p>
      </div>
      <!-- 右侧操作按钮插槽 -->
      <div class="flex items-center gap-3 shrink-0">
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>
