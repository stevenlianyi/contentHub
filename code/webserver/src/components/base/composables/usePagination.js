/* ============================================================================
 * usePagination · 组合式函数（Step 4）
 * ----------------------------------------------------------------------------
 * 职责：把「服务端分页」的取数样板（beginNum/endNum + total + indexKey）收敛到一处，
 *       供所有列表页复用；**不在前端切片数据**（§2.11 长列表用服务端分页）。
 *
 * 契约（§2.4.4 查询类报文）：
 *   fetcher({ beginNum, endNum, indexKey?, ...extra }) → { data: [], total, indexKey }
 *   · 首屏（page===1 且无 indexKey）只传 beginNum/endNum；
 *   · 后续带 indexKey（后端 queryBufferCommon 的缓冲续取口径；generalnext 场景）。
 *   · 失败时把 `MSG.content` 落到 `error`（页面渲染 ErrorState），并 console.error（不吞异常）。
 *
 * 依赖变化自动重取：page / size 变化即重新 load（immediate=true 时挂载即取首屏）。
 * ========================================================================== */
import { computed, ref, watch } from 'vue'

export function usePagination(fetcher, { pageSize = 20, immediate = true } = {}) {
  const page = ref(1)
  const size = ref(Number(pageSize) || 20)
  const total = ref(0)
  const rows = ref([])
  const loading = ref(false)
  const error = ref('')
  const indexKey = ref('')

  /** 并发护栏：只接受最后一次发起的响应，避免快速翻页时旧响应覆盖新数据 */
  let requestId = 0

  async function load(extra = {}) {
    const current = ++requestId
    loading.value = true
    error.value = ''

    try {
      const isFirstBatch = (page.value - 1) * size.value === 0 && !indexKey.value
      const params = isFirstBatch
        ? { beginNum: 0, endNum: size.value }
        : { beginNum: (page.value - 1) * size.value, endNum: page.value * size.value, indexKey: indexKey.value }

      const res = await fetcher({ ...params, ...extra })
      if (current !== requestId) return

      rows.value = Array.isArray(res?.data) ? res.data : []
      total.value = Number(res?.total || 0)
      indexKey.value = res?.indexKey || ''
    } catch (e) {
      if (current !== requestId) return
      error.value = e?.MSG?.content || '加载失败'
      console.error('[usePagination]', e)
    } finally {
      if (current === requestId) loading.value = false
    }
  }

  const pageCount = computed(() => Math.max(1, Math.ceil(total.value / size.value)))
  const hasPrev = computed(() => page.value > 1)
  const hasNext = computed(() => page.value < pageCount.value)

  /** 翻页：改变页码并触发重取 */
  function goPage(nextPage) {
    const target = Number(nextPage) || 1
    if (target === page.value) return load()
    page.value = target
  }

  /** 切换每页条数：重置 indexKey 与页码后重取 */
  function changeSize(nextSize) {
    const target = Number(nextSize) || size.value
    indexKey.value = ''
    size.value = target
    page.value = 1
  }

  /** 强制刷新（绕过后端查询缓冲由调用方在 extra 里传 forceFlashFlag: '1'） */
  function refresh(extra = {}) {
    return load(extra)
  }

  /** 回到首屏（筛选条件变化时调用） */
  function reset(extra = {}) {
    indexKey.value = ''
    page.value = 1
    return load(extra)
  }

  // page / size 变化即重取；immediate 让首屏在 setup 阶段直接发起
  watch([page, size], () => load(), { immediate })

  return { page, size, total, rows, loading, error, indexKey, pageCount, hasPrev, hasNext, load, goPage, changeSize, refresh, reset }
}

export default usePagination
