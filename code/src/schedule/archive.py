#! /usr/bin/env python3
#encoding: utf-8:

#Filename: archive.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 归档清理(SP4c · 主计划 5.5 P3-7 / 3.4.6 审计日志归档策略 / 6.4 R-23)。

#职责:
#  1) ch_audit_log 归档: 按保留期(默认 24 个月)筛选 regYMDHMS 早于阈值的记录;
#     ★ 分批(默认 5000/批)导出 + 分批 DELETE, 避免长事务; 每批留日志与审计;
#     ★ ★ 强顺序: **先导出(并经 common/fileStorageCommon.py 上传)成功, 才允许删除**;
#       导出失败一律中止本批并**不删除**(绝不先删后导)。
#  2) ch_artifact 过期清理: expireYMDHMS 到期 -> **先置 artifactStatus=EXPIRED, 再 delFile 删对象**;
#     对象删除失败 -> **不再变更状态(保持已置的 EXPIRED)并告警**(不静默)。
#  3) ★★ 破坏性操作**默认 dry-run**: 未显式确认(参数 --execute 或环境变量 CH_ARCHIVE_EXECUTE=1)
#     只打印「将删除/将导出」清单, 不做导出、不做删除;
#     主计划 8.6 红线: 生成器无 migration, 误删不可逆。
#
#★ 审计留痕: 归档/清理动作本身必须写 ch_audit_log(谁在何时删了什么) —— 经 processor/auditService.writeAudit。
#★ 数据/文件红线: 数据库只经 common/mysqlCommon.py; 文件只经 common/fileStorageCommon.py; 无裸 SQL、无厂商分支。
#★ Redis: 仅用于单实例运行锁, **可降级**(不可用 -> 进程内锁 + 告警, 不阻塞)。
#★ 分层契约: 本文件属调度层, 只依赖 processor/ 与 common/ 与 chmonitor/ 与 config/; **不 import main/subfunc**。
#★ 用法:
#   dry-run(默认, 只打印清单): cd code/src && python schedule/archive.py
#   单次执行(真删, 需显式确认): python schedule/archive.py --execute
#   环境变量确认:               set CH_ARCHIVE_EXECUTE=1 && python schedule/archive.py
#   自定义保留期/批大小:        python schedule/archive.py --retain-months 24 --batch-size 5000
#   只跑审计归档 / 只跑产物清理: --only audit | --only artifact

_VERSION="20260919"


import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../code/src
if parentdir not in sys.path:
    sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #setdefaultencoding('utf-8')

import argparse
import calendar
import csv
import datetime
import gzip
import json
import threading
import time
import traceback

#global defintion/common var etc.
from common import globalDefinition as comGD

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#数据层唯一入口(红线 R1): 本文件只读/删 ch_audit_log 与 ch_artifact
from common import mysqlCommon as comMysql

#文件门面(红线 R2): 归档导出上传 / 产物对象删除的唯一出口(本文件不出现任何厂商分支)
from common import fileStorageCommon as comFS

#Redis 唯一入口(红线: 只经 common/redisCommon.py; 本文件不直连)
from common import redisCommon as comDB

#配置(保留期/批大小/确认开关等; 全部可配)
from config import opsSettings

#审计留痕(归档/清理动作本身必须写 ch_audit_log)
from processor import auditService

#渲染任务状态机/产物状态常量(复用既有定义, 不造第二份)
from processor import renderService

#监控: 心跳(定时任务最后成功时间) + 告警通道(删除失败不静默)
from chmonitor import alertChannel

from chmonitor import heartbeat


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    try:
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None


#===== 常量 begin =====

#审计导出列(与 database/ch_audit_log.txt 字段一致; 固定列序, 便于归档回读)
AUDIT_EXPORT_COLUMN_LIST = [
    "recID", "actor", "source", "action", "targetType", "targetID", "payloadDigest",
    "result", "errMsg", "costMs", "ipAddr", "label", "memo",
    "regID", "regYMDHMS", "modifyID", "modifyYMDHMS", "delFlag",
]

#产物清理: 到期判定状态
ARTIFACT_STATUS_READY = renderService.ARTIFACT_STATUS_READY
ARTIFACT_STATUS_EXPIRED = renderService.ARTIFACT_STATUS_EXPIRED

#归档导出本地临时目录名(落 config/opsSettings.MONITOR_DATA_DIR 下)
ARCHIVE_WORK_DIRNAME = "archive_work"

#===== 常量 end =====


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


def _chunks(seq, size):
    """把序列切分为 size 大小的批次"""
    size = max(1, _toInt(size, 1))
    for index in range(0, len(seq), size):
        yield seq[index:index + size]


def _logInfo(message):
    if _LOG:
        _LOG.info(f"PID:{_processorPID}, {message}")


def _logWarn(message):
    if _LOG:
        _LOG.warning(f"W: PID:{_processorPID}, {message}")


def _logError(message):
    if _LOG:
        _LOG.error(f"PID:{_processorPID}, {message}")


def _alertOps(level, metricName, title, message, extra = None):
    """删除失败/异常**不静默**: 经可插拔告警通道输出(默认通道=日志落盘; 占位通道不发网络请求)"""
    alert = {"metricName": _toStr(metricName), "title": _toStr(title),
             "level": _toStr(level).upper() or "ERROR", "currentValue": "",
             "threshold": "", "suggest": "请人工核查归档/清理失败原因后重跑(默认 dry-run)",
             "text": _toStr(message)}
    if isinstance(extra, dict):
        alert.update(extra)
    try:
        return alertChannel.sendAlert(alert)
    except Exception as e:
        _logError(f"告警发送失败(忽略): {e}")
        return {}


def isDryRun(executeFlag = False):
    """★ 是否 dry-run: 未显式 --execute 且未设环境变量 CH_ARCHIVE_EXECUTE=1 -> True(默认)"""
    return not (bool(executeFlag) or opsSettings.isExecuteEnabled())


def getArchiveWorkDir():
    """归档导出本地临时目录"""
    workDir = os.path.join(opsSettings.getMonitorDataDir(), ARCHIVE_WORK_DIRNAME)
    if not os.path.isdir(workDir):
        try:
            os.makedirs(workDir, exist_ok = True)
        except Exception:
            return ""
    return workDir

#===== 通用小工具 end =====


#===== Redis 单实例运行锁(可降级) begin =====

_PROCESS_LOCK_STAMP = 0.0
_PROCESS_LOCK_FLAG = False
_PROCESS_LOCK_GUARD = threading.Lock()


def acquireArchiveLock(ttlSeconds = None):
    """获取归档运行锁: 返回 (locked, degraded)。
       进程内锁 + Redis SET NX EX; ★ Redis 不可用 -> degraded=True 并**放行**(降级不阻塞)。"""
    global _PROCESS_LOCK_STAMP, _PROCESS_LOCK_FLAG
    ttlSeconds = _toInt(ttlSeconds, opsSettings.DEFAULT_ARCHIVE_LOCK_TTL_SECONDS) or opsSettings.DEFAULT_ARCHIVE_LOCK_TTL_SECONDS
    now = time.time()
    with _PROCESS_LOCK_GUARD:
        if _PROCESS_LOCK_FLAG and now - _PROCESS_LOCK_STAMP <= int(ttlSeconds):
            return False, False
        _PROCESS_LOCK_FLAG = True
        _PROCESS_LOCK_STAMP = now

    degraded = False
    try:
        redisKey = comDB.genDBKey(opsSettings.ARCHIVE_LOCK_LEVEL1, opsSettings.ARCHIVE_LOCK_NAME, "runlock")
        locked = comDB.redisMainDB.set(redisKey, _processorPID, nx = True, ex = int(ttlSeconds))
        if not locked:
            with _PROCESS_LOCK_GUARD:
                _PROCESS_LOCK_FLAG = False
            return False, False
    except Exception as e:
        #★ 降级: Redis 不可用时不阻塞(单实例 + 进程内锁兜底), 记告警日志
        degraded = True
        _logWarn(f"归档运行锁降级为进程内锁(Redis 不可用), errMsg:{e}")
    return True, degraded


def releaseArchiveLock():
    """释放归档运行锁(幂等; Redis 异常不抛)"""
    global _PROCESS_LOCK_FLAG
    with _PROCESS_LOCK_GUARD:
        _PROCESS_LOCK_FLAG = False
    try:
        comDB.redisMainDB.delete(comDB.genDBKey(opsSettings.ARCHIVE_LOCK_LEVEL1,
                                                opsSettings.ARCHIVE_LOCK_NAME, "runlock"))
    except Exception as e:
        _logWarn(f"归档运行锁释放失败(忽略), errMsg:{e}")

#===== Redis 单实例运行锁 end =====


#===== 保留期计算 begin =====

def shiftMonths(dt, months):
    """按自然月回退 months 个月(日超出当月天数时取当月最后一天)"""
    months = _toInt(months, 0)
    totalMonths = dt.year * 12 + (dt.month - 1) - months
    year, monthIndex = divmod(totalMonths, 12)
    month = monthIndex + 1
    lastDay = calendar.monthrange(year, month)[1]
    return dt.replace(year = year, month = month, day = min(dt.day, lastDay))


def computeCutoffYMDHMS(retainMonths, nowDt = None):
    """保留期阈值: 「现在 - retainMonths 个月」的 14 位时间串; 早于此值的审计记录进入归档"""
    nowDt = nowDt or datetime.datetime.now()
    cutoff = shiftMonths(nowDt, max(1, _toInt(retainMonths, 1)))
    return cutoff.strftime("%Y%m%d%H%M%S")

#===== 保留期计算 end =====


#===== 审计日志归档: 导出(先导出) begin =====

def exportRowsToFile(rows, exportFormat, fileName):
    """把审计行导出为本地文件(CSV 或 JSON.gz); 出参 (localPath, errMsg)。"""
    exportFormat = _toStr(exportFormat).lower() or opsSettings.DEFAULT_ARCHIVE_EXPORT_FORMAT
    try:
        if exportFormat == "csv":
            with open(fileName, "w", encoding = "utf-8-sig", newline = "") as hFile:
                writer = csv.DictWriter(hFile, fieldnames = AUDIT_EXPORT_COLUMN_LIST, extrasaction = "ignore")
                writer.writeheader()
                for row in rows:
                    writer.writerow({key: row.get(key, "") for key in AUDIT_EXPORT_COLUMN_LIST})
        else:
            with gzip.open(fileName, "wt", encoding = "utf-8") as hFile:
                json.dump(rows, hFile, ensure_ascii = False, default = str)
    except Exception as e:
        _logError(f"审计导出写文件失败 fileName:{fileName}, errMsg:{e}, {traceback.format_exc()}")
        return "", f"导出写文件失败: {str(e)[:200]}"
    if not os.path.isfile(fileName):
        return "", "导出失败: 未产出文件"
    return fileName, ""


def exportAuditBatch(rows, batchIndex, cutoff, exportFormat, workDir):
    """★ 归档前导出单批: 落本地 -> 经 common/fileStorageCommon.py 上传 -> 返回 fileID。
       出参 (localPath, fileID, errMsg); **errMsg 非空表示导出失败, 调用方禁止删除本批**。"""
    stamp = misc.getTime()
    baseName = f"audit_archive_{cutoff}_{stamp}_batch{_toInt(batchIndex, 0):04d}"
    ext = ".csv" if _toStr(exportFormat).lower() == "csv" else ".json.gz"
    localPath = os.path.join(workDir or "", baseName + ext)
    localPath, writeErr = exportRowsToFile(rows, exportFormat, localPath)
    if writeErr:
        return "", "", writeErr

    objectName = f"{opsSettings.ARCHIVE_EXPORT_OBJECT_PREFIX}{baseName}{ext}"
    try:
        fileID = comFS.saveFile(localPath, objectName = objectName, privateFlag = True,
                                bucketCode = comFS.chDefaultBucketCode())
    except Exception as e:
        _logError(f"审计归档上传异常 objectName:{objectName}, errMsg:{e}, {traceback.format_exc()}")
        return localPath, "", f"归档导出上传异常: {str(e)[:200]}"
    if not fileID:
        return localPath, "", "归档导出上传失败(未取得 fileID)"
    return localPath, _toStr(fileID), ""

#===== 审计日志归档: 导出 end =====


#===== 审计日志归档: 分批导出 + 分批删除 begin =====

def queryAuditBatchForArchive(tableName, cutoff, batchSize):
    """取一批待归档审计记录(regYMDHMS <= cutoff, 按 recID 升序=最旧优先)"""
    return comMysql.query_ch_audit_log(tableName, endYMDHMS = cutoff, mode = "full",
                                       order = "create", limitNum = batchSize)


def archiveAuditLog(dryRun = True, retainMonths = None, batchSize = None,
                    maxBatch = None, exportFormat = None, workDir = None):
    """★ ch_audit_log 分批归档: 每批「先导出上传成功 -> 再删除 -> 再留审计」。
       dry-run: 只打印「将导出/将删除」清单(不导出、不删除)。
       出参: {"mode","cutoff","retainMonths","batchSize","format","batches",
             "exported","deleted","files","planRows","errMsg"}。"""
    retainMonths = opsSettings.getAuditRetainMonths() if retainMonths is None else _toInt(retainMonths, 0)
    batchSize = opsSettings.getBatchSize() if batchSize is None else _toInt(batchSize, 0)
    maxBatch = opsSettings.getMaxBatchCount() if maxBatch is None else _toInt(maxBatch, 0)
    exportFormat = opsSettings.getExportFormat() if not exportFormat else _toStr(exportFormat).lower()
    workDir = workDir or getArchiveWorkDir()

    cutoff = computeCutoffYMDHMS(retainMonths)
    tableName = comMysql.tablename_convertor_ch_audit_log()
    stats = {"mode": "dry-run" if dryRun else "execute", "cutoff": cutoff,
             "retainMonths": retainMonths, "batchSize": batchSize, "format": exportFormat,
             "batches": 0, "exported": 0, "deleted": 0, "files": [], "planRows": 0, "errMsg": ""}

    if dryRun:
        rows = queryAuditBatchForArchive(tableName, cutoff, batchSize)
        rows = [row for row in (rows or []) if isinstance(row, dict)]
        stats["planRows"] = len(rows)
        _logInfo(f"[DRY-RUN] 审计归档: 保留期 {retainMonths} 个月, cutoff={cutoff}, "
                 f"本批将导出/将删除 {len(rows)} 条(每批 {batchSize} 条, 循环执行)")
        for row in rows[:20]:
            _logInfo(f"[DRY-RUN] 将删除 ch_audit_log recID:{row.get('recID')}, "
                     f"action:{row.get('action')}, regYMDHMS:{row.get('regYMDHMS')}")
        if not rows:
            _logInfo("[DRY-RUN] 无待归档审计记录(expire 阈值内无数据)")
        return stats

    batchIndex = 0
    while True:
        if maxBatch and batchIndex >= maxBatch:
            _logWarn(f"审计归档达到最大批次数({maxBatch}), 本轮回合结束")
            break
        rows = queryAuditBatchForArchive(tableName, cutoff, batchSize)
        rows = [row for row in (rows or []) if isinstance(row, dict)]
        if not rows:
            break
        batchIndex += 1

        #★ 强顺序 ①: 先导出并上传成功(失败即中止, 绝不删除本批)
        localPath, fileID, exportErr = exportAuditBatch(rows, batchIndex, cutoff, exportFormat, workDir)
        if exportErr:
            stats["errMsg"] = f"第 {batchIndex} 批导出失败, 已中止且未删除: {exportErr}"
            _logError(stats["errMsg"])
            _alertOps("ERROR", auditService.ACTION_ARCHIVE_AUDIT_LOG, "审计归档导出失败",
                      stats["errMsg"], {"batchIndex": batchIndex, "rowCount": len(rows)})
            break
        stats["files"].append({"batch": batchIndex, "fileID": fileID, "localPath": localPath,
                               "rowCount": len(rows)})
        stats["exported"] += len(rows)

        #★ 强顺序 ②: 导出成功后才分批删除(逐条 delete, 避免长事务)
        deleted = 0
        for row in rows:
            recID = _toInt(row.get("recID"), 0)
            if recID <= 0:
                continue
            try:
                if _toInt(comMysql.delete_ch_audit_log(tableName, recID), 0) > 0:
                    deleted += 1
            except Exception as e:
                _logWarn(f"审计记录删除失败 recID:{recID}, errMsg:{e}")
        stats["deleted"] += deleted
        stats["batches"] = batchIndex

        #每批留日志与审计(谁在何时删了什么)
        auditService.writeAudit(opsSettings.OPS_ACTOR_LOGINID, auditService.ACTION_ARCHIVE_AUDIT_LOG,
                                targetType = auditService.TARGET_TYPE_AUDIT_LOG,
                                targetID = f"batch{batchIndex}",
                                payload = {"cutoff": cutoff, "batchIndex": batchIndex,
                                           "rowCount": len(rows), "deleted": deleted,
                                           "fileID": fileID, "format": exportFormat},
                                result = auditService.RESULT_OK,
                                memo = f"审计归档批次: 导出 {len(rows)} 条 / 删除 {deleted} 条")
        _logInfo(f"审计归档批次完成: batch={batchIndex}, exported={len(rows)}, deleted={deleted}, fileID={fileID}")

        if deleted <= 0:
            stats["errMsg"] = f"第 {batchIndex} 批删除 0 条(可能存在写入/权限问题), 已中止以避免重复循环"
            _logError(stats["errMsg"])
            _alertOps("ERROR", auditService.ACTION_ARCHIVE_AUDIT_LOG, "审计归档删除 0 条",
                      stats["errMsg"], {"batchIndex": batchIndex})
            break

    _logInfo(f"审计归档完成: mode={stats['mode']}, batches={stats['batches']}, "
             f"exported={stats['exported']}, deleted={stats['deleted']}, errMsg={stats['errMsg'] or '-'}")
    return stats

#===== 审计日志归档 end =====


#===== 产物过期清理: 先置状态, 再删对象 begin =====

def queryExpiredArtifacts(scanLimit = None):
    """取一批到期且 READY 的产物记录(expireYMDHMS <= now, 按 recID 升序=最旧优先)"""
    scanLimit = opsSettings.getArtifactScanLimit() if scanLimit is None else _toInt(scanLimit, 0)
    nowStr = misc.getTime()
    tableName = comMysql.tablename_convertor_ch_artifact()
    rows = comMysql.query_ch_artifact(tableName, artifactStatus = ARTIFACT_STATUS_READY,
                                      expireBeforeYMDHMS = nowStr, mode = "full",
                                      order = "create", limitNum = scanLimit)
    expiredRows = []
    for row in (rows or []):
        if not isinstance(row, dict):
            continue
        expireAt = _toStr(row.get("expireYMDHMS"))
        #expireYMDHMS 为空 = 未设置保留期, 不清理(「0 = 未设置」口径)
        if expireAt and expireAt <= nowStr:
            expiredRows.append(row)
    return expiredRows


def purgeExpiredArtifacts(dryRun = True, batchSize = None, scanLimit = None):
    """★ ch_artifact 过期清理: 到期 -> **先置 artifactStatus=EXPIRED** -> 再 delFile 删对象。
       对象删除失败 -> **不再变更状态(保持已置的 EXPIRED)并告警**(不静默); 不删除 ch_artifact 行。
       dry-run: 只打印「将置 EXPIRED 并删除对象」清单。
       出参: {"mode","batches","purged","failed","skipped","errMsg"}。"""
    batchSize = opsSettings.getBatchSize() if batchSize is None else _toInt(batchSize, 0)
    stats = {"mode": "dry-run" if dryRun else "execute", "batches": 0,
             "purged": 0, "failed": 0, "skipped": 0, "errMsg": ""}

    rows = queryExpiredArtifacts(scanLimit)
    if not rows:
        _logInfo(f"[{stats['mode']}] 无到期产物需要清理")
        return stats

    if dryRun:
        _logInfo(f"[DRY-RUN] 产物过期清理: 将置 EXPIRED 并删除对象 {len(rows)} 条(每批 {batchSize} 条)")
        for row in rows[:20]:
            _logInfo(f"[DRY-RUN] 将置 EXPIRED 并 delFile: recID:{row.get('recID')}, "
                     f"fileID:{row.get('fileID')}, expire:{row.get('expireYMDHMS')}")
        stats["skipped"] = len(rows)
        return stats

    tableName = comMysql.tablename_convertor_ch_artifact()
    nowStr = misc.getTime()
    batchIndex = 0
    for chunk in _chunks(rows, batchSize):
        batchIndex += 1
        purged = 0
        failed = 0
        for row in chunk:
            recID = _toInt(row.get("recID"), 0)
            fileID = _toStr(row.get("fileID"))
            if recID <= 0 or not fileID:
                failed += 1
                _alertOps("ERROR", auditService.ACTION_ARCHIVE_ARTIFACT, "产物清理记录非法",
                          f"recID:{recID}, fileID:{fileID}", {"recID": recID})
                continue

            #★ 顺序 ①: 先置 artifactStatus=EXPIRED(状态先落, 使产物即刻不可再被使用)
            try:
                comMysql.update_ch_artifact(tableName, recID, {
                    "artifactStatus": ARTIFACT_STATUS_EXPIRED,
                    "modifyID": opsSettings.OPS_ACTOR_LOGINID,
                    "modifyYMDHMS": nowStr,
                })
            except Exception as e:
                failed += 1
                _logError(f"产物置 EXPIRED 失败 recID:{recID}, errMsg:{e}")
                continue

            #★ 顺序 ②: 再 delFile 删对象(唯一出口; 删除失败保持原状态=已置的 EXPIRED 并告警)
            try:
                deleteOk = comFS.delFile(fileID)
            except Exception as e:
                deleteOk = False
                _logError(f"产物对象删除异常 fileID:{fileID}, errMsg:{e}")
            if not deleteOk:
                failed += 1
                _logError(f"产物对象删除失败(状态保持 EXPIRED, 不静默) recID:{recID}, fileID:{fileID}")
                _alertOps("ERROR", auditService.ACTION_ARCHIVE_ARTIFACT, "产物对象删除失败",
                          f"recID:{recID}, fileID:{fileID} 删除失败, 状态保持 EXPIRED, 请人工处理",
                          {"recID": recID, "fileID": fileID})
                continue
            purged += 1

        stats["purged"] += purged
        stats["failed"] += failed
        stats["batches"] = batchIndex

        #每批留日志与审计(谁在何时删了什么对象)
        auditService.writeAudit(opsSettings.OPS_ACTOR_LOGINID, auditService.ACTION_ARCHIVE_ARTIFACT,
                                targetType = auditService.TARGET_TYPE_ARTIFACT,
                                targetID = f"batch{batchIndex}",
                                payload = {"batchIndex": batchIndex, "chunkSize": len(chunk),
                                           "purged": purged, "failed": failed},
                                result = auditService.RESULT_OK if failed == 0 else auditService.RESULT_FAIL,
                                errMsg = "" if failed == 0 else f"{failed} 条对象删除失败",
                                memo = f"产物过期清理批次: 置 EXPIRED+删对象 {purged} 条 / 失败 {failed} 条")
        _logInfo(f"产物清理批次完成: batch={batchIndex}, purged={purged}, failed={failed}")

    _logInfo(f"产物过期清理完成: mode={stats['mode']}, purged={stats['purged']}, "
             f"failed={stats['failed']}, errMsg={stats['errMsg'] or '-'}")
    return stats

#===== 产物过期清理 end =====


#===== 单次运行入口 begin =====

def runOnce(dataSet = None, execute = False):
    """单次归档+清理(默认 dry-run)。
       出参: {"startedAt","dryRun","degraded","locked","audit","artifact","errMsg"}。"""
    dataSet = dataSet if isinstance(dataSet, dict) else {}
    dryRun = isDryRun(execute) if not dataSet.get("dryRun") else bool(dataSet.get("dryRun"))
    only = _toStr(dataSet.get("only")).lower()
    stats = {"startedAt": misc.getTime(), "dryRun": dryRun, "degraded": 0,
             "locked": False, "audit": {}, "artifact": {}, "errMsg": ""}

    if _toStr(dataSet.get("useLock")) == "0":
        locked, degraded = True, False
    else:
        locked, degraded = acquireArchiveLock()
    stats["locked"] = bool(locked)
    stats["degraded"] = 1 if degraded else 0
    if not locked:
        stats["errMsg"] = "已有归档任务在执行(锁未获取), 本轮跳过"
        _logWarn(stats["errMsg"])
        return stats

    try:
        if only in ("", "audit", "all"):
            stats["audit"] = archiveAuditLog(dryRun = dryRun,
                                             retainMonths = dataSet.get("retainMonths"),
                                             batchSize = dataSet.get("batchSize"),
                                             maxBatch = dataSet.get("maxBatch"),
                                             exportFormat = dataSet.get("exportFormat"))
            if stats["audit"].get("errMsg"):
                stats["errMsg"] = stats["audit"]["errMsg"]
        if only in ("", "artifact", "all"):
            stats["artifact"] = purgeExpiredArtifacts(dryRun = dryRun,
                                                      batchSize = dataSet.get("batchSize"),
                                                      scanLimit = dataSet.get("scanLimit"))
            if stats["artifact"].get("errMsg"):
                stats["errMsg"] = stats["artifact"]["errMsg"]
    except Exception as e:
        stats["errMsg"] = f"归档清理异常: {str(e)}"
        _logError(f"归档清理异常, errMsg:{e}, {traceback.format_exc()}")
    finally:
        releaseArchiveLock()

    #心跳: 仅真执行时记录(定时任务「最后成功时间」指标的数据来源)
    if not dryRun:
        heartbeat.recordRun(heartbeat.JOB_ARCHIVE, ok = (not stats["errMsg"]),
                            note = f"deleted={stats.get('audit', {}).get('deleted')}, "
                                   f"purged={stats.get('artifact', {}).get('purged')}, errMsg={stats['errMsg'] or '-'}")
    return stats

#===== 单次运行入口 end =====


def main(argv = None):
    parser = argparse.ArgumentParser(description = "contentHub 归档清理(默认 dry-run; 真删需 --execute)")
    parser.add_argument("--execute", action = "store_true",
                        help = "★ 显式确认执行破坏性操作(真删); 缺省为 dry-run")
    parser.add_argument("--dry-run", action = "store_true",
                        help = "强制 dry-run(即使设置了 CH_ARCHIVE_EXECUTE=1)")
    parser.add_argument("--retain-months", type = int, default = None,
                        help = f"审计保留期(月, 默认 {opsSettings.DEFAULT_ARCHIVE_AUDIT_RETAIN_MONTHS})")
    parser.add_argument("--batch-size", type = int, default = None,
                        help = f"分批大小(默认 {opsSettings.DEFAULT_ARCHIVE_BATCH_SIZE})")
    parser.add_argument("--max-batch", type = int, default = None, help = "单次最大批次数(0=不限制)")
    parser.add_argument("--format", type = str, default = "", help = "导出格式(csv | json.gz)")
    parser.add_argument("--only", type = str, default = "", help = "只跑归档/清理(audit | artifact)")
    parser.add_argument("--json", action = "store_true", help = "以 JSON 输出统计")
    args = parser.parse_args(argv)

    execute = bool(args.execute) and not bool(args.dry_run)
    dataSet = {"only": args.only, "retainMonths": args.retain_months, "batchSize": args.batch_size,
               "maxBatch": args.max_batch, "exportFormat": args.format or None}
    dryRun = isDryRun(execute)

    #★ 脚本头显著提示(默认 dry-run)
    banner = ("=" * 78 + "\n"
              "★ contentHub 归档清理\n"
              "★ 破坏性操作默认 dry-run: 本次" + ("【将真删】已显式确认(--execute / CH_ARCHIVE_EXECUTE=1)" if not dryRun
                                                     else "【DRY-RUN】只打印清单, 不导出、不删除") + "\n"
              "★ 执行顺序强约束: 先导出上传成功 -> 再分批删除; 导出失败一律不删除\n"
              "★ 归档/清理动作本身写入 ch_audit_log(谁在何时删了什么)\n" + "=" * 78)
    print(banner)
    _logInfo(banner.replace("\n", " | "))

    stats = runOnce(dataSet, execute = execute)
    if args.json:
        print(json.dumps(stats, ensure_ascii = False, indent = 2))
    else:
        print(f"[archive] dryRun={stats['dryRun']}, degraded={stats['degraded']}, locked={stats['locked']}, "
              f"audit={stats['audit']}, artifact={stats['artifact']}, errMsg={stats['errMsg'] or '-'}")
    return 0 if not stats["errMsg"] else 1


if __name__ == "__main__":
    sys.exit(main())
