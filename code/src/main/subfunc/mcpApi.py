#! /usr/bin/env python3
#encoding: utf-8

#Filename: mcpApi.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub /chapi 侧的 MCP 薄入口(见 plan/chAPIPost分拆方案.md 3.1 / 6.4)。
#
#职责收窄(重要): MCP 协议层与工具实现已独立为 code/src/mcpapi/ 包(mcp_entry.py + mcpPost.py),
#  本文件只承载 /chapi 侧的 mcpinvoke **薄入口**(常规 REST 形态的 MCP 只读能力入口):
#    token 校验(G0/G1) -> 工具级授权(MCP_TOOL_LIST) -> toolName 路由 -> 经
#    common/chServerCommon.py 转发到下游 /chapi 的既有只读查询命令。
#  ★ 不得在本文件重复实现 MCP 工具注册表与协议解析(无 jsonrpc / tools/call / FastMCP 等);
#  ★ 不得改动 mcpapi/* 的任何既有逻辑(该包为独立只读层, 由 mcp_entry.py 自行对 MCP 客户端提供协议服务)。
#
#★ 鉴权: 沿用 Redis session(comDB.getSessionInfo) + ROLE_CMD_LIST, 并支持可选 MCP_TOOL_LIST 工具级授权;
#  与 mcpapi/mcpPost.py::CHTokenVerifier 同一套口径(角色 -> 放行; 工具级清单非空时按清单裁剪)。
#  token 取「请求 dataSet.token/sessionID」或「会话上下文 sessionIDSet」(二者取其一即可)。
#
#★ 错误码(G 段, 见 common/errMsgCommon.py): G0 令牌无效/角色非法 | G1 工具权限不足 |
#  G2 未知工具 | G3 下游调用失败。成功统一 B0(下游 errCode 原样回显在 data.downstream 内)。
#
#★ 分层契约: 本文件属接入层, 只做「鉴权 + 路由 + 报文封装」; 转发下游一律经
#  common/chServerCommon.py(访问 /chapi 的唯一数据入口), **不承载任何业务计算**。

_VERSION="20260919"


import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import traceback

from subfunc import apiCommon

#Redis 唯一入口(红线: 只经 common/redisCommon.py; 本文件不直连)
from common import redisCommon as comDB

#访问 /chapi 的唯一数据入口(MCP 侧 REST 客户端; 本文件只做转发)
from common import chServerCommon as comCh

from config import basicSettings as settings

from config import mcpConfig


#===== 错误码与常量 begin =====

ERR_OK = "B0"
ERR_TOKEN_INVALID = "G0"        #令牌无效/会话不存在/角色非法
ERR_TOOL_FORBIDDEN = "G1"       #工具权限不足(MCP_TOOL_LIST 工具级授权)
ERR_TOOL_UNKNOWN = "G2"         #未知工具
ERR_DOWNSTREAM = "G3"           #下游 /chapi 调用失败

#★ MCP 只读工具 -> 下游 /chapi 命令(路由表; 与 mcpapi/mcpPost.py::toolPathMap 的只读范围一致)。
#  说明: 这是「数据路由」而非协议解析 —— 本文件不解析 MCP JSON-RPC, 只按工具名转发既有 REST 命令。
TOOL_CMD_MAP = {
    "search_topics": "topicqry",
    "get_topic": "topicqry",
    "list_topic_assets": "topicassetqry",
    "list_layouts": "layoutqry",
    "list_platforms": "platformqry",
    "get_render_job": "renderjobqry",
    "list_artifacts": "artifactqry",
    "list_publish_records": "publishrecordqry",
}

#工具入参键 -> 下游命令入参键(仅在两侧命名不一致时登记; 其余同名透传)
TOOL_PARAM_KEY_MAP = {
    "topic_code": "topicCode",
    "topic_id": "recID",
    "category_code": "categoryCode",
    "publish_status": "publishStatus",
    "owner_id": "ownerID",
    "layout_type": "layoutType",
    "layout_code": "layoutCode",
    "platform_code": "platformCode",
    "job_code": "jobCode",
    "job_status": "jobStatus",
    "job_id": "jobID",
    "artifact_id": "artifactID",
    "artifact_status": "artifactStatus",
    "usage_type": "usageType",
    "file_id": "fileID",
}

#内部/鉴权字段(不向下游透传)
_INTERNAL_KEY_LIST = ["token", "sessionID", "toolName", "tool", "params", "args", "dataSet", "lang"]

#===== 错误码与常量 end =====


#===== 通用小工具 begin =====

def _toStr(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _normalizeParams(dataSet):
    """取工具入参: params/args/dataSet 子字典优先, 其余键透传; 清理空值与内部字段"""
    rawSet = {}
    for key in ("params", "args", "dataSet"):
        value = dataSet.get(key)
        if isinstance(value, dict):
            rawSet.update(value)
    for key, value in dataSet.items():
        if key in ("params", "args", "dataSet"):
            continue
        if key not in rawSet:
            rawSet[key] = value

    params = {}
    for key, value in rawSet.items():
        if key in _INTERNAL_KEY_LIST or key.startswith("_"):
            continue
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        params[TOOL_PARAM_KEY_MAP.get(key, key)] = value
    return params


def _resolveIdentity(dataSet, sessionIDSet):
    """解析调用者身份: 优先 Redis session(经 token), 回落接入层已校验的会话上下文。
       出参: (token, roleName, loginID, source)。"""
    token = (_toStr(dataSet.get("token")) or _toStr(dataSet.get("sessionID"))
             or _toStr(sessionIDSet.get("sessionID")) or _toStr(sessionIDSet.get("token")))
    roleName = _toStr(sessionIDSet.get("roleName"))
    loginID = _toStr(sessionIDSet.get("loginID"))
    source = "session"

    if token:
        try:
            #Redis 会话(与 mcpapi/mcpPost.py 的鉴权数据源一致)
            sessionInfo = comDB.getSessionInfo(token) or {}
            if sessionInfo:
                roleName = _toStr(sessionInfo.get("roleName")) or roleName
                loginID = _toStr(sessionInfo.get("loginID")) or loginID
                source = "redis"
        except Exception as e:
            #Redis 不可用时回落接入层会话(不阻断、不静默改权限判定口径)
            _logWarn(f"mcpinvoke Redis 会话读取失败(回落接入层会话) token:{token[:12]}..., errMsg:{e}")
    return token, roleName, loginID, source


def _allowedToolList(roleName):
    """角色级工具清单(空 = 不限制, 与 mcpapi/mcpPost.py::_genAllowedTools 同口径)"""
    try:
        toolListData = getattr(settings, "MCP_TOOL_LIST", {}) or {}
        return [_toStr(item) for item in toolListData.get(roleName, []) if _toStr(item)]
    except Exception as e:
        _logError(f"读取 MCP_TOOL_LIST 失败 roleName:{roleName}, errMsg:{e}")
        return []


def _logWarn(message):
    if apiCommon._LOG:
        apiCommon._LOG.warning(f"W: PID:{apiCommon._processorPID}, {message}")


def _logError(message):
    if apiCommon._LOG:
        apiCommon._LOG.error(f"PID:{apiCommon._processorPID}, {message}")


def _errResult(CMD, errCode, lang, errMsgList):
    return apiCommon.genRtnResult(CMD, errCode = errCode, rtnField = errCode, lang = lang,
                                  msgKey = apiCommon.DEFAULT_MSG_KEY, rtnErrMsgList = errMsgList)

#===== 通用小工具 end =====


#MCP 薄入口(mcpinvoke): token 校验 -> 工具级授权 -> 路由 -> 经 chServerCommon 转发下游 /chapi
def funcMcpInvoke(CMD, dataSet, sessionIDSet):
    result = {}
    try:
        if not isinstance(dataSet, dict):
            dataSet = {}
        sessionIDSet = sessionIDSet if isinstance(sessionIDSet, dict) else {}
        lang = apiCommon.genLang(dataSet)

        #1) 工具名(兼容 toolName / tool)
        toolName = _toStr(dataSet.get("toolName")) or _toStr(dataSet.get("tool"))
        if not toolName:
            return _errResult(CMD, ERR_TOOL_UNKNOWN, lang, ["缺少 toolName(或 tool)参数"])

        #2) 令牌与会话(G0: 无 token 且无有效会话角色)
        token, roleName, loginID, identitySource = _resolveIdentity(dataSet, sessionIDSet)
        if not roleName:
            return _errResult(CMD, ERR_TOKEN_INVALID, lang,
                              [f"令牌无效或会话不存在(identitySource={identitySource})"])
        if roleName not in settings.ROLE_CMD_LIST:
            return _errResult(CMD, ERR_TOKEN_INVALID, lang,
                              [f"角色无权访问: roleName={roleName}"])

        #3) 工具级授权(G1): MCP_TOOL_LIST 未配置该角色 -> 清单为空 -> 不限制(与 MCP 层一致)
        allowedToolList = _allowedToolList(roleName)
        if allowedToolList and toolName not in allowedToolList:
            return _errResult(CMD, ERR_TOOL_FORBIDDEN, lang,
                              [f"工具权限不足: roleName={roleName}, toolName={toolName}, "
                               f"allowed={allowedToolList}"])

        #4) 工具路由(G2: 未知工具)
        cmd = TOOL_CMD_MAP.get(toolName, "")
        if not cmd:
            return _errResult(CMD, ERR_TOOL_UNKNOWN, lang,
                              [f"未知工具: toolName={toolName}, 允许值={sorted(TOOL_CMD_MAP.keys())}"])

        #5) 转发下游 /chapi(唯一数据入口: common/chServerCommon.py)
        params = _normalizeParams(dataSet)
        try:
            server = comCh.ChServer(host = mcpConfig.CH_SERVER_HOST, port = mcpConfig.CH_SERVER_PORT,
                                    sessionID = token, rootPath = mcpConfig.CH_SERVER_ROOT_PATH)
            response = server.query(cmd, params)
        except Exception as e:
            _logError(f"mcpinvoke 下游调用异常 toolName:{toolName}, cmd:{cmd}, errMsg:{e}, {traceback.format_exc()}")
            return _errResult(CMD, ERR_DOWNSTREAM, lang, [f"下游 /chapi 调用异常: {str(e)}"])

        if not isinstance(response, dict) or not response:
            _logError(f"mcpinvoke 下游不可达 toolName:{toolName}, cmd:{cmd}, "
                      f"host:{mcpConfig.CH_SERVER_HOST}, port:{mcpConfig.CH_SERVER_PORT}")
            return _errResult(CMD, ERR_DOWNSTREAM, lang,
                              [f"下游 /chapi 不可达: {mcpConfig.CH_SERVER_HOST}:{mcpConfig.CH_SERVER_PORT}"])

        downstream = response.get("data") or {}
        downstreamErrCode = _toStr(downstream.get("errCode")) if isinstance(downstream, dict) else ""

        rtnData = {
            "toolName": toolName,
            "cmd": cmd,
            "roleName": roleName,
            "loginID": loginID,
            "identitySource": identitySource,
            "downstreamErrCode": downstreamErrCode,
            "downstream": downstream,
        }
        result = apiCommon.genRtnResult(CMD, errCode = ERR_OK, rtnField = "", lang = lang,
                                        msgKey = apiCommon.DEFAULT_MSG_KEY, rtnData = rtnData)
    except Exception as e:
        result = apiCommon.genErrResult(CMD, e)
    return result


CMD_MAP = {
    "mcpinvoke": funcMcpInvoke,
}

#占位端点清单(供诊断/落地跟踪使用, 不参与注册表合并)
#★ SP4b(P3-4): mcpinvoke 已落地为 /chapi 侧薄入口(端点总数仍 69, 不新增 CMD)
PLACEHOLDER_CMD_LIST = []


if __name__ == "__main__":
    pass
    print("mcpApi CMD_MAP keys:", list(CMD_MAP.keys()))
    print("TOOL_CMD_MAP:", TOOL_CMD_MAP)
