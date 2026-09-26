<!-- ============================================================================
 * WordCounter · L2 业务组件（Step 4）
 * ----------------------------------------------------------------------------
 * 规格：12px；≥90% 转 warning、越界转 danger；`aria-live="polite"`。
 * ★ 播报策略：可见计数 `aria-hidden`（避免每次输入都朗读），另置一个只在「接近上限 / 越界」
 *   才写入文字的 live region —— 既满足 aria-live，又不打扰输入（计划明确要求）。
 * 口径：`current` 由调用方传入（`utils/common.js` 的 wordCount 或 charCount，见 §2.7 两套口径）。
 * ========================================================================== -->
<template>
  <span class="inline-flex items-center gap-xs">
    <span class="inline-flex items-center gap-xs text-caption tabular-nums" :class="toneClass" :title="summary">
      <i v-if="tone !== 'normal'" :class="iconClass" aria-hidden="true"></i>
      <span aria-hidden="true">{{ display }}</span>
    </span>
    <span class="sr-only" :aria-live="ariaLive">{{ liveText }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  current: { type: [Number, String], default: 0 },
  max: { type: Number, default: 0 },
  /** 区间下限（如主题详述 2000–5000）：>0 时展示为“当前 / 下限–上限” */
  min: { type: Number, default: 0 },
  ariaLive: { type: String, default: 'polite' }
})

const currentNum = computed(() => Number(props.current) || 0)
const maxNum = computed(() => Number(props.max) || 0)

const isOver = computed(() => maxNum.value > 0 && currentNum.value > maxNum.value)
const isUnder = computed(() => props.min > 0 && currentNum.value < props.min)
const nearLimit = computed(() => maxNum.value > 0 && currentNum.value >= maxNum.value * 0.9)

/** normal / warning / danger */
const tone = computed(() => {
  if (isOver.value || isUnder.value) return 'danger'
  if (nearLimit.value) return 'warning'
  return 'normal'
})

const toneClass = computed(() => {
  if (tone.value === 'danger') return 'text-ch-danger'
  if (tone.value === 'warning') return 'text-ch-warning'
  return 'text-ch-text-tertiary'
})

const iconClass = computed(() =>
  tone.value === 'danger' ? 'fa fa-circle-xmark' : 'fa fa-triangle-exclamation'
)

const display = computed(() => {
  if (props.min > 0) return `${currentNum.value} / ${props.min}–${maxNum.value}`
  return `${currentNum.value} / ${maxNum.value}`
})

const summary = computed(() => {
  if (isOver.value) return `已超出上限 ${currentNum.value - maxNum.value} 字`
  if (isUnder.value) return `还差 ${props.min - currentNum.value} 字达到下限`
  if (props.min > 0) return `需在 ${props.min}–${maxNum.value} 字之间`
  return `上限 ${maxNum.value} 字`
})

/** 仅在接近上限 / 越界时给出播报文字，避免每次输入都触发 aria-live */
const liveText = computed(() => {
  if (isOver.value) return `已超出上限 ${currentNum.value - maxNum.value} 字`
  if (isUnder.value && nearLimit.value) return `还需 ${props.min - currentNum.value} 字`
  if (nearLimit.value) return `已接近上限，还剩 ${maxNum.value - currentNum.value} 字`
  return ''
})
</script>
