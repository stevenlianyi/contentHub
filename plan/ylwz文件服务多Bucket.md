# ylwz 文件服务多 Bucket 支持方案

| 项 | 内容 |
|---|---|
| 支线编号 | **S1** |
| 目标文件 | `code/src/ylwzRecvFiles.py`（contentHub 落位） |
| 关联配置 | `code/src/config/aliyunSettings.py`、`code/src/config/tencentSettings.py` |
| 基线参考 | `ylwzProject/museum/code/src/main/ylwzRecvFiles.py`（1483 行）、`common/aliyunOSS.py`、`common/tencentCOS.py`、`config/aliyunSettings.py`、`config/tencentSettings.py`、`common/selfFileCommon.py`、`config/selfFileSettings.py` |
| 类型 | **并行支线**（与主计划 Phase 0 · T7 同步/前置） |
| 优先级 | **P1**（不阻塞主干，但阻塞「多桶能力」这一扩展诉求） |
| 预估工时 | **7.0 人天** |
| 版本 | v1.0 · 2026-09-17 |

---

## 1. 背景与现状（实测事实）

### 1.1 现状结论一句话

> 当前 `ylwzRecvFiles.py` 的 Bucket 是**「环境级常量」**：ALIOSS 只有 1 个桶且写死在适配器常量里，TENCENT 有 2 个桶但仅靠 `privateFlag` 二分；**请求协议中没有任何字段可指定目标桶**，**读取时也不依据记录里的桶名路由**。

### 1.2 事实清单（均带行号，来源 `museum/code/src`）

| # | 事实 | 位置 |
|---|---|---|
| F1 | 文件服务为 **Flask** 应用，仅 1 个路由 `@application.route("/hfile", methods=['POST'])` | `main/ylwzRecvFiles.py` L19/L21/L1401 |
| F2 | `/hfile` 按 mimetype 分流：`multipart/form-data` → `fileHandler()`；`application/json` → `fileRequestServices()` | L1407-1428、L436、L1383 |
| F3 | 命令分发表 `urlPathMap` 为模块级 dict，共 8 条（F0A0/F1A0/F2A0/F4A0/F6A0/F7A0/F8A0 + `/hfile`）；`F3A0`/`F5A0` 已注释 | L1360-1380（F3A0 L1369、F5A0 L1373 注释） |
| F4 | 处理函数统一签名 `func(CMD, dataSet, sessionIDSet)` | L1393 |
| F5 | **ALIOSS 只有单桶**：`BucketNamePrivate = settings.ALIYUN_OSS_SERVICE["BucketName"]`，且被 9 处调用硬编码传入 | `common/aliyunOSS.py` L79；使用点 L93/122/142/159/192/228/250/280 |
| F6 | `aliyunOSS.py` 全文件**没有 `privateFlag` 形参**，`privateFlag` 对选桶**完全无效** | `common/aliyunOSS.py` 全文件 |
| F7 | **TENCENT 双桶**：`bucketName` / `privateBucketName`，每个函数入口按 `privateFlag` 选桶 | `common/tencentCOS.py` L51-52；选择点 L64-67/97-100/119-122/139-142/159-162/179-182/199-202/220-247 |
| F8 | `aliyunOSS` 实际消费的 config 键：`AccessKeyId`/`AccessKeySecret`/`RegionId`/`Endpoint`/`EndpointExternal`/`EndpointInternal`/**`BucketName`**/`DispTimeOut`/`sts*`/`roleArn`/`stsPolicyData`；`ConnTimeOut` 仅在注释中出现 | `common/aliyunOSS.py` L49/57/71/72/73/79/222/245/275-292 |
| F9 | `tencentCOS` 实际消费：`secretId`/`secretKey`/`regionId`/`bucketName`/`privateBucketName`/`url`/`privateUrl`；`domainBase`/`connTimeOut`/`dispTimeOut` **未被引用** | `common/tencentCOS.py` L46-52/L221/L223 |
| F10 | config 采用「顶层服务名 → `_SYS` → 键值」三段结构，环境键为 `local/server_01/server_02/test_server/home` | `config/aliyunSettings.py` L104-240；`config/tencentSettings.py` L117-167 |
| F11 | OSS 配置中 `BucketName` 单值，且 `stsPolicyData.Statement[].Resource` 的 ARN **写死在单桶上** | `aliyunSettings.py` L118/127、L145/154、L172/181、L199/208、L226/235 |
| F12 | COS 配置中有 `bucketName` + `url` + `privateBucketName` + `privateUrl` | `tencentSettings.py` L123-126 等 |
| F13 | `cmdF0A0` 实际读取的请求字段仅：`token`/`YMDHMS`/`fileID`/`requestType`/`prefix`/`privateFlag`/`compressFlag`/`objectName`/`serverName`/`lang` —— **无任何可承载「目标桶」的字段** | `ylwzRecvFiles.py` L644-937（鉴权 L655-660、参数 L670/671/674/676/689） |
| F14 | `fileSystem` 来源为**记录（Redis）**，为空才回落全局 `FILE_SYSTEM_MODE`；**不读请求字段** | L664-666 |
| F15 | `objectName` 生成规则：`prefix + description + "_" + YMDHMS + "_" + uuid4hex + fileExt`（缩略图追加 `_thumbnail`） | L721、L708（ALIOSS）；L782、L769（TENCENT） |
| F16 | SELFFILE fileID = `{3位随机分片}/file{uuid4hex}`，落盘为 `<fileID>.data` + `<fileID>.info` | `selfFileCommon.py` L110-117、L132-133 |
| F17 | SELFFILE `.info` JSON 字段：`serverName/fileSystem/description/fileName/oldFileName/objectName/fileExtName/fileSize/fileUrl/uploadYMDHMS/requestType/prefix/compressFlag` —— **不含 `storageBucket` / `storagePath`** | `ylwzRecvFiles.py` L847-861；`selfFileCommon.py` L124-147 |
| F18 | `SELF_FILE_SERVER_STORAGE_DIR` 为**单值**（每个 `_SYS` 唯一路径），本地后端**无多根目录能力** | `config/selfFileSettings.py` L73-78 |
| F19 | 读路径选桶 = **全局 `FILE_SYSTEM_MODE` + （仅 TENCENT）`privateFlag`** | `ylwzRecvFiles.py` `getTempLocation` L217-306（OSS L227 / COS L262-264 / SELFFILE L298） |
| F20 | museum 表 `mu_image_resource` **已有 `storageBucket VARCHAR(64) NULL`**（注释：对象存储桶名，本地为 local）与 `storagePath VARCHAR(512)` | `database/mu_image_resource.txt` L10/L9；`common/mysqlCommon.py` L4167-4168 |
| F21 | `storageBucket` **只被写入（且恒写 `"local"`），从未被读取用于路由** | 写入：`processor/crawler_base.py` L690、`crawler_base_http.py` L408、`downloader.py` L317、`downloader_http.py` L326；全仓检索无读取路由处 |
| F22 | 调用方读文件的统一入口为 `getTempLocation(fileID, privateFlag)`，内部组装 `CMD="F7A0"` 并传**全局** `fileSystem` | `common/funcCommon.py` L1271-1305；`common/museumCommon.py` L695-729 |

### 1.3 现状问题清单

| # | 问题 | 影响 |
|---|---|---|
| P1 | 单环境只能用一个物理桶 | 无法按业务域隔离（媒体 / 产物 / 公开资源），无法做生命周期与成本分层 |
| P2 | 桶名写死在适配器常量与调用点 | 换桶/加桶必须改代码并全量回归 |
| P3 | `privateFlag` 语义在两端**不一致**（TENCENT 有效、ALIOSS 完全无效） | 上层无法用统一方式表达「放哪个区」，跨后端行为不可预期 |
| P4 | 请求协议无「目标桶」字段 | 调用方无法指定落点，只能落默认桶 |
| P5 | 读取不依据记录快照路由 | 一旦加桶，历史文件将按「当前默认桶」去取 → **读不到**（这是多桶改造的最大兼容性陷阱） |
| P6 | STS 策略 Resource ARN 写死单桶 | 加桶后 STS 临时凭据上传到新桶会被拒绝 |
| P7 | 本地后端无多根目录 | 与云端多桶语义不对齐，`SELFFILE` 环境无法做等价演练 |

---

## 2. 目标与范围

### 2.1 目标

1. **多桶可配**：同一环境下可定义 N 个逻辑桶（logical bucket），每个逻辑桶映射到一个物理桶 + 路径前缀 + 访问属性。
2. **协议向后兼容**：不传 `bucketCode` 时**行为与现在完全一致**（落默认桶）。
3. **落库可追溯**：写入时把「逻辑桶码 + 物理桶名」快照写入元信息与业务表，读取时**按快照路由**。
4. **后端对称**：ALIOSS / TENCENT 语义对齐，`privateFlag` 不再是「有时有效有时无效」的隐式开关。
5. **零硬编码**：新增/切换桶只改 `config/`，不改 `ylwzRecvFiles.py` 与适配器的业务分支。

### 2.2 范围

| 在范围 | 不在范围 |
|---|---|
| `config/aliyunSettings.py`、`config/tencentSettings.py` 结构升级 | 本地后端（SELFFILE）多根目录改造（仅做语义预留，见 6.5） |
| `common/aliyunOSS.py`、`common/tencentCOS.py` 支持 `bucketCode` 参数 | 新增云厂商适配器 |
| `ylwzRecvFiles.py` 的 F0A0 / F1A0 / F2A0 / F6A0 / F7A0 / F8A0 支持桶参数与快照 | 跨桶数据迁移工具（另立任务） |
| 元信息与业务表落库桶快照；读取按快照路由 | 存储生命周期策略（云侧配置，非代码） |
| 兼容性验证与回滚方案 | 存量文件重分布 |

---

## 3. 配置格式设计

### 3.1 设计要点

1. **逻辑桶码（`bucketCode`）与物理桶名解耦**：业务层只说 `bucketCode`（如 `media`），物理名与路径前缀由配置决定 → 换桶不改业务代码。
2. **公共认证共享**：`AccessKeyId/Secret`、`Endpoint`、超时等留在服务级，**只有桶相关内容下沉到 `Buckets`**，避免 N 份密钥。
3. **兼容键保留**：`BucketName`（OSS）、`bucketName`/`privateBucketName`（COS）保留为**派生别名**，由 `Buckets` 计算得出，消除双份维护。
4. **默认桶显式声明**：`DefaultBucketCode`，不传 `bucketCode` 时用它。

### 3.2 `config/aliyunSettings.py` 新结构

```python
# —— 多桶公共部分（服务级，各桶共享）——
_OSS_COMMON = {
    "RegionId": "cn-beijing",
    "roleArn": "acs:ram::<account>:user/oss_access",
    "AccessKeyId": "<redacted>",
    "AccessKeySecret": "<redacted>",
    "readOnlyAccessKeyId": "<redacted>",
    "readOnlyAccessKeySecret": "<redacted>",
    "Endpoint": "https://oss-cn-beijing.aliyuncs.com",
    "EndpointExternal": "https://oss-cn-beijing.aliyuncs.com",
    "EndpointInternal": "https://oss-cn-beijing-internal.aliyuncs.com",
    "ConnTimeOut": 60,
    "DispTimeOut": 1800,
}

# —— 各环境的多桶定义 ——
ALIYUN_OSS_BUCKETS = {
    "local": {
        "DefaultBucketCode": "default",
        "Buckets": {
            # bucketCode : 桶定义
            "default":  {"BucketName": "contenthub-private",  "Access": "private", "PathPrefix": "",          "UrlBase": ""},
            "media":    {"BucketName": "contenthub-media",    "Access": "private", "PathPrefix": "media/",    "UrlBase": ""},
            "artifact": {"BucketName": "contenthub-artifact", "Access": "private", "PathPrefix": "artifact/", "UrlBase": ""},
            "public":   {"BucketName": "contenthub-public",   "Access": "public",  "PathPrefix": "pub/",      "UrlBase": "https://contenthub-public.oss-cn-beijing.aliyuncs.com"},
        },
    },
    "server_01": { ... },
    "server_02": { ... },
    "test_server": { ... },
    "home": { ... },
}[_SYS]

_BUCKETS = ALIYUN_OSS_BUCKETS["Buckets"]
_DEFAULT_BUCKET_CODE = ALIYUN_OSS_BUCKETS["DefaultBucketCode"]

# —— STS 策略：Resource 按全部桶自动展开，避免加桶后漏配 ——
def _genStsResource(buckets):
    res = []
    for _code, b in buckets.items():
        name = b["BucketName"]
        res.append(f"acs:oss:*:*:{name}")
        res.append(f"acs:oss:*:*:{name}/*")
    return res

ALIYUN_OSS_SERVICE = dict(_OSS_COMMON)
ALIYUN_OSS_SERVICE.update({
    # ▼ 兼容别名：等价于默认桶，老代码 settings.ALIYUN_OSS_SERVICE["BucketName"] 继续可用
    "BucketName": _BUCKETS[_DEFAULT_BUCKET_CODE]["BucketName"],
    # ▼ 新增
    "DefaultBucketCode": _DEFAULT_BUCKET_CODE,
    "Buckets": _BUCKETS,
    "stsRegionId": "oss-cn-beijing",
    "stsAccessKeyId": "stskeyid",
    "stsAccessKeySecret": "stssecret",
    "stsPolicyData": {
        "Version": "1",
        "Statement": [{
            "Effect": "Allow",
            "Action": ["oss:Put*"],
            "Resource": _genStsResource(_BUCKETS),   # ← 自动覆盖全部桶
            "Condition": {},
        }],
    },
})
```

> **兼容性保证**：`ALIYUN_OSS_SERVICE["BucketName"]` 仍存在且等于默认桶物理名 → `common/aliyunOSS.py` L79 的 `BucketNamePrivate` 赋值**无需立即修改即可继续工作**（渐进改造的前提）。

### 3.3 `config/tencentSettings.py` 新结构

```python
TECENT_COS_BUCKETS = {
    "local": {
        "DefaultBucketCode": "private",
        "Buckets": {
            "private": {"BucketName": "xjy-private-home", "Access": "private", "PathPrefix": "",       "Url": "https://xjy-private-home.cos.ap-chengdu.myqcloud.com"},
            "public":  {"BucketName": "xjy-data-home",    "Access": "public",  "PathPrefix": "pub/",   "Url": "https://xjy-data-home.cos.ap-chengdu.myqcloud.com"},
            "media":   {"BucketName": "xjy-media-home",   "Access": "private", "PathPrefix": "media/", "Url": "https://xjy-media-home.cos.ap-chengdu.myqcloud.com"},
        },
    },
    "server_01": { ... }, "server_02": { ... }, "home": { ... },
}[_SYS]

_COS_BUCKETS = TECENT_COS_BUCKETS["Buckets"]
_COS_DEFAULT = TECENT_COS_BUCKETS["DefaultBucketCode"]

TECENT_COS_SERVICE = {
    "secretId": "<redacted>",
    "secretKey": "<redacted>",
    "domainBase": "myqcloud.com",
    "regionId": "ap-chengdu",
    "connTimeOut": 60,
    "dispTimeOut": 1800,
    # ▼ 兼容别名（语义保持与旧版一致：privateFlag=True → private 桶）
    "privateBucketName": _COS_BUCKETS["private"]["BucketName"],
    "privateUrl":        _COS_BUCKETS["private"]["Url"],
    "bucketName":        _COS_BUCKETS["public"]["BucketName"],
    "url":               _COS_BUCKETS["public"]["Url"],
    # ▼ 新增
    "DefaultBucketCode": _COS_DEFAULT,
    "Buckets": _COS_BUCKETS,
}
```

> **语义对齐说明**：旧版 `privateFlag=True` 选 `privateBucketName`、`False` 选 `bucketName`。新结构把这个隐式映射**显式化为 `private` / `public` 两个 bucketCode**，并保留 `privateFlag` 的旧语义作为 fallback（见 4.2），因此行为连续。

### 3.4 统一桶解析器（新增，配置层唯一出口）

建议新增 `config/bucketSettings.py`（纯函数、无副作用），作为**全项目唯一的桶解析入口**：

```python
from config import basicSettings as settings

_ALIYUN = None
_TENCENT = None

def _services():
    from config import aliyunSettings, tencentSettings
    return {"ALIOSS": aliyunSettings.ALIYUN_OSS_SERVICE,
            "TENCENT": tencentSettings.TECENT_COS_SERVICE}

def listBuckets(fileSystem=""):
    fileSystem = fileSystem or settings.FILE_SYSTEM_MODE
    svc = _services()[fileSystem]
    return svc.get("Buckets", {}) if isinstance(svc, dict) else {}

def getBucketInfo(fileSystem="", bucketCode="", privateFlag=False):
    """返回 {bucketCode, bucketName, access, pathPrefix, urlBase}
    解析优先级：bucketCode > privateFlag(仅 TENCENT) > DefaultBucketCode
    """
    svc = _services()[fileSystem or settings.FILE_SYSTEM_MODE]
    buckets = svc.get("Buckets", {})
    if bucketCode and bucketCode in buckets:
        code = bucketCode
    elif fileSystem == "TENCENT":
        code = "private" if privateFlag else "public"
        code = code if code in buckets else svc.get("DefaultBucketCode", "default")
    else:
        code = svc.get("DefaultBucketCode", "default")
    b = dict(buckets.get(code, {}))
    b["bucketCode"] = code
    return b

def resolveBucketBySnapshot(fileSystem, storageBucket="", bucketCode=""):
    """读取路径：优先按落库快照路由；快照缺失则回落默认桶（旧数据兼容）"""
    buckets = listBuckets(fileSystem)
    if bucketCode and bucketCode in buckets:
        b = dict(buckets[bucketCode]); b["bucketCode"] = bucketCode; return b
    if storageBucket:
        for code, b in buckets.items():
            if b.get("BucketName") == storageBucket:
                r = dict(b); r["bucketCode"] = code; return r
    return getBucketInfo(fileSystem)
```

---

## 4. 代码改造点

### 4.1 改造总览

| 层 | 文件 | 改造性质 | 风险 |
|---|---|---|---|
| 配置 | `config/aliyunSettings.py`、`config/tencentSettings.py` | **结构升级 + 兼容别名** | 低（别名保证旧代码可跑） |
| 配置 | `config/bucketSettings.py`（新增） | 纯新增 | 无 |
| 适配器 | `common/aliyunOSS.py` | 加可选 `bucketCode` 参数（尾部），替换 L79 常量 | 中（9 处调用点） |
| 适配器 | `common/tencentCOS.py` | 加可选 `bucketCode` 参数，替换桶选择逻辑 | 中（8 处选择点） |
| 服务 | `ylwzRecvFiles.py` | 协议扩展 + 落库快照 + 读路径路由 | 中高（核心链路） |
| 元信息 | `ylwzRecvFiles.py` SELFFILE `.info` | 增 2 个字段 | 低（新增字段向后兼容） |
| 业务表 | `ch_asset.storageBucket` | 已有列，补写真实桶名 + 新增 `bucketCode` 语义 | 低 |

### 4.2 `common/aliyunOSS.py`

| # | 改造点 | 说明 |
|---|---|---|
| A1 | L79 `BucketNamePrivate = settings.ALIYUN_OSS_SERVICE["BucketName"]` | 保留该常量（兼容），但**新增**内部解析函数；常量改为 `= getBucketName()`（默认桶） |
| A2 | 新增 `def _resolveBucket(bucketCode=""): return comBucket.getBucketInfo("ALIOSS", bucketCode)` | 延迟 import 避免循环依赖 |
| A3 | 6 个统一接口 + `setFileAccess`/`genFileUploadUrl`/`genSTSToken` 全部追加**尾部可选参数** `bucketCode=""` | 例：`uploadFile(objName, fileName, downloadName="", bucketCode="")` |
| A4 | 9 处 `bucket=BucketNamePrivate` 替换为 `bucket=_resolveBucket(bucketCode)["bucketName"]` | L93/122/142/159/192/228/250/280 |
| A5 | `genSTSToken` 的 `Resource` 改用配置里的 `stsPolicyData`（已自动覆盖全桶） | L280-292 |
| A6 | **补 `privateFlag` 形参（接受但忽略）** 或明确文档化 | 见 6.2 语义对齐决策 |
| A7 | 路径前缀拼接：`objectName = bucketInfo["pathPrefix"] + objectName`（前缀非空时） | 在 A4 同处实现 |

> **向后兼容**：所有新增参数都有默认值且位于参数尾部 → 现有 25+ 处调用**零改动**。

### 4.3 `common/tencentCOS.py`

| # | 改造点 | 说明 |
|---|---|---|
| B1 | L51-52 `bucketName`/`privateBucketName` 常量保留 | 兼容出口 |
| B2 | 新增 `def _resolveBucket(privateFlag=False, bucketCode=""): return comBucket.getBucketInfo("TENCENT", bucketCode, privateFlag)` | 统一解析 |
| B3 | 8 处 `localBucketName = privateBucketName if privateFlag else bucketName` 替换为 `_resolveBucket(...)["bucketName"]` | L64-67/97-100/119-122/139-142/159-162/179-182/199-202/220-247 |
| B4 | `genFileTempUrl` / `genFilePublicUrl` 的域名改用 `bucketInfo["Url"]` | 原先用 `privateUrl`/`url`，改后支持任意桶 |
| B5 | 追加尾部可选参数 `bucketCode=""` | 同 A3 |

### 4.4 `ylwzRecvFiles.py`

| # | 改造点 | 位置 | 说明 |
|---|---|---|---|
| C1 | `cmdF0A0` 读取可选 `bucketCode = dataSet.get("bucketCode", "")` | L644-937（参数区 L670-689） | 缺省为空 → 落默认桶（**行为不变**） |
| C2 | `cmdF0A0` 上传时透传 `bucketCode` | L724（OSS）、L782 区（COS）、L869 区（SELFFILE） | 三后端同参 |
| C3 | `cmdF0A0` 返回体新增 `bucketCode` / `storageBucket` | L925-929 | 供调用方落库 |
| C4 | SELFFILE `.info` 新增 `storageBucket` / `bucketCode` 字段 | L847-861 | 保持既有字段不变，仅追加 |
| C5 | `cmdF7A0` / `getTempLocation` 支持按快照路由 | L1211-1279、L217-306 | 入参优先取 `bucketCode`，其次 `storageBucket`，缺失回落默认 |
| C6 | `cmdF1A0` / `cmdF2A0` 删除时按快照选桶 | L941、L1016 | 否则会去默认桶删而报「文件不存在」 |
| C7 | `cmdF6A0` / `cmdF8A0` 取文件信息时按快照选桶 | L1161、L1283 | 同上 |
| C8 | `cmdF4A0` 多图合并的**输入/输出**分别按快照选桶 | L1085 | 长图拼接场景涉及跨桶读写 |
| C9 | 新增可选诊断 CMD `F9A0`（列出当前环境可用桶，只读） | 新增 + `urlPathMap` L1360-1380 追加 | 非必需，便于运维排查；**不破坏既有协议** |

### 4.5 调用方与落库（contentHub 侧）

| # | 改造点 | 说明 |
|---|---|---|
| D1 | `common/fileStorageCommon.py` 的 `saveFile/delFile/getTempLocation` 追加可选 `bucketCode=""` | 与第 3 章门面设计兼容，仅加尾部参数 |
| D2 | `ch_asset` 写入 `storageBucket`（**真实物理桶名**），并新增语义约定：另存 `objectName` 已含路径前缀 | 复用现有列，无需改表 |
| D3 | `ch_asset` 的 `bucketCode` 若不新增列，则约定「`storageBucket` 存物理桶名，读时由 `resolveBucketBySnapshot` 反查 bucketCode」 | **推荐此方案**，避免改表（生成器链路成本高） |
| D4 | 出参 `fillFileUrls` 取 URL 时传桶快照 | 保证历史文件可读 |
| D5 | `processor/` 中所有 `getTempLocation(...)` 调用点补传桶快照 | 逐处核对 |

> **改表决策**：`ch_asset` 现有 `storageBucket VARCHAR(64)` 与 `storagePath VARCHAR(512)` 已满足需求（与 museum 的 `mu_image_resource` 同构），**v1.0 不改表**；若后续确需 `bucketCode` 独立列，走「新增列 + 双写过渡」流程（见主计划 8.6 数据库回滚红线）。

---

## 5. 兼容性处理

| 维度 | 场景 | 处理 |
|---|---|---|
| **协议** | 调用方不传 `bucketCode` | 落默认桶，返回体带 `storageBucket`；行为与改造前**逐字节一致** |
| **协议** | 调用方传了未知 `bucketCode` | **拒绝并返回明确 errCode**（不静默回落），避免写错桶 |
| **适配器** | 旧调用 `uploadFile(objName, fileName)` | 参数尾部有默认值，签名兼容 |
| **适配器** | 旧调用 `settings.ALIYUN_OSS_SERVICE["BucketName"]` | 派生别名仍存在 |
| **旧数据** | 改造前落库的记录（无 `storageBucket` / `bucketCode`） | `resolveBucketBySnapshot` 回落默认桶 → 读得到（前提：默认桶=改造前的那个桶） |
| **旧数据** | SELFFILE 旧 `.info`（无新字段） | `dict.get` 取默认值，不报错 |
| **STS** | 加桶后临时凭据 | `Resource` 由 `_genStsResource(_BUCKETS)` 自动展开全桶 |
| **默认桶一致性** | 必须保证「改造后的默认桶物理名 == 改造前的唯一桶」 | 这是**旧数据可读的唯一前提**，写入上线检查清单 |
| **回滚** | 需要退回单桶 | 删除 `Buckets` 相关键、恢复 `BucketName` 字面值；适配器因参数均有默认值可保留 | 
| **跨环境** | `_SYS` 切换 | 各环境 `Buckets` 独立定义，默认桶可不同 |

> ⚠️ **红线**：**默认桶的物理名在改造前后必须保持不变**。若必须变更，需先做「存量 fileID 的桶归属回填」，否则历史文件大面积不可读。

---

## 6. 关键设计决策（需确认）

| # | 决策点 | 选项 | 建议 |
|---|---|---|---|
| 6.1 | `bucketCode` 的命名 | 业务域命名（`media`/`artifact`/`public`）vs 环境命名 | **业务域命名**，与 `ch_asset` 用途对齐 |
| 6.2 | `privateFlag` 与 `bucketCode` 的优先级 | ① `bucketCode` 优先，`privateFlag` 仅作 fallback；② 两者互斥（同时传报错） | **①**，保证旧调用零改动 |
| 6.3 | ALIOSS 是否补 `privateFlag` 形参 | 补（接受并忽略，语义对齐）vs 不补（维持现状 + 文档标注） | **补形参并忽略**，消除「传了没用」的隐式陷阱 |
| 6.4 | 未知 `bucketCode` 的处理 | 静默回落默认桶 vs 报错 | **报错**（写错桶的代价远高于报错） |
| 6.5 | SELFFILE 是否同步多根 | 同步支持（`SELF_FILE_SERVER_STORAGE_DIR` 支持 `Buckets` 映射）vs 仅预留 | **仅预留**：`fileSystem=SELFFILE` 时 `bucketCode` 一律解析为 `default`，本地多根列入后续 |
| 6.6 | 是否新增 `F9A0` 诊断命令 | 新增 vs 不加 | **新增**（只读、非破坏，运维价值高） |
| 6.7 | 路径前缀 vs 多桶 | 单桶多前缀已能满足隔离诉求 | **两者都支持**：小规模用前缀，物理隔离用多桶 |

---

## 7. 测试验证步骤

### 7.1 单元测试

| # | 用例 | 期望 |
|---|---|---|
| U1 | `getBucketInfo("ALIOSS", bucketCode="media")` | 返回 `media` 物理桶名 + `PathPrefix="media/"` |
| U2 | `getBucketInfo("ALIOSS")`（不传） | 返回 `DefaultBucketCode` 对应桶 |
| U3 | `getBucketInfo("TENCENT", privateFlag=True)` | 返回 `private` 桶（与旧行为一致） |
| U4 | `getBucketInfo("TENCENT", privateFlag=False)` | 返回 `public` 桶（与旧行为一致） |
| U5 | `getBucketInfo("ALIOSS", bucketCode="media", privateFlag=True)` | `bucketCode` 优先（决策 6.2①） |
| U6 | 未知 `bucketCode` | 抛错 / 返回明确错误码（决策 6.4） |
| U7 | `_genStsResource` | `Resource` 包含**全部**桶的 ARN（含 `/*`），数量 = 桶数 × 2 |
| U8 | `resolveBucketBySnapshot("ALIOSS", storageBucket="contenthub-media")` | 反查出 `bucketCode="media"` |
| U9 | `resolveBucketBySnapshot` 快照为空 | 回落默认桶 |

### 7.2 集成测试

| # | 场景 | 步骤 | 期望 |
|---|---|---|---|
| I1 | **一致性回归（最关键）** | 不传 `bucketCode`，走完整 F0A0 → F7A0 → F2A0 | 与改造前完全一致：落默认桶、URL 可取、删除成功 |
| I2 | 多桶写入 | 分别以 `bucketCode=default/media/artifact/public` 各上传 1 个文件 | 4 个物理桶内各自出现对象，`storageBucket` 返回正确 |
| I3 | 路径前缀 | `bucketCode=media` 上传 | 对象键为 `media/xxx` |
| I4 | 快照读取 | 用 I2 的 4 个 fileID 调 F7A0 | 全部取到正确 URL（验证按快照路由） |
| I5 | 同名校验 | 两个桶使用**相同 objectName** | 各自独立存在，互不覆盖 |
| I6 | 删除路由 | 对 `media` 桶的文件调 F2A0 | 仅删除 `media` 桶对象，默认桶不受影响 |
| I7 | 文件信息 | F6A0 / F8A0 对多桶文件 | 均返回正确元信息 |
| I8 | 长图跨桶 | F4A0 输入取自 `media`、输出落 `artifact` | 合并成功，产物落在指定桶 |
| I9 | 旧数据读取 | 用改造前落库的 fileID（无桶快照） | 回落默认桶，读取成功 |
| I10 | STS 上传 | 用 `genSTSToken` 获取临时凭据上传到 `media` 桶 | 上传成功（验证 Resource 全桶展开） |
| I11 | 未知桶拒绝 | 传 `bucketCode="notexist"` | 返回明确错误，**未产生任何对象** |
| I12 | 三后端一致性 | 同用例依次在 `FILE_SYSTEM_MODE=ALIOSS / TENCENT / SELFFILE` 执行 | 前两者通过；SELFFILE 全部落 `default`（6.5 预留） |
| I13 | `F9A0` 诊断 | 调用诊断命令 | 返回当前环境桶清单（码/物理名/前缀/访问属性），无密钥泄露 |

### 7.3 回归与验收

| # | 检查项 | 方式 | 期望 |
|---|---|---|---|
| A1 | 现有调用方零改动可跑 | 全局搜索 `uploadFile(` / `genFileTempUrl(` 调用点，不做任何修改 | 全部正常（默认参数生效） |
| A2 | 配置向后兼容 | `python -c "from config import aliyunSettings as a; print(a.ALIYUN_OSS_SERVICE['BucketName'])"` | 输出默认桶物理名，非空 |
| A3 | 适配器常量兼容 | `python -c "from common import aliyunOSS as o; print(o.BucketNamePrivate)"` | 与 A2 一致 |
| A4 | 全链路冒烟 | contentHub 主计划 7.4 节 E2E 步骤 2（上传素材） | 通过 |
| A5 | 回滚演练 | 临时移除 `Buckets`，仅保留 `BucketName` | 服务可启动、默认桶读写正常 |

---

## 8. 风险与回滚

| # | 风险 | 等级 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | **默认桶物理名变更导致历史文件不可读** | 高 | 大面积读失败 | 红线：默认桶物理名**不得变更**；变更须先回填桶归属 |
| R2 | 读到未授权桶 → 权限报错 | 中 | 单文件操作失败 | I11 + 启动期校验：加载配置时逐桶 `head_object` 探活 |
| R3 | STS `Resource` 漏配新桶 | 中 | 临时凭据上传被拒 | `_genStsResource` 自动展开 + U7 断言 |
| R4 | 适配器参数追加破坏既有位置参数调用 | 中 | 调用错位 | **只在尾部追加**且给默认值；A1 全局搜索核对 |
| R5 | TENCENT `privateFlag` 语义漂移 | 中 | 文件进错桶 | U3/U4 锁死旧语义；6.2 决策① |
| R6 | 配置结构升级导致其他模块 import 失败 | 中 | 启动失败 | 保留全部旧键作为派生别名；A2/A3 验收 |
| R7 | 误传 `bucketCode` 写错桶 | 低 | 数据分散 | 未知码报错 + `F9A0` 可查 + 审计留痕 |
| R8 | SELFFILE 语义不对齐引发误解 | 低 | 本地与线上行为不一致 | 文档显式标注（6.5）+ I12 覆盖 |

**回滚方案**：本方案所有改动均为「**尾部追加参数 + 新增配置键 + 保留旧键**」形态，回滚只需：

1. 配置层删除 `ALIYUN_OSS_BUCKETS` / `TECENT_COS_BUCKETS`，恢复 `BucketName` 字面值；
2. 适配器保留新函数（对旧调用无影响），或回退到上一版本包；
3. `ylwzRecvFiles.py` 回退版本包（协议扩展对旧调用方无破坏，可选择性保留）。

---

## 9. 工作量与排期

| 阶段 | 任务 | 交付物 | 工时 |
|---|---|---|---|
| S1-1 | 配置结构升级 + `bucketSettings.py` 解析器 | 三份 config 可加载、解析器单测 | 1.0 |
| S1-2 | `aliyunOSS.py` 改造（A1–A7） | 支持 `bucketCode` 的 OSS 适配器 | 1.5 |
| S1-3 | `tencentCOS.py` 改造（B1–B5） | 支持 `bucketCode` 的 COS 适配器 | 1.0 |
| S1-4 | `ylwzRecvFiles.py` 协议扩展 + 落库快照（C1–C4） | 写入侧多桶 | 1.5 |
| S1-5 | 读/删/信息/合并路由改造（C5–C8）+ `F9A0`（C9） | 读取侧多桶 | 1.0 |
| S1-6 | 三后端联调 + 一致性与兼容性回归（I1–I13、A1–A5） | 联调与回归报告 | 1.0 |
| | | **合计** | **7.0 人天** |

**排期建议**：与主计划 **Phase 0 · T7（文件门面 + 三后端联调）并行**推进；S1-1/S1-2/S1-3 与 T7 同周完成，S1-4~S1-6 紧随其后。若资源紧张，可**只做 S1-1~S1-3**（配置 + 适配器具备多桶能力，服务协议暂不扩展），工时压缩至 3.5 人天。

---

## 10. 与主计划的关系

| 维度 | 说明 |
|---|---|
| **依赖方向** | 主计划 **Phase 0 · T7**（`fileStorageCommon.py` 门面 + 三后端联调）→ **并行** S1；S1 是 T7 的**上游能力增强**，不是 T7 的前置 |
| **被谁依赖** | C3 素材图库（多桶落点）、C5 平台适配（产物独立落桶）、`ch_artifact` 产物管理（产物与大图分桶，控制成本与保留期） |
| **阻塞性** | **不阻塞主干**。主计划 Phase 0–3 全部按单桶可跑；S1 完成后才启用多桶 |
| **优先级** | **P1**。与 Phase 0 并行；若与主干冲突，主干优先，S1 顺延至 Phase 1 内完成 |
| **与三条红线的关系** | 强化 **R2（配置驱动）**：多桶能力本身就是「配置驱动多态」的延伸，不得引入任何硬编码桶分支 |
| **对主计划的影响** | 主计划 3.3.3 节的适配器 shim（D2）在 S1 落地后由「参数适配」升级为「参数适配 + 桶解析」，`fileStorageCommon` 签名追加尾部可选参数 `bucketCode` |

---

> 编制日期：2026-09-17 ｜ 基线实测：`ylwzProject/museum/code/src`（只读核实，事实条目见第 1.2 节，均带行号）
> 关联文档：`plan/contentHub开发计划.md`（主计划）、`plan/chAPIPost分拆方案.md`（另一支线）
