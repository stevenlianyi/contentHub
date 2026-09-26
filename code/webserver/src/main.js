import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import Toast from 'vue3-toastify'
import 'vue3-toastify/dist/index.css'
// 图标库：Font Awesome 6 Free（裁定 D / 选项 A）
//  `.fa` 在 FA6 中自带 solid 字体族与 900 字重（css/all.css: .fa { font-family: var(--fa-style-family, "Font Awesome 6 Free"); font-weight: var(--fa-style, 900) }），
//  故代码中沿用 `class="fa fa-house"` 的 v4/v5 简写即可，无需改写成 `fa-solid fa-house`。
import '@fortawesome/fontawesome-free/css/all.min.css'
import './styles/tailwind.css'
import './styles/element-vars.css'

import App from './App.vue'
import { router, resetRouter } from './router'
import { pinia } from './store'
import { useUserStore } from './store/modules/user'

const app = createApp(App)

// Element Plus 图标全量注册（@element-plus/icons-vue 已在 package.json 显式声明）
for (const [key, comp] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, comp)
}

/**
 * 会话失效桥接（§2.5 第 2 条 ↔ 裁定 E 的落地）：
 * `utils/http.js` 不得 import store（否则 store → api → http 成环），故它在 B8/401 时
 * 只清 sessionStorage 并广播 `ch:session-timeout`；此处收到广播后复位内存会话与动态路由，
 * 使「清会话 + 跳登录」与 Step 2 的 `resetAccessToken()` 行为完全一致。
 */
window.addEventListener('ch:session-timeout', () => {
  const userStore = useUserStore()
  userStore.resetAccessToken()
  resetRouter()
})

// 主界面仅暗色：同步写入 html 上的 class（index.html 已预置，这里兜底保证）
document.documentElement.classList.add('dark')

// 点击外部关闭（下拉菜单/浮层通用）
app.directive('click-outside', {
  beforeMount(el, binding) {
    el.__clickOutside__ = (event) => {
      if (!el.contains(event.target)) binding.value(event)
    }
    document.addEventListener('click', el.__clickOutside__)
  },
  unmounted(el) {
    if (el.__clickOutside__) document.removeEventListener('click', el.__clickOutside__)
    delete el.__clickOutside__
  }
})

/**
 * 启动：仅在 VITE_USE_MOCK === 'true' 时**动态**挂载 Mock adapter。
 * ★ 必须用动态 `import()` 而非顶层静态 import —— 这样 `VITE_USE_MOCK=false` 构建时
 *   `src/mock/**` 会被 tree-shaking 整体剔除（验收项 6）。
 * ★ 不使用顶层 `await`（Vite 5 默认 build.target 不支持，会导致 npm run build 失败）。
 *
 * ★ 越界修复（Step 7 复测发现，口径未变、仅调整**执行顺序**）：
 *   `app.use(router)` 会**立即启动初始导航**，而守卫在「已有 token 但 roles 为空」（刷新场景）
 *   时会先调 `getuserinfo`。若 Mock adapter 尚未安装，该请求会打到真实网络（开发态 Vite 代理
 *   /chapi 返回 500）→ 守卫按 B8 口径 `resetAccessToken()` + `logout()` → **刷新即掉线跳登录**。
 *   故把插件安装整体移入 bootstrap()，置于 Mock adapter 安装**之后**（pinia 仍先于 router 安装，
 *   保证守卫内 `useUserStore()` 有活动 pinia 实例）。
 */
async function bootstrap() {
  if (import.meta.env.VITE_USE_MOCK === 'true') {
    const [{ default: http }, { installMockAdapter }] = await Promise.all([
      import('./utils/http'),
      import('./mock')
    ])
    installMockAdapter(http)
  }

  app.use(pinia)
  app.use(router)
  app.use(ElementPlus)
  app.use(Toast, { position: 'top-right', autoClose: 3000, hideProgressBar: true })

  app.mount('#app')
}

bootstrap()
