#! /usr/bin/env python3
#encoding: utf-8:

#Filename: publishService.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 发布投递业务服务(SP4a · C6 投递链路, 主计划 2.5 / 5.4 P3-1·P3-3 / 6.4 R-03·R-04·R-17·R-19 / 7.2 U-13·U-14)。

#职责(C6 业务编排 —— 本模块是**唯一对外产生副作用的模块**):
#  1) 投递前置(硬闸门):
#       - 平台/通道判定: 仅 wechat_mp(draft_box)可投递; ★ 小红书一律**不投递、不发布**(平台红线),
#         通用 HTML 亦不投递(只导出);
#       - ch_artifact 为 READY(传 artifactID 时必须就绪; 草稿投递可无产物, 由 layoutCode 现场渲染);
#       - ★ **投递前必须过合规校验**: 调用 processor/complianceService.py::publishCheck
#         (SP3c 已交付的唯一闸门), 未过校验绝不投递;
#  2) 凭据安全(R-19):
#       - ch_account.credentialCipher/credentialIV 经 common/credentialCipher.py(AES-256-GCM)解密;
#         密钥经**环境变量** CH_CREDENTIAL_KEY 注入, **不入库、不入代码库**;
#       - 解密失败/未配置/已过期/未认证 -> 明确错误码 F0(不静默降级), 并回写 healthStatus;
#  3) access_token: 获取 + 进程内缓存 + 提前刷新(WECHAT_TOKEN_REFRESH_AHEAD_SECONDS);
#     失败按 R-03 明确回显(errcode/errmsg 可读), 并置 healthStatus=INVALID;
#  4) 图片转存: 正文/封面图经微信接口转存为 mmbiz.qpic.cn 可显示地址
#     (补齐 engine/inlineStyle.py 中 E4「需转存」分支的真实实现; 转存通道在 wechatMp.py);
#  5) 草稿投递: draft/add 并回写 remoteID(ch_artifact/publish_record 口径见 §4);
#  6) 幂等防重(P3-3 / R-04):
#       - idempotencyKey 幂等(形态 {artifactID}:{accountID}:{uuid4}), 同键二次提交被拒(F1)且不产生第二条记录;
#       - **二次确认**: 显式参数 confirmFlag + confirmToken 必填(F4), 并写审计留痕;
#       - **60 秒撤销窗**: 用「发布记录状态 + 推送时间」判断(不依赖 Redis), 逾窗拒绝(F5);
#       - 发布记录全字段落库 + 失败原因可读回显;
#  7) 推送 ≠ 发布: freepublish/submit **默认关闭**, 必须「人工二次确认 + ch_platform.autoPublishFlag=1
#     + 配置开关 WECHAT_AUTO_PUBLISH_ENABLED=1」三重条件同时满足才调用; 否则显式 F6 拒绝, **绝不默认群发**;
#  8) 审计留痕(P3-5): 成功与失败都写 ch_audit_log(actor/source/action/targetType/targetID/
#     payloadDigest(sha256)/result/errMsg/costMs/ipAddr); payloadDigest 不含凭据明文。
#
#★ 分层契约(强制单向): 接入层(main/) -> 业务层(processor/) -> 引擎层(engine/) -> 公共层(common/)
#  本文件属业务处理器层, 只依赖 processor/ 同层(complianceService/renderService/platformAdapter/auditService)、
#  engine/(layoutEngine)、common/ 与 config/; **严禁 import main/subfunc**(接入层)。
#
#错误码(contenthub msgKey; 见 code/src/plan.md §4):
#  C4 必填缺失 | C7 取值非法(平台无投递通道/产物未就绪/状态非法)| CB 无此记录 | CG 记录写入失败
#  F0 凭据无效/缺失/过期 | F1 幂等命中 | F3 平台拒绝 | F4 需二次确认 | F5 逾撤销窗 | F6 自动发布未开启
#  E1/E4 渲染与转存(经适配器透传) | D4 产物文件缺失

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

import datetime
import json
import threading
import time
import uuid

#global defintion/common var etc.
from common import globalDefinition as comGD

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#数据层唯一入口(红线 R1): ch_account / ch_artifact / ch_publish_record / ch_audit_log
from common import mysqlCommon as comMysql

#跨域业务公共件(唯一键幂等写入)
from common import chCommon as comCh

#凭据加解密(AES-256-GCM; 密钥经环境变量注入)
from common import credentialCipher

#setting files(投递开关/撤销窗/提前刷新秒数; ★ 平台凭据一律来自 ch_account, 不取本文件的环境变量兜底)
from config import wechatSettings

#业务层同层服务(合规闸门 / 渲染取数 / 适配器)
from processor import complianceService

from processor import renderService

from processor import auditService

from processor import platformAdapter

from processor.platformAdapter import base as adapterBase

#引擎层(版式定义读取)
from engine import layoutEngine


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    try:
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None


#===== 错误码与常量 begin =====

ERR_OK = "B0"
ERR_FIELD_MISSING = "C4"        #必填缺失
ERR_FIELD_INVALID = "C7"        #取值非法(无投递通道/产物未就绪/记录状态不允许撤销)
ERR_NO_RECORD = "CB"            #无此记录
ERR_DB_FAILED = "CG"            #记录写入失败(复用 contenthub「记录添加失败」)
ERR_FILE_NOT_FOUND = "D4"       #产物文件缺失
ERR_CREDENTIAL = "F0"           #凭据无效/缺失/过期/解密失败
ERR_IDEMPOTENT = "F1"           #幂等命中(重复提交)
ERR_PLATFORM_REJECTED = "F3"    #平台拒绝
ERR_CONFIRM_REQUIRED = "F4"     #需要人工二次确认
ERR_REVOKE_WINDOW = "F5"        #已超出撤销窗
ERR_AUTO_PUBLISH_DISABLED = "F6"  #自动发布未开启(须人工确认后发布)

#动作(同一端点 publishpush 内区分投递/撤销; 不新增 CMD)
ACTION_PUSH = "push"
ACTION_REVOKE = "revoke"
SUPPORTED_ACTION_LIST = [ACTION_PUSH, ACTION_REVOKE]

#投递形态(与 ch_platform.deliverMode 一致)
DELIVER_MODE_DRAFT_BOX = "draft_box"
DELIVER_MODE_ASSET_PACK = "asset_pack"
SUPPORTED_DELIVER_MODE_LIST = [DELIVER_MODE_DRAFT_BOX]

#★ 平台红线: 小红书**不投递、不发布**(只导出素材包); 通用 HTML 亦不投递
NON_DELIVERABLE_PLATFORM_LIST = ["xiaohongshu", "generic"]
#可投递平台(白名单; 与 NON_DELIVERABLE_PLATFORM_LIST 互为兜底: 既非白名单也非黑名单 -> C7)
DELIVERABLE_PLATFORM_LIST = ["wechat_mp"]

#产物台账状态(与 renderService 口径一致)
ARTIFACT_STATUS_READY = "READY"

#发布记录状态口径(ch_publish_record 无独立状态列: success + delFlag + pushedYMDHMS 组合表达)
PUBLISH_SUCCESS_YES = "1"
PUBLISH_SUCCESS_NO = "0"
PUBLISH_DELFLAG_REVOKED = "1"

#二次确认参数(显式参数 + 审计留痕; 无前端 -> 由调用方回显服务端下发的 confirmToken)
CONFIRM_FLAG_KEY = "confirmFlag"
CONFIRM_TOKEN_KEY = "confirmToken"

#自动发布参数(默认关闭; 需三重条件)
AUTO_PUBLISH_KEY = "autoPublish"
AUTO_PUBLISH_CONFIRM_KEY = "autoPublishConfirm"

#撤销窗与凭据到期预警
REVOKE_WINDOW_SECONDS = int(getattr(wechatSettings, "WECHAT_REVOKE_WINDOW_SECONDS", 60) or 60)
CREDENTIAL_EXPIRE_WARN_DAYS = 7
AUTO_PUBLISH_ENABLED = bool(getattr(wechatSettings, "WECHAT_AUTO_PUBLISH_ENABLED", False))
TOKEN_REFRESH_AHEAD_SECONDS = int(getattr(wechatSettings, "WECHAT_TOKEN_REFRESH_AHEAD_SECONDS", 300) or 300)

#access_token 进程内缓存(Redis 仅做加速属可选; 关键路径不依赖 Redis)
_TOKEN_CACHE = {}
_TOKEN_CACHE_LOCK = threading.Lock()

#审计动作名
AUDIT_ACTION_PUSH = auditService.ACTION_PUBLISH_PUSH
AUDIT_ACTION_REVOKE = auditService.ACTION_PUBLISH_REVOKE

#===== 错误码与常量 end =====


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


def _toBool(value):
    if isinstance(value, bool):
        return value
    return _toStr(value).lower() in ("1", "true", "yes", "on")


def _ok(data = None, errMsgList = None):
    return {"errCode": ERR_OK, "field": "", "errMsgList": errMsgList or [], "data": data or {}}


def _err(errCode, rtnField, errMsgList = None, data = None):
    return {"errCode": errCode, "field": rtnField, "errMsgList": errMsgList or [], "data": data or {}}


def _fieldLabel(fieldName):
    return f"{fieldName}(publishpush)"


def _logWarn(message):
    if _LOG:
        _LOG.warning(f"W: PID:{_processorPID}, {message}")


def _logError(message):
    if _LOG:
        _LOG.error(f"PID:{_processorPID}, {message}")


def _nowYMDHMS():
    return misc.getTime()


def parseYMDHMS(text):
    """14 位 YYYYMMDDHHMMSS -> datetime; 非法返回 None"""
    text = _toStr(text)
    if len(text) < 14:
        return None
    try:
        return datetime.datetime.strptime(text[:14], "%Y%m%d%H%M%S")
    except Exception:
        return None

#===== 通用小工具 end =====


#===== 幂等键与二次确认 begin =====

def buildIdempotencyKey(artifactID, accountID, nonce = None):
    """★ 幂等键形态(主计划 7.2 U-13): {artifactID}:{accountID}:{uuid4}
       nonce 可显式传入(便于调用方复用同一键做二次确认); 缺省生成 uuid4。"""
    nonce = _toStr(nonce) or uuid.uuid4().hex
    return f"{_toInt(artifactID, 0)}:{_toInt(accountID, 0)}:{nonce}"


def parseIdempotencyKey(idempotencyKey):
    """解析幂等键 -> (artifactID, accountID, nonce); 形态非法返回 (0, 0, \"\")"""
    parts = _toStr(idempotencyKey).split(":")
    if len(parts) < 3:
        return 0, 0, ""
    return _toInt(parts[0], 0), _toInt(parts[1], 0), ":".join(parts[2:])


def isValidIdempotencyKey(idempotencyKey):
    """幂等键必须为 {数字}:{数字}:{非空} 形态(与 chCommon.upsertByUniqueKey 的单列唯一键配套)"""
    artifactID, accountID, nonce = parseIdempotencyKey(idempotencyKey)
    return nonce != "" and _toStr(idempotencyKey).count(":") >= 2


def buildConfirmToken(idempotencyKey):
    """二次确认令牌: 由幂等键派生(把「确认」与该次投递强绑定, 防误确认)。
       ★ 令牌不含任何凭据信息; 调用方(前端)必须回显服务端下发的值。"""
    return credentialCipher.sha256Hex("contenthub.publish.confirm:" + _toStr(idempotencyKey))[:32]


def checkConfirmParams(dataSet, idempotencyKey):
    """★ 二次确认校验(P3-3): confirmFlag 必须为真 + confirmToken 必须与服务端派生值一致。
       合法返回 None; 非法返回错误出参(F4), 并在 data 中回显本次请求的 idempotencyKey/confirmToken 供回显确认。"""
    confirmFlag = dataSet.get(CONFIRM_FLAG_KEY)
    if not _toBool(confirmFlag):
        return _err(ERR_CONFIRM_REQUIRED, _fieldLabel(CONFIRM_FLAG_KEY),
                    [f"投递前必须人工二次确认: 请传 {CONFIRM_FLAG_KEY}=1(推送≠发布, 最终群发须人工在后台完成)"],
                    {"idempotencyKey": _toStr(idempotencyKey),
                     "confirmToken": buildConfirmToken(idempotencyKey),
                     "confirmFlagKey": CONFIRM_FLAG_KEY, "confirmTokenKey": CONFIRM_TOKEN_KEY})

    confirmToken = _toStr(dataSet.get(CONFIRM_TOKEN_KEY))
    if not confirmToken:
        return _err(ERR_CONFIRM_REQUIRED, _fieldLabel(CONFIRM_TOKEN_KEY),
                    [f"缺少二次确认令牌: 请回显 {CONFIRM_TOKEN_KEY}"],
                    {"idempotencyKey": _toStr(idempotencyKey),
                     "confirmToken": buildConfirmToken(idempotencyKey)})

    expectedToken = buildConfirmToken(idempotencyKey)
    if confirmToken != expectedToken:
        return _err(ERR_CONFIRM_REQUIRED, _fieldLabel(CONFIRM_TOKEN_KEY),
                    ["二次确认令牌不匹配(确认须与本次投递强绑定)"],
                    {"idempotencyKey": _toStr(idempotencyKey), "confirmToken": expectedToken})
    return None

#===== 幂等键与二次确认 end =====


#===== 取数: 产物/账号 begin =====

def queryArtifactRecord(artifactID):
    """按 recID 取 ch_artifact 记录; 未命中返回 {}"""
    artifactID = _toInt(artifactID, 0)
    if artifactID <= 0:
        return {}
    tableName = comMysql.tablename_convertor_ch_artifact()
    try:
        rows = comMysql.query_ch_artifact(tableName, recID = artifactID, mode = "full")
    except Exception as e:
        _logError(f"产物查询失败 artifactID:{artifactID}, errMsg:{e}")
        return {}
    for row in rows or []:
        if isinstance(row, dict):
            return row
    return {}


def resolveArtifactRecord(artifactID, topicID, platformCode, required = False):
    """产物前置校验(★ 投递前置: 确认 ch_artifact 为 READY)。
        - 显式传 artifactID(>0): 必须存在且 artifactStatus=READY, 否则 CB / C7;
        - 未传(草稿投递): required=False 时返回 (None, None)(产物不关联, artifactId 落 0);
          required=True 时按 topicID+platform 取最近一条 READY, 无则 C7。
       出参: (artifactRecord, errRtn)。"""
    artifactID = _toInt(artifactID, 0)
    if artifactID > 0:
        record = queryArtifactRecord(artifactID)
        if not record:
            return None, _err(ERR_NO_RECORD, _fieldLabel("artifactID"),
                              [f"无此产物记录: artifactID={artifactID}"])
        status = _toStr(record.get("artifactStatus"))
        if status != ARTIFACT_STATUS_READY:
            return None, _err(ERR_FIELD_INVALID, _fieldLabel("artifactStatus"),
                              [f"产物未就绪(artifactStatus={status or 'UNKNOWN'}), 拒绝投递: "
                               f"artifactID={artifactID}"],
                              {"artifactID": artifactID, "artifactStatus": status})
        return record, None

    if not required:
        return None, None

    tableName = comMysql.tablename_convertor_ch_artifact()
    try:
        rows = comMysql.query_ch_artifact(tableName, topicID = _toInt(topicID, 0),
                                          platform = _toStr(platformCode),
                                          artifactStatus = ARTIFACT_STATUS_READY, mode = "full")
    except Exception as e:
        return None, _err(ERR_DB_FAILED, _fieldLabel("artifactID"), [f"产物查询失败: {str(e)}"])

    candidates = [row for row in (rows or []) if isinstance(row, dict)]
    if not candidates:
        return None, _err(ERR_FIELD_INVALID, _fieldLabel("artifactID"),
                          [f"未找到 READY 产物: topicID={topicID}, platform={platformCode}"
                           f"(请先经 topicrender 渲染产物)"])
    candidates.sort(key = lambda data: _toInt(data.get("recID"), 0), reverse = True)
    return candidates[0], None


def loadAccountRecord(dataSet, platformCode):
    """取发布平台账号(ch_account): 优先 accountID > accountCode(+platform) > (platform 最新一条)。
       出参: (accountRecord, errRtn)。"""
    tableName = comMysql.tablename_convertor_ch_account()
    accountID = _toInt(dataSet.get("accountID"), 0)
    accountCode = _toStr(dataSet.get("accountCode"))
    try:
        if accountID > 0:
            rows = comMysql.query_ch_account(tableName, recID = accountID, mode = "full")
        elif accountCode:
            rows = comMysql.query_ch_account(tableName, accountCode = accountCode,
                                             platform = _toStr(platformCode), mode = "full")
        else:
            rows = comMysql.query_ch_account(tableName, platform = _toStr(platformCode), mode = "full")
    except Exception as e:
        return None, _err(ERR_DB_FAILED, _fieldLabel("accountID"), [f"账号查询失败: {str(e)}"])

    accountList = [row for row in (rows or []) if isinstance(row, dict)]
    if not accountList:
        return None, _err(ERR_FIELD_MISSING, _fieldLabel("accountID"),
                          [f"未找到发布账号: accountID={accountID}, accountCode={accountCode or '(空)'}, "
                           f"platform={platformCode}"])
    if accountID <= 0 and len(accountList) > 1:
        _logWarn(f"平台 {platformCode} 存在 {len(accountList)} 个账号, 未指定 accountID/accountCode, "
                 f"取 recID 最小者(请显式指定以免投错账号)")
        accountList.sort(key = lambda data: _toInt(data.get("recID"), 0))
    return accountList[0], None


def markAccountHealth(accountID, healthStatus, lastCheck = True, lastUse = False):
    """回写 ch_account.healthStatus / lastCheckYMDHMS / lastUseYMDHMS(失败仅记日志, 不阻断主流程)"""
    accountID = _toInt(accountID, 0)
    if accountID <= 0 or not _toStr(healthStatus):
        return
    saveSet = {"healthStatus": _toStr(healthStatus), "modifyYMDHMS": _nowYMDHMS()}
    if lastCheck:
        saveSet["lastCheckYMDHMS"] = _nowYMDHMS()
    if lastUse:
        saveSet["lastUseYMDHMS"] = _nowYMDHMS()
    try:
        tableName = comMysql.tablename_convertor_ch_account()
        comMysql.update_ch_account(tableName, accountID, saveSet)
    except Exception as e:
        _logWarn(f"账号健康状态回写失败 accountID:{accountID}, healthStatus:{healthStatus}, errMsg:{e}")

#===== 取数: 产物/账号 end =====


#===== 凭据解密 begin =====

def decryptAccountCredential(accountRecord):
    """★ 凭据读取与解密(R-19):
        - credentialCipher/credentialIV 经 AES-256-GCM 解密 -> appSecret;
        - ★ 凭据**唯一来源** = `ch_account`(用户在「第三方账号管理」页录入, 服务端加密落库);
          **不再回落环境变量**(CH_WECHAT_APPSECRET / CH_WECHAT_APPID 已不作为凭据来源);
        - 解密失败/未录入/已过期/healthStatus=INVALID 一律显式 F0(**不静默降级**)。
       出参: (credentialDict, errRtn); credentialDict={"appID","appSecret","healthStatus","source"}。"""
    accountRecord = accountRecord if isinstance(accountRecord, dict) else {}

    #1) 密码文优先(也是唯一来源)
    cipherText = accountRecord.get("credentialCipher")
    iv = accountRecord.get("credentialIV")
    appSecret = ""
    source = ""
    if _toStr(cipherText) and _toStr(iv):
        try:
            plainSecret = credentialCipher.decrypt(cipherText, iv)
        except credentialCipher.CredentialCipherError as e:
            return None, _err(ERR_CREDENTIAL, _fieldLabel("credentialCipher"),
                              [f"凭据解密失败: {e.message} (凭据可能已损坏或密钥不匹配)"])
        except Exception as e:
            return None, _err(ERR_CREDENTIAL, _fieldLabel("credentialCipher"),
                              [f"凭据解密异常: {str(e)}"])
        appSecret = _extractAppSecret(plainSecret)
        source = "ch_account.cipher"
        if not appSecret:
            return None, _err(ERR_CREDENTIAL, _fieldLabel("credentialCipher"),
                              ["凭据解密结果中未取到 appSecret(格式应为 JSON 或原样密钥串)"])

    #2) 未录入凭据即显式失败, 并引导到录入入口(不回落环境变量)
    #★ 2026-09-24 手改(凭据来源收口; 来源: 需求「凭据需用户输入而非环境变量」):
    #  ① 取消 CH_WECHAT_APPSECRET / CH_WECHAT_APPID 兜底 —— 平台凭据一律由用户在
    #     「第三方账号管理」(/my-accounts) 或「账号管理」(/accounts) 录入, 经 _applyAccountSecret
    #     以 AES-256-GCM 加密写入 credentialCipher/credentialIV(明文不落库、不回显);
    #  ② appID 与 appSecret 必须**成对取自同一条 ch_account 记录**: 跨源(环境 appID + 记录内
    #     AppSecret)混配会因 appID/secret 不匹配导致换取 access_token 失败, 且与「按归属各管
    #     本人账号」的多账号模型冲突(见 plan/前端开发计划.md 附录 B R-35)。
    if not appSecret:
        return None, _err(ERR_CREDENTIAL, _fieldLabel("credentialCipher"),
                          ["凭据未配置: 该账号尚未录入 AppSecret; 请在「第三方账号管理」页为该账号录入凭据"
                           "(由服务端 AES-256-GCM 加密落库, 明文不留存)"])

    appID = _toStr(accountRecord.get("appID"))
    if not appID:
        return None, _err(ERR_CREDENTIAL, _fieldLabel("appID"),
                          ["appID 未配置: 请在「第三方账号管理」页为该账号填写平台 appID"
                           "(须与所录入的 AppSecret 属同一公众号)"])

    #3) 有效期与健康状态
    expireYMDHMS = _toStr(accountRecord.get("expireYMDHMS"))
    expireAt = parseYMDHMS(expireYMDHMS)
    if expireAt is not None:
        now = datetime.datetime.now()
        if expireAt <= now:
            return None, _err(ERR_CREDENTIAL, _fieldLabel("expireYMDHMS"),
                              [f"凭据已过期: expireYMDHMS={expireYMDHMS}(R-03 凭据静默失效前置拦截)"])
    healthStatus = _toStr(accountRecord.get("healthStatus")).upper()
    if healthStatus == "INVALID":
        return None, _err(ERR_CREDENTIAL, _fieldLabel("healthStatus"),
                          ["账号凭据健康状态为 INVALID: 请先更新凭据并完成健康检查(R-03)"])

    #到期预警(不阻断, 仅回写状态)
    if expireAt is not None and expireAt <= datetime.datetime.now() + datetime.timedelta(
            days = CREDENTIAL_EXPIRE_WARN_DAYS):
        healthStatus = "EXPIRING"

    return {"appID": appID, "appSecret": appSecret,
            "healthStatus": healthStatus or "OK", "source": source,
            "expireYMDHMS": expireYMDHMS}, None


def _extractAppSecret(plainSecret):
    """解密结果可能是 JSON({"appSecret"/"secret"}) 或原样密钥串"""
    text = _toStr(plainSecret)
    if not text:
        return ""
    if text.startswith("{"):
        try:
            data = json.loads(text)
            for key in ("appSecret", "appsecret", "secret", "app_secret"):
                if isinstance(data, dict) and _toStr(data.get(key)):
                    return _toStr(data.get(key))
        except Exception:
            pass
    return text


def saveAccountCredential(accountID, plainSecret, appID = None, expireYMDHMS = None,
                          healthStatus = "OK", rawKey = None):
    """★ ch_account 凭据**写入**（R-19 读写闭环）：明文经 AES-256-GCM 加密后只落
       `credentialCipher`(密文+认证标签) 与 `credentialIV`(IV)，**明文与密钥永不落库**。
       入参: accountID 必填; plainSecret 明文 appSecret(或 {"appSecret":...} JSON 串);
             appID/expireYMDHMS/healthStatus 可选; rawKey 可选(缺省取环境变量 CH_CREDENTIAL_KEY)。
       出参: (recID, errRtn); 加密失败/入参非法/写库失败一律明确错误码, **不静默**。
       ★ 本轮**不暴露对外端点**(不新增 CMD)，由运维脚本或后续子计划调用。"""
    accountID = _toInt(accountID, 0)
    if accountID <= 0:
        return 0, _err(ERR_FIELD_MISSING, _fieldLabel("accountID"), ["accountID 为必填字段"])

    secret = _toStr(plainSecret)
    if not secret:
        return 0, _err(ERR_FIELD_MISSING, _fieldLabel("plainSecret"), ["凭据明文为空"])

    payload = secret if secret.startswith("{") else json.dumps({"appSecret": secret}, ensure_ascii = False)
    try:
        encRtn = credentialCipher.encrypt(payload, rawKey = rawKey)
    except credentialCipher.CredentialCipherError as e:
        return 0, _err(e.errCode, _fieldLabel("credentialCipher"), [f"凭据加密失败: {e.message}"])
    except Exception as e:
        return 0, _err(ERR_CREDENTIAL, _fieldLabel("credentialCipher"), [f"凭据加密异常: {str(e)}"])

    saveSet = {
        "credentialCipher": encRtn.get("cipher", ""),
        "credentialIV": encRtn.get("iv", ""),
        "healthStatus": _toStr(healthStatus) or "OK",
        "modifyYMDHMS": _nowYMDHMS(),
    }
    if _toStr(appID):
        saveSet["appID"] = _toStr(appID)
    if _toStr(expireYMDHMS):
        saveSet["expireYMDHMS"] = _toStr(expireYMDHMS)

    try:
        tableName = comMysql.tablename_convertor_ch_account()
        comMysql.update_ch_account(tableName, accountID, saveSet)
    except Exception as e:
        return 0, _err(ERR_DB_FAILED, _fieldLabel("accountID"), [f"凭据写入失败: {str(e)}"])
    return accountID, None

#===== 凭据解密 end =====


#===== access_token 获取 + 缓存 + 提前刷新 begin =====

def getAccessToken(appID, appSecret, adapter, timeout = None, forceRefresh = False):
    """access_token 获取 + 进程内缓存 + 提前刷新(避免临界期失效)。
       出参: (accessToken, errRtn); 失败时 errRtn 为适配器返回的明确错误(F0/F3, 含 errcode/errmsg)。"""
    cacheKey = _toStr(appID)
    now = time.time()

    if not forceRefresh:
        with _TOKEN_CACHE_LOCK:
            entry = _TOKEN_CACHE.get(cacheKey)
        if entry and now < float(entry.get("expireAt", 0) or 0) - TOKEN_REFRESH_AHEAD_SECONDS:
            return _toStr(entry.get("accessToken")), None

    fetchFunc = getattr(adapter, "fetchAccessToken", None)
    if fetchFunc is None:
        return "", _err(ERR_FIELD_INVALID, _fieldLabel("accessToken"),
                        [f"平台适配器未提供 access_token 通道: platformCode={getattr(adapter, 'platformCode', '')}"])

    rtn = fetchFunc(appID, appSecret, timeout = timeout)
    if not isinstance(rtn, dict):
        rtn = {}
    if rtn.get("errCode") != ERR_OK:
        return "", rtn

    data = rtn.get("data") or {}
    accessToken = _toStr(data.get("accessToken"))
    expiresIn = _toInt(data.get("expiresIn"), 0)
    if not accessToken:
        return "", _err(ERR_CREDENTIAL, _fieldLabel("accessToken"), ["access_token 换取失败: 响应为空"])

    #expires_in 非法时给一个保守的短有效期, 依赖提前刷新兜底
    if expiresIn <= 0:
        expiresIn = 7200
    with _TOKEN_CACHE_LOCK:
        _TOKEN_CACHE[cacheKey] = {"accessToken": accessToken, "expireAt": now + expiresIn}
    return accessToken, None


def clearAccessTokenCache(appID = None):
    """清空 token 缓存(诊断/强制刷新用)"""
    with _TOKEN_CACHE_LOCK:
        if appID is None:
            _TOKEN_CACHE.clear()
        else:
            _TOKEN_CACHE.pop(_toStr(appID), None)

#===== access_token end =====


#===== 自动发布闸门(推送≠发布) begin =====

def checkAutoPublishGate(dataSet, platformRecord, accountRecord = None):
    """★ 正式发布闸门(freepublish/submit; 默认关闭, 以下条件缺一不可):
        ① ch_platform.autoPublishFlag = "1"   ② 配置 WECHAT_AUTO_PUBLISH_ENABLED = True
        ③ 请求显式携带 autoPublishConfirm=1(人工二次确认)
        ④ 账号已认证且非个人主体(verifiedFlag="1" 且 subjectType != personal; 主计划 2.4 平台能力矩阵)
       若请求未要求自动发布 -> (False, None) 正常走草稿投递;
       若请求要求自动发布但条件不足 -> (False, errRtn(F6) 显式拒绝, **绝不默认群发**)。"""
    if not _toBool(dataSet.get(AUTO_PUBLISH_KEY)):
        return False, None

    normalized = adapterBase.normalizePlatformRecord(platformRecord)
    accountRecord = accountRecord if isinstance(accountRecord, dict) else {}
    autoPublishFlag = _toStr(normalized.get("autoPublishFlag")) or "0"
    verifiedFlag = _toStr(accountRecord.get("verifiedFlag")) or "0"
    subjectType = _toStr(accountRecord.get("subjectType")).lower()

    reasonList = []
    if autoPublishFlag != "1":
        reasonList.append(f"ch_platform.autoPublishFlag={autoPublishFlag}(平台/账号未开启自动发布)")
    if not AUTO_PUBLISH_ENABLED:
        reasonList.append("配置开关 WECHAT_AUTO_PUBLISH_ENABLED 未开启(默认关闭)")
    if not _toBool(dataSet.get(AUTO_PUBLISH_CONFIRM_KEY)):
        reasonList.append(f"缺少人工二次确认: 请显式传 {AUTO_PUBLISH_CONFIRM_KEY}=1")
    if verifiedFlag != "1" or subjectType == "personal":
        reasonList.append(f"账号未认证或为个人主体(verifiedFlag={verifiedFlag}, "
                          f"subjectType={subjectType or 'unknown'}), 不具备 freepublish 权限")
    if reasonList:
        return False, _err(ERR_AUTO_PUBLISH_DISABLED, _fieldLabel(AUTO_PUBLISH_KEY),
                           ["自动发布被拒绝(推送≠发布, 最终群发须人工在后台完成): " + "; ".join(reasonList)],
                           {"autoPublishRequested": "1", "autoPublishAllowed": "0",
                            "autoPublishFlag": autoPublishFlag, "verifiedFlag": verifiedFlag,
                            "autoPublishEnabled": "1" if AUTO_PUBLISH_ENABLED else "0"})
    return True, None

#===== 自动发布闸门 end =====


#===== 发布记录(ch_publish_record) begin =====

def queryPublishRecord(idempotencyKey = "", recID = "0", delFlag = "0"):
    """按幂等键/recID 取发布记录; 未命中返回 {}。
       ★ delFlag 传 "" 表示**不过滤已删除**: 幂等判定/撤销判定必须能看到 delFlag=1(已撤销)的记录,
        否则「已撤销 -> F1」「失败后同键重试」两条分支都会失效(记录被默认过滤掉 -> 误判为无记录)。"""
    tableName = comMysql.tablename_convertor_ch_publish_record()
    try:
        if _toInt(recID, 0) > 0:
            rows = comMysql.query_ch_publish_record(tableName, recID = recID, mode = "full", delFlag = delFlag)
        elif _toStr(idempotencyKey):
            rows = comMysql.query_ch_publish_record(tableName, idempotencyKey = idempotencyKey, mode = "full",
                                                    delFlag = delFlag)
        else:
            return {}
    except Exception as e:
        _logError(f"发布记录查询失败 idempotencyKey:{idempotencyKey}, recID:{recID}, errMsg:{e}")
        return {}
    for row in rows or []:
        if isinstance(row, dict):
            return row
    return {}


def savePublishRecord(idempotencyKey, saveSet):
    """★ 发布记录全字段落库(幂等: 唯一键 idempotencyKey; 生成器不支持 ON DUPLICATE KEY, 走 upsert)。
       出参: recID(失败 0)。"""
    tableName = comMysql.tablename_convertor_ch_publish_record()
    return comCh.upsertByUniqueKey(
        tableName, idempotencyKey, saveSet,
        #查询须含已撤销记录(delFlag=""): 否则同键重试会因唯一键冲突插入失败, 破坏「原地覆盖不产生第二条记录」
        lambda t, v: comMysql.query_ch_publish_record(t, idempotencyKey = v, delFlag = ""),
        comMysql.insert_ch_publish_record,
        comMysql.update_ch_publish_record)


def buildPublishSaveSet(idempotencyKey, artifactID, topicID, accountID, platformCode, deliverMode,
                        requestPayload, responsePayload, errcode, errmsg, success, remoteID,
                        operator, autoPublishFlag = "0", memo = ""):
    """构造 ch_publish_record 全字段写入字典(对外出参/审计均基于脱敏后 payload)"""
    nowYMDHMS = _nowYMDHMS()
    return {
        "idempotencyKey": _toStr(idempotencyKey),
        "artifactId": _toInt(artifactID, 0),
        "topicID": _toInt(topicID, 0),
        "accountID": _toInt(accountID, 0),
        "platform": _toStr(platformCode),
        "deliverMode": _toStr(deliverMode),
        "requestJson": auditService.sanitizePayload(requestPayload or {}),
        "responseJson": auditService.sanitizePayload(responsePayload or {}),
        "errcode": _toInt(errcode, 0),
        "errmsg": _toStr(errmsg)[:500],
        "success": _toStr(success) or PUBLISH_SUCCESS_NO,
        "remoteID": _toStr(remoteID),
        "operator": _toStr(operator),
        "pushedYMDHMS": nowYMDHMS,
        "label": "",
        "memo": f"autoPublish={autoPublishFlag}; {_toStr(memo)}"[:200],
        "regID": _toStr(operator),
        "regYMDHMS": nowYMDHMS,
        "delFlag": "0",
    }


def checkRevokeWindow(record, windowSeconds = None):
    """★ 60 秒撤销窗(用「记录状态 + 推送时间」判断, 不依赖 Redis)。
       出参: (allowedFlag, elapsedSeconds, reason)"""
    windowSeconds = _toInt(windowSeconds, 0) or REVOKE_WINDOW_SECONDS
    pushedAt = parseYMDHMS(record.get("pushedYMDHMS") if isinstance(record, dict) else "")
    if pushedAt is None:
        return False, -1, "发布记录缺少有效推送时间(pushedYMDHMS), 无法判定撤销窗"
    elapsed = int((datetime.datetime.now() - pushedAt).total_seconds())
    if elapsed < 0:
        elapsed = 0
    if elapsed > windowSeconds:
        return False, elapsed, f"已超出撤销窗({elapsed}s > {windowSeconds}s)"
    return True, elapsed, ""

#===== 发布记录 end =====


#===== 审计辅助 begin =====

def _writeAudit(actor, action, targetID, payload, result, errMsg, costMs, ipAddr, source, memo = ""):
    """写审计(成功与失败都留痕; 失败不阻断主流程)"""
    return auditService.writeAudit(actor = actor, action = action,
                                   targetType = auditService.TARGET_TYPE_PUBLISH_RECORD,
                                   targetID = _toStr(targetID), payload = payload,
                                   result = result, errMsg = errMsg, costMs = costMs,
                                   ipAddr = ipAddr, source = source, memo = memo)


def _failAudited(errRtn, actor, action, targetID, payload, startTime, ipAddr, source, memo = ""):
    """失败收口: 写审计 FAIL + 补 costMs, 返回原错误出参"""
    costMs = int((time.time() - startTime) * 1000)
    errMsg = ";".join(errRtn.get("errMsgList") or []) or _toStr(errRtn.get("errCode"))
    auditID = _writeAudit(actor, action, targetID, payload, auditService.RESULT_FAIL,
                          errMsg, costMs, ipAddr, source, memo = memo)
    errRtn.setdefault("data", {})
    errRtn["data"].update({"costMs": costMs, "auditWritten": "1" if auditID else "0"})
    return errRtn

#===== 审计辅助 end =====


#===== 业务入口: 投递 / 撤销(publishpush) begin =====

def publishPush(dataSet, sessionIDSet = None):
    """publishpush 业务入口(C6 投递编排)。
       入参(dataSet):
         action            可选 push(默认) / revoke
         platform          必填平台编码(仅 wechat_mp 提供投递通道)
         topicID           必填(或由 artifactID 反推)
         layoutCode        必填(投递需现场渲染平台形态产物)
         artifactID        可选(传则必须 READY; 草稿投递可省)
         accountID/accountCode  可选(ch_account; 缺省按平台取)
         idempotencyKey    可选(缺省生成 {artifactID}:{accountID}:{uuid4})
         confirmFlag/confirmToken  ★ 必填(二次确认; 首次调用返回 F4 并下发 confirmToken)
         autoPublish       可选(默认 0; 为 1 时受三重闸门约束, 否则 F6 显式拒绝)
         ownerID/operator  可选(操作者)
       出参: {"errCode","field","errMsgList","data"}。"""
    startTime = time.time()
    dataSet = dataSet if isinstance(dataSet, dict) else {}
    sessionIDSet = sessionIDSet if isinstance(sessionIDSet, dict) else {}

    actor = _toStr(sessionIDSet.get("loginID")) or _toStr(dataSet.get("operator")) or "anonymous"
    ipAddr = _toStr(dataSet.get("_IP"))
    source = _toStr(dataSet.get("source")).lower() or auditService.SOURCE_WEB

    #0) 动作分发(同一端点: push / revoke; 不新增 CMD)
    action = _toStr(dataSet.get("action")).lower() or ACTION_PUSH
    if action not in SUPPORTED_ACTION_LIST:
        return _failAudited(_err(ERR_FIELD_INVALID, _fieldLabel("action"),
                                 [f"action 取值非法: {action}, 允许值={SUPPORTED_ACTION_LIST}"]),
                            actor, AUDIT_ACTION_PUSH, "", dataSet, startTime, ipAddr, source)
    if action == ACTION_REVOKE:
        return revokePublish(dataSet, sessionIDSet)

    #1) 通道判定(★ 平台红线: 小红书不投递/不发布)
    platformCode = _toStr(dataSet.get("platform"))
    if not platformCode:
        return _failAudited(_err(ERR_FIELD_MISSING, _fieldLabel("platform"), ["platform 为必填字段"]),
                            actor, AUDIT_ACTION_PUSH, "", dataSet, startTime, ipAddr, source)
    if platformCode in NON_DELIVERABLE_PLATFORM_LIST:
        return _failAudited(_err(ERR_FIELD_INVALID, _fieldLabel("platform"),
                                 [f"平台 {platformCode} 不提供投递/发布通道(平台红线: "
                                  f"小红书只导出素材包, 绝不投递/发布; 通用 HTML 只导出)"]),
                            actor, AUDIT_ACTION_PUSH, "", dataSet, startTime, ipAddr, source)
    if platformCode not in DELIVERABLE_PLATFORM_LIST:
        return _failAudited(_err(ERR_FIELD_INVALID, _fieldLabel("platform"),
                                 [f"平台无投递通道: platformCode={platformCode}, "
                                  f"可投递={DELIVERABLE_PLATFORM_LIST}"]),
                            actor, AUDIT_ACTION_PUSH, "", dataSet, startTime, ipAddr, source)

    platformRecord, platformErr = renderService._fetchPlatformRecord(platformCode)
    if platformErr is not None:
        return _failAudited(platformErr, actor, AUDIT_ACTION_PUSH, "", dataSet, startTime, ipAddr, source)

    deliverMode = _toStr((platformRecord or {}).get("deliverMode"))
    if deliverMode not in SUPPORTED_DELIVER_MODE_LIST:
        return _failAudited(_err(ERR_FIELD_INVALID, _fieldLabel("deliverMode"),
                                 [f"投递形态不支持: deliverMode={deliverMode}, "
                                  f"支持={SUPPORTED_DELIVER_MODE_LIST}"]),
                            actor, AUDIT_ACTION_PUSH, "", dataSet, startTime, ipAddr, source)

    adapter = platformAdapter.getAdapter(platformCode, platformRecord)
    if adapter is None or type(adapter).deliver is adapterBase.PlatformAdapter.deliver:
        return _failAudited(_err(ERR_FIELD_INVALID, _fieldLabel("platform"),
                                 [f"平台 {platformCode} 未实现投递通道(deliver 仍为基类未实现)"]),
                            actor, AUDIT_ACTION_PUSH, "", dataSet, startTime, ipAddr, source)

    #2) 账号 + 凭据(R-19)
    accountRecord, accountErr = loadAccountRecord(dataSet, platformCode)
    if accountErr is not None:
        return _failAudited(accountErr, actor, AUDIT_ACTION_PUSH, "", dataSet, startTime, ipAddr, source)
    accountID = _toInt(accountRecord.get("recID"), 0)

    credential, credentialErr = decryptAccountCredential(accountRecord)
    if credentialErr is not None:
        #解密失败/过期/未认证 -> 明确回写健康状态(不静默降级)
        markAccountHealth(accountID, "INVALID")
        return _failAudited(credentialErr, actor, AUDIT_ACTION_PUSH, _toStr(accountID), dataSet,
                            startTime, ipAddr, source)

    #3) 产物前置(★ ch_artifact 为 READY)
    artifactID = _toInt(dataSet.get("artifactID"), 0)
    topicID = _toStr(dataSet.get("topicID")) or _toStr(dataSet.get("recID"))
    if not topicID and artifactID > 0:
        topicID = _toStr(queryArtifactRecord(artifactID).get("topicID"))
    if not topicID:
        return _failAudited(_err(ERR_FIELD_MISSING, _fieldLabel("topicID"), ["topicID 为必填字段"]),
                            actor, AUDIT_ACTION_PUSH, "", dataSet, startTime, ipAddr, source)

    artifactRecord, artifactErr = resolveArtifactRecord(artifactID, topicID, platformCode,
                                                        required = (deliverMode != DELIVER_MODE_DRAFT_BOX))
    if artifactErr is not None:
        return _failAudited(artifactErr, actor, AUDIT_ACTION_PUSH, _toStr(artifactID), dataSet,
                            startTime, ipAddr, source)
    if artifactRecord:
        artifactID = _toInt(artifactRecord.get("recID"), artifactID)

    layoutCode = _toStr(dataSet.get("layoutCode"))
    if not layoutCode:
        return _failAudited(_err(ERR_FIELD_MISSING, _fieldLabel("layoutCode"),
                                 ["layoutCode 为必填字段(投递需现场渲染平台形态产物)"]),
                            actor, AUDIT_ACTION_PUSH, "", dataSet, startTime, ipAddr, source)

    #4) 幂等 + 二次确认(P3-3; 先于昂贵的合规/渲染, 避免重复提交产生副作用)
    nonce = _toStr(dataSet.get("nonce"))
    idempotencyKey = _toStr(dataSet.get("idempotencyKey"))
    if idempotencyKey:
        if not isValidIdempotencyKey(idempotencyKey):
            return _failAudited(_err(ERR_FIELD_INVALID, _fieldLabel("idempotencyKey"),
                                     [f"idempotencyKey 形态非法: 应为 {{artifactID}}:{{accountID}}:{{uuid4}}, "
                                      f"实为 {idempotencyKey}"]),
                                actor, AUDIT_ACTION_PUSH, "", dataSet, startTime, ipAddr, source)
    else:
        idempotencyKey = buildIdempotencyKey(artifactID, accountID, nonce = nonce)

    #★ 幂等判定口径(2026-09-24 修正): 只有「已成功投递」或「已撤销」才算幂等命中(F1);
    #  上次**失败**的记录(success != 1, 如 C4 封面缺失/F3 平台拒绝)必须允许**同键重试** ——
    #  修复前「失败也落库 + 命中即 F1」会把失败死锁住: 前端拿到 F4 后回显的同一 idempotencyKey
    #  重试恒返回「F1 幂等命中, 已投递」(而 success=0), 用户改好了素材也无法重新投递。
    #  重试仍不产生第二条记录: 落库走唯一键 upsert(ch_publish_record.idempotencyKey UNIQUE)-> 原地覆盖。
    duplicateRecord = queryPublishRecord(idempotencyKey = idempotencyKey, delFlag = "")
    retryOfFailed = False
    if duplicateRecord:
        revoked = _toStr(duplicateRecord.get("delFlag")) == PUBLISH_DELFLAG_REVOKED
        lastSuccess = _toStr(duplicateRecord.get("success")) or PUBLISH_SUCCESS_NO
        if revoked or lastSuccess == PUBLISH_SUCCESS_YES:
            return _failAudited(_err(ERR_IDEMPOTENT, _fieldLabel("idempotencyKey"),
                                     [f"幂等命中: 该 idempotencyKey 已{'撤销' if revoked else '成功投递'}"
                                      f"(不产生第二条发布记录)"],
                                     {"idempotencyKey": idempotencyKey,
                                      "publishRecordID": _toInt(duplicateRecord.get("recID"), 0),
                                      "remoteID": _toStr(duplicateRecord.get("remoteID")),
                                      "success": lastSuccess,
                                      "revoked": "1" if revoked else "0",
                                      "pushedYMDHMS": _toStr(duplicateRecord.get("pushedYMDHMS"))}),
                                actor, AUDIT_ACTION_PUSH, _toStr(duplicateRecord.get("recID")),
                                {"idempotencyKey": idempotencyKey}, startTime, ipAddr, source)
        retryOfFailed = True
        _logWarn(f"幂等键命中失败记录, 允许同键重试 idempotencyKey:{idempotencyKey}, "
                 f"recID:{_toStr(duplicateRecord.get('recID'))}, lastSuccess:{lastSuccess}, "
                 f"lastErrmsg:{_toStr(duplicateRecord.get('errmsg'))[:200]}")

    confirmErr = checkConfirmParams(dataSet, idempotencyKey)
    if confirmErr is not None:
        return _failAudited(confirmErr, actor, AUDIT_ACTION_PUSH, "",
                            {"idempotencyKey": idempotencyKey, "retryOfFailed": "1" if retryOfFailed else "0"},
                            startTime, ipAddr, source)

    #5) 自动发布闸门(推送≠发布; 默认关闭, 不满足即显式拒绝, 不先投草稿)
    autoPublishAllowed, autoPublishErr = checkAutoPublishGate(dataSet, platformRecord, accountRecord)
    if autoPublishErr is not None:
        return _failAudited(autoPublishErr, actor, AUDIT_ACTION_PUSH, idempotencyKey, dataSet,
                            startTime, ipAddr, source)

    auditPayload = {"idempotencyKey": idempotencyKey, "platform": platformCode,
                    "topicID": topicID, "layoutCode": layoutCode, "artifactID": artifactID,
                    "accountID": accountID, "credentialSource": credential.get("source"),
                    "autoPublish": "1" if autoPublishAllowed else "0",
                    "retryOfFailed": "1" if retryOfFailed else "0"}

    #6) 合规闸门(★ 投递前必须过校验; 复用 SP3c 的 publishCheck)
    complianceRtn = complianceService.publishCheck(
        {"topicID": topicID, "platform": platformCode, "layoutCode": layoutCode,
         "accountID": accountID, "ownerID": _toStr(sessionIDSet.get("loginID"))},
        sessionIDSet = sessionIDSet)
    if not isinstance(complianceRtn, dict):
        complianceRtn = {}
    if complianceRtn.get("errCode") != ERR_OK:
        return _failAudited(_err(complianceRtn.get("errCode", ERR_FIELD_INVALID),
                                 complianceRtn.get("field") or _fieldLabel("compliance"),
                                 complianceRtn.get("errMsgList"),
                                 {"compliance": complianceRtn.get("data") or {}, "idempotencyKey": idempotencyKey}),
                            actor, AUDIT_ACTION_PUSH, idempotencyKey, auditPayload,
                            startTime, ipAddr, source, memo = "compliance blocked")

    #7) 取数: 主题 + 附图 + 版式
    topicRecord, topicErr = renderService._fetchTopic({"recID": topicID})
    if topicErr is not None:
        return _failAudited(topicErr, actor, AUDIT_ACTION_PUSH, idempotencyKey, auditPayload,
                            startTime, ipAddr, source)

    assetList, assetErr = renderService._fetchAssets(topicID)
    if assetErr is not None:
        _logWarn(f"附图查询失败(降级为空) topicID:{topicID}, errMsg:{assetErr.get('errMsgList')}")
        assetList = []
    else:
        assetList = renderService._mergeAssetMeta(assetList)

    try:
        layoutRecord = layoutEngine.loadLayoutRecord(layoutCode)
    except layoutEngine.LayoutEngineError as e:
        return _failAudited(_err(e.errCode, e.field or _fieldLabel("layoutCode"), [e.message]),
                            actor, AUDIT_ACTION_PUSH, idempotencyKey, auditPayload,
                            startTime, ipAddr, source)

    #8) access_token(获取 + 缓存 + 提前刷新)
    accessToken, tokenErr = getAccessToken(credential.get("appID"), credential.get("appSecret"), adapter)
    if tokenErr is not None:
        markAccountHealth(accountID, "INVALID")
        return _failAudited(tokenErr, actor, AUDIT_ACTION_PUSH, idempotencyKey, auditPayload,
                            startTime, ipAddr, source, memo = "access_token failed")

    #9) 渲染平台形态产物(注入转存通道 -> 外链图片真实转存为 mmbiz.qpic.cn)
    buildTransfer = getattr(adapter, "buildTransferFunc", None)
    transferFunc = buildTransfer(accessToken) if buildTransfer else None
    options = {"transferFunc": transferFunc, "timeout": dataSet.get("timeoutMs")}
    overrideSpec = renderService._resolveOverrideSpec(dataSet)

    renderRtn = adapter.render(topicRecord, layoutRecord, assetList, overrideSpec, options)
    if not isinstance(renderRtn, dict):
        renderRtn = {}
    if renderRtn.get("errCode") != ERR_OK:
        return _failAudited(_err(renderRtn.get("errCode", ERR_FIELD_INVALID),
                                 renderRtn.get("field") or _fieldLabel("render"),
                                 renderRtn.get("errMsgList"),
                                 {"idempotencyKey": idempotencyKey}),
                            actor, AUDIT_ACTION_PUSH, idempotencyKey, auditPayload,
                            startTime, ipAddr, source, memo = "render failed")
    renderData = renderRtn.get("data") or {}

    packageRtn = adapter.package(renderData, topicRecord, assetList, options)
    if not isinstance(packageRtn, dict):
        packageRtn = {}
    if packageRtn.get("errCode") != ERR_OK:
        return _failAudited(_err(packageRtn.get("errCode", ERR_FIELD_INVALID),
                                 packageRtn.get("field") or _fieldLabel("package"),
                                 packageRtn.get("errMsgList"), {"idempotencyKey": idempotencyKey}),
                            actor, AUDIT_ACTION_PUSH, idempotencyKey, auditPayload,
                            startTime, ipAddr, source, memo = "package failed")

    #10) 通道投递(草稿)
    deliverRtn = adapter.deliver(packageRtn, {"accessToken": accessToken, "timeout": dataSet.get("timeoutMs"),
                                              "transferFunc": transferFunc})
    if not isinstance(deliverRtn, dict):
        deliverRtn = {}
    deliverData = deliverRtn.get("data") or {}
    remoteID = _toStr(deliverData.get("remoteID"))

    if deliverRtn.get("errCode") != ERR_OK:
        #失败也全字段落库 + 审计 FAIL(失败原因可读回显)
        saveSet = buildPublishSaveSet(idempotencyKey, artifactID, topicID, accountID, platformCode,
                                      deliverMode, auditPayload,
                                      {"errcode": deliverData.get("errcode"),
                                       "errmsg": deliverData.get("errmsg"),
                                       "deliverErrCode": deliverRtn.get("errCode")},
                                      deliverData.get("errcode") or 0,
                                      ";".join(deliverRtn.get("errMsgList") or []) or _toStr(deliverRtn.get("errCode")),
                                      PUBLISH_SUCCESS_NO, remoteID, actor,
                                      autoPublishFlag = "1" if autoPublishAllowed else "0",
                                      memo = "deliver failed")
        recordID = savePublishRecord(idempotencyKey, saveSet)
        deliverRtn.setdefault("data", {})
        deliverRtn["data"].update({"publishRecordID": _toInt(recordID, 0), "idempotencyKey": idempotencyKey,
                                   "recordWritten": "1" if recordID else "0"})
        return _failAudited(deliverRtn, actor, AUDIT_ACTION_PUSH, _toStr(recordID) or idempotencyKey,
                            auditPayload, startTime, ipAddr, source, memo = "deliver rejected")

    #11) 正式发布(仅在人工二次确认 + 三重闸门通过时; 默认不会走到)
    autoPublishFlag = "0"
    publishID = ""
    if autoPublishAllowed:
        submitExtra = {"errcode": 0, "errmsg": "ok", "deliverErrCode": ""}
        submitRtn = adapter.submitFreePublish(accessToken, remoteID, timeout = dataSet.get("timeoutMs"))
        if not isinstance(submitRtn, dict):
            submitRtn = {}
        if submitRtn.get("errCode") != ERR_OK:
            saveSet = buildPublishSaveSet(idempotencyKey, artifactID, topicID, accountID, platformCode,
                                          deliverMode, auditPayload,
                                          {"draftRemoteID": remoteID, "publishErrCode": submitRtn.get("errCode"),
                                           "publishErrMsg": submitRtn.get("errMsgList")},
                                          submitRtn.get("errcode", 0),
                                          ";".join(submitRtn.get("errMsgList") or []),
                                          PUBLISH_SUCCESS_NO, remoteID, actor,
                                          autoPublishFlag = "1", memo = "freepublish failed(draft created)")
            recordID = savePublishRecord(idempotencyKey, saveSet)
            submitRtn.setdefault("data", {})
            submitRtn["data"].update({"publishRecordID": _toInt(recordID, 0), "draftRemoteID": remoteID,
                                      "idempotencyKey": idempotencyKey,
                                      "message": "草稿已投递但正式发布失败(须人工在后台确认)"})
            return _failAudited(submitRtn, actor, AUDIT_ACTION_PUSH, _toStr(recordID) or idempotencyKey,
                                auditPayload, startTime, ipAddr, source, memo = "freepublish failed")
        autoPublishFlag = "1"
        publishID = _toStr((submitRtn.get("data") or {}).get("publishID"))
        submitExtra.update({"errcode": 0, "errmsg": "ok", "publishID": publishID})
    else:
        submitExtra = {"errcode": deliverData.get("errcode"), "errmsg": deliverData.get("errmsg"),
                       "deliverErrCode": ""}

    #12) 成功落库 + 审计 OK
    saveSet = buildPublishSaveSet(idempotencyKey, artifactID, topicID, accountID, platformCode,
                                  deliverMode, auditPayload, submitExtra,
                                  deliverData.get("errcode") or 0, "", PUBLISH_SUCCESS_YES,
                                  remoteID, actor, autoPublishFlag = autoPublishFlag,
                                  memo = "draft delivered")
    recordID = savePublishRecord(idempotencyKey, saveSet)
    markAccountHealth(accountID, credential.get("healthStatus") or "OK", lastCheck = True, lastUse = True)

    costMs = int((time.time() - startTime) * 1000)
    auditID = _writeAudit(actor, AUDIT_ACTION_PUSH, _toStr(recordID) or idempotencyKey, auditPayload,
                          auditService.RESULT_OK, "", costMs, ipAddr, source,
                          memo = f"remoteID={remoteID}, autoPublish={autoPublishFlag}")

    return _ok({
        "idempotencyKey": idempotencyKey,
        "publishRecordID": _toInt(recordID, 0),
        "recordWritten": "1" if recordID else "0",
        "retryOfFailed": "1" if retryOfFailed else "0",
        "auditWritten": "1" if auditID else "0",
        "platform": platformCode,
        "deliverMode": deliverMode,
        "artifactID": artifactID,
        "topicID": _toInt(topicID, 0),
        "accountID": accountID,
        "remoteID": remoteID,
        "success": PUBLISH_SUCCESS_YES,
        "pushedYMDHMS": saveSet.get("pushedYMDHMS"),
        "autoPublish": autoPublishFlag,
        "publishID": publishID,
        "transferredImageCount": _toInt(deliverData.get("transferredImageCount"), 0),
        "compliance": {"passed": "1"},
        "costMs": costMs,
        "note": "草稿已投递(推送≠发布); 最终群发须人工在公众号后台完成",
    })

#===== 业务入口: 投递 end =====


#===== 业务入口: 撤销(撤销窗内) begin =====

def revokePublish(dataSet, sessionIDSet = None):
    """★ 撤销(publishpush 的 action=revoke): 仅撤销窗(默认 60s)内、且投递成功、且未撤销过。
        - 逾窗 -> F5 显式拒绝; 未成功投递 -> C7; 已撤销 -> F1(幂等命中);
        - 撤销动作: 发布记录 delFlag="1"(软删除语义) + 审计留痕(不依赖 Redis)。"""
    startTime = time.time()
    dataSet = dataSet if isinstance(dataSet, dict) else {}
    sessionIDSet = sessionIDSet if isinstance(sessionIDSet, dict) else {}
    actor = _toStr(sessionIDSet.get("loginID")) or _toStr(dataSet.get("operator")) or "anonymous"
    ipAddr = _toStr(dataSet.get("_IP"))
    source = _toStr(dataSet.get("source")).lower() or auditService.SOURCE_WEB

    idempotencyKey = _toStr(dataSet.get("idempotencyKey"))
    publishRecordID = _toInt(dataSet.get("publishRecordID"), 0)
    if not idempotencyKey and publishRecordID <= 0:
        return _failAudited(_err(ERR_FIELD_MISSING, _fieldLabel("publishRecordID"),
                                 ["撤销需提供 publishRecordID 或 idempotencyKey"]),
                            actor, AUDIT_ACTION_REVOKE, "", dataSet, startTime, ipAddr, source)

    #★ delFlag="": 必须能看到已撤销记录, 否则「已撤销 -> F1 幂等命中」分支不可达(会误报 CB 无此记录)
    record = queryPublishRecord(idempotencyKey = idempotencyKey, recID = publishRecordID, delFlag = "")
    if not record:
        return _failAudited(_err(ERR_NO_RECORD, _fieldLabel("publishRecordID"),
                                 [f"无此发布记录: publishRecordID={publishRecordID}, "
                                  f"idempotencyKey={idempotencyKey or '(空)'}"]),
                            actor, AUDIT_ACTION_REVOKE, _toStr(publishRecordID), dataSet,
                            startTime, ipAddr, source)

    publishRecordID = _toInt(record.get("recID"), publishRecordID)
    targetPayload = {"publishRecordID": publishRecordID,
                     "idempotencyKey": _toStr(record.get("idempotencyKey"))}

    if _toStr(record.get("delFlag")) == PUBLISH_DELFLAG_REVOKED:
        return _failAudited(_err(ERR_IDEMPOTENT, _fieldLabel("publishRecordID"),
                                 ["该发布记录已撤销(幂等命中)"],
                                 {"publishRecordID": publishRecordID, "revoked": "1"}),
                            actor, AUDIT_ACTION_REVOKE, _toStr(publishRecordID), targetPayload,
                            startTime, ipAddr, source)

    if _toStr(record.get("success")) != PUBLISH_SUCCESS_YES:
        return _failAudited(_err(ERR_FIELD_INVALID, _fieldLabel("success"),
                                 [f"该发布记录未成功投递(success={_toStr(record.get('success')) or '0'}), 不可撤销"]),
                            actor, AUDIT_ACTION_REVOKE, _toStr(publishRecordID), targetPayload,
                            startTime, ipAddr, source)

    allowed, elapsed, reason = checkRevokeWindow(record)
    if not allowed:
        return _failAudited(_err(ERR_REVOKE_WINDOW, _fieldLabel("pushedYMDHMS"),
                                 [f"撤销被拒: {reason}(撤销窗 {REVOKE_WINDOW_SECONDS}s)"],
                                 {"publishRecordID": publishRecordID, "elapsedSeconds": elapsed,
                                  "windowSeconds": REVOKE_WINDOW_SECONDS}),
                            actor, AUDIT_ACTION_REVOKE, _toStr(publishRecordID), targetPayload,
                            startTime, ipAddr, source, memo = "revoke window expired")

    tableName = comMysql.tablename_convertor_ch_publish_record()
    try:
        comMysql.update_ch_publish_record(tableName, publishRecordID, {
            "delFlag": PUBLISH_DELFLAG_REVOKED,
            "modifyID": actor,
            "modifyYMDHMS": _nowYMDHMS(),
            "memo": f"revoked_at={_nowYMDHMS()}, elapsed={elapsed}s"[:200],
        })
    except Exception as e:
        return _failAudited(_err(ERR_DB_FAILED, _fieldLabel("publishRecordID"),
                                 [f"撤销写库失败: {str(e)}"]),
                            actor, AUDIT_ACTION_REVOKE, _toStr(publishRecordID), targetPayload,
                            startTime, ipAddr, source)

    costMs = int((time.time() - startTime) * 1000)
    auditID = _writeAudit(actor, AUDIT_ACTION_REVOKE, _toStr(publishRecordID), targetPayload,
                          auditService.RESULT_OK, "", costMs, ipAddr, source,
                          memo = f"revoked within {REVOKE_WINDOW_SECONDS}s window")
    return _ok({
        "publishRecordID": publishRecordID,
        "idempotencyKey": _toStr(record.get("idempotencyKey")),
        "revoked": "1",
        "elapsedSeconds": elapsed,
        "windowSeconds": REVOKE_WINDOW_SECONDS,
        "remoteID": _toStr(record.get("remoteID")),
        "auditWritten": "1" if auditID else "0",
        "costMs": costMs,
        "note": "已撤销(本地发布记录置 delFlag=1); 平台侧草稿如需删除请人工在后台处理",
    })

#===== 业务入口: 撤销 end =====


if __name__ == "__main__":
    pass
    #本地自测(不连库/不联网): 只验证纯函数
    print("idempotencyKey:", buildIdempotencyKey(12, 34, nonce = "abc"))
    print("isValid:", isValidIdempotencyKey("12:34:abc"), isValidIdempotencyKey("bad"))
    _key = buildIdempotencyKey(12, 34)
    print("confirmToken:", buildConfirmToken(_key))
    print("confirm(missing):", (checkConfirmParams({}, _key) or {}).get("errCode"))
    print("confirm(ok):", checkConfirmParams({CONFIRM_FLAG_KEY: "1", CONFIRM_TOKEN_KEY: buildConfirmToken(_key)}, _key))
    print("nonDeliverable:", NON_DELIVERABLE_PLATFORM_LIST, "deliverable:", DELIVERABLE_PLATFORM_LIST)
    print("revokeWindowSeconds:", REVOKE_WINDOW_SECONDS, "autoPublishEnabled:", AUTO_PUBLISH_ENABLED)
