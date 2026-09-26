#! /usr/bin/env python3
#encoding: utf-8

#Filename: renderApi.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 渲染与产物业务域接入端点(见 plan/chAPIPost分拆方案.md 3.1 / 4.1)。

#约定(命名即契约, G6): 本模块只暴露模块级 `CMD_MAP = {"cmd小写": 处理函数}`, 不自行修改全局注册表。
#处理函数统一签名 func(CMD, dataSet, sessionIDSet), 由聚合器(subfunc/__init__.py)合并进注册表。
#
#★ SP2c(C4 版式引擎)职责变更:
#  `topicrender` **由本模块(渲染域)接管**, 内部统一走 processor/renderService.py ->
#  engine/layoutEngine.py(唯一渲染入口) + 4 套 Jinja2 模板(stack/carousel/longimage/swipe)。
#  为此已从 subfunc/topicApi.py 的 CMD_MAP 与 TOPIC_CMD_LIST 中**移出** topicrender(topic 域 9 -> 8)。
#  端点总数保持 69: 分布变为 {account:16, crud:32, topic:8, asset:9, render:1, publish:1, compliance:1, mcp:1}。
#  若两侧同时登记同名 CMD, 聚合器的 V1 冲突校验会在导入期直接抛 RuntimeError(服务起不来)。
#
#★ SP3a(C5 平台适配)职责延伸(**不新增 CMD, 端点总数仍 69**):
#  `topicrender` 的 dataSet 增加可选参数 `platform`(缺省取 ch_layout.platform)、`renderMode`
#  (本轮只支持 sync; job -> C2, 异步化归 SP3c)、`exportKind`(通用导出形态)。
#  渲染入口内部经 processor/platformAdapter 的适配器得到**平台形态产物**(wechat_mp 内联样式 HTML /
#  generic HTML·Markdown·JSON)。适配器只做「形态转换」, 业务编排仍在 processor/renderService.py。
#  新增平台只需「加一个适配器 + 一条 ch_platform 记录」, 不改主干、不改本文件的路由表。
#
#本层职责边界: 只做「会话上下文抽取 + 报文封装 + 异常兜底」, 业务规则一律在 renderService 内;
#  严禁在本文件拼 SQL / 直接调 mysqlCommon(红线 R1)—— 数据访问只经 renderService。
#
#本期仍留占位: artifactpack(素材包打包, 归 SP3, 仍在 assetApi)。

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

from processor import renderService


#本模块接管的业务端点(供诊断/静态校验使用, 不参与注册表合并)
RENDER_CMD_LIST = ["topicrender"]


def _serviceResult(CMD, dataSet, sessionIDSet, serviceFunc):
    """统一收口: 调用 renderService 并把业务返回映射为 HTTP 报文(零业务, 只做封装/兜底)"""
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


#主题渲染(topicrender): 按主题 + 版式同步渲染出结构化正文/卡片/切片计划(SP2c 落地)
def funcTopicRender(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, renderService.renderTopic)


CMD_MAP = {
    "topicrender": funcTopicRender,
}

#占位端点清单(供诊断/落地跟踪使用, 不参与注册表合并)
PLACEHOLDER_CMD_LIST = []


if __name__ == "__main__":
    pass
    print("renderApi CMD_MAP keys:", list(CMD_MAP.keys()))
    print("renderApi RENDER_CMD_LIST:", RENDER_CMD_LIST)
