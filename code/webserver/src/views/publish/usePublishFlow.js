/* ============================================================================
 * usePublishFlow · P-10 / P-03 Tab5「投递编排」（Step 14 · 越界授权文件，裁定 K）
 * ----------------------------------------------------------------------------
 * 【为什么独立成文件】`DeliverPanel.vue`（双通道卡片）与两个宿主页（P-10 / Tab5）共用同一套
 *   取数与动作编排；把逻辑收在本文件才能满足「单文件 ≤ 600 行」（§2.1）。
 *
 * 【后端事实（已核源码，服从；不得凭计划文字臆断）】
 *   · `publishpush`（`processor/publishService.py:717-1021`）执行顺序：
 *     平台红线 → deliverMode=draft_box → adapter.deliver → **账号解析 + 凭据解密（失败 F0，并把账号置
 *     INVALID）** → 产物前置 → **幂等（命中 F1，data 回显原记录）** → **二次确认（缺 confirmFlag → F4，
 *     data 回显 idempotencyKey + confirmToken）** → 自动发布闸门（仅当 `autoPublish` 为真才检查，不足 F6）
 *     → **合规闸门（服务端内部自动调 publishcheck；未过 → 返回合规侧 errCode + data.compliance）** →
 *     取数 → access_token → render → package → deliver（草稿）→ 落库 + 审计。
 *     ★ 推论 1：**F4 在合规闸门之前** → 首次调用（不带确认参数）必定拿到 F4，与合规是否通过无关。
 *     ★ 推论 2：幂等键形态 `{artifactID}:{accountID}:{uuid4}`（`:234-252`）由服务端下发，
 *       前端**只回传、不构造**；两次调用的 `topicID/layoutCode/artifactID/accountID` 必须完全一致，
 *       否则确认与投递不绑定（幂等键是按这四个值派生的）。
 *     ★ 推论 3：成功出参含 `pushedYMDHMS`、**不含** `windowSeconds` → 倒计时先按 60 展示，
 *       真实窗口以 `revoke` 响应 / `F5` 的 `data.windowSeconds` 为准（裁定 H）。
 *   · `revoke`（同一端点 `action:'revoke'`，`:1028-1108`）：`CB` 无此记录 / `C7` 未成功投递不可撤销 /
 *     `F1` 已撤销 / `F5` 逾窗（`data.elapsedSeconds` + `data.windowSeconds`）/ `CG` 写库失败；
 *     撤销 = `delFlag='1'`（软删）。★ 数据层默认 `delFlag='0' OR delFlag IS NULL`
 *     （`mysqlCommon.query_ch_publish_record:496-516`）→ 已撤销记录**默认不再出现在列表**（待确认项）。
 *   · `artifactpack`（`processor/artifactService.py:488-676`）：未过合规 → **非 B0** + `data.packaged='0'`
 *     + `data.compliance` 明细；成功 `data` 含 `fileUrl / imageCount / entryList / extraEntryList /
 *     manifest / checkSum / checkSumMethod / zipSizeBytes`；★ `localZipPath` 为服务端本地路径，前端不可用。
 *   · 数值/JSON 字符串口径（R-26）：`total / errorCount / windowSeconds / artifactID` 等一律 `Number()`
 *     归一后再比较。
 *
 * 【红线（裁定 L）】永不传 `autoPublish` / `autoPublishConfirm`；UI 不提供任何自动发布开关；
 *   若后端返回 `F6`（不应发生）→ 按 `MSG.content` 原样提示，不得改写为「发布成功」。
 * ========================================================================== */
import { computed, ref } from 'vue'
import { toast } from 'vue3-toastify'
import { accountQry } from '@/api/account'
import { artifactPack, artifactQry } from '@/api/artifact'
import { publishCheck } from '@/api/compliance'
import { platformQry } from '@/api/platform'
import { publishPush, publishRecordQry } from '@/api/publish'
import { errText } from '@/config/chOptions'
import { parseDateTime } from '@/utils/common'

/* ------------------------------ 1. 常量 ------------------------------ */

/** 唯一可投递平台（`publishService.DELIVERABLE_PLATFORM_LIST`）；★ 小红书/通用 **无** 投递通道 */
export const WECHAT_PLATFORM = 'wechat_mp'
/** 素材包导出通道缺省平台（只导出、无平台动作） */
export const PACK_PLATFORM = 'xiaohongshu'
/** 素材包导出通道可选平台（`ch_platform.deliverMode='asset_pack'`；★ 两者都**没有**投递/发布通道） */
export const PACK_PLATFORMS = ['xiaohongshu', 'generic']
/**
 * ★ 微信订阅号「日群发 / 草稿」配额口径来自 `plan/前端开发计划.md` §2.7 能力矩阵与 `.md` 4.2 P-10，
 *   **不是接口字段**（`ch_platform` 无配额列）→ 前端常量 + 服务端筛选（当日 `success='1'` 条数）估算。
 */
export const WECHAT_DAILY_QUOTA = 1
/** Step 13「标记通过」的本机留痕键前缀（P-09 写入；此处**仅展示**，不作为放行条件） */
export const MARK_PASS_STORAGE_PREFIX = 'chapp:compliance:'
/** 最近一次成功投递（用于页面刷新后按绝对时间恢复撤销入口，避免「进入即 60」的假倒计时） */
export const LAST_DELIVERY_STORAGE_KEY = 'chapp:lastDelivery'
/** 未拿到后端窗口值时的展示回退值（默认 60；真实值以后端 `windowSeconds` 为准） */
export const DEFAULT_REVOKE_WINDOW_SECONDS = 60

const str = (value) => (value === null || value === undefined ? '' : String(value))
const num = (value, fallback = 0) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}
const isOk = (rtn) => str(rtn?.errCode) === 'B0'
const msgOf = (rtn) => str(rtn?.MSG?.content).trim().replace(/[;；]+$/, '') || errText(str(rtn?.errCode)) || '请求失败，请稍后重试'
const pad2 = (value) => String(value).padStart(2, '0')

/** 当日 `YYYYMMDD000000` ~ `YYYYMMDD235959`（服务端筛选 `beginYMDHMS/endYMDHMS` 作用于 `pushedYMDHMS`） */
export function todayRange(date = new Date()) {
  const ymd = `${date.getFullYear()}${pad2(date.getMonth() + 1)}${pad2(date.getDate())}`
  return { beginYMDHMS: `${ymd}000000`, endYMDHMS: `${ymd}235959` }
}

/** 近 N 天范围（记录表默认近 7 天；含当日） */
export function recentRange(days = 7, now = new Date()) {
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - (Math.max(1, days) - 1))
  const ymd = `${start.getFullYear()}${pad2(start.getMonth() + 1)}${pad2(start.getDate())}`
  const today = `${now.getFullYear()}${pad2(now.getMonth() + 1)}${pad2(now.getDate())}`
  return { beginYMDHMS: `${ymd}000000`, endYMDHMS: `${today}235959` }
}

/** 读 P-09 的「已校验」留痕（**仅展示**；放行条件仍是实时 `publishcheck`） */
export function readComplianceMark(topicCode) {
  const code = str(topicCode)
  if (!code || typeof window === 'undefined') return null
  try {
    const raw = window.sessionStorage.getItem(`${MARK_PASS_STORAGE_PREFIX}${code}`)
    return raw ? JSON.parse(raw) : null
  } catch (error) {
    console.error('[P-10] 读取合规标记失败', error)
    return null
  }
}

export function readLastDelivery() {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.sessionStorage.getItem(LAST_DELIVERY_STORAGE_KEY)
    if (!raw) return null
    const record = JSON.parse(raw)
    return record && record.publishRecordID ? record : null
  } catch (error) {
    return null
  }
}

export function writeLastDelivery(record) {
  if (typeof window === 'undefined' || !record) return
  try {
    window.sessionStorage.setItem(LAST_DELIVERY_STORAGE_KEY, JSON.stringify(record))
  } catch (error) {
    console.error('[P-10] 撤销入口留痕写入失败（隐私模式？）', error)
  }
}

export function clearLastDelivery() {
  if (typeof window === 'undefined') return
  try {
    window.sessionStorage.removeItem(LAST_DELIVERY_STORAGE_KEY)
  } catch (error) {
    /* 忽略 */
  }
}

/** 剩余可撤销秒数（★ 按 `pushedYMDHMS + windowSeconds` 绝对时间重算，不得按「进入页面即满窗」） */
export function remainingRevokeSeconds(record, now = Date.now()) {
  if (!record) return 0
  const pushed = parseDateTime(record.pushedYMDHMS)
  const windowSeconds = num(record.windowSeconds, DEFAULT_REVOKE_WINDOW_SECONDS) || DEFAULT_REVOKE_WINDOW_SECONDS
  if (!pushed) return 0
  return Math.max(0, Math.ceil((pushed.getTime() + windowSeconds * 1000 - now) / 1000))
}

/**
 * 撤销（`action:'revoke'`）：返回 `{ ok, errCode, message, data }`，**不抛异常**。
 * `F5` / `F1` 时调用方应移除撤销入口（入口已失效）。
 */
export async function revokePublishRecord({ publishRecordID, idempotencyKey }) {
  const body = { action: 'revoke' }
  if (publishRecordID) body.publishRecordID = String(publishRecordID)
  if (idempotencyKey) body.idempotencyKey = String(idempotencyKey)
  if (!body.publishRecordID && !body.idempotencyKey) return { ok: false, errCode: 'C4', message: '撤销需要记录标识' }

  const rtn = await publishPush(body, { silent: true }).catch((e) => e)
  if (isOk(rtn)) return { ok: true, errCode: 'B0', message: '已撤销', data: rtn.data || {} }
  const errCode = str(rtn?.errCode)
  const data = rtn?.data || {}
  let message = msgOf(rtn)
  if (errCode === 'F5') {
    message = `撤销窗已过期（已过 ${num(data.elapsedSeconds)} 秒 / 窗口 ${num(data.windowSeconds, DEFAULT_REVOKE_WINDOW_SECONDS)} 秒）`
  } else if (errCode === 'F1') {
    message = '该记录已撤销（幂等命中）'
  }
  return { ok: false, errCode, message, data }
}

/** 打开 ZIP 下载（`<a target="_blank" rel="noopener">`；★ 仅成功路径调用） */
export function openZipDownload(fileUrl) {
  const url = str(fileUrl)
  if (!url || typeof document === 'undefined') return false
  const link = document.createElement('a')
  link.href = url
  link.target = '_blank'
  link.rel = 'noopener'
  link.download = ''
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  return true
}

/* ------------------------------ 2. 组合式函数 ------------------------------ */

/**
 * @param {object} options
 * @param {() => object|null} options.getTopic 主题记录（`topicID` 取 `ch_topic.recID`，裁定 A）
 * @param {() => Promise<void>} [options.onRecordsChanged] 写操作成功后刷新记录列表
 * @param {(record: object) => void} [options.onDelivered] 投递成功（宿主页据此挂撤销倒计时条）
 */
export function usePublishFlow({ getTopic, onRecordsChanged, onDelivered } = {}) {
  const topic = computed(() => getTopic?.() || null)
  const topicID = computed(() => str(topic.value?.recID))
  const topicCode = computed(() => str(topic.value?.topicCode))
  const layoutCode = computed(() => str(topic.value?.layoutCode))

  const accounts = ref([])
  const invalidAccounts = ref([])
  const selectedAccountID = ref('')
  const platformRecords = ref({})
  const artifacts = ref([])
  const selectedArtifactID = ref('')
  /** 素材包通道 READY 产物（按平台分桶，仅展示图数） */
  const packArtifactsByPlatform = ref({})
  const selectedPackArtifactID = ref('')
  const quota = ref({ used: 0, limit: WECHAT_DAILY_QUOTA, loaded: false })
  const compliance = ref(null)
  const complianceError = ref('')
  const complianceLoading = ref(false)
  const complianceMark = ref(null)
  const deliverError = ref(null)
  const loadError = ref('')
  const loading = ref(false)
  const submitting = ref(false)
  const confirmVisible = ref(false)
  const pending = ref(null)
  const lastDelivery = ref(null)
  const revoking = ref(false)
  const packLoading = ref(false)
  const packResult = ref(null)
  const packError = ref(null)

  /* ------------------------------ 2.1 派生 ------------------------------ */

  const selectedAccount = computed(
    () => accounts.value.find((item) => str(item.accountID) === selectedAccountID.value) || null
  )
  const selectedArtifact = computed(
    () => artifacts.value.find((item) => str(item.recID) === selectedArtifactID.value) || artifacts.value[0] || null
  )
  const healthAccounts = computed(() =>
    accounts.value.filter((item) => ['OK', 'EXPIRING'].includes(str(item.healthStatus)))
  )
  const layoutMissing = computed(() => !layoutCode.value)
  const artifactMissing = computed(() => !artifacts.value.length)
  const accountInvalid = computed(() => str(selectedAccount.value?.healthStatus) === 'INVALID')
  const errorCount = computed(() => num(compliance.value?.errorCount))
  const passed = computed(() => str(compliance.value?.passed) === '1')
  const complianceReady = computed(() => Boolean(compliance.value) && passed.value)
  const complianceIssues = computed(() => (Array.isArray(compliance.value?.issues) ? compliance.value.issues : []))
  const warningCount = computed(() => num(compliance.value?.warningCount))
  const usedCount = computed(() => num(quota.value.used))
  const quotaLimit = computed(() => num(quota.value.limit, WECHAT_DAILY_QUOTA))
  const remaining = computed(() => Math.max(0, quotaLimit.value - usedCount.value))
  const quotaExhausted = computed(() => remaining.value <= 0)
  const packPlatformRecord = computed(() => platformRecords.value[PACK_PLATFORM] || null)
  const wechatPlatformRecord = computed(() => platformRecords.value[WECHAT_PLATFORM] || null)

  /** 投递按钮禁用原因（按服务端前置顺序给出**首个**原因，避免「点了没反应」） */
  const deliverBlockReason = computed(() => {
    if (layoutMissing.value) return '请先为该主题选择版式后方可投递'
    if (artifactMissing.value) return '请先渲染出可用产物'
    if (accountInvalid.value) return '所选账号凭据已失效，请到账号管理重新授权'
    if (complianceError.value) return '合规校验结果未取到，请先到合规校验页确认'
    if (errorCount.value > 0) return `存在 ${errorCount.value} 项阻断，请先修正`
    if (quotaExhausted.value) return `今日剩余推送次数为 0（上限 ${quotaLimit.value} 次/天），请明日再试`
    return ''
  })
  const canDeliver = computed(() => !deliverBlockReason.value && !submitting.value)

  /* ------------------------------ 2.2 取数 ------------------------------ */

  async function loadAccounts() {
    const res = await accountQry({ platform: WECHAT_PLATFORM, beginNum: 0, endNum: 50 }).catch((e) => e)
    const list = Array.isArray(res?.data) ? res.data : []
    accounts.value = list
    const invalid = await accountQry({ platform: WECHAT_PLATFORM, healthStatus: 'INVALID', beginNum: 0, endNum: 50 }).catch((e) => e)
    invalidAccounts.value = Array.isArray(invalid?.data) ? invalid.data : []
    const stillThere = list.some((item) => str(item.accountID) === selectedAccountID.value)
    if (!stillThere) {
      const picked = healthAccounts.value[0] || list[0] || null
      selectedAccountID.value = str(picked?.accountID)
    }
  }

  async function loadArtifacts() {
    const params = {
      topicID: topicID.value,
      platform: WECHAT_PLATFORM,
      artifactStatus: 'READY',
      order: 'modify',
      beginNum: 0,
      endNum: 20
    }
    const res = await artifactQry(params, { silent: true }).catch((e) => e)
    artifacts.value = Array.isArray(res?.data) ? res.data : []
    // ★ 默认取最新一条（后端 `order:'modify'` → `modifyYMDHMS DESC`）
    if (!artifacts.value.some((item) => str(item.recID) === selectedArtifactID.value)) {
      selectedArtifactID.value = str(artifacts.value[0]?.recID)
    }

    // 素材包通道：按平台分别取 READY 产物（仅用于展示图数，不做产物管理）
    await Promise.all(
      PACK_PLATFORMS.map(async (code) => {
        const packRes = await artifactQry({ ...params, platform: code }, { silent: true }).catch((e) => e)
        packArtifactsByPlatform.value = {
          ...packArtifactsByPlatform.value,
          [code]: Array.isArray(packRes?.data) ? packRes.data : []
        }
      })
    )
  }

  /** 配额：当日成功投递条数（★ 前端常量 + 服务端筛选，非接口字段） */
  async function loadQuota() {
    const { beginYMDHMS, endYMDHMS } = todayRange()
    const res = await publishRecordQry(
      { platform: WECHAT_PLATFORM, success: '1', beginYMDHMS, endYMDHMS, beginNum: 0, endNum: 1 },
      { silent: true }
    ).catch((e) => e)
    // ★ 失败时保持 `loaded:false`（页面显示「读取中」而不是「剩余 0」，裁定 G）
    if (str(res?.errCode) === 'B0') quota.value = { used: num(res?.total), limit: WECHAT_DAILY_QUOTA, loaded: true }
  }

  async function loadPlatforms() {
    const result = { ...platformRecords.value }
    for (const code of [WECHAT_PLATFORM, ...PACK_PLATFORMS]) {
      const res = await platformQry({ platformCode: code }, { silent: true }).catch((e) => e)
      const hit = Array.isArray(res?.data) ? res.data[0] : null
      if (hit) result[code] = hit
    }
    platformRecords.value = result
  }

  /** 合规硬门禁 = 实时 `publishcheck`（`errorCount>0` 阻断；★ 兼容「非 B0 + data 明细」的真实出参） */
  async function loadCompliance() {
    complianceLoading.value = true
    complianceError.value = ''
    try {
      const params = { topicCode: topicCode.value, platform: WECHAT_PLATFORM }
      if (layoutCode.value) params.layoutCode = layoutCode.value
      const rtn = await publishCheck(params, { silent: true }).catch((e) => e)
      const data = rtn?.data && typeof rtn.data === 'object' && (rtn.data.errorCount !== undefined || Array.isArray(rtn.data.issues))
        ? rtn.data
        : null
      if (!data) {
        compliance.value = null
        complianceError.value = '合规校验结果未取到'
        console.error('[P-10] publishcheck 未返回可用结果', rtn)
        return
      }
      compliance.value = {
        ...data,
        passed: str(data.passed),
        errorCount: num(data.errorCount),
        warningCount: num(data.warningCount),
        issueCount: num(data.issueCount),
        issues: Array.isArray(data.issues) ? data.issues : []
      }
    } finally {
      complianceLoading.value = false
    }
  }

  /** 进入页面 / 切换主题：全部前置一次取齐（失败互不影响，逐项降级） */
  async function loadAll() {
    complianceMark.value = readComplianceMark(topicCode.value)
    lastDelivery.value = readLastDelivery()
    if (!topicID.value) return
    loading.value = true
    loadError.value = ''
    try {
      await Promise.all([loadAccounts(), loadArtifacts(), loadQuota(), loadPlatforms(), loadCompliance()])
    } catch (error) {
      loadError.value = error?.MSG?.content || '投递前置信息读取失败'
      console.error('[P-10] 投递前置取数失败', error)
    } finally {
      loading.value = false
    }
  }

  /** 仅刷新合规门禁（「重新校验」/ 阻断修正后回来看结果） */
  async function refreshCompliance() {
    await loadCompliance()
    complianceMark.value = readComplianceMark(topicCode.value)
  }

  /* ------------------------------ 2.3 两步二次确认 ------------------------------ */

  function buildPushParams() {
    // ★ 永不传 autoPublish（裁定 L）；artifactID 传 ch_artifact.recID；topicID 传 ch_topic.recID（裁定 A）
    return {
      platform: WECHAT_PLATFORM,
      topicID: topicID.value,
      layoutCode: layoutCode.value,
      artifactID: str(selectedArtifact.value?.recID),
      accountID: str(selectedAccount.value?.accountID || selectedAccountID.value)
    }
  }

  function describeError(rtn) {
    return {
      code: str(rtn?.errCode) || 'ERR_GENERAL',
      field: str(rtn?.field),
      message: msgOf(rtn),
      data: rtn?.data && typeof rtn.data === 'object' ? rtn.data : {},
      compliance: rtn?.data?.compliance && typeof rtn.data.compliance === 'object' ? rtn.data.compliance : null
    }
  }

  async function handlePushError(rtn) {
    const detail = describeError(rtn)
    deliverError.value = detail
    if (detail.compliance) compliance.value = { ...(compliance.value || {}), ...detail.compliance }
    toast.error(detail.message)
    // ★ F0：服务端在凭据解密失败时会把账号置 INVALID → 刷新账号列表（不要只 toast）
    if (detail.code === 'F0') await loadAccounts()
    return detail
  }

  async function handleDelivered(data, params) {
    const record = {
      publishRecordID: str(data.publishRecordID),
      idempotencyKey: str(data.idempotencyKey || params?.idempotencyKey),
      remoteID: str(data.remoteID),
      pushedYMDHMS: str(data.pushedYMDHMS),
      windowSeconds: num(data.windowSeconds, DEFAULT_REVOKE_WINDOW_SECONDS) || DEFAULT_REVOKE_WINDOW_SECONDS,
      topicID: topicID.value,
      topicCode: topicCode.value,
      topicTitle: str(topic.value?.title),
      platform: WECHAT_PLATFORM,
      accountID: str(params?.accountID)
    }
    deliverError.value = null
    lastDelivery.value = record
    writeLastDelivery(record)
    toast.success(`已推送到草稿箱${record.remoteID ? `（remoteID ${record.remoteID}）` : ''}；群发需在公众号后台手动完成`)
    await Promise.all([loadQuota(), refreshCompliance()])
    await onRecordsChanged?.()
    onDelivered?.(record)
  }

  /** 第 1 步：不带确认参数的 silent 调用（预期 F4；兼容后端未强制两步时直接成功） */
  async function startPush() {
    if (!canDeliver.value) {
      toast.warning(deliverBlockReason.value)
      return { ok: false, errCode: 'BLOCKED', message: deliverBlockReason.value }
    }
    submitting.value = true
    deliverError.value = null
    try {
      const params = buildPushParams()
      const rtn = await publishPush(params, { silent: true }).catch((e) => e)
      if (isOk(rtn)) {
        // ★ 兼容路径：后端未强制两步 → 直接视为成功，不弹确认窗
        await handleDelivered(rtn.data || {}, params)
        return { ok: true, oneStep: true }
      }
      if (str(rtn?.errCode) === 'F4') {
        const data = rtn?.data || {}
        if (!data.idempotencyKey || !data.confirmToken) {
          await handlePushError(rtn)
          return { ok: false, errCode: 'F4' }
        }
        pending.value = { idempotencyKey: str(data.idempotencyKey), confirmToken: str(data.confirmToken), params }
        confirmVisible.value = true
        console.info(
          '[P-10] publishpush 首次调用（无确认参数）→ F4 回显 ' +
            JSON.stringify({
              request: params,
              response: {
                errCode: str(rtn.errCode),
                data: {
                  idempotencyKey: str(data.idempotencyKey),
                  confirmToken: str(data.confirmToken),
                  confirmFlagKey: str(data.confirmFlagKey),
                  confirmTokenKey: str(data.confirmTokenKey)
                }
              }
            })
        )
        return { ok: false, errCode: 'F4', waitingConfirm: true }
      }
      // F0 / C7 / 合规侧 errCode …：按 MSG.content 展示，**不弹确认窗**
      const detail = await handlePushError(rtn)
      return { ok: false, errCode: detail.code, message: detail.message }
    } finally {
      submitting.value = false
    }
  }

  /** 第 2 步：用户确认后带 `idempotencyKey` + `confirmFlag` + `confirmToken` 提交 */
  async function confirmPush() {
    if (!pending.value) return { ok: false }
    submitting.value = true
    try {
      const { idempotencyKey, confirmToken, params } = pending.value
      const body = { ...params, idempotencyKey, confirmFlag: '1', confirmToken }
      console.info('[P-10] publishpush 第二次调用（带确认参数） ' + JSON.stringify(body))
      const rtn = await publishPush(body, { silent: true }).catch((e) => e)
      if (isOk(rtn)) {
        console.info('[P-10] publishpush 投递成功出参 ' + JSON.stringify(rtn.data || {}))
        confirmVisible.value = false
        pending.value = null
        await handleDelivered(rtn.data || {}, { ...params, idempotencyKey })
        return { ok: true }
      }
      // ★ 失败：关闭 loading、**保留弹窗与内容**（不清空），仅追加错误说明
      const detail = await handlePushError(rtn)
      return { ok: false, errCode: detail.code, message: detail.message }
    } finally {
      submitting.value = false
    }
  }

  function cancelConfirm() {
    // 取消不解除服务端绑定：幂等键仍可复用（下次点击会重新走第 1 步，服务端回显同一 key）
    confirmVisible.value = false
  }

  /* ------------------------------ 2.4 撤销 / 素材包 ------------------------------ */

  async function revoke(record) {
    revoking.value = true
    try {
      const result = await revokePublishRecord({
        publishRecordID: record?.publishRecordID,
        idempotencyKey: record?.idempotencyKey
      })
      if (result.ok) {
        toast.success('已撤销本次草稿投递（发布记录置 delFlag=1）')
        clearLastDelivery()
        lastDelivery.value = null
      } else if (result.errCode === 'F5') {
        toast.error(result.message)
        clearLastDelivery()
        lastDelivery.value = null
      } else if (result.errCode === 'F1') {
        toast.warning(result.message)
        clearLastDelivery()
        lastDelivery.value = null
      } else {
        toast.error(result.message)
      }
      await onRecordsChanged?.()
      return result
    } finally {
      revoking.value = false
    }
  }

  /** 导出素材包 ZIP（★ 只导出不投递：无二次确认；`packaged='0'` 时**不得**触发下载、不得当成功） */
  async function exportPack(packPlatform = PACK_PLATFORM) {
    if (!topicID.value || packLoading.value) return { ok: false }
    packLoading.value = true
    packError.value = null
    packResult.value = null
    try {
      const params = { topicID: topicID.value, topicCode: topicCode.value, platform: packPlatform }
      if (layoutCode.value) params.layoutCode = layoutCode.value
      if (selectedPackArtifactID.value) params.artifactID = selectedPackArtifactID.value
      const rtn = await artifactPack(params, { silent: true }).catch((e) => e)
      if (isOk(rtn)) {
        const data = rtn.data || {}
        packResult.value = {
          ...data,
          imageCount: num(data.imageCount),
          zipSizeBytes: num(data.zipSizeBytes),
          entryList: (Array.isArray(data.entryList) ? data.entryList : [])
            .slice()
            .sort((a, b) => num(a.seqNo) - num(b.seqNo)),
          extraEntryList: Array.isArray(data.extraEntryList) ? data.extraEntryList : []
        }
        const started = openZipDownload(data.fileUrl)
        toast.success(started ? '素材包已开始下载；如未自动下载请右键另存为' : '素材包已生成，但未取到下载地址')
        return { ok: true, data: packResult.value }
      }
      const data = rtn?.data && typeof rtn.data === 'object' ? rtn.data : {}
      const blocked = str(data.packaged) === '0' || Boolean(data.compliance)
      packError.value = {
        code: str(rtn?.errCode) || 'ERR_GENERAL',
        message: msgOf(rtn),
        packaged: str(data.packaged),
        compliance: blocked ? (data.compliance || data) : null
      }
      console.warn(
        '[P-10] artifactpack 未出包（未触发下载） ' +
          JSON.stringify({ errCode: packError.value.code, packaged: packError.value.packaged, data })
      )
      return { ok: false, ...packError.value }
    } finally {
      packLoading.value = false
    }
  }

  return {
    // 状态
    topicID,
    topicCode,
    layoutCode,
    accounts,
    healthAccounts,
    invalidAccounts,
    selectedAccountID,
    selectedAccount,
    artifacts,
    selectedArtifactID,
    selectedArtifact,
    packArtifactsByPlatform,
    selectedPackArtifactID,
    platformRecords,
    packPlatformRecord,
    wechatPlatformRecord,
    quota,
    usedCount,
    quotaLimit,
    remaining,
    compliance,
    complianceIssues,
    complianceError,
    complianceLoading,
    complianceMark,
    errorCount,
    warningCount,
    passed,
    complianceReady,
    deliverError,
    loadError,
    loading,
    submitting,
    confirmVisible,
    pending,
    lastDelivery,
    revoking,
    packLoading,
    packResult,
    packError,
    // 派生门禁
    layoutMissing,
    artifactMissing,
    accountInvalid,
    quotaExhausted,
    canDeliver,
    deliverBlockReason,
    // 动作
    loadAll,
    loadAccounts,
    refreshCompliance,
    startPush,
    confirmPush,
    cancelConfirm,
    revoke,
    exportPack
  }
}

export default usePublishFlow
