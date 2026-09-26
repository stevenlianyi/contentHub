#! /usr/bin/env python3
#encoding: utf-8

#Filename: accountClient.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub(内容中枢) 账号服务(account service) HTTP 客户端。
#
#背景(见 plan/chAPIPost分拆方案.md 6.4 / 决策 12.2):
#  账号服务是外部 HTTP 服务(config/basicSettings.py::ACCOUNT_SERVICE_URL), 通过 CMD 码转发请求;
#  基线 museum 把这段转发代码写死在 main/museumAPIPost.py 里(7 处 requests.post 重复实现),
#  contentHub 统一收敛到本文件: subfunc/accountSvcClient.py 只做薄封装(角色映射/默认角色回落),
#  MCP 层访问 /chapi 走 common/chServerCommon.py, 不复用本文件。
#
#职责边界:
#  1) accountServiceRequest        低层转发: 组包(misc.jsonDumps) -> POST -> 解析(misc.jsonLoads), 异常不外抛;
#  2) getSessionAndCmdList(GAA0)   取会话 + 功能清单(权限中枢的数据来源);
#  3) getUserInfo(A3A0)            取用户基本信息;
#  4) chkUserExist(AIA0)           账号服务侧存在性(登录前置检查);
#  5) modifyUserRoleName(AEA0)     修改角色;
#  本文件不做任何业务判断、不写库、不落 Redis。

_VERSION="20260918"


import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import traceback
import requests

from common import miscCommon as misc

from config import basicSettings as settings


_processorPID = os.getpid()

#日志: 上级(main/chAPI.py 或 main/chAPIPost.py)可注入 _LOG; 未注入时留空, 由调用方保证有日志
if "_LOG" not in dir() or not _LOG:
    _LOG = None

#账号服务请求超时(秒): 防止下游无响应时请求线程长时间挂起
_HTTP_REQUEST_TIMEOUT = 30

#账号服务命令码(与 account service 协议一致, 集中登记避免散落魔数)
ACCOUNT_SVC_CMD_LOGIN = "A0A0"           #登录 / 注册
ACCOUNT_SVC_CMD_GEN_SESSION = "A2A0"     #生成会话
ACCOUNT_SVC_CMD_USER_INFO = "A3A0"       #取用户信息
ACCOUNT_SVC_CMD_LOGOUT = "A5A0"          #登出
ACCOUNT_SVC_CMD_SMS_REQUEST = "A6A0"     #短信验证码请求
ACCOUNT_SVC_CMD_SMS_VERIFY = "A7A0"      #短信验证码校验
ACCOUNT_SVC_CMD_RESET_PASSWD = "A9A0"    #重置口令
ACCOUNT_SVC_CMD_MODIFY_ROLE = "AEA0"     #修改角色
ACCOUNT_SVC_CMD_USER_EXIST = "AIA0"      #用户存在性
ACCOUNT_SVC_CMD_SAVE_USER_DATA = "G1A0"  #保存用户数据
ACCOUNT_SVC_CMD_GET_USER_DATA = "G2A0"   #读取用户数据
ACCOUNT_SVC_CMD_SESSION_CMD_LIST = "GAA0" #取会话 + 功能清单

#固定请求头(与 ylwz 既有体系一致)
_ACCOUNT_HTTP_HEADERS = {"content-type": "application/json"}


def accountServiceRequestEx(cmd, requestData, timeout = _HTTP_REQUEST_TIMEOUT):
    """账号服务低层转发(唯一出口, 带 HTTP 状态码)。
       出参: (statusCode, rtnData)
             statusCode HTTP 状态码; 请求未发起或异常时为 0;
             rtnData    账号服务返回的报文字典; 非 200 / 非 JSON 时为 {}。
       说明: 本函数不抛异常、不做业务语义解释; 需要区分「下游不可用」与「下游返回错误码」的
             调用方请使用本函数(如 subfunc/accountSvcClient.py 把 status != 200 映射为 "CI")。"""
    statusCode = 0
    result = {}

    try:
        if not isinstance(requestData, dict):
            requestData = {}
        else:
            requestData = dict(requestData)

        requestData["CMD"] = cmd

        payload = misc.jsonDumps(requestData)
        r = requests.post(settings.ACCOUNT_SERVICE_URL, data = payload,
                          headers = _ACCOUNT_HTTP_HEADERS, timeout = timeout)

        statusCode = r.status_code
        if statusCode == 200:
            rtnData = misc.jsonLoads(r.text)
            if isinstance(rtnData, dict):
                result = rtnData

    except Exception as e:
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, accountServiceRequestEx cmd:{cmd}, errMsg:{str(e)}, {traceback.format_exc()}")

    return statusCode, result


def accountServiceRequest(cmd, requestData, timeout = _HTTP_REQUEST_TIMEOUT):
    """账号服务低层转发(仅返回报文字典)。
       出参: 账号服务返回的报文字典; 网络异常 / 非 200 / 非 JSON 一律返回 {}, 不抛异常。"""
    statusCode, rtnData = accountServiceRequestEx(cmd, requestData, timeout = timeout)  # noqa: F841

    return rtnData


def getSessionAndCmdList(sessionID, cmdMapKeyList = None):
    """GAA0: 取会话信息与功能清单(权限判定中枢的数据来源)。
       出参: (errCode, sessionIDSet)
             errCode      账号服务侧错误码("B0" 为成功, 失败时保持原值供上层透出);
             sessionIDSet 会话信息字典(含 loginID/openID/roleName/activeFLag 等, 失败时为空字典)。
       说明: 回包结构与基线保持一致(外层 errCode + 内层 data.errCode 双层判定)。"""
    errCode = "B0"
    sessionIDSet = {}

    if cmdMapKeyList is None:
        cmdMapKeyList = []

    requestData = {
        "sessionID": sessionID,
        "CMDMapKeyList": cmdMapKeyList,
    }
    rtnData = accountServiceRequest(ACCOUNT_SVC_CMD_SESSION_CMD_LIST, requestData)

    userErrCode = rtnData.get("errCode", "B0")
    if userErrCode == "B0":
        data = rtnData.get("data", {})
        if not isinstance(data, dict):
            data = {}
        errCode = data.get("errCode", "B0")
        if errCode == "B0":
            sessionIDSet = data.get("sessionIDSet", {})
            if not isinstance(sessionIDSet, dict):
                sessionIDSet = {}

    return errCode, sessionIDSet


def getUserInfo(loginID, sessionID = ""):
    """A3A0: 取用户基本信息。
       出参: 字典(取到时含 loginID/nickName/realName/email/sex/roleName); 失败时为空字典。
       说明: 不做角色回落(角色映射与默认角色由 subfunc/accountSvcClient.py 统一处理)。"""
    result = {}

    requestData = {
        "loginID": loginID,
        "sessionID": sessionID,
    }
    rtnData = accountServiceRequest(ACCOUNT_SVC_CMD_USER_INFO, requestData)

    if rtnData.get("errCode") == "B0":
        result["loginID"] = rtnData.get("loginID", "")
        result["nickName"] = rtnData.get("nickName", "")
        result["realName"] = rtnData.get("realName", "")
        result["email"] = rtnData.get("email", "")
        result["sex"] = rtnData.get("sex", "")
        result["roleName"] = rtnData.get("roleName", "")

    return result


def chkUserExist(loginID):
    """AIA0: 账号服务侧用户存在性。出参 True / False(不抛异常)。"""
    result = False

    rtnData = accountServiceRequest(ACCOUNT_SVC_CMD_USER_EXIST, {"userID": loginID})
    if rtnData.get("userExistFlag") == "Y":
        result = True

    return result


def modifyUserRoleName(loginID, roleName, sessionID):
    """AEA0: 修改用户在账号服务侧的角色。出参 True / False(本地库同步由调用方负责)。"""
    result = False

    requestData = {
        "loginID": loginID,
        "roleName": roleName,
        "sessionID": sessionID,
    }
    rtnData = accountServiceRequest(ACCOUNT_SVC_CMD_MODIFY_ROLE, requestData)
    if rtnData.get("errCode") == "B0":
        result = True

    return result


if __name__ == "__main__":
    pass
    print("ACCOUNT_SERVICE_URL", settings.ACCOUNT_SERVICE_URL)
    print("account svc cmd list", [
        ACCOUNT_SVC_CMD_LOGIN, ACCOUNT_SVC_CMD_GEN_SESSION, ACCOUNT_SVC_CMD_USER_INFO,
        ACCOUNT_SVC_CMD_LOGOUT, ACCOUNT_SVC_CMD_SMS_REQUEST, ACCOUNT_SVC_CMD_SMS_VERIFY,
        ACCOUNT_SVC_CMD_RESET_PASSWD, ACCOUNT_SVC_CMD_MODIFY_ROLE, ACCOUNT_SVC_CMD_USER_EXIST,
        ACCOUNT_SVC_CMD_SAVE_USER_DATA, ACCOUNT_SVC_CMD_GET_USER_DATA, ACCOUNT_SVC_CMD_SESSION_CMD_LIST,
    ])
