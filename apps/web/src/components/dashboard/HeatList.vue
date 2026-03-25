<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

const { t } = useI18n()
const router = useRouter()

type HeatStatus = 'normal' | 'abnormal' | 'pending'

interface HeatItem {
  id: string
  heatNo: string
  startTime: string
  duration?: string
  deviationPercent: number | null
  status: HeatStatus
}

interface Props {
  heats?: HeatItem[]
  loading?: boolean
  errorMessage?: string | null
}

withDefaults(defineProps<Props>(), {
  heats: () => [],
  loading: false,
  errorMessage: null,
})

// 偏差值颜色
const getDeviationClass = (val: number | null): string => {
  if (val === null) return 'text-slate-600 font-semibold'
  if (val > 10) return 'text-red-500 font-bold'
  if (val > 5) return 'text-orange-500 font-semibold'
  return 'text-slate-600'
}

const formatDeviation = (value: number | null): string => {
  return value === null ? t('heat.deviationPending') : `+${value}%`
}

// 状态圆点颜色
const getStatusDotClass = (status: HeatStatus): string => {
  switch (status) {
    case 'normal':
      return 'bg-green-500'
    case 'abnormal':
      return 'bg-red-500'
    case 'pending':
      return 'bg-slate-400'
    default:
      return 'bg-slate-400'
  }
}

const getStatusLabel = (status: HeatStatus): string => {
  switch (status) {
    case 'normal':
      return t('heat.statusNormal')
    case 'abnormal':
      return t('heat.statusAbnormal')
    case 'pending':
      return t('heat.statusPending')
    default:
      return status
  }
}

const handleViewDetail = (heatNo: string) => {
  router.push(`/heats/${heatNo}`)
}
</script>

<template>
  <div
    class="bg-white rounded-xl shadow-card border border-border-light h-full flex flex-col overflow-hidden"
  >
    <!-- 标题区 -->
    <div
      class="flex items-center justify-between px-6 py-4 border-b border-border-light bg-slate-50/50"
    >
      <div class="flex items-center gap-2">
        <span class="material-symbols-outlined text-slate-500 text-[20px]">list_alt</span>
        <h3 class="text-base font-bold text-slate-800">
          {{ t('dashboard.recentHeats') }}
        </h3>
      </div>
      <button
        class="text-sm text-primary font-medium hover:text-primary-dark flex items-center gap-1 transition-colors"
        @click="router.push('/heats')"
      >
        {{ t('common.viewAll') }}
        <span class="material-symbols-outlined text-[16px]">chevron_right</span>
      </button>
    </div>

    <!-- 原生表格 -->
    <div class="flex-1 overflow-y-auto">
      <table class="w-full">
        <thead class="sticky top-0 z-10 bg-white">
          <tr class="border-b border-border-light">
            <th
              class="text-left text-xs font-semibold text-slate-400 uppercase tracking-wider px-6 py-3"
            >
              {{ t('heat.heatNo') }}
            </th>
            <th
              class="text-left text-xs font-semibold text-slate-400 uppercase tracking-wider px-4 py-3"
            >
              {{ t('heat.startTime') }}
            </th>
            <th
              class="text-left text-xs font-semibold text-slate-400 uppercase tracking-wider px-4 py-3"
            >
              {{ t('heat.deviation') }}
            </th>
            <th
              class="text-left text-xs font-semibold text-slate-400 uppercase tracking-wider px-4 py-3"
            >
              {{ t('heat.status') }}
            </th>
            <th class="px-4 py-3" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="heat in heats"
            :key="heat.id"
            class="border-b border-border-light last:border-0 hover:bg-slate-50 transition-colors cursor-pointer group"
            @click="handleViewDetail(heat.heatNo)"
          >
            <td class="px-6 py-3.5">
              <span class="text-sm font-medium text-slate-800">{{
                heat.heatNo
              }}</span>
            </td>
            <td class="px-4 py-3.5">
              <span class="text-sm text-slate-600">{{ heat.startTime }}</span>
            </td>
            <td class="px-4 py-3.5">
              <span
                :data-testid="`dashboard-recent-heat-deviation-${heat.id}`"
                :class="['text-sm', getDeviationClass(heat.deviationPercent)]"
              >
                {{ formatDeviation(heat.deviationPercent) }}
              </span>
            </td>
            <td class="px-4 py-3.5">
              <span class="flex items-center gap-2">
                <span
                  :class="[
                    'w-2 h-2 rounded-full',
                    getStatusDotClass(heat.status),
                  ]"
                />
                <span class="text-sm text-slate-600">{{
                  getStatusLabel(heat.status)
                }}</span>
              </span>
            </td>
            <td class="px-4 py-3.5 text-right">
              <span
                class="text-xs text-primary font-medium opacity-0 group-hover:opacity-100 transition-opacity"
              >{{ t('common.detail') }}</span>
            </td>
          </tr>
          <!-- 空状态 -->
          <tr v-if="loading && heats.length === 0">
            <td
              colspan="5"
              class="px-6 py-10 text-center"
              data-testid="dashboard-recent-heats-loading"
            >
              <span class="material-symbols-outlined text-slate-300 text-4xl">progress_activity</span>
              <p class="text-sm text-slate-400 mt-2">
                {{ t('common.loading') }}
              </p>
            </td>
          </tr>
          <tr v-else-if="errorMessage && heats.length === 0">
            <td
              colspan="5"
              class="px-6 py-10 text-center"
              data-testid="dashboard-recent-heats-error"
            >
              <span class="material-symbols-outlined text-amber-400 text-4xl">warning</span>
              <p class="text-sm text-slate-600 mt-2 font-medium">
                {{ errorMessage }}
              </p>
              <p class="text-xs text-slate-400 mt-2">
                {{ t('dashboard.recentHeatsReloadHint') }}
              </p>
            </td>
          </tr>
          <tr v-else-if="heats.length === 0">
            <td
              colspan="5"
              class="px-6 py-10 text-center"
            >
              <span class="material-symbols-outlined text-slate-300 text-4xl">inbox</span>
              <p class="text-sm text-slate-400 mt-2">
                暂无炉次数据
              </p>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
