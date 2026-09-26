<template>
  <div class="flex min-h-screen items-center justify-center bg-ch-base p-2xl">
    <div
      class="grid w-full max-w-[960px] overflow-hidden rounded-2xl border border-ch-border bg-ch-surface shadow-modal lg:grid-cols-[1.05fr_1fr]"
    >
      <!-- 品牌区 -->
      <section class="hidden flex-col justify-between gap-3xl bg-ch-sidebar p-3xl lg:flex">
        <div class="flex items-center gap-sm">
          <span class="flex h-7 w-7 items-center justify-center rounded-lg bg-ch-primary text-ch-text-inverse">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden="true">
              <rect x="0" y="0" width="6" height="6" rx="1.5" />
              <rect x="8" y="0" width="6" height="6" rx="1.5" />
              <rect x="0" y="8" width="6" height="6" rx="1.5" />
              <rect x="8" y="8" width="6" height="6" rx="1.5" />
            </svg>
          </span>
          <span class="text-[15px] font-semibold text-ch-text-primary">内容中枢</span>
        </div>

        <div class="flex flex-col gap-md">
          <h2 class="text-h2 text-ch-text-primary">内容生产与投递中台</h2>
          <ul class="flex flex-col gap-sm text-body-s text-ch-text-secondary">
            <li v-for="feature in FEATURES" :key="feature" class="flex items-center gap-sm">
              <i class="fa fa-angle-right text-caption text-ch-primary" aria-hidden="true"></i>
              <span>{{ feature }}</span>
            </li>
          </ul>
        </div>

        <p class="text-caption text-ch-text-tertiary">内部系统 · 请使用分配给你的账号登录</p>
      </section>

      <!-- 表单区 -->
      <section class="p-3xl">
        <h1 class="text-h1 text-ch-text-primary">登录</h1>
        <p class="mt-xs text-body-s text-ch-text-secondary">请输入账号与口令</p>

        <form class="mt-2xl flex flex-col gap-xl" novalidate @submit.prevent="handleSubmit">
          <div class="flex flex-col gap-xs">
            <label for="loginID" class="text-body-s text-ch-text-secondary">账号</label>
            <input
              id="loginID"
              v-model.trim="form.loginID"
              type="text"
              autocomplete="username"
              class="h-9 rounded-md border border-ch-border bg-ch-input px-md text-body text-ch-text-primary placeholder:text-ch-text-tertiary focus:border-ch-border-focus"
              placeholder="登录账号"
            />
          </div>

          <div class="flex flex-col gap-xs">
            <label for="passwd" class="text-body-s text-ch-text-secondary">口令</label>
            <input
              id="passwd"
              v-model="form.passwd"
              type="password"
              autocomplete="current-password"
              class="h-9 rounded-md border border-ch-border bg-ch-input px-md text-body text-ch-text-primary placeholder:text-ch-text-tertiary focus:border-ch-border-focus"
              placeholder="登录口令"
            />
          </div>

          <!--
            开发态角色（裁定 B）：仅当 VITE_USE_MOCK === 'true' 时渲染，生产构建下不出现；
            且 devRole 字段仅在 Mock 模式下附加到登录请求（store 侧控制），真实模式不污染请求体。
          -->
          <div v-if="isMock" class="flex flex-col gap-xs">
            <label for="devRole" class="text-body-s text-ch-text-secondary">开发态角色</label>
            <select
              id="devRole"
              v-model="form.role"
              class="h-9 rounded-md border border-ch-border bg-ch-input px-md text-body text-ch-text-primary"
            >
              <option v-for="item in ROLE_OPTIONS" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
            <p class="text-caption text-ch-text-tertiary">
              仅 Mock 模式可见：账号填 <code class="font-mono">expired</code> 验证会话失效（B8）路径，
              填 <code class="font-mono">error</code> 验证失败态不清空输入。
            </p>
          </div>

          <!-- 错误态不清空输入（计划 Step 2 第 8 点） -->
          <p v-if="errorMessage" role="alert" class="rounded-lg border border-ch-danger px-md py-sm text-body-s text-ch-danger">
            {{ errorMessage }}
          </p>

          <button
            type="submit"
            class="h-9 min-w-[112px] rounded-lg bg-ch-primary px-lg text-body font-medium text-ch-text-inverse transition-colors duration-150 ease-out hover:bg-ch-primary-hover active:bg-ch-primary-active disabled:cursor-not-allowed disabled:bg-ch-text-disabled"
            :disabled="loading"
          >
            {{ loading ? '登录中…' : '登录' }}
          </button>
        </form>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toast } from 'vue3-toastify'
import { ROLE_OPTIONS, roleLabel, useUserStore } from '@/store/modules/user'

const FEATURES = ['主题与素材统一管理', '版式渲染与合规校验', '投递留痕与审计追溯']

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// 开发态角色下拉仅在 Mock 模式下渲染（裁定 B）；生产构建（VITE_USE_MOCK=false）下不出现
const isMock = import.meta.env.VITE_USE_MOCK === 'true'

function readRoleFromQuery() {
  const value = typeof route.query.role === 'string' ? route.query.role : ''
  return ROLE_OPTIONS.some((item) => item.value === value) ? value : ROLE_OPTIONS[0].value
}

const form = reactive({ loginID: '', passwd: '', role: readRoleFromQuery() })
const loading = ref(false)
const errorMessage = ref('')

/** ?redirect= 回跳（仅接受站内相对路径，避免开放重定向） */
const redirect = computed(() => {
  const value = route.query.redirect
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) return '/'
  return value
})

function greeting() {
  const hour = new Date().getHours()
  if (hour < 6) return '凌晨好'
  if (hour < 12) return '上午好'
  if (hour < 18) return '下午好'
  return '晚上好'
}

async function handleSubmit() {
  errorMessage.value = ''
  if (!form.loginID) {
    errorMessage.value = '请输入账号'
    return
  }
  if (!form.passwd) {
    errorMessage.value = '请输入口令'
    return
  }

  loading.value = true
  try {
    await userStore.login({ loginID: form.loginID, passwd: form.passwd, role: form.role })
    const who = userStore.realName || userStore.username
    const roles = userStore.roles.map(roleLabel).join('、')
    // 登录成功按当前时段 toast 欢迎
    toast.success(`${greeting()}，${who}（${roles}）`)
    await router.replace(redirect.value)
  } catch (error) {
    // 失败时保留用户已填内容，只提示原因。
    // 非 B0 的 errCode 由 http.js 统一 toast `MSG.content`；此处做行内提示（同文案）。
    errorMessage.value = error?.MSG?.content || error?.message || '登录失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>
