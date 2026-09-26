/* ============================================================================
 * api 域：主题（processor/topicService 的 8 个 CMD，§2.9.2）
 * ----------------------------------------------------------------------------
 * 页面使用点：P-01 / P-02 / P-03 / P-08 / P-09 / P-10。
 *
 * ★ Step 13 追加（与 Step 11 对 api/render.js 的处理同源）：`topicQry` / `topicModify` 透传
 *   第二个参数 `config`（axios 级配置，向后兼容——既有调用方只传 params）。
 *   依据：§2.5 第 5 条「页面级拦截开关 config.silent = true」；P-09 合规校验页要求
 *   **本页请求一律 silent**（自行渲染问题清单/错误态，不叠加全局 toast）。
 *   该开关只能经 axios config 传递（utils/http.js 读的是 `response.config.silent`），无法写在请求体。
 * ========================================================================== */
import { createService } from '@/utils/http'

const svc = createService()

/** 主题列表 / 详情：支持 recID · topicCode · searchOption · beginNum/endNum · forceFlashFlag */
export const topicQry = (params, config) => svc.post('/topicqry', params, config)
export const topicAdd = (params) => svc.post('/topicadd', params)
export const topicModify = (params, config) => svc.post('/topicmodify', params, config)
export const topicDel = (params) => svc.post('/topicdel', params)

/** 版本快照（P-03 版本抽屉；按 topicID 取列表） */
export const topicVersionQry = (params) => svc.post('/topicversionqry', params)
export const topicVersionAdd = (params) => svc.post('/topicversionadd', params)
export const topicVersionModify = (params) => svc.post('/topicversionmodify', params)
export const topicVersionDel = (params) => svc.post('/topicversiondel', params)
