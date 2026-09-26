<!-- ============================================================================
 * TabLayout · P-03 Tab3「版式与平台」（Step 9 · 替换 Step 7 的 EmptyState 占位）
 * ----------------------------------------------------------------------------
 * 编排三段（内联常显，无折叠）：
 *   ① 选择版式（LayoutPicker：平台过滤器 + 可用版式卡片，不可用组合**不进 DOM**）；
 *   ② 目标平台能力矩阵（PlatformMatrix：行取自 platformqry + 矩阵固定行）；
 *   ③ 选中 `swipe_v1` 时出现滑动顺序编排（复用 Step 4 的 AssetOrderStrip）。
 * 入口按钮：[渲染预览] 跳 P-08 `?platform=&layoutCode=`；[发起渲染] **打开外壳的同一个弹窗**
 *   （裁定 F：页级唯一 primary 仍是外壳的「提交渲染」，本 Tab 内一律 secondary）。
 *
 * ★ 裁定 G：本 Tab 的 AssetOrderStrip **复用 Tab2 已加载的附图状态**（`assets` prop 与外壳同一 ref），
 *   保存也只 emit 给外壳的**同一个** `onReorder`（`topicassetmodify` 的 `orderList`，
 *   同时带 `topicID` + `recID`），不各存副本，避免顺序漂移。
 *
 * ★ 裁定 C / R-08：平台可用性**以矩阵为准**（`isLayoutAllowed`）；当 `ch_layout.platform` 与矩阵漂移时
 *   `console.error` 记录（同一组合只报一次），便于发现种子/规则漂移。
 * ★ 单文件 ≤ 600 行（§2.1 硬约束）：本文件只做编排与入口，版式网格 / 能力矩阵 / 渲染弹窗分别在
 *   LayoutPicker.vue / PlatformMatrix.vue / RenderTriggerDialog.vue（校验与编排在 useRenderTrigger.js）。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-2xl">
    <header class="flex flex-wrap items-center justify-between gap-md">
      <div>
        <h2 class="text-h3 text-ch-text-primary">版式与平台</h2>
        <p class="text-body-s text-ch-text-secondary">
          版式决定渲染模板与产物形态；平台决定可用版式与规格上限（矩阵为准）。
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-md">
        <AppButton
          icon="fa fa-eye"
          :disabled="!layoutCode"
          :disabled-reason="'请先选择版式'"
          @click="goPreview"
        >
          渲染预览
        </AppButton>
        <AppButton
          icon="fa fa-paper-plane"
          :disabled="renderDisabled"
          :disabled-reason="renderBlockReason"
          @click="emit('open-render')"
        >
          发起渲染
        </AppButton>
      </div>
    </header>

    <LayoutPicker
      v-model:platform="filterPlatform"
      :layouts="layouts"
      :platforms="platforms"
      :model-value="layoutCode"
      :loading="catalogLoading"
      :saving="layoutSaving"
      :saved-at="layoutSavedAt"
      :error="catalogError"
      @select="emit('select-layout', $event)"
      @refresh="emit('refresh-catalog')"
    />

    <PlatformMatrix :platforms="platforms" :layouts="layouts" />

    <section v-if="isSwipe" class="ch-card flex flex-col gap-lg">
      <header class="flex flex-col gap-xs">
        <h2 class="text-h3 text-ch-text-primary">滑动顺序编排（swipe_v1）</h2>
        <p class="text-body-s text-ch-text-secondary">
          序号即 App 内左右滑动顺序，第 1 张为封面；拖动或使用「上移 / 下移」调整，
          保存写回 topicassetmodify 的 orderList（与「素材」页共用同一份数据）。
        </p>
      </header>

      <EmptyState
        v-if="!assets.length"
        icon="fa fa-image"
        title="还没有附图"
        description="swipe_v1 需要至少 1 张附图，请先到「素材」页添加。"
      />

      <template v-else>
        <AssetOrderStrip :items="stripItems" :sortable="true" @update:items="onStripUpdate" />
        <p class="text-caption text-ch-text-tertiary">
          共 {{ assets.length }} 张；上限 {{ swipeMax }} 张
          （min(ch_layout.specJson.maxCount {{ specMaxCount }}, ch_platform.imageMaxCount
          {{ platformMax || '暂不可用' }}））。
        </p>
      </template>
    </section>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import AppButton from '@/components/base/AppButton.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import AssetOrderStrip from '@/components/biz/AssetOrderStrip.vue'
import LayoutPicker from '@/views/topic/LayoutPicker.vue'
import PlatformMatrix from '@/views/topic/PlatformMatrix.vue'
import { PLATFORM_ORDER, isLayoutAllowed } from '@/config/chOptions'
import { detectMatrixDrift, ratioKeyOf, toNum } from '@/views/topic/useRenderTrigger'

const props = defineProps({
  /** 主题记录（含 recID / topicCode / layoutCode / status） */
  topic: { type: Object, default: null },
  /** 附图列表（与 Tab2 共享同一个响应式来源，裁定 G） */
  assets: { type: Array, default: () => [] },
  /** 归一化后的版式 / 平台目录 */
  layouts: { type: Array, default: () => [] },
  platforms: { type: Array, default: () => [] },
  catalogLoading: { type: Boolean, default: false },
  catalogError: { type: String, default: '' },
  /** 由外壳统一判定的渲染可用性（状态机 + 校验清单，同源） */
  renderDisabled: { type: Boolean, default: false },
  renderBlockReason: { type: String, default: '' },
  layoutSaving: { type: Boolean, default: false },
  layoutSavedAt: { type: String, default: '' }
})

const emit = defineEmits(['select-layout', 'reorder', 'open-render', 'refresh-catalog'])

const router = useRouter()

const layoutCode = computed(() => String(props.topic?.layoutCode ?? '').trim())
const selectedLayout = computed(() => props.layouts.find((item) => item.layoutCode === layoutCode.value) || null)
const platformCode = computed(() => selectedLayout.value?.platform || '')
const platform = computed(() => props.platforms.find((item) => item.platformCode === platformCode.value) || null)
const isSwipe = computed(() => layoutCode.value === 'swipe_v1')

/** 平台过滤器：默认取所选版式登记的 platform（裁定 B），用户可手动切换过滤其他平台 */
const userPickedPlatform = ref('')
const derivedPlatform = computed(() => {
  if (platformCode.value) return platformCode.value
  const firstAllowed = PLATFORM_ORDER.find((code) => isLayoutAllowed(layoutCode.value, code))
  return firstAllowed || PLATFORM_ORDER[0]
})
const filterPlatform = computed({
  get: () => userPickedPlatform.value || derivedPlatform.value,
  set: (value) => {
    userPickedPlatform.value = String(value || '')
  }
})

/** 矩阵漂移（R-08）：矩阵允许、ch_layout 未登记的「版式 × 平台」组合只报一次 */
const driftLogged = new Set()
watch(
  [() => props.layouts, filterPlatform],
  ([list, currentPlatform]) => {
    detectMatrixDrift(list, currentPlatform).forEach((item) => {
      const key = `${item.layoutCode}|${item.matrixPlatform}|${item.registeredPlatform}`
      if (driftLogged.has(key)) return
      driftLogged.add(key)
      console.error(
        '[P-05] 版式 × 平台矩阵漂移（以矩阵为准，附录 B R-08）',
        `矩阵允许 ${item.layoutCode} × ${item.matrixPlatform}，但 ch_layout 只登记 ${item.registeredPlatform}`
      )
    })
  },
  { immediate: true }
)

/* ---------------- swipe_v1 顺序编排（复用 Tab2 的附图状态与保存出口，裁定 G） ---------------- */
const specMaxCount = computed(() => toNum(selectedLayout.value?.spec?.maxCount, 18) || 18)
const platformMax = computed(() => toNum(platform.value?.imageMaxCount))
const swipeMax = computed(() => (platformMax.value > 0 ? Math.min(specMaxCount.value, platformMax.value) : specMaxCount.value))

/**
 * 顺序条数据：序号即 App 内滑动顺序，**第 1 张即封面**（AssetOrderStrip 对 index===0 标「封面」），
 * 故此处不再另传 isCover，避免与 index 口径产生两个「封面」标记。
 */
const stripItems = computed(() =>
  props.assets.map((item, index) => ({
    fileID: String(item.fileID ?? ''),
    url: item.imageUrl || '',
    thumbnailUrl: item.thumbnailUrl || '',
    seqNo: index + 1,
    ratio: ratioKeyOf(item)
  }))
)

/** 顺序变化 → 交回外壳的同一个 onReorder（orderList 落库），两处显示随之刷新 */
function onStripUpdate(next) {
  if (!Array.isArray(next) || !next.length) return
  const ids = new Set(next.map((item) => String(item.fileID)))
  const byFileId = new Map(props.assets.map((item) => [String(item.fileID), item]))
  const ordered = next.map((item) => byFileId.get(String(item.fileID))).filter(Boolean)
  props.assets.forEach((item) => {
    if (!ids.has(String(item.fileID))) ordered.push(item)
  })
  emit('reorder', ordered)
}

/** [渲染预览] → P-08 `/preview/:code?platform=&layoutCode=`（Step 10） */
function goPreview() {
  if (!layoutCode.value) return
  router.push({
    name: 'Preview',
    params: { code: String(props.topic?.topicCode || props.topic?.recID || '') },
    query: { platform: platformCode.value, layoutCode: layoutCode.value }
  })
}
</script>
