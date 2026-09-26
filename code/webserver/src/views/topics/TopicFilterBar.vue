<!-- ============================================================================
 * TopicFilterBar · P-02 主题库筛选条（Step 6）
 * ----------------------------------------------------------------------------
 * ★ 参数与真实后端严格一致（Step 6 裁定 B，纠计划原文之错）：
 *   1) 搜索 → `keyword`。真实 `topicService.queryTopic` 只读 `keyword`
 *      （processor/topicService.py:834；映射到 title/summary/description 的 LIKE），
 *      ★ `searchOption` 在 topicqry 上**不存在**，禁止使用；
 *   2) 状态 → `status`。后端是**单值等值条件**（query_ch_topic → condList ["status","=",status]），
 *      故此处实现为**单选下拉**；计划原文的「多选」登记为需后端扩展的待确认项，
 *      ★ 不得用「对 5 个状态各发一次请求再合并」伪造多选（会破坏 total 与分页语义）；
 *   3) 时间 → `beginYMDHMS` / `endYMDHMS`（14 位 YYYYMMDDHHMMSS）。
 *      ★ 后端该条件作用在 **regYMDHMS（创建时间）**（mysqlCommon.py:356-357），
 *      故 UI 文案必须是「创建时间」而非「更新时间」；
 *   4) ★ 不渲染平台筛选控件：真实 topicqry **没有 platform 参数**（裁定 b4），
 *      若读取 mock 独有的 `topic.platform` 做筛选，会出现「Mock 通过、真实后端静默不筛」的假象。
 *
 * 排序（裁定 D）：只提供后端支持的两档 —— `modify`（= modifyYMDHMS DESC，全量排序，缺省）
 *   与 `create`（= recID ASC，后端缺省顺序，mysqlCommon.py:290-295）；
 *   ★ 不做「仅当前页排序」并宣称全量排序。
 *
 * 无障碍：全部为原生 input/select（§2.11 禁止 div 模拟控件）；`/` 聚焦搜索框、Esc 归还焦点（§2.11 快捷键）。
 * ========================================================================== -->
<template>
  <div class="flex flex-wrap items-end gap-md rounded-xl border border-ch-border bg-ch-surface px-xl py-lg">
    <label class="flex min-w-[200px] flex-1 flex-col gap-xs">
      <span class="text-body-s text-ch-text-secondary">搜索标题</span>
      <span class="relative flex items-center">
        <i class="fa fa-magnifying-glass absolute left-md text-caption text-ch-text-tertiary" aria-hidden="true"></i>
        <input
          ref="keywordRef"
          :value="keyword"
          type="search"
          class="h-9 w-full rounded-md border border-ch-border bg-ch-input pl-3xl pr-md text-body text-ch-text-primary placeholder:text-ch-text-tertiary focus:border-ch-border-focus"
          placeholder="标题 / 编码（按 / 聚焦）"
          aria-label="搜索标题，按斜杠键可快速聚焦"
          :disabled="disabled"
          @input="handleKeyword"
          @keydown.esc="blurKeyword"
        />
      </span>
    </label>

    <label class="flex flex-col gap-xs">
      <span class="text-body-s text-ch-text-secondary">状态</span>
      <select
        class="h-9 rounded-md border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
        aria-label="按状态筛选（单选）"
        :value="status"
        :disabled="disabled"
        @change="emit('update:status', $event.target.value)"
      >
        <option value="">全部状态</option>
        <option v-for="(meta, key) in TOPIC_STATUS_MAP" :key="key" :value="key">{{ meta.label }}</option>
      </select>
    </label>

    <label class="flex flex-col gap-xs">
      <span class="text-body-s text-ch-text-secondary">创建时间</span>
      <select
        class="h-9 rounded-md border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
        aria-label="按创建时间筛选"
        :value="range"
        :disabled="disabled"
        @change="emit('update:range', $event.target.value)"
      >
        <option v-for="option in RANGE_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
    </label>

    <label class="flex flex-col gap-xs">
      <span class="text-body-s text-ch-text-secondary">排序</span>
      <select
        class="h-9 rounded-md border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
        aria-label="排序方式"
        :value="order"
        :disabled="disabled"
        @change="emit('update:order', $event.target.value)"
      >
        <option v-for="option in ORDER_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
    </label>

    <AppButton
      v-if="dirty"
      size="sm"
      icon="fa fa-rotate-right"
      :disabled="disabled"
      @click="emit('reset')"
    >
      清除筛选
    </AppButton>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import AppButton from '@/components/base/AppButton.vue'
import { TOPIC_STATUS_MAP } from '@/config/chOptions'
import { debounce } from '@/utils/common'

/** 创建时间档位（★ 语义为「创建时间」，见文件头第 3 条） */
const RANGE_OPTIONS = [
  { value: 'all', label: '全部时间' },
  { value: '7', label: '近 7 天' },
  { value: '30', label: '近 30 天' },
  { value: '90', label: '近 90 天' }
]

/** 排序档位（裁定 D：只列后端支持的两档） */
const ORDER_OPTIONS = [
  { value: 'modify', label: '按修改时间（默认）' },
  { value: 'create', label: '按创建顺序' }
]

const props = defineProps({
  keyword: { type: String, default: '' },
  status: { type: String, default: '' },
  range: { type: String, default: 'all' },
  order: { type: String, default: 'modify' },
  disabled: { type: Boolean, default: false }
})

const emit = defineEmits(['update:keyword', 'update:status', 'update:range', 'update:order', 'reset'])

const keywordRef = ref(null)

/** 是否存在生效中的筛选（用于展示「清除筛选」） */
const dirty = computed(
  () => Boolean(props.keyword || props.status) || props.range !== 'all' || props.order !== 'modify'
)

/** 输入防抖 300ms（§2.3 微交互；避免每敲一个字就打一次列表请求） */
const pushKeyword = debounce((value) => emit('update:keyword', value), 300)

function handleKeyword(event) {
  pushKeyword(event.target.value)
}

/** Esc：清空本地输入态并归还焦点（键盘可达的退出路径） */
function blurKeyword() {
  pushKeyword.cancel()
  keywordRef.value?.blur()
}

/**
 * `/` 聚焦搜索框（§2.11 快捷键）。仅在焦点不在可编辑控件上时接管，避免打断正常输入。
 */
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
