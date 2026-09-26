<!-- ============================================================================
 * LayoutPicker · P-03 Tab3「选择版式」（Step 9）
 * ----------------------------------------------------------------------------
 * 职责：① 目标平台筛选器（**过滤器**，不是独立持久态 —— `ch_topic` 无 platform 列，裁定 B）；
 *      ② 4 套版式卡片网格（数据来自 `layoutqry`，已按 `enabled='1'` + `sortWeight` 升序归一化）。
 * ★ 不可用组合**直接不渲染**（`v-if`，不是 `display:none`）：卡片列表由 `isLayoutAllowed()` 过滤，
 *   矩阵与 `ch_layout.platform` 冲突时**以矩阵为准**（裁定 C），漂移日志见 TabLayout.vue。
 * ★ 组件不持有平台业务分支：`LayoutCard` 只接收 `available`，过滤在父级/本层完成（§2.11）。
 * ★ 空响应容错（附录 B R-24）：平台数据为空时回退到 `chOptions` 的平台字典**仅用于筛选器可用**，
 *   并显式标注「平台配置暂不可用」；矩阵区仍显示 EmptyState（见 PlatformMatrix.vue）。
 * ★ 单文件 ≤ 600 行（§2.1 硬约束）：本文件只做平台过滤与卡片网格，弹窗与前置校验不在本文件。
 * ========================================================================== -->
<template>
  <section class="ch-card flex flex-col gap-xl">
    <header class="flex flex-wrap items-start justify-between gap-md">
      <div>
        <h2 class="text-h3 text-ch-text-primary">选择版式</h2>
        <p class="text-body-s text-ch-text-secondary">
          先选目标平台，卡片区只展示该平台**可用**的版式；不可用组合不出现在卡片区。
        </p>
      </div>
      <span class="flex shrink-0 items-center gap-xs text-caption text-ch-text-tertiary" aria-live="polite">
        <i :class="saveIcon" aria-hidden="true"></i>
        <span>{{ saveText }}</span>
      </span>
    </header>

    <!-- 目标平台（过滤器） -->
    <div class="flex flex-col gap-sm">
      <span id="layout-picker-platform-label" class="text-body-s text-ch-text-secondary">目标平台</span>
      <div class="flex flex-wrap items-center gap-sm" role="group" aria-labelledby="layout-picker-platform-label">
        <button
          v-for="item in platformOptions"
          :key="item.platformCode"
          type="button"
          class="flex items-center gap-sm rounded-lg border px-md py-sm transition-colors duration-150 ease-out"
          :class="item.platformCode === platform
            ? 'border-ch-primary bg-ch-primary-subtle'
            : 'border-ch-border bg-ch-surface hover:border-ch-border-light'"
          :aria-pressed="item.platformCode === platform ? 'true' : 'false'"
          @click="emit('update:platform', item.platformCode)"
        >
          <PlatformChip :platform="item.platformCode" size="sm" />
          <i
            v-if="item.platformCode === platform"
            class="fa fa-check text-caption text-ch-primary"
            aria-hidden="true"
          ></i>
        </button>
      </div>
      <p v-if="!platforms.length" class="text-caption text-ch-warning">
        <i class="fa fa-triangle-exclamation" aria-hidden="true"></i>
        平台配置暂不可用（platformqry 未返回数据），筛选器已降级为内置平台字典。
      </p>
    </div>

    <!-- 已选版式在当前平台不可用（矩阵口径，裁定 C） -->
    <p
      v-if="selectedNotAllowed"
      class="flex items-start gap-sm rounded-lg border border-ch-warning px-lg py-md text-body-s text-ch-warning"
    >
      <i class="fa fa-triangle-exclamation mt-xs" aria-hidden="true"></i>
      <span>
        当前已选版式 <span class="font-mono text-code">{{ modelValue }}</span> 在
        {{ platformLabel }} 下不在可用矩阵内（已按服务端 layoutCode 回显，未擅自改动）；请改选下方任一卡片。
      </span>
    </p>

    <ErrorState v-if="error" :message="error" hint="版式配置读取失败，请重试。" @retry="emit('refresh')" />

    <Skeleton v-else-if="loading && !cards.length" type="card" :rows="1" label="版式配置加载中" />

    <EmptyState
      v-else-if="!cards.length"
      icon="fa fa-layer-group"
      title="当前平台没有可用版式"
      description="layoutqry 未返回该平台的可用版式（配置数据暂不可用，见附录 B R-24 / R-08），或矩阵未放行任何组合。"
    />

    <!-- 不可用组合不进入 DOM（v-if 过滤，非 display:none）；`data-layout-code` 便于核对实际渲染的卡片 -->
    <ul v-else class="flex flex-wrap gap-lg" role="list">
      <li v-for="item in cards" :key="item.layoutCode" :data-layout-code="item.layoutCode" class="flex flex-col gap-sm">
        <LayoutCard
          :layout-code="item.layoutCode"
          :layout-name="item.layoutName"
          :layout-type="item.layoutType"
          :available="true"
          :selected="item.layoutCode === modelValue"
          @select="emit('select', $event)"
        />
        <span class="font-mono text-code text-ch-text-secondary">{{ item.layoutCode }}</span>
        <p v-if="item.note" class="w-[160px] text-caption text-ch-warning">{{ item.note }}</p>
      </li>
    </ul>

    <p class="text-caption text-ch-text-tertiary">
      数据来源：layoutqry（enabled='1'，按 sortWeight 升序）；示意图为结构示意，非真实渲染。
      选择即静默保存到 ch_topic.layoutCode。
    </p>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import EmptyState from '@/components/base/EmptyState.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import Skeleton from '@/components/base/Skeleton.vue'
import LayoutCard from '@/components/biz/LayoutCard.vue'
import PlatformChip from '@/components/biz/PlatformChip.vue'
import {
  LAYOUT_PLATFORM_NOTES,
  PLATFORM_MAP,
  isLayoutAllowed
} from '@/config/chOptions'
import { fallbackPlatformOptions } from '@/views/topic/useRenderTrigger'

const props = defineProps({
  /** 归一化后的版式列表（layoutqry） */
  layouts: { type: Array, default: () => [] },
  /** 归一化后的平台列表（platformqry） */
  platforms: { type: Array, default: () => [] },
  /** 目标平台（过滤器） */
  platform: { type: String, default: '' },
  /** 服务端已选版式（topicqry 回显口径，裁定 A） */
  modelValue: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  savedAt: { type: String, default: '' },
  error: { type: String, default: '' }
})

const emit = defineEmits(['update:platform', 'select', 'refresh'])

/** 平台筛选器选项：优先 platformqry；为空时回退平台字典（仅筛选器可用，并显式标注） */
const platformOptions = computed(() =>
  props.platforms.length
    ? props.platforms.map((item) => ({ platformCode: item.platformCode, platformName: item.platformName }))
    : fallbackPlatformOptions()
)

const platformLabel = computed(
  () => PLATFORM_MAP[props.platform]?.label || props.platform || '当前平台'
)

/** 卡片 = layoutqry ∩ 矩阵放行的组合（不可用组合不进入 DOM） */
const cards = computed(() =>
  props.layouts
    .filter((item) => isLayoutAllowed(item.layoutCode, props.platform))
    .map((item) => ({ ...item, note: LAYOUT_PLATFORM_NOTES[`${item.layoutCode}|${props.platform}`] || '' }))
)

const selectedNotAllowed = computed(
  () => Boolean(props.modelValue) && !isLayoutAllowed(props.modelValue, props.platform)
)

const saveIcon = computed(() =>
  props.saving ? 'fa fa-circle-notch fa-spin' : props.savedAt ? 'fa fa-circle-check' : 'fa-regular fa-circle'
)

const saveText = computed(() => {
  if (props.saving) return '版式保存中…'
  if (props.savedAt) return `版式已保存 ${props.savedAt}`
  return '选择即自动保存（layoutCode）'
})
</script>
