<!-- ============================================================================
 * SpecChecker · L2 业务组件（Step 4）
 * ----------------------------------------------------------------------------
 * 规格：图标 + 标题 + 详情 + 操作；三级（阻断 / 警告 / 通过）；**必带「定位」与「去修正」**；
 *       敏感词项回显上下文并高亮命中区间。
 * ★ 安全（裁定 F）：高亮区间一律 `text.slice(offsetStart, offsetEnd)` 分段渲染 + `<mark>`，
 *   **禁止**用 v-html 拼接含接口文本的字符串。
 * 口径（§2.6 修正 ②）：接口 `level` 为 ERROR / WARN，UI 三分类为 阻断 / 警告 / 通过。
 * 依赖：`context` 为命中所在的原始字段文本（缺少时只回显 matchedWord，不猜测偏移）。
 * ========================================================================== -->
<template>
  <article class="flex items-start gap-md rounded-lg border px-lg py-md" :class="toneClass">
    <i :class="meta.icon" class="mt-xs shrink-0 text-body" :style="{ color: meta.color }" aria-hidden="true"></i>

    <div class="flex min-w-0 flex-1 flex-col gap-sm">
      <div class="flex flex-wrap items-center gap-sm">
        <span class="text-body font-medium text-ch-text-primary">{{ issue.message || meta.label }}</span>
        <span
          v-if="issue.errCode"
          class="rounded-sm border border-ch-border px-xs font-mono text-code text-ch-text-tertiary"
        >
          {{ issue.errCode }}
        </span>
      </div>

      <p v-if="locationText" class="text-caption text-ch-text-secondary">{{ locationText }}</p>

      <!-- 命中上下文：分段渲染，命中区间用 <mark>，其余为文本节点 -->
      <p
        v-if="segments.length"
        class="overflow-x-auto whitespace-pre-wrap break-all rounded-md border border-ch-border bg-ch-input px-sm py-xs font-mono text-code text-ch-text-secondary"
      >
        <template v-for="(segment, index) in segments" :key="index">
          <mark
            v-if="segment.hit"
            class="rounded-sm bg-ch-warning/30 px-xs text-ch-text-primary"
          >{{ segment.text }}</mark>
          <template v-else>{{ segment.text }}</template>
        </template>
      </p>

      <div class="flex flex-wrap items-center gap-sm">
        <button
          v-if="showLocate"
          type="button"
          class="inline-flex h-7 items-center gap-xs rounded-md px-sm text-caption text-ch-text-secondary transition-colors duration-150 ease-out hover:bg-ch-hover hover:text-ch-text-primary"
          :aria-label="`定位到问题位置：${locationText || issue.field || '当前字段'}`"
          @click="emit('locate', issue)"
        >
          <i class="fa fa-crosshairs" aria-hidden="true"></i>
          定位
        </button>
        <AppButton size="sm" @click="emit('fix', issue)">去修正</AppButton>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import AppButton from '@/components/base/AppButton.vue'
import { COMPLIANCE_LEVEL_MAP, SENSITIVE_LEVEL_MAP, resolveStatusMeta } from '@/config/chOptions'

const props = defineProps({
  /** { level, message, location, field?, errCode, offsetStart, offsetEnd, matchedWord } */
  issue: { type: Object, default: () => ({}) },
  /** 命中所在字段的原文（用于按偏移切片高亮；缺失时仅回显 matchedWord） */
  context: { type: String, default: '' },
  showLocate: { type: Boolean, default: true }
})

const emit = defineEmits(['fix', 'locate'])

/** 上下文窗口：命中前后各保留 40 字符，两端以省略号示意（避免整段长文铺满） */
const WINDOW = 40

const LEVEL_MAP = { ...COMPLIANCE_LEVEL_MAP, ...SENSITIVE_LEVEL_MAP }

const meta = computed(() => resolveStatusMeta(LEVEL_MAP, props.issue.level))

const TONE = {
  danger: 'border-ch-danger/40 bg-ch-danger/10',
  warning: 'border-ch-warning/40 bg-ch-warning/10',
  success: 'border-ch-success/40 bg-ch-success/10'
}

const toneClass = computed(() => {
  if (props.issue.level === 'ERROR' || props.issue.level === 'BLOCK') return TONE.danger
  if (props.issue.level === 'WARN') return TONE.warning
  if (props.issue.level === 'PASS') return TONE.success
  return 'border-ch-border bg-ch-surface'
})

const locationText = computed(() => {
  const parts = []
  if (props.issue.location) parts.push(`位置：${props.issue.location}`)
  if (props.issue.field) parts.push(`字段：${props.issue.field}`)
  return parts.join('　')
})

/**
 * 高亮分段：仅当偏移合法（0 <= start < end <= text.length）时切片；
 * 非法或缺失时退回整段/命中词，绝不越界读取。
 */
const segments = computed(() => {
  const text = props.context || ''
  const issue = props.issue || {}
  const start = Number(issue.offsetStart)
  const end = Number(issue.offsetEnd)

  if (!text) {
    return issue.matchedWord ? [{ text: issue.matchedWord, hit: true }] : []
  }

  const valid = Number.isFinite(start) && Number.isFinite(end) && start >= 0 && end > start && end <= text.length
  if (!valid) return [{ text, hit: false }]

  const from = Math.max(0, start - WINDOW)
  const to = Math.min(text.length, end + WINDOW)
  const parts = []
  if (from > 0) parts.push({ text: '…', hit: false })
  parts.push({ text: text.slice(from, start), hit: false })
  parts.push({ text: text.slice(start, end), hit: true })
  parts.push({ text: text.slice(end, to), hit: false })
  if (to < text.length) parts.push({ text: '…', hit: false })
  return parts.filter((part) => part.text)
})
</script>
