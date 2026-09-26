/* ============================================================================
 * 通用纯函数集合 · Step 3 重写（计划 Step 3 要点 3）
 * ----------------------------------------------------------------------------
 * 硬约束：
 *   1) 本文件**只放纯函数**（输入 → 输出，无副作用）；唯一例外是 `copyText`，
 *      按计划要求「带 toast」，故它是本文件唯一引入 UI 依赖的函数（写剪贴板 + 提示）。
 *   2) ★ 禁止出现任何依赖组件实例（`this`）的函数——在 `<script setup>` 下无 this，调用即报错。
 *   3) 禁止硬编码颜色；本文件只做数据与文案处理。
 *
 * 字数口径（与后端 processor/topicService.py::countWords 严格一致，见计划 §2.7）：
 *   - `wordCount`：CJK 按字符、连续 [A-Za-z0-9] 串算 1 词、标点空白不计 —— 用于详述 2000–5000；
 *   - `charCount`：按 Unicode 码点计 —— 用于标题 ≤50、简介 ≤200。
 * ========================================================================== */
import { toast } from 'vue3-toastify'

/* 中文（CJK 统一表意文字，含扩展 A 区）按「字符」计 */
const CJK_PATTERN = /[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/g
/* 英文/数字按「词」计：连续 [A-Za-z0-9] 串算 1 个词，保留 don't / e-mail 这类内部连字符 */
const WORD_TOKEN_PATTERN = /[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*/g

const pad2 = (value) => String(value).padStart(2, '0')

/** 宽松解析：14 位 YMDHMS / 8 位日期 / Date / 毫秒时间戳 / 可被 Date 解析的字符串 → Date | null */
function toDate(value) {
  if (value === null || value === undefined || value === '') return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value
  if (typeof value === 'number') {
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? null : date
  }
  const text = String(value).trim()
  if (/^\d{14}$/.test(text)) {
    return new Date(
      Number(text.slice(0, 4)), Number(text.slice(4, 6)) - 1, Number(text.slice(6, 8)),
      Number(text.slice(8, 10)), Number(text.slice(10, 12)), Number(text.slice(12, 14))
    )
  }
  if (/^\d{8}$/.test(text)) {
    return new Date(Number(text.slice(0, 4)), Number(text.slice(4, 6)) - 1, Number(text.slice(6, 8)))
  }
  const parsed = new Date(text)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

/**
 * 时间格式化：14 位 `YYYYMMDDHHMMSS` → `YYYY-MM-DD HH:mm:ss`。
 * @param {string|number|Date} value 后端 YMDHMS / Date / 毫秒时间戳
 * @param {string} pattern 支持 YYYY MM DD HH mm ss
 * @returns {string} 空值返回 `""`；无法解析时**原样返回入参**
 */
export function formatYMDHMS(value, pattern = 'YYYY-MM-DD HH:mm:ss') {
  if (value === null || value === undefined || value === '') return ''
  const date = toDate(value)
  if (!date) return value
  const map = {
    YYYY: String(date.getFullYear()),
    MM: pad2(date.getMonth() + 1),
    DD: pad2(date.getDate()),
    HH: pad2(date.getHours()),
    mm: pad2(date.getMinutes()),
    ss: pad2(date.getSeconds())
  }
  return pattern.replace(/YYYY|MM|DD|HH|mm|ss/g, (key) => map[key])
}

/**
 * 产物保留期文案（`ch_artifact.expireYMDHMS`，裁定 E；语义见 `database/ch_artifact.txt:14`）。
 *
 * ★ 空值（`''` / `0` / `null` / `undefined`）= **未设置保留期 = 不清理** → 「长期保留」，
 *   **不得**显示为「已过期」：是否过期只由 `artifactStatus === 'EXPIRED'` 决定。
 *   后端保留期为 14 位 `YYYYMMDDHHMMSS`（附录 B R-26 以字符串返回）。
 * @param {string|number|null|undefined} expireYMDHMS
 * @returns {string} 「长期保留」或「保留至 YYYY-MM-DD」
 */
export function artifactRetentionText(expireYMDHMS) {
  const raw = expireYMDHMS === null || expireYMDHMS === undefined ? '' : String(expireYMDHMS).trim()
  if (!raw || raw === '0' || !/^\d{8,14}$/.test(raw)) return '长期保留'
  const date = formatYMDHMS(raw, 'YYYY-MM-DD')
  return date ? `保留至 ${date}` : '长期保留'
}

/** 解析后端时间串为 Date（非法输入返回 null，不抛异常）；供排序 / 差值计算用 */
export function parseDateTime(value) {
  return toDate(value)
}

/**
 * 相对时间文案。
 * @returns {{ text: string, absolute: string }} `text` 供正文展示；
 *          `absolute`（`YYYY-MM-DD HH:mm:ss`）供 `title` 属性展示绝对时间。
 *          无法解析时返回 `{ text: '', absolute: '' }`。
 */
export function fromNow(value) {
  const date = toDate(value)
  if (!date) return { text: '', absolute: '' }
  const absolute = formatYMDHMS(date)
  const diff = Date.now() - date.getTime()
  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour
  let text
  if (diff < 0) text = absolute
  else if (diff < minute) text = '刚刚'
  else if (diff < hour) text = `${Math.floor(diff / minute)} 分钟前`
  else if (diff < day) text = `${Math.floor(diff / hour)} 小时前`
  else if (diff < 2 * day) text = '昨天'
  else if (diff < 30 * day) text = `${Math.floor(diff / day)} 天前`
  else text = absolute
  return { text, absolute }
}

/**
 * 字数统计，口径与后端 countWords 一致：
 * 中文按字符、连续 [A-Za-z0-9] 串算 1 词、标点空白换行不计。
 * 用途：主题详述 2000–5000 字区间校验（WordCounter）。
 */
export function wordCount(text) {
  if (!text) return 0
  const source = typeof text === 'string' ? text : String(text)
  const cjk = source.match(CJK_PATTERN)
  const tokens = source.match(WORD_TOKEN_PATTERN)
  return (cjk ? cjk.length : 0) + (tokens ? tokens.length : 0)
}

/** 字符数统计（按 Unicode 码点计），口径与后端 len(title) / len(summary) 一致：标题 ≤50、简介 ≤200 */
export function charCount(text) {
  if (!text) return 0
  return Array.from(typeof text === 'string' ? text : String(text)).length
}

/**
 * 是否越过上限（§2.7 两套校验口径的统一判定入口）。
 * @param {number} current 当前长度（`charCount` 或 `wordCount` 的结果）
 * @param {number} max 上限
 * @param {number} min 下限，缺省 0
 * @returns {boolean} 越界（>max 或 <min）返回 true
 */
export function isOverLimit(current, max, min = 0) {
  const value = Number(current) || 0
  return value > Number(max) || value < Number(min)
}

/** 字节数 → 人类可读体积（B / KB / MB / GB） */
export function formatBytes(bytes, decimals = 1) {
  const size = Number(bytes)
  if (!Number.isFinite(size) || size <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.min(Math.floor(Math.log(size) / Math.log(1024)), units.length - 1)
  const value = size / 1024 ** index
  return `${index === 0 ? value : value.toFixed(decimals)} ${units[index]}`
}

/**
 * 毫秒 → 人类可读时长（Step 11 裁定 G：渲染任务「耗时」列）。
 * 口径：<1s → `820ms`；<60s → `8.2s`（一位小数，整数省略 `.0`）；<60min → `1m12s`；≥60min → `1h02m`。
 * @param {string|number} ms 后端 `costMs`（★ 真实后端以字符串返回，R-26，内部一律 `Number()`）
 * @param {string} emptyText 未完成 / 非法值的占位文案（缺省 `—`，与「未完成显示 —」口径一致）
 * @returns {string}
 */
export function formatDuration(ms, emptyText = '—') {
  const value = Number(ms)
  if (!Number.isFinite(value) || value <= 0) return emptyText
  if (value < 1000) return `${Math.round(value)}ms`
  const totalSeconds = value / 1000
  if (totalSeconds < 60) return `${totalSeconds.toFixed(1).replace(/\.0$/, '')}s`
  const roundedSeconds = Math.round(totalSeconds)
  const minutes = Math.floor(roundedSeconds / 60)
  if (minutes < 60) return `${minutes}m${pad2(roundedSeconds % 60)}s`
  return `${Math.floor(minutes / 60)}h${pad2(minutes % 60)}m`
}

/** 防抖：返回的函数带 `cancel()`，便于组件卸载时清理 */
export function debounce(fn, wait = 300) {
  let timer = null
  const debounced = (...args) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      fn(...args)
    }, wait)
  }
  debounced.cancel = () => {
    if (timer) clearTimeout(timer)
    timer = null
  }
  return debounced
}

/**
 * 复制文本到剪贴板（失败降级到 `document.execCommand('copy')`）+ toast 提示。
 * ★ 本文件唯一带 UI 副作用的函数（计划 Step 3 要点 3 明确要求「带 toast」）。
 * @returns {Promise<boolean>}
 */
export async function copyText(text) {
  const value = text === null || text === undefined ? '' : String(text)
  if (!value) return false
  const fallback = () => {
    const area = document.createElement('textarea')
    area.value = value
    area.setAttribute('readonly', 'readonly')
    area.style.position = 'fixed'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(area)
    return ok
  }
  try {
    let ok = false
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value)
      ok = true
    } else {
      ok = fallback()
    }
    if (ok) toast.success('已复制到剪贴板')
    else toast.error('复制失败，请手动选择复制')
    return ok
  } catch (error) {
    console.error('[common] 复制失败：', error)
    try {
      const ok = fallback()
      if (ok) toast.success('已复制到剪贴板')
      return ok
    } catch (innerError) {
      console.error('[common] 复制降级方案失败：', innerError)
      toast.error('复制失败，请手动选择复制')
      return false
    }
  }
}

/**
 * 凭据掩码：保留前 4 后 4，中间以 `••••` 替代（P-11 账号凭据展示）。
 * @param {string} secret 原文
 * @param {number} head 保留头部位数（默认 4）
 * @param {number} tail 保留尾部位数（默认 4）
 */
export function maskSecret(secret, head = 4, tail = 4) {
  const value = secret === null || secret === undefined ? '' : String(secret)
  if (!value) return ''
  if (value.length <= head + tail) return '•'.repeat(value.length)
  return `${value.slice(0, head)}${'•'.repeat(4)}${value.slice(value.length - tail)}`
}

/**
 * 查询类请求的公共字段生成器（§2.4.3；Step 3 要点 7）。
 * `sessionID` 不在此处注入（由 utils/http.js 请求拦截统一写请求体，避免两处维护）。
 * @param {object} params 业务字段 + `beginNum` / `endNum`
 * @returns {object} 含 lang / clientType / SN / mode / beginNum / endNum / forceFlashFlag
 */
export function buildQueryParam(params = {}) {
  const { beginNum = 0, endNum = 20, sn, mode = 'full', forceFlashFlag = '0', ...rest } = params
  return {
    lang: 'CN',
    clientType: 'web',
    SN: sn === undefined ? Date.now() : sn,
    mode,
    beginNum,
    endNum,
    forceFlashFlag,
    ...rest
  }
}

/** 截断字符串并在末尾追加省略号 */
export function truncateString(str, maxLength) {
  const source = str === null || str === undefined ? '' : String(str)
  if (source.length <= maxLength) return source
  return `${source.substring(0, maxLength)}...`
}

/** 是否为图片扩展名（上传前置校验） */
export function isImageFile(str) {
  return /\.(jpg|jpeg|png|gif|webp)$/i.test(String(str || ''))
}

/** dataURL → File（上传登记场景用） */
export function dataURLtoFile(dataurl, filename) {
  const arr = String(dataurl).split(',')
  const mime = arr[0].match(/:(.*?);/)[1]
  const bstr = atob(arr[1])
  let n = bstr.length
  const u8arr = new Uint8Array(n)
  while (n--) {
    u8arr[n] = bstr.charCodeAt(n)
  }
  return new File([u8arr], filename, { type: mime })
}

/** 列表按 key1 === value 命中后取 key2 的值（未命中返回空串） */
export function getListObjectValue2(list, key1, value, key2) {
  if (!Array.isArray(list)) return ''
  const hit = list.find((item) => item && item[key1] === value)
  return hit ? hit[key2] : ''
}
