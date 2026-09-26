<!-- ============================================================================
 * PublishRecords · P-10 投递 / 发布记录（Step 14，原地替换 Step 7 占位页）
 * ----------------------------------------------------------------------------
 * 页面职责（只做页头 + 编排；投递逻辑在 `views/publish/usePublishFlow.js`，面板在
 * `views/publish/DeliverPanel.vue`，记录表在 `views/publish/PublishRecordTable.vue`）：
 *   ① 主题选择：`topicID` 一律取 `ch_topic.recID`（裁定 A：**禁止**把 `topicCode` 当 `topicID` 传）；
 *      并把 `topicCode` 写入 URL query（供「重试」深链与刷新保持）；
 *   ② 撤销倒计时条：投递成功后出现，窗口值以后端为准；★ 按 `pushedYMDHMS + windowSeconds`
 *      绝对时间重算，页面刷新后仍可恢复（不留痕则一刷新就没，属于「进入即 60」式假倒计时的反面）；
 *   ③ 双通道投递面板（微信草稿投递 + 素材包导出；★ 无任何小红书发布入口）；
 *   ④ 发布记录表（全部主题 + 服务端筛选 + 强制分页）。
 *
 * ★ 登记项：撤销后记录 `delFlag='1'`，而 `publishrecordqry` 默认过滤软删 → 刷新后该行可能不再返回；
 *   本页在撤销成功后先把该行本地标记「已撤销」，再刷新，并给出说明（见 `revokedNotice`）。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-lg">
    <header class="flex flex-col gap-xs">
      <h1 class="text-h1 text-ch-text-primary">投递 / 发布记录</h1>
      <p class="text-body-s text-ch-text-secondary">
        公众号**草稿投递**（强制二次确认 + 撤销窗）与小红书/通用素材包 ZIP 导出；发布记录可追溯（失败原因可展开）。
        ★ 本页不提供任何「自动发布」开关，也不提供小红书发布入口（平台红线）。
      </p>
    </header>

    <!-- ① 主题选择 -->
    <div class="flex flex-wrap items-end gap-md rounded-xl border border-ch-border bg-ch-surface px-xl py-lg">
      <label class="flex min-w-0 flex-col gap-xs">
        <span class="text-caption text-ch-text-secondary">主题（topicID 取 ch_topic.recID）</span>
        <select
          v-model="selectedTopicCode"
          class="h-9 max-w-[420px] rounded-lg border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
          aria-label="选择投递主题"
          :disabled="topicLoading"
          @change="onTopicChange"
        >
          <option v-if="!topics.length" value="">{{ topicLoading ? '主题加载中…' : '暂无可投递主题' }}</option>
          <option v-for="topic in topics" :key="topic.topicCode" :value="topic.topicCode">
            {{ topic.title }} · {{ topic.topicCode }}
          </option>
        </select>
      </label>

      <p v-if="selectedTopic" class="flex flex-wrap items-center gap-sm text-caption text-ch-text-tertiary">
        <span>recID：{{ selectedTopic.recID }}</span>
        <span>版式：{{ selectedTopic.layoutCode || '（未选择）' }}</span>
        <StateBadge domain="topic" :status="selectedTopic.status" />
      </p>
    </div>

    <!-- ② 撤销倒计时（成功后出现；按绝对时间重算） -->
    <RevokeCountdownBar
      v-if="countdownRecord"
      :record="countdownRecord"
      :revoking="revoking"
      @revoke="onRevoke"
      @expired="countdownRecord = null"
    />

    <ConflictBanner
      v-if="revokedNotice"
      type="info"
      title="该记录已撤销（软删）"
      closable
      @close="revokedNotice = null"
    >
      撤销已成功：`ch_publish_record.delFlag` 置为 1。★ `publishrecordqry` 与数据层一致地默认过滤软删记录
      （`delFlag='0' OR delFlag IS NULL`），因此刷新后该行可能不再出现在列表中（记录 ID
      {{ revokedNotice.recID }}，幂等键 {{ revokedNotice.idempotencyKey || '—' }}）。
    </ConflictBanner>

    <!-- ③ 双通道投递面板 -->
    <EmptyState
      v-if="!selectedTopic"
      icon="fa fa-paper-plane"
      title="请先选择主题"
      description="投递需要明确的主题（topicID 取 ch_topic.recID）与已选版式；请在上方选择主题后继续。"
    />
    <DeliverPanel
      v-else
      ref="panelRef"
      :topic="selectedTopic"
      @delivered="onDelivered"
      @records-changed="onRecordsChanged"
    />

    <!-- ④ 发布记录（全部主题） -->
    <article class="flex flex-col gap-lg">
      <h2 class="text-h2 text-ch-text-primary">发布记录</h2>
      <PublishRecordTable ref="tableRef" sync-query @retry="onRetry" @revoke="onRevoke" />
    </article>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toast } from 'vue3-toastify'
import ConflictBanner from '@/components/base/ConflictBanner.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import StateBadge from '@/components/biz/StateBadge.vue'
import DeliverPanel from '@/views/publish/DeliverPanel.vue'
import PublishRecordTable from '@/views/publish/PublishRecordTable.vue'
import RevokeCountdownBar from '@/views/publish/RevokeCountdownBar.vue'
import { topicQry } from '@/api/topic'
import {
  readLastDelivery,
  remainingRevokeSeconds,
  revokePublishRecord
} from '@/views/publish/usePublishFlow'

const route = useRoute()
const router = useRouter()

const topics = ref([])
const topicLoading = ref(false)
const selectedTopicCode = ref('')
const countdownRecord = ref(null)
const revoking = ref(false)
const revokedNotice = ref(null)
const tableRef = ref(null)
const panelRef = ref(null)

const selectedTopic = computed(
  () => topics.value.find((item) => String(item.topicCode) === selectedTopicCode.value) || null
)

/**
 * 主题列表（仅取列表字段；`?topicCode=` 深链优先；无参数时默认最近修改的一条）。
 * ★ 深链兜底：`?topicCode=` 指向的主题可能不在「最近修改 50 条」内（如记录表「重试」跳转的历史主题），
 *   此时补一次 `topicqry({ topicCode })` 并置顶，避免静默落到别的主题（否则投递/重试会张冠李戴）。
 */
async function loadTopics() {
  topicLoading.value = true
  try {
    const res = await topicQry({ order: 'modify', beginNum: 0, endNum: 50 })
    topics.value = Array.isArray(res?.data) ? res.data : []
    const fromQuery = String(route.query.topicCode || '')
    if (fromQuery && !topics.value.some((item) => String(item.topicCode) === fromQuery)) {
      const extra = await topicQry({ topicCode: fromQuery }, { silent: true }).catch((e) => e)
      const hit = Array.isArray(extra?.data) ? extra.data[0] : null
      if (hit) topics.value = [hit, ...topics.value]
    }
    const matched = topics.value.find((item) => String(item.topicCode) === fromQuery)
    selectedTopicCode.value = String((matched || topics.value[0] || {}).topicCode || '')
  } catch (error) {
    topics.value = []
    console.error('[P-10] 主题列表读取失败', error)
  } finally {
    topicLoading.value = false
  }
}

function onTopicChange() {
  // 切换主题：清理撤销入口与说明，并把 topicCode 写入 query（保持刷新/前进后退一致）
  countdownRecord.value = null
  revokedNotice.value = null
  router.replace({ path: route.path, query: { ...route.query, topicCode: selectedTopicCode.value || undefined } })
}

/** 撤销入口：成功后本地标记该行「已撤销」并刷新列表（刷新后若消失，见 `revokedNotice`） */
async function onRevoke(record) {
  if (!record) return
  const row = record
  revoking.value = true
  try {
    const result = await revokePublishRecord({
      publishRecordID: row.publishRecordID || row.recID,
      idempotencyKey: row.idempotencyKey
    })
    if (!result.ok) {
      toast.error(result.message)
      if (result.errCode === 'F5' || result.errCode === 'F1') {
        countdownRecord.value = null
        await tableRef.value?.refresh()
      }
      return
    }
    toast.success('已撤销本次草稿投递')
    countdownRecord.value = null
    const recID = String(row.publishRecordID || row.recID || '')
    tableRef.value?.markRevoked(recID)
    revokedNotice.value = { recID, idempotencyKey: String(row.idempotencyKey || '') }
    await tableRef.value?.refresh()
    // ★ 撤销后配额释放（配额 = 当日 success='1' 且未软删的条数）→ 面板重算配额与合规状态
    await panelRef.value?.loadAll()
  } finally {
    revoking.value = false
  }
}

function onDelivered(record) {
  countdownRecord.value = record
  revokedNotice.value = null
  tableRef.value?.refresh()
}

/** 记录表写操作 / 面板投递后刷新（列表与配额由面板内部刷新） */
function onRecordsChanged() {
  tableRef.value?.refresh()
}

/** 「重试」：把该记录所属主题切到当前选择，并把产物预填到面板（仍需用户点击按钮走二次确认） */
async function onRetry(row) {
  const topicID = String(row.topicID || '')
  const cached = tableRef.value?.topicRecordOf(topicID)
  const topicCode = cached?.topicCode || ''
  if (topicCode && topicCode !== selectedTopicCode.value) {
    selectedTopicCode.value = topicCode
    router.replace({ path: route.path, query: { ...route.query, topicCode } })
    await nextTick()
    // 面板的产物/合规在前置取数完成后才有值 → 先等一次取数，再预填产物
    await panelRef.value?.loadAll()
  }
  panelRef.value?.retryFrom(row)
}

onMounted(async () => {
  await loadTopics()
  // ★ 刷新后恢复撤销入口：按 pushedYMDHMS + windowSeconds 绝对时间重算，窗口已过则不显示
  const last = readLastDelivery()
  if (last && remainingRevokeSeconds(last) > 0) countdownRecord.value = last
})

/**
 * ★ `?topicCode=` 变化（**同路由 query 变化不触发重挂载**：如从记录表「重试」跳转 / 手工改地址）
 *   → 重新对齐选中主题；否则会出现「URL 已变、面板仍是上一个主题」的错位（本步实测发现并修复）。
 */
watch(
  () => route.query.topicCode,
  async (value) => {
    const next = String(value || '')
    if (!next || next === selectedTopicCode.value) return
    countdownRecord.value = null
    revokedNotice.value = null
    if (topics.value.some((item) => String(item.topicCode) === next)) {
      selectedTopicCode.value = next
      return
    }
    await loadTopics()
  }
)
</script>
