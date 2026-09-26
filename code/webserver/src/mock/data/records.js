/* ============================================================================
 * Mock 数据 · 渲染任务 / 产物 / 投递记录（确定性生成）
 * ----------------------------------------------------------------------------
 * 渲染任务：四种状态样例（PENDING / RUNNING / DONE / FAILED）齐备；
 * 产物：按渲染任务派生，含 EXPIRED（已过期）与「未设置保留期」（长期保留）样例；
 * 投递记录：公众号草稿投递（draft_box），★ 小红书仅素材包导出，不产生投递记录。
 *
 * ★ topicID 语义对齐（裁定 a4）：`topicID = ch_topic.recID`
 *   （对齐 ch_render_job.topicID / ch_artifact.topicID / ch_publish_record.topicID），
 *   `topicCode` 保留作冗余展示字段；时间列名对齐 ch_*.txt（regYMDHMS = 创建时间）。
 * ========================================================================== */
import { hoursBefore, pad, pick, ymdhms } from './util'
import { TOPICS } from './topic'

const JOB_STATUS_CYCLE = ['PENDING', 'RUNNING', 'DONE', 'FAILED']
const FAIL_REASONS = [
  { code: 'E1', msg: '渲染失败：正文图 3 加载超时' },
  { code: 'E2', msg: '截图超时：长图拼接超过 60 秒' },
  { code: 'E3', msg: '产物生成失败：磁盘写入被拒绝' },
  { code: 'E4', msg: '外链图片需转存，但存储凭据缺失' }
]

function buildJobs(count = 24) {
  return Array.from({ length: count }, (unused, i) => {
    const topic = TOPICS[i]
    const jobStatus = pick(JOB_STATUS_CYCLE, i)
    const reason = jobStatus === 'FAILED' ? pick(FAIL_REASONS, i) : null
    const startedAt = hoursBefore(Math.max(1, 300 - i * 11))
    const finishedAt = hoursBefore(Math.max(0, 300 - i * 11 - 1))
    return {
      recID: `RJ${pad(i + 1, 6)}`,
      jobCode: `JOB-${pad(i + 1, 5)}`,
      topicID: topic.recID,
      topicCode: topic.topicCode,
      topicTitle: topic.title,
      layoutCode: topic.layoutCode,
      platform: topic.platform,
      jobStatus,
      progress: jobStatus === 'DONE' ? 100 : jobStatus === 'RUNNING' ? 35 + (i % 5) * 9 : 0,
      retryCount: jobStatus === 'FAILED' ? 1 : 0,
      renderMode: i % 4 === 0 ? 'sync' : 'job',
      errorCode: reason ? reason.code : '',
      errorMsg: reason ? reason.msg : '',
      costMs: jobStatus === 'DONE' ? 8200 + i * 137 : 0,
      operator: topic.owner,
      startedYMDHMS: ymdhms(startedAt),
      finishedYMDHMS: jobStatus === 'DONE' || jobStatus === 'FAILED' ? ymdhms(finishedAt) : '',
      regYMDHMS: ymdhms(startedAt)
    }
  })
}

/** 渲染任务（四种状态样例齐备） */
export const RENDER_JOBS = buildJobs(24)

/* ---------------------------------------------------------------------------
 * 产物台账（`ch_artifact`，权威列见 `database/ch_artifact.txt`）
 * ---------------------------------------------------------------------------
 * ★ 2026-09-22（Step 12）对齐真实契约：原实现使用自造字段（`artifactID` / `outputKind` /
 *   `pageCount` / `width` / `height` / `packaged` / `sha256` / `layoutCode`），与权威列不符，
 *   会让前端页面在 Mock 下「看起来正常」而真实后端一片空白。现按权威列重写：
 *   `recID / artifactKey / jobID / topicID / kind / platform / fileID / thumbnailID / seqNo /
 *    artifactVer / specNote / sizeBytes / artifactStatus / expireYMDHMS / label / memo /
 *    regID / regYMDHMS / modifyID / modifyYMDHMS / delFlag`。
 *   另附 `fileUrl` / `thumbnailUrl` —— 模拟后端 `chCommon.fillFileUrls` 把 fileID 转 URL 的结果
 *   （§2.4.5：前端只读 `*Url`，禁止拿 fileID 当 URL）。
 * ★ **按渲染任务派生**（`jobID` = `ch_render_job.recID`），使 P-07 的「按任务分组」与组头
 *   「查看任务」跳转在 Mock 下可复现；同一 job 的 PNG 图集按 `seqNo` 递增（seqNo=1 即封面）。
 * ★ 样例齐备：`READY` / `EXPIRED`（每 4 个任务一组过期）、`expireYMDHMS` 空（长期保留，
 *   每 3 个任务一组）、无缩略图（html / json，用于验证「按 kind 显示类型图标」）。
 * ★ 数值字段一律以**字符串**返回（附录 B R-26：真实后端即此形态）。
 * ------------------------------------------------------------------------- */
const ARTIFACT_KIND_BY_PLATFORM = { wechat_mp: 'html', xiaohongshu: 'png', generic: 'html' }

function buildArtifacts(jobCount = 16) {
  const rows = []
  RENDER_JOBS.slice(0, jobCount).forEach((job, jobIndex) => {
    const baseKind = ARTIFACT_KIND_BY_PLATFORM[job.platform] || 'html'
    // generic 平台交替产出 html / json：覆盖 json 样例与「specNote 缺失 → 」（裁定 I）
    const kind = baseKind === 'html' && job.platform === 'generic' && jobIndex % 2 === 0 ? 'json' : baseKind
    const isPng = kind === 'png'
    // PNG 类平台为图集（4–6 张，seqNo 递增）；HTML / JSON 为单件（seqNo=1）
    const count = isPng ? 4 + (jobIndex % 3) : 1
    // 过期样例整组出现，便于按任务分组观察「主操作 = 重新渲染」
    const artifactStatus = jobIndex % 4 === 3 ? 'EXPIRED' : 'READY'
    // 保留期：每 3 个任务留 1 组「未设置保留期」→ 前端须显示「长期保留」（裁定 E）
    const noRetention = jobIndex % 3 === 0
    const regAt = hoursBefore(Math.max(2, 420 - jobIndex * 16))
    const expireAt = hoursBefore(-(24 * 30 - jobIndex * 8))
    for (let i = 0; i < count; i += 1) {
      const seqNo = i + 1
      const seq = rows.length + 1
      const stamp = pad(seq, 3)
      rows.push({
        recID: `AR${pad(seq, 6)}`,
        // 幂等键口径：`{jobID}:{kind}:{platform}:{seqNo}`（ch_artifact.artifactKey 注释）
        artifactKey: `${job.recID}:${kind}:${job.platform}:${seqNo}`,
        jobID: job.recID,
        topicID: job.topicID,
        kind,
        platform: job.platform,
        fileID: `FILE${pad(200 + seq, 5)}`,
        thumbnailID: isPng ? `FILE${pad(500 + seq, 5)}` : '',
        seqNo: String(seqNo),
        artifactVer: String(1 + (jobIndex % 3)),
        specNote: kind === 'json' ? '' : isPng ? '1080x1440' : '750x1000',
        sizeBytes: String((isPng ? 1_600_000 : 420_000) + seq * 1024),
        artifactStatus,
        expireYMDHMS: noRetention ? '' : ymdhms(expireAt),
        label: '',
        memo: '',
        regID: 'system',
        regYMDHMS: ymdhms(regAt),
        modifyID: 'system',
        modifyYMDHMS: ymdhms(regAt),
        delFlag: '0',
        // fillFileUrls 的模拟（仅 png 有缩略图）
        fileUrl: `https://placehold.co/${isPng ? '1080x1440' : '750x1000'}/1F2937/F3F4F6?text=${kind.toUpperCase()}+${stamp}`,
        thumbnailUrl: isPng ? `https://placehold.co/320x200/374151/F3F4F6?text=PNG+${stamp}` : ''
      })
    }
  })
  return rows
}

/** 产物台账（READY / EXPIRED / 长期保留 / 无缩略图 / 图集 样例齐备） */
export const ARTIFACTS = buildArtifacts(16)

const PUBLISH_STATUS_CYCLE = ['PUBLISHED', 'DRAFTED', 'FAILED', 'PUBLISHED']
const PUBLISH_FAIL = { code: 'F0', msg: '凭据解密失败，请在账号管理重新登记' }

/** 投递记录（仅 wechat_mp：公众号草稿箱） */
export const PUBLISH_RECORDS = Array.from({ length: 30 }, (unused, i) => {
  const topic = TOPICS[i + 2]
  const publishStatus = pick(PUBLISH_STATUS_CYCLE, i)
  const artifact = ARTIFACTS[i]
  // layoutCode 属展示冗余（ch_publish_record 无该列）→ 取该产物所属任务，避免下标越界
  const job = RENDER_JOBS.find((item) => item.recID === artifact.jobID) || RENDER_JOBS[0]
  const createdAt = hoursBefore(Math.max(1, 360 - i * 12))
  return {
    recID: `PR${pad(i + 1, 6)}`,
    publishRecordID: `PUB-${pad(i + 1, 5)}`,
    topicID: topic.recID,
    topicCode: topic.topicCode,
    topicTitle: topic.title,
    platform: 'wechat_mp',
    deliverMode: 'draft_box',
    accountID: `ACC-${pad(1 + (i % 2), 3)}`,
    accountName: i % 2 === 0 ? '内容中枢 · 主号' : '内容中枢 · 备用号',
    layoutCode: job.layoutCode,
    // ★ `ch_publish_record.artifactId` = `ch_artifact.recID`（权威注释，BIGINT）
    artifactID: artifact.recID,
    artifactTitle: `${topic.title}（${job.layoutCode}）`,
    publishStatus,
    autoPublish: '0',
    remoteID: publishStatus === 'FAILED' ? '' : `draft_media_${pad(9000 + i, 6)}`,
    errorCode: publishStatus === 'FAILED' ? PUBLISH_FAIL.code : '',
    errorMsg: publishStatus === 'FAILED' ? PUBLISH_FAIL.msg : '',
    costMs: publishStatus === 'FAILED' ? 620 : 1450 + i * 23,
    idempotencyKey: `IDEM-${pad(i + 1, 6)}`,
    operator: topic.owner,
    createdAtYMDHMS: ymdhms(createdAt),
    regYMDHMS: ymdhms(createdAt)
  }
})

export default RENDER_JOBS
