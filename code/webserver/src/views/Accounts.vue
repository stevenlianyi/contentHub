<!-- ============================================================================
 * Accounts · P-11 账号管理（Step 15，原地替换 PLACEHOLDER）
 * ----------------------------------------------------------------------------
 * 页面只做「列表 + 编排」；弹窗 / 巡检面板 / 删除确认各自独立文件（§2.1 单文件 ≤600 行）：
 *   · `views/accounts/AccountEditDialog.vue`   新增 / 编辑（凭据录入：明文 appSecret → 服务端加密）
 *   · `views/accounts/CredentialCheckPanel.vue` 巡检三层展示
 *   · `views/accounts/AccountDeleteConfirm.vue` 硬删除二次确认（关联发布记录数取真实值）
 *
 * 【后端事实（一律服从源码，不凭计划文字推断）】
 *   ① 列表取数（裁定 B）：`accountqry({ mode:'full', order:'modify', ... })`。
 *      ★ 必须 `mode:'full'`：`mode='short'` 走 `CH_QUERY_SHORT_COLUMNS['ch_account']`
 *        （`common/mysqlCommon.py:333`）= `recID,accountCode,platform,accountName,subjectType,
 *        verifiedFlag,capability,healthStatus`，**不含** `expireYMDHMS` / `lastCheckYMDHMS` / `appID`；
 *        而 `full`（`*`）会**带出 `credentialCipher` / `credentialIV` 密文列**
 *        → 故必须经 `toAccountRow()` 白名单映射，密文列在进入 state / 模板之前即被丢弃。
 *   ② 服务端筛选与排序：`platform` / `healthStatus` / `order:'modify'`（= `modifyYMDHMS DESC`），
 *      由 R-28 手改后的 `funcAccountQry` 透传到底层 `query_ch_account`。
 *   ③ 巡检（`accounthealth`）：`check` / `refresh` / `probe` **三者等价**（同一 `runOnce` 调用）
 *      → 只用 `check`；`action` 为空 = **只汇总不巡检**（用于删除后刷新健康数字）。
 *      出参为 copy 域（P-ENV-01）：业务字段在 `data` 内（`healthSummary` / `credentialCheck`）。
 *   ④ 删除：`accountdel` 是**硬删除**（`delete_ch_account`；其上 `delFlag='1'` 的软删分支被注释
 *      —— `subfunc/crudApi.py:2133`）；查不到记录返回 `CB`。
 *   ⑤ 写入语义：`accountadd` **空值也会写入**；`accountmodify` **「非空且与当前值不同才写」**
 *      → 与附录 B R-22 同源，**空串无法清空字段**，UI 不得承诺「清空生效」。
 *
 * 【凭据安全（裁定 A / 后端 R-30）】
 *   响应面：`credentialCipher` / `credentialIV` **不进 state/表格/日志、不 copy**，只派生布尔 `credentialConfigured`；
 *   写入面唯一通道是**明文 `appSecret`**（仅弹窗本地变量，提交后立即置空），由后端 `_applyAccountSecret`
 *   经 AES-256-GCM 加密落库；无密钥 / 加密失败 → `F0` 拒绝落库。
 *   删除确认的「关联发布记录数」：`publishrecordqry({ accountID })`（R-31）；取不到显示 `—`（旧后端忽略该过滤时为平台总量）。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-lg">
    <header class="flex flex-wrap items-start justify-between gap-md">
      <div class="flex min-w-0 flex-col gap-xs">
        <h1 class="text-h1 text-ch-text-primary">账号管理</h1>
        <p class="text-body-s text-ch-text-secondary">
          平台凭据台账：凭据只显示掩码（密文不入选表、不进入任何请求）；健康徽章四态由巡检回写；
          小红书 / 通用平台无平台凭据，巡检会跳过并直出后端原因原文（不是失败）。
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-sm">
        <!-- ★ 2026-09-23：与「第三方账号管理」(/my-accounts) 双向链接；本页保持管理员全量台账口径不变 -->
        <AppButton size="sm" icon="fa fa-user-shield" @click="router.push('/my-accounts')">按归属查看</AppButton>
        <AppButton icon="fa fa-rotate-right" :loading="checking" :disabled="checking" @click="runCheck()">
          凭据巡检
        </AppButton>
        <AppButton type="primary" icon="fa fa-plus" @click="openCreate()">新建账号</AppButton>
      </div>
    </header>

    <!-- 凭据通道说明（后端 R-30）：明文只在弹窗本地，由服务端加密落库 -->
    <ConflictBanner type="info" title="凭据写入：明文只在弹窗本地输入，由服务端加密落库">
      弹窗只提交明文 appSecret，由后端经 AES-256-GCM 加密写入 credentialCipher / credentialIV；
      明文永不落库、不回显、不入日志；无密钥（CH_CREDENTIAL_KEY 未配置）或加密失败 → F0 且拒绝落库。
    </ConflictBanner>

    <!-- 保存凭据后的巡检闭环（裁定 C）：提示 + 「立即巡检该账号」入口 -->
    <ConflictBanner
      v-if="credentialNotice"
      type="info"
      title="凭据已保存，建议立即巡检验证"
      :actions="[{ key: 'check', label: '立即巡检该账号' }]"
      closable
      @action="runCheck(credentialNotice.recID)"
      @close="credentialNotice = null"
    >
      账号：{{ credentialNotice.accountName || credentialNotice.accountCode || credentialNotice.recID }}
      （{{ credentialNotice.accountCode || credentialNotice.recID }}）。该巡检按 accountID 收窄，只用该账号在
      credentialCheck.items[] 里的结论更新本行徽章与「最近检查」时间。
    </ConflictBanner>

    <!-- 筛选：平台（platformqry）+ 健康状态（HEALTH_STATUS_MAP 四态）→ 服务端筛选 -->
    <div class="flex flex-wrap items-end gap-md rounded-xl border border-ch-border bg-ch-surface px-xl py-lg">
      <label class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">平台</span>
        <select
          v-model="filters.platform"
          class="h-9 rounded-lg border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
          aria-label="按平台筛选"
          :disabled="loading"
          @change="applyFilters()"
        >
          <option value="">全部平台</option>
          <option v-for="option in platformOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
      </label>

      <label class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">健康状态</span>
        <select
          v-model="filters.healthStatus"
          class="h-9 rounded-lg border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
          aria-label="按健康状态筛选"
          :disabled="loading"
          @change="applyFilters()"
        >
          <option value="">全部状态</option>
          <option v-for="option in healthStatusOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
      </label>

      <AppButton size="sm" icon="fa fa-rotate-right" :loading="loading" @click="refreshList()">刷新</AppButton>
      <AppButton size="sm" :disabled="loading" @click="resetFilters()">重置</AppButton>
    </div>

    <p class="text-caption text-ch-text-tertiary">
      共 {{ total }} 条；平台 / 健康状态筛选与排序（order=modify → modifyYMDHMS 倒序）均由服务端 accountqry 执行，
      筛选与页码写入地址栏。列表取数 mode=full（short 缺 expireYMDHMS / lastCheckYMDHMS / appID），密文列已映射丢弃。
    </p>

    <!-- 巡检面板：三层展示（healthSummary / credentialCheck 统计 / items 明细） -->
    <CredentialCheckPanel
      :summary="healthSummary"
      :result="checkResult"
      :accounts="rows"
      :checking="checking"
      :error="checkError"
      :notice="checkNotice"
      :scope-note="checkScopeNote"
      @check="runCheck()"
    />

    <!-- 三态：错误态优先，其次表格 + 分页（loading / empty 由 AppTable 内置） -->
    <ErrorState
      v-if="error"
      :message="error"
      hint="账号列表读取失败：请检查网络或会话，稍后重试；服务端筛选条件已保留。"
      @retry="pagination.reset()"
    />

    <template v-else>
      <AppTable
        :columns="columns"
        :rows="rows"
        :loading="loading"
        row-key="recID"
        empty="还没有配置平台账号"
        empty-description="新增平台账号后，凭据健康巡检会按平台探活并回写健康徽章。"
        empty-action-text="新建账号"
        @empty-action="openCreate()"
      >
        <template #cell-accountName="{ row }">
          <div class="flex min-w-0 flex-col">
            <span class="truncate text-body-s text-ch-text-primary" :title="row.accountName">{{ row.accountName || '—' }}</span>
            <span class="truncate font-mono text-code text-ch-text-tertiary" :title="row.accountCode">{{ row.accountCode || '—' }}</span>
          </div>
        </template>

        <template #cell-platform="{ row }">
          <PlatformChip :platform="row.platform" />
        </template>

        <template #cell-subjectType="{ row }">
          <span class="text-body-s text-ch-text-secondary">{{ subjectText(row.subjectType) }}</span>
        </template>

        <template #cell-capability="{ row }">
          <span class="flex flex-col">
            <span class="text-body-s text-ch-text-primary">{{ capabilityText(row.capability) }}</span>
            <span class="text-caption text-ch-text-tertiary">{{ verifiedText(row.verifiedFlag) }}</span>
          </span>
        </template>

        <template #cell-healthStatus="{ row }">
          <StateBadge domain="health" :status="row.healthStatus || 'UNKNOWN'" />
        </template>

        <template #cell-expireYMDHMS="{ row }">
          <div class="flex flex-col">
            <span class="text-body-s text-ch-text-secondary">
              {{ row.expireYMDHMS ? formatYMDHMS(row.expireYMDHMS, 'YYYY-MM-DD') : '长期有效' }}
            </span>
            <span v-if="expireHint(row)" class="text-caption" :class="expireHint(row).class">
              {{ expireHint(row).text }}
            </span>
          </div>
        </template>

        <template #cell-lastCheckYMDHMS="{ row }">
          <div class="flex flex-col">
            <span class="text-body-s text-ch-text-secondary">
              {{ row.lastCheckYMDHMS ? formatYMDHMS(row.lastCheckYMDHMS) : '—' }}
            </span>
            <span v-if="row.lastCheckYMDHMS" class="text-caption text-ch-text-tertiary">
              {{ fromNow(row.lastCheckYMDHMS).text }}
            </span>
          </div>
        </template>

        <template #cell-actions="{ row }">
          <div class="flex flex-wrap items-center gap-sm">
            <AppButton size="sm" icon="fa fa-pen" @click="openEdit(row)">编辑</AppButton>
            <AppButton
              size="sm"
              icon="fa fa-rotate-right"
              :disabled="checking"
              :disabled-reason="checking ? '已有巡检在执行，请稍候' : ''"
              @click="runCheck(row.recID)"
            >
              巡检
            </AppButton>
            <AppButton size="sm" type="danger" icon="fa fa-trash" @click="openDelete(row)">删除</AppButton>
          </div>
        </template>
      </AppTable>

      <AppPagination
        :total="total"
        :page-size="size"
        :current-page="page"
        :disabled="loading"
        @page-change="onPageChange"
      />
    </template>

    <AccountEditDialog
      v-model="dialogVisible"
      :mode="dialogMode"
      :account="editingRow"
      :platform-options="platformOptions"
      :subject-options="subjectOptions"
      :capability-options="capabilityOptions"
      :verified-options="verifiedOptions"
      @saved="onSaved"
    />

    <AccountDeleteConfirm v-model="deleteVisible" :account="deletingRow" @deleted="onDeleted" />
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toast } from 'vue3-toastify'
import AppButton from '@/components/base/AppButton.vue'
import AppPagination from '@/components/base/AppPagination.vue'
import AppTable from '@/components/base/AppTable.vue'
import ConflictBanner from '@/components/base/ConflictBanner.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import PlatformChip from '@/components/biz/PlatformChip.vue'
import StateBadge from '@/components/biz/StateBadge.vue'
import AccountDeleteConfirm from '@/views/accounts/AccountDeleteConfirm.vue'
import AccountEditDialog from '@/views/accounts/AccountEditDialog.vue'
import CredentialCheckPanel from '@/views/accounts/CredentialCheckPanel.vue'
import { HEALTH_STATUS_MAP, PLATFORM_MAP, PLATFORM_ORDER } from '@/config/chOptions'
import { usePagination } from '@/components/base/composables/usePagination'
import { normalizeHealth } from '@/views/dashboard/useDashboardData'
import { accountHealth, accountQry } from '@/api/account'
import { platformQry } from '@/api/platform'
import { formatYMDHMS, fromNow, parseDateTime } from '@/utils/common'

/* ------------------------------ 字典（展示口径，来源 database/ch_account.txt） ------------------------------ */
/** 主体类型：`subjectType` ∈ personal / enterprise */
const SUBJECT_MAP = { personal: '个人', enterprise: '企业' }
/** 能力：`capability` ∈ draft_box / asset_pack / api_publish（★ 不是投递入口，仅能力声明） */
const CAPABILITY_MAP = { draft_box: '草稿箱', asset_pack: '素材包', api_publish: '正式发布' }
/** 认证标记：`verifiedFlag` ∈ 0 / 1 */
const VERIFIED_MAP = { 0: '未认证', 1: '已认证' }

const toOptions = (map) => Object.entries(map).map(([value, label]) => ({ value, label }))
const subjectOptions = toOptions(SUBJECT_MAP)
const capabilityOptions = toOptions(CAPABILITY_MAP)
const verifiedOptions = toOptions(VERIFIED_MAP)

/** 状态元信息 → 下拉项（四态键唯一来源 = chOptions.HEALTH_STATUS_MAP） */
const healthStatusOptions = Object.entries(HEALTH_STATUS_MAP).map(([value, meta]) => ({ value, label: meta.label }))

/** 到期阈值兜底（对齐后端 `DEFAULT_EXPIRE_WARN_DAYS`，仅在响应未回传 warnDays 时使用；不参与正常展示） */
const FALLBACK_WARN_DAYS = 7

const subjectText = (value) => SUBJECT_MAP[String(value)] || (value ? String(value) : '—')
const capabilityText = (value) => CAPABILITY_MAP[String(value)] || (value ? String(value) : '—')
const verifiedText = (value) => VERIFIED_MAP[String(value)] || '—'

/* ------------------------------ 字段白名单（裁定 B，密文一律丢弃） ------------------------------ */
/**
 * 允许进入 state / 模板的列（= 页面与三个子组件用到的全部字段）。
 * ★ 其余列**全部丢弃**，其中必须丢弃的敏感列：
 *   `credentialCipher`（凭据密文，TEXT）、`credentialIV`（加密初始向量）、
 *   `appSecret` / `credentialRef`（Mock 独有字段，真实表无此列）。
 * ★ 同时丢弃的未使用列（真实 `mode='full'` 会带出）：
 *   `accountID` / `quotaUsed` / `quotaLimit` / `autoPublishFlag` / `operator` /
 *   `regID` / `regYMDHMS` / `modifyID` / `modifyYMDHMS` / `delFlag`（以及后端未来新增的任何列）。
 */
const ACCOUNT_FIELD_WHITELIST = [
  'recID', 'accountCode', 'platform', 'accountName', 'subjectType', 'verifiedFlag', 'capability',
  'appID', 'expireYMDHMS', 'healthStatus', 'lastCheckYMDHMS', 'lastUseYMDHMS', 'ownerID', 'label', 'memo'
]

/** 开发态证据：记录最近一次映射的「保留 / 丢弃」列名（**只记录列名，不记录任何值**） */
function recordFilterEvidence(rawKeys, keptKeys) {
  if (!import.meta.env.DEV || typeof window === 'undefined') return
  window.__P11_ACCOUNT_FILTER__ = {
    kept: keptKeys,
    dropped: rawKeys.filter((key) => !keptKeys.includes(key))
  }
}

/**
 * 响应行 → 页面行（**唯一入口**，模板与子组件只消费本函数的输出）。
 * ★ `credentialConfigured` 由密文列**存在性**派生（布尔），原始密文**不赋给任何变量、不入 state**；
 *   该派生依赖 `mode:'full'`：若后端把 `expireYMDHMS,lastCheckYMDHMS,appID` 补进 short 列清单并改用
 *   `mode:'short'`（已在产出说明登记为建议），则本布尔需改为由「凭据引用列」推断。
 */
function toAccountRow(raw) {
  if (!raw || typeof raw !== 'object') return null
  const row = {}
  ACCOUNT_FIELD_WHITELIST.forEach((key) => {
    const value = raw[key]
    row[key] = value === undefined || value === null ? '' : String(value)
  })
  row.credentialConfigured = Boolean(String(raw.credentialCipher || '').trim())
  recordFilterEvidence(Object.keys(raw), Object.keys(row))
  return row
}

/* ------------------------------ 列表取数（服务端分页 + 服务端筛选） ------------------------------ */
const route = useRoute()
const router = useRouter()

const filters = reactive({ platform: '', healthStatus: '' })
const platforms = ref([])

const queryParams = () => ({
  // ★ mode 必须 full：short 列清单缺 expireYMDHMS / lastCheckYMDHMS / appID
  mode: 'full',
  order: 'modify',
  ...(filters.platform ? { platform: filters.platform } : {}),
  ...(filters.healthStatus ? { healthStatus: filters.healthStatus } : {})
})

const pagination = usePagination(
  async ({ beginNum, endNum }) => {
    const res = await accountQry({ ...queryParams(), beginNum, endNum })
    const list = Array.isArray(res?.data) ? res.data : []
    // ★ 白名单映射在此处完成：密文列不会随 rows 进入任何组件
    return { ...res, data: list.map(toAccountRow).filter(Boolean) }
  },
  { pageSize: 20, immediate: false }
)

const { rows, total, page, size, loading, error } = pagination

// ★ 2026-09-24 收紧列宽(同 MyAccounts 口径): el-table 总宽超容器会按比例压缩所有列, 平台列须容纳 PlatformChip(最长 95px: 通用HTML)+内边距 16×2
//   ⚠ 原注释写的 PlatformChip(76px) 是「未修不换行时被挤成两行」的宽度, 不是约束值; 内边距口径见 styles/element-vars.css ④
const columns = [
  { key: 'accountName', title: '账号名', minWidth: 168 },
  { key: 'platform', title: '平台', width: 132 },
  { key: 'subjectType', title: '主体类型', width: 96 },
  { key: 'capability', title: '能力', width: 108 },
  { key: 'healthStatus', title: '健康状态', width: 120 },
  { key: 'expireYMDHMS', title: '到期时间', width: 136 },
  { key: 'lastCheckYMDHMS', title: '最近检查', width: 148 },
  { key: 'actions', title: '操作', width: 236 }
]

async function loadPlatforms() {
  const res = await platformQry({ beginNum: 0, endNum: 50 }, { silent: true }).catch((e) => e)
  const list = Array.isArray(res?.data) ? res.data : []
  platforms.value = list
    .map((item) => ({ value: String(item.platformCode || ''), label: String(item.platformName || '') }))
    .filter((item) => item.value)
}

/** 平台选项：优先 `platformqry`（免登录端点）；取不到时回落前端字典（`PLATFORM_ORDER`） */
const platformOptions = computed(() =>
  platforms.value.length
    ? platforms.value
    : PLATFORM_ORDER.map((code) => ({ value: code, label: PLATFORM_MAP[code]?.label || code }))
)

/* ------------------------------ 巡检与健康汇总（裁定 D / C） ------------------------------ */
const healthSummary = ref(null)
const checkResult = ref(null)
const checking = ref(false)
const checkError = ref('')
const checkNotice = ref('')
/** 本轮巡检的收窄目标（空串 = 全量）；用于面板补充说明 */
const checkScope = ref('')

/** 只汇总不巡检（action 留空）→ 用于首屏与删除后刷新健康数字 */
async function loadSummary() {
  try {
    const res = await accountHealth({}, { silent: true })
    const data = res?.data || {}
    healthSummary.value = normalizeHealth(data.healthSummary || data.summary || res?.healthSummary)
  } catch (e) {
    console.error('[P-11] 健康汇总读取失败', e)
  }
}

/**
 * 用单账号巡检结论更新该行（裁定 C）：**只认 `items[]` 中 `accountID` 命中的那一条**（不按全量
 * `healthSummary` 推断）；`lastCheckYMDHMS` 仅在后端确实回写时同步（跳过项不改「最近检查」）。
 * @returns {boolean} 是否命中并已更新
 */
function applyRowCheckResult(recID, check) {
  const items = Array.isArray(check?.items) ? check.items : []
  const hit = items.find((item) => String(item?.accountID) === String(recID))
  if (!hit) return false
  const row = rows.value.find((item) => String(item.recID) === String(recID))
  if (row) {
    row.healthStatus = String(hit.healthStatus || 'UNKNOWN')
    if (!String(hit.skipReason || '')) row.lastCheckYMDHMS = String(check.checkedAt || '')
  }
  return true
}

/**
 * 触发巡检：只用 `check`（`check` / `refresh` / `probe` 后端完全等价）。
 * @param {string} [recID] 收窄单账号（`ch_account.recID`；后端 `accounthealth` → `runOnce` 按 recID 过滤）
 */
async function runCheck(recID) {
  if (checking.value) return
  const targetRecID = String(recID || '')
  checking.value = true
  checkError.value = ''
  checkNotice.value = ''
  try {
    const params = { action: 'check' }
    if (targetRecID) params.accountID = targetRecID
    const res = await accountHealth(params, { silent: true })
    const data = res?.data || {}
    const check = data.credentialCheck || null
    checkResult.value = check
    checkScope.value = targetRecID
    healthSummary.value = normalizeHealth(data.healthSummary || data.summary || res?.healthSummary)
    if (!check) {
      checkNotice.value = '本次响应未包含 credentialCheck 明细（后端 action 为空时只汇总不巡检）。'
      return
    }
    if (!targetRecID) {
      // 全量巡检：回写 healthStatus / lastCheckYMDHMS → 刷新列表让徽章与「最近检查」同步
      await pagination.reset()
      return
    }
    // ★ 单账号巡检（保存凭据后的闭环）：只用 items[] 结论更新该行
    const updated = applyRowCheckResult(targetRecID, check)
    if (Number(check.skipped) === -1) toast.info('已有巡检在执行，本轮跳过（未改写任何账号）')
    else if (Number(check.degraded) === 1) toast.info('巡检锁 / 计数已降级（Redis 不可用），结果可能不完整')
    else if (!updated) toast.warning('本轮未返回该账号的明细，未更新行徽章')
    else toast.success('已按最新探活结论更新该账号徽章与「最近检查」时间')
    await pagination.load()
  } catch (e) {
    checkError.value = e?.MSG?.content || '凭据巡检失败，请稍后重试'
    console.error('[P-11] 凭据巡检失败', e)
  } finally {
    checking.value = false
  }
}

/** 面板补充说明：单账号巡检时说明「明细收窄、汇总仍为全量」，避免误读 */
const checkScopeNote = computed(() => (checkScope.value
  ? `本轮为单账号巡检（accountID=${checkScope.value}）：下方统计与明细仅含该账号；健康汇总 healthSummary 仍为全量。`
  : ''))

/* ------------------------------ 到期预警（裁定 E：阈值取后端 warnDays） ------------------------------ */
const warnDays = computed(() => {
  const value = Number(checkResult.value?.warnDays)
  return Number.isFinite(value) && value > 0 ? value : FALLBACK_WARN_DAYS
})

/** 剩余时间：空/非法 `expireYMDHMS` → null（长期有效，**不得显示为已过期**） */
function expireRemainMs(expireYMDHMS) {
  const raw = String(expireYMDHMS || '').trim()
  if (!raw || !/^\d{8,14}$/.test(raw)) return null
  const date = parseDateTime(raw)
  return date ? date.getTime() - Date.now() : null
}

/** 行内到期提示：已过期（危险）/ N 天后到期（预警）/ 无提示（长期有效或未临期） */
function expireHint(row) {
  const remain = expireRemainMs(row.expireYMDHMS)
  if (remain === null) return null
  if (remain <= 0) return { text: '已过期', class: 'text-ch-danger' }
  const days = Math.ceil(remain / 86400000)
  if (days <= warnDays.value) return { text: `${days} 天后到期`, class: 'text-ch-warning' }
  return null
}

/* ------------------------------ URL query（筛选 / 页码 / ?action=check） ------------------------------ */
function writeQuery() {
  router.replace({
    path: route.path,
    query: {
      ...route.query,
      platform: filters.platform || undefined,
      healthStatus: filters.healthStatus || undefined,
      page: page.value > 1 ? String(page.value) : undefined
    }
  })
}

function readQuery() {
  const query = route.query
  filters.platform = String(query.platform || '')
  filters.healthStatus = String(query.healthStatus || '')
  const parsedPage = Number(query.page)
  if (Number.isFinite(parsedPage) && parsedPage > 0) page.value = parsedPage
}

function applyFilters() {
  writeQuery()
  pagination.reset()
}

function resetFilters() {
  filters.platform = ''
  filters.healthStatus = ''
  page.value = 1
  applyFilters()
}

/** 刷新当前页（不清筛选、不跳页） */
function refreshList() {
  return pagination.load()
}

function onPageChange({ page: nextPage, size: nextSize }) {
  if (nextSize && nextSize !== size.value) {
    pagination.changeSize(nextSize)
  } else if (nextPage !== page.value) {
    pagination.goPage(nextPage)
  }
  writeQuery()
}

/* ------------------------------ 新建 / 编辑 / 删除编排 ------------------------------ */
const dialogVisible = ref(false)
const dialogMode = ref('create')
const editingRow = ref(null)
const deleteVisible = ref(false)
const deletingRow = ref(null)
/** 保存凭据成功后的巡检入口（保存提示条；成功保存凭据才有值） */
const credentialNotice = ref(null)

function openCreate() {
  dialogMode.value = 'create'
  editingRow.value = null
  dialogVisible.value = true
}

function openEdit(row) {
  dialogMode.value = 'edit'
  editingRow.value = row
  dialogVisible.value = true
}

function openDelete(row) {
  deletingRow.value = row
  deleteVisible.value = true
}

/**
 * 新增 / 编辑成功：关闭弹窗并发起一次全量刷新（服务端 order=modify，新记录会自然置顶）。
 * @param {{recID?:string, accountCode?:string, accountName?:string, credentialSaved?:boolean}} [payload]
 *   `credentialSaved = true` → 展示「凭据已保存，建议立即巡检验证」提示条（含「立即巡检该账号」入口）。
 */
async function onSaved(payload) {
  dialogVisible.value = false
  editingRow.value = null
  if (payload?.credentialSaved) {
    credentialNotice.value = {
      recID: String(payload.recID || ''),
      accountCode: String(payload.accountCode || ''),
      accountName: String(payload.accountName || '')
    }
  }
  await pagination.reset()
  await loadSummary()
}

/**
 * 删除完成（含 `CB`「无此账号记录」）：刷新列表 + **重新拉一次 accounthealth（不传 action，只汇总）**
 * 刷新健康数字（裁定 C）。
 */
async function onDeleted() {
  deleteVisible.value = false
  deletingRow.value = null
  await pagination.reset()
  await loadSummary()
}

/* ------------------------------ 首屏 ------------------------------ */
onMounted(async () => {
  readQuery()
  loadPlatforms()
  await loadSummary()
  await pagination.load()
  // ★ `?action=check` 直达（P-01 系统状态条入口）：消费后立即清掉 query，避免刷新重复触发
  if (String(route.query.action || '') === 'check') {
    await router.replace({
      path: route.path,
      query: { ...route.query, action: undefined }
    })
    await runCheck()
  }
})
</script>
