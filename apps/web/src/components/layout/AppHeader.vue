<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

interface Emits {
  (e: 'toggle-sidebar'): void
}

const emit = defineEmits<Emits>()

const { t } = useI18n()
const route = useRoute()

// 根据当前路由获取页面标题
const pageTitle = computed(() => {
  const titleKey = route.meta.title as string | undefined
  if (titleKey) {
    return t(titleKey)
  }
  return t('nav.dashboard')
})

// 系统状态（后续可从 store 获取）
const systemStatus = computed(() => ({
  isOnline: true,
  label: t('common.systemNormal', '系统运行正常'),
}))

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
        v-if="systemStatus.isOnline"
        class="hidden md:flex items-center gap-2 text-xs font-medium px-2 py-1 rounded bg-green-100 text-green-700 border border-green-200"
      >
        <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
        {{ systemStatus.label }}
      </span>
    </div>

    <!-- 右侧：搜索框 + 工具按钮 -->
    <div class="flex items-center gap-6">
      <!-- 搜索框 — 原生 input + Material icon -->
      <div
        class="hidden lg:flex items-center bg-slate-100 rounded-lg px-3 py-2 w-64 border border-transparent focus-within:border-primary focus-within:ring-1 focus-within:ring-primary/20 transition-all"
      >
        <span class="material-symbols-outlined text-slate-400 text-[20px]"
          >search</span
        >
        <input
          type="text"
          class="bg-transparent border-none focus:ring-0 focus:outline-none text-sm text-slate-700 w-full placeholder:text-slate-400 ml-2 p-0 h-auto"
          :placeholder="t('common.searchHeatId', '搜索炉次 ID...')"
        />
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
