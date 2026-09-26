<!-- ============================================================================
 * 组件自测页 · Step 4（裁定 D：本步对 §2.1 目录规范的唯一增补）
 * ----------------------------------------------------------------------------
 * 仅在 DEV 生效：router/index.js 用 `if (import.meta.env.DEV) router.addRoute(...)` 注册，
 * 生产构建中 `import.meta.env.DEV` 被静态替换为 false，动态 import 被消除 → dist 不含本页 chunk。
 * ★ 必须用「配置数组 + v-for」驱动（裁定 E），禁止为每个组件手写平铺用例；
 * ★ 本文件 ≤ 600 行（§2.1 硬约束）。
 * ★ 兜底用例（StateBadge 未定义状态）默认不渲染，避免污染「0 console error」的自测结论。
 * ========================================================================== -->
<template>
  <div class="min-h-screen bg-ch-base px-2xl py-xl text-ch-text-primary">
    <header class="mb-xl flex flex-col gap-sm">
      <h1 class="text-h1 text-ch-text-primary">组件自测 · Step 4</h1>
      <p class="text-body-s text-ch-text-secondary">
        共 {{ CASES.length }} 个用例 / 22 个组件；锚点格式 <code class="font-mono text-code">#case-&lt;key&gt;</code>。
      </p>
      <label class="flex items-center gap-sm text-body-s text-ch-text-secondary">
        <input v-model="showFallback" type="checkbox" class="h-4 w-4" />
        显示 StateBadge 兜底用例（会输出**预期内**的 console.error）
      </label>
    </header>

    <section
      v-for="item in visibleCases"
      :id="`case-${item.key}`"
      :key="item.key"
      class="mb-lg rounded-xl border border-ch-border bg-ch-surface p-xl"
    >
      <div class="mb-md flex flex-wrap items-center justify-between gap-md">
        <h2 class="text-h3 text-ch-text-primary">{{ item.name }}</h2>
        <code class="font-mono text-code text-ch-text-tertiary">#case-{{ item.key }}</code>
      </div>
      <p v-if="item.note" class="mb-md text-caption text-ch-text-tertiary">{{ item.note }}</p>

      <div class="flex flex-wrap items-start gap-md">
        <AppButton v-if="item.modal" type="primary" size="sm" @click="openModal(item)">
          打开 {{ item.name }}
        </AppButton>

        <component :is="REGISTRY[item.name]" v-bind="bindProps(item)" v-on="listeners(item)">
          <template v-if="item.slot">{{ item.slot }}</template>
        </component>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'

import AppButton from '@/components/base/AppButton.vue'
import FormInput from '@/components/base/FormInput.vue'
import AppTabs from '@/components/base/AppTabs.vue'
import AppTable from '@/components/base/AppTable.vue'
import AppDialog from '@/components/base/AppDialog.vue'
import AppPagination from '@/components/base/AppPagination.vue'
import Skeleton from '@/components/base/Skeleton.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import PermissionDenied from '@/components/base/PermissionDenied.vue'
import ConflictBanner from '@/components/base/ConflictBanner.vue'
import SourceTag from '@/components/base/SourceTag.vue'
import Badge from '@/components/base/Badge.vue'

import StateBadge from '@/components/biz/StateBadge.vue'
import PlatformChip from '@/components/biz/PlatformChip.vue'
import AssetThumb from '@/components/biz/AssetThumb.vue'
import LayoutCard from '@/components/biz/LayoutCard.vue'
import AssetOrderStrip from '@/components/biz/AssetOrderStrip.vue'
import WordCounter from '@/components/biz/WordCounter.vue'
import SpecChecker from '@/components/biz/SpecChecker.vue'
import PreviewFrame from '@/components/biz/PreviewFrame.vue'
import ConfirmPublish from '@/components/biz/ConfirmPublish.vue'

const REGISTRY = {
  AppButton, FormInput, AppTabs, AppTable, AppDialog, AppPagination, Skeleton,
  EmptyState, ErrorState, PermissionDenied, ConflictBanner, SourceTag, Badge,
  StateBadge, PlatformChip, AssetThumb, LayoutCard, AssetOrderStrip, WordCounter,
  SpecChecker, PreviewFrame, ConfirmPublish
}

/** placehold.co 占位图（与 mock 同口径；URL 内含色值文本但不带 `#`，不触发 lint:hex） */
const img = (seed, w = 320, h = 427) => `https://placehold.co/${w}x${h}/1F2937/F3F4F6?text=IMG+${seed}`
const thumbs = (seed) => ({ 320: img(seed), 640: img(seed, 640, 854), 1280: img(seed, 1280, 1707) })

const TABLE_COLUMNS = [
  { key: 'title', title: '主题标题', minWidth: 220 },
  { key: 'status', title: '状态', width: 120, render: (row) => row.statusLabel },
  { key: 'modifyYMDHMS', title: '更新时间', width: 160, align: 'right' }
]
const TABLE_ROWS = [
  { id: 'TOPIC-2026-0001', title: '敦煌壁画的色谱研究', statusLabel: '草稿', modifyYMDHMS: '2026-09-20 11:20:00' },
  { id: 'TOPIC-2026-0002', title: '宋代点茶考据与器皿形制', statusLabel: '已渲染', modifyYMDHMS: '2026-09-20 10:02:11' },
  { id: 'TOPIC-2026-0003', title: '明代家具榫卯结构图解', statusLabel: '已投递', modifyYMDHMS: '2026-09-19 18:44:30' }
]

const STRIP_ITEMS = () => [
  { fileID: 'FILE00001', url: img('001'), ratio: '3:4', seqNo: 1, isCover: '1' },
  { fileID: 'FILE00002', url: img('002'), ratio: '3:4', seqNo: 2, isCover: '0' },
  { fileID: 'FILE00003', url: img('003', 320, 178), ratio: '16:9', seqNo: 3, isCover: '0' },
  { fileID: 'FILE00004', url: img('004'), ratio: '3:4', seqNo: 4, isCover: '0' }
]

const CASES = [
  { key: 'AppButton', name: 'AppButton', props: { type: 'primary' }, slot: '主操作' },
  { key: 'AppButton-danger', name: 'AppButton', props: { type: 'danger-solid', disabled: true, disabledReason: '主题已归档，不能再次投递' }, slot: '删除' },
  { key: 'FormInput', name: 'FormInput', model: true, initial: '', props: { label: '主题标题', placeholder: '请输入标题', required: true, prefixIcon: 'fa fa-pen', help: '标题 ≤50 字', wordLimit: 50 } },
  { key: 'FormInput-error', name: 'FormInput', model: true, initial: '一个明显超过五十个字符上限的标题示例文本用于展示错误态样式', props: { label: '主题标题（错误态）', error: '标题超出 50 字上限', suffixIcon: 'fa fa-circle-xmark' } },
  { key: 'AppTabs', name: 'AppTabs', model: true, initial: 'content', props: { items: [{ key: 'content', label: '内容', badge: 2 }, { key: 'assets', label: '素材' }, { key: 'layout', label: '版式' }] } },
  { key: 'AppTable', name: 'AppTable', props: { columns: TABLE_COLUMNS, rows: TABLE_ROWS, rowKey: 'id', maxHeight: 220 } },
  { key: 'AppDialog', name: 'AppDialog', model: true, modal: true, initial: false, props: { title: '删除主题', danger: true }, slot: '删除后不可恢复（Esc 关闭并归还焦点）。' },
  { key: 'AppPagination', name: 'AppPagination', props: { total: 128, currentPage: 3, pageSize: 20 } },
  { key: 'Skeleton', name: 'Skeleton', props: { type: 'table', rows: 3 } },
  { key: 'EmptyState', name: 'EmptyState', props: { title: '暂无主题', description: '新建主题后即可在此处查看与投递。', actionText: '新建主题' } },
  { key: 'ErrorState', name: 'ErrorState', props: { message: '主题列表加载失败', detail: 'errCode: ERR_GENERAL\nMSG: 服务异常，请稍后重试' } },
  { key: 'PermissionDenied', name: 'PermissionDenied', props: {} },
  { key: 'ConflictBanner', name: 'ConflictBanner', props: { type: 'warning', title: '该图片已存在（contentHash 命中）', actions: [{ key: 'reuse', label: '复用已有素材' }, { key: 'keep', label: '仍然新增' }] }, slot: '系统检测到与『壁画色谱取样现场（自然光）』内容一致。' },
  { key: 'SourceTag', name: 'SourceTag', props: { source: 'mcp' } },
  { key: 'Badge', name: 'Badge', props: { count: 120, max: 99, variant: 'danger' } },
  { key: 'StateBadge-topic', name: 'StateBadge', note: '渲染中带脉冲（pulse-slow 2s）', props: { domain: 'topic', status: 'RENDERING' } },
  { key: 'StateBadge-health-OK', name: 'StateBadge', note: '灰度对照基准：success 形状', props: { domain: 'health', status: 'OK' } },
  { key: 'StateBadge-health-INVALID', name: 'StateBadge', note: '灰度对照基准：danger 形状', props: { domain: 'health', status: 'INVALID' } },
  { key: 'StateBadge-compliance', name: 'StateBadge', props: { domain: 'compliance', status: 'ERROR' } },
  { key: 'StateBadge-fallback-VALID', name: 'StateBadge', devOnly: true, note: 'VALID 不是 health 的合法键 → 应落兜底（灰色 + 空心 ○ + 原值）', props: { domain: 'health', status: 'VALID' } },
  { key: 'StateBadge-fallback-unknown', name: 'StateBadge', devOnly: true, note: '空状态值 → 兜底文案「未知」', props: { domain: 'health', status: '' } },
  { key: 'PlatformChip', name: 'PlatformChip', props: { platform: 'xiaohongshu' } },
  { key: 'AssetThumb', name: 'AssetThumb', props: { url: img('100', 1280, 1707), thumbnailUrl: img('100'), thumbnails: thumbs('100'), caption: '壁画色谱取样现场（自然光）', duplicated: true, sizes: '240px' } },
  { key: 'LayoutCard', name: 'LayoutCard', props: { layoutCode: 'swipe_v1', layoutName: '左右滑动多图集', layoutType: 'swipe', selected: true } },
  { key: 'LayoutCard-unavailable', name: 'LayoutCard', note: 'available=false → 组件根节点 v-if 不渲染（父级须先调用 isLayoutAllowed 过滤，组件内不做平台分支）', props: { layoutCode: 'carousel_v1', layoutName: '左右轮播', layoutType: 'carousel', available: false } },
  { key: 'AssetOrderStrip', name: 'AssetOrderStrip', model: true, modelKey: 'items', initial: STRIP_ITEMS, extraEvents: ['update:items'], props: { expectedRatio: '3:4' } },
  { key: 'WordCounter', name: 'WordCounter', props: { current: 2480, min: 2000, max: 2500 } },
  { key: 'SpecChecker', name: 'SpecChecker', props: { issue: { level: 'ERROR', message: '命中敏感词，禁止投递', location: '第 2 段', field: 'topicDesc', errCode: 'C5', offsetStart: 15, offsetEnd: 18, matchedWord: '最优秀' }, context: '本次研究以敦煌壁画的矿物颜料为对象，最优秀的取样方案已整理成册。' } },
  { key: 'PreviewFrame', name: 'PreviewFrame', model: true, initial: 0, modelKey: 'current', extraEvents: ['update:current'], props: { mode: 'phone', platform: 'wechat_mp', images: [{ id: 1 }, { id: 2 }, { id: 3 }], ratioMismatch: true, ratioHint: '微信正文图推荐 1080×1440（3:4）' }, slot: '预览内容：此处渲染真实 HTML 片段。' },
  { key: 'ConfirmPublish', name: 'ConfirmPublish', model: true, modal: true, modelKey: 'visible', initial: false, props: { topic: { title: '敦煌壁画的色谱研究' }, account: { accountName: '文博研究社（服务号）' }, layout: { layoutName: '上下展示' }, artifact: { artifactID: 'ART202609200001' }, quota: { used: 1, limit: 3 } } }
]

const state = reactive({})
const showFallback = ref(false)

CASES.forEach((item) => {
  if (!item.model) return
  state[item.key] = typeof item.initial === 'function' ? item.initial() : item.initial === undefined ? '' : item.initial
})

const visibleCases = computed(() => CASES.filter((item) => !item.devOnly || showFallback.value))

function bindProps(item) {
  if (!item.model) return item.props || {}
  return { ...(item.props || {}), [item.modelKey || 'modelValue']: state[item.key] }
}

function listeners(item) {
  const map = {}
  if (item.model) {
    map['update:modelValue'] = (value) => { state[item.key] = value }
    if (item.modal) {
      map.cancel = () => { state[item.key] = false }
      map.confirm = () => { state[item.key] = false }
    }
  }
  ;(item.extraEvents || []).forEach((name) => {
    map[name] = (value) => { state[item.key] = value }
  })
  return map
}

function openModal(item) {
  state[item.key] = true
}
</script>
