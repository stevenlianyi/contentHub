<!-- ============================================================================
 * AssetReferenceList · P-04 引用主题列表（Step 8，独立文件）
 * ----------------------------------------------------------------------------
 * 用途：详情抽屉与删除确认弹窗**共用**「引用它的主题」清单 —— 这是删除安全的客户端安全网
 *   （附录 B R-21：真实 `assetdel` 不做引用检查，后端**不会**因「被引用」拒绝删除）。
 * 数据：`useAssetReferences.fetchDetail(fileID)` 的 items（topicID / topicCode / title / usageType）。
 * ★ 跳转：`topicCode` 存在时用 `<RouterLink>`（可聚焦、键盘可达）；缺失时降级为 topicID 纯文本
 *   并显式标注「编码缺失，暂不可跳转」，不伪造链接。
 * ★ 超出 REF_TITLE_LIMIT 时只显示前 10 条 + 「等 N 处」，与附录 B R-20 的口径一致。
 * ========================================================================== -->
<template>
  <div class="flex flex-col gap-sm">
    <Skeleton v-if="loading" type="detail" :rows="2" label="引用关系查询中" />

    <ErrorState
      v-else-if="error"
      :message="error"
      hint="引用关系读取失败，删除前请先确认该素材是否被主题使用。"
      @retry="emit('retry')"
    />

    <p v-else-if="!total" class="flex items-center gap-xs text-body-s text-ch-text-secondary">
      <i class="fa-regular fa-circle" aria-hidden="true"></i>
      <span>未被任何主题引用</span>
    </p>

    <template v-else>
      <p class="flex items-center gap-xs text-body-s text-ch-text-secondary">
        <i class="fa fa-link" aria-hidden="true"></i>
        <span>被 <span class="font-medium text-ch-text-primary">{{ total }}</span> 个主题引用</span>
      </p>

      <ul class="flex max-h-56 flex-col gap-xs overflow-y-auto rounded-lg border border-ch-border bg-ch-input px-md py-sm" role="list">
        <li v-for="item in visibleItems" :key="item.key" class="flex items-start gap-sm text-body-s">
          <i class="fa fa-file-lines mt-[2px] shrink-0 text-ch-text-tertiary" aria-hidden="true"></i>
          <RouterLink
            v-if="item.topicCode"
            :to="{ name: 'TopicEdit', params: { code: item.topicCode } }"
            class="min-w-0 flex-1 truncate text-ch-primary hover:text-ch-primary-hover"
            :title="`前往主题「${item.title || item.topicCode}」`"
          >
            {{ item.title || item.topicCode }}
          </RouterLink>
          <span v-else class="min-w-0 flex-1 truncate text-ch-text-secondary" :title="`topicID=${item.topicID}`">
            {{ item.title || `topicID ${item.topicID}` }}（编码缺失，暂不可跳转）
          </span>
          <span class="shrink-0 text-caption text-ch-text-tertiary">
            {{ USAGE_TYPE_MAP[item.usageType] || item.usageType || '附图' }}{{ item.caption ? ` · ${item.caption}` : '' }}
          </span>
        </li>
        <li v-if="extraCount" class="text-caption text-ch-text-tertiary">
          等 {{ extraCount }} 处（仅列出前 {{ REF_TITLE_LIMIT }} 条标题，见附录 B R-20）
        </li>
      </ul>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import ErrorState from '@/components/base/ErrorState.vue'
import Skeleton from '@/components/base/Skeleton.vue'
import { USAGE_TYPE_MAP } from '@/config/chOptions'
import { REF_TITLE_LIMIT } from '@/views/assets/useAssetReferences'

const props = defineProps({
  items: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  extraCount: { type: Number, default: 0 },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' }
})

const emit = defineEmits(['retry'])

const visibleItems = computed(() => props.items.slice(0, REF_TITLE_LIMIT))
</script>
