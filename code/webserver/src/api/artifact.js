/* ============================================================================
 * api 域：产物（ch_artifact CRUD + artifactpack，§2.9.3 / §2.9.8）
 * ----------------------------------------------------------------------------
 * 页面使用点：P-07 产物台账、P-03 Tab4、P-10 素材包导出。
 * ★ `artifactpack` 在 assetApi 域登记，但按**页面归属**（P-07 / P-10）收在本文件，
 *   与 Step 3 Mock 清单的分组保持一致（已在交付说明登记该归组口径）。
 * `artifactqry` 为**免登录端点**（§2.9.8）。
 *
 * ★ Step 14 追加：`artifactQry` / `artifactPack` 透传第二个参数 `config`（axios 级配置，
 *   向后兼容——既有调用方只传 params），支持 `{ silent: true }`。
 *   依据：§2.5 第 5 条；P-10 的投递前置产物取数与素材包导出需**自行处理阻塞原因/合规明细**
 *   （`packaged==='0'` 时页面呈现阻断清单，且**不得触发下载**），不叠加全局 toast。
 * ========================================================================== */
import { createService } from '@/utils/http'

const svc = createService()

/**
 * 产物查询（服务端筛选：`recID / jobID / topicID / kind / platform / artifactStatus / order`）。
 * @param {object} [config] axios 级配置（Step 14 追加）——P-10 传 `{ silent: true }`
 */
export const artifactQry = (params, config) => svc.post('/artifactqry', params, config)
export const artifactAdd = (params) => svc.post('/artifactadd', params)
export const artifactModify = (params) => svc.post('/artifactmodify', params)
export const artifactDel = (params) => svc.post('/artifactdel', params)

/**
 * 素材包 ZIP 导出（★ 只导出不投递：全程不产生任何投递/发布动作，故**无需二次确认**）。
 * 未过合规校验 → 非 `B0` + `data.packaged="0"` + `data.compliance` 明细（前端**不得当成功**）。
 * @param {object} [config] axios 级配置（Step 14 追加）——P-10 传 `{ silent: true }`
 */
export const artifactPack = (params, config) => svc.post('/artifactpack', params, config)
