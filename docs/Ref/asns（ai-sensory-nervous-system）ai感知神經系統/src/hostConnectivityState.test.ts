import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildHostConnectivityDraft,
  isHostConnectivityDraftCurrent,
  restoreHostConnectivityDraft,
  toggleWindowState,
  type PersistedConnectionState,
} from './hostConnectivityState';
import {
  buildDisconnectedConnectionState,
  getDefaultAddedChannelIds,
  hasSourceIdentityChanged,
  reconcileAddedChannelIds,
} from './hostConnectivitySync';

const fallbackConnection: PersistedConnectionState = {
  isConnected: false,
  machineName: 'EDC Test Gateway',
  lastSyncLabel: '2026-03-16 11:12',
  meta: {
    source: '宿主直连',
    sensorCount: 26,
    channelCount: 2286,
    enabledChannelCount: 6,
  },
};

test('toggleWindowState opens a closed dock app', () => {
  const nextState = toggleWindowState([], 'edc-electricity');

  assert.deepEqual(nextState.openWindowIds, ['edc-electricity']);
  assert.equal(nextState.activeWin, 'edc-electricity');
});

test('toggleWindowState focuses an already open dock app without duplicating it', () => {
  const nextState = toggleWindowState(['dash', 'edc-electricity'], 'edc-electricity');

  assert.deepEqual(nextState.openWindowIds, ['dash', 'edc-electricity']);
  assert.equal(nextState.activeWin, 'edc-electricity');
});

test('restoreHostConnectivityDraft keeps connected session metadata and filters unknown channels', () => {
  const raw = JSON.stringify(
    buildHostConnectivityDraft({
      config: {
        endpoint: 'http://60.251.229.32',
        username: 'volapu',
        password: 'admin',
      },
      sourceIdentity: 'http://60.251.229.32::volapu',
      baseSourceRevision: 3,
      addedChannelIds: ['channel-001', 'channel-001', 'channel-999'],
      addedChannels: [
        {
          id: 'channel-001',
          deviceName: '电表 A',
          deviceType: '三相智能电表',
          area: '主电力',
          suid: '2349',
          cuid: '199',
          channelName: '总有功功率',
          unit: 'kW',
          lastValue: '--',
          status: 'online',
        },
      ],
      channelCatalogSource: 'http://60.251.229.32::volapu',
      savedAt: '2026-03-19T08:00:00.000Z',
      connection: {
        isConnected: true,
        machineName: 'EDC Line A',
        lastSyncLabel: '2026-03-19 16:00',
        meta: {
          source: '宿主直连',
          sensorCount: 18,
          channelCount: 512,
          enabledChannelCount: 4,
        },
      },
    }),
  );

  const restored = restoreHostConnectivityDraft(
    raw,
    ['channel-001', 'channel-002'],
    fallbackConnection,
  );

  assert.ok(restored);
  assert.deepEqual(restored.config, {
    endpoint: 'http://60.251.229.32',
    username: 'volapu',
    password: 'admin',
  });
  assert.equal(restored.sourceIdentity, 'http://60.251.229.32::volapu');
  assert.equal(restored.baseSourceRevision, 3);
  assert.deepEqual(restored.addedChannelIds, ['channel-001']);
  assert.deepEqual(restored.addedChannels, [
    {
      id: 'channel-001',
      deviceName: '电表 A',
      deviceType: '三相智能电表',
      area: '主电力',
      suid: '2349',
      cuid: '199',
      channelName: '总有功功率',
      unit: 'kW',
      lastValue: '--',
      status: 'online',
    },
  ]);
  assert.equal(restored.channelCatalogSource, 'http://60.251.229.32::volapu');
  assert.equal(restored.savedAt, '2026-03-19T08:00:00.000Z');
  assert.equal(restored.connection?.isConnected, true);
  assert.equal(restored.connection?.machineName, 'EDC Line A');
  assert.equal(restored.connection?.lastSyncLabel, '2026-03-19 16:00');
  assert.deepEqual(restored.connection?.meta, {
    source: '宿主直连',
    sensorCount: 18,
    channelCount: 512,
    enabledChannelCount: 4,
  });
  assert.equal(
    isHostConnectivityDraftCurrent(restored, 'http://60.251.229.32::volapu', 3),
    true,
  );
});

test('restoreHostConnectivityDraft falls back safely when connection payload is incomplete', () => {
  const raw = JSON.stringify({
    config: {
      endpoint: 'http://60.251.229.32',
      username: 'volapu',
      password: 'admin',
    },
    addedChannelIds: ['channel-001'],
    savedAt: '2026-03-19T08:00:00.000Z',
    connection: {
      isConnected: true,
      meta: {
        channelCount: 1024,
      },
    },
  });

  const restored = restoreHostConnectivityDraft(
    raw,
    ['channel-001'],
    fallbackConnection,
  );

  assert.ok(restored);
  assert.equal(restored.connection?.isConnected, true);
  assert.equal(restored.connection?.machineName, fallbackConnection.machineName);
  assert.equal(restored.connection?.lastSyncLabel, fallbackConnection.lastSyncLabel);
  assert.deepEqual(restored.connection?.meta, {
    source: fallbackConnection.meta.source,
    sensorCount: fallbackConnection.meta.sensorCount,
    channelCount: 1024,
    enabledChannelCount: fallbackConnection.meta.enabledChannelCount,
  });
});

test('restoreHostConnectivityDraft drops legacy channel selections without a matching catalog source', () => {
  const raw = JSON.stringify({
    config: {
      endpoint: 'http://61.216.55.133',
      username: 'admin',
      password: 'admin',
    },
    addedChannelIds: ['2349-199', '2349-128'],
    savedAt: '2026-03-27T08:00:00.000Z',
    connection: {
      isConnected: true,
      machineName: 'EDC Gateway',
      lastSyncLabel: '2026-03-27 16:00',
      meta: {
        source: 'http://61.216.55.133',
        sensorCount: 3,
        channelCount: 788,
        enabledChannelCount: 739,
      },
    },
  });

  const restored = restoreHostConnectivityDraft(
    raw,
    ['2349-199', '2349-128'],
    fallbackConnection,
  );

  assert.ok(restored);
  assert.deepEqual(restored.addedChannelIds, []);
  assert.deepEqual(restored.addedChannels, []);
  assert.equal(restored.channelCatalogSource, null);
});

test('isHostConnectivityDraftCurrent rejects stale source identity and revision', () => {
  const restored = restoreHostConnectivityDraft(
    JSON.stringify({
      config: {
        endpoint: 'http://61.216.55.133',
        username: 'admin',
        password: 'admin',
      },
      sourceIdentity: 'http://61.216.55.133::admin',
      baseSourceRevision: 7,
      addedChannelIds: ['2349-199'],
      channelCatalogSource: 'http://61.216.55.133::admin',
      savedAt: '2026-03-27T08:00:00.000Z',
    }),
    ['2349-199'],
    fallbackConnection,
  );

  assert.ok(restored);
  assert.equal(
    isHostConnectivityDraftCurrent(restored, 'http://61.216.55.133::admin', 8),
    false,
  );
  assert.equal(
    isHostConnectivityDraftCurrent(restored, 'http://new-edc-host::admin', 7),
    false,
  );
});

test('getDefaultAddedChannelIds prefers realtime power and voltage channels over the snapshot head', () => {
  const channelIds = getDefaultAddedChannelIds([
    {
      id: '2054-128',
      deviceName: '温度 A',
      deviceType: '热电偶',
      area: 'A',
      suid: '2054',
      cuid: '128',
      channelName: '热电偶温度采集通道',
      unit: '℃',
      lastValue: '--',
      status: 'online',
    },
    {
      id: '2349-199',
      deviceName: '电表',
      deviceType: '三相智能电表',
      area: '主电力',
      suid: '2349',
      cuid: '199',
      channelName: '总有功功率',
      unit: 'kW',
      lastValue: '--',
      status: 'online',
    },
    {
      id: '2349-128',
      deviceName: '电表',
      deviceType: '三相智能电表',
      area: '主电力',
      suid: '2349',
      cuid: '128',
      channelName: 'A相电压',
      unit: 'V',
      lastValue: '--',
      status: 'online',
    },
  ]);

  assert.deepEqual(channelIds.slice(0, 3), ['2349-199', '2349-128', '2054-128']);
});

test('getDefaultAddedChannelIds prefers total and non-fundamental electrical channels', () => {
  const channelIds = getDefaultAddedChannelIds([
    {
      id: '2755-151',
      deviceName: '电表 A',
      deviceType: '三相智能电表',
      area: '主电力',
      suid: '2755',
      cuid: '151',
      channelName: 'A相基波實功功率',
      unit: 'kW',
      lastValue: '--',
      status: 'online',
    },
    {
      id: '2755-205',
      deviceName: '电表 A',
      deviceType: '三相智能电表',
      area: '主电力',
      suid: '2755',
      cuid: '205',
      channelName: '總有功功率',
      unit: 'kW',
      lastValue: '--',
      status: 'online',
    },
    {
      id: '2752-129',
      deviceName: '电表 B',
      deviceType: '三相智能电表',
      area: '主电力',
      suid: '2752',
      cuid: '129',
      channelName: 'A相基波電壓 (或VAB)',
      unit: 'V',
      lastValue: '--',
      status: 'online',
    },
    {
      id: '2752-128',
      deviceName: '电表 B',
      deviceType: '三相智能电表',
      area: '主电力',
      suid: '2752',
      cuid: '128',
      channelName: 'A相電壓 (或VAB)',
      unit: 'V',
      lastValue: '--',
      status: 'online',
    },
  ]);

  assert.deepEqual(channelIds.slice(0, 2), ['2755-205', '2752-128']);
});

test('reconcileAddedChannelIds falls back to recommended defaults when persisted ids are no longer valid', () => {
  const reconciled = reconcileAddedChannelIds(['missing-channel'], [
    {
      id: '2054-128',
      deviceName: '温度 A',
      deviceType: '热电偶',
      area: 'A',
      suid: '2054',
      cuid: '128',
      channelName: '热电偶温度采集通道',
      unit: '℃',
      lastValue: '--',
      status: 'online',
    },
    {
      id: '2349-199',
      deviceName: '电表',
      deviceType: '三相智能电表',
      area: '主电力',
      suid: '2349',
      cuid: '199',
      channelName: '总有功功率',
      unit: 'kW',
      lastValue: '--',
      status: 'online',
    },
  ]);

  assert.deepEqual(reconciled, ['2349-199', '2054-128']);
});

test('reconcileAddedChannelIds keeps saved channels but appends the recommended power and voltage coverage', () => {
  const reconciled = reconcileAddedChannelIds(['936-128'], [
    {
      id: '936-128',
      deviceName: '电表 A',
      deviceType: '三相智能电表',
      area: '测试区',
      suid: '936',
      cuid: '128',
      channelName: 'A相电压',
      unit: 'V',
      lastValue: '--',
      status: 'online',
    },
    {
      id: '2349-199',
      deviceName: '主电表',
      deviceType: '三相智能电表',
      area: '主电力',
      suid: '2349',
      cuid: '199',
      channelName: '总有功功率',
      unit: 'kW',
      lastValue: '--',
      status: 'online',
    },
  ]);

  assert.deepEqual(reconciled, ['936-128', '2349-199']);
});

test('buildDisconnectedConnectionState clears stale machine and sync summary', () => {
  assert.deepEqual(buildDisconnectedConnectionState('http://60.251.229.32'), {
    isConnected: false,
    machineName: '--',
    lastSyncLabel: '--',
    meta: {
      source: 'http://60.251.229.32',
      sensorCount: 0,
      channelCount: 0,
      enabledChannelCount: 0,
    },
  });
});

test('hasSourceIdentityChanged ignores password-only edits but treats account changes as source changes', () => {
  assert.equal(
    hasSourceIdentityChanged(
      {
        endpoint: 'http://61.216.55.133',
        username: 'admin',
        password: 'old-secret',
      },
      {
        endpoint: 'http://61.216.55.133',
        username: 'admin',
        password: 'new-secret',
      },
    ),
    false,
  );

  assert.equal(
    hasSourceIdentityChanged(
      {
        endpoint: 'http://61.216.55.133',
        username: 'admin',
        password: 'secret',
      },
      {
        endpoint: 'http://61.216.55.133',
        username: 'operator',
        password: 'secret',
      },
    ),
    true,
  );
});
