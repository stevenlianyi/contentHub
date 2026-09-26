<!-- ============================================================================
 * Compliance · P-09 合规校验（Step 13；路由 `/compliance/:code`，`code` = **topicCode**）
 * ----------------------------------------------------------------------------
 * 页面结构（自上而下）：
 *   ① 页头：主题标题 / topicCode / 主题状态徽章 / 后端 `checkedAt`；
 *   ② CheckToolbar：平台选择（保证 `platform` 非空，后端两者都空会直接 C7）+ 自定义敏感词 +
 *      「重新校验」+「标记通过」（仅无阻断项可用，否则禁用 + Tooltip）；
 *   ③ 汇总条（★ 裁定 A）：`阻断 N` / `警告 M` / 结论 chip —— **不出现「通过数」**；
 *   ④ 提示条：未选版式（去选版式）/ 限流降级（含本地计数）/ 已发起渲染任务（查看任务）；
 *   ⑤ 三段分组：阻断（红）→ 警告（橙）→ 通过（绿，只列未产出问题的类别，未执行另标注）。
 *
 * ★ 关键裁定（详见 plan/前端开发计划.md Step 13 与本次裁定 A~N）：
 *   A. 后端**不返回「检查项总数」** → 汇总条固定为「两数 + 结论」，禁止推算「通过 12」；
 *   B. 「通过」分组 = 本次未产出问题的检查类别（真实可数），未执行类别标注「本次未执行」；
 *   C. `issue.field` 一律 `normalizeField()` 后再映射 Tab（否则全部落兜底）；
 *   D. 「去修正」用 `AppButton` 跳 `/topics/:code?tab=…&focus=…`（禁止 `div + @click`）；
 *   E. 敏感词高亮只在 `SensitiveHighlight.vue` 内用后端偏移 `slice` 分段 + `<mark>`（禁 v-html）；
 *   F. 本页**不传 products**（C5 产物校验属 Step 14）；主题无 layoutCode 时按所选平台规格校验；
 *   G. 「重新校验」重跑 `publishcheck`（`silent: true`），失败用 `ErrorState`；
 *   J. 「标记通过」写 `sessionStorage`（供 Step 14 门禁），**不写 `topicmodify` 的 memo**；
 *   K. 限流降级用中性说明条（不得当红色配置错误处理）；
 *   L. 出参数值一律 `Number()`；`issues` 缺失按 `[]` 处理并 `console.error`（R-24）。
 * ★ 本页所有请求均带 `silent` 或为只读取数 → **不出现全局 toast 叠加**。
 * ★ 单文件 ≤600 行（§2.1）。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-lg">
    <header class="flex flex-wrap items-start justify-between gap-md">
      <div class="flex min-w-0 flex-col gap-xs">
        <h1 class="text-h1 text-ch-text-primary">合规校验</h1>
        <div class="flex flex-wrap items-center gap-sm">
          <span class="min-w-0 truncate text-body-s text-ch-text-secondary" :title="topicTitle">{{ topicTitle }}</span>
          <span v-if="topicCode" class="font-mono text-code text-ch-text-tertiary">{{ topicCode }}</span>
          <StateBadge v-if="topic" domain="topic" :status="topic.status" />
        </div>
        <p v-if="checkedAt" class="text-caption text-ch-text-tertiary">
          校验时间：{{ formatYMDHMS(checkedAt) }}（后端 checkedAt；重新校验会刷新）
        </p>
      </div>

      <RouterLink
        v-if="topicCode"
        :to="{ name: 'TopicEdit', params: { code: topicCode } }"
        class="text-body-s text-ch-primary hover:text-ch-primary-hover"
      >
        <i class="fa fa-pen mr-xs" aria-hidden="true"></i>前往主题编辑
      </RouterLink>
    </header>

    <ErrorState
      v-if="error"
      :message="error"
      :detail="errorDetail"
      hint="合规校验请求失败：请检查网络或稍后重试；若持续失败请核对主题是否存在。"
      @retry="load()"
    />

    <Skeleton v-else-if="loading" type="detail" :rows="6" label="合规校验加载中" />

    <template v-else-if="result">
      <CheckToolbar
        :platform="selectedPlatform"
        :options="platformOptions"
        :sensitive-words="sensitiveWordsText"
        :platform-summary="platformSummary"
        :loading="checking"
        :mark-disabled="markDisabled"
        :mark-reason="markReason"
        :dirty="dirty"
        @update:platform="updatePlatform"
        @update:sensitive-words="updateSensitiveWords"
        @check="check()"
        @mark-pass="onMarkPass"
      />

      <!-- 汇总条（★ 裁定 A：两数 + 结论，无「通过数」） -->
      <div
        class="flex flex-wrap items-center gap-xl rounded-xl border border-ch-border bg-ch-surface px-xl py-lg"
        aria-label="校验汇总"
      >
        <span class="flex items-center gap-sm text-body">
          <i :class="blockMeta.icon" :style="{ color: blockMeta.color }" aria-hidden="true"></i>
          <span :style="{ color: blockMeta.color }">阻断 {{ errorCount }}</span>
        </span>
        <span class="flex items-center gap-sm text-body">
          <i :class="warnMeta.icon" :style="{ color: warnMeta.color }" aria-hidden="true"></i>
          <span :style="{ color: warnMeta.color }">警告 {{ warningCount }}</span>
        </span>
        <span
          class="flex items-center gap-sm rounded-md border px-md py-xs text-body-s"
          :style="{ borderColor: conclusionMeta.color, color: conclusionMeta.color }"
          :title="CONCLUSION_HINT"
        >
          <i :class="conclusionMeta.icon" aria-hidden="true"></i>
          <span>{{ conclusionMeta.text }}</span>
        </span>
        <span v-if="!passed" class="text-body-s text-ch-danger">存在 {{ errorCount }} 项阻断，请先修正</span>
        <span v-else class="text-body-s text-ch-text-secondary">未发现阻断项（警告不阻断）</span>
      </div>

      <p class="flex flex-wrap items-center gap-md text-caption text-ch-text-tertiary">
        <span>平台：{{ result.platform || selectedPlatform || '—' }}</span>
        <span>版式：{{ result.layoutCode || '（未选择版式）' }}</span>
        <span>版式类型：{{ result.layoutType || '—' }}</span>
        <span>附图：{{ result.assetCount }} 张</span>
        <span>敏感词命中：{{ result.sensitiveHitCount }} 处</span>
      </p>

      <!-- 未选版式提示（裁定 F：不伪造 layoutCode） -->
      <div
        v-if="topic && !hasLayout"
        class="flex flex-wrap items-center gap-md rounded-xl border border-ch-border bg-ch-surface px-xl py-lg"
      >
        <i class="fa fa-triangle-exclamation text-ch-warning" aria-hidden="true"></i>
        <span class="text-body-s text-ch-text-secondary">该主题尚未选择版式，当前按所选平台规格校验</span>
        <RouterLink
          :to="{ name: 'TopicEdit', params: { code: topicCode }, query: { tab: 'layout' } }"
          class="text-body-s text-ch-primary hover:text-ch-primary-hover"
        >
          去选版式
        </RouterLink>
      </div>

      <!-- 限流降级（★ 裁定 K：中性说明，不做红色错误处理；「查看限流说明」锚点） -->
      <div
        v-if="showRateLimitNote"
        id="rate-limit-note"
        ref="rateLimitNoteRef"
        class="flex flex-wrap items-center gap-md rounded-xl border border-ch-border bg-ch-surface px-xl py-lg"
        aria-label="限流说明"
      >
        <i class="fa fa-triangle-exclamation text-ch-warning" aria-hidden="true"></i>
        <span class="text-body-s text-ch-text-secondary">（限流统计已降级为本地计数）</span>
        <span class="text-caption text-ch-text-tertiary">
          本地计数 {{ rateLimit.count }} / 上限 {{ rateLimit.limitCount }} 次 / 窗口 {{ rateLimit.windowSeconds }} 秒（backend={{ rateLimit.backend || '—' }}）
        </span>
      </div>

      <!-- 一键切分后：渲染任务入口（裁定 H） -->
      <div
        v-if="renderJobLink"
        class="flex flex-wrap items-center gap-md rounded-xl border border-ch-border bg-ch-surface px-xl py-lg"
      >
        <i class="fa fa-circle-notch text-ch-info" aria-hidden="true"></i>
        <span class="text-body-s text-ch-text-secondary">
          已发起渲染：渲染为异步任务，完成后请再次点击「重新校验」确认切分结果
        </span>
        <RouterLink :to="renderJobLink" class="text-body-s text-ch-primary hover:text-ch-primary-hover">查看任务</RouterLink>
      </div>

      <!-- 三段分组：阻断 → 警告 → 通过 -->
      <IssueGroup
        level="ERROR"
        :issues="errorIssues"
        :field-texts="fieldTexts"
        :ai-label-fit="aiLabelFit"
        :splitting="splitting"
        :applying-ai-label="applyingAiLabel"
        @fix="onFix"
        @split="onSplit"
        @ai-label="onAiLabel"
        @rate-limit-note="scrollToRateLimit"
      />
      <IssueGroup
        level="WARN"
        :issues="warnIssues"
        :field-texts="fieldTexts"
        :ai-label-fit="aiLabelFit"
        :splitting="splitting"
        :applying-ai-label="applyingAiLabel"
        @fix="onFix"
        @split="onSplit"
        @ai-label="onAiLabel"
        @rate-limit-note="scrollToRateLimit"
      />
      <IssueGroup level="PASS" :statuses="sourceStatuses" />
    </template>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { toast } from 'vue3-toastify'
import CheckToolbar from '@/views/compliance/CheckToolbar.vue'
import IssueGroup from '@/views/compliance/IssueGroup.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import Skeleton from '@/components/base/Skeleton.vue'
import StateBadge from '@/components/biz/StateBadge.vue'
import { COMPLIANCE_LEVEL_MAP } from '@/config/chOptions'
import { formatYMDHMS } from '@/utils/common'
import { resolveIssueTarget, useComplianceCheck } from '@/views/compliance/useComplianceCheck'

const router = useRouter()
const route = useRoute()
const rateLimitNoteRef = ref(null)

const {
  topic,
  result,
  errorIssues,
  warnIssues,
  errorCount,
  warningCount,
  passed,
  checkedAt,
  rateLimit,
  showRateLimitNote,
  sourceStatuses,
  fieldTexts,
  topicCode,
  topicTitle,
  hasLayout,
  dirty,
  aiLabelFit,
  platformOptions,
  platformRecord,
  selectedPlatform,
  sensitiveWordsText,
  loading,
  checking,
  error,
  errorDetail,
  renderJobLink,
  splitting,
  applyingAiLabel,
  load,
  check,
  updatePlatform,
  markPassed,
  appendAiLabel,
  startSplitRender
} = useComplianceCheck({ getTopicCode: () => String(route.params.code || '') })

/** 自定义敏感词输入（原始文本；仅在点「重新校验」时才随请求下发） */
function updateSensitiveWords(value) {
  sensitiveWordsText.value = String(value ?? '')
}

/* ---------------- 汇总条（★ 裁定 A：只有两个数字 + 结论） ---------------- */
const blockMeta = COMPLIANCE_LEVEL_MAP.BLOCK
const warnMeta = COMPLIANCE_LEVEL_MAP.WARN
const conclusionMeta = computed(() =>
  passed.value
    ? { ...COMPLIANCE_LEVEL_MAP.PASS, text: '通过校验' }
    : { ...COMPLIANCE_LEVEL_MAP.BLOCK, text: '未通过' }
)
const CONCLUSION_HINT = '后端未提供「检查项总数」，故不展示「通过数」（见页面说明与交付说明）'

/** 平台规格摘要：数值全部来自 `ch_platform`（前端不硬编码副本） */
const platformSummary = computed(() => {
  const record = platformRecord.value
  if (!record) return ''
  const parts = [
    `标题上限 ${record.titleMaxLen} 字`,
    `摘要上限 ${record.summaryMaxLen} 字`,
    `图片上限 ${record.imageMaxCount} 张`,
    `AI 标识${String(record.needAiLabelFlag) === '1' ? '强制' : '不强制'}`
  ]
  if (record.coverSpec) parts.push(`封面 ${record.coverSpec}`)
  if (record.imageSpec) parts.push(`正文图 ${record.imageSpec}`)
  return parts.join(' · ')
})

/* ---------------- 「标记通过」（裁定 J） ---------------- */
const markDisabled = computed(() => errorCount.value > 0 || checking.value)
const markReason = computed(() => {
  if (errorCount.value > 0) return `存在 ${errorCount.value} 项阻断，请先修正`
  if (checking.value) return '校验进行中，请稍候'
  return ''
})

function onMarkPass() {
  if (errorCount.value > 0) return
  if (!markPassed()) {
    toast.error('标记通过失败：本机存储不可用')
    return
  }
  toast.success('已标记通过（本机记录）')
}

/* ---------------- 「去修正」（裁定 C / D） ---------------- */
function onFix(issue) {
  const target = resolveIssueTarget(issue)
  if (target.kind === 'rate-limit') {
    scrollToRateLimit()
    return
  }
  const query = { tab: target.tab }
  if (target.kind === 'assets' && target.assetIndex >= 0) query.focus = `assetList[${target.assetIndex}]`
  else if (target.focus) query.focus = target.focus
  router.push({ name: 'TopicEdit', params: { code: topicCode.value }, query })
}

function scrollToRateLimit() {
  rateLimitNoteRef.value?.scrollIntoView?.({ block: 'center', behavior: 'smooth' })
}

/* ---------------- 「一键切分」/「一键添加」（裁定 H / I） ---------------- */
async function onSplit() {
  const { ok, jobCode, message } = await startSplitRender()
  if (!ok) {
    toast.error(message)
    return
  }
  toast.success(`已发起渲染${jobCode ? `（任务 ${jobCode}）` : ''}，渲染期将按 sliceHeight 自动切分`)
}

async function onAiLabel() {
  if (!aiLabelFit.value.ok) {
    toast.warning(aiLabelFit.value.reason)
    return
  }
  const { ok, message } = await appendAiLabel()
  if (!ok) {
    toast.error(message)
    return
  }
  toast.success('已在详述尾部追加标准 AI 标识，并已重新校验')
}
</script>
