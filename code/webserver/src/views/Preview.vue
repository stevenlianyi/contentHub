<!-- ============================================================================
 * Preview · P-08 预览（Step 10 · 原地替换 Step 0 的 PLACEHOLDER）
 * ----------------------------------------------------------------------------
 * 职责：**只做编排与渲染分支**（取数、归一化、平台→形态映射在 `views/preview/usePreviewRender.js`）。
 *   ① 页头：返回 / 标题 / 平台切换（微信 / 小红书 / 通用）/ 关闭（Esc 同效）；
 *   ② 提示条：交互降级、版式复用 stack、图片未转存（+「去账号管理」）；
 *   ③ 画布：画布外取 `bg/base` 底层色（最暗），`.preview-scope` 子树强制浅色（唯一浅色区域）；
 *   ④ 底部信息栏：`规格 {w}×{h} · {n} 图 · {状态}` + `[上一版式] [下一版式]` + 当前版式名。
 *
 * 【本页是只读页（裁定 E）】**禁止调用 `topicmodify`**（不改 `status` / `layoutCode`）；
 *   平台 / 版式切换**只改 URL query**（`?platform=&layoutCode=`）并重新 `topicrender`。
 *
 * 【平台 → 预览形态（裁定 A 的落地，详见 usePreviewRender.PREVIEW_KIND_MAP）】
 *   · `wechat_mp` / `generic` → 传 `previewKind:'wechat'`，`content` 即**已含手机框**
 *     （`data-preview` + `data-phone-screen`）的片段 → 直接 `v-html` 注入 `.preview-scope`；
 *   · `xiaohongshu` → **不传 `previewKind`**（后端适配器忽略），改用 `products[].fileUrl`
 *     渲染图片集：`swipe_v1` → `SwipePreview`，其余 → `LongImagePreview`；
 *     ★ 禁止把小红书返回的 `content` 当手机框片段注入（它是未包裹的原始 HTML）。
 *   ★ 裁定 B：HTML 类平台的手机框由**后端片段自带**，前端只提供浅色容器 + 居中布局，
 *     故本页**不为 HTML 类平台套 `PreviewFrame`**（`PreviewFrame` 只用于 PNG 图集 / 长图）。
 *
 * 【异常态】E4 外链未转存 → `ErrorState` +「去账号管理」；E2 截图超时 → `ErrorState` + 重试；
 *   未选版式 → `EmptyState` +「去选版式并发起渲染」（裁定 G：**不调** `topicrender` 吃 C4）。
 *
 * 【无障碍（裁定 I）】平台切换按钮带 `aria-label`；序号点 `role="tablist"/"tab"` + `aria-selected`；
 *   `←`/`→` 仅在预览区聚焦时生效；`Esc` 返回上一页（与既有 AppDialog 行为一致）。
 * ★ 单文件 ≤ 600 行（§2.1）：平台切换 / 图集 / 长图 / 取数各自独立文件。
 * ========================================================================== -->
<template>
  <section class="flex min-h-full flex-col gap-lg">
    <!-- ① 页头（应用级暗色区域，位于 .preview-scope 之外） -->
    <header class="flex flex-wrap items-center gap-md">
      <AppButton size="sm" type="ghost" icon="fa fa-arrow-left" @click="goBack">返回</AppButton>
      <h1 class="min-w-0 flex-1 truncate text-h1 text-ch-text-primary" :title="headerTitle">
        预览 · {{ headerTitle }}
      </h1>
      <PlatformSwitcher
        v-if="!emptyState"
        :platform="platform"
        :platforms="platformOptions"
        :loading="loading"
        @change="switchPlatform"
      />
      <AppButton size="sm" icon-only icon="fa fa-times" :aria-label="'关闭预览并返回'" title="关闭（Esc）" @click="goBack" />
    </header>

    <!-- ② 提示条：降级 / 复用 / 未转存（应用级暗色区域） -->
    <ConflictBanner v-if="degradedHint" type="warning" :title="degradedHint" />
    <ConflictBanner v-if="reuseImplHint" type="info" :title="reuseImplHint" />
    <ConflictBanner
      v-if="transferWarning"
      type="warning"
      title="有图片未能转存到平台域名，发布后将无法显示"
      :actions="[{ key: 'accounts', label: '去账号管理' }]"
      @action="goAccounts"
    >
      <span>
        共 {{ transferWarning.count }} 张未转存（needUploadCount {{ transferWarning.need }} /
        transferredImageCount {{ transferWarning.transferred }}，字符串按 Number() 比较）。
      </span>
    </ConflictBanner>
    <p v-if="layoutsError" class="text-caption text-ch-warning">
      <i class="fa fa-triangle-exclamation" aria-hidden="true"></i>
      {{ layoutsError }}——版式名称与规格回落项不可用，可用版式按矩阵推导（附录 B R-24 / R-08）。
    </p>

    <!-- ③ 未选版式：短路为空态，不调 topicrender（裁定 G） -->
    <EmptyState
      v-if="emptyState"
      icon="fa fa-layer-group"
      title="该主题尚未渲染"
      description="该主题未选择版式（ch_topic.layoutCode 为空），无法生成预览。请先选择版式并发起渲染。"
      action-text="去选版式并发起渲染"
      @action="goLayout"
    />

    <!-- ④ 错误态 -->
    <template v-else-if="error">
      <ErrorState
        :message="error.message"
        :hint="error.hint"
        :detail="error.detail"
        @retry="load()"
      />
      <div v-if="error.code === 'E4'" class="flex justify-center">
        <AppButton size="sm" @click="goAccounts">去账号管理</AppButton>
      </div>
    </template>

    <!-- ⑤ 预览画布：画布外取 bg/base 底层色，浅色隔离域在 .preview-scope 内 -->
    <div
      v-else
      data-preview-canvas="1"
      class="flex min-h-[520px] justify-center rounded-xl bg-ch-base px-lg py-3xl"
    >
      <Skeleton v-if="!result" type="detail" :rows="6" label="预览渲染中" />

      <template v-else>
        <!-- preview-scope:begin —— 浅色隔离域：本区段内不得出现应用级暗色 Token 类 -->
        <div
          v-if="!isPng"
          data-preview-scope="1"
          class="preview-scope max-h-[860px] w-full max-w-[900px] overflow-auto rounded-xl"
          role="group"
          :aria-label="`${platformLabel}预览片段（手机框由后端片段自带）`"
        >
          <div v-html="result.content"></div>
        </div>

        <SwipePreview
          v-else-if="isSwipe"
          :products="products"
          :alt="headerTitle"
        />

        <LongImagePreview
          v-else
          :products="products"
          :meta="meta"
          :alt="headerTitle"
        />
        <!-- preview-scope:end -->
      </template>
    </div>

    <!-- ⑥ 底部信息栏：规格 · 图数 · 状态 + 版式循环切换 -->
    <footer
      v-if="layoutCode && !emptyState"
      class="flex flex-wrap items-center justify-between gap-md rounded-lg border border-ch-border bg-ch-surface px-lg py-md"
    >
      <div class="flex flex-wrap items-center gap-md">
        <AppButton
          size="sm"
          icon="fa fa-angle-left"
          :disabled="layoutOptions.length < 2"
          :disabled-reason="'当前平台仅 1 个可用版式'"
          @click="switchLayout(-1)"
        >
          上一版式
        </AppButton>
        <span class="text-body-s text-ch-text-primary">{{ layoutLabel }}</span>
        <AppButton
          size="sm"
          icon="fa fa-angle-right"
          :disabled="layoutOptions.length < 2"
          :disabled-reason="'当前平台仅 1 个可用版式'"
          @click="switchLayout(1)"
        >
          下一版式
        </AppButton>
      </div>

      <p data-preview-spec="1" class="flex flex-wrap items-center gap-sm text-body-s text-ch-text-secondary">
        <span>{{ specText }}</span>
        <span aria-hidden="true">·</span>
        <span
          class="inline-flex items-center gap-xs"
          :style="{ color: statusMeta.color }"
          :aria-label="`渲染状态：${statusMeta.label}`"
        >
          <i :class="[statusMeta.icon, statusMeta.pulse ? 'animate-pulse-slow' : '']" aria-hidden="true"></i>
          <span>{{ statusMeta.label }}</span>
        </span>
        <span v-if="reused" class="inline-flex items-center gap-xs text-ch-info">
          <i class="fa fa-circle-info" aria-hidden="true"></i>
          已复用既有产物（内容未变）
        </span>
      </p>
    </footer>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppButton from '@/components/base/AppButton.vue'
import ConflictBanner from '@/components/base/ConflictBanner.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import Skeleton from '@/components/base/Skeleton.vue'
import LongImagePreview from '@/views/preview/LongImagePreview.vue'
import PlatformSwitcher from '@/views/preview/PlatformSwitcher.vue'
import SwipePreview from '@/views/preview/SwipePreview.vue'
import { JOB_STATUS_MAP, LAYOUT_TYPE_MAP, PLATFORM_MAP, isLayoutAllowed } from '@/config/chOptions'
import { toNum } from '@/views/topic/useRenderTrigger'
import {
  availableLayouts,
  availablePlatforms,
  defaultPlatform,
  normalizeError,
  str,
  usePreviewRender
} from '@/views/preview/usePreviewRender'

/**
 * 渲染结果三态（裁定 C）：`已就绪` / `渲染中` / `失败`。
 * ★ 图标与颜色取 §2.6 渲染状态机字典（`JOB_STATUS_MAP` 的 DONE / RUNNING / FAILED）→
 *   「形状图标 + 颜色 + 文字」三重编码不破（裁定 C6），仅按本页口径替换文字。
 */
const STATUS_META = {
  ready: { ...JOB_STATUS_MAP.DONE, label: '已就绪' },
  rendering: { ...JOB_STATUS_MAP.RUNNING, label: '渲染中' },
  failed: { ...JOB_STATUS_MAP.FAILED, label: '失败' }
}

const route = useRoute()
const router = useRouter()

const {
  topic,
  layouts,
  layoutsError,
  loading,
  error,
  result,
  lastPayload,
  loadTopic,
  ensureLayouts,
  renderPreview,
  resetResult
} = usePreviewRender()

/* ---------------- 路由入参 ---------------- */
const code = computed(() => str(route.params.code))
const queryPlatform = computed(() => str(route.query.platform))
const queryLayoutCode = computed(() => str(route.query.layoutCode))

/** specOverride 从 URL query 透传（JSON 字符串）；解析失败只 console.error 并忽略，不阻断预览 */
const specOverride = computed(() => {
  const raw = str(route.query.specOverride)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null
    return parsed
  } catch (e) {
    console.error('[P-08] specOverride 解析失败，已忽略（不透传）', e)
    return null
  }
})

/* ---------------- 派生：版式 / 平台 / 输出形态 ---------------- */
/** 生效版式：URL query > `topicqry` 返回的 `ch_topic.layoutCode`（本页只读，不写回，裁定 E） */
const layoutCode = computed(() => queryLayoutCode.value || str(topic.value?.layoutCode))

/** 当前平台可用版式（矩阵 ∪ ch_layout，R-08）；`[上一版式]/[下一版式]` 在集合内循环 */
const layoutOptions = computed(() => availableLayouts(platform.value, layouts.value))

/** 生效平台：URL query（须与版式匹配）> `ch_layout.platform` > 矩阵首个允许平台（裁定 B） */
const platform = computed(() => {
  if (queryPlatform.value && isLayoutAllowed(layoutCode.value, queryPlatform.value)) return queryPlatform.value
  return defaultPlatform(layoutCode.value, layouts.value)
})

/** 平台切换入口：**不可用组合不提供入口**（如「小红书 + carousel_v1」不出现） */
const platformOptions = computed(() => availablePlatforms(layoutCode.value))

const platformLabel = computed(() => PLATFORM_MAP[platform.value]?.label || platform.value || '预览')
const currentLayout = computed(() => layoutOptions.value.find((item) => item.layoutCode === layoutCode.value) || null)
const layoutLabel = computed(() => {
  const codeText = layoutCode.value
  if (!codeText) return ''
  const type = currentLayout.value?.layoutType || str(result.value?.metrics?.layoutType)
  const typeText = LAYOUT_TYPE_MAP[type] || type || '未登记类型'
  const name = currentLayout.value?.layoutName || ''
  return name && name !== typeText ? `${codeText}（${name} · ${typeText}）` : `${codeText}（${typeText}）`
})

const meta = computed(() => result.value?.meta || {})
const products = computed(() => result.value?.products || [])
const reused = computed(() => str(result.value?.reused) === '1')

/** 输出形态：PNG 类（小红书）走图集 / 长图；HTML 类走后端自带手机框的片段 */
const isPng = computed(() => str(result.value?.metrics?.outputKind) === 'png')
/** 滑动多图集判据：请求的版式 / 后端 layoutType / 适配器 artifactKind 三取一 */
const isSwipe = computed(
  () =>
    str(result.value?.request?.layoutCode) === 'swipe_v1' ||
    str(result.value?.metrics?.layoutType) === 'swipe' ||
    str(result.value?.metrics?.artifactKind) === 'png_cards'
)

const headerTitle = computed(() => str(topic.value?.title) || '（无标题）')
const emptyState = computed(() => !loading.value && !error.value && !layoutCode.value)

/* ---------------- 信息栏：`规格 {w}×{h} · {n} 图 · {状态}`（裁定 C） ---------------- */
const sizeText = computed(() => {
  if (!result.value) return ''
  if (isPng.value) {
    // PNG 平台：取 products[0] 的宽高（字符串 → Number，R-26）
    const first = products.value[0]
    const width = toNum(first?.width)
    const height = toNum(first?.height)
    return width > 0 && height > 0 ? `${width}×${height}` : ''
  }
  // HTML 平台：优先 meta.spec.size / meta.size，缺失回落所选版式 specJson（size / maxWidth）
  const candidates = [str(meta.value?.spec?.size), str(meta.value?.size), str(currentLayout.value?.spec?.size), str(currentLayout.value?.spec?.maxWidth)]
  for (const candidate of candidates) {
    if (!candidate) continue
    const cleaned = candidate.replace(/px$/i, '').trim()
    if (/\d/.test(cleaned)) return cleaned.includes('x') ? cleaned.replace('x', '×') : cleaned
  }
  return ''
})

/** 图数：PNG 平台取 `products.length`；HTML 平台取 `meta.imageCount`（字符串 → Number） */
const imageCount = computed(() => (isPng.value ? products.value.length : toNum(meta.value?.imageCount)))

/** 两段拼装为 `规格 {w}×{h} · {n} 图`；两者都拿不到时按裁定 C 显示 `—`，**不编造** */
const specText = computed(() => {
  if (!result.value) return '规格 —'
  const segments = [sizeText.value ? `规格 ${sizeText.value}` : '规格 —']
  if (imageCount.value > 0) segments.push(`${imageCount.value} 图`)
  return segments.join(' · ')
})

const statusKey = computed(() => {
  if (error.value) return 'failed'
  if (loading.value || !result.value) return 'rendering'
  return 'ready'
})
const statusMeta = computed(() => STATUS_META[statusKey.value])

/* ---------------- 降级与转存提示（裁定 D；按字符串比较） ---------------- */
const degradedHint = computed(() =>
  str(meta.value?.interactionDegraded) === '1' ? '当前平台不支持交互脚本，已降级为静态图集' : ''
)
const reuseImplHint = computed(() =>
  str(meta.value?.degradedImpl) === 'stack_v1_reuse' ? '该版式在通用平台以 stack 实现复用' : ''
)
/** E4 的更精确判据：needUploadCount > transferredImageCount（两者均为字符串 → Number 比较） */
const transferWarning = computed(() => {
  if (error.value && error.value.code === 'E4') return null // E4 错误码本身走 ErrorState，不重复展示
  if (!result.value) return null
  const need = toNum(meta.value?.needUploadCount)
  const transferred = toNum(meta.value?.transferredImageCount ?? 0)
  if (need <= transferred) return null
  return { count: need - transferred, need, transferred }
})

/* ---------------- 取数编排 ---------------- */
async function load() {
  const key = code.value
  if (!key) return
  loading.value = true
  error.value = null
  try {
    const loadedCode = str(topic.value?.topicCode) || str(topic.value?.recID)
    if (!topic.value || (loadedCode !== key && str(topic.value?.recID) !== key)) {
      resetResult()
      const record = await loadTopic(key)
      if (!record) {
        error.value = normalizeError({ errCode: 'CB' })
        return
      }
    }
    await ensureLayouts()

    // ★ 裁定 G：未选版式 → 直接空态，不去调 topicrender（否则把可预期状态变成 C4 错误 toast）
    if (!layoutCode.value) {
      resetResult()
      return
    }

    const targetPlatform =
      queryPlatform.value && isLayoutAllowed(layoutCode.value, queryPlatform.value)
        ? queryPlatform.value
        : defaultPlatform(layoutCode.value, layouts.value)

    await renderPreview({
      topicID: str(topic.value?.recID),
      topicCode: str(topic.value?.topicCode) || key,
      layoutCode: layoutCode.value,
      platform: targetPlatform,
      specOverride: specOverride.value
    })
  } catch (e) {
    error.value = normalizeError(e)
    console.error('[P-08] 预览取数 / 渲染失败', e, { lastPayload: lastPayload.value })
  } finally {
    loading.value = false
  }
}

/** 只监听 URL 原始入参（不在 watcher 内做平台推导，避免「版式目录异步加载」触发二次渲染） */
watch([code, queryPlatform, queryLayoutCode, specOverride], load, { immediate: true })

/* ---------------- 交互（只改 URL query，重新 topicrender；不改任何落库字段，裁定 E） ---------------- */
function switchPlatform(next) {
  const target = str(next)
  // ★ 未选版式时不允许由平台切换「凭空」推出一个版式（裁定 G：该状态只给「去选版式并发起渲染」）
  if (!target || !layoutCode.value || target === platform.value) return
  // 平台切换后若当前版式在新平台不可用，则取该平台的第一个可用版式
  const options = availableLayouts(target, layouts.value)
  const keep = options.some((item) => item.layoutCode === layoutCode.value)
  const nextLayout = keep ? layoutCode.value : str(options[0]?.layoutCode)
  router.replace({ query: { ...route.query, platform: target, layoutCode: nextLayout } })
}

function switchLayout(step) {
  const options = layoutOptions.value
  if (options.length < 2) return
  const index = options.findIndex((item) => item.layoutCode === layoutCode.value)
  const next = options[(index + step + options.length) % options.length]
  if (!next) return
  router.replace({ query: { ...route.query, platform: platform.value, layoutCode: str(next.layoutCode) } })
}

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push({ name: 'Topics' })
}

function goLayout() {
  router.push({ name: 'TopicEdit', params: { code: code.value }, query: { tab: 'layout' } })
}

function goAccounts() {
  router.push({ name: 'Accounts' })
}

/** Esc 返回上一页（与既有 AppDialog 行为一致，裁定 I） */
function onKeydown(event) {
  if (event.key !== 'Escape') return
  event.preventDefault()
  goBack()
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>
