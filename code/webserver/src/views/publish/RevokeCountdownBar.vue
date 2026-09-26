<!-- ============================================================================
 * RevokeCountdownBar · P-10 / Tab5「60 秒撤销入口」（Step 14 · 越界授权文件，裁定 K）
 * ----------------------------------------------------------------------------
 * 【后端事实（服从）】撤销窗由服务端 `WECHAT_REVOKE_WINDOW_SECONDS`（默认 60，`data.windowSeconds`
 *   为准）判定，前端**只做倒计时展示**。撤销 = `delFlag='1'`（软删）。
 *
 * 【★ 倒计时的正确口径（裁定 H）】剩余秒数一律按 **`pushedYMDHMS + windowSeconds` 绝对时间重算**：
 *   · 挂载时即按绝对时间算剩余（例如投递后 8 秒才挂载 → 显示 52 秒，**不是** 60）；
 *   · 页面隐藏 / 切标签 / 刷新后回来（`visibilitychange` / `focus` / `pageshow`）立即重算；
 *   · **禁止**「进入页面即 60」的假倒计时。
 * 计时器与事件监听在 `onBeforeUnmount` 全部清理（§2.11）。
 * ========================================================================== -->
<template>
  <div
    class="sticky top-0 z-30 flex flex-wrap items-center gap-md rounded-xl border border-ch-primary/40 bg-ch-primary-subtle px-xl py-md"
    role="status"
    aria-live="polite"
  >
    <i class="fa fa-paper-plane text-ch-primary" aria-hidden="true"></i>

    <p class="flex flex-wrap items-center gap-sm text-body-s text-ch-text-primary">
      <span>已推送到草稿箱 · 可在</span>
      <span class="font-mono text-body text-ch-primary" data-testid="revoke-remaining">{{ remaining }}</span>
      <span>秒内撤销</span>
      <span v-if="remoteID" class="font-mono text-code text-ch-text-tertiary" :title="remoteID">
        （remoteID {{ remoteID }}）
      </span>
    </p>

    <p class="text-caption text-ch-text-tertiary">
      撤销仅置本地发布记录 `delFlag=1`；平台侧草稿如需删除请人工在后台处理
    </p>

    <div class="ml-auto flex items-center gap-sm">
      <AppButton
        size="sm"
        icon="fa fa-rotate-left"
        :loading="revoking"
        :disabled="remaining <= 0"
        :disabled-reason="remaining <= 0 ? '撤销窗已过期' : ''"
        data-testid="revoke-button"
        @click="emit('revoke', record)"
      >
        撤销
      </AppButton>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppButton from '@/components/base/AppButton.vue'
import { remainingRevokeSeconds } from '@/views/publish/usePublishFlow'

const props = defineProps({
  /** { publishRecordID, idempotencyKey, remoteID, pushedYMDHMS, windowSeconds } */
  record: { type: Object, default: null },
  revoking: { type: Boolean, default: false }
})

const emit = defineEmits(['revoke', 'expired'])

const tick = ref(Date.now())
let timer = null

const remaining = computed(() => remainingRevokeSeconds(props.record, tick.value))
const remoteID = computed(() => String(props.record?.remoteID || ''))

/** ★ 绝对时间重算：隐藏/切换回来时立即刷新（tab 被节流也不影响） */
function recompute() {
  tick.value = Date.now()
  if (props.record && remaining.value <= 0) {
    stop()
    emit('expired', props.record)
  }
}

function start() {
  stop()
  tick.value = Date.now()
  if (!props.record) return
  if (remaining.value <= 0) {
    emit('expired', props.record)
    return
  }
  timer = window.setInterval(recompute, 1000)
}

function stop() {
  if (timer) window.clearInterval(timer)
  timer = null
}

onMounted(() => {
  start()
  document.addEventListener('visibilitychange', recompute)
  window.addEventListener('focus', recompute)
  window.addEventListener('pageshow', recompute)
})

onBeforeUnmount(() => {
  stop()
  document.removeEventListener('visibilitychange', recompute)
  window.removeEventListener('focus', recompute)
  window.removeEventListener('pageshow', recompute)
})

watch(() => [props.record?.publishRecordID, props.record?.pushedYMDHMS, props.record?.windowSeconds], () => start())
</script>
