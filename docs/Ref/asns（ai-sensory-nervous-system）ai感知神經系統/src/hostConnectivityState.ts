export interface HostConnectivityConfig {
  endpoint: string;
  username: string;
  password: string;
}

export interface HostEdcMeta {
  source: string;
  sensorCount: number;
  channelCount: number;
  enabledChannelCount: number;
}

export interface PersistedConnectionState {
  isConnected: boolean;
  machineName: string;
  lastSyncLabel: string;
  meta: HostEdcMeta;
}

export interface PersistedHostChannelDraftItem {
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

export interface HostConnectivityDraft {
  config: HostConnectivityConfig;
  sourceIdentity?: string | null;
  baseSourceRevision?: number | null;
  addedChannelIds: string[];
  addedChannels?: PersistedHostChannelDraftItem[];
  channelCatalogSource?: string | null;
  savedAt: string;
  connection?: PersistedConnectionState | null;
}

export interface RestoredHostConnectivityDraft {
  config: HostConnectivityConfig | null;
  sourceIdentity: string | null;
  baseSourceRevision: number | null;
  addedChannelIds: string[];
  addedChannels: PersistedHostChannelDraftItem[];
  channelCatalogSource: string | null;
  savedAt: string | null;
  connection: PersistedConnectionState | null;
}

export interface WindowToggleState {
  activeWin: string;
  openWindowIds: string[];
}

export const hostSettingsStorageKey = 'asns-host-connectivity-draft';

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function normalizeSourceValue(value: string): string {
  return value.trim().replace(/\/+$/, '');
}

function normalizeDraftChannel(value: unknown): PersistedHostChannelDraftItem | null {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const candidate = value as Partial<PersistedHostChannelDraftItem>;
  if (
    !isNonEmptyString(candidate.id) ||
    !isNonEmptyString(candidate.deviceName) ||
    !isNonEmptyString(candidate.deviceType) ||
    !isNonEmptyString(candidate.area) ||
    !isNonEmptyString(candidate.suid) ||
    !isNonEmptyString(candidate.cuid) ||
    !isNonEmptyString(candidate.channelName) ||
    !isNonEmptyString(candidate.unit) ||
    !isNonEmptyString(candidate.lastValue) ||
    (candidate.status !== 'online' && candidate.status !== 'idle')
  ) {
    return null;
  }

  return {
    id: candidate.id,
    deviceName: candidate.deviceName,
    deviceType: candidate.deviceType,
    area: candidate.area,
    suid: candidate.suid,
    cuid: candidate.cuid,
    channelName: candidate.channelName,
    unit: candidate.unit,
    lastValue: candidate.lastValue,
    status: candidate.status,
  };
}

function dedupeDraftChannels(
  items: PersistedHostChannelDraftItem[],
): PersistedHostChannelDraftItem[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.id)) {
      return false;
    }
    seen.add(item.id);
    return true;
  });
}

function normalizeConnectionState(
  value: unknown,
  fallback: PersistedConnectionState,
): PersistedConnectionState | null {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const candidate = value as Partial<PersistedConnectionState>;
  if (typeof candidate.isConnected !== 'boolean') {
    return null;
  }

  return {
    isConnected: candidate.isConnected,
    machineName: isNonEmptyString(candidate.machineName)
      ? candidate.machineName
      : fallback.machineName,
    lastSyncLabel: isNonEmptyString(candidate.lastSyncLabel)
      ? candidate.lastSyncLabel
      : fallback.lastSyncLabel,
    meta: {
      source: isNonEmptyString(candidate.meta?.source)
        ? candidate.meta.source
        : fallback.meta.source,
      sensorCount:
        typeof candidate.meta?.sensorCount === 'number'
          ? candidate.meta.sensorCount
          : fallback.meta.sensorCount,
      channelCount:
        typeof candidate.meta?.channelCount === 'number'
          ? candidate.meta.channelCount
          : fallback.meta.channelCount,
      enabledChannelCount:
        typeof candidate.meta?.enabledChannelCount === 'number'
          ? candidate.meta.enabledChannelCount
          : fallback.meta.enabledChannelCount,
    },
  };
}

export function restoreHostConnectivityDraft(
  raw: string | null,
  availableChannelIds: string[],
  fallbackConnection: PersistedConnectionState,
): RestoredHostConnectivityDraft | null {
  if (!raw) {
    return null;
  }

  const parsed = JSON.parse(raw) as Partial<HostConnectivityDraft>;
  const channelIds = new Set(availableChannelIds);
  const config =
    isNonEmptyString(parsed.config?.endpoint) &&
    isNonEmptyString(parsed.config?.username) &&
    typeof parsed.config?.password === 'string'
      ? {
          endpoint: parsed.config.endpoint,
          username: parsed.config.username,
          password: parsed.config.password,
        }
      : null;
  const sourceIdentity = isNonEmptyString(parsed.sourceIdentity)
    ? normalizeSourceValue(parsed.sourceIdentity)
    : null;
  const baseSourceRevision =
    typeof parsed.baseSourceRevision === 'number' && Number.isInteger(parsed.baseSourceRevision)
      ? parsed.baseSourceRevision
      : null;
  const channelCatalogSource = isNonEmptyString(parsed.channelCatalogSource)
    ? normalizeSourceValue(parsed.channelCatalogSource)
    : null;
  const canRestoreCatalog =
    channelCatalogSource !== null &&
    sourceIdentity !== null &&
    channelCatalogSource === sourceIdentity;
  const restoredChannels = canRestoreCatalog && Array.isArray(parsed.addedChannels)
    ? dedupeDraftChannels(parsed.addedChannels.map(normalizeDraftChannel).filter(
        (item): item is PersistedHostChannelDraftItem => item !== null,
      ))
    : [];
  const restoredChannelIds = restoredChannels.length > 0
    ? restoredChannels.map((item) => item.id)
    : canRestoreCatalog && Array.isArray(parsed.addedChannelIds)
      ? parsed.addedChannelIds.filter(
          (channelId): channelId is string =>
            typeof channelId === 'string' && channelIds.has(channelId),
        )
      : [];

  return {
    config,
    sourceIdentity,
    baseSourceRevision,
    addedChannelIds: restoredChannelIds,
    addedChannels: restoredChannels,
    channelCatalogSource: canRestoreCatalog ? channelCatalogSource : null,
    savedAt: isNonEmptyString(parsed.savedAt) ? parsed.savedAt : null,
    connection: normalizeConnectionState(parsed.connection, fallbackConnection),
  };
}

export function buildHostConnectivityDraft(
  draft: HostConnectivityDraft,
): HostConnectivityDraft {
  const normalizedAddedChannels = Array.isArray(draft.addedChannels)
    ? dedupeDraftChannels(draft.addedChannels.map(normalizeDraftChannel).filter(
        (item): item is PersistedHostChannelDraftItem => item !== null,
      ))
    : [];

  return {
    config: {
      endpoint: draft.config.endpoint,
      username: draft.config.username,
      password: draft.config.password,
    },
    sourceIdentity: isNonEmptyString(draft.sourceIdentity)
      ? normalizeSourceValue(draft.sourceIdentity)
      : null,
    baseSourceRevision:
      typeof draft.baseSourceRevision === 'number' && Number.isInteger(draft.baseSourceRevision)
        ? draft.baseSourceRevision
        : null,
    addedChannelIds: Array.from(new Set(draft.addedChannelIds)),
    addedChannels: normalizedAddedChannels,
    channelCatalogSource: isNonEmptyString(draft.channelCatalogSource)
      ? normalizeSourceValue(draft.channelCatalogSource)
      : null,
    savedAt: draft.savedAt,
    connection: draft.connection
      ? {
          isConnected: draft.connection.isConnected,
          machineName: draft.connection.machineName,
          lastSyncLabel: draft.connection.lastSyncLabel,
          meta: { ...draft.connection.meta },
        }
      : null,
  };
}

export function isHostConnectivityDraftCurrent(
  draft: RestoredHostConnectivityDraft | null,
  currentSourceIdentity: string | null,
  currentSourceRevision: number,
): boolean {
  if (!draft) {
    return false;
  }
  if (!isNonEmptyString(currentSourceIdentity)) {
    return false;
  }
  if (!isNonEmptyString(draft.sourceIdentity)) {
    return false;
  }
  if (
    typeof draft.baseSourceRevision !== 'number' ||
    !Number.isInteger(draft.baseSourceRevision)
  ) {
    return false;
  }
  return (
    normalizeSourceValue(draft.sourceIdentity) === normalizeSourceValue(currentSourceIdentity) &&
    draft.baseSourceRevision === currentSourceRevision
  );
}

export function clearHostConnectivityDraftStorage(): void {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.removeItem(hostSettingsStorageKey);
}

export function toggleWindowState(
  openWindowIds: string[],
  appId: string,
): WindowToggleState {
  if (openWindowIds.includes(appId)) {
    return {
      activeWin: appId,
      openWindowIds: [...openWindowIds],
    };
  }

  return {
    activeWin: appId,
    openWindowIds: [...openWindowIds, appId],
  };
}
