<!-- ============================================================================
 * ArtifactsPanel · 产物台账「列表主体」（Step 12 · 越界授权文件，裁定 L 已登记）
 * ----------------------------------------------------------------------------
 * 为什么必须独立成文件：`views/Artifacts.vue`（P-07）与 `views/topic/TabArtifacts.vue`
 *   （P-03 Tab4）是**同一套列表**，仅「主题是否固定 / 是否写 URL query」不同；若各写一份必然
 *   出现两套筛选与两种分组。视图层另拆 `ArtifactsList.vue`（卡片 / 表格 + 分组折叠），
 *   以满足「单文件 ≤ 600 行」（§2.1）。
 *
 * ★ 筛选一律走**服务端**（裁定 A；能力已于 2026-09-22 补齐，附录 B R-28）：
 *   `artifactqry` 透传 `jobID / topicID / kind / platform / artifactStatus / order`
 *   （+ `mode` / `beginNum` / `endNum`）。本文件**没有**任何「已加载页内筛选」兜底，
 *   也**不得**出现「后端未透传过滤参数」的说法（那是改造前的旧口径）。
 *   `order` 固定传 `'modify'`（`modifyYMDHMS DESC`，新产物在前；依据
 *   `common/mysqlCommon.py::queryTableGeneral:290-295`）；★ 不得传 `'update'` 等未定义值。
 *   ★ 请求体**不得**出现 `searchOption`（crud 域旧式表达式筛选，本页不使用）。
 *
 * ★ 直达落点（裁定 J，必须消费）：`?jobID=`（Step 11「查看产物」）、`?topicID=`（Tab3/Tab4 互跳），
 *   与 `?view=` / `?page=` 一并写入 URL（仅 P-07；Tab4 固定主题且不写 query，避免污染 `?tab=`）。
 * ★ 主题值域取 `ch_topic.recID`；Tab4 由父级固定传入并隐藏主题筛选控件（裁定 B）。
 * ★ 三态齐备：骨架屏 / `ErrorState`（原因 + 重试 + 详情）/ `EmptyState`（区分「暂无产物」与
 *   「当前筛选无结果」，裁定 A）。★ 页面**不得**出现「立即清理」类按钮（裁定 K）。
 * ★ ZIP 素材包**不登记 `ch_artifact`**（R-10）→ 类型筛选不含 zip；导出入口归 Step 14（裁定 D）。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-lg">
    <!-- ① 筛选：四类下拉 + 任务号，全部作为请求参数下发（服务端过滤） -->
    <div class="flex flex-wrap items-end gap-md rounded-xl border border-ch-border bg-ch-surface px-xl py-lg">
      <div class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">视图</span>
        <div class="flex items-center gap-xs rounded-lg border border-ch-border bg-ch-input p-xs" role="group" aria-label="切换产物视图">
          <button
            v-for="item in VIEW_OPTIONS"
            :key="item.key"
            type="button"
            class="h-7 rounded-md px-sm text-caption transition-colors duration-150 ease-out"
            :class="view === item.key ? 'bg-ch-primary text-ch-text-inverse' : 'text-ch-text-secondary hover:bg-ch-hover'"
            :aria-pressed="view === item.key ? 'true' : 'false'"
            :aria-label="`切换到${item.label}视图`"
            @click="switchView(item.key)"
          >
            {{ item.label }}
          </button>
        </div>
      </div>

      <label v-for="field in selectFields" :key="field.key" class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">{{ field.label }}</span>
        <select
          class="h-9 max-w-[280px] rounded-lg border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
          :aria-label="field.aria"
          :value="filters[field.key]"
          @change="applyField(field.key, $event.target.value)"
        >
          <option value="">{{ field.allLabel }}</option>
          <option v-for="option in field.options" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
      </label>

      <label class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">任务号</span>
        <input
          v-model="jobIdInput"
          class="h-9 w-40 rounded-lg border border-ch-border bg-ch-input px-sm font-mono text-code text-ch-text-primary placeholder:text-ch-text-tertiary"
          type="text"
          placeholder="ch_render_job.recID"
          aria-label="按渲染任务号筛选"
          @change="applyJobID"
        />
      </label>

      <AppButton v-if="filterActive" size="sm" @click="clearFilters">清除筛选</AppButton>
      <AppButton size="sm" icon="fa fa-rotate-right" :loading="loading" @click="refresh">刷新</AppButton>
    </div>

    <p class="text-caption text-ch-text-tertiary">
      共 {{ total }} 个产物；平台 / 类型 / 状态 / 主题 / 任务号五类筛选与排序（order=modify，modifyYMDHMS 倒序）均由服务端
      artifactqry 执行（附录 B R-28）。★ 素材包 ZIP 不登记产物台账（R-10），故类型筛选不含 zip；本页不提供任何「清理 / 导出」入口。
    </p>

    <!-- ② 直达过滤回显（?jobID= / ?topicID=），可逐条清除 -->
    <div v-if="directChips.length" class="flex flex-wrap items-center gap-sm">
      <span
        v-for="chip in directChips"
        :key="chip.key"
        class="flex items-center gap-sm rounded-lg border border-ch-primary/40 bg-ch-primary-subtle px-sm py-xs text-body-s text-ch-text-primary"
      >
        {{ chip.label }}
        <button
          type="button"
          class="text-ch-text-secondary transition-colors duration-150 ease-out hover:text-ch-text-primary"
          :aria-label="`清除过滤：${chip.label}`"
          @click="clearChip(chip.key)"
        >
          <i class="fa fa-times" aria-hidden="true"></i>
        </button>
      </span>
    </div>

    <!-- ③ 行内提示：复用既有产物（不谎称已重新渲染）/ 动作失败（E4 附「去账号管理」） -->
    <ConflictBanner
      v-if="reuseNotice"
      type="info"
      title="输入未变化，已复用既有产物"
      :actions="[{ key: 'focus', label: '查看该任务产物' }]"
      closable
      @action="focusReusedJob"
      @close="reuseNotice = null"
    >
      未新建任务：后端 inputHash 命中既有 DONE 任务并返回 reused=1{{ reuseNotice.jobCode ? `（复用 ${reuseNotice.jobCode}）` : '' }}，
      本次并未重新渲染（仅复用既有产物）。
    </ConflictBanner>

    <ConflictBanner
      v-if="actionError"
      type="warning"
      :title="actionError.title"
      :actions="actionError.accountLink ? [{ key: 'accounts', label: '去账号管理' }] : []"
      closable
      @action="goAccounts"
      @close="actionError = null"
    >
      <p>{{ actionError.message }}</p>
      <p v-if="actionError.hint" class="text-ch-text-tertiary">{{ actionError.hint }}</p>
      <p v-if="actionError.detail" class="font-mono text-code text-ch-text-tertiary">{{ actionError.detail }}</p>
    </ConflictBanner>

    <!-- ④ 三态：错误 / 骨架 / 空 / 列表（卡片视图默认，表格视图可切换） -->
    <ErrorState
      v-if="error"
      :message="error"
      :detail="errorDetail"
      hint="产物台账读取失败，请检查网络或稍后重试；若持续失败请联系管理员。"
      @retry="refresh"
    />

    <template v-else>
      <div class="flex flex-col gap-lg" role="status" aria-live="polite" :aria-busy="loading ? 'true' : 'false'">
        <Skeleton v-if="loading && !rows.length" type="card" :rows="4" label="产物加载中" />
        <EmptyState
          v-else-if="!rows.length"
          :icon="emptyIcon"
          :title="emptyTitleValue"
          :description="emptyDescriptionValue"
          :action-text="emptyActionTextValue"
          @action="onEmptyAction"
        />
        <ArtifactsList
          v-else
          :rows="rows"
          :view="view"
          :rerendering-id="rerenderingID"
          @preview="openPreview"
          @rerender="onRerender"
        />
      </div>

      <AppPagination
        :total="total"
        :page-size="size"
        :current-page="page"
        :disabled="loading"
        @page-change="onPageChange"
      />
    </template>

    <ArtifactPreviewDrawer
      v-model="previewVisible"
      :artifact="previewTarget"
      :rerendering="rerenderingID === previewTarget.recID"
      @rerender="onRerender"
    />
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toast } from 'vue3-toastify'
import AppButton from '@/components/base/AppButton.vue'
import AppPagination from '@/components/base/AppPagination.vue'
import ConflictBanner from '@/components/base/ConflictBanner.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import Skeleton from '@/components/base/Skeleton.vue'
import ArtifactPreviewDrawer from '@/views/artifacts/ArtifactPreviewDrawer.vue'
import ArtifactsList from '@/views/artifacts/ArtifactsList.vue'
import { artifactQry } from '@/api/artifact'
import { topicRender } from '@/api/render'
import { topicQry } from '@/api/topic'
import {
  ARTIFACT_KIND_FILTER_OPTIONS,
  ARTIFACT_STATUS_MAP,
  ERR_CODE_TEXT,
  PLATFORM_MAP,
  PLATFORM_ORDER,
  artifactKindMeta
} from '@/config/chOptions'
import { artifactRetentionText, copyText } from '@/utils/common'
import { usePagination } from '@/components/base/composables/usePagination'

const props = defineProps({
  /** 固定主题过滤（Tab4 传 `ch_topic.recID`）；为空则展示主题筛选控件（P-07） */
  topicId: { type: String, default: '' },
  /** 筛选 / 视图 / 页码与 URL query 双向同步（仅 P-07 开启；Tab4 不写 query） */
  syncQuery: { type: Boolean, default: false },
  emptyIcon: { type: String, default: 'fa fa-file-lines' },
  emptyTitle: { type: String, default: '暂无产物' },
  emptyDescription: { type: String, default: '还没有产物。到主题库选择版式并提交渲染后，产物会登记在这里。' },
  emptyActionText: { type: String, default: '去主题库' }
})

const emit = defineEmits(['empty-action'])

const route = useRoute()
const router = useRouter()

/* ------------------------------ 常量与纯函数 ------------------------------ */
const PAGE_SIZE = 20
const VIEW_OPTIONS = [
  { key: 'card', label: '卡片' },
  { key: 'table', label: '表格' }
]
/** `ch_artifact.artifactStatus` 取值（§2.6 产物状态机） */
const STATUS_ORDER = Object.keys(ARTIFACT_STATUS_MAP)
/** 任务号 / 主题标识：真实后端为 BIGINT，Mock 形如 `RJ000003` → 只拦截明显非法字符 */
const ID_PATTERN = /^[0-9A-Za-z_-]{1,32}$/

const str = (value) => (value === null || value === undefined ? '' : String(value))
const toNum = (value, fallback = 0) => {
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}
const trimTail = (text) => str(text).trim().replace(/[;；]+$/, '')
const platformLabel = (code) => PLATFORM_MAP[code]?.label || str(code)
const kindLabel = (code) => artifactKindMeta(code).label
const statusLabel = (code) => ARTIFACT_STATUS_MAP[str(code).toUpperCase()]?.label || str(code)

/* ------------------------------ 初值（含 ?jobID= / ?topicID= 直达） ------------------------------ */
function readQuery(query = {}) {
  const platform = str(query.platform)
  const kind = str(query.kind).toLowerCase()
  const artifactStatus = str(query.artifactStatus).toUpperCase()
  return {
    platform: PLATFORM_ORDER.includes(platform) ? platform : '',
    kind: ARTIFACT_KIND_FILTER_OPTIONS.includes(kind) ? kind : '',
    artifactStatus: STATUS_ORDER.includes(artifactStatus) ? artifactStatus : '',
    topicID: str(query.topicID),
    jobID: str(query.jobID),
    view: VIEW_OPTIONS.some((item) => item.key === query.view) ? str(query.view) : 'card',
    page: Math.max(1, toNum(query.page, 1))
  }
}

const fixedTopic = computed(() => Boolean(props.topicId))
const initial = fixedTopic.value
  ? { platform: '', kind: '', artifactStatus: '', topicID: props.topicId, jobID: '', view: 'card', page: 1 }
  : props.syncQuery
    ? readQuery(route.query)
    : { platform: '', kind: '', artifactStatus: '', topicID: '', jobID: '', view: 'card', page: 1 }

const filters = reactive({
  platform: initial.platform,
  kind: initial.kind,
  artifactStatus: initial.artifactStatus,
  topicID: initial.topicID,
  jobID: initial.jobID
})
const view = ref(initial.view)
const jobIdInput = ref(initial.jobID)
const topicOptions = ref([])
const previewVisible = ref(false)
const previewTarget = ref({})
const rerenderingID = ref('')
const errorDetail = ref('')
/** 「重新渲染」命中 inputHash 复用（★ 不得谎称已重新渲染） */
const reuseNotice = ref(null)
/** 动作失败的行内说明（E4 附「去账号管理」） */
const actionError = ref(null)

/** 四类下拉筛选项（Tab4 不渲染「主题」控件；选项在 computed 内展开为普通数组） */
const selectFields = computed(() => {
  const fields = []
  if (!fixedTopic.value) {
    fields.push({
      key: 'topicID',
      label: '主题',
      allLabel: '全部主题',
      aria: '按主题筛选',
      options: topicOptions.value
    })
  }
  fields.push(
    {
      key: 'platform',
      label: '平台',
      allLabel: '全部平台',
      aria: '按平台筛选',
      options: PLATFORM_ORDER.map((code) => ({ value: code, label: platformLabel(code) }))
    },
    {
      key: 'kind',
      label: '类型',
      allLabel: '全部类型',
      aria: '按产物类型筛选',
      options: ARTIFACT_KIND_FILTER_OPTIONS.map((code) => ({ value: code, label: kindLabel(code) }))
    },
    {
      key: 'artifactStatus',
      label: '状态',
      allLabel: '全部状态',
      aria: '按产物状态筛选',
      options: STATUS_ORDER.map((code) => ({ value: code, label: statusLabel(code) }))
    }
  )
  return fields
})

/* ------------------------------ 取数（服务端分页 + 服务端筛选） ------------------------------ */
/** 归一化：数值一律 `Number()`（附录 B R-26）；保留期文案统一由 `artifactRetentionText` 产出 */
function normalizeArtifact(raw) {
  const row = raw && typeof raw === 'object' ? raw : {}
  return {
    ...row,
    recID: str(row.recID),
    artifactKey: str(row.artifactKey),
    jobID: str(row.jobID),
    topicID: str(row.topicID),
    kind: str(row.kind).toLowerCase(),
    platform: str(row.platform),
    fileUrl: str(row.fileUrl),
    thumbnailUrl: str(row.thumbnailUrl),
    specNote: str(row.specNote),
    seqNo: toNum(row.seqNo, 1),
    artifactVer: toNum(row.artifactVer, 1),
    sizeBytes: toNum(row.sizeBytes),
    artifactStatus: str(row.artifactStatus).toUpperCase(),
    expireYMDHMS: str(row.expireYMDHMS),
    retention: artifactRetentionText(row.expireYMDHMS),
    regYMDHMS: str(row.regYMDHMS),
    modifyYMDHMS: str(row.modifyYMDHMS)
  }
}

/**
 * 取数：`artifactqry`（免登录端点）→ 服务端过滤 + 服务端分页（keep 信封：`data` 为数组）。
 * ★ 五类筛选**全部**作为请求参数下发；不做任何本地兜底筛选（裁定 A）。
 */
async function fetchArtifacts(params) {
  const payload = {
    mode: 'full',
    beginNum: params.beginNum,
    endNum: params.endNum,
    // 产物随渲染完成即时新增 → 绕过后端查询缓冲（§2.4.3）
    forceFlashFlag: '1',
    order: 'modify',
    platform: filters.platform,
    kind: filters.kind,
    artifactStatus: filters.artifactStatus,
    topicID: props.topicId || filters.topicID,
    jobID: filters.jobID
  }
  console.info('[P-07] artifactqry 实际发出的 payload', payload)
  try {
    const res = await artifactQry(payload)
    return { ...res, data: (Array.isArray(res?.data) ? res.data : []).map(normalizeArtifact) }
  } catch (error) {
    errorDetail.value = [error?.errCode ? `errCode: ${error.errCode}` : '', error?.message || '']
      .filter(Boolean)
      .join('\n')
    throw error
  }
}

const { rows, total, page, size, loading, error, goPage, changeSize, reset, refresh: reload } = usePagination(
  fetchArtifacts,
  { pageSize: PAGE_SIZE, immediate: false }
)
// 深链 `?page=N`（仅 P-07）：赋值即触发取数；`onMounted` 内对 page===1 的路径另行取首屏
if (initial.page > 1) page.value = initial.page

/* ------------------------------ 派生：筛选状态 / 空态文案 ------------------------------ */
const filterActive = computed(() =>
  Boolean(
    filters.platform || filters.kind || filters.artifactStatus || filters.jobID || (!fixedTopic.value && filters.topicID)
  )
)
const emptyTitleValue = computed(() => (filterActive.value ? '当前筛选无结果' : props.emptyTitle))
const emptyDescriptionValue = computed(() =>
  filterActive.value
    ? '没有符合当前筛选条件的产物：五类筛选均由服务端执行（附录 B R-28），可清除筛选查看全部。'
    : props.emptyDescription
)
const emptyActionTextValue = computed(() => (filterActive.value ? '清除筛选' : props.emptyActionText))
/** 直达过滤回显（Tab4 的主题是固定值，不重复展示） */
const directChips = computed(() => {
  const chips = []
  if (filters.jobID) chips.push({ key: 'jobID', label: `任务 ${filters.jobID}` })
  if (!fixedTopic.value && filters.topicID) chips.push({ key: 'topicID', label: `主题 ${filters.topicID}` })
  return chips
})

/* ------------------------------ 筛选 / 视图 / 分页 ------------------------------ */
/** 筛选 → URL query（仅 P-07；缺省值不写入，保持链接干净） */
function syncUrl() {
  if (!props.syncQuery) return
  const query = {}
  if (filters.platform) query.platform = filters.platform
  if (filters.kind) query.kind = filters.kind
  if (filters.artifactStatus) query.artifactStatus = filters.artifactStatus
  if (filters.topicID) query.topicID = filters.topicID
  if (filters.jobID) query.jobID = filters.jobID
  if (view.value !== 'card') query.view = view.value
  if (page.value > 1) query.page = String(page.value)
  router.replace({ path: route.path, query })
}

function applyFilters(patch = {}, options = {}) {
  Object.assign(filters, {
    platform: str(patch.platform ?? filters.platform),
    kind: str(patch.kind ?? filters.kind),
    artifactStatus: str(patch.artifactStatus ?? filters.artifactStatus),
    topicID: str(patch.topicID ?? filters.topicID),
    jobID: str(patch.jobID ?? filters.jobID)
  })
  jobIdInput.value = filters.jobID
  // ★ 先重置页码再同步 URL：否则 syncUrl 会把旧 page 写回 query，路由 watcher 又会把它翻回来
  const task = reset()
  if (!options.fromUrl) syncUrl()
  return task
}

/** 下拉筛选回调（字段名动态） */
function applyField(key, value) {
  applyFilters({ [key]: value })
}

function applyJobID() {
  const next = str(jobIdInput.value).trim()
  if (next && !ID_PATTERN.test(next)) {
    toast.warning('任务号仅支持字母、数字、下划线与连字符（真实后端为 ch_render_job.recID）')
    jobIdInput.value = filters.jobID
    return
  }
  jobIdInput.value = next
  applyFilters({ jobID: next })
}

function clearFilters() {
  applyFilters({ platform: '', kind: '', artifactStatus: '', jobID: '', ...(fixedTopic.value ? {} : { topicID: '' }) })
}

/** 清除单个直达过滤条件（chip 的关闭按钮） */
function clearChip(key) {
  applyFilters({ [key]: '' })
}

function switchView(key) {
  if (view.value === key) return
  view.value = key
  syncUrl()
}

/** 分页回调：条数变化与页码变化合并为一次请求（避免连打两次） */
function onPageChange({ page: nextPage, size: nextSize }) {
  const target = Math.max(1, toNum(nextPage, 1))
  const targetSize = toNum(nextSize, size.value)
  if (targetSize === size.value) {
    if (target !== page.value) goPage(target)
  } else {
    changeSize(targetSize)
  }
  syncUrl()
}

const refresh = () => reload()

function onEmptyAction() {
  if (filterActive.value) clearFilters()
  else emit('empty-action')
}

function openPreview(row) {
  previewTarget.value = row || {}
  previewVisible.value = true
}

/* ------------------------------ 重新渲染（EXPIRED 主操作，裁定 H） ------------------------------ */
async function onRerender(row) {
  const topicID = str(row?.topicID)
  if (!topicID) {
    toast.error('该产物未返回 topicID，无法定位主题')
    return
  }
  rerenderingID.value = str(row?.recID)
  try {
    // `ch_artifact` 无 layoutCode 列 → 点击时经 topicqry 取该主题（R-23：存量库需先执行 DDL）
    const res = await topicQry({ recID: topicID })
    const topic = (Array.isArray(res?.data) ? res.data : [])[0] || null
    if (!topic) {
      toast.error('未查询到该主题，无法重新渲染')
      return
    }
    const layoutCode = str(topic.layoutCode)
    if (!layoutCode) {
      // 裁定 H：layoutCode 为空 → 不发请求，改为「去选版式」引导（等价于「不给按钮」，
      // 并避免列表加载时对每行做 N+1 反查）
      toast.info('该主题未选版式，请先到「版式与平台」选择后发起渲染')
      router.push({ name: 'TopicEdit', params: { code: str(topic.topicCode) || topicID }, query: { tab: 'layout' } })
      return
    }
    const payload = { topicID, layoutCode, renderMode: 'job' }
    console.info('[P-07] topicrender 实际发出的 payload', payload)
    const render = await topicRender(payload)
    // `topicrender` 属 move 形态（P-ENV-01）：业务字段在 `data`
    const data = { ...(render || {}), ...(render?.data && typeof render.data === 'object' ? render.data : {}) }
    if (str(data.reused) === '1') {
      reuseNotice.value = { jobID: str(data.jobID), jobCode: str(data.jobCode), topicID }
      toast.info('输入未变化，已复用既有产物')
      return
    }
    toast.success(`已创建渲染任务 ${str(data.jobCode) || ''}（${str(data.jobStatus) || 'PENDING'}）`)
    router.push({ path: '/render-jobs', query: { topicID } })
  } catch (err) {
    const code = str(err?.errCode || err?.MSG?.errCode || err?.code)
    actionError.value = {
      title: '重新渲染失败',
      message: trimTail(err?.MSG?.content) || ERR_CODE_TEXT[code] || '操作失败',
      hint: ERR_CODE_TEXT[code] || '',
      detail: code ? `errCode: ${code}` : '',
      // E4＝外链图片需转存但凭据缺失 → 与 Step 10 口径一致，给出「去账号管理」
      accountLink: code === 'E4'
    }
    console.error('[P-07] 重新渲染失败', err)
  } finally {
    rerenderingID.value = ''
  }
}

/** 复用命中 → 就地切到该任务的产物（不谎称已重新渲染） */
function focusReusedJob() {
  const jobID = str(reuseNotice.value?.jobID)
  reuseNotice.value = null
  if (!jobID) return
  applyFilters({ jobID })
}

function goAccounts() {
  router.push('/accounts')
}

/* ------------------------------ 主题筛选选项 / 路由同步 / 首屏 ------------------------------ */
async function loadTopicOptions() {
  if (fixedTopic.value) return
  try {
    const res = await topicQry({ order: 'modify', beginNum: 0, endNum: 200 })
    topicOptions.value = (Array.isArray(res?.data) ? res.data : []).map((item) => ({
      value: str(item.recID),
      label: `${str(item.title) || '（无标题）'}（${str(item.topicCode) || str(item.recID)}）`
    }))
  } catch (err) {
    // 主题筛选选项失败不影响产物列表（不白屏）
    console.error('[P-07] 主题筛选选项读取失败', err)
  }
}

if (props.syncQuery) {
  watch(
    () => route.query,
    (query) => {
      const next = readQuery(query)
      const changed = ['platform', 'kind', 'artifactStatus', 'topicID', 'jobID'].some((key) => next[key] !== filters[key])
      if (changed) {
        applyFilters(next, { fromUrl: true })
        return
      }
      if (next.page !== page.value) goPage(next.page)
    }
  )
}

onMounted(() => {
  console.info('[P-07] 初始筛选（来自 URL query / 固定主题）', { ...readQuery(route.query), ...filters, fixedTopic: props.topicId })
  loadTopicOptions()
  // `usePagination` 未开启 immediate：页码 > 1 时由 page 变化触发取数，否则此处取首屏
  if (page.value === 1) refresh()
})
</script>
