#! /usr/bin/env python3
#encoding: utf-8

#Filename: mysqlCommon.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub(内容中枢) 全库读写唯一入口。
#
#组成:
#  1) 手写段(本文件上半部): 模块头 + 公共件 + 12 张 ch_* 表的扩展查询函数 query_ch_*
#  2) 生成段(本文件下半部, 由 #===== auto-generated sections 标记包裹):
#     由 database/ch_*.txt 经 database/mysqlCodeGenerator.py 产出, 再由
#     tools/mergeMysqlCommon.py 合并进来(tablename_convertor_/decode_/create_/drop_/delete_/insert_/update_)
#
#红线(主计划 1.5 与 3.5):
#  R1 本模块是业务层访问数据库的唯一入口, 业务代码禁止裸 SQL;
#  R3 生成段一律由 `-i ch_*.txt` 的 readFromFile() 路径产出, 禁止走 handleSQL();
#  ★ 表结构变更流程: 改 database/ch_*.txt -> 重跑 tools/genTableCode.ps1 -> 重跑
#    tools/mergeMysqlCommon.py(覆盖生成段) -> 手写段按需同步(检索列/短列清单)。
#
#生成器已知坑的处置(主计划 3.5.4):
#  坑2 生成的 query_* 内 LIMIT 拼装被注释掉 -> 本项目 query_ch_* 全部由手写段提供,
#     统一经 queryTableGeneral 叠加 delFlag 过滤 + ORDER BY + LIMIT, 不再使用生成版 query;
#  坑3 insert_*/update_* 对数值列强制 int()/float() 且异常置 0 -> 可空数值列(width/height/
#     sizeBytes/costMs/progress 等)业务层统一约定「0 = 未设置」。

_VERSION="20260920"

import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import re
import traceback

#global defintion/common var etc.
from common import globalDefinition as comGD

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#setting files
from config import mysqlSettings as mysqlSettings

from config import basicSettings as settings

HOME_DIR = settings._HOME_DIR

if "_LOG" not in dir() or not _LOG:
    #setLogNew(title, filebasename, homeDir) 第三参是"日志目录"(不是文件路径)
    try:
        logDir = os.path.join(settings._CODE_DIR, "log")
        _LOG = misc.setLogNew("CHMYSQL", comGD._DEF_GENRAL_MYSQL_LOG_NAME, logDir)
    except Exception:
        _LOG = None

_DEBUG = settings._DEBUG

auto_increment_default_value = 10000

SYS_DEFAULT_AUTO_LOGINID = settings.SYS_DEFAULT_AUTO_LOGINID

if "mysqlDB" not in dir() or not mysqlDB:
    mysqlDB = mysqlSettings.mysqlDB

database_name = mysqlSettings.MYSQL_READ_DB

#查询条件运算符白名单(字段名另做正则校验, 条件值一律走参数化占位符)
_DEF_QUERY_OPERATOR_LIST = ["=", "!=", ">", "<", ">=", "<=", "LIKE"]
#字段名合法性: 只允许字母开头的字母/数字/下划线组合, 避免拼接字段名引入注入
_DEF_QUERY_FIELD_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
#审计日志为大表(千万级), 默认 LIMIT 收紧到 5000(主计划 3.4.6 / 6.4 R-10)
_DEF_CH_AUDIT_LOG_QUERY_LIMIT_NUM = 5000


#common begin

def toIntSafe(value, default = 0):
    """数值安全转换: 任意输入转 int, 失败返回 default
       (与生成器「异常置 0」的口径一致, 可空数值列统一约定 0 = 未设置)"""
    result = default
    try:
        result = int(value)
    except Exception:
        result = default
    return result


def dataFormatConvert(dataList):
    """查询结果出参归一: 数值转字符串, None 转空串, 指定列 JSON 文本转对象"""
    result = dataList
    for data in dataList:
        for k, v in data.items():
            if isinstance(v, int):
                data[k] = str(v)
            if isinstance(v, float):
                data[k] = str(v)
            if v == None:
                data[k] = ""
            if k in ["position", "regPosition", "fileIDList"]:
                if v:
                    v = v.replace("'", "\"")
                    data[k] = misc.jsonLoads(v)
    result = dataList
    return result


#本工程所有 JSON 类型列的统一名单(源自 database/ch_*.txt 表定义), 写库时据此做归一化
#新增 JSON 列时请在此追加, 否则空串仍会被当成非法 JSON 报错(MySQL 错误 3140)
MYSQL_JSON_COLUMN_NAME_LIST = [
    "requestJson",      #ch_publish_record
    "responseJson",     #ch_publish_record
]
MYSQL_JSON_COLUMN_NAME_SET = set(MYSQL_JSON_COLUMN_NAME_LIST)


def normalizeJsonValue4DB(v):
    """JSON 列值写库前归一化:
       缺省/None/空串 -> None(落库为 SQL NULL, 避免 '' 被 JSON 校验拒绝)
       dict/list     -> json.dumps 成 JSON 文本
       其它(已是合法 JSON 文本) -> 原样返回"""
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        try:
            return misc.jsonDumps(v)
        except Exception:
            return None
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


def chkTableExist(tableName):
    """表是否存在(建表脚本用于回报结果)"""
    result = False
    sqlStr = "SELECT table_name FROM information_schema.TABLES WHERE table_schema = %s and table_name = %s;"
    rtn = mysqlDB.executeRead(sqlStr, (database_name, tableName))
    if rtn > 0:
        result = True
    return result


def dropTableGeneral(tableName):
    """删除表(破坏性操作入口)
       ★★ 生产库禁止调用 ★★ 仅保留给测试库/本地库做建表演练"""
    result = False
    try:
        sqlStr = "DROP TABLE %s;" % tableName
        rtn = mysqlDB.executeWrite(sqlStr)
        rtn = chkTableExist(tableName)
        if rtn == False:
            result = True
    except Exception as e:
        pass
    return result


def insertTableGeneral(tableName, dataSet, selfDefinedPrimaryKey = comGD._CONST_NO):
    """通用插入: 参数化拼装, JSON 列自动归一化, 返回自增主键(失败返回 0)"""
    result = 0
    try:
        insertStr = ("INSERT INTO %s (" % tableName)
        fieldNameList = [insertStr]
        placeHolderList = []
        valuesList = []

        for k, v in dataSet.items():
            #JSON 列: 空串为非法 JSON, 归一为 NULL; dict/list 自动转 JSON 文本
            if k in MYSQL_JSON_COLUMN_NAME_SET:
                v = normalizeJsonValue4DB(v)
            fieldNameList.append(k)
            fieldNameList.append(",")
            valuesList.append(v)
            placeHolderList.append("%s")
            placeHolderList.append(",")

        fieldNameList = fieldNameList[0:-1]
        fieldNameList.append(")  VALUES (" )
        placeHolderList = placeHolderList[0:-1]
        fieldNameList.extend(placeHolderList)
        fieldNameList.append(")")
        sqlStr = "".join(fieldNameList)
        rtn = mysqlDB.executeWrite(sqlStr, tuple(valuesList))

        if rtn > 0:
            if selfDefinedPrimaryKey == comGD._CONST_NO:
                result = mysqlDB.insertID()
            else:
                result = rtn

    except Exception as e:
        errMsg = '%s %s'%("insertTableGeneral", str(e))
        if _DEBUG and _LOG:
            _LOG.error(errMsg)

    return result


def updateTableGeneral(tableName, keySqlstr, keyValues, dataSet):
    """通用更新: keySqlstr 为 WHERE 条件片段(由调用方生成, 只含占位符),
       keyValues 为条件值列表, 返回受影响行数"""
    result = 0
    try:
        tempStr = "UPDATE %s SET " % tableName
        fieldNameList = [tempStr]
        valuesList = []
        for k, v in dataSet.items():
            #JSON 列归一化, 与 insertTableGeneral 保持一致
            if k in MYSQL_JSON_COLUMN_NAME_SET:
                v = normalizeJsonValue4DB(v)
            fieldNameList.append("%s = " % (k))
            fieldNameList.append("%s")
            fieldNameList.append(",")
            valuesList.append(v)

        fieldNameList = fieldNameList[0:-1]

        fieldNameList.append("  WHERE %s;" % (keySqlstr))
        valuesList.extend(keyValues)

        sqlStr = "".join(fieldNameList)
        rtn = mysqlDB.executeWrite(sqlStr, tuple(valuesList))
        result = rtn

    except Exception as e:
        errMsg = '%s %s'%("updateTableGeneral", str(e))
        if _DEBUG and _LOG:
            _LOG.error(errMsg)

    return result


def queryTableGeneral(tableName, condList = None, likeOrList = None, keyword = "",
                      columns = "*", delFlag = "0", order = "create",
                      limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
    """全部 query_ch_* 的公共实现(手写段核心):
       - condList:   [[字段名, 运算符, 值], ...], 运算符取 _DEF_QUERY_OPERATOR_LIST 白名单
       - likeOrList: 关键词模糊匹配的字段清单, 与 keyword 组成 (a LIKE %kw% OR b LIKE %kw%)
       - delFlag:    非空时叠加 (delFlag = 值 OR delFlag IS NULL); 传 "" 表示不过滤已删除
       - order:      modify -> modifyYMDHMS 降序; create -> recID 升序; 其他 -> recID 降序
       - limitNum:   LIMIT 条数, <=0 时回落 comGD._DEF_MAX_QUERY_LIMIT_NUM, 防止全表拉取
       说明: 字段名经 _DEF_QUERY_FIELD_PATTERN 校验, 条件值一律参数化, 不拼接字面量
    """
    result = []
    valuesList = []
    whereList = []
    sqlStr = "SELECT %s FROM %s " % (columns, tableName)

    try:
        for cond in (condList or []):
            try:
                fieldName = str(cond[0])
                operator = str(cond[1]).upper()
                fieldValue = cond[2]
            except Exception:
                continue
            if operator not in _DEF_QUERY_OPERATOR_LIST:
                continue
            if not _DEF_QUERY_FIELD_PATTERN.match(fieldName):
                continue
            if fieldValue in (None, ""):
                continue
            whereList.append(" %s %s %%s" % (fieldName, operator))
            valuesList.append(fieldValue)

        if keyword and likeOrList:
            orList = []
            for fieldName in likeOrList:
                if not _DEF_QUERY_FIELD_PATTERN.match(str(fieldName)):
                    continue
                orList.append(" %s LIKE %%s" % fieldName)
                valuesList.append("%" + str(keyword) + "%")
            if orList:
                whereList.append(" (" + " OR ".join(orList) + ")")

        if delFlag != "":
            whereList.append(" (delFlag = %s OR delFlag IS NULL)")
            valuesList.append(delFlag)

        if whereList:
            sqlStr += " WHERE " + " AND ".join(whereList)

        if order == "modify":
            sqlStr += " ORDER BY modifyYMDHMS DESC" 
        elif order == "create":
            sqlStr += " ORDER BY recID ASC"
        else:
            sqlStr += " ORDER BY recID DESC"

        limitNum = toIntSafe(limitNum, comGD._DEF_MAX_QUERY_LIMIT_NUM)
        if limitNum <= 0:
            limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM
        sqlStr += " LIMIT %s"
        valuesList.append(limitNum)

        rtn = mysqlDB.executeRead(sqlStr, tuple(valuesList))
        if rtn > 0:
            dataList = mysqlDB.fetchAll()
            dataList = dataFormatConvert(dataList)
            result = list(dataList)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        if _DEBUG and _LOG:
            _LOG.error(f"{tableName},{errMsg}")

    return result


def getShortColumns(mode, tableName):
    """mode 语义(对齐基线 queryUserBasic): short -> 少量关键列; 其余(含 full) -> 全列"""
    if mode == "short":
        return CH_QUERY_SHORT_COLUMNS.get(tableName, "*")
    return "*"


#short 模式的关键列清单(仅收敛列表接口的返回体积, 不改变过滤条件)
CH_QUERY_SHORT_COLUMNS = {
    "ch_topic": "recID,topicCode,title,status,publishStatus,coverFileID,coverThumbID,assetCount,wordCount,regYMDHMS",
    "ch_asset": "recID,fileID,thumbnailID,fileExt,origSizeBytes,width,height,processStatus,regYMDHMS",
    "ch_artifact": "recID,artifactKey,jobID,topicID,kind,platform,fileID,thumbnailID,seqNo,artifactStatus",
    "ch_audit_log": "recID,actor,source,action,targetType,targetID,result,costMs,regYMDHMS",
    "ch_publish_record": "recID,idempotencyKey,artifactId,topicID,platform,deliverMode,success,remoteID,pushedYMDHMS",
    "ch_render_job": "recID,jobCode,topicID,layoutCode,platform,jobStatus,progress,regYMDHMS",
    "ch_account": "recID,accountCode,platform,accountName,subjectType,verifiedFlag,capability,healthStatus",
    "ch_topic_asset": "recID,assetKey,topicID,fileID,usageType,sortOrder",
    "ch_layout": "recID,layoutCode,layoutName,layoutType,platform,outputKind,enabled,sortWeight",
    "ch_platform": "recID,platformCode,platformName,deliverMode,imageSpec,imageMaxCount,enabled",
    "ch_topic_version": "recID,verKey,topicID,versionNo,diffNote,ownerID,regYMDHMS",
    "ch_mcp_token": "recID,tokenName,tokenScope,projectCode,revokedYMDHMS",
}


#ch_topic 查询记录
def query_ch_topic(tableName, recID = "0", topicCode = "", status = "", publishStatus = "",
                   ownerID = "", categoryCode = "", keyword = "", beginYMDHMS = "", endYMDHMS = "",
                   delFlag = "0", mode = "full", order = "create",
                   limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
    condList = []
    recID = toIntSafe(recID, 0)
    if recID > 0:
        condList.append(["recID", "=", recID])
    condList.append(["topicCode", "=", topicCode])
    condList.append(["status", "=", status])
    condList.append(["publishStatus", "=", publishStatus])
    condList.append(["ownerID", "=", ownerID])
    condList.append(["categoryCode", "=", categoryCode])
    condList.append(["regYMDHMS", ">=", beginYMDHMS])
    condList.append(["regYMDHMS", "<=", endYMDHMS])
    return queryTableGeneral(tableName, condList = condList, likeOrList = ["title", "summary", "description"],
                             keyword = keyword, columns = getShortColumns(mode, tableName),
                             delFlag = delFlag, order = order, limitNum = limitNum)


#ch_topic_asset 查询记录
def query_ch_topic_asset(tableName, recID = "0", topicID = "", fileID = "", usageType = "",
                         delFlag = "0", mode = "full", order = "create",
                         limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
    condList = []
    recID = toIntSafe(recID, 0)
    topicID = toIntSafe(topicID, 0)
    if recID > 0:
        condList.append(["recID", "=", recID])
    if topicID > 0:
        condList.append(["topicID", "=", topicID])
    condList.append(["fileID", "=", fileID])
    condList.append(["usageType", "=", usageType])
    return queryTableGeneral(tableName, condList = condList, columns = getShortColumns(mode, tableName),
                             delFlag = delFlag, order = order, limitNum = limitNum)


#ch_asset 查询记录
#★ 2026-09-20 追加 keyword(origName/objectName 模糊) 与 fileExt 过滤: 素材图库 P-04 的搜索/类型筛选需要;
#  两者缺省 "" 时条件被自动跳过, 既有调用方零影响。
def query_ch_asset(tableName, recID = "0", fileID = "", contentHash = "", fileSystem = "",
                   processStatus = "", ownerID = "", keyword = "", fileExt = "",
                   delFlag = "0", mode = "full", order = "create",
                   limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
    condList = []
    recID = toIntSafe(recID, 0)
    if recID > 0:
        condList.append(["recID", "=", recID])
    condList.append(["fileID", "=", fileID])
    condList.append(["contentHash", "=", contentHash])
    condList.append(["fileSystem", "=", fileSystem])
    condList.append(["processStatus", "=", processStatus])
    condList.append(["ownerID", "=", ownerID])
    condList.append(["fileExt", "=", fileExt])
    return queryTableGeneral(tableName, condList = condList, likeOrList = ["origName", "objectName"],
                             keyword = keyword, columns = getShortColumns(mode, tableName),
                             delFlag = delFlag, order = order, limitNum = limitNum)


#ch_layout 查询记录
def query_ch_layout(tableName, recID = "0", layoutCode = "", layoutType = "", platform = "",
                    enabled = "", delFlag = "0", mode = "full", order = "create",
                    limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
    condList = []
    recID = toIntSafe(recID, 0)
    if recID > 0:
        condList.append(["recID", "=", recID])
    condList.append(["layoutCode", "=", layoutCode])
    condList.append(["layoutType", "=", layoutType])
    condList.append(["platform", "=", platform])
    condList.append(["enabled", "=", enabled])
    return queryTableGeneral(tableName, condList = condList, columns = getShortColumns(mode, tableName),
                             delFlag = delFlag, order = order, limitNum = limitNum)


#ch_platform 查询记录
def query_ch_platform(tableName, recID = "0", platformCode = "", deliverMode = "", enabled = "",
                      delFlag = "0", mode = "full", order = "create",
                      limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
    condList = []
    recID = toIntSafe(recID, 0)
    if recID > 0:
        condList.append(["recID", "=", recID])
    condList.append(["platformCode", "=", platformCode])
    condList.append(["deliverMode", "=", deliverMode])
    condList.append(["enabled", "=", enabled])
    return queryTableGeneral(tableName, condList = condList, columns = getShortColumns(mode, tableName),
                             delFlag = delFlag, order = order, limitNum = limitNum)


#ch_render_job 查询记录
def query_ch_render_job(tableName, recID = "0", jobCode = "", topicID = "", jobStatus = "",
                        platform = "", ownerID = "", beginYMDHMS = "", endYMDHMS = "",
                        delFlag = "0", mode = "full", order = "create",
                        limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
    condList = []
    recID = toIntSafe(recID, 0)
    topicID = toIntSafe(topicID, 0)
    if recID > 0:
        condList.append(["recID", "=", recID])
    if topicID > 0:
        condList.append(["topicID", "=", topicID])
    condList.append(["jobCode", "=", jobCode])
    condList.append(["jobStatus", "=", jobStatus])
    condList.append(["platform", "=", platform])
    condList.append(["ownerID", "=", ownerID])
    condList.append(["regYMDHMS", ">=", beginYMDHMS])
    condList.append(["regYMDHMS", "<=", endYMDHMS])
    return queryTableGeneral(tableName, condList = condList, columns = getShortColumns(mode, tableName),
                             delFlag = delFlag, order = order, limitNum = limitNum)


#ch_artifact 查询记录
#★ SP4c 追加可选筛选 expireBeforeYMDHMS: 过期清理(archive.py)按 expireYMDHMS <= 阈值取到期产物;
#  缺省 "" 时该条件被自动跳过, 既有调用方零影响。
def query_ch_artifact(tableName, recID = "0", jobID = "", topicID = "", kind = "", platform = "",
                      artifactStatus = "", expireBeforeYMDHMS = "", delFlag = "0", mode = "full",
                      order = "create", limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
    condList = []
    recID = toIntSafe(recID, 0)
    jobID = toIntSafe(jobID, 0)
    topicID = toIntSafe(topicID, 0)
    if recID > 0:
        condList.append(["recID", "=", recID])
    if jobID > 0:
        condList.append(["jobID", "=", jobID])
    if topicID > 0:
        condList.append(["topicID", "=", topicID])
    condList.append(["kind", "=", kind])
    condList.append(["platform", "=", platform])
    condList.append(["artifactStatus", "=", artifactStatus])
    condList.append(["expireYMDHMS", "<=", expireBeforeYMDHMS])
    return queryTableGeneral(tableName, condList = condList, columns = getShortColumns(mode, tableName),
                             delFlag = delFlag, order = order, limitNum = limitNum)


#ch_account 查询记录
def query_ch_account(tableName, recID = "0", accountCode = "", platform = "", healthStatus = "",
                     ownerID = "", delFlag = "0", mode = "full", order = "create",
                     limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
    condList = []
    recID = toIntSafe(recID, 0)
    if recID > 0:
        condList.append(["recID", "=", recID])
    condList.append(["accountCode", "=", accountCode])
    condList.append(["platform", "=", platform])
    condList.append(["healthStatus", "=", healthStatus])
    condList.append(["ownerID", "=", ownerID])
    return queryTableGeneral(tableName, condList = condList, columns = getShortColumns(mode, tableName),
                             delFlag = delFlag, order = order, limitNum = limitNum)


#ch_publish_record 查询记录
def query_ch_publish_record(tableName, recID = "0", idempotencyKey = "", artifactID = "", topicID = "",
                            accountID = "", platform = "", success = "", beginYMDHMS = "", endYMDHMS = "",
                            delFlag = "0", mode = "full", order = "create",
                            limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
    condList = []
    recID = toIntSafe(recID, 0)
    artifactID = toIntSafe(artifactID, 0)
    topicID = toIntSafe(topicID, 0)
    #★ 2026-09-22: 增加 accountID 过滤(前端 P-11 删除账号前展示「关联发布记录数」需要; 见附录 B R-31)
    accountID = toIntSafe(accountID, 0)
    if recID > 0:
        condList.append(["recID", "=", recID])
    if artifactID > 0:
        condList.append(["artifactID", "=", artifactID])
    if topicID > 0:
        condList.append(["topicID", "=", topicID])
    if accountID > 0:
        condList.append(["accountID", "=", accountID])
    condList.append(["idempotencyKey", "=", idempotencyKey])
    condList.append(["platform", "=", platform])
    condList.append(["success", "=", success])
    condList.append(["pushedYMDHMS", ">=", beginYMDHMS])
    condList.append(["pushedYMDHMS", "<=", endYMDHMS])
    return queryTableGeneral(tableName, condList = condList, columns = getShortColumns(mode, tableName),
                             delFlag = delFlag, order = order, limitNum = limitNum)


#ch_mcp_token 查询记录
def query_ch_mcp_token(tableName, recID = "0", tokenHash = "", tokenName = "", tokenScope = "",
                       projectCode = "", delFlag = "0", mode = "full", order = "create",
                       limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
    condList = []
    recID = toIntSafe(recID, 0)
    if recID > 0:
        condList.append(["recID", "=", recID])
    condList.append(["tokenHash", "=", tokenHash])
    condList.append(["tokenName", "=", tokenName])
    condList.append(["tokenScope", "=", tokenScope])
    condList.append(["projectCode", "=", projectCode])
    return queryTableGeneral(tableName, condList = condList, columns = getShortColumns(mode, tableName),
                             delFlag = delFlag, order = order, limitNum = limitNum)


#ch_audit_log 查询记录(大表: 默认 LIMIT 5000, 必须带时间范围或过滤条件使用)
def query_ch_audit_log(tableName, recID = "0", actor = "", action = "", result = "", source = "",
                       targetType = "", targetID = "", ipAddr = "", beginYMDHMS = "", endYMDHMS = "",
                       delFlag = "", mode = "full", order = "create",
                       limitNum = _DEF_CH_AUDIT_LOG_QUERY_LIMIT_NUM):
    condList = []
    recID = toIntSafe(recID, 0)
    if recID > 0:
        condList.append(["recID", "=", recID])
    condList.append(["actor", "=", actor])
    condList.append(["action", "=", action])
    condList.append(["result", "=", result])
    condList.append(["source", "=", source])
    condList.append(["targetType", "=", targetType])
    condList.append(["targetID", "=", targetID])
    #★ 2026-09-22: 增加 ipAddr 过滤(前端 P-12 审计日志按来源 IP 筛选需要; 等值匹配, 见附录 B R-32)
    condList.append(["ipAddr", "=", ipAddr])
    condList.append(["regYMDHMS", ">=", beginYMDHMS])
    condList.append(["regYMDHMS", "<=", endYMDHMS])
    #审计日志为追加写语义, 默认不做 delFlag 过滤(delFlag 传 "" 即不过滤)
    return queryTableGeneral(tableName, condList = condList, columns = getShortColumns(mode, tableName),
                             delFlag = delFlag, order = order, limitNum = limitNum)


#ch_topic_version 查询记录
def query_ch_topic_version(tableName, recID = "0", topicID = "", versionNo = "", ownerID = "",
                           delFlag = "0", mode = "full", order = "update",
                           limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
    condList = []
    recID = toIntSafe(recID, 0)
    topicID = toIntSafe(topicID, 0)
    versionNo = toIntSafe(versionNo, 0)
    if recID > 0:
        condList.append(["recID", "=", recID])
    if topicID > 0:
        condList.append(["topicID", "=", topicID])
    if versionNo > 0:
        condList.append(["versionNo", "=", versionNo])
    condList.append(["ownerID", "=", ownerID])
    return queryTableGeneral(tableName, condList = condList, columns = getShortColumns(mode, tableName),
                             delFlag = delFlag, order = order, limitNum = limitNum)

#common end


#===== 外部既有表(port from museum) begin =====
#说明(见 plan.md §11「移植表登记」):
#  1) USER_BASIC 与 weixin_pay 是 museum 既有的「外部表」, **不套用 ch_* 的 recID/尾部七字段规范**;
#  2) USER_BASIC 的建表与读写全部为手写段(下方位 user family 8 个函数), 列集合以
#     database/userBasic.txt 为唯一数据源 —— 两侧逐列一致, 由 test/test_ch_phase0_static.py 的 S19 锁定;
#  3) weixin_pay 的数据层(tablename_convertor_/decode_/create_/drop_/delete_/insert_/update_)为生成段,
#     已由 tools/mergeMysqlCommon.py 合并到本文件生成区; 其手写 query_weixin_pay 在本段下方;
#  4) 移植来源: museum common/mysqlCommon.py 的 user family(L282-1005) 与 query_weixin_pay(L1629-1705),
#     逻辑逐行照搬, 仅补充注释;
#  5) 账号域(accountApi)本轮仍走既有实现, 下轮再切换到本表(见 plan.md §9 SP1.5 交接事项)。



#user family begin(USER_BASIC: 用户账号主表, 主键 loginID)

#genOrList: 生成 "( key = %s OR key = %s ... )" 条件串(移植自 museum common/mysqlCommon.py L265-277,
#USER_BASIC 的 queryUserBasic 依赖它; 与 contentHub 内 queryTableGeneral 的 likeOrList 实现互不影响)
def genOrList(IDList, keyName = ""):
    aList = []
    count = 0
    aList.append("( ")
    for ID in IDList:
        if count == 0:
            aList.append(f" {keyName} = %s ")
        else:
            aList.append(f" OR {keyName} = %s ")
        count += 1
    aList.append(") ")
    result = "".join(aList)
    return result


def createUserBasic():
    tableName = "USER_BASIC"
    aList  = ["CREATE TABLE IF NOT EXISTS %s("
    "loginID VARCHAR(32) PRIMARY KEY COMMENT '用户登录号',",
    "passwd VARCHAR(80) COMMENT '用户密码',",
    "openID VARCHAR(40) COMMENT '微信openID',",
    "roleName VARCHAR(16) COMMENT '角色名称',",
    "nickName VARCHAR(40) COMMENT '昵称',",
    "realName VARCHAR(40) COMMENT '用户真实姓名' ,",
    "gender CHAR(1) COMMENT '性别',",
    "avatarID VARCHAR(200) COMMENT '头像ID',",
    "mobilePhoneNo VARCHAR(32) COMMENT '手机号',",
    "masterID VARCHAR(32) COMMENT '用户主号',",
    "province VARCHAR(32) COMMENT '省',",
    "city VARCHAR(32) COMMENT '市',",
    "area VARCHAR(32) COMMENT '地区',",
    "address VARCHAR(200) COMMENT '地址',",
    "email VARCHAR(100) COMMENT '用户邮箱',",
    "PID VARCHAR(20) COMMENT '用户身份证号',",
    "photoIDFront VARCHAR(128) COMMENT '用户身份证头像侧',",
    "photoIDBack VARCHAR(128) COMMENT '用户身份证背面',",
    "photoID VARCHAR(128) COMMENT '用户照片',",
    "delFlag CHAR(1) COMMENT '删除标记',",
    "activeFlag CHAR(1) COMMENT '活动标记',",
    "regPosition VARCHAR(80) COMMENT '注册位置',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "updateYMDHMS VARCHAR(16) COMMENT '数据更新日期',",
    "lastOpenID VARCHAR(40) COMMENT '用户最后一次登录openID',",
    "lastLoginYMDHMS VARCHAR(16) COMMENT '用户最后一次登录年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "passwdYMDHMS VARCHAR(16) COMMENT '密码修改年月日',",
    "extSessionID VARCHAR(48) COMMENT '扩展用户sessionID',",
    "extStartYMDHMS VARCHAR(16) COMMENT '扩展开始年月日',",
    "extLeaveYMDHMS VARCHAR(16) COMMENT '扩展停止年月日',",
    "extJobPosition VARCHAR(100) COMMENT '扩展职位',",
    "extDepartment VARCHAR(100) COMMENT '扩展部门',",
    "extOrgName VARCHAR(300) COMMENT '扩展组织名称',",
    "extOrgID INT COMMENT '扩展组织ID',",
    "extInService VARCHAR(1) COMMENT '扩展是否在职',",
    "extJobLabel VARCHAR(16) COMMENT '扩展职位身份标签_注册用户_区域用户_后台用户',",
    "extJobDetail VARCHAR(64) COMMENT '扩展职位细节_例如是工信厅卫生局等',",
    "extBrief VARCHAR(1000) COMMENT '扩展人员简介_专家简介_区域管理员类别',",
    "extManualTagList VARCHAR(500) COMMENT '扩展标签列表',",
    "extManagementAreaList VARCHAR(500) COMMENT '扩展管理区域',",
    "extMemo VARCHAR(100) COMMENT '扩展备注'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;" , 
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        sqlStr = "CREATE INDEX {1} ON {0}({1})".format(tableName, "roleName")
        rtn = mysqlDB.executeWrite(sqlStr)
        # sqlStr = "CREATE INDEX {1} ON {0}({1})".format(tableName, "extJobLabel")
        # rtn = mysqlDB.executeWrite(sqlStr)

    return result


def dropUserBasic():
    tableName = "USER_BASIC"
    result = dropTableGeneral(tableName)
    return result


#以后这个是标准写法,利用fetchMany来处理数据
#SELECT * FROM USER_BASIC WHERE loginID = "13910710766";
def queryUserBasic(loginID = "" , name = "", mobile = "", manualTag = "",jobLabel="",
                   searchOption = {},  roleName = "", roleNameList = [],  keyword="",
                   mode = "normal", beginYMD = "",endYMD = "", 
                   order="create", limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
    result = []
    tableName = "USER_BASIC"

    if mode =="short":
        columns = "loginID,nickName,realName,roleName, gender,avatarID"
    elif mode =="normal":
        columns = "loginID,nickName,realName,roleName,gender,avatarID,openID,masterID,mobilePhoneNo,province,city,area, address, email, regYMDHMS, updateYMDHMS"
    else:
        columns = "*"
    valuesList = [] 
    sqlStr =   "SELECT %s FROM %s " % (columns, tableName )

    try:
        if loginID:
            sqlStr += " WHERE loginID = %s"
            valuesList = [loginID]
        else:
            valuesList = []
            #以下 searchOption,roleName,roleNameList是并列关系,只能选一个
            if searchOption:
                if valuesList:
                    whereStr = " AND "
                else:
                    whereStr = " WHERE "
                logic = searchOption.get("logic", "AND")
                optionList = searchOption.get("optionList", [])
                count = 0
                for optionSet in optionList:
                    if count > 0:
                        whereStr += " " + logic + " "
                    if "realName" in optionSet:
                        whereStr += " realName = %s" 
                        valuesList.append(optionSet["realName"])
                    if "nickName" in optionSet:
                        whereStr += " nickName = %s" 
                        valuesList.append(optionSet["nickName"])
                    if "loginID" in optionSet:
                        whereStr += " loginID = %s" 
                        valuesList.append(optionSet["loginID"])
                    if "roleName" in optionSet:
                        whereStr += " roleName = %s" 
                        valuesList.append(optionSet["roleName"])
                    if "province" in optionSet:
                        whereStr += " province = %s" 
                        valuesList.append(optionSet["province"])
                    count += 1
                sqlStr += whereStr 
                
            elif jobLabel:
                if valuesList:
                    whereStr = " AND extJobLabel = %s "
                else:
                    whereStr = " WHERE extJobLabel = %s "
                valuesList.append(jobLabel)
                sqlStr += whereStr 

            elif roleName:
                if valuesList:
                    whereStr = " AND roleName = %s "
                else:
                    whereStr = " WHERE roleName = %s "
                valuesList.append(roleName)
                sqlStr += whereStr 

            elif roleNameList:
                if valuesList:
                    whereStr = " AND " + genOrList(roleNameList, "roleName")
                else:
                    whereStr = " WHERE " + genOrList(roleNameList, "roleName")
                valuesList += roleNameList
                sqlStr += whereStr 
            
            if keyword:
                if valuesList:
                    sqlStr =  sqlStr + " AND (locate(%s,realName) OR locate(%s,nickName) OR locate(%s,extJobPosition) OR locate(%s,extJobDetail) OR locate(%s,extOrgName) OR locate(%s,loginID) )" 
                else:
                    sqlStr =  sqlStr + " WHERE (locate(%s,realName) OR locate(%s,nickName) OR locate(%s,extJobPosition) OR locate(%s,extJobDetail) OR locate(%s,extOrgName) OR locate(%s,loginID) )" 
                valuesList.append(keyword)
                valuesList.append(keyword)
                valuesList.append(keyword)
                valuesList.append(keyword)
                valuesList.append(keyword)
                valuesList.append(keyword)

            # beginYMD 和 endYMD可以和上面混用
            if beginYMD  and endYMD :
                beginYMDHMS = beginYMD + "000000"
                endYMDHMS = endYMD + "240000"
                if valuesList:
                    whereStr = " AND regYMDHMS >= %s and regYMDHMS <= %s "
                else:
                    whereStr = " WHERE regYMDHMS >= %s and regYMDHMS <= %s "
                sqlStr = sqlStr + " WHERE regYMDHMS >= %s and regYMDHMS <= %s " 
                valuesList += [beginYMDHMS, endYMDHMS] 
                                
        if order == "create":
            sqlStr += " ORDER BY regYMDHMS DESC"
        
        #其他过滤数据的在这里
        if name or mobile or manualTag:
            #分批次获取数据并挑选数据
            rtn = mysqlDB.executeRead(sqlStr, tuple(valuesList))
            if rtn:
                batchNum = 1000
                total = 0
                while True:
                    dataList = mysqlDB.fetchMany(batchNum)
                    dataList = dataFormatConvert(dataList)
                
                    for data in dataList:
                        matchFlag = False

                        if mobile:
                            keyword = mobile
                            keyList = ["mobilePhoneNo","loginID"]
                            for key in keyList:
                                currVal = data.get(key)
                                if currVal:
                                    if currVal.find(keyword) >= 0:
                                        matchFlag = True
                                        break
                        if name:
                            keyword = name
                            keyList = ["roleName","nickName","realName"]
                            for key in keyList:
                                currVal = data.get(key)
                                if currVal:
                                    if currVal.find(keyword) >= 0:
                                        matchFlag = True
                                        break

                        if matchFlag:
                            result.append(data)

                    #final
                    #如果取不到更多数据就退出
                    currDataLen = len(dataList)
                    if currDataLen < batchNum:
                        break
                    
                    #如果取到的数据满足要求也退出,limitNUm = 0 是提取全部满足条件数据
                    if limitNum > 0:
                        total = len(result)
                        if total >= limitNum:
                            result = result[0:limitNum]
                            break
        else:
            if limitNum > 0:
                sqlStr += " LIMIT {0}".format(limitNum)

            rtn = mysqlDB.executeRead(sqlStr, tuple(valuesList))
            if rtn > 0:
                dataList = mysqlDB.fetchAll()
                dataList = dataFormatConvert(dataList)

                result = dataList

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
#        if _DEBUG:
#            _LOG.error(f"{errMsg}")

    return result

    
#SELECT * FROM USER_BASIC WHERE loginID = "13910710766";
def deleteUserBasic(loginID):
    result = 0
    tableName = "USER_BASIC"
    try:
    
        sqlStr = "DELETE FROM %s WHERE loginID = \"%s\";" % (tableName, loginID)
        rtn = mysqlDB.executeWrite(sqlStr)
        result = rtn

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
#        if _DEBUG:
#            _LOG.error(f"{errMsg}")

    return result
    
    
def insertUserBasic(loginID, dataSet):
    result = 0
    tableName = "USER_BASIC"
    try:
        saveSet = {}
        saveSet["loginID"]  = loginID

        saveSet["passwd"] = dataSet.get("passwd", "") 

        saveSet["openID"] = dataSet.get("openID", "") 

        saveSet["roleName"] = dataSet.get("roleName", "") 

        saveSet["nickName"] = dataSet.get("nickName", "") 

        saveSet["realName"] = dataSet.get("realName", "") 

        saveSet["gender"] = dataSet.get("gender", "") 

        saveSet["avatarID"] = dataSet.get("avatarID", "") 

        saveSet["mobilePhoneNo"] = dataSet.get("mobilePhoneNo", "") 

        saveSet["masterID"] = dataSet.get("masterID", "") 

        saveSet["province"] = dataSet.get("province", "") 

        saveSet["city"] = dataSet.get("city", "") 

        saveSet["area"] = dataSet.get("area", "") 

        saveSet["address"] = dataSet.get("address", "") 

        saveSet["email"] = dataSet.get("email", "") 

        saveSet["PID"] = dataSet.get("PID", "") 

        saveSet["photoIDFront"] = dataSet.get("photoIDFront", "") 

        saveSet["photoIDBack"] = dataSet.get("photoIDBack", "") 

        saveSet["photoID"] = dataSet.get("photoID", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        saveSet["activeFlag"] = dataSet.get("activeFlag", comGD._CONST_YES) 

        regPosition = dataSet.get("regPosition", {})
        if (regPosition != {}):
            #双引号的特殊处理
            saveSet["regPosition"]  = misc.jsonDumps(regPosition).replace("\"", "'")
        else:
            saveSet["regPosition"] = misc.jsonDumps({})

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["updateYMDHMS"] = dataSet.get("updateYMDHMS", "") 

        saveSet["lastOpenID"] = dataSet.get("lastOpenID", "") 

        saveSet["lastLoginYMDHMS"] = dataSet.get("lastLoginYMDHMS", "") 

        saveSet["passwdYMDHMS"] = dataSet.get("passwdYMDHMS", "") 

        # extend items begin, per project
        saveSet["extSessionID"] = dataSet.get("extSessionID", "") 

        saveSet["extStartYMDHMS"] = dataSet.get("extStartYMDHMS", "") 

        saveSet["extStartYMDHMS"] = dataSet.get("extStartYMDHMS", "") 

        saveSet["extLeaveYMDHMS"] = dataSet.get("extLeaveYMDHMS", "") 

        saveSet["extJobPosition"] = dataSet.get("extJobPosition", "") 

        saveSet["extDepartment"] = dataSet.get("extDepartment", "") 

        saveSet["extOrgName"] = dataSet.get("extOrgName", "") 

        try:
            extOrgID = int(dataSet.get("extOrgID")) 
        except:
            extOrgID = 0 
        saveSet["extOrgID"] = extOrgID

        saveSet["extInService"] = dataSet.get("extInService", "") 

        saveSet["extJobLabel"] = dataSet.get("extJobLabel", "") 

        saveSet["extJobDetail"] = dataSet.get("extJobDetail", "") 

        saveSet["extBrief"] = dataSet.get("extBrief", "") 

        saveSet["extManualTagList"] = dataSet.get("extManualTagList", "") 

        saveSet["extManagementAreaList"] = dataSet.get("extManagementAreaList", "") 

        saveSet["extMemo"] = dataSet.get("extMemo", "") 
        # extend items end, per project

        result = insertTableGeneral(tableName, saveSet, selfDefinedPrimaryKey = comGD._CONST_YES)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
#        if _DEBUG:
#            _LOG.error(f"{errMsg}")

    return result
    
    
def updateUserBasic(loginID, dataSet):
    result = 0
    tableName = "USER_BASIC"
    try:
        saveSet = {}
        
        passwd = dataSet.get("passwd")
        if passwd != "" and passwd:
            saveSet["passwd"] = passwd
            
        openID = dataSet.get("openID", "")
        if openID != "":
            saveSet["openID"] = openID

        roleName = dataSet.get("roleName", "")
        if roleName != "":
            saveSet["roleName"] = roleName

        nickName = dataSet.get("nickName", "")
        if nickName != "":
            saveSet["nickName"] = nickName

        realName = dataSet.get("realName", "")
        if realName != "":
            saveSet["realName"] = realName

        gender = dataSet.get("gender", "")
        if gender != "":
            saveSet["gender"] = gender

        avatarID = dataSet.get("avatarID", "")
        if avatarID != "":
            saveSet["avatarID"] = avatarID

        mobilePhoneNo = dataSet.get("mobilePhoneNo", "")
        if mobilePhoneNo != "":
            saveSet["mobilePhoneNo"] = mobilePhoneNo

        province = dataSet.get("province", "")
        if province != "":
            saveSet["province"] = province
            
        masterID = dataSet.get("masterID", "")
        if masterID != "":
            saveSet["masterID"] = masterID
            
        city = dataSet.get("city", "")
        if city != "":
            saveSet["city"] = city
            
        area = dataSet.get("area", "")
        if area != "":
            saveSet["area"] = area
            
        address = dataSet.get("address", "")
        if address != "":
            saveSet["address"] = address
            
        email = dataSet.get("email", "")
        if email != "":
            saveSet["email"] = email
            
        PID = dataSet.get("PID", "")
        if PID != "":
            saveSet["PID"] = PID
            
        photoIDFront = dataSet.get("photoIDFront", "")
        if photoIDFront != "":
            saveSet["photoIDFront"] = photoIDFront
            
        photoIDBack = dataSet.get("photoIDBack", "")
        if photoIDBack != "":
            saveSet["photoIDBack"] = photoIDBack
            
        photoIDBack = dataSet.get("photoIDBack", "")
        if photoIDBack != "":
            saveSet["photoIDBack"] = photoIDBack
            
        photoID = dataSet.get("photoID", "")
        if photoID != "":
            saveSet["photoID"] = photoID

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            if delFlag != "1":
                delFlag = "0"
            saveSet["delFlag"] = delFlag

        activeFlag = dataSet.get("activeFlag")
        if activeFlag:
            saveSet["activeFlag"] = activeFlag

        regPosition = dataSet.get("regPosition", {})
        if (regPosition != {}):
            #双引号的特殊处理
            saveSet["regPosition"] = misc.jsonDumps(regPosition).replace("\"", "'")

        updateYMDHMS = dataSet.get("updateYMDHMS", "")
        if updateYMDHMS != "":
            saveSet["updateYMDHMS"] = updateYMDHMS
        lastOpenID = dataSet.get("lastOpenID", "")

        if lastOpenID != "":
            saveSet["lastOpenID"] = lastOpenID

        lastLoginYMDHMS = dataSet.get("lastLoginYMDHMS", "")
        if lastLoginYMDHMS != "":
            saveSet["lastLoginYMDHMS"] = lastLoginYMDHMS

        modifyID = dataSet.get("modifyID")
        if modifyID != "":
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS", "")
        if modifyYMDHMS != "":
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        passwdYMDHMS = dataSet.get("passwdYMDHMS", "")
        if passwdYMDHMS != "":
            saveSet["passwdYMDHMS"] = passwdYMDHMS
    
        # extend items begin, per project

        extSessionID = dataSet.get("extSessionID", "")
        if extSessionID != "":
            saveSet["extSessionID"] = extSessionID

        extStartYMDHMS = dataSet.get("extStartYMDHMS") 
        if extStartYMDHMS:
            saveSet["extStartYMDHMS"] = extStartYMDHMS

        extLeaveYMDHMS = dataSet.get("extLeaveYMDHMS") 
        if extLeaveYMDHMS:
            saveSet["extLeaveYMDHMS"] = extLeaveYMDHMS

        extJobPosition = dataSet.get("extJobPosition") 
        if extJobPosition:
            saveSet["extJobPosition"] = extJobPosition

        extDepartment = dataSet.get("extDepartment") 
        if extDepartment:
            saveSet["extDepartment"] = extDepartment

        extOrgName = dataSet.get("extOrgName") 
        if extOrgName:
            saveSet["extOrgName"] = extOrgName

        extOrgID = dataSet.get("extOrgID") 
        if extOrgID:
            try:
                extOrgID = int(dataSet.get("extOrgID")) 
                saveSet["extOrgID"] = extOrgID
            except:
                pass

        extInService = dataSet.get("extInService") 
        if extInService:
            saveSet["extInService"] = extInService

        extJobLabel = dataSet.get("extJobLabel") 
        if extJobLabel:
            saveSet["extJobLabel"] = extJobLabel

        extJobDetail = dataSet.get("extJobDetail") 
        if extJobDetail:
            saveSet["extJobDetail"] = extJobDetail

        extBrief = dataSet.get("extBrief") 
        if extBrief:
            saveSet["extBrief"] = extBrief

        extManualTagList = dataSet.get("extManualTagList") 
        if extManualTagList:
            saveSet["extManualTagList"] = extManualTagList

        extManagementAreaList = dataSet.get("extManagementAreaList") 
        if extManagementAreaList:
            saveSet["extManagementAreaList"] = extManagementAreaList

        extMemo = dataSet.get("extMemo") 
        if extMemo:
            saveSet["extMemo"] = extMemo

        # extend items end, per project

        keySqlstr = "loginID = %s" 
        keyValues = [loginID]
        
        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)
        
    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
#        if _DEBUG:
#            _LOG.error(f"{errMsg}")

    return result


#获取本地用户信息mysql
def getUserInfoMysql(loginID):
    result = {}
    try:
        mode = "full"
        currDataList = queryUserBasic(loginID,mode = mode)

        if currDataList:
            currDataSet = currDataList[0]

            aSet = {}

            aSet["loginID"] = currDataSet.get("loginID","")
            # aSet["openID"] = currDataSet.get("openID","")
            aSet["roleName"] = currDataSet.get("roleName","")
            aSet["nickName"] = currDataSet.get("nickName","")
            aSet["realName"] = currDataSet.get("realName","")
            aSet["gender"] = currDataSet.get("gender","")

            aSet["avatarID"] = currDataSet.get("avatarID","")

            aSet["mobilePhoneNo"] = currDataSet.get("mobilePhoneNo","")
            aSet["masterID"] = currDataSet.get("masterID","")
            aSet["province"] = currDataSet.get("province","")
            aSet["city"] = currDataSet.get("city","")
            aSet["area"] = currDataSet.get("area","")
            aSet["address"] = currDataSet.get("address","")
            aSet["email"] = currDataSet.get("email","")
            aSet["PID"] = currDataSet.get("PID","")
            aSet["activeFlag"] = currDataSet.get("activeFlag","")

            # photoIDFront = currDataSet.get("photoIDFront","")
            # if photoIDFront:
            #     photoIDFront = getTempLocation(photoIDFront, privateFlag = True)
            # aSet["photoIDFront"] = photoIDFront

            # photoIDBack = currDataSet.get("photoIDBack","")
            # if photoIDBack:
            #     photoIDBack = getTempLocation(photoIDBack, privateFlag = True)
            # aSet["photoIDBack"] = photoIDBack

            # photoID = currDataSet.get("photoID","")
            # if photoID:
            #     photoID = getTempLocation(photoID, privateFlag = True)
            # aSet["photoID"] = photoID

            # aSet["delFlag"] = currDataSet.get("delFlag","")
            aSet["regPosition"] = currDataSet.get("regPosition","")
            aSet["regID"] = currDataSet.get("regID","")
            aSet["regYMDHMS"] = currDataSet.get("regYMDHMS","")
            aSet["updateYMDHMS"] = currDataSet.get("updateYMDHMS","")
            # aSet["lastOpenID"] = currDataSet.get("lastOpenID","")
            aSet["lastLoginYMDHMS"] = currDataSet.get("lastLoginYMDHMS","")
            aSet["modifyID"] = currDataSet.get("modifyID","")
            aSet["modifyYMDHMS"] = currDataSet.get("modifyYMDHMS","")
            # aSet["passwdYMDHMS"] = currDataSet.get("passwdYMDHMS","")

            # extend items begin, per project
            aSet["extSessionID"] = currDataSet.get("extSessionID","")
            aSet["extStartYMDHMS"] = currDataSet.get("extStartYMDHMS","")
            aSet["extLeaveYMDHMS"] = currDataSet.get("extLeaveYMDHMS","")
            aSet["extJobPosition"] = currDataSet.get("extJobPosition","")
            aSet["extDepartment"] = currDataSet.get("extDepartment","")
            aSet["extOrgName"] = currDataSet.get("extOrgName","")
            aSet["extOrgID"] = currDataSet.get("extOrgID","")

            aSet["extInService"] = currDataSet.get("extInService","")
            # aSet["extInService"] = chkIsInService(aSet["extInService"],aSet["activeFlag"])

            aSet["extJobLabel"] = currDataSet.get("extJobLabel","")
            aSet["extJobDetail"] = currDataSet.get("extJobDetail","")
            aSet["extBrief"] = currDataSet.get("extBrief","")

            #list/dict处理
            extManualTagList = currDataSet.get("extManualTagList")
            try:
                extManualTagList = misc.jsonLoads(extManualTagList)
            except:
                extManualTagList = []
            aSet["extManualTagList"] = extManualTagList

            #list/dict处理
            extManagementAreaList = currDataSet.get("extManagementAreaList")
            try:
                extManagementAreaList = misc.jsonLoads(extManagementAreaList)
            except:
                extManagementAreaList = []
            aSet["extManagementAreaList"] = extManagementAreaList
            aSet["extMemo"] = currDataSet.get("extMemo","")
            # extend items end, per project

            result = aSet
    except:
        pass
    return result


#champion only 
def statUserBasic(statBy = "roleName", beginYMD = "",endYMD = ""):
    result = []
    tableName = "USER_BASIC"

    valuesList = []

    try:
        if statBy == "roleName":
            sqlStr = f"SELECT count(loginID) as total, roleName FROM {tableName} "

            if beginYMD:
                beginYMDHMS = beginYMD + "000000"
                if valuesList:
                    sqlStr += " AND regYMDHMS >= % " 
                else:
                    sqlStr += " WHERE regYMDHMS >= % " 
                valuesList.append(beginYMDHMS)

            if endYMD:
                endYMDHMS = endYMD + "240000"
                if valuesList:
                    sqlStr += " AND regYMDHMS <= % " 
                else:
                    sqlStr += " WHERE regYMDHMS <= % " 
                valuesList.append(endYMDHMS)
            
            sqlStr += " GROUP BY roleName"
        else:
            sqlStr = f"SELECT count(loginID) as total FROM {tableName}"

            if beginYMD:
                beginYMDHMS = beginYMD + "000000"
                if valuesList:
                    sqlStr += " AND regYMDHMS >= % " 
                else:
                    sqlStr += " WHERE regYMDHMS >= % " 
                valuesList.append(beginYMDHMS)

            if endYMD:
                endYMDHMS = endYMD + "240000"
                if valuesList:
                    sqlStr += " AND regYMDHMS <= % " 
                else:
                    sqlStr += " WHERE regYMDHMS <= % " 
                valuesList.append(endYMDHMS)
            
        rtn = mysqlDB.executeRead(sqlStr, tuple(valuesList))
        if rtn > 0:
            dataList = mysqlDB.fetchAll()
            dataList = dataFormatConvert(dataList)
            result = dataList

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
#        if _DEBUG:
#            _LOG.error(f"{errMsg}")

    return result


#user family end


#query_weixin_pay begin(weixin_pay: 微信支付/退款流水, 主键 sortID, 业务唯一键 tradeNo)
def query_weixin_pay(tableName,tradeNo = "", parentTradeNo="",productID = "", loginID = "", startYMDHMS = "", endYMDHMS = "", delFlag = "0", mode = "full",order = "create",limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
    result = []
    columns = "*"
    valuesList = []
    sqlStr = f"SELECT {columns} FROM {tableName}"

    try:
        whereFlag = False
        if delFlag in ["0","1"]:
            if tradeNo != "":
                sqlStr =  sqlStr + " WHERE  delFlag = %s and tradeNo = %s" 
                valuesList = [delFlag,tradeNo]
                whereFlag = True                
            else:
                sqlStr =  sqlStr + " WHERE  delFlag = %s " 
                valuesList = [delFlag]
                whereFlag = True   
        else:
            if tradeNo != "":
                sqlStr =  sqlStr + " WHERE tradeNo = %s" 
                valuesList = [tradeNo]
                whereFlag = True

        if productID != "":
            if whereFlag:
                sqlStr =  sqlStr + " AND productID = %s" 
            else:
                sqlStr =  sqlStr + " WHERE productID = %s" 
            valuesList.append(productID)
            whereFlag = True   

        if loginID != "":
            if whereFlag:
                sqlStr =  sqlStr + " AND loginID = %s" 
            else:
                sqlStr =  sqlStr + " WHERE loginID = %s" 
            valuesList.append(loginID)
            whereFlag = True   

        if parentTradeNo != "":
            if whereFlag:
                sqlStr =  sqlStr + " AND parentTradeNo = %s" 
            else:
                sqlStr =  sqlStr + " WHERE parentTradeNo = %s" 
            valuesList.append(parentTradeNo)
            whereFlag = True  
            
        if startYMDHMS and endYMDHMS:
            if whereFlag:
                sqlStr =  sqlStr + " AND createYMDHMS >= %s"
                sqlStr =  sqlStr + " AND createYMDHMS <= %s"
            else:
                sqlStr =  sqlStr + " WHERE createYMDHMS >= %s"
                sqlStr =  sqlStr + " AND createYMDHMS <= %s"
                whereFlag = True
            valuesList.append(startYMDHMS)
            valuesList.append(endYMDHMS)
            
        if order == "create":
            sqlStr += " ORDER BY createYMDHMS DESC"

        if limitNum > 0:
            sqlStr += " LIMIT {0}".format(limitNum)

        rtn = mysqlDB.executeRead(sqlStr, tuple(valuesList))
        dataList = mysqlDB.fetchAll()
        dataList = dataFormatConvert(dataList)
        result = list(dataList)  

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result

#query_weixin_pay end
#===== 外部既有表(port from museum) end =====


#===== auto-generated sections begin (由 tools/mergeMysqlCommon.py 生成, 请勿手改) =====



#ch_topic begin 

def tablename_convertor_ch_topic():
    tableName = "ch_topic"
    tableName = tableName.lower()
    return tableName


def decode_tablename_ch_topic(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建ch_topic表
def create_ch_topic(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "topicCode VARCHAR(64) NOT NULL UNIQUE COMMENT '主题编码 幂等键',",
    "title VARCHAR(128) NOT NULL COMMENT '标题 限50字',",
    "summary VARCHAR(400) NULL COMMENT '简介 限200字',",
    "`description` MEDIUMTEXT NULL COMMENT '详细描述正文 不超过5000字,可留空',",
    "descriptionFileID VARCHAR(200) NULL COMMENT '详述大稿fileID 超长时正文转存文件',",
    "coverFileID VARCHAR(200) NULL COMMENT '标题图fileID',",
    "coverThumbID VARCHAR(200) NULL COMMENT '标题图缩略图fileID',",
    "author VARCHAR(64) NULL COMMENT '作者',",
    "location VARCHAR(128) NULL COMMENT '地点',",
    "`source` VARCHAR(255) NULL COMMENT '来源',",
    "period VARCHAR(64) NULL COMMENT '时期',",
    "tagList VARCHAR(512) NULL COMMENT '标签 逗号分隔',",
    "categoryCode VARCHAR(32) NULL COMMENT '分类编码',",
    "layoutCode VARCHAR(64) NULL COMMENT '已选版式编码 关联ch_layout.layoutCode',",
    "complianceStatus VARCHAR(24) NULL COMMENT '合规校验结论 UNCHECKED或PASSED或BLOCKED',",
    "complianceCheckedAt VARCHAR(16) NULL COMMENT '最近合规校验时间 YYYYMMDDHHMMSS',",
    "`status` VARCHAR(24) NOT NULL DEFAULT 'DRAFT' COMMENT 'DRAFT或RENDERING或RENDERED或PUBLISHED或ARCHIVED',",
    "publishStatus VARCHAR(24) NOT NULL DEFAULT 'UNPUBLISHED' COMMENT 'UNPUBLISHED或DRAFTED或PUBLISHED或FAILED',",
    "assetCount SMALLINT NOT NULL DEFAULT 0 COMMENT '附图数量',",
    "wordCount INT NOT NULL DEFAULT 0 COMMENT '详述字数',",
    "aiFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '是否AI参与创作',",
    "ownerID VARCHAR(64) NULL COMMENT '归属用户loginID',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "topicCode")
        rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除ch_topic表
def drop_ch_topic(tableName):
    result = dropTableGeneral(tableName)
    return result


#ch_topic 删除记录
def delete_ch_topic(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_topic 增加记录
def insert_ch_topic(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["topicCode"] = dataSet.get("topicCode", "") 

        saveSet["title"] = dataSet.get("title", "") 

        saveSet["summary"] = dataSet.get("summary", "") 

        saveSet["description"] = dataSet.get("description", "") 

        saveSet["descriptionFileID"] = dataSet.get("descriptionFileID", "") 

        saveSet["coverFileID"] = dataSet.get("coverFileID", "") 

        saveSet["coverThumbID"] = dataSet.get("coverThumbID", "") 

        saveSet["author"] = dataSet.get("author", "") 

        saveSet["location"] = dataSet.get("location", "") 

        saveSet["source"] = dataSet.get("source", "") 

        saveSet["period"] = dataSet.get("period", "") 

        saveSet["tagList"] = dataSet.get("tagList", "") 

        saveSet["categoryCode"] = dataSet.get("categoryCode", "") 

        saveSet["layoutCode"] = dataSet.get("layoutCode", "") 

        saveSet["complianceStatus"] = dataSet.get("complianceStatus", "") 

        saveSet["complianceCheckedAt"] = dataSet.get("complianceCheckedAt", "") 

        saveSet["status"] = dataSet.get("status", "") 

        saveSet["publishStatus"] = dataSet.get("publishStatus", "") 

        try:
            assetCount = int(dataSet.get("assetCount")) 
        except:
            assetCount = 0 
        saveSet["assetCount"] = assetCount

        try:
            wordCount = int(dataSet.get("wordCount")) 
        except:
            wordCount = 0 
        saveSet["wordCount"] = wordCount

        saveSet["aiFlag"] = dataSet.get("aiFlag", "") 

        saveSet["ownerID"] = dataSet.get("ownerID", "") 

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_topic 修改记录
def update_ch_topic(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        topicCode = dataSet.get("topicCode") 
        if topicCode:
            saveSet["topicCode"] = topicCode

        title = dataSet.get("title") 
        if title:
            saveSet["title"] = title

        summary = dataSet.get("summary") 
        if summary:
            saveSet["summary"] = summary

        description = dataSet.get("description") 
        if description:
            saveSet["description"] = description

        descriptionFileID = dataSet.get("descriptionFileID") 
        if descriptionFileID:
            saveSet["descriptionFileID"] = descriptionFileID

        coverFileID = dataSet.get("coverFileID") 
        if coverFileID:
            saveSet["coverFileID"] = coverFileID

        coverThumbID = dataSet.get("coverThumbID") 
        if coverThumbID:
            saveSet["coverThumbID"] = coverThumbID

        author = dataSet.get("author") 
        if author:
            saveSet["author"] = author

        location = dataSet.get("location") 
        if location:
            saveSet["location"] = location

        source = dataSet.get("source") 
        if source:
            saveSet["source"] = source

        period = dataSet.get("period") 
        if period:
            saveSet["period"] = period

        tagList = dataSet.get("tagList") 
        if tagList:
            saveSet["tagList"] = tagList

        categoryCode = dataSet.get("categoryCode") 
        if categoryCode:
            saveSet["categoryCode"] = categoryCode

        layoutCode = dataSet.get("layoutCode") 
        if layoutCode:
            saveSet["layoutCode"] = layoutCode

        complianceStatus = dataSet.get("complianceStatus") 
        if complianceStatus:
            saveSet["complianceStatus"] = complianceStatus

        complianceCheckedAt = dataSet.get("complianceCheckedAt") 
        if complianceCheckedAt:
            saveSet["complianceCheckedAt"] = complianceCheckedAt

        status = dataSet.get("status") 
        if status:
            saveSet["status"] = status

        publishStatus = dataSet.get("publishStatus") 
        if publishStatus:
            saveSet["publishStatus"] = publishStatus

        try:
            assetCount = int(dataSet.get("assetCount")) 
            saveSet["assetCount"] = assetCount
        except:
            pass

        try:
            wordCount = int(dataSet.get("wordCount")) 
            saveSet["wordCount"] = wordCount
        except:
            pass

        aiFlag = dataSet.get("aiFlag") 
        if aiFlag:
            saveSet["aiFlag"] = aiFlag

        ownerID = dataSet.get("ownerID") 
        if ownerID:
            saveSet["ownerID"] = ownerID

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_topic end




#ch_topic_asset begin 

def tablename_convertor_ch_topic_asset():
    tableName = "ch_topic_asset"
    tableName = tableName.lower()
    return tableName


def decode_tablename_ch_topic_asset(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建ch_topic_asset表
def create_ch_topic_asset(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "assetKey VARCHAR(400) NOT NULL UNIQUE COMMENT '幂等键 topicID加冒号加fileID',",
    "topicID BIGINT NOT NULL COMMENT '关联ch_topic.recID',",
    "fileID VARCHAR(200) NOT NULL COMMENT '素材fileID 关联ch_asset.fileID',",
    "caption VARCHAR(512) NULL COMMENT '图片简要说明',",
    "usageType VARCHAR(24) NOT NULL DEFAULT 'body' COMMENT 'cover或body或inline',",
    "sortOrder SMALLINT NOT NULL DEFAULT 100 COMMENT '展示顺序 越小越靠前',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "topicID")
        rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除ch_topic_asset表
def drop_ch_topic_asset(tableName):
    result = dropTableGeneral(tableName)
    return result


#ch_topic_asset 删除记录
def delete_ch_topic_asset(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_topic_asset 增加记录
def insert_ch_topic_asset(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["assetKey"] = dataSet.get("assetKey", "") 

        try:
            topicID = int(dataSet.get("topicID")) 
        except:
            topicID = 0 
        saveSet["topicID"] = topicID

        saveSet["fileID"] = dataSet.get("fileID", "") 

        saveSet["caption"] = dataSet.get("caption", "") 

        saveSet["usageType"] = dataSet.get("usageType", "") 

        try:
            sortOrder = int(dataSet.get("sortOrder")) 
        except:
            sortOrder = 0 
        saveSet["sortOrder"] = sortOrder

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_topic_asset 修改记录
def update_ch_topic_asset(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        assetKey = dataSet.get("assetKey") 
        if assetKey:
            saveSet["assetKey"] = assetKey

        try:
            topicID = int(dataSet.get("topicID")) 
            saveSet["topicID"] = topicID
        except:
            pass

        fileID = dataSet.get("fileID") 
        if fileID:
            saveSet["fileID"] = fileID

        caption = dataSet.get("caption") 
        if caption:
            saveSet["caption"] = caption

        usageType = dataSet.get("usageType") 
        if usageType:
            saveSet["usageType"] = usageType

        try:
            sortOrder = int(dataSet.get("sortOrder")) 
            saveSet["sortOrder"] = sortOrder
        except:
            pass

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_topic_asset end




#ch_asset begin 

def tablename_convertor_ch_asset():
    tableName = "ch_asset"
    tableName = tableName.lower()
    return tableName


def decode_tablename_ch_asset(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建ch_asset表
def create_ch_asset(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "fileID VARCHAR(200) NOT NULL UNIQUE COMMENT '文件服务器fileID 只存标识',",
    "thumbnailID VARCHAR(200) NULL COMMENT '缩略图fileID',",
    "contentHash CHAR(64) NOT NULL UNIQUE COMMENT 'sha256原始字节 内容级去重',",
    "fileSystem VARCHAR(16) NOT NULL COMMENT '落库时后端快照 ALIOSS或TENCENT或SELFFILE',",
    "storageBucket VARCHAR(64) NULL COMMENT '存储桶名 本地存储为local',",
    "storagePath VARCHAR(512) NULL COMMENT '本地相对路径 SELFFILE用',",
    "objectName VARCHAR(255) NULL COMMENT '对象键 ALIOSS/TENCENT用',",
    "origName VARCHAR(255) NULL COMMENT '原始文件名',",
    "mimeType VARCHAR(64) NULL COMMENT 'MIME类型',",
    "fileExt VARCHAR(16) NULL COMMENT '扩展名',",
    "origSizeBytes BIGINT NOT NULL DEFAULT 0 COMMENT '原始字节数',",
    "width INT NULL COMMENT '原始宽度',",
    "height INT NULL COMMENT '原始高度',",
    "derivedFileID VARCHAR(200) NULL COMMENT '规格处理后fileID',",
    "derivedThumbID VARCHAR(200) NULL COMMENT '处理后缩略图fileID',",
    "derivedWidth INT NULL COMMENT '处理后宽度',",
    "derivedHeight INT NULL COMMENT '处理后高度',",
    "derivedSizeBytes BIGINT NULL COMMENT '处理后字节数',",
    "exifStripped CHAR(1) NOT NULL DEFAULT '0' COMMENT '是否已剥离EXIF',",
    "processStatus VARCHAR(24) NOT NULL DEFAULT 'RAW' COMMENT 'RAW或PROCESSED或FAILED',",
    "errMsg VARCHAR(512) NULL COMMENT '错误信息',",
    "ownerID VARCHAR(64) NULL COMMENT '上传者loginID',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "contentHash")
        rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除ch_asset表
def drop_ch_asset(tableName):
    result = dropTableGeneral(tableName)
    return result


#ch_asset 删除记录
def delete_ch_asset(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_asset 增加记录
def insert_ch_asset(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["fileID"] = dataSet.get("fileID", "") 

        saveSet["thumbnailID"] = dataSet.get("thumbnailID", "") 

        saveSet["contentHash"] = dataSet.get("contentHash", "") 

        saveSet["fileSystem"] = dataSet.get("fileSystem", "") 

        saveSet["storageBucket"] = dataSet.get("storageBucket", "") 

        saveSet["storagePath"] = dataSet.get("storagePath", "") 

        saveSet["objectName"] = dataSet.get("objectName", "") 

        saveSet["origName"] = dataSet.get("origName", "") 

        saveSet["mimeType"] = dataSet.get("mimeType", "") 

        saveSet["fileExt"] = dataSet.get("fileExt", "") 

        try:
            origSizeBytes = int(dataSet.get("origSizeBytes")) 
        except:
            origSizeBytes = 0 
        saveSet["origSizeBytes"] = origSizeBytes

        try:
            width = int(dataSet.get("width")) 
        except:
            width = 0 
        saveSet["width"] = width

        try:
            height = int(dataSet.get("height")) 
        except:
            height = 0 
        saveSet["height"] = height

        saveSet["derivedFileID"] = dataSet.get("derivedFileID", "") 

        saveSet["derivedThumbID"] = dataSet.get("derivedThumbID", "") 

        try:
            derivedWidth = int(dataSet.get("derivedWidth")) 
        except:
            derivedWidth = 0 
        saveSet["derivedWidth"] = derivedWidth

        try:
            derivedHeight = int(dataSet.get("derivedHeight")) 
        except:
            derivedHeight = 0 
        saveSet["derivedHeight"] = derivedHeight

        try:
            derivedSizeBytes = int(dataSet.get("derivedSizeBytes")) 
        except:
            derivedSizeBytes = 0 
        saveSet["derivedSizeBytes"] = derivedSizeBytes

        saveSet["exifStripped"] = dataSet.get("exifStripped", "") 

        saveSet["processStatus"] = dataSet.get("processStatus", "") 

        saveSet["errMsg"] = dataSet.get("errMsg", "") 

        saveSet["ownerID"] = dataSet.get("ownerID", "") 

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_asset 修改记录
def update_ch_asset(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        fileID = dataSet.get("fileID") 
        if fileID:
            saveSet["fileID"] = fileID

        thumbnailID = dataSet.get("thumbnailID") 
        if thumbnailID:
            saveSet["thumbnailID"] = thumbnailID

        contentHash = dataSet.get("contentHash") 
        if contentHash:
            saveSet["contentHash"] = contentHash

        fileSystem = dataSet.get("fileSystem") 
        if fileSystem:
            saveSet["fileSystem"] = fileSystem

        storageBucket = dataSet.get("storageBucket") 
        if storageBucket:
            saveSet["storageBucket"] = storageBucket

        storagePath = dataSet.get("storagePath") 
        if storagePath:
            saveSet["storagePath"] = storagePath

        objectName = dataSet.get("objectName") 
        if objectName:
            saveSet["objectName"] = objectName

        origName = dataSet.get("origName") 
        if origName:
            saveSet["origName"] = origName

        mimeType = dataSet.get("mimeType") 
        if mimeType:
            saveSet["mimeType"] = mimeType

        fileExt = dataSet.get("fileExt") 
        if fileExt:
            saveSet["fileExt"] = fileExt

        try:
            origSizeBytes = int(dataSet.get("origSizeBytes")) 
            saveSet["origSizeBytes"] = origSizeBytes
        except:
            pass

        try:
            width = int(dataSet.get("width")) 
            saveSet["width"] = width
        except:
            pass

        try:
            height = int(dataSet.get("height")) 
            saveSet["height"] = height
        except:
            pass

        derivedFileID = dataSet.get("derivedFileID") 
        if derivedFileID:
            saveSet["derivedFileID"] = derivedFileID

        derivedThumbID = dataSet.get("derivedThumbID") 
        if derivedThumbID:
            saveSet["derivedThumbID"] = derivedThumbID

        try:
            derivedWidth = int(dataSet.get("derivedWidth")) 
            saveSet["derivedWidth"] = derivedWidth
        except:
            pass

        try:
            derivedHeight = int(dataSet.get("derivedHeight")) 
            saveSet["derivedHeight"] = derivedHeight
        except:
            pass

        try:
            derivedSizeBytes = int(dataSet.get("derivedSizeBytes")) 
            saveSet["derivedSizeBytes"] = derivedSizeBytes
        except:
            pass

        exifStripped = dataSet.get("exifStripped") 
        if exifStripped:
            saveSet["exifStripped"] = exifStripped

        processStatus = dataSet.get("processStatus") 
        if processStatus:
            saveSet["processStatus"] = processStatus

        errMsg = dataSet.get("errMsg") 
        if errMsg:
            saveSet["errMsg"] = errMsg

        ownerID = dataSet.get("ownerID") 
        if ownerID:
            saveSet["ownerID"] = ownerID

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_asset end




#ch_layout begin 

def tablename_convertor_ch_layout():
    tableName = "ch_layout"
    tableName = tableName.lower()
    return tableName


def decode_tablename_ch_layout(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建ch_layout表
def create_ch_layout(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "layoutCode VARCHAR(64) NOT NULL UNIQUE COMMENT '版式唯一编码 如stack_v1',",
    "layoutName VARCHAR(64) NOT NULL COMMENT '版式名称',",
    "layoutType VARCHAR(24) NOT NULL COMMENT 'stack上下 或 carousel左右轮播 或 longimage长图 或 swipe左右滑动浏览',",
    "platform VARCHAR(24) NOT NULL COMMENT 'wechat_mp或xiaohongshu或generic',",
    "`engine` VARCHAR(24) NOT NULL DEFAULT 'jinja2' COMMENT '渲染引擎',",
    "templatePath VARCHAR(255) NULL COMMENT '模板文件相对路径',",
    "templateVer VARCHAR(24) NOT NULL DEFAULT 'v1' COMMENT '模板版本',",
    "outputKind VARCHAR(24) NOT NULL DEFAULT 'html' COMMENT 'html或png或zip',",
    "specJson VARCHAR(1000) NULL COMMENT '版式参数JSON 尺寸或间距或配色',",
    "previewFileID VARCHAR(200) NULL COMMENT '版式预览图fileID',",
    "builtinFlag CHAR(1) NOT NULL DEFAULT '1' COMMENT '是否内置',",
    "enabled CHAR(1) NOT NULL DEFAULT '1' COMMENT '是否启用',",
    "sortWeight SMALLINT NOT NULL DEFAULT 100 COMMENT '排序权重 越小越靠前',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "platform")
        rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除ch_layout表
def drop_ch_layout(tableName):
    result = dropTableGeneral(tableName)
    return result


#ch_layout 删除记录
def delete_ch_layout(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_layout 增加记录
def insert_ch_layout(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["layoutCode"] = dataSet.get("layoutCode", "") 

        saveSet["layoutName"] = dataSet.get("layoutName", "") 

        saveSet["layoutType"] = dataSet.get("layoutType", "") 

        saveSet["platform"] = dataSet.get("platform", "") 

        saveSet["engine"] = dataSet.get("engine", "") 

        saveSet["templatePath"] = dataSet.get("templatePath", "") 

        saveSet["templateVer"] = dataSet.get("templateVer", "") 

        saveSet["outputKind"] = dataSet.get("outputKind", "") 

        saveSet["specJson"] = dataSet.get("specJson", "") 

        saveSet["previewFileID"] = dataSet.get("previewFileID", "") 

        saveSet["builtinFlag"] = dataSet.get("builtinFlag", "") 

        saveSet["enabled"] = dataSet.get("enabled", "") 

        try:
            sortWeight = int(dataSet.get("sortWeight")) 
        except:
            sortWeight = 0 
        saveSet["sortWeight"] = sortWeight

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_layout 修改记录
def update_ch_layout(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        layoutCode = dataSet.get("layoutCode") 
        if layoutCode:
            saveSet["layoutCode"] = layoutCode

        layoutName = dataSet.get("layoutName") 
        if layoutName:
            saveSet["layoutName"] = layoutName

        layoutType = dataSet.get("layoutType") 
        if layoutType:
            saveSet["layoutType"] = layoutType

        platform = dataSet.get("platform") 
        if platform:
            saveSet["platform"] = platform

        engine = dataSet.get("engine") 
        if engine:
            saveSet["engine"] = engine

        templatePath = dataSet.get("templatePath") 
        if templatePath:
            saveSet["templatePath"] = templatePath

        templateVer = dataSet.get("templateVer") 
        if templateVer:
            saveSet["templateVer"] = templateVer

        outputKind = dataSet.get("outputKind") 
        if outputKind:
            saveSet["outputKind"] = outputKind

        specJson = dataSet.get("specJson") 
        if specJson:
            saveSet["specJson"] = specJson

        previewFileID = dataSet.get("previewFileID") 
        if previewFileID:
            saveSet["previewFileID"] = previewFileID

        builtinFlag = dataSet.get("builtinFlag") 
        if builtinFlag:
            saveSet["builtinFlag"] = builtinFlag

        enabled = dataSet.get("enabled") 
        if enabled:
            saveSet["enabled"] = enabled

        try:
            sortWeight = int(dataSet.get("sortWeight")) 
            saveSet["sortWeight"] = sortWeight
        except:
            pass

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_layout end




#ch_platform begin 

def tablename_convertor_ch_platform():
    tableName = "ch_platform"
    tableName = tableName.lower()
    return tableName


def decode_tablename_ch_platform(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建ch_platform表
def create_ch_platform(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "platformCode VARCHAR(32) NOT NULL UNIQUE COMMENT 'wechat_mp或xiaohongshu或generic',",
    "platformName VARCHAR(64) NOT NULL COMMENT '平台名称',",
    "subjectScope VARCHAR(128) NULL COMMENT '支持的主体类型 如个人订阅号或认证服务号',",
    "deliverMode VARCHAR(24) NOT NULL COMMENT 'draft_box或asset_pack或api_publish',",
    "titleMaxLen SMALLINT NOT NULL DEFAULT 64 COMMENT '标题字数上限',",
    "summaryMaxLen SMALLINT NOT NULL DEFAULT 200 COMMENT '简介字数上限',",
    "coverSpec VARCHAR(64) NULL COMMENT '封面规格 如900x500',",
    "imageSpec VARCHAR(64) NULL COMMENT '正文图规格 如1080x1440',",
    "imageMaxCount SMALLINT NOT NULL DEFAULT 20 COMMENT '图片数量上限',",
    "allowSvgFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '是否允许SVG交互',",
    "needAiLabelFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '是否强制AI内容标识',",
    "autoPublishFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '是否允许自动发布',",
    "limitNote VARCHAR(512) NULL COMMENT '限制与风控说明',",
    "docUrl VARCHAR(512) NULL COMMENT '官方文档地址',",
    "enabled CHAR(1) NOT NULL DEFAULT '1' COMMENT '是否启用',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "platformCode")
        rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除ch_platform表
def drop_ch_platform(tableName):
    result = dropTableGeneral(tableName)
    return result


#ch_platform 删除记录
def delete_ch_platform(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_platform 增加记录
def insert_ch_platform(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["platformCode"] = dataSet.get("platformCode", "") 

        saveSet["platformName"] = dataSet.get("platformName", "") 

        saveSet["subjectScope"] = dataSet.get("subjectScope", "") 

        saveSet["deliverMode"] = dataSet.get("deliverMode", "") 

        try:
            titleMaxLen = int(dataSet.get("titleMaxLen")) 
        except:
            titleMaxLen = 0 
        saveSet["titleMaxLen"] = titleMaxLen

        try:
            summaryMaxLen = int(dataSet.get("summaryMaxLen")) 
        except:
            summaryMaxLen = 0 
        saveSet["summaryMaxLen"] = summaryMaxLen

        saveSet["coverSpec"] = dataSet.get("coverSpec", "") 

        saveSet["imageSpec"] = dataSet.get("imageSpec", "") 

        try:
            imageMaxCount = int(dataSet.get("imageMaxCount")) 
        except:
            imageMaxCount = 0 
        saveSet["imageMaxCount"] = imageMaxCount

        saveSet["allowSvgFlag"] = dataSet.get("allowSvgFlag", "") 

        saveSet["needAiLabelFlag"] = dataSet.get("needAiLabelFlag", "") 

        saveSet["autoPublishFlag"] = dataSet.get("autoPublishFlag", "") 

        saveSet["limitNote"] = dataSet.get("limitNote", "") 

        saveSet["docUrl"] = dataSet.get("docUrl", "") 

        saveSet["enabled"] = dataSet.get("enabled", "") 

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_platform 修改记录
def update_ch_platform(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        platformCode = dataSet.get("platformCode") 
        if platformCode:
            saveSet["platformCode"] = platformCode

        platformName = dataSet.get("platformName") 
        if platformName:
            saveSet["platformName"] = platformName

        subjectScope = dataSet.get("subjectScope") 
        if subjectScope:
            saveSet["subjectScope"] = subjectScope

        deliverMode = dataSet.get("deliverMode") 
        if deliverMode:
            saveSet["deliverMode"] = deliverMode

        try:
            titleMaxLen = int(dataSet.get("titleMaxLen")) 
            saveSet["titleMaxLen"] = titleMaxLen
        except:
            pass

        try:
            summaryMaxLen = int(dataSet.get("summaryMaxLen")) 
            saveSet["summaryMaxLen"] = summaryMaxLen
        except:
            pass

        coverSpec = dataSet.get("coverSpec") 
        if coverSpec:
            saveSet["coverSpec"] = coverSpec

        imageSpec = dataSet.get("imageSpec") 
        if imageSpec:
            saveSet["imageSpec"] = imageSpec

        try:
            imageMaxCount = int(dataSet.get("imageMaxCount")) 
            saveSet["imageMaxCount"] = imageMaxCount
        except:
            pass

        allowSvgFlag = dataSet.get("allowSvgFlag") 
        if allowSvgFlag:
            saveSet["allowSvgFlag"] = allowSvgFlag

        needAiLabelFlag = dataSet.get("needAiLabelFlag") 
        if needAiLabelFlag:
            saveSet["needAiLabelFlag"] = needAiLabelFlag

        autoPublishFlag = dataSet.get("autoPublishFlag") 
        if autoPublishFlag:
            saveSet["autoPublishFlag"] = autoPublishFlag

        limitNote = dataSet.get("limitNote") 
        if limitNote:
            saveSet["limitNote"] = limitNote

        docUrl = dataSet.get("docUrl") 
        if docUrl:
            saveSet["docUrl"] = docUrl

        enabled = dataSet.get("enabled") 
        if enabled:
            saveSet["enabled"] = enabled

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_platform end




#ch_render_job begin 

def tablename_convertor_ch_render_job():
    tableName = "ch_render_job"
    tableName = tableName.lower()
    return tableName


def decode_tablename_ch_render_job(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建ch_render_job表
def create_ch_render_job(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "jobCode VARCHAR(64) NOT NULL UNIQUE COMMENT '任务编码 幂等键',",
    "topicID BIGINT NOT NULL COMMENT '关联ch_topic.recID',",
    "layoutCode VARCHAR(64) NOT NULL COMMENT '版式编码',",
    "platform VARCHAR(24) NOT NULL COMMENT '目标平台',",
    "jobStatus VARCHAR(24) NOT NULL DEFAULT 'PENDING' COMMENT 'PENDING或RUNNING或DONE或FAILED',",
    "inputHash CHAR(64) NULL COMMENT '输入快照sha256 内容未变可复用产物',",
    "progress TINYINT NOT NULL DEFAULT 0 COMMENT '进度百分比',",
    "errMsg VARCHAR(512) NULL COMMENT '错误信息',",
    "startYMDHMS VARCHAR(16) NULL COMMENT '开始时间',",
    "finishYMDHMS VARCHAR(16) NULL COMMENT '完成时间',",
    "costMs INT NULL COMMENT '耗时毫秒',",
    "ownerID VARCHAR(64) NULL COMMENT '发起者loginID',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "topicID")
        rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除ch_render_job表
def drop_ch_render_job(tableName):
    result = dropTableGeneral(tableName)
    return result


#ch_render_job 删除记录
def delete_ch_render_job(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_render_job 增加记录
def insert_ch_render_job(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["jobCode"] = dataSet.get("jobCode", "") 

        try:
            topicID = int(dataSet.get("topicID")) 
        except:
            topicID = 0 
        saveSet["topicID"] = topicID

        saveSet["layoutCode"] = dataSet.get("layoutCode", "") 

        saveSet["platform"] = dataSet.get("platform", "") 

        saveSet["jobStatus"] = dataSet.get("jobStatus", "") 

        saveSet["inputHash"] = dataSet.get("inputHash", "") 

        try:
            progress = int(dataSet.get("progress")) 
        except:
            progress = 0 
        saveSet["progress"] = progress

        saveSet["errMsg"] = dataSet.get("errMsg", "") 

        saveSet["startYMDHMS"] = dataSet.get("startYMDHMS", "") 

        saveSet["finishYMDHMS"] = dataSet.get("finishYMDHMS", "") 

        try:
            costMs = int(dataSet.get("costMs")) 
        except:
            costMs = 0 
        saveSet["costMs"] = costMs

        saveSet["ownerID"] = dataSet.get("ownerID", "") 

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_render_job 修改记录
def update_ch_render_job(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        jobCode = dataSet.get("jobCode") 
        if jobCode:
            saveSet["jobCode"] = jobCode

        try:
            topicID = int(dataSet.get("topicID")) 
            saveSet["topicID"] = topicID
        except:
            pass

        layoutCode = dataSet.get("layoutCode") 
        if layoutCode:
            saveSet["layoutCode"] = layoutCode

        platform = dataSet.get("platform") 
        if platform:
            saveSet["platform"] = platform

        jobStatus = dataSet.get("jobStatus") 
        if jobStatus:
            saveSet["jobStatus"] = jobStatus

        inputHash = dataSet.get("inputHash") 
        if inputHash:
            saveSet["inputHash"] = inputHash

        try:
            progress = int(dataSet.get("progress")) 
            saveSet["progress"] = progress
        except:
            pass

        errMsg = dataSet.get("errMsg") 
        if errMsg:
            saveSet["errMsg"] = errMsg

        startYMDHMS = dataSet.get("startYMDHMS") 
        if startYMDHMS:
            saveSet["startYMDHMS"] = startYMDHMS

        finishYMDHMS = dataSet.get("finishYMDHMS") 
        if finishYMDHMS:
            saveSet["finishYMDHMS"] = finishYMDHMS

        try:
            costMs = int(dataSet.get("costMs")) 
            saveSet["costMs"] = costMs
        except:
            pass

        ownerID = dataSet.get("ownerID") 
        if ownerID:
            saveSet["ownerID"] = ownerID

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_render_job end




#ch_artifact begin 

def tablename_convertor_ch_artifact():
    tableName = "ch_artifact"
    tableName = tableName.lower()
    return tableName


def decode_tablename_ch_artifact(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建ch_artifact表
def create_ch_artifact(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "artifactKey VARCHAR(400) NOT NULL UNIQUE COMMENT '幂等键 jobID加冒号加kind加冒号加platform加冒号加seqNo',",
    "jobID BIGINT NOT NULL COMMENT '关联ch_render_job.recID',",
    "topicID BIGINT NOT NULL COMMENT '冗余主题ID 便于按主题查产物',",
    "kind VARCHAR(24) NOT NULL COMMENT 'html或png或zip或json或markdown',",
    "platform VARCHAR(24) NOT NULL COMMENT '目标平台',",
    "fileID VARCHAR(200) NOT NULL COMMENT '产物文件fileID',",
    "thumbnailID VARCHAR(200) NULL COMMENT '产物缩略图fileID',",
    "seqNo SMALLINT NOT NULL DEFAULT 1 COMMENT '序号 图集多张时递增',",
    "artifactVer INT NOT NULL DEFAULT 1 COMMENT '产物版本',",
    "specNote VARCHAR(128) NULL COMMENT '规格说明 如1080x1440',",
    "sizeBytes BIGINT NULL COMMENT '字节数',",
    "artifactStatus VARCHAR(24) NOT NULL DEFAULT 'READY' COMMENT 'READY或EXPIRED',",
    "expireYMDHMS VARCHAR(16) NULL COMMENT '保留到期时间',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "jobID")
        rtn = mysqlDB.executeWrite(sqlStr)
        sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "topicID")
        rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除ch_artifact表
def drop_ch_artifact(tableName):
    result = dropTableGeneral(tableName)
    return result


#ch_artifact 删除记录
def delete_ch_artifact(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_artifact 增加记录
def insert_ch_artifact(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["artifactKey"] = dataSet.get("artifactKey", "") 

        try:
            jobID = int(dataSet.get("jobID")) 
        except:
            jobID = 0 
        saveSet["jobID"] = jobID

        try:
            topicID = int(dataSet.get("topicID")) 
        except:
            topicID = 0 
        saveSet["topicID"] = topicID

        saveSet["kind"] = dataSet.get("kind", "") 

        saveSet["platform"] = dataSet.get("platform", "") 

        saveSet["fileID"] = dataSet.get("fileID", "") 

        saveSet["thumbnailID"] = dataSet.get("thumbnailID", "") 

        try:
            seqNo = int(dataSet.get("seqNo")) 
        except:
            seqNo = 0 
        saveSet["seqNo"] = seqNo

        try:
            artifactVer = int(dataSet.get("artifactVer")) 
        except:
            artifactVer = 0 
        saveSet["artifactVer"] = artifactVer

        saveSet["specNote"] = dataSet.get("specNote", "") 

        try:
            sizeBytes = int(dataSet.get("sizeBytes")) 
        except:
            sizeBytes = 0 
        saveSet["sizeBytes"] = sizeBytes

        saveSet["artifactStatus"] = dataSet.get("artifactStatus", "") 

        saveSet["expireYMDHMS"] = dataSet.get("expireYMDHMS", "") 

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_artifact 修改记录
def update_ch_artifact(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        artifactKey = dataSet.get("artifactKey") 
        if artifactKey:
            saveSet["artifactKey"] = artifactKey

        try:
            jobID = int(dataSet.get("jobID")) 
            saveSet["jobID"] = jobID
        except:
            pass

        try:
            topicID = int(dataSet.get("topicID")) 
            saveSet["topicID"] = topicID
        except:
            pass

        kind = dataSet.get("kind") 
        if kind:
            saveSet["kind"] = kind

        platform = dataSet.get("platform") 
        if platform:
            saveSet["platform"] = platform

        fileID = dataSet.get("fileID") 
        if fileID:
            saveSet["fileID"] = fileID

        thumbnailID = dataSet.get("thumbnailID") 
        if thumbnailID:
            saveSet["thumbnailID"] = thumbnailID

        try:
            seqNo = int(dataSet.get("seqNo")) 
            saveSet["seqNo"] = seqNo
        except:
            pass

        try:
            artifactVer = int(dataSet.get("artifactVer")) 
            saveSet["artifactVer"] = artifactVer
        except:
            pass

        specNote = dataSet.get("specNote") 
        if specNote:
            saveSet["specNote"] = specNote

        try:
            sizeBytes = int(dataSet.get("sizeBytes")) 
            saveSet["sizeBytes"] = sizeBytes
        except:
            pass

        artifactStatus = dataSet.get("artifactStatus") 
        if artifactStatus:
            saveSet["artifactStatus"] = artifactStatus

        expireYMDHMS = dataSet.get("expireYMDHMS") 
        if expireYMDHMS:
            saveSet["expireYMDHMS"] = expireYMDHMS

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_artifact end




#ch_account begin 

def tablename_convertor_ch_account():
    tableName = "ch_account"
    tableName = tableName.lower()
    return tableName


def decode_tablename_ch_account(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建ch_account表
def create_ch_account(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "accountCode VARCHAR(64) NOT NULL UNIQUE COMMENT '账号幂等键',",
    "platform VARCHAR(24) NOT NULL COMMENT '所属平台',",
    "accountName VARCHAR(128) NOT NULL COMMENT '账号名称',",
    "subjectType VARCHAR(24) NOT NULL COMMENT 'personal或enterprise',",
    "verifiedFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '是否已认证',",
    "capability VARCHAR(64) NOT NULL COMMENT 'draft_box或asset_pack或api_publish',",
    "appID VARCHAR(64) NULL COMMENT '平台appID 微信为appid',",
    "credentialCipher TEXT NULL COMMENT '凭据密文 AES加密 明文永不落库',",
    "credentialIV VARCHAR(64) NULL COMMENT '加密初始向量',",
    "expireYMDHMS VARCHAR(16) NULL COMMENT '凭据到期时间',",
    "healthStatus VARCHAR(24) NOT NULL DEFAULT 'UNKNOWN' COMMENT 'OK或EXPIRING或INVALID或UNKNOWN',",
    "lastCheckYMDHMS VARCHAR(16) NULL COMMENT '最近健康检查时间',",
    "lastUseYMDHMS VARCHAR(16) NULL COMMENT '最近调用时间',",
    "ownerID VARCHAR(64) NULL COMMENT '归属loginID',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "accountCode")
        rtn = mysqlDB.executeWrite(sqlStr)
        sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "platform")
        rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除ch_account表
def drop_ch_account(tableName):
    result = dropTableGeneral(tableName)
    return result


#ch_account 删除记录
def delete_ch_account(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_account 增加记录
def insert_ch_account(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["accountCode"] = dataSet.get("accountCode", "") 

        saveSet["platform"] = dataSet.get("platform", "") 

        saveSet["accountName"] = dataSet.get("accountName", "") 

        saveSet["subjectType"] = dataSet.get("subjectType", "") 

        saveSet["verifiedFlag"] = dataSet.get("verifiedFlag", "") 

        saveSet["capability"] = dataSet.get("capability", "") 

        saveSet["appID"] = dataSet.get("appID", "") 

        saveSet["credentialCipher"] = dataSet.get("credentialCipher", "") 

        saveSet["credentialIV"] = dataSet.get("credentialIV", "") 

        saveSet["expireYMDHMS"] = dataSet.get("expireYMDHMS", "") 

        saveSet["healthStatus"] = dataSet.get("healthStatus", "") 

        saveSet["lastCheckYMDHMS"] = dataSet.get("lastCheckYMDHMS", "") 

        saveSet["lastUseYMDHMS"] = dataSet.get("lastUseYMDHMS", "") 

        saveSet["ownerID"] = dataSet.get("ownerID", "") 

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_account 修改记录
def update_ch_account(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        accountCode = dataSet.get("accountCode") 
        if accountCode:
            saveSet["accountCode"] = accountCode

        platform = dataSet.get("platform") 
        if platform:
            saveSet["platform"] = platform

        accountName = dataSet.get("accountName") 
        if accountName:
            saveSet["accountName"] = accountName

        subjectType = dataSet.get("subjectType") 
        if subjectType:
            saveSet["subjectType"] = subjectType

        verifiedFlag = dataSet.get("verifiedFlag") 
        if verifiedFlag:
            saveSet["verifiedFlag"] = verifiedFlag

        capability = dataSet.get("capability") 
        if capability:
            saveSet["capability"] = capability

        appID = dataSet.get("appID") 
        if appID:
            saveSet["appID"] = appID

        credentialCipher = dataSet.get("credentialCipher") 
        if credentialCipher:
            saveSet["credentialCipher"] = credentialCipher

        credentialIV = dataSet.get("credentialIV") 
        if credentialIV:
            saveSet["credentialIV"] = credentialIV

        expireYMDHMS = dataSet.get("expireYMDHMS") 
        if expireYMDHMS:
            saveSet["expireYMDHMS"] = expireYMDHMS

        healthStatus = dataSet.get("healthStatus") 
        if healthStatus:
            saveSet["healthStatus"] = healthStatus

        lastCheckYMDHMS = dataSet.get("lastCheckYMDHMS") 
        if lastCheckYMDHMS:
            saveSet["lastCheckYMDHMS"] = lastCheckYMDHMS

        lastUseYMDHMS = dataSet.get("lastUseYMDHMS") 
        if lastUseYMDHMS:
            saveSet["lastUseYMDHMS"] = lastUseYMDHMS

        ownerID = dataSet.get("ownerID") 
        if ownerID:
            saveSet["ownerID"] = ownerID

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_account end




#ch_publish_record begin 

def tablename_convertor_ch_publish_record():
    tableName = "ch_publish_record"
    tableName = tableName.lower()
    return tableName


def decode_tablename_ch_publish_record(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建ch_publish_record表
def create_ch_publish_record(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "idempotencyKey VARCHAR(400) NOT NULL UNIQUE COMMENT '幂等键 由调用方传入 防重复提交',",
    "artifactId BIGINT NOT NULL COMMENT '关联ch_artifact.recID',",
    "topicID BIGINT NOT NULL COMMENT '冗余主题ID',",
    "accountID BIGINT NULL COMMENT '关联ch_account.recID 素材包导出可空',",
    "platform VARCHAR(24) NOT NULL COMMENT '目标平台',",
    "deliverMode VARCHAR(24) NOT NULL COMMENT 'draft_box或asset_pack',",
    "requestJson JSON NULL COMMENT '请求报文摘要',",
    "responseJson JSON NULL COMMENT '响应报文摘要',",
    "errcode INT NULL COMMENT '平台返回码',",
    "errmsg VARCHAR(512) NULL COMMENT '平台返回信息',",
    "success CHAR(1) NOT NULL DEFAULT '0' COMMENT '是否成功',",
    "remoteID VARCHAR(128) NULL COMMENT '平台侧ID 微信草稿mediaID等',",
    "operator VARCHAR(64) NULL COMMENT '操作者loginID',",
    "pushedYMDHMS VARCHAR(16) NULL COMMENT '投递时间',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "artifactId")
        rtn = mysqlDB.executeWrite(sqlStr)
        sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "topicID")
        rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除ch_publish_record表
def drop_ch_publish_record(tableName):
    result = dropTableGeneral(tableName)
    return result


#ch_publish_record 删除记录
def delete_ch_publish_record(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_publish_record 增加记录
def insert_ch_publish_record(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["idempotencyKey"] = dataSet.get("idempotencyKey", "") 

        try:
            artifactId = int(dataSet.get("artifactId")) 
        except:
            artifactId = 0 
        saveSet["artifactId"] = artifactId

        try:
            topicID = int(dataSet.get("topicID")) 
        except:
            topicID = 0 
        saveSet["topicID"] = topicID

        try:
            accountID = int(dataSet.get("accountID")) 
        except:
            accountID = 0 
        saveSet["accountID"] = accountID

        saveSet["platform"] = dataSet.get("platform", "") 

        saveSet["deliverMode"] = dataSet.get("deliverMode", "") 

        saveSet["requestJson"] = dataSet.get("requestJson", "") 

        saveSet["responseJson"] = dataSet.get("responseJson", "") 

        try:
            errcode = int(dataSet.get("errcode")) 
        except:
            errcode = 0 
        saveSet["errcode"] = errcode

        saveSet["errmsg"] = dataSet.get("errmsg", "") 

        saveSet["success"] = dataSet.get("success", "") 

        saveSet["remoteID"] = dataSet.get("remoteID", "") 

        saveSet["operator"] = dataSet.get("operator", "") 

        saveSet["pushedYMDHMS"] = dataSet.get("pushedYMDHMS", "") 

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_publish_record 修改记录
def update_ch_publish_record(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        idempotencyKey = dataSet.get("idempotencyKey") 
        if idempotencyKey:
            saveSet["idempotencyKey"] = idempotencyKey

        try:
            artifactId = int(dataSet.get("artifactId")) 
            saveSet["artifactId"] = artifactId
        except:
            pass

        try:
            topicID = int(dataSet.get("topicID")) 
            saveSet["topicID"] = topicID
        except:
            pass

        try:
            accountID = int(dataSet.get("accountID")) 
            saveSet["accountID"] = accountID
        except:
            pass

        platform = dataSet.get("platform") 
        if platform:
            saveSet["platform"] = platform

        deliverMode = dataSet.get("deliverMode") 
        if deliverMode:
            saveSet["deliverMode"] = deliverMode

        requestJson = dataSet.get("requestJson") 
        if requestJson:
            saveSet["requestJson"] = requestJson

        responseJson = dataSet.get("responseJson") 
        if responseJson:
            saveSet["responseJson"] = responseJson

        try:
            errcode = int(dataSet.get("errcode")) 
            saveSet["errcode"] = errcode
        except:
            pass

        errmsg = dataSet.get("errmsg") 
        if errmsg:
            saveSet["errmsg"] = errmsg

        success = dataSet.get("success") 
        if success:
            saveSet["success"] = success

        remoteID = dataSet.get("remoteID") 
        if remoteID:
            saveSet["remoteID"] = remoteID

        operator = dataSet.get("operator") 
        if operator:
            saveSet["operator"] = operator

        pushedYMDHMS = dataSet.get("pushedYMDHMS") 
        if pushedYMDHMS:
            saveSet["pushedYMDHMS"] = pushedYMDHMS

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_publish_record end




#ch_mcp_token begin 

def tablename_convertor_ch_mcp_token():
    tableName = "ch_mcp_token"
    tableName = tableName.lower()
    return tableName


def decode_tablename_ch_mcp_token(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建ch_mcp_token表
def create_ch_mcp_token(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "tokenHash CHAR(64) NOT NULL UNIQUE COMMENT 'token的sha256 不存明文',",
    "tokenName VARCHAR(64) NOT NULL COMMENT '令牌名称',",
    "tokenScope VARCHAR(64) NOT NULL DEFAULT 'read' COMMENT 'read或write或publish',",
    "projectCode VARCHAR(64) NULL COMMENT '绑定项目',",
    "transport VARCHAR(16) NOT NULL DEFAULT 'sse' COMMENT 'sse或stdio',",
    "lastUseYMDHMS VARCHAR(16) NULL COMMENT '最近使用时间',",
    "useCount INT NOT NULL DEFAULT 0 COMMENT '累计调用次数',",
    "revokedYMDHMS VARCHAR(16) NULL COMMENT '吊销时间 有值即失效',",
    "ownerID VARCHAR(64) NULL COMMENT '创建者loginID',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        #sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "indexKey")
        #rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除ch_mcp_token表
def drop_ch_mcp_token(tableName):
    result = dropTableGeneral(tableName)
    return result


#ch_mcp_token 删除记录
def delete_ch_mcp_token(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_mcp_token 增加记录
def insert_ch_mcp_token(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["tokenHash"] = dataSet.get("tokenHash", "") 

        saveSet["tokenName"] = dataSet.get("tokenName", "") 

        saveSet["tokenScope"] = dataSet.get("tokenScope", "") 

        saveSet["projectCode"] = dataSet.get("projectCode", "") 

        saveSet["transport"] = dataSet.get("transport", "") 

        saveSet["lastUseYMDHMS"] = dataSet.get("lastUseYMDHMS", "") 

        try:
            useCount = int(dataSet.get("useCount")) 
        except:
            useCount = 0 
        saveSet["useCount"] = useCount

        saveSet["revokedYMDHMS"] = dataSet.get("revokedYMDHMS", "") 

        saveSet["ownerID"] = dataSet.get("ownerID", "") 

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_mcp_token 修改记录
def update_ch_mcp_token(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        tokenHash = dataSet.get("tokenHash") 
        if tokenHash:
            saveSet["tokenHash"] = tokenHash

        tokenName = dataSet.get("tokenName") 
        if tokenName:
            saveSet["tokenName"] = tokenName

        tokenScope = dataSet.get("tokenScope") 
        if tokenScope:
            saveSet["tokenScope"] = tokenScope

        projectCode = dataSet.get("projectCode") 
        if projectCode:
            saveSet["projectCode"] = projectCode

        transport = dataSet.get("transport") 
        if transport:
            saveSet["transport"] = transport

        lastUseYMDHMS = dataSet.get("lastUseYMDHMS") 
        if lastUseYMDHMS:
            saveSet["lastUseYMDHMS"] = lastUseYMDHMS

        try:
            useCount = int(dataSet.get("useCount")) 
            saveSet["useCount"] = useCount
        except:
            pass

        revokedYMDHMS = dataSet.get("revokedYMDHMS") 
        if revokedYMDHMS:
            saveSet["revokedYMDHMS"] = revokedYMDHMS

        ownerID = dataSet.get("ownerID") 
        if ownerID:
            saveSet["ownerID"] = ownerID

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_mcp_token end




#ch_audit_log begin 

def tablename_convertor_ch_audit_log():
    tableName = "ch_audit_log"
    tableName = tableName.lower()
    return tableName


def decode_tablename_ch_audit_log(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建ch_audit_log表
def create_ch_audit_log(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "actor VARCHAR(64) NULL COMMENT '操作者 loginID或mcp令牌名',",
    "`source` VARCHAR(16) NOT NULL DEFAULT 'web' COMMENT 'web或api或mcp',",
    "`action` VARCHAR(64) NOT NULL COMMENT '动作 如topic.create或publish.push',",
    "targetType VARCHAR(32) NULL COMMENT '对象类型',",
    "targetID VARCHAR(64) NULL COMMENT '对象ID',",
    "payloadDigest CHAR(64) NULL COMMENT '入参摘要sha256',",
    "result VARCHAR(24) NOT NULL DEFAULT 'OK' COMMENT 'OK或FAIL',",
    "errMsg VARCHAR(512) NULL COMMENT '错误信息',",
    "costMs INT NULL COMMENT '耗时毫秒',",
    "ipAddr VARCHAR(64) NULL COMMENT '来源IP',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        # sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "actor")
        # rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除ch_audit_log表
def drop_ch_audit_log(tableName):
    result = dropTableGeneral(tableName)
    return result


#ch_audit_log 删除记录
def delete_ch_audit_log(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_audit_log 增加记录
def insert_ch_audit_log(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["actor"] = dataSet.get("actor", "") 

        saveSet["source"] = dataSet.get("source", "") 

        saveSet["action"] = dataSet.get("action", "") 

        saveSet["targetType"] = dataSet.get("targetType", "") 

        saveSet["targetID"] = dataSet.get("targetID", "") 

        saveSet["payloadDigest"] = dataSet.get("payloadDigest", "") 

        saveSet["result"] = dataSet.get("result", "") 

        saveSet["errMsg"] = dataSet.get("errMsg", "") 

        try:
            costMs = int(dataSet.get("costMs")) 
        except:
            costMs = 0 
        saveSet["costMs"] = costMs

        saveSet["ipAddr"] = dataSet.get("ipAddr", "") 

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_audit_log 修改记录
def update_ch_audit_log(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        actor = dataSet.get("actor") 
        if actor:
            saveSet["actor"] = actor

        source = dataSet.get("source") 
        if source:
            saveSet["source"] = source

        action = dataSet.get("action") 
        if action:
            saveSet["action"] = action

        targetType = dataSet.get("targetType") 
        if targetType:
            saveSet["targetType"] = targetType

        targetID = dataSet.get("targetID") 
        if targetID:
            saveSet["targetID"] = targetID

        payloadDigest = dataSet.get("payloadDigest") 
        if payloadDigest:
            saveSet["payloadDigest"] = payloadDigest

        result = dataSet.get("result") 
        if result:
            saveSet["result"] = result

        errMsg = dataSet.get("errMsg") 
        if errMsg:
            saveSet["errMsg"] = errMsg

        try:
            costMs = int(dataSet.get("costMs")) 
            saveSet["costMs"] = costMs
        except:
            pass

        ipAddr = dataSet.get("ipAddr") 
        if ipAddr:
            saveSet["ipAddr"] = ipAddr

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_audit_log end




#ch_topic_version begin 

def tablename_convertor_ch_topic_version():
    tableName = "ch_topic_version"
    tableName = tableName.lower()
    return tableName


def decode_tablename_ch_topic_version(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建ch_topic_version表
def create_ch_topic_version(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "verKey VARCHAR(64) NOT NULL UNIQUE COMMENT '幂等键 topicID加冒号加versionNo',",
    "topicID BIGINT NOT NULL COMMENT '关联ch_topic.recID',",
    "versionNo INT NOT NULL COMMENT '版本号 从1递增',",
    "snapshotJson MEDIUMTEXT NULL COMMENT '主题完整快照JSON',",
    "diffNote VARCHAR(512) NULL COMMENT '变更说明',",
    "ownerID VARCHAR(64) NULL COMMENT '保存者loginID',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        #sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "indexKey")
        #rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除ch_topic_version表
def drop_ch_topic_version(tableName):
    result = dropTableGeneral(tableName)
    return result


#ch_topic_version 删除记录
def delete_ch_topic_version(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_topic_version 增加记录
def insert_ch_topic_version(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["verKey"] = dataSet.get("verKey", "") 

        try:
            topicID = int(dataSet.get("topicID")) 
        except:
            topicID = 0 
        saveSet["topicID"] = topicID

        try:
            versionNo = int(dataSet.get("versionNo")) 
        except:
            versionNo = 0 
        saveSet["versionNo"] = versionNo

        saveSet["snapshotJson"] = dataSet.get("snapshotJson", "") 

        saveSet["diffNote"] = dataSet.get("diffNote", "") 

        saveSet["ownerID"] = dataSet.get("ownerID", "") 

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_topic_version 修改记录
def update_ch_topic_version(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        verKey = dataSet.get("verKey") 
        if verKey:
            saveSet["verKey"] = verKey

        try:
            topicID = int(dataSet.get("topicID")) 
            saveSet["topicID"] = topicID
        except:
            pass

        try:
            versionNo = int(dataSet.get("versionNo")) 
            saveSet["versionNo"] = versionNo
        except:
            pass

        snapshotJson = dataSet.get("snapshotJson") 
        if snapshotJson:
            saveSet["snapshotJson"] = snapshotJson

        diffNote = dataSet.get("diffNote") 
        if diffNote:
            saveSet["diffNote"] = diffNote

        ownerID = dataSet.get("ownerID") 
        if ownerID:
            saveSet["ownerID"] = ownerID

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#ch_topic_version end




#weixin_pay begin 

def tablename_convertor_weixin_pay():
    tableName = "weixin_pay"
    tableName = tableName.lower()
    return tableName


def decode_tablename_weixin_pay(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建weixin_pay表
def create_weixin_pay(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "sortID INT AUTO_INCREMENT NOT NULL PRIMARY KEY COMMENT '排序ID',",
    "tradeNo VARCHAR(32) NOT NULL UNIQUE COMMENT '商户订单号',",
    "parentTradeNo VARCHAR(32) NULL COMMENT '关联的商户订单号',",
    "bizType CHAR(1) NULL COMMENT '业务类型',",
    "productID VARCHAR(64) NULL COMMENT '商品id',",
    "productName VARCHAR(256) NULL COMMENT '商品名称',",
    "quantity INT NULL COMMENT '商品数量',",
    "loginID VARCHAR(32) NULL COMMENT '客户唯一ID',",
    "contactName VARCHAR(32) NULL COMMENT '客户姓名',",
    "fee INT NOT NULL COMMENT '订单金额',",
    "feeType VARCHAR(8) NULL COMMENT '订单金额货币类型',",
    "`status` CHAR(1) NULL COMMENT '支付/退款状态',",
    "reason VARCHAR(256) NULL COMMENT '失败原因',",
    "appID VARCHAR(32) NULL COMMENT '应用appid',",
    "mchID VARCHAR(32) NULL COMMENT '商户id',",
    "transactionID VARCHAR(32) NULL COMMENT '微信支付订单号',",
    "tradeType VARCHAR(16) NULL COMMENT '交易类型',",
    "tradeState VARCHAR(32) NULL COMMENT '交易状态',",
    "tradeStateDesc VARCHAR(256) NULL COMMENT '交易状态描述',",
    "bankType VARCHAR(32) NULL COMMENT '银行类型',",
    "attach VARCHAR(128) NULL COMMENT '商户数据包',",
    "successTime VARCHAR(64) NULL COMMENT '支付/退款完成时间',",
    "openID VARCHAR(128) NULL COMMENT '用户openid',",
    "deviceID VARCHAR(32) NULL COMMENT '商户端设备号',",
    "promotionCouponID VARCHAR(32) NULL COMMENT '代金券id',",
    "promotionName VARCHAR(32) NULL COMMENT '优惠券名称',",
    "promotionScope VARCHAR(32) NULL COMMENT '优惠券作用范围',",
    "promotionType VARCHAR(32) NULL COMMENT '优惠券类型',",
    "promotionAmount INT NULL COMMENT '优惠券面额',",
    "promotionStockID VARCHAR(32) NULL COMMENT '单张代金券所对应的批次号',",
    "promotionWechatContribute INT NULL COMMENT '微信出资类型的优惠券面额',",
    "promotionMerchantContribute INT NULL COMMENT '商户出资类型的优惠券面额',",
    "promotionOtherContribute INT NULL COMMENT '其它出资类型的优惠券面额',",
    "promotionCurrency VARCHAR(16) NULL COMMENT '代金券金额所对应的货币种类',",
    "promotionGoodsDetail VARCHAR(2000) NULL COMMENT '优惠单品列表',",
    "refundFlag CHAR(1) NULL COMMENT '退款标志',",
    "refundID CHAR(32) NULL COMMENT '微信支付退款单号',",
    "refundStatus VARCHAR(32) NULL COMMENT '退款状态',",
    "userReceivedAccount VARCHAR(64) NULL COMMENT '退款入账账户',",
    "amountTotal INT NULL COMMENT '原订单总金额',",
    "amountRefund INT NULL COMMENT '退款金额',",
    "amountPayerTotal INT NULL COMMENT '用户支付金额',",
    "amountPayerRefund INT NULL COMMENT '用户退款金额',",
    "amountCurrency VARCHAR(16) NULL COMMENT '货币类型',",
    "amountPayerCurrency VARCHAR(16) NULL COMMENT '用户支付货币类型',",
    "completeYMDHMS VARCHAR(16) NULL COMMENT '支付/退款完成时间',",
    "createYMDHMS VARCHAR(16) COMMENT '创建时间',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "tradeNo")
        rtn = mysqlDB.executeWrite(sqlStr)
        sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "loginID")
        rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除weixin_pay表
def drop_weixin_pay(tableName):
    result = dropTableGeneral(tableName)
    return result


#weixin_pay 删除记录
def delete_weixin_pay(tableName,sortID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE sortID = %s"
        valuesList = [sortID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#weixin_pay 增加记录
def insert_weixin_pay(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["tradeNo"] = dataSet.get("tradeNo", "") 

        saveSet["parentTradeNo"] = dataSet.get("parentTradeNo", "") 

        saveSet["bizType"] = dataSet.get("bizType", "") 

        saveSet["productID"] = dataSet.get("productID", "") 

        saveSet["productName"] = dataSet.get("productName", "") 

        try:
            quantity = int(dataSet.get("quantity")) 
        except:
            quantity = 0 
        saveSet["quantity"] = quantity

        saveSet["loginID"] = dataSet.get("loginID", "") 

        saveSet["contactName"] = dataSet.get("contactName", "") 

        try:
            fee = int(dataSet.get("fee")) 
        except:
            fee = 0 
        saveSet["fee"] = fee

        saveSet["feeType"] = dataSet.get("feeType", "") 

        saveSet["status"] = dataSet.get("status", "") 

        saveSet["reason"] = dataSet.get("reason", "") 

        saveSet["appID"] = dataSet.get("appID", "") 

        saveSet["mchID"] = dataSet.get("mchID", "") 

        saveSet["transactionID"] = dataSet.get("transactionID", "") 

        saveSet["tradeType"] = dataSet.get("tradeType", "") 

        saveSet["tradeState"] = dataSet.get("tradeState", "") 

        saveSet["tradeStateDesc"] = dataSet.get("tradeStateDesc", "") 

        saveSet["bankType"] = dataSet.get("bankType", "") 

        saveSet["attach"] = dataSet.get("attach", "") 

        saveSet["successTime"] = dataSet.get("successTime", "") 

        saveSet["openID"] = dataSet.get("openID", "") 

        saveSet["deviceID"] = dataSet.get("deviceID", "") 

        saveSet["promotionCouponID"] = dataSet.get("promotionCouponID", "") 

        saveSet["promotionName"] = dataSet.get("promotionName", "") 

        saveSet["promotionScope"] = dataSet.get("promotionScope", "") 

        saveSet["promotionType"] = dataSet.get("promotionType", "") 

        try:
            promotionAmount = int(dataSet.get("promotionAmount")) 
        except:
            promotionAmount = 0 
        saveSet["promotionAmount"] = promotionAmount

        saveSet["promotionStockID"] = dataSet.get("promotionStockID", "") 

        try:
            promotionWechatContribute = int(dataSet.get("promotionWechatContribute")) 
        except:
            promotionWechatContribute = 0 
        saveSet["promotionWechatContribute"] = promotionWechatContribute

        try:
            promotionMerchantContribute = int(dataSet.get("promotionMerchantContribute")) 
        except:
            promotionMerchantContribute = 0 
        saveSet["promotionMerchantContribute"] = promotionMerchantContribute

        try:
            promotionOtherContribute = int(dataSet.get("promotionOtherContribute")) 
        except:
            promotionOtherContribute = 0 
        saveSet["promotionOtherContribute"] = promotionOtherContribute

        saveSet["promotionCurrency"] = dataSet.get("promotionCurrency", "") 

        saveSet["promotionGoodsDetail"] = dataSet.get("promotionGoodsDetail", "") 

        saveSet["refundFlag"] = dataSet.get("refundFlag", "") 

        saveSet["refundID"] = dataSet.get("refundID", "") 

        saveSet["refundStatus"] = dataSet.get("refundStatus", "") 

        saveSet["userReceivedAccount"] = dataSet.get("userReceivedAccount", "") 

        try:
            amountTotal = int(dataSet.get("amountTotal")) 
        except:
            amountTotal = 0 
        saveSet["amountTotal"] = amountTotal

        try:
            amountRefund = int(dataSet.get("amountRefund")) 
        except:
            amountRefund = 0 
        saveSet["amountRefund"] = amountRefund

        try:
            amountPayerTotal = int(dataSet.get("amountPayerTotal")) 
        except:
            amountPayerTotal = 0 
        saveSet["amountPayerTotal"] = amountPayerTotal

        try:
            amountPayerRefund = int(dataSet.get("amountPayerRefund")) 
        except:
            amountPayerRefund = 0 
        saveSet["amountPayerRefund"] = amountPayerRefund

        saveSet["amountCurrency"] = dataSet.get("amountCurrency", "") 

        saveSet["amountPayerCurrency"] = dataSet.get("amountPayerCurrency", "") 

        saveSet["completeYMDHMS"] = dataSet.get("completeYMDHMS", "") 

        saveSet["createYMDHMS"] = dataSet.get("createYMDHMS", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#weixin_pay 修改记录
def update_weixin_pay(tableName,sortID,dataSet):
    result = -2
    try:
        saveSet = {}

        tradeNo = dataSet.get("tradeNo") 
        if tradeNo:
            saveSet["tradeNo"] = tradeNo

        parentTradeNo = dataSet.get("parentTradeNo") 
        if parentTradeNo:
            saveSet["parentTradeNo"] = parentTradeNo

        bizType = dataSet.get("bizType") 
        if bizType:
            saveSet["bizType"] = bizType

        productID = dataSet.get("productID") 
        if productID:
            saveSet["productID"] = productID

        productName = dataSet.get("productName") 
        if productName:
            saveSet["productName"] = productName

        try:
            quantity = int(dataSet.get("quantity")) 
            saveSet["quantity"] = quantity
        except:
            pass

        loginID = dataSet.get("loginID") 
        if loginID:
            saveSet["loginID"] = loginID

        contactName = dataSet.get("contactName") 
        if contactName:
            saveSet["contactName"] = contactName

        try:
            fee = int(dataSet.get("fee")) 
            saveSet["fee"] = fee
        except:
            pass

        feeType = dataSet.get("feeType") 
        if feeType:
            saveSet["feeType"] = feeType

        status = dataSet.get("status") 
        if status:
            saveSet["status"] = status

        reason = dataSet.get("reason") 
        if reason:
            saveSet["reason"] = reason

        appID = dataSet.get("appID") 
        if appID:
            saveSet["appID"] = appID

        mchID = dataSet.get("mchID") 
        if mchID:
            saveSet["mchID"] = mchID

        transactionID = dataSet.get("transactionID") 
        if transactionID:
            saveSet["transactionID"] = transactionID

        tradeType = dataSet.get("tradeType") 
        if tradeType:
            saveSet["tradeType"] = tradeType

        tradeState = dataSet.get("tradeState") 
        if tradeState:
            saveSet["tradeState"] = tradeState

        tradeStateDesc = dataSet.get("tradeStateDesc") 
        if tradeStateDesc:
            saveSet["tradeStateDesc"] = tradeStateDesc

        bankType = dataSet.get("bankType") 
        if bankType:
            saveSet["bankType"] = bankType

        attach = dataSet.get("attach") 
        if attach:
            saveSet["attach"] = attach

        successTime = dataSet.get("successTime") 
        if successTime:
            saveSet["successTime"] = successTime

        openID = dataSet.get("openID") 
        if openID:
            saveSet["openID"] = openID

        deviceID = dataSet.get("deviceID") 
        if deviceID:
            saveSet["deviceID"] = deviceID

        promotionCouponID = dataSet.get("promotionCouponID") 
        if promotionCouponID:
            saveSet["promotionCouponID"] = promotionCouponID

        promotionName = dataSet.get("promotionName") 
        if promotionName:
            saveSet["promotionName"] = promotionName

        promotionScope = dataSet.get("promotionScope") 
        if promotionScope:
            saveSet["promotionScope"] = promotionScope

        promotionType = dataSet.get("promotionType") 
        if promotionType:
            saveSet["promotionType"] = promotionType

        try:
            promotionAmount = int(dataSet.get("promotionAmount")) 
            saveSet["promotionAmount"] = promotionAmount
        except:
            pass

        promotionStockID = dataSet.get("promotionStockID") 
        if promotionStockID:
            saveSet["promotionStockID"] = promotionStockID

        try:
            promotionWechatContribute = int(dataSet.get("promotionWechatContribute")) 
            saveSet["promotionWechatContribute"] = promotionWechatContribute
        except:
            pass

        try:
            promotionMerchantContribute = int(dataSet.get("promotionMerchantContribute")) 
            saveSet["promotionMerchantContribute"] = promotionMerchantContribute
        except:
            pass

        try:
            promotionOtherContribute = int(dataSet.get("promotionOtherContribute")) 
            saveSet["promotionOtherContribute"] = promotionOtherContribute
        except:
            pass

        promotionCurrency = dataSet.get("promotionCurrency") 
        if promotionCurrency:
            saveSet["promotionCurrency"] = promotionCurrency

        promotionGoodsDetail = dataSet.get("promotionGoodsDetail") 
        if promotionGoodsDetail:
            saveSet["promotionGoodsDetail"] = promotionGoodsDetail

        refundFlag = dataSet.get("refundFlag") 
        if refundFlag:
            saveSet["refundFlag"] = refundFlag

        refundID = dataSet.get("refundID") 
        if refundID:
            saveSet["refundID"] = refundID

        refundStatus = dataSet.get("refundStatus") 
        if refundStatus:
            saveSet["refundStatus"] = refundStatus

        userReceivedAccount = dataSet.get("userReceivedAccount") 
        if userReceivedAccount:
            saveSet["userReceivedAccount"] = userReceivedAccount

        try:
            amountTotal = int(dataSet.get("amountTotal")) 
            saveSet["amountTotal"] = amountTotal
        except:
            pass

        try:
            amountRefund = int(dataSet.get("amountRefund")) 
            saveSet["amountRefund"] = amountRefund
        except:
            pass

        try:
            amountPayerTotal = int(dataSet.get("amountPayerTotal")) 
            saveSet["amountPayerTotal"] = amountPayerTotal
        except:
            pass

        try:
            amountPayerRefund = int(dataSet.get("amountPayerRefund")) 
            saveSet["amountPayerRefund"] = amountPayerRefund
        except:
            pass

        amountCurrency = dataSet.get("amountCurrency") 
        if amountCurrency:
            saveSet["amountCurrency"] = amountCurrency

        amountPayerCurrency = dataSet.get("amountPayerCurrency") 
        if amountPayerCurrency:
            saveSet["amountPayerCurrency"] = amountPayerCurrency

        completeYMDHMS = dataSet.get("completeYMDHMS") 
        if completeYMDHMS:
            saveSet["completeYMDHMS"] = completeYMDHMS

        createYMDHMS = dataSet.get("createYMDHMS") 
        if createYMDHMS:
            saveSet["createYMDHMS"] = createYMDHMS

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "sortID = %s"
        keyValues = [sortID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#weixin_pay end

#===== auto-generated sections end =====


if __name__ == "__main__":
    pass
    # import pdb
    # pdb.set_trace()
    print ("_SYS", settings._SYS)
    print ("FILE_SYSTEM_MODE", settings.FILE_SYSTEM_MODE)
    print ("database_name", database_name)
    print ("mysqlDB", mysqlDB)
    print ("jsonColumns", MYSQL_JSON_COLUMN_NAME_LIST)
    print ("auditLogLimit", _DEF_CH_AUDIT_LOG_QUERY_LIMIT_NUM)
