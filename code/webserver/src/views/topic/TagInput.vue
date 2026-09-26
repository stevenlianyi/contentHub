<!-- ============================================================================
 * TagInput · P-03 Tab1「标签」字段（Step 7）
 * ----------------------------------------------------------------------------
 * 规格（计划 Step 7 字段表）：`tagList` = **逗号分隔字符串**，单标签 ≤ 20 字。
 *   交互：回车 / 逗号（半角 `,` 与全角 `，`）生成 Chip；`×` 删除；空输入按 Backspace 删末项；
 *        blur 时把未提交的输入一并落成 Chip（避免「打了字没回车就保存丢了」）。
 * 契约：**对外始终是字符串数组**（`v-model` 为 Array），服务端字符串 ↔ 数组的编解码由
 *   `useTopicDraft.js` 统一负责（裁定 H：提交时拼成逗号分隔串）。
 * ★ 空值无法清空字段（裁定 G）：删掉最后一个标签后保存不会提交该字段，故此处
 *   **不承诺「清空会生效」**，仅在 hint 中说明服务端语义。
 * 无障碍（§2.11）：原生 input/button；每个 `×` 带 aria-label；Chip 列表为 role="list"。
 * ========================================================================== -->
<template>
  <div class="flex flex-col gap-xs">
    <label v-if="label" :for="inputId" class="flex items-center gap-xs text-body-s text-ch-text-secondary">
      <span>{{ label }}</span>
      <span v-if="required" class="text-ch-danger" aria-hidden="true">*</span>
    </label>

    <div
      class="flex flex-wrap items-center gap-sm rounded-md border bg-ch-input px-md py-sm"
      :class="error ? 'border-ch-danger' : 'border-ch-border focus-within:border-ch-border-focus'"
    >
      <ul v-if="tags.length" class="flex flex-wrap items-center gap-sm" role="list">
        <li
          v-for="(tag, index) in tags"
          :key="`${tag}-${index}`"
          class="inline-flex items-center gap-xs rounded-sm bg-ch-primary-subtle px-sm py-[2px] text-caption text-ch-primary"
        >
          <span>{{ tag }}</span>
          <button
            type="button"
            class="text-ch-primary transition-colors duration-150 ease-out hover:text-ch-danger"
            :aria-label="`删除标签 ${tag}`"
            :disabled="disabled"
            @click="removeAt(index)"
          >
            <i class="fa fa-xmark" aria-hidden="true"></i>
          </button>
        </li>
      </ul>

      <input
        :id="inputId"
        ref="inputRef"
        class="h-7 min-w-[140px] flex-1 bg-transparent text-body text-ch-text-primary placeholder:text-ch-text-tertiary focus-visible:outline-none"
        type="text"
        :value="draft"
        :placeholder="tags.length ? '继续添加…' : placeholder"
        :disabled="disabled"
        autocomplete="off"
        :aria-invalid="error ? 'true' : undefined"
        @input="draft = $event.target.value"
        @keydown="onKeydown"
        @blur="commitDraft"
      />
    </div>

    <p v-if="error" class="flex items-center gap-xs text-caption text-ch-danger" role="alert">
      <i class="fa fa-circle-xmark" aria-hidden="true"></i>
      <span>{{ error }}</span>
    </p>
    <p v-else-if="hint" class="text-caption text-ch-text-tertiary">{{ hint }}</p>
  </div>
</template>

<script setup>
import { computed, ref, useId } from 'vue'

/** 单标签字数上限（后端 tagList 为 VARCHAR(512)，前端按计划约定单标签 ≤ 20 字） */
const TAG_MAX_LEN = 20
const SPLIT_PATTERN = /[,，]/

const props = defineProps({
  /** 标签数组（对外契约：Array；不与服务端的逗号串直接混用） */
  modelValue: { type: Array, default: () => [] },
  label: { type: String, default: '标签' },
  placeholder: { type: String, default: '输入后按回车或逗号生成' },
  error: { type: String, default: '' },
  hint: { type: String, default: '逗号分隔，单个标签 ≤ 20 字' },
  required: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue'])

const inputId = `ch-tags-${useId()}`
const inputRef = ref(null)
const draft = ref('')

const tags = computed(() => (Array.isArray(props.modelValue) ? props.modelValue : []))

/** 提交一个候选标签：去空白、超长拒绝、去重 */
function pushTag(raw) {
  const value = String(raw || '').trim()
  if (!value) return false
  if (Array.from(value).length > TAG_MAX_LEN) return false
  if (tags.value.includes(value)) return false
  emit('update:modelValue', [...tags.value, value])
  return true
}

/** 把输入框内容（可能含多个逗号）全部提交 */
function commitDraft() {
  const raw = draft.value
  if (!raw) return
  const parts = raw.split(SPLIT_PATTERN)
  let next = tags.value
  for (const part of parts) {
    const value = part.trim()
    if (!value) continue
    if (Array.from(value).length > TAG_MAX_LEN) continue
    if (next.includes(value)) continue
    next = [...next, value]
  }
  draft.value = ''
  if (next !== tags.value) emit('update:modelValue', next)
}

function removeAt(index) {
  const next = [...tags.value]
  next.splice(index, 1)
  emit('update:modelValue', next)
}

function onKeydown(event) {
  if (event.key === 'Enter' || event.key === ',' || event.key === '，') {
    event.preventDefault()
    commitDraft()
    return
  }
  if (event.key === 'Backspace' && !draft.value && tags.value.length) {
    event.preventDefault()
    removeAt(tags.value.length - 1)
  }
}

/** 供页面在「去修正」时聚焦 */
defineExpose({ focus: () => inputRef.value?.focus() })
</script>
