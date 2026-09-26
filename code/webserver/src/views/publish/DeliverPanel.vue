<!-- ============================================================================
 * DeliverPanel · P-10 / P-03 Tab5「投递面板」（Step 14）
 * ----------------------------------------------------------------------------
 * 组成（自上而下）：
 *   ① 合规摘要条（**实时 `publishcheck`** 硬门禁）+「重新校验」+「去校验」+（仅展示）P-09「已校验 ✓ 时间」徽标；
 *   ② 失效账号 `ConflictBanner`（healthStatus=INVALID）→ 直达账号管理；
 *   ③ 阻断/错误明细（合规阻断明细 或 投递失败 `F0`/`C7`/合规侧 errCode）；
 *   ④ 双通道卡片：
 *      · 微信公众号 `wechat_mp` / `draft_box`：账号（含健康徽章）+ 今日已用配额 + 「推送到草稿箱」（两步二次确认）；
 *      · 素材包通道 `xiaohongshu`/`generic` / `asset_pack`：产物图数 + 规格 + 「导出素材包 ZIP」。
 *        ★ **只有导出，没有发布**：全组件不存在任何「发布 / 群发」动作按钮或暗示（AD-07）。
 *
 * 【硬约束】
 *   · 投递按钮的可用性 = 版式已选 ∩ 有 READY 产物 ∩ 账号有效 ∩ 合规无阻断 ∩ 配额未尽（裁定 B/D/E/F/G）；
 *   · 主题 `layoutCode` 为空 → **不渲染**投递按钮，改为提示条 +「去选版式」（跳 `?tab=layout`）；
 *   · 永不传 `autoPublish`；`F6`（不应发生）按 `MSG.content` 原样提示，不得改写为「发布成功」（裁定 L）；
 *   · 所有颜色取自 Token/Tailwind 语义类，无硬编码色值（§2.11）。
 * ========================================================================== -->
<template>
  <section class="flex flex-col gap-lg">
    <!-- ① 合规摘要（实时门禁） -->
    <div class="ch-card flex flex-wrap items-center gap-md">
      <i :class="complianceMeta.icon" :style="{ color: complianceMeta.color }" aria-hidden="true"></i>
      <span class="text-body-s" :style="{ color: complianceMeta.color }">{{ complianceMeta.label }}</span>
      <span class="text-body-s text-ch-text-secondary">
        阻断 {{ errorCount }} · 警告 {{ warningCount }}
      </span>
      <span v-if="compliance?.checkedAt" class="text-caption text-ch-text-tertiary">
        校验时间：{{ formatYMDHMS(compliance.checkedAt) }}
      </span>
      <span
        v-if="complianceMark"
        class="flex items-center gap-xs rounded-md border border-ch-success/40 px-sm py-xs text-caption text-ch-success"
        :title="'P-09「标记通过」的本机留痕；仅展示，放行条件仍是实时 publishcheck'"
      >
        <i class="fa fa-circle-check" aria-hidden="true"></i>
        <span>已校验 ✓ {{ formatYMDHMS(complianceMark.checkedAt || complianceMark.passedAt, 'MM-DD HH:mm:ss') }}</span>
      </span>

      <div class="ml-auto flex flex-wrap items-center gap-sm">
        <AppButton size="sm" :loading="complianceLoading" @click="refreshCompliance()">重新校验</AppButton>
        <RouterLink
          v-if="topic?.topicCode"
          :to="{ name: 'Compliance', params: { code: topic.topicCode } }"
          class="text-body-s text-ch-primary hover:text-ch-primary-hover"
        >
          去校验
        </RouterLink>
      </div>
    </div>

    <!-- ② 失效账号 -->
    <ConflictBanner
      v-if="invalidAccounts.length"
      type="warning"
      title="账号凭据已失效，请到账号管理重新授权"
      :actions="[{ key: 'accounts', label: '去账号管理' }]"
      @action="goAccounts"
    >
      共 {{ invalidAccounts.length }} 个公众号账号 healthStatus 为 INVALID。服务端在凭据解密失败时会把账号置为
      INVALID，此时投递必然失败（F0）；请先在账号管理重新登记凭据。
    </ConflictBanner>

    <!-- ③ 阻断 / 失败明细 -->
    <div
      v-if="errorCount > 0 || deliverError?.compliance"
      class="flex flex-col gap-sm rounded-xl border border-ch-danger/40 bg-ch-danger/10 px-xl py-lg"
      role="alert"
    >
      <p class="flex items-center gap-sm text-body-s text-ch-danger">
        <i class="fa fa-circle-xmark" aria-hidden="true"></i>
        <span>合规未通过：存在 {{ errorCount }} 项阻断，投递已被前端门禁拦下（后端仍会再校验）</span>
      </p>
      <ul class="flex flex-col gap-xs">
        <li
          v-for="(issue, index) in blockIssues"
          :key="`${issue.field}-${index}`"
          class="flex items-start gap-sm text-body-s text-ch-text-secondary"
        >
          <i class="fa fa-circle-xmark mt-xs shrink-0 text-ch-danger" aria-hidden="true"></i>
          <span>
            <span class="text-ch-text-tertiary">[{{ sourceLabel(issue.source) }}]</span>
            {{ issue.message }}
          </span>
        </li>
      </ul>
      <RouterLink
        v-if="topic?.topicCode"
        :to="{ name: 'Compliance', params: { code: topic.topicCode } }"
        class="text-body-s text-ch-primary hover:text-ch-primary-hover"
      >
        去校验并修正
      </RouterLink>
    </div>

    <!-- ③′ 非合规类失败（F0 / C7 / CG …）：按 MSG.content 原样呈现，不改写为成功 -->
    <ConflictBanner
      v-else-if="deliverError"
      type="warning"
      :title="`投递失败（${deliverError.code}）`"
      :actions="deliverError.code === 'F0' ? [{ key: 'accounts', label: '去账号管理' }] : []"
      @action="goAccounts"
    >
      <p>{{ deliverError.message }}</p>
      <p v-if="deliverError.field" class="font-mono text-code text-ch-text-tertiary">field: {{ deliverError.field }}</p>
      <p class="text-ch-text-tertiary">本次未产生任何发布记录变更；请修正后重新提交（幂等键由服务端下发，未自行构造）。</p>
    </ConflictBanner>

    <!-- ④ 双通道卡片 -->
    <div class="grid gap-lg xl:grid-cols-2">
      <!-- 微信公众号：草稿投递 -->
      <article class="ch-card flex flex-col gap-md">
        <header class="flex flex-wrap items-center gap-sm">
          <PlatformChip platform="wechat_mp" />
          <h2 class="text-h3 text-ch-text-primary">草稿箱投递</h2>
          <span class="rounded-md border border-ch-border px-sm py-xs text-caption text-ch-text-secondary">
            交付方式：草稿投递（draft_box）
          </span>
        </header>

        <p class="text-body-s text-ch-text-secondary">
          推送 ≠ 发布：本产品只把内容投递到公众号**草稿箱**，最终群发须人工在公众号后台完成（平台自 2025-07
          起回收了第三方发布接口权限）。
        </p>

        <!-- 版式缺失：不渲染投递按钮（裁定 B） -->
        <div
          v-if="layoutMissing"
          class="flex flex-wrap items-center gap-md rounded-lg border border-ch-warning/40 bg-ch-warning/10 px-lg py-md"
        >
          <i class="fa fa-triangle-exclamation text-ch-warning" aria-hidden="true"></i>
          <span class="text-body-s text-ch-text-secondary">请先为该主题选择版式后方可投递</span>
          <RouterLink
            v-if="topic?.topicCode"
            :to="{ name: 'TopicEdit', params: { code: topic.topicCode }, query: { tab: 'layout' } }"
            class="text-body-s text-ch-primary hover:text-ch-primary-hover"
          >
            去选版式
          </RouterLink>
        </div>

        <template v-else>
          <label class="flex flex-col gap-xs">
            <span class="text-caption text-ch-text-secondary">投递账号（ch_account，含健康状态）</span>
            <div class="flex flex-wrap items-center gap-sm">
              <select
                v-model="selectedAccountID"
                class="h-9 rounded-lg border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
                aria-label="选择投递账号"
              >
                <option v-for="account in accounts" :key="account.accountID" :value="String(account.accountID)">
                  {{ account.accountName || account.accountID }}
                </option>
              </select>
              <StateBadge v-if="selectedAccount" domain="health" :status="selectedAccount.healthStatus" />
            </div>
          </label>

          <label class="flex flex-col gap-xs">
            <span class="text-caption text-ch-text-secondary">投递产物（ch_artifact · READY，默认最新一条）</span>
            <select
              v-model="selectedArtifactID"
              class="h-9 rounded-lg border border-ch-border bg-ch-input px-sm text-body-s text-ch-text-primary"
              aria-label="选择投递产物"
            >
              <option v-for="artifact in artifacts" :key="artifact.recID" :value="String(artifact.recID)">
                {{ artifactLabel(artifact) }}
              </option>
            </select>
            <span v-if="!artifacts.length" class="text-caption text-ch-warning">
              该主题没有公众号 READY 产物；请先渲染出可用产物。
              <RouterLink
                v-if="topic?.topicCode"
                :to="{ name: 'TopicEdit', params: { code: topic.topicCode }, query: { tab: 'artifacts' } }"
                class="text-ch-primary hover:text-ch-primary-hover"
              >
                去渲染
              </RouterLink>
            </span>
          </label>

          <p class="flex flex-wrap items-center gap-sm text-body-s text-ch-text-secondary">
            <i class="fa fa-chart-simple text-ch-text-tertiary" aria-hidden="true"></i>
            <span>今日已用 {{ quotaLabel }} 次</span>
            <span class="text-caption text-ch-text-tertiary">
              （配额 = 当日成功投递条数 / 前端常量 {{ quotaLimit }}；ch_platform 无配额字段，非接口字段）
            </span>
          </p>

          <div class="mt-auto flex flex-wrap items-center gap-md pt-sm">
            <AppButton
              type="primary"
              size="lg"
              icon="fa fa-paper-plane"
              :loading="submitting"
              :disabled="!canDeliver"
              :disabled-reason="deliverBlockReason"
              @click="startPush()"
            >
              推送到草稿箱
            </AppButton>
            <span class="text-caption text-ch-text-tertiary">点击后将先做一次静默校验，再弹出二次确认</span>
          </div>
        </template>
      </article>

      <!-- 素材包：只导出，无发布 -->
      <article class="ch-card flex flex-col gap-md">
        <header class="flex flex-wrap items-center gap-sm">
          <PlatformChip :platform="packPlatform" />
          <h2 class="text-h3 text-ch-text-primary">素材包导出</h2>
          <span class="rounded-md border border-ch-border px-sm py-xs text-caption text-ch-text-secondary">
            交付方式：素材包 ZIP（asset_pack）
          </span>
        </header>

        <p class="flex items-start gap-sm text-body-s text-ch-text-secondary">
          <i class="fa fa-circle-info mt-xs shrink-0" aria-hidden="true"></i>
          <span>
            小红书禁止第三方自动发布，本产品仅提供素材包导出；导出后请在官方创作服务平台手动发布。
            ★ 导出**可逆且无平台动作**，故无需二次确认。
          </span>
        </p>

        <div class="flex flex-wrap items-center gap-md">
          <span class="text-caption text-ch-text-secondary">目标平台</span>
          <div class="flex items-center gap-xs rounded-lg border border-ch-border bg-ch-input p-xs" role="group" aria-label="切换素材包目标平台">
            <button
              v-for="code in PACK_PLATFORMS"
              :key="code"
              type="button"
              class="h-7 rounded-md px-sm text-caption transition-colors duration-150 ease-out"
              :class="packPlatform === code ? 'bg-ch-primary text-ch-text-inverse' : 'text-ch-text-secondary hover:bg-ch-hover'"
              :aria-pressed="packPlatform === code ? 'true' : 'false'"
              @click="packPlatform = code"
            >
              {{ platformLabel(code) }}
            </button>
          </div>
        </div>

        <p class="flex flex-wrap items-center gap-md text-body-s text-ch-text-secondary">
          <span>
            产物：{{ packArtifactText }}
          </span>
          <span>规格：{{ packSpecText }}</span>
        </p>

        <div class="mt-auto flex flex-wrap items-center gap-md pt-sm">
          <AppButton
            size="lg"
            icon="fa fa-download"
            :loading="packLoading"
            :disabled="!topicID"
            :disabled-reason="!topicID ? '请先选择主题' : ''"
            @click="exportPack(packPlatform)"
          >
            导出素材包 ZIP
          </AppButton>
          <span class="text-caption text-ch-text-tertiary">
            导出前由服务端运行合规闸门；未过则不出包（本页不会触发下载）
          </span>
        </div>

        <!-- 未过合规：展示阻断原因，★ 不下载、不当成功（裁定 J） -->
        <div
          v-if="packError"
          class="flex flex-col gap-sm rounded-lg border border-ch-danger/40 bg-ch-danger/10 px-lg py-md"
          role="alert"
        >
          <p class="flex items-center gap-sm text-body-s text-ch-danger">
            <i class="fa fa-circle-xmark" aria-hidden="true"></i>
            <span>未出包（{{ packError.code }}）：{{ packError.message }}</span>
          </p>
          <template v-if="packError.compliance">
            <p class="text-caption text-ch-text-secondary">
              阻断 {{ packError.compliance.errorCount || 0 }} 项 · 警告 {{ packError.compliance.warningCount || 0 }} 项
            </p>
            <ul class="flex flex-col gap-xs">
              <li
                v-for="(issue, index) in packBlockIssues"
                :key="`${issue.field}-${index}`"
                class="flex items-start gap-sm text-body-s text-ch-text-secondary"
              >
                <i class="fa fa-circle-xmark mt-xs shrink-0 text-ch-danger" aria-hidden="true"></i>
                <span>{{ issue.message }}</span>
              </li>
            </ul>
          </template>
          <RouterLink
            v-if="topic?.topicCode"
            :to="{ name: 'Compliance', params: { code: topic.topicCode } }"
            class="text-body-s text-ch-primary hover:text-ch-primary-hover"
          >
            去校验
          </RouterLink>
        </div>

        <!-- 成功：包内清单 + checkSum + 滑动顺序说明 -->
        <div v-if="packResult" class="flex flex-col gap-sm rounded-lg border border-ch-border bg-ch-input px-lg py-md">
          <p class="text-body-s text-ch-text-primary">
            素材包已生成：{{ packResult.imageCount }} 张图片 · {{ formatBytes(packResult.zipSizeBytes) }} ·
            <a
              :href="packResult.fileUrl"
              target="_blank"
              rel="noopener"
              class="text-ch-primary hover:text-ch-primary-hover"
            >
              重新下载（如未自动下载请右键另存为）
            </a>
          </p>
          <p class="font-mono text-code text-ch-text-secondary">checkSum: {{ packResult.checkSum }}</p>
          <p class="text-caption text-ch-text-tertiary">{{ packResult.checkSumMethod }}</p>
          <ol class="flex flex-col gap-xs">
            <li
              v-for="entry in packResult.entryList"
              :key="entry.entryName"
              class="flex flex-wrap items-center gap-sm text-caption text-ch-text-secondary"
            >
              <span class="font-mono text-ch-text-primary">{{ entry.entryName }}</span>
              <span>{{ entry.width }}×{{ entry.height }}</span>
              <span>{{ formatBytes(entry.sizeBytes) }}</span>
              <span v-if="String(entry.isCover) === '1'" class="text-ch-primary">（封面）</span>
            </li>
          </ol>
          <p class="text-caption text-ch-text-tertiary">
            其他条目：{{ packResult.extraEntryList.join(' / ') }}
          </p>
          <p class="text-caption text-ch-text-tertiary">★ 图片顺序即 App 内左右滑动浏览顺序（01_、02_… 与附图 sortOrder 一致）。</p>
        </div>
      </article>
    </div>

    <!-- 二次确认（Step 4 组件接线；props/文案未改） -->
    <ConfirmPublish
      :visible="confirmVisible"
      :topic="topic"
      :account="confirmAccount"
      :layout="confirmLayout"
      :artifact="confirmArtifact"
      :quota="{ used: usedCount, limit: quotaLimit }"
      :confirm-loading="submitting"
      @confirm="confirmPush()"
      @cancel="cancelConfirm()"
    />
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { toast } from 'vue3-toastify'
import AppButton from '@/components/base/AppButton.vue'
import ConflictBanner from '@/components/base/ConflictBanner.vue'
import ConfirmPublish from '@/components/biz/ConfirmPublish.vue'
import PlatformChip from '@/components/biz/PlatformChip.vue'
import StateBadge from '@/components/biz/StateBadge.vue'
import { COMPLIANCE_LEVEL_MAP, COMPLIANCE_SOURCE_MAP, PLATFORM_MAP, artifactKindMeta } from '@/config/chOptions'
import { formatBytes, formatYMDHMS } from '@/utils/common'
import { PACK_PLATFORMS, usePublishFlow } from '@/views/publish/usePublishFlow'

const props = defineProps({
  /** 主题记录（`topicID` 取 `ch_topic.recID`，裁定 A）；为空表示尚未选择主题 */
  topic: { type: Object, default: null }
})

const emit = defineEmits(['delivered', 'records-changed'])

const packPlatform = ref('xiaohongshu')

const {
  topicID,
  accounts,
  invalidAccounts,
  selectedAccountID,
  selectedAccount,
  artifacts,
  selectedArtifactID,
  selectedArtifact,
  packArtifactsByPlatform,
  platformRecords,
  quota,
  usedCount,
  quotaLimit,
  compliance,
  complianceMark,
  complianceLoading,
  errorCount,
  warningCount,
  deliverError,
  layoutMissing,
  canDeliver,
  deliverBlockReason,
  submitting,
  confirmVisible,
  packLoading,
  packResult,
  packError,
  loadAll,
  refreshCompliance,
  startPush,
  confirmPush,
  cancelConfirm,
  exportPack
} = usePublishFlow({
  getTopic: () => props.topic,
  onRecordsChanged: () => emit('records-changed'),
  // 投递成功（配额已在 handleDelivered 内按服务端 total 重算）→ 宿主页挂撤销倒计时条
  onDelivered: (record) => emit('delivered', record)
})

/* ------------------------------ 展示口径 ------------------------------ */

const platformLabel = (code) => PLATFORM_MAP[code]?.label || code
const sourceLabel = (source) => COMPLIANCE_SOURCE_MAP[String(source || '')] || String(source || '其他')

const complianceMeta = computed(() => {
  if (complianceLoading.value) return { ...COMPLIANCE_LEVEL_MAP.WARN, label: '合规校验中…' }
  if (errorCount.value > 0) return { ...COMPLIANCE_LEVEL_MAP.BLOCK, label: '合规未通过（存在阻断）' }
  if (compliance.value) {
    return warningCount.value > 0
      ? { ...COMPLIANCE_LEVEL_MAP.WARN, label: '合规通过（含警告，不阻断）' }
      : { ...COMPLIANCE_LEVEL_MAP.PASS, label: '合规通过（实时校验）' }
  }
  return { ...COMPLIANCE_LEVEL_MAP.BLOCK, label: '合规校验结果未取到' }
})

const blockIssues = computed(() => {
  const list = Array.isArray(compliance.value?.issues) ? compliance.value.issues : []
  return list.filter((item) => String(item.level).toUpperCase() === 'ERROR').slice(0, 5)
})
const packBlockIssues = computed(() => {
  const issues = Array.isArray(packError.value?.compliance?.issues) ? packError.value.compliance.issues : []
  const errors = issues.filter((item) => String(item.level).toUpperCase() === 'ERROR')
  return (errors.length ? errors : issues).slice(0, 5)
})

/** 配额展示：服务端 `total` 未回来之前显示「读取中」，**不**先显示「剩余 0」（裁定 G） */
const quotaLabel = computed(() => (quota.value.loaded ? `${usedCount.value} / ${quotaLimit.value}` : '读取中'))

const packArtifactText = computed(() => {
  const list = packArtifactsByPlatform.value[packPlatform.value] || []
  if (!list.length) return '该平台暂无 READY 产物（导出将由服务端按台账取图，可能返回 CB）'
  return packPlatform.value === 'xiaohongshu' ? `${list.length} 张（左右滑动多图集）` : `${list.length} 张`
})

const packSpecText = computed(() => {
  const record = platformRecords.value[packPlatform.value]
  if (!record) return '规格读取中…'
  const parts = []
  if (record.imageSpec) parts.push(String(record.imageSpec))
  if (packPlatform.value === 'xiaohongshu') parts.push('3:4')
  if (record.imageMaxCount) parts.push(`上限 ${record.imageMaxCount} 张`)
  return parts.join(' · ') || '—'
})

const artifactLabel = (artifact) => {
  const kind = artifactKindMeta(artifact?.kind).label
  const seq = artifact?.seqNo ? ` · 第 ${artifact.seqNo} 张` : ''
  const spec = artifact?.specNote ? ` · ${artifact.specNote}` : ''
  return `${artifact?.recID || '—'} · ${kind}${seq}${spec}`
}

/* ------------------------------ 二次确认复述值 ------------------------------ */

/** 账号复述：账号名 + 健康状态（healthStatus 权威取值 OK/EXPIRING/INVALID/UNKNOWN） */
const confirmAccount = computed(() => {
  const account = selectedAccount.value
  if (!account) return null
  const health = { OK: '有效', EXPIRING: '即将过期', INVALID: '已失效', UNKNOWN: '未知' }[String(account.healthStatus)] || account.healthStatus
  return {
    accountName: `${account.accountName || account.accountID}（${health}）`,
    accountCode: String(account.accountID || ''),
    platform: 'wechat_mp'
  }
})

const confirmLayout = computed(() => ({ layoutCode: String(props.topic?.layoutCode || '') }))

/**
 * 产物复述：Step 4 冻结的 `ConfirmPublish` 按 `artifactID → artifactCode → outputKind` 取第一个非空值展示，
 * 故此处把「recID · 类型 · 规格 · 体积」复述串放入 `artifactID`（recID 置于串首，仍可追溯）。
 * ★ 未修改 `ConfirmPublish` 的 props 名与文案（裁定 H：本步只接线）。
 */
const confirmArtifact = computed(() => {
  const artifact = selectedArtifact.value
  if (!artifact) return null
  const parts = [String(artifact.recID || '')]
  if (artifact.kind) parts.push(artifactKindMeta(artifact.kind).label)
  if (artifact.specNote) parts.push(String(artifact.specNote))
  if (artifact.sizeBytes) parts.push(formatBytes(artifact.sizeBytes))
  return { artifactID: parts.join(' · '), artifactCode: String(artifact.recID || ''), outputKind: String(artifact.kind || '') }
})

/* ------------------------------ 动作编排 ------------------------------ */

function goAccounts() {
  window.location.hash = '#/accounts'
}

/** 主题变化（切换主题）→ 重取全部前置（账号 / 产物 / 配额 / 合规） */
watch(() => topicID.value, () => loadAll(), { immediate: true })

/** 供宿主页「重试」使用：预填该记录的产物（仍需用户点击按钮，二次确认语义不变） */
function retryFrom(row) {
  const artifactID = String(row?.artifactId || '')
  if (artifactID && artifacts.value.some((item) => String(item.recID) === artifactID)) {
    selectedArtifactID.value = artifactID
    toast.info('已按该记录预填产物；请核对后点击「推送到草稿箱」重新发起（幂等键由服务端重新下发）')
    return true
  }
  toast.warning('该记录关联的产物已不在可用列表（可能已过期），请先重新渲染后再投递')
  return false
}

defineExpose({ retryFrom, refreshCompliance, loadAll })
</script>
