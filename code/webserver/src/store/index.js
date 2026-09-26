// ============================================================
// Pinia 实例（Step 2 · 全局框架与路由）
// ------------------------------------------------------------
// 约定（计划 §2.1）：store/modules 只放跨页共享状态；页面局部状态用 ref/reactive，不进 store。
// 本步仅挂载 modules/user.js（会话 + 角色 + 权限）。
// ★ 不使用 persist 插件（基线 user.js 的 persist 因缺插件而失效，属缺陷，不继承）。
// ============================================================
import { createPinia } from 'pinia'

export const pinia = createPinia()

export default pinia
