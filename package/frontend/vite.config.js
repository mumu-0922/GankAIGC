import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig(({ mode }) => {
  // 加载 .env 文件中的所有变量（第三个参数 '' 表示不限制 VITE_ 前缀）
  const env = loadEnv(mode, process.cwd(), '')

  const devHost = env.VITE_DEV_HOST || '0.0.0.0'
  const devPort = parseInt(env.VITE_DEV_PORT) || 5174
  const apiTarget = env.VITE_API_TARGET || 'http://localhost:9800'

  return {
    plugins: [react()],
    base: '/',
    build: {
      outDir: 'dist',
      assetsDir: 'assets',
      emptyOutDir: true,
      // 生产环境优化
      minify: 'terser',
      sourcemap: false,
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ['react', 'react-dom', 'react-router-dom'],
          },
        },
      },
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      host: devHost,
      port: devPort,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          // 不需要重写路径，后端路由已经以 /api 为前缀
        },
      },
    },
  }
})
