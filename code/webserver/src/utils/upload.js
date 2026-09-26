/* ============================================================================
 * 上传工具 · Step 8（P-04 素材上传的「两步流程」）
 * ----------------------------------------------------------------------------
 * 真实链路（★ 以后端事实为准，见计划附录 B 的 R-01 / R-12 / R-18）：
 *   第 1 步 `POST /upload`（multipart，表单字段名 **`file`**，该分支**不校验 token**）：
 *     nginx upload 模块在该路由注入 `file.path / file.name / file.size / file.md5` 后转交后端 `/hfile`；
 *     · `main/ylwzRecvFiles.py::fileHandler` 读的是 **nginx upload 模块注入**的表单字段
 *       （`file.path` / `file.name` / `file.size` / `file.md5`），**不解二进制本体**；
 *     · 返回体里服务端可读的本地完整路径是 **`fileName`** —— 正是 `assetadd.localPath` 所需形态；
 *       `fileUrl` 是**文件服务内部临时 key**（供 F0A0 转存永久存储），本工程**不用它**。
 *   第 2 步 `assetadd({ localPath, contentHash? })`：裁剪 / EXIF 剥离 / 缩略图 / 上云 /
 *     contentHash 内容级去重**全部由服务端完成**。
 * ★ 严禁「`assetadd({ fileID: fileUrl, contentHash })` 直接登记」：会把临时链接当永久 fileID
 *   落库，且临时文件会被文件服务的清理任务删除，形成死链。
 * ★ 本地直连后端**无法复现上传**（fileHandler 依赖 nginx upload 模块注入的字段）→
 *   本地开发走 Mock：`uploadTemp` 返回与真实 `fileName` **同形**的确定性伪本地路径，
 *   使「两步流程 + 去重演示」在 Mock 中完整闭环；assetadd 仍走 Mock 的业务规则，
 *   **不把失败静默吞掉、也不改为假成功**。真实链路留待部署环境（nginx 前置）联调。
 * ★ contentHash：`assetadd` 只有**在请求里带 contentHash** 且命中既有记录时才回 `dedupHit='1'`
 *   （`processor/assetService.py:698-710`）；服务端算出的 hash 与传入不符回 `C7`。
 *   故本文件在浏览器支持时用 SubtleCrypto 计算 sha256 一并上传（计算失败则不传，绝不错传）。
 * ========================================================================== */
import { settings } from '@/config/settings'
import { assetAdd } from '@/api/asset'

/** 上传通道地址（对齐真实上传通道 /upload；见 .env.development / .env.production 与 vite.config.js） */
export const uploadUrl = settings.uploadUrl

/** 上传/登记链路的可读错误（携带后端错误码，供面板逐条反馈） */
export class UploadError extends Error {
  constructor(code, message) {
    super(message)
    this.name = 'UploadError'
    this.code = code || ''
  }
}

const isMock = () => import.meta.env.VITE_USE_MOCK === 'true'

/**
 * Mock 专用：构造与真实 `fileName`（服务端本地完整路径）同形的确定性伪路径。
 * 同一份文件（名称 + 字节数 + 最后修改时间相同）必得同一路径，从而让
 * Mock 的 `assetadd`（模拟服务端按 localPath 计算 sha256 去重）可稳定演示 dedupHit='1'。
 */
function mockLocalPath(file) {
  const safeName = String(file?.name || 'unnamed').replace(/[\\/]/g, '_')
  return `/mock/hfile/temp/0/${safeName}__${Number(file?.size) || 0}__${Number(file?.lastModified) || 0}`
}

/**
 * 第 1 步：把文件送到上传通道，换回**服务端可读的本地路径**（`assetadd.localPath`）。
 * @param {File} file 待上传文件
 * @returns {Promise<string>} 服务端本地完整路径（真实返回 `fileName`）
 * @throws {UploadError} 通道不可达 / 非 B0 / 未返回路径
 */
export async function uploadTemp(file) {
  if (!file) throw new UploadError('C4', '未选择文件')

  if (isMock()) return mockLocalPath(file)

  const formData = new FormData()
  formData.append('file', file)

  let response
  try {
    response = await fetch(uploadUrl, { method: 'POST', body: formData })
  } catch (error) {
    throw new UploadError('D3', `上传通道不可达：${error?.message || error}`)
  }
  if (!response.ok) throw new UploadError('D3', `上传通道返回 HTTP ${response.status}`)

  let json
  try {
    json = await response.json()
  } catch (error) {
    throw new UploadError('D3', '上传通道返回内容不是合法 JSON')
  }

  const errCode = String(json?.errCode || '')
  if (errCode && errCode !== 'B0') {
    throw new UploadError(errCode, json?.MSG?.content || '上传失败')
  }
  // ★ 首选 fileName（服务端本地完整路径）；localPath / filePath 仅作兼容兜底
  const localPath = String(json?.fileName || json?.localPath || json?.filePath || '')
  if (!localPath) throw new UploadError('D3', '上传通道未返回服务端文件路径（fileName）')
  return localPath
}

/**
 * 第 2 步：登记素材（服务端完成裁剪 / EXIF 剥离 / 缩略图 / 上云 + contentHash 去重）。
 * @param {string} localPath 第 1 步换回的服务端本地路径
 * @param {object} [extra] 附加字段（如 contentHash / origName）
 * @returns {Promise<object>} `assetadd` 业务报文；`data.dedupHit === '1'` 表示命中既有素材
 */
export const registerAsset = (localPath, extra = {}) => assetAdd({ localPath, ...extra })

/**
 * 第 1 步换回的 `fileName` 是**服务端本地临时路径**，且 `ylwzRecvFiles.fileHandler` 会先把上传文件
 * `modifyFileName()` **改名成 UUID**（2026-09-24 起保留原扩展名，如 `/data/webserver/temp/8/b16c….jpg`）；
 * `assetService.uploadAssetFile` 又**不返回** `fileExt` / `mimeType`。
 * 因此「原始文件名 / 扩展名 / MIME」必须由前端回传，否则：
 *   · `ch_asset.origName` 会落成 UUID（P-04 列表的「文件名」与 `keyword` 搜索全失真）；
 *   · `ch_asset.fileExt` / `mimeType` 会为空（P-04 的「类型」筛选永不适配）。
 * 三者均在 `assetService.validateAssetFields` 的白名单内（origName ≤255 / fileExt ≤16 / mimeType ≤64）。
 */
export function assetMetaOf(file) {
  const name = String(file?.name || '')
  const match = /\.([A-Za-z0-9]+)$/.exec(name)
  return {
    origName: name,
    fileExt: match ? match[1].toLowerCase() : '',
    mimeType: String(file?.type || '')
  }
}

/**
 * 计算文件 sha256（小写十六进制）。用于让服务端回 `dedupHit='1'`。
 * 非安全上下文 / 浏览器不支持时返回 `''`（调用方**不传** contentHash，避免服务端 `C7`）。
 */
export async function sha256OfFile(file) {
  try {
    if (!globalThis.crypto?.subtle?.digest || !file?.arrayBuffer) return ''
    const buffer = await file.arrayBuffer()
    const digest = await globalThis.crypto.subtle.digest('SHA-256', buffer)
    return Array.from(new Uint8Array(digest))
      .map((byte) => byte.toString(16).padStart(2, '0'))
      .join('')
  } catch (error) {
    console.warn('[upload] 浏览器无法计算 sha256，本次不携带 contentHash：', error)
    return ''
  }
}

/** 把上传/登记错误翻译成可读文案（区分「本地文件不存在」与「上传失败」） */
export function describeUploadError(error) {
  const code = String(error?.code || error?.errCode || '')
  const backendText = error?.MSG?.content
  if (code === 'ERR_FILE_NOT_FOUND' || code === 'D4') {
    return `服务端找不到该本地文件（上传通道返回的路径无效）：${backendText || '请重新选择文件再试'}`
  }
  if (code === 'D3' || code === 'BL') return `上传失败：${backendText || error?.message || '请重试'}`
  if (code === 'C7') return `文件指纹校验未通过：${backendText || '请重新选择文件再试'}`
  if (code === 'D0') return `文件类型不允许：${backendText || '后端拒绝该扩展名'}`
  if (code === 'B8') return '会话已过期，请重新登录'
  return backendText || error?.message || '上传失败，请重试'
}
