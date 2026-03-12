<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

interface Props {
  collapsed?: boolean
}

withDefaults(defineProps<Props>(), {
  collapsed: false,
})

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

// 导航菜单配置 — 分组式 (对齐原型)
interface MenuItem {
  path: string
  name: string
  icon: string
  label: string
}

interface MenuGroup {
  title: string
  items: MenuItem[]
}

const menuGroups = computed<MenuGroup[]>(() => [
  {
    title: t('nav.groupOverview', '生产概览'),
    items: [
      {
        path: '/',
        name: 'Dashboard',
        icon: 'dashboard',
        label: t('nav.dashboard'),
      },
    ],
  },
  {
    title: t('nav.groupMonitor', '监控与分析'),
    items: [
      {
        path: '/baseline-definitions',
        name: 'BaselineDefinitions',
        icon: 'grid_on',
        label: t('nav.baselineDefinitions'),
      },
      {
        path: '/baselines',
        name: 'Baselines',
        icon: 'library_books',
        label: t('nav.baselines'),
      },
      {
        path: '/heats',
        name: 'Heats',
        icon: 'dataset',
        label: t('nav.heats'),
      },
      {
        path: '/inbox',
        name: 'Inbox',
        icon: 'mail',
        label: t('nav.inbox'),
      },
      {
        path: '/tasks',
        name: 'Tasks',
        icon: 'assignment',
        label: t('nav.tasks'),
      },
      {
        path: '/reports',
        name: 'Reports',
        icon: 'picture_as_pdf',
        label: t('nav.reports'),
      },
    ],
  },
  {
    title: t('nav.groupManage', '管理'),
    items: [
      {
        path: '/settings',
        name: 'Settings',
        icon: 'settings',
        label: t('nav.settings'),
      },
    ],
  },
])

const isActive = (path: string): boolean => {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

const handleNavigate = (path: string) => {
  router.push(path)
}


</script>

<template>
  <aside
    class="h-full flex flex-col bg-surface-light border-r border-border-light transition-all duration-300 z-20"
    :class="collapsed ? 'w-sidebar-collapsed' : 'w-sidebar'"
  >
    <!-- Logo 区域 -->
    <div class="h-header flex items-center px-6 border-b border-border-light">
      <div class="flex items-center gap-3 overflow-hidden">
        <div
          class="shrink-0 w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary"
        >
          <span class="material-symbols-outlined text-[20px]">precision_manufacturing</span>
        </div>
        <div
          v-show="!collapsed"
          class="flex flex-col min-w-0"
        >
          <h1
            class="text-sm font-bold text-slate-900 leading-none tracking-tight"
          >
            AI老师傅
          </h1>
          <span class="text-xs text-slate-500 font-medium mt-1">{{
            t('common.appName', '智慧熔炼偏差分析')
          }}</span>
        </div>
      </div>
    </div>

    <!-- 导航菜单 — 分组式 -->
    <nav class="flex-1 overflow-y-auto py-4 px-3">
      <div
        v-for="(group, gIdx) in menuGroups"
        :key="group.title"
        :class="gIdx > 0 ? 'mt-4' : ''"
      >
        <!-- 分组分隔线 -->
        <div
          v-if="gIdx > 0"
          class="h-px bg-border-light mx-2 mb-3"
        />
        <!-- 分组标题 -->
        <p
          v-show="!collapsed"
          class="px-3 text-xs font-bold text-slate-400 uppercase tracking-wider mb-2"
        >
          {{ group.title }}
        </p>
        <!-- 菜单项 -->
        <ul class="flex flex-col gap-1">
          <li
            v-for="item in group.items"
            :key="item.path"
          >
            <button
              class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 relative"
              :class="[
                isActive(item.path)
                  ? 'bg-primary/10 text-primary font-bold'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
              ]"
              :title="collapsed ? item.label : undefined"
              @click="handleNavigate(item.path)"
            >
              <!-- 活跃项左侧指示条 -->
              <div
                v-if="isActive(item.path)"
                class="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-primary rounded-r-full"
              />
              <span
                class="material-symbols-outlined text-[20px] shrink-0"
                :class="isActive(item.path) ? '' : 'text-slate-400'"
                :style="
                  isActive(item.path)
                    ? 'font-variation-settings: \'FILL\' 1'
                    : ''
                "
              >{{ item.icon }}</span>
              <span
                v-show="!collapsed"
                class="text-sm truncate"
              >{{
                item.label
              }}</span>
            </button>
          </li>
        </ul>
      </div>
    </nav>

    <!-- 底部用户信息卡 -->
    <div class="p-4 border-t border-border-light">
      <div
        class="flex items-center gap-3 p-2 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
      >
        <div
          class="w-9 h-9 rounded-full bg-primary/20 text-primary flex items-center justify-center text-xs font-bold ring-2 ring-white shadow-sm shrink-0"
        >
          WG
        </div>
        <div
          v-show="!collapsed"
          class="flex flex-col min-w-0"
        >
          <p class="text-sm font-bold text-slate-900 truncate">
            王工程师
          </p>
          <p class="text-xs text-slate-500 truncate">
            高级工艺主管
          </p>
        </div>
        <span
          v-show="!collapsed"
          class="material-symbols-outlined text-slate-400 ml-auto text-lg"
        >expand_more</span>
      </div>
    </div>
  </aside>
</template>

<style scoped>
/* 自定义导航区滚动条 */
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
