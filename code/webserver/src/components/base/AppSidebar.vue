<script>
/**
 * 一级导航（顺序与文案冻结，计划 Step 2 第 1 点）：
 *   工作台 / 主题库 / 素材图库 / 渲染 / 合规校验 / 投递记录 / **第三方账号管理** / 系统
 * ★ `合规校验` 必须在 `投递记录` 之前（裁定 C1）；「系统」为 tertiary 层级。
 * ★ 角色清单与 router/index.js 的 meta.roles 保持一致（侧栏可见 ⇔ 路由可访问）。
 * ★ 2026-09-23「第三方账号管理」（第 8 项，置于「投递记录」之后、「系统」之前）：
 *   原「冻结 7 项」口径由本次需求改为 8 项（已登记 plan/前端开发计划.md）；
 *   非访客角色均可见 —— 归属隔离由**服务端**按登录 loginID 强制，菜单仅控制入口。
 */
export const NAV_ITEMS = [
  { id: 'dashboard', label: '工作台', route: '/', icon: 'fa-house', roles: ['administrator', 'manager', 'operator', 'customer', 'visitor'] },
  { id: 'topics', label: '主题库', route: '/topics', icon: 'fa-file-lines', roles: ['administrator', 'manager', 'operator', 'customer'] },
  { id: 'assets', label: '素材图库', route: '/assets', icon: 'fa-image', roles: ['administrator', 'manager', 'operator', 'customer'] },
  { id: 'render', label: '渲染', route: '/render-jobs', icon: 'fa-layer-group', roles: ['administrator', 'manager', 'operator'] },
  { id: 'compliance', label: '合规校验', route: '/compliance-hub', icon: 'fa-shield-halved', roles: ['administrator', 'manager', 'operator', 'customer'] },
  { id: 'publish', label: '投递记录', route: '/publish-records', icon: 'fa-box-archive', roles: ['administrator', 'manager', 'operator', 'customer'] },
  { id: 'myAccounts', label: '第三方账号管理', route: '/my-accounts', icon: 'fa-user-shield', roles: ['administrator', 'manager', 'operator', 'customer'] },
  { id: 'settings', label: '系统', route: '/settings', icon: 'fa-gear', roles: ['administrator', 'manager'], tertiary: true }
]
</script>

<script setup>
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useUserStore } from '@/store/modules/user'

const props = defineProps({
  // 展开 240 / 折叠 64（仅 desktop 生效）
  collapsed: { type: Boolean, default: false },
  mode: { type: String, default: 'desktop' } // desktop | drawer
})

const emit = defineEmits(['toggle-collapse', 'navigate'])

const route = useRoute()
const userStore = useUserStore()

/** 按当前角色裁剪导航项 */
const visibleItems = computed(() =>
  NAV_ITEMS.filter((item) => item.roles.some((role) => userStore.roles.includes(role)))
)

const isCollapsed = computed(() => props.mode === 'desktop' && props.collapsed)

function isActive(item) {
  if (item.route === '/') return route.path === '/'
  return route.path === item.route || route.path.startsWith(`${item.route}/`)
}

function itemClass(item) {
  const base = 'flex h-[var(--ch-nav-item-h)] items-center gap-sm rounded-lg px-sm text-body transition-colors duration-150 ease-out'
  if (isActive(item)) return `${base} bg-ch-primary-subtle font-medium text-ch-text-primary`
  if (item.tertiary) return `${base} text-ch-text-tertiary hover:bg-ch-hover hover:text-ch-text-secondary`
  return `${base} text-ch-text-secondary hover:bg-ch-hover hover:text-ch-text-primary`
}

const widthClass = computed(() => (isCollapsed.value ? 'w-[var(--ch-sidebar-collapsed-w)]' : 'w-[var(--ch-sidebar-w)]'))
</script>

<template>
  <aside
    class="flex h-full flex-col border-r border-ch-border bg-ch-sidebar p-lg transition-[width] duration-200 ease-out"
    :class="widthClass"
  >
    <!-- logo 行：高 44px，mark 28×28 圆角 8，文字 15/600 -->
    <RouterLink
      to="/"
      class="flex h-11 items-center gap-sm rounded-lg px-sm transition-colors duration-150 ease-out hover:bg-ch-hover"
      :class="isCollapsed ? 'justify-center' : ''"
      aria-label="内容中枢 · 工作台"
      @click="emit('navigate')"
    >
      <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-ch-primary text-ch-text-inverse">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden="true">
          <rect x="0" y="0" width="6" height="6" rx="1.5" />
          <rect x="8" y="0" width="6" height="6" rx="1.5" />
          <rect x="0" y="8" width="6" height="6" rx="1.5" />
          <rect x="8" y="8" width="6" height="6" rx="1.5" />
        </svg>
      </span>
      <span v-if="!isCollapsed" class="truncate text-[15px] font-semibold text-ch-text-primary">内容中枢</span>
    </RouterLink>

    <nav class="mt-md flex flex-1 flex-col gap-1.5 overflow-y-auto" aria-label="一级导航">
      <el-tooltip
        v-for="item in visibleItems"
        :key="item.id"
        :content="item.label"
        placement="right"
        :disabled="!isCollapsed"
        :show-after="200"
      >
        <RouterLink :to="item.route" class="ch-nav-item" :class="itemClass(item)" @click="emit('navigate')">
          <i
            class="fa w-4 shrink-0 text-center text-base"
            :class="[item.icon, isActive(item) ? 'text-ch-primary' : '']"
            aria-hidden="true"
          ></i>
          <span v-if="!isCollapsed" class="truncate">{{ item.label }}</span>
        </RouterLink>
      </el-tooltip>
    </nav>

    <button
      v-if="mode === 'desktop'"
      type="button"
      class="mt-md flex h-[var(--ch-nav-item-h)] items-center gap-sm rounded-lg px-sm text-body-s text-ch-text-tertiary transition-colors duration-150 ease-out hover:bg-ch-hover hover:text-ch-text-secondary"
      :class="isCollapsed ? 'justify-center' : ''"
      :aria-label="isCollapsed ? '展开侧栏' : '收起侧栏'"
      :aria-expanded="!isCollapsed"
      @click="emit('toggle-collapse')"
    >
      <i class="fa text-base" :class="isCollapsed ? 'fa-angle-double-right' : 'fa-angle-double-left'" aria-hidden="true"></i>
      <span v-if="!isCollapsed">收起侧栏</span>
    </button>
  </aside>
</template>
