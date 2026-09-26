/* ============================================================================
 * api 域：平台（ch_platform CRUD，§2.9.8）
 * ----------------------------------------------------------------------------
 * 页面使用点：P-05 能力矩阵（读 `platformqry`，免登录端点）、P-10 / P-13 只读展示。
 * 平台规格（titleMaxLen / coverSpec / imageMaxCount …）为**数据驱动**，前端不得硬编码副本。
 * ========================================================================== */
import { createService } from '@/utils/http'

const svc = createService()

/**
 * ★ Step 13 追加：透传 axios 级 `config`（向后兼容），支持 `{ silent: true }`
 *   —— P-09 合规校验页自行渲染错误态，不叠加全局 toast（§2.5 第 5 条）。
 */
export const platformQry = (params, config) => svc.post('/platformqry', params, config)
export const platformAdd = (params) => svc.post('/platformadd', params)
export const platformModify = (params) => svc.post('/platformmodify', params)
export const platformDel = (params) => svc.post('/platformdel', params)
