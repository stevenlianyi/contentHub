#! /usr/bin/env python3
#encoding: utf-8

#Filename: context.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub 接入层公共依赖与全局单例(见 plan/chAPIPost分拆方案.md 6.2)。
#
#存在意义:
#  基线 main/museumAPIPost.py 的 60-103 行把 settings/comGD/comFC/comDB/comMysql/_LOG 等共享依赖
#  散落在模块顶层, 拆分后若每个子模块各自 import + 各自 setLogNew, 会重复创建 logger handler、
#  重复初始化连接。本模块把它们收敛为单一来源, 所有 subfunc/* 一律 `from subfunc import context as ctx`。
#
#依赖方向(强制单向, G2): subfunc/* -> context -> common/*、config/*
#  禁止 context 反向引用 subfunc 内的业务模块; 禁止任何 subfunc/* 引用 main/chAPIPost.py。

_VERSION="20260918"


import os
import sys

#main/ 需要在 sys.path 中, 才能让 `from subfunc import xxx` 在任意 cwd 下解析成功
_mainDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../code/src/main
_srcDir = os.path.dirname(_mainDir)                                     # .../code/src
if _srcDir not in sys.path:
    sys.path.insert(0, _srcDir)
if _mainDir not in sys.path:
    sys.path.insert(0, _mainDir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')


from config import basicSettings as settings

from common import globalDefinition as comGD

from common import funcCommon as comFC

from common import miscCommon as misc

from common import redisCommon as comDB

from common import mysqlCommon as comMysql

from common import chCommon as comCh

from common import errMsgCommon as comErr

from common import accountClient as comAcc

from common import queryBufferCommon as comQB


_processorPID = os.getpid()

#trace 开关(config/basicSettings.py::_DEBUG)
_DEBUG = settings._DEBUG

#运行环境与文件系统
_SYS = settings._SYS
_SYS_SERVER_NAME = settings._SYS_SERVER_NAME
FILE_SYSTEM_MODE = settings.FILE_SYSTEM_MODE
FILE_SERVER_URL = settings.FILE_SERVER_URL
ACCOUNT_SERVICE_URL = settings.ACCOUNT_SERVICE_URL

#请求来源服务器地址(文件转存时使用), 由 apiCommon.setSourceServerAddr() 在每次请求内刷新;
#基线用模块级全局承载, 这里保持同样语义, 仅集中到单例模块。
gSourceServerAddr = ""


#日志: 上级(main/chAPI.py)可注入 _LOG; 未注入时按 contentHub Web 入口常量创建。
#注意 miscCommon.setLogNew 内部有 `if not logger.handlers` 判重, 且同名 logger 唯一, 天然幂等。
if "_LOG" not in dir() or not _LOG:
    try:
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        #日志初始化失败(如目录只读)不阻断服务, 退化为 stderr 提示(miscCommon 内部已兜底)
        _LOG = None

#把日志对象注入公共件(museum 基线同样是 main 侧注入 common 侧):
#accountClient 自身不创建 logger, 未注入时静默, 由本模块统一注入。
comAcc._LOG = _LOG
