/* ============================================================================
 * useAssetReferences · P-04 引用关系反查（Step 8）
 * ----------------------------------------------------------------------------
 * ★ 越界授权文件（本步交付说明已登记）：计划 Step 8 的产出清单为 4 个文件，
 *   本文件按「Assets.vue 只做视图与编排」的硬约束把反查逻辑独立出来。
 *
 * 真实链路（附录 B R-20：引用关系为 N+1 反查）：
 *   1) `topicassetqry({ fileID })` → 取引用该素材的**附图记录**（含 topicID / usageType / caption；
 *      ch_topic_asset 无 topicCode / 标题列，故 mock 之外的字段必须二次查询）；
 *   2) 对去重后的 `topicID`（= ch_topic.recID）逐个 `topicqry({ recID, mode: 'short' })` 取标题与
 *      topicCode：**≤10 处并发**（并发上限 6），超出只取前 10 条标题并显示「等 N 处」；
 *   3) 结果按 fileID 缓存，避免翻页 / 重复打开抽屉时重打 N+1 请求。
 *
 * 说明：本组合式函数**只做取数与归并**，不碰 UI；失败一律落到各自的 error 字段（不吞异常）。
 * ========================================================================== */
import { reactive } from 'vue'
import { topicAssetQry } from '@/api/asset'
import { topicQry } from '@/api/topic'

/** 逐条取标题的上限（超出部分只计数不查标题，见 R-20） */
export const REF_TITLE_LIMIT = 10
/** 并发上限：既避免 N+1 打满连接，也避免串行等待过久 */
const CONCURRENCY = 6

/** 并发映射：保持入参顺序，单项失败不中断其余 */
async function mapLimit(list, limit, worker) {
  const result = new Array(list.length)
  let cursor = 0
  const runners = Array.from({ length: Math.min(limit, list.length) }, async () => {
    while (cursor < list.length) {
      const index = cursor
      cursor += 1
      result[index] = await worker(list[index], index)
    }
  })
  await Promise.all(runners)
  return result
}

/** 按 topicID 并发取标题与 topicCode（单条失败降级为空标题，不中断） */
async function fetchTopicTitles(topicIds) {
  const pairs = await mapLimit(topicIds, CONCURRENCY, async (topicID) => {
    try {
      const res = await topicQry({ recID: topicID, mode: 'short' })
      const record = Array.isArray(res?.data) ? res.data[0] : null
      return { topicID, topicCode: String(record?.topicCode || ''), title: String(record?.title || '') }
    } catch (error) {
      console.warn('[useAssetReferences] 取主题标题失败', topicID, error)
      return { topicID, topicCode: '', title: '' }
    }
  })
  return Object.fromEntries(pairs.map((item) => [item.topicID, item]))
}

export function useAssetReferences() {
  /** fileID → 引用数（undefined = 尚未查询） */
  const counts = reactive({})
  /** fileID → 'loading' | 'ready' | 'error' */
  const countState = reactive({})
  /** fileID → { loading, error, total, extraCount, items[] } */
  const details = reactive({})

  const countOf = (fileID) => counts[String(fileID || '')]
  const stateOf = (fileID) => countState[String(fileID || '')] || 'idle'
  /** 引用明细快照（响应式）：未查询时返回空结构，供抽屉 / 删除弹窗直接绑定 */
  const detailOf = (fileID) =>
    details[String(fileID || '')] || { loading: false, error: '', total: 0, extraCount: 0, items: [] }

  /** 批量查引用数（仅 topicassetqry，不查标题）——用于网格/列表的「引用 N 处」 */
  async function loadCounts(fileIDs, { force = false } = {}) {
    const targets = [...new Set((fileIDs || []).map((item) => String(item || '')).filter(Boolean))]
      .filter((fileID) => force || stateOf(fileID) !== 'ready')
    if (!targets.length) return
    targets.forEach((fileID) => {
      countState[fileID] = 'loading'
    })
    await mapLimit(targets, CONCURRENCY, async (fileID) => {
      try {
        const res = await topicAssetQry({ fileID })
        counts[fileID] = Array.isArray(res?.data) ? res.data.length : 0
        countState[fileID] = 'ready'
      } catch (error) {
        console.warn('[useAssetReferences] 引用数查询失败', fileID, error)
        countState[fileID] = 'error'
      }
    })
  }

  /** 查引用明细（引用主题列表 + 标题）；结果缓存，`force` 可强制重查 */
  async function fetchDetail(fileID, { force = false } = {}) {
    const key = String(fileID || '')
    if (!key) return null
    if (!force && details[key]?.items && !details[key]?.error) return details[key]

    details[key] = { ...(details[key] || {}), loading: true, error: '' }
    try {
      const res = await topicAssetQry({ fileID: key })
      const links = Array.isArray(res?.data) ? res.data : []
      const topicIds = [...new Set(links.map((link) => String(link.topicID || '')).filter(Boolean))]
      const limited = topicIds.slice(0, REF_TITLE_LIMIT)
      const titleMap = limited.length ? await fetchTopicTitles(limited) : {}

      const items = links
        .map((link) => {
          const topicID = String(link.topicID || '')
          const meta = titleMap[topicID] || {}
          return {
            key: String(link.recID || link.assetKey || topicID),
            topicID,
            topicCode: String(link.topicCode || meta.topicCode || ''),
            title: String(link.title || meta.title || ''),
            usageType: String(link.usageType || ''),
            caption: String(link.caption || link.assetName || '')
          }
        })
        .sort((a, b) => a.title.localeCompare(b.title, 'zh-Hans-CN'))

      const extraCount = Math.max(0, topicIds.length - limited.length)
      details[key] = { loading: false, error: '', total: links.length, extraCount, items }
      counts[key] = links.length
      countState[key] = 'ready'
      return details[key]
    } catch (error) {
      details[key] = { loading: false, error: error?.MSG?.content || '引用关系查询失败', total: 0, extraCount: 0, items: [] }
      countState[key] = 'error'
      return details[key]
    }
  }

  return { counts, countState, details, countOf, stateOf, detailOf, loadCounts, fetchDetail }
}

export default useAssetReferences
