/* ============================================================================
 * Mock · 素材域（assetqry ≥60 条 / assetadd 内容级去重 / assetdel 默认放行 …）
 * ----------------------------------------------------------------------------
 * ★ Step 8（P-04 素材图库）对齐后端事实的三处小改（已在本步交付说明登记）：
 *   1) `topicassetqry` 补 **fileID 反查分支**（真实 `query_ch_topic_asset` 的 condList 含 fileID，
 *      `processor/assetService.queryTopicAsset:1027-1034`）——否则 P-04 无法在 Mock 下验引用关系；
 *   2) `assetdel` **默认放行**（真实 `deleteAsset` 为软删、**不做引用检查**，附录 B R-21）。
 *      旧 Mock 以「被引用 → C7」拦截与后端不一致；改为保留开发态开关
 *      `window.__MOCK_ASSET_DEL_BLOCK__ === true` 时返回 C7，用于演示阻断分支；
 *      ★ 前端不得把「后端会拦」当安全假设 —— 引用确认是**客户端安全网**。
 *   3) `assetadd` 的 `localPath` 路径补「服务端算 hash → 去重复用」：真实后端在只有 localPath 时
 *      用 `computeContentHash(localPath)` 落唯一键，**请求带 contentHash 且命中才回 dedupHit='1'**
 *      （`assetService.addAsset:698-710`）。Mock 以 localPath 派生确定性 sha256 模拟，
 *      使「同一张图上传两次 → 第二次 dedupHit='1'」可稳定验收（P-04 验收第 2 项）。
 *   另：`assetqry` 补齐真实筛选面 —— `keyword` 命中 **origName / objectName**（likeOrList）、
 *      `fileExt`、`fileSystem`、`processStatus`、`ownerID`、`order`（create=recID ASC /
 *      modify=modifyYMDHMS DESC / 其他=recID DESC）与 `mode:'short'` 列裁剪
 *      （`mysqlCommon.query_ch_asset` + `getShortColumns`）。
 *
 * ★ Step 7 对齐（保留）：
 *   `topicassetadd` 为幂等 upsert（assetKey = `{topicID}:{fileID}`），`usageType='cover'` 时由服务端
 *   把旧封面降级为 body；`topicassetmodify` 的 `orderList` 只批量重排 sortOrder；`topicassetdel`
 *   只解绑（软删），不动 `ch_asset` 本体。
 *
 * 可触发失败样例：
 *   · `assetadd` 的 `contentHash` 非 64 位小写 sha256 → D0；
 *   · `assetadd` 既无 localPath 也无 fileID+contentHash → C4；
 *   · `assetmodify` 改动 fileID / contentHash / fileSystem → C7；label > 32 / memo > 200 → C5；
 *   · `window.__MOCK_ASSET_DEL_BLOCK__ = true` 时删除被引用素材 → C7。
 * ========================================================================== */
import { ASSETS, TOPIC_ASSETS } from './data/asset'
import { TOPICS } from './data/topic'
import { hexHash, pad } from './data/util'

const SHA256_LOWER = /^[0-9a-f]{64}$/
/** ch_asset 的 short 列（对齐 mysqlCommon.CH_QUERY_SHORT_COLUMNS） */
const SHORT_FIELDS = ['recID', 'fileID', 'thumbnailID', 'fileExt', 'origSizeBytes', 'width', 'height', 'processStatus', 'regYMDHMS']
const LABEL_MAX = 32
const MEMO_MAX = 200
const IMMUTABLE_FIELDS = ['fileID', 'contentHash', 'fileSystem']

const state = {
  assets: ASSETS.map((item) => ({ ...item })),
  links: Object.fromEntries(Object.entries(TOPIC_ASSETS).map(([key, list]) => [key, list.map((item) => ({ ...item }))])),
  seq: ASSETS.length,
  linkSeq: Object.values(TOPIC_ASSETS).reduce((total, list) => total + list.length, 0)
}

function nowStr() {
  const d = new Date()
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
}

/** 字符串 → 稳定种子（FNV-1a），供 hexHash 生成确定性 sha256 形态串 */
function seedFromText(text) {
  let hash = 2166136261
  for (let i = 0; i < String(text).length; i += 1) {
    hash ^= String(text).charCodeAt(i)
    hash = Math.imul(hash, 16777619) >>> 0
  }
  return hash || 1
}

/** 模拟服务端 `computeContentHash(localPath)`：同一 localPath 必得同一 64 位小写 sha256 */
const hashOfLocalPath = (localPath) => hexHash(seedFromText(localPath))

/** 排序口径与后端 queryTableGeneral:290-295 一致 */
const sortedAssets = (order) => {
  const list = [...state.assets]
  if (order === 'modify') return list.sort((a, b) => String(b.modifyYMDHMS).localeCompare(String(a.modifyYMDHMS)))
  if (order === 'create') return list.sort((a, b) => String(a.recID).localeCompare(String(b.recID)))
  return list.sort((a, b) => String(b.recID).localeCompare(String(a.recID)))
}

/** 全部附图绑定记录（跨主题），供 fileID / recID 反查 */
const allLinks = () => Object.values(state.links).flatMap((list) => list)

const linkCountOf = (fileID) => allLinks().filter((item) => item.fileID === fileID).length

const extOf = (name) => {
  const match = /\.([A-Za-z0-9]+)$/.exec(String(name || ''))
  return match ? match[1].toLowerCase() : ''
}

const MIME_BY_EXT = { png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', webp: 'image/webp', gif: 'image/gif' }

/**
 * topicID 语义对齐（裁定 a4）：接受 ch_topic.recID 或 topicCode，统一归一到 recID，
 * 兼容已交付的 Step 5 与后续步骤（两者都传入同一个主题时都能命中同一份附图）。
 */
const resolveTopicID = (input) => {
  const value = String(input || '')
  if (!value) return ''
  const hit = TOPICS.find((item) => item.recID === value || item.topicCode === value)
  return hit ? hit.recID : value
}

const linksOf = (topicID) => state.links[resolveTopicID(topicID)] || []

/**
 * 封面唯一：把该主题下**其他** usageType=cover 的附图降级为 body。
 * ★ 对齐后端 `assetService.demoteOtherCoverAssets`（裁定 C：降级由服务端完成，前端不自造逻辑）。
 */
function demoteOtherCovers(list, keepAssetKey) {
  list.forEach((item) => {
    if (item.assetKey === keepAssetKey) return
    if (item.usageType === 'cover') {
      item.usageType = 'body'
      item.isCover = '0'
    }
  })
}

export const handlers = {
  assetqry: (body, ctx) => {
    const keyword = String(body.keyword || '').trim().toLowerCase()
    const fileExt = String(body.fileExt || '').trim().toLowerCase()
    let list = sortedAssets(String(body.order || 'create'))
    if (body.recID) list = list.filter((item) => item.recID === body.recID)
    if (body.fileID) list = list.filter((item) => item.fileID === body.fileID)
    if (body.contentHash) list = list.filter((item) => item.contentHash === body.contentHash)
    if (body.fileSystem) list = list.filter((item) => item.fileSystem === body.fileSystem)
    if (body.processStatus) list = list.filter((item) => item.processStatus === body.processStatus)
    if (body.ownerID) list = list.filter((item) => item.ownerID === body.ownerID)
    if (fileExt) list = list.filter((item) => String(item.fileExt || '').toLowerCase() === fileExt)
    // ★ keyword 的命中面 = origName / objectName（对齐 mysqlCommon.query_ch_asset 的 likeOrList）
    if (keyword) {
      list = list.filter((item) => `${item.origName || ''} ${item.objectName || ''}`.toLowerCase().includes(keyword))
    }
    const mode = String(body.mode || 'full')
    const rows = mode === 'short'
      ? list.map((item) => Object.fromEntries(SHORT_FIELDS.map((field) => [field, item[field]])))
      : list
    return ctx.paginate(rows, body, 'assetqry', `${mode}|${fileExt}|${keyword}|${body.order || ''}`)
  },

  assetadd: (body) => {
    if (!body.localPath && !body.fileID) {
      return { __err: { code: 'C4', content: '需提供 localPath，或 fileID + contentHash' } }
    }
    const providedHash = String(body.contentHash || '')
    if (providedHash && !SHA256_LOWER.test(providedHash)) {
      return { __err: { code: 'D0', content: 'contentHash 必须为 64 位小写十六进制 sha256' } }
    }
    if (!body.localPath && !providedHash) {
      return { __err: { code: 'C4', content: 'fileID 登记时 contentHash 为必填' } }
    }
    // 模拟服务端「无 contentHash 时按 localPath 算 sha256」
    const contentHash = providedHash || hashOfLocalPath(body.localPath)
    // ★ 内容级去重：命中即复用既有素材，直接返回 dedupHit='1'（不重复上传、不新增记录）
    const hit = state.assets.find((item) => item.contentHash === contentHash)
    if (hit) {
      // 开发态留痕：Mock 短路了网络，DevTools Network 看不到响应，故把关键出参打到 console
      console.info('[mock] assetadd 响应', { dedupHit: '1', recID: hit.recID, fileID: hit.fileID, contentHash })
      return { data: { ...hit, dedupHit: '1' } }
    }

    state.seq += 1
    const width = Number(body.width) || 1080
    const height = Number(body.height) || 1440
    const label = pad(state.seq, 3)
    const fileExt = String(body.fileExt || extOf(body.origName || body.localPath) || 'png').toLowerCase()
    const origName = body.origName || `${body.fileName || `asset-${label}`}`
    const processStatus = body.processStatus || 'PROCESSED'
    const fileSystem = body.fileSystem || 'SELFFILE'
    const record = {
      recID: `AS${pad(state.seq, 6)}`,
      fileID: body.fileID || `FILE${pad(state.seq, 5)}`,
      thumbnailID: `THUMB${pad(state.seq, 5)}`,
      fileName: origName,
      origName,
      objectName: body.objectName || `ASSET_${nowStr()}_${pad(state.seq, 5)}.${fileExt}`,
      fileExt,
      mimeType: body.mimeType || MIME_BY_EXT[fileExt] || 'application/octet-stream',
      fileSystem,
      storageBucket: body.storageBucket || (fileSystem === 'SELFFILE' ? 'local' : `ch-asset-${pad(state.seq, 3)}`),
      origSizeBytes: Number(body.origSizeBytes) || 1024 * 1024,
      sizeBytes: Number(body.origSizeBytes) || 1024 * 1024,
      width,
      height,
      contentHash,
      label: body.label || '',
      memo: body.memo || '',
      caption: body.caption || origName,
      usageType: body.usageType || 'body',
      processStatus,
      exifStripped: body.exifStripped || '0',
      dedupHit: '0',
      imageUrl: `https://placehold.co/${width}x${height}/1F2937/F3F4F6?text=IMG+${label}`,
      thumbnailUrl: `https://placehold.co/320x${Math.round((320 * height) / width)}/1F2937/F3F4F6?text=IMG+${label}`,
      thumbnails: {
        320: `https://placehold.co/320x${Math.round((320 * height) / width)}/1F2937/F3F4F6?text=IMG+${label}`,
        640: `https://placehold.co/640x${Math.round((640 * height) / width)}/1F2937/F3F4F6?text=IMG+${label}`,
        1280: `https://placehold.co/1280x${Math.round((1280 * height) / width)}/1F2937/F3F4F6?text=IMG+${label}`
      },
      source: body.localPath ? '服务端本地路径' : '图库同步',
      uploadedBy: body.uploadedBy || '陈立恒',
      ownerID: body.ownerID || 'chenlh',
      regYMDHMS: nowStr(),
      modifyYMDHMS: nowStr()
    }
    state.assets.unshift(record)
    console.info('[mock] assetadd 响应', { dedupHit: '0', recID: record.recID, fileID: record.fileID, contentHash })
    return { data: record }
  },

  assetmodify: (body) => {
    const index = state.assets.findIndex((item) => item.recID === body.recID || item.fileID === body.fileID)
    if (index < 0) return { __err: { code: 'BI', content: '素材记录标识无效' } }
    const current = state.assets[index]
    // 落库快照字段不可改（对齐 assetService.modifyAsset:786-790）
    for (const field of IMMUTABLE_FIELDS) {
      const next = body[field] === undefined ? '' : String(body[field])
      if (next && next !== String(current[field])) {
        return { __err: { code: 'C7', content: `取值非法: ${field}(字段);${field} 不可修改(素材落库快照字段)` } }
      }
    }
    if (body.label && String(body.label).length > LABEL_MAX) {
      return { __err: { code: 'C5', content: `label 长度=${String(body.label).length} 超上限 ${LABEL_MAX}` } }
    }
    if (body.memo && String(body.memo).length > MEMO_MAX) {
      return { __err: { code: 'C5', content: `memo 长度=${String(body.memo).length} 超上限 ${MEMO_MAX}` } }
    }
    const patch = { ...body }
    IMMUTABLE_FIELDS.forEach((field) => delete patch[field])
    state.assets[index] = { ...current, ...patch, recID: current.recID, modifyYMDHMS: nowStr() }
    return { data: state.assets[index] }
  },

  assetdel: (body) => {
    const index = state.assets.findIndex((item) => item.recID === body.recID || item.fileID === body.fileID)
    if (index < 0) return { __err: { code: 'BI', content: '素材记录标识无效' } }
    const target = state.assets[index]
    // ★ R-21：真实 deleteAsset 为软删且**不做引用检查** → 默认放行；
    //   仅开发态显式打开开关时模拟「被引用 → C7」的阻断分支（演示用）。
    if (typeof window !== 'undefined' && window.__MOCK_ASSET_DEL_BLOCK__ === true) {
      const referenced = linkCountOf(target.fileID)
      if (referenced) {
        return { __err: { code: 'C7', content: `[演示开关] 素材「${target.caption}」已被 ${referenced} 个主题引用` } }
      }
    }
    state.assets.splice(index, 1)
    return { data: { success: '1', recID: target.recID, fileID: target.fileID, delFlag: '1' } }
  },

  topicassetqry: (body) => {
    const fileID = String(body.fileID || '')
    // ★ fileID 反查：真实 query_ch_topic_asset 的 condList 含 fileID（assetService:1027-1034）
    if (fileID) {
      const list = allLinks().filter((item) => item.fileID === fileID).sort((a, b) => a.sortOrder - b.sortOrder)
      return { data: list, total: list.length }
    }
    if (body.recID) {
      const hit = allLinks().filter((item) => item.recID === body.recID)
      return { data: hit, total: hit.length }
    }
    if (!body.topicID) return { __err: { code: 'C4', content: 'topicID 为必填项' } }
    const list = [...linksOf(body.topicID)].sort((a, b) => a.sortOrder - b.sortOrder)
    return { data: list, total: list.length }
  },

  topicassetadd: (body) => {
    if (!body.topicID || !body.fileID) return { __err: { code: 'C4', content: 'topicID 与 fileID 均为必填项' } }
    const topicID = resolveTopicID(body.topicID)
    const list = linksOf(topicID)
    const assetKey = `${topicID}:${body.fileID}`
    const usageType = body.usageType || 'body'

    // ★ 幂等 upsert（对齐后端 addTopicAsset = chCommon.upsertByUniqueKey）：
    //   同一 assetKey 重复绑定**不报错**，按传入字段更新；★ 设为 cover 时把旧封面降级为 body
    //   （后端 demoteOtherCoverAssets；裁定 C：前端不得自造降级逻辑）。
    const existed = list.find((item) => item.assetKey === assetKey)
    if (existed) {
      if (body.caption) existed.assetName = body.caption
      existed.usageType = usageType
      existed.isCover = usageType === 'cover' ? '1' : '0'
      if (body.sortOrder !== undefined && body.sortOrder !== '') {
        existed.sortOrder = Number(body.sortOrder) || existed.sortOrder
      }
      if (usageType === 'cover') demoteOtherCovers(list, assetKey)
      return { data: existed }
    }

    const asset = state.assets.find((item) => item.fileID === body.fileID)
    if (!asset) return { __err: { code: 'BI', content: '素材不存在或 fileID 无效' } }
    state.linkSeq += 1
    const record = {
      recID: `TA${pad(state.linkSeq, 6)}`,
      topicID,
      assetKey,
      fileID: asset.fileID,
      assetName: body.caption || asset.caption,
      caption: body.caption || asset.caption,
      usageType,
      sortOrder: body.sortOrder || list.length + 1,
      isCover: usageType === 'cover' ? '1' : '0',
      width: asset.width,
      height: asset.height,
      imageUrl: asset.imageUrl,
      thumbnailUrl: asset.thumbnailUrl,
      regYMDHMS: nowStr()
    }
    if (!state.links[topicID]) state.links[topicID] = []
    state.links[topicID].push(record)
    if (usageType === 'cover') demoteOtherCovers(list, assetKey)
    return { data: record }
  },

  topicassetmodify: (body) => {
    const list = linksOf(body.topicID)
    if (!list.length) return { __err: { code: 'CB', content: '该主题暂无附图' } }

    // 批量重排：orderList = [{ recID, sortOrder }]（对齐 assetService.reorderTopicAssets）
    if (Array.isArray(body.orderList) && body.orderList.length) {
      body.orderList.forEach((entry) => {
        const hit = list.find((item) => item.recID === entry.recID)
        if (hit) hit.sortOrder = Number(entry.sortOrder) || hit.sortOrder
      })
      list.sort((a, b) => a.sortOrder - b.sortOrder)
      return { data: list, total: list.length }
    }

    const index = list.findIndex((item) => item.recID === body.recID || item.assetKey === body.assetKey)
    if (index < 0) return { __err: { code: 'BI', content: '附图记录标识无效' } }
    const current = list[index]

    // 幂等键不可改（对齐后端 modifyTopicAsset：topicID / fileID / assetKey 传了就必须与现值一致）
    for (const field of ['topicID', 'fileID', 'assetKey']) {
      const next = body[field] === undefined ? '' : String(body[field])
      if (next && next !== String(current[field])) {
        return { __err: { code: 'C7', content: `取值非法: ${field}(字段);${field} 不可修改(附图绑定的幂等键)` } }
      }
    }

    const patch = { ...body }
    delete patch.topicID
    delete patch.fileID
    delete patch.assetKey
    delete patch.orderList
    if (patch.sortOrder !== undefined) patch.sortOrder = Number(patch.sortOrder) || current.sortOrder
    Object.assign(current, patch)

    if (current.usageType === 'cover') {
      current.isCover = '1'
      demoteOtherCovers(list, current.assetKey)
    } else {
      current.isCover = '0'
    }
    return { data: current }
  },

  topicassetdel: (body) => {
    const list = linksOf(body.topicID)
    const index = list.findIndex((item) => item.recID === body.recID || item.assetKey === body.assetKey)
    if (index < 0) return { __err: { code: 'BI', content: '附图记录标识无效' } }
    const [removed] = list.splice(index, 1)
    return { data: { success: '1', recID: removed.recID } }
  }
}

export const mockAssets = state.assets
/**
 * ★ Step 14 追加（越界授权小改，产出说明已登记）：导出**实时**的主题-附图关联表。
 * 原因：真实后端 `renderService._fetchAssets` 读 `ch_topic_asset`（在库数据）；而
 * `mock/compliance.js` 原先读静态种子 `data/asset.js::TOPIC_ASSETS`，
 * 导致「页面已解绑全部附图（附图 0）但合规仍按种子图报规格/超长图阻断」的 **Mock 假象**，
 * 使 P-09/P-10 的「解绑附图后重校验」链路在 Mock 下不可复核。
 */
export const mockTopicLinks = state.links
export default handlers
