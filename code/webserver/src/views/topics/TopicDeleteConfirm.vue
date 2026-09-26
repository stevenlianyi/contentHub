<!-- ============================================================================
 * TopicDeleteConfirm · P-02 删除二次确认（Step 6，破坏性操作）
 * ----------------------------------------------------------------------------
 * 规格（计划 Step 6 第 6/7 点 + 裁定 H）：
 *   · `AppDialog` + `danger` 变体（danger 描边 + danger-solid 确认按钮）；
 *   · **必须输入标题**才能确认：单条删除要求输入该主题的完整标题；
 *     批量删除要求输入「删除 N 个主题」（同时在上方列出待删标题与数量）；
 *   · 确认按钮文案固定为「确认删除」——★ 不得出现「确定」（含任何同义简写）；
 *   · 点确认**不自动关闭**：由父级在请求成功后置 false，失败时保留已输入内容（§2.5 第 3 条）；
 *   · 焦点锁定 / Esc 关闭 / 焦点归还由 `AppDialog` 统一实现（§2.11）。
 * ★ 删除是破坏性操作，不提供「回车即通过」的捷径：输入不匹配时确认按钮保持 disabled，
 *   并给出可读的失败原因（不依赖颜色单独表达）。
 * ========================================================================== -->
<template>
  <AppDialog
    :model-value="modelValue"
    :title="title"
    danger
    @update:model-value="emit('update:modelValue', $event)"
    @cancel="emit('cancel')"
  >
    <div class="flex flex-col gap-md">
      <p class="text-body text-ch-text-primary">
        即将删除 {{ summary }}，删除后不可恢复，请确认。
      </p>

      <ul v-if="topics.length > 1" class="max-h-40 overflow-y-auto rounded-lg border border-ch-border bg-ch-input px-md py-sm">
        <li v-for="item in topics" :key="item.recID || item.topicCode" class="truncate text-body-s text-ch-text-secondary">
          · {{ item.title || '（无标题）' }}
        </li>
      </ul>

      <label class="flex flex-col gap-xs">
        <span class="text-body-s text-ch-text-secondary">
          请输入 <code class="rounded-sm bg-ch-input px-xs font-mono text-code text-ch-text-primary">{{ expectText }}</code> 以确认：
        </span>
        <input
          v-model="typed"
          type="text"
          class="h-9 rounded-md border bg-ch-input px-md text-body text-ch-text-primary placeholder:text-ch-text-tertiary focus:border-ch-border-focus"
          :class="typed && !matched ? 'border-ch-danger' : 'border-ch-border'"
          :placeholder="expectText"
          :aria-invalid="typed && !matched ? 'true' : undefined"
          aria-label="输入确认文本"
          autocomplete="off"
        />
      </label>

      <p v-if="typed && !matched" class="flex items-center gap-xs text-caption text-ch-danger" role="alert">
        <i class="fa fa-circle-xmark" aria-hidden="true"></i>
        <span>输入与要求不一致，请照抄上方文本（区分大小写与空格）。</span>
      </p>
    </div>

    <template #footer>
      <AppButton size="md" :disabled="loading" @click="emit('update:modelValue', false)">取消</AppButton>
      <AppButton
        type="danger-solid"
        size="md"
        icon="fa fa-trash"
        :disabled="!matched"
        :disabled-reason="'请先输入上方要求的确认文本'"
        :loading="loading"
        @click="emit('confirm')"
      >
        确认删除
      </AppButton>
    </template>
  </AppDialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import AppButton from '@/components/base/AppButton.vue'
import AppDialog from '@/components/base/AppDialog.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 待删除的主题数组（单条 = 行内删除；多条 = 批量删除） */
  topics: { type: Array, default: () => [] },
  /** 请求进行中（按钮转圈并禁用，防止重复提交） */
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'cancel', 'confirm'])

const typed = ref('')

const title = computed(() => (props.topics.length > 1 ? `批量删除 ${props.topics.length} 个主题` : '删除主题'))
const summary = computed(() =>
  props.topics.length > 1 ? `${props.topics.length} 个主题` : `主题「${props.topics[0]?.title || ''}」`
)

/**
 * 需照抄的确认文本：
 *   · 单条 → 该主题的完整标题（满足裁定 H「必须输入标题」）；
 *   · 批量 → 「删除 N 个主题」（标题逐条列出，避免要求用户抄写 N 条标题造成误操作）。
 */
const expectText = computed(() =>
  props.topics.length > 1 ? `删除 ${props.topics.length} 个主题` : String(props.topics[0]?.title || '')
)

const matched = computed(() => Boolean(expectText.value) && typed.value.trim() === expectText.value.trim())

/** 每次打开重置输入（关闭后不保留上一次的确认文本） */
watch(
  () => props.modelValue,
  (open) => {
    if (open) typed.value = ''
  }
)
</script>
