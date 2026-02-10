<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElButton, ElCard, ElEmpty, ElTag } from 'element-plus'
import { useReportStore } from '@/stores/report'

const { t } = useI18n()
const router = useRouter()
const reportStore = useReportStore()

function handleView(date: string) {
  router.push(`/reports/${date}`)
}

onMounted(() => {
  void reportStore.fetchList()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-gray-900">
        {{ t('report.title') }}
      </h1>
      <div class="text-sm text-gray-500">
        {{ t('heat.totalCount') }}: {{ reportStore.list.length }}
      </div>
    </div>

    <el-card>
      <div
        v-if="reportStore.list.length > 0"
        class="space-y-3"
      >
        <div
          v-for="item in reportStore.list"
          :key="item.date"
          class="rounded-lg border border-gray-200 p-4 hover:border-primary transition"
        >
          <div class="flex items-center justify-between gap-4 flex-wrap">
            <div class="space-y-1">
              <div class="text-base font-semibold text-gray-900">
                {{ item.date }}
              </div>
              <div class="text-sm text-gray-500">
                {{ t('report.totalHeats') }}: {{ item.totalHeats }} · {{ t('report.normalRate') }}:
                {{ ((item.normalHeats / item.totalHeats) * 100).toFixed(1) }}%
              </div>
            </div>
            <div class="flex items-center gap-3">
              <el-tag type="info">
                {{ t('dashboard.avgDeviation') }}: {{ item.avgDeviation }}%
              </el-tag>
              <el-button
                type="primary"
                link
                @click="handleView(item.date)"
              >
                {{ t('inbox.viewDetail') }}
              </el-button>
            </div>
          </div>
        </div>
      </div>
      <el-empty
        v-else
        :description="t('common.noData')"
      />
    </el-card>
  </div>
</template>
