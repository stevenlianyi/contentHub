<!-- ============================================================================
 * FormInput · L1 基础组件（Step 4）
 * ----------------------------------------------------------------------------
 * ★ prop 名冻结（计划 Step 4 明确要求）：`prefixIcon` / `suffixIcon` / `error` / `help`。
 *   不得复现基线的 `icon` / `showToggle` 与调用方 `error` 不匹配的缺陷。
 * 规格：聚焦 border/focus + shadow/focus；错误态边框 danger + 12px 文案 + 图标；
 *       字数计数在右侧，≥90% 转 warning、越界转 danger（计数口径同后端 countWords 之外的
 *       字符口径 charCount，标题/简介/摘要用字符数）。
 * 依赖方向：base 不依赖 biz，故计数条在本文件内实现，不复用 biz/WordCounter。
 * ========================================================================== -->
<template>
  <div class="flex flex-col gap-xs">
    <label v-if="label" :for="fieldId" class="flex items-center gap-xs text-body-s text-ch-text-secondary">
      <span>{{ label }}</span>
      <span v-if="required" class="text-ch-danger" aria-hidden="true">*</span>
      <span v-if="required" class="sr-only">必填</span>
    </label>

    <!-- 焦点可见由本容器承担（focus-within: 边框转主色 + 3px 光圈，圆角随容器）。
         故内层 input/textarea 用 `focus-visible:outline-none` 抑制全局
         `*:focus-visible` 的 2px 方角 outline（tailwind.css @layer base）——
         否则会与外层圆角光圈形成「外圆内方」双重描边。焦点指示依然可见，未弱化无障碍。 -->
    <div
      class="flex items-center gap-sm rounded-md border bg-ch-input px-md transition-colors duration-150 ease-out"
      :class="boxClass"
    >
      <i v-if="prefixIcon" :class="prefixIcon" class="shrink-0 text-caption text-ch-text-tertiary" aria-hidden="true"></i>

      <textarea
        v-if="isTextarea"
        :id="fieldId"
        ref="controlRef"
        class="w-full resize-y bg-transparent text-body text-ch-text-primary placeholder:text-ch-text-tertiary focus-visible:outline-none"
        :class="controlClass"
        :value="modelValue"
        :placeholder="placeholder"
        :rows="rows"
        :disabled="disabled"
        :aria-invalid="error ? 'true' : undefined"
        :aria-describedby="describedBy"
        @input="handleInput"
        @focus="emit('focus', $event)"
        @blur="handleBlur"
      ></textarea>

      <input
        v-else
        :id="fieldId"
        ref="controlRef"
        class="w-full bg-transparent text-body text-ch-text-primary placeholder:text-ch-text-tertiary focus-visible:outline-none"
        :class="controlClass"
        :type="controlType"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :autocomplete="autocomplete"
        :aria-invalid="error ? 'true' : undefined"
        :aria-describedby="describedBy"
        @input="handleInput"
        @focus="emit('focus', $event)"
        @blur="handleBlur"
      />

      <i v-if="suffixIcon" :class="suffixIcon" class="shrink-0 text-caption text-ch-text-tertiary" aria-hidden="true"></i>

      <button
        v-if="isPassword"
        type="button"
        class="shrink-0 rounded-sm p-xs text-ch-text-tertiary transition-colors duration-150 ease-out hover:text-ch-text-primary"
        :aria-label="revealed ? '隐藏密码' : '显示密码'"
        :aria-pressed="revealed ? 'true' : 'false'"
        @click="revealed = !revealed"
      >
        <i :class="revealed ? 'fa fa-eye-slash' : 'fa fa-eye'" aria-hidden="true"></i>
      </button>
    </div>

    <div class="flex items-start justify-between gap-md">
      <p
        v-if="error || help"
        class="flex items-center gap-xs text-caption"
        :class="error ? 'text-ch-danger' : 'text-ch-text-tertiary'"
        :id="`${fieldId}-msg`"
      >
        <i v-if="error" class="fa fa-circle-xmark" aria-hidden="true"></i>
        <span>{{ error || help }}</span>
      </p>
      <span v-else class="flex-1"></span>

      <span
        v-if="showCounter"
        class="shrink-0 text-caption tabular-nums"
        :class="counterClass"
        :aria-label="`已输入 ${count} 个字符，上限 ${wordLimit} 个字符`"
      >
        {{ count }} / {{ wordLimit }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, useId } from 'vue'
import { charCount } from '@/utils/common'

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  label: { type: String, default: '' },
  /** text / password / number / textarea */
  type: { type: String, default: 'text' },
  placeholder: { type: String, default: '' },
  prefixIcon: { type: String, default: '' },
  suffixIcon: { type: String, default: '' },
  /** 错误文案：非空即进入错误态（边框 danger + 12px 文案 + 图标） */
  error: { type: String, default: '' },
  /** 辅助说明：无 error 时展示 */
  help: { type: String, default: '' },
  required: { type: Boolean, default: false },
  /** 字数上限：给定即显示右侧计数（≥90% warning、越界 danger） */
  wordLimit: { type: Number, default: 0 },
  disabled: { type: Boolean, default: false },
  rows: { type: Number, default: 4 },
  autocomplete: { type: String, default: 'off' }
})

const emit = defineEmits(['update:modelValue', 'blur', 'focus'])

/** 唯一 id：用 Vue 3.5 的 useId（同页多实例、label↔control、aria-describedby 均需唯一） */
const fieldId = `ch-field-${useId()}`
const controlRef = ref(null)
const revealed = ref(false)

const isTextarea = computed(() => props.type === 'textarea')
const isPassword = computed(() => props.type === 'password')
const controlType = computed(() => (isPassword.value && revealed.value ? 'text' : props.type))
const controlClass = computed(() =>
  isTextarea.value ? 'min-h-[96px] py-sm leading-relaxed' : 'h-9 py-0'
)

const boxClass = computed(() => {
  const base = props.error ? 'border-ch-danger' : 'border-ch-border'
  return `${base} focus-within:border-ch-border-focus focus-within:shadow-focus`
})

const describedBy = computed(() => (props.error || props.help ? `${fieldId}-msg` : undefined))

const count = computed(() => charCount(props.modelValue))
const showCounter = computed(() => Number(props.wordLimit) > 0)
const counterClass = computed(() => {
  if (!showCounter.value) return ''
  if (count.value > props.wordLimit) return 'text-ch-danger'
  if (count.value >= props.wordLimit * 0.9) return 'text-ch-warning'
  return 'text-ch-text-tertiary'
})

function handleInput(event) {
  emit('update:modelValue', event.target.value)
}

function handleBlur(event) {
  emit('blur', event.target.value)
}

/** 供页面在「去修正」/「定位」时编程式聚焦 */
defineExpose({
  focus: () => controlRef.value?.focus()
})
</script>
