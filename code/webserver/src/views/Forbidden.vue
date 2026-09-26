<template>
  <main class="flex min-h-screen items-center justify-center bg-ch-base p-2xl">
    <section
      class="flex w-full max-w-[480px] flex-col items-center gap-lg rounded-2xl border border-ch-border bg-ch-surface p-3xl text-center"
      role="alert"
    >
      <p class="font-mono text-display text-ch-text-tertiary">403</p>
      <!-- 不显示具体功能名（计划 Step 2 第 9 点） -->
      <h1 class="text-h2 text-ch-text-primary">当前角色无此权限，请联系管理员</h1>
      <p class="text-body-s text-ch-text-secondary">如需访问该功能，请联系管理员为你的账号分配对应角色。</p>
      <RouterLink
        to="/"
        class="mt-md flex h-9 min-w-[112px] items-center justify-center rounded-lg bg-ch-primary px-lg text-body font-medium text-ch-text-inverse transition-colors duration-150 ease-out hover:bg-ch-primary-hover"
      >
        返回工作台
      </RouterLink>
    </section>
  </main>
</template>

<script setup>
import { RouterLink } from 'vue-router'
</script>
