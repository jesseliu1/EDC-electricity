<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import StatCard from '@/components/dashboard/StatCard.vue'
import RealtimeChart from '@/components/dashboard/RealtimeChart.vue'
import HeatList from '@/components/dashboard/HeatList.vue'
import { useDashboardStore } from '@/stores/dashboard'

const { t } = useI18n()
const router = useRouter()

const dashboardStore = useDashboardStore()

// 统计卡片数据 — 使用 Material Symbols 图标名
const stats = computed(() => [
  {
    id: 1,
    title: t('dashboard.todayHeats'),
    value: dashboardStore.stats.todayHeats,
    unit: t('dashboard.unit.heats'),
    trend: 12,
    description: '较昨日增加 14 炉',
    icon: 'monitoring',
    accentColor: 'primary' as const,
  },
  {
    id: 2,
    title: t('dashboard.avgDeviation'),
    value: dashboardStore.stats.avgDeviation,
    unit: t('dashboard.unit.percent'),
    trend: 0.5,
    description: '控制在允许范围内 (5%)',
    icon: 'speed',
    accentColor: 'orange' as const,
  },
  {
    id: 3,
    title: t('dashboard.pendingTasks'),
    value: dashboardStore.stats.pendingTasks,
    unit: t('dashboard.unit.tasks'),
    trend: -1,
    description: '',
    icon: 'assignment',
    accentColor: 'green' as const,
  },
  {
    id: 4,
    title: t('dashboard.baselineStatus'),
    value:
      dashboardStore.stats.activeBaseline ||
      t('dashboard.baselineStatusNormal'),
    unit: '',
    trend: 0,
    description: '上次校准: 2023-10-24',
    icon: 'verified',
    accentColor: 'green' as const,
  },
])

// 快捷入口配置
const quickLinks = [
  {
    icon: 'dataset',
    label: '炉次浏览',
    route: '/heats',
    color: 'bg-blue-100 text-blue-600',
  },
  {
    icon: 'mail',
    label: '偏差收件箱',
    route: '/inbox',
    color: 'bg-orange-100 text-orange-600',
    badge: 3,
  },
  {
    icon: 'assignment',
    label: '纠偏任务单',
    route: '/tasks',
    color: 'bg-emerald-100 text-emerald-600',
  },
  {
    icon: 'library_books',
    label: '黄金基线库',
    route: '/baselines',
    color: 'bg-cyan-100 text-cyan-600',
  },
  {
    icon: 'lightbulb',
    label: '纠偏知识卡',
    route: '/baselines',
    color: 'bg-purple-100 text-purple-600',
  },
  {
    icon: 'picture_as_pdf',
    label: '日报与审计',
    route: '/reports',
    color: 'bg-red-100 text-red-600',
  },
]

const handleRangeChange = (range: '5m' | '1h' | '6h' | '24h') => {
  dashboardStore.fetchRealtime(range)
}

const navigateTo = (route: string) => {
  router.push(route)
}

onMounted(() => {
  dashboardStore.fetchAll()
})
</script>

<template>
  <div
    class="flex flex-col gap-6"
    data-testid="dashboard-page"
  >
    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
      <StatCard
        v-for="stat in stats"
        :key="stat.id"
        :title="stat.title"
        :value="stat.value"
        :unit="stat.unit"
        :trend="stat.trend"
        :description="stat.description"
        :icon="stat.icon"
        :accent-color="stat.accentColor"
      />
    </div>

    <!-- 快捷入口 -->
    <div class="grid grid-cols-3 md:grid-cols-6 gap-4">
      <button
        v-for="link in quickLinks"
        :key="link.label"
        :data-testid="`dashboard-quick-link-${link.route.replace('/', '') || 'home'}`"
        class="relative flex flex-col items-center gap-3 py-5 px-3 bg-white rounded-xl border border-border-light shadow-subtle hover:shadow-card hover:border-primary/20 transition-all duration-200 group cursor-pointer"
        @click="navigateTo(link.route)"
      >
        <!-- 角标 -->
        <span
          v-if="link.badge"
          class="absolute top-2 right-2 w-5 h-5 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center"
        >
          {{ link.badge }}
        </span>
        <span
          :class="[
            'w-12 h-12 rounded-xl flex items-center justify-center transition-transform group-hover:scale-110',
            link.color,
          ]"
        >
          <span class="material-symbols-outlined text-[24px]">{{
            link.icon
          }}</span>
        </span>
        <span
          class="text-sm font-medium text-slate-700 group-hover:text-primary transition-colors"
          >{{ link.label }}</span
        >
      </button>
    </div>

    <!-- 实时曲线 (全宽) -->
    <div class="h-[500px]">
      <RealtimeChart
        :power="dashboardStore.realtime.power"
        :baseline-power="dashboardStore.realtime.baselinePower"
        :selected-range="dashboardStore.timeRange"
        @range-change="handleRangeChange"
      />
    </div>

    <!-- 底部三列: 最近炉次 + 偏差收件箱 + 纠偏待办 -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <div class="lg:col-span-5">
        <HeatList :heats="dashboardStore.recentHeats" />
      </div>
      <div class="lg:col-span-4">
        <div
          class="bg-white rounded-xl border border-border-light shadow-card p-6 h-full"
        >
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <span
                class="material-symbols-outlined text-orange-500 text-[20px]"
                >mail</span
              >
              <h3 class="text-base font-bold text-slate-800">偏差收件箱预览</h3>
            </div>
          </div>
          <div class="space-y-3">
            <div
              class="p-3 bg-slate-50 rounded-lg border border-border-light hover:border-primary/30 transition-colors cursor-pointer"
            >
              <div class="flex items-center justify-between mb-1">
                <span class="text-sm font-semibold text-slate-700"
                  >Cluster #C-882</span
                >
                <span
                  class="text-xs px-2 py-0.5 rounded-full bg-orange-100 text-orange-600 font-medium"
                  >未命名</span
                >
              </div>
              <p class="text-xs text-slate-500">出现 5 次 · 相似度 92%</p>
              <div class="h-1 bg-red-400 rounded-full mt-2" />
            </div>
            <div
              class="p-3 bg-slate-50 rounded-lg border border-border-light hover:border-primary/30 transition-colors cursor-pointer"
            >
              <div class="flex items-center justify-between mb-1">
                <span class="text-sm font-semibold text-slate-700"
                  >Cluster #C-881</span
                >
                <span
                  class="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-600 font-medium"
                  >已归档</span
                >
              </div>
              <p class="text-xs text-slate-500">出现 3 次 · 相似度 87%</p>
              <div class="h-1 bg-green-400 rounded-full mt-2 w-3/4" />
            </div>
          </div>
        </div>
      </div>
      <div class="lg:col-span-3">
        <div
          class="bg-white rounded-xl border border-border-light shadow-card p-6 h-full"
        >
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <span
                class="material-symbols-outlined text-primary text-[20px]"
                >task_alt</span
              >
              <h3 class="text-base font-bold text-slate-800">纠偏任务待办</h3>
            </div>
            <span
              class="w-6 h-6 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center"
              >3</span
            >
          </div>
          <div class="space-y-3">
            <div class="p-3 bg-slate-50 rounded-lg">
              <p class="text-sm font-semibold text-slate-700 mb-1">
                供氧参数调整
              </p>
              <p class="text-xs text-slate-500">机台: 2#炉</p>
              <div class="flex items-center justify-between mt-2">
                <span class="text-xs text-slate-400">李工</span>
                <span
                  class="text-xs px-2 py-0.5 rounded bg-primary text-white font-medium"
                  >Dev: +12%</span
                >
              </div>
            </div>
            <div class="p-3 bg-slate-50 rounded-lg">
              <p class="text-sm font-semibold text-slate-700 mb-1">
                废气阀门检查
              </p>
              <p class="text-xs text-slate-500">机台: 1#炉</p>
              <div class="flex items-center justify-between mt-2">
                <span class="text-xs text-slate-400">王工</span>
                <span
                  class="text-xs px-2 py-0.5 rounded bg-orange-500 text-white font-medium"
                  >Dev: +8%</span
                >
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
