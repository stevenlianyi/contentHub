/* ============================================================================
 * Mock · 主题域（topicqry ≥128 条可分页 / topicadd 超长 C5 / 状态跃迁 C7 …）
 * ----------------------------------------------------------------------------
 * 两套校验口径的**业务侧**在 Mock 中按后端口径复现（§2.7）：
 *   标题 ≤50 字、简介 ≤200 字（按字符）；详述 ≤5000 字、**无下限**（`wordCount`，与后端 countWords 一致）。
 * 可触发失败样例（裁定 F）：标题 51 字 → C5；重复标题 → CA；非法状态跃迁 → C7 且回显
 * data.currentStatus；渲染中的主题删除 → C7；recID 无效 → BI。
 *
 * ★ Step 7 对齐（后端为权威，`processor/topicService.py`）：
 *   1) 字段名 `detail` → **`description`**（ch_topic.txt 权威列名，前端 Tab1 按此读写）；
 *   2) 详述的强校验只在**提交渲染路径**（`_checkRenderReadiness`，裁定 #1）；2026-09-22 起
 *      **下限已取消**，该函数只在「无正文且无 descriptionFileID」时返回 C4；
 *      保存时 >5000 字 → 转存文件并回填 `descriptionFileID`，库内只保留 5000 字前缀；
 *   3) 状态机补齐 `RENDERED → DRAFT`（TOPIC_STATUS_TRANSITIONS:116-122）。
 * ========================================================================== */
import { charCount, wordCount } from '@/utils/common'
import { TOPICS, TOPIC_VERSIONS, buildDetail } from './data/topic'
import { TOPIC_ASSETS } from './data/asset'
import { pad } from './data/util'

/** 主题状态机合法跃迁（对齐 topicService.TOPIC_STATUS_TRANSITIONS；ARCHIVED 为终态） */
const ALLOWED_NEXT = {
  DRAFT: ['DRAFT', 'RENDERING', 'ARCHIVED'],
  RENDERING: ['RENDERING', 'RENDERED', 'DRAFT', 'ARCHIVED'],
  RENDERED: ['RENDERED', 'PUBLISHED', 'RENDERING', 'DRAFT', 'ARCHIVED'],
  PUBLISHED: ['PUBLISHED', 'ARCHIVED'],
  ARCHIVED: ['ARCHIVED']
}

const TITLE_MAX = 50
const SUMMARY_MAX = 200
/** 详述无下限（2026-09-22 裁定：可留空、可短写），仅保留 ≤5000 的上限 */
const DETAIL_MAX = 5000
/** 转存时库内保留的正文预览长度（字符），与 topicService.DESCRIPTION_INLINE_PREVIEW_CHARS 一致 */
const DETAIL_INLINE_PREVIEW_CHARS = 5000

/**
 * 内存表（等价于「库内确实存着这些字段」）。
 * ★ 详述正文**必须落进 state**：后端 `topicmodify` 的出参是**落库后回读的完整记录**
 *   （topicService.py:842-860），前端按服务端返回值刷新草稿（裁定 H）。若 state 里
 *   description 恒为空串，仅保存标题也会把草稿正文「洗掉」，与真实后端行为相反。
 *   列表路径在查询时剥离正文（list 不返回大字段，保持报文精简），详情路径返回完整正文。
 */
const state = {
  topics: TOPICS.map((item) => {
    const description = item.description || buildDetail(item)
    return { ...item, description, wordCount: item.wordCount || wordCount(description) }
  }),
  versions: TOPIC_VERSIONS.map((item) => ({ ...item })),
  seq: TOPICS.length
}

function nowStr() {
  const d = new Date()
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
}

/**
 * 列表排序（★ 裁定 a2）：三态与后端 `queryTableGeneral` 完全一致（mysqlCommon.py:290-295），
 *   `modify` → modifyYMDHMS DESC（★ 缺省即此，对齐计划「默认按修改时间倒序」）；
 *   `create` → recID ASC；其他 → recID DESC。
 * ★ 禁止忽略 `order` 只按固定字段排序，否则前端写错参数在 Mock 下也会「看起来正常」。
 */
const sorted = (order) => {
  const list = [...state.topics]
  if (order === 'modify') {
    return list.sort((a, b) => String(b.modifyYMDHMS).localeCompare(String(a.modifyYMDHMS)))
  }
  if (order === 'create') {
    return list.sort((a, b) => String(a.recID).localeCompare(String(b.recID)))
  }
  return list.sort((a, b) => String(b.recID).localeCompare(String(a.recID)))
}

/** topicID 语义对齐（裁定 a4）：接受 ch_topic.recID 或 topicCode，统一归一到 recID */
const resolveTopicID = (input) => {
  const value = String(input || '')
  const hit = state.topics.find((item) => item.recID === value || item.topicCode === value)
  return hit ? hit.recID : value
}

function validateTopicFields(body) {
  if (!body.title) return { code: 'C4', content: '标题为必填项' }
  if (charCount(body.title) > TITLE_MAX) return { code: 'C5', content: `标题已 ${charCount(body.title)} 字，超出上限 ${TITLE_MAX} 字` }
  if (body.summary && charCount(body.summary) > SUMMARY_MAX) return { code: 'C5', content: `简介已 ${charCount(body.summary)} 字，超出上限 ${SUMMARY_MAX} 字` }
  // ★ 详述 2000–5000 的强校验只在「提交渲染」路径生效（见 checkRenderReadiness，裁定 #1）；
  //   保存路径不拦：<2000 允许留作草稿，>5000 走转存文件。
  return null
}

/** 提交渲染前置强校验（对齐 `topicService._checkRenderReadiness`，裁定 #1）。
 *  错误文案刻意与后端同形（`数值超出允许范围: description(字段#5);…`），
 *  便于前端 `useTopicDraft.applyServerError` 反查字段并做行内回显。 */
function checkRenderReadiness(record, body) {
  const description = String(body?.description || record?.description || '')
  const descriptionFileID = String(body?.descriptionFileID || record?.descriptionFileID || '')
  const words = description
    ? wordCount(description)
    : Number(record?.wordCount) || wordCount(String(record?.description || ''))

  if (!description && !descriptionFileID && !words) {
    return {
      code: 'C4',
      content: '缺少必填字段: description(字段#5);提交渲染前必须有详述正文(上限 5000 字, 无下限)或 descriptionFileID'
    }
  }
  //★ 2026-09-22 裁定: 取消详述 2000 字下限, 故此处不再返回 C6(字数不足)。
  return null
}

export const handlers = {
  topicqry: (body, ctx) => {
    const keyword = String(body.keyword || '').trim()
    const status = String(body.status || '')
    const platform = String(body.platform || '')
    // 时间范围（裁定 b3）：后端该条件作用在 regYMDHMS（创建时间），不是 modifyYMDHMS
    const beginYMDHMS = String(body.beginYMDHMS || '')
    const endYMDHMS = String(body.endYMDHMS || '')
    let list = sorted(String(body.order || 'modify'))
    if (body.recID) list = list.filter((item) => item.recID === body.recID)
    if (body.topicCode) list = list.filter((item) => item.topicCode === body.topicCode)
    if (status) list = list.filter((item) => item.status === status)
    if (platform) list = list.filter((item) => item.platform === platform)
    if (beginYMDHMS) list = list.filter((item) => String(item.regYMDHMS) >= beginYMDHMS)
    if (endYMDHMS) list = list.filter((item) => String(item.regYMDHMS) <= endYMDHMS)
    if (keyword) list = list.filter((item) => item.title.includes(keyword) || item.topicCode.includes(keyword))

    // 详情查询（recID / topicCode）：返回完整记录（含详述正文）+ 封面 URL
    // （列表查询剥离详述正文，避免报文过大；后端 fillFileUrls 亦在此把 coverFileID 转成 coverUrl）
    if (body.recID || body.topicCode) {
      list = list.map((item) => {
        const links = TOPIC_ASSETS[item.recID] || []
        const cover = links.find((link) => link.usageType === 'cover')
        return {
          ...item,
          coverFileID: item.coverFileID || (cover ? cover.fileID : ''),
          coverUrl: item.coverUrl || (cover ? cover.imageUrl : '')
        }
      })
    } else {
      list = list.map((item) => ({ ...item, description: '' }))
    }
    return ctx.paginate(list, body, 'topicqry', `${status}|${platform}|${keyword}|${beginYMDHMS}|${endYMDHMS}|${body.order}`)
  },

  topicadd: (body, ctx) => {
    const invalid = validateTopicFields(body)
    if (invalid) return { __err: { ...invalid } }
    const title = String(body.title).trim()
    if (state.topics.some((item) => item.title === title)) {
      return { __err: { code: 'CA', content: `已存在同名主题「${title}」` } }
    }
    state.seq += 1
    const record = {
      recID: `TP${pad(state.seq, 6)}`,
      topicCode: `TOPIC-2026-${pad(state.seq, 4)}`,
      title,
      summary: body.summary || '',
      description: body.description || '',
      descriptionFileID: '',
      coverFileID: body.coverFileID || '',
      author: body.author || '',
      location: body.location || '',
      source: body.source || '',
      period: body.period || '',
      tagList: body.tagList || '',
      categoryCode: body.categoryCode || '',
      aiFlag: body.aiFlag === '1' ? '1' : '0',
      status: 'DRAFT',
      publishStatus: 'UNPUBLISHED',
      platform: body.platform || 'wechat_mp',
      layoutCode: body.layoutCode || '',
      coverUrl: `https://placehold.co/320x200/1F2937/F3F4F6?text=NEW+TOPIC`,
      assetCount: 0,
      wordCount: 0,
      artifactCount: 0,
      versionNo: 1,
      owner: body.owner || '陈立恒',
      remark: '',
      // 字段名对齐 ch_topic.txt 权威列名（裁定 a1）
      regYMDHMS: nowStr(),
      modifyYMDHMS: nowStr()
    }
    state.topics.unshift(record)
    state.versions.push({
      recID: `TV${pad(state.versions.length + 1, 6)}`,
      topicID: record.recID,
      topicCode: record.topicCode,
      versionNo: 1,
      versionName: '第 1 版',
      changeNote: '创建主题',
      operator: record.owner,
      regYMDHMS: record.regYMDHMS
    })
    return { data: record }
  },

  topicmodify: (body) => {
    const index = state.topics.findIndex((item) => item.recID === body.recID)
    if (index < 0) return { __err: { code: 'BI', content: '主题记录标识无效' } }
    const current = state.topics[index]
    if (body.status && body.status !== current.status) {
      const allowed = ALLOWED_NEXT[current.status] || []
      if (!allowed.includes(body.status)) {
        return {
          __err: {
            code: 'C7',
            // 与后端同形：MSG.content = 「<码文案>: <字段名>(字段#N);<逐条原因>」
            content: `取值非法: status(字段#16);status(主题状态) 非法跃迁: ${current.status} -> ${body.status}, ` +
              `当前状态=${current.status}, 允许跃迁=${JSON.stringify(allowed)}`,
            data: { recID: current.recID, currentStatus: current.status, targetStatus: body.status }
          }
        }
      }
    }

    // ★ 提交渲染前置强校验（对齐 _checkRenderReadiness）：详述缺失 → C4；字数不足 → C6
    //   前端已做「提前提示」，此处是后端兜底（验收要求证明双保险生效）。
    if (body.status === 'RENDERING' && body.status !== current.status) {
      const readiness = checkRenderReadiness(current, body)
      if (readiness) {
        return { __err: { ...readiness, data: { recID: current.recID, currentStatus: current.status } } }
      }
    }

    const invalid = validateTopicFields({ ...current, ...body })
    if (invalid) return { __err: { ...invalid } }

    const merged = { ...current, ...body, recID: current.recID, modifyYMDHMS: nowStr() }
    if (body.status === 'PUBLISHED') merged.publishStatus = 'PUBLISHED'

    // ★ 详述 >5000 字 → 转存文件（不静默截断），库内只保留 5000 字前缀 + wordCount 记全文口径
    //   （裁定 H：前端保存成功后必须以服务端返回刷新字数与 descriptionFileID）
    if (typeof merged.description === 'string' && merged.description) {
      const words = wordCount(merged.description)
      merged.wordCount = words
      if (words > DETAIL_MAX) {
        merged.descriptionFileID = merged.descriptionFileID || `FILE-DESC-${pad(state.seq, 6)}`
        merged.description = merged.description.slice(0, DETAIL_INLINE_PREVIEW_CHARS)
      }
    }

    state.topics[index] = merged
    return { data: merged }
  },

  topicdel: (body) => {
    const index = state.topics.findIndex((item) => item.recID === body.recID)
    if (index < 0) return { __err: { code: 'BI', content: '主题记录标识无效' } }
    const current = state.topics[index]
    if (current.status === 'RENDERING') {
      return { __err: { code: 'C7', content: '渲染中的主题不可删除，请等待渲染结束或取消任务' } }
    }
    state.topics.splice(index, 1)
    return { data: { success: '1', recID: current.recID } }
  },

  topicversionqry: (body, ctx) => {
    if (!body.topicID) return { __err: { code: 'C4', content: 'topicID 为必填项' } }
    // 两种入参容忍（裁定 a4）：recID 与 topicCode 都能命中
    const topicID = resolveTopicID(body.topicID)
    const list = state.versions
      .filter((item) => item.topicID === topicID)
      .sort((a, b) => b.versionNo - a.versionNo)
    return ctx.paginate(list, body, 'topicversionqry', topicID)
  },

  topicversionadd: (body) => {
    if (!body.topicID) return { __err: { code: 'C4', content: 'topicID 为必填项' } }
    const topicID = resolveTopicID(body.topicID)
    const versionNo = state.versions.filter((item) => item.topicID === topicID).length + 1
    const record = {
      recID: `TV${pad(state.versions.length + 1, 6)}`,
      topicID,
      versionNo,
      versionName: body.versionName || `第 ${versionNo} 版`,
      changeNote: body.changeNote || '',
      operator: body.operator || '陈立恒',
      regYMDHMS: nowStr()
    }
    state.versions.push(record)
    return { data: record }
  },

  topicversionmodify: (body) => {
    const index = state.versions.findIndex((item) => item.recID === body.recID)
    if (index < 0) return { __err: { code: 'BI', content: '版本记录标识无效' } }
    state.versions[index] = { ...state.versions[index], ...body, recID: state.versions[index].recID }
    return { data: state.versions[index] }
  },

  topicversiondel: (body) => {
    const index = state.versions.findIndex((item) => item.recID === body.recID)
    if (index < 0) return { __err: { code: 'BI', content: '版本记录标识无效' } }
    const [removed] = state.versions.splice(index, 1)
    return { data: { success: '1', recID: removed.recID } }
  }
}

export const mockTopics = state.topics
export default handlers
