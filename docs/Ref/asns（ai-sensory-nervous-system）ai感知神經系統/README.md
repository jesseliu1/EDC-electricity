# ASNS 宿主“神经系统”参考工程

此目录是 `EDC electricity` 使用的宿主参考工程，默认开发端口为 `3001`。

统一部署说明见：

- `../../DEPLOYMENT.md`

## 本地运行

前置：

- Node.js 20 LTS

安装依赖：

```bash
npm install
```

开发运行：

```bash
npm run dev
```

## 构建与预览

构建：

```bash
npm run build
```

预览运行：

```bash
npm run preview -- --host 0.0.0.0 --port 3001
```

## 说明

- 当前项目不再使用 AI Studio / Gemini 的部署口径
- 当前宿主通过 Vite middleware 提供 `/host-api/edc/*` 接口，生产环境建议保留 `vite preview` 进程
- 如果只部署 `dist/` 到纯静态服务器，宿主的 EDC 测试连接与同步通道功能将不可用
