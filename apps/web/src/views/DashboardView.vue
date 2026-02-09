<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import StatCard from '@/components/dashboard/StatCard.vue'
import RealtimeChart from '@/components/dashboard/RealtimeChart.vue'
import HeatList from '@/components/dashboard/HeatList.vue'
import { DataLine, Odometer, Tickets, Warning } from '@element-plus/icons-vue'
import { useDashboardStore } from '@/stores/dashboard'

const { t } = useI18n()

const dashboardStore = useDashboardStore()

const stats = computed(() => [
  {
    id: 1,
    title: t('dashboard.todayHeats'),
    value: dashboardStore.stats.todayHeats,
    unit: t('dashboard.unit.heats'),
    trend: 0,
    icon: DataLine
  },
  {
    id: 2,
    title: t('dashboard.avgDeviation'),
    value: dashboardStore.stats.avgDeviation,
    unit: t('dashboard.unit.percent'),
    trend: 0,
    icon: Odometer
  },
  {
    id: 3,
    title: t('dashboard.pendingTasks'),
    value: dashboardStore.stats.pendingTasks,
    unit: t('dashboard.unit.tasks'),
    trend: 0,
    icon: Tickets
  },
  {
    id: 4,
    title: t('dashboard.baselineStatus'),
    value: dashboardStore.stats.activeBaseline || t('dashboard.baselineStatusNormal'),
    unit: '',
    trend: 0,
    icon: Warning
  }
])

const handleRangeChange = (range: '5m' | '1h' | '6h' | '24h') => {
  dashboardStore.fetchRealtime(range)
}

onMounted(() => {
  dashboardStore.fetchAll()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Stats Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <StatCard
        v-for="stat in stats"
        :key="stat.id"
        :title="stat.title"
        :value="stat.value"
        :unit="stat.unit"
        :trend="stat.trend"
        :icon="stat.icon"
      />
    </div>

    <!-- Main Content Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Chart takes 2/3 width -->
      <div class="lg:col-span-2 h-[500px]">
        <RealtimeChart
          :power="dashboardStore.realtime.power"
          :baseline-power="dashboardStore.realtime.baselinePower"
          :selected-range="dashboardStore.timeRange"
          @range-change="handleRangeChange"
        />
      </div>
      <!-- List takes 1/3 width -->
      <div class="h-[500px]">
        <HeatList :heats="dashboardStore.recentHeats" />
      </div>
    </div>
  </div>
</template>
