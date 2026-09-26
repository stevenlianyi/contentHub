<!-- ============================================================================
 * Assets · 素材图库（P-04，Step 8）
 * ----------------------------------------------------------------------------
 * 本文件**只做视图与编排**（裁定 H：≤600 行，§2.1 硬约束）：上传面板（AssetUploadPanel）、详情抽屉
 * （AssetDetailDrawer）、引用列表（AssetReferenceList）、筛选条（AssetFilterBar）、网格（AssetGrid）、
 * 引用反查（useAssetReferences）、列表与筛选逻辑（useAssetList）均为独立文件（详见产出清单）。
 *
 * 关键口径：
 *   · 取数 `assetqry`（默认 mode:'full'，★ 禁止 short）+ 服务端分页（beginNum/endNum + total）；
 *   · 筛选对照（附录 B R-17）：搜索 → `keyword`、类型 → `fileExt`（服务端支持）；
 *     规格 / 引用状态 → 后端无参数 → **仅当前页**，控件后缀与提示均显式标注，不静默忽略；
 *   · 去重可见（裁定 F）：`dedupHit='1'` → 网格原位「⚠ 重复（已存在）」+ ConflictBanner「该图片已存在，已复用」；
 *   · 删除安全（裁定 D / 附录 B R-21）：未引用可直接删；已引用**先列出引用主题**（可跳转）再删；
 *     确认按钮为「确认删除素材」（danger），★ 不出现「确定」；
 *   · URL query 保持：kw / ext / spec / ref / view / page。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-lg">
    <header class="flex flex-wrap items-center justify-between gap-md">
      <div>
        <h1 class="text-h1 text-ch-text-primary">素材图库</h1>
        <p class="text-body-s text-ch-text-secondary">
          共 {{ total }} 张素材 · 当前文件后端
          <span class="font-mono" :title="BACKEND_HINT">{{ fileBackend }}</span>
        </p>
      </div>
      <AppButton type="primary" icon="fa fa-upload" @click="uploadVisible = true">上传素材</AppButton>
    </header>

    <!-- 去重结果必须可见（裁定 F） -->
    <ConflictBanner v-if="dedupNames.length" type="warning" title="该图片已存在，已复用" closable @close="dedupNames = []">
      下列文件命中既有素材（`assetadd` 返回 `dedupHit='1'`），未重复上传、未新增记录，网格中已原位标记：
      <ul class="mt-xs flex flex-col gap-xs">
        <li v-for="name in dedupNames" :key="name">· {{ name }}</li>
      </ul>
    </ConflictBanner>

    <AssetFilterBar
      :keyword="filters.keyword"
      :ext="filters.fileExt"
      :spec="filters.spec"
      :ref-state="filters.ref"
      :view="filters.view"
      :disabled="loading"
      @update:keyword="applyFilter({ keyword: $event })"
      @update:ext="applyFilter({ fileExt: $event })"
      @update:spec="applyFilter({ spec: $event })"
      @update:ref="applyFilter({ ref: $event })"
      @update:view="applyFilter({ view: $event })"
      @reset="resetFilters"
    />

    <p v-if="pageOnlyFilter" class="flex items-start gap-sm text-caption text-ch-text-tertiary" role="note">
      <i class="fa fa-circle-info mt-[2px]" aria-hidden="true"></i>
      <span>{{ SCOPE_NOTICE }}</span>
    </p>

    <ErrorState
      v-if="error"
      :message="error"
      :detail="errorDetail"
      hint="素材列表读取失败，请检查网络或稍后重试；若持续失败请联系管理员。"
      @retry="refresh()"
    />

    <template v-else>
      <AssetGrid
        v-if="filters.view === 'grid'"
        :rows="visibleRows"
        :loading="loading"
        :ref-counts="refCounts"
        :dedup-file-ids="dedupFileIds"
        :empty-title="rows.length ? '当前页没有符合条件的素材' : '还没有素材'"
        :empty-description="emptyDescription"
        :empty-action-text="rows.length ? '清除筛选' : '上传素材'"
        @view="openDetail"
        @remove="openDelete"
        @empty-action="onEmptyAction"
      />

      <AppTable
        v-else
        :columns="COLUMNS"
        :rows="visibleRows"
        :loading="loading"
        :skeleton-rows="8"
        row-key="recID"
        row-height="compact"
        :empty="rows.length ? '当前页没有符合条件的素材' : '还没有素材'"
        :empty-description="emptyDescription"
        :empty-action-text="rows.length ? '清除筛选' : '上传素材'"
        @empty-action="onEmptyAction"
      >
        <template #cell-origName="{ row }">
          <button
            type="button"
            class="block max-w-[280px] truncate text-left text-body-s text-ch-primary hover:text-ch-primary-hover"
            :title="altOf(row)"
            @click="openDetail(row)"
          >
            {{ row.origName || row.fileName || '（无文件名）' }}
          </button>
        </template>
        <template #cell-fileSystem="{ row }">
          <span class="font-mono text-code text-ch-text-secondary">{{ row.fileSystem || '—' }}</span>
        </template>
        <template #cell-refCount="{ row }">
          <span :class="refClass(row.fileID)">{{ refText(row.fileID) }}</span>
        </template>
        <template #cell-actions="{ row }">
          <div class="flex items-center gap-md">
            <button type="button" class="text-body-s text-ch-primary hover:text-ch-primary-hover" @click="openDetail(row)">查看</button>
            <button type="button" class="text-body-s text-ch-danger hover:underline" @click="openDelete(row)">删除</button>
          </div>
        </template>
      </AppTable>

      <AppPagination :total="total" :page-size="size" :current-page="page" :disabled="loading" @page-change="onPageChange" />
    </template>

    <AppDialog v-model="uploadVisible" title="上传素材" size="lg">
      <AssetUploadPanel :file-backend="fileBackend" @done="onUploaded" />
      <template #footer>
        <AppButton size="md" @click="uploadVisible = false">关闭</AppButton>
      </template>
    </AppDialog>

    <AssetDetailDrawer
      v-model="detailVisible"
      :asset="currentAsset"
      :ref-loading="currentRef.loading"
      :ref-error="currentRef.error"
      :ref-total="currentRef.total"
      :ref-items="currentRef.items"
      :ref-extra-count="currentRef.extraCount"
      @retry-ref="reloadRefs(currentAsset)"
      @saved="onSaved"
      @remove="openDelete(currentAsset)"
    />

    <AssetDeleteConfirm
      v-model="deleteVisible"
      :asset="deleteTarget"
      :deleting="deleting"
      :ref-loading="deleteRef.loading"
      :ref-error="deleteRef.error"
      :ref-total="deleteRef.total"
      :ref-items="deleteRef.items"
      :ref-extra-count="deleteRef.extraCount"
      @retry-ref="reloadRefs(deleteTarget)"
      @confirm="submitDelete"
    />
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { toast } from 'vue3-toastify'
import AppButton from '@/components/base/AppButton.vue'
import AppDialog from '@/components/base/AppDialog.vue'
import AppPagination from '@/components/base/AppPagination.vue'
import AppTable from '@/components/base/AppTable.vue'
import ConflictBanner from '@/components/base/ConflictBanner.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import AssetDetailDrawer from '@/components/biz/AssetDetailDrawer.vue'
import AssetUploadPanel from '@/components/biz/AssetUploadPanel.vue'
import AssetDeleteConfirm from '@/views/assets/AssetDeleteConfirm.vue'
import AssetFilterBar from '@/views/assets/AssetFilterBar.vue'
import AssetGrid from '@/views/assets/AssetGrid.vue'
import { useAssetList } from '@/views/assets/useAssetList'
import { assetDel } from '@/api/asset'
import { formatBytes, formatYMDHMS } from '@/utils/common'

const BACKEND_HINT =
  '无只读端点可获取全局 FILE_SYSTEM_MODE（F9A0 需 digest token，前端不可调用，附录 B R-19）；此处显示已加载素材的 fileSystem 归纳值。'
const SCOPE_NOTICE =
  '「规格 / 引用状态」后端无对应查询参数（附录 B R-17），仅对当前页已加载的素材生效，不是全量筛选。'

const COLUMNS = [
  { key: 'origName', title: '文件名', minWidth: 200 },
  { key: 'size', title: '尺寸', width: 120, render: (row) => dimensionOf(row) },
  { key: 'sizeBytes', title: '大小', width: 110, render: (row) => formatBytes(row.origSizeBytes || row.sizeBytes) },
  { key: 'fileExt', title: '格式', width: 90, render: (row) => String(row.fileExt || '').toUpperCase() || '—' },
  { key: 'fileSystem', title: '后端', width: 110 },
  { key: 'refCount', title: '引用数', width: 140 },
  { key: 'regYMDHMS', title: '上传时间', width: 170, render: (row) => formatYMDHMS(row.regYMDHMS) },
  { key: 'actions', title: '操作', width: 140, fixed: 'right' }
]

const {
  filters,
  page,
  size,
  total,
  rows,
  loading,
  error,
  errorDetail,
  visibleRows,
  pageOnlyFilter,
  refCounts,
  refText,
  refClass,
  fileBackend,
  dimensionOf,
  altOf,
  dedupNames,
  dedupFileIds,
  markDuplicates,
  applyFilter,
  resetFilters,
  onPageChange,
  refresh,
  detailOf,
  fetchDetail
} = useAssetList()

const emptyDescription = computed(() =>
  rows.value.length
    ? '规格 / 引用状态为仅当前页筛选，可翻页或清除筛选。'
    : '上传第一张素材，服务端会自动裁剪、剥离 EXIF 并生成缩略图。'
)

/** 空态主按钮：有数据说明是「仅当前页筛选」筛空了 → 清筛选；无数据 → 去上传 */
function onEmptyAction() {
  if (rows.value.length) resetFilters()
  else uploadVisible.value = true
}

/* ------------------------------- 1. 上传与去重 ------------------------------- */
const uploadVisible = ref(false)

/** 上传结果回填：去重命中项在网格原位标记（裁定 F），并强制重查列表 */
function onUploaded({ results }) {
  markDuplicates(results)
  const success = results.filter((item) => item.status === 'done').length
  const dup = results.filter((item) => item.status === 'dup').length
  if (results.length) toast.success(`上传完成：成功 ${success} / 去重复用 ${dup}`)
  refresh({ forceFlashFlag: '1' })
}

/* ------------------------------- 2. 详情抽屉 ------------------------------- */
const detailVisible = ref(false)
const currentAsset = ref(null)
/** 引用明细直接读组合式函数的响应式缓存（`fetchDetail` 同步置 loading） */
const currentRef = computed(() => detailOf(String(currentAsset.value?.fileID || '')))

function reloadRefs(row) {
  return fetchDetail(String(row?.fileID || ''), { force: true })
}

function openDetail(row) {
  if (!row) return
  currentAsset.value = row
  detailVisible.value = true
  reloadRefs(row)
}

function onSaved(record) {
  if (record?.notice) toast.success(record.notice)
  refresh({ forceFlashFlag: '1' })
}

/* ------------------------------- 3. 安全删除 ------------------------------- */
const deleteVisible = ref(false)
const deleteTarget = ref(null)
const deleting = ref(false)
const deleteRef = computed(() => detailOf(String(deleteTarget.value?.fileID || '')))

/** ★ 引用检查是客户端安全网：真实 assetdel 不做引用检查（附录 B R-21） */
function openDelete(row) {
  if (!row) return
  deleteTarget.value = row
  deleteVisible.value = true
  reloadRefs(row)
}

async function submitDelete() {
  const target = deleteTarget.value
  if (!target) return
  deleting.value = true
  try {
    await assetDel({ recID: target.recID, fileID: target.fileID })
    deleteVisible.value = false
    detailVisible.value = false
    toast.success('素材已删除（软删除）')
    refresh({ forceFlashFlag: '1' })
  } catch (e) {
    // 非 B0 已由 utils/http.js 统一 toast；保留弹窗便于重试或先解绑引用（§2.5）
    console.error('[assets] 删除素材失败', e)
  } finally {
    deleting.value = false
  }
}
</script>
