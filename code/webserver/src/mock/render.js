/* ============================================================================
 * Mock · 渲染域（topicrender sync/job + ch_render_job CRUD）
 * ----------------------------------------------------------------------------
 * · `sync`：直接返回 `content` + `meta` + `products`（PNG 类平台）+ `fileIDs` + `reused`；
 * · `job`：建任务后立即返回 `jobCode` + `PENDING`，任务进入 `renderjobqry` 可查（四态样例）；
 * · 失败样例：版式 × 平台组合不受支持 → `C7`（判定以前端字典 `LAYOUT_PLATFORM_MATRIX` 为准）；
 *   缺 `layoutCode` → `C4`；主题不存在 → `CB`。
 * ========================================================================== */
import { isLayoutAllowed } from '@/config/chOptions'
import { RENDER_JOBS } from './data/records'
import { TOPICS } from './data/topic'
import { hexHash, pad } from './data/util'

const state = {
  jobs: RENDER_JOBS.map((item) => ({ ...item })),
  seq: RENDER_JOBS.length
}

function nowStr() {
  const d = new Date()
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
}

/** topicID 语义对齐（裁定 a4）：topicID 指 ch_topic.recID，同时容忍 topicCode 入参 */
const findTopic = (body) =>
  TOPICS.find(
    (item) =>
      (body.topicID && (item.recID === body.topicID || item.topicCode === body.topicID)) ||
      (body.topicCode && item.topicCode === body.topicCode)
  )

/** PNG 类平台的产物列表（seqNo / kind / fileID / fileUrl / 尺寸 / sha256 / isCover） */
function buildProducts(topic, layoutCode, count) {
  return Array.from({ length: count }, (unused, i) => ({
    seqNo: i + 1,
    kind: i === 0 ? 'cover' : 'body',
    fileID: `FILE${pad(600 + i, 5)}`,
    fileUrl: `https://placehold.co/1080x1440/1F2937/F3F4F6?text=P${pad(i + 1, 2)}`,
    width: 1080,
    height: 1440,
    sizeBytes: 1_500_000 + i * 4096,
    sha256: hexHash(i + 501 + topic.topicCode.length),
    isCover: i === 0 ? '1' : '0',
    layoutCode
  }))
}

/** 渲染片段（预览用；预览区始终走 .preview-scope 浅色隔离，此处只产出内容） */
function buildContent(topic, layoutCode) {
  return `<article class="ch-preview" data-layout="${layoutCode}">
  <h1>${topic.title}</h1>
  <p>${topic.summary || ''}</p>
  <figure><img src="${topic.coverUrl}" alt="${topic.title}" /></figure>
  <p>本片段由 Mock 渲染器生成，用于验证预览链路与版式容器；真实渲染由 renderApi 产出。</p>
</article>`
}

export const handlers = {
  topicrender: (body) => {
    const topic = findTopic(body)
    if (!topic) return { __err: { code: 'CB', content: '未查询到该主题' } }
    if (!body.layoutCode) return { __err: { code: 'C4', content: 'layoutCode 为必填项' } }
    const platform = body.platform || topic.platform
    if (!isLayoutAllowed(body.layoutCode, platform)) {
      return { __err: { code: 'C7', content: `版式 ${body.layoutCode} 不支持平台 ${platform}` } }
    }
    const renderMode = body.renderMode === 'job' ? 'job' : 'sync'
    const startedAt = nowStr()

    if (renderMode === 'job') {
      state.seq += 1
      const job = {
        recID: `RJ${pad(state.seq, 6)}`,
        jobCode: `JOB-${pad(state.seq, 5)}`,
        topicID: topic.recID,
        topicCode: topic.topicCode,
        topicTitle: topic.title,
        layoutCode: body.layoutCode,
        platform,
        jobStatus: 'PENDING',
        progress: 0,
        retryCount: 0,
        renderMode: 'job',
        errorCode: '',
        errorMsg: '',
        costMs: 0,
        operator: body.operator || topic.owner,
        startedYMDHMS: startedAt,
        finishedYMDHMS: '',
        regYMDHMS: startedAt
      }
      state.jobs.unshift(job)
      return { data: { jobCode: job.jobCode, jobStatus: 'PENDING', renderMode: 'job', topicID: topic.recID, platform } }
    }

    const outputKind = platform === 'generic' ? (body.exportKind || 'html') : platform === 'xiaohongshu' ? 'png' : 'html'
    const isPng = outputKind === 'png'
    const products = isPng ? buildProducts(topic, body.layoutCode, 4) : []
    return {
      data: {
        content: buildContent(topic, body.layoutCode),
        meta: {
          layoutCode: body.layoutCode,
          layoutType: 'stack',
          platform,
          outputKind,
          inlineStyled: !isPng,
          imageCount: products.length,
          renderMode: 'sync',
          overrideSpec: body.specOverride || body.overrideSpec || null
        },
        products,
        fileIDs: products.map((item) => item.fileID),
        reused: '0'
      }
    }
  },

  renderjobqry: (body, ctx) => {
    const keyword = String(body.keyword || '').trim()
    const jobStatus = String(body.jobStatus || '')
    let list = [...state.jobs]
    if (body.jobCode) list = list.filter((item) => item.jobCode === body.jobCode)
    if (body.topicID) list = list.filter((item) => item.topicCode === body.topicID || item.topicID === body.topicID)
    if (jobStatus) list = list.filter((item) => item.jobStatus === jobStatus)
    if (keyword) list = list.filter((item) => item.topicTitle.includes(keyword) || item.jobCode.includes(keyword))
    return ctx.paginate(list, body, 'renderjobqry', `${jobStatus}|${keyword}`)
  },

  renderjobadd: (body) => {
    state.seq += 1
    const record = {
      recID: `RJ${pad(state.seq, 6)}`,
      jobCode: `JOB-${pad(state.seq, 5)}`,
      jobStatus: 'PENDING',
      progress: 0,
      retryCount: 0,
      errorCode: '',
      errorMsg: '',
      operator: body.operator || '陈立恒',
      startedYMDHMS: nowStr(),
      finishedYMDHMS: '',
      regYMDHMS: nowStr(),
      ...body
    }
    state.jobs.unshift(record)
    return { data: record }
  },

  renderjobmodify: (body) => {
    const index = state.jobs.findIndex((item) => item.recID === body.recID || item.jobCode === body.jobCode)
    if (index < 0) return { __err: { code: 'BI', content: '渲染任务标识无效' } }
    const current = state.jobs[index]
    if (body.action === 'retry') {
      if (current.jobStatus !== 'FAILED') {
        return { __err: { code: 'C7', content: '仅失败的任务可重试' } }
      }
      state.jobs[index] = {
        ...current,
        jobStatus: 'RUNNING',
        progress: 10,
        retryCount: current.retryCount + 1,
        errorCode: '',
        errorMsg: '',
        startedYMDHMS: nowStr(),
        finishedYMDHMS: ''
      }
      return { data: state.jobs[index] }
    }
    if (body.action === 'cancel') {
      if (!['PENDING', 'RUNNING'].includes(current.jobStatus)) {
        return { __err: { code: 'C7', content: '仅排队中 / 运行中的任务可取消' } }
      }
      state.jobs[index] = { ...current, jobStatus: 'FAILED', progress: 0, errorCode: 'E1', errorMsg: '用户取消', finishedYMDHMS: nowStr() }
      return { data: state.jobs[index] }
    }
    state.jobs[index] = { ...current, ...body, recID: current.recID }
    return { data: state.jobs[index] }
  },

  renderjobdel: (body) => {
    const index = state.jobs.findIndex((item) => item.recID === body.recID || item.jobCode === body.jobCode)
    if (index < 0) return { __err: { code: 'BI', content: '渲染任务标识无效' } }
    const [removed] = state.jobs.splice(index, 1)
    return { data: { success: '1', recID: removed.recID } }
  }
}

export const mockJobs = state.jobs
export default handlers
