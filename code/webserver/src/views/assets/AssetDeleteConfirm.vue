<!-- ============================================================================
 * AssetDeleteConfirm · P-04 删除素材二次确认（Step 8，破坏性操作）
 * ----------------------------------------------------------------------------
 * 规格（计划 Step 8 要点 3 + 裁定 D）：
 *   · `AppDialog` + `danger` 变体；确认按钮文案固定 **「确认删除素材」**（动词，★ 不出现「确定」）；
 *   · `未引用` 才可直接删除；`引用 N 处` 时**先列出引用它的主题**（可点击跳转）再删除；
 *   · ★ 引用检查是**客户端安全网**：真实 `assetService.deleteAsset` 为软删、**不做引用检查**
 *     （附录 B R-21），后端不会替我们拦住「删掉仍在用的素材」，故必须在此显式复述后果；
 *   · 点确认**不自动关闭**：由父级在请求成功后置 false，失败时保留弹窗（§2.5 第 3 条）。
 * ========================================================================== -->
<template>
  <AppDialog
    :model-value="modelValue"
    title="删除素材"
    danger
    @update:model-value="emit('update:modelValue', $event)"
    @cancel="emit('cancel')"
  >
    <div class="flex flex-col gap-lg">
      <p class="text-body text-ch-text-primary">
        即将删除素材「{{ displayName }}」。删除为软删除（只标记 delFlag，不删除文件服务上的对象），
        且服务端不会因「被引用」而拒绝删除。
      </p>

      <div v-if="referenced" class="flex items-start gap-sm rounded-lg border border-ch-warning/40 bg-ch-warning/10 px-md py-sm">
        <i class="fa fa-triangle-exclamation mt-xs shrink-0 text-body text-ch-warning" aria-hidden="true"></i>
        <p class="text-body-s text-ch-text-secondary">
          该素材仍被 <span class="font-medium text-ch-text-primary">{{ total }}</span> 个主题引用：
          删除后这些主题中的附图会指向已删除的素材，请确认影响范围后再操作。
        </p>
      </div>

      <AssetReferenceList
        :items="items"
        :total="total"
        :extra-count="extraCount"
        :loading="refLoading"
        :error="refError"
        @retry="emit('retry-ref')"
      />
    </div>

    <template #footer>
      <AppButton size="md" :disabled="deleting" @click="emit('update:modelValue', false)">取消</AppButton>
      <AppButton
        type="danger-solid"
        size="md"
        icon="fa fa-trash"
        :loading="deleting"
        @click="emit('confirm')"
      >
        确认删除素材
      </AppButton>
    </template>
  </AppDialog>
</template>

<script setup>
import { computed } from 'vue'
import AppButton from '@/components/base/AppButton.vue'
import AppDialog from '@/components/base/AppDialog.vue'
import AssetReferenceList from '@/views/assets/AssetReferenceList.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 待删除素材（assetqry 的一行；缺省表示未选中） */
  asset: { type: Object, default: null },
  refLoading: { type: Boolean, default: false },
  refError: { type: String, default: '' },
  refTotal: { type: Number, default: 0 },
  refItems: { type: Array, default: () => [] },
  refExtraCount: { type: Number, default: 0 },
  deleting: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'cancel', 'confirm', 'retry-ref'])

const total = computed(() => Number(props.refTotal) || 0)
const referenced = computed(() => total.value > 0)
/** 素材名优先取原始文件名（origName），退到 fileName / fileID，保证「删的是哪一张」明确 */
const displayName = computed(() => {
  const asset = props.asset || {}
  return String(asset.origName || asset.fileName || asset.label || asset.fileID || '未命名素材')
})
const items = computed(() => props.refItems)
const extraCount = computed(() => Number(props.refExtraCount) || 0)
</script>
