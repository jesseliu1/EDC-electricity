import type {
  HostConnectivityConfig,
  HostEdcMeta,
  PersistedConnectionState,
} from './hostConnectivityState';

export interface HostChannelMappingItem {
  id: string;
  deviceName: string;
  deviceType: string;
  area: string;
  suid: string;
  cuid: string;
  channelName: string;
  unit: string;
  lastValue: string;
  status: 'online' | 'idle';
}

export interface HostEdcResponse {
  ok: boolean;
  nodeName: string;
  checkedAt: string;
  meta: HostEdcMeta;
  channels?: HostChannelMappingItem[];
  message?: string;
}

export const appApiBase = 'http://127.0.0.1:8000/api';
const hostSyncHeaders = {
  'Content-Type': 'application/json',
  'X-ASNS-Host-Sync': 'true',
} as const;

const preferredChannelIds = [
  '2349-199',
  '2349-128',
  '2054-128',
  '2066-128',
  '769-128',
  '769-129',
];

function pickChannelByKeyword(
  catalog: readonly HostChannelMappingItem[],
  selectedIds: Set<string>,
  predicate: (item: HostChannelMappingItem) => boolean,
): void {
  const match = catalog.find((item) => !selectedIds.has(item.id) && predicate(item));
  if (match) {
    selectedIds.add(match.id);
  }
}

export function getDefaultAddedChannelIds(catalog: readonly HostChannelMappingItem[]): string[] {
  const catalogIds = new Set(catalog.map((item) => item.id));
  const selectedIds = new Set<string>();

  preferredChannelIds.forEach((channelId) => {
    if (catalogIds.has(channelId)) {
      selectedIds.add(channelId);
    }
  });

  pickChannelByKeyword(catalog, selectedIds, (item) => item.unit === 'kW' || item.channelName.includes('功率'));
  pickChannelByKeyword(catalog, selectedIds, (item) => item.unit === 'V' || item.channelName.includes('电压'));
  pickChannelByKeyword(catalog, selectedIds, (item) => item.unit === '℃' || item.channelName.includes('温'));
  pickChannelByKeyword(catalog, selectedIds, (item) => item.channelName.includes('压'));

  catalog.forEach((item) => {
    if (selectedIds.size >= 6) {
      return;
    }
    selectedIds.add(item.id);
  });

  return Array.from(selectedIds).slice(0, 6);
}

export function reconcileAddedChannelIds(
  addedChannelIds: string[],
  catalog: readonly HostChannelMappingItem[],
): string[] {
  const catalogIds = new Set(catalog.map((item) => item.id));
  const validIds = addedChannelIds.filter((channelId) => catalogIds.has(channelId));
  if (validIds.length > 0) {
    const mergedIds = Array.from(new Set(validIds));
    getDefaultAddedChannelIds(catalog).forEach((channelId) => {
      if (!mergedIds.includes(channelId)) {
        mergedIds.push(channelId);
      }
    });
    return mergedIds;
  }
  return getDefaultAddedChannelIds(catalog);
}

export function buildDisconnectedConnectionState(source: string): PersistedConnectionState {
  return {
    isConnected: false,
    machineName: '--',
    lastSyncLabel: '--',
    meta: {
      source: source || '--',
      sensorCount: 0,
      channelCount: 0,
      enabledChannelCount: 0,
    },
  };
}

export async function callHostApi(path: string, config: HostConnectivityConfig) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  return { response, data: (await response.json()) as HostEdcResponse };
}

export async function syncSelectionToBackend(
  config: HostConnectivityConfig,
  selectedChannels: HostChannelMappingItem[],
  connection: PersistedConnectionState,
) {
  const payload = selectedChannels.map((channel) => ({
    id: channel.id,
    device_name: channel.deviceName,
    device_type: channel.deviceType,
    area: channel.area,
    suid: channel.suid,
    cuid: channel.cuid,
    channel_name: channel.channelName,
    unit: channel.unit,
    last_value: channel.lastValue,
    status: channel.status,
  }));

  const connectionStatusPayload = {
    is_connected: connection.isConnected,
    machine_name: connection.machineName,
    last_sync_label: connection.lastSyncLabel,
    meta: {
      source: connection.meta.source,
      sensor_count: connection.meta.sensorCount,
      channel_count: connection.meta.channelCount,
      enabled_channel_count: connection.meta.enabledChannelCount,
    },
  };

  const saveConnection = fetch(`${appApiBase}/settings/edc-connection`, {
    method: 'PUT',
    headers: hostSyncHeaders,
    body: JSON.stringify({
      base_url: config.endpoint,
      username: config.username,
      password: config.password,
    }),
  });

  const saveChannels = fetch(`${appApiBase}/settings/host-channels`, {
    method: 'PUT',
    headers: hostSyncHeaders,
    body: JSON.stringify({ items: payload }),
  });

  const saveConnectivityStatus = fetch(`${appApiBase}/settings/host-connectivity-status`, {
    method: 'PUT',
    headers: hostSyncHeaders,
    body: JSON.stringify(connectionStatusPayload),
  });

  const [connectionResponse, channelsResponse, connectivityStatusResponse] = await Promise.all([
    saveConnection,
    saveChannels,
    saveConnectivityStatus,
  ]);
  if (!connectionResponse.ok || !channelsResponse.ok || !connectivityStatusResponse.ok) {
    throw new Error('Settings sync failed');
  }
}
