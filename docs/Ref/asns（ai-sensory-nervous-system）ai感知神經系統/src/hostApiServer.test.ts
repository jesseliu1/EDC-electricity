import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createServer } from 'node:http';
import test from 'node:test';

type MockRequestRecord = {
  path: string;
  body: unknown;
};

function createNumericPayload(data: unknown): string {
  return Array.from(Buffer.from(JSON.stringify({ code: 0, data }), 'utf-8')).join(' ');
}

async function getFreePort(): Promise<number> {
  const server = createServer();
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const address = server.address();
  if (!address || typeof address === 'string') {
    throw new Error('无法获取测试端口。');
  }
  const { port } = address;
  server.close();
  await once(server, 'close');
  return port;
}

async function startMockEdcServer() {
  const requests: MockRequestRecord[] = [];
  const server = createServer(async (req, res) => {
    const chunks: Buffer[] = [];
    for await (const chunk of req) {
      chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
    }
    const rawBody = Buffer.concat(chunks).toString('utf-8');
    const body = rawBody ? JSON.parse(rawBody) : null;
    requests.push({ path: req.url || '', body });

    if (req.url === '/login') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ code: 0, data: 'mock-token-001' }));
      return;
    }

    if (req.url === '/systemcfg') {
      res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end(
        createNumericPayload([
          {
            uid: '2054',
            sensorName: '热电偶温度采集器',
            sensorNickName: 'A-1温度',
            sensorDes: 'A-1温度',
            channelList: [
              {
                cuid: '128',
                chnName: '热电偶温度采集通道',
                chnDim: '℃',
                status: '1',
              },
              {
                cuid: '129',
                chnName: '备用温度通道',
                chnDim: '℃',
                status: '0',
              },
            ],
          },
          {
            uid: '2349',
            sensorName: '三相智能电表',
            sensorNickName: '主电力',
            sensorDes: '主电力',
            channelList: [
              {
                cuid: '199',
                chnName: '总有功功率',
                chnDim: 'kW',
                status: '1',
              },
            ],
          },
        ]),
      );
      return;
    }

    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: false, message: 'not found' }));
  });

  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const address = server.address();
  if (!address || typeof address === 'string') {
    throw new Error('mock EDC 服务端口获取失败。');
  }

  return {
    server,
    endpoint: `http://127.0.0.1:${address.port}`,
    requests,
  };
}

async function stopServer(server: ReturnType<typeof createServer>): Promise<void> {
  if (!server.listening) {
    return;
  }
  server.close();
  await once(server, 'close');
}

async function postJsonWithRetry(url: string, body: unknown, retries = 20): Promise<Response> {
  let lastError: unknown;
  for (let attempt = 0; attempt < retries; attempt += 1) {
    try {
      return await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } catch (error) {
      lastError = error;
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
  }
  throw lastError instanceof Error ? lastError : new Error('宿主测试服务未能及时启动。');
}

test('server host-api accepts source-B-style numeric sensor payloads and returns connected summaries', async (t) => {
  const mockEdc = await startMockEdcServer();
  const hostPort = await getFreePort();
  const hostRoot =
    'D:\\project\\EDC electricity\\docs\\Ref\\asns（ai-sensory-nervous-system）ai感知神經系統';
  const hostLogs: string[] = [];
  const hostProc = spawn('node', ['server.mjs'], {
    cwd: hostRoot,
    env: {
      ...process.env,
      PORT: String(hostPort),
      ASNS_BASE_PATH: '/',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  hostProc.stdout.setEncoding('utf-8');
  hostProc.stderr.setEncoding('utf-8');
  hostProc.stdout.on('data', (chunk) => {
    hostLogs.push(chunk);
  });
  hostProc.stderr.on('data', (chunk) => {
    hostLogs.push(chunk);
  });

  t.after(async () => {
    hostProc.kill();
    await once(hostProc, 'exit').catch(() => undefined);
    await stopServer(mockEdc.server);
  });

  const payload = {
    endpoint: mockEdc.endpoint,
    username: 'admin',
    password: 'admin',
  };

  const testConnectionResponse = await postJsonWithRetry(
    `http://127.0.0.1:${hostPort}/host-api/edc/test-connection`,
    payload,
  );
  const testConnectionBody = (await testConnectionResponse.json()) as {
    ok: boolean;
    nodeName: string;
    meta: {
      source: string;
      sensorCount: number;
      channelCount: number;
      enabledChannelCount: number;
    };
    message: string;
  };

  assert.equal(
    testConnectionResponse.status,
    200,
    `test-connection 未返回 200。宿主日志：\n${hostLogs.join('')}`,
  );
  assert.equal(testConnectionBody.ok, true);
  assert.equal(testConnectionBody.nodeName, `EDC Gateway (${new URL(mockEdc.endpoint).host})`);
  assert.deepEqual(testConnectionBody.meta, {
    source: mockEdc.endpoint,
    sensorCount: 2,
    channelCount: 3,
    enabledChannelCount: 2,
  });
  assert.match(testConnectionBody.message, /连接成功/);

  const syncChannelsResponse = await postJsonWithRetry(
    `http://127.0.0.1:${hostPort}/host-api/edc/sync-channels`,
    payload,
  );
  const syncChannelsBody = (await syncChannelsResponse.json()) as {
    ok: boolean;
    channels: Array<{
      id: string;
      deviceName: string;
      deviceType: string;
      area: string;
      suid: string;
      cuid: string;
      channelName: string;
      unit: string;
      lastValue: string;
      status: string;
    }>;
    message: string;
  };

  assert.equal(syncChannelsResponse.status, 200);
  assert.equal(syncChannelsBody.ok, true);
  assert.equal(syncChannelsBody.channels.length, 3);
  assert.deepEqual(
    syncChannelsBody.channels.map((item) => ({
      id: item.id,
      status: item.status,
      unit: item.unit,
      channelName: item.channelName,
    })),
    [
      {
        id: '2349-199',
        status: 'online',
        unit: 'kW',
        channelName: '总有功功率',
      },
      {
        id: '2054-128',
        status: 'online',
        unit: '℃',
        channelName: '热电偶温度采集通道',
      },
      {
        id: '2054-129',
        status: 'idle',
        unit: '℃',
        channelName: '备用温度通道',
      },
    ],
  );
  assert.match(syncChannelsBody.message, /同步完成/);

  assert.deepEqual(
    mockEdc.requests.map((item) => item.path),
    ['/login', '/systemcfg', '/login', '/systemcfg'],
  );
  assert.deepEqual(mockEdc.requests[0]?.body, {
    username: 'admin',
    password: 'admin',
  });
  assert.deepEqual(mockEdc.requests[1]?.body, {
    request: 'getAllSensorList',
    value: '',
    token: 'mock-token-001',
  });
});
