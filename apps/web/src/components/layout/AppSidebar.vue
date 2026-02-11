<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  Odometer,
  DataLine,
  Grid,
  List,
  Document,
  Message,
  DataAnalysis,
  Setting,
  Fold,
  Expand,
} from '@element-plus/icons-vue'

interface Props {
  collapsed?: boolean
}

withDefaults(defineProps<Props>(), {
  collapsed: false,
})

interface Emits {
  (e: 'toggle'): void
}

const emit = defineEmits<Emits>()

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

// 导航菜单配置
const menuItems = computed(() => [
  {
    path: '/',
    name: 'Dashboard',
    icon: Odometer,
    label: t('nav.dashboard'),
  },
  {
    path: '/baselines',
    name: 'Baselines',
    icon: DataLine,
    label: t('nav.baselines'),
  },
  {
    path: '/baseline-definitions',
    name: 'BaselineDefinitions',
    icon: Grid,
    label: t('nav.baselineDefinitions'),
  },
  {
    path: '/heats',
    name: 'Heats',
    icon: List,
    label: t('nav.heats'),
  },
  {
    path: '/tasks',
    name: 'Tasks',
    icon: Document,
    label: t('nav.tasks'),
  },
  {
    path: '/inbox',
    name: 'Inbox',
    icon: Message,
    label: t('nav.inbox'),
  },
  {
    path: '/reports',
    name: 'Reports',
    icon: DataAnalysis,
    label: t('nav.reports'),
  },
  {
    path: '/settings',
    name: 'Settings',
    icon: Setting,
    label: t('nav.settings'),
  },
])

const isActive = (path: string): boolean => {
  return route.path === path
}

const handleNavigate = (path: string) => {
  router.push(path)
}

const handleToggle = () => {
  emit('toggle')
}
</script>

<template>
  <aside
    class="h-full flex flex-col bg-white border-r border-border-light transition-all duration-300"
    :class="collapsed ? 'w-sidebar-collapsed' : 'w-sidebar'"
  >
    <!-- Logo 区域 -->
    <div class="h-header flex items-center px-4 border-b border-border-light">
      <div class="flex items-center gap-3 overflow-hidden">
        <div class="shrink-0 w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
          <el-icon :size="24" class="text-primary">
            <Odometer />
          </el-icon>
        </div>
        <div v-show="!collapsed" class="flex flex-col min-w-0">
          <h1 class="text-sm font-bold text-text-primary truncate">AI老师傅</h1>
          <span class="text-xs text-text-secondary truncate">{{ t('common.appName') }}</span>
        </div>
      </div>
    </div>

    <!-- 导航菜单 -->
    <nav class="flex-1 overflow-y-auto py-4 px-3">
      <ul class="flex flex-col gap-1">
        <li v-for="item in menuItems" :key="item.path">
          <button
            class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200"
            :class="[
              isActive(item.path)
                ? 'bg-primary/10 text-primary font-medium'
                : 'text-text-regular hover:bg-gray-100 hover:text-text-primary',
            ]"
            :title="collapsed ? item.label : undefined"
            @click="handleNavigate(item.path)"
          >
            <el-icon :size="20" class="shrink-0">
              <component :is="item.icon" />
            </el-icon>
            <span v-show="!collapsed" class="text-sm truncate">{{ item.label }}</span>
          </button>
        </li>
      </ul>
    </nav>

    <!-- 底部折叠按钮 -->
    <div class="p-3 border-t border-border-light">
      <button
        class="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-text-secondary hover:bg-gray-100 hover:text-text-primary transition-colors"
        @click="handleToggle"
      >
        <el-icon :size="18">
          <Fold v-if="!collapsed" />
          <Expand v-else />
        </el-icon>
        <span v-show="!collapsed" class="text-sm">{{ collapsed ? '' : '收起菜单' }}</span>
      </button>
    </div>
  </aside>
</template>

<style scoped>
/* 自定义滚动条 */
nav::-webkit-scrollbar {
  width: 4px;
}

nav::-webkit-scrollbar-track {
  background: transparent;
}

nav::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 2px;
}

nav::-webkit-scrollbar-thumb:hover {
  background: #c0c4cc;
}
</style>
