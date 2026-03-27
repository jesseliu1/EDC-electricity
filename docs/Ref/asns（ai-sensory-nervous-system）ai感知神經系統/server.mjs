import { Buffer } from 'node:buffer';
import { existsSync, readFileSync } from 'node:fs';
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

function trimTrailingSlash(value) {
  return `${value || ''}`.replace(/\/+$/, '');
}

function buildNodeName(endpoint) {
  try {
    return `EDC Gateway (${new URL(endpoint).host})`;
  } catch {
    return 'EDC Gateway';
  }
}

function buildProxyBody(req) {
  if (req.method === 'GET' || req.method === 'HEAD') {
    return undefined;
  }
  if (req.body == null || req.body === '') {
    return undefined;
  }
  if (Buffer.isBuffer(req.body) || typeof req.body === 'string') {
    return req.body;
  }
  return JSON.stringify(req.body);
}

async function proxyRequest(req, res, upstreamBase) {
  const targetUrl = new URL(req.originalUrl, `${trimTrailingSlash(upstreamBase)}/`);
  const headers = new Headers();
  for (const [key, value] of Object.entries(req.headers)) {
    if (value == null) {
      continue;
    }
    const lowerKey = key.toLowerCase();
    if (lowerKey === 'host' || lowerKey === 'content-length' || lowerKey === 'connection') {
      continue;
    }
    headers.set(key, Array.isArray(value) ? value.join(', ') : value);
  }

  const body = buildProxyBody(req);
  if (
    body != null &&
    !headers.has('content-type') &&
    typeof req.body === 'object' &&
    !Buffer.isBuffer(req.body)
  ) {
    headers.set('content-type', 'application/json');
  }

  const upstreamResponse = await fetch(targetUrl, {
    method: req.method,
    headers,
    body,
    redirect: 'manual',
  });

  res.status(upstreamResponse.status);
  upstreamResponse.headers.forEach((value, key) => {
    const lowerKey = key.toLowerCase();
    if (lowerKey === 'content-encoding' || lowerKey === 'transfer-encoding' || lowerKey === 'connection') {
      return;
    }
    res.setHeader(key, value);
  });

  const payload = Buffer.from(await upstreamResponse.arrayBuffer());
  res.end(payload);
}

function detectPublishedAssetsDir(indexFile) {
  if (!existsSync(indexFile)) {
    return null;
  }
  const html = readFileSync(indexFile, 'utf-8');
  const match = html.match(/\/edc\/([^/]+)\/index-[^"']+\.js/);
  return match?.[1] || null;
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
  const compatibilityPrefixes = basePath === '/' ? ['/asns'] : [];
  const paths = ['/host-api/edc/test-connection', '/host-api/edc/sync-channels'];
  if (basePrefix) {
    paths.push(`${basePrefix}/host-api/edc/test-connection`, `${basePrefix}/host-api/edc/sync-channels`);
  }
  for (const prefix of compatibilityPrefixes) {
    paths.push(`${prefix}/host-api/edc/test-connection`, `${prefix}/host-api/edc/sync-channels`);
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
const compatibilityPrefixes = basePath === '/' ? ['/asns'] : [];
const edcWebRoot = process.env.ASNS_EDC_WEB_ROOT || '/var/www/edc-electricity';
const edcIndexFile = path.join(edcWebRoot, 'index.html');
const edcApiBase = process.env.ASNS_EDC_API_BASE || 'http://127.0.0.1:8001';
const edcAssetsAliasDir = detectPublishedAssetsDir(edcIndexFile);

app.use(express.json({ limit: '1mb' }));
app.use(createHostApiRouter(basePath));
app.use('/api', async (req, res, next) => {
  try {
    await proxyRequest(req, res, edcApiBase);
  } catch (error) {
    next(error);
  }
});

if (existsSync(edcIndexFile)) {
  if (edcAssetsAliasDir) {
    app.use('/edc/assets', express.static(path.join(edcWebRoot, edcAssetsAliasDir)));
  }
  app.use('/edc', express.static(edcWebRoot));
  app.get(['/edc', '/edc/*'], (_req, res) => {
    res.sendFile(edcIndexFile);
  });
}

if (basePath === '/') {
  for (const prefix of compatibilityPrefixes) {
    app.use(prefix, express.static(distDir));
  }
  app.use(express.static(distDir));
  for (const prefix of compatibilityPrefixes) {
    app.get([prefix, `${prefix}/*`], (_req, res) => {
      res.sendFile(indexFile);
    });
  }
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
