#! /usr/bin/env python3
#encoding: utf-8

#Filename: chAPIPost.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub(内容中枢) HTTP 接入层瘦入口 —— 聚合注册表 + post() 主流程。
#
#拆分依据: plan/chAPIPost分拆方案.md 形态 A / 4.3 / 5.3 / 8.2。
#★ 本文件只保留「聚合 + 编排」职责(目标 ≤400 行), 禁止堆放任何业务处理函数:
#  - 注册表与三道校验      -> subfunc/__init__.py
#  - 入参处理/返回封装/兜底 -> subfunc/apiCommon.py
#  - 账号与会话/权限        -> subfunc/accountApi.py + accountSvcClient.py
#  - 48 张表 CRUD(生成件)   -> subfunc/crudApi.py
#  - 业务域端点             -> subfunc/{topic|asset|render|publish|compliance|mcp}Api.py
#
#依赖方向(强制单向, G2): main/chAPI.py -> main/chAPIPost.py -> subfunc/* -> (context、common/*)
#  subfunc/ 内严禁反向 import 本文件。

_VERSION="20260918"


import os
import sys

#main/ 与 code/src 同时入 sys.path: 保证 `from subfunc import ...` / `from common import ...`
#在任意 cwd(含 gunicorn/fcgi 启动)下都能解析成功
_mainDir = os.path.dirname(os.path.abspath(__file__))
_srcDir = os.path.dirname(_mainDir)
for _path in (_srcDir, _mainDir):
    if _path not in sys.path:
        sys.path.insert(0, _path)

if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import traceback

from config import basicSettings as settings

from common import globalDefinition as comGD

from common import funcCommon as comFC

from common import miscCommon as misc

from common import redisCommon as comDB

from common import chCommon as comCh

from common import errMsgCommon as comErr

from subfunc import CMD_MAP, CMD_LIST, CMD_OWNER  # CMD_OWNER: CMD -> 业务域(出参信封整形按域分派/诊断)

from subfunc import context as ctx

from subfunc import apiCommon

from subfunc import accountApi

from subfunc import accountSvcClient


_processorPID = ctx._processorPID
_DEBUG = ctx._DEBUG

#日志: 上级(main/chAPI.py)可注入; 未注入时复用 context 单例(同名 logger, 天然同一对象)
_LOG = ctx._LOG

#聚合后的完整注册表(方案 5.3): 由各子模块 CMD_MAP 合并而成, 导入期已过三道校验
urlPathMap = dict(CMD_MAP)

#由聚合结果派生, 不再逐个手写(方案 5.2)
CMDMapKeyList = list(CMD_LIST)

#程序流水号(与基线一致: 进程内自增, 用于日志/出参串接一次请求)
gSN = 0

#出参是否把 fileID 转成可访问 URL(主计划 3.3.8「库内只存 fileID, URL 由后端出参转换」)。
#★ 该开关同时落实 CI 约束 C5: common/chCommon.py 必须被 chAPIPost.py 真实引用(防「建而不用」)。
_FILE_URL_FILL_FLAG = True


def applyLog(logObj):
    """注入日志对象(供 main/chAPI.py 调用)并同步到各子模块, 保证全链路同一 logger。"""
    global _LOG

    if not logObj:
        return _LOG

    _LOG = logObj
    ctx._LOG = logObj
    apiCommon._LOG = logObj
    accountApi._LOG = logObj
    accountSvcClient._LOG = logObj

    return _LOG


def fillFileUrlsInResult(aResult):
    """出参收口: 把结果中的 fileID 字段转成可访问 URL(多桶路由由 chCommon 内部按记录快照解析)。
       说明: fileStorageCommon 采用延迟导入, 不牵出云厂商 SDK; 单条记录也可命中顶层字段。"""
    if not _FILE_URL_FILL_FLAG or not aResult:
        return aResult

    try:
        data = None
        if isinstance(aResult, dict):
            data = aResult.get("data")

        if isinstance(data, list):
            comCh.fillFileUrls(data)
        elif isinstance(data, dict):
            comCh.fillFileUrls(data)
        else:
            comCh.fillFileUrls(aResult)
    except Exception as e:
        if _LOG:
            _LOG.warning(f"W: PID:{_processorPID}, fillFileUrls failed, errMsg:{str(e)}")

    return aResult


def normalizeMsgKey(aResult):
    """出参信封统一(2026-09-21): 把 msgKey 归一到 contentHub 口径。

    背景: 生成器产物(database/auto_generated/auto_gen_code_ch_*.py)与 crudApi.py 硬编码
          `msgKey = "applicationMsgKey"`, 而 contentHub 统一使用 `"contenthub"`;
          common/errMsgCommon.py::MSG_KEY_ALIAS 已保证「错误码文案」查表正确,
          但出参信封里回显的 msgKey 仍是旧值。
    做法: 在唯一分发出口收口, 72 个端点出参一致, 且生成件零改动(重新生成也不会回退)。
    """
    if isinstance(aResult, dict) and aResult.get("msgKey"):
        aResult["msgKey"] = comErr.resolveMsgKey(aResult.get("msgKey"))
    return aResult


def post(urlPath, dataSet, IP, envSet, appType):
    """统一分发入口(与基线 main/museumAPIPost.py::post 行为对齐):
       免登录判定 -> 会话/权限校验 -> 停用拦截 -> 分发
       -> 出参收口(fileID 转 URL/信封整形/msgKey/SN/时间戳) -> 异常兜底。"""
    global gSN
    global _LOG

    CMD = str(urlPath).lower()
    errCode = "OK"
    rtnData = {}
    localSN = ""

    try:
        gSN += 1
        localSN = str(gSN)

        if not isinstance(dataSet, dict):
            dataSet = {}
        if not isinstance(envSet, dict):
            envSet = {}

        #访问的服务器地址, 用于文件系统转存(写回 context 单例, 与基线 gSourceServerAddr 语义一致)
        dataSet["_source_server_http"] = apiCommon.setSourceServerAddr(envSet)

        if _DEBUG and _LOG:
            _LOG.info(f"R: PID: {_processorPID},IP:{IP},SN:{localSN},CMD:{CMD} '{misc.jsonDumps(dataSet)}'")

        IP = str(IP).strip()

        #IP 频次防刷(checkFlag=False 时不触发 Redis 计数, 与基线一致)
        if comDB.chkIPCount(IP, checkFlag = False):
            if CMD != "":
                dataSet["CMD"] = CMD

                #客户端可自带 SN, 用于串联同一次业务操作
                try:
                    localSN = str(int(dataSet.get("SN")))
                except Exception:
                    pass

                dataType = dataSet.get("dataType", "")
                if dataType != "":
                    dataSet = apiCommon.dataFormatConvertor(dataType, dataSet)

                if CMD in settings.NO_SESSIONID_CMD_LIST:
                    #免登录白名单: 使用默认账号/角色, 不做账号服务往返
                    userCMDMapKeyList = list(settings.NO_SESSIONID_CMD_LIST)
                    sessionIDSet = {}
                    sessionIDSet["loginID"] = settings.accountServiceDefaultLoginID
                    sessionIDSet["roleName"] = settings.accountServiceDefaultRoleName
                    errCode = "B0"
                else:
                    userCMDMapKeyList, sessionIDSet, errCode = accountApi.calUserCMDMapKeyList(dataSet, CMDMapKeyList)

                #停用账号拦截(基线字段名 activeFLag, 保持兼容)
                activeFlag = sessionIDSet.get("activeFLag", comGD._CONST_YES)
                if activeFlag == comGD._CONST_NO:
                    errCode = "BT"

                if errCode == "B0":
                    sessionIDSet["appType"] = appType

                    if (CMD in userCMDMapKeyList) and (CMD in urlPathMap):
                        dataSet["_IP"] = IP
                        rtnData = urlPathMap[CMD](CMD, dataSet, sessionIDSet)
                    else:
                        rtnData = comFC.rtnMSG("ERR_NOCMD", "ERR_NOCMD")
                else:
                    rtnData = comFC.rtnMSG(errCode, errCode)
                    rtnData["errCode"] = errCode
            else:
                rtnData = comFC.rtnMSG("ERR_NOCMD", "ERR_NOCMD")
        else:
            rtnData = comFC.rtnMSG("ERR_IPFLOOD", "ERR_IPFLOOD")

        if not isinstance(rtnData, dict):
            rtnData = {}

        fillFileUrlsInResult(rtnData)

        #出参信封整形(见 plan/出参信封统一改造.md): 查询类维持原结构, 其余按域取 CMD_OWNER 分派
        #(account -> 顶层保留 + data 副本; ch_* -> 业务字段整体迁入 data; 未注册 CMD -> 原样)
        #★ 必须排在 fillFileUrlsInResult 之后: fillFileUrls 只加工传入对象的一层字段
        if CMD not in apiCommon.QUERY_CMD_LIST:
            rtnData = apiCommon.normalizeEnvelope(rtnData, CMD_OWNER.get(CMD, ""), CMD)

        normalizeMsgKey(rtnData)

        rtnData["SN"] = localSN
        rtnData["YMDHMS"] = misc.getTime()
        result = rtnData

        if _DEBUG and _LOG:
            _LOG.info(f"S: PID: {_processorPID},IP:{IP},SN:{localSN},CMD:{CMD},data:{misc.jsonDumps(result)}")

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD}, IP:{IP}, post() unknow failure, errMsg:{str(e)}"
        if _LOG:
            _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        result = comFC.rtnMSG("ERROR", "ERR_GENERAL")

    return result


if __name__ == "__main__":
    #本地调试入口: python chAPIPost.py <cmd> '<json>'
    _IP = "0.0.0.0"
    _appType = ""
    _envSet = {"CONTENT_LENGTH": 100}

    if len(sys.argv) > 1:
        _urlPath = sys.argv[1]
        _msg = sys.argv[2] if len(sys.argv) > 2 else "{}"
        print(misc.jsonDumps(post(_urlPath, misc.jsonLoads(_msg), _IP, _envSet, _appType)))
