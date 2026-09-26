<!-- ============================================================================
 * AssetFilterBar · P-04 素材图库筛选条 + 视图切换（Step 8）
 * ----------------------------------------------------------------------------
 * ★ 筛选能力对照（附录 B R-17，**不得让用户误以为是全量筛选**）：
 *   · 搜索 → `keyword`   ：服务端支持（后端按 `origName` / `objectName` 模糊）；
 *   · 类型 → `fileExt`   ：服务端支持（2026-09-20 新增）；
 *   · 规格 → 无对应参数   ：**仅当前页**（客户端按 width/height 判定）→ 标签后缀「仅当前页」；
 *   · 引用状态 → 无对应参数：**仅当前页**（客户端按 topicassetqry 反查结果判定）→ 同上。
 *   两个「仅当前页」控件均带 title 说明，且不隐藏、不静默忽略。
 * 视图切换（网格 / 列表）与全部筛选项写入 URL query（刷新保持）。
 * 无障碍：全部原生 input/select/button（§2.11 禁止 div 模拟控件）；`/` 聚焦搜索框。
 * ========================================================================== -->
<template>
  <div class="flex flex-wrap items-end gap-md rounded-xl border border-ch-border bg-ch-surface px-xl py-lg">
    <label class="flex min-w-[220px] flex-1 flex-col gap-xs">
      <span class="text-body-s text-ch-text-secondary">搜索素材</span>
      <span class="relative flex items-center">
        <i class="fa fa-magnifying-glass absolute left-md text-caption text-ch-text-tertiary" aria-hidden="true"></i>
        <input
          ref="keywordRef"
          :value="keyword"
          type="search"
          class="h-9 w-full rounded-md border border-ch-border bg-ch-input pl-3xl pr-md text-body text-ch-text-primary placeholder:text-ch-text-tertiary focus:border-ch-border-focus"
          placeholder="原始文件名 / 对象键（按 / 聚焦）"
          aria-label="搜索素材：按后端 origName / objectName 模糊匹配，按斜杠键可快速聚焦"
          :disabled="disabled"
          @input="handleKeyword"
          @keydown.esc="blurKeyword"
        />
      </span>
    </label>

    <label class="flex flex-col gap-xs">
      <span class="text-body-s text-ch-text-secondary">类型</span>
      <select
        class="h-9 rounded-md border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
        aria-label="按扩展名筛选（服务端 fileExt）"
        :value="ext"
        :disabled="disabled"
        @change="emit('update:ext', $event.target.value)"
      >
        <option v-for="option in EXT_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
    </label>

    <label class="flex flex-col gap-xs" :title="SCOPE_HINT">
      <span class="text-body-s text-ch-text-secondary">规格（仅当前页）</span>
      <select
        class="h-9 rounded-md border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
        aria-label="按规格筛选（仅当前页，后端无对应参数）"
        :value="spec"
        :disabled="disabled"
        @change="emit('update:spec', $event.target.value)"
      >
        <option v-for="option in SPEC_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
    </label>

    <label class="flex flex-col gap-xs" :title="SCOPE_HINT">
      <span class="text-body-s text-ch-text-secondary">引用状态（仅当前页）</span>
      <select
        class="h-9 rounded-md border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
        aria-label="按引用状态筛选（仅当前页，后端无对应参数）"
        :value="refState"
        :disabled="disabled"
        @change="emit('update:ref', $event.target.value)"
      >
        <option v-for="option in REF_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
    </label>

    <AppButton v-if="dirty" size="sm" icon="fa fa-rotate-right" :disabled="disabled" @click="emit('reset')">
      清除筛选
    </AppButton>

    <div class="ml-auto flex items-center gap-xs" role="group" aria-label="视图切换">
      <button
        v-for="option in VIEW_OPTIONS"
        :key="option.value"
        type="button"
        class="inline-flex h-9 items-center gap-xs rounded-lg border px-md text-body-s transition-colors duration-150 ease-out"
        :class="viewClass(option.value)"
        :aria-pressed="view === option.value ? 'true' : 'false'"
        :disabled="disabled"
        @click="emit('update:view', option.value)"
      >
        <i :class="option.icon" aria-hidden="true"></i>
        <span>{{ option.label }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import AppButton from '@/components/base/AppButton.vue'
import { debounce } from '@/utils/common'

/** 类型档位 = 后端 `fileExt` 落库值（小写、无点） */
const EXT_OPTIONS = [
  { value: '', label: '全部类型' },
  { value: 'png', label: 'PNG' },
  { value: 'jpg', label: 'JPG' },
  { value: 'jpeg', label: 'JPEG' },
  { value: 'gif', label: 'GIF' },
  { value: 'webp', label: 'WEBP' }
]

/** 规格档位（客户端判定，仅当前页） */
const SPEC_OPTIONS = [
  { value: '', label: '全部规格' },
  { value: 'oversize', label: '超大（> 1920px）' },
  { value: '3:4', label: '3:4' },
  { value: '1:1', label: '1:1' },
  { value: '4:3', label: '4:3' }
]

const REF_OPTIONS = [
  { value: '', label: '全部' },
  { value: 'none', label: '未引用' },
  { value: 'some', label: '已引用' }
]

const VIEW_OPTIONS = [
  { value: 'grid', label: '网格', icon: 'fa fa-table-cells-large' },
  { value: 'list', label: '列表', icon: 'fa fa-list' }
]

const SCOPE_HINT =
  '「规格 / 引用状态」后端无对应查询参数（附录 B R-17），仅对当前页已加载的素材生效，不是全量筛选。'

const props = defineProps({
  keyword: { type: String, default: '' },
  /** 扩展名（后端 `fileExt`） */
  ext: { type: String, default: '' },
  spec: { type: String, default: '' },
  refState: { type: String, default: '' },
  view: { type: String, default: 'grid' },
  disabled: { type: Boolean, default: false }
})

const emit = defineEmits(['update:keyword', 'update:ext', 'update:spec', 'update:ref', 'update:view', 'reset'])

const keywordRef = ref(null)

const dirty = computed(
  () => Boolean(props.keyword || props.ext || props.spec || props.refState) || props.view !== 'grid'
)

const viewClass = (value) =>
  props.view === value
    ? 'border-ch-primary bg-ch-primary-subtle text-ch-primary'
    : 'border-ch-border-light bg-ch-elevated text-ch-text-secondary hover:border-ch-primary hover:text-ch-primary'

/** 输入防抖 300ms（避免每敲一个字就打一次列表请求） */
const pushKeyword = debounce((value) => emit('update:keyword', value), 300)

const handleKeyword = (event) => pushKeyword(event.target.value)

function blurKeyword() {
  pushKeyword.cancel()
  keywordRef.value?.blur()
}

/** `/` 聚焦搜索框（§2.11 快捷键）：焦点在可编辑控件上时不接管 */
function onGlobalKeydown(event) {
  if (event.key !== '/' || event.metaKey || event.ctrlKey || event.altKey) return
  const tag = String(event.target?.tagName || '').toLowerCase()
  if (tag === 'input' || tag === 'textarea' || tag === 'select' || event.target?.isContentEditable) return
  event.preventDefault()
  keywordRef.value?.focus()
}

onMounted(() => window.addEventListener('keydown', onGlobalKeydown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onGlobalKeydown)
  pushKeyword.cancel()
})
</script>
