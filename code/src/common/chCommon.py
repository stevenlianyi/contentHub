#! /usr/bin/env python3
#encoding: utf-8

#Filename: chCommon.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub(内容中枢) 跨域业务公共件(对齐基线 museumCommon, 但必须先被使用,
#严禁「建而不用」——见主计划 6.4 R-24 与 chAPIPost分拆方案.md 9.3 CI-C5)。
#
#本轮(SP1)只落数据库侧能力:
#  1) upsertByUniqueKey —— 按唯一键拼接列幂等写入(生成器不支持 ON DUPLICATE KEY / 复合唯一键)
#  2) fillFileUrls      —— 出参把 fileID 转成可访问 URL, 库内只存 fileID(主计划 3.3.8 约定)
#分页缓冲三函数(genBufferIndexKey/putQuery2Buffer/getQueryBufferComplte)与错误消息模块属接入层,
#按子计划切分归 SP1.5, 不在本文件实现。
#
#红线:
#  R1 只经 common/mysqlCommon.py 访问数据库, 本文件不写裸 SQL;
#  R2 文件访问只经 common/fileStorageCommon.py, 不做厂商分支判断。

_VERSION="20260918"

import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import traceback

#global defintion/common var etc.
from common import globalDefinition as comGD

#common functions(log,time,string, json etc)
from common import miscCommon as misc

from common import fileStorageCommon as comFS

from config import basicSettings as settings

HOME_DIR = settings._HOME_DIR

if "_LOG" not in dir() or not _LOG:
    try:
        logDir = os.path.join(settings._CODE_DIR, "log")
        _LOG = misc.setLogNew("CHCOMMON", comGD._DEF_GENRAL_MYSQL_LOG_NAME, logDir)
    except Exception:
        _LOG = None

_processorPID = os.getpid()

_DEBUG = settings._DEBUG


#fileID 字段 -> 出参 URL 字段的固定映射(库内只存 fileID, URL 由后端转换)
#说明: 不使用 replace("FileID","Url") 这类字符串推导, 因为 thumbnailID/coverThumbID 并不含 "FileID",
#      推导会漏转; 此处显式登记, 新增文件字段时同步追加。
FILE_FIELD_URL_MAP = {
    "fileID": "fileUrl",
    "thumbnailID": "thumbnailUrl",
    "coverFileID": "coverUrl",
    "coverThumbID": "coverThumbUrl",
    "descriptionFileID": "descriptionUrl",
    "derivedFileID": "derivedUrl",
    "derivedThumbID": "derivedThumbUrl",
    "previewFileID": "previewUrl",
}


def upsertByUniqueKey(tableName, uniqueValue, saveSet, queryFunc, insertFunc, updateFunc):
    """按唯一键幂等写入(生成器不支持 ON DUPLICATE KEY, 也不支持复合唯一键):
       命中 -> 更新(recID 不变, 返回既有 recID); 未命中 -> 插入(返回新 recID); 失败 -> 0

       入参:
         tableName  表名(由 comMysql.tablename_convertor_ch_*() 取得)
         uniqueValue 唯一键取值(如 topicCode / assetKey / contentHash / idempotencyKey)
         saveSet    待写入的数据字典
         queryFunc  查询函数, 约定签名 queryFunc(tableName, uniqueValue) -> list
                    (由调用方用 lambda 绑定具体检索列, 例如
                     lambda t, v: comMysql.query_ch_topic(t, topicCode = v))
         insertFunc 插入函数, 约定签名 insertFunc(tableName, saveSet) -> recID
         updateFunc 更新函数, 约定签名 updateFunc(tableName, recID, saveSet) -> 受影响行数
    """
    result = 0
    try:
        dataList = queryFunc(tableName, uniqueValue)

        if len(dataList) > 0:
            recID = 0
            try:
                recID = int(dataList[0].get("recID", 0))
            except Exception:
                recID = 0
            if recID > 0:
                updateFunc(tableName, recID, saveSet)
                result = recID
            else:
                #查到记录却取不到主键(理论上不会发生): 记日志并返回 0, 不做插入以免产生重复数据
                if _LOG:
                    _LOG.error(f"PID:{_processorPID}, upsertByUniqueKey: {tableName} 命中记录但 recID 非法, uniqueValue:{uniqueValue}")
        else:
            result = insertFunc(tableName, saveSet)

        if _DEBUG and _LOG:
            _LOG.info(f"PID:{_processorPID}, upsertByUniqueKey {tableName}, uniqueValue:{uniqueValue}, recID:{result}")

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, upsertByUniqueKey {tableName}, uniqueValue:{uniqueValue}, errMsg:{e},{traceMsg}")

    return result


def fillFileUrls(aSet, fileFields = None, privateFlag = True):
    """出参转换(主计划 3.3.8): 把记录里的 fileID 字段转成可访问 URL。
       入参 aSet 支持 dict(单条) 或 list(多条); 返回与入参同形态。
       多桶路由: 优先按记录里的 storageBucket 快照解析, 缺失时回落当前默认桶
                 (中途切换 FILE_SYSTEM_MODE 后, 历史文件仍可正确读取, 见主计划 6.4 R-16)。
       说明: fileStorageCommon 采用函数内延迟导入 —— 该模块会牵出云厂商 SDK,
             仅做数据库操作的调用方不应被动依赖这些 SDK。
    """
    if fileFields is None:
        fileFields = list(FILE_FIELD_URL_MAP.keys())

    if aSet is None:
        return aSet

    if isinstance(aSet, list):
        for data in aSet:
            _fillOneRecordFileUrls(data, fileFields, privateFlag)
        return aSet

    _fillOneRecordFileUrls(aSet, fileFields, privateFlag)
    return aSet


def _fillOneRecordFileUrls(aSet, fileFields, privateFlag = True):
    """单条记录的 fileID -> URL 转换(内部实现)"""
    if not isinstance(aSet, dict):
        return aSet

    storageBucket = aSet.get("storageBucket", "")
    for fieldName in fileFields:
        fileID = aSet.get(fieldName, "")
        if not fileID:
            continue
        urlField = FILE_FIELD_URL_MAP.get(fieldName, "")
        if not urlField:
            continue
        try:
            aSet[urlField] = comFS.getTempLocation(fileID, privateFlag = privateFlag,
                                                   storageBucket = storageBucket)
        except Exception as e:
            if _LOG:
                _LOG.error(f"PID:{_processorPID}, fillFileUrls {fieldName}:{fileID}, errMsg:{e}")
            aSet[urlField] = ""
    return aSet


if __name__ == "__main__":
    pass
    # import pdb
    # pdb.set_trace()
    print ("_SYS", settings._SYS)
    print ("FILE_SYSTEM_MODE", settings.FILE_SYSTEM_MODE)
    print ("fileFields", list(FILE_FIELD_URL_MAP.keys()))
    print ("sample", fillFileUrls({"fileID": "037/file4f2a9c8e", "storageBucket": "local"}))
