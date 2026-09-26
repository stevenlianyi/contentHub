/* ============================================================================
 * Mock · MCP 令牌域（ch_mcp_token CRUD，P-13 只读展示）
 * ----------------------------------------------------------------------------
 * ⚠️ 与 `src/api/mcp.js` 同步增补（11 域清单未含 MCP 域，见该文件说明）。
 *
 * ★ Step 17（裁定 I）入参对齐 —— 服务端筛选口径以 `main/subfunc/crudApi.py::funcMcptokenQry`
 *   （2026-09-22 手改，附录 B R-28）为准：
 *     可用筛选 = `tokenHash` / `tokenName` / `tokenScope` / `projectCode` / `order`（**全部等值**）
 *     + `recID`（生成器模板原有）+ `mode` / `beginNum` / `endNum` / `indexKey` / `forceFlashFlag`；
 *   · **删除旧入参** `keyword`（后端无模糊搜索）与 `tokenStatus`（状态由 `revokedYMDHMS` 推导，
 *     表内没有 `tokenStatus` 列，故后端也不存在该筛选条件）。
 *   · `order` 三态（`common/mysqlCommon.queryTableGeneral:290-295`）：`modify` →
 *     `ORDER BY modifyYMDHMS DESC`；`create` → `recID ASC`；其他 → `recID DESC`。
 *     缺省由调用方给定（P-13 传 `modify`）。
 *   · 与 R-28 同口径：**筛选条件必须进 `indexKey`**（不同筛选组合不能命中同一查询缓冲）。
 *
 * ★ 鉴权口径（务必写准确）：MCP 调用鉴权走**会话令牌（Redis session）+ 角色 / 工具级配置**
 *   （`ROLE_CMD_LIST` / `MCP_TOOL_LIST`，见 `main/subfunc/mcpApi.py` 与 `mcpapi/mcpPost.py`）；
 *   **没有任何鉴权路径去查本表** → `ch_mcp_token` 是**登记台账**。
 * ★ 本表**不存在令牌明文**（`tokenHash` COMMENT「不存明文」）→ Mock 也不再返回 `tokenValue`，
 *   页面亦不提供「复制 / 显示令牌」入口。
 * ★ add / modify / del 三个写处理器**本期无调用方**（P-13 只读）：保留它们仅为与后端 4 个 CMD
 *   一一对应，字段口径已同步为新列（不再出现 `tokenValue` / `tokenStatus` / `tokenID` / `remark`）。
 * ========================================================================== */
import { MCP_TOKENS } from './data/ops'
import { pad } from './data/util'

const state = { tokens: MCP_TOKENS.map((item) => ({ ...item })), seq: MCP_TOKENS.length }

function nowStr() {
  const d = new Date()
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
}

const str = (value) => (value === null || value === undefined ? '' : String(value))

/** order 三态排序（与 `common/mysqlCommon.py:290-295` 一致；recID 为字符串形态，按字典序比较） */
function sortTokens(list, order) {
  const rows = [...list]
  if (order === 'modify') {
    rows.sort((a, b) => str(b.modifyYMDHMS).localeCompare(str(a.modifyYMDHMS)))
  } else if (order === 'create') {
    rows.sort((a, b) => str(a.recID).localeCompare(str(b.recID)))
  } else {
    rows.sort((a, b) => str(b.recID).localeCompare(str(a.recID)))
  }
  return rows
}

export const handlers = {
  mcptokenqry: (body, ctx) => {
    const tokenHash = str(body.tokenHash).trim()
    const tokenName = str(body.tokenName).trim()
    const tokenScope = str(body.tokenScope).trim()
    const projectCode = str(body.projectCode).trim()
    const order = str(body.order).trim()

    let list = [...state.tokens]
    if (str(body.recID).trim()) list = list.filter((item) => str(item.recID) === str(body.recID).trim())
    if (tokenHash) list = list.filter((item) => item.tokenHash === tokenHash)
    if (tokenName) list = list.filter((item) => item.tokenName === tokenName)
    if (tokenScope) list = list.filter((item) => item.tokenScope === tokenScope)
    if (projectCode) list = list.filter((item) => item.projectCode === projectCode)

    // 筛选条件进 indexKey（R-28 同口径），避免不同组合共用同一查询缓冲
    const bufferKey = [tokenHash, tokenName, tokenScope, projectCode, order].join('|')
    return ctx.paginate(sortTokens(list, order), body, 'mcptokenqry', bufferKey)
  },

  /* ---- 以下三个写端点为「与后端 CMD 一一对应」保留，P-13 不调用 ---- */

  mcptokenadd: (body) => {
    if (!str(body.tokenName)) return { __err: { code: 'C4', content: '令牌名称为必填项' } }
    if (!str(body.tokenHash)) return { __err: { code: 'C4', content: 'tokenHash（sha256，不存明文）为必填项' } }
    if (state.tokens.some((item) => item.tokenHash === body.tokenHash)) {
      return { __err: { code: 'CA', content: '该 tokenHash 已登记' } }
    }
    state.seq += 1
    const now = nowStr()
    const record = {
      recID: `MT${pad(state.seq, 6)}`,
      tokenHash: str(body.tokenHash),
      tokenName: str(body.tokenName),
      tokenScope: str(body.tokenScope) || 'read',
      projectCode: str(body.projectCode),
      transport: str(body.transport) || 'sse',
      lastUseYMDHMS: '',
      useCount: 0,
      revokedYMDHMS: '',
      ownerID: str(body.ownerID),
      label: str(body.label),
      memo: str(body.memo),
      regID: str(body.ownerID),
      regYMDHMS: now,
      modifyID: str(body.ownerID),
      modifyYMDHMS: now,
      delFlag: '0'
    }
    state.tokens.unshift(record)
    return { data: record }
  },

  mcptokenmodify: (body) => {
    const index = state.tokens.findIndex((item) => str(item.recID) === str(body.recID))
    if (index < 0) return { __err: { code: 'BI', content: '令牌记录标识无效' } }
    const current = state.tokens[index]
    // recID / regYMDHMS 为登记标识与创建时刻，不允许被入参改写
    state.tokens[index] = {
      ...current,
      ...body,
      recID: current.recID,
      regYMDHMS: current.regYMDHMS,
      modifyYMDHMS: nowStr()
    }
    return { data: state.tokens[index] }
  },

  mcptokendel: (body) => {
    const index = state.tokens.findIndex((item) => str(item.recID) === str(body.recID))
    if (index < 0) return { __err: { code: 'BI', content: '令牌记录标识无效' } }
    const [removed] = state.tokens.splice(index, 1)
    return { data: { success: '1', recID: removed.recID } }
  }
}

export const mockMcpTokens = state.tokens
export default handlers
