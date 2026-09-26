/* ============================================================================
 * api 域：合规（publishcheck，§2.9.6）
 * ----------------------------------------------------------------------------
 * 页面使用点：P-09 合规校验（以及 P-03 / P-10 的投递前置校验）。
 *
 * 出参（P-ENV-01 整形后业务字段在 `data` 内；`publishcheck` 属 move 类）：
 *   `data = { passed, issueCount, errorCount, warningCount, issues[], platformCode, layoutType,
 *             assetCount, sensitiveHitCount, rateLimit{...}, topicID, topicCode, layoutCode,
 *             platform, accountID, checkedAt }`；
 *   每条 `issue = { field, location, level(ERROR|WARN), errCode, message, source, offsetStart?, offsetEnd?, matchedWord? }`；
 *   `passed === '1'` 仅当无 ERROR（WARN 不阻断）。
 * ★ 调用方通常传 `{ silent: true }` 自行渲染错误清单（§2.5 第 5 条；该开关是 **axios config**，
 *   不能写进请求体）。
 * ★ `publishcheck` **不在** 2.9.8 的免登录清单内 → 请求必须带 `sessionID`（由 utils/http.js 注入）。
 * ========================================================================== */
import { createService } from '@/utils/http'

const svc = createService()

/**
 * 发布前合规校验。
 * @param {object} params `topicID | recID | topicCode`（三选一）+ 可选 `platform` / `layoutCode` /
 *   `layoutType` / `sensitiveWords[]` / `products[]` / `rateLimitCount` / `rateLimitWindow`
 * @param {object} [config] axios 级配置（Step 13 追加，向后兼容：既有调用方只传 params）——
 *   P-09 一律传 `{ silent: true }`，由页面自行渲染问题清单，避免全局 toast 叠加。
 */
export const publishCheck = (params, config) => svc.post('/publishcheck', params, config)
