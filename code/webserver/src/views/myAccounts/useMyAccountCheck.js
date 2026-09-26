/* ============================================================================
 * useMyAccountCheck · 「第三方账号管理」巡检 / 健康汇总 / 到期预警编排
 * ----------------------------------------------------------------------------
 * 从 `views/MyAccounts.vue` 拆出（单文件 ≤600 行硬约束，与 `views/compliance/useComplianceCheck.js`
 * / `views/assets/useAssetList.js` 同范式）——**只承载行为，不承载展示**。
 *
 * 【后端事实（一律服从源码）】
 *   · 触发：`accounthealth({ action:'check' })`；`check` / `refresh` / `probe` 三者完全等价
 *     （`subfunc/accountApi.py` 同一 `runOnce` 调用）；`action` 为空 = **只汇总不巡检**。
 *   · ★ 归属收窄（方案甲）：非管理员由后端按登录 loginID 强制 `ownerID = loginID` ——
 *     `credentialCheck.items[]` 与 `healthSummary` **同口径收窄**；管理员保持全量。
 *     故本层**刻意不传 `ownerID`**（传了也不可信、无必要）；行内巡检只传本人 `recID`。
 *   · 出参为 copy 域（P-ENV-01）：业务字段在 `data` 内（`healthSummary` / `credentialCheck`）。
 *   · `credentialCheck` 字段：`{ total, checked, ok, expiring, invalid, unknown, skipped, degraded,
 *     warnDays, items[], alertSummary, checkedAt }`；`skipped = -1`（锁未取到）与 `degraded = 1`
 *     （Redis 降级）**均非错误态**。
 *
 * 【约束】
 *   · 鉴权不得使用 `hasPermission()`（恒 false）；本层只接收 `isManager` 判定结果用于**文案**，
 *     真正的隔离由服务端强制。
 *   · 密文列（`credentialCipher` / `credentialIV`）与明文 `appSecret` 一律不进入本层。
 * ========================================================================== */
import { computed, ref } from 'vue'
import { toast } from 'vue3-toastify'
import { accountHealth } from '@/api/account'
import { normalizeHealth } from '@/views/dashboard/useDashboardData'
import { parseDateTime } from '@/utils/common'

/** 到期阈值兜底（对齐后端 `DEFAULT_EXPIRE_WARN_DAYS`；仅在响应未回传 warnDays 时使用） */
const FALLBACK_WARN_DAYS = 7

/**
 * @param {object} deps
 * @param {import('vue').ComputedRef<boolean>} deps.isManager 管理员判定（仅用于文案与「是否全量」说明）
 * @param {import('vue').ComputedRef<string>}  deps.loginID  当前登录 loginID（仅用于文案展示）
 * @param {import('vue').Ref<Array>}           deps.rows     当前页行（行内巡检后原地更新徽章）
 * @param {{resetList:Function, loadList:Function}} deps.reload 列表刷新入口
 */
export function useMyAccountCheck({ isManager, loginID, rows, reload }) {
  const healthSummary = ref(null)
  const checkResult = ref(null)
  const checking = ref(false)
  const checkError = ref('')
  const checkNotice = ref('')
  /** 本轮巡检的收窄目标（空串 = 按登录账号 / 超管全量）；仅用于面板补充说明 */
  const checkScope = ref('')

  /** 只汇总不巡检（action 留空）→ 用于首屏与删除后刷新健康数字（后端同样按归属收窄） */
  async function loadSummary() {
    try {
      const res = await accountHealth({}, { silent: true })
      const data = res?.data || {}
      healthSummary.value = normalizeHealth(data.healthSummary || data.summary || res?.healthSummary)
    } catch (e) {
      console.error('[MyAccounts] 健康汇总读取失败', e)
    }
  }

  /**
   * 用单账号巡检结论更新该行：**只认 `items[]` 中 `accountID` 命中的那一条**（不按全量
   * `healthSummary` 推断）；`lastCheckYMDHMS` 仅在后端确实回写时同步（跳过项不改「最近检查」）。
   * @returns {boolean} 是否命中并已更新
   */
  function applyRowCheckResult(recID, check) {
    const items = Array.isArray(check?.items) ? check.items : []
    const hit = items.find((item) => String(item?.accountID) === String(recID))
    if (!hit) return false
    const row = rows.value.find((item) => String(item.recID) === String(recID))
    if (row) {
      row.healthStatus = String(hit.healthStatus || 'UNKNOWN')
      if (!String(hit.skipReason || '')) row.lastCheckYMDHMS = String(check.checkedAt || '')
    }
    return true
  }

  /**
   * 触发巡检：只用 `check`（`check` / `refresh` / `probe` 后端完全等价）。
   * ★ **不传 `ownerID`**：非管理员的收窄由后端按登录 loginID 强制注入。
   * @param {string} [recID] 收窄单账号（本页只可能是本人账号的 recID；后端仍会叠加归属条件）
   */
  async function runCheck(recID) {
    if (checking.value) return
    const targetRecID = String(recID || '')
    checking.value = true
    checkError.value = ''
    checkNotice.value = ''
    try {
      const params = { action: 'check' }
      if (targetRecID) params.accountID = targetRecID
      const res = await accountHealth(params, { silent: true })
      const data = res?.data || {}
      const check = data.credentialCheck || null
      checkResult.value = check
      checkScope.value = targetRecID
      healthSummary.value = normalizeHealth(data.healthSummary || data.summary || res?.healthSummary)
      if (!check) {
        checkNotice.value = '本次响应未包含 credentialCheck 明细（后端 action 为空时只汇总不巡检）。'
        return
      }
      if (!targetRecID) {
        // 按范围巡检：回写 healthStatus / lastCheckYMDHMS → 刷新列表让徽章与「最近检查」同步
        await reload.resetList()
        return
      }
      // ★ 单账号巡检（保存凭据后的闭环）：只用 items[] 结论更新该行
      const updated = applyRowCheckResult(targetRecID, check)
      if (Number(check.skipped) === -1) toast.info('已有巡检在执行，本轮跳过（未改写任何账号）')
      else if (Number(check.degraded) === 1) toast.info('巡检锁 / 计数已降级（Redis 不可用），结果可能不完整')
      else if (!updated) toast.warning('本轮未返回该账号的明细，未更新行徽章')
      else toast.success('已按最新探活结论更新该账号徽章与「最近检查」时间')
      await reload.loadList()
    } catch (e) {
      checkError.value = e?.MSG?.content || '凭据巡检失败，请稍后重试'
      console.error('[MyAccounts] 凭据巡检失败', e)
    } finally {
      checking.value = false
    }
  }

  /** 面板补充说明：明确本轮收窄范围（单账号 / 本人账号 / 超管全量），避免误读汇总口径 */
  const checkScopeNote = computed(() => {
    if (checkScope.value) {
      return `本轮为单账号巡检（accountID=${checkScope.value}）：下方统计与明细仅含该账号。`
    }
    return isManager.value
      ? '本轮为超管视角巡检：credentialCheck 明细与 healthSummary 均为全量。'
      : `本轮巡检按登录账号收窄（后端 ownerID=${loginID.value || '当前登录账号'}）：只探活并回写本人账号；`
        + 'healthSummary 同为本人范围（非全站）。'
  })

  /* ------------------------------ 到期预警（阈值取后端 warnDays） ------------------------------ */
  const warnDays = computed(() => {
    const value = Number(checkResult.value?.warnDays)
    return Number.isFinite(value) && value > 0 ? value : FALLBACK_WARN_DAYS
  })

  /** 剩余时间：空/非法 `expireYMDHMS` → null（长期有效，**不得显示为已过期**） */
  function expireRemainMs(expireYMDHMS) {
    const raw = String(expireYMDHMS || '').trim()
    if (!raw || !/^\d{8,14}$/.test(raw)) return null
    const date = parseDateTime(raw)
    return date ? date.getTime() - Date.now() : null
  }

  /** 行内到期提示：已过期（危险）/ N 天后到期（预警）/ 无提示（长期有效或未临期） */
  function expireHint(row) {
    const remain = expireRemainMs(row.expireYMDHMS)
    if (remain === null) return null
    if (remain <= 0) return { text: '已过期', class: 'text-ch-danger' }
    const days = Math.ceil(remain / 86400000)
    if (days <= warnDays.value) return { text: `${days} 天后到期`, class: 'text-ch-warning' }
    return null
  }

  return {
    healthSummary, checkResult, checking, checkError, checkNotice, checkScopeNote,
    warnDays, expireHint, loadSummary, runCheck
  }
}
