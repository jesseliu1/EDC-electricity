<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useRuntimeStatusStore } from '@/stores/runtimeStatus'

interface Emits {
  (e: 'toggle-sidebar'): void
}

const emit = defineEmits<Emits>()

const { t } = useI18n()
const route = useRoute()
const runtimeStatusStore = useRuntimeStatusStore()

// 根据当前路由获取页面标题
const pageTitle = computed(() => {
  const titleKey = route.meta.title as string | undefined
  if (titleKey) {
    return t(titleKey)
  }
  return t('nav.dashboard')
})

const systemStatus = computed(() => {
  if (!runtimeStatusStore.loaded) {
    return {
      isVisible: false,
      className: '',
      dotClass: '',
      label: ''
    }
  }
  const code = runtimeStatusStore.headerCode
  if (code === 'showtime') {
    return {
      isVisible: true,
      className: 'hidden md:flex items-center gap-2 text-xs font-medium px-2 py-1 rounded bg-amber-100 text-amber-700 border border-amber-200',
      dotClass: 'w-2 h-2 rounded-full bg-amber-500',
      label: t('runtime.header.showtime')
    }
  }
  if (code === 'ready') {
    return {
      isVisible: true,
      className: 'hidden md:flex items-center gap-2 text-xs font-medium px-2 py-1 rounded bg-green-100 text-green-700 border border-green-200',
      dotClass: 'w-2 h-2 rounded-full bg-green-500 animate-pulse',
      label: t('runtime.header.ready')
    }
  }
  return {
    isVisible: true,
    className: 'hidden md:flex items-center gap-2 text-xs font-medium px-2 py-1 rounded bg-orange-100 text-orange-700 border border-orange-200',
    dotClass: 'w-2 h-2 rounded-full bg-orange-500',
    label: t(`runtime.header.${code}`)
  }
})

const handleToggleSidebar = () => {
  emit('toggle-sidebar')
}
</script>

<template>
  <header
    class="h-header bg-surface-light border-b border-border-light flex items-center justify-between px-6 lg:px-8 shrink-0 z-10"
  >
    <!-- 左侧：菜单按钮 + 页面标题 + 系统状态 -->
    <div class="flex items-center gap-4">
      <!-- 移动端菜单按钮 -->
      <button
        class="lg:hidden p-2 text-slate-500 hover:text-primary hover:bg-slate-100 rounded-lg transition-colors"
        @click="handleToggleSidebar"
      >
        <span class="material-symbols-outlined">menu</span>
      </button>

      <!-- 页面标题 -->
      <h2 class="text-xl font-bold text-slate-800 tracking-tight">
        {{ pageTitle }}
      </h2>

      <!-- 分隔线 -->
      <div class="hidden md:block h-6 w-px bg-border-light mx-2" />

      <!-- 系统状态指示器 -->
      <span
        v-if="systemStatus.isVisible"
        :class="systemStatus.className"
      >
        <span :class="systemStatus.dotClass" />
        {{ systemStatus.label }}
      </span>
    </div>

    <!-- 右侧：搜索框 + 工具按钮 -->
    <div class="flex items-center gap-6">
      <!-- 搜索框 — 原生 input + Material icon -->
      <div
        class="hidden lg:flex items-center bg-slate-100 rounded-lg px-3 py-2 w-64 border border-transparent focus-within:border-primary focus-within:ring-1 focus-within:ring-primary/20 transition-all"
      >
        <span class="material-symbols-outlined text-slate-400 text-[20px]">search</span>
        <input
          type="text"
          class="bg-transparent border-none focus:ring-0 focus:outline-none text-sm text-slate-700 w-full placeholder:text-slate-400 ml-2 p-0 h-auto"
          :placeholder="t('common.searchHeatId')"
        >
      </div>

      <!-- 工具按钮组 -->
      <div class="flex items-center gap-3">
        <!-- 通知按钮 — 红点式 -->
        <button
          class="relative p-2 text-slate-500 hover:text-primary hover:bg-slate-100 rounded-full transition-colors"
        >
          <span class="material-symbols-outlined">notifications</span>
          <span
            class="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full border-2 border-white"
          />
        </button>

        <!-- 帮助按钮 -->
        <button
          class="p-2 text-slate-500 hover:text-primary hover:bg-slate-100 rounded-full transition-colors"
        >
          <span class="material-symbols-outlined">help</span>
        </button>
      </div>
    </div>
  </header>
</template>
