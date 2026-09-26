/* ============================================================================
 * Mock · 版式（layoutqry 4 条种子版式；免登录端点）
 * ----------------------------------------------------------------------------
 * ★ 2026-09-21 按远端实测（www.mindgram.top）回写报文形态，与真实后端**同构**（§2.8.2）：
 *   1) `specJson` 是 **JSON 字符串**（`"{\"maxWidth\":\"750px\"}"`），前端必须 `JSON.parse`
 *      （`useRenderTrigger.parseSpecJson` 解析失败按 `{}` 并 console.error）；
 *   2) 数值字段（`sortWeight` / `specJson.maxCount`）以**字符串**返回 → 前端一律 `Number()`；
 *   3) 补齐 `ch_layout` 既有列：`engine` / `templatePath` / `templateVer` / `builtinFlag` /
 *      `previewFileID` / `sortWeight`（此前 Mock 缺列会掩盖「按 sortWeight 升序」的实现缺陷）。
 * ⚠️ 种子中每个版式仅登记一条 `ch_layout`（platform 固定），比 .md 4.2 P-05 的可选性矩阵窄（R-08）。
 *    约定（§2.7 / 裁定 C）：P-05 卡片过滤以 `LAYOUT_PLATFORM_MATRIX` 为准，
 *    本 Mock 按种子原样返回，便于验证「矩阵与种子漂移」的 console.error 逻辑。
 * ========================================================================== */
import { pad } from './data/util'

/** 4 条种子版式（specJson 关键项与 §2.7 完全一致，但序列化为 JSON 字符串） */
export const LAYOUTS = [
  {
    recID: 'LY000001',
    layoutCode: 'stack_v1',
    layoutName: '上下展示',
    layoutType: 'stack',
    platform: 'wechat_mp',
    engine: 'jinja2',
    templatePath: 'templates/stack_v1.html.j2',
    templateVer: 'v1',
    outputKind: 'html',
    specJson: JSON.stringify({ maxWidth: '750px', fontSize: '16px', lineHeight: 1.75 }),
    previewFileID: '',
    builtinFlag: '1',
    enabled: '1',
    sortWeight: '10',
    description: '正文自上而下顺序排布，适合图文混排的长文阅读。',
    regYMDHMS: '20260105093000'
  },
  {
    recID: 'LY000002',
    layoutCode: 'carousel_v1',
    layoutName: '左右轮播',
    layoutType: 'carousel',
    platform: 'wechat_mp',
    engine: 'jinja2',
    templatePath: 'templates/carousel_v1.html.j2',
    templateVer: 'v1',
    outputKind: 'html',
    specJson: JSON.stringify({ size: '1080x1440', ratio: '3:4', maxCount: 9, allowSvg: false, needStaticFallback: true }),
    previewFileID: '',
    builtinFlag: '1',
    enabled: '1',
    sortWeight: '20',
    description: '多图左右轮播；无脚本运行环境时以静态兜底图展示。',
    regYMDHMS: '20260105093600'
  },
  {
    recID: 'LY000003',
    layoutCode: 'longimage_v1',
    layoutName: '长图拼接',
    layoutType: 'longimage',
    platform: 'xiaohongshu',
    engine: 'jinja2',
    templatePath: 'templates/longimage_v1.py',
    templateVer: 'v1',
    outputKind: 'png',
    specJson: JSON.stringify({ size: '1080x1440', sliceHeight: 1440, maxTotalHeight: 21600 }),
    previewFileID: '',
    builtinFlag: '1',
    enabled: '1',
    sortWeight: '30',
    description: '整篇拼接为长图；超长时按切片高度切分，整篇须保持同一比例。',
    regYMDHMS: '20260105094100'
  },
  {
    recID: 'LY000004',
    layoutCode: 'swipe_v1',
    layoutName: '左右滑动多图集',
    layoutType: 'swipe',
    platform: 'xiaohongshu',
    engine: 'jinja2',
    templatePath: 'templates/swipe_v1.py',
    templateVer: 'v1',
    outputKind: 'png',
    specJson: JSON.stringify({ size: '1080x1440', maxCount: 18, uniformRatio: true, maxSizePerImageMB: 20 }),
    previewFileID: '',
    builtinFlag: '1',
    enabled: '1',
    sortWeight: '40',
    description: '多图集滑动浏览；各图比例必须一致，单图体积不超过 20MB。',
    regYMDHMS: '20260105094700'
  }
]

const state = { layouts: LAYOUTS.map((item) => ({ ...item })), seq: LAYOUTS.length }

function nowStr() {
  const d = new Date()
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
}

/** `specJson` 落库口径：真实 `ch_layout.specJson` 是 VARCHAR(1000) JSON 字符串 */
const toSpecJsonText = (value) => {
  if (value === null || value === undefined || value === '') return ''
  return typeof value === 'string' ? value : JSON.stringify(value)
}

export const handlers = {
  layoutqry: (body, ctx) => {
    const platform = String(body.platform || '')
    const layoutType = String(body.layoutType || '')
    const enabledOnly = body.enabled !== 'all'
    const list = state.layouts.filter((item) => {
      const matchPlatform = !platform || item.platform === platform
      const matchType = !layoutType || item.layoutType === layoutType
      const matchEnabled = !enabledOnly || item.enabled === '1'
      return matchPlatform && matchType && matchEnabled
    })
    return ctx.paginate(list, body, 'layoutqry', `${platform}|${layoutType}`)
  },

  layoutadd: (body) => {
    if (!body.layoutCode || !body.layoutName) return { __err: { code: 'C4', content: '版式编码与名称为必填项' } }
    if (state.layouts.some((item) => item.layoutCode === body.layoutCode)) {
      return { __err: { code: 'CA', content: `版式编码 ${body.layoutCode} 已存在` } }
    }
    state.seq += 1
    const record = {
      recID: `LY${pad(state.seq, 6)}`,
      layoutCode: body.layoutCode,
      layoutName: body.layoutName,
      layoutType: body.layoutType || 'stack',
      platform: body.platform || 'wechat_mp',
      engine: body.engine || 'jinja2',
      templatePath: body.templatePath || '',
      templateVer: body.templateVer || 'v1',
      outputKind: body.outputKind || 'html',
      specJson: toSpecJsonText(body.specJson),
      previewFileID: body.previewFileID || '',
      builtinFlag: body.builtinFlag || '0',
      enabled: body.enabled || '1',
      // 数值列在真实表中是 SMALLINT，但出参以字符串返回（2026-09-21 实测）→ 统一存字符串
      sortWeight: String(body.sortWeight === undefined ? '100' : body.sortWeight),
      description: body.description || '',
      regYMDHMS: nowStr()
    }
    state.layouts.push(record)
    return { data: record }
  },

  layoutmodify: (body) => {
    const index = state.layouts.findIndex((item) => item.recID === body.recID || item.layoutCode === body.layoutCode)
    if (index < 0) return { __err: { code: 'BI', content: '版式记录标识无效' } }
    const patch = { ...body }
    if (patch.specJson !== undefined) patch.specJson = toSpecJsonText(patch.specJson)
    if (patch.sortWeight !== undefined) patch.sortWeight = String(patch.sortWeight)
    state.layouts[index] = { ...state.layouts[index], ...patch, recID: state.layouts[index].recID }
    return { data: state.layouts[index] }
  },

  layoutdel: (body) => {
    const index = state.layouts.findIndex((item) => item.recID === body.recID || item.layoutCode === body.layoutCode)
    if (index < 0) return { __err: { code: 'BI', content: '版式记录标识无效' } }
    const [removed] = state.layouts.splice(index, 1)
    return { data: { success: '1', recID: removed.recID } }
  }
}

export default handlers
