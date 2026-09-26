/* ============================================================================
 * Mock 数据 · 审计日志 / 平台账号凭据 / MCP 令牌（确定性生成）
 * ----------------------------------------------------------------------------
 * 账号 `healthStatus` 权威取值：OK / EXPIRING / INVALID / UNKNOWN（§2.6 修正 ①），四值样例齐备。
 * ★ 凭据密文在 Mock 中按「原文」返回，**由页面用 `maskSecret()` 掩码后展示**（禁止直出明文）。
 *
 * ★ 审计域（Step 16 / P-12）**整体重写为与真实后端同构**（裁定 I），字段口径以
 *   `code/src/database/ch_audit_log.txt`（权威列）+ `code/src/processor/auditService.py`
 *   （`buildAuditSaveSet` / `SOURCE_LIST` / `RESULT_LIST` / 5 个 `ACTION_*` 常量 /
 *   `TARGET_TYPE_*` 常量）为准：
 *     · 列 = recID(数字自增) / actor / source / action / targetType / targetID / payloadDigest /
 *            result(OK|FAIL) / errMsg / costMs / ipAddr / label / memo / regID / regYMDHMS /
 *            modifyID / modifyYMDHMS / delFlag（= `funcAuditlogQry` 的 aSet 全字段）；
 *     · **移除**旧口径的 `logID` / `roleName` / `cmd` / `detail` / `ip` / `operator` / `remark`
 *       （真实表**无**这些列）；
 *     · **不提供任何 `payload` 字段** —— `ch_audit_log` 无 payload 列，`sanitizePayload()` 的结果
 *       只用于算 `payloadDigest`（`auditService.py:182-190` / `:216`），不落库；
 *     · `action` 只取真实后端会写的 5 类（`auditService.py:66-72`）；`source ∈ {web, api, mcp}`
 *       （**无 system**）；`result ∈ {OK, FAIL}`；`targetType ∈ {ch_publish_record, ch_account,
 *       ch_audit_log, ch_artifact}`。
 *   ★ 主题 / 素材 / 渲染 / 账号域**当前都不写审计**，故本文件**不生成**这些域的动作。
 * ========================================================================== */
import { hoursBefore, hexHash, pad, pick, ymdhms } from './util'

/* ---------------------------------------------------------------------------
 * 审计日志（P-12）· 与 `ch_audit_log` / `auditService.py` 同构
 * ------------------------------------------------------------------------- */

/** 动作 → 对象类型（严格取自 `auditService.py:66-90` 的 5 个动作与 4 个对象类型） */
const AUDIT_ACTIONS = [
  { action: 'publish.push', targetType: 'ch_publish_record' },
  { action: 'publish.revoke', targetType: 'ch_publish_record' },
  { action: 'publish.confirm', targetType: 'ch_publish_record' },
  { action: 'archive.audit_log', targetType: 'ch_audit_log' },
  { action: 'archive.artifact_purge', targetType: 'ch_artifact' }
]

/**
 * ★ `ch_account` 对象类型样例（裁定 I 要求覆盖 4 类 `targetType`）。
 * ⚠️ 事实：`auditService.TARGET_TYPE_ACCOUNT = "ch_account"` 已声明，但**当前无任何写入方使用**
 *   （`publishService._writeAudit` 固定 `ch_publish_record`；`schedule/archive.py` 用
 *   `ch_audit_log` / `ch_artifact`）→ 真实环境该取值**暂时为 0 条**。
 *   本 Mock 保留 3 条样例仅为验证 P-12 的筛选面与建议值，并在 `memo` 中显式标注，避免被误读为真实数据。
 */
const AUDIT_ACCOUNT_SAMPLE = { action: 'publish.confirm', targetType: 'ch_account' }

/** 来源三值（`auditService.py:74-78`）：web / api / mcp —— **没有 system** */
const AUDIT_SOURCES = ['web', 'api', 'mcp']

/** 操作者：loginID（web/api 调用人）或 MCP 令牌名（mcp 来源）—— `ch_audit_log.actor` COMMENT */
const AUDIT_ACTORS = {
  web: ['chenliheng', 'zhoumin', 'lisiyuan', 'gunanping'],
  api: ['chenliheng', 'svc-contenthub-job'],
  mcp: ['审计日志导出', '投递记录查询']
}

/** FAIL 行的 `errMsg`（对齐真实链路的错误码与文案，非编造状态） */
const AUDIT_FAIL_MSG = [
  'F1 幂等命中：同一 idempotencyKey 已存在，重复投递被拒绝',
  'F4 缺少二次确认：confirmToken 不匹配或已过期',
  'F0 凭据解密失败：credentialCipher 无可用密钥',
  'E2 截图超时：Chromium 字体预加载超时，已重试 1 次',
  'C7 平台不支持：xiaohongshu 无投递通道（本期仅素材包导出）',
  'F5 撤销窗已过期：超出 60 秒撤销窗口，记录不可撤销',
  'G3 下游服务调用失败：微信接口返回 48001（未授权）',
  'ERR_GENERAL 归档任务异常终止：导出分片校验不一致'
]

const AUDIT_MEMO = [
  '投递后自动留痕；幂等键由服务端下发',
  '归档批次 202609-01，导出后保留 24 个月',
  '二次确认（confirmFlag=1）留痕',
  '审计写入失败不阻断主流程，此处为补写记录',
  ''
]

/** 来源 IP（等值筛选用；周期 6，便于「同一 IP 命中多条」可验证） */
const AUDIT_IP_LIST = ['10.20.30.100', '10.20.30.101', '10.20.31.100', '10.20.31.101', '172.16.8.24', '203.0.113.7']

/**
 * 记录时刻（小时，相对**真实当前时刻**）。
 *
 * ★ 此处**刻意不用** `data/util.js::hoursBefore`（它相对固定基准 `BASE_TIME=2026-09-20 12:00`）：
 *   P-12 进入页面默认「近 24 小时」，若按固定基准生成数据，默认范围**永远查不到记录**，
 *   「时间范围必填 / 90 天上限 / 三区间分布」三项都无法在 Mock 下验收。
 *   数据形状与条数仍是确定的（仅时间锚点跟随当前时刻平移）。
 *   区间：i<12 → 近 24 小时；12≤i<30 → 近 7 天；30≤i<46 → 更早（8~40 天）；i≥46 → ~100 天（验证 90 天上限）。
 */
function auditHoursAgo(i) {
  if (i < 12) return 0.5 + i * 1.9
  if (i < 30) return 26 + (i - 12) * 7.6
  if (i < 46) return 200 + (i - 30) * 48
  return 2400 + (i - 46) * 24
}

function buildAuditLogs(count = 48) {
  const anchor = Date.now()
  return Array.from({ length: count }, (unused, i) => {
    const source = pick(AUDIT_SOURCES, i)
    const isAccountTarget = i % 17 === 4
    const template = isAccountTarget ? AUDIT_ACCOUNT_SAMPLE : pick(AUDIT_ACTIONS, i)
    const actor = pick(AUDIT_ACTORS[source], i)
    /**
     * 失败占比约 30%（14/48）：FAIL 行必有 errMsg，OK 行 errMsg 为空串（与 buildAuditSaveSet 一致）。
     * ★ 失败判定用 `i % 7`（而非 `i % 3`）：`source` 按 `i % 3`、`action` 按 `i % 5` 轮转，
     *   若失败也按 `i % 3` 取，会退化成「所有 FAIL 行都来自同一 source」，无法验证组合筛选。
     */
    const failed = i % 7 === 2 || i % 7 === 5
    const regDate = new Date(anchor - auditHoursAgo(i) * 3600 * 1000)
    const seq = i + 1
    return {
      recID: seq, // ★ 数字自增（真实 `BIGINT AUTO_INCREMENT`）—— 页面不得对它 Number()/排序
      actor,
      source,
      action: template.action,
      // 少量行故意留空，验证「空值显示 —」与「未知/空值不硬塞」
      targetType: i % 17 === 9 ? '' : template.targetType,
      targetID:
        i % 17 === 9
          ? ''
          : isAccountTarget
            ? String(1 + (i % 6))
            : String(1000 + ((i * 37) % 900)),
      payloadDigest: hexHash(seq + 101), // 64 位小写 sha256（形态同真实）
      result: failed ? 'FAIL' : 'OK',
      errMsg: failed ? pick(AUDIT_FAIL_MSG, i) : '',
      costMs: i % 11 === 5 ? '' : 30 + ((i * 53) % 900),
      ipAddr: i % 13 === 7 ? '' : pick(AUDIT_IP_LIST, i),
      label: i % 4 === 0 ? 'audit' : '',
      memo: isAccountTarget
        ? 'Mock 样例：targetType=ch_account 用于验证筛选面（真实写入方暂未使用该常量）'
        : pick(AUDIT_MEMO, i),
      regID: actor,
      regYMDHMS: ymdhms(regDate),
      modifyID: '', // 审计行为追加写：不修改
      modifyYMDHMS: '',
      delFlag: '0'
    }
  })
}

/** 审计日志（只追加；时间范围必填查询用） */
export const AUDIT_LOGS = buildAuditLogs(48)

/**
 * 平台账号凭据（四种健康状态齐备）。
 *
 * ★ Step 15 补全（P-11）：字段以 `code/src/database/ch_account.txt` 的**权威列名**为准，
 *   补齐 `accountCode / subjectType / verifiedFlag / capability / credentialCipher / credentialIV /
 *   lastUseYMDHMS / ownerID / label / memo / modifyYMDHMS`，使 Mock 与真实后端「`mode='full'`
 *   返回 `*`」同构（尤其**必须带出 `credentialCipher`/`credentialIV`**，否则无法验证
 *   P-11 的字段白名单确实丢弃了密文列）。
 * ★ `appSecret` / `credentialRef` / `quotaUsed` / `quotaLimit` / `operator` 为本 Mock 既有字段
 *   （P-10 用），**保留不动**；真实表无这几列，P-11 的白名单会全部丢弃。
 * ★ 凭据密文在 Mock 中按「密文形态的假值」返回（AES 密文/IV 的可读形态），
 *   **任何页面都不得展示**（P-11 只展示「已配置 / 未配置」+ 固定掩码）。
 */
export const ACCOUNTS = [
  {
    recID: 'AC000001',
    accountID: 'ACC-001',
    accountCode: 'WX-MAIN-001',
    accountName: '内容中枢 · 主号',
    platform: 'wechat_mp',
    subjectType: 'enterprise',
    verifiedFlag: '1',
    capability: 'api_publish',
    appID: 'wx8f2c41d7a9e35b60',
    appSecret: 'wxsec-4f8a1c92d70e3b56a1c47d2e',
    credentialRef: 'vault://contenthub/wechat_mp/main',
    credentialCipher: 'q1c0F3nT8yQ2mZ7vL4xR9wB6sK1dH5jP0aG2eU8tW3yA=',
    credentialIV: '3b7f9c1d4e802a56',
    healthStatus: 'OK',
    expireYMDHMS: ymdhms(hoursBefore(-(24 * 76))),
    quotaUsed: 6,
    quotaLimit: 10,
    autoPublishFlag: '0',
    lastCheckYMDHMS: ymdhms(hoursBefore(3)),
    lastUseYMDHMS: ymdhms(hoursBefore(2)),
    ownerID: 'chenliheng',
    label: '主号',
    memo: '内容中枢对外主账号，群发须手动完成',
    modifyYMDHMS: ymdhms(hoursBefore(3)),
    operator: '陈立恒'
  },
  {
    recID: 'AC000002',
    accountID: 'ACC-002',
    accountCode: 'WX-BACKUP-002',
    accountName: '内容中枢 · 备用号',
    platform: 'wechat_mp',
    subjectType: 'enterprise',
    verifiedFlag: '0',
    capability: 'draft_box',
    appID: 'wx31b7e05c8d2f4a19',
    appSecret: 'wxsec-9b2d5e71c3a80f46b7d19e02',
    credentialRef: 'vault://contenthub/wechat_mp/backup',
    credentialCipher: 'a7B2d9K4mP1sV6tX0zC3lQ8nR5wE2yU4iO7pA1sD6fG=',
    credentialIV: '9c2e5a71b0d43f68',
    healthStatus: 'EXPIRING',
    expireYMDHMS: ymdhms(hoursBefore(-(24 * 5))),
    quotaUsed: 9,
    quotaLimit: 10,
    autoPublishFlag: '0',
    lastCheckYMDHMS: ymdhms(hoursBefore(6)),
    lastUseYMDHMS: ymdhms(hoursBefore(5)),
    ownerID: 'zhoumin',
    label: '备用号',
    memo: '主号额度用尽时切换；到期前须更换凭据',
    modifyYMDHMS: ymdhms(hoursBefore(6)),
    operator: '周敏'
  },
  {
    recID: 'AC000003',
    accountID: 'ACC-003',
    accountCode: 'WX-MUSEUM-003',
    accountName: '博物院展厅 · 订阅号',
    platform: 'wechat_mp',
    subjectType: 'personal',
    verifiedFlag: '1',
    capability: 'draft_box',
    appID: 'wx7c19a4f2b65d0831',
    appSecret: 'wxsec-1a6f9c37d4b25e80c93a47f1',
    credentialRef: 'vault://contenthub/wechat_mp/museum',
    credentialCipher: 'z8Y5u3I1o9P7a5S3d1F9g7H5j3K1l9M7n5B3v1C9x7Z=',
    credentialIV: '5d8c1a2f9e304b76',
    healthStatus: 'INVALID',
    expireYMDHMS: ymdhms(hoursBefore(24 * 2)),
    quotaUsed: 0,
    quotaLimit: 10,
    autoPublishFlag: '0',
    lastCheckYMDHMS: ymdhms(hoursBefore(9)),
    lastUseYMDHMS: ymdhms(hoursBefore(30)),
    ownerID: 'lisiyuan',
    label: '展厅订阅号',
    memo: '凭据已过期，探活被拒绝；需运维重新注入密文',
    modifyYMDHMS: ymdhms(hoursBefore(9)),
    operator: '李思远'
  },
  {
    recID: 'AC000004',
    accountID: 'ACC-004',
    accountCode: 'XHS-EXPORT-004',
    accountName: '小红书素材包（仅导出）',
    platform: 'xiaohongshu',
    subjectType: 'personal',
    verifiedFlag: '0',
    capability: 'asset_pack',
    appID: 'xhs-demo-2026',
    appSecret: 'xhssec-5d2a70c1e9b348f6d10c7a28',
    credentialRef: 'vault://contenthub/xiaohongshu/export',
    credentialCipher: '',
    credentialIV: '',
    healthStatus: 'UNKNOWN',
    expireYMDHMS: '',
    quotaUsed: 0,
    quotaLimit: 0,
    autoPublishFlag: '0',
    lastCheckYMDHMS: '',
    lastUseYMDHMS: '',
    ownerID: 'zhoumin',
    label: '素材包导出',
    memo: '本期只导出素材包，不投递不发布；巡检跳过',
    modifyYMDHMS: ymdhms(hoursBefore(48)),
    operator: '周敏'
  },
  {
    recID: 'AC000005',
    accountID: 'ACC-005',
    accountCode: 'GEN-SITE-005',
    accountName: '通用 HTML 站点',
    platform: 'generic',
    subjectType: 'enterprise',
    verifiedFlag: '0',
    capability: 'asset_pack',
    appID: 'generic-site-01',
    appSecret: 'gnsec-7e4b1d05a2c96f38b7e01d4c',
    credentialRef: 'vault://contenthub/generic/site01',
    credentialCipher: '',
    credentialIV: '',
    healthStatus: 'OK',
    expireYMDHMS: ymdhms(hoursBefore(-(24 * 120))),
    quotaUsed: 2,
    quotaLimit: 50,
    autoPublishFlag: '0',
    lastCheckYMDHMS: ymdhms(hoursBefore(12)),
    lastUseYMDHMS: ymdhms(hoursBefore(11)),
    ownerID: 'lisiyuan',
    label: '内部站点',
    memo: '无平台凭据，导出 HTML 供内部站点使用',
    modifyYMDHMS: ymdhms(hoursBefore(12)),
    operator: '李思远'
  },
  {
    recID: 'AC000006',
    accountID: 'ACC-006',
    accountCode: 'WX-CAMPAIGN-006',
    accountName: '专题活动 · 服务号',
    platform: 'wechat_mp',
    subjectType: 'enterprise',
    verifiedFlag: '1',
    capability: 'api_publish',
    appID: 'wx2d90c7b1f4a83e5c',
    appSecret: 'wxsec-3c8d20f7a19b45e6d02f7a13',
    credentialRef: 'vault://contenthub/wechat_mp/campaign',
    credentialCipher: 'm4N2b8V6c4X2z0A8s6D4f2G0h8J6k4L2q0W8e6R4t2Y=',
    credentialIV: '1f4b7d0a3c6e9285',
    healthStatus: 'OK',
    expireYMDHMS: ymdhms(hoursBefore(-(24 * 40))),
    quotaUsed: 1,
    quotaLimit: 10,
    autoPublishFlag: '0',
    lastCheckYMDHMS: ymdhms(hoursBefore(20)),
    lastUseYMDHMS: ymdhms(hoursBefore(19)),
    ownerID: 'gunanping',
    label: '活动服务号',
    memo: '专题活动期间使用，凭据长期有效',
    modifyYMDHMS: ymdhms(hoursBefore(20)),
    operator: '顾南屏'
  },
  /* -------------------------------------------------------------------------
   * ★ 2026-09-23「第三方账号管理」新增（Mock 归属隔离可验收性）：
   *   customer 的开发态登录账号为 `wangys`（mock/user.js PROFILES）——
   *   原 6 条种子中**无** ownerID='wangys' 的记录，若照搬真实后端语义，customer
   *   登录后列表恒为空、无法演示「只看得到自己的账号」。故补 1 条归属该账号的记录。
   *   operator（lisiyuan）已有 2 条、manager（zhoumin）已有 2 条（manager 为超管视角，不受归属限制）。
   * ----------------------------------------------------------------------- */
  {
    recID: 'AC000007',
    accountID: 'ACC-007',
    accountCode: 'WX-CUST-007',
    accountName: '客户自助 · 订阅号',
    platform: 'wechat_mp',
    subjectType: 'personal',
    verifiedFlag: '0',
    capability: 'draft_box',
    appID: 'wx7a1d4f2b8e6c9035',
    appSecret: 'wxsec-2c7e4a91b6d3f580a9e26c41',
    credentialRef: 'vault://contenthub/wechat_mp/customer',
    credentialCipher: 'd2F6h4J8l0N2p4R6t8V0x2Z4b6D8f0H2j4L6n8P0r2T4v=',
    credentialIV: '6a9d2c5f8b1e4703',
    healthStatus: 'OK',
    expireYMDHMS: ymdhms(hoursBefore(-(24 * 60))),
    quotaUsed: 3,
    quotaLimit: 10,
    autoPublishFlag: '0',
    lastCheckYMDHMS: ymdhms(hoursBefore(8)),
    lastUseYMDHMS: ymdhms(hoursBefore(7)),
    ownerID: 'wangys',
    label: '客户号',
    memo: '普通用户自管账号：仅本人可见可改（归属隔离演示数据）',
    modifyYMDHMS: ymdhms(hoursBefore(8)),
    operator: '王雨珊'
  }
]

/* ---------------------------------------------------------------------------
 * MCP 令牌（P-13 只读展示）· 与 `code/src/database/ch_mcp_token.txt` 权威列同构
 * -------------------------------------------------------------------------
 * ★ Step 17 按裁定 I 对齐（字段改名 / 删除 / 新增逐条说明）：
 *   · 权威列 = recID / tokenHash / tokenName / tokenScope(read|write|publish，默认 read) /
 *     projectCode / transport(sse|stdio，默认 sse) / lastUseYMDHMS / useCount /
 *     revokedYMDHMS(有值即失效) / ownerID / label / memo / regID / regYMDHMS /
 *     modifyID / modifyYMDHMS / delFlag；
 *   · **删除** `tokenValue`（明文令牌）—— 真实表 `tokenHash` COMMENT 明确「不存明文」，
 *     页面也不得提供「复制 / 显示令牌」入口；
 *   · **删除** `tokenStatus` —— 状态**由 `revokedYMDHMS` 推导**（有值 → 已吊销）；
 *   · **删除** `tokenID` / `remark`（真实表无这两列，旧口径系自造）；
 *   · **修正** `tokenScope` → `read / write / publish`（旧值 `readonly` / `render:read` 等为自造）；
 *   · **修正** `transport` → `sse / stdio`（旧值含 `http`，真实表 COMMENT 为 sse 或 stdio）；
 *   · **新增** `tokenHash`（64 位小写 hex 假值，用 `hexHash()` 生成，便于验证「前 8 位 + …」展示）、
 *     `useCount` / `lastUseYMDHMS` / `ownerID` / `label` / `memo` / `regID` /
 *     `modifyYMDHMS` / `delFlag`；
 *   · `mode='full'` 才会返回 `transport / lastUseYMDHMS / useCount / regYMDHMS`
 *     （`CH_QUERY_SHORT_COLUMNS["ch_mcp_token"]` 只含 `recID,tokenName,tokenScope,projectCode,revokedYMDHMS`）。
 * ★ 覆盖度：含「从未使用」（`lastUseYMDHMS=''` + `useCount=0`）与「已吊销」各 1 条，
 *   用于验证「—」占位、`Number()` 归一与状态三重编码。
 * ------------------------------------------------------------------------- */
const MCP_TOKEN_SEED = [
  {
    tokenName: '内容中枢只读接入',
    tokenScope: 'read',
    transport: 'sse',
    projectCode: 'contenthub-web',
    ownerID: 'chenliheng',
    label: '只读接入',
    memo: '前端联调用的只读令牌，仅可查询主题与素材',
    useCount: 1284,
    lastUseHours: 2,
    revokedHours: null,
    modifyHours: 6
  },
  {
    tokenName: '渲染任务查询',
    tokenScope: 'read',
    transport: 'sse',
    projectCode: 'contenthub-render',
    ownerID: 'zhoumin',
    label: '渲染只读',
    memo: '渲染巡检脚本使用，按 jobCode 拉取任务状态',
    useCount: 356,
    lastUseHours: 9,
    revokedHours: null,
    modifyHours: 24
  },
  {
    tokenName: '主题内容维护',
    tokenScope: 'write',
    transport: 'stdio',
    projectCode: 'contenthub-topic',
    ownerID: 'lisiyuan',
    label: '内容写入',
    memo: '本地 stdio 接入，用于批量改写主题标签',
    useCount: 0,
    lastUseHours: null,
    revokedHours: null,
    modifyHours: 42
  },
  {
    tokenName: '素材检索服务',
    tokenScope: 'read',
    transport: 'stdio',
    projectCode: 'contenthub-asset',
    ownerID: 'gunanping',
    label: '素材检索',
    memo: '素材去重前先用 contentHash 检索是否已入库',
    useCount: 41,
    lastUseHours: 26,
    revokedHours: null,
    modifyHours: 60
  },
  {
    tokenName: '投递台账导出',
    tokenScope: 'publish',
    transport: 'sse',
    projectCode: 'contenthub-publish',
    ownerID: 'chenliheng',
    label: '台账导出',
    memo: '仅导出投递记录用于对账；因人员离岗已吊销',
    useCount: 7,
    lastUseHours: 720,
    revokedHours: 30,
    modifyHours: 30
  }
]

/** MCP 令牌登记台账（状态由 `revokedYMDHMS` 推导；**无任何明文令牌字段**） */
export const MCP_TOKENS = MCP_TOKEN_SEED.map((seed, i) => {
  const regYMDHMS = ymdhms(hoursBefore(1200 + i * 180))
  const revokedYMDHMS = seed.revokedHours === null ? '' : ymdhms(hoursBefore(seed.revokedHours))
  return {
    recID: `MT${pad(i + 1, 6)}`,
    tokenHash: hexHash(i + 201), // 64 位小写 hex（sha256 形态；仅用于「前 8 位」展示）
    tokenName: seed.tokenName,
    tokenScope: seed.tokenScope,
    projectCode: seed.projectCode,
    transport: seed.transport,
    lastUseYMDHMS: seed.lastUseHours === null ? '' : ymdhms(hoursBefore(seed.lastUseHours)),
    useCount: seed.useCount,
    revokedYMDHMS,
    ownerID: seed.ownerID,
    label: seed.label,
    memo: seed.memo,
    regID: seed.ownerID,
    regYMDHMS,
    modifyID: seed.ownerID,
    modifyYMDHMS: revokedYMDHMS || ymdhms(hoursBefore(seed.modifyHours)),
    delFlag: '0'
  }
})

export default AUDIT_LOGS
