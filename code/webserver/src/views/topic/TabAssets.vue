<!-- ============================================================================
 * TabAssets · P-03 Tab2「素材」（Step 7，含素材图库选择抽屉）
 * ----------------------------------------------------------------------------
 * 数据：`topicassetqry`（按 `topicID` = **ch_topic.recID**，裁定 A）→ 每项含
 *   `fileID / imageUrl / caption / sortOrder / usageType`（后端按 sortOrder 升序返回）。
 * ★ 图片与图注**成对编辑**：图注输入框与图片在同一张卡片内，排序后不会错位（S2 痛点）。
 * 排序：拖拽（HTML5 dnd）+ **上移/下移按钮**（无障碍 P0，§2.11）——两者走同一个 `emit('reorder')`
 *   出口，保证结果一致；实际落库由外壳用 `topicassetmodify` 的 `orderList` 批量提交。
 * 封面：设为封面时不自造降级逻辑（裁定 C）：`topicassetadd(usageType='cover')` → 服务端把旧封面
 *   降级为 body → 外壳重新拉取附图并用被设封面项的 `fileID` 同步 `ch_topic.coverFileID`。
 * 解绑：`topicassetdel` 只解除引用（后端软删 delFlag='1'），**不动 `ch_asset` 素材本体**。
 * 添加：`assetqry`（**服务端分页**）图库抽屉多选 → 由外壳逐个 `topicassetadd`
 *   （`assetKey = {topicID}:{fileID}` 幂等）；已在附图里的素材禁止重复选择。
 * ========================================================================== -->
<template>
  <div class="flex flex-col gap-lg">
    <header class="flex flex-wrap items-center justify-between gap-md">
      <div>
        <h2 class="text-h3 text-ch-text-primary">附图（{{ assets.length }}）</h2>
        <p class="text-body-s text-ch-text-secondary">
          拖拽卡片或使用「上移 / 下移」调整顺序；顺序以 orderList 批量提交，图注与顺序一起保存。
        </p>
      </div>
      <div class="flex items-center gap-md">
        <AppButton size="sm" icon="fa fa-rotate-right" :loading="loading" @click="emit('refresh')">刷新</AppButton>
        <AppButton size="sm" icon="fa fa-plus" @click="openPicker">添加素材</AppButton>
      </div>
    </header>

    <Skeleton v-if="loading && !assets.length" type="card" :rows="4" label="附图加载中" />

    <EmptyState
      v-else-if="!assets.length"
      icon="fa fa-image"
      title="还没有附图"
      description="点击右上角「添加素材」从素材图库多选绑定；上传通道由 Step 8 提供。"
    />

    <ul v-else class="flex flex-col gap-md" role="list">
      <li
        v-for="(item, index) in assets"
        :key="item.recID || item.assetKey || item.fileID"
        class="flex cursor-grab flex-col gap-lg rounded-xl border bg-ch-surface p-lg transition-colors duration-150 ease-out md:flex-row"
        :class="dragIndex === index ? 'border-ch-primary opacity-60' : 'border-ch-border'"
        draggable="true"
        @dragstart="onDragStart(index)"
        @dragover.prevent="onDragOver(index)"
        @drop.prevent="onDrop"
        @dragend="onDragEnd"
      >
        <div class="w-full shrink-0 md:w-[176px]">
          <AssetThumb
            :url="item.imageUrl"
            :thumbnail-url="item.thumbnailUrl"
            :thumbnails="item.thumbnails || null"
            :caption="item.caption"
            :viewable="false"
            :removable="false"
            aspect="4:3"
            sizes="(max-width: 768px) 90vw, 176px"
          />
        </div>

        <div class="flex min-w-0 flex-1 flex-col gap-sm">
          <div class="flex flex-wrap items-center gap-sm">
            <span class="inline-flex items-center gap-xs text-caption text-ch-text-tertiary">
              <i class="fa fa-grip-vertical" aria-hidden="true"></i>
              <span class="tabular-nums">第 {{ index + 1 }} 张 · sortOrder {{ item.sortOrder }}</span>
            </span>
            <span
              v-if="isCover(item)"
              class="inline-flex items-center gap-xs rounded-sm bg-ch-primary-subtle px-sm py-[2px] text-caption text-ch-info"
            >
              <i class="fa fa-circle-check" aria-hidden="true"></i>
              当前封面
            </span>
          </div>

          <label class="flex flex-col gap-xs">
            <span class="text-body-s text-ch-text-secondary">图注（作为图片 alt，建议填写）</span>
            <input
              :value="item.caption"
              type="text"
              class="h-9 rounded-md border border-ch-border bg-ch-input px-md text-body text-ch-text-primary placeholder:text-ch-text-tertiary focus:border-ch-border-focus"
              :placeholder="`如：${suggestCaption(item)}`"
              :aria-label="`第 ${index + 1} 张附图的图注`"
              @change="emit('caption', item, $event.target.value)"
            />
          </label>

          <p class="text-caption text-ch-text-tertiary">
            fileID：<span class="font-mono text-code">{{ item.fileID }}</span>
            · 用途：{{ USAGE_TYPE_MAP[item.usageType] || item.usageType || '正文图' }}
          </p>

          <div class="flex flex-wrap items-center gap-sm">
            <AppButton
              size="sm"
              icon="fa fa-arrow-up"
              :disabled="index === 0"
              :disabled-reason="'已是第一张'"
              :aria-label="`上移第 ${index + 1} 张`"
              @click="move(index, -1)"
            >
              上移
            </AppButton>
            <AppButton
              size="sm"
              icon="fa fa-arrow-down"
              :disabled="index === assets.length - 1"
              :disabled-reason="'已是最后一张'"
              :aria-label="`下移第 ${index + 1} 张`"
              @click="move(index, 1)"
            >
              下移
            </AppButton>
            <AppButton
              size="sm"
              icon="fa fa-image"
              :disabled="isCover(item)"
              :disabled-reason="'该图已是封面'"
              @click="emit('cover', item)"
            >
              设为封面
            </AppButton>
            <AppButton size="sm" type="danger" icon="fa fa-trash" @click="emit('remove', item)">移除</AppButton>
          </div>
        </div>
      </li>
    </ul>

    <!-- 素材图库抽屉：assetqry 服务端分页 + 多选（确认后由外壳逐个 topicassetadd 绑定） -->
    <AppDialog
      v-model="pickerVisible"
      title="从素材图库选择"
      size="lg"
      @cancel="closePicker"
    >
      <div class="flex flex-col gap-lg">
        <div class="flex flex-col items-start gap-md md:flex-row md:items-end">
          <label class="flex min-w-0 flex-1 flex-col gap-xs">
            <span class="text-body-s text-ch-text-secondary">搜索素材</span>
            <input
              :value="keyword"
              type="search"
              class="h-9 w-full rounded-md border border-ch-border bg-ch-input px-md text-body text-ch-text-primary placeholder:text-ch-text-tertiary focus:border-ch-border-focus"
              placeholder="按图注 / 文件名搜索"
              aria-label="搜索素材"
              @input="onKeyword"
            />
          </label>
          <AppButton
            type="primary"
            icon="fa fa-upload"
            size="md"
            :loading="uploadRunning"
            :disabled="uploadRunning"
            @click="openFilePicker"
          >
            本地上传
          </AppButton>
          <input
            ref="fileInputRef"
            type="file"
            multiple
            accept="image/*"
            class="sr-only"
            aria-label="选择要上传的本地素材"
            @change="onFileChange"
          />
        </div>

        <ErrorState v-if="pickerError" :message="pickerError" hint="素材列表读取失败，请重试。" @retry="reloadPicker()" />

        <Skeleton v-else-if="pickerLoading" type="card" :rows="3" label="素材加载中" />

        <div v-else-if="pickerRows.length" class="grid grid-cols-2 gap-md md:grid-cols-3">
          <button
            v-for="item in pickerRows"
            :key="item.recID || item.fileID"
            type="button"
            class="flex flex-col gap-xs rounded-xl border p-sm text-left transition-colors duration-150 ease-out"
            :class="cardClass(item)"
            :disabled="isBound(item.fileID)"
            :aria-pressed="isSelected(item.fileID) ? 'true' : 'false'"
            @click="toggle(item.fileID)"
          >
            <AssetThumb
              :url="item.imageUrl"
              :thumbnail-url="item.thumbnailUrl"
              :thumbnails="item.thumbnails || null"
              :caption="item.caption"
              :selected="isSelected(item.fileID)"
              :duplicated="String(item.dedupHit) === '1'"
              :viewable="false"
              :removable="false"
              aspect="4:3"
              sizes="(max-width: 768px) 45vw, 220px"
            />
            <span class="truncate text-caption text-ch-text-primary" :title="item.caption">{{ item.caption }}</span>
            <span class="flex items-center gap-xs text-caption text-ch-text-tertiary">
              <i :class="pickerStateIcon(item.fileID)" aria-hidden="true"></i>
              <span>{{ pickerStateText(item) }}</span>
            </span>
          </button>
        </div>

        <EmptyState
          v-else
          icon="fa fa-image"
          title="图库为空"
          description="素材图库中没有可绑定的素材；可先在「素材图库」页上传，或直接从本地选择上传。"
          action-text="选择本地图片上传"
          :action-disabled="uploadRunning"
          :action-disabled-reason="uploadRunning ? '上传进行中，请稍候' : ''"
          @action="openFilePicker"
        />

        <AppPagination
          :total="pickerTotal"
          :page-size="pickerSize"
          :current-page="pickerPage"
          :disabled="pickerLoading"
          @page-change="onPickerPageChange"
        />
      </div>

      <template #footer>
        <AppButton size="md" @click="closePicker">取消</AppButton>
        <AppButton
          type="primary"
          size="md"
          icon="fa fa-plus"
          :disabled="!selected.length"
          :disabled-reason="'请先选择至少 1 张素材'"
          @click="submitPicker"
        >
          添加选中的 {{ selected.length }} 张
        </AppButton>
      </template>
    </AppDialog>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { toast } from 'vue3-toastify'
import AppButton from '@/components/base/AppButton.vue'
import AppDialog from '@/components/base/AppDialog.vue'
import AppPagination from '@/components/base/AppPagination.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import Skeleton from '@/components/base/Skeleton.vue'
import AssetThumb from '@/components/biz/AssetThumb.vue'
import { usePagination } from '@/components/base/composables/usePagination'
import { USAGE_TYPE_MAP } from '@/config/chOptions'
import { assetQry } from '@/api/asset'
import { debounce } from '@/utils/common'
import { assetMetaOf, describeUploadError, registerAsset, sha256OfFile, uploadTemp } from '@/utils/upload'

const props = defineProps({
  /** 该主题的附图（后端已按 sortOrder 升序返回） */
  assets: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  /** 主题当前封面 fileID（与服务端 coverFileID 对齐；用于判定「已是封面」） */
  coverFileId: { type: String, default: '' }
})

const emit = defineEmits(['refresh', 'reorder', 'caption', 'cover', 'remove', 'add'])

const dragIndex = ref(-1)
const overIndex = ref(-1)

/* ---------------- 附图卡片：排序 / 封面判定 ---------------- */
const boundFileIds = computed(() => props.assets.map((item) => String(item.fileID || '')))

/** 封面判定：优先看 usageType（服务端权威），退化到 coverFileID 比对 */
const isCover = (item) =>
  String(item.usageType || '') === 'cover' ||
  (Boolean(props.coverFileId) && String(item.fileID) === String(props.coverFileId))

const suggestCaption = (item) => (item.caption ? item.caption : `附图 ${item.fileID || ''}`)

/** 上移 / 下移（与拖拽共用同一出口 emit('reorder')，保证结果一致） */
function move(index, delta) {
  const target = index + delta
  if (target < 0 || target >= props.assets.length) return
  const next = [...props.assets]
  const [item] = next.splice(index, 1)
  next.splice(target, 0, item)
  emit('reorder', next)
}

function onDragStart(index) {
  dragIndex.value = index
}

function onDragOver(index) {
  overIndex.value = index
}

function onDragEnd() {
  dragIndex.value = -1
  overIndex.value = -1
}

function onDrop() {
  const from = dragIndex.value
  const to = overIndex.value
  if (from < 0 || to < 0 || from === to) {
    onDragEnd()
    return
  }
  const next = [...props.assets]
  const [item] = next.splice(from, 1)
  next.splice(to, 0, item)
  emit('reorder', next)
  onDragEnd()
}

/* ---------------- 图库抽屉：取数 / 多选 ---------------- */
const pickerVisible = ref(false)
const keyword = ref('')
const selected = ref([])
const pickerError = ref('')
const fileInputRef = ref(null)
const uploadRunning = ref(false)

async function fetchAssets({ beginNum, endNum }) {
  try {
    const params = { beginNum, endNum }
    if (keyword.value) params.keyword = keyword.value
    const res = await assetQry(params)
    pickerError.value = ''
    return res
  } catch (e) {
    pickerError.value = e?.MSG?.content || '加载失败'
    throw e
  }
}

const {
  page: pickerPage,
  size: pickerSize,
  total: pickerTotal,
  rows: pickerRows,
  loading: pickerLoading,
  refresh: reloadPicker,
  reset: resetPickerPage
} = usePagination(fetchAssets, { pageSize: 8, immediate: false })

const pushKeyword = debounce((value) => {
  keyword.value = value
  resetPickerPage()
}, 300)

const onKeyword = (event) => pushKeyword(event.target.value)

const isBound = (fileID) => boundFileIds.value.includes(String(fileID || ''))
const isSelected = (fileID) => selected.value.includes(String(fileID || ''))

const cardClass = (item) => {
  if (isBound(item.fileID)) return 'border-ch-border bg-ch-input opacity-70 cursor-not-allowed'
  if (isSelected(item.fileID)) return 'border-ch-primary bg-ch-primary-subtle'
  return 'border-ch-border bg-ch-surface hover:border-ch-primary'
}

const pickerStateIcon = (fileID) => (isSelected(fileID) ? 'fa fa-circle-check' : 'fa-regular fa-circle')

const pickerStateText = (item) => {
  if (isBound(item.fileID)) return '已添加'
  return isSelected(item.fileID) ? '已选中' : '点击选择'
}

function toggle(fileID) {
  const value = String(fileID || '')
  if (!value || isBound(value)) return
  const index = selected.value.indexOf(value)
  if (index >= 0) selected.value.splice(index, 1)
  else selected.value.push(value)
}

function onPickerPageChange({ page: nextPage, size: nextSize }) {
  if (nextSize && nextSize !== pickerSize.value) pickerSize.value = nextSize
  if (nextPage !== pickerPage.value) pickerPage.value = nextPage
}

function submitPicker() {
  if (!selected.value.length) return
  emit('add', [...selected.value])
}

/** 打开抽屉：重置选择与分页（避免沿用上一次的勾选） */
function openPicker() {
  selected.value = []
  keyword.value = ''
  pickerVisible.value = true
  resetPickerPage()
}

function closePicker() {
  pickerVisible.value = false
}

function openFilePicker() {
  fileInputRef.value?.click()
}

function onFileChange(event) {
  const files = event.target.files
  if (!files || !files.length) return
  uploadLocalFiles(files)
  event.target.value = ''
}

/**
 * 本地上传并自动绑定：与 P-04 素材图库共用同一套「uploadTemp → registerAsset」两步流程，
 * 上传成功的素材（含去重复用）直接作为 fileID 列表 emit('add') 交给外壳绑定到主题。
 */
async function uploadLocalFiles(fileList) {
  uploadRunning.value = true
  const fileIds = []
  const failed = []
  for (const file of Array.from(fileList || [])) {
    try {
      const localPath = await uploadTemp(file)
      const contentHash = await sha256OfFile(file)
      const res = await registerAsset(localPath, {
        ...assetMetaOf(file),
        ...(contentHash ? { contentHash } : {})
      })
      const fileID = String(res?.data?.fileID || '')
      if (!fileID) {
        throw new Error('素材登记后未返回 fileID')
      }
      fileIds.push(fileID)
    } catch (error) {
      failed.push({ name: file.name, error: describeUploadError(error) })
    }
  }
  uploadRunning.value = false

  if (failed.length) {
    toast.warning(`已上传 ${fileIds.length} 张，失败 ${failed.length} 张：${failed[0].error}`)
  } else if (fileIds.length) {
    toast.success(`已上传 ${fileIds.length} 张素材，即将绑定到主题`)
  }

  if (fileIds.length) {
    emit('add', fileIds)
  }
}

/** 供外壳在全部绑定成功后收起抽屉（`resetPicker` 供外壳统一收口） */
defineExpose({
  resetPicker: () => {
    closePicker()
    selected.value = []
  }
})
</script>
