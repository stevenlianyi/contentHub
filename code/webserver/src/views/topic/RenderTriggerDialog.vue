<!-- ============================================================================
 * RenderTriggerDialog · P-03「发起渲染」弹窗（Step 9 · **全页唯一**，裁定 F）
 * ----------------------------------------------------------------------------
 * ★ 外壳右上角「提交渲染」（Step 7）与本 Tab「发起渲染」**必须打开同一个弹窗实例**，
 *   校验清单也来自同一处：`useRenderTrigger.buildRenderChecks()` 的 `checks` prop
 *   （由外壳统一计算并下传，避免出现两套阈值 / 两套实现）。
 * 内容：
 *   ① 前置校验清单（三重编码：图标 + 颜色 + 文字），与后端 `_checkRenderReadiness` 同口径；
 *   ② 渲染模式：默认 `job`（建任务后立即返回 jobCode + PENDING）；可选 `sync`（等待结果，快速预览）；
 *   ③ `specOverride` 临时覆盖 `specJson`（★ 只随本次请求下发，**不写回 ch_layout / ch_topic**，裁定 J）。
 * ★ 弹窗的「确认并渲染」用 primary：页级唯一 primary 仍是外壳的「提交渲染」，弹窗是独立模态面
 *   （与 AppDialog / 素材抽屉既有约定一致），本 Tab 内的页级按钮一律 secondary。
 * ★ 失败处理：C4/C6 由外壳做字段行内回显并**保持弹窗打开**；其余错误码走 http.js 统一 toast。
 * ★ 单文件 ≤ 600 行（§2.1 硬约束）：本文件只管展示与提交事件，校验判定与请求编排在
 *   `useRenderTrigger.js`（越界授权文件，裁定 F）。
 * ========================================================================== -->
<template>
  <AppDialog
    :model-value="modelValue"
    title="发起渲染"
    size="lg"
    @cancel="close"
  >
    <div class="flex flex-col gap-xl">
      <!-- 目标 1：版式 / 平台摘要 -->
      <div class="flex flex-wrap items-center gap-md rounded-lg border border-ch-border bg-ch-input px-lg py-md">
        <span class="text-body-s text-ch-text-secondary">本次渲染</span>
        <span class="font-mono text-code text-ch-text-primary">{{ layoutCode || '（未选择版式）' }}</span>
        <span v-if="layoutName" class="text-body-s text-ch-text-secondary">{{ layoutName }}</span>
        <PlatformChip v-if="platformCode" :platform="platformCode" size="sm" />
        <span class="text-caption text-ch-text-tertiary">附图 {{ assets.length }} 张</span>
      </div>

      <!-- 目标 2：前置校验清单 -->
      <section class="flex flex-col gap-sm" aria-labelledby="render-checks-title">
        <h3 id="render-checks-title" class="text-h3 text-ch-text-primary">
          前置校验
          <span class="text-body-s text-ch-text-secondary">（前端先拦，后端仍会再校验）</span>
        </h3>
        <ul class="flex flex-col gap-sm" role="list">
          <li
            v-for="item in checks"
            :key="item.key"
            class="flex items-start gap-sm text-body-s"
            :class="item.ok ? 'text-ch-text-secondary' : 'text-ch-danger'"
          >
            <i
              :class="item.ok ? 'fa fa-circle-check text-ch-success' : 'fa fa-circle-xmark text-ch-danger'"
              class="mt-[3px] shrink-0"
              aria-hidden="true"
            ></i>
            <span>
              <span class="text-ch-text-primary">{{ item.label }}</span>
              <span class="mx-xs">·</span>
              <span>{{ item.reason }}</span>
            </span>
          </li>
        </ul>
        <p v-if="catalogError" class="text-caption text-ch-warning">
          <i class="fa fa-triangle-exclamation" aria-hidden="true"></i>
          {{ catalogError }}（版式 / 平台配置未取到时，张数上限按 ch_layout 单侧判定）
        </p>
      </section>

      <!-- 目标 3：渲染模式 -->
      <fieldset class="flex flex-col gap-sm">
        <legend class="text-h3 text-ch-text-primary">渲染模式</legend>
        <label
          v-for="item in MODES"
          :key="item.value"
          class="flex cursor-pointer items-start gap-sm rounded-lg border px-lg py-md transition-colors duration-150 ease-out"
          :class="renderMode === item.value ? 'border-ch-primary bg-ch-primary-subtle' : 'border-ch-border bg-ch-input'"
        >
          <input
            v-model="renderMode"
            type="radio"
            name="render-mode"
            :value="item.value"
            class="mt-[3px]"
          />
          <span class="flex flex-col gap-xs">
            <span class="text-body text-ch-text-primary">{{ item.label }}</span>
            <span class="text-caption text-ch-text-tertiary">{{ item.hint }}</span>
          </span>
        </label>
      </fieldset>

      <!-- 目标 4：specOverride（临时覆盖，不写回） -->
      <section v-if="layoutCode" class="flex flex-col gap-sm" aria-labelledby="render-spec-title">
        <div class="flex flex-wrap items-center justify-between gap-sm">
          <h3 id="render-spec-title" class="text-h3 text-ch-text-primary">
            渲染参数临时覆盖
            <span class="font-mono text-code text-ch-text-secondary">specOverride</span>
          </h3>
          <AppButton size="sm" icon="fa fa-rotate-right" :disabled="specText === originalSpecText" :disabled-reason="'当前已是 ch_layout 原始参数'" @click="specText = originalSpecText">
            恢复默认
          </AppButton>
        </div>
        <textarea
          v-model="specText"
          rows="6"
          spellcheck="false"
          aria-label="渲染参数临时覆盖 JSON"
          class="w-full rounded-lg border bg-ch-input px-md py-sm font-mono text-code text-ch-text-primary focus:border-ch-border-focus"
          :class="specError ? 'border-ch-danger' : 'border-ch-border'"
        ></textarea>
        <p v-if="specError" class="flex items-center gap-xs text-caption text-ch-danger">
          <i class="fa fa-circle-xmark" aria-hidden="true"></i>
          <span>{{ specError }}</span>
        </p>
        <p v-else class="text-caption text-ch-text-tertiary">
          仅本次渲染生效（如 stack_v1 的 maxWidth / fontSize），**不写回** ch_layout，也不写回 ch_topic。
          与原始参数一致时不会下发 specOverride。
        </p>
      </section>
    </div>

    <template #footer>
      <AppButton size="md" :disabled="submitting" @click="close">取消</AppButton>
      <AppButton
        type="primary"
        size="md"
        icon="fa fa-paper-plane"
        :loading="submitting"
        :disabled="!ready"
        :disabled-reason="blockedReason || specError"
        @click="confirm"
      >
        确认并渲染
      </AppButton>
    </template>
  </AppDialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import AppButton from '@/components/base/AppButton.vue'
import AppDialog from '@/components/base/AppDialog.vue'
import PlatformChip from '@/components/biz/PlatformChip.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 已选版式编码（服务端 layoutCode） */
  layoutCode: { type: String, default: '' },
  layoutName: { type: String, default: '' },
  /** ch_layout.specJson 解析后的对象（作为覆盖基线） */
  layoutSpec: { type: Object, default: () => ({}) },
  /** 由 ch_layout.platform 推导的平台编码（裁定 B） */
  platformCode: { type: String, default: '' },
  assets: { type: Array, default: () => [] },
  /** useRenderTrigger.buildRenderChecks() 的输出（单一校验实现） */
  checks: { type: Array, default: () => [] },
  blockedReason: { type: String, default: '' },
  submitting: { type: Boolean, default: false },
  catalogError: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue', 'submit', 'cancel'])

const MODES = [
  {
    value: 'job',
    label: '异步任务（默认）',
    hint: '建任务后立即返回 jobCode + PENDING，进度在「渲染任务」页查看'
  },
  {
    value: 'sync',
    label: '同步渲染（等待结果）',
    hint: '等待渲染完成后直接跳转预览，耗时较长，适合快速确认排版'
  }
]

const renderMode = ref('job')
const specText = ref('')

const originalSpecText = computed(() => JSON.stringify(props.layoutSpec || {}, null, 2))

const specError = computed(() => {
  const text = specText.value.trim()
  if (!text) return ''
  try {
    const parsed = JSON.parse(text)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return 'specOverride 必须是一个 JSON 对象'
    return ''
  } catch (error) {
    return `JSON 解析失败：${error.message}`
  }
})

/** 有效覆盖：解析成功且与 ch_layout 原始参数不同 */
const overrideSpec = computed(() => {
  if (specError.value) return null
  const text = specText.value.trim()
  if (!text || text === originalSpecText.value) return null
  return JSON.parse(text)
})

const ready = computed(
  () => props.checks.length > 0 && props.checks.every((item) => item.ok) && !specError.value
)

/** 打开时重置：默认 job 模式；覆盖框回填该版式的原始 specJson（便于局部修改） */
watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    renderMode.value = 'job'
    specText.value = originalSpecText.value
  },
  { immediate: true }
)

function close() {
  emit('cancel')
  emit('update:modelValue', false)
}

function confirm() {
  if (!ready.value) return
  emit('submit', { renderMode: renderMode.value, specOverride: overrideSpec.value })
}
</script>
