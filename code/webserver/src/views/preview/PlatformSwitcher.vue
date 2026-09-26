<!-- ============================================================================
 * PlatformSwitcher · P-08 预览页平台切换（Step 10）
 * ----------------------------------------------------------------------------
 * 三档：微信 / 小红书 / 通用（顺序固定取 `chOptions.PLATFORM_ORDER`，名称/识别色取 `PLATFORM_MAP`）。
 * ★ 不可用组合**不提供入口**：`platforms` 由页面用 `availablePlatforms(layoutCode)`
 *   （即 `LAYOUT_PLATFORM_MATRIX` 矩阵口径，§2.7 / 裁定 C）过滤后传入，
 *   例如「小红书 + carousel_v1」不会出现在列表中（不灰显、不占位）。
 * ★ 切换只改 URL query（`?platform=`）并由页面重新 `topicrender`（裁定 E），
 *   本组件**不发起任何请求**，也不做平台 → 形态的判定（该判定在 usePreviewRender / Preview.vue）。
 * ★ 无障碍：每个按钮带 `aria-label`（含目标平台名）+ `aria-pressed`；容器 `role="group"`。
 * ★ 本组件位于 `.preview-scope` **之外**（应用级暗色区域），故可使用应用级 Token 类。
 * ★ 不含任何投递 / 发布入口（小红书本期仅导出素材包）。
 * ========================================================================== -->
<template>
  <div class="flex items-center gap-sm" role="group" aria-label="切换预览平台">
    <button
      v-for="code in platforms"
      :key="code"
      type="button"
      class="inline-flex h-7 items-center gap-xs rounded-md border px-sm text-caption transition-colors duration-150 ease-out disabled:cursor-not-allowed disabled:opacity-[.45]"
      :class="
        code === platform
          ? 'border-ch-primary bg-ch-primary-subtle text-ch-primary'
          : 'border-ch-border-light bg-ch-elevated text-ch-text-secondary hover:border-ch-primary hover:text-ch-primary'
      "
      :disabled="loading && code !== platform"
      :aria-pressed="code === platform ? 'true' : 'false'"
      :aria-label="`切换到${labelOf(code)}预览`"
      :title="`切换到${labelOf(code)}预览`"
      @click="emit('change', code)"
    >
      <i :class="iconOf(code)" aria-hidden="true"></i>
      <span>{{ labelOf(code) }}</span>
    </button>

    <span v-if="platforms.length < 3" class="text-caption text-ch-text-tertiary">
      （当前版式仅 {{ platforms.length }} 个可用平台）
    </span>
  </div>
</template>

<script setup>
import { PLATFORM_MAP } from '@/config/chOptions'

defineProps({
  /** 当前生效平台编码 */
  platform: { type: String, default: '' },
  /** 可用平台编码列表（页面已按矩阵过滤，不可用组合不传入） */
  platforms: { type: Array, default: () => [] },
  /** 渲染中：非当前平台的按钮禁用（避免并发渲染同一主题） */
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['change'])

/** 平台识别图标（功能性图标，与 PlatformChip 同口径，不受 §2.6 状态图标表约束） */
const PLATFORM_ICON = {
  wechat_mp: 'fa fa-comment-dots',
  xiaohongshu: 'fa fa-book-open',
  generic: 'fa fa-code'
}

const labelOf = (code) => PLATFORM_MAP[code]?.label || String(code || '未知平台')
const iconOf = (code) => PLATFORM_ICON[code] || 'fa fa-circle'
</script>
