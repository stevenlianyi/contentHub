import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// 内容中枢前端构建配置（计划 2.1 / Step 0）
// - base '/chapp/'：与后端同源部署时前端挂在 /chapp/ 下
// - 代理 /chapi、/upload 与 /hfile 到后端：
//     · 默认本机 chAPI.py / ylwzRecvFiles.py（127.0.0.1:5000）；
//     · 远端联调：在 .env.development.local 写 VITE_PROXY_TARGET=https://www.mindgram.top
//       并把 VITE_USE_MOCK 置 false（该文件按 Vite 约定不纳入版本库）
// - Step 8：上传通道为 **/upload**（nginx upload 模块在该路由注入 file.path/file.name 等字段后
//   转交后端 /hfile）；前端直打 /hfile 会因缺字段被 fileHandler 拒绝回 D3。/hfile 代理仅留作直连调试。
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = env.VITE_PROXY_TARGET || 'http://127.0.0.1:5000'
  //★ 2026-09-22: 部署路径可配 —— 开发态缺省 /chapp/; 生产由 .env.production 的 VITE_BASE_PATH 指定
  //  (计划部署节点: http://www.mindgrap.com/contenthubapp → base 应为 /contenthubapp/)。
  //  ★ 必须与 src/router/index.js 的 createWebHashHistory(import.meta.env.BASE_URL) 保持一致。
  const basePath = env.VITE_BASE_PATH || '/chapp/'
  const proxyOptions = {
    target: proxyTarget,
    changeOrigin: true,
    secure: !proxyTarget.startsWith('https') ? undefined : false
  }
  return {
    plugins: [vue()],
    base: basePath,
    build: {
      outDir: 'dist',
      rollupOptions: {
        output: {
          entryFileNames: 'assets/[name].[hash].js',
          chunkFileNames: 'assets/[name].[hash].js',
          assetFileNames: 'assets/[name].[hash].[ext]'
        }
      }
    },
    server: {
      port: 3000,
      host: '0.0.0.0',
      allowedHosts: true,
      proxy: {
        '/chapi': { ...proxyOptions },
        '/hfile': { ...proxyOptions },
        '/upload': { ...proxyOptions }
      }
    },
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    }
  }
})
