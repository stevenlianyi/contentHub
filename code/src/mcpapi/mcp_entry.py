#! /usr/bin/env python3
#encoding: utf-8

#Filename: mcp_entry.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-17
#Description:  contentHub(内容中枢) MCP服务入口层, 负责MCP协议接入/工具路由分发/响应返回
#类比 src/main/chAPI.py (Flask入口层)
#不含任何业务逻辑, 业务处理全部转发到 mcpPost.py (实现层)
#本期范围: 只读工具(8个) + 只读资源(3个)
#参照 stock_rotation_strategy/src/mcpapi/mcp_entry.py 的结构与实现模式


_VERSION="20260917"

import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
#将本文件所在目录加入sys.path, 保证以包方式导入时 import mcpPost 也能找到
mcpapiDir = os.path.dirname(os.path.abspath(__file__))
if mcpapiDir not in sys.path:
    sys.path.insert(0, mcpapiDir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import logging

import uvicorn

#MCP SDK
from mcp.server.fastmcp import FastMCP
from mcp.server.auth.settings import AuthSettings

from pydantic import AnyHttpUrl

from typing import Any

#global defintion/common var etc.
from common import globalDefinition as comGD

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#业务实现层 (类比 chAPI.py 中 import chAPIPost as userApp)
from mcpapi import mcpPost as userApp #modify here

#setting files
from config import mcpConfig as mcpConfig


_processorPID = os.getpid()

appName = "chmcpapi" #modify here
transportType = mcpConfig.MCP_TRANSPORT #MCP传输协议: streamable-http/sse/stdio
_DEBUG = True #modify here
# _DEBUG = False #modify here


#日志器: 项目标准模式, 优先使用已有_LOG
if "_LOG" not in dir() or not _LOG:
    _LOG = misc.setLogNew(comGD._DEF_LOG_CH_MCP_TITLE, comGD._DEF_LOG_CH_MCP_NAME) #modify here

#注入日志器到实现层
userApp._LOG = _LOG

# 关闭 uvicorn 和 FastMCP 的 INFO 日志
# 如果需要更彻底的关闭
logging.getLogger("uvicorn").handlers.clear()
logging.getLogger("mcp").handlers.clear()

systemVersion = str(sys.version_info.major) + "." + str(sys.version_info.minor ) + "." + str(sys.version_info.micro )
_LOG.info(f"PID:{_processorPID}, python version:{systemVersion}, start code version:{_VERSION}, server version:{mcpConfig.MCP_SERVER_VERSION}, main code version:{userApp._VERSION}")

_LOG.info(f"C: serverName:{mcpConfig.MCP_SERVER_NAME}, transport:{transportType}, host:{mcpConfig.MCP_SERVER_HOST}, port:{mcpConfig.MCP_SERVER_PORT}, appType:{appName}")


# ============================================================
# 创建 FastMCP 服务实例(鉴权采用SDK官方token_verifier机制)
# 校验逻辑定义于 mcpPost.CHTokenVerifier, 由SDK自动装配官方鉴权中间件
# (BearerAuthBackend + AuthContextMiddleware + RequireAuthMiddleware)
# ============================================================
mcp = FastMCP(
    mcpConfig.MCP_SERVER_NAME,
    instructions="内容中枢MCP服务, 提供主题/主题附图/版式/平台能力矩阵/渲染任务/渲染产物/投递记录等只读查询工具",
    host=mcpConfig.MCP_SERVER_HOST,
    port=mcpConfig.MCP_SERVER_PORT,
    token_verifier=userApp.CHTokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(mcpConfig.MCP_AUTH_ISSUER_URL),
        resource_server_url=AnyHttpUrl(mcpConfig.MCP_AUTH_RESOURCE_SERVER_URL),
    ),
)

app = mcp.streamable_http_app()  # 调用函数获取 ASGI 应用(内部已含官方鉴权中间件)


#===========================================================
# MCP 工具注册 (类比 chAPI.py 的 @application.route)
# 每个工具仅做参数转发, 不包含业务逻辑
#===========================================================

#主题工具
@mcp.tool()
def search_topics(
    keyword: str = "",
    category_code: str = "",
    status: str = "",
    publish_status: str = "",
    owner_id: str = "",
    mode: str = "",
    limit: int = 30,
) -> dict[str, Any]:
    """查询主题列表(内容中枢的核心内容资产)。

    Args:
        keyword: 关键字(匹配标题, 可选)
        category_code: 分类编码(可选)
        status: 主题状态(DRAFT/RENDERING/RENDERED/PUBLISHED/ARCHIVED, 可选)
        publish_status: 发布状态(UNPUBLISHED/DRAFTED/PUBLISHED/FAILED, 可选)
        owner_id: 归属用户loginID(可选)
        mode: 查询模式(full/simple, 可选)
        limit: 返回条数上限(默认30)

    Returns:
        包含 errCode 和 rtnData 的字典
    """
    envSet = {"toolName": "search_topics"}
    dataSet = {
        "keyword": keyword,
        "category_code": category_code,
        "status": status,
        "publish_status": publish_status,
        "owner_id": owner_id,
        "mode": mode,
        "limit": limit,
    }
    return userApp.post("search_topics", dataSet, envSet)


@mcp.tool()
def get_topic(
    topic_code: str = "",
    topic_id: str = "",
    limit: int = 30,
) -> dict[str, Any]:
    """查询单条主题详情(主题编码与记录ID至少提供一个)。

    Args:
        topic_code: 主题编码(幂等键, 可选)
        topic_id: 主题记录ID(ch_topic.recID, 可选)
        limit: 返回条数上限(默认30)

    Returns:
        包含 errCode 和 rtnData 的字典
    """
    envSet = {"toolName": "get_topic"}
    dataSet = {
        "topic_code": topic_code,
        "topic_id": topic_id,
        "limit": limit,
    }
    return userApp.post("get_topic", dataSet, envSet)


@mcp.tool()
def list_topic_assets(
    topic_id: str,
    usage_type: str = "",
    limit: int = 30,
) -> dict[str, Any]:
    """查询主题附图清单(含图注/用途/展示顺序)。

    Args:
        topic_id: 主题记录ID(ch_topic.recID)
        usage_type: 用途类型(cover=封面/body=正文图/inline=内联图, 可选)
        limit: 返回条数上限(默认30)

    Returns:
        包含 errCode 和 rtnData 的字典
    """
    envSet = {"toolName": "list_topic_assets"}
    dataSet = {
        "topic_id": topic_id,
        "usage_type": usage_type,
        "limit": limit,
    }
    return userApp.post("list_topic_assets", dataSet, envSet)


#版式与平台工具
@mcp.tool()
def list_layouts(
    platform: str = "",
    layout_type: str = "",
    layout_code: str = "",
    enabled: str = "",
    limit: int = 30,
) -> dict[str, Any]:
    """查询版式模板清单(上下展示/左右轮播/长图拼接)。

    Args:
        platform: 目标平台(wechat_mp/xiaohongshu/generic, 可选)
        layout_type: 版式类型(stack=上下/carousel=左右轮播/longimage=长图, 可选)
        layout_code: 版式编码(如 stack_v1, 可选)
        enabled: 是否启用(1=启用/0=停用, 可选)
        limit: 返回条数上限(默认30)

    Returns:
        包含 errCode 和 rtnData 的字典
    """
    envSet = {"toolName": "list_layouts"}
    dataSet = {
        "platform": platform,
        "layout_type": layout_type,
        "layout_code": layout_code,
        "enabled": enabled,
        "limit": limit,
    }
    return userApp.post("list_layouts", dataSet, envSet)


@mcp.tool()
def list_platforms(
    platform_code: str = "",
    enabled: str = "",
    limit: int = 30,
) -> dict[str, Any]:
    """查询平台能力矩阵(各平台的交付模式/规格上限/合规要求)。

    Args:
        platform_code: 平台编码(wechat_mp/xiaohongshu/generic, 可选)
        enabled: 是否启用(1=启用/0=停用, 可选)
        limit: 返回条数上限(默认30)

    Returns:
        包含 errCode 和 rtnData 的字典
    """
    envSet = {"toolName": "list_platforms"}
    dataSet = {
        "platform_code": platform_code,
        "enabled": enabled,
        "limit": limit,
    }
    return userApp.post("list_platforms", dataSet, envSet)


#渲染工具
@mcp.tool()
def get_render_job(
    job_code: str = "",
    topic_id: str = "",
    job_status: str = "",
    platform: str = "",
    limit: int = 30,
) -> dict[str, Any]:
    """查询渲染任务及其状态(进度/耗时/错误信息)。

    Args:
        job_code: 任务编码(幂等键, 可选)
        topic_id: 关联主题记录ID(可选)
        job_status: 任务状态(PENDING/RUNNING/DONE/FAILED, 可选)
        platform: 目标平台(可选)
        limit: 返回条数上限(默认30)

    Returns:
        包含 errCode 和 rtnData 的字典
    """
    envSet = {"toolName": "get_render_job"}
    dataSet = {
        "job_code": job_code,
        "topic_id": topic_id,
        "job_status": job_status,
        "platform": platform,
        "limit": limit,
    }
    return userApp.post("get_render_job", dataSet, envSet)


@mcp.tool()
def list_artifacts(
    topic_id: str = "",
    job_id: str = "",
    kind: str = "",
    platform: str = "",
    artifact_status: str = "",
    limit: int = 30,
) -> dict[str, Any]:
    """查询渲染产物清单(html/png/zip/json)。

    Args:
        topic_id: 关联主题记录ID(可选)
        job_id: 关联渲染任务记录ID(可选)
        kind: 产物类型(html/png/zip/json, 可选)
        platform: 目标平台(可选)
        artifact_status: 产物状态(READY/EXPIRED, 可选)
        limit: 返回条数上限(默认30)

    Returns:
        包含 errCode 和 rtnData 的字典
    """
    envSet = {"toolName": "list_artifacts"}
    dataSet = {
        "topic_id": topic_id,
        "job_id": job_id,
        "kind": kind,
        "platform": platform,
        "artifact_status": artifact_status,
        "limit": limit,
    }
    return userApp.post("list_artifacts", dataSet, envSet)


#投递记录工具
@mcp.tool()
def list_publish_records(
    topic_id: str = "",
    platform: str = "",
    success: str = "",
    limit: int = 30,
) -> dict[str, Any]:
    """查询投递(发布)记录清单(含平台返回码与远程ID)。

    Args:
        topic_id: 关联主题记录ID(可选)
        platform: 目标平台(可选)
        success: 是否成功(1=成功/0=失败, 可选)
        limit: 返回条数上限(默认30)

    Returns:
        包含 errCode 和 rtnData 的字典
    """
    envSet = {"toolName": "list_publish_records"}
    dataSet = {
        "topic_id": topic_id,
        "platform": platform,
        "success": success,
        "limit": limit,
    }
    return userApp.post("list_publish_records", dataSet, envSet)


#===========================================================
# MCP 资源注册 (只读资源, 与工具同样仅做转发)
# 资源返回JSON字符串, 便于客户端直接消费
#===========================================================

@mcp.resource("contenthub://platforms")
def resource_platforms() -> str:
    """平台能力矩阵(各平台可交付形态/规格上限/合规要求)"""
    envSet = {"toolName": "resource_platforms"}
    dataSet = {"enabled": "1", "limit": 30}
    result = userApp.post("list_platforms", dataSet, envSet)
    return misc.jsonDumps(result, ensure_ascii=False)


@mcp.resource("contenthub://layouts")
def resource_layouts() -> str:
    """版式模板清单(内置版式及其参数规格)"""
    envSet = {"toolName": "resource_layouts"}
    dataSet = {"enabled": "1", "limit": 100}
    result = userApp.post("list_layouts", dataSet, envSet)
    return misc.jsonDumps(result, ensure_ascii=False)


@mcp.resource("contenthub://topic/{topic_id}")
def resource_topic(topic_id: str) -> str:
    """主题详情资源(按主题记录ID读取)

    Args:
        topic_id: 主题记录ID(ch_topic.recID)
    """
    envSet = {"toolName": "resource_topic"}
    dataSet = {"topic_id": topic_id, "limit": 1}
    result = userApp.post("get_topic", dataSet, envSet)
    return misc.jsonDumps(result, ensure_ascii=False)


#===========================================================
# 主入口
#===========================================================

if __name__ == "__main__":
    _LOG.info(f"I: MCP Server 启动: {mcpConfig.MCP_SERVER_NAME}, transport: {transportType}")
    # mcp.run(transport=transportType)
    # 使用已添加中间件的 app
    uvicorn.run(app, host=mcpConfig.MCP_SERVER_HOST, port=mcpConfig.MCP_SERVER_PORT)
