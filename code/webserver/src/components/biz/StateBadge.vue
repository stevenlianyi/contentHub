<!-- ============================================================================
 * StateBadge · L2 业务组件（Step 4）
 * ----------------------------------------------------------------------------
 * ★ 三重编码（裁定 C6）：**形状图标 + 颜色 + 文字**，禁止仅用颜色表达状态，
 *   故灰度（Chrome DevTools Rendering → Emulate vision deficiencies: Achromatopsia）下
 *   success（fa-circle-check）与 danger（fa-circle-xmark）依然可区分。
 * ★ 字典唯一来源：`src/config/chOptions.js`，一律走 `resolveStatusMeta()`；
 *   未知状态由兜底产出「灰色 + 空心 ○ + 原值」，并额外 console.error（便于发现字典缺项）。
 * ★ 组件内**不得**出现平台/厂商分支（§2.11）；平台过滤由父级调用 `isLayoutAllowed()`。
 * 支持域：topic / publish / job / artifact / health / compliance（6 类，见 §2.6）。
 * ========================================================================== -->
<template>
  <span
    class="inline-flex items-center gap-xs whitespace-nowrap text-body-s"
    :style="{ color: meta.color }"
    :aria-label="`状态：${meta.label}`"
  >
    <i :class="[meta.icon, meta.pulse ? 'animate-pulse-slow' : '']" aria-hidden="true"></i>
    <span v-if="showLabel">{{ meta.label }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import {
  ARTIFACT_STATUS_MAP,
  COMPLIANCE_LEVEL_MAP,
  HEALTH_STATUS_MAP,
  JOB_STATUS_MAP,
  PUBLISH_STATUS_MAP,
  SENSITIVE_LEVEL_MAP,
  TOPIC_STATUS_MAP,
  resolveStatusMeta
} from '@/config/chOptions'

const props = defineProps({
  /** topic / publish / job / artifact / health / compliance */
  domain: { type: String, default: '' },
  status: { type: [String, Number], default: '' },
  showLabel: { type: Boolean, default: true }
})

/**
 * 合规域同时接受两套口径（§2.6 修正 ②）：
 * 汇总用 PASS / WARN / BLOCK，问题清单用 ERROR / WARN —— 合并后两者都能命中。
 */
const DOMAIN_MAP = {
  topic: TOPIC_STATUS_MAP,
  publish: PUBLISH_STATUS_MAP,
  job: JOB_STATUS_MAP,
  artifact: ARTIFACT_STATUS_MAP,
  health: HEALTH_STATUS_MAP,
  compliance: { ...COMPLIANCE_LEVEL_MAP, ...SENSITIVE_LEVEL_MAP }
}

const meta = computed(() => {
  const map = DOMAIN_MAP[props.domain]
  const defined = Boolean(map) && Object.prototype.hasOwnProperty.call(map, props.status)
  if (!defined) {
    console.error('[StateBadge] 未定义状态', props.domain, props.status)
  }
  return resolveStatusMeta(map, props.status)
})
</script>
