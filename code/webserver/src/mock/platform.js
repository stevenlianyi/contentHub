/* ============================================================================
 * Mock · 平台（platformqry 3 条种子平台；免登录端点）
 * ----------------------------------------------------------------------------
 * ★ 2026-09-21 按远端实测（www.mindgram.top）回写报文形态，与真实后端**同构**（§2.8.2）：
 *   1) 数值字段（`titleMaxLen` / `summaryMaxLen` / `imageMaxCount`）以**字符串**返回
 *      → 前端一律 `Number()` 后再计算/展示（裁定 C）；
 *   2) 补齐 `ch_platform` 既有列 **`limitNote` / `subjectScope` / `docUrl`**：
 *     P-05 能力矩阵的「✕ 不支持」原因**优先取 `limitNote`**（实测有真实原因文案，裁定 D），
 *     缺列会让矩阵只能落到前端固定文案，掩盖配置漂移。
 * `needAiLabelFlag`：小红书为 1（合规校验据此给 WARN）。
 * ★ 不含任何「发布」动作：`autoPublishFlag` 三个平台均为 '0'。
 * ========================================================================== */
import { pad } from './data/util'

/** 3 条种子平台（数值列已按实测改为字符串；`limitNote` 为远端实际文案） */
export const PLATFORMS = [
  {
    recID: 'PF000001',
    platformCode: 'wechat_mp',
    platformName: '微信公众号',
    subjectScope: '订阅号 / 服务号（含个人主体与未认证企业号）',
    deliverMode: 'draft_box',
    titleMaxLen: '64',
    summaryMaxLen: '200',
    coverSpec: '900x500',
    imageSpec: '1080x1440',
    imageMaxCount: '20',
    allowSvgFlag: '0',
    needAiLabelFlag: '0',
    autoPublishFlag: '0',
    limitNote:
      '个人主体与未认证企业号自2025年7月起已被回收发布接口权限 本项目只能推草稿箱 最终群发须人工在后台完成',
    docUrl: '',
    enabled: '1'
  },
  {
    recID: 'PF000002',
    platformCode: 'xiaohongshu',
    platformName: '小红书',
    subjectScope: '个人号 / 专业号（本产品不接入发布链路）',
    deliverMode: 'asset_pack',
    titleMaxLen: '20',
    summaryMaxLen: '1000',
    coverSpec: '1080x1440',
    imageSpec: '1080x1440',
    imageMaxCount: '18',
    allowSvgFlag: '0',
    needAiLabelFlag: '1',
    autoPublishFlag: '0',
    limitNote:
      '严禁第三方自动发布与AI托管 本平台仅导出素材包; 整篇图片须比例统一 单张不超过20MB 超长图须按1080x1440切分',
    docUrl: '',
    enabled: '1'
  },
  {
    recID: 'PF000003',
    platformCode: 'generic',
    platformName: '通用HTML',
    subjectScope: '无（内部导出与调试形态）',
    deliverMode: 'asset_pack',
    titleMaxLen: '128',
    summaryMaxLen: '400',
    coverSpec: '',
    imageSpec: '',
    imageMaxCount: '50',
    allowSvgFlag: '1',
    needAiLabelFlag: '0',
    autoPublishFlag: '0',
    limitNote: '无平台限制 作为兜底与调试形态',
    docUrl: '',
    enabled: '1'
  }
]

const state = { platforms: PLATFORMS.map((item) => ({ ...item })), seq: PLATFORMS.length }

/** 数值列出参一律字符串（与真实后端一致）；非数值保持原样 */
const toNumericText = (value) => (value === null || value === undefined || value === '' ? '' : String(value))

export const handlers = {
  platformqry: (body, ctx) => {
    const platformCode = String(body.platformCode || '')
    const list = state.platforms.filter((item) => !platformCode || item.platformCode === platformCode)
    return ctx.paginate(list, body, 'platformqry', platformCode)
  },

  platformadd: (body) => {
    if (!body.platformCode) return { __err: { code: 'C4', content: '平台编码为必填项' } }
    if (state.platforms.some((item) => item.platformCode === body.platformCode)) {
      return { __err: { code: 'CA', content: `平台编码 ${body.platformCode} 已存在` } }
    }
    state.seq += 1
    const record = {
      recID: `PF${pad(state.seq, 6)}`,
      subjectScope: '',
      deliverMode: 'asset_pack',
      titleMaxLen: '64',
      summaryMaxLen: '200',
      imageMaxCount: '20',
      allowSvgFlag: '0',
      needAiLabelFlag: '0',
      autoPublishFlag: '0',
      limitNote: '',
      docUrl: '',
      enabled: '1',
      ...body
    }
    record.titleMaxLen = toNumericText(record.titleMaxLen)
    record.summaryMaxLen = toNumericText(record.summaryMaxLen)
    record.imageMaxCount = toNumericText(record.imageMaxCount)
    state.platforms.push(record)
    return { data: record }
  },

  platformmodify: (body) => {
    const index = state.platforms.findIndex((item) => item.recID === body.recID || item.platformCode === body.platformCode)
    if (index < 0) return { __err: { code: 'BI', content: '平台记录标识无效' } }
    // 正式发布为三重闸门控制的红线项，Mock 侧禁止通过该端点打开
    const patch = { ...body }
    if (patch.autoPublishFlag === '1') {
      return { __err: { code: 'F6', content: '自动发布闸门未开启，该字段不可通过接口开启' } }
    }
    delete patch.autoPublishFlag
    for (const field of ['titleMaxLen', 'summaryMaxLen', 'imageMaxCount']) {
      if (patch[field] !== undefined) patch[field] = toNumericText(patch[field])
    }
    state.platforms[index] = { ...state.platforms[index], ...patch, recID: state.platforms[index].recID }
    return { data: state.platforms[index] }
  },

  platformdel: (body) => {
    const index = state.platforms.findIndex((item) => item.recID === body.recID || item.platformCode === body.platformCode)
    if (index < 0) return { __err: { code: 'BI', content: '平台记录标识无效' } }
    const [removed] = state.platforms.splice(index, 1)
    return { data: { success: '1', recID: removed.recID } }
  }
}

export const mockPlatforms = state.platforms
export default handlers
