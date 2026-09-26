#!/usr/bin/env node
/* ============================================================================
 * 对比度校验（计划 Step 1 · 第 6 点 / §2.11 · WCAG 2.1 AA）
 * ----------------------------------------------------------------------------
 * 作用：读取 `src/js/tokens.js`，输出「文字色 × 背景色」对比度矩阵，并对
 *       语义组合（实心按钮、链接、状态徽章、平台 chip、描边）做非文字对比校验。
 * 算法：WCAG 2.1 相对亮度（sRGB 线性化）+ 对比度 (L1 + 0.05) / (L2 + 0.05)。
 * 阈值：正文 4.5:1；大字号 / 次要文字 / 功能图标 / 非文字描边 3:1。
 * 退出码：存在「低于阈值且未登记豁免」的组合 → 1；否则 0。
 * 豁免：**必须在 WHITELIST 中显式登记（含理由）**，禁止静默放过。
 * 用法：node scripts/check-contrast.mjs
 * ========================================================================== */

import { tokens } from '../src/js/tokens.js'

/* --------------------------------------------------------------------------
 * 1. 颜色解析与对比度计算
 * ------------------------------------------------------------------------ */

const RE_HEX = /^#([0-9a-f]{3,8})$/i
const RE_RGB = /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)\s*(?:[,/]\s*([\d.]+%?)\s*)?\)$/i

/**
 * 解析色值，返回 { r, g, b, a }。
 * 支持 `#RGB` / `#RGBA` / `#RRGGBB` / `#RRGGBBAA` / `rgb()` / `rgba()`，
 * 以及已解析过的颜色对象（内部合成结果直接透传）。
 */
function parseColor(input) {
  if (input && typeof input === 'object' && typeof input.r === 'number') {
    return { r: input.r, g: input.g, b: input.b, a: input.a === undefined ? 1 : input.a }
  }

  const value = String(input).trim()

  const hex = RE_HEX.exec(value)
  if (hex) {
    let body = hex[1]
    if (body.length === 3 || body.length === 4) {
      body = body
        .split('')
        .map((ch) => ch + ch)
        .join('')
    }
    if (body.length !== 6 && body.length !== 8) {
      throw new Error(`无法解析色值：${input}`)
    }
    const alpha = body.length === 8 ? parseInt(body.slice(6, 8), 16) / 255 : 1
    return {
      r: parseInt(body.slice(0, 2), 16),
      g: parseInt(body.slice(2, 4), 16),
      b: parseInt(body.slice(4, 6), 16),
      a: Number(alpha.toFixed(4)),
    }
  }

  const rgb = RE_RGB.exec(value)
  if (rgb) {
    const alphaRaw = rgb[4]
    let alpha = 1
    if (alphaRaw !== undefined) {
      alpha = alphaRaw.endsWith('%') ? parseFloat(alphaRaw) / 100 : parseFloat(alphaRaw)
    }
    return { r: Number(rgb[1]), g: Number(rgb[2]), b: Number(rgb[3]), a: alpha }
  }

  throw new Error(`无法解析色值：${input}（仅支持 hex / rgb / rgba）`)
}

/** 把半透明色叠加到不透明底色上，返回不透明结果 */
function composite(foreground, backdrop) {
  const fg = parseColor(foreground)
  const bg = parseColor(backdrop)
  if (fg.a >= 1) return fg
  if (bg.a < 1) throw new Error('叠加底色必须不透明')
  const mix = (f, b) => Math.round(f * fg.a + b * (1 - fg.a))
  return { r: mix(fg.r, bg.r), g: mix(fg.g, bg.g), b: mix(fg.b, bg.b), a: 1 }
}

/** WCAG 2.1 相对亮度 */
function relativeLuminance(color) {
  const channel = (raw) => {
    const c = raw / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  return (
    0.2126 * channel(color.r) + 0.7152 * channel(color.g) + 0.0722 * channel(color.b)
  )
}

/** WCAG 2.1 对比度 */
function contrastRatio(colorA, colorB) {
  const la = relativeLuminance(parseColor(colorA))
  const lb = relativeLuminance(parseColor(colorB))
  const [hi, lo] = la >= lb ? [la, lb] : [lb, la]
  return (hi + 0.05) / (lo + 0.05)
}

const toHex = (color) => {
  const hex = (n) => Math.round(n).toString(16).padStart(2, '0').toUpperCase()
  return `#${hex(color.r)}${hex(color.g)}${hex(color.b)}`
}

/* --------------------------------------------------------------------------
 * 2. 受检组合定义（全部取自 tokens.js）
 * ------------------------------------------------------------------------ */

/** 背景 Token；半透明者先合成到指定底色 */
const BACKGROUNDS = [
  { key: 'bg.base', value: tokens.bg.base },
  { key: 'bg.sidebar', value: tokens.bg.sidebar },
  { key: 'bg.surface', value: tokens.bg.surface },
  { key: 'bg.elevated', value: tokens.bg.elevated },
  { key: 'bg.input', value: tokens.bg.input },
  // C3 裁定值 bg.hover 为半透明叠加层，合成到最底层与卡片面两个承载面
  {
    key: 'bg.hover over bg.base',
    value: composite(tokens.bg.hover, tokens.bg.base),
    composited: true,
  },
  {
    key: 'bg.hover over bg.surface',
    value: composite(tokens.bg.hover, tokens.bg.surface),
    composited: true,
  },
]

/** 文字 Token 及其阈值（正文 4.5 / 次要文字 3.0） */
const TEXTS = [
  { key: 'text.primary', value: tokens.text.primary, min: 4.5, kind: '正文' },
  { key: 'text.secondary', value: tokens.text.secondary, min: 3.0, kind: '次要文字' },
  { key: 'text.tertiary', value: tokens.text.tertiary, min: 3.0, kind: '次要文字' },
  { key: 'text.disabled', value: tokens.text.disabled, min: 3.0, kind: '禁用文字' },
]

/** 语义组合对：前景 Token × 背景 Token × 阈值 */
const SEMANTIC_PAIRS = [
  { fg: 'text.inverse', bg: 'primary.base', min: 4.5, note: '实心主按钮文字' },
  { fg: 'primary.base', bg: 'bg.base', min: 3.0, note: '链接 / 主色图标' },
  { fg: 'primary.base', bg: 'bg.surface', min: 3.0, note: '链接 / 主色图标' },
  { fg: 'primary.base', bg: 'bg.input', min: 3.0, note: '输入框 focus 描边' },
  { fg: 'status.success', bg: 'bg.surface', min: 3.0, note: '状态徽章（三重编码取色）' },
  { fg: 'status.warning', bg: 'bg.surface', min: 3.0, note: '状态徽章（三重编码取色）' },
  { fg: 'status.danger', bg: 'bg.surface', min: 3.0, note: '状态徽章（三重编码取色）' },
  { fg: 'status.info', bg: 'bg.surface', min: 3.0, note: '完成度指示器' },
  { fg: 'platform.wechat_mp', bg: 'bg.surface', min: 3.0, note: '平台识别 chip' },
  { fg: 'platform.xiaohongshu', bg: 'bg.surface', min: 3.0, note: '平台识别 chip' },
  { fg: 'platform.generic', bg: 'bg.surface', min: 3.0, note: '平台识别 chip' },
]

/** 非文字对比（WCAG 1.4.11，3:1）：描边 / 焦点环与其相邻背景 */
const BORDER_PAIRS = [
  { fg: 'border.default', bg: 'bg.base', min: 3.0, note: '卡片描边' },
  { fg: 'border.default', bg: 'bg.sidebar', min: 3.0, note: '侧栏分隔' },
  { fg: 'border.default', bg: 'bg.surface', min: 3.0, note: '卡片描边' },
  { fg: 'border.light', bg: 'bg.elevated', min: 3.0, note: '浮层内次级描边' },
  { fg: 'border.light', bg: 'bg.surface', min: 3.0, note: '按钮描边' },
  { fg: 'border.focus', bg: 'bg.base', min: 3.0, note: '焦点环' },
  { fg: 'border.focus', bg: 'bg.sidebar', min: 3.0, note: '焦点环' },
  { fg: 'border.focus', bg: 'bg.surface', min: 3.0, note: '焦点环' },
  { fg: 'border.focus', bg: 'bg.input', min: 3.0, note: '焦点环' },
  { fg: 'border.focus', bg: 'bg.elevated', min: 3.0, note: '浮层内焦点环' },
]

/* --------------------------------------------------------------------------
 * 3. 豁免白名单（显式登记：键 = `<前景 Token>|<背景 Token>`）
 *    登记项必须写明理由；未登记的低于阈值组合一律导致退出码 1。
 * ------------------------------------------------------------------------ */

const DISABLED_EXEMPT =
  'WCAG 2.1 1.4.3 / 1.4.11 明确豁免「非活动（禁用）控件」；text/disabled 为禁用态专用色，' +
  '低对比是有意的视觉表达，且始终配合 aria-disabled + Tooltip 说明禁用原因'

const STRUCTURAL_BORDER_EXEMPT =
  '已知豁免（计划 Step 1 第 6 点）：暗色下卡片分层靠背景明度差（bg.surface 对 bg.base）表达，' +
  '描边为 1px 极细结构线，不承载信息；若强行提到 3:1 会破坏「卡片默认不用阴影/不抢层级」的设计意图'

const SECONDARY_BORDER_EXEMPT =
  'UI 设计.md §5.2 明确「Secondary 按钮描边 = border/light #4B5563」，该描边为 1px 结构线，' +
  '对 bg/surface（1.94:1）与 bg/elevated（1.36:1）均低于 3:1。按钮的可点击性由文字表达' +
  '（text/primary 对 bg/elevated 为 9.37:1）并配合 hover 描边转主色，登记为与 border/default 同源的已知豁免'

const WHITELIST = {
  'text.disabled|bg.base': DISABLED_EXEMPT,
  'text.disabled|bg.sidebar': DISABLED_EXEMPT,
  'text.disabled|bg.surface': DISABLED_EXEMPT,
  'text.disabled|bg.elevated': DISABLED_EXEMPT,
  'text.disabled|bg.input': DISABLED_EXEMPT,
  'text.disabled|bg.hover over bg.base': DISABLED_EXEMPT,
  'text.disabled|bg.hover over bg.surface': DISABLED_EXEMPT,
  'text.tertiary|bg.elevated':
    'text/tertiary 仅用于「非关键信息（占位符、时间戳）」，其实际承载面为 bg.input（输入框）与 ' +
    'bg.surface（表格/卡片）；bg.elevated 只用于浮层与表头，表头文字按 §1.4 用 text/secondary。' +
    '该组合不构成实际界面，登记为可接受偏差（若后续确需在 elevated 上放非关键文字，应改用 text/secondary）',
  'border.default|bg.base': STRUCTURAL_BORDER_EXEMPT,
  'border.default|bg.sidebar': STRUCTURAL_BORDER_EXEMPT,
  'border.default|bg.surface': STRUCTURAL_BORDER_EXEMPT,
  'border.light|bg.surface': SECONDARY_BORDER_EXEMPT,
  'border.light|bg.elevated': SECONDARY_BORDER_EXEMPT,
  'border.focus|bg.elevated':
    '焦点环在浮层（bg.elevated）上为 2.80:1；该环为 2px 实线 + 2px offset 且与外层 bg.surface ' +
    '（4.06:1）形成闭合描边，仍可辨识，登记为已知豁免',
}

/* --------------------------------------------------------------------------
 * 4. 执行
 * ------------------------------------------------------------------------ */

const resolveToken = (path) =>
  path.split('.').reduce((node, step) => (node === undefined ? undefined : node[step]), tokens)

let failures = 0
let whitelisted = 0
let checked = 0

const padRight = (text, width) => String(text) + ' '.repeat(Math.max(0, width - String(text).length))
const padLeft = (text, width) => ' '.repeat(Math.max(0, width - String(text).length)) + String(text)

/** 判定单个组合 */
function evaluate({ fgKey, fgValue, bgKey, bgValue, min, kind, note }) {
  checked += 1
  const ratio = contrastRatio(fgValue, bgValue)
  const passed = ratio + 1e-9 >= min
  const key = `${fgKey}|${bgKey}`
  const exemptReason = WHITELIST[key]
  if (passed) return { ratio, status: 'pass' }
  if (exemptReason) {
    whitelisted += 1
    return { ratio, status: 'exempt', key, min, kind, note, exemptReason }
  }
  failures += 1
  return { ratio, status: 'fail', key, min, kind, note }
}

/* --- 4.1 文字 × 背景矩阵 ------------------------------------------------- */

console.log('\n=== 对比度矩阵：文字 Token × 背景 Token（WCAG 2.1）===\n')
console.log('阈值：text.primary（正文）4.5:1；其余文字 Token 3:1（次要文字 / 功能图标）\n')

const columnWidths = BACKGROUNDS.map((bg) => Math.max(bg.key.length, 9))
const header = `| ${padRight('前景 \\ 背景', 18)} | ${BACKGROUNDS.map((bg, i) => padRight(bg.key, columnWidths[i])).join(' | ')} |`
console.log(header)
console.log(`|${'-'.repeat(20)}|${columnWidths.map((w) => '-'.repeat(w + 2)).join('|')}|`)

const matrixExempt = []
const matrixFailures = []

for (const text of TEXTS) {
  const cells = []
  for (let i = 0; i < BACKGROUNDS.length; i += 1) {
    const bg = BACKGROUNDS[i]
    const result = evaluate({
      fgKey: text.key,
      fgValue: text.value,
      bgKey: bg.key,
      bgValue: bg.value,
      min: text.min,
      kind: text.kind,
    })
    if (result.status === 'exempt') matrixExempt.push(result)
    if (result.status === 'fail') matrixFailures.push(result)
    const mark = result.status === 'pass' ? '' : result.status === 'exempt' ? ' ~' : ' !'
    cells.push(padRight(`${result.ratio.toFixed(2)}${mark}`, columnWidths[i]))
  }
  console.log(`| ${padRight(text.key, 18)} | ${cells.join(' | ')} |`)
}

console.log('\n标记：数字=对比度；`!`=低于阈值且未登记豁免；`~`=低于阈值但已登记豁免（见下方清单）')

// 半透明背景先按 alpha 合成，这里给出合成后的实际色值，便于回查
const compositedBackgrounds = BACKGROUNDS.filter((bg) => bg.composited)
if (compositedBackgrounds.length > 0) {
  console.log(
    `半透明背景合成结果：${compositedBackgrounds
      .map((bg) => `${bg.key} → ${toHex(bg.value)}`)
      .join('；')}`
  )
}

/* --- 4.2 语义组合 ------------------------------------------------------- */

console.log('\n=== 语义组合（实心按钮 / 链接 / 状态 / 平台）===\n')
const semanticExempt = []
const semanticFailures = []

for (const pair of [...SEMANTIC_PAIRS, ...BORDER_PAIRS]) {
  const value = evaluate({
    fgKey: pair.fg,
    fgValue: resolveToken(pair.fg),
    bgKey: pair.bg,
    bgValue: resolveToken(pair.bg),
    min: pair.min,
    kind: pair.note,
  })
  const state = value.status === 'pass' ? 'OK  ' : value.status === 'exempt' ? '豁免' : '不达标'
  console.log(
    `${state}  ${padRight(`${pair.fg} on ${pair.bg}`, 44)} ${padLeft(value.ratio.toFixed(2), 6)}:1  (阈值 ${pair.min}:1)  ${pair.note}`
  )
  if (value.status === 'exempt') semanticExempt.push(value)
  if (value.status === 'fail') semanticFailures.push(value)
}

/* --- 4.3 未达标 / 豁免汇总 --------------------------------------------- */

const allFailures = [...matrixFailures, ...semanticFailures]
const allExempt = [...matrixExempt, ...semanticExempt]

console.log(`\n=== 汇总：共校验 ${checked} 组，达标 ${checked - allFailures.length - allExempt.length} 组 ===`)

if (allExempt.length > 0) {
  console.log(`\n--- 已登记豁免（${allExempt.length} 组）---`)
  const byReason = new Map()
  for (const item of allExempt) {
    const list = byReason.get(item.exemptReason) || []
    list.push(`${item.key} = ${item.ratio.toFixed(2)}:1（阈值 ${item.min}:1）`)
    byReason.set(item.exemptReason, list)
  }
  for (const [reason, items] of byReason) {
    console.log(`\n  理由：${reason}`)
    for (const item of items) console.log(`    · ${item}`)
  }
}

if (allFailures.length > 0) {
  console.log(`\n--- 未达标且未登记豁免（${allFailures.length} 组）---`)
  for (const item of allFailures) {
    console.log(`  ✗ ${item.key} = ${item.ratio.toFixed(2)}:1（阈值 ${item.min}:1）— ${item.kind || item.note || ''}`)
  }
  console.log('\n处理方式：调整 Token 取值，或在 scripts/check-contrast.mjs 的 WHITELIST 中显式登记豁免理由。')
  console.log('\n对比度校验未通过。\n')
  process.exit(1)
}

console.log('\n对比度校验通过（所有低于阈值的组合均已在 WHITELIST 登记豁免理由）。\n')
process.exit(0)
