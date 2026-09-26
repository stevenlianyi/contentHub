#! /usr/bin/env python3
#encoding: utf-8:

#Filename: monitorService.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 监控采集与每日汇总(SP4c · P3-8 / 主计划 8.7)。

#职责:
#  1) 采集七项指标的数据源(渲染任务 / 投递记录 / 账号健康 / 存储用量 / 定时任务心跳 / 审计日志量);
#  2) 交由 chmonitor/metrics.py 的**纯函数**做阈值判定(本层只取数, 不含阈值判定逻辑);
#  3) runDailyCheck: 汇总各指标 -> 生成报告(落 config/opsSettings.MONITOR_DATA_DIR) -> 经告警通道发送 WARN/ERROR。
#
#★ 降级口径(首期): 取数失败(本机无 MySQL / 目录不可读)一律**标记 degraded 并给 INFO**, 不误报、不崩溃;
#  不做看板/时序数据库, 不引入新中间件依赖, **不发起任何对外网络请求**。
#★ 数据来源: 只经 common/mysqlCommon.py(红线 R1), 只读; 本文件不写任何业务表。

_VERSION="20260919"


import datetime
import json
import os
import shutil
import sys
import traceback
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../code/src
if parentdir not in sys.path:
    sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #setdefaultencoding('utf-8')

from common import globalDefinition as comGD

from common import miscCommon as misc

#数据层唯一入口(红线 R1): 本文件只读
from common import mysqlCommon as comMysql

from config import opsSettings

from chmonitor import alertChannel

from chmonitor import heartbeat

from chmonitor import metrics


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    try:
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None


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


def _logInfo(message):
    if _LOG:
        _LOG.info(f"PID:{_processorPID}, {message}")


def _logWarn(message):
    if _LOG:
        _LOG.warning(f"W: PID:{_processorPID}, {message}")


def _degradedResult(metricName, note):
    """取数失败/不可用时的降级结果: level=INFO + degraded=1(不误报)"""
    return metrics.buildMetricResult(metricName, None, None, metrics.LEVEL_INFO,
                                     degraded = 1, detailText = note)


#===== 七项指标采集 begin =====

def collectRenderFailureRate(nowDt = None):
    """① 渲染失败率: 近 N 分钟 ch_render_job 中 FAILED 占比"""
    metricName = metrics.METRIC_RENDER_FAILURE_RATE
    nowDt = nowDt or datetime.datetime.now()
    windowMinutes = opsSettings.MONITOR_RENDER_WINDOW_MINUTES
    windowStart = (nowDt - datetime.timedelta(minutes = max(1, windowMinutes))).strftime("%Y%m%d%H%M%S")
    nowStr = nowDt.strftime("%Y%m%d%H%M%S")
    try:
        tableName = comMysql.tablename_convertor_ch_render_job()
        rows = comMysql.query_ch_render_job(tableName, beginYMDHMS = windowStart, endYMDHMS = nowStr,
                                            mode = "short", order = "create",
                                            limitNum = opsSettings.MONITOR_QUERY_LIMIT)
    except Exception as e:
        _logWarn(f"渲染失败率取数失败(降级): {e}")
        return _degradedResult(metricName, f"取数失败(降级): {str(e)[:120]}")
    rows = [row for row in (rows or []) if isinstance(row, dict)]
    failedCount = sum(1 for row in rows if _toStr(row.get("jobStatus")).upper() == "FAILED")
    return metrics.evaluateRenderFailureRate(len(rows), failedCount, windowMinutes = windowMinutes)


def collectPublishSuccessRate(nowDt = None):
    """② 投递成功率: 近 N 小时 ch_publish_record 失败率 + 连续失败次数"""
    metricName = metrics.METRIC_PUBLISH_SUCCESS_RATE
    nowDt = nowDt or datetime.datetime.now()
    windowStart = (nowDt - datetime.timedelta(hours = max(1, opsSettings.MONITOR_PUBLISH_WINDOW_HOURS))).strftime("%Y%m%d%H%M%S")
    nowStr = nowDt.strftime("%Y%m%d%H%M%S")
    try:
        tableName = comMysql.tablename_convertor_ch_publish_record()
        rows = comMysql.query_ch_publish_record(tableName, beginYMDHMS = windowStart, endYMDHMS = nowStr,
                                                mode = "short", order = "create",
                                                limitNum = opsSettings.MONITOR_QUERY_LIMIT)
    except Exception as e:
        _logWarn(f"投递成功率取数失败(降级): {e}")
        return _degradedResult(metricName, f"取数失败(降级): {str(e)[:120]}")
    rows = [row for row in (rows or []) if isinstance(row, dict)]
    failedCount = sum(1 for row in rows if _toStr(row.get("success")) == "0")
    consecutive = 0
    for row in reversed(rows):
        if _toStr(row.get("success")) == "0":
            consecutive += 1
        else:
            break
    return metrics.evaluatePublishSuccessRate(len(rows), failedCount, consecutive)


def collectQueueBacklog(nowDt = None):
    """③ 渲染队列积压: PENDING 数量与最老任务等待分钟"""
    metricName = metrics.METRIC_RENDER_QUEUE_BACKLOG
    nowDt = nowDt or datetime.datetime.now()
    try:
        tableName = comMysql.tablename_convertor_ch_render_job()
        rows = comMysql.query_ch_render_job(tableName, jobStatus = "PENDING", mode = "short",
                                            order = "create", limitNum = opsSettings.MONITOR_QUERY_LIMIT)
    except Exception as e:
        _logWarn(f"渲染队列积压取数失败(降级): {e}")
        return _degradedResult(metricName, f"取数失败(降级): {str(e)[:120]}")
    rows = [row for row in (rows or []) if isinstance(row, dict)]
    oldestWaitMinutes = 0.0
    if rows:
        oldestDt = metrics.parseYMDHMS(rows[0].get("regYMDHMS"))
        if oldestDt is not None:
            oldestWaitMinutes = max(0.0, (nowDt - oldestDt).total_seconds() / 60.0)
    return metrics.evaluateQueueBacklog(len(rows), oldestWaitMinutes)


def collectCredentialHealth():
    """④ 凭据健康: ch_account.healthStatus 中 EXPIRING / INVALID 数量"""
    metricName = metrics.METRIC_CREDENTIAL_HEALTH
    try:
        tableName = comMysql.tablename_convertor_ch_account()
        rows = comMysql.query_ch_account(tableName, mode = "short", order = "create",
                                         limitNum = opsSettings.MONITOR_QUERY_LIMIT)
    except Exception as e:
        _logWarn(f"凭据健康取数失败(降级): {e}")
        return _degradedResult(metricName, f"取数失败(降级): {str(e)[:120]}")
    rows = [row for row in (rows or []) if isinstance(row, dict)]
    expiringCount = sum(1 for row in rows if _toStr(row.get("healthStatus")).upper() == "EXPIRING")
    invalidCount = sum(1 for row in rows if _toStr(row.get("healthStatus")).upper() == "INVALID")
    return metrics.evaluateCredentialHealth(expiringCount, invalidCount)


def collectStorageUsage(nowDt = None):
    """⑤ 存储用量: 本地存储目录所在磁盘使用率(无统一容量接口时降级为 INFO)"""
    metricName = metrics.METRIC_STORAGE_USAGE
    storageDir = _toStr(opsSettings.LOCAL_FILE_SERVER_STORAGE_DIR)
    if not storageDir:
        return _degradedResult(metricName, "未配置存储目录, 用量未知")
    try:
        usage = shutil.disk_usage(storageDir)
        total = _toInt(usage.total, 0)
        ratio = (usage.used / total) if total > 0 else None
    except Exception as e:
        _logWarn(f"存储用量取数失败(降级): {e}")
        return _degradedResult(metricName, f"取数失败(降级): {str(e)[:120]}")
    result = metrics.evaluateStorageUsage(ratio)
    result["storageDir"] = storageDir
    return result


def collectSchedulerLastSuccess(nowDt = None):
    """⑥ 定时任务最后成功时间: 遍历周期表, 取最严重的一项作为该项指标"""
    metricName = metrics.METRIC_SCHEDULER_LAST_SUCCESS
    nowDt = nowDt or datetime.datetime.now()
    nowStr = nowDt.strftime("%Y%m%d%H%M%S")
    jobs = []
    worst = None
    state = heartbeat.readHeartbeats()
    for jobName, periodSeconds in opsSettings.MONITOR_SCHEDULE_PERIOD_TABLE.items():
        lastSuccess = ""
        item = state.get(jobName)
        if isinstance(item, dict):
            lastSuccess = _toStr(item.get("lastSuccessYMDHMS"))
        result = metrics.evaluateSchedulerLastSuccess(lastSuccess, periodSeconds, nowYMDHMS = nowStr)
        result["jobName"] = jobName
        jobs.append(result)
        if worst is None or metrics.LEVEL_ORDER.get(result.get("level"), 0) > metrics.LEVEL_ORDER.get(worst.get("level"), 0):
            worst = result
    if worst is None:
        return _degradedResult(metricName, "无定时任务周期配置")
    worst = dict(worst)
    worst["jobs"] = jobs
    worst["detailText"] = "; ".join(f"{job.get('jobName')}={job.get('level')}" for job in jobs)
    return worst


def collectAuditDailyGrowth(nowDt = None):
    """⑦ 审计日增量: 今日 vs 昨日 ch_audit_log 增量(环比)"""
    metricName = metrics.METRIC_AUDIT_DAILY_GROWTH
    nowDt = nowDt or datetime.datetime.now()
    todayStartDt = nowDt.replace(hour = 0, minute = 0, second = 0, microsecond = 0)
    yesterdayStartDt = todayStartDt - datetime.timedelta(days = 1)
    nowStr = nowDt.strftime("%Y%m%d%H%M%S")
    todayStart = todayStartDt.strftime("%Y%m%d%H%M%S")
    yesterdayStart = yesterdayStartDt.strftime("%Y%m%d%H%M%S")
    yesterdayEnd = (todayStartDt - datetime.timedelta(seconds = 1)).strftime("%Y%m%d%H%M%S")
    try:
        tableName = comMysql.tablename_convertor_ch_audit_log()
        todayRows = comMysql.query_ch_audit_log(tableName, beginYMDHMS = todayStart, endYMDHMS = nowStr,
                                               mode = "short", order = "create",
                                               limitNum = opsSettings.MONITOR_QUERY_LIMIT)
        yesterdayRows = comMysql.query_ch_audit_log(tableName, beginYMDHMS = yesterdayStart, endYMDHMS = yesterdayEnd,
                                                    mode = "short", order = "create",
                                                    limitNum = opsSettings.MONITOR_QUERY_LIMIT)
    except Exception as e:
        _logWarn(f"审计日增量取数失败(降级): {e}")
        return _degradedResult(metricName, f"取数失败(降级): {str(e)[:120]}")
    return metrics.evaluateAuditDailyGrowth(len(todayRows or []), len(yesterdayRows or []))


#采集器清单(顺序与主计划 8.7 一致)
METRIC_COLLECTOR_LIST = [
    metrics.METRIC_RENDER_FAILURE_RATE,
    metrics.METRIC_PUBLISH_SUCCESS_RATE,
    metrics.METRIC_RENDER_QUEUE_BACKLOG,
    metrics.METRIC_CREDENTIAL_HEALTH,
    metrics.METRIC_STORAGE_USAGE,
    metrics.METRIC_SCHEDULER_LAST_SUCCESS,
    metrics.METRIC_AUDIT_DAILY_GROWTH,
]

METRIC_COLLECTOR_MAP = {
    metrics.METRIC_RENDER_FAILURE_RATE: collectRenderFailureRate,
    metrics.METRIC_PUBLISH_SUCCESS_RATE: collectPublishSuccessRate,
    metrics.METRIC_RENDER_QUEUE_BACKLOG: collectQueueBacklog,
    metrics.METRIC_CREDENTIAL_HEALTH: collectCredentialHealth,
    metrics.METRIC_STORAGE_USAGE: collectStorageUsage,
    metrics.METRIC_SCHEDULER_LAST_SUCCESS: collectSchedulerLastSuccess,
    metrics.METRIC_AUDIT_DAILY_GROWTH: collectAuditDailyGrowth,
}

#===== 七项指标采集 end =====


def collectAllMetrics(dataSet = None):
    """采集全部七项指标(单项异常不影响其余项)"""
    nowDt = datetime.datetime.now()
    results = []
    for metricName in METRIC_COLLECTOR_LIST:
        collector = METRIC_COLLECTOR_MAP.get(metricName)
        try:
            results.append(collector(nowDt))
        except Exception as e:
            _logWarn(f"指标采集异常(降级) {metricName}: {e}, {traceback.format_exc()}")
            results.append(_degradedResult(metricName, f"采集异常(降级): {str(e)[:120]}"))
    return results


def buildReport(metricResults, alertResult = None):
    """组装每日巡检报告"""
    summary = metrics.summarizeMetricResults(metricResults)
    degraded = any(_toStr(item.get("degraded")) == "1" for item in metricResults or [] if isinstance(item, dict))
    return {
        "checkedAt": misc.getTime(),
        "summary": summary,
        "metrics": metricResults,
        "alerts": alertResult or {},
        "heartbeats": heartbeat.readHeartbeats(),
        "degraded": 1 if degraded else 0,
        "note": "首期降级口径: 日志告警 + 每日巡检; 不做看板/时序数据库; 告警通道为占位实现(不发网络请求)",
    }


def getReportDir():
    return opsSettings.getMonitorDataDir()


def writeReport(report):
    """写报告(JSON + 文本), 返回落盘路径; 失败返回 ""(不抛异常)"""
    reportDir = getReportDir()
    try:
        if not os.path.isdir(reportDir):
            os.makedirs(reportDir, exist_ok = True)
        stamp = _toStr((report or {}).get("checkedAt")) or misc.getTime()
        jsonPath = os.path.join(reportDir, f"{opsSettings.MONITOR_REPORT_PREFIX}{stamp}.json")
        with open(jsonPath, "w", encoding = "utf-8") as hFile:
            json.dump(report, hFile, ensure_ascii = False, indent = 2)
        return jsonPath
    except Exception as e:
        _logWarn(f"监控报告写入失败(忽略): {e}")
        return ""


def formatReportText(report):
    """报告文本(供控制台/日志查看)"""
    report = report if isinstance(report, dict) else {}
    lines = [f"contentHub 每日巡检报告 checkedAt={report.get('checkedAt')}"]
    summary = report.get("summary") or {}
    lines.append(f"汇总: total={summary.get('total')}, INFO={summary.get('info')}, "
                 f"WARN={summary.get('warn')}, ERROR={summary.get('error')}, worst={summary.get('worstLevel')}")
    for item in report.get("metrics") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"  [{item.get('level')}] {item.get('title')}({item.get('metricName')}): "
                     f"当前值={item.get('currentValue')}, 阈值={item.get('threshold')}, "
                     f"建议={item.get('suggest')}")
    alerts = report.get("alerts") or {}
    lines.append(f"告警通道: {alerts.get('channel')}, 请求={alerts.get('requested')}, 已发送={alerts.get('sent')}")
    return "\n".join(lines)


def runDailyCheck(dataSet = None):
    """每日巡检: 采集 -> 判定 -> 汇总 -> 发送告警(仅 WARN/ERROR) -> 报告落盘 -> 心跳。
       出参: report dict。"""
    dataSet = dataSet if isinstance(dataSet, dict) else {}
    metricResults = collectAllMetrics(dataSet)
    actor = _toStr(dataSet.get("actor")) or opsSettings.OPS_ACTOR_LOGINID
    alertResult = alertChannel.sendMetricAlerts(metricResults, actor = actor,
                                                channelName = _toStr(dataSet.get("alertChannel")))
    report = buildReport(metricResults, alertResult)
    reportPath = writeReport(report)
    report["reportPath"] = reportPath

    summary = report.get("summary") or {}
    _logInfo(f"每日巡检完成: worst={summary.get('worstLevel')}, WARN={summary.get('warn')}, "
             f"ERROR={summary.get('error')}, degraded={report.get('degraded')}, report={reportPath}")
    heartbeat.recordRun(heartbeat.JOB_DAILY_CHECK, True,
                        note = f"worst={summary.get('worstLevel')}, report={os.path.basename(reportPath) if reportPath else '-'}")
    return report


if __name__ == "__main__":
    pass
    #本地自测(不连库; 取数失败会走降级路径)
    _report = runDailyCheck({})
    print(formatReportText(_report))
