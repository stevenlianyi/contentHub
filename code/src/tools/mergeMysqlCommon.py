#! /usr/bin/env python3
#encoding: utf-8

#Filename: mergeMysqlCommon.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   把 database/auto_generated/auto_gen_code_*.py 的「数据层段」合并进
#common/mysqlCommon.py 的自动生成区(由 BEGIN/END 标记包裹), 供表结构变更后重复执行。
#说明: 除 12 张 ch_* 表外, 还包含外部既有表 weixin_pay(定义 database/weixin_pay.txt);
#      USER_BASIC 不是生成件(其为手写段, 见 mysqlCommon.py 的 user family), 故不在此列表。
#
#为什么需要本工具:
#  红线 R1 要求「改表只改 database/ch_*.txt -> 重跑生成器 -> 合并 mysqlCommon」, 人工逐次
#  合并 12 张表极易漏项; 本工具让该流程可重复且可校验, 同时把手写段(公共件 + 扩展查询)
#  与生成段物理隔离, 重跑不会覆盖手写代码。
#
#合并规则:
#  1. 只取产物中 `#mysqlCommon code begin` 与 `#mysqlCommon code end` 之间的内容
#     (不含 http interface / testMysql / insert 等段落 —— 接口处理段由 SP1.5 装配到
#      main/subfunc/crudApi.py);
#  2. 丢弃产物自带的 query_{table}(...) —— 其 LIMIT 拼装在生成器里被注释掉(主计划 3.5.4 坑2),
#     本项目统一改由 mysqlCommon.py 手写段的扩展 query_ch_* 提供;
#  3. 校验每张表 7 个数据层函数齐全、且不含 func{Title}{Add/Del/Modify/Qry} 处理器。
#
#用法: python tools/mergeMysqlCommon.py   (工作目录不限, 脚本内按自身位置定位工程根)

_VERSION="20260918"

import os
import sys

_processorPID = os.getpid()

#表顺序: 前 12 张与 config/basicSettings.py 的 _CRUD_TITLES 一致(仅用于稳定输出顺序);
#weixin_pay 为「外部既有表」移植(见 plan.md §11), 排在最后
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
    #外部既有表(非 ch_* 命名规范): 表定义 database/weixin_pay.txt, 数据层由生成器产出
    "weixin_pay",
]

#每张表在数据层应具备的函数(前缀匹配, 实际函数名带表名)
REQUIRED_FUNC_PREFIX_LIST = [
    "def tablename_convertor_",
    "def decode_tablename_",
    "def create_",
    "def drop_",
    "def delete_",
    "def insert_",
    "def update_",
]

#不应出现在数据层段的 REST 处理器前缀(出现即为合并范围出错)
FORBIDDEN_FUNC_PREFIX = "def func"

SECTION_BEGIN = "#===== auto-generated sections begin (由 tools/mergeMysqlCommon.py 生成, 请勿手改) ====="
SECTION_END = "#===== auto-generated sections end ====="

MYSQL_COMMON_BEGIN = "#mysqlCommon code begin"
MYSQL_COMMON_END = "#mysqlCommon code end"


def readText(filePath):
    """容错读取生成产物:
       生成器写文件时未指定编码(不能改生成器), 在 Windows 上产物会是 GBK(cp936),
       在 Linux 上则是 UTF-8; 本工具统一按 utf-8 -> gbk -> latin-1 依次尝试,
       并统一以 UTF-8 写回 mysqlCommon.py, 避免混合编码导致模块无法编译。"""
    with open(filePath, "rb") as hFile:
        raw = hFile.read()
    for encoding in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors = "replace")


def writeText(filePath, text):
    with open(filePath, "w", encoding = "utf-8", newline = "\n") as hFile:
        hFile.write(text)


def extractDataLayerSection(filePath, tableName):
    """从生成产物中抽取数据层段(含表名 begin/end 注释), 并剔除生成版 query_*"""
    text = readText(filePath)
    lines = text.split("\n")

    beginIdx = -1
    endIdx = -1
    for idx, line in enumerate(lines):
        if MYSQL_COMMON_BEGIN in line:
            beginIdx = idx
        if MYSQL_COMMON_END in line:
            endIdx = idx
            break
    if beginIdx < 0 or endIdx < 0 or endIdx <= beginIdx:
        raise RuntimeError(f"[merge] 产物缺少 mysqlCommon 段落标记: {filePath}")

    sectionLines = lines[beginIdx + 1: endIdx]

    #剔除生成版 query_{table}: 连同其上方注释一起删, 但保留 "#{tableName} end" 收尾标记
    queryIdx = -1
    for idx, line in enumerate(sectionLines):
        if line.startswith(f"def query_{tableName}("):
            queryIdx = idx
            break
    if queryIdx < 0:
        raise RuntimeError(f"[merge] 产物缺少 query_{tableName}(): {filePath}")

    cutIdx = queryIdx
    while cutIdx > 0 and sectionLines[cutIdx - 1].strip().startswith("#"):
        cutIdx -= 1

    tailMarker = f"#{tableName} end"
    tailIdx = -1
    for idx in range(len(sectionLines) - 1, queryIdx, -1):
        if sectionLines[idx].strip() == tailMarker:
            tailIdx = idx
            break
    if tailIdx < 0:
        raise RuntimeError(f"[merge] 产物缺少 {tailMarker} 收尾标记: {filePath}")

    sectionLines = sectionLines[:cutIdx] + [tailMarker]
    return "\n".join(sectionLines).strip("\n")


def checkSection(sectionText, tableName):
    for prefix in REQUIRED_FUNC_PREFIX_LIST:
        if prefix not in sectionText:
            raise RuntimeError(f"[merge] {tableName} 数据层缺少函数: {prefix}...")
    if f"def query_{tableName}(" in sectionText:
        raise RuntimeError(f"[merge] {tableName} 数据层仍残留生成版 query_{tableName}()")
    for line in sectionText.split("\n"):
        if line.startswith(FORBIDDEN_FUNC_PREFIX):
            raise RuntimeError(f"[merge] {tableName} 数据层混入 REST 处理器: {line.strip()}")


def main():
    scriptDir = os.path.dirname(os.path.abspath(__file__))
    srcDir = os.path.dirname(scriptDir)
    autoGenDir = os.path.join(srcDir, "database", "auto_generated")
    mysqlCommonPath = os.path.join(srcDir, "common", "mysqlCommon.py")

    if not os.path.isfile(mysqlCommonPath):
        raise RuntimeError(f"[merge] 未找到手写段文件: {mysqlCommonPath}")

    sections = []
    for tableName in TABLE_NAME_LIST:
        productPath = os.path.join(autoGenDir, f"auto_gen_code_{tableName}.py")
        if not os.path.isfile(productPath):
            raise RuntimeError(f"[merge] 缺少生成产物: {productPath} (请先执行 tools/genTableCode.ps1)")
        sectionText = extractDataLayerSection(productPath, tableName)
        checkSection(sectionText, tableName)
        sections.append(sectionText)
        print(f"[merge] PID:{_processorPID} ok {tableName} lines:{len(sectionText.splitlines())}")

    generatedBlock = SECTION_BEGIN + "\n\n" + "\n\n\n".join(sections) + "\n\n" + SECTION_END

    text = readText(mysqlCommonPath)
    beginPos = text.find(SECTION_BEGIN)
    endPos = text.find(SECTION_END)
    if beginPos < 0 or endPos < 0 or endPos < beginPos:
        raise RuntimeError("[merge] mysqlCommon.py 中未找到自动生成区标记, 请先恢复标记行")

    newText = text[:beginPos] + generatedBlock + text[endPos + len(SECTION_END):]
    writeText(mysqlCommonPath, newText)

    print(f"[merge] PID:{_processorPID} done: {len(TABLE_NAME_LIST)} tables -> {mysqlCommonPath}")


if __name__ == "__main__":
    main()
