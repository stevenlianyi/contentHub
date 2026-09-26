<!-- ============================================================================
 * AssetOrderStrip · L2 业务组件（Step 4）
 * ----------------------------------------------------------------------------
 * 规格：缩略图 64×64 / 圆角 6 / 间距 8；序号即滑动顺序；第 1 张标记「封面」；
 *       支持拖拽**且必须提供「上移 / 下移」按钮**（无障碍 P0，裁定 G）；比例不一致的项显示 ⚠。
 * 无障碍：上移/下移为原生 button（Tab 可到达、Enter/Space 可触发），带具体 aria-label
 *       （如「上移第 3 项」）；首项禁用上移、末项禁用下移。
 * 序号口径：`sortOrder`/`seqNo` 越小越靠前（§2.9.3）；重排后统一回写 seqNo 与封面唯一标记。
 * ========================================================================== -->
<template>
  <ol class="flex flex-wrap items-center gap-sm">
    <li
      v-for="(item, index) in items"
      :key="item.fileID || item.assetKey || index"
      class="flex flex-col items-center gap-xs"
      :draggable="sortable ? 'true' : 'false'"
      @dragstart="onDragStart(index, $event)"
      @dragover="onDragOver"
      @drop="onDrop(index)"
      @dragend="dragIndex = null"
    >
      <div
        class="relative h-16 w-16 overflow-hidden rounded-md border"
        :class="coverFlag(item, index) ? 'border-ch-primary' : 'border-ch-border'"
      >
        <img
          v-if="displaySrc(item)"
          :src="displaySrc(item)"
          :alt="`第 ${index + 1} 张素材`"
          loading="lazy"
          decoding="async"
          class="h-full w-full object-cover"
        />
        <span v-else class="flex h-full w-full items-center justify-center text-ch-text-tertiary">
          <i class="fa fa-image" aria-hidden="true"></i>
        </span>

        <span
          class="absolute left-0 top-0 rounded-br-md bg-ch-base/80 px-xs text-caption text-ch-text-primary"
          aria-hidden="true"
        >
          {{ index + 1 }}
        </span>

        <span
          v-if="coverFlag(item, index)"
          class="absolute inset-x-0 bottom-0 bg-ch-primary text-center text-[10px] leading-4 text-ch-text-inverse"
        >
          封面
        </span>

        <span
          v-if="isMismatch(item)"
          class="absolute right-0 top-0 flex h-4 w-4 items-center justify-center rounded-bl-md bg-ch-warning text-[10px] text-ch-text-inverse"
          :title="`比例不一致（当前 ${item.ratio || '未知'}），App 内滑动会跳动`"
          :aria-label="`第 ${index + 1} 项比例不一致`"
          role="img"
        >
          <i class="fa fa-triangle-exclamation" aria-hidden="true"></i>
        </span>
      </div>

      <div v-if="sortable" class="flex items-center gap-xs">
        <button
          type="button"
          class="flex h-6 w-6 items-center justify-center rounded-sm border border-ch-border-light text-ch-text-secondary transition-colors duration-150 ease-out hover:bg-ch-hover disabled:cursor-not-allowed disabled:text-ch-text-disabled"
          :disabled="index === 0"
          :aria-label="`上移第 ${index + 1} 项`"
          @click="move(index, -1)"
        >
          <i class="fa fa-angle-up" aria-hidden="true"></i>
        </button>
        <button
          type="button"
          class="flex h-6 w-6 items-center justify-center rounded-sm border border-ch-border-light text-ch-text-secondary transition-colors duration-150 ease-out hover:bg-ch-hover disabled:cursor-not-allowed disabled:text-ch-text-disabled"
          :disabled="index === items.length - 1"
          :aria-label="`下移第 ${index + 1} 项`"
          @click="move(index, 1)"
        >
          <i class="fa fa-angle-down" aria-hidden="true"></i>
        </button>
      </div>
    </li>
  </ol>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  /** [{ fileID, url, thumbnailUrl?, seqNo, ratio, isCover }] */
  items: { type: Array, default: () => [] },
  sortable: { type: Boolean, default: true },
  /** 期望比例（如 '3:4'）；不传则按出现次数最多的比例作为基准 */
  expectedRatio: { type: String, default: '' }
})

const emit = defineEmits(['update:items'])

let dragIndex = null

const displaySrc = (item) => item.thumbnailUrl || item.url || ''
const coverFlag = (item, index) => index === 0 || item.isCover === true || item.isCover === '1'

const dominantRatio = computed(() => {
  if (props.expectedRatio) return props.expectedRatio
  const counts = new Map()
  props.items.forEach((item) => {
    const key = String(item.ratio || '')
    if (!key) return
    counts.set(key, (counts.get(key) || 0) + 1)
  })
  let best = ''
  let bestCount = -1
  counts.forEach((count, key) => {
    if (count > bestCount) {
      bestCount = count
      best = key
    }
  })
  return best
})

const isMismatch = (item) => {
  const key = String(item.ratio || '')
  return Boolean(key) && Boolean(dominantRatio.value) && key !== dominantRatio.value
}

/** 重排：回写 seqNo（1 起）与封面唯一标记，保证与后端 topicassetmodify orderList 口径一致 */
function reorder(from, to) {
  if (to < 0 || to >= props.items.length) return
  const next = props.items.slice()
  const [moved] = next.splice(from, 1)
  next.splice(to, 0, moved)
  emit(
    'update:items',
    next.map((item, index) => ({ ...item, seqNo: index + 1, isCover: index === 0 ? '1' : '0' }))
  )
}

function move(index, step) {
  reorder(index, index + step)
}

function onDragStart(index, event) {
  dragIndex = index
  event.dataTransfer?.setData('text/plain', String(index))
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}

function onDragOver(event) {
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
}

function onDrop(index) {
  if (dragIndex === null || dragIndex === index) return
  reorder(dragIndex, index)
  dragIndex = null
}
</script>
