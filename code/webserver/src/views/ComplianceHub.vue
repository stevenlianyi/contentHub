<!-- ============================================================================
 * ComplianceHub · 合规校验中转列表（P-09 的一级导航落点，Step 6）
 * ----------------------------------------------------------------------------
 * ★ 路径唯一（Step 6 裁定 E）：一级导航「合规校验」指向 `/compliance-hub`
 *   （`components/base/AppSidebar.vue` 的 NAV_ITEMS 与 `router/index.js` 均已引用本文件），
 *   因此**只保留 `src/views/ComplianceHub.vue`**，禁止再建 `src/views/topics/ComplianceHub.vue`
 *   （同一职能出现两个路径会让导航与埋点口径分裂）。
 *
 * 职责：只做「选一个主题去校验」的中转——列：标题 / 状态 / 最近校验时间 / 操作「去校验」，
 *   点击进入 `/compliance/:topicCode`（P-09，由 Step 13 实现）。
 *
 * ★ 「最近校验时间」**无任何端点提供**（`publishcheck` 是即时校验、ch_topic 无该列、
 *   ch_audit_log 也未按主题聚合校验时间）→ 本期一律显示 `—（无数据源）`，
 *   严禁用 `modifyYMDHMS` 等其它时间字段冒充，也严禁伪造。已登记为待确认项。
 *
 * 四态齐备（裁定 H）：筛选（keyword）/ 加载（AppTable 骨架行）/ 空（EmptyState）/ 错（ErrorState）。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-lg">
    <header class="flex flex-wrap items-center justify-between gap-md">
      <div class="flex flex-col gap-xs">
        <h1 class="text-h1 text-ch-text-primary">合规校验</h1>
        <p class="text-body-s text-ch-text-secondary">选择一个主题，进入该主题的合规校验清单。</p>
      </div>
    </header>

    <div class="flex flex-wrap items-end gap-md rounded-xl border border-ch-border bg-ch-surface px-xl py-lg">
      <label class="flex min-w-[200px] flex-1 flex-col gap-xs">
        <span class="text-body-s text-ch-text-secondary">搜索标题</span>
        <input
          :value="keyword"
          type="search"
          class="h-9 w-full rounded-md border border-ch-border bg-ch-input px-md text-body text-ch-text-primary placeholder:text-ch-text-tertiary focus:border-ch-border-focus"
          placeholder="标题 / 编码"
          aria-label="搜索标题"
          :disabled="loading"
          @input="onKeyword"
        />
      </label>
    </div>

    <ErrorState
      v-if="error"
      :message="error"
      :detail="errorDetail"
      hint="主题列表读取失败，无法选择待校验主题，请稍后重试。"
      @retry="refresh()"
    />

    <template v-else>
      <AppTable
        :columns="COLUMNS"
        :rows="rows"
        :loading="loading"
        :skeleton-rows="8"
        row-key="recID"
        empty="暂无可校验的主题"
        empty-description="主题库为空时无法发起合规校验，请先在主题库创建主题。"
        empty-action-text="前往主题库"
        @empty-action="goTopics"
      >
        <template #cell-title="{ row }">
          <span class="block truncate text-body-s text-ch-text-primary" :title="row.title">{{ row.title }}</span>
        </template>
        <template #cell-status="{ row }">
          <StateBadge domain="topic" :status="row.status" />
        </template>
        <template #cell-lastCheck>
          <span class="text-body-s text-ch-text-tertiary" :title="LAST_CHECK_HINT">—（无数据源）</span>
        </template>
        <template #cell-actions="{ row }">
          <RouterLink
            :to="{ name: 'Compliance', params: { code: row.topicCode } }"
            class="text-body-s text-ch-primary hover:text-ch-primary-hover"
          >
            <i class="fa fa-shield-halved mr-xs" aria-hidden="true"></i>去校验
          </RouterLink>
        </template>
      </AppTable>

      <AppPagination
        :total="total"
        :page-size="size"
        :current-page="page"
        :disabled="loading"
        @page-change="onPageChange"
      />
    </template>
  </section>
</template>

<script setup>
import { onBeforeUnmount, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import AppPagination from '@/components/base/AppPagination.vue'
import AppTable from '@/components/base/AppTable.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import StateBadge from '@/components/biz/StateBadge.vue'
import { usePagination } from '@/components/base/composables/usePagination'
import { topicQry } from '@/api/topic'
import { generalNext } from '@/api/user'
import { debounce } from '@/utils/common'

/** 「最近校验时间」无数据源（见文件头）——用 Tooltip 说明原因，不用其它时间字段冒充 */
const LAST_CHECK_HINT = '平台未提供「最近校验时间」数据源（publishcheck 为即时校验，ch_topic 无该列），故一律显示无数据源。'

const COLUMNS = [
  { key: 'title', title: '标题', minWidth: 240 },
  { key: 'status', title: '状态', width: 96 },
  { key: 'lastCheck', title: '最近校验时间', width: 160 },
  { key: 'actions', title: '操作', width: 120 }
]

const router = useRouter()
const keyword = ref('')
const errorDetail = ref('')

async function requestTopics({ beginNum, endNum, indexKey }) {
  try {
    // 续取口径与 P-02 一致：仅当上一批响应带 indexKey（后端确有查询缓冲）时走 generalnext，
    // 否则始终用 topicqry(beginNum/endNum) —— 避免在无缓冲的实现上抛出「缓冲已失效」。
    const res = indexKey
      ? await generalNext({ indexKey, beginNum, endNum })
      : await topicQry({ order: 'modify', beginNum, endNum, keyword: keyword.value })
    errorDetail.value = ''
    return res
  } catch (e) {
    errorDetail.value = [e?.errCode ? `errCode: ${e.errCode}` : '', e?.MSG?.content || e?.message || '']
      .filter(Boolean)
      .join('\n')
    throw e
  }
}

const { page, size, total, rows, loading, error, goPage, changeSize, refresh, reset } = usePagination(
  requestTopics,
  { pageSize: 20 }
)

/** 关键词防抖 300ms：命中后端 `keyword`（title/summary/description 的 LIKE） */
const pushKeyword = debounce((value) => {
  keyword.value = value
  reset()
}, 300)

function onKeyword(event) {
  pushKeyword(event.target.value)
}

function onPageChange({ page: nextPage, size: nextSize }) {
  if (nextSize && nextSize !== size.value) changeSize(nextSize)
  if (nextPage !== page.value) goPage(nextPage)
}

function goTopics() {
  router.push('/topics')
}

onBeforeUnmount(() => pushKeyword.cancel())
</script>
