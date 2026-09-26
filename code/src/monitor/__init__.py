#! /usr/bin/env python3
#encoding: utf-8:

#Filename: __init__.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 运维监控 / 守护层(由 museum/code/src/monitor 迁移并改造为 contentHub 口径)。

#★ 来源与迁移说明:
#  - 源目录: `ylwzProject/museum/code/src/monitor`
#    (`monitor.py` / `alert.py` / `monitorConfig.py` / `crontab.txt` / `restore_monitor.sh`);
#  - ★ 改造(保持 contentHub「监控层零对外网络」红线):
#      ① 剥离网络请求(HTTP 探活)、套接字端口探测、子进程调用与进程 kill 等原语;
#      ② 剥离 museum 专属配置与 museum 业务表(mu_ 前缀)依赖, 改为复用 contentHub 的 `chmonitor/` 与 `config/opsSettings.py`;
#      ③ 原「进程 / 端口 / 服务守护」函数改为**显式不支持并记日志**(不静默、不误报)。
#  - 与 chmonitor/ 的分工:
#      `chmonitor/` = 七项指标 + 告警通道 + 心跳 + 每日巡检(SP4c P3-8 核心);
#      `monitor/`   = 文件变化守护(纯 os.path) + 告警汇总(复用 chmonitor) + 部署样例(crontab / restore)。
#
#★ 分层契约: 只依赖 config/ 与 chmonitor/(懒加载); **不 import main/subfunc**。

_VERSION="20260919"
