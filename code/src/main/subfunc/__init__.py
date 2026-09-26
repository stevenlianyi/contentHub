#! /usr/bin/env python3
#encoding: utf-8

#Filename: __init__.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub 接入层子包聚合器(见 plan/chAPIPost分拆方案.md 3.1 / 5.2 / 5.4)。
#
#职责: 只做「声明合并 + 导入期校验」, 不含任何业务逻辑、不发起任何 IO。
#
#三道校验(方案 5.4):
#  V1 CMD 冲突检测  —— 同一 CMD 出现在两个模块, 防止静默覆盖;
#  V2 可调用性检测  —— 处理函数必须是 callable, 防止误写常量/字符串;
#  V3 与配置完整性比对 —— CMD_MAP 必须覆盖 ROLE_CMD_LIST 全集 ∪ NO_SESSIONID_CMD_LIST,
#     防止出现「配置里声明了权限但端点不存在(授权却 404)」或反之的隐蔽缺陷。
#
#★ 可静态测试设计: 三道校验集中在纯函数 mergeCmdMaps() 中, 该函数不引用任何模块级名字
#  (只用内置函数), 因此 test/test_ch_phase0_static.py 可用 AST 抽取其源码 + exec 到隔离
#  命名空间后传伪造入参真触发 V1/V2/V3, 而不需要安装 pandas/PIL/pymysql 等第三方依赖。

_VERSION="20260918"


import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')


from subfunc import context

from subfunc import apiCommon

from subfunc import accountSvcClient

from subfunc import accountApi

from subfunc import crudApi

from subfunc import topicApi

from subfunc import assetApi

from subfunc import renderApi

from subfunc import publishApi

from subfunc import complianceApi

from subfunc import mcpApi


def mergeCmdMaps(moduleMaps, roleCmdList = None, noSessionCmdList = None):
    """合并各子模块的 CMD_MAP 并执行三道校验(纯函数, 不引用模块级名字, 便于静态测试真触发)。

       入参:
         moduleMaps        {"域": {"cmd小写": 处理函数}}; 域按字典序处理, 保证报错稳定可复现;
         roleCmdList       角色 -> 命令清单(dict), 或单个命令清单(list); 缺省 None 跳过 V3 的角色部分;
         noSessionCmdList  免登录命令集合(set/list); 缺省 None 跳过 V3 的免登录部分。

       出参: 合并后的 {"cmd小写": 处理函数}。

       异常:
         V1 同一 cmd 定义于两个域 -> RuntimeError
         V2 处理函数不可调用      -> TypeError
         V3 配置声明的命令缺项     -> RuntimeError
    """
    merged = {}
    owner = {}

    #V1 CMD 冲突检测 + V2 可调用性检测
    domainList = list(moduleMaps.keys())
    try:
        domainList = sorted(domainList)
    except Exception:
        pass

    for domain in domainList:
        cmdMap = moduleMaps.get(domain)

        if not isinstance(cmdMap, dict):
            raise TypeError(f"[subfunc] 域 '{domain}' 的 CMD_MAP 不是 dict: {type(cmdMap)}")

        cmdList = list(cmdMap.keys())
        try:
            cmdList = sorted(cmdList)
        except Exception:
            pass

        for cmd in cmdList:
            handler = cmdMap.get(cmd)

            if cmd in merged:
                raise RuntimeError(
                    f"[subfunc] CMD 冲突: '{cmd}' 同时定义于 '{owner[cmd]}' 与 '{domain}'")

            if not callable(handler):
                raise TypeError(
                    f"[subfunc] CMD '{cmd}'({domain}) 的处理函数不可调用: {type(handler)}")

            merged[cmd] = handler
            owner[cmd] = domain

    #V3 与配置的完整性比对
    needSet = set()

    if roleCmdList:
        if isinstance(roleCmdList, dict):
            roleCmdLists = list(roleCmdList.values())
        else:
            roleCmdLists = [roleCmdList]
        for cmdList in roleCmdLists:
            if cmdList:
                needSet.update(cmdList)

    if noSessionCmdList:
        needSet.update(noSessionCmdList)

    missingList = list(needSet.difference(set(merged.keys())))
    try:
        missingList = sorted(missingList)
    except Exception:
        pass

    if missingList:
        raise RuntimeError(
            f"[subfunc] 注册表与配置不一致: ROLE_CMD_LIST ∪ NO_SESSIONID_CMD_LIST 中以下 CMD 未注册 -> {missingList}")

    return merged


#注册顺序即声明顺序; 顺序不影响路由(dict 精确匹配)
MODULE_MAPS = {
    "account": accountApi.CMD_MAP,
    "crud": crudApi.CMD_MAP,
    "topic": topicApi.CMD_MAP,
    "asset": assetApi.CMD_MAP,
    "render": renderApi.CMD_MAP,
    "publish": publishApi.CMD_MAP,
    "compliance": complianceApi.CMD_MAP,
    "mcp": mcpApi.CMD_MAP,
}

#导入期即完成聚合与三道校验: 冲突/不可调用/配置缺项都会让进程起不来(不静默)
CMD_MAP = mergeCmdMaps(MODULE_MAPS, context.settings.ROLE_CMD_LIST, context.settings.NO_SESSIONID_CMD_LIST)

#由聚合结果派生, 不再逐个手写
CMD_LIST = list(CMD_MAP.keys())

#诊断用: CMD -> 所属域
CMD_OWNER = {cmd: domain for domain, cmdMap in MODULE_MAPS.items() for cmd in cmdMap}


__all__ = [
    "context", "apiCommon", "accountSvcClient", "accountApi", "crudApi",
    "topicApi", "assetApi", "renderApi", "publishApi", "complianceApi", "mcpApi",
    "mergeCmdMaps", "MODULE_MAPS", "CMD_MAP", "CMD_LIST", "CMD_OWNER",
]


if __name__ == "__main__":
    pass
    print("CMD total:", len(CMD_MAP))
    print("CMD by domain:", {k: len(v) for k, v in MODULE_MAPS.items()})
    print("not covered by owner:", [c for c in CMD_MAP if c not in CMD_OWNER])
