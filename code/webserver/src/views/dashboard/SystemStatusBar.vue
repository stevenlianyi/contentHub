<!-- ============================================================================
 * SystemStatusBar · 工作台「系统状态」条（Step 5 · P-01）
 * ----------------------------------------------------------------------------
 * ★ 形态硬约束（裁定 I）：**单行 inline 文本 + 状态点**；不做图表、不做进度条、不做百分比。
 *
 * 三项口径（一律以实际实现为准，不编造）：
 *   ① 渲染队列积压 = `renderjobqry` 中 `jobStatus === 'PENDING'` 的条数（0 为正常态）；
 *   ② 凭据健康     = `accounthealth` 出参 `data.healthSummary`，由 `useDashboardData.normalizeHealth()`
 *                    **归一为小写键**后传入（`{ total, ok, expiring, invalid, unknown }`）
 *                    → 显示 `ok/total 有效`；`invalid > 0` 时状态点转红并给出「去处理」；
 *                    ★ 本组件只认小写键契约，键名/大小写的差异收敛在 composable（P-ENV-01）；
 *                    ★ 2026-09-23 两处口径变更：
 *                      ① 「去处理」**按角色分流**——administrator / manager → `/accounts`（全量台账），
 *                         其他角色 → `/my-accounts`（本人账号）；避免非管理员点进 `/accounts` 落 403
 *                         （`/accounts` 的 `meta.roles` 仅 ROLES_SYSTEM）。
 *                      ② 工作台**不再触发巡检**（`useDashboardData` 不传 action）→ 本指标为
 *                         **快照**；用 `healthCheckedAt`（后端按归属收窄的最近一次巡检时间）
 *                         标注「截至 …」，**不得**暗示实时性。
 *   ③ 存储用量     = **本期无对应端点**（附录 B R-03），固定显示 `—（无数据源）`，不伪造数字。
 *
 * 三重编码（§2.6）：每项均为「形状图标 + 颜色 + 文字」，例如正常态 `fa-circle-check` 绿、
 *   积压态 `fa-clock` 橙、失效态 `fa-circle-xmark` 红、无数据源 `fa-regular fa-circle` 灰；
 *   灰度模式下三项仍可区分，不依赖颜色单维表达。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-md rounded-xl border border-ch-border bg-ch-surface p-xl">
    <h2 class="text-h2 text-ch-text-primary">系统状态</h2>

    <!-- 加载态形状对齐：最终形态为一行文本，故用 detail(1 行) 而非 table(表头 40 + 行 44) -->
    <Skeleton v-if="loading" type="detail" :rows="1" label="系统状态加载中" />

    <p v-else class="flex flex-wrap items-center gap-x-md gap-y-sm text-body-s text-ch-text-secondary">
      <span class="inline-flex items-center gap-xs">
        <i :class="[queueMeta.icon, queueMeta.colorClass]" aria-hidden="true"></i>
        渲染队列
        <span class="font-medium text-ch-text-primary">{{ pendingCount }} 积压</span>
      </span>

      <span class="text-ch-text-disabled" aria-hidden="true">·</span>

      <span class="inline-flex items-center gap-xs">
        <i :class="[healthMeta.icon, healthMeta.colorClass]" aria-hidden="true"></i>
        凭据健康
        <span class="font-medium text-ch-text-primary">{{ healthMeta.text }}</span>
        <!-- ★ 2026-09-23：工作台已不触发巡检 → 标注快照时点，不暗示实时 -->
        <span v-if="healthMeta.text !== '—'" class="text-ch-text-tertiary">{{ snapshotText }}</span>
      </span>

      <RouterLink
        v-if="healthMeta.hasInvalid"
        :to="accountEntryRoute"
        class="text-body-s text-ch-danger underline underline-offset-2"
      >
        去处理
      </RouterLink>

      <span class="text-ch-text-disabled" aria-hidden="true">·</span>

      <span class="inline-flex items-center gap-xs">
        <i class="fa-regular fa-circle text-ch-text-tertiary" aria-hidden="true"></i>
        存储
        <span class="text-ch-text-tertiary">—（无数据源）</span>
      </span>
    </p>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import Skeleton from '@/components/base/Skeleton.vue'
import { useUserStore } from '@/store/modules/user'
import { formatYMDHMS } from '@/utils/common'

const props = defineProps({
  /** `renderjobqry` 中 jobStatus === 'PENDING' 的条数 */
  pendingCount: { type: Number, default: 0 },
  /** `accounthealth` 归一化后的 `{ total, ok, expiring, invalid, unknown }`；未取到（如失败）时传 null */
  health: { type: Object, default: null },
  /** 凭据健康快照时点（14 位 `YYYYMMDDHHMMSS`；空串 = 从未巡检） */
  healthCheckedAt: { type: String, default: '' },
  loading: { type: Boolean, default: false }
})

const userStore = useUserStore()

/**
 * 「去处理」去向按角色分流（★ 2026-09-23）：
 *   · administrator / manager → `/accounts`（全量台账，`meta.roles = ROLES_SYSTEM`）；
 *   · 其他角色 → `/my-accounts`（本人账号，`meta.roles = ROLES_ACCOUNT_SELF`）。
 * ★ 鉴权只用 `hasRole()`：`hasPermission()` 恒为 false（后端不下发 permissions，见 store/modules/user.js）。
 */
const accountEntryRoute = computed(() =>
  userStore.hasRole(['administrator', 'manager']) ? '/accounts' : '/my-accounts'
)

/** 快照时点文案：非法 / 空 → 「— 尚未巡检」，**不编造时间** */
const snapshotText = computed(() => {
  const stamp = formatYMDHMS(props.healthCheckedAt, 'YYYY-MM-DD HH:mm')
  // 合法输入会被格式化（与原文不同）；非法输入 `formatYMDHMS` 原样返回 → 归为「尚未巡检」
  return stamp && stamp !== props.healthCheckedAt ? `（截至 ${stamp}）` : '（— 尚未巡检）'
})

/** 渲染队列：0 积压为正常态（绿 + fa-circle-check），否则待处理（橙 + fa-clock） */
const queueMeta = computed(() =>
  props.pendingCount === 0
    ? { icon: 'fa fa-circle-check', colorClass: 'text-ch-success' }
    : { icon: 'fa fa-clock', colorClass: 'text-ch-warning' }
)

/** 凭据健康：失效 > 即将过期 > 正常 > 未知（undefined 全部按未知处理） */
const healthMeta = computed(() => {
  const summary = props.health
  if (!summary) {
    return { icon: 'fa fa-circle-question', colorClass: 'text-ch-text-tertiary', text: '—', hasInvalid: false }
  }
  const total = Number(summary.total || 0)
  const ok = Number(summary.ok || 0)
  const expiring = Number(summary.expiring || 0)
  const invalid = Number(summary.invalid || 0)
  const text = total > 0 ? `${ok}/${total} 有效` : '—'
  if (invalid > 0) return { icon: 'fa fa-circle-xmark', colorClass: 'text-ch-danger', text, hasInvalid: true }
  if (expiring > 0) return { icon: 'fa fa-triangle-exclamation', colorClass: 'text-ch-warning', text, hasInvalid: false }
  return { icon: 'fa fa-circle-check', colorClass: 'text-ch-success', text, hasInvalid: false }
})
</script>
