<!-- ============================================================================
 * TabPublish · P-03 Tab5「投递」（Step 14 原地替换 Step 7 占位）
 * ----------------------------------------------------------------------------
 * 组成：
 *   ① 顶部：该主题的合规校验摘要 +「去校验」入口（由 `DeliverPanel` 的合规摘要条承载，避免两套口径）；
 *   ② `DeliverPanel`：复用投递面板（本 Tab **固定主题**，`topicID = ch_topic.recID`，裁定 A）；
 *   ③ `PublishRecordTable`：内嵌该主题的记录子集（固定 `topicID`，**不写 URL query**，避免污染 `?tab=`，
 *      与 Step 12 Tab4 同款口径）；
 *   ④ 成功后同一撤销倒计时条（与 P-10 同一组件、同一绝对时间重算口径）。
 *
 * ★ 主题记录由本组件按路由 `:code` 自行取（`topicqry` 的 `topicCode` → 回退 `recID`）；
 *   ★ 未修改外壳 `TopicEdit.vue`（其 `<TabPublish v-else />` 不传 props，本步不改外壳）。
 * ★ 不得引入任何小红书自动发布 / 投递入口（本期小红书只导出素材包）。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-2xl">
    <header class="flex flex-wrap items-center justify-between gap-md">
      <div class="flex min-w-0 flex-col gap-xs">
        <h2 class="text-h2 text-ch-text-primary">投递</h2>
        <p class="flex flex-wrap items-center gap-sm text-body-s text-ch-text-secondary">
          <span class="min-w-0 truncate" :title="topic?.title || ''">{{ topic?.title || '主题加载中…' }}</span>
          <span v-if="topic?.topicCode" class="font-mono text-code text-ch-text-tertiary">{{ topic.topicCode }}</span>
          <StateBadge v-if="topic" domain="topic" :status="topic.status" />
        </p>
        <p class="text-caption text-ch-text-tertiary">
          交付方式：微信公众号 → 草稿投递（draft_box，二次确认 + 撤销窗）；小红书 / 通用 → 素材包 ZIP（只导出）。
          ★ 本页不提供「自动发布」开关，也不提供小红书发布入口。
        </p>
      </div>

      <RouterLink
        v-if="topic?.topicCode"
        :to="{ name: 'Compliance', params: { code: topic.topicCode } }"
        class="text-body-s text-ch-primary hover:text-ch-primary-hover"
      >
        <i class="fa fa-shield-halved mr-xs" aria-hidden="true"></i>去合规校验
      </RouterLink>
    </header>

    <ErrorState
      v-if="loadError"
      :message="loadError"
      hint="主题读取失败，请检查网络或稍后重试；若持续失败请核对主题是否存在。"
      @retry="loadTopic()"
    />

    <Skeleton v-else-if="loading && !topic" type="detail" :rows="5" label="投递面板加载中" />

    <template v-else-if="topic">
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
        撤销已成功：`ch_publish_record.delFlag` 置为 1。★ 记录列表默认过滤软删记录，刷新后该行可能不再出现
        （记录 ID {{ revokedNotice.recID }}）。
      </ConflictBanner>

      <DeliverPanel
        ref="panelRef"
        :topic="topic"
        @delivered="onDelivered"
        @records-changed="onRecordsChanged"
      />

      <article class="flex flex-col gap-lg">
        <h3 class="text-h3 text-ch-text-primary">本主题投递记录</h3>
        <PublishRecordTable
          ref="tableRef"
          :topic-id="String(topic.recID || '')"
          @retry="onRetry"
          @revoke="onRevoke"
        />
      </article>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { toast } from 'vue3-toastify'
import ConflictBanner from '@/components/base/ConflictBanner.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import Skeleton from '@/components/base/Skeleton.vue'
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

const topic = ref(null)
const loading = ref(false)
const loadError = ref('')
const countdownRecord = ref(null)
const revoking = ref(false)
const revokedNotice = ref(null)
const tableRef = ref(null)
const panelRef = ref(null)

const topicCode = computed(() => String(route.params.code || ''))

/** 与 `TopicEdit.fetchTopicRecord` 同口径：优先 `topicCode`，未命中回退 `recID` */
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
    const record = await fetchTopicRecord(topicCode.value)
    if (!record) {
      topic.value = null
      loadError.value = `未查询到该主题（${topicCode.value}）`
      return
    }
    topic.value = record
  } catch (error) {
    topic.value = null
    loadError.value = error?.MSG?.content || '主题读取失败'
    console.error('[P-03 Tab5] 主题读取失败', error)
  } finally {
    loading.value = false
  }
}

/** 撤销（与 P-10 同一链路与文案口径） */
async function onRevoke(record) {
  if (!record) return
  revoking.value = true
  try {
    const result = await revokePublishRecord({
      publishRecordID: record.publishRecordID || record.recID,
      idempotencyKey: record.idempotencyKey
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
    const recID = String(record.publishRecordID || record.recID || '')
    tableRef.value?.markRevoked(recID)
    revokedNotice.value = { recID, idempotencyKey: String(record.idempotencyKey || '') }
    await tableRef.value?.refresh()
    // ★ 撤销后配额释放 → 面板重算配额与合规状态
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

function onRecordsChanged() {
  tableRef.value?.refresh()
}

/** 重试：本 Tab 主题固定，直接预填产物（仍需用户点击按钮走二次确认） */
function onRetry(row) {
  panelRef.value?.retryFrom(row)
}

watch(topicCode, () => {
  countdownRecord.value = null
  revokedNotice.value = null
  loadTopic()
}, { immediate: true })

onMounted(() => {
  // ★ 刷新/深链后恢复撤销入口：按 pushedYMDHMS + windowSeconds 绝对时间重算
  const last = readLastDelivery()
  if (last && remainingRevokeSeconds(last) > 0) countdownRecord.value = last
})
</script>
