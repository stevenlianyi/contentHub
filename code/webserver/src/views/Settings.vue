<!-- ============================================================================
 * Settings · P-13 系统设置（Step 17，原地替换 Step 3 的 PLACEHOLDER）
 * ----------------------------------------------------------------------------
 * 本页**只做四个分区的编排**（裁定 G / J），具体内容分别在：
 *   ① 文件后端（只读）      → 本文件内联（静态、无取数，无需独立文件）
 *   ② 平台默认参数（只读）  → `views/settings/PlatformDefaultsPanel.vue`（platformqry）
 *   ③ MCP 令牌（只读）      → `views/settings/McpTokenPanel.vue`（mcptokenqry）
 *   ④ 关于（只读）          → `views/settings/AboutPanel.vue`（前端自身信息）
 * 卡片：纵向间距 24（gap-2xl）、内边距 20（.ch-card，§2.3.3）；每张卡片 H2 标题 + 「来源」说明。
 *
 * 【只读红线（裁定 E / F）】
 *   · 页面**不含任何表单控件**（输入框 / 文本域 / 下拉 / 提交按钮），
 *     且**不调用任何写接口**（`platformmodify` / `mcptokenadd` / `mcptokenmodify` / `mcptokendel`
 *     四个写端点一律不调用）；
 *   · 不做主题切换（仅暗色）、不做语言切换、不做任何改变 `FILE_SYSTEM_MODE` 的写操作（红线 R2）。
 *
 * 【文件后端（裁定 A）】★ 后端**没有**该配置的只读端点（附录 B R-19：唯一返回它的 F9A0 属
 *   `/hfile` 的 JSON 分支，且需 `genDigest(GEN_DIST_KEY,…)`，前端无密钥不可调用）
 *   → 固定显示「由服务端配置决定（无查询端点）」+ 来源小字说明；
 *   ★ **严禁硬编码对象存储后端的任一候选取值，也不得推测**（本页不出现任何后端名）。
 *   若未来后端提供只读端点，再改为读值（本步不留代码入口）。
 * 【硬约束】单文件 ≤ 600 行（§2.1）。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-2xl">
    <header class="flex flex-col gap-xs">
      <h1 class="text-h1 text-ch-text-primary">系统设置</h1>
      <p class="text-body-s text-ch-text-secondary">
        本页全部为只读配置展示：文件后端、平台默认参数、MCP 令牌登记台账、关于。
        页面不提供任何编辑控件，也不调用任何写接口（修改配置请走服务端配置层）。
      </p>
    </header>

    <!-- 只读提示（裁定 E 建议） -->
    <ConflictBanner type="info" title="本页全部为只读配置展示，修改请走服务端配置层">
      文件后端由环境变量 / 服务端配置决定，平台规格取自 ch_platform 配置表，MCP 令牌为登记台账：
      均无编辑入口，避免「看得见改不了」的困惑，也避免误触红线（如任何改变 FILE_SYSTEM_MODE 的写操作）。
    </ConflictBanner>

    <!-- ① 文件后端（只读；无端点，固定文案） -->
    <section class="ch-card flex flex-col gap-lg">
      <header class="flex flex-col gap-xs">
        <h2 class="text-h2 text-ch-text-primary">文件后端</h2>
        <p class="text-body-s text-ch-text-secondary">
          对象存储后端由服务端环境决定。后端当前没有该配置的只读端点（附录 B R-19），
          本页不猜测取值、也不提供任何切换入口，故固定显示如下。
        </p>
      </header>

      <dl class="flex flex-col">
        <div
          v-for="row in FILE_ROWS"
          :key="row.key"
          class="flex flex-wrap items-center justify-between gap-x-lg gap-y-xs border-b border-ch-divider py-md last:border-b-0"
        >
          <dt class="w-[196px] shrink-0 text-body-s text-ch-text-secondary">{{ row.label }}</dt>
          <dd class="flex min-w-0 flex-1 flex-wrap items-center justify-between gap-x-md gap-y-xs">
            <span class="text-body-s text-ch-text-primary">{{ row.value }}</span>
            <span class="text-caption text-ch-text-secondary">{{ row.source }}</span>
          </dd>
        </div>
      </dl>
    </section>

    <!-- ② 平台默认参数（只读，platformqry） -->
    <PlatformDefaultsPanel />

    <!-- ③ MCP 令牌（只读，mcptokenqry） -->
    <McpTokenPanel />

    <!-- ④ 关于（只读，前端自身信息） -->
    <AboutPanel />
  </section>
</template>

<script setup>
import ConflictBanner from '@/components/base/ConflictBanner.vue'
import AboutPanel from '@/views/settings/AboutPanel.vue'
import McpTokenPanel from '@/views/settings/McpTokenPanel.vue'
import PlatformDefaultsPanel from '@/views/settings/PlatformDefaultsPanel.vue'
import { uploadUrl } from '@/config/settings'

/**
 * 文件后端两行（均为只读静态值）：
 *   · `FILE_SYSTEM_MODE`：★ 无只读端点（R-19）→ **不写任何候选取值**，固定展示「由服务端配置决定」；
 *   · 上传通道：取前端自身配置 `VITE_UPLOAD_URL`（真实上传通道为 /upload：nginx upload 模块注入 file.* 字段后转交后端 /hfile）。
 */
const FILE_ROWS = [
  {
    key: 'fileSystemMode',
    label: 'FILE_SYSTEM_MODE',
    value: '由服务端配置决定（无查询端点）',
    source: '来源：环境变量 / config/basicSettings.py（附录 B R-19：无只读端点）'
  },
  {
    key: 'uploadChannel',
    label: '上传通道（前端配置）',
    value: uploadUrl || '—',
    source: '来源：src/config/settings.js → uploadUrl ← VITE_UPLOAD_URL（附录 B R-18）'
  }
]
</script>
