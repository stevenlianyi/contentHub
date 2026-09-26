#! /usr/bin/env python3
#encoding: utf-8:

#Filename: __init__.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 调度层包(SP3c 首次创建)。

#包职责与分层契约:
#  - 本包为「常驻调度/后台消费」层, 依赖 业务层(processor/) 与 公共层(common/);
#  - **不得 import main/subfunc**(接入层) —— 调度进程与 Web 进程相互独立;
#  - 本包只做「取任务 -> 加锁 -> 调用业务层执行 -> 收口状态」, 业务规则一律在 processor/ 内;
#  - 与 Web 进程相同: 数据库只经 common/mysqlCommon.py, Redis 只经 common/redisCommon.py(且必须可降级),
#    文件只经 common/fileStorageCommon.py(由 processor/engine 间接使用)。
#
#当前落点:
#  schedule/renderWorker.py     渲染任务常驻消费者(ch_render_job: PENDING -> RUNNING -> DONE/FAILED)
#  schedule/credentialCheck.py  ★ SP4b(P3-6) 凭据健康巡检(公众号只读探活 + healthStatus/EXPIRING·INVALID
#                               分级告警 + 小红书跳过说明; Redis 锁可降级; __main__ 单次执行)
#                               ★ SP4c P3-6/P3-8: 守护化(--loop 常驻 + 单次入口), 告警对接 chmonitor/alertChannel
#                               并刷新 monitor 心跳
#  schedule/archive.py          ★ SP4c(P3-7) 归档清理(ch_audit_log 分批导出+删除 / ch_artifact 过期清理)
#                               ★★ 破坏性操作**默认 dry-run**, 真删须 --execute 或 CH_ARCHIVE_EXECUTE=1;
#                               先导出上传成功才删除; 归档/清理动作写 ch_audit_log; Redis 锁可降级
#
#后续落点(尚未实现, 见 plan.md §9): 其余运维脚本按需追加。

_VERSION="20260919"
