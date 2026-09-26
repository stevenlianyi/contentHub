<!-- ============================================================================
 * TabArtifacts · P-03 Tab4「产物」（Step 12 原地替换 Step 7 的占位实现）
 * ----------------------------------------------------------------------------
 * 组成：
 *   ① 顶部：该主题**最近一次渲染结果**（`renderjobqry({ topicID, order:'modify' })`）+「去渲染」入口；
 *   ② 列表主体：与 P-07 共用 `views/artifacts/ArtifactsPanel.vue`，固定 `topicID` 过滤、
 *      隐藏主题筛选控件、不写 URL query（避免污染 `?tab=`，裁定 B）。
 *
 * 后端事实（服从）：
 *   · `ch_artifact.topicID` = `ch_topic.recID`（表注释），故 `topicID` 一律传 `topic.recID`；
 *   · `renderjobqry` 的服务端过滤（`topicID / order`）由 2026-09-22 手改补充（附录 B R-28）；
 *     ★ `order='modify'` → `modifyYMDHMS DESC`；Mock 未实现该排序，故此处对返回批取「时间最大者」
 *       作为「最近一次」，真实后端即第一条（兼容两种实现，不做本地过滤）；
 *   · 无 `layoutCode` 时 `topicrender` 必填项缺失（C4）→ 「去渲染」统一引导到 Tab3 选版式。
 *
 * ★ 本 Tab 的「去渲染」为 **secondary**：页级唯一 primary 仍是外壳的「提交渲染」
 *   （与 Step 9 Tab3「发起渲染」同款口径，避免同屏两个 primary）。
 * ★ 不提供「立即清理 / 导出素材包」入口（清理归 `schedule/archive.py`；导出归 Step 14，裁定 D）。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-2xl">
    <!-- 顶部：最近一次渲染结果 + 去渲染入口 -->
    <div class="ch-card flex flex-wrap items-start justify-between gap-md">
      <div class="flex min-w-0 flex-col gap-sm">
        <h2 class="text-h3 text-ch-text-primary">产物</h2>

        <p v-if="latestLoading" class="text-body-s text-ch-text-secondary">最近一次渲染结果读取中…</p>

        <div v-else-if="latest" class="flex flex-wrap items-center gap-sm">
          <span class="text-body-s text-ch-text-secondary">最近一次渲染</span>
          <span class="font-mono text-code text-ch-text-primary">{{ latest.jobCode || latest.recID || '—' }}</span>
          <StateBadge domain="job" :status="latest.jobStatus" />
          <span v-if="latest.at" class="text-caption text-ch-text-tertiary">{{ latest.atText }}</span>
          <RouterLink
            :to="{ path: '/render-jobs', query: { jobID: latest.recID } }"
            class="text-body-s text-ch-primary hover:text-ch-primary-hover"
          >
            查看任务
          </RouterLink>
        </div>

        <p v-else class="text-body-s text-ch-text-secondary">
          该主题还没有渲染任务。
          <span v-if="latestError" class="text-ch-warning">（渲染任务读取失败：{{ latestError }}）</span>
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-md">
        <AppButton size="sm" icon="fa fa-rotate-right" :loading="latestLoading" @click="loadLatest">刷新</AppButton>
        <AppButton
          size="sm"
          icon="fa fa-paper-plane"
          :disabled="!topicID"
          :disabled-reason="'主题尚未加载完成'"
          @click="goRender"
        >
          去渲染
        </AppButton>
      </div>
    </div>

    <!-- 列表主体：固定 topicID，隐藏主题筛选，不写 URL query -->
    <ArtifactsPanel
      :topic-id="topicID"
      empty-icon="fa fa-file-lines"
      empty-title="该主题尚未渲染"
      empty-description="该主题还没有产物；先到「版式与平台」选择版式并提交渲染。"
      empty-action-text="去渲染"
      @empty-action="goRender"
    />
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import AppButton from '@/components/base/AppButton.vue'
import StateBadge from '@/components/biz/StateBadge.vue'
import ArtifactsPanel from '@/views/artifacts/ArtifactsPanel.vue'
import { renderJobQry } from '@/api/render'
import { formatYMDHMS } from '@/utils/common'

const props = defineProps({
  /** 主题记录（由外壳传入；`topicID` 取 `recID`，与 `ch_artifact.topicID` 同口径） */
  topic: { type: Object, default: null }
})

const route = useRoute()
const router = useRouter()

const str = (value) => (value === null || value === undefined ? '' : String(value))

const topicID = computed(() => str(props.topic?.recID))
const latest = ref(null)
const latestLoading = ref(false)
const latestError = ref('')

/**
 * 最近一次渲染结果：`renderjobqry({ topicID, order:'modify', beginNum:0, endNum:10 })`。
 * ★ `order:'modify'` 由后端按 `modifyYMDHMS DESC` 排序（附录 B R-28 / mysqlCommon:290-295）；
 *   为避免 Mock 未实现该排序导致误判，这里对返回批取**时间最大**的一条（不是本地筛选，
 *   只是「取最新一条」；真实后端取到的即第一条）。
 */
async function loadLatest() {
  if (!topicID.value) {
    latest.value = null
    return
  }
  latestLoading.value = true
  latestError.value = ''
  try {
    const res = await renderJobQry({ topicID: topicID.value, order: 'modify', beginNum: 0, endNum: 10 })
    const list = Array.isArray(res?.data) ? res.data : []
    const picked = list
      .map((row) => {
        const at = str(
          row?.modifyYMDHMS || row?.finishYMDHMS || row?.startYMDHMS || row?.finishedYMDHMS || row?.startedYMDHMS || row?.regYMDHMS
        )
        return {
          recID: str(row?.recID),
          jobCode: str(row?.jobCode),
          jobStatus: str(row?.jobStatus).toUpperCase(),
          at,
          atText: formatYMDHMS(at, 'MM-DD HH:mm')
        }
      })
      .sort((a, b) => b.at.localeCompare(a.at))[0]
    latest.value = picked || null
  } catch (err) {
    // 失败不遮挡产物列表：只在顶部提示（产物本身来自 artifactqry，互不影响）
    latest.value = null
    latestError.value = err?.MSG?.content || '渲染任务读取失败'
    console.error('[P-03 Tab4] renderjobqry 读取最近一次渲染结果失败', err)
  } finally {
    latestLoading.value = false
  }
}

/** 去渲染：跳到 Tab3（版式与平台）——那里有「发起渲染」入口（同一个外壳弹窗，裁定 F） */
function goRender() {
  router.replace({ path: route.path, query: { ...route.query, tab: 'layout' } })
}

watch(topicID, () => loadLatest(), { immediate: true })
</script>
