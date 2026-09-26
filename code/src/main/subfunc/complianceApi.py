#! /usr/bin/env python3
#encoding: utf-8:

#Filename: complianceApi.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub 合规校验业务域接入端点(见 plan/chAPIPost分拆方案.md 3.1 / 4.1)。

#约定(命名即契约, G6): 本模块只暴露模块级 `CMD_MAP = {"cmd小写": 处理函数}`, 不自行修改全局注册表。

#★ SP3c(C8 合规校验)职责落地:
#  `publishcheck` **由本模块接管**, 内部统一走 processor/complianceService.py(问题清单 + 限流降级);
#  它是「投递前的强制闸门」—— SP4 的 publishpush 落地时必须先过本端点。
#  **不新增 CMD**: CMD_MAP 仍只有 publishcheck 一条, 端点总数保持 69(V3 校验不变)。
#
#本层职责边界: 只做「会话上下文抽取 + 报文封装 + 异常兜底」, 业务规则一律在 complianceService 内;
#  严禁在本文件拼 SQL / 直接调 mysqlCommon(红线 R1)—— 数据访问只经 complianceService。

_VERSION="20260919"


import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

from subfunc import apiCommon

from processor import complianceService


#本模块接管的业务端点(供诊断/静态校验使用, 不参与注册表合并)
COMPLIANCE_CMD_LIST = ["publishcheck"]


def _serviceResult(CMD, dataSet, sessionIDSet, serviceFunc):
    """统一收口: 调用 complianceService 并把业务返回映射为 HTTP 报文(零业务, 只做封装/兜底)"""
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


#发布前合规校验(publishcheck): 对主题/产物做投递前校验, 产出统一「问题清单」(SP3c 落地)
def funcPublishCheck(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, complianceService.publishCheck)


CMD_MAP = {
    "publishcheck": funcPublishCheck,
}

#占位端点清单(供诊断/落地跟踪使用, 不参与注册表合并): SP3c 起 publishcheck 已实现
PLACEHOLDER_CMD_LIST = []


if __name__ == "__main__":
    pass
    print("complianceApi CMD_MAP keys:", list(CMD_MAP.keys()))
    print("complianceApi COMPLIANCE_CMD_LIST:", COMPLIANCE_CMD_LIST)
