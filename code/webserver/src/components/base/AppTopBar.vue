<template>
  <header
    class="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-lg border-b border-ch-border bg-ch-sidebar px-lg"
  >
    <!-- 汉堡按钮：≥1024px 折叠/展开侧栏；<1024px 唤出抽屉 -->
    <button
      type="button"
      class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-ch-text-secondary transition-colors duration-150 ease-out hover:bg-ch-hover hover:text-ch-text-primary"
      :aria-label="toggleLabel"
      :aria-expanded="isDesktop ? !collapsed : drawerOpen"
      @click="emit('toggle-sidebar')"
    >
      <i class="fa fa-bars text-base" aria-hidden="true"></i>
    </button>

    <!-- 面包屑：14px / text-secondary，随路由更新 -->
    <nav class="flex min-w-0 items-center gap-sm text-body text-ch-text-secondary" aria-label="面包屑">
      <RouterLink to="/" class="shrink-0 rounded-sm transition-colors duration-150 ease-out hover:text-ch-text-primary">
        内容中枢
      </RouterLink>
      <template v-for="(crumb, index) in breadcrumbs" :key="crumb.key">
        <i class="fa fa-angle-right shrink-0 text-caption text-ch-text-tertiary" aria-hidden="true"></i>
        <span
          class="truncate"
          :class="index === breadcrumbs.length - 1 ? 'text-ch-text-primary' : ''"
          :aria-current="index === breadcrumbs.length - 1 ? 'page' : undefined"
        >
          {{ crumb.title }}
        </span>
      </template>
    </nav>

    <div class="ml-auto flex shrink-0 items-center gap-md">
      <!-- 搜索框：200×32，bg/input，圆角 6，focus 时 border/focus + shadow/focus，"/" 快捷键聚焦 -->
      <form
        role="search"
        class="flex h-8 w-[200px] items-center gap-xs rounded-md border border-ch-border bg-ch-input px-sm transition-colors duration-150 ease-out focus-within:border-ch-border-focus focus-within:shadow-focus"
        @submit.prevent="handleSearch"
      >
        <i class="fa fa-search text-caption text-ch-text-tertiary" aria-hidden="true"></i>
        <input
          ref="searchRef"
          v-model="keyword"
          type="text"
          class="w-full bg-transparent text-body-s text-ch-text-primary placeholder:text-ch-text-tertiary focus-visible:outline-none"
          placeholder="搜索标题 / 编码"
          aria-label="搜索主题（按 / 聚焦）"
        />
        <button type="submit" class="sr-only">搜索</button>
      </form>

      <!-- 通知（保留通知，裁定 C7） -->
      <el-popover placement="bottom-end" :width="260" trigger="click">
        <template #reference>
          <button
            type="button"
            class="flex h-8 w-8 items-center justify-center rounded-lg text-ch-text-secondary transition-colors duration-150 ease-out hover:bg-ch-hover hover:text-ch-text-primary"
            :aria-label="`通知（${NOTICE_COUNT} 条未读）`"
          >
            <el-badge :value="NOTICE_COUNT" :offset="[4, 4]">
              <i class="fa fa-bell text-base" aria-hidden="true"></i>
            </el-badge>
          </button>
        </template>
        <p class="text-body-s text-ch-text-secondary">
          通知明细由后续步骤接入（任务结果 / 投递状态 / 凭据到期提醒）。
        </p>
      </el-popover>

      <!-- 头像下拉：28px 圆，菜单 个人资料 / 退出登录 -->
      <el-dropdown trigger="click" @command="handleUserCommand">
        <button
          type="button"
          class="flex items-center gap-sm rounded-lg px-xs py-xs transition-colors duration-150 ease-out hover:bg-ch-hover"
          aria-label="用户菜单"
          aria-haspopup="menu"
        >
          <span
            class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ch-text-disabled text-caption font-medium text-ch-text-primary"
          >
            {{ avatarText }}
          </span>
          <span class="hidden max-w-[120px] truncate text-body-s text-ch-text-secondary md:inline">
            {{ userStore.realName || userStore.username }}
          </span>
          <i class="fa fa-angle-down text-caption text-ch-text-tertiary" aria-hidden="true"></i>
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">个人资料</el-dropdown-item>
            <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <!-- 个人资料（本步仅展示会话内已有信息，不调用接口） -->
    <AppDialog v-model="profileVisible" title="个人资料" size="sm">
      <dl class="flex flex-col gap-md text-body-s">
        <div class="flex gap-lg">
          <dt class="w-20 shrink-0 text-ch-text-tertiary">账号</dt>
          <dd class="text-ch-text-primary">{{ userStore.username || '—' }}</dd>
        </div>
        <div class="flex gap-lg">
          <dt class="w-20 shrink-0 text-ch-text-tertiary">姓名</dt>
          <dd class="text-ch-text-primary">{{ userStore.realName || '—' }}</dd>
        </div>
        <div class="flex gap-lg">
          <dt class="w-20 shrink-0 text-ch-text-tertiary">角色</dt>
          <dd class="text-ch-text-primary">{{ roleText }}</dd>
        </div>
        <div class="flex gap-lg">
          <dt class="w-20 shrink-0 text-ch-text-tertiary">权限项</dt>
          <dd class="font-mono text-ch-text-secondary">{{ permissionText }}</dd>
        </div>
      </dl>
      <template #footer>
        <button
          type="button"
          class="h-9 min-w-[112px] rounded-lg bg-ch-primary px-lg text-body font-medium text-ch-text-inverse transition-colors duration-150 ease-out hover:bg-ch-primary-hover"
          @click="profileVisible = false"
        >
          关闭
        </button>
      </template>
    </AppDialog>
  </header>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { toast } from 'vue3-toastify'
import AppDialog from '@/components/base/AppDialog.vue'
import { roleLabel, useUserStore } from '@/store/modules/user'

const props = defineProps({
  isDesktop: { type: Boolean, default: true },
  collapsed: { type: Boolean, default: false },
  drawerOpen: { type: Boolean, default: false }
})

const emit = defineEmits(['toggle-sidebar'])

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// 通知徽标为占位值：无通知接口（暂未在端点清单内），明细由后续步骤接入
const NOTICE_COUNT = 3

const keyword = ref('')
const searchRef = ref(null)
const profileVisible = ref(false)

const toggleLabel = computed(() => {
  if (props.isDesktop) return props.collapsed ? '展开侧栏' : '收起侧栏'
  return props.drawerOpen ? '关闭导航抽屉' : '打开导航抽屉'
})

/** 面包屑 = 当前匹配链上带 meta.title 的记录 + 动态段参数 */
const breadcrumbs = computed(() => {
  const crumbs = route.matched
    .filter((record) => record.meta?.title)
    .map((record) => ({ key: record.name || record.path, title: record.meta.title }))
  const dynamicValue = route.params?.code
  if (dynamicValue) crumbs.push({ key: 'param-code', title: String(dynamicValue) })
  return crumbs
})

const avatarText = computed(() => {
  const name = userStore.realName || userStore.username || '未'
  return Array.from(name)[0]
})

const roleText = computed(() => (userStore.roles.length ? userStore.roles.map(roleLabel).join('、') : '—'))

const permissionText = computed(() => {
  const list = userStore.permissions
  if (!list.length) return '—'
  return list.includes('*') ? '全量' : `${list.length} 项`
})

function handleSearch() {
  const value = keyword.value.trim()
  if (!value) return
  if (!router.hasRoute('Topics')) {
    toast.info('当前角色无主题库访问权限')
    return
  }
  router.push({ path: '/topics', query: { keyword: value } })
}

async function handleUserCommand(command) {
  if (command === 'profile') {
    profileVisible.value = true
    return
  }
  if (command === 'logout') await userStore.logout()
}

function isTypingTarget(element) {
  if (!element || !element.tagName) return false
  return ['INPUT', 'TEXTAREA', 'SELECT'].includes(element.tagName) || element.isContentEditable === true
}

/** `/` 聚焦搜索框（§2.11 快捷键） */
function handleShortcut(event) {
  if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) return
  if (isTypingTarget(event.target) || isTypingTarget(document.activeElement)) return
  event.preventDefault()
  searchRef.value?.focus()
}

onMounted(() => window.addEventListener('keydown', handleShortcut))
onBeforeUnmount(() => window.removeEventListener('keydown', handleShortcut))
</script>
