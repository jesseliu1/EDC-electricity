import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const base = env.VITE_EDC_BASE_PATH || '/edc/'
  const devPort = Number(env.VITE_EDC_DEV_PORT || '3000')
  const apiTarget = env.VITE_EDC_API_TARGET || 'http://localhost:8000'

  return {
    base,
    plugins: [vue()],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
      },
    },
    server: {
      port: devPort,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
    build: {
      sourcemap: false,
      rollupOptions: {
        output: {
          manualChunks: {
            vue: ['vue', 'vue-router', 'pinia', 'vue-i18n'],
            elementPlus: ['element-plus', '@element-plus/icons-vue'],
            echarts: ['echarts', 'vue-echarts'],
          },
        },
      },
    },
  }
})
