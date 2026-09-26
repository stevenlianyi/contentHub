<!-- ============================================================================
 * SwipePreview · P-08 小红书「滑动多图集」预览（swipe_v1，Step 10）
 * ----------------------------------------------------------------------------
 * 依据（已核源码，服从）：
 *   · processor/platformAdapter/xiaohongshu.py:197-370 → **不处理 `previewKind`**；
 *     出参 `outputKind:'png'` + `content`（未包裹的原始 HTML）+ `products[]`，
 *     每项含 `seqNo/kind/fileID/fileUrl/width/height/sizeBytes/sha256/isCover`
 *     （`fileID` 已由 `renderService` 经 `fillFileUrls` 转成 `fileUrl`，§2.4.5）。
 *     ★ 因此本组件**只吃 `products[].fileUrl`**，绝不把 `content` 当手机框片段注入。
 *   · 数值形态（R-26）：`width`/`height` 为**字符串** → 展示与比较前一律 `Number()`。
 *
 * 形态：手机框内**一次展示一张** 1080×1440 卡片（宽度自适应框宽、按 `aspect-ratio` 保持比例），
 *       底部 `{当前} / {总数}` + `role="tablist"` 序号点；
 *       `←`/`→`、左右箭头按钮、点击序号点三种方式切换；**不做真实手势模拟**（真机验收）。
 * 比例一致性：各图比例不一致时，在序号点**上方**给出
 *       「⚠ 比例不一致，App 内滑动会跳动」。
 * 无障碍：序号点 `role="tab"` + `aria-selected` + `aria-controls`；
 *       图片区 `role="tabpanel"`；`←`/`→` **仅在预览区聚焦时**生效（不劫持全局滚动）。
 * ★ 浅色隔离：本文件整体渲染在 `.preview-scope` 子树内，
 *   只使用 `tokens.preview.*`（内联）与不含 ch 前缀的 Tailwind 类；
 *   禁止出现应用级暗色 Token（bg / text / border 三类 ch 前缀类一律不得出现）。
 * ★ 手机框由 Step 4 的 `PreviewFrame`（mode="phone"）提供，不重复实现外壳。
 * ========================================================================== -->
<template>
  <div
    class="flex w-full flex-col items-center gap-sm"
    tabindex="0"
    role="group"
    :aria-label="`滑动多图集预览（${products.length} 张，当前第 ${index + 1} 张）`"
    @keydown="onKeydown"
  >
    <PreviewFrame mode="phone" :images="[]" :switchable="false" :padded="false">
      <div class="flex h-full flex-col">
        <div
          :id="panelId"
          class="flex flex-1 items-center justify-center overflow-hidden"
          role="tabpanel"
          :aria-labelledby="dotId(index)"
          aria-live="polite"
        >
          <img
            v-if="current.fileUrl"
            :src="current.fileUrl"
            :alt="`${alt} 第 ${index + 1} 张`"
            class="block w-full"
            :style="{ aspectRatio: cardRatio }"
          />
          <p v-else class="px-lg text-center text-body-s" :style="{ color: preview.text }">
            产物 URL 缺失（fileID {{ current.fileID || '—' }}），请重新渲染后再预览。
          </p>
        </div>

        <div
          class="flex shrink-0 flex-col items-center gap-xs px-md py-sm"
          :style="{ borderTop: `1px solid ${preview.border}` }"
        >
          <p
            v-if="ratio.mismatch"
            class="flex items-center gap-xs text-caption"
            :style="{ color: tokens.status.warning }"
          >
            <i class="fa fa-triangle-exclamation" aria-hidden="true"></i>
            比例不一致，App 内滑动会跳动
          </p>

          <div class="flex items-center gap-sm">
            <button
              type="button"
              class="flex h-6 w-6 items-center justify-center rounded-sm disabled:opacity-[.45]"
              :style="{ border: `1px solid ${preview.border}`, color: preview.text }"
              :disabled="index <= 0"
              aria-label="上一张"
              @click="go(index - 1)"
            >
              <i class="fa fa-angle-left" aria-hidden="true"></i>
            </button>

            <span class="text-caption tabular-nums" :style="{ color: preview.text }">
              {{ index + 1 }} / {{ products.length }}
            </span>

            <button
              type="button"
              class="flex h-6 w-6 items-center justify-center rounded-sm disabled:opacity-[.45]"
              :style="{ border: `1px solid ${preview.border}`, color: preview.text }"
              :disabled="index >= products.length - 1"
              aria-label="下一张"
              @click="go(index + 1)"
            >
              <i class="fa fa-angle-right" aria-hidden="true"></i>
            </button>
          </div>

          <div class="flex items-center gap-xs" role="tablist" aria-label="图片序号">
            <button
              v-for="(item, dotIndex) in products"
              :id="dotId(dotIndex)"
              :key="item.seqNo || dotIndex"
              type="button"
              role="tab"
              class="h-2 w-2 rounded-full"
              :style="{ backgroundColor: dotIndex === index ? preview.text : preview.border }"
              :aria-selected="dotIndex === index ? 'true' : 'false'"
              :aria-controls="panelId"
              :aria-label="`第 ${dotIndex + 1} 张，共 ${products.length} 张`"
              :tabindex="dotIndex === index ? 0 : -1"
              @click="go(dotIndex)"
            ></button>
          </div>
        </div>
      </div>
    </PreviewFrame>

    <p class="text-center text-caption" :style="{ color: tokens.text.tertiary }">
      聚焦本区域后可用 ← / → 切换；点击箭头或序号点可直达（真实左右滑动体验留待真机验收）。
    </p>
  </div>
</template>

<script setup>
import { computed, ref, useId } from 'vue'
import PreviewFrame from '@/components/biz/PreviewFrame.vue'
import { tokens } from '@/js/tokens'
import { checkRatioUniform } from '@/views/preview/usePreviewRender'

const props = defineProps({
  /** 产物列表（`{ seqNo, fileUrl, width, height, ... }`，数值已 Number 化） */
  products: { type: Array, default: () => [] },
  /** 主题标题（仅用于图片 alt） */
  alt: { type: String, default: '预览' }
})

const preview = tokens.preview
const index = ref(0)
/** 无障碍关联 id（`useId` 只能在 setup 顶层调用一次，故此处固化为前缀） */
const uid = useId()
const panelId = `preview-swipe-panel-${uid}`
const dotId = (position) => `preview-swipe-dot-${uid}-${position}`

const list = computed(() => (Array.isArray(props.products) ? props.products : []))
const safeIndex = computed(() => Math.min(Math.max(0, index.value), Math.max(0, list.value.length - 1)))
const current = computed(() => list.value[safeIndex.value] || {})
/** 卡片比例：首图为基准（1080×1440 → `1080 / 1440`）；宽高缺失时回落 3:4（ch_layout 种子 ratio） */
const cardRatio = computed(() => {
  const width = Number(current.value?.width)
  const height = Number(current.value?.height)
  if (width > 0 && height > 0) return `${width} / ${height}`
  return '3 / 4'
})

/** 比例一致性（各图比例不一致 → App 内滑动会跳动） */
const ratio = computed(() => checkRatioUniform(list.value))

function go(next) {
  const size = list.value.length
  if (size < 1 || next < 0 || next >= size || next === safeIndex.value) return
  index.value = next
}

/** ←/→ 切换（仅在预览区聚焦时生效；不劫持全局滚动） */
function onKeydown(event) {
  if (list.value.length < 2) return
  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
  event.preventDefault()
  go(event.key === 'ArrowRight' ? safeIndex.value + 1 : safeIndex.value - 1)
}
</script>
