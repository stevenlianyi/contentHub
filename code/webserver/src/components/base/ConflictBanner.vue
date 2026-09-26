<!-- ============================================================================
 * ConflictBanner · L1 基础组件（Step 4）
 * ----------------------------------------------------------------------------
 * 用途：顶部橙色/蓝色条，说明「发生了什么」+ 给出选择。三处典型场景：
 *       素材去重命中（assetadd 返回 dedupHit=1）、并发编辑冲突（B9）、凭据失效（B8/F0/T/账号停用）。
 * 规格：type=warning → 橙条；type=info → 蓝条；actions[] 渲染为可选操作（默认 secondary，
 *       避免与页面主操作争夺「每屏唯一 primary」）。
 * ========================================================================== -->
<template>
  <div class="flex items-start gap-md rounded-lg border px-lg py-md" :class="toneClass" role="alert">
    <i :class="meta.icon" class="mt-xs shrink-0 text-body" :style="{ color: meta.color }" aria-hidden="true"></i>

    <div class="flex min-w-0 flex-1 flex-col gap-sm">
      <p class="text-body font-medium text-ch-text-primary">{{ title }}</p>
      <div v-if="$slots.default" class="text-body-s text-ch-text-secondary">
        <slot />
      </div>
      <div v-if="actions.length" class="flex flex-wrap items-center gap-sm">
        <AppButton
          v-for="action in actions"
          :key="action.key"
          :type="action.type || 'secondary'"
          size="sm"
          @click="emit('action', action.key, action)"
        >
          {{ action.label }}
        </AppButton>
      </div>
    </div>

    <button
      v-if="closable"
      type="button"
      class="shrink-0 rounded-sm p-xs text-ch-text-secondary transition-colors duration-150 ease-out hover:bg-ch-hover hover:text-ch-text-primary"
      aria-label="关闭提示"
      @click="emit('close')"
    >
      <i class="fa fa-times" aria-hidden="true"></i>
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { tokens } from '@/js/tokens'
import AppButton from '@/components/base/AppButton.vue'

const props = defineProps({
  type: { type: String, default: 'warning' }, // warning / info
  title: { type: String, default: '' },
  /** [{ key, label, type? }] */
  actions: { type: Array, default: () => [] },
  closable: { type: Boolean, default: false }
})

const emit = defineEmits(['action', 'close'])

const TONE = {
  warning: {
    box: 'border-ch-warning/40 bg-ch-warning/10',
    icon: 'fa fa-triangle-exclamation',
    color: tokens.status.warning
  },
  info: {
    box: 'border-ch-info/40 bg-ch-info/10',
    icon: 'fa fa-circle-info',
    color: tokens.status.info
  }
}

const meta = computed(() => TONE[props.type] || TONE.warning)
const toneClass = computed(() => meta.value.box)
</script>
