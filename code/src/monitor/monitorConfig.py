#! /usr/bin/env python3
#encoding: utf-8:

#Filename: monitorConfig.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 运维监控配置(由 museum/code/src/monitor/monitorConfig.py 迁移并改造为 contentHub 口径)。

#★ 迁移改造说明:
#  - 去掉 museum 的 Linux 绝对路径(`/data/mindgram/...`), 监控工作目录改取 `config/opsSettings.getMonitorDataDir()`
#    (默认 `code/data/monitor/`, 可用 `CH_MONITOR_DATA_DIR` 覆盖);
#  - ★ 进程守护 / 端口探测 / 服务探活配置**保留结构但置空** —— 相关原语(子进程/套接字/网络请求)
#    已按 contentHub「监控层零对外网络」红线剥离, 保留字段供后续按需扩展(不引入新依赖);
#  - 阈值/周期等监控参数一律来自 `config/opsSettings.py`(禁止在本文件散落硬编码)。

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

from config import opsSettings


#工作模式标识(与 museum 一致; 保留供部署脚本读取)
currWorkMode = "monitor"

#监控工作目录: contentHub 运维数据目录(code/data/monitor/), 与 chmonitor 报告/心跳同源
monitorWorkDir = opsSettings.getMonitorDataDir()

#文件状态快照文件名(供文件变化检测落盘)
monitorFileStatusFileName = "tempMonitorFileName.json"


#进程守护配置(★ 已剥离: 原 museum 通过 ps / 子进程 / 进程 kill 实现, 属 contentHub 零网络红线外原语)
processData = []

#需清理的既有进程键(★ 已剥离)
existProcessKeys = []


#服务探活配置(★ 已剥离: 原 museum 通过 HTTP 探测各服务健康, 属对外网络请求)
serviceMonitorData = []


if __name__ == "__main__":
    print("currWorkMode", currWorkMode)
    print("monitorWorkDir", monitorWorkDir)
    print("processData", processData, "serviceMonitorData", serviceMonitorData)
