<!-- ============================================================================
 * EmptyState · L1 基础组件（Step 4）
 * ----------------------------------------------------------------------------
 * 规格：线性单色插画 + 一句说明 + **一个主操作**（actionText 为空则不渲染按钮）。
 * 用法：列表/网格为空时由 AppTable 或页面直接内嵌；`icon` 传 chOptions 风格的完整 class 字符串。
 * ========================================================================== -->
<template>
  <div class="flex flex-col items-center justify-center gap-md px-xl py-3xl text-center">
    <span
      class="flex h-16 w-16 items-center justify-center rounded-full border border-dashed border-ch-border"
      aria-hidden="true"
    >
      <i :class="icon" class="text-2xl text-ch-text-tertiary"></i>
    </span>
    <p class="text-h3 text-ch-text-primary">{{ title }}</p>
    <p v-if="description" class="max-w-[420px] text-body-s text-ch-text-secondary">{{ description }}</p>
    <AppButton
      v-if="actionText"
      type="primary"
      size="sm"
      :disabled="actionDisabled"
      :disabled-reason="actionDisabledReason"
      @click="emit('action')"
    >
      {{ actionText }}
    </AppButton>
  </div>
</template>

<script setup>
import AppButton from '@/components/base/AppButton.vue'

defineProps({
  icon: { type: String, default: 'fa-regular fa-folder-open' },
  title: { type: String, default: '暂无数据' },
  description: { type: String, default: '' },
  actionText: { type: String, default: '' },
  /** 主操作不可用时给出原因（Tooltip 呈现），避免「按钮点了没反应」 */
  actionDisabled: { type: Boolean, default: false },
  actionDisabledReason: { type: String, default: '' }
})

const emit = defineEmits(['action'])
</script>
