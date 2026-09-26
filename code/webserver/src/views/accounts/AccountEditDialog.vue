<!-- ============================================================================
 * AccountEditDialog · P-11 新增 / 编辑平台账号（Step 15 + 凭据写入增量）
 * ----------------------------------------------------------------------------
 * 【★ 凭据写入：已由「入口禁用」升级为可用（后端 R-30 已落地）】
 *   后端 `main/subfunc/crudApi.py` 账号 CRUD 区新增 `_applyAccountSecret(saveSet, dataSet, rtnErrMsgList)`：
 *   · **只读明文 `appSecret`**，经 `common/credentialCipher.encrypt()`（AES-256-GCM）写入
 *     `credentialCipher` / `credentialIV`；**明文永不落库、不入日志、不回显**；
 *   · 未提供 `appSecret`（或空串）→ 保持原行为，**不写任何凭据列**（兼容 cipher/IV 直传的旧调用）；
 *   · **无密钥（`CH_CREDENTIAL_KEY` 未配置）或加密失败 → `F0` 且拒绝落库**：
 *     `accountadd` 短路不 insert；`accountmodify` 不 update；错误文案含
 *     「请检查环境变量 CH_CREDENTIAL_KEY 是否已配置」。
 *   → 故前端提交路径为：`accountAdd({ ..., appSecret })` / `accountModify({ recID, ..., appSecret })`，
 *     **只传明文 `appSecret`，绝不再传 `credentialCipher` / `credentialIV`**（后者已进 FORBIDDEN 硬拦截）。
 *
 * 【凭据安全（硬约束）】
 *   `appSecret` 明文**只允许存在于本弹窗的本地输入变量**：不进 URL query、不进 Pinia/store、
 *   不进 console、不进错误提示；提交成功后立即置空；响应里的 `credentialCipher` / `credentialIV`
 *   一律丢弃（不解析、不存 state、不回显）。
 *
 * 【写入语义差异（UI 不得承诺「清空生效」）】
 *   · `accountadd`：**空值也会写入**（`dataSet.get(field, "")`）→ 新增时全量提交白名单字段；
 *   · `accountmodify`：**「与当前值不同且非空才写」**（`if x != currDataSet.get(x) and x:`）
 *     → 只提交「有变化的非空字段」；与附录 B R-22 同源：**空串无法清空字段**。
 *   ★ 凭据列不受该语义约束：提供了非空 `appSecret` 即覆盖（由服务端加密后写入）。
 *
 * 【字段白名单（裁定 H）】
 *   可编辑：`accountCode`（仅新增；编辑只读）/ `platform` / `accountName` / `subjectType` /
 *   `verifiedFlag`（0|1）/ `capability`（draft_box|asset_pack|api_publish）/ `appID` /
 *   `expireYMDHMS`（14 位，日期选择器转 14 位串）/ `ownerID` / `label` / `memo` / **`appSecret`（明文，仅非空时提交）**。
 *   必填：`accountCode` / `platform` / `accountName` / `subjectType` / `capability`（缺失后端返回 BA 或 CG）。
 *   ★ 只读、不提交：`healthStatus` / `lastCheckYMDHMS` / `lastUseYMDHMS`（巡检回写，提交会覆盖结论）。
 *   ★ 2026-09-23 追加 `ownerFixed` prop：为 `true`（第三方账号管理页的非管理员）时 `ownerID`
 *     只读展示当前登录 loginID 且**不提交** —— 归属由服务端按 `sessionIDSet.loginID` 强制派生
 *     （`crudApi.funcAccountAdd` 覆盖 / `funcAccountModify` 忽略），前端值一律不可信。
 *   ★ 2026-09-24 字段位置：明文凭据输入 `appSecret` 紧接 `appID` **之后**（表单第二列，同排），
 *     并已**撤出弹窗底部** —— 内容区 `max-height: 80vh` 可滚动，置于底部时会落在默认视口的
 *     折叠线以下，视觉上等同「弹窗里没有该输入项」，且与 `appID` 相隔最远、不利于对照填写。
 *     原底部「凭据区」的只读状态行（已配置 / 未配置）折进该字段的 `help`，安全声明段落保留在表单末尾。
 * ========================================================================== -->
<template>
  <!--
    ★ 2026-09-24：表单弹窗形态 —— **点弹窗外部 / Esc 均不关闭**，避免误触遮罩导致已填内容
      （含明文 AppSecret 本地值）丢失；头部 × 与底部「取消」保留为显式出口（二者等价）。
  -->
  <AppDialog
    :model-value="modelValue"
    :title="isEdit ? '编辑平台账号' : '新建平台账号'"
    size="lg"
    :confirm-text="isEdit ? '保存修改' : '创建账号'"
    :confirm-loading="saving"
    :close-on-overlay="false"
    :close-on-esc="false"
    @update:model-value="emit('update:modelValue', $event)"
    @cancel="emit('update:modelValue', false)"
    @confirm="submit"
  >
    <div class="flex flex-col gap-xl">
      <!-- 保存失败就地说明（F0：后端拒绝落库；**弹窗不关闭、表单不清空**） -->
      <ConflictBanner v-if="submitError" type="warning" title="保存失败，请按下方原因处理后重试">
        <span class="break-words">{{ submitError }}</span>
      </ConflictBanner>

      <div class="grid grid-cols-1 gap-lg md:grid-cols-2">
        <FormInput
          v-model="form.accountCode"
          label="账号幂等键"
          required
          :disabled="isEdit"
          placeholder="如 WX-MAIN-001"
          :word-limit="64"
          :error="errors.accountCode"
          :help="isEdit ? '编辑时不可修改（accountCode 为唯一幂等键）' : '全表唯一，创建后不可修改'"
        />

        <label class="flex flex-col gap-xs">
          <span class="flex items-center gap-xs text-body-s text-ch-text-secondary">
            <span>平台</span>
            <span class="text-ch-danger" aria-hidden="true">*</span>
          </span>
          <select
            v-model="form.platform"
            class="h-9 rounded-md border bg-ch-input px-sm text-body-s text-ch-text-primary"
            :class="errors.platform ? 'border-ch-danger' : 'border-ch-border'"
            aria-label="所属平台"
          >
            <option value="">请选择平台</option>
            <option v-for="option in platformOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
          <span v-if="errors.platform" class="flex items-center gap-xs text-caption text-ch-danger">
            <i class="fa fa-circle-xmark" aria-hidden="true"></i>{{ errors.platform }}
          </span>
          <span v-else class="text-caption text-ch-text-tertiary">平台取值来自 platformqry（数据驱动）</span>
        </label>

        <FormInput
          v-model="form.accountName"
          label="账号名称"
          required
          placeholder="如 内容中枢 · 主号"
          :word-limit="128"
          :error="errors.accountName"
        />

        <label class="flex flex-col gap-xs">
          <span class="flex items-center gap-xs text-body-s text-ch-text-secondary">
            <span>主体类型</span>
            <span class="text-ch-danger" aria-hidden="true">*</span>
          </span>
          <select
            v-model="form.subjectType"
            class="h-9 rounded-md border bg-ch-input px-sm text-body-s text-ch-text-primary"
            :class="errors.subjectType ? 'border-ch-danger' : 'border-ch-border'"
            aria-label="主体类型"
          >
            <option value="">请选择主体类型</option>
            <option v-for="option in subjectOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
          <span v-if="errors.subjectType" class="flex items-center gap-xs text-caption text-ch-danger">
            <i class="fa fa-circle-xmark" aria-hidden="true"></i>{{ errors.subjectType }}
          </span>
        </label>

        <label class="flex flex-col gap-xs">
          <span class="flex items-center gap-xs text-body-s text-ch-text-secondary">
            <span>能力</span>
            <span class="text-ch-danger" aria-hidden="true">*</span>
          </span>
          <select
            v-model="form.capability"
            class="h-9 rounded-md border bg-ch-input px-sm text-body-s text-ch-text-primary"
            :class="errors.capability ? 'border-ch-danger' : 'border-ch-border'"
            aria-label="账号能力"
          >
            <option value="">请选择能力</option>
            <option v-for="option in capabilityOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
          <span v-if="errors.capability" class="flex items-center gap-xs text-caption text-ch-danger">
            <i class="fa fa-circle-xmark" aria-hidden="true"></i>{{ errors.capability }}
          </span>
          <span v-else class="text-caption text-ch-text-tertiary">能力仅作声明，不构成任何投递 / 发布入口</span>
        </label>

        <label class="flex flex-col gap-xs">
          <span class="text-body-s text-ch-text-secondary">是否已认证</span>
          <select
            v-model="form.verifiedFlag"
            class="h-9 rounded-md border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
            aria-label="是否已认证"
          >
            <option v-for="option in verifiedOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
        </label>

        <FormInput
          v-model="form.appID"
          label="平台 appID"
          placeholder="微信为 appid，如 wx8f2c41d7a9e35b60"
          :word-limit="64"
          :error="errors.appID"
        />

        <!--
          ★ 2026-09-24 位置调整：明文凭据输入从弹窗底部移到「平台 appID」**之后**（与 appID 同排）。
            原因：原「凭据区」位于内容区末尾，而内容区 `max-height: 80vh` 可滚动 ——
            输入项落在默认视口的折叠线以下，只能滚动才可见，容易被误判成「弹窗里没有 AppSecret 输入项」。
            凭据状态（已配置 / 未配置）原为底部独立状态行，现就地折进本字段的 `help`，避免同一信息两处重复。
          ⚠ 安全约束不变：明文只存在于本弹窗本地变量与 `appSecret` 请求键（见 `buildPayload`）。
        -->
        <FormInput
          v-model="form.appSecret"
          label="平台 AppSecret"
          type="password"
          autocomplete="new-password"
          :placeholder="isEdit ? '留空 = 不修改' : '可选，填写则加密写入'"
          :help="appSecretHelp"
        />

        <label class="flex flex-col gap-xs">
          <span class="text-body-s text-ch-text-secondary">凭据到期时间</span>
          <input
            v-model="form.expireDate"
            type="date"
            class="h-9 rounded-md border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
            aria-label="凭据到期时间"
          />
          <span class="text-caption text-ch-text-tertiary">
            {{ form.expireDate ? `提交为 ${toYMDHMS(form.expireDate)}（当日 23:59:59）` : '留空 = 长期有效（不提交该字段）' }}
          </span>
        </label>

        <FormInput
          v-model="form.ownerID"
          label="归属 loginID"
          placeholder="如 chenliheng"
          :disabled="ownerFixed"
          :word-limit="64"
          :error="errors.ownerID"
          :help="ownerFixed
            ? '归属由服务端按当前登录账号派生（不可修改，也不随请求提交）'
            : '仅管理员可指定归属；非管理员由服务端强制为本人 loginID'"
        />

        <FormInput v-model="form.label" label="标签" placeholder="如 主号" :word-limit="32" :error="errors.label" />
      </div>

      <FormInput
        v-model="form.memo"
        label="备注"
        type="textarea"
        :rows="3"
        placeholder="用途说明、切换条件等（选填）"
        :word-limit="200"
        :error="errors.memo"
      />

      <!--
        ★ 2026-09-24：原「凭据区」（只读状态行 + 明文输入 + 安全说明）已收敛 ——
        输入项上移到「平台 appID」之后，状态信息折进该字段的 `help`；本块只保留安全口径声明。
      -->
      <p class="text-caption text-ch-text-tertiary">
        明文只存在于本弹窗的本地输入变量：不进 URL、不进 store、不进日志、不进错误提示，提交成功后立即清空。
        后端只要求非空，故前端不做阻断式长度校验；微信 AppSecret 通常为 32 位，可据此自查。
      </p>

      <p class="text-caption text-ch-text-tertiary">
        只读字段（不提交，由巡检回写）：健康状态 healthStatus、最近检查 lastCheckYMDHMS、最近调用 lastUseYMDHMS。
      </p>
    </div>
  </AppDialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { toast } from 'vue3-toastify'
import AppDialog from '@/components/base/AppDialog.vue'
import ConflictBanner from '@/components/base/ConflictBanner.vue'
import FormInput from '@/components/base/FormInput.vue'
import { accountAdd, accountModify } from '@/api/account'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** create | edit */
  mode: { type: String, default: 'create' },
  /** 编辑时的列表行（已白名单映射，不含 credentialCipher / credentialIV / appSecret） */
  account: { type: Object, default: null },
  /** 平台选项（来源 `platformqry`；由宿主页透传，保持字典单源） */
  platformOptions: { type: Array, default: () => [] },
  subjectOptions: { type: Array, default: () => [] },
  capabilityOptions: { type: Array, default: () => [] },
  verifiedOptions: { type: Array, default: () => [] },
  /**
   * ★ 2026-09-23「第三方账号管理」：归属锁定。
   * `true` → `ownerID` 只读展示（取值 `ownerLoginID`）且**不进请求体** —— 服务端会按登录 loginID
   * 强制派生归属（`subfunc/crudApi.py`：add 强制覆盖、modify 忽略该入参），前端不作可信来源。
   * `false`（缺省，管理员 / 全量台账）→ 保持原有「可指定归属」行为。
   */
  ownerFixed: { type: Boolean, default: false },
  /**
   * 归属锁定时用于展示的当前登录 loginID（`false` 时忽略）。
   * ⚠ 调用方必须用 **camelCase** 绑定 `:ownerLoginID="..."`：Vue 的 kebab 归一为 `ownerLoginId`
   *   （只大写首字母），与本 prop 的 `...ID` 结尾**不匹配**，写成 `owner-login-id` 会静默取默认值 ''。
   */
  ownerLoginID: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue', 'saved'])

/** 固定掩码（页面不持有密文 → 只能给占位符；「已配置」由 `credentialConfigured` 布尔表达） */
const CREDENTIAL_MASK = '••••••••'

/** 可提交字段（白名单）——明文凭据**只允许**经 `appSecret` 键提交 */
const SUBMIT_FIELD_LIST = [
  'accountCode', 'platform', 'accountName', 'subjectType', 'verifiedFlag', 'capability',
  'appID', 'expireYMDHMS', 'ownerID', 'label', 'memo'
]
/** 硬拦截：密文字段与 Mock 私有字段一律不得出现在请求体里（`appSecret` 走专用键，不在此列） */
const FORBIDDEN_FIELD_LIST = ['credentialCipher', 'credentialIV', 'credentialRef']

const saving = ref(false)
/** 就地错误说明（F0 等：原文 + 补充说明；弹窗保持打开、表单不清空） */
const submitError = ref('')
/**
 * 表单：白名单字段 + 明文凭据本地变量。
 * ★ `appSecret` **只在这里存在**（本地输入），提交后立即置空；不派生到任何其他状态。
 */
const form = reactive({
  accountCode: '', platform: '', accountName: '', subjectType: '', verifiedFlag: '0',
  capability: '', appID: '', expireDate: '', ownerID: '', label: '', memo: '', appSecret: ''
})
const errors = reactive({})

const isEdit = computed(() => props.mode === 'edit')
const credentialConfigured = computed(() => (isEdit.value ? Boolean(props.account?.credentialConfigured) : false))

/**
 * `appSecret` 字段的辅助说明。
 * ★ 2026-09-24：把「凭据当前状态」就地表达在本字段的 `help` 里 —— 原先挂在弹窗底部的独立状态行
 *   随输入项上移而取消，避免同一信息在两处重复（底部状态行同时也落在内容区滚动折叠线以下）。
 */
const appSecretHelp = computed(() => {
  if (!isEdit.value) return '可选：填写则创建时一并加密写入凭据（服务端 AES-256-GCM）'
  return credentialConfigured.value
    ? `当前：已配置（${CREDENTIAL_MASK}）· 留空 = 不改动既有凭据（不提交该字段）；填写则覆盖`
    : '当前：未配置 · 留空 = 不设置凭据；填写则加密写入'
})

/** `YYYY-MM-DD` → 14 位 `YYYYMMDDHHMMSS`（到期当日 23:59:59，与 R-26 的 14 位口径一致） */
const toYMDHMS = (dateText) => (dateText ? `${String(dateText).replace(/-/g, '')}235959` : '')
/** 14 位 / 8 位 `expireYMDHMS` → `YYYY-MM-DD`（回填日期选择器；非法即留空） */
function toDateInput(value) {
  const raw = String(value || '').trim()
  if (!/^\d{8,14}$/.test(raw)) return ''
  return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`
}

const textOf = (value) => (value === undefined || value === null ? '' : String(value))
/** 与 `utils/http.js` 的 `normalize` 同口径（去尾部多余分号） */
const normalizeMsg = (text) => String(text || '').trim().replace(/[;；]+$/, '')

function resetForm() {
  const source = isEdit.value && props.account ? props.account : {}
  form.accountCode = textOf(source.accountCode)
  form.platform = textOf(source.platform)
  form.accountName = textOf(source.accountName)
  form.subjectType = textOf(source.subjectType)
  form.verifiedFlag = textOf(source.verifiedFlag) || '0'
  form.capability = textOf(source.capability)
  form.appID = textOf(source.appID)
  form.expireDate = toDateInput(source.expireYMDHMS)
  // ★ ownerFixed：归属只读展示当前登录 loginID（不取自记录，避免把他人归属显示成本人）
  form.ownerID = props.ownerFixed ? textOf(props.ownerLoginID) : textOf(source.ownerID)
  form.label = textOf(source.label)
  form.memo = textOf(source.memo)
  form.appSecret = ''
  submitError.value = ''
  Object.keys(errors).forEach((key) => { delete errors[key] })
}

watch(
  () => props.modelValue,
  (open) => { if (open) resetForm() }
)

/** 必填与长度校验（必填缺失后端会返回 BA / CG，前端先拦一道）；★ 不对 `appSecret` 做阻断式校验 */
function validate() {
  const required = [
    ['accountCode', '账号幂等键为必填项'],
    ['platform', '请选择平台'],
    ['accountName', '账号名称为必填项'],
    ['subjectType', '请选择主体类型'],
    ['capability', '请选择能力']
  ]
  required.forEach(([key, message]) => {
    if (key === 'accountCode' && isEdit.value) return
    if (!textOf(form[key]).trim()) errors[key] = message
  })
  if (textOf(form.accountCode).length > 64) errors.accountCode = '账号幂等键最长 64 个字符'
  if (textOf(form.accountName).length > 128) errors.accountName = '账号名称最长 128 个字符'
  if (textOf(form.appID).length > 64) errors.appID = 'appID 最长 64 个字符'
  if (textOf(form.ownerID).length > 64) errors.ownerID = 'loginID 最长 64 个字符'
  if (textOf(form.label).length > 32) errors.label = '标签最长 32 个字符'
  if (textOf(form.memo).length > 200) errors.memo = '备注最长 200 个字符'
  return Object.keys(errors).length === 0
}

/**
 * 构造提交载荷（白名单）。
 * · create：后端 add 分支**空值也会写入** → 全量提交白名单字段（空串照发）；
 * · edit  ：后端 modify 分支**非空且与原值不同才写** → 只提交发生变化的非空字段；
 *           `accountCode` 只读不提交（避免改动幂等键）。
 * · 凭据：**仅当本地输入非空时**追加 `appSecret`（未修改则连键都不出现，避免无意义 body）。
 */
function buildPayload() {
  const payload = {}
  if (!isEdit.value) {
    SUBMIT_FIELD_LIST.forEach((key) => {
      if (key === 'ownerID' && props.ownerFixed) return
      payload[key] = key === 'expireYMDHMS' ? toYMDHMS(form.expireDate) : textOf(form[key])
    })
  } else {
    payload.recID = textOf(props.account?.recID)
    SUBMIT_FIELD_LIST.forEach((key) => {
      if (key === 'accountCode') return
      if (key === 'ownerID' && props.ownerFixed) return
      const next = key === 'expireYMDHMS' ? toYMDHMS(form.expireDate) : textOf(form[key])
      const prev = key === 'expireYMDHMS' ? textOf(props.account?.expireYMDHMS) : textOf(props.account?.[key])
      if (next === '' || next === prev) return
      payload[key] = next
    })
  }
  const secret = textOf(form.appSecret).trim()
  if (secret) payload.appSecret = secret
  return payload
}

/** 二次拦截：请求体**不得**出现密文字段（P0 硬约束；明文只允许走 `appSecret` 键） */
function assertNoCipherFields(payload) {
  const leaked = FORBIDDEN_FIELD_LIST.filter((key) => Object.prototype.hasOwnProperty.call(payload, key))
  if (!leaked.length) return true
  leaked.forEach((key) => { delete payload[key] })
  console.error('[P-11] 请求体出现被禁密文字段，已在发请求前删除（仅字段名）：', leaked)
  return false
}

async function submit() {
  if (saving.value) return
  if (!validate()) {
    toast.error('请先修正表单中的必填项')
    return
  }
  const payload = buildPayload()
  assertNoCipherFields(payload)
  const credentialSaved = Boolean(payload.appSecret)
  const changedCount = Object.keys(payload).filter((key) => key !== 'recID' && key !== 'appSecret').length
  if (isEdit.value && !credentialSaved && changedCount === 0) {
    toast.info('未检测到可提交的修改（空值不会覆盖服务端原值）')
    return
  }

  saving.value = true
  submitError.value = ''
  try {
    // silent：失败需要自行组织文案（尤其 F0 要追加「其它字段的修改未丢失」），B8 仍由 http.js 处理
    const config = { silent: true }
    const res = isEdit.value
      ? await accountModify(payload, config)
      : await accountAdd(payload, config)

    // ★ 内存清理：明文立即置空（此后不再被任何逻辑读取）
    form.appSecret = ''
    // 开发态证据（仅记布尔，不记任何值；生产构建随 DEV 判断剔除）
    if (import.meta.env.DEV && typeof window !== 'undefined') {
      window.__P11_LAST_SECRET__ = { cleared: form.appSecret === '', credentialSaved, at: Date.now() }
    }
    const recID = isEdit.value
      ? textOf(props.account?.recID)
      : textOf(res?.data?.recID || res?.recID)
    toast.success(credentialSaved ? '凭据已保存，建议立即巡检验证' : (isEdit.value ? '账号已更新' : '账号已创建'))
    emit('update:modelValue', false)
    emit('saved', {
      recID,
      accountCode: textOf(form.accountCode) || textOf(props.account?.accountCode),
      accountName: textOf(form.accountName) || textOf(props.account?.accountName),
      credentialSaved
    })
  } catch (error) {
    const code = String(error?.errCode || '')
    const content = normalizeMsg(error?.MSG?.content)
    if (code === 'F0') {
      // 无密钥 / 加密失败：后端**拒绝落库**；`MSG.content` 原样展示 + 追加一句；弹窗保持打开、表单不清空（§2.5）
      const raw = content || '凭据加密失败(CredentialCipherError): 未写入 credentialCipher, 明文未落库; 请检查环境变量 CH_CREDENTIAL_KEY 是否已配置'
      submitError.value = `${raw}；其它字段的修改未丢失（弹窗保持打开、表单内容未清空）`
      toast.error(raw)
    } else if (code !== 'B8') {
      // B8 已由 utils/http.js 统一 toast + 清会话跳登录，此处不重复提示
      toast.error(content || `保存失败（${code || '未知错误'}）`)
      console.error('[P-11] 账号写入失败', code)
    }
  } finally {
    saving.value = false
  }
}
</script>
