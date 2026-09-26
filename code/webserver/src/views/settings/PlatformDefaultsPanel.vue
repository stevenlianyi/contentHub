<!-- ============================================================================
 * PlatformDefaultsPanel · P-13 设置页「平台默认参数」（Step 17）
 * ----------------------------------------------------------------------------
 * 【数据来源（唯一）】`platformqry`（`ch_platform` CRUD 的 qry，**免登录端点**）。
 *   取数口径（裁定 B）：`platformQry({}, { silent: true })` —— 不传任何业务参数；
 *   `silent: true` 由本组件自行渲染错误态 / 空响应态（§2.5 第 5 条），不叠加全局 toast。
 *
 * 【后端事实（服从，已核源码，不得凭计划文字臆断）】
 *   · 列（`database/ch_platform.txt`）= platformCode / platformName / subjectScope / deliverMode /
 *     titleMaxLen / summaryMaxLen / coverSpec / imageSpec / imageMaxCount / allowSvgFlag /
 *     needAiLabelFlag / autoPublishFlag / limitNote / docUrl / enabled / label / memo / …；
 *   · ★ 数值列经出参以**字符串**返回（`"titleMaxLen":"64"`、`"imageMaxCount":"20"`，附录 B R-26）
 *     → 展示前一律 `Number()` 归一；
 *   · ★ **R-24 空响应**：免登录端点「带参即静默返回 `{}`」（无 `errCode` / 无 `MSG`）。
 *     `utils/http.js` 的请求拦截器会统一注入 `lang` / `clientType`（登录态下还有 `sessionID`），
 *     故真实后端对本请求**极可能恒返回 `{}`** → 此时必须渲染 EmptyState + 说明，
 *     **不得**用本地 `PLATFORM_MAP` 兜底伪造任何规格数值，也不得白屏。
 *
 * 【只读】本组件**不含任何表单控件**（输入框 / 文本域 / 下拉 / 提交按钮），
 *   且不调用任何写端点：`platformmodify` / `platformadd` / `platformdel` 一律不调用（裁定 E）。
 * 【来源标注（裁定 B / E）】每个字段右侧配 12px `text/secondary` 的「来源：ch_platform 配置表」小字。
 * 【硬约束】单文件 ≤ 600 行（§2.1）。
 * ========================================================================== -->
<template>
  <section class="ch-card flex flex-col gap-lg">
    <header class="flex flex-col gap-xs">
      <h2 class="text-h2 text-ch-text-primary">平台默认参数</h2>
      <p class="text-body-s text-ch-text-secondary">
        逐平台展示 ch_platform 的 8 个规格字段（标题 / 简介字数上限、封面与正文图规格、图片数量上限、
        交付方式、AI 内容标识、正式发布）。数值列经出参以字符串返回，页面统一 Number() 归一后展示
        （附录 B R-26）；本区为只读展示，不提供编辑入口，也不调用 platformmodify。
      </p>
    </header>

    <!-- 三态之一：loading（骨架屏，形状对齐最终卡片） -->
    <Skeleton v-if="loading" type="card" :rows="3" />

    <!-- 三态之二：error（可重试；★ 不允许空白） -->
    <ErrorState
      v-else-if="errorText"
      :message="errorText"
      :detail="errorDetail"
      hint="平台默认参数读取失败：platformqry 为免登录端点，请检查网络与后端服务状态后重试。"
      @retry="load()"
    />

    <!-- 三态之三：empty（★ R-24：空响应 / 缺 data / data 非数组 → 一律走这里，绝不伪造规格数值） -->
    <EmptyState
      v-else-if="!platforms.length"
      icon="fa fa-gear"
      title="平台配置暂不可用"
      description="后端对该请求返回了空响应（附录 B R-24：免登录端点带参会被静默吞掉），请联系后端补齐 else 分支"
    />

    <template v-else>
      <article
        v-for="block in blocks"
        :key="block.code || block.name"
        class="flex flex-col gap-md rounded-xl border border-ch-border p-lg"
      >
        <header class="flex flex-wrap items-center gap-md">
          <PlatformChip :platform="block.code" />
          <span class="text-body text-ch-text-primary">{{ block.name }}</span>
          <span class="font-mono text-code text-ch-text-secondary">{{ block.code || '—' }}</span>
          <span
            v-if="block.disabled"
            class="inline-flex items-center gap-xs text-caption text-ch-warning"
            :aria-label="'平台状态：已停用'"
          >
            <i class="fa fa-triangle-exclamation" aria-hidden="true"></i>
            <span>已停用</span>
          </span>
        </header>

        <dl class="flex flex-col">
          <div
            v-for="row in block.rows"
            :key="row.key"
            class="flex flex-wrap items-center justify-between gap-x-lg gap-y-xs border-b border-ch-divider py-md last:border-b-0"
          >
            <dt class="w-[168px] shrink-0 text-body-s text-ch-text-secondary">{{ row.label }}</dt>
            <dd class="flex min-w-0 flex-1 flex-wrap items-center justify-between gap-x-md gap-y-xs">
              <a
                v-if="row.href"
                :href="row.href"
                target="_blank"
                rel="noopener"
                class="truncate font-mono text-code text-ch-primary hover:underline"
                :title="row.href"
              >
                {{ row.value }}
              </a>
              <span v-else class="text-body-s" :class="TONE_CLASS[row.tone] || TONE_CLASS.primary">
                {{ row.value }}
              </span>
              <span class="text-caption text-ch-text-secondary">来源：ch_platform 配置表</span>
            </dd>
          </div>
        </dl>
      </article>

      <p class="text-caption text-ch-text-secondary">
        来源：ch_platform 配置表（只读端点 platformqry，mode 缺省 full）。本区只读，无编辑控件。
      </p>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import EmptyState from '@/components/base/EmptyState.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import Skeleton from '@/components/base/Skeleton.vue'
import PlatformChip from '@/components/biz/PlatformChip.vue'
import { platformQry } from '@/api/platform'

/* ---------------------------------------------------------------------------
 * 文案字典与取值归一
 * ------------------------------------------------------------------------- */

/** `deliverMode` 中文映射（`database/ch_platform.txt:5`：draft_box / asset_pack / api_publish） */
const DELIVER_MODE_TEXT = {
  draft_box: '草稿箱',
  asset_pack: '素材包',
  api_publish: '正式发布'
}

/** 取值色调（仅表达「是否需要留意」，不复用 §2.6 状态机字典，避免占用状态语义） */
const TONE_CLASS = {
  primary: 'text-ch-text-primary',
  neutral: 'text-ch-text-secondary',
  warning: 'text-ch-warning'
}

/** 原始值 → 去空白字符串（null / undefined → ''） */
const rawText = (value) => (value === null || value === undefined ? '' : String(value).trim())

/** 字符串口径数值 → Number（★ R-26：后端以字符串返回）；空 / 非数值 → null（展示为 —） */
function toNumber(value) {
  const text = rawText(value)
  if (!text) return null
  const parsed = Number(text)
  return Number.isFinite(parsed) ? parsed : null
}

const textOrDash = (value) => rawText(value) || '—'

const maxText = (value, unit) => {
  const parsed = toNumber(value)
  return parsed === null ? '—' : `≤ ${parsed} ${unit}`
}

/** 仅接受 http / https（`docUrl` 为配置项，显式排除 javascript: 等协议，裁定 B） */
function safeUrl(value) {
  const text = rawText(value)
  return /^https?:\/\//i.test(text) ? text : ''
}

/**
 * 逐平台行配置（8 个裁定字段在前，4 个可补充字段在后）。
 * ★ 新增字段只需追加一行，无分支模板。
 */
function buildRows(item) {
  const deliverMode = rawText(item.deliverMode)
  const aiLabel = rawText(item.needAiLabelFlag)
  const autoPublish = rawText(item.autoPublishFlag)
  const enabled = rawText(item.enabled)
  const docUrl = safeUrl(item.docUrl)
  return [
    { key: 'titleMaxLen', label: '标题字数上限', value: maxText(item.titleMaxLen, '字'), tone: 'primary' },
    { key: 'summaryMaxLen', label: '简介字数上限', value: maxText(item.summaryMaxLen, '字'), tone: 'primary' },
    { key: 'coverSpec', label: '封面规格', value: textOrDash(item.coverSpec), tone: 'primary' },
    { key: 'imageSpec', label: '正文图规格', value: textOrDash(item.imageSpec), tone: 'primary' },
    { key: 'imageMaxCount', label: '图片数量上限', value: maxText(item.imageMaxCount, '张'), tone: 'primary' },
    {
      key: 'deliverMode',
      label: '交付方式',
      value: DELIVER_MODE_TEXT[deliverMode] || textOrDash(deliverMode),
      tone: 'primary'
    },
    {
      key: 'needAiLabelFlag',
      label: 'AI 内容标识',
      value: aiLabel === '1' ? '强制 AI 内容标识' : aiLabel === '0' ? '不强制' : '—',
      // 「强制」是合规要求（小红书为 1）→ 提示色；「不强制」为常态 → 中性，均不报警级红
      tone: aiLabel === '1' ? 'warning' : 'neutral'
    },
    {
      key: 'autoPublishFlag',
      label: '正式发布',
      // ★ 裁定 B：autoPublishFlag === '0'（或 0）→ 「正式发布已关闭」，中性呈现、不报警
      //   （取裁定给出的「绿 / 中性」中的**中性**分支：避免与 §2.6 StateBadge 的
      //    「成功 / 通过」语义混淆；关闭态本身不是「成功」）
      value: autoPublish === '0' ? '正式发布已关闭' : autoPublish === '1' ? '正式发布已开启' : '—',
      tone: autoPublish === '1' ? 'warning' : 'neutral'
    },
    { key: 'subjectScope', label: '支持主体范围', value: textOrDash(item.subjectScope), tone: 'neutral' },
    { key: 'limitNote', label: '限制与风控说明', value: textOrDash(item.limitNote), tone: 'neutral' },
    { key: 'docUrl', label: '官方文档', value: docUrl || '—', href: docUrl, tone: 'primary' },
    {
      key: 'enabled',
      label: '启用状态',
      value: enabled === '0' ? '已停用' : enabled === '1' ? '已启用' : '—',
      tone: enabled === '0' ? 'warning' : 'neutral'
    }
  ]
}

/* ---------------------------------------------------------------------------
 * 取数（三态齐备；R-24 空响应容错）
 * ------------------------------------------------------------------------- */

const platforms = ref([])
const loading = ref(false)
const errorText = ref('')
const errorDetail = ref('')

/**
 * 是否为「无 errCode 的信封对象」= R-24 的静默空响应 `{}`。
 * 区分依据：网络 / HTTP 层错误是 axios Error（含 `isAxiosError` / `response`），
 * 业务错误带 `errCode`；只有「带参被吞掉的空响应」是不含 `errCode` 的裸对象。
 */
function isEmptyEnvelope(payload) {
  return (
    Boolean(payload) &&
    typeof payload === 'object' &&
    !Object.prototype.hasOwnProperty.call(payload, 'errCode') &&
    !payload.isAxiosError &&
    !payload.response
  )
}

async function load() {
  loading.value = true
  errorText.value = ''
  errorDetail.value = ''
  try {
    const res = await platformQry({}, { silent: true })
    platforms.value = Array.isArray(res?.data) ? res.data : []
  } catch (error) {
    platforms.value = []
    if (isEmptyEnvelope(error)) {
      // ★ R-24：静默空响应 → 交给 EmptyState 说明，不伪造规格数值、不白屏
      console.warn('[P-13] platformqry 返回空响应（附录 B R-24：免登录端点带参被静默吞掉）')
      return
    }
    errorText.value = error?.MSG?.content || error?.message || '平台配置读取失败'
    errorDetail.value = [
      error?.errCode ? `errCode: ${error.errCode}` : '',
      error?.message || ''
    ]
      .filter(Boolean)
      .join('\n')
  } finally {
    loading.value = false
  }
}

/** 平台展示块（行配置一次算完，避免模板内重复求值） */
const blocks = computed(() =>
  platforms.value.map((item) => {
    const record = item && typeof item === 'object' ? item : {}
    return {
      code: rawText(record.platformCode),
      name: rawText(record.platformName) || '未命名平台',
      disabled: rawText(record.enabled) === '0',
      rows: buildRows(record)
    }
  })
)

onMounted(load)
</script>
