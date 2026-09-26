/* ============================================================================
 * Mock 数据 · 主题（≥128 条，含五种状态样例；纯生成器，确定性）
 * ----------------------------------------------------------------------------
 * 样例沿用计划 §2.8 指定的三条真实感标题：敦煌壁画的色谱研究 / 宋代点茶考据与器皿形制 /
 * 明代家具榫卯结构图解。禁止「示例数据1」这类占位内容。
 * ========================================================================== */
import { wordCount } from '@/utils/common'
import { hoursBefore, pad, pick, ymdhms } from './util'

/** 32 条基础选题（真实感中文），×4 轮次 → 128 条 */
const TITLE_SEEDS = [
  '敦煌壁画的色谱研究', '宋代点茶考据与器皿形制', '明代家具榫卯结构图解', '唐代金银器纹样的外来影响',
  '《营造法式》中的材份制度拆解', '宋代山水画的皴法谱系', '汉代漆器纹饰的地域差异', '魏晋墓葬壁画的图像秩序',
  '景德镇青白瓷的釉色成因', '清代外销瓷纹样的中西混融', '徽州民居天井的采光策略', '闽南红砖厝的砌筑工艺',
  '云南扎染的靛蓝发酵工艺', '苏绣针法的分丝与劈线', '龙泉青瓷的冰裂纹控制', '宣纸捞制的帘纹与厚薄',
  '古琴形制的断代依据', '宋代金石学的著录体例', '明代刻本书口的版本学价值', '清宫造办处的活计档研究',
  '佛山木版年画的套色顺序', '杨柳青年画的勾填技法', '秦淮灯彩的骨架扎法', '苗族银饰的錾刻纹样',
  '侗族鼓楼的结构受力分析', '晋东南古戏台的声学特征', '江南园林的框景与借景', '北京四合院的排水体系',
  '茶马古道上的饮器流变', '海上丝绸之路的沉船瓷器', '古法造纸的纤维显微鉴定', '传统制墨的油烟与松烟'
]

/** 轮次后缀：第 1 轮为原题（用于验收例句），后续轮次加限定词，保证 128 条标题互不相同且 ≤50 字 */
const ROUND_SUFFIX = ['', '·续编', '·补遗', '·图谱']

const OWNERS = ['陈立恒', '周敏', '李思远', '王雨珊', '赵一鸣', '沈知微', '顾南屏']
const PLATFORMS = ['wechat_mp', 'xiaohongshu', 'generic']

/* ---- Step 7 追加：P-03 Tab1 的全字段样例（真实感中文，禁止占位文案） ----------------
 * 字段名严格对齐 database/ch_topic.txt（description / author / period / tagList …），
 * ★ 本文件原先的 `detail` 为 mock 自造名，已按权威列名改回 `description`。
 * ---------------------------------------------------------------------------------- */
const AUTHORS = ['陈立恒', '周敏', '李思远', '王雨珊', '赵一鸣', '沈知微', '顾南屏']
const LOCATIONS = ['甘肃敦煌', '福建泉州', '江西景德镇', '江苏苏州', '山西晋城', '北京', '浙江龙泉', '安徽徽州']
const SOURCES = [
  '馆藏实物测绘与考古发掘简报',
  '地方志与族谱记载',
  '修复档案与老匠人口述',
  '近二十年专题论文与图录',
  '博物馆藏品登记册'
]
const PERIODS = ['汉', '魏晋', '唐', '宋', '元', '明', '清', '近现代']
const TAG_POOL = [
  '壁画', '色谱', '材料分析', '器形', '工艺复原', '断代', '纹样', '测绘',
  '釉色', '显微观察', '地方志', '匠作组织', '贸易史', '建筑构件'
]
const CATEGORY_CODES = ['MURAL', 'CERAMIC', 'TEXTILE', 'ARCHITECTURE', 'PAINTING', 'CRAFT']
const LAYOUTS = {
  wechat_mp: ['stack_v1', 'carousel_v1', 'longimage_v1'],
  xiaohongshu: ['stack_v1', 'longimage_v1', 'swipe_v1'],
  generic: ['stack_v1', 'carousel_v1', 'longimage_v1']
}
/** 状态轮转：保证五种状态都有样例（下标 0 已投递 / 1 草稿 / 2 已渲染 / 3 渲染中 / 4 已归档） */
const STATUS_CYCLE = ['PUBLISHED', 'DRAFT', 'RENDERED', 'RENDERING', 'ARCHIVED']
const PUBLISH_BY_STATUS = {
  DRAFT: 'UNPUBLISHED',
  RENDERING: 'UNPUBLISHED',
  RENDERED: 'DRAFTED',
  PUBLISHED: 'PUBLISHED',
  ARCHIVED: 'PUBLISHED'
}

const SUMMARY_TEMPLATES = [
  '围绕{title}的实物与文献互证，梳理可复核的年代序列与工艺参数。',
  '从材料、工艺、使用场景三条线索切入，整理{title}的比对样本与结论。',
  '汇总近年考古简报与馆藏记录，给出{title}的断代建议与争议点清单。',
  '以可复现的实测数据为基础，讨论{title}在不同地域的形制差异。'
]

const DETAIL_PARAGRAPHS = [
  '本文以{title}为对象，先交代选题缘起与材料范围：一手材料来自馆藏实物测绘、考古发掘简报与历年修复档案，二手材料为近二十年的专题论文与图录。所有尺寸、色值、纹理参数均按同一套记录表登记，便于横向比对。',
  '研究方法上分三步推进。第一步做形制编年，按器形比例、部件连接方式与装饰母题建立类型序列；第二步做工艺复原，借助显微观察、断面分析与可控条件下的复烧实验，验证工序假设；第三步做功能推定，结合使用痕迹与同出器物组合，判断其在具体场景中的用途。',
  '实测部分给出关键参数区间：主要构件的长宽比集中在稳定区间，表面处理痕迹呈规律性分布，说明存在成熟的分工与量具。少数偏离样本集中出现在晚期地层，提示技术传播或匠作组织发生了变化。',
  '争议点集中在两处：一是年代上限的判定依据，二是外来因素的影响权重。本文倾向于以本地技术传统为主线，将外来因素视为选择性吸收，并给出可供检验的量化指标，供后续研究补充或修正。需要说明的是，本文认为以同批样本做交叉校正，是目前最有效的判定路径，该结论已在三处独立样本上复现。',
  '结论与展望：{title}的形制与工艺具备可复现的技术链条，建议后续补做材料成分分析与长期暴露实验，并建立开放的结构化数据集，以便与同类研究交叉验证。文中标注的待确认项均已列明取证方式。'
]

const EMPTY = ''

function buildSummary(title, index) {
  return pick(SUMMARY_TEMPLATES, index).replace(/\{title\}/g, title)
}

/** 详述正文（2000–5000 字区间内；按段落循环堆叠，确定性） */
export function buildDetail(topic) {
  const parts = []
  let round = 1
  // 目标 ≈2600 字（码点数），落在 2000–5000 区间内
  while (parts.join('').length < 2600 && round <= 6) {
    DETAIL_PARAGRAPHS.forEach((paragraph, index) => {
      const suffix = round === 1 ? '' : `（第 ${round} 轮校注）`
      parts.push(`${index + 1}. ${paragraph.replace(/\{title\}/g, topic.title)}${suffix}`)
    })
    round += 1
  }
  return parts.join('\n\n')
}

function buildTopics(count = 128) {
  const list = []
  for (let i = 0; i < count; i += 1) {
    const seed = TITLE_SEEDS[i % TITLE_SEEDS.length]
    const round = Math.floor(i / TITLE_SEEDS.length)
    const title = `${seed}${ROUND_SUFFIX[round] || ''}`
    const status = pick(STATUS_CYCLE, i)
    const platform = pick(PLATFORMS, i + Math.floor(i / 7))
    const createdAt = hoursBefore(1200 - i * 9)
    const updatedAt = hoursBefore(Math.max(1, 480 - i * 3))
    list.push({
      recID: `TP${pad(i + 1, 6)}`,
      topicCode: `TOPIC-2026-${pad(i + 1, 4)}`,
      title,
      summary: buildSummary(title, i),
      description: EMPTY, // 列表不返回详述，详情按需用 buildDetail() 生成
      descriptionFileID: '',
      coverFileID: '',
      author: pick(AUTHORS, i + round),
      location: pick(LOCATIONS, i + Math.floor(i / 5)),
      source: pick(SOURCES, i + Math.floor(i / 3)),
      period: pick(PERIODS, i + round),
      tagList: [pick(TAG_POOL, i), pick(TAG_POOL, i + 3), pick(TAG_POOL, i + 7)].join(','),
      categoryCode: pick(CATEGORY_CODES, i + round),
      // AI 标识：每 4 条留 1 条「含 AI 参与创作」样例，覆盖 aiFlag 的两种取值
      aiFlag: i % 4 === 0 ? '1' : '0',
      status,
      publishStatus: PUBLISH_BY_STATUS[status],
      platform,
      // ★ Step 7：i % 8 === 3 的主题刻意留空 layoutCode —— 模拟「空草稿 / 未选版式」，
      //   用于让「完成度 4/5」「提交渲染因版式未选而禁用」两条验收有**可复现的数据**。
      layoutCode: i % 8 === 3 ? '' : pick(LAYOUTS[platform], i + round),
      coverUrl: `https://placehold.co/320x200/1F2937/F3F4F6?text=TOPIC+${pad(i + 1, 3)}`,
      assetCount: 3 + ((i * 5) % 12),
      // 字数口径（★ 裁定 a3）：与后端 processor/topicService.countWords 一致，
      // 由 utils/common.wordCount(buildDetail(topic)) 计算，落在 §2.7 的 2000–5000 区间（构造后回填）
      wordCount: 0,
      artifactCount: status === 'DRAFT' ? 0 : (i % 9),
      versionNo: 1 + (i % 4),
      owner: pick(OWNERS, i),
      remark: i % 11 === 0 ? '待补充出土层位信息' : '',
      // 字段名对齐 ch_topic.txt 权威列名（裁定 a1）：regYMDHMS = 创建、modifyYMDHMS = 修改
      regYMDHMS: ymdhms(createdAt),
      modifyYMDHMS: ymdhms(updatedAt)
    })
  }
  // 详述正文与字数的口径统一：列表不返回详述，但字数必须是详述真实口径（不是编造值）
  list.forEach((item) => {
    item.wordCount = wordCount(buildDetail(item))
  })
  return list
}

/** 主题种子数据（>=128 条） */
export const TOPICS = buildTopics(128)

/** 版本快照（P-03 版本抽屉：按 topicID 取列表） */
export const TOPIC_VERSIONS = TOPICS.slice(0, 24).flatMap((topic, topicIndex) => {
  const count = 1 + (topicIndex % 3)
  return Array.from({ length: count }, (unused, versionIndex) => ({
    recID: `TV${pad(topicIndex * 3 + versionIndex + 1, 6)}`,
    // topicID 语义对齐（裁定 a4）：= ch_topic.recID；topicCode 保留作冗余展示字段
    topicID: topic.recID,
    topicCode: topic.topicCode,
    versionNo: versionIndex + 1,
    versionName: `第 ${versionIndex + 1} 版`,
    changeNote: versionIndex === 0 ? '创建主题' : pick(['补充考古简报引用', '调整详述结构', '修正图注与来源', '更新平台规格'], versionIndex),
    operator: topic.owner,
    regYMDHMS: topic.modifyYMDHMS
  }))
})

/** 敏感词样例（publishcheck 用；命中即报 ERROR / WARN） */
export const SENSITIVE_WORDS = [
  { word: '最有效', level: 'ERROR', suggestion: '绝对化用语，建议改为「较为有效」' },
  { word: '国家级', level: 'WARN', suggestion: '资质类表述需提供证明或删除' },
  { word: '独家', level: 'WARN', suggestion: '独占性表述易触发平台限流' }
]

export default TOPICS
