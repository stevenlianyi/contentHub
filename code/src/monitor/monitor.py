#! /usr/bin/env python3
#encoding: utf-8:

#Filename: monitor.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 运维监控 / 守护入口(由 museum/code/src/monitor/monitor.py 迁移并改造为 contentHub 口径)。

#★ 迁移改造说明(务必阅读):
#  1) 保留可复用逻辑: JSON 读写、时间戳、文件变化检测
#     (`readExistFileInfo` / `saveCurrFileInfo` / `chkFileChanges` / `funcMonitorFileChanges`) 与 getopt 命令行入口;
#  2) ★ 剥离(保持 contentHub「监控层零对外网络」红线): 网络请求(HTTP 探活)、套接字端口探测、
#     子进程调用与进程 kill —— 这些原语一律不再出现;
#     原 `funcMonitorProcess` / `funcKillProcess` / `funcMonitorService` 改为**显式不支持并记日志**(不静默、不误报);
#  3) contentHub 口径: 新增 `funcMonitorContentHub()`, 委托 `chmonitor.monitorService.runDailyCheck()`
#     运行七项指标(渲染失败率 / 投递成功率 / 队列积压 / 凭据健康 / 存储用量 / 定时任务最后成功 / 审计日增量);
#  4) 命令行: `python monitor/monitor.py [-k 清理(不支持, 仅记日志)] [-i 输入文件] [-d 调试] [-h 帮助]`。
#
#★ 分层契约: 只依赖 config/ 与 chmonitor/(懒加载); **不 import main/subfunc**。

_VERSION = "20260919"


import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../code/src
if parentdir not in sys.path:
    sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #setdefaultencoding('utf-8')

import getopt
import json
import time
import traceback

#global defintion/common var etc.
from common import globalDefinition as comGD

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#监控配置(工作目录 / 文件快照名 / 已置空的进程与服务配置)
from monitor import monitorConfig as comMC


_DISPLAY_IN_MAIN = False

_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    try:
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None


def _logInfo(message):
    if _LOG:
        _LOG.info(f"PID:{_processorPID}, {message}")


def _logWarn(message):
    if _LOG:
        _LOG.warning(f"W: PID:{_processorPID}, {message}")


def _logError(message):
    if _LOG:
        _LOG.error(f"PID:{_processorPID}, {message}")


#datetime function
def getTime():
    return time.strftime("%Y%m%d%H%M%S", time.localtime())


def getHumanTimeStamp():
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())


def time2HumandTimeStamp(t):
    x = time.localtime(t)
    return time.strftime('%Y-%m-%d %H:%M:%S', x)


# JSON/string function (移植自 museum, 逻辑保持不变)
def jsonDumps(data, ensure_ascii=True, indent = 0):
    if indent > 0:
        return json.dumps(data, separators=(',', ':'), ensure_ascii=ensure_ascii, indent = indent)
    else:
        return json.dumps(data, separators=(',', ':'), ensure_ascii=ensure_ascii)


def jsonLoads(data):
    return json.loads(data)


def loadJsonData(fileName, typeStyle="list"):
    result = None
    try:
        with open(fileName, "r", encoding = "utf-8") as hFile:
            if typeStyle == "list":
                lines = hFile.readlines()
                result = []
                for a in lines:
                    aSet = json.loads(a)
                    result.append(aSet)
            else:
                result = json.load(hFile)
    except Exception:
        pass

    return result


def saveJsonData(fileName, dataList, ensure_ascii=True, indent = 0):
    if dataList != None:
        typeStyle = type(dataList)
        with open(fileName, "w", encoding = 'utf-8') as hFile:
            if typeStyle == dict:
                strT = jsonDumps(dataList, ensure_ascii, indent) + "\n"
                hFile.write(strT)
            else:
                for a in dataList:
                    strT = jsonDumps(a, ensure_ascii) + "\n"
                    hFile.write(strT)
    pass


def this_abs_path(script_name):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), script_name))


def readProcessData(fileName):
    result = []
    try:
        filePath = os.path.join(comMC.monitorWorkDir, fileName)
        result = loadJsonData(filePath, typeStyle = "dict")
    except Exception:
        pass
    return result


#★ 已剥离: 原 museum 的 getRequest / postRequest(HTTP 探活) 与 monitor_port(套接字端口探测) 不再提供


#进程守护处理 begin(★ 已剥离: 子进程 / 进程 kill 属零网络红线外原语, 一律显式不支持并记日志)

PROCESS_MONITOR_DISABLED_NOTE = ("进程守护已按 contentHub 口径剥离(不再执行系统进程查询 / 子进程 / 进程 kill), "
                                 "请改用系统级进程守护(systemd / Windows 服务 / 计划任务)")


def funcKillProcess():
    """★ 已剥离: 原 museum 清理既有进程的能力不再提供(显式记日志, 不静默)"""
    _logInfo(f"funcKillProcess: {PROCESS_MONITOR_DISABLED_NOTE}")
    return 0


def funcMonitorProcess(processData):
    """★ 已剥离: 原 museum 进程存活检测与自动拉起不再提供(显式记日志, 不静默)"""
    count = len(processData or []) if isinstance(processData, (list, tuple)) else 0
    _logInfo(f"funcMonitorProcess: {PROCESS_MONITOR_DISABLED_NOTE}; 配置条数={count}")
    return 0

#进程守护处理 end


#服务探活处理 begin(★ 已剥离: HTTP 探活属对外网络请求)

def funcMonitorService():
    """★ 已剥离: 原 museum 服务探活(HTTP)不再提供(显式记日志, 不静默)"""
    _logInfo("funcMonitorService: 服务探活(HTTP)已按 contentHub 零网络红线剥离")
    return 0

#服务探活处理 end


#文件变化检测处理 begin(★ 纯 os.path 实现, 保留可复用逻辑)

existFileInfoData = {}
currFileInfoData = {}


def readExistFileInfo():
    global existFileInfoData
    monitorWorkDir = comMC.monitorWorkDir
    saveFileName = os.path.join(monitorWorkDir, comMC.monitorFileStatusFileName)
    currData = loadJsonData(saveFileName, typeStyle = "dict")
    if currData:
        existFileInfoData = currData


def saveCurrFileInfo():
    global currFileInfoData
    monitorWorkDir = comMC.monitorWorkDir
    saveFileName = os.path.join(monitorWorkDir, comMC.monitorFileStatusFileName)
    saveJsonData(saveFileName, currFileInfoData, indent = 2)


def chkFileChanges(fileName):
    """检测文件是否新增或(修改时间/大小)发生变化; 出参 bool"""
    global existFileInfoData
    global currFileInfoData
    fileChangedFlag = False
    if os.path.exists(fileName):
        currModifyTime = os.path.getmtime(fileName)
        currCreateTime = os.path.getctime(fileName)
        currSize = os.path.getsize(fileName)

        aSet = {}
        if isinstance(fileName, str):
            aSet["fileName"] = fileName
        else:
            aSet["fileName"] = fileName.decode()
        aSet["modifyTime"] = currModifyTime
        aSet["createTime"] = currCreateTime
        aSet["fileSize"] = currSize

        currFileInfoData[fileName] = aSet

        if fileName in existFileInfoData:
            existDataSet = existFileInfoData.get(fileName)
            existModifyTime = existDataSet.get("modifyTime")
            existFileSize = existDataSet.get("fileSize")
            if currModifyTime != existModifyTime or currSize != existFileSize:
                fileChangedFlag = True
        else:
            fileChangedFlag = True

    return fileChangedFlag


def funcMonitorFileChanges(processData):
    """检测配置中的文件是否变化; 变化时**仅告警提示**(自动重启涉及进程原语, 已剥离)"""
    global _DISPLAY_IN_MAIN

    if _DISPLAY_IN_MAIN:
        print()
        print(f"funcMonitorFileChanges : {getHumanTimeStamp()}")

    result = 0
    try:
        readExistFileInfo()

        dataList = processData
        for data in dataList:
            key = data["key"]
            fileName = data.get("file", None)
            fileNameList = data.get("fileList", [])
            if not fileNameList:
                fileNameList = []
            fileNameList.append(fileName)

            changedFlag = False
            for oneFile in fileNameList:
                if oneFile:
                    currChangedFlag = chkFileChanges(oneFile)
                    if currChangedFlag:
                        changedFlag = True
                    if _DISPLAY_IN_MAIN:
                        print(key, oneFile, currChangedFlag)

            if changedFlag:
                #★ 已剥离进程 kill: 变化时仅告警提示, 由部署流程负责重启
                _logWarn(f"{key}: {fileNameList} 已变化; 请按部署流程重启(自动 kill 已按口径剥离)")
                result += 1

        saveCurrFileInfo()
    except Exception as e:
        _logError(f"funcMonitorFileChanges 异常: {e}, {traceback.format_exc()}")

    return result

#文件变化检测处理 end


#contentHub 口径监控 begin(委托 chmonitor 七项指标; 懒加载避免耦合)

def funcMonitorContentHub():
    """运行 contentHub 七项监控指标(委托 chmonitor.monitorService.runDailyCheck)。
       出参: 1=已运行 / 0=不可用(记日志, 不抛异常)。"""
    try:
        from chmonitor import monitorService
        report = monitorService.runDailyCheck({})
        summary = (report or {}).get("summary") or {}
        _logInfo(f"funcMonitorContentHub: worst={summary.get('worstLevel')}, "
                 f"INFO={summary.get('info')}, WARN={summary.get('warn')}, ERROR={summary.get('error')}, "
                 f"degraded={(report or {}).get('degraded')}")
        return 1
    except Exception as e:
        _logError(f"funcMonitorContentHub 异常(监控不可用): {e}, {traceback.format_exc()}")
        return 0

#contentHub 口径监控 end


def main():
    global _DISPLAY_IN_MAIN
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hki:d", ["help", "kill", "input=", "debug"])
    except getopt.GetoptError:
        sys.exit()

    debugFlag = False
    killExistFlag = False
    inputFileName = ""

    for name, value in opts:
        if name in ("-h", "--help"):
            print("-k kill(已剥离, 仅记日志) -i input -d debug")
            sys.exit()
        elif name in ("-k", "--kill"):
            killExistFlag = True
        elif name in ("-i", "--input"):
            inputFileName = value
        elif name in ("-d", "--debug"):
            debugFlag = True
        else:
            pass

    if debugFlag:
        import pdb
        pdb.set_trace()

    _DISPLAY_IN_MAIN = True

    systemVersion = str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro)
    print(f"\nmonitor process: python version {systemVersion}, code version {_VERSION}  : {getHumanTimeStamp()} ")

    if inputFileName:
        processData = readProcessData(inputFileName)
        print(f"processData from :{inputFileName}")
    else:
        processData = comMC.processData

    if killExistFlag:
        funcKillProcess()
        time.sleep(2)

    #检测服务是否正常(★ 已剥离)
    funcMonitorService()

    #检测文件变化(★ 纯 os.path: 变化仅告警)
    funcMonitorFileChanges(processData)

    #监控进程(★ 已剥离)
    funcMonitorProcess(processData)

    #contentHub 口径: 委托 chmonitor 运行七项指标
    funcMonitorContentHub()

    print()


if __name__ == '__main__':
    main()
