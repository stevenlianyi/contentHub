/* ============================================================================
 * useAssetList · P-04 列表 / 筛选 / 分页 / 仅当前页派生（Step 8）
 * ----------------------------------------------------------------------------
 * ★ 越界授权文件（本步交付说明已登记）：裁定 H 要求 `Assets.vue` 只做视图与编排且 ≤600 行
 *   （§2.1 硬约束；本文件由该拆分产生），
 *   故把「取数 + 筛选 + URL query + 仅当前页派生 + 引用数」收敛到本组合式函数。
 *
 * 取数口径：`assetqry` + **默认 mode:'full'**（★ 禁止 short：short 列不含 origName / fileSystem /
 *   regYMDHMS，列表会缺字段）+ 服务端分页（beginNum/endNum + total）。
 *   ★ 真实 `assetService.queryAsset` 未做分页切片（`beginNum/endNum` 被忽略，仅 `limitNum` 生效）——
 *   该差异登记为待确认项；本地验收以 Mock（按分页语义返回）为准。
 * 筛选能力对照（附录 B R-17）：
 *   · 搜索 → `keyword`（服务端按 `origName` / `objectName` 模糊）；
 *   · 类型 → `fileExt`（服务端支持）；
 *   · 规格 / 引用状态 → **后端无参数** → 仅当前页客户端筛选（控件已显式标注，不静默忽略）。
 * URL query：kw / ext / spec / ref / view / page 全部写入，刷新与前进后退均保持。
 * ========================================================================== */
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePagination } from '@/components/base/composables/usePagination'
import { useAssetReferences } from '@/views/assets/useAssetReferences'
import { assetQry } from '@/api/asset'

const MAX_PIC = 1920
const SPEC_VALUES = ['', 'oversize', '3:4', '1:1', '4:3']
const REF_VALUES = ['', 'none', 'some']
const VIEW_VALUES = ['grid', 'list']

export function useAssetList() {
  const route = useRoute()
  const router = useRouter()
  // ★ 单一实例：列表的「引用 N 处」与抽屉/删除弹窗的引用明细共用同一份缓存（避免重复 N+1）
  const { loadCounts, countOf, stateOf, detailOf, fetchDetail } = useAssetReferences()

  /* ------------------------------ 1. 筛选与 URL ------------------------------ */
  function readQuery(query) {
    const pick = (value, allowed, fallback) => (allowed.includes(String(value || '')) ? String(value || '') : fallback)
    return {
      keyword: String(query.kw || ''),
      fileExt: String(query.ext || ''),
      spec: pick(query.spec, SPEC_VALUES, ''),
      ref: pick(query.ref, REF_VALUES, ''),
      view: pick(query.view, VIEW_VALUES, 'grid') || 'grid'
    }
  }

  const filters = reactive(readQuery(route.query))
  const initialPage = Math.max(1, Number(route.query.page) || 1)
  const pageOnlyFilter = computed(() => Boolean(filters.spec || filters.ref))
  const errorDetail = ref('')

  function syncUrl() {
    const query = {}
    if (filters.keyword) query.kw = filters.keyword
    if (filters.fileExt) query.ext = filters.fileExt
    if (filters.spec) query.spec = filters.spec
    if (filters.ref) query.ref = filters.ref
    if (filters.view !== 'grid') query.view = filters.view
    if (page.value > 1) query.page = String(page.value)
    router.replace({ path: '/assets', query })
  }

  /* ------------------------------- 2. 取数 ------------------------------- */

  /** ★ mode:'full'（禁止 short）；order:'modify' → modifyYMDHMS DESC（最新在前） */
  async function requestAssets({ beginNum, endNum, forceFlashFlag }) {
    const params = { mode: 'full', order: 'modify', beginNum, endNum, forceFlashFlag: forceFlashFlag || '0' }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.fileExt) params.fileExt = filters.fileExt
    try {
      const res = await assetQry(params)
      errorDetail.value = ''
      return res
    } catch (e) {
      errorDetail.value = [e?.errCode ? `errCode: ${e.errCode}` : '', e?.MSG?.content || e?.message || '']
        .filter(Boolean)
        .join('\n')
      throw e
    }
  }

  const { page, size, total, rows, loading, error, goPage, changeSize, refresh } = usePagination(requestAssets, { pageSize: 20 })

  /** 已加载素材的 fileSystem 归纳值（不伪造、不留空，附录 B R-19） */
  const backendSet = ref(new Set())
  const fileBackend = computed(() => (backendSet.value.size ? [...backendSet.value].join(' / ') : '由服务端配置决定'))

  /* ------------------- 3. 仅当前页：规格 / 引用状态 / 引用数 ------------------- */
  function ratioOf(row) {
    const width = Number(row.width) || 0
    const height = Number(row.height) || 0
    if (!width || !height) return ''
    const gcd = (a, b) => (b ? gcd(b, a % b) : a)
    const divisor = gcd(width, height)
    return `${width / divisor}:${height / divisor}`
  }

  const isOversize = (row) => Number(row.width) > MAX_PIC || Number(row.height) > MAX_PIC

  function matchSpec(row, spec) {
    if (!spec) return true
    return spec === 'oversize' ? isOversize(row) : ratioOf(row) === spec
  }

  /** 引用状态只能基于当前页已加载素材判定；未查完前不参与过滤，避免结果抖动 */
  function matchRef(row, refState) {
    if (!refState) return true
    const fileID = String(row.fileID || '')
    if (stateOf(fileID) !== 'ready') return true
    const count = countOf(fileID) || 0
    return refState === 'none' ? count === 0 : count > 0
  }

  const visibleRows = computed(() => rows.value.filter((row) => matchSpec(row, filters.spec) && matchRef(row, filters.ref)))

  const refText = (fileID) => {
    const state = stateOf(String(fileID || ''))
    if (state === 'ready') return `引用 ${countOf(fileID) || 0} 处`
    if (state === 'error') return '引用状态未知'
    return '引用查询中…'
  }
  const refClass = (fileID) => (stateOf(String(fileID || '')) === 'error' ? 'text-ch-warning' : 'text-ch-text-tertiary')

  /** 供子组件（AssetGrid）渲染引用数：fileID → { state, count } */
  const refCounts = computed(() =>
    Object.fromEntries(
      visibleRows.value.map((row) => {
        const fileID = String(row.fileID || '')
        return [fileID, { state: stateOf(fileID), count: countOf(fileID) || 0 }]
      })
    )
  )

  const dimensionOf = (row) => (row.width && row.height ? `${row.width}×${row.height}` : '尺寸未知')
  const altOf = (row) => String(row.label || row.origName || row.fileName || '素材图，图注待补充')

  /* ----------------------------- 4. 去重标记 ----------------------------- */
  const dedupNames = ref([])
  const dedupFileIds = ref([])
  const isDuplicated = (row) => String(row.dedupHit) === '1' || dedupFileIds.value.includes(String(row.fileID || ''))

  /** 上传结果回填：命中既有素材（dedupHit='1'）的文件在网格中原位标记（裁定 F） */
  function markDuplicates(results) {
    const duplicated = (results || []).filter((item) => item.status === 'dup')
    dedupNames.value = duplicated.map((item) => item.name)
    dedupFileIds.value = duplicated.map((item) => String(item.fileID || ''))
  }

  watch(rows, (list) => {
    list.forEach((row) => {
      if (row.fileSystem) backendSet.value.add(String(row.fileSystem))
    })
    loadCounts(list.map((row) => row.fileID))
  })

  /* --------------------------- 5. 筛选动作与同步 --------------------------- */
  function applyFilter(patch) {
    Object.assign(filters, patch)
    // 筛选变化回到第 1 页；已在第 1 页时直接强制重查（避免与 page 侦听器重复打请求）
    const wasFirstPage = page.value === 1
    page.value = 1
    syncUrl()
    if (wasFirstPage) refresh({ forceFlashFlag: '1' })
  }

  const resetFilters = () => applyFilter({ keyword: '', fileExt: '', spec: '', ref: '', view: 'grid' })

  function onPageChange({ page: nextPage, size: nextSize }) {
    if (nextSize && nextSize !== size.value) changeSize(nextSize)
    if (nextPage !== page.value) goPage(nextPage)
    syncUrl()
  }

  watch(page, () => syncUrl())

  /** 路由 query 变化（前进 / 后退 / 手改地址）→ 重新取数 */
  watch(
    () => route.query,
    (query) => {
      const next = readQuery(query)
      if (!Object.keys(next).some((key) => next[key] !== filters[key])) return
      Object.assign(filters, next)
      refresh({ forceFlashFlag: '1' })
    }
  )

  if (initialPage > 1) goPage(initialPage)

  return {
    filters,
    page,
    size,
    total,
    rows,
    loading,
    error,
    errorDetail,
    visibleRows,
    pageOnlyFilter,
    refCounts,
    refText,
    refClass,
    fileBackend,
    dimensionOf,
    altOf,
    isOversize,
    isDuplicated,
    dedupNames,
    dedupFileIds,
    markDuplicates,
    applyFilter,
    resetFilters,
    onPageChange,
    refresh,
    detailOf,
    fetchDetail
  }
}

export default useAssetList
