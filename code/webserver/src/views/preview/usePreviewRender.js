/* ============================================================================
 * usePreviewRender · P-08 预览页「取数 + 归一化 + 形态映射」（Step 10）
 * ----------------------------------------------------------------------------
 * 【越界授权登记（裁定 J）】本文件**不在** Step 10 产出清单内，登记为越界授权文件：
 *   `Preview.vue` 只做编排与渲染分支；取数（`topicqry` / `layoutqry` / `topicrender`）、
 *   出参归一化、平台 → 预览形态映射、可用版式/平台集合（R-08 矩阵口径）收敛到本文件，
 *   以满足「单文件 ≤ 600 行」（§2.1）硬约束。
 *
 * 【后端事实（已核源码，服从；不得凭计划文字臆断）】
 *   · processor/renderService.py:752-765 `renderTopic`：
 *       `topicID`/`recID`/`topicCode` 三者之一必填（缺 → C4）；`layoutCode` 必填（缺 → C4）；
 *       `platform` 可选（缺省取 `ch_layout.platform`）；`renderMode` 默认 `sync`；
 *       ★ `specOverride` **仅 sync 生效**（job 模式后端忽略）→ 本页一律 `renderMode='sync'`（裁定 H）；
 *       ★ `inputHash` 命中既有 DONE 任务 → 直接复用产物并返回 `reused='1'`（**字符串**）：
 *         裁定 F 只做文案提示，**不重试、不加缓存破坏参数**；
 *       ★ sync 会真实写 `ch_artifact` 台账（设计内行为，前端不做额外解释）。
 *   · engine/layoutEngine.py:88-99 `PREVIEW_TEMPLATE_MAP`：允许值
 *       `wechat` / `wechat_mp` / `xiaohongshu` / `xhs`（:743 `.lower()` → **大小写不敏感**）；
 *       未知值 → `E0`（:745-748）。包裹后的 HTML **自带手机框节点**
 *       `data-preview="<kind>"` + `data-phone-screen`，并含主题标题。
 *   · processor/platformAdapter/wechatMp.py:180-190：`previewKind` **无条件**生效；
 *     meta 含 `inlineStyled` / `classFree` / **`interactionDegraded`（字符串 '1'/'0'）** /
 *     `imageCount` / `needUploadCount` / `transferredImageCount` / `specCheck`。
 *   · processor/platformAdapter/generic.py:196-214：meta 含 **`degradedImpl='stack_v1_reuse'`**；
 *     `previewKind` 仅在 `outputKind === 'html'` 时生效。
 *   · processor/platformAdapter/xiaohongshu.py:197-370：★ **不处理 `previewKind`**（只按 layoutType 分派）；
 *     出参 `outputKind:'png'` + `content`（**未包裹**的 HTML）+ `products[]`
 *     （`seqNo/kind/fileID/fileUrl/width/height/sizeBytes/sha256/isCover`；fileID 已由 `renderService`
 *     经 `fillFileUrls` 转成 `fileUrl`）。
 *   · engine/layoutEngine.py:438-470（carousel 降级）：降级后 HTML 含 `data-degraded="static_fallback"`
 *     且**移除翻页控件**（`data-carousel-controls`）；`spec` 键为
 *     `size`/`ratio`/`maxCount`/`allowSvg`/`needStaticFallback`。
 *   · 数值形态（2026-09-21 实测，附录 B R-26）：数值与 JSON 字段均为**字符串**
 *     （`meta.imageCount:'8'`、`products[].width:'1080'`）→ 比较前一律 `Number()`；
 *     `ch_layout.specJson` 是 JSON **字符串** → `JSON.parse`。
 *   · 附录 B R-24：免登录端点带业务参数可能返回**空对象 `{}`**（无 errCode）→
 *     一律 `res?.data || []`，不抛错、不白屏；配置为空由页面用 EmptyState 说明。
 * ========================================================================== */
import { ref } from 'vue'
import { layoutQry } from '@/api/layout'
import { topicQry } from '@/api/topic'
import { topicRender } from '@/api/render'
import { LAYOUT_PLATFORM_MATRIX, PLATFORM_ORDER, errText, isLayoutAllowed } from '@/config/chOptions'
/* 复用 Step 9 的归一化实现（**只 import，不修改 Step 9 文件**）：
 * `normalizeLayouts` 已处理 `enabled` 过滤 / `sortWeight` 字符串转数 / `specJson` JSON.parse（R-26） */
import { normalizeLayouts, toNum } from '@/views/topic/useRenderTrigger'

/** 预览渲染模式：一律 sync（裁定 H；且 `specOverride` 仅 sync 生效） */
export const PREVIEW_RENDER_MODE = 'sync'

/**
 * ★ 平台 → 预览形态（`previewKind`）的**最终映射**（裁定 A 的落地结果）：
 *   · `wechat_mp`   → `'wechat'`  → 后端用 `preview/wechat_mp.html` 包裹**已渲染片段**，
 *                     返回**已含手机框**（`data-preview` + `data-phone-screen`）的片段；
 *   · `generic`     → `'wechat'`  → 同为 HTML 类片段、同一模板（`PREVIEW_TEMPLATE_MAP` 无 generic 专属模板）。
 *                     ★ 两项可选（传 `'wechat'` 得包裹片段 / 传空得未包裹片段），本页**固定选前者**：
 *                       裁定 B 要求「HTML 类平台的手机框由后端片段自带，前端只提供 .preview-scope 浅色容器」，
 *                       若对 generic 传空则必须由前端补框，会出现两套 HTML 呈现路径。
 *                       已知副作用（待确认项）：手机框顶部平台名取自模板常量，会显示「微信公众号」，
 *                       与 generic 平台不符；后端未提供 generic 预览模板前无法修正。
 *   · `xiaohongshu` → `''`（**不传** `previewKind`）→ 适配器本就不消费该参数（xiaohongshu.py:197-370）；
 *                     出参 `content` 是**未包裹的原始 HTML**，★ **禁止**当作手机框片段注入，
 *                     改用 `products[].fileUrl` 渲染图片集（swipe_v1 → 滑动多图集；其余 → 长图）。
 */
export const PREVIEW_KIND_MAP = {
  wechat_mp: 'wechat',
  generic: 'wechat',
  xiaohongshu: ''
}

/** 安全字符串化（null / undefined → 空串） */
export const str = (value) => (value === null || value === undefined ? '' : String(value))
/** 开关类字段（'0' / '1'）归一化字符串，**不做布尔转换**（后端以字符串返回） */
const flag = (value) => str(value ?? '0')
/** 去掉末尾多余分号（§2.5 第 3 条：toast 文案口径） */
const trimTail = (text) => str(text).trim().replace(/[;；]+$/, '')

/** 平台 → `previewKind`（未知平台返回空串 = 不传该字段） */
export function previewKindOf(platform) {
  return PREVIEW_KIND_MAP[str(platform)] || ''
}

/** 该版式允许的平台（**以矩阵为准**，§2.7 / 裁定 C；未知组合为空 → 兜底返回全部三档） */
export function availablePlatforms(layoutCode) {
  const code = str(layoutCode)
  if (!code) return [...PLATFORM_ORDER]
  const allowed = PLATFORM_ORDER.filter((platform) => isLayoutAllowed(code, platform))
  return allowed.length ? allowed : [...PLATFORM_ORDER]
}

/** 版式登记的平台（`ch_layout.platform`），矩阵不允许时回落矩阵首个允许平台（裁定 B） */
export function defaultPlatform(layoutCode, catalog) {
  const code = str(layoutCode)
  if (!code) return ''
  const hit = (Array.isArray(catalog) ? catalog : []).find((item) => item.layoutCode === code)
  if (hit?.platform && isLayoutAllowed(code, hit.platform)) return hit.platform
  return availablePlatforms(code)[0] || ''
}

/**
 * 指定平台下的可用版式（**矩阵 ∪ ch_layout**）：
 * R-08 → `ch_layout` 种子每版式只登记一个平台，比矩阵窄，故**以矩阵为准**并补充目录中登记的版式；
 * 仅矩阵有、目录未登记的版式以 `matrixOnly=true` 占位（名称留空，由页面回落到 layoutCode）。
 */
export function availableLayouts(platform, catalog) {
  const code = str(platform)
  const list = Array.isArray(catalog) ? catalog : []
  const known = new Set(list.map((item) => item.layoutCode))
  const placeholders = Object.keys(LAYOUT_PLATFORM_MATRIX)
    .filter((layoutCode) => !known.has(layoutCode))
    .map((layoutCode) => ({
      recID: '',
      layoutCode,
      layoutName: '',
      layoutType: '',
      platform: '',
      outputKind: '',
      sortWeight: Number.MAX_SAFE_INTEGER,
      spec: {},
      matrixOnly: true
    }))
  return [...list, ...placeholders].filter((item) => item.layoutCode && isLayoutAllowed(item.layoutCode, code))
}

/** 产物归一化：数值字段一律 `Number()`（R-26；`fileUrl` 由后端 `fillFileUrls` 提供，2.4.5） */
export function normalizeProducts(raw) {
  return (Array.isArray(raw) ? raw : []).map((item, index) => ({
    seqNo: toNum(item?.seqNo, index + 1),
    kind: str(item?.kind),
    fileID: str(item?.fileID),
    fileUrl: str(item?.fileUrl || item?.url),
    width: toNum(item?.width),
    height: toNum(item?.height),
    sizeBytes: toNum(item?.sizeBytes),
    sha256: str(item?.sha256),
    isCover: flag(item?.isCover ?? '0')
  }))
}

/** 单图比例键（4 位小数）；宽高缺失返回空串（无法判定，不阻断） */
export function ratioKeyOf(product) {
  const width = toNum(product?.width)
  const height = toNum(product?.height)
  return width > 0 && height > 0 ? (width / height).toFixed(4) : ''
}

/**
 * 比例一致性（小红书 swipe / longimage「App 内滑动会跳动」判据）：
 * @returns {{ skipped: boolean, mismatch: boolean, indexes: number[] }}
 *   `skipped=true` 表示产物未返回宽高，前端无法判定（不提示，交后端 `D1` 兜底）。
 */
export function checkRatioUniform(products) {
  const keys = (Array.isArray(products) ? products : []).map(ratioKeyOf)
  if (!keys.length || keys.some((key) => !key)) return { skipped: true, mismatch: false, indexes: [] }
  const baseline = keys[0]
  const indexes = keys.map((key, index) => (key !== baseline ? index + 1 : 0)).filter(Boolean)
  return { skipped: false, mismatch: indexes.length > 0, indexes }
}

/**
 * 出参归一化（`topicrender` 出参 → 页面消费形态）。
 *
 * ★★ 出参信封形态（**现状**：出参信封统一改造 P-ENV-01，2026-09-21 远端实测已生效）：
 *   · `topicrender` 属 ch_* 域 **move** 形态 → 业务字段整体迁入 `data`
 *     （`data = { content, meta, products, fileIDs, reused, outputKind, jobCode, previewKind, … }`）；
 *     ★ 失败路径原先自带的 `data`（`jobID`/`jobCode` 诊断信息）随迁为 **`data.data`**，语义零改动；
 *   · `topicqry` / `layoutqry` / `artifactqry` 等 14 个查询类为 **keep**（`data` 为数组，位置不变）；
 *   · `getuserinfo` / `accounthealth` / `login` 等 account 域为 **copy**（顶层保留 + `data` 副本）。
 *
 * ★ 本函数仍按「信封顶层 ⊕ `data` 内层（内层优先，数组不参与合并）」两侧取值，原因有三：
 *   ① 灰度/回滚期旧部署仍是**平铺**（改造前 `topicrender` 顶层无 `data` 键）—— 只读 `res.data`
 *      会拿到空 content / 空 meta（本步首轮联调即在此失败，改造前后都必须工作）；
 *   ② move 形态下 `data.data` 双层键存在，顶层 ⊕ 内层合并对两层都安全；
 *   ③ 合并成本极低，且**不依赖**信封印花（`CMD`/`msgKey`/`MSG`/`errCode`/`SN`/`YMDHMS` 不参与业务取值）。
 */
export function normalizeRenderResult(res, request) {
  const envelope = res && typeof res === 'object' ? res : {}
  const inner = envelope.data && typeof envelope.data === 'object' && !Array.isArray(envelope.data) ? envelope.data : null
  const data = inner ? { ...envelope, ...inner } : envelope
  const meta = data.meta && typeof data.meta === 'object' ? data.meta : {}
  const products = normalizeProducts(data.products)
  return {
    request,
    content: str(data.content),
    meta,
    products,
    reused: flag(data.reused),
    fileIDs: Array.isArray(data.fileIDs) ? data.fileIDs.map(str) : products.map((item) => item.fileID),
    // 归一化后的数值视图（字符串 → Number，R-26）
    metrics: {
      /**
       * ★★ 平台形态产物类型：**必须优先取业务层的 `outputKind`**（即合并后对象的顶层业务键，
       *   改造后位于 `data.outputKind`；2026-09-21 实测）：
       *   业务层 `outputKind` = 本次「版式 × 平台」的产物形态（如请求 `wechat_mp + longimage_v1`
       *   → `'html'`，片段是**带手机框的 HTML**）；
       *   而 `meta.outputKind` / `meta.platform` 是**引擎侧口径**（= `ch_layout` 登记的
       *   `outputKind`/`platform`，上例为 `'png'`/`'xiaohongshu'`）—— 据此判定会误走 PNG 图集分支。
       *   故 `meta.platform` 一律不作为平台判据，平台以路由/`ch_layout` 推导值为准。
       */
      outputKind: str(data.outputKind) || str(meta.outputKind),
      layoutType: str(meta.layoutType),
      artifactKind: str(meta.artifactKind),
      imageCount: toNum(meta.imageCount),
      needUploadCount: toNum(meta.needUploadCount),
      transferredImageCount: toNum(meta.transferredImageCount ?? 0),
      interactionDegraded: flag(meta.interactionDegraded),
      degradedImpl: str(meta.degradedImpl),
      inlineStyled: flag(meta.inlineStyled),
      classFree: flag(meta.classFree),
      specCheck: str(meta.specCheck)
    }
  }
}

/** 错误码 → ErrorState 的「原因 + 提示」文案（§2.5；默认走后端 MSG.content） */
const ERROR_HINT = {
  E0: '模板缺失或版式不支持：请确认该「版式 × 平台」组合是否可用（矩阵口径）。',
  E1: '渲染失败：请检查素材与详述内容后重试。',
  E2: '截图超时：可稍后重试，或改用图片更少的版式。',
  E3: '产物生成失败：请稍后重试。',
  E4: '外链图片需转存到平台域名，但存储凭据缺失：请到「账号管理」登记或修复凭据后重试。',
  C4: '缺少必要参数：该「版式 × 平台」组合缺少必需数据（如小红书至少需要 1 张附图），请先在主题编辑页补齐后重试。',
  C7: '后端判定该「版式 × 平台」组合不受支持（前端矩阵允许，属附录 B R-08 的种子漂移）。',
  CB: '未查询到该主题。',
  BI: '记录标识无效：请从主题库重新进入。'
}

/**
 * 任意 HTTP / 业务异常 → `{ code, message, hint, detail }`。
 * ★ 真实后端存在「顶层无 `errCode`、只在 `MSG.errCode` 给出」的路径
 *   （2026-09-21 实测：非法 `previewKind` → 信封无 `errCode`，仅 `MSG:{errCode:'ERR_GENERAL', content:'exception. unknow error. ERR_GENERAL'}`），
 *   故错误码取值链为 `errCode` → `MSG.errCode` → `code`。
 */
export function normalizeError(error) {
  const code = str(error?.errCode || error?.MSG?.errCode || error?.code)
  const message = trimTail(error?.MSG?.content) || errText(code) || '预览渲染失败'
  return {
    code,
    message,
    hint: ERROR_HINT[code] || '请检查网络或稍后重试；若持续失败请联系管理员。',
    detail: code ? `errCode: ${code}` : ''
  }
}

/**
 * 预览页数据层。
 * @returns 取数函数与状态；页面（Preview.vue）负责路由监听、可用性判定与渲染分支。
 */
export function usePreviewRender() {
  const topic = ref(null)
  const layouts = ref([])
  const layoutsError = ref('')
  const loading = ref(false)
  const error = ref(null)
  const result = ref(null)
  /** 最近一次实际发出的 `topicrender` payload（供自测核对「小红书未传 previewKind」） */
  const lastPayload = ref(null)

  /**
   * 主题详情：`topicqry({ topicCode })`，未命中原样再试 `recID`（与 Step 7 / Step 9 同口径）。
   * ★ 裁定 G：进页面**先取一次**主题详情；`layoutCode` 为空时由页面短路为 EmptyState，
   *   **不调** `topicrender`（避免把可预期状态变成 C4 错误 toast）。
   */
  async function loadTopic(code) {
    const key = str(code)
    if (!key) return null
    const first = await topicQry({ topicCode: key })
    const firstList = Array.isArray(first?.data) ? first.data : []
    if (firstList.length) {
      topic.value = firstList[0]
      return topic.value
    }
    const second = await topicQry({ recID: key })
    const secondList = Array.isArray(second?.data) ? second.data : []
    topic.value = secondList[0] || null
    return topic.value
  }

  /** 版式目录（免登录端点；R-24：空响应一律按空数组，不抛错、不白屏） */
  async function ensureLayouts(force = false) {
    if (layouts.value.length && !force) return layouts.value
    layoutsError.value = ''
    try {
      const res = await layoutQry()
      layouts.value = normalizeLayouts(res?.data)
      if (!layouts.value.length) {
        console.error('[P-08] layoutqry 返回空（附录 B R-24），可用版式将只按矩阵键推导')
      }
    } catch (e) {
      layoutsError.value = trimTail(e?.MSG?.content) || '版式配置读取失败'
      console.error('[P-08] layoutqry 失败：可用版式仅按矩阵推导', e)
    }
    return layouts.value
  }

  /**
   * 发起预览渲染（`renderMode='sync'`；`specOverride` 仅随本次请求下发，不写回任何表，裁定 J）。
   * @param {{ topicID?: string, topicCode?: string, layoutCode: string, platform?: string, specOverride?: object }} input
   */
  async function renderPreview(input = {}) {
    const layoutCode = str(input.layoutCode)
    if (!layoutCode) throw { errCode: 'C4', MSG: { content: '缺少必填字段: layoutCode' } }

    const payload = {
      layoutCode,
      renderMode: PREVIEW_RENDER_MODE
    }
    if (str(input.topicID)) payload.topicID = str(input.topicID)
    if (str(input.topicCode)) payload.topicCode = str(input.topicCode)
    if (str(input.platform)) payload.platform = str(input.platform)
    // ★ 小红书（及任何未登记平台）不传 previewKind：后端适配器不消费该参数
    const previewKind = previewKindOf(input.platform)
    if (previewKind) payload.previewKind = previewKind
    if (input.specOverride && typeof input.specOverride === 'object' && Object.keys(input.specOverride).length) {
      payload.specOverride = input.specOverride
    }

    lastPayload.value = payload
    console.info('[P-08] topicrender 实际发出的 payload', payload)
    error.value = null
    const res = await topicRender(payload)
    result.value = normalizeRenderResult(res, payload)
    return result.value
  }

  /** 重置渲染结果（切换平台 / 版式 / 主题时避免残留上一次的产物） */
  function resetResult() {
    result.value = null
    error.value = null
  }

  return {
    topic,
    layouts,
    layoutsError,
    loading,
    error,
    result,
    lastPayload,
    loadTopic,
    ensureLayouts,
    renderPreview,
    resetResult
  }
}

export default usePreviewRender
