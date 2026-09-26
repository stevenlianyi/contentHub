/* ============================================================================
 * api 域：投递（publishpush + ch_publish_record CRUD，§2.9.5 / §2.9.8）
 * ----------------------------------------------------------------------------
 * 页面使用点：P-10 投递 / 发布记录、P-03 Tab5。
 *
 * `publishpush` 关键约定：
 *   - `platform` 仅 `wechat_mp` 可投递，`xiaohongshu` / `generic` → C7（★ 无任何小红书自动发布入口）；
 *   - 二次确认两步：首次缺 `confirmFlag` → F4 并回显 `idempotencyKey` / `confirmToken`（服务端下发，
 *     前端**禁止自行构造**幂等键：形态 `{artifactID}:{accountID}:{uuid4}`）；
 *   - ★ 永不传 `autoPublish` / `autoPublishConfirm`（三重闸门默认关，UI 无任何自动群发开关）；
 *   - `action` = `push`（缺省）/ `revoke`（撤销窗内软删 `delFlag='1'`）。
 *
 * ★ Step 14 追加（与 Step 13 对 api/topic.js 的处理同源）：`publishPush` / `publishRecordQry` 透传第二个
 *   参数 `config`（axios 级配置，向后兼容——既有调用方只传 params）。
 *   依据：§2.5 第 5 条「页面级拦截开关 config.silent = true」；P-10 的两步确认与撤销需要**自行处理
 *   `F4` / `F5` / 合规侧 errCode**（不叠加全局 toast），该开关只能经 axios config 传递
 *   （utils/http.js 读的是 `response.config.silent`），无法写在请求体。
 * ========================================================================== */
import { createService } from '@/utils/http'

const svc = createService()

/**
 * 投递 / 撤销（同一端点，`action:'revoke'` 走撤销分支）。
 * @param {object} params `platform / topicID / layoutCode / artifactID / accountID / idempotencyKey /
 *   confirmFlag / confirmToken / action`
 * @param {object} [config] axios 级配置（Step 14 追加）——P-10 一律传 `{ silent: true }`
 */
export const publishPush = (params, config) => svc.post('/publishpush', params, config)

/**
 * 发布记录台账（服务端筛选：`idempotencyKey / artifactID / topicID / platform / success /
 * beginYMDHMS / endYMDHMS / order`，附录 B R-28；★ 时间范围作用于 `pushedYMDHMS`）。
 * @param {object} [config] axios 级配置（Step 14 追加）
 */
export const publishRecordQry = (params, config) => svc.post('/publishrecordqry', params, config)
export const publishRecordAdd = (params) => svc.post('/publishrecordadd', params)
export const publishRecordModify = (params) => svc.post('/publishrecordmodify', params)
export const publishRecordDel = (params) => svc.post('/publishrecorddel', params)
