<!-- ============================================================================
 * TopicEdit · 主题详情外壳（P-03 / Step 7）
 * ----------------------------------------------------------------------------
 * 职责：标题栏（返回 + 标题 + StateBadge + [保存][提交渲染]）+ 页内 5 Tab 编排 + 取数 +
 *   附图动作 + 提交渲染编排（单文件 ≤600 行，§2.1；字段差量计算抽到 useTopicDraft.js，见裁定 K）。
 * ★ 页内 Tab 非独立路由：切换只改 `?tab=`（router.replace），**不整页刷新、不重复请求主题详情**
 *   （详情只在 `topicCode` / `recID` 变化时重取，裁定 I）。
 * ★ 草稿与附图状态都提升到本层，Tab 组件只做展示与事件上报 → 切 Tab 不丢未保存内容。
 * 保存双轨（计划要点 4）：
 *   自动保存 = 切 Tab / 离开页面（onBeforeRouteLeave）/ 30s 无操作 → `topicmodify` **只提交内容差量**；
 *   显式保存 = 右上角「保存」或 Ctrl/Cmd+S → 成功 toast + 「已保存 HH:mm:ss」。
 *   ★ 自动保存绝不提交 `status` / `publishStatus`（裁定 D：状态跃迁只允许出现在显式动作中）。
 * 提交渲染（计划要点 6 + 裁定 E）：仅 `DRAFT` / `RENDERED` 可跃迁到 `RENDERING`
 *   （依据 processor/topicService.py:116-122 的状态机；PUBLISHED / ARCHIVED 下后端会返回 C7，
 *   计划正文未写明，此处按后端事实实现并在按钮 Tooltip 中说明原因）。
 *   ★ Step 9 起：`topic.layoutCode` 的**写入口在 Tab3**（`topicmodify`，裁定 A）；
 *     本层只读服务端返回值判定「版式已选」，并与 Tab3 **共用** `useRenderTrigger` +
 *     `RenderTriggerDialog`（裁定 F：全页唯一弹窗，页级唯一 primary 仍是本层按钮）。
 * 待确认项（登记）：Tab「产物」的条数徽章需 `artifactqry`（Step 12 / P-07 的接口），
 *   本步接口清单未含该端点，故**不显示产物徽章**，不用 mock 独有字段 `artifactCount` 冒充。
 *
 * ★ Step 13 最小修复（越界登记）：消费 `?focus=` 的时机从「仅在已挂载且 tab=content 时」扩展为
 *   「首次取数完成后补一次 + tab 变化时补一次」，并支持 `focus=assetList[N]` 高亮第 N 张素材卡片
 *   （P-09「去修正」的落点）。仅本文件改动，未改 TabContent / TabAssets 的对外接口。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-lg">
    <header class="flex flex-wrap items-center gap-md">
      <AppButton size="sm" type="ghost" icon="fa fa-arrow-left" @click="goBack">返回</AppButton>

      <h1 class="min-w-0 flex-1 truncate text-h1 text-ch-text-primary" :title="headerTitle">
        {{ headerTitle }}
      </h1>

      <div class="flex flex-wrap items-center gap-md">
        <StateBadge v-if="topic" domain="topic" :status="topic.status" />
        <span v-if="topic?.topicCode" class="font-mono text-code text-ch-text-tertiary">{{ topic.topicCode }}</span>
        <span v-if="draftSavedAt" class="text-caption text-ch-text-tertiary">已保存 {{ draftSavedAt }}</span>
        <AppButton icon="fa fa-floppy-disk" :loading="draftSaving" @click="saveNow">保存</AppButton>
        <AppButton
          type="primary"
          icon="fa fa-paper-plane"
          :disabled="!canSubmitRender"
          :disabled-reason="renderBlockReason"
          :loading="renderSubmitting"
          @click="submitRender"
        >
          提交渲染
        </AppButton>
      </div>
    </header>

    <ErrorState
      v-if="loadError"
      :message="loadError"
      hint="主题详情读取失败，请检查网络或稍后重试；若持续失败请联系管理员。"
      @retry="loadTopic()"
    />

    <Skeleton v-else-if="loading && !topic" type="detail" :rows="6" label="主题加载中" />

    <AppTabs
      v-else
      v-model="activeTab"
      variant="line"
      :items="tabItems"
      aria-label="主题编辑分区"
      @change="onTabChange"
    >
      <template v-if="activeTab === 'content'">
        <TabContent
          ref="tabContentRef"
          :form="draft.form"
          :field-errors="draft.fieldErrors"
          :words="descriptionWords"
          :cover-url="topic?.coverUrl || ''"
          :cover-file-id="topic?.coverFileID || ''"
          :description-file-id="topic?.descriptionFileID || ''"
          :description-url="topic?.descriptionUrl || ''"
          :asset-count="assets.length"
          :layout-code="topic?.layoutCode || ''"
        />
      </template>

      <TabAssets
        v-else-if="activeTab === 'assets'"
        ref="tabAssetsRef"
        :assets="assets"
        :loading="assetsLoading"
        :cover-file-id="topic?.coverFileID || ''"
        @refresh="loadAssets()"
        @reorder="onReorder"
        @caption="onCaption"
        @cover="onSetCover"
        @remove="onRemoveAsset"
        @add="onAddAssets"
      />

      <!-- Tab3 版式与平台（Step 9）：附图与顺序保存**共用本层状态**与同一个 onReorder（裁定 G） -->
      <TabLayout
        v-else-if="activeTab === 'layout'"
        :topic="topic"
        :assets="assets"
        :layouts="layoutCatalog"
        :platforms="platformCatalog"
        :catalog-loading="catalogLoading"
        :catalog-error="catalogError"
        :render-disabled="!canSubmitRender"
        :render-block-reason="renderBlockReason"
        :layout-saving="layoutSaving"
        :layout-saved-at="layoutSavedAt"
        @select-layout="selectLayoutCode"
        @reorder="onReorder"
        @open-render="submitRender"
        @refresh-catalog="ensureCatalog(true)"
      />
      <!-- Tab4 产物（Step 12）：外壳传入主题记录 → Tab 内固定 `topicID = ch_topic.recID` -->
      <TabArtifacts v-else-if="activeTab === 'artifacts'" :topic="topic" />
      <TabPublish v-else />
    </AppTabs>

    <!--
      ★ 全页唯一的渲染弹窗（裁定 F）：外壳右上角「提交渲染」与 Tab3「发起渲染」都调用 submitRender(),
      submitRender() 只负责 openRenderDialog() —— 因此不存在两套校验、两个弹窗。
    -->
    <RenderTriggerDialog
      v-model="renderDialogVisible"
      :layout-code="selectedLayoutCode"
      :layout-name="selectedLayout?.layoutName || ''"
      :layout-spec="selectedLayout?.spec || {}"
      :platform-code="selectedPlatform?.platformCode || selectedLayout?.platform || ''"
      :assets="assets"
      :checks="renderChecks"
      :blocked-reason="renderBlockReason"
      :submitting="renderSubmitting"
      :catalog-error="catalogError"
      @submit="submitRenderAction"
    />
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { toast } from 'vue3-toastify'
import AppButton from '@/components/base/AppButton.vue'
import AppTabs from '@/components/base/AppTabs.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import Skeleton from '@/components/base/Skeleton.vue'
import StateBadge from '@/components/biz/StateBadge.vue'
import TabArtifacts from '@/views/topic/TabArtifacts.vue'
import TabAssets from '@/views/topic/TabAssets.vue'
import TabContent from '@/views/topic/TabContent.vue'
import TabLayout from '@/views/topic/TabLayout.vue'
import TabPublish from '@/views/topic/TabPublish.vue'
import RenderTriggerDialog from '@/views/topic/RenderTriggerDialog.vue'
import { useTopicDraft } from '@/views/topic/useTopicDraft'
import { useRenderTrigger } from '@/views/topic/useRenderTrigger'
import { topicAssetAdd, topicAssetDel, topicAssetModify, topicAssetQry } from '@/api/asset'
import { topicQry, topicModify } from '@/api/topic'

/** 页内 Tab（键写入 `?tab=`；`/topics/:code?tab=content&focus=description`） */
const TAB_KEYS = ['content', 'assets', 'layout', 'artifacts', 'publish']
/** 仅这两个状态可跃迁到 RENDERING（topicService.TOPIC_STATUS_TRANSITIONS:116-122） */
const RENDERABLE_STATUS = ['DRAFT', 'RENDERED']

const route = useRoute()
const router = useRouter()

const readTab = (value) => {
  const key = String(value || '')
  return TAB_KEYS.includes(key) ? key : 'content'
}

const activeTab = ref(readTab(route.query.tab))
const topic = ref(null)
const assets = ref([])
const loading = ref(false)
const assetsLoading = ref(false)
const loadError = ref('')
const tabContentRef = ref(null)
const tabAssetsRef = ref(null)

/* ---------------- 草稿（内容字段） ---------------- */
const draft = useTopicDraft(topic, {
  onSaved: (record) => {
    topic.value = { ...(topic.value || {}), ...record }
  }
})
// 顶层解构，保证模板中按 ref 自动解包（嵌套对象的 ref 在模板里不会自动解包）
const draftSaving = draft.saving
const draftSavedAt = draft.savedAt

const tabItems = computed(() => [
  { key: 'content', label: '内容' },
  { key: 'assets', label: '素材', badge: assets.value.length || 0 },
  { key: 'layout', label: '版式与平台' },
  { key: 'artifacts', label: '产物' },
  { key: 'publish', label: '投递' }
])

const headerTitle = computed(() => draft.form.title || topic.value?.title || '（无标题）')

/** 详述字数：已转存文件时以服务端 `wordCount`（全文口径）为准，否则用草稿实时字数（裁定 H） */
const descriptionWords = computed(() => {
  if (topic.value?.descriptionFileID) return Number(topic.value.wordCount) || draft.descriptionWords.value
  return draft.descriptionWords.value
})

/* ---------------- 取数 ---------------- */
async function fetchTopicRecord(code) {
  const first = await topicQry({ topicCode: code })
  const list = Array.isArray(first?.data) ? first.data : []
  if (list.length) return list[0]
  const second = await topicQry({ recID: code })
  const fallback = Array.isArray(second?.data) ? second.data : []
  return fallback[0] || null
}

async function loadTopic() {
  loading.value = true
  loadError.value = ''
  try {
    const record = await fetchTopicRecord(String(route.params.code || ''))
    if (!record) {
      loadError.value = '未查询到该主题（topicCode / recID 均未命中）'
      topic.value = null
      return
    }
    topic.value = record
    draft.reset(record)
    await loadAssets()
  } catch (e) {
    loadError.value = e?.MSG?.content || '主题详情读取失败'
    console.error('[TopicEdit] 主题详情读取失败', e)
  } finally {
    loading.value = false
    // ★ Step 13 最小修复：深链/跳入时补一次 `?focus=` 消费（TabContent 需在取数完成、骨架屏退场后才挂载）
    applyRouteFocus()
  }
}

async function loadAssets() {
  const recID = topic.value?.recID
  if (!recID) {
    assets.value = []
    return
  }
  assetsLoading.value = true
  try {
    // ★ topicID 一律传 ch_topic.recID（裁定 A）
    const res = await topicAssetQry({ topicID: String(recID) })
    assets.value = Array.isArray(res?.data) ? res.data : []
  } catch (e) {
    console.error('[TopicEdit] 附图读取失败', e)
  } finally {
    assetsLoading.value = false
  }
}

/** 详情只在 code 变化时重取（裁定 I） */
watch(() => route.params.code, () => loadTopic(), { immediate: true })

/* ---------------- Tab 切换与字段定位 ---------------- */
function onTabChange(key) {
  draft.saveIfDirty() // 自动保存：切 Tab
  const query = { ...route.query, tab: key }
  delete query.focus
  router.replace({ path: route.path, query })
}

/* ---------------- `?focus=` 消费（★ Step 13 最小修复，已在产出说明登记） ----------------
 * 背景（Step 13 裁定 D）：P-09 的「去修正」跳 `/topics/:code?tab={content|assets|layout|artifacts}&focus=…`。
 * 本层原先只在「已挂载 + tab=content」时响应 `route.query.focus` 的**变化**，
 * 而「从合规校验页跳入」属于**新挂载**（watcher 无 immediate）→ 焦点不会落下，验收项 3 无法通过。
 * 最小修复范围（仅本文件；**未改** TabContent / TabAssets 的对外接口与模板）：
 *   1) 首次取数完成后补一次 `applyRouteFocus()`；
 *   2) `tab=assets` 且 `focus=assetList[N]` 时高亮第 N 张素材卡片（0 基下标，UI 文案「第 N+1 张」）。
 * 说明：素材卡片高亮走 `tabAssetsRef.$el` 的 DOM 形变（临时描边 + 临时 tabindex），
 *       属 **Step 13 未获授权修改 TabAssets** 前提下的收敛做法，已登记为待确认项。
 * ---------------------------------------------------------------------------- */
function clearFocusQuery() {
  const query = { ...route.query }
  delete query.focus
  router.replace({ path: route.path, query })
}

/** 高亮第 index 张素材卡片（0 基）：滚动到视口 + 临时描边 + 临时可聚焦（不只靠颜色表达） */
function highlightAssetAt(index) {
  const root = tabAssetsRef.value?.$el
  if (!root || !Number.isInteger(index) || index < 0) return false
  const target = root.querySelectorAll('li')[index]
  if (!target) return false
  target.scrollIntoView({ block: 'center', behavior: 'smooth' })
  target.classList.add('ring-2', 'ring-ch-primary')
  target.setAttribute('tabindex', '-1')
  target.focus({ preventScroll: true })
  window.setTimeout(() => {
    target.classList.remove('ring-2', 'ring-ch-primary')
    target.removeAttribute('tabindex')
  }, 4000)
  return true
}

/** 消费 `?focus=`：content → `TabContent.focusField(key)`；assets → 高亮 `assetList[N]`；其余忽略 */
function applyRouteFocus() {
  const field = String(route.query.focus || '')
  if (!field) return
  const tab = readTab(route.query.tab)
  if (tab === 'content') {
    if (activeTab.value !== 'content') activeTab.value = 'content'
    nextTick(() => {
      if (tabContentRef.value?.focusField(field)) clearFocusQuery()
    })
    return
  }
  if (tab === 'assets') {
    const matched = /^assetList\[(\d+)\]$/.exec(field)
    if (!matched) return
    if (activeTab.value !== 'assets') activeTab.value = 'assets'
    nextTick(() => {
      if (highlightAssetAt(Number(matched[1]))) clearFocusQuery()
    })
  }
}

watch(
  () => route.query.tab,
  (value) => {
    const next = readTab(value)
    if (next !== activeTab.value) activeTab.value = next
    applyRouteFocus()
  }
)

watch(() => route.query.focus, () => applyRouteFocus())

function focusFirstErrorField() {
  const key = Object.keys(draft.fieldErrors)[0]
  if (!key) return
  if (activeTab.value !== 'content') {
    activeTab.value = 'content'
    router.replace({ path: route.path, query: { ...route.query, tab: 'content' } })
  }
  nextTick(() => tabContentRef.value?.focusField(key))
}

/* ---------------- 保存（显式 / 自动） ---------------- */
async function saveNow() {
  const ok = await draft.save({})
  if (!ok) focusFirstErrorField()
}

function onKeydown(event) {
  if (!(event.ctrlKey || event.metaKey) || event.altKey) return
  const key = String(event.key || '').toLowerCase()
  if (key === 's' || event.key === 'Enter') {
    event.preventDefault()
    saveNow()
  }
}

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push({ name: 'Topics' })
}

/* ---------------- 附图：排序 / 图注 / 封面 / 解绑 / 添加 ---------------- */
function assetLocator(item) {
  // 裁定 B：modify / del 同时带 topicID + recID（并附 assetKey 供后端按幂等键定位）
  return {
    topicID: String(topic.value?.recID || ''),
    recID: String(item?.recID || ''),
    assetKey: String(item?.assetKey || '')
  }
}

async function onReorder(ordered) {
  if (!topic.value?.recID || !Array.isArray(ordered) || !ordered.length) return
  const before = ordered.map((item) => `${item.recID}:${item.sortOrder}`).join(' | ')
  assets.value = [...ordered] // 乐观更新，失败再以服务端顺序拉回
  const orderList = ordered.map((item, index) => ({ recID: String(item.recID), sortOrder: index + 1 }))
  console.info('[TopicEdit] orderList 提交', { before, orderList })
  try {
    await topicAssetModify({ ...assetLocator(ordered[0]), orderList })
  } catch (e) {
    console.error('[TopicEdit] 附图排序失败', e)
  }
  await loadAssets()
}

async function onCaption(item, caption) {
  const next = String(caption || '').trim()
  if (next === String(item.caption || '').trim()) return
  if (!next) {
    // 裁定 G：后端「非空才写入」，无法用空值清空图注，前端不伪装成成功
    toast.warning('图注不能为空（服务端无法用空值清空字段）')
    return
  }
  try {
    await topicAssetModify({ ...assetLocator(item), caption: next })
    await loadAssets()
  } catch (e) {
    console.error('[TopicEdit] 图注保存失败', e)
  }
}

/**
 * 设为封面（裁定 C：不自造降级逻辑）
 * 1) `topicassetadd(usageType='cover')` → 服务端把旧封面降级为 body；
 * 2) 重新拉取 `topicassetqry`；
 * 3) 用被设封面项的 `fileID` 调 `topicmodify` 同步 `coverFileID`（存的是 fileID）。
 */
async function onSetCover(item) {
  if (!topic.value?.recID) return
  try {
    await topicAssetAdd({
      topicID: String(topic.value.recID),
      fileID: String(item.fileID),
      caption: item.caption || '',
      usageType: 'cover',
      sortOrder: Number(item.sortOrder) || 1
    })
    await loadAssets()
    const fresh = assets.value.find((row) => String(row.fileID) === String(item.fileID)) || item
    await topicModify({ recID: String(topic.value.recID), coverFileID: String(fresh.fileID) })
    topic.value = { ...topic.value, coverFileID: String(fresh.fileID), coverUrl: fresh.imageUrl || topic.value.coverUrl }
    await loadAssets()
    toast.success('已设为封面（原封面已由服务端降级为正文图）')
  } catch (e) {
    console.error('[TopicEdit] 设置封面失败', e)
    await loadAssets()
  }
}

async function onRemoveAsset(item) {
  try {
    await topicAssetDel({ ...assetLocator(item) })
    await loadAssets()
    toast.success('已解除引用，素材仍保留在图库中')
  } catch (e) {
    console.error('[TopicEdit] 解除附图引用失败', e)
  }
}

async function onAddAssets(fileIds) {
  const recID = String(topic.value?.recID || '')
  if (!recID || !Array.isArray(fileIds) || !fileIds.length) return
  let success = 0
  const failed = []
  for (let index = 0; index < fileIds.length; index += 1) {
    try {
      await topicAssetAdd({
        topicID: recID,
        fileID: String(fileIds[index]),
        usageType: 'body',
        sortOrder: assets.value.length + index + 1
      })
      success += 1
    } catch (e) {
      failed.push(e?.MSG?.content || '绑定失败')
    }
  }
  tabAssetsRef.value?.resetPicker()
  await loadAssets()
  if (failed.length) toast.warning(`已绑定 ${success} 张，失败 ${failed.length} 张：${failed[0]}`)
  else toast.success(`已绑定 ${success} 张素材`)
}

/* ---------------- 提交渲染（外壳与 Tab3 共用同一弹窗 / 同一套校验，裁定 F） ---------------- */
/**
 * 目录 / 版式落库 / 前置校验 / 发起渲染全部收敛到 `useRenderTrigger`：
 * 本层只提供「主题 + 附图 + 详述字数」三个数据入口与「差量落库 / 字段行内回显」两个回调，
 * 因此外壳的 primary 按钮与 Tab3 的 secondary 按钮必然是同一个动作、同一个弹窗。
 */
const {
  layouts: layoutCatalog,
  platforms: platformCatalog,
  catalogLoading,
  catalogError,
  dialogVisible: renderDialogVisible,
  submitting: renderSubmitting,
  layoutSaving,
  layoutSavedAt,
  layoutCode: selectedLayoutCode,
  layout: selectedLayout,
  platform: selectedPlatform,
  checks: renderChecks,
  blockedReason: renderCheckBlockReason,
  canRender: renderChecksPassed,
  ensureCatalog,
  selectLayoutCode,
  openDialog: openRenderDialog,
  submit: submitRenderAction
} = useRenderTrigger({
  getTopic: () => topic.value,
  getAssets: () => assets.value,
  getWords: () => descriptionWords.value,
  // 提交前先落库草稿差量（不含 status）；失败则中止并定位到首个错误字段
  beforeSubmit: () => draft.saveIfDirty(),
  onTopicPatch: (patch) => {
    topic.value = { ...(topic.value || {}), ...patch }
  },
  // C4/C6（无正文/字数不足）→ 复用 Step 7 的字段行内回显，保持弹窗打开、不清空用户输入
  onFieldError: (error) => {
    const field = draft.applyServerError(error)
    if (field) focusFirstErrorField()
    return field
  }
})

const status = computed(() => String(topic.value?.status || ''))

/** 状态机原因（Step 7 口径，依据 processor/topicService.py 的 TOPIC_STATUS_TRANSITIONS） */
const statusBlockReason = computed(() => {
  if (!topic.value) return '主题尚未加载完成'
  if (RENDERABLE_STATUS.includes(status.value)) return ''
  if (status.value === 'RENDERING') return '渲染中：请等待任务完成后再提交'
  if (status.value === 'PUBLISHED') return '已投递：状态机不允许 PUBLISHED → RENDERING（后端返回 C7）'
  if (status.value === 'ARCHIVED') return '已归档：终态不可再渲染（后端返回 C7）'
  return `当前状态 ${status.value} 不允许提交渲染`
})

/** 可用性 = 状态机放行 ∩ 校验清单全通过（清单见 useRenderTrigger.buildRenderChecks） */
const canSubmitRender = computed(() => !statusBlockReason.value && renderChecksPassed.value)
const renderBlockReason = computed(() => statusBlockReason.value || renderCheckBlockReason.value)

/** 两个入口都只做「打开同一个弹窗」；真正的校验在弹窗内展示、在提交时复用同一套判定 */
function submitRender() {
  if (!canSubmitRender.value) {
    toast.warning(renderBlockReason.value)
    return
  }
  openRenderDialog()
}

/**
 * 进入 Tab3 时预取版式 / 平台目录（免登录端点；空响应降级为 EmptyState，附录 B R-24）。
 * ★ `immediate: true` 必须有：直接深链 `/topics/:code?tab=layout` 时 `activeTab` 在 setup 阶段
 *   即为 'layout'，无 immediate 的 watcher 不会触发 → 卡片区恒为空。
 */
watch(activeTab, (key) => {
  if (key === 'layout') ensureCatalog()
}, { immediate: true })

/* ---------------- 生命周期 ---------------- */
onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))

/** 离开页面：有变更则静默保存内容差量（不含 status） */
onBeforeRouteLeave(async () => {
  await draft.saveIfDirty()
  return true
})
</script>
