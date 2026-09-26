<!-- ============================================================================
 * LayoutCard · L2 业务组件（Step 4）
 * ----------------------------------------------------------------------------
 * 规格：宽 160 / 高 120；结构示意图（抽象方块，非真实渲染）；选中态 primary 2px 边框
 *       （实现：1px `border-primary` + 1px inset ring 模拟 2px，见 §2.3.3 描边规则）+ 右上角 ✓。
 * ★ 可用性：`available=false` 时**不渲染**（由父级调用 `isLayoutAllowed()` 过滤，而非灰显）；
 *   组件自身**不做平台分支**（§2.11 禁止在业务组件里写平台/厂商分支）。
 * ★ 计划原文「primory」为错别字，实现使用 `primary`。
 * ========================================================================== -->
<template>
  <button
    v-if="available"
    type="button"
    class="relative flex h-[120px] w-[160px] shrink-0 flex-col justify-between rounded-xl border bg-ch-surface p-md text-left transition-colors duration-150 ease-out"
    :class="selected ? 'border-ch-primary ring-1 ring-inset ring-ch-primary' : 'border-ch-border hover:border-ch-border-light'"
    :aria-pressed="selected ? 'true' : 'false'"
    :aria-label="`选择版式：${layoutName}${selected ? '（已选中）' : ''}`"
    @click="emit('select', layoutCode)"
  >
    <!-- 结构示意图：按 layoutType 抽象成方块，不渲染真实内容 -->
    <span class="flex h-[64px] items-center justify-center rounded-lg border border-ch-border bg-ch-input p-xs" aria-hidden="true">
      <span v-if="layoutType === 'stack'" class="flex w-full flex-col gap-xs">
        <span class="h-2 w-full rounded-sm bg-ch-border-light"></span>
        <span class="h-2 w-full rounded-sm bg-ch-border-light"></span>
        <span class="h-2 w-2/3 rounded-sm bg-ch-border-light"></span>
      </span>
      <span v-else-if="layoutType === 'carousel'" class="flex w-full items-center gap-xs">
        <span class="h-8 w-1/3 rounded-sm bg-ch-border-light"></span>
        <span class="h-8 w-1/3 rounded-sm bg-ch-border"></span>
        <span class="h-8 w-1/3 rounded-sm bg-ch-border-light"></span>
      </span>
      <span v-else-if="layoutType === 'longimage'" class="flex h-full w-1/3 flex-col items-center justify-center rounded-sm bg-ch-border-light"></span>
      <span v-else class="flex w-full flex-col items-center gap-xs">
        <span class="h-6 w-full rounded-sm bg-ch-border-light"></span>
        <span class="flex gap-xs">
          <span class="h-1.5 w-1.5 rounded-full bg-ch-text-tertiary"></span>
          <span class="h-1.5 w-1.5 rounded-full bg-ch-border-light"></span>
          <span class="h-1.5 w-1.5 rounded-full bg-ch-border-light"></span>
        </span>
      </span>
    </span>

    <span class="flex items-center justify-between gap-xs">
      <span class="truncate text-body-s text-ch-text-primary">{{ layoutName }}</span>
      <span class="shrink-0 text-caption text-ch-text-tertiary">{{ typeLabel }}</span>
    </span>

    <span
      v-if="selected"
      class="absolute right-sm top-sm flex h-4 w-4 items-center justify-center rounded-full bg-ch-primary text-[10px] text-ch-text-inverse"
      aria-hidden="true"
    >
      <i class="fa fa-check"></i>
    </span>
  </button>
</template>

<script setup>
import { computed } from 'vue'
import { LAYOUT_TYPE_MAP } from '@/config/chOptions'

const props = defineProps({
  layoutCode: { type: String, default: '' },
  layoutName: { type: String, default: '' },
  layoutType: { type: String, default: '' },
  /** 由父级用 `isLayoutAllowed(layoutCode, platform)` 计算后传入 */
  available: { type: Boolean, default: true },
  selected: { type: Boolean, default: false }
})

const emit = defineEmits(['select'])

const typeLabel = computed(() => LAYOUT_TYPE_MAP[props.layoutType] || props.layoutType || '—')
</script>
