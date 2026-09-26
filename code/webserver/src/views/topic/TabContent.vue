<!-- ============================================================================
 * TabContent · P-03 Tab1「内容」（Step 7）
 * ----------------------------------------------------------------------------
 * 字段与校验口径（严格区分两套口径，§2.7 —— 本页只做**主题字段区间**这一套）：
 *   标题 ≤50 字（charCount，与后端 len(title) 同口径）| 简介 ≤200 字 |
 *   详述 **≤5000 字，无下限**（wordCount，与后端 countWords 同口径）| 作者 ≤64 / 地点 ≤128 /
 *   来源 ≤255 / 时期 ≤64 / 分类 ≤32 | 标签（逗号分隔，单标签 ≤20）| aiFlag '0'/'1'。
 * ★ 详述不设字数下限（2026-09-22 裁定：可留空、可短写），故本页只保留「>5000 转存」提示，
 *   不再有「至少 2000 字」行内报错；硬校验由后端兜底：`_checkRenderReadiness` 仅在
 *   「无正文且无 descriptionFileID」时返回 `C4`，按字段行内回显（裁定 E）。
 * 草稿所有权：`form` 由外壳（TopicEdit.vue）经 useTopicDraft 持有并以**共享响应式对象**传入，
 *   本页直接写 `form.xxx`（v-model 的等价写法）；这样切 Tab / 切组件时不丢未保存内容（裁定 I）。
 * ========================================================================== -->
<template>
  <div class="flex flex-col gap-2xl min-[1366px]:flex-row min-[1366px]:items-start">
    <div class="flex min-w-0 flex-1 flex-col gap-2xl">
      <section class="ch-card flex flex-col gap-xl" aria-labelledby="content-basic-title">
        <h2 id="content-basic-title" class="text-h3 text-ch-text-primary">基本信息</h2>

        <div :ref="setFieldRef('title')">
          <FormInput
            v-model="form.title"
            label="标题"
            required
            :word-limit="50"
            :error="fieldErrors.title || titleError"
            help="不超过 50 字；列表页与预览均以此为准"
            placeholder="请输入主题标题"
          />
        </div>

        <div :ref="setFieldRef('summary')">
          <FormInput
            v-model="form.summary"
            label="简介"
            required
            type="textarea"
            :rows="4"
            :word-limit="200"
            :error="fieldErrors.summary || summaryError"
            help="不超过 200 字，用于列表摘要与平台摘要"
          />
        </div>

        <div :ref="setFieldRef('description')" class="flex flex-col gap-xs">
          <FormInput
            v-model="form.description"
            label="详述"
            type="textarea"
            :rows="14"
            :error="fieldErrors.description"
            help="可留空、不限字数下限；超出 5000 字的部分将由服务端转存为文件，不影响保存"
          />
          <div class="flex flex-wrap items-center justify-between gap-md">
            <WordCounter :current="words" :max="5000" />
            <p v-if="overMax" class="flex items-center gap-xs text-caption text-ch-warning">
              <i class="fa fa-triangle-exclamation" aria-hidden="true"></i>
              <span>超出 {{ words - 5000 }} 字，将转存为文件（库内保留前 5000 字）</span>
            </p>
          </div>
          <p v-if="descriptionFileId" class="flex flex-wrap items-center gap-xs text-caption text-ch-info">
            <i class="fa fa-circle-check" aria-hidden="true"></i>
            <span>详述已转存文件：<span class="font-mono text-code">{{ descriptionFileId }}</span></span>
            <a
              v-if="descriptionUrl"
              :href="descriptionUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="text-ch-primary hover:text-ch-primary-hover"
            >查看文件</a>
          </p>
        </div>

        <div class="grid gap-xl md:grid-cols-2">
          <div :ref="setFieldRef('author')">
            <FormInput v-model="form.author" label="作者" :word-limit="64" :error="fieldErrors.author" placeholder="如：陈立恒" />
          </div>
          <div :ref="setFieldRef('location')">
            <FormInput v-model="form.location" label="地点" :word-limit="128" :error="fieldErrors.location" placeholder="如：甘肃敦煌" />
          </div>
          <div :ref="setFieldRef('source')">
            <FormInput v-model="form.source" label="来源" :word-limit="255" :error="fieldErrors.source" placeholder="如：馆藏实物测绘与考古简报" />
          </div>
          <div :ref="setFieldRef('period')">
            <FormInput v-model="form.period" label="时期" :word-limit="64" :error="fieldErrors.period" placeholder="如：盛唐" />
          </div>
        </div>

        <div :ref="setFieldRef('tagList')">
          <TagInput v-model="form.tagList" label="标签" :error="fieldErrors.tagList" />
        </div>

        <div :ref="setFieldRef('categoryCode')">
          <FormInput
            v-model="form.categoryCode"
            label="分类编码"
            :word-limit="32"
            :error="fieldErrors.categoryCode"
            help="可留空；对应 ch_topic.categoryCode"
            placeholder="如：MURAL"
          />
        </div>
      </section>

      <section class="ch-card flex flex-col gap-xl" aria-labelledby="content-extras-title">
        <h2 id="content-extras-title" class="text-h3 text-ch-text-primary">封面与标识</h2>

        <div class="flex flex-wrap items-start gap-xl">
          <div class="h-[120px] w-[160px] shrink-0 overflow-hidden rounded-lg border border-ch-border bg-ch-input">
            <img
              v-if="coverUrl"
              :src="coverUrl"
              :alt="form.title ? `${form.title} 封面` : '主题封面'"
              loading="lazy"
              decoding="async"
              class="h-full w-full object-cover"
            />
            <div v-else class="flex h-full w-full flex-col items-center justify-center gap-xs text-ch-text-tertiary">
              <i class="fa fa-image" aria-hidden="true"></i>
              <span class="text-caption">未设置封面</span>
            </div>
          </div>
          <div class="flex min-w-0 flex-1 flex-col gap-xs">
            <p class="text-body-s text-ch-text-secondary">封面取自「素材」页中被设为封面的那张附图。</p>
            <p class="text-caption text-ch-text-tertiary">
              coverFileID：<span class="font-mono text-code">{{ coverFileId || '（空）' }}</span>
            </p>
            <p class="text-caption text-ch-text-tertiary">
              ★ 更换封面请在「素材」页操作（服务端会把旧封面自动降级为正文图）。
            </p>
          </div>
        </div>

        <div :ref="setFieldRef('aiFlag')" class="flex flex-wrap items-center gap-md">
          <span class="text-body-s text-ch-text-secondary" id="ai-flag-label">AI 标识</span>
          <el-switch
            v-model="form.aiFlag"
            active-value="1"
            inactive-value="0"
            aria-labelledby="ai-flag-label"
          />
          <span class="text-body-s" :class="form.aiFlag === '1' ? 'text-ch-info' : 'text-ch-text-tertiary'">
            {{ form.aiFlag === '1' ? '含 AI 生成内容（已显式标注）' : '未标注 AI 参与' }}
          </span>
          <span class="text-caption text-ch-text-tertiary">含 AI 生成内容须显式标注</span>
        </div>
      </section>
    </div>

    <!-- ≥1024px：常显（≥1366px 为右侧固定 280px，1024–1365px 下沉到内容底部） -->
    <div
      class="hidden w-full shrink-0 lg:block min-[1366px]:w-[280px] min-[1366px]:sticky min-[1366px]:top-lg"
    >
      <CompletionPanel v-bind="panelProps" />
    </div>

    <!-- <1024px：折叠为可展开区 -->
    <details class="w-full rounded-xl border border-ch-border bg-ch-surface lg:hidden">
      <summary class="cursor-pointer px-xl py-lg text-body text-ch-text-primary">
        完成度 {{ doneCount }} / 5（展开查看）
      </summary>
      <div class="px-xl pb-xl">
        <CompletionPanel v-bind="panelProps" />
      </div>
    </details>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import FormInput from '@/components/base/FormInput.vue'
import WordCounter from '@/components/biz/WordCounter.vue'
import CompletionPanel from '@/views/topic/CompletionPanel.vue'
import TagInput from '@/views/topic/TagInput.vue'
import { charCount } from '@/utils/common'

const props = defineProps({
  /** 共享草稿（由外壳的 useTopicDraft 持有；此处直接改写其属性） */
  form: { type: Object, required: true },
  /** 服务端字段级错误（useTopicDraft.applyServerError 写入） */
  fieldErrors: { type: Object, default: () => ({}) },
  /** 详述实时字数（wordCount 口径，由外壳统一计算） */
  words: { type: Number, default: 0 },
  coverUrl: { type: String, default: '' },
  coverFileId: { type: String, default: '' },
  descriptionFileId: { type: String, default: '' },
  descriptionUrl: { type: String, default: '' },
  /** 附图条数（完成度第 4 项） */
  assetCount: { type: [Number, String], default: 0 },
  /** 服务端已选版式（完成度第 5 项，裁定 F） */
  layoutCode: { type: String, default: '' }
})

const TITLE_MAX = 50
const SUMMARY_MAX = 200

/* ---------------- 实时区间校验（行内提示，不阻断提交） ---------------- */
const titleError = computed(() =>
  charCount(props.form.title) > TITLE_MAX ? `${charCount(props.form.title)} 字，超出上限 ${TITLE_MAX} 字` : ''
)
const summaryError = computed(() =>
  charCount(props.form.summary) > SUMMARY_MAX ? `${charCount(props.form.summary)} 字，超出上限 ${SUMMARY_MAX} 字` : ''
)
/** 详述无下限（0 字合法），故只有 >5000 的提示，由下方 warning 行承担 */
const overMax = computed(() => props.words > 5000)

const panelProps = computed(() => ({
  title: props.form.title,
  summary: props.form.summary,
  wordCount: props.words,
  assetCount: props.assetCount,
  layoutCode: props.layoutCode,
  descriptionFileId: props.descriptionFileId
}))

/** 与 CompletionPanel 同口径的完成度计数（供 <1024px 折叠区的 summary 文案用） */
const doneCount = computed(() => {
  let count = 0
  if (props.form.title.trim() && charCount(props.form.title) <= TITLE_MAX) count += 1
  if (props.form.summary.trim() && charCount(props.form.summary) <= SUMMARY_MAX) count += 1
  if (props.descriptionFileId || props.words > 0) count += 1
  if (Number(props.assetCount) >= 1) count += 1
  if (props.layoutCode.trim()) count += 1
  return count
})

/* ---------------- 字段定位（`?focus=description` 与错误跳转用） ---------------- */
const fieldRefs = ref({})
const setFieldRef = (key) => (el) => {
  fieldRefs.value[key] = el || null
}

/** 滚动到字段并聚焦其原生控件 */
function focusField(key) {
  const wrapper = fieldRefs.value[key]
  if (!wrapper) return false
  const root = wrapper.$el || wrapper
  root?.scrollIntoView?.({ block: 'center', behavior: 'smooth' })
  const control = root?.querySelector?.('input, textarea')
  control?.focus?.()
  return Boolean(control)
}

defineExpose({ focusField })
</script>
