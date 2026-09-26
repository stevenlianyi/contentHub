/* ============================================================================
 * useTopicDraft · P-03 Tab1「内容」草稿编排（Step 7 · 越界授权新建，裁定 K）
 * ----------------------------------------------------------------------------
 * 职责（只做内容字段，不碰状态）：
 *   1) 服务端记录 ↔ 表单草稿的双向编解码（`tagList` 数组 ↔ 逗号分隔串，裁定 H）；
 *   2) **差量提交**：`buildDiff()` 只产出与基线不同的**内容字段**；
 *      ★ 绝不提交 `status` / `publishStatus`（裁定 D：状态跃迁只允许出现在显式动作中）；
 *      ★ 空值一律跳过（裁定 G：后端「非空才写入」，清空无法生效）；
 *   3) 保存双轨：显式保存（Ctrl/Cmd+S）与静默自动保存（切 Tab / 离开 / 30s 无操作）；
 *      ★ 失败不清空输入（§2.5 第 3 条）：只记录字段级错误并保留草稿；
 *   4) 服务端 `C4/C5/C6/C7` → **按字段行内回显**（见 `applyServerError`）。
 *
 * 服务端事实（不可凭计划文字臆断）：
 *   · `topicmodify` 出参 `data.data` = 落库后**回读的完整记录**（topicService.py:853-860），
 *     故保存成功后一律以服务端返回刷新草稿与字数（裁定 H：详述 >5000 会被转存，
 *     库内正文只剩 5000 字前缀，本地输入字数不可继续沿用）；
 *   · 字段错误文案形如「数值超出允许范围: description(字段#5);提交渲染前详述字数=1500, …」
 *     （errMsgCommon.rtnMSG 用 `field = '<字段名>(字段#N)'` 做 %s 替换，apiCommon.genRtnResult 追加 errMsgList），
 *     故字段定位靠 MSG.content 中的 `<字段名>(字段#N)` 反查。
 * ========================================================================== */
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { toast } from 'vue3-toastify'
import { topicModify } from '@/api/topic'
import { charCount, formatYMDHMS, wordCount as countWords } from '@/utils/common'

/** 内容字段清单（= Tab1 可编辑字段，顺序即错误定位顺序） */
export const DRAFT_FIELDS = [
  'title', 'summary', 'description', 'author', 'location',
  'source', 'period', 'tagList', 'categoryCode', 'aiFlag'
]

/** 可被行内回显的服务端错误码（§2.5 C 段） */
const FIELD_ERROR_CODES = ['C4', 'C5', 'C6', 'C7']

const TAG_SEPARATOR = ','
const IDLE_AUTOSAVE_MS = 30000

const toText = (value) => (value === null || value === undefined ? '' : String(value))

/** 服务端 tagList（逗号分隔串）→ 数组 */
export function splitTagList(value) {
  return toText(value)
    .split(/[,，]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

/** 主题记录 → 草稿形态（表单字段 + 数组化 tagList） */
export function topicToDraft(topic) {
  const source = topic || {}
  return {
    title: toText(source.title),
    summary: toText(source.summary),
    description: toText(source.description),
    author: toText(source.author),
    location: toText(source.location),
    source: toText(source.source),
    period: toText(source.period),
    tagList: splitTagList(source.tagList),
    categoryCode: toText(source.categoryCode),
    aiFlag: toText(source.aiFlag) === '1' ? '1' : '0'
  }
}

/** 从服务端错误文案中反查字段名（`description(字段#5)` → `description`） */
export function matchErrorField(content) {
  const text = toText(content)
  return DRAFT_FIELDS.find((key) => text.includes(`${key}(`)) || ''
}

/** 服务端错误文案 → 行内提示（保留「字段名 + 位置」与逐条原因，分号转全角便于阅读） */
export function normalizeErrorText(content) {
  return toText(content)
    .split(';')
    .map((item) => item.trim())
    .filter(Boolean)
    .join('；')
    .replace(/；+/g, '；')
}

/**
 * @param {import('vue').Ref<object|null>} topicRef 当前主题（服务端记录，含 recID）
 * @param {{ onSaved?: (record: object) => void, idleDelay?: number }} [options]
 */
export function useTopicDraft(topicRef, options = {}) {
  const { onSaved, idleDelay = IDLE_AUTOSAVE_MS } = options

  const form = reactive(topicToDraft(null))
  const baseline = ref(topicToDraft(null))
  const fieldErrors = reactive({})
  const saving = ref(false)
  const savedAt = ref('')
  let idleTimer = null

  /** 当前草稿的规范化取值（用于与基线比对 / 组装 payload） */
  function currentValues() {
    return {
      title: form.title.trim(),
      summary: form.summary.trim(),
      description: form.description,
      author: form.author.trim(),
      location: form.location.trim(),
      source: form.source.trim(),
      period: form.period.trim(),
      tagList: form.tagList.map((item) => item.trim()).filter(Boolean),
      categoryCode: form.categoryCode.trim(),
      aiFlag: toText(form.aiFlag) === '1' ? '1' : '0'
    }
  }

  /**
   * 差量：仅返回「与基线不同且非空」的内容字段。
   * ★ 不含 status / publishStatus / coverFileID（封面由 Tab2 的显式动作同步）。
   * ★ 空值跳过（裁定 G）：清空标题/简介/标签时后端无法置空，前端不伪装成成功。
   */
  function buildDiff() {
    const now = currentValues()
    const base = baseline.value
    const payload = {}

    const title = now.title
    if (title && title !== base.title) payload.title = title

    const summary = now.summary
    if (summary && summary !== base.summary) payload.summary = summary

    if (now.description && now.description !== base.description) payload.description = now.description

    for (const key of ['author', 'location', 'source', 'period', 'categoryCode']) {
      const value = now[key]
      if (value && value !== base[key]) payload[key] = value
    }

    const tagList = now.tagList.join(TAG_SEPARATOR)
    if (tagList && tagList !== base.tagList.join(TAG_SEPARATOR)) payload.tagList = tagList

    if (now.aiFlag !== base.aiFlag) payload.aiFlag = now.aiFlag

    return payload
  }

  const diff = computed(() => buildDiff())
  const dirty = computed(() => Object.keys(diff.value).length > 0)

  /** 字数：详述用后端口径 wordCount（CJK 按字符 + 英文按词），其余用 charCount */
  const descriptionWords = computed(() => countWords(form.description))
  const titleChars = computed(() => charCount(form.title))
  const summaryChars = computed(() => charCount(form.summary))

  function clearErrors() {
    for (const key of Object.keys(fieldErrors)) delete fieldErrors[key]
  }

  /** 服务端字段级错误 → 行内回显；返回命中的字段名（未命中返回空串） */
  function applyServerError(error) {
    const code = toText(error?.errCode)
    if (!FIELD_ERROR_CODES.includes(code)) return ''
    const message = normalizeErrorText(error?.MSG?.content || '')
    if (!message) return ''
    const field = matchErrorField(message)
    if (!field) return ''
    fieldErrors[field] = message
    return field
  }

  /** 以服务端记录刷新基线（并回填详述前缀与 descriptionFileID 等，裁定 H） */
  function syncFromServer(record) {
    if (!record || typeof record !== 'object') return
    const next = topicToDraft(record)
    baseline.value = next
    // ★ 只在服务端确实返回了该字段时回填，避免把未参与本次修改的字段清空
    for (const key of DRAFT_FIELDS) {
      if (record[key] === undefined) continue
      if (key === 'tagList') {
        form.tagList = Array.isArray(next.tagList) ? [...next.tagList] : []
        continue
      }
      form[key] = next[key]
    }
  }

  function resetIdleTimer() {
    if (idleTimer) clearTimeout(idleTimer)
    idleTimer = setTimeout(() => {
      if (dirty.value) save({ silent: true })
    }, idleDelay)
  }

  function stopIdleTimer() {
    if (idleTimer) clearTimeout(idleTimer)
    idleTimer = null
  }

  /**
   * 保存差量。
   * @param {{ silent?: boolean }} [opts] silent=true 为自动保存（不弹成功 toast，不打断输入）
   * @returns {Promise<boolean>} 是否成功（无差量视为成功）
   */
  async function save(opts = {}) {
    const { silent = false } = opts
    if (saving.value) return false

    const payload = buildDiff()
    const recID = toText(topicRef.value?.recID)
    if (!payload || Object.keys(payload).length === 0) return true
    if (!recID) return false

    clearErrors()
    saving.value = true
    try {
      // ★ payload 只含内容字段：无 status / publishStatus（裁定 D）
      const res = await topicModify({ recID, ...payload })
      const record = res?.data?.data || res?.data || {}
      syncFromServer(record)
      savedAt.value = formatYMDHMS(new Date(), 'HH:mm:ss')
      if (typeof onSaved === 'function') onSaved(record)
      if (!silent) toast.success(`已保存 ${savedAt.value}`)
      return true
    } catch (error) {
      // 失败不清空输入（§2.5 第 3 条）：非 B0 已由 http.js 统一 toast MSG.content
      applyServerError(error)
      console.error('[useTopicDraft] 保存主题失败', error)
      return false
    } finally {
      saving.value = false
      stopIdleTimer()
      if (dirty.value) resetIdleTimer()
    }
  }

  /** 有变更才保存（切 Tab / 离开页面用） */
  function saveIfDirty() {
    return dirty.value ? save({ silent: true }) : Promise.resolve(true)
  }

  /** 主题切换时重置草稿（★ 只在 recID 变化时调用，切 Tab 不触发） */
  function reset(topic) {
    const next = topicToDraft(topic)
    for (const key of DRAFT_FIELDS) {
      form[key] = key === 'tagList' ? [...next.tagList] : next[key]
    }
    baseline.value = next
    clearErrors()
    savedAt.value = ''
    stopIdleTimer()
  }

  watch(
    form,
    () => {
      if (dirty.value) resetIdleTimer()
    },
    { deep: true }
  )

  onBeforeUnmount(stopIdleTimer)

  return {
    form,
    fieldErrors,
    saving,
    savedAt,
    dirty,
    diff,
    buildDiff,
    titleChars,
    summaryChars,
    descriptionWords,
    save,
    saveIfDirty,
    applyServerError,
    clearErrors,
    syncFromServer,
    reset
  }
}

export default useTopicDraft
