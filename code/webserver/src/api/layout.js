/* ============================================================================
 * api 域：版式（ch_layout CRUD，§2.9.8）
 * ----------------------------------------------------------------------------
 * 页面使用点：P-05 版式与平台（读 `layoutqry`，免登录端点）。
 * 版式 × 平台可选性以前端字典 `config/chOptions.js` 的 `LAYOUT_PLATFORM_MATRIX` 为准（§2.7）。
 * ========================================================================== */
import { createService } from '@/utils/http'

const svc = createService()

/**
 * ★ Step 13 追加：透传 axios 级 `config`（向后兼容），支持 `{ silent: true }`
 *   —— P-09 合规校验页自行渲染错误态，不叠加全局 toast（§2.5 第 5 条）。
 */
export const layoutQry = (params, config) => svc.post('/layoutqry', params, config)
export const layoutAdd = (params) => svc.post('/layoutadd', params)
export const layoutModify = (params) => svc.post('/layoutmodify', params)
export const layoutDel = (params) => svc.post('/layoutdel', params)
