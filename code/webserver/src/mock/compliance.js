/* ============================================================================
 * Mock · 合规域（publishcheck：与 processor/complianceService.py **同构**的问题清单）
 * ----------------------------------------------------------------------------
 * ★ Step 13 对齐（裁定 N）：本文件不再自造 source / field / location，一律复刻真实后端口径：
 *   · source ∈ { platform_spec, swipe_spec, overlong_image, sensitive_word, ai_label, rate_limit,
 *     artifact_spec }（complianceService.py:102-108）；
 *   · field 形如 `description(ch_topic)` / `coverSpec(ch_platform:wechat_mp)` / `specJson.sliceHeight`
 *     / `products[0].fileID` / `rateLimit`；location 形如 `description[12,15]` / `assetList[2]`
 *     （后端 `_issue` 在未显式给 location 时回落为 field 同值）；
 *   · data 与真实同构：passed / issueCount / errorCount / warningCount / issues / platformCode /
 *     layoutType / assetCount / sensitiveHitCount / rateLimit{accountID,platform,limitCount,
 *     windowSeconds,count,allowed,backend,degraded,errorMsg} / topicID(=ch_topic.recID) / topicCode /
 *     layoutCode / platform / accountID / checkedAt。
 * ★ 规则来源与后端一致（**不在本文件另立规则表**）：
 *   · 平台规格 = processor/platformAdapter/base.py::checkPlatformSpec（数据驱动 ch_platform）；
 *   · swipe 专项 = processor/platformAdapter/xiaohongshu.py::validateSwipeSpec；
 *   · 超长整图 = complianceService.checkOverlongImageIssues（阈值 spec.sliceHeight 或卡片高，默认 1440，E3）；
 *   · 敏感词 / AI 标识 / 限流 = complianceService 对应函数（敏感词恒为 **ERROR** C7；
 *     限流 Redis 不可用恒为 **WARN** 且 degraded='1'）。
 * ★ 可触发的样例（开发态）：
 *   · 敏感词：默认词表取自 ./data/topic.js 的 SENSITIVE_WORDS（与 Mock 正文同源，命中即得真实偏移）；
 *     请求 `sensitiveWords`（数组或逗号分隔字符串）可覆盖，传空则回落默认词表；
 *   · 限流降级 WARN：默认 degraded='1'（Mock 无 Redis，与真实降级语义一致）；
 *     `window.__MOCK_RATE_DEGRADED__ = false` 关闭降级；`window.__MOCK_RATE_LIMIT__ =
 *     { count: 31, allowed: '0' }` 触发「窗口内超上限」ERROR(C6)；
 *   · AI 标识：平台 `needAiLabelFlag='1'`（小红书）且正文/简介无标识词时产出；
 *     `aiFlag='1'` → ERROR，未声明 → WARN。
 *   · 超长整图：附图高 > 切片阈值（1200x1600 的样例素材即命中）。
 * ★ 生产构建仍应能剔除 mock（VITE_USE_MOCK=false 时不安装本 adapter）。
 * ========================================================================== */
import { charCount } from '@/utils/common'
import { SENSITIVE_WORDS, TOPICS, buildDetail } from './data/topic'
import { ASSETS, TOPIC_ASSETS } from './data/asset'
import { mockTopicLinks } from './asset'
import { LAYOUTS } from './layout'
import { PLATFORMS } from './platform'
import { mockTopics } from './topic'
import { pad } from './data/util'

/* ---------------- 与后端一致的常量（complianceService.py / base.py / xiaohongshu.py） ------- */
const SOURCE = {
  platformSpec: 'platform_spec',
  swipeSpec: 'swipe_spec',
  overlongImage: 'overlong_image',
  sensitiveWord: 'sensitive_word',
  aiLabel: 'ai_label',
  rateLimit: 'rate_limit',
  artifactSpec: 'artifact_spec'
}
const LEVEL = { error: 'ERROR', warn: 'WARN' }
const ERR = {
  fieldMissing: 'C4',
  tooLong: 'C5',
  outOfRange: 'C6',
  invalid: 'C7',
  fileType: 'D0',
  imageSpec: 'D1',
  fileNotFound: 'D4',
  artifactFailed: 'E3'
}
/** AI 标识词（xiaohongshu 平台红线；与后端 AI_LABEL_MARKER_LIST 逐字一致） */
const AI_LABEL_MARKER_LIST = ['AI生成', 'AI 生成', 'AI辅助创作', 'AI 辅助创作', 'AI创作', '人工智能生成', '本内容由AI']
/** 敏感词扫描字段（字段名 → 中文标签，与后端 SENSITIVE_SCAN_FIELD_LIST 一致） */
const SCAN_FIELD_LIST = [['title', '标题'], ['summary', '简介'], ['description', '正文'], ['author', '作者']]
const RATE_LIMIT_MAX_PUBLISH = 30
const RATE_LIMIT_WINDOW_SECONDS = 3600
const ARTIFACT_MAX_SIZE_MB = 20
const DEFAULT_SLICE_HEIGHT = 1440
const DEFAULT_CARD_SIZE = [1080, 1440]
const SWIPE_DEFAULT_RATIO = [3, 4]
const SWIPE_RATIO_TOLERANCE = 0.02
const SWIPE_DEFAULT_FORMAT = ['jpg', 'png']
const SWIPE_INDEX_RE = /第\s*(\d+)\s*张/

/* ---------------- 小工具 ---------------- */
const str = (value) => (value === null || value === undefined ? '' : String(value).trim())
const num = (value, fallback = 0) => {
  const parsed = Number(str(value))
  return Number.isFinite(parsed) ? parsed : fallback
}

/** `'900x500'` / `'1080*1440'` → `[w, h]`（非法回落 `[0, 0]`，与 base.parseSizeSpec 同口径） */
function parseSize(sizeSpec) {
  const text = str(sizeSpec).toLowerCase().replace('*', 'x')
  const matched = /^(\d+)x(\d+)$/.exec(text)
  return matched ? [Number(matched[1]), Number(matched[2])] : [0, 0]
}

/** `ch_layout.specJson` 是 JSON 字符串（真实同构）→ 对象；解析失败按 {} 并 console.error */
function parseSpecJson(raw) {
  if (!raw) return {}
  try {
    const parsed = JSON.parse(String(raw))
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch (error) {
    console.error('[mock] specJson 解析失败，已按 {} 处理', { raw, error })
    return {}
  }
}

function nowStr() {
  const d = new Date()
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
}

/** 构造统一问题项（对齐 complianceService._issue：location 缺省回落 field） */
const makeIssue = (field, level, errCode, message, location, source, extra) => ({
  field,
  location: str(location) || field,
  level,
  errCode,
  message,
  source,
  ...(extra || {})
})

/** 去重（对齐 complianceService._dedupeIssues） */
function dedupeIssues(issues) {
  const seen = new Set()
  const result = []
  for (const item of issues || []) {
    const key = [item.level, item.errCode, item.field, item.location, item.message].join('|')
    if (seen.has(key)) continue
    seen.add(key)
    result.push(item)
  }
  return result
}

/** topicID 语义对齐（裁定 a4）：topicID 指 ch_topic.recID，同时容忍 topicCode 入参 */
const findTopic = (body) =>
  TOPICS.find(
    (item) =>
      (body.topicID && (item.recID === body.topicID || item.topicCode === body.topicID)) ||
      (body.recID && item.recID === body.recID) ||
      (body.topicCode && item.topicCode === body.topicCode)
  )

/**
 * ★ 取「在库记录」：真实后端 `publishCheck` 从 `ch_topic` 读主题（`renderService._fetchTopic`），
 *   因此 `topicmodify` 写入的内容（如 P-09「一键添加」追加的 AI 标识）必须能在再次校验时读到。
 *   Mock 侧 `./topic.js` 的 `mockTopics` 就是「库」本体（topicmodify 会就地更新它），
 *   故这里以它为权威，仅在其缺失时回落到种子数据。
 */
const liveTopic = (topic) => mockTopics.find((item) => item.recID === topic.recID) || topic

/**
 * 附图列表：`ch_topic_asset` 关联 + `ch_asset` 元信息（fileExt / origSizeBytes），与 `_mergeAssetMeta` 同口径。
 * ★ Step 14 修正（越界授权小改，产出说明已登记）：优先取 `mock/asset.js` 的**实时**关联表
 *   （`topicassetdel` 解绑后立即生效，与真实后端读 `ch_topic_asset` 一致）；
 *   仅在实时表无该主题键时回落静态种子 —— 否则会出现「页面附图 0，合规仍按种子图报阻断」的 Mock 假象。
 */
function fetchAssets(topicID) {
  const links = (mockTopicLinks && mockTopicLinks[topicID]) || TOPIC_ASSETS[topicID] || []
  return links.map((link) => {
    const meta = ASSETS.find((asset) => asset.fileID === link.fileID) || {}
    return { ...link, fileExt: meta.fileExt || '', origSizeBytes: num(meta.origSizeBytes), caption: link.caption || meta.caption || '' }
  })
}

/** 敏感词表：请求覆盖 > Mock 默认（默认表与 Mock 正文同源，否则无可触发样例） */
function resolveWords(input) {
  if (input === undefined || input === null || input === '') return SENSITIVE_WORDS.map((item) => item.word).filter(Boolean)
  const list = Array.isArray(input) ? input : String(input).split(',')
  const words = list.map((item) => str(typeof item === 'string' ? item : item?.word)).filter(Boolean)
  return Array.from(new Set(words))
}

/* ---------------- 平台规格（★ 复用 base.checkPlatformSpec 的判定口径） ---------------- */
function platformSpecIssues(platform, topic, assetList) {
  const code = str(platform.platformCode)
  const label = (name) => `${name}(ch_platform:${code})`
  const issues = []

  const title = str(topic.title)
  const titleMaxLen = num(platform.titleMaxLen)
  if (!title) issues.push(makeIssue(label('title'), LEVEL.error, ERR.fieldMissing, 'title 为必填字段', label('title'), SOURCE.platformSpec))
  else if (titleMaxLen > 0 && charCount(title) > titleMaxLen) {
    issues.push(makeIssue(label('title'), LEVEL.error, ERR.tooLong, `title 长度=${charCount(title)} 超平台上限 ${titleMaxLen}`, label('title'), SOURCE.platformSpec))
  }

  const summary = str(topic.summary)
  const summaryMaxLen = num(platform.summaryMaxLen)
  if (summary && summaryMaxLen > 0 && charCount(summary) > summaryMaxLen) {
    issues.push(makeIssue(label('summary'), LEVEL.error, ERR.tooLong, `summary 长度=${charCount(summary)} 超平台上限 ${summaryMaxLen}`, label('summary'), SOURCE.platformSpec))
  }

  const [coverWidth, coverHeight] = parseSize(platform.coverSpec)
  if (coverWidth > 0 && coverHeight > 0) {
    const cover = (assetList || []).find((item) => str(item.usageType).toLowerCase() === 'cover')
    if (cover) {
      const width = num(cover.width)
      const height = num(cover.height)
      if (width > 0 && height > 0 && (width !== coverWidth || height !== coverHeight)) {
        issues.push(makeIssue(label('coverSpec'), LEVEL.error, ERR.imageSpec,
          `封面尺寸 ${width}x${height} 与平台规格 ${coverWidth}x${coverHeight} 不一致(须由渲染期 imageProc 派生归一)`,
          label('coverSpec'), SOURCE.platformSpec))
      }
    }
  }

  const [imageWidth, imageHeight] = parseSize(platform.imageSpec)
  if (imageWidth > 0 && imageHeight > 0) {
    ;(assetList || []).forEach((item, index) => {
      if (str(item.usageType).toLowerCase() === 'cover') return
      const width = num(item.width)
      const height = num(item.height)
      if (width > 0 && height > 0 && (width !== imageWidth || height !== imageHeight)) {
        issues.push(makeIssue(label('imageSpec'), LEVEL.error, ERR.imageSpec,
          `第 ${index + 1} 张正文图尺寸 ${width}x${height} 与平台规格 ${imageWidth}x${imageHeight} 不一致(须由渲染期 imageProc 派生归一)`,
          label('imageSpec'), SOURCE.platformSpec))
      }
    })
  }

  const imageMaxCount = num(platform.imageMaxCount)
  if (imageMaxCount > 0 && (assetList || []).length > imageMaxCount) {
    issues.push(makeIssue(label('imageMaxCount'), LEVEL.error, ERR.outOfRange,
      `图片数 ${assetList.length} 超平台上限 ${imageMaxCount}`, label('imageMaxCount'), SOURCE.platformSpec))
  }
  return issues
}

/* ---------------- 超长整图（★ E3；渲染期无此判定，属 C8 前置闸门） ---------------- */
function overlongImageIssues(assetList, spec) {
  const [, cardHeight] = parseSize(spec.size)
  const threshold = num(spec.sliceHeight) || cardHeight || (DEFAULT_CARD_SIZE[1] || DEFAULT_SLICE_HEIGHT)
  const issues = []
  ;(assetList || []).forEach((item, index) => {
    const height = num(item.height)
    if (height > threshold) {
      issues.push(makeIssue('specJson.sliceHeight', LEVEL.error, ERR.artifactFailed,
        `第 ${index + 1} 张图高 ${height} 超单图上限 ${threshold}, 须先按 ${threshold} 切分(禁止直接上传超长整图)`,
        `assetList[${index}]`, SOURCE.overlongImage))
    }
  })
  return issues
}

/** swipe 校验消息里的「第 N 张」→ assetList 下标（对齐 _resolveSwipeLocation） */
function resolveSwipeLocation(message, fallbackField) {
  const matched = SWIPE_INDEX_RE.exec(str(message))
  if (matched) {
    const index = Number(matched[1]) - 1
    if (index >= 0) return `assetList[${index}]`
  }
  return fallbackField
}

/* ---------------- swipe 专项（★ 复用 xiaohongshu.validateSwipeSpec 的判定口径） ---------------- */
function swipeSpecIssues(platform, assetList, spec) {
  const code = str(platform.platformCode)
  const label = (name) => `${name}(ch_platform:${code})`
  const [ratioWidth, ratioHeight] = (() => {
    const parts = str(spec.ratio).split(':').map((item) => Number(item))
    return parts.length === 2 && parts[0] > 0 && parts[1] > 0 ? parts : SWIPE_DEFAULT_RATIO
  })()
  const targetRatio = ratioHeight ? ratioWidth / ratioHeight : 0.75

  let maxCount = num(spec.maxCount, 18) || 18
  const imageMaxCount = num(platform.imageMaxCount)
  if (imageMaxCount > 0) maxCount = maxCount > 0 ? Math.min(maxCount, imageMaxCount) : imageMaxCount
  const maxSizeMB = num(spec.maxSizePerImageMB, ARTIFACT_MAX_SIZE_MB) || ARTIFACT_MAX_SIZE_MB
  const formatList = Array.isArray(spec.format)
    ? spec.format.map((item) => str(item).toLowerCase()).filter(Boolean)
    : SWIPE_DEFAULT_FORMAT.slice()

  const errors = []
  const addError = (errCode, fieldLabel, message) => errors.push({ errCode, fieldLabel, message })

  const count = (assetList || []).length
  if (maxCount > 0 && count > maxCount) {
    addError(ERR.outOfRange, label('imageMaxCount'),
      `图片数 ${count} 超小红书上限 ${maxCount}(ch_platform.imageMaxCount / specJson.maxCount)`)
  }

  ;(assetList || []).forEach((item, index) => {
    const seqLabel = `第 ${index + 1} 张`
    const fileExt = str(item.fileExt).toLowerCase()
    if (formatList.length && fileExt && !formatList.includes(fileExt)) {
      addError(ERR.fileType, label('specJson.format'), `${seqLabel}格式 ${fileExt} 不在允许范围 ${formatList}`)
    }
    const sizeBytes = num(item.origSizeBytes)
    if (maxSizeMB > 0 && sizeBytes > maxSizeMB * 1024 * 1024) {
      addError(ERR.imageSpec, label('specJson.maxSizePerImageMB'), `${seqLabel}大小 ${sizeBytes} 字节 超单张上限 ${maxSizeMB}MB`)
    }
    const width = num(item.width)
    const height = num(item.height)
    if (width > 0 && height > 0 && Math.abs(width / height - targetRatio) > SWIPE_RATIO_TOLERANCE) {
      addError(ERR.imageSpec, label('specJson.uniformRatio'),
        `${seqLabel}比例 ${width}x${height} 与整篇 ${ratioWidth}:${ratioHeight} 不一致`
        + `(小红书要求整篇单一比例, 混用会导致滑动时画面跳动; **不静默裁切**, 请先统一源图比例)`)
    }
  })

  return errors.map((item) => makeIssue(item.fieldLabel, LEVEL.error, item.errCode, item.message,
    resolveSwipeLocation(item.message, item.fieldLabel), SOURCE.swipeSpec))
}

/* ---------------- 敏感词（★ 命中恒为 ERROR C7，带真实偏移区间） ---------------- */
function sensitiveWordIssues(topic, words) {
  const issues = []
  SCAN_FIELD_LIST.forEach(([fieldName, fieldLabel]) => {
    const text = str(topic[fieldName])
    if (!text) return
    words.forEach((word) => {
      let start = text.indexOf(word)
      while (start >= 0) {
        issues.push(makeIssue(`${fieldName}(ch_topic)`, LEVEL.error, ERR.invalid,
          `${fieldLabel}命中敏感词 '${word}'(字符偏移 ${start}-${start + word.length})`,
          `${fieldName}[${start},${start + word.length}]`, SOURCE.sensitiveWord,
          { offsetStart: start, offsetEnd: start + word.length, matchedWord: word }))
        start = text.indexOf(word, start + word.length)
      }
    })
  })
  return issues
}

/* ---------------- AI 内容标识（needAiLabelFlag='1' 才校验） ---------------- */
function aiLabelIssues(platform, topic) {
  if (str(platform.needAiLabelFlag) !== '1') return []
  let hasLabel = Boolean(str(topic.aiLabel))
  if (!hasLabel) {
    const blob = `${str(topic.summary)} ${str(topic.description)}`
    hasLabel = AI_LABEL_MARKER_LIST.some((marker) => blob.includes(marker))
  }
  if (hasLabel) return []
  const aiFlag = str(topic.aiFlag)
  const level = aiFlag === '1' ? LEVEL.error : LEVEL.warn
  return [makeIssue('aiLabel(ch_topic)', level, ERR.invalid,
    `平台强制 AI 内容标识(needAiLabelFlag=1)但未检测到标识: 请填写 aiLabel 或在正文/简介加入标识词 `
    + `(${AI_LABEL_MARKER_LIST}); 当前 aiFlag=${aiFlag || '未声明'}`,
    'aiLabel', SOURCE.aiLabel)]
}

/* ---------------- 发布频率限流（Redis 不可用 → 恒降级为进程内计数） ---------------- */
function buildRateLimit(body, accountID, platformCode) {
  const limitCount = num(body.rateLimitCount, RATE_LIMIT_MAX_PUBLISH) || RATE_LIMIT_MAX_PUBLISH
  const windowSeconds = num(body.rateLimitWindow, RATE_LIMIT_WINDOW_SECONDS) || RATE_LIMIT_WINDOW_SECONDS
  // ★ Mock 环境未接入 Redis → 默认与真实后端「Redis 不可用即降级」同形（degraded='1'）
  const degraded = typeof window !== 'undefined' && window.__MOCK_RATE_DEGRADED__ === false ? '0' : '1'
  const info = {
    accountID,
    platform: platformCode,
    limitCount,
    windowSeconds,
    count: 1,
    allowed: '1',
    backend: degraded === '1' ? 'memory' : 'redis',
    degraded,
    errorMsg: degraded === '1' ? 'Mock 环境未接入 Redis（按真实后端口径降级为进程内计数）' : ''
  }
  const forced = typeof window !== 'undefined' ? window.__MOCK_RATE_LIMIT__ : null
  if (forced && typeof forced === 'object') Object.assign(info, forced)
  if (!forced || forced.allowed === undefined) {
    info.allowed = num(info.count) > num(info.limitCount) && num(info.limitCount) > 0 ? '0' : '1'
  }
  return info
}

function rateLimitIssues(rateLimitInfo) {
  const issues = []
  if (str(rateLimitInfo.degraded) === '1') {
    issues.push(makeIssue('rateLimit', LEVEL.warn, ERR.outOfRange,
      `发布频率限流已降级为进程内计数(Redis 不可用, degraded=1, backend=${rateLimitInfo.backend}); 未阻断本次校验`,
      'rateLimit', SOURCE.rateLimit))
  }
  if (str(rateLimitInfo.allowed) === '0') {
    issues.push(makeIssue('rateLimit', LEVEL.error, ERR.outOfRange,
      `发布频率超限: 账号 ${rateLimitInfo.accountID} 在 ${rateLimitInfo.windowSeconds} 秒内已发布 `
      + `${rateLimitInfo.count} 次, 超上限 ${rateLimitInfo.limitCount}`,
      'rateLimit', SOURCE.rateLimit))
  }
  return issues
}

/* ---------------- 产物校验（★ 仅请求显式传了 products 才执行，Step 14 投递前置用） ---------------- */
function artifactSpecIssues(products, platform) {
  const list = Array.isArray(products) ? products : []
  const [imageWidth, imageHeight] = parseSize(platform.imageSpec)
  const imageMaxCount = num(platform.imageMaxCount)
  const issues = []
  list.forEach((item, index) => {
    if (!str(item.fileID)) {
      issues.push(makeIssue(`products[${index}].fileID`, LEVEL.error, ERR.fileNotFound,
        `第 ${index + 1} 个产物缺少 fileID(未上传成功)`, `products[${index}]`, SOURCE.artifactSpec))
    }
    const width = num(item.width)
    const height = num(item.height)
    if (imageWidth > 0 && imageHeight > 0 && width > 0 && height > 0 && (width !== imageWidth || height !== imageHeight)) {
      issues.push(makeIssue(`products[${index}].size`, LEVEL.error, ERR.imageSpec,
        `第 ${index + 1} 个产物尺寸 ${width}x${height} 与平台规格 ${imageWidth}x${imageHeight} 不一致`,
        `products[${index}]`, SOURCE.artifactSpec))
    }
    const sizeBytes = num(item.sizeBytes)
    if (sizeBytes > ARTIFACT_MAX_SIZE_MB * 1024 * 1024) {
      issues.push(makeIssue(`products[${index}].sizeBytes`, LEVEL.error, ERR.imageSpec,
        `第 ${index + 1} 个产物大小 ${sizeBytes} 字节 超单张上限 ${ARTIFACT_MAX_SIZE_MB}MB`,
        `products[${index}]`, SOURCE.artifactSpec))
    }
  })
  if (imageMaxCount > 0 && list.length > imageMaxCount) {
    issues.push(makeIssue('imageMaxCount(ch_platform)', LEVEL.error, ERR.outOfRange,
      `产物数 ${list.length} 超平台上限 ${imageMaxCount}`, 'products', SOURCE.artifactSpec))
  }
  return issues
}

export const handlers = {
  publishcheck: (body) => {
    const seed = findTopic(body)
    if (!seed) return { __err: { code: 'CB', content: '未查询到该主题' } }
    // ★ 以「在库记录」为准（topicmodify 后的内容必须立即可见，与真实后端一致）
    const topic = liveTopic(seed)

    const topicData = { ...topic, description: topic.description || buildDetail(topic) }
    const layoutCode = str(body.layoutCode) || str(topic.layoutCode)
    const layout = LAYOUTS.find((item) => item.layoutCode === layoutCode) || null
    const layoutType = (str(body.layoutType) || str(layout?.layoutType)).toLowerCase()
    // ★ 平台：请求 platform > ch_layout.platform；两者都空 → C7（与后端 publishCheck 第 4 步同形）
    const platformCode = str(body.platform) || str(layout?.platform)
    if (!platformCode) {
      return { __err: { code: 'C7', content: '平台未指定且版式未声明 platform: 请传 platform 或 layoutCode' } }
    }
    const platform = PLATFORMS.find((item) => item.platformCode === platformCode) || { platformCode }
    const assetList = fetchAssets(topic.recID)
    const spec = parseSpecJson(layout?.specJson)

    const issues = []
    issues.push(...platformSpecIssues(platform, topicData, assetList))
    if (layoutType === 'swipe') issues.push(...swipeSpecIssues(platform, assetList, spec))
    issues.push(...overlongImageIssues(assetList, spec))
    issues.push(...sensitiveWordIssues(topicData, resolveWords(body.sensitiveWords)))
    issues.push(...aiLabelIssues(platform, topicData))

    const accountID = str(body.accountID) || str(body.ownerID) || str(topic.owner) || 'anonymous'
    const rateLimit = buildRateLimit(body, accountID, platformCode)
    issues.push(...rateLimitIssues(rateLimit))
    if (body.products !== undefined) issues.push(...artifactSpecIssues(body.products, platform))

    const deduped = dedupeIssues(issues)
    const errorCount = deduped.filter((item) => item.level === LEVEL.error).length
    const warningCount = deduped.length - errorCount

    return {
      data: {
        passed: errorCount === 0 ? '1' : '0',
        issueCount: deduped.length,
        errorCount,
        warningCount,
        issues: deduped,
        platformCode,
        layoutType,
        assetCount: assetList.length,
        sensitiveHitCount: deduped.filter((item) => item.source === SOURCE.sensitiveWord).length,
        rateLimit,
        topicID: topic.recID,
        topicCode: topic.topicCode,
        layoutCode,
        platform: platformCode,
        accountID,
        checkedAt: nowStr()
      }
    }
  }
}

export default handlers
