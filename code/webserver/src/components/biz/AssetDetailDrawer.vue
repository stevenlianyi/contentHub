<!-- ============================================================================
 * AssetDetailDrawer · P-04 素材详情抽屉（Step 8）
 * ----------------------------------------------------------------------------
 * 内容（计划 Step 8 要点 5）：大图预览 / fileID 与 contentHash（等宽 + 一键复制）/
 *   尺寸 / 字节数 / fileSystem 快照 / processStatus / 上传时间 / 引用关系（主题列表 + 跳转）/ 删除入口。
 * 元信息编辑：`assetmodify({ recID, label, memo })`（ch_asset 的 label ≤32 / memo ≤200）。
 *   ★ 附录 B R-22：后端写入一律「非空才落库」，**空值无法清空字段** → 只提交非空值，
 *     并在 UI 明确「清空不生效」，不承诺做不到的事。
 * 数据口径（§2.4.5）：图片 URL 只读后端出参（`fileUrl` / `thumbnailUrl`），前端不拼接 fileID。
 * 无障碍：role=dialog + aria-modal + Esc 关闭 + 打开时聚焦面板、关闭后归还焦点。
 * ========================================================================== -->
<template>
  <Teleport to="body">
    <div v-if="modelValue" class="fixed inset-0 z-50 flex justify-end bg-ch-base/80" @click.self="close">
      <aside
        ref="panelRef"
        role="dialog"
        aria-modal="true"
        aria-labelledby="asset-drawer-title"
        tabindex="-1"
        class="flex h-full w-full max-w-[560px] flex-col border-l border-ch-border bg-ch-elevated shadow-modal"
      >
        <header class="flex items-center justify-between gap-sm border-b border-ch-border px-xl py-md">
          <h3 id="asset-drawer-title" class="text-h3 text-ch-text-primary">素材详情</h3>
          <button
            type="button"
            class="rounded-md p-1 text-ch-text-secondary transition-colors duration-150 ease-out hover:bg-ch-hover hover:text-ch-text-primary"
            aria-label="关闭素材详情"
            @click="close"
          >
            <i class="fa fa-times" aria-hidden="true"></i>
          </button>
        </header>

        <div v-if="asset" class="flex min-h-0 flex-1 flex-col gap-xl overflow-y-auto px-xl py-lg">
          <!-- 大图预览 -->
          <div class="overflow-hidden rounded-lg border border-ch-border bg-ch-input">
            <img
              v-if="previewUrl"
              :src="previewUrl"
              :alt="altText"
              class="max-h-[320px] w-full object-contain"
              loading="lazy"
              decoding="async"
            />
            <p v-else class="flex items-center justify-center gap-sm py-3xl text-body-s text-ch-text-tertiary">
              <i class="fa fa-image" aria-hidden="true"></i>无预览图
            </p>
          </div>

          <!-- 标识符：等宽 + 一键复制 -->
          <div class="flex flex-col gap-md">
            <div v-for="row in idRows" :key="row.label" class="flex flex-col gap-xs">
              <span class="text-body-s text-ch-text-secondary">{{ row.label }}</span>
              <div class="flex items-center gap-sm">
                <code class="min-w-0 flex-1 truncate rounded-md border border-ch-border bg-ch-input px-md py-sm font-mono text-code text-ch-text-primary">
                  {{ row.value || '—' }}
                </code>
                <AppButton
                  size="sm"
                  icon="fa fa-copy"
                  :disabled="!row.value"
                  :disabled-reason="`${row.label} 为空，无可复制内容`"
                  :aria-label="`复制 ${row.label}`"
                  @click="copyText(row.value)"
                >
                  复制
                </AppButton>
              </div>
            </div>
          </div>

          <!-- 元信息 -->
          <dl class="grid grid-cols-2 gap-md text-body-s">
            <div v-for="row in metaRows" :key="row.label" class="flex flex-col gap-xs">
              <dt class="text-ch-text-secondary">{{ row.label }}</dt>
              <dd class="break-all text-ch-text-primary">{{ row.value || '—' }}</dd>
            </div>
            <div class="flex flex-col gap-xs">
              <dt class="text-ch-text-secondary">处理状态</dt>
              <dd class="inline-flex items-center gap-xs" :class="processMeta.cls">
                <i :class="processMeta.icon" aria-hidden="true"></i>
                <span>{{ processMeta.text }}</span>
              </dd>
            </div>
          </dl>

          <!-- 图注 / 备注（assetmodify；空值不落库 → 清空不生效） -->
          <section class="flex flex-col gap-md rounded-lg border border-ch-border bg-ch-surface px-lg py-md">
            <h4 class="text-body font-medium text-ch-text-primary">图注与备注</h4>
            <label class="flex flex-col gap-xs">
              <span class="text-body-s text-ch-text-secondary">图注（作为图片 alt，≤32 字）</span>
              <input
                v-model="form.label"
                type="text"
                maxlength="32"
                class="h-9 rounded-md border border-ch-border bg-ch-input px-md text-body text-ch-text-primary focus:border-ch-border-focus"
                placeholder="如：壁画色谱取样现场（自然光）"
                aria-label="素材图注"
              />
            </label>
            <label class="flex flex-col gap-xs">
              <span class="text-body-s text-ch-text-secondary">备注（≤200 字）</span>
              <textarea
                v-model="form.memo"
                rows="3"
                maxlength="200"
                class="rounded-md border border-ch-border bg-ch-input px-md py-sm text-body text-ch-text-primary focus:border-ch-border-focus"
                aria-label="素材备注"
              ></textarea>
            </label>
            <p class="text-caption text-ch-text-tertiary">
              服务端语义为「非空才落库」（附录 B R-22）：留空保存不会清空原值，只会跳过该字段。
            </p>
            <div class="flex justify-end">
              <AppButton type="primary" size="sm" :loading="saving" :disabled="!dirty" :disabled-reason="'没有需要保存的修改'" @click="save">
                保存图注与备注
              </AppButton>
            </div>
          </section>

          <!-- 引用关系 -->
          <section class="flex flex-col gap-md">
            <h4 class="text-body font-medium text-ch-text-primary">引用关系</h4>
            <AssetReferenceList
              :items="refItems"
              :total="refTotal"
              :extra-count="refExtraCount"
              :loading="refLoading"
              :error="refError"
              @retry="emit('retry-ref')"
            />
          </section>
        </div>

        <footer class="flex items-center justify-between gap-md border-t border-ch-border px-xl py-md">
          <p class="text-caption text-ch-text-tertiary">删除为软删除（只标记 delFlag），且服务端不做引用检查。</p>
          <AppButton type="danger" size="sm" icon="fa fa-trash" :disabled="!asset" @click="emit('remove')">
            删除素材
          </AppButton>
        </footer>
      </aside>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import AppButton from '@/components/base/AppButton.vue'
import AssetReferenceList from '@/views/assets/AssetReferenceList.vue'
import { ASSET_PROCESS_STATUS_MAP } from '@/config/chOptions'
import { assetModify } from '@/api/asset'
import { copyText, formatBytes, formatYMDHMS, fromNow } from '@/utils/common'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** assetqry 的一行（ch_asset 全列口径） */
  asset: { type: Object, default: null },
  refLoading: { type: Boolean, default: false },
  refError: { type: String, default: '' },
  refTotal: { type: Number, default: 0 },
  refItems: { type: Array, default: () => [] },
  refExtraCount: { type: Number, default: 0 }
})

const emit = defineEmits(['update:modelValue', 'remove', 'retry-ref', 'saved'])

const panelRef = ref(null)
const saving = ref(false)
const form = reactive({ label: '', memo: '' })
let lastActiveElement = null

const previewUrl = computed(() => String(props.asset?.fileUrl || props.asset?.imageUrl || ''))
/** ★ 无图注时用原始文件名兜底，**不产出空 alt**（裁定 G） */
const altText = computed(() => {
  const asset = props.asset || {}
  return String(asset.label || asset.origName || asset.fileName || '素材图，图注待补充')
})

/** 三重编码（形状图标 + 颜色 + 文字）：processStatus 为 ch_asset 的处理状态 */
const PROCESS_META = {
  RAW: { text: ASSET_PROCESS_STATUS_MAP.RAW, icon: 'fa-regular fa-circle', cls: 'text-ch-text-secondary' },
  PROCESSED: { text: ASSET_PROCESS_STATUS_MAP.PROCESSED, icon: 'fa fa-circle-check', cls: 'text-ch-info' },
  FAILED: { text: ASSET_PROCESS_STATUS_MAP.FAILED, icon: 'fa fa-circle-xmark', cls: 'text-ch-danger' }
}
const processMeta = computed(() => PROCESS_META[String(props.asset?.processStatus || '')] || PROCESS_META.RAW)

const idRows = computed(() => [
  { label: 'fileID', value: String(props.asset?.fileID || '') },
  { label: 'contentHash', value: String(props.asset?.contentHash || '') }
])

const metaRows = computed(() => {
  const asset = props.asset || {}
  const size = asset.origSizeBytes || asset.sizeBytes
  const created = fromNow(asset.regYMDHMS)
  return [
    { label: '尺寸', value: asset.width && asset.height ? `${asset.width} × ${asset.height}` : '' },
    { label: '字节数', value: size ? `${formatBytes(size)}（${size} B）` : '' },
    { label: '格式', value: [String(asset.fileExt || '').toUpperCase(), asset.mimeType].filter(Boolean).join(' · ') },
    { label: '文件后端（落库快照）', value: asset.fileSystem || '' },
    { label: '存储桶', value: asset.storageBucket || '' },
    { label: '原始文件名', value: asset.origName || '' },
    { label: '对象键', value: asset.objectName || '' },
    { label: '上传者', value: asset.ownerID || asset.uploadedBy || '' },
    { label: '上传时间', value: created.text ? `${formatYMDHMS(asset.regYMDHMS)}（${created.text}）` : '' }
  ]
})

const dirty = computed(() => {
  const asset = props.asset || {}
  return form.label !== String(asset.label || '') || form.memo !== String(asset.memo || '')
})

/** 打开抽屉时把当前值灌入表单（不保留上一次编辑残留） */
watch(
  () => [props.modelValue, props.asset?.recID],
  async ([open]) => {
    if (!open) {
      document.removeEventListener('keydown', onKeydown)
      if (lastActiveElement && typeof lastActiveElement.focus === 'function') lastActiveElement.focus()
      lastActiveElement = null
      return
    }
    form.label = String(props.asset?.label || '')
    form.memo = String(props.asset?.memo || '')
    lastActiveElement = document.activeElement
    document.addEventListener('keydown', onKeydown)
    await nextTick()
    panelRef.value?.focus()
  }
)

function onKeydown(event) {
  if (event.key === 'Escape') {
    event.preventDefault()
    close()
  }
}

function close() {
  emit('update:modelValue', false)
}

/** 保存：只提交非空值（与后端「非空才落库」语义一致，附录 B R-22） */
async function save() {
  const asset = props.asset || {}
  const patch = { recID: String(asset.recID || '') }
  if (form.label.trim()) patch.label = form.label.trim()
  if (form.memo.trim()) patch.memo = form.memo.trim()
  if (!patch.recID) return
  if (Object.keys(patch).length === 1) {
    // 两项都为空：后端不会把字段改成空串，明确告知而不是「假成功」
    emit('saved', { ...asset, notice: '图注与备注均为空：服务端不支持清空（空值不落库），本次未提交修改。' })
    return
  }
  saving.value = true
  try {
    await assetModify(patch)
    emit('saved', { ...asset, ...patch, notice: '图注与备注已保存' })
  } catch (error) {
    console.error('[AssetDetailDrawer] 保存素材元信息失败', error)
  } finally {
    saving.value = false
  }
}

onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>
