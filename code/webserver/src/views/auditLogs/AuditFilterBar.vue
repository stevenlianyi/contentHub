<!-- ============================================================================
 * AuditFilterBar · P-12 审计日志筛选栏（Step 16 · 越界授权文件，裁定 J-②）
 * ----------------------------------------------------------------------------
 * 职责：时间范围（必填）+ 5 个主筛选 + 「更多筛选」（targetType / targetID）+ 查询 / 清空，
 *       并**作为 URL query 的唯一写入方**（裁定 D「所有条件写入 URL query，刷新/前进后退保持」）。
 *       取数、分页、表格、抽屉均在宿主页 `AuditLogs.vue`。
 *
 * 【后端事实（服从，不得凭计划文字臆断）】
 *   · 入参 = `actor / action / result / source / targetType / targetID / ipAddr /
 *     beginYMDHMS / endYMDHMS / order`（`crudApi.py::funcAuditlogQry`，附录 B R-28 + R-32）；
 *   · ★ **全部等值匹配**（`mysqlCommon.py::query_ch_audit_log:539-560` 一律 `condList.append([x,"=",x])`，
 *     无 keyword / 无模糊匹配）→ UI 不做「搜索」措辞、不做前缀/网段/本地过滤；
 *   · 时间条件作用在 `regYMDHMS`；`order:'desc'` → `ORDER BY recID DESC`（追加写日志最新在前，
 *     `mysqlCommon.py:290-295` 的「其他值」分支）；★ **禁止传 `'modify'`**（审计行 `modifyYMDHMS` 为空）。
 *
 * 【裁定 A · 时间范围必填（★ 前端约定，后端不强制）】
 *   · 进入页面默认**近 24 小时**并自动查询；一律转 14 位 `YYYYMMDDHHMMSS` 下发；
 *   · 任一为空 → **查询按钮禁用** + 提示「请选择时间范围（最长 90 天）」，且**不发请求**；
 *   · 跨度 > 90 天 → 提示并**阻止提交**（不截断、不静默改范围）；
 *   · ★ 该 90 天上限是**前端保护**（后端无此校验）：`ch_audit_log` 无 `regYMDHMS` 索引
 *     （建表后索引语句被注释，`mysqlCommon.py:4026-4027`）+ 数据层默认 `LIMIT 5000`
 *     （`_DEF_CH_AUDIT_LOG_QUERY_LIMIT_NUM`）→ 避免大表全扫。
 *
 * 【裁定 D】actor / ipAddr：等值输入框（placeholder 明示「需填写完整…」）；
 *   source：下拉三值 `web / api / mcp`；result：下拉 `OK / FAIL`；
 *   action：★ **不做封闭下拉**（后端无枚举接口、未来还会有新动作）→ 输入 + `datalist` 建议值
 *   （已知 5 个动作 ∪ 当前页出现过的 action）；targetType 同款处理（4 个已知取值 ∪ 当前页取值）。
 *   「清空筛选」只清上述条件、**保留时间范围**。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-md">
    <div class="flex flex-wrap items-end gap-md rounded-xl border border-ch-border bg-ch-surface px-xl py-lg">
      <label class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">开始时间（必填）</span>
        <input
          v-model="range.begin"
          type="datetime-local"
          step="1"
          class="h-9 rounded-lg border bg-ch-input px-sm text-body-s text-ch-text-primary"
          :class="rangeInvalid ? 'border-ch-danger' : 'border-ch-border'"
          aria-label="按审计时间筛选：开始时间（必填）"
          @change="apply()"
        />
      </label>

      <label class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">结束时间（必填）</span>
        <input
          v-model="range.end"
          type="datetime-local"
          step="1"
          class="h-9 rounded-lg border bg-ch-input px-sm text-body-s text-ch-text-primary"
          :class="rangeInvalid ? 'border-ch-danger' : 'border-ch-border'"
          aria-label="按审计时间筛选：结束时间（必填）"
          @change="apply()"
        />
      </label>

      <label class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">操作者</span>
        <input
          v-model="form.actor"
          type="text"
          placeholder="需填写完整 loginID"
          class="h-9 w-[200px] rounded-lg border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary placeholder:text-ch-text-tertiary"
          aria-label="按操作者筛选（等值，需填写完整 loginID）"
          @keydown.enter="apply()"
        />
      </label>

      <label class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">来源</span>
        <select
          v-model="form.source"
          class="h-9 w-[132px] rounded-lg border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
          aria-label="按来源筛选"
          @change="apply()"
        >
          <option value="">全部来源</option>
          <option v-for="value in SOURCE_ORDER" :key="value" :value="value">{{ SOURCE_LABEL[value] }}</option>
        </select>
      </label>

      <label class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">结果</span>
        <select
          v-model="form.result"
          class="h-9 w-[112px] rounded-lg border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
          aria-label="按结果筛选"
          @change="apply()"
        >
          <option value="">全部结果</option>
          <option value="OK">OK</option>
          <option value="FAIL">FAIL</option>
        </select>
      </label>

      <label class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">动作</span>
        <input
          v-model="form.action"
          type="text"
          list="ch-audit-action-options"
          placeholder="如 publish.push"
          class="h-9 w-[200px] rounded-lg border border-ch-border bg-ch-input px-sm font-mono text-code text-ch-text-primary placeholder:font-sans placeholder:text-body-s placeholder:text-ch-text-tertiary"
          aria-label="按动作筛选（等值，可输入或选建议值）"
          @keydown.enter="apply()"
        />
        <datalist id="ch-audit-action-options">
          <option v-for="value in actionOptions" :key="value" :value="value"></option>
        </datalist>
      </label>

      <label class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">来源 IP</span>
        <input
          v-model="form.ipAddr"
          type="text"
          placeholder="需填写完整 IP"
          class="h-9 w-[180px] rounded-lg border border-ch-border bg-ch-input px-sm font-mono text-code text-ch-text-primary placeholder:font-sans placeholder:text-body-s placeholder:text-ch-text-tertiary"
          aria-label="按来源 IP 筛选（等值，需填写完整 IP）"
          @keydown.enter="apply()"
        />
      </label>

      <div class="flex flex-wrap items-center gap-sm">
        <AppButton
          type="primary"
          size="md"
          icon="fa fa-magnifying-glass"
          :loading="loading"
          :disabled="!canQuery"
          :disabled-reason="queryDisabledReason"
          @click="apply()"
        >
          查询
        </AppButton>
        <AppButton
          size="md"
          icon="fa fa-eraser"
          :disabled="!hasFilters"
          disabled-reason="当前没有可清空的筛选条件（时间范围会被保留）"
          @click="clearFilters()"
        >
          清空筛选
        </AppButton>
        <AppButton size="md" icon="fa fa-clock" @click="useRecent24h()">近 24 小时</AppButton>
        <!-- 展开/收起由文案 + 箭头图标表达（AppButton 的根节点是 tooltip 包裹层，不承载 aria-expanded） -->
        <AppButton
          size="md"
          :icon="showMore ? 'fa fa-chevron-up' : 'fa fa-chevron-down'"
          @click="showMore = !showMore"
        >
          {{ showMore ? '收起更多筛选' : '更多筛选' }}
        </AppButton>
      </div>
    </div>

    <!-- 更多筛选（默认收起）：后端已支持，但日常排查用得少 -->
    <div
      v-if="showMore"
      class="flex flex-wrap items-end gap-md rounded-xl border border-ch-border bg-ch-surface px-xl py-lg"
    >
      <label class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">对象类型 targetType</span>
        <input
          v-model="form.targetType"
          type="text"
          list="ch-audit-targettype-options"
          placeholder="如 ch_publish_record"
          class="h-9 w-[240px] rounded-lg border border-ch-border bg-ch-input px-sm font-mono text-code text-ch-text-primary placeholder:font-sans placeholder:text-body-s placeholder:text-ch-text-tertiary"
          aria-label="按对象类型筛选（等值）"
          @keydown.enter="apply()"
        />
        <datalist id="ch-audit-targettype-options">
          <option v-for="value in targetTypeOptions" :key="value" :value="value"></option>
        </datalist>
      </label>

      <label class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">对象 ID targetID</span>
        <input
          v-model="form.targetID"
          type="text"
          placeholder="需填写完整 ID（目标表 recID）"
          class="h-9 w-[240px] rounded-lg border border-ch-border bg-ch-input px-sm font-mono text-code text-ch-text-primary placeholder:font-sans placeholder:text-body-s placeholder:text-ch-text-tertiary"
          aria-label="按对象 ID 筛选（等值）"
          @keydown.enter="apply()"
        />
      </label>
    </div>

    <p v-if="invalidReason === 'range-missing'" class="text-body-s text-ch-danger" role="alert">
      请选择时间范围（最长 90 天）：开始与结束时间均为必填，清空后<b>不会发起请求</b>（避免大表全扫）。
    </p>

    <p v-else-if="invalidReason === 'range-too-long'" class="text-body-s text-ch-danger" role="alert">
      所选时间跨度为 {{ spanDaysText }} 天，超过 90 天上限，已阻止提交：请缩小时间范围后重试
      （前端保护，不截断、不静默改范围；后端无此校验，且审计表无 regYMDHMS 索引）。
    </p>

    <p class="text-caption text-ch-text-tertiary">
      筛选与排序全部由服务端 `auditlogqry` 执行：时间条件作用于 `regYMDHMS`，其余条件均为<b>等值匹配</b>
      （后端无 keyword / 无模糊匹配）；`order='desc'` → `ORDER BY recID DESC`（追加写日志最新在前）。
      默认近 24 小时；90 天上限为前端保护（后端无校验）；来源 IP 与时间范围需同时使用（`ipAddr` 无索引）。
    </p>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppButton from '@/components/base/AppButton.vue'

/** 来源三值（`processor/auditService.py:74-78`：web / api / mcp，**没有 system**） */
const SOURCE_ORDER = ['web', 'api', 'mcp']
const SOURCE_LABEL = { web: 'Web', api: 'API', mcp: 'MCP' }

/**
 * 已知动作（`auditService.py:66-72` 的 5 个常量；★ 不做封闭下拉，仅作 `datalist` 建议值 ——
 * 后端无枚举接口，未来还会新增动作，封闭下拉会把新动作筛掉）。
 */
const KNOWN_ACTIONS = [
  'publish.push',
  'publish.revoke',
  'publish.confirm',
  'archive.audit_log',
  'archive.artifact_purge'
]

/** 已知对象类型（`auditService.py:86-90` 的 4 个常量；同样只作建议值） */
const KNOWN_TARGET_TYPES = ['ch_publish_record', 'ch_account', 'ch_audit_log', 'ch_artifact']

/** 时间范围上限（天）：★ 前端保护，后端无此校验 */
const MAX_RANGE_DAYS = 90

const props = defineProps({
  /** 请求进行中：禁用查询/清空等触发动作 */
  loading: { type: Boolean, default: false },
  /** 当前页码（宿主页持有）：写 URL query 的 page 时使用 */
  currentPage: { type: [Number, String], default: 1 },
  /** 当前页数据里出现过的 action / targetType（并入 datalist 建议值） */
  seenActions: { type: Array, default: () => [] },
  seenTargetTypes: { type: Array, default: () => [] }
})

const emit = defineEmits(['apply'])

const route = useRoute()
const router = useRouter()

const range = reactive({ begin: '', end: '' })
const form = reactive({
  actor: '',
  source: '',
  result: '',
  action: '',
  ipAddr: '',
  targetType: '',
  targetID: ''
})
const showMore = ref(false)

/* ------------------------------ 时间换算 ------------------------------ */

const pad2 = (value) => String(value).padStart(2, '0')

/** Date → `datetime-local` 控件值 `YYYY-MM-DDTHH:mm:ss` */
const toInputValue = (date) =>
  `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}` +
  `T${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}`

/** 控件值 / URL 值 → 14 位 `YYYYMMDDHHMMSS`（缺秒补 `00`，缺时间补 `000000`） */
function toYMDHMS(value) {
  const digits = String(value || '').replace(/\D/g, '')
  if (digits.length >= 14) return digits.slice(0, 14)
  if (digits.length === 12) return `${digits}00`
  if (digits.length === 8) return `${digits}000000`
  return ''
}

/** 14 位 / 8 位 → `datetime-local` 控件值（用于 URL 回填） */
function toInputFromYMDHMS(value) {
  const digits = String(value || '').replace(/\D/g, '')
  if (digits.length === 14) {
    return `${digits.slice(0, 4)}-${digits.slice(4, 6)}-${digits.slice(6, 8)}T` +
      `${digits.slice(8, 10)}:${digits.slice(10, 12)}:${digits.slice(12, 14)}`
  }
  if (digits.length === 8) return `${digits.slice(0, 4)}-${digits.slice(4, 6)}-${digits.slice(6, 8)}T00:00:00`
  return ''
}

const beginYMDHMS = computed(() => toYMDHMS(range.begin))
const endYMDHMS = computed(() => toYMDHMS(range.end))
const rangeMissing = computed(() => !beginYMDHMS.value || !endYMDHMS.value)

/** 跨度（天，含小数）；任一为空或解析失败返回 0 */
const spanDays = computed(() => {
  const begin = beginYMDHMS.value
  const end = endYMDHMS.value
  if (!begin || !end || !toInputFromYMDHMS(begin) || !toInputFromYMDHMS(end)) return 0
  const b = new Date(toInputFromYMDHMS(begin))
  const e = new Date(toInputFromYMDHMS(end))
  const diff = (e.getTime() - b.getTime()) / 86400000
  return Number.isFinite(diff) && diff > 0 ? diff : 0
})

const spanDaysText = computed(() => (spanDays.value ? spanDays.value.toFixed(1) : String(spanDays.value)))
const rangeTooLong = computed(() => spanDays.value > MAX_RANGE_DAYS)

/** `''` | `range-missing` | `range-too-long` */
const invalidReason = computed(() => {
  if (rangeMissing.value) return 'range-missing'
  if (rangeTooLong.value) return 'range-too-long'
  return ''
})
const rangeInvalid = computed(() => invalidReason.value !== '')

/** 除时间范围外的条件（用于「有筛选」空态文案与「清空筛选」可用性） */
const hasFilters = computed(() =>
  Boolean(
    form.actor || form.source || form.result || form.action || form.ipAddr || form.targetType || form.targetID
  )
)

const canQuery = computed(() => invalidReason.value === '' && !props.loading)
const queryDisabledReason = computed(() => {
  if (props.loading) return '查询进行中，请稍候'
  if (invalidReason.value === 'range-missing') return '请选择时间范围（最长 90 天）'
  if (invalidReason.value === 'range-too-long') return `时间跨度超过 ${MAX_RANGE_DAYS} 天，已阻止提交`
  return ''
})

/** `datalist` 建议值 = 已知取值 ∪ 当前页出现过的取值（去重、非空、稳定顺序） */
const actionOptions = computed(() =>
  Array.from(new Set([...KNOWN_ACTIONS, ...props.seenActions.map((item) => String(item || '')).filter(Boolean)]))
)
const targetTypeOptions = computed(() =>
  Array.from(
    new Set([...KNOWN_TARGET_TYPES, ...props.seenTargetTypes.map((item) => String(item || '')).filter(Boolean)])
  )
)

/* ------------------------------ 请求参数与 URL ------------------------------ */

/**
 * 请求参数（与 `funcAuditlogQry` 逐字对齐）。
 * ★ `mode: 'full'`：`ch_audit_log` 的 short 列清单不含 `payloadDigest / ipAddr / memo / errMsg`
 *   （`mysqlCommon.CH_QUERY_SHORT_COLUMNS:330`）→ P-12 必须取 full。
 * ★ `order: 'desc'`：命中数据层「其他值 → ORDER BY recID DESC」（最新在前）；**禁止 `'modify'`**。
 * ★ 分页 `beginNum / endNum` 由宿主页（usePagination）显式补齐，此处不提供。
 */
function buildParams() {
  return {
    ...(form.actor ? { actor: form.actor.trim() } : {}),
    ...(form.source ? { source: form.source } : {}),
    ...(form.result ? { result: form.result } : {}),
    ...(form.action ? { action: form.action.trim() } : {}),
    ...(form.ipAddr ? { ipAddr: form.ipAddr.trim() } : {}),
    ...(form.targetType ? { targetType: form.targetType.trim() } : {}),
    ...(form.targetID ? { targetID: form.targetID.trim() } : {}),
    ...(rangeMissing.value ? {} : { beginYMDHMS: beginYMDHMS.value, endYMDHMS: endYMDHMS.value }),
    order: 'desc',
    mode: 'full'
  }
}

/** 写 URL query（本组件是唯一写入方；`keepPage` 仅分页变化时为 true） */
function writeQuery(keepPage = false) {
  router.replace({
    path: route.path,
    query: {
      ...route.query,
      beginYMDHMS: beginYMDHMS.value || undefined,
      endYMDHMS: endYMDHMS.value || undefined,
      actor: form.actor.trim() || undefined,
      source: form.source || undefined,
      result: form.result || undefined,
      action: form.action.trim() || undefined,
      ipAddr: form.ipAddr.trim() || undefined,
      targetType: form.targetType.trim() || undefined,
      targetID: form.targetID.trim() || undefined,
      // 筛选条件变化即回到第 1 页；只有分页变化才保留 page
      page: keepPage && Number(props.currentPage) > 1 ? String(props.currentPage) : undefined
    }
  })
}

/** 从 URL query 回填（刷新 / 前进后退）；时间范围缺失时回落**近 24 小时** */
function readQuery() {
  const q = route.query
  const fallback = recent24h()
  range.begin = toInputFromYMDHMS(q.beginYMDHMS) || fallback.begin
  range.end = toInputFromYMDHMS(q.endYMDHMS) || fallback.end
  form.actor = String(q.actor || '')
  form.source = String(q.source || '')
  form.result = String(q.result || '')
  form.action = String(q.action || '')
  form.ipAddr = String(q.ipAddr || '')
  form.targetType = String(q.targetType || '')
  form.targetID = String(q.targetID || '')
  showMore.value = Boolean(form.targetType || form.targetID)
}

/** 近 24 小时（默认值，裁定 A） */
function recent24h() {
  const now = new Date()
  return { begin: toInputValue(new Date(now.getTime() - 24 * 3600 * 1000)), end: toInputValue(now) }
}

/**
 * 提交查询：非法（缺时间范围 / 超 90 天）→ 写 URL + 通知宿主「不发请求」。
 * ★ `keepPage`：**进入页面的首次** apply 要保留 URL 里的 `page`（刷新后仍停在同一页）；
 *   之后任何条件变化一律回到第 1 页（写 query 时清掉 `page`）。
 */
let firstApplyDone = false
function apply() {
  writeQuery(!firstApplyDone)
  firstApplyDone = true
  emit('apply', {
    params: invalidReason.value ? null : buildParams(),
    invalidReason: invalidReason.value,
    hasFilters: hasFilters.value
  })
}

/** 清空筛选：只清条件，**保留时间范围**（裁定 D） */
function clearFilters() {
  form.actor = ''
  form.source = ''
  form.result = ''
  form.action = ''
  form.ipAddr = ''
  form.targetType = ''
  form.targetID = ''
  apply()
}

/** 回到近 24 小时（仅改时间范围，其余条件保留） */
function useRecent24h() {
  const preset = recent24h()
  range.begin = preset.begin
  range.end = preset.end
  apply()
}

/** 供宿主页在分页变化后把 page 写进 URL（本组件是 URL query 唯一写入方） */
function syncQuery() {
  writeQuery(true)
}

defineExpose({ apply, clearFilters, syncQuery, readQuery })

onMounted(() => {
  readQuery()
  apply() // 进入页面即按默认近 24 小时自动查询（裁定 A）
})
</script>
