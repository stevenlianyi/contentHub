#! /usr/bin/env python3
#encoding: utf-8:

#Filename: complianceService.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 合规校验业务服务(C8, SP3c · Phase 2, 主计划 2.2 / 2.6.3 / 7.2 U-11~U-14)。

#职责(横切两条入口, 统一产出「问题清单」):
#  1) C2 输入校验侧: 提交/渲染前的**前置拦截** —— 平台规格(标题/摘要上限、封面规格、正文图规格、图片数量上限)、
#     swipe 专项(2.6.3: 比例统一/张数/单张大小/格式/超长整图)、敏感词、AI 内容标识、发布频率限流;
#  2) C5 产物校验侧: 渲染产物(products)与平台规格的一致性(fileID 齐备 / 尺寸 / 单张大小 / 数量)。
#
#★ 规则单一来源(硬约束, 禁止第二张规则表):
#  - 平台规格一律**复用** processor/platformAdapter/base.py::checkPlatformSpec(数据源 ch_platform);
#  - swipe 专项一律**复用** processor/platformAdapter/xiaohongshu.py::validateSwipeSpec(主计划 2.6.3 的唯一定义处);
#  - 本文件只做「前置拦截调用 + 把结果归一为问题清单」, 不重写任何规格判定逻辑。
#
#★ 问题清单结构(主计划 7.2 U-11/U-12, 前端可直接消费):
#  每项 = {"field" 字段, "location" 位置(可含下标/偏移), "level" ERROR/WARN, "errCode" contenthub 段,
#          "message" 说明, "source" 来源}; 敏感词项另附 offsetStart/offsetEnd/matchedWord(供前端直接高亮)。
#
#★ 发布频率限流(主计划 7.2 U-14) + Redis 降级(本机无 Redis 服务端):
#  按账号维度计数(Redis INCR + EXPIRE); **Redis 不可用时不拒绝、不崩溃**, 降级为**进程内计数**,
#  显式置 degraded="1" 并记告警日志(关键路径不得因 Redis 不可用而阻塞)。
#
#★ 错误码(contenthub msgKey; 见 code/src/plan.md §4): C 段字段校验 / D 段文件素材 / E 段渲染产物;
#  **F 段(F0-F9 投递)本轮不占用** —— 限流超限落 C6(计数超上限), 不落 F2。
#
#★ 分层契约(强制单向): 接入层(main/) -> 业务层(processor/) -> 引擎层(engine/) -> 公共层(common/)
#  本文件属业务处理器层, 只依赖 processor/ 同层(renderService/topicService/assetService/platformAdapter)、
#  engine/(layoutEngine) 与 common/; **严禁 import main/subfunc**(接入层)。
#
#★ 零对外网络: 只读 ch_platform/ch_topic/附图与 Redis 计数, 不调任何平台接口、不做投递(投递归 SP4)。

_VERSION="20260919"


import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../code/src
if parentdir not in sys.path:
    sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import re
import threading
import time
import traceback

#global defintion/common var etc.
from common import globalDefinition as comGD

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#Redis 唯一入口(红线: 只经 common/redisCommon.py; 本文件不直连)
from common import redisCommon as comDB

#业务层同层服务(取主题/附图/平台记录复用渲染编排的既有取数实现, 不重复造第二份)
from processor import renderService

#平台适配契约(规格校验唯一定义处)
from processor.platformAdapter import base

#引擎层: specJson 解析(layoutType/size/sliceHeight)
from engine import layoutEngine


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    try:
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None


#===== 错误码与常量 begin =====

ERR_OK = "B0"
ERR_FIELD_MISSING = "C4"
ERR_FIELD_TOO_LONG = "C5"
ERR_FIELD_OUT_OF_RANGE = "C6"     #计数/数量超上限(含发布频率超限)
ERR_FIELD_INVALID = "C7"          #取值非法(含敏感词命中)
ERR_IMAGE_SPEC = "D1"             #图片尺寸/大小不符
ERR_FILE_TYPE = "D0"              #文件类型不允许
ERR_FILE_NOT_FOUND = "D4"         #产物文件缺失
ERR_RENDER_FAILED = "E1"
ERR_ARTIFACT_FAILED = "E3"        #超长整图须先切分

#问题级别
ISSUE_LEVEL_ERROR = "ERROR"       #阻断发布
ISSUE_LEVEL_WARN = "WARN"         #提示(不阻断)

#问题来源(便于前端分类展示与排查)
SOURCE_PLATFORM_SPEC = "platform_spec"
SOURCE_SWIPE_SPEC = "swipe_spec"
SOURCE_OVERLONG_IMAGE = "overlong_image"
SOURCE_SENSITIVE_WORD = "sensitive_word"
SOURCE_AI_LABEL = "ai_label"
SOURCE_ARTIFACT_SPEC = "artifact_spec"
SOURCE_RATE_LIMIT = "rate_limit"

#敏感词默认词表(内容合规口径; 可按请求 dataSet.sensitiveWords 覆盖, 不写死在渲染链路)
#说明: 这是「内容规则」而非「平台规格规则」, 不违反「规格规则单一来源」约束(平台规格仍只来自 ch_platform)。
DEFAULT_SENSITIVE_WORD_LIST = [
    "违禁词示例", "绝对化用语示例", "敏感词样例", "内部资料", "未公开",
]

#AI 内容标识词(needAiLabelFlag=1 时, 正文/简介含其一即视为已标识)
AI_LABEL_MARKER_LIST = ["AI生成", "AI 生成", "AI辅助创作", "AI 辅助创作", "AI创作", "人工智能生成", "本内容由AI"]

#发布频率限流(账号维度; 主计划 7.2 U-14)
RATE_LIMIT_KEY = "contenthub.ratelimit.publish"
RATE_LIMIT_MAX_PUBLISH = 30       #窗口内最多发布次数
RATE_LIMIT_WINDOW_SECONDS = 3600  #窗口长度(秒)

#产物单张大小上限(小红书 2.6.3 口径: 20MB)
ARTIFACT_MAX_SIZE_MB = 20

#产物登记保留天数(仅为本轮写入 expireYMDHMS 字段; **过期清理任务归 SP4**)
ARTIFACT_EXPIRE_DAYS = 30

#敏感词扫描字段(字段名 -> 中文标签)
SENSITIVE_SCAN_FIELD_LIST = [
    ("title", "标题"), ("summary", "简介"), ("description", "正文"), ("author", "作者"),
]

#swipe 消息里的「第 N 张」定位(把校验输出映射回 assetList 下标)
_SWIPE_INDEX_PATTERN = re.compile(r"第\s*(\d+)\s*张")

#===== 错误码与常量 end =====


#===== 通用小工具 begin =====

def _toStr(value):
    """None/数字/任意 -> 去空白字符串"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _toInt(value, default = 0):
    try:
        return int(float(_toStr(value)))
    except Exception:
        return default


def _fieldLabel(fieldName):
    return f"{fieldName}(publishcheck)"


def _ok(data = None, errMsgList = None):
    return {"errCode": ERR_OK, "field": "", "errMsgList": errMsgList or [], "data": data or {}}


def _err(errCode, rtnField, errMsgList = None, data = None):
    return {"errCode": errCode, "field": rtnField, "errMsgList": errMsgList or [], "data": data or {}}


def _logWarn(message):
    if _LOG:
        _LOG.warning(f"W: PID:{_processorPID}, {message}")


def _logError(message):
    if _LOG:
        _LOG.error(f"PID:{_processorPID}, {message}")


def _issue(field, level, errCode, message, location = "", source = "", **extra):
    """构造统一问题项(问题清单的最小单元); extra 用于敏感词的偏移区间等附加信息"""
    item = {
        "field": _toStr(field),
        "location": _toStr(location) or _toStr(field),
        "level": _toStr(level) or ISSUE_LEVEL_ERROR,
        "errCode": _toStr(errCode),
        "message": _toStr(message),
        "source": _toStr(source),
    }
    for key, value in (extra or {}).items():
        item[key] = value
    return item

#===== 通用小工具 end =====


#===== 问题汇总 begin =====

def summarizeIssues(issues, data = None):
    """把问题清单归一为统一出参(可定位可计数):
        - passed = "1" 仅当无 ERROR 级问题(警告不阻断);
        - errCode/field 取**首个 ERROR**(无 ERROR 则 B0), errMsgList 为全部问题说明;
        - data 含 issues/passed/issueCount/errorCount/warningCount(供前端直接渲染)。
       出参: {"errCode","field","errMsgList","data"}。"""
    issues = [item for item in (issues or []) if isinstance(item, dict)]
    errorList = [item for item in issues if _toStr(item.get("level")) == ISSUE_LEVEL_ERROR]
    warnList = [item for item in issues if _toStr(item.get("level")) == ISSUE_LEVEL_WARN]

    resultData = dict(data or {})
    resultData.update({
        "passed": "0" if errorList else "1",
        "issueCount": len(issues),
        "errorCount": len(errorList),
        "warningCount": len(warnList),
        "issues": issues,
    })

    rtn = _ok(resultData)
    if errorList:
        rtn["errCode"] = _toStr(errorList[0].get("errCode")) or ERR_FIELD_INVALID
        rtn["field"] = _toStr(errorList[0].get("field"))
        rtn["errMsgList"] = [_toStr(item.get("message")) for item in issues]
    elif warnList:
        rtn["errMsgList"] = [_toStr(item.get("message")) for item in issues]

    return rtn


def _dedupeIssues(issues):
    """按 (level, errCode, field, location, message) 去重(平台规格与 swipe 校验会有合理重叠)"""
    result = []
    seen = set()
    for item in issues or []:
        if not isinstance(item, dict):
            continue
        key = (item.get("level"), item.get("errCode"), item.get("field"),
               item.get("location"), item.get("message"))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result

#===== 问题汇总 end =====


#===== 平台规格校验(★ 复用 base.checkPlatformSpec, 不新建规则表) begin =====

def checkPlatformSpecIssues(platformRecord, topicData, assetList):
    """平台规格校验 -> 问题清单。★ 规则一律来自 ch_platform, 由 base.checkPlatformSpec 统一判定
       (标题/摘要上限、封面 900x500、正文图规格、图片数量上限); 本函数只做结果归一。"""
    rtn = base.checkPlatformSpec(platformRecord, topicData, assetList)
    issues = []
    for item in (rtn.get("data") or {}).get("issues") or []:
        if not isinstance(item, dict):
            continue
        fieldLabel = _toStr(item.get("field"))
        issues.append(_issue(fieldLabel, ISSUE_LEVEL_ERROR, _toStr(item.get("errCode")),
                             _toStr(item.get("message")), fieldLabel, SOURCE_PLATFORM_SPEC))
    return issues

#===== 平台规格校验 end =====


#===== swipe 专项校验(★ 复用 xiaohongshu.validateSwipeSpec, 不复制规则) begin =====

def _resolveSwipeLocation(message, fallbackField):
    """把 swipe 校验消息里的「第 N 张」映射为 assetList 下标定位(便于前端跳转)"""
    matched = _SWIPE_INDEX_PATTERN.search(_toStr(message))
    if matched:
        try:
            index = int(matched.group(1)) - 1
            if index >= 0:
                return f"assetList[{index}]"
        except Exception:
            pass
    return _toStr(fallbackField)


def checkOverlongImageIssues(assetList, spec = None):
    """超长整图拦截(主计划 2.6.3): 单张高 > 单图上限(切片高/卡片高, 默认 1440)须先切分,
       **禁止直接上传超长整图**(会被平台强制缩放导致文字模糊) -> E3。"""
    spec = spec if isinstance(spec, dict) else {}
    cardWidth, cardHeight = layoutEngine.parseSize(spec.get("size"), layoutEngine.DEFAULT_CARD_SIZE)
    threshold = _toInt(spec.get("sliceHeight"), 0) or cardHeight or layoutEngine.DEFAULT_CARD_SIZE[1]

    issues = []
    for idx, item in enumerate(assetList or []):
        if not isinstance(item, dict):
            continue
        height = _toInt(item.get("height"), 0)
        if height > threshold:
            issues.append(_issue("specJson.sliceHeight", ISSUE_LEVEL_ERROR, ERR_ARTIFACT_FAILED,
                                 f"第 {idx + 1} 张图高 {height} 超单图上限 {threshold}, "
                                 f"须先按 {threshold} 切分(禁止直接上传超长整图)",
                                 f"assetList[{idx}]", SOURCE_OVERLONG_IMAGE))
    return issues


def checkSwipeIssues(layoutRecord, assetList, platformRecord = None, overrideSpec = None):
    """swipe 专项校验 -> 问题清单。
       ★ 比例统一(uniformRatio)/张数/单张大小/格式四项一律复用 xiaohongshu.validateSwipeSpec(2.6.3 唯一定义处);
         本函数额外补「超长整图须先切分」的前置拦截项(渲染期无此判定, 属 C8 前置闸门)。"""
    layoutRecord = layoutRecord if isinstance(layoutRecord, dict) else {}
    spec = layoutEngine.resolveSpec(layoutRecord, overrideSpec)

    normalized = base.normalizePlatformRecord(platformRecord)
    imageMaxCount = _toInt(normalized.get("imageMaxCount"), 0)

    issues = []
    try:
        #延迟导入: 适配器包内模块级只导入 base, 具体适配器按需加载(避免包内循环依赖)
        from processor.platformAdapter import xiaohongshu as swipeAdapter
        checkRtn = swipeAdapter.validateSwipeSpec(assetList, spec, imageMaxCount = imageMaxCount)
    except Exception as e:
        _logError(f"swipe 专项校验复用失败, errMsg:{e}, {traceback.format_exc()}")
        return [_issue("assetList", ISSUE_LEVEL_ERROR, ERR_RENDER_FAILED,
                       f"swipe 专项校验不可用: {str(e)}", "assetList", SOURCE_SWIPE_SPEC)]

    if checkRtn.get("errCode") != ERR_OK:
        errCode = _toStr(checkRtn.get("errCode"))
        fieldLabel = _toStr(checkRtn.get("field"))
        for message in checkRtn.get("errMsgList") or []:
            issues.append(_issue(fieldLabel, ISSUE_LEVEL_ERROR, errCode, _toStr(message),
                                 _resolveSwipeLocation(message, fieldLabel), SOURCE_SWIPE_SPEC))

    issues += checkOverlongImageIssues(assetList, spec)
    return issues

#===== swipe 专项校验 end =====


#===== 敏感词检测(命中词 + 偏移区间, 支持多命中) begin =====

def detectSensitiveWords(text, wordList = None):
    """敏感词检测: 返回全部命中(多命中), 每项 {"word","start","end"}(end 为开区间)。
       wordList 缺省用 DEFAULT_SENSITIVE_WORD_LIST; 空列表视为不检测。"""
    text = _toStr(text)
    if not text:
        return []

    if wordList is None:
        words = DEFAULT_SENSITIVE_WORD_LIST
    else:
        words = wordList if isinstance(wordList, (list, tuple)) else []

    hits = []
    for word in words:
        word = _toStr(word)
        if not word:
            continue
        start = text.find(word)
        while start >= 0:
            hits.append({"word": word, "start": start, "end": start + len(word)})
            start = text.find(word, start + len(word))

    hits.sort(key = lambda data: (data["start"], data["end"], data["word"]))
    return hits


def checkSensitiveWordIssues(topicData, wordList = None):
    """敏感词 -> 问题清单(含**偏移区间** offsetStart/offsetEnd, 供前端直接高亮)。
       扫描字段: title / summary / description / author(主计划 7.2 U-12)。"""
    topicData = topicData if isinstance(topicData, dict) else {}
    issues = []
    for fieldName, label in SENSITIVE_SCAN_FIELD_LIST:
        text = _toStr(topicData.get(fieldName))
        for hit in detectSensitiveWords(text, wordList):
            issues.append(_issue(f"{fieldName}(ch_topic)", ISSUE_LEVEL_ERROR, ERR_FIELD_INVALID,
                                 f"{label}命中敏感词 '{hit['word']}'(字符偏移 {hit['start']}-{hit['end']})",
                                 f"{fieldName}[{hit['start']},{hit['end']}]", SOURCE_SENSITIVE_WORD,
                                 offsetStart = hit["start"], offsetEnd = hit["end"], matchedWord = hit["word"]))
    return issues

#===== 敏感词检测 end =====


#===== AI 内容标识校验 begin =====

def checkAiLabelIssues(platformRecord, topicData):
    """AI 内容标识校验(主计划 7.2 U-11 的一部分, 也是平台红线):
        - ch_platform.needAiLabelFlag != "1" -> 不校验;
        - 标识存在性: topicData.aiLabel 非空 或 正文/简介含 AI 标识词(AI_LABEL_MARKER_LIST);
        - 缺标识: 内容声明 AI 参与(aiFlag="1") -> ERROR(阻断); 未声明 -> WARN(仍给出明确问题项)。"""
    normalized = base.normalizePlatformRecord(platformRecord)
    if _toStr(normalized.get("needAiLabelFlag")) != "1":
        return []

    topicData = topicData if isinstance(topicData, dict) else {}
    aiLabel = _toStr(topicData.get("aiLabel"))
    hasLabel = bool(aiLabel)
    if not hasLabel:
        blob = _toStr(topicData.get("summary")) + " " + _toStr(topicData.get("description"))
        for marker in AI_LABEL_MARKER_LIST:
            if marker in blob:
                hasLabel = True
                break
    if hasLabel:
        return []

    aiFlag = _toStr(topicData.get("aiFlag"))
    level = ISSUE_LEVEL_ERROR if aiFlag == "1" else ISSUE_LEVEL_WARN
    return [_issue("aiLabel(ch_topic)", level, ERR_FIELD_INVALID,
                   f"平台强制 AI 内容标识(needAiLabelFlag=1)但未检测到标识: 请填写 aiLabel 或在正文/简介加入标识词 "
                   f"({AI_LABEL_MARKER_LIST}); 当前 aiFlag={aiFlag or '未声明'}",
                   "aiLabel", SOURCE_AI_LABEL)]

#===== AI 内容标识校验 end =====


#===== 产物校验(C5 侧: 渲染产物 -> 平台规格一致性) begin =====

def checkArtifactIssues(products, platformRecord, topicData = None):
    """已渲染产物校验: fileID 齐备 / 尺寸符合 imageSpec / 单张大小 / 数量上限。
       用于 C5 产物侧(publishcheck 传入 dataSet.products)与复用命中前的产物探活。"""
    normalized = base.normalizePlatformRecord(platformRecord)
    specWidth, specHeight = base.parseSizeSpec(normalized.get("imageSpec"))
    imageMaxCount = _toInt(normalized.get("imageMaxCount"), 0)

    productList = products if isinstance(products, (list, tuple)) else []
    issues = []

    for idx, item in enumerate(productList):
        if not isinstance(item, dict):
            continue
        if not _toStr(item.get("fileID")):
            issues.append(_issue(f"products[{idx}].fileID", ISSUE_LEVEL_ERROR, ERR_FILE_NOT_FOUND,
                                 f"第 {idx + 1} 个产物缺少 fileID(未上传成功)", f"products[{idx}]",
                                 SOURCE_ARTIFACT_SPEC))
        width = _toInt(item.get("width"), 0)
        height = _toInt(item.get("height"), 0)
        if specWidth > 0 and specHeight > 0 and width > 0 and height > 0 \
                and (width, height) != (specWidth, specHeight):
            issues.append(_issue(f"products[{idx}].size", ISSUE_LEVEL_ERROR, ERR_IMAGE_SPEC,
                                 f"第 {idx + 1} 个产物尺寸 {width}x{height} 与平台规格 "
                                 f"{specWidth}x{specHeight} 不一致", f"products[{idx}]", SOURCE_ARTIFACT_SPEC))
        sizeBytes = _toInt(item.get("sizeBytes"), 0)
        if sizeBytes > ARTIFACT_MAX_SIZE_MB * 1024 * 1024:
            issues.append(_issue(f"products[{idx}].sizeBytes", ISSUE_LEVEL_ERROR, ERR_IMAGE_SPEC,
                                 f"第 {idx + 1} 个产物大小 {sizeBytes} 字节 超单张上限 {ARTIFACT_MAX_SIZE_MB}MB",
                                 f"products[{idx}]", SOURCE_ARTIFACT_SPEC))

    if imageMaxCount > 0 and len(productList) > imageMaxCount:
        issues.append(_issue("imageMaxCount(ch_platform)", ISSUE_LEVEL_ERROR, ERR_FIELD_OUT_OF_RANGE,
                             f"产物数 {len(productList)} 超平台上限 {imageMaxCount}",
                             "products", SOURCE_ARTIFACT_SPEC))
    return issues

#===== 产物校验 end =====


#===== 发布频率限流(账号维度; Redis 可降级) begin =====

_MEMORY_RATE_BUFFER = {}
_MEMORY_RATE_LOCK = threading.Lock()
_MEMORY_RATE_MAX_KEYS = 5000


def _redisCounterIncr(redisKey, windowSeconds):
    """Redis 计数: INCR 首次设置过期(账号+平台维度窗口计数)。
       只经 common/redisCommon.py 的封装句柄(红线), 不直连、不新增 key 结构之外的东西。"""
    counter = int(comDB.redisMainDB.incr(redisKey))
    if counter == 1:
        comDB.redisMainDB.expire(redisKey, int(windowSeconds))
    return counter


def _memoryCounterIncr(redisKey, windowSeconds):
    """进程内降级计数(Redis 不可用时使用): 固定窗口计数, 过期即重置。"""
    now = time.time()
    with _MEMORY_RATE_LOCK:
        if len(_MEMORY_RATE_BUFFER) > _MEMORY_RATE_MAX_KEYS:
            expiredKeys = [key for key, value in _MEMORY_RATE_BUFFER.items()
                           if now - value.get("windowStart", now) >= windowSeconds]
            for key in expiredKeys:
                _MEMORY_RATE_BUFFER.pop(key, None)
        bucket = _MEMORY_RATE_BUFFER.get(redisKey)
        if bucket is None or now - bucket.get("windowStart", now) >= windowSeconds:
            bucket = {"windowStart": now, "count": 0}
            _MEMORY_RATE_BUFFER[redisKey] = bucket
        bucket["count"] += 1
        return bucket["count"]


def checkPublishRateLimit(accountID, platformCode = "", limitCount = None, windowSeconds = None):
    """发布频率限流(主计划 7.2 U-14, 主计划 6.4 R-04 防误发/重复推送):
        - 按账号(+平台)维度计数: Redis INCR + EXPIRE;
        - ★ Redis 不可用 -> **降级为进程内计数**, degraded="1" 并记告警日志, **不拒绝、不崩溃**;
        - allowed="0" 仅表示计数超限(超限判定与后端无关, 降级后同样生效)。
       出参: {"accountID","platform","limitCount","windowSeconds","count","allowed","backend","degraded","errorMsg"}。"""
    accountID = _toStr(accountID) or "anonymous"
    platformCode = _toStr(platformCode) or "any"
    limitCount = _toInt(limitCount, RATE_LIMIT_MAX_PUBLISH) or RATE_LIMIT_MAX_PUBLISH
    windowSeconds = _toInt(windowSeconds, RATE_LIMIT_WINDOW_SECONDS) or RATE_LIMIT_WINDOW_SECONDS

    redisKey = f"{RATE_LIMIT_KEY}.{accountID}.{platformCode}"
    info = {
        "accountID": accountID, "platform": platformCode,
        "limitCount": limitCount, "windowSeconds": windowSeconds,
        "count": 0, "allowed": "1", "backend": "redis", "degraded": "0", "errorMsg": "",
    }

    try:
        count = _redisCounterIncr(redisKey, windowSeconds)
        info["backend"] = "redis"
        info["count"] = count
    except Exception as e:
        #★ 降级: 关键路径不得因 Redis 不可用而阻塞
        info["backend"] = "memory"
        info["degraded"] = "1"
        info["errorMsg"] = str(e)
        _logWarn(f"发布频率限流降级为进程内计数(Redis 不可用) accountID:{accountID}, "
                 f"platform:{platformCode}, errMsg:{e}")
        try:
            info["count"] = _memoryCounterIncr(redisKey, windowSeconds)
        except Exception as memErr:
            #进程内计数也异常时, 放行(enforce 失败不阻断发布), 但标记降级与错误
            info["count"] = 0
            info["errorMsg"] = f"{e}; memory fallback failed: {memErr}"
            _logError(f"发布频率限流进程内降级亦失败, 放行本次请求, errMsg:{memErr}")

    if limitCount > 0 and _toInt(info["count"], 0) > limitCount:
        info["allowed"] = "0"
    return info


def checkRateLimitIssues(rateLimitInfo):
    """限流结果 -> 问题清单(超限 -> ERROR C6; 降级 -> WARN 显式可见)"""
    if not isinstance(rateLimitInfo, dict):
        return []
    issues = []
    if _toStr(rateLimitInfo.get("degraded")) == "1":
        issues.append(_issue("rateLimit", ISSUE_LEVEL_WARN, ERR_FIELD_OUT_OF_RANGE,
                             f"发布频率限流已降级为进程内计数(Redis 不可用, degraded=1, backend="
                             f"{rateLimitInfo.get('backend')}); 未阻断本次校验",
                             "rateLimit", SOURCE_RATE_LIMIT))
    if _toStr(rateLimitInfo.get("allowed")) == "0":
        issues.append(_issue("rateLimit", ISSUE_LEVEL_ERROR, ERR_FIELD_OUT_OF_RANGE,
                             f"发布频率超限: 账号 {rateLimitInfo.get('accountID')} 在 "
                             f"{rateLimitInfo.get('windowSeconds')} 秒内已发布 {rateLimitInfo.get('count')} 次, "
                             f"超上限 {rateLimitInfo.get('limitCount')}",
                             "rateLimit", SOURCE_RATE_LIMIT))
    return issues

#===== 发布频率限流 end =====


#===== 合规评估(纯函数: 不触库/不触文件, 便于静态与冒烟验证) begin =====

def evaluateCompliance(topicData, assetList, platformRecord, layoutRecord = None, overrideSpec = None,
                       wordList = None, rateLimitInfo = None, products = None):
    """统一合规评估(C2 输入侧 + C5 产物侧), 产出「问题清单」出参。
       入参(全部由调用方取好后传入; 本函数不触库/不触文件 -> 可离线测试):
         topicData      主题记录(topicService 出参单条)
         assetList      附图列表(含 width/height/usageType/fileExt/origSizeBytes)
         platformRecord ch_platform 记录
         layoutRecord   可选 ch_layout 记录(决定是否走 swipe 专项校验)
         overrideSpec   可选渲染覆盖参数
         wordList       可选敏感词表(缺省 DEFAULT_SENSITIVE_WORD_LIST)
         rateLimitInfo  可选限流结果(checkPublishRateLimit 出参)
         products       可选已渲染产物(非 None 时做 C5 产物校验)
       出参: {"errCode","field","errMsgList","data"}。"""
    topicData = topicData if isinstance(topicData, dict) else {}
    assetList = assetList if isinstance(assetList, (list, tuple)) else []
    layoutRecord = layoutRecord if isinstance(layoutRecord, dict) else {}

    issues = []
    #1) 平台规格(唯一来源: ch_platform + base.checkPlatformSpec)
    issues += checkPlatformSpecIssues(platformRecord, topicData, assetList)

    #2) 版式专项: swipe 走 2.6.3 专项校验; 其余版式做超长整图前置拦截
    layoutType = _toStr(layoutRecord.get("layoutType")).lower()
    if layoutType == "swipe":
        issues += checkSwipeIssues(layoutRecord, assetList, platformRecord, overrideSpec)
    else:
        spec = layoutEngine.resolveSpec(layoutRecord, overrideSpec) if layoutRecord else {}
        issues += checkOverlongImageIssues(assetList, spec)

    #3) 敏感词(命中词 + 偏移区间)
    issues += checkSensitiveWordIssues(topicData, wordList)

    #4) AI 内容标识
    issues += checkAiLabelIssues(platformRecord, topicData)

    #5) 发布频率限流
    issues += checkRateLimitIssues(rateLimitInfo)

    #6) C5 产物侧(请求显式带了 products 才校验)
    if products is not None:
        issues += checkArtifactIssues(products, platformRecord, topicData)

    issues = _dedupeIssues(issues)

    normalized = base.normalizePlatformRecord(platformRecord)
    data = {
        "platformCode": _toStr(normalized.get("platformCode")),
        "layoutType": layoutType,
        "assetCount": len(assetList),
        "sensitiveHitCount": len([item for item in issues if item.get("source") == SOURCE_SENSITIVE_WORD]),
        "rateLimit": rateLimitInfo if isinstance(rateLimitInfo, dict) else {},
    }
    return summarizeIssues(issues, data)

#===== 合规评估 end =====


#===== 业务入口: publishcheck begin =====

def publishCheck(dataSet, sessionIDSet = None):
    """发布前合规校验(publishcheck): 取主题 + 附图(+可选版式/平台) -> 统一合规评估 -> 问题清单。
       入参(dataSet):
         topicID / recID / topicCode  必填(其一)
         platform                     可选平台编码; 缺省取 layoutCode 对应 ch_layout.platform
         layoutCode                   可选版式(提供时启用 swipe 专项校验)
         layoutType                   可选(无 layoutCode 时可直接指定, 如 "swipe")
         sensitiveWords               可选敏感词表(数组)
         products                     可选已渲染产物数组(触发 C5 产物校验)
         rateLimitCount / rateLimitWindow  可选限流阈值覆盖
         accountID / ownerID          可选限流归因账号(缺省取会话 loginID/主题 ownerID)
       出参: {"errCode","field","errMsgList","data"}, data 含 issues/passed/errorCount/warningCount 等。"""
    if not isinstance(dataSet, dict):
        dataSet = {}
    sessionIDSet = sessionIDSet if isinstance(sessionIDSet, dict) else {}

    #1) 取主题(复用渲染编排的取数实现, 不重复造第二份)
    topicRecord, errRtn = renderService._fetchTopic(dataSet)
    if errRtn is not None:
        return errRtn
    topicID = _toStr(topicRecord.get("recID"))

    #2) 取附图(失败不阻断: 无图版式仍可提交, 但记日志)
    assetList = []
    assetErr = None
    try:
        assetList, assetErr = renderService._fetchAssets(topicID)
    except Exception as e:
        assetErr = str(e)
    if assetErr is not None:
        _logWarn(f"publishcheck 附图查询失败(降级为空) topicID:{topicID}, errMsg:{assetErr}")
        assetList = []
    else:
        try:
            assetList = renderService._mergeAssetMeta(assetList)
        except Exception as e:
            _logWarn(f"publishcheck 附图元信息合并失败(降级) topicID:{topicID}, errMsg:{e}")

    #3) 版式(可选)
    layoutRecord = None
    layoutCode = _toStr(dataSet.get("layoutCode"))
    if layoutCode:
        try:
            layoutRecord = layoutEngine.loadLayoutRecord(layoutCode)
        except layoutEngine.LayoutEngineError as e:
            return _err(e.errCode, e.field or _fieldLabel("layoutCode"), [e.message])
    else:
        layoutType = _toStr(dataSet.get("layoutType")).lower()
        if layoutType:
            layoutRecord = {"layoutType": layoutType, "specJson": _toStr(dataSet.get("specJson"))}

    #4) 平台(请求 platform > ch_layout.platform)
    platformCode = _toStr(dataSet.get("platform")) or _toStr((layoutRecord or {}).get("platform"))
    if not platformCode:
        return _err(ERR_FIELD_INVALID, _fieldLabel("platform"),
                    ["平台未指定且版式未声明 platform: 请传 platform 或 layoutCode"])
    platformRecord, platformErr = renderService._fetchPlatformRecord(platformCode)
    if platformErr is not None:
        return platformErr

    #5) 渲染覆盖参数(与 topicrender 同一套键)
    overrideSpec = None
    for key in renderService.OVERRIDE_SPEC_KEYS:
        if dataSet.get(key):
            overrideSpec = dataSet.get(key)
            break

    #6) 限流(账号维度; Redis 不可用则降级, 不阻断)
    accountID = (_toStr(dataSet.get("accountID")) or _toStr(dataSet.get("ownerID"))
                 or _toStr(sessionIDSet.get("loginID")) or _toStr(topicRecord.get("ownerID")))
    rateLimitInfo = checkPublishRateLimit(accountID, platformCode,
                                          dataSet.get("rateLimitCount"), dataSet.get("rateLimitWindow"))

    #7) 统一评估
    wordList = dataSet.get("sensitiveWords")
    products = dataSet.get("products")
    rtn = evaluateCompliance(topicRecord, assetList, platformRecord, layoutRecord, overrideSpec,
                             wordList = wordList, rateLimitInfo = rateLimitInfo, products = products)

    data = rtn.get("data") or {}
    data.update({
        "topicID": topicID,
        "topicCode": _toStr(topicRecord.get("topicCode")),
        "layoutCode": layoutCode or _toStr(dataSet.get("layoutType")),
        "platform": platformCode,
        "accountID": accountID,
        "rateLimit": rateLimitInfo,
        "checkedAt": misc.getTime(),
    })
    rtn["data"] = data
    return rtn

#===== 业务入口结束 =====


if __name__ == "__main__":
    pass
    #本地自测(不连库/不连 Redis): 只验证纯函数与降级路径
    print("DEFAULT_SENSITIVE_WORD_LIST:", DEFAULT_SENSITIVE_WORD_LIST)
    print("detectSensitiveWords:", detectSensitiveWords("这里有敏感词样例和敏感词样例", ["敏感词样例"]))
    print("rateLimit(degraded?):", checkPublishRateLimit("demo", "xiaohongshu"))
