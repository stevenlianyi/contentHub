/* ============================================================================
 * useJobPolling · P-06 渲染任务「取数 + 出参归一化 + 轮询 + 动作自约束」（Step 11）
 * ----------------------------------------------------------------------------
 * 【越界授权登记（裁定 L·l1）】本文件**不在** Step 11 产出清单内，登记为越界授权文件：
 *   `RenderJobs.vue` 只做视图与编排；取数 / 出参归一化 / 轮询 / 筛选 / 动作调用收敛到本文件，
 *   以满足「单文件 ≤ 600 行」（§2.1）硬约束。
 *
 * 【后端事实（已核源码，服从；不得凭计划文字臆断）】
 *   · processor/renderService.py:113-120 **状态机**：PENDING → [RUNNING, FAILED]；RUNNING → [DONE, FAILED]；
 *     DONE → []（终态）；FAILED → [PENDING]；非法跃迁 → `C7` 并回显 `data.currentStatus` /
 *     `data.allowedTransitions`（renderService.py:431-469 `updateJobStatus`）。
 *   · ★ **HTTP 端点 `renderjobmodify` 属 crud 域生成件**（`subfunc/crudApi.py:1170-1290`）：直接
 *     `update_ch_render_job` 写字段、**不做状态机校验** → 非法跃迁后端不拦，只能由**前端自我约束**
 *     （本文件 `JOB_ACTIONS` + `assertJobTransition`，见裁定 B）。
 *   · `renderjobmodify` 实参（crudApi.py:1197-1216 + mysqlCommon.py:2890-2972）：`recID` 定位 +
 *     `jobStatus` / `errMsg` / `progress` / `costMs` / `startYMDHMS` / `finishYMDHMS`…；★ 空值不落库
 *     （`if errMsg:` 等）→ **无法用空串清空字段**（附录 B R-22 同款语义）。
 *   · ★ `renderjobqry` 的**服务端过滤**已于 2026-09-22 补齐（附录 B R-28，手改 `funcRenderjobQry`）：
 *     `jobCode/topicID/jobStatus/platform/ownerID/beginYMDHMS/endYMDHMS/order` 均透传 → 本文件把
 *     `jobStatus`/`topicID` **纯服务端筛选**（无客户端兜底，避免双重条件掩盖漏筛；order 固定 'modify'）。
 *   · `keyword` 后端**仍无**该入参（只有 searchOption）→ 保留**本地筛选**，文案须写明这一点。
 *   · `ch_render_job`（`database/ch_render_job.txt`）**无 `errorCode` 列**，只有自由文本 `errMsg`
 *     → 错误码语义由 `resolveErrCode()` 从 `errorCode`（Mock / 未来字段）或 `errMsg` 文本推导。
 *     ★ `progress` **不由渲染流程驱动**（附录 B R-06）→ 只允许文本百分比，禁止进度条。
 *   · `topicrender`（renderService.py:752-845）：`job` 模式建任务后立即返回 `{renderMode, reused:'0',
 *     jobID, jobCode, jobStatus:'PENDING', inputHash, message}`；`inputHash` 命中既有 DONE 任务 →
 *     `reused='1'` 且**不重复渲染**（`_buildReuseResult` renderService.py:708-745 返回原
 *     `jobID`/`jobCode`）。`jobID` = `ch_render_job.recID`（自增主键）→「查看产物」跳
 *     `/artifacts?jobID=<recID>`，与 `ch_artifact.jobID`（注释：关联 ch_render_job.recID）同口径。
 *   · `renderjobqry` **不返回主题标题**（表里只有 `topicID`）→ 需 `topicqry({recID})` 补标题；按当前页
 *     去重并发补取并**跨轮询缓存**（避免每 5s 重打）。
 *
 * 【出参信封（P-ENV-01，2026-09-21 生效）】`renderjobqry` = **keep**（`data` 为数组 + `total`）；
 *   `renderjobmodify` / `topicrender` = **move**（业务字段在 `data`；`topicrender` 失败路径自带的
 *   `data.{jobID,jobCode}` 随迁为 `data.data.*`）。★ 统一经 `pickEnvelope(res)`（信封顶层 ⊕ `data`
 *   内层，**内层优先、数组不参与合并**）读取 —— 与 `views/preview/usePreviewRender.js` 同一口径，
 *   理由：① 灰度/回滚期旧部署仍是平铺；② move 形态下 `data.data` 双层键对合并安全；③ 不依赖信封印花键。
 *
 * 【数值形态（附录 B R-26）】`progress` / `costMs` / `jobID` / `seqNo` 一律 `Number()` 后再比较/展示。
 * ========================================================================== */
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { toast } from 'vue3-toastify'
import { renderJobModify, renderJobQry, topicRender } from '@/api/render'
import { topicQry } from '@/api/topic'
import { ERR_CODE_TEXT, LAYOUT_TYPE_MAP } from '@/config/chOptions'

/* ------------------------------ 1. 常量与字典 ------------------------------ */

/** 轮询间隔（裁定 E：存在 PENDING/RUNNING 时每 5s 刷新） */
export const POLL_INTERVAL_MS = 5000
/** 连续失败上限（裁定 E：累计 3 次失败后停止轮询，页面给「自动刷新已暂停」+「手动刷新」） */
export const MAX_POLL_FAILURES = 3
/** 每页条数（服务端分页；§2.11 长列表用服务端分页） */
export const PAGE_SIZE = 20
/** 取消任务的 `errMsg` 约定值（裁定 C） */
export const CANCELED_ERR_MSG = 'USER_CANCELED'
/** 状态顺序（筛选下拉 / 展示顺序；与 §2.6 渲染状态机一致） */
export const JOB_STATUS_ORDER = ['PENDING', 'RUNNING', 'DONE', 'FAILED']

/**
 * ★ 渲染任务状态机 —— 与 `processor/renderService.py:113-120` **逐字一致**（唯一权威）。
 * 前端据此只暴露合法动作；非法跃迁在发请求前就被 `assertJobTransition()` 拦下（裁定 B）。
 */
export const JOB_STATUS_TRANSITIONS = {
  PENDING: ['RUNNING', 'FAILED'],
  RUNNING: ['DONE', 'FAILED'],
  DONE: [],
  FAILED: ['PENDING']
}

/**
 * ★ 前端允许暴露的 UI 动作（裁定 B；因 HTTP 端点不校验状态机，必须由前端自我约束）：
 *   PENDING → 仅「取消」；RUNNING → 仅「查看详情」（不与 renderWorker 竞争取消）；
 *   FAILED  → 「重试」+「重新渲染」；DONE → 「查看产物」（终态）。
 * ★ 禁止出现 DONE→PENDING / RUNNING→PENDING 等非法动作。
 */
export const JOB_ACTIONS = {
  PENDING: ['cancel'],
  RUNNING: ['detail'],
  DONE: ['artifacts'],
  FAILED: ['retry', 'rerender', 'detail']
}

/** 取消类任务在失败详情里的专用语义（`errMsg` 约定值，非错误码） */
const CANCELED_LABEL = '用户已取消（非系统失败）'
/** 错误码 → `errMsg` 文本特征（`ch_render_job` 无 errorCode 列，只能按文本推导语义） */
const ERR_TEXT_PATTERNS = [
  ['E1', ['渲染失败']],
  ['E2', ['截图超时']],
  ['E3', ['产物生成失败']],
  ['E4', ['外链图片', '转存']]
]

/* ------------------------------ 2. 纯函数 ------------------------------ */

/** 安全字符串化（null / undefined → 空串） */
export const str = (value) => (value === null || value === undefined ? '' : String(value))
/** 宽松数值转换（★ R-26：真实后端数值字段以字符串返回，比较前一律 Number()） */
export const toNum = (value, fallback = 0) => {
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}
/** 开关类字段（'0' / '1'）归一化为字符串，不做布尔转换（后端以字符串返回） */
export const flag = (value) => str(value ?? '0')
/** 去掉末尾多余分号（§2.5 第 3 条：toast 文案口径） */
const trimTail = (text) => str(text).trim().replace(/[;；]+$/, '')

/** 当前状态是否为活动态（决定是否轮询） */
export const isActiveJob = (row) => row?.jobStatus === 'PENDING' || row?.jobStatus === 'RUNNING'

/** 该状态允许的 UI 动作（未知状态一律返回空数组：不暴露任何写操作） */
export function allowedActions(status) {
  return JOB_ACTIONS[str(status).toUpperCase()] || []
}

/**
 * ★ 出参信封读取（P-ENV-01）：信封顶层 ⊕ `data` 内层，**内层优先、数组不参与合并**
 * （`renderjobqry` 为 keep 形态，`data` 是数组，业务列表由调用方直接读 `res.data`）。
 */
export function pickEnvelope(res) {
  const envelope = res && typeof res === 'object' ? res : {}
  const inner = envelope.data && typeof envelope.data === 'object' && !Array.isArray(envelope.data) ? envelope.data : null
  return inner ? { ...envelope, ...inner } : envelope
}

/** 错误码语义（§2.5 / chOptions.ERR_CODE_TEXT；未知码返回空串，由调用方回落到原文） */
export function errCodeText(code) {
  return ERR_CODE_TEXT[str(code)] || ''
}

/**
 * 推导失败原因的错误码语义（★ `ch_render_job` 无 errorCode 列，只有 `errMsg` 自由文本）：
 * ① 记录自带 `errorCode` / `errCode` 且命中字典 → 直接采用；② `errMsg` 命中 `E1–E4` 特征词 → 推导；
 * ③ 都不命中 → 空串（页面显式说明「后端未给出错误码」，**不编造**）。
 */
export function resolveErrCode(row) {
  // ★ 先 `errMsg`（权威列名）再 `errorMsg`（Mock 旧命名）：取消后 Mock 行会同时存在两者。
  const text = str(row?.errMsg) || str(row?.errorMsg)
  // ★ 「取消」以 errMsg 约定值表达（裁定 C），优先级**高于任何遗留 errorCode**：
  //   取消后记录里可能仍留着被覆盖前的 errorCode（如 E4），据此回显会造成误读
  //   （2026-09-21 自测实测：Mock 行的 `errorCode='E4'` 会把「已取消」错标成 E4）。
  if (text.includes(CANCELED_ERR_MSG)) return CANCELED_ERR_MSG
  const explicit = str(row?.errorCode || row?.errCode)
  if (explicit && errCodeText(explicit)) return explicit
  if (!text) return ''
  const hit = ERR_TEXT_PATTERNS.find(([, words]) => words.some((word) => text.includes(word)))
  return hit ? hit[0] : ''
}

/** 失败原因的错误码语义文案（含「用户取消」与「未给码」两种非 E 码情形） */
export function errCodeLabel(code) {
  const key = str(code)
  if (!key) return ''
  if (key === CANCELED_ERR_MSG) return CANCELED_LABEL
  return errCodeText(key)
}

/**
 * 版式「类型」推导（版式列需 `layoutCode` + `LAYOUT_TYPE_MAP` 中文）。
 * ★ `ch_render_job` 无 layoutType 列，而 `LAYOUT_TYPE_MAP` 的键是*类型*（stack / carousel /
 *   longimage / swipe），四个种子版式的编码前缀即类型（`stack_v1` → `stack`…，计划 §2.7）
 *   → 优先取记录自带 `layoutType`（若后端将来补充），否则按 `layoutCode` 前缀推导。
 */
export function layoutTypeOf(row) {
  const explicit = str(row?.layoutType)
  if (explicit) return explicit
  const code = str(row?.layoutCode)
  const index = code.indexOf('_')
  return index > 0 ? code.slice(0, index) : ''
}

/** 版式中文名（未知版式返回空串，由调用方只显示 layoutCode） */
export function layoutLabelOf(row) {
  return LAYOUT_TYPE_MAP[layoutTypeOf(row)] || ''
}

/**
 * 记录归一化：字段名兼容 + 数值转 `Number`（R-26）。★ 字段名差异（已在交付说明登记）：
 * 真实列 `errMsg` / `startYMDHMS` / `finishYMDHMS`，Mock 为 `errorMsg` / `startedYMDHMS` /
 * `finishedYMDHMS` → 两套都读，取到即用。
 */
export function normalizeJob(raw) {
  const row = raw && typeof raw === 'object' ? raw : {}
  const jobStatus = str(row.jobStatus).toUpperCase()
  return {
    ...row,
    recID: str(row.recID),
    jobCode: str(row.jobCode),
    topicID: str(row.topicID),
    topicCode: str(row.topicCode),
    topicTitle: str(row.topicTitle || row.title),
    layoutCode: str(row.layoutCode),
    platform: str(row.platform),
    jobStatus,
    progress: toNum(row.progress),
    costMs: toNum(row.costMs),
    inputHash: str(row.inputHash),
    errMsg: str(row.errMsg || row.errorMsg),
    errCode: resolveErrCode(row),
    startYMDHMS: str(row.startYMDHMS || row.startedYMDHMS),
    finishYMDHMS: str(row.finishYMDHMS || row.finishedYMDHMS),
    isTerminal: jobStatus === 'DONE' || jobStatus === 'FAILED'
  }
}

/**
 * ★ 状态机前置断言（裁定 B）：只用 `JOB_STATUS_TRANSITIONS` 判定，非法跃迁**不发请求**。
 * 抛出的对象与后端错误信封同形（`errCode` / `MSG.content` / `data`），便于 `describeJobError()` 统一解析。
 */
export function assertJobTransition(from, to) {
  const current = str(from).toUpperCase()
  const next = str(to).toUpperCase()
  if (!JOB_STATUS_ORDER.includes(next)) {
    throw { errCode: 'C7', MSG: { content: `目标状态 ${next || '（空）'} 非法，允许值：${JOB_STATUS_ORDER.join(' / ')}` }, data: {} }
  }
  if (!current || current === next) return true
  const allowed = JOB_STATUS_TRANSITIONS[current] || []
  if (!allowed.includes(next)) {
    throw {
      errCode: 'C7',
      MSG: { content: `非法跃迁 ${current} → ${next}（当前状态 ${current}，允许跃迁 ${allowed.join(' / ') || '无（终态）'}）` },
      data: { currentStatus: current, allowedTransitions: allowed }
    }
  }
  return true
}

/**
 * 异常 → 行内说明（裁定 B）：
 * 错误码取值链 `errCode` → `MSG.errCode` → `code`（与 Step 10 同口径）；
 * ★ `C7` 时读取 `data.currentStatus` / `data.allowedTransitions` 给出行内说明 ——
 *   processor 路径会回显，**HTTP 路径不会**（crud 生成件不校验），故两处都容错。
 */
export function describeJobError(error) {
  const code = str(error?.errCode || error?.MSG?.errCode || error?.code)
  const inner = pickEnvelope(error)
  const currentStatus = str(inner.currentStatus)
  const allowed = Array.isArray(inner.allowedTransitions) ? inner.allowedTransitions.map(str) : []
  const message = trimTail(error?.MSG?.content) || errCodeText(code) || '操作失败'
  const hint = code === 'C7' && currentStatus
    ? `后端状态机：当前 ${currentStatus}，允许跃迁 ${allowed.length ? allowed.join(' / ') : '无（终态）'}`
    : ''
  return { code, message, currentStatus, allowed, hint, detail: code ? `errCode: ${code}` : '' }
}

/* ------------------------------ 3. 组合式函数 ------------------------------ */

/**
 * @param {{ jobStatus?: string, topicID?: string, page?: number|string, pageSize?: number|string }} [options]
 *        初值来自路由 query（由页面读取并传入，本文件不依赖 vue-router，便于单测）。
 */
export function useJobPolling(options = {}) {
  /* --------------------------- 3.1 状态 --------------------------- */
  const rows = ref([])
  const total = ref(0)
  const page = ref(Math.max(1, toNum(options.page, 1)))
  const size = ref(Math.max(1, toNum(options.pageSize, PAGE_SIZE)))
  /**
   * 首屏 / 手动刷新（显示骨架或遮罩；轮询不置位，避免每 5s 闪一次）。
   * ★ 初值 true：页面在 `onMounted` 立即 `load()`，避免「空态 → 骨架 → 数据」的闪烁。
   */
  const loading = ref(true)
  /** 静默轮询中（只用于顶部「自动刷新中」文案，不遮挡表格） */
  const refreshing = ref(false)
  const error = ref('')
  const errorDetail = ref('')
  /** 服务端请求参数（页面负责与 URL query 双向同步） */
  const filters = reactive({
    jobStatus: str(options.jobStatus),
    topicID: str(options.topicID),
    keyword: str(options.keyword)
  })
  /** 主题标题缓存：`topicID(recID)` → `{ title, topicCode }`（跨轮询复用，避免每 5s 重打） */
  const titleMap = ref({})
  const pollFailures = ref(0)
  const pollPaused = ref(false)
  /** 最近一次取数时刻（HH:mm:ss，供自测核对轮询间隔） */
  const lastLoadedAt = ref('')

  /** 已尝试补取标题的 topicID（失败也记一次，避免轮询反复重打、反复 toast） */
  const triedTopicIDs = new Set()
  let timer = null
  let requestId = 0
  let loadSeq = 0
  let hadActive = false
  let finishedNotified = false

  /* --------------------------- 3.2 派生 --------------------------- */
  const filterActive = computed(() => Boolean(filters.jobStatus || filters.topicID || filters.keyword))
  /** ★ 状态/主题为纯服务端筛选（R-28）→ 此处**只**叠加关键字本地筛选，不做二次过滤掩盖漏筛 */
  const visibleRows = computed(() => rows.value.filter((row) => matchesKeyword(row)))
  const hasActiveJobs = computed(() => rows.value.some(isActiveJob))
  /** 轮询是否真的在跑（活动任务存在 且 未因连续失败暂停） */
  const pollingActive = computed(() => hasActiveJobs.value && !pollPaused.value)
  const pageCount = computed(() => Math.max(1, Math.ceil(total.value / size.value)))
  const isEmpty = computed(() => !loading.value && !error.value && visibleRows.value.length === 0)
  const emptyTitle = computed(() => (filterActive.value ? '当前筛选无匹配任务' : '暂无渲染任务'))
  const emptyDescription = computed(() =>
    filterActive.value
      ? '状态 / 主题筛选由服务端执行（renderjobqry 已透传 jobStatus / topicID，附录 B R-28）；关键字为本地筛选（后端无 keyword 参数）。可清除筛选查看全部。'
      : '还没有渲染任务。到主题库选择版式并发起渲染后，任务会出现在这里。'
  )

  /* --------------------------- 3.3 内部工具 --------------------------- */
  /** ★ 仅**关键字**为本地筛选（后端无 keyword 入参）；状态/主题已由服务端完成（R-28） */
  function matchesKeyword(row) {
    if (!filters.keyword) return true
    const keyword = filters.keyword.toLowerCase()
    const haystack = `${row.topicTitle || ''} ${row.jobCode || ''}`.toLowerCase()
    return haystack.includes(keyword)
  }

  function nowText() {
    return new Date().toTimeString().slice(0, 8)
  }

  function stopTimer() {
    if (timer) clearTimeout(timer)
    timer = null
  }

  function buildParams() {
    const params = {
      mode: 'full',
      beginNum: (page.value - 1) * size.value,
      endNum: page.value * size.value,
      // ★ 任务状态秒级变化：一律绕过后端查询缓冲（§2.4.3 forceFlashFlag='1'）
      forceFlashFlag: '1',
      // ★ 服务端排序（R-28 已透传 order）：modify → 修改时间倒序；不得传 'update' 等未定义值
      order: 'modify'
    }
    if (filters.jobStatus) params.jobStatus = filters.jobStatus
    if (filters.topicID) params.topicID = filters.topicID
    if (filters.keyword) params.keyword = filters.keyword
    return params
  }

  function patchRow(recID, patch) {
    rows.value = rows.value.map((row) => (row.recID === recID ? normalizeJob({ ...row, ...patch }) : row))
  }

  /** 主题标题补取（`renderjobqry` 只有 topicID；按当前页去重 + 并发 + 缓存，N+1 上限 = 页大小） */
  async function ensureTitles(list) {
    const missing = [...new Set(list.map((row) => str(row.topicID)).filter((id) => id && !titleMap.value[id] && !triedTopicIDs.has(id)))]
    if (!missing.length) return
    missing.forEach((id) => triedTopicIDs.add(id))
    const results = await Promise.all(
      missing.map(async (id) => {
        try {
          const res = await topicQry({ recID: id })
          const first = Array.isArray(res?.data) ? res.data[0] : pickEnvelope(res)
          if (!first || typeof first !== 'object') return [id, null]
          return [id, { title: str(first.title), topicCode: str(first.topicCode) }]
        } catch (e) {
          console.warn('[P-06] topicqry 补取主题标题失败（该行回落到话题ID）', id, e)
          return [id, null]
        }
      })
    )
    const next = { ...titleMap.value }
    results.forEach(([id, value]) => {
      if (value) next[id] = value
    })
    titleMap.value = next
  }

  /* --------------------------- 3.4 轮询调度 --------------------------- */
  function schedule() {
    stopTimer()
    if (pollPaused.value) return
    // 页面隐藏时不排程；可见时由 visibilitychange 立即补一次并重新排程（裁定 E）
    if (typeof document !== 'undefined' && document.hidden) return
    timer = setTimeout(() => void poll(), POLL_INTERVAL_MS)
  }

  async function poll() {
    timer = null
    if (typeof document !== 'undefined' && document.hidden) {
      schedule()
      return
    }
    await load({ silent: true })
  }

  /** 取数后重算轮询状态：全终态 → 停轮询并「只提示一次」；有活动任务 → 继续排程 */
  function syncPolling() {
    const active = rows.value.some(isActiveJob)
    if (active) {
      hadActive = true
      finishedNotified = false
      schedule()
      return
    }
    stopTimer()
    if (hadActive && !finishedNotified) {
      finishedNotified = true
      toast.success('全部任务已完成')
    }
    hadActive = false
  }

  function onVisibilityChange() {
    if (typeof document === 'undefined') return
    if (document.hidden) {
      stopTimer()
      return
    }
    if (pollPaused.value || !rows.value.some(isActiveJob)) return
    void load({ silent: true })
  }

  if (typeof document !== 'undefined') document.addEventListener('visibilitychange', onVisibilityChange)

  /* --------------------------- 3.5 取数 --------------------------- */

  /**
   * 取数。
   * @param {{ silent?: boolean }} [opts] `silent=true` 为**轮询**：不置 loading、带 `config.silent`
   *        抑制全局 toast（裁定 E），失败仅 `console.warn` 且累计 3 次后暂停轮询。
   */
  async function load(opts = {}) {
    const { silent = false } = opts
    const current = ++requestId
    loadSeq += 1
    if (silent) refreshing.value = true
    else loading.value = true
    if (!silent) error.value = ''

    const params = buildParams()
    // 轮询留痕（供自测核对 5s 间隔；与 Step 10 的 topicrender payload 日志同风格）
    console.info(`[P-06] renderjobqry #${loadSeq}`, { at: nowText(), silent, ...params })

    try {
      const res = await renderJobQry(params, silent ? { silent: true } : undefined)
      if (current !== requestId) return
      // ★ renderjobqry 属 keep 形态（P-ENV-01）：`data` 为数组
      const list = Array.isArray(res?.data) ? res.data : []
      rows.value = list.map(normalizeJob)
      total.value = Number(res?.total || 0)
      error.value = ''
      errorDetail.value = ''
      pollFailures.value = 0
      if (pollPaused.value) {
        pollPaused.value = false
        console.info('[P-06] 手动刷新成功，已恢复自动刷新')
      }
      lastLoadedAt.value = nowText()
      void ensureTitles(rows.value)
      syncPolling()
    } catch (e) {
      if (current !== requestId) return
      if (silent) {
        pollFailures.value += 1
        console.warn(`[P-06] 轮询失败（静默，第 ${pollFailures.value}/${MAX_POLL_FAILURES} 次）`, e)
        if (pollFailures.value >= MAX_POLL_FAILURES) {
          pollPaused.value = true
          stopTimer()
          console.warn('[P-06] 连续失败达 3 次，已暂停自动刷新（页面提供「手动刷新」）')
        }
      } else {
        // 非 B0 已由 utils/http.js 统一 toast MSG.content；此处只落到页面级 ErrorState（不留白）
        error.value = trimTail(e?.MSG?.content) || '渲染任务读取失败'
        errorDetail.value = [e?.errCode ? `errCode: ${e.errCode}` : '', e?.message || ''].filter(Boolean).join('\n')
        console.error('[P-06] renderjobqry 失败', e)
      }
    } finally {
      if (current === requestId) {
        if (silent) refreshing.value = false
        else loading.value = false
      }
    }
  }

  /* --------------------------- 3.6 筛选 / 分页 --------------------------- */
  /** 应用筛选（页面先同步 URL query 再调用）：回到第 1 页并重取 */
  function setFilters(patch = {}) {
    Object.assign(filters, {
      jobStatus: str(patch.jobStatus).toUpperCase(),
      topicID: str(patch.topicID),
      keyword: str(patch.keyword)
    })
    page.value = 1
    return load()
  }

  function goPage(nextPage) {
    const target = Math.min(Math.max(1, toNum(nextPage, 1)), pageCount.value)
    if (target === page.value) return load()
    page.value = target
    return load()
  }

  function changeSize(nextSize) {
    const target = Math.max(1, toNum(nextSize, size.value))
    size.value = target
    page.value = 1
    return load()
  }

  /* --------------------------- 3.7 动作（自我约束） --------------------------- */

  /**
   * 取消（裁定 C）：`renderjobmodify({ recID, jobStatus:'FAILED', errMsg:'USER_CANCELED' })`。
   * ★ 用任务记录的 **`recID`** 定位（不是 jobCode）；`PENDING → FAILED` 是状态机合法跃迁。
   * ★ payload 严格限定 3 个字段（裁定 C），不额外回填 finishYMDHMS（登记为待确认项）。
   */
  async function cancelJob(row) {
    const recID = str(row?.recID)
    if (!recID) throw { errCode: 'BI', MSG: { content: '任务记录缺少 recID，无法定位' }, data: {} }
    assertJobTransition(row.jobStatus, 'FAILED')
    const res = await renderJobModify({ recID, jobStatus: 'FAILED', errMsg: CANCELED_ERR_MSG })
    patchRow(recID, { jobStatus: 'FAILED', errMsg: CANCELED_ERR_MSG, errCode: CANCELED_ERR_MSG })
    void load({ silent: true })
    return { recID, jobCode: str(row.jobCode), data: pickEnvelope(res) }
  }

  /**
   * 重试（裁定 D）：把 `jobStatus` 置回 `PENDING`，**沿用原输入**重新入队（无新任务号）。
   * ★ `FAILED → PENDING` 是状态机合法跃迁；★ 不清空 `errMsg`（crud 端点空值不落库，置空无效）。
   */
  async function retryJob(row) {
    const recID = str(row?.recID)
    if (!recID) throw { errCode: 'BI', MSG: { content: '任务记录缺少 recID，无法定位' }, data: {} }
    assertJobTransition(row.jobStatus, 'PENDING')
    const res = await renderJobModify({ recID, jobStatus: 'PENDING' })
    patchRow(recID, { jobStatus: 'PENDING' })
    void load({ silent: true })
    return { recID, jobCode: str(row.jobCode), data: pickEnvelope(res) }
  }

  /**
   * 重新渲染（裁定 D）：调 `topicrender({renderMode:'job'})` 建**新任务**。
   * ★ 省略 platform（Step 9 裁定 B：传与版式冲突的值会得到 C7，缺省由 `ch_layout.platform` 推导）；
   * ★ `reused='1'` → 输入未变化、已复用既有产物，**UI 必须显式提示**并给出跳产物页入口。
   */
  async function rerenderTopic(row) {
    const payload = { topicID: str(row?.topicID), layoutCode: str(row?.layoutCode), renderMode: 'job' }
    if (!payload.topicID || !payload.layoutCode) {
      throw { errCode: 'C4', MSG: { content: '缺少 topicID 或 layoutCode，无法重新渲染' }, data: {} }
    }
    console.info('[P-06] topicrender 实际发出的 payload', payload)
    const res = await topicRender(payload)
    const data = pickEnvelope(res)
    void load({ silent: true })
    return {
      payload,
      reused: flag(data.reused),
      jobID: str(data.jobID),
      jobCode: str(data.jobCode),
      jobStatus: str(data.jobStatus),
      reuseReason: str(data.reuseReason)
    }
  }

  /** 销毁：停轮询 + 摘监听（路由离开时不留定时器） */
  onBeforeUnmount(() => {
    stopTimer()
    if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', onVisibilityChange)
  })

  return {
    // 数据与状态
    rows,
    visibleRows,
    total,
    page,
    size,
    pageCount,
    loading,
    refreshing,
    error,
    errorDetail,
    filters,
    filterActive,
    titleMap,
    isEmpty,
    emptyTitle,
    emptyDescription,
    // 轮询
    hasActiveJobs,
    pollingActive,
    pollPaused,
    pollFailures,
    lastLoadedAt,
    // 方法
    load,
    setFilters,
    goPage,
    changeSize,
    cancelJob,
    retryJob,
    rerenderTopic,
    stopPolling: stopTimer
  }
}

export default useJobPolling
