#! /usr/bin/env python3
#encoding: utf-8

#Filename: test_ch_phase0_static.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub SP1(Phase 0 数据库链路) + SP1.5(S2 接入层拆分) 无依赖静态验收脚本。
#
#设计约束: 不连数据库、不连 Redis、不连文件服务, **不 import 任何需要第三方库的项目模块**
#(pymysql/oss2 等未安装时也能跑), 只做: 语法编译 + AST 符号核查 + 定义文件格式核查 + 产物计数。
#
#覆盖项:
#  S1  新增/修改模块全部通过 py_compile
#  S2  12 个 ch_*.txt 齐备且符合写法红线(无制表符/无百分号/无井号/单空格/首字段/尾部七字段)
#  S3  12 份产物 py + 12 份接口文档 csv 齐备
#  S4  产物函数名合法(无 func['xxx'] 形态), 4 个 REST 处理器命名与 _CRUD_TITLES 对齐
#  S5  mysqlCommon.py 生成区齐备(12 表 × 8 个数据层函数), 且未混入 REST 处理器
#  S6  mysqlCommon.py 手写段齐备(公共件 + 12 个扩展 query_ch_*)
#  S7  globalDefinition.py 已补齐 3 个 MCP 日志常量 + 2 个 Web 入口日志常量
#  S8  chCommon.py 暴露 upsertByUniqueKey / fillFileUrls
#  S9  config 缺口已补(mysqlSettings / wechatSettings)
#  S10 tools 三脚本齐备且有 main()
#  S11 跨模块符号闭环(tools 与产物对 comMysql/comCh/comFS 的引用均有定义)
#  S12 delFlag 取值约定("0"/"1", 禁止 comGD._CONST_NO)
#  (SP1.5 追加)
#  S13 接入层结构与行数上限(chAPIPost ≤1000 / subfunc ≤900, crudApi 作为生成件豁免)
#  S14 subfunc/ 无反向 import chAPIPost|chAPI(防循环依赖)
#  S15 crudApi 覆盖 48 个 CRUD CMD 且注册表指向已定义处理器
#  S16 聚合器 mergeCmdMaps 的 V1/V2/V3 三道校验可真触发(AST 抽取 + 隔离执行)
#  S17 错误消息模块(errMsgCommon 零依赖 / contenthub 键 / applicationMsgKey 归一并覆盖 CG / funcCommon 只 re-export)
#  S18 注册表静态覆盖(账号域 19 + 业务域 5 + CRUD 48, 无重名) 与 chCommon 真实引用(CI-C5)
#  S19 外部既有表移植(user_basic/weixin_pay): 定义文件与建表 DDL 逐列一致 + 函数齐备 + 建表脚本登记
#  (SP2a 追加)
#  S20 SP2a(C2 主题管理): topicService 函数/常量齐备 + 只经 comMysql/comCh(禁裸 SQL) +
#      错误码落点真实存在 + topicApi 接管 8 端点(topicrender 已于 SP2c 迁出) + crudApi 不再装配被接管表
#  (SP2b 追加)
#  S21 SP2b(C3 素材图库): assetService 函数/常量齐备 + 只经 comMysql/comCh/fileStorageCommon(禁裸 SQL) +
#      错误码落点真实存在 + assetApi 接管 8 端点(artifactpack 已于 SP4b 落地, 素材域占位清空) + crudApi 不再装配被接管表
#  (SP2c 追加)
#  S22 SP2c(C4 版式引擎): engine 包 + 4 套模板齐备 + layoutType 与模板目录一一对应 +
#      specJson 既有键被真实消费 + topicrender 归属唯一(renderApi) + 模板无平台专属硬编码 +
#      carousel 有交互与静态兜底 / swipe 不自实现交互 + 引擎层不反向依赖
#  (SP3a 追加)
#  S23 SP3a(C5 平台适配层): platformAdapter 四文件 + engine/inlineStyle.py 齐备 +
#      PlatformAdapter 契约五方法齐备 + deliver 显式未实现(C2) + ch_platform 数据驱动规格校验生效 +
#      inlineStyle 输出无 class 依赖且外链图片策略生效 + 适配器零网络 + topicrender platform 分支可达且无新增 CMD
#  (SP3b 追加)
#  S24 SP3b(C5 小红书产物渲染): xiaohongshu 适配器 + htmlToImage 截图管线齐备 +
#      小红书适配器契约齐备且不覆写 deliver(未实现) + 无自动发布/投递红线 +
#      xiaohongshu 从 C7 迁移(注册表登记 + renderService 无硬编码) + carousel 显式不可用(C7) +
#      swipe 强校验(比例统一/张数)错误码落点 + E2/E3 落点 + htmlToImage 零网络/分层
#  (SP3c 追加)
#  S25 SP3c(C8 合规校验 + 产物台账 + 渲染任务化):
#      complianceService 齐备且**复用 base.checkPlatformSpec / xiaohongshu.validateSwipeSpec**(禁重写规则表) +
#      问题清单结构(field/location/level/errCode/message + 敏感词偏移区间) + 限流降级路径存在 +
#      renderService 任务状态机(PENDING->RUNNING->DONE/FAILED)与 inputHash 复用 + artifactKey 幂等 +
#      renderWorker 单实例串行且无并发截图 + publishcheck 已实现(占位清空)且端点总数不新增
#  (SP4a 追加)
#  S26 SP4a(C6 投递链路): 凭据 AES-256-GCM 公共件(密钥来自环境变量 CH_CREDENTIAL_KEY, 明文不落库/不入代码库,
#      无密钥显式报错不崩溃) + publishService(幂等键 {artifactID}:{accountID}:{uuid4} / 二次确认参数必填 /
#      60 秒撤销窗状态机 / 投递前必须复用 complianceService.publishCheck / 产物 READY 前置 / 凭据解密 F0 /
#      审计成功失败都留痕 / freepublish 默认关闭) + auditService(ch_audit_log 字段齐备 + payloadDigest 脱敏)
#      + publishApi 接管 publishpush(不新增 CMD, 占位清空) + ★ 静态扫描确认不存在小红书投递/发布代码路径
#  (SP4b 追加)
#  S27 SP4b(素材包 ZIP + MCP 接入 + 凭据巡检): artifactService(7.8 条目齐备 / 风险告知与滑动提示 /
#      **未过合规校验不得出包** / 合规规则单一来源不复写 / 只经 fileStorageCommon / 无投递-发布路径) +
#      assetApi.artifactpack 落地(占位清空, 不新增 CMD) + mcpApi 薄入口(仅转发不承载协议解析 /
#      ROLE_CMD_LIST·MCP_TOOL_LIST 校验落点 / G0-G3) + mcpapi 既有 8 tool·3 resource 未改动 +
#      **MCP 监听端口 8891(配置取值, 禁硬编码; 本轮不联调)** +
#      credentialCheck(healthStatus 四态 + R-03 分级告警 + 公众号探活复用 C6 凭据解密 + 小红书跳过说明) +
#      accounthealth 内接入巡检(不新增 CMD) + 端点总数仍 69(★ 2026-09-20 起为 72: 账号域补齐 useradd/usermodify/userdel)
#  (SP4c 追加)
#  S28 SP4c(归档清理 + 监控告警 + 巡检守护化): schedule/archive.py(归档 dry-run 为默认 /
#      先导出后删除顺序 / 分批与保留期可配 / 破坏性操作需显式确认 / 产物清理先置 EXPIRED 后 delFile /
#      审计留痕落点 / Redis 锁可降级) + chmonitor/(七项指标与阈值可配 / 告警级别 INFO-WARN-ERROR /
#      告警通道为占位且无网络调用 / 每日巡检脚本入口) + monitor/(由 museum 迁移改造: 零网络 / 剥离 museum 依赖与子进程原语 /
#      复用 chmonitor) + credentialCheck 守护化入口(--loop 单实例) +
#      config/opsSettings.py 可配项齐备; ★ S23 零网络扫描同步纳入 chmonitor/ 与 monitor/
#
#用法: cd code/src && python test/test_ch_phase0_static.py

_VERSION="20260918"

import ast
import json
import os
import py_compile
import re
import sys
import tempfile

_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATABASE_DIR = os.path.join(_SRC_DIR, "database")
_AUTO_GEN_DIR = os.path.join(_DATABASE_DIR, "auto_generated")
_MAIN_DIR = os.path.join(_SRC_DIR, "main")
_SUBFUNC_DIR = os.path.join(_MAIN_DIR, "subfunc")

#SP1.5(S2 拆分结构) 期望值 —— 与 plan/chAPIPost分拆方案.md 3.1 / 5.4 / 9.1 一致
SUBFUNC_FILE_LIST = [
    "__init__.py", "context.py", "apiCommon.py", "accountSvcClient.py", "accountApi.py",
    "crudApi.py", "topicApi.py", "assetApi.py", "renderApi.py", "publishApi.py",
    "complianceApi.py", "mcpApi.py",
]

#行数上限(方案 A1/A2); crudApi.py 为「生成件装配」(约 5000 行), 按决策豁免上限
#★ 2026-09-21 调整(plan/出参信封统一改造.md): chAPIPost 上限由 400 放宽为 1000
#★ 2026-09-23 调整(第三方账号管理): subfunc 单文件上限由 900 放宽为 1500
#  (accountApi.funcAccountHealth 需增加归属收窄逻辑, 原 887/900 余量不足以承载手改注释)
CH_APIPOST_MAX_LINES = 1000
SUBFUNC_MAX_LINES = 1500
SUBFUNC_LINE_EXEMPT_LIST = ["crudApi.py"]

#账号域 CMD(contentHub 的 NO_SESSIONID_CMD_LIST ∪ ROLE_CMD_LIST 反推, 共 19 个;
#★ 2026-09-20: 补齐 museum 账号域三端点, 16 -> 19)
ACCOUNT_CMD_LIST = [
    "chkuserexist", "registration", "login", "logout",
    "usersearch", "userinfoqry", "getuserinfo",
    "smsrequest", "smsverify", "resetpasswd",
    "usersavedata", "usergetdata", "generalnext",
    "genusersessionid", "gethomepagedata", "accounthealth",
    #管理员专用(settings.USER_ADMIN_ROLE_LIST; useradd 与 registration 独立)
    "useradd", "usermodify", "userdel",
]

#SP2a 主题域业务端点(topicApi 接管, 内部走 processor/topicService.py)
TOPIC_CMD_LIST = [
    "topicadd", "topicdel", "topicmodify", "topicqry",
    "topicversionadd", "topicversiondel", "topicversionmodify", "topicversionqry",
]

#SP2b 素材域业务端点(assetApi 接管, 内部走 processor/assetService.py)
ASSET_CMD_LIST = [
    "assetadd", "assetdel", "assetmodify", "assetqry",
    "topicassetadd", "topicassetdel", "topicassetmodify", "topicassetqry",
]

#6 个业务端点按域分布(方案 4.1「新接口按域拆」; renderApi 本期为空, V3 为超集校验)
#SP2a/SP2b: topic 域与 asset 域在「1 个业务端点」之上, 再各接管 8 个 CRUD 端点(见 CRUD_TAKEOVER_TITLE_LIST)
#SP2c: topicrender 由 renderApi(渲染域)接管(topic 域 9 -> 8, render 域 0 -> 1)
BIZ_CMD_DOMAIN_MAP = {
    "topic": TOPIC_CMD_LIST,
    "asset": ASSET_CMD_LIST + ["artifactpack"],
    "render": ["topicrender"],
    "publish": ["publishpush"],
    "compliance": ["publishcheck"],
    "mcp": ["mcpinvoke"],
}

#外部既有表移植(见 plan.md §11): 不套用 ch_* 的 recID/尾部七字段红线, 由 S19 单列校验
USER_BASIC_TXT = "userBasic.txt"
WEIXIN_PAY_TXT = "weixin_pay.txt"

#USER_BASIC 手写段(user family, 移植自 museum mysqlCommon L282-1005)
USER_BASIC_FUNC_LIST = [
    "createUserBasic", "dropUserBasic", "queryUserBasic", "deleteUserBasic",
    "insertUserBasic", "updateUserBasic", "getUserInfoMysql", "statUserBasic",
]

#USER_BASIC 查询依赖的公共件(移植自 museum mysqlCommon L265-277)
USER_BASIC_HELPER_FUNC_LIST = ["genOrList"]

#weixin_pay 生成段的数据层函数(由 mergeMysqlCommon 合并进 mysqlCommon 生成区)
WEIXIN_PAY_GENERATED_FUNC_LIST = [
    "tablename_convertor_weixin_pay", "decode_tablename_weixin_pay", "create_weixin_pay",
    "drop_weixin_pay", "delete_weixin_pay", "insert_weixin_pay", "update_weixin_pay",
]

TABLE_NAME_LIST = [
    "ch_topic",
    "ch_topic_asset",
    "ch_asset",
    "ch_layout",
    "ch_platform",
    "ch_render_job",
    "ch_artifact",
    "ch_account",
    "ch_publish_record",
    "ch_mcp_token",
    "ch_audit_log",
    "ch_topic_version",
]

#与 config/basicSettings.py 的 _CRUD_TITLES 一致
CRUD_TITLE_LIST = [
    "topic", "topicasset", "asset", "layout",
    "platform", "renderjob", "artifact", "account",
    "publishrecord", "mcptoken", "auditlog", "topicversion",
]

#SP2a/SP2b: 由业务域接管的表标题 —— topicApi(topic/topicversion)、assetApi(asset/topicasset) ——
#不再由 crudApi 装配(见 tools/mergeCrudApi.py::EXCLUDED_TABLE_LIST 与 code/src/plan.md §7)
CRUD_TAKEOVER_TITLE_LIST = ["topic", "topicversion", "asset", "topicasset"]

#crudApi 实际装配的 CRUD 标题与条数(48 - 16 = 32)
CRUD_API_TITLE_LIST = [t for t in CRUD_TITLE_LIST if t not in CRUD_TAKEOVER_TITLE_LIST]
CRUD_API_CMD_TOTAL = len(CRUD_API_TITLE_LIST) * 4

#topicService 必须具备的业务函数与常量(S20)
TOPIC_SERVICE_FUNC_LIST = [
    "addTopic", "modifyTopic", "deleteTopic", "queryTopic",
    "addTopicVersion", "modifyTopicVersion", "deleteTopicVersion", "queryTopicVersion",
    "saveTopicSnapshot", "countWords", "validateTopicFields", "checkStatusTransition",
]
TOPIC_SERVICE_CONST_LIST = [
    "TOPIC_STATUS_LIST", "TOPIC_STATUS_TRANSITIONS",
    "TITLE_MAX_LEN", "SUMMARY_MAX_LEN",
    "DESCRIPTION_MIN_WORDS", "DESCRIPTION_MAX_WORDS",
]

#assetService 必须具备的业务函数与常量(S21)
ASSET_SERVICE_FUNC_LIST = [
    "addAsset", "modifyAsset", "deleteAsset", "queryAsset",
    "addTopicAsset", "modifyTopicAsset", "deleteTopicAsset", "queryTopicAsset",
    "validateAssetFields", "validateTopicAssetFields",
    "computeContentHash", "computeContentHashFromBytes",
    "processImageForUpload", "stripExif", "fitImageToMaxSize",
    "uploadAssetFile", "buildThumbnailForUpload",
    "reorderTopicAssets", "demoteOtherCoverAssets",
]
ASSET_SERVICE_CONST_LIST = [
    "ASSET_TABLE", "TOPIC_ASSET_TABLE",
    "USAGE_TYPE_LIST", "PROCESS_STATUS_LIST",
    "SORT_ORDER_DEFAULT", "SORT_ORDER_MIN", "SORT_ORDER_MAX",
    "EXIF_STRIPPED_NO", "EXIF_STRIPPED_YES",
]

#SP2c 引擎层(C4 版式引擎) 常量: layoutType <-> 模板目录一一对应
ENGINE_DIR = os.path.join(_SRC_DIR, "engine")
TEMPLATE_DIR = os.path.join(ENGINE_DIR, "templates")
ENGINE_LAYOUT_TYPE_TEMPLATE_MAP = {
    "stack": "stack_v1",
    "carousel": "carousel_v1",
    "longimage": "longimage_v1",
    "swipe": "swipe_v1",
}
ENGINE_TEMPLATE_FILE_LIST = [
    "partials/base.html",
    "stack_v1/index.html",
    "carousel_v1/index.html",
    "longimage_v1/index.html",
    "swipe_v1/index.html",
    "preview/wechat_mp.html",
    "preview/xiaohongshu.html",
]
#模板禁止的平台专属硬编码(平台差异必须由 ch_platform / specJson 数据驱动)
TEMPLATE_FORBIDDEN_TOKEN_LIST = [
    "mmbiz.qpic.cn", "mp.weixin.qq.com", "weixin.qq.com",
    "xiaohongshu.com", "xhslink",
]

#渲染域端点(SP2c 由 renderApi 接管)
RENDER_CMD_LIST = ["topicrender"]

#SP3a 平台适配层(C5) 常量
PLATFORM_ADAPTER_DIR = os.path.join(_SRC_DIR, "processor", "platformAdapter")
PLATFORM_ADAPTER_FILE_LIST = ["__init__.py", "base.py", "wechatMp.py", "generic.py", "xiaohongshu.py"]
ADAPTER_CONTRACT_METHOD_LIST = ["render", "validate", "package", "deliver", "checkHealth"]
#platformCode -> 适配器类名(新增平台只加一条 ch_platform 记录 + 一个适配器)
ADAPTER_REGISTRY_EXPECT = {"wechat_mp": "WechatMpAdapter", "generic": "GenericAdapter",
                           "xiaohongshu": "XiaohongshuAdapter"}
#平台显示域白名单必须落在适配器内(模板不得出现平台专属域名; plan.md §4 模板约定)
WECHAT_DISPLAY_HOST = "mmbiz.qpic.cn"
#零网络红线(SP3a/SP3b): 不调任何平台接口/不做转存/不做投递
NETWORK_FORBIDDEN_TOKEN_LIST = ["requests.", "urllib", "http.client", "urlopen", "socket."]

#SP3b 小红书产物渲染(C5) 常量
XHS_ADAPTER_CLASS = "XiaohongshuAdapter"
#小红书适配器必须实现的方法(★ deliver 不在此列: 由基类统一显式未实现, 投递归 SP4)
XHS_CONTRACT_METHOD_LIST = ["render", "validate", "package", "checkHealth"]
#小红书适配器必须齐备的渲染管线函数
HTML_TO_IMAGE_FUNC_LIST = [
    "getBrowser", "closeBrowser", "isBrowserAvailable", "waitForFonts", "inlineLocalImages",
    "renderHtmlToImage", "renderCardsFromHtml", "renderLongImageSlices",
    "uploadArtifact", "computeFileSha256", "fileSizeBytes",
]
#平台红线: 小红书适配器内不得出现任何自动发布/投递代码痕迹
XHS_FORBIDDEN_PUBLISH_TOKEN_LIST = ["freepublish", "draft/add", "draft_add", "api_publish",
                                    "publishsubmit", "access_token", "open.weixin"]
#小红书不接收 HTML 且轮播交互属公众号自实现 -> carousel 必须显式不可用(C7)
XHS_UNAVAILABLE_LAYOUT_TOKEN = "carousel"
#swipe 强制校验(主计划 2.6.3)必须体现的错误码落点
XHS_SWIPE_GUARD_TOKEN_LIST = ["uniformRatio", "ERR_IMAGE_SPEC", "ERR_FIELD_OUT_OF_RANGE"]

#SP3c 合规服务(C8)与渲染任务化/产物台账 常量
COMPLIANCE_SERVICE_FUNC_LIST = [
    "publishCheck", "evaluateCompliance", "summarizeIssues",
    "checkPlatformSpecIssues", "checkSwipeIssues", "checkOverlongImageIssues",
    "detectSensitiveWords", "checkSensitiveWordIssues", "checkAiLabelIssues", "checkArtifactIssues",
    "checkPublishRateLimit", "checkRateLimitIssues",
]
COMPLIANCE_SERVICE_CONST_LIST = [
    "DEFAULT_SENSITIVE_WORD_LIST", "AI_LABEL_MARKER_LIST",
    "RATE_LIMIT_MAX_PUBLISH", "RATE_LIMIT_WINDOW_SECONDS",
    "ISSUE_LEVEL_ERROR", "ISSUE_LEVEL_WARN",
    "SOURCE_PLATFORM_SPEC", "SOURCE_SWIPE_SPEC", "SOURCE_SENSITIVE_WORD",
    "SOURCE_AI_LABEL", "SOURCE_RATE_LIMIT",
]
#渲染任务状态机(主计划 P2-7)
JOB_STATUS_EXPECT_LIST = ["PENDING", "RUNNING", "DONE", "FAILED"]
#产物台账状态(主计划 P2-6; 过期清理归 SP4)
ARTIFACT_STATUS_EXPECT_LIST = ["READY", "EXPIRED"]
#renderWorker 必须保持「单实例 + 串行」: 不得出现并发截图/并发池痕迹
WORKER_FORBIDDEN_CONCURRENCY_TOKEN_LIST = [
    "ThreadPool", "concurrent.futures", "multiprocessing", "threading.Thread",
]

#SP4a C6 投递链路 常量
CREDENTIAL_CIPHER_FUNC_LIST = [
    "encrypt", "decrypt", "getMasterKey", "isKeyConfigured", "decodeKeyMaterial",
    "maskSecret", "sha256Hex",
]
#★ 密钥来源必须是环境变量(不入库/不入代码库)
CREDENTIAL_KEY_ENV_TOKEN = "CH_CREDENTIAL_KEY"
PUBLISH_SERVICE_FUNC_LIST = [
    "publishPush", "revokePublish", "buildIdempotencyKey", "parseIdempotencyKey", "isValidIdempotencyKey",
    "buildConfirmToken", "checkConfirmParams", "resolveArtifactRecord", "loadAccountRecord",
    "decryptAccountCredential", "saveAccountCredential", "getAccessToken", "clearAccessTokenCache",
    "checkAutoPublishGate", "queryPublishRecord", "savePublishRecord", "buildPublishSaveSet",
    "checkRevokeWindow",
]
PUBLISH_SERVICE_CONST_LIST = [
    "NON_DELIVERABLE_PLATFORM_LIST", "DELIVERABLE_PLATFORM_LIST", "SUPPORTED_DELIVER_MODE_LIST",
    "REVOKE_WINDOW_SECONDS", "CONFIRM_FLAG_KEY", "CONFIRM_TOKEN_KEY",
    "AUTO_PUBLISH_KEY", "AUTO_PUBLISH_CONFIRM_KEY", "ACTION_PUSH", "ACTION_REVOKE",
    "ERR_IDEMPOTENT", "ERR_CONFIRM_REQUIRED", "ERR_REVOKE_WINDOW", "ERR_AUTO_PUBLISH_DISABLED",
]
AUDIT_SERVICE_FUNC_LIST = [
    "writeAudit", "buildAuditSaveSet", "sanitizePayload", "buildPayloadDigest", "queryAuditLog",
]
AUDIT_SERVICE_CONST_LIST = [
    "ACTION_PUBLISH_PUSH", "ACTION_PUBLISH_REVOKE", "RESULT_OK", "RESULT_FAIL",
    "SENSITIVE_FIELD_TOKEN_LIST", "TARGET_TYPE_PUBLISH_RECORD",
]
#ch_audit_log 必填字段(主计划 P3-5)
AUDIT_FIELD_LIST = [
    "actor", "source", "action", "targetType", "targetID", "payloadDigest", "result", "errMsg",
    "costMs", "ipAddr",
]
#★ 平台红线: 小红书投递/发布代码路径必须**不存在**(全仓静态扫描的硬线索)
XHS_PUBLISH_FORBIDDEN_TOKEN_LIST = [
    "api.xiaohongshu", "xhslink", "xiaohongshu.com", "creator.xiaohongshu", "xhssign",
]
#投递链路需扫描的平台红线文件
XHS_PUBLISH_SCAN_FILE_LIST = [
    "processor/publishService.py", "processor/auditService.py",
    "processor/platformAdapter/wechatMp.py", "processor/platformAdapter/base.py",
    "main/subfunc/publishApi.py",
]
#投递段错误码必须在 contenthub 消息表中真实存在
PUBLISH_ERR_CODE_LIST = ["F0", "F1", "F3", "F4", "F5", "F6"]

#生成区应包含的数据层函数前缀
DATA_LAYER_FUNC_PREFIX_LIST = [
    "tablename_convertor_",
    "decode_tablename_",
    "create_",
    "drop_",
    "delete_",
    "insert_",
    "update_",
    "query_",
]

#定义文件尾部固定七字段(顺序不可变)
TAIL_FIELD_LIST = ["label", "memo", "regID", "regYMDHMS", "modifyID", "modifyYMDHMS", "delFlag"]

FIRST_FIELD_LINE = "recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID'"

#允许的字段类型(与 database/ch_*.txt 实际使用一致)
ALLOWED_TYPE_PATTERN = re.compile(r"^(BIGINT|INT|SMALLINT|TINYINT|CHAR\(\d+\)|VARCHAR\(\d+\)|MEDIUMTEXT|TEXT|JSON)$")

COMPILE_TARGET_LIST = [
    "common/mysqlCommon.py",
    "common/chCommon.py",
    "common/mysqlHandle.py",
    "common/globalDefinition.py",
    "config/mysqlSettings.py",
    "config/wechatSettings.py",
    "tools/initTables.py",
    "tools/initSeed.py",
    "tools/test_storage.py",
    "tools/mergeMysqlCommon.py",
    #SP1.5 新增/改造
    "common/errMsgCommon.py",
    "common/funcCommon.py",
    "common/accountClient.py",
    "common/queryBufferCommon.py",
    "main/chAPI.py",
    "main/chAPIPost.py",
    "main/subfunc/__init__.py",
    "main/subfunc/context.py",
    "main/subfunc/apiCommon.py",
    "main/subfunc/accountSvcClient.py",
    "main/subfunc/accountApi.py",
    "main/subfunc/crudApi.py",
    "main/subfunc/topicApi.py",
    "main/subfunc/assetApi.py",
    "main/subfunc/renderApi.py",
    "main/subfunc/publishApi.py",
    "main/subfunc/complianceApi.py",
    "main/subfunc/mcpApi.py",
    "tools/mergeCrudApi.py",
    #SP2a(Phase 1 · C2 主题管理)
    "processor/__init__.py",
    "processor/topicService.py",
    #SP2b(Phase 1 · C3 素材图库)
    "processor/assetService.py",
    #SP2c(Phase 1 · C4 版式引擎)
    "processor/renderService.py",
    "engine/__init__.py",
    "engine/layoutEngine.py",
    "engine/imageProc.py",
    #SP3a(Phase 2 · C5 平台适配层)
    "processor/platformAdapter/__init__.py",
    "processor/platformAdapter/base.py",
    "processor/platformAdapter/wechatMp.py",
    "processor/platformAdapter/generic.py",
    "engine/inlineStyle.py",
    #SP3b(Phase 2 · C5 小红书产物渲染)
    "processor/platformAdapter/xiaohongshu.py",
    "engine/htmlToImage.py",
    #SP3c(Phase 2 · C8 合规校验 + 产物台账 + 渲染任务化)
    "processor/complianceService.py",
    "schedule/__init__.py",
    "schedule/renderWorker.py",
    #SP4a(Phase 3 · C6 投递链路)
    "common/credentialCipher.py",
    "processor/auditService.py",
    "processor/publishService.py",
    #SP4b(Phase 3 · 素材包 ZIP + MCP 接入 + 凭据巡检)
    "processor/artifactService.py",
    "schedule/credentialCheck.py",
]

_resultList = []


def record(name, ok, detail = ""):
    _resultList.append((name, ok, detail))
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {name}{('  -> ' + detail) if detail else ''}")


def readText(filePath):
    """容错读取: 生成产物在 Windows 上可能是 GBK"""
    with open(filePath, "rb") as hFile:
        raw = hFile.read()
    for encoding in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors = "replace")


def stripComments(text):
    """去掉整行注释与行内注释(smoke/static 扫描禁词时用)。
       说明: 采用「# 到行尾」的粗略剥离 —— 引号内的 # 亦会被截断, 但仅用于**禁词扫描**,
             不会影响被扫描代码之外的任何断言(S27 的禁词扫描面向「不得出现的投递/协议解析痕迹」,
             注释中说明「不得出现 xxx」不应被误判为出现)。"""
    lines = []
    for line in text.split("\n"):
        if line.lstrip().startswith("#"):
            continue
        pos = line.find("#")
        if pos >= 0:
            line = line[:pos]
        lines.append(line)
    return "\n".join(lines)


def collectTopLevelNames(filePath):
    """AST 提取模块级函数名/类名/变量名(不执行模块, 无第三方依赖)
       说明: 条件赋值(如 mysqlSettings.py 的 if _SKIP_CONNECT: mysqlDB = None)也按模块级符号计入,
             因此会向下递归一层 if/else 分支。"""
    result = set()
    tree = ast.parse(readText(filePath))
    _collectFromBody(tree.body, result, 0)
    return result


def _collectFromBody(body, result, depth):
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            result.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    result.add(target.id)
        elif isinstance(node, ast.If) and depth == 0:
            _collectFromBody(node.body, result, depth + 1)
            _collectFromBody(node.orelse, result, depth + 1)


def checkCompile():
    """S1 语法编译"""
    failList = []
    for relPath in COMPILE_TARGET_LIST:
        absPath = os.path.join(_SRC_DIR, relPath)
        if not os.path.isfile(absPath):
            failList.append(f"{relPath}(missing)")
            continue
        try:
            with tempfile.TemporaryDirectory() as tmpDir:
                py_compile.compile(absPath, cfile = os.path.join(tmpDir, "x.pyc"), doraise = True)
        except Exception as e:
            failList.append(f"{relPath}({e})")
    record("S1 py_compile", not failList, ",".join(failList))


def checkTableDefFiles():
    """S2 表定义文件齐备 + 写法红线"""
    missingList = []
    formatErrList = []
    for tableName in TABLE_NAME_LIST:
        filePath = os.path.join(_DATABASE_DIR, f"{tableName}.txt")
        if not os.path.isfile(filePath):
            missingList.append(tableName)
            continue

        text = readText(filePath)
        if "\t" in text:
            formatErrList.append(f"{tableName}:含制表符")
        if "%" in text:
            formatErrList.append(f"{tableName}:含百分号")
        if "#" in text:
            formatErrList.append(f"{tableName}:含井号")

        lines = [ln for ln in text.split("\n") if ln.strip() != ""]
        if not lines or lines[0].strip() != FIRST_FIELD_LINE:
            formatErrList.append(f"{tableName}:首字段不是 {FIRST_FIELD_LINE}")

        if len(lines) < 8:
            formatErrList.append(f"{tableName}:字段行数不足")
            continue

        #尾部七字段顺序
        if [ln.split(" ")[0] for ln in lines[-7:]] != TAIL_FIELD_LIST:
            formatErrList.append(f"{tableName}:尾部七字段顺序不符")

        for idx, line in enumerate(lines):
            if re.search(r"\S  +\S", line):
                formatErrList.append(f"{tableName}#{idx + 1}:出现连续空格")
            parts = line.split(" ")
            if len(parts) < 3:
                formatErrList.append(f"{tableName}#{idx + 1}:字段行不足三段")
                continue
            if not ALLOWED_TYPE_PATTERN.match(parts[1]):
                formatErrList.append(f"{tableName}#{idx + 1}:类型不被支持 {parts[1]}")

    record("S2 定义文件齐备", not missingList, ",".join(missingList))
    record("S2 定义文件格式红线", not formatErrList, "; ".join(formatErrList[:6]))


def checkGenerateProducts():
    """S3/S4 产物齐备 + 函数名合法 + REST 处理器命名对齐"""
    missingList = []
    nameErrList = []
    for tableName in TABLE_NAME_LIST:
        pyPath = os.path.join(_AUTO_GEN_DIR, f"auto_gen_code_{tableName}.py")
        csvPath = os.path.join(_AUTO_GEN_DIR, f"word_table_{tableName}.csv")
        if not os.path.isfile(pyPath):
            missingList.append(os.path.basename(pyPath))
            continue
        if not os.path.isfile(csvPath):
            missingList.append(os.path.basename(csvPath))

        text = readText(pyPath)
        if "func['" in text or "func[\"" in text:
            nameErrList.append(f"{tableName}:非法函数名形态")
        for prefix in DATA_LAYER_FUNC_PREFIX_LIST:
            if f"def {prefix}{tableName}(" not in text:
                nameErrList.append(f"{tableName}:缺少 {prefix}{tableName}()")

    record("S3 产物齐备(12 py + 12 csv)", not missingList, ",".join(missingList))
    record("S4 产物函数名合法/齐备", not nameErrList, "; ".join(nameErrList[:6]))


def checkCrudTitleAlignment():
    """S4b 4 个 REST 处理器命名与 _CRUD_TITLES 对齐(供 SP1.5 装配 crudApi 用)"""
    errList = []
    for title in CRUD_TITLE_LIST:
        #_CRUD_TITLES 是去下划线形式, 这里按表名反推核对
        matched = [t for t in TABLE_NAME_LIST if t.replace("ch_", "").replace("_", "") == title]
        if not matched:
            errList.append(f"{title}:无对应表")
            continue
        tableName = matched[0]
        pyPath = os.path.join(_AUTO_GEN_DIR, f"auto_gen_code_{tableName}.py")
        if not os.path.isfile(pyPath):
            errList.append(f"{tableName}:产物缺失")
            continue
        text = readText(pyPath)
        funcTitle = title[0].upper() + title[1:]
        for op in ("Add", "Del", "Modify", "Qry"):
            if f"def func{funcTitle}{op}(" not in text:
                errList.append(f"func{funcTitle}{op} 缺失")
    record("S4b REST 处理器命名对齐", not errList, "; ".join(errList[:6]))


def checkMysqlCommon():
    """S5/S6 mysqlCommon 生成区与手写段齐备"""
    filePath = os.path.join(_SRC_DIR, "common", "mysqlCommon.py")
    if not os.path.isfile(filePath):
        record("S5 mysqlCommon 生成区", False, "common/mysqlCommon.py 缺失")
        record("S6 mysqlCommon 手写段", False, "common/mysqlCommon.py 缺失")
        return

    text = readText(filePath)

    genErrList = []
    if "#===== auto-generated sections begin" not in text or "#===== auto-generated sections end" not in text:
        genErrList.append("缺少自动生成区标记")
    for tableName in TABLE_NAME_LIST:
        for prefix in DATA_LAYER_FUNC_PREFIX_LIST:
            #前缀均以 "_" 结尾, 直接拼接即为实际函数名(如 create_ + ch_topic -> create_ch_topic)
            name = f"{prefix}{tableName}"
            if f"def {name}(" not in text:
                genErrList.append(f"缺少 {name}()")
    if "def func" in text:
        genErrList.append("生成区混入 REST 处理器")
    record("S5 mysqlCommon 生成区(12表×8函数)", not genErrList, "; ".join(genErrList[:6]))

    handErrList = []
    for name in ["dataFormatConvert", "normalizeJsonValue4DB", "chkTableExist", "dropTableGeneral",
                 "insertTableGeneral", "updateTableGeneral", "queryTableGeneral", "toIntSafe",
                 "MYSQL_JSON_COLUMN_NAME_LIST", "CH_QUERY_SHORT_COLUMNS"]:
        if name not in text:
            handErrList.append(f"{name} 缺失")
    if f"def query_ch_audit_log(" in text:
        #大表查询必须显式收紧 LIMIT
        if "_DEF_CH_AUDIT_LOG_QUERY_LIMIT_NUM" not in text:
            handErrList.append("审计日志未收紧 LIMIT")
    else:
        handErrList.append("query_ch_audit_log 缺失")
    for column in ["requestJson", "responseJson"]:
        if column not in text:
            handErrList.append(f"JSON 列 {column} 未登记")
    record("S6 mysqlCommon 手写段", not handErrList, "; ".join(handErrList[:6]))


def checkGlobalDefinition():
    """S7 3 个 MCP 日志常量已补齐"""
    filePath = os.path.join(_SRC_DIR, "common", "globalDefinition.py")
    names = collectTopLevelNames(filePath)
    needList = ["_DEF_LOG_CH_MCP_TITLE", "_DEF_LOG_CH_MCP_NAME", "_DEF_LOG_CH_TEST_NAME"]
    missList = [n for n in needList if n not in names]
    record("S7 MCP 日志常量", not missList, ",".join(missList))


def checkChCommon():
    """S8 chCommon 公共件齐备"""
    filePath = os.path.join(_SRC_DIR, "common", "chCommon.py")
    if not os.path.isfile(filePath):
        record("S8 chCommon 公共件", False, "common/chCommon.py 缺失")
        return
    names = collectTopLevelNames(filePath)
    needList = ["upsertByUniqueKey", "fillFileUrls", "FILE_FIELD_URL_MAP"]
    missList = [n for n in needList if n not in names]
    record("S8 chCommon 公共件", not missList, ",".join(missList))


def checkConfigGap():
    """S9 config 缺口已补"""
    errList = []
    mysqlSettingsPath = os.path.join(_SRC_DIR, "config", "mysqlSettings.py")
    if not os.path.isfile(mysqlSettingsPath):
        errList.append("mysqlSettings.py 缺失")
    else:
        names = collectTopLevelNames(mysqlSettingsPath)
        for n in ["MYSQL_WRITE_DB", "MYSQL_READ_DB", "mysqlDB", "_SKIP_CONNECT", "mysqlReconnect"]:
            if n not in names:
                errList.append(f"mysqlSettings.{n} 缺失")

    wechatSettingsPath = os.path.join(_SRC_DIR, "config", "wechatSettings.py")
    if not os.path.isfile(wechatSettingsPath):
        errList.append("wechatSettings.py 缺失")
    else:
        names = collectTopLevelNames(wechatSettingsPath)
        for n in ["WECHAT_API_BASE", "WECHAT_API_PATH", "WECHAT_APP_ID", "WECHAT_APP_SECRET"]:
            if n not in names:
                errList.append(f"wechatSettings.{n} 缺失")

    record("S9 config 缺口补齐", not errList, "; ".join(errList))


def checkTools():
    """S10 tools 脚本齐备且有 main()"""
    errList = []
    for relPath in ["tools/initTables.py", "tools/initSeed.py", "tools/test_storage.py",
                    "tools/mergeMysqlCommon.py", "tools/genTableCode.ps1"]:
        absPath = os.path.join(_SRC_DIR, relPath)
        if not os.path.isfile(absPath):
            errList.append(f"{relPath} 缺失")
            continue
        if relPath.endswith(".py"):
            names = collectTopLevelNames(absPath)
            if "main" not in names:
                errList.append(f"{relPath} 无 main()")
    record("S10 tools 脚本", not errList, "; ".join(errList))


def checkCrossModuleReferences():
    """S11 跨模块符号闭环: tools/ 与产物中对 comMysql./comCh./comFS. 的引用必须都有定义
       (重跑生成器或改表后最容易出现「调用了不存在的函数」这类隐蔽缺陷)"""
    commonFuncNames = collectTopLevelNames(os.path.join(_SRC_DIR, "common", "mysqlCommon.py"))
    chCommonNames = collectTopLevelNames(os.path.join(_SRC_DIR, "common", "chCommon.py"))
    fsNames = collectTopLevelNames(os.path.join(_SRC_DIR, "common", "fileStorageCommon.py"))

    moduleMap = {
        "comMysql": commonFuncNames,
        "comCh": chCommonNames,
        "comFS": fsNames,
    }

    #扫描范围: tools 下的脚本 + 12 份产物(产物中的接口处理段将来由 SP1.5 装配, 先一并核查)
    #         + processor 业务层(SP2a/SP2b: 防止手写服务层调用了不存在的数据层/公共件函数)
    scanPathList = []
    for relPath in ["tools/initTables.py", "tools/initSeed.py", "tools/test_storage.py",
                    "processor/topicService.py", "processor/assetService.py",
                    "processor/renderService.py",
                    "engine/layoutEngine.py", "engine/imageProc.py",
                    "engine/inlineStyle.py", "engine/htmlToImage.py",
                    "processor/platformAdapter/base.py", "processor/platformAdapter/wechatMp.py",
                    "processor/platformAdapter/generic.py", "processor/platformAdapter/xiaohongshu.py",
                    "processor/complianceService.py", "schedule/renderWorker.py"]:
        scanPathList.append(os.path.join(_SRC_DIR, relPath))
    for fileName in sorted(os.listdir(_AUTO_GEN_DIR)):
        if fileName.startswith("auto_gen_code_") and fileName.endswith(".py"):
            scanPathList.append(os.path.join(_AUTO_GEN_DIR, fileName))

    errList = []
    pattern = re.compile(r"\b(comMysql|comCh|comFS)\.([A-Za-z_][A-Za-z0-9_]*)")
    for filePath in scanPathList:
        if not os.path.isfile(filePath):
            errList.append(f"{os.path.basename(filePath)} 缺失")
            continue
        text = readText(filePath)
        for moduleName, symbol in set(pattern.findall(text)):
            known = moduleMap.get(moduleName, set())
            if symbol not in known:
                errList.append(f"{os.path.basename(filePath)}: {moduleName}.{symbol} 未定义")

    record("S11 跨模块符号闭环", not errList, "; ".join(sorted(set(errList))[:8]))


def checkDelFlagConvention():
    """S12 删除标记取值约定: delFlag 一律用 "0"/"1", 禁止误用 comGD._CONST_NO("N")/_CONST_YES("Y")
       (表定义与 query_ch_* 的 delFlag 过滤均按 "0" 未删除, 误用会导致数据"写进去查不到")"""
    errList = []

    for relPath in ["tools/initSeed.py", "common/chCommon.py", "common/mysqlCommon.py",
                    "tools/initTables.py", "processor/topicService.py",
                    "processor/assetService.py"]:
        filePath = os.path.join(_SRC_DIR, relPath)
        if not os.path.isfile(filePath):
            continue
        for idx, line in enumerate(readText(filePath).split("\n")):
            stripped = line.strip()
            if stripped.startswith("#"):
                #纯注释行跳过(文件中存在"不要用 comGD._CONST_NO 当 delFlag"这类说明性注释)
                continue
            if "delFlag" in line and ("_CONST_NO" in line or "_CONST_YES" in line):
                errList.append(f"{relPath}#{idx + 1}:{stripped[:50]}")

    seedText = readText(os.path.join(_SRC_DIR, "tools", "initSeed.py"))
    if '"delFlag": "0"' not in seedText:
        errList.append("initSeed.py 未显式设置 delFlag=\"0\"")

    record("S12 delFlag 取值约定", not errList, "; ".join(errList[:6]))


def _readLines(filePath):
    return readText(filePath).split("\n")


def _getCmdMapKeys(filePath):
    """AST 取模块级 CMD_MAP 的字符串键与函数名值(不执行模块)"""
    keys = []
    values = []
    tree = ast.parse(readText(filePath))
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id == "CMD_MAP" and isinstance(node.value, ast.Dict):
            for keyNode, valNode in zip(node.value.keys, node.value.values):
                if isinstance(keyNode, ast.Constant):
                    keys.append(keyNode.value)
                if isinstance(valNode, ast.Name):
                    values.append(valNode.id)
    return keys, values


def _getTopLevelDefNames(filePath):
    tree = ast.parse(readText(filePath))
    return [node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def checkWebEntryStructure():
    """S13 接入层结构与行数上限(方案 A1/A2 + 决策: crudApi 作为生成件豁免上限)"""
    errList = []

    chAPIPostPath = os.path.join(_MAIN_DIR, "chAPIPost.py")
    chAPIPath = os.path.join(_MAIN_DIR, "chAPI.py")
    for filePath in (chAPIPostPath, chAPIPath):
        if not os.path.isfile(filePath):
            errList.append(f"{os.path.basename(filePath)} 缺失")

    if os.path.isfile(chAPIPostPath):
        lineNum = len(_readLines(chAPIPostPath))
        if lineNum > CH_APIPOST_MAX_LINES:
            errList.append(f"chAPIPost.py {lineNum} 行 > {CH_APIPOST_MAX_LINES}")

    for fileName in SUBFUNC_FILE_LIST:
        filePath = os.path.join(_SUBFUNC_DIR, fileName)
        if not os.path.isfile(filePath):
            errList.append(f"subfunc/{fileName} 缺失")
            continue
        lineNum = len(_readLines(filePath))
        if fileName not in SUBFUNC_LINE_EXEMPT_LIST and lineNum > SUBFUNC_MAX_LINES:
            errList.append(f"subfunc/{fileName} {lineNum} 行 > {SUBFUNC_MAX_LINES}")

    record("S13 接入层结构与行数上限", not errList, "; ".join(errList[:6]))


def checkSubfuncNoCircularImport():
    """S14 subfunc/ 不得反向 import chAPIPost / chAPI(防循环依赖, 方案 9.1 A4)"""
    errList = []
    pattern = re.compile(r"^\s*(import|from)\s+(chAPIPost|chAPI)\b")

    for fileName in SUBFUNC_FILE_LIST:
        filePath = os.path.join(_SUBFUNC_DIR, fileName)
        if not os.path.isfile(filePath):
            continue
        for idx, line in enumerate(_readLines(filePath)):
            if line.strip().startswith("#"):
                continue
            if pattern.search(line):
                errList.append(f"subfunc/{fileName}#{idx + 1}:{line.strip()[:40]}")

    record("S14 subfunc 无反向依赖", not errList, "; ".join(errList[:6]))


def checkCrudApiCoverage():
    """S15 crudApi 覆盖 CRUD_API_CMD_TOTAL 个 CRUD CMD(48 扣除业务域接管的 topic/topicversion/asset/topicasset),
       且注册表指向已定义处理器"""
    filePath = os.path.join(_SUBFUNC_DIR, "crudApi.py")
    if not os.path.isfile(filePath):
        record(f"S15 crudApi {CRUD_API_CMD_TOTAL} CMD 覆盖", False, "subfunc/crudApi.py 缺失")
        return

    cmdKeys, funcNames = _getCmdMapKeys(filePath)
    definedFuncs = set(_getTopLevelDefNames(filePath))

    expectSet = set()
    for title in CRUD_API_TITLE_LIST:
        for op in ("add", "del", "modify", "qry"):
            expectSet.add(f"{title}{op}")

    errList = []
    missingList = sorted(expectSet - set(cmdKeys))
    extraList = sorted(set(cmdKeys) - expectSet)
    if missingList:
        errList.append(f"缺少 {len(missingList)} 条: {missingList[:5]}")
    if extraList:
        errList.append(f"多出 {len(extraList)} 条: {extraList[:5]}")
    if len(cmdKeys) != CRUD_API_CMD_TOTAL:
        errList.append(f"CMDMap 条数 {len(cmdKeys)} != {CRUD_API_CMD_TOTAL}")

    undefinedList = sorted(set(funcNames) - definedFuncs)
    if undefinedList:
        errList.append(f"注册表指向未定义函数: {undefinedList[:5]}")

    record(f"S15 crudApi {CRUD_API_CMD_TOTAL} CMD 覆盖", not errList, "; ".join(errList[:6]))


def checkAggregatorValidations():
    """S16 聚合器三道校验可触发(方案 5.4 / 9.2 B8):
       AST 抽取 mergeCmdMaps 源码 + exec 到隔离命名空间, 传伪造入参断言
       V1 抛 RuntimeError / V2 抛 TypeError / V3 抛 RuntimeError, 且正常路径可合并。"""
    filePath = os.path.join(_SUBFUNC_DIR, "__init__.py")
    if not os.path.isfile(filePath):
        record("S16 聚合器 V1/V2/V3 可触发", False, "subfunc/__init__.py 缺失")
        return

    text = readText(filePath)
    tree = ast.parse(text)

    targetNode = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "mergeCmdMaps":
            targetNode = node
            break

    if targetNode is None:
        record("S16 聚合器 V1/V2/V3 可触发", False, "未找到 mergeCmdMaps()")
        return

    namespace = {}
    try:
        exec(ast.get_source_segment(text, targetNode), namespace)
    except Exception as e:
        record("S16 聚合器 V1/V2/V3 可触发", False,
               f"mergeCmdMaps 无法独立执行(存在模块级依赖): {e}")
        return

    mergeFunc = namespace["mergeCmdMaps"]
    errList = []

    def _stubHandler(CMD, dataSet, sessionIDSet):
        return {}

    #V1 同一 CMD 定义于两个域(处理函数均为可调用, 确保命中的是 V1 而非 V2)
    try:
        mergeFunc({"a": {"x": _stubHandler}, "b": {"x": _stubHandler}})
        errList.append("V1 未触发")
    except RuntimeError:
        pass
    except Exception as e:
        errList.append(f"V1 异常类型不符: {type(e).__name__}")

    #V2 处理函数不可调用
    try:
        mergeFunc({"a": {"x": 1}})
        errList.append("V2 未触发")
    except TypeError:
        pass
    except Exception as e:
        errList.append(f"V2 异常类型不符: {type(e).__name__}")

    #V3 配置声明的命令缺项(dict 与 set 两种配置形态都要能比对)
    try:
        mergeFunc({"a": {"x": _stubHandler}}, {"admin": ["x", "y"]}, {"z"})
        errList.append("V3 未触发")
    except RuntimeError:
        pass
    except Exception as e:
        errList.append(f"V3 异常类型不符: {type(e).__name__}")

    #正常路径: 配置与注册表一致时返回合并结果
    try:
        merged = mergeFunc({"a": {"x": _stubHandler}, "b": {"y": _stubHandler}},
                           {"admin": ["x", "y"]}, {"x"})
        if sorted(merged.keys()) != ["x", "y"]:
            errList.append(f"正常路径结果不符: {sorted(merged.keys())}")
    except Exception as e:
        errList.append(f"正常路径异常: {e}")

    record("S16 聚合器 V1/V2/V3 可触发", not errList, "; ".join(errList[:6]))


def checkErrMsgModule():
    """S17 错误消息模块(决策 12.4/12.6):
       - common/errMsgCommon.py 零依赖可用, 含 contenthub 消息键与 applicationMsgKey 别名;
       - 生成件硬编码的 applicationMsgKey 必须解析到 contenthub(不再静默回落 default);
       - common/funcCommon.py 只做 re-export, 不再本地定义 CONST_ERROR_wordList(CI-C4)。"""
    errList = []

    errMsgPath = os.path.join(_SRC_DIR, "common", "errMsgCommon.py")
    funcCommonPath = os.path.join(_SRC_DIR, "common", "funcCommon.py")

    if not os.path.isfile(errMsgPath):
        errList.append("common/errMsgCommon.py 缺失")
    else:
        msgText = readText(errMsgPath)
        namespace = {}
        try:
            exec(compile(msgText, errMsgPath, "exec"), namespace)
        except Exception as e:
            errList.append(f"errMsgCommon 独立执行失败(疑似有依赖): {e}")
        else:
            rtnMSG = namespace.get("rtnMSG")
            wordList = namespace.get("CONST_ERROR_wordList", {})
            if "contenthub" not in wordList:
                errList.append("缺少 contenthub 消息键")
            if not callable(rtnMSG):
                errList.append("rtnMSG 不可调用")
            else:
                rtnSet = rtnMSG("CG", "", "CN", "applicationMsgKey")
                if rtnSet.get("msgKey") != "contenthub":
                    errList.append(f"applicationMsgKey 未归一(contenthub), 实为 {rtnSet.get('msgKey')}")
                if "记录添加失败" != rtnSet.get("MSG", {}).get("content"):
                    errList.append(f"contenthub 未覆盖 CG 码: {rtnSet.get('MSG', {}).get('content')}")

    if not os.path.isfile(funcCommonPath):
        errList.append("common/funcCommon.py 缺失")
    else:
        tree = ast.parse(readText(funcCommonPath))
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                    and node.targets[0].id == "CONST_ERROR_wordList":
                errList.append("funcCommon.py 仍本地定义 CONST_ERROR_wordList(CI-C4)")
        if not any(isinstance(node, ast.ImportFrom) and node.module == "common.errMsgCommon"
                   for node in tree.body):
            errList.append("funcCommon.py 缺少 common.errMsgCommon re-export")

    record("S17 错误消息模块与 contenthub 键", not errList, "; ".join(errList[:6]))


def checkAggregateCoverage():
    """S18 注册表静态覆盖 + chCommon 真实引用(CI-C5):
       - 各域 CMD_MAP 覆盖账号域 19 个 CMD 与 5 个业务端点, 且各域之间无重名(V1 静态等价);
       - chAPIPost.py 必须真实引用 common/chCommon.py(防「建而不用」)。"""
    errList = []

    chAPIPostPath = os.path.join(_MAIN_DIR, "chAPIPost.py")
    if not os.path.isfile(chAPIPostPath):
        errList.append("main/chAPIPost.py 缺失")
    else:
        mainText = readText(chAPIPostPath)
        if "chCommon" not in mainText or "comCh.fillFileUrls" not in mainText:
            errList.append("chAPIPost.py 未真实引用 chCommon(CI-C5)")

    initPath = os.path.join(_SUBFUNC_DIR, "__init__.py")
    if os.path.isfile(initPath):
        initText = readText(initPath)
        if "mergeCmdMaps(MODULE_MAPS" not in initText:
            errList.append("__init__.py 未在导入期调用 mergeCmdMaps")
        if "settings.ROLE_CMD_LIST" not in initText or "settings.NO_SESSIONID_CMD_LIST" not in initText:
            errList.append("__init__.py 未把配置传入 V3 完整性校验")
    else:
        errList.append("subfunc/__init__.py 缺失")

    accountKeys, _ = _getCmdMapKeys(os.path.join(_SUBFUNC_DIR, "accountApi.py"))
    missingList = sorted(set(ACCOUNT_CMD_LIST) - set(accountKeys))
    if missingList:
        errList.append(f"accountApi 缺少账号域 CMD: {missingList[:6]}")

    domainCmdList = [("account", ACCOUNT_CMD_LIST)]
    for domain, cmdList in BIZ_CMD_DOMAIN_MAP.items():
        keys, _ = _getCmdMapKeys(os.path.join(_SUBFUNC_DIR, f"{domain}Api.py"))
        if sorted(keys) != sorted(cmdList):
            errList.append(f"{domain}Api CMD_MAP 应为 {cmdList}, 实为 {keys}")
        domainCmdList.append((domain, cmdList))

    crudKeys, _ = _getCmdMapKeys(os.path.join(_SUBFUNC_DIR, "crudApi.py"))
    domainCmdList.append(("crud", crudKeys))

    #各域之间不得出现同名 CMD(V1 的静态等价检查)
    ownerMap = {}
    for domain, cmdList in domainCmdList:
        for cmd in cmdList:
            if cmd in ownerMap:
                errList.append(f"CMD 冲突: {cmd} 同时属于 {ownerMap[cmd]} 与 {domain}")
            ownerMap[cmd] = domain

    record("S18 注册表静态覆盖与 chCommon 引用", not errList, "; ".join(errList[:6]))


def _extractTextFileColumns(filePath):
    """表定义文件列名(顺序), 去掉可能存在的反引号包裹"""
    return [ln.split(" ")[0].strip().strip("`") for ln in _readLines(filePath) if ln.strip()]


def _extractDdlColumns(filePath, funcName):
    """从建表函数内拼出 DDL 并解析列名(顺序), 供「定义文件 == 建表 DDL」逐列核对。
       实现要点: 只取函数内 aList 列表的字符串元素(生成器与手写 DDL 都是这个形态),
                 避免 ast.walk 顺序不确定; 兼容保留字被反引号包裹(如 `status`)。"""
    tree = ast.parse(readText(filePath))
    ddlText = ""

    for node in tree.body:
        if not (isinstance(node, ast.FunctionDef) and node.name == funcName):
            continue
        for item in node.body:
            if isinstance(item, ast.Assign) and isinstance(item.targets[0], ast.Name) \
                    and isinstance(item.value, ast.List):
                parts = [e.value for e in item.value.elts
                         if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                if parts:
                    ddlText = "".join(parts)
                break
        break

    if not ddlText:
        return []

    pos = ddlText.upper().find("CREATE TABLE")
    if pos >= 0:
        ddlText = ddlText[pos:]
    pos = ddlText.find("(")
    if pos >= 0:
        ddlText = ddlText[pos + 1:]

    columns = []
    for frag in ddlText.split(","):
        frag = frag.strip()
        matched = re.match(
            r"^`?([A-Za-z_][A-Za-z0-9_]*)`?\s+(INT|BIGINT|SMALLINT|TINYINT|CHAR|VARCHAR|TEXT|MEDIUMTEXT|JSON)\b",
            frag, re.IGNORECASE)
        if matched:
            columns.append(matched.group(1))

    return columns


def checkPortTables():
    """S19 外部既有表移植(user_basic / weixin_pay, 见 plan.md §11):
       - 定义文件与建表 DDL 逐列一致(R1: 定义文件是唯一数据源);
       - USER_BASIC 手写段 8 函数 + genOrList 齐备;
       - weixin_pay 生成段 7 个数据层函数齐备, 且生成区未混入其 REST 处理器;
       - 手写 query_weixin_pay 存在; initTables.py 已登记两张表。"""
    errList = []

    userTxt = os.path.join(_DATABASE_DIR, USER_BASIC_TXT)
    payTxt = os.path.join(_DATABASE_DIR, WEIXIN_PAY_TXT)
    for filePath in (userTxt, payTxt):
        if not os.path.isfile(filePath):
            errList.append(f"{os.path.basename(filePath)} 缺失")

    mysqlCommonPath = os.path.join(_SRC_DIR, "common", "mysqlCommon.py")
    if not os.path.isfile(mysqlCommonPath):
        record("S19 移植表(user_basic/weixin_pay)", False, "common/mysqlCommon.py 缺失")
        return

    mysqlText = readText(mysqlCommonPath)
    definedFuncs = set(_getTopLevelDefNames(mysqlCommonPath))

    #1) USER_BASIC 手写段
    missingList = [name for name in USER_BASIC_FUNC_LIST + USER_BASIC_HELPER_FUNC_LIST
                   if name not in definedFuncs]
    if missingList:
        errList.append(f"USER_BASIC 手写函数缺失: {missingList}")

    if os.path.isfile(userTxt):
        txtCols = _extractTextFileColumns(userTxt)
        ddlCols = _extractDdlColumns(mysqlCommonPath, "createUserBasic")
        if txtCols != ddlCols:
            errList.append(f"userBasic.txt({len(txtCols)}列) != createUserBasic DDL({len(ddlCols)}列)")

    #2) weixin_pay 生成段 + 手写查询
    productPath = os.path.join(_AUTO_GEN_DIR, "auto_gen_code_weixin_pay.py")
    if not os.path.isfile(productPath):
        errList.append("auto_gen_code_weixin_pay.py 缺失")
    elif os.path.isfile(payTxt):
        txtCols = _extractTextFileColumns(payTxt)
        ddlCols = _extractDdlColumns(productPath, "create_weixin_pay")
        if txtCols != ddlCols:
            errList.append(f"weixin_pay.txt({len(txtCols)}列) != create_weixin_pay DDL({len(ddlCols)}列)")

    payMissing = [name for name in WEIXIN_PAY_GENERATED_FUNC_LIST if name not in definedFuncs]
    if payMissing:
        errList.append(f"mysqlCommon 生成区缺少 weixin_pay 数据层: {payMissing}")

    if "query_weixin_pay" not in definedFuncs:
        errList.append("缺少手写 query_weixin_pay")

    if "def funcWeixinpay" in mysqlText:
        errList.append("mysqlCommon 混入 weixin_pay 的 REST 处理器")

    #3) 建表脚本登记
    initTablesPath = os.path.join(_SRC_DIR, "tools", "initTables.py")
    if not os.path.isfile(initTablesPath):
        errList.append("tools/initTables.py 缺失")
    else:
        initText = readText(initTablesPath)
        for token in ("weixin_pay", "USER_BASIC"):
            if token not in initText:
                errList.append(f"initTables.py 未登记 {token}")

    record("S19 移植表(user_basic/weixin_pay)", not errList, "; ".join(errList[:6]))


def checkTopicService():
    """S20 SP2a(C2 主题管理)静态校验:
       - processor/topicService.py 的业务函数/常量齐备;
       - 只经 mysqlCommon/chCommon(禁裸 SQL), 且真实引用 upsertByUniqueKey / fillFileUrls / 文件门面;
       - ERR_* 错误码落点为 contenthub 消息表中真实存在的 C 段/D 段码;
       - topicApi 的 CMD_MAP 覆盖 8 个接管端点 + topicrender 占位, 处理函数签名 func(CMD, dataSet, sessionIDSet);
       - crudApi 已不再装配被接管端点(否则聚合器 V1 冲突会在导入期抛错)。"""
    errList = []

    servicePath = os.path.join(_SRC_DIR, "processor", "topicService.py")
    if not os.path.isfile(servicePath):
        errList.append("processor/topicService.py 缺失")
    else:
        names = collectTopLevelNames(servicePath)
        missFunc = [n for n in TOPIC_SERVICE_FUNC_LIST if n not in names]
        if missFunc:
            errList.append(f"topicService 缺少函数: {missFunc}")
        missConst = [n for n in TOPIC_SERVICE_CONST_LIST if n not in names]
        if missConst:
            errList.append(f"topicService 缺少常量: {missConst}")

        text = readText(servicePath)

        #真实引用公共件(防「建而不用」): 数据层 / 幂等写入 / fileID 转 URL / 文件门面 / delFlag
        for token in ["comMysql.", "comCh.upsertByUniqueKey", "comCh.fillFileUrls",
                      "fileStorageCommon", "delFlag"]:
            if token not in text:
                errList.append(f"topicService 未使用: {token}")

        #禁裸 SQL(逐行扫非注释行; R1)
        sqlPattern = re.compile(
            r"\b(SELECT\s+.*\bFROM\b|INSERT\s+INTO\b|UPDATE\s+\w+\s+SET\b|DELETE\s+FROM\b|"
            r"CREATE\s+TABLE\b|DROP\s+TABLE\b|ALTER\s+TABLE\b)", re.IGNORECASE)
        for idx, line in enumerate(text.split("\n")):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if sqlPattern.search(stripped):
                errList.append(f"topicService#{idx + 1} 疑似裸 SQL: {stripped[:40]}")

        #错误码落点必须真实存在于 contenthub 消息表(避免拼写错误导致的静默 unknown error)
        errMsgPath = os.path.join(_SRC_DIR, "common", "errMsgCommon.py")
        try:
            namespace = {}
            exec(compile(readText(errMsgPath), errMsgPath, "exec"), namespace)
            wordList = namespace.get("CONST_ERROR_wordList", {}).get("contenthub", {}).get("CN", {})
            codeList = []
            for node in ast.parse(text).body:
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                        and node.targets[0].id.startswith("ERR_") \
                        and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    codeList.append(node.value.value)
            if not codeList:
                errList.append("topicService 未定义 ERR_* 错误码常量")
            for code in codeList:
                if code not in wordList:
                    errList.append(f"错误码 {code} 不在 contenthub 消息表")
        except Exception as e:
            errList.append(f"错误码落点核查失败: {e}")

    #topicApi 注册表与处理函数签名
    apiPath = os.path.join(_SUBFUNC_DIR, "topicApi.py")
    if not os.path.isfile(apiPath):
        errList.append("subfunc/topicApi.py 缺失")
    else:
        apiText = readText(apiPath)
        cmdKeys, funcNames = _getCmdMapKeys(apiPath)
        expectKeys = sorted(TOPIC_CMD_LIST)
        if sorted(cmdKeys) != expectKeys:
            errList.append(f"topicApi CMD_MAP 应为 {expectKeys}, 实为 {sorted(cmdKeys)}")
        if "topicrender" in cmdKeys:
            errList.append("topicrender 应已迁出 topicApi(归 subfunc/renderApi.py)")

        definedFuncs = set(_getTopLevelDefNames(apiPath))
        undefinedList = sorted(set(funcNames) - definedFuncs)
        if undefinedList:
            errList.append(f"topicApi 注册表指向未定义函数: {undefinedList}")

        #处理函数统一签名 func(CMD, dataSet, sessionIDSet)
        for node in ast.parse(apiText).body:
            if not (isinstance(node, ast.FunctionDef) and node.name in funcNames):
                continue
            argNames = [a.arg for a in node.args.args]
            if argNames != ["CMD", "dataSet", "sessionIDSet"]:
                errList.append(f"{node.name} 签名不符: {argNames}")
            if node.args.vararg or node.args.kwarg:
                errList.append(f"{node.name} 不得使用 *args/**kwargs")

        if "PLACEHOLDER_CMD_LIST = []" not in apiText:
            errList.append("topicApi 的 PLACEHOLDER_CMD_LIST 应为 [] (topicrender 已迁出)")
        if "topicService" not in apiText:
            errList.append("topicApi 未真实引用 topicService")

    #crudApi 不得再装配被接管端点(否则聚合器 V1 冲突)
    crudKeys, _ = _getCmdMapKeys(os.path.join(_SUBFUNC_DIR, "crudApi.py"))
    overlapList = sorted(set(crudKeys) & set(TOPIC_CMD_LIST))
    if overlapList:
        errList.append(f"crudApi 仍装配被接管端点: {overlapList}")

    record("S20 SP2a 主题服务与端点", not errList, "; ".join(errList[:6]))


def checkAssetService():
    """S21 SP2b(C3 素材图库)静态校验:
       - processor/assetService.py 的业务函数/常量齐备;
       - 只经 mysqlCommon/chCommon/fileStorageCommon(禁裸 SQL), 且真实引用 upsertByUniqueKey /
         fillFileUrls / 文件门面 / contentHash 去重 / 规格口径(MAX_PIC_SIZE / THUMBNAIL_SIZE);
       - ERR_* 错误码落点为 contenthub 消息表中真实存在的 C 段/D 段码;
       - assetApi 的 CMD_MAP 覆盖 8 个接管端点 + artifactpack(SP4b 起为真实实现), 处理函数签名 func(CMD, dataSet, sessionIDSet);
       - crudApi 已不再装配被接管端点(否则聚合器 V1 冲突会在导入期抛错)。"""
    errList = []

    servicePath = os.path.join(_SRC_DIR, "processor", "assetService.py")
    if not os.path.isfile(servicePath):
        errList.append("processor/assetService.py 缺失")
    else:
        names = collectTopLevelNames(servicePath)
        missFunc = [n for n in ASSET_SERVICE_FUNC_LIST if n not in names]
        if missFunc:
            errList.append(f"assetService 缺少函数: {missFunc}")
        missConst = [n for n in ASSET_SERVICE_CONST_LIST if n not in names]
        if missConst:
            errList.append(f"assetService 缺少常量: {missConst}")

        text = readText(servicePath)

        #真实引用公共件(防「建而不用」): 数据层 / 幂等写入 / fileID 转 URL / 文件门面 /
        #contentHash 去重 / 规格口径 / delFlag
        for token in ["comMysql.", "comCh.upsertByUniqueKey", "comCh.fillFileUrls",
                      "fileStorageCommon", "contentHash", "MAX_PIC_SIZE", "THUMBNAIL_SIZE",
                      "delFlag"]:
            if token not in text:
                errList.append(f"assetService 未使用: {token}")

        #红线 R2: 不得出现任何厂商分支判断(三后端切换只经 fileStorageCommon 门面)
        for token in ["aliyunOSS", "tencentCOS", "selfFileCommon"]:
            if token in text:
                errList.append(f"assetService 出现厂商分支: {token}")

        #禁裸 SQL(逐行扫非注释行; R1)
        sqlPattern = re.compile(
            r"\b(SELECT\s+.*\bFROM\b|INSERT\s+INTO\b|UPDATE\s+\w+\s+SET\b|DELETE\s+FROM\b|"
            r"CREATE\s+TABLE\b|DROP\s+TABLE\b|ALTER\s+TABLE\b)", re.IGNORECASE)
        for idx, line in enumerate(text.split("\n")):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if sqlPattern.search(stripped):
                errList.append(f"assetService#{idx + 1} 疑似裸 SQL: {stripped[:40]}")

        #错误码落点必须真实存在于 contenthub 消息表(避免拼写错误导致的静默 unknown error)
        errMsgPath = os.path.join(_SRC_DIR, "common", "errMsgCommon.py")
        try:
            namespace = {}
            exec(compile(readText(errMsgPath), errMsgPath, "exec"), namespace)
            wordList = namespace.get("CONST_ERROR_wordList", {}).get("contenthub", {}).get("CN", {})
            codeList = []
            for node in ast.parse(text).body:
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                        and node.targets[0].id.startswith("ERR_") \
                        and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    codeList.append(node.value.value)
            if not codeList:
                errList.append("assetService 未定义 ERR_* 错误码常量")
            for code in codeList:
                if code not in wordList:
                    errList.append(f"错误码 {code} 不在 contenthub 消息表")
        except Exception as e:
            errList.append(f"错误码落点核查失败: {e}")

    #assetApi 注册表与处理函数签名
    apiPath = os.path.join(_SUBFUNC_DIR, "assetApi.py")
    if not os.path.isfile(apiPath):
        errList.append("subfunc/assetApi.py 缺失")
    else:
        apiText = readText(apiPath)
        cmdKeys, funcNames = _getCmdMapKeys(apiPath)
        expectKeys = sorted(ASSET_CMD_LIST + ["artifactpack"])
        if sorted(cmdKeys) != expectKeys:
            errList.append(f"assetApi CMD_MAP 应为 {expectKeys}, 实为 {sorted(cmdKeys)}")

        definedFuncs = set(_getTopLevelDefNames(apiPath))
        undefinedList = sorted(set(funcNames) - definedFuncs)
        if undefinedList:
            errList.append(f"assetApi 注册表指向未定义函数: {undefinedList}")

        #处理函数统一签名 func(CMD, dataSet, sessionIDSet)
        for node in ast.parse(apiText).body:
            if not (isinstance(node, ast.FunctionDef) and node.name in funcNames):
                continue
            argNames = [a.arg for a in node.args.args]
            if argNames != ["CMD", "dataSet", "sessionIDSet"]:
                errList.append(f"{node.name} 签名不符: {argNames}")
            if node.args.vararg or node.args.kwarg:
                errList.append(f"{node.name} 不得使用 *args/**kwargs")

        #★ SP4b 起 artifactpack 已落地(素材域占位清空); 本项随 SP4b 调整, 由 S27 复核真实实现
        if "PLACEHOLDER_CMD_LIST = []" not in apiText:
            errList.append("assetApi 的 PLACEHOLDER_CMD_LIST 应已清空(SP4b 起 artifactpack 已落地)")
        if "assetService" not in apiText:
            errList.append("assetApi 未真实引用 assetService")

    #crudApi 不得再装配被接管端点(否则聚合器 V1 冲突)
    crudKeys, _ = _getCmdMapKeys(os.path.join(_SUBFUNC_DIR, "crudApi.py"))
    overlapList = sorted(set(crudKeys) & set(ASSET_CMD_LIST))
    if overlapList:
        errList.append(f"crudApi 仍装配被接管端点: {overlapList}")

    record("S21 SP2b 素材服务与端点", not errList, "; ".join(errList[:6]))


def _loadLayoutSeeds():
    """AST 读取 tools/initSeed.py 的 LAYOUT_SEED_LIST(权威 specJson 取值), 不执行模块"""
    seedPath = os.path.join(_SRC_DIR, "tools", "initSeed.py")
    if not os.path.isfile(seedPath):
        return []
    tree = ast.parse(readText(seedPath))
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id == "LAYOUT_SEED_LIST":
            return [ast.literal_eval(element) for element in node.value.elts]
    return []


def _checkNoReverseImport(filePath, relPath, errList, forbiddenModules = ("processor", "subfunc")):
    """逐行(跳过纯注释行)检查是否 import 了禁用的上游模块"""
    pattern = re.compile(r"^\s*(import|from)\s+(" + "|".join(forbiddenModules) + r")\b")
    for idx, line in enumerate(readText(filePath).split("\n")):
        if line.strip().startswith("#"):
            continue
        if pattern.search(line):
            errList.append(f"{relPath}#{idx + 1}: 反向依赖 {line.strip()[:40]}")


def checkRenderEngine():
    """S22 SP2c(C4 版式引擎)静态校验:
       - engine 包与 4 套模板齐备; layoutType 与模板目录一一对应(引擎常量 + 种子 templatePath);
       - specJson 既有键被真实消费(consumed by layoutEngine, 不得自造第二套参数名);
       - topicrender 归属唯一(subfunc/renderApi.py, 不在 topicApi);
       - 模板不含平台专属硬编码; carousel 有交互+静态兜底; swipe 不自实现交互;
       - 引擎层不反向依赖 processor/subfunc; imageProc 经文件门面且无厂商分支。"""
    errList = []

    #1) 引擎文件齐备(py_compile 在 S1, 这里只查存在性)
    for relPath in ["engine/__init__.py", "engine/layoutEngine.py", "engine/imageProc.py",
                    "processor/renderService.py"]:
        if not os.path.isfile(os.path.join(_SRC_DIR, relPath)):
            errList.append(f"{relPath} 缺失")

    #2) 模板齐备
    for relPath in ENGINE_TEMPLATE_FILE_LIST:
        if not os.path.isfile(os.path.join(TEMPLATE_DIR, relPath)):
            errList.append(f"templates/{relPath} 缺失")

    #3) layoutType <-> 模板目录一一对应
    engineMap = {}
    layoutEnginePath = os.path.join(ENGINE_DIR, "layoutEngine.py")
    if os.path.isfile(layoutEnginePath):
        for node in ast.parse(readText(layoutEnginePath)).body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                    and node.targets[0].id == "LAYOUT_TYPE_TEMPLATE_MAP":
                engineMap = ast.literal_eval(node.value)
    if engineMap != ENGINE_LAYOUT_TYPE_TEMPLATE_MAP:
        errList.append(f"LAYOUT_TYPE_TEMPLATE_MAP 应为 {ENGINE_LAYOUT_TYPE_TEMPLATE_MAP}, 实为 {engineMap}")

    #4) specJson 键被真实消费 + 种子 templatePath 与目录一致
    seedList = _loadLayoutSeeds()
    if not seedList:
        errList.append("initSeed.LAYOUT_SEED_LIST 读取失败")
    layoutEngineText = readText(layoutEnginePath) if os.path.isfile(layoutEnginePath) else ""
    for seed in seedList:
        layoutType = seed.get("layoutType")
        dirName = ENGINE_LAYOUT_TYPE_TEMPLATE_MAP.get(layoutType)
        if not dirName:
            errList.append(f"initSeed 出现未登记 layoutType: {layoutType}")
            continue
        try:
            spec = json.loads(seed.get("specJson") or "{}")
        except Exception as e:
            errList.append(f"{layoutType} specJson 非法: {e}")
            continue
        for key in spec.keys():
            if key not in layoutEngineText:
                errList.append(f"{layoutType} specJson 键未被消费: {key}")
        templatePath = (seed.get("templatePath") or "").replace("\\", "/")
        if not templatePath.endswith(f"{dirName}/index.html"):
            errList.append(f"{layoutType} 种子 templatePath 与目录不符: {templatePath}")

    #5) topicrender 归属唯一
    topicApiPath = os.path.join(_SUBFUNC_DIR, "topicApi.py")
    renderApiPath = os.path.join(_SUBFUNC_DIR, "renderApi.py")
    topicKeys = _getCmdMapKeys(topicApiPath)[0] if os.path.isfile(topicApiPath) else []
    if "topicrender" in topicKeys:
        errList.append("topicrender 仍登记在 topicApi(归属不唯一)")
    if not os.path.isfile(renderApiPath):
        errList.append("subfunc/renderApi.py 缺失")
    else:
        renderKeys, renderFuncNames = _getCmdMapKeys(renderApiPath)
        if sorted(renderKeys) != sorted(RENDER_CMD_LIST):
            errList.append(f"renderApi CMD_MAP 应为 {sorted(RENDER_CMD_LIST)}, 实为 {sorted(renderKeys)}")
        undefinedList = sorted(set(renderFuncNames) - set(_getTopLevelDefNames(renderApiPath)))
        if undefinedList:
            errList.append(f"renderApi 注册表指向未定义函数: {undefinedList}")
        renderText = readText(renderApiPath)
        if "renderService" not in renderText:
            errList.append("renderApi 未真实引用 renderService")

    #6) 模板不含平台专属硬编码
    for relPath in ENGINE_TEMPLATE_FILE_LIST:
        filePath = os.path.join(TEMPLATE_DIR, relPath)
        if not os.path.isfile(filePath):
            continue
        text = readText(filePath)
        for token in TEMPLATE_FORBIDDEN_TOKEN_LIST:
            if token in text:
                errList.append(f"templates/{relPath} 含平台专属硬编码: {token}")

    #7) carousel 有交互+静态兜底; swipe 不自实现交互
    carouselPath = os.path.join(TEMPLATE_DIR, "carousel_v1", "index.html")
    if os.path.isfile(carouselPath):
        carouselText = readText(carouselPath)
        for token in ["data-interactive", "data-carousel-slide", "data-carousel-prev",
                      'data-carousel-fallback="static"', "<script"]:
            if token not in carouselText:
                errList.append(f"carousel_v1 缺少: {token}")
    swipePath = os.path.join(TEMPLATE_DIR, "swipe_v1", "index.html")
    if os.path.isfile(swipePath):
        swipeText = readText(swipePath)
        if "<script" in swipeText or re.search(r"onclick\s*=", swipeText, re.IGNORECASE):
            errList.append("swipe_v1 出现自实现交互(script/onclick)")
        if 'data-mechanism="platform_native"' not in swipeText:
            errList.append("swipe_v1 缺少 platform_native 标记")

    #8) 引擎分层: 不反向依赖 processor/subfunc; imageProc 经文件门面且无厂商分支
    for relPath in ["engine/layoutEngine.py", "engine/imageProc.py"]:
        filePath = os.path.join(_SRC_DIR, relPath)
        if os.path.isfile(filePath):
            _checkNoReverseImport(filePath, relPath, errList)
    imageProcPath = os.path.join(ENGINE_DIR, "imageProc.py")
    if os.path.isfile(imageProcPath):
        imageProcText = readText(imageProcPath)
        if "fileStorageCommon" not in imageProcText:
            errList.append("imageProc 未经 fileStorageCommon 门面")
        for token in ["aliyunOSS", "tencentCOS", "selfFileCommon"]:
            if token in imageProcText:
                errList.append(f"imageProc 出现厂商分支: {token}")

    #9) renderService 为「业务层 -> 引擎层」连接点
    renderServicePath = os.path.join(_SRC_DIR, "processor", "renderService.py")
    if os.path.isfile(renderServicePath):
        renderServiceText = readText(renderServicePath)
        for token in ["topicService", "assetService", "layoutEngine"]:
            if token not in renderServiceText:
                errList.append(f"renderService 未引用: {token}")

    record("S22 SP2c 版式引擎与模板", not errList, "; ".join(errList[:8]))


def _loadPlatformSeeds():
    """AST 读取 tools/initSeed.py 的 PLATFORM_SEED_LIST(权威 ch_platform 规格), 不执行模块"""
    seedPath = os.path.join(_SRC_DIR, "tools", "initSeed.py")
    if not os.path.isfile(seedPath):
        return []
    tree = ast.parse(readText(seedPath))
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id == "PLATFORM_SEED_LIST":
            return [ast.literal_eval(element) for element in node.value.elts]
    return []


def _execStandaloneModule(filePath, moduleName):
    """把「只依赖标准库」的模块源码 exec 到隔离命名空间(便于无第三方依赖时做真行为断言)"""
    namespace = {"__file__": filePath, "__name__": moduleName}
    exec(compile(readText(filePath), filePath, "exec"), namespace)
    return namespace


def checkPlatformAdapter():
    """S23 SP3a(C5 平台适配层)静态校验:
       - platformAdapter 四文件 + engine/inlineStyle.py 齐备;
       - PlatformAdapter 契约五方法齐备(render/validate/package/deliver/checkHealth);
       - deliver ★本轮一律显式返回「未实现」(C2), 具体适配器不覆写(不得静默成功);
       - base.checkPlatformSpec 按 ch_platform 数据驱动生效(标题超长 C5 / 图片超量 C6 / 封面与正文图规格 D1);
       - inlineStyle: 输出无 class 依赖、无残留 <style>(样式已下沉内联);
         外链图片策略 = 平台显示域原样 / 非白名单外链显式 E4(绝不静默保留外链); carousel 交互降级复用静态兜底;
       - wechatMp/generic 已注册且平台差异(显示域白名单)落在适配器内;
         ★ SP4a: wechat_mp 覆写 deliver(通道调用, 会调微信接口), generic/xiaohongshu 仍继承基类显式未实现(C2),
           故本项零网络扫描**不再包含 wechatMp**(其网络调用由 S26 与投递链路约定把关);
       - topicrender 经 platformAdapter 分支(platform 参数化 + renderMode 支持 sync/job), 且无新增 CMD。"""
    errList = []

    #1) 文件齐备(py_compile 在 S1)
    for relPath in ["processor/platformAdapter/__init__.py", "processor/platformAdapter/base.py",
                    "processor/platformAdapter/wechatMp.py", "processor/platformAdapter/generic.py",
                    "engine/inlineStyle.py"]:
        if not os.path.isfile(os.path.join(_SRC_DIR, relPath)):
            errList.append(f"{relPath} 缺失")

    basePath = os.path.join(PLATFORM_ADAPTER_DIR, "base.py")
    inlineStylePath = os.path.join(_SRC_DIR, "engine", "inlineStyle.py")

    #2) 契约五方法齐备(AST)
    if os.path.isfile(basePath):
        tree = ast.parse(readText(basePath))
        methodSet = set()
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == "PlatformAdapter":
                methodSet = {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
        if not methodSet:
            errList.append("未找到 PlatformAdapter 基类")
        else:
            missList = [name for name in ADAPTER_CONTRACT_METHOD_LIST if name not in methodSet]
            if missList:
                errList.append(f"PlatformAdapter 缺少契约方法: {missList}")

    #3) deliver 未实现(真行为) + ch_platform 数据驱动规格校验(真行为)
    if os.path.isfile(basePath):
        baseNs = None
        try:
            baseNs = _execStandaloneModule(basePath, "platformAdapter.base")
        except Exception as e:
            errList.append(f"base.py 无法独立执行(疑似引入非标准库依赖): {e}")

        if baseNs:
            BaseClass = baseNs.get("PlatformAdapter")
            try:
                stubClass = type("_StubAdapter", (BaseClass,), {
                    "render": lambda self, *a, **k: {},
                    "package": lambda self, *a, **k: {},
                    "checkHealth": lambda self, *a, **k: {},
                })
                deliverRtn = stubClass().deliver({}, {})
                if deliverRtn.get("errCode") != "C2":
                    errList.append(f"deliver 未返回显式未实现(C2): {deliverRtn.get('errCode')}")
            except Exception as e:
                errList.append(f"deliver 行为断言失败: {e}")

            wechatSeed = next((s for s in _loadPlatformSeeds() if s.get("platformCode") == "wechat_mp"), None)
            if not wechatSeed:
                errList.append("initSeed 中未找到 wechat_mp 平台种子")
            else:
                checkSpec = baseNs.get("checkPlatformSpec")
                titleMaxLen = int(wechatSeed.get("titleMaxLen") or 0)
                imageMaxCount = int(wechatSeed.get("imageMaxCount") or 0)
                caseList = [
                    ("合规入参", checkSpec(wechatSeed, {"title": "t" * 8, "summary": "s"}, []), "B0"),
                    ("标题超长", checkSpec(wechatSeed, {"title": "t" * (titleMaxLen + 1)}, []), "C5"),
                    ("图片超量", checkSpec(wechatSeed, {"title": "t"},
                                          [{"usageType": "body", "width": 1080, "height": 1440}
                                           for _ in range(imageMaxCount + 1)]), "C6"),
                    ("封面尺寸不符", checkSpec(wechatSeed, {"title": "t"},
                                             [{"usageType": "cover", "width": 100, "height": 100}]), "D1"),
                    ("正文图规格不符", checkSpec(wechatSeed, {"title": "t"},
                                               [{"usageType": "body", "width": 720, "height": 960}]), "D1"),
                ]
                for caseName, rtnData, expectCode in caseList:
                    if rtnData.get("errCode") != expectCode:
                        errList.append(f"{caseName} 期望 {expectCode} 实为 {rtnData.get('errCode')}")

    #4) inlineStyle 真行为: 无 class / 无 <style> / 样式下沉 / 外链策略 / carousel 交互降级
    if os.path.isfile(inlineStylePath):
        styleNs = None
        try:
            styleNs = _execStandaloneModule(inlineStylePath, "engine.inlineStyle")
        except Exception as e:
            errList.append(f"inlineStyle.py 无法独立执行(疑似引入非标准库依赖): {e}")

        if styleNs:
            inlineHtml = styleNs.get("inlineHtml")
            resolveImageUrl = styleNs.get("resolveImageUrl")
            try:
                sample = ('<style>[data-layout="stack_v1"] img{max-width:100%;}</style>'
                          '<p class="a x"><img class="c" src="https://mmbiz.qpic.cn/a.jpg" style="width:100%;"/></p>')
                inlineRtn = inlineHtml(sample, ["mmbiz.qpic.cn"])
                inlineContent = (inlineRtn.get("data") or {}).get("content", "")
                if inlineRtn.get("errCode") != "B0":
                    errList.append(f"inlineHtml 正常样例失败: {inlineRtn.get('errCode')}")
                if "class=" in inlineContent:
                    errList.append("inlineHtml 输出残留 class 依赖")
                if "<style" in inlineContent:
                    errList.append("inlineHtml 输出残留 <style>")
                if "max-width:100%" not in inlineContent:
                    errList.append("inlineHtml 未把 <style> 规则下沉为内联 style")
                if (inlineRtn.get("data") or {}).get("classDependency") is not False:
                    errList.append("inlineHtml classDependency 标记非 False")

                carouselSample = ('<section data-layout="carousel_v1" data-interactive="1">'
                                  '<figure data-carousel-slide="1"></figure><script>var a=1;</script></section>'
                                  '<section data-carousel-fallback="static">'
                                  '<img src="https://mmbiz.qpic.cn/b.jpg"/></section>')
                degradeRtn = inlineHtml(carouselSample, ["mmbiz.qpic.cn"], degradeInteraction = True)
                degradeContent = (degradeRtn.get("data") or {}).get("content", "")
                if degradeRtn.get("errCode") != "B0":
                    errList.append(f"carousel 降级失败: {degradeRtn.get('errCode')}")
                if "<script" in degradeContent:
                    errList.append("carousel 降级后仍残留 <script>")
                if 'data-degraded="static_fallback"' not in degradeContent:
                    errList.append("carousel 降级未复用静态图集兜底节点")
                if 'data-carousel-fallback="static"' not in degradeContent:
                    errList.append("carousel 降级丢失原始兜底节点标记")
            except Exception as e:
                errList.append(f"inlineHtml 行为断言失败: {e}")

            try:
                okUrl = resolveImageUrl("https://mmbiz.qpic.cn/a.jpg", ["mmbiz.qpic.cn"])
                extUrl = resolveImageUrl("https://example.com/a.jpg", ["mmbiz.qpic.cn"])
                if okUrl.get("errCode") != "B0":
                    errList.append(f"平台显示域图片被误判: {okUrl.get('errCode')}")
                if extUrl.get("errCode") != "E4":
                    errList.append(f"外链图片未显式返回 E4: {extUrl.get('errCode')}")
            except Exception as e:
                errList.append(f"resolveImageUrl 行为断言失败: {e}")

    #5) 适配器注册 + 平台差异落在适配器内 + 具体适配器不覆写 deliver
    if os.path.isfile(basePath):
        for node in ast.parse(readText(basePath)).body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                    and node.targets[0].id == "ADAPTER_MODULE_MAP":
                try:
                    adapterMap = ast.literal_eval(node.value)
                except Exception:
                    adapterMap = {}
                for code, className in ADAPTER_REGISTRY_EXPECT.items():
                    entry = adapterMap.get(code) or ()
                    if className not in entry:
                        errList.append(f"ADAPTER_MODULE_MAP 未登记 {code} -> {className}")

    #★ SP4a: wechat_mp 覆写 deliver(通道调用); generic 继续继承基类(显式未实现 C2)
    for relPath, className, expectTokenList, deliverPolicy in (
            ("processor/platformAdapter/wechatMp.py", "WechatMpAdapter", [WECHAT_DISPLAY_HOST], "override"),
            ("processor/platformAdapter/generic.py", "GenericAdapter", [], "inherit")):
        filePath = os.path.join(_SRC_DIR, relPath)
        if not os.path.isfile(filePath):
            continue
        text = readText(filePath)
        tree = ast.parse(text)
        if className not in {node.name for node in tree.body if isinstance(node, ast.ClassDef)}:
            errList.append(f"{relPath} 缺少类 {className}")
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == className:
                methodNames = {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
                if deliverPolicy == "override" and "deliver" not in methodNames:
                    errList.append(f"{className} 未实现 deliver(SP4a 起 wechat_mp 须提供通道调用)")
                if deliverPolicy == "inherit" and "deliver" in methodNames:
                    errList.append(f"{className} 覆写了 deliver(未实现应由基类统一保证)")
                for expectMethod in ("render", "validate", "package", "checkHealth"):
                    if expectMethod not in methodNames:
                        errList.append(f"{className} 缺少方法 {expectMethod}")
        for token in expectTokenList:
            if token not in text:
                errList.append(f"{relPath} 未声明平台显示域 {token}")
        if "PlatformAdapter" not in text:
            errList.append(f"{relPath} 未继承 PlatformAdapter")
        if "checkPlatformSpec" not in text:
            errList.append(f"{relPath} validate 未复用 base.checkPlatformSpec")

    #6) 分层与零网络: inlineStyle 不得反向依赖 processor/subfunc; 适配器不得 import subfunc; 无网络调用痕迹
    #   ★ SP4a: wechat_mp 的 deliver 按设计就是「通道调用」(调微信开放平台接口), 故不再纳入零网络扫描;
    #   其余适配器(generic/xiaohongshu)与引擎层仍必须保持零网络(小红书平台红线: 不投递/不发布)。
    _checkNoReverseImport(os.path.join(_SRC_DIR, "engine", "inlineStyle.py"), "engine/inlineStyle.py",
                          errList, forbiddenModules = ("processor", "subfunc"))
    for fileName in PLATFORM_ADAPTER_FILE_LIST:
        filePath = os.path.join(PLATFORM_ADAPTER_DIR, fileName)
        if os.path.isfile(filePath):
            _checkNoReverseImport(filePath, f"processor/platformAdapter/{fileName}", errList,
                                  forbiddenModules = ("subfunc",))
    for relPath in ["processor/platformAdapter/base.py",
                    "processor/platformAdapter/generic.py", "processor/platformAdapter/xiaohongshu.py",
                    "engine/inlineStyle.py", "engine/htmlToImage.py"]:
        filePath = os.path.join(_SRC_DIR, relPath)
        if not os.path.isfile(filePath):
            continue
        text = readText(filePath)
        for token in NETWORK_FORBIDDEN_TOKEN_LIST:
            if token in text:
                errList.append(f"{relPath} 出现网络调用痕迹: {token}")
    #★ SP4c: S23 零网络扫描同步纳入 chmonitor/ 与 monitor/(告警通道为占位实现; museum 迁移代码已剥离网络原语, 不发任何网络请求)
    for relPath in MONITOR_ZERO_NETWORK_FILE_LIST:
        filePath = os.path.join(_SRC_DIR, relPath)
        if not os.path.isfile(filePath):
            continue
        text = readText(filePath)
        for token in NETWORK_FORBIDDEN_TOKEN_LIST:
            if token in text:
                errList.append(f"{relPath} 出现网络调用痕迹: {token}")

    #7) topicrender 经 platformAdapter 分支(platform 参数化 + renderMode=job -> C2), 且无新增 CMD
    renderServicePath = os.path.join(_SRC_DIR, "processor", "renderService.py")
    if os.path.isfile(renderServicePath):
        serviceText = readText(renderServicePath)
        for token in ["platformAdapter", "getAdapter", "loadLayoutRecord", "renderMode",
                      "SUPPORTED_RENDER_MODE_LIST", "comMysql.query_ch_platform"]:
            if token not in serviceText:
                errList.append(f"renderService 未接入平台分支: 缺少 {token}")
        if "ERR_NOT_IMPLEMENTED" not in serviceText:
            errList.append("renderService 未对 renderMode=job 返回 C2")
    else:
        errList.append("processor/renderService.py 缺失")

    renderApiPath = os.path.join(_SUBFUNC_DIR, "renderApi.py")
    if os.path.isfile(renderApiPath):
        renderKeys = _getCmdMapKeys(renderApiPath)[0]
        if sorted(renderKeys) != sorted(RENDER_CMD_LIST):
            errList.append(f"renderApi CMD_MAP 新增/变更了端点(应为 {RENDER_CMD_LIST}): {renderKeys}")
    else:
        errList.append("subfunc/renderApi.py 缺失")

    record("S23 SP3a 平台适配层", not errList, "; ".join(errList[:8]))


def checkXiaohongshuRender():
    """S24 SP3b(C5 小红书产物渲染)静态校验:
       - processor/platformAdapter/xiaohongshu.py 与 engine/htmlToImage.py 齐备;
       - XiaohongshuAdapter 契约齐备(render/validate/package/checkHealth), ★ 不覆写 deliver(未实现由基类统一保证);
       - ADAPTER_MODULE_MAP 已登记 xiaohongshu(从 C7 迁移: renderService 不再对小红书硬编码 C7);
       - deliverMode=asset_pack, ★ 无任何小红书自动发布/投递路径(静态红线扫描);
       - carousel 在小红书显式不可用(C7); swipe 强制校验(比例统一/张数)错误码落点齐备;
       - 错误码 E2(截图超时)/E3(产物失败)落在 htmlToImage; htmlToImage 零对外网络;
       - 分层: htmlToImage 不反向依赖 processor/subfunc; xiaohongshu 不 import subfunc。"""
    errList = []

    #1) 文件齐备(py_compile 在 S1)
    xhsPath = os.path.join(PLATFORM_ADAPTER_DIR, "xiaohongshu.py")
    htmlToImagePath = os.path.join(_SRC_DIR, "engine", "htmlToImage.py")
    for filePath in (xhsPath, htmlToImagePath):
        if not os.path.isfile(filePath):
            errList.append(f"{os.path.relpath(filePath, _SRC_DIR)} 缺失")

    #2) 小红书适配器契约齐备 + 不覆写 deliver
    if os.path.isfile(xhsPath):
        text = readText(xhsPath)
        tree = ast.parse(text)
        classNode = None
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == XHS_ADAPTER_CLASS:
                classNode = node
        if classNode is None:
            errList.append(f"缺少类 {XHS_ADAPTER_CLASS}")
        else:
            methodNames = {item.name for item in classNode.body if isinstance(item, ast.FunctionDef)}
            for name in XHS_CONTRACT_METHOD_LIST:
                if name not in methodNames:
                    errList.append(f"{XHS_ADAPTER_CLASS} 缺少方法 {name}")
            if "deliver" in methodNames:
                errList.append(f"{XHS_ADAPTER_CLASS} 覆写了 deliver(未实现应由基类统一保证)")
        if "PlatformAdapter" not in text:
            errList.append("xiaohongshu 未继承 PlatformAdapter")
        if 'DELIVER_MODE = "asset_pack"' not in text:
            errList.append("xiaohongshu deliverMode 非 asset_pack")

        #渲染管线复用(不重复实现): 截图经 htmlToImage, 派生经 imageProc
        for token in ["htmlToImage", "imageProc", "layoutEngine"]:
            if token not in text:
                errList.append(f"xiaohongshu 未引用渲染管线: {token}")

        #carousel 显式不可用(C7, 不静默转换)
        if XHS_UNAVAILABLE_LAYOUT_TOKEN not in text or "ERR_FIELD_INVALID" not in text:
            errList.append("xiaohongshu 未显式拦截 carousel(应返回 C7, 不得静默转换)")
        #swipe 强制校验(主计划 2.6.3)错误码落点
        for token in XHS_SWIPE_GUARD_TOKEN_LIST:
            if token not in text:
                errList.append(f"xiaohongshu swipe 强校验缺少: {token}")

        #★ 平台红线: 不引入任何小红书自动发布/投递路径
        for token in XHS_FORBIDDEN_PUBLISH_TOKEN_LIST:
            if token in text:
                errList.append(f"xiaohongshu 出现自动发布/投递痕迹: {token}")

    #3) 适配器注册(从 C7 迁移)
    basePath = os.path.join(PLATFORM_ADAPTER_DIR, "base.py")
    if os.path.isfile(basePath):
        for node in ast.parse(readText(basePath)).body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                    and node.targets[0].id == "ADAPTER_MODULE_MAP":
                try:
                    adapterMap = ast.literal_eval(node.value)
                except Exception:
                    adapterMap = {}
                entry = adapterMap.get("xiaohongshu") or ()
                if XHS_ADAPTER_CLASS not in entry:
                    errList.append("ADAPTER_MODULE_MAP 未登记 xiaohongshu -> XiaohongshuAdapter")

    #迁移硬约束: renderService 不再对小红书硬编码(选适配器统一由工厂完成)
    renderServicePath = os.path.join(_SRC_DIR, "processor", "renderService.py")
    if os.path.isfile(renderServicePath):
        if "xiaohongshu" in readText(renderServicePath):
            errList.append("renderService 仍对 xiaohongshu 硬编码(应统一走 getAdapter)")
        else:
            renderText = readText(renderServicePath)
            if "comCh.fillFileUrls" not in renderText:
                errList.append("renderService 未对产物 fileID 经 chCommon.fillFileUrls 转换")

    #4) htmlToImage: 管线函数齐备 + E2/E3 错误码落点 + 零对外网络
    if os.path.isfile(htmlToImagePath):
        htmlText = readText(htmlToImagePath)
        for name in HTML_TO_IMAGE_FUNC_LIST:
            if f"def {name}(" not in htmlText:
                errList.append(f"htmlToImage 缺少函数: {name}")
        for token in ["E2", "E3", "waitForFonts", "document.fonts"]:
            if token not in htmlText:
                errList.append(f"htmlToImage 缺少: {token}")
        if "fileStorageCommon" not in htmlText:
            errList.append("htmlToImage 产物上传未经 fileStorageCommon 门面")
        for token in NETWORK_FORBIDDEN_TOKEN_LIST:
            if token in htmlText:
                errList.append(f"htmlToImage 出现网络调用痕迹: {token}")

    #5) 分层: htmlToImage 不反向依赖 processor/subfunc; xiaohongshu 不 import subfunc
    if os.path.isfile(htmlToImagePath):
        _checkNoReverseImport(htmlToImagePath, "engine/htmlToImage.py", errList,
                              forbiddenModules = ("processor", "subfunc"))
    if os.path.isfile(xhsPath):
        _checkNoReverseImport(xhsPath, "processor/platformAdapter/xiaohongshu.py", errList,
                              forbiddenModules = ("subfunc",))

    record("S24 SP3b 小红书产物渲染", not errList, "; ".join(errList[:8]))


def checkComplianceAndLedger():
    """S25 SP3c(C8 合规校验 + ch_artifact 产物台账 + ch_render_job 渲染任务化)静态校验:
       - complianceService 函数/常量齐备;
       - ★ 规格校验单一来源: 复用 base.checkPlatformSpec + xiaohongshu.validateSwipeSpec, 禁重写规则表;
       - 统一问题清单结构(field/location/level/errCode/message + 敏感词 offsetStart/offsetEnd);
       - 限流降级路径存在(Redis 不可用 -> 进程内计数 + degraded 标记), 且只经 redisCommon;
       - renderService: 任务状态机 PENDING->RUNNING->DONE/FAILED + inputHash 复用 + artifactKey 幂等
         + sync 也建 ch_render_job(jobID 有值);
       - renderWorker: 单实例串行 + Redis 任务锁(可降级) + 无并发截图 + 可单次执行;
       - publishcheck 已实现(占位清空)且 CMD_MAP 仍为 ['publishcheck']; renderApi 仍只有 topicrender(端点不新增)。"""
    errList = []

    #1) complianceService 齐备 + 单一来源 + 问题清单结构 + 降级路径
    compPath = os.path.join(_SRC_DIR, "processor", "complianceService.py")
    if not os.path.isfile(compPath):
        errList.append("processor/complianceService.py 缺失")
    else:
        names = collectTopLevelNames(compPath)
        missFunc = [n for n in COMPLIANCE_SERVICE_FUNC_LIST if n not in names]
        if missFunc:
            errList.append(f"complianceService 缺少函数: {missFunc}")
        missConst = [n for n in COMPLIANCE_SERVICE_CONST_LIST if n not in names]
        if missConst:
            errList.append(f"complianceService 缺少常量: {missConst}")

        text = readText(compPath)
        #规格校验单一来源: 复用既有实现而非自建第二张规则表
        for token in ["checkPlatformSpec", "validateSwipeSpec", "normalizePlatformRecord"]:
            if token not in text:
                errList.append(f"complianceService 未复用规格校验: {token}")
        if "def checkPlatformSpec(" in text or "def validateSwipeSpec(" in text:
            errList.append("complianceService 重写了规格校验(违反单一来源)")
        #统一问题清单结构(含敏感词偏移区间)
        for token in ["issues", "location", "level", "errCode", "offsetStart", "offsetEnd", "matchedWord"]:
            if token not in text:
                errList.append(f"问题清单缺少字段: {token}")
        #限流降级路径(Redis 不可用 -> 进程内计数 + degraded 标记)
        for token in ["degraded", "backend", "memory", "except"]:
            if token not in text:
                errList.append(f"限流降级路径缺少: {token}")
        if "redisMainDB" not in text:
            errList.append("complianceService 限流计数未经 redisCommon 句柄")
        #分层: 不 import subfunc
        _checkNoReverseImport(compPath, "processor/complianceService.py", errList,
                              forbiddenModules = ("subfunc",))

    #2) renderService: 任务状态机 + inputHash 复用 + artifactKey 幂等 + sync 建 job
    rsPath = os.path.join(_SRC_DIR, "processor", "renderService.py")
    if not os.path.isfile(rsPath):
        errList.append("processor/renderService.py 缺失")
    else:
        names = collectTopLevelNames(rsPath)
        for funcName in ["checkJobStatusTransition", "buildInputHash", "findReusableJob", "saveArtifacts",
                         "buildArtifactKey", "updateJobStatus", "executeJob", "buildJobCode"]:
            if funcName not in names:
                errList.append(f"renderService 缺少 {funcName}()")
        rsText = readText(rsPath)
        for token in ["JOB_STATUS_LIST", "JOB_STATUS_TRANSITIONS", "ARTIFACT_STATUS_READY",
                      "ARTIFACT_STATUS_EXPIRED", "comCh.upsertByUniqueKey", "buildArtifactKey",
                      "{jobID}:{kind}:{platform}:{seqNo}", "inputHash", "reused",
                      "insert_ch_render_job"]:
            if token not in rsText:
                errList.append(f"renderService 缺少: {token}")
        for status in JOB_STATUS_EXPECT_LIST:
            if status not in rsText:
                errList.append(f"renderService 缺少任务状态 {status}")
        for status in ARTIFACT_STATUS_EXPECT_LIST:
            if status not in rsText:
                errList.append(f"renderService 缺少产物状态 {status}")

    #3) renderWorker: 单实例串行 + Redis 锁(可降级) + 无并发截图 + 可单次执行
    workerPath = os.path.join(_SRC_DIR, "schedule", "renderWorker.py")
    if not os.path.isfile(workerPath):
        errList.append("schedule/renderWorker.py 缺失")
    else:
        wNames = collectTopLevelNames(workerPath)
        for funcName in ["acquireTaskLock", "releaseTaskLock", "fetchPendingJobs", "processJob", "runOnce", "main"]:
            if funcName not in wNames:
                errList.append(f"renderWorker 缺少 {funcName}()")
        wText = readText(workerPath)
        for token in ["PENDING", "RUNNING", "executeJob", "renderService", "串行", "--once", "degraded"]:
            if token not in wText:
                errList.append(f"renderWorker 缺少: {token}")
        for token in WORKER_FORBIDDEN_CONCURRENCY_TOKEN_LIST:
            if token in wText:
                errList.append(f"renderWorker 出现并发痕迹(应串行): {token}")
        if "redisMainDB" not in wText:
            errList.append("renderWorker 任务锁未经 redisCommon 句柄")
        _checkNoReverseImport(workerPath, "schedule/renderWorker.py", errList, forbiddenModules = ("subfunc",))

    #4) 端点不变式: publishcheck 已实现(占位清空), 端点总数不新增
    compApiPath = os.path.join(_SUBFUNC_DIR, "complianceApi.py")
    if not os.path.isfile(compApiPath):
        errList.append("subfunc/complianceApi.py 缺失")
    else:
        apiKeys, apiFuncs = _getCmdMapKeys(compApiPath)
        if sorted(apiKeys) != ["publishcheck"]:
            errList.append(f"complianceApi CMD_MAP 应为 ['publishcheck'], 实为 {sorted(apiKeys)}")
        apiText = readText(compApiPath)
        if "PLACEHOLDER_CMD_LIST = []" not in apiText:
            errList.append("complianceApi 占位清单未清空(publishcheck 已实现)")
        if "complianceService" not in apiText:
            errList.append("complianceApi 未真实引用 complianceService")
        undefinedList = sorted(set(apiFuncs) - set(_getTopLevelDefNames(compApiPath)))
        if undefinedList:
            errList.append(f"complianceApi 注册表指向未定义函数: {undefinedList}")

    renderApiPath = os.path.join(_SUBFUNC_DIR, "renderApi.py")
    renderKeys = _getCmdMapKeys(renderApiPath)[0] if os.path.isfile(renderApiPath) else []
    if sorted(renderKeys) != sorted(RENDER_CMD_LIST):
        errList.append(f"renderApi CMD_MAP 变更(应仍为 {RENDER_CMD_LIST}): {sorted(renderKeys)}")

    record("S25 SP3c 合规服务与台账", not errList, "; ".join(errList[:8]))


def checkPublishDelivery():
    """S26 SP4a(C6 投递链路)静态校验:
       - 凭据安全: common/credentialCipher.py 齐备(AES-256-GCM) + 密钥来自环境变量 CH_CREDENTIAL_KEY
         + 真行为(加密→解密往返一致 / 密文与明文不同 / 无密钥时显式报错不崩溃);
       - processor/publishService.py 齐备: 幂等键拼接 / 二次确认参数必填 / 60 秒撤销窗状态机 /
         投递前**必须复用 complianceService.publishCheck** / 产物 READY 前置 / 凭据解密(F0) /
         审计留痕(成功与失败都写) / freepublish 默认关闭;
       - processor/auditService.py 齐备: ch_audit_log 字段齐备(actor..ipAddr) + payloadDigest 脱敏;
       - publishApi 接管 publishpush(不新增 CMD, 占位清空);
       - ★ 平台红线: 静态扫描确认**不存在小红书投递/发布代码路径**;
       - 投递类错误码(F 段)在 contenthub 消息表中真实存在。"""
    errList = []
    detailList = []

    #1) 文件齐备(py_compile 在 S1)
    for relPath in ["common/credentialCipher.py", "processor/auditService.py",
                    "processor/publishService.py"]:
        if not os.path.isfile(os.path.join(_SRC_DIR, relPath)):
            errList.append(f"{relPath} 缺失")

    #2) 凭据加解密公共件: 函数齐备 + 密钥来自环境变量 + 真行为
    cipherPath = os.path.join(_SRC_DIR, "common", "credentialCipher.py")
    if os.path.isfile(cipherPath):
        names = collectTopLevelNames(cipherPath)
        missFunc = [n for n in CREDENTIAL_CIPHER_FUNC_LIST if n not in names]
        if missFunc:
            errList.append(f"credentialCipher 缺少函数: {missFunc}")
        text = readText(cipherPath)
        if CREDENTIAL_KEY_ENV_TOKEN not in text:
            errList.append(f"credentialCipher 未从环境变量取密钥: {CREDENTIAL_KEY_ENV_TOKEN}")
        if "AES-256-GCM" not in text or "AESGCM" not in text:
            errList.append("credentialCipher 未使用 AES-256-GCM")
        if "os.getenv" not in text and "os.environ" not in text:
            errList.append("credentialCipher 未读取环境变量(密钥未走环境变量注入)")
        for badToken in ["BEGIN PRIVATE KEY", "BEGIN RSA PRIVATE KEY"]:
            if badToken in text:
                errList.append(f"credentialCipher 出现密钥字面量痕迹: {badToken}")

        #真行为: 模块仅标准库依赖 -> 可 exec 隔离执行(cryptography 为函数内延迟导入)
        try:
            cipherNs = _execStandaloneModule(cipherPath, "common.credentialCipher")
            testKey = "static-self-test-passphrase-0123456789"
            encRtn = cipherNs["encrypt"]("PLAINTEXT-42", rawKey = testKey)
            cipherText = (encRtn or {}).get("cipher", "")
            iv = (encRtn or {}).get("iv", "")
            if not cipherText or not iv:
                errList.append("credentialCipher.encrypt 未返回 cipher/iv")
            if "PLAINTEXT" in cipherText:
                errList.append("credentialCipher 密文中出现明文痕迹")
            if cipherNs["decrypt"](cipherText, iv, rawKey = testKey) != "PLAINTEXT-42":
                errList.append("credentialCipher 加解密往返不一致")
            if not cipherNs["maskSecret"]("abcdefgh"):
                errList.append("credentialCipher.maskSecret 未生效")

            #无密钥不崩溃: 显式抛 CredentialCipherError(非裸异常)
            savedKey = os.environ.pop(CREDENTIAL_KEY_ENV_TOKEN, None)
            try:
                if cipherNs["isKeyConfigured"]():
                    errList.append("无密钥时 isKeyConfigured 仍为真")
                try:
                    cipherNs["encrypt"]("x")
                    errList.append("无密钥时 encrypt 未显式报错")
                except Exception as e:
                    if "CredentialCipherError" not in type(e).__name__:
                        errList.append(f"无密钥时抛出非 CredentialCipherError: {type(e).__name__}")
            finally:
                if savedKey is not None:
                    os.environ[CREDENTIAL_KEY_ENV_TOKEN] = savedKey
        except Exception as e:
            if "cryptography" in str(e):
                detailList.append("cryptography 未安装, 已跳过加解密往返(依赖缺失时仍显式报错)")
            else:
                errList.append(f"credentialCipher 行为断言失败: {e}")

    #3) publishService: 编排齐备 + 关键约定(幂等/二次确认/撤销窗/合规闸门/审计/默认不群发)
    publishPath = os.path.join(_SRC_DIR, "processor", "publishService.py")
    if os.path.isfile(publishPath):
        names = collectTopLevelNames(publishPath)
        missFunc = [n for n in PUBLISH_SERVICE_FUNC_LIST if n not in names]
        if missFunc:
            errList.append(f"publishService 缺少函数: {missFunc}")
        missConst = [n for n in PUBLISH_SERVICE_CONST_LIST if n not in names]
        if missConst:
            errList.append(f"publishService 缺少常量: {missConst}")

        text = readText(publishPath)
        #幂等键拼接 {artifactID}:{accountID}:{uuid4}
        for token in ["buildIdempotencyKey", "uuid.uuid4().hex", "}:{_toInt(accountID, 0)}:",
                      "isValidIdempotencyKey"]:
            if token not in text:
                errList.append(f"publishService 幂等键约定缺失: {token}")
        #二次确认参数必填 + 审计留痕
        for token in ["CONFIRM_FLAG_KEY", "CONFIRM_TOKEN_KEY", "ERR_CONFIRM_REQUIRED", "buildConfirmToken"]:
            if token not in text:
                errList.append(f"publishService 二次确认缺失: {token}")
        #撤销窗状态机(success+delFlag+pushedYMDHMS, 不依赖 Redis)
        for token in ["REVOKE_WINDOW_SECONDS", "checkRevokeWindow", "ERR_REVOKE_WINDOW",
                      "pushedYMDHMS", "PUBLISH_DELFLAG_REVOKED"]:
            if token not in text:
                errList.append(f"publishService 撤销窗缺失: {token}")
        if "redisCommon" in text or "redisMainDB" in text:
            errList.append("publishService 撤销窗/幂等不应依赖 Redis(应仅用发布记录状态+时间)")
        #投递前必须过合规校验(复用 SP3c 的 publishCheck)
        if "complianceService.publishCheck" not in text:
            errList.append("publishService 未复用 complianceService.publishCheck(投递前合规闸门)")
        #产物 READY 前置
        for token in ["ARTIFACT_STATUS_READY", "resolveArtifactRecord", "artifactStatus"]:
            if token not in text:
                errList.append(f"publishService 产物前置校验缺失: {token}")
        #凭据解密与健康状态(F0) + 凭据写入(ch_account 读写闭环)
        for token in ["credentialCipher.decrypt", "credentialCipher.encrypt", "decryptAccountCredential",
                      "saveAccountCredential", "markAccountHealth", "ERR_CREDENTIAL"]:
            if token not in text:
                errList.append(f"publishService 凭据安全缺失: {token}")
        #审计: 成功与失败都留痕
        for token in ["auditService.writeAudit", "auditService.RESULT_FAIL", "auditService.RESULT_OK"]:
            if token not in text:
                errList.append(f"publishService 审计留痕缺失: {token}")
        #access_token 缓存 + 提前刷新
        for token in ["getAccessToken", "TOKEN_REFRESH_AHEAD_SECONDS", "_TOKEN_CACHE"]:
            if token not in text:
                errList.append(f"publishService access_token 缓存/刷新缺失: {token}")
        #推送≠发布: freepublish 默认关闭, 需三重闸门
        for token in ["checkAutoPublishGate", "AUTO_PUBLISH_ENABLED", "ERR_AUTO_PUBLISH_DISABLED",
                      "submitFreePublish", "autoPublishFlag", "verifiedFlag"]:
            if token not in text:
                errList.append(f"publishService 自动发布闸门缺失: {token}")
        #分层: 不 import subfunc
        _checkNoReverseImport(publishPath, "processor/publishService.py", errList,
                              forbiddenModules = ("subfunc",))

    #4) auditService: 字段齐备 + 脱敏(凭据明文不入审计)
    auditPath = os.path.join(_SRC_DIR, "processor", "auditService.py")
    if os.path.isfile(auditPath):
        names = collectTopLevelNames(auditPath)
        missFunc = [n for n in AUDIT_SERVICE_FUNC_LIST if n not in names]
        if missFunc:
            errList.append(f"auditService 缺少函数: {missFunc}")
        missConst = [n for n in AUDIT_SERVICE_CONST_LIST if n not in names]
        if missConst:
            errList.append(f"auditService 缺少常量: {missConst}")
        text = readText(auditPath)
        for field in AUDIT_FIELD_LIST:
            if f'"{field}"' not in text:
                errList.append(f"auditService 审计字段缺失: {field}")
        for token in ["sha256", "MASKED_VALUE", "sanitizePayload", "buildPayloadDigest"]:
            if token not in text:
                errList.append(f"auditService 脱敏/摘要缺失: {token}")
        if "insert_ch_audit_log" not in text:
            errList.append("auditService 未经 mysqlCommon 写 ch_audit_log")
        _checkNoReverseImport(auditPath, "processor/auditService.py", errList,
                              forbiddenModules = ("subfunc",))

    #5) publishApi 接管 publishpush: 不新增 CMD + 占位清空
    publishApiPath = os.path.join(_SUBFUNC_DIR, "publishApi.py")
    if os.path.isfile(publishApiPath):
        apiKeys, apiFuncs = _getCmdMapKeys(publishApiPath)
        if sorted(apiKeys) != ["publishpush"]:
            errList.append(f"publishApi CMD_MAP 应为 ['publishpush'], 实为 {sorted(apiKeys)}")
        apiText = readText(publishApiPath)
        if "PLACEHOLDER_CMD_LIST = []" not in apiText:
            errList.append("publishApi 占位清单未清空(publishpush 已实现)")
        if "publishService" not in apiText:
            errList.append("publishApi 未真实引用 publishService")
        undefinedList = sorted(set(apiFuncs) - set(_getTopLevelDefNames(publishApiPath)))
        if undefinedList:
            errList.append(f"publishApi 注册表指向未定义函数: {undefinedList}")
    else:
        errList.append("subfunc/publishApi.py 缺失")

    #6) 平台红线: 小红书投递/发布代码路径不得存在
    for relPath in XHS_PUBLISH_SCAN_FILE_LIST:
        filePath = os.path.join(_SRC_DIR, relPath)
        if not os.path.isfile(filePath):
            continue
        text = readText(filePath)
        for token in XHS_PUBLISH_FORBIDDEN_TOKEN_LIST:
            if token in text:
                errList.append(f"{relPath} 出现小红书发布路径痕迹: {token}")
    #publishService 必须显式把小红书列为不可投递, 且 wechat_mp 为唯一可投递平台
    if os.path.isfile(publishPath):
        text = readText(publishPath)
        if '"xiaohongshu"' not in text:
            errList.append("publishService 未把 xiaohongshu 列入不可投递平台(平台红线)")
        if "NON_DELIVERABLE_PLATFORM_LIST" not in text:
            errList.append("publishService 缺少 NON_DELIVERABLE_PLATFORM_LIST")
    #wechatMp 的通道调用必须止于草稿箱(draft/add), 正式发布须 publishService 三重闸门
    wechatPath = os.path.join(PLATFORM_ADAPTER_DIR, "wechatMp.py")
    if os.path.isfile(wechatPath):
        wText = readText(wechatPath)
        for token in ["draftAdd", "freePublishSubmit", "materialAdd", "uploadImg", "fetchAccessToken"]:
            if token not in wText:
                errList.append(f"wechatMp 通道原语缺失: {token}")
        for token in ["NON_DELIVERABLE_PLATFORM_LIST", "from processor import publishService",
                      "import publishService"]:
            if token in wText:
                errList.append(f"wechatMp 不应承载业务编排: {token}")

    #7) 投递类错误码(F 段)必须在 contenthub 消息表中真实存在
    errMsgPath = os.path.join(_SRC_DIR, "common", "errMsgCommon.py")
    if os.path.isfile(errMsgPath):
        try:
            errNs = _execStandaloneModule(errMsgPath, "common.errMsgCommon")
            wordList = (errNs.get("CONST_ERROR_wordList") or {}).get("contenthub", {}).get("CN", {})
            missCode = [code for code in PUBLISH_ERR_CODE_LIST if code not in wordList]
            if missCode:
                errList.append(f"contenthub 消息表缺少投递错误码: {missCode}")
        except Exception as e:
            errList.append(f"errMsgCommon 独立执行失败: {e}")

    detail = "; ".join(errList[:8]) if errList else "; ".join(detailList)
    record("S26 SP4a 投递链路(凭据/幂等/确认/撤销窗/合规/审计/红线)", not errList, detail)


#===== SP4b(素材包 ZIP + MCP 接入 + 凭据巡检) begin =====

#SP4b 期望: ZIP 内固定文本条目(主计划 7.8 第 3/4/6/7/8/11 项)
SP4B_ZIP_TEXT_ENTRY_LIST = [
    "title.txt", "content.txt", "manifest.json",
    "COPYRIGHT.txt", "RISK_NOTICE.txt", "SWIPE_TIPS.txt",
]

#SP4b 期望: MCP 只读工具(8 个, 与 mcpapi/mcpPost.py::toolPathMap / mcp_entry.py 的 @mcp.tool() 一致)
SP4B_MCP_TOOL_LIST = [
    "search_topics", "get_topic", "list_topic_assets", "list_layouts",
    "list_platforms", "get_render_job", "list_artifacts", "list_publish_records",
]

#SP4b 新增/校验的 MCP 错误码(G 段)
SP4B_MCP_ERR_CODE_LIST = ["G0", "G1", "G2", "G3"]

#端点总数不变式(SP1.5 起固定; SP4b 不新增 CMD)
#★ 2026-09-20: 账号域补齐管理员专用 useradd/usermodify/userdel, 69 -> 72(19 + 5 + 48)
SP4B_ENDPOINT_TOTAL = 72


def checkArtifactPackAndMcp():
    """S27 SP4b(素材包 ZIP + MCP 接入 + 凭据巡检)静态校验:
       - 素材包 ZIP: 7.8 条目齐备 / 风险告知与滑动提示文本落地 / **未过合规校验不得出包**(闸门先于打包) /
         合规规则单一来源(**不重写** base.checkPlatformSpec / xiaohongshu.validateSwipeSpec) /
         只经 fileStorageCommon 上传(无厂商分支) / **静态扫描确认无投递-发布路径**;
       - assetApi: artifactpack 由占位替换为真实实现, 素材域占位清空(**不新增 CMD**);
       - MCP 薄入口: mcpApi.mcpinvoke 只做「鉴权 + 路由 + 经 chServerCommon 转发」(**不承载协议解析**),
         ROLE_CMD_LIST / MCP_TOOL_LIST 校验落点齐备, G0/G1/G2/G3 错误码存在;
         mcpapi/ 既有只读层未被改动(8 tool + 3 resource 仍在), **监听端口固定 8891**
         (配置取值 + 不得硬编码; ★ 本轮不联调, 故服务端 401/拒绝两项不在冒烟内执行);
       - 凭据巡检: credentialCheck healthStatus 四态 + R-03 分级告警(INFO/WARN/ERROR) +
         公众号探活复用 publishService 凭据解密 + 小红书跳过说明 + 只读探活(不投递);
         accounthealth 端点在同一处理函数内接入巡检(**不新增 CMD**);
       - 端点总数仍 69(聚合器实测口径的静态等价检查)。"""
    errList = []
    detailList = []

    artifactPath = os.path.join(_SRC_DIR, "processor", "artifactService.py")
    assetApiPath = os.path.join(_SUBFUNC_DIR, "assetApi.py")
    mcpApiPath = os.path.join(_SUBFUNC_DIR, "mcpApi.py")
    mcpPostPath = os.path.join(_SRC_DIR, "mcpapi", "mcpPost.py")
    mcpEntryPath = os.path.join(_SRC_DIR, "mcpapi", "mcp_entry.py")
    credCheckPath = os.path.join(_SRC_DIR, "schedule", "credentialCheck.py")
    accountApiPath = os.path.join(_SUBFUNC_DIR, "accountApi.py")

    for path in (artifactPath, mcpApiPath, credCheckPath):
        if not os.path.isfile(path):
            errList.append(f"SP4b 交付文件缺失: {os.path.relpath(path, _SRC_DIR)}")
    if errList:
        record("S27 SP4b 素材包 ZIP / MCP 接入 / 凭据巡检", False, "; ".join(errList[:6]))
        return

    #----- 1) 素材包 ZIP 导出(processor/artifactService.py) -----
    artifactNames = collectTopLevelNames(artifactPath)
    for token in ["exportAssetPack", "loadReadyArtifactRecords", "materializeProduct",
                  "runCompliance", "buildImageEntryName", "buildManifest", "writeZipPackage",
                  "buildTitleText", "buildContentText", "buildCopyrightText",
                  "buildRiskNoticeText", "buildSwipeTipsText", "combineCheckSum",
                  "ZIP_TEXT_ENTRY_LIST", "ZIP_STRUCTURE_SPEC", "RISK_NOTICE_TEXT", "SWIPE_TIPS_TEXT"]:
        if token not in artifactNames:
            errList.append(f"artifactService 缺少符号: {token}")

    artifactText = readText(artifactPath)
    #7.8 条目齐备
    for entry in SP4B_ZIP_TEXT_ENTRY_LIST:
        if entry not in artifactText:
            errList.append(f"ZIP 条目缺失: {entry}")
    #风险告知 / 滑动提示 文本(7.8 第 8/11 项)
    for token in ["官方创作服务平台", "禁止第三方自动发布", "图片显示区域", "8.0"]:
        if token not in artifactText:
            errList.append(f"风险告知/滑动提示缺少关键文本: {token}")
    #合规规则单一来源(禁止第二张规则表)
    for forbidden in ["def checkPlatformSpec(", "def validateSwipeSpec("]:
        if forbidden in artifactText:
            errList.append(f"artifactService 重写了规格规则表(违反单一来源): {forbidden}")
    if "complianceService" not in artifactText:
        errList.append("artifactService 未复用 complianceService(合规闸门)")
    #文件只经门面(红线 R2)
    if "fileStorageCommon" not in artifactText:
        errList.append("artifactService 未经 fileStorageCommon 上传")
    if re.search(r"if\s+[^\n]*FILE_SYSTEM_MODE\s*==", artifactText):
        errList.append("artifactService 出现厂商分支判断(违反 R2)")
    #★ 未过合规校验不得出包: 合规闸门必须在 ZIP 组装之前
    gatePos = artifactText.find("runCompliance(")
    zipPos = artifactText.find("writeZipPackage(")
    if gatePos < 0 or zipPos < 0 or gatePos > zipPos:
        errList.append("合规闸门未先于 ZIP 组装(未过校验可能仍出包)")
    if "拒绝出包" not in artifactText:
        errList.append("artifactService 缺少「未过校验拒绝出包」的显式分支")
    #★ 只导出不投递: 静态扫描确认无投递/发布路径(仅扫代码, 注释中的「不得出现 xxx」不误判)
    artifactCode = stripComments(artifactText)
    for forbidden in ["publishService", "freepublish", "draft/add", "submitFreePublish", "deliver("]:
        if forbidden in artifactCode:
            errList.append(f"artifactService 疑似投递/发布路径: {forbidden}")
    #分层: 业务层不得反向依赖接入层
    if re.search(r"^\s*(from|import)\s+(main|subfunc)\b", artifactText, re.M):
        errList.append("artifactService 反向依赖接入层(main/subfunc)")

    #assetApi: artifactpack 已实现且占位清空
    assetText = readText(assetApiPath)
    if "artifactService.exportAssetPack" not in assetText:
        errList.append("assetApi.funcArtifactPack 未走 artifactService.exportAssetPack")
    if "PLACEHOLDER_CMD_LIST = []" not in assetText:
        errList.append("assetApi 占位清单未清空(artifactpack 应已落地)")
    if "genNotImplementedResult" in assetText:
        errList.append("assetApi 仍保留未实现占位返回")
    detailList.append("artifactpack=已实现")

    #----- 2) MCP 薄入口(main/subfunc/mcpApi.py) -----
    mcpText = readText(mcpApiPath)
    for token in ["TOOL_CMD_MAP", "chServerCommon", "settings.ROLE_CMD_LIST", "MCP_TOOL_LIST",
                  "getSessionInfo", "ChServer"]:
        if token not in mcpText:
            errList.append(f"mcpApi 薄入口缺少要素: {token}")
    #★ 只转发, 不承载协议解析(仅扫代码, 注释中的「不得出现 xxx」不误判)
    mcpCode = stripComments(mcpText)
    for forbidden in ["jsonrpc", "tools/call", "FastMCP", "mcp.server", "toolPathMap"]:
        if forbidden in mcpCode:
            errList.append(f"mcpApi 疑似承载 MCP 协议解析: {forbidden}")
    #错误码落点(G0/G1/G2/G3)
    for code in SP4B_MCP_ERR_CODE_LIST:
        if f'"{code}"' not in mcpText:
            errList.append(f"mcpApi 缺少错误码落点: {code}")
    if "PLACEHOLDER_CMD_LIST = []" not in mcpText:
        errList.append("mcpApi 占位清单未清空(mcpinvoke 应已落地)")
    #工具路由与 MCP 层一致(8 个只读工具)
    mcpPostText = readText(mcpPostPath)
    for tool in SP4B_MCP_TOOL_LIST:
        if tool not in mcpText or tool not in mcpPostText:
            errList.append(f"mcpApi/mcpPost 工具名不一致: {tool}")

    #mcpapi/ 既有只读层未被改动(8 tool + 3 resource)
    mcpEntryText = readText(mcpEntryPath)
    if mcpEntryText.count("@mcp.tool()") != len(SP4B_MCP_TOOL_LIST):
        errList.append(f"mcp_entry tool 数 != {len(SP4B_MCP_TOOL_LIST)}")
    if mcpEntryText.count("@mcp.resource(") != 3:
        errList.append("mcp_entry resource 数 != 3")
    for uri in ["contenthub://platforms", "contenthub://layouts", "contenthub://topic/{topic_id}"]:
        if uri not in mcpEntryText:
            errList.append(f"mcp_entry 缺少 resource: {uri}")
    if "_genAllowedTools" not in mcpPostText or "CHTokenVerifier" not in mcpPostText:
        errList.append("mcpPost 鉴权/工具授权实现缺失")
    #★ SP4b: MCP 监听端口固定 8891(本轮不联调, 由配置 + 本项静态断言锁定), 且端口不得硬编码在 mcp_entry
    mcpConfigPath = os.path.join(_SRC_DIR, "config", "mcpConfig.py")
    mcpConfigText = readText(mcpConfigPath)
    if "MCP_SERVER_PORT = 8891" not in mcpConfigText:
        errList.append("mcpConfig.MCP_SERVER_PORT 应为 8891")
    if 'MCP_TRANSPORT = "streamable-http"' not in mcpConfigText:
        errList.append("mcpConfig.MCP_TRANSPORT 应为 streamable-http")
    if "port=mcpConfig.MCP_SERVER_PORT" not in mcpEntryText:
        errList.append("mcp_entry 未从 mcpConfig 取监听端口(禁止硬编码端口)")
    if "8891" in mcpEntryText:
        errList.append("mcp_entry 出现硬编码端口 8891(应取 mcpConfig.MCP_SERVER_PORT)")
    detailList.append("mcp: 8 tool + 3 resource, port=8891(不联调)")

    #----- 3) 凭据健康巡检(schedule/credentialCheck.py) -----
    credNames = collectTopLevelNames(credCheckPath)
    for token in ["checkAccount", "runOnce", "main", "decideHealthStatus", "acquireCheckLock",
                  "releaseCheckLock", "fetchAccountList",
                  "HEALTH_OK", "HEALTH_EXPIRING", "HEALTH_INVALID", "HEALTH_UNKNOWN",
                  "ALERT_LEVEL_MAP", "PROBE_PLATFORM_LIST", "SKIP_PLATFORM_NOTE_MAP"]:
        if token not in credNames:
            errList.append(f"credentialCheck 缺少符号: {token}")

    credText = readText(credCheckPath)
    #healthStatus 四态 + R-03 分级告警
    for level in ['"INFO"', '"WARN"', '"ERROR"']:
        if level not in credText:
            errList.append(f"credentialCheck 缺少告警级别: {level}")
    #公众号探活复用 C6 凭据解密与健康回写; 小红书跳过并说明
    for token in ["publishService.decryptAccountCredential", "publishService.markAccountHealth",
                  "fetchAccessToken", "xiaohongshu"]:
        if token not in credText:
            errList.append(f"credentialCheck 缺少要素: {token}")
    #只读探活: 巡检不得投递/发布
    for forbidden in ["publishPush", "freepublish", "draft/add", "deliver("]:
        if forbidden in credText:
            errList.append(f"credentialCheck 疑似投递/发布路径: {forbidden}")
    #Redis 锁可降级
    if "redisMainDB" not in credText or "degraded" not in credText:
        errList.append("credentialCheck 缺少 Redis 锁降级路径")
    #分层: 调度层不得依赖接入层
    if re.search(r"^\s*(from|import)\s+(main|subfunc)\b", credText, re.M):
        errList.append("credentialCheck 依赖接入层(main/subfunc)")
    #accounthealth 端点内接入(不新增 CMD)
    accountText = readText(accountApiPath)
    if "credentialCheck" not in accountText:
        errList.append("accounthealth 未接入凭据巡检")
    if 'action in ("check", "refresh", "probe")' not in accountText:
        errList.append("accounthealth 缺少巡检触发条件(action)")
    accountKeys, _ = _getCmdMapKeys(accountApiPath)
    if sorted(accountKeys) != sorted(ACCOUNT_CMD_LIST):
        errList.append("accountApi CMD_MAP 发生变化(不得新增/删减 CMD)")
    detailList.append("credentialCheck=已接入 accounthealth")

    #----- 4) 端点不变式(仍 69; 不新增 CMD) -----
    domainTotal = 0
    for domain, cmdList in BIZ_CMD_DOMAIN_MAP.items():
        keys, _ = _getCmdMapKeys(os.path.join(_SUBFUNC_DIR, f"{domain}Api.py"))
        domainTotal += len(keys)
        if sorted(keys) != sorted(cmdList):
            errList.append(f"{domain}Api CMD_MAP 应为 {cmdList}, 实为 {keys}")
    crudKeys, _ = _getCmdMapKeys(os.path.join(_SUBFUNC_DIR, "crudApi.py"))
    domainTotal += len(accountKeys) + len(crudKeys)
    if domainTotal != SP4B_ENDPOINT_TOTAL:
        errList.append(f"端点总数 {domainTotal} != {SP4B_ENDPOINT_TOTAL}(端点基数不变式)")
    detailList.append(f"CMD total={domainTotal}")

    #G 段错误码真实存在(errMsgCommon 独立执行)
    try:
        errMsgPath = os.path.join(_SRC_DIR, "common", "errMsgCommon.py")
        errNs = _execStandaloneModule(errMsgPath, "common.errMsgCommon")
        wordList = (errNs.get("CONST_ERROR_wordList") or {}).get("contenthub", {}).get("CN", {})
        missCode = [code for code in SP4B_MCP_ERR_CODE_LIST if code not in wordList]
        if missCode:
            errList.append(f"contenthub 消息表缺少 MCP 错误码: {missCode}")
    except Exception as e:
        errList.append(f"errMsgCommon 独立执行失败: {e}")

    detail = "; ".join(errList[:8]) if errList else "; ".join(detailList)
    record("S27 SP4b 素材包 ZIP / MCP 接入 / 凭据巡检", not errList, detail)

#===== SP4b end =====


#===== SP4c(归档清理 + 监控告警 + 巡检守护化) begin =====

#SP4c 交付文件
OPS_SETTINGS_PATH = "config/opsSettings.py"
ARCHIVE_PATH = "schedule/archive.py"

#★ SP4c 监控核心包: 原名 monitor/, 本轮为接收 museum/code/src/monitor 迁移改造代码, 重命名为 chmonitor/
CHMONITOR_FILE_LIST = [
    "chmonitor/__init__.py", "chmonitor/metrics.py", "chmonitor/alertChannel.py",
    "chmonitor/heartbeat.py", "chmonitor/monitorService.py", "chmonitor/dailyCheck.py",
]

#★ monitor/: 由 museum/code/src/monitor 迁移并改造为 contentHub 口径(零网络)的运维监控/守护层
MUSEUM_MONITOR_FILE_LIST = [
    "monitor/__init__.py", "monitor/monitor.py", "monitor/alert.py", "monitor/monitorConfig.py",
]

#★ S23 零网络扫描同步纳入 chmonitor/ 与 monitor/(告警通道为占位实现; 迁移代码已剥离网络原语)
MONITOR_ZERO_NETWORK_FILE_LIST = CHMONITOR_FILE_LIST + MUSEUM_MONITOR_FILE_LIST

#★ 迁移改造必须剥离的 museum 依赖与原语(mu_ 前缀业务表 / museum 专属配置 / 网络与子进程原语)
MUSEUM_DEP_FORBIDDEN_TOKEN_LIST = [
    "museumSettings", "mu_crawl_run_log", "mu_translation_task", "subprocess",
]

#七项监控指标名(与 chmonitor/metrics.py 常量一致; 主计划 8.7 监控告警阈值表)
SP4C_METRIC_NAME_LIST = [
    "render_failure_rate", "publish_success_rate", "render_queue_backlog",
    "credential_health", "storage_usage", "scheduler_last_success", "audit_daily_growth",
]

#指标判定纯函数名(边界值分级; 冒烟同步验证)
SP4C_METRIC_EVALUATOR_LIST = [
    "evaluateRenderFailureRate", "evaluatePublishSuccessRate", "evaluateQueueBacklog",
    "evaluateCredentialHealth", "evaluateStorageUsage", "evaluateSchedulerLastSuccess",
    "evaluateAuditDailyGrowth",
]

#告警级别(INFO/WARN/ERROR)
SP4C_LEVEL_LIST = ["INFO", "WARN", "ERROR"]

#opsSettings 必须齐备的可配项(阈值/保留期/批大小一律可配, 禁止散落硬编码)
SP4C_OPS_CONFIG_TOKEN_LIST = [
    "ARCHIVE_AUDIT_RETAIN_MONTHS_ENV_KEY", "DEFAULT_ARCHIVE_AUDIT_RETAIN_MONTHS",
    "ARCHIVE_BATCH_SIZE_ENV_KEY", "DEFAULT_ARCHIVE_BATCH_SIZE",
    "ARCHIVE_EXPORT_FORMAT_ENV_KEY", "ARCHIVE_EXECUTE_ENV_KEY", "DEFAULT_ARCHIVE_EXECUTE",
    "getAuditRetainMonths", "getBatchSize", "getExportFormat", "isExecuteEnabled",
    "MONITOR_RENDER_FAILURE_RATE", "MONITOR_PUBLISH_FAILURE_RATE", "MONITOR_QUEUE_BACKLOG_MINUTES",
    "MONITOR_STORAGE_USAGE_RATE", "MONITOR_SCHEDULE_GRACE_FACTOR", "MONITOR_AUDIT_GROWTH_FACTOR",
    "MONITOR_METRIC_TABLE", "MONITOR_SCHEDULE_PERIOD_TABLE", "MONITOR_ALERT_CHANNEL",
]

#archive 关键要素(dry-run 默认 / 显式确认 / 强顺序 / 审计留痕 / 降级锁)
SP4C_ARCHIVE_TOKEN_LIST = [
    "def isDryRun", "--execute", "CH_ARCHIVE_EXECUTE", "dryRun",
    "exportAuditBatch", "delete_ch_audit_log", "saveFile",
    "ARTIFACT_STATUS_EXPIRED", "delFile", "writeAudit",
    "query_ch_artifact", "expireBeforeYMDHMS", "redisMainDB", "degraded",
]

#归档/监控不得出现的投递-发布路径(小红书红线延续)
SP4C_FORBIDDEN_DELIVER_TOKEN_LIST = [
    "publishPush", "freepublish", "draft/add", "submitFreePublish", "deliver(",
]

#守护化入口要素(credentialCheck --loop 单实例)
SP4C_GUARD_TOKEN_LIST = ["--loop", "--interval", "heartbeat", "alertChannel"]


def checkArchiveAndMonitor():
    """S28 SP4c(归档清理 + 监控告警 + 巡检守护化)静态校验:
       - archive.py: **默认 dry-run**(未显式确认只打印清单) / 真删需 --execute 或 CH_ARCHIVE_EXECUTE=1 /
         **先导出上传成功再删除**(源序: exportAuditBatch&saveFile 先于 delete_ch_audit_log) /
         产物清理**先置 EXPIRED 再 delFile** / 分批与保留期可配 / 归档-清理动作写 ch_audit_log / Redis 锁可降级;
       - opsSettings.py: 保留期/批大小/七项阈值/告警通道全部可配(含 os.environ.get);
       - chmonitor/ (原 monitor/, 本轮重命名): 七项指标名与判定纯函数齐备 + INFO/WARN/ERROR +
         告警通道为占位且无网络调用 + 每日巡检入口;
       - monitor/ (由 museum/code/src/monitor 迁移改造): 文件齐备 + **零网络** + 已剥离 museum 专属依赖
         (mu_ 前缀业务表 / museum 配置)与子进程原语 + 复用 chmonitor;
       - credentialCheck: 守护化入口(--loop/--interval 单实例)且告警对接 chmonitor;
       - 红线: 无投递/发布路径; chmonitor/monitor 不反向依赖 main/subfunc。"""
    errList = []
    detailList = []

    #1) 文件齐备(chmonitor 监控核心 + monitor 迁移层)
    for relPath in [OPS_SETTINGS_PATH, ARCHIVE_PATH] + CHMONITOR_FILE_LIST + MUSEUM_MONITOR_FILE_LIST:
        if not os.path.isfile(os.path.join(_SRC_DIR, relPath)):
            errList.append(f"{relPath} 缺失")

    #2) archive.py 关键要素与强顺序
    archivePath = os.path.join(_SRC_DIR, ARCHIVE_PATH)
    if os.path.isfile(archivePath):
        archiveText = readText(archivePath)
        for token in SP4C_ARCHIVE_TOKEN_LIST:
            if token not in archiveText:
                errList.append(f"archive.py 缺少要素: {token}")
        #默认 dry-run 显式落点
        if "isDryRun" not in archiveText or "DRY-RUN" not in archiveText:
            errList.append("archive.py 未体现默认 dry-run")
        #★ 强顺序: 先导出(含上传)成功 -> 再删除
        exportIdx = archiveText.find("exportAuditBatch(")
        saveIdx = archiveText.find("comFS.saveFile(")
        deleteIdx = archiveText.find("delete_ch_audit_log(")
        if -1 in (exportIdx, saveIdx, deleteIdx):
            errList.append("archive.py 缺少导出/上传/删除落点(强顺序无法校验)")
        elif not (exportIdx < deleteIdx and saveIdx < deleteIdx):
            errList.append("archive.py 顺序错误: 必须先导出上传成功, 再删除")
        #★ 产物清理: 先置 EXPIRED 再 delFile
        expireIdx = archiveText.find("ARTIFACT_STATUS_EXPIRED")
        delFileIdx = archiveText.find("comFS.delFile(")
        if expireIdx < 0 or delFileIdx < 0 or expireIdx > delFileIdx:
            errList.append("archive.py 顺序错误: 产物清理必须「先置 EXPIRED 再 delFile」")
        #审计留痕
        if "auditService.writeAudit" not in archiveText or "ACTION_ARCHIVE" not in archiveText:
            errList.append("archive.py 归档/清理动作未写 ch_audit_log(审计留痕缺失)")
        #投递/发布红线
        for forbidden in SP4C_FORBIDDEN_DELIVER_TOKEN_LIST:
            if forbidden in archiveText:
                errList.append(f"archive.py 疑似投递/发布路径: {forbidden}")
        #分层
        _checkNoReverseImport(archivePath, ARCHIVE_PATH, errList, forbiddenModules = ("main", "subfunc"))
        detailList.append("archive=ok")

    #3) opsSettings.py 可配项齐备
    opsPath = os.path.join(_SRC_DIR, OPS_SETTINGS_PATH)
    if os.path.isfile(opsPath):
        opsText = readText(opsPath)
        for token in SP4C_OPS_CONFIG_TOKEN_LIST:
            if token not in opsText:
                errList.append(f"opsSettings.py 缺少可配项: {token}")
        if "os.environ.get" not in opsText:
            errList.append("opsSettings.py 未通过环境变量开放配置(不可配)")
        detailList.append("opsSettings=ok")

    #4) chmonitor/ 七项指标 + 级别 + 告警通道占位 + 每日巡检入口
    metricsText = readText(os.path.join(_SRC_DIR, "chmonitor", "metrics.py")) \
        if os.path.isfile(os.path.join(_SRC_DIR, "chmonitor", "metrics.py")) else ""
    for metricName in SP4C_METRIC_NAME_LIST:
        if metricName not in metricsText:
            errList.append(f"chmonitor/metrics.py 缺少指标: {metricName}")
    for funcName in SP4C_METRIC_EVALUATOR_LIST:
        if f"def {funcName}(" not in metricsText:
            errList.append(f"chmonitor/metrics.py 缺少判定纯函数: {funcName}")
    for level in SP4C_LEVEL_LIST:
        if f'"{level}"' not in metricsText:
            errList.append(f"chmonitor/metrics.py 缺少告警级别: {level}")
    if "MONITOR_METRIC_TABLE" not in metricsText:
        errList.append("chmonitor/metrics.py 未取自可配阈值表(MONITOR_METRIC_TABLE)")

    alertText = readText(os.path.join(_SRC_DIR, "chmonitor", "alertChannel.py")) \
        if os.path.isfile(os.path.join(_SRC_DIR, "chmonitor", "alertChannel.py")) else ""
    for token in ["LogAlertChannel", "EmailAlertChannel", "WeComAlertChannel", "ALERT_CHANNEL_MAP",
                  "NETWORK_REQUEST_NO"]:
        if token not in alertText:
            errList.append(f"chmonitor/alertChannel.py 缺少要素: {token}")
    #占位通道不发网络请求
    if 'NETWORK_REQUEST_NO = "0"' not in alertText:
        errList.append("chmonitor/alertChannel.py 占位通道网络标记应为 \"0\"")
    for token in NETWORK_FORBIDDEN_TOKEN_LIST:
        if token in alertText:
            errList.append(f"chmonitor/alertChannel.py 出现网络调用痕迹: {token}")

    dailyText = readText(os.path.join(_SRC_DIR, "chmonitor", "dailyCheck.py")) \
        if os.path.isfile(os.path.join(_SRC_DIR, "chmonitor", "dailyCheck.py")) else ""
    if "runDailyCheck" not in dailyText or '__main__' not in dailyText:
        errList.append("chmonitor/dailyCheck.py 缺少每日巡检入口(runDailyCheck/__main__)")

    #★ monitor/(museum 迁移改造层): 零网络 + 已剥离 museum 依赖与子进程原语 + 复用 chmonitor
    monitorText = ""
    for relPath in MUSEUM_MONITOR_FILE_LIST:
        filePath = os.path.join(_SRC_DIR, relPath)
        if not os.path.isfile(filePath):
            continue
        oneText = readText(filePath)
        monitorText += oneText
        for token in NETWORK_FORBIDDEN_TOKEN_LIST:
            if token in oneText:
                errList.append(f"{relPath} 出现网络调用痕迹: {token}(迁移改造应已剥离)")
        for token in MUSEUM_DEP_FORBIDDEN_TOKEN_LIST:
            if token in oneText:
                errList.append(f"{relPath} 残留 museum 依赖/子进程原语: {token}")
    #★ monitor/ 复用 chmonitor(改造口径: 监控核心在 chmonitor, monitor 只做守护/汇总)
    if "chmonitor" not in monitorText:
        errList.append("monitor/ 未复用 chmonitor(迁移改造口径不完整)")
    #★ 迁移来源登记
    if "museum" not in monitorText:
        errList.append("monitor/ 未登记迁移来源(museum)")

    #chmonitor / monitor 不得反向依赖接入层; 且不 import subfunc
    for relPath in CHMONITOR_FILE_LIST + MUSEUM_MONITOR_FILE_LIST:
        filePath = os.path.join(_SRC_DIR, relPath)
        if os.path.isfile(filePath):
            _checkNoReverseImport(filePath, relPath, errList, forbiddenModules = ("main", "subfunc"))
    detailList.append("chmonitor=ok")
    detailList.append("monitor(museum 迁移改造)=ok")

    #5) credentialCheck 守护化入口(单实例 --loop) + 告警对接
    credPath = os.path.join(_SRC_DIR, "schedule", "credentialCheck.py")
    if os.path.isfile(credPath):
        credText = readText(credPath)
        for token in SP4C_GUARD_TOKEN_LIST:
            if token not in credText:
                errList.append(f"credentialCheck.py 缺少守护化要素: {token}")
        if "heartbeat.recordRun" not in credText:
            errList.append("credentialCheck.py 未刷新定时任务心跳")
    detailList.append("guard=ok")

    detail = "; ".join(errList[:8]) if errList else "; ".join(detailList)
    record("S28 SP4c 归档清理 / 监控告警 / 巡检守护化", not errList, detail)

#===== SP4c end =====


def main():
    print(f"[static] srcDir:{_SRC_DIR}")

    checkCompile()
    checkTableDefFiles()
    checkGenerateProducts()
    checkCrudTitleAlignment()
    checkMysqlCommon()
    checkGlobalDefinition()
    checkChCommon()
    checkConfigGap()
    checkTools()
    checkCrossModuleReferences()
    checkDelFlagConvention()

    #SP1.5(S2 拆分结构) 结构校验
    checkWebEntryStructure()
    checkSubfuncNoCircularImport()
    checkCrudApiCoverage()
    checkAggregatorValidations()
    checkErrMsgModule()
    checkAggregateCoverage()

    #SP1.5 追加: 外部既有表移植(user_basic / weixin_pay)
    checkPortTables()

    #SP2a 追加: C2 主题管理(topicService + topicApi 接管)
    checkTopicService()

    #SP2b 追加: C3 素材图库(assetService + assetApi 接管)
    checkAssetService()

    #SP2c 追加: C4 版式引擎(engine + 4 套模板 + topicrender 归属迁移)
    checkRenderEngine()

    #SP3a 追加: C5 平台适配层(platformAdapter + inlineStyle + topicrender platform 分支)
    checkPlatformAdapter()

    #SP3b 追加: C5 小红书产物渲染(htmlToImage 截图管线 + xiaohongshu 适配器, 从 C7 迁移)
    checkXiaohongshuRender()

    #SP3c 追加: C8 合规校验 + ch_artifact 产物台账 + ch_render_job 渲染任务化
    checkComplianceAndLedger()

    #SP4a 追加: C6 投递链路(凭据加密 / 幂等·二次确认·撤销窗 / 合规闸门 / 审计 / 平台红线)
    checkPublishDelivery()

    #SP4b 追加: 素材包 ZIP(artifactpack) + MCP 薄入口(mcpinvoke) + 凭据健康巡检(credentialCheck)
    checkArtifactPackAndMcp()

    #SP4c 追加: 归档清理(archive) + 监控告警(monitor/) + 巡检守护化(credentialCheck --loop)
    checkArchiveAndMonitor()

    failList = [name for name, ok, _ in _resultList if not ok]
    print(f"[static] done: total={len(_resultList)}, pass={len(_resultList) - len(failList)}, fail={len(failList)}")
    if failList:
        print(f"[static] failed items: {', '.join(failList)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
