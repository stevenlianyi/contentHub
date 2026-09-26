<!-- ============================================================================
 * MyAccounts · 第三方账号管理（★ 2026-09-23 新增页面，路由 /my-accounts，name MyAccounts）
 * ----------------------------------------------------------------------------
 * 【与 P-11 /accounts 的关系（裁定：两页并存，不合并）】
 *   · `/accounts`（P-11）  = 管理员全量台账（`meta.roles = ROLES_SYSTEM`，行为本次**未改动**）；
 *   · `/my-accounts`（本页）= 面向所有**非访客**角色的「按归属」入口，两页互相跳转
 *     （本页 → 「打开全量台账」按钮；`/accounts` → 「按归属查看」按钮）。
 *   ★ 管理员在本页仍是**超管视角**（后端 `chkIsManager` 不按 ownerID 过滤），故管理员两页数据等价，
 *     本页只多一层「归属」列与口径说明；非管理员则只可能看到 `ownerID = 本人 loginID` 的记录。
 *
 * 【归属隔离（后端事实，前端只表达不实现）】
 *   · `accountqry`：非管理员被服务端**强制** `ownerID = loginID`（前端传别人的 ownerID 亦被覆盖）；
 *   · `accountadd` / `accountmodify` / `accountdel`：服务端按登录账号归属校验，越权 → `BG`（权限不足）；
 *   · `accounthealth`：非管理员巡检与 `healthSummary` 均按 `ownerID = loginID` 收窄（方案甲）；
 *   · 因此本页**不传 `ownerID`**（传了也无意义，且会掩盖服务端口径）；行内「巡检」也只传本人 `recID`。
 *   · 鉴权一律 `userStore.hasRole([...])`：`hasPermission()` 因后端不下发 permissions 恒为 false，
 *     **严禁**用作本页任何门禁分支（`store/modules/user.js:194-203`）。
 *
 * 【凭据安全（沿用 P-11 硬约束，不破例）】
 *   · 列表 `mode:'full'` 会带出 `credentialCipher` / `credentialIV` 密文列
 *     → 必须经 `toAccountRow()` 白名单映射，密文列进入 state / 模板之前即被丢弃；
 *   · 明文 `appSecret` 只存在于弹窗本地变量，提交后立即置空；不进 URL / Pinia / console / 错误提示；
 *   · 非管理员的弹窗以 `owner-fixed` 锁定归属（只读展示 loginID，且不随请求提交）。
 *
 * 【子组件 / 组合式复用（不复制第二份）】
 *   `views/accounts/{AccountEditDialog,CredentialCheckPanel,AccountDeleteConfirm}.vue`、
 *   `views/myAccounts/useMyAccountCheck.js`（巡检 / 汇总 / 到期预警编排，本页超 600 行后按范式拆出）。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-lg">
    <header class="flex flex-wrap items-start justify-between gap-md">
      <div class="flex min-w-0 flex-col gap-xs">
        <h1 class="text-h1 text-ch-text-primary">第三方账号管理</h1>
        <p class="text-body-s text-ch-text-secondary">
          管理<strong>本人</strong>的平台账号与凭据：归属由服务端按登录账号派生，列表只返回本人账号；
          凭据只显示掩码（密文不入选表、不进入任何请求）；健康徽章四态由巡检回写。
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-sm">
        <AppButton
          icon="fa fa-rotate-right"
          :loading="checking"
          :disabled="checking"
          :disabled-reason="checking ? '已有巡检在执行，请稍候' : ''"
          @click="runCheck()"
        >
          凭据巡检
        </AppButton>
        <AppButton type="primary" icon="fa fa-plus" @click="openCreate()">新建账号</AppButton>
      </div>
    </header>

    <!-- 归属口径说明条（管理员 / 非管理员两套文案，均由服务端口径决定） -->
    <ConflictBanner type="info" :title="scopeTitle">{{ scopeText }}</ConflictBanner>

    <!-- 管理员：两页并存的口径说明 + 跳转（与 /accounts 的「按归属查看」互为双向入口） -->
    <ConflictBanner
      v-if="isManager"
      type="info"
      title="与「账号管理」(/accounts) 并存：本页为「按归属」入口"
      :actions="[{ key: 'go', label: '打开全量台账' }]"
      @action="goAllAccounts()"
    >
      管理员（administrator / manager）在本页同为<strong>超管视角</strong>：后端不按 ownerID 过滤，可读可改任意账号，
      故两页数据等价；差异仅在入口语义（本页强调归属列，/accounts 为 P-11 全量台账）。
    </ConflictBanner>

    <!-- 凭据通道说明（后端 R-30）：明文只在弹窗本地，由服务端加密落库 -->
    <ConflictBanner type="info" title="凭据写入：明文只在弹窗本地输入，由服务端加密落库">
      弹窗只提交明文 appSecret，由后端经 AES-256-GCM 加密写入 credentialCipher / credentialIV；
      明文永不落库、不回显、不入日志；无密钥（CH_CREDENTIAL_KEY 未配置）或加密失败 → F0 且拒绝落库。
    </ConflictBanner>

    <!-- 保存凭据后的巡检闭环：提示 + 「立即巡检该账号」入口 -->
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
      共 {{ total }} 条（{{ scopeCountText }}）；平台 / 健康状态筛选与排序（order=modify → modifyYMDHMS 倒序）
      均由服务端 accountqry 执行，筛选与页码写入地址栏。列表取数 mode=full（short 缺 expireYMDHMS /
      lastCheckYMDHMS / appID），密文列已映射丢弃。
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
        empty="还没有属于你的平台账号"
        empty-description="新建平台账号后，凭据健康巡检会按平台探活并回写健康徽章；归属由服务端按登录账号派生。"
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

        <template #cell-ownerID="{ row }">
          <span class="flex flex-col">
            <span class="truncate font-mono text-code text-ch-text-secondary" :title="row.ownerID">{{ row.ownerID || '—' }}</span>
            <span v-if="isSelfOwned(row)" class="text-caption text-ch-text-tertiary">本人</span>
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

    <!-- 弹窗复用：非管理员以 owner-fixed 锁定归属（只读当前 loginID，且不随请求提交） -->
    <AccountEditDialog
      v-model="dialogVisible"
      :mode="dialogMode"
      :account="editingRow"
      :platform-options="platformOptions"
      :subject-options="subjectOptions"
      :capability-options="capabilityOptions"
      :verified-options="verifiedOptions"
      :owner-fixed="!isManager"
      :ownerLoginID="loginID"
      @saved="onSaved"
    />

    <AccountDeleteConfirm v-model="deleteVisible" :account="deletingRow" @deleted="onDeleted" />
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
import { accountQry } from '@/api/account'
import { platformQry } from '@/api/platform'
import { useUserStore } from '@/store/modules/user'
import { useMyAccountCheck } from '@/views/myAccounts/useMyAccountCheck'
import { formatYMDHMS, fromNow } from '@/utils/common'

/* ------------------------------ 会话与口径 ------------------------------ */
const userStore = useUserStore()
/** ★ 鉴权只用 hasRole：hasPermission() 恒为 false（后端不下发 permissions），不得用于门禁 */
const isManager = computed(() => userStore.hasRole(['administrator', 'manager']))
const loginID = computed(() => String(userStore.username || ''))

const scopeTitle = computed(() => (isManager.value
  ? '超管视角：本页不按归属过滤'
  : `归属隔离：仅显示并只能修改归属为「${loginID.value || '当前登录账号'}」的账号`))

const scopeText = computed(() => (isManager.value
  ? '管理员（administrator / manager）为超管视角：accountqry 不放 ownerID 条件、可读可改任意账号，'
    + 'healthSummary 与巡检明细亦为全量。'
  : '服务端强制按登录账号收窄：accountqry 覆盖前端 ownerID 入参；'
    + 'accountadd 强制写入本人归属；accountmodify / accountdel 越权一律返回 BG（权限不足）；'
    + '凭据巡检与健康汇总同样只覆盖本人账号。归属不可自行修改。'))

const scopeCountText = computed(() => (isManager.value ? '超管视角：全量' : '仅本人账号'))

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

/* ------------------------------ 字段白名单（密文一律丢弃） ------------------------------ */
/**
 * 允许进入 state / 模板的列（= 本页与三个子组件用到的全部字段）。
 * ★ 必须丢弃的敏感列：`credentialCipher`（密文）/ `credentialIV`（初始向量）/
 *   `appSecret` / `credentialRef`（Mock 私有）；同时丢弃未使用列
 *   （`accountID` / `quotaUsed` / `regID` / `regYMDHMS` / `modifyID` / `modifyYMDHMS` / `delFlag` 等）。
 */
const ACCOUNT_FIELD_WHITELIST = [
  'recID', 'accountCode', 'platform', 'accountName', 'subjectType', 'verifiedFlag', 'capability',
  'appID', 'expireYMDHMS', 'healthStatus', 'lastCheckYMDHMS', 'lastUseYMDHMS', 'ownerID', 'label', 'memo'
]

/** 开发态证据：记录最近一次映射的「保留 / 丢弃」列名（**只记录列名，不记录任何值**） */
function recordFilterEvidence(rawKeys, keptKeys) {
  if (!import.meta.env.DEV || typeof window === 'undefined') return
  window.__MYACCOUNTS_FILTER__ = {
    kept: keptKeys,
    dropped: rawKeys.filter((key) => !keptKeys.includes(key))
  }
}

/**
 * 响应行 → 页面行（**唯一入口**，模板与子组件只消费本函数的输出）。
 * ★ `credentialConfigured` 由密文列**存在性**派生（布尔），原始密文不赋给任何变量、不入 state。
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

/** 归属是否为本人的行（仅用于展示「本人」小字；管理员视角下他人行不标） */
const isSelfOwned = (row) => Boolean(loginID.value) && String(row?.ownerID || '') === loginID.value

/* ------------------------------ 列表取数（服务端分页 + 服务端筛选） ------------------------------ */
const route = useRoute()
const router = useRouter()

const filters = reactive({ platform: '', healthStatus: '' })
const platforms = ref([])

/**
 * ★ 刻意**不传 `ownerID`**：非管理员的归属由服务端按 loginID 强制收窄；
 *   管理员传 ownerID 会从超管视角降级为单归属筛选，与本页「超管视角」口径不一致。
 */
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

/**
 * 列宽（★ 2026-09-24 调整）：平台列 132 —— `PlatformChip` 为原子标识（`shrink-0 + whitespace-nowrap`，
 * 实测宽度 94（微信公众号）/ **95**（通用HTML，最长），列宽须 ≥ 95 + 单元格内边距 16×2 = 127；
 * ★ 该算式只在「单元格内边距每侧 16」时成立：EP 默认还会给内层 `.cell` 再叠 12px，
 *   已由 `styles/element-vars.css` ④ 归零。**不得按修复前的实际值反推列宽**，
 *   否则会误判成「列宽不足」而盲目加宽（该误导即 09-24 那次 6~7px 裁切的来源）。
 * 操作列 236 保证三个按钮不折行；账号名列用 `minWidth`（弹性列，空间不足时优先让位）。
 */
const columns = [
  { key: 'accountName', title: '账号名', minWidth: 168 },
  { key: 'platform', title: '平台', width: 132 },
  { key: 'ownerID', title: '归属', width: 128 },
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

/* ------------------------------ 巡检 / 汇总 / 到期预警（组合式拆分） ------------------------------ */
const {
  healthSummary, checkResult, checking, checkError, checkNotice, checkScopeNote,
  expireHint, loadSummary, runCheck
} = useMyAccountCheck({
  isManager,
  loginID,
  rows,
  reload: { resetList: () => pagination.reset(), loadList: () => pagination.load() }
})

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

/** 跳转管理员全量台账（P-11）——与 /accounts 的「按归属查看」构成双向入口 */
function goAllAccounts() {
  router.push('/accounts')
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
 * 新增 / 编辑成功：关闭弹窗并发起一次刷新（服务端 order=modify，新记录会自然置顶）。
 * @param {{recID?:string, accountCode?:string, accountName?:string, credentialSaved?:boolean}} [payload]
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

/** 删除完成（含 `CB` / 越权 `BG`）：刷新列表 + 重新拉一次 accounthealth（不传 action，只汇总） */
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
  // ★ `?action=check` 直达（工作台状态条入口）：消费后立即清掉 query，避免刷新重复触发
  if (String(route.query.action || '') === 'check') {
    await router.replace({
      path: route.path,
      query: { ...route.query, action: undefined }
    })
    await runCheck()
  }
})
</script>
