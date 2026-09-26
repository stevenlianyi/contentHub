/* ============================================================================
 * api 域：平台账号（ch_account CRUD + accounthealth，§2.9.1 / §2.9.8）
 * ----------------------------------------------------------------------------
 * 页面使用点：P-11 账号管理（读写）、P-01 工作台健康汇总、P-10 投递选号（只读）。
 *
 * `accounthealth`：平台凭据健康汇总；`action ∈ {check, refresh, probe}` 触发巡检。
 *   ★ 后端事实（`subfunc/accountApi.py:806-851`）：三个 action **完全等价**（同一 `runOnce` 调用）；
 *     `action` 为空时**只汇总、不巡检**（出参无 `credentialCheck`）。出参为 **copy 域**
 *     （P-ENV-01）：顶层保留 + `data` 副本，业务字段（`healthSummary` / `credentialCheck` /
 *     `checkedAt`）在 `data` 内；`healthSummary` 的状态计数键为**大写**
 *     `OK / EXPIRING / INVALID / UNKNOWN`（含 `total`）。
 *
 * `healthStatus` 权威取值 `OK / EXPIRING / INVALID / UNKNOWN`（§2.6；字典见 config/chOptions.js）。
 *
 * ★ 凭据安全（P-11 裁定 A/B）：
 *   · `accountqry` 必须显式传 `mode:'full'`（short 列清单不含 `expireYMDHMS`/`lastCheckYMDHMS`/`appID`），
 *     但调用方**必须做字段白名单映射**，丢弃 `credentialCipher`/`credentialIV` 等密文列；
 *   · 本层**不提供**任何「明文 appSecret → 加密写入」的调用：后端 `funcAccountAdd`/`funcAccountModify`
 *     把 `credentialCipher`/`credentialIV` 原样落库、不做加密，写入即「明文落库 + 后续解密失败 F0」。
 *     故 P-11 的凭据区只读（禁用入口），见 `views/accounts/AccountEditDialog.vue` 文件头 P0 说明。
 *
 * ★ 本步越界授权（裁定 I-①）：五个方法签名加 `config` 形参（透传 axios 级配置，如 `{ silent: true }`），
 *   否则 P-11 巡检面板无法自行渲染错误态（§2.5 第 5 条）。写法与 `api/platform.js` 一致，向后兼容。
 * ========================================================================== */
import { createService } from '@/utils/http'

const svc = createService()

export const accountQry = (params, config) => svc.post('/accountqry', params, config)
export const accountAdd = (params, config) => svc.post('/accountadd', params, config)
export const accountModify = (params, config) => svc.post('/accountmodify', params, config)
export const accountDel = (params, config) => svc.post('/accountdel', params, config)

/** 凭据健康汇总 / 巡检触发 */
export const accountHealth = (params, config) => svc.post('/accounthealth', params, config)
