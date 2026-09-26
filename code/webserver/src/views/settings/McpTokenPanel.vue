<!-- ============================================================================
 * McpTokenPanel · P-13 设置页「MCP 令牌」（Step 17）
 * ----------------------------------------------------------------------------
 * 【数据来源（唯一）】`mcptokenqry`（`ch_mcp_token` CRUD 的 qry，需登录）。
 *   取数口径（裁定 C）：`mcpTokenQry({ mode:'full', order:'modify', beginNum, endNum }, { silent:true })`
 *   · ★ **必须 `mode:'full'`**：`CH_QUERY_SHORT_COLUMNS["ch_mcp_token"]` =
 *     `recID,tokenName,tokenScope,projectCode,revokedYMDHMS` —— **不含** `transport` /
 *     `lastUseYMDHMS` / `useCount` / `regYMDHMS`，用 short 会让整张表大面积显示「—」；
 *   · `order:'modify'` → `ORDER BY modifyYMDHMS DESC`（`mysqlCommon.queryTableGeneral` 三态之一）；
 *   · `silent: true` 由本组件自行渲染错误态（§2.5 第 5 条）。
 *
 * 【后端事实（服从，已核源码）】
 *   · 表列（`database/ch_mcp_token.txt`）= recID / **tokenHash CHAR(64) UNIQUE
 *     COMMENT『token的sha256 不存明文』** / tokenName / tokenScope（read|write|publish，默认 read）/
 *     projectCode / transport（sse|stdio，默认 sse）/ lastUseYMDHMS / useCount /
 *     revokedYMDHMS（有值即失效）/ ownerID / label / memo / regID / regYMDHMS / …
 *     → ★ **全表没有任何令牌明文**，故本组件**不提供**「复制令牌 / 显示令牌」入口；
 *   · 服务端筛选（附录 B R-28，2026-09-22 手改 `crudApi.py::funcMcptokenQry`）=
 *     `tokenHash` / `tokenName` / `tokenScope` / `projectCode` / `order`，**全部等值匹配**；
 *   · ★ 本区**不提供**筛选控件：裁定 C 的筛选为「可选」，而本步验收要求页面**不含任何表单控件**
 *     （输入框 / 文本域 / 下拉），故只保留服务端分页 + 排序，登记为已决事项。
 *
 * 【鉴权口径（裁定 C：必须精确，不得改写成「不参与鉴权」）】
 *   MCP 调用鉴权走**会话令牌（Redis session）+ 角色 / 工具级配置**
 *   （`main/subfunc/mcpApi.py::_resolveIdentity` 与 `mcpapi/mcpPost.py::CHTokenVerifier`
 *   都用 `comDB.getSessionInfo(token)`，再按 `ROLE_CMD_LIST` / `MCP_TOOL_LIST` 授权）；
 *   **没有任何鉴权路径去查 `ch_mcp_token`** → 该表是**登记台账**。
 *
 * 【只读】无编辑控件，且**不调用** `mcptokenadd` / `mcptokenmodify` / `mcptokendel`（裁定 E）。
 * 【硬约束】单文件 ≤ 600 行（§2.1）。
 * ========================================================================== -->
<template>
  <section class="ch-card flex flex-col gap-lg">
    <header class="flex flex-col gap-xs">
      <h2 class="text-h2 text-ch-text-primary">MCP 令牌</h2>
      <p class="text-body-s text-ch-text-secondary">
        本区为 ch_mcp_token 的只读登记台账：展示已登记令牌的名称、hash 前 8 位、范围、传输、状态、
        创建时间、最近使用、调用次数与创建者。本页不提供新建 / 编辑 / 吊销入口，
        也不提供「复制令牌 / 显示令牌」（表内只有 sha256，不存在明文）。
      </p>
    </header>

    <!-- ★ 鉴权说明（裁定 C：整句照抄，仅加粗强调，不得改写成「不参与鉴权」）
         ⚠️ 本句必须写成**单行**：行内标签之间一旦出现换行/缩进，Vue 的 whitespace 压缩会在
         文本节点之间补空格，渲染出的 textContent 就会与裁定 C 的原句不一致。 -->
    <ConflictBanner type="info" title="鉴权说明">
      <p>MCP 调用鉴权使用<strong>会话令牌（Redis session）+ 角色 / 工具级配置</strong>（<span class="font-mono text-code">ROLE_CMD_LIST</span> / <span class="font-mono text-code">MCP_TOOL_LIST</span>）；本表为<strong>登记台账</strong>，不参与鉴权。</p>
    </ConflictBanner>

    <!-- 三态之二：error（可重试；★ 不允许空白） -->
    <ErrorState
      v-if="error"
      :message="error"
      :detail="errorDetail"
      hint="MCP 令牌台账读取失败：mcptokenqry 需登录态，请检查网络与会话是否有效后重试。"
      @retry="reload()"
    />

    <template v-else>
      <div class="flex flex-wrap items-center justify-between gap-sm">
        <p class="text-caption text-ch-text-secondary">
          共 {{ total }} 条；服务端分页（每页 {{ size }} 条）· 排序
          <span class="font-mono text-code">order='modify'</span>（modifyYMDHMS DESC，最近变更在前）·
          <span class="font-mono text-code">mode='full'</span>
          （short 列清单不含 transport / lastUseYMDHMS / useCount / regYMDHMS）
        </p>
        <AppButton size="sm" icon="fa fa-rotate-right" :loading="loading" @click="reload()">刷新</AppButton>
      </div>

      <!-- 三态之一：loading（首屏骨架行）/ 三态之三：empty（内置 EmptyState）由 AppTable 承载 -->
      <AppTable
        :columns="COLUMNS"
        :rows="tableRows"
        :loading="loading"
        :empty="'暂无登记令牌'"
        :empty-description="'ch_mcp_token 中还没有登记记录；本页只读，不提供新建入口，如需新增请走服务端登记流程。'"
        row-height="compact"
        row-key="recID"
      >
        <template #cell-tokenName="{ row }">
          <span class="flex min-w-0 flex-col gap-xs">
            <span class="truncate text-ch-text-primary">{{ row.tokenName }}</span>
            <span class="truncate text-caption text-ch-text-secondary">项目 {{ row.projectCode || '—' }}</span>
          </span>
        </template>

        <!-- 标识：★ tokenHash 前 8 位 + …（title 给出完整 hash）；表内无明文，故不提供复制 -->
        <template #cell-tokenHash="{ row }">
          <span class="font-mono text-code text-ch-text-secondary" :title="row.tokenHash || '—'">
            {{ row.shortHash }}
          </span>
        </template>

        <template #cell-tokenScope="{ row }">
          <span class="text-body-s text-ch-text-primary">{{ row.scopeText }}</span>
        </template>

        <template #cell-transport="{ row }">
          <span class="font-mono text-code text-ch-text-secondary">{{ row.transportText }}</span>
        </template>

        <!-- 状态：★ 由 revokedYMDHMS 推导（有值 → 已吊销），形状图标 + 颜色 + 文字三重编码 -->
        <template #cell-status="{ row }">
          <span
            class="inline-flex items-center gap-xs whitespace-nowrap text-body-s"
            :style="{ color: row.statusColor }"
            :aria-label="`状态：${row.statusLabel}`"
          >
            <i :class="row.statusIcon" aria-hidden="true"></i>
            <span>{{ row.statusLabel }}</span>
          </span>
        </template>

        <template #cell-regYMDHMS="{ row }">
          <span class="tabular-nums text-ch-text-secondary">{{ row.regText }}</span>
        </template>

        <template #cell-lastUseYMDHMS="{ row }">
          <span class="tabular-nums" :class="row.lastUseText === '—' ? 'text-ch-text-tertiary' : 'text-ch-text-secondary'">
            {{ row.lastUseText }}
          </span>
        </template>

        <template #cell-useCount="{ row }">
          <span class="tabular-nums text-ch-text-primary">{{ row.useCountText }}</span>
        </template>

        <template #cell-ownerID="{ row }">
          <span class="font-mono text-code text-ch-text-secondary">{{ row.ownerID }}</span>
        </template>
      </AppTable>

      <AppPagination
        :total="total"
        :page-size="size"
        :current-page="page"
        :disabled="loading"
        @page-change="onPageChange"
      />

      <p class="text-caption text-ch-text-secondary">
        来源：ch_mcp_token 配置表（只读端点 mcptokenqry）· 状态由 revokedYMDHMS 推导（有值即失效）·
        调用次数 useCount 经 Number() 归一（附录 B R-26：后端以字符串返回）。
      </p>
    </template>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import AppButton from '@/components/base/AppButton.vue'
import AppPagination from '@/components/base/AppPagination.vue'
import AppTable from '@/components/base/AppTable.vue'
import ConflictBanner from '@/components/base/ConflictBanner.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import { tokens } from '@/js/tokens'
import { mcpTokenQry } from '@/api/mcp'
import { formatYMDHMS } from '@/utils/common'
import { usePagination } from '@/components/base/composables/usePagination'

/** 列配置（末列「创建者」= 可选补充字段 ownerID；projectCode 并入「令牌」单元格第二行） */
const COLUMNS = [
  { key: 'tokenName', title: '令牌', minWidth: 196 },
  { key: 'tokenHash', title: '标识（hash 前 8 位）', width: 168 },
  { key: 'tokenScope', title: '范围', width: 96 },
  { key: 'transport', title: '传输', width: 96 },
  { key: 'status', title: '状态', width: 108 },
  { key: 'regYMDHMS', title: '创建时间', width: 168 },
  { key: 'lastUseYMDHMS', title: '最近使用', width: 168 },
  { key: 'useCount', title: '调用次数', width: 104, align: 'right' },
  { key: 'ownerID', title: '创建者', width: 132 }
]

/** `tokenScope` 中文映射（表 COMMENT：read 或 write 或 publish） */
const SCOPE_TEXT = { read: '只读', write: '读写', publish: '可发布' }

const rawText = (value) => (value === null || value === undefined ? '' : String(value).trim())

/** 字符串口径数值 → Number（R-26）；空 / 非数值 → null */
function toNumber(value) {
  const text = rawText(value)
  if (!text) return null
  const parsed = Number(text)
  return Number.isFinite(parsed) ? parsed : null
}

/** 14 位 YMDHMS → `YYYY-MM-DD HH:mm:ss`；空值 → `—` */
const timeText = (value) => (rawText(value) ? formatYMDHMS(rawText(value)) : '—')

/** 行归一（把「后端口径」翻译成「展示口径」，模板内不做分支） */
function normalizeToken(row) {
  const source = row && typeof row === 'object' ? row : {}
  const hash = rawText(source.tokenHash)
  const scope = rawText(source.tokenScope)
  const revoked = rawText(source.revokedYMDHMS)
  const useCount = toNumber(source.useCount)
  return {
    recID: rawText(source.recID),
    tokenName: rawText(source.tokenName) || '—',
    tokenHash: hash,
    shortHash: hash ? `${hash.slice(0, 8)}…` : '—',
    scopeText: SCOPE_TEXT[scope] || scope || '—',
    transportText: rawText(source.transport) || '—',
    statusLabel: revoked ? '已吊销' : '有效',
    // 三重编码（裁定 C6）：已吊销 = 灰 + fa-ban；有效 = 绿 + fa-circle-check（灰度下仍可区分）
    statusColor: revoked ? tokens.text.secondary : tokens.status.success,
    statusIcon: revoked ? 'fa fa-ban' : 'fa fa-circle-check',
    regText: timeText(source.regYMDHMS),
    lastUseText: timeText(source.lastUseYMDHMS),
    useCountText: useCount === null ? '—' : String(useCount),
    projectCode: rawText(source.projectCode),
    ownerID: rawText(source.ownerID) || '—'
  }
}

/* ---------------------------------------------------------------------------
 * 取数（服务端分页 + 三态）
 * ------------------------------------------------------------------------- */

const errorDetail = ref('')

async function fetchTokens(params) {
  try {
    const res = await mcpTokenQry(
      { mode: 'full', order: 'modify', ...params },
      { silent: true }
    )
    errorDetail.value = ''
    return res
  } catch (error) {
    errorDetail.value = [
      error?.errCode ? `errCode: ${error.errCode}` : '',
      error?.MSG?.content || error?.message || ''
    ]
      .filter(Boolean)
      .join('\n')
    throw error
  }
}

const { rows, total, page, size, loading, error, goPage, changeSize, refresh } = usePagination(fetchTokens, {
  pageSize: 20
})

const tableRows = computed(() => rows.value.map(normalizeToken))

/** 手动刷新：`forceFlashFlag:'1'` 绕过后端查询缓冲重查（§2.4.3） */
function reload() {
  return refresh({ forceFlashFlag: '1' })
}

function onPageChange({ page: nextPage, size: nextSize }) {
  if (nextSize && nextSize !== size.value) changeSize(nextSize)
  else if (nextPage !== page.value) goPage(nextPage)
}
</script>
