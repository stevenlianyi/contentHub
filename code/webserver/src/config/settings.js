// ============================================================
// 全局配置（Step 3 补全）
// ------------------------------------------------------------
// 冻结口径（见计划 §2.4 / §2.5）：
//   - 会话键 tokenName / storage / tokenTableName：sessionID 放请求体（§2.4.2），本地仅存这一个键；
//   - sucessRespCode 'B0' / sessionTimeOutCode 'B8'：http.js 响应拦截据此放行或清会话；
//   - msgKey 'contenthub'：后端 errMsgCommon 的文案段键（§2.4.4 报文字段 msgKey）。
// ★ 键名（title / tokenName / sucessRespCode / sessionTimeOutCode / storage / tokenTableName）
//   已被 Step 2 的 router 守卫、accessToken.js、Login.vue 引用，本步只增不改。
// ============================================================

// 应用标题（document.title 前缀由路由守卫同步，见 router/index.js afterEach）
export const title = '内容中枢'

// 接口基础地址：开发态由 Vite 代理 /chapi → http://127.0.0.1:5000
export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/chapi'

// 上传地址（Step 8；真实上传通道为 /upload —— nginx upload 模块注入 file.path/file.name 等字段
// 后转交后端 /hfile；前端直打 /hfile 会因缺字段被 fileHandler 拒绝回 D3，见 utils/upload.js 注释）
export const uploadUrl = import.meta.env.VITE_UPLOAD_URL || '/upload'

// 请求超时（毫秒）：渲染同步等待可能长达数分钟，故给到 30 分钟
export const requestTimeout = 1800000

// 响应码：B0 成功；B8 会话失效（前端清会话并跳登录）
export const sucessRespCode = 'B0'
export const sessionTimeOutCode = 'B8'

// 会话存储：sessionID 放请求体（§2.4.2），本地仅存此一个键
export const tokenName = 'sessionID'
export const storage = 'sessionStorage'
export const tokenTableName = 'chapp-adminInfo'

// 后端文案段键（响应报文 msgKey，§2.4.4）
export const msgKey = 'contenthub'

/**
 * ★ Step 17 追加（P-13 设置页「关于」区展示；越界授权小改，见交付说明）：
 * 设计规范版本号。出处：`plan/UI/contentHub UI 设计.md`（v1.1）。
 * 页面只读引用本常量；本文件与既有 `title` 等常量同处，不新增文件。
 */
export const DESIGN_SPEC_VERSION = 'v1.1'

// 聚合导出：utils/http.js 按计划示例以 `settings.xxx` 访问（同时保留上面的具名导出供既有代码使用）
export const settings = {
  title,
  apiBaseUrl,
  uploadUrl,
  requestTimeout,
  sucessRespCode,
  sessionTimeOutCode,
  tokenName,
  storage,
  tokenTableName,
  msgKey,
  designSpecVersion: DESIGN_SPEC_VERSION
}

export default settings
