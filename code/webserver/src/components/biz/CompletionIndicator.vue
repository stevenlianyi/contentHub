<!-- ============================================================================
 * CompletionIndicator · L2 业务组件（Step 7 · 越界授权新建，裁定 J）
 * ----------------------------------------------------------------------------
 * 用途：表达**完成度**（「已渲染/未选择」这类进度信息），对应计划 §2.6 末段与 .md 4.2 P-03
 *   右侧完成度辅助栏。★ 与 StateBadge 是两回事：
 *     · StateBadge = 五类状态机的取值徽章，颜色来自 chOptions 字典（status.*）；
 *     · 本组件 = 布尔型完成度，**统一 info 色**（`tokens.status.info`，见 src/js/tokens.js），
 *       ★ 不复用 StateBadge 的样式与字典，也不占用主题状态位（不得新增中间态）。
 * 三重编码（形状图标 + 颜色 + 文字）：
 *   完成 `fa fa-circle-check`（实心对勾，info 色 + 「已完成」文字）；
 *   未完成 `fa-regular fa-circle`（空心圆，text/tertiary + 「未完成」文字），
 *   灰度（色盲模拟）下仍可区分，且每项都带 `sr-only` 状态词。
 * ========================================================================== -->
<template>
  <span
    class="inline-flex items-center gap-sm text-body-s"
    :class="done ? 'text-ch-info' : 'text-ch-text-tertiary'"
  >
    <i :class="done ? 'fa fa-circle-check' : 'fa-regular fa-circle'" aria-hidden="true"></i>
    <span>{{ label }}</span>
    <span v-if="hint" class="text-caption text-ch-text-tertiary">{{ hint }}</span>
    <span class="sr-only">{{ done ? '已完成' : '未完成' }}</span>
  </span>
</template>

<script setup>
defineProps({
  done: { type: Boolean, default: false },
  label: { type: String, default: '' },
  /** 附注（如「超出上限 5000 字」/「未选择版式」） */
  hint: { type: String, default: '' }
})
</script>
