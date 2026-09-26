#! /usr/bin/env python3
#encoding: utf-8:

#Filename: credentialCheck.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 凭据健康巡检(SP4b · P3-6 / 主计划 6.4 R-03 凭据静默失效)。

#职责:
#  1) 定时探活: 按 ch_account 解出凭据后换取 access_token 判定可用性(仅公众号有凭据可探活);
#  2) 更新 ch_account.healthStatus ∈ {OK, EXPIRING, INVALID, UNKNOWN} 与 lastCheckYMDHMS;
#     - 探活成功 + 未到期 -> OK;
#     - 探活成功 + 到期日在阈值内 -> EXPIRING;
#     - 探活失败 / 凭据缺失·解密失败·已过期 -> INVALID;
#     - 平台不适用 / 平台配置缺失 / 探活能力缺失 -> UNKNOWN(不误判为 INVALID);
#  3) ★ 按 R-03 分级告警(日志告警): OK=info / EXPIRING=warn / INVALID=error / UNKNOWN=warn;
#  4) 小红书无平台凭据、且本项目对小红书**只导出素材包、不投递不发布** -> **跳过并说明**(不改写其健康状态);
#  5) ★ SP4c 守护化(§10 第 9 条): 提供常驻定时入口 --loop(与 renderWorker 同风格: 单实例 + Redis 锁可降级 +
#     日志规范)与单次执行入口(供 cron/计划任务调用); 告警输出对接 chmonitor/alertChannel(可插拔通道, 默认落盘,
#     占位通道不发网络请求), 不再只写日志; 每次运行刷新 chmonitor/heartbeat(供「定时任务最后成功时间」指标判定)。
#
#★ 凭据红线(R-19): 明文与密钥永不落库/不入日志 —— 解密复用 processor/publishService.decryptAccountCredential,
#  本文件不自行解密、不打印任何凭据内容, 日志一律经 publishService 的脱敏口径。
#★ 投递红线: 本文件只做**只读探活**(换取 access_token), **不做任何投递/发布**。
#★ 分层契约: 本文件属调度层, 只依赖 processor/ 与 common/ 与 chmonitor/ 与 config/; **不 import main/subfunc**。
#★ 用法:
#   全量单次执行:  cd code/src && python schedule/credentialCheck.py
#   ★ 常驻定时:    python schedule/credentialCheck.py --loop --interval 3600
#   指定账号:      python schedule/credentialCheck.py --account-id 77
#   指定平台:      python schedule/credentialCheck.py --platform wechat_mp
#   JSON 输出:     python schedule/credentialCheck.py --json

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
import datetime
import json
import threading
import time
import traceback

#global defintion/common var etc.
from common import globalDefinition as comGD

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#数据层唯一入口(红线 R1): 本文件只读写 ch_account
from common import mysqlCommon as comMysql

#Redis 唯一入口(红线: 只经 common/redisCommon.py; 本文件不直连)
from common import redisCommon as comDB

#业务层: 凭据解密/健康状态回写/平台适配器工厂(复用既有实现, 不造第二份)
from processor import publishService

from processor import renderService

from processor import platformAdapter

#监控心跳(定时任务最后成功时间) —— SP4c 守护化; 本模块不 import schedule, 无循环依赖
from chmonitor import heartbeat


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    try:
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None


#===== 常量 begin =====

#健康状态口径(与 database/ch_account.txt 的注释一致)
HEALTH_OK = "OK"
HEALTH_EXPIRING = "EXPIRING"
HEALTH_INVALID = "INVALID"
HEALTH_UNKNOWN = "UNKNOWN"
HEALTH_STATUS_LIST = [HEALTH_OK, HEALTH_EXPIRING, HEALTH_INVALID, HEALTH_UNKNOWN]

#可探活平台(有平台凭据可换取 token); 其余平台跳过并说明
PROBE_PLATFORM_LIST = ["wechat_mp"]

#★ 小红书: 无平台凭据、且本项目只导出素材包(不投递/不发布) -> 巡检跳过
SKIP_PLATFORM_NOTE_MAP = {
    "xiaohongshu": "小红书无平台凭据(只导出素材包, 不投递不发布), 无需探活, 已跳过",
    "generic": "通用 HTML 导出无平台凭据, 无需探活, 已跳过",
}

#到期预警阈值(天): 到期日在阈值内 -> EXPIRING(环境变量 CH_CREDENTIAL_EXPIRE_WARN_DAYS 可覆盖)
DEFAULT_EXPIRE_WARN_DAYS = 7
EXPIRE_WARN_DAYS_ENV_KEY = "CH_CREDENTIAL_EXPIRE_WARN_DAYS"

#Redis 重入锁(可降级)
LOCK_LEVEL1 = "contenthub"
LOCK_NAME = "credentialcheck"
DEFAULT_LOCK_TTL_SECONDS = 300

#★ SP4c 守护化: 常驻轮询间隔(秒), 默认 3600(每小时一次); 可用 --interval 或环境变量覆盖
DEFAULT_LOOP_INTERVAL_SECONDS = 3600
LOOP_INTERVAL_ENV_KEY = "CH_CREDENTIAL_CHECK_INTERVAL"

#告警级别(供静态验收断言分级落点)
ALERT_LEVEL_MAP = {
    HEALTH_OK: "INFO",
    HEALTH_EXPIRING: "WARN",
    HEALTH_INVALID: "ERROR",
    HEALTH_UNKNOWN: "WARN",
}

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


def getExpireWarnDays():
    """到期预警阈值(天); 非法/未配置回落默认值"""
    days = _toInt(os.environ.get(EXPIRE_WARN_DAYS_ENV_KEY), 0)
    return days if days > 0 else DEFAULT_EXPIRE_WARN_DAYS


def _alert(healthStatus, accountID, platform, message):
    """★ R-03 分级告警: OK=info / EXPIRING=warn / INVALID=error / UNKNOWN=warn。
       ★ SP4c: 除日志落盘外, **对接 monitor 可插拔告警通道**(占位通道不发任何网络请求)。"""
    text = f"凭据巡检 accountID:{accountID}, platform:{platform}, healthStatus:{healthStatus}, {message}"
    level = ALERT_LEVEL_MAP.get(_toStr(healthStatus).upper(), "WARN")
    if level == "ERROR":
        _logError(text)
    elif level == "WARN":
        _logWarn(text)
    else:
        _logInfo(text)
    #告警输出对接 monitor(懒加载, 避免与 monitor 包产生导入环); 失败不影响巡检主流程
    try:
        from chmonitor import alertChannel
        alertChannel.sendAlert({"metricName": "credential_health", "title": "凭据健康",
                                "level": level, "currentValue": _toStr(healthStatus),
                                "threshold": "OK/EXPIRING/INVALID/UNKNOWN",
                                "suggest": "INVALID 凭据立即更新; EXPIRING 在到期前更换",
                                "text": text})
    except Exception as e:
        _logWarn(f"告警通道对接失败(忽略), errMsg:{e}")
    return level

#===== 通用小工具 end =====


#===== Redis 重入锁(可降级) begin =====

_PROCESS_LOCK_STAMP = 0.0
_PROCESS_LOCK_FLAG = False
_PROCESS_LOCK_GUARD = threading.Lock()


def acquireCheckLock(ttlSeconds = DEFAULT_LOCK_TTL_SECONDS):
    """获取巡检锁: 返回 (locked, degraded)。
       进程内锁 + Redis SET NX EX; ★ Redis 不可用 -> degraded=True 并**放行**(降级不阻塞)。"""
    global _PROCESS_LOCK_STAMP, _PROCESS_LOCK_FLAG
    now = time.time()
    with _PROCESS_LOCK_GUARD:
        if _PROCESS_LOCK_FLAG and now - _PROCESS_LOCK_STAMP <= int(ttlSeconds):
            return False, False
        _PROCESS_LOCK_FLAG = True
        _PROCESS_LOCK_STAMP = now

    degraded = False
    try:
        redisKey = comDB.genDBKey(LOCK_LEVEL1, LOCK_NAME, "runlock")
        locked = comDB.redisMainDB.set(redisKey, _processorPID, nx = True, ex = int(ttlSeconds))
        if not locked:
            with _PROCESS_LOCK_GUARD:
                _PROCESS_LOCK_FLAG = False
            return False, False
    except Exception as e:
        degraded = True
        _logWarn(f"凭据巡检锁降级为进程内锁(Redis 不可用), errMsg:{e}")
    return True, degraded


def releaseCheckLock():
    """释放巡检锁(幂等; Redis 异常不抛)"""
    global _PROCESS_LOCK_FLAG
    with _PROCESS_LOCK_GUARD:
        _PROCESS_LOCK_FLAG = False
    try:
        comDB.redisMainDB.delete(comDB.genDBKey(LOCK_LEVEL1, LOCK_NAME, "runlock"))
    except Exception as e:
        _logWarn(f"凭据巡检锁释放失败(忽略), errMsg:{e}")

#===== Redis 重入锁 end =====


#===== 单账号探活 begin =====

def decideHealthStatus(expireYMDHMS, probeOk, warnDays = None):
    """健康状态判定(纯函数, 便于离线验证三态):
       - 探活失败 -> INVALID;
       - 已过期   -> INVALID;
       - 阈值内   -> EXPIRING;
       - 其余     -> OK。"""
    if not probeOk:
        return HEALTH_INVALID
    warnDays = warnDays if warnDays else getExpireWarnDays()
    expireAt = publishService.parseYMDHMS(_toStr(expireYMDHMS))
    if expireAt is None:
        return HEALTH_OK
    now = datetime.datetime.now()
    if expireAt <= now:
        return HEALTH_INVALID
    if expireAt <= now + datetime.timedelta(days = warnDays):
        return HEALTH_EXPIRING
    return HEALTH_OK


def checkAccount(accountRecord, fetchAccessTokenFunc = None):
    """单账号凭据巡检(只读探活 + 健康状态回写)。
       入参 accountRecord 为 ch_account 记录(dict); fetchAccessTokenFunc 预留桩注入(冒烟用)。
       出参: {"accountID","accountCode","platform","healthStatus","probed","alertLevel","errMsg","skipReason"}。"""
    accountRecord = accountRecord if isinstance(accountRecord, dict) else {}
    accountID = _toInt(accountRecord.get("recID"), 0)
    accountCode = _toStr(accountRecord.get("accountCode"))
    platform = _toStr(accountRecord.get("platform"))

    info = {"accountID": accountID, "accountCode": accountCode, "platform": platform,
            "healthStatus": HEALTH_UNKNOWN, "probed": False, "alertLevel": "", "errMsg": "", "skipReason": ""}

    #1) 平台不适用(小红书/通用): 跳过并说明, **不改写**其健康状态
    if platform not in PROBE_PLATFORM_LIST:
        info["healthStatus"] = _toStr(accountRecord.get("healthStatus")).upper() or HEALTH_UNKNOWN
        info["skipReason"] = SKIP_PLATFORM_NOTE_MAP.get(
            platform, f"平台 {platform} 无平台凭据可探活, 已跳过")
        info["alertLevel"] = ALERT_LEVEL_MAP.get(info["healthStatus"], "WARN")
        _logInfo(f"凭据巡检跳过 accountID:{accountID}, platform:{platform}, 原因:{info['skipReason']}")
        return info

    #2) 平台配置 + 适配器
    platformRecord, platformErr = renderService._fetchPlatformRecord(platform)
    if platformErr is not None:
        info["errMsg"] = f"平台配置不可用: {platformErr.get('errMsgList')}"
        info["alertLevel"] = _alert(HEALTH_UNKNOWN, accountID, platform, info["errMsg"])
        _writeHealth(accountID, HEALTH_UNKNOWN)
        return info

    adapter = platformAdapter.getAdapter(platform, platformRecord)
    if adapter is None:
        info["errMsg"] = f"平台适配器未实现: platform={platform}"
        info["alertLevel"] = _alert(HEALTH_UNKNOWN, accountID, platform, info["errMsg"])
        _writeHealth(accountID, HEALTH_UNKNOWN)
        return info

    #3) 凭据解密(明文不落库/不入日志; 失败即 INVALID, 不静默降级)
    credential, credentialErr = publishService.decryptAccountCredential(accountRecord)
    if credentialErr is not None:
        info["errMsg"] = ";".join(credentialErr.get("errMsgList") or []) or _toStr(credentialErr.get("errCode"))
        info["healthStatus"] = HEALTH_INVALID
        info["alertLevel"] = _alert(HEALTH_INVALID, accountID, platform, info["errMsg"])
        _writeHealth(accountID, HEALTH_INVALID)
        return info

    #4) 真实探活: 换取 access_token(只读; 不投递、不发布)
    try:
        if fetchAccessTokenFunc is not None:
            probeRtn = fetchAccessTokenFunc(credential.get("appID"), credential.get("appSecret"))
        else:
            probeRtn = adapter.fetchAccessToken(credential.get("appID"), credential.get("appSecret"))
    except Exception as e:
        probeRtn = {"errCode": "F0", "errMsgList": [f"探活异常: {str(e)}"]}

    probeOk = _toStr((probeRtn or {}).get("errCode")) == "B0"
    info["probed"] = True
    if not probeOk:
        info["errMsg"] = ";".join((probeRtn or {}).get("errMsgList") or []) or _toStr((probeRtn or {}).get("errCode"))
    else:
        info["expiresIn"] = _toInt(((probeRtn or {}).get("data") or {}).get("expiresIn"), 0)

    healthStatus = decideHealthStatus(accountRecord.get("expireYMDHMS"), probeOk)
    info["healthStatus"] = healthStatus
    info["alertLevel"] = _alert(healthStatus, accountID, platform,
                                info["errMsg"] or f"探活成功, expiresIn:{info.get('expiresIn', 0)}s")
    _writeHealth(accountID, healthStatus)
    return info


def _writeHealth(accountID, healthStatus):
    """回写健康状态与最近检查时间(复用 C6 编排的既有实现; 失败仅记日志, 不阻断巡检)"""
    publishService.markAccountHealth(accountID, healthStatus, lastCheck = True, lastUse = False)

#===== 单账号探活 end =====


#===== 批量巡检 begin =====

def fetchAccountList(dataSet = None):
    """取待巡检账号清单(ch_account; 可按 platform / accountID / ownerID 收窄); 读取异常返回 []"""
    dataSet = dataSet if isinstance(dataSet, dict) else {}
    tableName = comMysql.tablename_convertor_ch_account()
    querySet = {"mode": "full"}
    if _toStr(dataSet.get("platform")):
        querySet["platform"] = _toStr(dataSet.get("platform"))
    accountID = _toInt(dataSet.get("accountID"), 0)
    if accountID > 0:
        querySet["recID"] = accountID
    #★ 2026-09-23 手改(第三方账号管理/巡检归属收窄): ownerID 为**可选**收窄条件 ——
    #  仅当 dataSet 显式传入非空 ownerID 时才加入(query_ch_account 对空值等同不过滤)。
    #  HTTP 入口(accounthealth)按登录用户注入; 定时任务/--loop/main() 不传 -> 缺省全量, 行为零变化。
    #  见 plan/前端开发计划.md「第三方账号管理」。
    if _toStr(dataSet.get("ownerID")):
        querySet["ownerID"] = _toStr(dataSet.get("ownerID"))

    try:
        rows = comMysql.query_ch_account(tableName, **querySet)
    except Exception as e:
        _logError(f"账号清单查询失败, errMsg:{e}, {traceback.format_exc()}")
        return []
    return [row for row in (rows or []) if isinstance(row, dict)]


def runOnce(dataSet = None, fetchAccessTokenFunc = None):
    """单轮巡检(幂等; 可被 accounthealth 端点或守护进程调用)。
       出参: {"total","checked","ok","expiring","invalid","unknown","skipped","degraded",
             "warnDays","items","alertSummary","checkedAt"}。"""
    dataSet = dataSet if isinstance(dataSet, dict) else {}
    stats = {"total": 0, "checked": 0, "ok": 0, "expiring": 0, "invalid": 0, "unknown": 0, "skipped": 0,
             "degraded": 0, "warnDays": getExpireWarnDays(), "items": [], "alertSummary": {},
             "checkedAt": misc.getTime()}

    if _toStr(dataSet.get("useLock")) == "0":
        locked, degraded = True, False
    else:
        locked, degraded = acquireCheckLock()
    if not locked:
        stats["skipped"] = -1
        stats["msg"] = "已有巡检在执行(锁未获取), 本轮跳过"
        _logWarn("凭据巡检未获取到锁, 本轮跳过")
        return stats
    stats["degraded"] = 1 if degraded else 0

    try:
        #★ 2026-09-23 手改(第三方账号管理/巡检归属收窄): dataSet 整体透传 —— 其中 ownerID 由 HTTP 入口
        #  (accountApi.funcAccountHealth)按登录用户注入; 此处**刻意不写任何默认收窄逻辑**,
        #  缺省(定时任务/--loop/main())即全量, 保证调度语义零变化。见 plan/前端开发计划.md。
        accountList = fetchAccountList(dataSet)
        stats["total"] = len(accountList)
        for accountRecord in accountList:
            item = checkAccount(accountRecord, fetchAccessTokenFunc = fetchAccessTokenFunc)
            stats["items"].append(item)
            key = _toStr(item.get("healthStatus")).upper() or HEALTH_UNKNOWN
            if item.get("skipReason"):
                stats["skipped"] += 1
            else:
                stats["checked"] += 1
            if key == HEALTH_OK:
                stats["ok"] += 1
            elif key == HEALTH_EXPIRING:
                stats["expiring"] += 1
            elif key == HEALTH_INVALID:
                stats["invalid"] += 1
            else:
                stats["unknown"] += 1
            alertLevel = _toStr(item.get("alertLevel")) or "WARN"
            stats["alertSummary"][alertLevel] = stats["alertSummary"].get(alertLevel, 0) + 1

        _logInfo(f"凭据巡检完成: total:{stats['total']}, checked:{stats['checked']}, ok:{stats['ok']}, "
                 f"expiring:{stats['expiring']}, invalid:{stats['invalid']}, unknown:{stats['unknown']}, "
                 f"skipped:{stats['skipped']}, degraded:{stats['degraded']}")
    except Exception as e:
        stats["errMsg"] = f"凭据巡检异常: {str(e)}"
        _logError(f"凭据巡检异常, errMsg:{e}, {traceback.format_exc()}")
    finally:
        releaseCheckLock()

    #★ SP4c: 刷新心跳(供 monitor「定时任务最后成功时间」指标判定; 写入失败不阻断)
    heartbeat.recordRun(heartbeat.JOB_CREDENTIAL_CHECK, ok = (not stats.get("errMsg")),
                        note = f"checked={stats.get('checked')}, invalid={stats.get('invalid')}, "
                              f"expiring={stats.get('expiring')}, errMsg={stats.get('errMsg') or '-'}")
    return stats

#===== 批量巡检 end =====


def _printStats(stats, asJson = False):
    if asJson:
        print(json.dumps(stats, ensure_ascii = False, indent = 2))
        return
    print(f"[credentialCheck] total={stats['total']}, checked={stats['checked']}, "
          f"ok={stats['ok']}, expiring={stats['expiring']}, invalid={stats['invalid']}, "
          f"unknown={stats['unknown']}, skipped={stats['skipped']}, degraded={stats['degraded']}")
    for item in stats.get("items") or []:
        print(f"  accountID={item.get('accountID')}, platform={item.get('platform')}, "
              f"healthStatus={item.get('healthStatus')}, alert={item.get('alertLevel')}, "
              f"skip={item.get('skipReason') or '-'}, err={item.get('errMsg') or '-'}")


def main(argv = None):
    parser = argparse.ArgumentParser(description = "contentHub 凭据健康巡检(单次执行 / --loop 常驻)")
    parser.add_argument("--loop", action = "store_true",
                        help = "★ SP4c 常驻定时模式(单实例; 与 renderWorker 同风格); 缺省为单次执行")
    parser.add_argument("--interval", type = int,
                        default = _toInt(os.environ.get(LOOP_INTERVAL_ENV_KEY), DEFAULT_LOOP_INTERVAL_SECONDS),
                        help = f"--loop 下的轮询间隔秒数(默认 {DEFAULT_LOOP_INTERVAL_SECONDS})")
    parser.add_argument("--account-id", type = int, default = 0, help = "只巡检指定 ch_account.recID")
    parser.add_argument("--platform", type = str, default = "", help = "只巡检指定平台(如 wechat_mp)")
    parser.add_argument("--json", action = "store_true", help = "以 JSON 输出巡检结果")
    args = parser.parse_args(argv)

    dataSet = {"accountID": args.account_id, "platform": args.platform}

    if not args.loop:
        stats = runOnce(dataSet)
        _printStats(stats, args.json)
        return 0

    #★ 常驻定时模式: 单实例(Redis 锁可降级); 单轮异常不退出守护
    interval = max(1, _toInt(args.interval, DEFAULT_LOOP_INTERVAL_SECONDS))
    _logInfo(f"credentialCheck 启动(常驻): interval={interval}s")
    try:
        while True:
            try:
                stats = runOnce(dataSet)
                if args.json:
                    _printStats(stats, True)
                else:
                    _logInfo(f"巡检轮次完成: checked={stats.get('checked')}, invalid={stats.get('invalid')}, "
                             f"expiring={stats.get('expiring')}, skipped={stats.get('skipped')}, "
                             f"degraded={stats.get('degraded')}")
            except Exception as e:
                #单轮异常不退出守护(记录后继续下一轮)
                _logError(f"凭据巡检单轮异常, errMsg:{e}, {traceback.format_exc()}")
            time.sleep(interval)
    except KeyboardInterrupt:
        _logInfo("credentialCheck 收到中断, 退出")
    return 0


if __name__ == "__main__":
    sys.exit(main())
