<!-- ============================================================================
 * Badge · L1 基础组件（Step 4）
 * ----------------------------------------------------------------------------
 * 规格：数字徽标；`count > max` 显示 `max+`；`count <= 0` 不渲染（避免空圈）。
 * 用法：默认行内（Tab 标签旁、表格字段旁）；`absolute` 时吸附父容器右上角（图标按钮角标）。
 * ========================================================================== -->
<template>
  <span
    v-if="visible"
    class="inline-flex h-5 min-w-[20px] items-center justify-center rounded-full px-xs text-caption font-medium leading-none"
    :class="[variantClass, absolute ? 'absolute -right-1 -top-1' : '']"
    :aria-label="ariaLabel || `计数 ${count}`"
  >
    {{ text }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  count: { type: [Number, String], default: 0 },
  max: { type: Number, default: 99 },
  variant: { type: String, default: 'danger' }, // primary / danger
  absolute: { type: Boolean, default: false },
  ariaLabel: { type: String, default: '' }
})

const VARIANT_CLASS = {
  primary: 'bg-ch-primary text-ch-text-inverse',
  danger: 'bg-ch-danger text-ch-text-inverse'
}

const value = computed(() => Number(props.count) || 0)
const visible = computed(() => value.value > 0)
const text = computed(() => (value.value > props.max ? `${props.max}+` : String(value.value)))
const variantClass = computed(() => VARIANT_CLASS[props.variant] || VARIANT_CLASS.danger)
</script>
