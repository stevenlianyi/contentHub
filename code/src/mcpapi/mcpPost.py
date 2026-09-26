#! /usr/bin/env python3
#encoding: utf-8

#Filename: mcpPost.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-17
#Description:  contentHub(内容中枢) MCP服务实现层, 承载全部业务处理逻辑/数据获取
#类比 src/main/chAPIPost.py (业务实现层)
#入口层 mcp_entry.py 通过 userApp.post(toolName, dataSet, envSet) 调用本层
#本期范围: 只读工具(主题/主题附图/版式/平台能力矩阵/渲染任务/渲染产物/投递记录)
#参照 stock_rotation_strategy/src/mcpapi/mcpPost.py 的结构与实现模式


_VERSION="20260917"


import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import traceback
import asyncio

#global defintion/common var etc.
from common import globalDefinition as comGD

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#contentHub RESTful 客户端
from common import chServerCommon as comCh

#Redis会话校验(鉴权数据源)
from common import redisCommon as comDB

#MCP SDK官方鉴权协议
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.middleware.auth_context import get_access_token

#setting files
from config import basicSettings as settings
from config import mcpConfig as mcpConfig


_processorPID = os.getpid()


# _LOG 处理: 上级(如mcp_entry.py)可注入, 未注入时创建默认logger
# 项目标准模式, 优先使用已有_LOG(同 chAPIPost.py)
if "_LOG" not in dir() or not _LOG:
    _LOG = misc.setLogNew(comGD._DEF_LOG_CH_MCP_TITLE, comGD._DEF_LOG_CH_MCP_NAME) #modify here

_DEBUG = getattr(settings, "_DEBUG", False)

#contentHub服务sessionID, 优先环境变量, 其次默认账号
_CH_SESSION_ID = mcpConfig.CH_SESSION_ID

#ChServer全局单例池(按sessionID缓存, 复用HTTP连接)
_chServers = {}


#command part begin

#===========================================================
# MCP鉴权部分: 承载Bearer token校验
# 由FastMCP官方 token_verifier 机制调用(streamable-http传输)
# 鉴权数据源为Redis session + ROLE_CMD_LIST, 与 ylwz 既有体系一致
#===========================================================

class CHAccessToken(AccessToken):
    """扩展SDK的AccessToken, 额外携带roleName/allowedTools, 便于业务层按用户/角色差异化处理"""
    roleName: str = ""
    allowedTools: str = ""


class CHTokenVerifier(TokenVerifier):
    """MCP Bearer token 校验器: 复用 Redis session + ROLE_CMD_LIST 鉴权
    实现 mcp.server.auth.provider.TokenVerifier 协议:
    async def verify_token(self, token: str) -> AccessToken | None
    """
    async def verify_token(self, token: str) -> AccessToken | None:
        """验证token, 有效则返回携带身份信息的AccessToken, 无效返回None"""
        result = None
        try:
            tokenMasking = token[:20] + "..."
            #Redis读取走线程池, 避免阻塞事件循环
            sessionIDSet = await asyncio.to_thread(comDB.getSessionInfo, token)
            roleName = sessionIDSet.get("roleName", "")
            if roleName in settings.ROLE_CMD_LIST:
                loginID = sessionIDSet.get("loginID", "")
                result = CHAccessToken(
                    token=token,
                    client_id=loginID,
                    scopes=[],
                    expires_at=None,
                )
                result.roleName = roleName
                result.allowedTools = _genAllowedTools(roleName)
                _LOG.info(f"D: PID:{_processorPID}, token:{tokenMasking}, loginID:{loginID}, roleName:{roleName}")
        except Exception as e:
            errMsg = f"PID: {_processorPID}, verify_token errMsg:{str(e)}"
            _LOG.error(f"{errMsg}, {traceback.format_exc()}")
        return result


def _genAllowedTools(roleName):
    """按角色取允许调用的MCP工具清单(逗号分隔)
    未配置 settings.MCP_TOOL_LIST 时返回空串, 表示不限制工具(与参考实现行为一致)
    """
    allowedTools = ""
    try:
        toolListData = getattr(settings, "MCP_TOOL_LIST", {})
        toolNameList = toolListData.get(roleName, [])
        allowedTools = ",".join(toolNameList)
    except Exception as e:
        _LOG.error(f"PID:{_processorPID}, 生成工具权限清单失败:{str(e)}")
    return allowedTools


#===========================================================
# ChServer 单例管理(按sessionID缓存)
#===========================================================

def getChServer(sessionID=""):
    """获取ChServer实例(按sessionID懒加载缓存)
    说明: 参考实现使用单一全局单例; 本项目按调用者sessionID分池,
          以便下游 /chapi 按真实调用者做权限裁剪
    """
    global _chServers
    if not sessionID:
        sessionID = _CH_SESSION_ID
    if sessionID not in _chServers:
        try:
            _chServers[sessionID] = comCh.ChServer(
                host=mcpConfig.CH_SERVER_HOST,
                port=mcpConfig.CH_SERVER_PORT,
                sessionID=sessionID,
                rootPath=mcpConfig.CH_SERVER_ROOT_PATH,
            )
            comCh._LOG = _LOG  #注入日志器(模块级变量)
            if _DEBUG:
                _LOG.info(f"创建 ChServer 实例, host:{mcpConfig.CH_SERVER_HOST}, port:{mcpConfig.CH_SERVER_PORT}, sessionID:{str(sessionID)[:8]}...")
        except Exception as e:
            _LOG.error(f"创建 ChServer 实例失败: {str(e)}, {traceback.format_exc()}")
    if sessionID not in _chServers:
        raise RuntimeError("ChServer 实例创建失败")
    return _chServers[sessionID]


def _getSessionID(dataSet):
    """取本次调用使用的sessionID: 优先调用者token, 其次默认账号"""
    sessionID = ""
    try:
        sessionID = dataSet.get("_sessionID", "") or _CH_SESSION_ID
    except Exception:
        sessionID = _CH_SESSION_ID
    return sessionID


#===========================================================
# 统一分发入口 (类比 chAPIPost.py 的 post())
# toolPathMap 工具注册表定义在文件末尾(类比 urlPathMap)
#===========================================================

def post(toolName, dataSet, envSet):
    """
    MCP实现层统一分发入口
    toolName: 工具名
    dataSet: 请求参数dict
    envSet: 环境信息dict(如来源会话)
    返回: {toolName, errCode, rtnData}
    """
    result = {}
    errCode = "B0"
    rtnData = {}
    localSN = str(_processorPID)

    try:
        #从官方鉴权context中获取已验证身份(HTTP层已由SDK的RequireAuthMiddleware保证有效)
        accessTokenObj = get_access_token()
        if accessTokenObj:
            envSet["token"] = accessTokenObj.token
            envSet["loginID"] = accessTokenObj.client_id
            envSet["roleName"] = getattr(accessTokenObj, "roleName", "")
            envSet["allowedTools"] = getattr(accessTokenObj, "allowedTools", "")
        else:
            envSet["token"] = ""
            envSet["loginID"] = ""
            envSet["roleName"] = ""
            envSet["allowedTools"] = ""
            _LOG.warning(f"W: PID:{_processorPID}, toolName:{toolName}, get_access_token() is None")

        if not toolName:
            errCode = "ERR_NOCMD"
            rtnData = {"errMsg": "ERR_NOCMD, toolName is empty"}
        else:
            #工具级授权: 未配置MCP_TOOL_LIST时 allowedTools 为空, 不限制
            allowedTools = envSet.get("allowedTools", "")
            if allowedTools and toolName not in allowedTools.split(","):
                errCode = "BT"
                rtnData = {"errMsg": f"BT, tool not allowed, toolName:{toolName}, roleName:{envSet.get('roleName','')}"}
                _LOG.warning(f"W: PID:{_processorPID}, toolName:{toolName}, roleName:{envSet.get('roleName','')}, BT")
            elif toolName in toolPathMap:
                #把调用者会话透传给处理函数(处理函数签名保持 (CMD, dataSet), 与参考实现一致)
                if isinstance(dataSet, dict):
                    dataSet["_sessionID"] = envSet.get("token", "")

                if _DEBUG:
                    _LOG.info(f"R: MCP,toolName:{toolName},data:{misc.jsonDumps(dataSet)},envSet:{misc.jsonDumps(envSet)}")

                funcResult = toolPathMap[toolName](toolName, dataSet)
                #解包func*返回的 {errCode, rtnData}, 使返回结构统一为 {toolName, errCode, rtnData}
                if isinstance(funcResult, dict):
                    errCode = funcResult.get("errCode", "B0")
                    rtnData = funcResult.get("rtnData", {})
                else:
                    errCode = "B0"
                    rtnData = funcResult
            else:
                errCode = "ERR_NOCMD"
                rtnData = {"errMsg": f"ERR_NOCMD, unknow toolName:{toolName}"}

    except Exception as e:
        errMsg = f"PID: {_processorPID},toolName:{toolName}, post() unknow failure, errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")
        errCode = "ERROR"
        rtnData = {"errMsg": f"ERR_GENERAL, {str(e)}"}

    result = {
        "toolName": toolName,
        "errCode": errCode,
        "rtnData": rtnData,
    }

    if _DEBUG:
        _LOG.info(f"S: MCP,toolName:{toolName},errCode:{errCode},data:{misc.jsonDumps(result)}")

    return result


#===========================================================
# 通用辅助函数
#===========================================================

def _truncateResult(dataList, limit=None):
    """截断结果列表, 防止token超限; 返回 (截断后列表, 总数)"""
    total = 0
    try:
        if dataList is None:
            return [], 0
        if not isinstance(dataList, list):
            return dataList, 0
        total = len(dataList)
        if limit is None:
            limit = mcpConfig.TOOL_RESULT_LIMIT
        if total > limit:
            return dataList[-limit:], total
        return dataList, total
    except Exception as e:
        _LOG.error(f"截断结果异常: {str(e)}")
        return dataList, total


def _normalizeData(dataSet):
    """参数归一化: 清理空字符串参数"""
    result = {}
    try:
        if not dataSet:
            return result
        for k, v in dataSet.items():
            if v is None:
                continue
            if isinstance(v, str) and v.strip() == "":
                continue
            result[k] = v
    except Exception as e:
        _LOG.error(f"参数归一化异常: {str(e)}")
        result = dataSet
    return result


def _extractList(resp):
    """从下游 /chapi 查询响应中取出数据列表与总数
    下游查询响应形如: {"data": {"indexKey":.., "total":.., "beginNum":.., "endNum":.., "data":[...]}, "status":200}
    """
    dataList = []
    total = 0
    try:
        if isinstance(resp, dict):
            body = resp.get("data", {})
            if isinstance(body, dict):
                dataList = body.get("data", []) or []
                total = int(body.get("total", 0) or 0)
            elif isinstance(body, list):
                dataList = body
        elif isinstance(resp, list):
            dataList = resp
    except Exception as e:
        _LOG.error(f"解析查询响应异常: {str(e)}, {traceback.format_exc()}")
    return dataList, total


def _genPageRtnData(dataList, total, limitNum):
    """组装分页返回体(统一 total/returned/data 三件套)"""
    resultData, listTotal = _truncateResult(dataList, limitNum)
    rtnData = {
        "total": total if total else listTotal,
        "returned": len(resultData),
        "data": resultData,
    }
    return rtnData


#===========================================================
# 只读工具处理函数 (类比 func* 处理函数)
#===========================================================

def funcSearchTopics(CMD, dataSet):
    """查询主题列表"""
    result = {}
    errCode = "B0"
    rtnData = {}

    try:
        dataSet = _normalizeData(dataSet)
        limitNum = int(dataSet.get("limit", 0) or mcpConfig.QUERY_DEFAULT_LIMIT)

        server = getChServer(_getSessionID(dataSet))
        resp = server.searchTopics(
            topicCode=dataSet.get("topic_code", dataSet.get("topicCode", "")),
            title=dataSet.get("keyword", dataSet.get("title", "")),
            status=dataSet.get("status", ""),
            publishStatus=dataSet.get("publish_status", dataSet.get("publishStatus", "")),
            categoryCode=dataSet.get("category_code", dataSet.get("categoryCode", "")),
            ownerID=dataSet.get("owner_id", dataSet.get("ownerID", "")),
            mode=dataSet.get("mode", ""),
            limitNum=limitNum,
        )

        dataList, total = _extractList(resp)
        rtnData = _genPageRtnData(dataList, total, limitNum)
        rtnData["keyword"] = dataSet.get("keyword", "")
    except Exception as e:
        errMsg = f"查询主题列表失败: {str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")
        errCode = "ERROR"
        rtnData = {"errMsg": errMsg}

    result["errCode"] = errCode
    result["rtnData"] = rtnData
    return result


def funcGetTopic(CMD, dataSet):
    """查询单条主题详情"""
    result = {}
    errCode = "B0"
    rtnData = {}

    try:
        dataSet = _normalizeData(dataSet)
        topicCode = dataSet.get("topic_code", dataSet.get("topicCode", ""))
        recID = dataSet.get("topic_id", dataSet.get("recID", ""))
        if not topicCode and not recID:
            return {"errCode": "BA", "errMsg": "参数 topic_code 与 topic_id 至少需要一个"}

        limitNum = int(dataSet.get("limit", 0) or mcpConfig.QUERY_DEFAULT_LIMIT)
        server = getChServer(_getSessionID(dataSet))
        resp = server.getTopic(
            topicCode=topicCode,
            recID=recID,
            mode=dataSet.get("mode", ""),
            limitNum=limitNum,
        )

        dataList, total = _extractList(resp)
        rtnData = _genPageRtnData(dataList, total, limitNum)
        rtnData["topicCode"] = topicCode
        rtnData["topicID"] = recID
    except Exception as e:
        errMsg = f"查询主题详情失败: {str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")
        errCode = "ERROR"
        rtnData = {"errMsg": errMsg}

    result["errCode"] = errCode
    result["rtnData"] = rtnData
    return result


def funcListTopicAssets(CMD, dataSet):
    """查询主题附图清单"""
    result = {}
    errCode = "B0"
    rtnData = {}

    try:
        dataSet = _normalizeData(dataSet)
        topicID = dataSet.get("topic_id", dataSet.get("topicID", ""))
        if not topicID:
            return {"errCode": "BA", "errMsg": "参数 topic_id 不能为空"}

        limitNum = int(dataSet.get("limit", 0) or mcpConfig.QUERY_DEFAULT_LIMIT)
        server = getChServer(_getSessionID(dataSet))
        resp = server.readTopicAssetList(
            topicID=topicID,
            fileID=dataSet.get("file_id", dataSet.get("fileID", "")),
            usageType=dataSet.get("usage_type", dataSet.get("usageType", "")),
            limitNum=limitNum,
        )

        dataList, total = _extractList(resp)
        rtnData = _genPageRtnData(dataList, total, limitNum)
        rtnData["topicID"] = topicID
    except Exception as e:
        errMsg = f"查询主题附图清单失败: {str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")
        errCode = "ERROR"
        rtnData = {"errMsg": errMsg}

    result["errCode"] = errCode
    result["rtnData"] = rtnData
    return result


def funcListLayouts(CMD, dataSet):
    """查询版式模板清单"""
    result = {}
    errCode = "B0"
    rtnData = {}

    try:
        dataSet = _normalizeData(dataSet)
        limitNum = int(dataSet.get("limit", 0) or mcpConfig.QUERY_DEFAULT_LIMIT)

        server = getChServer(_getSessionID(dataSet))
        resp = server.readLayoutList(
            platform=dataSet.get("platform", ""),
            layoutType=dataSet.get("layout_type", dataSet.get("layoutType", "")),
            layoutCode=dataSet.get("layout_code", dataSet.get("layoutCode", "")),
            enabled=dataSet.get("enabled", ""),
            limitNum=limitNum,
        )

        dataList, total = _extractList(resp)
        rtnData = _genPageRtnData(dataList, total, limitNum)
    except Exception as e:
        errMsg = f"查询版式模板清单失败: {str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")
        errCode = "ERROR"
        rtnData = {"errMsg": errMsg}

    result["errCode"] = errCode
    result["rtnData"] = rtnData
    return result


def funcListPlatforms(CMD, dataSet):
    """查询平台能力矩阵"""
    result = {}
    errCode = "B0"
    rtnData = {}

    try:
        dataSet = _normalizeData(dataSet)
        limitNum = int(dataSet.get("limit", 0) or mcpConfig.QUERY_DEFAULT_LIMIT)

        server = getChServer(_getSessionID(dataSet))
        resp = server.readPlatformList(
            platformCode=dataSet.get("platform_code", dataSet.get("platformCode", "")),
            enabled=dataSet.get("enabled", ""),
            limitNum=limitNum,
        )

        dataList, total = _extractList(resp)
        rtnData = _genPageRtnData(dataList, total, limitNum)
    except Exception as e:
        errMsg = f"查询平台能力矩阵失败: {str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")
        errCode = "ERROR"
        rtnData = {"errMsg": errMsg}

    result["errCode"] = errCode
    result["rtnData"] = rtnData
    return result


def funcGetRenderJob(CMD, dataSet):
    """查询渲染任务清单"""
    result = {}
    errCode = "B0"
    rtnData = {}

    try:
        dataSet = _normalizeData(dataSet)
        limitNum = int(dataSet.get("limit", 0) or mcpConfig.QUERY_DEFAULT_LIMIT)

        server = getChServer(_getSessionID(dataSet))
        resp = server.readRenderJobList(
            jobCode=dataSet.get("job_code", dataSet.get("jobCode", "")),
            topicID=dataSet.get("topic_id", dataSet.get("topicID", "")),
            jobStatus=dataSet.get("job_status", dataSet.get("jobStatus", "")),
            platform=dataSet.get("platform", ""),
            limitNum=limitNum,
        )

        dataList, total = _extractList(resp)
        rtnData = _genPageRtnData(dataList, total, limitNum)
    except Exception as e:
        errMsg = f"查询渲染任务清单失败: {str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")
        errCode = "ERROR"
        rtnData = {"errMsg": errMsg}

    result["errCode"] = errCode
    result["rtnData"] = rtnData
    return result


def funcListArtifacts(CMD, dataSet):
    """查询渲染产物清单"""
    result = {}
    errCode = "B0"
    rtnData = {}

    try:
        dataSet = _normalizeData(dataSet)
        limitNum = int(dataSet.get("limit", 0) or mcpConfig.QUERY_DEFAULT_LIMIT)

        server = getChServer(_getSessionID(dataSet))
        resp = server.readArtifactList(
            topicID=dataSet.get("topic_id", dataSet.get("topicID", "")),
            jobID=dataSet.get("job_id", dataSet.get("jobID", "")),
            kind=dataSet.get("kind", ""),
            platform=dataSet.get("platform", ""),
            artifactStatus=dataSet.get("artifact_status", dataSet.get("artifactStatus", "")),
            limitNum=limitNum,
        )

        dataList, total = _extractList(resp)
        rtnData = _genPageRtnData(dataList, total, limitNum)
    except Exception as e:
        errMsg = f"查询渲染产物清单失败: {str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")
        errCode = "ERROR"
        rtnData = {"errMsg": errMsg}

    result["errCode"] = errCode
    result["rtnData"] = rtnData
    return result


def funcListPublishRecords(CMD, dataSet):
    """查询投递(发布)记录清单"""
    result = {}
    errCode = "B0"
    rtnData = {}

    try:
        dataSet = _normalizeData(dataSet)
        limitNum = int(dataSet.get("limit", 0) or mcpConfig.QUERY_DEFAULT_LIMIT)

        server = getChServer(_getSessionID(dataSet))
        resp = server.readPublishRecordList(
            topicID=dataSet.get("topic_id", dataSet.get("topicID", "")),
            artifactId=dataSet.get("artifact_id", dataSet.get("artifactId", "")),
            platform=dataSet.get("platform", ""),
            success=dataSet.get("success", ""),
            operator=dataSet.get("operator", ""),
            limitNum=limitNum,
        )

        dataList, total = _extractList(resp)
        rtnData = _genPageRtnData(dataList, total, limitNum)
    except Exception as e:
        errMsg = f"查询投递(发布)记录清单失败: {str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")
        errCode = "ERROR"
        rtnData = {"errMsg": errMsg}

    result["errCode"] = errCode
    result["rtnData"] = rtnData
    return result


#===========================================================
# 工具注册表 (类比 chAPIPost.py 的 urlPathMap)
# 新增只读工具时: 在此登记 + 在 mcp_entry.py 增加 @mcp.tool()
#===========================================================

toolPathMap = {
    "search_topics":        funcSearchTopics,
    "get_topic":            funcGetTopic,
    "list_topic_assets":    funcListTopicAssets,
    "list_layouts":         funcListLayouts,
    "list_platforms":       funcListPlatforms,
    "get_render_job":       funcGetRenderJob,
    "list_artifacts":       funcListArtifacts,
    "list_publish_records": funcListPublishRecords,
}


if __name__ == "__main__":
    pass
    # import pdb
    # pdb.set_trace()
    print("toolPathMap keys:", list(toolPathMap.keys()))
