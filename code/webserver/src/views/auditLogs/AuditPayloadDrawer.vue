<!-- ============================================================================
 * AuditPayloadDrawer · P-12 审计明细抽屉（Step 16 产出文件）
 * ----------------------------------------------------------------------------
 * 入口：`AuditLogs.vue` 表格「入参摘要」列的 `payloadDigest`（点击打开右侧抽屉）。
 *
 * ★【为什么只展示 digest、不展示 payload（计划要点 5 的口径修正）】
 *   `ch_audit_log`（`database/ch_audit_log.txt`）**没有 `payload` 列**；
 *   `processor/auditService.py::sanitizePayload()` 的结果**只用于计算**
 *   `buildPayloadDigest()`（:182-190 / :216），**不落库** → 本页**无法**展示入参明细。
 *   故抽屉只展示 `payloadDigest`（64 位 sha256），并给出显式说明；
 *   ★ **禁止**任何拼接 / 反查 / 还原 payload 的尝试（摘要不可逆）。
 *
 * ★【凭据红线】`sanitizePayload` 会把 `secret/appSecret/credentialCipher/credentialIV/password/token`
 *   等命中 SENSITIVE_FIELD_TOKEN_LIST 的字段替换为 `***masked***`，且**根本不落库**；
 *   本组件只渲染真实列（不含任何凭据类字段），不做二次加工。
 *
 * 无障碍：`role="dialog"` + `aria-modal="true"` + `aria-labelledby`；Esc 关闭；Tab 焦点锁定；
 *   关闭后焦点归还触发行（复用 `ArtifactPreviewDrawer` / `AppDialog` 的既有范式）。
 * ========================================================================== -->
<template>
  <Teleport to="body">
    <div v-if="modelValue" class="fixed inset-0 z-50 flex justify-end bg-ch-base/80" @click.self="close">
      <aside
        ref="panelRef"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
        tabindex="-1"
        class="flex h-full w-full max-w-[640px] flex-col border-l border-ch-border bg-ch-elevated shadow-modal"
      >
        <header class="flex items-start justify-between gap-md border-b border-ch-border px-xl py-md">
          <div class="flex min-w-0 flex-col gap-xs">
            <h3 :id="titleId" class="text-h3 text-ch-text-primary">审计明细 · {{ record.action || '—' }}</h3>
            <p class="flex flex-wrap items-center gap-x-md gap-y-xs text-caption text-ch-text-tertiary">
              <span class="font-mono">recID {{ record.recID || '—' }}</span>
              <span class="font-mono">{{ record.regYMDHMS || '—' }}</span>
            </p>
          </div>
          <button
            type="button"
            class="shrink-0 rounded-md p-1 text-ch-text-secondary transition-colors duration-150 ease-out hover:bg-ch-hover hover:text-ch-text-primary"
            aria-label="关闭审计明细"
            @click="close"
          >
            <i class="fa fa-times" aria-hidden="true"></i>
          </button>
        </header>

        <div class="flex min-h-0 flex-1 flex-col gap-lg overflow-y-auto px-xl py-lg">
          <!-- FAIL 优先展示：结果 + errMsg（失败原因比对账本身更重要） -->
          <div
            v-if="isFail"
            class="flex flex-col gap-xs rounded-xl border border-ch-danger px-lg py-md"
            role="alert"
          >
            <p class="flex items-center gap-xs text-body-s" :style="{ color: tokens.status.danger }">
              <i class="fa fa-circle-xmark" aria-hidden="true"></i>
              <span>结果 FAIL</span>
            </p>
            <p class="break-words text-body-s text-ch-text-primary">{{ record.errMsg || '（后端未返回 errMsg）' }}</p>
          </div>

          <dl class="flex flex-col gap-md">
            <div v-for="item in rows" :key="item.label" class="flex flex-col gap-xs">
              <dt class="text-caption text-ch-text-tertiary">{{ item.label }}</dt>
              <!-- 来源：与表格同一组件口径（SourceTag）；空值显示「—」，不硬塞成 System -->
              <dd v-if="item.kind === 'source'" class="flex items-center gap-sm text-body-s text-ch-text-primary">
                <SourceTag v-if="hasSource" :source="str(record.source)" />
                <span v-else>—</span>
              </dd>
              <dd
                v-else
                :class="item.mono ? 'break-all font-mono text-code text-ch-text-primary' : 'text-body-s text-ch-text-primary'"
              >
                {{ item.value }}
              </dd>
            </div>
          </dl>

          <!-- payloadDigest：等宽 + 复制（★ 唯一可得的「入参」信息） -->
          <div class="flex flex-col gap-xs">
            <p class="text-caption text-ch-text-tertiary">payloadDigest（入参摘要 sha256）</p>
            <div class="flex flex-wrap items-center gap-sm">
              <span class="min-w-0 flex-1 break-all font-mono text-code text-ch-text-primary">
                {{ record.payloadDigest || '—' }}
              </span>
              <AppButton
                size="sm"
                icon="fa fa-copy"
                :disabled="!record.payloadDigest"
                disabled-reason="该审计记录未返回 payloadDigest（后端无入参时不计算摘要）"
                @click="copyDigest()"
              >
                复制
              </AppButton>
            </div>
          </div>

          <p class="rounded-xl border border-ch-border bg-ch-input px-lg py-md text-caption text-ch-text-secondary">
            <i class="fa fa-circle-info mr-xs" aria-hidden="true"></i>
            <b>入参明细不落库</b>：审计表只保存入参脱敏后的 sha256 摘要，无法从此页还原请求内容
            （`ch_audit_log` 无 payload 列；`sanitizePayload()` 的结果仅用于计算摘要、不写入数据库）。
            凭据类字段（`appSecret` / `credentialCipher` / `password` / `token` 等）在摘要计算前即被替换为
            `***masked***`，也不会落库。
          </p>
        </div>

        <footer class="flex items-center justify-end gap-sm border-t border-ch-border px-xl py-md">
          <AppButton size="md" @click="close">关闭</AppButton>
        </footer>
      </aside>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'
import AppButton from '@/components/base/AppButton.vue'
import SourceTag from '@/components/base/SourceTag.vue'
import { tokens } from '@/js/tokens'
import { copyText, formatYMDHMS } from '@/utils/common'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 当前审计记录（`auditlogqry` 的单条 aSet 原样传入，不做字段改名） */
  record: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['update:modelValue'])

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

const panelRef = ref(null)
const titleId = `ch-audit-drawer-${useId()}`
let lastActiveElement = null

const str = (value) => (value === null || value === undefined ? '' : String(value))
const dash = (value) => str(value) || '—'

const isFail = computed(() => str(props.record?.result).toUpperCase() === 'FAIL')
/**
 * `source` 一律由 `SourceTag` 渲染（裁定 D）；**未知值或空值不硬塞成 `System`**：
 * 空值显示「—」，未知值由 SourceTag 兜底展示原值。
 * ⚠️ 已知口径差：`SourceTag` 的 `api → Worker`（Step 4 L1 组件表），而 P-12 验收写作 `API` ——
 *   本步**未获授权**改基础组件，故按实际渲染，并在交付说明登记（详见产出说明「被改动验收项」）。
 */
const hasSource = computed(() => Boolean(str(props.record?.source)))
const costText = computed(() => {
  const raw = str(props.record?.costMs).trim()
  if (!raw) return '—'
  const value = Number(raw)
  return Number.isFinite(value) ? `${value} ms` : dash(raw)
})

/** 明细字段（裁定 E 的清单；★ 不含任何凭据类字段，也不含不存在的 payload） */
const rows = computed(() => [
  { label: '结果', value: dash(props.record?.result), mono: true },
  { label: '动作 action', value: dash(props.record?.action), mono: true },
  { label: '来源 source', kind: 'source' },
  { label: '操作者 actor', value: dash(props.record?.actor), mono: true },
  { label: '对象 targetType', value: dash(props.record?.targetType), mono: true },
  { label: '对象 ID targetID', value: dash(props.record?.targetID), mono: true },
  { label: '时间 regYMDHMS', value: props.record?.regYMDHMS ? formatYMDHMS(props.record.regYMDHMS) : '—', mono: false },
  { label: '耗时 costMs', value: costText.value, mono: false },
  { label: '来源 IP ipAddr', value: dash(props.record?.ipAddr), mono: true },
  { label: '失败原因 errMsg', value: dash(props.record?.errMsg), mono: false },
  { label: '备注 memo', value: dash(props.record?.memo), mono: false }
])

function copyDigest() {
  const digest = str(props.record?.payloadDigest)
  if (!digest) return
  void copyText(digest)
}

function close() {
  emit('update:modelValue', false)
}

/** Esc 关闭 + Tab 焦点锁定（§2.11；与 AppDialog 同款实现） */
function handleKeydown(event) {
  if (event.key === 'Escape') {
    event.preventDefault()
    close()
    return
  }
  if (event.key !== 'Tab' || !panelRef.value) return
  const nodes = Array.from(panelRef.value.querySelectorAll(FOCUSABLE)).filter((el) => el.offsetParent !== null)
  if (nodes.length === 0) {
    event.preventDefault()
    panelRef.value.focus()
    return
  }
  const first = nodes[0]
  const last = nodes[nodes.length - 1]
  if (event.shiftKey && (document.activeElement === first || document.activeElement === panelRef.value)) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      // 焦点归还目标 = 打开抽屉前的触发元素（表格里的 payloadDigest 按钮）
      lastActiveElement = document.activeElement
      document.addEventListener('keydown', handleKeydown)
      await nextTick()
      panelRef.value?.focus()
    } else {
      document.removeEventListener('keydown', handleKeydown)
      if (lastActiveElement && typeof lastActiveElement.focus === 'function') lastActiveElement.focus()
      lastActiveElement = null
    }
  }
)

onBeforeUnmount(() => document.removeEventListener('keydown', handleKeydown))
</script>
