/* ============================================================================
 * Step 8 P-04 浏览器端验收取证（临时脚本，验收后删除）
 * ----------------------------------------------------------------------------
 * 通过 Chrome DevTools Protocol 驱动真实 Chromium：
 *   1) 读取素材网格的真实 DOM（img 的 srcset / loading="lazy" / alt）；
 *   2) 采集 Network 层的图片请求 URL（证明 srcset 与 lazy 实际生效）；
 *   3) 打开某「引用 N 处」素材的删除弹窗，取证引用反查链路与主题列表；
 *   4) 通过上传面板上传同一张图片两次，取证 assetadd 两次的请求与响应（第二次 dedupHit='1'）。
 * 用法：node scripts/step8-verify.mjs   （需先启动 npm run dev）
 * ========================================================================== */
import { spawn } from 'node:child_process'
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const PORT = Number(process.env.CDP_PORT || 9333)
const ORIGIN = process.env.APP_ORIGIN || 'http://127.0.0.1:3002'
const APP_URL = `${ORIGIN}/chapp/`
const SHOT_DIR = join(tmpdir(), 'ch-p04-shots')

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
/** 1x1 合法 PNG，用于上传取证 */
const PNG_B64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg=='

const record = (key, value) => console.log(`\n### ${key}\n${typeof value === 'string' ? value : JSON.stringify(value, null, 2)}`)

const workDir = mkdtempSync(join(tmpdir(), 'ch-p04-work-'))
const userDataDir = mkdtempSync(join(tmpdir(), 'ch-p04-profile-'))
mkdirSync(SHOT_DIR, { recursive: true })
const fileA = join(workDir, '壁画色谱取样现场-上传证.png')
const fileB = join(workDir, '点茶击拂汤花形态-上传证.png')
writeFileSync(fileA, Buffer.from(PNG_B64, 'base64'))
writeFileSync(fileB, Buffer.from(PNG_B64, 'base64'))

const chrome = spawn(
  CHROME,
  [
    '--headless=new',
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${userDataDir}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-gpu',
    '--window-size=1440,900',
    '--hide-scrollbars',
    'about:blank'
  ],
  { stdio: 'ignore' }
)

let version = null
for (let i = 0; i < 80 && !version; i += 1) {
  try {
    version = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json()
  } catch {
    await sleep(250)
  }
}
if (!version) throw new Error('Chrome 调试端口未就绪（请检查 CHROME_PATH）')

const ws = new WebSocket(version.webSocketDebuggerUrl)
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve, { once: true })
  ws.addEventListener('error', reject, { once: true })
})

let msgId = 0
const pending = new Map()
const consoleLines = []
const netUrls = []

const formatArg = (arg) => {
  if (arg.value !== undefined) return String(arg.value)
  if (arg.preview?.properties) return `{${arg.preview.properties.map((p) => `${p.name}:${p.value}`).join(',')}}`
  return arg.description || arg.type
}

ws.addEventListener('message', (event) => {
  const msg = JSON.parse(event.data)
  if (msg.id && pending.has(msg.id)) {
    const task = pending.get(msg.id)
    pending.delete(msg.id)
    if (msg.error) task.reject(new Error(JSON.stringify(msg.error)))
    else task.resolve(msg.result)
    return
  }
  if (msg.method === 'Runtime.consoleAPICalled') {
    consoleLines.push(msg.params.args.map(formatArg).join(' '))
  }
  if (msg.method === 'Network.requestWillBeSent') netUrls.push(msg.params.request.url)
})

const send = (method, params = {}, sessionId) =>
  new Promise((resolve, reject) => {
    const id = (msgId += 1)
    pending.set(id, { resolve, reject })
    ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }))
  })

const { targetId } = await send('Target.createTarget', { url: 'about:blank' })
const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true })
for (const domain of ['Page.enable', 'Runtime.enable', 'Network.enable', 'DOM.enable']) await send(domain, {}, sessionId)

async function evalJs(expression, awaitPromise = false) {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise }, sessionId)
  if (result.exceptionDetails) {
    throw new Error(`页面异常: ${result.exceptionDetails.exception?.description || JSON.stringify(result.exceptionDetails)}`)
  }
  return result.result.value
}

async function waitFor(expression, timeout = 20000, interval = 400) {
  const deadline = Date.now() + timeout
  while (Date.now() < deadline) {
    if (await evalJs(expression)) return true
    await sleep(interval)
  }
  return false
}

async function shot(name) {
  const { data } = await send('Page.captureScreenshot', { format: 'png' }, sessionId)
  const file = join(SHOT_DIR, `${name}.png`)
  writeFileSync(file, Buffer.from(data, 'base64'))
  return file
}

/** 注入页面侧取证助手（页面 reload 后会丢失，需重新注入） */
const HELPERS = `window.__p04 = {
  imgs: () => [...document.querySelectorAll('img')].map((i) => ({ src: i.src, srcset: i.srcset, sizes: i.sizes, loading: i.loading, alt: i.alt })),
  cards: () => [...document.querySelectorAll('figure')].map((f) => { const li = f.closest('li'); return li ? li.innerText.replace(/\\n+/g, ' | ').trim() : '' }),
  reqs: () => (window.__MOCK_REQUESTS__ || []).map((r) => ({ url: r.url, payload: r.payload })),
  clickText: (text, nth) => { const list = [...document.querySelectorAll('button')].filter((b) => (b.textContent || '').includes(text)); const hit = list[nth || 0]; if (!hit) return 'NOT_FOUND'; hit.click(); return 'CLICKED: ' + (hit.textContent || '').trim() },
  dialogText: (must) => { const list = [...document.querySelectorAll('[role=dialog]')]; const hit = list.find((d) => !must || d.innerText.includes(must)); return hit ? hit.innerText.trim() : '' },
  setSelect: (labelPart, value) => { const s = [...document.querySelectorAll('select')].find((x) => (x.getAttribute('aria-label') || '').includes(labelPart)); if (!s) return 'NO_SELECT'; s.value = value; s.dispatchEvent(new Event('change', { bubbles: true })); return s.value },
  setValue: (selector, value) => { const el = document.querySelector(selector); if (!el) return 'NO_INPUT'; const proto = el instanceof window.HTMLTextAreaElement ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value); el.dispatchEvent(new Event('input', { bubbles: true })); return el.value },
  clickRemoveOfMostReferenced: () => {
    let best = null
    for (const f of document.querySelectorAll('figure')) {
      const li = f.closest('li')
      if (!li) continue
      const m = /引用 (\\d+) 处/.exec(li.innerText)
      if (!m) continue
      const n = Number(m[1])
      if (n > 0 && (!best || n > best.n)) best = { n, li, f }
    }
    if (!best) return 'NO_REF_CARD'
    const b = best.f.querySelector('button[aria-label^="移除素材"]')
    if (!b) return 'NO_REMOVE_BTN'
    const text = best.li.innerText.replace(/\\n+/g, ' | ').trim()
    b.click()
    return 'count=' + best.n + ' :: ' + text
  }
}; 'helpers-ready'`

const installHelpers = () => evalJs(HELPERS)

try {
  await send('Page.navigate', { url: APP_URL }, sessionId)
  await sleep(1500)
  await evalJs(`sessionStorage.setItem('chapp-adminInfo','mock-administrator-20260920'); location.hash='#/assets'; location.reload(); 'ok'`)
  const ready = await waitFor(`document.body.innerText.includes('素材图库')`)
  record('0. 已进入 /assets（Mock 管理员会话）', String(ready))
  await waitFor(`document.querySelectorAll('figure').length > 0`)
  await sleep(2500) // 等当前页引用反查（N+1）落定

  await evalJs(`window.__p04 = {
    imgs: () => [...document.querySelectorAll('img')].map((i) => ({ src: i.src, srcset: i.srcset, sizes: i.sizes, loading: i.loading, alt: i.alt })),
    cards: () => [...document.querySelectorAll('figure')].map((f) => { const li = f.closest('li'); return li ? li.innerText.replace(/\\n+/g, ' | ').trim() : '' }),
    reqs: () => (window.__MOCK_REQUESTS__ || []).map((r) => ({ url: r.url, payload: r.payload })),
    clickText: (text, nth) => { const list = [...document.querySelectorAll('button')].filter((b) => (b.textContent || '').includes(text)); const hit = list[nth || 0]; if (!hit) return 'NOT_FOUND'; hit.click(); return 'CLICKED: ' + (hit.textContent || '').trim() },
    dialogText: (must) => { const list = [...document.querySelectorAll('[role=dialog]')]; const hit = list.find((d) => !must || d.innerText.includes(must)); return hit ? hit.innerText.trim() : '' },
    setSelect: (labelPart, value) => { const s = [...document.querySelectorAll('select')].find((x) => (x.getAttribute('aria-label') || '').includes(labelPart)); if (!s) return 'NO_SELECT'; s.value = value; s.dispatchEvent(new Event('change', { bubbles: true })); return s.value },
    setValue: (selector, value) => { const el = document.querySelector(selector); if (!el) return 'NO_INPUT'; const proto = el instanceof window.HTMLTextAreaElement ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value); el.dispatchEvent(new Event('input', { bubbles: true })); return el.value },
    clickRemoveOfMostReferenced: () => {
      let best = null
      for (const f of document.querySelectorAll('figure')) {
        const li = f.closest('li')
        if (!li) continue
        const m = /引用 (\\d+) 处/.exec(li.innerText)
        if (!m) continue
        const n = Number(m[1])
        if (n > 0 && (!best || n > best.n)) best = { n, li, f }
      }
      if (!best) return 'NO_REF_CARD'
      const b = best.f.querySelector('button[aria-label^="移除素材"]')
      if (!b) return 'NO_REMOVE_BTN'
      const text = best.li.innerText.replace(/\\n+/g, ' | ').trim()
      b.click()
      return 'count=' + best.n + ' :: ' + text
    }
  }; 'helpers-ready'`)

  /* ---------------- 1. 网格双视图 / 缩略图 srcset / alt ---------------- */
  const cards = await evalJs('window.__p04.cards()')
  const imgs = await evalJs('window.__p04.imgs()')
  record('1. 网格首屏卡片（前 4 张）', cards.slice(0, 4))
  record('1b. 图片元素属性（前 2 个）', imgs.slice(0, 2))

  /* ---------------- 2. Network 层的缩略图请求（srcset + lazy） ---------------- */
  const imageUrls = [...new Set(netUrls.filter((u) => /placehold\.co/.test(u)))]
  record('2. Network 实际发出的图片请求（去重后前 6 条）', imageUrls.slice(0, 6))
  record('2b. Network 请求总数 / 图片请求数', `${netUrls.length} / ${netUrls.filter((u) => /placehold\.co/.test(u)).length}`)
  record('2c. 截图', await shot('01-assets-grid'))

  /* ---------------- 3. 列表视图（URL query + 表格列） ---------------- */
  await evalJs(`window.__p04.clickText('列表', 0)`)
  await sleep(1800)
  record('3. 视图切换后 URL', await evalJs('location.hash'))
  record('3b. 列表视图表格首行文本', await evalJs(`(() => { const t = document.querySelector('.el-table__body tbody tr'); return t ? t.innerText.replace(/\\n+/g, ' | ') : 'NO_TABLE' })()`))

  /* ---------------- 3c. 筛选写入 URL query + 仅当前页筛选 ---------------- */
  await evalJs(`window.__p04.clickText('网格', 0)`)
  await sleep(1500)
  const cardCountAll = (await evalJs('window.__p04.cards()')).length
  record('3c. 未筛选时当前页卡片数', cardCountAll)
  await evalJs(`window.__p04.setSelect('规格', '3:4')`)
  await sleep(1600)
  record('3d. 规格=3:4 → URL / 卡片数 / 首卡', {
    url: await evalJs('location.hash'),
    cards: (await evalJs('window.__p04.cards()')).length,
    first: (await evalJs('window.__p04.cards()'))[0]
  })
  await evalJs(`window.__p04.setSelect('引用状态', 'none')`)
  await sleep(1600)
  record('3e. 再叠加 引用状态=未引用 → URL / 卡片数', {
    url: await evalJs('location.hash'),
    cards: (await evalJs('window.__p04.cards()')).length
  })
  record('3f. 刷新后是否保持（reload + 读回 URL 与卡片数）', await (async () => {
    await evalJs(`location.reload(); 'reloading'`)
    await waitFor(`document.querySelectorAll('figure').length > 0`, 20000)
    await installHelpers()
    await sleep(2500)
    return { url: await evalJs('location.hash'), cards: (await evalJs('window.__p04.cards()')).length }
  })())
  await evalJs(`window.__p04.clickText('清除筛选', 0) || window.__p04.clickText('清除筛选', 1)`)
  await sleep(1800)
  record('3g. 清除筛选后 URL / 卡片数', { url: await evalJs('location.hash'), cards: (await evalJs('window.__p04.cards()')).length })

  /* ---------------- 3h. 详情抽屉：复制 / 元信息 / 图注保存（assetmodify） ---------------- */
  await evalJs(`document.querySelector('button[aria-label^="查看素材"]').click()`)
  await waitFor(`!!window.__p04.dialogText('素材详情')`, 15000)
  await sleep(2500)
  const drawerBefore = await evalJs(`window.__p04.dialogText('素材详情')`)
  record('3h. 详情抽屉内容（fileID / contentHash / 元信息 / 引用）', drawerBefore)
  await evalJs(`window.__p04.setValue('input[aria-label="素材图注"]', '壁画色谱取样现场·图注验收')`)
  await sleep(400)
  record('3i. 保存图注与备注（assetmodify）', await evalJs(`window.__p04.clickText('保存图注与备注', 0)`))
  await sleep(1800)
  record('3j. 保存后抽屉内容', await evalJs(`window.__p04.dialogText('素材详情')`))
  await evalJs(`document.querySelector('button[aria-label="关闭素材详情"]').click()`)
  await sleep(2000)
  record('3k. 关闭抽屉后首卡（alt 已取图注 + 卡片文案）', {
    img: (await evalJs('window.__p04.imgs()'))[0],
    card: (await evalJs('window.__p04.cards()'))[0]
  })

  /* ---------------- 4. 引用反查与删除弹窗（验收 3） ---------------- */
  record('4. 被点击的「引用 N 处」卡片', await evalJs('window.__p04.clickRemoveOfMostReferenced()'))
  const delOk = await waitFor(`!!window.__p04.dialogText('删除素材')`)
  await sleep(2000)
  record('4b. 删除弹窗内容（引用主题列表 + 确认按钮文案）', await evalJs(`window.__p04.dialogText('删除素材')`))
  record('4c. 弹窗内是否出现「确定」二字（须为 false）', await evalJs(`window.__p04.dialogText('删除素材').includes('确定')`))
  record('4d. 引用反查链路的请求（topicassetqry / topicqry）', (await evalJs('window.__p04.reqs()')).filter((r) => /topicassetqry|topicqry/.test(r.url)).slice(-6))
  record('4e. 截图', await shot('02-delete-referenced'))
  await evalJs(`window.__p04.clickText('取消', 0)`)
  await sleep(600)

  /* ---------------- 5. 上传两次同一张图片（验收 2、5） ---------------- */
  record('5. 打开上传面板', await evalJs(`window.__p04.clickText('上传素材', 0)`))
  await waitFor(`!!document.querySelector('input[type=file]')`)
  await sleep(500)
  record('5b. 上传面板首屏（文件后端展示）', await evalJs(`window.__p04.dialogText('当前文件后端')`))

  const setFiles = async (files) => {
    const { root } = await send('DOM.getDocument', { depth: -1 }, sessionId)
    const { nodeId } = await send('DOM.querySelector', { nodeId: root.nodeId, selector: 'input[type=file]' }, sessionId)
    await send('DOM.setFileInputFiles', { files, nodeId }, sessionId)
  }

  await setFiles([fileA, fileB])
  await sleep(800)
  record('6. 第一次上传开始', await evalJs(`window.__p04.clickText('开始上传', 0)`))
  await waitFor(`window.__p04.dialogText('当前文件后端').includes('已登记')`, 20000)
  await sleep(1200)
  record('6b. 第一次上传后面板内容', await evalJs(`window.__p04.dialogText('当前文件后端')`))
  record('6c. 截图', await shot('03-upload-first'))

  await setFiles([fileA])
  await sleep(800)
  record('7. 第二次上传（同一张图片）开始', await evalJs(`window.__p04.clickText('开始上传', 0)`))
  await waitFor(`window.__p04.dialogText('当前文件后端').includes('重复（已存在）')`, 20000)
  await sleep(1200)
  record('7b. 第二次上传后面板内容（去重可见）', await evalJs(`window.__p04.dialogText('当前文件后端')`))
  record('7c. 截图', await shot('04-upload-dedup'))

  const reqs = await evalJs('window.__p04.reqs()')
  record('8. 三次 assetadd 的实际请求（Mock 短路，取自 window.__MOCK_REQUESTS__）', reqs.filter((r) => r.url === '/assetadd'))
  record('8b. 三次 assetadd 的实际响应（Mock 开发态留痕 console）', consoleLines.filter((line) => line.includes('assetadd 响应')))

  await evalJs(`window.__p04.clickText('关闭', 0)`)
  await sleep(2200)
  record('9. 关闭面板后页面的去重横幅与网格标记', {
    banners: await evalJs(`[...document.querySelectorAll('[role=alert]')].map((a) => a.innerText.replace(/\\n+/g, ' | ').trim())`),
    gridDedup: (await evalJs('window.__p04.cards()')).filter((t) => t.includes('重复（已存在）')),
    firstCards: (await evalJs('window.__p04.cards()')).slice(0, 3),
    url: await evalJs('location.hash')
  })
  record('9b. 截图', await shot('05-after-dedup'))

  /* ---------------- 9c. 搜索 origName（keyword 服务端筛选） ---------------- */
  await evalJs(`window.__p04.setValue('input[aria-label^="搜索素材"]', '壁画色谱取样现场-上传证')`)
  await sleep(2000)
  record('9c. 按原始文件名搜索（keyword）', {
    url: await evalJs('location.hash'),
    cards: await evalJs('window.__p04.cards()')
  })
  await evalJs(`window.__p04.setValue('input[aria-label^="搜索素材"]', '')`)
  await sleep(1800)

  /* ---------------- 10. 页面标题/总数行 ---------------- */
  const totalOf = () => evalJs(`(document.querySelector('h1').parentElement.innerText.match(/共 (\\d+) 张/) || [])[1]`)
  record('10. 页面标题/总数行', await evalJs(`document.querySelector('h1').parentElement.innerText.replace(/\\n+/g, ' | ')`))

  /* ---------------- 11. 未引用素材直接删除（验收 3） ---------------- */
  const beforeDelete = await totalOf()
  record('11. 删除前总数', beforeDelete)
  record('11b. 被点击的「引用 0 处」卡片', await evalJs(`(() => { for (const f of document.querySelectorAll('figure')) { const li = f.closest('li'); if (li && /引用 0 处/.test(li.innerText)) { const b = f.querySelector('button[aria-label^="移除素材"]'); if (b) { b.click(); return li.innerText.replace(/\\n+/g, ' | ').trim() } } } return 'NO_UNREF_CARD' })()`))
  await waitFor(`!!window.__p04.dialogText('删除素材')`, 15000)
  await sleep(2000)
  record('11c. 未引用素材的删除弹窗', await evalJs(`window.__p04.dialogText('删除素材')`))
  await evalJs(`window.__p04.clickText('确认删除素材', 0)`)
  await sleep(3000)
  record('11d. 删除后总数 / 弹窗是否已关闭', {
    before: beforeDelete,
    after: await totalOf(),
    dialogClosed: !(await evalJs(`!!window.__p04.dialogText('删除素材')`))
  })
  record('11e. 截图', await shot('06-after-delete'))
} finally {
  try {
    ws.close()
  } catch {
    /* ignore */
  }
  chrome.kill()
  await sleep(500)
  console.log('\n### 截图目录\n' + SHOT_DIR)
}
