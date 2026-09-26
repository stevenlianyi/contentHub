<!-- ============================================================================
 * ArtifactsList · 产物列表的「两个视图」（Step 12 · 越界授权文件，裁定 L 已登记）
 * ----------------------------------------------------------------------------
 * 拆分理由：`ArtifactsPanel.vue`（筛选 + 取数 + 三态 + 动作编排）加上两套视图会突破
 *   「单文件 ≤ 600 行」（§2.1）硬约束 → 视图层独立成本文件，面板只做编排。
 *
 * 视图：
 *   ① 卡片视图（默认）：按 `jobID` 分组，组头 = 任务号 + 「查看任务」；组内 PNG 按
 *      `Number(seqNo)` **升序**（裁定 F），`seqNo === 1` 标「封面」；支持折叠/展开
 *      （折叠状态是本组件内的 `ref`，**不落库**）。
 *   ② 表格视图：平铺（服务端 `order='modify'` 排序），含「任务」「保留期」列与行内操作；
 *      「下载」在 `EXPIRED` 时为**禁用态 + Tooltip**（`title` 承载文案）。
 *
 * ★ 数据（`rows`）由面板 `normalizeArtifact()` 归一（数值已 `Number()`，保留期文案已生成），
 *   本组件不做取数、不做筛选、不做二次转换。
 * ★ 状态一律 `StateBadge domain="artifact"`（形状图标 + 颜色 + 文字，§2.6）。
 * ★ 无「立即清理 / 导出素材包」入口（清理归后端定时任务，导出归 Step 14）。
 * ========================================================================== -->
<template>
  <!-- 卡片视图（默认）：按 jobID 分组 + 折叠 -->
  <template v-if="view === 'card'">
    <section v-for="group in groups" :key="group.jobID" class="ch-card ch-card--compact flex flex-col gap-md">
      <header class="flex flex-wrap items-center justify-between gap-sm">
        <div class="flex flex-wrap items-center gap-sm">
          <button
            type="button"
            class="inline-flex items-center gap-xs rounded-md px-xs py-[2px] text-body-s text-ch-text-primary transition-colors duration-150 ease-out hover:bg-ch-hover"
            :aria-expanded="isCollapsed(group.jobID) ? 'false' : 'true'"
            :aria-controls="groupPanelId(group.jobID)"
            :aria-label="`${isCollapsed(group.jobID) ? '展开' : '收起'}任务 ${group.jobID} 的产物`"
            @click="toggleGroup(group.jobID)"
          >
            <i :class="isCollapsed(group.jobID) ? 'fa fa-angle-right' : 'fa fa-angle-down'" aria-hidden="true"></i>
            <span class="font-mono text-code">任务 {{ group.jobID }}</span>
          </button>
          <span class="text-caption text-ch-text-tertiary">
            {{ group.items.length }} 个产物 · {{ group.kinds.map(kindLabel).join(' / ') }}
          </span>
          <PlatformChip :platform="group.platform" size="sm" />
        </div>
        <RouterLink :to="jobRoute(group.jobID)" class="text-body-s text-ch-primary hover:text-ch-primary-hover">
          查看任务
        </RouterLink>
      </header>

      <div
        v-show="!isCollapsed(group.jobID)"
        :id="groupPanelId(group.jobID)"
        class="grid gap-lg sm:grid-cols-2 xl:grid-cols-3"
      >
        <ArtifactCard
          v-for="item in group.items"
          :key="item.recID"
          :artifact="item"
          :seq-total="group.items.length"
          :rerendering="rerenderingID === item.recID"
          @preview="emit('preview', $event)"
          @rerender="emit('rerender', $event)"
        />
      </div>
    </section>
  </template>

  <!-- 表格视图：平铺（服务端排序） -->
  <AppTable
    v-else
    :columns="COLUMNS"
    :rows="rows"
    row-height="compact"
    :skeleton-rows="6"
  >
    <template v-slot:cell-kind="{ row }">
      <span class="inline-flex items-center gap-xs text-body-s text-ch-text-primary">
        <i :class="kindMetaOf(row.kind).icon" aria-hidden="true"></i>{{ kindMetaOf(row.kind).label }}
      </span>
    </template>
    <template v-slot:cell-platform="{ row }">
      <PlatformChip :platform="row.platform" size="sm" />
    </template>
    <template v-slot:cell-specNote="{ row }">
      <span class="text-body-s text-ch-text-secondary">{{ row.specNote || '—' }}</span>
    </template>
    <template v-slot:cell-sizeBytes="{ row }">
      <span class="tabular-nums text-body-s text-ch-text-secondary">{{ formatBytes(row.sizeBytes) }}</span>
    </template>
    <template v-slot:cell-artifactVer="{ row }">
      <span class="font-mono text-code text-ch-text-secondary">v{{ row.artifactVer || 1 }}</span>
    </template>
    <template v-slot:cell-seqNo="{ row }">
      <span class="tabular-nums text-body-s text-ch-text-secondary">{{ row.seqNo }}</span>
      <span
        v-if="isCoverArtifact(row)"
        class="ml-xs rounded-sm bg-ch-primary px-xs py-[1px] text-caption text-ch-text-inverse"
      >
        封面
      </span>
    </template>
    <template v-slot:cell-artifactStatus="{ row }">
      <StateBadge domain="artifact" :status="row.artifactStatus" />
    </template>
    <template v-slot:cell-retention="{ row }">
      <span class="text-body-s text-ch-text-secondary">{{ row.retention }}</span>
    </template>
    <template v-slot:cell-jobID="{ row }">
      <RouterLink :to="jobRoute(row.jobID)" class="font-mono text-code text-ch-primary hover:text-ch-primary-hover">
        {{ row.jobID || '—' }}
      </RouterLink>
    </template>
    <template v-slot:cell-actions="{ row }">
      <div class="flex flex-wrap items-center gap-md">
        <button
          v-if="isReadyArtifact(row)"
          type="button"
          class="text-body-s text-ch-primary hover:text-ch-primary-hover"
          @click="emit('preview', row)"
        >
          预览
        </button>
        <a
          v-if="isReadyArtifact(row) && row.fileUrl"
          :href="row.fileUrl"
          target="_blank"
          rel="noopener"
          class="text-body-s text-ch-primary hover:text-ch-primary-hover"
          :title="DOWNLOAD_HINT"
        >
          下载
        </a>
        <span
          v-else
          class="cursor-not-allowed text-body-s text-ch-text-disabled"
          aria-disabled="true"
          :title="isReadyArtifact(row) ? '该产物无 fileUrl' : EXPIRED_REASON"
        >
          下载
        </span>
        <button
          type="button"
          class="text-body-s text-ch-text-secondary hover:text-ch-text-primary disabled:cursor-not-allowed disabled:text-ch-text-disabled"
          :disabled="!row.fileUrl"
          @click="copyLink(row)"
        >
          复制链接
        </button>
        <button
          v-if="!isReadyArtifact(row)"
          type="button"
          class="text-body-s text-ch-primary hover:text-ch-primary-hover disabled:cursor-not-allowed disabled:text-ch-text-disabled"
          :disabled="rerenderingID === row.recID"
          @click="emit('rerender', row)"
        >
          重新渲染
        </button>
      </div>
    </template>
  </AppTable>
</template>

<script setup>
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import AppTable from '@/components/base/AppTable.vue'
import PlatformChip from '@/components/biz/PlatformChip.vue'
import StateBadge from '@/components/biz/StateBadge.vue'
import ArtifactCard from '@/views/artifacts/ArtifactCard.vue'
import { artifactKindMeta } from '@/config/chOptions'
import { copyText, formatBytes } from '@/utils/common'

const props = defineProps({
  /** 已归一化的产物记录（当前页） */
  rows: { type: Array, default: () => [] },
  /** card / table（默认卡片视图） */
  view: { type: String, default: 'card' },
  /** 正在「重新渲染」的产物 recID（禁用该行按钮，避免重复提交） */
  rerenderingID: { type: String, default: '' }
})

const emit = defineEmits(['preview', 'rerender'])

/** 下载提示（裁定 G：跨域签名 URL 无法指定文件名） */
const DOWNLOAD_HINT = '若未自动下载，请在打开的页面右键另存为'
/** 过期产物的统一说明（逐字沿用裁定 G/H） */
const EXPIRED_REASON = '产物已过期，请重新渲染'
const COLUMNS = [
  { key: 'kind', title: '类型', width: 130 },
  { key: 'platform', title: '平台', width: 130 },
  { key: 'specNote', title: '规格', width: 110 },
  { key: 'sizeBytes', title: '大小', width: 100, align: 'right' },
  { key: 'artifactVer', title: '版本', width: 80 },
  { key: 'seqNo', title: '序号', width: 100 },
  { key: 'artifactStatus', title: '状态', width: 130 },
  { key: 'retention', title: '保留期', minWidth: 130 },
  { key: 'jobID', title: '任务', width: 140 },
  { key: 'actions', title: '操作', width: 260, fixed: 'right' }
]

const str = (value) => (value === null || value === undefined ? '' : String(value))
const toNum = (value, fallback = 0) => {
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}
const kindLabel = (code) => artifactKindMeta(code).label
const kindMetaOf = (code) => artifactKindMeta(code)
const isReadyArtifact = (row) => str(row?.artifactStatus).toUpperCase() === 'READY'
const isCoverArtifact = (row) => str(row?.kind).toLowerCase() === 'png' && toNum(row?.seqNo, 1) === 1

/** 分组与组内排序：同一 `jobID` 的 PNG 按 `seqNo` 升序（裁定 F） */
const groups = computed(() => {
  const map = new Map()
  props.rows.forEach((row) => {
    const key = str(row.jobID) || 'unknown'
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(row)
  })
  return [...map.entries()].map(([jobID, items]) => ({
    jobID,
    items: [...items].sort((a, b) => toNum(a.seqNo, 1) - toNum(b.seqNo, 1)),
    platform: str(items[0]?.platform),
    kinds: [...new Set(items.map((item) => str(item.kind)))]
  }))
})

/** 折叠记忆（同页 `ref`，不落库） */
const collapsed = ref({})
const isCollapsed = (jobID) => Boolean(collapsed.value[str(jobID)])
function toggleGroup(jobID) {
  const key = str(jobID)
  collapsed.value = { ...collapsed.value, [key]: !collapsed.value[key] }
}
const groupPanelId = (jobID) => `artifact-group-${str(jobID) || 'unknown'}`

/** 「查看任务」：跳 P-06 并带 `jobID`（本步按计划落点；`renderjobqry` 无 jobID 入参见交付说明） */
const jobRoute = (jobID) => ({ path: '/render-jobs', query: { jobID: str(jobID) } })

/** 表格视图的复制链接：只复制 `fileUrl`（带 toast；不复制 fileID） */
function copyLink(row) {
  const url = str(row?.fileUrl)
  if (!url) return
  void copyText(url)
}
</script>
