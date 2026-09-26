<!-- ============================================================================
 * Topics · 主题库（P-02，Step 6）
 * ----------------------------------------------------------------------------
 * 单文件承载「模板 + 筛选 + 服务端分页 + 新建/复制/删除/批量导出」
 *   （§2.1 单文件 ≤600 行；本文件约 420 行，无需拆分子模块）。
 *
 * 取数：`topicqry`（首批）+ `generalnext`（按 indexKey 续取，§2.4.4）；**服务端分页**，
 *   前端不做任何切片（§2.11）。默认请求带 `order: 'modify'`（= modifyYMDHMS DESC，全量排序）。
 *
 * 筛选参数与真实后端严格一致（裁定 B）：`keyword` / `status`（单值）/ `beginYMDHMS`+`endYMDHMS`
 *   （作用在 **regYMDHMS = 创建时间**）；★ 不使用不存在的 `searchOption`，不渲染平台筛选（无 platform 参数）。
 *   筛选项全部写入 URL query（b5），刷新与分享后保持；URL 变化（前进/后退/手改地址）会重新取数。
 *
 * ★ 平台列 = 计划方案 C（裁定 C，已核实源码、A/B 均不可行）：
 *   `ch_topic` 无平台字段；平台需聚合 `ch_render_job.platform` / `ch_artifact.platform`，
 *   但 `crudApi.funcRenderjobQry`（crudApi.py:1327-1385）与 `funcArtifactQry`（:1796+）**只支持按自身
 *   recID 过滤**——底层 `query_ch_render_job` / `query_ch_artifact` 虽有 `topicID` 入参
 *   （mysqlCommon.py:429-447 / 453-471），两个端点**均未透传 topicID**。
 *   故本期平台列固定显示「—」并给出 Tooltip 说明；登记待确认项：**后端透传 topicID 即可开启**。
 *   ★ 绝不用 mock 独有的 `topic.platform` 冒充平台列数据。
 *
 * 无障碍（裁定 F）：行内「编辑」是 `<RouterLink>`（键盘可达的主入口），`@row-click` 仅作鼠标便利；
 *   操作按钮在行 hover 时显示，但同时保留 `focus-within` 可见路径（键盘 Tab 可达，§2.11 焦点永远可见）。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-lg">
    <header class="flex flex-wrap items-center justify-between gap-md">
      <h1 class="text-h1 text-ch-text-primary">主题库</h1>
      <AppButton type="primary" icon="fa fa-plus" @click="openCreate">新建主题</AppButton>
    </header>

    <!-- 工具栏「原位替换」：未勾选 → 筛选条；已勾选 → 批量条（危险按钮右置 + danger 描边） -->
    <TopicFilterBar
      v-if="!selected.length"
      :keyword="filters.keyword"
      :status="filters.status"
      :range="filters.range"
      :order="filters.order"
      :disabled="loading"
      @update:keyword="applyFilter({ keyword: $event })"
      @update:status="applyFilter({ status: $event })"
      @update:range="applyFilter({ range: $event })"
      @update:order="applyFilter({ order: $event })"
      @reset="resetFilters"
    />
    <div
      v-else
      class="flex flex-wrap items-center justify-between gap-md rounded-xl border border-ch-border bg-ch-surface px-xl py-lg"
      role="toolbar"
      aria-label="批量操作"
    >
      <p class="text-body-s text-ch-text-secondary">
        已选 <span class="font-medium text-ch-text-primary">{{ selected.length }}</span> 项
      </p>
      <div class="flex flex-wrap items-center gap-md">
        <AppButton size="sm" icon="fa fa-xmark" @click="clearSelection">取消</AppButton>
        <AppButton size="sm" icon="fa fa-download" :loading="exporting" @click="batchExport(selected)">
          批量导出
        </AppButton>
        <AppButton size="sm" type="danger" icon="fa fa-trash" @click="openDelete(selected)">批量删除</AppButton>
      </div>
    </div>

    <!-- 部分失败汇总：项目内无 PartialFailure 组件 → 既有 ConflictBanner + 可展开失败清单（裁定 g2） -->
    <ConflictBanner
      v-if="batchResult"
      :type="batchResult.failed.length ? 'warning' : 'info'"
      :title="batchResult.title"
      :actions="batchResult.failed.length ? [{ key: 'toggle', label: showFailures ? '收起失败项' : '展开失败项' }] : []"
      closable
      @action="showFailures = !showFailures"
      @close="batchResult = null"
    >
      <ul v-if="showFailures" class="flex max-h-40 flex-col gap-xs overflow-y-auto">
        <li v-for="item in batchResult.failed" :key="item.title" class="text-body-s">· {{ item.title }}：{{ item.reason }}</li>
      </ul>
      <span v-else>{{ batchResult.detail }}</span>
    </ConflictBanner>

    <ErrorState
      v-if="error"
      :message="error"
      :detail="errorDetail"
      hint="主题列表读取失败，请检查网络或稍后重试；若持续失败请联系管理员。"
      @retry="refresh()"
    />

    <template v-else>
      <div @mouseover="onRowHover" @mouseleave="hoverRecID = ''">
        <AppTable
          ref="tableRef"
          :columns="COLUMNS"
          :rows="rows"
          :loading="loading"
          :skeleton-rows="8"
          selectable
          row-key="recID"
          empty="还没有主题"
          empty-description="创建第一个选题资产"
          empty-action-text="新建主题"
          @empty-action="openCreate"
          @selection-change="onSelectionChange"
          @row-click="onRowClick"
        >
          <template #cell-title="{ row }">
            <RouterLink
              :to="topicRoute(row)"
              :title="row.title"
              class="block truncate text-body-s text-ch-primary hover:text-ch-primary-hover"
            >
              {{ row.title || '（无标题）' }}
            </RouterLink>
          </template>
          <template #cell-status="{ row }">
            <StateBadge domain="topic" :status="row.status" />
          </template>
          <template #cell-platform>
            <span class="text-body-s text-ch-text-tertiary" :title="PLATFORM_HINT">—</span>
          </template>
          <template #cell-assetCount="{ row }">
            <span class="tabular-nums">{{ Number(row.assetCount) || 0 }}</span>
          </template>
          <template #cell-wordCount="{ row }">
            <span class="tabular-nums">{{ Number(row.wordCount) || 0 }}</span>
          </template>
          <template #cell-modifyYMDHMS="{ row }">
            <span class="text-body-s text-ch-text-tertiary" :title="absoluteOf(row)">{{ relativeOf(row) }}</span>
          </template>
          <template #cell-actions="{ row }">
            <div
              class="flex items-center gap-md transition-opacity duration-150 ease-out focus-within:opacity-100"
              :class="hoverRecID === row.recID ? 'opacity-100' : 'opacity-0'"
            >
              <RouterLink :to="topicRoute(row)" class="text-body-s text-ch-primary hover:text-ch-primary-hover">编辑</RouterLink>
              <button type="button" class="text-body-s text-ch-text-secondary hover:text-ch-text-primary" @click.stop="copyTopic(row)">
                复制
              </button>
              <button type="button" class="text-body-s text-ch-danger hover:underline" @click.stop="openDelete([row])">
                删除
              </button>
            </div>
          </template>
        </AppTable>
      </div>

      <AppPagination
        :total="total"
        :page-size="size"
        :current-page="page"
        :disabled="loading"
        @page-change="onPageChange"
      />
    </template>

    <AppDialog
      v-model="createVisible"
      title="新建主题"
      confirm-text="创建并进入编辑"
      :confirm-loading="creating"
      @confirm="submitCreate"
    >
      <FormInput
        v-model="createTitle"
        label="主题标题"
        required
        placeholder="请输入主题标题"
        help="标题 ≤50 字；其余字段进入编辑页后填写，主题编码由后端幂等生成。"
        :word-limit="50"
      />
    </AppDialog>

    <TopicDeleteConfirm v-model="deleteVisible" :topics="deleteTargets" :loading="deleting" @confirm="submitDelete" />
  </section>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { toast } from 'vue3-toastify'
import AppButton from '@/components/base/AppButton.vue'
import AppDialog from '@/components/base/AppDialog.vue'
import AppPagination from '@/components/base/AppPagination.vue'
import AppTable from '@/components/base/AppTable.vue'
import ConflictBanner from '@/components/base/ConflictBanner.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import FormInput from '@/components/base/FormInput.vue'
import StateBadge from '@/components/biz/StateBadge.vue'
import TopicDeleteConfirm from '@/views/topics/TopicDeleteConfirm.vue'
import TopicFilterBar from '@/views/topics/TopicFilterBar.vue'
import { usePagination } from '@/components/base/composables/usePagination'
import { artifactPack } from '@/api/artifact'
import { topicAdd, topicDel, topicQry } from '@/api/topic'
import { generalNext } from '@/api/user'
import { formatYMDHMS, fromNow } from '@/utils/common'

/** 平台列说明：方案 C 的原因 + 开启条件（裁定 C） */
const PLATFORM_HINT =
  '本期不展示平台：ch_topic 无平台字段，且 renderjobqry / artifactqry 未透传 topicID，无法按主题聚合平台。后端透传 topicID 后即可开启。'

/** 列定义：☐ / 标题 / 状态（固定 96px）/ 平台 / 图片 / 字数 / 更新时间 / 操作（右侧固定） */
const COLUMNS = [
  { key: 'title', title: '标题', minWidth: 240 },
  { key: 'status', title: '状态', width: 96 },
  { key: 'platform', title: '平台', width: 180 },
  { key: 'assetCount', title: '图片', width: 88, align: 'right' },
  { key: 'wordCount', title: '字数', width: 96, align: 'right' },
  { key: 'modifyYMDHMS', title: '更新时间', width: 130 },
  { key: 'actions', title: '操作', width: 168, fixed: 'right' }
]

/** 创建时间档位白名单（非法值一律回落 all，避免脏 query 打崩列表） */
const RANGE_VALUES = ['7', '30', '90']
/** 标题上限 50 字（§2.7 业务校验口径） */
const TITLE_MAX = 50

const route = useRoute()
const router = useRouter()
const tableRef = ref(null)

/* ==========================================================================
 * 1. 筛选（URL query 为单一来源）
 * ======================================================================== */

/** 从 URL query 解析筛选（非法值回落缺省） */
function readQuery(query) {
  return {
    keyword: String(query.keyword || ''),
    status: String(query.status || ''),
    range: RANGE_VALUES.includes(String(query.range)) ? String(query.range) : 'all',
    order: query.order === 'create' ? 'create' : 'modify'
  }
}

const filters = reactive(readQuery(route.query))

/** 创建时间档位 → 14 位 YMDHMS（★ 后端作用字段是 regYMDHMS，裁定 b3） */
function rangeToYMDHMS(range) {
  const days = Number(range)
  if (!days) return null
  const end = new Date()
  const begin = new Date(end.getTime() - days * 24 * 60 * 60 * 1000)
  return { beginYMDHMS: formatYMDHMS(begin, 'YYYYMMDDHHmmss'), endYMDHMS: formatYMDHMS(end, 'YYYYMMDDHHmmss') }
}

/** 筛选 → URL query（b5；缺省值不写入，保持链接干净） */
function syncUrl() {
  const query = {}
  if (filters.keyword) query.keyword = filters.keyword
  if (filters.status) query.status = filters.status
  if (filters.range !== 'all') query.range = filters.range
  if (filters.order !== 'modify') query.order = filters.order
  router.replace({ path: '/topics', query })
}

function applyFilter(patch) {
  Object.assign(filters, patch)
  syncUrl()
  reset()
}

function resetFilters() {
  applyFilter({ keyword: '', status: '', range: 'all', order: 'modify' })
}

/* ==========================================================================
 * 2. 取数（服务端分页 + 按 indexKey 续取）
 * ======================================================================== */

const errorDetail = ref('')

/** 首批 topicqry；后续用 generalnext + indexKey 续取（§2.4.4）；forceFlashFlag='1' 强制重查 */
async function requestTopics({ beginNum, endNum, indexKey, forceFlashFlag }) {
  try {
    // 续取自适应：仅当上一批响应带回 indexKey（后端确有查询缓冲）时才走 generalnext；
    // 增量写操作后必须带 forceFlashFlag='1' 重查，避免读到旧缓冲。
    if (indexKey && forceFlashFlag !== '1') {
      const res = await generalNext({ indexKey, beginNum, endNum })
      errorDetail.value = ''
      return res
    }
    const params = { order: filters.order, beginNum, endNum, forceFlashFlag: forceFlashFlag || '0' }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.status) params.status = filters.status
    const range = rangeToYMDHMS(filters.range)
    if (range) Object.assign(params, range)
    const res = await topicQry(params)
    errorDetail.value = ''
    return res
  } catch (e) {
    errorDetail.value = [e?.errCode ? `errCode: ${e.errCode}` : '', e?.MSG?.content || e?.message || '']
      .filter(Boolean)
      .join('\n')
    throw e
  }
}

const { page, size, total, rows, loading, error, goPage, changeSize, refresh, reset } = usePagination(
  requestTopics,
  { pageSize: 20 }
)

/** 路由 query 变化（前进 / 后退 / 手改地址）→ 重新取数；与本地一致时不重复请求 */
watch(
  () => route.query,
  (query) => {
    const next = readQuery(query)
    if (!Object.keys(next).some((key) => next[key] !== filters[key])) return
    Object.assign(filters, next)
    reset()
  }
)

/** 分页组件回调：条数变化与页码变化合并为一次请求（避免连打两次） */
function onPageChange({ page: nextPage, size: nextSize }) {
  if (nextSize && nextSize !== size.value) changeSize(nextSize)
  if (nextPage !== page.value) goPage(nextPage)
}

/* ==========================================================================
 * 3. 表格 DOM 交互（勾选 / 行 hover / 跳转）
 * ======================================================================== */

const selected = ref([])
const hoverRecID = ref('')

function onSelectionChange(list) {
  selected.value = Array.isArray(list) ? list : []
}

/** 表格 ref 的 clearSelection 会同时清掉 el-table 内部选中态与本地副本 */
function clearSelection() {
  tableRef.value?.clearSelection()
  selected.value = []
}

/**
 * 操作列按行 hover 显示（验收 4）：从 DOM 的 `<tr>` 反查行序号再映射回数据，
 * 避免用 scoped 样式穿透 el-table 内部结构（更稳定）。
 */
function onRowHover(event) {
  const tr = event.target?.closest?.('tr.el-table__row')
  const index = tr ? Array.prototype.indexOf.call(tr.parentElement.children, tr) : -1
  hoverRecID.value = index < 0 ? '' : rows.value[index]?.recID || ''
}

const topicRoute = (row) => ({ name: 'TopicEdit', params: { code: row.topicCode } })

/** 鼠标便利：点在链接 / 按钮 / 勾选框上时不重复跳转（键盘路径始终是标题列的 RouterLink） */
function onRowClick(row, column, event) {
  if (event?.target?.closest?.('a, button, input, label')) return
  router.push(topicRoute(row))
}

/** 更新时间为相对时间，绝对时间放 `title` 属性（§2.3.2 + 计划要点 1） */
const relativeOf = (row) => fromNow(row.modifyYMDHMS).text || '—'
const absoluteOf = (row) => fromNow(row.modifyYMDHMS).absolute

/* ==========================================================================
 * 4. 新建 / 复制（裁定 g1）
 * ======================================================================== */

const createVisible = ref(false)
const createTitle = ref('')
const creating = ref(false)

function openCreate() {
  createTitle.value = ''
  createVisible.value = true
}

async function submitCreate() {
  const title = createTitle.value.trim()
  if (!title) {
    toast.error('请输入主题标题')
    return
  }
  creating.value = true
  try {
    const res = await topicAdd({ title })
    createVisible.value = false
    toast.success('主题已创建')
    const code = res?.data?.topicCode
    if (code) router.push({ name: 'TopicEdit', params: { code } })
    else refresh({ forceFlashFlag: '1' })
  } catch (e) {
    // 非 B0 已由 utils/http.js 统一 toast `MSG.content`；★ 保留用户已填标题（§2.5 第 3 条）
    console.error('[topics] 新建主题失败', e)
  } finally {
    creating.value = false
  }
}

/** 复制 = 以 `{原标题} 副本` 调 topicadd，成功后 toast + 刷新列表（不跳转） */
async function copyTopic(row) {
  const suffix = ' 副本'
  const raw = String(row.title || '')
  // 原文过长时截断，避免必然触发后端 C5（标题 ≤50 字）
  const title = `${raw.length + suffix.length > TITLE_MAX ? raw.slice(0, TITLE_MAX - suffix.length) : raw}${suffix}`
  try {
    await topicAdd({ title })
    toast.success('已复制为新主题')
    refresh({ forceFlashFlag: '1' })
  } catch (e) {
    console.error('[topics] 复制主题失败', e)
  }
}

/* ==========================================================================
 * 5. 删除（破坏性二次确认）/ 批量导出（只导出不投递）
 * ======================================================================== */

const deleteVisible = ref(false)
const deleteTargets = ref([])
const deleting = ref(false)
const exporting = ref(false)
const batchResult = ref(null)
const showFailures = ref(false)

function openDelete(list) {
  deleteTargets.value = [...list]
  deleteVisible.value = true
}

/** 逐条删除并汇总：部分失败不中断（保证「成功 N / 失败 M」口径准确） */
async function submitDelete() {
  deleting.value = true
  let success = 0
  const failed = []
  for (const topic of deleteTargets.value) {
    try {
      await topicDel({ recID: topic.recID })
      success += 1
    } catch (e) {
      failed.push({ title: topic.title || topic.recID || '', reason: e?.MSG?.content || e?.errCode || '删除失败' })
    }
  }
  deleting.value = false
  deleteVisible.value = false
  if (failed.length) {
    showFailures.value = true
    batchResult.value = {
      title: `删除完成：成功 ${success} / 失败 ${failed.length}`,
      detail: '以下主题未删除，可展开查看原因。',
      failed
    }
    toast.warning(`成功 ${success} / 失败 ${failed.length}`)
  } else {
    toast.success(`已删除 ${success} 个主题`)
  }
  clearSelection()
  refresh({ forceFlashFlag: '1' })
}

/** 批量导出 = 对选中主题逐条调 `artifactpack`（★ 只导出不投递），逐条汇总结果 */
async function batchExport(targets) {
  exporting.value = true
  let success = 0
  const failed = []
  for (const topic of targets) {
    try {
      const res = await artifactPack({ topicID: topic.recID, topicCode: topic.topicCode })
      if (String(res?.data?.packaged) === '1') success += 1
      else failed.push({ title: topic.title || '', reason: res?.data?.reason || '未生成素材包' })
    } catch (e) {
      failed.push({ title: topic.title || '', reason: e?.MSG?.content || e?.errCode || '导出失败' })
    }
  }
  exporting.value = false
  showFailures.value = failed.length > 0
  batchResult.value = {
    title: `导出完成：成功 ${success} / 失败 ${failed.length}`,
    detail: '未生成素材包的主题通常为「未过合规校验」或「产物已过期」，可展开查看原因。',
    failed
  }
  if (success) toast.success(`成功 ${success} / 失败 ${failed.length}`)
  else toast.error(`成功 0 / 失败 ${failed.length}`)
}

/* ==========================================================================
 * 6. 生命周期
 * ======================================================================== */

onMounted(() => {
  // 消费 Step 5 遗留的 `/topics?create=1`（裁定 g3）：自动打开新建弹窗并清掉该参数
  if (String(route.query.create || '') !== '1') return
  openCreate()
  const query = { ...route.query }
  delete query.create
  router.replace({ path: '/topics', query })
})
</script>
