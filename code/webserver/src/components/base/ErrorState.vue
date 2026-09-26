<!-- ============================================================================
 * ErrorState · L1 基础组件（Step 4）
 * ----------------------------------------------------------------------------
 * 规格：原因 + 「重试」+「查看详情」，**不允许空白**（§2.11 错误态）。
 * 安全：detail 以文本插值渲染（禁止 v-html），接口原文按纯文本展示。
 * ========================================================================== -->
<template>
  <div class="flex flex-col items-center justify-center gap-md px-xl py-3xl text-center" role="alert">
    <i class="fa fa-circle-xmark text-3xl text-ch-danger" aria-hidden="true"></i>
    <p class="text-h3 text-ch-text-primary">{{ message }}</p>
    <p v-if="hint" class="max-w-[420px] text-body-s text-ch-text-secondary">{{ hint }}</p>

    <div class="flex flex-wrap items-center justify-center gap-md">
      <AppButton type="primary" size="sm" icon="fa fa-rotate-right" @click="emit('retry')">
        {{ retryText }}
      </AppButton>
      <AppButton v-if="detail" size="sm" @click="expanded = !expanded">
        {{ expanded ? '收起详情' : detailText }}
      </AppButton>
    </div>

    <pre
      v-if="detail && expanded"
      class="ch-measure w-full overflow-x-auto whitespace-pre-wrap rounded-lg border border-ch-border bg-ch-input px-lg py-md text-left font-mono text-code text-ch-text-secondary"
    >{{ detail }}</pre>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import AppButton from '@/components/base/AppButton.vue'

defineProps({
  message: { type: String, default: '数据加载失败' },
  /** 一句话补充说明（可选），保证「原因」永远存在 */
  hint: { type: String, default: '请检查网络或稍后重试；若持续失败请联系管理员。' },
  /** 技术详情（错误码 / 后端原文），默认折叠 */
  detail: { type: String, default: '' },
  retryText: { type: String, default: '重试' },
  detailText: { type: String, default: '查看详情' }
})

const emit = defineEmits(['retry'])
const expanded = ref(false)
</script>
