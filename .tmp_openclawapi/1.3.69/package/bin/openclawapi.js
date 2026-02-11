#!/usr/bin/env node

const inquirer = require('inquirer');
const chalk = require('chalk');
const fs = require('fs');
const JSON5 = require('json5');
const path = require('path');
const os = require('os');
const https = require('https');
const http = require('http');
const crypto = require('crypto');
const net = require('net');
const { exec, execFileSync, execSync, spawn } = require('child_process');
const ora = require('ora');
const DEFAULT_AUTH_MODE = 'api-key';

// ============ 错误码定义 ============
const ERROR_CODES = {
  NODE_VERSION: { code: 1, message: 'Node.js 版本过低' },
  OPENCLAW_NOT_FOUND: { code: 2, message: '未检测到 OpenClaw 安装' },
  OPENCLAW_CMD_NOT_FOUND: { code: 3, message: '未找到 openclaw 命令' },
  CONFIG_FAILED: { code: 4, message: '配置失败' },
  GATEWAY_RESTART_FAILED: { code: 5, message: 'Gateway 重启失败' },
  INVALID_INPUT: { code: 6, message: '输入无效' },
  PERMISSION_DENIED: { code: 7, message: '权限不足' },
  NETWORK_ERROR: { code: 8, message: '网络错误' },
  API_TEST_FAILED: { code: 9, message: 'API 测试失败' },
};

// 退出并显示错误
function exitWithError(errorType, details = '', solutions = []) {
  const err = ERROR_CODES[errorType] || { code: 99, message: '未知错误' };
  console.log(chalk.bold(chalk.red('\n========================================')));
  console.log(chalk.bold(chalk.red(`❌ 错误: ${err.message}`)));
  console.log(chalk.bold(chalk.red('========================================')));
  if (details) console.log(chalk.gray(`  ${details}`));
  if (solutions.length > 0) {
    console.log(chalk.cyan('\n解决方案:'));
    solutions.forEach((s, i) => console.log(`  ${i + 1}. ${s}`));
  }
  console.log(chalk.gray(`\n错误码: ${err.code}`));
  process.exit(err.code);
}

function safeExec(cmd, options = {}) {
  try {
    const output = execSync(cmd, { encoding: 'utf8', stdio: 'pipe', ...options });
    return { ok: true, output: output.trim() };
  } catch (e) {
    return {
      ok: false,
      error: e.message,
      stderr: e.stderr?.toString() || '',
      stdout: e.stdout?.toString() || ''
    };
  }
}

// ============ 预设 (默认值, 可由 API节点设置.md 覆盖) ============
const DEFAULT_ENDPOINTS = [
  { name: '国内主节点', url: 'https://yunyi.rdzhvip.com' },
  { name: 'CF国外节点1', url: 'https://yunyi.cfd' },
  { name: 'CF国外节点2', url: 'https://cdn1.yunyi.cfd' },
  { name: 'CF国外节点3', url: 'https://cdn2.yunyi.cfd' }
];

const FALLBACK_ENDPOINTS = [
  { name: '备用节点1', url: 'http://47.99.42.193' },
  { name: '备用节点2', url: 'http://47.97.100.10' }
];

const DEFAULT_CLAUDE_MODELS = [
  { id: 'claude-opus-4-6', name: 'Claude Opus 4.6' },
  { id: 'claude-sonnet-4-5', name: 'Claude Sonnet 4.5' },
  { id: 'claude-haiku-4-5', name: 'Claude Haiku 4.5' }
];

const DEFAULT_CODEX_MODELS = [
  { id: 'gpt-5.3-codex', name: 'GPT 5.3 Codex' },
  { id: 'gpt-5.2', name: 'GPT 5.2' }
];

const DEFAULT_API_CONFIG = {
  claude: {
    urlSuffix: '/claude',
    api: 'anthropic-messages',
    contextWindow: 200000,
    maxTokens: 8192,
    providerName: 'claude-yunyi'
  },
  codex: {
    urlSuffix: '/codex',
    api: 'openai-responses',
    contextWindow: 128000,
    maxTokens: 32768,
    providerName: 'yunyi'
  }
};

function normalizeEndpoints(raw, fallback) {
  if (!Array.isArray(raw)) return fallback;
  const normalized = raw
    .map(item => ({
      name: String(item?.name || '').trim(),
      url: String(item?.url || '').trim()
    }))
    .filter(item => item.name && item.url);
  return normalized.length > 0 ? normalized : fallback;
}

function normalizeModels(raw, fallback) {
  if (!Array.isArray(raw)) return fallback;
  const normalized = raw
    .map(item => {
      const id = String(item?.id || item?.model || '').trim();
      const name = String(item?.name || id).trim();
      return id ? { id, name } : null;
    })
    .filter(Boolean);
  return normalized.length > 0 ? normalized : fallback;
}

function normalizeApiConfig(raw, fallback) {
  if (!raw || typeof raw !== 'object') return fallback;
  const merged = { ...fallback };
  for (const key of Object.keys(fallback)) {
    if (!raw[key]) continue;
    merged[key] = { ...fallback[key], ...raw[key] };
  }
  return merged;
}

function extractJsonBlockFromMarkdown(markdown) {
  if (!markdown) return null;
  const fenceRegex = /```(?:json5|json)?\s*([\s\S]*?)```/i;
  const match = markdown.match(fenceRegex);
  if (match && match[1]) return match[1].trim();
  return null;
}

function parsePresetFile(filePath) {
  const raw = fs.readFileSync(filePath, 'utf8');
  if (filePath.toLowerCase().endsWith('.md')) {
    const jsonBlock = extractJsonBlockFromMarkdown(raw);
    if (jsonBlock) return JSON5.parse(jsonBlock);
  }
  return JSON5.parse(raw);
}

function loadPresetData() {
  const defaultData = {
    endpoints: DEFAULT_ENDPOINTS,
    fallbackEndpoints: FALLBACK_ENDPOINTS,
    models: {
      claude: DEFAULT_CLAUDE_MODELS,
      codex: DEFAULT_CODEX_MODELS
    },
    apiConfig: DEFAULT_API_CONFIG
  };

  const envPreset = process.env.OPENCLAW_PRESET_PATH;
  const presetCandidates = [
    envPreset,
    path.join(__dirname, '..', 'config', 'API节点设置.md'),
    path.join(__dirname, 'API节点设置.md'),
    path.join(__dirname, 'presets.json')
  ].filter(Boolean);

  const presetPath = presetCandidates.find(p => fs.existsSync(p));
  if (!presetPath) return defaultData;

  try {
    const parsed = parsePresetFile(presetPath);
    return {
      endpoints: normalizeEndpoints(parsed?.endpoints, DEFAULT_ENDPOINTS),
      fallbackEndpoints: normalizeEndpoints(parsed?.fallbackEndpoints, FALLBACK_ENDPOINTS),
      models: {
        claude: normalizeModels(parsed?.models?.claude, DEFAULT_CLAUDE_MODELS),
        codex: normalizeModels(parsed?.models?.codex, DEFAULT_CODEX_MODELS)
      },
      apiConfig: normalizeApiConfig(parsed?.apiConfig, DEFAULT_API_CONFIG)
    };
  } catch (error) {
    const hint = path.basename(presetPath);
    console.log(chalk.yellow(`⚠️ ${hint} 读取失败，已使用默认配置: ${error.message}`));
    return defaultData;
  }
}

const PRESETS = loadPresetData();
const ENDPOINTS = PRESETS.endpoints;
const FALLBACK_EPS = PRESETS.fallbackEndpoints;
const CLAUDE_MODELS = PRESETS.models.claude;
const CODEX_MODELS = PRESETS.models.codex;
const API_CONFIG = PRESETS.apiConfig;

// 备份文件名
const BACKUP_FILENAME = 'openclaw-default.json.bak';
const EXTRA_BIN_DIRS = [
  path.join(os.homedir(), '.npm-global', 'bin'),
  path.join(os.homedir(), '.local', 'bin'),
  '/usr/local/bin',
  '/usr/local/sbin',
  '/usr/bin',
  '/usr/sbin',
  '/bin',
  '/sbin',
  '/opt/moltbot/bin',
  '/opt/moltbot/node/bin'
];

// ============ 测速功能 ============
async function testSpeed(url) {
  return new Promise((resolve) => {
    const startTime = Date.now();
    const urlObj = new URL(url);
    const protocol = urlObj.protocol === 'https:' ? https : http;
    const timeout = 5000;

    const req = protocol.get(url, { timeout, rejectUnauthorized: false }, (res) => {
      const endTime = Date.now();
      res.on('data', () => {});
      res.on('end', () => {
        resolve({ success: true, latency: endTime - startTime });
      });
    });

    req.on('timeout', () => {
      req.destroy();
      resolve({ success: false, latency: null, error: '超时' });
    });

    req.on('error', () => {
      resolve({ success: false, latency: null, error: '连接失败' });
    });
  });
}

async function testAllEndpoints(endpoints = ENDPOINTS) {
  const spinner = ora({ text: `检测中... (0/${endpoints.length} 完成)`, spinner: 'dots' }).start();
  let done = 0;
  const results = await Promise.all(endpoints.map(async (ep) => {
    const result = await testSpeed(ep.url);
    done++;
    spinner.text = `检测中... (${done}/${endpoints.length} 完成)`;
    return { ...ep, ...result };
  }));
  spinner.stop();
  for (const r of results) {
    if (r.success) {
      console.log(chalk.gray(`  ${r.name}`) + chalk.green(` ${r.latency}ms`));
    } else {
      console.log(chalk.gray(`  ${r.name}`) + chalk.red(` ${r.error}`));
    }
  }
  return results;
}

async function testFallbackEndpoints() {
  if (FALLBACK_EPS.length === 0) return [];
  const spinner = ora({ text: `检测备用节点... (0/${FALLBACK_EPS.length} 完成)`, spinner: 'dots' }).start();
  let done = 0;
  const results = await Promise.all(FALLBACK_EPS.map(async (ep) => {
    const result = await testSpeed(ep.url);
    done++;
    spinner.text = `检测备用节点... (${done}/${FALLBACK_EPS.length} 完成)`;
    return { ...ep, ...result };
  }));
  spinner.stop();
  for (const r of results) {
    if (r.success) {
      console.log(chalk.gray(`  ${r.name}`) + chalk.green(` ${r.latency}ms`));
    } else {
      console.log(chalk.gray(`  ${r.name}`) + chalk.red(` ${r.error}`));
    }
  }
  return results;
}

// ============ API Key 验证 ============
function httpGetJson(url, headers = {}, timeout = 10000) {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);
    const protocol = urlObj.protocol === 'https:' ? https : http;
    const req = protocol.get(url, { headers, timeout, rejectUnauthorized: false }, (res) => {
      let data = '';
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => {
        try { resolve({ status: res.statusCode, data: JSON.parse(data) }); }
        catch { resolve({ status: res.statusCode, data: data }); }
      });
    });
    req.on('timeout', () => { req.destroy(); reject(new Error('请求超时')); });
    req.on('error', (e) => reject(e));
  });
}

async function validateApiKey(nodeUrl, apiKey) {
  const verifyUrl = `${nodeUrl.replace(/\/+$/, '')}/user/api/v1/me`;
  const spinner = ora({ text: '正在验证 API Key...', spinner: 'dots' }).start();
  try {
    const res = await httpGetJson(verifyUrl, { Authorization: `Bearer ${apiKey}` });
    if (res.status === 200 && res.data) {
      spinner.succeed('API Key 验证成功');
      if (res.data.service_type) {
        console.log(chalk.gray(`  服务类型: ${res.data.service_type}`));
      }
      if (res.data.status && res.data.status !== 'active') {
        console.log(chalk.yellow(`  ⚠ 状态: ${res.data.status}`));
      }
      return { valid: true, data: res.data };
    } else {
      spinner.fail('API Key 验证失败');
      console.log(chalk.red(`  HTTP ${res.status}`));
      return { valid: false, status: res.status };
    }
  } catch (err) {
    spinner.fail('API Key 验证失败');
    console.log(chalk.gray(`  ${err.message}`));
    return { valid: false, error: err.message };
  }
}

// ============ 配置路径 ============
function getMoltbotStateDirs(homeDir) {
  const candidates = [];
  if (process.env.MOLTBOT_STATE_DIR) candidates.push(process.env.MOLTBOT_STATE_DIR);
  candidates.push(path.join(homeDir, '.moltbot'));
  candidates.push('/opt/moltbot');
  candidates.push('/opt/moltbot/.moltbot');
  candidates.push('/etc/moltbot');
  candidates.push('/var/lib/moltbot');
  return candidates.filter((value, index) => value && candidates.indexOf(value) === index);
}

function buildStateCandidates(baseDirs) {
  const configs = [];
  for (const baseDir of baseDirs) {
    configs.push(
      path.join(baseDir, 'moltbot.json'),
      path.join(baseDir, 'openclaw.json'),
      path.join(baseDir, 'clawdbot.json'),
      path.join(baseDir, 'config', 'moltbot.json'),
      path.join(baseDir, 'config', 'openclaw.json'),
      path.join(baseDir, 'config', 'clawdbot.json')
    );
  }
  return configs;
}

function buildAuthCandidates(baseDirs) {
  const auths = [];
  for (const baseDir of baseDirs) {
    auths.push(
      path.join(baseDir, 'agents', 'main', 'agent', 'auth-profiles.json'),
      path.join(baseDir, 'agent', 'auth-profiles.json')
    );
  }
  return auths;
}

function getConfigPath() {
  const homeDir = os.homedir();
  const openclawStateDir = process.env.OPENCLAW_STATE_DIR || path.join(homeDir, '.openclaw');
  const clawdbotStateDir = process.env.CLAWDBOT_STATE_DIR || path.join(homeDir, '.clawdbot');
  const moltbotStateDirs = getMoltbotStateDirs(homeDir);
  const moltbotPrimaryDir = moltbotStateDirs.find(dir => fs.existsSync(dir)) || path.join(homeDir, '.moltbot');

  const envConfig = process.env.OPENCLAW_CONFIG_PATH || process.env.CLAWDBOT_CONFIG_PATH || process.env.MOLTBOT_CONFIG_PATH;
  const envConfigName = envConfig ? path.basename(envConfig).toLowerCase() : '';
  const envHintsMoltbot = envConfigName.includes('moltbot');
  const { cliName } = getCliMeta();

  const moltbotCandidates = buildStateCandidates(moltbotStateDirs);

  const openclawCandidates = [
    path.join(openclawStateDir, 'openclaw.json'),
    path.join(openclawStateDir, 'moltbot.json'),
    path.join(clawdbotStateDir, 'openclaw.json'),
    path.join(clawdbotStateDir, 'clawdbot.json'),
    path.join(clawdbotStateDir, 'moltbot.json')
  ];

  const moltbotExisting = moltbotCandidates.find(p => p && fs.existsSync(p));
  const moltbotDirExists = moltbotStateDirs.some(dir => fs.existsSync(dir));
  const preferMoltbot = envHintsMoltbot || moltbotDirExists || !!moltbotExisting || cliName === 'moltbot';

  const candidates = [];
  if (envConfig) candidates.push(envConfig);
  if (preferMoltbot) {
    candidates.push(...moltbotCandidates, ...openclawCandidates);
  } else {
    candidates.push(...openclawCandidates, ...moltbotCandidates);
  }

  const defaultConfig = preferMoltbot
    ? path.join(moltbotPrimaryDir, 'moltbot.json')
    : path.join(openclawStateDir, 'openclaw.json');

  const openclawConfig = candidates.find(p => p && fs.existsSync(p)) || (envConfig || defaultConfig);

  const configDir = path.dirname(openclawConfig);

  const baseAuthCandidates = buildAuthCandidates([openclawStateDir, clawdbotStateDir]);
  const moltbotAuthCandidates = buildAuthCandidates(moltbotStateDirs);

  const authCandidates = preferMoltbot
    ? [...moltbotAuthCandidates, ...baseAuthCandidates]
    : [...baseAuthCandidates, ...moltbotAuthCandidates];

  const authProfiles = authCandidates.find(p => fs.existsSync(p)) || authCandidates[0];

  const syncTargets = [];
  if (openclawConfig.startsWith(openclawStateDir) && fs.existsSync(clawdbotStateDir)) {
    syncTargets.push(
      path.join(clawdbotStateDir, 'openclaw.json'),
      path.join(clawdbotStateDir, 'clawdbot.json')
    );
  }

  return { openclawConfig, authProfiles, configDir, syncTargets };
}

// ============ 配置读写 ============
function readConfig(configPath) {
  if (fs.existsSync(configPath)) {
    const raw = fs.readFileSync(configPath, 'utf8');
    return JSON5.parse(raw);
  }
  return null;
}

function writeConfig(configPath, config) {
  const dir = path.dirname(configPath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf8');
}

function syncClawdbotConfigs(paths, config) {
  if (!paths.syncTargets || paths.syncTargets.length === 0) return;
  for (const target of paths.syncTargets) {
    if (target === paths.openclawConfig) continue;
    const dir = path.dirname(target);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(target, JSON.stringify(config, null, 2), 'utf8');
  }
}

function writeConfigWithSync(paths, config) {
  writeConfig(paths.openclawConfig, config);
  syncClawdbotConfigs(paths, config);
}

function coerceModelsRecord(value) {
  if (value && !Array.isArray(value) && typeof value === 'object') {
    return value;
  }

  const record = {};
  if (Array.isArray(value)) {
    for (const item of value) {
      if (typeof item === 'string') {
        record[item] = {};
        continue;
      }
      if (item && typeof item === 'object') {
        const key = item.key || item.id || item.model || item.name;
        if (!key) continue;
        const entry = {};
        if (item.alias) entry.alias = item.alias;
        record[key] = entry;
      }
    }
  }
  return record;
}

function ensureConfigStructure(config) {
  const next = config || {};
  if (!next.models) next.models = {};
  if (!next.models.providers) next.models.providers = {};
  if (!next.agents) next.agents = {};
  if (!next.agents.defaults) next.agents.defaults = {};
  if (!next.agents.defaults.model) next.agents.defaults.model = {};
  if (!next.agents.defaults.models || Array.isArray(next.agents.defaults.models) || typeof next.agents.defaults.models !== 'object') {
    next.agents.defaults.models = coerceModelsRecord(next.agents.defaults.models);
  }
  if (!next.auth) next.auth = {};
  if (!next.auth.profiles) next.auth.profiles = {};
  return next;
}

function pruneProvidersByPrefix(config, prefixBase, keepProviders = []) {
  if (!config?.models?.providers) return [];
  const removed = [];
  const keepSet = new Set(keepProviders);

  for (const name of Object.keys(config.models.providers)) {
    if (name.startsWith(prefixBase) && !keepSet.has(name)) {
      delete config.models.providers[name];
      removed.push(name);
    }
  }

  if (removed.length === 0) return removed;

  if (config?.agents?.defaults?.models) {
    for (const key of Object.keys(config.agents.defaults.models)) {
      const provider = key.split('/')[0];
      if (removed.includes(provider)) {
        delete config.agents.defaults.models[key];
      }
    }
  }

  if (config?.agents?.defaults?.model) {
    const currentPrimary = config.agents.defaults.model.primary || '';
    const currentProvider = currentPrimary.split('/')[0];
    if (removed.includes(currentProvider)) {
      config.agents.defaults.model.primary = '';
    }

    if (Array.isArray(config.agents.defaults.model.fallbacks)) {
      config.agents.defaults.model.fallbacks = config.agents.defaults.model.fallbacks.filter((modelKey) => {
        const provider = String(modelKey || '').split('/')[0];
        return provider && !removed.includes(provider);
      });
    }
  }

  return removed;
}

function pruneProvidersExcept(config, keepProviders = []) {
  if (!config?.models?.providers) return [];
  const removed = [];
  const keepSet = new Set(keepProviders);

  for (const name of Object.keys(config.models.providers)) {
    if (!keepSet.has(name)) {
      delete config.models.providers[name];
      removed.push(name);
    }
  }

  if (removed.length === 0) return removed;

  if (config?.agents?.defaults?.models) {
    for (const key of Object.keys(config.agents.defaults.models)) {
      const provider = key.split('/')[0];
      if (removed.includes(provider)) {
        delete config.agents.defaults.models[key];
      }
    }
  }

  if (config?.agents?.defaults?.model) {
    const currentPrimary = config.agents.defaults.model.primary || '';
    const currentProvider = currentPrimary.split('/')[0];
    if (removed.includes(currentProvider)) {
      config.agents.defaults.model.primary = '';
    }

    if (Array.isArray(config.agents.defaults.model.fallbacks)) {
      config.agents.defaults.model.fallbacks = config.agents.defaults.model.fallbacks.filter((modelKey) => {
        const provider = String(modelKey || '').split('/')[0];
        return provider && !removed.includes(provider);
      });
    }
  }

  if (config?.auth?.profiles) {
    for (const key of Object.keys(config.auth.profiles)) {
      const provider = key.split(':')[0];
      if (removed.includes(provider)) {
        delete config.auth.profiles[key];
      }
    }
  }

  return removed;
}

// Read auth-profiles.json in Gateway's versioned format { version, profiles }
function readAuthStore(authProfilesPath) {
  const store = { version: 1, profiles: {} };
  if (!fs.existsSync(authProfilesPath)) return store;
  try {
    const raw = JSON.parse(fs.readFileSync(authProfilesPath, 'utf8'));
    if (raw && typeof raw === 'object' && raw.profiles && typeof raw.profiles === 'object') {
      return raw; // already versioned
    }
    // migrate flat/legacy entries
    for (const [k, v] of Object.entries(raw)) {
      if (v && typeof v === 'object' && v.type) store.profiles[k] = v;
    }
  } catch {}
  return store;
}

function writeAuthStore(authProfilesPath, store) {
  fs.writeFileSync(authProfilesPath, JSON.stringify(store, null, 2), 'utf8');
}

function pruneAuthProfilesByPrefix(authProfilesPath, prefixBase, keepProviders = []) {
  const keepSet = new Set(keepProviders);
  const store = readAuthStore(authProfilesPath);

  const removed = [];
  for (const key of Object.keys(store.profiles)) {
    const provider = key.split(':')[0];
    if (provider.startsWith(prefixBase) && !keepSet.has(provider)) {
      delete store.profiles[key];
      removed.push(provider);
    }
  }

  if (removed.length > 0) {
    writeAuthStore(authProfilesPath, store);
  }

  return removed;
}

function pruneAuthProfilesExcept(authProfilesPath, keepProviders = []) {
  const keepSet = new Set(keepProviders);
  const store = readAuthStore(authProfilesPath);

  const removed = [];
  for (const key of Object.keys(store.profiles)) {
    const provider = key.split(':')[0];
    if (!keepSet.has(provider)) {
      delete store.profiles[key];
      removed.push(provider);
    }
  }

  if (removed.length > 0) {
    writeAuthStore(authProfilesPath, store);
  }

  return removed;
}

function updateAuthProfiles(authProfilesPath, providerName, apiKey) {
  const authDir = path.dirname(authProfilesPath);
  if (!fs.existsSync(authDir)) {
    fs.mkdirSync(authDir, { recursive: true });
  }

  const store = readAuthStore(authProfilesPath);
  const profileKey = `${providerName}:default`;
  store.profiles[profileKey] = {
    type: 'api_key',
    key: apiKey.trim(),
    provider: providerName
  };

  writeAuthStore(authProfilesPath, store);
}

function getApiKeyFromArgs(args, envFallbacks = []) {
  const direct = (args['api-key'] || args.apiKey || args.key || '').toString().trim();
  if (direct) return direct;

  for (const envKey of envFallbacks) {
    const value = (process.env[envKey] || '').toString().trim();
    if (value) return value;
  }

  return '';
}

async function promptApiKey(message, defaultValue) {
  // inquirer 的 password 类型在 Windows PowerShell 下会被跳过，
  // readline 和 inquirer 共享 stdin 在 Windows 上也会冲突。
  // 解决方案：用 inquirer 的 input 类型，加延迟确保上一个 prompt 完全释放 stdin。
  await new Promise(resolve => setTimeout(resolve, 100));
  const displayDefault = defaultValue
    ? ` (回车保留: ${defaultValue.slice(0, 4)}...${defaultValue.slice(-4)})`
    : '';
  const { apiKeyInput } = await inquirer.prompt([{
    type: 'input',
    name: 'apiKeyInput',
    message: (message || '请输入 API Key:') + displayDefault,
    validate: input => {
      if (input.trim() !== '') return true;
      if (defaultValue) return true;
      return 'API Key 不能为空';
    }
  }]);
  const key = apiKeyInput.trim();
  if (key) return key;
  if (defaultValue) return defaultValue;
  return '';
}

function extendPathEnv(preferredNodePath) {
  const current = process.env.PATH || '';
  const parts = current.split(path.delimiter).filter(Boolean);
  if (preferredNodePath) {
    const nodeDir = path.dirname(preferredNodePath);
    if (nodeDir && !parts.includes(nodeDir)) {
      parts.unshift(nodeDir);
    }
  }
  for (const extra of EXTRA_BIN_DIRS) {
    if (extra && !parts.includes(extra)) {
      parts.push(extra);
    }
  }
  return parts.join(path.delimiter);
}

function isNodeShebang(filePath) {
  try {
    const ext = path.extname(filePath).toLowerCase();
    if (ext === '.js' || ext === '.mjs' || ext === '.cjs') {
      return true;
    }
    const fd = fs.openSync(filePath, 'r');
    const buffer = Buffer.alloc(128);
    const bytes = fs.readSync(fd, buffer, 0, buffer.length, 0);
    fs.closeSync(fd);
    if (bytes <= 0) return false;
    const header = buffer.toString('utf8', 0, bytes);
    return header.startsWith('#!') && header.includes('node');
  } catch {
    return false;
  }
}

function shellQuote(value) {
  const str = String(value);
  return `"${str.replace(/(["\\$`])/g, '\\$1')}"`;
}

function escapeXml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function resolveCliBinary() {
  const override = process.env.OPENCLAW_CLI_PATH || process.env.CLAWDBOT_CLI_PATH || process.env.MOLTBOT_CLI_PATH;
  if (override) {
    try {
      if (fs.existsSync(override) && fs.statSync(override).isFile()) {
        return override;
      }
    } catch {}
  }

  // Validate that a found binary is a real gateway CLI, not openclawapi itself
  function isRealCli(filePath) {
    try {
      // Resolve symlinks to get the real target
      const realPath = fs.realpathSync(filePath);
      const baseName = path.basename(realPath).toLowerCase();
      // Skip if it points to openclawapi (our own config tool, not the gateway CLI)
      if (baseName === 'openclawapi' || baseName === 'openclawapi.js' || realPath.includes('openclawapi')) {
        return false;
      }
      return true;
    } catch {
      return true; // If we can't resolve, assume it's valid
    }
  }

  const candidates = ['openclaw', 'clawdbot', 'moltbot'];
  const searchDirs = (process.env.PATH || '').split(path.delimiter).concat(EXTRA_BIN_DIRS);
  for (const name of candidates) {
    for (const dir of searchDirs) {
      if (!dir) continue;
      const full = path.join(dir, name);
      try {
        if (fs.existsSync(full) && fs.statSync(full).isFile() && isRealCli(full)) {
          return full;
        }
      } catch {}
    }
  }

  const moltbotRoots = [];
  if (process.env.MOLTBOT_ROOT) moltbotRoots.push(process.env.MOLTBOT_ROOT);
  moltbotRoots.push('/opt/moltbot');
  moltbotRoots.push('/opt/moltbot/app');

  const scriptCandidates = [];
  for (const root of moltbotRoots) {
    scriptCandidates.push(
      path.join(root, 'moltbot.mjs'),
      path.join(root, 'bin', 'moltbot.mjs'),
      path.join(root, 'bin', 'moltbot.js'),
      path.join(root, 'src', 'moltbot.mjs'),
      path.join(root, 'src', 'moltbot.js')
    );
  }

  for (const candidate of scriptCandidates) {
    try {
      if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
        return candidate;
      }
    } catch {}
  }

  // Fallback: use login shell to find the binary (loads .zshrc/.bashrc PATH)
  for (const name of candidates) {
    if (process.platform === 'win32') {
      const r = safeExec(`where ${name}`);
      if (r.ok && r.output) {
        const resolved = r.output.split('\n')[0].trim();
        if (resolved && fs.existsSync(resolved) && isRealCli(resolved)) return resolved;
      }
    } else {
      // Try login shell (-l) so nvm/homebrew PATH is loaded
      for (const sh of ['/bin/zsh', '/bin/bash', '/bin/sh']) {
        if (!fs.existsSync(sh)) continue;
        const r = safeExec(`${sh} -lc "command -v ${name}"`);
        if (r.ok && r.output) {
          const resolved = r.output.split('\n')[0].trim();
          if (resolved && fs.existsSync(resolved) && isRealCli(resolved)) return resolved;
        }
      }
    }
  }

  // Fallback: check npm global bin directory
  const npmPrefixResult = safeExec('npm prefix -g');
  if (npmPrefixResult.ok && npmPrefixResult.output) {
    const npmBin = path.join(npmPrefixResult.output.trim(), 'bin');
    for (const name of candidates) {
      const full = path.join(npmBin, name);
      try {
        if (fs.existsSync(full) && fs.statSync(full).isFile() && isRealCli(full)) return full;
      } catch {}
    }
  }

  // Fallback: search common node_modules/.bin locations
  const extraSearchDirs = [
    path.join(os.homedir(), '.nvm', 'current', 'bin'),
    '/opt/homebrew/bin',
    '/opt/homebrew/sbin',
  ];
  // Add nvm version dirs
  const nvmDir = process.env.NVM_DIR || path.join(os.homedir(), '.nvm');
  const nvmVersionsDir = path.join(nvmDir, 'versions', 'node');
  try {
    if (fs.existsSync(nvmVersionsDir)) {
      for (const entry of fs.readdirSync(nvmVersionsDir)) {
        extraSearchDirs.push(path.join(nvmVersionsDir, entry, 'bin'));
      }
    }
  } catch {}

  for (const dir of extraSearchDirs) {
    for (const name of candidates) {
      const full = path.join(dir, name);
      try {
        if (fs.existsSync(full) && fs.statSync(full).isFile() && isRealCli(full)) return full;
      } catch {}
    }
  }

  return null;
}

function getCliMeta() {
  const cliBinary = resolveCliBinary();
  const cliName = cliBinary ? path.basename(cliBinary) : '';
  const cliLower = cliName.toLowerCase();
  const isMoltbot = cliLower.startsWith('moltbot') || cliLower.includes('moltbot');
  const nodeMajor = isMoltbot ? 24 : 22;
  return { cliBinary, cliName, nodeMajor };
}

function getNodeMajor(versionOutput) {
  const match = String(versionOutput || '').trim().match(/^v?(\d+)/);
  return match ? Number(match[1]) : null;
}

function findCompatibleNode(minMajor = 22) {
  const candidates = [];

  if (process.env.OPENCLAW_NODE_PATH) {
    candidates.push(process.env.OPENCLAW_NODE_PATH);
  }

  if (process.execPath) {
    candidates.push(process.execPath);
  }

  candidates.push('/usr/bin/node', '/usr/local/bin/node', '/opt/homebrew/bin/node', '/opt/moltbot/node/bin/node');

  const nvmDir = process.env.NVM_DIR || path.join(os.homedir(), '.nvm');
  const nvmVersionsDir = path.join(nvmDir, 'versions', 'node');
  if (fs.existsSync(nvmVersionsDir)) {
    try {
      const entries = fs.readdirSync(nvmVersionsDir);
      for (const entry of entries) {
        candidates.push(path.join(nvmVersionsDir, entry, 'bin', 'node'));
      }
    } catch {}
  }

  const seen = new Set();
  for (const candidate of candidates) {
    if (!candidate || seen.has(candidate)) continue;
    seen.add(candidate);
    try {
      if (!fs.existsSync(candidate)) continue;
      const version = execFileSync(candidate, ['-v'], { encoding: 'utf8', timeout: 2000 });
      const major = getNodeMajor(version);
      if (major && major >= minMajor) {
        return { path: candidate, version: version.trim(), major };
      }
    } catch {}
  }

  return null;
}

function ensureGatewaySettings(config) {
  if (!config.gateway) config.gateway = {};
  const gateway = config.gateway;

  if (!gateway.mode) gateway.mode = 'local';
  if (!gateway.bind) gateway.bind = 'loopback';
  if (!gateway.port) gateway.port = 18789;

  if (!gateway.auth) gateway.auth = {};
  if (!gateway.auth.mode) gateway.auth.mode = 'token';
  if (!gateway.auth.token) gateway.auth.token = crypto.randomBytes(24).toString('hex');

  if (!gateway.remote) gateway.remote = {};
  const isLocal = gateway.mode === 'local' || gateway.bind === 'loopback';
  if (isLocal && gateway.remote.token !== gateway.auth.token) {
    gateway.remote.token = gateway.auth.token;
  }
}

function isPortOpen(port, host = '127.0.0.1', timeoutMs = 800) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    let settled = false;

    const finish = (result) => {
      if (settled) return;
      settled = true;
      socket.destroy();
      resolve(result);
    };

    socket.setTimeout(timeoutMs);
    socket.once('connect', () => finish(true));
    socket.once('timeout', () => finish(false));
    socket.once('error', () => finish(false));

    socket.connect(port, host);
  });
}

async function waitForGateway(port, host = '127.0.0.1', timeoutMs = 8000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (await isPortOpen(port, host)) return true;
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  return false;
}

function spawnDetached(command, env) {
  try {
    const child = spawn(command, {
      shell: true,
      env,
      detached: true,
      stdio: 'ignore'
    });
    child.unref();
    return true;
  } catch {
    return false;
  }
}

function buildLaunchAgentPlist(label, command, stdoutPath, stderrPath) {
  return `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${escapeXml(label)}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>${escapeXml(command)}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${escapeXml(stdoutPath)}</string>
  <key>StandardErrorPath</key>
  <string>${escapeXml(stderrPath)}</string>
</dict>
</plist>`;
}

function installMacGatewayDaemon() {
  if (process.platform !== 'darwin') return { success: false, reason: 'not-darwin' };

  const { cliBinary, nodeMajor } = getCliMeta();
  if (!cliBinary) return { success: false, reason: 'cli-not-found' };

  const nodeInfo = findCompatibleNode(nodeMajor);
  const useNode = !!(nodeInfo && isNodeShebang(cliBinary));
  const pathEnv = extendPathEnv(nodeInfo ? nodeInfo.path : null);
  const command = useNode
    ? `PATH=${shellQuote(pathEnv)} ${shellQuote(nodeInfo.path)} ${shellQuote(cliBinary)} gateway`
    : `PATH=${shellQuote(pathEnv)} ${shellQuote(cliBinary)} gateway`;

  const label = 'com.openclaw.gateway';
  const launchAgentsDir = path.join(os.homedir(), 'Library', 'LaunchAgents');
  const logsDir = path.join(os.homedir(), 'Library', 'Logs');
  const plistPath = path.join(launchAgentsDir, `${label}.plist`);
  const stdoutPath = path.join(logsDir, 'openclaw-gateway.log');
  const stderrPath = path.join(logsDir, 'openclaw-gateway.err.log');

  try {
    fs.mkdirSync(launchAgentsDir, { recursive: true });
    fs.mkdirSync(logsDir, { recursive: true });

    const plist = buildLaunchAgentPlist(label, command, stdoutPath, stderrPath);
    fs.writeFileSync(plistPath, plist, 'utf8');

    const uid = typeof process.getuid === 'function' ? process.getuid() : null;
    if (!uid && uid !== 0) {
      return { success: false, reason: 'uid-missing', plistPath };
    }

    const domain = `gui/${uid}`;
    const service = `${domain}/${label}`;

    try { execFileSync('launchctl', ['bootout', service], { stdio: 'ignore' }); } catch {}
    execFileSync('launchctl', ['bootstrap', domain, plistPath], { stdio: 'ignore' });
    execFileSync('launchctl', ['kickstart', '-k', service], { stdio: 'ignore' });

    return { success: true, plistPath };
  } catch (error) {
    return { success: false, reason: error.message };
  }
}

async function tryAutoStartGateway(port, allowAutoDaemon) {
  const isRoot = typeof process.getuid === 'function' && process.getuid() === 0;

  if (process.platform === 'darwin' && allowAutoDaemon) {
    console.log(chalk.yellow('⚠️ Gateway 未检测到运行，尝试在 macOS 后台启动 (LaunchAgent)...'));
    const daemonResult = installMacGatewayDaemon();
    if (daemonResult.success) {
      console.log(chalk.green('✅ 已尝试安装并启动 LaunchAgent'));
      if (daemonResult.plistPath) {
        console.log(chalk.gray(`   配置: ${daemonResult.plistPath}`));
      }
      if (await waitForGateway(port, '127.0.0.1', 10000)) {
        return { started: true, method: 'launchd' };
      }
    } else {
      if (daemonResult.reason === 'cli-not-found') {
        console.log(chalk.red('❌ 未找到 openclaw/clawdbot/moltbot 命令，无法自动启动 Gateway'));
      } else {
        console.log(chalk.red(`❌ 自动启动失败: ${daemonResult.reason}`));
      }
    }
  }

  if (process.platform === 'linux' && allowAutoDaemon) {
    if (safeExec('command -v systemctl').ok) {
      if (!isRoot) {
        console.log(chalk.yellow('⚠️ Gateway 未检测到运行，尝试启动 systemd --user 服务...'));
        const systemdUser = safeExec('systemctl --user start openclaw');
        if (systemdUser.ok) {
          if (await waitForGateway(port, '127.0.0.1', 15000)) {
            console.log(chalk.green('✅ 已启动 systemd --user 服务'));
            return { started: true, method: 'systemd-user' };
          }
        }

        console.log(chalk.yellow('⚠️ systemd --user 启动失败，尝试启动 systemd 系统服务...'));
        const systemdSystem = safeExec('systemctl start openclaw');
        if (systemdSystem.ok) {
          if (await waitForGateway(port, '127.0.0.1', 15000)) {
            console.log(chalk.green('✅ 已启动 systemd 服务'));
            return { started: true, method: 'systemd' };
          }
        }
      } else {
        console.log(chalk.yellow('⚠️ Gateway 未检测到运行，尝试启动 systemd 系统服务...'));
        const systemdSystem = safeExec('systemctl start openclaw');
        if (systemdSystem.ok) {
          if (await waitForGateway(port, '127.0.0.1', 15000)) {
            console.log(chalk.green('✅ 已启动 systemd 服务'));
            return { started: true, method: 'systemd' };
          }
        }
      }
    }
  }

  const { cliBinary, nodeMajor } = getCliMeta();
  const nodeInfo = findCompatibleNode(nodeMajor);
  const env = { ...process.env, PATH: extendPathEnv(nodeInfo ? nodeInfo.path : null) };
  const useNode = cliBinary && nodeInfo && isNodeShebang(cliBinary);
  const cliCmd = cliBinary
    ? (useNode ? `"${nodeInfo.path}" "${cliBinary}" gateway` : `"${cliBinary}" gateway`)
    : null;

  const candidates = [];
  if (cliCmd) candidates.push(cliCmd);
  candidates.push('openclaw gateway', 'clawdbot gateway', 'moltbot gateway');

  for (const cmd of [...new Set(candidates)].filter(Boolean)) {
    console.log(chalk.yellow(`⚠️ 尝试启动 Gateway: ${cmd}`));
    if (spawnDetached(cmd, env)) {
      if (await waitForGateway(port, '127.0.0.1', 10000)) {
        console.log(chalk.green('✅ Gateway 已启动'));
        return { started: true, method: 'cli', cmd };
      }
    }
  }

  return { started: false };
}

// ============ 备份/恢复 ============
function backupOriginalConfig(configPath, configDir) {
  const backupPath = path.join(configDir, BACKUP_FILENAME);
  if (!fs.existsSync(backupPath) && fs.existsSync(configPath)) {
    fs.copyFileSync(configPath, backupPath);
    return true;
  }
  return false;
}

function restoreDefaultConfig(configPath, configDir) {
  const backupPath = path.join(configDir, BACKUP_FILENAME);
  if (fs.existsSync(backupPath)) {
    fs.copyFileSync(backupPath, configPath);
    return true;
  }
  return false;
}

// ============ URL 构建 ============
function buildFullUrl(baseUrl, type) {
  let trimmed = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
  if (type === 'claude') {
    trimmed = trimClaudeMessagesSuffix(trimmed);
  }
  const suffix = API_CONFIG[type].urlSuffix;
  if (trimmed.endsWith(suffix)) return trimmed;
  return trimmed + suffix;
}

function normalizeBaseUrl(baseUrl, type, confirmAutoAppend) {
  let trimmed = baseUrl.trim();
  if (!type || !API_CONFIG[type]) return trimmed;

  if (type === 'claude') {
    trimmed = trimClaudeMessagesSuffix(trimmed);
  }

  const suffix = API_CONFIG[type].urlSuffix;
  if (trimmed.includes(suffix)) return trimmed;

  const urlObj = new URL(trimmed);
  const shouldAutoAppend = urlObj.pathname === '/' || urlObj.pathname === '';

  if (!shouldAutoAppend) {
    return trimmed;
  }

  if (confirmAutoAppend === false) {
    return trimmed;
  }

  return buildFullUrl(trimmed, type);
}

function isValidUrl(urlString) {
  try {
    const url = new URL(urlString);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (!arg.startsWith('--')) {
      args._.push(arg);
      continue;
    }

    const raw = arg.slice(2);
    const [key, inlineValue] = raw.split('=');
    if (inlineValue !== undefined) {
      args[key] = inlineValue;
      continue;
    }

    const next = argv[i + 1];
    if (next && !next.startsWith('--')) {
      args[key] = next;
      i += 1;
    } else {
      args[key] = true;
    }
  }
  return args;
}

function trimClaudeMessagesSuffix(baseUrl) {
  const trimmed = baseUrl.trim();
  if (trimmed.endsWith('/v1/messages')) {
    return trimmed.slice(0, -'/v1/messages'.length);
  }
  return trimmed;
}

async function quickSetup(paths, args = {}) {
  console.log(chalk.cyan.bold('\n🚀 快速配置向导\n'));

  const typeArg = (args.type || args.t || '').toString().toLowerCase();
  const validTypes = ['claude', 'codex'];
  const initialType = validTypes.includes(typeArg) ? typeArg : null;

  const { relayType } = initialType
    ? { relayType: initialType }
    : await inquirer.prompt([{
        type: 'list',
        name: 'relayType',
        message: '选择类型:',
        choices: [
          { name: 'Claude', value: 'claude' },
          { name: 'Codex / GPT', value: 'codex' }
        ]
      }]);

  const type = relayType;
  const typeLabel = type === 'claude' ? 'Claude' : 'Codex';
  const apiConfig = API_CONFIG[type];

  const providerName = (args.provider || args['provider-name'] || apiConfig.providerName).toString().trim() || apiConfig.providerName;

  let baseUrl = (args['base-url'] || args.baseUrl || '').toString().trim();
  if (!baseUrl || !isValidUrl(baseUrl)) {
    const { baseUrlInput } = await inquirer.prompt([{
      type: 'input',
      name: 'baseUrlInput',
      message: `请输入 ${typeLabel} 中转 Base URL（可自动补全路径）:`,
      validate: input => isValidUrl(input.trim()) || '请输入有效的 URL (http:// 或 https://)'
    }]);
    baseUrl = baseUrlInput.trim();
  }

  const normalizedBaseUrl = normalizeBaseUrl(baseUrl, type, true);
  if (normalizedBaseUrl !== baseUrl) {
    console.log(chalk.gray(`已自动补全路径: ${normalizedBaseUrl}`));
  }

  const models = type === 'claude' ? CLAUDE_MODELS : CODEX_MODELS;

  let apiKey = (args['api-key'] || args.apiKey || '').toString();
  if (!apiKey) {
    apiKey = await promptApiKey(`请输入 ${typeLabel} API Key:`);
  }

  let modelId = (args.model || args['model-id'] || '').toString().trim();
  let modelName = (args['model-name'] || '').toString().trim();

  if (!modelId) {
    const { selectedModel } = await inquirer.prompt([{
      type: 'list',
      name: 'selectedModel',
      message: `选择 ${typeLabel} 模型:`,
      choices: models.map(m => ({ name: m.name, value: m.id }))
    }]);
    modelId = selectedModel;
  }

  const modelConfig = models.find(m => m.id === modelId);
  if (!modelName) {
    modelName = modelConfig ? modelConfig.name : modelId;
  }

  let setPrimary = true;
  if (args['no-primary'] || args['noPrimary']) {
    setPrimary = false;
  } else if (args.primary !== undefined || args['set-primary'] !== undefined) {
    const raw = args.primary !== undefined ? args.primary : args['set-primary'];
    if (typeof raw === 'string') {
      setPrimary = !['false', '0', 'no'].includes(raw.toLowerCase());
    } else {
      setPrimary = !!raw;
    }
  } else {
    const { confirmPrimary } = await inquirer.prompt([{
      type: 'confirm',
      name: 'confirmPrimary',
      message: '设为默认模型？',
      default: true
    }]);
    setPrimary = confirmPrimary;
  }

  let config = readConfig(paths.openclawConfig) || {};
  config = ensureConfigStructure(config);

  const existingProviders = Object.keys(config.models.providers || {});
  const toRemove = existingProviders.filter(name => name !== providerName);
  if (toRemove.length > 0 && !args.force) {
    const { overwrite } = await inquirer.prompt([{
      type: 'confirm',
      name: 'overwrite',
      message: `检测到已有中转配置: ${existingProviders.join(', ')}，将仅保留 ${providerName}。是否继续？`,
      default: false
    }]);
    if (!overwrite) {
      console.log(chalk.gray('已取消'));
      return;
    }
  }

  if (toRemove.length > 0) {
    pruneProvidersExcept(config, [providerName]);
    pruneAuthProfilesExcept(paths.authProfiles, [providerName]);
  }

  config.models.providers[providerName] = {
    baseUrl: normalizedBaseUrl,
    auth: DEFAULT_AUTH_MODE,
    api: apiConfig.api,
    headers: {},
    authHeader: false,
    apiKey: apiKey.trim(),
    models: [
      {
        id: modelId,
        name: modelName,
        contextWindow: apiConfig.contextWindow,
        maxTokens: apiConfig.maxTokens
      }
    ]
  };

  config.auth.profiles[`${providerName}:default`] = {
    provider: providerName,
    mode: 'api_key'
  };

  const modelKey = `${providerName}/${modelId}`;
  config.agents.defaults.models[modelKey] = { alias: providerName };

  if (setPrimary) {
    config.agents.defaults.model.primary = modelKey;
    config.agents.defaults.model.fallbacks = [];
  }

  const ws = ora({ text: '正在写入配置...', spinner: 'dots' }).start();
  ensureGatewaySettings(config);
  writeConfigWithSync(paths, config);
  updateAuthProfiles(paths.authProfiles, providerName, apiKey);
  ws.succeed('配置写入完成');

  console.log(chalk.green(`\n✅ ${typeLabel} 中转已配置完成！`));
  console.log(chalk.cyan(`   Provider: ${providerName}`));
  console.log(chalk.gray(`   Base URL: ${normalizedBaseUrl}`));
  console.log(chalk.gray(`   模型: ${modelName}`));
  console.log(chalk.gray(`   API Key: 已设置`));
  if (setPrimary) {
    console.log(chalk.yellow(`   主模型: ${modelKey}`));
  }
}

async function presetClaude(paths, args = {}) {
  console.log(chalk.cyan.bold('\n🚀 Claude 快速配置（自动测速推荐节点）\n'));

  const apiConfig = API_CONFIG.claude;
  const providerPrefix = (args['provider-prefix'] || args.prefix || apiConfig.providerName).toString().trim() || apiConfig.providerName;

  const shouldTest = !(args['no-test'] || args.noTest);
  let selectedEndpoint = ENDPOINTS[0];

  if (shouldTest) {
    console.log(chalk.cyan('📡 开始测速 Claude 节点...\n'));
    const results = await testAllEndpoints();
    const reachable = results.filter(r => r.success);

    if (reachable.length === 0) {
      console.log(chalk.red('\n⚠️  所有常规节点不可达'));
      if (FALLBACK_EPS.length > 0) {
        const { useFallback } = await inquirer.prompt([{
          type: 'confirm', name: 'useFallback',
          message: chalk.yellow('是否尝试备用节点？'), default: true
        }]);
        if (useFallback) {
          console.log('');
          const fbResults = await testFallbackEndpoints();
          const fbReachable = fbResults.filter(r => r.success);
          if (fbReachable.length > 0) {
            const sorted = fbReachable.sort((a, b) => a.latency - b.latency);
            selectedEndpoint = sorted[0];
            console.log(chalk.yellow(`\n⚠ 使用备用节点: ${selectedEndpoint.name} (${selectedEndpoint.latency}ms)\n`));
          } else {
            console.log(chalk.red('\n备用节点也不可达'));
            const { proceed } = await inquirer.prompt([{
              type: 'confirm', name: 'proceed',
              message: '仍要写入默认节点配置吗？', default: false
            }]);
            if (!proceed) { console.log(chalk.gray('已取消')); return; }
          }
        } else {
          const { proceed } = await inquirer.prompt([{
            type: 'confirm', name: 'proceed',
            message: '仍要写入默认节点配置吗？', default: false
          }]);
          if (!proceed) { console.log(chalk.gray('已取消')); return; }
        }
      } else {
        const { proceed } = await inquirer.prompt([{
          type: 'confirm', name: 'proceed',
          message: '仍要写入默认节点配置吗？', default: false
        }]);
        if (!proceed) { console.log(chalk.gray('已取消')); return; }
      }
    } else {
      const sortedReachable = reachable.sort((a, b) => a.latency - b.latency);
      selectedEndpoint = sortedReachable[0];
      console.log(chalk.green(`\n🏆 推荐节点（最低延迟）: ${selectedEndpoint.name} (${selectedEndpoint.latency}ms)\n`));
    }
  }

  const config = ensureConfigStructure(readConfig(paths.openclawConfig) || {});

  const providerName = (args['provider-name'] || args.provider || providerPrefix).toString().trim() || apiConfig.providerName;

  const existingProviders = Object.keys(config.models.providers || {});
  const toRemove = existingProviders.filter(name => name !== providerName);

  if (toRemove.length > 0 && !args.force) {
    const { overwrite } = await inquirer.prompt([{
      type: 'confirm',
      name: 'overwrite',
      message: `检测到已有中转配置: ${existingProviders.join(', ')}，将仅保留 ${providerName}。是否继续？`,
      default: false
    }]);
    if (!overwrite) {
      console.log(chalk.gray('已取消'));
      return;
    }
  }

  const removedProviders = toRemove.length > 0
    ? pruneProvidersExcept(config, [providerName])
    : [];
  if (removedProviders.length > 0) {
    pruneAuthProfilesExcept(paths.authProfiles, [providerName]);
  }

  const baseUrl = buildFullUrl(selectedEndpoint.url, 'claude');

  const apiKeyEnvFallbacks = [
    'OPENCLAW_CLAUDE_KEY',
    'CLAUDE_API_KEY',
    'OPENCLAW_API_KEY'
  ];
  const directKey = (args['api-key'] || args.apiKey || args.key || '').toString().trim();
  let apiKey;
  if (directKey) {
    apiKey = directKey;
  } else {
    const envKey = getApiKeyFromArgs({}, apiKeyEnvFallbacks);
    const configKey = config.models.providers[providerName]?.apiKey || '';
    const existingKey = envKey || configKey;
    apiKey = await promptApiKey('请输入 Claude API Key（将用于当前节点）:', existingKey);
  }

  // 验证 API Key
  console.log('');
  const validation = await validateApiKey(selectedEndpoint.url, apiKey);
  if (!validation.valid) {
    const { continueAnyway } = await inquirer.prompt([{
      type: 'confirm', name: 'continueAnyway',
      message: 'API Key 验证失败，是否仍然继续写入配置？', default: false
    }]);
    if (!continueAnyway) { console.log(chalk.gray('已取消')); return; }
  }

  const modelIdArg = (args.model || args['model-id'] || '').toString().trim();
  let modelId = modelIdArg;
  if (!modelId) {
    const { selectedModel } = await inquirer.prompt([{
      type: 'list',
      name: 'selectedModel',
      message: '选择 Claude 模型:',
      choices: CLAUDE_MODELS.map(m => ({ name: m.name, value: m.id }))
    }]);
    modelId = selectedModel;
  }

  const modelConfig = CLAUDE_MODELS.find(m => m.id === modelId);
  const modelName = modelConfig ? modelConfig.name : modelId;

  const modelKey = `${providerName}/${modelId}`;
  const currentPrimary = config.agents.defaults.model.primary || '';
  const currentProvider = currentPrimary.split('/')[0];

  let setPrimary = true;
  if (args['no-primary'] || args.noPrimary) {
    setPrimary = false;
  } else if (args.primary !== undefined || args['set-primary'] !== undefined) {
    const raw = args.primary !== undefined ? args.primary : args['set-primary'];
    if (typeof raw === 'string') {
      setPrimary = !['false', '0', 'no'].includes(raw.toLowerCase());
    } else {
      setPrimary = !!raw;
    }
  } else {
    const { confirmPrimary } = await inquirer.prompt([{
      type: 'confirm',
      name: 'confirmPrimary',
      message: '设为默认模型？',
      default: true
    }]);
    setPrimary = confirmPrimary;
  }

  config.models.providers[providerName] = {
    baseUrl,
    auth: DEFAULT_AUTH_MODE,
    api: apiConfig.api,
    headers: {},
    authHeader: false,
    apiKey: apiKey.trim(),
    models: [
      {
        id: modelId,
        name: modelName,
        contextWindow: apiConfig.contextWindow,
        maxTokens: apiConfig.maxTokens
      }
    ]
  };

  config.auth.profiles[`${providerName}:default`] = {
    provider: providerName,
    mode: 'api_key'
  };

  config.agents.defaults.models[modelKey] = { alias: providerName };

  if (setPrimary || !currentPrimary || removedProviders.includes(currentProvider)) {
    config.agents.defaults.model.primary = modelKey;
    config.agents.defaults.model.fallbacks = [];
  }

  const writeSpinner = ora({ text: '正在写入配置...', spinner: 'dots' }).start();
  ensureGatewaySettings(config);
  writeConfigWithSync(paths, config);
  updateAuthProfiles(paths.authProfiles, providerName, apiKey);
  writeSpinner.succeed('配置写入完成');

  console.log(chalk.green('\n✅ Claude 节点配置完成！'));
  const tag = setPrimary ? ' (主)' : '';
  console.log(chalk.cyan(`   ${providerName}${tag}: ${buildFullUrl(selectedEndpoint.url, 'claude')}`));
  console.log(chalk.gray(`   模型: ${modelName}`));
  console.log(chalk.gray('   API Key: 已设置'));

  const shouldTestGateway = args.test !== undefined
    ? !['false', '0', 'no'].includes(String(args.test).toLowerCase())
    : await inquirer.prompt([{
        type: 'confirm',
        name: 'testGateway',
        message: '是否立即通过 OpenClaw Gateway 测试？',
        default: true
      }]).then(r => r.testGateway);

  if (shouldTestGateway) {
    await testConnection(paths, args);
  }
}

async function presetCodex(paths, args = {}) {
  console.log(chalk.cyan.bold('\n🚀 Codex 快速配置（自动测速推荐节点）\n'));

  const apiConfig = API_CONFIG.codex;
  const providerPrefix = (args['provider-prefix'] || args.prefix || apiConfig.providerName).toString().trim() || apiConfig.providerName;
  const providerName = (args['provider-name'] || args.provider || providerPrefix).toString().trim() || apiConfig.providerName;

  const shouldTest = !(args['no-test'] || args.noTest);
  let selectedEndpoint = ENDPOINTS[0];

  if (shouldTest) {
    console.log(chalk.cyan('📡 开始测速 Codex 节点...\n'));
    const results = await testAllEndpoints();
    const reachable = results.filter(r => r.success);

    if (reachable.length === 0) {
      console.log(chalk.red('\n⚠️  所有常规节点不可达'));
      if (FALLBACK_EPS.length > 0) {
        const { useFallback } = await inquirer.prompt([{
          type: 'confirm', name: 'useFallback',
          message: chalk.yellow('是否尝试备用节点？'), default: true
        }]);
        if (useFallback) {
          console.log('');
          const fbResults = await testFallbackEndpoints();
          const fbReachable = fbResults.filter(r => r.success);
          if (fbReachable.length > 0) {
            const sorted = fbReachable.sort((a, b) => a.latency - b.latency);
            selectedEndpoint = sorted[0];
            console.log(chalk.yellow(`\n⚠ 使用备用节点: ${selectedEndpoint.name} (${selectedEndpoint.latency}ms)\n`));
          } else {
            console.log(chalk.red('\n备用节点也不可达'));
            const { proceed } = await inquirer.prompt([{
              type: 'confirm', name: 'proceed',
              message: '仍要写入默认节点配置吗？', default: false
            }]);
            if (!proceed) { console.log(chalk.gray('已取消')); return; }
          }
        } else {
          const { proceed } = await inquirer.prompt([{
            type: 'confirm', name: 'proceed',
            message: '仍要写入默认节点配置吗？', default: false
          }]);
          if (!proceed) { console.log(chalk.gray('已取消')); return; }
        }
      } else {
        const { proceed } = await inquirer.prompt([{
          type: 'confirm', name: 'proceed',
          message: '仍要写入默认节点配置吗？', default: false
        }]);
        if (!proceed) { console.log(chalk.gray('已取消')); return; }
      }
    } else {
      const sortedReachable = reachable.sort((a, b) => a.latency - b.latency);
      selectedEndpoint = sortedReachable[0];
      console.log(chalk.green(`\n🏆 推荐节点（最低延迟）: ${selectedEndpoint.name} (${selectedEndpoint.latency}ms)\n`));
    }
  }

  const config = ensureConfigStructure(readConfig(paths.openclawConfig) || {});
  const existingProviders = Object.keys(config.models.providers || {});
  const toRemove = existingProviders.filter(name => name !== providerName);

  if (toRemove.length > 0 && !args.force) {
    const { overwrite } = await inquirer.prompt([{
      type: 'confirm',
      name: 'overwrite',
      message: `检测到已有中转配置: ${existingProviders.join(', ')}，将仅保留 ${providerName}。是否继续？`,
      default: false
    }]);
    if (!overwrite) {
      console.log(chalk.gray('已取消'));
      return;
    }
  }

  const removedProviders = toRemove.length > 0
    ? pruneProvidersExcept(config, [providerName])
    : [];
  if (removedProviders.length > 0) {
    pruneAuthProfilesExcept(paths.authProfiles, [providerName]);
  }

  const baseUrl = buildFullUrl(selectedEndpoint.url, 'codex');

  const apiKeyEnvFallbacks = [
    'OPENCLAW_CODEX_KEY',
    'OPENAI_API_KEY',
    'OPENCLAW_API_KEY'
  ];
  const directKey = (args['api-key'] || args.apiKey || args.key || '').toString().trim();
  let apiKey;
  if (directKey) {
    apiKey = directKey;
  } else {
    const existingKey = getApiKeyFromArgs({}, apiKeyEnvFallbacks)
      || config.models.providers[providerName]?.apiKey || '';
    apiKey = await promptApiKey('请输入 Codex API Key（将用于当前节点）:', existingKey);
  }

  // 验证 API Key
  console.log('');
  const validation = await validateApiKey(selectedEndpoint.url, apiKey);
  if (!validation.valid) {
    const { continueAnyway } = await inquirer.prompt([{
      type: 'confirm', name: 'continueAnyway',
      message: 'API Key 验证失败，是否仍然继续写入配置？', default: false
    }]);
    if (!continueAnyway) { console.log(chalk.gray('已取消')); return; }
  }

  const modelIdArg = (args.model || args['model-id'] || '').toString().trim();
  let modelId = modelIdArg;
  if (!modelId) {
    const { selectedModel } = await inquirer.prompt([{
      type: 'list',
      name: 'selectedModel',
      message: '选择 Codex 模型:',
      choices: CODEX_MODELS.map(m => ({ name: m.name, value: m.id }))
    }]);
    modelId = selectedModel;
  }

  const modelConfig = CODEX_MODELS.find(m => m.id === modelId);
  const modelName = modelConfig ? modelConfig.name : modelId;

  const modelKey = `${providerName}/${modelId}`;
  const currentPrimary = config.agents.defaults.model.primary || '';
  const currentProvider = currentPrimary.split('/')[0];

  let setPrimary = true;
  if (args['no-primary'] || args.noPrimary) {
    setPrimary = false;
  } else if (args.primary !== undefined || args['set-primary'] !== undefined) {
    const raw = args.primary !== undefined ? args.primary : args['set-primary'];
    if (typeof raw === 'string') {
      setPrimary = !['false', '0', 'no'].includes(raw.toLowerCase());
    } else {
      setPrimary = !!raw;
    }
  } else {
    const { confirmPrimary } = await inquirer.prompt([{
      type: 'confirm',
      name: 'confirmPrimary',
      message: '设为默认模型？',
      default: true
    }]);
    setPrimary = confirmPrimary;
  }

  config.models.providers[providerName] = {
    baseUrl,
    auth: DEFAULT_AUTH_MODE,
    api: apiConfig.api,
    headers: {},
    authHeader: false,
    apiKey: apiKey.trim(),
    models: [
      {
        id: modelId,
        name: modelName,
        contextWindow: apiConfig.contextWindow,
        maxTokens: apiConfig.maxTokens
      }
    ]
  };

  config.auth.profiles[`${providerName}:default`] = {
    provider: providerName,
    mode: 'api_key'
  };

  config.agents.defaults.models[modelKey] = { alias: providerName };

  if (setPrimary || !currentPrimary || removedProviders.includes(currentProvider)) {
    config.agents.defaults.model.primary = modelKey;
    config.agents.defaults.model.fallbacks = [];
  }

  const writeSpinner2 = ora({ text: '正在写入配置...', spinner: 'dots' }).start();
  ensureGatewaySettings(config);
  writeConfigWithSync(paths, config);
  updateAuthProfiles(paths.authProfiles, providerName, apiKey);
  writeSpinner2.succeed('配置写入完成');

  console.log(chalk.green('\n✅ Codex 节点配置完成！'));
  const tag = setPrimary ? ' (主)' : '';
  console.log(chalk.cyan(`   ${providerName}${tag}: ${baseUrl}`));
  console.log(chalk.gray(`   模型: ${modelName}`));
  console.log(chalk.gray('   API Key: 已设置'));

  const shouldTestGateway = args.test !== undefined
    ? !['false', '0', 'no'].includes(String(args.test).toLowerCase())
    : await inquirer.prompt([{
        type: 'confirm',
        name: 'testGateway',
        message: '是否立即通过 OpenClaw Gateway 测试？',
        default: true
      }]).then(r => r.testGateway);

  if (shouldTestGateway) {
    await testConnection(paths, args);
  }
}

// ============ 主程序 ============
async function main() {
  console.clear();
  console.log(chalk.cyan.bold('\n🔧 OpenClaw API 配置工具\n'));

  const paths = getConfigPath();
  console.log(chalk.gray(`配置文件: ${paths.openclawConfig}\n`));

  // 首次运行备份
  if (backupOriginalConfig(paths.openclawConfig, paths.configDir)) {
    console.log(chalk.green('✓ 已备份原始配置\n'));
  }

  const args = parseArgs(process.argv.slice(2));
  if (args.quick || args._.includes('quick')) {
    await quickSetup(paths, args);
    return;
  }
  if (args.preset === 'claude' || args._.includes('preset-claude') || args._.includes('claude-preset')) {
    await presetClaude(paths, args);
    return;
  }
  if (args.preset === 'codex' || args._.includes('preset-codex') || args._.includes('codex-preset')) {
    await presetCodex(paths, args);
    return;
  }

  while (true) {
    // 显示当前状态
    const statusLine = getConfigStatusLine(paths);
    if (statusLine) {
      console.log(chalk.gray('─'.repeat(40)));
      console.log(statusLine);
      console.log(chalk.gray('─'.repeat(40)) + '\n');
    }

    const { action } = await inquirer.prompt([{
      type: 'list',
      name: 'action',
      message: '请选择操作:',
      pageSize: 10,
      loop: false,
      choices: [
        new inquirer.Separator(chalk.gray('── 配置模型 ──')),
        { name: '⚡ 激活 Claude', value: 'activate_claude' },
        { name: '⚡ 激活 Codex (GPT)', value: 'activate_codex' },
        new inquirer.Separator(chalk.gray('── 工具 ──')),
        { name: '→ 测试连接', value: 'test_connection' },
        { name: '→ 查看配置', value: 'view_config' },
        { name: '→ 恢复默认', value: 'restore' },
        new inquirer.Separator(''),
        { name: chalk.gray('退出'), value: 'exit' }
      ]
    }]);

    console.log('');

    if (action === 'exit') {
      console.log(chalk.cyan('👋 再见！\n'));
      process.exit(0);
    }

    try {
      switch (action) {
        case 'activate_claude':
          await presetClaude(paths, {});
          break;
        case 'activate_codex':
          await presetCodex(paths, {});
          break;
        case 'test_connection':
          await testConnection(paths, {});
          break;
        case 'view_config':
          await viewConfig(paths);
          break;
        case 'restore':
          await restore(paths);
          break;
      }
    } catch (error) {
      console.log(chalk.red(`\n错误: ${error.message}\n`));
    }

    // 操作完成后暂停，让用户看到结果
    await new Promise(resolve => setTimeout(resolve, 500));
    console.log('');
  }
}

// 获取当前配置状态摘要
function getConfigStatusLine(paths) {
  try {
    const config = readConfig(paths.openclawConfig);
    if (!config?.models?.providers) return null;

    const providers = Object.keys(config.models.providers);
    const primary = config?.agents?.defaults?.model?.primary || '';

    const parts = [];

    // 检查 Claude
    const hasClaude = providers.some(p => p.includes('claude') || p.includes('yunyi-claude'));
    if (hasClaude) {
      const isActive = primary.includes('claude');
      parts.push(isActive ? chalk.green('Claude ✓') : chalk.yellow('Claude ○'));
    }

    // 检查 Codex/GPT
    const hasCodex = providers.some(p => p.includes('codex') || p.includes('gpt') || p.includes('yunyi-codex'));
    if (hasCodex) {
      const isActive = primary.includes('codex') || primary.includes('gpt');
      parts.push(isActive ? chalk.green('Codex ✓') : chalk.yellow('Codex ○'));
    }

    if (parts.length === 0) {
      return chalk.gray('当前状态: 未配置任何模型');
    }

    return chalk.gray('当前状态: ') + parts.join('  ') + chalk.gray('  (✓ 主模型  ○ 已配置)');
  } catch {
    return null;
  }
}

// ============ 选择节点 (Claude/Codex) ============
async function selectNode(paths, type) {
  const typeLabel = type === 'claude' ? 'Claude' : 'Codex';
  const models = type === 'claude' ? CLAUDE_MODELS : CODEX_MODELS;
  const apiConfig = API_CONFIG[type];

  console.log(chalk.cyan(`📡 ${typeLabel} 节点测速中...\n`));

  const results = await testAllEndpoints();

  const sorted = results
    .filter(r => r.success)
    .sort((a, b) => a.latency - b.latency);

  if (sorted.length === 0) {
    console.log(chalk.red('\n所有节点都无法访问！'));
    return;
  }

  console.log(chalk.green(`\n🏆 最快节点: ${sorted[0].name} (${sorted[0].latency}ms)\n`));

  // 选择节点
  const { selectedIndex } = await inquirer.prompt([{
    type: 'list',
    name: 'selectedIndex',
    message: '选择节点:',
    choices: [
      { name: `🚀 使用最快节点 (${sorted[0].name})`, value: -1 },
      new inquirer.Separator('--- 或手动选择 ---'),
      ...sorted.map((e, i) => ({
        name: `${e.name} - ${e.latency}ms`,
        value: i
      }))
    ]
  }]);

  const primaryIndex = selectedIndex === -1 ? 0 : selectedIndex;
  const selectedEndpoint = sorted[primaryIndex];

  // 选择模型
  const { selectedModel } = await inquirer.prompt([{
    type: 'list',
    name: 'selectedModel',
    message: `选择 ${typeLabel} 模型:`,
    choices: models.map(m => ({ name: m.name, value: m.id }))
  }]);

  const modelConfig = models.find(m => m.id === selectedModel);

  // 读取或创建配置
  let config = readConfig(paths.openclawConfig) || {};

  // 初始化结构
  if (!config.models) config.models = {};
  if (!config.models.providers) config.models.providers = {};
  if (!config.agents) config.agents = {};
  if (!config.agents.defaults) config.agents.defaults = {};
  if (!config.agents.defaults.model) config.agents.defaults.model = {};
  if (!config.agents.defaults.models) config.agents.defaults.models = {};

  // 保留旧的 API Key
  const oldProvider = config.models.providers[apiConfig.providerName];
  const oldApiKey = oldProvider?.apiKey;

  // 添加/更新节点
  config.models.providers[apiConfig.providerName] = {
    baseUrl: buildFullUrl(selectedEndpoint.url, type),
    api: apiConfig.api,
    apiKey: oldApiKey,
    models: [{
      id: modelConfig.id,
      name: modelConfig.name,
      contextWindow: apiConfig.contextWindow,
      maxTokens: apiConfig.maxTokens
    }]
  };

  // 注册模型
  const modelKey = `${apiConfig.providerName}/${modelConfig.id}`;
  config.agents.defaults.models[modelKey] = { alias: apiConfig.providerName };

  writeConfigWithSync(paths, config);

  console.log(chalk.green(`\n✅ ${typeLabel} 节点配置完成！`));
  console.log(chalk.cyan(`   节点: ${selectedEndpoint.name} (${selectedEndpoint.url})`));
  console.log(chalk.gray(`   模型: ${modelConfig.name}`));
  console.log(chalk.gray(`   API Key: ${oldApiKey ? '已设置' : '未设置'}`));
}

// ============ 激活 (Claude/Codex) ============
async function activate(paths, type) {
  const typeLabel = type === 'claude' ? 'Claude' : 'Codex';
  const apiConfig = API_CONFIG[type];
  const models = type === 'claude' ? CLAUDE_MODELS : CODEX_MODELS;

  let config = readConfig(paths.openclawConfig);

  if (!config?.models?.providers?.[apiConfig.providerName]) {
    console.log(chalk.yellow(`⚠️ 请先选择 ${typeLabel} 节点`));
    return;
  }

  const provider = config.models.providers[apiConfig.providerName];
  const currentModelId = provider.models?.[0]?.id || models[0].id;
  const modelConfig = models.find(m => m.id === currentModelId) || models[0];

  // 输入 API Key
  const currentKey = provider.apiKey;
  const apiKey = await promptApiKey(`请输入 ${typeLabel} API Key:`, currentKey);

  // 保存 API Key
  config.models.providers[apiConfig.providerName].apiKey = apiKey;

  // 设置为主模型
  const modelKey = `${apiConfig.providerName}/${modelConfig.id}`;
  config.agents.defaults.model.primary = modelKey;
  config.agents.defaults.model.fallbacks = [];

  writeConfigWithSync(paths, config);

  // 同时写入 auth-profiles (versioned format)
  const authDir = path.dirname(paths.authProfiles);
  if (!fs.existsSync(authDir)) {
    fs.mkdirSync(authDir, { recursive: true });
  }

  const authStore = readAuthStore(paths.authProfiles);
  authStore.profiles[`${apiConfig.providerName}:default`] = { type: 'api_key', key: apiKey.trim(), provider: apiConfig.providerName };
  writeAuthStore(paths.authProfiles, authStore);

  console.log(chalk.green(`\n✅ 已激活 ${typeLabel}`));
  console.log(chalk.cyan(`   节点: ${provider.baseUrl}`));
  console.log(chalk.gray(`   模型: ${modelConfig.name}`));
  console.log(chalk.gray(`   API Key: 已设置`));
}

// ============ 测试连接 ============
async function testConnection(paths, args = {}) {
  console.log(chalk.cyan('🧪 测试 OpenClaw Gateway 连接\n'));

  const config = readConfig(paths.openclawConfig);

  if (!config) {
    console.log(chalk.yellow('配置文件不存在，请先选择节点'));
    return;
  }

  // 检查当前激活的是哪个
  const primary = config.agents?.defaults?.model?.primary || '';
  if (!primary.includes('/')) {
    console.log(chalk.yellow('⚠️ 请先设置主模型'));
    return;
  }

  const providerName = primary.split('/')[0];
  const provider = config.models?.providers?.[providerName];
  if (!provider) {
    console.log(chalk.yellow(`⚠️ 主模型对应的中转站不存在: ${providerName}`));
    return;
  }

  const apiType = provider.api || '';
  const typeLabel = apiType.startsWith('anthropic')
    ? 'Claude'
    : (apiType.startsWith('openai') ? 'Codex' : '模型');

  if (!provider.apiKey) {
    console.log(chalk.yellow(`⚠️ ${typeLabel} API Key 未设置`));
    return;
  }

  // 获取 Gateway 配置
  const gatewayPort = config.gateway?.port || 18789;

  console.log(chalk.gray(`当前激活: ${typeLabel}`));
  console.log(chalk.gray(`中转节点: ${provider.baseUrl}`));
  console.log(chalk.gray(`模型: ${primary}`));
  console.log(chalk.gray(`Gateway: http://localhost:${gatewayPort}\n`));

  // 获取 Gateway token
  const gatewayToken = config.gateway?.auth?.token;
  if (!gatewayToken) {
    console.log(chalk.yellow('⚠️ Gateway token 未配置'));
    return;
  }

  const allowAutoDaemon = !(args['no-daemon'] || args.noDaemon);

  // 步骤1: 先重启 Gateway 使配置生效
  console.log(chalk.cyan('步骤 1/2: 重启 Gateway 使配置生效...'));
  await restartGateway();

  // 等待 Gateway 启动
  const gwSpinner = ora({ text: '等待 Gateway 启动...', spinner: 'dots' }).start();
  await new Promise(resolve => setTimeout(resolve, 2000));

  let gatewayRunning = await waitForGateway(gatewayPort);
  if (!gatewayRunning) {
    gwSpinner.text = '尝试自动启动 Gateway...';
    const autoResult = await tryAutoStartGateway(gatewayPort, allowAutoDaemon);
    gatewayRunning = autoResult.started;
  }

  if (!gatewayRunning) {
    gwSpinner.fail('Gateway 未运行');
    console.log(chalk.gray('   请在新的终端执行: openclaw gateway'));
    console.log(chalk.gray('   或: clawdbot gateway'));
    console.log(chalk.gray('   或: moltbot gateway'));
    return;
  }

  gwSpinner.succeed('Gateway 已启动');

  // 步骤2: 通过 Gateway 端点测试（优先使用 CLI agent）
  console.log(chalk.cyan(`\n步骤 2/2: 测试 Gateway API 端点...`));

  try {
    const cliResult = await testGatewayViaAgent(primary);
    let cliPassed = false;

    if (cliResult.usedCli) {
      if (cliResult.success) {
        cliPassed = true;
        console.log(chalk.green(`\n✅ CLI 对话测试成功`));
        if (cliResult.provider && cliResult.model) {
          console.log(chalk.cyan(`   Provider: ${cliResult.provider}`));
          console.log(chalk.cyan(`   Model: ${cliResult.model}`));
        }
        if (cliResult.message) {
          const reply = sanitizeModelReply(cliResult.message, {
            provider: cliResult.provider,
            model: cliResult.model,
            modelKey: primary
          });
          console.log(chalk.yellow(`   模型回复: ${reply}`));
        }
        console.log(chalk.gray('   将继续验证 Web 鉴权端点（避免“CLI 正常但网页 401”）...'));
      }

      if (!cliResult.success) {
        console.log(chalk.red(`\n❌ Gateway CLI 测试失败`));
        console.log(chalk.red(`   错误: ${cliResult.error || '未知错误'}`));
        console.log(chalk.gray(`   将尝试使用 HTTP 端点测试...`));
      }
    }

    console.log(chalk.gray(`   端点: http://localhost:${gatewayPort}/v1/responses`));
    const startTime = Date.now();
    let result = await testGatewayApi(gatewayPort, gatewayToken, primary);
    const latency = Date.now() - startTime;

    // /v1/responses 返回 405 时，回退测试 /v1/chat/completions
    if (!result.success && result.reachable && result.status === 405) {
      console.log(chalk.gray('   /v1/responses 不支持，回退测试 /v1/chat/completions...'));
      result = await testGatewayApi(gatewayPort, gatewayToken, primary, '/v1/chat/completions');
    }

    // CLI 对话已成功 + Gateway 可达（405）= Dashboard 通过 WebSocket 工作，视为通过
    if (!result.success && cliPassed && result.reachable && result.status === 405) {
      console.log(chalk.green(`\n✅ Gateway 测试通过`));
      console.log(chalk.cyan(`   CLI 对话正常，Gateway 可达`));
      console.log(chalk.gray(`   注: Gateway Dashboard 通过 WebSocket 通信，REST 端点返回 405 属正常现象`));
    } else if (result.success) {
      console.log(chalk.green(`\n✅ Gateway 测试成功！Web Dashboard 可正常使用`));
      console.log(chalk.cyan(`   响应时间: ${latency}ms`));
      const reply = sanitizeModelReply(result.message, {
        provider: providerName,
        model: primary.includes('/') ? primary.split('/')[1] : '',
        modelKey: primary
      });
      console.log(chalk.yellow(`   模型回复: ${reply}`));
    } else {
      if (result.reachable) {
        console.log(chalk.yellow(`\n⚠ Gateway HTTP 可达，但接口返回限制`));
      } else {
        console.log(chalk.red(`\n❌ Gateway API 连接失败`));
      }
      console.log(chalk.red(`   错误: ${result.error}`));

      if (cliPassed && /\b401\b/.test(String(result.error || ''))) {
        console.log(chalk.yellow(`\n⚠️ 已定位：CLI 可对话，但 Web 鉴权失败（401）`));
        console.log(chalk.yellow(`   这通常会导致 Dashboard 网页对话返回 401。`));
        console.log(chalk.gray(`\n   建议操作：`));
        console.log(chalk.gray(`   1) 复制最新地址并重新打开浏览器（不要用旧书签）`));
        console.log(chalk.cyan(`      http://127.0.0.1:${gatewayPort}/?token=${gatewayToken}`));
        console.log(chalk.gray(`   2) 执行 Gateway 重启：openclaw gateway restart / clawdbot gateway restart`));
        console.log(chalk.gray(`   3) 若仍 401，检查是否存在多个配置目录（.openclaw 与 .clawdbot）`));
      }

      if (cliPassed && /\b405\b/.test(String(result.error || ''))) {
        console.log(chalk.yellow(`\n⚠️ 已定位：Gateway 可达（HTTP 405），Web API 端点不支持当前请求方法`));
        console.log(chalk.gray(`   CLI 对话正常，Web Dashboard 应可正常使用。`));
        console.log(chalk.gray(`   如遇问题，尝试更新 Gateway: npm install -g openclaw@latest && openclaw gateway restart`));
      }

      console.log(chalk.gray(`\n   提示: 如果 Gateway 未运行，请执行: openclaw gateway / clawdbot gateway / moltbot gateway`));
    }
  } catch (error) {
    console.log(chalk.red(`❌ 测试失败: ${error.message}`));
  }
}

// ============ 重启 Gateway ============
async function restartGateway() {
  console.log(chalk.cyan('\n🔄 正在重启 OpenClaw Gateway...'));

  const { cliBinary: resolved, nodeMajor } = getCliMeta();
  const nodeInfo = findCompatibleNode(nodeMajor);
  const env = { ...process.env, PATH: extendPathEnv(nodeInfo ? nodeInfo.path : null) };
  const useNode = resolved && nodeInfo && isNodeShebang(resolved);

  // 尝试多种命令
  const commands = resolved
    ? [
        useNode ? `"${nodeInfo.path}" "${resolved}" gateway restart` : `"${resolved}" gateway restart`
      ]
    : [
        'openclaw gateway restart',
        'clawdbot gateway restart',
        'moltbot gateway restart',
        'npx openclaw gateway restart',
        'npx clawdbot gateway restart',
        'npx moltbot gateway restart'
      ];

  return new Promise((resolve) => {
    let tried = 0;

    const tryNext = () => {
      if (tried >= commands.length) {
        console.log(chalk.red(`❌ 重启失败: 找不到 openclaw/clawdbot/moltbot 命令`));
        console.log(chalk.gray(`   请手动运行: openclaw gateway restart`));
        console.log(chalk.gray(`   或: clawdbot gateway restart`));
        console.log(chalk.gray(`   或: moltbot gateway restart`));
        // 诊断信息
        console.log(chalk.gray(`\n   [诊断] resolveCliBinary = ${resolved || 'null'}`));
        const npmPrefix = safeExec('npm prefix -g');
        if (npmPrefix.ok) console.log(chalk.gray(`   [诊断] npm prefix -g = ${npmPrefix.output}`));
        for (const name of ['openclaw', 'clawdbot', 'moltbot']) {
          const which = safeExec(process.platform === 'win32' ? `where ${name} 2>nul` : `/bin/zsh -lc "command -v ${name}" 2>/dev/null || /bin/bash -lc "command -v ${name}" 2>/dev/null`);
          if (which.ok && which.output) console.log(chalk.gray(`   [诊断] ${name} -> ${which.output.split('\n')[0].trim()}`));
        }
        console.log(chalk.gray(`   [诊断] 等待 Gateway 启动...`));
        resolve();
        return;
      }

      const cmd = commands[tried];
      tried++;

      exec(cmd, { timeout: 30000, env }, (error) => {
        if (error) {
          tryNext();
        } else {
          console.log(chalk.green(`✅ Gateway 已重启`));
          console.log(chalk.gray(`   现在可以在 Web/Telegram/Discord 等渠道测试对话了`));
          resolve();
        }
      });
    };

    tryNext();
  });
}

// Gateway API 测试 - 通过本地 Gateway 端口测试
function testGatewayApi(port, token, model, endpoint = '/v1/responses') {
  return new Promise((resolve) => {
    const isChatCompletions = endpoint.includes('chat/completions');
    const postData = isChatCompletions
      ? JSON.stringify({
          model: model,
          messages: [{ role: 'user', content: '你是什么模型？' }]
        })
      : JSON.stringify({
          model: model,
          input: '你是什么模型？'
        });

    const options = {
      hostname: '127.0.0.1',
      port: port,
      path: endpoint,
      method: 'POST',
      timeout: 60000,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        'Content-Length': Buffer.byteLength(postData)
      }
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        const status = Number(res.statusCode || 0);
        const gatewayReachable = status === 401 || status === 403 || status === 404 || status === 405;

        if (gatewayReachable) {
          resolve({
            success: false,
            reachable: true,
            status,
            error: `HTTP ${status}: ${data.substring(0, 300)}`
          });
          return;
        }

        try {
          const json = JSON.parse(data);
          // OpenResponses 格式响应
          const outputText = json.output?.[0]?.content?.[0]?.text;
          // Chat Completions 格式响应
          const chatText = json.choices?.[0]?.message?.content;
          const message = outputText || chatText;
          if (message) {
            resolve({ success: true, message });
          } else if (json.error) {
            resolve({ success: false, error: json.error.message || JSON.stringify(json.error) });
          } else {
            resolve({ success: false, error: `HTTP ${res.statusCode}: ${data.substring(0, 300)}` });
          }
        } catch {
          resolve({ success: false, error: `HTTP ${res.statusCode}: ${data.substring(0, 300)}` });
        }
      });
    });

    req.on('timeout', () => {
      req.destroy();
      resolve({ success: false, error: '请求超时 (60s)' });
    });

    req.on('error', (e) => {
      if (e.code === 'ECONNREFUSED') {
        resolve({ success: false, error: 'Gateway 未运行，请先启动: openclaw gateway / clawdbot gateway / moltbot gateway' });
      } else {
        resolve({ success: false, error: e.message });
      }
    });

    req.write(postData);
    req.end();
  });
}

function testGatewayViaAgent(model) {
  return new Promise((resolve) => {
    const { cliBinary, nodeMajor } = getCliMeta();
    if (!cliBinary) {
      resolve({ success: false, usedCli: false, error: '未找到 openclaw/clawdbot/moltbot 命令' });
      return;
    }

    const nodeInfo = findCompatibleNode(nodeMajor);
    // 清除可能覆盖配置文件 apiKey 的环境变量，避免 Gateway 使用错误的 key
    const env = { ...process.env, PATH: extendPathEnv(nodeInfo ? nodeInfo.path : null), NODE_NO_WARNINGS: '1' };
    delete env.CLAUDE_API_KEY;
    delete env.OPENCLAW_CLAUDE_KEY;
    delete env.OPENCLAW_API_KEY;
    delete env.OPENAI_API_KEY;
    delete env.OPENCLAW_CODEX_KEY;
    const useNode = nodeInfo && isNodeShebang(cliBinary);
    const cmd = useNode
      ? `"${nodeInfo.path}" "${cliBinary}" agent --session-id openclawapi-test --message "请回复你的模型名称" --json --timeout 120`
      : `"${cliBinary}" agent --session-id openclawapi-test --message "请回复你的模型名称" --json --timeout 120`;

    exec(cmd, { timeout: 120000, env }, (error, stdout, stderr) => {
      // 过滤 stderr 中的 Node.js DeprecationWarning 噪音
      const cleanStderr = (stderr || '').replace(/\(node:\d+\) \[DEP\d+\] DeprecationWarning:.*(\n.*trace-deprecation.*)?/g, '').trim();

      if (error) {
        // 即使 exec 报错，stdout 中可能仍有有效 JSON（如 CLI 输出了结果但 exit code 非零）
        const fallbackOutput = (stdout || '').trim();
        const fbJsonStart = fallbackOutput.indexOf('{');
        const fbJsonEnd = fallbackOutput.lastIndexOf('}');
        if (fbJsonStart !== -1 && fbJsonEnd > fbJsonStart) {
          // stdout 有 JSON，走正常解析流程而非直接报错
          stdout = fallbackOutput;
        } else {
          resolve({
            success: false,
            usedCli: true,
            error: (cleanStderr || fallbackOutput || error.message || 'CLI 执行失败').trim()
          });
          return;
        }
      }

      const output = (stdout || '').trim();
      const jsonStart = output.indexOf('{');
      const jsonEnd = output.lastIndexOf('}');
      if (jsonStart === -1 || jsonEnd === -1 || jsonEnd <= jsonStart) {
        resolve({
          success: false,
          usedCli: true,
          error: (stdout || stderr || 'CLI 输出无法解析').trim()
        });
        return;
      }

      try {
        const parsed = JSON.parse(output.slice(jsonStart, jsonEnd + 1));
        // Support both top-level format (current) and legacy .result wrapper
        const envelope = parsed?.result ?? parsed;
        const message = envelope?.payloads?.[0]?.text || '';
        const provider = envelope?.meta?.agentMeta?.provider || '';
        const modelId = envelope?.meta?.agentMeta?.model || '';

        if (!provider || !modelId) {
          resolve({
            success: false,
            usedCli: true,
            error: message || 'CLI 返回缺少 provider/model'
          });
          return;
        }

        // 检查回复内容是否实际上是错误信息
        const msgLower = (message || '').toLowerCase();
        const isErrorResponse = (
          (msgLower.includes('401') && (msgLower.includes('invalid api key') || msgLower.includes('unauthorized'))) ||
          (msgLower.includes('403') && (msgLower.includes('forbidden') || msgLower.includes('access denied'))) ||
          /^http\s+\d{3}:/i.test(message.trim())
        );

        if (isErrorResponse) {
          resolve({
            success: false,
            usedCli: true,
            provider,
            model: modelId,
            error: message.substring(0, 200)
          });
          return;
        }

        resolve({
          success: true,
          usedCli: true,
          provider,
          model: modelId,
          message
        });
      } catch (parseError) {
        resolve({
          success: false,
          usedCli: true,
          error: (stdout || stderr || String(parseError)).trim()
        });
      }
    });
  });
}

function escapeRegExp(text) {
  return String(text).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function sanitizeModelReply(message, options = {}) {
  let text = String(message || '').trim();
  const tokens = [options.provider, options.model, options.modelKey]
    .filter(Boolean)
    .map(escapeRegExp);

  const tailPattern = tokens.length
    ? new RegExp(
        `[（(][^）)]*(?:${tokens.join('|')}|[A-Za-z0-9_.-]+\\/[A-Za-z0-9_.-]+)[^）)]*[）)]\\s*$`,
        'i'
      )
    : /[（(][^）)]*[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+[^）)]*[）)]\s*$/i;

  text = text
    .replace(/（\s*通过[^）]*别名配置\s*）/g, '')
    .replace(/\(\s*通过[^)]*别名配置\s*\)/g, '')
    .replace(tailPattern, '')
    .trim();

  return text;
}

// Claude API 测试 (直接测试中转，备用)
function testClaudeApi(baseUrl, apiKey, model) {
  return new Promise((resolve) => {
    const trimmed = trimClaudeMessagesSuffix(baseUrl);
    const normalized = trimmed.endsWith('/claude') ? `${trimmed}/v1/messages` : trimmed;
    const urlObj = new URL(normalized);
    const protocol = urlObj.protocol === 'https:' ? https : http;

    const postData = JSON.stringify({
      model: model || 'claude-sonnet-4-5',
      max_tokens: 150,
      messages: [{ role: 'user', content: '你是哪个模型？请用一句话回答你的模型名称和版本。' }]
    });

    const options = {
      hostname: urlObj.hostname,
      port: urlObj.port || (urlObj.protocol === 'https:' ? 443 : 80),
      path: urlObj.pathname,
      method: 'POST',
      timeout: 30000,
      rejectUnauthorized: false,
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
        'Content-Length': Buffer.byteLength(postData)
      }
    };

    const req = protocol.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          if (json.content && json.content[0]) {
            resolve({ success: true, message: json.content[0].text?.substring(0, 100) || 'OK' });
          } else if (json.error) {
            resolve({ success: false, error: json.error.message || JSON.stringify(json.error) });
          } else {
            resolve({ success: false, error: `HTTP ${res.statusCode}: ${data.substring(0, 200)}` });
          }
        } catch {
          resolve({ success: false, error: `HTTP ${res.statusCode}: ${data.substring(0, 200)}` });
        }
      });
    });

    req.on('timeout', () => {
      req.destroy();
      resolve({ success: false, error: '请求超时 (30s)' });
    });

    req.on('error', (e) => {
      resolve({ success: false, error: e.message });
    });

    req.write(postData);
    req.end();
  });
}

// Codex API 测试
function testCodexApi(baseUrl, apiKey, model) {
  return new Promise((resolve) => {
    const urlObj = new URL(baseUrl);
    const protocol = urlObj.protocol === 'https:' ? https : http;

    const postData = JSON.stringify({
      model: model || 'gpt-5.2',
      input: '你是哪个模型？请用一句话回答你的模型名称和版本。'
    });

    const options = {
      hostname: urlObj.hostname,
      port: urlObj.port || (urlObj.protocol === 'https:' ? 443 : 80),
      path: urlObj.pathname,
      method: 'POST',
      timeout: 30000,
      rejectUnauthorized: false,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
        'Content-Length': Buffer.byteLength(postData)
      }
    };

    const req = protocol.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          if (json.output && json.output[0]) {
            const text = json.output[0].content?.[0]?.text || json.output[0].text || 'OK';
            resolve({ success: true, message: text.substring(0, 100) });
          } else if (json.error) {
            resolve({ success: false, error: json.error.message || JSON.stringify(json.error) });
          } else {
            resolve({ success: false, error: `HTTP ${res.statusCode}: ${data.substring(0, 200)}` });
          }
        } catch {
          resolve({ success: false, error: `HTTP ${res.statusCode}: ${data.substring(0, 200)}` });
        }
      });
    });

    req.on('timeout', () => {
      req.destroy();
      resolve({ success: false, error: '请求超时 (30s)' });
    });

    req.on('error', (e) => {
      resolve({ success: false, error: e.message });
    });

    req.write(postData);
    req.end();
  });
}

// ============ 查看配置 ============
async function viewConfig(paths) {
  console.log(chalk.cyan('📋 当前配置\n'));

  const config = readConfig(paths.openclawConfig);

  if (!config) {
    console.log(chalk.yellow('配置文件不存在，请先选择节点'));
    return;
  }

  // 当前激活
  const primary = config.agents?.defaults?.model?.primary || '未设置';
  const isClaudeActive = primary.startsWith('claude-yunyi') || primary.startsWith('yunyi-claude');
  const isCodexActive = primary.startsWith('yunyi/') || primary.startsWith('yunyi-codex') || primary.startsWith('codex-yunyi');

  console.log(chalk.yellow('当前激活:'));
  if (isClaudeActive) {
    console.log(chalk.blue(`  🔵 Claude: ${primary}`));
  } else if (isCodexActive) {
    console.log(chalk.green(`  🟢 Codex: ${primary}`));
  } else {
    console.log(`  ${primary}`);
  }
  console.log('');

  // 中转站列表
  console.log(chalk.yellow('中转站配置:'));
  const providers = config.models?.providers || {};
  const providerEntries = Object.entries(providers);
  if (providerEntries.length === 0) {
    console.log(chalk.gray('  未配置'));
  } else {
    for (const [name, provider] of providerEntries) {
      const hasKey = provider.apiKey ? chalk.green('✓') : chalk.red('✗');
      const model = provider.models?.[0]?.name || 'N/A';
      const isPrimary = primary.startsWith(`${name}/`);
      console.log(`  ${isPrimary ? '⭐ ' : ''}${name}`);
      console.log(`    URL: ${provider.baseUrl}`);
      console.log(`    模型: ${model}`);
      console.log(`    API Key: ${hasKey}`);
    }
  }
  console.log('');

  // 备份状态
  const backupPath = path.join(paths.configDir, BACKUP_FILENAME);
  console.log(chalk.yellow('备份状态:'));
  console.log(`  ${fs.existsSync(backupPath) ? chalk.green('✓ 已备份') : chalk.gray('未备份')}`);
}

// ============ 恢复默认配置 ============
async function restore(paths) {
  const backupPath = path.join(paths.configDir, BACKUP_FILENAME);

  if (!fs.existsSync(backupPath)) {
    console.log(chalk.yellow('⚠️ 没有找到备份文件'));
    return;
  }

  const { confirm } = await inquirer.prompt([{
    type: 'confirm',
    name: 'confirm',
    message: '确定要恢复默认配置吗？当前配置将被覆盖。',
    default: false
  }]);

  if (!confirm) {
    console.log(chalk.gray('已取消'));
    return;
  }

  if (restoreDefaultConfig(paths.openclawConfig, paths.configDir)) {
    console.log(chalk.green('\n✅ 已恢复默认配置'));
  } else {
    console.log(chalk.red('\n❌ 恢复失败'));
  }
}

// 启动
main().catch(error => {
  exitWithError('CONFIG_FAILED', error.message, [
    '检查网络连接',
    '确保 OpenClaw 已正确安装',
    '查看详细错误信息并重试',
  ]);
});
