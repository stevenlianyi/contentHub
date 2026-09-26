<!-- ============================================================================
 * AccountDeleteConfirm · P-11 删除账号二次确认（Step 15 · 独立文件，裁定 I-②）
 * ----------------------------------------------------------------------------
 * 【后端事实（一律服从源码）】
 *   · `accountdel`（`subfunc/crudApi.py:2103-2164`）是**硬删除**：调用 `comMysql.delete_ch_account`；
 *     其上原有的软删写法 `#saveSet["delFlag"] = "1"` 已被注释（`:2133`）
 *     → 记录**不可恢复**，故确认文案必须写明「永久删除、不可恢复」，按钮必须用**动作动词**
 *     「确认删除账号」（UI 设计 §4.4：不用「确定」）。
 *   · 查不到记录返回 **`CB`**（无此账号记录）→ 视为「已不存在」，提示后刷新列表即可。
 *   · 历史发布记录本身保留：`ch_publish_record` 与该账号无外键级联，删除账号**不会**删除记录，
 *     但记录中的账号引用将失效（这正是文案要说明的点）。
 *
 * 【★ 关联发布记录数：已由「无数据源」升级为真实值（后端 R-31 已落地）】
 *   · `common/mysqlCommon.query_ch_publish_record` 新增 `accountID` 过滤
 *     （`ch_publish_record.accountID` = `ch_account.recID`，BIGINT）；`funcPublishrecordQry` 透传
 *     并写入 `indexKey`（与 R-28 同口径，不会串数据）→ 用法 `publishRecordQry({ accountID, beginNum:0,
 *     endNum:1 })` 取 `Number(total)`；
 *   · 故本组件在**弹窗打开时**按 `recID` 拉一次真实条数：加载中 `…`；失败 / `total` 缺失显示 `—`
 *     （**不编造、不用 0 冒充**）；`0` 是合法值，照实显示「0 条」；
 *   · ⚠ 若服务端未部署 R-31（忽略 `accountID`），返回的 `total` 会是**平台总量** —— 该风险已在
 *     产出说明登记；此处仍如实展示，但标签固定为「关联发布记录」：R-31 上线后才是账号维度。
 * ========================================================================== -->
<template>
  <AppDialog
    :model-value="modelValue"
    title="删除平台账号"
    size="md"
    danger
    confirm-text="确认删除账号"
    :confirm-loading="deleting"
    @update:model-value="emit('update:modelValue', $event)"
    @cancel="emit('update:modelValue', false)"
    @confirm="submit"
  >
    <div class="flex flex-col gap-lg">
      <dl class="flex flex-col gap-sm rounded-lg border border-ch-border bg-ch-input px-lg py-md text-body-s">
        <div class="flex flex-wrap items-center gap-sm">
          <dt class="w-28 shrink-0 text-ch-text-tertiary">账号名</dt>
          <dd class="min-w-0 flex-1 break-words text-ch-text-primary">{{ account?.accountName || '—' }}</dd>
        </div>
        <div class="flex flex-wrap items-center gap-sm">
          <dt class="w-28 shrink-0 text-ch-text-tertiary">账号幂等键</dt>
          <dd class="min-w-0 flex-1 break-all font-mono text-code text-ch-text-secondary">{{ account?.accountCode || '—' }}</dd>
        </div>
        <div class="flex flex-wrap items-center gap-sm">
          <dt class="w-28 shrink-0 text-ch-text-tertiary">平台</dt>
          <dd class="min-w-0 flex-1"><PlatformChip :platform="String(account?.platform || '')" size="sm" /></dd>
        </div>
        <div class="flex flex-wrap items-center gap-sm">
          <dt class="w-28 shrink-0 text-ch-text-tertiary">关联发布记录</dt>
          <dd class="min-w-0 flex-1 text-ch-text-primary" aria-live="polite">{{ countText }}</dd>
        </div>
      </dl>

      <ConflictBanner type="warning" title="删除为永久删除、不可恢复">
        该账号的历史发布记录仍会保留，但其中的账号引用将失效。后端 accountdel 直接执行物理删除
        （软删分支已注释），删除后无法恢复。
      </ConflictBanner>

      <p class="text-body-s text-ch-text-tertiary">
        「关联发布记录」由 publishrecordqry 按 accountID（= ch_account.recID）过滤后取 total；
        取不到时显示「—」，不以平台总量代替，也不估算。若服务端未部署该过滤能力，该数字可能为平台总量。
        删除成功后本页会刷新列表并重新汇总凭据健康数字。
      </p>
    </div>
  </AppDialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { toast } from 'vue3-toastify'
import AppDialog from '@/components/base/AppDialog.vue'
import ConflictBanner from '@/components/base/ConflictBanner.vue'
import PlatformChip from '@/components/biz/PlatformChip.vue'
import { accountDel } from '@/api/account'
import { publishRecordQry } from '@/api/publish'
import { errText } from '@/config/chOptions'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 待删除行（列表白名单映射后的行） */
  account: { type: Object, default: null }
})

const emit = defineEmits(['update:modelValue', 'deleted'])

const deleting = ref(false)
/** 'idle' | 'loading' | 'ok' | 'unknown' */
const countState = ref('idle')
const recordCount = ref(0)

/** 条数展示：加载中 `…` / 取到 `N 条` / 取不到 `—`（★ 0 是合法值，照实显示） */
const countText = computed(() => {
  if (countState.value === 'loading') return '…'
  if (countState.value === 'ok') return `${recordCount.value} 条`
  return '—'
})

/**
 * 拉取关联发布记录数（R-31）。
 * ★ `silent: true`：条数属于辅助信息，失败只降级为 `—`，不打扰用户（删除主流程不受影响）。
 */
async function loadCount() {
  const recID = String(props.account?.recID || '')
  if (!recID) {
    countState.value = 'unknown'
    return
  }
  countState.value = 'loading'
  try {
    const res = await publishRecordQry({ accountID: recID, beginNum: 0, endNum: 1 }, { silent: true })
    const total = Number(res?.total)
    if (!Number.isFinite(total)) {
      countState.value = 'unknown'
      return
    }
    recordCount.value = total
    countState.value = 'ok'
  } catch (error) {
    countState.value = 'unknown'
    console.error('[P-11] 关联发布记录数读取失败（降级显示 —）', error?.errCode || '')
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    recordCount.value = 0
    countState.value = 'idle'
    loadCount()
  }
)

async function submit() {
  if (deleting.value) return
  const recID = String(props.account?.recID || '')
  if (!recID) {
    toast.error('账号记录标识缺失，请刷新列表后重试')
    return
  }
  deleting.value = true
  try {
    // silent：CB 需要自定义文案（「无此账号记录」并刷新），其余错误自行兜底
    await accountDel({ recID }, { silent: true })
    toast.success('账号已删除')
    emit('deleted')
  } catch (error) {
    if (error?.errCode === 'CB') {
      toast.info('无此账号记录，已刷新列表')
      emit('deleted')
    } else {
      toast.error(error?.MSG?.content || errText(error?.errCode) || '删除失败，请稍后重试')
      console.error('[P-11] 删除账号失败', error)
    }
  } finally {
    deleting.value = false
  }
}
</script>
