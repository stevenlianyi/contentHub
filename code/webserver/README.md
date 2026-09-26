# 内容中枢 · 前端（contentHub webserver）

内容生产与投递中台的前端工程。技术栈：**Vue 3 + Vite 5 + Element Plus + Tailwind CSS + Pinia + Vue Router**（JavaScript，不使用 TypeScript）。

> 本工程严格遵循 `plan/前端开发计划.md`。本文档当前描述的是 **Step 0（工程脚手架与去业务化）** 的产物状态。

## 环境要求

| 项 | 要求 |
|---|---|
| Node.js | ≥ 18（开发机实测 v22.20.0） |
| 包管理器 | npm（开发机实测 10.9.3） |

## 启动方式

```bash
cd code/webserver
npm i
npm run dev          # 访问 http://localhost:3000/chapp/
npm run build        # 产出 dist/
npm run preview      # 本地预览构建产物
```

开发服务：`port 3000`、`host 0.0.0.0`、`allowedHosts: true`。
构建产物基准路径为 `base: '/chapp/'`，与后端同源部署时前端挂在 `/chapp/` 下。

## 环境变量

| 变量 | `.env.development` | `.env.production` | 含义 |
|---|---|---|---|
| `VITE_API_BASE_URL` | `/chapi` | `/chapi` | 接口基础地址；`urlPath` = CMD 小写，如 `POST /chapi/topicqry` |
| `VITE_UPLOAD_URL` | `/upload` | `/upload` | 上传地址（待确认项，见计划附录 B） |
| `VITE_USE_MOCK` | `true` | `false` | Mock 开关 |

开发态由 Vite 代理转发到本机后端：

- `/chapi` → `http://127.0.0.1:5000`（`chAPI.py` 默认端口）
- `/upload` → `http://127.0.0.1:5000`

## Mock 开关

- `VITE_USE_MOCK === 'true'` 时，`src/mock/index.js` 的 `installMockAdapter(http)` 会把 axios 的自定义 adapter 短路到本地路由表（Step 3 落地）。
- 业务代码**零感知**：`src/api/*.js` 在有无后端时完全一致。
- 生产构建固定 `VITE_USE_MOCK=false`。

## 目录结构（Step 0 已建立部分）

```text
code/webserver/
├── index.html               # lang="zh-CN" class="dark"；标题「内容中枢」
├── package.json
├── vite.config.js           # base=/chapp/；alias @→src；代理 /chapi 与 /upload
├── postcss.config.js        # ESM（package.json 已声明 "type": "module"）
├── .env.development / .env.production
└── src/
    ├── main.js              # ElementPlus + 图标全量注册 + Toast + 暗色基底 + v-click-outside
    ├── App.vue              # 仅承载 RouterView
    ├── router/index.js      # 【Step 0 占位】Step 2 重写为 Hash 路由 + 守卫
    ├── store/index.js       # 【Step 0 占位】导出 pinia；Step 2 追加 modules/user.js
    ├── config/settings.js   # 接口地址 / B0·B8 / 会话键 / storage / title（Step 2 扩展）
    ├── utils/
    │   ├── accessToken.js   # sessionStorage 读写（已修复基线的 sessionStorage.clear() 缺陷）
    │   ├── common.js        # 纯函数：formatYMDHMS / wordCount / charCount / formatBytes / debounce 等
    │   └── cron.js          # 5 段 crontab 表达式校验
    ├── components/base/     # AppDialog.vue / AppPagination.vue
    └── styles/
        ├── tailwind.css     # 【Step 0 占位】Step 1 按 §2.3 完整重写
        └── element-vars.css # 【Step 0 占位】Step 1 输出 --ch-* 与 --el-* 覆盖 + .preview-scope
```

## 工程约定（全局）

1. **Token 单一数据源**：所有颜色/字号/间距/圆角/阴影只从 `src/js/tokens.js` 取（Step 1 建立），`.vue` 中禁止硬编码十六进制色值。
2. **请求与会话**：所有请求经 `src/utils/http.js`（Step 3）；`sessionID` 放**请求体**；`errCode !== 'B0'` 一律 toast `MSG.content` 且**保留用户已填内容**；`B8` 清会话并跳登录。
3. **列表分页**：服务端分页（`beginNum`/`endNum` + `total`），页面三态（loading / error / empty）齐备。
4. **状态表达**：一律「形状图标 + 颜色 + 文字」三重编码，禁止仅用颜色表达状态；未定义的中间态禁止新增。
5. **预览隔离**：预览区强制浅色隔离（`.preview-scope`），不得引用应用级暗色 Token。
6. **合规红线**：不引入任何小红书自动发布 / 自动投递入口。
7. **单文件 ≤ 600 行**；页面私有组件放 `views/<page>/`，跨页复用组件才进 `components/`。

## Step 0 说明（当前状态）

- 已建立可运行空壳：`npm run dev` 可启动，`<html class="dark">`，无控制台报错。
- `src/router/index.js` 中的 `/` 路由为**占位页面**（Step 2 将替换为 `MainLayout` + 14 个业务页面）。
- `src/styles/tailwind.css` 与 `src/styles/element-vars.css` 为**占位文件**，Step 1 将按设计 Token 完整重写。
- 未包含：`tailwind.config.js`、`src/js/tokens.js`、`src/api/**`、`src/mock/**`、`src/utils/http.js`、`src/views/**`（登录/业务页）——均属后续 Step。
