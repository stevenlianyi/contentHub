# 内容中枢（content-hub）· Phase 0 落地任务清单

> **用途**：直接交给 codeBuddy 执行的 Phase 0 工单。设计底稿见 `content-hub-开发计划v3.md` / `.html`，参考基线为 `ylwzProject/museum`。
> **目标里程碑 M0**：12 张 `ch_*` 表定义文件 + 生成器跑通 + 文件存储抽象层冻结。
> **周期**：1–2 周。**Day 1 必须并行启动企业号认证（外部审核 2–4 周，非阻塞主干）。**

---

## 0. 预读与前提

**必读**
- `content-hub-开发计划v3.md` 第 4 节（文件系统抽象）、第 5 节（数据库设计）、第 6 节（CRUD 生成方案）、第 7 节（目录结构）
- 参考基线 `D:\StevenLianData\0301. Private Project\ylwzProject\museum\code\src` 下的：`common/{mysqlHandle,funcCommon,miscCommon,globalDefinition,redisCommon,aliyunOSS,tencentCOS,selfFileCommon}.py`、`database/mysqlCodeGenerator.py`

**环境**
- Python 3.13（managed）
- MySQL 8.0（utf8mb4 / utf8mb4_unicode_ci / InnoDB）
- 复用的 common 层直接搬 ylwz，不重写

**三条红线（贯穿全程）**
1. 数据库结构以 `ch_*.txt` 为唯一数据源，业务层禁止裸 SQL。
2. 文件后端配置驱动：`FILE_SYSTEM_MODE` ∈ {ALIOSS, TENCENT, SELFFILE}，代码不得出现硬编码分支。
3. 生成器**只走 `readFromFile()` 路径**（`-i xx.txt`），绝不走 `handleSQL()`（参数错位坑，见 T5 备注）。

---

## T1 · 目录骨架

按 v3 第 7 节建好 `code/src/` 下空目录（文件在后续任务填充）：

```bash
cd code/src
mkdir -p common config database/auto_generated engine/templates/{stack_v1,carousel_v1,longimage_v1,swipe_v1} \
         processor/platformAdapter schedule monitor tools test \
         main
```

**验收**：目录存在即可，不要求有内容。

---

## T2 · 复用层搬运（ylwz → 本项目 common/）

从 `ylwzProject/museum/code/src/common/` 复制以下文件到本项目 `common/`，**原样复用，不改动逻辑**：

| 源文件 | 目标 | 备注 |
|---|---|---|
| `mysqlHandle.py` | `common/mysqlHandle.py` | 连接池 executeRead/executeWrite |
| `funcCommon.py` | `common/funcCommon.py` | genDigest / rtnMSG / fileServerRequest |
| `miscCommon.py` | `common/miscCommon.py` | getTime / setLogNew / jsonLoads |
| `globalDefinition.py` | `common/globalDefinition.py` | 全局常量 |
| `redisCommon.py` | `common/redisCommon.py` | 查询缓冲 |
| `aliyunOSS.py` | `common/aliyunOSS.py` | ALIOSS 适配器（6 方法） |
| `tencentCOS.py` | `common/tencentCOS.py` | TENCENT 适配器（6 方法） |
| `selfFileCommon.py` | `common/selfFileCommon.py` | SELFFILE 适配器（6 方法） |

同时把 `ylwzProject/museum/code/src/database/mysqlCodeGenerator.py` 复制到本项目 `database/mysqlCodeGenerator.py`（**不要修改生成器**）。

新增空占位（Phase 0 先建文件，内容后续填）：
- `common/fileStorageCommon.py`（T6 填）
- `common/chCommon.py`（本项目公共封装，对齐 museumCommon）
- `common/accountClient.py`（账号服务客户端，对齐 acis）

**验收**：`import` 以上模块无报错（依赖 config，T3 后验证）。

---

## T3 · 配置文件（config/ 七文件）

新建 `code/src/config/` 下文件。关键项：

**`local_settings.py`**（环境入口）
```python
_SYS = "local"                 # local | server_01 | server_02 | test_server | home
_SYS_SERVER_NAME = "chserver_01"
```

**`basicSettings.py`**（全局开关，含 FILE_SYSTEM_MODE 映射 + 图片规格 + 角色裁剪）
```python
FILE_SYSTEM_MODE = {
    "local":       "SELFFILE",
    "server_01":   "ALIOSS",
    "server_02":   "TENCENT",
    "test_server": "SELFFILE",
    "home":        "SELFFILE",
}[_SYS]

LOCAL_FILE_SERVER_PATH = {...}[_SYS]   # http://host:9000/temp/
LOCAL_FILE_SERVER_BASE = {...}[_SYS]   # /data/webserver/temp/
LOCAL_FILE_TEMP_WEB_DIR = "web/"

MAX_PIC_SIZE   = (1920, 1920)
THUMBNAIL_SIZE = (640, 640)
ALLOW_FILE_TYPE_LIST = [".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4"]

# 角色裁剪：administrator / manager 全权；operator 主题素材全权+账号只读；customer 全只读；visitor 仅 platform/layout/artifact 只读
ROLE_CMD_LIST = { ... }   # 见 v3 §6.6
NO_SESSIONID_CMD_LIST = ["platformqry", "layoutqry", "artifactqry"]
```

**`aliyunSettings.py` / `tencentSettings.py` / `selfFileSettings.py`**（各持 AK/bucket/根目录，按 `_SYS` 映射；`selfFileSettings` 含 `LOCAL_FILE_STORAGE_DIR_MAX_NUM=1000`、`LOCAL_FILE_STORAGE_DIR_LEN=3`、`SELF_FILE_SERVER_STORAGE_DIR`）

**`mysqlSettings.py` / `redisSettings.py`**（连接串）、**`wechatSettings.py`**（公众号 appID/secret/模板ID，Phase 0 先留空结构）

**验收**：`python -c "from config import basicSettings"` 无报错。

---

## T4 · 12 个 `ch_*.txt` 定义文件

> **写法红线**：每行一个字段，`字段名 类型 [约束] COMMENT '说明'`，**字段行内严格单空格分隔（禁用 Tab）**；`COMMENT` 内不得出现 `%`（用「百分比」或「pct」）；首字段必须 `recID BIGINT AUTO_INCREMENT PRIMARY KEY`；尾部固定七字段顺序不可变：`label / memo / regID / regYMDHMS / modifyID / modifyYMDHMS / delFlag`。

将以下 12 段分别写入 `code/src/database/ch_*.txt`（文件名 = 表名）。

### 写入 `database/ch_topic.txt`
```
recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID'
topicCode VARCHAR(64) NOT NULL UNIQUE COMMENT '主题编码 幂等键'
title VARCHAR(128) NOT NULL COMMENT '标题 限50字'
summary VARCHAR(400) NULL COMMENT '简介 限200字'
description MEDIUMTEXT NULL COMMENT '详细描述正文 2000到5000字'
descriptionFileID VARCHAR(200) NULL COMMENT '详述大稿fileID 超长时正文转存文件'
coverFileID VARCHAR(200) NULL COMMENT '标题图fileID'
coverThumbID VARCHAR(200) NULL COMMENT '标题图缩略图fileID'
author VARCHAR(64) NULL COMMENT '作者'
location VARCHAR(128) NULL COMMENT '地点'
source VARCHAR(255) NULL COMMENT '来源'
period VARCHAR(64) NULL COMMENT '时期'
tagList VARCHAR(512) NULL COMMENT '标签 逗号分隔'
categoryCode VARCHAR(32) NULL COMMENT '分类编码'
status VARCHAR(24) NOT NULL DEFAULT 'DRAFT' COMMENT 'DRAFT或RENDERING或RENDERED或PUBLISHED或ARCHIVED'
publishStatus VARCHAR(24) NOT NULL DEFAULT 'UNPUBLISHED' COMMENT 'UNPUBLISHED或DRAFTED或PUBLISHED或FAILED'
assetCount SMALLINT NOT NULL DEFAULT 0 COMMENT '附图数量'
wordCount INT NOT NULL DEFAULT 0 COMMENT '详述字数'
aiFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '是否AI参与创作'
ownerID VARCHAR(64) NULL COMMENT '归属用户loginID'
label VARCHAR(32) COMMENT 'label'
memo VARCHAR(200) COMMENT 'memo'
regID VARCHAR(32) COMMENT '注册ID'
regYMDHMS VARCHAR(16) COMMENT '注册年月日'
modifyID VARCHAR(32) COMMENT '修改用户ID'
modifyYMDHMS VARCHAR(16) COMMENT '修改年月日'
delFlag CHAR(1) COMMENT '删除标记'
```

### 写入 `database/ch_topic_asset.txt`
```
recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID'
assetKey VARCHAR(400) NOT NULL UNIQUE COMMENT '幂等键 topicID加冒号加fileID'
topicID BIGINT NOT NULL COMMENT '关联ch_topic.recID'
fileID VARCHAR(200) NOT NULL COMMENT '素材fileID 关联ch_asset.fileID'
caption VARCHAR(512) NULL COMMENT '图片简要说明'
usageType VARCHAR(24) NOT NULL DEFAULT 'body' COMMENT 'cover或body或inline'
sortOrder SMALLINT NOT NULL DEFAULT 100 COMMENT '展示顺序 越小越靠前'
label VARCHAR(32) COMMENT 'label'
memo VARCHAR(200) COMMENT 'memo'
regID VARCHAR(32) COMMENT '注册ID'
regYMDHMS VARCHAR(16) COMMENT '注册年月日'
modifyID VARCHAR(32) COMMENT '修改用户ID'
modifyYMDHMS VARCHAR(16) COMMENT '修改年月日'
delFlag CHAR(1) COMMENT '删除标记'
```

### 写入 `database/ch_asset.txt`
```
recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID'
fileID VARCHAR(200) NOT NULL UNIQUE COMMENT '文件服务器fileID 只存标识'
thumbnailID VARCHAR(200) NULL COMMENT '缩略图fileID'
contentHash CHAR(64) NOT NULL UNIQUE COMMENT 'sha256原始字节 内容级去重'
fileSystem VARCHAR(16) NOT NULL COMMENT '落库时后端快照 ALIOSS或TENCENT或SELFFILE'
storageBucket VARCHAR(64) NULL COMMENT '存储桶名 本地存储为local'
storagePath VARCHAR(512) NULL COMMENT '本地相对路径 SELFFILE用'
objectName VARCHAR(255) NULL COMMENT '对象键 ALIOSS/TENCENT用'
origName VARCHAR(255) NULL COMMENT '原始文件名'
mimeType VARCHAR(64) NULL COMMENT 'MIME类型'
fileExt VARCHAR(16) NULL COMMENT '扩展名'
origSizeBytes BIGINT NOT NULL DEFAULT 0 COMMENT '原始字节数'
width INT NULL COMMENT '原始宽度'
height INT NULL COMMENT '原始高度'
derivedFileID VARCHAR(200) NULL COMMENT '规格处理后fileID'
derivedThumbID VARCHAR(200) NULL COMMENT '处理后缩略图fileID'
derivedWidth INT NULL COMMENT '处理后宽度'
derivedHeight INT NULL COMMENT '处理后高度'
derivedSizeBytes BIGINT NULL COMMENT '处理后字节数'
exifStripped CHAR(1) NOT NULL DEFAULT '0' COMMENT '是否已剥离EXIF'
processStatus VARCHAR(24) NOT NULL DEFAULT 'RAW' COMMENT 'RAW或PROCESSED或FAILED'
errMsg VARCHAR(512) NULL COMMENT '错误信息'
ownerID VARCHAR(64) NULL COMMENT '上传者loginID'
label VARCHAR(32) COMMENT 'label'
memo VARCHAR(200) COMMENT 'memo'
regID VARCHAR(32) COMMENT '注册ID'
regYMDHMS VARCHAR(16) COMMENT '注册年月日'
modifyID VARCHAR(32) COMMENT '修改用户ID'
modifyYMDHMS VARCHAR(16) COMMENT '修改年月日'
delFlag CHAR(1) COMMENT '删除标记'
```

### 写入 `database/ch_layout.txt`
```
recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID'
layoutCode VARCHAR(64) NOT NULL UNIQUE COMMENT '版式唯一编码 如stack_v1'
layoutName VARCHAR(64) NOT NULL COMMENT '版式名称'
layoutType VARCHAR(24) NOT NULL COMMENT 'stack上下 或 carousel左右轮播 或 longimage长图 或 swipe左右滑动浏览'
platform VARCHAR(24) NOT NULL COMMENT 'wechat_mp或xiaohongshu或generic'
engine VARCHAR(24) NOT NULL DEFAULT 'jinja2' COMMENT '渲染引擎'
templatePath VARCHAR(255) NULL COMMENT '模板文件相对路径'
templateVer VARCHAR(24) NOT NULL DEFAULT 'v1' COMMENT '模板版本'
outputKind VARCHAR(24) NOT NULL DEFAULT 'html' COMMENT 'html或png或zip'
specJson VARCHAR(1000) NULL COMMENT '版式参数JSON 尺寸或间距或配色'
previewFileID VARCHAR(200) NULL COMMENT '版式预览图fileID'
builtinFlag CHAR(1) NOT NULL DEFAULT '1' COMMENT '是否内置'
enabled CHAR(1) NOT NULL DEFAULT '1' COMMENT '是否启用'
sortWeight SMALLINT NOT NULL DEFAULT 100 COMMENT '排序权重 越小越靠前'
label VARCHAR(32) COMMENT 'label'
memo VARCHAR(200) COMMENT 'memo'
regID VARCHAR(32) COMMENT '注册ID'
regYMDHMS VARCHAR(16) COMMENT '注册年月日'
modifyID VARCHAR(32) COMMENT '修改用户ID'
modifyYMDHMS VARCHAR(16) COMMENT '修改年月日'
delFlag CHAR(1) COMMENT '删除标记'
```

### 写入 `database/ch_platform.txt`
```
recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID'
platformCode VARCHAR(32) NOT NULL UNIQUE COMMENT 'wechat_mp或xiaohongshu或generic'
platformName VARCHAR(64) NOT NULL COMMENT '平台名称'
subjectScope VARCHAR(128) NULL COMMENT '支持的主体类型 如个人订阅号或认证服务号'
deliverMode VARCHAR(24) NOT NULL COMMENT 'draft_box或asset_pack或api_publish'
titleMaxLen SMALLINT NOT NULL DEFAULT 64 COMMENT '标题字数上限'
summaryMaxLen SMALLINT NOT NULL DEFAULT 200 COMMENT '简介字数上限'
coverSpec VARCHAR(64) NULL COMMENT '封面规格 如900x500'
imageSpec VARCHAR(64) NULL COMMENT '正文图规格 如1080x1440'
imageMaxCount SMALLINT NOT NULL DEFAULT 20 COMMENT '图片数量上限'
allowSvgFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '是否允许SVG交互'
needAiLabelFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '是否强制AI内容标识'
autoPublishFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '是否允许自动发布'
limitNote VARCHAR(512) NULL COMMENT '限制与风控说明'
docUrl VARCHAR(512) NULL COMMENT '官方文档地址'
enabled CHAR(1) NOT NULL DEFAULT '1' COMMENT '是否启用'
label VARCHAR(32) COMMENT 'label'
memo VARCHAR(200) COMMENT 'memo'
regID VARCHAR(32) COMMENT '注册ID'
regYMDHMS VARCHAR(16) COMMENT '注册年月日'
modifyID VARCHAR(32) COMMENT '修改用户ID'
modifyYMDHMS VARCHAR(16) COMMENT '修改年月日'
delFlag CHAR(1) COMMENT '删除标记'
```

### 写入 `database/ch_render_job.txt`
```
recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID'
jobCode VARCHAR(64) NOT NULL UNIQUE COMMENT '任务编码 幂等键'
topicID BIGINT NOT NULL COMMENT '关联ch_topic.recID'
layoutCode VARCHAR(64) NOT NULL COMMENT '版式编码'
platform VARCHAR(24) NOT NULL COMMENT '目标平台'
jobStatus VARCHAR(24) NOT NULL DEFAULT 'PENDING' COMMENT 'PENDING或RUNNING或DONE或FAILED'
inputHash CHAR(64) NULL COMMENT '输入快照sha256 内容未变可复用产物'
progress TINYINT NOT NULL DEFAULT 0 COMMENT '进度百分比'
errMsg VARCHAR(512) NULL COMMENT '错误信息'
startYMDHMS VARCHAR(16) NULL COMMENT '开始时间'
finishYMDHMS VARCHAR(16) NULL COMMENT '完成时间'
costMs INT NULL COMMENT '耗时毫秒'
ownerID VARCHAR(64) NULL COMMENT '发起者loginID'
label VARCHAR(32) COMMENT 'label'
memo VARCHAR(200) COMMENT 'memo'
regID VARCHAR(32) COMMENT '注册ID'
regYMDHMS VARCHAR(16) COMMENT '注册年月日'
modifyID VARCHAR(32) COMMENT '修改用户ID'
modifyYMDHMS VARCHAR(16) COMMENT '修改年月日'
delFlag CHAR(1) COMMENT '删除标记'
```

### 写入 `database/ch_artifact.txt`
```
recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID'
artifactKey VARCHAR(400) NOT NULL UNIQUE COMMENT '幂等键 jobID加冒号加kind加冒号加platform加冒号加seqNo'
jobID BIGINT NOT NULL COMMENT '关联ch_render_job.recID'
topicID BIGINT NOT NULL COMMENT '冗余主题ID 便于按主题查产物'
kind VARCHAR(24) NOT NULL COMMENT 'html或png或zip或json或markdown'
platform VARCHAR(24) NOT NULL COMMENT '目标平台'
fileID VARCHAR(200) NOT NULL COMMENT '产物文件fileID'
thumbnailID VARCHAR(200) NULL COMMENT '产物缩略图fileID'
seqNo SMALLINT NOT NULL DEFAULT 1 COMMENT '序号 图集多张时递增'
artifactVer INT NOT NULL DEFAULT 1 COMMENT '产物版本'
specNote VARCHAR(128) NULL COMMENT '规格说明 如1080x1440'
sizeBytes BIGINT NULL COMMENT '字节数'
artifactStatus VARCHAR(24) NOT NULL DEFAULT 'READY' COMMENT 'READY或EXPIRED'
expireYMDHMS VARCHAR(16) NULL COMMENT '保留到期时间'
label VARCHAR(32) COMMENT 'label'
memo VARCHAR(200) COMMENT 'memo'
regID VARCHAR(32) COMMENT '注册ID'
regYMDHMS VARCHAR(16) COMMENT '注册年月日'
modifyID VARCHAR(32) COMMENT '修改用户ID'
modifyYMDHMS VARCHAR(16) COMMENT '修改年月日'
delFlag CHAR(1) COMMENT '删除标记'
```

### 写入 `database/ch_account.txt`
```
recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID'
accountCode VARCHAR(64) NOT NULL UNIQUE COMMENT '账号幂等键'
platform VARCHAR(24) NOT NULL COMMENT '所属平台'
accountName VARCHAR(128) NOT NULL COMMENT '账号名称'
subjectType VARCHAR(24) NOT NULL COMMENT 'personal或enterprise'
verifiedFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '是否已认证'
capability VARCHAR(64) NOT NULL COMMENT 'draft_box或asset_pack或api_publish'
appID VARCHAR(64) NULL COMMENT '平台appID 微信为appid'
credentialCipher TEXT NULL COMMENT '凭据密文 AES加密 明文永不落库'
credentialIV VARCHAR(64) NULL COMMENT '加密初始向量'
expireYMDHMS VARCHAR(16) NULL COMMENT '凭据到期时间'
healthStatus VARCHAR(24) NOT NULL DEFAULT 'UNKNOWN' COMMENT 'OK或EXPIRING或INVALID或UNKNOWN'
lastCheckYMDHMS VARCHAR(16) NULL COMMENT '最近健康检查时间'
lastUseYMDHMS VARCHAR(16) NULL COMMENT '最近调用时间'
ownerID VARCHAR(64) NULL COMMENT '归属loginID'
label VARCHAR(32) COMMENT 'label'
memo VARCHAR(200) COMMENT 'memo'
regID VARCHAR(32) COMMENT '注册ID'
regYMDHMS VARCHAR(16) COMMENT '注册年月日'
modifyID VARCHAR(32) COMMENT '修改用户ID'
modifyYMDHMS VARCHAR(16) COMMENT '修改年月日'
delFlag CHAR(1) COMMENT '删除标记'
```

### 写入 `database/ch_publish_record.txt`
```
recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID'
idempotencyKey VARCHAR(400) NOT NULL UNIQUE COMMENT '幂等键 由调用方传入 防重复提交'
artifactId BIGINT NOT NULL COMMENT '关联ch_artifact.recID'
topicID BIGINT NOT NULL COMMENT '冗余主题ID'
accountID BIGINT NULL COMMENT '关联ch_account.recID 素材包导出可空'
platform VARCHAR(24) NOT NULL COMMENT '目标平台'
deliverMode VARCHAR(24) NOT NULL COMMENT 'draft_box或asset_pack'
requestJson JSON NULL COMMENT '请求报文摘要'
responseJson JSON NULL COMMENT '响应报文摘要'
errcode INT NULL COMMENT '平台返回码'
errmsg VARCHAR(512) NULL COMMENT '平台返回信息'
success CHAR(1) NOT NULL DEFAULT '0' COMMENT '是否成功'
remoteID VARCHAR(128) NULL COMMENT '平台侧ID 微信草稿mediaID等'
operator VARCHAR(64) NULL COMMENT '操作者loginID'
pushedYMDHMS VARCHAR(16) NULL COMMENT '投递时间'
label VARCHAR(32) COMMENT 'label'
memo VARCHAR(200) COMMENT 'memo'
regID VARCHAR(32) COMMENT '注册ID'
regYMDHMS VARCHAR(16) COMMENT '注册年月日'
modifyID VARCHAR(32) COMMENT '修改用户ID'
modifyYMDHMS VARCHAR(16) COMMENT '修改年月日'
delFlag CHAR(1) COMMENT '删除标记'
```

### 写入 `database/ch_mcp_token.txt`
```
recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID'
tokenHash CHAR(64) NOT NULL UNIQUE COMMENT 'token的sha256 不存明文'
tokenName VARCHAR(64) NOT NULL COMMENT '令牌名称'
tokenScope VARCHAR(64) NOT NULL DEFAULT 'read' COMMENT 'read或write或publish'
projectCode VARCHAR(64) NULL COMMENT '绑定项目'
transport VARCHAR(16) NOT NULL DEFAULT 'sse' COMMENT 'sse或stdio'
lastUseYMDHMS VARCHAR(16) NULL COMMENT '最近使用时间'
useCount INT NOT NULL DEFAULT 0 COMMENT '累计调用次数'
revokedYMDHMS VARCHAR(16) NULL COMMENT '吊销时间 有值即失效'
ownerID VARCHAR(64) NULL COMMENT '创建者loginID'
label VARCHAR(32) COMMENT 'label'
memo VARCHAR(200) COMMENT 'memo'
regID VARCHAR(32) COMMENT '注册ID'
regYMDHMS VARCHAR(16) COMMENT '注册年月日'
modifyID VARCHAR(32) COMMENT '修改用户ID'
modifyYMDHMS VARCHAR(16) COMMENT '修改年月日'
delFlag CHAR(1) COMMENT '删除标记'
```

### 写入 `database/ch_audit_log.txt`
```
recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID'
actor VARCHAR(64) NULL COMMENT '操作者 loginID或mcp令牌名'
source VARCHAR(16) NOT NULL DEFAULT 'web' COMMENT 'web或api或mcp'
action VARCHAR(64) NOT NULL COMMENT '动作 如topic.create或publish.push'
targetType VARCHAR(32) NULL COMMENT '对象类型'
targetID VARCHAR(64) NULL COMMENT '对象ID'
payloadDigest CHAR(64) NULL COMMENT '入参摘要sha256'
result VARCHAR(24) NOT NULL DEFAULT 'OK' COMMENT 'OK或FAIL'
errMsg VARCHAR(512) NULL COMMENT '错误信息'
costMs INT NULL COMMENT '耗时毫秒'
ipAddr VARCHAR(64) NULL COMMENT '来源IP'
label VARCHAR(32) COMMENT 'label'
memo VARCHAR(200) COMMENT 'memo'
regID VARCHAR(32) COMMENT '注册ID'
regYMDHMS VARCHAR(16) COMMENT '注册年月日'
modifyID VARCHAR(32) COMMENT '修改用户ID'
modifyYMDHMS VARCHAR(16) COMMENT '修改年月日'
delFlag CHAR(1) COMMENT '删除标记'
```

### 写入 `database/ch_topic_version.txt`
```
recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID'
verKey VARCHAR(64) NOT NULL UNIQUE COMMENT '幂等键 topicID加冒号加versionNo'
topicID BIGINT NOT NULL COMMENT '关联ch_topic.recID'
versionNo INT NOT NULL COMMENT '版本号 从1递增'
snapshotJson MEDIUMTEXT NULL COMMENT '主题完整快照JSON'
diffNote VARCHAR(512) NULL COMMENT '变更说明'
ownerID VARCHAR(64) NULL COMMENT '保存者loginID'
label VARCHAR(32) COMMENT 'label'
memo VARCHAR(200) COMMENT 'memo'
regID VARCHAR(32) COMMENT '注册ID'
regYMDHMS VARCHAR(16) COMMENT '注册年月日'
modifyID VARCHAR(32) COMMENT '修改用户ID'
modifyYMDHMS VARCHAR(16) COMMENT '修改年月日'
delFlag CHAR(1) COMMENT '删除标记'
```

**验收**：`ls database/ch_*.txt | wc -l` = 12；且每行字段行单空格分隔（用 `cat -A` 抽查无 `^I`）。

---

## T5 · 跑生成器（只走 readFromFile 路径）

```bash
cd code/src
PY=python   # 或用 managed: C:\Users\steve\.workbuddy\binaries\python\versions\3.13.12\python.exe

# 批量生成 12 张表
for f in database/ch_*.txt; do
  t=$(basename "$f" .txt | sed 's/^ch_//')   # topic, topic_asset, asset, layout, ...
  $PY database/mysqlCodeGenerator.py -i "$f" -t "$t"
done
```

生成产物落 `database/auto_generated/auto_gen_code_ch_*.py` + `word_table_ch_*.csv`。

> **坑提醒（必看 v3 §6.4）**
> - **坑 1**：绝对不要传原生 `CREATE TABLE` SQL 给生成器（参数错位 → 非法函数名）。本项目只传 `-i ch_*.txt`。
> - **坑 2**：生成代码的 `query_ch_audit_log()` 默认无 LIMIT，千万级表会拉全表。合并后**必须手工补回 LIMIT**（建议 `LIMIT 5000` + 游标分页）。
> - **坑 3**：`insert_*` 对 INT 强制 `int()`，异常置 0。可空数值列（`ch_asset.width/height`、`ch_artifact.sizeBytes` 等）业务层约定「0 = 未设置」。

**验收**：12 个 `auto_gen_code_ch_*.py` 全部生成，文件内 `func{Title}Add` 函数名合法（无 `func['xxx']Add`）。

---

## T6 · 合并 mysqlCommon + 建表验证

1. 将 12 个 `auto_gen_code_ch_*.py` 的 5 段代码（convertor / create / CRUD / func / test）人工合并进 `common/mysqlCommon.py`。保留既有 ylwz 表的函数，追加本项目 12 张表。
2. 建表脚本 `tools/initTables.py`：
```python
from common import mysqlCommon as comMysql
for fn in [comMysql.tablename_convertor_ch_topic, comMysql.tablename_convertor_ch_topic_asset,
           comMysql.tablename_convertor_ch_asset, comMysql.tablename_convertor_ch_layout,
           comMysql.tablename_convertor_ch_platform, comMysql.tablename_convertor_ch_render_job,
           comMysql.tablename_convertor_ch_artifact, comMysql.tablename_convertor_ch_account,
           comMysql.tablename_convertor_ch_publish_record, comMysql.tablename_convertor_ch_mcp_token,
           comMysql.tablename_convertor_ch_audit_log, comMysql.tablename_convertor_ch_topic_version]:
    t = fn()
    comMysql.create_ch_xxx(t) if hasattr(comMysql, "create_" + t) else None
```
   更稳妥的做法：直接用生成器产出的 `create_ch_*` 函数逐表建表。
3. 执行后连 MySQL 校验 `SHOW TABLES` 含 12 张 `ch_*` 表。

**验收**：`SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='<db>' AND table_name LIKE 'ch_%'` = 12。

---

## T7 · fileStorageCommon.py 门面（新增核心抽象）

新建 `common/fileStorageCommon.py`，按 v3 §4.4 实现：
- `getStorage(mode)` 工厂：按 `FILE_SYSTEM_MODE` 返回 `aliyunOSS / tencentCOS / selfFileCommon`
- 业务层函数：`saveFile / getFileTempUrl / delFile / saveWithThumbnail`
- 兼容旧体系入口：`getTempLocation(fileID, privateFlag, localAccess, localAddress, targetFileName, sourceServerAddr)`（fileID 已是 http 则原样返回）

**联调脚本 `tools/test_storage.py`**（三种后端各跑一遍 upload → getTempUrl → download → delete）：

```python
from common import fileStorageCommon as fs
import os, tempfile

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

**验收**：SELFFILE 本地模式全过；ALIOSS/TENCENT 配置就绪后切 `FILE_SYSTEM_MODE` 各跑一遍通过。

---

## T8 · 种子数据 + plan.md

- `tools/initSeed.py`：用生成器产出的 `insert_ch_platform()` / `insert_ch_layout()` 灌种子（见 v3 §5.4）：
  - `ch_platform`：`wechat_mp`(draft_box, allowSvg=0, needAiLabel=0, coverSpec=900x500, imageSpec=1080x1440)、`xiaohongshu`(asset_pack, imageSpec=1080x1440, **imageMaxCount=18**, needAiLabel=1, autoPublish=0)、`generic`(asset_pack)
  - `ch_layout`：`stack_v1`(上下)、`carousel_v1`(左右轮播)、`longimage_v1`(长图拼接)、**`swipe_v1`(左右滑动多图集：layoutType=swipe、platform=xiaohongshu、outputKind=png、specJson={size:1080x1440, ratio:"3:4", maxCount:18, uniformRatio:true, maxSizePerImageMB:20})**，各平台各一套
- 产出 `plan.md`（目录骨架 / 模块边界 C1–C8 / 接口约定 / 配置项清单 / MCP 协议选型结论 sse+stdio 双支持）—— 可基于 `content-hub-开发计划v3.md` 第 2/3/7 节精简。

**验收**：种子后 `SELECT COUNT(*) FROM ch_platform` = 3、`ch_layout` ≥ 4（含 `swipe_v1`）。

---

## T9 · Phase 0 验收总表

| # | 检查项 | 命令/方法 | 期望 |
|---|---|---|---|
| 1 | 目录骨架 | `ls` | T1 目录齐全 |
| 2 | 复用层 import | `python -c "from common import mysqlHandle,funcCommon,miscCommon,globalDefinition,redisCommon,aliyunOSS,tencentCOS,selfFileCommon"` | 无报错 |
| 3 | 配置文件 | `python -c "from config import basicSettings"` | 无报错 |
| 4 | 12 个 txt | `ls database/ch_*.txt \| wc -l` | 12 |
| 5 | 生成器产物 | `ls database/auto_generated/auto_gen_code_ch_*.py \| wc -l` | 12 |
| 6 | 建表 | `SHOW TABLES LIKE 'ch_%'` | 12 张 |
| 7 | 文件门面 | `python tools/test_storage.py`（SELFFILE） | upload/url/del 均 True |
| 8 | 种子 | `SELECT COUNT(*) FROM ch_platform` | 3 |

---

## 转 Phase 1 的交接说明

Phase 0 完成后，主干进入 **C1 接入权限 → C2 主题管理 → C3 素材图库 → C4 版式引擎（先硬编码 4 套模板，含小红书 `swipe_v1` 左右滑动多图集）**。注意：
- **MCP Hub（C7）不在 Phase 1**，必须等 C4/C6 稳定（Phase 3）再做，否则接口随渲染引擎返工。
- **企业号认证**从 Day 1 并行启动，但不阻塞 Phase 1–2（即使未过审，素材包导出形态依然完整）。
- 渲染产物的「小红书长图拼接」直接复用 ylwz 文件服务 `F4A0`（`multiImageMerge`），不自研。

*本清单为 content-hub-开发计划v3 的 Phase 0 可执行拆解 · 2026-09-17 · 阿枢整理*
