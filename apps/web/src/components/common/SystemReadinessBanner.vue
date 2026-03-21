<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRuntimeStatusStore } from '@/stores/runtimeStatus'

type Section = 'dashboard' | 'heats' | 'inbox' | 'tasks' | 'reports' | 'baselines'

const props = defineProps<{
  section: Section
  testId?: string
}>()

const { t } = useI18n()
const runtimeStatusStore = useRuntimeStatusStore()

const pipeline = computed(() => runtimeStatusStore.data.pipelines[props.section])

const tone = computed(() => {
  if (pipeline.value.code === 'showtime') {
    return {
      wrapper: 'border-amber-200 bg-amber-50 text-amber-800',
      icon: 'text-amber-600'
    }
  }
  return {
    wrapper: 'border-orange-200 bg-orange-50 text-orange-800',
    icon: 'text-orange-600'
  }
})

const title = computed(() => t(`runtime.banner.${pipeline.value.code}.title`))
const body = computed(() => t(`runtime.banner.${pipeline.value.code}.body`))
</script>

<template>
  <div
    v-if="runtimeStatusStore.loaded && pipeline.code !== 'ready'"
    :data-testid="testId"
    :class="['flex items-start gap-3 rounded-xl border p-4 text-sm', tone.wrapper]"
  >
    <span
      class="material-symbols-outlined mt-0.5"
      :class="tone.icon"
    >info</span>
    <div>
      <div class="font-semibold">
        {{ title }}
      </div>
      <div class="mt-1">
        {{ body }}
      </div>
    </div>
  </div>
</template>
