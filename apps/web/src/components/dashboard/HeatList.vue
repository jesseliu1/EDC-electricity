<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ArrowRight } from '@element-plus/icons-vue'

const { t } = useI18n()

type HeatStatus = 'normal' | 'abnormal' | 'pending'

interface HeatItem {
  id: string
  heatNo: string
  startTime: string
  deviationPercent: number | null
  status: HeatStatus
}

interface Props {
  heats?: HeatItem[]
}

const props = withDefaults(defineProps<Props>(), {
  heats: () => []
})

const getStatusType = (status: HeatStatus) => {
  switch (status) {
    case 'normal': return 'success'
    case 'abnormal': return 'danger'
    case 'pending': return 'info'
    default: return 'info'
  }
}

const getStatusLabel = (status: HeatStatus) => {
  switch (status) {
    case 'normal': return t('heat.statusNormal')
    case 'abnormal': return t('heat.statusAbnormal')
    case 'pending': return t('heat.statusPending')
    default: return status
  }
}
</script>

<template>
  <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100 h-full flex flex-col">
    <div class="flex justify-between items-center mb-4">
      <h3 class="text-lg font-semibold text-gray-800">
        {{ t('dashboard.recentHeats') }}
      </h3>
      <el-button
        link
        type="primary"
      >
        {{ t('common.viewAll') }} <el-icon class="ml-1">
          <ArrowRight />
        </el-icon>
      </el-button>
    </div>
    
    <div class="flex-1 overflow-hidden">
      <el-table
        :data="props.heats"
        class="w-full"
        :show-header="true"
      >
        <el-table-column
          prop="heatNo"
          :label="t('heat.heatNo')"
          min-width="140"
        />
        <el-table-column
          prop="startTime"
          :label="t('heat.startTime')"
          min-width="160"
        />
        <el-table-column
          :label="t('heat.deviation')"
          min-width="100"
        >
          <template #default="{ row }">
            <span
              :class="
                row.deviationPercent !== null && row.deviationPercent > 10
                  ? 'text-red-500 font-bold'
                  : 'text-gray-600'
              "
            >
              {{ row.deviationPercent !== null ? `${row.deviationPercent}%` : '--' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column
          :label="t('heat.status')"
          min-width="100"
        >
          <template #default="{ row }">
            <el-tag
              :type="getStatusType(row.status)"
              size="small"
              effect="plain"
            >
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>
