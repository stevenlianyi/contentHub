#! /usr/bin/env python3
#encoding: utf-8:

#Filename: publishApi.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 投递业务域接入端点(见 plan/chAPIPost分拆方案.md 3.1 / 4.1)。
#
#约定(命名即契约, G6): 本模块只暴露模块级 `CMD_MAP = {"cmd小写": 处理函数}`, 不自行修改全局注册表。
#
#★ SP4a(C6 投递链路)职责落地:
#  `publishpush` **由本模块接管**, 内部统一走 processor/publishService.py(投递编排 + 幂等/二次确认/
#  撤销窗 + 落库 + 审计); 它**不新增 CMD**(CMD_MAP 仍只有 publishpush, 端点总数保持 69, V3 校验不变)。
#  投递路径**必须复用** SP3c 的 `publishcheck`(在 publishService 内以合规闸门形式调用, 未过校验不得投递)。
#
#平台红线: 本项目只做公众号草稿投递路径, **不得引入小红书投递/自动发布的任何代码路径**
#  (publishService 对 xiaohongshu/generic 显式拒绝, 见 NON_DELIVERABLE_PLATFORM_LIST)。
#
#本层职责边界: 只做「会话上下文抽取 + 报文封装 + 异常兜底」, 业务规则一律在 publishService 内;
#  严禁在本文件拼 SQL / 直接调 mysqlCommon(红线 R1)—— 数据访问只经 publishService。

_VERSION="20260919"


import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #setdefaultencoding('utf-8')

from subfunc import apiCommon

from processor import publishService


#本模块接管的业务端点(供诊断/静态校验使用, 不参与注册表合并)
PUBLISH_CMD_LIST = ["publishpush"]


def _serviceResult(CMD, dataSet, sessionIDSet, serviceFunc):
    """统一收口: 调用 publishService 并把业务返回映射为 HTTP 报文(零业务, 只做封装/兜底)"""
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


#投递推送(publishpush): 把渲染产物投递到目标平台(公众号草稿箱); action=revoke 时在撤销窗内撤销
def funcPublishPush(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, publishService.publishPush)


CMD_MAP = {
    "publishpush": funcPublishPush,
}

#占位端点清单(供诊断/落地跟踪使用, 不参与注册表合并): SP4a 起 publishpush 已实现
PLACEHOLDER_CMD_LIST = []


if __name__ == "__main__":
    pass
    print("publishApi CMD_MAP keys:", list(CMD_MAP.keys()))
    print("publishApi PUBLISH_CMD_LIST:", PUBLISH_CMD_LIST)
