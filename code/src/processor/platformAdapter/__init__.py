#! /usr/bin/env python3
#encoding: utf-8

#Filename: __init__.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 平台适配层包(processor/platformAdapter/, SP3a · C5)。

#★ 包定位(主计划 2.5):
#  以统一抽象基类隔离平台差异, 适配器只做「形态转换 + 通道调用」, 业务编排留在 processor/renderService.py。
#  新增平台只需「加一个适配器 + 一条 ch_platform 记录」, 不改主干。
#
#文件:
#   base.py        PlatformAdapter 抽象基类(契约五方法 render/validate/package/deliver/checkHealth)
#                  + ch_platform 数据驱动的规格校验 + 适配器工厂 getAdapter()
#   wechatMp.py    WechatMpAdapter: 公众号内联样式 HTML(deliverMode=draft_box)
#   generic.py     GenericAdapter: 通用 HTML / Markdown / JSON 导出(deliverMode=asset_pack)
#   xiaohongshu.py XiaohongshuAdapter: 小红书卡片/长图切片(deliverMode=asset_pack; SP3b;
#                  **只导出素材包, 无任何自动发布/投递路径**)
#
#★ 分层契约(强制单向): 本包属业务处理器层(processor/), 只可依赖 engine/ 与 common/;
#  **严禁 import main/subfunc**(接入层); 引擎层(engine/)亦不得反向 import 本包。
#
#★ 本轮(SP3a)零网络: 不调微信/小红书任何接口、不做图片转存、不做投递;
#  deliver 一律返回「未实现」显式错误(投递归 SP4)。
#
#★ 导入策略: 本 __init__ 只导入 base(纯标准库), **不在模块级导入具体适配器**
#  (wechatMp/generic 会牵出 engine/layoutEngine -> common/mysqlCommon), 具体适配器一律经
#  getAdapter() 延迟导入 —— 这既避免包内循环依赖, 也让静态验收可在无第三方依赖下 exec base.py。

_VERSION="20260919"

import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # .../code/src
if parentdir not in sys.path:
    sys.path.insert(0, parentdir)

from processor.platformAdapter import base

from processor.platformAdapter.base import (
    PlatformAdapter,
    PlatformAdapterError,
    checkPlatformSpec,
    normalizePlatformRecord,
    parseSizeSpec,
    getAdapter,
    listAdapterCodes,
    ADAPTER_MODULE_MAP,
)


__all__ = [
    "base", "PlatformAdapter", "PlatformAdapterError",
    "checkPlatformSpec", "normalizePlatformRecord", "parseSizeSpec",
    "getAdapter", "listAdapterCodes", "ADAPTER_MODULE_MAP",
]


if __name__ == "__main__":
    pass
    print("platformAdapter adapters:", listAdapterCodes())
    print("ADAPTER_MODULE_MAP:", ADAPTER_MODULE_MAP)
