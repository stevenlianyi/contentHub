<!-- ============================================================================
 * PlatformMatrix · P-03 Tab3「平台能力矩阵」（Step 9）
 * ----------------------------------------------------------------------------
 * 规格：内联常显、不折叠；3 列（微信公众号 / 小红书 / 通用 HTML）。
 * ★ 行数据来源（裁定 D）：
 *   · 字段行 ← `ch_platform`（`platformqry`）：产物形态 / 交付方式 / 标题上限 / 简介上限 /
 *     封面规格 / 正文图规格 / 图片数量 / AI 标识 / SVG 交互 / 自动发布；
 *   · **固定行** ← 本文件（矩阵定义，非表字段）：图片比例、多图浏览方式、超长图处理。
 * ★ 「✕ 不支持」的三重编码：删除线图标 + `text/tertiary` + 文字「✕ 不支持」，
 *   并在**行尾给出一句原因**：优先取该平台的 `limitNote`，其次 `subjectScope`，
 *   都没有时才用本文件固定文案（裁定 D）。
 * ★ 所有数值字段后端以**字符串**返回（`"imageMaxCount":"20"`）→ 一律 `Number()` 后再展示（裁定 C）。
 * ★ 行配置数组驱动（裁定 K）：不为 3 列手写 3 套模板，新增能力项只加一行配置。
 * ★ 平台数据为空（附录 B R-24）时显示 EmptyState「配置数据暂不可用」，不白屏、不抛错。
 * ★ 单文件 ≤ 600 行（§2.1 硬约束）：行配置数组驱动，新增能力项只加一行 `ROWS` 配置。
 * ========================================================================== -->
<template>
  <section class="ch-card flex flex-col gap-lg">
    <header class="flex flex-col gap-xs">
      <h2 class="text-h3 text-ch-text-primary">目标平台能力矩阵</h2>
      <p class="text-body-s text-ch-text-secondary">
        内联常显、不折叠；「✕ 不支持」的行尾附平台给出的原因，数值与限制均取自配置表。
      </p>
    </header>

    <EmptyState
      v-if="!platforms.length"
      icon="fa fa-gear"
      title="配置数据暂不可用"
      description="platformqry 未返回可用平台配置（免登录端点带参数会返回空对象，见附录 B R-24）；请稍后重试或联系管理员。"
    />

    <template v-else>
      <div class="overflow-x-auto">
        <table class="w-full min-w-[760px] border-collapse text-body-s">
          <caption class="sr-only">各平台能力对比（来源 ch_platform 配置表）</caption>
          <thead>
            <tr>
              <th scope="col" class="w-[150px] border-b border-ch-border px-lg py-md text-left text-ch-text-secondary">
                能力项
              </th>
              <th
                v-for="item in platforms"
                :key="item.platformCode"
                scope="col"
                class="border-b border-ch-border px-lg py-md text-left"
              >
                <PlatformChip :platform="item.platformCode" size="md" />
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in ROWS" :key="row.key" class="border-b border-ch-divider">
              <th scope="row" class="px-lg py-md text-left font-normal text-ch-text-secondary">
                {{ row.label }}
              </th>
              <td v-for="item in platforms" :key="item.platformCode" class="px-lg py-md align-top">
                <span class="flex flex-col gap-xs">
                  <span
                    class="flex items-start gap-xs"
                    :class="cellOf(item, row).no ? 'text-ch-text-tertiary' : 'text-ch-text-primary'"
                  >
                    <i
                      v-if="cellOf(item, row).no"
                      class="fa fa-strikethrough mt-[3px] shrink-0 text-caption"
                      aria-hidden="true"
                    ></i>
                    <span>{{ cellOf(item, row).text }}</span>
                  </span>
                  <span
                    v-if="cellOf(item, row).reason"
                    class="text-caption text-ch-text-tertiary"
                  >
                    原因：{{ cellOf(item, row).reason }}
                  </span>
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <p class="text-caption text-ch-text-tertiary">来源：ch_platform 配置表，非硬编码</p>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import EmptyState from '@/components/base/EmptyState.vue'
import PlatformChip from '@/components/biz/PlatformChip.vue'

const props = defineProps({
  /** 归一化后的平台列表（platformqry，数值字段已 Number()） */
  platforms: { type: Array, default: () => [] },
  /** 归一化后的版式列表（用于按平台归纳「产物形态」的 outputKind 实登记值） */
  layouts: { type: Array, default: () => [] }
})

/* ---------------------------------------------------------------------------
 * 固定行取值（矩阵定义，非 ch_platform 字段；出处：计划 Step 9 要点 3）
 * ------------------------------------------------------------------------- */
const RATIO_RULE = {
  wechat_mp: '无强制（建议正文图 3:4）',
  xiaohongshu: '整篇单一比例（超长图按 1080×1440 切分）',
  generic: '不限制',
  default: '不限制'
}
const MULTI_BROWSE = {
  wechat_mp: '轮播（carousel_v1 以 SVG 自实现，需静态兜底图）',
  xiaohongshu: '左右滑动多图集（swipe_v1）',
  generic: '上下 / 轮播（视所选版式）',
  default: '视所选版式'
}
const LONG_IMAGE = {
  wechat_mp: '长图按切片高度 1440 分片，整篇同一比例',
  xiaohongshu: '超长图须按 1080×1440 切分，单张不超过 20MB',
  generic: '不限制（导出形态自选 html / markdown / json）',
  default: '不限制'
}

/** 产物形态 / 交付方式字典（对 `outputKind` / `deliverMode` 两个**数据字段**做文案映射） */
const OUTPUT_KIND_TEXT = { html: '内联样式 HTML', png: '图集 PNG', zip: '素材包 ZIP' }
const DELIVER_MODE_TEXT = {
  draft_box: '草稿箱投递',
  asset_pack: '素材包 ZIP 导出',
  api_publish: '第三方 API 发布'
}

/** 「✕ 不支持」的兜底原因（仅当 limitNote / subjectScope 都为空时使用，裁定 D） */
const FALLBACK_REASON = {
  autoPublishFlag: '本产品不提供自动发布入口，须人工在平台后台完成',
  allowSvgFlag: '该平台不允许 SVG 交互，渲染将输出静态兜底图'
}

const FIXED = {
  ratio: (item) => RATIO_RULE[item.platformCode] ?? RATIO_RULE.default,
  multiBrowse: (item) => MULTI_BROWSE[item.platformCode] ?? MULTI_BROWSE.default,
  longImage: (item) => LONG_IMAGE[item.platformCode] ?? LONG_IMAGE.default
}

const outputsOf = (platformCode) =>
  [...new Set(props.layouts.filter((item) => item.platform === platformCode).map((item) => item.outputKind).filter(Boolean))]

/** 产物形态：优先用该平台在 ch_layout 实际登记的 outputKind（数据驱动）；无登记时回退交付方式文案 */
function outputKindText(item) {
  const kinds = outputsOf(item.platformCode)
  if (kinds.length === 1) return OUTPUT_KIND_TEXT[kinds[0]] || String(kinds[0]).toUpperCase()
  if (kinds.length > 1) return kinds.map((key) => OUTPUT_KIND_TEXT[key] || key).join(' / ')
  return item.deliverMode === 'draft_box' ? '内联样式 HTML' : '素材包（形态视所选版式而定）'
}

/** 原因：limitNote → subjectScope → 固定文案（裁定 D） */
const reasonOf = (item, key) => item.limitNote || item.subjectScope || FALLBACK_REASON[key] || '该平台不支持此能力'

/** 是/否 类字段 → 「支持 / ✕ 不支持（原因）」 */
const flagCell = (item, key, yesText) =>
  item[key] === '1'
    ? { text: yesText, no: false, reason: '' }
    : { text: '✕ 不支持', no: true, reason: reasonOf(item, key) }

/** 数值/文本行 → 「≤ 20 张 / 1080x1440 / —」 */
const textCell = (text) => ({ text: text || '—', no: false, reason: '' })

/**
 * `needAiLabelFlag` 是「是否**强制**AI 标识」而非「是否支持」，故不走 ✕ 不支持 语义：
 * '1' → 必须标注；'0' → 不强制（不附「不支持」原因，避免与平台限制文案语义错配）。
 */
const aiLabelCell = (item) =>
  item.needAiLabelFlag === '1'
    ? { text: '必须标注（含 AI 生成内容）', no: false, reason: '' }
    : { text: '不强制标注', no: false, reason: '' }

/**
 * 行配置数组（裁定 K）：每行一个 `{ key, label, cell }`，新增能力项只追加一行。
 * 顺序与计划 Step 9 要点 3 的表格一致（产物形态 → 交付方式 → … → 自动发布）。
 */
const ROWS = [
  { key: 'outputKind', label: '产物形态', cell: (item) => textCell(outputKindText(item)) },
  { key: 'deliverMode', label: '交付方式', cell: (item) => textCell(DELIVER_MODE_TEXT[item.deliverMode] || item.deliverMode) },
  { key: 'titleMaxLen', label: '标题字数上限', cell: (item) => textCell(item.titleMaxLen ? `≤ ${item.titleMaxLen} 字` : '') },
  { key: 'summaryMaxLen', label: '简介字数上限', cell: (item) => textCell(item.summaryMaxLen ? `≤ ${item.summaryMaxLen} 字` : '') },
  { key: 'coverSpec', label: '封面规格', cell: (item) => textCell(item.coverSpec) },
  { key: 'imageSpec', label: '正文图规格', cell: (item) => textCell(item.imageSpec) },
  { key: 'imageMaxCount', label: '图片数量上限', cell: (item) => textCell(item.imageMaxCount ? `≤ ${item.imageMaxCount} 张` : '') },
  { key: 'ratio', label: '图片比例', cell: (item) => textCell(FIXED.ratio(item)) },
  { key: 'multiBrowse', label: '多图浏览方式', cell: (item) => textCell(FIXED.multiBrowse(item)) },
  { key: 'longImage', label: '超长图处理', cell: (item) => textCell(FIXED.longImage(item)) },
  { key: 'needAiLabelFlag', label: 'AI 内容标识', cell: (item) => aiLabelCell(item) },
  { key: 'allowSvgFlag', label: 'SVG 交互', cell: (item) => flagCell(item, 'allowSvgFlag', '允许') },
  { key: 'autoPublishFlag', label: '自动发布', cell: (item) => flagCell(item, 'autoPublishFlag', '允许') }
]

/** 预算矩阵：`{ [platformCode]: { [rowKey]: { text, no, reason } } }`，避免模板内重复求值 */
const matrix = computed(() =>
  Object.fromEntries(
    props.platforms.map((item) => [
      item.platformCode,
      Object.fromEntries(ROWS.map((row) => [row.key, row.cell(item)]))
    ])
  )
)

const cellOf = (item, row) => matrix.value[item.platformCode]?.[row.key] || { text: '—', no: false, reason: '' }
</script>
