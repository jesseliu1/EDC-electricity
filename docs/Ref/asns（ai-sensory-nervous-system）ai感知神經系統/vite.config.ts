import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { Buffer } from 'node:buffer';
import type { IncomingMessage, ServerResponse } from 'node:http';
import type { Connect } from 'vite';
import { defineConfig, loadEnv } from 'vite';

interface HostApiConfig {
  endpoint?: string;
  username?: string;
  password?: string;
}

interface ChannelMappingItem {
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

function normalizeEndpoint(endpoint: string) {
  return endpoint.trim().replace(/\/+$/, '');
}

function buildNodeName(endpoint: string) {
  try {
    return `EDC Gateway (${new URL(endpoint).host})`;
  } catch {
    return 'EDC Gateway';
  }
}

async function readJsonBody(req: IncomingMessage): Promise<HostApiConfig> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  const raw = Buffer.concat(chunks).toString('utf-8').trim();
  if (!raw) {
    return {};
  }
  return JSON.parse(raw) as HostApiConfig;
}

function sendJson(res: ServerResponse, statusCode: number, payload: unknown) {
  res.statusCode = statusCode;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.end(JSON.stringify(payload));
}

function decodeSensorPayload(rawText: string) {
  const trimmed = rawText.trim();
  if (!trimmed) {
    return [];
  }
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    const parsed = JSON.parse(trimmed);
    return parsed.value || parsed.data || parsed;
  }
  const numericTokens = trimmed.split(/\s+/).filter((token) => /^\d+$/.test(token));
  const decoded = Buffer.from(numericTokens.map((token) => Number(token))).toString('utf-8');
  const parsed = JSON.parse(decoded);
  return parsed.value || parsed.data || parsed;
}

async function loginEdc(config: HostApiConfig) {
  const endpoint = normalizeEndpoint(config.endpoint || '');
  const username = config.username?.trim();
  const password = config.password ?? '';
  if (!endpoint || !username || !password) {
    throw new Error('请先填写 EDC URL、账户名和密码。');
  }

  const response = await fetch(`${endpoint}/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  const payload = await response.json();
  const token = payload.token || payload.data;
  if (!response.ok || payload.code !== 0 || !token) {
    throw new Error(payload.msg || payload.message || 'EDC 登录失败。');
  }
  return { endpoint, token: String(token) };
}

async function fetchChannelSnapshot(endpoint: string, token: string) {
  const response = await fetch(`${endpoint}/systemcfg`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      request: 'getAllSensorList',
      value: '',
      token,
    }),
  });
  const rawText = await response.text();
  const sensors = decodeSensorPayload(rawText) as Array<Record<string, unknown>>;
  if (!Array.isArray(sensors)) {
    throw new Error('EDC 返回的设备清单格式无法识别。');
  }

  const channels: ChannelMappingItem[] = [];
  let enabledChannelCount = 0;
  for (const sensor of sensors) {
    const suid = String(sensor.uid || sensor.suid || '');
    const sensorName = String(sensor.sensorName || sensor.name || 'Unknown Device');
    const sensorNickname = String(sensor.sensorNickName || '');
    const sensorDesc = String(sensor.sensorDes || '');
    const deviceName = sensorNickname ? `${sensorNickname} · ${sensorName}` : `${sensorName} · ${suid}`;
    const area = sensorDesc || sensorNickname || sensorName;
    const channelList = Array.isArray(sensor.channelList) ? sensor.channelList : [];

    for (const channel of channelList as Array<Record<string, unknown>>) {
      const status = String(channel.status) === '1' ? 'online' : 'idle';
      if (status === 'online') {
        enabledChannelCount += 1;
      }
      channels.push({
        id: `${suid}-${String(channel.cuid || '')}`,
        deviceName,
        deviceType: sensorName,
        area,
        suid,
        cuid: String(channel.cuid || ''),
        channelName: String(channel.chnName || channel.name || `Channel ${String(channel.cuid || '')}`),
        unit: String(channel.chnDim || ''),
        lastValue: '--',
        status,
      });
    }
  }

  channels.sort((a, b) => {
    const deviceCompare = a.deviceName.localeCompare(b.deviceName, 'zh-CN');
    if (deviceCompare !== 0) {
      return deviceCompare;
    }
    return a.cuid.localeCompare(b.cuid, 'zh-CN', { numeric: true });
  });

  return {
    nodeName: buildNodeName(endpoint),
    checkedAt: new Date().toISOString(),
    meta: {
      source: endpoint,
      sensorCount: sensors.length,
      channelCount: channels.length,
      enabledChannelCount,
    },
    channels,
  };
}

function createEdcHostMiddleware(): Connect.NextHandleFunction {
  return async (req, res, next) => {
    const pathName = req.url?.split('?')[0] || '';
    if (req.method !== 'POST' || (pathName !== '/host-api/edc/test-connection' && pathName !== '/host-api/edc/sync-channels')) {
      next();
      return;
    }

    try {
      const config = await readJsonBody(req);
      const { endpoint, token } = await loginEdc(config);
      const snapshot = await fetchChannelSnapshot(endpoint, token);
      const basePayload = {
        ok: true,
        nodeName: snapshot.nodeName,
        checkedAt: snapshot.checkedAt,
        meta: snapshot.meta,
      };

      if (pathName === '/host-api/edc/test-connection') {
        sendJson(res as ServerResponse, 200, {
          ...basePayload,
          message: `连接成功，已读取 ${snapshot.meta.sensorCount} 台设备 / ${snapshot.meta.channelCount} 通道。`,
        });
        return;
      }

      sendJson(res as ServerResponse, 200, {
        ...basePayload,
        channels: snapshot.channels,
        message: `同步完成，已刷新 ${snapshot.meta.channelCount} 条通道目录。`,
      });
    } catch (error) {
      sendJson(res as ServerResponse, 500, {
        ok: false,
        message: error instanceof Error ? error.message : '宿主调用 EDC 失败。',
      });
    }
  };
}

function edcHostApiPlugin() {
  const middleware = createEdcHostMiddleware();
  return {
    name: 'edc-host-api',
    configureServer(server: { middlewares: { use: (fn: Connect.NextHandleFunction) => void } }) {
      server.middlewares.use(middleware);
    },
    configurePreviewServer(server: { middlewares: { use: (fn: Connect.NextHandleFunction) => void } }) {
      server.middlewares.use(middleware);
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  return {
    plugins: [react(), tailwindcss(), edcHostApiPlugin()],
    define: {
      'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY),
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      port: 3001,
      hmr: process.env.DISABLE_HMR !== 'true',
    },
    preview: {
      port: 3001,
    },
  };
});
