import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000'
  return {
    plugins: [vue()],
    base: '/',
    server: {
      port: 5173,
      proxy: {
        '/api': { target: proxyTarget, changeOrigin: true },
      },
    },
    build: { outDir: 'dist', chunkSizeWarningLimit: 2000 },
  }
})
