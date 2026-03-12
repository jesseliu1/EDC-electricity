<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useHeatStore } from '@/stores/heat'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()
const router = useRouter()
const heatStore = useHeatStore()

const inboxItems = computed(() =>
  heatStore.list.filter((item) => item.status === 'abnormal' || item.status === 'pending')
)

function handleView(id: string) {
  router.push(`/heats/${id}`)
}

onMounted(async () => {
  await heatStore.setStatus('abnormal')
})
</script>

<template>
  <div class="flex flex-col gap-6">
    <PageHeader
      :title="t('inbox.title')"
      description="Require immediate attention and analysis for process deviations."
    >
       <template #actions>
          <div class="flex items-center gap-2 bg-orange-50 text-orange-700 font-medium px-3 py-1.5 rounded text-sm border border-orange-200">
             <span class="material-symbols-outlined text-[16px]">warning</span>
             {{ inboxItems.length }} 异常需要处理
          </div>
       </template>
    </PageHeader>

    <div class="bg-white rounded-xl border border-border-light shadow-card overflow-hidden">
       <div class="flex items-center justify-between bg-slate-50/50 px-6 py-4 border-b border-border-light">
          <h3 class="text-sm font-bold text-slate-800 flex items-center gap-2">
            <span class="material-symbols-outlined text-primary text-[20px]">mark_email_unread</span>
            收件箱待办列表
          </h3>
       </div>

      <div v-if="inboxItems.length > 0" class="divide-y divide-border-light">
        <div
          v-for="item in inboxItems"
          :key="item.id"
          class="flex items-center justify-between p-6 hover:bg-slate-50 transition-colors group cursor-pointer border-l-4 border-l-transparent hover:border-l-red-500"
          @click="handleView(item.id)"
        >
           <div class="flex items-start gap-4">
              <div class="mt-1 w-10 h-10 rounded-full bg-red-50 text-red-600 flex items-center justify-center shrink-0 border border-red-100">
                 <span class="material-symbols-outlined">whatshot</span>
              </div>
              <div class="space-y-1">
                 <div class="flex items-center gap-2">
                   <h4 class="text-base font-bold text-slate-900 group-hover:text-primary transition-colors">
                     {{ item.heatNo }}
                   </h4>
                   <span v-if="item.status === 'abnormal'" class="bg-red-100 text-red-700 text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider">
                     High Priority
                   </span>
                 </div>
                 <div class="text-sm text-slate-500 flex items-center gap-3">
                   <span class="flex items-center gap-1"><span class="material-symbols-outlined text-[14px]">schedule</span> {{ item.startTime }}</span>
                 </div>
              </div>
           </div>
           

           <div class="flex items-center gap-6">
             <!-- Deviation Visual -->
             <div class="flex flex-col items-end gap-1">
               <span class="text-xs text-slate-400 font-semibold uppercase tracking-wider">Deviation</span>
               <span class="text-lg font-bold text-red-600 bg-red-50 px-2 rounded-md font-mono">{{ item.deviationPercent ?? '--' }}%</span>
             </div>
             
             <!-- Action Button -->
             <button
                class="w-10 h-10 rounded-full flex items-center justify-center bg-slate-50 text-slate-400 group-hover:bg-primary group-hover:text-white transition-all shadow-sm"
             >
                <span class="material-symbols-outlined">chevron_right</span>
             </button>
           </div>
        </div>
      </div>
      
      <!-- 空状态 -->
      <div v-else class="py-16 flex flex-col items-center justify-center">
        <div class="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4 border border-slate-100">
           <span class="material-symbols-outlined text-slate-300 text-3xl">inbox</span>
        </div>
        <h3 class="text-slate-800 font-bold mb-1">所有项已处理</h3>
        <p class="text-sm text-slate-500">{{ t('common.noData') }}</p>
      </div>
    </div>
  </div>
</template>
