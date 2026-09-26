<!-- ============================================================================
 * IssueGroup · P-09 页私有组件（Step 13）
 * ----------------------------------------------------------------------------
 * 一个分组卡片，`level` 决定语义：
 *   · `ERROR`（阻断，红）/ `WARN`（警告，橙）：逐条渲染 `issues[]`（每条来自后端，不合并、不改写）；
 *   · `PASS`（通过，绿）：★ **不列具体检查项**，只列「本次未产出问题的检查类别」（裁定 B），
 *     未执行的类别标注「本次未执行」且**不得**算作通过。
 * 每条问题的呈现：
 *   · 普通问题 → `SpecChecker`（message / 位置 / 去修正）；
 *   · `source === 'sensitive_word'` → 外层 `SensitiveHighlight`（后端偏移高亮命中上下文）
 *     + 内部 `SpecChecker`（★ 传给 SpecChecker 的偏移/matchedWord 置空，避免同一段文本两处高亮）；
 *   · `source === 'rate_limit'` → 独立行 + 「查看限流说明」（裁定 C：限流项不跳转；
 *     SpecChecker 的按钮文案固定为「去修正」，无法表达该语义，故单独渲染）。
 * ★ 三重编码（§2.6 裁定 C6）：形状图标 + 颜色 + 文字，图标/颜色一律取 `chOptions` 字典。
 * ★ 单文件 ≤600 行（§2.1）。
 * ========================================================================== -->
<template>
  <section class="ch-card flex flex-col gap-lg">
    <header class="flex flex-wrap items-center gap-sm">
      <i :class="meta.icon" class="text-body" :style="{ color: meta.color }" aria-hidden="true"></i>
      <h2 class="text-h3" :style="{ color: meta.color }">{{ meta.label }}</h2>
      <span v-if="level !== 'PASS'" class="rounded-sm border border-ch-border px-xs text-caption text-ch-text-secondary">
        {{ issues.length }} 项
      </span>
    </header>

    <!-- ---------- 阻断 / 警告：逐条问题 ---------- -->
    <template v-if="level !== 'PASS'">
      <p v-if="!issues.length" class="text-body-s text-ch-text-tertiary">无{{ meta.label }}项</p>

      <ul v-else class="flex flex-col gap-lg" role="list">
        <li v-for="(issue, index) in issues" :key="issueKey(issue, index)" class="flex flex-col gap-sm">
          <!-- 限流：独立行（不跳转，仅说明） -->
          <article
            v-if="isRateLimit(issue)"
            class="flex items-start gap-md rounded-lg border border-ch-border bg-ch-surface px-lg py-md"
          >
            <i class="fa fa-clock mt-xs shrink-0 text-body text-ch-text-secondary" aria-hidden="true"></i>
            <div class="flex min-w-0 flex-1 flex-col gap-sm">
              <span class="text-body text-ch-text-primary">{{ issue.message }}</span>
              <p class="text-caption text-ch-text-secondary">位置：{{ issue.location || issue.field }}</p>
              <div>
                <AppButton size="sm" icon="fa fa-circle-info" @click="emit('rate-limit-note')">查看限流说明</AppButton>
              </div>
            </div>
          </article>

          <!-- 敏感词：SpecChecker + 后端偏移高亮上下文 -->
          <SensitiveHighlight
            v-else-if="isSensitive(issue)"
            :issue="issue"
            :text="textOf(issue)"
          >
            <SpecChecker :issue="plainIssue(issue)" context="" :show-locate="false" @fix="emit('fix', $event)" />
          </SensitiveHighlight>

          <!-- 其余问题 -->
          <SpecChecker v-else :issue="issue" context="" :show-locate="false" @fix="emit('fix', $event)" />

          <p v-if="impactNote(issue)" class="flex items-center gap-xs text-caption text-ch-warning">
            <i class="fa fa-triangle-exclamation" aria-hidden="true"></i>
            <span>{{ impactNote(issue) }}</span>
          </p>

          <p v-if="targetOf(issue).kind === 'fallback'" class="text-caption text-ch-text-tertiary">
            该字段未登记跳转位置，默认打开「内容」页签；位置：{{ issue.location || issue.field }}
          </p>

          <!-- 专项动作（裁定 H / I） -->
          <div v-if="isOverlong(issue) || isAiLabel(issue)" class="flex flex-wrap items-center gap-md">
            <AppButton
              v-if="isOverlong(issue)"
              size="sm"
              icon="fa fa-rotate-right"
              :loading="splitting"
              @click="emit('split', issue)"
            >
              重新渲染（渲染期自动切分）
            </AppButton>
            <template v-if="isAiLabel(issue)">
              <AppButton
                v-if="aiLabelFit.ok"
                size="sm"
                icon="fa fa-plus"
                :loading="applyingAiLabel"
                @click="emit('ai-label', issue)"
              >
                一键添加
              </AppButton>
              <span v-else class="text-caption text-ch-warning">{{ aiLabelFit.reason }}</span>
            </template>
          </div>
        </li>
      </ul>
    </template>

    <!-- ---------- 通过：只列「未产出问题的检查类别」+「本次未执行」 ---------- -->
    <template v-else>
      <p v-if="allClear" class="text-body-s text-ch-success">未发现问题</p>
      <p v-else class="text-body-s text-ch-text-secondary">
        以下检查类别本次未产出问题（通过/未执行均不代表「检查项总数」，后端未提供该项数据）。
      </p>

      <ul class="flex flex-col gap-sm" role="list">
        <li
          v-for="item in passedItems"
          :key="item.key"
          class="flex flex-wrap items-center gap-sm text-body-s text-ch-text-secondary"
        >
          <i class="fa fa-circle-check text-ch-success" aria-hidden="true"></i>
          <span>{{ item.label }}</span>
          <span class="text-caption text-ch-text-tertiary">未发现问题</span>
        </li>
        <li
          v-for="item in skippedItems"
          :key="item.key"
          class="flex flex-wrap items-center gap-sm text-body-s text-ch-text-tertiary"
        >
          <i class="fa-regular fa-circle" aria-hidden="true"></i>
          <span>{{ item.label }}</span>
          <span class="rounded-sm border border-ch-border px-xs text-caption">本次未执行</span>
          <span class="text-caption">{{ item.reason }}</span>
        </li>
      </ul>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import AppButton from '@/components/base/AppButton.vue'
import SpecChecker from '@/components/biz/SpecChecker.vue'
import SensitiveHighlight from '@/views/compliance/SensitiveHighlight.vue'
import { COMPLIANCE_LEVEL_MAP, SENSITIVE_LEVEL_MAP, resolveStatusMeta } from '@/config/chOptions'
import { issueImpactNote, normalizeField, resolveIssueTarget } from '@/views/compliance/useComplianceCheck'

const props = defineProps({
  /** `ERROR`（阻断）/ `WARN`（警告）/ `PASS`（通过） */
  level: { type: String, required: true },
  /** 该分组的问题清单（PASS 分组应传空数组，改用 `statuses`） */
  issues: { type: Array, default: () => [] },
  /** PASS 分组的类别状态：`[{ key, label, state: 'issue'|'pass'|'skipped', reason }]` */
  statuses: { type: Array, default: () => [] },
  /** 命中上下文原文：`{ title, summary, description, author }`（按 normalizeField(issue.field) 取） */
  fieldTexts: { type: Object, default: () => ({}) },
  /** 「一键添加 AI 标识」的可用性：`{ ok, reason }`（裁定 I） */
  aiLabelFit: { type: Object, default: () => ({ ok: false, reason: '' }) },
  splitting: { type: Boolean, default: false },
  applyingAiLabel: { type: Boolean, default: false }
})

const emit = defineEmits(['fix', 'split', 'ai-label', 'rate-limit-note'])

/**
 * ★ 两级字典合并（与 SpecChecker 同口径）：分组键是后端原始口径 `ERROR` / `WARN`，
 *   而三分类字典 `COMPLIANCE_LEVEL_MAP` 的键是 `PASS` / `WARN` / `BLOCK`
 *   → 必须并入 `SENSITIVE_LEVEL_MAP`（`ERROR` → 阻断），否则标题会退化成 `ERROR` + 灰色兜底图标。
 */
const LEVEL_MAP = { ...COMPLIANCE_LEVEL_MAP, ...SENSITIVE_LEVEL_MAP }
const meta = computed(() => resolveStatusMeta(LEVEL_MAP, props.level))
const allClear = computed(() => !props.statuses.some((item) => item.state === 'issue'))
const passedItems = computed(() => props.statuses.filter((item) => item.state === 'pass'))
const skippedItems = computed(() => props.statuses.filter((item) => item.state === 'skipped'))

const isSensitive = (issue) => String(issue?.source || '') === 'sensitive_word'
const isRateLimit = (issue) => String(issue?.source || '') === 'rate_limit'
const isOverlong = (issue) => String(issue?.source || '') === 'overlong_image' || String(issue?.errCode || '') === 'E3'
const isAiLabel = (issue) => String(issue?.source || '') === 'ai_label'

/**
 * 按 normalizeField(issue.field) 取命中原文（`title` / `summary` / `description` / `author`）。
 * ★ 不做任何字段猜测：取不到就返回空串，由 SensitiveHighlight 走「只显示命中词」的兜底。
 */
function textOf(issue) {
  const key = normalizeField(issue?.field)
  const value = props.fieldTexts?.[key]
  return value === null || value === undefined ? '' : String(value)
}

/** 交给 SpecChecker 的副本：置空偏移与 matchedWord，避免与 SensitiveHighlight 重复高亮 */
const plainIssue = (issue) => ({ ...issue, offsetStart: undefined, offsetEnd: undefined, matchedWord: '' })

const impactNote = (issue) => issueImpactNote(issue)
const targetOf = (issue) => resolveIssueTarget(issue)
const issueKey = (issue, index) => `${issue?.level}-${issue?.source}-${issue?.field}-${issue?.location}-${index}`
</script>
