<!-- ============================================================================
 * Skeleton · L1 基础组件（Step 4）
 * ----------------------------------------------------------------------------
 * 规格：shimmer 1.5s（`animate-shimmer` ← tailwind.config.js 取 tokens.motion.shimmer）；
 *       形状匹配最终内容（表格=表头 40 + 行 44；卡片=主块 + 3 行 + 按钮位），避免跳动。
 * 无障碍：容器 aria-busy="true" + role="status" + 仅供屏阅读的「加载中」文案（§2.11）。
 * 降级：tailwind.css 的 prefers-reduced-motion 分支会把动画时长压到 0.01ms，无需额外处理。
 * ========================================================================== -->
<template>
  <div class="flex flex-col" :class="type === 'table' ? 'gap-0' : 'gap-md'" role="status" aria-busy="true" :aria-label="label">
    <span class="sr-only">{{ label }}</span>

    <!-- 表格：表头行（40）+ N 行（44），与 AppTable 的最终形状对齐 -->
    <template v-if="type === 'table'">
      <div class="flex h-10 items-center gap-lg rounded-t-md px-lg" :class="BAR_CLASS" aria-hidden="true">
        <span v-for="n in 5" :key="`h-${n}`" class="h-3 rounded-sm" :class="[...BAR_CLASS, headerWidth(n)]"></span>
      </div>
      <div
        v-for="row in rowCount"
        :key="`r-${row}`"
        class="flex h-11 items-center gap-lg border-b border-ch-border px-lg"
        aria-hidden="true"
      >
        <span
          v-for="n in 5"
          :key="`c-${row}-${n}`"
          class="h-3 rounded-sm"
          :class="[...BAR_CLASS, cellWidth(n, row)]"
        ></span>
      </div>
    </template>

    <!-- 卡片：一个 120 高主块 + N 行文字 + 一个按钮位 -->
    <template v-else-if="type === 'card'">
      <div class="h-[120px] w-full rounded-xl" :class="BAR_CLASS" aria-hidden="true"></div>
      <div
        v-for="n in rowCount"
        :key="`c-${n}`"
        class="h-3 rounded-sm"
        :class="[...BAR_CLASS, lineWidth(n)]"
        aria-hidden="true"
      ></div>
      <div class="mt-xs h-9 w-28 rounded-lg" :class="BAR_CLASS" aria-hidden="true"></div>
    </template>

    <!-- 详情：标题行 + N 行长文本 -->
    <template v-else>
      <div class="h-6 w-2/5 rounded-sm" :class="BAR_CLASS" aria-hidden="true"></div>
      <div
        v-for="n in rowCount"
        :key="`d-${n}`"
        class="h-3 rounded-sm"
        :class="[...BAR_CLASS, lineWidth(n)]"
        aria-hidden="true"
      ></div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  rows: { type: Number, default: 3 },
  type: { type: String, default: 'detail' }, // table / card / detail
  label: { type: String, default: '加载中' }
})

const rowCount = computed(() => Math.max(1, Number(props.rows) || 3))

/**
 * 骨架条统一类：`.shimmer` 提供渐变底（scoped，取 --ch-* 变量），`animate-shimmer` 提供
 * 1.5s linear 循环的 background-position 平移（tailwind.config.js ← tokens.motion.shimmer）。
 */
const BAR_CLASS = ['shimmer', 'animate-shimmer']

const WIDTH_CYCLE = ['w-3/5', 'w-4/5', 'w-2/5', 'w-3/4', 'w-1/2']
const HEADER_WIDTHS = ['w-24', 'w-32', 'w-20', 'w-28', 'w-16']

const headerWidth = (index) => HEADER_WIDTHS[index - 1] || 'w-24'
const lineWidth = (index) => WIDTH_CYCLE[(index - 1) % WIDTH_CYCLE.length]
const cellWidth = (index, row) => WIDTH_CYCLE[(index + row) % WIDTH_CYCLE.length]
</script>

<style scoped>
/* 渐变底：三段 Token 色，宽度 400% 以配合 shimmer 关键帧的 background-position 平移 */
.shimmer {
  background-image: linear-gradient(
    90deg,
    var(--ch-bg-elevated) 25%,
    var(--ch-bg-surface) 37%,
    var(--ch-bg-elevated) 63%
  );
  background-size: 400% 100%;
}
</style>
