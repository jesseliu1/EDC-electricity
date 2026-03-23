import { Buffer } from 'node:buffer';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import express from 'express';

function normalizeBasePath(basePath) {
  const trimmed = `${basePath || '/'}`.trim();
  if (!trimmed || trimmed === '/') {
    return '/';
  }
  return `/${trimmed.replace(/^\/+|\/+$/g, '')}/`;
}

function normalizeEndpoint(endpoint) {
  return endpoint.trim().replace(/\/+$/, '');
}

function buildNodeName(endpoint) {
  try {
    return `EDC Gateway (${new URL(endpoint).host})`;
  } catch {
    return 'EDC Gateway';
  }
}

function decodeSensorPayload(rawText) {
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

async function loginEdc(config) {
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

async function fetchChannelSnapshot(endpoint, token) {
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
  const sensors = decodeSensorPayload(rawText);
  if (!Array.isArray(sensors)) {
    throw new Error('EDC 返回的设备清单格式无法识别。');
  }

  const channels = [];
  let enabledChannelCount = 0;
  for (const sensor of sensors) {
    const suid = String(sensor.uid || sensor.suid || '');
    const sensorName = String(sensor.sensorName || sensor.name || 'Unknown Device');
    const sensorNickname = String(sensor.sensorNickName || '');
    const sensorDesc = String(sensor.sensorDes || '');
    const deviceName = sensorNickname ? `${sensorNickname} · ${sensorName}` : `${sensorName} · ${suid}`;
    const area = sensorDesc || sensorNickname || sensorName;
    const channelList = Array.isArray(sensor.channelList) ? sensor.channelList : [];

    for (const channel of channelList) {
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

function createHostApiRouter(basePath) {
  const router = express.Router();
  const basePrefix = basePath === '/' ? '' : basePath.slice(0, -1);
  const paths = ['/host-api/edc/test-connection', '/host-api/edc/sync-channels'];
  if (basePrefix) {
    paths.push(`${basePrefix}/host-api/edc/test-connection`, `${basePrefix}/host-api/edc/sync-channels`);
  }

  router.post(paths, async (req, res) => {
    try {
      const { endpoint, token } = await loginEdc(req.body || {});
      const snapshot = await fetchChannelSnapshot(endpoint, token);
      const basePayload = {
        ok: true,
        nodeName: snapshot.nodeName,
        checkedAt: snapshot.checkedAt,
        meta: snapshot.meta,
      };

      if (req.path.endsWith('/host-api/edc/test-connection')) {
        res.json({
          ...basePayload,
          message: `连接成功，已读取 ${snapshot.meta.sensorCount} 台设备 / ${snapshot.meta.channelCount} 通道。`,
        });
        return;
      }

      res.json({
        ...basePayload,
        channels: snapshot.channels,
        message: `同步完成，已刷新 ${snapshot.meta.channelCount} 条通道目录。`,
      });
    } catch (error) {
      res.status(500).json({
        ok: false,
        message: error instanceof Error ? error.message : '宿主调用 EDC 失败。',
      });
    }
  });

  return router;
}

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const port = Number(process.env.PORT || 3001);
const basePath = normalizeBasePath(process.env.ASNS_BASE_PATH || process.env.VITE_ASNS_BASE_PATH || '/');
const distDir = path.join(__dirname, 'dist');
const indexFile = path.join(distDir, 'index.html');
const basePrefix = basePath === '/' ? '' : basePath.slice(0, -1);

app.use(express.json({ limit: '1mb' }));
app.use(createHostApiRouter(basePath));

if (basePath === '/') {
  app.use(express.static(distDir));
  app.get('*', (_req, res) => {
    res.sendFile(indexFile);
  });
} else {
  app.use(basePath, express.static(distDir));
  app.get([basePrefix, `${basePrefix}/*`], (_req, res) => {
    res.sendFile(indexFile);
  });
}

app.listen(port, () => {
  console.log(`ASNS host listening on ${port} with base path ${basePath}`);
});
