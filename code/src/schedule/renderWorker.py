#! /usr/bin/env python3
#encoding: utf-8:

#Filename: renderWorker.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 渲染任务常驻消费者(SP3c · 主计划 P2-7 / P2-8)。

#职责:
#  1) 主路径: **阻塞消费 Redis 渲染队列 CH_RENDER**(由 processor/renderService._notifyRenderWorker 投递,
#     comDB.getMsg2Queue brpop 阻塞, 近实时触发), **单实例 + 串行消费**;
#     兜底路径: brpop 超时(=interval)无消息时, 跑一次 runOnce 轮询 ch_render_job 的 PENDING
#     —— 补偿 Redis 抖动/通知丢失/队列功能上线前的存量任务; ★ MySQL 表始终是任务真相源与持久化。
#  2) Redis 任务锁防多进程重复消费; ★ Redis 不可用时降级为「进程内锁 + 告警日志」, 不阻塞、不崩溃;
#  3) 逐条执行: processor/renderService.executeJob() -> 渲染 -> 写 ch_artifact -> 更新 jobStatus/progress/costMs/errMsg;
#     异常/渲染失败 -> FAILED 并记录原因(不抛出到主循环);
#  4) ★ 与 SP3b 的 Playwright 策略保持一致: **不并发截图** —— worker 串行处理任务,
#     engine/htmlToImage.py 内部亦为单浏览器实例 + 串行渲染(同一时刻只渲染一个页面)。
#
#★ 分层契约: 本文件属调度层, 只依赖 processor/ 与 common/; **不 import main/subfunc**。
#★ 用法:
#   常驻(默认):  cd code/src && python schedule/renderWorker.py
#   单次执行:    cd code/src && python schedule/renderWorker.py --once
#   自定义兜底周期:  python schedule/renderWorker.py --interval 30 --limit 3
#   (环境变量 CH_RENDER_WORKER_INTERVAL / CH_RENDER_WORKER_LIMIT 亦可覆盖)

_VERSION="20260919"


import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../code/src
if parentdir not in sys.path:
    sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import argparse
import threading
import time
import traceback

#global defintion/common var etc.
from common import globalDefinition as comGD

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#数据层唯一入口(红线 R1): 只读写 ch_render_job
from common import mysqlCommon as comMysql

#Redis 唯一入口(红线: 只经 common/redisCommon.py; 本文件不直连)
from common import redisCommon as comDB

#业务层: 渲染任务执行(唯一执行入口)
from processor import renderService


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    try:
        # _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_RENDER_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None


#===== 常量 begin =====

#单轮最多消费任务数(串行执行; 保守策略, 不做并发池)
DEFAULT_BATCH_SIZE = 3

#Redis 任务锁: TTL 需大于单任务最长渲染时间(长图多切片截图可能较久)
DEFAULT_TASK_LOCK_TTL_SECONDS = 300

#Redis 任务锁 key 结构(与既有 Redis 用法保持一致: genDBKey 生成)
LOCK_LEVEL1 = "contenthub"
LOCK_NAME = "renderjoblock"

#渲染通知队列(与 transferCHMysql 的 CH_MYSQL 同款 key 组装; 由 renderService 投递)
RENDER_QUEUE_KEY = comGD._DEF_CH_MSG_QUEUE_RENDER_TITLE

#兜底轮询周期(秒): 同时作为 getMsg2Queue(brpop) 的阻塞超时;
#超时无消息则跑一次 runOnce(SELECT ch_render_job WHERE PENDING)补偿——
#补偿 Redis 抖动期未投出/丢失的通知、以及队列功能上线前的存量 PENDING 任务。
#★ MySQL 表始终是任务真相源与持久化, 队列只作「触发器」, 双路径由任务锁 + 状态机防重复执行。
DEFAULT_BACKSTOP_INTERVAL_SECONDS = 30

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


def _logInfo(message):
    if _LOG:
        _LOG.info(f"PID:{_processorPID}, {message}")


def _logWarn(message):
    if _LOG:
        _LOG.warning(f"W: PID:{_processorPID}, {message}")


def _logError(message):
    if _LOG:
        _LOG.error(f"PID:{_processorPID}, {message}")

#===== 通用小工具 end =====


#===== Redis 任务锁(可降级) begin =====

#进程内锁(Redis 不可用时的降级实现; 也是单进程内的第一道去重)
_PROCESS_LOCK_TABLE = {}
_PROCESS_LOCK_GUARD = threading.Lock()


def _genLockKey(jobCode):
    return comDB.genDBKey(LOCK_LEVEL1, LOCK_NAME, _toStr(jobCode))


def acquireTaskLock(jobCode, ttlSeconds = DEFAULT_TASK_LOCK_TTL_SECONDS):
    """获取任务锁: 返回 (locked, degraded)。
       - 先取进程内锁(同进程天然串行, 防止同一任务被重复消费);
       - 再取 Redis 锁(跨进程防重复消费); ★ Redis 不可用 -> degraded=True 并**放行**(降级不阻塞)。"""
    jobCode = _toStr(jobCode)
    if not jobCode:
        return False, False

    now = time.time()
    with _PROCESS_LOCK_GUARD:
        expiredKeys = [key for key, stamp in _PROCESS_LOCK_TABLE.items()
                       if now - stamp > int(ttlSeconds)]
        for key in expiredKeys:
            _PROCESS_LOCK_TABLE.pop(key, None)
        if jobCode in _PROCESS_LOCK_TABLE:
            return False, False
        _PROCESS_LOCK_TABLE[jobCode] = now

    degraded = False
    try:
        locked = comDB.redisMainDB.set(_genLockKey(jobCode), _processorPID, nx = True, ex = int(ttlSeconds))
        if not locked:
            #已有其它实例持锁: 释放进程内锁并跳过(防多进程重复消费)
            with _PROCESS_LOCK_GUARD:
                _PROCESS_LOCK_TABLE.pop(jobCode, None)
            return False, False
    except Exception as e:
        #★ 降级: Redis 任务锁不可用时不阻塞消费(单实例 + 进程内锁兜底), 记告警日志
        degraded = True
        _logWarn(f"任务锁降级为进程内锁(Redis 不可用) jobCode:{jobCode}, errMsg:{e}")

    return True, degraded


def releaseTaskLock(jobCode):
    """释放任务锁(幂等; Redis 异常不抛)"""
    jobCode = _toStr(jobCode)
    if not jobCode:
        return
    with _PROCESS_LOCK_GUARD:
        _PROCESS_LOCK_TABLE.pop(jobCode, None)
    try:
        comDB.redisMainDB.delete(_genLockKey(jobCode))
    except Exception as e:
        _logWarn(f"任务锁释放失败(忽略) jobCode:{jobCode}, errMsg:{e}")

#===== Redis 任务锁 end =====


#===== 任务消费 begin =====

def fetchPendingJobs(limitNum = DEFAULT_BATCH_SIZE):
    """取待执行任务(PENDING, 按 recID 升序 = 先进先出); 读取异常返回 []"""
    tableName = comMysql.tablename_convertor_ch_render_job()
    limitNum = _toInt(limitNum, DEFAULT_BATCH_SIZE) or DEFAULT_BATCH_SIZE
    try:
        rows = comMysql.query_ch_render_job(tableName, jobStatus = "PENDING", mode = "full",
                                            order = "create", limitNum = limitNum)
    except Exception as e:
        _logError(f"待执行任务查询失败, errMsg:{e}, {traceback.format_exc()}")
        return []
    return [row for row in (rows or []) if isinstance(row, dict)]


def processJob(jobRecord, dataSet = None):
    """处理单条任务(串行): 加锁 -> executeJob -> 释放锁。
       出参: {"jobCode","jobID","locked","degraded","errCode","skipped","data"}。"""
    jobCode = _toStr(jobRecord.get("jobCode"))
    jobID = _toInt(jobRecord.get("recID"), 0)

    #防御: 只有 PENDING(或 FAILED 重试入队)的任务可被消费; 状态机校验复用业务层实现(不重复定义转移表)
    currStatus = _toStr(jobRecord.get("jobStatus"))
    transitionCode, _rtnField, transitionMsg = renderService.checkJobStatusTransition(currStatus, "RUNNING")
    if transitionCode:
        return {"jobCode": jobCode, "jobID": jobID, "locked": False, "degraded": False,
                "errCode": transitionCode, "skipped": "1",
                "msg": f"任务状态不可执行: {transitionMsg}"}

    locked, degraded = acquireTaskLock(jobCode)
    if not locked:
        return {"jobCode": jobCode, "jobID": jobID, "locked": False, "degraded": degraded,
                "errCode": "", "skipped": "1", "msg": "任务已被其它实例/本轮持锁, 跳过"}

    try:
        rtn = renderService.executeJob(jobRecord, dataSet)
        if not isinstance(rtn, dict):
            rtn = {}
        return {"jobCode": jobCode, "jobID": jobID, "locked": True, "degraded": degraded,
                "errCode": _toStr(rtn.get("errCode")), "skipped": "0",
                "msg": ";".join(rtn.get("errMsgList") or []),
                "data": rtn.get("data") or {}}
    except Exception as e:
        #executeJob 内部已收口 FAILED; 这里兜底防御(不让单任务异常中断 worker)
        _logError(f"任务执行异常(worker 兜底) jobCode:{jobCode}, errMsg:{e}, {traceback.format_exc()}")
        try:
            renderService.updateJobStatus(jobID, "FAILED", progress = 0,
                                          errMsg = f"worker 兜底异常: {str(e)}"[:500],
                                          finishYMDHMS = misc.getTime())
        except Exception:
            pass
        #★ 2026-09-24: 兜底路径也要联动主题状态(否则失败后主题永久卡在 RENDERING); 失败只告警
        try:
            renderService.rollbackTopicRenderFailedById(_toStr(jobRecord.get("topicID")),
                                                       _toStr(jobRecord.get("ownerID")), jobCode,
                                                       f"worker 兜底异常: {str(e)}")
        except Exception:
            pass
        return {"jobCode": jobCode, "jobID": jobID, "locked": True, "degraded": degraded,
                "errCode": "E1", "skipped": "0", "msg": f"worker 兜底异常: {str(e)}", "data": {}}
    finally:
        releaseTaskLock(jobCode)


def runOnce(limitNum = DEFAULT_BATCH_SIZE, dataSet = None):
    """单轮消费: 取 PENDING 任务并**串行**逐条执行(不并发截图)。出参统计信息。"""
    jobList = fetchPendingJobs(limitNum)
    stats = {"fetched": len(jobList), "done": 0, "failed": 0, "skipped": 0, "degraded": 0, "items": []}

    for jobRecord in jobList:
        result = processJob(jobRecord, dataSet)
        stats["items"].append(result)
        if result.get("degraded"):
            stats["degraded"] += 1
        if result.get("skipped") == "1":
            stats["skipped"] += 1
        elif result.get("errCode") == "B0":
            stats["done"] += 1
        else:
            stats["failed"] += 1

    if jobList:
        _logInfo(f"runOnce 完成: fetched:{stats['fetched']}, done:{stats['done']}, "
                 f"failed:{stats['failed']}, skipped:{stats['skipped']}, degraded:{stats['degraded']}")
    return stats


def consumeOneMessage(msg):
    """消费一条 CH_RENDER 队列消息: 回查任务记录 -> processJob(锁 + 状态机 + 执行)。

       队列只带最小标识(recID/jobCode), 这里回 MySQL 取完整记录(与现有 runOnce -> processJob 流程一致);
       回查不到即跳过, 交由兜底轮询补偿(不在此重试, 避免无谓 DB 压力)。"""
    if not isinstance(msg, dict):
        return
    jobCode = _toStr(msg.get("jobCode"))
    recID = _toInt(msg.get("recID"), 0)
    if recID <= 0 and not jobCode:
        _logWarn("渲染队列消息缺少 jobCode/recID, 丢弃")
        return

    jobRecord = renderService.getJobRecord(recID) if recID > 0 else {}
    if not isinstance(jobRecord, dict) or not jobRecord:
        _logWarn(f"渲染队列任务记录回查失败, 交由兜底轮询处理 jobCode:{jobCode}, recID:{recID}")
        return

    result = processJob(jobRecord)
    _logInfo(f"队列消费 jobCode:{jobCode}, skipped:{result.get('skipped')}, "
             f"errCode:{result.get('errCode')}, msg:{result.get('msg', '')}")


def drainQueueOnce(limitNum = DEFAULT_BATCH_SIZE, drainTimeout = 1):
    """--once 模式: 有限次排空 CH_RENDER 队列(最多 limitNum*4 条, 防无限), 排空后退出。"""
    maxDrain = max(1, _toInt(limitNum, DEFAULT_BATCH_SIZE)) * 4
    drained = 0
    for _ in range(maxDrain):
        try:
            msg = comDB.getMsg2Queue(RENDER_QUEUE_KEY, timeout = drainTimeout)
        except Exception as e:
            _logError(f"--once 排空队列异常, errMsg:{e}")
            break
        if not msg:
            break
        consumeOneMessage(msg)
        drained += 1
    if drained:
        _logInfo(f"--once 排空渲染队列 {drained} 条")
    return drained


def _closeBrowserQuietly():
    """收尾释放截图浏览器实例(单浏览器实例进程内复用, 用完统一关闭)"""
    try:
        from engine import htmlToImage
        htmlToImage.closeBrowser()
    except Exception:
        pass


def main(argv = None):
    parser = argparse.ArgumentParser(description = "contentHub 渲染任务消费者(队列阻塞消费 + 兜底轮询, 单实例串行)")
    parser.add_argument("--once", action = "store_true", help = "排空队列 + 跑一轮兜底轮询后退出(无守护环境验证用)")
    parser.add_argument("--interval", type = int,
                        default = _toInt(os.environ.get("CH_RENDER_WORKER_INTERVAL"), DEFAULT_BACKSTOP_INTERVAL_SECONDS),
                        help = f"队列阻塞超时/兜底轮询周期秒数(默认 {DEFAULT_BACKSTOP_INTERVAL_SECONDS})")
    parser.add_argument("--limit", type = int,
                        default = _toInt(os.environ.get("CH_RENDER_WORKER_LIMIT"), DEFAULT_BATCH_SIZE),
                        help = f"单轮兜底最多消费 PENDING 任务数(默认 {DEFAULT_BATCH_SIZE})")
    args = parser.parse_args(argv)

    interval = max(1, _toInt(args.interval, DEFAULT_BACKSTOP_INTERVAL_SECONDS))
    limitNum = max(1, _toInt(args.limit, DEFAULT_BATCH_SIZE))

    _logInfo(f"renderWorker 启动: backstop={interval}s, limit={limitNum}, once={bool(args.once)}")

    if args.once:
        drainQueueOnce(limitNum)
        stats = runOnce(limitNum)
        _closeBrowserQuietly()
        return 0 if stats.get("failed", 0) == 0 else 1

    try:
        while True:
            #主路径: 阻塞消费 CH_RENDER 队列(近实时); brpop 超时(=interval)无消息则跑兜底轮询
            try:
                msg = comDB.getMsg2Queue(RENDER_QUEUE_KEY, timeout = interval)
            except Exception as e:
                _logError(f"渲染队列消费异常, errMsg:{e}, {traceback.format_exc()}")
                msg = {}

            if msg:
                consumeOneMessage(msg)
            else:
                #超时无消息 -> 兜底轮询 PENDING(补偿 Redis 抖动/丢失通知/存量任务)
                try:
                    runOnce(limitNum)
                except Exception as e:
                    _logError(f"renderWorker 兜底轮询异常, errMsg:{e}, {traceback.format_exc()}")
            #注: getMsg2Queue 阻塞至超时, 队列有消息时即时处理, 无需额外 time.sleep
    except KeyboardInterrupt:
        _logInfo("renderWorker 收到中断, 退出")
    finally:
        _closeBrowserQuietly()
    return 0


if __name__ == "__main__":
    sys.exit(main())
