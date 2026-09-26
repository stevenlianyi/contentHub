<!-- ============================================================================
 * PermissionDenied · L1 基础组件（Step 4）
 * ----------------------------------------------------------------------------
 * 规格：文案固定为「当前角色无此权限，请联系管理员」，**不显示具体功能名**
 *       （避免暴露页面/端点存在性，故不接受 title / featureName 之类的 props）。
 * ========================================================================== -->
<template>
  <div class="flex flex-col items-center justify-center gap-md px-xl py-3xl text-center" role="alert">
    <span
      class="flex h-16 w-16 items-center justify-center rounded-full border border-dashed border-ch-border"
      aria-hidden="true"
    >
      <i class="fa fa-shield-halved text-2xl text-ch-text-tertiary"></i>
    </span>
    <p class="text-h3 text-ch-text-primary">当前角色无此权限，请联系管理员</p>
    <p v-if="description" class="max-w-[420px] text-body-s text-ch-text-secondary">{{ description }}</p>
  </div>
</template>

<script setup>
defineProps({
  description: { type: String, default: '' }
})
</script>
