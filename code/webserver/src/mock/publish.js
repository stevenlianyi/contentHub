/* ============================================================================
 * Mock · 投递域（publishpush 二次确认 F4 / 撤销 F1·F5 / 平台红线 C7 + 发布记录台账）
 * ----------------------------------------------------------------------------
 * ★ 2026-09-22（Step 14）按**真实后端事实**（`processor/publishService.py:717-1108`、
 *   `common/mysqlCommon.py::query_ch_publish_record:496-516`、`ch_publish_record.txt`）重写：
 *   ① 记录列改用权威列名：`recID / idempotencyKey / artifactId / topicID / accountID / platform /
 *      deliverMode / requestJson / responseJson / errcode / errmsg / success / remoteID / operator /
 *      pushedYMDHMS / label / memo / regID / regYMDHMS / modifyID / modifyYMDHMS / delFlag`。
 *      ★ 列名是 `artifactId`（小写 d）；**无主题标题列**、**无 autoPublishFlag 列**、无 publishStatus 列。
 *      故本 Mock **不再返回** `topicTitle / accountName / layoutCode / publishStatus`（否则前端会写成
 *      「Mock 通过、真实后端一片空白」）。结果语义 = `success` + `delFlag` 组合表达。
 *   ② 执行顺序与真实后端一致（★ 决定前端两步确认的语义）：
 *      平台红线 → deliverMode=draft_box → 账号 + 凭据（失败 F0）→ 产物前置 → 幂等（命中 F1）→
 *      **二次确认（缺 confirmFlag → F4，回显 idempotencyKey/confirmToken）** → 自动发布闸门（F6）→
 *      **合规闸门（复用 publishcheck，未过 → 返回合规侧 errCode + data.compliance）** → 落库 + 审计。
 *      ★ 注意 F4 在合规闸门**之前**：前端首次调用（不带确认参数）必定拿到 F4，与合规是否通过无关。
 *   ③ `publishpush` 的 `topicID` = `ch_topic.recID`（后端不读 topicCode；此处仅容忍入参便于联调）。
 *   ④ 幂等键形态 `{artifactID}:{accountID}:{uuid4}` 由**服务端下发**，前端原样回传（Mock 内生成）。
 *   ⑤ 撤销 = `delFlag='1'`（软删）；`publishrecordqry` 与真实数据层同款口径
 *      （`delFlag='0' OR delFlag IS NULL`）→ **已撤销记录默认不再出现在列表**（该差异已登记为待确认项，
 *      前端在本地先标记「已撤销」再做刷新并给出说明）。
 *   ⑥ `beginYMDHMS/endYMDHMS` 过滤 `pushedYMDHMS`；`order` 三态与 `queryTableGeneral` 一致
 *      （`modify` → modifyYMDHMS DESC；`create` → recID ASC；其他 → recID DESC）。
 *   ⑦ ★ 2026-09-22（对齐后端 R-31）：`publishrecordqry` 支持 **`accountID`** 过滤
 *      （`ch_publish_record.accountID` = `ch_account.recID`，用于 P-11 删除确认的「关联发布记录」条数）；
 *      该条件同样**进入 `indexKey`**（与 R-28 同口径，避免命中别的筛选组合的缓冲）。
 *      ⚠ Mock 种子记录的 `accountID` 用的是 `ch_account.accountID` 形态（`ACC-00x`），
 *      故先把入参归一为「同一条账号的多种键」再匹配；真实后端为纯数值等值比较。
 *
 * 可触发路径（开发态）：
 *   · 缺 `confirmFlag` → `F4` + `data{idempotencyKey, confirmToken, confirmFlagKey, confirmTokenKey}`；
 *   · `confirmToken` 不匹配 → `F4` + `data{idempotencyKey, confirmToken}`；
 *   · `idempotencyKey` 命中既有记录 → `F1` + `data{idempotencyKey, publishRecordID, success, revoked…}`；
 *   · `platform !== 'wechat_mp'` → `C7`（★ 小红书 / 通用仅导出素材包，无任何自动发布入口）；
 *   · 账号 `healthStatus === 'INVALID'` → `F0`（真实后端在此把账号置 INVALID）；
 *   · 合规未过 → 合规侧 errCode（C4/C5/C6/C7/D1/D3/D4/E3）+ `data.compliance`；
 *   · `action='revoke'`：无记录 → `CB`；未成功投递 → `C7`；已撤销 → `F1`；逾窗 → `F5`。
 * ========================================================================== */
import { ARTIFACTS, PUBLISH_RECORDS } from './data/records'
import { TOPICS } from './data/topic'
import { pad } from './data/util'
import { mockAccounts } from './account'
import { handlers as complianceHandlers } from './compliance'

/** 撤销窗秒数（真实后端取 `WECHAT_REVOKE_WINDOW_SECONDS`，默认 60；出参一律以服务端 `windowSeconds` 为准） */
const REVOKE_WINDOW_SECONDS = 60

/** 合规侧错误码（首条 ERROR 的 errCode；与 `complianceService.summarizeIssues` 同口径） */
const COMPLIANCE_ERR_FALLBACK = 'C7'

function now14() {
  const d = new Date()
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
}

/** 14 位 YMDHMS → 毫秒（非法返回 0） */
function parseYMDHMS(text) {
  const value = String(text || '')
  if (value.length < 14) return 0
  const d = new Date(
    Number(value.slice(0, 4)), Number(value.slice(4, 6)) - 1, Number(value.slice(6, 8)),
    Number(value.slice(8, 10)), Number(value.slice(10, 12)), Number(value.slice(12, 14))
  )
  return Number.isNaN(d.getTime()) ? 0 : d.getTime()
}

/**
 * 种子记录 → 权威列（`ch_publish_record`）。
 * 种子（`mock/data/records.js`）用 `publishStatus` 表达结果，按真实口径换算：
 * `PUBLISHED/DRAFTED → success='1'`、`FAILED → success='0'` + `errcode/errmsg`；`delFlag='0'`。
 */
function normalizeSeed(item) {
  const failed = String(item.publishStatus || '').toUpperCase() === 'FAILED'
  const pushed = String(item.createdAtYMDHMS || item.regYMDHMS || '')
  return {
    recID: String(item.recID || ''),
    idempotencyKey: String(item.idempotencyKey || `IDEM-${String(item.recID || '').slice(-6)}`),
    artifactId: String(item.artifactID || ''),
    topicID: String(item.topicID || ''),
    accountID: String(item.accountID || ''),
    platform: String(item.platform || 'wechat_mp'),
    deliverMode: String(item.deliverMode || 'draft_box'),
    requestJson: JSON.stringify({ topicID: String(item.topicID || ''), artifactId: String(item.artifactID || '') }),
    responseJson: JSON.stringify({ remoteID: String(item.remoteID || ''), costMs: Number(item.costMs) || 0 }),
    errcode: failed ? String(item.errorCode || '') : '',
    errmsg: failed ? String(item.errorMsg || '') : '',
    success: failed ? '0' : '1',
    remoteID: String(item.remoteID || ''),
    operator: String(item.operator || ''),
    pushedYMDHMS: pushed,
    label: '',
    memo: '',
    regID: 'system',
    regYMDHMS: pushed,
    modifyID: 'system',
    modifyYMDHMS: pushed,
    delFlag: '0'
  }
}

const state = {
  records: PUBLISH_RECORDS.map(normalizeSeed),
  pending: new Map(), // idempotencyKey → { confirmToken, params }
  seq: PUBLISH_RECORDS.length
}

/** topicID 语义（裁定 A）：`topicID = ch_topic.recID`；仅容忍 topicCode 便于手工联调 */
const findTopic = (body) =>
  TOPICS.find(
    (item) =>
      (body.topicID && (item.recID === String(body.topicID) || item.topicCode === String(body.topicID))) ||
      (body.topicCode && item.topicCode === String(body.topicCode))
  )

const findAccount = (body) => {
  const key = String(body.accountID || body.accountCode || '')
  if (!key) return mockAccounts.find((item) => item.platform === 'wechat_mp') || null
  return mockAccounts.find((item) => item.accountID === key || item.recID === key || item.accountCode === key) || null
}

/** 幂等键派生二次确认令牌（真实后端：sha256('contenthub.publish.confirm:' + key)[:32]） */
const buildConfirmToken = (idempotencyKey) => `CFM-${String(idempotencyKey).slice(-24)}`

/** 幂等键形态校验：`{数字}:{数字}:{非空}`（`publishService.isValidIdempotencyKey`） */
function isValidIdempotencyKey(key) {
  const parts = String(key || '').split(':')
  return parts.length >= 3 && parts[0] !== '' && parts[1] !== '' && parts.slice(2).join(':') !== ''
}

const buildIdempotencyKey = (artifactID, accountID) =>
  `${Number(artifactID) || 0}:${Number(accountID) || 0}:${Math.random().toString(16).slice(2, 10)}`

/** 结构化失败（`__err.data` 会落进信封 `data`，与真实后端一致） */
const fail = (code, content, data) => ({ __err: { code, content, data } })

/** 排序：三态与 `common/mysqlCommon.queryTableGeneral:290-295` 一致 */
function sorted(list, order) {
  const copy = [...list]
  if (order === 'modify') {
    return copy.sort((a, b) => String(b.modifyYMDHMS).localeCompare(String(a.modifyYMDHMS)))
  }
  if (order === 'create') {
    return copy.sort((a, b) => String(a.recID).localeCompare(String(b.recID)))
  }
  return copy.sort((a, b) => String(b.recID).localeCompare(String(a.recID)))
}

/** 合规闸门：真实后端在投递内部自动调 `publishcheck`（未过 → 返回合规侧 errCode） */
function runComplianceGate({ topicID, platform, layoutCode, accountID }) {
  const rtn = complianceHandlers.publishcheck({ topicID, platform, layoutCode, accountID })
  if (rtn && rtn.__err) return { __err: rtn.__err }
  const data = rtn?.data || {}
  if (Number(data.errorCount) > 0) {
    const firstError = (data.issues || []).find((item) => String(item.level).toUpperCase() === 'ERROR') || {}
    return fail(
      String(firstError.errCode || COMPLIANCE_ERR_FALLBACK),
      String(firstError.message || '未通过合规校验'),
      { compliance: data }
    )
  }
  return null
}

/** 撤销分支（`publishService.revokePublish:1028-1108`） */
function revokePublish(body) {
  const publishRecordID = String(body.publishRecordID || '')
  const idempotencyKey = String(body.idempotencyKey || '')
  if (!publishRecordID && !idempotencyKey) {
    return fail('C4', '撤销需提供 publishRecordID 或 idempotencyKey')
  }
  const record = state.records.find(
    (item) => (publishRecordID && item.recID === publishRecordID) || (idempotencyKey && item.idempotencyKey === idempotencyKey)
  )
  if (!record) return fail('CB', '无此发布记录，无法撤销')

  if (String(record.delFlag) === '1') {
    return fail('F1', '该发布记录已撤销（幂等命中）', { publishRecordID: record.recID, revoked: '1' })
  }
  if (String(record.success) !== '1') {
    return fail('C7', `该发布记录未成功投递（success=${record.success || '0'}），不可撤销`)
  }

  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - parseYMDHMS(record.pushedYMDHMS)) / 1000))
  if (elapsedSeconds > REVOKE_WINDOW_SECONDS) {
    return fail('F5', `撤销被拒：已超出撤销窗（撤销窗 ${REVOKE_WINDOW_SECONDS}s）`, {
      publishRecordID: record.recID,
      elapsedSeconds,
      windowSeconds: REVOKE_WINDOW_SECONDS
    })
  }

  record.delFlag = '1'
  record.modifyID = String(body.operator || 'system')
  record.modifyYMDHMS = now14()
  record.memo = `revoked_at=${record.modifyYMDHMS}, elapsed=${elapsedSeconds}s`
  return {
    data: {
      publishRecordID: record.recID,
      idempotencyKey: record.idempotencyKey,
      revoked: '1',
      elapsedSeconds,
      windowSeconds: REVOKE_WINDOW_SECONDS,
      remoteID: record.remoteID,
      auditWritten: '1',
      costMs: 42,
      note: '已撤销（本地发布记录置 delFlag=1）；平台侧草稿如需删除请人工在后台处理'
    }
  }
}

export const handlers = {
  publishpush: (body) => {
    if (String(body.action || 'push').toLowerCase() === 'revoke') return revokePublish(body)

    // 1) 通道判定（平台红线）
    const platform = String(body.platform || '')
    if (!platform) return fail('C4', 'platform 为必填字段')
    if (platform !== 'wechat_mp') {
      return fail(
        'C7',
        platform === 'xiaohongshu'
          ? '平台 xiaohongshu 不提供投递/发布通道（平台红线：小红书只导出素材包，绝不投递/发布）'
          : `平台无投递通道：platform=${platform}，可投递=['wechat_mp']`
      )
    }

    const topic = findTopic(body)
    if (!topic) return fail('CB', '未查询到该主题（topicID 需为 ch_topic.recID）')

    // 2) 账号 + 凭据（解密失败 → F0，真实后端同时把账号置 INVALID）
    const account = findAccount(body)
    if (!account) return fail('CB', '未查询到可用账号，请先到账号管理登记公众号凭据')
    if (String(account.healthStatus) === 'INVALID') {
      return fail('F0', '凭据解密失败：账号凭据已失效，请在账号管理重新登记')
    }
    const accountID = String(account.recID || account.accountID)

    // 3) 产物前置（★ draft_box 下 artifactID 非必需，但传了就必须 READY）
    const artifactID = String(body.artifactID || '')
    if (artifactID) {
      const artifact = ARTIFACTS.find((item) => String(item.recID) === artifactID)
      if (!artifact) return fail('C7', `产物记录标识无效：artifactID=${artifactID}`)
      if (String(artifact.artifactStatus) !== 'READY') {
        return fail('C7', `产物未就绪（artifactStatus=${artifact.artifactStatus}），请先重新渲染出可用产物`)
      }
    }

    // 4) 版式（投递需现场渲染）
    const layoutCode = String(body.layoutCode || '')
    if (!layoutCode) return fail('C4', 'layoutCode 为必填字段（投递需现场渲染平台形态产物）')

    // 5) 幂等 + 二次确认（★ 幂等键缺省由服务端生成，前端必须原样回传）
    let idempotencyKey = String(body.idempotencyKey || '')
    if (idempotencyKey) {
      if (!isValidIdempotencyKey(idempotencyKey)) {
        return fail('C7', `idempotencyKey 形态非法：应为 {artifactID}:{accountID}:{uuid4}，实为 ${idempotencyKey}`)
      }
    } else {
      idempotencyKey = buildIdempotencyKey(artifactID, accountID)
    }

    const duplicate = state.records.find((item) => item.idempotencyKey === idempotencyKey)
    if (duplicate) {
      return fail('F1', '幂等命中：该 idempotencyKey 已投递（不产生第二条发布记录）', {
        idempotencyKey,
        publishRecordID: duplicate.recID,
        remoteID: duplicate.remoteID,
        success: duplicate.success,
        revoked: String(duplicate.delFlag) === '1' ? '1' : '0',
        pushedYMDHMS: duplicate.pushedYMDHMS
      })
    }

    const confirmToken = buildConfirmToken(idempotencyKey)
    const confirmFlagOn = ['1', 'true', 'yes', 'on'].includes(String(body.confirmFlag || '').toLowerCase())
    if (!confirmFlagOn) {
      return fail('F4', '投递前必须人工二次确认：请传 confirmFlag=1（推送≠发布，最终群发须人工在后台完成）', {
        idempotencyKey,
        confirmToken,
        confirmFlagKey: 'confirmFlag',
        confirmTokenKey: 'confirmToken'
      })
    }
    if (String(body.confirmToken || '') !== confirmToken) {
      return fail('F4', '二次确认信息不匹配，请重新确认后再推送', { idempotencyKey, confirmToken })
    }

    // 6) 自动发布闸门（★ 前端永不传 autoPublish；此处仅做后端语义兜底）
    if (['1', 'true', 'yes', 'on'].includes(String(body.autoPublish || '').toLowerCase())) {
      return fail('F6', '自动发布闸门未开启：本期仅支持推送草稿，群发请到公众号后台手动完成')
    }

    // 7) 合规闸门（服务端内部自动调用 publishcheck）
    const gate = runComplianceGate({ topicID: topic.recID, platform, layoutCode, accountID: String(account.accountID || '') })
    if (gate) {
      gate.__err.data = { ...(gate.__err.data || {}), idempotencyKey }
      return gate
    }

    // 8) 落库（成功）+ 审计
    state.seq += 1
    const pushedYMDHMS = now14()
    const remoteID = `draft_media_${pad(9000 + state.seq, 6)}`
    const record = {
      recID: `PR${pad(state.seq, 6)}`,
      idempotencyKey,
      artifactId: artifactID,
      topicID: String(topic.recID),
      accountID,
      platform,
      deliverMode: 'draft_box',
      requestJson: JSON.stringify({ topicID: String(topic.recID), layoutCode, artifactID, accountID }),
      responseJson: JSON.stringify({ remoteID, errcode: 0, errmsg: 'ok' }),
      errcode: '',
      errmsg: '',
      success: '1',
      remoteID,
      operator: String(body.operator || ''),
      pushedYMDHMS,
      label: '',
      memo: 'draft delivered',
      regID: String(body.operator || 'system'),
      regYMDHMS: pushedYMDHMS,
      modifyID: String(body.operator || 'system'),
      modifyYMDHMS: pushedYMDHMS,
      delFlag: '0'
    }
    state.records.unshift(record)

    return {
      data: {
        idempotencyKey,
        publishRecordID: record.recID,
        recordWritten: '1',
        auditWritten: '1',
        platform,
        deliverMode: 'draft_box',
        artifactID: Number(artifactID) || 0,
        topicID: String(topic.recID),
        accountID,
        remoteID,
        success: '1',
        pushedYMDHMS,
        autoPublish: '0',
        publishID: '',
        transferredImageCount: 0,
        compliance: { passed: '1' },
        costMs: 1480,
        note: '草稿已投递（推送≠发布）；最终群发须人工在公众号后台完成'
      }
    }
  },

  /**
   * 发布记录台账（服务端筛选）。
   * ★ 与真实数据层同款：`delFlag='0' OR delFlag IS NULL` → **已撤销（delFlag='1'）记录默认不返回**。
   */
  publishrecordqry: (body, ctx) => {
    const recID = String(body.recID || '')
    const idempotencyKey = String(body.idempotencyKey || '')
    const artifactId = String(body.artifactID || body.artifactId || '')
    const topicID = String(body.topicID || '')
    const accountID = String(body.accountID || '')
    const platform = String(body.platform || '')
    const success = String(body.success || '')
    const beginYMDHMS = String(body.beginYMDHMS || '')
    const endYMDHMS = String(body.endYMDHMS || '')
    const order = String(body.order || 'create')

    let list = sorted(state.records, order).filter((item) => String(item.delFlag) !== '1')
    if (recID) list = list.filter((item) => item.recID === recID)
    if (idempotencyKey) list = list.filter((item) => item.idempotencyKey === idempotencyKey)
    if (artifactId) list = list.filter((item) => item.artifactId === artifactId)
    if (topicID) list = list.filter((item) => item.topicID === topicID)
    if (accountID) {
      // ★ R-31：真实后端按 `ch_publish_record.accountID`（= ch_account.recID）等值过滤；
      //   Mock 种子记录存的是 accountID 形态，故把入参归一为同一账号的多种键后再匹配。
      const account = mockAccounts.find((item) => (
        String(item.recID) === accountID
        || String(item.accountID) === accountID
        || String(item.accountCode) === accountID
      ))
      const keys = new Set([accountID])
      if (account) {
        keys.add(String(account.recID))
        keys.add(String(account.accountID))
        if (account.accountCode) keys.add(String(account.accountCode))
      }
      list = list.filter((item) => keys.has(String(item.accountID)))
    }
    if (platform) list = list.filter((item) => item.platform === platform)
    if (success) list = list.filter((item) => item.success === success)
    if (beginYMDHMS) list = list.filter((item) => String(item.pushedYMDHMS) >= beginYMDHMS)
    if (endYMDHMS) list = list.filter((item) => String(item.pushedYMDHMS) <= endYMDHMS)

    // ★ 与后端一致：过滤条件进入 indexKey（不同筛选组合不得共用同一查询缓冲）
    const indexKey = [recID, idempotencyKey, artifactId, topicID, accountID, platform, success, beginYMDHMS, endYMDHMS, order].join('|')
    return ctx.paginate(list, body, 'publishrecordqry', indexKey)
  },

  publishrecordadd: (body) => {
    state.seq += 1
    const record = {
      recID: `PR${pad(state.seq, 6)}`,
      idempotencyKey: String(body.idempotencyKey || `IDEM-${pad(state.seq, 6)}`),
      artifactId: String(body.artifactID || ''),
      topicID: String(body.topicID || ''),
      accountID: String(body.accountID || ''),
      platform: String(body.platform || 'wechat_mp'),
      deliverMode: String(body.deliverMode || 'draft_box'),
      requestJson: JSON.stringify(body),
      responseJson: '',
      errcode: '',
      errmsg: '',
      success: String(body.success || '0'),
      remoteID: String(body.remoteID || ''),
      operator: String(body.operator || 'system'),
      pushedYMDHMS: now14(),
      label: '',
      memo: '',
      regID: 'system',
      regYMDHMS: now14(),
      modifyID: 'system',
      modifyYMDHMS: now14(),
      delFlag: '0'
    }
    state.records.unshift(record)
    return { data: record }
  },

  publishrecordmodify: (body) => {
    const index = state.records.findIndex(
      (item) => item.recID === String(body.recID || '') || item.idempotencyKey === String(body.idempotencyKey || '')
    )
    if (index < 0) return fail('BI', '投递记录标识无效')
    state.records[index] = {
      ...state.records[index],
      ...body,
      recID: state.records[index].recID,
      modifyYMDHMS: now14()
    }
    return { data: state.records[index] }
  },

  publishrecorddel: (body) => {
    const index = state.records.findIndex((item) => item.recID === String(body.recID || ''))
    if (index < 0) return fail('BI', '投递记录标识无效')
    const [removed] = state.records.splice(index, 1)
    return { data: { success: '1', recID: removed.recID } }
  }
}

export const mockPublishRecords = state.records
export default handlers
