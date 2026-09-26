#! /usr/bin/env python3
#encoding: utf-8:

#Filename: auditService.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 审计留痕业务服务(SP4a · C6 投递链路随投递落地, 主计划 P3-5 / ch_audit_log)。
#
#职责(ch_audit_log 写入规范, 见 code/src/plan.md §4「审计写入规范」):
#  对每一次有副作用的关键动作写一条审计: action 形如 publish.push / publish.revoke;
#  字段齐备: actor / source / action / targetType / targetID / payloadDigest(sha256) /
#            result(OK|FAIL) / errMsg / costMs / ipAddr; **成功与失败都要留痕**。
#
#★ 凭据红线(R-19): payloadDigest 为**入参摘要**, 入参先经 sanitizePayload 脱敏 ——
#  凭据明文(appSecret/credentialCipher/password/token/... )一律替换为脱敏串, **绝不明文落库**。
#
#★ 可用性: 审计写入失败**不阻断主流程**(关键路径不得因审计失败而阻塞), 但必须记 error 日志, 并返回 0
#  由调用方在出参里标注 auditWritten="0"(不静默)。
#
#★ 分层契约(强制单向): 接入层(main/) -> 业务层(processor/) -> 引擎层(engine/) -> 公共层(common/)
#  本文件属业务处理器层, 只依赖 common/(mysqlCommon / credentialCipher / miscCommon);
#  **严禁 import main/subfunc**(接入层)。

_VERSION="20260919"


import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../code/src
if parentdir not in sys.path:
    sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #setdefaultencoding('utf-8')

import json
import traceback

#global defintion/common var etc.
from common import globalDefinition as comGD

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#数据层唯一入口(红线 R1): 本文件只写 ch_audit_log
from common import mysqlCommon as comMysql

#摘要与脱敏(凭据红线: 审计中不得出现凭据明文)
from common import credentialCipher


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    try:
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None


#===== 常量 begin =====

#动作名(与主计划 3.4 ch_audit_log 备注口径一致: 域.动作)
ACTION_PUBLISH_PUSH = "publish.push"         #投递到草稿箱/(受控)提交发布
ACTION_PUBLISH_REVOKE = "publish.revoke"     #撤销窗内撤销
ACTION_PUBLISH_CONFIRM = "publish.confirm"   #二次确认留痕(可选)
#★ SP4c: 归档清理动作(归档/清理动作本身必须留痕: 谁在何时删了什么)
ACTION_ARCHIVE_AUDIT_LOG = "archive.audit_log"          #ch_audit_log 分批归档(导出+删除)
ACTION_ARCHIVE_ARTIFACT = "archive.artifact_purge"      #ch_artifact 过期清理(置 EXPIRED + 删对象)

#来源
SOURCE_WEB = "web"
SOURCE_API = "api"
SOURCE_MCP = "mcp"
SOURCE_LIST = [SOURCE_WEB, SOURCE_API, SOURCE_MCP]

#结果
RESULT_OK = "OK"
RESULT_FAIL = "FAIL"
RESULT_LIST = [RESULT_OK, RESULT_FAIL]

#对象类型
TARGET_TYPE_PUBLISH_RECORD = "ch_publish_record"
TARGET_TYPE_ACCOUNT = "ch_account"
#★ SP4c: 归档清理动作的对象类型(ch_audit_log 归档 / ch_artifact 过期清理)
TARGET_TYPE_AUDIT_LOG = "ch_audit_log"
TARGET_TYPE_ARTIFACT = "ch_artifact"

#★ 脱敏字段名(大小写不敏感的子串匹配): 命中即替换为脱敏串, 绝不明文落库
SENSITIVE_FIELD_TOKEN_LIST = [
    "secret", "appsecret", "credentialcipher", "credentialiv", "password", "passwd",
    "token", "accesstoken", "refresh_token", "apikey", "api_key", "privatekey", "key",
]

#脱敏替换串
MASKED_VALUE = "***masked***"

#payloadDigest 折叠深度上限(防止异常深的结构)
MAX_SANITIZE_DEPTH = 6

#===== 常量 end =====


#===== 通用小工具 begin =====

def _toStr(value):
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


def _logError(message):
    if _LOG:
        _LOG.error(f"PID:{_processorPID}, {message}")


def _logWarn(message):
    if _LOG:
        _LOG.warning(f"W: PID:{_processorPID}, {message}")


def _isSensitiveField(fieldName):
    name = _toStr(fieldName).lower()
    if not name:
        return False
    for token in SENSITIVE_FIELD_TOKEN_LIST:
        if token in name:
            return True
    return False

#===== 通用小工具 end =====


#===== 脱敏 begin =====

def sanitizePayload(payload, depth = 0):
    """入参脱敏(供摘要计算与审计 memo 使用):
        - 敏感字段(命中 SENSITIVE_FIELD_TOKEN_LIST)→ MASKED_VALUE;
        - 下划线开头的内部字段(如 _IP/_source_server_http)→ 丢弃;
        - 递归处理 dict/list, 深度受 MAX_SANITIZE_DEPTH 限制;
        - 长文本折叠为前 200 字符摘要(避免审计表被大报文撑爆)。
       ★ 本函数保证返回值中**不含凭据明文**。"""
    if depth > MAX_SANITIZE_DEPTH:
        return "<max-depth>"

    if payload is None:
        return None
    if isinstance(payload, bool):
        return payload
    if isinstance(payload, (int, float)):
        return payload
    if isinstance(payload, str):
        return payload if len(payload) <= 200 else payload[:200] + "...(truncated)"
    if isinstance(payload, (list, tuple)):
        return [sanitizePayload(item, depth + 1) for item in payload]
    if isinstance(payload, dict):
        result = {}
        for key, value in payload.items():
            keyText = _toStr(key)
            if keyText.startswith("_"):
                continue
            if _isSensitiveField(keyText):
                result[keyText] = MASKED_VALUE
                continue
            result[keyText] = sanitizePayload(value, depth + 1)
        return result
    return _toStr(payload)


def buildPayloadDigest(payload):
    """入参摘要: sha256(canonical json of sanitized payload)。
       ★ 摘要基于**脱敏后**结构, 故凭据明文不参与摘要、也不落库。"""
    sanitized = sanitizePayload(payload)
    try:
        text = json.dumps(sanitized, sort_keys = True, ensure_ascii = False, default = str)
    except Exception:
        text = str(sanitized)
    return credentialCipher.sha256Hex(text)

#===== 脱敏 end =====


#===== 审计写入 begin =====

def buildAuditSaveSet(actor, action, targetType = "", targetID = "", payload = None,
                      result = RESULT_OK, errMsg = "", costMs = 0, ipAddr = "",
                      source = SOURCE_WEB, memo = ""):
    """构造 ch_audit_log 的写入字典(不落库; 便于单测/静态校验与复用)。
       ★ 字段齐备: actor/source/action/targetType/targetID/payloadDigest/result/errMsg/costMs/ipAddr。"""
    action = _toStr(action)
    result = _toStr(result).upper() or RESULT_OK
    source = _toStr(source).lower() or SOURCE_WEB
    if source not in SOURCE_LIST:
        source = SOURCE_WEB
    if result not in RESULT_LIST:
        result = RESULT_OK

    saveSet = {
        "actor": _toStr(actor),
        "source": source,
        "action": action,
        "targetType": _toStr(targetType),
        "targetID": _toStr(targetID),
        "payloadDigest": buildPayloadDigest(payload) if payload is not None else "",
        "result": result,
        "errMsg": _toStr(errMsg)[:500],
        "costMs": _toInt(costMs, 0),
        "ipAddr": _toStr(ipAddr),
        "memo": _toStr(memo)[:200],
        "regID": _toStr(actor),
        "regYMDHMS": misc.getTime(),
        "delFlag": "0",
    }
    return saveSet


def writeAudit(actor, action, targetType = "", targetID = "", payload = None,
               result = RESULT_OK, errMsg = "", costMs = 0, ipAddr = "",
               source = SOURCE_WEB, memo = ""):
    """写一条审计日志(ch_audit_log)。
       ★ 成功与失败都要留痕(调用方 result 传 OK/FAIL);
       ★ 写入失败**不抛异常**(不阻断主流程), 记 error 日志并返回 0。
       出参: recID(成功) / 0(失败)。"""
    saveSet = buildAuditSaveSet(actor, action, targetType, targetID, payload,
                                result = result, errMsg = errMsg, costMs = costMs,
                                ipAddr = ipAddr, source = source, memo = memo)
    tableName = comMysql.tablename_convertor_ch_audit_log()
    try:
        recID = comMysql.insert_ch_audit_log(tableName, saveSet)
        return _toInt(recID, 0)
    except Exception as e:
        _logError(f"审计写入失败 action:{action}, targetID:{targetID}, errMsg:{e}, "
                  f"{traceback.format_exc()}")
        return 0


def queryAuditLog(beginYMDHMS = "", endYMDHMS = "", action = "", actor = "",
                  targetID = "", result = "", limitNum = 200):
    """按条件查审计日志(**必须带时间范围**, ch_audit_log 默认 LIMIT 5000 为大表防护)。
       出参: [record, ...](查询失败降级为空列表并记日志)。"""
    if not _toStr(beginYMDHMS) and not _toStr(endYMDHMS) and not _toStr(targetID) and not _toStr(action):
        _logWarn("queryAuditLog 未带时间范围/条件: 已按默认 LIMIT 收敛, 请补充过滤条件")
    tableName = comMysql.tablename_convertor_ch_audit_log()
    try:
        return comMysql.query_ch_audit_log(tableName, actor = actor, action = action,
                                           result = result, targetID = targetID,
                                           beginYMDHMS = beginYMDHMS, endYMDHMS = endYMDHMS,
                                           mode = "short", limitNum = limitNum)
    except Exception as e:
        _logError(f"审计查询失败 action:{action}, errMsg:{e}")
        return []

#===== 审计写入 end =====


if __name__ == "__main__":
    pass
    #本地自测(不连库): 只验证脱敏与摘要
    _sample = {"topicID": "1", "appSecret": "PLAINTEXT-SHOULD-NOT-LEAK", "nested": {"accessToken": "tk"}}
    print("sanitized:", sanitizePayload(_sample))
    print("digest:", buildPayloadDigest(_sample)[:16])
    print("saveSet keys:", sorted(buildAuditSaveSet("u1", ACTION_PUBLISH_PUSH, "ch_publish_record", "9").keys()))
