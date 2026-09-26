<!-- ============================================================================
 * AppPagination · L1 基础组件（Step 4 扩展既有件）
 * ----------------------------------------------------------------------------
 * ★ 既有 props / emits 名保持不变：total / pageSize / currentPage / pageSizeOptions /
 *   maxVisiblePages / disabled；emits：page-change / size-change。
 * 本步追加：`pageSizes`（缺省 [10, 20, 50]，显式传入时优先于 pageSizeOptions）、
 *           「显示 x-y 条，共 N 条」文案与每页条数选择。
 * ★ 服务端分页语义：本组件**不做任何前端切片**，只 emit `page-change({ page, size })`；
 *   beginNum/endNum 由调用方（或 usePagination）换算，并在拿到 total 后回填本组件。
 * 兼容说明：尺寸变更时先 emit `size-change`(number，兼容旧调用方)，再 emit
 *           `page-change({ page: 1, size })`，保证两套订阅方式都能拿到最新状态。
 * ========================================================================== -->
<template>
  <div class="flex flex-wrap items-center justify-between gap-md">
    <p class="text-body-s text-ch-text-secondary">
      显示 {{ rangeStart }}-{{ rangeEnd }} 条，共 {{ totalNum }} 条
    </p>

    <div class="flex flex-wrap items-center gap-md">
      <label class="flex items-center gap-sm text-body-s text-ch-text-secondary">
        <span>每页</span>
        <select
          class="h-8 rounded-md border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
          aria-label="每页条数"
          :value="sizeNum"
          :disabled="disabled"
          @change="handleSizeChange"
        >
          <option v-for="option in sizeOptions" :key="option" :value="option">{{ option }}</option>
        </select>
        <span>条</span>
      </label>

      <nav class="flex items-center gap-sm" aria-label="分页导航">
        <button
          type="button"
          class="flex h-8 w-8 items-center justify-center rounded-lg border border-ch-border-light text-ch-text-secondary transition-colors duration-150 ease-out hover:bg-ch-hover disabled:cursor-not-allowed disabled:text-ch-text-disabled"
          :disabled="disabled || pageNum <= 1"
          aria-label="上一页"
          @click="goToPage(pageNum - 1)"
        >
          <i class="fa fa-angle-left" aria-hidden="true"></i>
        </button>

        <button
          v-for="page in visiblePages"
          :key="page"
          type="button"
          class="h-8 min-w-[32px] rounded-lg px-sm text-body-s transition-colors duration-150 ease-out disabled:cursor-not-allowed"
          :class="pageButtonClass(page)"
          :aria-current="page === pageNum ? 'page' : undefined"
          :aria-label="`第 ${page} 页`"
          :disabled="disabled"
          @click="goToPage(page)"
        >
          {{ page }}
        </button>

        <button
          type="button"
          class="flex h-8 w-8 items-center justify-center rounded-lg border border-ch-border-light text-ch-text-secondary transition-colors duration-150 ease-out hover:bg-ch-hover disabled:cursor-not-allowed disabled:text-ch-text-disabled"
          :disabled="disabled || pageNum >= totalPages"
          aria-label="下一页"
          @click="goToPage(pageNum + 1)"
        >
          <i class="fa fa-angle-right" aria-hidden="true"></i>
        </button>
      </nav>
    </div>
  </div>
</template>

<script setup>
import { computed, watch } from 'vue'

const props = defineProps({
  // 后端返回的总条数（total 为数字；beginNum/endNum 才是字符串，注意转换）
  total: { type: [Number, String], default: 0 },
  pageSize: { type: [Number, String], default: 20 },
  currentPage: { type: [Number, String], default: 1 },
  /** 计划 Step 4 规格：每页条数档位 [10, 20, 50]；显式传入时优先 */
  pageSizes: { type: Array, default: null },
  /** 既有 prop（兼容保留）：未传 pageSizes 时生效 */
  pageSizeOptions: { type: Array, default: () => [10, 20, 50] },
  maxVisiblePages: { type: Number, default: 5 },
  // loading 时禁止翻页，避免并发请求
  disabled: { type: Boolean, default: false }
})

// 事件：page-change({ page, size })（服务端分页主契约）；size-change(每页条数)（兼容）
// 服务端分页参数由调用方换算：beginNum = (page - 1) * pageSize，endNum = page * pageSize
const emit = defineEmits(['page-change', 'size-change'])

const totalNum = computed(() => Number(props.total) || 0)
const sizeNum = computed(() => Number(props.pageSize) || 20)
const pageNum = computed(() => Number(props.currentPage) || 1)
const sizeOptions = computed(() =>
  Array.isArray(props.pageSizes) && props.pageSizes.length ? props.pageSizes : props.pageSizeOptions
)

const totalPages = computed(() => Math.max(1, Math.ceil(totalNum.value / sizeNum.value)))

const rangeStart = computed(() => (totalNum.value === 0 ? 0 : (pageNum.value - 1) * sizeNum.value + 1))
const rangeEnd = computed(() => Math.min(pageNum.value * sizeNum.value, totalNum.value))

const visiblePages = computed(() => {
  const pages = []
  let startPage = Math.max(1, pageNum.value - Math.floor(props.maxVisiblePages / 2))
  const endPage = Math.min(totalPages.value, startPage + props.maxVisiblePages - 1)
  if (endPage - startPage + 1 < props.maxVisiblePages) {
    startPage = Math.max(1, endPage - props.maxVisiblePages + 1)
  }
  for (let i = startPage; i <= endPage; i += 1) {
    pages.push(i)
  }
  return pages
})

const pageButtonClass = (page) => {
  if (page === pageNum.value) {
    return 'bg-ch-primary text-ch-text-inverse'
  }
  return 'text-ch-text-secondary hover:bg-ch-hover'
}

function goToPage(page) {
  if (props.disabled) return
  if (page < 1 || page > totalPages.value || page === pageNum.value) return
  emit('page-change', { page, size: sizeNum.value })
}

function handleSizeChange(event) {
  const nextSize = Number(event.target.value)
  if (!nextSize || nextSize === sizeNum.value) return
  emit('size-change', nextSize)
  emit('page-change', { page: 1, size: nextSize })
}

// 数据量变化导致当前页越界时，回退到最后一页
watch(totalPages, (nextTotal) => {
  if (pageNum.value > nextTotal && nextTotal > 0) {
    emit('page-change', { page: nextTotal, size: sizeNum.value })
  }
})
</script>
