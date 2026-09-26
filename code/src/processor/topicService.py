#! /usr/bin/env python3
#encoding: utf-8

#Filename: topicService.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub C2 主题管理业务服务(SP2a 落点, 见主计划 2.2 C2 / 5.3 P1-3·P1-4)。
#
#职责(纯业务, 不涉 HTTP 报文封装):
#  1) 主题全字段 CRUD(ch_topic)           —— 只经 common/mysqlCommon.py(红线 R1, 禁裸 SQL);
#  2) 字段区间校验: 标题 ≤50 / 简介 ≤200 / 详述 ≤5000 字(中文按字符、英文按词);
#     ★ 2026-09-20 裁定 #1: 详述的强校验由「新增必填」迁移到「提交渲染」路径
#       (新增允许空草稿; 详述 >5000 仍走转存文件), 见 _checkRenderReadiness;
#     ★ 2026-09-22 用户裁定: **取消详述 2000 字下限**(可留空、可短写, 0 字合法);
#       提交渲染仅要求「有正文或 descriptionFileID」(C4), 不再有字数不足(C6);
#  3) 状态机: DRAFT / RENDERING / RENDERED / PUBLISHED / ARCHIVED, 非法跃迁拒绝并回显当前状态;
#  4) wordCount 自动统计(口径见 countWords 注释);
#  5) topicCode 幂等写入(经 common/chCommon.py::upsertByUniqueKey);
#  6) 详述超长转存文件并写 descriptionFileID(只经 common/fileStorageCommon.py, 红线 R2);
#  7) 版本快照(ch_topic_version): 保存主题时落快照, 支持按主题列版本 / 按版本取快照;
#  8) 出参统一经 common/chCommon.py::fillFileUrls 把 fileID 转 URL。
#
#返回契约(供 main/subfunc/topicApi.py 直接映射为 HTTP 报文):
#  {"errCode": <"B0"=通过 / C·D 段错误码>, "field": <出错字段描述>, "errMsgList": [<原因>], "data": {...}}
#
#错误码落点(均为 common/errMsgCommon.py 的 contenthub 消息键, C 段=通用与字段校验 / D 段=文件与素材):
#  C4 必填缺失 | C5 字段超长 | C6 数值/区间越界 | C7 取值非法(含非法状态跃迁)
#  CA 重复记录 | CB 无此记录 | D1 文件超出限制 | D3 文件上传失败 | CG 版本快照落库失败
#
#设计约束:
#  - 本模块不 import main/subfunc/*(避免 processor <-> 接入层的循环依赖; 分层单向);
#  - 文件门面按 chCommon 既有约定「函数内延迟导入」—— fileStorageCommon 会牵出云厂商 SDK,
#    仅在真正需要转存时导入, 保证只做数据库操作的调用方不被动依赖这些 SDK。

_VERSION="20260919"


import os
import re
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../code/src
if parentdir not in sys.path:
    sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import tempfile
import traceback

#global defintion/common var etc.
from common import globalDefinition as comGD

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#数据层唯一入口(红线 R1)
from common import mysqlCommon as comMysql

#跨域业务公共件(幂等写入 + fileID -> URL)
from common import chCommon as comCh

#setting files
from config import basicSettings as settings


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    #与接入层共用同一 logger(同名 logger 唯一, miscCommon.setLogNew 内部有 handlers 判重)
    try:
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None

_DEBUG = settings._DEBUG


#===== 表与字段常量 begin =====

TOPIC_TABLE = "ch_topic"
TOPIC_VERSION_TABLE = "ch_topic_version"

#ch_topic 字段顺序(唯一数据源: database/ch_topic.txt), 仅用于「字段名 + 位置」的错误提示
TOPIC_FIELD_ORDER = [
    "recID", "topicCode", "title", "summary", "description", "descriptionFileID",
    "coverFileID", "coverThumbID", "author", "location", "source", "period",
    "tagList", "categoryCode", "layoutCode", "complianceStatus", "complianceCheckedAt",
    "status", "publishStatus", "assetCount", "wordCount",
    "aiFlag", "ownerID", "label", "memo", "regID", "regYMDHMS", "modifyID",
    "modifyYMDHMS", "delFlag",
]

#字段区间(主计划 5.3 P1-3)
TOPIC_CODE_MAX_LEN = 64
#topicCode 缺省时由服务端生成(裁定 #1 / 2026-09-20: 前端「新建主题」只传 title, 编码由服务端幂等生成)
TOPIC_CODE_AUTO_PREFIX = "TOPIC"
#已选版式编码区间(裁定 #2 / 2026-09-20: ch_topic 增加 layoutCode 列, 关联 ch_layout.layoutCode)
LAYOUT_CODE_MAX_LEN = 64
#合规通过态落库(裁定 / 2026-09-22: ch_topic 增加 complianceStatus + complianceCheckedAt 两列):
#  供 P-09「标记通过」与 P-10 投递门禁**跨设备/跨浏览器**读取; 由前端经 topicmodify 写入,
#  时间取 publishcheck 出参的 data.checkedAt(本层不自行生成时间, 避免与校验时刻脱钩)。
#  说明: 本列是「人工确认过的校验结论」留痕, **不作为投递的强制闸门**(投递时服务端仍会重跑 publishcheck)。
COMPLIANCE_STATUS_LIST = ["UNCHECKED", "PASSED", "BLOCKED"]
COMPLIANCE_STATUS_INITIAL = "UNCHECKED"
COMPLIANCE_CHECKED_AT_LEN = 16
TITLE_MAX_LEN = 50
SUMMARY_MAX_LEN = 200
#★ 2026-09-22 用户裁定: 详述取消字数下限 —— 可留空、可短写, 0 字合法。
#  本常量保留(置 0)仅为兼容 test_ch_phase0_static.py 的常量清单校验;
#  校验逻辑已不再据此拦截(见 validateTopicFields / _checkRenderReadiness)。
DESCRIPTION_MIN_WORDS = 0
DESCRIPTION_MAX_WORDS = 5000
#详述正文的绝对上限(超过视为异常上报, 防止无界落盘)
DESCRIPTION_MAX_TRANSFER_WORDS = 200000
#转存时库内保留的正文预览长度(字符)。为什么不置空: 生成器产出的 update_ch_topic 对空串会跳过,
#「置空」在更新路径上无法生效(旧正文会残留); 保留有界前缀可同时满足「有界存储 + 可更新」。
DESCRIPTION_INLINE_PREVIEW_CHARS = 5000

#详情转存文件的对象名前缀
DESCRIPTION_FILE_OBJECT_PREFIX = "topic/description"

#主题状态机(主计划 3.4.3 ch_topic.status 枚举): 单向推进为主, 允许渲染失败/退回编辑, 归档为终态。
TOPIC_STATUS_INITIAL = "DRAFT"
TOPIC_STATUS_LIST = ["DRAFT", "RENDERING", "RENDERED", "PUBLISHED", "ARCHIVED"]
TOPIC_STATUS_TRANSITIONS = {
    "DRAFT":     ["RENDERING", "ARCHIVED"],
    "RENDERING": ["RENDERED", "DRAFT", "ARCHIVED"],
    "RENDERED":  ["PUBLISHED", "RENDERING", "DRAFT", "ARCHIVED"],
    "PUBLISHED": ["ARCHIVED"],
    "ARCHIVED":  [],
}

#发布状态(publishStatus 由 C6 投递推进, 本层只做取值合法性校验)
PUBLISH_STATUS_LIST = ["UNPUBLISHED", "DRAFTED", "PUBLISHED", "FAILED"]
PUBLISH_STATUS_INITIAL = "UNPUBLISHED"

#AI 标识
AI_FLAG_LIST = ["0", "1"]

#删除标记(红线: delFlag 一律 "0"/"1", 不是 comGD._CONST_NO/_CONST_YES)
DEL_FLAG_NORMAL = "0"
DEL_FLAG_DELETED = "1"

#错误码落点(common/errMsgCommon.py::_CH_ERROR_WORD 的 contenthub C/D 段)
ERR_FIELD_MISSING = "C4"
ERR_FIELD_TOO_LONG = "C5"
ERR_FIELD_OUT_OF_RANGE = "C6"
ERR_FIELD_INVALID = "C7"
ERR_DUPLICATE = "CA"
ERR_NO_RECORD = "CB"
ERR_FILE_LIMIT = "D1"
ERR_FILE_UPLOAD = "D3"
#版本快照落库失败。复用 contenthub 继承自 default 的 CG 码("记录添加失败"/"insert record error"):
#快照失败是「写入失败」而非「文件上传失败」, 不可错用 D3, 否则 topicversionadd 会向客户端回显「文件上传失败」而误导排查方向。
ERR_SNAPSHOT_FAILED = "CG"

#===== 表与字段常量 end =====


#===== 通用小工具 begin =====

def _toStr(value):
    """None/数字/任意 -> 去空白字符串"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _fieldLabel(fieldName):
    """字段名 + 位置(在 ch_topic 中的序号, 从 1 开始), 用于错误提示「标明字段名与位置」"""
    try:
        pos = TOPIC_FIELD_ORDER.index(fieldName) + 1
    except ValueError:
        pos = 0
    return f"{fieldName}(字段#{pos})"


def _ok(data = None, errMsgList = None):
    """业务成功返回"""
    return {"errCode": "B0", "field": "", "errMsgList": errMsgList or [], "data": data or {}}


def _err(errCode, rtnField, errMsgList = None, data = None):
    """业务失败返回(可携带回显数据, 如当前状态)"""
    return {"errCode": errCode, "field": rtnField, "errMsgList": errMsgList or [], "data": data or {}}


def _tableName():
    """表名一律经 mysqlCommon 的转名函数取得(不硬编码表名字面量之外的拼接)"""
    return comMysql.tablename_convertor_ch_topic()


def _versionTableName():
    return comMysql.tablename_convertor_ch_topic_version()

#===== 通用小工具 end =====


#===== wordCount 统计 begin =====
#口径(契约, 写死):
#  - 中文(CJK 统一表意文字, 含扩展 A 区)按「字符」计: 每个汉字算 1;
#  - 英文/数字按「词」计: 连续的 [A-Za-z0-9] 串算 1 个词(保留 don't / e-mail 这类内部连字符/撇号);
#  - 标点、空白、换行、表情等一律不计入。
_WORD_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_WORD_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+(?:['\-][A-Za-z0-9]+)*")


def countWords(text):
    """返回 text 的 wordCount(中文按字符 + 英文按词), 详见上方口径注释"""
    if not text:
        return 0
    if not isinstance(text, str):
        text = str(text)
    cjkNum = len(_WORD_CJK_PATTERN.findall(text))
    tokenNum = len(_WORD_TOKEN_PATTERN.findall(text))
    return cjkNum + tokenNum

#===== wordCount 统计 end =====


#===== 状态机 begin =====

def checkStatusTransition(currStatus, newStatus):
    """主题状态机校验。返回 (errCode, rtnField, errMsg); 合法返回 ("", "", "")。
       规则:
         - newStatus 不在枚举内          -> C7
         - newStatus == currStatus       -> 合法(幂等保存)
         - currStatus 为空(首存)         -> 合法(初始状态赋值)
         - 跃迁不在 TOPIC_STATUS_TRANSITIONS[currStatus] -> C7 并回显当前状态"""
    currStatus = _toStr(currStatus).upper()
    newStatus = _toStr(newStatus).upper()

    if not newStatus:
        return "", "", ""

    if newStatus not in TOPIC_STATUS_LIST:
        return (ERR_FIELD_INVALID, _fieldLabel("status"),
                f"status(主题状态) 取值非法: {newStatus}, 允许值={TOPIC_STATUS_LIST}")

    if not currStatus:
        return "", "", ""

    if newStatus == currStatus:
        return "", "", ""

    allowList = TOPIC_STATUS_TRANSITIONS.get(currStatus, [])
    if newStatus not in allowList:
        return (ERR_FIELD_INVALID, _fieldLabel("status"),
                f"status(主题状态) 非法跃迁: {currStatus} -> {newStatus}, "
                f"当前状态={currStatus}, 允许跃迁={allowList or '无(终态)'}")

    return "", "", ""

#===== 状态机 end =====


#===== 字段校验与归一 begin =====

def _genTopicCode():
    """服务端生成 topicCode(裁定 #1 / 2026-09-20)。
       格式: TOPIC-{yyyyMMddHHmmss}-{4位十六进制随机}; 唯一性由 ch_topic.topicCode 的 UNIQUE 约束兜底。"""
    return f"{TOPIC_CODE_AUTO_PREFIX}-{misc.getTime()}-{os.urandom(2).hex().upper()}"


def _checkRenderReadiness(dataSet, currDataSet = None):
    """提交渲染前置强校验(裁定 #1 / 2026-09-20: 原 add 分支的详述强校验迁移到此处)。

    规则(任一不满足即拦截, 返回 (errCode, rtnField, errMsgList)):
      - 详述正文缺失(本次未传且库内也没有)且无 descriptionFileID -> C4;
      - ★ 2026-09-22 用户裁定: **取消详述 2000 字下限**, 故不再有「字数不足 -> C6」;
        · 超过 DESCRIPTION_MAX_WORDS 属「转存文件」的合法场景(保存阶段已处理), 此处不拦;
    字数口径: 本次传了正文则按本次正文重算; 否则取库内 wordCount(转存场景下库内存的是全文口径)。
    """
    currDataSet = currDataSet or {}
    description = _toStr(dataSet.get("description"))
    descriptionFileID = _toStr(dataSet.get("descriptionFileID")) or _toStr(currDataSet.get("descriptionFileID"))

    if description:
        wordCount = countWords(description)
    else:
        wordCount = comMysql.toIntSafe(currDataSet.get("wordCount"), 0)
        if not wordCount and _toStr(currDataSet.get("description")):
            wordCount = countWords(_toStr(currDataSet.get("description")))

    if not description and not descriptionFileID and not wordCount:
        return (ERR_FIELD_MISSING, _fieldLabel("description"),
                ["提交渲染前必须有详述正文(上限 5000 字, 无下限)或 descriptionFileID"])

    #★ 2026-09-22 用户裁定: 取消详述 2000 字下限 —— 不再返回「字数不足」的 C6。
    return "", "", ""


def validateTopicFields(dataSet, mode = "add", currDataSet = None):
    """主题字段区间校验 + 归一化(纯函数: 不触库、不做文件 IO, 便于静态/单测)。
       入参:
         dataSet       请求数据
         mode          "add" 必填项按新增规则; "modify" 未提供的字段跳过校验(局部更新)
         currDataSet   修改场景的当前记录(用于状态机跃迁校验)
       出参: (errCode, rtnField, rtnErrMsgList, saveSet, meta)
         errCode == "B0" 表示通过; saveSet 仅含需要落库的字段;
         meta = {"hasDescription":bool, "needTransfer":bool, "fullDescription":str, "wordCount":int}
    """
    errList = []          #[(errCode, rtnField, errMsg)]
    saveSet = {}
    meta = {"hasDescription": False, "needTransfer": False, "fullDescription": "", "wordCount": 0}

    currDataSet = currDataSet or {}
    isAdd = (mode == "add")

    def addErr(errCode, fieldName, errMsg):
        errList.append((errCode, _fieldLabel(fieldName), errMsg))

    if not isinstance(dataSet, dict):
        return ERR_FIELD_MISSING, _fieldLabel("dataSet"), ["请求数据为空或格式非法"], saveSet, meta

    #1) topicCode(幂等唯一键)
    topicCode = _toStr(dataSet.get("topicCode"))
    if topicCode:
        if len(topicCode) > TOPIC_CODE_MAX_LEN:
            addErr(ERR_FIELD_TOO_LONG, "topicCode",
                   f"topicCode(主题编码) 长度={len(topicCode)} 超上限 {TOPIC_CODE_MAX_LEN}")
        else:
            saveSet["topicCode"] = topicCode
    elif isAdd:
        #裁定 #1(2026-09-20): 新增时 topicCode 缺省由服务端生成, 不再要求调用方提供;
        #唯一性由 ch_topic.topicCode 的 UNIQUE 约束兜底(upsert 幂等)。
        saveSet["topicCode"] = _genTopicCode()

    #2) title(标题 ≤50)
    title = _toStr(dataSet.get("title"))
    if title:
        if len(title) > TITLE_MAX_LEN:
            addErr(ERR_FIELD_TOO_LONG, "title",
                   f"title(标题) 长度={len(title)} 超上限 {TITLE_MAX_LEN}")
        else:
            saveSet["title"] = title
    elif isAdd:
        addErr(ERR_FIELD_MISSING, "title", "title(标题) 为必填字段")

    #3) summary(简介 ≤200)
    summary = _toStr(dataSet.get("summary"))
    if summary:
        if len(summary) > SUMMARY_MAX_LEN:
            addErr(ERR_FIELD_TOO_LONG, "summary",
                   f"summary(简介) 长度={len(summary)} 超上限 {SUMMARY_MAX_LEN}")
        else:
            saveSet["summary"] = summary

    #4) description(详述 ≤5000 字, 无下限；超 5000 转存文件, 由调用方执行 IO)
    description = dataSet.get("description")
    description = description if isinstance(description, str) else _toStr(description)
    descriptionFileID = _toStr(dataSet.get("descriptionFileID"))

    if description:
        wordCount = countWords(description)
        meta["hasDescription"] = True
        meta["fullDescription"] = description
        meta["wordCount"] = wordCount

        if wordCount > DESCRIPTION_MAX_TRANSFER_WORDS:
            addErr(ERR_FILE_LIMIT, "description",
                   f"description(详述) 字数={wordCount} 超绝对上限 {DESCRIPTION_MAX_TRANSFER_WORDS}, 拒绝落盘")
        elif wordCount > DESCRIPTION_MAX_WORDS:
            #超上限: 转存文件(不静默截断), 库内保留有界预览
            meta["needTransfer"] = True
            saveSet["wordCount"] = wordCount
        else:
            saveSet["description"] = description
            saveSet["wordCount"] = wordCount
    else:
        if descriptionFileID:
            saveSet["descriptionFileID"] = descriptionFileID
        #裁定 #1(2026-09-20): 新增允许「空草稿」(详述可留空);
        #★ 2026-09-22 用户裁定: 取消 2000 字下限 —— 保存与提交渲染均不再按字数下限拦截,
        #  提交渲染仅在有「正文或 descriptionFileID」时放行(C4 仅拦「两者皆无」)。

    #5) status(状态机)
    status = _toStr(dataSet.get("status")).upper()
    if status:
        currStatus = _toStr(currDataSet.get("status"))
        errCode, rtnField, errMsg = checkStatusTransition(currStatus, status)
        if errCode:
            addErr(errCode, "status", errMsg)
        else:
            saveSet["status"] = status

    #6) publishStatus
    publishStatus = _toStr(dataSet.get("publishStatus")).upper()
    if publishStatus:
        if publishStatus not in PUBLISH_STATUS_LIST:
            addErr(ERR_FIELD_INVALID, "publishStatus",
                   f"publishStatus(发布状态) 取值非法: {publishStatus}, 允许值={PUBLISH_STATUS_LIST}")
        else:
            saveSet["publishStatus"] = publishStatus

    #7) aiFlag
    aiFlag = _toStr(dataSet.get("aiFlag"))
    if aiFlag:
        if aiFlag not in AI_FLAG_LIST:
            addErr(ERR_FIELD_INVALID, "aiFlag", f"aiFlag 取值非法: {aiFlag}, 允许值={AI_FLAG_LIST}")
        else:
            saveSet["aiFlag"] = aiFlag

    #8) assetCount(数值列, 异常经 toIntSafe 归 0, 与生成器「异常置 0」口径一致)
    if "assetCount" in dataSet and _toStr(dataSet.get("assetCount")) != "":
        saveSet["assetCount"] = comMysql.toIntSafe(dataSet.get("assetCount"), 0)

    #9) layoutCode(已选版式编码, 裁定 #2; 关联 ch_layout.layoutCode)
    layoutCode = _toStr(dataSet.get("layoutCode"))
    if layoutCode:
        if len(layoutCode) > LAYOUT_CODE_MAX_LEN:
            addErr(ERR_FIELD_TOO_LONG, "layoutCode",
                   f"layoutCode(版式编码) 长度={len(layoutCode)} 超上限 {LAYOUT_CODE_MAX_LEN}")
        else:
            saveSet["layoutCode"] = layoutCode

    #9.1) complianceStatus / complianceCheckedAt(合规通过态留痕; 成对写入更好, 但单列亦允许)
    complianceStatus = _toStr(dataSet.get("complianceStatus")).upper()
    if complianceStatus:
        if complianceStatus not in COMPLIANCE_STATUS_LIST:
            addErr(ERR_FIELD_INVALID, "complianceStatus",
                   f"complianceStatus(合规结论) 取值非法: {complianceStatus}, "
                   f"允许值={COMPLIANCE_STATUS_LIST}")
        else:
            saveSet["complianceStatus"] = complianceStatus

    complianceCheckedAt = _toStr(dataSet.get("complianceCheckedAt"))
    if complianceCheckedAt:
        if len(complianceCheckedAt) != COMPLIANCE_CHECKED_AT_LEN or not complianceCheckedAt.isdigit():
            addErr(ERR_FIELD_INVALID, "complianceCheckedAt",
                   f"complianceCheckedAt 需为 {COMPLIANCE_CHECKED_AT_LEN} 位 YYYYMMDDHHMMSS"
                   f"(实为 {complianceCheckedAt})")
        else:
            saveSet["complianceCheckedAt"] = complianceCheckedAt

    #10) 其余透传字段(空值不落库, 与生成器对空值的跳过语义保持一致)
    passthroughList = ["coverFileID", "coverThumbID", "author", "location", "source",
                       "period", "tagList", "categoryCode", "ownerID", "label", "memo"]
    for fieldName in passthroughList:
        value = _toStr(dataSet.get(fieldName))
        if value:
            saveSet[fieldName] = value

    if errList:
        errCode, rtnField, _errMsg = errList[0]
        return errCode, rtnField, [item[2] for item in errList], saveSet, meta

    return "B0", "", [], saveSet, meta


def _fillTopicFileUrls(data):
    """出参统一经 chCommon.fillFileUrls 转换 fileID -> URL(库内只存 fileID)"""
    try:
        return comCh.fillFileUrls(data)
    except Exception as e:
        if _LOG:
            _LOG.warning(f"W: PID:{_processorPID}, fillTopicFileUrls failed, errMsg:{str(e)}")
        return data

#===== 字段校验与归一 end =====


#===== 内部查询与转存 begin =====

def _queryOneTopic(recID = "", topicCode = ""):
    """按 recID 或 topicCode 取唯一主题记录; 未命中/歧义返回 None"""
    tableName = _tableName()
    dataList = []
    if recID:
        dataList = comMysql.query_ch_topic(tableName, recID)
    elif topicCode:
        dataList = comMysql.query_ch_topic(tableName, topicCode = topicCode)

    if len(dataList) == 1:
        return dataList[0]
    return None


def _transferDescriptionToFile(description, topicCode, loginID = ""):
    """把超长详述正文转存为文件, 返回 fileID(失败返回 "")。
       红线 R2: 只经 common/fileStorageCommon.py, 不出现任何厂商分支;
       延迟导入: fileStorageCommon 会牵出云厂商 SDK, 仅转存路径才需要。"""
    fileID = ""
    tmpPath = ""
    try:
        from common import fileStorageCommon as comFS

        fd, tmpPath = tempfile.mkstemp(suffix = ".txt", prefix = "ch_topic_desc_")
        with os.fdopen(fd, "w", encoding = "utf-8") as hFile:
            hFile.write(description)

        objectName = f"{DESCRIPTION_FILE_OBJECT_PREFIX}/{topicCode}_{misc.getTime()}.txt"
        fileID = comFS.saveFile(tmpPath, objectName = objectName, privateFlag = True,
                                bucketCode = comFS.chDefaultBucketCode())

        if not fileID and _LOG:
            _LOG.error(f"PID:{_processorPID}, description 转存失败(空 fileID), topicCode:{topicCode}")
    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, description 转存异常, topicCode:{topicCode}, errMsg:{e},{traceMsg}")
    finally:
        if tmpPath and os.path.isfile(tmpPath):
            try:
                os.remove(tmpPath)
            except Exception:
                pass

    return fileID

#===== 内部查询与转存 end =====


#===== 版本快照 begin =====

def _nextVersionNo(topicID):
    """下一个版本号(从 1 递增): 取该主题既有最大 versionNo + 1。
       注: 用 mode="short" 取数 —— 只需 versionNo(在 CH_QUERY_SHORT_COLUMNS 内),
           避免为算版本号把每版 snapshotJson(MEDIUMTEXT)全量拉回。"""
    maxNo = 0
    try:
        dataList = comMysql.query_ch_topic_version(_versionTableName(), topicID = topicID, mode = "short")
        for data in dataList:
            no = comMysql.toIntSafe(data.get("versionNo"), 0)
            if no > maxNo:
                maxNo = no
    except Exception as e:
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, _nextVersionNo topicID:{topicID}, errMsg:{str(e)}")
    return maxNo + 1


def saveTopicSnapshot(topicRecord, loginID = "", diffNote = ""):
    """为一条主题记录落版本快照(ch_topic_version)。
       verKey = {topicID}:{versionNo}, versionNo 从 1 递增; 幂等写入经 chCommon.upsertByUniqueKey。
       返回 (errCode, rtnData)。版本对比/回滚属 P2, 本轮只落快照 + 查询。"""
    if not isinstance(topicRecord, dict):
        return ERR_NO_RECORD, {"topicID": "", "versionNo": 0, "verKey": ""}

    topicID = comMysql.toIntSafe(topicRecord.get("recID"), 0)
    if topicID <= 0:
        return ERR_NO_RECORD, {"topicID": "", "versionNo": 0, "verKey": ""}

    versionNo = _nextVersionNo(topicID)
    verKey = f"{topicID}:{versionNo}"
    tableName = _versionTableName()

    try:
        snapshotJson = misc.jsonDumps(topicRecord)
    except Exception:
        snapshotJson = "{}"

    saveSet = {
        "verKey": verKey,
        "topicID": topicID,
        "versionNo": versionNo,
        "snapshotJson": snapshotJson,
        "diffNote": _toStr(diffNote),
        "ownerID": loginID,
        "regID": loginID,
        "regYMDHMS": misc.getTime(),
        "delFlag": DEL_FLAG_NORMAL,
    }

    recID = comCh.upsertByUniqueKey(
        tableName, verKey, saveSet,
        lambda t, v: comMysql.query_ch_topic_version(t, topicID = topicID, versionNo = versionNo),
        comMysql.insert_ch_topic_version,
        comMysql.update_ch_topic_version)

    if recID <= 0:
        return ERR_SNAPSHOT_FAILED, {"topicID": topicID, "versionNo": versionNo, "verKey": verKey}

    return "B0", {"recID": str(recID), "topicID": str(topicID),
                  "versionNo": str(versionNo), "verKey": verKey}


def queryTopicVersion(dataSet, sessionIDSet = None):
    """版本查询(交付: 按主题查询版本列表 / 按版本取快照):
       - 传 verKey(=topicID:versionNo) 或 topicID + versionNo -> 返回单条完整快照;
       - 仅传 topicID -> 返回该主题版本列表(short 列, 不含 snapshotJson);
       - 什么都不传 -> C4。出参经 fillFileUrls 收口。"""
    if not isinstance(dataSet, dict):
        dataSet = {}

    tableName = _versionTableName()
    verKey = _toStr(dataSet.get("verKey"))
    topicID = _toStr(dataSet.get("topicID"))
    versionNo = _toStr(dataSet.get("versionNo"))

    if verKey and not (topicID and versionNo):
        parts = verKey.split(":")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            topicID, versionNo = parts[0], parts[1]
        else:
            return _err(ERR_FIELD_INVALID, _fieldLabel("verKey"),
                        [f"verKey 格式非法(应为 topicID:versionNo): {verKey}"])

    if not topicID:
        return _err(ERR_FIELD_MISSING, _fieldLabel("topicID"),
                    ["topicID 为必填字段(或改传 verKey)"])

    try:
        if versionNo:
            #单版本取快照(full: 含 snapshotJson)
            dataList = comMysql.query_ch_topic_version(tableName, topicID = topicID,
                                                       versionNo = versionNo, mode = "full")
            if not dataList:
                return _err(ERR_NO_RECORD, _fieldLabel("versionNo"),
                            [f"无此版本记录: topicID={topicID}, versionNo={versionNo}"])
            data = dataList[0]
            return _ok(_fillTopicFileUrls({"data": data, "total": 1}))

        #按主题列版本(short: 不含 snapshotJson, 避免列表接口拉大字段)
        dataList = comMysql.query_ch_topic_version(tableName, topicID = topicID, mode = "short")
        return _ok(_fillTopicFileUrls({"data": dataList, "total": len(dataList)}))
    except Exception as e:
        return _err("ERR_GENERAL", "", [f"版本查询失败: {str(e)}"])


def addTopicVersion(dataSet, sessionIDSet = None):
    """手动落一次快照(用于回滚前的留档); 自动快照在保存主题时已落。
       入参: recID 或 topicCode 定位主题; diffNote 可选。"""
    if not isinstance(dataSet, dict):
        dataSet = {}

    loginID = _loginID(sessionIDSet)
    topicRecord = _queryOneTopic(_toStr(dataSet.get("recID")), _toStr(dataSet.get("topicCode")))
    if not topicRecord:
        return _err(ERR_NO_RECORD, _fieldLabel("recID"), ["无此主题记录, 无法落快照"])

    errCode, rtnData = saveTopicSnapshot(topicRecord, loginID, _toStr(dataSet.get("diffNote")))
    if errCode != "B0":
        return _err(errCode, _fieldLabel("versionNo"),
                    [f"版本快照落库失败: topicID={rtnData.get('topicID')}"])

    return _ok(rtnData)


def modifyTopicVersion(dataSet, sessionIDSet = None):
    """版本元信息修改: 只允许 diffNote / label / memo; 快照正文与版本号不可改(改则 C7)。"""
    if not isinstance(dataSet, dict):
        dataSet = {}

    loginID = _loginID(sessionIDSet)
    tableName = _versionTableName()

    recID = _toStr(dataSet.get("recID"))
    verKey = _toStr(dataSet.get("verKey"))

    if not recID and verKey:
        parts = verKey.split(":")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            dataList = comMysql.query_ch_topic_version(tableName, topicID = parts[0],
                                                       versionNo = parts[1], mode = "full")
            if dataList:
                recID = _toStr(dataList[0].get("recID"))
        if not recID:
            return _err(ERR_NO_RECORD, _fieldLabel("verKey"), [f"无此版本记录: verKey={verKey}"])

    if not recID:
        return _err(ERR_FIELD_MISSING, _fieldLabel("recID"), ["recID 或 verKey 为必填字段"])

    currDataList = comMysql.query_ch_topic_version(tableName, recID = recID, mode = "full")
    if len(currDataList) != 1:
        return _err(ERR_NO_RECORD, _fieldLabel("recID"), [f"无此版本记录: recID={recID}"])
    currDataSet = currDataList[0]

    #快照正文/版本号/所属主题不可改
    immutableList = ["snapshotJson", "versionNo", "topicID", "verKey"]
    for fieldName in immutableList:
        newValue = _toStr(dataSet.get(fieldName))
        if newValue and newValue != _toStr(currDataSet.get(fieldName)):
            return _err(ERR_FIELD_INVALID, _fieldLabel(fieldName),
                        [f"{fieldName} 不可修改(版本快照为不可变记录)"])

    saveSet = {"modifyID": loginID, "modifyYMDHMS": misc.getTime()}
    for fieldName in ["diffNote", "label", "memo"]:
        if fieldName in dataSet:
            saveSet[fieldName] = _toStr(dataSet.get(fieldName))

    rtn = comMysql.update_ch_topic_version(tableName, recID, saveSet)
    if rtn is None or comMysql.toIntSafe(rtn, -1) == -2:
        return _err("ERR_GENERAL", "", [f"版本元信息更新失败: recID={recID}"])

    return _ok({"recID": recID})


def deleteTopicVersion(dataSet, sessionIDSet = None):
    """版本软删除(delFlag="1", 红线: delFlag 用 "0"/"1")"""
    if not isinstance(dataSet, dict):
        dataSet = {}

    loginID = _loginID(sessionIDSet)
    tableName = _versionTableName()

    recID = _toStr(dataSet.get("recID"))
    verKey = _toStr(dataSet.get("verKey"))

    if not recID and verKey:
        parts = verKey.split(":")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            dataList = comMysql.query_ch_topic_version(tableName, topicID = parts[0],
                                                       versionNo = parts[1], mode = "short")
            if dataList:
                recID = _toStr(dataList[0].get("recID"))

    if not recID:
        return _err(ERR_FIELD_MISSING, _fieldLabel("recID"), ["recID 或 verKey 为必填字段"])

    currDataList = comMysql.query_ch_topic_version(tableName, recID = recID, mode = "short")
    if len(currDataList) != 1:
        return _err(ERR_NO_RECORD, _fieldLabel("recID"), [f"无此版本记录: recID={recID}"])

    saveSet = {"delFlag": DEL_FLAG_DELETED, "modifyID": loginID, "modifyYMDHMS": misc.getTime()}
    rtn = comMysql.update_ch_topic_version(tableName, recID, saveSet)

    return _ok({"recID": recID, "rtn": str(rtn)})

#===== 版本快照 end =====


#===== 会话小工具 begin =====

def _loginID(sessionIDSet):
    """从会话上下文取 loginID(缺省用系统默认自动 loginID, 与基线一致)"""
    if isinstance(sessionIDSet, dict):
        loginID = _toStr(sessionIDSet.get("loginID"))
        if loginID:
            return loginID
    return settings.SYS_DEFAULT_AUTO_LOGINID

#===== 会话小工具 end =====


#===== 主题 CRUD 业务入口 begin =====

def addTopic(dataSet, sessionIDSet = None):
    """新增主题(topicCode 幂等: 已存在则更新, 不产生重复数据)。
       保存成功后自动落版本快照。"""
    if not isinstance(dataSet, dict):
        dataSet = {}

    loginID = _loginID(sessionIDSet)

    errCode, rtnField, errMsgList, saveSet, meta = validateTopicFields(dataSet, mode = "add")
    if errCode != "B0":
        return _err(errCode, rtnField, errMsgList)

    #★ 提交渲染前置强校验(裁定 #1): 仅当本次直接以 RENDERING 建档时生效
    if _toStr(saveSet.get("status")).upper() == "RENDERING":
        rErrCode, rRtnField, rErrMsgList = _checkRenderReadiness(dataSet, None)
        if rErrCode:
            return _err(rErrCode, rRtnField, rErrMsgList)

    #回填系统字段
    saveSet.setdefault("status", TOPIC_STATUS_INITIAL)
    saveSet.setdefault("publishStatus", PUBLISH_STATUS_INITIAL)
    saveSet.setdefault("complianceStatus", COMPLIANCE_STATUS_INITIAL)
    saveSet.setdefault("aiFlag", "0")
    saveSet.setdefault("assetCount", 0)
    saveSet.setdefault("ownerID", loginID)
    saveSet["regID"] = loginID
    saveSet["regYMDHMS"] = misc.getTime()
    saveSet["delFlag"] = DEL_FLAG_NORMAL

    #详述超长 -> 转存文件(不静默截断)
    if meta.get("needTransfer"):
        topicCode = _toStr(saveSet.get("topicCode"))
        fileID = _transferDescriptionToFile(meta.get("fullDescription", ""), topicCode, loginID)
        if not fileID:
            return _err(ERR_FILE_UPLOAD, _fieldLabel("descriptionFileID"),
                        [f"description(详述) 超上限 {DESCRIPTION_MAX_WORDS} 字, 转存文件失败"])
        saveSet["descriptionFileID"] = fileID
        saveSet["description"] = meta.get("fullDescription", "")[:DESCRIPTION_INLINE_PREVIEW_CHARS]

    return _saveTopicWithSnapshot(saveSet, dataSet, loginID, mode = "add")


def modifyTopic(dataSet, sessionIDSet = None):
    """修改主题(按 recID 或 topicCode 定位; 局部更新, 未提供字段不校验不改动)。
       保存成功后自动落版本快照。"""
    if not isinstance(dataSet, dict):
        dataSet = {}

    loginID = _loginID(sessionIDSet)

    currDataSet = _queryOneTopic(_toStr(dataSet.get("recID")), _toStr(dataSet.get("topicCode")))
    if not currDataSet:
        return _err(ERR_NO_RECORD, _fieldLabel("recID"),
                    [f"无此主题记录: recID={_toStr(dataSet.get('recID'))}, "
                     f"topicCode={_toStr(dataSet.get('topicCode'))}"])

    #topicCode 变更时不得与其他主题冲突(库内 topicCode 为 UNIQUE)
    newTopicCode = _toStr(dataSet.get("topicCode"))
    if newTopicCode and newTopicCode != _toStr(currDataSet.get("topicCode")):
        if _queryOneTopic("", newTopicCode):
            return _err(ERR_DUPLICATE, _fieldLabel("topicCode"),
                        [f"topicCode(主题编码) 已存在: {newTopicCode}"])

    errCode, rtnField, errMsgList, saveSet, meta = validateTopicFields(
        dataSet, mode = "modify", currDataSet = currDataSet)
    if errCode != "B0":
        #非法状态跃迁等场景回显当前状态
        return _err(errCode, rtnField, errMsgList,
                    {"recID": _toStr(currDataSet.get("recID")),
                     "currentStatus": _toStr(currDataSet.get("status"))})

    #★ 提交渲染前置强校验(裁定 #1, 2026-09-22 取消下限): 状态跃迁到 RENDERING 时,
    #  详述须有「正文或已有 descriptionFileID」(C4 仅拦两者皆无, 不再按字数下限拦截)
    if _toStr(saveSet.get("status")).upper() == "RENDERING":
        rErrCode, rRtnField, rErrMsgList = _checkRenderReadiness(dataSet, currDataSet)
        if rErrCode:
            return _err(rErrCode, rRtnField, rErrMsgList,
                        {"recID": _toStr(currDataSet.get("recID")),
                         "currentStatus": _toStr(currDataSet.get("status"))})

    #详述超长 -> 转存文件(不静默截断)
    if meta.get("needTransfer"):
        topicCode = _toStr(saveSet.get("topicCode")) or _toStr(currDataSet.get("topicCode"))
        fileID = _transferDescriptionToFile(meta.get("fullDescription", ""), topicCode, loginID)
        if not fileID:
            return _err(ERR_FILE_UPLOAD, _fieldLabel("descriptionFileID"),
                        [f"description(详述) 超上限 {DESCRIPTION_MAX_WORDS} 字, 转存文件失败"])
        saveSet["descriptionFileID"] = fileID
        saveSet["description"] = meta.get("fullDescription", "")[:DESCRIPTION_INLINE_PREVIEW_CHARS]

    if not saveSet:
        return _err(ERR_FIELD_MISSING, "", ["没有任何需要更新的字段"])

    saveSet["modifyID"] = loginID
    saveSet["modifyYMDHMS"] = misc.getTime()
    #更新路径下 topicCode 用于幂等定位, 不重复写入(避免与 recID 定位冲突)
    if not _toStr(dataSet.get("topicCode")):
        saveSet.pop("topicCode", None)

    return _saveTopicWithSnapshot(saveSet, dataSet, loginID, mode = "modify",
                                  recID = _toStr(currDataSet.get("recID")))


def _saveTopicWithSnapshot(saveSet, dataSet, loginID, mode = "add", recID = ""):
    """落库主题(新增走 topicCode 幂等 upsert / 修改走 recID 定向更新) + 落版本快照 + 出参收口"""
    tableName = _tableName()

    try:
        if mode == "add":
            topicCode = _toStr(saveSet.get("topicCode"))
            recID = _toStr(comCh.upsertByUniqueKey(
                tableName, topicCode, saveSet,
                lambda t, v: comMysql.query_ch_topic(t, topicCode = v),
                comMysql.insert_ch_topic,
                comMysql.update_ch_topic))
        else:
            rtn = comMysql.update_ch_topic(tableName, recID, saveSet)
            if rtn is None:
                return _err("ERR_GENERAL", "", [f"主题更新失败: recID={recID}"])
    except Exception as e:
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, _saveTopicWithSnapshot mode:{mode}, errMsg:{str(e)}")
        return _err("ERR_GENERAL", "", [f"主题保存异常: {str(e)}"])

    if not recID or comMysql.toIntSafe(recID, 0) <= 0:
        return _err(ERR_DUPLICATE if mode == "add" else ERR_NO_RECORD, _fieldLabel("topicCode"),
                    [f"主题落库失败(mode={mode}, topicCode={_toStr(saveSet.get('topicCode'))})"])

    #回读落库后的完整记录(快照与出参都以库内为准)
    topicRecord = _queryOneTopic(recID)
    if not topicRecord:
        return _err(ERR_NO_RECORD, _fieldLabel("recID"), [f"主题落库后回读失败: recID={recID}"])

    #版本快照(保存主题时落快照)
    snapErrCode, snapData = saveTopicSnapshot(topicRecord, loginID, _toStr(dataSet.get("diffNote")))
    if snapErrCode != "B0" and _LOG:
        #快照失败不回滚主题(主题数据优先), 但必须留痕, 不静默
        _LOG.error(f"PID:{_processorPID}, 主题快照落库失败 recID:{recID}, verKey:{snapData.get('verKey')}")

    rtnData = {"recID": str(recID), "topicCode": _toStr(topicRecord.get("topicCode")),
               "status": _toStr(topicRecord.get("status")),
               "wordCount": _toStr(topicRecord.get("wordCount")),
               "versionNo": _toStr(snapData.get("versionNo")),
               "verKey": _toStr(snapData.get("verKey")),
               "data": topicRecord}

    return _ok(_fillTopicFileUrls(rtnData))


def deleteTopic(dataSet, sessionIDSet = None):
    """删除主题(软删除: delFlag="1", 与 query_ch_topic 的 delFlag 过滤一致)"""
    if not isinstance(dataSet, dict):
        dataSet = {}

    loginID = _loginID(sessionIDSet)
    tableName = _tableName()

    currDataSet = _queryOneTopic(_toStr(dataSet.get("recID")), _toStr(dataSet.get("topicCode")))
    if not currDataSet:
        return _err(ERR_NO_RECORD, _fieldLabel("recID"),
                    [f"无此主题记录: recID={_toStr(dataSet.get('recID'))}, "
                     f"topicCode={_toStr(dataSet.get('topicCode'))}"])

    recID = _toStr(currDataSet.get("recID"))
    saveSet = {"delFlag": DEL_FLAG_DELETED, "modifyID": loginID, "modifyYMDHMS": misc.getTime()}
    rtn = comMysql.update_ch_topic(tableName, recID, saveSet)

    return _ok({"recID": recID, "rtn": str(rtn)})


def queryTopic(dataSet, sessionIDSet = None):
    """主题查询(mode=short 走关键列; keyword 模糊匹配 title/summary/description)。
       出参统一经 chCommon.fillFileUrls 把 fileID 转 URL。"""
    if not isinstance(dataSet, dict):
        dataSet = {}

    tableName = _tableName()
    mode = _toStr(dataSet.get("mode")) or "full"
    order = _toStr(dataSet.get("order")) or "create"

    kwargs = {
        "recID": _toStr(dataSet.get("recID")),
        "topicCode": _toStr(dataSet.get("topicCode")),
        "status": _toStr(dataSet.get("status")),
        "publishStatus": _toStr(dataSet.get("publishStatus")),
        "ownerID": _toStr(dataSet.get("ownerID")),
        "categoryCode": _toStr(dataSet.get("categoryCode")),
        "keyword": _toStr(dataSet.get("keyword")),
        "beginYMDHMS": _toStr(dataSet.get("beginYMDHMS")),
        "endYMDHMS": _toStr(dataSet.get("endYMDHMS")),
        "mode": mode,
        "order": order,
    }
    limitNum = _toStr(dataSet.get("limitNum"))
    if limitNum != "":
        kwargs["limitNum"] = limitNum

    try:
        dataList = comMysql.query_ch_topic(tableName, **kwargs)
    except Exception as e:
        return _err("ERR_GENERAL", "", [f"主题查询失败: {str(e)}"])

    return _ok(_fillTopicFileUrls({"data": dataList, "total": len(dataList)}))

#===== 主题 CRUD 业务入口 end =====


if __name__ == "__main__":
    pass
    #本地自测(不连库): 只验证纯函数
    print("countWords 中文:", countWords("你好世界"))
    print("countWords 英文:", countWords("hello world, don't stop"))
    print("status DRAFT->RENDERING:", checkStatusTransition("DRAFT", "RENDERING"))
    print("status DRAFT->PUBLISHED:", checkStatusTransition("DRAFT", "PUBLISHED"))
