/* ============================================================================
 * useComplianceCheck · P-09（Step 13）页私有取数 / 归一化 / 跳转映射（裁定 M 授权新增）
 * ----------------------------------------------------------------------------
 * 为什么独立成文件：`Compliance.vue` 需同时收敛「取数 + 参数拼装 + issue 归一化 + 跳转映射」，
 * 全写在 .vue 里会逼近 600 行上限（§2.1）；本文件只放**纯逻辑**，视图由 .vue 负责。
 *
 * ★ 后端事实（已核 `code/src/processor/complianceService.py`，实现必须服从）：
 *   1) 出参 `data` 字段：passed("1"/"0") / issueCount / errorCount / warningCount / issues[] /
 *      platformCode / layoutType / assetCount / sensitiveHitCount / rateLimit{...} / topicID
 *      (= ch_topic.recID) / topicCode / layoutCode / platform / accountID / checkedAt。
 *      ★ **后端不返回「检查项总数」** → 前端不得推算「通过数」（裁定 A）。
 *   2) `passed === '1'` 仅当无 ERROR（WARN 不阻断）。
 *   3) 入参：`topicID | recID | topicCode`（三选一）+ 可选 platform / layoutCode / layoutType /
 *      sensitiveWords[] / products[] / rateLimitCount / rateLimitWindow / accountID / ownerID；
 *      ★ platform 缺省取 layoutCode 对应 `ch_layout.platform`，**两者都空 → 直接 C7**
 *      → 调用前必须保证 platform 非空（本文件用页内平台选择器兜底）。
 *   4) issue 的 field/location 一律「带后缀」：`description(ch_topic)` / `coverSpec(ch_platform:wechat_mp)`
 *      / `specJson.sliceHeight` / `products[0].fileID` / `rateLimit`；location 另有 `description[12,15]`
 *      与 `assetList[N]` 两种形态 → ★ 必须先 `normalizeField()` 再比对，否则全部落兜底（裁定 C）。
 *   5) `publishcheck` **不是免登录端点**（2.9.8 清单里没有它）→ 请求必须带 sessionID
 *      （由 utils/http.js 统一注入请求体）。
 * ★ 本页**全部请求**（topicqry / layoutqry / platformqry / publishcheck / topicmodify / topicrender）
 *   一律 `{ silent: true }`：错误原因由页面 ErrorState 或页面级 toast 呈现，
 *   **不出现全局 toast 叠加**（通用约束 4；故 api/{topic,layout,platform}.js 要透传 config）。
 * ========================================================================== */
import { computed, ref, watch } from 'vue'
import { publishCheck } from '@/api/compliance'
import { layoutQry } from '@/api/layout'
import { platformQry } from '@/api/platform'
import { topicRender } from '@/api/render'
import { topicModify, topicQry } from '@/api/topic'
import { COMPLIANCE_SOURCE_MAP, COMPLIANCE_SOURCE_ORDER } from '@/config/chOptions'
import { normalizeLayouts, normalizePlatforms } from '@/views/topic/useRenderTrigger'
import { charCount } from '@/utils/common'

/** 追加的标准 AI 标识文案（★ 必须命中后端 `AI_LABEL_MARKER_LIST` 中的词，见 appendAiLabel 注释） */
export const AI_LABEL_MARKER = '本内容由AI辅助创作'
/** 详述字符上限（裁定 I：追加前用 `charCount()` 判断，超限则不给按钮） */
export const DESCRIPTION_MAX_CHARS = 5000
/** 「标记通过」的本机记录键前缀（供 Step 14 投递页读取作为门禁，裁定 J） */
export const MARK_PASS_STORAGE_PREFIX = 'chapp:compliance:'
/** 平台缺省值（§2.7 种子；后端 platform 全空会直接 C7，故必须给非空值） */
export const DEFAULT_PLATFORM = 'wechat_mp'

/** 宽松数值转换：后端数值/计数一律按字符串返回（R-26），统一 Number() 后再参与计算（裁定 L） */
export const toNum = (value, fallback = 0) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

/**
 * 字段名归一化（裁定 C）：`String(field).split('(')[0].trim()`。
 * 例：`description(ch_topic)` → `description`；`coverSpec(ch_platform:wechat_mp)` → `coverSpec`；
 *     `specJson.sliceHeight` → `specJson.sliceHeight`（无括号，原样）。
 * ★ 直接拿原始 field 比对会导致**全部落兜底**。
 */
export function normalizeField(field) {
  return String(field ?? '').split('(')[0].trim()
}

/** 内容页（Tab1）字段：`focus` 取同名字段（TabContent.vue 已导出 focusField(key)） */
const CONTENT_FIELDS = new Set([
  'title', 'summary', 'description', 'author', 'location', 'source', 'period',
  'tagList', 'categoryCode', 'aiFlag'
])
/** 素材页（Tab2）字段（含 imageMaxCount / imageCount：数量类问题同样落在素材页处理） */
const ASSET_FIELDS = new Set(['coverSpec', 'coverFileID', 'imageSpec', 'imageMaxCount', 'imageCount', 'assetList'])
/** 版式页（Tab3）字段 */
const LAYOUT_FIELDS = new Set(['layoutCode', 'layoutType', 'platform', 'platformCode', 'specJson.sliceHeight'])

/** 页面侧「影响」说明（★ 仅解释界面后果，不改写后端 message） */
const IMPACT_NOTES = {
  'specJson.uniformRatio': '影响：App 内左右滑动时画面会跳动',
  'specJson.sliceHeight': '影响：超长整图会被平台强制缩放，文字发虚'
}

/** 取 issue 的界面「影响」说明（无则返回空串） */
export function issueImpactNote(issue) {
  return IMPACT_NOTES[normalizeField(issue?.field)] || ''
}

/**
 * issue → 「去修正」跳转目标（裁定 C / D）：
 *   · `location` 形如 `assetList[N]` → 素材页并高亮第 N 张（0 基下标，UI 文案用「第 N+1 张」）；
 *     ★ 该条与 `specJson.sliceHeight` 的字段级兜底冲突时**以精确下标优先**（更可操作）；
 *   · `products…`（含 location=products）→ 产物页（Tab4，Step 12 已交付）；
 *   · `rateLimit` → 不跳转（页面内滚动到限流说明，裁定 C 允许按钮改为「查看限流说明」）；
 *   · 未命中一律 `content` 且不聚焦（kind='fallback'，由调用方给出「位置：{location}」兜底文案）。
 * @returns {{ kind: string, tab: string, focus: string, assetIndex: number }}
 */
export function resolveIssueTarget(issue) {
  const field = normalizeField(issue?.field)
  const location = String(issue?.location ?? '')
  const assetMatched = /^assetList\[(\d+)\]/.exec(location)

  if (field === 'rateLimit' || location === 'rateLimit') return { kind: 'rate-limit', tab: '', focus: '', assetIndex: -1 }
  if (assetMatched) return { kind: 'assets', tab: 'assets', focus: '', assetIndex: Number(assetMatched[1]) }
  if (location.startsWith('products') || field.startsWith('products')) {
    return { kind: 'artifacts', tab: 'artifacts', focus: field, assetIndex: -1 }
  }
  // ★ `ch_topic` 无 aiLabel 列（只有 aiFlag）→ AI 标识的问题只能落到「详述」上修正（见 appendAiLabel）
  if (field === 'aiLabel') return { kind: 'content', tab: 'content', focus: 'description', assetIndex: -1 }
  if (CONTENT_FIELDS.has(field)) return { kind: 'content', tab: 'content', focus: field, assetIndex: -1 }
  if (ASSET_FIELDS.has(field)) return { kind: 'assets', tab: 'assets', focus: '', assetIndex: -1 }
  if (LAYOUT_FIELDS.has(field)) return { kind: 'layout', tab: 'layout', focus: '', assetIndex: -1 }
  if (field.startsWith('specJson.')) return { kind: 'assets', tab: 'assets', focus: '', assetIndex: -1 }
  return { kind: 'fallback', tab: 'content', focus: '', assetIndex: -1 }
}

/**
 * 「通过」分组的类别状态（裁定 B）：`issue` 已出问题 / `pass` 未产出问题 / `skipped` 本次未执行。
 * ★ `skipped` **不得**算作通过；判定依据全部来自后端出参（`data.layoutType`）与 `ch_platform`
 *   的 `needAiLabelFlag`（页内已加载 platformqry），**不臆断**。
 */
export function buildSourceStatuses({ issues = [], data = {}, platformRecord = null } = {}) {
  const present = new Set((issues || []).map((item) => String(item?.source || '')).filter(Boolean))
  const layoutType = String(data?.layoutType || '').toLowerCase()
  // 平台记录缺失（R-24 空响应）时无法判定 AI 标识是否强制 → 按「已执行」处理，不谎报「未执行」
  const needAiLabel = platformRecord ? String(platformRecord.needAiLabelFlag ?? '') === '1' : null
  const executed = {
    platform_spec: true,
    swipe_spec: layoutType === 'swipe', // 仅 swipe 版式才跑 xiaohongshu.validateSwipeSpec
    overlong_image: true, // 非 swipe 版式直接跑；swipe 版式内含于滑动专项
    sensitive_word: true,
    ai_label: needAiLabel === null ? true : needAiLabel,
    rate_limit: true,
    artifact_spec: false // ★ 本步不传 products（C5 产物校验属 Step 14 投递前置）
  }
  const SKIP_REASON = {
    swipe_spec: '本次版式非 swipe，未执行滑动专项校验',
    ai_label: '当前平台未强制 AI 内容标识（needAiLabelFlag=0）',
    artifact_spec: '本次未传 products（产物校验属投递前置，Step 14）'
  }
  return COMPLIANCE_SOURCE_ORDER.map((key) => {
    const state = !executed[key] ? 'skipped' : present.has(key) ? 'issue' : 'pass'
    // ★ 未执行原因只在 `skipped` 上给出（其余状态给原因会与「已执行」自相矛盾）
    return {
      key,
      label: COMPLIANCE_SOURCE_MAP[key] || key,
      state,
      reason: state === 'skipped' ? SKIP_REASON[key] || '' : ''
    }
  })
}

/** 自定义敏感词输入（逗号分隔，兼容中英文逗号）→ 数组；空则返回 []（调用方不传该字段 → 后端默认词表） */
export function parseSensitiveWords(text) {
  return Array.from(
    new Set(
      String(text || '')
        .split(/[,，]/)
        .map((item) => item.trim())
        .filter(Boolean)
    )
  )
}

/** 统一封装 axios 错误文案（errCode + MSG.content），供 ErrorState 的「查看详情」用 */
function describeError(error) {
  return [error?.errCode ? `errCode: ${error.errCode}` : '', error?.MSG?.content || error?.message || '']
    .filter(Boolean)
    .join('\n')
}

/** rateLimit 子对象归一化（count / limitCount / windowSeconds 一律 Number()） */
function normalizeRateLimit(raw) {
  if (!raw || typeof raw !== 'object') return {}
  return {
    ...raw,
    limitCount: toNum(raw.limitCount),
    windowSeconds: toNum(raw.windowSeconds),
    count: toNum(raw.count)
  }
}

/**
 * P-09 取数与动作编排。
 * @param {{ getTopicCode: () => string }} options `getTopicCode` 取路由参数（`/compliance/:code` 的 code = topicCode）
 */
export function useComplianceCheck({ getTopicCode }) {
  const topic = ref(null)
  const result = ref(null)
  const loading = ref(false)
  const checking = ref(false)
  const error = ref('')
  const errorDetail = ref('')

  const layoutCatalog = ref([])
  const platformCatalog = ref([])
  const selectedPlatform = ref('')
  const sensitiveWordsText = ref('')

  /** 最近一次**实际下发**校验的平台 / 敏感词（用于提示「参数已改，点击重新校验生效」） */
  const lastCheckedPlatform = ref('')
  const lastCheckedWords = ref('')

  const renderJobLink = ref('')
  const splitting = ref(false)
  const applyingAiLabel = ref(false)

  /* ---------------- 派生状态 ---------------- */
  const issues = computed(() => (Array.isArray(result.value?.issues) ? result.value.issues : []))
  const errorIssues = computed(() => issues.value.filter((item) => String(item?.level) === 'ERROR'))
  const warnIssues = computed(() => issues.value.filter((item) => String(item?.level) === 'WARN'))
  const errorCount = computed(() => toNum(result.value?.errorCount))
  const warningCount = computed(() => toNum(result.value?.warningCount))
  const passed = computed(() => String(result.value?.passed ?? '') === '1')
  const checkedAt = computed(() => String(result.value?.checkedAt || ''))
  const rateLimit = computed(() => result.value?.rateLimit || {})
  const degraded = computed(() => String(rateLimit.value?.degraded ?? '') === '1')
  const showRateLimitNote = computed(
    () => degraded.value || issues.value.some((item) => String(item?.source) === 'rate_limit')
  )
  const platformOptions = computed(() => platformCatalog.value)
  const platformRecord = computed(
    () => platformCatalog.value.find((item) => item.platformCode === selectedPlatform.value) || null
  )
  const sourceStatuses = computed(() =>
    buildSourceStatuses({ issues: issues.value, data: result.value || {}, platformRecord: platformRecord.value })
  )
  const topicCode = computed(() => String(topic.value?.topicCode || getTopicCode() || ''))
  const topicTitle = computed(() => String(topic.value?.title || '未查询到主题'))
  const hasLayout = computed(() => Boolean(String(topic.value?.layoutCode || '').trim()))
  const dirty = computed(
    () =>
      (Boolean(lastCheckedPlatform.value) && selectedPlatform.value !== lastCheckedPlatform.value) ||
      sensitiveWordsText.value.trim() !== lastCheckedWords.value
  )
  /** 命中上下文的原文（仅在原文本可用时才按偏移切片；见 SensitiveHighlight.vue） */
  const fieldTexts = computed(() => ({
    title: String(topic.value?.title || ''),
    summary: String(topic.value?.summary || ''),
    description: String(topic.value?.description || ''),
    author: String(topic.value?.author || '')
  }))

  /** 「一键添加」AI 标识的可用性（裁定 I）：详述已转存文件 / 追加后会超 5000 字 → 不给按钮 */
  const aiLabelIssuePresent = computed(() => issues.value.some((item) => String(item?.source) === 'ai_label'))
  const aiLabelBlockReason = computed(() => {
    if (String(topic.value?.descriptionFileID || '')) return '详述已转存为文件，请到主题编辑页手动补充 AI 标识'
    const next = charCount(topic.value?.description || '') + AI_LABEL_MARKER.length + 2
    if (next > DESCRIPTION_MAX_CHARS) return '详述已达上限，请先精简'
    return ''
  })
  const aiLabelFit = computed(() => ({
    ok: aiLabelIssuePresent.value && !aiLabelBlockReason.value,
    reason: aiLabelBlockReason.value
  }))

  /* ---------------- 取数 ---------------- */
  async function fetchTopicRecord(code) {
    const first = await topicQry({ topicCode: code }, { silent: true })
    const list = Array.isArray(first?.data) ? first.data : []
    if (list.length) return list[0]
    const second = await topicQry({ recID: code }, { silent: true })
    const fallback = Array.isArray(second?.data) ? second.data : []
    return fallback[0] || null
  }

  /**
   * 目录取数（免登录端点；R-24：异常/空响应可能返回 `{}` → 一律 `res?.data || []`，由页面 EmptyState 兜底）。
   * ★ 复用 Step 9 的 `normalizeLayouts` / `normalizePlatforms`（禁止第二套归一化实现）。
   * ★ 全部 `silent: true`：失败原因由页面 ErrorState 呈现，不叠加全局 toast（通用约束 4）。
   */
  async function loadCatalogs() {
    const [layoutRes, platformRes] = await Promise.all([
      layoutQry({ beginNum: 0, endNum: 50 }, { silent: true }),
      platformQry({ beginNum: 0, endNum: 50 }, { silent: true })
    ])
    layoutCatalog.value = normalizeLayouts(layoutRes?.data)
    platformCatalog.value = normalizePlatforms(platformRes?.data)
  }

  /** 平台缺省：所选版式的 `ch_layout.platform` → `wechat_mp` → 目录首项（保证**非空**，否则后端 C7） */
  function defaultPlatform() {
    const codes = platformCatalog.value.map((item) => item.platformCode)
    const layout = layoutCatalog.value.find((item) => item.layoutCode === String(topic.value?.layoutCode || ''))
    const fromLayout = String(layout?.platform || '')
    if (fromLayout && (!codes.length || codes.includes(fromLayout))) return fromLayout
    if (codes.includes(DEFAULT_PLATFORM)) return DEFAULT_PLATFORM
    return codes[0] || DEFAULT_PLATFORM
  }

  /** 组装 `publishcheck` 入参：★ 不传 products（C5 产物校验留给 Step 14） */
  function buildParams() {
    const params = { topicCode: String(getTopicCode() || '') }
    const layoutCode = String(topic.value?.layoutCode || '')
    if (layoutCode) params.layoutCode = layoutCode
    if (selectedPlatform.value) params.platform = selectedPlatform.value
    const words = parseSensitiveWords(sensitiveWordsText.value)
    if (words.length) params.sensitiveWords = words
    return params
  }

  /** 重新校验（★ `silent: true`：自行渲染清单，不弹全局 toast；同一个请求即一次限流计数） */
  async function check() {
    if (!topic.value) return false
    checking.value = true
    try {
      const res = await publishCheck(buildParams(), { silent: true })
      const data = res?.data && typeof res.data === 'object' ? res.data : {}
      if (!Array.isArray(data.issues)) {
        console.error('[P-09] publishcheck 出参缺少 issues 数组，已按 [] 处理（R-24 空响应容错）', res?.data)
      }
      result.value = {
        ...data,
        issues: Array.isArray(data.issues) ? data.issues : [],
        issueCount: toNum(data.issueCount),
        errorCount: toNum(data.errorCount),
        warningCount: toNum(data.warningCount),
        assetCount: toNum(data.assetCount),
        sensitiveHitCount: toNum(data.sensitiveHitCount),
        rateLimit: normalizeRateLimit(data.rateLimit)
      }
      lastCheckedPlatform.value = selectedPlatform.value
      lastCheckedWords.value = sensitiveWordsText.value.trim()
      error.value = ''
      errorDetail.value = ''
      return true
    } catch (e) {
      result.value = null
      error.value = e?.MSG?.content || e?.message || '合规校验失败'
      errorDetail.value = describeError(e)
      console.error('[P-09] publishcheck 失败', e)
      return false
    } finally {
      checking.value = false
    }
  }

  /** 页面取数：主题详情 → 目录 → 平台缺省 → 首次校验 */
  async function load() {
    const code = String(getTopicCode() || '')
    if (!code) return
    loading.value = true
    error.value = ''
    errorDetail.value = ''
    renderJobLink.value = ''
    try {
      const record = await fetchTopicRecord(code)
      if (!record) {
        topic.value = null
        result.value = null
        error.value = `未查询到该主题（${code}）`
        return
      }
      topic.value = record
      await loadCatalogs()
      if (!selectedPlatform.value) selectedPlatform.value = defaultPlatform()
      await check()
    } catch (e) {
      topic.value = null
      result.value = null
      error.value = e?.MSG?.content || e?.message || '合规校验读取失败'
      errorDetail.value = describeError(e)
      console.error('[P-09] 合规校验取数失败', e)
    } finally {
      loading.value = false
    }
  }

  function updatePlatform(code) {
    selectedPlatform.value = String(code || '')
  }

  /**
   * 「标记通过」（裁定 J）：仅 `errorCount === 0` 可用；本机 `sessionStorage` 留痕（供 Step 14 门禁），
   * ★ **不调 `topicmodify` 写 `memo`**（避免污染自由文本字段；`ch_topic` 无合规状态列）。
   */
  function markPassed() {
    if (errorCount.value > 0) return false
    const code = String(topic.value?.topicCode || getTopicCode() || '')
    const payload = {
      passedAt: Date.now(),
      checkedAt: checkedAt.value,
      platform: selectedPlatform.value,
      layoutCode: String(topic.value?.layoutCode || '')
    }
    try {
      window.sessionStorage.setItem(`${MARK_PASS_STORAGE_PREFIX}${code}`, JSON.stringify(payload))
    } catch (e) {
      console.error('[P-09] 标记通过写入 sessionStorage 失败（隐私模式？）', e)
      return false
    }
    return true
  }

  /**
   * 「一键添加」AI 标识（裁定 I）：在 `description` **尾部**追加标准标识文案 → `topicmodify` → 重新校验。
   * ★ 依据：后端 `checkAiLabelIssues` 读 `topicData.aiLabel` **或** 正文/简介含 `AI_LABEL_MARKER_LIST`
   *   中的标识词；而 `ch_topic` **没有 aiLabel 列**（只有 aiFlag）→ 追加正文是**唯一可行**路径。
   */
  async function appendAiLabel() {
    if (!aiLabelFit.value.ok) return { ok: false, message: aiLabelBlockReason.value }
    const recID = String(topic.value?.recID || '')
    if (!recID) return { ok: false, message: '主题记录标识缺失' }
    const next = `${String(topic.value?.description || '').trimEnd()}\n\n${AI_LABEL_MARKER}`
    applyingAiLabel.value = true
    try {
      // ★ `silent: true`：失败原因由页面 toast 呈现（本页不叠加全局 toast，通用约束 4）
      const res = await topicModify({ recID, description: next }, { silent: true })
      // 双态兼容（P-ENV-01：topicmodify 属 move → 落 data；旧形态直接平铺）
      const record = res?.data?.data || res?.data
      topic.value = record?.recID ? { ...topic.value, ...record } : { ...topic.value, description: next }
      await check()
      return { ok: true, message: '' }
    } catch (e) {
      console.error('[P-09] 追加 AI 标识失败', e)
      return { ok: false, message: e?.MSG?.content || e?.message || '追加 AI 标识失败' }
    } finally {
      applyingAiLabel.value = false
    }
  }

  /**
   * 「重新渲染（渲染期自动切分）」（裁定 H）：`topicrender` 建 job，渲染期由 imageProc 按 `sliceHeight` 切分。
   * ★ 不传 `platform`（与版式 platform 冲突会得到 C7，与 useRenderTrigger 同口径）；
   * ★ 渲染为异步任务 → 完成后需再次「重新校验」，UI 不得宣称「该问题一定消除」。
   */
  async function startSplitRender() {
    const topicID = String(topic.value?.recID || '')
    if (!topicID) return { ok: false, jobCode: '', message: '主题记录标识缺失' }
    splitting.value = true
    try {
      const res = await topicRender({
        topicID,
        layoutCode: String(topic.value?.layoutCode || ''),
        renderMode: 'job'
      }, { silent: true })
      const jobCode = String(res?.data?.jobCode || '')
      renderJobLink.value = `/render-jobs?topicID=${encodeURIComponent(topicID)}`
      await check()
      return { ok: true, jobCode, message: '' }
    } catch (e) {
      console.error('[P-09] 发起渲染失败', e)
      return { ok: false, jobCode: '', message: e?.MSG?.content || e?.message || '发起渲染失败' }
    } finally {
      splitting.value = false
    }
  }

  /** 路由参数（topicCode）变化时重新取数（`/compliance/:code`） */
  watch(
    () => getTopicCode(),
    () => load(),
    { immediate: true }
  )

  return {
    // 数据
    topic,
    result,
    issues,
    errorIssues,
    warnIssues,
    errorCount,
    warningCount,
    passed,
    checkedAt,
    rateLimit,
    degraded,
    showRateLimitNote,
    sourceStatuses,
    fieldTexts,
    topicCode,
    topicTitle,
    hasLayout,
    dirty,
    aiLabelFit,
    // 目录与参数
    platformOptions,
    platformRecord,
    selectedPlatform,
    sensitiveWordsText,
    // 状态
    loading,
    checking,
    error,
    errorDetail,
    renderJobLink,
    splitting,
    applyingAiLabel,
    // 动作
    load,
    check,
    updatePlatform,
    markPassed,
    appendAiLabel,
    startSplitRender
  }
}
