#! /usr/bin/env python3
#encoding: utf-8

#Filename: queryBufferCommon.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub(内容中枢) 查询缓冲(Redis buffer)公共件 —— D3 移植落点。
#
#背景(见 plan.md §8 D3 / plan/chAPIPost分拆方案.md 4.2):
#  genBufferIndexKey / putQuery2Buffer / getQueryBufferComplte 三个函数在基线里「位置错位」——
#  它们既不在 common/redisCommon.py, 也不在 common/museumCommon.py 被使用, 而是写死在
#  main/museumAPIPost.py 中(生成器产出的 funcXxxQry 直接按模块级名字调用)。SP1.5 的接入层
#  (subfunc/crudApi.py 的 48 个查询处理器)依赖它们, 故统一移植到本文件。
#
#落点说明:
#  - 不放进 common/chCommon.py: 该文件头已声明「分页缓冲三函数属接入层, 不在本文件实现」;
#  - 不修改 common/redisCommon.py 的既有逻辑: 本文件只调用其既有缓冲函数;
#  - 不新增 Redis key 结构, 与基线保持一致(_DEF_REDIS_BUFFER_LEVEL1/_DEF_BUFFER_DATA_NAME)。
#
#红线: 只经 common/redisCommon.py 访问 Redis, 本文件不直连(与 R1「数据库只经 mysqlCommon」同理)。

_VERSION="20260918"


import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import uuid

from common import globalDefinition as comGD

from common import funcCommon as comFC

from common import redisCommon as comDB


_processorPID = os.getpid()

#是否启用查询缓冲区(与基线 museum 的开关含义一致)。
#注意: 生成器产出的 funcXxxQry 以「模块级名字」读取该开关, subfunc/crudApi.py 会把它导入到
#      自身命名空间, 因此这里是进程级常量 —— 如某环境需要开启, 改本常量并随发布生效即可。
useQueryBufferFlag = False


def genBufferIndexKey(CMD, sessionID, indexKeyDataSet):
    """生成查询缓冲的 indexKey(基线逻辑原样移植):
       有检索条件时按「条件名升序 + 取值」拼接后取摘要, 无检索条件时退化为 CMD + sessionID;
       统一加 "<CMD>_" 前缀, 便于运维按命令字排查 Redis 缓冲。
       入参 indexKeyDataSet 支持 dict / 空值。"""
    if indexKeyDataSet:
        aList = []
        keys = list(indexKeyDataSet.keys())
        keys.sort()
        for k in keys:
            v = indexKeyDataSet[k]
            aList.append(str(k))
            aList.append(str(v))
        strT = "".join(aList)
        indexKey = comFC.genDigest(CMD, strT)
    else:
        indexKey = comFC.genDigest(CMD, sessionID)

    indexKey = CMD + "_" + indexKey #方便未来区分

    return indexKey


def genBufferToken(prefix = "qry"):
    """生成一次查询专用的缓冲隔离 token(供手写查询处理器使用)。
       用途: 同一 sessionID 下多个不同查询若共用 indexKey 会相互覆盖 Redis 缓冲,
             客户端为每次查询带上唯一 bufferToken 后, 各查询缓冲相互隔离。"""
    result = prefix + "-" + str(_processorPID) + "-" + uuid.uuid4().hex

    return result


def putQuery2Buffer(indexKey, dataList, overwriteFlag = True):
    """把一批数据写入指定缓冲区, 返回 indexKey。
       overwriteFlag=False 时仅在缓冲不存在时写入(避免并发覆盖已有缓冲)。"""
    if overwriteFlag:
        rtn = comDB.putAllDataBuffer(indexKey, dataList)
    else:
        if not comDB.chkBufferExist(indexKey):
            rtn = comDB.putAllDataBuffer(indexKey, dataList)

    result = indexKey

    return result


def chkBufferExist(indexKey):
    """判断缓冲区是否存在"""
    return comDB.chkBufferExist(indexKey)


def getBufferDataLen(indexKey):
    """取缓冲区数据条数"""
    return comDB.getBufferDataLen(indexKey)


def getQueryBuffer(indexKey, beginNum = 0, endNum = -1):
    """取缓冲数据, 出参 (bufferTotal, dataList)"""
    bufferTotal = comDB.getBufferDataLen(indexKey)
    dataList = comDB.getDataBuffer(indexKey, beginNum, endNum)

    return bufferTotal, dataList


def getQueryBufferComplte(indexKey, beginNum = 0, endNum = -1):
    """取缓冲数据(带完整分页信息), 基线逻辑原样移植。
       出参: {"indexKey", "total", "beginNum", "endNum", "data"}
       说明: endNum 按 java/c 规则收敛到 bufferTotal-1(与基线一致), 数据不存在时 data 为 []。"""
    result = {}

    bufferTotal = comDB.getBufferDataLen(indexKey)
    dataList = comDB.getDataBuffer(indexKey, beginNum, endNum)

    result["indexKey"] = indexKey

    result["total"] = bufferTotal
    result["beginNum"] = str(beginNum)

    if endNum >= bufferTotal:
        endNum = bufferTotal - 1 #java/c rule, not python rule
    if beginNum > endNum:
        beginNum = 0
    result["endNum"] = str(endNum)

    if bufferTotal > 0:
        result["data"] = dataList
    else:
        result["data"] = []

    return result


def chkNeedFlashQuery(indexKey, forceFlashFlag = comGD._CONST_NO):
    """判断是否需要重新查询(缓冲不存在 / 未启用缓冲 / 强制刷新)"""
    result = (not(useQueryBufferFlag and chkBufferExist(indexKey))) or (forceFlashFlag == comGD._CONST_YES)

    return result


if __name__ == "__main__":
    pass
    print("useQueryBufferFlag", useQueryBufferFlag)
    print("sample indexKey", genBufferIndexKey("topicqry", "session", {"mode": "full"}))
    print("sample token", genBufferToken())
