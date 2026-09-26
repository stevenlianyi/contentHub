#! /usr/bin/env python3
#encoding: utf-8

#Filename: initTables.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub 建表脚本: 按 database/ch_*.txt 经生成器产出的 create_ch_* 逐表建表。
#本轮追加外部既有表(见 plan.md §11): weixin_pay(生成段, database/weixin_pay.txt) 与
#USER_BASIC(手写段, database/userBasic.txt, 建表函数 createUserBasic())。
#
#★★ 破坏性操作红线 ★★
#  1. 本脚本只调用 create_ch_*(CREATE TABLE IF NOT EXISTS), **禁止**出现任何 drop_* 调用;
#  2. 生成器不提供 migration: 生产库改表须走「备份 + 测试库演练 + 保留回滚 DDL」三步
#     (主计划 8.6);
#  3. 执行前务必确认 _SYS 指向目标库(脚本会打印环境与库名)。
#
#用法: cd code/src && python tools/initTables.py

_VERSION="20260918"

import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)

from config import basicSettings as settings
from config import mysqlSettings as mysqlSettings

from common import mysqlCommon as comMysql

_processorPID = os.getpid()

#建表顺序: 无外键约束, 顺序仅影响可读性; 按业务链路排列
TABLE_NAME_LIST = [
    "ch_topic",
    "ch_topic_asset",
    "ch_asset",
    "ch_layout",
    "ch_platform",
    "ch_render_job",
    "ch_artifact",
    "ch_account",
    "ch_publish_record",
    "ch_mcp_token",
    "ch_audit_log",
    "ch_topic_version",
]

#外部既有表(无 ch_ 前缀, 不套 ch_* 的 recID/尾部七字段规范; 见 plan.md §11):
#  weixin_pay : 生成段建表(create_weixin_pay(tableName)), 调用方式与 ch_* 相同;
#  USER_BASIC : 手写段建表(createUserBasic(), 无参数), 其 DDL 列集合与 database/userBasic.txt 逐列一致。
EXTRA_GENERATED_TABLE_LIST = ["weixin_pay"]
EXTRA_HANDWRITTEN_TABLE_LIST = ["USER_BASIC"]
EXTRA_HANDWRITTEN_FUNC_MAP = {"USER_BASIC": "createUserBasic"}


def createOneTable(tableName):
    """按表名调用生成器产出的 create_{tableName}(tableName)"""
    result = False
    convertorName = f"tablename_convertor_{tableName}"
    createFuncName = f"create_{tableName}"

    convertor = getattr(comMysql, convertorName, None)
    createFunc = getattr(comMysql, createFuncName, None)

    if convertor is None or createFunc is None:
        print(f"[initTables] MISS {tableName}: 缺少 {convertorName} 或 {createFuncName} (请先跑生成器并合并)")
        return result

    try:
        result = createFunc(convertor())
        if result:
            print(f"[initTables] OK   {tableName}")
        else:
            print(f"[initTables] FAIL {tableName}")
    except Exception as e:
        print(f"[initTables] FAIL {tableName}: {e}")
        result = False

    return result


def createHandwrittenTable(tableName):
    """手写段建表(当前仅 USER_BASIC -> createUserBasic())"""
    result = False
    createFuncName = EXTRA_HANDWRITTEN_FUNC_MAP.get(tableName, "")

    createFunc = getattr(comMysql, createFuncName, None) if createFuncName else None

    if createFunc is None:
        print(f"[initTables] MISS {tableName}: 缺少手写建表函数 {createFuncName}()")
        return result

    try:
        result = createFunc()
        if result:
            print(f"[initTables] OK   {tableName} (handwritten)")
        else:
            print(f"[initTables] FAIL {tableName} (handwritten)")
    except Exception as e:
        print(f"[initTables] FAIL {tableName} (handwritten): {e}")
        result = False

    return result


def main():
    print(f"[initTables] PID:{_processorPID}, _SYS:{settings._SYS}, FILE_SYSTEM_MODE:{settings.FILE_SYSTEM_MODE}")
    print(f"[initTables] writeDB:{mysqlSettings.MYSQL_WRITE_DB}, readDB:{mysqlSettings.MYSQL_READ_DB}")

    if mysqlSettings.mysqlDB is None:
        print("[initTables] 未建立数据库连接(MYSQL_SKIP_CONNECT=1): 请先关闭该开关再执行建表")
        return 1

    totalNum = len(TABLE_NAME_LIST) + len(EXTRA_GENERATED_TABLE_LIST) + len(EXTRA_HANDWRITTEN_TABLE_LIST)

    okCount = 0
    for tableName in TABLE_NAME_LIST + EXTRA_GENERATED_TABLE_LIST:
        if createOneTable(tableName):
            okCount += 1

    for tableName in EXTRA_HANDWRITTEN_TABLE_LIST:
        if createHandwrittenTable(tableName):
            okCount += 1

    print(f"[initTables] done: ok={okCount}, total={totalNum}")
    return 0 if okCount == totalNum else 1


if __name__ == "__main__":
    sys.exit(main())
