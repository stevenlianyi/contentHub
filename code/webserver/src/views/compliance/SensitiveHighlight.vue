<!-- ============================================================================
 * SensitiveHighlight · P-09 页私有组件（Step 13，裁定 E）
 * ----------------------------------------------------------------------------
 * 职责：把后端给的**敏感词命中偏移**渲染成可读上下文：命中区间前后各 20 字（不足则贴边），
 *       命中区间加 `danger` 背景的 `<mark>`。
 * ★ 定位来源只有后端：`offsetStart` / `offsetEnd`（end 为**开区间**）/ `matchedWord`；
 *   **禁止**前端自行做字符串匹配定位（不用 indexOf / includes / RegExp 找词）。
 * ★ 安全：一律 `String.prototype.slice()` 分段渲染为文本节点 + `<mark>`，
 *   **禁止 `v-html`** 拼接含接口文本的字符串。
 * ★ 容错：偏移越界 / 非数字 / 原文本不可用（如详述已转存为文件、字段为空）→ 退化为
 *   「只显示 matchedWord + location 文本」并 `console.error`，绝不越界读取、绝不猜测位置。
 * ★ 无原文时（`text` 为空）**不做任何高亮**：宁可少展示，也不给出可能错位的高亮。
 * ========================================================================== -->
<template>
  <div class="flex flex-col gap-sm">
    <!-- 调用方传入的 issue 卡片（SpecChecker：message / location / 去修正） -->
    <slot />

    <div v-if="segments.length" class="flex flex-col gap-xs">
      <span class="text-caption text-ch-text-tertiary">
        命中上下文（后端偏移 offsetStart={{ start }} / offsetEnd={{ end }}，命中「{{ word }}」）
      </span>
      <p
        class="overflow-x-auto whitespace-pre-wrap break-all rounded-md border border-ch-border bg-ch-input px-sm py-xs font-mono text-code text-ch-text-secondary"
      >
        <template v-for="(segment, index) in segments" :key="index">
          <mark v-if="segment.hit" class="rounded-sm bg-ch-danger/30 px-xs text-ch-text-primary">{{ segment.text }}</mark>
          <template v-else>{{ segment.text }}</template>
        </template>
      </p>
    </div>

    <p v-else class="text-caption text-ch-warning">{{ fallbackText }}</p>
  </div>
</template>

<script setup>
import { computed, watch } from 'vue'
import { normalizeField } from '@/views/compliance/useComplianceCheck'

const props = defineProps({
  /** 原始 issue（★ 必须含后端 offsetStart / offsetEnd / matchedWord，不做任何改写） */
  issue: { type: Object, default: () => ({}) },
  /** 命中所在的**原始字段文本**（由页面从 `topicqry` 详情按 normalizeField(issue.field) 取出） */
  text: { type: String, default: '' }
})

/** 上下文窗口：命中前后各 20 字（裁定 E；不足则贴边，不补白） */
const WINDOW = 20
/** 省略号：窗口被裁切时用于示意两侧仍有内容 */
const ELLIPSIS = '…'

const start = computed(() => Number(props.issue?.offsetStart))
const end = computed(() => Number(props.issue?.offsetEnd))
const word = computed(() => String(props.issue?.matchedWord || ''))
const source = computed(() => String(props.text || ''))

/** 偏移是否可信：非数字 / 越界 / 空区间 / 超出原文长度 一律判为不可信 */
const offsetsValid = computed(() => {
  const text = source.value
  const from = start.value
  const to = end.value
  if (!text) return false
  if (!Number.isFinite(from) || !Number.isFinite(to)) return false
  if (from < 0 || to <= from || to > text.length) return false
  return true
})

const fallbackText = computed(
  () => `命中「${word.value || '（后端未返回 matchedWord）'}」· 位置：${String(props.issue?.location || normalizeField(props.issue?.field) || '未提供')}`
)

/** 分段：命中前窗口 / 命中区间（hit）/ 命中后窗口；窗口裁切处补省略号 */
const segments = computed(() => {
  if (!offsetsValid.value) return []
  const text = source.value
  const from = Math.max(0, start.value - WINDOW)
  const to = Math.min(text.length, end.value + WINDOW)
  const parts = []
  if (from > 0) parts.push({ text: ELLIPSIS, hit: false })
  parts.push({ text: text.slice(from, start.value), hit: false })
  parts.push({ text: text.slice(start.value, end.value), hit: true })
  parts.push({ text: text.slice(end.value, to), hit: false })
  if (to < text.length) parts.push({ text: ELLIPSIS, hit: false })
  return parts.filter((part) => part.text)
})

/** 偏移不可信时记录一条错误供排查（不抛错、不阻断渲染） */
watch(
  offsetsValid,
  (valid) => {
    if (valid) return
    console.error('[P-09] 敏感词偏移不可信（越界/非数字/原文不可用），退化为仅显示命中词 + location', {
      field: props.issue?.field,
      location: props.issue?.location,
      offsetStart: props.issue?.offsetStart,
      offsetEnd: props.issue?.offsetEnd,
      matchedWord: props.issue?.matchedWord,
      textLength: source.value.length
    })
  },
  { immediate: true }
)
</script>
