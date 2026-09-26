/* ============================================================================
 * api 域：渲染（topicrender + ch_render_job CRUD，§2.9.4 / §2.9.8）
 * ----------------------------------------------------------------------------
 * 页面使用点：P-05 发起渲染、P-06 渲染任务列表（重试 / 取消）、P-08 预览。
 *
 * `topicrender` 出参：`content`（HTML 或片段）+ `meta{layoutCode,layoutType,platform,outputKind,…}`，
 * PNG 类平台另含 `products[]`（seqNo/kind/fileID/fileUrl/width/height/sizeBytes/sha256/isCover）。
 * ========================================================================== */
import { createService } from '@/utils/http'

const svc = createService()

/**
 * ★ Step 11 追加：全部函数透传第二个参数 `config`（axios 级配置，向后兼容——既有调用方只传 params）。
 *   依据：§2.5 第 5 条「页面级拦截开关 `config.silent = true`」+ 裁定 E「轮询请求必须静默，
 *   失败不得每 5s 弹一次全局 toast」。`utils/http.js` 读的是 `response.config.silent`，
 *   故该开关只能经 axios config 传递，无法写在请求体里。
 */

/** 渲染：renderMode `sync`（缺省，同步等待）/ `job`（建任务后立即返回 jobCode + PENDING） */
export const topicRender = (params, config) => svc.post('/topicrender', params, config)

/** 渲染任务台账 */
export const renderJobQry = (params, config) => svc.post('/renderjobqry', params, config)
export const renderJobAdd = (params, config) => svc.post('/renderjobadd', params, config)
export const renderJobModify = (params, config) => svc.post('/renderjobmodify', params, config)
export const renderJobDel = (params, config) => svc.post('/renderjobdel', params, config)
