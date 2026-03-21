import { defineStore } from 'pinia'
import { settingApi } from '@/api/setting'

export type RuntimeStatusCode =
  | 'ready'
  | 'showtime'
  | 'host_disconnected'
  | 'edc_unconfigured'
  | 'no_enabled_channels'
  | 'heat_inference_disabled'

export interface RuntimePipelineStatus {
  code: RuntimeStatusCode
  ready: boolean
}

export interface RuntimeStatusState {
  overallCode: Exclude<RuntimeStatusCode, 'heat_inference_disabled'>
  host: {
    isConnected: boolean
    machineName: string
    lastSyncLabel: string
    source: string
    sensorCount: number
    channelCount: number
    enabledChannelCount: number
  }
  edc: {
    configured: boolean
    baseUrl: string
    usernamePresent: boolean
    hostChannelTotal: number
    enabledChannelCount: number
  }
  activeBaseline: {
    id: string | null
    name: string | null
    status: string | null
  }
  runtime: {
    showtimeEnabled: boolean
    liveHeatInferenceEnabled: boolean
    baselineLengthScopeMode: 'definition' | 'system' | 'production_line'
  }
  pipelines: {
    dashboard: RuntimePipelineStatus
    heats: RuntimePipelineStatus
    inbox: RuntimePipelineStatus
    tasks: RuntimePipelineStatus
    reports: RuntimePipelineStatus
    baselines: RuntimePipelineStatus
  }
}

const defaultPipeline = (): RuntimePipelineStatus => ({
  code: 'host_disconnected',
  ready: false
})

const defaultState = (): RuntimeStatusState => ({
  overallCode: 'host_disconnected',
  host: {
    isConnected: false,
    machineName: '--',
    lastSyncLabel: '--',
    source: '--',
    sensorCount: 0,
    channelCount: 0,
    enabledChannelCount: 0
  },
  edc: {
    configured: false,
    baseUrl: '',
    usernamePresent: false,
    hostChannelTotal: 0,
    enabledChannelCount: 0
  },
  activeBaseline: {
    id: null,
    name: null,
    status: null
  },
  runtime: {
    showtimeEnabled: false,
    liveHeatInferenceEnabled: false,
    baselineLengthScopeMode: 'definition'
  },
  pipelines: {
    dashboard: defaultPipeline(),
    heats: defaultPipeline(),
    inbox: defaultPipeline(),
    tasks: defaultPipeline(),
    reports: defaultPipeline(),
    baselines: defaultPipeline()
  }
})

export const useRuntimeStatusStore = defineStore('runtime-status', {
  state: () => ({
    data: defaultState(),
    loading: false,
    loaded: false
  }),
  getters: {
    headerCode: state => state.data.overallCode
  },
  actions: {
    async fetchRuntimeStatus() {
      this.loading = true
      try {
        const response = await settingApi.getRuntimeStatus()
        this.data = {
          overallCode: response.overall_code,
          host: {
            isConnected: response.host.is_connected,
            machineName: response.host.machine_name,
            lastSyncLabel: response.host.last_sync_label,
            source: response.host.meta.source,
            sensorCount: response.host.meta.sensor_count,
            channelCount: response.host.meta.channel_count,
            enabledChannelCount: response.host.meta.enabled_channel_count
          },
          edc: {
            configured: response.edc.configured,
            baseUrl: response.edc.base_url,
            usernamePresent: response.edc.username_present,
            hostChannelTotal: response.edc.host_channel_total,
            enabledChannelCount: response.edc.enabled_channel_count
          },
          activeBaseline: {
            id: response.active_baseline.id,
            name: response.active_baseline.name,
            status: response.active_baseline.status
          },
          runtime: {
            showtimeEnabled: response.runtime.showtime_enabled,
            liveHeatInferenceEnabled: response.runtime.live_heat_inference_enabled,
            baselineLengthScopeMode: response.runtime.baseline_length_scope_mode
          },
          pipelines: {
            dashboard: response.pipelines.dashboard,
            heats: response.pipelines.heats,
            inbox: response.pipelines.inbox,
            tasks: response.pipelines.tasks,
            reports: response.pipelines.reports,
            baselines: response.pipelines.baselines
          }
        }
        this.loaded = true
      } catch (error) {
        console.warn('Runtime status fallback to default.', error)
        this.data = defaultState()
      } finally {
        this.loading = false
      }
    }
  }
})
