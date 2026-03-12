<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

interface BreadcrumbItem {
  label: string
  path?: string
}

// 自动根据路由生成面包屑
const breadcrumbs = computed<BreadcrumbItem[]>(() => {
  const items: BreadcrumbItem[] = [
    { label: t('nav.dashboard'), path: '/' },
  ]

  // 从路由 meta 获取面包屑信息
  const meta = route.meta
  if (meta.breadcrumb && typeof meta.breadcrumb === 'string') {
    items.push({ label: t(meta.breadcrumb) })
  } else if (meta.title && typeof meta.title === 'string') {
    items.push({ label: t(meta.title) })
  }

  return items
})

const handleNavigate = (path: string | undefined) => {
  if (path) {
    router.push(path)
  }
}
</script>

<template>
  <nav class="flex items-center gap-1.5 text-sm" aria-label="Breadcrumb">
    <template v-for="(item, idx) in breadcrumbs" :key="idx">
      <!-- 分隔符 -->
      <span v-if="idx > 0" class="material-symbols-outlined text-slate-300 text-[16px]">
        chevron_right
      </span>
      <!-- 面包屑项 -->
      <button
        v-if="item.path && idx < breadcrumbs.length - 1"
        class="text-slate-500 hover:text-primary transition-colors font-medium flex items-center gap-1"
        @click="handleNavigate(item.path)"
      >
        <span v-if="idx === 0" class="material-symbols-outlined text-[16px]">home</span>
        {{ item.label }}
      </button>
      <span v-else class="text-slate-700 font-medium">
        {{ item.label }}
      </span>
    </template>
  </nav>
</template>
