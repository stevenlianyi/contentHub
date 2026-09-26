<!-- ============================================================================
 * Dashboard · 工作台（P-01，Step 5）
 * ----------------------------------------------------------------------------
 * 本文件只做**组合与布局**（≤600 行硬约束，裁定 H）：取数聚合在
 * `views/dashboard/useDashboardData.js`，区块分别在 dashboard/ 下的三个子组件。
 *
 * 结构：页面标题 + 唯一主按钮（新建主题）→ 4 张指标卡 → 最近主题 6 行 → 系统状态条。
 *
 * 三态（裁定 I）：
 *   · loading → 骨架屏（指标卡 4 张 / 最近主题 6 行 / 系统状态 1 行，形状与最终内容对齐）；
 *   · error   → 单个 `ErrorState`（含重试）。4 个请求同属一个 Promise.all，失败即整体重试，
 *               故不在三个区块各报一次错；页面不出现空白。
 *   · empty   → 由 `RecentTopics` 内置 `EmptyState` 承担。
 *
 * 响应式（裁定 J；基准 1440 + 5 档）：≤640 单列；≥640 两列；≥1360 四列。
 *   即 1280px 宽时指标卡为 2×2，1440px 时为 1×4，且均无横向滚动（固定 24px 内容边距 + fr 栅格，
 *   不使用固定像素宽度写死）。
 *
 * 红线（§1.1 / 通用约束 6）：本页不含任何小红书发布/投递入口。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-2xl">
    <header class="flex flex-wrap items-center justify-between gap-md">
      <h1 class="text-h1 text-ch-text-primary">工作台</h1>
      <AppButton type="primary" icon="fa fa-plus" @click="goCreateTopic">新建主题</AppButton>
    </header>

    <template v-if="loading">
      <!-- 加载态：4 张指标卡骨架（形状=标签行 + 数值行，故用 detail 而非 card 的 120 主块） -->
      <div class="grid grid-cols-1 gap-lg sm:grid-cols-2 min-[1360px]:grid-cols-4">
        <div
          v-for="n in METRIC_COUNT"
          :key="`metric-skeleton-${n}`"
          class="rounded-xl border border-ch-border bg-ch-surface p-xl"
        >
          <Skeleton type="detail" :rows="2" label="指标加载中" />
        </div>
      </div>
      <RecentTopics :topics="[]" loading />
      <SystemStatusBar loading />
    </template>

    <ErrorState
      v-else-if="error"
      :message="error"
      :detail="errorDetail"
      hint="工作台需并发读取主题 / 渲染任务 / 产物 / 凭据健康四类数据，请检查网络或稍后重试。"
      @retry="load"
    />

    <template v-else>
      <div class="grid grid-cols-1 gap-lg sm:grid-cols-2 min-[1360px]:grid-cols-4">
        <MetricCard v-for="card in metricCards" :key="card.key" v-bind="card" />
      </div>
      <RecentTopics :topics="recentTopics" @row-click="openTopic" />
      <SystemStatusBar
        :pending-count="pendingCount"
        :health="health"
        :health-checked-at="healthCheckedAt"
      />
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppButton from '@/components/base/AppButton.vue'
import Skeleton from '@/components/base/Skeleton.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import MetricCard from '@/views/dashboard/MetricCard.vue'
import RecentTopics from '@/views/dashboard/RecentTopics.vue'
import SystemStatusBar from '@/views/dashboard/SystemStatusBar.vue'
import { useDashboardData } from '@/views/dashboard/useDashboardData'

/** 指标卡数量（骨架屏按同一数量渲染，避免加载完成时栅格跳变） */
const METRIC_COUNT = 4

const router = useRouter()
const { loading, error, errorDetail, health, healthCheckedAt, counts, recentTopics, pendingCount, load } = useDashboardData()

/**
 * 4 张指标卡（数量 + 标签 + 图标 + 点击去向）。
 * ★ query 参数按计划口径原样传递；对应列表页的「筛选消费」属后续 Step（见交付说明清单）。
 * ★ 图标一律取自 §2.3.5 语义映射表：重试/重新渲染、合规校验、投递/推送、警告。
 */
const metricCards = computed(() => [
  {
    key: 'needRender',
    label: '待渲染',
    value: counts.value.needRender,
    icon: 'fa fa-rotate-right',
    tone: 'neutral',
    to: { path: '/topics', query: { needRender: '1' } }
  },
  {
    key: 'needCheck',
    label: '待校验',
    value: counts.value.needCheck,
    icon: 'fa fa-shield-halved',
    tone: 'neutral',
    to: { path: '/topics', query: { needCheck: '1' } }
  },
  {
    key: 'needPublish',
    label: '待投递',
    value: counts.value.needPublish,
    icon: 'fa fa-paper-plane',
    tone: 'neutral',
    to: { path: '/publish-records', query: { status: 'UNPUBLISHED' } }
  },
  {
    key: 'needRenderFailed',
    label: '渲染失败',
    value: counts.value.jobFailed,
    icon: 'fa fa-triangle-exclamation',
    tone: 'warning',
    to: { path: '/render-jobs', query: { jobStatus: 'FAILED' } }
  }
])

onMounted(load)

/** 新建主题：跳主题库并携带创建意图（P-02 消费 create=1，见交付说明的 query 清单） */
function goCreateTopic() {
  router.push({ path: '/topics', query: { create: '1' } })
}

/** 最近主题行点击：进入主题编辑（P-03 `/topics/:code`） */
function openTopic(topic) {
  if (!topic?.topicCode) return
  router.push({ name: 'TopicEdit', params: { code: topic.topicCode } })
}
</script>
