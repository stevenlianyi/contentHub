<!-- ============================================================================
 * MetricCard · 工作台指标卡（Step 5 · P-01）
 * ----------------------------------------------------------------------------
 * 形态：数量（Display 32px/700）+ 标签 + 图标；整卡可点击直达「已按口径筛选」的列表页。
 *
 * 无障碍（裁定 G）：
 *   · 根节点是 `<RouterLink>`（不是 div + @click），键盘可达、可被「在新标签页打开」；
 *   · 焦点态 = 全局 `*:focus-visible` 的 2px outline + 本卡 `focus-visible:shadow-focus`，
 *     **不得** `outline: none`；
 *   · `aria-label` 给出「标签 + 数值 + 去向」，图标 `aria-hidden`（不参与可访问名）。
 *
 * 颜色：一律走 Tailwind 语义类（ch-* / plat.*），本文件无任何字面色值。
 * 图标：来自 §2.3.5 图标语义映射表，不得替换为表外图标。
 * ========================================================================== -->
<template>
  <RouterLink
    :to="to"
    class="flex min-w-0 items-start justify-between gap-md rounded-xl border border-ch-border bg-ch-surface p-xl transition-colors duration-150 ease-out hover:border-ch-primary hover:bg-ch-hover focus-visible:shadow-focus"
    :aria-label="`${label} ${value}，点击查看明细`"
  >
    <span class="flex min-w-0 flex-col gap-sm">
      <span class="truncate text-body-s text-ch-text-secondary">{{ label }}</span>
      <span class="text-display tabular-nums text-ch-text-primary">{{ value }}</span>
    </span>
    <i :class="[icon, TONE_CLASS[tone] || TONE_CLASS.neutral]" class="text-lg" aria-hidden="true"></i>
  </RouterLink>
</template>

<script setup>
import { RouterLink } from 'vue-router'

defineProps({
  /** 卡片标签，如「待渲染」 */
  label: { type: String, required: true },
  /** 卡片数值（数量） */
  value: { type: [String, Number], default: 0 },
  /** 图标（§2.3.5 表内语义图标，如 `fa fa-paper-plane`） */
  icon: { type: String, default: 'fa fa-file-lines' },
  /** neutral（默认）/ warning（异常提示，如「渲染失败」） */
  tone: { type: String, default: 'neutral' },
  /** 跳转目标：字符串路径或 `{ path, query }` 对象 */
  to: { type: [String, Object], required: true }
})

/** 图标着色：仅图标承载状态色，数字保持主文字色以保证可读性一致 */
const TONE_CLASS = {
  neutral: 'text-ch-text-tertiary',
  warning: 'text-ch-warning',
  danger: 'text-ch-danger'
}
</script>
