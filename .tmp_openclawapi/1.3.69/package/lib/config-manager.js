const fs = require('fs-extra');
const JSON5 = require('json5');
const path = require('path');
const os = require('os');

// 默认配置模板
const DEFAULT_CONFIG = {
  models: {
    providers: {}
  },
  auth: {
    profiles: {}
  },
  agents: {
    defaults: {
      model: {
        primary: '',
        fallbacks: []
      },
      models: {},
      maxConcurrent: 4,
      subagents: {
        maxConcurrent: 8
      },
      workspace: ''
    }
  }
};

// 获取跨平台配置目录
function getConfigDir() {
  const homeDir = os.homedir();
  // Windows: %USERPROFILE%\.clawdbot
  // macOS/Linux: ~/.clawdbot
  return path.join(homeDir, '.clawdbot');
}

// 获取跨平台默认工作区路径
function getDefaultWorkspace() {
  const homeDir = os.homedir();
  const openclawStateDir = process.env.OPENCLAW_STATE_DIR || path.join(homeDir, '.openclaw');
  const clawdbotStateDir = process.env.CLAWDBOT_STATE_DIR || path.join(homeDir, '.clawdbot');
  const profile = process.env.OPENCLAW_PROFILE;
  const workspaceSuffix = profile && profile !== 'default' ? `-${profile}` : '';

  if (process.env.OPENCLAW_STATE_DIR || process.env.OPENCLAW_CONFIG_PATH) {
    return path.join(openclawStateDir, `workspace${workspaceSuffix}`);
  }
  if (process.env.CLAWDBOT_STATE_DIR || process.env.CLAWDBOT_CONFIG_PATH) {
    return path.join(clawdbotStateDir, 'workspace');
  }
  return path.join(openclawStateDir, `workspace${workspaceSuffix}`);
}

// 验证 URL 格式
function isValidUrl(urlString) {
  try {
    const url = new URL(urlString);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

// 验证数值范围
function isValidNumber(value, min, max) {
  const num = Number(value);
  return !isNaN(num) && num >= min && num <= max;
}

class ConfigManager {
  constructor(configPaths) {
    this.openclawConfigPath = configPaths.openclawConfig;
    this.authProfilesPath = configPaths.authProfiles;
    this.configDir = path.dirname(configPaths.openclawConfig);
  }

  // 检查配置文件是否存在
  async checkConfigExists() {
    return {
      openclaw: await fs.pathExists(this.openclawConfigPath),
      auth: await fs.pathExists(this.authProfilesPath)
    };
  }

  // 初始化配置文件（如果不存在则创建）
  async initializeConfig() {
    try {
      // 确保配置目录存在
      await fs.ensureDir(this.configDir);

      // 检查并创建 openclaw.json
      if (!await fs.pathExists(this.openclawConfigPath)) {
        const defaultConfig = JSON.parse(JSON.stringify(DEFAULT_CONFIG));
        defaultConfig.agents.defaults.workspace = getDefaultWorkspace();
        await fs.writeJson(this.openclawConfigPath, defaultConfig, { spaces: 2 });
      }

      // 确保 auth-profiles.json 目录存在
      const authDir = path.dirname(this.authProfilesPath);
      await fs.ensureDir(authDir);

      if (!await fs.pathExists(this.authProfilesPath)) {
        await fs.writeJson(this.authProfilesPath, {}, { spaces: 2 });
      }

      return true;
    } catch (error) {
      throw new Error(`初始化配置失败: ${error.message}`);
    }
  }

  // 检查文件写入权限
  async checkWritePermission(filePath) {
    try {
      const dir = path.dirname(filePath);
      await fs.ensureDir(dir);
      // 尝试写入测试文件
      const testFile = path.join(dir, '.write-test-' + Date.now());
      await fs.writeFile(testFile, '');
      await fs.remove(testFile);
      return true;
    } catch (error) {
      return false;
    }
  }

  // 读取 openclaw.json
  async readOpenclawConfig() {
    try {
      if (!await fs.pathExists(this.openclawConfigPath)) {
        // 自动初始化配置
        await this.initializeConfig();
      }
      const raw = await fs.readFile(this.openclawConfigPath, 'utf8');
      return JSON5.parse(raw);
    } catch (error) {
      if (error.code === 'EACCES') {
        throw new Error(`没有权限读取配置文件: ${this.openclawConfigPath}`);
      }
      if (error.code === 'ENOENT') {
        throw new Error(`配置文件不存在: ${this.openclawConfigPath}`);
      }
      throw new Error(`读取配置文件失败: ${error.message}`);
    }
  }

  // 写入 openclaw.json
  async writeOpenclawConfig(config) {
    try {
      // 检查写入权限
      if (!await this.checkWritePermission(this.openclawConfigPath)) {
        throw new Error(`没有权限写入配置文件: ${this.openclawConfigPath}`);
      }
      await fs.ensureDir(path.dirname(this.openclawConfigPath));
      await fs.writeJson(this.openclawConfigPath, config, { spaces: 2 });
    } catch (error) {
      if (error.code === 'EACCES') {
        throw new Error(`没有权限写入配置文件: ${this.openclawConfigPath}`);
      }
      throw new Error(`写入配置文件失败: ${error.message}`);
    }
  }

  // 读取 auth-profiles.json
  async readAuthProfiles() {
    try {
      if (await fs.pathExists(this.authProfilesPath)) {
        return await fs.readJson(this.authProfilesPath);
      }
      return {};
    } catch (error) {
      if (error.code === 'EACCES') {
        throw new Error(`没有权限读取认证文件: ${this.authProfilesPath}`);
      }
      throw new Error(`读取认证文件失败: ${error.message}`);
    }
  }

  // 写入 auth-profiles.json
  async writeAuthProfiles(profiles) {
    try {
      const authDir = path.dirname(this.authProfilesPath);
      if (!await this.checkWritePermission(this.authProfilesPath)) {
        throw new Error(`没有权限写入认证文件: ${this.authProfilesPath}`);
      }
      await fs.ensureDir(authDir);
      await fs.writeJson(this.authProfilesPath, profiles, { spaces: 2 });
    } catch (error) {
      if (error.code === 'EACCES') {
        throw new Error(`没有权限写入认证文件: ${this.authProfilesPath}`);
      }
      throw new Error(`写入认证文件失败: ${error.message}`);
    }
  }

  // 添加中转站
  async addRelay(relayConfig) {
    // 验证输入
    if (!relayConfig.name || relayConfig.name.trim() === '') {
      throw new Error('中转站名称不能为空');
    }
    if (!relayConfig.baseUrl || !isValidUrl(relayConfig.baseUrl)) {
      throw new Error('请输入有效的 URL (http:// 或 https://)');
    }
    const hasModelsArray = Array.isArray(relayConfig.models);
    const primaryModelId = relayConfig.model?.id || relayConfig.models?.[0]?.id;
    if (!primaryModelId) {
      throw new Error('模型 ID 不能为空');
    }
    if (!hasModelsArray) {
      if (!relayConfig.model || !relayConfig.model.id) {
        throw new Error('模型配置不能为空');
      }
      if (!isValidNumber(relayConfig.model.contextWindow, 1000, 10000000)) {
        throw new Error('上下文窗口大小必须在 1000 到 10000000 之间');
      }
      if (!isValidNumber(relayConfig.model.maxTokens, 100, 1000000)) {
        throw new Error('最大输出 tokens 必须在 100 到 1000000 之间');
      }
    }

    const config = await this.readOpenclawConfig();

    const providerName = relayConfig.name.trim();
    const profileKey = `${providerName}:default`;

    // 检查是否已存在同名中转站
    if (config.models?.providers?.[providerName]) {
      throw new Error(`中转站 "${providerName}" 已存在，请使用其他名称或编辑现有中转站`);
    }

    // 添加到 models.providers
    if (!config.models) config.models = {};
    if (!config.models.providers) config.models.providers = {};
    if (!config.models.mode && relayConfig.modelsMode) {
      config.models.mode = relayConfig.modelsMode;
    }

    config.models.providers[providerName] = {
      baseUrl: relayConfig.baseUrl.trim(),
      auth: relayConfig.auth || 'api-key',
      api: relayConfig.api || 'openai-completions',
      headers: relayConfig.headers || {},
      authHeader: relayConfig.authHeader === true,
      models: Array.isArray(relayConfig.models)
        ? relayConfig.models
        : [
            {
              id: relayConfig.model.id.trim(),
              name: relayConfig.model.name || relayConfig.model.id,
              reasoning: !!relayConfig.model.reasoning,
              input: relayConfig.model.input || ['text'],
              cost: relayConfig.model.cost || {
                input: 0,
                output: 0,
                cacheRead: 0,
                cacheWrite: 0
              },
              contextWindow: Number(relayConfig.model.contextWindow),
              maxTokens: Number(relayConfig.model.maxTokens)
            }
          ]
    };

    // 添加到 auth.profiles
    if (!config.auth) config.auth = {};
    if (!config.auth.profiles) config.auth.profiles = {};

    config.auth.profiles[profileKey] = {
      provider: providerName,
      mode: 'api_key'
    };

    // 注册到 agents.defaults.models，便于切换与备用
    if (!config.agents) config.agents = {};
    if (!config.agents.defaults) config.agents.defaults = {};
    if (!config.agents.defaults.models) config.agents.defaults.models = {};
    const modelKey = `${providerName}/${primaryModelId}`;
    if (!config.agents.defaults.models[modelKey]) {
      config.agents.defaults.models[modelKey] = {
        alias: providerName
      };
    }

    await this.writeOpenclawConfig(config);
  }

  // 列出所有中转站
  async listRelays() {
    const config = await this.readOpenclawConfig();
    const relays = [];
    const primary = config.agents?.defaults?.model?.primary || '';
    const registeredModels = config.agents?.defaults?.models || {};

    if (config.models && config.models.providers) {
      for (const [name, provider] of Object.entries(config.models.providers)) {
        let modelId = '';
        let modelName = 'N/A';
        let contextWindow = undefined;
        let maxTokens = undefined;

        if (provider.models && provider.models.length > 0) {
          const model = provider.models[0];
          modelId = model.id;
          modelName = model.name || model.id;
          contextWindow = model.contextWindow;
          maxTokens = model.maxTokens;
        } else if (primary.startsWith(`${name}/`)) {
          modelId = primary.split('/')[1] || '';
          modelName = modelId || 'N/A';
        } else {
          const modelKey = Object.keys(registeredModels).find(key => key.startsWith(`${name}/`));
          if (modelKey) {
            modelId = modelKey.split('/')[1] || '';
            modelName = modelId || 'N/A';
          }
        }

        relays.push({
          name,
          baseUrl: provider.baseUrl,
          modelId,
          modelName,
          contextWindow,
          maxTokens
        });
      }
    }

    return relays;
  }

  // 更新中转站
  async updateRelay(relayName, updates) {
    const config = await this.readOpenclawConfig();

    if (!config.models?.providers?.[relayName]) {
      throw new Error(`中转站 "${relayName}" 不存在`);
    }

    // 验证输入
    if (updates.baseUrl && !isValidUrl(updates.baseUrl)) {
      throw new Error('请输入有效的 URL (http:// 或 https://)');
    }
    if (updates.contextWindow !== undefined && !isValidNumber(updates.contextWindow, 1000, 10000000)) {
      throw new Error('上下文窗口大小必须在 1000 到 10000000 之间');
    }
    if (updates.maxTokens !== undefined && !isValidNumber(updates.maxTokens, 100, 1000000)) {
      throw new Error('最大输出 tokens 必须在 100 到 1000000 之间');
    }

    const provider = config.models.providers[relayName];

    if (updates.baseUrl) {
      provider.baseUrl = updates.baseUrl.trim();
    }
    if (updates.api) {
      provider.api = updates.api;
    }
    if (updates.auth) {
      provider.auth = updates.auth;
    }
    if (updates.headers && typeof updates.headers === 'object') {
      provider.headers = updates.headers;
    }
    if (updates.authHeader !== undefined) {
      provider.authHeader = !!updates.authHeader;
    }
    if (updates.apiKey) {
      provider.apiKey = updates.apiKey.trim();
    }

    if (provider.models && provider.models.length > 0) {
      if (updates.contextWindow !== undefined) {
        provider.models[0].contextWindow = Number(updates.contextWindow);
      }
      if (updates.maxTokens !== undefined) {
        provider.models[0].maxTokens = Number(updates.maxTokens);
      }
    }

    await this.writeOpenclawConfig(config);
  }

  // 删除中转站
  async deleteRelay(relayName) {
    const config = await this.readOpenclawConfig();

    // 删除 provider
    if (config.models?.providers?.[relayName]) {
      delete config.models.providers[relayName];
    }

    // 删除 auth profile
    const profileKey = `${relayName}:default`;
    if (config.auth?.profiles?.[profileKey]) {
      delete config.auth.profiles[profileKey];
    }

    // 从 agents.defaults.models 中删除
    if (config.agents?.defaults?.models) {
      for (const key of Object.keys(config.agents.defaults.models)) {
        if (key.startsWith(`${relayName}/`)) {
          delete config.agents.defaults.models[key];
        }
      }
    }

    // 如果是主模型，需要切换到其他模型
    if (config.agents?.defaults?.model?.primary?.startsWith(`${relayName}/`)) {
      const remainingRelays = await this.listRelays();
      if (remainingRelays.length > 0) {
        const firstRelay = remainingRelays[0];
        config.agents.defaults.model.primary = `${firstRelay.name}/${firstRelay.modelId}`;
      }
    }

    // 从 fallbacks 中删除
    if (config.agents?.defaults?.model?.fallbacks) {
      config.agents.defaults.model.fallbacks = config.agents.defaults.model.fallbacks.filter(
        f => !f.startsWith(`${relayName}/`)
      );
    }

    await this.writeOpenclawConfig(config);

    // 删除 API Key
    const authProfiles = await this.readAuthProfiles();
    if (authProfiles[profileKey]) {
      delete authProfiles[profileKey];
      await this.writeAuthProfiles(authProfiles);
    }
  }

  // 获取主模型
  async getPrimaryModel() {
    const config = await this.readOpenclawConfig();
    const primary = config.agents?.defaults?.model?.primary || '';
    const [provider, modelId] = primary.split('/');
    return { provider, modelId, full: primary };
  }

  // 设置主模型
  async setPrimaryModel(relayName, modelIdOverride) {
    const config = await this.readOpenclawConfig();
    let modelId = modelIdOverride;
    if (!modelId) {
      const relays = await this.listRelays();
      const relay = relays.find(r => r.name === relayName);

      if (!relay) {
        throw new Error(`中转站 "${relayName}" 不存在`);
      }
      modelId = relay.modelId;
    }
    if (!modelId) {
      throw new Error(`中转站 "${relayName}" 未配置模型 ID`);
    }

    if (!config.agents) config.agents = {};
    if (!config.agents.defaults) config.agents.defaults = {};
    if (!config.agents.defaults.model) config.agents.defaults.model = {};

    config.agents.defaults.model.primary = `${relayName}/${modelId}`;

    // 确保在 models 中注册
    if (!config.agents.defaults.models) config.agents.defaults.models = {};
    const modelKey = `${relayName}/${modelId}`;
    if (!config.agents.defaults.models[modelKey]) {
      config.agents.defaults.models[modelKey] = {
        alias: relayName
      };
    }

    await this.writeOpenclawConfig(config);
  }

  // 获取备用模型
  async getFallbackModels() {
    const config = await this.readOpenclawConfig();
    return config.agents?.defaults?.model?.fallbacks || [];
  }

  // 设置备用模型
  async setFallbackModels(models) {
    const config = await this.readOpenclawConfig();

    if (!config.agents) config.agents = {};
    if (!config.agents.defaults) config.agents.defaults = {};
    if (!config.agents.defaults.model) config.agents.defaults.model = {};

    config.agents.defaults.model.fallbacks = models;

    // 确保所有模型都在 models 中注册
    if (!config.agents.defaults.models) config.agents.defaults.models = {};
    for (const modelKey of models) {
      if (!config.agents.defaults.models[modelKey]) {
        const [provider] = modelKey.split('/');
        config.agents.defaults.models[modelKey] = {
          alias: provider
        };
      }
    }

    await this.writeOpenclawConfig(config);
  }

  // 设置 API Key
  async setApiKey(relayName, apiKey) {
    if (!apiKey || apiKey.trim() === '') {
      throw new Error('API Key 不能为空');
    }

    const config = await this.readOpenclawConfig();
    if (config.models?.providers?.[relayName]) {
      config.models.providers[relayName].apiKey = apiKey.trim();
      await this.writeOpenclawConfig(config);
    }

    const authProfiles = await this.readAuthProfiles();
    const profileKey = `${relayName}:default`;

    // 保留现有的 token 设置
    const existing = authProfiles[profileKey] || {};
    authProfiles[profileKey] = {
      ...existing,
      apiKey: apiKey.trim()
    };

    await this.writeAuthProfiles(authProfiles);
  }

  // 设置 Token
  async setToken(relayName, token) {
    if (!token || token.trim() === '') {
      throw new Error('Token 不能为空');
    }

    const authProfiles = await this.readAuthProfiles();
    const profileKey = `${relayName}:default`;

    // 保留现有的 apiKey 设置
    const existing = authProfiles[profileKey] || {};
    authProfiles[profileKey] = {
      ...existing,
      token: token.trim()
    };

    await this.writeAuthProfiles(authProfiles);
  }

  // 获取 Token
  async getToken(relayName) {
    const authProfiles = await this.readAuthProfiles();
    const profileKey = `${relayName}:default`;
    return authProfiles[profileKey]?.token || null;
  }

  // 列出所有 API Keys 和 Tokens
  async listApiKeys() {
    const config = await this.readOpenclawConfig();
    const authProfiles = await this.readAuthProfiles();
    const keys = [];
    const providers = new Set();

    if (config.models?.providers) {
      Object.keys(config.models.providers).forEach(p => providers.add(p));
    }
    Object.keys(authProfiles).forEach(profile => {
      const provider = profile.split(':')[0];
      providers.add(provider);
    });

    for (const provider of providers) {
      const profileKey = `${provider}:default`;
      const providerConfig = config.models?.providers?.[provider] || {};
      const profileData = authProfiles[profileKey] || {};
      keys.push({
        provider,
        key: providerConfig.apiKey || profileData.apiKey || null,
        token: profileData.token || null
      });
    }

    return keys;
  }

  // 删除 Token
  async deleteToken(provider) {
    const authProfiles = await this.readAuthProfiles();
    const profileKey = provider.includes(':') ? provider : `${provider}:default`;

    if (authProfiles[profileKey] && authProfiles[profileKey].token) {
      delete authProfiles[profileKey].token;
      // 如果没有其他数据，删除整个 profile
      if (!authProfiles[profileKey].apiKey) {
        delete authProfiles[profileKey];
      }
      await this.writeAuthProfiles(authProfiles);
    }
  }

  // 删除 API Key
  async deleteApiKey(provider) {
    const config = await this.readOpenclawConfig();
    if (config.models?.providers?.[provider]) {
      delete config.models.providers[provider].apiKey;
      await this.writeOpenclawConfig(config);
    }

    const authProfiles = await this.readAuthProfiles();
    const profileKey = provider.includes(':') ? provider : `${provider}:default`;

    if (authProfiles[profileKey]) {
      delete authProfiles[profileKey].apiKey;
      // 如果没有其他数据，删除整个 profile
      if (!authProfiles[profileKey].token) {
        delete authProfiles[profileKey];
      }
      await this.writeAuthProfiles(authProfiles);
    }
  }

  // 获取高级设置
  async getAdvancedSettings() {
    const config = await this.readOpenclawConfig();
    return {
      maxConcurrent: config.agents?.defaults?.maxConcurrent || 4,
      subagentMaxConcurrent: config.agents?.defaults?.subagents?.maxConcurrent || 8,
      workspace: config.agents?.defaults?.workspace || getDefaultWorkspace(),
      compactionMode: config.agents?.defaults?.compaction?.mode || '',
      gatewayAuthMode: config.gateway?.auth?.mode || '',
      gatewayToken: config.gateway?.auth?.token || '',
      gatewayPort: config.gateway?.port,
      gatewayBind: config.gateway?.bind
    };
  }

  // 设置高级设置
  async setAdvancedSettings(settings) {
    const config = await this.readOpenclawConfig();

    // 验证输入
    if (settings.maxConcurrent !== undefined && !isValidNumber(settings.maxConcurrent, 1, 100)) {
      throw new Error('最大并发任务数必须在 1 到 100 之间');
    }
    if (settings.subagentMaxConcurrent !== undefined && !isValidNumber(settings.subagentMaxConcurrent, 1, 100)) {
      throw new Error('子代理最大并发数必须在 1 到 100 之间');
    }

    if (!config.agents) config.agents = {};
    if (!config.agents.defaults) config.agents.defaults = {};

    if (settings.maxConcurrent !== undefined) {
      config.agents.defaults.maxConcurrent = Number(settings.maxConcurrent);
    }

    if (settings.subagentMaxConcurrent !== undefined) {
      if (!config.agents.defaults.subagents) config.agents.defaults.subagents = {};
      config.agents.defaults.subagents.maxConcurrent = Number(settings.subagentMaxConcurrent);
    }

    if (settings.workspace) {
      // 规范化路径（跨平台）
      config.agents.defaults.workspace = path.normalize(settings.workspace.trim());
    }

    if (settings.compactionMode) {
      if (!config.agents.defaults.compaction) config.agents.defaults.compaction = {};
      config.agents.defaults.compaction.mode = settings.compactionMode;
    }

    if (settings.gatewayToken) {
      if (!config.gateway) config.gateway = {};
      if (!config.gateway.auth) config.gateway.auth = {};
      config.gateway.auth.mode = config.gateway.auth.mode || 'token';
      config.gateway.auth.token = settings.gatewayToken.trim();
    }

    await this.writeOpenclawConfig(config);
  }

  // 获取当前完整配置
  async getCurrentConfig() {
    const config = await this.readOpenclawConfig();
    const relays = await this.listRelays();
    const primary = await this.getPrimaryModel();
    const fallbacks = await this.getFallbackModels();
    const advanced = await this.getAdvancedSettings();

    return {
      primary: primary.full,
      fallbacks,
      relays,
      advanced
    };
  }
}

module.exports = {
  ConfigManager,
  getConfigDir,
  getDefaultWorkspace,
  isValidUrl,
  isValidNumber
};
