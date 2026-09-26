<!-- ============================================================================
 * AssetUploadPanel · P-04 素材上传面板（Step 8）
 * ----------------------------------------------------------------------------
 * 两步流程（★ 依据见 utils/upload.js 文件头 + 附录 B R-18）：
 *   uploadTemp(file)  → POST /upload（multipart，字段名 file）→ 取 **fileName** 作 localPath
 *   registerAsset()   → assetadd({ localPath, contentHash? }) → 服务端裁剪/EXIF/缩略图/上云/去重
 * ★ 本地无 nginx upload 模块时无法复现真实上传 → 本面板**以 Mock 验收为准**（不静默吞错、不假成功）。
 *
 * 硬要求：
 *   · 显示**当前文件后端**（裁定 E：无全局端点 → 显示已加载素材的 fileSystem 归纳值；
 *     无素材时显示「由服务端配置决定」，附录 B R-19；★ 不留空、不伪造）；
 *   · **去重结果必须可见**（裁定 F）：`dedupHit='1'` → 列表项原位打「⚠ 重复（已存在）」，
 *     并由父级在网格原位覆盖同一标记 + 顶部 `ConflictBanner`「该图片已存在，已复用」；
 *   · 结果**逐条反馈**；部分失败汇总为「成功 N / 失败 M」+ 失败项可展开（复用 ConflictBanner）。
 * ========================================================================== -->
<template>
  <div class="flex flex-col gap-lg">
    <!-- 当前文件后端（不留空、不伪造） -->
    <div class="rounded-lg border border-ch-border bg-ch-input px-lg py-md">
      <p class="text-body text-ch-text-primary">
        当前文件后端：<span class="font-mono text-ch-text-primary">{{ fileBackend }}</span>
      </p>
      <p class="mt-xs text-caption text-ch-text-tertiary">
        上传通道 <code class="font-mono text-code">POST {{ uploadUrl }}</code>（multipart，字段名
        <code class="font-mono text-code">file</code>）；裁剪、EXIF 剥离、缩略图、上云与 contentHash
        内容级去重均由服务端完成。
      </p>
      <p class="mt-xs text-caption text-ch-text-tertiary">
        全局 FILE_SYSTEM_MODE 无只读端点（F9A0 需 digest token，前端不可调用，附录 B R-19）：
        上方显示已加载素材的 fileSystem 归纳值，无素材时显示「由服务端配置决定」，不猜测、不留空。
      </p>
    </div>

    <!-- 上传结果：去重命中（必须可见） -->
    <ConflictBanner
      v-if="duplicated.length"
      type="warning"
      title="该图片已存在，已复用"
      closable
      @close="bannerClosed = true"
    >
      下列文件命中既有素材的 contentHash（`dedupHit='1'`），未重复上传、未新增记录，已直接复用：
      <ul class="mt-xs flex flex-col gap-xs">
        <li v-for="item in duplicated" :key="item.id">· {{ item.name }}</li>
      </ul>
    </ConflictBanner>

    <!-- 上传结果：部分失败汇总（成功 N / 失败 M + 可展开失败项） -->
    <ConflictBanner
      v-if="failed.length"
      type="warning"
      :title="`上传完成：成功 ${successCount} / 失败 ${failed.length}`"
      :actions="[{ key: 'toggle', label: showFailures ? '收起失败项' : '展开失败项' }]"
      @action="showFailures = !showFailures"
    >
      <ul v-if="showFailures" class="flex max-h-40 flex-col gap-xs overflow-y-auto">
        <li v-for="item in failed" :key="item.id">· {{ item.name }}：{{ item.error }}</li>
      </ul>
      <span v-else>失败项可展开查看原因；已成功的素材已登记，无需重传。</span>
    </ConflictBanner>

    <!-- 选择 / 拖拽（拖拽区含原生 file input 与按钮，键盘可达） -->
    <div
      class="flex flex-col items-center gap-md rounded-xl border border-dashed px-xl py-2xl text-center transition-colors duration-150 ease-out"
      :class="dragging ? 'border-ch-primary bg-ch-primary-subtle' : 'border-ch-border bg-ch-surface'"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <i class="fa fa-upload text-xl text-ch-text-tertiary" aria-hidden="true"></i>
      <p class="text-body-s text-ch-text-secondary">把图片拖到这里，或</p>
      <input ref="inputRef" type="file" multiple class="sr-only" aria-label="选择要上传的素材文件" @change="onPick" />
      <AppButton type="primary" icon="fa fa-upload" :disabled="running" @click="openPicker">选择文件</AppButton>
      <p class="text-caption text-ch-text-tertiary">
        非图片文件不做前端拦截（ALLOW_FILE_TYPE_LIST 为空 = 不限制），后端可能返回 D0。
      </p>
    </div>

    <!-- 待上传 / 上传中 / 结果逐条反馈 -->
    <ul v-if="items.length" class="flex flex-col gap-sm" role="list">
      <li
        v-for="item in items"
        :key="item.id"
        class="flex flex-wrap items-center gap-md rounded-lg border border-ch-border bg-ch-surface px-md py-sm"
      >
        <span class="min-w-0 flex-1 truncate text-body-s text-ch-text-primary" :title="item.name">{{ item.name }}</span>
        <span class="text-caption text-ch-text-tertiary">{{ formatBytes(item.size) }}</span>
        <span v-if="item.sizeHint" class="inline-flex items-center gap-xs text-caption text-ch-warning">
          <i class="fa fa-triangle-exclamation" aria-hidden="true"></i>
          <span>{{ item.sizeHint }}</span>
        </span>
        <span class="inline-flex items-center gap-xs text-caption" :class="statusClass(item)">
          <i :class="statusIcon(item)" aria-hidden="true"></i>
          <span>{{ statusText(item) }}</span>
        </span>
        <span v-if="item.status === 'failed'" class="w-full text-caption text-ch-danger">{{ item.error }}</span>
        <button
          v-if="item.status === 'pending' || item.status === 'failed'"
          type="button"
          class="rounded-md p-xs text-ch-text-secondary transition-colors duration-150 ease-out hover:bg-ch-hover hover:text-ch-text-primary"
          :aria-label="`从列表移除 ${item.name}`"
          @click="removeItem(item)"
        >
          <i class="fa fa-xmark" aria-hidden="true"></i>
        </button>
      </li>
    </ul>

    <div class="flex flex-wrap items-center justify-between gap-md">
      <p class="text-body-s text-ch-text-secondary">
        共 {{ items.length }} 个文件 · 成功 <span class="text-ch-text-primary">{{ successCount }}</span> ·
        去重复用 <span class="text-ch-text-primary">{{ duplicated.length }}</span> ·
        失败 <span class="text-ch-text-primary">{{ failed.length }}</span>
      </p>
      <div class="flex items-center gap-md">
        <AppButton v-if="items.length" size="sm" :disabled="running" @click="reset">清空列表</AppButton>
        <AppButton
          type="primary"
          icon="fa fa-arrow-up-from-bracket"
          :loading="running"
          :disabled="!uploadable"
          :disabled-reason="'请先选择文件'"
          @click="start"
        >
          开始上传（{{ uploadableCount }}）
        </AppButton>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import AppButton from '@/components/base/AppButton.vue'
import ConflictBanner from '@/components/base/ConflictBanner.vue'
import { formatBytes } from '@/utils/common'
import { assetMetaOf, describeUploadError, registerAsset, sha256OfFile, uploadTemp, uploadUrl } from '@/utils/upload'

/** 与服务端 MAX_PIC_SIZE 一致（超出后由服务端等比压缩，前端只做提示） */
const MAX_PIC_SIZE = 1920

const props = defineProps({
  /** 当前文件后端展示文案：已加载素材 fileSystem 归纳值，或「由服务端配置决定」（R-19） */
  fileBackend: { type: String, default: '由服务端配置决定' }
})

const emit = defineEmits(['done'])

const inputRef = ref(null)
const items = ref([])
const dragging = ref(false)
const running = ref(false)
const showFailures = ref(false)
const bannerClosed = ref(false)
let seq = 0

const duplicated = computed(() => (bannerClosed.value ? [] : items.value.filter((item) => item.status === 'dup')))
const failed = computed(() => items.value.filter((item) => item.status === 'failed'))
const successCount = computed(() => items.value.filter((item) => item.status === 'done').length)
const uploadableCount = computed(() => items.value.filter((item) => item.status === 'pending' || item.status === 'failed').length)
const uploadable = computed(() => uploadableCount.value > 0 && !running.value)

/** 图片尺寸：仅超限时给出提示（服务端将等比压缩至 MAX_PIC_SIZE 以内） */
async function readSizeHint(file) {
  if (!String(file.type || '').startsWith('image/')) return ''
  const src = URL.createObjectURL(file)
  try {
    const size = await new Promise((resolve) => {
      const image = new Image()
      image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight })
      image.onerror = () => resolve(null)
      image.src = src
    })
    if (!size) return ''
    if (size.width > MAX_PIC_SIZE || size.height > MAX_PIC_SIZE) {
      return `${size.width}×${size.height}，服务端将等比压缩至 ${MAX_PIC_SIZE} 以内`
    }
    return ''
  } finally {
    URL.revokeObjectURL(src)
  }
}

function addFiles(fileList) {
  // 仅对**待上传**项去重：已登记 / 已去重 / 失败的项允许再次选择（便于「同一张图传两次验去重」）
  const existing = new Set(
    items.value.filter((item) => item.status === 'pending').map((item) => `${item.name}|${item.size}|${item.lastModified}`)
  )
  Array.from(fileList || []).forEach((file) => {
    const key = `${file.name}|${file.size}|${file.lastModified}`
    if (existing.has(key)) return // 同一批内去重，避免误重复提交
    existing.add(key)
    seq += 1
    const item = { id: seq, file, name: file.name, size: file.size, lastModified: file.lastModified, status: 'pending', error: '', sizeHint: '', fileID: '', recID: '' }
    items.value.push(item)
    readSizeHint(file).then((hint) => {
      item.sizeHint = hint
    })
  })
  bannerClosed.value = false
}

const openPicker = () => inputRef.value?.click()
const onPick = (event) => {
  addFiles(event.target.files)
  event.target.value = ''
}
const onDrop = (event) => {
  dragging.value = false
  addFiles(event.dataTransfer?.files)
}
const removeItem = (item) => {
  items.value = items.value.filter((entry) => entry.id !== item.id)
}
const reset = () => {
  items.value = []
  showFailures.value = false
  bannerClosed.value = false
}

const STATUS_META = {
  pending: { text: '待上传', icon: 'fa fa-clock', cls: 'text-ch-text-tertiary' },
  uploading: { text: '上传中', icon: 'fa fa-circle-notch fa-spin', cls: 'text-ch-primary' },
  done: { text: '已登记', icon: 'fa fa-circle-check', cls: 'text-ch-success' },
  dup: { text: '⚠ 重复（已存在）', icon: 'fa fa-triangle-exclamation', cls: 'text-ch-warning' },
  failed: { text: '失败', icon: 'fa fa-circle-xmark', cls: 'text-ch-danger' }
}

const statusText = (item) => STATUS_META[item.status]?.text || item.status
const statusIcon = (item) => STATUS_META[item.status]?.icon || 'fa-regular fa-circle'
const statusClass = (item) => STATUS_META[item.status]?.cls || 'text-ch-text-secondary'

/** 逐条串行上传：每条都走「上传通道 → 取 localPath → assetadd 登记」两步 */
async function start() {
  running.value = true
  showFailures.value = false
  const results = []
  for (const item of items.value) {
    if (item.status === 'done' || item.status === 'dup') continue
    item.status = 'uploading'
    item.error = ''
    try {
      const localPath = await uploadTemp(item.file)
      // contentHash 仅在浏览器可计算时携带（服务端会校验，不一致回 C7 → 绝不错传）；
      // origName / fileExt / mimeType 必须回传，否则库内会落 UUID 且类型列为空（见 assetMetaOf 注释）
      const contentHash = await sha256OfFile(item.file)
      const res = await registerAsset(localPath, {
        ...assetMetaOf(item.file),
        ...(contentHash ? { contentHash } : {})
      })
      const dedup = String(res?.data?.dedupHit) === '1'
      item.fileID = String(res?.data?.fileID || '')
      item.recID = String(res?.data?.recID || '')
      item.status = dedup ? 'dup' : 'done'
      results.push({ name: item.name, status: item.status, fileID: item.fileID, recID: item.recID, dedup })
    } catch (error) {
      item.status = 'failed'
      item.error = describeUploadError(error)
      // 非 B0 已由 utils/http.js 统一 toast；这里仅做逐条留痕，保留用户已选文件（§2.5）
      results.push({ name: item.name, status: 'failed', reason: item.error })
    }
  }
  running.value = false
  showFailures.value = failed.value.length > 0
  emit('done', { results })
}

defineExpose({ reset })
</script>
