<!-- ============================================================================
 * CompletionPanel · P-03 Tab1 右侧「完成度」辅助栏（Step 7）
 * ----------------------------------------------------------------------------
 * 5 项检查（计划 Step 7 要点 5）：标题 / 简介 / 详述（≤5000 字，**无下限**）/ 素材 ≥1 / 版式已选。
 * ★ 这是**完成度**，不是状态机（§2.6 末段）：一律用 `info` 色的 CompletionIndicator 表达，
 *   不使用 StateBadge，不占用 `ch_topic.status` 的任何语义，也不新增中间态。
 * 数据来源（验收第 9 项要求逐项列出）：
 *   · title        ← 草稿实时值（未保存也可反映在完成度上）
 *   · summary      ← 草稿实时值
 *   · wordCount    ← `descriptionFileID` 非空时取服务端 `topic.wordCount`（全文口径，转存场景），
 *                    否则取草稿正文的实时 `wordCount`（与后端 countWords 同口径，见 utils/common）
 *   · assetCount   ← Tab2 附图条数（`topicassetqry` 结果长度，非 `ch_topic.assetCount` 缓存）
 *   · layoutCode   ← 服务端 `topicqry` 返回的 `topic.layoutCode`（裁定 F：不以本地状态冒充「已选」）
 * 响应式由父级（TabContent）控制：≥1366px 右侧固定 280px；1024–1365px 下沉到内容底部；
 *   <1024px 折叠为可展开区（<details>）。
 * ========================================================================== -->
<template>
  <section
    class="ch-card flex flex-col gap-lg"
    :aria-labelledby="titleId"
  >
    <header class="flex items-center justify-between gap-md">
      <h2 :id="titleId" class="text-h3 text-ch-text-primary">完成度</h2>
      <span class="text-body-s text-ch-text-secondary tabular-nums" aria-live="polite">
        {{ doneCount }} / {{ checks.length }}
      </span>
    </header>

    <div class="flex items-center gap-xs" aria-hidden="true">
      <i
        v-for="(item, index) in checks"
        :key="`dot-${index}`"
        :class="item.done ? 'fa fa-circle' : 'fa-regular fa-circle'"
        class="text-caption"
        :style="{ color: item.done ? dotColor : undefined }"
      ></i>
    </div>

    <ul class="flex flex-col gap-md" role="list">
      <li v-for="item in checks" :key="item.key">
        <CompletionIndicator :done="item.done" :label="item.label" :hint="item.hint" />
      </li>
    </ul>

    <div v-if="pendingHints.length" class="flex flex-col gap-xs border-t border-ch-border pt-lg">
      <p class="text-caption text-ch-text-tertiary">── 提示 ──</p>
      <p v-for="(hint, index) in pendingHints" :key="`hint-${index}`" class="text-body-s text-ch-text-secondary">
        · {{ hint }}
      </p>
    </div>
  </section>
</template>

<script setup>
import { computed, useId } from 'vue'
import CompletionIndicator from '@/components/biz/CompletionIndicator.vue'
import { charCount } from '@/utils/common'
import { tokens } from '@/js/tokens'

const props = defineProps({
  /** 草稿标题（实时） */
  title: { type: String, default: '' },
  /** 草稿简介（实时） */
  summary: { type: String, default: '' },
  /** 详述字数（口径见文件头） */
  wordCount: { type: [Number, String], default: 0 },
  /** 附图条数（topicassetqry 结果长度） */
  assetCount: { type: [Number, String], default: 0 },
  /** 服务端已选版式（裁定 F：空即未选） */
  layoutCode: { type: String, default: '' },
  /** 详述转存文件 ID（非空表示详述已达标 · 全文在文件中） */
  descriptionFileId: { type: String, default: '' }
})

/** ★ 完成度统一 info 色（tokens.status.info），不复用状态徽章配色 */
const dotColor = tokens.status.info

/**
 * 标题 id 必须唯一：TabContent 在 <1024px（折叠区）与 ≥1024px（常显区）各渲染一个实例，
 * 硬编码 id 会造成同页重复 id（aria-labelledby 指向不确定）。故用 useId() 逐实例生成。
 */
const titleId = `completion-title-${useId()}`

/** 详述：无下限（2026-09-22 裁定，0 字合法），只有 ≤5000 的上限 */
const DETAIL_MAX = 5000

const checks = computed(() => {
  const title = props.title.trim()
  const summary = props.summary.trim()
  const words = Number(props.wordCount) || 0
  const assets = Number(props.assetCount) || 0
  const layout = props.layoutCode.trim()
  const detailOk = Boolean(props.descriptionFileId) || (words > 0 && words <= DETAIL_MAX)

  return [
    {
      key: 'title',
      label: '标题',
      done: Boolean(title) && charCount(title) <= 50,
      hint: title ? '' : '未填写'
    },
    {
      key: 'summary',
      label: '简介',
      done: Boolean(summary) && charCount(summary) <= 200,
      hint: summary ? '' : '未填写'
    },
    {
      key: 'description',
      label: '详述',
      done: detailOk,
      hint: detailOk ? '' : words > DETAIL_MAX ? `${words} 字，超出上限 ${DETAIL_MAX} 字` : '未填写（可留空）'
    },
    {
      key: 'assets',
      label: '素材',
      done: assets >= 1,
      hint: assets >= 1 ? `${assets} 张` : '至少 1 张附图'
    },
    {
      key: 'layout',
      label: '版式已选',
      done: Boolean(layout),
      hint: layout || '未选择版式（在「版式与平台」页选择）'
    }
  ]
})

const doneCount = computed(() => checks.value.filter((item) => item.done).length)

/** 未完成项的提示（把 hint 汇总到面板底部，避免逐项噪音） */
const pendingHints = computed(() =>
  checks.value.filter((item) => !item.done && item.hint).map((item) => `${item.label}：${item.hint}`)
)
</script>
