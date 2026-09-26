/* ============================================================================
 * api 域：素材（subfunc/assetApi.py 的 9 个 CMD 中的 8 个，§2.9.3）
 * ----------------------------------------------------------------------------
 * `artifactpack`（同属 assetApi 域）按**页面归属**放在 `api/artifact.js`：
 * P-07 产物台账 / P-10 投递记录调用，且 Step 3 的 Mock 清单将它与 artifactqry 同组。
 *
 * 入参要点（§2.9.3）：
 *   - `assetadd` 二选一：`localPath`（服务端本地路径）或 `fileID` + `contentHash`（64 位小写 sha256）；
 *   - `topicassetadd` 幂等键 `{topicID}:{fileID}`，`sortOrder` 越小越靠前，`usageType ∈ {cover,body,inline}` 且封面唯一；
 *   - `topicassetmodify` 支持 `orderList` 批量重排。
 * 出参：文件类字段只读 `xxxUrl`（后端 fillFileUrls 转换，§2.4.5）。
 * ========================================================================== */
import { createService } from '@/utils/http'

const svc = createService()

export const assetQry = (params) => svc.post('/assetqry', params)
export const assetAdd = (params) => svc.post('/assetadd', params)
export const assetModify = (params) => svc.post('/assetmodify', params)
export const assetDel = (params) => svc.post('/assetdel', params)

/** 主题-素材关联（附图管理，P-03 Tab2 / P-04） */
export const topicAssetQry = (params) => svc.post('/topicassetqry', params)
export const topicAssetAdd = (params) => svc.post('/topicassetadd', params)
export const topicAssetModify = (params) => svc.post('/topicassetmodify', params)
export const topicAssetDel = (params) => svc.post('/topicassetdel', params)
