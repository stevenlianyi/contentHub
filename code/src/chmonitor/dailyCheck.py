#! /usr/bin/env python3
#encoding: utf-8:

#Filename: dailyCheck.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 每日巡检脚本(SP4c · P3-8; 主计划 8.7 监控告警)。

#职责:
#  单次执行 -> 采集七项指标 -> 阈值判定 -> 汇总报告落 code/data/monitor/(JSON) -> 经告警通道发送 WARN/ERROR。
#  ★ 本包原名 monitor/, 本轮重命名为 chmonitor/(详见 chmonitor/__init__.py 的「命名说明」)。
#
#★ 首期降级口径: 日志落盘告警(默认通道) + 每日巡检脚本 + 占位通知接口; **不做看板/时序数据库**;
#  不引入新中间件依赖; **不发起任何对外网络请求**。
#★ 分层契约: 只依赖 chmonitor/ 与 config/; **不 import main/subfunc**。
#★ 用法:
#   单次执行:   cd code/src && python chmonitor/dailyCheck.py
#   JSON 输出:  python chmonitor/dailyCheck.py --json
#   指定通道:   python chmonitor/dailyCheck.py --channel log
#   (服务器建议由 cron / Windows 计划任务每日调用一次)

_VERSION="20260919"


import argparse
import json
import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../code/src
if parentdir not in sys.path:
    sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #setdefaultencoding('utf-8')

from chmonitor import monitorService


def main(argv = None):
    parser = argparse.ArgumentParser(description = "contentHub 每日巡检(单次执行; 首期降级口径)")
    parser.add_argument("--json", action = "store_true", help = "以 JSON 输出完整报告")
    parser.add_argument("--channel", type = str, default = "",
                        help = "告警通道名(log/email/wecom; email/wecom 为占位实现, 不发网络请求)")
    args = parser.parse_args(argv)

    report = monitorService.runDailyCheck({"alertChannel": args.channel})
    if args.json:
        print(json.dumps(report, ensure_ascii = False, indent = 2))
    else:
        print(monitorService.formatReportText(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
