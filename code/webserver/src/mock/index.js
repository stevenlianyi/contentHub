/* ============================================================================
 * Mock 层 · axios 自定义 adapter 短路（计划 §2.8 / Step 3 要点 5·6）
 * ----------------------------------------------------------------------------
 * 设计要点：
 *   1) **不改业务代码**：`api/*.js`（createService → http）完全一致，仅在此处替换 adapter；
 *   2) **报文同构**：`data` / `CMD` / `msgKey` / `MSG` / `errCode` / `SN` / `YMDHMS`，
 *      查询类附 `total` / `beginNum`（字符串）/ `endNum`（字符串）/ `indexKey`；
 *   3) **领域处理器返回极简结构**，由本文件统一封装报文，避免 11 个域文件重复拼装：
 *        · 成功：`{ data, total?, beginNum?, endNum?, indexKey? }`
 *        · 失败：`{ __err: { code, content, data? } }`
 *   4) 共享能力（分页切片 / 缓冲续取 / 强制错误 / 时间）通过 `ctx` 注入处理器，
 *      ★ 从而**不新增** mock 公共模块（裁定 D：目录增补仅限 `src/mock/data/*.js`）；
 *   5) 会话契约（§2.4.2 + 裁定 G）：免登录 CMD 不校验 `sessionID`，其余缺失即 `B8`。
 *
 * 开发态可触发入口（裁定 F，全部位于 mock 内，生产构建随 mock 一并剔除）：
 *   · `login` 传 `loginID='expired'` → `B8`；传 `'error'` → `C4`；
 *   · `window.__MOCK_FORCE_ERR__ = 'C5'` → **下一次**请求强制返回该错误码（读取后即清除）；
 *   · `topicadd` 标题 > 50 字 → `C5`；`assetadd` 非 64 位小写 sha256 → `D0`；
 *   · `publishpush` 缺 `confirmFlag` → `F4` 且回显 `idempotencyKey` / `confirmToken`。
 * ========================================================================== */
import { settings } from '@/config/settings'
import { errText } from '@/config/chOptions'
import { setActiveAdapter } from '@/utils/http'
import { handlers as userHandlers } from './user'
import { handlers as topicHandlers } from './topic'
import { handlers as assetHandlers } from './asset'
import { handlers as layoutHandlers } from './layout'
import { handlers as platformHandlers } from './platform'
import { handlers as renderHandlers } from './render'
import { handlers as artifactHandlers } from './artifact'
import { handlers as publishHandlers } from './publish'
import { handlers as complianceHandlers } from './compliance'
import { handlers as accountHandlers } from './account'
import { handlers as auditHandlers } from './audit'
import { handlers as mcpHandlers } from './mcp'
import { pad } from './data/util'

/** 路由表：CMD（小写）→ 处理器 */
export const routeTable = {
  ...userHandlers,
  ...topicHandlers,
  ...assetHandlers,
  ...layoutHandlers,
  ...platformHandlers,
  ...renderHandlers,
  ...artifactHandlers,
  ...publishHandlers,
  ...complianceHandlers,
  ...accountHandlers,
  ...auditHandlers,
  ...mcpHandlers
}

/** 免登录端点（§2.9.8）：不校验 sessionID */
export const FREE_CMDS = new Set([
  'generalnext', 'login', 'registration', 'smsrequest', 'smsverify',
  'resetpasswd', 'chkuserexist', 'platformqry', 'layoutqry', 'artifactqry'
])

/* ------------------------------ 报文封装 ------------------------------ */

let snCounter = 0
const now14 = () => {
  const d = new Date()
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
}

function baseEnvelope(cmd, errCode, content, strSn) {
  return {
    CMD: cmd,
    msgKey: settings.msgKey,
    MSG: { errCode, content },
    errCode,
    SN: strSn,
    YMDHMS: now14()
  }
}

export function okEnvelope(cmd, result = {}, strSn) {
  const envelope = { data: result.data === undefined ? null : result.data, ...baseEnvelope(cmd, 'B0', '', strSn) }
  // 查询类附加字段（与后端 queryBufferCommon 缓冲返回同构，§2.4.4）
  for (const key of ['total', 'beginNum', 'endNum', 'indexKey']) {
    if (result[key] !== undefined) envelope[key] = result[key]
  }
  return envelope
}

export function errEnvelope(cmd, code, content, data, strSn) {
  return {
    data: data === undefined ? {} : data,
    ...baseEnvelope(cmd, code, content || errText(code) || `请求失败（${code}）`, strSn)
  }
}

/* ------------------------------ 共享能力 ------------------------------ */

/** 查询缓冲：indexKey → 列表快照（供 generalnext 续取，§2.4.4） */
const buffers = new Map()

/** 分页切片：返回同构的查询元信息；beginNum / endNum 按后端口径转字符串 */
function paginate(list, body, cmd, key = '') {
  const begin = Math.max(0, Number(body.beginNum) || 0)
  const size = Math.max(1, (Number(body.endNum) || begin + 20) - begin)
  const indexKey = `${cmd}_${key || 'all'}_${begin}_${size}_${list.length}`
  buffers.set(indexKey, list)
  return {
    data: list.slice(begin, begin + size),
    total: list.length,
    beginNum: String(begin),
    endNum: String(begin + size),
    indexKey
  }
}

/** generalnext：按 indexKey 取下一批（避免每页重查全量） */
function nextBuffer(body) {
  const list = buffers.get(body.indexKey)
  if (!list) {
    return { __err: { code: 'CB', content: '查询缓冲已失效，请刷新列表后重试' } }
  }
  const begin = Math.max(0, Number(body.beginNum) || 0)
  const size = Math.max(1, (Number(body.endNum) || begin + 20) - begin)
  return {
    data: list.slice(begin, begin + size),
    total: list.length,
    beginNum: String(begin),
    endNum: String(begin + size),
    indexKey: body.indexKey
  }
}

/** 开发态强制错误开关：读取后立即清除（裁定 F） */
function takeForcedError() {
  if (typeof window === 'undefined') return ''
  const code = window.__MOCK_FORCE_ERR__
  if (!code) return ''
  window.__MOCK_FORCE_ERR__ = ''
  console.warn(`[mock] 已按 __MOCK_FORCE_ERR__ 强制返回 ${code}`)
  return String(code)
}

const ctx = {
  paginate,
  nextBuffer,
  now14,
  err: (code, content, data) => ({ __err: { code, content, data } })
}

/* ------------------------------ adapter ------------------------------ */

function parseBody(data) {
  if (!data) return {}
  if (typeof data === 'string') {
    try {
      return JSON.parse(data)
    } catch {
      return {}
    }
  }
  return typeof data === 'object' ? data : {}
}

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

/** 构造与真实 axios 响应同形的返回体 */
const respond = (config, data) => ({ data, status: 200, statusText: 'OK', headers: {}, config })

/**
 * 开发态请求留痕（仅 Mock 层，生产构建随 mock 剔除）：
 * 记录**请求拦截器之后**的最终报文正文，等价于 DevTools Network 里的 Request Payload，
 * 便于在无真实网络请求（Mock 短路）时核对 `sessionID` 是否在 body 中（验收标准 1）。
 * 读取：`window.__MOCK_REQUESTS__`（最近 20 条）。
 */
function recordRequest(config) {
  if (typeof window === 'undefined') return
  const log = window.__MOCK_REQUESTS__ || (window.__MOCK_REQUESTS__ = [])
  log.push({
    url: config.url,
    method: String(config.method || 'get').toUpperCase(),
    headerSessionID: config.headers?.sessionID || '',
    payload: config.data
  })
  if (log.length > 20) log.shift()
}

export function createMockAdapter() {
  return async (config) => {
    const cmd = String(config.url || '').replace(/^\/+/, '').split('?')[0].toLowerCase()
    const body = parseBody(config.data)
    recordRequest(config)
    const strSn = body.SN === undefined ? String((snCounter += 1)) : String(body.SN)
    await delay(120 + Math.floor(Math.random() * 180)) // 模拟网络延迟，便于观察骨架屏

    const forced = takeForcedError()
    if (forced) return respond(config, errEnvelope(cmd, forced, '', undefined, strSn))

    if (!FREE_CMDS.has(cmd) && !body.sessionID) {
      return respond(config, errEnvelope(cmd, 'B8', '会话已失效，请重新登录', undefined, strSn))
    }

    const handler = routeTable[cmd]
    if (!handler) {
      return respond(config, errEnvelope(cmd, 'ERR_NOCMD', `Mock 未覆盖的命令：${cmd}`, undefined, strSn))
    }

    const result = await handler(body, ctx)
    if (result && result.__err) {
      return respond(config, errEnvelope(cmd, result.__err.code, result.__err.content, result.__err.data, strSn))
    }
    return respond(config, okEnvelope(cmd, result || {}, strSn))
  }
}

/**
 * 安装 Mock adapter。
 * @param {object} [instance] 目标 axios 实例（`main.js` 传 http）
 *
 * 同时调用 `setActiveAdapter`：js 模块在 import 期即执行，业务侧 `createService()` 可能早于本调用，
 * 那些派生实例已按引用复制了旧的 adapter，只有通过「转发适配器」才能让它们也被 Mock 短路。
 */
export function installMockAdapter(instance) {
  const adapter = createMockAdapter()
  setActiveAdapter(adapter)
  if (instance?.defaults) instance.defaults.adapter = adapter
  console.info('[mock] Mock adapter 已安装（VITE_USE_MOCK=true）')
  return adapter
}

export default installMockAdapter
