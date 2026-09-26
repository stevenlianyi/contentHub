/* ============================================================================
 * Mock 数据生成工具（确定性，禁止 Math.random）
 * ----------------------------------------------------------------------------
 * 裁定 D：mock 数据量大（topicqry ≥128 条），统一用**生成器函数**程序化产出，
 * 保证「同一份代码 → 同一份数据」，刷新页面数据不变，便于比对与复现。
 * ⚠️ 本文件属 `src/mock/data/` 目录增补（裁定 D 允许），生产构建随 mock 一并剔除。
 * ========================================================================== */

/** 数字定长补零 */
export const pad = (value, len = 2) => String(value).padStart(len, '0')

/** Date → 后端口径 14 位 `YYYYMMDDHHMMSS` */
export const ymdhms = (date) =>
  `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}` +
  `${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`

/** 基准时刻（固定值，保证生成数据不随运行时间漂移） */
export const BASE_TIME = new Date(2026, 8, 20, 12, 0, 0)

/** 相对基准时刻往前推 n 小时 */
export const hoursBefore = (hours) => new Date(BASE_TIME.getTime() - hours * 3600 * 1000)

/** 全局唯一的 Mock 基准号（模块级自增，保证 recID / fileID 不重复） */
let serial = 0
export const nextSerial = () => {
  serial += 1
  return serial
}
export const resetSerial = (value = 0) => {
  serial = value
}

/** 确定性线性同余发生器：返回 [0, 1) 的取值函数 */
export function lcg(seed) {
  let state = (seed >>> 0) || 1
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0
    return state / 4294967296
  }
}

/** 由种子生成 64 位小写十六进制串（用于 sha256 形态的 contentHash，避免硬编码超长字面量） */
export function hexHash(seed, length = 64) {
  const digits = '0123456789abcdef'
  let state = (Math.imul(seed + 7, 2654435761) >>> 0) || 11
  const out = []
  for (let i = 0; i < length; i += 1) {
    state = (Math.imul(state ^ (i + 1), 2246822519) + 374761393) >>> 0
    out.push(digits[(state >>> (i % 28)) & 15])
  }
  return out.join('')
}

/** 环形取项（越界自动回到开头） */
export const pick = (list, index) => list[index % list.length]

/** 确定性取整区间值 [min, max] */
export const between = (index, seed, min, max) => {
  const span = max - min + 1
  return min + ((Math.imul(index + 1, 1103515245) ^ (seed >>> 3)) >>> 8) % span
}
