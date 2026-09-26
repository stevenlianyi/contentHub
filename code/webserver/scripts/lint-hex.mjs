#!/usr/bin/env node
/* ============================================================================
 * 色值硬编码扫描（计划 Step 1 · 第 7 点 / §2.11）
 * ----------------------------------------------------------------------------
 * 作用：扫描源码，命中十六进制色值（`#RGB` / `#RGBA` / `#RRGGBB` / `#RRGGBBAA`）
 *       即报错并列出 `文件:行:列`。
 * 默认范围：`src` 目录下所有 `.vue`（计划 Step 1 第 7 点规定）。
 *          加 `--all` 时扩展为 `.vue` / `.js` / `.css`，用于自查其它层是否夹带色值。
 * 白名单：`src/js/tokens.js`（Token 定义层）、`src/styles/element-vars.css`、
 *         `src/styles/tailwind.css`（CSS 变量桥接层）——色值的唯一合法归属地。
 * 退出码：存在命中 → 1；否则 0。
 * 用法：node scripts/lint-hex.mjs [--all]
 * ========================================================================== */

import { readdirSync, readFileSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join, relative, resolve, sep } from 'node:path'

const ROOT = resolve(fileURLToPath(import.meta.url), '..', '..')
const SRC_DIR = join(ROOT, 'src')

/** 白名单（相对 ROOT 的 posix 路径） */
const WHITELIST = new Set([
  'src/js/tokens.js',
  'src/styles/element-vars.css',
  'src/styles/tailwind.css',
])

/** 默认只扫 .vue；`--all` 时扩展到 js / css */
const scanAll = process.argv.includes('--all')
const EXTENSIONS = scanAll ? new Set(['.vue', '.js', '.css']) : new Set(['.vue'])

/** 十六进制色值：按长度从长到短匹配，避免 8 位色值被截断成 6 位而漏报 */
const RE_HEX_COLOR = /#(?:[0-9A-Fa-f]{8}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{4}|[0-9A-Fa-f]{3})(?![0-9A-Fa-f])/g

const toPosix = (path) => path.split(sep).join('/')

/** 递归收集待扫文件 */
function collect(dir) {
  const entries = []
  for (const name of readdirSync(dir)) {
    const full = join(dir, name)
    if (statSync(full).isDirectory()) {
      entries.push(...collect(full))
      continue
    }
    const dot = name.lastIndexOf('.')
    if (dot >= 0 && EXTENSIONS.has(name.slice(dot))) entries.push(full)
  }
  return entries
}

/** 计算命中位置并生成一条违规记录 */
function collectViolations(file, content) {
  const violations = []
  const lines = content.split(/\r?\n/)
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    RE_HEX_COLOR.lastIndex = 0
    let match = RE_HEX_COLOR.exec(line)
    while (match) {
      violations.push({
        file: toPosix(relative(ROOT, file)),
        line: index + 1,
        column: match.index + 1,
        text: match[0],
        snippet: line.trim(),
      })
      match = RE_HEX_COLOR.exec(line)
    }
  }
  return violations
}

const targets = collect(SRC_DIR)
  .map((file) => ({ file, relative: toPosix(relative(ROOT, file)) }))
  .filter((entry) => !WHITELIST.has(entry.relative))

const violations = []
for (const target of targets) {
  violations.push(...collectViolations(target.file, readFileSync(target.file, 'utf8')))
}

const scope = scanAll ? 'src/**/*.{vue,js,css}' : 'src/**/*.vue'
console.log(`\n=== 色值硬编码扫描（${scope}；已排除白名单 ${WHITELIST.size} 个 Token 层文件）===`)
console.log(`扫描文件 ${targets.length} 个\n`)

if (violations.length === 0) {
  console.log('0 命中：未发现硬编码十六进制色值。\n')
  process.exit(0)
}

const width = Math.max(...violations.map((v) => `${v.file}:${v.line}:${v.column}`.length))
for (const v of violations) {
  const location = `${v.file}:${v.line}:${v.column}`.padEnd(width)
  console.log(`  ✗ ${location}  ${v.text.padEnd(9)}  ${v.snippet}`)
}

console.log(`\n共 ${violations.length} 处命中。`)
console.log('处理方式：改用 Tailwind 语义类（如 bg-ch-surface / text-ch-text-primary）或 var(--ch-*)；')
console.log('         若确需新增色值，请先在 src/js/tokens.js 登记（并同步设计文档）。\n')
process.exit(1)
