// ============================================================
// 标准 crontab（5 段）校验工具（自基线工程 src/utils/cron.js 移植）
// ------------------------------------------------------------
// 与后端调度口径保持一致：CronTrigger.from_crontab(cronExpr)，
// 要求「分 时 日 月 周」共 5 段。
//
// 支持写法：
//   *            任意值
//   n            具体值
//   a-b          范围
//   */s          从最小值起按步长 s
//   a-b/s        范围内按步长 s
//   a,b,c        枚举（可混合以上形式）
//   月/星期 支持英文缩写：jan-dec / sun-sat
//
// 用途：P-11 / P-13 展示平台参数时的表达式校验。
// ============================================================

const MONTH_NAMES = {
  jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6,
  jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12
}

const DOW_NAMES = {
  sun: 0, mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6
}

// 字段顺序：分 时 日 月 周
const FIELD_SPECS = [
  { name: '分钟', min: 0, max: 59, names: null },
  { name: '小时', min: 0, max: 23, names: null },
  { name: '日', min: 1, max: 31, names: null },
  { name: '月', min: 1, max: 12, names: MONTH_NAMES },
  { name: '星期', min: 0, max: 7, names: DOW_NAMES }
]

const parseValue = (token, spec) => {
  const lower = String(token).toLowerCase()
  if (spec.names && lower in spec.names) {
    return spec.names[lower]
  }
  if (!/^\d+$/.test(token)) {
    return NaN
  }
  return parseInt(token, 10)
}

const validateField = (field, spec) => {
  if (!field) {
    return `${spec.name}段不能为空`
  }

  const items = field.split(',')
  for (const item of items) {
    if (!item) {
      return `${spec.name}段存在多余逗号`
    }

    const slashParts = item.split('/')
    if (slashParts.length > 2) {
      return `${spec.name}段步长格式错误：${item}`
    }
    const [rangePart, stepPart] = slashParts

    if (stepPart !== undefined) {
      if (!/^\d+$/.test(stepPart) || parseInt(stepPart, 10) < 1) {
        return `${spec.name}段步长必须为正整数：${item}`
      }
    }

    if (rangePart === '*') {
      continue
    }

    const rangeTokens = rangePart.split('-')
    if (rangeTokens.length > 2) {
      return `${spec.name}段范围格式错误：${item}`
    }

    const values = rangeTokens.map((token) => parseValue(token, spec))
    if (values.some((v) => Number.isNaN(v))) {
      return `${spec.name}段含非法值：${item}`
    }
    if (values.some((v) => v < spec.min || v > spec.max)) {
      return `${spec.name}段取值需在 ${spec.min}-${spec.max} 之间：${item}`
    }
    if (values.length === 2 && values[0] > values[1]) {
      return `${spec.name}段起始值大于结束值：${item}`
    }
  }

  return ''
}

/**
 * 校验 crontab 表达式
 * @param {string} expr 形如 "0 5 * * *"
 * @returns {string} 空字符串表示校验通过，否则返回错误原因
 */
export const validateCronExpr = (expr) => {
  const text = String(expr || '').trim()
  if (!text) {
    return 'cron 表达式不能为空'
  }

  const fields = text.split(/\s+/)
  if (fields.length !== 5) {
    return `cron 表达式需为 5 段（分 时 日 月 周），当前为 ${fields.length} 段`
  }

  for (let i = 0; i < FIELD_SPECS.length; i += 1) {
    const message = validateField(fields[i], FIELD_SPECS[i])
    if (message) {
      return message
    }
  }

  return ''
}

// 归一化：去除首尾空白并将中间多空格合并为单个空格
export const normalizeCronExpr = (expr) => String(expr || '').trim().split(/\s+/).join(' ')

// 常用示例，供编辑弹窗提示
export const CRON_EXAMPLES = [
  { expr: '0 5 * * *', desc: '每天 05:00' },
  { expr: '0 */6 * * *', desc: '每 6 小时' },
  { expr: '30 6 * * *', desc: '每天 06:30' },
  { expr: '* * * * *', desc: '每分钟' }
]
