#! /usr/bin/env python3
#encoding: utf-8

#Filename: apiCommon.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub 接入层 HTTP 公共件(见 plan/chAPIPost分拆方案.md 3.1 / 4.2 / 6.3)。
#
#★ 零业务约束(强制): 本文件只允许出现「与业务域无关」的入参处理、返回封装、异常兜底、
#  分页入参、会话上下文抽取。任何领域判断(角色/表/状态/合规规则)一律不得写入本文件 —— 这是
#  防止 apiCommon 演化为第二个巨型文件的关键约束(方案 6.3)。
#  ☆ 显式豁免(见 plan/出参信封统一改造.md): normalizeEnvelope 属上列「返回封装」职责, 其唯一
#    域输入是 subfunc.CMD_OWNER 的路由标签(account / crud / topic / ...), 不含角色/表/状态/
#    合规等业务规则, 故不违反本约束。
#
#本文件承载(基线 museumAPIPost.py 的对应段落):
#  - dataFormatConvertor / dataTrustDomainCheck / uploadContentCheck  (L11552-11622)
#  - genRtnResult / genErrResult                                     (museumCommon.py L1041/L1055)
#  - genSessionContext / genIndexKeyDataSet / packQueryData / getQueryBeginEndNum (museumCommon.py)
#  - setSourceServerAddr                                             (museumCommon.py L1088)
#  - 占位端点统一返回(C2) / 默认消息键(DEFAULT_MSG_KEY)

_VERSION="20260918"


import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import traceback

from subfunc import context as ctx

from common import globalDefinition as comGD

from common import funcCommon as comFC

from common import miscCommon as misc

from common import errMsgCommon as comErr


_processorPID = ctx._processorPID
_LOG = ctx._LOG
_DEBUG = ctx._DEBUG

#contentHub 命令处理器的默认消息键(决策 12.6: 与 museum 的 applicationMsgKey 解耦)
DEFAULT_MSG_KEY = comErr.DEFAULT_MSG_KEY

#占位端点专用错误码(C 段: 已登记但尚未实现的端点, 见 common/errMsgCommon.py 错误码规划)
_ERR_NOT_IMPLEMENTED = "C2"


#===== 出参信封整形(全仓唯一改造点, 见 plan/出参信封统一改造.md) begin =====

#恒留信封顶层的账本键: 不参与业务字段归集, 也绝不进入 data
ENVELOPE_KEY_SET = {"CMD", "msgKey", "MSG", "errCode", "SN", "YMDHMS"}

#查询类端点清单(显式可审计): 出参维持「data 为数组 + total/beginNum/endNum/indexKey 在信封顶层」不变。
#★ 必须用显式清单而非结构启发式 —— topicversionqry 的「单条快照」分支 data 为**对象**
#  (仅含 data/total, 无 indexKey), 用「data 是否为数组 / 是否含 indexKey」判定会误判并二次嵌套。
QUERY_CMD_LIST = [
    "usersearch", "generalnext",
    "topicqry", "topicversionqry", "assetqry", "topicassetqry",
    "layoutqry", "platformqry", "renderjobqry", "artifactqry",
    "accountqry", "publishrecordqry", "mcptokenqry", "auditlogqry",
]

#account 域标签(取自 subfunc.CMD_OWNER): 该域走「顶层保持不变 + 复制一份到 data」的双写策略
ACCOUNT_OWNER = "account"

#===== 出参信封整形 end =====


#===== 入参处理 begin =====

def dataFormatConvertor(dataType, dataSet):
    """FORM 型入参转换: 把 formData 子字典提升到顶层(基线逻辑原样保留)"""
    result = dataSet
    if dataType == "FORM":
        formData = dataSet.get("formData", {})
        for k, v in formData.items():
            result[k] = v
        result.pop("formData")
    return result


def dataTrustDomainCheck(dataSet):
    """信任域名检查: 返参 (validDataFlag, result)。
       说明: 与基线一致, 该检查默认不启用(post() 中以开关形式保留落点)。"""
    validDataFlag = True
    result = {}
    for key, val in dataSet.items():
        if isinstance(val, list):
            for v in val:
                if not comFC.chkTrustDomain(v):
                    validDataFlag = False
                    break
        elif isinstance(val, dict):
            for k, v in val.items():
                if not comFC.chkTrustDomain(v):
                    validDataFlag = False
                    break
            result[key] = val
        else:
            if not comFC.chkTrustDomain(val):
                validDataFlag = False
                break
        if validDataFlag:
            result[key] = val
        else:
            if _LOG:
                _LOG.warning(f"W:not trust domain data,{key},{val}")
    return validDataFlag, result


def uploadContentCheck(dataSet):
    """上传内容合规检查: 返回错误码("B0" 通过 / "EL" 不通过)。
       说明: 与基线一致, 该检查默认不启用(post() 中以开关形式保留落点)。"""
    errCode = "B0"
    if isinstance(dataSet, list):
        for val in dataSet:
            if not comFC.uploadContentCheck(val):
                errCode = "EL"
                if _LOG:
                    _LOG.warning(f"W:upload content error,{val}")
                break
    elif isinstance(dataSet, dict):
        for key, val in dataSet.items():
            if isinstance(val, list):
                for v in val:
                    if not comFC.uploadContentCheck(v):
                        errCode = "EL"
                        if _LOG:
                            _LOG.warning(f"W:upload content error,{v}")
                        break
            elif isinstance(val, dict):
                for k, v in val.items():
                    if not comFC.uploadContentCheck(v):
                        errCode = "EL"
                        if _LOG:
                            _LOG.warning(f"W:upload content error,{v}")
                        break
            else:
                if not comFC.uploadContentCheck(val):
                    errCode = "EL"
                    if _LOG:
                        _LOG.warning(f"W:upload content error,{val}")
    else:
        if not comFC.uploadContentCheck(dataSet):
            errCode = "EL"
            if _LOG:
                _LOG.warning(f"W:upload content error,{dataSet}")

    return errCode

#===== 入参处理 end =====


#===== 返回报文封装 begin =====

def genLang(dataSet):
    """取请求语言(缺省 CN, 与基线一致)"""
    lang = comGD._DEF_DEFAULT_LANGUAGE
    if isinstance(dataSet, dict):
        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
    return lang


def genSessionContext(dataSet, sessionIDSet):
    """抽取命令处理器的公共会话上下文(各 funcXxx 处理器开头统一使用)"""
    context = {}
    context["lang"] = genLang(dataSet)
    context["msgKey"] = DEFAULT_MSG_KEY
    context["openID"] = sessionIDSet.get("openID", "")
    context["roleName"] = sessionIDSet.get("roleName", "")
    context["loginID"] = sessionIDSet.get("loginID", "")
    context["sessionID"] = sessionIDSet.get("sessionID", "")
    return context


def genRtnResult(CMD, errCode = "B0", rtnField = "", lang = comGD._DEF_DEFAULT_LANGUAGE,
                 msgKey = DEFAULT_MSG_KEY, rtnErrMsgList = None, rtnData = None):
    """抽取命令处理器的返回报文封装(各 funcXxx 处理器结尾统一使用)。
       出参结构与基线完全一致: 业务字段 + CMD + msgKey + MSG + errCode,
       其中 MSG.content 追加逐条数据校验原因(rtnErrMsgList)。"""
    result = {}

    if rtnErrMsgList is None:
        rtnErrMsgList = []
    if rtnData is None:
        rtnData = {}

    rtnSet = comFC.rtnMSG(errCode, rtnField, lang, msgKey)

    result.update(rtnData)
    result["CMD"] = CMD
    result["msgKey"] = msgKey
    result["MSG"] = rtnSet["MSG"]
    result["errCode"] = errCode
    result["MSG"]["content"] += ";" + ";".join(rtnErrMsgList)

    return result


def genErrResult(CMD, e):
    """抽取命令处理器的统一异常返回(记日志 + ERR_GENERAL 报文)"""
    errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
    if _LOG:
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

    result = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")

    return result


def genNotImplementedResult(CMD, dataSet = None, sessionIDSet = None):
    """占位端点统一返回(C2)。SP1.5 已登记但尚未实现的端点使用, 保证「可受理、不 404、不静默」。"""
    lang = genLang(dataSet)
    result = genRtnResult(CMD, errCode = _ERR_NOT_IMPLEMENTED, rtnField = _ERR_NOT_IMPLEMENTED,
                          lang = lang, msgKey = DEFAULT_MSG_KEY)
    return result


def normalizeEnvelope(aResult, owner = "", cmd = ""):
    """出参信封整形(见 plan/出参信封统一改造.md; 由 main/chAPIPost.py::post() 出口唯一调用)。

    三态规则:
      keep —— owner 为空(CMD 未注册 / 框架级返回)或查询类端点: 原样返回;
      copy —— owner == ACCOUNT_OWNER: **顶层业务字段一律保持不变**, 额外补
              data = 顶层业务字段副本(排除信封键); 顶层已有 data 时不覆盖;
      move —— 其余 ch_* 域(非查询类): 业务字段整体迁入 data; 原先自带的 data 子键
              随之成为新 data 内的子键(机械迁移, 语义零改动)。

    出参:
      dict —— 整形后的新字典(move 分支不修改入参对象); keep/copy 分支返回入参本身。

    ★ 本函数是纯数据整形, 只依据 CMD_OWNER 的路由标签分域, 不含任何角色/表/状态/合规业务规则,
      属本文件「返回报文封装」职责(零业务约束的显式豁免项)。
    ★ 异常绝不外抛: 整形失败仅记一条 warning 并原样返回, 保证可用性不受影响。
    """
    if not isinstance(aResult, dict) or not owner:
        return aResult

    try:
        #业务字段 = 除信封账本键以外的全部顶层键
        businessKeyList = [key for key in aResult.keys() if key not in ENVELOPE_KEY_SET]

        if owner == ACCOUNT_OWNER:
            #copy: 顶层不动, 仅额外补一份副本(已有 data 则保持原样, 不覆盖下游语义)
            if "data" in aResult:
                return aResult
            aResult["data"] = {key: aResult.get(key) for key in businessKeyList}
            return aResult

        #move: 幂等保护 —— 非信封键仅剩 data, 说明已完成整形
        if len(businessKeyList) == 1 and businessKeyList[0] == "data":
            return aResult

        newResult = {}
        for key in aResult.keys():
            if key in ENVELOPE_KEY_SET:
                newResult[key] = aResult.get(key)
        newResult["data"] = {key: aResult.get(key) for key in businessKeyList}

        return newResult
    except Exception as e:
        if _LOG:
            _LOG.warning(f"W: PID:{_processorPID},CMD:{cmd}, normalizeEnvelope failed, errMsg:{str(e)}")
        return aResult

#===== 返回报文封装 end =====


#===== 分页与来源地址 begin =====

def genIndexKeyDataSet(dataSet, keyNameList):
    """按字段清单从请求数据中抽取生成 indexKey 的因素(仅取有值项)"""
    indexKeyDataSet = {}
    for keyName in keyNameList:
        val = dataSet.get(keyName)
        if val:
            indexKeyDataSet[keyName] = val
    return indexKeyDataSet


def packQueryData(currDataSet, fieldNameList):
    """按字段清单从一条记录中抽取需要返回的数据"""
    aSet = {}
    for fieldName in fieldNameList:
        aSet[fieldName] = currDataSet.get(fieldName, "")
    return aSet


def getQueryBeginEndNum(dataSet):
    """取查询的起止序号(缺省使用全局缓冲区间的默认值)"""
    try:
        beginNum = int(dataSet.get("beginNum", comGD._DEF_BUFFER_DATA_BEGIN_NUM))
    except Exception:
        beginNum = comGD._DEF_BUFFER_DATA_BEGIN_NUM
    try:
        endNum = int(dataSet.get("endNum", comGD._DEF_BUFFER_DATA_END_NUM))
    except Exception:
        endNum = comGD._DEF_BUFFER_DATA_END_NUM
    return beginNum, endNum


def setSourceServerAddr(envSet):
    """从请求头环境解析来源服务器地址(文件转存时使用), 写回 context 单例并返回。"""
    _x_server_addr = envSet.get("_x_server_addr", "")
    _x_server_port = envSet.get("_x_server_port", "")
    _x_protocol_used = envSet.get("_x_protocol_used", "")

    if _x_server_addr and _x_server_port and _x_protocol_used:
        sourceServerAddr = _x_protocol_used + "://" + _x_server_addr + ":" + _x_server_port
    else:
        sourceServerAddr = ""

    ctx.gSourceServerAddr = sourceServerAddr

    return sourceServerAddr

#===== 分页与来源地址 end =====


if __name__ == "__main__":
    pass
    print("DEFAULT_MSG_KEY", DEFAULT_MSG_KEY)
    print("sample rtn", genRtnResult("login", "B8", "B8", "CN"))
    print("sample not implemented", genNotImplementedResult("topicrender", {}, {}))
    print("QUERY_CMD_LIST", QUERY_CMD_LIST)

    #出参信封整形自检(平铺入参 -> 整形后); 入参一律先浅拷贝, 避免污染样例
    sampleFlat = genRtnResult("topicadd", "B0", "B0", "CN", rtnData = {"recID": "7"})
    print("copy(account)         ", normalizeEnvelope(dict(sampleFlat), ACCOUNT_OWNER, "accounthealth"))
    print("move(ch_*)            ", normalizeEnvelope(dict(sampleFlat), "topic", "topicadd"))
    print("keep(owner 为空)      ", normalizeEnvelope(dict(sampleFlat), "", "ERR_NOCMD"))
    print("move(无业务字段)      ", normalizeEnvelope(genNotImplementedResult("topicrender", {}, {}),
                                                     "render", "topicrender"))
    print("move(原有 data 子键)  ", normalizeEnvelope(
        genRtnResult("assetadd", "B0", "B0", "CN",
                     rtnData = {"recID": "9", "dedupHit": "0", "data": {"recID": "9"}}),
        "asset", "assetadd"))
    print("move(幂等)            ", normalizeEnvelope(
        normalizeEnvelope(dict(sampleFlat), "topic", "topicadd"), "topic", "topicadd"))
