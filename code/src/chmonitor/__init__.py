#! /usr/bin/env python3
#encoding: utf-8:

#Filename: __init__.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 监控告警包(SP4c · 主计划 P3-8 / 8.7 监控告警)。
#
#★ 命名说明(重要): 本包**原名 `monitor/`**, 本轮为接收由 museum/code/src/monitor 迁移改造的运维监控代码,
#  已重命名为 **`chmonitor/`**(contentHub 监控核心); `monitor/` 现为「museum 迁移改造后的运维监控/守护」层。
#  两层分工: `chmonitor/` = 七项指标/告警通道/心跳/每日巡检(SP4c 核心); `monitor/` = 文件变化守护 + 告警汇总(复用 chmonitor)。

#包职责与分层契约:
#  - 本包为「监控告警」层, 依赖 业务层(processor/)、公共层(common/) 与 调度层(schedule/, 仅取心跳/数据);
#  - **不得 import main/subfunc**(接入层); 关键路径不得因监控不可用而阻塞;
#  - 首期按主计划降级口径实现: **日志落盘告警 + 每日巡检脚本 + 可插拔通知接口(占位)**,
#    **不做看板/时序数据库**, **不引入新中间件依赖**, **不发起任何对外网络请求**;
#  - 全部阈值/周期/保留期来自 config/opsSettings.py(禁止散落硬编码)。

#当前落点:
#  chmonitor/metrics.py         七项指标判定(纯函数; 阈值可配; 输出 指标名/当前值/阈值/级别/建议动作)
#  chmonitor/alertChannel.py    ★ 可插拔告警通知接口(日志通道默认; email/wecom 为占位, 不发网络请求)
#  chmonitor/heartbeat.py       ★ 定时任务最后成功时间心跳(供「定时任务」指标判定)
#  chmonitor/monitorService.py  指标采集 + 每日汇总(runDailyCheck)
#  chmonitor/dailyCheck.py      ★ 每日巡检脚本(单次执行 -> 汇总报告落 code/data/monitor/)

_VERSION="20260919"
