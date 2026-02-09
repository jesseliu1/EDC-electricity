<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Search, Bell, QuestionFilled } from '@element-plus/icons-vue'

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
  label: '系统运行正常',
}))

const handleToggleSidebar = () => {
  emit('toggle-sidebar')
}
</script>

<template>
  <header
    class="h-header bg-white border-b border-border-light flex items-center justify-between px-6 shrink-0"
  >
    <!-- 左侧：菜单按钮 + 页面标题 + 系统状态 -->
    <div class="flex items-center gap-4">
      <!-- 移动端菜单按钮 -->
      <button
        class="lg:hidden p-2 text-text-secondary hover:text-primary hover:bg-gray-100 rounded-lg transition-colors"
        @click="handleToggleSidebar"
      >
        <el-icon :size="20">
          <svg viewBox="0 0 24 24" fill="currentColor" class="w-5 h-5">
            <path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z" />
          </svg>
        </el-icon>
      </button>

      <!-- 页面标题 -->
      <h2 class="text-lg font-bold text-text-primary">{{ pageTitle }}</h2>

      <!-- 分隔线 -->
      <div class="hidden md:block h-5 w-px bg-border-light" />

      <!-- 系统状态指示器 -->
      <span
        v-if="systemStatus.isOnline"
        class="hidden md:flex items-center gap-2 text-xs font-medium px-2.5 py-1.5 rounded-md bg-green-50 text-green-700 border border-green-200"
      >
        <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
        {{ systemStatus.label }}
      </span>
    </div>

    <!-- 右侧：搜索框 + 工具按钮 -->
    <div class="flex items-center gap-4">
      <!-- 搜索框 -->
      <div class="hidden lg:flex items-center">
        <el-input
          :placeholder="t('common.search') + '...'"
          :prefix-icon="Search"
          class="w-64"
          size="default"
          clearable
        />
      </div>

      <!-- 工具按钮组 -->
      <div class="flex items-center gap-1">
        <!-- 通知按钮 -->
        <el-badge :value="3" :max="99" class="notification-badge">
          <el-button :icon="Bell" circle size="default" text />
        </el-badge>

        <!-- 帮助按钮 -->
        <el-button :icon="QuestionFilled" circle size="default" text />
      </div>
    </div>
  </header>
</template>

<style scoped>
.notification-badge :deep(.el-badge__content) {
  top: 6px;
  right: 10px;
}
</style>
