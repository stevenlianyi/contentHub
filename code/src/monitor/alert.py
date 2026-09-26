#! /usr/bin/env python3
#encoding: utf-8:

#Filename: alert.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 运维告警汇总(由 museum/code/src/monitor/alert.py 迁移并改造为 contentHub 口径)。

#★ 迁移改造说明:
#  - museum 原规则依赖 museum 专属配置与 museum 业务表(mu_ 前缀的采集/翻译运行日志表), 在 contentHub 不可用;
#    本版**改为复用 contentHub 自身的七项指标**(`chmonitor.monitorService.collectAllMetrics`)
#    并归集 WARN / ERROR, 保留「规则清单 + run_alert 汇总 + 分级日志」的可复用结构;
#  - ★ 触达方式: 日志落盘 + `chmonitor.alertChannel` 可插拔通道(默认 log; 邮件/企微为占位, **不发网络请求**);
#  - ★ 数据来源: 只经 `chmonitor`(其内部只经 common/mysqlCommon 只读), 本文件不做任何业务写入、不发任何对外网络请求。
#
#★ 分层契约: 只依赖 chmonitor/ 与 common/ 与 config/; **不 import main/subfunc**。

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

import traceback

#global defintion/common var etc.
from common import globalDefinition as comGD

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#指标判定(阈值来自 config/opsSettings; 本层不做阈值判定, 只归集)
from chmonitor import metrics as chMetrics


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    try:
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None


#告警级别(与 chmonitor/metrics 一致: INFO / WARN / ERROR)
LEVEL_INFO = chMetrics.LEVEL_INFO
LEVEL_WARN = chMetrics.LEVEL_WARN
LEVEL_ERROR = chMetrics.LEVEL_ERROR

#★ 只把 WARN / ERROR 作为告警项(INFO 仅记录, 不告警)
ALERT_LEVEL_LIST = [LEVEL_WARN, LEVEL_ERROR]

#规则清单(每项为一个 contentHub 监控指标; 结构保留 museum 「规则清单 + 汇总」范式)
ALERT_RULE_METRIC_LIST = list(chMetrics.METRIC_NAME_LIST)


def _logInfo(message):
    if _LOG:
        _LOG.info(f"PID:{_processorPID}, {message}")


def _logWarn(message):
    if _LOG:
        _LOG.warning(f"W: PID:{_processorPID}, {message}")


def _logError(message):
    if _LOG:
        _LOG.error(f"PID:{_processorPID}, {message}")


def _buildMessage(metricResult):
    return (f"{metricResult.get('title')}({metricResult.get('metricName')}): "
            f"当前值={metricResult.get('currentValue')}, 阈值={metricResult.get('threshold')}, "
            f"建议={metricResult.get('suggest')}")


#规则实现 begin(逐项指标 -> 告警项)

def rule_from_metric(metricResult):
    """单个指标判定结果 -> 告警项(dict); 非 WARN/ERROR 返回 None"""
    if not isinstance(metricResult, dict):
        return None
    level = str(metricResult.get("level") or "").upper()
    if level not in ALERT_LEVEL_LIST:
        return None
    return {"level": level, "rule": metricResult.get("metricName"),
            "message": _buildMessage(metricResult), "row": metricResult}


def collect_alerts():
    """采集七项指标并归集 WARN/ERROR 告警(取数不可用时降级为空列表并记日志)"""
    alertList = []
    metricResults = []
    try:
        #懒加载: monitorService 经 common/mysqlCommon 取数, 无 DB 时不应阻断本模块导入
        from chmonitor import monitorService
        metricResults = monitorService.collectAllMetrics()
    except Exception as e:
        _logError(f"collect_alerts 取数失败(降级): {e}, {traceback.format_exc()}")
        return alertList

    for metricResult in metricResults:
        alert = rule_from_metric(metricResult)
        if alert:
            alertList.append(alert)
    return alertList

#规则实现 end


def run_alert(verbose = False):
    """跑全部规则, 触发即记 ERROR/WARNING 日志并经 chmonitor 告警通道触达; 返回告警列表(与 museum 同名入口)"""
    alertList = collect_alerts()

    for alert in alertList:
        message = f"[{alert.get('level')}][{alert.get('rule')}] {alert.get('message')}"
        if alert.get("level") == LEVEL_ERROR:
            _logError(message)
        else:
            _logWarn(message)
        #★ 触达: 经 chmonitor 可插拔告警通道(默认 log; 占位通道不发网络请求); 失败不影响主流程
        try:
            from chmonitor import alertChannel
            alertChannel.sendAlert({"metricName": alert.get("rule"),
                                    "title": (alert.get("row") or {}).get("title") or alert.get("rule"),
                                    "level": alert.get("level"), "text": message})
        except Exception as e:
            _logWarn(f"告警通道触达失败(忽略): {e}")

    _logInfo(f"run_alert done, triggered:{len(alertList)}, metrics:{len(ALERT_RULE_METRIC_LIST)}")
    if verbose:
        print(f"run_alert done, triggered:{len(alertList)}")
        for alert in alertList:
            print(f"  [{alert.get('level')}] {alert.get('rule')}: {alert.get('message')}")
    return alertList


if __name__ == "__main__":
    run_alert(verbose = True)
