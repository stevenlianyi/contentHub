<!-- ============================================================================
 * SourceTag · L1 基础组件（Step 4）
 * ----------------------------------------------------------------------------
 * 规格：12px；四值映射 `web → Web` / `api → Worker` / `mcp → MCP` / `system → System`。
 * 说明：图标为**功能性图标**（非状态语义），故不受 §2.6 三重编码约束；
 *       未知来源兜底展示原值 + 空心 ○ + 灰色（与 StateBadge 兜底口径一致）。
 * ========================================================================== -->
<template>
  <span
    class="inline-flex items-center gap-xs rounded-sm border border-ch-border px-xs py-[2px] text-caption"
    :class="meta.tone"
    :aria-label="`来源：${meta.label}`"
  >
    <i :class="meta.icon" aria-hidden="true"></i>
    <span>{{ meta.label }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  source: { type: String, default: 'system' } // web / api / mcp / system
})

const SOURCE_MAP = {
  web: { label: 'Web', icon: 'fa fa-globe', tone: 'text-ch-text-secondary' },
  api: { label: 'Worker', icon: 'fa fa-server', tone: 'text-ch-text-secondary' },
  mcp: { label: 'MCP', icon: 'fa fa-plug', tone: 'text-ch-info' },
  system: { label: 'System', icon: 'fa fa-gear', tone: 'text-ch-text-secondary' }
}

const meta = computed(() => {
  const hit = SOURCE_MAP[props.source]
  if (hit) return hit
  return { label: props.source || '未知', icon: 'fa-regular fa-circle', tone: 'text-ch-text-tertiary' }
})
</script>
