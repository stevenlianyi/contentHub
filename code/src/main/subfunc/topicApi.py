#! /usr/bin/env python3
#encoding: utf-8

#Filename: topicApi.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 主题业务域接入端点(见 plan/chAPIPost分拆方案.md 3.1 / 4.1)。
#
#约定(命名即契约, G6): 本模块只暴露模块级 `CMD_MAP = {"cmd小写": 处理函数}`, 不自行修改全局注册表。
#处理函数统一签名 func(CMD, dataSet, sessionIDSet), 由聚合器(subfunc/__init__.py)合并进注册表。
#
#★ SP2a(C2 主题管理)职责变更:
#  ch_topic / ch_topic_version 的 8 个 CRUD 端点(topic{add|del|modify|qry} +
#  topicversion{add|del|modify|qry})**由本模块接管**, 内部统一走 processor/topicService.py,
#  以便「字段区间校验 / 状态机 / wordCount 统计 / topicCode 幂等 / 版本快照」在 HTTP 路径上真实生效。
#  为此 tools/mergeCrudApi.py 已把这两张表列入 EXCLUDED_TABLE_LIST, crudApi 只装配其余 8 张表(32 条 CMD);
#  若两侧同时登记同名 CMD, 聚合器的 V1 冲突校验会在导入期直接抛 RuntimeError(服务起不来)。
#
#★ SP2c(C4 版式引擎)归属迁移: topicrender 已从本模块**移出**, 由 subfunc/renderApi.py(渲染域)接管,
#  内部走 processor/renderService.py -> engine/layoutEngine.py。故主题域由 9 条降为 8 条
#  (TOPIC_CMD_LIST 恒为 8 条 CRUD; PLACEHOLDER_CMD_LIST 清空)。迁移后端点总数仍为 69:
#  {account:16, crud:32, topic:8, asset:9, render:1, publish:1, compliance:1, mcp:1}。
#
#本层职责边界: 只做「会话上下文抽取 + 报文封装 + 异常兜底」, 业务规则一律在 topicService 内;
#  严禁在本文件拼 SQL / 直接调 mysqlCommon(红线 R1)—— 数据访问只经 topicService。

_VERSION="20260919"


import os
import sys

_mainDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../code/src/main
_srcDir = os.path.dirname(_mainDir)                                     # .../code/src
for _path in (_srcDir, _mainDir):
    if _path not in sys.path:
        sys.path.insert(0, _path)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

from subfunc import apiCommon

from processor import topicService


#本模块接管的 8 个业务端点(供诊断/静态校验使用, 不参与注册表合并)
TOPIC_CMD_LIST = [
    "topicadd", "topicdel", "topicmodify", "topicqry",
    "topicversionadd", "topicversiondel", "topicversionmodify", "topicversionqry",
]


def _serviceResult(CMD, dataSet, sessionIDSet, serviceFunc):
    """统一收口: 调用 topicService 并把业务返回映射为 HTTP 报文(零业务, 只做封装/兜底)"""
    try:
        sessionCtx = apiCommon.genSessionContext(dataSet, sessionIDSet)
        rtn = serviceFunc(dataSet, sessionIDSet)
        if not isinstance(rtn, dict):
            rtn = {}

        return apiCommon.genRtnResult(CMD,
                                      errCode = rtn.get("errCode", "C1"),
                                      rtnField = rtn.get("field", ""),
                                      lang = sessionCtx["lang"],
                                      msgKey = sessionCtx["msgKey"],
                                      rtnErrMsgList = rtn.get("errMsgList"),
                                      rtnData = rtn.get("data"))
    except Exception as e:
        return apiCommon.genErrResult(CMD, e)


#主题(topic): 字段区间校验 + 状态机 + wordCount + topicCode 幂等 + 版本快照
def funcTopicAdd(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, topicService.addTopic)


def funcTopicDel(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, topicService.deleteTopic)


def funcTopicModify(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, topicService.modifyTopic)


def funcTopicQry(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, topicService.queryTopic)


#主题版本快照(topicversion): 保存主题时自动落快照; 这里提供手动落快照/元信息维护/查询
def funcTopicversionAdd(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, topicService.addTopicVersion)


def funcTopicversionDel(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, topicService.deleteTopicVersion)


def funcTopicversionModify(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, topicService.modifyTopicVersion)


def funcTopicversionQry(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, topicService.queryTopicVersion)


CMD_MAP = {
    "topicadd": funcTopicAdd,
    "topicdel": funcTopicDel,
    "topicmodify": funcTopicModify,
    "topicqry": funcTopicQry,

    "topicversionadd": funcTopicversionAdd,
    "topicversiondel": funcTopicversionDel,
    "topicversionmodify": funcTopicversionModify,
    "topicversionqry": funcTopicversionQry,
}

#占位端点清单(供诊断/落地跟踪使用, 不参与注册表合并); topicrender 已于 SP2c 迁至 subfunc/renderApi.py
PLACEHOLDER_CMD_LIST = []


if __name__ == "__main__":
    pass
    print("topicApi CMD_MAP keys:", list(CMD_MAP.keys()))
    print("topicApi TOPIC_CMD_LIST:", TOPIC_CMD_LIST)
