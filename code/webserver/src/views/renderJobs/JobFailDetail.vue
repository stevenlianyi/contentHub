<!-- ============================================================================
 * JobFailDetail · P-06 失败行展开面板（Step 11 · 产出文件）
 * ----------------------------------------------------------------------------
 * 触发方式：在 `RenderJobs.vue` 的 `el-table` 展开行内渲染（预置条件：`job.jobStatus === 'FAILED'`）。
 *
 * 内容（计划 Step 11 要点 3 + 裁定 I）：
 *   ① `errMsg` **全文**（`whitespace-pre-wrap` + `break-words`，纯文本插值，禁止 v-html）；
 *   ② 错误码语义：E1 渲染失败 / E2 截图超时 / E3 产物生成失败 / E4 外链图片未转存
 *      （取 `config/chOptions.ERR_CODE_TEXT`）+ 「用户已取消」；
 *      ★ `ch_render_job` **无 errorCode 列**（`database/ch_render_job.txt` 只有自由文本 `errMsg`）
 *        → 错误码由 `useJobPolling.resolveErrCode()` 按 `errorCode` 字段或 `errMsg` 文本推导；
 *          两者都不命中时**显式说明「后端未给出错误码」，不编造**。
 *   ③ 诊断字段：`inputHash` / `layoutCode` / `platform` / `startYMDHMS` / `finishYMDHMS`
 *      （时间经 `formatYMDHMS` 转 `YYYY-MM-DD HH:mm:ss`）；
 *   ④ 「重试」「重新渲染」两个入口（语义不同，文案不得混用，裁定 D）。
 *
 * 无障碍（裁定 I / §2.11）：
 *   · 面板容器 `role="status"` + `aria-live="polite"`（展开即播报失败原因）；
 *   · 触发按钮（位于 `RenderJobs.vue` 的操作列）带 `aria-expanded` + `aria-controls="<panelId>"`；
 *   · 焦点圈由 `styles/tailwind.css` 的 `*:focus-visible` 统一提供，本文件不得出现 `outline: none`。
 *
 * 颜色：只取 Token（Tailwind 语义类），无任何十六进制字面量（`npm run lint:hex`）。
 * ★ 面板按钮一律**不用 primary**：失败行可同时多条展开，避免与页面主操作争夺「每屏唯一 primary」。
 * ========================================================================== -->
<template>
  <div
    :id="panelId"
    class="flex flex-col gap-md rounded-lg border border-ch-border bg-ch-base/40 p-lg"
    role="status"
    aria-live="polite"
  >
    <div class="flex items-start gap-sm">
      <i
        class="mt-xs shrink-0"
        :class="[isCanceled ? 'fa fa-circle-info' : 'fa fa-circle-xmark', toneClass]"
        aria-hidden="true"
      ></i>
      <div class="flex min-w-0 flex-1 flex-col gap-xs">
        <p class="text-body-s font-medium text-ch-text-primary">失败原因</p>
        <p class="whitespace-pre-wrap break-words text-body-s text-ch-text-secondary">{{ message }}</p>
        <p class="flex flex-wrap items-center gap-xs text-caption" :class="toneClass">
          <template v-if="codeLabel">
            <span class="rounded-sm border border-current px-xs py-[1px] font-mono">{{ code }}</span>
            <span>{{ codeLabel }}</span>
          </template>
          <span v-else class="text-ch-text-tertiary">
            后端未给出错误码（ch_render_job 仅存 errMsg 文本）
          </span>
        </p>
      </div>
    </div>

    <dl class="grid grid-cols-1 gap-x-lg gap-y-xs text-caption md:grid-cols-2">
      <div v-for="item in diagnostics" :key="item.key" class="flex min-w-0 items-baseline gap-sm">
        <dt class="w-20 shrink-0 text-ch-text-tertiary">{{ item.label }}</dt>
        <dd class="min-w-0 break-all font-mono text-ch-text-secondary" :title="item.value">{{ item.value }}</dd>
      </div>
    </dl>

    <div class="flex flex-wrap items-center gap-md">
      <AppButton size="sm" icon="fa fa-rotate-right" @click="emit('retry')">重试</AppButton>
      <AppButton
        size="sm"
        icon="fa fa-rotate-right"
        :disabled="!hasLayout"
        :disabled-reason="hasLayout ? '' : '该任务未记录布局版式（layoutCode），无法发起重新渲染'"
        @click="emit('rerender')"
      >
        重新渲染
      </AppButton>
      <p class="text-caption text-ch-text-tertiary">
        <template v-if="hasLayout">重试＝沿用原输入重新入队（不产生新任务号）；重新渲染＝按当前版式新建任务。</template>
        <template v-else>该任务未记录 layoutCode，`topicrender` 必填该参数（缺 → C4）：请到主题编辑页选择版式后重新发起渲染。</template>
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import AppButton from '@/components/base/AppButton.vue'
import { PLATFORM_MAP } from '@/config/chOptions'
import { formatYMDHMS } from '@/utils/common'
import { CANCELED_ERR_MSG, errCodeLabel, layoutLabelOf, str } from '@/views/renderJobs/useJobPolling'

const props = defineProps({
  /** `renderjobqry` 单行记录（已经 `useJobPolling.normalizeJob()` 归一化） */
  job: { type: Object, required: true }
})

const emit = defineEmits(['retry', 'rerender'])

/** 与操作列触发按钮的 `aria-controls` 配对（`recID` 唯一） */
const panelId = computed(() => `job-fail-${str(props.job?.recID) || 'unknown'}`)
/** ★ `errMsg` 全文（不做截断；后端写入侧上限 500 字符） */
const message = computed(() => str(props.job?.errMsg) || '后端未返回 errMsg（原因未知）')
const code = computed(() => str(props.job?.errCode))
const codeLabel = computed(() => errCodeLabel(code.value))
/** 「用户已取消」不是系统失败：用中性色 + 信息图标，避免误读为渲染故障 */
const isCanceled = computed(() => code.value === CANCELED_ERR_MSG)
const toneClass = computed(() => (isCanceled ? 'text-ch-text-secondary' : 'text-ch-danger'))
/** `topicrender` 的 `layoutCode` 为必填（缺 → C4）→ 无版式时禁用「重新渲染」并给出原因 */
const hasLayout = computed(() => Boolean(str(props.job?.layoutCode)))

/** 诊断字段（裁定 I）：缺失一律显示 `—`，不伪造取值 */
const diagnostics = computed(() => {
  const job = props.job || {}
  return [
    { key: 'inputHash', label: 'inputHash', value: str(job.inputHash) || '—' },
    {
      key: 'layoutCode',
      label: '版式',
      value: str(job.layoutCode) ? `${job.layoutCode}${layoutLabelOf(job) ? `（${layoutLabelOf(job)}）` : ''}` : '—'
    },
    {
      key: 'platform',
      label: '平台',
      value: str(job.platform) ? `${PLATFORM_MAP[job.platform]?.label || job.platform}` : '—'
    },
    { key: 'startYMDHMS', label: '开始时间', value: formatYMDHMS(str(job.startYMDHMS)) || '—' },
    { key: 'finishYMDHMS', label: '结束时间', value: formatYMDHMS(str(job.finishYMDHMS)) || '—' }
  ]
})
</script>
