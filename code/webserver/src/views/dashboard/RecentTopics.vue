<!-- ============================================================================
 * RecentTopics · 工作台「最近主题」区块（Step 5 · P-01）
 * ----------------------------------------------------------------------------
 * 内容：恰好 6 行（由 `useDashboardData.pickRecentTopics` 按更新时间倒序后 slice(0,6)），
 *       行内四要素交给共用的 `views/topics/TopicRow.vue`，本组件只负责
 *       ① 区块外壳 ② 表头 ③ 三态（骨架 / 空态 / 有数据）。
 *
 * 三态（裁定 I）：
 *   · 加载 → `Skeleton type="table"`（表头 40 + 行 44 × 6，与最终形状一致，避免首屏跳动）；
 *   · 空   → `EmptyState`；
 *   · 错误 → 由页面统一渲染（4 个请求同属一个 Promise.all，失败即整体重试，不重复三处报错）。
 *
 * 表头为**纯视觉**对齐（每行按钮的 aria-label 已复述全部要素），故 `aria-hidden="true"`，
 * 避免屏幕阅读器把「标题/状态/平台/更新时间/操作」当成无关联的孤立文字读出。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-lg rounded-xl border border-ch-border bg-ch-surface p-xl">
    <header class="flex flex-wrap items-center justify-between gap-sm">
      <h2 class="text-h2 text-ch-text-primary">最近主题</h2>
      <RouterLink
        to="/topics"
        class="text-body-s text-ch-primary transition-colors duration-150 ease-out hover:text-ch-primary-hover"
      >
        查看全部
      </RouterLink>
    </header>

    <Skeleton v-if="loading" type="table" :rows="RECENT_LIMIT" label="最近主题加载中" />

    <EmptyState
      v-else-if="!topics.length"
      icon="fa fa-file-lines"
      title="暂无主题"
      description="创建主题后，最近更新的 6 条会显示在这里。"
    />

    <ul v-else class="flex flex-col">
      <li
        class="hidden border-b border-ch-border pb-sm text-caption text-ch-text-secondary md:grid md:items-center"
        :class="TOPIC_ROW_GRID_CLASS"
        aria-hidden="true"
      >
        <span>标题</span>
        <span>状态</span>
        <span>平台</span>
        <span>更新时间</span>
        <span>操作</span>
      </li>
      <li
        v-for="topic in topics"
        :key="topic.topicCode || topic.recID"
        class="border-b border-ch-divider last:border-b-0"
      >
        <TopicRow :topic="topic" @row-click="emit('row-click', $event)" />
      </li>
    </ul>
  </section>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import Skeleton from '@/components/base/Skeleton.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import TopicRow, { TOPIC_ROW_GRID_CLASS } from '@/views/topics/TopicRow.vue'

/** 与 `useDashboardData.RECENT_LIMIT` 一致：骨架行数按最终行数给出，避免加载完成时高度跳变 */
const RECENT_LIMIT = 6

defineProps({
  /** 已按更新时间倒序的 6 条主题（排序口径见 useDashboardData） */
  topics: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['row-click'])
</script>
