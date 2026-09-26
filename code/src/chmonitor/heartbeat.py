#! /usr/bin/env python3
#encoding: utf-8:

#Filename: heartbeat.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 定时任务心跳(SP4c · P3-8; 「定时任务最后成功时间」指标的数据来源)。

#职责:
#  1) 记录定时任务(归档 schedule/archive.py、巡检 schedule/credentialCheck.py、每日巡检 chmonitor/dailyCheck.py)
#     的**最后运行时间**与**最后成功时间**;
#  2) 落点: config/opsSettings.MONITOR_DATA_DIR(默认 code/data/monitor/)下的 heartbeat.json;
#  3) 供 chmonitor/metrics.evaluateSchedulerLastSuccess 判定「超过 1.5 个周期未成功」。
#
#★ 设计: 采用「本地文件心跳」而非新中间件 —— 首期降级口径, 不引入新依赖、不阻塞关键路径;
#  重跑覆盖式写入(非追加), 避免文件无限增长; 写入失败仅记日志, **不抛异常**(不阻断调度任务)。
#★ 分层契约: 只依赖 standard library 与 config/, 不 import processor/subfunc; 亦不被 common 反向依赖。

_VERSION="20260919"


import json
import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../code/src
if parentdir not in sys.path:
    sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #setdefaultencoding('utf-8')

from common import miscCommon as misc

from config import opsSettings


JOB_ARCHIVE = "archive"
JOB_CREDENTIAL_CHECK = "credentialCheck"
JOB_DAILY_CHECK = "dailyCheck"
JOB_NAME_LIST = [JOB_ARCHIVE, JOB_CREDENTIAL_CHECK, JOB_DAILY_CHECK]


def _toStr(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def getStateFilePath():
    """心跳文件路径"""
    return os.path.join(opsSettings.getMonitorDataDir(), opsSettings.MONITOR_HEARTBEAT_FILE)


def loadState():
    """读取心跳状态(不存在/损坏 -> 空字典, 不抛异常)"""
    filePath = getStateFilePath()
    if not os.path.isfile(filePath):
        return {}
    try:
        with open(filePath, "r", encoding = "utf-8") as hFile:
            state = json.load(hFile)
        return state if isinstance(state, dict) else {}
    except Exception:
        return {}


def saveState(state):
    """写心跳状态(覆盖式); 失败返回 False(不抛异常)"""
    state = state if isinstance(state, dict) else {}
    filePath = getStateFilePath()
    try:
        dirPath = os.path.dirname(filePath)
        if dirPath and not os.path.isdir(dirPath):
            os.makedirs(dirPath, exist_ok = True)
        with open(filePath, "w", encoding = "utf-8") as hFile:
            json.dump(state, hFile, ensure_ascii = False, indent = 2)
        return True
    except Exception:
        return False


def recordRun(jobName, ok, ymdhms = "", note = ""):
    """记录一次运行(成功或失败); 成功时同步刷新 lastSuccessYMDHMS。
       出参: 该任务的最新心跳 dict。"""
    jobName = _toStr(jobName)
    if not jobName:
        return {}
    stamp = _toStr(ymdhms) or misc.getTime()
    state = loadState()
    item = state.get(jobName) if isinstance(state.get(jobName), dict) else {}
    item["lastRunYMDHMS"] = stamp
    item["lastResult"] = "OK" if ok else "FAIL"
    item["lastNote"] = _toStr(note)[:200]
    if ok:
        item["lastSuccessYMDHMS"] = stamp
    state[jobName] = item
    saveState(state)
    return item


def recordSuccess(jobName, ymdhms = "", note = ""):
    """记录一次成功运行"""
    return recordRun(jobName, True, ymdhms = ymdhms, note = note)


def recordFail(jobName, ymdhms = "", note = ""):
    """记录一次失败运行(不刷新 lastSuccessYMDHMS)"""
    return recordRun(jobName, False, ymdhms = ymdhms, note = note)


def getLastSuccess(jobName):
    """取某任务最后成功时间(无记录 -> "")"""
    state = loadState()
    item = state.get(_toStr(jobName))
    if isinstance(item, dict):
        return _toStr(item.get("lastSuccessYMDHMS"))
    return ""


def readHeartbeats():
    """返回全部心跳(供每日巡检报告)"""
    return loadState()


if __name__ == "__main__":
    pass
    #本地自测(不连库/不联网): 写读一次心跳(落 code/data/monitor/)
    recordSuccess(JOB_ARCHIVE, note = "self-test")
    print("heartbeat file:", getStateFilePath())
    print("lastSuccess:", getLastSuccess(JOB_ARCHIVE))
