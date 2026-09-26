#! /usr/bin/env python3
#encoding: utf-8

#Filename: __init__.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 业务处理器层(processor/)包声明。
#
#分层契约(见 plan/contentHub开发计划.md 3.1 分层架构 与 code/src/plan.md §3):
#  接入层(main/) -> 业务处理器层(processor/) -> 引擎层(engine/) -> 公共层(common/)
#本层只承载「领域业务规则」(校验/状态机/幂等/编排), **不写 HTTP 报文封装**(归 main/subfunc/apiCommon.py),
#**不写裸 SQL**(红线 R1: 数据库只经 common/mysqlCommon.py), **不做厂商分支**(红线 R2: 文件只经 common/fileStorageCommon.py)。
#
#本轮(SP2a)落点: topicService.py(C2 主题管理)。后续子计划: assetService.py(C3) / publishService.py(C6) /
#complianceService.py(C8) / platformAdapter/(C5)。

_VERSION="20260919"
