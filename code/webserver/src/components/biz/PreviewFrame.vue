<!-- ============================================================================
 * PreviewFrame · L2 业务组件（Step 4）
 * ----------------------------------------------------------------------------
 * 规格：手机 390×844；长图宽 750；**内部强制 `.preview-scope` 浅色**；顶部平台标签可切换；
 *       多图集时底部「1 / 8」序号点 + ←/→ 键与箭头切换；比例不一致时序号点上方提示
 *       「⚠ 比例不一致，App 内滑动会跳动」；外壳 `shadow/device` + 圆角 24。
 * ★ 浅色隔离（§2.3.1 / Step 4 验收 7）：`.preview-scope` 子树**不得引用应用级暗色 Token**，
 *   本组件在该子树内只用 tokens.preview.* 的内联值与本组件自有类，不出现 `bg-ch-*`。
 * ★ 本组件不含任何投递/发布入口（小红书本期仅导出素材包）。
 * ========================================================================== -->
<template>
  <div class="flex flex-col items-center gap-md">
    <!-- 平台标签（应用级暗色区域，位于 .preview-scope 之外） -->
    <div v-if="switchable" class="flex items-center gap-sm" role="group" aria-label="切换预览平台">
      <button
        v-for="code in platforms"
        :key="code"
        type="button"
        class="h-6 rounded-md border px-sm text-caption transition-colors duration-150 ease-out"
        :class="
          code === platform
            ? 'border-ch-primary bg-ch-primary-subtle text-ch-primary'
            : 'border-ch-border text-ch-text-secondary hover:bg-ch-hover'
        "
        :aria-pressed="code === platform ? 'true' : 'false'"
        @click="emit('update:platform', code)"
      >
        {{ labelOf(code) }}
      </button>
    </div>

    <!-- 设备外壳：本元素即 .preview-scope（浅色隔离域） -->
    <div
      class="preview-scope relative flex flex-col overflow-hidden rounded-[24px] shadow-device"
      :style="frameStyle"
      tabindex="0"
      role="group"
      :aria-label="`预览区域（${mode === 'phone' ? '手机 390×844' : '长图 750 宽'}）`"
      @keydown="onKeydown"
    >
      <div class="min-h-0 flex-1 overflow-y-auto" :style="contentStyle">
        <slot />
      </div>

      <div
        v-if="showFooter"
        class="flex shrink-0 flex-col items-center gap-xs px-md py-sm"
        :style="{ borderTop: `1px solid ${preview.border}` }"
      >
        <p
          v-if="ratioMismatch"
          class="flex items-center gap-xs text-caption"
          :style="{ color: tokens.status.warning }"
        >
          <i class="fa fa-triangle-exclamation" aria-hidden="true"></i>
          比例不一致，App 内滑动会跳动
        </p>

        <div v-if="images.length > 1" class="flex items-center gap-sm">
          <button
            type="button"
            class="flex h-6 w-6 items-center justify-center rounded-sm"
            :style="{ border: `1px solid ${preview.border}`, color: preview.text }"
            :disabled="index <= 0"
            aria-label="上一张"
            @click="go(index - 1)"
          >
            <i class="fa fa-angle-left" aria-hidden="true"></i>
          </button>
          <span class="text-caption tabular-nums" :style="{ color: preview.text }" aria-live="polite">
            {{ index + 1 }} / {{ images.length }}
          </span>
          <button
            type="button"
            class="flex h-6 w-6 items-center justify-center rounded-sm"
            :style="{ border: `1px solid ${preview.border}`, color: preview.text }"
            :disabled="index >= images.length - 1"
            aria-label="下一张"
            @click="go(index + 1)"
          >
            <i class="fa fa-angle-right" aria-hidden="true"></i>
          </button>

          <span class="flex items-center gap-xs">
            <button
              v-for="(image, dotIndex) in images"
              :key="image.id || dotIndex"
              type="button"
              class="h-1.5 w-1.5 rounded-full"
              :style="{ backgroundColor: dotIndex === index ? preview.text : preview.border }"
              :aria-label="`第 ${dotIndex + 1} 张`"
              :aria-current="dotIndex === index ? 'true' : undefined"
              @click="go(dotIndex)"
            ></button>
          </span>
        </div>
      </div>

      <slot name="indicator" />
    </div>

    <p v-if="ratioHint" class="ch-measure text-center text-caption text-ch-text-tertiary">{{ ratioHint }}</p>
  </div>
</template>

<script setup>
import { computed, useSlots } from 'vue'
import { PLATFORM_MAP, PLATFORM_ORDER } from '@/config/chOptions'
import { tokens } from '@/js/tokens'

const props = defineProps({
  mode: { type: String, default: 'phone' }, // phone / longimage
  platform: { type: String, default: 'wechat_mp' },
  platforms: { type: Array, default: () => PLATFORM_ORDER },
  switchable: { type: Boolean, default: true },
  /** 多图集：[{ id?, url?, thumbnailUrl? }]；长度 > 1 时出现序号点与箭头 */
  images: { type: Array, default: () => [] },
  current: { type: Number, default: 0 },
  /** 序号点上方提示：比例不一致 */
  ratioMismatch: { type: Boolean, default: false },
  /** 帧下方一句比例提示（如“小红书推荐 3:4”） */
  ratioHint: { type: String, default: '' },
  padded: { type: Boolean, default: true }
})

const emit = defineEmits(['update:platform', 'update:current'])

const slots = useSlots()
const preview = tokens.preview

const index = computed(() => {
  const max = Math.max(0, props.images.length - 1)
  return Math.min(Math.max(0, Number(props.current) || 0), max)
})

const frameStyle = computed(() => {
  if (props.mode === 'longimage') {
    return { width: '750px', maxWidth: '100%', maxHeight: '844px', backgroundColor: preview.bg }
  }
  return { width: '390px', maxWidth: '100%', height: '844px', backgroundColor: preview.bg }
})

const contentStyle = computed(() => ({
  color: preview.text,
  backgroundColor: preview.bg,
  padding: props.padded ? `${tokens.space.lg}px` : '0'
}))

const showFooter = computed(() => props.ratioMismatch || props.images.length > 1 || Boolean(slots.indicator))

const labelOf = (code) => PLATFORM_MAP[code]?.label || code

function go(next) {
  if (next < 0 || next >= props.images.length || next === index.value) return
  emit('update:current', next)
}

/** ←/→ 切换多图（帧可 Tab 聚焦后使用键盘；仅在多图时接管按键） */
function onKeydown(event) {
  if (props.images.length < 2) return
  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
  event.preventDefault()
  go(event.key === 'ArrowRight' ? index.value + 1 : index.value - 1)
}
</script>
