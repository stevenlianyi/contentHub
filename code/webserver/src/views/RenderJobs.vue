<!-- ============================================================================
 * RenderJobs · 渲染任务（P-06，Step 11）
 * ----------------------------------------------------------------------------
 * 页面职责（取数 / 轮询 / 状态机自约束全部收敛到 `views/renderJobs/useJobPolling.js`）：
 *   ① **6 列**：任务号（`jobCode`，等宽）/ 主题（标题，点击进 `/topics/:topicCode`）/
 *      版式（`layoutCode` + `LAYOUT_TYPE_MAP` 中文）/ 状态（`StateBadge domain="job"`）/
 *      耗时（`costMs` → 人类可读）/ 操作；另有 1 个 40px **展开控件列**（无表头文案，非数据列），
 *      用于内联展开失败原因（★ `AppTable` 未暴露 `el-table` 的展开行能力，且不得改动 Step 4 组件
 *      → 按 §2.11「默认用 Element Plus `el-table`」直用 `el-table`，并沿用与 AppTable 同一套
 *      Token 样式口径，见下方 `headerCellStyle` / `cellStyle` / `rowStyle`）。
 *   ② **不使用进度条**（附录 B R-06：`ch_render_job.progress` 不由渲染流程驱动）：
 *      仅在 `RUNNING && Number(progress) > 0` 时以**文本**显示百分比，`= 0` 时显示「进行中」。
 *   ③ 操作严格按状态机暴露（裁定 B，见 `useJobPolling.JOB_ACTIONS`）：
 *      `PENDING`→取消；`RUNNING`→查看详情；`FAILED`→重试 / 重新渲染；`DONE`→查看产物。
 *      ★ HTTP 端点 `renderjobmodify` 不校验状态机 → 非法动作在 UI 上**不出现**，并在调用前二次断言。
 *   ④ 筛选（状态 / 主题 / 关键字）写入 URL query（刷新与前进后退保持），并消费
 *      上游落点：Step 5 工作台「渲染失败」→ `?jobStatus=FAILED`、Step 9「提交渲染」→ `?topicID=<recID>`。
 *   ⑤ 存在 `PENDING`/`RUNNING` 时每 5s 静默轮询；隐藏时暂停、可见时立即补一次；连续 3 次失败
 *      暂停并给出「手动刷新」；全部终态后停止并只提示一次「全部任务已完成」。
 *   ⑥ 三态齐备：骨架屏 / `ErrorState`（原因 + 重试 + 详情）/ `EmptyState`（主操作「去主题库」）。
 *
 * 无障碍：任务行容器 `role="status"` + `aria-live="polite"`（状态变化播报）；
 *   失败原因触发按钮带 `aria-expanded` + `aria-controls`；颜色只取 Token（`npm run lint:hex`）。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-lg">
    <header class="flex flex-wrap items-center justify-between gap-md">
      <div class="flex flex-col gap-xs">
        <h1 class="text-h1 text-ch-text-primary">渲染任务</h1>
        <p class="text-caption text-ch-text-tertiary">
          <span v-if="pollingActive">每 5 秒自动刷新中</span>
          <span v-else-if="pollPaused" class="text-ch-warning">自动刷新已暂停</span>
          <span v-else-if="hasActiveJobs">自动刷新已暂停（页面不可见）</span>
          <span v-else>任务均已进入终态，自动刷新已停止</span>
          <span v-if="lastLoadedAt"> · 最近刷新 {{ lastLoadedAt }}</span>
        </p>
      </div>
      <AppButton icon="fa fa-rotate-right" :loading="loading || refreshing" @click="manualRefresh">刷新</AppButton>
    </header>

    <!-- 筛选：状态 / 主题（关键字）→ 全部写入 URL query -->
    <div class="flex flex-wrap items-end gap-md rounded-xl border border-ch-border bg-ch-surface px-xl py-lg">
      <label class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">状态</span>
        <select
          class="h-9 rounded-lg border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
          aria-label="按状态筛选"
          :value="filters.jobStatus"
          @change="applyFilter({ jobStatus: $event.target.value })"
        >
          <option value="">全部状态</option>
          <option v-for="status in JOB_STATUS_ORDER" :key="status" :value="status">{{ statusLabel(status) }}</option>
        </select>
      </label>

      <label class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">主题 / 任务号</span>
        <input
          class="h-9 w-56 rounded-lg border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary placeholder:text-ch-text-tertiary"
          type="search"
          placeholder="输入主题标题或任务号后回车"
          aria-label="按主题标题或任务号筛选"
          :value="filters.keyword"
          @change="applyFilter({ keyword: $event.target.value })"
        />
      </label>

      <p
        v-if="filters.topicID"
        class="flex items-center gap-sm rounded-lg border border-ch-primary/40 bg-ch-primary-subtle px-sm py-xs text-body-s text-ch-text-primary"
      >
        主题 #{{ filters.topicID }}
        <button
          type="button"
          class="text-ch-text-secondary transition-colors duration-150 ease-out hover:text-ch-text-primary"
          aria-label="清除主题筛选"
          @click="applyFilter({ topicID: '' })"
        >
          <i class="fa fa-times" aria-hidden="true"></i>
        </button>
      </p>

      <AppButton v-if="filterActive" size="sm" @click="clearFilters">清除筛选</AppButton>

      <p v-if="filterActive" class="max-w-[560px] text-caption text-ch-text-tertiary">
        状态 / 主题筛选由服务端执行（renderjobqry 已透传 jobStatus / topicID，附录 B R-28）；
        关键字为本地筛选（后端无 keyword 参数）。
      </p>
    </div>

    <!-- 动作失败 / C7 行内说明（裁定 B：HTTP 路径不回显 currentStatus，两处都容错） -->
    <ConflictBanner v-if="actionError" type="warning" :title="actionError.title" closable @close="actionError = null">
      <p>{{ actionError.message }}</p>
      <p v-if="actionError.hint" class="text-ch-text-tertiary">{{ actionError.hint }}</p>
    </ConflictBanner>

    <!-- 重新渲染命中 inputHash 复用（裁定 D：不得让用户误以为重新渲染了） -->
    <ConflictBanner
      v-if="reuseNotice"
      type="info"
      title="输入未变化，已复用既有产物"
      :actions="[{ key: 'artifacts', label: '查看产物' }]"
      closable
      @action="goArtifacts(reuseNotice.jobID)"
      @close="reuseNotice = null"
    >
      未新建任务：后端 inputHash 命中既有 DONE 任务并返回 reused=1{{ reuseNotice.jobCode ? `（复用 ${reuseNotice.jobCode}）` : '' }}。
    </ConflictBanner>

    <!-- 轮询暂停（连续失败 3 次） -->
    <ConflictBanner
      v-if="pollPaused"
      type="warning"
      title="自动刷新已暂停"
      :actions="[{ key: 'refresh', label: '手动刷新' }]"
      @action="manualRefresh"
    >
      连续 {{ pollFailures }} 次自动刷新失败，已停止轮询（轮询失败不弹全局提示）。手动刷新成功后自动恢复。
    </ConflictBanner>

    <ErrorState
      v-if="error"
      :message="error"
      :detail="errorDetail"
      hint="渲染任务读取失败，请检查网络或稍后重试；若持续失败请联系管理员。"
      @retry="manualRefresh"
    />

    <template v-else>
      <!-- role=status + aria-live：任务状态变化的播报容器（计划 Step 11 要点 6） -->
      <div class="ch-card ch-card--compact" role="status" aria-live="polite" :aria-busy="loading ? 'true' : 'false'">
        <Skeleton v-if="loading && !rows.length" type="table" :rows="8" label="渲染任务加载中" />

        <el-table
          v-else
          ref="tableRef"
          :data="visibleRows"
          row-key="recID"
          :expand-row-keys="expandKeys"
          :header-cell-style="headerCellStyle"
          :cell-style="cellStyle"
          :row-style="rowStyle"
          @row-click="onRowClick"
          @expand-change="onExpandChange"
        >
          <!-- ★ 列插槽一律写 `v-slot:default`，不用井号简写：`default` 的前四个字母恰好构成 4 位
               十六进制，会被 scripts/lint-hex.mjs 的色值正则误判（与 components/base/AppTable.vue 同一写法）。 -->
          <!-- 展开控件列（40px，无表头文案；非数据列） -->
          <el-table-column type="expand" width="40" :resizable="false">
            <template v-slot:default="{ row }">
              <JobFailDetail v-if="row.jobStatus === 'FAILED'" :job="row" @retry="onRetry(row)" @rerender="onRerender(row)" />
              <p v-else class="px-lg py-md break-all text-body-s text-ch-text-tertiary">
                该任务暂无失败原因（当前状态：{{ statusLabel(row.jobStatus) }}）；inputHash
                {{ row.inputHash || '—' }} · 版式 {{ row.layoutCode || '—' }} · 开始
                {{ formatYMDHMS(row.startYMDHMS) || '—' }}
              </p>
            </template>
          </el-table-column>

          <el-table-column label="任务号" width="140">
            <template v-slot:default="{ row }">
              <span class="font-mono text-code text-ch-text-primary" :title="`recID: ${row.recID || '—'}`">
                {{ row.jobCode || '—' }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="主题" min-width="220">
            <template v-slot:default="{ row }">
              <RouterLink
                v-if="topicCodeOf(row)"
                :to="{ name: 'TopicEdit', params: { code: topicCodeOf(row) } }"
                class="block truncate text-body-s text-ch-primary hover:text-ch-primary-hover"
                :title="titleOf(row)"
              >
                {{ titleOf(row) }}
              </RouterLink>
              <span v-else class="block truncate text-body-s text-ch-text-secondary" :title="titleOf(row)">
                {{ titleOf(row) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="版式" width="170">
            <template v-slot:default="{ row }">
              <span class="font-mono text-code text-ch-text-primary">{{ row.layoutCode || '—' }}</span>
              <span v-if="layoutLabelOf(row)" class="ml-xs text-caption text-ch-text-tertiary">{{ layoutLabelOf(row) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="状态" width="120">
            <template v-slot:default="{ row }">
              <div class="flex flex-col gap-xs">
                <StateBadge domain="job" :status="row.jobStatus" />
                <span v-if="progressText(row)" class="text-caption tabular-nums text-ch-text-tertiary">
                  {{ progressText(row) }}
                </span>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="耗时" width="90" align="right">
            <template v-slot:default="{ row }">
              <span class="tabular-nums text-body-s text-ch-text-secondary">{{ formatDuration(row.costMs) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="200" fixed="right">
            <template v-slot:default="{ row }">
              <div class="flex flex-wrap items-center gap-md">
                <button
                  v-if="canCancel(row)"
                  type="button"
                  class="text-body-s text-ch-danger hover:underline"
                  @click.stop="openCancel(row)"
                >
                  取消
                </button>
                <button
                  v-if="canRetry(row)"
                  type="button"
                  class="text-body-s text-ch-primary hover:text-ch-primary-hover"
                  @click.stop="onRetry(row)"
                >
                  重试
                </button>
                <button
                  v-if="canRerender(row)"
                  type="button"
                  class="text-body-s text-ch-primary hover:text-ch-primary-hover"
                  @click.stop="onRerender(row)"
                >
                  重新渲染
                </button>
                <RouterLink
                  v-if="canViewArtifacts(row)"
                  :to="artifactsRoute(row)"
                  class="text-body-s text-ch-primary hover:text-ch-primary-hover"
                >
                  查看产物
                </RouterLink>
                <button
                  v-if="row.jobStatus === 'FAILED'"
                  type="button"
                  class="text-body-s text-ch-text-secondary hover:text-ch-text-primary"
                  :aria-expanded="isExpanded(row) ? 'true' : 'false'"
                  :aria-controls="panelIdOf(row)"
                  @click.stop="toggleExpand(row)"
                >
                  {{ isExpanded(row) ? '收起失败原因' : '查看失败原因' }}
                </button>
                <button
                  v-else-if="canDetail(row)"
                  type="button"
                  class="text-body-s text-ch-text-secondary hover:text-ch-text-primary"
                  :aria-expanded="isExpanded(row) ? 'true' : 'false'"
                  @click.stop="toggleExpand(row)"
                >
                  {{ isExpanded(row) ? '收起详情' : '查看详情' }}
                </button>
              </div>
            </template>
          </el-table-column>

          <template #empty>
            <EmptyState
              :title="emptyTitle"
              :description="emptyDescription"
              :action-text="filterActive ? '清除筛选' : '去主题库'"
              @action="onEmptyAction"
            />
          </template>
        </el-table>
      </div>

      <AppPagination
        :total="total"
        :page-size="size"
        :current-page="page"
        :disabled="loading"
        @page-change="onPageChange"
      />
    </template>

    <!-- 取消任务二次确认（裁定 C：动词按钮「确认取消任务」） -->
    <AppDialog
      v-model="cancelVisible"
      title="取消渲染任务"
      danger
      confirm-text="确认取消任务"
      :confirm-loading="canceling"
      @confirm="submitCancel"
    >
      <p>
        确认取消任务
        <span class="font-mono text-ch-text-primary">{{ cancelTarget?.jobCode || '—' }}</span>
        （{{ cancelTitle }}）？
      </p>
      <p class="mt-sm text-caption text-ch-text-tertiary">
        后端渲染任务状态机只允许 PENDING → FAILED：取消将以「jobStatus=FAILED + errMsg=USER_CANCELED」表达，
        已占用的渲染资源不会回滚。
      </p>
    </AppDialog>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { toast } from 'vue3-toastify'
import AppButton from '@/components/base/AppButton.vue'
import AppDialog from '@/components/base/AppDialog.vue'
import AppPagination from '@/components/base/AppPagination.vue'
import ConflictBanner from '@/components/base/ConflictBanner.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import Skeleton from '@/components/base/Skeleton.vue'
import StateBadge from '@/components/biz/StateBadge.vue'
import JobFailDetail from '@/views/renderJobs/JobFailDetail.vue'
import { tokens } from '@/js/tokens'
import { JOB_STATUS_MAP } from '@/config/chOptions'
import { formatDuration, formatYMDHMS } from '@/utils/common'
import {
  JOB_STATUS_ORDER,
  allowedActions,
  describeJobError,
  layoutLabelOf,
  str,
  useJobPolling
} from '@/views/renderJobs/useJobPolling'

const route = useRoute()
const router = useRouter()
const tableRef = ref(null)

/* ==========================================================================
 * 1. 筛选（URL query 为单一来源；消费 ?jobStatus=FAILED 与 ?topicID=<recID>）
 * ======================================================================== */

/** 从 URL query 解析筛选（非法状态值一律回落「全部」，避免脏 query 打崩列表） */
function readQuery(query) {
  const status = str(query.jobStatus).toUpperCase()
  return {
    jobStatus: JOB_STATUS_ORDER.includes(status) ? status : '',
    topicID: str(query.topicID),
    keyword: str(query.keyword)
  }
}

const {
  rows,
  visibleRows,
  total,
  page,
  size,
  loading,
  refreshing,
  error,
  errorDetail,
  filters,
  filterActive,
  titleMap,
  emptyTitle,
  emptyDescription,
  hasActiveJobs,
  pollingActive,
  pollPaused,
  pollFailures,
  lastLoadedAt,
  load,
  setFilters,
  goPage,
  changeSize,
  cancelJob,
  retryJob,
  rerenderTopic
} = useJobPolling({ ...readQuery(route.query), page: route.query.page })

/** 筛选 → URL query（缺省值不写入，保持链接干净） */
function syncUrl() {
  const query = {}
  if (filters.jobStatus) query.jobStatus = filters.jobStatus
  if (filters.topicID) query.topicID = filters.topicID
  if (filters.keyword) query.keyword = filters.keyword
  if (page.value > 1) query.page = String(page.value)
  router.replace({ path: '/render-jobs', query })
}

/** 应用筛选（回到第 1 页）并同步 URL */
function applyFilter(patch = {}) {
  setFilters({ jobStatus: filters.jobStatus, topicID: filters.topicID, keyword: filters.keyword, ...patch })
  syncUrl()
}

function clearFilters() {
  applyFilter({ jobStatus: '', topicID: '', keyword: '' })
}

/** 路由 query 变化（工作台跳转 / 前进后退 / 手改地址）→ 重新取数 */
watch(
  () => route.query,
  (query) => {
    const next = readQuery(query)
    const filterChanged =
      next.jobStatus !== filters.jobStatus || next.topicID !== filters.topicID || next.keyword !== filters.keyword
    if (filterChanged) {
      setFilters(next)
      return
    }
    const nextPage = Math.max(1, Number(query.page) || 1)
    if (nextPage !== page.value) goPage(nextPage)
  }
)

/* ==========================================================================
 * 2. 表格样式（与 AppTable 同一套 Token 口径：表头 40 / 行 44 / 单元格内边距 16）
 * ======================================================================== */

const headerCellStyle = () => ({
  height: `${tokens.layout.tableHeadH}px`,
  padding: `0 ${tokens.layout.cellPadX}px`,
  backgroundColor: tokens.bg.elevated,
  color: tokens.text.secondary,
  fontSize: `${tokens.fontSize.bodyS}px`,
  fontWeight: 500
})

const cellStyle = () => ({
  padding: `0 ${tokens.layout.cellPadX}px`,
  borderBottom: `1px solid ${tokens.border.default}`,
  color: tokens.text.primary,
  fontSize: `${tokens.fontSize.bodyS}px`
})

const rowStyle = () => ({ height: `${tokens.layout.tableRowH}px` })

/* ==========================================================================
 * 3. 列渲染与派生
 * ======================================================================== */

const statusLabel = (status) => JOB_STATUS_MAP[str(status)]?.label || str(status) || '未知'
const titleOf = (row) => str(row.topicTitle) || str(titleMap.value[str(row.topicID)]?.title) || `主题 #${row.topicID || '—'}`
const topicCodeOf = (row) => str(row.topicCode) || str(titleMap.value[str(row.topicID)]?.topicCode)
const artifactsRoute = (row) => ({ path: '/artifacts', query: { jobID: str(row.recID) } })

/** ★ 不使用进度条（R-06）：仅文本百分比 / 「进行中」；`PENDING` 不显示（徽章「排队中」已表达） */
function progressText(row) {
  if (row.jobStatus !== 'RUNNING') return ''
  const progress = Number(row.progress) || 0
  return progress > 0 ? `${progress}%` : '进行中'
}

/** 操作按钮白名单（裁定 B：非法动作不渲染，永远不出现 DONE→PENDING 之类入口） */
const canCancel = (row) => allowedActions(row.jobStatus).includes('cancel')
const canRetry = (row) => allowedActions(row.jobStatus).includes('retry')
/**
 * 「重新渲染」= 调 `topicrender` 建新任务，而 `layoutCode` 是该端点的**必填项**
 * （renderService.py:775-777 缺 → C4）→ 无版式的任务**不渲染该入口**，避免「点了必然失败」
 * （自测实测：Mock 部分主题无 layoutCode，点击后本地 C4 失败）。
 */
const canRerender = (row) => allowedActions(row.jobStatus).includes('rerender') && Boolean(str(row.layoutCode))
const canViewArtifacts = (row) => allowedActions(row.jobStatus).includes('artifacts')
const canDetail = (row) => allowedActions(row.jobStatus).includes('detail')

/* ==========================================================================
 * 4. 失败行展开（el-table 展开行 + 受控 expand-row-keys）
 * ======================================================================== */

const expandKeys = ref([])
const isExpanded = (row) => expandKeys.value.includes(str(row.recID))
const panelIdOf = (row) => `job-fail-${str(row.recID) || 'unknown'}`

function toggleExpand(row) {
  const key = str(row.recID)
  expandKeys.value = expandKeys.value.includes(key) ? [] : [key]
}

function onExpandChange(unused, expandedRows) {
  if (Array.isArray(expandedRows)) {
    expandKeys.value = expandedRows.map((item) => str(item.recID))
  }
}

/** 整行点击展开：仅失败行（鼠标便利；键盘路径由操作列的触发按钮提供） */
function onRowClick(row, column, event) {
  if (event?.target?.closest?.('a, button, input, label')) return
  if (row.jobStatus !== 'FAILED') return
  toggleExpand(row)
}

/* ==========================================================================
 * 5. 动作：取消（二次确认）/ 重试 / 重新渲染 / 跳转
 * ======================================================================== */

const cancelVisible = ref(false)
const cancelTarget = ref(null)
const canceling = ref(false)
/** 动作失败的行内说明（C7 带 `currentStatus` / `allowedTransitions`） */
const actionError = ref(null)
/** 「重新渲染」命中复用时的提示（裁定 D） */
const reuseNotice = ref(null)

const cancelTitle = computed(() => titleOf(cancelTarget.value || {}))

function openCancel(row) {
  cancelTarget.value = row
  cancelVisible.value = true
}

/** 取消：`renderjobmodify({ recID, jobStatus:'FAILED', errMsg:'USER_CANCELED' })`（裁定 C） */
async function submitCancel() {
  if (!cancelTarget.value) return
  canceling.value = true
  try {
    const result = await cancelJob(cancelTarget.value)
    cancelVisible.value = false
    toast.success(`已取消任务 ${result.jobCode || result.recID}`)
  } catch (e) {
    // 非 B0 已由 utils/http.js toast MSG.content；此处再给出行内说明（HTTP 路径不回显状态机信息）
    actionError.value = { title: '取消任务失败', ...describeJobError(e) }
    console.error('[P-06] 取消任务失败', e)
  } finally {
    canceling.value = false
  }
}

/** 重试（裁定 D）：沿用原输入重新入队，无新任务号 */
async function onRetry(row) {
  try {
    const result = await retryJob(row)
    toast.success(`任务 ${result.jobCode || result.recID} 已重新入队（PENDING）`)
  } catch (e) {
    actionError.value = { title: '重试失败', ...describeJobError(e) }
    console.error('[P-06] 重试失败', e)
  }
}

/** 重新渲染（裁定 D）：建新任务；`reused='1'` 时显式提示「已复用既有产物」 */
async function onRerender(row) {
  try {
    const result = await rerenderTopic(row)
    if (result.reused === '1') {
      reuseNotice.value = result
      toast.info('输入未变化，已复用既有产物')
      return
    }
    toast.success(`已创建新渲染任务 ${result.jobCode || ''}（${result.jobStatus || 'PENDING'}）`)
  } catch (e) {
    actionError.value = { title: '重新渲染失败', ...describeJobError(e) }
    console.error('[P-06] 重新渲染失败', e)
  }
}

/** `DONE` → 产物台账（Step 12 落点；`jobID` = `ch_render_job.recID`，与 ch_artifact.jobID 口径一致） */
function goArtifacts(jobID) {
  if (!str(jobID)) return
  router.push({ path: '/artifacts', query: { jobID: str(jobID) } })
}

function onEmptyAction() {
  if (filterActive.value) clearFilters()
  else router.push('/topics')
}

/* ==========================================================================
 * 6. 分页 / 生命周期
 * ======================================================================== */

/** 分页回调：条数变化与页码变化合并为一次请求（避免连打两次） */
function onPageChange({ page: nextPage, size: nextSize }) {
  const target = Math.max(1, Number(nextPage) || 1)
  const targetSize = Number(nextSize) || size.value
  if (targetSize === size.value) {
    if (target !== page.value) goPage(target)
  } else {
    // AppPagination 在切换每页条数时同时回传 page=1，changeSize 已重置页码并重取
    changeSize(targetSize)
  }
  syncUrl()
}

const manualRefresh = () => load()

onMounted(() => {
  // 首屏取数；初筛自此固定（后续变更由 applyFilter / 路由 watch 驱动）
  console.info('[P-06] 初始筛选（来自 URL query）', readQuery(route.query))
  load()
})
</script>
