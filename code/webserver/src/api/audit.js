/* ============================================================================
 * api 域：审计日志（ch_audit_log CRUD，§2.9.8）
 * ----------------------------------------------------------------------------
 * 页面使用点：P-12 审计日志（读 `auditlogqry`；前端约定「时间范围必填」）。
 * 日志为**只追加**语义：页面不开放开 / 改 / 删入口，此处仅为端点映射完整性保留。
 *
 * `auditlogqry` 服务端等值筛选（附录 B R-28 + R-32，`crudApi.py::funcAuditlogQry`）：
 *   `actor / action / result / source / targetType / targetID / ipAddr /
 *    beginYMDHMS / endYMDHMS / order` + 分页 `beginNum / endNum`。
 *   ★ 全部为**等值**匹配（数据层 `condList.append([x,"=",x])`，**无 keyword**）；
 *   ★ 时间条件作用在 `regYMDHMS`；`order:'desc'` 命中「其他 → ORDER BY recID DESC」（最新在前）；
 *   ★ 缺省 `limitNum=5000` → 前端**必须显式传 `beginNum` / `endNum`**（否则脱离分页意图）。
 *
 * ★ Step 16 越界授权（裁定 J-①）：`auditLogQry` 签名加第二个 `config` 形参（透传 axios 级配置），
 *   P-12 传 `{ silent: true }` 以**自行渲染错误态**（§2.5 第 5 条；`utils/http.js` 读
 *   `response.config.silent`，无法写在请求体）。写法与 `api/account.js` / `api/publish.js` 一致，
 *   向后兼容（既有调用方只传 params）。
 * ========================================================================== */
import { createService } from '@/utils/http'

const svc = createService()

/**
 * 审计日志查询。
 * @param {object} params `actor / action / result / source / targetType / targetID / ipAddr /
 *   beginYMDHMS / endYMDHMS / order / mode / beginNum / endNum`
 * @param {object} [config] axios 级配置（Step 16 追加）——P-12 传 `{ silent: true }`
 */
export const auditLogQry = (params, config) => svc.post('/auditlogqry', params, config)
export const auditLogAdd = (params) => svc.post('/auditlogadd', params)
export const auditLogModify = (params) => svc.post('/auditlogmodify', params)
export const auditLogDel = (params) => svc.post('/auditlogdel', params)
