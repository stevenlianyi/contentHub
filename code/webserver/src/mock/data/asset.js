/* ============================================================================
 * Mock 数据 · 素材与主题-素材关联（素材 ≥60 条，含 1 条 dedupHit 样例）
 * ----------------------------------------------------------------------------
 * 计划 §2.8：涉及文件 URL 的字段用 `https://placehold.co/` 占位图；
 * 缩略图提供 320 / 640 / 1280 三档，用于验证素材网格的 `srcset`。
 * `assetadd` 的 contentHash 必须为 64 位小写 sha256 —— 用 hexHash() 生成，避免超长字面量。
 * ========================================================================== */
import { hoursBefore, hexHash, pad, pick, ymdhms } from './util'

const CAPTIONS = [
  '壁画色谱取样现场（自然光）', '点茶击拂后的汤花形态', '榫卯节点装配示意', '金银器锤揲纹样特写',
  '《营造法式》材份尺度标注', '山水画皴法局部对照', '漆器纹饰线描摹本', '墓葬壁画图像层次说明',
  '青白瓷釉面显微照片', '外销瓷纹样拼版过程', '天井采光模拟结果', '红砖厝砌筑灰缝细节',
  '扎染靛蓝发酵缸状态', '苏绣分丝显微图', '冰裂纹开片对照表', '宣纸帘纹透光观察',
  '古琴断纹拓片', '金石著录书影', '刻本版心与书口', '活计档摘录页',
  '年画套色分版样张', '勾填技法步骤图', '灯彩骨架扎制', '银饰錾刻纹样拓印',
  '鼓楼梁架测绘图', '古戏台藻井声反射', '园林框景实拍', '合院排水沟剖面',
  '饮器形制演变序列', '沉船瓷器清理记录', '纤维显微鉴定图', '墨锭断面与研磨面'
]

const USAGE_CYCLE = ['cover', 'body', 'body', 'inline']
const PROCESS_CYCLE = ['PROCESSED', 'PROCESSED', 'RAW', 'PROCESSED', 'FAILED']

/**
 * ★ Step 8 补齐：与 `database/ch_asset.txt` 权威列对齐的字段（此前只有 UI 展示字段）。
 * P-04 的「类型筛选（fileExt）」「文件后端（fileSystem）」「原始文件名/对象键（keyword 命中面）」
 * 都依赖这些列；缺列会让真实后端能筛、Mock 不能筛，产生「Mock 通过、真实静默不筛」的假象。
 */
const EXT_CYCLE = ['png', 'jpg', 'jpeg', 'webp']
const MIME_BY_EXT = { png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', webp: 'image/webp' }
const FILE_SYSTEM_CYCLE = ['ALIOSS', 'TENCENT', 'SELFFILE']

const RATIOS = [
  { width: 1080, height: 1440 }, // 微信正文图 / 小红书封面正文图（3:4）
  { width: 900, height: 500 }, // 微信封面
  { width: 750, height: 1000 }, // 长图切片前的原图
  { width: 1200, height: 1600 } // 高清竖图
]

const placeholder = (width, height, seed) => `https://placehold.co/${width}x${height}/1F2937/F3F4F6?text=IMG+${seed}`

function buildAssets(count = 66) {
  const list = []
  for (let i = 0; i < count; i += 1) {
    const ratio = pick(RATIOS, i)
    const sizeBytes = 420 * 1024 + ((i * 7919) % 2600) * 1024
    const createdAt = hoursBefore(900 - i * 12)
    // 第 8 条沿用第 4 条的 contentHash → 命中即复用（dedupHit=1），用于验证「命中即复用」
    const hashSeed = i === 7 ? 4 : i + 1
    const caption = pick(CAPTIONS, i)
    const fileExt = pick(EXT_CYCLE, i)
    const fileSystem = pick(FILE_SYSTEM_CYCLE, i)
    // ★ origName / objectName 是 `keyword` 的真实命中面（mysqlCommon.query_ch_asset 的 likeOrList），
    //   故用真实感中文文件名，保证「按文件名搜索」在 Mock 下可验。
    const origName = `${caption}.${fileExt}`
    list.push({
      recID: `AS${pad(i + 1, 6)}`,
      fileID: `FILE${pad(i + 1, 5)}`,
      thumbnailID: `THUMB${pad(i + 1, 5)}`,
      fileName: origName,
      origName,
      objectName: `ASSET_20260920_${pad(i + 1, 5)}.${fileExt}`,
      fileExt,
      mimeType: MIME_BY_EXT[fileExt],
      fileSystem,
      storageBucket: fileSystem === 'SELFFILE' ? 'local' : `ch-asset-${fileSystem === 'ALIOSS' ? 'oss' : 'cos'}-01`,
      origSizeBytes: sizeBytes,
      label: '',
      memo: '',
      ownerID: pick(['chenlh', 'zhoumin', 'lisiyuan', 'wangys'], i),
      caption,
      usageType: pick(USAGE_CYCLE, i),
      width: ratio.width,
      height: ratio.height,
      sizeBytes,
      contentHash: hexHash(hashSeed),
      processStatus: pick(PROCESS_CYCLE, i),
      dedupHit: i === 7 ? '1' : '0',
      imageUrl: placeholder(ratio.width, ratio.height, pad(i + 1, 3)),
      thumbnailUrl: placeholder(320, Math.round((320 * ratio.height) / ratio.width), pad(i + 1, 3)),
      thumbnails: {
        320: placeholder(320, Math.round((320 * ratio.height) / ratio.width), pad(i + 1, 3)),
        640: placeholder(640, Math.round((640 * ratio.height) / ratio.width), pad(i + 1, 3)),
        1280: placeholder(1280, Math.round((1280 * ratio.height) / ratio.width), pad(i + 1, 3))
      },
      source: i % 5 === 0 ? '本地上传' : '图库同步',
      uploadedBy: pick(['陈立恒', '周敏', '李思远', '王雨珊'], i),
      // 字段名对齐 ch_asset.txt 权威列名（裁定 a1）
      regYMDHMS: ymdhms(createdAt),
      modifyYMDHMS: ymdhms(createdAt)
    })
  }
  return list
}

/** 素材种子数据（>=60 条，其中 recID AS000008 为 dedupHit 样例） */
export const ASSETS = buildAssets(66)

/**
 * 主题-素材关联（附图）。
 * 幂等键 `assetKey = {topicID}:{fileID}`；`sortOrder` 越小越靠前；封面唯一。
 * ★ topicID 语义对齐（裁定 a4）：= ch_topic.recID（对齐 ch_topic_asset.topicID），
 *   `topicCode` 保留作冗余展示字段；`src/mock/asset.js` 的处理器同时容忍两种入参。
 * 关联规模不变：主题 1 关联 5 张（含封面）、其余主题 2–4 张，比例混合用于验证拦截。
 */
export const TOPIC_ASSETS = (() => {
  const map = {}
  const topicCodes = Array.from({ length: 32 }, (unused, i) => `TOPIC-2026-${pad(i + 1, 4)}`)
  topicCodes.forEach((topicCode, topicIndex) => {
    const topicID = `TP${pad(topicIndex + 1, 6)}` // 与 data/topic.js 的 TOPICS[i].recID 一致
    const count = 2 + (topicIndex % 3) + (topicIndex === 0 ? 2 : 0)
    const items = []
    for (let j = 0; j < count; j += 1) {
      const asset = pick(ASSETS, topicIndex * 3 + j)
      items.push({
        recID: `TA${pad(topicIndex * 6 + j + 1, 6)}`,
        topicID,
        topicCode,
        assetKey: `${topicID}:${asset.fileID}`,
        fileID: asset.fileID,
        assetName: asset.caption,
        // ★ Step 7 对齐：ch_topic_asset 有 caption 列（后端 validateTopicAssetFields 单列校验 ≤512），
        //   附图卡片「图注」直接读写该列，不再只有素材表的 assetName。
        caption: asset.caption,
        usageType: j === 0 ? 'cover' : pick(['body', 'body', 'inline'], j),
        sortOrder: j + 1,
        isCover: j === 0 ? '1' : '0',
        width: asset.width,
        height: asset.height,
        imageUrl: asset.imageUrl,
        thumbnailUrl: asset.thumbnailUrl,
        regYMDHMS: asset.regYMDHMS
      })
    }
    map[topicID] = items
  })
  return map
})()

export default ASSETS
