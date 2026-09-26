<!-- ============================================================================
 * ArtifactCard · P-07 产物台账「单卡片」（Step 12 · 产出文件）
 * ----------------------------------------------------------------------------
 * 职责：只渲染**一张**产物 + 该卡片自己的动作入口；不做取数 / 不做筛选 / 不持列表状态
 *       （列表、筛选、分页、分组折叠都在 `ArtifactsPanel.vue`）。
 *
 * 字段口径（权威 `database/ch_artifact.txt` + `chCommon.fillFileUrls`）：
 *   · 缩略图读 `thumbnailUrl`（★ 只读 `*Url`，不得拿 fileID 当 URL，§2.4.5）；
 *     缺失时按 `kind` 显示**类型图标 + 类型名**，禁止破图占位；
 *   · `specNote` 原样显示（如 `1080x1440`），缺失显示 `—`；
 *   · `sizeBytes` → `formatBytes`；`artifactVer` → `v{n}`；
 *   · `seqNo`：同一 job 的图集显示 `3 / 8`（序号 / 组内总数），`seqNo === 1` 的 PNG 标「封面」；
 *   · 保留期 `retention`（由面板用 `artifactRetentionText()` 归一：空值 = 「长期保留」，裁定 E）；
 *   · 状态三重编码：`StateBadge domain="artifact"`（形状图标 + 颜色 + 文字，§2.6 裁定 C6）。
 * ★ 数值已由面板 `normalizeArtifact()` 统一 `Number()`（附录 B R-26），本组件不重复转换。
 *
 * 动作口径（裁定 G / H）：
 *   · `READY` → 预览 / 下载 / 复制链接；下载用 `<a href target="_blank" rel="noopener">`
 *     ——跨域签名 URL 上 `download` 属性会被浏览器忽略，故打开新页 + 提示右键另存为，
 *     **不伪造本地文件名**；
 *   · `EXPIRED` → 下载**禁用**（`AppButton disabled` + Tooltip「产物已过期，请重新渲染」），
 *     主操作改为「重新渲染」（emit 给面板，由面板统一调 `topicrender`）。
 *   · 复制的内容一律是 `fileUrl`，**不得**复制 `fileID`。
 * ★ 本组件不含「立即清理 / 导出素材包」入口：清理归 `schedule/archive.py`，导出归 Step 14。
 * ★ 「重新渲染」在卡片上置于动作行**首位**表达主操作，但**不使用 primary 色**：
 *   同一屏可出现多张 EXPIRED 卡片，需遵守「每屏唯一 primary」（§2.11；与 Step 11 JobFailDetail 同款裁定）。
 * ========================================================================== -->
<template>
  <article class="flex flex-col gap-md rounded-xl border border-ch-border bg-ch-surface p-lg">
    <!-- 缩略图 / 类型图标兜底 -->
    <div class="relative aspect-[4/3] w-full overflow-hidden rounded-lg border border-ch-border bg-ch-input">
      <img
        v-if="hasThumb && !thumbFailed"
        :src="artifact.thumbnailUrl"
        :alt="altText"
        loading="lazy"
        decoding="async"
        class="h-full w-full object-cover"
        @error="thumbFailed = true"
      />
      <div v-else class="flex h-full w-full flex-col items-center justify-center gap-xs text-ch-text-tertiary">
        <i :class="kindMeta.icon" class="text-2xl" aria-hidden="true"></i>
        <span class="text-caption">{{ kindMeta.label }}</span>
      </div>

      <span
        v-if="isCover"
        class="absolute left-xs top-xs rounded-sm bg-ch-primary px-xs py-[2px] text-caption text-ch-text-inverse"
      >
        封面
      </span>
      <span
        v-if="seqTotal > 1"
        class="absolute right-xs top-xs rounded-sm bg-ch-base/70 px-xs py-[2px] font-mono text-caption text-ch-text-primary"
      >
        {{ artifact.seqNo }} / {{ seqTotal }}
      </span>
    </div>

    <!-- 类型 + 平台徽标 -->
    <div class="flex flex-wrap items-center gap-xs">
      <span
        class="inline-flex h-6 items-center gap-xs rounded-md border border-ch-border-light px-sm text-caption text-ch-text-secondary"
      >
        <i :class="kindMeta.icon" aria-hidden="true"></i>
        {{ kindMeta.label }}
      </span>
      <PlatformChip :platform="artifact.platform" size="sm" />
    </div>

    <!-- 规格 / 大小 / 版本 / 保留期 -->
    <dl class="grid grid-cols-2 gap-x-lg gap-y-xs text-body-s">
      <div class="flex min-w-0 items-baseline gap-xs">
        <dt class="shrink-0 text-ch-text-tertiary">规格</dt>
        <dd class="min-w-0 truncate text-ch-text-primary" :title="specText">{{ specText }}</dd>
      </div>
      <div class="flex min-w-0 items-baseline gap-xs">
        <dt class="shrink-0 text-ch-text-tertiary">大小</dt>
        <dd class="min-w-0 truncate tabular-nums text-ch-text-primary">{{ sizeText }}</dd>
      </div>
      <div class="flex min-w-0 items-baseline gap-xs">
        <dt class="shrink-0 text-ch-text-tertiary">版本</dt>
        <dd class="min-w-0 truncate font-mono text-ch-text-primary">{{ verText }}</dd>
      </div>
      <div class="flex min-w-0 items-baseline gap-xs">
        <dt class="shrink-0 text-ch-text-tertiary">保留期</dt>
        <dd class="min-w-0 truncate text-ch-text-secondary" :title="artifact.retention">{{ artifact.retention }}</dd>
      </div>
    </dl>

    <div class="flex flex-wrap items-center justify-between gap-sm">
      <StateBadge domain="artifact" :status="artifact.artifactStatus" />
      <span class="font-mono text-code text-ch-text-tertiary">{{ artifact.recID }}</span>
    </div>

    <!-- 动作（EXPIRED 时「重新渲染」置于首位） -->
    <div class="flex flex-wrap items-center gap-sm">
      <AppButton
        v-if="!isReady"
        size="sm"
        icon="fa fa-rotate-right"
        :loading="rerendering"
        @click="emit('rerender', artifact)"
      >
        重新渲染
      </AppButton>
      <AppButton
        size="sm"
        icon="fa fa-eye"
        :disabled="!isReady"
        :disabled-reason="EXPIRED_REASON"
        @click="emit('preview', artifact)"
      >
        预览
      </AppButton>
      <a
        v-if="isReady && artifact.fileUrl"
        :href="artifact.fileUrl"
        target="_blank"
        rel="noopener"
        class="inline-flex h-7 items-center justify-center gap-sm rounded-md border border-ch-border-light bg-ch-elevated px-sm text-caption font-medium text-ch-text-primary transition-colors duration-150 ease-out hover:border-ch-primary hover:text-ch-primary"
        :title="DOWNLOAD_HINT"
      >
        <i class="fa fa-download" aria-hidden="true"></i>
        下载
      </a>
      <AppButton v-else size="sm" icon="fa fa-download" disabled :disabled-reason="isReady ? '该产物无 fileUrl' : EXPIRED_REASON">
        下载
      </AppButton>
      <AppButton
        size="sm"
        icon="fa fa-link"
        :disabled="!artifact.fileUrl"
        :disabled-reason="'该产物无 fileUrl，无法复制链接'"
        @click="copyLink"
      >
        复制链接
      </AppButton>
    </div>

    <p class="text-caption text-ch-text-tertiary">{{ actionHint }}</p>
  </article>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import AppButton from '@/components/base/AppButton.vue'
import PlatformChip from '@/components/biz/PlatformChip.vue'
import StateBadge from '@/components/biz/StateBadge.vue'
import { artifactKindMeta } from '@/config/chOptions'
import { copyText, formatBytes } from '@/utils/common'

const props = defineProps({
  /** 已由 `ArtifactsPanel.normalizeArtifact()` 归一化的产物记录 */
  artifact: { type: Object, required: true },
  /** 同一 job 组内的产物总数（图集「3 / 8」的分母；缺省 1 表示单件） */
  seqTotal: { type: Number, default: 1 },
  /** 「重新渲染」进行中（避免同一卡片重复点击） */
  rerendering: { type: Boolean, default: false }
})

const emit = defineEmits(['preview', 'rerender'])

/** 下载提示（裁定 G：跨域签名 URL 无法指定文件名，需提示右键另存为） */
const DOWNLOAD_HINT = '若未自动下载，请在打开的页面右键另存为'
/** 过期产物的统一说明（与 Tooltip 文案一致，逐字沿用裁定 G/H） */
const EXPIRED_REASON = '产物已过期，请重新渲染'

const toNum = (value, fallback = 0) => {
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}
const str = (value) => (value === null || value === undefined ? '' : String(value))

/** 缩略图加载失败时同样回落到类型图标（不显示破图） */
const thumbFailed = ref(false)
watch(() => props.artifact?.thumbnailUrl, () => { thumbFailed.value = false })

const kindMeta = computed(() => artifactKindMeta(props.artifact?.kind))
const hasThumb = computed(() => Boolean(str(props.artifact?.thumbnailUrl)))
const isReady = computed(() => str(props.artifact?.artifactStatus).toUpperCase() === 'READY')
const isCover = computed(() => str(props.artifact?.kind).toLowerCase() === 'png' && toNum(props.artifact?.seqNo, 1) === 1)
const specText = computed(() => str(props.artifact?.specNote) || '—')
const sizeText = computed(() => formatBytes(props.artifact?.sizeBytes))
const verText = computed(() => `v${toNum(props.artifact?.artifactVer, 1) || 1}`)
const altText = computed(() => `${kindMeta.value.label} 产物第 ${toNum(props.artifact?.seqNo, 1)} 张`)
const actionHint = computed(() =>
  isReady.value
    ? `下载：${DOWNLOAD_HINT}；复制的是 fileUrl（不复制 fileID）。`
    : `该产物已过期（artifactStatus=EXPIRED）：下载已禁用，请「重新渲染」生成新产物。`
)

/** 复制链接：只复制 `fileUrl`（带 toast，utils/common.copyText） */
function copyLink() {
  const url = str(props.artifact?.fileUrl)
  if (!url) return
  void copyText(url)
}
</script>
