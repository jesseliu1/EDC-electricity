import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronRight,
  Database,
  Info,
  Key,
  LayoutGrid,
  Power,
  RefreshCw,
  Save,
  Search,
  Settings,
  User,
} from 'lucide-react';
import {
  buildHostConnectivityDraft,
  clearHostConnectivityDraftStorage,
  hostSettingsStorageKey,
  isHostConnectivityDraftCurrent,
  restoreHostConnectivityDraft,
  type HostEdcMeta,
  type PersistedConnectionState,
} from './hostConnectivityState';
import {
  buildSourceIdentity,
  buildDisconnectedConnectionState,
  callHostApi,
  applySourceSwitchToBackend,
  fetchHostBootstrap,
  hasSourceIdentityChanged,
  reconcileAddedChannelIds,
  SourceRevisionConflictError,
  syncSelectionToBackend,
  type HostChannelMappingItem,
} from './hostConnectivitySync';

export interface SettingsViewConfig {
  endpoint: string;
  username: string;
  password: string;
}

export interface SettingsViewProps {
  config: SettingsViewConfig;
  setConfig: (config: SettingsViewConfig) => void;
  t: (key: string) => string;
  isConnected: boolean;
  setIsConnected: (connected: boolean) => void;
}

type ChannelMappingItem = HostChannelMappingItem;
type SourceAwareAction = 'connect' | 'sync' | 'apply';

interface SourceSwitchDialogState {
  action: SourceAwareAction;
  nextSource: string;
}

interface PreparedSourceAwareState {
  sourceRevision: number;
  sourceIdentityChanged: boolean;
  connectionMaterialChanged: boolean;
  channelIds: string[];
  catalog: ChannelMappingItem[];
  catalogSource: string | null;
  connection: PersistedConnectionState;
  message: string | null;
}

const emptyMeta: HostEdcMeta = {
  source: '--',
  sensorCount: 0,
  channelCount: 0,
  enabledChannelCount: 0,
};

export default function SettingsView({ config, setConfig, t, isConnected, setIsConnected }: SettingsViewProps) {
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [query, setQuery] = useState('');
  const [expandedDevices, setExpandedDevices] = useState<Record<string, boolean>>({});
  const [channelCatalog, setChannelCatalog] = useState<ChannelMappingItem[]>([]);
  const [addedChannelIds, setAddedChannelIds] = useState<string[]>([]);
  const [channelCatalogSource, setChannelCatalogSource] = useState<string | null>(null);
  const [currentSourceIdentity, setCurrentSourceIdentity] = useState<string | null>(null);
  const [currentSourceRevision, setCurrentSourceRevision] = useState(1);
  const [lastAppliedConfig, setLastAppliedConfig] = useState<SettingsViewConfig | null>(null);
  const [statusMessage, setStatusMessage] = useState('');
  const [saveFeedback, setSaveFeedback] = useState('');
  const [machineName, setMachineName] = useState('--');
  const [lastSyncLabel, setLastSyncLabel] = useState('--');
  const [meta, setMeta] = useState<HostEdcMeta>(emptyMeta);
  const [sourceSwitchDialog, setSourceSwitchDialog] = useState<SourceSwitchDialogState | null>(null);
  const sourceSwitchConfirmRef = useRef<((confirmed: boolean) => void) | null>(null);

  const currentConnectionState = (): PersistedConnectionState => ({
    isConnected,
    machineName,
    lastSyncLabel,
    meta,
  });

  const applyConnectionState = (connection: PersistedConnectionState) => {
    setIsConnected(connection.isConnected);
    setMachineName(connection.machineName);
    setLastSyncLabel(connection.lastSyncLabel);
    setMeta(connection.meta);
  };

  const mergeCatalogChannels = (
    primary: ChannelMappingItem[],
    fallback: ChannelMappingItem[],
  ): ChannelMappingItem[] => {
    const merged = new Map<string, ChannelMappingItem>();
    primary.forEach((item) => merged.set(item.id, item));
    fallback.forEach((item) => {
      if (!merged.has(item.id)) {
        merged.set(item.id, item);
      }
    });
    return Array.from(merged.values());
  };

  const filterSelectedChannelIds = (
    channelIds: string[],
    catalog: ChannelMappingItem[],
  ): string[] => {
    const catalogIds = new Set(catalog.map((item) => item.id));
    return Array.from(new Set(channelIds.filter((channelId) => catalogIds.has(channelId))));
  };

  const selectChannelsFromCatalog = (
    channelIds: string[],
    catalog: ChannelMappingItem[],
  ): ChannelMappingItem[] =>
    channelIds
      .map((channelId) => catalog.find((item) => item.id === channelId))
      .filter((item): item is ChannelMappingItem => Boolean(item));

  const clearSourceScopedSelection = () => {
    setChannelCatalog([]);
    setAddedChannelIds([]);
    setChannelCatalogSource(null);
  };

  const hasSourceScopedState = () =>
    channelCatalog.length > 0 ||
    addedChannelIds.length > 0 ||
    Boolean(channelCatalogSource) ||
    isConnected ||
    meta.enabledChannelCount > 0;

  const resolveActionLabel = (action: SourceAwareAction) => {
    if (action === 'connect') {
      return t('testConnection');
    }
    if (action === 'sync') {
      return t('syncChannels');
    }
    return t('apply');
  };

  const requestSourceSwitchConfirmation = (action: SourceAwareAction) =>
    new Promise<boolean>((resolve) => {
      sourceSwitchConfirmRef.current = resolve;
      setSourceSwitchDialog({
        action,
        nextSource: config.endpoint.trim() || '--',
      });
    });

  const closeSourceSwitchDialog = (confirmed: boolean) => {
    setSourceSwitchDialog(null);
    sourceSwitchConfirmRef.current?.(confirmed);
    sourceSwitchConfirmRef.current = null;
  };

  const filteredChannels = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return channelCatalog;
    }
    return channelCatalog.filter((item) =>
      [item.deviceName, item.deviceType, item.area, item.channelName, item.suid, item.cuid]
        .join(' ')
        .toLowerCase()
        .includes(normalized),
    );
  }, [channelCatalog, query]);

  const groupedChannels = useMemo(() => {
    const groups = new Map<string, ChannelMappingItem[]>();
    filteredChannels.forEach((item) => {
      const existing = groups.get(item.deviceName) || [];
      existing.push(item);
      groups.set(item.deviceName, existing);
    });
    return Array.from(groups.entries()).map(([deviceName, items]) => ({
      deviceName,
      deviceType: items[0]?.deviceType || '',
      area: items[0]?.area || '',
      items,
    }));
  }, [filteredChannels]);

  const addedChannelIdSet = useMemo(() => new Set(addedChannelIds), [addedChannelIds]);

  const addedChannels = useMemo(
    () =>
      addedChannelIds
        .map((channelId) => channelCatalog.find((item) => item.id === channelId))
        .filter((item): item is ChannelMappingItem => Boolean(item)),
    [addedChannelIds, channelCatalog],
  );

  const addedChannelGroups = useMemo(() => {
    const groups = new Map<string, ChannelMappingItem[]>();
    addedChannels.forEach((item) => {
      const existing = groups.get(item.deviceName) || [];
      existing.push(item);
      groups.set(item.deviceName, existing);
    });
    return Array.from(groups.entries()).map(([deviceName, items]) => ({
      deviceName,
      deviceType: items[0]?.deviceType || '',
      area: items[0]?.area || '',
      items,
    }));
  }, [addedChannels]);

  const loadHostBootstrap = React.useCallback(async (clearDraftFirst = false) => {
    if (typeof window === 'undefined') {
      return;
    }

    if (clearDraftFirst) {
      clearHostConnectivityDraftStorage();
    }

    const bootstrap = await fetchHostBootstrap();
    const backendConfig: SettingsViewConfig = {
      endpoint: bootstrap.config.endpoint,
      username: bootstrap.config.username,
      password: bootstrap.config.password,
    };
    const backendCatalog = mergeCatalogChannels(
      bootstrap.host_channel_catalog.items,
      bootstrap.host_channels.items,
    );
    const backendSelectedIds = bootstrap.host_channels.items.map((item) => item.id);
    const backendSourceIdentity = buildSourceIdentity(
      backendConfig.endpoint,
      backendConfig.username,
    );

    const restored = restoreHostConnectivityDraft(
      window.localStorage.getItem(hostSettingsStorageKey),
      backendCatalog.map((item) => item.id),
      bootstrap.connectivity_status,
    );
    const shouldUseDraft = isHostConnectivityDraftCurrent(
      restored,
      backendSourceIdentity,
      bootstrap.source_revision,
    );
    if (!shouldUseDraft && restored) {
      clearHostConnectivityDraftStorage();
    }

    const effectiveCatalog = shouldUseDraft
      ? mergeCatalogChannels(backendCatalog, restored.addedChannels)
      : backendCatalog;
    const effectiveSelectedIds = shouldUseDraft
      ? filterSelectedChannelIds(
          restored.addedChannels.length > 0
            ? restored.addedChannels.map((item) => item.id)
            : restored.addedChannelIds,
          effectiveCatalog,
        )
      : filterSelectedChannelIds(backendSelectedIds, effectiveCatalog);

    setCurrentSourceRevision(bootstrap.source_revision);
    setCurrentSourceIdentity(backendSourceIdentity);
    setLastAppliedConfig(backendConfig);
    setConfig(shouldUseDraft && restored.config ? restored.config : backendConfig);
    applyConnectionState(bootstrap.connectivity_status);
    setChannelCatalog(effectiveCatalog);
    setChannelCatalogSource(backendSourceIdentity);
    setAddedChannelIds(effectiveSelectedIds);
  }, [setConfig]);

  useEffect(() => {
    void loadHostBootstrap();
  }, [loadHostBootstrap]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const handleStorage = (event: StorageEvent) => {
      if (event.key !== hostSettingsStorageKey || event.newValue !== null) {
        return;
      }
      void loadHostBootstrap();
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, [loadHostBootstrap]);

  useEffect(() => {
    if (!saveFeedback) {
      return;
    }
    const timer = window.setTimeout(() => {
      setSaveFeedback('');
    }, 3200);
    return () => window.clearTimeout(timer);
  }, [saveFeedback]);

  const toggleDevice = (deviceName: string) => {
    setExpandedDevices((prev) => ({ ...prev, [deviceName]: !prev[deviceName] }));
  };

  const addChannel = (channelId: string) => {
    setAddedChannelIds((prev) => (prev.includes(channelId) ? prev : [...prev, channelId]));
  };

  const addGroupChannels = (deviceName: string) => {
    const groupIds = channelCatalog.filter((item) => item.deviceName === deviceName).map((item) => item.id);
    setAddedChannelIds((prev) => [...prev, ...groupIds.filter((id) => !prev.includes(id))]);
  };

  const removeChannel = (channelId: string) => {
    setAddedChannelIds((prev) => prev.filter((id) => id !== channelId));
  };

  const removeGroupChannels = (deviceName: string) => {
    const groupIds = new Set(channelCatalog.filter((item) => item.deviceName === deviceName).map((item) => item.id));
    setAddedChannelIds((prev) => prev.filter((id) => !groupIds.has(id)));
  };

  const formatCheckedAt = (value: string) => {
    try {
      return new Date(value).toLocaleString('zh-CN', { hour12: false });
    } catch {
      return value;
    }
  };

  const hasConnectionMaterialChanged = (
    previous: SettingsViewConfig | null,
    next: SettingsViewConfig,
  ) => {
    if (!previous) {
      return false;
    }
    return (
      buildSourceIdentity(previous.endpoint, previous.username) !==
        buildSourceIdentity(next.endpoint, next.username) ||
      previous.password !== next.password
    );
  };

  const syncAddedChannelsWithCatalog = (
    baseAddedChannelIds: string[],
    channels: ChannelMappingItem[],
  ) => {
    const nextAddedChannelIds = reconcileAddedChannelIds(baseAddedChannelIds, channels);
    setAddedChannelIds(nextAddedChannelIds);
    return nextAddedChannelIds;
  };

  const writeDraft = (
    savedAt: string,
    connection: PersistedConnectionState,
    channelIds = addedChannelIds,
    catalog = channelCatalog,
    catalogSource = channelCatalogSource,
  ) => {
    if (typeof window === 'undefined') {
      return;
    }
    window.localStorage.setItem(
      hostSettingsStorageKey,
      JSON.stringify(
        buildHostConnectivityDraft({
          config,
          sourceIdentity: currentSourceIdentity,
          baseSourceRevision: currentSourceRevision,
          addedChannelIds: channelIds,
          addedChannels: channelIds
            .map((channelId) => catalog.find((item) => item.id === channelId))
            .filter((item): item is ChannelMappingItem => Boolean(item)),
          channelCatalogSource: catalogSource,
          savedAt,
          connection,
        }),
      ),
    );
  };

  const handleSaveDraft = () => {
    const savedAt = new Date().toISOString();
    writeDraft(savedAt, currentConnectionState(), addedChannelIds, channelCatalog, channelCatalogSource);
    const message = `${t('draftSaved')} ${formatCheckedAt(savedAt)}`;
    setStatusMessage(message);
    setSaveFeedback(message);
  };

  const applyRuntimeSyncResponse = (
    nextSourceRevision: number,
    nextConfig: SettingsViewConfig,
    nextCatalog: ChannelMappingItem[],
    nextSelectedIds: string[],
    connection: PersistedConnectionState,
  ) => {
    const nextSourceIdentity = buildSourceIdentity(nextConfig.endpoint, nextConfig.username);
    setCurrentSourceRevision(nextSourceRevision);
    setCurrentSourceIdentity(nextSourceIdentity);
    setLastAppliedConfig(nextConfig);
    applyConnectionState(connection);
    setChannelCatalog(nextCatalog);
    setChannelCatalogSource(nextSourceIdentity);
    setAddedChannelIds(nextSelectedIds);
    clearHostConnectivityDraftStorage();
  };

  const syncCurrentSelectionToBackend = async (
    sourceRevision = currentSourceRevision,
    channelIds = addedChannelIds,
    catalog = channelCatalog,
    connection = currentConnectionState(),
  ) => {
    const selectedChannels = selectChannelsFromCatalog(channelIds, catalog);
    try {
      const runtime = await syncSelectionToBackend(
        sourceRevision,
        selectedChannels,
        catalog,
        connection,
      );
      const nextCatalog = mergeCatalogChannels(
        runtime.host_channel_catalog.items,
        runtime.host_channels.items,
      );
      const nextSelectedIds = filterSelectedChannelIds(
        runtime.host_channels.items.map((item) => item.id),
        nextCatalog,
      );
      applyRuntimeSyncResponse(
        runtime.source_revision,
        config,
        nextCatalog,
        nextSelectedIds,
        runtime.connectivity_status,
      );
      return runtime;
    } catch (error) {
      if (error instanceof SourceRevisionConflictError) {
        throw error;
      }
      throw new Error(t('settingsSyncFailed'));
    }
  };

  const reloadAfterRevisionConflict = async (message: string) => {
    clearHostConnectivityDraftStorage();
    setSaveFeedback('');
    setStatusMessage(message);
    await loadHostBootstrap(true);
  };

  const prepareSourceAwareAction = async (action: SourceAwareAction): Promise<PreparedSourceAwareState> => {
    const sourceIdentityChanged = hasSourceIdentityChanged(lastAppliedConfig, config);
    const connectionMaterialChanged = hasConnectionMaterialChanged(lastAppliedConfig, config);

    if (!connectionMaterialChanged) {
      return {
        sourceRevision: currentSourceRevision,
        sourceIdentityChanged: false,
        connectionMaterialChanged: false,
        channelIds: addedChannelIds,
        catalog: channelCatalog,
        catalogSource: channelCatalogSource,
        connection: currentConnectionState(),
        message: null,
      };
    }

    if (sourceIdentityChanged && hasSourceScopedState()) {
      const confirmed = await requestSourceSwitchConfirmation(action);
      if (!confirmed) {
        throw new Error(t('sourceSwitchCancelled'));
      }
    }

    const result = await applySourceSwitchToBackend(config, currentSourceRevision);
    const nextSourceIdentity = buildSourceIdentity(config.endpoint, config.username);
    const disconnectedState = buildDisconnectedConnectionState(config.endpoint);
    const retainedChannels = sourceIdentityChanged
      ? []
      : selectChannelsFromCatalog(addedChannelIds, channelCatalog);
    const retainedCatalog = sourceIdentityChanged ? [] : retainedChannels;
    const retainedChannelIds = retainedChannels.map((item) => item.id);

    applyConnectionState(disconnectedState);
    if (sourceIdentityChanged) {
      clearSourceScopedSelection();
    } else {
      setChannelCatalog(retainedCatalog);
      setAddedChannelIds(retainedChannelIds);
      setChannelCatalogSource(nextSourceIdentity);
    }
    setCurrentSourceRevision(result.source_revision);
    setCurrentSourceIdentity(nextSourceIdentity);
    setLastAppliedConfig(config);
    clearHostConnectivityDraftStorage();
    setSaveFeedback('');
    setStatusMessage(result.message);

    return {
      sourceRevision: result.source_revision,
      sourceIdentityChanged,
      connectionMaterialChanged,
      channelIds: sourceIdentityChanged ? [] : retainedChannelIds,
      catalog: sourceIdentityChanged ? [] : retainedCatalog,
      catalogSource: sourceIdentityChanged ? null : nextSourceIdentity,
      connection: disconnectedState,
      message: result.message,
    };
  };

  const handleApply = async () => {
    try {
      const prepared = await prepareSourceAwareAction('apply');
      if (!prepared.sourceIdentityChanged) {
        await syncCurrentSelectionToBackend(
          prepared.sourceRevision,
          prepared.channelIds,
          prepared.catalog,
          prepared.connection,
        );
      }
      const savedAt = new Date().toISOString();
      const message = `${t('settingsAppliedMessage')} ${formatCheckedAt(savedAt)}`;
      setStatusMessage(message);
      setSaveFeedback(message);
    } catch (error) {
      if (error instanceof SourceRevisionConflictError) {
        await reloadAfterRevisionConflict(error.message);
        return;
      }
      const message = error instanceof Error ? error.message : t('settingsSyncFailed');
      setStatusMessage(message);
      setSaveFeedback('');
    }
  };

  const handleConnect = async () => {
    setLoading(true);
    setSaveFeedback('');
    let prepared: PreparedSourceAwareState | null = null;
    try {
      prepared = await prepareSourceAwareAction('connect');
      const { response, data } = await callHostApi('/edc/test-connection', config);
      if (!response.ok || !data.ok) {
        throw new Error(data.message || t('testFailed'));
      }
      const connectedState: PersistedConnectionState = {
        isConnected: true,
        machineName: data.nodeName,
          lastSyncLabel: formatCheckedAt(data.checkedAt),
          meta: data.meta,
      };
      await syncCurrentSelectionToBackend(
        prepared.sourceRevision,
        prepared.channelIds,
        prepared.catalog,
        connectedState,
      );
      setStatusMessage(data.message || t('testSuccess'));
    } catch (error) {
      if (error instanceof SourceRevisionConflictError) {
        await reloadAfterRevisionConflict(error.message);
        return;
      }
      if (!prepared) {
        setSaveFeedback('');
        setStatusMessage(error instanceof Error ? error.message : t('testFailed'));
        return;
      }
      const disconnectedState = buildDisconnectedConnectionState(config.endpoint);
      applyConnectionState(disconnectedState);
      setSaveFeedback('');
      setStatusMessage(error instanceof Error ? error.message : t('testFailed'));
      try {
        await syncCurrentSelectionToBackend(
          prepared.sourceRevision,
          prepared.channelIds,
          prepared.catalog,
          disconnectedState,
        );
      } catch (syncError) {
        if (syncError instanceof SourceRevisionConflictError) {
          await reloadAfterRevisionConflict(syncError.message);
          return;
        }
        // 连接校验失败时，后端断线摘要尽量同步；失败则保留原始提示。
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSyncChannels = async () => {
    setSyncing(true);
    setSaveFeedback('');
    try {
      const prepared = await prepareSourceAwareAction('sync');
      const { response, data } = await callHostApi('/edc/sync-channels', config);
      if (!response.ok || !data.ok || !data.channels) {
        throw new Error(data.message || t('syncFailed'));
      }
      const connectedState: PersistedConnectionState = {
        isConnected: true,
        machineName: data.nodeName,
          lastSyncLabel: formatCheckedAt(data.checkedAt),
          meta: data.meta,
      };
      const nextAddedChannelIds = prepared.sourceIdentityChanged
        ? []
        : syncAddedChannelsWithCatalog(prepared.channelIds, data.channels);
      await syncCurrentSelectionToBackend(
        prepared.sourceRevision,
        nextAddedChannelIds,
        data.channels,
        connectedState,
      );
      setStatusMessage(data.message || t('syncSuccess'));
    } catch (error) {
      if (error instanceof SourceRevisionConflictError) {
        await reloadAfterRevisionConflict(error.message);
        return;
      }
      setStatusMessage(error instanceof Error ? error.message : t('syncFailed'));
    } finally {
      setSyncing(false);
    }
  };

  const connectedMachineDisplay = isConnected ? machineName : '--';
  const lastSyncDisplay = isConnected ? lastSyncLabel : '--';
  const connectionMetaDisplay = isConnected
    ? `${meta.sensorCount} devices / ${meta.channelCount} channels`
    : '--';
  const sourceDisplay = isConnected ? meta.source : '--';
  const enabledChannelsDisplay = isConnected ? String(meta.enabledChannelCount) : '--';

  return (
    <div className="p-6 md:p-10 flex flex-col gap-6 md:gap-8 h-full bg-gradient-to-br from-transparent to-black/5 dark:to-white/5 overflow-y-auto custom-scrollbar">
      {sourceSwitchDialog ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-6 backdrop-blur-sm">
          <div className="w-full max-w-xl rounded-[28px] border border-white/20 bg-white/90 p-6 shadow-2xl backdrop-blur-xl dark:border-white/10 dark:bg-slate-950/90">
            <div className="flex items-start gap-4">
              <div className="rounded-2xl bg-amber-500/15 p-3 text-amber-600 dark:text-amber-300">
                <AlertTriangle className="h-6 w-6" />
              </div>
              <div className="flex-1">
                <p className="text-[10px] font-black uppercase tracking-[0.24em] opacity-45">{t('sourceSwitchTitle')}</p>
                <h3 className="mt-2 text-xl font-black tracking-tight">{t('sourceSwitchHeading')}</h3>
                <p className="mt-3 text-sm leading-6 opacity-75">
                  {t('sourceSwitchPromptPrefix')} {resolveActionLabel(sourceSwitchDialog.action)}
                  {t('sourceSwitchPromptSuffix')}
                </p>
              </div>
            </div>

            <div className="mt-5 rounded-[22px] border border-amber-500/15 bg-amber-500/10 px-4 py-4 text-sm leading-6 text-slate-700 dark:text-slate-200">
              <p className="font-bold">{t('sourceSwitchTargetLabel')}: {sourceSwitchDialog.nextSource}</p>
              <p className="mt-3">{t('sourceSwitchResetSummary')}</p>
              <p className="mt-2 opacity-75">{t('sourceSwitchResetList')}</p>
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => closeSourceSwitchDialog(false)}
                className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs font-black uppercase tracking-widest text-slate-700 transition-colors hover:bg-slate-50 dark:border-white/10 dark:bg-white/10 dark:text-slate-200 dark:hover:bg-white/15"
              >
                {t('cancelSourceSwitch')}
              </button>
              <button
                type="button"
                onClick={() => closeSourceSwitchDialog(true)}
                className="rounded-2xl bg-amber-500 px-4 py-3 text-xs font-black uppercase tracking-widest text-white shadow-lg shadow-amber-500/25 transition-colors hover:bg-amber-400"
              >
                {t('confirmSourceSwitch')}
              </button>
            </div>
          </div>
        </div>
      ) : null}
      <div className="flex items-center gap-4 md:gap-6 animate-in slide-in-from-left duration-500">
        <div className="p-4 md:p-5 bg-blue-500 rounded-[20px] md:rounded-[24px] text-white shadow-lg shadow-blue-500/30 ring-4 ring-blue-500/10">
          <Settings className="w-8 h-8 md:w-10 md:h-10" />
        </div>
        <div>
          <h2 className="text-2xl md:text-3xl font-black tracking-tight mb-1">{t('connect')}</h2>
          <p className="text-[11px] md:text-xs opacity-60 font-medium max-w-3xl">{t('apiConnectionDesc')}</p>
        </div>
      </div>

      <section className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        <div className="xl:col-span-7 bg-white/55 dark:bg-black/20 rounded-[28px] border border-white/40 dark:border-white/10 backdrop-blur-xl shadow-sm p-6 space-y-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.24em] opacity-40">{t('apiConnection')}</p>
              <h3 className="text-xl font-black tracking-tight mt-1">{t('connectSource')}</h3>
              <p className="text-[11px] md:text-xs opacity-55 mt-2 max-w-2xl">{t('connectSourceDesc')}</p>
            </div>
            <div className="px-3 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest bg-blue-500/10 text-blue-600 dark:text-blue-300 border border-blue-500/15">
              EDC
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="text-[10px] font-black uppercase opacity-40 ml-1 mb-2 block tracking-wider">{t('endpoint')}</label>
              <div className="relative group">
                <Database className="absolute left-4 top-4 w-4 h-4 opacity-40 group-focus-within:text-blue-500 transition-colors" />
                <input
                  type="text"
                  value={config.endpoint}
                  onChange={(e) => setConfig({ ...config, endpoint: e.target.value })}
                  className="w-full bg-slate-100/80 dark:bg-black/40 border-none rounded-2xl pl-12 pr-4 py-4 text-sm font-medium focus:ring-2 ring-blue-500/50 transition-all font-mono shadow-inner"
                />
              </div>
            </div>
            <div>
              <label className="text-[10px] font-black uppercase opacity-40 ml-1 mb-2 block tracking-wider">{t('username')}</label>
              <div className="relative group">
                <User className="absolute left-4 top-4 w-4 h-4 opacity-40 group-focus-within:text-blue-500 transition-colors" />
                <input
                  type="text"
                  value={config.username}
                  onChange={(e) => setConfig({ ...config, username: e.target.value })}
                  className="w-full bg-slate-100/80 dark:bg-black/40 border-none rounded-2xl pl-12 pr-4 py-4 text-sm font-medium focus:ring-2 ring-blue-500/50 transition-all shadow-inner"
                />
              </div>
            </div>
            <div>
              <label className="text-[10px] font-black uppercase opacity-40 ml-1 mb-2 block tracking-wider">{t('password')}</label>
              <div className="relative group">
                <Key className="absolute left-4 top-4 w-4 h-4 opacity-40 group-focus-within:text-blue-500 transition-colors" />
                <input
                  type="password"
                  value={config.password}
                  onChange={(e) => setConfig({ ...config, password: e.target.value })}
                  className="w-full bg-slate-100/80 dark:bg-black/40 border-none rounded-2xl pl-12 pr-4 py-4 text-sm font-medium focus:ring-2 ring-blue-500/50 transition-all shadow-inner"
                />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-[22px] bg-slate-100/80 dark:bg-white/5 border border-white/40 dark:border-white/10 p-4">
              <p className="text-[10px] uppercase tracking-widest opacity-40 font-black">{t('status')}</p>
              <div className="mt-3 flex items-center gap-3">
                <div className={`h-3 w-3 rounded-full ${isConnected ? 'bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.5)]' : 'bg-slate-400'}`} />
                <span className="text-sm font-black">{isConnected ? t('online') : t('offline')}</span>
              </div>
            </div>
            <div className="rounded-[22px] bg-slate-100/80 dark:bg-white/5 border border-white/40 dark:border-white/10 p-4">
              <p className="text-[10px] uppercase tracking-widest opacity-40 font-black">{t('connectedMachine')}</p>
              <p className="mt-3 text-sm font-black">{config.endpoint}</p>
              <p className="text-[10px] opacity-50 mt-1">{connectedMachineDisplay}</p>
            </div>
            <div className="rounded-[22px] bg-slate-100/80 dark:bg-white/5 border border-white/40 dark:border-white/10 p-4">
              <p className="text-[10px] uppercase tracking-widest opacity-40 font-black">{t('lastSync')}</p>
              <p className="mt-3 text-sm font-black">{lastSyncDisplay}</p>
              <p className="text-[10px] opacity-50 mt-1">{connectionMetaDisplay}</p>
            </div>
          </div>

          <div className="rounded-[22px] bg-blue-500/10 text-blue-700 dark:text-blue-300 border border-blue-500/15 px-4 py-3 text-[11px] font-medium">
            {statusMessage || t('connectSourceDesc')}
          </div>

          <div className="flex flex-wrap justify-end gap-3 pt-1">
            <button
              type="button"
              onClick={handleConnect}
              className="px-5 py-3 rounded-2xl bg-white dark:bg-white/10 text-slate-700 dark:text-slate-200 text-xs font-black uppercase tracking-widest border border-slate-200 dark:border-white/10 hover:bg-slate-50 dark:hover:bg-white/15 transition-colors flex items-center gap-2"
            >
              {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Power className="w-4 h-4" />}
              {t('testConnection')}
            </button>
            <button
              type="button"
              onClick={handleSyncChannels}
              className="px-5 py-3 rounded-2xl bg-blue-600 text-white text-xs font-black uppercase tracking-widest shadow-lg shadow-blue-500/20 hover:bg-blue-500 transition-colors flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
              {t('syncChannels')}
            </button>
          </div>
        </div>

        <div className="xl:col-span-5 bg-gradient-to-br from-white/85 to-white/45 dark:from-white/10 dark:to-white/5 rounded-[28px] border border-white/40 dark:border-white/10 backdrop-blur-xl shadow-sm p-6 flex flex-col gap-4">
          <p className="text-[10px] font-black uppercase tracking-[0.24em] opacity-40">{t('status')}</p>
          <div className="flex items-center gap-3">
            <div className={`w-11 h-11 rounded-2xl flex items-center justify-center ${isConnected ? 'bg-emerald-500/15 text-emerald-500' : 'bg-slate-200/70 dark:bg-white/10 text-slate-500'}`}>
              {isConnected ? <Check className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
            </div>
            <div>
              <h4 className="text-lg font-black tracking-tight">{isConnected ? t('connectionReady') : t('waitingValidation')}</h4>
              <p className="text-[11px] opacity-55 mt-1">{isConnected ? t('mappingWorkbenchDesc') : t('channelAddHint')}</p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="rounded-[22px] bg-black/5 dark:bg-white/5 border border-white/40 dark:border-white/10 p-4">
              <p className="text-[10px] uppercase tracking-widest opacity-40 font-black">{t('sourceRealtime')}</p>
              <p className="mt-2 text-sm font-black">{sourceDisplay}</p>
            </div>
            <div className="rounded-[22px] bg-black/5 dark:bg-white/5 border border-white/40 dark:border-white/10 p-4">
              <p className="text-[10px] uppercase tracking-widest opacity-40 font-black">{t('enabledChannels')}</p>
              <p className="mt-2 text-sm font-black">{enabledChannelsDisplay}</p>
            </div>
          </div>
          <div className="mt-2 rounded-[22px] bg-black/5 dark:bg-white/5 border border-white/40 dark:border-white/10 p-4 space-y-3">
            <div className="flex items-start gap-3">
              <Info className="w-4 h-4 text-blue-500 mt-0.5" />
              <div>
                <p className="text-xs font-black">{t('connectSource')}</p>
                <p className="text-[11px] opacity-55 mt-1">{t('hostConnectNote')}</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <LayoutGrid className="w-4 h-4 text-cyan-500 mt-0.5" />
              <div>
                <p className="text-xs font-black">{t('hardwareCollectionWorkbench')}</p>
                <p className="text-[11px] opacity-55 mt-1">{t('hostCollectionNote')}</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        <div className="xl:col-span-6 bg-white/55 dark:bg-black/20 rounded-[28px] border border-white/40 dark:border-white/10 backdrop-blur-xl shadow-sm p-6 flex flex-col gap-5 min-h-[560px]">
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.24em] opacity-40">{t('hardwareCollectionWorkbench')}</p>
              <h3 className="text-xl font-black tracking-tight mt-1">{t('sourceCatalog')}</h3>
              <p className="text-[11px] md:text-xs opacity-55 mt-2 max-w-2xl">{t('sourceCatalogDesc')}</p>
            </div>
            <div className="relative w-full md:w-80">
              <Search className="absolute left-4 top-3.5 w-4 h-4 opacity-40" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t('searchPlaceholder')}
                className="w-full rounded-2xl bg-slate-100/85 dark:bg-black/35 border-none pl-11 pr-4 py-3 text-sm font-medium shadow-inner focus:ring-2 ring-blue-500/50"
              />
            </div>
          </div>

          <div className="flex items-center justify-between gap-3 rounded-2xl bg-blue-500/10 text-blue-700 dark:text-blue-300 border border-blue-500/15 px-4 py-3 text-[11px] font-medium">
            <span>{t('channelAddHint')}</span>
            <span className="shrink-0 px-2 py-1 rounded-full bg-white/70 dark:bg-white/10 text-[10px] font-black uppercase tracking-widest">{t('sourceReadonly')}</span>
          </div>

          <div className="flex-1 overflow-y-auto pr-1 space-y-4 custom-scrollbar">
            {groupedChannels.length === 0 ? (
              <div className="h-full min-h-[220px] rounded-[24px] border border-dashed border-slate-300 dark:border-white/10 flex items-center justify-center text-sm opacity-50">
                {t('noResult')}
              </div>
            ) : (
              groupedChannels.map((group) => {
                const expanded = expandedDevices[group.deviceName] ?? false;
                const isGroupAdded = group.items.every((item) => addedChannelIdSet.has(item.id));
                return (
                  <div key={group.deviceName} className="rounded-[24px] border border-white/40 dark:border-white/10 bg-slate-100/65 dark:bg-white/5 overflow-hidden">
                    <div className="sticky top-0 z-10 w-full px-5 py-4 flex items-center justify-between gap-4 bg-slate-100/95 dark:bg-slate-900/90 backdrop-blur">
                      <button
                        type="button"
                        onClick={() => toggleDevice(group.deviceName)}
                        aria-expanded={expanded}
                        className="min-w-0 flex flex-1 items-center justify-between gap-4 text-left hover:bg-black/5 dark:hover:bg-white/5 transition-colors rounded-2xl -m-2 p-2"
                      >
                        <div className="min-w-0 text-left">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-black">{group.deviceName}</span>
                            <span className="px-2 py-0.5 rounded-full bg-white/70 dark:bg-white/10 text-[9px] uppercase tracking-widest font-black opacity-70">{group.deviceType}</span>
                          </div>
                          <p className="text-[11px] opacity-50 mt-1">{group.area} · {group.items.length} channels</p>
                        </div>
                        {expanded ? <ChevronDown className="w-4 h-4 opacity-50 shrink-0" /> : <ChevronRight className="w-4 h-4 opacity-50 shrink-0" />}
                      </button>
                      <button
                        type="button"
                        onClick={() => addGroupChannels(group.deviceName)}
                        disabled={isGroupAdded}
                        className="shrink-0 px-3 py-2 rounded-xl bg-slate-900 dark:bg-white dark:text-slate-900 text-white text-[10px] font-black uppercase tracking-widest shadow-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
                      >
                        {isGroupAdded ? t('alreadyAdded') : t('addGroup')}
                      </button>
                    </div>
                    {expanded && (
                      <div className="px-4 pb-4 space-y-2">
                        {group.items.map((channel) => {
                          const isAdded = addedChannelIdSet.has(channel.id);
                          return (
                            <div
                              key={channel.id}
                              className="w-full rounded-[20px] border border-white/50 dark:border-white/10 bg-white/70 dark:bg-black/20 hover:border-blue-300 hover:bg-blue-500/5 px-4 py-3 text-left transition-all"
                            >
                              <div className="flex items-start justify-between gap-4">
                                <div className="flex-1 text-left">
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <span className="text-sm font-black">{channel.channelName}</span>
                                    <span className="px-2 py-0.5 rounded-full bg-slate-900 text-white text-[9px] uppercase tracking-widest font-black">{channel.unit || '--'}</span>
                                    {isAdded && <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 text-[9px] uppercase tracking-widest font-black">{t('added')}</span>}
                                  </div>
                                  <p className="text-[11px] opacity-55 mt-1">{t('sourceDevice')}: {channel.deviceName} · suid {channel.suid}</p>
                                  <p className="text-[11px] opacity-55 mt-1">{t('sourceChannel')}: cuid {channel.cuid} · last {channel.lastValue}</p>
                                </div>
                                <div className="flex flex-col items-end gap-2">
                                  <span className="text-[10px] font-black uppercase tracking-widest opacity-40 pt-1">{t('sourceDetailLabel')}</span>
                                  <button
                                    type="button"
                                    onClick={() => addChannel(channel.id)}
                                    className="px-3 py-2 rounded-xl bg-slate-900 dark:bg-white dark:text-slate-900 text-white text-[10px] font-black uppercase tracking-widest shadow-lg hover:opacity-90 transition-opacity"
                                  >
                                    {isAdded ? t('alreadyAdded') : t('addCurrent')}
                                  </button>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        <div className="xl:col-span-6 bg-gradient-to-br from-white/85 to-white/50 dark:from-white/10 dark:to-white/5 rounded-[28px] border border-white/40 dark:border-white/10 backdrop-blur-xl shadow-sm p-6 flex flex-col gap-5 min-h-[560px]">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.24em] opacity-40">{t('hardwareCollectionWorkbench')}</p>
            <h3 className="text-xl font-black tracking-tight mt-1">{t('addedChannels')}</h3>
            <p className="text-[11px] md:text-xs opacity-55 mt-2">{t('addedChannelsDesc')}</p>
          </div>

          <div className="rounded-2xl bg-blue-500/10 text-blue-700 dark:text-blue-300 border border-blue-500/15 px-4 py-3 text-[11px] font-medium">
            {t('collectionExplain')}
          </div>

          <div className="flex-1 overflow-y-auto pr-1 space-y-4 custom-scrollbar">
            {addedChannelGroups.length === 0 ? (
              <div className="h-full min-h-[220px] rounded-[24px] border border-dashed border-slate-300 dark:border-white/10 flex items-center justify-center text-sm opacity-50 px-6 text-center">
                {t('noAddedChannels')}
              </div>
            ) : (
              addedChannelGroups.map((group) => (
                <div key={group.deviceName} className="rounded-[24px] border border-white/40 dark:border-white/10 bg-slate-100/70 dark:bg-white/5 overflow-hidden">
                  <div className="sticky top-0 z-10 px-4 py-4 bg-slate-100/95 dark:bg-slate-900/90 backdrop-blur border-b border-white/40 dark:border-white/10 flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-black">{group.deviceName}</span>
                        <span className="px-2 py-0.5 rounded-full bg-white/70 dark:bg-white/10 text-[9px] uppercase tracking-widest font-black opacity-70">{group.deviceType}</span>
                      </div>
                      <p className="text-[11px] opacity-55 mt-1">{group.area} · {group.items.length} {t('channelCountLabel')}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeGroupChannels(group.deviceName)}
                      className="px-3 py-2 rounded-xl bg-white dark:bg-white/10 text-[10px] font-black uppercase tracking-widest border border-slate-200 dark:border-white/10 hover:bg-slate-50 dark:hover:bg-white/15 transition-colors"
                    >
                      {t('removeGroup')}
                    </button>
                  </div>
                  <div className="px-4 py-4 space-y-3">
                    {group.items.map((channel) => (
                      <div key={channel.id} className="rounded-[18px] bg-white/80 dark:bg-black/20 border border-white/50 dark:border-white/10 px-4 py-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-black">{channel.channelName}</p>
                            <p className="text-[11px] opacity-55 mt-1">suid {channel.suid} / cuid {channel.cuid} · {channel.unit || '--'}</p>
                            <p className="text-[11px] opacity-55 mt-1">{t('sourceDevice')}: {channel.deviceName}</p>
                          </div>
                          <button
                            type="button"
                            onClick={() => removeChannel(channel.id)}
                            className="px-3 py-2 rounded-xl bg-white dark:bg-white/10 text-[10px] font-black uppercase tracking-widest border border-slate-200 dark:border-white/10 hover:bg-slate-50 dark:hover:bg-white/15 transition-colors"
                          >
                            {t('removeCurrent')}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="mt-auto space-y-3">
            {saveFeedback ? (
              <div className="flex items-center justify-end">
                <div className="inline-flex items-center gap-2 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-[11px] font-bold text-emerald-700 shadow-sm dark:text-emerald-300">
                  <Check className="h-4 w-4" />
                  <span>{saveFeedback}</span>
                </div>
              </div>
            ) : null}
            <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={handleSaveDraft}
              className="px-4 py-3 rounded-2xl bg-white dark:bg-white/10 text-slate-700 dark:text-slate-200 text-xs font-black uppercase tracking-widest border border-slate-200 dark:border-white/10 hover:bg-slate-50 dark:hover:bg-white/15 transition-colors"
            >
              {t('saveDraft')}
            </button>
            <button
              type="button"
              onClick={() => void handleApply()}
              className="px-4 py-3 rounded-2xl bg-slate-900 dark:bg-white dark:text-slate-900 text-white text-xs font-black uppercase tracking-widest shadow-lg hover:opacity-90 transition-opacity flex items-center gap-2"
            >
              <Save className="w-4 h-4" />
              {t('apply')}
            </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
