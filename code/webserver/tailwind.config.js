/* ============================================================================
 * Tailwind 配置 · Design Token 落点之一（计划 §2.3 / Step 1）
 * ----------------------------------------------------------------------------
 * 取值一律从 `src/js/tokens.js` 引入并映射为主题键，本文件**不再维护任何独立色值**。
 * 对应关系：
 *   tokens.bg/text/border/primary/status  → theme.extend.colors.ch.* / plat.*
 *   tokens.font.*                        → theme.extend.fontFamily.*
 *   tokens.fontSize.*                    → theme.extend.fontSize.*（含行高/字重）
 *   tokens.radius.*                      → theme.extend.borderRadius.*
 *   tokens.shadow.*                      → theme.extend.boxShadow.*
 *   tokens.space.*                       → theme.extend.spacing.*（4px 基准，数值自动补 px）
 *   tokens.motion.*                      → theme.extend.keyframes / animation
 * 注：`extend` 只有**一个**键（修复基线 `tailwind.config.js:8` 与 `:39` 重复 `extend` 的缺陷：
 *     后者会静默覆盖前者）。新增主题必须写入同一个 `extend` 对象内。
 * 注：`.ch-card` 等极少数组合工具类写在 `src/styles/tailwind.css` 的 `@layer utilities` 中，
 *     以便随 `content` 扫描结果按需产出（不引入额外 plugin）。
 * ========================================================================== */
import { tokens } from './src/js/tokens.js'

/** 数值型 Token → CSS 长度（数值补 px；字符串原样透传，如 '9999px'） */
const toLength = (value) => (typeof value === 'number' ? `${value}px` : value)

/** 对 Token 对象整体做长度转换 */
const toSpacingScale = (source) =>
  Object.fromEntries(Object.entries(source).map(([key, value]) => [key, toLength(value)]))

/** 字体族字符串 → Tailwind 需要的数组（去空格，避免生成多余空白） */
const toFontStack = (value) => value.split(',').map((item) => item.trim())

export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        ch: {
          /* 背景 */
          base: tokens.bg.base,
          sidebar: tokens.bg.sidebar,
          surface: tokens.bg.surface,
          elevated: tokens.bg.elevated,
          input: tokens.bg.input,
          hover: tokens.bg.hover,
          /* 文字 */
          'text-primary': tokens.text.primary,
          'text-secondary': tokens.text.secondary,
          'text-tertiary': tokens.text.tertiary,
          'text-disabled': tokens.text.disabled,
          'text-inverse': tokens.text.inverse,
          /* 描边 */
          border: tokens.border.default,
          'border-light': tokens.border.light,
          'border-focus': tokens.border.focus,
          divider: tokens.border.divider,
          /* 主色 */
          primary: tokens.primary.base,
          'primary-hover': tokens.primary.hover,
          'primary-active': tokens.primary.active,
          'primary-subtle': tokens.primary.subtle,
          /* 状态 */
          success: tokens.status.success,
          warning: tokens.status.warning,
          danger: tokens.status.danger,
          info: tokens.status.info,
          /* 预览区（浅色隔离域，仅 .preview-scope 内可用） */
          'preview-bg': tokens.preview.bg,
          'preview-text': tokens.preview.text,
          'preview-border': tokens.preview.border,
        },
        plat: {
          wechat: tokens.platform.wechat_mp,
          xhs: tokens.platform.xiaohongshu,
          generic: tokens.platform.generic,
        },
      },
      // Preflight 的 `*` 默认 border-color 取自 theme('borderColor.DEFAULT')（Tailwind 默认是
      // 浅灰 #e5e7eb）；暗色下会给任何只设 border-width 的元素带上浅灰，故按 Token 覆盖默认值。
      borderColor: { DEFAULT: tokens.border.default },
      fontFamily: {
        cjk: toFontStack(tokens.font.cjk),
        latin: toFontStack(tokens.font.latin),
        mono: toFontStack(tokens.font.mono),
      },
      fontSize: {
        display: [toLength(tokens.fontSize.display), { lineHeight: '1.2', fontWeight: '700' }],
        h1: [toLength(tokens.fontSize.h1), { lineHeight: '1.35', fontWeight: '600' }],
        h2: [toLength(tokens.fontSize.h2), { lineHeight: '1.4', fontWeight: '600' }],
        h3: [toLength(tokens.fontSize.h3), { lineHeight: '1.5', fontWeight: '500' }],
        body: [toLength(tokens.fontSize.body), { lineHeight: '1.6' }],
        'body-s': [toLength(tokens.fontSize.bodyS), { lineHeight: '1.5' }],
        caption: [toLength(tokens.fontSize.caption), { lineHeight: '1.4' }],
        code: [toLength(tokens.fontSize.code), { lineHeight: '1.5' }],
      },
      spacing: tokens.space,
      borderRadius: toSpacingScale(tokens.radius),
      boxShadow: {
        raised: tokens.shadow.raised,
        modal: tokens.shadow.modal,
        focus: tokens.shadow.focus,
        device: tokens.shadow.device,
      },
      keyframes: {
        pulseSlow: {
          '0%,100%': { opacity: '1' },
          '50%': { opacity: '.45' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        // 时长统一取 tokens.motion（状态脉冲 2s / 骨架屏 shimmer 1.5s，见 §2.3.4）
        'pulse-slow': `pulseSlow ${tokens.motion.statusPulse.duration}ms ${tokens.motion.statusPulse.easing} infinite`,
        shimmer: `shimmer ${tokens.motion.shimmer.duration}ms ${tokens.motion.shimmer.easing} infinite`,
      },
    },
  },
  plugins: [],
}
