<!-- ============================================================================
 * AssetGrid · P-04 素材网格（Step 8，独立文件）
 * ----------------------------------------------------------------------------
 * 规格（计划 Step 8 要点 1 + 裁定 G）：
 *   · `grid-auto-fit minmax(200px,1fr)`；缩略图 4:3、圆角 8（由 `AssetThumb` 承载）；
 *   · hover 的「查看 / 移除」是 `AssetThumb` 内的**可聚焦按钮**（非 div + click）；
 *   · `srcset`（320/640/1280）+ `loading="lazy"` 由 `AssetThumb` 实际输出；
 *   · `alt` 取图注，无图注时用**原始文件名**兜底并提示补图注（不产出空 alt）；
 *   · `dedupHit='1'` 的素材原位覆盖「⚠ 重复（已存在）」标记（裁定 F，不静默跳过）。
 * 说明：引用数为**当前页**反查结果（附录 B R-17 / R-20），未查完时显示「引用查询中…」。
 * ========================================================================== -->
<template>
  <div>
    <Skeleton v-if="loading && !rows.length" type="card" :rows="4" label="素材加载中" />

    <EmptyState
      v-else-if="!rows.length"
      icon="fa fa-image"
      :title="emptyTitle"
      :description="emptyDescription"
      :action-text="emptyActionText"
      @action="emit('empty-action')"
    />

    <ul v-else class="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-lg" role="list">
      <li v-for="row in rows" :key="row.recID || row.fileID" class="flex flex-col gap-xs">
        <AssetThumb
          :url="row.fileUrl || row.imageUrl"
          :thumbnail-url="row.thumbnailUrl"
          :thumbnails="row.thumbnails || null"
          :caption="row.label"
          :alt="altOf(row)"
          :duplicated="isDuplicated(row)"
          aspect="4:3"
          sizes="(max-width: 640px) 50vw, 240px"
          @view="emit('view', row)"
          @remove="emit('remove', row)"
        />
        <p class="flex items-center justify-between gap-sm text-caption text-ch-text-tertiary">
          <span>{{ dimensionOf(row) }}</span>
          <span :class="refClass(row.fileID)">{{ refText(row.fileID) }}</span>
        </p>
        <p v-if="isDuplicated(row)" class="text-caption text-ch-warning">⚠ 重复（已存在）· 已去重复用既有素材</p>
        <p v-if="isOversize(row)" class="text-caption text-ch-warning">超 1920px，服务端将等比压缩</p>
      </li>
    </ul>
  </div>
</template>

<script setup>
import AssetThumb from '@/components/biz/AssetThumb.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import Skeleton from '@/components/base/Skeleton.vue'

const MAX_PIC = 1920

const props = defineProps({
  rows: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  /** fileID → { state: 'idle'|'loading'|'ready'|'error', count }（当前页引用反查结果） */
  refCounts: { type: Object, default: () => ({}) },
  /** 本次会话中 `dedupHit='1'` 的 fileID 列表 */
  dedupFileIds: { type: Array, default: () => [] },
  emptyTitle: { type: String, default: '还没有素材' },
  emptyDescription: { type: String, default: '' },
  emptyActionText: { type: String, default: '' }
})

const emit = defineEmits(['view', 'remove', 'empty-action'])

const dimensionOf = (row) => (row.width && row.height ? `${row.width}×${row.height}` : '尺寸未知')
const altOf = (row) => String(row.label || row.origName || row.fileName || '素材图，图注待补充')
const isOversize = (row) => Number(row.width) > MAX_PIC || Number(row.height) > MAX_PIC
const isDuplicated = (row) =>
  String(row.dedupHit) === '1' || props.dedupFileIds.includes(String(row.fileID || ''))

const infoOf = (fileID) => props.refCounts[String(fileID || '')]
const refText = (fileID) => {
  const info = infoOf(fileID)
  if (!info || info.state === 'idle' || info.state === 'loading') return '引用查询中…'
  if (info.state === 'error') return '引用状态未知'
  return `引用 ${info.count} 处`
}
const refClass = (fileID) => (infoOf(fileID)?.state === 'error' ? 'text-ch-warning' : 'text-ch-text-tertiary')
</script>
