#! /usr/bin/env python3
#encoding: utf-8

#Filename: accountSvcClient.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub 账号服务薄封装(见 plan/chAPIPost分拆方案.md 3.1 / 决策 12.2)。
#
#职责边界(方案 6.3「循环依赖规避」):
#  HTTP 细节全部在 common/accountClient.py(低层唯一出口), 本文件只做:
#    1) 错误码归一: 账号服务回包取 MSG.errCode(与基线一致), 下游不可用统一映射为 "CI";
#    2) 角色映射与默认角色回落(settings.ROLE_ACCOUNT_ROLE / accountServiceDefaultRoleName);
#    3) 为 accountApi 提供「一命令一函数」的薄包装, 使 CMD 处理器保持短小。
#  ★ 本文件不写库、不落 Redis、不做任何权限判定; 亦不得反向 import main/chAPIPost.py。

_VERSION="20260918"


import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

from config import basicSettings as settings

from common import accountClient as comAcc

from subfunc import context as ctx


_processorPID = ctx._processorPID
_LOG = ctx._LOG
_DEBUG = ctx._DEBUG

#账号服务命令码(统一从 common/accountClient.py re-export, 便于调用方少写一层前缀)
ACCOUNT_CMD_LOGIN = comAcc.ACCOUNT_SVC_CMD_LOGIN
ACCOUNT_CMD_GEN_SESSION = comAcc.ACCOUNT_SVC_CMD_GEN_SESSION
ACCOUNT_CMD_USER_INFO = comAcc.ACCOUNT_SVC_CMD_USER_INFO
ACCOUNT_CMD_LOGOUT = comAcc.ACCOUNT_SVC_CMD_LOGOUT
ACCOUNT_CMD_SMS_REQUEST = comAcc.ACCOUNT_SVC_CMD_SMS_REQUEST
ACCOUNT_CMD_SMS_VERIFY = comAcc.ACCOUNT_SVC_CMD_SMS_VERIFY
ACCOUNT_CMD_RESET_PASSWD = comAcc.ACCOUNT_SVC_CMD_RESET_PASSWD
ACCOUNT_CMD_MODIFY_ROLE = comAcc.ACCOUNT_SVC_CMD_MODIFY_ROLE
ACCOUNT_CMD_USER_EXIST = comAcc.ACCOUNT_SVC_CMD_USER_EXIST
ACCOUNT_CMD_SAVE_USER_DATA = comAcc.ACCOUNT_SVC_CMD_SAVE_USER_DATA
ACCOUNT_CMD_GET_USER_DATA = comAcc.ACCOUNT_SVC_CMD_GET_USER_DATA
ACCOUNT_CMD_SESSION_CMD_LIST = comAcc.ACCOUNT_SVC_CMD_SESSION_CMD_LIST

#下游不可用时的统一错误码(基线账号服务封装体把非 200 记为 "CI")
_ERR_SVC_OFFLINE = "CI"


def normalizeRoleName(roleName):
    """角色归一: 不在 settings.ROLE_CMD_LIST 中的角色一律回落默认角色(与基线一致)"""
    if roleName not in settings.ROLE_CMD_LIST:
        roleName = settings.accountServiceDefaultRoleName

    return roleName


def svcErrCode(rtnData):
    """从账号服务回包中取错误码: 优先 MSG.errCode(与基线的 msgData.get("errCode") 一致),
       其次顶层 errCode; 均缺失时视为成功 "B0"。"""
    result = "B0"

    if isinstance(rtnData, dict):
        msgData = rtnData.get("MSG", {})
        if isinstance(msgData, dict) and msgData.get("errCode"):
            result = msgData.get("errCode")
        elif rtnData.get("errCode"):
            result = rtnData.get("errCode")

    return result


def accountServiceForward(cmd, dataSet, roleName = None):
    """账号服务薄转发(所有账号类 CMD 的唯一入口)。

       入参:
         cmd      账号服务命令码(A0A0/A2A0/A5A0/A6A0/A7A0/A9A0/G1A0/G2A0 ...);
         dataSet  请求报文(原样透传, 不修改调用方字典);
         roleName 需要做「本系统角色 -> 账号服务角色」转换时传入, 缺省不转换。

       出参: (errCode, rtnData)
         errCode  账号服务错误码; 下游非 200 / 不可达时统一为 "CI";
         rtnData  账号服务原始回包(失败时为空字典)。
    """
    requestData = dict(dataSet) if isinstance(dataSet, dict) else {}

    if roleName is not None:
        if roleName in settings.ROLE_ACCOUNT_ROLE:
            requestData["roleName"] = settings.ROLE_ACCOUNT_ROLE[roleName]
        else:
            #角色无法映射到账号服务: 与基线一致, 直接判 B8(会话/角色异常), 不再转发
            return "B8", {}

    statusCode, rtnData = comAcc.accountServiceRequestEx(cmd, requestData)

    if statusCode != 200:
        if _LOG:
            _LOG.warning(f"W: PID:{_processorPID}, account service unavailable, cmd:{cmd}, status:{statusCode}")
        return _ERR_SVC_OFFLINE, {}

    return svcErrCode(rtnData), rtnData


def getSessionAndCmdList(sessionID):
    """GAA0: 取会话 + 功能清单(角色已归一)。出参 (errCode, sessionIDSet)。"""
    errCode, sessionIDSet = comAcc.getSessionAndCmdList(sessionID)

    if isinstance(sessionIDSet, dict) and sessionIDSet:
        sessionIDSet["roleName"] = normalizeRoleName(sessionIDSet.get("roleName"))

    return errCode, sessionIDSet


def getUserInfo(loginID, sessionID = ""):
    """A3A0: 取用户信息(角色已归一)。出参 用户信息字典(失败为空字典)。"""
    result = comAcc.getUserInfo(loginID, sessionID)

    if result:
        result["roleName"] = normalizeRoleName(result.get("roleName"))

    return result


def chkUserExist(loginID):
    """AIA0: 账号服务侧用户存在性。出参 True / False。"""
    return comAcc.chkUserExist(loginID)


def modifyUserRoleName(loginID, roleName, sessionID):
    """AEA0: 修改账号服务侧角色。出参 True / False。"""
    return comAcc.modifyUserRoleName(loginID, roleName, sessionID)


def userLoginOrRegistration(dataSet):
    """A0A0: 登录 / 注册转发(角色回落与基线一致)。出参 (errCode, rtnData)。"""
    errCode, rtnData = accountServiceForward(ACCOUNT_CMD_LOGIN, dataSet)

    if isinstance(rtnData, dict) and (not rtnData.get("roleName") or rtnData.get("roleName") == "visitor"):
        #与基线一致: 未返回角色或不合法时回落默认角色
        rtnData["roleName"] = settings.accountServiceDefaultRoleName

    return errCode, rtnData


def userLogout(dataSet, roleName = None):
    """A5A0: 登出转发(需要本系统角色 -> 账号服务角色转换)。出参 (errCode, rtnData)。"""
    return accountServiceForward(ACCOUNT_CMD_LOGOUT, dataSet, roleName = roleName)


def userGenSession(dataSet):
    """A2A0: 生成会话转发。出参 (errCode, rtnData)。"""
    return accountServiceForward(ACCOUNT_CMD_GEN_SESSION, dataSet)


def smsRequest(dataSet):
    """A6A0: 短信验证码请求转发。出参 (errCode, rtnData)。"""
    return accountServiceForward(ACCOUNT_CMD_SMS_REQUEST, dataSet)


def smsVerify(dataSet):
    """A7A0: 短信验证码校验转发。出参 (errCode, rtnData)。"""
    return accountServiceForward(ACCOUNT_CMD_SMS_VERIFY, dataSet)


def resetPasswd(dataSet):
    """A9A0: 重置口令转发。出参 (errCode, rtnData)。"""
    return accountServiceForward(ACCOUNT_CMD_RESET_PASSWD, dataSet)


def saveUserData(dataSet):
    """G1A0: 保存用户数据转发。出参 (errCode, rtnData)。"""
    return accountServiceForward(ACCOUNT_CMD_SAVE_USER_DATA, dataSet)


def getUserData(dataSet):
    """G2A0: 读取用户数据转发。出参 (errCode, rtnData)。"""
    return accountServiceForward(ACCOUNT_CMD_GET_USER_DATA, dataSet)


if __name__ == "__main__":
    pass
    print("account cmd list:", [
        ACCOUNT_CMD_LOGIN, ACCOUNT_CMD_GEN_SESSION, ACCOUNT_CMD_USER_INFO,
        ACCOUNT_CMD_LOGOUT, ACCOUNT_CMD_SMS_REQUEST, ACCOUNT_CMD_SMS_VERIFY,
        ACCOUNT_CMD_RESET_PASSWD, ACCOUNT_CMD_MODIFY_ROLE, ACCOUNT_CMD_USER_EXIST,
        ACCOUNT_CMD_SAVE_USER_DATA, ACCOUNT_CMD_GET_USER_DATA, ACCOUNT_CMD_SESSION_CMD_LIST,
    ])
    print("normalizeRoleName:", normalizeRoleName(""), normalizeRoleName("administrator"), normalizeRoleName("unknown"))
