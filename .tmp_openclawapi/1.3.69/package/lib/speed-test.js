const https = require('https');
const http = require('http');

// 测试 URL 的响应时间
async function testSpeed(url) {
  return new Promise((resolve) => {
    const startTime = Date.now();
    const urlObj = new URL(url);
    const protocol = urlObj.protocol === 'https:' ? https : http;

    const timeout = 5000; // 5秒超时

    const req = protocol.get(url, { timeout }, (res) => {
      const endTime = Date.now();
      const latency = endTime - startTime;

      // 读取响应数据（避免连接挂起）
      res.on('data', () => {});
      res.on('end', () => {
        resolve({
          success: true,
          latency,
          statusCode: res.statusCode
        });
      });
    });

    req.on('timeout', () => {
      req.destroy();
      resolve({
        success: false,
        latency: timeout,
        error: '超时'
      });
    });

    req.on('error', (error) => {
      const endTime = Date.now();
      resolve({
        success: false,
        latency: endTime - startTime,
        error: error.message
      });
    });
  });
}

// 测试多个中转站的速度
async function testMultipleRelays(relays) {
  const results = [];

  for (const relay of relays) {
    // 构建测试 URL（去掉 /v1 后缀，只测试基础域名）
    const baseUrl = relay.baseUrl.replace(/\/v1$/, '');
    const testUrl = baseUrl;

    const result = await testSpeed(testUrl);
    results.push({
      name: relay.name,
      url: relay.baseUrl,
      ...result
    });
  }

  return results;
}

// 根据速度排序中转站
function sortBySpeed(results) {
  return results
    .filter(r => r.success)
    .sort((a, b) => a.latency - b.latency);
}

// 格式化延迟显示
function formatLatency(latency) {
  if (latency < 100) return 'excellent';
  if (latency < 300) return 'good';
  if (latency < 1000) return 'fair';
  return 'poor';
}

module.exports = {
  testSpeed,
  testMultipleRelays,
  sortBySpeed,
  formatLatency
};
