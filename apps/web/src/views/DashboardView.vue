<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import StatCard from '@/components/dashboard/StatCard.vue'
import RealtimeChart from '@/components/dashboard/RealtimeChart.vue'
import HeatList from '@/components/dashboard/HeatList.vue'
import SystemReadinessBanner from '@/components/common/SystemReadinessBanner.vue'
import { useDashboardStore } from '@/stores/dashboard'
import type { TaskStatus } from '@/api/task'

const { t } = useI18n()
const router = useRouter()

const dashboardStore = useDashboardStore()
const statsPending = computed(() => dashboardStore.loading && !dashboardStore.statsLoaded)
const statsUnavailable = computed(() => Boolean(dashboardStore.statsError) && !dashboardStore.statsLoaded)
const recentHeatsPending = computed(
  () => dashboardStore.loading && !dashboardStore.recentHeatsLoaded
)
const dashboardWarnings = computed(() =>
  [dashboardStore.statsError, dashboardStore.realtimeError, dashboardStore.recentHeatsError].filter(
    (item): item is string => Boolean(item)
  )
)

const inboxPreview = computed(() =>
  dashboardStore.recentHeats
    .filter(item => item.status === 'abnormal' || item.status === 'pending')
    .slice(0, 3)
)

const stats = computed(() => [
  {
    id: 1,
    title: t('dashboard.todayHeats'),
    value: statsPending.value || statsUnavailable.value ? '--' : dashboardStore.stats.todayHeats,
    unit: statsPending.value || statsUnavailable.value ? '' : t('dashboard.unit.heats'),
    trend: 0,
    description:
      statsUnavailable.value
        ? t('dashboard.statsLoadFailedHint')
        : dashboardStore.stats.todayHeats > 0
        ? `${t('report.normalRate')}: ${dashboardStore.stats.normalRate}%`
        : '',
    icon: 'monitoring',
    accentColor: 'primary' as const,
  },
  {
    id: 2,
    title: t('dashboard.avgDeviation'),
    value: statsPending.value || statsUnavailable.value ? '--' : dashboardStore.stats.avgDeviation,
    unit: statsPending.value || statsUnavailable.value ? '' : t('dashboard.unit.percent'),
    trend: 0,
    description: statsUnavailable.value ? t('dashboard.statsLoadFailedHint') : '',
    icon: 'speed',
    accentColor: 'orange' as const,
  },
  {
    id: 3,
    title: t('dashboard.pendingTasks'),
    value: statsPending.value || statsUnavailable.value ? '--' : dashboardStore.stats.pendingTasks,
    unit: statsPending.value || statsUnavailable.value ? '' : t('dashboard.unit.tasks'),
    trend: 0,
    description: statsUnavailable.value ? t('dashboard.statsLoadFailedHint') : '',
    icon: 'assignment',
    accentColor: 'green' as const,
  },
  {
    id: 4,
    title: t('dashboard.baselineStatus'),
    value:
      statsPending.value || statsUnavailable.value
        ? '--'
        : dashboardStore.stats.activeBaseline || t('dashboard.baselineStatusNormal'),
    unit: '',
    trend: 0,
    description:
      statsUnavailable.value
        ? t('dashboard.statsLoadFailedHint')
        : dashboardStore.realtimeError
          ? t('dashboard.realtimeLoadFailedHint')
        : dashboardStore.realtime.timestamp
          ? dayjs(dashboardStore.realtime.timestamp).format('YYYY-MM-DD HH:mm')
          : '',
    icon: 'verified',
    accentColor: 'green' as const,
  },
])

const quickLinks = computed(() => [
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
    badge: inboxPreview.value.length || undefined,
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
])

const handleRangeChange = (range: '5m' | '1h' | '6h' | '24h') => {
  void dashboardStore.fetchRealtime(range)
}

const navigateTo = (route: string) => {
  void router.push(route)
}

const taskStatusClass = (status: TaskStatus) => {
  if (status === 'pending') return 'bg-red-500 text-white'
  if (status === 'in_progress') return 'bg-orange-500 text-white'
  return 'bg-slate-200 text-slate-600'
}

const taskStatusLabel = (status: TaskStatus) => {
  if (status === 'pending') return t('task.statusPending')
  if (status === 'in_progress') return t('task.statusInProgress')
  if (status === 'completed') return t('task.statusCompleted')
  return t('task.statusCancelled')
}

const formatTaskDeviation = (value: number | null) => {
  return value === null ? t('task.deviationPending') : `${value}%`
}

onMounted(() => {
  void dashboardStore.fetchAll()
})
</script>

<template>
  <div
    class="flex flex-col gap-6"
    data-testid="dashboard-page"
  >
    <SystemReadinessBanner
      section="dashboard"
      test-id="dashboard-runtime-banner"
    />

    <div
      v-if="dashboardWarnings.length > 0"
      class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
      data-testid="dashboard-load-warning"
    >
      <div class="font-semibold">
        {{ t('dashboard.loadWarningTitle') }}
      </div>
      <div class="mt-2 flex flex-col gap-1 text-amber-700">
        <span
          v-for="item in dashboardWarnings"
          :key="item"
        >{{ item }}</span>
      </div>
    </div>

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

    <div class="grid grid-cols-3 md:grid-cols-6 gap-4">
      <button
        v-for="link in quickLinks"
        :key="link.label"
        :data-testid="`dashboard-quick-link-${link.route.replace('/', '') || 'home'}`"
        class="relative flex flex-col items-center gap-3 py-5 px-3 bg-white rounded-xl border border-border-light shadow-subtle hover:shadow-card hover:border-primary/20 transition-all duration-200 group cursor-pointer"
        @click="navigateTo(link.route)"
      >
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
          <span class="material-symbols-outlined text-[24px]">{{ link.icon }}</span>
        </span>
        <span
          class="text-sm font-medium text-slate-700 group-hover:text-primary transition-colors"
        >{{ link.label }}</span>
      </button>
    </div>

    <div class="h-[500px]">
      <RealtimeChart
        :timestamp="dashboardStore.realtime.timestamp"
        :power="dashboardStore.realtime.power"
        :baseline-power="dashboardStore.realtime.baselinePower"
        :selected-range="dashboardStore.timeRange"
        :baseline-name="dashboardStore.realtime.baselineName"
        :power-source-label="dashboardStore.realtime.powerSourceLabel"
        :voltage-source-label="dashboardStore.realtime.voltageSourceLabel"
        :error-message="dashboardStore.realtimeError"
        @range-change="handleRangeChange"
      />
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <div class="lg:col-span-5">
        <HeatList
          :heats="dashboardStore.recentHeats"
          :loading="recentHeatsPending"
          :error-message="dashboardStore.recentHeatsError"
        />
      </div>
      <div class="lg:col-span-4">
        <div class="bg-white rounded-xl border border-border-light shadow-card p-6 h-full">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <span class="material-symbols-outlined text-orange-500 text-[20px]">mail</span>
              <h3 class="text-base font-bold text-slate-800">
                {{ t('nav.inbox') }}
              </h3>
            </div>
          </div>
          <div
            v-if="inboxPreview.length > 0"
            class="space-y-3"
          >
            <div
              v-for="item in inboxPreview"
              :key="item.id"
              class="p-3 bg-slate-50 rounded-lg border border-border-light hover:border-primary/30 transition-colors cursor-pointer"
              @click="navigateTo(`/heats/${item.id}`)"
            >
              <div class="flex items-center justify-between mb-1">
                <span class="text-sm font-semibold text-slate-700">{{ item.heatNo }}</span>
                <span
                  :class="[
                    'text-xs px-2 py-0.5 rounded-full font-medium',
                    item.status === 'abnormal'
                      ? 'bg-orange-100 text-orange-600'
                      : 'bg-slate-100 text-slate-500',
                  ]"
                >{{ item.status === 'abnormal' ? t('heat.statusAbnormal') : t('heat.statusPending') }}</span>
              </div>
              <p class="text-xs text-slate-500">
                {{ item.startTime }}
              </p>
              <div
                :class="[
                  'h-1 rounded-full mt-2',
                  item.status === 'abnormal' ? 'bg-red-400' : 'bg-slate-300',
                ]"
              />
            </div>
          </div>
          <div
            v-else
            class="h-full min-h-[180px] flex items-center justify-center text-sm text-slate-400"
          >
            {{ t('common.noData') }}
          </div>
        </div>
      </div>
      <div class="lg:col-span-3">
        <div class="bg-white rounded-xl border border-border-light shadow-card p-6 h-full">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <span class="material-symbols-outlined text-primary text-[20px]">task_alt</span>
              <h3 class="text-base font-bold text-slate-800">
                {{ t('task.title') }}
              </h3>
            </div>
            <span
              v-if="dashboardStore.pendingTaskPreview.length > 0"
              class="w-6 h-6 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center"
            >{{ dashboardStore.pendingTaskPreview.length }}</span>
          </div>
          <div
            v-if="dashboardStore.pendingTaskPreview.length > 0"
            class="space-y-3"
          >
            <div
              v-for="item in dashboardStore.pendingTaskPreview"
              :key="item.id"
              class="p-3 bg-slate-50 rounded-lg cursor-pointer"
              @click="navigateTo(`/tasks/${item.id}`)"
            >
              <p class="text-sm font-semibold text-slate-700 mb-1">
                {{ item.taskNo }}
              </p>
              <p class="text-xs text-slate-500">
                {{ t('task.relatedHeat') }}: {{ item.heatId }}
              </p>
              <div class="flex items-center justify-between mt-2">
                <span class="text-xs text-slate-400">{{ item.updatedAt }}</span>
                <span
                  :class="[
                    'text-xs px-2 py-0.5 rounded font-medium',
                    taskStatusClass(item.status),
                  ]"
                >{{ taskStatusLabel(item.status) }} · {{ formatTaskDeviation(item.deviationPercent) }}</span>
              </div>
            </div>
          </div>
          <div
            v-else
            class="h-full min-h-[180px] flex items-center justify-center text-sm text-slate-400"
          >
            {{ t('common.noData') }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
