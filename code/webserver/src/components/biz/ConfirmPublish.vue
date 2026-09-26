<!-- ============================================================================
 * ConfirmPublish · L2 业务组件（Step 4）
 * ----------------------------------------------------------------------------
 * 规格：宽 480；**复述 主题 / 账号 / 版式 / 产物**；明确「本次为草稿投递，群发需在公众号后台
 *       手动完成」；显示**剩余配额**；按钮为**动词**（「确认推送草稿」/「取消」）。
 * ★ 文案禁令（裁定 H）：本组件内**禁止出现「确定 / 是 / 否」**。
 * ★ props 为 `visible`（不是 modelValue），emits 为 `confirm` / `cancel`（按计划保留）。
 * ★ 仅承载「投递到草稿箱」的确认动作；自动发布闸门与撤销窗在后续步骤处理。
 * ========================================================================== -->
<template>
  <AppDialog
    :model-value="visible"
    title="确认投递"
    size="sm"
    @cancel="emit('cancel')"
  >
    <dl class="flex flex-col gap-md text-body-s">
      <div v-for="row in summaryRows" :key="row.label" class="flex gap-lg">
        <dt class="w-20 shrink-0 text-ch-text-tertiary">{{ row.label }}</dt>
        <dd class="min-w-0 flex-1 truncate text-ch-text-primary" :title="row.value">
          {{ row.value || '—' }}
        </dd>
      </div>
    </dl>

    <div class="mt-lg flex flex-col gap-sm rounded-lg border border-ch-border bg-ch-input px-lg py-md text-body-s">
      <p class="flex items-start gap-sm text-ch-text-secondary">
        <i class="fa fa-circle-info mt-xs shrink-0" aria-hidden="true"></i>
        <span>本次为草稿投递，群发需在公众号后台手动完成。</span>
      </p>
      <p class="flex items-center gap-sm" :class="remaining > 0 ? 'text-ch-text-secondary' : 'text-ch-danger'">
        <i class="fa fa-chart-simple shrink-0" aria-hidden="true"></i>
        <span>剩余配额：{{ remaining }} / {{ limit }}（今日已用 {{ used }}）</span>
      </p>
    </div>

    <template #footer>
      <AppButton size="md" :disabled="confirmLoading" @click="emit('cancel')">取消</AppButton>
      <AppButton
        type="primary"
        size="md"
        :loading="confirmLoading"
        :disabled="remaining <= 0"
        :disabled-reason="remaining <= 0 ? '今日剩余配额为 0，请明日再试或调整账号' : ''"
        @click="emit('confirm')"
      >
        确认推送草稿
      </AppButton>
    </template>
  </AppDialog>
</template>

<script setup>
import { computed } from 'vue'
import AppDialog from '@/components/base/AppDialog.vue'
import AppButton from '@/components/base/AppButton.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  /** { title | topicTitle | topicCode, ... } */
  topic: { type: Object, default: null },
  /** { accountName | platformAccount, platform, ... } */
  account: { type: Object, default: null },
  /** { layoutName | layoutCode, layoutType } */
  layout: { type: Object, default: null },
  /** { artifactID | artifactCode, outputKind, fileUrl } */
  artifact: { type: Object, default: null },
  /** { used, limit } */
  quota: { type: Object, default: null },
  confirmLoading: { type: Boolean, default: false }
})

const emit = defineEmits(['confirm', 'cancel'])

const used = computed(() => Number(props.quota?.used || 0))
const limit = computed(() => Number(props.quota?.limit || 0))
const remaining = computed(() => Math.max(0, limit.value - used.value))

const summaryRows = computed(() => [
  {
    label: '主题',
    value: props.topic?.title || props.topic?.topicTitle || props.topic?.topicCode || ''
  },
  {
    label: '账号',
    value: props.account?.accountName || props.account?.platformAccount || props.account?.accountCode || ''
  },
  {
    label: '版式',
    value: props.layout?.layoutName || props.layout?.layoutCode || ''
  },
  {
    label: '产物',
    value: props.artifact?.artifactID || props.artifact?.artifactCode || props.artifact?.outputKind || ''
  }
])
</script>
