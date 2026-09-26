/* ============================================================================
 * HTTP 层 · Step 3（计划 Step 3 要点 1 / §2.4 / §2.5）
 * ----------------------------------------------------------------------------
 * 三条硬约定：
 *   1) ★ 会话必须放**请求体**：后端 `accountApi.calUserCMDMapKeyList` → `dataSet.get("sessionID")`，
 *      仅放 header 会导致所有需登录接口返回 B8（§2.4.2）。本文件同时写 header 仅作兼容。
 *   2) 响应拦截：`B0` 放行并**返回业务报文本身**（含 data/total/errCode），页面写
 *      `const { data, total } = await topicQry(...)`；`B8` 清会话 + 跳登录；
 *      其他 errCode → toast `MSG.content` + reject（★ 页面必须保留用户已填内容）。
 *   3) ★ 本文件**不得 import store / router**（否则 store → api → http 成环；
 *      router → store → api → http 同样成环）。B8/401 走 `removeAccessToken()` + 改写 `location.hash`。
 *
 * adapter 路由（Mock 挂载的关键）：js 模块在 import 时即执行，业务侧 `createService()` 会在
 * `installMockAdapter(http)` 之前把当时的 adapter **按引用**复制走。因此这里给 axios 装一个
 * 「转发适配器」，它在**每次请求时**读取当前生效的 adapter —— 这样安装 Mock 后，
 * 安装前已创建的派生实例也能被 Mock 短路（否则 Mock 开关会静默失效）。
 * ========================================================================== */
import axios from 'axios'
import { toast } from 'vue3-toastify'
import { settings } from '@/config/settings'
import { getAccessToken, removeAccessToken } from '@/utils/accessToken'

/** 解析 axios 默认适配器：axios 1.x 的 `defaults.adapter` 可能是字符串数组（['xhr','http','fetch']） */
function pickDefaultAdapter() {
  const raw = axios.defaults.adapter
  if (typeof raw === 'function') return raw
  if (typeof axios.getAdapter === 'function') return axios.getAdapter(raw)
  return () => Promise.reject(new Error(`[http] 无法解析 axios 默认 adapter：${String(raw)}`))
}

const defaultAdapter = pickDefaultAdapter()
let activeAdapter = null

/** 安装/卸载自定义 adapter（Mock 层唯一入口；传 null 即恢复真实网络） */
export function setActiveAdapter(adapter) {
  activeAdapter = typeof adapter === 'function' ? adapter : null
}

/** 转发适配器：请求时再决定走 Mock 还是真实网络 */
const routingAdapter = (config) => (activeAdapter || defaultAdapter)(config)

const http = axios.create({
  baseURL: settings.apiBaseUrl,
  timeout: Number(settings.requestTimeout),
  adapter: routingAdapter
})

/* ---------------------------------------------------------------------------
 * 请求拦截：sessionID 注入请求体
 * ------------------------------------------------------------------------- */
function onRequest(config) {
  const token = getAccessToken()
  if (token) {
    config.headers = config.headers || {}
    // header 同名兼容（后端以请求体为准）
    config.headers.sessionID = token
    config.headers['Content-Type'] = config.headers['Content-Type'] || 'application/json'
    if (config.data && typeof config.data === 'object' && !(config.data instanceof FormData)) {
      config.data = { lang: 'CN', clientType: 'web', ...config.data, sessionID: token }
    } else if (!config.data) {
      config.data = { lang: 'CN', clientType: 'web', sessionID: token }
    }
  }
  return config
}

/* ---------------------------------------------------------------------------
 * 响应拦截：B0 放行 / B8 清会话 / 其他 toast MSG.content
 * ------------------------------------------------------------------------- */
const normalize = (text) => String(text || '').trim().replace(/[;；]+$/, '')

let lastTimeoutAt = 0

/**
 * 会话失效统一处理（§2.5 第 2 条 + 裁定 E）：
 *   · 清本地持久化会话（accessToken.js）；
 *   · 广播 `ch:session-timeout` —— 本文件**不得 import store**（否则 store → api → http 成环），
 *     故由启动层（main.js）监听该事件并执行 `userStore.resetAccessToken()` + `resetRouter()`，
 *     保证内存中的 accessToken / roles / 动态路由一并复位；
 *   · 改写 `location.hash` 跳登录页（带 redirect 回跳），不依赖 router 实例。
 */
function handleSessionTimeout() {
  removeAccessToken()
  if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('ch:session-timeout'))
  const now = Date.now()
  if (now - lastTimeoutAt < 1500) return // 并发请求只处理一次
  lastTimeoutAt = now
  toast.error('会话已过期，请重新登录')
  const current = location.hash.replace(/^#/, '') || '/'
  if (current.startsWith('/login')) return // 已在登录页：只清会话，不重复跳转
  location.hash = `#/login?redirect=${encodeURIComponent(current)}`
}

function redirectTo(path) {
  if (location.hash.replace(/^#/, '').split('?')[0] !== path) location.hash = `#${path}`
}

function onResponse(response) {
  const res = response.data
  if (!res || typeof res !== 'object') return response
  if (res.errCode === settings.sucessRespCode) return res // B0：返回业务报文
  if (res.errCode === settings.sessionTimeOutCode) {
    handleSessionTimeout()
    return Promise.reject(res)
  }
  if (!response.config.silent) {
    toast.error(normalize(res.MSG?.content) || `请求失败（${res.errCode}）`)
  }
  return Promise.reject(res)
}

function onResponseError(error) {
  const status = error.response?.status
  if (status === 401) {
    handleSessionTimeout()
    return Promise.reject(error)
  }
  if (status === 403) {
    redirectTo('/403')
    return Promise.reject(error)
  }
  if (!error.config?.silent) toast.error('服务异常，请稍后重试')
  console.error('[http]', error)
  return Promise.reject(error)
}

/**
 * 给实例挂上同一组拦截器。
 * ★ 必须显式挂载：axios 1.x 的 `instance.create()` 会 `new Axios()` 生成**全新的上下文**，
 *   拦截器**不会继承**。若按计划示例只写 `http.create({baseURL})`，派生的 svc 会丢掉
 *   「sessionID 注入请求体」与「B0/B8 处理」——表现为所有请求都返回 B8、且页面拿不到业务报文。
 *   （本步实测复现：svc 的返回值是原始 axios response，errCode 恒为 B8。）
 */
function applyInterceptors(instance) {
  instance.interceptors.request.use(onRequest)
  instance.interceptors.response.use(onResponse, onResponseError)
  return instance
}

applyInterceptors(http)

/** 各域 api 用：派生实例并挂载同一组拦截器（adapter 仍走 routingAdapter，故 Mock 生效） */
export const createService = (baseURL = settings.apiBaseUrl) =>
  applyInterceptors(http.create({ baseURL, timeout: Number(settings.requestTimeout) }))

export default http
