<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import {
  ElCard,
  ElDatePicker,
  ElEmpty,
  ElPagination,
  ElRadioButton,
  ElRadioGroup,
  ElTag,
  ElButton
} from 'element-plus'
import { useHeatStore } from '@/stores/heat'
import type { HeatStatus } from '@/api/heat'

const { t } = useI18n()
const router = useRouter()
const heatStore = useHeatStore()

type StatusFilter = 'all' | HeatStatus

function statusTagType(status: HeatStatus) {
  if (status === 'normal') return 'success'
  if (status === 'abnormal') return 'danger'
  return 'info'
}

function statusText(status: HeatStatus) {
  if (status === 'normal') return t('heat.statusNormal')
  if (status === 'abnormal') return t('heat.statusAbnormal')
  return t('heat.statusPending')
}

function handleStatusChange(value: string | number | boolean) {
  void heatStore.setStatus(value as StatusFilter)
}

function handleDateRangeChange(value: [Date, Date] | null) {
  void heatStore.setDateRange(value)
}

function handleViewDetail(id: string) {
  router.push(`/heats/${id}`)
}

onMounted(() => {
  void heatStore.fetchList()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between gap-4 flex-wrap">
      <h1 class="text-2xl font-bold text-gray-900">
        {{ t('heat.title') }}
      </h1>
      <div class="text-sm text-gray-500">
        {{ t('heat.totalCount') }}: {{ heatStore.total }}
      </div>
    </div>

    <el-card>
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div class="space-y-2">
          <div class="text-sm text-gray-500">
            {{ t('heat.filterDateRange') }}
          </div>
          <el-date-picker
            :model-value="heatStore.filters.dateRange"
            type="daterange"
            unlink-panels
            :range-separator="t('heat.to')"
            :start-placeholder="t('heat.startDate')"
            :end-placeholder="t('heat.endDate')"
            @update:model-value="handleDateRangeChange"
          />
        </div>
        <div class="space-y-2">
          <div class="text-sm text-gray-500">
            {{ t('heat.status') }}
          </div>
          <el-radio-group
            :model-value="heatStore.filters.status"
            @change="handleStatusChange"
          >
            <el-radio-button label="all">
              {{ t('common.viewAll') }}
            </el-radio-button>
            <el-radio-button label="normal">
              {{ t('heat.statusNormal') }}
            </el-radio-button>
            <el-radio-button label="abnormal">
              {{ t('heat.statusAbnormal') }}
            </el-radio-button>
            <el-radio-button label="pending">
              {{ t('heat.statusPending') }}
            </el-radio-button>
          </el-radio-group>
        </div>
      </div>
    </el-card>

    <el-card>
      <div
        v-if="heatStore.list.length > 0"
        class="space-y-3"
      >
        <div
          v-for="item in heatStore.list"
          :key="item.id"
          class="rounded-lg border border-gray-200 p-4 hover:border-primary transition"
        >
          <div class="flex items-center justify-between gap-4 flex-wrap">
            <div class="space-y-1">
              <div class="text-base font-semibold text-gray-900">
                {{ item.heatNo }}
              </div>
              <div
                v-if="item.description"
                class="text-sm text-gray-400"
              >
                {{ item.description }}
              </div>
              <div class="text-sm text-gray-500">
                {{ item.startTime }} - {{ item.endTime }}
              </div>
            </div>

            <div class="flex items-center gap-4 flex-wrap">
              <el-tag :type="statusTagType(item.status)">
                {{ statusText(item.status) }}
              </el-tag>
              <el-button
                type="primary"
                link
                @click="handleViewDetail(item.id)"
              >
                {{ t('inbox.viewDetail') }}
              </el-button>
            </div>
          </div>
        </div>

        <div class="pt-2 flex justify-end">
          <el-pagination
            background
            layout="total, sizes, prev, pager, next"
            :current-page="heatStore.page"
            :page-size="heatStore.pageSize"
            :page-sizes="[10, 20, 50]"
            :total="heatStore.total"
            @update:current-page="heatStore.setPage"
            @update:page-size="heatStore.setPageSize"
          />
        </div>
      </div>

      <el-empty
        v-else
        :description="t('common.noData')"
      />
    </el-card>
  </div>
</template>
