import React, { useEffect, useMemo, useState } from 'react';
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
import { edcChannelSnapshot, edcSnapshotMeta } from './edcChannelSnapshot';
import {
  buildHostConnectivityDraft,
  hostSettingsStorageKey,
  restoreHostConnectivityDraft,
  type HostEdcMeta,
  type PersistedConnectionState,
} from './hostConnectivityState';
import {
  buildDisconnectedConnectionState,
  callHostApi,
  getDefaultAddedChannelIds,
  reconcileAddedChannelIds,
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

const initialCatalog: ChannelMappingItem[] = [...edcChannelSnapshot];
const defaultAddedChannelIds = getDefaultAddedChannelIds(initialCatalog);

export default function SettingsView({ config, setConfig, t, isConnected, setIsConnected }: SettingsViewProps) {
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [query, setQuery] = useState('');
  const [expandedDevices, setExpandedDevices] = useState<Record<string, boolean>>({});
  const [channelCatalog, setChannelCatalog] = useState<ChannelMappingItem[]>(initialCatalog);
  const [addedChannelIds, setAddedChannelIds] = useState<string[]>(defaultAddedChannelIds);
  const [statusMessage, setStatusMessage] = useState('');
  const [saveFeedback, setSaveFeedback] = useState('');
  const [machineName, setMachineName] = useState('EDC Test Gateway');
  const [lastSyncLabel, setLastSyncLabel] = useState('2026-03-16 11:12');
  const [meta, setMeta] = useState<HostEdcMeta>(edcSnapshotMeta);

  const currentConnectionState = (): PersistedConnectionState => ({
    isConnected,
    machineName,
    lastSyncLabel,
    meta,
  });

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

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    try {
      const restored = restoreHostConnectivityDraft(
        window.localStorage.getItem(hostSettingsStorageKey),
        initialCatalog.map((item) => item.id),
        {
          isConnected: false,
          machineName: 'EDC Test Gateway',
          lastSyncLabel: '2026-03-16 11:12',
          meta: edcSnapshotMeta,
        },
      );
      if (!restored) {
        return;
      }
      if (restored.config) {
        setConfig(restored.config);
      }
      setAddedChannelIds(reconcileAddedChannelIds(restored.addedChannelIds, initialCatalog));
      if (restored.connection) {
        setIsConnected(restored.connection.isConnected);
        setMachineName(restored.connection.machineName);
        setLastSyncLabel(restored.connection.lastSyncLabel);
        setMeta(restored.connection.meta);
      }
      if (typeof restored.savedAt === 'string') {
        setStatusMessage(`${t('draftRestored')} ${formatCheckedAt(restored.savedAt)}`);
      }
    } catch {
      setStatusMessage(t('draftRestoreFailed'));
    }
  }, [setConfig, setIsConnected, t]);

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

  const syncAddedChannelsWithCatalog = (channels: ChannelMappingItem[]) => {
    const nextAddedChannelIds = reconcileAddedChannelIds(addedChannelIds, channels);
    setAddedChannelIds(nextAddedChannelIds);
    return nextAddedChannelIds;
  };

  const writeDraft = (savedAt: string, connection: PersistedConnectionState) => {
    if (typeof window === 'undefined') {
      return;
    }
    window.localStorage.setItem(
      hostSettingsStorageKey,
      JSON.stringify(
        buildHostConnectivityDraft({
          config,
          addedChannelIds,
          savedAt,
          connection,
        }),
      ),
    );
  };

  const persistDraft = (mode: 'draft' | 'apply', connection = currentConnectionState()) => {
    if (typeof window === 'undefined') {
      return;
    }
    const savedAt = new Date().toISOString();
    writeDraft(savedAt, connection);
    const message =
      mode === 'draft'
        ? `${t('draftSaved')} ${formatCheckedAt(savedAt)}`
        : `${t('settingsAppliedMessage')} ${formatCheckedAt(savedAt)}`;
    setStatusMessage(message);
    setSaveFeedback(message);
  };

  const persistConnectionState = (connection: PersistedConnectionState) => {
    writeDraft(new Date().toISOString(), connection);
  };

  const syncCurrentSelectionToBackend = async (
    channelIds = addedChannelIds,
    catalog = channelCatalog,
    connection = currentConnectionState(),
  ) => {
    const selectedChannels = channelIds
      .map((channelId) => catalog.find((item) => item.id === channelId))
      .filter((item): item is ChannelMappingItem => Boolean(item));
    try {
      await syncSelectionToBackend(config, selectedChannels, connection);
    } catch {
      throw new Error(t('settingsSyncFailed'));
    }
  };

  const handlePersist = async (mode: 'draft' | 'apply') => {
    persistDraft(mode);
    if (mode !== 'apply') {
      return;
    }

    try {
      await syncCurrentSelectionToBackend(addedChannelIds, channelCatalog, currentConnectionState());
      const savedAt = new Date().toISOString();
      const message = `${t('settingsAppliedMessage')} ${formatCheckedAt(savedAt)}`;
      setStatusMessage(message);
      setSaveFeedback(message);
    } catch (error) {
      const message = error instanceof Error ? error.message : t('settingsSyncFailed');
      setStatusMessage(message);
      setSaveFeedback(message);
    }
  };

  const handleConnect = async () => {
    setLoading(true);
    try {
      const { response, data } = await callHostApi('/host-api/edc/test-connection', config);
      if (!response.ok || !data.ok) {
        throw new Error(data.message || t('testFailed'));
      }
      const connectedState: PersistedConnectionState = {
        isConnected: true,
        machineName: data.nodeName,
        lastSyncLabel: formatCheckedAt(data.checkedAt),
        meta: data.meta,
      };
      setIsConnected(true);
      setMachineName(connectedState.machineName);
      setMeta(connectedState.meta);
      setLastSyncLabel(connectedState.lastSyncLabel);
      await syncCurrentSelectionToBackend(addedChannelIds, channelCatalog, connectedState);
      setStatusMessage(data.message || t('testSuccess'));
      persistConnectionState(connectedState);
    } catch (error) {
      const disconnectedState = buildDisconnectedConnectionState(config.endpoint);
      setIsConnected(false);
      setMachineName(disconnectedState.machineName);
      setMeta(disconnectedState.meta);
      setLastSyncLabel(disconnectedState.lastSyncLabel);
      setStatusMessage(error instanceof Error ? error.message : t('testFailed'));
      try {
        await syncCurrentSelectionToBackend(addedChannelIds, channelCatalog, disconnectedState);
      } catch {
        // 连接校验失败时，后端断线摘要尽量同步；失败则保留原始提示。
      }
      persistConnectionState(disconnectedState);
    } finally {
      setLoading(false);
    }
  };

  const handleSyncChannels = async () => {
    setSyncing(true);
    try {
      const { response, data } = await callHostApi('/host-api/edc/sync-channels', config);
      if (!response.ok || !data.ok || !data.channels) {
        throw new Error(data.message || t('syncFailed'));
      }
      const connectedState: PersistedConnectionState = {
        isConnected: true,
        machineName: data.nodeName,
        lastSyncLabel: formatCheckedAt(data.checkedAt),
        meta: data.meta,
      };
      setIsConnected(true);
      setMachineName(connectedState.machineName);
      setMeta(connectedState.meta);
      setLastSyncLabel(connectedState.lastSyncLabel);
      setChannelCatalog(data.channels);
      const nextAddedChannelIds = syncAddedChannelsWithCatalog(data.channels);
      await syncCurrentSelectionToBackend(nextAddedChannelIds, data.channels, connectedState);
      setStatusMessage(data.message || t('syncSuccess'));
      persistConnectionState(connectedState);
    } catch (error) {
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
              onClick={() => void handlePersist('draft')}
              className="px-4 py-3 rounded-2xl bg-white dark:bg-white/10 text-slate-700 dark:text-slate-200 text-xs font-black uppercase tracking-widest border border-slate-200 dark:border-white/10 hover:bg-slate-50 dark:hover:bg-white/15 transition-colors"
            >
              {t('saveDraft')}
            </button>
            <button
              type="button"
              onClick={() => void handlePersist('apply')}
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
