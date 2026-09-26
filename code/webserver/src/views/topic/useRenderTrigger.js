/* ============================================================================
 * useRenderTrigger · Tab3 与外壳「提交渲染」的**共用编排**（Step 9 · 裁定 F 越界授权）
 * ----------------------------------------------------------------------------
 * 为什么必须独立成文件：外壳右上角的「提交渲染」（Step 7 交付）与本 Tab 的「发起渲染」是**同一个动作**，
 * 规范要求两者共用同一个 `RenderTriggerDialog.vue` 与同一套校验逻辑；若各写一份，必然出现两套阈值
 * 与两个弹窗。故把下面四件事收敛到本文件：
 *   1) **目录取数**：`layoutqry` / `platformqry`（免登录端点）→ 归一化；
 *   2) **版式落库**：`topicmodify({ recID, layoutCode })`，选择即静默保存（debounce 300ms）；
 *   3) **前置校验**：`buildRenderChecks()`（前端先拦，后端 `_checkRenderReadiness` 兜底）；
 *   4) **发起渲染**：`topicmodify(status='RENDERING')` → `topicrender`（默认 `renderMode='job'`）。
 *
 * ★ 单文件 ≤ 600 行（§2.1 硬约束；2026-09-21 起统一口径，见附录 G v1.3）。
 *
 * 后端事实（服从，不得按计划文字臆断）：
 *   · 裁定 B：`ch_topic` **无 platform 列** → 平台只能由所选版式经 `ch_layout.platform` 推导；
 *     调 `topicrender` 时**省略 platform**（传与版式冲突的值会得到 `C7`）；
 *   · 裁定 I：`topicmodify` 返回 `C4`/`C6` 时**不得继续**调 `topicrender`（本文件靠 try/catch 顺序保证）；
 *   · 裁定 C：`specJson` 是 JSON **字符串**、数值字段（`sortWeight`/`imageMaxCount`…）是**字符串**
 *     → 一律 `JSON.parse` / `Number()`（解析失败按 `{}` 并 console.error，不抛错中断渲染）；
 *   · 裁定 A：选择版式即静默保存（debounce 300ms），失败只 toast（http.js 统一弹 `MSG.content`）
 *     且**不回滚 UI 选中态**；裁定 J：`specOverride` 只随本次请求下发，不写回任何表；
 *   · 附录 B R-24：`layoutqry` / `platformqry` 在「未登录 + 带任意参数」时返回空对象 `{}`（无 errCode），
 *     故本文件不传业务参数，且一律 `res.data || []`，数据为空由页面用 EmptyState 说明（不白屏、不抛错）；
 *   · 附录 B R-08：`ch_layout` 种子每版式只登记一个平台，比矩阵窄 —— 可用性**以矩阵为准**
 *     （`isLayoutAllowed`），漂移由 `detectMatrixDrift()` 记录（调用点见 TabLayout.vue）。
 * ========================================================================== */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'vue3-toastify'
import { layoutQry } from '@/api/layout'
import { platformQry } from '@/api/platform'
import { topicRender } from '@/api/render'
import { topicModify } from '@/api/topic'
import { isLayoutAllowed, PLATFORM_MAP, PLATFORM_ORDER } from '@/config/chOptions'

/** 详述字数上限（§2.7 主题字段区间）。
 *  ★ 2026-09-22 裁定：**去掉 2000 字下限** —— 详述可留空、可短写，不再设区间下限；
 *    5000 仍为「库内正文」上限，超出部分由服务端转存为文件（写 `descriptionFileID`）。
 *    后端 `_checkRenderReadiness` 当下只在「无正文且无 descriptionFileID」时返回 `C4`。 */
export const DETAIL_MAX = 5000
/** `swipe_v1` 张数缺省上限（specJson.maxCount 缺失时的兜底，与 §2.7 版式种子一致） */
export const SWIPE_FALLBACK_MAX_COUNT = 18

/** 安全字符串化（null / undefined → 空串） */
const str = (value) => (value === null || value === undefined ? '' : String(value))

/** 开关类字段（`'0'` / `'1'`）归一化，缺省按 `'0'` */
const flag = (value) => str(value ?? '0')

/** 宽松数值转换：字符串/数字/空值一律安全转 Number（后端数值字段以字符串返回） */
export const toNum = (value, fallback = 0) => {
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}

/** 按 `{ 字段名: 转换器 }` 批量拷贝，避免逐字段样板 */
const pick = (source, schema) =>
  Object.fromEntries(Object.entries(schema).map(([key, cast]) => [key, cast(source?.[key])]))

/** `specJson`（JSON **字符串**）→ 对象；失败按 `{}` 处理并 console.error，**不得抛错** */
export function parseSpecJson(raw) {
  if (raw === null || raw === undefined || raw === '') return {}
  if (typeof raw === 'object') return raw
  try {
    const parsed = JSON.parse(String(raw))
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch (error) {
    console.error('[P-05] specJson 解析失败，已按 {} 处理（不中断渲染）', { raw, error })
    return {}
  }
}

const LAYOUT_SCHEMA = {
  recID: str,
  layoutCode: str,
  layoutName: str,
  layoutType: str,
  platform: str,
  outputKind: str,
  sortWeight: (value) => toNum(value, 100)
}

const PLATFORM_SCHEMA = {
  recID: str,
  platformCode: str,
  platformName: str,
  subjectScope: str,
  deliverMode: str,
  titleMaxLen: toNum,
  summaryMaxLen: toNum,
  imageMaxCount: toNum,
  coverSpec: str,
  imageSpec: str,
  limitNote: str,
  docUrl: str,
  allowSvgFlag: flag,
  needAiLabelFlag: flag,
  autoPublishFlag: flag
}

/** 版式列表归一化：`enabled='1'` 过滤 → 数值转 Number → specJson 解析 → `sortWeight` 升序（裁定 C） */
export function normalizeLayouts(rows) {
  return (Array.isArray(rows) ? rows : [])
    .filter((row) => str(row?.enabled ?? '1') === '1')
    .map((row) => ({
      ...pick(row, LAYOUT_SCHEMA),
      spec: parseSpecJson(row?.specJson)
    }))
    .sort((a, b) => a.sortWeight - b.sortWeight)
}

/** 平台列表归一化：★ 所有数值字段以字符串返回，一律 `Number()` 后再用于展示/计算（裁定 D） */
export function normalizePlatforms(rows) {
  const orderOf = (code) => {
    const index = PLATFORM_ORDER.indexOf(code)
    return index < 0 ? PLATFORM_ORDER.length : index
  }
  return (Array.isArray(rows) ? rows : [])
    .filter((row) => str(row?.enabled ?? '1') === '1')
    .map((row) => pick(row, PLATFORM_SCHEMA))
    .sort((a, b) => orderOf(a.platformCode) - orderOf(b.platformCode))
}

/** 平台字典兜底（`platformqry` 返回空对象时仅供筛选器可用，矩阵仍显示 EmptyState） */
export function fallbackPlatformOptions() {
  return PLATFORM_ORDER.map((code) => ({
    platformCode: code,
    platformName: PLATFORM_MAP[code]?.label || code
  }))
}

/** 单图比例键（4 位小数）；缺宽高返回空串（真实 `topicassetqry` 无 width/height 列，Step 7 已登记） */
export function ratioKeyOf(item) {
  const width = toNum(item?.width)
  const height = toNum(item?.height)
  return width > 0 && height > 0 ? (width / height).toFixed(4) : ''
}

/**
 * 比例一致性：以**第 1 张为基准**（第 1 张即 App 内封面 / 首屏）。
 * @returns {{ ok: boolean, skipped: boolean, baseline: string, indexes: number[] }}
 *   `skipped=true` 表示附图未返回宽高，前端无法判定（不阻断，交由后端 `D1` 兜底）。
 */
export function checkRatioUniform(assets) {
  const keys = (Array.isArray(assets) ? assets : []).map(ratioKeyOf)
  if (keys.some((key) => !key)) return { ok: true, skipped: true, baseline: '', indexes: [] }
  const baseline = keys[0] || ''
  const indexes = keys.map((key, index) => (key !== baseline ? index + 1 : 0)).filter(Boolean)
  return { ok: indexes.length === 0, skipped: false, baseline, indexes }
}

/** 版式 × 平台矩阵漂移（R-08）：矩阵允许、但 `ch_layout` 未登记该平台的组合 */
export function detectMatrixDrift(layouts, platform) {
  const code = str(platform)
  if (!code) return []
  return (Array.isArray(layouts) ? layouts : [])
    .filter((item) => item.layoutCode && item.platform && item.platform !== code && isLayoutAllowed(item.layoutCode, code))
    .map((item) => ({ layoutCode: item.layoutCode, matrixPlatform: code, registeredPlatform: item.platform }))
}

/**
 * 发起渲染前置校验（裁定 E）：素材 ≥1 / 版式已选 / 详述 2000–5000 /
 * `swipe_v1` 比例统一且张数 ≤ min(specJson.maxCount, ch_platform.imageMaxCount) /
 * `longimage_v1` 整篇同比例。任一不满足 → 按钮禁用 + Tooltip 说明（不得只在点击后报错）。
 * @returns {Array<{ key: string, label: string, ok: boolean, reason: string }>}
 */
export function buildRenderChecks(ctx) {
  const list = Array.isArray(ctx.assets) ? ctx.assets : []
  const code = str(ctx.layoutCode)
  const words = toNum(ctx.words)
  const platformMax = ctx.platform ? toNum(ctx.platform.imageMaxCount) : 0
  const ratio = checkRatioUniform(list)
  const checks = [
    {
      key: 'assets',
      label: '素材',
      ok: list.length >= 1,
      reason: list.length >= 1 ? `已绑定 ${list.length} 张附图` : '需至少 1 张附图：请先到「素材」页添加'
    },
    {
      key: 'layout',
      label: '版式',
      ok: Boolean(code) && Boolean(ctx.layout),
      reason: !code
        ? '未选择版式：请在上方选择版式卡片'
        : ctx.layout
          ? `${ctx.layout.layoutName}（${code}）`
          : `版式 ${code} 未在 ch_layout 中登记（配置数据暂不可用）`
    },
    {
      key: 'description',
      label: '详述',
      ok: Boolean(ctx.hasDescriptionFile) || (words > 0 && words <= DETAIL_MAX),
      reason: ctx.hasDescriptionFile
        ? '详述已转存文件（全文口径，跳过字数判定）'
        : words === 0
          ? '详述为空且无 descriptionFileID（后端返回 C4）'
          : words > DETAIL_MAX
            ? `${words} 字，超出上限 ${DETAIL_MAX} 字（先保存即可转存为文件）`
            : `${words} 字（上限 ${DETAIL_MAX} 字，无下限）`
    }
  ]

  if (code === 'swipe_v1' || code === 'longimage_v1') {
    checks.push({
      key: 'ratio',
      label: code === 'swipe_v1' ? '比例统一（swipe_v1）' : '整篇同比例（longimage_v1）',
      ok: ratio.ok,
      reason: ratio.skipped
        ? '附图未返回宽高信息，比例校验已跳过（真实 topicassetqry 无 width/height 列）'
        : ratio.ok
          ? `各图比例一致（基准 ${ratio.baseline}）`
          : `第 ${ratio.indexes.join('、')} 张比例不一致，整篇须同一比例`
    })
  }

  if (code === 'swipe_v1') {
    const specMax = toNum(ctx.layout?.spec?.maxCount, SWIPE_FALLBACK_MAX_COUNT) || SWIPE_FALLBACK_MAX_COUNT
    const limit = platformMax > 0 ? Math.min(specMax, platformMax) : specMax
    const source = platformMax > 0
      ? `min(specJson.maxCount ${specMax}, imageMaxCount ${platformMax})`
      : `specJson.maxCount ${specMax}（ch_platform 数据暂不可用，未参与取小）`
    checks.push({
      key: 'count',
      label: '张数上限（swipe_v1）',
      ok: list.length <= limit,
      reason: list.length <= limit
        ? `当前 ${list.length} 张 ≤ 上限 ${limit} 张（${source}）`
        : `当前 ${list.length} 张，超出上限 ${limit} 张（${source}）`
    })
  }

  return checks
}

/**
 * 由外壳（TopicEdit.vue）**唯一实例化**；Tab 内按钮只 emit 到外壳，不另建实例（裁定 F）。
 * @param {object} options
 * @param {() => object|null} options.getTopic 当前主题（服务端记录，含 recID / layoutCode）
 * @param {() => Array} options.getAssets 附图列表（与 Tab2 共享同一份状态，裁定 G）
 * @param {() => number} options.getWords 详述实时字数（外壳 wordCount 口径）
 * @param {() => Promise<boolean>} options.beforeSubmit 提交前落库草稿差量（失败即中止）
 * @param {(patch: object) => void} options.onTopicPatch 以服务端语义回写主题局部字段
 * @param {(error: object) => string} options.onFieldError 服务端 C4/C6 → 字段行内回显，返回命中字段名
 */
export function useRenderTrigger(options = {}) {
  const router = useRouter()
  const { getTopic, getAssets, getWords, beforeSubmit, onTopicPatch, onFieldError } = options
  const patchTopic = typeof onTopicPatch === 'function' ? onTopicPatch : () => {}

  const layouts = ref([])
  const platforms = ref([])
  const catalogLoading = ref(false)
  const catalogLoaded = ref(false)
  const catalogError = ref('')
  const dialogVisible = ref(false)
  const submitting = ref(false)
  const layoutSaving = ref(false)
  const layoutSavedAt = ref('')
  /** 已落库的版式基线（乐观高亮后据此判断是否真需要写库） */
  const savedLayoutCode = ref('')
  let layoutTimer = null

  const topic = computed(() => getTopic() || null)
  const assets = computed(() => (Array.isArray(getAssets()) ? getAssets() : []))
  const layoutCode = computed(() => str(topic.value?.layoutCode).trim())
  const layout = computed(() => layouts.value.find((item) => item.layoutCode === layoutCode.value) || null)
  /** `ch_topic` 无 platform 列（裁定 B）：由 `ch_layout.platform` 推导，缺失时退化为矩阵首个允许平台 */
  const platformCode = computed(() => {
    if (layout.value?.platform) return layout.value.platform
    return layoutCode.value ? PLATFORM_ORDER.find((code) => isLayoutAllowed(layoutCode.value, code)) || '' : ''
  })
  const platform = computed(() => platforms.value.find((item) => item.platformCode === platformCode.value) || null)
  const checks = computed(() =>
    buildRenderChecks({
      layoutCode: layoutCode.value,
      layout: layout.value,
      platform: platform.value,
      assets: assets.value,
      words: typeof getWords === 'function' ? getWords() : 0,
      hasDescriptionFile: Boolean(str(topic.value?.descriptionFileID))
    })
  )
  const blockedReason = computed(() => {
    const failed = checks.value.find((item) => !item.ok)
    return failed ? `${failed.label}：${failed.reason}` : ''
  })
  const canRender = computed(() => checks.value.every((item) => item.ok))

  /** 目录取数：★ R-24 → 不传业务参数；空响应一律 `data || []`，不抛错、不白屏 */
  async function ensureCatalog(force = false) {
    if (catalogLoading.value) return
    if (catalogLoaded.value && !force) return
    catalogLoading.value = true
    catalogError.value = ''
    const [layoutResult, platformResult] = await Promise.allSettled([layoutQry(), platformQry()])
    if (layoutResult.status === 'fulfilled') layouts.value = normalizeLayouts(layoutResult.value?.data)
    if (platformResult.status === 'fulfilled') platforms.value = normalizePlatforms(platformResult.value?.data)
    if (layoutResult.status === 'rejected' || platformResult.status === 'rejected') {
      catalogError.value =
        layoutResult.reason?.MSG?.content || platformResult.reason?.MSG?.content || '版式 / 平台配置读取失败'
      console.error('[P-05] 版式 / 平台配置读取失败', layoutResult.reason, platformResult.reason)
    } else if (!layouts.value.length || !platforms.value.length) {
      console.error('[P-05] 配置数据为空，页面将降级为 EmptyState（附录 B R-24）', {
        layoutCount: layouts.value.length,
        platformCount: platforms.value.length
      })
    }
    catalogLoaded.value = true
    catalogLoading.value = false
  }

  /** 真正写库（裁定 A）：失败只保留 UI 选中态，不清空用户选择 */
  async function applyLayoutCode(code) {
    const next = str(code).trim()
    const recID = str(topic.value?.recID)
    if (!next || !recID || next === savedLayoutCode.value) return false
    layoutSaving.value = true
    try {
      const res = await topicModify({ recID, layoutCode: next })
      const record = res?.data?.data || res?.data || {}
      savedLayoutCode.value = str(record.layoutCode) || next
      patchTopic({ layoutCode: savedLayoutCode.value })
      layoutSavedAt.value = new Date().toTimeString().slice(0, 8)
      console.info('[P-05] 版式已落库 topicmodify', { recID, layoutCode: savedLayoutCode.value })
      return true
    } catch (error) {
      // 非 B0 已由 http.js 统一 toast MSG.content；此处**不回滚** UI 选中态（§2.5 不清空用户输入）
      console.error('[P-05] 版式落库失败（保留 UI 选中态，待重试）', { recID, layoutCode: next, error })
      return false
    } finally {
      layoutSaving.value = false
    }
  }

  /** 选择版式：立即高亮（乐观），debounce 300ms 静默保存（裁定 A） */
  function selectLayoutCode(code) {
    const next = str(code).trim()
    if (!next) return
    patchTopic({ layoutCode: next })
    layoutSavedAt.value = ''
    if (layoutTimer) clearTimeout(layoutTimer)
    layoutTimer = setTimeout(() => {
      layoutTimer = null
      applyLayoutCode(next)
    }, 300)
  }

  function openDialog() {
    dialogVisible.value = true
  }

  function closeDialog() {
    dialogVisible.value = false
  }

  /** 发起渲染：`job`（默认，建任务）/ `sync`（同步等待），裁定 B + I + J */
  async function submit(payload = {}) {
    const isJob = payload.renderMode !== 'sync'
    const specOverride = payload.specOverride && Object.keys(payload.specOverride).length ? payload.specOverride : null
    if (submitting.value) return false
    if (!canRender.value) {
      toast.warning(blockedReason.value)
      return false
    }
    if (typeof beforeSubmit === 'function' && !(await beforeSubmit())) return false

    const recID = str(topic.value?.recID)
    const topicCode = str(topic.value?.topicCode) || recID
    if (!recID) {
      toast.error('主题尚未加载完成，无法发起渲染')
      return false
    }

    submitting.value = true
    try {
      // ① 先跃迁状态：后端在此做 _checkRenderReadiness 强校验（C4/C6 时**不会**进入 ②）
      await topicModify({ recID, status: 'RENDERING' })
      patchTopic({ status: 'RENDERING' })
      // ② ★ 裁定 B：省略 platform（后端缺省取 ch_layout.platform）；★ 裁定 J：specOverride 不落库
      const res = await topicRender({
        topicID: recID,
        topicCode,
        layoutCode: layoutCode.value,
        renderMode: isJob ? 'job' : 'sync',
        ...(specOverride ? { specOverride } : {})
      })
      const data = res?.data || {}
      dialogVisible.value = false
      if (isJob) {
        toast.success(`已创建渲染任务 ${data.jobCode || ''}（${data.jobStatus || 'PENDING'}）`)
        router.push({ name: 'RenderJobs', query: { topicID: recID } })
      } else {
        toast.success('同步渲染已完成，正在跳转预览')
        router.push({
          name: 'Preview',
          params: { code: topicCode },
          query: { platform: platformCode.value, layoutCode: layoutCode.value }
        })
      }
      return true
    } catch (error) {
      const field = typeof onFieldError === 'function' ? onFieldError(error) : ''
      if (field) return false // C4/C6：字段行内回显，弹窗保持打开、不清空用户输入
      // 状态已置 RENDERING 但渲染未发起成功 → 回退草稿（状态机允许 RENDERING → DRAFT）
      try {
        await topicModify({ recID, status: 'DRAFT' })
        patchTopic({ status: 'DRAFT' })
        toast.warning('渲染未发起成功，已回退为草稿状态')
      } catch (innerError) {
        console.error('[P-05] 回退草稿状态失败', innerError)
      }
      return false
    } finally {
      submitting.value = false
    }
  }

  /** 主题切换时重设版式基线（★ 回显以 `topicqry` 返回的 layoutCode 为准，裁定 A） */
  watch(
    () => str(topic.value?.recID),
    () => {
      savedLayoutCode.value = str(topic.value?.layoutCode)
      layoutSavedAt.value = ''
    },
    { immediate: true }
  )

  onBeforeUnmount(() => {
    if (layoutTimer) clearTimeout(layoutTimer)
  })

  return {
    layouts,
    platforms,
    catalogLoading,
    catalogError,
    dialogVisible,
    submitting,
    layoutSaving,
    layoutSavedAt,
    layoutCode,
    layout,
    platform,
    platformCode,
    checks,
    canRender,
    blockedReason,
    ensureCatalog,
    selectLayoutCode,
    applyLayoutCode,
    openDialog,
    closeDialog,
    submit
  }
}

export default useRenderTrigger
