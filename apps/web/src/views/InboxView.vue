<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElCard, ElEmpty, ElTag, ElButton } from 'element-plus'
import { useHeatStore } from '@/stores/heat'

const { t } = useI18n()
const router = useRouter()
const heatStore = useHeatStore()

const inboxItems = computed(() =>
  heatStore.list.filter(item => item.status === 'abnormal' || item.status === 'pending')
)

function handleView(id: string) {
  router.push(`/heats/${id}`)
}

onMounted(async () => {
  await heatStore.setStatus('abnormal')
})
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold text-gray-900">
      {{ t('inbox.title') }}
    </h1>

    <el-card>
      <div
        v-if="inboxItems.length > 0"
        class="space-y-3"
      >
        <div
          v-for="item in inboxItems"
          :key="item.id"
          class="rounded-lg border border-red-200 bg-red-50 p-4"
        >
          <div class="flex items-center justify-between gap-4 flex-wrap">
            <div class="space-y-1">
              <div class="text-base font-semibold text-gray-900">
                {{ item.heatNo }}
              </div>
              <div class="text-sm text-gray-600">
                {{ item.startTime }}
              </div>
            </div>
            <div class="flex items-center gap-3">
              <el-tag type="danger">
                {{ item.deviationPercent ?? '--' }}%
              </el-tag>
              <el-button
                type="primary"
                link
                @click="handleView(item.id)"
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
