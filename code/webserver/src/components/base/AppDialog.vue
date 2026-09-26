<!-- ============================================================================
 * AppDialog · L1 基础组件（Step 4 扩展既有件）
 * ----------------------------------------------------------------------------
 * ★ 既有 props / emits 名保持不变（AppTopBar 等已在用）：modelValue / title / size / danger，
 *   emits：update:modelValue / cancel / confirm。
 * 本步追加：size(480/640/800，兼容 sm/md/lg)、footer 插槽、danger 变体、confirmText / cancelText /
 *           confirmLoading；默认底栏（无 footer 插槽时渲染）。
 * 无障碍硬要求（裁定 C 与 §2.11）：role="dialog" + aria-modal="true" + aria-labelledby +
 *   Tab 焦点锁定 + 关闭后焦点归还触发元素 + Esc 关闭；destroy-on-close（v-if 卸载）。
 * 行为约定：点确认**不自动关闭** —— 由父级在请求成功后置 false，失败时保留用户已填内容（§2.5）。
 *
 * ★ 2026-09-24 追加「关闭途径开关」（默认全为 true = 既有行为，未传参的调用方零影响）：
 *   closeOnOverlay / closeOnEsc / showClose。三者同时收紧 = 表单弹窗形态（关闭入口只剩
 *   底部「取消 / 确认」），用于避免误触弹窗外部导致已填内容丢失 —— 账号「新建 / 编辑」弹窗
 *   （`views/accounts/AccountEditDialog.vue`）按要求采用该形态；其余调用方保持默认。
 * ========================================================================== -->
<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="fixed inset-0 z-50 flex items-center justify-center bg-ch-base/80 p-4"
      @click.self="handleOverlayClick"
    >
      <div
        ref="panelRef"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
        tabindex="-1"
        class="flex w-full flex-col rounded-2xl border bg-ch-elevated shadow-modal"
        :class="danger ? 'border-ch-danger' : 'border-ch-border'"
        :style="{ maxWidth: panelWidth, maxHeight: '80vh' }"
      >
        <header class="flex items-center justify-between gap-sm border-b border-ch-border px-xl py-md">
          <h3 :id="titleId" class="text-h3 text-ch-text-primary">{{ title }}</h3>
          <button
            v-if="showClose"
            type="button"
            class="rounded-md p-1 text-ch-text-secondary transition-colors duration-150 ease-out hover:bg-ch-hover hover:text-ch-text-primary"
            aria-label="关闭"
            @click="handleCancel"
          >
            <i class="fa fa-times" aria-hidden="true"></i>
          </button>
        </header>

        <div class="overflow-y-auto px-xl py-lg text-body text-ch-text-secondary">
          <slot />
        </div>

        <footer class="flex items-center justify-end gap-md border-t border-ch-border px-xl py-md">
          <slot name="footer">
            <AppButton size="md" :disabled="confirmLoading" @click="handleCancel">{{ cancelText }}</AppButton>
            <AppButton
              :type="danger ? 'danger-solid' : 'primary'"
              size="md"
              :loading="confirmLoading"
              @click="emit('confirm')"
            >
              {{ confirmText }}
            </AppButton>
          </slot>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'
import AppButton from '@/components/base/AppButton.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  /** 480 / 640 / 800，或直接传数字；兼容既有的 sm(480) / md(640) / lg(800) */
  size: { type: [String, Number], default: 'md' },
  /** 危险操作变体（删除/撤销等）：danger 描边，默认确认文案为「删除」 */
  danger: { type: Boolean, default: false },
  confirmText: { type: String, default: '' },
  cancelText: { type: String, default: '取消' },
  confirmLoading: { type: Boolean, default: false },
  /**
   * ★ 2026-09-24 追加三个关闭途径开关（**默认值保持既有行为**，未传的调用方零影响）：
   *   `closeOnOverlay=false` → 点击弹窗外部（遮罩）**不关闭**；
   *   `closeOnEsc=false`     → 按 Esc **不关闭**；
   *   `showClose=false`      → 不渲染头部 × 按钮。
   * 三者同时收紧即「表单弹窗」形态：关闭入口只剩底部「取消 / 确认」两个显式操作，
   * 避免误触弹窗外部导致已填内容丢失（账号「新建 / 编辑」弹窗即采用该形态）。
   */
  closeOnOverlay: { type: Boolean, default: true },
  closeOnEsc: { type: Boolean, default: true },
  showClose: { type: Boolean, default: true }
})

const emit = defineEmits(['update:modelValue', 'cancel', 'confirm'])

const SIZE_MAP = { sm: 480, md: 640, lg: 800 }
const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

const panelRef = ref(null)
const titleId = `ch-dialog-title-${useId()}`
let lastActiveElement = null

const panelWidth = computed(() => {
  const width = typeof props.size === 'number' ? props.size : SIZE_MAP[props.size] || SIZE_MAP.md
  return `min(${width}px, 90vw)`
})

const confirmText = computed(() => props.confirmText || (props.danger ? '删除' : '确认'))

const handleCancel = () => {
  emit('cancel')
  emit('update:modelValue', false)
}

/** 遮罩点击：`closeOnOverlay=false` 时**忽略**（表单弹窗防误触丢内容；仍会吞掉该次点击不外泄） */
const handleOverlayClick = () => {
  if (!props.closeOnOverlay) return
  handleCancel()
}

/** Esc 关闭 + Tab 焦点锁定（§2.11：弹窗必须焦点锁定并归还） */
const handleKeydown = (event) => {
  if (event.key === 'Escape') {
    //★ 无论是否允许 Esc 关闭都 preventDefault：避免按键继续外泄到页面（如页面级 Esc 行为）
    event.preventDefault()
    if (props.closeOnEsc) handleCancel()
    return
  }
  if (event.key !== 'Tab' || !panelRef.value) return

  const nodes = Array.from(panelRef.value.querySelectorAll(FOCUSABLE)).filter((el) => el.offsetParent !== null)
  if (nodes.length === 0) {
    event.preventDefault()
    panelRef.value.focus()
    return
  }

  const first = nodes[0]
  const last = nodes[nodes.length - 1]
  if (event.shiftKey && (document.activeElement === first || document.activeElement === panelRef.value)) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
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
