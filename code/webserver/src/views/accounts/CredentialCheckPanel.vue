<!-- ============================================================================
 * CredentialCheckPanel · P-11 凭据健康巡检面板（Step 15）
 * ----------------------------------------------------------------------------
 * 【后端事实（一律服从源码）】
 *   · 触发：`accounthealth({ action:'check' })` —— `check` / `refresh` / `probe` **完全等价**
 *     （`subfunc/accountApi.py:818-825` 同一 `runOnce` 调用，参数均为 `{accountID, platform}`）
 *     → 本组件只发 `check`；`action` 为空 = **只汇总不巡检**（出参无 `credentialCheck`）。
 *   · 出参为 copy 域（P-ENV-01）：业务字段在 `data` 内。
 *     `data.healthSummary`（★ **状态计数键为「大写」**，四个状态键与
 *     `config/chOptions.HEALTH_STATUS_MAP` 完全一致，另含 `total`）；
 *     `data.credentialCheck` 仅在 action 非空时存在。
 *   · `credentialCheck`（`schedule/credentialCheck.py::runOnce`）字段：
 *     `total / checked / ok / expiring / invalid / unknown / skipped / degraded / warnDays /
 *      items[] / alertSummary / checkedAt`；
 *     · 锁未取到 → `skipped = -1` + `msg`（**非错误态**，本轮只是没跑）；
 *     · Redis 不可用 → `degraded = 1`（**非错误态**，降级运行）；
 *     · `items[]` 每项 `{ accountID, accountCode, platform, healthStatus, probed, alertLevel, errMsg,
 *       skipReason }` —— ★ **不含 `accountName`** → 用列表数据把 `accountCode` 映射为 `accountName`，
 *       映射不到（不在当前页）就显示 `accountCode`，绝不编造账号名；
 *     · 小红书 / 通用平台**跳过并给出原因原文**（`SKIP_PLATFORM_NOTE_MAP`）→ **直出 `skipReason`**，
 *       前端不自编文案、不报错；
 *     · `alertLevel ∈ {INFO, WARN, ERROR}`（`ALERT_LEVEL_MAP`）→ 中性 / 橙 / 红（图标 + 颜色 + 文字）。
 *   · `healthSummary` 由 `useDashboardData.normalizeHealth()` 归一小写键后传入（R-27 / P-ENV-01），
 *     本组件只认小写键契约。
 *   · ★ `UNKNOWN`（平台配置缺失 / 适配器未实现）用**灰色**，与「已失效」语义不同，不得混用。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-lg rounded-xl border border-ch-border bg-ch-surface p-xl">
    <header class="flex flex-wrap items-start justify-between gap-md">
      <div class="flex min-w-0 flex-col gap-xs">
        <h2 class="text-h2 text-ch-text-primary">凭据健康巡检</h2>
        <p class="text-body-s text-ch-text-secondary">
          只读探活：不投递、不发布。巡检会回写 healthStatus 与 lastCheckYMDHMS；
          小红书 / 通用平台无平台凭据，会跳过并给出后端原因原文（不是失败）。
        </p>
      </div>
      <AppButton
        icon="fa fa-rotate-right"
        :loading="checking"
        :disabled="checking"
        :disabled-reason="checking ? '已有巡检在执行，请稍候' : ''"
        @click="emit('check')"
      >
        立即巡检
      </AppButton>
    </header>

    <ErrorState
      v-if="error"
      :message="error"
      hint="巡检未取到结果：请确认会话有效后重试；列表数据不受影响。"
      @retry="emit('check')"
    />

    <!-- 非错误态提示（不得当失败展示）：notice 来自宿主页（如响应缺 credentialCheck） -->
    <ConflictBanner v-if="notice" type="info" title="巡检已触发，但无明细">{{ notice }}</ConflictBanner>
    <ConflictBanner v-if="isSkipped" type="info" title="已有巡检在执行，本轮跳过">
      skipped = -1：本轮未执行任何探活（不是失败，也未改写任何账号的健康状态）
      <template v-if="result?.msg">；后端原文：{{ result.msg }}</template>。
    </ConflictBanner>
    <ConflictBanner v-if="isDegraded" type="info" title="巡检锁 / 计数已降级（Redis 不可用）">
      degraded = 1：本轮仍在执行，但互斥锁与计数走降级路径，结果可能不完整；请恢复 Redis 后重跑一次。
    </ConflictBanner>

    <Skeleton v-if="checking && !result" type="detail" :rows="3" label="巡检执行中" />

    <!-- ① healthSummary（归一为小写键后渲染） -->
    <div class="flex flex-col gap-sm">
      <h3 class="text-h3 text-ch-text-primary">健康汇总（healthSummary）</h3>
      <p v-if="!normalizedSummary" class="text-body-s text-ch-text-tertiary">
        —（暂未取到健康汇总：accounthealth 返回 healthSummary 后显示；不编造 0 值）
      </p>
      <p v-else class="flex flex-wrap items-center gap-x-lg gap-y-sm text-body-s text-ch-text-secondary">
        <span v-for="row in summaryRows" :key="row.key" class="inline-flex items-center gap-xs">
          <StateBadge domain="health" :status="row.status" />
          <span class="font-medium text-ch-text-primary">{{ row.text }}</span>
        </span>
      </p>
    </div>

    <!-- ② credentialCheck 统计 -->
    <div class="flex flex-col gap-sm">
      <h3 class="text-h3 text-ch-text-primary">巡检统计（credentialCheck）</h3>
      <p v-if="scopeNote" class="text-body-s text-ch-info">{{ scopeNote }}</p>
      <p v-if="!result" class="text-body-s text-ch-text-tertiary">
        —（尚未执行巡检：点击「立即巡检」后显示；action 为空时后端只汇总不巡检）
      </p>
      <dl v-else class="grid grid-cols-2 gap-x-lg gap-y-sm md:grid-cols-4 xl:grid-cols-5">
        <div v-for="item in statItems" :key="item.key" class="flex flex-col">
          <dt class="text-caption text-ch-text-tertiary">{{ item.label }}</dt>
          <dd class="text-body font-medium text-ch-text-primary">{{ item.value }}</dd>
        </div>
      </dl>
    </div>

    <!-- ③ items[] 明细（列：账号 / 平台 / 探活 / 健康 / 告警级别 / 说明） -->
    <div class="flex flex-col gap-sm">
      <h3 class="text-h3 text-ch-text-primary">逐账号明细（credentialCheck.items[]）</h3>
      <p class="text-caption text-ch-text-tertiary">
        账号名由列表数据按 accountCode 映射（items 不含 accountName）；不在当前页的账号显示 accountCode。
        跳过项直接展示后端 skipReason 原文。
      </p>
      <AppTable
        :columns="ITEM_COLUMNS"
        :rows="items"
        :loading="checking && !result"
        row-key="accountCode"
        row-height="compact"
        empty="本轮巡检无可展示的账号明细"
        :empty-description="result?.skipped === -1 ? '本轮巡检被跳过（已有巡检在执行）。' : '巡检未返回明细项。'"
      >
        <template #cell-account="{ row }">
          <div class="flex min-w-0 flex-col">
            <span class="truncate text-body-s text-ch-text-primary" :title="accountText(row)">{{ accountText(row) }}</span>
            <span class="truncate font-mono text-code text-ch-text-tertiary">{{ row.accountCode || '—' }}</span>
          </div>
        </template>

        <template #cell-platform="{ row }">
          <PlatformChip :platform="String(row.platform || '')" size="sm" />
        </template>

        <template #cell-probed="{ row }">
          <span class="inline-flex items-center gap-xs text-body-s text-ch-text-secondary">
            <i :class="row.probed ? 'fa fa-circle-check' : 'fa-regular fa-circle'" aria-hidden="true"></i>
            {{ row.probed ? '是' : '否' }}
          </span>
        </template>

        <template #cell-healthStatus="{ row }">
          <StateBadge domain="health" :status="row.healthStatus || 'UNKNOWN'" />
        </template>

        <template #cell-alertLevel="{ row }">
          <span class="inline-flex items-center gap-xs whitespace-nowrap text-body-s" :class="alertMeta(row.alertLevel).class">
            <i :class="alertMeta(row.alertLevel).icon" aria-hidden="true"></i>
            <span>{{ alertMeta(row.alertLevel).text }}</span>
          </span>
        </template>

        <template #cell-note="{ row }">
          <span class="block text-body-s" :class="row.skipReason ? 'text-ch-text-secondary' : 'text-ch-text-tertiary'">
            {{ noteText(row) }}
          </span>
        </template>
      </AppTable>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import AppButton from '@/components/base/AppButton.vue'
import AppTable from '@/components/base/AppTable.vue'
import ConflictBanner from '@/components/base/ConflictBanner.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import Skeleton from '@/components/base/Skeleton.vue'
import PlatformChip from '@/components/biz/PlatformChip.vue'
import StateBadge from '@/components/biz/StateBadge.vue'
import { formatYMDHMS } from '@/utils/common'

const props = defineProps({
  /** `normalizeHealth()` 归一后的小写键汇总 `{ total, ok, expiring, invalid, unknown }`；未取到传 null */
  summary: { type: Object, default: null },
  /** `data.credentialCheck`（`runOnce` 同构对象）；未巡检传 null */
  result: { type: Object, default: null },
  /** 列表当前页（用于 accountCode → accountName 映射） */
  accounts: { type: Array, default: () => [] },
  checking: { type: Boolean, default: false },
  error: { type: String, default: '' },
  /** 宿主页的补充说明（如响应缺 credentialCheck 明细） */
  notice: { type: String, default: '' },
  /** 单账号巡检时的收窄说明（明细仅含该账号；healthSummary 仍为全量） */
  scopeNote: { type: String, default: '' }
})

const emit = defineEmits(['check'])

/**
 * 明细列（探活 = probed → 是/否；说明 = skipReason 原文优先，其次 errMsg）。
 * ★ 2026-09-24：平台列 132 —— `PlatformChip` 为原子标识（`shrink-0 + whitespace-nowrap`，
 *   实测 94（微信公众号）/ 95（通用HTML，最长）），列宽须 ≥ 95 + 单元格内边距 16×2 = 127，
 *   否则胶囊右侧会被 `.cell` 的 `overflow:hidden` 切掉（内边距口径见 `styles/element-vars.css` ④）。
 */
const ITEM_COLUMNS = [
  { key: 'account', title: '账号', minWidth: 176 },
  { key: 'platform', title: '平台', width: 132 },
  { key: 'probed', title: '探活', width: 80 },
  { key: 'healthStatus', title: '健康', width: 120 },
  { key: 'alertLevel', title: '告警级别', width: 132 },
  { key: 'note', title: '说明', minWidth: 220 }
]

/** 汇总行顺序与口径（★ 状态键在此派生，避免在正文里写死状态取值） */
const SUMMARY_ORDER = [
  { key: 'ok', mode: 'ratio' },
  { key: 'expiring', mode: 'count' },
  { key: 'invalid', mode: 'count' },
  { key: 'unknown', mode: 'count' }
]

const normalizedSummary = computed(() => (props.summary && typeof props.summary === 'object' ? props.summary : null))

const summaryRows = computed(() => {
  const data = normalizedSummary.value
  if (!data) return []
  return SUMMARY_ORDER.map(({ key, mode }) => ({
    key,
    // 小写键 → 大写状态键，与 config/chOptions.HEALTH_STATUS_MAP 同形
    status: key.toUpperCase(),
    text: mode === 'ratio' ? `${Number(data.ok) || 0}/${Number(data.total) || 0}` : String(Number(data[key]) || 0)
  }))
})

const isSkipped = computed(() => Number(props.result?.skipped) === -1)
const isDegraded = computed(() => Number(props.result?.degraded) === 1)

const statItems = computed(() => {
  const data = props.result
  if (!data) return []
  const num = (value) => String(Number(value) || 0)
  const stat = (key, label) => ({ key, label, value: num(data[key]) })
  return [
    stat('total', '巡检账号数'),
    stat('checked', '已探活'),
    stat('ok', '有效'),
    stat('expiring', '即将过期'),
    stat('invalid', '已失效'),
    stat('unknown', '未知'),
    { key: 'skipped', label: '跳过', value: Number(data.skipped) === -1 ? '-1（本轮跳过）' : num(data.skipped) },
    { key: 'degraded', label: '降级', value: num(data.degraded) },
    { key: 'warnDays', label: '预警阈值', value: `${Number(data.warnDays) || 0} 天` },
    { key: 'checkedAt', label: '巡检时间', value: data.checkedAt ? formatYMDHMS(data.checkedAt) : '—' }
  ]
})

const items = computed(() => (Array.isArray(props.result?.items) ? props.result.items : []))

/** accountCode → accountName（仅用列表白名单字段；映射不到回落 accountCode） */
const nameMap = computed(() => {
  const map = new Map()
  props.accounts.forEach((row) => {
    const code = String(row?.accountCode || '')
    if (code) map.set(code, String(row.accountName || ''))
  })
  return map
})

const accountText = (item) => nameMap.value.get(String(item?.accountCode || '')) || String(item?.accountCode || '—')

/** 告警级别三重编码（中性 / 橙 / 红）；未知取值兜底中性，不猜语义 */
const ALERT_LEVEL_META = {
  INFO: { label: '中性', icon: 'fa fa-circle-info', class: 'text-ch-text-secondary' },
  WARN: { label: '警告', icon: 'fa fa-triangle-exclamation', class: 'text-ch-warning' },
  ERROR: { label: '阻断', icon: 'fa fa-circle-xmark', class: 'text-ch-danger' }
}

function alertMeta(level) {
  const raw = String(level || '').toUpperCase()
  const meta = ALERT_LEVEL_META[raw]
  if (!meta) return { text: raw || '—', icon: 'fa-regular fa-circle', class: 'text-ch-text-secondary' }
  return { text: `${raw} · ${meta.label}`, icon: meta.icon, class: meta.class }
}

/** 说明列：跳过原因**原文优先**，其次错误原文，都空显示 `—` */
function noteText(item) {
  return String(item?.skipReason || '').trim() || String(item?.errMsg || '').trim() || '—'
}
</script>
