# contentHub 工程说明（code/src）

> 本文件是 `code/src` 的工程契约说明，对应主计划 `plan/contentHub开发计划.md` 的 **SP1 · Phase 0 数据库链路收口**（里程碑 M0 的数据库部分）、
> **SP1.5 · S2 HTTP 接入层拆分**（`plan/chAPIPost分拆方案.md`，C1 的强前置）、**SP3a · Phase 2 · C5 平台适配层 + 微信产物**（里程碑 M2 第一块）、
> **SP3b · Phase 2 · C5 小红书产物渲染**（里程碑 M2 第二块，主计划 P2-3：`engine/htmlToImage.py` Playwright 截图 + 小红书适配器）、
> **SP3c · Phase 2 · C8 合规校验 + 产物台账 + 渲染任务化**（**里程碑 M2 收口**，主计划 2.2 / 2.6.3 / 3.4.5 / P2-6 / P2-7 / P2-8：`processor/complianceService.py` + `ch_artifact` 台账 + `ch_render_job` 任务化 + `schedule/renderWorker.py` + `publishcheck`）
> 与 **SP4a · Phase 3 · C6 公众号草稿投递链路**（**里程碑 M3 第一块**，主计划 1.3 结论一「推送≠发布」/ 2.4 平台能力矩阵 / 2.5 适配器设计要点 / 5.5 P3-1·P3-3·P3-5 / 6.4 R-03·R-04·R-17·R-19 / 7.2 U-13·U-14 / 7.5 C6 DoD / 8.4 上线检查：`processor/publishService.py` + `processor/auditService.py` + `common/credentialCipher.py` + `wechatMp.deliver` + `publishpush`）。
> **SP4b · Phase 3 · 素材包 ZIP + MCP 接入 + 凭据巡检**（**里程碑 M3 第二块**，主计划 1.4.1 / 5.5 P3-2·P3-4·P3-6 / 7.8 素材包合规 12 项 / 9.6 MCP 十项冒烟：`processor/artifactService.py` + `assetApi.artifactpack` + `mcpApi.mcpinvoke` + `schedule/credentialCheck.py` + `accountApi.accounthealth` 接线 + G2·G3 错误码 + `mcp<2` 依赖口径）。
> 与 **SP4c · Phase 3 · 归档清理 + 监控告警 + 巡检守护化**（**里程碑 M3 第三块**，主计划 5.5 P3-7·P3-8 / 3.4.6 审计日志归档 / 6.4 R-23 产物存储膨胀 / 8.7 监控告警阈值表：`schedule/archive.py` + `chmonitor/`（原 `monitor/`，本轮重命名） + `monitor/`（由 `museum/code/src/monitor` 迁移改造为 contentHub 口径） + `schedule/credentialCheck.py` 守护化 + `config/opsSettings.py`；★ 破坏性操作默认 dry-run）。
> 权威设计文档仍是 `plan/contentHub开发计划.md`；本文件只记录「本工程实际落地形态」与「已核实结论」。

---

## 1. SP1 + SP1.5 交付清单与验收结果

| # | 交付物 | 位置 | 状态 |
|---|---|---|---|
| 1 | 读写分离连接封装 | `common/mysqlHandle.py` | 原样复用 museum 基线，未改逻辑 |
| 2 | 数据库连接配置（含跳过直连开关） | `config/mysqlSettings.py` | 新增，按 `_SYS` 映射，口令走环境变量 |
| 3 | 公众号配置空结构 | `config/wechatSettings.py` | 新增，敏感项走环境变量，不落代码库 |
| 4 | MCP 日志常量补齐 | `common/globalDefinition.py` | 纯追加 `_DEF_LOG_CH_MCP_TITLE` / `_DEF_LOG_CH_MCP_NAME` / `_DEF_LOG_CH_TEST_NAME` |
| 5 | 12 张表定义文件（唯一数据源） | `database/ch_*.txt` | 新增，逐字取自 Phase0 任务清单 §T4 |
| 6 | 代码生成器 | `database/mysqlCodeGenerator.py` | 原样复用，未修改 |
| 7 | 生成产物 | `database/auto_generated/auto_gen_code_ch_*.py` + `word_table_ch_*.csv` | 12 + 12 |
| 8 | 全库读写唯一入口 | `common/mysqlCommon.py` | 新建（手写段 + 生成段，3499+ 行） |
| 9 | 跨域业务公共件 | `common/chCommon.py` | 新增（幂等写入 + fileID 转 URL） |
| 10 | 建表脚本 | `tools/initTables.py` | 新增（仅 `create_*`，无任何 `drop_*`） |
| 11 | 种子脚本 | `tools/initSeed.py` | 新增（平台 3 条 + 版式 4 条，幂等） |
| 12 | 文件门面三后端联调脚本 | `tools/test_storage.py` | 新增（交付脚本，未执行） |
| 13 | 批量生成脚本 | `tools/genTableCode.ps1` | 新增（含表名陷阱说明） |
| 14 | 产物合并工具 | `tools/mergeMysqlCommon.py` | 新增（可重复执行，手写段与生成段物理隔离） |
| 15 | 静态验收脚本 | `test/test_ch_phase0_static.py` | 新增，14 项全过 |
| 16 | 运行依赖清单 | `requirements.txt` | 新增 |

**SP1.5（S2 HTTP 接入层拆分）追加交付物**：

| # | 交付物 | 位置 | 状态 |
|---|---|---|---|
| 17 | HTTP 门面（Flask，路由 `/chapi/<urlPath>`） | `main/chAPI.py` | 新增 |
| 18 | 瘦入口（230 行，≤400 上限）+ `post()` 主流程 | `main/chAPIPost.py` | 新增 |
| 19 | 接入层拆分包（12 文件） | `main/subfunc/` | 新增（`__init__.py` 聚合器三道校验 / `context.py` / `apiCommon.py` / `accountSvcClient.py` / `accountApi.py` / `crudApi.py` / 6 个业务域） |
| 20 | 48 个 CRUD 处理器装配件（5755 行，生成件豁免行数上限）+ 可重复装配工具 | `main/subfunc/crudApi.py` / `tools/mergeCrudApi.py` | 新增（生成区与手写头部用标记物理隔离） |
| 21 | 账号服务 HTTP 客户端（GAA0/A3A0/AIA0/AEA0 + 低层转发） | `common/accountClient.py` | 新增 |
| 22 | 错误消息独立模块（`contenthub` 消息键 + `applicationMsgKey` 别名归一并补 `contenthub`）；`funcCommon.py` 改为 re-export | `common/errMsgCommon.py` / `common/funcCommon.py` | 新增 + 改造（既有 25 个引用方零改动） |
| 23 | D3 分页缓冲移植（三函数 + 生成件所需开关与辅助） | `common/queryBufferCommon.py` | 新增 |
| 24 | Web 入口日志常量 | `common/globalDefinition.py` | 追加 `_DEF_LOG_CH_WEBAPI_TITLE` / `_DEF_LOG_CH_WEB_API_NAME` |
| 25 | 静态验收脚本扩展（S13–S19） | `test/test_ch_phase0_static.py` | 改造 |
| 26 | 移植表: 用户账号主表 USER_BASIC（手写段：8 函数 + `genOrList`；定义文件 `database/userBasic.txt`） | `common/mysqlCommon.py` | 新增（见 §11） |
| 27 | 移植表: 微信支付/退款流水 weixin_pay（生成段 7 函数 + 手写 `query_weixin_pay`） | `common/mysqlCommon.py` + `database/weixin_pay.txt` + 产物 | 新增（见 §11） |
| 28 | 建表脚本登记两张移植表 | `tools/initTables.py` | 改造 |

**SP2a（Phase 1 · C2 主题管理）追加交付物**：

| # | 交付物 | 位置 | 状态 |
|---|---|---|---|
| 29 | 业务处理器层包（分层契约声明） | `processor/__init__.py` | 新增 |
| 30 | C2 主题管理业务服务（全字段 CRUD + 字段区间校验 + 状态机 + `wordCount` + `topicCode` 幂等 + 详述超长转存 + 版本快照） | `processor/topicService.py` | 新增 |
| 31 | 主题域接入端点（接管 `topic{add/del/modify/qry}` + `topicversion{...}` 共 8 条；`topicrender` 仍占位） | `main/subfunc/topicApi.py` | 改造（替换占位） |
| 32 | 装配工具支持「业务域接管排除」并重生成 crudApi（48 → 40） | `tools/mergeCrudApi.py` / `main/subfunc/crudApi.py` | 改造 |
| 33 | `ch_topic_version` short 列补 `diffNote/ownerID`（版本列表接口避免拉 `snapshotJson` 大字段） | `common/mysqlCommon.py` | 改造（手写段） |
| 34 | 静态验收脚本扩展（S15 调整为 40 CMD / S18 topic 域 9 条 / 新增 S20；S12 纳入 topicService） | `test/test_ch_phase0_static.py` | 改造 |

**SP2b（Phase 1 · C3 素材图库）追加交付物**：

| # | 交付物 | 位置 | 状态 |
|---|---|---|---|
| 35 | C3 素材图库业务服务（`contentHash` 内容级去重 + 规格裁剪 + EXIF 剥离 + 缩略图 + `fileSystem`/`storageBucket` 快照 + 素材与附图 CRUD） | `processor/assetService.py` | 新增 |
| 36 | 素材域接入端点（接管 `asset{add/del/modify/qry}` + `topicasset{...}` 共 8 条；`artifactpack` 仍占位） | `main/subfunc/assetApi.py` | 改造（替换占位） |
| 37 | 装配工具支持「素材域接管排除」并重生成 crudApi（40 → 32） | `tools/mergeCrudApi.py` / `main/subfunc/crudApi.py` | 改造 |
| 38 | 静态验收脚本扩展（S15 调整为 32 CMD / S18 asset 域 9 条 / 新增 S21；S12 纳入 assetService） | `test/test_ch_phase0_static.py` | 改造 |

**SP2c（Phase 1 · C4 版式引擎，里程碑 M1 最后一块）追加交付物**：

| # | 交付物 | 位置 | 状态 |
|---|---|---|---|
| 39 | 渲染引擎层包（分层契约声明：接入层→业务层→引擎层→公共层） | `engine/__init__.py` | 新增 |
| 40 | 版式调度引擎（唯一渲染入口：读 ch_layout → 注入 specJson → Jinja2 渲染 → `{outputKind, content, meta}`；按 layoutType 分派 4 类；模板缺失/渲染异常返回 E0–E3） | `engine/layoutEngine.py` | 新增 |
| 41 | 渲染期图像处理公共件（封面 900×500 / 卡片 1080×1440 统一 / 长图切片；与 assetService 的入库前处理明确分工） | `engine/imageProc.py` | 新增 |
| 42 | 4 套内置版式模板 + 共用骨架 | `engine/templates/{stack_v1,carousel_v1,longimage_v1,swipe_v1}/index.html` + `engine/templates/partials/base.html` | 新增 |
| 43 | 站内预览页（微信手机框 / 小红书手机框模拟） | `engine/templates/preview/wechat_mp.html` / `xiaohongshu.html` | 新增 |
| 44 | 渲染业务编排（「业务层→引擎层」唯一连接点：取主题 + 附图 → 引擎渲染；同步渲染） | `processor/renderService.py` | 新增 |
| 45 | 渲染域接入端点（接管 `topicrender`；主题域 9→8、渲染域 0→1；沿用 `_serviceResult` 范式） | `main/subfunc/renderApi.py` + `main/subfunc/topicApi.py` | 改造（归属迁移） |
| 46 | 静态验收脚本扩展（新增 S22；S18 调整为 render 域 1 条；S20 调整为 topic 域 8 条；S11/S1 纳入 engine） | `test/test_ch_phase0_static.py` | 改造 |
| 47 | 真实渲染冒烟脚本（不连库；4 套模板断言 + 产物落 `code/data/preview/`） | `test/test_sp2c_render_smoke.py` | 新增 |

**SP3a（Phase 2 · C5 平台适配层 + 微信产物，里程碑 M2 第一块）追加交付物**：

| # | 交付物 | 位置 | 状态 |
|---|---|---|---|
| 48 | 平台适配层包（包声明 + 适配器工厂出口） | `processor/platformAdapter/__init__.py` | 新增 |
| 49 | 适配器抽象基类（契约五方法 + ch_platform 数据驱动规格校验 + `deliver` 显式未实现 + 适配器注册表） | `processor/platformAdapter/base.py` | 新增 |
| 50 | 微信公众号适配器（内联样式 HTML / 规格校验 / 草稿载荷清单 / 只读健康巡检） | `processor/platformAdapter/wechatMp.py` | 新增 |
| 51 | 通用适配器（HTML **复用 stack_v1 的降级实现** + Markdown/JSON 导出） | `processor/platformAdapter/generic.py` | 新增 |
| 52 | 微信内联化公共件（class 清洗 / `<style>` 下沉内联 / 外链图片统一出口 / carousel 交互降级） | `engine/inlineStyle.py` | 新增 |
| 53 | 渲染编排接入平台分支（`platform` 参数化 + `renderMode` sync/job→C2 + 只读 ch_platform） | `processor/renderService.py` | 改造 |
| 54 | 错误码扩段（contenthub E 段新增 `E4` = 外链图片需转存但凭据缺失） | `common/errMsgCommon.py` | 改造 |
| 55 | 静态验收脚本扩展（新增 S23） | `test/test_ch_phase0_static.py` | 改造 |
| 56 | 渲染冒烟扩展（wechat_mp / generic 平台产物断言） | `test/test_sp2c_render_smoke.py` | 改造 |

**SP3b（Phase 2 · C5 小红书产物渲染，里程碑 M2 第二块）追加交付物**：

| # | 交付物 | 位置 | 状态 |
|---|---|---|---|
| 57 | HTML→PNG 截图管线（单浏览器实例懒加载/串行、每卡片独立 page、headless、viewport=1080×1440、device_scale_factor 可配、字体预加载 `waitForFonts`、元素级/整页截图、长图切片复用 `imageProc`、产物落本地再经文件门面上传、E2/E3 错误码） | `engine/htmlToImage.py` | 新增 |
| 58 | 小红书平台适配器（`deliverMode=asset_pack`：swipe 卡片 / longimage 与 stack→长图切片 / carousel 显式不可用 C7；swipe 2.6.3 强制校验；package 素材包清单 + manifest 草稿；`deliver` 未实现；`checkHealth` 只读零网络） | `processor/platformAdapter/xiaohongshu.py` | 新增 |
| 59 | 适配器注册（`ADAPTER_MODULE_MAP` 增 `xiaohongshu`；小红书从 C7 迁移） | `processor/platformAdapter/base.py` / `__init__.py` | 改造 |
| 60 | 渲染编排出参扩展（多张 PNG 产物 `products`/`fileIDs` 经 `chCommon.fillFileUrls` 转换；选适配器一律走工厂，无平台硬编码） | `processor/renderService.py` | 改造 |
| 61 | 静态验收脚本扩展（新增 **S24** 小红书产物渲染；S23 同步纳管 xiaohongshu 适配器与 htmlToImage） | `test/test_ch_phase0_static.py` | 改造 |
| 62 | 渲染冒烟扩展为**真实截图断言**（swipe 张数/像素 1080×1440/seqNo/封面、longimage·stack 切片数=ceil(总高/sliceHeight) 且无超长单图、package 清单有序含 manifest、carousel 不可用、swipe 比例/张数强校验） | `test/test_sp2c_render_smoke.py` | 改造 |

**SP3c（Phase 2 · C8 合规校验 + 产物台账 + 渲染任务化，里程碑 M2 收口）追加交付物**：

| # | 交付物 | 位置 | 状态 |
|---|---|---|---|
| 63 | C8 合规校验服务（平台规格校验**复用 `base.checkPlatformSpec`** / swipe 专项**复用 `xiaohongshu.validateSwipeSpec`** + 超长整图前置拦截 / 敏感词命中+**偏移区间** / AI 内容标识 / 发布频率限流 **Redis 可降级** / 统一**问题清单**结构） | `processor/complianceService.py` | 新增 |
| 64 | 渲染任务化 + 产物台账（`ch_render_job` 状态机 PENDING→RUNNING→DONE/FAILED、`inputHash` 输入快照 sha256 **命中复用既有产物**、**同步渲染也建 job（终态 DONE）**使 `artifactKey` 的 jobID 有值、`renderMode=job` 提交即返回 `jobCode`+PENDING；`ch_artifact` 经 `chCommon.upsertByUniqueKey` 幂等写入、`artifactVer` 同 job 重渲染 +1） | `processor/renderService.py`（改造） | 改造 |
| 65 | 渲染任务常驻消费者（★ 首次创建 `schedule/` 包；单实例 + **串行**消费 PENDING、Redis 任务锁（可降级进程内锁）、异常落 FAILED、**不并发截图**、`__main__` 支持 `--once` 单次执行） | `schedule/__init__.py` + `schedule/renderWorker.py` | 新增 |
| 66 | `publishcheck` 端点落地（内部走 `complianceService.publishCheck`，沿用 `_serviceResult` 范式；**不新增 CMD**，端点总数仍 69） | `main/subfunc/complianceApi.py` | 改造（替换占位） |
| 67 | 静态验收脚本扩展（新增 **S25**：合规服务与台账——规格校验复用 base 而非重写 / swipe 专项齐备 / 问题清单结构 / 任务状态机 / `artifactKey` 幂等 / Redis 降级路径 / renderWorker 无并发截图 / 端点不新增） | `test/test_ch_phase0_static.py` | 改造 |
| 68 | 渲染冒烟扩展（不连库、**桩替换数据层/计数后端**）：敏感词偏移区间、`needAiLabelFlag=1` 缺标识被拦、规格违例命中问题清单且可定位、`artifactKey` 幂等键形态与 upsert 路径、job 非法跃迁被拒、`inputHash` 相同→复用命中、Redis 不可用→限流降级 | `test/test_sp2c_render_smoke.py` | 改造 |

**SP4a（Phase 3 · C6 公众号草稿投递链路，里程碑 M3 第一块）追加交付物**：

| # | 交付物 | 位置 | 状态 |
|---|---|---|---|
| 69 | 凭据加解密公共件（**AES-256-GCM**：`encrypt`/`decrypt`/`getMasterKey`/`isKeyConfigured`/`decodeKeyMaterial`/`maskSecret`/`sha256Hex`；密钥经**环境变量 `CH_CREDENTIAL_KEY`** 注入，密钥不入库/不入代码库；无密钥/解密失败一律显式 `CredentialCipherError(F0)`，**不静默降级**；`cryptography` 为函数内延迟导入，未安装时 import 不失败） | `common/credentialCipher.py` | 新增 |
| 70 | 审计留痕公共件（`ch_audit_log` 写入规范：actor/source/action/targetType/targetID/**payloadDigest(sha256)**/result/errMsg/costMs/ipAddr；`sanitizePayload` 对凭据类字段脱敏，**凭据明文不入审计**；写入失败不阻断主流程但记 error 日志） | `processor/auditService.py` | 新增 |
| 71 | C6 投递业务编排（★ 唯一对外产生副作用的模块）：通道判定（仅 `wechat_mp`；**小红书/通用显式拒绝**）→ 账号+凭据解密（`ch_account.credentialCipher/IV`）→ 产物 READY 前置 → **幂等**（`{artifactID}:{accountID}:{uuid4}`）→ **二次确认**（`confirmFlag`+`confirmToken`）→ 自动发布三重闸门 → **合规闸门（复用 `complianceService.publishCheck`）** → 取数 → **access_token 获取+缓存+提前刷新** → 渲染（注入转存回调）→ `package` → `deliver` → 发布记录全字段落库 + 审计；另含 `revokePublish`（60 秒撤销窗：`success`+`delFlag`+`pushedYMDHMS` 状态机，不依赖 Redis）与 `saveAccountCredential`（凭据加密写入 `ch_account`，明文不落库；**不暴露端点**） | `processor/publishService.py` | 新增 |
| 72 | 微信通道调用（`deliver` 实现 + 通道原语）：`fetchAccessToken` / `uploadArticleImage`(media/uploadimg) / `addMaterial`(material/add_material) / `addDraft`(draft/add) / `submitFreePublish`(freepublish/submit，**仅业务层三重闸门后调用**) / `downloadImageBytes` / `buildTransferFunc`；`package` 载荷扩展为含 `content`/`imageList`/`cover` | `processor/platformAdapter/wechatMp.py` | 改造 |
| 73 | 外链图片**真实转存分支**（补齐 §4 中 `E4` 的实现）：`resolveImageUrl`/`inlineHtml` 增加可选 `transferFunc`（回调由适配器/业务层注入，引擎层仅回调、**仍只依赖标准库**）；注入后就地替换 src 为平台地址，转存失败仍显式 `E4` | `engine/inlineStyle.py` | 改造 |
| 74 | `deliver` 契约说明更新（默认实现仍为 `C2`；SP4a 起仅 `wechat_mp(draft_box)` 覆写，小红书/通用继续显式未实现） | `processor/platformAdapter/base.py` | 改造 |
| 75 | `publishpush` 端点落地（沿用 `_serviceResult` 范式，内部走 `publishService.publishPush`；`action=push\|revoke` 同端点；**不新增 CMD，端点总数仍 69**） | `main/subfunc/publishApi.py` | 改造 |
| 76 | 投递配置项与依赖：`WECHAT_AUTO_PUBLISH_ENABLED`（默认 `False`）/ `WECHAT_REVOKE_WINDOW_SECONDS`(60) / `WECHAT_CREDENTIAL_KEY_ENV`；`cryptography>=42.0.0`；错误码扩段（contenthub F 段新增 `F4` 需人工二次确认 / `F5` 逾撤销窗 / `F6` 自动发布未开启，`F0` 语义扩为「无效/缺失/过期/解密失败」） | `config/wechatSettings.py` / `requirements.txt` / `common/errMsgCommon.py` | 改造 |
| 77 | 静态验收 **S26**（凭据加密不落明文 / 密钥来自环境变量 / 幂等键拼接 / 二次确认参数必填 / 撤销窗状态机 / 投递前必须过合规校验 / 审计字段齐备 / **静态扫描确认不存在小红书投递/发布代码路径**；S23 同步调整：wechat_mp 覆写 `deliver` 并移出零网络扫描） | `test/test_ch_phase0_static.py` | 改造 |
| 78 | 投递链路冒烟扩展（**9 项**：凭据加解密往返+无密钥行为 / `ch_account` 凭据读写闭环 / 外链真实转存分支 / 未过合规校验拒绝投递 / 二次确认必填 / 幂等二次提交被拒且不产生第二条记录 / 撤销窗内可撤销·逾窗拒绝·已撤销幂等 / 投递失败错误码+errmsg 落库+审计 FAIL / 自动发布默认关闭显式拒绝） | `test/test_sp2c_render_smoke.py` | 改造 |

**SP4b（Phase 3 · 素材包 ZIP + MCP 接入 + 凭据巡检，里程碑 M3 第二块）追加交付物**：

| # | 交付物 | 位置 | 状态 |
|---|---|---|---|
| 79 | C6 素材包 ZIP 导出业务服务（取 ch_artifact 的 `READY` 产物或调用方 `products` → **合规闸门** → 组装 ZIP（有序图片 `01_`/`02_`… + `title.txt` + `content.txt` + `manifest.json` + `COPYRIGHT.txt` + `RISK_NOTICE.txt` + `SWIPE_TIPS.txt`）→ 经文件门面上传返回 `fileID`；**未过校验一律不出包**；**只导出不投递**） | `processor/artifactService.py` | 新增 |
| 80 | `artifactpack` 端点落地（沿用 `_serviceResult` 范式，内部走 `artifactService.exportAssetPack`；素材域占位清空；**不新增 CMD**，端点总数仍 69） | `main/subfunc/assetApi.py` | 改造（替换占位） |
| 81 | MCP 薄入口 `mcpinvoke`（`/chapi` 侧：token 校验 G0 → **工具级授权 MCP_TOOL_LIST** G1 → `TOOL_CMD_MAP` 路由 G2 → 经 `common/chServerCommon.py` 转发下游 `/chapi` G3；**只转发、不承载 MCP 协议解析**） | `main/subfunc/mcpApi.py` | 改造（替换占位） |
| 82 | 凭据健康巡检（公众号只读探活：`ch_account` → 凭据解密 → `access_token` 换取 → `healthStatus ∈ {OK, EXPIRING, INVALID, UNKNOWN}` + `lastCheckYMDHMS`；到期阈值可配；R-03 分级告警（INFO/WARN/ERROR）；**小红书无凭据/不适用 → 跳过并说明**；Redis 锁可降级；`__main__` 单次执行） | `schedule/credentialCheck.py` | 新增 |
| 83 | `accounthealth` 端点内接入巡检（`action ∈ {check, refresh, probe}` → 触发巡检后再汇总；**不新增 CMD**） | `main/subfunc/accountApi.py` | 改造（同一处理函数内） |
| 84 | 错误码扩段（contenthub G 段新增 `G2` 未知 MCP 工具 / `G3` 下游服务调用失败；`G0`/`G1` 复用为“令牌无效/权限不足”） | `common/errMsgCommon.py` | 改造 |
| 85 | 依赖口径修正（`mcp>=1.2.0,<2`：mcp 2.x 已将 `FastMCP` 更名为 `MCPServer` 且鉴权/传输 API 变更，`mcpapi/` 为独立只读层不得改动，须锁 v1 才可启动） | `requirements.txt` | 改造 |
| 86 | 静态验收 **S27**（ZIP 结构与 7.8 项齐备 / **未过校验不得出包**（合规闸门先于 ZIP 组装）/ 合规规则单一来源不复写 / 只经 `fileStorageCommon`（无厂商分支）/ ★**静态扫描确认无投递·发布路径** / MCP 薄入口不承载协议解析 + `ROLE_CMD_LIST`·`MCP_TOOL_LIST` 校验落点 + G0–G3 / `mcpapi/` 既有 8 tool·3 resource 未改动 / **MCP 监听端口 8891（配置取值、禁硬编码）** / 巡检 healthStatus 四级与分级告警落点 / `accounthealth` 接入且不新增 CMD / 端点总数仍 69；S21 同步调整：素材域 `PLACEHOLDER_CMD_LIST` 由 `["artifactpack"]` 改为 `[]`） | `test/test_ch_phase0_static.py` | 改造 |
| 87 | 冒烟扩展（**7 项**）：真实产物打 ZIP（7.8 自动可判定项逐项断言 + 校验值复核 + 台账取数路径）/ 未过合规校验 → 拒绝出包（不上传）/ **MCP 监听端口与传输不变式（8891 / streamable-http）** / MCP 9.6.6 清单（★ **本轮不联调**：①② 未执行，③–⑩ 直调实现层逐条验证）/ 巡检 OK→EXPIRING→INVALID 三态与分级告警 / `accounthealth` 接入 | `test/test_sp2c_render_smoke.py` | 改造 |

**SP4c（Phase 3 · 归档清理 + 监控告警 + 巡检守护化，里程碑 M3 第三块）追加交付物**：

| # | 交付物 | 位置 | 状态 |
|---|---|---|---|
| 88 | 运维配置集中出口（审计保留期 / 分批大小 / 导出格式 / dry-run 确认开关 / 七项监控阈值 / 告警通道 / 周期表；**全部可经环境变量覆盖**，禁止散落硬编码） | `config/opsSettings.py` | 新增 |
| 89 | 归档清理（`ch_audit_log` 分批导出+删除 + `ch_artifact` 过期清理；★ **默认 dry-run**，真删须 `--execute` 或 `CH_ARCHIVE_EXECUTE=1`；★ **先导出上传成功才删除**；产物**先置 `EXPIRED` 再 `delFile`**；归档/清理动作写 `ch_audit_log`；Redis 锁可降级；`__main__` 单次执行） | `schedule/archive.py` | 新增 |
| 90 | 监控指标判定（七项：渲染失败率 / 投递成功率 / 队列积压 / 凭据健康 / 存储用量 / 定时任务最后成功 / 审计日增量；**纯函数**，阈值可配，输出 指标名/当前值/阈值/级别 INFO·WARN·ERROR/建议动作） | `chmonitor/metrics.py` | 新增 |
| 91 | 可插拔告警通道（日志通道默认；邮件 / 企微机器人为**占位实现**，★ 本轮**不发任何网络请求**，接口可注入；`networkRequest` 恒 `"0"`） | `chmonitor/alertChannel.py` | 新增 |
| 92 | 定时任务心跳（本地文件心跳，供「定时任务最后成功时间」指标；不引入新中间件） | `chmonitor/heartbeat.py` | 新增 |
| 93 | 监控采集与每日汇总（七项指标取数 + 降级 + 报告落 `code/data/monitor/` + WARN/ERROR 告警） | `chmonitor/monitorService.py` | 新增 |
| 94 | 每日巡检脚本（单次执行入口，`__main__`；供 cron / 计划任务调用） | `chmonitor/dailyCheck.py` | 新增 |
| 95 | 凭据巡检守护化（`--loop` 常驻 + `--interval`，与 `renderWorker` 同风格：单实例 + Redis 锁可降级；告警对接 `chmonitor/alertChannel`；刷新 `chmonitor` 心跳） | `schedule/credentialCheck.py` | 改造 |
| 96 | 运维定时运行脚本（Windows 计划任务用；默认 dry-run，`-Execute` 才真删） | `tools/runOpsJobs.ps1` | 新增 |
| 97 | `ch_artifact` 过期筛选（手写段 `query_ch_artifact` 增可选 `expireBeforeYMDHMS`，缺省 `""` 时条件自动跳过，既有调用零影响） | `common/mysqlCommon.py` | 改造 |
| 98 | 审计动作/对象常量（`archive.audit_log` / `archive.artifact_purge` + `ch_audit_log` / `ch_artifact`） | `processor/auditService.py` | 改造 |
| 99 | 静态验收 **S28**（归档 dry-run 为默认 / 先导出后删除顺序 / 分批与保留期可配 / 破坏性操作需显式确认 / 产物清理先置状态后删对象 / 审计留痕落点 / 监控七项指标与阈值可配 / 告警通道为占位且无网络调用 / 守护化入口存在且单实例；**S23 零网络扫描同步纳入 chmonitor/ 与 monitor/**） | `test/test_ch_phase0_static.py` | 改造 |
| 100 | 冒烟扩展（**5 项**：归档 dry-run 不产生任何导出/删除调用 + 显式执行时先导出后删除与批次循环 / 产物清理 到期→EXPIRED→delFile 顺序与删除失败不改状态 / 七项阈值边界值分级 / 告警通道占位不发网络请求 / 守护化入口） | `test/test_sp2c_render_smoke.py` | 改造 |
| 101 | ★ **目录重命名**：SP4c 监控核心包 `monitor/` → **`chmonitor/`**（释放 `monitor/` 名称；同步更新 `schedule/archive.py`、`schedule/credentialCheck.py`、包内引用、`test/` 两份脚本、`tools/runOpsJobs.ps1`、`config/opsSettings.py` 与本文档全部引用） | `chmonitor/`（原 `monitor/`） | 重命名 |
| 102 | ★ **museum 运维监控迁移改造**（源 `museum/code/src/monitor`：`monitor.py` / `alert.py` / `monitorConfig.py` / `crontab.txt` / `restore_monitor.sh`；**保留可复用逻辑**（JSON/时间戳/文件变化检测/告警汇总结构与 `run_alert` 入口），**剥离**网络请求、套接字、子进程与进程 kill 原语，**剥离** museum 专属依赖（`mu_` 前缀业务表 / museum 配置），改为复用 `chmonitor/` 与 `config/opsSettings.py`；★ 保持监控层零网络） | `monitor/` | 新增（迁移改造） |

**★★ SP4c 口径声明（真实执行 / 桩验证）**：**真实执行** = 指标判定七项边界值纯函数、告警通道（日志通道落盘 + 占位通道返回 `networkRequest="0"`/`sent=0`）、`chmonitor` 心跳读写、`chmonitor/dailyCheck.py` 每日巡检（本机无 MySQL → 取数走降级路径并给出报告；`存储用量` 为**真实**磁盘使用率）、归档 dry-run 清单、归档显式执行的「先导出后删除」事件序（**导出/删除/置状态均为桩替换调用点，事件序为真实断言**）、产物清理「先置 EXPIRED 后 delFile」事件序与删除失败不改状态、`archive.py` 默认 dry-run banner、`credentialCheck --loop` 入口、**`monitor/monitor.py`（`-h`/直接运行）与 `monitor/alert.py`（`run_alert` 汇总 + 经 `chmonitor` 通道触达）真实可运行**。**桩验证** = 归档真删的连库读写（本机无 MySQL → `query_ch_audit_log`/`delete_ch_audit_log`/`query_ch_artifact`/`update_ch_artifact` 与 `fileStorageCommon.saveFile/delFile` 均为桩）、监控七项指标的真实取数（本机无 MySQL → `dailyCheck` 各指标走 `degraded` 降级路径，`scheduler_last_success` 为真实心跳判定）、`monitor/` 迁移代码的「进程/服务守护」分支（已按口径剥离为显式不支持，不参与真实执行）。**★★ 未做（→ 见 §10 尚欠项）**：连库端到端归档真删、真实对象存储删除、cron/计划任务实际调度与告警通道真实投递（邮件/企微为占位）。

**★★ SP4b 口径声明（真实执行 / 桩验证）**：**真实执行** = 素材包 ZIP 组装与 7.8 结构（用 SP3b 真实小红书产物）、合规闸门（复用 `complianceService.evaluateCompliance`）、`manifest.checkSum` 与逐文件 sha256 复核、经 `fileStorageCommon`（SELFFILE）**真实上传**与**按 fileID 真实取回**、MCP 未知工具 `ERR_NOCMD`、缺必填参 `BA`、`ERR_NOCMD`/`BT`/`ERROR`/截断分支、巡检三态纯函数与告警分级、Redis 不可用降级。**桩验证** = `ch_artifact` 台账查询（本机无 MySQL）、MCP 的有效 token 放行（本机无 Redis 服务端 → `getSessionInfo` 为桩）、MCP 下游 `/chapi`（第 ⑦/⑧/⑨/⑩ 项，本机未起 Flask 服务）、巡检的账号清单与凭据解密（数据层为桩）。**★★ 本轮明确不做（已确认口径）**：**MCP 不做联调** —— **不启动 `mcp_entry.py`、不监听端口**（监听端口固定 **8891**，由 `config/mcpConfig.py` 取值 + 静态 S27 + 冒烟配置断言锁定，`mcp_entry` 内不得硬编码）；故 9.6.6 的 ①（无 token → 401）/②（无效 token → 拒绝）两项属**服务端鉴权中间件行为，本轮未执行**（→ 见 §10 尚欠项）。**未做**：连库端到端、真实公众号凭据探活（→ 见 §10 尚欠项）。

**★★ SP4a 凭据现状声明（务必按此理解验收口径）**：本机**无可用公众号凭据**（`CH_WECHAT_APPID`/`CH_WECHAT_APPSECRET` 未配置、`Chrome`/网络侧亦无 KMS），
故本轮属 **A/B 二选一中的 (B) 口径**：只做「载荷构造 + **桩替换 HTTP 调用**」的验证，**未端到端打通真实平台**（未真实调用 `get access_token` / `draft/add`，无真实 `errcode/errmsg/remoteID`）。
其中**真实执行**的部分为：AES-256-GCM 加解密往返、`inlineStyle` 外链转存分支、合规纯函数与限流降级；
**桩验证**的部分为：发布记录落库/幂等判定/撤销窗/审计写入/`deliver` 通道（均以桩替换数据层与 HTTP 通道）。

**★★ 2026-09-24 口径变更（平台凭据来源收口；覆盖上一条的「凭据来源」取数方式）**：公众号 appID/appSecret **不再从环境变量获取** —— `processor/publishService.py::decryptAccountCredential` 已删除 `CH_WECHAT_APPID`/`CH_WECHAT_APPSECRET` 兜底（`source="env"` 分支不复存在），平台凭据**唯一来源**是 `ch_account`（用户在「第三方账号管理」`/my-accounts`、或管理员「账号管理」`/accounts` 页录入，经 `main/subfunc/crudApi.py::_applyAccountSecret` 以 AES-256-GCM 加密写入 `credentialCipher`/`credentialIV`，明文不落库、不回显）。未录入凭据的账号在巡检/投递时**显式返回 `F0` 并引导到页面录入**（不静默降级）；appID 与 appSecret 必须**成对取自同一条账号记录**（跨源混配会因 appid/secret 不匹配导致换取 `access_token` 失败）。`config/wechatSettings.py` 的 `WECHAT_APP_ID`/`WECHAT_APP_SECRET` 常量**保留但不再作为凭据来源**（兼容 S9 静态断言）；`processor/platformAdapter/wechatMp.py::checkHealth` 的凭据判定改为**由 `ch_account.credentialCipher` 派生**（仍零网络，新增 `credentialSource` 字段）。**红线不变**：凭据加密主密钥 `CH_CREDENTIAL_KEY` 仍**必须**由环境变量注入（密钥不入库、不入代码库）。回归测试：`python test/test_credential_source.py`（21 项断言：环境变量哨兵不被采用 / 正向解密 / checkHealth 派生 / 静态红线）。

**验收结论**：`python test/test_ch_phase0_static.py` → `total=30, pass=30, fail=0`（SP1 的 S1–S12 + SP1.5 的 S13–S19〔其中 **S15 已随 SP2b 调整为 crudApi 32 CMD 覆盖**、S18 的 topic 域为 8 条 / asset 域为 9 条 / render 域为 1 条〕+ SP2a 的 S20 主题服务与端点 + SP2b 的 S21 素材服务与端点〔SP4b 起 `artifactpack` 已落地，素材域占位清空〕+ SP2c 的 S22 版式引擎与模板 + SP3a 的 S23 平台适配层 + SP3b 的 S24 小红书产物渲染 + SP3c 的 S25 合规服务与台账 + SP4a 的 S26 投递链路 + **SP4b 的 S27 素材包 ZIP / MCP 接入 / 凭据巡检** + **SP4c 的 S28 归档清理 / 监控告警 / 巡检守护化**〔S23 零网络扫描同步纳入 `chmonitor/` 与 `monitor/`（museum 迁移改造层）〕）。
**SP2c/SP3a/SP3b/SP3c/SP4a/SP4b 渲染·投递·素材包·MCP·巡检冒烟**（不连库，对 4 套模板各渲染一次并断言结构/兜底/切片/顺序，SP3b 另做真实截图，SP3c 以**桩替换数据层/计数后端**验证台账与任务化，SP4a 以**桩替换数据层/HTTP 通道**验证投递编排，SP4b 用**真实产物打 ZIP**（★ **MCP 本轮不联调**：不启动服务、不监听端口；端口固定 8891））：`python test/test_sp2c_render_smoke.py` → `total=45, pass=45, fail=0`（SP2c 的 7 项 + **SP3a 的 4 项平台产物**：wechat_mp 内联样式/无 class/图片落在平台显示域/deliver 未实现、wechat_mp carousel 交互降级复用静态兜底、wechat_mp 非白名单外链显式 `E4`、generic html·markdown·json 三形态 + **SP3b 的 6 项小红书真实截图产物**：swipe 卡片 1080×1440/张数/seqNo/封面、longimage 切片数=ceil(总高/sliceHeight)、stack→长图切片、package 清单有序含 manifest、carousel 显式 `C7`、swipe 比例混用 `D1`/超量 `C6` + **SP3c 的 7 项**：敏感词偏移区间（多命中）、`needAiLabelFlag=1` 缺标识被拦、规格违例（`C5`/`C6`/`D1`）命中问题清单且可定位、`ch_artifact` 幂等键形态与 upsert 调用路径 + `artifactVer` 递增、job 非法跃迁被拒、`inputHash` 相同→复用命中、Redis 不可用→限流降级；产物落 `code/data/preview/` 与 `code/data/preview/xiaohongshu/`）。**SP3b 实测像素证据**：swipe 4 张卡片各 `1080×1440`；longimage `fullHeight=5760` → `ceil(5760/1440)=4` 张切片（每张 `1080×1440`）；stack→长图 `fullHeight=7484` → `ceil(7484/1440)=6` 张切片（无超长单图）。**SP3c 实测证据**：`artifactKey=['456:png:xiaohongshu:1','456:png:xiaohongshu:2']`（`artifactStatus=READY`、`artifactVer` 初次 1 / 重渲染 3→4）；`inputHash` 命中 → `reused=1, jobID=88, productCount=1`；Redis 桩不可用与**真实不可用**（本机无服务端）均 `backend=memory, degraded=1, allowed=1`。**SP4a 实测证据（9 项）**：AES-256-GCM `cipherLen=40/ivLen=16`（往返一致、密文≠明文、无密钥抛 `CredentialCipherError`）；`ch_account` 凭据加密写入后**读回解密一致且明文不落库**；`transferFunc` 转存 → `errCode=B0, url=https://mmbiz.qpic.cn/transferred.jpg, transferred=True`（失败保持 `E4`）；敏感词命中 → `errCode=C7, deliverCalls=0`（未投递）；确认缺失 → `F4` 且下发 `confirmToken`；首次投递 `B0, records=1` → 二次提交 `F1, records=1, deliverCalls=1`；撤销窗内 `B0 revoked=1 elapsed=0s`、逾窗 `F5 elapsed=120s`、重复撤销 `F1`；投递失败 `F3, records=1(success=0), auditFails=1`；自动发布 `F6, deliverCalls=0`（且显式确认后仍 `F6`，因平台/配置/账号认证默认不满足）。**SP4b 实测证据（6 项）**：素材包 ZIP 条目 `['01_SMOKE_TOPIC_0001_01_cover.png','02_SMOKE_TOPIC_0001_02_card.png','03_SMOKE_TOPIC_0001_03_card.png','04_SMOKE_TOPIC_0001_04_card.png','title.txt','content.txt','manifest.json','COPYRIGHT.txt','RISK_NOTICE.txt','SWIPE_TIPS.txt']`（图片严格 `01_`/`02_`… 有序、文本条目顺序与 7.8 一致）、`checkSum=f5cd137c0704d710...`（与按序拼接各文件 sha256 复核一致）、`fileID=118/filee8...`（SELFFILE 真实上传）、`zipSizeBytes=23190`；台账取数路径（桩替换 `query_ch_artifact` + **真实**按 `fileID` 取回）→ `errCode=B0, imageCount=4, fileID=019/filecd4a...`；未过合规（敏感词）→ `errCode=C7, packaged=0, uploadCalls=0`（**未上传、未出包**）；MCP **端口不变式** → `MCP_SERVER_PORT=8891, transport=streamable-http, issuer=http://127.0.0.1:8891`；MCP 9.6.6 清单 → `①②未执行(本轮不联调) ③pass(桩:Redis) ④ERR_NOCMD ⑤BT ⑥BA ⑦B0/total=3/returned=3 ⑧3/3 ⑨ERROR ⑩returned=10/total=50`；巡检 → 三态 `{'OK':'OK','EXPIRING':'EXPIRING','INVALID':'INVALID','INVALID_PROBE':'INVALID'}`、逐账号 `OK/EXPIRING/INVALID/UNKNOWN(小红书跳过)`、回写 `['OK','EXPIRING','INVALID']`（跳过项不回写）、`runOnce ok=1/skipped=1`、Redis 不可用 `degraded=1`；`accounthealth` `errCode=B0, checkResult=1`。

**SP4c 实测证据（5 项 + 迁移；本机无 MySQL → 数据层/文件门面为桩）**：① 归档 → `[sp4c-archive] dryRun planRows=2, events=0 execute batches=2, exported=3, deleted=3, events=['export','delete','delete','export','delete']`（★ dry-run **零导出零删除**；显式执行时**每批先导出后删除**且批次循环正确）；② 产物清理 → `[sp4c-purge] purged=1, failed=1, events=[('EXPIRED','11','EXPIRED'),('delFile','f11'),('EXPIRED','12','EXPIRED'),('delFile','f12')]`（★ **先置 EXPIRED 再 delFile**；`f12` 删除失败 → 状态**不再二次变更**并告警）；③ 指标边界 → `[sp4c-metrics] cases=19, metrics=7`（恰在阈值 → `INFO`，越界 → `WARN`/`ERROR`，含「连续失败 3 次」「1.5 周期」「3 倍环比」边界）；④ 告警通道 → `[sp4c-alert] scan=chmonitor+monitor log=1, email=0/0, wecom=0/0`（占位通道 `networkRequest="0"` 且 `sent=0`，静态扫描 **chmonitor/ 与 monitor/ 均无网络痕迹**）；⑤ 守护化入口 → `[sp4c-guard] credentialCheck=--loop, archive=--execute, dailyCheck=__main__, monitor(museum)=ok`（心跳可读写）。**⑥ 目录重命名 + museum 迁移改造实测**：SP4c 监控核心包 `monitor/` → `chmonitor/`（引用全量更新，静态 S28 输出 `chmonitor=ok; monitor(museum 迁移改造)=ok`）；`monitor/` 由 `museum/code/src/monitor` 迁移改造后可直接运行 —— `python monitor/monitor.py -h` 输出帮助、`python monitor/monitor.py` 完成文件变化检测并委托 `chmonitor` 运行七项指标、`python monitor/alert.py` 输出 `run_alert done, triggered:1`（`scheduler_last_success` WARN）；★ `monitor/*.py` 已剥离网络/套接字/子进程与 museum 专属依赖，**零网络**（S23/S28 双扫描）。

**导入级/冒烟验证（本机已做，非连库验证）**：全量安装 `requirements.txt`（另补 `alibabacloud_oss_v2` / `cos-python-sdk-v5`，否则 `fileStorageCommon` 无法导入）后，`MYSQL_SKIP_CONNECT=1` 下
`import subfunc` 成功 → **`CMD total = 69`**（聚合器实际输出：账号域 16 + crud 32 + 主题域 8 + 素材域 9〔8 接管 + `artifactpack`（★ SP4b 已实现）〕+ **渲染域 1（`topicrender`）** + 其余业务域 3〔`publishpush`（★ SP4a 已实现）/`publishcheck`（★ SP3c 已实现）/`mcpinvoke`（★ SP4b 已实现）〕）〔★ 2026-09-20 起：账号域 16 → 19、`CMD total = 72`，见 §9 交接事项第 7 条〕，三道校验通过；`chAPIPost.post()` 对未知命令返回 `B8`；`chAPI.application` 已注册 `/chapi/<urlPath>`。**SP2c 迁移后不变式**：`topicrender` 归属唯一（`CMD_OWNER["topicrender"] == "render"`），主题域 9→8、渲染域 0→1，总数仍 69。
SP2a 追加冒烟（不连库，验证纯函数与端点封装）：`topicadd` 传超长标题 → `C5 + msgKey=contenthub`；`countWords` 中文按字符 / 英文按词；`DRAFT→PUBLISHED` 非法跃迁 → `C7` 并回显当前状态与允许跃迁集。
SP2b 追加冒烟（不连库，验证纯函数与端点封装）：`assetApi.CMD_MAP` 共 9 条（8 接管 + `artifactpack`）；`artifactpack` → `C2`（★ **SP4b 起该断言不再适用**：`artifactpack` 已落地，空入参返回 `C4`、未过合规返回合规原始错误码）；`assetadd` 空入参 → `C4`；`topicassetadd` 空入参 → `C4`、传 `usageType=xxx` → `C7` 并回显允许值、合法入参派生 `assetKey=1:f1`（`{topicID}:{fileID}`）；`computeContentHashFromBytes` 与 `sha256` 一致。
SP2c 追加冒烟（不连库，验证渲染与归属）：`test/test_sp2c_render_smoke.py` 7/7（见上「SP2c 真实渲染冒烟」）；`renderApi.funcTopicRender('topicrender', {}, {})` → `C4 + msgKey=contenthub`（已非占位 `C2`）；`import subfunc` 后 `MODULE_MAPS` 分布 = `{account:16, crud:32, topic:8, asset:9, render:1, publish:1, compliance:1, mcp:1}`。
SP3a 追加冒烟（不连库，验证平台适配层与平台分支；本轮**零网络**）：静态 S23 以「exec 隔离执行纯标准库模块」方式真触发契约与行为 —— `PlatformAdapter` 五方法齐备；`deliver` → `C2`（具体适配器不覆写，未实现由基类统一保证）；`base.checkPlatformSpec` 按 `initSeed.PLATFORM_SEED_LIST`（wechat_mp）真生效（合规→`B0`、标题超长→`C5`、图片超量→`C6`、封面尺寸不符→`D1`、正文图规格不符→`D1`）；`inlineStyle.inlineHtml` 输出无 `class=`/无 `<style>` 且 `max-width:100%` 已下沉内联、carousel 降级复用静态兜底（`data-degraded="static_fallback"`）、`resolveImageUrl` 微信域→`B0` / 非白名单外链→`E4`；适配器零网络调用痕迹。另以桩替换取数（`_fetchPlatformRecord`/`loadLayoutRecord`/`_fetchTopic`/`_fetchAssets`）跑通 `renderService.renderTopic`：缺省取 `ch_layout.platform` → wechat_mp 内联样式 HTML（`B0`，无 class/无 `<style>`）；`platform=generic&exportKind=markdown` → `B0` 且 `outputKind=markdown`；`renderMode=job` → `C2`（异步化归 SP3c）。（★ SP3a 原「`platform=xiaohongshu` → `C7`」的断言已在 SP3b 随适配器落地改为「适配器存在 / `deliver` → `C2`」。）
SP3b 追加冒烟（不连库，**真实 Chromium 截图**，零对外网络）：静态 **S24** 以 AST/文本断言 —— `XiaohongshuAdapter` 契约齐备（`render`/`validate`/`package`/`checkHealth`，**不覆写 `deliver`**）、`deliverMode=asset_pack`、无任何自动发布/投递痕迹（`freepublish`/`draft/add`/`api_publish`/`publishsubmit` 等静态扫描）、`carousel` 显式 `C7`、swipe 强校验错误码落点齐备、`ADAPTER_MODULE_MAP` 已登记 `xiaohongshu`、`renderService` 无 `xiaohongshu` 硬编码、`htmlToImage` 齐备 `getBrowser/closeBrowser/waitForFonts/renderHtmlToImage/renderCardsFromHtml/renderLongImageSlices/uploadArtifact` 且含 `E2`/`E3`、零网络调用、分层不反向依赖；真实截图冒烟 `test_sp2c_render_smoke.py` → `total=17, pass=17, fail=0`（见上「SP2c/SP3a/SP3b 真实渲染冒烟」）。**端点不变式**：`import subfunc` → `CMD total=69`，`CMD_OWNER["topicrender"]=="render"`，适配器注册表 `["generic","wechat_mp","xiaohongshu"]`，`getAdapter("xiaohongshu").deliver({})` → `C2`（**无新增 CMD**）。
SP3c 追加冒烟（不连库、不连 Redis；台账/job/复用/降级均以**桩替换数据层/计数后端**验证，属**桩验证**；纯函数与限流真实调用属**真实执行**）：
静态 **S25** 以 AST/文本断言 —— `complianceService` 函数/常量齐备且**复用** `base.checkPlatformSpec` + `xiaohongshu.validateSwipeSpec`（`def checkPlatformSpec(` / `def validateSwipeSpec(` 均不存在 → 未重写规则表）、问题清单结构（`field`/`location`/`level`/`errCode`/`offsetStart`/`offsetEnd`/`matchedWord`）、限流降级路径（`degraded`/`backend`/`memory` + 只经 `redisMainDB`）、`renderService` 任务状态机与 `inputHash`/`artifactKey`/`insert_ch_render_job`（sync 也建 job）、`renderWorker` 单实例串行（无 `ThreadPool`/`concurrent.futures`/`multiprocessing`/`threading.Thread`）且含 `--once`、`publishcheck` 已实现（`PLACEHOLDER_CMD_LIST = []`）且 `renderApi` 仍只有 `topicrender`（**无新增 CMD**）。
冒烟 `test_sp2c_render_smoke.py` → `total=24, pass=24, fail=0`，SP3c 7 项：① 敏感词多命中 + 偏移区间（`text[start:end]` 与实际命中一致、`location="description[1,6]"`）；② `needAiLabelFlag=1` + `aiFlag=1` 缺标识 → `ERROR`，已提供 `aiLabel`/正文标识词或非强制平台（`wechat_mp`）→ 放行；③ 规格违例 → 问题清单含 `C5`(title，可定位) / `C6`(图片超量) / `D1`(比例不统一，`location=assetList[1]`)；④ `ch_artifact` 幂等键形态 `{jobID}:{kind}:{platform}:{seqNo}` + `upsertByUniqueKey` 落在 `ch_artifact` + `artifactStatus=READY` + `expireYMDHMS` 已写 + 重渲染 `artifactVer` 3→4；⑤ job 状态机 `DONE→RUNNING` / `PENDING→DONE` 被拒（回显允许跃迁集），`PENDING→RUNNING`/`RUNNING→DONE`/`RUNNING→FAILED`/`FAILED→PENDING` 放行；⑥ `inputHash` 相同 → `reused=1` 复用既有产物（`jobID/productCount/reuseReason` 齐备）；⑦ Redis 桩不可用 → `degraded=1, backend=memory, allowed=1` 且降级在问题清单中以 `WARN` 可见（**真实调用**本机亦 `backend=memory, degraded=1`，不崩溃）。**端点不变式**：`import subfunc` → `CMD total=69`，分布 `{account:16, crud:32, topic:8, asset:9, render:1, publish:1, compliance:1, mcp:1}`，`CMD_OWNER["topicrender"]=="render"`，`complianceApi.CMD_MAP==["publishcheck"]`。

SP4b 追加冒烟（不连库；**ZIP 与 MCP 大量真实执行**，仅数据层/下游为桩）：
静态 **S27** 以 AST/文本断言 —— `artifactService` 符号齐备（`exportAssetPack/loadReadyArtifactRecords/materializeProduct/runCompliance/buildImageEntryName/buildManifest/writeZipPackage/...`）、ZIP 六项固定文本条目齐备、风险告知含「官方创作服务平台/禁止第三方自动发布」与滑动提示含「图片显示区域/8.0」、**不重写** `def checkPlatformSpec(` / `def validateSwipeSpec(`（规则单一来源）、只经 `fileStorageCommon`（无 `FILE_SYSTEM_MODE ==` 厂商分支）、**合规闸门位置先于 `writeZipPackage(`**（未过校验不得出包）、代码注释剥离后静态扫描无 `publishService/freepublish/draft/add/submitFreePublish/deliver(`（**小红书不投递不发布**）、不反向依赖 `main/subfunc`；`assetApi` 占位清空且走 `artifactService.exportAssetPack`；`mcpApi` 薄入口含 `TOOL_CMD_MAP/chServerCommon/settings.ROLE_CMD_LIST/MCP_TOOL_LIST/getSessionInfo/ChServer`，剥离注释后无 `jsonrpc/tools/call/FastMCP/mcp.server/toolPathMap`（**不承载协议解析**），G0–G3 错误码落点齐备，8 个只读工具名与 `mcpPost.toolPathMap` 一致；`mcpapi/` 既有 `@mcp.tool()` 8 个 + `@mcp.resource(` 3 个未被改动；`credentialCheck` 符号（`checkAccount/runOnce/decideHealthStatus/acquireCheckLock/...`）与四态常量、`ALERT_LEVEL_MAP` 的 INFO/WARN/ERROR、复用 `publishService.decryptAccountCredential`·`markAccountHealth` 与 `fetchAccessToken`、`xiaohongshu` 跳过说明、`redisMainDB` 降级路径齐备，且不含投递/发布路径；`accountApi` 在**同一处理函数**内接入巡检（`action in ("check","refresh","probe")`）且 `CMD_MAP` 未变；**MCP 监听端口 8891 由 `mcpConfig` 取值且 `mcp_entry` 不得硬编码**；端点总数静态合计 **69**；G2/G3 在 contenthub 消息表中真实存在（exec `errMsgCommon`）。
冒烟 `test/test_sp2c_render_smoke.py` → `total=40, pass=40, fail=0`，SP4b 7 项：① 素材包 ZIP（真实产物，结构/7.8/校验值）② 台账取数路径（桩台账 + 真实取回）③ 未过校验拒绝出包 ④ **MCP 监听端口与传输不变式（8891 / streamable-http）** ⑤ MCP 9.6.6 清单（①②未执行[不联调]，③–⑩ 直调验证）⑥ 巡检三态与分级 ⑦ `accounthealth` 接入。**端点不变式**：`import subfunc` → `CMD total=69`，分布 `{account:16, crud:32, topic:8, asset:9, render:1, publish:1, compliance:1, mcp:1}`，`CMD_OWNER["artifactpack"]=="asset"`、`CMD_OWNER["mcpinvoke"]=="mcp"`、`CMD_OWNER["accounthealth"]=="account"`（**无新增 CMD**）。

未执行（按约定交由有环境的机器）：`tools/initTables.py`、`tools/initSeed.py`、`tools/test_storage.py`（不连数据库 / 不连文件服务）。

---

## 2. 目录骨架

```text
code/src/
├── common/
│   ├── mysqlCommon.py          # ★ 全库读写唯一入口(手写段 + 生成段)
│   ├── mysqlHandle.py          # 读写分离长连接封装(复用)
│   ├── chCommon.py             # ★ 跨域业务公共件(upsertByUniqueKey / fillFileUrls)
│   ├── credentialCipher.py     # ★ SP4a 凭据加解密公共件(AES-256-GCM; 密钥经环境变量 CH_CREDENTIAL_KEY, 不入库不入代码库)
│   ├── accountClient.py        # ★ SP1.5 账号服务 HTTP 客户端(GAA0/A3A0/AIA0/AEA0 + 低层转发)
│   ├── errMsgCommon.py         # ★ SP1.5 错误消息表与返回封装(contenthub msgKey + applicationMsgKey 别名)
│   ├── queryBufferCommon.py    # ★ SP1.5 D3 分页缓冲(genBufferIndexKey/putQuery2Buffer/getQueryBufferComplte)
│   ├── fileStorageCommon.py    # 文件存储门面(三后端 shim + 多桶)
│   ├── chServerCommon.py       # MCP 层访问 /chapi 的 REST 客户端
│   ├── aliyunOSS.py / tencentCOS.py / selfFileCommon.py
│   ├── funcCommon.py / miscCommon.py / globalDefinition.py
│   ├── redisCommon.py / redisHandle.py
├── config/
│   ├── local_settings.py       # ★ 环境入口: _SYS / _SYS_SERVER_NAME
│   ├── basicSettings.py        # FILE_SYSTEM_MODE / ROLE_CMD_LIST / 规格 / MCP_TOOL_LIST
│   ├── mysqlSettings.py        # ★ 读写库连接
│   ├── wechatSettings.py       # ★ 公众号凭据与接口(空结构)
│   ├── aliyunSettings.py / tencentSettings.py / selfFileSettings.py
│   ├── bucketSettings.py       # 多桶统一解析出口
│   ├── redisSettings.py / mcpConfig.py
│   ├── opsSettings.py          # ★ SP4c 归档/监控运维配置(保留期/批大小/导出格式/dry-run 确认开关/七项阈值/告警通道/周期表; 全部可配)
├── database/
│   ├── ch_*.txt                # ★ 12 张表定义(唯一数据源, 套用 recID/尾部七字段规范)
│   ├── userBasic.txt           # ★ 移植表: USER_BASIC 列定义(唯一数据源, 与 createUserBasic() DDL 逐列一致)
│   ├── weixin_pay.txt          # ★ 移植表: 微信支付/退款流水(生成器输入, 见 §11)
│   ├── mysqlCodeGenerator.py   # 生成器(禁止修改)
│   └── auto_generated/         # 产物落点(数据层段 -> mergeMysqlCommon; REST 段 -> mergeCrudApi, 均已在 SP1.5 装配)
├── tools/
│   ├── genTableCode.ps1        # 批量生成
│   ├── mergeMysqlCommon.py     # 产物合并进 mysqlCommon 生成区
│   ├── mergeCrudApi.py         # ★ SP1.5 产物 REST 处理段合并进 subfunc/crudApi.py 生成区
│   ├── initTables.py / initSeed.py / test_storage.py
│   ├── runOpsJobs.ps1          # ★ SP4c 运维定时运行脚本(归档默认 dry-run + 巡检 + 每日巡检; -Execute 才真删)
├── test/
│   ├── test_ch_phase0_static.py    # ★ S1–S28(SP4b 新增 S27 素材包 ZIP / MCP 接入 / 凭据巡检; SP4c 新增 S28 归档清理 / 监控告警 / 巡检守护化, 且 S23 零网络扫描纳入 chmonitor/ 与 monitor/)
│   └── test_sp2c_render_smoke.py   # ★ SP2c/SP3a/SP3b/SP3c/SP4a/SP4b/SP4c 冒烟(不连库; SP3b 为**真实 Chromium 截图**, SP4a 以桩替换数据层/HTTP 通道验证投递编排, SP4b 用真实产物打 ZIP + **MCP 不做联调**(端口 8891 仅配置不变式断言), SP4c 归档/清理以桩替换数据层/文件门面且静态扫描 chmonitor/+monitor/; 产物落 code/data/preview/、preview/xiaohongshu/、data/assetpack/ 与 data/monitor/)
├── main/
│   ├── chAPI.py                # ★ SP1.5 Flask 门面(/chapi/<urlPath>)
│   ├── chAPIPost.py            # ★ SP1.5 瘦入口(230 行): 聚合注册表 + post() 主流程
│   ├── subfunc/                # ★ SP1.5 接入层拆分包(12 文件)
│   │   ├── __init__.py         #   聚合器: MODULE_MAPS + mergeCmdMaps(V1/V2/V3)
│   │   ├── context.py          #   公共依赖与全局单例
│   │   ├── apiCommon.py        #   零业务 HTTP 层公共件
│   │   ├── accountSvcClient.py #   账号服务薄封装(角色映射/错误码归一)
│   │   ├── accountApi.py       #   账号域 16 CMD + calUserCMDMapKeyList(缺陷已修)
│   │   ├── crudApi.py          #   ★ 生成件落点: 32 个 CRUD 处理器 + CMD_MAP(生成区禁止手改)
│   │   └── topicApi / assetApi / renderApi / publishApi / complianceApi / mcpApi
│   │       #   topicApi ★ SP2a 接管主题域 8 端点; assetApi ★ SP2b 接管素材域 8 端点
│   │       #   publishApi ★ SP4a 落地 publishpush(内部走 publishService; action=push|revoke; 不新增 CMD)
│   │       #   mcpApi ★ SP4b 落地 mcpinvoke(仅「鉴权 + 路由 + 经 chServerCommon 转发」, 不承载 MCP 协议解析; 不新增 CMD)
│   └── ylwzRecvFiles.py        # 文件服务(复用)
├── processor/                  # ★ SP2a/SP2b 业务处理器层
│   ├── __init__.py             #   包声明与分层契约(接入层 -> 业务层 -> 引擎层 -> 公共层)
│   ├── topicService.py         #   ★ C2 主题管理(字段区间校验/状态机/wordCount/幂等/版本快照/超长转存)
│   ├── assetService.py         #   ★ C3 素材图库(contentHash 去重/规格裁剪/EXIF 剥离/缩略图/快照/附图绑定)
│   ├── renderService.py        #   ★ SP2c/SP3a/SP3c C4+C5 渲染编排 + 渲染任务化(job 状态机/inputHash 复用/ch_artifact 台账)
│   ├── complianceService.py    #   ★ SP3c C8 合规校验(复用 base.checkPlatformSpec + swipe 专项校验 / 敏感词偏移 / AI 标识 / 限流降级 / 问题清单)
│   ├── auditService.py         #   ★ SP4a 审计留痕(ch_audit_log 字段齐备 + payloadDigest sha256 + 凭据字段脱敏)
│   ├── publishService.py       #   ★ SP4a C6 投递编排(合规闸门/凭据解密/token 缓存刷新/幂等/二次确认/撤销窗/发布记录/审计; 唯一对外产生副作用的模块)
│   ├── artifactService.py      #   ★ SP4b C6 素材包 ZIP 导出(7.8 结构 + 未过校验不出包 + 只导出不投递; 清单复用适配器 package())
│   └── platformAdapter/        #   ★ SP3a C5 平台适配层(适配器只做「形态转换 + 通道调用」, 业务编排留在 renderService/publishService)
│       ├── __init__.py         #   包声明 + 契约/工厂出口(模块级只导入 base, 具体适配器经 getAdapter 延迟导入)
│       ├── base.py             #   ★ PlatformAdapter 抽象基类(五方法) + ch_platform 数据驱动规格校验 + 适配器注册表(deliver 默认仍显式未实现 C2)
│       ├── wechatMp.py         #   ★ WechatMpAdapter(内联样式 HTML / 规格校验 / 草稿载荷清单 / 只读健康巡检 / ★ SP4a 通道调用与 deliver 实现)
│       ├── generic.py          #   ★ GenericAdapter(HTML 复用 stack_v1 的降级实现 + Markdown/JSON 导出)
│       └── xiaohongshu.py      #   ★ SP3b XiaohongshuAdapter(卡片/长图切片 + 素材包清单; asset_pack; 无自动发布路径)
├── engine/                     # ★ SP2c C4 版式引擎层
│   ├── __init__.py             #   包声明与分层契约(引擎层不反向依赖业务层/接入层)
│   ├── layoutEngine.py         #   ★ 版式调度(唯一渲染入口: 读 ch_layout -> 注入 specJson -> Jinja2 -> {outputKind,content,meta})
│   ├── imageProc.py            #   ★ 渲染期图像派生(封面 900x500 / 卡片 1080x1440 统一 / 长图切片; 与 assetService 分工)
│   ├── inlineStyle.py          #   ★ SP3a 微信内联化(class 清洗 / <style> 下沉内联 / 外链图片统一出口 / carousel 交互降级)
│   ├── htmlToImage.py          #   ★ SP3b HTML->PNG 截图管线(Playwright 单实例串行 / 字体预加载 waitForFonts / 整页+元素级 / 长图切片 / E2·E3)
│   └── templates/              #   4 套版式 + partials/base + preview/ 站内手机框预览
│       ├── partials/base.html
│       ├── stack_v1/index.html
│       ├── carousel_v1/index.html
│       ├── longimage_v1/index.html
│       ├── swipe_v1/index.html
│       └── preview/{wechat_mp,xiaohongshu}.html
├── schedule/                   # ★ SP3c 调度层(常驻消费; 只依赖 processor/common, 不得 import main/subfunc)
│   ├── __init__.py             #   包声明与分层契约
│   ├── renderWorker.py         #   ★ SP3c 渲染任务常驻消费者(PENDING->RUNNING->DONE/FAILED; 单实例串行 + Redis 锁可降级; --once)
│   ├── credentialCheck.py      #   ★ SP4b P3-6 凭据健康巡检(公众号只读探活 + healthStatus/分级告警; 小红书跳过; Redis 锁可降级; __main__ 单次执行)
│   │                           #   ★ SP4c: 守护化(--loop 常驻 + --interval; 单实例 + Redis 锁可降级), 告警对接 chmonitor, 刷新心跳
│   └── archive.py              #   ★ SP4c P3-7 归档清理(ch_audit_log 分批导出+删除 / ch_artifact 过期清理)
│                               #   ★★ 默认 dry-run(真删须 --execute / CH_ARCHIVE_EXECUTE=1); 先导出上传成功才删除; 先置 EXPIRED 再 delFile
├── chmonitor/                  # ★ SP4c P3-8 监控核心层(原 monitor/, 本轮重命名; 只依赖 processor/common/config; 不得 import main/subfunc)
│   ├── __init__.py             #   包声明与分层契约(命名说明: 原 monitor/; 首期降级口径: 日志告警 + 每日巡检 + 占位通知接口; 零网络)
│   ├── metrics.py              #   七项指标判定纯函数(阈值可配; 输出 指标名/当前值/阈值/级别 INFO·WARN·ERROR/建议动作)
│   ├── alertChannel.py         #   可插拔告警通道(日志默认; email/wecom 占位, ★ 不发任何网络请求, networkRequest 恒 "0")
│   ├── heartbeat.py            #   定时任务心跳(本地文件; 供「定时任务最后成功时间」指标)
│   ├── monitorService.py       #   指标采集与每日汇总(取数降级 + 报告落 code/data/monitor/ + WARN/ERROR 告警)
│   └── dailyCheck.py           #   ★ 每日巡检脚本(单次执行 __main__; 供 cron / 计划任务调用)
├── monitor/                    # ★ SP4c 运维监控/守护层(由 museum/code/src/monitor 迁移并改造为 contentHub 口径; 零网络)
│   ├── __init__.py             #   包声明与迁移说明(改造口径: 剥离网络/套接字/子进程原语与 museum 专属依赖)
│   ├── monitorConfig.py        #   监控配置(工作目录取 opsSettings; 进程/服务配置置空, 相关原语已剥离)
│   ├── monitor.py              #   ★ 文件变化守护(纯 os.path) + 委托 chmonitor 运行七项指标; __main__ 入口
│   ├── alert.py                #   ★ 告警汇总(复用 chmonitor 七项指标; run_alert 入口; 经 chmonitor 通道触达)
│   ├── crontab.txt             #   Linux crontab 部署样例(museum 迁移改造; 路径已改为 contentHub)
│   └── restore_monitor.sh      #   Linux 守护启动样例(museum 迁移改造)
├── mcpapi/                     # MCP 只读层(mcp_entry.py / mcpPost.py)
├── requirements.txt
└── plan.md                     # 本文件
```

尚未创建（由后续子计划落点）：`code/webserver/`（`processor/` 已于 SP2a 建立、`engine/` 已于 SP2c 建立、`processor/platformAdapter/` 已于 SP3a 建立、`schedule/` 已于 SP3c 建立、**`chmonitor/` 与 `monitor/` 已于 SP4c 建立**〔`chmonitor/` = SP4c 监控核心，原 `monitor/`；`monitor/` = 由 `museum/code/src/monitor` 迁移改造的运维监控/守护层〕）。

---

## 3. 模块边界

| ID | 模块 | 落点 | 所属子计划 |
|---|---|---|---|
| C1 | 接入与权限 | `main/chAPI.py` / `main/chAPIPost.py` / `main/subfunc/account*.py` / `common/accountClient.py` | SP1.5 |
| C2 | 主题管理 | `processor/topicService.py` + `main/subfunc/topicApi.py`（接管主题域 8 端点） | **SP2a（已完成）** |
| C3 | 素材图库 | `processor/assetService.py` + `main/subfunc/assetApi.py`（接管素材域 8 端点） | **SP2b（已完成）** |
| C4 | 版式引擎 | `engine/layoutEngine.py` + `engine/imageProc.py` + `engine/templates/` + `processor/renderService.py` | **SP2c（已完成）** |
| C5 | 平台适配 | `processor/platformAdapter/*` + `engine/inlineStyle.py` + `engine/htmlToImage.py` | **SP3a（已完成：适配器基类/微信内联化/通用导出；零网络）**；**SP3b（已完成：`htmlToImage.py` Playwright 真实截图 + 小红书适配器 swipe 卡片/长图切片/素材包清单；零对外网络、无自动发布路径）** |
| C6 | 发布投递 | `processor/publishService.py`（投递编排）+ `processor/platformAdapter/wechatMp.py`（通道调用）+ `main/subfunc/publishApi.py`（`publishpush`）+ `common/credentialCipher.py`（凭据加密） | **SP4a（已完成：公众号草稿箱投递链路；★ 小红书一律不投递/不发布）** |
| 审计 / 凭据安全 | `processor/auditService.py`（`ch_audit_log` 全链路留痕）+ `common/credentialCipher.py`（AES-256-GCM，密钥走环境变量） | **SP4a（已完成：随投递落地 P3-5 审计与 R-19 凭据加密）** |
| C7 | MCP 与开放接口 | `mcpapi/`（只读层：8 tool + 3 resource）；`main/subfunc/mcpApi.py` 仅薄入口（`mcpinvoke`） | **SP4b（已完成：`mcpapi/` 既有逻辑未改动，监听端口固定 **8891**；★ **本轮不联调**（不启动服务/不监听端口），9.6.6 的 ①② 未执行、③–⑩ 直调实现层验证；`mcpinvoke` 落地为 REST 薄入口，复用 `common/chServerCommon.py` 转发）** |
| C8 | 合规校验 | `processor/complianceService.py` + `main/subfunc/complianceApi.py`（`publishcheck`） | **SP3c（已完成：平台规格**复用 `base.checkPlatformSpec`** / swipe 专项**复用 `xiaohongshu.validateSwipeSpec`** + 超长整图前置拦截 / 敏感词命中+偏移区间 / AI 内容标识 / 发布频率限流**可降级** / 统一问题清单）** |
| 渲染任务化 / 产物台账 | `processor/renderService.py`（`ch_render_job` 状态机 + `inputHash` 复用 + `ch_artifact` 台账）+ `schedule/renderWorker.py`（常驻消费） | **SP3c（已完成；M2 收口）** |
| 素材包导出 / 凭据巡检 | `processor/artifactService.py`（ZIP 导出）+ `main/subfunc/assetApi.py`（`artifactpack`）；`schedule/credentialCheck.py`（凭据探活）+ `main/subfunc/accountApi.py`（`accounthealth` 接线） | **SP4b（已完成：只导出不投递 / 未过校验不出包；巡检只读探活 + 分级告警）** |
| 归档清理 / 监控告警 | `schedule/archive.py`（`ch_audit_log` 归档 + `ch_artifact` 过期清理）+ `chmonitor/`（七项指标 / 告警通道 / 每日巡检）+ `monitor/`（museum 迁移改造：文件变化守护 + 告警汇总）+ `schedule/credentialCheck.py`（守护化）+ `config/opsSettings.py`（运维配置） | **SP4c（已完成：★ 破坏性操作默认 dry-run / 先导出后删除 / 先置 EXPIRED 再 delFile / 告警通道为占位且零网络；★ 监控核心包由 `monitor/` 重命名为 `chmonitor/`，`monitor/` 接收 museum 迁移改造代码；M3 第三块）** |
| C9 / C10 | 版本协作 / 数据回收（P2） | 暂不实现 | v1.1 |
| 数据库链路 | 表定义 / 生成 / 合并 / 建表 / 种子 | `database/` + `common/mysqlCommon.py` + `tools/` | **SP1（本轮，已完成）** |

---

## 4. 接口约定速查

| 约定 | 内容 |
|---|---|
| 数据库访问 | 只经 `common/mysqlCommon.py`（`insert_ch_* / query_ch_* / update_ch_* / delete_ch_* / create_ch_*`），业务层禁止裸 SQL |
| 文件访问 | 只经 `common/fileStorageCommon.py`，禁止厂商分支判断 |
| 时间格式 | `misc.getTime()` → 14 位 `YYYYMMDDHHMMSS`；时间列 `VARCHAR(16)` |
| 报文格式 | `comFC.rtnMSG(errCode, field, lang, msgKey)` → `{"MSG":{"errCode","content"},"msgKey"}`（实现已抽取到 `common/errMsgCommon.py`，`funcCommon` 仅 re-export） |
| 错误消息键 | contentHub 统一 `msgKey="contenthub"`（决策 12.6）；生成件硬编码的 `applicationMsgKey` 经 `MSG_KEY_ALIAS` 归一为 `contenthub`，**不再静默回落 `default`**（决策 12.4） |
| 错误码分段 | `C0-C9` 通用与字段校验（`C2`=占位端点未实现）｜`D0-D9` 文件与素材｜`E0-E9` 渲染与产物｜`F0-F9` 投递｜`G0-G9` MCP 与令牌（★ SP4b 启用 `G2`=未知 MCP 工具 / `G3`=下游服务调用失败，`G0`/`G1` 复用为令牌无效 / 权限不足）；与既有 `B*/C[字母]*/D[字母]*` 段零重叠 |
| 接入层注册表 | 各 `subfunc/*Api.py` 只声明模块级 `CMD_MAP`，由 `subfunc/__init__.py::mergeCmdMaps` 合并并做 V1 冲突 / V2 可调用 / V3 与 `ROLE_CMD_LIST ∪ NO_SESSIONID_CMD_LIST` 完整性三道校验（导入期失败即不启动） |
| 分页缓冲 | `genBufferIndexKey` / `putQuery2Buffer` / `getQueryBufferComplte`（D3 移植，落点 `common/queryBufferCommon.py`） |
| 入口日志 | `_DEF_LOG_CH_WEBAPI_TITLE="CHAPI"` / `_DEF_LOG_CH_WEB_API_NAME="chweblog"`，`chAPI.py` 与 `chAPIPost.py` 共用一个 logger |
| 摘要 | `comFC.genDigest(d1..d5)` → MD5 hexdigest |
| 文件引用 | 库内只存 `fileID`；URL 由后端出参转换（`chCommon.fillFileUrls`，按 `storageBucket` 快照路由） |
| 幂等写入 | 唯一键拼接单列 + `UNIQUE`；写入走 `chCommon.upsertByUniqueKey`（命中更新 / 未命中插入） |
| 幂等键拼接 | `ch_topic_asset.assetKey={topicID}:{fileID}`；`ch_artifact.artifactKey={jobID}:{kind}:{platform}:{seqNo}`；`ch_topic_version.verKey={topicID}:{versionNo}`；`ch_asset.contentHash=sha256(原始字节)`；`ch_publish_record.idempotencyKey` 由调用方传入 |
| 查询默认行为 | `query_ch_*` 一律叠加 `delFlag` 过滤 + `ORDER BY recID` + `LIMIT`；`ch_audit_log` 默认 `LIMIT 5000` |
| 可空数值列 | 生成器对数值列强转并异常置 0 → 业务层统一约定「**0 = 未设置**」 |
| 端点命名 | `{表名去 ch_ 去下划线}{add/del/modify/qry}`，共 48 个（见 §7） |
| 端点总数 | **69** = crudApi 32（8 表 × 4）+ 主题域 8 + 素材域 9 + 渲染域 1（`topicrender`）+ 账号域 16 + 其余业务域 3。★ SP3a 平台适配层**不新增 CMD**（`topicrender` 用 `platform` 参数化）、SP3c **同样不新增 CMD**（`publishcheck` 由占位替换为真实实现，`renderMode=job` 复用 `topicrender`）、★ SP4a **同样不新增 CMD**（`publishpush` 由占位替换为真实实现，投递与撤销经 `action=push\|revoke` 复用同一端点）、★ SP4b **同样不新增 CMD**（`artifactpack` 与 `mcpinvoke` 由占位替换为真实实现；凭据巡检经 `accounthealth` 的 `action` 承接），聚合器实测总数仍 69 |
| 端点归属 | ★ SP2a 起：`topic{add/del/modify/qry}` + `topicversion{add/del/modify/qry}` 共 8 条由 `main/subfunc/topicApi.py` 接管（内部走 `processor/topicService.py`）；★ SP2b 起：`asset{add/del/modify/qry}` + `topicasset{add/del/modify/qry}` 共 8 条由 `main/subfunc/assetApi.py` 接管（内部走 `processor/assetService.py`）；★ SP2c 起：`topicrender` 由 `main/subfunc/renderApi.py` 接管（内部走 `processor/renderService.py` → `engine/layoutEngine.py`），主题域 9→8、渲染域 0→1；其余 32 条 CRUD 由 `main/subfunc/crudApi.py` 装配 |
| 业务端点 | `topicrender`（★ SP3a 可选入参：`platform`〔缺省取 `ch_layout.platform`〕、`exportKind`〔generic 的 `html`/`markdown`/`json`〕、`previewKind`；★ SP3c `renderMode ∈ {sync, job}`，`job` 返回 `jobCode`+`PENDING`）/ ★ SP3c `publishcheck`（合规闸门，出参含统一问题清单 `data.issues`；入参 `topicID/topicCode` + 可选 `layoutCode`/`platform`/`sensitiveWords`/`products`/`rateLimitCount`/`rateLimitWindow`）/ ★ SP4a `publishpush`（**已实现**：公众号草稿箱投递 + 撤销；入参 `platform/topicID/layoutCode/artifactID/accountID/idempotencyKey/confirmFlag/confirmToken/autoPublish/action`；出参含 `remoteID/publishRecordID/success/autoPublish/costMs/auditWritten`）/ ★ SP4b `artifactpack`（**已实现**：素材包 ZIP 导出；入参 `topicID/topicCode` + `jobID` 或 `artifactID(s)`（或直接 `products`）+ 可选 `layoutCode/platform/specOverride/sensitiveWords/objectDir`；出参 `fileID/fileUrl/manifest/entryList/checkSum/zipSha256/imageCount/compliance`，`packaged="0"` 表示未过校验未出包）/ ★ SP4b `accounthealth`（**已实现**：健康汇总；`action ∈ {check,refresh,probe}` 时先触发凭据巡检，出参含 `healthSummary` + `credentialCheck`）/ ★ SP4b `mcpinvoke`（**已实现**：MCP REST 薄入口；入参 `toolName/tool` + `params/args` + `token/sessionID`；出参 `toolName/cmd/downstream/downstreamErrCode`） |
| 主题字段区间 | 标题 ≤50 字、简介 ≤200 字、详述 **无字数下限（可留空 / 0 字）、≤5000 字**（**>5000 转存文件并写 `descriptionFileID`，绝不静默截断**）；保存与提交渲染均不受字数下限拦截（★ 2026-09-22 裁定取消 2000 字下限）；违例返回 contenthub `C4/C5/C6/C7` 并标明字段名与位置 |
| 主题状态机 | `DRAFT→RENDERING→RENDERED→PUBLISHED→ARCHIVED`（允许渲染失败/退回编辑，`ARCHIVED` 为终态）；非法跃迁返回 `C7` 并回显当前状态与允许跃迁集 |
| `wordCount` 口径 | 中文（CJK）按**字符**、英文/数字按**词**（连续 `[A-Za-z0-9]` 串算 1 词），标点空白不计；由 `topicService.countWords` 统一实现 |
| 免登录端点 | `NO_SESSIONID_CMD_LIST = [platformqry, layoutqry, artifactqry]`（+ 登录注册类） |
| MCP 分发 | `post(toolName, dataSet, envSet)` → `{toolName, errCode, rtnData}`；注册表 `toolPathMap` 在 `mcpPost.py` 末尾 |
| MCP 传输 | streamable-http（`mcp.streamable_http_app()` + uvicorn，默认端口 **8891**） |
| 版式类型 | `stack` / `carousel`（项目自实现交互）/ `longimage` / `swipe`（平台原生，仅小红书）；`carousel` 与 `swipe` 禁止合并或互替 |
| 小红书多图规格 | 张数 ≤18、整篇单一比例（首选 1080×1440）、单张 ≤20MB、格式 JPG/PNG、长图须按 1080×1440 切分 |
| 渲染入口 | 引擎层：`engine/layoutEngine.py::renderLayout(layoutRecord, topicData, assetList, overrideSpec=None, embedMode=False)` → `{outputKind, content, meta}`；`renderTopic(...)`/`loadLayoutRecord(layoutCode)` 读 ch_layout（只经 `mysqlCommon`）。**数据由业务层取好后传入**：`processor/renderService.py` 为「业务层→引擎层」唯一连接点（引擎层不反向依赖 processor/subfunc）。★ SP3a 起业务入口再经 `processor/platformAdapter` 适配器出**平台形态产物**（适配器只做形态转换） |
| 渲染期错误码 | 一律 contenthub `E` 段（不占用 C*/D*/B* 段）：`E0` 模板缺失/版式不支持、`E1` 渲染失败（spec 校验不通过/版式停用/平台配置读取失败）、`E2` **截图超时**（SP3b 落地）、`E3` 产物生成失败（长图超上限/切片失败）、`E4` **外链图片需转存但凭据缺失**（SP3a 新增；绝不静默保留外链）。平台适配层另有 `C2`（`deliver` 未实现）/`C4`/`C5`/`C6`/`C7`（**含小红书 `carousel` 不可用**）/`CB`/`D0`（文件类型不允许）/`D1`（图片尺寸或比例不符；**swipe 比例不统一即 `D1`，不静默裁切**）（见下方「平台适配器契约」） |
| 平台适配器契约 | `processor/platformAdapter/base.py::PlatformAdapter` 抽象基类，**契约五方法**：`render(topicData, layoutRecord, assetList, overrideSpec, options)`（形态转换）/ `validate(topicData, assetList, platformRecord)`（平台规格校验）/ `package(renderResult, topicData, assetList, options)`（打包清单，本轮只出清单不落盘）/ `deliver(packageResult, options)`（投递通道）/ `checkHealth(sessionIDSet)`（凭据/账号健康，只读）。统一出参 `{errCode, field, errMsgList, data}`；子类须声明 `platformCode` / `deliverMode` |
| `deliver` 归属与实现（SP4a 更新） | `deliver` 基类默认实现仍**一律返回显式未实现 `C2`**（`generic`/`xiaohongshu` 继续走默认实现）；★ **SP4a 起仅 `wechat_mp(draft_box)` 覆写 `deliver`**（做「通道调用」：封面素材上传 + `draft/add`，返回 `remoteID`）。**业务编排（幂等 / 二次确认 / 撤销窗 / 合规闸门 / 凭据解密 / token 缓存 / 发布记录 / 审计）一律在 `processor/publishService.py`**；素材包 ZIP（`artifactpack`）仍归 SP4。适配器不再「零网络」，但网络只出现在 `wechatMp.py`（`base.py`/`generic.py`/`xiaohongshu.py`/`inlineStyle.py`/`htmlToImage.py` 仍零网络，S23/S24 锁定） |
| 适配器注册与新增平台 | 注册表 `platformAdapter.base.ADAPTER_MODULE_MAP = {platformCode: (模块路径, 类名)}`，经 `getAdapter(platformCode, platformRecord)` 延迟导入实例；`processor/platformAdapter/__init__.py` 模块级只导入 `base`（纯标准库），具体适配器经工厂延迟导入（避免包内循环依赖）。**新增平台 = 加一个适配器 + 一条 `ch_platform` 记录**，不改主干、不改 CMD 路由。★ SP3b：小红书适配器已登记（`xiaohongshu → XiaohongshuAdapter`，`deliverMode=asset_pack`），**只做卡片/长图形态转换与素材包清单，`deliver` 仍由基类统一显式未实现（C2），不含任何自动发布/投递路径**（平台红线）；请求无适配器的平台仍 → `C7` |
| 平台规格校验 | 数据驱动（规则全部取自 `ch_platform`）：`titleMaxLen`（超长→`C5`）/ `summaryMaxLen`（超长→`C5`）/ `coverSpec` 如 `900x500`（封面尺寸不符→`D1`）/ `imageSpec` 如 `1080x1440`（正文图尺寸不符→`D1`）/ `imageMaxCount`（超量→`C6`）；`title` 缺失→`C4`。尺寸未知时不误报（渲染期由 `imageProc` 派生归一后再判） |
| 外链图片策略 | ★ 统一出口 `engine/inlineStyle.py::resolveImageUrl(imageUrl, displayHostList, allowAnyHost)`：空串→原样；非 http(s)（相对/本地/fileID）→原样并标记 `needUpload`（不属外链范畴，交上传链路）；http(s) 且 host 在**适配器传入的**显示域白名单（`wechat_mp`=`mmbiz.qpic.cn`；`generic`=`["*"]`）→原样；其余外链：★ SP4a 起若调用方注入可选 `transferFunc`（由 `wechatMp.buildTransferFunc` 提供，凭据就绪时业务层注入）则**真实转存并就地替换 src 为平台地址**（返回 `B0` + `transferred=True`），转存失败或未注入时**显式返回 `E4`**，绝不静默保留外链。**平台域名只出现在适配器内，模板不得出现平台专属域名** |
| 交互降级规则 | ★ 平台不允许脚本时（`ch_platform.allowSvgFlag != "1"`，公众号为 `0`）`inlineStyle.degradeCarouselInteraction` 移除 carousel 自实现交互（`data-interactive="1"` 节点含 `<script>` 与翻页按钮），**复用 SP2c 已产出的静态图集兜底节点**（`data-carousel-fallback="static"`）并标记 `data-degraded="static_fallback"`；`meta.interactionDegraded="1"`。`swipe` 不做交互降级（本就无脚本），其模板仍禁止 `script/onclick` |
| 版式参数键 | 一律沿用 `ch_layout.specJson` 的既有键（见 `tools/initSeed.py`），**不得自造第二套参数名**。stack=`maxWidth/fontSize/lineHeight/paragraphGap`；carousel=`size/ratio/maxCount/allowSvg/needStaticFallback`；longimage=`size/ratio/sliceHeight/maxTotalHeight`；swipe=`size/ratio/maxCount/minCount/uniformRatio/maxSizePerImageMB/format/sortable/coverFlag`；请求可用 `specOverride/overrideSpec` 在渲染期覆盖 |
| 图片处理分工 | `processor/assetService.py` = **入库前**（`MAX_PIC_SIZE` 裁剪 / `THUMBNAIL_SIZE` 缩略图 / EXIF 剥离，写 `ch_asset`）；`engine/imageProc.py` = **渲染期派生**（封面 900×500、卡片 1080×1440 统一、长图按 `sliceHeight` 切片），经 `common/fileStorageCommon.py` 上传派生对象，**不写 `ch_asset`、不重复入库前能力、不出现厂商分支** |
| 模板约定 | 目录 `engine/templates/`；`layoutType` 与模板目录一一对应（`stack→stack_v1`/`carousel→carousel_v1`/`longimage→longimage_v1`/`swipe→swipe_v1`）；共用骨架 `partials/base.html`（`embedMode=True` 输出片段供站内预览嵌入）；布局用内联 style + `data-*`，**不依赖 class 语义**（为 SP3 微信内联化留余地）；模板不得出现平台专属域名等硬编码 |
| carousel/swipe 边界 | `carousel` = 本项目自实现交互，**静态图集兜底节点必须产出**（公众号 SVG 不稳）；`swipe` = 平台原生交互，本项目**只切分+排序+统一比例**，模板**不得出现 script/onclick**；二者禁止合并或互替 |
| 渲染出参 | `content` 为 Jinja2 渲染结果（完整 HTML 或片段）；`meta` 含 `layoutCode/layoutType/platform/outputKind/spec/renderAt` 及分派专有信息：longimage=`sliceHeight/sliceCount/slices`、swipe=`cards/coverFileID/mechanism=platform_native`、carousel=`interactive/staticFallback`。★ SP3a 起 `topicrender` 出参额外含 `platform`，`meta` 叠加适配器信息：`platformCode/platformName/deliverMode/adapter/inlineStyled/classFree/interactionDegraded/imageCount/networkRequest`（generic 另含 `exportKind/degradedImpl`）。★ SP3b 起 PNG 产物类平台（小红书）出参额外含 `data.products`（**有序产物记录**：`seqNo/kind/fileID/fileUrl/localPath/fileName/width/height/sizeBytes/sha256/isCover/sourceFileID/caption`）与 `data.fileIDs`（仅 fileID 列表，经 `chCommon.fillFileUrls` 转 URL）、`data.productCount`；`meta` 叠加 `artifactKind/productCount/fontInfo/fullWidth/fullHeight/sliceCount`。**`ch_artifact` 台账写入归 SP3c，本轮不写库** |
| 站内预览 | `topicrender` 可选参数 `previewKind ∈ {wechat, xiaohongshu}` → `engine/templates/preview/` 手机框包裹渲染片段（★ SP3a 起由**适配器**包裹**平台形态片段**，故微信预览展示的即降级后形态）；出参 `fileID` 一律经 `chCommon.fillFileUrls` 转换 |
| 渲染任务模式 | ★ **SP3c 起 `topicrender` 支持 `renderMode ∈ {sync, job}`**（缺省 `sync`；其它值 → `C2` 显式未实现）。**`sync` 与 `job` 都建 `ch_render_job`**：`sync` 建 job 后即时推进 `PENDING→RUNNING→DONE`；`job` 建 job（`PENDING`）后**立即返回 `jobCode` + `jobStatus`**，由 `schedule/renderWorker.py` 异步执行（`FAILED` 可由调用方重新入队）。★ 原 SP3a「`job` → `C2`」的行为已由 SP3c 兑现（`C2` 仅保留给未支持的 `renderMode` 取值） |
| 渲染任务状态机 | `ch_render_job.jobStatus`：`PENDING→RUNNING→DONE/FAILED`（`FAILED→PENDING` 允许重试入队；`DONE` 为终态）。非法跃迁 → `C7` 并**回显当前状态与允许跃迁集**（`renderService.checkJobStatusTransition`，沿用 `topicService` 范式）；worker 消费前复用同一状态机做防御校验 |
| 渲染输入快照（`inputHash`） | `renderService.buildInputHash` = `sha256(canonical json)`，口径 = 主题关键字段（`topicCode/title/summary/description/coverFileID/aiFlag`）+ **附图列表**（按 `(sortOrder, fileID)` 排序后取 `fileID/尺寸/用途`）+ `layoutCode/layoutType` + `platform` + **生效 spec**（`specJson` 叠加 `overrideSpec`）。**命中既有 `DONE` 任务的同一 `inputHash` 且产物齐备 → 复用既有产物、不重复渲染**（出参 `reused="1"` + `reuseReason`/`jobID`/`artifacts`，并记日志） |
| `ch_artifact` 台账与 `artifactVer` | 写入一律经 `chCommon.upsertByUniqueKey`，唯一键 `artifactKey = {jobID}:{kind}:{platform}:{seqNo}`（3.4.5 幂等）；记录 `kind/platform/fileID/thumbnailID/seqNo/artifactVer/specNote/sizeBytes/artifactStatus/expireYMDHMS`。`artifactStatus ∈ {READY, EXPIRED}`；**`artifactVer` 递增规则：同一 `artifactKey` 首次写入为 1，同 job 重渲染命中既有键 → 既有版本 +1**。★ **过期清理任务不在 SP3c**（归 SP4 归档/清理），本轮只写字段 |
| 合规问题清单结构 | `processor/complianceService.py` 统一输出：每项 = `{field 字段, location 位置(含下标/偏移), level ∈ {ERROR, WARN}, errCode contenthub 段, message 说明, source 来源}`；**敏感词项另附 `offsetStart/offsetEnd/matchedWord`**（供前端直接高亮）；汇总出参 `data = {passed, issueCount, errorCount, warningCount, issues, ...}`，`passed="1"` 仅当无 `ERROR`（`WARN` 不阻断） |
| 合规规格校验的单一来源 | ★ 平台规格一律**复用** `base.checkPlatformSpec`（规则全部来自 `ch_platform`）；swipe 专项（比例统一 `uniformRatio`/张数/单张 ≤20MB/格式 JPG·PNG）一律**复用** `xiaohongshu.validateSwipeSpec`（2.6.3 唯一定义处）；`complianceService` **只做前置拦截调用 + 结果归一为问题清单**，超长整图（高 > 切片高/卡片高，默认 1440）另作 C8 前置拦截（`E3`），**禁止第二张规则表** |
| 发布频率限流与降级 | 按**账号（+平台）维度**计数：Redis `INCR` + `EXPIRE`（窗口默认 3600s / 上限 30，可经 `rateLimitCount`/`rateLimitWindow` 覆盖）；超限 → `C6`（★ `F2` 属投递段，**本轮不占用**）。★ **Redis 不可用时降级为进程内固定窗口计数 + `degraded="1"` + 告警日志**，**不拒绝、不崩溃**；降级在问题清单中以 `WARN` 显式可见（`checkRateLimitIssues`） |
| Redis 使用红线与降级 | Redis 只用于「会话/缓冲/锁/限流」，且**必须可降级**：`renderWorker` 任务锁 = 进程内锁 + Redis `SET NX EX`（Redis 不可用 → `degraded` 放行，单实例串行兜底）；限流 = Redis 计数（不可用 → 进程内计数）。**关键路径不得因 Redis 不可用而阻塞**；一律只经 `common/redisCommon.py`（不直连、不改其既有逻辑） |
| 截图管线参数（SP3b） | `engine/htmlToImage.py`（Playwright）：**懒加载单浏览器实例**（进程内复用、**串行渲染**、`closeBrowser()` 统一关闭；同一时刻只渲染一个页面）；`headless=True`；viewport 取 `DEFAULT_CARD_SIZE(1080×1440)` 或 `specJson.size`；`device_scale_factor` 可配（默认 `1`，保证输出像素 = CSS 像素，卡片精确 1080×1440）；渲染超时上限 `DEFAULT_RENDER_TIMEOUT_MS=30000`。`renderHtmlToImage`（元素级 `selector` 或整页 `full_page`）/ `renderCardsFromHtml`（swipe：每张卡片独立 context/page，一屏一张 PNG）/ `renderLongImageSlices`（整页截图后复用 `imageProc.sliceLongImage` 切分，**禁止直接产出超长单图**）。失败映射：**截图超时 → `E2`，产物生成失败 → `E3`**（`HtmlToImageError`，不抛裸异常）；Playwright 不可用/Chromium 启动失败 → `E1` |
| 字体预加载（SP3b） | `htmlToImage.waitForFonts`：注入中文字体栈（`DEFAULT_FONT_FAMILY`，Windows 微软雅黑 / Linux 需另装 CJK 字体）+ 等待 `document.fonts.status === "loaded"`（`document.fonts.ready`），**另有显式超时兜底**（超时不抛异常，仅记 `timedOut`）；`meta.fontInfo` 记录 `ready/timedOut/fontStatus/declaredFontFamilies/usedFontFamilies`（**实际使用字体**，便于排查中文丢字） |
| swipe 切分与校验（SP3b） | `XiaohongshuAdapter` 只做「**切分 + 排序 + 统一比例**」，**不自实现滑动交互**（`mechanism=platform_native`，模板不得出现 `script/onclick`）。强制校验（主计划 2.6.3，渲染前拦截）：**比例统一**（源图比例与 `spec.ratio`（默认 3:4）不一致 → 显式 `D1`，**不静默裁切/缩放掩盖**）、**张数 ≤ min(specJson.maxCount, ch_platform.imageMaxCount=18)**（超量 → `C6`）、**单张 ≤ 20MB**（超限 → `D1`）、**格式 JPG/PNG**（其他 → `D0`）。产物：N 张 1080×1440 PNG，`seqNo` 递增、第 1 张 `isCover="1"`、`coverFileID` 稳定置顶 |
| 长图切片（SP3b） | 小红书形态的 `longimage` 与 `stack`（`stack` 在小红书形态为长图，渲染期把 `maxWidth` 归一到卡片宽度）走同一长图管线：整页截图 → 按 `specJson.sliceHeight`（默认 1440）切分为多张；**每张切片都作为独立产物登记（`seqNo` 递增）**；切片数 = `ceil(长图实际总高/sliceHeight)`；超 `specJson.maxTotalHeight` → `E3` |
| carousel 在小红书不可用（SP3b） | ★ 小红书**不接收 HTML**，且 `carousel` 交互（含静态图集兜底）属**公众号自实现** → 请求 `carousel + xiaohongshu` **显式返回 `C7`**（标明字段与原因），**绝不静默转换为长图/图集**（`carousel` 与 `swipe` 边界不可越界） |
| 素材包清单（SP3b） | `XiaohongshuAdapter.package` 只出**结构化清单**：`itemList`（有序产物文件列表：seqNo/fileName/fileID/尺寸/字节数/sha256/isCover）+ `manifestDraft`（主题编码/标题/生成时间/版式/平台/文件清单/`checkSum=sha256(按序拼接各文件 sha256)`）；`packageKind="xiaohongshu_asset_pack"`、`zipPacked=False`。★ **ZIP 打包与导出归 SP4**（`artifactpack` 端点仍 `C2`），本轮不下发文件 |
| 小红书产物上传（SP3b） | 产物先落**本地临时目录**（或调用方经 `options.productDir` 指定，如冒烟落 `code/data/preview/xiaohongshu/`），再经 `common/fileStorageCommon.py` 上传（红线 R2；`SELFFILE` 可真实落盘验证）；出参 `fileID` 由业务层经 `chCommon.fillFileUrls` 转 URL；**`ch_artifact` 台账写入归 SP3c，本轮不写库**。页面内本地图片一律内联为 data URI（`inlineLocalImages`），保证**本地渲染零对外网络** |
| 凭据加密方案与密钥来源（SP4a） | ★ 算法 **AES-256-GCM**（`common/credentialCipher.py`，`cryptography` 函数内延迟导入）；密钥**仅经环境变量 `CH_CREDENTIAL_KEY`** 注入（本机无 KMS），接受 64 位 hex / base64(32 字节) / 32 字节原文 / ≥16 字节口令(sha256 派生)；**密钥不入库、不入代码库**；`ch_account` 只存 `credentialCipher`(base64 密文+认证标签) 与 `credentialIV`(base64, 12 字节)，**明文永不落库**；解密失败/密钥缺失/密文篡改 → `CredentialCipherError(F0)`，**不静默降级**；日志/审计一律经 `maskSecret` 脱敏；读写闭环：`publishService.saveAccountCredential`（加密写入，明文不落库）+ `decryptAccountCredential`（解密读取），均可选 `rawKey` 传入便于离线自验 |
| 投递前置校验（SP4a） | ★ 投递前**必须**满足三项硬闸门，任一不过即拒绝且不投递：① 平台/通道合法（仅 `wechat_mp`；`xiaohongshu`/`generic` 显式 `C7` 拒绝）；② `ch_artifact` 为 `READY`（传 `artifactID` 时必须就绪，否则 `CB`/`C7`；草稿投递可省，但需 `layoutCode` 现场渲染）；③ **合规校验通过** —— 复用 SP3c 的 `complianceService.publishCheck`（`errCode != B0` 即阻断，返回其原始错误码与问题清单）。闸门顺序：平台 → 账号+凭据 → 产物 → 幂等 → 二次确认 → 自动发布闸门 → 合规 |
| 二次确认参数（SP4a） | ★ 显式参数 `confirmFlag`（必须为真）+ `confirmToken`（必须等于服务端派生值 `buildConfirmToken(idempotencyKey)=sha256("contenthub.publish.confirm:"+key)[:32]`）**必填**；缺失/不匹配 → `F4`，并在 `data` 回显 `idempotencyKey`/`confirmToken` 供前端回填（两步确认）；无前端，故以「接口参数 + 审计留痕」承载人工确认语义；**推送≠发布**：确认只针对「投递草稿」 |
| 撤销窗实现载体（SP4a） | ★ **不依赖 Redis**：`ch_publish_record` 以 `success`（`1`=投递成功 / `0`=失败）+ `delFlag`（`1`=已撤销）+ `pushedYMDHMS` 组合表达状态机；`checkRevokeWindow` 用 `now - pushedYMDHMS <= WECHAT_REVOKE_WINDOW_SECONDS(默认 60)` 判定；窗内撤销置 `delFlag="1"` 并写审计 `publish.revoke`(OK)；逾窗 → `F5`，已撤销 → `F1`，未成功投递 → `C7`；入口为 `publishpush` 的 `action=revoke`（**不新增 CMD**） |
| 转存与草稿接口清单（SP4a） | ★ 平台通道原语全部落在 `processor/platformAdapter/wechatMp.py`（接口基址/路径常量取自 `config/wechatSettings.py::WECHAT_API_BASE/WECHAT_API_PATH`）：`/cgi-bin/token`(access_token，业务层缓存+提前刷新) → `/cgi-bin/media/uploadimg`(正文图转存，返回 `mmbiz.qpic.cn` 地址) → `/cgi-bin/material/add_material`(封面永久素材，换 `thumb_media_id`) → `/cgi-bin/draft/add`(新建草稿，`remoteID`=`media_id`) → `/cgi-bin/freepublish/submit`(**仅三重闸门后由业务层调用**)；**`deliver` 只做草稿**，绝不群发；`engine/inlineStyle.resolveImageUrl/inlineHtml` 新增可选 `transferFunc`：注入即真实转存并就地替换 src，失败/未注入仍显式 `E4`（引擎层仍只依赖标准库） |
| 审计写入规范（SP4a） | ★ 一律经 `processor/auditService.py::writeAudit` 写 `ch_audit_log`：`actor`(loginID) / `source`(`web`\|`api`\|`mcp`) / `action`(`publish.push`\|`publish.revoke`) / `targetType`(`ch_publish_record`) / `targetID`(recID，未落库时用 `idempotencyKey`) / `payloadDigest`(`sha256(canonical json of sanitizePayload(payload))`) / `result`(`OK`\|`FAIL`) / `errMsg` / `costMs` / `ipAddr`(取 `dataSet._IP`，由 `chAPIPost.post` 注入)；**投递成功与失败都要留痕**；`sanitizePayload` 对 `secret/appSecret/credentialCipher/credentialIV/password/token/key` 等字段替换为 `***masked***`、丢弃 `_` 前缀内部字段 —— **凭据明文不入审计**；审计写入失败**不阻断主流程**，但记 error 日志并在出参标注 `auditWritten="0"` |
| 投递通道归属与平台红线（SP4a） | `deliver` 默认实现仍显式未实现（`C2`）；**SP4a 起仅 `wechat_mp(draft_box)` 覆写**（通道调用），`generic`/`xiaohongshu` 继续走默认实现；★ **小红书一律不投递、不发布**：`publishService.NON_DELIVERABLE_PLATFORM_LIST=["xiaohongshu","generic"]` 在取适配器前即显式 `C7` 拒绝，代码中无任何小红书投递/发布路径（S26 静态扫描 + 8.4 上线检查）；`freepublish/submit` 默认关闭（`WECHAT_AUTO_PUBLISH_ENABLED=False`），须「人工二次确认 + `ch_platform.autoPublishFlag=1` + 配置开关=1」三重条件，否则显式 `F6` |
| 幂等键与发布记录（SP4a） | `idempotencyKey` 形态 **`{artifactID}:{accountID}:{uuid4}`**（缺省由服务端生成，可显式传入以复用）；二次提交命中既有键 → `F1` 且**不产生第二条发布记录**（查询前置拦截 + `chCommon.upsertByUniqueKey` 双保险）；发布记录**全字段落库** `ch_publish_record`：`idempotencyKey/artifactId/topicID/accountID/platform/deliverMode/requestJson/responseJson/errcode/errmsg/success/remoteID/operator/pushedYMDHMS`（`requestJson`/`responseJson` 经 `sanitizePayload` 脱敏后写入，JSON 列）；失败原因可读回显（`errcode`/`errmsg` 落库 + 出参 `errMsgList`） |
| 素材包 ZIP 结构与命名顺序（SP4b） | ★ `artifactpack` 产物为 ZIP，条目顺序固定：**有序图片在前**（条目名 `01_<原名去序号前缀><ext>`、`02_`…，**顺序即 App 内左右滑动浏览顺序、与附图 `sortOrder`（即产物 `seqNo`）一致**）→ 其后依次 `title.txt` / `content.txt` / `manifest.json` / `COPYRIGHT.txt` / `RISK_NOTICE.txt` / `SWIPE_TIPS.txt`。文本条目一律 UTF-8 写入。`manifest.json` 含 `topicCode/topicID/title/generatedAt/layoutCode/layoutType/platform/packageKind/deliverMode/imageCount/size/ratio/fileList/extraFileList/checkSum/checkSumMethod`；`checkSum = sha256(按 seqNo 拼接各图片文件 sha256)`；`fileList` 每项含 `seqNo/entryName/fileName/fileID/artifactKey/width/height/sizeBytes/sha256/isCover` |
| 素材包文本口径（SP4b） | ① `title.txt` = `ch_topic.title` 原样（长度由合规闸门按 `ch_platform.titleMaxLen` 判定）；② `content.txt` = 正文 + `#话题标签`（由 `ch_topic.tagList` 生成）+ **当 `aiFlag=1` 且 `ch_platform.needAiLabelFlag=1` 时正文尾部补 AI 创作标识**；③ `COPYRIGHT.txt` = 来源 / 时期 / 作者 + 版权提示（主题未填则给出提示语）；④ `RISK_NOTICE.txt` = 「本素材包需在官方创作服务平台**手动发布**，禁止第三方自动发布」+ 第三方自动发布风险说明；⑤ `SWIPE_TIPS.txt` = 「滑动须在**图片显示区域内**操作（标题栏/评论区无效）」+「老版本 App 需 **8.0+**」 |
| 素材包合规闸门（SP4b） | ★ 导出前**必须**调用 `complianceService.evaluateCompliance`（其内部再复用 `base.checkPlatformSpec` 与 `xiaohongshu.validateSwipeSpec`，**本层不新增第二张规则表**），校验对象为**生效主题**（正文已含话题标签与必要的 AI 标识）与产物列表；`errCode != B0` → **拒绝出包**（返回合规原始错误码，`data.packaged="0"`，**不生成 ZIP、不上传**）。产物取数：`dataSet.products` 优先，其次按 `jobID` / `artifactID(s)` 取 `ch_artifact` 中 `artifactStatus=READY` 的记录（无记录 → `CB`；文件不可取回 → `D4`）；ZIP 经 `fileStorageCommon.saveFile` 上传（失败 → `D3`；组装失败 → `E3`），出参 `fileID` 经 `fillFileUrls` 转 URL；★ **只导出不投递**（`deliverMode=asset_pack`，无任何投递/发布调用） |
| MCP 薄入口与鉴权（SP4b） | ★ `main/subfunc/mcpApi.py::mcpinvoke` 只做「**鉴权 + 工具路由 + 经 `common/chServerCommon.py` 转发下游 `/chapi`**」，**不承载 MCP 协议解析**（不得出现 `jsonrpc`/`tools/call`/`FastMCP`/`toolPathMap`），也**不得改动 `mcpapi/`**。鉴权：token（请求 `token`/`sessionID` 或会话上下文）经 `comDB.getSessionInfo` 取 `roleName`，须 ∈ `settings.ROLE_CMD_LIST`（否则 `G0`）；工具级授权 `settings.MCP_TOOL_LIST[roleName]` 非空且 `toolName` 不在其中 → `G1`；未知工具 → `G2`；下游不可达/异常 → `G3`；转发成功 → `B0` 且 `data.downstream` 回显下游报文与 `downstreamErrCode`。路由表 `TOOL_CMD_MAP` 与 `mcpPost.toolPathMap` 的 8 个只读工具一一对应 |
| MCP 传输与依赖口径（SP4b） | ★ `mcpapi/` 为**独立只读层**（8 tool + 3 resource），协议与鉴权由 `mcp_entry.py`（FastMCP `token_verifier` = `CHTokenVerifier`，Bearer token 即 ylwz sessionID）+ `mcpPost.py` 承载；传输 `streamable-http`（uvicorn `:8891`，ASGI 路径 `/mcp`），**端口一律取 `config/mcpConfig.py::MCP_SERVER_PORT`（8891），`mcp_entry.py` 内不得硬编码**。★ **本轮不联调**（不启动 MCP 服务、不监听端口）：9.6.6 的 ①② 未执行，③–⑩ 直调实现层验证。**依赖必须锁 `mcp>=1.2.0,<2`**（mcp 2.x 已将 `FastMCP` 更名为 `MCPServer` 且鉴权/传输 API 变更，装 2.x 会在导入期直接报错） |
| 凭据巡检阈值与分级（SP4b） | ★ `schedule/credentialCheck.py`：仅对 `PROBE_PLATFORM_LIST = ["wechat_mp"]` 做**只读探活**（`ch_account` → `publishService.decryptAccountCredential` 解密 → `adapter.fetchAccessToken(appID, appSecret)`）；`healthStatus` 判定 = 探活失败/已过期 → `INVALID`，到期日在阈值内 → `EXPIRING`，其余 → `OK`；平台不适用（`xiaohongshu`/`generic`，含小红书无凭据、只导出不投递）→ **跳过并说明且不改写健康状态**；平台配置/适配器不可用 → `UNKNOWN`。阈值 `CH_CREDENTIAL_EXPIRE_WARN_DAYS`（默认 **7** 天）。写出 `healthStatus` + `lastCheckYMDHMS`（跳过项不回写）。★ R-03 分级告警（日志）：`OK→INFO` / `EXPIRING→WARN` / `INVALID→ERROR` / `UNKNOWN→WARN`（`ALERT_LEVEL_MAP`）。Redis 重入锁 `SET NX EX`（不可用 → 进程内锁 + 告警，**不阻塞**）；`__main__` 支持单次执行（`--account-id`/`--platform`/`--json`）。接入 `accounthealth`（`action ∈ {check,refresh,probe}`，**不新增 CMD**） |
| 归档保留期与分批（SP4c） | ★ `schedule/archive.py` 的 `ch_audit_log` 归档按**保留期**（`CH_ARCHIVE_AUDIT_RETAIN_MONTHS`，默认 **24 个月**）筛选 `regYMDHMS` 早于阈值的记录；**分批处理**（`CH_ARCHIVE_BATCH_SIZE`，默认 **5000/批**）**循环执行**，避免长事务（主计划 3.4.6）；保留期/批大小/导出格式（`CH_ARCHIVE_EXPORT_FORMAT` ∈ {`json.gz`(默认), `csv`}）/最大批次数（`CH_ARCHIVE_MAX_BATCH`，0=不限制）**一律可配**（`config/opsSettings.py`） |
| ★★ 破坏性操作 dry-run 与显式确认（SP4c） | ★★ `schedule/archive.py` **默认 dry-run**：未显式确认只打印「将删除/将导出」清单，**不导出、不删除**；真删须显式参数 `--execute` 或环境变量 `CH_ARCHIVE_EXECUTE=1`（`isDryRun()` 判定），并在脚本头与日志显著提示（主计划 8.6 红线：生成器无 migration，误删不可逆）。`tools/runOpsJobs.ps1` 默认 dry-run，`-Execute` 才真删 |
| 先导出后删除（SP4c，强顺序） | ★ 归档**必须先导出（CSV / JSON.gz）并经 `common/fileStorageCommon.py` 上传成功，才允许删除**；导出/上传失败一律**中止本批且不删除**（绝不先删后导）。`ch_audit_log` 删除走 `mysqlCommon.delete_ch_audit_log`（逐条，配合分批），归档批次信息经 `auditService.writeAudit` 留痕 |
| 产物过期清理顺序（SP4c） | ★ `ch_artifact` 过期清理：`expireYMDHMS` 到期且 `artifactStatus=READY` → **先置 `artifactStatus=EXPIRED`，再 `delFile` 删对象**（唯一删除出口 `common/fileStorageCommon.py`）；★ 对象删除失败 → **状态不再二次变更（保持已置的 `EXPIRED`）**、不删除 `ch_artifact` 行、**告警不静默**。`expireYMDHMS` 为空 = 未设置保留期 → 不清理（「0 = 未设置」口径）。台账筛选经手写段 `query_ch_artifact(..., expireBeforeYMDHMS=...)`（缺省 `""` 时条件自动跳过，既有调用零影响） |
| ★ 素材包 ZIP 台账裁定（SP4c，§10 第 5 条收口） | ★ **裁定：素材包 ZIP 不登记 `ch_artifact`**（保持台账语义单一：`ch_artifact` = **渲染产物**台账；`ch_artifact` 的 `artifactKey` 唯一键口径 `{jobID}:{kind}:{platform}:{seqNo}` 与 `jobID NOT NULL` 约束不适配「一次性导出且可多次、无 job 归属」的 ZIP，登记会造成同键覆盖/旧 ZIP 变孤儿对象）。ZIP 生命周期由**对象存储生命周期策略 / 人工保留策略**管理；归档清理**只处理 `ch_artifact` 渲染产物与 `ch_audit_log`**。若后续要将 ZIP 纳入自动清理，须先扩展 `ch_artifact` 语义（新增列 / 专属唯一键约定）并另立子计划 |
| 指标阈值与告警级别（SP4c） | ★ `chmonitor/metrics.py` 七项指标判定为**纯函数**，输出 `{metricName,title,currentValue,threshold,level ∈ {INFO,WARN,ERROR},suggest}`；阈值**全部可配**（`config/opsSettings.py::MONITOR_METRIC_TABLE` + `CH_MONITOR_*` 环境变量，禁止散落硬编码）；边界口径**「恰在阈值不告警、越界才告警」**：渲染失败率（15 分钟窗口 `rate > 10%` → `ERROR`）/ 投递失败率（`rate > 5%` 或连续失败 `>= 3` → `ERROR`）/ 队列积压（最老 `PENDING` 等待 `> 15` 分钟 → `WARN`）/ 凭据健康（`INVALID > 0 → ERROR`，否则 `EXPIRING > 0 → WARN`）/ 存储用量（`> 80% → WARN`）/ 定时任务最后成功（`> 1.5 × 周期 → WARN`，无心跳记录 → `WARN`）/ 审计日增量（今日 `> 3 ×` 昨日 → `WARN`） |
| 告警通道占位口径（SP4c） | ★ `chmonitor/alertChannel.py` 提供**可插拔**通知接口（`AlertChannel` + `ALERT_CHANNEL_MAP`），**默认通道 = `log`**（沿用 `miscCommon.setLogNew` 落盘 `code/log/`）；`email` / `wecom` 为**占位实现**：★ **本轮不发任何网络请求**，`networkRequest` 恒 `"0"`、`sent=0`，仅记录告警意图（接口可注入，上线前再接入真实通道）。通道名经 `CH_MONITOR_ALERT_CHANNEL` 配置；告警发送异常不外抛（不阻断主流程） |
| ★ 监控包命名与 museum 迁移（SP4c） | ★ **命名**：SP4c 监控核心包由 `monitor/` **重命名为 `chmonitor/`**（`schedule/`、`test/`、`tools/runOpsJobs.ps1`、`config/opsSettings.py` 与本文档引用同步更新）；`monitor/` 名称让给 museum 迁移代码。★ **迁移来源**：`museum/code/src/monitor`（`monitor.py` / `alert.py` / `monitorConfig.py` / `crontab.txt` / `restore_monitor.sh`）。★ **改造口径（零网络红线）**：保留可复用逻辑（JSON/时间戳/文件变化检测/告警汇总结构与 `run_alert` 入口），**剥离**网络请求、套接字、子进程与进程 kill 原语（原「进程/端口/服务守护」改为**显式不支持并记日志**），**剥离** museum 专属依赖（`mu_` 前缀业务表 / museum 配置），改为复用 `chmonitor.monitorService.collectAllMetrics` 与 `config/opsSettings.py`；`monitor/` 与 `chmonitor/` **均纳入 S23/S28 零网络扫描**（S28 另断言无 `mu_`/`museumSettings`/子进程原语残留） |
| 归档/清理审计留痕（SP4c） | ★ 归档与清理动作**本身必须写 `ch_audit_log`**：`processor/auditService.py` 新增 `ACTION_ARCHIVE_AUDIT_LOG="archive.audit_log"` / `ACTION_ARCHIVE_ARTIFACT="archive.artifact_purge"` 与 `TARGET_TYPE_AUDIT_LOG="ch_audit_log"` / `TARGET_TYPE_ARTIFACT="ch_artifact"`；操作者取 `CH_OPS_ACTOR_LOGINID`（默认 `charchive`）。**每批**归档/清理均留痕（谁在何时删了什么），删除失败批次 `result=FAIL` |

---

## 5. 配置项清单

### 5.1 环境映射（改环境只改 `config/local_settings.py` 的 `_SYS`）

| `_SYS` | 用途 | `FILE_SYSTEM_MODE` | MySQL 库 |
|---|---|---|---|
| `local` | 本地开发 | `SELFFILE` | `contenthub_data` |
| `home` | 个人环境 | `SELFFILE` | `contenthub_data` |
| `test_server` | 测试环境 | `SELFFILE` | `contenthub_test` |
| `server_01` | 生产 A | `ALIOSS` | `contenthub_data` |
| `server_02` | 生产 B | `TENCENT` | `contenthub_data` |

### 5.2 新增配置项

| 文件 | 关键项 | 说明 |
|---|---|---|
| `config/mysqlSettings.py` | `MYSQL_WRITE_*` / `MYSQL_READ_*` | host/port/db/user/passwd；库名 `contenthub_data`（测试为 `contenthub_test`） |
| | `MYSQL_SKIP_CONNECT`（环境变量） | `=1` 时 `mysqlDB = None`，导入不建连（CI / 静态检查 / 仅走 HTTP 的进程） |
| | `CH_MYSQL_WRITE_PASSWD` / `CH_MYSQL_READ_PASSWD`（环境变量） | 口令不入代码库；未设置时仅本地环境回落开发默认值 |
| | `mysqlReconnect()` | 连接失效时重建 |
| `config/wechatSettings.py` | `WECHAT_API_BASE` / `WECHAT_API_PATH` | 接口基址与 5 个接口路径常量（accessToken / materialAdd / uploadImg / draftAdd / freePublishSubmit） |
| | `WECHAT_APP_ID` / `WECHAT_APP_SECRET` / `WECHAT_SERVER_TOKEN` / `WECHAT_ENCODING_AES_KEY` | 一律取环境变量 `CH_WECHAT_*`，本期为空 |
| | `WECHAT_TEMPLATE_ID` / `WECHAT_HTTP_TIMEOUT` / `WECHAT_TOKEN_REFRESH_AHEAD_SECONDS` | 模板消息与超时预留；★ SP4a 起 `WECHAT_TOKEN_REFRESH_AHEAD_SECONDS` 真实用于 access_token 提前刷新 |
| | `WECHAT_AUTO_PUBLISH_ENABLED`（环境变量 `CH_WECHAT_AUTO_PUBLISH`，默认 `False`） | ★ SP4a：`freepublish/submit` 总开关，**默认关闭**；与 `ch_platform.autoPublishFlag` + `autoPublishConfirm` 三重条件才允许正式发布 |
| | `WECHAT_REVOKE_WINDOW_SECONDS`（默认 60） | ★ SP4a：撤销窗长度（发布记录状态 + 时间判定，不依赖 Redis） |
| | `WECHAT_CREDENTIAL_KEY_ENV`（`CH_CREDENTIAL_KEY`） | ★ SP4a：凭据 AES-256-GCM 主密钥的环境变量名（密钥不入库/不入代码库） |
| `schedule/credentialCheck.py` | `CH_CREDENTIAL_EXPIRE_WARN_DAYS`（环境变量，默认 7） | ★ SP4b：凭据到期预警阈值（天）；到期日在该阈值内 → `healthStatus=EXPIRING` 并 WARN 告警 |
| | `CH_CREDENTIAL_CHECK_INTERVAL`（默认 3600） | ★ SP4c：`credentialCheck --loop` 常驻轮询间隔（秒）；单次执行不受影响 |
| `config/opsSettings.py` | `CH_ARCHIVE_AUDIT_RETAIN_MONTHS`(24) / `CH_ARCHIVE_BATCH_SIZE`(5000) / `CH_ARCHIVE_EXPORT_FORMAT`(`json.gz`) / `CH_ARCHIVE_MAX_BATCH`(0=不限) / `CH_ARCHIVE_EXECUTE`(默认未设 = **dry-run**) / `CH_ARCHIVE_EXPORT_OBJECT_PREFIX` / `CH_OPS_ACTOR_LOGINID`(`charchive`) | ★ SP4c：归档清理保留期 / 分批大小 / 导出格式 / 破坏性操作确认开关（★ 默认 dry-run）与审计操作者 |
| | `CH_MONITOR_RENDER_WINDOW_MINUTES`(15) / `CH_MONITOR_RENDER_FAILURE_RATE`(0.10) / `CH_MONITOR_PUBLISH_FAILURE_RATE`(0.05) / `CH_MONITOR_PUBLISH_CONSECUTIVE_FAIL`(3) / `CH_MONITOR_QUEUE_BACKLOG_MINUTES`(15) / `CH_MONITOR_STORAGE_USAGE_RATE`(0.80) / `CH_MONITOR_SCHEDULE_GRACE_FACTOR`(1.5) / `CH_MONITOR_AUDIT_GROWTH_FACTOR`(3.0) / `CH_MONITOR_PERIOD_*_SECONDS` / `CH_MONITOR_ALERT_CHANNEL`(`log`) / `CH_MONITOR_DATA_DIR` | ★ SP4c：监控七项阈值 / 定时任务周期 / 告警通道 / 报告与心跳目录（**全部可配，禁止散落硬编码**） |
| `requirements.txt` | `mcp>=1.2.0,<2` | ★ SP4b：MCP 依赖口径锁定（mcp 2.x 更名 `MCPServer` 且鉴权/传输 API 变更，`mcpapi/` 为独立只读层不得改动，装 2.x 导入期即报错） |

---

## 6. 表结构变更流程（必读）

```text
① 改 database/ch_*.txt（唯一数据源）
② cd code/src/database && python mysqlCodeGenerator.py -i ch_topic.txt -t topic
   （批量：cd code/src && powershell -File tools/genTableCode.ps1）
③ cd code/src && python tools/mergeMysqlCommon.py      # 覆盖 mysqlCommon.py 的自动生成区
④ 若新增/调整了检索列或 short 列，手工同步 mysqlCommon.py 手写段的 query_ch_* 与 CH_QUERY_SHORT_COLUMNS
⑤ 若新增 JSON 列，登记 MYSQL_JSON_COLUMN_NAME_LIST
⑥ 测试库执行 tools/initTables.py 验证；生产库改表须「备份 + 演练 + 保留回滚 DDL」
```

**生成器使用红线（已实测确认）**

1. **只走 `readFromFile()` 路径**（`-i ch_*.txt`），绝不传原生 `CREATE TABLE` SQL，不使用 `handleSQL()` / `mysqlStatementHandle()`（参数错位会产出非法函数名并丢主键）。
2. **必须在 `code/src/database` 目录下执行并传裸文件名**：生成器用 `fileName.split(".")[0]` 取表名，产物目录为相对路径 `auto_generated`；若传 `database/ch_topic.txt`，表名会变成 `database/ch_topic`。
3. **`-t` 取「去 `ch_` 前缀 + 去全部下划线」**（`ch_audit_log` → `auditlog`），否则会生成 `funcAudit_logAdd` 这类与 `basicSettings._CRUD_TITLES` 对不上的处理器名。
4. 定义文件写法：单空格分隔、禁制表符；`COMMENT` 内不得出现 `%`（会被替换为全角）；不得出现 `#`（会被当成注释截断）；首字段固定 `recID BIGINT AUTO_INCREMENT PRIMARY KEY`；尾部七字段顺序不可变。
5. 生成器不支持复合唯一键 / 外键 / 分区 → 唯一性由「应用层拼接单列 + 内联 `UNIQUE`」承担。
6. 生成器写文件未指定编码：Windows 下产物为 GBK，Linux 下为 UTF-8。`tools/mergeMysqlCommon.py` 已做 utf-8 → gbk 容错解码并统一以 UTF-8 写回。

---

## 7. 端点映射（SP1.5 装配 + SP2a 主题域接管 + SP2b 素材域接管 + SP2c 渲染域接管 + SP3a 平台适配〔无新增端点〕+ SP3c 合规/任务化〔无新增端点〕+ SP4a 投递〔无新增端点〕+ SP4b 素材包/MCP/巡检〔无新增端点〕+ SP4c 归档/监控〔无新增端点〕）

| 表 | `_CRUD_TITLES` | add / del / modify / qry | 归属（已验证对齐） |
|---|---|---|---|
| `ch_topic` | `topic` | topicadd / topicdel / topicmodify / topicqry | ★ SP2a 起由 `subfunc/topicApi.py` 接管 → `processor/topicService.py`（**不再装配进 crudApi**） |
| `ch_topic_asset` | `topicasset` | topicassetadd / … / topicassetqry | ★ SP2b 起由 `subfunc/assetApi.py` 接管 → `processor/assetService.py`（**不再装配进 crudApi**） |
| `ch_asset` | `asset` | assetadd / … / assetqry | ★ SP2b 起由 `subfunc/assetApi.py` 接管 → `processor/assetService.py`（**不再装配进 crudApi**） |
| `ch_layout` | `layout` | layoutadd / … / layoutqry | `funcLayout*` |
| `ch_platform` | `platform` | platformadd / … / platformqry | `funcPlatform*` |
| `ch_render_job` | `renderjob` | renderjobadd / … / renderjobqry | `funcRenderjob*` |
| `ch_artifact` | `artifact` | artifactadd / … / artifactqry | `funcArtifact*` |
| `ch_account` | `account` | accountadd / … / accountqry | `funcAccount*` |
| `ch_publish_record` | `publishrecord` | publishrecordadd / … / publishrecordqry | `funcPublishrecord*` |
| `ch_mcp_token` | `mcptoken` | mcptokenadd / … / mcptokenqry | `funcMcptoken*` |
| `ch_audit_log` | `auditlog` | auditlogadd / … / auditlogqry | `funcAuditlog*` |
| `ch_topic_version` | `topicversion` | topicversionadd / … / topicversionqry | ★ SP2a 起由 `subfunc/topicApi.py` 接管 → `processor/topicService.py`（**不再装配进 crudApi**） |

**产物接口处理段的去向**：`database/auto_generated/auto_gen_code_ch_*.py` 中的 `func{Title}{Add/Del/Modify/Qry}` 由 **SP1.5** 装配进 `main/subfunc/crudApi.py`：装配工具 `tools/mergeCrudApi.py` 从产物的 `#http interface code begin/end` 段抽取处理器 + 依据 `_CRUD_TITLES` 派生 `CMD_MAP`，写入 `crudApi.py` 的 `#===== auto-generated crud sections begin/end` 生成区（生成件豁免单文件行数上限）。手写头部（符号导入）与生成区物理隔离，重跑生成器/装配工具不覆盖手写代码。

**SP2a / SP2b 的接管排除**：`tools/mergeCrudApi.py` 的 `EXCLUDED_TABLE_LIST = ["ch_topic", "ch_topic_version", "ch_asset", "ch_topic_asset"]`——前两张表的端点由 `subfunc/topicApi.py`（内部 `processor/topicService.py`）接管，后两张表的端点由 `subfunc/assetApi.py`（内部 `processor/assetService.py`）接管，故 crudApi 只装配其余 8 张表 = **32 条 CMD**。若两侧同时登记同名 CMD，聚合器 `mergeCmdMaps` 的 V1 冲突校验会在**导入期**直接抛 `RuntimeError`（服务起不来），因此「排除表」与「接管端点」必须成套完成（只补一半等于服务起不来），这是硬约束。产物文件与 12 份 `word_table_*.csv` 仍按原样保留，不删除。

**SP2c 的归属迁移**：`topicrender` 为业务端点（非 CRUD），原登记在 `subfunc/topicApi.py` 且返回 `C2` 占位；SP2c 起迁至 `subfunc/renderApi.py`（内部 `processor/renderService.py` → `engine/layoutEngine.py`）。迁移必须**成套**：从 `topicApi.CMD_MAP` / `TOPIC_CMD_LIST` 移出（9→8）与在 `renderApi.CMD_MAP` 登记（0→1）同时完成，否则聚合器 V1 冲突或 V3 缺项会在导入期抛错。迁移后 `CMD_OWNER["topicrender"] == "render"`，总数仍 69。

**SP3a 不变式确认（平台适配层不新增端点，硬约束）**：SP3a 只在 `processor/renderService.py` 内为 `topicrender` 增加 `platform` / `renderMode` / `exportKind` 入参，并在 `processor/platformAdapter/*` 与 `engine/inlineStyle.py` 落地平台适配能力；**不新增 CMD、不改动任何域文件的 `CMD_MAP`、不改 `subfunc` 聚合器**。聚合器实测仍为 `CMD total=69`，分布 `{account:16, crud:32, topic:8, asset:9, render:1, publish:1, compliance:1, mcp:1}`，`CMD_OWNER["topicrender"]=="render"`。静态 S23 以 AST 断言 `renderApi.CMD_MAP == ["topicrender"]`（防回归）。

**SP3b 不变式确认（小红书产物渲染不新增端点，硬约束）**：SP3b 只在 `processor/platformAdapter/xiaohongshu.py`（新增适配器）+ `engine/htmlToImage.py`（新增截图管线）落地小红书能力，并把 `xiaohongshu` 登记进 `ADAPTER_MODULE_MAP`；**不新增 CMD、不改动任何域文件的 `CMD_MAP`、不改 `subfunc` 聚合器、不改 `renderApi` 路由表**。聚合器实测仍为 `CMD total=69`，分布 `{account:16, crud:32, topic:8, asset:9, render:1, publish:1, compliance:1, mcp:1}`，`CMD_OWNER["topicrender"]=="render"`；适配器注册表 `["generic","wechat_mp","xiaohongshu"]`。静态 S24 断言 `ADAPTER_MODULE_MAP` 已登记 `xiaohongshu` 且 `renderService` 无 `xiaohongshu` 硬编码（选适配器一律走工厂）。

**SP3c 不变式确认（合规校验 + 产物台账 + 渲染任务化不新增端点，硬约束）**：SP3c 只在 `processor/complianceService.py`（新增 C8 合规服务）+ `processor/renderService.py`（扩展：`ch_render_job` 状态机 + `inputHash` 复用 + `ch_artifact` 台账）+ `schedule/renderWorker.py`（新增调度层）+ `main/subfunc/complianceApi.py`（把 `publishcheck` 从占位替换为真实实现）落地；**不新增 CMD、不改动任何域文件的 `CMD_MAP`、不改 `subfunc` 聚合器、不改 `renderApi` 路由表**。聚合器实测仍为 `CMD total=69`，分布 `{account:16, crud:32, topic:8, asset:9, render:1, publish:1, compliance:1, mcp:1}`，`CMD_OWNER["topicrender"]=="render"`。静态 S25 断言 `complianceApi.CMD_MAP == ["publishcheck"]`、`PLACEHOLDER_CMD_LIST = []`、`renderApi.CMD_MAP == ["topicrender"]`（防回归）。

**SP4a 不变式确认（C6 投递链路不新增端点，硬约束）**：SP4a 只在 `processor/publishService.py`（新增 C6 编排）+ `processor/auditService.py`（新增审计留痕）+ `common/credentialCipher.py`（新增凭据加密）+ `processor/platformAdapter/wechatMp.py`（通道调用与 `deliver` 实现）+ `engine/inlineStyle.py`（`transferFunc` 真实转存分支）+ `main/subfunc/publishApi.py`（把 `publishpush` 从占位替换为真实实现）落地；**不新增 CMD、不改动任何域文件的 `CMD_MAP`、不改 `subfunc` 聚合器、不改 `renderApi` 路由表**。聚合器实测仍为 `CMD total=69`，分布 `{account:16, crud:32, topic:8, asset:9, render:1, publish:1, compliance:1, mcp:1}`，`CMD_OWNER["publishpush"]=="publish"`。静态 S26 断言 `publishApi.CMD_MAP == ["publishpush"]`、`PLACEHOLDER_CMD_LIST = []`（防回归），并断言 `publishService` 对 `xiaohongshu` 显式拒绝（平台红线）。

**SP4b 不变式确认（素材包 ZIP + MCP 薄入口 + 凭据巡检不新增端点，硬约束）**：SP4b 只在 `processor/artifactService.py`（新增素材包导出）+ `main/subfunc/assetApi.py`（把 `artifactpack` 从占位替换为真实实现）+ `main/subfunc/mcpApi.py`（把 `mcpinvoke` 从占位替换为真实实现，仅做鉴权/路由/转发）+ `schedule/credentialCheck.py`（新增巡检）+ `main/subfunc/accountApi.py`（在 `accounthealth` 同一处理函数内以 `action` 承接巡检，**不新增处理函数**）+ `common/errMsgCommon.py`（G 段追加 `G2`/`G3`）落地；**不新增 CMD、不改动任何域文件的 `CMD_MAP`、不改 `subfunc` 聚合器、不改 `renderApi` 路由表、不改 `mcpapi/`**。聚合器实测仍为 `CMD total=69`，分布 `{account:16, crud:32, topic:8, asset:9, render:1, publish:1, compliance:1, mcp:1}`，`CMD_OWNER["artifactpack"]=="asset"`、`CMD_OWNER["mcpinvoke"]=="mcp"`、`CMD_OWNER["accounthealth"]=="account"`。静态 S27 断言 `assetApi.PLACEHOLDER_CMD_LIST == []`、`mcpApi.PLACEHOLDER_CMD_LIST == []`、`accountApi.CMD_MAP` 未变、端点静态合计 69（防回归）。

**SP4c 不变式确认（归档清理 + 监控告警 + 巡检守护化不新增端点，硬约束）**：SP4c 只在 `schedule/archive.py`（新增归档清理）+ **`chmonitor/`**（新增监控核心：`metrics`/`alertChannel`/`heartbeat`/`monitorService`/`dailyCheck`；★ 原名 `monitor/`，本轮重命名）+ **`monitor/`**（由 `museum/code/src/monitor` 迁移改造为 contentHub 口径：文件变化守护 + 告警汇总 + 部署样例）+ `schedule/credentialCheck.py`（守护化 `--loop`，**不新增处理函数**）+ `config/opsSettings.py`（新增运维配置）+ `common/mysqlCommon.py`（手写段 `query_ch_artifact` 增可选 `expireBeforeYMDHMS`）+ `processor/auditService.py`（追加归档动作常量）+ `tools/runOpsJobs.ps1` 落地；**不新增 CMD、不改动任何域文件的 `CMD_MAP`、不改 `subfunc` 聚合器、不改 `renderApi` 路由表、不改 `mcpapi/`**。聚合器实测仍为 `CMD total=69`，分布 `{account:16, crud:32, topic:8, asset:9, render:1, publish:1, compliance:1, mcp:1}`。静态 S28 断言归档默认 dry-run / 先导出后删除 / 产物先置 EXPIRED 后 delFile / 审计留痕 / 七项指标与阈值可配 / 告警通道占位零网络 / 守护化入口 / **`monitor/` 迁移改造（零网络 + 无 museum 依赖残留 + 复用 `chmonitor`）**，且 S23 零网络扫描同步纳入 `chmonitor/` 与 `monitor/`（防回归）。

**重跑装配后的实际端点总数（以聚合器输出为准，不手数）**：`MYSQL_SKIP_CONNECT=1 python -c "import sys; sys.path.insert(0,'main'); import subfunc; print(len(subfunc.CMD_MAP))"` → **69**；按域分布 `{"account": 16, "crud": 32, "topic": 8, "asset": 9, "render": 1, "publish": 1, "compliance": 1, "mcp": 1}`（SP2c 起 `topicrender` 由 `renderApi` 接管，主题域 9→8、渲染域 0→1；SP3c 起 `compliance` 域仍 1 条，仅由占位变为真实实现；SP4a 起 `publishpush` 由占位变为真实实现；SP4b 起 `artifactpack`/`mcpinvoke` 由占位变为真实实现，素材域与 MCP 域计数不变）。

**生成的 REST 处理函数对数据层存在三种调用形式**（已实测确认，手写 `query_ch_*` 已兼容）：
`query_ch_X(tableName)` / `query_ch_X(tableName, recID, mode=mode)` / `query_ch_X(tableName, mode=mode)`。

---

## 8. 基线实测差异登记（D1–D4）

| # | 项 | 结论 | 本轮处置 |
|---|---|---|---|
| **D1** | `mysqlHandle` 连接模型 | 为 pymysql **单条长连接注入式**（`dbW`/`dbR`），**非连接池**；连接由 `config/mysqlSettings.py` 构造后注入 | 沿用现状；Web 进程与 worker 各自独立持有；并发压力上升时在 SP3 评估引入连接池 |
| **D2** | 三文件适配器签名不一致 | `aliyunOSS` / `tencentCOS` / `selfFileCommon` 的 upload/download/info/tempUrl 签名与返回值均不同 | **已由 `common/fileStorageCommon.py` 的 shim 层消化**（本轮未改动该文件） |
| **D3** | Redis 查询缓冲函数位置错位 | `genBufferIndexKey` / `putQuery2Buffer` / `getQueryBufferComplte` 实际在 museum 的 `main/museumAPIPost.py`，不在 `common/redisCommon.py` | **SP1.5 已移植**到 `common/queryBufferCommon.py`，并补齐生成件同样依赖的 `chkBufferExist` / `useQueryBufferFlag` / `chkNeedFlashQuery` / `genBufferToken`；只调用 `redisCommon` 既有缓冲函数，未改其逻辑，也未落在 `chCommon.py`（其文件头已声明不属于该文件） |
| **D4** | `F4A0` 长图拼接能力 | 未在基线检索到命令字定义位置，能力未验证 | 登记待实测；兜底方案 = Playwright 整页截图 / Pillow 纵向拼接（SP3 落地） |

---

## 9. 子计划切分与后续落点

| 子计划 | 内容 | 状态 |
|---|---|---|
| **SP1** | Phase 0 数据库链路（12 表 + 生成器 + mysqlCommon + 建表/种子/联调脚本 + 静态验收） | **本轮完成** |
| **SP1.5** | S2 拆分：`main/chAPI.py` + `main/chAPIPost.py`（230 行瘦入口）+ `main/subfunc/`（12 文件：聚合器三道校验 / context / apiCommon / accountSvcClient / accountApi / crudApi / 6 业务域）+ `tools/mergeCrudApi.py` + `common/accountClient.py` + `common/queryBufferCommon.py` + `common/errMsgCommon.py`（含 `contenthub` msgKey + `funcCommon` re-export） | **本轮完成** |
| **SP2a** | Phase 1 · C2 主题管理（里程碑 M1 第一块）：`processor/topicService.py`（全字段 CRUD + 字段区间校验 + 状态机 + `wordCount` + `topicCode` 幂等 + 详述超长转存）+ `ch_topic_version` 版本快照 + `main/subfunc/topicApi.py` 接管主题域 8 端点 + `tools/mergeCrudApi.py` 排除接管表（crudApi 48→40）+ S20 静态验收 | **本轮完成** |
| **SP2b** | Phase 1 · C3 素材图库（里程碑 M1 第二块）：`processor/assetService.py`（`contentHash` 内容级去重 + 规格裁剪 + EXIF 剥离 + 缩略图 + `fileSystem`/`storageBucket` 快照 + 素材与附图 CRUD）+ `main/subfunc/assetApi.py` 接管素材域 8 端点 + `tools/mergeCrudApi.py` 排除接管表（crudApi 40→32）+ S21 静态验收 | **本轮完成** |
| **SP2c** | Phase 1 · C4 版式引擎（里程碑 M1 最后一块）：`engine/layoutEngine.py`（唯一渲染入口：读 ch_layout → 注入 specJson → Jinja2 → `{outputKind,content,meta}`）+ `engine/imageProc.py`（渲染期派生：封面 900×500 / 卡片 1080×1440 / 长图切片）+ 4 套 Jinja2 模板（`stack_v1`/`carousel_v1`/`longimage_v1`/`swipe_v1`）+ `partials/base` + 站内预览（微信/小红书手机框）+ `processor/renderService.py` 编排 + `main/subfunc/renderApi.py` 接管 `topicrender`（topic 9→8 / render 0→1）+ S22 静态验收 + 真实渲染冒烟 | **本轮完成** |
| **SP2** | Phase 1（其余）：C1 权限收口（C2 已由 SP2a、C3 已由 SP2b、C4 已由 SP2c 交付） | 待开工 |
| **SP3a** | Phase 2 · C5 平台适配层 + 微信产物（里程碑 M2 第一块）：`processor/platformAdapter/`（`base` 契约五方法 + `wechatMp` + `generic`）+ `engine/inlineStyle.py`（class 清洗 / `<style>` 下沉内联 / 外链图片统一出口 / carousel 交互降级）+ `renderService` 平台分支（`platform` 参数化 / `renderMode` sync·job→C2；**不新增 CMD**）+ S23 静态验收 + 平台产物冒烟 | **本轮完成** |
| **SP3b** | Phase 2 · C5 小红书产物渲染（里程碑 M2 第二块）：`engine/htmlToImage.py`（Playwright 截图管线：单实例串行 / 1080×1440 卡片 / 长图整页截图+切片 / 字体预加载 `waitForFonts` / E2·E3）+ `processor/platformAdapter/xiaohongshu.py`（`deliverMode=asset_pack`：swipe 卡片 / longimage·stack 切片 / carousel 显式不可用 / 2.6.3 强校验 / 素材包清单）+ 适配器注册（小红书从 C7 迁移）+ 出参 `products/fileIDs` + S24 静态验收 + **真实截图冒烟**。**C8 合规校验（`complianceService.py`）与 `ch_artifact` 产物台账归 SP3c**（`artifactpack` ZIP 归 SP4） | **本轮完成（C5 小红书部分）** |
| **SP3c** | Phase 2 · C8 合规校验 + 产物台账 + 渲染任务化（**里程碑 M2 收口**）：`processor/complianceService.py`（平台规格/swipe 专项/敏感词/AI 标识/限流降级 + 统一问题清单）+ `ch_artifact` 产物台账 + `ch_render_job` 任务化（`inputHash` 复用 / sync 也建 job / `renderMode=job`）+ `schedule/renderWorker.py`（常驻消费，单实例串行 + Redis 锁可降级）+ `publishcheck` 落地（不新增 CMD） | **本轮完成（M2 收口）** |
| **SP4a** | Phase 3 · C6 公众号草稿投递链路（**里程碑 M3 第一块**）：`common/credentialCipher.py`（AES-256-GCM，密钥走环境变量）+ `processor/auditService.py`（`ch_audit_log` 留痕）+ `processor/publishService.py`（C6 编排：通道判定/凭据解密/产物 READY/幂等/二次确认/撤销窗/合规闸门/token 缓存刷新/落库/审计）+ `wechatMp.deliver`（通道调用）+ `inlineStyle.transferFunc`（真实转存分支）+ `publishApi.publishpush`（不新增 CMD）+ S26 静态验收 + 8 项投递冒烟 | **本轮完成（M3 第一块；★ 未端到端打通真实平台，详见 §1 凭据现状声明）** |
| **SP4b** | Phase 3 · 素材包 ZIP + MCP 接入 + 凭据巡检（**里程碑 M3 第二块**）：`processor/artifactService.py`（7.8 素材包 ZIP：有序图片 + `title.txt`/`content.txt`/`manifest.json`/`COPYRIGHT.txt`/`RISK_NOTICE.txt`/`SWIPE_TIPS.txt`；**未过合规校验不出包**；**只导出不投递**）+ `assetApi.artifactpack` 落地 + `mcpApi.mcpinvoke` 薄入口（仅鉴权/路由/经 `chServerCommon` 转发）+ **MCP 端口固定 8891（★ 本轮不联调：不启动服务/不监听端口，9.6.6 ①②未执行、③–⑩ 直调验证）** + `schedule/credentialCheck.py`（公众号只读探活 + `healthStatus` 四级 + R-03 分级告警 + 小红书跳过；Redis 锁可降级）+ `accounthealth` 接线 + G2/G3 错误码 + `mcp<2` 依赖口径 + S27 静态验收 + 7 项冒烟 | **本轮完成（M3 第二块；真实执行/桩验证边界见 §1 SP4b 口径声明）** |
| **SP4c** | Phase 3 · 归档清理 + 监控告警 + 巡检守护化（**里程碑 M3 第三块**）：`schedule/archive.py`（`ch_audit_log` 分批导出+删除 / `ch_artifact` 过期清理；★ **默认 dry-run + 显式确认**；★ 先导出后删除；★ 先置 `EXPIRED` 再 `delFile`）+ `chmonitor/`（七项指标〔渲染失败率 / 投递成功率 / 渲染队列积压 / 凭据健康 / 存储用量 / 定时任务最后成功时间 / 审计日增量〕+ **可插拔告警通道（占位、零网络）** + 每日巡检脚本；★ 原名 `monitor/`）+ `monitor/`（由 `museum/code/src/monitor` 迁移改造：文件变化守护 + 告警汇总；零网络）+ `schedule/credentialCheck.py` 守护化（`--loop`）+ `config/opsSettings.py` + `tools/runOpsJobs.ps1` + S28 静态验收 + 5 项冒烟 | **本轮完成（M3 第三块；真实执行/桩验证边界见 §1 SP4c 口径声明；★ v1.0 验收〔E2E / 并发压测 / 恢复演练 / 上线检查〕仍待开工）** |
| **SP5** | 前端 `code/webserver`（Vue3 + Element Plus + Tailwind，依据 `plan/UI/contentHub UI 设计.md`） | 待开工 |

> **M3 进度（Phase 3）**：M3 = **C6 投递链路（SP4a，已完成）+ 素材包 ZIP / MCP 接入 / 凭据巡检（SP4b，已完成）+ 归档清理 / 监控告警 / 巡检守护化（SP4c，已完成）**。**M3 三块全部落地**；★ **M3 出口尚欠项**（真凭据投递打通 / M2 真机排版 / MCP 服务端联调 / 归档监控连库端到端 / 监控通道真实连通，见 §10）需在有环境或人工条件下补做；**v1.0 验收（E2E / 并发压测 / 恢复演练 / 上线检查）未开工**。

**SP1.5 落点提示（避免返工）**：`subfunc/__init__.py` 的聚合器必须做三道校验（CMD 冲突 / 处理函数可调用 / 与 `ROLE_CMD_LIST ∪ NO_SESSIONID_CMD_LIST` 完整性比对）；`crudApi.py` 只放生成件；`apiCommon.py` 保持零业务；`chCommon.py` 必须被真实引用（防「建而不用」）。**以上四项已全部落实**并由静态验收 S13–S18 锁定（详见 §1 验收结论）。

**SP1.5 → C1/SP2 的交接事项（务必先读）**：

1. **新增业务端点只改自己的域文件**：在 `subfunc/{domain}Api.py` 的 `CMD_MAP` 里登记即可，聚合器自动合并并做三道校验；**不要直接改 `chAPIPost.py`**（其职责仅聚合与编排）。
2. **占位端点待补齐**：★ **全部清零** —— `publishpush` 已于 SP4a 落地；**`artifactpack` / `mcpinvoke` 已于 SP4b 落地**（素材包 ZIP / MCP REST 薄入口）；`accounthealth` 已实现（汇总 `ch_account.healthStatus`，SP4b 起可用 `action=check|refresh|probe` 触发凭据巡检）；`topicrender` 已于 SP2c/SP3a/SP3b/SP3c 落地（C4 渲染 + C5 平台适配 + 产物 + 任务化）；`publishcheck` 已于 SP3c 落地（C8 合规闸门）。当前 `PLACEHOLDER_CMD_LIST` 仅剩账号域 `genusersessionid` / `gethomepagedata`。
3. **账号域占位 2 个**：`genusersessionid` / `gethomepagedata` —— museum 基线**无对应实现**（仅有前端调用或权限声明），待产品定义后再落地（`accountApi.PLACEHOLDER_CMD_LIST` 已登记）。
4. **降级实现 3 个**：`chkuserexist` / `getuserinfo` / `usersearch` + `userinfoqry` —— museum 走本地用户表 `comMysql.queryUserBasic`（contentHub 无此表，`ch_account` 是「发布平台账号」而非系统用户），现改为「账号服务 A3A0/AIA0 + Redis 用户档案」双源；用户量级上来后需改走账号服务侧检索接口。`getuserinfo` 的 `avatarID` 出参经文件门面转 URL。
5. **落库队列无消费者**：`registration`/`login` 仍按基线语义写 `comDB.putMsg2Queue("CH_MYSQL", saveSet)`（常量 `MSG_QUEUE_KEY_CH_MYSQL`），contentHub 的 mysql-writer 消费者尚未落地，当前仅作审计留痕。
6. **一处有意的行为修正**（已在代码注释登记）：`calUserCMDMapKeyList` 改为「先拷贝入参再合并免登录集合」，修掉基线 `CMDList += settings.NO_SESSIONID_CMD_LIST` 污染模块级列表的缺陷；`logout` 的 `roleName` 补齐了 `sessionIDSet` 回落（基线仅取 `dataSet`，该路径恒判 `B8`）。
7. **★ 2026-09-20 账号域端点扩容（69 → 72）**：补齐 museum 账号域三个**管理员专用**端点（首轮移植遗漏 —— `plan/chAPIPost分拆方案.md` §1.4/1.5 的 23 CMD 清单里有，contentHub 首轮只落 16 条，此前无决策登记）：
   - `useradd`（`accountApi.funcUserAdd`，管理员添加用户 → 账号服务 `A0A0` 建号）/ `usermodify`（`funcUserModify`，改角色 → `AEA0`）/ `userdel`（`funcUserDel`，删除用户）；
   - **权限口径**：三者**仅管理员（administrator 或 manager）**可调 —— 请求级授权由 `config/basicSettings.py::USER_ADMIN_ROLE_LIST = ["administrator", "manager"]` 驱动 `ROLE_CMD_LIST`（下方循环自动追加）；处理器级二次校验**统一复用公共件 `common/funcCommon.py::chkIsManager(roleName)`**（不再自建角色清单），两处口径一致；`useradd` **与 `registration` 完全独立**（自助注册对所有角色开放，用户增/改/删仅管理员），非管理员一律 `BG`（权限不足）；
   - **生产者/消费者对齐**：三端点成功后分别投递落库队列 `useradd` / `usermodify` / `userdel`（消费者 `processor/transferCHMysql.py`），至此消费端 6 个 CMD 中 **5 个有生产者**（`putdatabufferlist` 仍无 —— contentHub 查询缓冲为进程内同步写，不做队列异步转存）；
   - **已知边界（不静默）**：contentHub 账号服务**未提供「删除用户」CMD**（仅 A0A0/A2A0/A3A0/A5A0/A6A0/A7A0/A9A0/AIA0/AEA0/G1A0/G2A0/GAA0），故 `userdel` 只删本地 `USER_BASIC`（经队列异步执行），出参显式回显 `accountSvcDelete="0"`；`usermodify` 本轮只支持**角色变更**（`AEA0`），其余资料字段待账号服务提供对应能力；
   - **验收期望同步**：`test/test_ch_phase0_static.py` 的 `ACCOUNT_CMD_LIST` 16 → 19、`SP4B_ENDPOINT_TOTAL` 69 → 72（S27 实测输出 `CMD total=72`；S13 行数上限 `accountApi.py` 886/900 仍满足）。

**SP2a 落地结论（C2 主题管理）**：

1. **分层落点**：`main/subfunc/topicApi.py`（接入/报文封装）→ `processor/topicService.py`（业务规则）→ `common/mysqlCommon.py`（唯一数据入口）。接入层只做「会话上下文 + `apiCommon.genRtnResult` 封装 + 异常兜底」，业务规则一律在 `topicService`，**topicApi 不拼 SQL、不直接调 `mysqlCommon`**。
2. **端点接管**：`topic{add/del/modify/qry}` 与 `topicversion{add/del/modify/qry}` 共 8 条由 `topicApi.CMD_MAP` 提供（`TOPIC_CMD_LIST` 常量登记）；`topicrender` 仍返回 `C2` 占位（归 SP2c/SP3）。crudApi 经 `tools/mergeCrudApi.py::EXCLUDED_TABLE_LIST` 排除这两张表 → 40 条 CMD；端点总数保持 **69**。
3. **错误码落点**：字段必填/超长/越界/取值非法 → `C4/C5/C6/C7`；重复/无记录 → `CA/CB`；转存失败/超限 → `D1/D3`；**版本快照落库失败 → `CG`**（复用 `contenthub` 继承自 `default` 的「记录添加失败」，不得错用 `D3`——快照失败是写入失败而非文件上传失败，错用会让 `topicversionadd` 回显「文件上传失败」而误导排查）。全部为 `contenthub` 消息表中真实存在的键（S20 以 exec errMsgCommon 校验），并统一 `msgKey="contenthub"`。
4. **幂等与快照**：`topicCode` 幂等走 `chCommon.upsertByUniqueKey`（命中更新 / 未命中插入）；每次保存成功后在 `ch_topic_version` 落一条快照（`verKey={topicID}:{versionNo}`，`versionNo` 从 1 递增，同样经 `upsertByUniqueKey`）。快照失败**不回滚**主题（主题数据优先），但必须记 error 日志（不静默）。
5. **详述超长转存**：`description` 字数 >5000 时写临时文件 → `fileStorageCommon.saveFile`（函数内延迟导入，仅转存路径依赖云 SDK）→ 写 `descriptionFileID`；库内 `description` 保留**有界前缀预览**（5000 字符）而非置空——因生成器产出的 `update_ch_topic` 对空串会跳过，「置空」在更新路径上无法生效。转存失败返回 `D3`，**绝不静默截断**。
6. **状态机**：`TOPIC_STATUS_TRANSITIONS` 单向推进为主，允许 `RENDERING→DRAFT`、`RENDERED→RENDERING/DRAFT` 回退，`ARCHIVED` 为终态；同状态保存视为幂等合法。非法跃迁返回 `C7`，`data.currentStatus` 回显当前状态。
7. **出参收口**：`topicService` 出参统一经 `chCommon.fillFileUrls`（`descriptionFileID→descriptionUrl`、`coverFileID→coverUrl` 等）；`chAPIPost.fillFileUrlsInResult` 会再收口一次（幂等，不覆盖 fileID 字段本身）。

**SP2b 落地结论（C3 素材图库）**：

1. **分层落点**：`main/subfunc/assetApi.py`（接入/报文封装）→ `processor/assetService.py`（业务规则）→ `common/mysqlCommon.py`（唯一数据入口）；文件访问只经 `common/fileStorageCommon.py`。接入层只做「会话上下文 + `apiCommon.genRtnResult` 封装 + 异常兜底」，**assetApi 不拼 SQL、不直接调 mysqlCommon、不做厂商分支**。
2. **端点接管**：`asset{add/del/modify/qry}` 与 `topicasset{add/del/modify/qry}` 共 8 条由 `assetApi.CMD_MAP` 提供（`ASSET_CMD_LIST` 常量登记）；`artifactpack` 仍返回 `C2` 占位（归 SP3）。crudApi 经 `tools/mergeCrudApi.py::EXCLUDED_TABLE_LIST` 排除这两张表 → 32 条 CMD；端点总数保持 **69**（聚合器实测输出，见 §7）。
3. **内容级去重（`contentHash`）**：`sha256` 取**原始字节**（非裁剪后字节），命中即复用既有素材并回显 `dedupHit="1"`（幂等，不产生重复记录）；未命中才走「规格裁剪 → EXIF 剥离 → 缩略图 → 上传 → 落库」。`ch_asset.contentHash` 为 `UNIQUE`，落库经 `chCommon.upsertByUniqueKey`。
4. **规格裁剪与 EXIF 剥离**：尺寸口径取 `settings.MAX_PIC_SIZE` / `settings.THUMBNAIL_SIZE`（配置驱动，不硬编码）；只缩不放（小图不放大失真）；EXIF 剥离通过「重建像素另存」实现（PIL 默认不写 exif/GPS）。**Pillow 缺失或处理失败一律降级为原样上传**（`processStatus=RAW`）并记日志，不阻断上传、不上抛异常。
5. **三后端切换（红线 R2）**：上传/缩略图统一走 `fileStorageCommon.saveWithThumbnail`（内部 `buildThumbnail` + `saveFile`），桶解析走 `fileStorageCommon.resolveBucket`；`fileSystem` 落库为**落库时后端快照**、`storageBucket` 为桶快照，保证中途切桶后历史文件仍可正确读取（§4 文件引用约定）。
6. **附图绑定（`ch_topic_asset`）**：`assetKey = {topicID}:{fileID}` 幂等（重复绑定同一素材不产生重复记录）；`sortOrder` 越小越靠前（`queryTopicAsset` 在业务层显式排序，不依赖数据层 `order` 取值口径）；`usageType ∈ {cover, body, inline}`，**封面唯一**——同一主题绑定新封面时把旧封面降级为 `body`（`demoteOtherCoverAssets`），批量重排由 `reorderTopicAssets` 承担（`orderList` 入参）。
7. **错误码落点**：字段必填/超长/越界/取值非法 → `C4/C5/C6/C7`；重复/无记录 → `CA/CB`；文件类型不允许 → `D0`；超规格 → `D1`；上传失败 → `D3`；文件不存在 → `D4`。全部为 `contenthub` 消息表中真实存在的键（S21 以 exec errMsgCommon 校验），并统一 `msgKey="contenthub"`。
8. **落库快照不可改**：`fileID` / `contentHash` / `fileSystem` 为落库快照字段，`assetmodify` 传新值一律 `C7`（避免改哈希绕过内容级去重、改后端标识导致历史文件路由错乱）；附图绑定的 `topicID` / `fileID` / `assetKey` 同理不可改。

**SP2c 落地结论（C4 版式引擎）**：

1. **分层落点**：`main/subfunc/renderApi.py`（接入/报文封装）→ `processor/renderService.py`（业务编排：取主题+附图）→ `engine/layoutEngine.py`（唯一渲染入口）→ `common/mysqlCommon.py`（只读 ch_layout）。引擎层**不 import processor/subfunc**（S22 反向依赖检查锁定），主题/附图由业务层取好后传入 —— 这是「单向依赖 subfunc → processor → engine → common」在渲染链路上的落点。
2. **端点接管与归属迁移**：`topicrender` 由 `renderApi.CMD_MAP` 提供（`RENDER_CMD_LIST` 常量登记）；从 `topicApi.CMD_MAP` / `TOPIC_CMD_LIST` 移出（9→8），`topicApi.PLACEHOLDER_CMD_LIST` 清空。迁移后聚合器实测 `{account:16, crud:32, topic:8, asset:9, render:1, publish:1, compliance:1, mcp:1}`，总数 69，`CMD_OWNER["topicrender"]=="render"`。
3. **版式分派**：`LAYOUT_TYPE_TEMPLATE_MAP` 将 4 类 `layoutType` 与模板目录一一对应；`templatePath` 与 `layoutType` 错配 → `E0`。`renderLayout` 返回 `{outputKind, content, meta}`。
4. **specJson 消费**：模板参数一律沿用 `initSeed` 既有键（S22 逐键核对「被 layoutEngine 消费」，不得自造第二套参数名），可经请求 `specOverride/overrideSpec` 在渲染期覆盖。
5. **4 类交互边界**：stack=纵向顺序；carousel=本项目自实现交互（HTML+JS）**且静态图集兜底必须产出**；longimage=拼接蓝图 + `slices` 切片计划（本轮不截图，Playwright 属 SP3）；swipe=平台原生交互，只切分+排序+统一比例（**不自实现交互**，模板无 script/onclick）。
6. **swipe 专项**：按 `sortOrder` 编排、封面（`usageType=cover`）稳定置顶且第 1 张 `isCover="1"`、`seqNo` 递增、卡片尺寸统一为 `spec.size`（1080×1440）、源图比例与整篇 `spec.ratio` 不一致且 `uniformRatio=true` 时 `E1`；单张格式/大小超 `spec.format`/`spec.maxSizePerImageMB` 亦 `E1`。
7. **图片处理分工**：`assetService` = 入库前（写 `ch_asset`）；`imageProc` = 渲染期派生（封面 900×500 / 卡片 1080×1440 / 长图切片），经 `fileStorageCommon` 上传派生对象，不写 `ch_asset`、无厂商分支。
8. **错误码落点**：渲染类一律 `E` 段 —— `E0` 模板缺失/版式不支持、`E1` 渲染失败（spec 校验不通过/停用）、`E3` 产物生成失败（长图超上限）；字段缺失 `C4`、无记录 `CB`。均为 `contenthub` 消息表中真实存在的键，统一 `msgKey="contenthub"`。
9. **站内预览（P1-8）**：`previewKind ∈ {wechat, xiaohongshu}` → `engine/templates/preview/` 手机框包裹片段（`embedMode=True` 渲染），出参 URL 经 `fillFileUrls`。
10. **真实渲染冒烟**：`test/test_sp2c_render_smoke.py`（不连库，脚本自设 `MYSQL_SKIP_CONNECT=1`）7/7 通过，产物落 `code/data/preview/`。

**SP3a 落地结论（C5 平台适配层 + 微信产物）**：

1. **分层落点**：`main/subfunc/renderApi.py`（接入/报文封装）→ `processor/renderService.py`（业务编排：取主题+附图+版式+平台 → 选适配器）→ `processor/platformAdapter/*`（形态转换）→ `engine/layoutEngine.py`（渲染）+ `engine/inlineStyle.py`（内联化）+ `common/mysqlCommon.py`（只读 `ch_layout` / `ch_platform`）。适配器属业务处理器层，只依赖 `engine/` 与 `common/`，**不 import `subfunc`**（S23 反向依赖检查锁定）；`engine/inlineStyle.py` 只依赖标准库，**不 import `processor`/`subfunc`**。
2. **契约五方法**：`PlatformAdapter` 抽象基类定义 `render / validate / package / deliver / checkHealth`。`validate` 有默认实现（`base.checkPlatformSpec`，数据驱动）；`deliver` 由基类统一实现且**一律返回 `C2` 未实现**，具体适配器**不得覆写**（S23 锁定）；其余三个为抽象方法（`@abc.abstractmethod`）。
3. **`deliver` 归属 SP4 + 零网络**：本轮不调微信/小红书任何接口、不做图片转存、不做投递；需要凭据的能力一律显式报错（S23 校验适配器无网络调用痕迹）。
4. **`topicrender` 参数化（不新增 CMD）**：`platform`（缺省取 `ch_layout.platform`；无平台记录→`CB`，平台停用→`C7`，无适配器→`C7`）、`renderMode`（`sync` 唯一支持，`job`→`C2`）、`exportKind`（generic 专用）、`previewKind`（适配器包裹**平台形态**片段）。聚合器实测端点总数仍 **69**。
5. **微信外链图片策略**：`inlineStyle.resolveImageUrl` 为统一出口 —— 微信显示域（`mmbiz.qpic.cn`，白名单由适配器传入）原样；非白名单外链在本轮无凭据时显式 `E4`（contenthub E 段新增码），**绝不静默保留外链**；平台域名只出现在适配器内，模板仍无平台专属硬编码。
6. **交互降级**：公众号（`allowSvgFlag="0"`）下 carousel 移除自实现交互（`data-interactive="1"` 节点含 `<script>` 与翻页按钮），**复用 SP2c 已产出的静态图集兜底节点**并标记 `data-degraded="static_fallback"`，`meta.interactionDegraded="1"`；`swipe` 不受影响（模板本就无 `script/onclick`）。
7. **`generic` 降级实现**（主计划 5.4 建议，已按允许范围执行）：HTML 输出**复用 `stack_v1`** 片段并标注 `meta.degradedImpl="stack_v1_reuse"`，另提供 Markdown / JSON 结构化导出；文件头已注明降级。
8. **错误码落点**：渲染/产物类一律 `E` 段（`E1` 渲染失败、`E3` 产物生成失败、**`E4` 外链需转存/凭据缺失**）；平台规格 `C5`（标题/摘要超长）、`C6`（图片超量）、`D1`（图片尺寸不符）、`C4`（必填缺失）；平台解析 `CB`/`C7`；`deliver` `C2`。均为 `contenthub` 消息表真实存在的键（S23 以 exec `errMsgCommon` 校验），统一 `msgKey="contenthub"`。
9. **静态验收**：`test/test_ch_phase0_static.py` 新增 **S23**（契约五方法齐备 / `deliver` 未实现 / 规格校验真触发 / `inlineStyle` 无 class 且外链策略生效 / 适配器零网络 / `topicrender` platform 分支可达且无新增 CMD）→ `total=25, pass=25, fail=0`。
10. **平台产物冒烟**：`test/test_sp2c_render_smoke.py` 扩展 4 项（wechat_mp 产物 / carousel 交互降级 / 外链 `E4` / generic html·markdown·json）→ `total=11, pass=11, fail=0`；产物落 `code/data/preview/`。

**SP3b 落地结论（C5 小红书产物渲染）**：

1. **分层落点**：`main/subfunc/renderApi.py`（接入/报文封装）→ `processor/renderService.py`（业务编排：取主题+附图+版式+平台 → 选适配器 → 产物 fileID 经 `chCommon.fillFileUrls` 转 URL）→ `processor/platformAdapter/xiaohongshu.py`（形态转换与素材包清单）→ `engine/layoutEngine.py`（渲染 HTML）+ `engine/htmlToImage.py`（Playwright 截图）+ `engine/imageProc.py`（长图切片复用）。适配器只依赖 `engine/` 与 `common/`，**不 import `subfunc`**（S24 反向依赖检查锁定）；`engine/htmlToImage.py` 不 import `processor`/`subfunc`。
2. **截图管线**：`engine/htmlToImage.py` 懒加载**单浏览器实例**（进程内复用、**串行渲染**、`closeBrowser()` 统一关闭），每张卡片独立 context/page，`headless=True`，viewport=`1080×1440`，`device_scale_factor` 默认 1（输出像素 = CSS 像素）。`renderHtmlToImage`（元素级/整页）、`renderCardsFromHtml`（swipe 一屏一张）、`renderLongImageSlices`（整页截图 + 复用 `imageProc.sliceLongImage` 切片）。
3. **字体预加载**：`waitForFonts` 注入中文字体栈并等待 `document.fonts.status === "loaded"`（含显式超时兜底，超时不抛异常），`meta.fontInfo` 记录**实际使用字体**，便于排查中文丢字。
4. **swipe 形态（2.6.1/2.6.3）**：每张卡片一屏 → N 张 `1080×1440` PNG，按 `sortOrder` 编排、`seqNo` 递增、第 1 张 `isCover="1"`（封面稳定置顶）、`mechanism=platform_native`（**不自实现滑动交互**）。强制校验（渲染前拦截）：比例统一（不一致 → `D1`，**不静默裁切**）、张数 ≤ `min(spec.maxCount, ch_platform.imageMaxCount=18)`（超量 → `C6`）、单张 ≤ 20MB（超限 → `D1`）、格式 JPG/PNG（其他 → `D0`）。
5. **longimage / stack 形态**：整页长图截图 → 按 `specJson.sliceHeight`（默认 1440）切分为多张，**每张切片独立登记产物（`seqNo` 递增）**，切片数 = `ceil(长图实际总高/sliceHeight)`，**禁止直接产出超长单图**；超 `maxTotalHeight` → `E3`。`stack` 在小红书形态为长图，渲染期把 `maxWidth` 归一到卡片宽度。
6. **carousel 边界**：小红书不接收 HTML，且 `carousel` 交互属公众号自实现 → `carousel + xiaohongshu` **显式返回 `C7`**，**绝不静默转换**（`carousel` 与 `swipe` 互不替代）。
7. **素材包清单（7.8）**：`package` 产出有序 `itemList`（seqNo/fileName/fileID/尺寸/字节数/sha256/isCover）+ `manifestDraft`（主题编码/标题/生成时间/版式/平台/文件清单/`checkSum`），`packageKind="xiaohongshu_asset_pack"`、`zipPacked=False`；**ZIP 打包与导出归 SP4**，本轮只出清单。
8. **投递红线**：`deliver` 继承基类，一律显式未实现（`C2`），具体适配器**不得覆写**（S24 锁定）；小红书适配器内**无任何自动发布/投递代码路径**（静态红线扫描）。
9. **错误码落点**：`E0`（不支持的 layoutType）、`E1`（渲染异常/Playwright 不可用）、`E2`（截图超时）、`E3`（产物失败/长图超上限）、`C4`（标题缺失）、`C5`（标题/摘要超长）、`C6`（图片超量）、`C7`（carousel 不可用）、`D0`（格式不允许）、`D1`（比例/大小不符）；均为 `contenthub` 消息表真实存在的键，统一 `msgKey="contenthub"`。
10. **出参与上传**：产物先落本地临时目录，再经 `common/fileStorageCommon.py` 上传（红线 R2；`SELFFILE` 真实落盘）；出参 `data.products`/`data.fileIDs`/`data.productCount`，fileID 经 `chCommon.fillFileUrls` 转 URL。**`ch_artifact` 台账写入归 SP3c，本轮不写库**。
11. **静态验收**：`test/test_ch_phase0_static.py` 新增 **S24**（适配器契约齐备且不覆写 `deliver` / 无自动发布投递路径 / `xiaohongshu` 从 C7 迁移 / `carousel` 显式 `C7` / swipe 强校验错误码落点 / `E2`·`E3` 落点 / `htmlToImage` 零对外网络与分层）→ `total=26, pass=26, fail=0`；S23 同步纳管 `xiaohongshu.py` 与 `htmlToImage.py`。
12. **真实截图冒烟**：`test/test_sp2c_render_smoke.py` 扩展 6 项（**真实 Chromium 截图**）→ `total=17, pass=17, fail=0`；实测证据：swipe 4 张卡片各 `1080×1440`；longimage `fullHeight=5760` → 4 张切片；stack→长图 `fullHeight=7484` → 6 张切片（无超长单图）；产物落 `code/data/preview/xiaohongshu/`。

**SP3c 落地结论（C8 合规校验 + 产物台账 + 渲染任务化；★ 里程碑 M2 闭环）**：

1. **分层落点**：`main/subfunc/complianceApi.py`（接入/报文封装）→ `processor/complianceService.py`（C8 合规规则与问题清单）→ `processor/renderService.py`（渲染编排 + 任务/台账）/ `engine/layoutEngine.py`；`schedule/renderWorker.py`（调度层）只调 `processor`。`complianceService` 只依赖 `processor` 同层 + `engine`/`common`，**不 import `subfunc`**（S25 锁定）；`renderWorker` **不 import `main/subfunc`**（S25 锁定）。**M2 闭环 = C4（版式）+ C5（平台适配/产物）+ C8（合规闸门）+ 渲染任务化/产物台账**四块在 `topicrender` / `publishcheck` 两条入口上贯通。
2. **规格校验单一来源（硬约束）**：平台规格一律调用 `platformAdapter.base.checkPlatformSpec`（规则全来自 `ch_platform`）；swipe 专项（比例统一 `uniformRatio`/张数 ≤ `ch_platform.imageMaxCount`/单张 ≤20MB/格式 JPG·PNG）一律调用 `xiaohongshu.validateSwipeSpec`（2.6.3 唯一定义处）。`complianceService` **不重写任何规格判定**（S25 断言 `def checkPlatformSpec(` / `def validateSwipeSpec(` 不存在），只补一条 C8 前端闸门：**超长整图（高 > 切片高/卡片高，默认 1440）须先切分 → `E3`**。
3. **统一问题清单**：`{field, location, level ∈ {ERROR,WARN}, errCode, message, source}`；敏感词项另附 `offsetStart/offsetEnd/matchedWord`。汇总出参 `data = {passed, issueCount, errorCount, warningCount, issues, platformCode, layoutType, sensitiveHitCount, rateLimit, ...}`；`passed="1"` 仅当无 `ERROR`。**前端可直接定位与高亮**（`location` 形如 `assetList[1]` / `description[1,6]`）。
4. **敏感词**：`detectSensitiveWords` 支持**多命中**（同一词多次出现全部返回，按 `start` 升序），扫描 `title/summary/description/author`；默认词表 `DEFAULT_SENSITIVE_WORD_LIST`（内容规则，非平台规格），可经 `dataSet.sensitiveWords` 覆盖。命中 → `C7`。
5. **AI 内容标识**：按 `ch_platform.needAiLabelFlag`；标识存在性 = `aiLabel` 非空 或 正文/简介含标识词（`AI_LABEL_MARKER_LIST`）。**缺标识时**：内容声明 AI 参与（`aiFlag="1"`）→ `ERROR`（阻断）；未声明 → `WARN`（仍给出明确问题项）。
6. **发布频率限流 + Redis 降级**：账号(+平台)维度 `INCR`+`EXPIRE`（默认窗口 3600s / 上限 30）；**Redis 不可用 → 进程内固定窗口计数 + `degraded="1"` + 告警日志**，`allowed` 仍按计数判定（**不拒绝、不崩溃**）；降级在问题清单中以 `WARN` 显式可见。超限 → `C6`（**不占用 F 段**）。
7. **产物台账（P2-6）**：`saveArtifacts` 经 `chCommon.upsertByUniqueKey` 幂等写入 `ch_artifact`，唯一键 `artifactKey = {jobID}:{kind}:{platform}:{seqNo}`（3.4.5）；写 `kind/platform/fileID/thumbnailID/seqNo/artifactVer/specNote/sizeBytes/artifactStatus=READY/expireYMDHMS`；**同 job 重渲染命中同一 `artifactKey` → `artifactVer` +1**（实测 3→4）。★ **过期清理归 SP4**，本轮只写字段（`ARTIFACT_STATUS_EXPIRED` 已定义但不在本轮触发）。
8. **渲染任务化（P2-7）**：`ch_render_job` 状态机 `PENDING→RUNNING→DONE/FAILED`（`FAILED→PENDING` 可重试），非法跃迁 → `C7` **并回显允许跃迁集**（`checkJobStatusTransition`，沿用 `topicService` 范式）。**同步渲染也建 job（终态 `DONE`）**，使 `artifactKey` 的 `jobID` 有值、`sync`/`job` 共用同一台账键；**`job` 模式下建 job 后立即返回 `jobCode` + `jobStatus=PENDING`**（兑现 SP2c/SP3a 预留的 `renderMode="job"`），由 worker 异步完成（`renderService.executeJob`）。建档失败时：`sync` 降级为「不写台账但照常渲染」，`job` **显式返回 `CG`**（不静默丢任务）。
9. **`inputHash` 复用**：`buildInputHash` 取渲染输入快照 sha256（主题关键字段 + 附图列表〔按 `(sortOrder, fileID)` 排序〕+ `layoutCode/layoutType` + `platform` + 生效 spec）；命中既有 `DONE` 任务且产物齐备 → **直接复用既有产物、不重复渲染**，出参 `reused="1"` / `reuseReason` / `jobID` / `artifacts`，并记日志（主计划 P2-7）。**同步与异步模式共享该判定**（复用判定先于适配器选择）。
10. **`schedule/renderWorker.py`（P2-8，首次创建 `schedule/` 包）**：常驻轮询 `PENDING`（默认间隔 4s，`--interval` 或 `CH_RENDER_WORKER_INTERVAL` 可配，3~5s 区间），**单实例 + 串行**消费；Redis 任务锁 `SET NX EX`（★ 不可用 → 降级为进程内锁 + 告警，**不阻塞消费**）；消费前复用状态机防御校验；执行 `renderService.executeJob` → 写 `ch_artifact` → 更新 `jobStatus/progress/costMs/errMsg`，异常落 `FAILED` 并记录原因；**不并发截图**（worker 串行 + `htmlToImage` 单浏览器实例串行），S25 断言无 `ThreadPool`/`concurrent.futures`/`multiprocessing`/`threading.Thread`。`__main__` 支持 `--once` 单次执行（无守护环境验证）。
11. **`publishcheck` 端点**：`complianceApi.funcPublishCheck` 内部走 `complianceService.publishCheck`（沿用 `_serviceResult` 范式），`CMD_MAP = {"publishcheck": ...}`、`PLACEHOLDER_CMD_LIST = []`。**不新增 CMD，端点总数仍 69**（聚合器实测）。
12. **验收**：`test/test_ch_phase0_static.py` 新增 **S25** → `total=27, pass=27, fail=0`；`test/test_sp2c_render_smoke.py` 扩展 7 项（**不连库，桩替换数据层/计数后端**）→ `total=24, pass=24, fail=0`。**桩验证 vs 真实执行**：台账写入/`inputHash` 复用/job 状态机/Redis 桩不可用为**桩验证**（本机无 MySQL/Redis 服务端）；合规纯函数（规格/敏感词/AI 标识）与 `checkPublishRateLimit` 真实调用为**真实执行**（真实调用在本机亦 `backend=memory, degraded=1`，证明降级路径生效且不崩溃）。

**SP4a 落地结论（C6 公众号草稿投递链路；★ 里程碑 M3 第一块）**：

1. **分层落点**：`main/subfunc/publishApi.py`（接入/报文封装）→ `processor/publishService.py`（C6 编排，**唯一对外产生副作用的模块**）→ `processor/platformAdapter/wechatMp.py`（通道调用）+ `processor/auditService.py`（审计）+ `common/credentialCipher.py`（加密）+ `engine/inlineStyle.py`（转存回调出口）；`publishService` 只依赖 processor 同层 / engine / common / config，**不 import `subfunc`**（S26 锁定）；`auditService` 同（S26 锁定）。
2. **推送≠发布（P0 红线）**：本项目交付形态为「一键推送到草稿箱」；`draft/add` 为终点，`remoteID` 回写 `ch_publish_record.remoteID`；`freepublish/submit` **默认关闭**，须「人工二次确认（`autoPublishConfirm=1`）+ `ch_platform.autoPublishFlag=1` + `WECHAT_AUTO_PUBLISH_ENABLED=1`」三重条件，否则显式 `F6` 拒绝且**不先投草稿**；`deliver` 本身绝不群发。
3. **★ 小红书不投递/不发布**：`publishService.NON_DELIVERABLE_PLATFORM_LIST=["xiaohongshu","generic"]` 在取适配器**之前**即显式 `C7` 拒绝；S26 以全仓静态扫描（`api.xiaohongshu`/`xhslink`/`xiaohongshu.com`/`creator.xiaohongshu`/`xhssign`）+ 8.4 上线检查项「小红书自动发布相关代码路径不存在」双保险。
4. **凭据安全（R-19）**：`common/credentialCipher.py` 提供 AES-256-GCM 对称接口，密钥**仅经环境变量 `CH_CREDENTIAL_KEY`** 注入（本机无 KMS），**密钥不入库、不入代码库**；`ch_account.credentialCipher/credentialIV` 解密失败/缺失/过期/`healthStatus=INVALID` → `F0` 并回写健康状态，**不静默降级**；`cryptography` 延迟导入保证 import 不失败；审计/日志经 `sanitizePayload`/`maskSecret` 脱敏（S26/SMOKE 断言凭据明文不入审计与发布记录）；并提供 `ch_account` 凭据**读写闭环**（`saveAccountCredential` 加密写入 / `decryptAccountCredential` 解密读取）。
5. **access_token（R-03）**：`publishService.getAccessToken` 进程内缓存 + `WECHAT_TOKEN_REFRESH_AHEAD_SECONDS` 提前刷新；失败按 R-03 明确回显（含平台 `errcode/errmsg`）并置 `healthStatus=INVALID`；token 失效类 errcode（40001/40014/40125/42001/41001/40003）统一按 `F0` 回显。
6. **图片转存（补齐 §4 E4 实现）**：`inlineStyle.resolveImageUrl/inlineHtml` 增加可选 `transferFunc` —— 业务层凭据就绪后经 `wechatMp.buildTransferFunc` 注入，外链经 `media/uploadimg` 转存为 `mmbiz.qpic.cn` 并**就地替换 src**；未注入/转存失败仍显式 `E4`；`deliver` 侧再校验正文无残留外链（有则 `E4` 拒绝）；封面经 `material/add_material` 换 `thumb_media_id`。
7. **幂等与防重（P3-3 / R-04）**：`idempotencyKey = {artifactID}:{accountID}:{uuid4}`；二次提交在**取数/合规之前**被 `F1` 拦截且不产生第二条发布记录（并在 `upsertByUniqueKey` 处再兜底）；二次确认参数必填（`F4`，首次调用回显 `confirmToken` 供两步确认）；60 秒撤销窗用 `success`+`delFlag`+`pushedYMDHMS` **状态机**实现（**不依赖 Redis**，Redis 仅可选加速）。
8. **投递前置（硬闸门）**：平台/通道 → 账号+凭据 → `ch_artifact` READY → 幂等 → 二次确认 → 自动发布闸门 → **合规闸门（复用 `complianceService.publishCheck`）**；未过合规校验返回其原始错误码（如 `C7` 敏感词）且**不投递、不落库**（仅审计 FAIL）。
9. **发布记录与审计（P3-5）**：`ch_publish_record` 全字段落库（`requestJson`/`responseJson` 经脱敏）；成功与失败都写 `ch_audit_log`（`actor/source/action/targetType/targetID/payloadDigest(sha256)/result/errMsg/costMs/ipAddr`）；审计写入失败不阻断主流程但出参标注 `auditWritten="0"`。
10. **验收**：`test/test_ch_phase0_static.py` 新增 **S26** → `total=28, pass=28, fail=0`（S23 同步调整：wechat_mp 覆写 `deliver` 并移出零网络扫描）；`test/test_sp2c_render_smoke.py` 扩展 **9 项** → `total=33, pass=33, fail=0`。
11. **★ 桩验证 vs 真实执行（本机无凭据，按 (B) 口径）**：**真实执行** = AES-256-GCM 加解密往返/无密钥行为、`inlineStyle` 转存分支、合规纯函数与限流降级；**桩验证** = 发布记录落库/幂等判定/撤销窗/审计写入/`deliver` 通道（桩替换数据层与 HTTP 通道）。**未端到端打通真实平台**（未真实调用 `get access_token` 与 `draft/add`，无真实 `errcode/errmsg/remoteID`）——凭据就绪后需在有环境机器上补做真实打通与真机排版验收（见 §10）。

**SP4b 落地结论（素材包 ZIP + MCP 接入 + 凭据巡检；★ 里程碑 M3 第二块）**：

1. **分层落点**：`main/subfunc/assetApi.py`（`artifactpack` 接入/报文封装）→ `processor/artifactService.py`（C6 素材包导出业务）→ `processor/complianceService.py`（合规闸门）+ `processor/platformAdapter/xiaohongshu.py`（清单/manifest 复用 `package()`）+ `common/fileStorageCommon.py`（ZIP 上传与产物取回）；`main/subfunc/mcpApi.py`（薄入口）→ `common/chServerCommon.py`（转发）/ `common/redisCommon.py`（会话）；`main/subfunc/accountApi.py`（`accounthealth` 接线）→ `schedule/credentialCheck.py`（巡检）→ `processor/publishService.py`（凭据解密/健康回写）+ `processor/platformAdapter/wechatMp.py`（`fetchAccessToken` 通道原语）。`artifactService`/`credentialCheck` 均**不 import `main/subfunc`**（S27 锁定）。
2. **素材包 ZIP 结构（7.8）**：条目顺序 = 有序图片（`01_`/`02_`…，**顺序即 App 内左右滑动浏览顺序**、与产物 `seqNo`（源自附图 `sortOrder`）一致）→ `title.txt` → `content.txt` → `manifest.json` → `COPYRIGHT.txt` → `RISK_NOTICE.txt` → `SWIPE_TIPS.txt`。图片条目名 = `{seqNo:02d}_{原名去序号前缀}{ext}`（`buildImageEntryName`，序化 + 安全化）；文本条目 UTF-8 写入。
3. **★ 未过合规校验不得出包**：导出前调用 `complianceService.evaluateCompliance`（校验对象为**生效主题**：正文已含 `#话题标签` 与必要的 AI 标识；`products` 参与 C5 产物校验），`errCode != B0` → 立即返回合规原始错误码（`C5/C6/C7/D0/D1/E3` 等）+ 问题清单，`data.packaged="0"`，**不生成 ZIP、不上传**。冒烟实测：敏感词命中 → `errCode=C7, packaged=0, uploadCalls=0`。
4. **规则单一来源（硬约束）**：`artifactService` **不重写**任何规格/合规判定（S27 断言 `def checkPlatformSpec(` / `def validateSwipeSpec(` 均不存在），素材包清单/manifest 字段亦**复用** SP3b 适配器 `package()` 的能力（本层只补 ZIP 条目名与逐文件 sha256）。
5. **内容级校验值**：`manifest.checkSum = sha256(按 seqNo 拼接各图片文件 sha256)`；`fileList` 逐项含真实 `sizeBytes`/`sha256`（由落盘文件现算，非沿用出参），冒烟以 ZIP 内实际字节复核一致。
6. **上传与出参（红线 R2）**：ZIP 经 `fileStorageCommon.saveFile` 上传（SELFFILE 实测真实落盘，`fileID=118/filee8...`、`zipSizeBytes=23190`），失败 → `D3`；组装失败 → `E3`；产物取回失败 → `D4`；无 READY 产物 → `CB`；出参 `fileID` 经 `chCommon.fillFileUrls` 转 URL。**全程无厂商分支**（S27 扫描无 `FILE_SYSTEM_MODE ==`）。
7. **★ 只导出不投递（平台红线）**：`deliverMode="asset_pack"`；`artifactService` 静态扫描无 `publishService`/`freepublish`/`draft/add`/`submitFreePublish`/`deliver(`；小红书素材包一律由用户手动在 official 创作服务平台发布（ZIP 内 `RISK_NOTICE.txt` 明示）。
8. **MCP 薄入口（P3-4）**：`mcpApi.mcpinvoke` = 「token → Redis 会话/`ROLE_CMD_LIST`（`G0`）→ 可选 `MCP_TOOL_LIST` 工具级授权（`G1`）→ `TOOL_CMD_MAP` 路由（`G2`）→ 经 `ChServer` 转发下游 `/chapi`（`G3`）」；成功 `B0` 且 `data.downstream`/`downstreamErrCode` 回显。**不承载协议解析**（无 `jsonrpc`/`tools/call`/`FastMCP`/`toolPathMap`），**`mcpapi/` 未改动**。
9. **★ MCP 接入（9.6.6 清单；★ 本轮不联调）**：监听端口固定 **8891**（`config/mcpConfig.py::MCP_SERVER_PORT`，`mcp_entry.py` 取值不硬编码；`MCP_AUTH_*` 占位 URL 同步指向 8891），传输 `streamable-http`（ASGI 路径 `/mcp`）。★ **本轮明确不联调** —— **不启动 `mcp_entry.py`、不监听端口**，故 9.6.6 的 **①（无 token → 401）/②（无效 token → 拒绝）未执行**（属服务端鉴权中间件行为，需真实监听才能观测 HTTP 状态码），其配置不变式由静态 S27（`token_verifier`/`AuthSettings`/8 tool·3 resource/端口）与冒烟 `assertMcpServerPort`（端口 8891 + streamable-http + issuer 指向 8891）锁定。其余各项**直调实现层**验证：③有效 token 放行（**桩**：本机无 Redis 服务端，`getSessionInfo` 注入会话）；④未知 tool → `ERR_NOCMD`（真实执行）；⑤`MCP_TOOL_LIST` 越权 → `BT`（鉴权上下文为桩）；⑥缺必填参 → `BA`（真实执行，不触下游）；⑦正常查询 → `B0` 且 `rtnData` 含 `total/returned/data`；⑧3 个 resource 均返回合法 JSON；⑨下游不可达 → `ERROR`（日志含 `PID`/`toolName`）；⑩超 `TOOL_RESULT_LIMIT` → `returned=10 < total=50`（⑦⑧⑨⑩ 的下游 `/chapi` 为**桩**）。**MCP 服务端端到端联调列入尚欠项（§10）**。
10. **凭据健康巡检（P3-6）**：仅 `wechat_mp` 做只读探活（解密凭据 → `fetchAccessToken`），`healthStatus` 四态（`OK`/`EXPIRING`/`INVALID`/`UNKNOWN`）+ `lastCheckYMDHMS` 回写；**小红书无凭据/不适用 → 跳过并说明且不改写健康状态**；阈值 `CH_CREDENTIAL_EXPIRE_WARN_DAYS`（默认 7）；R-03 分级告警 `OK→INFO`/`EXPIRING→WARN`/`INVALID→ERROR`/`UNKNOWN→WARN`；Redis 重入锁不可用 → 进程内锁 + 告警（**degraded=1**，实测）；`__main__` 单次执行实测可用。**只读探活，不含任何投递/发布**。
11. **`accounthealth` 接线（不新增 CMD）**：在 `funcAccountHealth` 同一处理函数内，`action ∈ {check, refresh, probe}` 时先触发 `credentialCheck.runOnce`（函数内延迟导入，保持接入层与调度层导入期解耦），再汇总；出参新增 `credentialCheck` 与 `checkedAt`。实测 `errCode=B0, checkResult=1`。
12. **验收**：`test/test_ch_phase0_static.py` 新增 **S27** → `total=29, pass=29, fail=0`（S21 同步调整：素材域占位清空）；`test/test_sp2c_render_smoke.py` 扩展 **7 项** → `total=40, pass=40, fail=0`。**端点不变式**：`CMD total=69`（无新增 CMD）。**依赖口径修正**：`requirements.txt` 锁 `mcp>=1.2.0,<2`（本机原装 2.2.0 导致 `mcp_entry.py` 导入期报错，实测装 1.30.0 后导入正常；★ 本轮不联调，未做端口监听）。

**SP4c 落地结论（归档清理 + 监控告警 + 巡检守护化；★ 里程碑 M3 第三块）**：

1. **分层落点**：`schedule/archive.py`（调度层）只调 `processor/auditService`、`common/mysqlCommon`、`common/fileStorageCommon`、`chmonitor/alertChannel`、`chmonitor/heartbeat`；`chmonitor/*` 只依赖 `processor`（同层可读）/`common`/`config`，**不 import `main/subfunc`**（S28 反向依赖检查锁定）；`config/opsSettings.py` 为运维配置集中出口（被 `schedule/`、`chmonitor/` 读取，不反向依赖业务）。★ **`monitor/`（ museum 迁移改造层）** 只依赖 `monitor/monitorConfig.py`（→ `config/opsSettings.py`）与 `chmonitor/`（懒加载）与 `common/`（日志）；同样 **不 import `main/subfunc`**。
2. **★★ 破坏性操作默认 dry-run**：`archive.py` 的 `isDryRun()` = 未 `--execute` 且未设 `CH_ARCHIVE_EXECUTE=1` → True；dry-run 只打印「将导出/将删除」清单（**零导出、零删除**，冒烟实测 `events=0`），脚本头与日志显著提示（主计划 8.6 红线：生成器无 migration，误删不可逆）。
3. **★ 审计归档（P3-7 / 3.4.6）**：按保留期（默认 24 个月）筛 `regYMDHMS <= cutoff`；**分批（默认 5000/批）循环**；每批**先导出（CSV / JSON.gz）并经 `common/fileStorageCommon.py` 上传成功**，**再逐条删除**；导出失败中止本批且**不删除**；删除 0 条即中止（防重复循环）；每批经 `auditService.writeAudit` 留痕（`archive.audit_log`）。冒烟实测事件序 `['export','delete','delete','export','delete']`（先导出后删除、批次循环正确）。
4. **★ 产物过期清理（P3-7 / R-23）**：`expireYMDHMS` 到期且 `READY` → **先置 `artifactStatus=EXPIRED`，再 `delFile`**（唯一出口 `fileStorageCommon`）；对象删除失败 → **状态不再二次变更（保持 `EXPIRED`）**、不删台账行、经告警通道**不静默**告警；`expireYMDHMS` 为空不清理。筛选经手写段 `query_ch_artifact(..., expireBeforeYMDHMS=...)`（可选参数，缺省不影响既有调用）。冒烟实测 `purged=1, failed=1`，事件序 `EXPIRED→delFile`、`f12` 删除失败后无二次变更。
5. **§10 第 5 条裁定（写入 §4）**：**素材包 ZIP 不登记 `ch_artifact`**（台账语义单一 + 唯一键/`jobID NOT NULL` 不适配一次性导出）；ZIP 由对象存储生命周期/人工保留策略管理，归档清理只处理渲染产物与审计日志。
6. **★ 监控告警（P3-8 / 8.7，首期降级口径）**：`chmonitor/metrics.py` 七项指标判定为**纯函数**（阈值全部取自 `config/opsSettings.py::MONITOR_METRIC_TABLE`，禁止硬编码）；`chmonitor/monitorService.py` 采集七项（取数失败 → `degraded=1` 且 `INFO`，不误报）；`chmonitor/dailyCheck.py` 单次执行 → 报告落 `code/data/monitor/`。**不做看板/时序数据库，不引入新中间件**。
7. **★ 告警通道占位零网络**：`chmonitor/alertChannel.py` 提供可插拔 `AlertChannel`（默认 `log`，沿用 `misc.setLogNew` 落盘）；`email`/`wecom` 为**占位实现**，`networkRequest` 恒 `"0"`、`sent=0`，★ **本轮不发任何对外网络请求**（S23 零网络扫描 + S28 + 冒烟运行期三重锁定）。`credentialCheck._alert` 已对接该通道（不再只写日志）。
8. **★ 巡检守护化（§10 第 9 条）**：`schedule/credentialCheck.py` 新增 `--loop` 常驻（`--interval` / `CH_CREDENTIAL_CHECK_INTERVAL` 默认 3600s），与 `renderWorker` 同风格（单实例 + Redis 锁可降级）；每次运行刷新 `chmonitor/heartbeat`；`tools/runOpsJobs.ps1` 供 cron/计划任务串联调用（归档默认 dry-run + 巡检 + 每日巡检）。
9. **★ 审计留痕**：`processor/auditService.py` 追加 `archive.audit_log` / `archive.artifact_purge` 动作与 `ch_audit_log` / `ch_artifact` 对象类型；归档/清理**每批**留痕（失败批次 `result=FAIL`）。
10. **★ 目录重命名与 museum 迁移改造**：SP4c 监控核心包 `monitor/` → **`chmonitor/`**（引用全量更新：`schedule/archive.py`、`schedule/credentialCheck.py`、包内引用、两份测试、`tools/runOpsJobs.ps1`、`config/opsSettings.py`、本文档）；`monitor/` 由 `museum/code/src/monitor` 迁移改造 —— **保留**可复用逻辑（JSON/时间戳/文件变化检测/告警汇总 `run_alert` 入口），**剥离**网络请求 / 套接字 / 子进程 / 进程 kill 原语（原进程-端口-服务守护改为**显式不支持并记日志**）与 museum 专属依赖（`mu_` 前缀业务表 / museum 配置），改为复用 `chmonitor.monitorService.collectAllMetrics` 与 `config/opsSettings.py`；`crontab.txt`/`restore_monitor.sh` 为 Linux 部署样例（路径改 contentHub）。实测 `python monitor/monitor.py -h` / `python monitor/monitor.py` / `python monitor/alert.py` 均可运行。
11. **验收**：`test/test_ch_phase0_static.py` 新增 **S28** → `total=30, pass=30, fail=0`（S23 零网络扫描纳入 `chmonitor/` 与 `monitor/`；S28 输出 `chmonitor=ok; monitor(museum 迁移改造)=ok`）；`test/test_sp2c_render_smoke.py` 扩展 **5 项** → `total=45, pass=45, fail=0`。**端点不变式**：`CMD total=69`（无新增 CMD）。**真实执行/桩验证边界见 §1 SP4c 口径声明**（本机无 MySQL/Redis → 归档真删与连库路径为桩/dry-run）。

---

## 10. 已知限制 / 待办

1. **未做运行验证**：本轮未连数据库、未连 Redis、未连文件服务；`mysqlCommon.py` 只做了语法编译与 AST 级符号闭环核查（本环境缺少 `pymysql`，无法做导入级检查）。首次运行前请先 `pip install -r requirements.txt`。
2. **`ch_layout` 种子为 4 条内置版式**（`stack_v1` / `carousel_v1` / `longimage_v1` / `swipe_v1`）；「各平台各一套」的完整矩阵待 SP2 按实际需要补录。
3. **`ch_asset.width/height`、`ch_artifact.sizeBytes`、`ch_render_job.costMs`、`ch_render_job.progress` 等可空数值列**受生成器「异常置 0」影响，业务层须按「0 = 未设置」处理。
4. **【SP4c 已收口】`ch_audit_log` 归档**：大表查询已收紧 `LIMIT 5000`；★ SP4c 已实现按保留期（默认 24 个月）**分批 DELETE + 导出归档**（`schedule/archive.py`：★ **先导出上传成功再分批删除**、保留期/批大小/导出格式可配、★ 默认 dry-run）。真删需在有 MySQL 的机器上以 `--execute` 执行（→ 见下方「SP4c 追加的已知限制 / 待办」）。
5. **LSP 符号核查不可用**：本环境 Python 语言服务未返回符号，符号闭环改由 `test/test_ch_phase0_static.py` 的 S11 项以 AST 方式实现（覆盖 tools 与 12 份产物对 `comMysql` / `comCh` / `comFS` 的全部引用），并由 S12 锁定删除标记取值约定（`delFlag` 用 `"0"/"1"`，禁止误用 `comGD._CONST_NO`）。
6. **小红书自动发布路径不存在**，且后续任何子计划不得引入（平台红线）。★ SP4a 已复核：`publishService` 对 `xiaohongshu` 显式 `C7` 拒绝（`NON_DELIVERABLE_PLATFORM_LIST`），S26 以全仓静态扫描（`api.xiaohongshu`/`xhslink`/`xiaohongshu.com`/`creator.xiaohongshu`/`xhssign`）锁定，对应主计划 8.4「小红书自动发布相关代码路径不存在」上线检查项。

**SP1.5 追加的已知限制 / 待办**：

7. **接入层未做联调运行验证**：本机无账号服务 / 无 Redis / 无 MySQL，仅做了「导入级聚合 + 未知命令 + 占位端点 + Flask 路由注册」冒烟；真实登录链路（A0A0/GAA0）与 48 个 CRUD 的读写需在有环境的机器上跑（先 `pip install -r requirements.txt`）。
8. **账号服务不可达时的权限语义沿用基线**：`getSessionAndCmdList`（GAA0）在回包缺失时按基线返回 `B0 + 空会话`，因此非免登录命令会统一落到 `B8`（拒绝），不会放行；`accountSvcClient.accountServiceForward` 才把「下游非 200 / 不可达」映射为 `CI`。若要更精确的诊断信息，需在 C1 一并调整（会改变与基线的错误码等价性）。
9. **`crudApi.py` 属生成件装配（SP2b 重跑后 3850 行 / 32 CMD）**：在静态检查 S13 中白名单豁免单文件行数上限；若后续把 CRUD 按表拆分，需同步修改 S13 的 `SUBFUNC_LINE_EXEMPT_LIST` 与 `tools/mergeCrudApi.py`。**注意：每次调整 `EXCLUDED_TABLE_LIST` 都必须重跑 `tools/mergeCrudApi.py`**，且「排除表」必须与「接管该表的域文件」成套提交（只改一侧会让聚合器 V1 校验在导入期抛 `RuntimeError`）。
10. **`apiCommon.py` 的「零业务」约束靠约束与评审保证**：S13–S18 未做自动语义检测（无法用 AST 判定何谓业务逻辑），后续新增公共件时必须人工把关，防止其演化为第二个巨型文件。
11. **`renderApi.py` 本期为空域**：渲染调度类对外命令字未定义，故 `CMD_MAP = {}`；聚合器 V3 是「注册表 ⊇ 配置声明」的超集校验，允许空域（SP3 落地后登记即可）。
12. **`_DEBUG` 默认开启**（与基线一致，`settings._DEBUG = True`）：生产环境经 `config/local_settings.py` 或环境变量关闭，避免逐请求全量报文入库。

**SP2a 追加的已知限制 / 待办**：

13. **主题链路未做连库运行验证**：本轮只做了 py_compile + AST 静态检查（S20）与「不连库」的纯函数/端点封装冒烟（`countWords`、状态机、字段区间、`C5` 报文）；`addTopic/modifyTopic/deleteTopic/queryTopic` 与版本快照的真实读写需在有 MySQL 的机器上验收（先执行 `tools/initTables.py`，并 `pip install -r requirements.txt` **外加** `alibabacloud_oss_v2` / `cos-python-sdk-v5`——`common/fileStorageCommon.py` 在模块级导入两家云适配器，缺 SDK 时连 `import chCommon` 都会失败）。
14. **软删除语义**：`topicdel` / `topicversiondel` 采用 `delFlag="1"` 软删除（与 `query_ch_*` 的 `delFlag` 过滤一致），不再走生成件原来的物理 `DELETE`；如需物理删除需另立运维脚本。
15. **生成器更新语义的两处遗留**（本轮已规避但需登记）：① `update_ch_topic` 对空串会跳过 → 无法「清空」单字段（由此把超长详述的库内正文改为有界前缀而非置空）；② `update_ch_topic` 不含 `regID/regYMDHMS` 项，更新路径不会改写注册信息（符合预期）。
16. **版本对比 / 回滚属 P2**：本轮只落快照 + 提供「按主题列版本 / 按版本取快照」（`topicversionqry`）；`C9 版本与协作`（diff / rollback / 审核流转）不在本轮范围。
17. **详述转存依赖文件后端**：`description` >5000 字时需文件服务可用；`FILE_SYSTEM_MODE=SELFFILE` 下可本地自验，云端桶切换后需在对应环境复验（转存对象名前缀 `topic/description/`）。
18. **★ 2026-09-22 裁定（详述取消 2000 字下限）**：`description` 区间由「2000–5000 字」改为**无下限、≤5000 字**（可留空 / 0 字）。代码口径：① 保存 `validateTopicFields` 删除「字数低于下限 → `C6`」拦截；② 提交渲染 `_checkRenderReadiness` 仅保留「既无正文也无 `descriptionFileID` → `C4`」，取消「低于 2000 → `C6`」；③ 常量 `DESCRIPTION_MIN_WORDS` 保留置 `0` 以兼容 S20 静态清单校验，但不再参与任何拦截；④ DDL 注释（`mysqlCommon.py` / `ch_topic.txt`）同步为「不超过5000字,可留空」。前端 `useRenderTrigger` / `TabContent` / `CompletionPanel` / `mock/topic` 同步去掉下限与「至少 2000 字」提示。

**SP2b 追加的已知限制 / 待办**：

18. **素材链路未做连库/连文件服务运行验证**：本轮只做了 py_compile + AST 静态检查（S21）与「不连库」的纯函数/端点封装冒烟（`computeContentHashFromBytes`、字段校验、`C2/C4/C7` 报文、`assetKey` 派生）；`assetadd/modify/del/qry` 与 `topicasset*` 的真实读写需在有 MySQL + 文件服务的机器上验收（先执行 `tools/initTables.py`，并 `pip install -r requirements.txt`）。
19. **上传入参形态**：`assetadd` 支持两条路径 —— ① `localPath`（服务端负责裁剪/EXIF/缩略图/上传，`contentHash` 由服务端计算）；② `fileID + contentHash`（登记已存在于文件服务的素材，服务端不重复上传）。当前 HTTP 入参按「JSON 内传本地路径」设计，**尚未接入 multipart 直传**；若前端改为浏览器直传，需在 C1/文件服务侧补一条「临时文件落地 → localPath」的约定。
20. **Pillow / 文件门面均为延迟导入**：`Pillow` 缺失或 `fileStorageCommon` 不可导入时，图像处理降级为原样上传（`processStatus=RAW`），**功能不中断但裁剪/EXIF/缩略图不生效**；生产环境须确保两者就绪（`Pillow` 已在 `requirements.txt`，云 SDK 见 §10.13）。
21. **软删除语义**：`assetdel` / `topicassetdel` 采用 `delFlag="1"` 软删除（与 `query_ch_*` 的 `delFlag` 过滤一致），**不删除文件服务上的对象**；文件对象的回收（含孤儿对象清理）不在本轮范围。
22. **`ch_asset` 的派生列暂未启用**：`derivedFileID` / `derivedThumbID` / `derivedWidth` / `derivedHeight` / `derivedSizeBytes` 为后续「平台规格图」预留（C5 平台适配），本轮裁剪结果直接覆盖主图字段（`fileID`/`width`/`height`），派生列保持 NULL。
23. **封面唯一性在业务层保证**：`ch_topic_asset` 无「同主题仅一个 cover」的数据库约束，`demoteOtherCoverAssets` 在并发绑定时存在极小概率的双封面竞态；如需强一致需加唯一索引或事务（数据层生成器不支持复合唯一键，需手写 DDL）。

**SP2c 追加的已知限制 / 待办**：

24. **未做连库端到端渲染验证**：`topicrender` 经 `renderService` 真实取数（`ch_layout` / `ch_topic` / `ch_topic_asset`）需在有 MySQL 的机器上验收（先 `tools/initTables.py` + `tools/initSeed.py` 灌入 4 套版式与平台矩阵）。本轮只做了「不连库 fixtures 真实渲染（S22 + 冒烟）」。
25. **PNG 产物已由 SP3b 落地**：`longimage` / `swipe` 的 `outputKind=png`，SP2c 只产出「卡片/拼接蓝图 + 切片参数」（`meta.slices` / `meta.cards`）；**SP3b 起由 `engine/htmlToImage.py`（Playwright）真实截图生成 PNG**（小红书适配器消费 `meta.cards`/`meta.slices` 产出多张 1080×1440 卡片或切片，见 §9「SP3b 落地结论」）。
26. **渲染期派生尚未回写 `ch_artifact`**：`imageProc` / `htmlToImage` 的产物上传后返回 fileID 并出参，但 `ch_artifact` 登记与生命周期（`artifactKey`/`expireYMDHMS`）归 **SP3c**（SP3b 本轮不写库）。
27. **carousel 交互为自实现，微信兼容性待复验**：公众号对 SVG/脚本兼容不稳，模板已内置静态图集兜底；SP3 `inlineStyle.py` 内联化时需复验交互在微信正文的可用性（不可用则仅用静态兜底）。
28. **swipe 比例/格式/大小校验为引擎期前置校验**：正式合规校验（敏感词 / AI 标识 / 频次限流 + 平台规格）由 SP3 的 `complianceService.py` 承担；本轮引擎只做渲染前置（`E1`），二者口径需在 SP3 对齐。
29. **预览页为静态模拟**：`engine/templates/preview/` 仅视觉模拟（375×640 手机框），不做真机走查；验收以主计划 7.8 节创作平台实测为准（平台红线：不引入小红书自动发布）。
30. **`renderService._mergeAssetMeta` 为 N+1 查询**：逐张按 fileID 取 `ch_asset` 元信息（供 swipe 比例校验 / 长图切片）；图多时应改为按 topicID 批量取（当前同步渲染、量级可控）。

**SP3a 追加的已知限制 / 待办**：

31. **平台产物未做连库/真机验证**：`topicrender` 经 `renderService` 真实取数（`ch_layout` / `ch_platform` / `ch_topic` / `ch_topic_asset`）需在有 MySQL 的机器上验收（先 `tools/initTables.py` + `tools/initSeed.py` 灌入 4 套版式与 3 条平台矩阵）。本轮只做了「不连库 fixtures 平台产物渲染（冒烟）+ 桩替换取数的端到端（S23 追加冒烟）」。
32. **微信图片转存与投递未实现（属 SP4）**：外链图片转存到 `mmbiz.qpic.cn` 的链路未落地，本轮**非白名单外链一律 `E4` 显式报错**；`deliver` 一律 `C2`。凭据（`CH_WECHAT_APPID` / `CH_WECHAT_APPSECRET`）与转存 / `draft/add` 草稿投递在 SP4 接上（接点在 `wechatMp.DISPLAY_HOST_LIST` 与 `inlineStyle.resolveImageUrl`）。
33. **`wechatMp.checkHealth` 未做真实探活**：本轮只读 `ch_account` 与 `wechatSettings` 配置态（`networkRequest="0"`）；`access_token` 获取与凭据有效期巡检归 `schedule/credentialCheck.py`（SP3/SP4）。
34. **平台规格校验依赖「已知尺寸」**：`coverSpec` / `imageSpec` 只在图片来源尺寸已知时判定，尺寸未知（`ch_asset.width/height` 为 0）时不误报。渲染期派生归一（`imageProc`）与平台规格的联动在 SP3b 接上后，正文图可先归一再生效。
35. **`generic` 为降级实现**：HTML 复用 `stack_v1`（主计划 5.4 允许，省 1 人天）；独立通用版式与 `artifactpack` ZIP 打包归 SP4。
36. **小红书适配器已由 SP3b 落地**：`ADAPTER_MODULE_MAP` 现登记 `wechat_mp` / `generic` / `xiaohongshu`（SP3a 时小红书为显式 `C7`）；`XiaohongshuAdapter`（`deliverMode=asset_pack`）只做卡片 / 长图 / 滑动多图集的**形态转换与素材包清单**，`deliver` 仍一律 `C2`，**不含任何自动发布/投递路径**（平台红线）。
37. **`inlineCss` 的下沉能力有界**：只下沉「选择器全部指向 `img`」的规则（当前 4 套模板仅有 `[data-layout="X"] img{max-width:100%}`）；伪元素 / 复杂后代选择器无法安全内联，计入 `droppedRuleCount` 后丢弃。新增模板若引入复杂选择器样式，需相应扩展本函数。
38. **`PlatformAdapter.validate` 在 `render` 内前置调用**：规格不通过时直接返回错误、不做无效渲染；因此**渲染链路会因正文图尺寸未归一而拦截**（这是本轮有意的显式行为，避免产出不合平台规格的产物）。

**SP3b 追加的已知限制 / 待办**：

39. **小红书链路未做连库端到端验证**：`topicrender(platform=xiaohongshu)` 经 `renderService` 真实取数（`ch_layout` / `ch_platform` / `ch_topic` / `ch_topic_asset`）需在有 MySQL 的机器上验收（先 `tools/initTables.py` + `tools/initSeed.py` 灌入 4 套版式与 3 条平台矩阵）；本轮只做了「不连库 fixtures 的**真实截图**冒烟」。
40. **Chromium 为运行前置**：`engine/htmlToImage.py` 依赖 Playwright + Chromium（`python -m playwright install chromium`）；缺失时 `getBrowser()` 返回 `E1`（不抛裸异常）。Linux 部署需另装中文字体（`DEFAULT_FONT_FAMILY` 已含 `Noto Sans CJK SC` / 文泉驿回退），否则中文可能丢字 —— **须在部署清单中登记**。
41. **生产取图依赖文件服务可达**：冒烟用本地图片（渲染期内联为 data URI，零对外网络）；生产环境 `assetUrl` 为文件服务 URL，截图时会由浏览器直接拉取 —— 若为私有桶需确保渲染进程可达或改走「先 `imageProc.fetchLocalCopy` 取回本地再内联」的路径（SP3c 可评估）。
42. **`ch_artifact` 台账与合规校验归 SP3c**：本轮产物只出参（`products`/`fileIDs`）与素材包清单，不写 `ch_artifact`、不做 `complianceService` 敏感词/AI 标识校验；`artifactpack`（ZIP）仍为 `C2`（归 SP4）。
43. **swipe 比例校验依赖源图尺寸已知**：`ch_asset.width/height` 为 0（尺寸未知）时不做比例判定（不误报），交由渲染期归一；如需强一致，应在素材入库时保证 `width/height` 已写入。
44. **长图切片按实际渲染高度**：切片数 = `ceil(长图实际总高/sliceHeight)`（非估算值），故与 `meta.estimatedTotalHeight` 可能不同；`maxTotalHeight` 上限以实际总高判定（超限 `E3`）。

**SP3c 追加的已知限制 / 待办**：

45. **合规/台账/任务化链路未做连库运行验证（本机无 MySQL/Redis 服务端）**：本轮只做了 py_compile + AST 静态检查（S25）与「不连库」的纯函数/桩替换冒烟（`test_sp2c_render_smoke.py` 的 SP3c 7 项）。`ch_render_job` 建档/状态跃迁、`ch_artifact` 幂等写入、`inputHash` 复用的真实读写、`renderWorker` 真实消费 `PENDING` 需在有 MySQL 的机器上验收（先 `tools/initTables.py` + `tools/initSeed.py`）；**四项桩验证/真实执行的边界已在 §1「SP3c 追加冒烟」与 §9 第 12 条显式标注**。
46. **Redis 降级为进程内计数，多进程/多实例下窗口不共享**：限流与任务锁在 Redis 不可用时各自退化为**进程内**实现，故降级期间跨进程频次统计不准确、任务锁退化为「单实例串行 + 进程内去重」。本机验证时该路径为**默认路径**（无服务端）；生产须确保 Redis 就绪，否则应视为「降级运行」并纳入告警。
47. **`artifactVer` 递增为「先按键查询再 upsert」两步**：并发对**同一 job 的同一产物键**重复写入时存在极小竞态（`ch_artifact` 无复合唯一索引，生成器不支持复合唯一键；`artifactKey` 单列 `UNIQUE` 已保证不产生重复行，但版本号可能少增）。如需强一致需手写唯一索引/加锁（同 §10.23 的封面竞态口径）。
48. **`job` 模式不支持 `specOverride`**：`ch_render_job` 无 spec 列（`memo` 仅 200 字符），故异步任务一律按 `ch_layout.specJson` 渲染，覆盖参数不随任务持久化；需要覆盖请走 `sync`，或后续扩表登记 `specJson` 字段。
49. **过期清理不在 SP3c（归 SP4）**：`artifactStatus=EXPIRED` 已定义但**本轮不触发**清理；`ch_artifact.expireYMDHMS` 只写不消费。归档/清理任务与审计日志归档策略（主计划 3.4.6）一并归 SP4。
50. **敏感词词表为模块内默认值**：`DEFAULT_SENSITIVE_WORD_LIST` 是**内容规则**的占位实现（不违反「平台规格单一来源」），生产应改为配置项或独立词库表；当前可按请求 `dataSet.sensitiveWords` 覆盖，且大小写/分词口径为「原样子串匹配」（不含分词与谐音变体）。
51. **限流阈值（默认 30 次/小时）为保守默认值**：需按平台风控与账号等级细化；且限流归因账号优先取「请求 `accountID`/`ownerID` → 会话 `loginID` → 主题 `ownerID`」，**尚未与 `ch_account` 的平台账号矩阵联动**（平台账号级限流需在 SP4 与 C6 投递一并收口）。
52. **`renderWorker` 未做守护化/心跳监控**：未提供 systemd/Windows 服务脚本与健康心跳（★ SP4c 已建立 `chmonitor/`（心跳/指标/告警）与 `monitor/`（museum 迁移的守护层），但 **`renderWorker` 自身仍未接入心跳/守护**）；`RUNNING` 卡死任务的超时回收（`WAITING→FAILED` 的看门狗）未实现，当前依赖 Redis 锁 TTL（300s）与人工干预，长任务需注意 TTL 与渲染耗时的关系。
53. **【SP4a 已解决】`publishcheck` 与投递闸门已串联**：`publishpush` 落地后，投递路径在 `publishService` 内**强制调用** `complianceService.publishCheck`，未过校验直接阻断（S26 + 投递冒烟断言「未过合规校验 → `deliverCalls=0`」）。★ `artifactpack`（ZIP）仍为 `C2`，归 SP4 余下部分。

**SP4a 追加的已知限制 / 待办**：

54. **★ 公众号投递链路未端到端打通真实平台（本机无凭据）**：本机 `CH_WECHAT_APPID`/`CH_WECHAT_APPSECRET` 未配置，本轮按 **(B) 口径**只做「载荷构造 + 桩替换 HTTP 调用」验证（见 §1 凭据现状声明）。**凭据就绪后必须补做**：真实 `get access_token` → `media/uploadimg`（正文图转存）→ `material/add_material`（封面）→ `draft/add`（回读真实 `errcode/errmsg/media_id`），并在公众号后台核对草稿内容与真机排版（主计划 7.4 步骤 7、8.5 灰度纪律：先小范围验证草稿正确性再扩大）。
55. **凭据写入 `ch_account` 尚无对外端点**：`publishService.saveAccountCredential` **已实现**（AES-256-GCM 加密后只落 `credentialCipher/credentialIV`，明文不落库），但**未暴露 REST/MCP 端点**（受「不新增 CMD」约束）；当前需由运维脚本或后续子计划提供录入入口；`schedule/credentialCheck.py`（P3-6 定时探活/到期告警）仍归 SP4。
56. **撤销仅置本地记录状态**：60 秒撤销窗把 `ch_publish_record.delFlag` 置 `1` 并留审计，**不调用平台删除草稿**（`wechatSettings.WECHAT_API_PATH` 未含 `draft/delete`）；如需同步删除平台草稿，应在凭据就绪后新增通道原语并补齐撤销语义（当前出参已注明「平台侧草稿请人工处理」）。
57. **`ch_publish_record` 无独立状态列**：撤销窗/投递态以 `success`+`delFlag`+`pushedYMDHMS` 组合表达（本轮约定，见 §4）。若后续需更细状态（如 `PENDING/CONFIRMED/REVOKED`）或需「撤销后重投」，应按主计划 8.6 红线走「新增列 + 双写过渡」而非 `drop_*`。
58. **`artifactID` 在草稿投递中可为 0**：`wechat_mp` 的 HTML 产物当前不落 `ch_artifact`（该表主用于 PNG 产物），故草稿投递允许 `artifactID=0`（`layoutCode` 现场渲染）；传了 `artifactID` 则强制 `READY`。`ch_publish_record.artifactId` 为 `NOT NULL`，未关联时落 `0`（「0 = 未设置」口径）。
59. **`wechatMp` 的 `deliver` 会真实联网**：SP4a 起 `wechatMp.py` 不再零网络（`urllib` 调开放平台接口），故 S23 的零网络扫描已将其移出（`base`/`generic`/`xiaohongshu`/`inlineStyle`/`htmlToImage` 仍零网络）；`submitFreePublish` 虽已实现但**默认不可达**（三重闸门）。
60. **`secret` 类字段脱敏为「键名子串匹配」**：`auditService.SENSITIVE_FIELD_TOKEN_LIST` 命中即掩码，存在误伤（如业务字段名含 `key`）与漏判（如自定义名 `cred`）的可能；新增凭据字段时应同步维护该清单。

**★★ SP4b 追加的「尚欠项」（必须登记，不得视为已闭环）**：

1. **尚欠项 ①：SP4d 真凭据验证（公众号草稿箱真实落地）** —— 本机无 `CH_WECHAT_APPID`/`CH_WECHAT_APPSECRET`、无 KMS，SP4a 的投递链路与 SP4b 的凭据巡检都只做到「载荷构造 + 桩替换 HTTP」与「探活分支验证」。**待凭据就绪的机器上补做**：`saveAccountCredential` 真实写入 `ch_account` → `credentialCheck` 真实换取 `access_token`（校验 `healthStatus` 由 `UNKNOWN` 变 `OK`）→ `publishpush` 真实调用 `media/uploadimg` / `material/add_material` / `draft/add` 并在公众号后台核对草稿内容（主计划 7.4 步骤 7 / 8.5 灰度纪律）。
2. **尚欠项 ②：M2 真机 / 手机尺寸模拟排版核对** —— 主计划 6.4 **R-08**（微信 HTML 兼容性 / 手机端排版错乱，列为「排版类产品口碑生死线，纳入 M2 出口标准」）尚未在真机走查；`engine/templates/preview/` 仅为 375×640 静态模拟。**待补做**：用真实草稿预览链接在 iOS/Android 微信客户端逐版式核对（重点 carousel 静态兜底与图片显示域），并登记走查结论。
3. **尚欠项（人工项）：7.8 第 12 项「平台实测复核」** —— 主计划 7.8 明确定义为**人工项**（第三方资料可能滞后于平台调整），**不由代码完成**。**待补做**：上线前在小红书创作服务平台实测复核图片数量 / 比例 / 大小规则，并登记复核人与日期。
4. **`artifactpack` 未做连库端到端（★ 本条保留）**：`ch_artifact` 取数为桩替换（本机无 MySQL）；台账取数路径的 SQL 落点由静态 S27 与冒烟桩验证覆盖，真实读写需在有 MySQL 的机器上验收（先 `tools/initTables.py` + `tools/initSeed.py`）。★ SP4c 现状：`ch_artifact` 台账新增「过期清理」与「存储用量监控」两条消费路径（`archive.py` / `chmonitor/`），但 **`artifactpack` 与归档的连库端到端仍未做**。
5. **【SP4c 已收口（裁定）】素材包 ZIP 生命周期**：★ 裁定 **素材包 ZIP 不登记 `ch_artifact`**（台账语义单一：`ch_artifact` = 渲染产物台账；其唯一键口径 `{jobID}:{kind}:{platform}:{seqNo}` 与 `jobID NOT NULL` 不适配「一次性导出且可多次、无 job 归属」的 ZIP，登记会造成同键覆盖/旧 ZIP 变孤儿对象）。ZIP 生命周期由**对象存储生命周期策略 / 人工保留策略**管理；归档清理只处理**渲染产物**（`ch_artifact` 置 `EXPIRED` 并删对象）与**审计日志**（`ch_audit_log`）。裁定已写入 §4「素材包 ZIP 台账裁定」。
6. **素材包不产出 HTML 形态**：小红书只输出 PNG 图集（swipe 卡片 / longimage 切片）；`stack`/`longimage` 源图若高 > 1440，SP3c 的「超长整图前置拦截」会在合规闸门处返回 `E3`（**要求先切分**）——这是有意的显式行为（7.8 第 9 项），不是缺陷。
7. **`mcpinvoke` 的鉴权依赖接入层会话与 Redis 双源**：token 优先走 `comDB.getSessionInfo`，Redis 不可用时回落到经账号服务校验过的会话上下文（`sessionIDSet`）并记告警——即**Redis 不可用不会放宽权限判定口径**，但会降低「token 与角色绑定」的强一致性；生产须确保 Redis 就绪。
8. **MCP 只读层依赖 `mcp<2`**：`mcpapi/` 基于 v1 的 `mcp.server.fastmcp.FastMCP` + `mcp.server.auth.*`，**不得改动其既有逻辑**；升级 mcp 2.x 需先在独立子计划内完成 API 迁移（`MCPServer`）并复跑 9.6.6 十项，本工程只做依赖锁定。
9. **【SP4c 已收口】巡检守护化与监控接入**：`schedule/credentialCheck.py` 已补**常驻定时入口 `--loop`**（`--interval` / `CH_CREDENTIAL_CHECK_INTERVAL` 默认 3600s；单实例 + Redis 锁可降级，与 `renderWorker` 同风格）与单次执行入口（供 cron/计划任务）；告警已**对接 `chmonitor/alertChannel`**（可插拔通道，默认落盘，占位通道零网络），不再只写日志；每次运行刷新 `chmonitor/heartbeat`；配套运行脚本 `tools/runOpsJobs.ps1`。
10. **巡检的 `EXPIRING` 依赖 `ch_account.expireYMDHMS`**：该列未填（NULL）时巡检一律判 `OK`（无法预知到期）；建议凭据录入时一并写 `expireYMDHMS`，否则「到期前预警」形同虚设。
11. **★ 尚欠项（本轮明确口径）：MCP 服务端端到端联调未做** —— 本轮按确认口径 **不联调**（不启动 `mcp_entry.py`、不监听端口），故 9.6.6 的 **①无 token → 401 / ②无效 token → 拒绝** 两项**未执行**，③–⑩ 亦为「直调实现层（部分为桩）」而非真实网络调用。**待补做**：在具备 Redis 服务端的机器上 `python mcpapi/mcp_entry.py`（监听 **8891**），以真实 `sessionID` 走 streamable-http `/mcp` 复跑 9.6.6 **十项全量**（含 ①② 的真实 401/拒绝与 ③ 的真实 Redis 会话放行），并登记实测结论。

**SP4c 追加的已知限制 / 待办**：

61. **归档/监控链路未做连库运行验证（本机无 MySQL/Redis 服务端）**：本轮只做了 py_compile + AST 静态检查（S28）与「不连库」的桩替换冒烟（`test_sp2c_render_smoke.py` 的 SP4c 5 项）；`ch_audit_log` 真实分批导出/删除、`ch_artifact` 真实置 `EXPIRED`/对象删除、七项指标真实取数需在有环境的机器上验收（先 `tools/initTables.py` + `tools/initSeed.py`）；**真实执行/桩验证边界已在 §1 SP4c 口径声明与 §9 第 10 条逐项标注**。`chmonitor/dailyCheck.py` 本机运行会因取数失败走 `degraded` 降级路径（报告仍产出，`存储用量` 为真实磁盘使用率）。
62. **★ 归档真删需显式确认且不可逆**：`schedule/archive.py` 默认 dry-run；`--execute` / `CH_ARCHIVE_EXECUTE=1` 才会真删。**首次真删前务必先在测试库演练**（主计划 8.6 红线：生成器无 migration，误删不可逆）。`ch_artifact` 清理只删**对象**并置 `EXPIRED`，**不删除台账行**（保留审计线索）；如需回收台账行需另立脚本。
63. **对象删除失败仅告警不重试**：`delFile` 失败时记录告警（`archive.artifact_purge` 审计 `result=FAIL`）并保持 `EXPIRED`，**无自动重试/补偿**；运维需按告警人工处理（可重跑 `--only artifact`）。审计归档导出失败的批次同样**不删除**，重跑即可。
64. **归档导出对象不参与清理**：归档产物（`archive/audit/*.json.gz|csv`）经文件门面上传，**不在本子计划的清理范围内**（与素材包 ZIP 同口径，由对象存储生命周期/人工策略管理）。
65. **监控首期为降级口径**：**仅日志落盘告警 + 每日巡检脚本 + 占位通知接口**，**不做看板/时序数据库**，`email`/`wecom` 未接入（占位、零网络）；「存储用量」在 `SELFFILE` 之外无统一容量接口 → 返回未知（`INFO`，不误报）；「渲染失败率」等窗口指标按 `ch_render_job.regYMDHMS` 近似统计（非精确滑动窗口）；「审计日增量」以查询条数（`LIMIT` 上限内）近似计数。
66. **告警通道对接为「接口就绪」而非「通道连通」**：主计划 8.4 上线检查「监控告警通道连通性验证（故意触发一次测试告警）」仍需在选定真实通道（邮件/企微）后补做并登记接收人确认。
67. **定时任务心跳为本地文件**：`chmonitor/heartbeat.py` 落 `code/data/monitor/heartbeat.json`（单机语义）；多实例部署时各实例心跳互不共享，跨实例「最后成功时间」判定需改为共享存储（本首期不引入新中间件）。`tools/runOpsJobs.ps1` 需由 cron/Windows 计划任务按周期调用（本机未实际配置调度）。
68. **★ `monitor/` 迁移代码的部署边界（已剥离进程守护）**：`monitor/` 由 `museum/code/src/monitor` 迁移改造后，**进程 / 端口 / 服务守护能力已按 contentHub 零网络红线剥离**（改为显式不支持并记日志），故它**不能替代系统级进程守护**（systemd / Windows 服务）；`crontab.txt` / `restore_monitor.sh` 为 **Linux 部署样例**（路径已改 contentHub），Windows 请用 `tools/runOpsJobs.ps1` + 计划任务；shell 脚本内的 `ps` / `kill` 属部署层面操作，**未纳入 S23/S28 扫描**（扫描对象为 Python 文件）。
69. **★ `monitor/` 与 `chmonitor/` 的功能边界**：`chmonitor/` = 七项指标 / 告警通道 / 心跳 / 每日巡检（SP4c 核心，已入 45 项冒烟逐项断言）；`monitor/` = 文件变化守护 + 告警汇总（复用 `chmonitor`），本机仅做**入口实测**（`-h` / 直接运行 / `run_alert`），其行为由 S28 静态校验与入口实测覆盖，**未纳入既有冒烟逐项断言**。
70. **★ 迁移未做数据 / 配置迁移**：museum 的 `monitorConfig.py` 中 museum 专属的 `processData` / `serviceMonitorData` 未迁移（已在 contentHub 版置空，并注明原语已剥离）；如需在 contentHub 承载进程守护，须另行设计且不得引入违规原语。

> **§10 收口说明**：本轮 **SP4c 收口第 4 条（`ch_audit_log` 归档）、SP4b 尚欠项第 5 条（素材包 ZIP 台账裁定）、SP4b 尚欠项第 9 条（巡检守护化/接监控）**；**其余条目明确保留** —— 尤其：SP4b 尚欠项第 1/2/3 条（真凭据验证 / M2 真机排版 / 7.8 平台实测复核，均需外部环境或人工）、第 4 条（`artifactpack` 连库端到端）、第 6/7/8/10/11 条（HTML 形态 / mcpinvoke 会话双源 / `mcp<2` / 巡检 `EXPIRING` 依赖 `expireYMDHMS` / MCP 服务端联调），以及 §10 第 54–60 条（SP4a 遗留：真平台投递未打通 / 凭据无端点 / 撤销不删平台草稿 等）。

---

## 11. 移植表登记（user_basic / weixin_pay）

**来源**：`ylwzProject/museum/code/src` 的 `database/userBasic.txt`、`database/weixin_pay.txt` 与 `common/mysqlCommon.py` 对应段落。
**本轮口径（已与需求方确认）**：① 原样移植（保留原表名/原主键/原列，**不套用 ch_* 的 recID + 尾部七字段红线**）；② `USER_BASIC` 的列集合以 museum 手写 `createUserBasic()` 为准并同步定义文件；③ 本轮**只落数据层**，账号域（`accountApi`）下轮再切回本地用户表；④ `weixin_pay` 只落数据层 + 建表，**不暴露 REST 端点**（权限矩阵与 69 CMD 基数不变）。

### 11.1 移植清单

| # | 表 | 形态 | 落点 | 内容 |
|---|---|---|---|---|
| 1 | `USER_BASIC`（用户账号主表，主键 `loginID`） | **手写段** | `common/mysqlCommon.py` 的「外部既有表」段（生成区标记之前） | `genOrList` + 8 个函数：`createUserBasic / dropUserBasic / queryUserBasic / deleteUserBasic / insertUserBasic / updateUserBasic / getUserInfoMysql / statUserBasic`（约 740 行，逐行照搬 museum `mysqlCommon.py` L265-1005） |
| 2 | `weixin_pay`（微信支付/退款流水，主键 `sortID`，业务唯一键 `tradeNo`） | **生成段** | `common/mysqlCommon.py` 生成区（`tools/mergeMysqlCommon.py` 合并） | `tablename_convertor_/decode_/create_/drop_/delete_/insert_/update_weixin_pay` 共 7 个（产物 `auto_generated/auto_gen_code_weixin_pay.py` + `word_table_weixin_pay.csv`） |
| 3 | `weixin_pay` 多条件检索 | **手写段** | 同上「外部既有表」段 | `query_weixin_pay(tableName, tradeNo, parentTradeNo, productID, loginID, startYMDHMS, endYMDHMS, delFlag, mode, order, limitNum)`（museum L1629-1705） |

**建表登记**：`tools/initTables.py` 新增两个清单 —— `EXTRA_GENERATED_TABLE_LIST = ["weixin_pay"]`（走 `create_weixin_pay(tablename_convertor_weixin_pay())`）与 `EXTRA_HANDWRITTEN_TABLE_LIST = ["USER_BASIC"]`（走手写 `createUserBasic()`，无参数）。

### 11.2 与 museum 的两处必要差异（已登记）

| # | 差异 | 原因与处置 |
|---|---|---|
| 1 | `USER_BASIC` 共 **44 列** = museum DDL 43 列 + 1 个追加列 | 追加列 `extSessionID VARCHAR(48)`：contentHub 新增（本表在初始化前的会话标识），museum 无此列；落在 `passwdYMDHMS` 之后、`extStartYMDHMS` 之前，`database/userBasic.txt` 与 `createUserBasic()` DDL 逐列一致（S19 锁定），并同步进 `insertUserBasic`（写入）/ `updateUserBasic`（非空才更新）/ `getUserInfoMysql`（出参返回）；纯追加可空列，不影响既有读写。★ **2026-09-20 修正**：museum 侧仅在 `.txt` 与 `museumAPIPost.py`（usersearch 的 searchOption 白名单）引用、而手写 `createUserBasic()` 漏建的 `extOverallEvaluation VARCHAR(2000)` 已**整体删除** —— `database/userBasic.txt` 与 `createUserBasic()` DDL 同步移除（45 列 → 44 列）；原因是该列在 contentHub **无任何读写路径**（`insertUserBasic` / `updateUserBasic` / `getUserInfoMysql` 三处均未覆盖），保留只会造成「表有列、代码无路径」的定义漂移 |
| 2 | `weixin_pay` 定义文件被规范化为生成器可解析形式（`sortID INT AUTO_INCREMENT NOT NULL PRIMARY KEY` + `tradeNo ... UNIQUE` + 类型大写） | museum 的 `weixin_pay.txt` 首字段缺少 `PRIMARY KEY` 关键字（生成器据 `PRIMARY KEY` 判定主键），直接喂给生成器会产出非法签名（如 `delete_weixin_pay(tableName,)`）。规范化后 `create_weixin_pay` 的 DDL 与 museum 实际表结构**等价**（PK=sortID、UNIQUE(tradeNo)）。因此 `delete_/update_/query_weixin_pay` 以 `sortID` 为键，而 museum 的对应函数以 `tradeNo` 为键（museum 该段为历史手改，与 `create` 的 DDL 自相矛盾）；tradeNo 维度的检索由手写 `query_weixin_pay` 提供，行为等价 |

### 11.3 本轮未做（后续待办）

1. **账号域未切换**：`accountApi` 的 `chkuserexist / getuserinfo / usersearch / userinfoqry` 仍为「账号服务 A3A0/AIA0 + Redis 档案」的降级实现；下轮切到 `comMysql.queryUserBasic / getUserInfoMysql / insertUserBasic / updateUserBasic` 后，可恢复与 museum 的行为等价（含 `statUserBasic`、`extOrgID/activeFlag` 等扩展列）。
2. **未暴露 REST 端点**：`userbasic*` / `weixinpay*` 未进入 `subfunc/crudApi.py` 与 `ROLE_CMD_LIST`；`weixinpayadd/del/modify/qry` 的产物处理段已生成但未装配。
3. **未做数据迁移**：移植只建空表；museum 既有数据的迁移（如需）另行评估。
4. **`USER_BASIC` 的索引**：`createUserBasic()` 保留 museum 的两个 `CREATE INDEX`（roleName / extJobLabel）；`weixin_pay` 的 `loginID` 非唯一索引未生成（生成器不支持非唯一索引），如检索性能需要请加 DDL 或建索引脚本。
