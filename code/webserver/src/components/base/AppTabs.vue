<!-- ============================================================================
 * AppTabs · L1 基础组件（Step 4）
 * ----------------------------------------------------------------------------
 * 规格：`line`（P-03 页内 Tab：1px 底边 + 250ms 平滑位移的 2px 下划线指示器）/
 *       `card`（区块切换：选中态 primary/subtle 底 + primary 描边）。
 * 无障碍：role="tablist" + role="tab" + aria-selected；←/→ 在标签间移动焦点（roving tabindex）。
 * 动效：指示器时长/缓动取 tokens.motion.tabIndicator（250ms ease-out）。
 * ========================================================================== -->
<template>
  <div class="flex flex-col gap-lg">
    <div
      class="relative"
      :class="variant === 'card' ? 'flex flex-wrap gap-sm' : 'flex items-center gap-xl border-b border-ch-border'"
      role="tablist"
      :aria-label="ariaLabel"
    >
      <button
        v-for="(item, index) in items"
        :key="item.key"
        :ref="(el) => setTabRef(el, index)"
        type="button"
        role="tab"
        class="relative flex items-center gap-xs whitespace-nowrap transition-colors duration-150 ease-out"
        :class="tabClass(item)"
        :aria-selected="item.key === modelValue ? 'true' : 'false'"
        :tabindex="item.key === modelValue ? 0 : -1"
        @click="select(item.key)"
        @keydown="onKeydown"
      >
        <span>{{ item.label }}</span>
        <Badge v-if="item.badge" :count="item.badge" variant="primary" :aria-label="`${item.label} ${item.badge} 条`" />
      </button>

      <span
        v-if="variant === 'line'"
        class="pointer-events-none absolute bottom-0 h-0.5 rounded-full bg-ch-primary"
        :style="indicatorStyle"
        aria-hidden="true"
      ></span>
    </div>

    <slot />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { tokens } from '@/js/tokens'
import Badge from '@/components/base/Badge.vue'

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  /** [{ key, label, badge? }] */
  items: { type: Array, default: () => [] },
  variant: { type: String, default: 'line' }, // line / card
  ariaLabel: { type: String, default: '标签页' }
})

const emit = defineEmits(['update:modelValue', 'change'])

const tabRefs = ref([])
const indicator = reactive({ left: 0, width: 0 })

const setTabRef = (el, index) => {
  tabRefs.value[index] = el || null
}

const indicatorStyle = computed(() => ({
  left: `${indicator.left}px`,
  width: `${indicator.width}px`,
  transitionProperty: 'left, width',
  transitionDuration: `${tokens.motion.tabIndicator.duration}ms`,
  transitionTimingFunction: tokens.motion.tabIndicator.easing
}))

const activeIndex = computed(() => props.items.findIndex((item) => item.key === props.modelValue))

function updateIndicator() {
  const el = tabRefs.value[activeIndex.value]
  if (!el) {
    indicator.left = 0
    indicator.width = 0
    return
  }
  indicator.left = el.offsetLeft
  indicator.width = el.offsetWidth
}

const tabClass = (item) => {
  const active = item.key === props.modelValue
  if (props.variant === 'card') {
    return [
      'rounded-lg border px-lg py-sm text-body-s',
      active
        ? 'border-ch-primary bg-ch-primary-subtle text-ch-primary'
        : 'border-ch-border text-ch-text-secondary hover:bg-ch-hover hover:text-ch-text-primary'
    ]
  }
  return [
    'pb-md pt-sm text-body',
    active ? 'font-medium text-ch-text-primary' : 'text-ch-text-secondary hover:text-ch-text-primary'
  ]
}

function select(key) {
  if (key === props.modelValue) return
  emit('update:modelValue', key)
  emit('change', key)
}

/** ←/→ 移动（仅移动焦点并同步选中，符合 WAI-ARIA tabs 的自动激活式实现） */
function onKeydown(event) {
  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
  const size = props.items.length
  if (!size) return
  event.preventDefault()
  const step = event.key === 'ArrowRight' ? 1 : -1
  const from = activeIndex.value < 0 ? 0 : activeIndex.value
  const next = (from + step + size) % size
  select(props.items[next].key)
  nextTick(() => tabRefs.value[next]?.focus())
}

let observer = null

onMounted(() => {
  updateIndicator()
  window.addEventListener('resize', updateIndicator)
  if (typeof ResizeObserver !== 'undefined') {
    observer = new ResizeObserver(updateIndicator)
    tabRefs.value.forEach((el) => el && observer.observe(el))
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateIndicator)
  observer?.disconnect()
  observer = null
})

watch(
  () => [props.modelValue, props.items.map((item) => `${item.key}:${item.label}`).join('|')],
  () => nextTick(updateIndicator)
)
</script>
