<!-- ============================================================================
 * AssetThumb · L2 业务组件（Step 4）
 * ----------------------------------------------------------------------------
 * 规格：1:1 或 4:3，圆角 8；hover 显示「查看 / 移除」；重复素材叠加 ⚠ 覆盖徽标；
 *       `alt` 默认取图注，无图注时提示填写；`loading="lazy"` + `srcset` 三档（320/640/1280）。
 * 数据口径（§2.4.5）：URL 一律读后端出参（`xxxUrl` / `thumbnails`），前端不拼接 fileID。
 * 无障碍：图标按钮必须可 Tab 到达且带 aria-label；覆盖层用 group-focus-within 同步可见。
 * ========================================================================== -->
<template>
  <figure
    class="group relative overflow-hidden rounded-lg border bg-ch-input"
    :class="[aspectClass, selected ? 'border-ch-primary' : 'border-ch-border']"
  >
    <img
      v-if="displaySrc && !failed"
      :src="displaySrc"
      :srcset="computedSrcset || undefined"
      :sizes="sizes"
      :alt="altText"
      :width="width || undefined"
      :height="height || undefined"
      loading="lazy"
      decoding="async"
      class="h-full w-full object-cover"
      @error="failed = true"
    />
    <div v-else class="flex h-full w-full flex-col items-center justify-center gap-xs text-ch-text-tertiary">
      <i class="fa fa-image text-xl" aria-hidden="true"></i>
      <span class="text-caption">{{ failed ? '图片加载失败' : '无预览图' }}</span>
    </div>

    <!-- 重复素材覆盖徽标（素材去重命中 dedupHit=1） -->
    <span
      v-if="duplicated"
      class="absolute left-xs top-xs inline-flex items-center gap-xs rounded-sm bg-ch-warning px-xs py-[2px] text-caption text-ch-text-inverse"
      title="重复素材：命中已有 contentHash，可直接复用"
    >
      <i class="fa fa-triangle-exclamation" aria-hidden="true"></i>
      重复
    </span>

    <!-- hover / 键盘聚焦时显示操作（viewable / removable 控制） -->
    <div
      v-if="viewable || removable"
      class="absolute inset-0 flex items-center justify-center gap-sm bg-ch-base/70 opacity-0 transition-opacity duration-150 ease-out group-hover:opacity-100 group-focus-within:opacity-100"
    >
      <button
        v-if="viewable"
        type="button"
        class="inline-flex h-7 items-center gap-xs rounded-md border border-ch-border-light bg-ch-elevated px-sm text-caption text-ch-text-primary transition-colors duration-150 ease-out hover:border-ch-primary hover:text-ch-primary"
        :aria-label="`查看素材：${altText}`"
        @click.stop="emit('view')"
      >
        <i class="fa fa-eye" aria-hidden="true"></i>
        查看
      </button>
      <button
        v-if="removable"
        type="button"
        class="inline-flex h-7 items-center gap-xs rounded-md border border-ch-danger bg-transparent px-sm text-caption text-ch-danger transition-colors duration-150 ease-out hover:bg-ch-danger/10"
        :aria-label="`移除素材：${altText}`"
        @click.stop="emit('remove')"
      >
        <i class="fa fa-trash" aria-hidden="true"></i>
        移除
      </button>
    </div>

    <figcaption
      v-if="caption"
      class="absolute inset-x-0 bottom-0 truncate bg-ch-base/70 px-sm py-xs text-caption text-ch-text-primary"
      :title="caption"
    >
      {{ caption }}
    </figcaption>
    <figcaption
      v-else
      class="absolute inset-x-0 bottom-0 truncate bg-ch-base/70 px-sm py-xs text-caption text-ch-warning"
    >
      图注待补充
    </figcaption>
  </figure>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  /** 原图 URL（后端出参，禁止前端拼接） */
  url: { type: String, default: '' },
  thumbnailUrl: { type: String, default: '' },
  /** { 320, 640, 1280 } 三档缩略图（mock 与后端同构） */
  thumbnails: { type: Object, default: null },
  /** 直接给 srcset 字符串时优先使用 */
  srcset: { type: String, default: '' },
  sizes: { type: String, default: '(max-width: 640px) 50vw, 240px' },
  width: { type: [Number, String], default: 0 },
  height: { type: [Number, String], default: 0 },
  caption: { type: String, default: '' },
  /** 显式 alt；缺省取图注 */
  alt: { type: String, default: '' },
  duplicated: { type: Boolean, default: false },
  selected: { type: Boolean, default: false },
  /** 1:1 / 4:3 / none */
  aspect: { type: String, default: '1:1' },
  viewable: { type: Boolean, default: true },
  removable: { type: Boolean, default: true }
})

const emit = defineEmits(['view', 'remove'])

const failed = ref(false)

const displaySrc = computed(() => props.thumbnailUrl || props.url)
const aspectClass = computed(() => {
  if (props.aspect === '4:3') return 'aspect-[4/3]'
  if (props.aspect === 'none') return ''
  return 'aspect-square'
})

/** alt 默认取图注；无图注时给出可操作的文案，而不是留空（无障碍 + 引导补全） */
const altText = computed(() => props.alt || props.caption || '素材图，图注待补充')

/** srcset 三档：优先显式 srcset，其次 thumbnails 对象，最后退回单图 */
const computedSrcset = computed(() => {
  if (props.srcset) return props.srcset
  const map = props.thumbnails
  if (!map) return ''
  return [320, 640, 1280]
    .filter((key) => map[key])
    .map((key) => `${map[key]} ${key}w`)
    .join(', ')
})

watch(
  () => [props.url, props.thumbnailUrl],
  () => {
    failed.value = false
  }
)
</script>
