<!-- ============================================================================
 * TopicRow · 主题行组件（Step 5 抽出，P-01 最近主题 / P-02 主题列表共用）
 * ----------------------------------------------------------------------------
 * 职责边界（越界授权 A）：**只做展示与事件**——行内渲染
 *   标题 / StateBadge(domain=topic) / PlatformChip / fromNow(更新时间)；
 *   不含任何取数逻辑（取数由页面或 composable 负责）。
 *
 * ★ 两种形态（Step 6 裁定 F：整行 button 不能嵌进 el-table 的 <tr>）：
 *   · `variant="row"`（缺省）：根节点是原生 `<button>`，**整行可聚焦**（Step 5 行为不变）；
 *   · `variant="cell"`：只渲染行内容、**不包裹任何交互元素**，交互（键盘路径）由承载它的
 *     `<td>` / `<li>` 提供（标题默认走 `#title` 插槽，宿主可在其中放 `<RouterLink>`）。
 *   两种形态都禁止 `div + @click` 独自承担交互。
 *
 * 更新时间的字段口径（★ 只读权威字段名，裁定 a5）：`ch_topic.modifyYMDHMS`
 *   （code/src/database/ch_topic.txt:26）。Mock 亦已全局对齐为 `modifyYMDHMS`，
 *   **不再保留旧的 updated 前缀兜底分支**（避免两种命名并存掩盖字段漂移）。
 *
 * 无障碍（§2.11 + WCAG 2.1 AA）：
 *   · `aria-label`（仅 row 形态）复述「标题 / 状态 / 平台 / 更新时间」，行内徽章只承担视觉编码；
 *   · `variant="cell"` 不设 aria-label（无交互语义，避免屏幕阅读器读出双重语义）；
 *   · 焦点圈由 styles/tailwind.css 的 `*:focus-visible`（2px 主色 + 2px offset）统一提供，
 *     本文件不得出现 `outline: none`。
 *
 * 响应式：< md 纵向堆叠；≥ md 按网格列宽取 `--ch-col-*` Token（colStatusW 96 / colPlatformW 180 /
 *   colUpdatedW 110，与 §2.3 一致）。
 * ========================================================================== -->
<template>
  <button
    v-if="variant === 'row'"
    type="button"
    class="flex w-full min-h-11 flex-col justify-center gap-xs px-0 py-sm text-left transition-colors duration-150 ease-out hover:bg-ch-hover md:grid md:items-center"
    :class="TOPIC_ROW_GRID_CLASS"
    :aria-label="ariaLabel"
    @click="emit('row-click', topic)"
  >
    <span class="min-w-0 truncate text-body-s text-ch-text-primary" :title="topic.title">
      {{ topic.title }}
    </span>
    <StateBadge domain="topic" :status="topic.status" />
    <PlatformChip v-if="showPlatform" :platform="topic.platform" size="sm" />
    <span v-else class="text-body-s text-ch-text-tertiary" aria-label="平台：本期不展示">—</span>
    <span class="text-caption text-ch-text-tertiary" :title="modified.absolute || ''">
      {{ modified.text || '—' }}
    </span>
    <span class="text-caption text-ch-primary">查看</span>
  </button>

  <div v-else class="flex flex-col gap-xs md:grid md:items-center" :class="TOPIC_CELL_GRID_CLASS">
    <slot name="title">
      <span class="min-w-0 truncate text-body-s text-ch-text-primary" :title="topic.title">{{ topic.title }}</span>
    </slot>
    <StateBadge domain="topic" :status="topic.status" />
    <PlatformChip v-if="showPlatform" :platform="topic.platform" size="sm" />
    <span v-else class="text-body-s text-ch-text-tertiary">—</span>
    <span class="text-body-s text-ch-text-tertiary" :title="modified.absolute || ''">{{ modified.text || '—' }}</span>
  </div>
</template>

<script>
/**
 * 行网格模板：与 RecentTopics 的列表表头**共用同一常量**，避免两处列宽漂移。
 * 5 列 = 标题（自适应，minmax(0,1fr) 保证可截断）/ 状态 96 / 平台 180 / 更新 110 / 操作 64。
 */
export const TOPIC_ROW_GRID_CLASS =
  'md:grid-cols-[minmax(0,1fr)_var(--ch-col-status-w)_var(--ch-col-platform-w)_var(--ch-col-updated-w)_4rem] md:gap-md'

/** cell 形态：无操作列（交互由宿主 td/li 提供），故 4 列 */
export const TOPIC_CELL_GRID_CLASS =
  'md:grid-cols-[minmax(0,1fr)_var(--ch-col-status-w)_var(--ch-col-platform-w)_var(--ch-col-updated-w)] md:gap-md'
</script>

<script setup>
import { computed } from 'vue'
import StateBadge from '@/components/biz/StateBadge.vue'
import PlatformChip from '@/components/biz/PlatformChip.vue'
import { PLATFORM_MAP, TOPIC_STATUS_MAP } from '@/config/chOptions'
import { fromNow } from '@/utils/common'

const props = defineProps({
  /** 主题记录（`topicqry` 出参原样传入，字段不做二次加工） */
  topic: { type: Object, required: true },
  /** row = 整行原生 button（缺省，Step 5 行为）；cell = 只渲染行内容，交互由宿主元素承载 */
  variant: { type: String, default: 'row' },
  /** 是否渲染平台列（P-02 平台列本期固定展示「—」，见裁定 C） */
  showPlatform: { type: Boolean, default: true }
})

const emit = defineEmits(['row-click'])

/** 更新时间：只读权威字段名 `modifyYMDHMS`（裁定 a5，已删除旧的 updated 前缀兜底） */
const modified = computed(() => fromNow(props.topic?.modifyYMDHMS || ''))

/** 整行可访问名（仅 row 形态）：复述四要素，保证不依赖颜色/图标也能获得完整语义 */
const ariaLabel = computed(() => {
  const topic = props.topic || {}
  const status = TOPIC_STATUS_MAP[topic.status]?.label || topic.status || '未知状态'
  const platform = PLATFORM_MAP[topic.platform]?.label || topic.platform || '未知平台'
  return `${topic.title || ''}，状态：${status}，平台：${platform}，更新于 ${modified.value.text || '未知时间'}，点击进入主题`
})
</script>
