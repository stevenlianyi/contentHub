<!-- ============================================================================
 * AboutPanel · P-13 设置页「关于」（Step 17）
 * ----------------------------------------------------------------------------
 * 【口径必须来源可查（裁定 D），不得编造】
 *   · 前端版本：`package.json` 的 `version`，经 **Vite JSON 导入**读取（`import pkg from '…/package.json'`），
 *     非硬编码；本步已授权把该字段由 `0.0.0` 改为 `1.0.0`（首个可用版本，不改动任何依赖行为）。
 *   · 后端版本：★ **后端无任何只读端点** → 固定显示 `—（无只读端点）`，登记为待确认项，**不得编造**。
 *   · 设计规范版本：常量 `DESIGN_SPEC_VERSION`（`src/config/settings.js`，本步授权小改），
 *     出处 `plan/UI/contentHub UI 设计.md`（v1.1），页面只读引用。
 *   · Design Token：显示「单一数据源 src/js/tokens.js（已冻结）」；★ **不得修改冻结文件**
 *     —— `tokens.js` 本身**没有版本号常量**，故此处只声明数据源与冻结状态，
 *     并把「如需展示版本号须先同步 UI 设计文档第七章与本计划 §2.3 再加常量」作为说明留在页面上。
 *   · 运行环境 / Mock 开关：仅取**前端自身**信息（`import.meta.env.MODE`、`VITE_USE_MOCK`），
 *     不去探测后端。
 * 【只读】不含任何表单控件（输入框 / 文本域 / 下拉 / 提交按钮）；不调用任何写接口。
 * 【来源标注（裁定 E）】每项右侧配 12px `text/secondary` 的「来源」小字。
 * 【硬约束】单文件 ≤ 600 行（§2.1）。
 * ========================================================================== -->
<template>
  <section class="ch-card flex flex-col gap-lg">
    <header class="flex flex-col gap-xs">
      <h2 class="text-h2 text-ch-text-primary">关于</h2>
      <p class="text-body-s text-ch-text-secondary">
        版本与运行环境信息。除「后端版本」外均取自前端可查来源（构建产物 / 配置常量 / 环境变量），
        不探测后端、不编造取值。
      </p>
    </header>

    <dl class="flex flex-col">
      <div
        v-for="row in ROWS"
        :key="row.key"
        class="flex flex-wrap items-center justify-between gap-x-lg gap-y-xs border-b border-ch-divider py-md last:border-b-0"
      >
        <dt class="w-[168px] shrink-0 text-body-s text-ch-text-secondary">{{ row.label }}</dt>
        <dd class="flex min-w-0 flex-1 flex-wrap items-center justify-between gap-x-md gap-y-xs">
          <span class="text-body-s" :class="row.tone === 'muted' ? 'text-ch-text-tertiary' : 'text-ch-text-primary'">
            {{ row.value }}
          </span>
          <span class="text-caption text-ch-text-secondary">{{ row.source }}</span>
        </dd>
      </div>
    </dl>

    <p class="text-caption text-ch-text-secondary">
      说明：src/js/tokens.js 为冻结文件且「无版本号常量」—— 如需在此展示 Token 版本号，
      须先同步 UI 设计文档第七章与本计划 §2.3，再在该文件增加常量（本步不改动冻结文件）。
    </p>
  </section>
</template>

<script setup>
import pkg from '../../../package.json'
import { DESIGN_SPEC_VERSION } from '@/config/settings'

/** 构建模式：development / production（前端自身信息，来自 Vite 静态替换） */
const MODE = String(import.meta.env.MODE || '')
/** Mock 开关：VITE_USE_MOCK（.env.development=true / .env.production=false） */
const MOCK_ON = String(import.meta.env.VITE_USE_MOCK ?? '') === 'true'

const ROWS = [
  {
    key: 'frontend',
    label: '前端版本',
    value: `v${pkg.version}`,
    source: '来源：code/webserver/package.json（Vite JSON 导入 pkg.version，非硬编码）'
  },
  {
    key: 'backend',
    label: '后端版本',
    value: '—（无只读端点）',
    tone: 'muted',
    source: '来源：后端 72 个端点中无版本查询端点（附录 B 待确认项，不编造）'
  },
  {
    key: 'designSpec',
    label: '设计规范版本',
    value: DESIGN_SPEC_VERSION,
    source: '来源：plan/UI/contentHub UI 设计.md（常量 DESIGN_SPEC_VERSION，src/config/settings.js）'
  },
  {
    key: 'tokens',
    label: 'Design Token',
    value: '单一数据源 src/js/tokens.js（已冻结）',
    source: '来源：src/js/tokens.js 冻结声明（Tailwind 主题键与 --ch-* 变量均由此派生）'
  },
  {
    key: 'mode',
    label: '运行环境',
    value: MODE || '—',
    source: '来源：import.meta.env.MODE（前端构建模式，不探测后端）'
  },
  {
    key: 'mock',
    label: 'Mock 开关',
    value: MOCK_ON ? '开启（true）' : '关闭（false）',
    source: '来源：VITE_USE_MOCK 环境变量（.env.development=true / .env.production=false）'
  }
]
</script>
