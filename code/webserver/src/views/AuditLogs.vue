<!-- ============================================================================
 * AuditLogs · P-12 审计日志（Step 16，原地替换 Step 7 占位页）
 * ----------------------------------------------------------------------------
 * 页面职责（只做编排；筛选栏在 `views/auditLogs/AuditFilterBar.vue`，明细抽屉在
 * `views/auditLogs/AuditPayloadDrawer.vue`）：
 *   ① 筛选栏（时间范围必填 + 等值筛选 + URL query）→ 本页监听 `apply` 事件后取数；
 *   ② 服务端分页（`beginNum` / `endNum` + `total`；默认每页 **50**，档位 `[20,50,100]`）；
 *   ③ 表格（行高 36px 紧凑）+ 三态（loading / error / empty）；
 *   ④ 明细抽屉（点击行内 `payloadDigest` 打开）。
 *
 * 【后端事实（服从）】
 *   · 端点 `auditlogqry`（`crudApi.py::funcAuditlogQry`）：入参 `actor / action / result / source /
 *     targetType / targetID / ipAddr / beginYMDHMS / endYMDHMS / order`，**全部等值匹配**
 *     （`mysqlCommon.query_ch_audit_log` 一律 `condList.append([x,"=",x])`，**无 keyword**）；
 *   · 时间条件作用在 `regYMDHMS`；`order:'desc'` 命中「其他值 → `ORDER BY recID DESC`」
 *     （`mysqlCommon.py:290-295`，追加写日志最新在前）；★ **不传 `'modify'`**（审计行 `modifyYMDHMS` 为空）；
 *   · ★ 分页**必须显式传** `beginNum` / `endNum`：通用查询缓冲缺省 `endNum = 9999`
 *     （`globalDefinition.py:192-193`），不传会一次拉近万条；
 *   · `mode: 'full'`：`ch_audit_log` 的 short 列清单
 *     （`mysqlCommon.CH_QUERY_SHORT_COLUMNS:330`）不含 `payloadDigest / ipAddr / memo / errMsg`；
 *   · `ch_audit_log` **无 `payload` 列** → 抽屉只展示 `payloadDigest`（摘要不落库、不可还原）；
 *   · 后端目前只写 5 类动作（`processor/auditService.py:66-72`）：`publish.push` / `publish.revoke` /
 *     `publish.confirm` / `archive.audit_log` / `archive.artifact_purge`；`source ∈ {web, api, mcp}`
 *     （**无 system**）；`result ∈ {OK, FAIL}`；`targetType ∈ {ch_publish_record, ch_account,
 *     ch_audit_log, ch_artifact}` —— 主题 / 素材 / 渲染 / 账号域**当前都不写审计**；
 *   · `auditlogqry` **不是免登录端点** → 请求必须带 `sessionID`（`utils/http.js` 统一注入）。
 *
 * ★ 本期**不提供任何前端导出 / 下载入口**（归档与导出走后端 `schedule/archive.py`，属破坏性/大批量
 *   操作）→ 已登记为待确认项；页面不出现导出按钮，也不提供「全部加载 / 每页 9999」入口。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-lg">
    <header class="flex flex-col gap-xs">
      <h1 class="text-h1 text-ch-text-primary">审计日志</h1>
      <p class="text-body-s text-ch-text-secondary">
        有副作用的关键动作留痕（追加写、不可改删）。当前仅
        <span class="font-mono text-code">publish.push</span> /
        <span class="font-mono text-code">publish.revoke</span> /
        <span class="font-mono text-code">publish.confirm</span> /
        <span class="font-mono text-code">archive.*</span> 动作会写审计；筛选一律为<b>等值匹配</b>
        （后端无模糊搜索），时间条件作用于 <span class="font-mono text-code">regYMDHMS</span>。
        ★ 入参不落库：仅保留脱敏后的 sha256 摘要；本页不提供导出 / 下载入口（归档走后端定时任务）。
      </p>
    </header>

    <AuditFilterBar
      ref="filterBarRef"
      :loading="loading"
      :current-page="page"
      :seen-actions="seenActions"
      :seen-target-types="seenTargetTypes"
      @apply="onFilterApply"
    />

    <!-- 错误态：原因 + 重试 + 详情（★ 不允许空白） -->
    <ErrorState
      v-if="error"
      :message="error"
      :detail="errorDetail"
      hint="审计日志读取失败：请检查网络与会话是否有效后重试；若筛选条件过宽，可缩小时间范围再试。"
      @retry="retry()"
    />

    <template v-else>
      <div class="flex flex-wrap items-center justify-between gap-sm">
        <p class="text-caption text-ch-text-tertiary">
          共 {{ total }} 条；服务端分页（每页 {{ size }} 条，默认 50）· 排序
          <span class="font-mono text-code">recID DESC</span>（最新在前）·
          <span class="font-mono text-code">mode=full</span>
        </p>
        <AppButton size="sm" icon="fa fa-rotate-right" :loading="loading" @click="refresh(true)">刷新</AppButton>
      </div>

      <AppTable
        :columns="columns"
        :rows="rows"
        :loading="loading"
        :empty="emptyText.title"
        :empty-description="emptyText.description"
        :empty-action-text="emptyText.actionText"
        row-height="compact"
        row-key="recID"
        @empty-action="onEmptyAction"
      >
        <template #cell-regYMDHMS="{ row }">
          <span class="tabular-nums" :title="String(row.regYMDHMS || '')">
            {{ row.regYMDHMS ? formatYMDHMS(row.regYMDHMS) : '—' }}
          </span>
        </template>

        <template #cell-actor="{ row }">
          <span class="font-mono text-code text-ch-text-primary">{{ row.actor || '—' }}</span>
        </template>

        <!-- 来源：`SourceTag` 渲染（web/api/mcp）；★ 未知值或空值不硬塞成 System -->
        <template #cell-source="{ row }">
          <SourceTag v-if="row.source" :source="String(row.source)" />
          <span v-else class="text-ch-text-tertiary">—</span>
        </template>

        <template #cell-action="{ row }">
          <span class="font-mono text-code text-ch-text-primary">{{ row.action || '—' }}</span>
        </template>

        <template #cell-target="{ row }">
          <span
            v-if="row.targetType || row.targetID"
            class="flex min-w-0 flex-col gap-xs"
            :title="`${row.targetType || '—'} ${row.targetID || '—'}`"
          >
            <span class="truncate text-caption text-ch-text-secondary">{{ row.targetType || '—' }}</span>
            <span class="truncate font-mono text-code text-ch-text-primary">{{ row.targetID || '—' }}</span>
          </span>
          <span v-else class="text-ch-text-tertiary">—</span>
        </template>

        <!-- 结果：形状图标 + 颜色 + 文字（三重编码；OK 绿 / FAIL 红，未知值兜底） -->
        <template #cell-result="{ row }">
          <span
            class="inline-flex items-center gap-xs whitespace-nowrap text-caption"
            :style="{ color: resultMeta(row).color }"
            :aria-label="`结果：${resultMeta(row).label}`"
          >
            <i :class="resultMeta(row).icon" aria-hidden="true"></i>
            <span>{{ resultMeta(row).label }}</span>
          </span>
        </template>

        <template #cell-costMs="{ row }">
          <span class="tabular-nums text-ch-text-secondary">{{ costText(row.costMs) }}</span>
        </template>

        <template #cell-ipAddr="{ row }">
          <span class="font-mono text-code text-ch-text-secondary">{{ row.ipAddr || '—' }}</span>
        </template>

        <!-- 入参摘要：点击打开明细抽屉（★ 只读摘要，不拼接/不还原 payload） -->
        <template #cell-payloadDigest="{ row }">
          <button
            v-if="row.payloadDigest"
            type="button"
            class="inline-flex min-w-0 max-w-full items-center gap-sm rounded-sm px-xs py-[2px] font-mono text-code text-ch-primary transition-colors duration-150 ease-out hover:bg-ch-hover"
            :title="String(row.payloadDigest)"
            :aria-label="`查看审计明细（入参摘要 ${row.payloadDigest}）`"
            @click="openDrawer(row)"
          >
            <i class="fa fa-list-check" aria-hidden="true"></i>
            <span class="truncate">{{ truncateString(String(row.payloadDigest), 12) }}</span>
          </button>
          <span v-else class="text-ch-text-tertiary">—</span>
        </template>
      </AppTable>

      <AppPagination
        :total="total"
        :page-size="size"
        :current-page="page"
        :page-sizes="PAGE_SIZES"
        :disabled="loading"
        @page-change="onPageChange"
      />
    </template>

    <AuditPayloadDrawer v-model="drawerOpen" :record="activeRecord" />
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '@/components/base/AppButton.vue'
import AppPagination from '@/components/base/AppPagination.vue'
import AppTable from '@/components/base/AppTable.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import SourceTag from '@/components/base/SourceTag.vue'
import AuditFilterBar from '@/views/auditLogs/AuditFilterBar.vue'
import AuditPayloadDrawer from '@/views/auditLogs/AuditPayloadDrawer.vue'
import { tokens } from '@/js/tokens'
import { auditLogQry } from '@/api/audit'
import { formatYMDHMS, truncateString } from '@/utils/common'
import { usePagination } from '@/components/base/composables/usePagination'

/** 每页档位（默认 50；★ 不提供「全部加载 / 每页 9999」） */
const PAGE_SIZES = [20, 50, 100]

const route = useRoute()

const filterBarRef = ref(null)
const drawerOpen = ref(false)
const activeRecord = ref({})
/** 请求失败时的 errCode（供 ErrorState 的「查看详情」展示；文案由 usePagination 落到 `error`） */
const errorCode = ref('')
/** 筛选栏回传的请求条件；`null` = 条件非法（缺时间范围 / 超 90 天）→ **不发请求** */
const queryParams = ref(null)
const invalidReason = ref('')
const hasFilters = ref(false)

/**
 * 取数：★ 每次请求都显式带 `beginNum` / `endNum`（由 `usePagination` 换算，见下表）；
 * `silent: true` 由本页自行渲染错误态（§2.5 第 5 条；B8 仍由 http 拦截器统一处理）。
 */
async function fetchPage(params) {
  if (!queryParams.value) return { data: [], total: 0 } // 条件非法：不发请求
  try {
    const res = await auditLogQry({ ...queryParams.value, ...params }, { silent: true })
    errorCode.value = ''
    return res
  } catch (error) {
    errorCode.value = String(error?.errCode || '')
    throw error
  }
}

/**
 * 服务端分页（列口径见 `docs` / 计划 §2.4.4）：
 *   第 1 页 → `{ beginNum: 0, endNum: 50 }`；第 2 页 → `{ beginNum: 50, endNum: 100, indexKey }`。
 * `immediate: false`：首屏由筛选栏 `mounted` 时的 `apply` 触发（默认近 24 小时）。
 */
const pagination = usePagination(fetchPage, { pageSize: 50, immediate: false })
const { rows, total, page, size, loading, error } = pagination

// URL 里的 page（刷新保持当前页；筛选条件由筛选栏从 query 回填）
const restoredPage = Number(route.query.page)
if (Number.isFinite(restoredPage) && restoredPage > 1) pagination.page.value = restoredPage

const columns = [
  { key: 'regYMDHMS', title: '时间', width: 172 },
  { key: 'actor', title: '操作者', width: 168 },
  { key: 'source', title: '来源', width: 108 },
  { key: 'action', title: '动作', minWidth: 196 },
  { key: 'target', title: '目标', minWidth: 176 },
  { key: 'result', title: '结果', width: 96 },
  { key: 'costMs', title: '耗时', width: 96, align: 'right' },
  { key: 'ipAddr', title: 'IP', width: 140 },
  { key: 'payloadDigest', title: '入参摘要', width: 148 }
]

/** `datalist` 建议值来源：当前页出现过的 action / targetType（∪ 已知 5 动作 / 4 对象类型） */
const seenActions = computed(() => Array.from(new Set(rows.value.map((row) => String(row.action || '')).filter(Boolean))))
const seenTargetTypes = computed(() =>
  Array.from(new Set(rows.value.map((row) => String(row.targetType || '')).filter(Boolean)))
)

const errorDetail = computed(() =>
  [errorCode.value ? `errCode: ${errorCode.value}` : '', error.value].filter(Boolean).join('\n')
)

/** 结果三重编码（★ 见文件头：禁止只用颜色表达） */
function resultMeta(row) {
  const value = String(row.result || '')
  if (value === 'OK') return { label: 'OK', icon: 'fa fa-circle-check', color: tokens.status.success }
  if (value === 'FAIL') return { label: 'FAIL', icon: 'fa fa-circle-xmark', color: tokens.status.danger }
  // 未知取值兜底：灰色空心 ○ + 原值（不新增未定义状态）
  return { label: value || '—', icon: 'fa-regular fa-circle', color: tokens.text.secondary }
}

/** 耗时：`N ms`；空值 / 非法值显示 `—`（真实后端以字符串返回，R-26） */
function costText(value) {
  const raw = value === null || value === undefined ? '' : String(value).trim()
  if (!raw) return '—'
  const ms = Number(raw)
  return Number.isFinite(ms) ? `${ms} ms` : raw
}

/** 空态文案（裁定 G）：条件非法 → 必填/上限提示；有筛选 → 当前条件无记录；仅时间范围 → 说明留痕范围 */
const emptyText = computed(() => {
  if (invalidReason.value === 'range-missing') {
    return {
      title: '请选择时间范围（最长 90 天）',
      description: '开始与结束时间均为必填（进入页面默认近 24 小时）；清空后不会发起请求。',
      actionText: ''
    }
  }
  if (invalidReason.value === 'range-too-long') {
    return {
      title: '所选时间跨度超过 90 天',
      description: '已阻止提交，请缩小时间范围后重试（前端保护：审计表无 regYMDHMS 索引，避免大表全扫）。',
      actionText: ''
    }
  }
  if (hasFilters.value) {
    return {
      title: '当前条件下没有审计记录',
      description: '筛选均为等值匹配（操作者需完整 loginID、IP 需完整地址）；可清空筛选后重试，时间范围会被保留。',
      actionText: '清空筛选'
    }
  }
  return {
    title: '该时间范围内没有审计记录',
    description:
      '当前仅投递（publish.push / publish.revoke）与归档清理（archive.*）动作会写审计留痕；' +
      '主题 / 素材 / 渲染 / 账号域暂不写审计。可放宽时间范围或改用「近 24 小时」之外的范围再试。',
    actionText: ''
  }
})

/* ------------------------------ 事件 ------------------------------ */

/**
 * 筛选栏提交：条件非法（`params === null`）→ 清空列表且**不发请求**（裁定 A）；
 * 合法 → 更新条件并回到第 1 页取数（首次进入保留 URL 里的 page）。
 */
let firstApply = true
function onFilterApply(payload) {
  invalidReason.value = String(payload?.invalidReason || '')
  hasFilters.value = Boolean(payload?.hasFilters)
  queryParams.value = payload?.params || null

  if (!queryParams.value) {
    // 条件非法：清空列表 + 清错误（不发请求），由空态文案给出必填 / 上限提示
    rows.value = []
    total.value = 0
    error.value = ''
    errorCode.value = ''
    return
  }
  if (firstApply) {
    firstApply = false
    refresh(false) // 首次：保留 URL 恢复的页码（不强制刷新缓冲）
    return
  }
  pagination.reset()
}

/** 手动刷新：`forceFlashFlag:'1'` 绕过后端查询缓冲重查（§2.4.3） */
function refresh(force) {
  return pagination.refresh(force ? { forceFlashFlag: '1' } : {})
}

function retry() {
  return refresh(true)
}

function onPageChange({ page: nextPage, size: nextSize }) {
  if (nextSize && nextSize !== size.value) {
    pagination.changeSize(nextSize)
  } else if (nextPage !== page.value) {
    pagination.goPage(nextPage)
  }
  // URL query 的唯一写入方是筛选栏：分页变化后让它把 page 同步进 query（刷新保持）
  filterBarRef.value?.syncQuery()
}

/** 空态主操作：清空筛选（保留时间范围，裁定 D） */
function onEmptyAction() {
  filterBarRef.value?.clearFilters()
}

function openDrawer(row) {
  activeRecord.value = { ...row } // 快照：避免翻页/刷新后抽屉内容被行数据覆盖
  drawerOpen.value = true
}
</script>
