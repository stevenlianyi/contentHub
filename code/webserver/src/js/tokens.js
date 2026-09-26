/* ============================================================================
 * 内容中枢 · Design Token（唯一数据源 / Single Source of Truth）
 * ----------------------------------------------------------------------------
 * 【冻结声明】
 *   本文件为设计 Token 的**唯一数据源**。任何取值变更必须同步修改：
 *     ① `plan/UI/contentHub UI 设计.md` 第七章（7.1~7.4）
 *     ② `plan/前端开发计划.md` §2.3 Design Token 表
 *   并重新执行 `npm run verify`（色值硬编码扫描 + 对比度校验）后方可合入。
 *
 * 【三条落地路径（均从本文件取值，禁止各自维护副本）】
 *   ① Tailwind   ：`tailwind.config.js` → 工具类 `bg-ch-surface` / `text-ch-text-primary` / `p-4` …
 *   ② CSS 变量   ：`src/styles/element-vars.css` → `:root` 的 `--ch-*`
 *                  （Element Plus 的 `--el-*` 一律 `var(--ch-*)` 引用）
 *   ③ JS / 内联  ：业务代码 `import { tokens } from '@/js/tokens'`
 *                  （仅用于 Tailwind 表达不了的场景：Canvas、图表、动态 style 计算）
 *
 * 【硬约束】
 *   - 禁止在任何 `.vue` 中硬编码十六进制色值（由 `scripts/lint-hex.mjs` 校验）；
 *     一律使用 Tailwind 语义类或 `var(--ch-*)`。
 *   - 预览区（`.preview-scope` 子树）强制浅色隔离，只允许 `preview/*` 三个 Token，
 *     不得引用应用级暗色 Token。
 *
 * 【差异裁定（计划 §1.3）】
 *   - C3：`bg.hover` 采纳 Ardot = `rgba(31, 41, 55, .30)`
 *   - C4：`status.info` 采纳 Ardot = `#06B6D4`
 *   - C5：设计稿基准 `1344 × 780`；Web 实现按 `1440` 基准 + 5 档响应式
 *
 * 【废弃禁用（不得再引用）】
 *   `primaryLight #60A5FA`、`successLight #34D399`、`dark-300 #0F172A`、
 *   `dark-350 #090F1E`、`shadow-btn`、`shadow-btn-hover`
 * ========================================================================== */

export const tokens = {
  /* ---------- 颜色 · 背景（2.3.1） ---------- */
  bg: {
    base: '#030712', // 应用最底层背景
    sidebar: '#111827', // 侧栏、顶栏
    surface: '#1F2937', // 卡片、面板、表格
    elevated: '#374151', // 弹窗、下拉、表头、浮层
    input: '#0B1220', // 输入框、下拉框底（深于卡片，制造凹陷感）
    hover: 'rgba(31, 41, 55, .30)', // 行/项 hover （C3：采纳 Ardot）
  },

  /* ---------- 颜色 · 文字 ---------- */
  text: {
    primary: '#F3F4F6', // 主标题、正文、表格主字段
    secondary: '#9CA3AF', // 次要文字、表头、说明
    tertiary: '#6B7280', // 占位符、时间戳（仅限非关键信息）
    disabled: '#4B5563', // 禁用文字
    inverse: '#111827', // 浅色底上的文字（预览区、实心按钮）
  },

  /* ---------- 颜色 · 描边与分隔 ---------- */
  border: {
    default: '#374151', // 卡片/容器边框
    light: '#4B5563', // 次级边框、按钮描边
    focus: '#3B82F6', // 焦点态
    divider: 'rgba(55, 65, 81, .50)', // 表格行分隔、列表分隔
  },

  /* ---------- 颜色 · 主色 ---------- */
  primary: {
    base: '#3B82F6', // 主操作、选中态、链接
    hover: '#2563EB', // 主操作 hover
    active: '#1D4ED8', // 主操作 active
    subtle: 'rgba(59, 130, 246, .12)', // 选中背景、浅色标签底
  },

  /* ---------- 颜色 · 状态（三重编码中的「颜色」一维） ---------- */
  status: {
    success: '#10B981', // 成功、通过、有效
    warning: '#F59E0B', // 警告、临期、即将过期
    danger: '#EF4444', // 失败、阻断、删除
    info: '#06B6D4', // 完成度指示、中性提示 （C4：采纳 Ardot）
  },

  /* ---------- 颜色 · 平台识别色（仅用于平台识别，不承载状态语义） ---------- */
  platform: {
    wechat_mp: '#07C160', // 微信公众号识别色
    xiaohongshu: '#FF2442', // 小红书识别色
    generic: '#6B7280', // 通用 HTML 识别色
  },

  /* ---------- 颜色 · 预览区（全站唯一浅色区域） ---------- */
  preview: {
    bg: '#FFFFFF', // 预览手机框内背景
    text: '#1F2937', // 预览内正文
    border: '#E5E7EB', // 预览内分隔
  },

  /* ---------- 字体族（2.3.2） ---------- */
  font: {
    cjk: '"PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif',
    latin: 'Inter, sans-serif',
    mono: '"JetBrains Mono", Consolas, ui-monospace, monospace',
  },

  /* ---------- 字号（px；字重仅 400 / 500 / 600，中文正文不用斜体） ---------- */
  fontSize: {
    display: 32, // Display：工作台指标卡数字
    h1: 22, // H1：页面标题
    h2: 18, // H2：卡片标题、区块标题
    h3: 16, // H3：弹窗标题、子区块
    body: 14, // Body：正文（默认基准）
    bodyS: 13, // Body-S：表格正文、表单辅助说明
    caption: 12, // Caption：标签、时间戳、计数
    code: 12, // Code：标识符、hash、日志
  },

  /* ---------- 间距（4px 基准，2.3.3） ---------- */
  space: {
    xs: 4,
    sm: 8,
    md: 12,
    lg: 16,
    xl: 20,
    '2xl': 24,
    '3xl': 32,
    '4xl': 40,
    '5xl': 48,
  },

  /* ---------- 圆角（2.3.3） ---------- */
  radius: {
    sm: 4,
    md: 6,
    lg: 8, // 按钮、缩略图
    xl: 12, // 卡片、面板
    '2xl': 16, // 弹窗、抽屉
    full: '9999px',
  },

  /* ---------- 阴影（卡片默认不用阴影，靠 border 分层） ---------- */
  shadow: {
    raised: '0 4px 16px rgba(0, 0, 0, .40)', // 下拉、Popover、Tooltip
    modal: '0 8px 32px rgba(0, 0, 0, .50)', // 弹窗、抽屉
    focus: '0 0 0 3px rgba(59, 130, 246, .25)',
    device: '0 0 0 1px #374151, 0 24px 48px rgba(0, 0, 0, .55)', // 预览手机框
  },

  /* ---------- 动效（2.3.4；禁止视差/渐变背景动画/粒子/自动轮播） ---------- */
  motion: {
    micro: { duration: 150, easing: 'ease-out' }, // 微交互（hover / 按钮）
    background: { duration: 200, easing: 'ease-out' }, // 背景色过渡
    modalEnter: { duration: 250, easing: 'ease-out' }, // 弹窗出现
    modalLeave: { duration: 180, easing: 'ease-in' }, // 弹窗关闭
    drawer: { duration: 250, easing: 'cubic-bezier(0.4, 0, 0.2, 1)' }, // 抽屉滑入
    tabIndicator: { duration: 250, easing: 'ease-out' }, // Tab 指示器滑动
    listEnter: { duration: 240, stagger: 40, staggerLimit: 10, easing: 'ease-out' }, // 列表项进入
    statusPulse: { duration: 2000, easing: 'ease-in-out', iteration: 'infinite' }, // 状态脉冲（仅 RUNNING）
    shimmer: { duration: 1500, easing: 'linear', iteration: 'infinite' }, // 骨架屏 shimmer
  },

  /* ---------- 基准与布局（C5；layout 值同时输出为 --ch-* 变量） ---------- */
  designBase: {
    artboard: { w: 1344, h: 780 }, // 设计稿基准（Ardot）
    web: { w: 1440 }, // Web 实现基准
  },
  layout: {
    sidebarW: 240,
    sidebarCollapsedW: 64,
    topbarH: 56,
    navItemH: 36,
    contentMaxW: 1440,
    contentPadding: 24,
    cardPadding: 20,
    tableRowH: 44,
    tableRowCompactH: 36,
    tableHeadH: 40,
    cellPadX: 16,
    colStatusW: 96,
    colPlatformW: 180,
    colUpdatedW: 110,
  },
}

export default tokens
