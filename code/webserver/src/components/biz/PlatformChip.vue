<!-- ============================================================================
 * PlatformChip · L2 业务组件（Step 4）
 * ----------------------------------------------------------------------------
 * 规格：高 24（sm → 20）；微信 / 小红书 / 通用三色取自 chOptions.PLATFORM_MAP（Token 层单一来源）。
 * ★ 仅用于**平台识别**，不承载状态语义（状态一律用 StateBadge 的三重编码）。
 * ★ 不含任何「发布 / 投递」入口（小红书本期仅导出素材包）。
 * ★ 2026-09-24 修复「平台名折行畸形」：本组件是**原子标识**，任何容器下都必须单行 ——
 *   `shrink-0` 禁止被 flex 压缩、`whitespace-nowrap` 禁止文本换行（否则窄列里
 *   「微信公众号」会折成「微信公 / 众号」两行并把固定高 24 的胶囊撑变形）。
 *   ★ 使用方仍应为该列预留足够宽度（表格列宽见各页 columns；窄视口请配合横向滚动而非压缩）。
 * ========================================================================== -->
<template>
  <span
    class="inline-flex shrink-0 items-center gap-xs whitespace-nowrap rounded-md border px-sm text-caption"
    :class="sizeClass"
    :style="{ color: meta.color, borderColor: meta.color }"
    :aria-label="`平台：${meta.label}`"
  >
    <i :class="meta.icon" aria-hidden="true"></i>
    <span v-if="showLabel">{{ meta.label }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { PLATFORM_MAP } from '@/config/chOptions'
import { tokens } from '@/js/tokens'

const props = defineProps({
  platform: { type: String, default: '' },
  showLabel: { type: Boolean, default: true },
  size: { type: String, default: 'md' } // md(24) / sm(20)
})

const SIZE_CLASS = { sm: 'h-5', md: 'h-6' }

/** 平台识别图标（功能性，不受 §2.6 状态图标表约束） */
const PLATFORM_ICON = {
  wechat_mp: 'fa fa-comment-dots',
  xiaohongshu: 'fa fa-book-open',
  generic: 'fa fa-code'
}

const meta = computed(() => {
  const hit = PLATFORM_MAP[props.platform]
  if (hit) return { label: hit.label, color: hit.color, icon: PLATFORM_ICON[props.platform] || 'fa fa-circle' }
  return { label: props.platform || '未知平台', color: tokens.text.tertiary, icon: 'fa-regular fa-circle' }
})

const sizeClass = computed(() => SIZE_CLASS[props.size] || SIZE_CLASS.md)
</script>
