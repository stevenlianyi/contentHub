#! /usr/bin/env python3
#encoding: utf-8:

#Filename: opsSettings.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 运维配置(SP4c · Phase 3 归档清理 + 监控告警)。
#
#定位(见 code/src/plan.md §4「新增约定」):
#  - 归档清理(schedule/archive.py)与监控告警(chmonitor/)的**全部可调项集中于此**:
#    审计保留期 / 分批大小 / 导出格式 / 破坏性操作确认开关 / 七项监控阈值 / 告警通道;
#  - ★ 红线: 阈值、保留期、批大小**一律可配**, 禁止在业务代码里散落硬编码;
#  - 取值优先级: 环境变量 > 本模块默认常量; 运行期读取一律走下方 get*()(便于单测覆盖与热调);
#  - 本模块属「配置层」, 只被 schedule/ 与 chmonitor/ 读取, 不反向依赖任何业务模块。

_VERSION="20260919"


import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

from config import basicSettings as settings


#项目根目录(code/), 与 basicSettings 保持一致
CODE_DIR = settings._CODE_DIR


#===== 通用取值工具 begin =====

def _toStr(value, default = ""):
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    return str(value).strip() or default


def _toInt(value, default = 0):
    try:
        return int(float(str(value).strip()))
    except Exception:
        return default


def _toFloat(value, default = 0.0):
    try:
        return float(str(value).strip())
    except Exception:
        return default


def _toBool(value, default = False):
    text = _toStr(value, "").lower()
    if text in ("1", "true", "yes", "y", "on"):
        return True
    if text in ("0", "false", "no", "n", "off"):
        return False
    return default


def _envInt(key, default):
    return _toInt(os.environ.get(key), default)


def _envFloat(key, default):
    return _toFloat(os.environ.get(key), default)


def _envStr(key, default):
    return _toStr(os.environ.get(key), default)

#===== 通用取值工具 end =====


#===== 归档清理配置(schedule/archive.py) begin =====

#审计日志保留期(月): regYMDHMS 早于「现在 - 保留期」的记录才进入归档(默认 24 个月, 主计划 3.4.6)
ARCHIVE_AUDIT_RETAIN_MONTHS_ENV_KEY = "CH_ARCHIVE_AUDIT_RETAIN_MONTHS"
DEFAULT_ARCHIVE_AUDIT_RETAIN_MONTHS = 24

#分批大小(每批导出+删除的记录数; 默认 5000/批, 避免长事务; 主计划 3.4.6)
ARCHIVE_BATCH_SIZE_ENV_KEY = "CH_ARCHIVE_BATCH_SIZE"
DEFAULT_ARCHIVE_BATCH_SIZE = 5000

#单次运行最大批次数(护栏: 防止误配后无限循环; 0 = 不限制)
ARCHIVE_MAX_BATCH_ENV_KEY = "CH_ARCHIVE_MAX_BATCH"
DEFAULT_ARCHIVE_MAX_BATCH = 0

#导出格式: json.gz(默认) 或 csv
ARCHIVE_EXPORT_FORMAT_ENV_KEY = "CH_ARCHIVE_EXPORT_FORMAT"
DEFAULT_ARCHIVE_EXPORT_FORMAT = "json.gz"
ARCHIVE_EXPORT_FORMAT_LIST = ["json.gz", "csv"]

#★ 破坏性操作默认 dry-run: 未显式确认一律只打印「将删除/将导出」清单, 不做导出/不做删除
#  真删必须显式参数 --execute 或环境变量 CH_ARCHIVE_EXECUTE=1(主计划 8.6 红线: 生成器无 migration, 误删不可逆)
ARCHIVE_EXECUTE_ENV_KEY = "CH_ARCHIVE_EXECUTE"
DEFAULT_ARCHIVE_EXECUTE = False

#归档导出对象名前缀(经 common/fileStorageCommon.py 上传)
ARCHIVE_EXPORT_OBJECT_PREFIX = _envStr("CH_ARCHIVE_EXPORT_OBJECT_PREFIX", "archive/audit/")

#产物过期清理: 单次拉取 READY 产物的上限(护栏; 过期产物按 recID 升序=最旧优先)
ARCHIVE_ARTIFACT_SCAN_LIMIT_ENV_KEY = "CH_ARCHIVE_ARTIFACT_SCAN_LIMIT"
DEFAULT_ARCHIVE_ARTIFACT_SCAN_LIMIT = 20000

#运维动作的操作者标识(写 ch_audit_log.actor)
OPS_ACTOR_LOGINID = _envStr("CH_OPS_ACTOR_LOGINID", "charchive")

#Redis 锁(可降级)
ARCHIVE_LOCK_LEVEL1 = "contenthub"
ARCHIVE_LOCK_NAME = "archivejob"
DEFAULT_ARCHIVE_LOCK_TTL_SECONDS = 1800


def getAuditRetainMonths():
    """审计保留期(月); 非法/未配置回落默认值"""
    months = _envInt(ARCHIVE_AUDIT_RETAIN_MONTHS_ENV_KEY, DEFAULT_ARCHIVE_AUDIT_RETAIN_MONTHS)
    return months if months > 0 else DEFAULT_ARCHIVE_AUDIT_RETAIN_MONTHS


def getBatchSize():
    """分批大小; 至少 1"""
    size = _envInt(ARCHIVE_BATCH_SIZE_ENV_KEY, DEFAULT_ARCHIVE_BATCH_SIZE)
    return size if size > 0 else DEFAULT_ARCHIVE_BATCH_SIZE


def getMaxBatchCount():
    """单次运行最大批次数; 0 = 不限制"""
    count = _envInt(ARCHIVE_MAX_BATCH_ENV_KEY, DEFAULT_ARCHIVE_MAX_BATCH)
    return count if count > 0 else 0


def getExportFormat():
    """导出格式; 非法值回落默认 json.gz"""
    fmt = _envStr(ARCHIVE_EXPORT_FORMAT_ENV_KEY, DEFAULT_ARCHIVE_EXPORT_FORMAT).lower()
    return fmt if fmt in ARCHIVE_EXPORT_FORMAT_LIST else DEFAULT_ARCHIVE_EXPORT_FORMAT


def getArtifactScanLimit():
    """产物扫描上限; 至少 1"""
    limitNum = _envInt(ARCHIVE_ARTIFACT_SCAN_LIMIT_ENV_KEY, DEFAULT_ARCHIVE_ARTIFACT_SCAN_LIMIT)
    return limitNum if limitNum > 0 else DEFAULT_ARCHIVE_ARTIFACT_SCAN_LIMIT


def isExecuteEnabled():
    """★ 是否已显式确认执行破坏性操作(真删)。默认 False(=dry-run)"""
    return _toBool(os.environ.get(ARCHIVE_EXECUTE_ENV_KEY), DEFAULT_ARCHIVE_EXECUTE)

#===== 归档清理配置 end =====


#===== 监控告警配置(chmonitor/) begin =====

#渲染失败率: 15 分钟窗口内 jobStatus=FAILED 占比 > 10% 告警(主计划 8.7)
MONITOR_RENDER_WINDOW_MINUTES = _envInt("CH_MONITOR_RENDER_WINDOW_MINUTES", 15)
MONITOR_RENDER_FAILURE_RATE = _envFloat("CH_MONITOR_RENDER_FAILURE_RATE", 0.10)

#投递成功率: 单日 success='0' 占比 > 5% 或连续 3 次失败告警(主计划 8.7)
MONITOR_PUBLISH_WINDOW_HOURS = _envInt("CH_MONITOR_PUBLISH_WINDOW_HOURS", 24)
MONITOR_PUBLISH_FAILURE_RATE = _envFloat("CH_MONITOR_PUBLISH_FAILURE_RATE", 0.05)
MONITOR_PUBLISH_CONSECUTIVE_FAIL = _envInt("CH_MONITOR_PUBLISH_CONSECUTIVE_FAIL", 3)

#渲染队列积压: PENDING 最老任务等待 > 15 分钟告警(主计划 8.7)
MONITOR_QUEUE_BACKLOG_MINUTES = _envFloat("CH_MONITOR_QUEUE_BACKLOG_MINUTES", 15.0)

#存储用量: 使用率 > 80% 告警(主计划 8.7)
MONITOR_STORAGE_USAGE_RATE = _envFloat("CH_MONITOR_STORAGE_USAGE_RATE", 0.80)

#定时任务: 最后成功时间超过 1.5 个周期告警(主计划 8.7)
MONITOR_SCHEDULE_GRACE_FACTOR = _envFloat("CH_MONITOR_SCHEDULE_GRACE_FACTOR", 1.5)

#审计日志量: 日增量环比突增 > 3 倍告警(主计划 8.7)
MONITOR_AUDIT_GROWTH_FACTOR = _envFloat("CH_MONITOR_AUDIT_GROWTH_FACTOR", 3.0)

#定时任务周期(秒)表: archive / credentialCheck / dailyCheck(可配; 用于「最后成功时间」判定)
MONITOR_SCHEDULE_PERIOD_TABLE = {
    "archive": _envInt("CH_MONITOR_PERIOD_ARCHIVE_SECONDS", 86400),
    "credentialCheck": _envInt("CH_MONITOR_PERIOD_CREDENTIAL_SECONDS", 3600),
    "dailyCheck": _envInt("CH_MONITOR_PERIOD_DAILYCHECK_SECONDS", 86400),
}

#查询上限(监控取数; 避免大表全量拉取)
MONITOR_QUERY_LIMIT = _envInt("CH_MONITOR_QUERY_LIMIT", 20000)

#★ 告警通道: 默认 log(仅落盘); email / wecom 为**占位实现**, 本轮不发任何网络请求
MONITOR_ALERT_CHANNEL = _envStr("CH_MONITOR_ALERT_CHANNEL", "log")

#监控报告与心跳落点(code/data/monitor/)
MONITOR_DATA_DIR = _envStr("CH_MONITOR_DATA_DIR", os.path.join(CODE_DIR, "data", "monitor"))

#本地存储物理根目录(供「存储用量」指标读取磁盘使用率; 由 basicSettings 统一解析, 不在此重复配置)
LOCAL_FILE_SERVER_STORAGE_DIR = _toStr(getattr(settings, "LOCAL_FILE_SERVER_STORAGE_DIR", ""))

#监控数据目录下的文件名
MONITOR_HEARTBEAT_FILE = "heartbeat.json"
MONITOR_REPORT_PREFIX = "daily_check_"


#★ 七项指标阈值表(单一事实来源; 供静态验收 S28 断言「阈值可配」)
MONITOR_METRIC_TABLE = {
    "render_failure_rate": {
        "title": "渲染失败率", "threshold": MONITOR_RENDER_FAILURE_RATE,
        "windowMinutes": MONITOR_RENDER_WINDOW_MINUTES, "level": "ERROR",
        "suggest": "检查 ch_render_job 中 FAILED 任务的 errMsg; 必要时重试入队并对失败原因归类",
    },
    "publish_success_rate": {
        "title": "投递成功率", "threshold": MONITOR_PUBLISH_FAILURE_RATE,
        "consecutiveFailLimit": MONITOR_PUBLISH_CONSECUTIVE_FAIL, "level": "ERROR",
        "suggest": "检查 ch_publish_record 失败原因与平台 errcode; 核对凭据有效性与平台限流",
    },
    "render_queue_backlog": {
        "title": "渲染队列积压", "thresholdMinutes": MONITOR_QUEUE_BACKLOG_MINUTES, "level": "WARN",
        "suggest": "确认 schedule/renderWorker.py 是否常驻; 检查截图浏览器与 Playwright 是否可用",
    },
    "credential_health": {
        "title": "凭据健康", "expiringLevel": "WARN", "invalidLevel": "ERROR",
        "suggest": "INVALID 凭据立即更新; EXPIRING 在到期前更换(CH_CREDENTIAL_EXPIRE_WARN_DAYS 内)",
    },
    "storage_usage": {
        "title": "存储用量", "threshold": MONITOR_STORAGE_USAGE_RATE, "level": "WARN",
        "suggest": "清理过期产物/归档对象, 或扩容对象存储/磁盘; 检查 ch_artifact.expireYMDHMS 清理是否按期执行",
    },
    "scheduler_last_success": {
        "title": "定时任务最后成功时间", "graceFactor": MONITOR_SCHEDULE_GRACE_FACTOR, "level": "WARN",
        "suggest": "检查 schedule/archive.py 与 schedule/credentialCheck.py 的调度与日志(心跳过期)",
    },
    "audit_daily_growth": {
        "title": "审计日增量", "factor": MONITOR_AUDIT_GROWTH_FACTOR, "level": "WARN",
        "suggest": "排查异常高频调用/重试风暴; 核对 ch_audit_log 来源(actor/action 分布)",
    },
}


def getMonitorAlertChannel():
    """告警通道名; 空值回落 log"""
    return _envStr("CH_MONITOR_ALERT_CHANNEL", MONITOR_ALERT_CHANNEL) or "log"


def getMonitorDataDir():
    """监控数据目录(报告/心跳); 不存在时由调用方创建"""
    return _envStr("CH_MONITOR_DATA_DIR", MONITOR_DATA_DIR) or MONITOR_DATA_DIR


def getMetricThreshold(metricName, key = "threshold", default = None):
    """从阈值表取某项指标的可配阈值"""
    item = MONITOR_METRIC_TABLE.get(_toStr(metricName, ""), {})
    value = item.get(key, default)
    return default if value is None else value

#===== 监控告警配置 end =====


if __name__ == "__main__":
    print("CODE_DIR", CODE_DIR)
    print("retainMonths", getAuditRetainMonths(), "batchSize", getBatchSize(), "format", getExportFormat())
    print("executeEnabled", isExecuteEnabled())
    print("MONITOR_METRIC_TABLE keys", sorted(MONITOR_METRIC_TABLE.keys()))
    print("alertChannel", getMonitorAlertChannel(), "dataDir", getMonitorDataDir())
