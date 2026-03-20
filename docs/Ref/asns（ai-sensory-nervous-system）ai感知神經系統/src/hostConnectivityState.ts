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

export interface HostConnectivityDraft {
  config: HostConnectivityConfig;
  addedChannelIds: string[];
  savedAt: string;
  connection?: PersistedConnectionState | null;
}

export interface RestoredHostConnectivityDraft {
  config: HostConnectivityConfig | null;
  addedChannelIds: string[];
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

  return {
    config:
      isNonEmptyString(parsed.config?.endpoint) &&
      isNonEmptyString(parsed.config?.username) &&
      typeof parsed.config?.password === 'string'
        ? {
            endpoint: parsed.config.endpoint,
            username: parsed.config.username,
            password: parsed.config.password,
          }
        : null,
    addedChannelIds: Array.isArray(parsed.addedChannelIds)
      ? parsed.addedChannelIds.filter(
          (channelId): channelId is string =>
            typeof channelId === 'string' && channelIds.has(channelId),
        )
      : [],
    savedAt: isNonEmptyString(parsed.savedAt) ? parsed.savedAt : null,
    connection: normalizeConnectionState(parsed.connection, fallbackConnection),
  };
}

export function buildHostConnectivityDraft(
  draft: HostConnectivityDraft,
): HostConnectivityDraft {
  return {
    config: {
      endpoint: draft.config.endpoint,
      username: draft.config.username,
      password: draft.config.password,
    },
    addedChannelIds: Array.from(new Set(draft.addedChannelIds)),
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
