/* ============================================================================
 * 路由 · Step 2「全局框架与路由」
 * ----------------------------------------------------------------------------
 * 三组路由（计划 Step 2 第 5 点）：
 *   ① publicRoutes  —— `/login`、`/403`（免登录）
 *   ② asyncRoutes   —— 父路由 `/`（MainLayout）下挂页面路由，按 `meta.roles` 动态挂载
 *   ③ notFoundRoute —— `/:pathMatch(.*)*` → NotFound
 * 全部页面组件用 `() => import('@/views/xxx.vue')` 懒加载（§2.11 性能）。
 *
 * 相对计划原文的 2 处实现说明（已在交付说明中登记，非口径变更）：
 *   ① notFoundRoute 常驻基础路由，而非「addRoutes 时追加」：保证未登录/未挂载动态路由时
 *      访问未知路径也能命中 404；否则 vue-router 会输出 "No match found" 警告且页面空白。
 *      addRoutes() 内仍调用 ensureNotFoundRoute() 兜底。
 *   ② document.title 的同步放在 afterEach：登出/越权重定向会连续触发多次守卫，
 *      afterEach 保证只写最终落定路由的标题。
 *
 * meta.roles 取值口径：与 AppSidebar 的 NAV_ITEMS 保持一致（侧栏可见 ⇔ 路由可访问），
 * 其中「导航未覆盖、需写权限」的页面按 2.9.8 角色授权表收紧（详见各行注释）。
 * ========================================================================== */
import { createRouter, createWebHashHistory } from 'vue-router'
import { title as APP_TITLE } from '@/config/settings'
import { useUserStore } from '@/store/modules/user'

const R_ADMIN = 'administrator'
const R_MANAGER = 'manager'
const R_OPERATOR = 'operator'
const R_CUSTOMER = 'customer'
const R_VISITOR = 'visitor'

/** 侧栏可见性（与 NAV_ITEMS 严格对齐；★ 2026-09-23 起为 8 项） */
const ROLES_ALL = [R_ADMIN, R_MANAGER, R_OPERATOR, R_CUSTOMER, R_VISITOR]
const ROLES_CONTENT = [R_ADMIN, R_MANAGER, R_OPERATOR, R_CUSTOMER]
/** 需 operator 及以上（渲染 / 合规校验 / 审计等写读权限，2.9.8） */
const ROLES_OPS = [R_ADMIN, R_MANAGER, R_OPERATOR]
/** 系统级（账号凭据、系统设置） */
const ROLES_SYSTEM = [R_ADMIN, R_MANAGER]
/**
 * ★ 2026-09-23「第三方账号管理」：所有非访客角色（可见性 = 侧栏 NAV_ITEMS 第 8 项）。
 * 归属隔离在**服务端**强制（非管理员强制 ownerID = 登录 loginID，见 `subfunc/crudApi.py` /
 * `subfunc/accountApi.py`），前端仅控制入口可见性 —— 不得用 `hasPermission()`（恒 false）。
 */
const ROLES_ACCOUNT_SELF = [R_ADMIN, R_MANAGER, R_OPERATOR, R_CUSTOMER]

/** 免登录路由 */
export const publicRoutes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/403',
    name: 'Forbidden',
    component: () => import('@/views/Forbidden.vue'),
    meta: { title: '无权限' }
  }
]

/** 404 兜底（常驻，见文件头说明 ①） */
export const notFoundRoute = {
  path: '/:pathMatch(.*)*',
  name: 'NotFound',
  component: () => import('@/views/NotFound.vue'),
  meta: { title: '页面不存在' }
}

/**
 * 动态路由：父路由 `/` 挂页面子路由（各页 `meta: { title, roles }`）。
 * 页面与端点映射见计划 §2.10；子路由顺序即侧栏之外的业务顺序，与导航无耦合。
 */
export const asyncRoutes = {
  path: '/',
  name: 'MainLayout',
  component: () => import('@/layouts/MainLayout.vue'),
  children: [
    { path: '', name: 'Dashboard', component: () => import('@/views/Dashboard.vue'), meta: { title: '工作台', roles: ROLES_ALL } },
    { path: 'topics', name: 'Topics', component: () => import('@/views/Topics.vue'), meta: { title: '主题库', roles: ROLES_CONTENT } },
    // P-03：customer 可只读查看（写操作由 Step 7 按 hasRole/hasPermission 收敛）
    { path: 'topics/:code', name: 'TopicEdit', component: () => import('@/views/TopicEdit.vue'), meta: { title: '主题编辑', roles: ROLES_CONTENT } },
    { path: 'assets', name: 'Assets', component: () => import('@/views/Assets.vue'), meta: { title: '素材图库', roles: ROLES_CONTENT } },
    { path: 'render-jobs', name: 'RenderJobs', component: () => import('@/views/RenderJobs.vue'), meta: { title: '渲染任务', roles: ROLES_OPS } },
    // P-07：artifactqry 为免登录端点，各角色均可读
    { path: 'artifacts', name: 'Artifacts', component: () => import('@/views/Artifacts.vue'), meta: { title: '产物台账', roles: ROLES_ALL } },
    // P-08：topicrender 不在 customer/visitor 授权清单内
    { path: 'preview/:code', name: 'Preview', component: () => import('@/views/Preview.vue'), meta: { title: '预览', roles: ROLES_OPS } },
    // P-09：publishcheck 不在 customer/visitor 授权清单内
    { path: 'compliance/:code', name: 'Compliance', component: () => import('@/views/Compliance.vue'), meta: { title: '合规校验', roles: ROLES_OPS } },
    // 合规校验一级入口（裁定 B：固定 /compliance-hub）
    { path: 'compliance-hub', name: 'ComplianceHub', component: () => import('@/views/ComplianceHub.vue'), meta: { title: '合规校验', roles: ROLES_CONTENT } },
    { path: 'publish-records', name: 'PublishRecords', component: () => import('@/views/PublishRecords.vue'), meta: { title: '投递记录', roles: ROLES_CONTENT } },
    // P-11：仅 administrator / manager（2.9.8 operator **无** account* 写权限）→ ROLES_SYSTEM
    { path: 'accounts', name: 'Accounts', component: () => import('@/views/Accounts.vue'), meta: { title: '账号管理', roles: ROLES_SYSTEM } },
    // ★ 2026-09-23「第三方账号管理」：非访客角色各管本人账号（服务端按 loginID 强制归属过滤）；
    //  与上方 /accounts（管理员全量台账）**并存**，两页互相跳转（见 AppSidebar 第 8 项）。
    { path: 'my-accounts', name: 'MyAccounts', component: () => import('@/views/MyAccounts.vue'), meta: { title: '第三方账号管理', roles: ROLES_ACCOUNT_SELF } },
    { path: 'audit-logs', name: 'AuditLogs', component: () => import('@/views/AuditLogs.vue'), meta: { title: '审计日志', roles: ROLES_OPS } },
    // P-13：导航文案为「系统」（NAV_ITEMS 冻结），页面标题用「系统设置」（2.3.5 语义）
    { path: 'settings', name: 'Settings', component: () => import('@/views/Settings.vue'), meta: { title: '系统设置', roles: ROLES_SYSTEM } }
  ]
}

export const routes = [...publicRoutes, notFoundRoute]

export const router = createRouter({
  //★ 2026-09-22: hash base 跟随构建 base(Vite 注入的 import.meta.env.BASE_URL),
  //  开发态=/chapp/, 生产态由 .env.production 的 VITE_BASE_PATH 决定(计划部署 /contenthubapp/)。
  //  ★ 必须与 vite.config.js 的 base 同源, 否则 router.resolve 生成的链接会指向旧前缀导致 404。
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes
})

/**
 * ★ 开发自测路由（Step 4 裁定 D）：`/dev/components` 逐组件渲染自测页。
 * 生产构建移除方式（三重保证，不依赖运行期判断）：
 *   ① 不静态 import、不写入 asyncRoutes / publicRoutes；
 *   ② `import.meta.env.DEV` 在构建时被 Vite 静态替换为 `false`，整块成为死代码；
 *   ③ 动态 `import()` 位于死代码块内，Rollup tree-shaking 后不会产出该页 chunk。
 */
if (import.meta.env.DEV) {
  router.addRoute({
    path: '/dev/components',
    name: 'DevComponents',
    component: () => import('@/views/dev/Components.vue')
  })
}

const LAYOUT_ROUTE_NAME = asyncRoutes.name

/** 越权判定用的「路径 → 允许角色」表（含被角色裁剪掉的页面） */
const PATH_ROLE_RULES = asyncRoutes.children.map((route) => ({
  roles: route.meta?.roles || [],
  matcher: toPathRegExp(route.path)
}))

/** 子路由相对路径 → 正则（`:param` 段按单段通配） */
function toPathRegExp(path) {
  const normalized = `/${path}`.replace(/\/+$/, '')
  return new RegExp(`^${normalized.replace(/:[A-Za-z0-9_]+/g, '[^/]+')}/?$`)
}

function hasAnyRole(currentRoles, requiredRoles) {
  if (!requiredRoles.length) return true
  return requiredRoles.some((role) => currentRoles.includes(role))
}

/** 重置动态路由（登出后重建；removeRoute 会连带移除全部子路由） */
export function resetRouter() {
  if (router.hasRoute(LAYOUT_ROUTE_NAME)) router.removeRoute(LAYOUT_ROUTE_NAME)
}

function ensureNotFoundRoute() {
  if (!router.hasRoute(notFoundRoute.name)) router.addRoute(notFoundRoute)
}

/**
 * 按角色裁剪并挂载动态路由。
 * @param {string[]} roles 当前用户角色
 * @returns 实际挂载的页面子路由
 */
export function addRoutes(roles = []) {
  resetRouter()
  const granted = asyncRoutes.children.filter((route) => hasAnyRole(roles, route.meta?.roles || []))
  const layoutRoute = { ...asyncRoutes, children: granted }
  // 角色未命中任何页面时，根路径直接落到 403，避免死循环或空白页
  if (!granted.length) layoutRoute.redirect = '/403'
  router.addRoute(layoutRoute)
  ensureNotFoundRoute()
  return granted
}

router.beforeEach(async (to) => {
  const userStore = useUserStore()
  await userStore.waitInitFinished()

  const loggedIn = Boolean(userStore.accessToken)

  // ② 已登录访问登录页 → 回工作台
  if (to.path === '/login') return loggedIn ? { path: '/' } : true

  // ③ 未登录访问受保护路由 → 登录页（带 redirect 回跳）
  if (!loggedIn) {
    return { path: '/login', query: to.fullPath && to.fullPath !== '/' ? { redirect: to.fullPath } : {} }
  }

  // ④ 已登录但角色为空（刷新后）→ 拉取用户信息，失败即清会话回登录页
  if (!userStore.roles.length) {
    try {
      await userStore.getInfo()
    } catch (error) {
      await userStore.logout()
      return false
    }
  }

  // ⑤ 动态路由未挂载 → 按角色挂载后重新解析当前地址
  if (!router.hasRoute(LAYOUT_ROUTE_NAME)) {
    addRoutes(userStore.roles)
    return { path: to.path, query: to.query, hash: to.hash, replace: true }
  }

  // ⑥ 越权：命中已挂载路由的 meta.roles，或命中被角色裁剪掉的页面路径 → 403
  const requiredRoles = to.meta?.roles
  const deniedByMeta = Array.isArray(requiredRoles) && !hasAnyRole(userStore.roles, requiredRoles)
  const deniedByPath = PATH_ROLE_RULES.some(
    (rule) => rule.matcher.test(to.path) && !hasAnyRole(userStore.roles, rule.roles)
  )
  if (deniedByMeta || deniedByPath) return { path: '/403', replace: true }

  return true
})

// ⑦ 同步页面标题（见文件头说明 ②）
router.afterEach((to) => {
  document.title = to.meta?.title ? `${to.meta.title} · ${APP_TITLE}` : APP_TITLE
})

export default router
