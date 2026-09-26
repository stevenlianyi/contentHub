<!-- ============================================================================
 * AppButton · L1 基础组件（Step 4）
 * ----------------------------------------------------------------------------
 * 规格：高 28/36/44（sm/md/lg）；圆角 6/8/8；禁用 opacity .45 + not-allowed + Tooltip 说明原因；
 *       loading 左侧 16px spinner 且**文字不变**；iconOnly 必须带 aria-label（§2.11）。
 * 约束：颜色只取 Token（Tailwind 语义类 / var(--ch-*)），本文件无字面色值；
 *       焦点态由 tailwind.css 的 `*:focus-visible`（2px 主色 + 2px offset）统一保证，禁止 outline:none。
 * 约定：`每屏唯一 primary` 由使用方保证（本组件不做运行时校验，避免误伤弹窗级联场景）。
 * ========================================================================== -->
<template>
  <el-tooltip
    :content="disabledReason"
    :disabled="!tipEnabled"
    placement="top"
    :show-after="200"
  >
    <span class="inline-flex" :class="block ? 'w-full' : ''">
      <button
        :type="nativeType"
        class="inline-flex items-center justify-center gap-sm whitespace-nowrap font-medium transition-colors duration-150 ease-out disabled:cursor-not-allowed disabled:opacity-[.45]"
        :class="[typeClass, sizeClass, block ? 'w-full' : '']"
        :disabled="disabled || loading"
        :aria-disabled="disabled || loading ? 'true' : undefined"
        :aria-busy="loading ? 'true' : undefined"
        :aria-label="iconOnly ? ariaLabel : undefined"
        @click="handleClick"
      >
        <i
          v-if="loading"
          class="fa fa-circle-notch fa-spin"
          :class="iconSizeClass"
          aria-hidden="true"
        ></i>
        <i v-else-if="icon" :class="[icon, iconSizeClass]" aria-hidden="true"></i>
        <span v-if="!iconOnly"><slot /></span>
      </button>
    </span>
  </el-tooltip>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  type: { type: String, default: 'secondary' }, // primary / secondary / ghost / danger / danger-solid
  size: { type: String, default: 'md' }, // sm / md / lg
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  /** 禁用原因：仅在 disabled=true 时以 Tooltip 呈现（禁用态低对比不可读，必须给出替代说明） */
  disabledReason: { type: String, default: '' },
  icon: { type: String, default: '' },
  /** 纯图标按钮：必须提供 ariaLabel（无障碍硬要求） */
  iconOnly: { type: Boolean, default: false },
  ariaLabel: { type: String, default: '' },
  nativeType: { type: String, default: 'button' },
  block: { type: Boolean, default: false }
})

const emit = defineEmits(['click'])

const TYPE_CLASS = {
  primary: 'bg-ch-primary text-ch-text-inverse hover:bg-ch-primary-hover active:bg-ch-primary-active',
  secondary:
    'border border-ch-border-light bg-ch-elevated text-ch-text-primary hover:border-ch-primary hover:text-ch-primary',
  ghost: 'bg-transparent text-ch-text-secondary hover:bg-ch-hover hover:text-ch-text-primary',
  danger: 'border border-ch-danger bg-transparent text-ch-danger hover:bg-ch-danger/10',
  'danger-solid': 'bg-ch-danger text-ch-text-inverse hover:bg-ch-danger/90 active:bg-ch-danger'
}

/** 盒高 28 / 36 / 44；圆角 sm=6、md/lg=8 */
const SIZE_CLASS = {
  sm: { box: 'h-7 rounded-md px-sm text-caption', iconOnly: 'h-7 w-7 rounded-md text-caption' },
  md: { box: 'h-9 rounded-lg px-lg text-body', iconOnly: 'h-9 w-9 rounded-lg text-body' },
  lg: { box: 'h-11 rounded-lg px-xl text-body', iconOnly: 'h-11 w-11 rounded-lg text-body' }
}

const typeClass = computed(() => TYPE_CLASS[props.type] || TYPE_CLASS.secondary)
const sizeClass = computed(() => {
  const size = SIZE_CLASS[props.size] || SIZE_CLASS.md
  return props.iconOnly ? size.iconOnly : size.box
})
const iconSizeClass = computed(() => (props.size === 'sm' ? 'text-caption' : 'text-base'))
const tipEnabled = computed(() => props.disabled && Boolean(props.disabledReason))

function handleClick(event) {
  if (props.disabled || props.loading) {
    event.preventDefault()
    return
  }
  emit('click', event)
}
</script>
