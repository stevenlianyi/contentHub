/* ============================================================================
 * api 域：MCP 令牌（ch_mcp_token CRUD，§2.9.8）
 * ----------------------------------------------------------------------------
 * ⚠️ 本文件是 11 个域文件清单之外的**必要增补**（已登记）：2.10 的 P-13 设置页需要
 *    `mcptokenqry`，而 11 文件清单（user/topic/asset/layout/platform/render/artifact/
 *    publish/compliance/account/audit）未含 MCP 域，若强行塞入其它域会造成语义错位。
 *
 * 页面使用点：P-13 系统设置（**只读**展示令牌登记台账）。
 * ★ 鉴权口径（Step 17 修正，务必写准确）：MCP 调用鉴权使用**会话令牌（Redis session）**
 *   —— `main/subfunc/mcpApi.py::_resolveIdentity` 与 `mcpapi/mcpPost.py::CHTokenVerifier`
 *   都走 `comDB.getSessionInfo(token)` —— 再叠加**角色 / 工具级配置**
 *   （`ROLE_CMD_LIST` / `MCP_TOOL_LIST`）；**没有任何鉴权路径去查 `ch_mcp_token`**
 *   → 该表是**登记台账**，不参与鉴权。
 * ★ 因此本域**只有** `mcpTokenQry` 会被调用；add / modify / del 三个写方法本期**无调用方**
 *   （P-13 不提供任何编辑入口）。保留导出仅为与后端 4 个 CMD 一一对应，便于后续按需接入。
 *   ⚠️ 真实表 `tokenHash CHAR(64)` COMMENT 明确「不存明文」→ 不存在可复制的令牌明文。
 *
 * `mcpinvoke`（§2.9.7）本期**不提供**：计划明确「前端本期不做独立页面」，故不建映射。
 * ========================================================================== */
import { createService } from '@/utils/http'

const svc = createService()

/**
 * ★ Step 17 追加：透传 axios 级 `config`（向后兼容），支持 `{ silent: true }`
 *   —— P-13 自行渲染错误态 / R-24 空响应态，不叠加全局 toast（§2.5 第 5 条）。
 *   与 `api/platform.js::platformQry`（Step 13）保持同一签名口径。
 */
export const mcpTokenQry = (params, config) => svc.post('/mcptokenqry', params, config)
export const mcpTokenAdd = (params) => svc.post('/mcptokenadd', params)
export const mcpTokenModify = (params) => svc.post('/mcptokenmodify', params)
export const mcpTokenDel = (params) => svc.post('/mcptokendel', params)
