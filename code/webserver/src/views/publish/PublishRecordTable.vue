<!-- ============================================================================
 * PublishRecordTable · P-10 / P-03 Tab5「发布记录表」（Step 14）
 * ----------------------------------------------------------------------------
 * 【后端事实（服从）】
 *   · `ch_publish_record`（`database/ch_publish_record.txt`）**无主题标题列**、**无 autoPublishFlag 列**；
 *     列名为 `artifactId`（小写 d，§待确认项）。→ 主题标题按 `topicID` 补取 `topicqry`：
 *     **当前页去重 + 并发 + 跨刷新缓存**（与 Step 11 `useJobPolling` 同一模式，N+1 上限 = 页大小）。
 *   · 服务端筛选（附录 B R-28 手改 `funcPublishrecordqry`）：`idempotencyKey / artifactID / topicID /
 *     platform / success / beginYMDHMS / endYMDHMS / order`；★ 时间范围作用于 `pushedYMDHMS`
 *     （`mysqlCommon.query_ch_publish_record:513-514`）；`order:'modify'` → `modifyYMDHMS DESC`。
 *   · 结果口径（本步定死，与后端 `success + delFlag` 组合表达一致）：
 *     `success==='1' && delFlag!=='1'` → 成功（绿，`fa-circle-check`）；
 *     `success==='1' && delFlag==='1'` → **已撤销**（灰，`fa-ban`）；
 *     `success!=='1'` → 失败（红，`fa-circle-xmark`）。三种都是「图标 + 颜色 + 文字」三重编码。
 *   · ★ 数据层默认 `delFlag='0' OR delFlag IS NULL` → 已撤销记录**默认不再出现在列表**（待确认项）。
 *     本表在本会话内被撤销的行会先本地标记「已撤销」，再刷新（刷新后若消失由宿主页给出说明）。
 *   · 数值字段一律字符串返回（R-26）→ 比较前 `Number()` / `String()` 归一。
 *
 * 【交互】时间范围**必填**（默认近 7 天）：清空即给出必填提示并**不发请求**；范围与平台/结果写入
 *   URL query（`sync-query`，仅 P-10；Tab5 固定主题且不污染 `?tab=`，与 Step 12 Tab4 同款口径）。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-lg">
    <!-- ① 筛选（全部服务端筛选） -->
    <div class="flex flex-wrap items-end gap-md rounded-xl border border-ch-border bg-ch-surface px-xl py-lg">
      <label class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">开始日期（必填）</span>
        <input
          v-model="filters.beginDate"
          type="date"
          class="h-9 rounded-lg border bg-ch-input px-sm text-body-s text-ch-text-primary"
          :class="rangeMissing ? 'border-ch-danger' : 'border-ch-border'"
          aria-label="按投递时间筛选：开始日期"
          @change="applyFilters()"
        />
      </label>

      <label class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">结束日期（必填）</span>
        <input
          v-model="filters.endDate"
          type="date"
          class="h-9 rounded-lg border bg-ch-input px-sm text-body-s text-ch-text-primary"
          :class="rangeMissing ? 'border-ch-danger' : 'border-ch-border'"
          aria-label="按投递时间筛选：结束日期"
          @change="applyFilters()"
        />
      </label>

      <label class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">平台</span>
        <select
          v-model="filters.platform"
          class="h-9 rounded-lg border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
          aria-label="按平台筛选"
          @change="applyFilters()"
        >
          <option value="">全部平台</option>
          <option v-for="code in PLATFORM_ORDER" :key="code" :value="code">{{ platformLabel(code) }}</option>
        </select>
      </label>

      <label class="flex flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">结果</span>
        <select
          v-model="filters.success"
          class="h-9 rounded-lg border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
          aria-label="按投递结果筛选"
          @change="applyFilters()"
        >
          <option value="">全部结果</option>
          <option value="1">成功</option>
          <option value="0">失败</option>
        </select>
      </label>

      <AppButton size="sm" :disabled="loading" @click="resetFilters">近 7 天</AppButton>
      <AppButton size="sm" icon="fa fa-rotate-right" :loading="loading" @click="refresh()">刷新</AppButton>
    </div>

    <p v-if="rangeMissing" class="text-body-s text-ch-danger" role="alert">
      时间范围为必填项：请选择开始与结束日期（已按近 7 天预填；清空后不会发起请求）。
    </p>

    <p class="text-caption text-ch-text-tertiary">
      共 {{ total }} 条；筛选与排序（order=modify → modifyYMDHMS 倒序）均由服务端 publishrecordqry 执行；
      时间范围作用于 pushedYMDHMS。★ 已撤销记录（delFlag=1）默认不在列表中（后端默认过滤软删）。
    </p>

    <!-- ② 三态 + 表格 -->
    <ErrorState
      v-if="error"
      :message="error"
      hint="发布记录读取失败，请检查网络或稍后重试；若持续失败请核对会话是否有效。"
      @retry="refresh()"
    />

    <template v-else>
      <AppTable
        :columns="columns"
        :rows="displayRows"
        :loading="loading"
        :empty="emptyText.title"
        :empty-description="emptyText.description"
        row-key="recID"
      >
        <template #cell-pushedYMDHMS="{ row }">
          <span :title="String(row.pushedYMDHMS || '')">
            {{ row.pushedYMDHMS ? formatYMDHMS(row.pushedYMDHMS) : '—' }}
          </span>
        </template>

        <template #cell-topic="{ row }">
          <span class="block max-w-[220px] truncate" :title="topicTitle(row)">
            {{ topicTitle(row) }}
          </span>
        </template>

        <template #cell-platform="{ row }">
          <PlatformChip :platform="String(row.platform || '')" />
        </template>

        <template #cell-deliverMode="{ row }">
          <span class="text-body-s text-ch-text-secondary">{{ deliverModeText(row.deliverMode) }}</span>
        </template>

        <template #cell-result="{ row }">
          <span class="inline-flex items-center gap-xs whitespace-nowrap" :style="{ color: resultMeta(row).color }">
            <i :class="resultMeta(row).icon" aria-hidden="true"></i>
            <span>{{ resultMeta(row).label }}</span>
          </span>
        </template>

        <template #cell-remoteID="{ row }">
          <span v-if="row.remoteID" class="inline-flex items-center gap-sm">
            <span class="font-mono text-code text-ch-text-secondary" :title="String(row.remoteID)">
              {{ truncateString(String(row.remoteID), 18) }}
            </span>
            <button
              type="button"
              class="rounded-sm p-xs text-ch-text-tertiary transition-colors duration-150 ease-out hover:bg-ch-hover hover:text-ch-text-primary"
              :aria-label="`复制远端 ID ${row.remoteID}`"
              @click="copyText(row.remoteID)"
            >
              <i class="fa fa-copy" aria-hidden="true"></i>
            </button>
          </span>
          <span v-else class="text-ch-text-tertiary">—</span>
        </template>

        <template #cell-operator="{ row }">
          <span v-if="canSeeOperator" class="inline-flex items-center gap-sm">
            <SourceTag :source="operatorSource(row)" />
            <span class="text-body-s text-ch-text-secondary">{{ row.operator || '—' }}</span>
          </span>
        </template>

        <template #cell-actions="{ row }">
          <div class="flex flex-col gap-sm">
            <div class="flex flex-wrap items-center gap-sm">
              <AppButton size="sm" @click="toggleDetail(row)">
                {{ expandedID === row.recID ? '收起' : '查看' }}
              </AppButton>
              <AppButton
                size="sm"
                icon="fa fa-rotate-right"
                :disabled="!canRetry(row)"
                :disabled-reason="retryReason(row)"
                @click="emit('retry', row)"
              >
                重试
              </AppButton>
              <AppButton
                size="sm"
                type="danger"
                icon="fa fa-rotate-left"
                :disabled="!canRevoke(row)"
                :disabled-reason="revokeReason(row)"
                @click="emit('revoke', row)"
              >
                撤销
              </AppButton>
            </div>

            <!-- 行内展开：errcode + errmsg（含平台原文） -->
            <dl
              v-if="expandedID === row.recID"
              class="flex w-[280px] flex-col gap-xs rounded-lg border border-ch-border bg-ch-input px-md py-sm text-caption"
            >
              <div class="flex gap-sm">
                <dt class="w-16 shrink-0 text-ch-text-tertiary">errcode</dt>
                <dd class="min-w-0 flex-1 break-all font-mono text-ch-text-secondary">{{ row.errcode || '—' }}</dd>
              </div>
              <div class="flex gap-sm">
                <dt class="w-16 shrink-0 text-ch-text-tertiary">errmsg</dt>
                <dd class="min-w-0 flex-1 break-words text-ch-text-secondary">{{ row.errmsg || '—' }}</dd>
              </div>
              <div class="flex gap-sm">
                <dt class="w-16 shrink-0 text-ch-text-tertiary">记录 ID</dt>
                <dd class="min-w-0 flex-1 break-all font-mono text-ch-text-secondary">{{ row.recID || '—' }}</dd>
              </div>
              <div class="flex gap-sm">
                <dt class="w-16 shrink-0 text-ch-text-tertiary">幂等键</dt>
                <dd class="min-w-0 flex-1 break-all font-mono text-ch-text-secondary">{{ row.idempotencyKey || '—' }}</dd>
              </div>
              <div class="flex gap-sm">
                <dt class="w-16 shrink-0 text-ch-text-tertiary">产物</dt>
                <dd class="min-w-0 flex-1 break-all font-mono text-ch-text-secondary">{{ row.artifactId || '—' }}</dd>
              </div>
            </dl>
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
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppButton from '@/components/base/AppButton.vue'
import AppPagination from '@/components/base/AppPagination.vue'
import AppTable from '@/components/base/AppTable.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import PlatformChip from '@/components/biz/PlatformChip.vue'
import SourceTag from '@/components/base/SourceTag.vue'
import { PLATFORM_MAP, PLATFORM_ORDER } from '@/config/chOptions'
import { tokens } from '@/js/tokens'
import { useUserStore } from '@/store/modules/user'
import { topicQry } from '@/api/topic'
import { publishRecordQry } from '@/api/publish'
import { copyText, formatYMDHMS, truncateString } from '@/utils/common'
import { recentRange } from '@/views/publish/usePublishFlow'
import { usePagination } from '@/components/base/composables/usePagination'

const props = defineProps({
  /**
   * 固定主题过滤（`ch_topic.recID`）；Tab5 传入，P-10 传空串表示全部主题。
   * ★ prop 名必须是 `topicId`（小写 d，与 `ArtifactsPanel.vue` 同款）：Vue 对属性名做 `camelize`，
   *   `:topic-id` → `topicId`，**不等于** `topicID` —— 写成 `topicID` 会让 `:topic-id` 落到 attrs 而非 props，
   *   表现为「Tab5 记录子集没有按主题过滤」（本步实测发现并修复）。
   */
  topicId: { type: String, default: '' },
  /** 是否把筛选条件写入 URL query（仅 P-10；Tab5 不写，避免污染 `?tab=`） */
  syncQuery: { type: Boolean, default: false }
})

const emit = defineEmits(['retry', 'revoke'])

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

/** 主题标题缓存（跨刷新共享；键 = `ch_topic.recID`） */
const titleCache = new Map()
const titleVersion = ref(0)

const defaultRange = () => recentRange(7)
const filters = reactive({ beginDate: '', endDate: '', platform: '', success: '' })
const expandedID = ref('')

/** `YYYY-MM-DD` → 14 位 `YYYYMMDDHHMMSS`（起止口径：000000 / 235959） */
const toYMDHMS = (dateText, suffix) => (dateText ? `${String(dateText).replace(/-/g, '')}${suffix}` : '')
/** 14 位 `YYYYMMDDHHMMSS` → `YYYY-MM-DD`（回填日期输入框） */
const toDateInput = (ymdhms) => {
  const value = String(ymdhms || '')
  return value.length >= 8 ? `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}` : ''
}

const rangeMissing = computed(() => !filters.beginDate || !filters.endDate)

const canSeeOperator = computed(() => {
  const roles = Array.isArray(userStore.roles) ? userStore.roles : []
  return roles.includes('administrator') || roles.includes('manager')
})

const columns = computed(() => {
  const list = [
    { key: 'pushedYMDHMS', title: '时间', width: 168 },
    { key: 'topic', title: '主题', minWidth: 200 },
    { key: 'platform', title: '平台', width: 132 },
    { key: 'deliverMode', title: '交付方式', width: 108 },
    { key: 'result', title: '结果', width: 108 },
    { key: 'remoteID', title: '远端 ID', width: 190 }
  ]
  if (canSeeOperator.value) list.push({ key: 'operator', title: '操作者', width: 168 })
  list.push({ key: 'actions', title: '操作', width: 300 })
  return list
})

/* ------------------------------ 取数（服务端分页 + 必填时间范围） ------------------------------ */

const queryParams = () => ({
  ...(props.topicId ? { topicID: props.topicId } : {}),
  ...(filters.platform ? { platform: filters.platform } : {}),
  ...(filters.success ? { success: filters.success } : {}),
  ...(rangeMissing.value
    ? {}
    : {
        beginYMDHMS: toYMDHMS(filters.beginDate, '000000'),
        endYMDHMS: toYMDHMS(filters.endDate, '235959')
      }),
  order: 'modify'
})

const pagination = usePagination(
  async ({ beginNum, endNum }) => {
    // ★ 时间范围必填：缺失时**不发请求**（返回空批，页面给出必填提示）
    if (rangeMissing.value) return { data: [], total: 0 }
    return publishRecordQry({ ...queryParams(), beginNum, endNum })
  },
  { pageSize: 20, immediate: false }
)

const { rows, total, page, size, loading, error } = pagination
const emptyText = computed(() =>
  rangeMissing.value
    ? { title: '请先选择时间范围', description: '时间范围为必填项（默认近 7 天），选择后才会加载记录。' }
    : { title: '暂无发布记录', description: '当前筛选条件下没有投递记录；换个时间范围或清空平台/结果筛选试试。' }
)

/** 当前页 → 补取主题标题（去重 + 并发 + 缓存；失败缓存空值并降级显示 `#topicID`） */
async function ensureTitles(list) {
  const missing = Array.from(new Set(list.map((row) => String(row.topicID || '')).filter((id) => id && !titleCache.has(id))))
  if (!missing.length) return
  await Promise.all(
    missing.map(async (id) => {
      const res = await topicQry({ recID: id }, { silent: true }).catch((e) => e)
      const hit = Array.isArray(res?.data) ? res.data[0] : null
      titleCache.set(id, { title: String(hit?.title || ''), topicCode: String(hit?.topicCode || '') })
    })
  )
  titleVersion.value += 1
}

watch(rows, (list) => {
  if (list.length) ensureTitles(list)
})

const displayRows = computed(() => {
  void titleVersion.value
  return rows.value.map((row) => ({
    ...row,
    _topicTitle: titleCache.get(String(row.topicID || ''))?.title || '',
    _topicCode: titleCache.get(String(row.topicID || ''))?.topicCode || ''
  }))
})

function topicTitle(row) {
  return row._topicTitle || `#${String(row.topicID || '—')}`
}

/** 供宿主页「重试」时把记录解析回主题（`topicID` → `topicCode`） */
function topicRecordOf(topicID) {
  const cached = titleCache.get(String(topicID || ''))
  return cached ? { title: cached.title, topicCode: cached.topicCode } : null
}

/* ------------------------------ 展示口径 ------------------------------ */

const platformLabel = (code) => PLATFORM_MAP[code]?.label || code
const deliverModeText = (mode) => {
  if (String(mode) === 'draft_box') return '草稿投递'
  if (String(mode) === 'asset_pack') return '素材包'
  return String(mode || '—')
}

/** 结果三重编码（★ 见文件头口径，禁止只用颜色表达） */
function resultMeta(row) {
  const success = String(row.success) === '1'
  const revoked = String(row.delFlag) === '1'
  if (!success) return { label: '失败', icon: 'fa fa-circle-xmark', color: tokens.status.danger }
  if (revoked) return { label: '已撤销', icon: 'fa fa-ban', color: tokens.text.tertiary }
  return { label: '成功', icon: 'fa fa-circle-check', color: tokens.status.success }
}

/** `ch_publish_record.operator` 为 loginID 时无法判定来源 → 投递只能从 Web 发起（`source` 缺省 web） */
function operatorSource(row) {
  const key = String(row.operator || '').toLowerCase()
  return ['web', 'api', 'mcp', 'system'].includes(key) ? key : 'web'
}

/* ------------------------------ 动作可用性 ------------------------------ */

const canRetry = (row) => String(row.success) !== '1'
const retryReason = (row) => {
  if (String(row.success) === '1') return '该记录已成功投递：幂等键已绑定，重复提交会命中 F1'
  return ''
}

const canRevoke = (row) => String(row.success) === '1' && String(row.delFlag) !== '1'
const revokeReason = (row) => {
  if (String(row.delFlag) === '1') return '该记录已撤销'
  if (String(row.success) !== '1') return '未成功投递的记录不可撤销（后端返回 C7）'
  return ''
}

function toggleDetail(row) {
  expandedID.value = expandedID.value === row.recID ? '' : String(row.recID)
}

/* ------------------------------ 筛选 / 分页 / URL query ------------------------------ */

function writeQuery() {
  if (!props.syncQuery) return
  router.replace({
    path: route.path,
    query: {
      ...route.query,
      beginYMDHMS: filters.beginDate,
      endYMDHMS: filters.endDate,
      platform: filters.platform || undefined,
      success: filters.success || undefined,
      page: page.value > 1 ? String(page.value) : undefined
    }
  })
}

function readQuery() {
  if (!props.syncQuery) return
  const q = route.query
  const fallback = defaultRange()
  filters.beginDate = toDateInput(q.beginYMDHMS) || toDateInput(fallback.beginYMDHMS)
  filters.endDate = toDateInput(q.endYMDHMS) || toDateInput(fallback.endYMDHMS)
  filters.platform = String(q.platform || '')
  filters.success = String(q.success || '')
  const parsedPage = Number(q.page)
  if (Number.isFinite(parsedPage) && parsedPage > 0) page.value = parsedPage
}

function applyFilters() {
  expandedID.value = ''
  writeQuery()
  pagination.reset()
}

function resetFilters() {
  const range = defaultRange()
  filters.beginDate = toDateInput(range.beginYMDHMS)
  filters.endDate = toDateInput(range.endYMDHMS)
  filters.platform = ''
  filters.success = ''
  page.value = 1
  applyFilters()
}

function onPageChange({ page: nextPage, size: nextSize }) {
  if (nextSize && nextSize !== size.value) {
    pagination.changeSize(nextSize)
  } else if (nextPage !== page.value) {
    pagination.goPage(nextPage)
  }
  writeQuery()
}

/** 供宿主页刷新（撤销 / 投递成功后调用） */
function refresh() {
  expandedID.value = ''
  return pagination.reset()
}

/** 本地标记「已撤销」（后端默认过滤 delFlag=1，刷新后该行可能不再返回，宿主页会给出说明） */
function markRevoked(recID) {
  const target = rows.value.find((row) => String(row.recID) === String(recID))
  if (target) target.delFlag = '1'
}

defineExpose({ refresh, markRevoked, topicRecordOf })

onMounted(() => {
  readQuery()
  if (rangeMissing.value) resetFilters()
  else refresh()
})
</script>
