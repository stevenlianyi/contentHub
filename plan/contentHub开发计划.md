# 内容中枢 contentHub · 完整开发计划

> **一句话定位**：不做「又一个一键分发工具」，做 **「选题资产工作台（Topic Asset Studio）」**——把一次选题的资料、图片、说明沉淀成可复用资产，再以版式引擎派生各平台合规产物。

| 项目 | 内容 |
|---|---|
| 项目名称 | contentHub（内容中枢 / 内容管理与多平台发布平台） |
| 项目类型 | 全新项目（`code/src` 为空骨架，从零搭建） |
| 工程基线 | `ylwzProject/museum`（复用其 `common/` 公共层与 `database/mysqlCodeGenerator.py`） |
| 目标平台 | 微信公众号（草稿投递）· 小红书（素材包导出）· 通用 HTML（站内预览/导出） |
| 技术栈 | Python 3.13 + Flask `/chapi` + Vue3 + Jinja2 + Playwright + Pillow + MySQL 8.0 + Redis |
| 数据表 | 12 张 `ch_*` 表 |
| 业务模块 | 8 个主干模块（C1–C8）+ 2 个后置模块（C9–C10） |
| 阶段划分 | Phase 0–3 共 4 个阶段，约 12 周（单人全职，不含资质等待） |
| 文档版本 | v1.0（2026-09-17） |
| 权威依据 | `plan/content-hub-开发计划v3.html`（架构与阶段口径）· `plan/content-hub-Phase0-任务清单.md`（可执行细节）· `plan/content-hub-调研与开发计划.html`（产品定位与合规边界） |

> **文档约定**
> 1. 本计划与既有文档冲突时，**以 `content-hub-开发计划v3` 为准**；涉及产品定位与平台合规边界时，参考 `content-hub-调研与开发计划`。
> 2. 计划中涉及基线代码的技术描述，均已对 `ylwzProject/museum/code/src` 做**只读实测核实**，差异之处在正文中显式标注「**实测差异**」。
> 3. 工时一律以**人天**为单位，按「单人全职、5 人天/周」估算。
> 4. 本文件为纯计划交付物，**不含任何代码实现**。

---

## 目录

1. [项目目标与范围](#1-项目目标与范围)
2. [核心功能模块拆解](#2-核心功能模块拆解)
3. [技术架构与选型建议](#3-技术架构与选型建议)
4. [开发阶段与里程碑划分](#4-开发阶段与里程碑划分)
5. [各阶段任务清单与预估工时](#5-各阶段任务清单与预估工时)
6. [依赖关系与风险点](#6-依赖关系与风险点)
7. [测试与验收标准](#7-测试与验收标准)
8. [部署与上线流程](#8-部署与上线流程)
9. [支线任务规划（并行 / 后续执行项）](#9-支线任务规划并行--后续执行项)
10. [附录](#10-附录)

---

# 1. 项目目标与范围

## 1.1 背景与产品定位

现有内容生产链路的痛点是「资产化缺失」：一次选题收集到的资料、图片、图注、来源、时期等信息，散落在个人笔记、聊天记录与本地文件夹中，最终只能靠人工拼装成一篇文章，无法复用、无法审计、无法派生多平台形态。

contentHub 以**「主题（Topic）」为核心内容资产**，而非以「文章」为核心：

- 一次录入 → 结构化落库（标题 / 简介 / 详述 / 作者 / 地点 / 来源 / 时期 / 标签 / 附图+图注）；
- 一份资产 → 版式引擎派生多形态（公众号长文 HTML / 小红书图集 PNG / 长图 / 通用 HTML）；
- 一次生成 → 多平台合规产物投递（公众号草稿箱 / 小红书素材包 ZIP）。

## 1.2 项目目标

| 维度 | 目标 | 衡量方式 |
|---|---|---|
| 产品目标 | 交付「主题资产 → 多版式渲染 → 多平台合规产物 → 通道投递」完整流水线 | 单一主题可同时产出公众号与小红书两套产物 |
| 技术目标 | 数据库定义文件 + 生成器驱动；文件后端配置驱动三态切换；渲染引擎模板可版本化 | 改 `ch_*.txt` 重跑生成器即可改表；改 `FILE_SYSTEM_MODE` 即可换后端 |
| 工程目标 | 复用 ylwz 既有公共层，不自研文件服务 / 账号体系 / 分页机制 | 净新增代码仅限「业务表 + 业务处理器 + 渲染引擎 + 平台适配器」 |
| 合规目标 | 零平台处罚事故；发布动作 100% 保留人工确认 | 连续运营 2 周无发布事故、无违规告警 |
| 交付目标 | v1.0 可交付：主题可建、产物可出、公众号可推草稿、小红书可导出素材包 | 里程碑 M3 验收通过 |

## 1.3 关键产品判断（决定范围的三个结论）

**结论一：全自动发布在国内主流平台已被政策封死，「半自动」是唯一可行形态。**

- 微信公众号：自 2025 年 7 月起，**个人主体账号、企业未认证账号**的 `freepublish/submit`（发布）接口权限被回收。个人订阅号通过 API 最多只能把文章推进**草稿箱**，最后一步「群发」必须人工在后台点击。
- 小红书：开放平台发布接口仅向通过资质审核的企业主体/品牌/服务商开放；且 2026 年 AI 治理规则明确将「AI 工具自动生成笔记、自动定时发布」列为**红线行为**，判定即限流/禁言，重度（全账号 AI 托管）将永久封禁并**连带同设备、同实名矩阵账号**。

⇒ **推送 ≠ 发布**。本项目交付形态定义为：**「一键推送到草稿箱 / 一键生成可发布素材包」，最终发布动作保留人工确认。**

**结论二：真正的技术难点是渲染引擎，不是发布通道。**

三个目标平台的产物形态完全不同，必须抽象出「版式中间层」：

| 渲染目标 | 产物形态 | 关键约束 |
|---|---|---|
| 微信公众号 | 内联样式 HTML | 外链图片一律不显示（须先转存 `mmbiz.qpic.cn`）；`class` 会被清洗；SVG 交互部分场景不稳，需静态图集兜底 |
| 小红书 | 图片 / 视频（图集 ≤18 图） | 不接受 HTML；「上下展示」须拼接为长图；须有 `HTML → PNG` 卡片渲染管线（Playwright 截图） |
| 通用 HTML | 站内预览 / 导出 / 第三方站点 | 无平台限制，作为兜底与调试形态 |

**结论三：这恰恰是市场空白，不是退路。**

市面工具是割裂的：排版工具（135 编辑器 / 秀米）只管单篇排版；分发工具（蚁小二 / 融媒宝 / Wechatsync）只管成品搬运；Headless CMS（Strapi / Payload / Directus）只管结构化存储。**没有产品做「结构化主题资产 → 多版式渲染 → 各平台合规产物 → 通道投递」这条完整流水线**——因为它们没有内容模型。本项目的护城河正在于此。

## 1.4 范围边界

### 1.4.1 在范围内（v1.0）

| 类别 | 内容 |
|---|---|
| 内容资产 | 主题 CRUD（全字段）、附图与图注绑定、主题状态机、主题版本快照（P2） |
| 素材图库 | 三后端上传切换、`contentHash` 内容级去重、规格裁剪压缩、EXIF 剥离、缩略图生成、封面图生成 |
| 版式引擎 | 版式 DSL（`ch_layout`）、内置 4 套模板（上下 / 左右轮播 / 长图 / **左右滑动多图集**）、Jinja2 服务端渲染、站内预览 |
| 平台适配 | 微信内联样式器与图片转存、小红书图集卡片（Playwright 截图）、通用 HTML |
| 发布投递 | 公众号草稿投递（`draft/add`）、小红书素材包 ZIP 导出、幂等防重发、发布记录 |
| 合规风控 | AI 内容标识、发布频率限流、敏感词检测、平台规格校验、二次确认 |
| 账号凭据 | 多账号凭据 AES 加密存储、健康巡检、平台能力矩阵展示 |
| 开放接口 | MCP Server（独立 `code/src/mcpapi/` 包，8 个只读 tool + 3 个 resource，**streamable-http** 传输；鉴权沿用 Redis session + `ROLE_CMD_LIST`）、审计日志 |
| 运维 | 建表脚本、种子灌入、渲染 worker、审计日志归档、监控告警 |

### 1.4.2 不在范围内（明确不做，红线）

| 不做项 | 原因 |
|---|---|
| ❌ 小红书全自动发布 / AI 托管运营 | 平台红线，判罚即限流/封号，且连带矩阵账号 |
| ❌ 个人号承诺「一键群发」 | 微信已于 2025.07 回收个人主体发布接口权限 |
| ❌ 自动点赞、自动评论、自动私信 | 平台红线 |
| ❌ 多账号同设备互赞互评、IP 指纹伪装批量养号 | 平台红线，且与产品价值无关 |
| ❌ 爬虫式抓取平台内容 | 合规风险 |
| ❌ 首期自建多租户 SaaS 后台 | 范围蔓延；v1.0 为内部工具形态 |
| ❌ 首期扩展知乎 / 头条 / 微博 / B 站等平台适配器 | 推迟至 Phase 4，接口设计需预留 |
| ❌ 首期数据回收看板（阅读 / 点赞回流） | P2，v1.0 后 |

## 1.5 三条红线（贯穿全程，不可违反）

| # | 红线 | 违反后果 | 强制做法 |
|---|---|---|---|
| **R1** | 数据库结构以 `ch_*.txt` 为**唯一数据源**，业务层**禁止裸 SQL** | 表结构漂移、生成代码与 DDL 不一致 | 改表只改 `database/ch_*.txt` → 重跑生成器 → 合并 `common/mysqlCommon.py`；业务代码只调 `comMysql.xxx_ch_*()` |
| **R2** | 文件后端**配置驱动**：`FILE_SYSTEM_MODE` ∈ {ALIOSS, TENCENT, SELFFILE} | 后续无法切换云厂商，迁移成本剧增 | 代码中**不得出现** `if FILE_SYSTEM_MODE == "ALIOSS"` 之类的硬编码分支，一律经 `common/fileStorageCommon.py` 门面 |
| **R3** | 生成器**只走 `readFromFile()` 路径**（`-i xx.txt`） | 产出 `func['xxx']Add` 等非法函数名，建表丢失主键 | 绝不向生成器传原生 `CREATE TABLE` SQL；不使用 `handleSQL()` / `mysqlStatementHandle()` 路径 |

## 1.6 验收与成功标准（v1.0）

1. 单一主题可同时产出：微信公众号内联样式 HTML（可推入草稿箱）+ 小红书图集 PNG / 长图（可导出 ZIP）。
2. 公众号草稿箱投递端到端打通，且**任何发布动作都需人工二次确认**。
3. 小红书**不存在**任何自动发布代码路径，仅素材包导出。
4. 四套内置版式在真机 / 手机尺寸模拟下排版无错乱；小红书多图集**比例统一**、顺序可按滑动浏览顺序编排。
5. 任意时刻切换 `FILE_SYSTEM_MODE`，历史文件仍可正确读取（依赖 `ch_asset.fileSystem` 快照）。
6. 真实账号连续运营 2 周无发布事故、无平台违规告警。

---

# 2. 核心功能模块拆解

## 2.1 业务链路（六步，对比 museum 的九步）

```text
①建主题  →  ②配素材  →  ③选版式×平台  →  ④渲染  →  ⑤合规校验  →  ⑥投递
```

| # | 环节 | 落库表 | 主状态字段 |
|---|---|---|---|
| ① | 建 / 改主题 | `ch_topic`、`ch_topic_version` | `ch_topic.status = DRAFT` |
| ② | 配素材 | `ch_asset`、`ch_topic_asset` | `ch_asset.processStatus` |
| ③ | 选版式 | `ch_layout`、`ch_platform` | 只读配置 |
| ④ | 渲染 | `ch_render_job`、`ch_artifact` | `ch_render_job.jobStatus` |
| ⑤ | 合规校验 | 不落库（写审计） | 结果进 `ch_audit_log` |
| ⑥ | 投递 | `ch_publish_record`、`ch_account` | `ch_topic.publishStatus` |

> 相比 museum 的九阶段链路（采集→清洗→图片→翻译→审核→成稿→图片处理→发布→回流），本项目是**人驱动编辑发布**而非爬取驱动，因此砍掉采集/清洗/翻译，压到六步。

## 2.2 模块清单（C1–C10）

模块从早期设计的 14 个收敛到 **8 个主干**（另 2 个为 P2 后置）。

| ID | 模块 | 职责 | 依赖 | 优先级 | 落点 |
|---|---|---|---|---|---|
| **C1** | 接入与权限 | 复用 accountService；角色裁剪；sessionID 校验 | ylwz 账号服务 | P0 | `main/`、`config/basicSettings.py` |
| **C2** | 主题管理 | 主题 CRUD；字段区间校验；状态机；版本快照 | C1 | P0 | `processor/topicService.py` |
| **C3** | 素材图库 | 上传（三后端切换）、内容哈希去重、规格裁剪、附图与说明绑定 | C1、文件服务 | P0 | `processor/assetService.py` |
| **C4** | 版式引擎 | 版式 DSL、内置 4 套模板、上下/轮播/长图/**左右滑动多图集**渲染 | C2、C3 | P0 | `engine/layoutEngine.py` |
| **C5** | 平台适配 | `PlatformAdapter` 统一接口；微信内联化；小红书图集卡片 | C4 | P0 | `processor/platformAdapter/` |
| **C6** | 发布投递 | 公众号推草稿、素材包打包、幂等、发布记录 | C5 | P0 | `processor/publishService.py` |
| **C7** | MCP 与开放接口 | MCP Server（8 个只读 tool + 3 个 resource）；Redis session + `ROLE_CMD_LIST` 鉴权；审计 | C2 / C4 / C6 | P0（Phase 3） | `mcpapi/`（`mcp_entry.py` + `mcpPost.py`） |
| **C8** | 合规校验 | AI 标识、频率限流、平台规格校验、二次确认 | C2、C5 | P0 | `processor/complianceService.py` |
| C9 | 版本与协作 | 草稿多版本对比 / 回滚、审核流转 | C2 | P2 | `processor/topicService.py` |
| C10 | 数据回收 | 阅读 / 点赞数据回流 | C6 | P2 | `processor/statsService.py` |

## 2.3 模块依赖关系

```text
外部依赖（Day 1 启动，2~4 周）
  企业号认证 ──► C1 凭据落库 ──► C6 公众号草稿投递

主干（可并行，不依赖外部审核）
  C1 ─► C2 ─► C3 ─► C4 ─► C5 ─► C6 ─► 产物
                        └─► C7（MCP Hub，依赖 C4 渲染 + C6 投递）

横切
  C8 合规校验：C2 输入校验 + C5 产物校验，两条入口
```

### 2.3.1 关键依赖说明

| 依赖 | 类型 | 说明 | 处理策略 |
|---|---|---|---|
| 企业号认证 → C6 | 外部、强 | 未过审则公众号只能推草稿箱（个人号连草稿也受限） | Day 1 启动；主干不阻塞；无资质阶段以「素材包导出」为完整替代形态 |
| C4 → C7 | 内部、强 | MCP 的 8 个 tool 描述的是渲染/投递动作，接口随渲染引擎定型 | **C7 必须等到 C4/C6 稳定后再做，排入 Phase 3** |
| C3 → C4 | 内部、强 | 渲染需要可访问的图片 URL | `fileID → URL` 由后端出参转换，渲染前统一取临时 URL |
| C5 → C8 | 内部、强 | 规格校验需知晓各平台产物规格 | 规格来自 `ch_platform` 配置表，不硬编码 |

## 2.4 平台能力矩阵（产品内必须展示）

把「平台能做什么、不能做什么」直接展示给用户，避免用户把平台限制误判为产品缺陷。数据来源为 `ch_platform` 配置表。

| 能力项 | 个人订阅号 | 认证企业订阅号 | 认证服务号 | 小红书 |
|---|---|---|---|---|
| 获取 access_token | 可用 | 可用 | 可用 | 需资质 |
| 上传封面 / 正文图 | 可用 | 可用 | 可用 | 素材接口 |
| 新建草稿 `draft/add` | 可用 | 可用 | 可用 | 无草稿概念 |
| 提交发布 `freepublish/submit` | **已回收（2025.07）** | 可用 | 可用 | **严禁第三方自动发布** |
| 自定义菜单 | 无权限 | 可用 | 可用 | — |
| 数据统计接口 | 无权限 | 可用 | 可用 | 仅商家 / 服务商 |
| 群发频率上限 | 1 次/天 | 1 次/天 | 4 次/月 | 无硬性次数，受风控节奏约束 |
| **多图浏览方式** | 页面内纵向阅读 | 页面内纵向阅读 | 页面内纵向阅读 | **原生左右滑动逐张切换**（须在图片显示区域内滑动；标题栏/评论区滑动无效；老版本 App 需 8.0+） |
| 单篇图片数量上限 | — | — | — | **18 张**（2024 年由 9 张扩容） |
| 图片比例约束 | — | — | — | **整篇只能用一种比例**；首选 3:4（1080×1440），另可选 1:1（1080×1080）/ 4:3（1080×810）；混用会导致**滑动时画面跳动** |
| 单张图片规格 | — | — | — | **≤ 20 MB**；格式 JPG / PNG |
| 超长图处理 | — | — | — | **不得直接上传超长原图**（系统强制缩放→文字模糊），须按 1080×1440 切分为多张顺序上传 |
| 图片顺序 | — | — | — | 可调整（上传后长按拖动排序），**顺序即滑动浏览顺序** |
| 第三方发布合规性 | — | 合规 | 合规 | **违规，判罚不依赖抓工具证据** |
| **本项目交付形态** | 草稿箱投递 | 草稿箱投递（可选正式发布） | 草稿箱投递（可选正式发布） | **素材包 ZIP 导出** |

## 2.5 平台适配器设计

`processor/platformAdapter/` 下以统一抽象基类约定所有平台能力，隔离平台差异：

| 文件 | 类 | 职责 | `deliverMode` |
|---|---|---|---|
| `base.py` | `PlatformAdapter`（抽象基类） | 定义 `render / validate / package / deliver / checkHealth` 统一接口 | — |
| `wechatMp.py` | `WechatMpAdapter` | 内联样式化、图片转存 `mmbiz.qpic.cn`、`draft/add` 投递、（认证号）`freepublish/submit` | `draft_box` / `api_publish` |
| `xiaohongshu.py` | `XiaohongshuAdapter` | 1080×1440 卡片渲染、**左右滑动多图集（切分 + 排序 + 比例统一校验）**、长图拼接与按 1080×1440 切分、**仅打包 ZIP 不投递** | `asset_pack` |
| `generic.py` | `GenericAdapter` | 通用 HTML 输出、站内预览、Markdown/JSON 导出 | `asset_pack` |

> **设计要点**：适配器只做「形态转换 + 通道调用」，业务编排留在 `publishService`；新增平台只需新增一个适配器 + 一条 `ch_platform` 记录，不改主干。

## 2.6 版式类型与交互方式（4 类）

经核实，小红书图文笔记在 App 内**原生支持左右滑动浏览多图**（手指左右轻扫翻页，须在图片显示区域内滑动）。因此 `ch_layout.layoutType` 枚举由 3 类扩为 **4 类**，新增 `swipe`（左右滑动浏览）。

| # | `layoutType` | 中文名 | 交互机制 | 产物形态 | 适用平台 | 本项目职责 |
|---|---|---|---|---|---|---|
| 1 | `stack` | 上下展示 | 纵向顺序阅读 | HTML（公众号）/ 长图（小红书） | 全部 | 渲染 |
| 2 | `carousel` | 左右轮播 | **页面内自实现交互**（公众号须用 SVG 交互，含静态图集兜底） | 单个 HTML | `wechat_mp` / `generic` | 渲染（含交互实现） |
| 3 | `longimage` | 长图拼接 | 多图纵向拼接为 1 张，用户纵向滚动 | 单张长图 PNG | `generic` / `xiaohongshu` | 渲染 |
| 4 | **`swipe`** | **左右滑动多图集** | **平台原生交互**，App 内左右滑动逐张切换 | **N 张 PNG**（`ch_artifact.seqNo` 递增） | **`xiaohongshu`** | **仅切分 + 排序 + 上传**，不自实现交互 |

> **`carousel` 与 `swipe` 的本质区别（务必区分，禁止合并或相互替代）**
>
> | 维度 | `carousel` 左右轮播 | `swipe` 左右滑动 |
> |---|---|---|
> | 交互由谁实现 | **本项目**（HTML / SVG 内自实现） | **平台原生**（小红书 App 内置） |
> | 产物 | 1 个 HTML 文件 | N 张 PNG（`seqNo` 1..N） |
> | 触屏手势可靠性 | 依赖微信对 SVG 的兼容性（不稳，需静态图集兜底） | 平台内置，稳定 |
> | 平台具备性 | 公众号**无**原生轮播，必须自实现 | 小红书**有**原生多图滑动 |
>
> 因此：`carousel_v1` **不可**用于小红书（小红书不接收 HTML）；`swipe_v1` 也**不可**用于公众号（公众号无原生多图滑动能力）。

### 2.6.1 `swipe` 的规格约束（`ch_layout.specJson` 建议值）

```json
{
  "size": "1080x1440",
  "ratio": "3:4",
  "maxCount": 18,
  "minCount": 1,
  "uniformRatio": true,
  "maxSizePerImageMB": 20,
  "format": ["jpg", "png"],
  "sortable": true,
  "coverFlag": true
}
```

### 2.6.2 `swipe` 的编排建议（顺序即滑动浏览顺序）

| 位置 | 作用 |
|---|---|
| 第 1 张 | **封面**（唯一决定点击率） |
| 第 2–3 张 | 承接：说清「解决什么」（结论前置） |
| 第 4–12 张 | 主体：一步一图，图上带编号 |
| 第 13–16 张 | 对比 / 补充 / 参数表 |
| 第 17 张 | 总结清单 |
| 第 18 张 | 收尾（互动引导 / 账号信息） |

> 不足 9 张的轻量内容可压缩为「封面 → 结论 → 主体 3–5 张 → 总结」，**6–9 张密度最佳**；不建议为凑满 18 张硬塞。

### 2.6.3 `swipe` 的强制校验项（归入 C8 合规校验）

| # | 校验项 | 规则 | 违反后果 |
|---|---|---|---|
| 1 | 比例统一 | 整篇同一比例（`uniformRatio`） | 混用比例会导致**滑动时画面跳动**，阅读体验崩坏 |
| 2 | 张数上限 | ≤ 18 张 | 超出无法上传 |
| 3 | 单张大小 | ≤ 20 MB | 超出无法上传 |
| 4 | 格式 | JPG / PNG | 其他格式无法上传 |
| 5 | 超长图拦截 | 高度 > 1440 的整图须先切分 | 直接上传会被强制缩放、文字模糊 |

> **数据来源与置信度**：上述结论由多方第三方资料交叉印证（2026 年小红书配图规范类文章、创作者工具站、用户操作指南），并与产品实际体验一致；**小红书官方后台为登录态、无公开稳定文档**，故上线前须在**小红书创作服务平台实测复核**（列入 7.8 节验收）。

---

# 3. 技术架构与选型建议

## 3.1 分层架构

```text
┌──────────────────────────────────────────────────────────────┐
│ 接入层                                                        │
│  Vue3 Web UI  │  RESTful (Flask /chapi)  │  MCP Server (streamable-http) │
└───────────────────────────┬──────────────────────────────────┘
                            │  三者共用同一套应用服务门面
┌───────────────────────────▼──────────────────────────────────┐
│ 应用服务层（processor/）                                       │
│  topicService │ assetService │ publishService │ complianceService│
│  platformAdapter(微信/小红书/通用) │ mcpapi/（MCP 独立包，C7）    │
└───────────────────────────┬──────────────────────────────────┘
┌───────────────────────────▼──────────────────────────────────┐
│ 引擎层（engine/）                                              │
│  Jinja2 版式引擎 │ 微信内联样式器 │ 卡片截图器(Playwright)      │
│  图片处理器(Pillow：缩放/压缩/EXIF剥离/图注水印)               │
└───────────────────────────┬──────────────────────────────────┘
┌───────────────────────────▼──────────────────────────────────┐
│ 公共层（common/）—— 全部复用 ylwz 既有实现                     │
│  mysqlCommon(生成器产物) │ mysqlHandle(读写连接)               │
│  fileStorageCommon │ aliyunOSS │ tencentCOS │ selfFileCommon   │
│  funcCommon │ miscCommon │ globalDefinition │ redisCommon      │
└───────────────────────────┬──────────────────────────────────┘
┌───────────────────────────▼──────────────────────────────────┐
│ 存储层                                                        │
│  MySQL 8.0 (ch_* 表)  │  ALIOSS / TENCENT / SELFFILE           │
│  Redis (查询缓冲 / 任务锁)                                     │
└──────────────────────────────────────────────────────────────┘
```

## 3.2 与 ylwz 既有体系的关系（复用清单）

| 能力 | 归属 | 复用方式 | 基线实测结论 |
|---|---|---|---|
| 文件落盘/转存/取 URL | ylwz 文件服务（`ylwzRecvFiles.py` + 三适配器） | HTTP 调用（`comFC.fileServerRequest`）或进程内直连适配器 | ✅ 三适配器与 `fileServerRequest` 均存在 |
| 用户登录/角色/权限 | accountService（acis） | HTTP `POST {ACCOUNT_SERVICE_URL}`，CMD=GAA0 / A3A0 | ⚠️ 本项目需新增 `common/accountClient.py` 封装 |
| 数据库读写 | `mysqlCommon.py` | 直接 import，只调 `insert_ch_* / query_ch_* / update_ch_* / delete_ch_*` | ✅ 存在（museum 版 274KB，本项目将新增 12 张 ch 表函数） |
| 数据库连接 | `mysqlHandle.py` | 读写分离连接注入 | ⚠️ **实测差异**：为 `pymysql` **单条长连接**（`dbW`/`dbR`）注入式，**非连接池**；连接由 `config/mysqlSettings.py` 构造后注入 |
| 时间/日志/JSON | `miscCommon.py` | `misc.getTime()` / `misc.setLogNew()` / `misc.jsonLoads()` | ✅ `getTime()` 返回 14 位 `YYYYMMDDHHMMSS`；`setLogNew(title, filebasename, ...)` 返回 `logging.Logger` |
| 摘要/报文/文件请求 | `funcCommon.py` | `comFC.genDigest()` / `comFC.rtnMSG()` / `comFC.fileServerRequest()` | ✅ `genDigest(d1..d5)` 为 **MD5** hexdigest（拼 `_DEF_COMM_HASH_KEY_FOR_ALL`）；`rtnMSG` 返回 `{"MSG":{"errCode","content"},"msgKey"}`；`fileServerRequest(serverName, dataSet)` 走 `settings.FILE_SERVER_URL`，非 200 返回 `{}` |
| 显示/展示隔离 | `funcCommon.py` | `shiftPosition` / `compressList` 等 | ✅ 存在，按需使用 |
| 分页查询缓冲 | Redis list + indexKey | `putQuery2Buffer` / `getQueryBufferComplte` | ⚠️ **实测差异**：这两个函数**不在 `common/redisCommon.py`**，而在 `main/museumAPIPost.py`（连同 `genBufferIndexKey`）。`redisCommon.py` 只提供 `putAllDataBuffer/putDataBuffer/getDataBuffer/putStepBuffer/getStepBuffer/chkBufferExist/getBufferDataLen/delDataBuffer`。**本项目需把这三个 API 层函数移植到 `common/`** |
| 全局常量 | `globalDefinition.py` | 直接 import | ⚠️ **实测差异**：文件服务命令字 `F0A0/F1A0/F2A0/F6A0/F7A0` **未集中定义**，以字面字符串分散在 `museumCommon.py` / `funcCommon.py` / `schedule/dataClean.py` / `processor/*`；`F4A0`/`F8A0` 在基线检索范围内**未验证到定义位置**（v3 文档称 `F4A0` 为 `multiImageMerge` 长图拼接，需 Phase 0 实测确认） |

### 3.2.1 复用收益

复用这一层可省掉「文件服务自研、账号体系自研、分页机制自研」三块工作，保守估计**省 3–4 周**。

### 3.2.2 基线实测差异清单（Phase 0 必须处理）

以下四项为编写本计划前对 `ylwzProject/museum/code/src` 的只读实测发现，与 v3 文档表述存在出入，**必须在 Phase 0 落地前对齐**：

| # | 项 | v3 文档表述 | 实测结果 | 处置建议 |
|---|---|---|---|---|
| D1 | `mysqlHandle` | 「连接池」 | `pymysql` 单条长连接注入式，无池化 | 文档口径修正为「读写分离长连接」；若并发压力大，Phase 3 评估引入连接池（DBUtils / SQLAlchemy pool） |
| D2 | 三适配器 6 方法 | 「完全一致，可直接沿用，无需改造」 | **仅 `tencentCOS.py` 基本一致**；`aliyunOSS.py` 与 `selfFileCommon.py` 签名差异较大（见 3.3.3） | 在 `fileStorageCommon.py` 内增加**参数适配/归一化层**（shim），不修改三适配器源码 |
| D3 | Redis 查询缓冲 | 「`redisCommon.py` 提供 `putQuery2Buffer` / `getQueryBufferComplte`」 | 实为 `main/museumAPIPost.py` 中的 API 层函数 | Phase 0/1 将 `genBufferIndexKey` / `putQuery2Buffer` / `getQueryBufferComplte` 移植到 `common/`（建议放入 `common/chCommon.py`） |
| D4 | 文件服务命令字 | 集中定义，`F4A0` 可复用于长图拼接 | 命令字未集中定义；`F4A0`/`F8A0` 未验证到定义位置 | Phase 0 联调时实测 `F4A0` 能力；若不可用，长图拼接改为 Playwright 自绘（兜底方案已有） |

## 3.3 文件系统抽象设计

本章是架构核心。目标：**同一套代码，改配置即可在 阿里云 OSS / 腾讯云 COS / 自建本地存储 之间切换**。

### 3.3.1 设计目标

1. **配置驱动**：后端选择写在 `config/basicSettings.py` 的 `FILE_SYSTEM_MODE`，按 `_SYS` 环境映射。
2. **接口统一**：所有后端实现同一组 6 个方法，业务层只调抽象方法名。
3. **业务无感**：业务代码不出现厂商分支判断。
4. **落库可追溯**：`ch_asset.fileSystem` 快照记录落库时使用的后端，支持中途切换后端后的历史文件读取。

### 3.3.2 配置层

**`config/local_settings.py` —— 环境选择入口**

```python
_SYS = "local"                 # local | server_01 | server_02 | test_server | home
_SYS_SERVER_NAME = "chserver_01"
```

**`config/basicSettings.py` —— 全局开关**

```python
# 文件系统模式: ALIOSS(阿里云) | TENCENT(腾讯云COS) | SELFFILE(本地文件系统)
FILE_SYSTEM_MODE = {
    "local":       "SELFFILE",
    "server_01":   "ALIOSS",
    "server_02":   "TENCENT",
    "test_server": "SELFFILE",
    "home":        "SELFFILE",
}[_SYS]

# 本地文件服务地址（SELFFILE / 临时文件访问用）
LOCAL_FILE_SERVER_PATH = {...}[_SYS]   # http://host:9000/temp/
LOCAL_FILE_SERVER_BASE = {...}[_SYS]   # /data/webserver/temp/
LOCAL_FILE_TEMP_WEB_DIR = "web/"

# 图片规格（沿用 ylwz 约定）
MAX_PIC_SIZE   = (1920, 1920)   # 正文图最大尺寸
THUMBNAIL_SIZE = (640, 640)     # 缩略图尺寸
ALLOW_FILE_TYPE_LIST = [".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4"]

# 角色裁剪（见 3.3.6 / 第 3.5 节）
ROLE_CMD_LIST = { ... }
NO_SESSIONID_CMD_LIST = ["platformqry", "layoutqry", "artifactqry"]
```

**`config/selfFileSettings.py` —— 本地存储关键项**

```python
SELF_FILE_SERVER_STORAGE_IF_REMOTE = False          # 是否远程存储（scp 同步）
SELF_FILE_SERVER_STORAGE_ADDR      = "127.0.0.1"
SELF_FILE_SERVER_STORAGE_DIR       = "/data/filestorage/"
LOCAL_FILE_STORAGE_DIR_MAX_NUM     = 1000           # 随机分片目录数
LOCAL_FILE_STORAGE_DIR_LEN         = 3              # 3 位零填充 000~999
```

其余四文件：`aliyunSettings.py` / `tencentSettings.py`（各持 AK / bucket / 根目录，按 `_SYS` 映射）、`mysqlSettings.py` / `redisSettings.py`（连接串）、`wechatSettings.py`（公众号 appID / secret / 模板 ID，Phase 0 先留空结构）。

### 3.3.3 统一接口与三后端实测签名对照

**目标统一接口（业务层契约）**

| # | 方法 | 目标签名 | 返回 | 说明 |
|---|---|---|---|---|
| 1 | `uploadFile` | `(localPath, objectName, privateFlag=False)` | fileID | 落盘 / 上传，返回文件标识 |
| 2 | `downloadFile` | `(fileID, targetPath, privateFlag=False)` | localPath（失败 `""`） | 取回本地 |
| 3 | `existFile` | `(fileID, privateFlag=False)` | bool | 存在性检查 |
| 4 | `getFileInfo` | `(fileID, privateFlag=False)` | dict | 元信息（size / objectName / …） |
| 5 | `deleteFile` | `(fileID, privateFlag=False)` | bool | 删除 |
| 6 | `genFileTempUrl` | `(fileID, targetFileName="", privateFlag=False, localAddress=False, sourceServerAddr="")` | url | **fileID → 可访问 URL** |

**三后端实测签名对照（务必按此实现 shim，勿盲信「完全一致」）**

| 目标方法 | `aliyunOSS.py` 实测 | `tencentCOS.py` 实测 | `selfFileCommon.py` 实测 |
|---|---|---|---|
| `uploadFile` | `uploadFile(objName, fileName, downloadName="")` ⚠️ **参数顺序为（对象名, 本地文件），且返回 bool** | `uploadFile(keyName, fileName, privateFlag=False)` ✅ 返回 bool | `uploadFile(fileInfo, privateFlag=False)` ⚠️ **首参为 dict（含 `fileName`），返回生成的 fileID 字符串** |
| `downloadFile` | `downloadFile(objName, fileName)` ⚠️ 无 `privateFlag`，返回 bool | `downloadFile(keyName, fileName, privateFlag=False)` ✅ 返回 bool | `downloadFile(fileID, targetFileName, privateFlag=False, overWriteFlag=True, saveFileCopy=True)` ⚠️ 返回落盘路径字符串 |
| `existFile` | `existFile(objName)` ⚠️ 无 `privateFlag` | `existFile(keyName, privateFlag=False)` ✅ | `existFile(fileID, privateFlag=False)` ✅（要求 `.data` 与 `.info` 同时存在） |
| `getFileInfo` | `getFileInfo(objName)` ⚠️ 返回 `{fileSize, ETag, modifyYMDHMS}` | `getFileInfo(keyName, privateFlag=False)` ⚠️ 返回原始 `list_objects` 结果 | `getFileInfo(fileID, privateFlag=False)` ✅ 返回 `.info` JSON |
| `deleteFile` | `deleteFile(objName)` ⚠️ 无 `privateFlag` | `deleteFile(keyName, privateFlag=False)` ✅ | `deleteFile(fileID, privateFlag=False)` ✅（两者皆删） |
| `genFileTempUrl` | `genFileTempUrl(objName, timeOut=...)` ⚠️ 第二参数为超时 | `genFileTempUrl(keyName, privateFlag=False)` ⚠️ 缺 `targetFileName/localAddress/sourceServerAddr` | `genFileTempUrl(fileID, targetFileName="", privateFlag=False, localAddress=False, overWriteFlag=True, saveFileCopy=True, sourceServerAddr="")` ⚠️ 多两个参数 |

**归一化要求（`fileStorageCommon.py` 职责）**：

1. **参数顺序转换**：`aliyunOSS.uploadFile` 需交换为（本地文件, 对象名）。
2. **参数形态转换**：`selfFileCommon.uploadFile` 需把 `(localPath, objectName)` 组装成 `fileInfo` dict。
3. **返回值归一**：`uploadFile` 统一返回 **fileID 字符串**——OSS/COS 场景 fileID 即调用方传入的 `objectName`（回显）；SELFFILE 场景为适配器生成的 `{分片}/{file+uuid}`。失败统一返回 `""`。
4. **`downloadFile` 归一**：OSS/COS 返回 bool，SELFFILE 返回路径——门面统一返回「落盘路径 or `""`」。
5. **`getFileInfo` 归一**：统一输出键名（见 3.3.5）。
6. **`privateFlag` 兜底**：对无该参数的适配器，由门面层忽略（当前三后端均默认私有桶 / 本地私有目录）。

> **注意**：shim 只做参数映射，**不修改三个适配器源码**，保证与 ylwz 保持同源、可随时同步上游修复。

### 3.3.4 工厂门面 —— `common/fileStorageCommon.py`（新增）

```python
from config import basicSettings as settings
from common import aliyunOSS     as OSS
from common import tencentCOS    as COS
from common import selfFileCommon as SF

def getStorage(mode=""):
    """按 FILE_SYSTEM_MODE 返回对应适配器模块"""
    mode = mode or settings.FILE_SYSTEM_MODE
    return {"ALIOSS": OSS, "TENCENT": COS, "SELFFILE": SF}.get(mode, SF)

# —— 业务层只调下面这组函数 ——
def saveFile(localPath, objectName="", privateFlag=False, mode=""):
    return getStorage(mode).uploadFile(localPath, objectName, privateFlag)

def delFile(fileID, privateFlag=False, mode=""):
    return getStorage(mode).deleteFile(fileID, privateFlag)

def saveWithThumbnail(localPath, objectName="", privateFlag=False, mode=""):
    """先出缩略图再存主图，返回 (fileID, thumbnailID)"""
    storage   = getStorage(mode)
    thumbPath = buildThumbnail(localPath)          # Pillow: thumbnail(THUMBNAIL_SIZE)
    thumbID   = storage.uploadFile(thumbPath, objectName + "_thumb", privateFlag)
    fileID    = storage.uploadFile(localPath, objectName, privateFlag)
    return fileID, thumbID

def getTempLocation(fileID, privateFlag=True, localAccess=False,
                    localAddress=False, targetFileName="", sourceServerAddr=""):
    """把 fileID 转成可访问 URL；fileID 已是 http 开头则原样返回"""
    if not fileID or fileID[:4] == "http":
        return fileID
    return getStorage().genFileTempUrl(
        fileID, targetFileName=targetFileName, privateFlag=privateFlag,
        localAddress=localAddress, sourceServerAddr=sourceServerAddr)
```

### 3.3.5 fileID 语义（按后端正交定义）

| 后端 | fileID 形态 | 示例 | 说明 |
|---|---|---|---|
| **ALIOSS** | 对象键 objectName | `pic_20260917093001_a1b2c3.jpg` | 桶内唯一键 |
| **TENCENT** | 对象键 objectName | `pic_20260917093001_a1b2c3.jpg` | 同上 |
| **SELFFILE** | `{3位分片}/{file+uuid}` | `037/file4f2a9c8e…` | 相对 `SELF_FILE_SERVER_STORAGE_DIR` 的路径 |

**SELFFILE 双文件机制（沿用 ylwz 设计，已实测确认）**

```text
/data/filestorage/037/file4f2a9c8e…  .data   <-- 二进制内容
                                     .info   <-- JSON 元信息
```

```json
{
  "serverName": "chserver_01",   "fileSystem": "SELFFILE",
  "description": "pic",          "fileName": "/data/webserver/temp/2/0000000322",
  "oldFileName": "cover.jpg",    "objectName": "cover.jpg",
  "fileExtName": ".jpg",         "fileSize": 299208,
  "fileUrl": "037/file4f2a9c8e…","uploadYMDHMS": "20260917093001",
  "prefix": "",                  "compressFlag": "N"
}
```

- **fileID 生成规则**：`{subDirNum补零3位}/file{uuid32去连字符}`，`subDirNum = random.randint(0, LOCAL_FILE_STORAGE_DIR_MAX_NUM-1)`。
- **`existFile` 语义**：`.data` 与 `.info` **同时存在**才视为存在。
- **`deleteFile` 语义**：两者一并删除。

### 3.3.6 两种接入模式

| 模式 | 适用 | 做法 | 优点 | 缺点 |
|---|---|---|---|---|
| **A. HTTP 文件服务**（默认） | Web 应用同步请求 | `comFC.fileServerRequest(serverName, {CMD:"F7A0", fileID, token})` | 应用不持有 AK；Token 鉴权；权限收敛 | 多一跳网络 |
| **B. 进程内直连** | 批处理 / 渲染 worker | 直接 import `fileStorageCommon` 调适配器 | 低延迟、适合批量 | 每个进程需配 AK |

> **推荐组合**：Web 请求走 A；渲染 / 打包 worker 走 B。两者最终落到**同一份配置**，fileID 语义一致，可互认。

### 3.3.7 文件服务命令（复用 ylwz 协议）

| CMD | 作用 | 本项目用法 | 基线核实 |
|---|---|---|---|
| `F0A0` | 临时 → 永久存储（可带缩略图 / 压缩） | 素材转存 | ✅ 使用于 `museumCommon.py:626`、`funcCommon.py:1238` |
| `F1A0` | 删除临时文件 | 上传后清理 | ✅ `schedule/dataClean.py:621` |
| `F2A0` | 删除长期文件 | 产物过期清理 | ✅ `schedule/dataClean.py:160`、`museumCommon.py:678` |
| `F4A0` | 合并多图为一张长图 | 小红书长图拼接（**待实测确认**） | ⚠️ **未验证到定义位置** |
| `F6A0` | 获取文件信息 | 校验 / 展示 | ✅ `museumCommon.py:739` |
| `F7A0` | 永久 → 本地临时目录并生成 URL | 渲染取图、预览 | ✅ `museumCommon.py:702`、`funcCommon.py:1277` |
| `F8A0` | 获取永久文件信息 | 产物核对 | ⚠️ **未验证到定义位置** |
| `/hfile` | multipart 直传 | 前端上传入口 | ⚠️ 需在 T7 联调时确认 |

> **兜底方案**：若 `F4A0` 不可用，小红书长图拼接改为 Playwright 整页截图 / Pillow 纵向拼接自绘，不阻塞主干。

### 3.3.8 fileID → URL 的转换责任（约定）

> **约定（P0）**：数据库只存 `fileID`（`VARCHAR(200)`），**URL 由后端在出参时转换**。前端永远拿不到、也不需要知道 `fileID`。

```python
def fillFileUrls(aSet, fileFields=["coverFileID", "thumbnailID", "fileID"]):
    for f in fileFields:
        fid = aSet.get(f, "")
        if fid:
            aSet[f.replace("FileID", "Url")] = getTempLocation(fid, privateFlag=True)
    return aSet
```

## 3.4 数据库设计

### 3.4.1 设计原则

| 原则 | 说明 |
|---|---|
| MySQL 8.0 / InnoDB / utf8mb4 | 引擎与字符集固定，排序规则 `utf8mb4_unicode_ci` |
| **定义文件是唯一数据源** | 12 张表各一个 `code/src/database/ch_*.txt`。改结构只改 txt → 重跑生成器 |
| **读写全走生成代码** | 业务层只调 `comMysql.insert_ch_*()` 等，禁止裸 SQL |
| 统一 `recID` 自增主键 | 首字段一律 `recID BIGINT AUTO_INCREMENT PRIMARY KEY`；业务唯一性由唯一索引承担 |
| 拼接唯一键即幂等 | 生成器不支持复合唯一键 → 应用层拼接单列 + 内联 `UNIQUE` |
| 无外键 | 全部移除 `FOREIGN KEY`，改应用层完整性 + 索引 |
| 时间列 `VARCHAR(16)` | 存 `YYYYMMDDHHMMSS`，不用 `DATETIME`（避免时区歧义，可直接字符串比较） |
| 固定尾部七字段 | `label / memo / regID / regYMDHMS / modifyID / modifyYMDHMS / delFlag`，顺序不可变 |
| 文件字段统一 | 文件引用 `fileID VARCHAR(200)`；缩略图 `thumbnailID VARCHAR(200)`；去重 `contentHash CHAR(64) UNIQUE` |

### 3.4.2 命名规范

- **定义文件**：`ch_` 前缀 + 小写下划线单数，如 `ch_topic.txt`
- **表名**：与文件名同名，全小写
- **业务标识列**：驼峰，如 `topicCode`、`assetKey`、`idempotencyKey`
- **布尔 / 标记**：`CHAR(1)`（`'0'`/`'1'`）
- **状态**：`VARCHAR(24)` + `COMMENT` 枚举（不用 `ENUM`）
- **小整数**：`SMALLINT` / `TINYINT`

### 3.4.3 表清单总览（12 张）

| # | 定义文件 | 表名 | 用途 | 幂等唯一键（拼接列） | 归档 | 量级 |
|---|---|---|---|---|---|---|
| 1 | `ch_topic.txt` | `ch_topic` | **主题主表** | `topicCode`（UNIQUE） | 否 | 十万级 |
| 2 | `ch_topic_asset.txt` | `ch_topic_asset` | 主题-附图关联（含说明） | `assetKey` = `topicID:fileID` | 否 | 百万级 |
| 3 | `ch_asset.txt` | `ch_asset` | **素材资源** | `fileID`、`contentHash`（各 UNIQUE） | 否 | 百万级 |
| 4 | `ch_layout.txt` | `ch_layout` | 版式模板定义 | `layoutCode`（UNIQUE） | 否 | 百级 |
| 5 | `ch_platform.txt` | `ch_platform` | **平台能力矩阵** | `platformCode`（UNIQUE） | 否 | 十级 |
| 6 | `ch_render_job.txt` | `ch_render_job` | 渲染任务 | `jobCode`（UNIQUE） | 否 | 十万级 |
| 7 | `ch_artifact.txt` | `ch_artifact` | **渲染产物** | `artifactKey` = `jobID:kind:platform:seqNo` | 否 | 百万级 |
| 8 | `ch_account.txt` | `ch_account` | **平台账号（含加密凭据）** | `accountCode`（UNIQUE） | 否 | 百级 |
| 9 | `ch_publish_record.txt` | `ch_publish_record` | 发布记录 | `idempotencyKey`（UNIQUE） | 否 | 十万级 |
| 10 | `ch_mcp_token.txt` | `ch_mcp_token` | MCP 访问令牌（**本期不参与鉴权**，保留建表以备后续独立吊销能力） | `tokenHash`（UNIQUE） | 否 | 百级 |
| 11 | `ch_audit_log.txt` | `ch_audit_log` | **审计日志** | —（追加写） | **是** | 千万级 |
| 12 | `ch_topic_version.txt` | `ch_topic_version` | 主题版本快照（P2） | `verKey` = `topicID:versionNo` | 否 | 十万级 |

> **字段级全文**（12 张表的每个字段、类型、约束、COMMENT）见 `plan/content-hub-Phase0-任务清单.md` 第 T4 节，可直接落盘为 `code/src/database/ch_*.txt`，本计划不重复罗列。

### 3.4.4 定义文件写法红线

1. 每行一个字段：`字段名 类型 [约束] COMMENT '说明'`。
2. **字段行内严格单空格分隔，禁用 Tab**（否则解析错位、字段丢失）。
3. `COMMENT` 内**不得出现 `%`**（生成器会替换为全角），用「百分比」或「pct」。
4. 首字段必须为 `recID BIGINT AUTO_INCREMENT PRIMARY KEY`。
5. 尾部固定七字段顺序不可变：`label / memo / regID / regYMDHMS / modifyID / modifyYMDHMS / delFlag`。
6. 规避 MySQL 保留字；生成器内置保留字表会自动加反引号，但仍建议主动规避（如 `status` → `jobStatus`）。

### 3.4.5 幂等写入约定

生成器不支持 `ON DUPLICATE KEY`，统一走「查唯一键 → 命中更新 / 未命中插入」：

```python
def upsertByUniqueKey(uniqueValue, saveSet, queryFn, insertFn, updateFn, tableName):
    """按唯一键幂等写入"""
    dataList = queryFn(tableName, uniqueValue)
    if len(dataList) == 1:
        recID = dataList[0].get("recID")
        updateFn(tableName, recID, saveSet)
        return recID
    return insertFn(tableName, saveSet)
```

| 表 | 唯一键 | 拼接规则 |
|---|---|---|
| `ch_topic_asset` | `assetKey` | `{topicID}:{fileID}` |
| `ch_artifact` | `artifactKey` | `{jobID}:{kind}:{platform}:{seqNo}` |
| `ch_topic_version` | `verKey` | `{topicID}:{versionNo}` |
| `ch_asset` | `contentHash` | `sha256(原始字节).hexdigest()` |
| `ch_publish_record` | `idempotencyKey` | 调用方传入（推荐 `{artifactID}:{accountID}:{uuid4}`） |
| `ch_mcp_token` | `tokenHash` | `sha256(token).hexdigest()` |

### 3.4.6 归档策略

`ch_audit_log` 是唯一大表，**不用分区**（生成器不支持），改：

1. `regYMDHMS` 单列索引；
2. 每月分批 `DELETE ... WHERE regYMDHMS < '20250101000000' LIMIT 5000`（循环执行，避免长事务）；
3. 保留 24 个月，归档前导出到对象存储。

### 3.4.7 种子数据

| 表 | 种子内容 |
|---|---|
| `ch_platform` | `wechat_mp`（`deliverMode=draft_box`、`allowSvg=0`、`needAiLabel=0`、`coverSpec=900x500`、`imageSpec=1080x1440`）、`xiaohongshu`（`deliverMode=asset_pack`、`imageSpec=1080x1440`、**`imageMaxCount=18`**、`needAiLabel=1`、`autoPublish=0`）、`generic`（`deliverMode=asset_pack`） |
| `ch_layout` | `stack_v1`（上下展示）、`carousel_v1`（左右轮播）、`longimage_v1`（长图拼接）、**`swipe_v1`（左右滑动多图集：`layoutType=swipe`、`platform=xiaohongshu`、`outputKind=png`、`specJson` 见 2.6.1）**，各平台各一套 |
| `ch_account` | 手工录入，不预置 |

> 种子走生成器产出的 `insert_ch_platform()` / `insert_ch_layout()`，**不维护第二份 SQL**。

## 3.5 CRUD 生成方案

### 3.5.1 生成器工作流

```text
ch_topic.txt (唯一数据源)
      │
      ▼  python mysqlCodeGenerator.py -i database/ch_topic.txt -t topic
mysqlCodeGenerator.readFromFile()
      │  anaTableData() 解析每行 → {fieldName, dataType, dataTypeString, rest, isPrimaryKey, text}
      ▼
generateFuncs() 产出 5 段代码
      ├─ tablename_convertor_ch_topic()      表名转换
      ├─ create_ch_topic(tableName)          建表（内联 DDL）
      ├─ drop_ / delete_ / insert_ / update_ / query_ch_topic()
      ├─ functopicAdd / functopicDel / functopicModify / functopicQry   ← REST 处理器
      ├─ test_ch_topic()                     自测用例
      └─ msg = '{...}'                       接口测试报文
      ▼
auto_generated/auto_gen_code_ch_topic.py   （产物，不手改）
      +
auto_generated/word_table_ch_topic.csv     （接口参数文档，TAB 分隔）
      │
      ▼  人工合并
common/mysqlCommon.py                      （全库读写唯一入口）
```

### 3.5.2 命令行与产物命名（已实测核实）

| 项 | 实测值 |
|---|---|
| `-i, --input` | 输入定义文件路径（默认 `database/stock_technical_indicators.txt`） |
| `-t, --title` | REST 处理器名中段，首字母自动大写（`cmdTitle = value[0].upper() + value[1:]`） |
| `-d, --debug` | 无参开关，进入 `pdb` / `breakpoint()` |
| `-h, --help` | 打印帮助并退出 |
| 代码产物 | `auto_generated/auto_gen_code_<tableName>.py` |
| 文档产物 | `auto_generated/word_table_<tableName>.csv`（**TAB 分隔，4 列**：参数 / 是否必须 / 数据类型 / 说明；首行表头，固定追加 `position`、`lang`、`YMDHMS` 三行） |
| 表名来源 | `readFromFile` 取文件名去扩展名（可用 `tableName = "xxx"` 行覆盖） |

**批量生成命令**

```bash
cd code/src
for f in database/ch_*.txt; do
  t=$(basename "$f" .txt | sed 's/^ch_//')   # topic, topic_asset, asset, layout, ...
  python database/mysqlCodeGenerator.py -i "$f" -t "$t"
done
```

### 3.5.3 生成器硬约束（红线）

| # | 约束 | 违反后果 | 规避 |
|---|---|---|---|
| 1 | 首字段必须是 `AUTO_INCREMENT` 主键 | `insert_*` 签名会多一个主键参数 | 一律 `recID BIGINT AUTO_INCREMENT PRIMARY KEY` |
| 2 | **不支持复合唯一键** `UNIQUE KEY (a,b)` | 生成器不产索引 | 应用层拼接单列 + 内联 `UNIQUE` |
| 3 | **不支持外键** | — | 移除 `FOREIGN KEY`，应用层保证 |
| 4 | **不支持分区** | — | `regYMDHMS` 索引 + 分批 DELETE |
| 5 | 字段行内**单空格**分隔 | 解析错位、字段丢失 | 严格单空格，禁用 Tab |
| 6 | `COMMENT` 中**不能有 `%`** | 生成器替换为全角 ％ | 用「百分比」或「pct」 |
| 7 | 字段名 / 表名不能是 MySQL 保留字 | 需反引号，易踩坑 | 主动规避；生成器内置保留字表自动加反引号 |
| 8 | `PRIMARY KEY` 关键字需完整匹配 | 字段名含 `primary`（如 `primaryImageUrl`）会被误判为主键 | v20260904 版已修复，确保使用新版生成器 |

### 3.5.4 已知坑（三坑，均已实测核实）

> **坑 1：`handleSQL()` 路径存在参数错位（已核实成立）**
>
> ```python
> def coderGenerator(tableName, fieldsList, cmdTitle="cmd", primaryKeys=[], insertsList=[]): ...
>
> # handleSQL() 内（第 2450 行，错位）
> coderGenerator(tableName, fieldsList, primaryKeys, insertsList)
> #   → primaryKeys 落到 cmdTitle，insertsList 落到 primaryKeys，第 5 参未传
>
> # readFromFile() 内（第 2544 行，正确）
> coderGenerator(tableName, fieldsList, cmdTitle)
> ```
>
> **影响**：从原生 `CREATE TABLE` SQL 生成代码会产出非法函数名、建表丢主键、INSERT 段为空。
> **规避**：只走 `readFromFile()` 路径（`-i ch_*.txt`），不使用 `handleSQL()` / `mysqlStatementHandle()`。

> **坑 2：`query_*()` 的 LIMIT 分支被注释掉（已核实成立）**
>
> 生成器源码第 461-465 行把 LIMIT 拼装整段注释：
> ```python
> tempString = TS2 + '#if limitNum > 0:'
> tempString = TS3 + '#sqlStr += " LIMIT {0}".format(limitNum)'
> ```
> 产物中 `limitNum` 形参存在但从不生效；REST 层同样注释掉了 `limitNum = dataSet.get(...)`、`indexKeyDataSet["limitNum"]`、`rtnData["limitNum"]`。
> **影响**：`ch_audit_log` 千万级时会拉全表。
> **规避**：合并进 `mysqlCommon.py` 后**手工补回 LIMIT**（建议 `LIMIT 5000` + 游标分页），REST 层显式接收并下传 `limitNum`。

> **坑 3：生成代码对 INT 类型强制 `int()`，异常置 0（已核实成立）**
>
> 生成器第 615-625 行：
> ```python
> try:
>     sortWeight = int(dataSet.get("sortWeight"))
> except:
>     sortWeight = 0
> saveSet["sortWeight"] = sortWeight
> ```
> （FLOAT 分支同理 `float(...)` / except `0`）
> **影响**：可空 INT 列（`ch_asset.width/height`、`ch_artifact.sizeBytes`、`ch_render_job.costMs` 等）丢失 NULL 语义。
> **规避**：可空数值列在业务层约定「**0 = 未设置**」；若确需区分，改用哨兵值 `-1` 并在文档标注。

> **坑 4（附带发现）：`genRecordAddCode` 存在未定义变量**
>
> 仅当 `insertsList` 非空（`handleSQL` 路径）时触发：第 2273 行使用未定义的 `valuesList` 且括号多余。本项目不使用该路径，**不受影响**；但若未来需要「从 SQL 导入历史数据」，需先修复此函数。

### 3.5.5 业务层调用约定

**唯一入口**：`common/mysqlCommon.py`

```python
from common import mysqlCommon as comMysql

tableName    = comMysql.tablename_convertor_ch_topic()
currDataList = comMysql.query_ch_topic(tableName, recID)            # 查
recID        = comMysql.insert_ch_topic(tableName, saveSet)         # 增
rtn          = comMysql.update_ch_topic(tableName, recID, saveSet)  # 改
rtn          = comMysql.delete_ch_topic(tableName, recID)           # 删
```

### 3.5.6 REST 端点映射（48 个 = 12 表 × 4 组）

| 表 | add | del | modify | qry |
|---|---|---|---|---|
| `ch_topic` | `topicadd` | `topicdel` | `topicmodify` | `topicqry` |
| `ch_topic_asset` | `topicassetadd` | `topicassetdel` | `topicassetmodify` | `topicassetqry` |
| `ch_asset` | `assetadd` | `assetdel` | `assetmodify` | `assetqry` |
| `ch_layout` | `layoutadd` | `layoutdel` | `layoutmodify` | `layoutqry` |
| `ch_platform` | `platformadd` | `platformdel` | `platformmodify` | `platformqry` |
| `ch_render_job` | `renderjobadd` | `renderjobdel` | `renderjobmodify` | `renderjobqry` |
| `ch_artifact` | `artifactadd` | `artifactdel` | `artifactmodify` | `artifactqry` |
| `ch_account` | `accountadd` | `accountdel` | `accountmodify` | `accountqry` |
| `ch_publish_record` | `publishrecordadd` | `publishrecorddel` | `publishrecordmodify` | `publishrecordqry` |
| `ch_mcp_token` | `mcptokenadd` | `mcptokendel` | `mcptokenmodify` | `mcptokenqry` |
| `ch_audit_log` | `auditlogadd` | `auditlogdel` | `auditlogmodify` | `auditlogqry` |
| `ch_topic_version` | `topicversionadd` | `topicversiondel` | `topicversionmodify` | `topicversionqry` |

**角色裁剪（`config/basicSettings.py` 的 `ROLE_CMD_LIST`）**

| 角色 | 权限 |
|---|---|
| `administrator` / `manager` | 全部 48 个端点 |
| `operator` | 主题 / 素材 / 渲染 / 产物 / 发布 全权限；账号（**★ 含 `accountadd`/`accountmodify`/`accountdel`，2026-09-23 起**）/ 令牌 / MCP 只读 |
| `customer` | 全部只读（`*qry`）＋**★ 账号域 `accountqry`/`accountadd`/`accountmodify`/`accountdel`/`accounthealth`（2026-09-23 起）** |
| `visitor` | 仅 `ch_platform` / `ch_layout` / `ch_artifact` 只读（**★ 不含任何账号域端点**） |

> ★ **2026-09-23 变更登记（「第三方账号管理」/ P-14 `/my-accounts`）**：为支持非访客角色「各管本人平台账号」，
> `ROLE_CMD_LIST` 对 `operator` 追加 `accountadd`/`accountmodify`/`accountdel`，对 `customer` 追加
> `accountqry`/`accountadd`/`accountmodify`/`accountdel`/`accounthealth`；**`visitor` 不追加**。
> 授权面放宽**不构成越权**：`ch_account` 的归属隔离在处理器层强制（`comFC.chkIsManager` 之外的登录用户
> 一律 `ownerID = loginID`，见 `subfunc/crudApi.py` / `subfunc/accountApi.py`），且凭据巡检同样按归属收窄
> （`schedule/credentialCheck.py::fetchAccountList` 的 `ownerID` 为可选条件；定时任务不传 → 全量语义不变）。
> 本改造**不新增 CMD**（端点总数仍 72），`subfunc/__init__.py::mergeCmdMaps` 的 V3 完整性校验不受影响。
> 前端侧登记见 `plan/前端开发计划.md` 附录 B **R-35**、附录 G **v1.10**；`ownerID` 索引为 DDL 待办（**R-34**）。

`NO_SESSIONID_CMD_LIST = ["platformqry", "layoutqry", "artifactqry"]`（免登录可读的公开配置类查询）。

**业务专用端点（不走生成器，手工实现）**

| 端点 | 作用 |
|---|---|
| `topicrender` | 触发渲染（建 job + 异步执行） |
| `artifactpack` | 打包素材包 ZIP |
| `publishpush` | 推送公众号草稿 |
| `publishcheck` | 合规与规格校验（不落库，返回问题清单） |
| `accounthealth` | 凭据健康检查 |
| `mcpinvoke` | `/chapi` 侧的 MCP tool 薄入口（**MCP 协议与工具实现已独立为 `code/src/mcpapi/` 包**，本端点仅作 REST 转发） |

## 3.6 技术选型汇总

| 层次 | 选型 | 理由 / 备选 |
|---|---|---|
| 语言 / 运行时 | **Python 3.13**（managed） | 与基线 ylwz 一致；语法/性能收益 |
| Web 框架 | **Flask（`/chapi`）** | **与 v3 权威口径一致**，对齐 ylwz 的 `main/*API.py` + `urlPathMap` 路由分发模式。备选：FastAPI（调研文档建议，选型更现代但会引入第二套工程范式，本期不采用） |
| 路由分发 | `main/chAPI.py` + `main/chAPIPost.py`（`urlPathMap`） | 对齐基线；48 个生成端点 + 6 个业务端点统一挂载 |
| 前端 | **Vue 3 + Vite + Pinia + Tailwind CSS + Element Plus** | 组件库与工程基线 `museum/webserver` 同源（**已裁定 2026-09-18**，零迁移成本）；Token 经 `--el-*` 变量注入。UI 规范见 `plan/UI/contentHub UI 设计.md` |
| 模板引擎 | **Jinja2** | 模板可版本化、可热更新；与 `ch_layout.engine` 字段对应 |
| 版式描述 | **Layout JSON DSL**（存 `ch_layout.specJson`） | 描述「区块 + 版式」，与渲染目标解耦 |
| 图片截图 | **Playwright（Chromium）** | HTML → 1080×1440 卡片、长图拼接。⚠️ 必须做字体预加载与 `waitForFonts`，否则中文丢字 |
| 图片处理 | **Pillow** | 缩放 / 压缩 / EXIF 剥离 / 缩略图 / 水印 |
| 任务调度 | **自研 `schedule/renderWorker.py`**（轮询队列）+ Redis 任务锁 | 对齐 v3 目录结构，无额外中间件。备选：Celery + Redis（若并发量上升再引入） |
| 数据库 | **MySQL 8.0 / InnoDB / utf8mb4** | 沿用 ylwz 定义文件 + 生成器链路 |
| 缓存 | **Redis** | 查询缓冲（indexKey 分页）+ 任务锁 + 频率限流计数 |
| 对象存储 | **ALIOSS / TENCENT / SELFFILE 三态可切** | 配置驱动，见 3.3 |
| 凭据加密 | **AES-256-GCM + 独立密钥管理** | `credentialCipher` + `credentialIV` 字段已就位；密钥走环境变量 / KMS，**不入库不入代码库** |
| 开放协议 | **MCP Server，streamable-http**（FastMCP + `streamable_http_app()` + uvicorn） | 已拍板：与参考实现 `stock_rotation_strategy/src/mcpapi` 完全一致；后续如需 SSE 由 `mcpConfig.MCP_TRANSPORT` 单点切换 |
| 日志 | `miscCommon.setLogNew()` | 对齐基线，输出到 `code/log/` |

## 3.7 目录结构

```text
contenthub/
├── plan/                                    # 设计文档
│   ├── contentHub开发计划.md                  # 【本文件】
│   ├── content-hub-开发计划v3.html            # 原始设计底稿（只读溯源）
│   ├── content-hub-调研与开发计划.html         # 原始调研底稿（只读溯源）
│   ├── content-hub-Phase0-任务清单.md          # Phase 0 可执行工单
│   ├── ylwz文件服务多Bucket.md                # 支线 S1 方案
│   ├── chAPIPost分拆方案.md                   # 支线 S2 方案
│   ├── UI/                                    # ★ UI 规范（前端唯一设计依据）
│   │   ├── contentHub UI 设计.md
│   │   └── contentHub UI 设计规范.pdf
│   └── platforms.json                        # 平台能力矩阵配置（种子来源）
└── code/
    ├── webserver/                            # ★ 前端工程（Vue3 + Element Plus + Tailwind，对齐 museum/webserver）
    └── src/
        ├── common/                          # 公共层（大部分复用 ylwz）
        │   ├── mysqlCommon.py               # ★ 全库读写唯一入口（生成器产物）
        │   ├── mysqlHandle.py               # 读写分离长连接 executeRead / executeWrite
        │   ├── fileStorageCommon.py         # ★ 新增：文件存储统一门面（含三后端 shim）
        │   ├── aliyunOSS.py                 # 【复用】阿里云适配器
        │   ├── tencentCOS.py                # 【复用】腾讯云适配器
        │   ├── selfFileCommon.py            # 【复用】本地文件适配器
        │   ├── funcCommon.py                # 【复用】genDigest / rtnMSG / fileServerRequest
        │   ├── miscCommon.py                # 【复用】getTime / setLogNew / jsonLoads
        │   ├── globalDefinition.py          # 【复用】全局常量
        │   ├── redisCommon.py               # 【复用】查询缓冲（+ 移植 3 个 API 层缓冲函数）
        │   ├── chCommon.py                  # ★ 新增：本项目公共封装（对齐 museumCommon）
        │   ├── chServerCommon.py            # ★ 新增：contentHub REST 客户端（对齐 ylwzStockCommon）
        │   └── accountClient.py             # ★ 新增：账号服务客户端
        ├── config/
        │   ├── local_settings.py            # _SYS 环境选择入口
        │   ├── basicSettings.py             # FILE_SYSTEM_MODE / ROLE_CMD_LIST / 规格
        │   ├── aliyunSettings.py            # OSS 桶与 AK
        │   ├── tencentSettings.py           # COS 桶与 AK
        │   ├── selfFileSettings.py          # 本地存储目录与分片
        │   ├── mysqlSettings.py             # DB 连接（构造 dbW/dbR 注入 mysqlHandle）
        │   ├── redisSettings.py             # Redis 连接
        │   ├── wechatSettings.py            # ★ 公众号 appID/secret/模板ID
        │   └── mcpConfig.py                 # ★ 新增：MCP 服务名/端口/传输/下游地址
        ├── database/                        # ★ 表定义目录（唯一数据源）
        │   ├── ch_topic.txt                 #   ...（共 12 个 ch_*.txt）
        │   ├── mysqlCodeGenerator.py        # 【不动】代码生成器
        │   └── auto_generated/              # 生成器产物落点（auto_gen_code_*.py / word_table_*.csv）
        ├── engine/                          # ★ 渲染引擎
        │   ├── layoutEngine.py              # 版式调度
        │   ├── inlineStyle.py               # 微信内联样式器
        │   ├── htmlToImage.py               # Playwright 截图
        │   ├── imageProc.py                 # Pillow 处理
        │   └── templates/                   # Jinja2 模板
        │       ├── stack_v1/
        │       ├── carousel_v1/
        │       ├── longimage_v1/
        │       └── swipe_v1/                # ★ 左右滑动多图集（小红书，仅切分+排序）
        ├── processor/                       # 业务处理器
        │   ├── topicService.py              # C2
        │   ├── assetService.py              # C3
        │   ├── publishService.py            # C6
        │   ├── complianceService.py         # C8
        │   └── platformAdapter/             # C5
        │       ├── base.py                  # PlatformAdapter 抽象基类
        │       ├── wechatMp.py
        │       ├── xiaohongshu.py
        │       └── generic.py
        ├── schedule/                        # cron 调度
        │   ├── renderWorker.py              # 渲染队列消费者
        │   ├── credentialCheck.py           # 凭据健康巡检
        │   └── archive.py                   # ch_audit_log 归档
        ├── monitor/                         # 监控告警
        ├── tools/                           # 运维脚本
        │   ├── initSeed.py                  # 灌种子（platform / layout）
        │   ├── initTables.py                # 建表（调 create_ch_*）
        │   └── test_storage.py              # 三后端联调脚本
        ├── test/
        ├── main/                            # 进程入口
        │   ├── chAPI.py                     # Flask 主入口（/chapi）
        │   ├── chAPIPost.py                 # urlPathMap 路由分发
        │   └── subfunc/                     # 拆分子模块（见支线 S2）
        └── mcpapi/                          # ★ 新增：MCP 服务独立包（见 9.6 节）
            ├── __init__.py                  # 包声明
            ├── mcp_entry.py                 # 入口层：FastMCP + 鉴权 + 8 tool + 3 resource
            ├── mcpPost.py                   # 实现层：toolPathMap 分发 + 8 个只读处理函数
            └── restore_mcp.sh               # 重启脚本
```

---

# 4. 开发阶段与里程碑划分

## 4.1 总体节奏与排期原则

| 原则 | 说明 |
|---|---|
| **双线并行** | A 线（内容与渲染主干，技术自控）+ B 线（平台资质与凭据，外部依赖）。B 线 Day 1 启动，**不阻塞 A 线** |
| **主干优先** | C1 → C2 → C3 → C4 → C5 → C6 顺序推进；C8 横切两条入口 |
| **渲染后置 MCP** | C7 必须等 C4 / C6 稳定后再做，否则接口随渲染引擎返工 |
| **形态兜底** | 即使资质未过审，Phase 1–2 依然完整交付「素材包导出」形态——**资质是加速项，不是阻塞项** |
| **阶段出口可验收** | 每个 Phase 以一个可演示里程碑收口，未达标不进入下一阶段 |

```text
周次:  1  2 | 3  4  5  6 | 7  8  9 | 10 11 12
Phase: 0    | 1            | 2        | 3
里程碑: M0  | M1           | M2       | M3 / v1.0
B线:   企业号认证申请 ─────────────────────► 草稿投递可用
```

## 4.2 Phase 0 · 地基（第 1–2 周）→ 里程碑 M0

**目标**：12 张 `ch_*` 表定义文件 + 生成器跑通 + 文件存储抽象层冻结。

**内容**：

1. **Day 1 并行启动企业号认证**（外部审核 2–4 周，非阻塞主干）。
2. 目录骨架 + `config/` 七文件。
3. 12 个 `ch_*.txt` 定义文件 + 生成器批量跑通 → 合并 `mysqlCommon.py` → 建表验证。
4. `fileStorageCommon.py` 门面 + 三后端（含 shim）联调。
5. `plan.md`（目录骨架 / 模块边界 / 接口约定 / 配置项清单 / MCP 协议选型结论）。
6. 处理 3.2.2 节列出的 **D1–D4 基线差异**。

**出口标准**：`plan/content-hub-Phase0-任务清单.md` 第 T9 节「Phase 0 验收总表」8 项全过（详见 7.6 节）。

**关键风险**：`F4A0` 长图拼接能力未验证 → 兜底方案（Playwright / Pillow 自绘）须在本阶段给出结论。

## 4.3 Phase 1 · 主题与素材（第 3–6 周）→ 里程碑 M1

**目标**：主题可建、素材可传、版式可预览。

**内容**：C1 接入权限 → C2 主题管理（含字段区间校验）→ C3 素材图库（三后端切换 + `contentHash` 去重）→ C4 版式引擎（**先硬编码 4 套模板**）。

**出口标准（M1）**：

1. 主题资产可完整录入（全字段 + 多图附件带说明）。
2. 图片可上传并自动出缩略图 / 规格图，重复图片被 `contentHash` 拦截。
3. 4 套版式（上下 / 轮播 / 长图 / **左右滑动多图集**）可在浏览器中预览渲染结果。
4. 权限裁剪生效：4 类角色看到不同可用端点集合。

## 4.4 Phase 2 · 渲染与产物（第 7–9 周）→ 里程碑 M2

**目标**：可渲染出双平台合规产物。

**内容**：C5 平台适配（微信内联化 + 小红书图集卡片）→ C8 合规校验 → `ch_artifact` 产物管理。

**出口标准（M2）**：

1. 同一主题可产出微信公众号内联样式 HTML（真机预览无错乱）。
2. 同一主题可产出小红书 **左右滑动多图集**（`swipe_v1`：N 张 1080×1440 PNG，比例统一、顺序可编排）、图集 PNG 与长图。
3. 平台规格校验前置生效（标题/摘要/图片尺寸/数量上限）。
4. 合规校验返回问题清单，未经校验不得进入投递环节。

## 4.5 Phase 3 · 投递与开放（第 10–12 周）→ 里程碑 M3 / v1.0

**目标**：可投递 + AI 可编排，交付 v1.0。

**内容**：C6 发布投递（公众号推草稿 + 素材包 ZIP）→ C7 MCP Hub（8 tool + Token + 审计）→ 归档 + 监控。

**出口标准（M3 / v1.0）**：

1. 主题 → 公众号草稿箱真实落地（认证号可追加正式发布）。
2. 主题 → 小红书素材包 ZIP 一键导出。
3. MCP Server（streamable-http）可用，8 个只读 tool 与 3 个 resource 可被 Agent 调用，鉴权走 Redis session + `ROLE_CMD_LIST`。
4. 审计日志、凭据巡检、产物过期清理按计划运行。
5. 真实账号连续运营 2 周无发布事故。

## 4.6 关键路径与并行策略

```text
外部：企业号认证 ──────────────────────────► C6 公众号草稿投递
主干：Phase 0 ─► C2 ─► C3 ─► C4 ─► C5 ─► 产物 ─► C6 ─► C7
                                        └─► C8（横切校验）
```

| 路径 | 组成 | 可控性 | 策略 |
|---|---|---|---|
| 最长路径（含外部依赖） | 企业号认证 → C1 凭据落库 → C6 草稿投递 | 低（外部审核不可控） | Day 1 启动；以素材包形态兜底；认证结果只决定「能否推草稿」，不决定主干进度 |
| 技术主干（可预测） | C2 → C3 → C4 → C5 → 产物 | 高 | 优先投人力，保证每周可演示 |
| 末端依赖 | C4/C6 → C7 MCP Hub | 中 | 强制后置到 Phase 3，避免接口返工 |

## 4.7 里程碑一览与验收标准

| 里程碑 | 时点 | 验收标准 | 对应出口 |
|---|---|---|---|
| **M0** 冻结 | 第 2 周末 | 12 个 `ch_*.txt` 落盘；生成器 12 份产物齐备；12 张表建成；三后端文件适配层跑通（SELFFILE 必过）；`plan.md` 产出；资质申请已提交 | Phase 0 |
| **M1** 可看 | 第 6 周末 | 主题资产可完整录入，4 套版式可预览渲染 | Phase 1 |
| **M2** 可用 | 第 9 周末 | 双平台合规产物可渲染；规格校验前置生效 | Phase 2 |
| **M3** 可运营 | 第 12 周末 | 公众号草稿箱端到端打通；小红书素材包可导出；MCP 可用；审计/巡检/归档运行 | Phase 3 |
| **v1.0** 发布 | 第 12 周末 + 观察期 | 真实账号连续运营 2 周无发布事故、无违规告警 | 上线 |

## 4.8 排期红线

| # | 红线 | 原因 |
|---|---|---|
| 1 | **C7（MCP Hub）必须等 C4 / C6 稳定后再做**，安排在 Phase 3 | 否则接口会随渲染引擎一起返工 |
| 2 | **企业号认证从 Day 1 并行启动**，但不阻塞 Phase 1–2 | 外部审核周期不可控；即使未过审，素材包形态依然完整 |
| 3 | **小红书长图拼接优先复用 ylwz `F4A0`（`multiImageMerge`）**，不自研 | 复用优于重造；但需 Phase 0 实测确认（见 D4） |
| 4 | **MCP 传输确定为 streamable-http**（已拍板），Phase 3 落地；后续如需 SSE 由 `mcpConfig.MCP_TRANSPORT` 单点切换 | 避免后期返工；与参考实现 `stock_rotation_strategy/src/mcpapi` 对齐 |
| 5 | **小红书自动发布相关需求一律拒绝**，不接受「技术上能做到」的评审意见 | 平台红线，非技术取舍 |

---

# 5. 各阶段任务清单与预估工时

## 5.1 估算口径与假设

| 项 | 约定 |
|---|---|
| 单位 | 人天（1 人天 = 8 小时有效工作） |
| 节奏 | 单人全职，5 人天/周 |
| 包含 | 编码 + 自测 + 联调 + 文档 |
| 不含 | 外部审核等待期、平台资质往返沟通、需求变更返工 |
| 粒度 | Phase 0 拆到 0.5 人天；Phase 1–3 按任务拆到 0.5~2 人天 |
| 浮动 | 渲染引擎（C4/C5）为最大不确定项，已按上限估算；若超期优先砍「版式数量」而非「渲染质量」 |

## 5.2 Phase 0 · 任务清单（T1–T9）

| ID | 任务 | 内容 | 交付物 | 工时 | 依赖 |
|---|---|---|---|---|---|
| T0 | 资质启动 | 确认目标账号主体类型；提交微信公众平台与小红书开放平台资质申请 | 申请回执、主体类型结论 | 0.5 | — |
| T1 | 目录骨架 | 按 3.7 节建好 `code/src/` 下空目录 | 目录树 | 0.5 | — |
| T2 | 复用层搬运 | 从 `museum/code/src/common/` 复制 8 个模块（`mysqlHandle/funcCommon/miscCommon/globalDefinition/redisCommon/aliyunOSS/tencentCOS/selfFileCommon`）+ `database/mysqlCodeGenerator.py`；新建空占位 `fileStorageCommon.py` / `chCommon.py` / `chServerCommon.py` / `accountClient.py`。**`globalDefinition.py` 需纯追加 3 个 MCP 日志常量**（`_DEF_LOG_CH_MCP_TITLE` / `_DEF_LOG_CH_MCP_NAME` / `_DEF_LOG_CH_TEST_NAME`），不改既有常量 | `common/` 完整文件集 | 0.5 | T1 |
| T3 | 配置文件 | 新建 `config/` 八文件（`local_settings` / `basicSettings` / 三个存储 Settings / `mysqlSettings` / `redisSettings` / `wechatSettings`（留空结构）/ **`mcpConfig.py`**）；`basicSettings` 需追加 **`MCP_TOOL_LIST`**（角色 → 允许的 MCP 工具清单） | 可 import 的 config 包 | 1.0 | T1 |
| T4 | 表定义文件 | 12 个 `database/ch_*.txt`（字段全文见 Phase0 任务清单 §T4）；严格遵守写法红线 | 12 个 txt | 1.5 | T1 |
| T5 | 跑生成器 | 批量执行 `-i ch_*.txt -t <title>`，**只走 `readFromFile()`** | 12 个 `auto_gen_code_ch_*.py` + 12 个 `word_table_ch_*.csv` | 0.5 | T4 |
| T6 | 合并与建表 | 12 份产物 5 段代码人工合并进 `common/mysqlCommon.py`；**补回 `query_*` 的 LIMIT**；`tools/initTables.py` 建表 | `mysqlCommon.py`、`initTables.py`、12 张表 | 1.5 | T5 |
| T7 | 文件门面 | 实现 `fileStorageCommon.py`（含 **D2 三后端签名 shim** + 返回值归一）；`tools/test_storage.py` 三后端联调（upload → getTempUrl → download → delete） | 门面模块 + 联调报告 | 2.0 | T2、T3 |
| T8 | 种子与 plan.md | `tools/initSeed.py` 灌 `ch_platform`(3) / `ch_layout`(≥3)；产出 `plan.md`（目录骨架 / 模块边界 / 接口约定 / 配置项清单 / MCP 选型结论 = **streamable-http + `mcpapi` 两层结构 + Redis session 鉴权**） | 种子数据、`plan.md` | 1.0 | T6 |
| T9 | 阶段验收 | 执行 Phase 0 验收总表 8 项；处理 D1–D4 差异结论 | 验收报告 | 0.5 | T7、T8 |
| | | | **合计** | **9.5** | |

### 5.2.1 T1 目录骨架命令

```bash
cd code/src
mkdir -p common config database/auto_generated \
         engine/templates/{stack_v1,carousel_v1,longimage_v1,swipe_v1} \
         processor/platformAdapter schedule monitor tools test main
```

**验收**：目录存在即可，不要求有内容。

### 5.2.2 T5 批量生成命令

```bash
cd code/src
for f in database/ch_*.txt; do
  t=$(basename "$f" .txt | sed 's/^ch_//')
  python database/mysqlCodeGenerator.py -i "$f" -t "$t"
done
```

**验收**：12 个 `auto_generated/auto_gen_code_ch_*.py` 全部生成，函数名合法（无 `func['xxx']Add`）。

### 5.2.3 T6 建表脚本要点

```python
from common import mysqlCommon as comMysql
for fn in [comMysql.tablename_convertor_ch_topic, comMysql.tablename_convertor_ch_topic_asset,
           comMysql.tablename_convertor_ch_asset, comMysql.tablename_convertor_ch_layout,
           comMysql.tablename_convertor_ch_platform, comMysql.tablename_convertor_ch_render_job,
           comMysql.tablename_convertor_ch_artifact, comMysql.tablename_convertor_ch_account,
           comMysql.tablename_convertor_ch_publish_record, comMysql.tablename_convertor_ch_mcp_token,
           comMysql.tablename_convertor_ch_audit_log, comMysql.tablename_convertor_ch_topic_version]:
    t = fn()
    # 更稳妥：直接调用生成器产出的 create_ch_* 逐表建表
```

> ⚠️ 建表函数为**破坏性操作入口**（`drop_*` 同源）。执行前必须确认 `_SYS` 指向正确的库，禁止在生产库执行 `drop_*`。

### 5.2.4 T7 三后端联调脚本要点

```python
from common import fileStorageCommon as fs
import tempfile

def probe(mode):
    p = tempfile.mktemp(suffix=".txt")
    open(p, "w").write("hello content-hub")
    fid = fs.saveFile(p, objectName=f"probe_{mode}.txt", mode=mode)
    url = fs.getFileTempUrl(fid, mode=mode)
    ok  = fs.delFile(fid, mode=mode)
    print(mode, "upload->", fid, "| url->", bool(url), "| del->", ok)

for m in ["ALIOSS", "TENCENT", "SELFFILE"]:
    probe(m)
```

**验收**：SELFFILE 本地模式全过；ALIOSS / TENCENT 配置就绪后切 `FILE_SYSTEM_MODE` 各跑一遍通过。

## 5.3 Phase 1 · 任务清单（C1 → C4）

| ID | 任务 | 内容 | 交付物 | 工时 | 依赖 |
|---|---|---|---|---|---|
| P1-1 | C1 接入与权限 | `main/chAPI.py` Flask 入口 + `main/chAPIPost.py` 路由分发；`accountClient.py`；sessionID 校验；`ROLE_CMD_LIST` 裁剪；`NO_SESSIONID_CMD_LIST` 放行 | 可鉴权的 `/chapi` | 3.0 | Phase 0 |
| P1-2 | C1 缓冲移植 | 将 `genBufferIndexKey` / `putQuery2Buffer` / `getQueryBufferComplte` 移植进 `common/`（**D3**） | 分页缓冲能力 | 1.0 | P1-1 |
| P1-3 | C2 主题管理 | `topicService.py`：CRUD + 字段区间校验（标题≤50、简介≤200、详述 2000–5000 字）+ 状态机 + `wordCount` 统计 + `topicCode` 幂等 | 主题全链路接口 | 4.0 | P1-1 |
| P1-4 | C2 版本快照 | `ch_topic_version` 写入与查询（P2 能力预留，本期仅落快照） | 版本快照 | 1.0 | P1-3 |
| P1-5 | C3 素材图库 | `assetService.py`：上传（三后端）、`sha256` 去重、规格裁剪（`MAX_PIC_SIZE`/`THUMBNAIL_SIZE`）、EXIF 剥离、缩略图、`fileSystem` 快照 | 素材上传与处理 | 4.5 | P1-1、Phase 0 T7 |
| P1-6 | C3 附图绑定 | `ch_topic_asset` 增删改查；`assetKey = {topicID}:{fileID}` 幂等；`sortOrder` 排序；`usageType` 语义 | 主题-附图关联 | 1.5 | P1-5、P1-3 |
| P1-7 | C4 版式引擎 v1 | `layoutEngine.py` + `imageProc.py`；**硬编码 4 套模板**（`stack_v1` / `carousel_v1` / `longimage_v1` / **`swipe_v1`**）；`specJson` 参数注入 | 可渲染的 4 套版式 | 6.0 | P1-3、P1-6 |
| P1-8 | C4 站内预览 | 微信手机框模拟 + 小红书手机框模拟预览页；`fileID → URL` 出参转换（`fillFileUrls`） | 预览能力 | 2.0 | P1-7 |
| P1-9 | M1 联调验收 | 端到端走查：建主题 → 传图 → 选版式 → 预览；修复缺陷 | M1 验收报告 | 2.0 | P1-8 |
| | | | **合计** | **25.0** | |

> Phase 1 名义周期 3–6 周（15–30 人天），合计 24.0 人天，处于区间内。若进度紧张，优先砍 P1-4（版本快照）与 P1-8 的部分模拟形态。

## 5.4 Phase 2 · 任务清单（C5 + C8）

| ID | 任务 | 内容 | 交付物 | 工时 | 依赖 |
|---|---|---|---|---|---|
| P2-1 | C5 适配基类 | `platformAdapter/base.py`：`render / validate / package / deliver / checkHealth` 抽象接口 | 适配器契约 | 1.0 | Phase 1 |
| P2-2 | C5 微信内联化 | `engine/inlineStyle.py`：全量内联样式化；图片转存 `mmbiz.qpic.cn`；`class` 清洗兼容；SVG 静态图集兜底 | 微信公众号 HTML | 3.0 | P2-1 |
| P2-3 | C5 小红书渲染 | `engine/htmlToImage.py`（Playwright）：HTML → 1080×1440 卡片、图集多张、长图拼接；**`swipe_v1` 左右滑动多图集（切分 + 顺序编排 + 比例统一 + 封面标记，`seqNo` 递增）**；长图按 1080×1440 切分（禁止直接上传超长原图）；**字体预加载 + `waitForFonts`** | 图集 PNG / 长图 / 滑动多图集 | 4.0 | P2-1 |
| P2-4 | C5 通用适配 | `generic.py`：通用 HTML / Markdown / JSON 导出 | 通用产物 | 1.0 | P2-1 |
| P2-5 | C8 合规校验 | `complianceService.py`：敏感词库 + 命中高亮；AI 内容标识校验；发布频率限流计数（Redis）；平台规格校验（标题 / 摘要 / 封面 900×500 / 图片 3:4 / 数量上限）；**新增 `swipe` 专项校验：比例统一（`uniformRatio`）、张数 ≤18、单张 ≤20 MB、格式 JPG/PNG、超长图拦截** | 校验接口 + 问题清单 | 3.5 | P2-1 |
| P2-6 | 产物管理 | `ch_artifact` 写入（`artifactKey` 幂等）、`artifactVer` 版本、`expireYMDHMS` 保留期、`READY/EXPIRED` 状态 | 产物台账 | 2.0 | P2-2、P2-3 |
| P2-7 | 渲染任务化 | `ch_render_job` 状态机（`PENDING/RUNNING/DONE/FAILED`）+ `inputHash` 复用判定 + `schedule/renderWorker.py` 轮询消费 | 异步渲染链路 | 2.0 | P2-6 |
| P2-8 | M2 联调验收 | 双平台产物端到端；规格校验前置拦截验证 | M2 验收报告 | 1.5 | P2-7 |
| | | | **合计** | **18.0** | |

> Phase 2 名义周期 3 周（15 人天），合计 16.5 人天，略超。缓冲来源：P2-4（通用适配）可降级为「复用 `stack_v1` 的 HTML 输出」，节省 1 人天。

## 5.5 Phase 3 · 任务清单（C6 + C7 + 运维）

| ID | 任务 | 内容 | 交付物 | 工时 | 依赖 |
|---|---|---|---|---|---|
| P3-1 | C6 模板消息推送 | 公众号素材上传（图片转 `mmbiz.qpic.cn`）→ `draft/add` 草稿投递；(认证号) `freepublish/submit` + 发布事件回调 | 草稿投递链路 | 3.0 | Phase 2、资质 |
| P3-2 | C6 素材包导出 | `artifactpack`：图集 PNG + `title.txt` + `content.txt`(含话题标签) + `manifest.json` → ZIP | 素材包 ZIP | 2.0 | Phase 2 |
| P3-3 | C6 幂等与防重 | `idempotencyKey` 幂等、二次确认、60 秒撤销窗、发布记录与失败原因回显 | 防重发机制 | 2.0 | P3-1 |
| P3-4 | C7 MCP Server（只读层） | `code/src/mcpapi/` 包（`mcp_entry.py` 入口层 + `mcpPost.py` 实现层）：**8 个只读 tool + 3 个 resource**；鉴权沿用 Redis session（`comDB.getSessionInfo`）+ `ROLE_CMD_LIST`（+ 可选 `MCP_TOOL_LIST` 工具级授权）；**streamable-http 传输**；配套 `config/mcpConfig.py`、`common/chServerCommon.py` | MCP 只读 Server | 8.5 | C4、C6 |
| P3-4b | C7 MCP 写入/生成层（延至 v1.1） | 写入类（`create_topic` / `update_topic`）、渲染类（`render_topic`）、导出类（`export_asset_pack`）、投递类（`push_wechat_draft`）tool | 扩展 tool | 不计入本期 | P3-4 |
| P3-5 | C7 审计 | `ch_audit_log` 全链路写入（`actor/source/action/targetType/targetID/payloadDigest/result/costMs/ipAddr`） | 审计日志 | 1.0 | P3-4 |
| P3-6 | 凭据健康巡检 | `schedule/credentialCheck.py`：定时探活、`healthStatus` 更新、到期前告警、`EXPIRING/INVALID` 告警分级 | 巡检任务 | 2.0 | P3-1 |
| P3-7 | 归档与清理 | `schedule/archive.py`：`ch_audit_log` 分批 DELETE（保留 24 个月）+ 导出；`ch_artifact` 过期产物清理 | 归档任务 | 1.5 | Phase 0 T6 |
| P3-8 | 监控告警 | `monitor/`：渲染失败率、投递成功率、队列积压、凭据健康、磁盘/存储用量 | 监控看板/告警 | 1.5 | P3-6 |
| P3-9 | v1.0 验收 | 全链路 E2E、并发压测（渲染 worker）、恢复演练、上线检查清单 | v1.0 验收报告 | 1.5 | 全部 |
| | | | **合计** | **23.0** | |

> Phase 3 名义周期 3 周（15 人天），合计 23.0 人天（P3-4 由 4.0 上调至 8.5：MCP 独立成包并按参考实现完整落地只读层），超出 8.0 人天。降级建议：P3-8 监控首期降级为「日志告警 + 每日巡检脚本」（-1 人天）；P3-7 归档策略先行落地、导出功能延后（-0.5 人天）；P3-4b 写入/渲染/投递类 tool 全部延至 v1.1（本期不计入）。

## 5.6 工时汇总

| 阶段 | 周期（范围） | 任务数 | 预估工时 | 折算周数 | 里程碑 |
|---|---|---|---|---|---|
| Phase 0 地基 | 第 1–2 周 | 10（T0–T9） | 9.5 人天 | 1.9 周 | M0 冻结 |
| Phase 1 主题与素材 | 第 3–6 周 | 9（P1-1~P1-9） | 25.0 人天 | 5.0 周 | M1 可看 |
| Phase 2 渲染与产物 | 第 7–9 周 | 8（P2-1~P2-8） | 18.0 人天 | 3.6 周 | M2 可用 |
| Phase 3 投递与开放 | 第 10–12 周 | 10（P3-1~P3-9，另 P3-4b 为延后项） | 23.0 人天 | 4.6 周 | M3 / v1.0 |
| **合计** | **约 13–15 周** | **37** | **75.5 人天** | **15.1 周** | — |

> **口径说明**：75.5 人天折算 15.1 周，超 v3 名义的 12 周。差异来自：① 3.2.2 节 D2 适配器 shim 的额外投入（+1 人天）；② Phase 1 补充了缓冲移植（D3）与版本快照（+2 人天）；③ **Phase 3 的 P3-4 由 4.0 上调至 8.5 人天**（MCP 独立成包、按参考实现完整落地只读层，+4.5 人天）；④ **新增 `swipe_v1` 左右滑动多图集**（P1-7 +1.0、P2-3 +1.0、P2-5 +0.5，合计 +2.5 人天，见 2.6 节）；⑤ Phase 2/3 按 5.5 节降级建议可回收 2.5 人天。**按降级建议执行后约 73 人天 ≈ 14.6 周**（名义 12 周为「乐观工期」，本表为「可交付工期」）。

---

# 6. 依赖关系与风险点

## 6.1 外部依赖清单

| # | 外部依赖 | 类型 | 可用性 | 是否阻塞主干 | 应对 |
|---|---|---|---|---|---|
| E1 | 微信公众号开放平台（`access_token` / `draft/add` / `freepublish/submit`） | 平台接口 | 认证后可用；个人号发布接口已回收 | 否 | 只承诺草稿箱；认证结果决定可否追加正式发布 |
| E2 | 小红书开放平台 | 平台接口 | 需企业主体 + 审核 2–4 周 | 否 | **不使用**；改为素材包导出，完全绕开 |
| E3 | 企业号认证（外部审核） | 资质 | 2–4 周不可控 | 否 | Day 1 启动；素材包形态兜底 |
| E4 | ylwz 文件服务（`ylwzRecvFiles.py` + 三适配器） | 内部基础服务 | 已存在，可复用 | 是（模式 A） | 同时支持模式 B 进程内直连，互为备用 |
| E5 | accountService（acis） | 内部基础服务 | 已存在 | 是（C1） | 需新增 `accountClient.py`；Phase 0 联调确认协议 |
| E6 | MySQL 8.0 | 基础设施 | 需新库 | 是 | Phase 0 开通 |
| E7 | Redis | 基础设施 | 需实例 | 是 | Phase 0 开通；仅用于缓冲/锁/限流，非关键路径可降级 |
| E8 | 阿里云 OSS / 腾讯云 COS | 云服务 | 需 AK 与 bucket | 否（SELFFILE 可兜底） | 本地开发全程 SELFFILE；上线前切配置验证 |
| E9 | Playwright Chromium 运行时 | 运行时依赖 | 需安装浏览器内核与中文字体 | 是（C5 小红书） | 镜像内预装；启动时 `waitForFonts` 校验 |
| E10 | DeepSeek / LLM 服务（C9/C10 或 AI 文案） | 外部 API | 可选 | 否 | v1.0 不纳入主线，仅作为 P2 增强；需成本计量与降级 |

## 6.2 内部依赖矩阵

| 模块 | 依赖 | 被依赖 | 说明 |
|---|---|---|---|
| C1 接入与权限 | E5、E6、E7 | C2、C3 | 所有业务入口的前置 |
| C2 主题管理 | C1、`mysqlCommon` | C4、C8 | 内容模型核心 |
| C3 素材图库 | C1、E4/E8、`fileStorageCommon` | C4、C6 | 提供可访问图片 URL |
| C4 版式引擎 | C2、C3、Jinja2、Pillow | C5、C7 | 产物生成的唯一来源 |
| C5 平台适配 | C4、Playwright | C6、C8 | 平台形态隔离层 |
| C6 发布投递 | C5、E1、`ch_account` | C7、C10 | 唯一对外产生副作用的模块 |
| C7 MCP Hub | C2、C4、C6 | — | 强制后置 |
| C8 合规校验 | C2、C5、`ch_platform` | — | 横切，两处入口 |
| 运维（schedule/monitor） | 全部 | — | Phase 3 收口 |

## 6.3 关键路径

```text
最长路径（含外部依赖，不可控）:
  企业号认证(E3) ──► C1 凭据落库 ──► C6 公众号草稿投递 ──► v1.0

技术主干（可控）:
  Phase 0 ──► C2 ──► C3 ──► C4 ──► C5 ──► ch_artifact ──► C6 ──► C7
                                          └──► C8（横切校验）
```

> **抗风险设计**：主干**完全不依赖外部审核**。即使企业号卡住，Phase 1–2 依然能交付「素材包导出」的完整可用形态。

## 6.4 风险登记册

| # | 风险 | 等级 | 影响 | 缓解措施 | 责任阶段 |
|---|---|---|---|---|---|
| R-01 | **版式引擎工作量被低估** | 高 | 三平台形态差异大，抽象过度会拖垮排期 | Phase 1 **先硬编码 4 套模板**跑通端到端，再抽 DSL；模板与引擎解耦、可热更新 | Phase 1–2 |
| R-02 | **微信图片外链不显示 / class 被清洗** | 高 | 公众号产物图片全部失效，排版错乱 | 渲染器强制**全量内联样式**；出图前统一转 `mmbiz.qpic.cn`；SVG 交互提供静态图集兜底；所有模板必须过**真机预览**验收 | Phase 2 |
| R-03 | **凭据静默失效** | 高 | Token 过期/改密后不通知，只表现为投递失败 | `schedule/credentialCheck.py` 定时探活 + `healthStatus` 分级告警（`EXPIRING`/`INVALID`） | Phase 3 |
| R-04 | **误发 / 重复推送** | 高 | 订阅号 1 次/天、服务号 4 次/月，误发不可撤回 | `idempotencyKey` 幂等 + **二次确认** + 60 秒撤销窗 + 发布历史展示 | Phase 3 |
| R-05 | **个人号发布接口已被回收（政策）** | 高 | 「自动发布」核心卖点失效 | 产品承诺改为「推送草稿箱 + 后台一键发布」；把 90% 自动化做扎实 | 全程 |
| R-06 | **小红书严禁第三方自动发布与 AI 托管** | 高 | 一旦实现，用户账号限流/禁言/永久封禁，并连带矩阵账号 | **坚决不做自动发布**；只输出素材包；产品内明确告知风险边界 | 全程 |
| R-07 | **开放平台资质门槛与审核周期** | 高 | 审核 2–4 周，卡住发布链路 | Day 1 提交申请；同期建设「素材包导出」作为无资质阶段的完整替代方案 | 全程 |
| R-08 | **微信 HTML 兼容性陷阱**（同 R-02，独立条目以覆盖「手机端错乱」） | 高 | 真机排版错乱，影响口碑 | 手机尺寸模拟 + 微信草稿预览链接；排版类产品口碑生死线，纳入 M2 出口标准 | Phase 2 |
| R-09 | 生成器 `handleSQL()` 参数错位 | 中 | 从原生 SQL 生成会产出非法函数名、丢主键 | **只走 `readFromFile()` 路径**；或改为关键字传参修复后使用 | Phase 0 |
| R-10 | `query_*` 默认无 LIMIT | 中 | `ch_audit_log` 千万级时拉全表，可能 OOM | 合并后**手工补回 LIMIT**（建议 5000）+ 游标分页；REST 层显式接收 `limitNum` | Phase 0 |
| R-11 | 生成器 INT 强转丢 NULL 语义 | 中 | 可空 INT 列被写成 0 | 可空数值列业务层约定「**0 = 未设置**」；必要时用 `-1` 哨兵并登记文档 | Phase 0 |
| R-12 | **三适配器签名不一致（D2）** | 中 | `aliyunOSS` / `selfFileCommon` 无法直接按统一接口调用，切换后端即报错 | 在 `fileStorageCommon.py` 内实现参数/返回值**归一化 shim**；不修改三个适配器源码；T7 三后端逐一联调 | Phase 0 |
| R-13 | **Redis 缓冲函数位置错位（D3）** | 中 | 以为可直接复用，实际在 API 层，Phase 1 才发现缺失 | Phase 0 明确移植清单（`genBufferIndexKey`/`putQuery2Buffer`/`getQueryBufferComplte`）；P1-2 预留 1 人天 | Phase 0–1 |
| R-14 | **`mysqlHandle` 无连接池（D1）** | 中 | 并发上升后连接数不足 / 单连接阻塞 | 短期：`ping(True)` 保活 + 进程隔离（web / worker 各自独立连接）；长期：Phase 3 评估引入连接池 | Phase 3 |
| R-15 | **`F4A0` 长图拼接能力未验证（D4）** | 中 | 小红书长图可能无法复用现成能力 | Phase 0 T7 实测；不可用则改用 Playwright 整页截图 / Pillow 纵向拼接（自研兜底） | Phase 0 |
| R-16 | 中途切换文件后端 | 中 | 历史 fileID 语义不同，可能读不到 | `ch_asset.fileSystem` 快照；读取时按快照路由到对应适配器 | Phase 1 |
| R-17 | 平台接口频繁变更 | 中 | 「三天一崩」是同类工具通病 | 适配器模式隔离平台差异；接口变更监控 + 快速降级到导出模式；发布失败必须明确提示原因 | Phase 3 |
| R-18 | AI 生成内容的事实错误与同质化 | 中 | 幻觉信息 + 模板化雷同会触发平台降权 | AI 结果**必须人工确认后落库**；保留「来源/时期」字段做事实锚点；生成多样性约束 | Phase 3+ |
| R-19 | 凭证安全与合规 | 中 | AppSecret / Token 泄露导致账号被盗与平台处罚 | AES-256-GCM 加密 + 独立密钥管理（不入库不入代码库）；最小权限；操作审计 | Phase 2–3 |
| R-20 | MCP 协议演进 | 中 | 标准仍在演进，可能返工 | MCP 层只做薄适配（`mcp_entry.py` 仅转发、`mcpPost.py` 仅编排），业务逻辑留在 `processor/*Service.py`；传输由 `mcpConfig.MCP_TRANSPORT` 单点可控 | Phase 3 |
| R-21 | 范围蔓延 | 中 | 平台适配器、模板市场、数据看板容易膨胀，v1.0 难产 | 严格按 P0 冻结 v1.0 范围；扩展平台放 Phase 4；Renderer 接口 + 适配器让扩展成本可预测 | 全程 |
| R-22 | 企业号认证周期 | 低 | 外部审核 2–4 周不可控 | Day 1 启动；主干不依赖 | 全程 |
| R-23 | 渲染产物存储膨胀 | 低 | 多版式产生大量 PNG 变体，存储与带宽成本上升 | `ch_artifact.expireYMDHMS` 保留期 + `schedule/archive.py` 定时清理；限制分辨率与格式（WebP） | Phase 3 |
| R-27 | **MCP 沿用 session 鉴权，token 无法独立吊销与审计** | 中 | 令牌生命周期依赖账号体系，无法针对 MCP 单独吊销/限流；人员离场或泄露时只能改账号密码 | 已接受该代价（对齐参考实现）；如需独立吊销，启用 `ch_mcp_token` 表并新增校验通道；当前以 `MCP_TOOL_LIST` 做工具级最小授权 + `ch_audit_log` 留痕 | Phase 3 |
| R-28 | **MCP 只读层与 Phase 0/1 交付顺序倒挂** | 中 | `mcpapi` 包依赖 `config/basicSettings.py`、`common/{globalDefinition,miscCommon,redisCommon}.py` 与 `/chapi` 端点，而这些由 Phase 0/1 产出；提前交付的代码在 Phase 0 前**不可运行** | 已按「只读 + 零业务」设计，前置就绪后即可联调；前置未就绪期间仅做语法/静态检查（本次已通过 `py_compile`，见 9.6.5） | Phase 0–1 |
| R-29 | **小红书多图规则口径依赖第三方资料** | 中 | `swipe` 的张数上限（18）、比例统一、单张 20 MB 等来自第三方聚合资料；小红书官方后台为登录态、无公开稳定文档，平台调整后我方规则可能失效（表现为批量上传失败） | 规格参数**全部数据化**存 `ch_platform` / `ch_layout.specJson`，平台调整时改配置不改代码；上线前在创作服务平台**实测复核**（7.8 节第 12 项）；上传失败按 `errmsg` 明确回显而非静默 | Phase 2–3 |

## 6.5 降级预案（Plan B）

| 触发条件 | 降级动作 | 影响 |
|---|---|---|
| 企业号认证未通过 | 关闭 `api_publish`，仅保留 `draft_box`（若个人号连草稿受限则仅素材包） | 发布需人工在后台完成 |
| `F4A0` 长图能力不可用 | 小红书长图改为 Playwright 整页截图 | 长图尺寸控制粒度变粗 |
| ALIOSS / TENCENT 任一不可用 | `FILE_SYSTEM_MODE` 切至 SELFFILE，历史文件按 `ch_asset.fileSystem` 快照读取 | 容量与并发受本地磁盘限制 |
| 渲染引擎超期 | 砍版式数量（保留 `stack_v1` 单套），不降低渲染质量 | 小红书图集形态减少 |
| 进度超期 2 周以上 | 将 C9/C10 与 P3-8 监控延至 v1.1 | v1.0 交付范围收缩，主干能力不变 |

---

# 7. 测试与验收标准

## 7.1 测试策略（分层）

| 层级 | 范围 | 手段 | 时机 | 通过标准 |
|---|---|---|---|---|
| L1 单元测试 | 适配器 shim、图片处理、模板渲染、状态机 | `test/` 下 pytest / 生成器自带 `test_ch_*()` | 随阶段开发 | 核心函数覆盖率 ≥70%，关键分支 100% |
| L2 集成测试 | 生成器 → 建表 → CRUD → 幂等写入；文件门面三后端 | `tools/initTables.py` + `tools/test_storage.py` | Phase 0 末 & 每次改表后 | 12 表可重建；三后端 upload/url/del 全 True |
| L3 端到端测试 | 主题 → 素材 → 渲染 → 产物 → 投递/导出 | 真实主题 PoC（建议用一个真实选题） | 每阶段末 | 全链路一键跑通，产物可人工验收 |
| L4 真机/兼容测试 | 微信内联 HTML、小红书手机框 | 真机预览 + 微信草稿预览链接 | Phase 2 起每次改模板 | 手机端排版无错乱、图片全部显示 |
| L5 非功能测试 | 并发渲染、队列积压、长事务、存储增长 | 压测脚本 + 监控观测 | Phase 3 | 渲染队列不积压超阈值；无长事务告警 |
| L6 安全测试 | 凭据加密、Token 校验、越权访问 | 手工 + 目录扫描 | Phase 3 | 明文凭据零落库；越权请求全部拒绝 |

## 7.2 单元测试清单

| 编号 | 被测对象 | 用例要点 | 期望 |
|---|---|---|---|
| U-01 | `fileStorageCommon.saveFile` | 三后端参数归一（含 `aliyunOSS` 参数顺序反转、`selfFileCommon` dict 组装） | 三后端均返回非空 fileID |
| U-02 | `fileStorageCommon.downloadFile` | 返回值归一（bool vs 路径字符串） | 统一返回落盘路径或 `""` |
| U-03 | `fileStorageCommon.getTempLocation` | 入参为 http 开头 | 原样返回，不触发后端调用 |
| U-04 | `saveWithThumbnail` | 缩略图生成 | 返回两个不同 fileID，缩略图 ≤ `THUMBNAIL_SIZE` |
| U-05 | 内容去重 | 同一文件二次上传 | `contentHash` 命中，返回既有 fileID，不产生新对象 |
| U-06 | `upsertByUniqueKey` | 命中 / 未命中两条路径 | 命中走 update 且 recID 不变；未命中走 insert |
| U-07 | `ch_topic` 字段校验 | 标题 51 字 / 简介 201 字 / 详述 1999 与 5001 字 | 全部拦截并返回明确错误码 |
| U-08 | 主题状态机 | 非法跃迁（如 `ARCHIVED → RENDERING`） | 拒绝并返回当前状态 |
| U-09 | 版式模板渲染 | 4 套模板 × 空数据 / 满数据 / 超长文本 | 无异常、无未转义输出 |
| U-10 | 微信内联样式器 | 输入含 `class` / 外链 `<img>` | 输出无 `class` 依赖，图片 URL 已转为平台可显示地址 |
| U-11 | 规格校验器 | 微信标题 65 字 / 小红书图 4:3 / 图片数超上限 | 全部命中问题清单，且标注字段与位置 |
| U-12 | 敏感词检测 | 命中位置与高亮区间 | 返回命中词与偏移，前端可直接标注 |
| U-13 | 幂等键 | 相同 `idempotencyKey` 二次提交 | 第二次被拒绝，不产生第二条发布记录 |
| U-14 | 频率限流 | 单账号当日超阈 | 拒绝并给出下一次可用时间 |
| U-15 | `ch_mcp_token` 校验 | 已吊销 / scope 不足 / 有效 | 分别返回 `REVOKED` / `FORBIDDEN` / 通过 |
| U-16 | 可空 INT 语义 | `width`/`height`/`sizeBytes` 传空 | 落库为 0，业务层按「未设置」处理，不报错 |

## 7.3 集成测试清单

| 编号 | 场景 | 步骤 | 期望 |
|---|---|---|---|
| I-01 | 生成器全量跑通 | 对 12 个 `ch_*.txt` 执行批量生成 | 12 个 `auto_gen_code_ch_*.py` + 12 个 `word_table_ch_*.csv` |
| I-02 | 建表 | 执行 `tools/initTables.py` | `SHOW TABLES LIKE 'ch_%'` 返回 12 张 |
| I-03 | CRUD 往返 | 对每张表 insert → query → update → delete | 四步均成功，`modifyYMDHMS` 正确更新 |
| I-04 | 幂等写入 | 对 6 张带唯一键的表执行 upsert 两次 | 记录数不增加 |
| I-05 | 三后端文件门面 | `tools/test_storage.py` 依次跑 ALIOSS / TENCENT / SELFFILE | 三种模式 upload/url/del 全 True |
| I-06 | 后端快照路由 | SELFFILE 落库后切 `FILE_SYSTEM_MODE=ALIOSS`，读历史 fileID | 依据 `ch_asset.fileSystem` 仍可正确取到 URL |
| I-07 | LIMIT 补丁有效性 | `query_ch_audit_log` 无参调用 | 实际 SQL 带 LIMIT 5000，不拉全表 |
| I-08 | 种子数据 | 执行 `tools/initSeed.py` | `ch_platform` = 3，`ch_layout` ≥ 3 |
| I-09 | 权限裁剪 | 以 4 类角色分别请求端点 | 可用端点集合与 `ROLE_CMD_LIST` 完全一致 |
| I-10 | 公开端点免登录 | 请求 `platformqry` / `layoutqry` / `artifactqry` | 不带 sessionID 亦可返回 |

## 7.4 端到端测试（PoC 场景）

**建议 PoC 脚本**：用一个真实选题走完整链路，验证版式引擎的表达力能覆盖真实场景。

| 步骤 | 操作 | 验收点 |
|---|---|---|
| 1 | 录入主题（标题 / 简介 / 2000 字以上详述 / 作者 / 地点 / 来源 / 时期 / 标签） | 落库成功，`wordCount` 自动统计正确 |
| 2 | 上传 5–10 张图（含重复图 1 张、超规格大图 1 张、带 EXIF 的图 1 张） | 重复图被拦截；大图被压缩至 `MAX_PIC_SIZE` 内；EXIF 已剥离 |
| 3 | 为每张图填写图注并排序 | `ch_topic_asset` 顺序正确，`assetKey` 无冲突 |
| 4 | 选择 `stack_v1` + `wechat_mp` 渲染 | 产出内联样式 HTML，站内预览无错乱 |
| 5 | 选择 `swipe_v1` / `carousel_v1` / `longimage_v1` + `xiaohongshu` 渲染 | `swipe_v1` 产出 N 张同比例 1080×1440 PNG（`seqNo` 递增、封面标记正确、顺序可编排）；长图产出无丢字；**比例混用时被 C8 校验拦截** |
| 6 | 执行合规校验 | 返回问题清单（若规格/敏感词命中则明确标注位置） |
| 7 | 公众号投递（如资质可用） | 草稿箱出现该文章，图片正常显示 |
| 8 | 小红书素材包导出 | ZIP 含图片 + `title.txt` + `content.txt` + `manifest.json`，可直接用于官方后台发布 |
| 9 | 查询审计日志 | 上述每个动作都有 `ch_audit_log` 记录，`actor/action/result` 正确 |

## 7.5 模块 DoD（Definition of Done）

| 模块 | DoD |
|---|---|
| C1 | 4 类角色端点集合与配置一致；越权请求 100% 拒绝；`NO_SESSIONID_CMD_LIST` 生效 |
| C2 | 全字段 CRUD 可用；区间校验生效；状态机无非法跃迁；`topicCode` 幂等 |
| C3 | 三后端可切；`contentHash` 去重生效；缩略图与规格图自动生成；`fileSystem` 快照落库 |
| C4 | **4 套模板**均可渲染（含 `swipe_v1`）；`specJson` 参数可调；预览页与真机效果一致 |
| C5 | 微信产物图片全部可见、无 class 依赖；小红书产物尺寸精确 1080×1440；通用产物可导出 |
| C6 | 草稿投递成功并回写 `remoteID`；素材包 ZIP 结构完整；重复提交被幂等拦截 |
| C7 | 8 个只读 tool 可被 Agent 调用；Redis session + `ROLE_CMD_LIST` 鉴权生效；streamable-http 可连 |
| C8 | 规格/敏感词/AI 标识/频率四类校验全部前置生效且返回可定位的问题清单 |
| 运维 | 归档、巡检、清理三个定时任务按计划执行并留痕 |

## 7.6 Phase 0 验收总表

| # | 检查项 | 命令 / 方法 | 期望 |
|---|---|---|---|
| 1 | 目录骨架 | `ls` | T1 目录齐全 |
| 2 | 复用层 import | `python -c "from common import mysqlHandle,funcCommon,miscCommon,globalDefinition,redisCommon,aliyunOSS,tencentCOS,selfFileCommon"` | 无报错 |
| 3 | 配置文件 | `python -c "from config import basicSettings"` | 无报错 |
| 4 | 12 个 txt | `ls database/ch_*.txt \| wc -l` | 12 |
| 5 | 生成器产物 | `ls database/auto_generated/auto_gen_code_ch_*.py \| wc -l` | 12 |
| 6 | 建表 | `SHOW TABLES LIKE 'ch_%'` | 12 张 |
| 7 | 文件门面 | `python tools/test_storage.py`（SELFFILE） | upload/url/del 均 True |
| 8 | 种子 | `SELECT COUNT(*) FROM ch_platform` | 3 |
| 9 | 定义文件格式 | `cat -A database/ch_*.txt \| grep -c $'\^I'` | 0（无 Tab 混入） |
| 10 | 函数名合法性 | 检查 12 份产物 | 无 `func['xxx']Add` 形态 |

## 7.7 里程碑验收标准

| 里程碑 | 时点 | 验收标准 | 验收方式 |
|---|---|---|---|
| **M0** 冻结 | 第 2 周末 | 7.6 节 10 项全过；D1–D4 差异有结论；`plan.md` 产出；资质申请已提交 | 逐项执行命令 + 验收报告 |
| **M1** 可看 | 第 6 周末 | 主题可完整录入；4 套版式可预览；权限裁剪生效 | 7.4 节步骤 1–4 通过 |
| **M2** 可用 | 第 9 周末 | 双平台合规产物可渲染；规格校验前置拦截 | 7.4 节步骤 1–6 通过 + 真机预览确认 |
| **M3** 可运营 | 第 12 周末 | 公众号草稿端到端打通；素材包可导出；MCP 可用；运维任务运行 | 7.4 节 9 步全通过 |
| **v1.0** | 第 12 周末 + 观察期 | 真实账号连续运营 2 周无发布事故、无违规告警 | 运营记录 + 审计日志复核 |

## 7.8 素材包合规验收（小红书专项）

小红书素材包是「不自动发布」路线的核心交付物，必须逐项验收：

| # | 检查项 | 期望 |
|---|---|---|
| 1 | 图片数量 | ≤ **18 张**（`ch_platform.imageMaxCount=18`）；建议 6–9 张密度最佳，不为凑数硬塞 |
| 2 | 图片命名 | 有序（`01_`、`02_`…），**顺序即 App 内左右滑动浏览顺序**，与选题逻辑一致 |
| 2b | **比例统一** | 整篇**只能用一种比例**（首选 3:4 = 1080×1440）；混用会导致滑动时画面跳动，须被 C8 校验拦截 |
| 2c | **单张规格** | ≤ 20 MB；格式 JPG / PNG；尺寸精确 1080×1440 |
| 3 | `title.txt` | 标题 ≤ 20 字，无敏感词 |
| 4 | `content.txt` | 正文含话题标签（`#`），无违规词，无模板化重复话术 |
| 5 | AI 标识 | 若 `aiFlag=1`，文案尾部含 AI 创作标识 |
| 6 | `manifest.json` | 含主题编码、生成时间、版式、平台、文件清单与校验值 |
| 7 | 图片版权提示 | 含来源/时期信息，提示用户核对版权 |
| 8 | 风险告知 | ZIP 内附「本素材包需在官方创作服务平台手动发布，禁止第三方自动发布」提示文本 |
| 9 | **超长图处理** | 不得直接上传超长原图（会被强制缩放导致文字模糊）；长图形态须按 1080×1440 切分为多张 |
| 10 | **顺序编排** | 第 1 张为封面；建议「封面 → 承接(2–3) → 主体(4–12) → 对比补充(13–16) → 总结(17) → 收尾(18)」 |
| 11 | **滑动可用性提示** | 提示用户：滑动须在**图片显示区域内**操作（标题栏 / 评论区滑动无效）；老版本 App 需 **8.0+** 才支持原生滑动手势 |
| 12 | **平台实测复核** | 上线前在**小红书创作服务平台**实测复核图片数量 / 比例 / 大小规则（第三方资料可能滞后于平台调整） |

## 7.9 上线前回归清单

1. 7.6 节 Phase 0 验收 10 项复跑通过。
2. 7.3 节集成测试 10 项全过。
3. 7.4 节端到端 9 步全过。
4. 7.8 节素材包合规 8 项全过。
5. `FILE_SYSTEM_MODE` 三种取值各跑一遍冒烟。
6. 备份与回滚脚本演练一次（恢复演练记录留档）。
7. 监控告警通道连通性验证（故意触发一次测试告警）。
8. 凭据巡检手动执行一次，`healthStatus` 正确写入。

---

# 8. 部署与上线流程

## 8.1 环境矩阵

`_SYS` 决定配置取值，`FILE_SYSTEM_MODE` 由 `_SYS` 映射得出。

| `_SYS` | 用途 | `FILE_SYSTEM_MODE` | MySQL | Redis | 说明 |
|---|---|---|---|---|---|
| `local` | 本地开发 | `SELFFILE` | 本地实例 | 本地实例 | 日常开发与单测 |
| `home` | 个人环境 | `SELFFILE` | 本地/远程 | 本地/远程 | 私人验证 |
| `test_server` | 测试环境 | `SELFFILE` | 测试库 | 测试实例 | 集成 / E2E / 回归 |
| `server_01` | 生产环境 A | `ALIOSS` | 生产库（读写分离） | 生产实例 | 正式运行 |
| `server_02` | 生产环境 B | `TENCENT` | 生产库（读写分离） | 生产实例 | 备用 / 迁移目标 |

> 切换环境只需改 `config/local_settings.py` 的 `_SYS`，**不改任何业务代码**。

## 8.2 部署拓扑

```text
                   ┌──────────────────────┐
  浏览器 / Agent ──►│ Nginx（TLS / 反代）  │
                   └───────┬──────────────┘
                           │
        ┌──────────────────┼──────────────────────┐
        ▼                  ▼                      ▼
  ┌───────────┐    ┌───────────────┐    ┌────────────────┐
  │ chAPI     │    │ renderWorker  │    │ mcp_entry      │
  │ (Flask    │    │ (常驻轮询     │    │ (streamable-   │
  │  多进程)  │    │  渲染队列)    │    │  http:8890)    │
  └─────┬─────┘    └───────┬───────┘    └───────┬────────┘
        │                  │                    │
        └──────────────────┼────────────────────┘
                           ▼
     ┌─────────────────────────────────────────────┐
     │ MySQL 8.0（读写分离） │ Redis（缓冲/锁/限流） │
     │ ALIOSS / TENCENT / SELFFILE                  │
     └─────────────────────────────────────────────┘
        ▲
        │ cron：credentialCheck（凭据巡检）/ archive（归档清理）
```

**常驻进程清单**

| 进程 | 启动方式 | 数量建议 | 说明 |
|---|---|---|---|
| `main/chAPI.py` | WSGI（gunicorn/uwsgi）多 worker | 2–4 | Web 与 REST 主入口 |
| `schedule/renderWorker.py` | 独立常驻进程（supervisor/systemd） | 1–2 | 渲染队列消费者；与 Web 隔离，避免截图任务拖垮 Web |
| `mcpapi/mcp_entry.py` | 独立常驻进程（supervisor/systemd，或 `restore_mcp.sh`） | 1 | MCP 远程接入（streamable-http，默认端口 8890） |
| `schedule/credentialCheck.py` | cron（建议每 6 小时） | — | 凭据健康巡检 |
| `schedule/archive.py` | cron（建议每日凌晨） | — | 审计日志归档 + 产物清理 |

## 8.3 首次部署步骤

| 步骤 | 操作 | 验收 |
|---|---|---|
| 1 | 环境准备：Python 3.13 运行时、MySQL 8.0（InnoDB / utf8mb4 / `utf8mb4_unicode_ci`）、Redis、Playwright Chromium 与中文字体 | 版本校验通过 |
| 2 | 拉取代码至 `code/src`，安装依赖（`pip install -r requirements.txt`，含 `pymysql / redis / requests / Jinja2 / Pillow / playwright / Flask / gunicorn`） | `pip check` 无冲突 |
| 3 | `playwright install chromium` 并验证中文字体渲染 | 截图无方框/丢字 |
| 4 | 配置：设置 `config/local_settings.py` 的 `_SYS`；填写 `mysqlSettings` / `redisSettings` / 存储 Settings / `wechatSettings`；凭据密钥写入环境变量或 KMS | `python -c "from config import basicSettings"` 无报错 |
| 5 | 建表：执行 `tools/initTables.py`（**生产库禁止执行 `drop_*`**） | `SHOW TABLES LIKE 'ch_%'` = 12 |
| 6 | 种子：执行 `tools/initSeed.py` | `ch_platform`=3、`ch_layout`≥3 |
| 7 | 文件门面冒烟：`tools/test_storage.py` | 三种模式全 True |
| 8 | 启动常驻进程（Web / worker / MCP），配置 Nginx 反代 `/chapi` 与 MCP SSE 路径 | 健康检查返回 200 |
| 9 | 配置 cron（巡检 / 归档） | 任务执行留痕 |
| 10 | 执行 7.9 节上线前回归清单 | 全部通过 |

## 8.4 上线检查清单

**发布前**

- [ ] 7.9 节回归清单 8 项全过
- [ ] `_SYS` 与 `FILE_SYSTEM_MODE` 指向目标生产环境并复核
- [ ] 数据库备份已完成，且备份文件可读（做一次抽样恢复验证）
- [ ] 凭据密钥（AES）与平台 AK 已配置，且**不在代码库中**
- [ ] `ROLE_CMD_LIST` 与 `NO_SESSIONID_CMD_LIST` 已复核，无越权暴露
- [ ] `ch_platform` / `ch_layout` 种子数据为最新版本
- [ ] 监控告警通道连通，告警接收人已确认
- [ ] 小红书自动发布相关代码路径**不存在**（静态检查确认）

**发布中**

- [ ] 逐进程滚动重启：先 worker，后 Web
- [ ] 每步后执行健康检查与一次最小冒烟（查询 `ch_platform`）
- [ ] 观察日志 10 分钟无 ERROR

**发布后**

- [ ] 执行一次完整 E2E（7.4 节 9 步）
- [ ] 观察渲染队列积压、投递成功率、接口错误率
- [ ] 审计日志确认本次发布动作已留痕
- [ ] 记录发布版本号与时间点

## 8.5 灰度与发布流程

| 阶段 | 范围 | 观察项 | 放行条件 |
|---|---|---|---|
| 内网自测 | `test_server`（`SELFFILE`） | 全链路、三后端切换 | 7.9 全过 |
| 小范围试用 | 1–2 个真实账号 | 草稿投递成功率、真机排版 | 连续 3 天无事故 |
| 全量上线 | 全部账号 | 投递成功率、队列积压、凭据健康 | 观察期 2 周无发布事故 → v1.0 达成 |

> **发布纪律**：公众号投递类功能**禁止一次性全量放开**，必须先小范围验证「草稿箱内容正确性」再扩大。

## 8.6 回滚方案

| 维度 | 回滚方式 | 前置条件 | 注意事项 |
|---|---|---|---|
| 应用代码 | 切回上一个发布版本（保留最近 3 个版本包） | 版本包留存 | 回滚后立即复跑冒烟 |
| 配置 | 恢复 `config/` 快照 | 每次发布前备份 `config/` | `_SYS` 改错是最高频事故源 |
| 数据库结构 | 生成器**不提供 migration**，仅提供 `create_*` / `drop_*` | 改表前必须备份 + 保留旧 `ch_*.txt` | ⚠️ **生产库禁止 `drop_*`**；需改表时走「新增列 + 双写过渡 + 收拾旧列」三步 |
| 数据 | 从备份恢复指定表 | 有可用备份（建议每日全量 + binlog） | 恢复后需重放期间的业务日志核对 |
| 进程 | supervisor/systemd 单进程回退 | 进程托管已配置 | 单进程回退不影响其他进程 |
| 文件后端 | `FILE_SYSTEM_MODE` 切回原值 | `ch_asset.fileSystem` 快照完整 | 历史文件按快照读取，无需迁移 |

> **数据库变更红线**：由于生成器无 migration 机制，**任何生产表结构变更必须先备份 + 在测试库演练 + 保留回滚 DDL**。这是本项目最容易造成不可逆损失的操作。

## 8.7 监控告警

| 监控项 | 采集方式 | 阈值（建议） | 告警级别 |
|---|---|---|---|
| 渲染失败率 | `ch_render_job.jobStatus=FAILED` 占比 | 15 分钟窗口 > 10% | 高 |
| 投递成功率 | `ch_publish_record.success='0'` 占比 | 单日 > 5% 或连续 3 次失败 | 高 |
| 渲染队列积压 | `PENDING` 任务数与最老任务等待时长 | 等待 > 15 分钟 | 中 |
| 凭据健康 | `ch_account.healthStatus` | 出现 `EXPIRING` / `INVALID` | 高 / 中 |
| 接口错误率 | `/chapi` 5xx 占比 | 5 分钟窗口 > 1% | 高 |
| 数据库慢查询 | MySQL slow log | 单条 > 2s | 中 |
| 存储用量 | 对象存储容量 / 本地磁盘 | 使用率 > 80% | 中 |
| 定时任务 | 归档 / 巡检最后成功时间 | 超过 1.5 个周期未成功 | 中 |
| 审计日志量 | `ch_audit_log` 日增量 | 环比突增 > 3 倍 | 低 |

**告警通道**：沿用 `miscCommon.setLogNew()` 落盘至 `code/log/`，外加 `monitor/` 输出的告警通知（邮件 / 企微机器人，具体通道在 Phase 3 定）。

---

# 9. 支线任务规划（并行 / 后续执行项）

主计划（第 1–8 章）覆盖 contentHub 的自有主干。本章登记两条**支线任务**——它们不属于主干交付路径，但会改变主干的部分技术前提，因此必须显式纳入规划、标明依赖与优先级。

## 9.1 支线总览

| 编号 | 支线 | 单独文档 | 类型标注 | 优先级 | 工时 | 执行窗口 | 与主计划关系 |
|---|---|---|---|---|---|---|---|
| **S1** | ylwz 文件服务多 Bucket 支持 | `plan/ylwz文件服务多Bucket.md` | **并行支线**（可降级为后续） | P1 | 7.0 人天 | 与 **Phase 0 · T7** 同步 | T7 的**上游能力增强**；不阻塞主干 |
| **S2** | chAPIPost 服务拆分（`subfunc/` 目录） | `plan/chAPIPost分拆方案.md` | **并行支线**（且为 **C1 强前置**） | **P1（关键前置）** | 11.0 人天 | **Phase 0 期间启动，C1 开工前收口** | **C1 的前置条件**；不完成则 C1 无法优雅落点 |

> **工时口径**：两条支线合计 **18.0 人天**，**不计入**主干 75.5 人天（第 5.6 节）。若计入，总工作量约 **93.5 人天 ≈ 18.7 周**。
>
> 另：主计划 C7（MCP）的**只读层已按参考实现提前交付**（见 9.6 节），其工时已计入主干 Phase 3 · P3-4，**不重复计算**。

## 9.2 S1 · ylwz 文件服务多 Bucket 支持

### 9.2.1 要解决的问题

现状 Bucket 是「环境级常量」：ALIOSS 只有 1 个桶且写死在适配器常量（`common/aliyunOSS.py` L79，9 处调用点硬编码）；TENCENT 虽有 2 个桶但仅靠 `privateFlag` 二分，且 `privateFlag` 在 ALIOSS 上**完全无效**；请求协议中**无任何字段可指定目标桶**；读取时也**不依据记录里的桶名路由**（实测确认：`storageBucket` 列只被写入、从未用于路由）。

### 9.2.2 关键交付

1. `config/aliyunSettings.py` / `config/tencentSettings.py` 结构升级：新增 `Buckets`（逻辑桶码 → 物理桶名 + 路径前缀 + 访问属性）与 `DefaultBucketCode`，**保留旧键作为派生别名**（旧代码零改动可跑）。
2. 新增 `config/bucketSettings.py`：全项目唯一的桶解析出口（`getBucketInfo` / `resolveBucketBySnapshot` / `listBuckets`）。
3. 三适配器追加**尾部可选参数** `bucketCode`，参数顺序与旧签名兼容。
4. `ylwzRecvFiles.py` 的 F0A0/F1A0/F2A0/F6A0/F7A0/F8A0 支持桶参数与快照落库，读/删/信息路径按快照路由。
5. STS 策略 `Resource` 按全部桶**自动展开**，避免加桶后漏配。

### 9.2.3 与主计划的依赖关系

| 维度 | 说明 |
|---|---|
| 依赖方向 | 主计划 **Phase 0 · T7**（`fileStorageCommon.py` 门面 + 三后端联调）与 S1 **并行**；S1 是 T7 的能力增强，**不是前置** |
| 被主计划谁消费 | C3 素材图库（多桶落点）、C5 平台适配（产物独立落桶）、`ch_artifact` 产物管理（产物与大图分桶，控制成本与保留期） |
| 阻塞性 | **不阻塞主干**。Phase 0–3 全部可按单桶跑通，S1 完成后才启用多桶 |
| 与红线关系 | 强化 **R2（配置驱动多态）**：多桶能力是「配置驱动」的延伸，不得引入任何硬编码桶分支 |
| 对主计划的改动 | 主计划 3.3.3 节的适配器 shim（差异 D2）由「参数适配」升级为「参数适配 + 桶解析」；`fileStorageCommon` 的 `saveFile / delFile / getTempLocation` 追加尾部可选参数 `bucketCode` |

### 9.2.4 降级路径

若资源紧张，可**只做 S1-1~S1-3**（配置结构 + 解析器 + 三适配器具备多桶能力，服务协议暂不扩展），工时压缩至 **3.5 人天**；其余部分顺延至 Phase 1 内完成。

## 9.3 S2 · chAPIPost 服务拆分

### 9.3.1 要解决的问题

基线 `main/museumAPIPost.py` 约 **11,810 行 / 469 KB**、**123 个 `def`**、单文件承载**全部 91 个对外 CMD**（约为整个 `common/` 目录之和的 1.4 倍）。账号逻辑与业务 CRUD 混放，大量重复样板，且 `common/museumCommon.py`（1,220 行）抽出的公共层**完全未被主文件 import**（17 处仅为注释）——公共层形同虚设。

### 9.3.2 关键交付

1. 新建 `code/src/main/subfunc/`：`__init__.py`（聚合 + 三道校验）、`context.py`（共享依赖）、`apiCommon.py`（**零业务**公共件）、`accountSvcClient.py`、`accountApi.py`、`crudApi.py`（生成件落点）、6 个业务域模块。
2. `main/chAPIPost.py` 收敛为**瘦入口**（目标 ≤ 400 行）：只做聚合 + `post()` 主流程 + 权限/会话/停用校验。
3. 聚合方式：各模块暴露 `CMD_MAP`，由 `subfunc/__init__.py` 合并并做 **CMD 冲突 / 可调用性 / 与 `ROLE_CMD_LIST` 完整性** 三道导入期校验。
4. `funcCommon.py` 错误消息部分（`CONST_ERROR_wordList` L57–486 + `rtnMSG`）抽为 `common/errMsgCommon.py`，**保留 re-export** 使 25 个既有引用方零改动，并新增 `contenthub` msgKey。
5. CI 约束（防回退）：`chAPIPost.py` > 500 行失败、`subfunc/` 单文件 > 1000 行失败、`subfunc/` 出现 `import chAPIPost` 失败、`chCommon.py` 建而不用失败。

### 9.3.3 与主计划的依赖关系

| 维度 | 说明 |
|---|---|
| 依赖方向 | **主计划 C1（接入与权限）依赖 S2**：`main/chAPIPost.py` 的结构与 `subfunc/` 骨架必须先定，C1 才有落点 |
| 被主计划谁消费 | C1（账号/权限全部落 `accountApi.py` 与 `apiCommon.py`）、C2–C8 的 6 个业务端点（各归其域）、Phase 3 的 C7（`mcpApi.py` 已预留） |
| 阻塞性 | **对 C1 是强前置**；对 Phase 0 不阻塞（Phase 0 不涉及 HTTP 层） |
| 优先级 | **P1，且高于 S1**——S2 不收口，C1 将在巨型文件上重复堆叠，后续拆分成本翻倍 |
| 与红线关系 | 强化 **R1**：`crudApi.py` 作为生成件落点与手写逻辑物理隔离，保证重跑生成器不覆盖手写代码 |
| 对主计划的改动 | ① 3.7 节目录结构在 `main/` 下补 `subfunc/` 子树；② 5.3 节 P1-1 拆为「S2 骨架（前置）+ C1 业务接入」两步；③ **C1 工时由 3.0 人天下调为 2.0 人天**（骨架由 S2 承担）；④ 新增风险 R-24「公共层建而不用」（见 9.5） |

### 9.3.4 里程碑（支线自有）

| 里程碑 | 内容 | 时点约束 |
|---|---|---|
| S2-M1 | 骨架 + 聚合器 + 公共层（S2-1、S2-2） | Phase 0 期间 |
| S2-M2 | 账号域 + 主流程跑通（S2-3、S2-7） | **C1 开工前，强约束** |
| S2-M3 | CRUD 装配 + 全量回归 + CI 约束（S2-4~S2-8） | Phase 1 内 |

## 9.4 支线与主干的时间关系

```text
周次:        1     2   |  3     4     5     6   |  7    8    9   | 10   11   12
主干 Phase:  0        |  1                     |  2             |  3
主干里程碑:  M0        |  M1                    |  M2            |  M3 / v1.0

S2 拆分:     ███ S2-M1 (骨架/公共层)                ← 必须在 C1 前
             ███ S2-M2 (账号域/主流程)  ──► 强约束：C1 开工前收口
                          ███ S2-M3 (CRUD/回归)  ← 可与 C1/C2 穿插

S1 多桶:     ███ (与 T7 并行) ──► 可降级为「仅配置+适配器」(3.5 人天)
```

| 判断 | 结论 |
|---|---|
| 必须并行 | **S2 的 S2-M1 / S2-M2**（否则阻塞 C1） |
| 建议并行 | **S1**（与 T7 同窗口，边际成本最低） |
| 可后续化 | S1 的服务协议扩展部分、S2-M3（CRUD 装配与回归） |

## 9.5 支线引入的主计划调整点（需同步生效）

| # | 调整项 | 位置 | 内容 |
|---|---|---|---|
| 1 | 目录结构补 `main/subfunc/` 子树 | 第 3.7 节 | 增加 `subfunc/`（11 个文件）与其职责说明 |
| 2 | C1 任务拆分 | 第 5.3 节 P1-1 | 拆为「S2 骨架（前置，由支线承担）+ C1 业务接入」，C1 工时 3.0 → **2.0 人天** |
| 3 | 文件门面签名扩展 | 第 3.3.4 节 | `saveFile/delFile/getTempLocation` 追加尾部可选参数 `bucketCode`（S1） |
| 4 | 风险登记册新增 | 第 6.4 节 | **R-24 公共层建而不用**（`museumCommon` 教训）、**R-25 支线与主干并行导致的人力争抢** |
| 5 | 工时汇总补充支线 | 第 5.6 节 | 主干 73.0 人天 + 支线 18.0 人天 = **91.0 人天 ≈ 18.2 周** |
| 6 | MCP 模块相关章节同步 | 第 2.2 / 3.6 / 3.7 / 4.8 / 5.2 / 5.5 / 6.4 / 10.2 / 10.5 节 | 传输改 streamable-http、落点改 `mcpapi/` 包、鉴权改 Redis session + `ROLE_CMD_LIST`、P3-4 工时 4.0→8.5 人天；详见 9.6 节 |

### 9.5.1 新增风险（补充至第 6.4 节风险登记册）

| # | 风险 | 等级 | 影响 | 缓解 | 责任阶段 |
|---|---|---|---|---|---|
| R-24 | **公共层建而不用**（重蹈 `museumCommon` 覆辙：抽出 1,220 行却零引用） | 高 | 拆分名义完成、实际继续堆叠，治理失效 | CI 约束「`chCommon.py` 存在但 `chAPIPost.py` 未 import 则构建失败」；`apiCommon.py` 强制零业务 | Phase 0–1 |
| R-25 | **支线与主干并行争抢人力** | 中 | 主干里程碑延期 | S2-M2 设为硬约束、其余支线任务标记为「可后续化」；主线冲突时支线让位 | Phase 0–1 |
| R-26 | S1 多桶改造导致**历史文件读不到** | 高 | 存量素材大面积失效 | 红线：**默认桶物理名不得变更**；读取按落库快照路由 + 快照缺失回落默认桶（旧数据兼容） | Phase 0 |

## 9.6 C7 · MCP 模块实现（提前交付项）

> 本节登记主计划 **C7（MCP 与开放接口）只读层**的实现方案与已交付产物。它**不属于支线**，而是 C7 在 Phase 3 之外的提前落地，工时计入主干 P3-4。

### 9.6.1 对齐依据与四项已拍板决策

参照实现：`D:\StevenLianData\0301. Private Project\gitData\stock_rotation_strategy\src\mcpapi`

| # | 决策点 | 结论 |
|---|---|---|
| 1 | 鉴权模型 | **沿用参考实现**：FastMCP 官方 `token_verifier`；Bearer token 即 ylwz sessionID，经 `comDB.getSessionInfo(token)` 取会话，`roleName in settings.ROLE_CMD_LIST` 放行。**不使用 `ch_mcp_token` 表** |
| 2 | 传输协议 | **streamable-http**（`FastMCP` + `mcp.streamable_http_app()` + uvicorn），默认端口 **8890**（避开参考实现的 8889） |
| 3 | 工具集范围 | **只读为主**：8 个只读 tool + 3 个只读 resource；写入/渲染/导出/投递类 tool 延至 v1.1 |
| 4 | 代码落位 | 新建 **`code/src/mcpapi/` 包**（完全对齐参考实现目录结构）；原规划的 `main/mcpServer.py`、`processor/mcpHub.py` **废弃** |

### 9.6.2 遵循的参考实现模式

| 模式 | 说明 |
|---|---|
| **两层结构** | `mcp_entry.py`（入口层：协议接入 + `@mcp.tool()` 纯参数转发，无业务逻辑）+ `mcpPost.py`（实现层：全部编排与数据获取） |
| **`_LOG` 注入** | 入口层 `misc.setLogNew(comGD._DEF_LOG_CH_MCP_TITLE, comGD._DEF_LOG_CH_MCP_NAME)` 创建 → `userApp._LOG = _LOG` 注入实现层；实现层保留 `if "_LOG" not in dir() or not _LOG:` 兜底 |
| **统一分发入口** | `post(toolName, dataSet, envSet)` → 返回 `{toolName, errCode, rtnData}` |
| **注册表** | `toolPathMap`（`toolName → funcXxx`）定义在 `mcpPost.py` **文件末尾**，与 Flask 侧 `urlPathMap` 同构 |
| **处理函数签名** | `funcXxx(CMD, dataSet)` → 返回 `{errCode, rtnData}` |
| **错误码** | `B0` 成功 / `BA` 参数缺失 / `BT` 无工具权限 / `ERR_NOCMD` 未知工具 / `ERROR` 异常 |
| **辅助件** | `_truncateResult(dataList, limit)`（防 token 超限）、`_normalizeData(dataSet)`（清理空参） |
| **懒加载单例** | `getChServer(sessionID)` 缓存 `comCh.ChServer` 实例并注入 `comCh._LOG = _LOG` |
| **REST 客户端** | `common/chServerCommon.py` 对标 `ylwzStockCommon.py`：`CH_API_URL_DATA`（`cmd → {method, description, host, port, headers, urlPath, params}`，`urlPath` 形如 `chapi/<cmd>`）、`QUERY_CMD_LIST`、`class ChServer`（`getRequest`/`postRequest`/`query`/`handleQueryResult`/`getRestNum`/`getNext` + 类型化业务方法） |

### 9.6.3 已交付文件清单

| # | 文件 | 行数 | 对标 | 内容 |
|---|---|---|---|---|
| 1 | `code/src/mcpapi/__init__.py` | 8 | `mcpapi/__init__.py` | 包声明（仅文件头注释） |
| 2 | `code/src/mcpapi/mcp_entry.py` | ≈430 | `mcpapi/mcp_entry.py` | 入口层：FastMCP + `AuthSettings` + `streamable_http_app()` + 8 tool + 3 resource + uvicorn 启动 |
| 3 | `code/src/mcpapi/mcpPost.py` | ≈620 | `mcpapi/mcpPost.py` | 实现层：`CHAccessToken` / `CHTokenVerifier` / `_genAllowedTools` / `getChServer` / `post` / `_truncateResult` / `_normalizeData` / `_extractList` / `_genPageRtnData` / 8 个 `funcXxx` / `toolPathMap` |
| 4 | `code/src/mcpapi/restore_mcp.sh` | 13 | `mcpapi/restore_mcp.sh` | 重启脚本（`HOME_DIR=/data/contenthubapp`，可配置） |
| 5 | `code/src/config/mcpConfig.py` | ≈75 | `config/mcpConfig.py` | MCP 服务名/版本/host/port/transport、CH_SERVER_HOST/PORT/ROOT_PATH、SESSION_ID 环境变量、TOOL_RESULT_LIMIT、QUERY_DEFAULT_LIMIT、HTTP 超时、MCP_AUTH_* |
| 6 | `code/src/common/chServerCommon.py` | ≈390 | `common/ylwzStockCommon.py` | REST 客户端：`CH_API_URL_DATA`（8 条：7 个查询命令 + `generalnext`）、`QUERY_CMD_LIST`、`class ChServer` + 7 个类型化查询方法 |

### 9.6.4 工具与资源清单

**8 个只读 tool**（`mcp_entry.py` 声明 → `mcpPost.py` 处理 → 下游 CMD）

| # | tool 名 | 处理函数 | 下游 CMD（`chapi/<cmd>`） |
|---|---|---|---|
| 1 | `search_topics` | `funcSearchTopics` | `topicqry` |
| 2 | `get_topic` | `funcGetTopic` | `topicqry` |
| 3 | `list_topic_assets` | `funcListTopicAssets` | `topicassetqry` |
| 4 | `list_layouts` | `funcListLayouts` | `layoutqry` |
| 5 | `list_platforms` | `funcListPlatforms` | `platformqry` |
| 6 | `get_render_job` | `funcGetRenderJob` | `renderjobqry` |
| 7 | `list_artifacts` | `funcListArtifacts` | `artifactqry` |
| 8 | `list_publish_records` | `funcListPublishRecords` | `publishrecordqry` |

**3 个只读 resource**（参考实现无此形态，为按同一两层模式新增的扩展项）

| # | URI | 复用 tool |
|---|---|---|
| 1 | `contenthub://platforms` | `list_platforms` |
| 2 | `contenthub://layouts` | `list_layouts` |
| 3 | `contenthub://topic/{topic_id}` | `get_topic` |

### 9.6.5 前置缺口与当前验证状态

**已通过**：5 个 Python 文件全部通过 `python -m py_compile` 语法编译校验（Python 3.13.11）。

**尚不可运行**（前置缺口，均由 Phase 0/1 产出）：

| # | 缺口 | 由谁补齐 |
|---|---|---|
| 1 | `config/basicSettings.py`（含 `_SYS` / `_DEBUG` / `ROLE_CMD_LIST` / `MCP_TOOL_LIST`） | Phase 0 · T3 |
| 2 | `common/globalDefinition.py`（需含 3 个 MCP 日志常量） | Phase 0 · T2（纯追加） |
| 3 | `common/miscCommon.py`、`common/redisCommon.py`（`getSessionInfo`） | Phase 0 · T2 |
| 4 | `/chapi/<urlPath>` 端点与 `generalnext` | Phase 1 · P1-1 / P1-2 |
| 5 | Python 依赖 `mcp`（FastMCP + `mcp.server.auth.*`）、`uvicorn`、`pydantic` | Phase 0 · 依赖清单 |

> **联调顺序**：Phase 0 T2/T3 完成 → 校验 import 链 → P1-1/P1-2 提供 `/chapi` 与 `generalnext` → 启动 `mcp_entry.py` → 执行 9.6.6 冒烟清单。

### 9.6.6 冒烟与验收清单（前置就绪后执行）

| # | 检查项 | 期望 |
|---|---|---|
| 1 | 无 token 调用任一 tool | 被 SDK 鉴权中间件拒绝（401） |
| 2 | 无效 token（Redis 无会话） | 被拒绝 |
| 3 | 有效 token 且角色在 `ROLE_CMD_LIST` | 放行 |
| 4 | 未知 tool 名 | `errCode = ERR_NOCMD` |
| 5 | `MCP_TOOL_LIST` 限制角色仅 `list_platforms` 时调用 `search_topics` | `errCode = BT` |
| 6 | 缺必填参（如 `list_topic_assets` 不传 `topic_id`） | `errCode = BA` |
| 7 | 正常查询 | `errCode = B0`，`rtnData` 含 `total`/`returned`/`data` |
| 8 | 3 个 resource 读取 | 返回合法 JSON 字符串 |
| 9 | 下游异常（`/chapi` 不可达） | `errCode = ERROR` 且日志含 `PID/toolName` |
| 10 | 结果超 `TOOL_RESULT_LIMIT` | `returned < total`，已截断 |

### 9.6.7 与参考实现的差异说明（4 处，均有理由）

| # | 差异 | 原因 |
|---|---|---|
| 1 | `getChServer(sessionID)` **按 sessionID 分池**（参考为单一全局单例） | 使下游 `/chapi` 能按真实调用者做 `ROLE_CMD_LIST` 权限裁剪，而非统一使用默认账号会话 |
| 2 | `post()` 中**把调用者 token 以 `_sessionID` 注入 `dataSet`** 供处理函数取用（参考不传） | 保持处理函数签名 `(CMD, dataSet)` 不变的前提下传递身份 |
| 3 | 新增 `_extractList` / `_genPageRtnData`，把下游分页缓冲体（`{indexKey,total,beginNum,endNum,data}`）解析为 `total/returned/data` | 参考实现直接把整包 dict 交给 `_truncateResult`，非 list 时截断失效；本项目修正为真实截断 |
| 4 | 新增可选**工具级授权** `MCP_TOOL_LIST`（未配置时退化为参考行为，不限制） | 参考仅做角色粗校验，任何有效 token 可调用全部工具 |

### 9.6.8 后续（P3-4b，延至 v1.1）

写入类（`create_topic` / `update_topic`）、渲染类（`render_topic`）、导出类（`export_asset_pack`）、投递类（`push_wechat_draft`）tool。落地时**必须**补齐：幂等键、二次确认、「推送 ≠ 发布」红线校验、审计留痕，并**不得**引入小红书自动发布路径。

---

## 9.7 支线执行优先级裁定表

| 情形 | 处置 |
|---|---|
| 人力充足（可按 5 人天/周投入） | S2（M1→M2）与 S1（配置+适配器）**同时并行**，均落在 Phase 0 窗口 |
| 人力受限（只能保一条） | **优先 S2**（S2 是 C1 强前置，S1 不阻塞任何主干任务） |
| 主干出现延期 | **支线立即让位**，仅保留「S2-M1 骨架 + S1-1 配置结构」这两项不可逆前置工作 |
| C1 已开工但 S2 未就绪 | 立即暂停 C1，先补 S2-M1/M2；**不允许**在 `chAPIPost.py` 上直接堆代码 |

---

# 10. 附录

## 10.1 附录 A · 里程碑一览

| 里程碑 | 时点 | 一句话验收 |
|---|---|---|
| M0 冻结 | 第 2 周末 | 12 表定义 + 生成器 + 文件抽象层就绪 |
| M1 可看 | 第 6 周末 | 主题可建、素材可传、版式可预览 |
| M2 可用 | 第 9 周末 | 双平台合规产物可渲染 |
| M3 可运营 | 第 12 周末 | 可投递 + MCP 可编排 |
| v1.0 | 第 12 周末 + 2 周观察 | 真实账号无事故运营 2 周 |

## 10.2 附录 B · 关键接口约定速查

| 约定 | 内容 |
|---|---|
| 数据库访问 | 只经 `common/mysqlCommon.py`，禁裸 SQL |
| 文件访问 | 只经 `common/fileStorageCommon.py`，禁厂商分支 |
| 时间格式 | `misc.getTime()` → 14 位 `YYYYMMDDHHMMSS`；时间列 `VARCHAR(16)` |
| 报文格式 | `comFC.rtnMSG(errCode, field, lang, msgKey)` → `{"MSG":{"errCode","content"},"msgKey"}` |
| 摘要 | `comFC.genDigest(d1..d5)` → MD5 hexdigest（含固定盐） |
| 文件引用 | 库内只存 `fileID`，URL 由后端出参转换（`fillFileUrls`） |
| 幂等 | 唯一键拼接单列 + UNIQUE；写入走 `upsertByUniqueKey` |
| 分页 | `indexKey` 缓冲（`genBufferIndexKey` 派生）+ `beginNum/endNum` 切片；默认缓冲 900 秒 |
| 可空数值 | 「0 = 未设置」 |
| 端点命名 | `{表名去 ch_ 去下划线}{add/del/modify/qry}` |
| 业务端点 | `topicrender` / `artifactpack` / `publishpush` / `publishcheck` / `accounthealth` / `mcpinvoke` |
| MCP 分发 | `post(toolName, dataSet, envSet)` → `{toolName, errCode, rtnData}`；注册表 `toolPathMap` 定义在 `mcpPost.py` 末尾；处理函数签名 `funcXxx(CMD, dataSet)` → `{errCode, rtnData}` |
| MCP 错误码 | `B0` 成功 / `BA` 参数缺失 / `BT` 无工具权限 / `ERR_NOCMD` 未知工具 / `ERROR` 异常 |
| MCP 鉴权 | FastMCP `token_verifier`（`CHTokenVerifier`）→ Redis session（`comDB.getSessionInfo`）+ `ROLE_CMD_LIST` 角色校验；可选 `MCP_TOOL_LIST` 工具级授权 |
| MCP 传输 | streamable-http（`mcp.streamable_http_app()` + uvicorn，默认端口 8890） |
| MCP 下游 | 经 `common/chServerCommon.py`（`class ChServer`）调用 `/chapi`，`urlPath` 形如 `chapi/<cmd>` |
| MCP 返回体 | 查询类统一 `{total, returned, data}` 三件套；`_truncateResult` 按 `TOOL_RESULT_LIMIT` 截断防 token 超限 |
| 版式类型 | `layoutType` ∈ `stack`（上下）/ `carousel`（左右轮播，项目自实现交互）/ `longimage`（长图拼接）/ `swipe`（左右滑动浏览，平台原生，仅 `xiaohongshu`）；`carousel` 与 `swipe` 禁止合并或互相替代（见 2.6 节） |
| 小红书多图规格 | 张数 ≤18、整篇单一比例（首选 1080×1440）、单张 ≤20 MB、格式 JPG/PNG、长图须按 1080×1440 切分 |

## 10.3 附录 C · 术语表

| 术语 | 含义 |
|---|---|
| **主题（Topic）** | 本项目的核心内容资产，聚合标题、详述、附图、图注、来源、时期等结构化信息 |
| **版式（Layout）** | 描述内容如何被编排的模板定义，对应 `ch_layout`，如 `stack_v1` / `carousel_v1` / `longimage_v1` / `swipe_v1` |
| **版式类型（layoutType）** | `stack` 上下展示 / `carousel` 左右轮播（**项目自实现交互**）/ `longimage` 长图拼接 / `swipe` 左右滑动浏览（**平台原生交互**，仅小红书）。见 2.6 节 |
| **左右滑动（swipe）** | 小红书图文笔记在 App 内的**原生**多图浏览交互：在图片显示区域内手指左右轻扫逐张切换；项目侧只负责按 1080×1440 切分、排序、统一比例，不自实现交互 |
| **产物（Artifact）** | 渲染的产出文件，对应 `ch_artifact`，可为 HTML / PNG / ZIP / JSON |
| **投递（Deliver）** | 把产物送往平台的动作；**不等于发布**（发布需人工在平台后台确认） |
| **素材包（Asset Pack）** | 小红书场景的交付形态：图集 PNG + 标题 + 正文 + 话题标签 + manifest，打包为 ZIP |
| **fileID** | 文件在后端的唯一标识（OSS/COS 为对象键，SELFFILE 为分片路径），库内只存 fileID |
| **draft_box** | 交付模式：推送到平台草稿箱 |
| **asset_pack** | 交付模式：仅导出素材包，不做任何投递 |
| **api_publish** | 交付模式：调用平台正式发布接口（仅认证企业号可用，需人工确认） |
| **contentHash** | 文件原始字节的 sha256，用于内容级去重 |
| **幂等键** | 拼接单列唯一键，用于防止重复写入 / 重复投递 |
| `_SYS` | 环境选择开关，取值 `local / server_01 / server_02 / test_server / home` |
| `FILE_SYSTEM_MODE` | 文件后端选择，取值 `ALIOSS / TENCENT / SELFFILE` |
| R1 / R2 / R3 | 三条工程红线（定义文件唯一数据源 / 配置驱动后端 / 只走 `readFromFile`） |
| D1–D4 | 基线实测发现的四处与 v3 文档表述的差异（见 3.2.2） |

## 10.4 附录 D · 文档溯源

| 本计划章节 | 主要来源 |
|---|---|
| 1.1–1.3 定位与结论 | `content-hub-调研与开发计划.html` 核心研判、§1.6 市场空白与定位结论 |
| 1.4 范围与不做清单 | `调研与开发计划.html` §2.5 优先级排序（明确不做）；`content-hub-开发计划v3.html` §1.1–1.3 |
| 1.5 三条红线 | `content-hub-Phase0-任务清单.md`「三条红线」 |
| 2.1–2.3 业务链路与模块 | `v3` §2.3、§3 模块划分与依赖 |
| 2.4 平台能力矩阵 | `调研与开发计划.html` §1 平台发布能力边界（实测口径） |
| 3.1 分层架构 | `v3` §2.1 |
| 3.2 复用清单 | `v3` §2.2 + **本次对 `museum/code/src` 的只读实测核实** |
| 3.3 文件系统抽象 | `v3` §4（含 4.2–4.8）+ 实测签名对照 |
| 3.4 数据库设计 | `v3` §5.1–5.5；字段全文见 `content-hub-Phase0-任务清单.md` §T4 |
| 3.5 CRUD 生成方案 | `v3` §6.1–6.6 + 生成器源码实测（坑 1–4） |
| 3.6 技术选型 | `v3` §2.1 架构图（Flask / Vue3 / Jinja2 / Playwright）；`调研` §2.1 作为备选参考 |
| 3.7 目录结构 | `v3` §7（含新增 `test_storage.py`） |
| 4 阶段与里程碑 | `v3` §8；里程碑验收标准参照 `调研` §2.4 里程碑一览 |
| 5 任务清单与工时 | `content-hub-Phase0-任务清单.md` T1–T9（原文保留验收命令）；Phase 1–3 为本次分解 |
| 6 依赖与风险 | `v3` §3 关键依赖路径、§9 风险登记册；`调研` §2.3 依赖关系、§4 风险登记册 |
| 7 测试与验收 | `content-hub-Phase0-任务清单.md` §T9 验收总表；`调研` §3 建议补充功能；本计划补充 L1–L6 分层策略与 DoD |
| 8 部署与上线 | `v3` §4.2（`_SYS` 环境映射）、§7（进程入口）；本计划补充部署拓扑、检查清单、回滚与监控 |
| 9 支线任务规划 | `plan/ylwz文件服务多Bucket.md`、`plan/chAPIPost分拆方案.md`；两条支线的事实依据均来自对 `ylwzProject/museum/code/src` 的只读实测核实 |
| 9.6 C7 · MCP 模块实现 | 参考实现 `gitData/stock_rotation_strategy/src/mcpapi`（`mcp_entry.py` / `mcpPost.py` / `restore_mcp.sh`）、`config/mcpConfig.py`、`common/ylwzStockCommon.py`；接口约定参照 `museum/code/src/main/museumAPI.py` 的 `/museumapi/<urlPath>` 路由范式 |
| 2.6 版式类型与交互方式 / 7.8 素材包合规 | 小红书多图能力由**第三方资料交叉印证**（2026 年小红书配图规范类文章、创作者工具站、用户操作指南）：单篇 ≤18 张、整篇单一比例、首选 1080×1440 (3:4)、单张 ≤20 MB、App 内**原生左右滑动逐张切换**（须在图片区域内滑动，老版本 App 需 8.0+）、超长图不得直接上传须切分。**官方后台为登录态、无公开稳定文档，故标注为待平台实测复核** |
| UI 设计规范 | `plan/UI/contentHub UI 设计.md`（v1.0 / 2026-09-18）；工程基线 `ylwzProject/museum/code/webserver`（Vue3 + Element Plus + Tailwind 暗色后台）；结构范本 `chin_mindgram/plan/UI/Mindgram-UI设计规范.md`。本计划 3.6/3.7 与附录 E 已据其裁定同步（Element Plus、状态机 5 态、前端落 `code/webserver/`） |

## 10.5 附录 E · 待拍板事项

以下决策会直接影响 Phase 0 的落地细节，建议在开工前确认；若未确认，本计划按「默认建议」执行。

| # | 事项 | 选项 | 默认建议 |
|---|---|---|---|
| 1 | 文件服务接入模式 | A. 统一走 HTTP 文件服务；B. Web 走 A + worker 走进程内直连 | **B 混合方案**（Web 不持 AK，worker 低延迟） |
| 2 | 表名前缀 | `ch_` / `mc_` / `ct_` | **`ch_`**（contentHub，且 Phase 0 任务清单已按此编写） |
| 3 | 目标账号主体类型 | 个人订阅号 / 认证企业订阅号 / 认证服务号 | 按实际资质确定；**无论哪种，v1.0 均只承诺草稿箱投递** |
| 4 | 小红书是否接受不自动发布 | 接受 / 不接受 | **接受**（合规底线，非技术取舍） |
| 5 | 是否引入本地投递代理（浏览器扩展 / CLI） | 引入 / 不引入 | **v1.0 不引入**；列入 Phase 4 评估（可解决个人号 Cookie 态投递，但增加客户端形态） |
| 6 | 是否复用 Headless CMS（Directus / Payload） | 复用 / 自研 | **自研**（本计划已基于 ylwz 生成器链路，替换成本高于收益） |
| 7 | MCP 传输方式 | streamable-http / SSE / stdio | **streamable-http**（已拍板，对齐参考实现 `stock_rotation_strategy/src/mcpapi`） |
| 8 | 前端 UI 库 | Element Plus / Naive UI / 自研 | **Element Plus**（**已裁定 2026-09-18**：与工程基线 `museum/webserver` 同源，组件可直接复用、零迁移成本） |
| 17 | 主题状态机基准 | UI 文档更细粒度（含 `LAYOUT_READY` / `VERIFIED`）/ 数据库现有 5 态 | **以数据库为准，5 态**：`DRAFT / RENDERING / RENDERED / PUBLISHED / ARCHIVED`（**已裁定 2026-09-18**）。「已选版式 / 已校验」改由 UI 完成度指示器表达，不占用状态位；UI 文档已同步 |
| 18 | UI 规范与前端工程落位 | 单列文档 / 并入主计划 | **单列** `plan/UI/contentHub UI 设计.md`（已交付），前端工程落 `code/webserver/` |
| 19 | **移动端是否有真实使用场景**（源自 Ardot 提问 Q-3） | ① 有：保留 XS/SM 断点与降级矩阵 ② 无：简化为桌面优先，XS/SM 仅声明不支持 | **待拍板**。建议 ②：本项目为内部运营工具、主计划无任何移动端要求；按 UI 文档 8.4 保留「只读 + 轻操作」的降级声明即可，不做 XS/SM 高保真稿，可省一笔设计投入 |
| 9 | **支线 S1**（文件服务多 Bucket）执行窗口 | 并行（与 Phase 0 · T7 同步）/ 后续 | **并行**；可降级为「仅配置结构 + 三适配器」3.5 人天，其余顺延 |
| 10 | **支线 S2**（chAPIPost 拆分）执行窗口 | 并行（C1 之前）/ 后续 | **并行且为 C1 强前置**：S2-M2（账号域 + 主流程）必须在 C1 开工前收口 |
| 11 | 支线聚合方式（S2） | 显式 `getUrlPathMap()` / `from subfunc import *` | **显式**（可做 CMD 冲突与配置完整性校验） |
| 12 | 错误消息模块抽取（S2） | 立刻抽 `common/errMsgCommon.py` / 延后 | **立刻**（保留 re-export，25 个引用方零改动） |
| 13 | **MCP 鉴权模型** | Redis session + `ROLE_CMD_LIST` / 独立 `ch_mcp_token` 表 | **沿用 Redis session**（已拍板；`ch_mcp_token` 本期不参与鉴权，保留建表待后续独立吊销） |
| 14 | **MCP 工具集范围** | 只读 / 只读 + 写入 / 全量 | **只读**（已拍板；写入与渲染/投递类 tool 延至 v1.1，见 9.6.8） |
| 15 | **MCP 工具级授权** | 引入 `MCP_TOOL_LIST` / 不引入 | **引入**（否则任何有效 token 可调用全部工具） |
| 16 | `ch_mcp_token` 表去留 | 保留建表 / 移除 | **保留建表**（本期不写校验链路，为后续独立吊销预留） |

---

> **文档维护说明**：本计划为 v1.0 基线。后续每次范围或架构变更，须同步更新第 4 章（排期）、第 6 章（风险）与附录 E（待拍板事项），并保留变更记录。
>
> 编写日期：2026-09-17 ｜ 依据：`plan/content-hub-调研与开发计划.html`、`plan/content-hub-开发计划v3.html`、`plan/content-hub-Phase0-任务清单.md`，并对 `ylwzProject/museum/code/src` 做只读实测核实。
