#! /usr/bin/env python3
#encoding: utf-8:

#Filename: renderService.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 渲染业务服务(SP2c · C4 版式引擎 / SP3a · C5 平台适配 / SP3b 小红书产物 /
#               SP3c · 渲染任务化 + 产物台账)。

#职责(纯业务, 不涉 HTTP 报文封装):
#  1) 按 topicID/topicCode 经 topicService 取主题(出参);
#  2) 按 topicID 经 assetService 取附图列表(出参), 并可选合并 ch_asset 的 width/height 元信息
#     (swipe 比例统一校验 / 长图切片 / 平台规格校验需要);
#  3) 读 ch_layout(版式定义)与 ch_platform(平台能力矩阵);
#  4) ★ SP3a: 经 processor/platformAdapter 的适配器把引擎产物转为**平台形态产物**(适配器只做形态转换);
#  5) ★ SP3b: 小红书等多产物平台出参 products / fileIDs(经 chCommon.fillFileUrls 转 URL);
#  6) ★ SP3c(P2-6/P2-7): **渲染任务化 + 产物台账** ——
#       - ch_render_job: 状态机 PENDING->RUNNING->DONE/FAILED(非法跃迁拒绝并回显允许集);
#         **同步渲染也建 job(state=DONE)**, 使 ch_artifact 的 jobID 有值, sync/job 共用台账键;
#         renderMode="job" 提交后立即返回 jobCode + PENDING, 由 schedule/renderWorker.py 异步完成(worker 调 executeJob);
#       - inputHash = 渲染输入快照 sha256(主题关键字段 + 附图列表 + layoutCode + platform + spec);
#         命中相同 inputHash 的既有 DONE 任务 -> **复用既有产物**(不重复渲染), 复用行为写进出参与日志;
#       - ch_artifact: artifactKey = {jobID}:{kind}:{platform}:{seqNo} 幂等(主计划 3.4.5),
#         经 chCommon.upsertByUniqueKey 写入; 同 job 重渲染 -> artifactVer +1;
#         **过期清理任务归 SP4**, 本轮只写 artifactStatus(READY/EXPIRED) 与 expireYMDHMS 字段。
#
#★ 分层契约(强制单向): 接入层(main/) -> 业务层(processor/) -> 引擎层(engine/) -> 公共层(common/)
#  本文件是「业务层 -> 引擎层 / 业务层 -> 适配层」的唯一连接点: 引擎层与适配层均不反向依赖接入层。
#
#★ 零对外网络: 不做图片转存、不做投递(deliver 一律显式「未实现」, 投递归 SP4)。
#
#返回契约(供 main/subfunc/renderApi.py 直接映射为 HTTP 报文):
#  {"errCode": <"B0"=通过 / C·E 段错误码>, "field": <出错字段描述>, "errMsgList": [<原因>], "data": {...}}
#
#错误码落点(均为 common/errMsgCommon.py 的 contenthub 消息键):
#  C2 renderMode 未支持(显式未实现) | C4 必填缺失 | C7 平台取值非法/无适配器/任务状态非法跃迁 | CB 无此记录
#  CG 任务/台账写入失败 | E0 模板缺失 | E1 渲染失败 | E2 截图超时 | E3 产物生成失败 | E4 外链图片需转存但凭据缺失
#
#★ 2026-09-24 手改(修复「任务 DONE 但 ch_artifact 为空 / 前端『查看产物』空态」):
#  现象: 公众号(wechat_mp)/通用(generic)的 outputKind 为文档类(html/json), 适配器只回 content 不产 products,
#        而 ch_artifact 的写入以 products 非空为门控 -> 台账恒为空(仅图集平台 png 才有产物)。
#  1) 文档类形态产物登记: 渲染成功后把 content 落文件服务, 登记**单件**产物(kind=html/json, seqNo=1),
#     与图集平台共用 saveArtifacts 一条写入路径(artifactKey 幂等口径不变);
#  2) 主题状态自动推进: 渲染成功且主题当前为 RENDERING -> 经 topicService 状态机推进到 RENDERED。
#  两项均为**降级不阻断**: 落盘/上传/状态推进失败只记告警, 绝不把已成功的渲染判为失败。

_VERSION="20260924"


import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../code/src
if parentdir not in sys.path:
    sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import datetime
import hashlib
import json
import tempfile
import time
import traceback
import uuid

#global defintion/common var etc.
from common import globalDefinition as comGD

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#数据层唯一入口(红线 R1): 本文件读写 ch_platform / ch_render_job / ch_artifact(平台矩阵与渲染任务台账)
from common import mysqlCommon as comMysql

#Redis 唯一入口(红线: 只经 common/redisCommon; 渲染队列投递 CH_RENDER 用)
from common import redisCommon as comDB

#跨域业务公共件(幂等写入 upsertByUniqueKey + fileID -> URL)
from common import chCommon as comCh

#业务层同层服务(不触库/不触文件, 各自只经 common/)
from processor import topicService

from processor import assetService

#平台适配层(SP3a · C5): 只做「形态转换」, 平台差异隔离在 processor/platformAdapter/*
from processor import platformAdapter

#引擎层唯一渲染入口(单向依赖: processor -> engine)
from engine import layoutEngine

#引擎层产物上传/校验值(2026-09-24 手改): 文档类形态(html/json)产物落盘后经引擎层文件门面
#uploadArtifact 上传(红线 R2: 本文件不直连任何云厂商 SDK)
from engine import htmlToImage


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    try:
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
        # _LOG = misc.setLogNew(comGD._DEF_LOG_CH_RENDER_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None


#===== 错误码与常量 begin =====

ERR_FIELD_MISSING = "C4"
ERR_FIELD_INVALID = "C7"
ERR_NO_RECORD = "CB"
ERR_NOT_IMPLEMENTED = "C2"      #未支持的 renderMode(显式未实现, 不静默)
ERR_RENDER_FAILED = "E1"
ERR_DB_FAILED = "CG"            #渲染任务/产物台账写入失败(复用 contenthub「记录添加失败」)

#渲染覆盖参数允许透传的键(dataSet.specOverride / overrideSpec)
OVERRIDE_SPEC_KEYS = ["specOverride", "overrideSpec", "specJson"]

#★ 渲染任务模式(plan.md §4): sync = 同步渲染(仍建 job, 终态 DONE); job = 异步(提交后由 worker 执行)
SUPPORTED_RENDER_MODE_LIST = ["sync", "job"]
RENDER_MODE_SYNC = "sync"
RENDER_MODE_JOB = "job"

#★ 渲染任务状态机(主计划 2.1 六步链路 / 3.4 ch_render_job):
#  PENDING -> RUNNING -> DONE/FAILED; FAILED 允许重新入队(PENDING)进行重试; DONE 为终态。
JOB_STATUS_LIST = ["PENDING", "RUNNING", "DONE", "FAILED"]
JOB_STATUS_INITIAL = "PENDING"
JOB_STATUS_TRANSITIONS = {
    "PENDING": ["RUNNING", "FAILED"],
    "RUNNING": ["DONE", "FAILED"],
    "DONE":    [],
    "FAILED":  ["PENDING"],
}

#产物台账状态(主计划 P2-6: READY/EXPIRED; **过期清理归 SP4**, 本轮只写字段)
ARTIFACT_STATUS_LIST = ["READY", "EXPIRED"]
ARTIFACT_STATUS_READY = "READY"
ARTIFACT_STATUS_EXPIRED = "EXPIRED"
ARTIFACT_KIND_PNG = "png"
ARTIFACT_EXPIRE_DAYS = 30

#★ 2026-09-24 手改(文档类形态产物登记): kind 取 ch_artifact.kind 的合法值
#  (database/ch_artifact.txt: html或png或zip或json或markdown —— markdown 为 2026-09-24 新增取值,
#   授权来源: 通用平台(ch_platform=generic)的 exportKind=markdown 形态需要产物留痕)。
#  其它未登记的 outputKind 无对应 kind -> 不登记(显式告警, 不写非法 kind)。
ARTIFACT_KIND_HTML = "html"
ARTIFACT_KIND_JSON = "json"
ARTIFACT_KIND_MARKDOWN = "markdown"
OUTPUT_KIND_ARTIFACT_MAP = {
    "html": (ARTIFACT_KIND_HTML, ".html"),
    "json": (ARTIFACT_KIND_JSON, ".json"),
    "markdown": (ARTIFACT_KIND_MARKDOWN, ".md"),
}

#文档类产物的包裹模板(适配器出参是 embedMode 片段, 补 charset/viewport 后可独立打开;
#  占位符用 {{X}} 而非 str.format —— 产物正文含内联样式的 { } 花括号, format 会被误解析)
HTML_DOC_TEMPLATE = (
    "<!DOCTYPE html>\n"
    "<html lang=\"zh-CN\">\n"
    "<head>\n"
    "<meta charset=\"utf-8\"/>\n"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>\n"
    "<meta name=\"generator\" content=\"contentHub\"/>\n"
    "<meta name=\"ch-platform\" content=\"{{PLATFORM}}\"/>\n"
    "<title>{{TITLE}}</title>\n"
    "</head>\n"
    "<body>\n"
    "{{CONTENT}}\n"
    "</body>\n"
    "</html>\n"
)

#主题状态口径(与 ch_topic.status / topicService.TOPIC_STATUS_LIST 一致):
#  渲染成功: RENDERING -> RENDERED(自动推进; 只经 topicService, 业务层不直写 ch_topic)
#  渲染失败: RENDERING -> DRAFT(自动回落, 修正后可重新提交; 状态机允许该跃迁)
TOPIC_STATUS_RENDERING = "RENDERING"
TOPIC_STATUS_RENDERED = "RENDERED"
TOPIC_STATUS_DRAFT = "DRAFT"

#同步 job 的进度标记(0 = 未设置口径之外, 进度百分比)
JOB_PROGRESS_RUNNING = 10
JOB_PROGRESS_DONE = 100

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


def _ok(data = None, errMsgList = None):
    """业务成功返回"""
    return {"errCode": "B0", "field": "", "errMsgList": errMsgList or [], "data": data or {}}


def _err(errCode, rtnField, errMsgList = None, data = None):
    """业务失败返回(可携带回显数据)"""
    return {"errCode": errCode, "field": rtnField, "errMsgList": errMsgList or [], "data": data or {}}


def _fieldLabel(fieldName):
    return f"{fieldName}(topicrender)"


def _logWarn(message):
    if _LOG:
        _LOG.warning(f"W: PID:{_processorPID}, {message}")


def _logError(message):
    if _LOG:
        _LOG.error(f"PID:{_processorPID}, {message}")


def _futureYMDHMS(days):
    """当前时间 + days 天, 输出 14 位 YYYYMMDDHHMMSS(产物保留到期时间字段用)"""
    try:
        target = datetime.datetime.now() + datetime.timedelta(days = int(days or 0))
        return target.strftime("%Y%m%d%H%M%S")
    except Exception:
        return misc.getTime()

#===== 通用小工具 end =====


#===== 渲染任务状态机 begin =====

def checkJobStatusTransition(currStatus, newStatus):
    """渲染任务状态机校验。返回 (errCode, rtnField, errMsg); 合法返回 ("", "", "")。
       规则(沿用 topicService.checkStatusTransition 的范式):
         - newStatus 不在枚举内    -> C7
         - newStatus == currStatus -> 合法(幂等更新)
         - currStatus 为空(首建)   -> 合法
         - 跃迁不在 JOB_STATUS_TRANSITIONS[currStatus] -> C7 并回显当前状态与允许跃迁集"""
    currStatus = _toStr(currStatus).upper()
    newStatus = _toStr(newStatus).upper()

    if not newStatus:
        return "", "", ""

    if newStatus not in JOB_STATUS_LIST:
        return (ERR_FIELD_INVALID, _fieldLabel("jobStatus"),
                f"jobStatus(渲染任务状态) 取值非法: {newStatus}, 允许值={JOB_STATUS_LIST}")

    if not currStatus:
        return "", "", ""

    if newStatus == currStatus:
        return "", "", ""

    allowList = JOB_STATUS_TRANSITIONS.get(currStatus, [])
    if newStatus not in allowList:
        return (ERR_FIELD_INVALID, _fieldLabel("jobStatus"),
                f"jobStatus(渲染任务状态) 非法跃迁: {currStatus} -> {newStatus}, "
                f"当前状态={currStatus}, 允许跃迁={allowList or '无(终态)'}")

    return "", "", ""

#===== 渲染任务状态机 end =====


#===== 渲染输入快照(inputHash) begin =====

def buildInputHash(topicRecord, layoutRecord, assetList, platformCode = "", overrideSpec = None):
    """渲染输入快照 sha256: 主题关键字段 + 附图列表 + layoutCode/layoutType + platform + 生效 spec。
       用途(主计划 P2-7): 命中相同 inputHash 的既有 DONE 任务 -> 复用既有产物, 不重复渲染。
       口径: 附图按 (sortOrder, fileID) 排序后取 fileID/尺寸/用途; spec 取 specJson 叠加 overrideSpec 后的生效值,
             故「内容未变 + 参数未变」必然得到同一摘要。"""
    topicRecord = topicRecord if isinstance(topicRecord, dict) else {}
    layoutRecord = layoutRecord if isinstance(layoutRecord, dict) else {}

    if layoutRecord:
        spec = layoutEngine.resolveSpec(layoutRecord, overrideSpec)
    elif isinstance(overrideSpec, dict):
        spec = dict(overrideSpec)
    else:
        spec = {}

    assetSnapshot = []
    for item in assetList or []:
        if not isinstance(item, dict):
            continue
        assetSnapshot.append({
            "fileID": _toStr(item.get("fileID")),
            "sortOrder": _toInt(item.get("sortOrder"), 100),
            "usageType": _toStr(item.get("usageType")) or "body",
            "width": _toInt(item.get("width"), 0),
            "height": _toInt(item.get("height"), 0),
        })
    assetSnapshot.sort(key = lambda data: (data["sortOrder"], data["fileID"]))

    snapshot = {
        "topicCode": _toStr(topicRecord.get("topicCode")),
        "title": _toStr(topicRecord.get("title")),
        "summary": _toStr(topicRecord.get("summary")),
        "description": _toStr(topicRecord.get("description")),
        "coverFileID": _toStr(topicRecord.get("coverFileID")),
        "aiFlag": _toStr(topicRecord.get("aiFlag")),
        "layoutCode": _toStr(layoutRecord.get("layoutCode")),
        "layoutType": _toStr(layoutRecord.get("layoutType")),
        "platform": _toStr(platformCode) or _toStr(layoutRecord.get("platform")),
        "spec": spec,
        "assets": assetSnapshot,
    }
    try:
        text = json.dumps(snapshot, sort_keys = True, ensure_ascii = False, default = str)
    except Exception:
        text = str(snapshot)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

#===== 渲染输入快照 end =====


#===== 取数: 主题 + 附图 begin =====

def _fetchTopic(dataSet):
    """经 topicService.queryTopic 取单条主题记录; 未命中返回 (None, errDict)"""
    topicID = _toStr(dataSet.get("topicID")) or _toStr(dataSet.get("recID"))
    topicCode = _toStr(dataSet.get("topicCode"))
    if not topicID and not topicCode:
        return None, _err(ERR_FIELD_MISSING, _fieldLabel("topicID"),
                          ["topicID 或 topicCode 为必填字段"])

    querySet = {"mode": "full"}
    if topicID:
        querySet["recID"] = topicID
    else:
        querySet["topicCode"] = topicCode

    rtn = topicService.queryTopic(querySet)
    if rtn.get("errCode") != "B0":
        return None, rtn

    dataList = (rtn.get("data") or {}).get("data") or []
    if not dataList:
        return None, _err(ERR_NO_RECORD, _fieldLabel("topicID"),
                          [f"无此主题记录: topicID={topicID}, topicCode={topicCode}"])

    return dataList[0], None


def _fetchAssets(topicID):
    """经 assetService.queryTopicAsset 取该主题附图列表(sortOrder 升序; 含图注/usageType/URL)"""
    if not topicID:
        return [], None

    rtn = assetService.queryTopicAsset({"topicID": topicID, "mode": "full"})
    if rtn.get("errCode") != "B0":
        return [], rtn

    dataList = (rtn.get("data") or {}).get("data") or []
    return dataList, None


def _mergeAssetMeta(assetList):
    """为附图列表补充 ch_asset 元信息(width/height/mimeType/origSizeBytes)。
       用途: swipe 比例统一校验(2.6.3)与长图切片需要尺寸; 失败逐条降级(不影响渲染主流程)。"""
    for item in assetList or []:
        if not isinstance(item, dict):
            continue
        fileID = _toStr(item.get("fileID"))
        if not fileID:
            continue
        try:
            rtn = assetService.queryAsset({"fileID": fileID, "mode": "full"})
            if rtn.get("errCode") != "B0":
                continue
            rows = (rtn.get("data") or {}).get("data") or []
            if not rows:
                continue
            meta = rows[0]
            for key in ("width", "height", "mimeType", "fileExt", "origSizeBytes", "thumbnailID", "thumbnailUrl"):
                value = meta.get(key)
                if value not in (None, "", 0, "0"):
                    item[key] = value
        except Exception as e:
            if _LOG:
                _LOG.warning(f"W: PID:{_processorPID}, mergeAssetMeta fileID:{fileID}, errMsg:{str(e)}")

    return assetList


def _fetchPlatformRecord(platformCode):
    """按 platformCode 读 ch_platform(只经 mysqlCommon; 红线 R1)。
       未命中 -> CB; 已停用 -> C7; 读取异常 -> E1。出参: (platformRecord, errDict)。"""
    platformCode = _toStr(platformCode)
    if not platformCode:
        return None, _err(ERR_FIELD_INVALID, _fieldLabel("platform"), ["platform 为空"])

    tableName = comMysql.tablename_convertor_ch_platform()
    try:
        dataList = comMysql.query_ch_platform(tableName, platformCode = platformCode, mode = "full")
    except Exception as e:
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, 平台配置读取失败 platformCode:{platformCode}, errMsg:{str(e)}")
        return None, _err(ERR_RENDER_FAILED, _fieldLabel("platform"),
                          [f"平台配置读取失败: platformCode={platformCode}, errMsg:{str(e)}"])

    if not dataList:
        return None, _err(ERR_NO_RECORD, _fieldLabel("platform"),
                          [f"无此平台配置记录: platformCode={platformCode}(请先执行 tools/initSeed.py)"])

    platformRecord = dataList[0]
    if _toStr(platformRecord.get("enabled")) == "0":
        return None, _err(ERR_FIELD_INVALID, _fieldLabel("platform"), [f"平台已停用: platformCode={platformCode}"])

    return platformRecord, None

#===== 取数结束 =====


#===== 渲染任务台账(ch_render_job) begin =====

def buildJobCode(platformCode, topicCode):
    """生成任务编码(jobCode 唯一键, VARCHAR(64), 幂等键)。
       形态: job_{platform}_{sha1(platform+topicCode)[:10]}_{YYYYMMDDHHMMSS}_{uuid8}; 长度受控 <= 64。"""
    platformCode = _toStr(platformCode) or "p"
    topicCode = _toStr(topicCode) or "t"
    digest = hashlib.sha1(f"{platformCode}_{topicCode}".encode("utf-8")).hexdigest()[:10]
    suffix = f"{misc.getTime()}_{uuid.uuid4().hex[:8]}"
    code = f"job_{platformCode[:12]}_{digest}_{suffix}"
    return code[:64]


def _insertJob(jobCode, topicID, layoutCode, platformCode, inputHash, ownerID = "", memo = ""):
    """建 ch_render_job 记录(初始 PENDING); 失败返回 0(不抛异常, 由调用方决定是否降级)。"""
    tableName = comMysql.tablename_convertor_ch_render_job()
    nowYMDHMS = misc.getTime()
    saveSet = {
        "jobCode": jobCode,
        "topicID": _toInt(topicID, 0),
        "layoutCode": _toStr(layoutCode),
        "platform": _toStr(platformCode),
        "jobStatus": JOB_STATUS_INITIAL,
        "inputHash": _toStr(inputHash),
        "progress": 0,
        "errMsg": "",
        "ownerID": _toStr(ownerID),
        "memo": _toStr(memo)[:200],
        "regID": _toStr(ownerID),
        "regYMDHMS": nowYMDHMS,
        "delFlag": "0",
    }
    try:
        recID = comMysql.insert_ch_render_job(tableName, saveSet)
        return _toInt(recID, 0)
    except Exception as e:
        _logError(f"渲染任务建档失败 jobCode:{jobCode}, errMsg:{e}, {traceback.format_exc()}")
        return 0


def _queryJobRecord(jobID):
    """按 recID 取单条任务记录; 返回 (record, errMsg)"""
    jobID = _toInt(jobID, 0)
    if jobID <= 0:
        return {}, "jobID 非法"
    tableName = comMysql.tablename_convertor_ch_render_job()
    try:
        rows = comMysql.query_ch_render_job(tableName, recID = jobID, mode = "full")
    except Exception as e:
        return {}, str(e)
    for row in rows or []:
        if isinstance(row, dict):
            return row, ""
    return {}, f"无此渲染任务记录: jobID={jobID}"


def getJobRecord(jobID):
    """按 recID 取渲染任务记录(供 schedule/renderWorker.py 消费 CH_RENDER 队列消息时回查完整记录);
       失败或不存在返回 {}。"""
    record, _errMsg = _queryJobRecord(jobID)
    return record if isinstance(record, dict) else {}


def _notifyRenderWorker(jobCode, jobID, topicID, layoutCode, platformCode, ownerID = ""):
    """投递渲染通知到 Redis 队列(CH_RENDER); 由 schedule/renderWorker.py 阻塞消费, 近实时触发渲染。

       ★ 降级: Redis 不可用 -> 仅告警、不抛不阻塞(任务已落 ch_render_job=PENDING,
         worker 的兜底轮询会补偿消费, 不丢任务); 与 transferCHMysql 的队列投递同口径。"""
    try:
        msg = {
            "jobCode": _toStr(jobCode),
            "recID": _toInt(jobID, 0),
            "topicID": _toStr(topicID),
            "layoutCode": _toStr(layoutCode),
            "platform": _toStr(platformCode),
            "ownerID": _toStr(ownerID),
        }
        rtn = comDB.putMsg2Queue(comGD._DEF_CH_MSG_QUEUE_RENDER_TITLE, msg)
        if _LOG:
            _LOG.info(f"渲染队列投递 jobCode:{jobCode}, recID:{jobID}, rtn:{rtn}")
    except Exception as e:
        _logWarn(f"渲染队列投递失败(降级为兜底轮询) jobCode:{jobCode}, recID:{jobID}, errMsg:{e}")


def updateJobStatus(jobID, newStatus, progress = None, errMsg = None, costMs = None,
                    startYMDHMS = None, finishYMDHMS = None):
    """状态机校验后更新任务状态(非法跃迁 -> C7 并回显当前状态与允许跃迁集)。
       出参: {"errCode","field","errMsgList","data"}; data.allowedTransitions 供前端/worker 参考。"""
    jobID = _toInt(jobID, 0)
    if jobID <= 0:
        return _err(ERR_DB_FAILED, _fieldLabel("jobID"), ["jobID 非法"])

    record, queryErr = _queryJobRecord(jobID)
    currStatus = _toStr((record or {}).get("jobStatus"))
    if queryErr:
        return _err(ERR_NO_RECORD, _fieldLabel("jobID"), [f"任务记录读取失败: {queryErr}"])

    errCode, rtnField, message = checkJobStatusTransition(currStatus, newStatus)
    if errCode:
        return _err(errCode, rtnField, [message],
                    {"jobID": jobID, "currentStatus": currStatus,
                     "allowedTransitions": JOB_STATUS_TRANSITIONS.get(currStatus, [])})

    saveSet = {"jobStatus": _toStr(newStatus).upper(), "modifyYMDHMS": misc.getTime()}
    if progress is not None:
        saveSet["progress"] = _toInt(progress, 0)
    if errMsg is not None:
        saveSet["errMsg"] = _toStr(errMsg)[:500]
    if costMs is not None:
        saveSet["costMs"] = _toInt(costMs, 0)
    if startYMDHMS:
        saveSet["startYMDHMS"] = _toStr(startYMDHMS)
    if finishYMDHMS:
        saveSet["finishYMDHMS"] = _toStr(finishYMDHMS)

    try:
        tableName = comMysql.tablename_convertor_ch_render_job()
        comMysql.update_ch_render_job(tableName, jobID, saveSet)
    except Exception as e:
        _logError(f"渲染任务状态更新失败 jobID:{jobID}, newStatus:{newStatus}, errMsg:{e}")
        return _err(ERR_DB_FAILED, _fieldLabel("jobStatus"), [f"任务状态更新失败: {str(e)}"])

    return _ok({"jobID": jobID, "jobStatus": _toStr(newStatus).upper(), "currentStatus": currStatus})


def _loadReadyArtifacts(jobID):
    """取某任务的 READY 产物台账(按 seqNo 升序); 失败降级为空(不阻断渲染)"""
    jobID = _toInt(jobID, 0)
    if jobID <= 0:
        return []
    tableName = comMysql.tablename_convertor_ch_artifact()
    try:
        rows = comMysql.query_ch_artifact(tableName, jobID = jobID,
                                          artifactStatus = ARTIFACT_STATUS_READY, mode = "full")
    except Exception as e:
        _logWarn(f"产物台账读取失败 jobID:{jobID}, errMsg:{e}")
        return []

    result = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        result.append({
            "seqNo": _toInt(row.get("seqNo"), 1),
            "kind": _toStr(row.get("kind")),
            "fileID": _toStr(row.get("fileID")),
            "thumbnailID": _toStr(row.get("thumbnailID")),
            "artifactKey": _toStr(row.get("artifactKey")),
            "artifactVer": _toInt(row.get("artifactVer"), 1),
            "artifactStatus": _toStr(row.get("artifactStatus")),
            "specNote": _toStr(row.get("specNote")),
            "sizeBytes": _toInt(row.get("sizeBytes"), 0),
        })
    result.sort(key = lambda data: data["seqNo"])
    return result


def findReusableJob(inputHash, topicID, platformCode):
    """按 inputHash 命中可复用的既有 DONE 任务(同主题+同平台); 命中且产物齐备 -> 返回复用信息, 否则 None。
       ★ 复用 = 不重复渲染(主计划 P2-7); 复用行为由调用方写入出参与日志。"""
    inputHash = _toStr(inputHash)
    topicID = _toInt(topicID, 0)
    if not inputHash or topicID <= 0:
        return None

    tableName = comMysql.tablename_convertor_ch_render_job()
    try:
        rows = comMysql.query_ch_render_job(tableName, topicID = topicID, platform = _toStr(platformCode),
                                            jobStatus = "DONE", mode = "full")
    except Exception as e:
        _logWarn(f"复用探测失败(inputHash 查询) topicID:{topicID}, errMsg:{e}")
        return None

    candidates = [row for row in (rows or [])
                  if isinstance(row, dict) and _toStr(row.get("inputHash")) == inputHash]
    candidates.sort(key = lambda data: _toInt(data.get("recID"), 0), reverse = True)

    for row in candidates:
        jobID = _toInt(row.get("recID"), 0)
        artifacts = _loadReadyArtifacts(jobID)
        if artifacts:
            return {"jobID": jobID, "jobCode": _toStr(row.get("jobCode")),
                    "inputHash": inputHash, "artifacts": artifacts}
    return None

#===== 渲染任务台账 end =====


#===== 产物台账(ch_artifact) begin =====

def buildArtifactKey(jobID, kind, platformCode, seqNo):
    """★ 产物幂等键(主计划 3.4.5): artifactKey = {jobID}:{kind}:{platform}:{seqNo}"""
    return f"{_toInt(jobID, 0)}:{_toStr(kind)}:{_toStr(platformCode)}:{_toInt(seqNo, 1)}"


def _queryArtifactByKey(tableName, artifactKey, jobID):
    """按幂等键在既有台账中定位(供 upsertByUniqueKey 的 queryFunc 使用):
       生成器不支持复合唯一键/ON DUPLICATE KEY, 故先按 jobID 收窄再由 artifactKey 精确匹配。"""
    artifactKey = _toStr(artifactKey)
    try:
        rows = comMysql.query_ch_artifact(tableName, jobID = _toInt(jobID, 0), mode = "full")
    except Exception as e:
        _logWarn(f"产物台账按键查询失败 artifactKey:{artifactKey}, errMsg:{e}")
        return []
    for row in rows or []:
        if isinstance(row, dict) and _toStr(row.get("artifactKey")) == artifactKey:
            return [row]
    return []


def saveArtifacts(jobID, topicID, platformCode, products, kind = "", expireDays = ARTIFACT_EXPIRE_DAYS):
    """把渲染产物登记到 ch_artifact(主计划 P2-6)。
       - 幂等: 走 chCommon.upsertByUniqueKey, 唯一键 = artifactKey = {jobID}:{kind}:{platform}:{seqNo};
       - artifactVer: 同 job 重渲染同一 artifactKey -> 既有版本 +1(初次写入为 1);
       - kind 缺省取产物记录里的 kind, 再回落 png;
       - ★ 过期清理任务不在本轮(归 SP4), 本函数只写 artifactStatus="READY" 与 expireYMDHMS。
       出参: [{"artifactKey","recID","artifactVer","fileID","seqNo"}]。"""
    jobID = _toInt(jobID, 0)
    topicID = _toInt(topicID, 0)
    platformCode = _toStr(platformCode)
    productList = products if isinstance(products, (list, tuple)) else []
    if jobID <= 0 or not productList:
        if jobID <= 0:
            _logWarn(f"saveArtifacts 跳过: jobID 非法(jobID={jobID}), 产物数={len(productList)}")
        return []

    tableName = comMysql.tablename_convertor_ch_artifact()
    nowYMDHMS = misc.getTime()
    expireYMDHMS = _futureYMDHMS(expireDays)
    savedList = []

    for index, product in enumerate(productList):
        if not isinstance(product, dict):
            continue
        seqNo = _toInt(product.get("seqNo"), index + 1) or (index + 1)
        productKind = _toStr(product.get("kind")) or _toStr(kind) or ARTIFACT_KIND_PNG
        artifactKey = buildArtifactKey(jobID, productKind, platformCode, seqNo)

        #版本递增: 命中既有同键记录 -> +1
        prevRows = _queryArtifactByKey(tableName, artifactKey, jobID)
        prevVer = _toInt(prevRows[0].get("artifactVer"), 0) if prevRows else 0
        artifactVer = prevVer + 1 if prevVer > 0 else 1

        width = _toInt(product.get("width"), 0)
        height = _toInt(product.get("height"), 0)
        saveSet = {
            "artifactKey": artifactKey,
            "jobID": jobID,
            "topicID": topicID,
            "kind": productKind,
            "platform": platformCode,
            "fileID": _toStr(product.get("fileID")),
            "thumbnailID": _toStr(product.get("thumbnailID")),
            "seqNo": seqNo,
            "artifactVer": artifactVer,
            "specNote": f"{width}x{height}" if width > 0 and height > 0 else _toStr(product.get("specNote")),
            "sizeBytes": _toInt(product.get("sizeBytes"), 0),
            "artifactStatus": ARTIFACT_STATUS_READY,
            "expireYMDHMS": expireYMDHMS,
            "regID": "",
            "regYMDHMS": nowYMDHMS,
            "delFlag": "0",
        }

        recID = comCh.upsertByUniqueKey(
            tableName, artifactKey, saveSet,
            lambda t, v, _jobID = jobID: _queryArtifactByKey(t, v, _jobID),
            comMysql.insert_ch_artifact,
            comMysql.update_ch_artifact)

        savedList.append({"artifactKey": artifactKey, "recID": _toInt(recID, 0),
                          "artifactVer": artifactVer, "fileID": saveSet["fileID"], "seqNo": seqNo})

    if _LOG and savedList:
        _LOG.info(f"PID:{_processorPID}, saveArtifacts jobID:{jobID}, platform:{platformCode}, "
                  f"count:{len(savedList)}, artifactVer:{savedList[0].get('artifactVer')}")
    return savedList

#===== 产物台账 end =====


#===== 文档类形态产物落盘与登记(2026-09-24 手改) begin =====

def _escapeHtmlText(text):
    """HTML 文本转义(只用于包裹文档的 title/platform, **不触碰产物正文**)"""
    return (_toStr(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _wrapHtmlDocument(content, title = "", platformCode = ""):
    """把平台形态片段包成**可独立打开**的 HTML 文档(补 charset/viewport; 正文原样保留)。
       原因: 适配器出参为 embedMode 片段(无文档头), 直接落盘在浏览器里会缺编码/标题信息。"""
    document = HTML_DOC_TEMPLATE
    document = document.replace("{{TITLE}}", _escapeHtmlText(title))
    document = document.replace("{{PLATFORM}}", _escapeHtmlText(platformCode))
    return document.replace("{{CONTENT}}", content if isinstance(content, str) else "")


def _specNoteOfDocument(layoutRecord):
    """文档类产物的规格说明: 取版式 specJson 声明的 size(如 1080x1440); 未声明 -> 空。
       ★ 不自造像素规格(html 文档无固定像素), 前端对空值按「—」显示。"""
    try:
        spec = layoutEngine.resolveSpec(layoutRecord, None)
    except Exception:
        spec = {}
    size = _toStr((spec or {}).get("size")).lower().replace("*", "x")
    if "x" in size and size.replace("x", "").isdigit():
        return size
    return ""


def buildDocumentProduct(data, topicRecord, layoutRecord, platformCode):
    """★ 文档类形态(html/json)产物落文件服务: 返回**单件**产物 dict, 供 saveArtifacts 统一登记。
       入参: data 为适配器出参(含 outputKind/content); topicRecord/layoutRecord 供出参自描述。
       出参: {"seqNo":1, "kind","fileID","sizeBytes","specNote"} / None。
       ★ 降级(绝不阻断渲染): 非文档类形态 / content 为空 / 落盘或上传失败 -> 返回 None 并告警。"""
    data = data if isinstance(data, dict) else {}
    outputKind = _toStr(data.get("outputKind")).lower()
    kindExt = OUTPUT_KIND_ARTIFACT_MAP.get(outputKind)
    if not kindExt:
        if outputKind:
            _logWarn(f"产物未登记: outputKind={outputKind} 无对应产物 kind"
                     f"(允许={sorted(OUTPUT_KIND_ARTIFACT_MAP.keys())}), 且适配器未产出 products, "
                     f"platform:{platformCode}")
        return None

    kind, fileExt = kindExt
    content = data.get("content")
    if not isinstance(content, str) or not content.strip():
        _logWarn(f"产物未登记: outputKind={outputKind} 但 content 为空, platform:{platformCode}")
        return None

    if kind == ARTIFACT_KIND_HTML:
        content = _wrapHtmlDocument(content, _toStr((topicRecord or {}).get("title")), platformCode)

    localDir = ""
    try:
        localDir = tempfile.mkdtemp(prefix = "ch_doc_artifact_")
        localPath = os.path.join(localDir, f"artifact_{misc.getTime()}_{uuid.uuid4().hex[:8]}{fileExt}")
        with open(localPath, "w", encoding = "utf-8") as hFile:
            hFile.write(content)

        #红线 R2: 产物只经引擎层文件门面上传(htmlToImage.uploadArtifact -> common/fileStorageCommon)
        objectName = f"{misc.getTime()}_{uuid.uuid4().hex}{fileExt}"
        fileID = htmlToImage.uploadArtifact(localPath, objectName = objectName, privateFlag = True)
        if not fileID:
            _logWarn(f"文档类产物上传失败(不登记产物) platform:{platformCode}, kind:{kind}, "
                     f"objectName:{objectName}(请检查文件服务配置)")
            return None

        product = {
            "seqNo": 1,
            "kind": kind,
            "fileID": _toStr(fileID),
            "sizeBytes": htmlToImage.fileSizeBytes(localPath),
            "specNote": _specNoteOfDocument(layoutRecord),
        }
        if _LOG:
            _LOG.info(f"PID:{_processorPID}, 文档类产物已上传 platform:{platformCode}, kind:{kind}, "
                      f"fileID:{product['fileID']}, sizeBytes:{product['sizeBytes']}")
        return product
    except Exception as e:
        _logWarn(f"文档类产物落盘/上传异常(不登记产物) platform:{platformCode}, kind:{kind}, errMsg:{e}")
        return None
    finally:
        if localDir:
            htmlToImage.cleanupTempDir(localDir)


def collectArtifactProducts(data, topicRecord, layoutRecord, platformCode):
    """★ 渲染产物清单的**唯一登记口径**(供 renderTopic / executeJob 共用):
       - 适配器返回 products 时(多产物平台: 图集 png)以适配器出参为准, 不叠加文档类产物(形态互斥);
       - 否则补办文档类单件产物(kind=html/json), 修复「任务 DONE 但 ch_artifact 为空」。"""
    products = []
    adapterProducts = (data or {}).get("products")
    if isinstance(adapterProducts, (list, tuple)) and adapterProducts:
        for item in adapterProducts:
            if isinstance(item, dict):
                products.append(dict(item))
        return products

    documentProduct = buildDocumentProduct(data, topicRecord, layoutRecord, platformCode)
    if documentProduct:
        products.append(documentProduct)
    return products

#===== 文档类形态产物落盘与登记 end =====


#===== 主题状态联动(渲染完成 -> RENDERED / 渲染失败 -> 回落 DRAFT) begin =====

def _modifyTopicStatus(topicID, newStatus, loginID = "", jobCode = "", diffNote = ""):
    """经 topicService 改主题状态(状态机 + 版本快照 + 出参收口都在 topicService);
       ★ 业务层**不直写 ch_topic**(红线: 状态变更只走业务同层服务)。
       出参: True=已改写; False=失败(只告警, 不影响渲染结果本身)。"""
    topicID = _toStr(topicID)
    newStatus = _toStr(newStatus).upper()
    if not topicID or not newStatus:
        return False

    try:
        rtn = topicService.modifyTopic({"recID": topicID, "status": newStatus, "diffNote": _toStr(diffNote)},
                                       {"loginID": _toStr(loginID)})
        if _toStr((rtn or {}).get("errCode")) != "B0":
            _logWarn(f"主题状态改写失败({newStatus}; 渲染结果不受影响) topicID:{topicID}, jobCode:{jobCode}, "
                     f"errCode:{(rtn or {}).get('errCode')}, errMsg:{(rtn or {}).get('errMsgList')}")
            return False
        if _LOG:
            _LOG.info(f"PID:{_processorPID}, 主题状态改写 topicID:{topicID}, ->{newStatus}, jobCode:{jobCode}")
        return True
    except Exception as e:
        _logWarn(f"主题状态改写异常({newStatus}; 渲染结果不受影响) topicID:{topicID}, "
                 f"jobCode:{jobCode}, errMsg:{e}")
        return False


def advanceTopicRendered(topicID, currStatus, loginID = "", jobCode = ""):
    """★ 2026-09-24 手改: 渲染成功后把主题状态推进到 RENDERED。
       - RENDERING -> RENDERED(正常路径);
       - DRAFT -> RENDERING -> RENDERED(**两跳**, 状态机不允许 DRAFT 直达 RENDERED;
         覆盖「失败回落 DRAFT / 未先置 RENDERING 直接渲染成功」的场景, 保证渲染成功即 RENDERED);
       - 其它状态(RENDERED/PUBLISHED/ARCHIVED)一律跳过(幂等, 不报错不改动)。
       防御: 推进失败**只告警**, 不影响渲染结果。
       出参: True=已推进; False=跳过或失败(原因见日志)。"""
    topicID = _toStr(topicID)
    currStatus = _toStr(currStatus).upper()
    if not topicID:
        return False

    if currStatus == TOPIC_STATUS_RENDERING:
        return _modifyTopicStatus(topicID, TOPIC_STATUS_RENDERED, loginID, jobCode,
                                  "渲染任务完成, 主题状态自动推进到 RENDERED")

    if currStatus == TOPIC_STATUS_DRAFT:
        #状态机护栏: DRAFT -> RENDERED 非法, 须经 RENDERING 中转
        if not _modifyTopicStatus(topicID, TOPIC_STATUS_RENDERING, loginID, jobCode,
                                  "渲染任务完成, 主题状态自动推进(第一步: RENDERING)"):
            return False
        return _modifyTopicStatus(topicID, TOPIC_STATUS_RENDERED, loginID, jobCode,
                                  "渲染任务完成, 主题状态自动推进到 RENDERED")

    return False


def rollbackTopicRenderFailed(topicRecord, loginID = "", jobCode = "", reason = ""):
    """★ 2026-09-24 手改: 渲染失败后把主题状态 RENDERING -> DRAFT(经 topicService 状态机)。
       目的: 渲染失败不再让主题永久停在 RENDERING(前端「提交渲染」的前置态), 修正后可重新提交;
       防御: 非 RENDERING 状态一律跳过(幂等); 回落失败**只告警**, 不改变已回显的渲染错误。
       出参: True=已回落; False=跳过或失败(原因见日志)。"""
    topicRecord = topicRecord if isinstance(topicRecord, dict) else {}
    topicID = _toStr(topicRecord.get("recID"))
    if not topicID or _toStr(topicRecord.get("status")).upper() != TOPIC_STATUS_RENDERING:
        return False

    diffNote = f"渲染失败回落到 DRAFT({_toStr(reason)[:80] or '渲染未完成'}), 修正后可重新提交"
    return _modifyTopicStatus(topicID, TOPIC_STATUS_DRAFT, loginID, jobCode, diffNote)


def rollbackTopicRenderFailedById(topicID, loginID = "", jobCode = "", reason = ""):
    """按 topicID 回落主题状态(供 worker 兜底路径使用: 手上只有 jobRecord, 无主题记录):
       先经 topicService.queryTopic 取当前记录, 再复用 rollbackTopicRenderFailed; 取数失败只告警。"""
    topicID = _toStr(topicID)
    if not topicID:
        return False
    try:
        rtn = topicService.queryTopic({"recID": topicID, "mode": "full"})
        rows = (rtn.get("data") or {}).get("data") or []
        if _toStr((rtn or {}).get("errCode")) != "B0" or not rows:
            _logWarn(f"主题状态回落跳过(主题记录读取失败) topicID:{topicID}, jobCode:{jobCode}, "
                     f"errCode:{(rtn or {}).get('errCode')}")
            return False
        return rollbackTopicRenderFailed(rows[0], loginID, jobCode, reason)
    except Exception as e:
        _logWarn(f"主题状态回落异常(忽略) topicID:{topicID}, jobCode:{jobCode}, errMsg:{e}")
        return False


def _rollbackOnRenderFail(topicRecord, loginID, jobCode, reason, errRtn = None):
    """渲染失败统一收口: 主题状态回落 RENDERING -> DRAFT;
       errRtn 非空时在该出参 data 上回显 topicStatusRolledBack(便于前端/排查知道主题已回 DRAFT)。
       出参: True=已回落。"""
    rolledBack = rollbackTopicRenderFailed(topicRecord, loginID, jobCode, reason)
    if isinstance(errRtn, dict):
        errRtn.setdefault("data", {})
        errRtn["data"].update({"topicStatusRolledBack": "1" if rolledBack else "0"})
    return rolledBack

#===== 主题状态联动 end =====


#===== 渲染执行(公共): 取数 -> 适配器 -> 写台账 begin =====

def _buildOptions(dataSet):
    """构造适配器 options(与 SP3a/SP3b 口径一致)"""
    return {
        "previewKind": _toStr(dataSet.get("previewKind")),
        "exportKind": _toStr(dataSet.get("exportKind")),
        "embedMode": bool(dataSet.get("embedMode")),
        #SP3b: 截图管线可选参数(缺省由 htmlToImage 取默认: 1080x1440 / 超时 30000ms)
        "deviceScaleFactor": dataSet.get("deviceScaleFactor"),
        "timeoutMs": dataSet.get("timeoutMs"),
        #SP3c: worker 可指定产物落盘目录(冒烟/调试用)
        "productDir": _toStr(dataSet.get("productDir")),
    }


def _resolveOverrideSpec(dataSet):
    for key in OVERRIDE_SPEC_KEYS:
        if dataSet.get(key):
            return dataSet.get(key)
    return None


def _renderViaAdapter(topicRecord, assetList, layoutRecord, platformRecord, platformCode, overrideSpec, options):
    """选适配器并执行形态转换; 出参 (rtnData, errDict)。
       ★ 选适配器一律走工厂(本层不对任何平台硬编码); 无适配器 -> C7。"""
    adapter = platformAdapter.getAdapter(platformCode, platformRecord)
    if adapter is None:
        return None, _err(ERR_FIELD_INVALID, _fieldLabel("platform"),
                          [f"平台适配器未实现: platformCode={platformCode}, "
                           f"已支持={platformAdapter.listAdapterCodes()}"])

    rtn = adapter.render(topicRecord, layoutRecord, assetList, overrideSpec, options)
    if not isinstance(rtn, dict):
        rtn = {}
    if rtn.get("errCode") != "B0":
        return None, _err(rtn.get("errCode", ERR_RENDER_FAILED),
                          rtn.get("field") or _fieldLabel("platform"), rtn.get("errMsgList"))

    return (rtn.get("data") or {}), None


def _buildRenderResult(topicRecord, topicID, layoutCode, platformCode, assetList, data, jobID = 0,
                       jobCode = "", renderMode = RENDER_MODE_SYNC, reused = "0", extra = None):
    """把适配器产物归一为业务出参(products/fileIDs 经 chCommon.fillFileUrls 转 URL)"""
    meta = data.get("meta") or {}
    rtnData = {
        "topicID": topicID,
        "topicCode": _toStr(topicRecord.get("topicCode")),
        "layoutCode": layoutCode,
        "platform": platformCode,
        "outputKind": data.get("outputKind"),
        "content": data.get("content"),
        "meta": meta,
        "assetCount": len(assetList or []),
        "renderMode": renderMode,
        "reused": reused,
        "jobID": _toInt(jobID, 0),
        "jobCode": _toStr(jobCode),
    }
    if meta.get("previewKind"):
        rtnData["previewKind"] = meta.get("previewKind")

    products = data.get("products")
    if isinstance(products, (list, tuple)) and products:
        products = list(products)
        try:
            comCh.fillFileUrls(products, fileFields = ["fileID"])
        except Exception as e:
            _logWarn(f"产物 fileID 转 URL 失败, errMsg:{str(e)}")
        rtnData["products"] = products
        rtnData["fileIDs"] = [_toStr(item.get("fileID")) for item in products
                              if isinstance(item, dict) and _toStr(item.get("fileID"))]
        rtnData["productCount"] = len(products)

    if isinstance(extra, dict):
        rtnData.update(extra)
    return rtnData


def _buildReuseResult(topicRecord, topicID, layoutCode, platformCode, reuseInfo,
                      renderMode = RENDER_MODE_SYNC):
    """命中 inputHash 复用时的出参(不重新渲染)"""
    artifacts = reuseInfo.get("artifacts") or []
    productList = []
    for item in artifacts:
        productList.append({
            "seqNo": _toInt(item.get("seqNo"), 1),
            "kind": _toStr(item.get("kind")),
            "fileID": _toStr(item.get("fileID")),
            "thumbnailID": _toStr(item.get("thumbnailID")),
            "artifactKey": _toStr(item.get("artifactKey")),
            "artifactVer": _toInt(item.get("artifactVer"), 1),
            "artifactStatus": _toStr(item.get("artifactStatus")),
            "specNote": _toStr(item.get("specNote")),
            "sizeBytes": _toInt(item.get("sizeBytes"), 0),
        })
    try:
        comCh.fillFileUrls(productList, fileFields = ["fileID", "thumbnailID"])
    except Exception as e:
        _logWarn(f"复用产物 fileID 转 URL 失败, errMsg:{str(e)}")

    rtnData = {
        "topicID": topicID,
        "topicCode": _toStr(topicRecord.get("topicCode")),
        "layoutCode": layoutCode,
        "platform": platformCode,
        "renderMode": renderMode,
        "reused": "1",
        "reuseReason": "inputHash 命中既有 DONE 任务, 复用既有产物(不重复渲染)",
        "inputHash": _toStr(reuseInfo.get("inputHash")),
        "jobID": _toInt(reuseInfo.get("jobID"), 0),
        "jobCode": _toStr(reuseInfo.get("jobCode")),
        "artifacts": productList,
        "fileIDs": [_toStr(item.get("fileID")) for item in productList if _toStr(item.get("fileID"))],
        "productCount": len(productList),
    }
    return rtnData

#===== 渲染执行 end =====


#===== 业务入口: 主题渲染(topicrender) begin =====

def renderTopic(dataSet, sessionIDSet = None):
    """主题渲染(同步或异步任务提交): 取主题 + 附图 + 版式 + 平台 -> 经 platformAdapter 得**平台形态产物**。
       入参(dataSet):
         topicID / recID / topicCode  必填(missing -> C4)
         layoutCode                   必填(missing -> C4)
         platform                     可选平台编码; 缺省取 ch_layout.platform
         renderMode                   可选 sync(默认) / job(提交 PENDING, 由 worker 执行)
         specOverride / overrideSpec  可选渲染覆盖参数(dict 或 JSON 字符串; **job 模式不支持覆盖**)
         previewKind                  可选站内预览形态(由适配器用手机框包裹)
         exportKind                   可选通用导出形态(仅 generic 适配器消费)
       行为(★ SP3c):
         - inputHash 命中既有 DONE 任务 -> 直接复用既有产物(reused="1", 不重复渲染);
         - sync: 建 job(PENDING->RUNNING->DONE), 渲染后写 ch_artifact 台账;
         - job : 建 job(PENDING) 后立即返回 jobCode, 渲染由 schedule/renderWorker.py 异步完成。"""
    if not isinstance(dataSet, dict):
        dataSet = {}

    #0) 渲染任务模式
    renderMode = _toStr(dataSet.get("renderMode")).lower() or RENDER_MODE_SYNC
    if renderMode not in SUPPORTED_RENDER_MODE_LIST:
        return _err(ERR_NOT_IMPLEMENTED, _fieldLabel("renderMode"),
                    [f"renderMode={renderMode} 未支持, 允许值={SUPPORTED_RENDER_MODE_LIST}"])

    layoutCode = _toStr(dataSet.get("layoutCode"))
    if not layoutCode:
        return _err(ERR_FIELD_MISSING, _fieldLabel("layoutCode"), ["layoutCode 为必填字段"])

    #1) 取主题 + 附图
    topicRecord, errRtn = _fetchTopic(dataSet)
    if errRtn is not None:
        return errRtn

    topicID = _toStr(topicRecord.get("recID"))
    #登录ID: 主题状态回落/渲染产物归属都用它(缺省取请求 ownerID, 再回落会话)
    loginID = _toStr(dataSet.get("ownerID")) or _toStr((sessionIDSet or {}).get("loginID"))
    assetList, assetErr = _fetchAssets(topicID)
    if assetErr is not None:
        #附图查询失败不阻断渲染(可渲染「无图」版式), 但记日志
        _logWarn(f"附图查询失败 topicID:{topicID}, errMsg:{assetErr.get('errMsgList')}")
        assetList = []
    else:
        assetList = _mergeAssetMeta(assetList)

    #2) 版式定义(供 platform 缺省取值与适配器渲染)
    try:
        layoutRecord = layoutEngine.loadLayoutRecord(layoutCode)
    except layoutEngine.LayoutEngineError as e:
        _logWarn(f"版式读取失败 layoutCode:{layoutCode}, errCode:{e.errCode}, errMsg:{e.message}")
        rtn = _err(e.errCode, e.field or _fieldLabel("layoutCode"), [e.message])
        #渲染未完成: 主题从 RENDERING 回落 DRAFT(否则主题会永久卡在 RENDERING)
        _rollbackOnRenderFail(topicRecord, loginID, "", f"版式读取失败:{e.errCode}", rtn)
        return rtn

    #3) 平台解析: 请求 platform > ch_layout.platform
    platformCode = _toStr(dataSet.get("platform")) or _toStr(layoutRecord.get("platform"))
    if not platformCode:
        rtn = _err(ERR_FIELD_INVALID, _fieldLabel("platform"),
                   ["版式未声明 platform 且请求未指定 platform"])
        _rollbackOnRenderFail(topicRecord, loginID, "", "平台未声明", rtn)
        return rtn

    platformRecord, platformErr = _fetchPlatformRecord(platformCode)
    if platformErr is not None:
        _rollbackOnRenderFail(topicRecord, loginID, "", "平台配置不可用/无适配器", platformErr)
        return platformErr

    overrideSpec = _resolveOverrideSpec(dataSet)

    #4) ★ inputHash 复用判定(不重复渲染)
    inputHash = buildInputHash(topicRecord, layoutRecord, assetList, platformCode, overrideSpec)
    reuseInfo = findReusableJob(inputHash, topicID, platformCode)
    if reuseInfo is not None:
        _logWarn(f"topicrender 命中 inputHash 复用 topicID:{topicID}, jobID:{reuseInfo.get('jobID')}, "
                 f"artifacts:{len(reuseInfo.get('artifacts') or [])}, 不重复渲染")
        reuseData = _buildReuseResult(topicRecord, topicID, layoutCode, platformCode, reuseInfo, renderMode)
        #复用同样属「本次渲染已产出」: 主题状态须一并收口(否则命中复用会把主题悬在 RENDERING)
        reuseData["statusAdvanced"] = "1" if advanceTopicRendered(
            topicID, topicRecord.get("status"), loginID, _toStr(reuseInfo.get("jobCode"))) else "0"
        return _ok(reuseData)

    ownerID = loginID
    jobCode = buildJobCode(platformCode, topicRecord.get("topicCode"))
    memo = f"renderMode={renderMode}; override={'1' if overrideSpec else '0'}"
    jobID = _insertJob(jobCode, topicID, layoutCode, platformCode, inputHash, ownerID = ownerID, memo = memo)
    if jobID <= 0:
        #台账建档失败: 同步渲染仍继续(降级不写台账), 但异步模式无法建任务 -> 显式报错不静默
        _logWarn(f"渲染任务建档失败(降级) topicID:{topicID}, platform:{platformCode}, jobCode:{jobCode}")
        if renderMode == RENDER_MODE_JOB:
            rtn = _err(ERR_DB_FAILED, _fieldLabel("jobCode"),
                       ["渲染任务建档失败(异步模式无法入队), 请检查数据库连接"])
            _rollbackOnRenderFail(topicRecord, loginID, jobCode, "渲染任务建档失败", rtn)
            return rtn

    #5) 异步任务模式: 建 job(PENDING) 后立即返回; 投递 CH_RENDER 队列通知 worker 近实时消费
    if renderMode == RENDER_MODE_JOB:
        _notifyRenderWorker(jobCode, jobID, topicID, layoutCode, platformCode, ownerID)
        return _ok({
            "topicID": topicID,
            "topicCode": _toStr(topicRecord.get("topicCode")),
            "layoutCode": layoutCode,
            "platform": platformCode,
            "renderMode": RENDER_MODE_JOB,
            "reused": "0",
            "jobID": jobID,
            "jobCode": jobCode,
            "jobStatus": JOB_STATUS_INITIAL,
            "inputHash": inputHash,
            "message": "任务已投递渲染队列(PENDING), 由 schedule/renderWorker.py 异步消费",
        })

    #6) 同步渲染: PENDING -> RUNNING -> DONE(全链路都写同一台账)
    startTime = time.time()
    if jobID > 0:
        updateJobStatus(jobID, "RUNNING", progress = JOB_PROGRESS_RUNNING, startYMDHMS = misc.getTime())

    options = _buildOptions(dataSet)
    data, renderErr = _renderViaAdapter(topicRecord, assetList, layoutRecord, platformRecord,
                                        platformCode, overrideSpec, options)
    if renderErr is not None:
        _logWarn(f"topicrender 平台形态转换失败 topicID:{topicID}, layoutCode:{layoutCode}, "
                 f"platform:{platformCode}, errCode:{renderErr.get('errCode')}, errMsg:{renderErr.get('errMsgList')}")
        if jobID > 0:
            updateJobStatus(jobID, "FAILED", progress = 0,
                            errMsg = ";".join(renderErr.get("errMsgList") or []) or _toStr(renderErr.get("errCode")),
                            costMs = int((time.time() - startTime) * 1000), finishYMDHMS = misc.getTime())
        renderErr.setdefault("data", {})
        renderErr["data"].update({"jobID": jobID, "jobCode": jobCode})
        #渲染失败: 主题从 RENDERING 回落 DRAFT(修正后可重新提交)
        _rollbackOnRenderFail(topicRecord, loginID, jobCode,
                              ";".join(renderErr.get("errMsgList") or []) or _toStr(renderErr.get("errCode")),
                              renderErr)
        return renderErr

    #7) 产物台账(主计划 P2-6): artifactKey = {jobID}:{kind}:{platform}:{seqNo}
    #   ★ 2026-09-24: 文档类形态(html/json)适配器不产 products, 由 collectArtifactProducts 补办单件产物;
    #   jobID<=0(台账建档失败降级)时不再落盘, 避免产生无人认领的孤儿产物
    products = collectArtifactProducts(data, topicRecord, layoutRecord, platformCode) if jobID > 0 else []
    savedArtifacts = []
    if products:
        savedArtifacts = saveArtifacts(jobID, _toInt(topicID, 0), platformCode, products)

    costMs = int((time.time() - startTime) * 1000)
    if jobID > 0:
        updateJobStatus(jobID, "DONE", progress = JOB_PROGRESS_DONE, costMs = costMs,
                        finishYMDHMS = misc.getTime())

    #8) ★ 主题状态自动推进(RENDERING -> RENDERED; 非 RENDERING 跳过, 失败只告警)
    statusAdvanced = "1" if advanceTopicRendered(topicID, topicRecord.get("status"),
                                                 ownerID, jobCode) else "0"

    rtnData = _buildRenderResult(topicRecord, topicID, layoutCode, platformCode, assetList, data,
                                 jobID = jobID, jobCode = jobCode, renderMode = RENDER_MODE_SYNC,
                                 reused = "0",
                                 extra = {"inputHash": inputHash, "costMs": costMs,
                                          "artifactCount": len(savedArtifacts),
                                          "statusAdvanced": statusAdvanced})
    return _ok(rtnData)

#===== 业务入口结束 =====


#===== 业务入口: 异步任务执行(供 schedule/renderWorker.py 调用) begin =====

def executeJob(jobRecord, dataSet = None, sessionIDSet = None):
    """执行一条已入队的渲染任务(由 worker 调用):
       RUNNING -> 渲染 -> 写 ch_artifact -> DONE; 异常或渲染失败 -> FAILED(并记录原因)。
       入参 jobRecord 为 ch_render_job 记录(dict); dataSet 可覆盖 options(productDir/timeoutMs 等)。
       出参: {"errCode","field","errMsgList","data"}; 失败时 data 含 jobID/jobCode/jobStatus。"""
    jobRecord = jobRecord if isinstance(jobRecord, dict) else {}
    dataSet = dataSet if isinstance(dataSet, dict) else {}

    jobID = _toInt(jobRecord.get("recID"), 0)
    jobCode = _toStr(jobRecord.get("jobCode"))
    topicID = _toStr(jobRecord.get("topicID"))
    layoutCode = _toStr(jobRecord.get("layoutCode"))
    platformCode = _toStr(jobRecord.get("platform"))
    #登录ID: 主题状态联动(成功推进/失败回落)与产物归属口径一致
    loginID = _toStr(jobRecord.get("ownerID"))

    if jobID <= 0 or not topicID or not layoutCode or not platformCode:
        return _err(ERR_FIELD_MISSING, _fieldLabel("jobRecord"),
                    [f"任务记录字段不完整: jobID={jobID}, topicID={topicID}, "
                     f"layoutCode={layoutCode}, platform={platformCode}"])

    #1) 状态机: 只允许 PENDING(或 FAILED 重试) -> RUNNING
    currStatus = _toStr(jobRecord.get("jobStatus"))
    errCode, rtnField, message = checkJobStatusTransition(currStatus, "RUNNING")
    if errCode:
        return _err(errCode, rtnField, [message],
                    {"jobID": jobID, "jobCode": jobCode, "currentStatus": currStatus,
                     "allowedTransitions": JOB_STATUS_TRANSITIONS.get(currStatus, [])})

    startTime = time.time()
    runningRtn = updateJobStatus(jobID, "RUNNING", progress = JOB_PROGRESS_RUNNING, startYMDHMS = misc.getTime())
    if runningRtn.get("errCode") != "B0":
        return runningRtn

    #主题记录(供失败收口时回落主题状态; 取数成功后被覆盖, 取数失败时保持空 -> 无法回落)
    topicRecord = {}
    try:
        #2) 取数(主题 + 附图 + 版式 + 平台)
        topicRecord, errRtn = _fetchTopic({"recID": topicID})
        if errRtn is not None:
            return _failJob(jobID, jobCode, startTime, errRtn)

        assetList, assetErr = _fetchAssets(topicID)
        if assetErr is not None:
            _logWarn(f"任务附图查询失败(降级为空) jobID:{jobID}, errMsg:{assetErr.get('errMsgList')}")
            assetList = []
        else:
            assetList = _mergeAssetMeta(assetList)

        layoutRecord = layoutEngine.loadLayoutRecord(layoutCode)
        platformRecord, platformErr = _fetchPlatformRecord(platformCode)
        if platformErr is not None:
            return _failJob(jobID, jobCode, startTime, platformErr, topicRecord, loginID)

        #3) 渲染(job 模式不支持 specOverride: job 表未持久化覆盖参数, 一律按 specJson 渲染)
        options = _buildOptions(dataSet)
        data, renderErr = _renderViaAdapter(topicRecord, assetList, layoutRecord, platformRecord,
                                            platformCode, None, options)
        if renderErr is not None:
            return _failJob(jobID, jobCode, startTime, renderErr, topicRecord, loginID)

        #4) 产物台账 + 任务收口
        #   ★ 2026-09-24: 文档类形态(html/json)适配器不产 products, 由 collectArtifactProducts 补办单件产物
        products = collectArtifactProducts(data, topicRecord, layoutRecord, platformCode)
        savedArtifacts = []
        if products:
            savedArtifacts = saveArtifacts(jobID, _toInt(topicID, 0), platformCode, products)

        costMs = int((time.time() - startTime) * 1000)
        updateJobStatus(jobID, "DONE", progress = JOB_PROGRESS_DONE, costMs = costMs,
                        finishYMDHMS = misc.getTime())

        #防: 状态推进失败只告警, 不把已成功的任务判为 FAILED
        statusAdvanced = "1" if advanceTopicRendered(topicID, topicRecord.get("status"),
                                                    loginID, jobCode) else "0"

        rtnData = _buildRenderResult(topicRecord, topicID, layoutCode, platformCode, assetList, data,
                                     jobID = jobID, jobCode = jobCode, renderMode = RENDER_MODE_JOB,
                                     reused = "0",
                                     extra = {"jobStatus": "DONE", "costMs": costMs,
                                              "artifactCount": len(savedArtifacts),
                                              "statusAdvanced": statusAdvanced})
        return _ok(rtnData)

    except layoutEngine.LayoutEngineError as e:
        _logWarn(f"任务渲染失败(版式) jobID:{jobID}, errCode:{e.errCode}, errMsg:{e.message}")
        return _failJob(jobID, jobCode, startTime,
                        _err(e.errCode, e.field or _fieldLabel("layoutCode"), [e.message]),
                        topicRecord, loginID)
    except Exception as e:
        _logError(f"任务执行异常 jobID:{jobID}, errMsg:{e}, {traceback.format_exc()}")
        return _failJob(jobID, jobCode, startTime,
                        _err(ERR_RENDER_FAILED, _fieldLabel("jobRecord"), [f"任务执行异常: {str(e)}"]),
                        topicRecord, loginID)


def _failJob(jobID, jobCode, startTime, errRtn, topicRecord = None, loginID = ""):
    """任务失败收口: FAILED + 原因(不抛异常) + 主题状态回落 RENDERING -> DRAFT。
       ★ topicRecord 为本次任务取到的主题记录(取主题失败时为 None -> 无法回落, 跳过);
         回落失败只告警, 绝不把 FAILED 的收口本身变成异常。"""
    errMsg = ";".join(errRtn.get("errMsgList") or []) or _toStr(errRtn.get("errCode"))
    updateJobStatus(jobID, "FAILED", progress = 0, errMsg = errMsg[:500],
                    costMs = int((time.time() - startTime) * 1000), finishYMDHMS = misc.getTime())
    errRtn.setdefault("data", {})
    errRtn["data"].update({"jobID": _toInt(jobID, 0), "jobCode": _toStr(jobCode), "jobStatus": "FAILED"})
    if isinstance(topicRecord, dict) and topicRecord:
        _rollbackOnRenderFail(topicRecord, loginID, jobCode, errMsg, errRtn)
    return errRtn


def queryJob(jobID):
    """按 jobID 取任务状态(worker/诊断用); 无记录 -> CB。"""
    record, queryErr = _queryJobRecord(jobID)
    if queryErr:
        return _err(ERR_NO_RECORD, _fieldLabel("jobID"), [queryErr])
    return _ok({"jobID": _toInt(jobID, 0), "jobStatus": _toStr(record.get("jobStatus")),
                "progress": _toInt(record.get("progress"), 0), "errMsg": _toStr(record.get("errMsg")),
                "jobCode": _toStr(record.get("jobCode")), "inputHash": _toStr(record.get("inputHash")),
                "costMs": _toInt(record.get("costMs"), 0)})

#===== 异步任务执行 end =====


if __name__ == "__main__":
    pass
    #本地自测(不连库): 只验证参数校验与状态机
    print("missing all:", renderTopic({}, {})["errCode"])
    print("missing layoutCode:", renderTopic({"topicID": "1"}, {})["errCode"])
    print("bad renderMode:", renderTopic({"topicID": "1", "layoutCode": "stack_v1", "renderMode": "xxx"}, {})["errCode"])
    print("job transition DONE->RUNNING:", checkJobStatusTransition("DONE", "RUNNING"))
    print("artifactKey:", buildArtifactKey(123, "png", "wechat_mp", 2))
    #2026-09-24 手改: 文档类产物(含内联样式花括号的正文必须原样保留 -> 不用 str.format)
    print("document artifact kinds:", sorted(OUTPUT_KIND_ARTIFACT_MAP.keys()))
    print("wrap html document:", _wrapHtmlDocument("<p style=\"a{b:1}\">{x}</p>", "标题", "wechat_mp")[:120])
    print("markdown mapped:", OUTPUT_KIND_ARTIFACT_MAP.get("markdown"))
    print("unknown kind not mapped:", OUTPUT_KIND_ARTIFACT_MAP.get("docx"))
    print("specNote(carousel):", _specNoteOfDocument({"specJson": "{\"size\":\"1080x1440\"}"}))
