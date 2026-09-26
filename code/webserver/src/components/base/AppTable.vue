<!-- ============================================================================
 * AppTable · L1 基础组件（Step 4）
 * ----------------------------------------------------------------------------
 * 基于 `el-table`（§2.11：默认用 Element Plus 表格，靠 `--el-table-*` 对齐 Token）。
 * 规格：表头高 40 + bg/elevated + 13px/500/文字 secondary；行高 44（`rowHeight="compact"` → 36）；
 *       单元格横向内边距 16；长文本单行省略 + Tooltip；空态内置 EmptyState；加载优先骨架行。
 * 扩展点：`columns[].render(row)` 返回 VNode（配置数组驱动场景，如开发自测页）或
 *         具名插槽 `#cell-<key>{ row, column, index }`（页面场景，避免 render 函数）。
 * 安全：render 返回的**字符串按文本渲染**（h('span', text)），不使用 v-html。
 * ========================================================================== -->
<template>
  <div class="relative">
    <!-- 加载优先骨架行：与最终表格形状一致（表头 40 + 行 44），避免首屏跳动 -->
    <div v-if="loading && !rows.length" class="ch-card ch-card--compact">
      <Skeleton type="table" :rows="skeletonRows" />
    </div>

    <el-table
      v-else
      ref="tableRef"
      :data="rows"
      :row-key="rowKey"
      :height="height"
      :max-height="maxHeight"
      :header-cell-style="headerCellStyle"
      :cell-style="cellStyle"
      :row-style="rowStyle"
      @row-click="handleRowClick"
      @selection-change="handleSelectionChange"
    >
      <el-table-column v-if="selectable" type="selection" width="48" :reserve-selection="Boolean(rowKey)" />

      <el-table-column
        v-for="column in columns"
        :key="column.key"
        :prop="column.key"
        :label="column.title"
        :width="column.width"
        :min-width="column.minWidth"
        :align="column.align || 'left'"
        :fixed="column.fixed || false"
        :show-overflow-tooltip="isPlain(column)"
      >
        <template v-if="!isPlain(column)" v-slot:default="scope">
          <slot :name="`cell-${column.key}`" :row="scope.row" :column="column" :index="scope.$index">
            <RenderCell :column="column" :row="scope.row" />
          </slot>
        </template>
      </el-table-column>

      <template #empty>
        <slot name="empty">
          <EmptyState
            :title="empty"
            :description="emptyDescription"
            :action-text="emptyActionText"
            @action="emit('empty-action')"
          />
        </slot>
      </template>
    </el-table>

    <!-- 已有数据时的翻页/刷新：局部 spinner 覆盖，容器 aria-busy -->
    <div
      v-if="loading && rows.length"
      class="absolute inset-0 flex items-start justify-center bg-ch-base/40 pt-3xl"
      aria-busy="true"
    >
      <i class="fa fa-circle-notch fa-spin text-xl text-ch-primary" aria-hidden="true"></i>
      <span class="sr-only">加载中</span>
    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, ref, useSlots } from 'vue'
import { tokens } from '@/js/tokens'
import Skeleton from '@/components/base/Skeleton.vue'
import EmptyState from '@/components/base/EmptyState.vue'

const props = defineProps({
  /** [{ key, title, width?, minWidth?, align?, fixed?, render?(row) }] */
  columns: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  /** 空态标题 */
  empty: { type: String, default: '暂无数据' },
  emptyDescription: { type: String, default: '' },
  emptyActionText: { type: String, default: '' },
  selectable: { type: Boolean, default: false },
  rowKey: { type: String, default: '' },
  /** default（44） / compact（36） */
  rowHeight: { type: String, default: 'default' },
  height: { type: [String, Number], default: undefined },
  maxHeight: { type: [String, Number], default: undefined },
  skeletonRows: { type: Number, default: 5 }
})

const emit = defineEmits(['row-click', 'selection-change', 'empty-action'])

const slots = useSlots()
const tableRef = ref(null)

/** 纯文本列才启用 show-overflow-tooltip（自定义 slot / render 的列交给调用方控制） */
const isPlain = (column) => !column.render && !slots[`cell-${column.key}`]

const rowHeightPx = computed(() =>
  props.rowHeight === 'compact' ? tokens.layout.tableRowCompactH : tokens.layout.tableRowH
)

/** 表头：高 40 + bg/elevated + 13px/500 + 文字 secondary（§1.4） */
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

const rowStyle = () => ({ height: `${rowHeightPx.value}px` })

/** 配置数组驱动场景：把 `column.render(row)` 的返回值包成 VNode（字符串安全按文本渲染） */
const RenderCell = defineComponent({
  name: 'AppTableCellRenderer',
  props: { column: { type: Object, required: true }, row: { type: Object, required: true } },
  setup(innerProps) {
    return () => {
      const output = innerProps.column.render ? innerProps.column.render(innerProps.row) : ''
      if (output === null || output === undefined || typeof output === 'boolean') return null
      if (typeof output === 'string' || typeof output === 'number') return h('span', String(output))
      return output
    }
  }
})

const handleRowClick = (row, column, event) => emit('row-click', row, column, event)
const handleSelectionChange = (selection) => emit('selection-change', selection)

defineExpose({
  clearSelection: () => tableRef.value?.clearSelection(),
  toggleRowSelection: (row, selected) => tableRef.value?.toggleRowSelection(row, selected)
})
</script>
