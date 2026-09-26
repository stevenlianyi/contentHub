<template>
  <div class="flex h-screen overflow-hidden bg-ch-base">
    <!-- 无障碍：首个 Tab 停靠点为「跳到主内容」（视觉隐藏，聚焦时显示） -->
    <a class="ch-skip-link" href="#ch-content">跳到主内容</a>

    <!-- ≥1024px：固定侧栏（可折叠 240 ↔ 64） -->
    <AppSidebar
      v-if="isDesktop"
      class="shrink-0"
      :collapsed="collapsed"
      @toggle-collapse="toggleCollapse"
    />

    <!-- <1024px：侧栏转抽屉，由顶栏汉堡按钮唤出（size 240px） -->
    <el-drawer
      v-if="!isDesktop"
      v-model="drawerVisible"
      class="ch-nav-drawer"
      direction="ltr"
      size="240px"
      :with-header="false"
    >
      <AppSidebar mode="drawer" @navigate="drawerVisible = false" />
    </el-drawer>

    <div class="flex min-w-0 flex-1 flex-col">
      <AppTopBar
        :is-desktop="isDesktop"
        :collapsed="collapsed"
        :drawer-open="drawerVisible"
        @toggle-sidebar="handleToggleSidebar"
      />

      <!-- 仅内容区滚动：Sidebar / TopBar 固定，避免嵌套滚动容器 -->
      <main id="ch-content" class="flex-1 overflow-y-auto">
        <div class="mx-auto w-full max-w-[var(--ch-content-max-w)] px-2xl py-2xl">
          <RouterView />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterView } from 'vue-router'
import AppSidebar from '@/components/base/AppSidebar.vue'
import AppTopBar from '@/components/base/AppTopBar.vue'

// 断点与侧栏规格一致（计划 Step 2 第 2 点）：< 1024px 侧栏转抽屉
const DESKTOP_QUERY = '(min-width: 1024px)'

const collapsed = ref(false)
const drawerVisible = ref(false)
const isDesktop = ref(typeof window === 'undefined' ? true : window.matchMedia(DESKTOP_QUERY).matches)

let mediaQuery = null

function syncViewport(event) {
  isDesktop.value = event.matches
  if (event.matches) drawerVisible.value = false
}

onMounted(() => {
  mediaQuery = window.matchMedia(DESKTOP_QUERY)
  isDesktop.value = mediaQuery.matches
  mediaQuery.addEventListener('change', syncViewport)
})

onBeforeUnmount(() => {
  if (mediaQuery) mediaQuery.removeEventListener('change', syncViewport)
})

// 命名沿用 toggle 语义（基线 MainLayout.vue:7 的 `toggleggleSidebar` 拼写缺陷不得复现）
function toggleCollapse() {
  collapsed.value = !collapsed.value
}

function handleToggleSidebar() {
  if (isDesktop.value) {
    toggleCollapse()
    return
  }
  drawerVisible.value = !drawerVisible.value
}
</script>

<style>
/* 抽屉内导航由 AppSidebar 自带 16px 内边距，去掉 el-drawer 默认 body padding */
.ch-nav-drawer .el-drawer__body {
  padding: 0;
  overflow: hidden;
}

/* 跳到主内容：默认移出视口，聚焦时落回左上角（无障碍硬要求） */
.ch-skip-link {
  position: absolute;
  left: -9999px;
  top: 0;
  z-index: 60;
  padding: var(--ch-space-sm) var(--ch-space-md);
  border-radius: var(--ch-radius-lg);
  background-color: var(--ch-bg-elevated);
  color: var(--ch-text-primary);
  font-size: var(--ch-font-size-body-s);
}

.ch-skip-link:focus {
  left: var(--ch-space-md);
  top: var(--ch-space-md);
}
</style>
