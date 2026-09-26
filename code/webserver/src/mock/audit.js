/* ============================================================================
 * Mock · 审计域（auditlogqry 服务端等值筛选 + 时间范围必填 + 只追加台账）
 * ----------------------------------------------------------------------------
 * ★ Step 16（P-12）**整体重写为与真实后端同构**（裁定 I）：入参口径对齐
 *   `main/subfunc/crudApi.py::funcAuditlogQry`（2026-09-22 手改，附录 B **R-28** + **R-32**）
 *   与 `common/mysqlCommon.py::query_ch_audit_log:539-560`：
 *
 *   入参：`actor / action / result / source / targetType / targetID / ipAddr /
 *          beginYMDHMS / endYMDHMS / order` + 分页 `beginNum / endNum`
 *         （★ 已删除旧口径的 `beginDate / endDate / operator / cmd / keyword`）。
 *   ★ **全部为等值匹配**（真实数据层 `condList.append([x, "=", x])`，**无 keyword / 模糊匹配**），
 *     Mock 侧同样只做 `===`，**不做前缀/包含匹配** —— 否则「Mock 通过、真实后端不筛」。
 *   ★ 排序（`mysqlCommon.py:290-295` 通用实现）三态：
 *     `'create'` → `ORDER BY recID ASC`；**其他值（含 `'desc'`）→ `ORDER BY recID DESC`**。
 *   ★ 时间条件作用在 **`regYMDHMS`**；`delFlag` 缺省 `""` = 不过滤（追加写语义）。
 *
 *   ⚠️ **Mock 与真实后端的唯一差异（必须登记）**：真实 `auditlogqry` **不强制**时间范围
 *   （缺省 `limitNum=5000` 只是大表防护，返回 `B0`）；Mock **强制**要求 `beginYMDHMS` / `endYMDHMS`，
 *   缺失返回 `C4`（必填缺失）。理由：让前端「时间范围必填」规则在**无后端**时可被验证。
 *   → 该差异不改变页面行为（页面本就不允许在缺时间范围时发请求）。
 *
 *   ★ 失败样例：缺时间范围 → `C4`；14 位格式非法 → `C0`；起止倒置 → `C0`。
 *   ★ 审计为**只追加**语义：页面不开放改 / 删入口，此处映射仅为端点完整性保留
 *     （`auditlogmodify` 只允许补 `memo`，`auditlogdel` 一律拒绝）。
 * ========================================================================== */
import { AUDIT_LOGS } from './data/ops'
import { pad } from './data/util'

const state = { logs: AUDIT_LOGS.map((item) => ({ ...item })), seq: AUDIT_LOGS[0]?.recID || AUDIT_LOGS.length }

function nowStr() {
  const d = new Date()
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
}

/** 归一化为 14 位 `YYYYMMDDHHMMSS`（`2026-09-22T10:00` / `20260922` / `20260922100000` 均可） */
function normalizeYMDHMS(value, endOfDay = false) {
  const text = String(value || '').replace(/[-/:T\s]/g, '').trim()
  if (/^\d{8}$/.test(text)) return `${text}${endOfDay ? '235959' : '000000'}`
  if (/^\d{14}$/.test(text)) return text
  return ''
}

/** 等值条件（空值 = 不筛；与数据层「空值自动跳过条件」一致） */
const eq = (value) => String(value === null || value === undefined ? '' : value).trim()

export const handlers = {
  auditlogqry: (body, ctx) => {
    const begin = normalizeYMDHMS(body.beginYMDHMS)
    const end = normalizeYMDHMS(body.endYMDHMS, true)
    // ★ Mock 强制时间范围（真实后端不强制，见文件头「Mock 与真实后端的唯一差异」）
    if (!begin || !end) {
      return {
        __err: {
          code: 'C4',
          content: '查询审计日志必须提供时间范围（beginYMDHMS / endYMDHMS，14 位 YYYYMMDDHHMMSS）'
        }
      }
    }
    if (begin > end) return { __err: { code: 'C0', content: '起始时间不能晚于结束时间' } }

    const actor = eq(body.actor)
    const action = eq(body.action)
    const result = eq(body.result)
    const source = eq(body.source)
    const targetType = eq(body.targetType)
    const targetID = eq(body.targetID)
    const ipAddr = eq(body.ipAddr)
    const recID = eq(body.recID)
    const delFlag = eq(body.delFlag)
    // ★ 缺省回落 `'create'`：与接入层一致（`crudApi.py:3990 / :4005` 的 `order if order else "create"`）
    const order = eq(body.order).toLowerCase() || 'create'

    const list = state.logs.filter((item) => {
      // 时间条件作用在 regYMDHMS（创建时间；`mysqlCommon.py:556-557`）
      if (!(item.regYMDHMS >= begin && item.regYMDHMS <= end)) return false
      // ★ 一律等值匹配（无 keyword / 无模糊匹配）
      if (actor && eq(item.actor) !== actor) return false
      if (action && eq(item.action) !== action) return false
      if (result && eq(item.result) !== result) return false
      if (source && eq(item.source) !== source) return false
      if (targetType && eq(item.targetType) !== targetType) return false
      if (targetID && eq(item.targetID) !== targetID) return false
      if (ipAddr && eq(item.ipAddr) !== ipAddr) return false
      if (recID && eq(item.recID) !== recID) return false
      if (delFlag && eq(item.delFlag) !== delFlag) return false
      return true
    })

    /**
     * 排序三态（`mysqlCommon.py:290-295` 的通用实现）：
     *   `'modify'` → `ORDER BY modifyYMDHMS DESC`（★ 审计行该列**基本为空** → 顺序不确定，
     *     故前端固定传 `'desc'`，禁止传 `'modify'`）；`'create'` → `recID ASC`；其他（含 `'desc'`）
     *     → `recID DESC`。Mock 侧对 `'modify'` 不单独实现（无该列语义），统一落到「其他」分支。
     */
    const sorted = [...list].sort((a, b) =>
      order === 'create' ? Number(a.recID) - Number(b.recID) : Number(b.recID) - Number(a.recID)
    )

    return ctx.paginate(
      sorted,
      body,
      'auditlogqry',
      `${actor}|${action}|${result}|${source}|${targetType}|${targetID}|${ipAddr}|${begin}|${end}|${order}`
    )
  },

  auditlogadd: (body) => {
    if (!body.action) return { __err: { code: 'C4', content: 'action 为必填项' } }
    state.seq += 1
    const record = {
      recID: state.seq, // ★ 数字自增
      actor: body.actor || '',
      source: ['web', 'api', 'mcp'].includes(body.source) ? body.source : 'web',
      action: body.action,
      targetType: body.targetType || '',
      targetID: body.targetID || '',
      payloadDigest: body.payloadDigest || '',
      result: body.result === 'FAIL' ? 'FAIL' : 'OK',
      errMsg: body.errMsg || '',
      costMs: body.costMs || 0,
      ipAddr: body.ipAddr || '',
      label: body.label || '',
      memo: body.memo || '',
      regID: body.actor || '',
      regYMDHMS: nowStr(),
      modifyID: '',
      modifyYMDHMS: '',
      delFlag: '0'
    }
    state.logs.unshift(record)
    return { data: record }
  },

  auditlogmodify: (body) => {
    const index = state.logs.findIndex((item) => String(item.recID) === String(body.recID))
    if (index < 0) return { __err: { code: 'BI', content: '日志记录标识无效' } }
    // 只追加语义：仅允许补充 memo（真实表其余列不提供修改入口）
    state.logs[index] = { ...state.logs[index], memo: body.memo ?? state.logs[index].memo }
    return { data: state.logs[index] }
  },

  auditlogdel: () => {
    // 只追加语义：拒绝物理删除（真实后端亦保留，归档走 schedule/archive.py）
    return { __err: { code: 'BT', content: '审计日志为只追加记录，不可删除' } }
  }
}

/** 供页面 / 自测读取当前台账（只读快照） */
export const mockAuditLogs = state.logs
export default handlers
