<!-- ============================================================================
 * CheckToolbar · P-09 页私有组件（Step 13）
 * ----------------------------------------------------------------------------
 * 职责（裁定 F / G / J）：
 *   · 平台选择器：`publishcheck` 的 `platform` **必须非空**（后端两者都空 → 直接 C7），
 *     缺省取所选版式所属平台，页内保证有值（缺省 `wechat_mp`）；
 *   · 自定义敏感词（逗号分隔）：留空 = 不传 `sensitiveWords` → 用后端默认词表；
 *   · 「重新校验」：重跑 `publishcheck`（调用方带 `silent`）；
 *   · 「标记通过」：仅 `errorCount === 0` 可用，否则 `disabled` + Tooltip 说明原因。
 * ★ 参数改动后**不自动重跑**（每次 `publishcheck` 都会给限流计数 +1，自动重跑会污染计数），
 *   而是给出「参数已改，点击重新校验生效」的提示。
 * ★ 表单控件一律原生 `<select>` / `<input>`（§2.11：禁止 `<div>` 模拟控件）。
 * ========================================================================== -->
<template>
  <div class="flex flex-col gap-md rounded-xl border border-ch-border bg-ch-surface px-xl py-lg">
    <div class="flex flex-wrap items-end gap-lg">
      <label class="flex min-w-[200px] flex-col gap-xs">
        <span class="text-body-s text-ch-text-secondary">校验平台（按 ch_platform 规格校验）</span>
        <select
          :value="platform"
          class="h-9 rounded-md border border-ch-border bg-ch-input px-md text-body text-ch-text-primary focus:border-ch-border-focus"
          :disabled="loading"
          aria-label="校验平台"
          @change="emit('update:platform', $event.target.value)"
        >
          <option v-for="item in options" :key="item.platformCode" :value="item.platformCode">
            {{ item.platformName || PLATFORM_MAP[item.platformCode]?.label || item.platformCode }}
          </option>
        </select>
      </label>

      <label class="flex min-w-[220px] flex-1 flex-col gap-xs">
        <span class="text-body-s text-ch-text-secondary">自定义敏感词（逗号分隔；留空用服务端默认词表）</span>
        <input
          :value="sensitiveWords"
          type="text"
          class="h-9 rounded-md border border-ch-border bg-ch-input px-md text-body text-ch-text-primary placeholder:text-ch-text-tertiary focus:border-ch-border-focus"
          placeholder="如：最有效, 国家级"
          :disabled="loading"
          aria-label="自定义敏感词"
          @input="emit('update:sensitiveWords', $event.target.value)"
        />
      </label>

      <div class="flex flex-wrap items-center gap-md">
        <AppButton icon="fa fa-rotate-right" :loading="loading" @click="emit('check')">重新校验</AppButton>
        <AppButton
          type="primary"
          icon="fa fa-shield-halved"
          :disabled="markDisabled"
          :disabled-reason="markReason"
          @click="emit('mark-pass')"
        >
          标记通过
        </AppButton>
      </div>
    </div>

    <p class="flex flex-wrap items-center gap-md text-caption text-ch-text-tertiary">
      <span v-if="platformSummary">{{ platformSummary }}</span>
      <span v-if="dirty" class="flex items-center gap-xs text-ch-warning">
        <i class="fa fa-triangle-exclamation" aria-hidden="true"></i>
        参数已修改，点击「重新校验」后生效
      </span>
    </p>
  </div>
</template>

<script setup>
import AppButton from '@/components/base/AppButton.vue'
import { PLATFORM_MAP } from '@/config/chOptions'

defineProps({
  /** 当前选中平台（非空；调用方保证缺省值） */
  platform: { type: String, default: '' },
  /** `platformqry` 归一化后的平台目录（免登录端点；为空时退回 `platform` 自身） */
  options: { type: Array, default: () => [] },
  /** 自定义敏感词输入（逗号分隔的原始文本） */
  sensitiveWords: { type: String, default: '' },
  /** 平台规格一行摘要（数据来自 ch_platform，前端不硬编码） */
  platformSummary: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  /** 「标记通过」是否禁用（存在阻断项即禁用） */
  markDisabled: { type: Boolean, default: false },
  /** 禁用原因（Tooltip 文案，§2.11：禁用态必须给出替代说明） */
  markReason: { type: String, default: '' },
  /** 参数（平台 / 敏感词）自上次校验后是否已变更 */
  dirty: { type: Boolean, default: false }
})

const emit = defineEmits(['update:platform', 'update:sensitiveWords', 'check', 'mark-pass'])
</script>
