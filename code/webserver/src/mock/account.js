/* ============================================================================
 * Mock · 平台账号域（accountqry / accountadd / accountmodify / accountdel / accounthealth）
 * ----------------------------------------------------------------------------
 * `healthStatus` 四值样例齐备（OK / EXPIRING / INVALID / UNKNOWN）。
 *
 * 【★ Step 15 与真实后端对齐的四处改动（理由一律为源码事实，非计划文字）】
 *   ① `accountqry` 支持 `mode` 投影 + 服务端筛选 + `order`：
 *      · `mode='full'`（缺省，与后端一致）返回 `ch_account` **全列**
 *        —— ★ 含 `credentialCipher` / `credentialIV`，用于验证 P-11 的字段白名单确实丢弃了密文列；
 *      · `mode='short'` 只返回 `CH_QUERY_SHORT_COLUMNS['ch_account']`
 *        （`recID,accountCode,platform,accountName,subjectType,verifiedFlag,capability,healthStatus`；
 *        见 `common/mysqlCommon.py:333`，**不含** `expireYMDHMS`/`lastCheckYMDHMS`/`appID`）；
 *      · 服务端筛选 `accountCode/platform/healthStatus/ownerID` + `order:'modify'`
 *        （`modifyYMDHMS DESC`），对齐 R-28 手改后的 `funcAccountQry`。
 *   ② `accounthealth` 的 `action` **不再默认 `check`**：空 action = **只汇总不巡检**
 *      （`subfunc/accountApi.py:812-844`），出参才带 `healthSummary`；非空 action 才带 `credentialCheck`。
 *      `refresh` / `probe` 与 `check` **完全等价**（同一 `runOnce` 调用）。
 *   ③ `accounthealth` 新增 **`credentialCheck`**（与 `schedule/credentialCheck.py::runOnce` 同构）：
 *      `{ total, checked, ok, expiring, invalid, unknown, skipped, degraded, warnDays, items[],
 *         alertSummary, checkedAt }`；`items[]` 每项
 *      `{ accountID, accountCode, platform, healthStatus, probed, alertLevel, errMsg, skipReason }`
 *      （★ **不含 `accountName`** → 页面用列表数据把 `accountCode` 映射为 `accountName`）。
 *      锁未取到 → `skipped = -1` + `msg`；Redis 不可用 → `degraded = 1`。
 *      ★ 小红书 / 通用平台**跳过并给出原因原文**（`SKIP_PLATFORM_NOTE_MAP`），且**不改写**其健康状态。
 *   ④ 移除旧 Mock 私有的 `accounts / probe / byPlatform` 出参（真实后端无此三项，且 `accounts`
 *      会把 `appSecret` 带到响应体里，与 P-11「响应中无明文密钥」的验收相冲突）。无消费方。
 *   ⑤ `accountdel` 未命中改回 **`CB`**（后端 `funcAccountDel` 查不到即 `CB`；旧 Mock 误用 `BI`），
 *      并保持**硬删除**语义（后端 `delete_ch_account`，软删分支 `delFlag='1'` 被注释掉）。
 *
 * 【⑦ 归属隔离（★ 2026-09-23「第三方账号管理」，对齐后端 crudApi / accountApi）】
 *   · 管理员 = administrator / manager → **超管视角**（不按 ownerID 过滤，可读可改任意账号）；
 *   · 非管理员：`accountqry` 强制 `ownerID = loginID`（覆盖前端入参）、`accountadd` 强制写本人归属、
 *     `accountmodify` / `accountdel` 越权 → `BG`（权限不足）、`accounthealth` 的巡检明细与
 *     `healthSummary` 均按 `ownerID = loginID` 收窄；归属不可自行修改（忽略 ownerID 入参）；
 *   · 会话口径复用 `./user` 的 `currentSession(body)`（**不新增** mock 公共模块，裁定 D 不破）；
 *   · 种子 `ACCOUNTS` 覆盖 4 个开发态登录账号（含 customer 的 `wangys`，见 `data/ops.js`）。
 *
 * 【开发态可触发入口（仅 Mock；生产构建随 mock 剔除）】
 *   · `window.__MOCK_CRED_SKIPPED__ = true`   → `accounthealth` 返回 `skipped = -1`（锁未取到，本轮跳过）；
 *   · `window.__MOCK_CRED_DEGRADED__ = true`  → `accounthealth` 返回 `degraded = 1`（Redis 不可用降级）；
 *   · `window.__MOCK_FORCE_ERR__ = 'CB'`      → 下一次请求强制报错（全局开关，见 mock/index.js）；
 *   · `accountadd` / `accountmodify` 传 `appSecret = 'no-key'` → 模拟「未配置 CH_CREDENTIAL_KEY」→ `F0`。
 *
 * 【⑥ 凭据写入（2026-09-22 对齐后端 R-30）】
 *   真实后端 `main/subfunc/crudApi.py` 账号 CRUD 区新增 `_applyAccountSecret()`：只读**明文 `appSecret`**，
 *   经 `common/credentialCipher.encrypt()`（AES-256-GCM）写入 `credentialCipher` / `credentialIV`；
 *   **明文永不落库、不入日志、不回显**；未提供 `appSecret` 时保持原行为（兼容 cipher/IV 直传的旧调用）；
 *   **无密钥（`CH_CREDENTIAL_KEY` 未配置）或加密失败 → `F0` 且拒绝落库**（add 短路不 insert / modify 不 update）。
 *   → 本 Mock 与之对齐：接受 `appSecret`，但**只把它折算为「已配置凭据」的占位密文**
 *     （占位密文由 recID 派生、**与明文无关、不可逆**，且**绝不**把明文写进数据或响应）；
 *   `credentialCipher` / `credentialIV` / `appSecret` 仍然**一律不进入响应体**（对外只暴露布尔语义）。
 * ========================================================================== */
import { ACCOUNTS } from './data/ops'
import { pad } from './data/util'
import { currentSession } from './user'

const VALID_ACTIONS = ['check', 'refresh', 'probe']

/** `CH_QUERY_SHORT_COLUMNS['ch_account']`（`common/mysqlCommon.py:333`） */
const SHORT_COLUMNS = [
  'recID', 'accountCode', 'platform', 'accountName', 'subjectType', 'verifiedFlag', 'capability', 'healthStatus'
]

/** 可探活平台（`schedule/credentialCheck.py:97` PROBE_PLATFORM_LIST） */
const PROBE_PLATFORM_LIST = ['wechat_mp']

/** 跳过原因原文（`schedule/credentialCheck.py:100-103` SKIP_PLATFORM_NOTE_MAP，逐字对齐） */
const SKIP_PLATFORM_NOTE_MAP = {
  xiaohongshu: '小红书无平台凭据(只导出素材包, 不投递不发布), 无需探活, 已跳过',
  generic: '通用 HTML 导出无平台凭据, 无需探活, 已跳过'
}

/** 告警级别（`schedule/credentialCheck.py:119-124` ALERT_LEVEL_MAP） */
const ALERT_LEVEL_MAP = { OK: 'INFO', EXPIRING: 'WARN', INVALID: 'ERROR', UNKNOWN: 'WARN' }

/** 到期预警阈值默认值（`schedule/credentialCheck.py:106` DEFAULT_EXPIRE_WARN_DAYS=7，可用环境变量覆盖） */
const DEFAULT_EXPIRE_WARN_DAYS = 7

const state = { accounts: ACCOUNTS.map((item) => ({ ...item })), seq: ACCOUNTS.length }

function nowStr() {
  const d = new Date()
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
}

/** 开发态触发开关（读取后**不清除**，便于连续观察同一态） */
const flagOn = (key) => typeof window !== 'undefined' && window[key] === true

/* ---------------------------------------------------------------------------
 * ★ 2026-09-23「第三方账号管理」归属隔离（与真实后端同构）
 * -------------------------------------------------------------------------
 * 真实后端事实（`main/subfunc/crudApi.py` / `main/subfunc/accountApi.py`）：
 *   · 管理员 = `common/funcCommon.chkIsManager(roleName)` → administrator / manager，**超管视角**
 *     （不按 ownerID 过滤，可读可改任意账号）；
 *   · 非管理员：accountqry 强制 `ownerID = loginID`（覆盖前端入参）、accountadd 强制写本人归属、
 *     accountmodify / accountdel 越权 → `BG`（权限不足，不区分「不存在」）；
 *   · accounthealth：非管理员的 `runOnce` 明细与 `healthSummary` 均按 `ownerID = loginID` 收窄。
 * Mock 侧复用 `./user` 的 `currentSession(body)`（会话 → { role, loginID }），保持同一口径。
 * ------------------------------------------------------------------------- */
const MANAGER_ROLES = ['administrator', 'manager']

/** 当前请求的归属口径：{ isManager, loginID }（无会话 → 非管理员且 loginID 为空） */
function scopeOf(body) {
  const session = currentSession(body)
  const role = String(session?.role || '')
  return { isManager: MANAGER_ROLES.includes(role), loginID: String(session?.loginID || '') }
}

/** `YYYYMMDDHHMMSS` → Date（参考 `processor/publishService.py::parseYMDHMS`；非法返回 null） */
function parseYMDHMS(value) {
  const raw = String(value || '').trim()
  if (!/^\d{14}$/.test(raw)) return null
  const date = new Date(
    Number(raw.slice(0, 4)), Number(raw.slice(4, 6)) - 1, Number(raw.slice(6, 8)),
    Number(raw.slice(8, 10)), Number(raw.slice(10, 12)), Number(raw.slice(12, 14))
  )
  return Number.isNaN(date.getTime()) ? null : date
}

/**
 * 三态判定（`schedule/credentialCheck.py:240-257` decideHealthStatus 的等价实现）：
 * 探活失败 / 已过期 → INVALID；阈值内 → EXPIRING；其余（含到期时间为空）→ OK。
 */
function decideHealthStatus(expireYMDHMS, probeOk, warnDays) {
  if (!probeOk) return 'INVALID'
  const expireAt = parseYMDHMS(expireYMDHMS)
  if (!expireAt) return 'OK'
  const now = Date.now()
  if (expireAt.getTime() <= now) return 'INVALID'
  if (expireAt.getTime() <= now + warnDays * 86400000) return 'EXPIRING'
  return 'OK'
}

/**
 * 单账号巡检（`schedule/credentialCheck.py:260-330` checkAccount 的等价实现）：
 * 平台不适用 → 跳过并给原因原文（不改写健康状态）；小红书/通用无凭据不报错；
 * 平台凭据缺失（`credentialCipher` 为空）→ 解密失败 → INVALID（对应后端 F0）。
 */
function checkAccount(account, warnDays) {
  const info = {
    accountID: account.recID,
    accountCode: String(account.accountCode || ''),
    platform: String(account.platform || ''),
    healthStatus: 'UNKNOWN',
    probed: false,
    alertLevel: '',
    errMsg: '',
    skipReason: ''
  }

  if (!PROBE_PLATFORM_LIST.includes(info.platform)) {
    info.healthStatus = String(account.healthStatus || 'UNKNOWN').toUpperCase() || 'UNKNOWN'
    info.skipReason = SKIP_PLATFORM_NOTE_MAP[info.platform] || `平台 ${info.platform} 无平台凭据可探活, 已跳过`
    info.alertLevel = ALERT_LEVEL_MAP[info.healthStatus] || 'WARN'
    return info
  }

  if (!String(account.credentialCipher || '').trim()) {
    info.errMsg = '凭据解密失败(credentialCipher 为空), 请由运维重新注入凭据密文'
    info.healthStatus = 'INVALID'
    info.alertLevel = ALERT_LEVEL_MAP.INVALID
    return info
  }

  // 探活：Mock 固定可达；已被人工置 INVALID 的账号视为探活被拒绝（决定 INVALID）
  info.probed = true
  const probeOk = String(account.healthStatus || '') !== 'INVALID'
  if (!probeOk) info.errMsg = '探活失败: access_token 换取被拒绝'
  info.healthStatus = decideHealthStatus(account.expireYMDHMS, probeOk, warnDays)
  info.alertLevel = ALERT_LEVEL_MAP[info.healthStatus] || 'WARN'
  return info
}

/** 健康状态回写（`credentialCheck.py::_writeHealth`；跳过项**不回写**） */
function writeHealth(account, healthStatus, checkedAt) {
  account.healthStatus = healthStatus
  account.lastCheckYMDHMS = checkedAt
}

/** 汇总（大写下标键，与 `subfunc/accountApi.py:832-840` 同形）；★ ownerID 非空时按归属收窄 */
function summarize(ownerID = '') {
  const summary = { total: 0, OK: 0, EXPIRING: 0, INVALID: 0, UNKNOWN: 0 }
  const scope = String(ownerID || '')
  const list = scope ? state.accounts.filter((item) => String(item.ownerID || '') === scope) : state.accounts
  list.forEach((item) => {
    summary.total += 1
    const key = String(item.healthStatus || 'UNKNOWN').toUpperCase()
    if (key in summary && key !== 'total') summary[key] += 1
    else summary.UNKNOWN += 1
  })
  const lower = {
    total: summary.total,
    ok: summary.OK,
    expiring: summary.EXPIRING,
    invalid: summary.INVALID,
    unknown: summary.UNKNOWN
  }
  return { summary, lower }
}

/** 单轮巡检（`runOnce` 等价实现；锁未取到 → `skipped=-1`；Redis 不可用 → `degraded=1`） */
function runOnce(filter = {}) {
  const warnDays = DEFAULT_EXPIRE_WARN_DAYS
  const checkedAt = nowStr()
  const stats = {
    total: 0, checked: 0, ok: 0, expiring: 0, invalid: 0, unknown: 0, skipped: 0,
    degraded: 0, warnDays, items: [], alertSummary: {}, checkedAt
  }

  if (flagOn('__MOCK_CRED_SKIPPED__')) {
    return { ...stats, skipped: -1, msg: '已有巡检在执行(锁未获取), 本轮跳过' }
  }
  stats.degraded = flagOn('__MOCK_CRED_DEGRADED__') ? 1 : 0

  let list = state.accounts
  if (String(filter.platform || '')) list = list.filter((item) => item.platform === filter.platform)
  const accountID = String(filter.accountID === undefined || filter.accountID === null ? '' : filter.accountID)
  if (accountID && accountID !== '0') list = list.filter((item) => String(item.recID) === accountID || String(item.accountID) === accountID)
  //★ 归属收窄（可选；仅当显式传入非空 ownerID 时生效——缺省全量，定时/全量巡检语义不变）
  const ownerID = String(filter.ownerID || '')
  if (ownerID) list = list.filter((item) => String(item.ownerID || '') === ownerID)

  stats.total = list.length
  list.forEach((account) => {
    const item = checkAccount(account, warnDays)
    stats.items.push(item)
    if (item.skipReason) {
      stats.skipped += 1
    } else {
      stats.checked += 1
      writeHealth(account, item.healthStatus, checkedAt)
    }
    const key = String(item.healthStatus || 'UNKNOWN').toUpperCase()
    if (key === 'OK') stats.ok += 1
    else if (key === 'EXPIRING') stats.expiring += 1
    else if (key === 'INVALID') stats.invalid += 1
    else stats.unknown += 1
    const level = String(item.alertLevel || 'WARN')
    stats.alertSummary[level] = (stats.alertSummary[level] || 0) + 1
  })
  return stats
}

/** 列投影：`mode='short'` 只出短列清单；`full`（缺省）返回全部列（含密文列） */
function project(row, mode) {
  if (String(mode) === 'short') {
    const short = {}
    SHORT_COLUMNS.forEach((key) => { short[key] = row[key] })
    return short
  }
  return { ...row }
}

/** 服务端筛选（对齐 R-28 手改 `funcAccountQry` 支持的参数） */
function filterList(body) {
  const keyword = String(body.keyword || '').trim()
  const accountCode = String(body.accountCode || '')
  const platform = String(body.platform || '')
  const healthStatus = String(body.healthStatus || '')
  const ownerID = String(body.ownerID || '')
  let list = [...state.accounts]
  if (body.recID) list = list.filter((item) => item.recID === body.recID)
  if (body.accountID) list = list.filter((item) => item.accountID === body.accountID)
  if (accountCode) list = list.filter((item) => item.accountCode === accountCode)
  if (platform) list = list.filter((item) => item.platform === platform)
  if (healthStatus) list = list.filter((item) => item.healthStatus === healthStatus)
  if (ownerID) list = list.filter((item) => item.ownerID === ownerID)
  if (keyword) list = list.filter((item) => item.accountName.includes(keyword) || String(item.appID || '').includes(keyword))
  // order：'modify' → modifyYMDHMS DESC；其余保持注册顺序（对齐后端 order 缺省回落行为）
  if (String(body.order || '') === 'modify') {
    list.sort((a, b) => String(b.modifyYMDHMS || '').localeCompare(String(a.modifyYMDHMS || '')))
  }
  return list
}

/** 客户端**绝不**直传密文字段（后端 R-30 之后唯一合法通道是明文 `appSecret`）→ 一律剔除 */
const CREDENTIAL_FIELD_LIST = ['credentialCipher', 'credentialIV', 'appSecret']

function stripCredentialFields(source) {
  const clean = { ...source }
  CREDENTIAL_FIELD_LIST.forEach((key) => { delete clean[key] })
  return clean
}

/** 模拟「未配置 CH_CREDENTIAL_KEY」的哨兵值（仅供开发态验收 `F0` 分支） */
const NO_KEY_SENTINEL = 'no-key'
/** 与后端逐字对齐的 `F0` 文案（`crudApi._applyAccountSecret` 的 `rtnErrMsgList`） */
const F0_MESSAGE =
  '凭据加密失败(CredentialCipherError): 未写入 credentialCipher, 明文未落库; ' +
  '请检查环境变量 CH_CREDENTIAL_KEY 是否已配置'

/**
 * 占位密文（**仅 Mock**）：由 recID/accountCode 派生、**与明文无关**，只用于表达「该账号已配置凭据」。
 * ★ 绝不把明文（或明文的长度/摘要）写进数据、响应或日志。
 */
function buildPlaceholderCredential(seedText) {
  const text = String(seedText || 'seed')
  let hash = 2166136261
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i)
    hash = Math.imul(hash, 16777619) >>> 0
  }
  const tail = String(hash).padStart(10, '0')
  return { cipher: `mockcipher.${tail}.${String(text.length).padStart(2, '0')}`, iv: `mockiv${tail.slice(0, 8)}` }
}

/**
 * 应用明文凭据（等价后端 `_applyAccountSecret`）。
 * @param {*} plainSecret 入参明文（**只在本次调用栈内存在，返回后即丢弃**）
 * @param {string} seedText 占位密文的派生种子（recID/accountCode，与明文无关）
 * @returns {{status:'absent'|'ok'|'rejected', cipher?:string, iv?:string}}
 *   · `absent`：未提供 / 空串 → 保持原行为（**不写任何凭据列**）；
 *   · `rejected`：模拟无密钥 → 调用方必须**拒绝落库**并返回 `F0`；
 *   · `ok`：已「加密」写入（占位密文，不代表明文可恢复）。
 */
function applyPlainSecret(plainSecret, seedText) {
  const plain = String(plainSecret === undefined || plainSecret === null ? '' : plainSecret)
  if (!plain) return { status: 'absent' }
  if (plain === NO_KEY_SENTINEL) return { status: 'rejected' }
  const placeholder = buildPlaceholderCredential(seedText)
  return { status: 'ok', cipher: placeholder.cipher, iv: placeholder.iv }
}

export const handlers = {
  accountqry: (body, ctx) => {
    const mode = String(body.mode || 'full')
    //★ 非管理员：**强制** ownerID = 登录 loginID（覆盖前端入参，前端传别人的 ownerID 亦无效）
    const scope = scopeOf(body)
    const query = scope.isManager ? body : { ...body, ownerID: scope.loginID }
    const list = filterList(query).map((item) => project(item, mode))
    const key = `${mode}|${body.platform || ''}|${body.healthStatus || ''}|${body.accountCode || ''}|${query.ownerID || ''}|${body.order || ''}`
    return ctx.paginate(list, body, 'accountqry', key)
  },

  accountadd: (body) => {
    // 必填口径对齐后端：accountCode/platform/accountName/subjectType/capability 缺失 → BA/CG
    if (!body.accountCode) return { __err: { code: 'BA', content: '账号幂等键(accountCode)为必填项' } }
    if (!body.platform) return { __err: { code: 'BA', content: '所属平台(platform)为必填项' } }
    if (!body.accountName) return { __err: { code: 'BA', content: '账号名称(accountName)为必填项' } }
    if (!body.subjectType) return { __err: { code: 'BA', content: '主体类型(subjectType)为必填项' } }
    if (!body.capability) return { __err: { code: 'BA', content: '能力(capability)为必填项' } }
    if (state.accounts.some((item) => item.accountCode === body.accountCode)) {
      return { __err: { code: 'CA', content: `账号幂等键 ${body.accountCode} 已存在` } }
    }
    // ★ R-30：明文 appSecret → 加密写入；无密钥（哨兵）→ F0 且**不 insert**（不进入 state）
    const secret = applyPlainSecret(body.appSecret, String(body.accountCode || ''))
    if (secret.status === 'rejected') return { __err: { code: 'F0', content: F0_MESSAGE } }
    //★ 归属隔离：非管理员**强制**写入本人归属（忽略前端 ownerID 入参）
    const scopeAdd = scopeOf(body)
    state.seq += 1
    const source = stripCredentialFields(body)
    // add 分支：空值也写入（`dataSet.get(field, "")`）
    const checkedAt = nowStr()
    const record = {
      recID: `AC${pad(state.seq, 6)}`,
      accountID: body.accountID || `ACC-${pad(state.seq, 3)}`,
      accountCode: body.accountCode,
      platform: body.platform,
      accountName: body.accountName,
      subjectType: body.subjectType,
      verifiedFlag: body.verifiedFlag === undefined ? '0' : String(body.verifiedFlag),
      capability: body.capability,
      appID: source.appID || '',
      appSecret: '',
      credentialRef: '',
      // ★ 凭据：仅在提供明文 appSecret 时写入占位密文；明文不落库、不回显
      credentialCipher: secret.status === 'ok' ? secret.cipher : '',
      credentialIV: secret.status === 'ok' ? secret.iv : '',
      healthStatus: 'UNKNOWN',
      expireYMDHMS: source.expireYMDHMS || '',
      quotaUsed: 0,
      quotaLimit: 10,
      autoPublishFlag: '0',
      lastCheckYMDHMS: '',
      lastUseYMDHMS: '',
      ownerID: scopeAdd.isManager ? (source.ownerID || '') : scopeAdd.loginID,
      label: source.label || '',
      memo: source.memo || '',
      regYMDHMS: checkedAt,
      modifyYMDHMS: checkedAt,
      operator: body.operator || '陈立恒'
    }
    state.accounts.unshift(record)
    return { data: record }
  },

  accountmodify: (body) => {
    const index = state.accounts.findIndex((item) => item.recID === body.recID || item.accountID === body.accountID)
    if (index < 0) return { __err: { code: 'BI', content: '账号记录标识无效' } }
    const current = state.accounts[index]
    //★ 归属隔离：非管理员改他人账号 → BG（与后端 `funcAccountModify` 同码；不区分「不存在」）
    const scopeMod = scopeOf(body)
    if (!scopeMod.isManager && String(current.ownerID || '') !== scopeMod.loginID) {
      return { __err: { code: 'BG', content: '您的权限不足' } }
    }
    // ★ R-30：无密钥（哨兵）→ **不 update**、直接 F0（错误码不被后续 BT/BA 覆盖）
    const secret = applyPlainSecret(body.appSecret, String(current.recID || ''))
    if (secret.status === 'rejected') return { __err: { code: 'F0', content: F0_MESSAGE } }
    const patch = stripCredentialFields(body)
    // 正式发布为红线项：不允许通过账号端点开启
    if (patch.autoPublishFlag === '1') {
      return { __err: { code: 'F6', content: '自动发布闸门未开启，该字段不可通过接口开启' } }
    }
    delete patch.autoPublishFlag
    // modify 分支：「与当前值不同且非空才写」→ 空串**无法清空**字段（与 R-22 同源）
    const writable = {}
    Object.keys(patch).forEach((key) => {
      //★ 归属隔离：非管理员不允许改归属（忽略前端 ownerID 入参；后端同口径）
      if (key === 'ownerID' && !scopeMod.isManager) return
      const next = patch[key]
      if (next === undefined || next === null || String(next) === '') return
      if (String(next) === String(current[key] === undefined || current[key] === null ? '' : current[key])) return
      writable[key] = next
    })
    // ★ 凭据列由服务端「加密」后写入（占位密文）；与业务字段的「非空且不同才写」无关，提供即覆盖。
    //   同时清空 `appSecret`（Mock 私有字段）：明文永不落库，记录里不留任何明文形态的字段值。
    if (secret.status === 'ok') {
      writable.credentialCipher = secret.cipher
      writable.credentialIV = secret.iv
      writable.appSecret = ''
    }
    state.accounts[index] = { ...current, ...writable, recID: current.recID, modifyYMDHMS: nowStr() }
    return { data: state.accounts[index] }
  },

  accountdel: (body) => {
    const index = state.accounts.findIndex((item) => item.recID === body.recID || item.accountID === body.accountID)
    // 硬删除：查不到记录 → CB（对齐后端 `funcAccountDel`）
    if (index < 0) return { __err: { code: 'CB', content: '无此账号记录' } }
    //★ 归属隔离：非管理员删他人账号 → BG（与后端同码；先判存在(CB)后判归属，顺序与后端一致）
    const scopeDel = scopeOf(body)
    if (!scopeDel.isManager && String(state.accounts[index].ownerID || '') !== scopeDel.loginID) {
      return { __err: { code: 'BG', content: '您的权限不足' } }
    }
    const [removed] = state.accounts.splice(index, 1)
    return { data: { success: '1', recID: removed.recID } }
  },

  accounthealth: (body) => {
    const action = String(body.action || '').toLowerCase()
    if (action && !VALID_ACTIONS.includes(action)) {
      return { __err: { code: 'C4', content: `action 取值需为 ${VALID_ACTIONS.join(' / ')} 或留空(仅汇总)` } }
    }
    const checkedAt = nowStr()
    //★ 归属隔离（方案甲）：非管理员的巡检明细与 healthSummary **同口径收窄**；
    //  管理员保持全量；不传 ownerID 的调用（定时/全量）行为不变。
    const scopeHealth = scopeOf(body)
    const scopeOwner = scopeHealth.isManager ? '' : scopeHealth.loginID
    // ★ action 为空 = 只汇总不巡检（后端事实）；check / refresh / probe 三者等价
    const checkResult = action
      ? runOnce({ accountID: body.accountID, platform: body.platform, ownerID: scopeOwner })
      : null
    const { summary, lower } = summarize(scopeOwner)
    const healthSummary = { total: summary.total, OK: summary.OK, EXPIRING: summary.EXPIRING, INVALID: summary.INVALID, UNKNOWN: summary.UNKNOWN }
    // ★ R-27：真实后端字段名为 `healthSummary`（大写键，含 total）；`summary`（小写键）保留为兼容副本
    const result = { action, checkYMDHMS: checkedAt, healthSummary, summary: lower }
    if (checkResult) {
      result.credentialCheck = checkResult
      result.checkedAt = checkResult.checkedAt || checkedAt
    } else {
      //★ 2026-09-23（与后端 `funcAccountHealth` 同口径）：不传 action = 只汇总、不巡检 →
      //  `checkedAt` 退化为**快照时点** = 本次范围内各账号 `lastCheckYMDHMS` 的最大值
      //  （= 最近一次真实巡检时间）；从未巡检 → 空串（前端显示「— 尚未巡检」，**不编造时间**）。
      //  ★ 同样按归属收窄，避免非管理员读到他人账号的巡检时间。
      const scopeList = scopeOwner
        ? state.accounts.filter((item) => String(item.ownerID || '') === scopeOwner)
        : state.accounts
      const stamps = scopeList
        .map((item) => String(item.lastCheckYMDHMS || '').trim())
        .filter(Boolean)
        .sort()
      result.checkedAt = stamps.length ? stamps[stamps.length - 1] : ''
    }
    return { data: result }
  }
}

export const mockAccounts = state.accounts
export default handlers
