/* ============================================================================
 * 前端字典（唯一来源）· Step 3 要点 4
 * ----------------------------------------------------------------------------
 * 供 Step 4 的 StateBadge / PlatformChip / LayoutCard / SpecChecker 及后续页面共用。
 * 三条硬约束：
 *   1) 状态一律「形状图标 + 颜色 + 文字」三重编码（§2.6 裁定 C6），禁止仅用颜色表达状态；
 *      故每项含 `{ label, color, icon, pulse? }`，`icon` 是**可直接绑定到 class 的完整字符串**。
 *   2) 颜色一律引用 `src/js/tokens.js`（同一份 Token 单源），本文件不写字面色值。
 *   3) FA6 写法（裁定 D / H）：实心 `fa fa-*`；空心必须 `fa-regular fa-circle`，
 *      ★ 禁止 `fa fa-regular fa-circle`（`.fa` 会把字重设回 900，两个 style 类冲突）。
 *
 * 【本步图标修订（裁定 H，已在交付说明登记）】
 *   §2.6「主题 ARCHIVED」原写 `fa-circle-ban`，FA6 Free 6.7.2 的 svgs/ 与 css/all.css 均查无该名，
 *   改用 **`fa-ban`**（`fa-box-archive` 已被「投递记录」导航占用，禁止复用）。
 *   §2.6 两处未标注空心/实心的 `fa-circle` 统一定为：
 *     「未开始 / 未投递」类 = 空心 `fa-regular fa-circle`；「已完成 / 已发布」类 = 实心 `fa fa-circle`。
 * ========================================================================== */
import { tokens } from '@/js/tokens'

/* ---------------------------------------------------------------------------
 * 1. 五类状态机（严格按 §2.6 表）
 * ------------------------------------------------------------------------- */

/** 主题状态机 `ch_topic.status` */
export const TOPIC_STATUS_MAP = {
  DRAFT: { label: '草稿', color: tokens.text.secondary, icon: 'fa-regular fa-circle' },
  RENDERING: { label: '渲染中', color: tokens.primary.base, icon: 'fa fa-circle-half-stroke', pulse: true },
  RENDERED: { label: '已渲染', color: tokens.status.info, icon: 'fa fa-circle-check' },
  PUBLISHED: { label: '已投递', color: tokens.status.success, icon: 'fa fa-circle' },
  // ★ fa-circle-ban 在 FA6 Free 不存在 → 改用 fa-ban（见文件头修订说明）
  ARCHIVED: { label: '已归档', color: tokens.text.tertiary, icon: 'fa fa-ban' }
}

/** 发布状态机 `ch_topic.publishStatus` */
export const PUBLISH_STATUS_MAP = {
  UNPUBLISHED: { label: '未投递', color: tokens.text.tertiary, icon: 'fa-regular fa-circle' },
  DRAFTED: { label: '已推草稿', color: tokens.primary.base, icon: 'fa fa-circle-half-stroke' },
  PUBLISHED: { label: '已发布', color: tokens.status.success, icon: 'fa fa-circle' },
  FAILED: { label: '投递失败', color: tokens.status.danger, icon: 'fa fa-circle-xmark' }
}

/** 渲染任务状态机 `ch_render_job.jobStatus` */
export const JOB_STATUS_MAP = {
  PENDING: { label: '排队中', color: tokens.text.secondary, icon: 'fa fa-clock' },
  RUNNING: { label: '运行中', color: tokens.primary.base, icon: 'fa fa-circle-half-stroke', pulse: true },
  DONE: { label: '完成', color: tokens.status.success, icon: 'fa fa-circle-check' },
  FAILED: { label: '失败', color: tokens.status.danger, icon: 'fa fa-circle-xmark' }
}

/** 产物状态机 `ch_artifact.artifactStatus` */
export const ARTIFACT_STATUS_MAP = {
  READY: { label: '可用', color: tokens.status.success, icon: 'fa fa-circle-check' },
  EXPIRED: { label: '已过期', color: tokens.status.warning, icon: 'fa fa-triangle-exclamation' }
}

/* ---------------------------------------------------------------------------
 * 产物类型（`ch_artifact.kind`，权威取值见 `database/ch_artifact.txt:5`）
 * -------------------------------------------------------------------------
 * ★ 类型图标属「功能性图标」，不受 §2.6 状态图标表约束（同 PlatformChip 的 PLATFORM_ICON 口径），
 *   用于缩略图缺失时按类型兜底展示**图标 + 文字**，不得用破图占位。
 * ★ `zip`（素材包）**不登记 `ch_artifact`**（附录 B R-10：ZIP 为一次性导出、无 job 归属）
 *   → 保留映射仅作「存量脏数据」的兜底渲染；**筛选器不提供该取值**
 *   （见 `ARTIFACT_KIND_FILTER_OPTIONS`），也禁止按 `kind='zip'` 发起查询。
 * ------------------------------------------------------------------------- */
export const ARTIFACT_KIND_MAP = {
  html: { label: 'HTML', icon: 'fa fa-file-code' },
  png: { label: '长图 PNG', icon: 'fa fa-image' },
  json: { label: 'JSON', icon: 'fa fa-file-lines' },
  //★ 2026-09-24 新增: 通用平台(ch_platform=generic)的 exportKind=markdown 形态产物
  //  (权威取值 database/ch_artifact.txt:5 已同步扩为 html或png或zip或json或markdown)
  markdown: { label: 'Markdown', icon: 'fa-brands fa-markdown' },
  zip: { label: '素材包 ZIP', icon: 'fa fa-file-zipper' }
}

/** 类型筛选可选值（★ 不含 `zip`，依据附录 B R-10；计划要点 1 的 kind 清单里 zip 已按此裁定收窄） */
export const ARTIFACT_KIND_FILTER_OPTIONS = ['html', 'png', 'json', 'markdown']

/** 取产物类型元信息（未知取值兜底：灰底 + 通用文件图标 + 原值，不抛错） */
export function artifactKindMeta(kind) {
  const key = String(kind || '').toLowerCase()
  return ARTIFACT_KIND_MAP[key] || { label: key || '未知类型', icon: 'fa-regular fa-file' }
}

/**
 * 凭据健康状态机 `ch_account.healthStatus`
 * ★ 权威取值来自 `database/ch_account.txt:12`：**OK / EXPIRING / INVALID / UNKNOWN**。
 *   UI 设计文档把「有效」写成另一个词属笔误；本字典键必须是 `OK`，
 *   且**只允许这四个键**，不得新增或改名（验收项：字典中不存在「有效态」的第五种键名）。
 */
export const HEALTH_STATUS_MAP = {
  OK: { label: '有效', color: tokens.status.success, icon: 'fa fa-circle-check' },
  EXPIRING: { label: '即将过期', color: tokens.status.warning, icon: 'fa fa-triangle-exclamation' },
  INVALID: { label: '已失效', color: tokens.status.danger, icon: 'fa fa-circle-xmark' },
  UNKNOWN: { label: '未知', color: tokens.text.tertiary, icon: 'fa fa-circle-question' }
}

/** 合规三分类（`publishcheck` 的 `level` 汇总口径） */
export const COMPLIANCE_LEVEL_MAP = {
  PASS: { label: '通过', color: tokens.status.success, icon: 'fa fa-circle-check' },
  WARN: { label: '警告', color: tokens.status.warning, icon: 'fa fa-triangle-exclamation' },
  BLOCK: { label: '阻断', color: tokens.status.danger, icon: 'fa fa-circle-xmark' }
}

/** 合规问题清单的原始口径：接口返回 `ERROR` / `WARN`（§2.6 修正 ②） */
export const SENSITIVE_LEVEL_MAP = {
  ERROR: { label: '阻断', color: tokens.status.danger, icon: 'fa fa-circle-xmark' },
  WARN: { label: '警告', color: tokens.status.warning, icon: 'fa fa-triangle-exclamation' }
}

/* ---------------------------------------------------------------------------
 * 合规问题「来源」（Step 13 追加 · 裁定 B）
 * -------------------------------------------------------------------------
 * ★ 权威枚举出自后端 `processor/complianceService.py:102-108`（SOURCE_* 常量），
 *   前端**不得**新增/改名；P-09 的「通过」分组按此列出「本次未产出问题的检查类别」。
 * ------------------------------------------------------------------------- */
export const COMPLIANCE_SOURCE_MAP = {
  platform_spec: '平台规格',
  swipe_spec: '滑动专项',
  overlong_image: '超长图切分',
  sensitive_word: '敏感词',
  ai_label: 'AI 内容标识',
  rate_limit: '发布频率限流',
  artifact_spec: '产物规格'
}

/** 分组展示顺序（固定，与后端 evaluateCompliance 的执行顺序一致） */
export const COMPLIANCE_SOURCE_ORDER = [
  'platform_spec',
  'swipe_spec',
  'overlong_image',
  'sensitive_word',
  'ai_label',
  'rate_limit',
  'artifact_spec'
]

/* ---------------------------------------------------------------------------
 * 2. 平台（§2.7 种子；**不含任何「发布」动作**，小红书本期仅导出素材包）
 *    平台规格数值属数据驱动（`ch_platform` → platformqry），此处只登记展示用元信息。
 * ------------------------------------------------------------------------- */
export const PLATFORM_MAP = {
  wechat_mp: { label: '微信公众号', color: tokens.platform.wechat_mp, deliverMode: 'draft_box' },
  xiaohongshu: { label: '小红书', color: tokens.platform.xiaohongshu, deliverMode: 'asset_pack' },
  generic: { label: '通用HTML', color: tokens.platform.generic, deliverMode: 'asset_pack' }
}

/** 平台下拉顺序（P-05 / P-10 固定顺序） */
export const PLATFORM_ORDER = ['wechat_mp', 'xiaohongshu', 'generic']

/* ---------------------------------------------------------------------------
 * 3. 版式（§2.7 版式种子 + .md 4.2 P-05 可选性矩阵）
 * ------------------------------------------------------------------------- */
export const LAYOUT_TYPE_MAP = {
  stack: '上下展示',
  carousel: '左右轮播',
  longimage: '长图拼接',
  swipe: '左右滑动多图集'
}

/**
 * 版式 × 平台可选性矩阵（P-05 卡片过滤**以此为准**，可叠加 `ch_layout` 实际数据）。
 * 不可用组合**直接不渲染卡片**（不灰显）；后端若仍返回 C7，前端按错误码回显。
 * 来源：`plan/UI/contentHub UI 设计.md` 4.2 P-05。
 */
export const LAYOUT_PLATFORM_MATRIX = {
  stack_v1: { wechat_mp: true, xiaohongshu: true, generic: true },
  carousel_v1: { wechat_mp: true, xiaohongshu: false, generic: true },
  longimage_v1: { wechat_mp: true, xiaohongshu: true, generic: true },
  swipe_v1: { wechat_mp: false, xiaohongshu: true, generic: false }
}

/** 可用性附注（P-05 卡片上的一句引导；Step 9 使用） */
export const LAYOUT_PLATFORM_NOTES = {
  'stack_v1|xiaohongshu': '小红书下按长图转出，整篇建议保持同一比例',
  'carousel_v1|wechat_mp': '微信下以 SVG 自实现交互，需静态兜底图',
  'longimage_v1|xiaohongshu': '超长原图会被强制缩放导致文字模糊，建议改用 swipe_v1（左右滑动多图集）'
}

/** 是否允许「版式 × 平台」组合（未知组合一律取 false，交由后端 C7 兜底） */
export function isLayoutAllowed(layoutCode, platform) {
  return Boolean(LAYOUT_PLATFORM_MATRIX[layoutCode]?.[platform])
}

/* ---------------------------------------------------------------------------
 * 4. 素材相关（§2.9.3）
 * ------------------------------------------------------------------------- */
/** 素材用途；封面唯一（`topicassetadd` 幂等键 `{topicID}:{fileID}`） */
export const USAGE_TYPE_MAP = {
  cover: '封面',
  body: '正文图',
  inline: '内联图'
}

/** 素材处理状态 */
export const ASSET_PROCESS_STATUS_MAP = {
  RAW: '原样',
  PROCESSED: '已处理',
  FAILED: '失败'
}

/* ---------------------------------------------------------------------------
 * 5. 错误码文案（§2.5；默认走后端 MSG.content，此处仅供需要自行展示时兜底）
 * ------------------------------------------------------------------------- */
export const ERR_CODE_TEXT = {
  B0: '操作成功',
  B4: '记录已存在',
  B8: '会话已过期，请重新登录',
  B9: '数据冲突，请刷新后重试',
  BA: '缺少必要参数',
  BG: '当前角色权限不足',
  BI: '记录标识无效',
  BL: '文件上传失败',
  BT: '账号不可用或无权访问',
  C0: '通用参数错误',
  C2: '该端点尚未实现',
  C4: '必填项缺失',
  C5: '内容超出长度限制',
  C6: '数量超出上限',
  C7: '当前状态或平台不支持该操作',
  CA: '记录重复',
  CB: '未查询到记录',
  CG: '写入失败，请稍后重试',
  D0: '文件类型不允许',
  D1: '图片尺寸或比例不符合平台要求',
  D3: '上传失败，请重试',
  D4: '文件取回失败',
  E0: '模板缺失或版式不支持',
  E1: '渲染失败',
  E2: '截图超时',
  E3: '产物生成失败',
  E4: '外链图片需转存，但存储凭据缺失',
  F0: '凭据解密失败，请在账号管理重新登记',
  F1: '已命中幂等记录或该投递已撤销',
  F4: '缺少二次确认，请重新确认后再推送',
  F5: '撤销窗口已过期',
  F6: '自动发布闸门未开启',
  G0: '令牌无效',
  G1: '令牌权限不足',
  G2: '未知的 MCP 工具',
  G3: '下游服务调用失败',
  ERR_NOCMD: '未知命令',
  ERR_IPFLOOD: '操作过于频繁，请稍后重试',
  ERR_GENERAL: '服务异常，请稍后重试'
}

/** 取错误码文案（未知码返回空串，由调用方决定展示原文） */
export function errText(code) {
  return ERR_CODE_TEXT[code] || ''
}

/* ---------------------------------------------------------------------------
 * 6. 通用辅助
 * ------------------------------------------------------------------------- */
/**
 * 安全取状态元信息：未知值返回 `{ label: 原值, color: text.secondary, icon: 'fa-regular fa-circle' }`。
 * ★ 禁止新增未在 §2.6 定义的中间态；未知值只做兜底展示，不参与业务判断。
 */
export function resolveStatusMeta(map, key) {
  if (map && Object.prototype.hasOwnProperty.call(map, key)) {
    return { key, ...map[key] }
  }
  return { key, label: key || '未知', color: tokens.text.secondary, icon: 'fa-regular fa-circle' }
}

/** 主题 / 发布 / 任务 / 产物 状态徽章的颜色（供 CompletionIndicator 等取同色） */
export const STATUS_COLOR = {
  success: tokens.status.success,
  warning: tokens.status.warning,
  danger: tokens.status.danger,
  info: tokens.status.info,
  neutral: tokens.text.secondary
}
