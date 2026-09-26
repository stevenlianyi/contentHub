#! /usr/bin/env python3
#encoding: utf-8:

#Filename: metrics.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 监控指标判定(SP4c · P3-8 / 主计划 8.7 监控告警阈值表)。

#职责(全部为**纯函数**, 便于离线与边界值验证):
#  对主计划 8.7 的七项指标给出统一判定结果, 每条输出:
#    指标名(metricName/title) / 当前值(currentValue) / 阈值(threshold) /
#    级别(level ∈ {INFO, WARN, ERROR}) / 建议动作(suggest)。
#
#★ 阈值一律来自 config/opsSettings.py(禁止硬编码); 亦可由调用方显式传参覆盖(便于单测边界)。
#★ 边界口径(全部为「恰在阈值不告警, 越界才告警」, 便于静态/冒烟锁定):
#   - 渲染失败率: rate > 阈值 -> ERROR;
#   - 投递失败率: rate > 阈值 或 连续失败 >= 阈值 -> ERROR;
#   - 队列积压:   最老等待 > 阈值分钟 -> WARN;
#   - 凭据健康:   INVALID > 0 -> ERROR; 否则 EXPIRING > 0 -> WARN;
#   - 存储用量:   使用率 > 阈值 -> WARN;
#   - 定时任务:   距最后成功 > 1.5 个周期 -> WARN(无记录 -> WARN, 视为未知);
#   - 审计日增量: 今日 > 环比倍数 * 昨日 -> WARN。

_VERSION="20260919"


import datetime
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


#===== 级别与指标名 begin =====

LEVEL_INFO = "INFO"
LEVEL_WARN = "WARN"
LEVEL_ERROR = "ERROR"
LEVEL_LIST = [LEVEL_INFO, LEVEL_WARN, LEVEL_ERROR]
LEVEL_ORDER = {LEVEL_INFO: 0, LEVEL_WARN: 1, LEVEL_ERROR: 2}

METRIC_RENDER_FAILURE_RATE = "render_failure_rate"
METRIC_PUBLISH_SUCCESS_RATE = "publish_success_rate"
METRIC_RENDER_QUEUE_BACKLOG = "render_queue_backlog"
METRIC_CREDENTIAL_HEALTH = "credential_health"
METRIC_STORAGE_USAGE = "storage_usage"
METRIC_SCHEDULER_LAST_SUCCESS = "scheduler_last_success"
METRIC_AUDIT_DAILY_GROWTH = "audit_daily_growth"

METRIC_NAME_LIST = [
    METRIC_RENDER_FAILURE_RATE, METRIC_PUBLISH_SUCCESS_RATE, METRIC_RENDER_QUEUE_BACKLOG,
    METRIC_CREDENTIAL_HEALTH, METRIC_STORAGE_USAGE, METRIC_SCHEDULER_LAST_SUCCESS,
    METRIC_AUDIT_DAILY_GROWTH,
]

#===== 级别与指标名 end =====


#===== 通用小工具 begin =====

def _toStr(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _toInt(value, default = 0):
    try:
        return int(float(_toStr(value)))
    except Exception:
        return default


def _toFloat(value, default = 0.0):
    try:
        return float(_toStr(value))
    except Exception:
        return default


def parseYMDHMS(text):
    """14 位 YYYYMMDDHHMMSS -> datetime; 解析失败返回 None"""
    text = _toStr(text)
    if len(text) < 14:
        return None
    try:
        return datetime.datetime.strptime(text[:14], "%Y%m%d%H%M%S")
    except Exception:
        return None


def nowYMDHMS():
    return datetime.datetime.now().strftime("%Y%m%d%H%M%S")


def _metricTitle(metricName):
    return _toStr(opsSettings.MONITOR_METRIC_TABLE.get(metricName, {}).get("title")) or metricName


def _suggest(metricName, default = ""):
    return _toStr(opsSettings.MONITOR_METRIC_TABLE.get(metricName, {}).get("suggest")) or default


def buildMetricResult(metricName, currentValue, threshold, level, suggest = "", **extra):
    """统一指标判定结果结构(供告警通道与报告消费)"""
    level = _toStr(level).upper()
    if level not in LEVEL_LIST:
        level = LEVEL_INFO
    result = {
        "metricName": _toStr(metricName),
        "title": _metricTitle(metricName),
        "currentValue": currentValue,
        "threshold": threshold,
        "level": level,
        "suggest": _toStr(suggest) or _suggest(metricName),
    }
    result.update(extra or {})
    return result


def worseLevel(levelA, levelB):
    """取更严重的级别(报告汇总用)"""
    a = _toStr(levelA).upper()
    b = _toStr(levelB).upper()
    return a if LEVEL_ORDER.get(a, -1) >= LEVEL_ORDER.get(b, -1) else b


def formatRatio(value):
    """比率 -> 百分比字符串(仅展示用)"""
    return f"{_toFloat(value, 0.0) * 100:.2f}%"

#===== 通用小工具 end =====


#===== 七项指标判定(纯函数) begin =====

def evaluateRenderFailureRate(totalCount, failedCount, threshold = None, windowMinutes = None):
    """① 渲染失败率: 窗口内 FAILED 占比 > 阈值 -> ERROR。
       无样本(total=0) -> INFO(不误报)。"""
    metricName = METRIC_RENDER_FAILURE_RATE
    totalCount = max(0, _toInt(totalCount, 0))
    failedCount = max(0, _toInt(failedCount, 0))
    threshold = opsSettings.MONITOR_RENDER_FAILURE_RATE if threshold is None else _toFloat(threshold, 0.0)
    windowMinutes = opsSettings.MONITOR_RENDER_WINDOW_MINUTES if windowMinutes is None else _toInt(windowMinutes, 0)
    rate = (failedCount / totalCount) if totalCount > 0 else 0.0
    level = LEVEL_ERROR if (totalCount > 0 and rate > threshold) else LEVEL_INFO
    return buildMetricResult(metricName, round(rate, 6), threshold, level,
                             windowMinutes = windowMinutes, totalCount = totalCount,
                             failedCount = failedCount,
                             detailText = f"窗口 {windowMinutes} 分钟: {failedCount}/{totalCount} = {formatRatio(rate)}")


def evaluatePublishSuccessRate(totalCount, failedCount, consecutiveFailCount = 0,
                               threshold = None, consecutiveLimit = None):
    """② 投递成功率: 单日失败率 > 阈值 **或** 连续失败 >= 阈值 -> ERROR。"""
    metricName = METRIC_PUBLISH_SUCCESS_RATE
    totalCount = max(0, _toInt(totalCount, 0))
    failedCount = max(0, _toInt(failedCount, 0))
    consecutiveFailCount = max(0, _toInt(consecutiveFailCount, 0))
    threshold = opsSettings.MONITOR_PUBLISH_FAILURE_RATE if threshold is None else _toFloat(threshold, 0.0)
    consecutiveLimit = (opsSettings.MONITOR_PUBLISH_CONSECUTIVE_FAIL
                        if consecutiveLimit is None else _toInt(consecutiveLimit, 0))
    rate = (failedCount / totalCount) if totalCount > 0 else 0.0
    rateBreach = totalCount > 0 and rate > threshold
    consecutiveBreach = consecutiveFailCount >= consecutiveLimit > 0
    level = LEVEL_ERROR if (rateBreach or consecutiveBreach) else LEVEL_INFO
    return buildMetricResult(metricName, round(rate, 6), threshold, level,
                             consecutiveFailLimit = consecutiveLimit,
                             totalCount = totalCount, failedCount = failedCount,
                             consecutiveFailCount = consecutiveFailCount,
                             detailText = f"失败 {failedCount}/{totalCount} = {formatRatio(rate)}; "
                                          f"连续失败 {consecutiveFailCount} 次")


def evaluateQueueBacklog(pendingCount, oldestWaitMinutes, thresholdMinutes = None):
    """③ 渲染队列积压: PENDING 最老等待 > 阈值分钟 -> WARN。"""
    metricName = METRIC_RENDER_QUEUE_BACKLOG
    pendingCount = max(0, _toInt(pendingCount, 0))
    oldestWaitMinutes = max(0.0, _toFloat(oldestWaitMinutes, 0.0))
    thresholdMinutes = (opsSettings.MONITOR_QUEUE_BACKLOG_MINUTES
                        if thresholdMinutes is None else _toFloat(thresholdMinutes, 0.0))
    level = LEVEL_WARN if (pendingCount > 0 and oldestWaitMinutes > thresholdMinutes) else LEVEL_INFO
    return buildMetricResult(metricName, round(oldestWaitMinutes, 3), thresholdMinutes, level,
                             pendingCount = pendingCount,
                             detailText = f"PENDING {pendingCount} 个; 最老等待 {oldestWaitMinutes:.2f} 分钟")


def evaluateCredentialHealth(expiringCount, invalidCount):
    """④ 凭据健康: 出现 INVALID -> ERROR; 否则 EXPIRING -> WARN; 均无 -> INFO。"""
    metricName = METRIC_CREDENTIAL_HEALTH
    expiringCount = max(0, _toInt(expiringCount, 0))
    invalidCount = max(0, _toInt(invalidCount, 0))
    if invalidCount > 0:
        level = LEVEL_ERROR
    elif expiringCount > 0:
        level = LEVEL_WARN
    else:
        level = LEVEL_INFO
    return buildMetricResult(metricName, {"expiring": expiringCount, "invalid": invalidCount},
                             "EXPIRING/INVALID", level,
                             expiringCount = expiringCount, invalidCount = invalidCount,
                             detailText = f"EXPIRING {expiringCount} 个; INVALID {invalidCount} 个")


def evaluateStorageUsage(usageRatio, threshold = None):
    """⑤ 存储用量: 使用率 > 阈值 -> WARN; usageRatio 为 None -> INFO(未知, 不误报)。"""
    metricName = METRIC_STORAGE_USAGE
    threshold = opsSettings.MONITOR_STORAGE_USAGE_RATE if threshold is None else _toFloat(threshold, 0.0)
    if usageRatio is None:
        return buildMetricResult(metricName, None, threshold, LEVEL_INFO,
                                 detailText = "存储用量未知(未接入容量接口/目录不可读), 首期不误报")
    ratio = max(0.0, _toFloat(usageRatio, 0.0))
    level = LEVEL_WARN if ratio > threshold else LEVEL_INFO
    return buildMetricResult(metricName, round(ratio, 6), threshold, level,
                             detailText = f"使用率 {formatRatio(ratio)}")


def evaluateSchedulerLastSuccess(lastSuccessYMDHMS, periodSeconds, graceFactor = None, nowYMDHMS = ""):
    """⑥ 定时任务最后成功时间: 距最后成功 > graceFactor * 周期 -> WARN; 无记录 -> WARN(未知)。"""
    metricName = METRIC_SCHEDULER_LAST_SUCCESS
    periodSeconds = max(1, _toInt(periodSeconds, 0))
    graceFactor = (opsSettings.MONITOR_SCHEDULE_GRACE_FACTOR
                   if graceFactor is None else _toFloat(graceFactor, 0.0))
    thresholdSeconds = periodSeconds * graceFactor
    nowDt = parseYMDHMS(nowYMDHMS) or datetime.datetime.now()
    lastDt = parseYMDHMS(lastSuccessYMDHMS)
    if lastDt is None:
        return buildMetricResult(metricName, None, thresholdSeconds, LEVEL_WARN,
                                 periodSeconds = periodSeconds, graceFactor = graceFactor,
                                 detailText = "无最后成功时间记录(心跳缺失), 视为未知")
    elapsedSeconds = max(0.0, (nowDt - lastDt).total_seconds())
    level = LEVEL_WARN if elapsedSeconds > thresholdSeconds else LEVEL_INFO
    return buildMetricResult(metricName, round(elapsedSeconds, 3), round(thresholdSeconds, 3), level,
                             periodSeconds = periodSeconds, graceFactor = graceFactor,
                             lastSuccessYMDHMS = _toStr(lastSuccessYMDHMS),
                             detailText = f"距最后成功 {elapsedSeconds:.0f}s(阈值 {thresholdSeconds:.0f}s)")


def evaluateAuditDailyGrowth(todayCount, yesterdayCount, factor = None):
    """⑦ 审计日增量: 今日 > 环比倍数 * 昨日 -> WARN; 昨日为 0/未知 -> INFO(不误报)。"""
    metricName = METRIC_AUDIT_DAILY_GROWTH
    todayCount = max(0, _toInt(todayCount, 0))
    yesterdayCount = max(0, _toInt(yesterdayCount, 0))
    factor = opsSettings.MONITOR_AUDIT_GROWTH_FACTOR if factor is None else _toFloat(factor, 0.0)
    if yesterdayCount <= 0:
        level = LEVEL_INFO
    else:
        level = LEVEL_WARN if todayCount > factor * yesterdayCount else LEVEL_INFO
    ratio = (todayCount / yesterdayCount) if yesterdayCount > 0 else 0.0
    return buildMetricResult(metricName, todayCount, factor, level,
                             todayCount = todayCount, yesterdayCount = yesterdayCount,
                             growthRatio = round(ratio, 3),
                             detailText = f"今日 {todayCount} / 昨日 {yesterdayCount} = {ratio:.2f} 倍")


#指标名 -> 判定函数(供 monitorService 与静态验收统一引用)
METRIC_EVALUATOR_MAP = {
    METRIC_RENDER_FAILURE_RATE: evaluateRenderFailureRate,
    METRIC_PUBLISH_SUCCESS_RATE: evaluatePublishSuccessRate,
    METRIC_RENDER_QUEUE_BACKLOG: evaluateQueueBacklog,
    METRIC_CREDENTIAL_HEALTH: evaluateCredentialHealth,
    METRIC_STORAGE_USAGE: evaluateStorageUsage,
    METRIC_SCHEDULER_LAST_SUCCESS: evaluateSchedulerLastSuccess,
    METRIC_AUDIT_DAILY_GROWTH: evaluateAuditDailyGrowth,
}

#===== 七项指标判定 end =====


def summarizeMetricResults(metricResults):
    """汇总: 各级别计数 + 最严重级别 + 是否需告警(WARN/ERROR)"""
    summary = {"total": 0, "info": 0, "warn": 0, "error": 0, "worstLevel": LEVEL_INFO, "alertCount": 0}
    for item in metricResults or []:
        if not isinstance(item, dict):
            continue
        summary["total"] += 1
        level = _toStr(item.get("level")).upper()
        if level == LEVEL_ERROR:
            summary["error"] += 1
        elif level == LEVEL_WARN:
            summary["warn"] += 1
        else:
            summary["info"] += 1
        summary["worstLevel"] = worseLevel(summary["worstLevel"], level)
    summary["alertCount"] = summary["warn"] + summary["error"]
    return summary


if __name__ == "__main__":
    #本地自测(纯函数, 无依赖): 边界值样例
    print("render 0.10:", evaluateRenderFailureRate(100, 10)["level"])
    print("render 0.11:", evaluateRenderFailureRate(100, 11)["level"])
    print("publish 0.05:", evaluatePublishSuccessRate(100, 5)["level"])
    print("publish consecutive:", evaluatePublishSuccessRate(100, 0, 3)["level"])
    print("backlog 15:", evaluateQueueBacklog(3, 15)["level"])
    print("credential:", evaluateCredentialHealth(1, 0)["level"], evaluateCredentialHealth(0, 1)["level"])
    print("storage 0.80:", evaluateStorageUsage(0.80)["level"], "0.81:", evaluateStorageUsage(0.81)["level"])
    print("scheduler:", evaluateSchedulerLastSuccess("", 3600)["level"])
    print("audit ==3x:", evaluateAuditDailyGrowth(300, 100)["level"], ">3x:", evaluateAuditDailyGrowth(301, 100)["level"])
