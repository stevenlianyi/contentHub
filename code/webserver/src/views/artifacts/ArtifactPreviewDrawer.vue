<!-- ============================================================================
 * ArtifactPreviewDrawer · 产物预览抽屉（Step 12 · 越界授权文件，裁定 L 已登记）
 * ----------------------------------------------------------------------------
 * 用途：`ArtifactsPanel.vue` 的「预览」入口。HTML / JSON 产物用 `<iframe :src=fileUrl>` 承载，
 *       PNG 用大图；★ **关闭即销毁 iframe**（`v-if` 卸载）——裁定 G。
 *
 * 浅色隔离（§2.3.1 / 通用约束 5）：产物内容位于 `.preview-scope` 子树内，容器配色**只取
 *   `tokens.preview.*`（内联）**，不把应用暗色 Token 传进预览内容；iframe 自身是独立文档，
 *   CSS 变量不会外泄（本组件也不向 iframe 注入任何样式）。
 *
 * 数据口径：只读 `fileUrl`（★ 禁止拿 fileID 当 URL，§2.4.5）；`EXPIRED` 时下载禁用 +
 *   Tooltip「产物已过期，请重新渲染」，主操作为「重新渲染」（emit 给面板统一调用 `topicrender`）。
 * 无障碍：`role="dialog"` + `aria-modal` + `aria-labelledby`；Esc 关闭；关闭后焦点归还触发元素。
 * ★ 抽屉内**不提供**「立即清理 / 导出素材包」入口（清理归后端定时任务，导出归 Step 14）。
 * ========================================================================== -->
<template>
  <Teleport to="body">
    <div v-if="modelValue" class="fixed inset-0 z-50 flex justify-end bg-ch-base/80" @click.self="close">
      <aside
        ref="panelRef"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
        tabindex="-1"
        class="flex h-full w-full max-w-[820px] flex-col border-l border-ch-border bg-ch-elevated shadow-modal"
      >
        <header class="flex items-start justify-between gap-md border-b border-ch-border px-xl py-md">
          <div class="flex min-w-0 flex-col gap-xs">
            <h3 :id="titleId" class="truncate text-h3 text-ch-text-primary">{{ title }}</h3>
            <p class="flex flex-wrap items-center gap-x-md gap-y-xs text-caption text-ch-text-tertiary">
              <span class="font-mono">recID {{ artifact.recID || '—' }}</span>
              <span class="font-mono">任务 {{ artifact.jobID || '—' }}</span>
              <span>规格 {{ specText }}</span>
              <span class="tabular-nums">{{ sizeText }}</span>
            </p>
          </div>
          <button
            type="button"
            class="shrink-0 rounded-md p-1 text-ch-text-secondary transition-colors duration-150 ease-out hover:bg-ch-hover hover:text-ch-text-primary"
            aria-label="关闭预览"
            @click="close"
          >
            <i class="fa fa-times" aria-hidden="true"></i>
          </button>
        </header>

        <div class="flex min-h-0 flex-1 flex-col gap-md overflow-y-auto px-xl py-lg">
          <ConflictBanner v-if="!isReady" type="warning" title="产物已过期，无法预览与下载">
            该记录 `artifactStatus=EXPIRED`；请先「重新渲染」生成新产物（过期清理与归档由后端定时任务负责，前端不提供清理入口）。
          </ConflictBanner>

          <div
            v-if="!artifact.fileUrl"
            class="flex min-h-[240px] items-center justify-center rounded-xl border border-ch-border bg-ch-input text-body-s text-ch-text-tertiary"
          >
            该产物未返回 fileUrl，无法预览（前端只读 `*Url`，不自行拼接 fileID）。
          </div>

          <!-- preview-scope:begin —— 浅色隔离域：仅用 tokens.preview.*，不引入应用暗色类 -->
          <div
            v-else-if="isImage"
            class="preview-scope flex min-h-[240px] flex-1 items-center justify-center overflow-auto rounded-xl border"
            :style="previewStyle"
          >
            <img :src="artifact.fileUrl" :alt="title" class="max-h-[70vh] max-w-full object-contain" />
          </div>
          <div v-else class="preview-scope min-h-[420px] flex-1 overflow-hidden rounded-xl border" :style="previewStyle">
            <iframe :src="artifact.fileUrl" :title="`${title}（iframe 独立文档）`" class="h-full w-full border-0"></iframe>
          </div>
          <!-- preview-scope:end -->
        </div>

        <footer class="flex flex-wrap items-center justify-between gap-sm border-t border-ch-border px-xl py-md">
          <p class="max-w-[420px] text-caption text-ch-text-tertiary">{{ footerHint }}</p>
          <div class="flex flex-wrap items-center gap-sm">
            <a
              v-if="isReady && artifact.fileUrl"
              :href="artifact.fileUrl"
              target="_blank"
              rel="noopener"
              class="inline-flex h-9 items-center justify-center gap-sm rounded-lg border border-ch-border-light bg-ch-elevated px-lg text-body font-medium text-ch-text-primary transition-colors duration-150 ease-out hover:border-ch-primary hover:text-ch-primary"
              :title="DOWNLOAD_HINT"
            >
              <i class="fa fa-download" aria-hidden="true"></i>
              下载
            </a>
            <AppButton v-else size="md" icon="fa fa-download" disabled :disabled-reason="isReady ? '该产物无 fileUrl' : EXPIRED_REASON">
              下载
            </AppButton>
            <AppButton
              size="md"
              icon="fa fa-link"
              :disabled="!artifact.fileUrl"
              :disabled-reason="'该产物无 fileUrl，无法复制链接'"
              @click="copyLink"
            >
              复制链接
            </AppButton>
            <AppButton
              v-if="!isImage && artifact.fileUrl"
              size="md"
              icon="fa fa-up-right-from-square"
              @click="openWindow"
            >
              新窗口打开
            </AppButton>
            <AppButton
              v-if="!isReady"
              size="md"
              type="primary"
              icon="fa fa-rotate-right"
              :loading="rerendering"
              @click="emit('rerender', artifact)"
            >
              重新渲染
            </AppButton>
          </div>
        </footer>
      </aside>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'
import AppButton from '@/components/base/AppButton.vue'
import ConflictBanner from '@/components/base/ConflictBanner.vue'
import { artifactKindMeta } from '@/config/chOptions'
import { tokens } from '@/js/tokens'
import { copyText, formatBytes } from '@/utils/common'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 归一化后的产物记录（`fileUrl` / `kind` / `status` / `recID`…） */
  artifact: { type: Object, default: () => ({}) },
  rerendering: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'rerender'])

/** 下载提示（裁定 G） */
const DOWNLOAD_HINT = '若未自动下载，请在打开的页面右键另存为'
/** 过期产物的统一说明（逐字沿用裁定 G/H） */
const EXPIRED_REASON = '产物已过期，请重新渲染'

const panelRef = ref(null)
const titleId = `ch-artifact-preview-${useId()}`
let lastActiveElement = null

const str = (value) => (value === null || value === undefined ? '' : String(value))

const kindMeta = computed(() => artifactKindMeta(props.artifact?.kind))
const isReady = computed(() => str(props.artifact?.artifactStatus).toUpperCase() === 'READY')
const isImage = computed(() => str(props.artifact?.kind).toLowerCase() === 'png')
const specText = computed(() => str(props.artifact?.specNote) || '—')
const sizeText = computed(() => formatBytes(props.artifact?.sizeBytes))
const title = computed(() => {
  const seq = Number(props.artifact?.seqNo) || 1
  return `${kindMeta.value.label} 预览 · 第 ${seq} 张`
})
const footerHint = computed(() =>
  isReady.value
    ? `下载：${DOWNLOAD_HINT}（跨域签名 URL 无法指定本地文件名）。`
    : '产物已过期：请「重新渲染」后再下载；过期清理与归档由后端定时任务负责。'
)

/** 预览容器配色只取 `tokens.preview.*`（浅色隔离域内不出现应用暗色 Token 类） */
const previewStyle = computed(() => ({
  backgroundColor: tokens.preview.bg,
  borderColor: tokens.preview.border
}))

const handleKeydown = (event) => {
  if (event.key === 'Escape') {
    event.preventDefault()
    close()
  }
}

function close() {
  emit('update:modelValue', false)
}

/** 复制链接：只复制 `fileUrl`（带 toast） */
function copyLink() {
  const url = str(props.artifact?.fileUrl)
  if (!url) return
  void copyText(url)
}

/** HTML / JSON 产物可另开新窗口（与抽屉 iframe 同一 URL，不做任何改写） */
function openWindow() {
  const url = str(props.artifact?.fileUrl)
  if (!url) return
  window.open(url, '_blank', 'noopener')
}

watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      lastActiveElement = document.activeElement
      document.addEventListener('keydown', handleKeydown)
      await nextTick()
      panelRef.value?.focus()
    } else {
      document.removeEventListener('keydown', handleKeydown)
      if (lastActiveElement && typeof lastActiveElement.focus === 'function') {
        lastActiveElement.focus()
      }
      lastActiveElement = null
    }
  }
)

onBeforeUnmount(() => document.removeEventListener('keydown', handleKeydown))
</script>
