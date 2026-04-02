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

export interface SourceSwitchResponse {
  success: boolean;
  message: string;
  source_revision: number;
  source_identity_changed: boolean;
  connection_material_changed: boolean;
  cleared_host_channel_count: number;
  cleared_host_channel_catalog_count: number;
  cleared_definition_binding_count: number;
  cleared_active_baseline_id: string;
  next_source: string;
}

export interface HostSourceConfig {
  endpoint: string;
  username: string;
  password: string;
}

export interface HostChannelCollectionResponse {
  items: HostChannelMappingItem[];
  total: number;
}

export interface HostBootstrapResponse {
  source_revision: number;
  config: HostSourceConfig;
  host_channels: HostChannelCollectionResponse;
  host_channel_catalog: HostChannelCollectionResponse;
  connectivity_status: PersistedConnectionState;
}

export interface HostRuntimeSyncResponse {
  success: boolean;
  message: string;
  source_revision: number;
  host_channels: HostChannelCollectionResponse;
  host_channel_catalog: HostChannelCollectionResponse;
  connectivity_status: PersistedConnectionState;
}

interface SourceRevisionConflictPayload {
  detail?: {
    message?: string;
    current_source_revision?: number;
  };
}

interface RawHostChannelItem {
  id?: unknown;
  device_name?: unknown;
  device_type?: unknown;
  area?: unknown;
  suid?: unknown;
  cuid?: unknown;
  channel_name?: unknown;
  unit?: unknown;
  last_value?: unknown;
  status?: unknown;
}

interface RawHostChannelCollectionResponse {
  items?: unknown;
  total?: unknown;
}

interface RawHostConnectivityMeta {
  source?: unknown;
  sensor_count?: unknown;
  channel_count?: unknown;
  enabled_channel_count?: unknown;
}

interface RawHostConnectivityStatusResponse {
  is_connected?: unknown;
  machine_name?: unknown;
  last_sync_label?: unknown;
  meta?: unknown;
}

interface RawHostBootstrapResponse {
  source_revision?: unknown;
  config?: unknown;
  host_channels?: unknown;
  host_channel_catalog?: unknown;
  connectivity_status?: unknown;
}

interface RawHostRuntimeSyncResponse {
  success?: unknown;
  message?: unknown;
  source_revision?: unknown;
  host_channels?: unknown;
  host_channel_catalog?: unknown;
  connectivity_status?: unknown;
}

export class SourceRevisionConflictError extends Error {
  currentSourceRevision: number | null;

  constructor(message: string, currentSourceRevision: number | null = null) {
    super(message);
    this.name = 'SourceRevisionConflictError';
    this.currentSourceRevision = currentSourceRevision;
  }
}

type HostRuntimeGlobals = typeof globalThis & {
  __ASNS_APP_API_BASE__?: string;
  __ASNS_HOST_API_BASE__?: string;
};

type HostImportMetaEnv = {
  VITE_ASNS_APP_API_BASE?: string;
  VITE_ASNS_HOST_API_BASE?: string;
  BASE_URL?: string;
};

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, '');
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback;
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function asBoolean(value: unknown, fallback = false): boolean {
  return typeof value === 'boolean' ? value : fallback;
}

function normalizeHostChannelItem(value: unknown): HostChannelMappingItem | null {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const raw = value as RawHostChannelItem;
  const id = asString(raw.id);
  const suid = asString(raw.suid);
  const cuid = asString(raw.cuid);
  if (!id || !suid || !cuid) {
    return null;
  }

  const status = raw.status === 'idle' ? 'idle' : 'online';
  return {
    id,
    deviceName: asString(raw.device_name),
    deviceType: asString(raw.device_type),
    area: asString(raw.area),
    suid,
    cuid,
    channelName: asString(raw.channel_name),
    unit: asString(raw.unit),
    lastValue: asString(raw.last_value, '--'),
    status,
  };
}

function normalizeHostChannelCollectionResponse(value: unknown): HostChannelCollectionResponse {
  if (!value || typeof value !== 'object') {
    return { items: [], total: 0 };
  }

  const raw = value as RawHostChannelCollectionResponse;
  const items = Array.isArray(raw.items)
    ? raw.items
        .map((item) => normalizeHostChannelItem(item))
        .filter((item): item is HostChannelMappingItem => item !== null)
    : [];
  return {
    items,
    total: asNumber(raw.total, items.length),
  };
}

function normalizeConnectionState(value: unknown): PersistedConnectionState {
  const fallback: PersistedConnectionState = {
    isConnected: false,
    machineName: '--',
    lastSyncLabel: '--',
    meta: {
      source: '--',
      sensorCount: 0,
      channelCount: 0,
      enabledChannelCount: 0,
    },
  };

  if (!value || typeof value !== 'object') {
    return fallback;
  }

  const raw = value as RawHostConnectivityStatusResponse;
  const rawMeta =
    raw.meta && typeof raw.meta === 'object' ? (raw.meta as RawHostConnectivityMeta) : {};
  return {
    isConnected: asBoolean(raw.is_connected),
    machineName: asString(raw.machine_name, '--'),
    lastSyncLabel: asString(raw.last_sync_label, '--'),
    meta: {
      source: asString(rawMeta.source, '--'),
      sensorCount: asNumber(rawMeta.sensor_count),
      channelCount: asNumber(rawMeta.channel_count),
      enabledChannelCount: asNumber(rawMeta.enabled_channel_count),
    },
  };
}

function normalizeHostBootstrapResponse(value: unknown): HostBootstrapResponse {
  const raw = (value as RawHostBootstrapResponse) || {};
  const rawConfig =
    raw.config && typeof raw.config === 'object'
      ? (raw.config as Partial<HostSourceConfig>)
      : {};

  return {
    source_revision: asNumber(raw.source_revision, 1),
    config: {
      endpoint: asString(rawConfig.endpoint),
      username: asString(rawConfig.username),
      password: asString(rawConfig.password),
    },
    host_channels: normalizeHostChannelCollectionResponse(raw.host_channels),
    host_channel_catalog: normalizeHostChannelCollectionResponse(raw.host_channel_catalog),
    connectivity_status: normalizeConnectionState(raw.connectivity_status),
  };
}

function normalizeHostRuntimeSyncResponse(value: unknown): HostRuntimeSyncResponse {
  const raw = (value as RawHostRuntimeSyncResponse) || {};
  return {
    success: asBoolean(raw.success),
    message: asString(raw.message),
    source_revision: asNumber(raw.source_revision, 1),
    host_channels: normalizeHostChannelCollectionResponse(raw.host_channels),
    host_channel_catalog: normalizeHostChannelCollectionResponse(raw.host_channel_catalog),
    connectivity_status: normalizeConnectionState(raw.connectivity_status),
  };
}

function normalizeConfigValue(value: string): string {
  return trimTrailingSlash(value.trim());
}

export function buildSourceIdentity(
  endpoint: string,
  username: string,
): string {
  return `${normalizeConfigValue(endpoint)}::${username.trim()}`;
}

function getBrowserOrigin(): string {
  if (typeof window === 'undefined') {
    return '';
  }
  return window.location.origin;
}

function getImportMetaEnv(): HostImportMetaEnv {
  return ((import.meta as ImportMeta & { env?: HostImportMetaEnv }).env ?? {});
}

function resolveAppApiBase(): string {
  const runtimeGlobals = globalThis as HostRuntimeGlobals;
  const importMetaEnv = getImportMetaEnv();
  const configuredBase =
    runtimeGlobals.__ASNS_APP_API_BASE__ ||
    importMetaEnv.VITE_ASNS_APP_API_BASE ||
    `${getBrowserOrigin()}/api`;
  return trimTrailingSlash(configuredBase);
}

function resolveHostApiBase(): string {
  const runtimeGlobals = globalThis as HostRuntimeGlobals;
  const importMetaEnv = getImportMetaEnv();
  const configuredBase = runtimeGlobals.__ASNS_HOST_API_BASE__ || importMetaEnv.VITE_ASNS_HOST_API_BASE;
  if (configuredBase) {
    return trimTrailingSlash(configuredBase);
  }

  const baseUrl = importMetaEnv.BASE_URL || '/';
  const browserOrigin = getBrowserOrigin();
  if (!browserOrigin) {
    return trimTrailingSlash(baseUrl === '/' ? '' : baseUrl);
  }
  return trimTrailingSlash(new URL(baseUrl, `${browserOrigin}/`).toString());
}

export const appApiBase = resolveAppApiBase();
const hostApiBase = resolveHostApiBase();
const hostSyncHeaders = {
  'Content-Type': 'application/json',
  'X-ASNS-Host-Sync': 'true',
} as const;

const preferredChannelIds: string[] = [];

function containsPhase(text: string): boolean {
  const lowered = text.toLowerCase();
  return lowered.includes('a相') || lowered.includes('b相') || lowered.includes('c相');
}

function containsTotal(channelName: string): boolean {
  return channelName.includes('总') || channelName.includes('總');
}

function containsFundamental(text: string): boolean {
  return text.toLowerCase().includes('基波') || text.toLowerCase().includes('fundamental');
}

function looksLikePressure(item: HostChannelMappingItem): boolean {
  const text = `${item.channelName} ${item.unit} ${item.deviceType}`.toLowerCase();
  return (
    item.unit.toLowerCase() === 'mpa' ||
    item.channelName.includes('压力') ||
    item.channelName.includes('壓力') ||
    text.includes('pressure')
  );
}

function metricChannelScore(
  item: HostChannelMappingItem,
  metricKey: 'power' | 'voltage',
): number {
  const channelName = item.channelName;
  const unit = item.unit;
  const text = `${channelName} ${unit} ${item.deviceType}`.toLowerCase();
  let score = 0;

  if (metricKey === 'power') {
    if (unit.toLowerCase() === 'kw') {
      score += 120;
    }
    if (
      channelName.includes('功率') ||
      channelName.includes('有功') ||
      channelName.includes('實功') ||
      channelName.includes('实功') ||
      text.includes('power')
    ) {
      score += 100;
    }
    if (containsTotal(channelName)) {
      score += 24;
    }
  } else {
    if (unit === 'V') {
      score += 120;
    }
    if (channelName.includes('电压') || channelName.includes('電壓') || text.includes('voltage')) {
      score += 100;
    }
    if (channelName.toLowerCase().includes('a相')) {
      score += 12;
    }
  }

  if (containsPhase(text)) {
    score += 8;
  }
  if (containsFundamental(text)) {
    score -= 16;
  }
  return score;
}

function pickBestMetricChannel(
  catalog: readonly HostChannelMappingItem[],
  selectedIds: Set<string>,
  metricKey: 'power' | 'voltage',
): void {
  const match = catalog
    .filter((item) => !selectedIds.has(item.id))
    .map((item) => ({ item, score: metricChannelScore(item, metricKey) }))
    .filter((entry) => entry.score > 0)
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }
      return left.item.channelName.localeCompare(right.item.channelName);
    })[0]?.item;
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

  pickBestMetricChannel(catalog, selectedIds, 'power');
  pickBestMetricChannel(catalog, selectedIds, 'voltage');
  const temperatureMatch = catalog.find(
    (item) => !selectedIds.has(item.id) && (item.unit === '℃' || item.channelName.includes('温') || item.channelName.includes('溫')),
  );
  if (temperatureMatch) {
    selectedIds.add(temperatureMatch.id);
  }
  const pressureMatch = catalog.find(
    (item) => !selectedIds.has(item.id) && looksLikePressure(item),
  );
  if (pressureMatch) {
    selectedIds.add(pressureMatch.id);
  }

  catalog.forEach((item) => {
    if (selectedIds.size >= 6) {
      return;
    }
    selectedIds.add(item.id);
  });

  return Array.from(selectedIds).slice(0, 6);
}

export function normalizeSourceIdentity(value: string): string {
  return normalizeConfigValue(value);
}

export function hasSourceIdentityChanged(
  previous: HostConnectivityConfig | null,
  next: HostConnectivityConfig,
): boolean {
  if (!previous) {
    return false;
  }

  return (
    normalizeConfigValue(previous.endpoint) !== normalizeConfigValue(next.endpoint) ||
    previous.username.trim() !== next.username.trim()
  );
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
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const requestPath = normalizedPath.startsWith(hostApiBase)
    ? normalizedPath
    : `${hostApiBase}${normalizedPath}`;
  const response = await fetch(requestPath, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  return { response, data: (await response.json()) as HostEdcResponse };
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  return (await response.json()) as T;
}

async function assertNoSourceRevisionConflict(response: Response): Promise<void> {
  if (response.status !== 409) {
    return;
  }
  const payload = await parseJsonResponse<SourceRevisionConflictPayload>(response);
  throw new SourceRevisionConflictError(
    payload.detail?.message || '当前来源配置已在其它入口变更，请刷新后重试',
    typeof payload.detail?.current_source_revision === 'number'
      ? payload.detail.current_source_revision
      : null,
  );
}

export async function fetchHostBootstrap(): Promise<HostBootstrapResponse> {
  const response = await fetch(`${appApiBase}/settings/host-bootstrap`);
  await assertNoSourceRevisionConflict(response);
  if (!response.ok) {
    throw new Error('Failed to load host bootstrap');
  }
  return normalizeHostBootstrapResponse(await parseJsonResponse<unknown>(response));
}

export async function syncSelectionToBackend(
  sourceRevision: number,
  selectedChannels: HostChannelMappingItem[],
  catalogChannels: HostChannelMappingItem[],
  connection: PersistedConnectionState,
) : Promise<HostRuntimeSyncResponse> {
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
  const catalogPayload = catalogChannels.map((channel) => ({
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

  const runtimeSyncPayload = {
    source_revision: sourceRevision,
    items: payload,
    catalog_items: catalogPayload,
    connection: {
      is_connected: connection.isConnected,
      machine_name: connection.machineName,
      last_sync_label: connection.lastSyncLabel,
      meta: {
        source: connection.meta.source,
        sensor_count: connection.meta.sensorCount,
        channel_count: connection.meta.channelCount,
        enabled_channel_count: connection.meta.enabledChannelCount,
      },
    },
  };

  const response = await fetch(`${appApiBase}/settings/host-runtime-sync`, {
    method: 'PUT',
    headers: hostSyncHeaders,
    body: JSON.stringify(runtimeSyncPayload),
  });
  await assertNoSourceRevisionConflict(response);
  if (!response.ok) {
    throw new Error('Settings sync failed');
  }
  return normalizeHostRuntimeSyncResponse(await parseJsonResponse<unknown>(response));
}

export async function applySourceSwitchToBackend(
  config: HostConnectivityConfig,
  sourceRevision: number,
): Promise<SourceSwitchResponse> {
  const response = await fetch(`${appApiBase}/settings/source-switch`, {
    method: 'POST',
    headers: hostSyncHeaders,
    body: JSON.stringify({
      source_revision: sourceRevision,
      base_url: config.endpoint,
      username: config.username,
      password: config.password,
      api_key: '',
    }),
  });

  await assertNoSourceRevisionConflict(response);
  if (!response.ok) {
    throw new Error('Settings sync failed');
  }

  return (await response.json()) as SourceSwitchResponse;
}
