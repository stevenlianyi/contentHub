#! /usr/bin/env python3
#encoding: utf-8

#Filename: mergeCrudApi.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   把 database/auto_generated/auto_gen_code_ch_*.py 的「REST 接口处理段」合并进
#main/subfunc/crudApi.py 的自动生成区(由 BEGIN/END 标记包裹), 供表结构变更后重复执行。
#
#为什么需要本工具(与 tools/mergeMysqlCommon.py 同构):
#  红线 R1 要求「改表只改 database/ch_*.txt -> 重跑生成器 -> 合并」; 12 张表的 REST 处理段
#  合计约 5000 行, 人工合并必漏项。本工具让该流程可重复、可校验, 同时把手写头部(符号导入)
#  与生成段物理隔离, 重跑不会覆盖手写代码(方案 R6)。
#
#合并规则:
#  1. 只取产物中 `#http interface code begin` 与 `#http interface code end` 之间的内容
#     (数据层段由 tools/mergeMysqlCommon.py 负责, 两工具互不重叠);
#  2. 校验每张表 4 个处理器 func{Title}{Add|Del|Modify|Qry} 齐全、且不含其它表的处理器;
#  3. 依据 _CRUD_TITLES(扣除 EXCLUDED_TABLE_LIST 的接管表)生成 CMD_MAP
#     ("{title}{add|del|modify|qry}" -> func{Title}{Op}), 使「注册表」与「处理器」永远同名同序,
#     避免手抄漏项。
#
#★ 业务域接管(SP2a + SP2b, 见 code/src/plan.md §7/§9):
#  ch_topic / ch_topic_version 的 4+4 个端点由 main/subfunc/topicApi.py 接管(内部走
#  processor/topicService.py), 以便「字段区间校验 / 状态机 / wordCount / topicCode 幂等 /
#  版本快照」在 HTTP 路径上真实生效。
#  ch_asset / ch_topic_asset 的 4+4 个端点由 main/subfunc/assetApi.py 接管(内部走
#  processor/assetService.py), 以便「contentHash 内容级去重 / 规格裁剪 / EXIF 剥离 / 缩略图 /
#  fileSystem 快照 / assetKey 幂等 / sortOrder 排序 / usageType 语义」在 HTTP 路径上真实生效。
#  若本工具仍为这四张表生成处理器与 CMD_MAP, 聚合器 subfunc/__init__.py 的 V1 冲突校验
#  会在导入期直接抛 RuntimeError(服务起不来)。
#  因此本工具将四张表列入 EXCLUDED_TABLE_LIST: crudApi 只装配其余 8 张表(32 条 CMD)。
#  端点总数不变(仍是 69 = crud 32 + topic 域 9 + asset 域 9 + 账号域 16 + 其余业务域 3)。
#
#用法: cd code/src && python tools/mergeCrudApi.py   (工作目录不限, 脚本内按自身位置定位工程根)

_VERSION="20260918"

import os
import sys

_processorPID = os.getpid()

#表顺序: 与 config/basicSettings.py 的 _CRUD_TITLES 一致(仅用于稳定输出顺序)
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

#_CRUD_TITLES: 去 ch_ 前缀 + 去全部下划线(与生成器 -t 参数、basicSettings._CRUD_TITLES 一致)
CRUD_TITLE_LIST = [
    "topic", "topicasset", "asset", "layout",
    "platform", "renderjob", "artifact", "account",
    "publishrecord", "mcptoken", "auditlog", "topicversion",
]

#★ 业务域接管的表: 不装配进 crudApi(分别由 topicApi / assetApi 接管, 见文件头说明)
EXCLUDED_TABLE_LIST = [
    "ch_topic",
    "ch_topic_version",
    "ch_asset",
    "ch_topic_asset",
]

#每张表的 4 个 REST 操作(后缀 -> cmd 后缀小写)
CRUD_OP_LIST = [("Add", "add"), ("Del", "del"), ("Modify", "modify"), ("Qry", "qry")]

HTTP_SECTION_BEGIN = "#http interface code begin"
HTTP_SECTION_END = "#http interface code end"

SECTION_BEGIN = "#===== auto-generated crud sections begin (由 tools/mergeCrudApi.py 生成, 请勿手改) ====="
SECTION_END = "#===== auto-generated crud sections end ====="


def readText(filePath):
    """容错读取生成产物:
       生成器写文件时未指定编码(不能改生成器), 在 Windows 上产物会是 GBK(cp936),
       在 Linux 上则是 UTF-8; 本工具统一按 utf-8 -> gbk -> latin-1 依次尝试,
       并统一以 UTF-8 写回 crudApi.py, 避免混合编码导致模块无法编译。"""
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


def funcTitleOf(title):
    """topic -> Topic, topicasset -> Topicasset(与生成器一致: 仅首字母大写)"""
    return title[0].upper() + title[1:]


def extractHttpSection(filePath, tableName):
    """从生成产物中抽取 REST 接口处理段"""
    text = readText(filePath)
    lines = text.split("\n")

    beginIdx = -1
    endIdx = -1
    for idx, line in enumerate(lines):
        if HTTP_SECTION_BEGIN in line:
            beginIdx = idx
        if HTTP_SECTION_END in line:
            endIdx = idx
            break
    if beginIdx < 0 or endIdx < 0 or endIdx <= beginIdx:
        raise RuntimeError(f"[merge] 产物缺少 http interface 段落标记: {filePath}")

    sectionLines = lines[beginIdx + 1: endIdx]
    sectionText = "\n".join(sectionLines).strip("\n")
    if not sectionText:
        raise RuntimeError(f"[merge] {tableName} 的 http interface 段落为空")

    return sectionText


def checkSection(sectionText, title):
    """校验: 4 个处理器齐全, 且无不属于本表的处理器"""
    funcTitle = funcTitleOf(title)
    errList = []

    for op, _cmdSuffix in CRUD_OP_LIST:
        if f"def func{funcTitle}{op}(" not in sectionText:
            errList.append(f"def func{funcTitle}{op}(")

    for line in sectionText.split("\n"):
        if line.startswith("def func"):
            funcName = line[len("def "):].split("(")[0]
            if not funcName.startswith(f"func{funcTitle}"):
                errList.append(f"混入非本表处理器 {funcName}")

    if errList:
        raise RuntimeError(f"[merge] {title} 处理段校验失败: {'; '.join(errList)}")


def genCmdMapBlock(titleList):
    """依据 title 清单(已扣除业务域接管表)生成 CMD_MAP, 与处理器同名同序"""
    lines = []
    lines.append("#----- CMD 注册表(依据 config/basicSettings.py::_CRUD_TITLES 派生, 与上方处理器同名同序) -----")
    lines.append("#说明: key 为对外命令字({title}{add|del|modify|qry}), value 为生成器产出的处理器对象;")
    lines.append("#      本段由 tools/mergeCrudApi.py 生成, 请勿手改。")
    lines.append("CMD_MAP = {")
    for idx, title in enumerate(titleList):
        funcTitle = funcTitleOf(title)
        if idx > 0:
            lines.append("")
        for op, cmdSuffix in CRUD_OP_LIST:
            lines.append(f'    "{title}{cmdSuffix}": func{funcTitle}{op},')
    lines.append("}")
    return "\n".join(lines)


def activeTablePairs():
    """返回 (tableName, title) 清单, 扣除业务域接管的表(EXCLUDED_TABLE_LIST)"""
    pairs = []
    for idx, tableName in enumerate(TABLE_NAME_LIST):
        if tableName in EXCLUDED_TABLE_LIST:
            continue
        pairs.append((tableName, CRUD_TITLE_LIST[idx]))
    return pairs


def main():
    scriptDir = os.path.dirname(os.path.abspath(__file__))
    srcDir = os.path.dirname(scriptDir)
    autoGenDir = os.path.join(srcDir, "database", "auto_generated")
    crudApiPath = os.path.join(srcDir, "main", "subfunc", "crudApi.py")

    if not os.path.isfile(crudApiPath):
        raise RuntimeError(f"[merge] 未找到 crudApi.py(手写头部需先存在): {crudApiPath}")

    tablePairs = activeTablePairs()
    activeTitleList = [title for _tableName, title in tablePairs]

    for tableName in EXCLUDED_TABLE_LIST:
        if tableName in TABLE_NAME_LIST:
            print(f"[merge] PID:{_processorPID} skip {tableName} (业务域接管, 见 EXCLUDED_TABLE_LIST)")

    sections = []
    for tableName, title in tablePairs:
        productPath = os.path.join(autoGenDir, f"auto_gen_code_{tableName}.py")
        if not os.path.isfile(productPath):
            raise RuntimeError(f"[merge] 缺少生成产物: {productPath} (请先执行 tools/genTableCode.ps1)")

        sectionText = extractHttpSection(productPath, tableName)
        checkSection(sectionText, title)

        sections.append(f"#{title}({tableName}) CRUD begin\n\n{sectionText}\n\n#{title}({tableName}) CRUD end")
        print(f"[merge] PID:{_processorPID} ok {tableName} lines:{len(sectionText.splitlines())}")

    generatedBlock = (SECTION_BEGIN + "\n\n"
                      + "\n\n\n".join(sections)
                      + "\n\n\n" + genCmdMapBlock(activeTitleList)
                      + "\n\n" + SECTION_END)

    text = readText(crudApiPath)
    beginPos = text.find(SECTION_BEGIN)
    endPos = text.find(SECTION_END)
    if beginPos < 0 or endPos < 0 or endPos < beginPos:
        raise RuntimeError("[merge] crudApi.py 中未找到自动生成区标记, 请先恢复标记行")

    newText = text[:beginPos] + generatedBlock + text[endPos + len(SECTION_END):]
    writeText(crudApiPath, newText)

    cmdTotal = len(tablePairs) * len(CRUD_OP_LIST)
    print(f"[merge] PID:{_processorPID} done: {len(tablePairs)} tables / {cmdTotal} CMD "
          f"(excluded: {EXCLUDED_TABLE_LIST}) -> {crudApiPath}")


if __name__ == "__main__":
    main()
