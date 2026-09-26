/* ============================================================================
 * Mock · 产物域（artifactqry / artifactadd / artifactmodify / artifactdel / artifactpack）
 * ----------------------------------------------------------------------------
 * ★ 2026-09-22（Step 12）对齐真实契约：
 *   ① 记录字段改用 `ch_artifact` 权威列（见 `mock/data/records.js` 中 ARTIFACTS 的说明），
 *      数值字段一律以**字符串**返回（附录 B R-26）；
 *   ② `artifactqry` 按**服务端过滤**实现，与 2026-09-22 手改的 `funcArtifactQry`
 *      （附录 B R-28）逐参一致：`recID / jobID / topicID / kind / platform / artifactStatus /
 *      order`（+ `mode` / `beginNum` / `endNum`）；过滤条件同时进入 indexKey（与后端同款要求：
 *      否则不同筛选组合会命中同一查询缓冲，取到别的组合的数据）；
 *   ③ `order` 三态与 `common/mysqlCommon.py::queryTableGeneral`（:290-295）完全一致：
 *      `modify` → `modifyYMDHMS DESC`；`create` → `recID ASC`；其他 → `recID DESC`。
 *      ★ 禁止忽略 `order` 固定排序，否则前端写错参数在 Mock 下也会「看起来正常」；
 *   ④ **不提供 `keyword` 过滤**：真实端点与底层 `query_ch_artifact` 均无该入参（只有 searchOption），
 *      若 Mock 提供会造成「Mock 通过、真实后端静默不筛」。
 *
 * 失败样例：recID / artifactKey 无效 → BI；已过期产物修改 → C7；
 *   `artifactpack` 该平台无 READY 产物 → `CB`；**未过合规校验 → 合规侧 errCode + `packaged='0'`**（见下）。
 * ★ `artifactpack` 只做 ZIP 导出，**不产生任何投递动作**；且 ZIP **不登记 `ch_artifact`**（R-10）。
 * ★ 2026-09-22（Step 14）`artifactpack` 补齐为**同构出参**并**内置合规闸门**（原实现依赖调用方传
 *   `passed='0'` 才阻断，而真实端点无该入参 → 「Mock 通过、真实拒绝」的假象）。本文件为 Step 14
 *   越界授权小改（产出说明已逐条登记）。
 * ========================================================================== */
import { ARTIFACTS } from './data/records'
import { TOPICS } from './data/topic'
import { hexHash, pad } from './data/util'
import { handlers as complianceHandlers } from './compliance'

const state = { artifacts: ARTIFACTS.map((item) => ({ ...item })), seq: ARTIFACTS.length }

function nowStr() {
  const d = new Date()
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
}

/** 排序：三态与后端 `queryTableGeneral` 一致（附录 B R-26 口径：比较前不依赖数值类型） */
function sorted(order) {
  const list = [...state.artifacts]
  if (order === 'modify') {
    return list.sort((a, b) => String(b.modifyYMDHMS).localeCompare(String(a.modifyYMDHMS)))
  }
  if (order === 'create') {
    return list.sort((a, b) => String(a.recID).localeCompare(String(b.recID)))
  }
  return list.sort((a, b) => String(b.recID).localeCompare(String(a.recID)))
}

/**
 * 单条产物定位（导出 / 修改 / 删除用）：
 * 先按 `recID` / `artifactKey` 精确命中；未命中且给了 `topicID` 时按主题取（优先 READY），
 * 兼容「按主题导出素材包」的调用姿势。
 */
const findArtifact = (body) => {
  const direct = state.artifacts.find(
    (item) =>
      (body.recID && item.recID === String(body.recID)) ||
      (body.artifactKey && item.artifactKey === String(body.artifactKey))
  )
  if (direct) return direct
  const topicKey = String(body.topicID || '')
  if (!topicKey) return undefined
  const candidates = state.artifacts.filter((item) => item.topicID === topicKey)
  return candidates.find((item) => item.artifactStatus === 'READY') || candidates[0]
}

export const handlers = {
  artifactqry: (body, ctx) => {
    const recID = String(body.recID || '')
    const jobID = String(body.jobID || '')
    const topicID = String(body.topicID || '')
    const kind = String(body.kind || '')
    const platform = String(body.platform || '')
    const artifactStatus = String(body.artifactStatus || '')
    const order = String(body.order || 'create')

    let list = sorted(order)
    if (recID) list = list.filter((item) => item.recID === recID)
    if (jobID) list = list.filter((item) => item.jobID === jobID)
    if (topicID) list = list.filter((item) => item.topicID === topicID)
    if (kind) list = list.filter((item) => item.kind === kind)
    if (platform) list = list.filter((item) => item.platform === platform)
    if (artifactStatus) list = list.filter((item) => item.artifactStatus === artifactStatus)

    // ★ 与后端手改版一致：过滤条件进入 indexKey（不同筛选组合不得共用同一查询缓冲）
    const indexKeyParts = [recID, jobID, topicID, kind, platform, artifactStatus, order]
    return ctx.paginate(list, body, 'artifactqry', indexKeyParts.join('|'))
  },

  artifactadd: (body) => {
    if (!body.jobID || !body.topicID || !body.kind || !body.platform) {
      return { __err: { code: 'C4', content: 'jobID / topicID / kind / platform 均为必填项' } }
    }
    state.seq += 1
    const seq = state.seq
    const seqNo = String(body.seqNo || 1)
    const kind = String(body.kind)
    const record = {
      recID: `AR${pad(seq, 6)}`,
      // 幂等键口径：{jobID}:{kind}:{platform}:{seqNo}
      artifactKey: body.artifactKey || `${body.jobID}:${kind}:${body.platform}:${seqNo}`,
      jobID: String(body.jobID),
      topicID: String(body.topicID),
      kind,
      platform: String(body.platform),
      fileID: body.fileID || `FILE${pad(900 + seq, 5)}`,
      thumbnailID: body.thumbnailID || '',
      seqNo,
      artifactVer: String(body.artifactVer || 1),
      specNote: body.specNote || '',
      sizeBytes: String(body.sizeBytes || 0),
      artifactStatus: body.artifactStatus || 'READY',
      expireYMDHMS: body.expireYMDHMS || '',
      label: body.label || '',
      memo: body.memo || '',
      regID: body.regID || 'system',
      regYMDHMS: nowStr(),
      modifyID: body.modifyID || 'system',
      modifyYMDHMS: nowStr(),
      delFlag: '0',
      fileUrl: body.fileUrl || `https://placehold.co/750x1000/1F2937/F3F4F6?text=ART+${pad(seq, 3)}`,
      thumbnailUrl: body.thumbnailUrl || ''
    }
    state.artifacts.unshift(record)
    return { data: record }
  },

  artifactmodify: (body) => {
    const target = findArtifact(body)
    if (!target) return { __err: { code: 'BI', content: '产物记录标识无效' } }
    if (target.artifactStatus === 'EXPIRED') {
      return { __err: { code: 'C7', content: '已过期产物不可修改，请重新渲染生成新产物' } }
    }
    const index = state.artifacts.indexOf(target)
    state.artifacts[index] = {
      ...target,
      ...body,
      recID: target.recID,
      artifactKey: target.artifactKey,
      modifyYMDHMS: nowStr()
    }
    return { data: state.artifacts[index] }
  },

  artifactdel: (body) => {
    const target = findArtifact(body)
    if (!target) return { __err: { code: 'BI', content: '产物记录标识无效' } }
    state.artifacts.splice(state.artifacts.indexOf(target), 1)
    return { data: { success: '1', recID: target.recID } }
  },

  /**
   * 素材包 ZIP 导出（★ 只导出不投递；ZIP 本身不登记 `ch_artifact`，R-10）。
   *
   * ★ 2026-09-22（Step 14）按 `processor/artifactService.py::exportAssetPack:488-676` 重写为**同构出参**：
   *   1) 产物取数：`topicID + platform + READY`（可用 `artifactID` / `jobID` 收窄）——与
   *      `loadReadyArtifactRecords` 同口径；无可用产物 → `CB`；
   *   2) **合规闸门**：内部复用 `publishcheck`（真实后端第 6 步）；未过 → 返回**合规侧 errCode**
   *      + `data.packaged='0'` + `data.compliance` 明细（★ 页面**不得**当成功、不得触发下载）；
   *   3) 出包字段：`imageCount / entryList / extraEntryList / manifest / checkSum / checkSumMethod /
   *      zipSizeBytes / compliance / note`；`fileID` 经 `fillFileUrls` 转 `fileUrl`；
   *      ★ `localZipPath` 是服务端本地路径（前端不可用），此处模拟同样返回但不供页面使用。
   */
  artifactpack: (body) => {
    const topicKey = String(body.topicID || body.recID || body.topicCode || '')
    const topic = TOPICS.find((item) => item.recID === topicKey || item.topicCode === topicKey)
    if (!topic) return { __err: { code: 'CB', content: '未查询到该主题' } }

    const platform = String(body.platform || 'xiaohongshu')
    const layoutCode = String(body.layoutCode || topic.layoutCode || '')
    const products = state.artifacts
      .filter(
        (item) =>
          item.topicID === topic.recID &&
          item.platform === platform &&
          item.artifactStatus === 'READY' &&
          (!body.artifactID || item.recID === String(body.artifactID)) &&
          (!body.jobID || item.jobID === String(body.jobID))
      )
      .sort((a, b) => Number(a.seqNo) - Number(b.seqNo))
    if (!products.length) {
      return { __err: { code: 'CB', content: '素材包无可用产物（该主题在该平台没有 READY 产物）' } }
    }

    const complianceRtn = complianceHandlers.publishcheck({ topicID: topic.recID, platform, layoutCode })
    if (complianceRtn && complianceRtn.__err) return complianceRtn
    const complianceData = complianceRtn?.data || {}
    if (Number(complianceData.errorCount) > 0) {
      const firstError = (complianceData.issues || []).find((item) => String(item.level).toUpperCase() === 'ERROR') || {}
      return {
        __err: {
          code: String(firstError.errCode || 'C7'),
          content: String(firstError.message || '未通过合规校验，拒绝出包'),
          data: {
            ...complianceData,
            packaged: '0',
            topicID: topic.recID,
            topicCode: topic.topicCode,
            platform
          }
        }
      }
    }

    const entryList = products.map((product, index) => {
      const seqNo = Number(product.seqNo) || index + 1
      const size = /^(\d+)x(\d+)$/.exec(String(product.specNote || ''))
      const ext = String(product.kind) === 'json' ? 'txt' : 'png'
      return {
        seqNo,
        entryName: `${String(seqNo).padStart(2, '0')}_${topic.topicCode}_${String(seqNo).padStart(2, '0')}.${ext}`,
        fileName: `${topic.topicCode}_${String(seqNo).padStart(2, '0')}.${ext}`,
        fileID: String(product.fileID),
        artifactKey: String(product.artifactKey),
        width: size ? Number(size[1]) : 1080,
        height: size ? Number(size[2]) : 1440,
        sizeBytes: Number(product.sizeBytes) || 0,
        sha256: hexHash(700 + seqNo + topic.topicCode.length),
        isCover: seqNo === 1 ? '1' : '0'
      }
    })
    const checkSum = hexHash(entryList.map((item) => item.sha256).join('').length + 900)
    const imageCount = entryList.length
    const zipSizeBytes = entryList.reduce((total, item) => total + item.sizeBytes, 0) + 4096
    const extraEntryList = ['title.txt', 'content.txt', 'manifest.json', 'COPYRIGHT.txt', 'RISK_NOTICE.txt', 'SWIPE_TIPS.txt']
    const manifest = {
      topicCode: topic.topicCode,
      topicTitle: topic.title,
      generatedAt: nowStr(),
      layoutCode,
      platform,
      size: '1080x1440',
      ratio: '3:4',
      fileList: entryList,
      extraFileList: extraEntryList,
      checkSum,
      checkSumMethod: 'sha256(按 seqNo 拼接各图片文件 sha256)'
    }
    const fileID = `FILE${pad(950 + state.artifacts.indexOf(products[0]), 5)}`

    return {
      data: {
        packageKind: `${platform}_asset_pack_zip`,
        deliverMode: 'asset_pack',
        platform,
        topicID: topic.recID,
        topicCode: topic.topicCode,
        layoutCode,
        jobID: String(products[0].jobID || ''),
        fileID,
        fileUrl: `https://placehold.co/320x200/374151/F3F4F6?text=ZIP+${topic.topicCode}`,
        fileName: `${topic.topicCode}_${nowStr()}_assetpack.zip`,
        // ★ 服务端本地路径：前端**不可用**（仅登记以保持同构）
        localZipPath: `/tmp/ch_assetpack/${topic.topicCode}.zip`,
        zipSizeBytes,
        zipSha256: hexHash(1200),
        imageCount,
        entryList,
        extraEntryList,
        manifest,
        checkSum,
        checkSumMethod: manifest.checkSumMethod,
        compliance: {
          passed: String(complianceData.passed || '1'),
          issueCount: Number(complianceData.issueCount) || 0,
          errorCount: Number(complianceData.errorCount) || 0,
          warningCount: Number(complianceData.warningCount) || 0,
          issues: complianceData.issues || []
        },
        exportedAt: nowStr(),
        note: '★ 只导出不投递：素材包须在官方创作服务平台手动发布'
      }
    }
  }
}

export const mockArtifacts = state.artifacts
export default handlers
