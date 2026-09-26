/* ============================================================================
 * useDashboardData · 工作台聚合取数（Step 5 · P-01）
 * ----------------------------------------------------------------------------
 * 取数（裁定 B）：`Promise.all` **并发 4 个**请求（accounthealth 亦并发，不串行）：
 *   · topicqry      beginNum 0 / endNum 200
 *   · renderjobqry  beginNum 0 / endNum 200
 *   · artifactqry   beginNum 0 / endNum 50
 *   · accounthealth **不传 action** → 后端只汇总、**不巡检**
 * 聚合在前端完成（计划「指标卡口径」表），**不伪造 total、不做本地假筛选**。
 *
 * ★ 2026-09-23 变更（巡检改为手工触发，本次仅改前端触发面）：
 *   本文件**不再在首屏触发凭据探活**（原为 `accountHealth({ action:'check' })`）——
 *   避免每次打开工作台都对全量账号发起**真实微信接口调用**。巡检改由「第三方账号管理」
 *   （`/my-accounts`，`views/myAccounts/useMyAccountCheck.js`）手工点击触发。
 *   ★ 代价（需登记）：本页「凭据健康」退化为**最近一次巡检的快照**，不再实时。
 *
 * ★ 近似统计的局限（必须随交付说明登记）：卡片为「近 N 条」近似值——
 *   若 `total > 拉取上限`（如 topicqry total > 200），命中条数会少于真实值。
 *   本步按计划不加额外 UI 提示，只在产出说明中登记。
 *
 * 字段口径（★ 一律以实际实现为准，不猜字段名）：
 *   · 主题「更新时间」：`ch_topic.modifyYMDHMS`（code/src/database/ch_topic.txt:26）。
 *     ★ 裁定 a5（Step 6）：Mock 已全局对齐为 `modifyYMDHMS`，旧的 updated 前缀兜底分支
 *     已删除 —— 只读权威字段名，避免两种命名并存掩盖字段漂移。
 *   · 凭据健康：`accounthealth` 出参为 `data.healthSummary`
 *     （★ 2026-09-21 远端实测：出参信封统一改造 P-ENV-01 后，`accounthealth` 属 **copy 域**
 *     —— 顶层保留 + `data` 副本，字段名确为 `healthSummary`，状态计数键为**大写**
 *     `OK/EXPIRING/INVALID/UNKNOWN`，与 §2.6 的 `ch_account.healthStatus` 枚举同形）。
 *     本文件用 `normalizeHealth()` 归一小写键，兼容 Mock（`data.summary` + 小写键），
 *     并把 Mock/真实两种来源收敛为同一契约，`SystemStatusBar` 只消费小写键。
 *     ★ 2026-09-23：该指标为**最近一次巡检的快照**（本页不再触发探活，见上方变更说明）
 *     → UI 文案**不得**暗示「实时」；且服务端按归属收窄：非管理员 = 本人账号范围，
 *     administrator / manager = 全站范围（两角色的数字口径不同）。
 * ========================================================================== */
import { computed, ref } from 'vue'
import { topicQry } from '@/api/topic'
import { renderJobQry } from '@/api/render'
import { artifactQry } from '@/api/artifact'
import { accountHealth } from '@/api/account'

/** 取数上限（计划 Step 5 要点 1；超出部分不计入统计，见文件头「近似统计的局限」） */
const TOPIC_LIMIT = 200
const JOB_LIMIT = 200
const ARTIFACT_LIMIT = 50
/** 最近主题条数（验收要求：Mock 数据下恰好 6 行） */
export const RECENT_LIMIT = 6

/** 「待渲染」候选主题状态（DRAFT / RENDERED 且无 DONE 渲染任务） */
const NEED_RENDER_STATUS = ['DRAFT', 'RENDERED']

/** 主题「更新时间」：14 位 `YYYYMMDDHHMMSS` 字符串，可直接字典序比较（只读权威字段名） */
export function topicModifiedAt(topic) {
  return String(topic?.modifyYMDHMS || '')
}

/** 主题 / 产物的归属键：后端以 topicCode 关联，Mock 同时给出 topicID，此处兼容两种命名 */
function topicKey(row) {
  return row?.topicCode || row?.topicID || ''
}

/** 待渲染：主题 status ∈ {DRAFT, RENDERED} 且该主题**没有** DONE 渲染任务 */
export function pickNeedRender(topics, jobs) {
  const doneKeys = new Set(jobs.filter((job) => job.jobStatus === 'DONE').map(topicKey))
  return topics.filter((topic) => NEED_RENDER_STATUS.includes(topic.status) && !doneKeys.has(topicKey(topic)))
}

/** 待校验：本期以「有 READY 产物」估算合规校验通过与否（后端无合规通过状态位） */
export function pickNeedCheck(artifacts) {
  return artifacts.filter((item) => item.artifactStatus === 'READY')
}

/** 待投递：`publishStatus === 'UNPUBLISHED'` 且该主题存在 READY 产物 */
export function pickNeedPublish(topics, artifacts) {
  const readyKeys = new Set(pickNeedCheck(artifacts).map(topicKey))
  return topics.filter((topic) => topic.publishStatus === 'UNPUBLISHED' && readyKeys.has(topicKey(topic)))
}

/** 渲染失败：`jobStatus === 'FAILED'` 的条数 */
export const pickJobFailed = (jobs) => jobs.filter((job) => job.jobStatus === 'FAILED')

/** 渲染队列积压：`jobStatus === 'PENDING'` 的条数 */
export const countPendingJobs = (jobs) => jobs.filter((job) => job.jobStatus === 'PENDING').length

/**
 * 凭据健康归一化（`accounthealth` → `{ total, ok, expiring, invalid, unknown }`）。
 * 取值来源按优先级：`data.healthSummary`（改造后真实后端，**大写**状态键）
 *                  → `data.summary`（Mock，**小写**状态键）
 *                  → 顶层 `healthSummary`（改造前部署的兜底，避免灰度期指标消失）。
 * 未取到 / 非法输入返回 `null`（由 SystemStatusBar 显示 `—`，**不编造 0 值**）。
 * @param {object|null|undefined} raw 后端原始 healthSummary / summary 对象
 */
export function normalizeHealth(raw) {
  if (!raw || typeof raw !== 'object') return null
  const num = (value) => (Number.isFinite(Number(value)) ? Number(value) : 0)
  return {
    total: num(raw.total),
    ok: num(raw.OK ?? raw.ok),
    expiring: num(raw.EXPIRING ?? raw.expiring),
    invalid: num(raw.INVALID ?? raw.invalid),
    unknown: num(raw.UNKNOWN ?? raw.unknown)
  }
}

/** 最近主题：**显式**按更新时间倒序（不依赖接口返回顺序）后取前 N 条 */
export function pickRecentTopics(topics, limit = RECENT_LIMIT) {
  return [...topics]
    .sort((a, b) => topicModifiedAt(b).localeCompare(topicModifiedAt(a)))
    .slice(0, limit)
}

export function useDashboardData() {
  const loading = ref(true)
  const error = ref('')
  const errorDetail = ref('')
  const topics = ref([])
  const jobs = ref([])
  const artifacts = ref([])
  const health = ref(null)
  /**
   * 凭据健康快照时点（14 位 `YYYYMMDDHHMMSS`；空串 = 从未巡检）。
   * ★ 2026-09-23：本页不触发巡检 → 该值来自后端按归属收窄后的
   *   `max(ch_account.lastCheckYMDHMS)`，仅用于标注「截至…」，不做实时性承诺。
   */
  const healthCheckedAt = ref('')
  /** 各查询的 `total`（用于交付说明中核对「total 是否超过拉取上限」） */
  const totals = ref({ topics: 0, jobs: 0, artifacts: 0 })

  async function load() {
    loading.value = true
    error.value = ''
    errorDetail.value = ''
    try {
      const [topicRes, jobRes, artifactRes, healthRes] = await Promise.all([
        topicQry({ beginNum: 0, endNum: TOPIC_LIMIT }),
        renderJobQry({ beginNum: 0, endNum: JOB_LIMIT }),
        artifactQry({ beginNum: 0, endNum: ARTIFACT_LIMIT }),
        // ★ 2026-09-23：不传 action → 后端只汇总、**不触发探活**（巡检改由 /my-accounts 手工触发）
        accountHealth({})
      ])
      topics.value = Array.isArray(topicRes?.data) ? topicRes.data : []
      jobs.value = Array.isArray(jobRes?.data) ? jobRes.data : []
      artifacts.value = Array.isArray(artifactRes?.data) ? artifactRes.data : []
      // ★ 出参信封统一改造（P-ENV-01）：accounthealth 为 copy 域 → 业务字段在 `data` 内（含 healthSummary）
      health.value = normalizeHealth(
        healthRes?.data?.healthSummary || healthRes?.data?.summary || healthRes?.healthSummary
      )
      // ★ 2026-09-23：快照时点。不传 action 时后端返回**范围内各账号 lastCheckYMDHMS 的最大值**
      //   （= 最近一次真实巡检时间；从未巡检为空串 → UI 显示「—」，不编造时间）。
      //   服务端已按归属收窄，故非管理员不会看到他人的巡检时间。
      healthCheckedAt.value = String(healthRes?.data?.checkedAt || '')
      totals.value = {
        topics: Number(topicRes?.total || 0),
        jobs: Number(jobRes?.total || 0),
        artifacts: Number(artifactRes?.total || 0)
      }
    } catch (e) {
      // 非 B0 的错误已由 utils/http.js 统一 toast `MSG.content`；此处只落到页面级 ErrorState
      error.value = e?.MSG?.content || '工作台数据加载失败'
      errorDetail.value = [e?.errCode ? `errCode: ${e.errCode}` : '', e?.message || ''].filter(Boolean).join('\n')
      console.error('[dashboard] 聚合取数失败', e)
    } finally {
      loading.value = false
    }
  }

  /** 4 张指标卡的命中条数（口径见 pick* 函数） */
  const counts = computed(() => ({
    needRender: pickNeedRender(topics.value, jobs.value).length,
    needCheck: pickNeedCheck(artifacts.value).length,
    needPublish: pickNeedPublish(topics.value, artifacts.value).length,
    jobFailed: pickJobFailed(jobs.value).length
  }))

  return {
    loading,
    error,
    errorDetail,
    totals,
    health,
    healthCheckedAt,
    counts,
    recentTopics: computed(() => pickRecentTopics(topics.value)),
    pendingCount: computed(() => countPendingJobs(jobs.value)),
    load
  }
}

export default useDashboardData
