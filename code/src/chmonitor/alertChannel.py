#! /usr/bin/env python3
#encoding: utf-8:

#Filename: alertChannel.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 告警通道(SP4c · P3-8; 可插拔通知接口)。

#职责:
#  1) 提供**可插拔**的告警通知接口: 统一入参 alert(见 buildAlert), 统一出参 {channel, sent, networkRequest, ...};
#  2) 默认通道 = log(沿用 miscCommon.setLogNew 落盘 code/log/), 保证「告警一定留痕」;
#  3) 邮件 / 企微机器人为**占位实现**(PH 阶段): ★ 本轮**不发起任何对外网络请求**,
#     接口可注入, 默认仅记录「已请求发送(占位)」—— 具体通道在 Phase 3 后续或上线前接入;
#  4) 供 schedule/archive.py、schedule/credentialCheck.py、chmonitor/dailyCheck.py 调用(懒加载, 避免导入环)。
#
#★ 网络红线: 本模块**不含任何网络调用**(无套接字/无 HTTP 客户端/无邮件库);
#  占位通道的 networkRequest 恒为 "0", 由静态验收 S28 与冒烟运行期断言双重锁定。
#★ 分层契约: 本模块只依赖 common/(日志) 与 config/(阈值来源), 不 import processor/subfunc。

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

from common import globalDefinition as comGD

from common import miscCommon as misc

from config import opsSettings

from chmonitor import metrics


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    try:
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None


#===== 常量 begin =====

CHANNEL_LOG = "log"
CHANNEL_EMAIL = "email"
CHANNEL_WECOM = "wecom"
CHANNEL_NAME_LIST = [CHANNEL_LOG, CHANNEL_EMAIL, CHANNEL_WECOM]

#网络请求标记: "0" = 未发起(占位/仅日志); 本轮所有通道恒为 "0"
NETWORK_REQUEST_NO = "0"

#占位实现说明
PLACEHOLDER_NOTE = "占位实现: 本轮不发任何网络请求, 仅记录告警意图(接口可注入, 默认仅记日志)"

#===== 常量 end =====


def _toStr(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _log(level, message):
    if not _LOG:
        return
    level = _toStr(level).upper()
    if level == metrics.LEVEL_ERROR:
        _LOG.error(f"PID:{_processorPID}, {message}")
    elif level == metrics.LEVEL_WARN:
        _LOG.warning(f"W: PID:{_processorPID}, {message}")
    else:
        _LOG.info(f"PID:{_processorPID}, {message}")


#===== 告警结构 begin =====

def buildAlert(metricResult, actor = "", extra = None):
    """把「指标判定结果」包装为统一告警体(供各通道消费)。
       出参: {metricName, title, currentValue, threshold, level, suggest, text, actor}"""
    metricResult = metricResult if isinstance(metricResult, dict) else {}
    metricName = _toStr(metricResult.get("metricName"))
    title = _toStr(metricResult.get("title")) or metricName
    level = _toStr(metricResult.get("level")).upper() or metrics.LEVEL_INFO
    alert = {
        "metricName": metricName,
        "title": title,
        "currentValue": metricResult.get("currentValue"),
        "threshold": metricResult.get("threshold"),
        "level": level,
        "suggest": _toStr(metricResult.get("suggest")),
        "actor": _toStr(actor),
        "text": (f"[{level}] {title}({metricName}): 当前值={metricResult.get('currentValue')}, "
                 f"阈值={metricResult.get('threshold')}, 建议={_toStr(metricResult.get('suggest'))}"),
    }
    if isinstance(extra, dict):
        alert.update(extra)
    return alert

#===== 告警结构 end =====


#===== 通道实现 begin =====

class AlertChannel:
    """告警通道抽象: 子类实现 send(alert) -> {channel, sent, networkRequest, ...}"""

    name = ""
    placeholderFlag = False
    networkRequest = NETWORK_REQUEST_NO

    def send(self, alert):
        raise NotImplementedError("AlertChannel.send 未实现")


class LogAlertChannel(AlertChannel):
    """★ 默认通道: 告警落盘(沿用 miscCommon.setLogNew 的 code/log/)"""

    name = CHANNEL_LOG
    placeholderFlag = False
    networkRequest = NETWORK_REQUEST_NO

    def send(self, alert):
        alert = alert if isinstance(alert, dict) else {}
        level = _toStr(alert.get("level")).upper() or metrics.LEVEL_INFO
        _log(level, f"告警(通道:{self.name}) {alert.get('text', '')}")
        return {"channel": self.name, "sent": 1, "networkRequest": self.networkRequest,
                "placeholder": "0", "note": "告警已落盘"}


class EmailAlertChannel(AlertChannel):
    """邮件通道 —— **占位实现**: 不发网络请求, 仅记录意图(上线前再注入真实实现)"""

    name = CHANNEL_EMAIL
    placeholderFlag = True
    networkRequest = NETWORK_REQUEST_NO

    def send(self, alert):
        alert = alert if isinstance(alert, dict) else {}
        _log(metrics.LEVEL_WARN, f"告警(通道:{self.name}, 占位未发送) {alert.get('text', '')}")
        return {"channel": self.name, "sent": 0, "networkRequest": self.networkRequest,
                "placeholder": "1", "note": PLACEHOLDER_NOTE}


class WeComAlertChannel(AlertChannel):
    """企微机器人通道 —— **占位实现**: 不发网络请求, 仅记录意图(上线前再注入真实实现)"""

    name = CHANNEL_WECOM
    placeholderFlag = True
    networkRequest = NETWORK_REQUEST_NO

    def send(self, alert):
        alert = alert if isinstance(alert, dict) else {}
        _log(metrics.LEVEL_WARN, f"告警(通道:{self.name}, 占位未发送) {alert.get('text', '')}")
        return {"channel": self.name, "sent": 0, "networkRequest": self.networkRequest,
                "placeholder": "1", "note": PLACEHOLDER_NOTE}


#通道注册表(可扩展: 新增通道 = 加一个实现 + 一条登记, 不改调用方)
ALERT_CHANNEL_MAP = {
    CHANNEL_LOG: LogAlertChannel,
    CHANNEL_EMAIL: EmailAlertChannel,
    CHANNEL_WECOM: WeComAlertChannel,
}

#===== 通道实现 end =====


def getAlertChannel(channelName = ""):
    """取通道实例(缺省取 config/opsSettings.MONITOR_ALERT_CHANNEL, 非法名回落 log)"""
    name = _toStr(channelName) or opsSettings.getMonitorAlertChannel()
    channelClass = ALERT_CHANNEL_MAP.get(name) or LogAlertChannel
    return channelClass()


def sendAlert(alert, channelName = ""):
    """发送单条告警; 任何异常不外抛(告警失败不得阻断主流程), 出参附 error 标记。"""
    try:
        channel = getAlertChannel(channelName)
    except Exception as e:
        _log(metrics.LEVEL_WARN, f"告警通道初始化失败(降级为日志): {e}")
        channel = LogAlertChannel()
    try:
        result = channel.send(alert)
        if not isinstance(result, dict):
            result = {"channel": getattr(channel, "name", ""), "sent": 0, "networkRequest": NETWORK_REQUEST_NO}
        return result
    except Exception as e:
        _log(metrics.LEVEL_WARN, f"告警发送异常(忽略): {e}")
        return {"channel": getattr(channel, "name", ""), "sent": 0,
                "networkRequest": NETWORK_REQUEST_NO, "error": str(e)[:200]}


def sendMetricAlerts(metricResults, actor = "", channelName = "", minLevel = metrics.LEVEL_WARN):
    """批量发送指标告警: 仅发送 level >= minLevel(默认 WARN)的项。
       出参: {"requested", "sent", "channel", "results"}。"""
    minLevel = _toStr(minLevel).upper() or metrics.LEVEL_WARN
    channel = getAlertChannel(channelName)
    results = []
    requested = 0
    for metricResult in metricResults or []:
        if not isinstance(metricResult, dict):
            continue
        level = _toStr(metricResult.get("level")).upper()
        if metrics.LEVEL_ORDER.get(level, 0) < metrics.LEVEL_ORDER.get(minLevel, 1):
            continue
        requested += 1
        results.append(sendAlert(buildAlert(metricResult, actor = actor), channelName = channel.name))
    return {"requested": requested, "sent": sum(1 for item in results if item.get("sent")),
            "channel": channel.name, "results": results}


if __name__ == "__main__":
    pass
    #本地自测(不发任何网络请求): 占位通道只记录意图
    _sample = metrics.evaluateRenderFailureRate(100, 20)
    print("log:", sendAlert(buildAlert(_sample), CHANNEL_LOG))
    print("email(placeholder):", sendAlert(buildAlert(_sample), CHANNEL_EMAIL))
    print("wecom(placeholder):", sendAlert(buildAlert(_sample), CHANNEL_WECOM))
