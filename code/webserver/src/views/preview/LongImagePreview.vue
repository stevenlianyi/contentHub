<!-- ============================================================================
 * LongImagePreview · P-08 小红书「长图」预览（longimage_v1 / 小红书形态的 stack_v1，Step 10）
 * ----------------------------------------------------------------------------
 * 依据（已核源码，服从）：
 *   · processor/platformAdapter/xiaohongshu.py:197-370 → **不处理 `previewKind`**；
 *     `longimage` 与 `stack`（小红书形态为长图）走同一长图管线 `_renderLongImage`：
 *     出参 `outputKind:'png'` + `meta.artifactKind='png_slices'` + `meta.sliceHeight` /
 *     `fullWidth` / `fullHeight` + `products[]`（按 `seqNo` 顺序的切片，每项含 `fileUrl`/`height`）。
 *     ★ 因此本组件只吃 `products[].fileUrl` + `meta`，**不注入 `content`**。
 *   · 数值形态（R-26）：`height` / `fullHeight` / `sliceHeight` 均为**字符串** → 一律 `Number()`。
 *
 * 形态：手机框（750 宽，`PreviewFrame mode="longimage"`）内**纵向滚动**图片切片，
 *       右侧显示**高度刻度**（每个切片边界一条刻度 + 累计高度标签，另标总高）。
 * 无障碍：容器可聚焦（`tabindex=0`），`↑/↓ PageUp/PageDown Home/End` 滚动预览区
 *       （不劫持全局滚动；直接对手机框内的滚动容器 `scrollBy`，避免滚到画布外）。
 * ★ 浅色隔离：本文件整体渲染在 `.preview-scope` 子树内，
 *   只使用 `tokens.preview.*`（内联）与不含 ch 前缀的 Tailwind 类；
 *   禁止出现应用级暗色 Token（bg / text / border 三类 ch 前缀类一律不得出现）。
 * ========================================================================== -->
<template>
  <div
    ref="rootRef"
    class="flex w-full flex-col items-center gap-sm"
    tabindex="0"
    role="group"
    :aria-label="`长图预览（${products.length} 张切片，总高 ${totalHeight} 像素）`"
    @keydown="onKeydown"
  >
    <PreviewFrame mode="longimage" :images="[]" :switchable="false" :padded="false">
      <div class="relative w-full">
        <div class="flex w-full flex-col">
          <img
            v-for="(item, position) in products"
            :key="item.seqNo || position"
            :src="item.fileUrl"
            :alt="`${alt} 长图第 ${position + 1} 段`"
            class="block w-full"
            :style="{ aspectRatio: sliceRatio(item) }"
          />
        </div>

        <!-- 右侧高度刻度：与内容同层，随内容一起滚动 -->
        <div class="pointer-events-none absolute right-0 top-0 h-full w-14" aria-hidden="true">
          <span
            v-for="mark in marks"
            :key="mark.key"
            class="absolute right-0 flex -translate-y-1/2 items-center justify-end gap-xs pr-xs"
            :style="{ top: `${mark.percent}%` }"
          >
            <span class="text-[10px] tabular-nums" :style="{ color: preview.text }">{{ mark.label }}</span>
            <span class="block h-px w-3" :style="{ backgroundColor: preview.border }"></span>
          </span>
        </div>
      </div>
    </PreviewFrame>

    <p class="text-center text-caption" :style="{ color: tokens.text.tertiary }">
      手机框内可纵向滚动；右侧为高度刻度（共 {{ products.length }} 段 · 总高 {{ totalHeight }}px）。
      聚焦本区域后可用 ↑ / ↓ / PageUp / PageDown 滚动。
    </p>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import PreviewFrame from '@/components/biz/PreviewFrame.vue'
import { tokens } from '@/js/tokens'

const props = defineProps({
  /** 切片产物（`{ seqNo, fileUrl, width, height, ... }`，数值已 Number 化） */
  products: { type: Array, default: () => [] },
  /** 渲染出参 meta（取 `fullHeight` / `fullWidth` / `sliceHeight`） */
  meta: { type: Object, default: () => ({}) },
  /** 主题标题（仅用于图片 alt） */
  alt: { type: String, default: '预览' }
})

const preview = tokens.preview
const rootRef = ref(null)
/** 手机框内的滚动容器（PreviewFrame 的 `overflow-y-auto` 层）；延迟解析，避免图片未加载时判定失败 */
let scroller = null

const list = computed(() => (Array.isArray(props.products) ? props.products : []))
/** 切片高度（回落到 `meta.sliceHeight` → 1440，与 §2.7 版式种子一致）；字符串按 Number() 处理 */
const sliceFallback = computed(() => Number(props.meta?.sliceHeight) || 1440)
const heights = computed(() => list.value.map((item) => Number(item.height) || sliceFallback.value))
const totalHeight = computed(() => {
  const fromMeta = Number(props.meta?.fullHeight)
  if (fromMeta > 0) return fromMeta
  return heights.value.reduce((sum, height) => sum + height, 0)
})

/** 刻度：每个切片边界（含首段 0 与末段总高）；`percent` 相对总高定位 */
const marks = computed(() => {
  const total = totalHeight.value
  if (!total) return []
  const out = []
  let acc = 0
  heights.value.forEach((height, position) => {
    out.push({ key: `mark-${position}`, label: `${acc}`, percent: (acc / total) * 100 })
    acc += height
  })
  out.push({ key: 'mark-total', label: `${acc}`, percent: 100 })
  return out
})

/** 单张比例：宽高缺失时回落 3:4（ch_layout 种子 swipe_v1/longimage_v1 的 ratio） */
function sliceRatio(item) {
  const width = Number(item?.width)
  const height = Number(item?.height)
  if (width > 0 && height > 0) return `${width} / ${height}`
  return '3 / 4'
}

/**
 * 查找手机框内的滚动容器。
 * ★ 注意：`PreviewFrame` 是**本组件的子节点**（手机框内含图片层），
 *   故滚动容器是 `rootRef` 的**后代**而非祖先 —— 必须在子树内向下查找。
 */
function resolveScroller() {
  const nodes = rootRef.value ? rootRef.value.querySelectorAll('*') : []
  for (const node of nodes) {
    const overflowY = window.getComputedStyle(node).overflowY
    if (overflowY === 'auto' || overflowY === 'scroll') return node
  }
  return null
}

onMounted(() => {
  scroller = resolveScroller()
  if (!scroller) console.warn('[P-08] 未找到手机框内的滚动容器，长图键盘滚动不可用（仍可用鼠标滚轮）')
})

/** ↑/↓ 等滚动键：仅在预览区聚焦时生效，直接滚动手机框内部，不劫持全局滚动 */
function onKeydown(event) {
  const step = { ArrowUp: -120, ArrowDown: 120, PageUp: -600, PageDown: 600 }[event.key]
  if (step === undefined && event.key !== 'Home' && event.key !== 'End') return
  // 懒解析：首帧图片未加载完成时祖先可能还不是滚动容器
  const target = scroller || (scroller = resolveScroller())
  if (!target) return
  event.preventDefault()
  if (event.key === 'Home') target.scrollTo({ top: 0 })
  else if (event.key === 'End') target.scrollTo({ top: target.scrollHeight })
  else target.scrollBy({ top: step, behavior: 'auto' })
}
</script>
