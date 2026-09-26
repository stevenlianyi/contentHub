#! /usr/bin/env python3
#encoding: utf-8

#Filename: crudApi.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub 12 张业务表的 REST 接入层(生成件落点)。
#
#★★★ 生 成 区 禁 止 手 改 ★★★
#  `#===== auto-generated crud sections begin/end` 之间由 tools/mergeCrudApi.py 从
#  database/auto_generated/auto_gen_code_ch_*.py 的 `#http interface code begin/end` 段装配而来
#  (12 表 × 4 操作 = 48 个处理器 + CMD_MAP 注册表)。
#  改表流程: ① 改 database/ch_*.txt -> ② 重跑生成器(tools/genTableCode.ps1)
#           -> ③ python tools/mergeCrudApi.py  (本文件生成区被覆盖, 手写头部不受影响)
#  手写逻辑一律进 subfunc/{domain}Api.py, 不要写在本文件, 否则重跑生成器会丢失(方案 R6)。
#
#本文件规模说明: 生成区约 5000 行, 属于「生成件装配」, 故在 test/test_ch_phase0_static.py 的
#  S2 结构校验中对该文件豁免单文件行数上限(其余 subfunc 文件 ≤1500 行, chAPIPost.py ≤1000 行)。
#
#下方手写头部的作用: 为生成件提供其运行时依赖的模块级符号(缺任一都会 NameError):
#  comGD / misc / comFC / comMysql / _LOG / _DEBUG / _processorPID
#  genBufferIndexKey / chkBufferExist / putQuery2Buffer / getQueryBufferComplte / useQueryBufferFlag

_VERSION="20260918"


import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

from common import globalDefinition as comGD

from common import miscCommon as misc

from common import funcCommon as comFC

from common import mysqlCommon as comMysql

from common.queryBufferCommon import (genBufferIndexKey, chkBufferExist,
                                      putQuery2Buffer, getQueryBufferComplte,
                                      useQueryBufferFlag)

from subfunc import context as ctx


_LOG = ctx._LOG
_DEBUG = ctx._DEBUG
_processorPID = ctx._processorPID

#生成件标记(供诊断: True = 本文件的生成区由 tools/mergeCrudApi.py 装配, 禁止手改)
CRUD_GENERATED = True


#===== auto-generated crud sections begin (由 tools/mergeCrudApi.py 生成, 请勿手改) =====

#layout(ch_layout) CRUD begin



#Server REST增加代码
def funcLayoutAdd(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:
        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID
            #权限检查

            if errCode == "B0": #
                #data validation check
                dataValidFlag = True
                if dataValidFlag:
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
                    saveSet["sortWeight"] = dataSet.get("sortWeight", "") 
                    saveSet["label"] = dataSet.get("label", "") 
                    saveSet["memo"] = dataSet.get("memo", "") 
                    saveSet["delFlag"] = dataSet.get("delFlag", "0") 
                    saveSet["regID"] = loginID
                    saveSet["regYMDHMS"] = misc.getTime()

                    tableName = comMysql.tablename_convertor_ch_layout()
                    recID = comMysql.insert_ch_layout(tableName,saveSet)
                    rtnData["recID"] = str(recID)

                    if recID <= 0:
                        #记录添加失败
                        errCode = "CG"
                        _LOG.warning(f"rtn:{recID},saveSet:{saveSet}")
                    else:
                        if _DEBUG:
                            pass
                            _LOG.info(f"D: recID:{recID}")

                    result = rtnData

                else:
                    #data invalid
                    errCode = "BA"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST删除代码
def funcLayoutDel(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID
            #权限检查

            if errCode == "B0": #
                recID = dataSet.get("recID", "")
                tableName = comMysql.tablename_convertor_ch_layout()
                currDataList = comMysql.query_ch_layout(tableName,recID)
                if len(currDataList) == 1:
                    saveSet = {}
                    saveSet["modifyID"] = loginID
                    saveSet["modifyYMDHMS"] = misc.getTime()
                    #saveSet["delFlag"] = "1"

                    rtn = comMysql.delete_ch_layout(tableName,recID)
                    rtnData["rtn"] = str(rtn)

                    if _DEBUG:
                        _LOG.info(f"D: rtn:{rtn}")

                    result = rtnData

                else:
                    errCode = "CB"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST修改代码
def funcLayoutModify(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID

            #权限检查/功能检测

            if errCode == "B0": #
                #data validation check
                dataValidFlag = True

                layoutCode = dataSet.get("layoutCode") 
                layoutName = dataSet.get("layoutName") 
                layoutType = dataSet.get("layoutType") 
                platform = dataSet.get("platform") 
                engine = dataSet.get("engine") 
                templatePath = dataSet.get("templatePath") 
                templateVer = dataSet.get("templateVer") 
                outputKind = dataSet.get("outputKind") 
                specJson = dataSet.get("specJson") 
                previewFileID = dataSet.get("previewFileID") 
                builtinFlag = dataSet.get("builtinFlag") 
                enabled = dataSet.get("enabled") 
                sortWeight = dataSet.get("sortWeight") 
                label = dataSet.get("label") 
                memo = dataSet.get("memo") 
                delFlag = dataSet.get("delFlag") 
                #data valid 检查

                if dataValidFlag:
                    #当前记录获取
                    recID = dataSet.get("recID", "")

                    tableName = comMysql.tablename_convertor_ch_layout()
                    currDataList = comMysql.query_ch_layout(tableName,recID)

                    if len(currDataList) == 1:
                        currDataSet = currDataList[0]

                        #权限或其他检查
                        if errCode == "B0": #

                            saveSet = {}

                            if layoutCode != currDataSet.get("layoutCode") and layoutCode:
                                saveSet["layoutCode"] = layoutCode

                            if layoutName != currDataSet.get("layoutName") and layoutName:
                                saveSet["layoutName"] = layoutName

                            if layoutType != currDataSet.get("layoutType") and layoutType:
                                saveSet["layoutType"] = layoutType

                            if platform != currDataSet.get("platform") and platform:
                                saveSet["platform"] = platform

                            if engine != currDataSet.get("engine") and engine:
                                saveSet["engine"] = engine

                            if templatePath != currDataSet.get("templatePath") and templatePath:
                                saveSet["templatePath"] = templatePath

                            if templateVer != currDataSet.get("templateVer") and templateVer:
                                saveSet["templateVer"] = templateVer

                            if outputKind != currDataSet.get("outputKind") and outputKind:
                                saveSet["outputKind"] = outputKind

                            if specJson != currDataSet.get("specJson") and specJson:
                                saveSet["specJson"] = specJson

                            if previewFileID != currDataSet.get("previewFileID") and previewFileID:
                                saveSet["previewFileID"] = previewFileID

                            if builtinFlag != currDataSet.get("builtinFlag") and builtinFlag:
                                saveSet["builtinFlag"] = builtinFlag

                            if enabled != currDataSet.get("enabled") and enabled:
                                saveSet["enabled"] = enabled

                            if sortWeight != currDataSet.get("sortWeight") and sortWeight != None:
                                saveSet["sortWeight"] = sortWeight

                            if label != currDataSet.get("label") and label:
                                saveSet["label"] = label

                            if memo != currDataSet.get("memo") and memo:
                                saveSet["memo"] = memo

                            if delFlag != currDataSet.get("delFlag") and delFlag:
                                saveSet["delFlag"] = delFlag

                            if saveSet:
                                #saveSet["delFlag"] = "0"
                                saveSet["modifyID"] = loginID
                                saveSet["modifyYMDHMS"] = misc.getTime()

                                #保存数据
                                tableName = comMysql.tablename_convertor_ch_layout()
                                rtn = comMysql.update_ch_layout(tableName,recID,saveSet)
                                rtnData["rtn"] = str(rtn)

                                if rtn < 0:
                                    _LOG.warning(f"D: rtn:{rtn},saveSet:{saveSet}")
                                else:
                                    if _DEBUG:
                                        pass
                                        _LOG.info(f"D: rtn:{rtn}")

                                result = rtnData

                        else:
                            #BT
                            errCode = "BT"

                    else:
                        #CB
                        errCode = "CB"

                else:
                    #data invalid
                    errCode = "BA"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST查询代码
def funcLayoutQry(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID

            #权限检查

            if errCode == "B0": #
                #获取查询输入参数
                recID = dataSet.get("recID", "")

                #houseID = dataSet.get("houseID", "")

                forceFlashFlag = dataSet.get("forceFlashFlag",comGD._CONST_NO) #是否强制查询(刷新)标记

                searchOption = dataSet.get("searchOption")

                mode = dataSet.get("mode", "full")

                #limitNum = dataSet.get("limitNum",0)

                #权限检查/功能检测

                rightCheckFlag = True

                if rightCheckFlag:

                    #生成indexKey
                    indexKeyDataSet = {} #查询生成index的因素
                    if recID:
                        indexKeyDataSet["recID"] = recID
                    if searchOption:
                        indexKeyDataSet["searchOption"] = searchOption
                    if mode:
                        indexKeyDataSet["mode"] = mode

                    #if limitNum:
                        #indexKeyDataSet["limitNum"] = limitNum

                    sessionID = sessionIDSet.get("sessionID", "")
                    indexKey = genBufferIndexKey(CMD, sessionID, indexKeyDataSet) 
                    beginNum = int(dataSet.get("beginNum", comGD._DEF_BUFFER_DATA_BEGIN_NUM)) 
                    endNum = int(dataSet.get("endNum", comGD._DEF_BUFFER_DATA_END_NUM)) 

                    #判断数据是否在缓冲区:
                    if not(useQueryBufferFlag and chkBufferExist(indexKey)) or forceFlashFlag == comGD._CONST_YES:

                        if searchOption:
                            currDataList = []
                            tableName = comMysql.tablename_convertor_ch_layout()
                            allDataList = comMysql.query_ch_layout(tableName,mode = mode)
                            allowList = ["description", "label"] #筛选字段
                            serachResultSet = comFC.handleSearchOption(searchOption,allowList, allDataList)
                            if serachResultSet["rtn"] == "B0":
                                currDataList = serachResultSet.get("data", [])
                        else:
                            if recID:
                                tableName = comMysql.tablename_convertor_ch_layout()
                                currDataList = comMysql.query_ch_layout(tableName,recID,mode = mode)
                            else:
                                tableName = comMysql.tablename_convertor_ch_layout()
                                currDataList = comMysql.query_ch_layout(tableName)

                        dataList = []

                        for currDataSet in currDataList:
                            aSet = {}

                            #需要把文件转移到public domain
                            #appendixFileID00 =  currDataSet.get("appendixFileID00", "")
                            #appendixFileID00 = getTempLocation(appendixFileID00, privateFlag = True)

                            #if mode == "full":
                                #aSet["houseID"] = currDataSet.get("houseID", "")

                            aSet["recID"] = currDataSet.get("recID","")
                            aSet["layoutCode"] = currDataSet.get("layoutCode","")
                            aSet["layoutName"] = currDataSet.get("layoutName","")
                            aSet["layoutType"] = currDataSet.get("layoutType","")
                            aSet["platform"] = currDataSet.get("platform","")
                            aSet["engine"] = currDataSet.get("engine","")
                            aSet["templatePath"] = currDataSet.get("templatePath","")
                            aSet["templateVer"] = currDataSet.get("templateVer","")
                            aSet["outputKind"] = currDataSet.get("outputKind","")
                            aSet["specJson"] = currDataSet.get("specJson","")
                            aSet["previewFileID"] = currDataSet.get("previewFileID","")
                            aSet["builtinFlag"] = currDataSet.get("builtinFlag","")
                            aSet["enabled"] = currDataSet.get("enabled","")
                            aSet["sortWeight"] = currDataSet.get("sortWeight","")
                            aSet["label"] = currDataSet.get("label","")
                            aSet["memo"] = currDataSet.get("memo","")
                            aSet["regID"] = currDataSet.get("regID","")
                            aSet["regYMDHMS"] = currDataSet.get("regYMDHMS","")
                            aSet["modifyID"] = currDataSet.get("modifyID","")
                            aSet["modifyYMDHMS"] = currDataSet.get("modifyYMDHMS","")
                            aSet["delFlag"] = currDataSet.get("delFlag","")

                            dataList.append(aSet)

                        #临时缓存机制,改进型, 2023/10/16
                        indexKey = putQuery2Buffer(indexKey, dataList) #存放数据到临时缓冲区去

                    rtnData = getQueryBufferComplte(indexKey, beginNum = beginNum,  endNum = endNum)

                    #rtnData["limitNum"] = limitNum

                    result = rtnData

                else:
                    errCode = "BT"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result




#layout(ch_layout) CRUD end


#platform(ch_platform) CRUD begin



#Server REST增加代码
def funcPlatformAdd(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:
        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID
            #权限检查

            if errCode == "B0": #
                #data validation check
                dataValidFlag = True
                if dataValidFlag:
                    saveSet = {}
                    saveSet["platformCode"] = dataSet.get("platformCode", "") 
                    saveSet["platformName"] = dataSet.get("platformName", "") 
                    saveSet["subjectScope"] = dataSet.get("subjectScope", "") 
                    saveSet["deliverMode"] = dataSet.get("deliverMode", "") 
                    saveSet["titleMaxLen"] = dataSet.get("titleMaxLen", "") 
                    saveSet["summaryMaxLen"] = dataSet.get("summaryMaxLen", "") 
                    saveSet["coverSpec"] = dataSet.get("coverSpec", "") 
                    saveSet["imageSpec"] = dataSet.get("imageSpec", "") 
                    saveSet["imageMaxCount"] = dataSet.get("imageMaxCount", "") 
                    saveSet["allowSvgFlag"] = dataSet.get("allowSvgFlag", "") 
                    saveSet["needAiLabelFlag"] = dataSet.get("needAiLabelFlag", "") 
                    saveSet["autoPublishFlag"] = dataSet.get("autoPublishFlag", "") 
                    saveSet["limitNote"] = dataSet.get("limitNote", "") 
                    saveSet["docUrl"] = dataSet.get("docUrl", "") 
                    saveSet["enabled"] = dataSet.get("enabled", "") 
                    saveSet["label"] = dataSet.get("label", "") 
                    saveSet["memo"] = dataSet.get("memo", "") 
                    saveSet["delFlag"] = dataSet.get("delFlag", "0") 
                    saveSet["regID"] = loginID
                    saveSet["regYMDHMS"] = misc.getTime()

                    tableName = comMysql.tablename_convertor_ch_platform()
                    recID = comMysql.insert_ch_platform(tableName,saveSet)
                    rtnData["recID"] = str(recID)

                    if recID <= 0:
                        #记录添加失败
                        errCode = "CG"
                        _LOG.warning(f"rtn:{recID},saveSet:{saveSet}")
                    else:
                        if _DEBUG:
                            pass
                            _LOG.info(f"D: recID:{recID}")

                    result = rtnData

                else:
                    #data invalid
                    errCode = "BA"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST删除代码
def funcPlatformDel(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID
            #权限检查

            if errCode == "B0": #
                recID = dataSet.get("recID", "")
                tableName = comMysql.tablename_convertor_ch_platform()
                currDataList = comMysql.query_ch_platform(tableName,recID)
                if len(currDataList) == 1:
                    saveSet = {}
                    saveSet["modifyID"] = loginID
                    saveSet["modifyYMDHMS"] = misc.getTime()
                    #saveSet["delFlag"] = "1"

                    rtn = comMysql.delete_ch_platform(tableName,recID)
                    rtnData["rtn"] = str(rtn)

                    if _DEBUG:
                        _LOG.info(f"D: rtn:{rtn}")

                    result = rtnData

                else:
                    errCode = "CB"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST修改代码
def funcPlatformModify(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID

            #权限检查/功能检测

            if errCode == "B0": #
                #data validation check
                dataValidFlag = True

                platformCode = dataSet.get("platformCode") 
                platformName = dataSet.get("platformName") 
                subjectScope = dataSet.get("subjectScope") 
                deliverMode = dataSet.get("deliverMode") 
                titleMaxLen = dataSet.get("titleMaxLen") 
                summaryMaxLen = dataSet.get("summaryMaxLen") 
                coverSpec = dataSet.get("coverSpec") 
                imageSpec = dataSet.get("imageSpec") 
                imageMaxCount = dataSet.get("imageMaxCount") 
                allowSvgFlag = dataSet.get("allowSvgFlag") 
                needAiLabelFlag = dataSet.get("needAiLabelFlag") 
                autoPublishFlag = dataSet.get("autoPublishFlag") 
                limitNote = dataSet.get("limitNote") 
                docUrl = dataSet.get("docUrl") 
                enabled = dataSet.get("enabled") 
                label = dataSet.get("label") 
                memo = dataSet.get("memo") 
                delFlag = dataSet.get("delFlag") 
                #data valid 检查

                if dataValidFlag:
                    #当前记录获取
                    recID = dataSet.get("recID", "")

                    tableName = comMysql.tablename_convertor_ch_platform()
                    currDataList = comMysql.query_ch_platform(tableName,recID)

                    if len(currDataList) == 1:
                        currDataSet = currDataList[0]

                        #权限或其他检查
                        if errCode == "B0": #

                            saveSet = {}

                            if platformCode != currDataSet.get("platformCode") and platformCode:
                                saveSet["platformCode"] = platformCode

                            if platformName != currDataSet.get("platformName") and platformName:
                                saveSet["platformName"] = platformName

                            if subjectScope != currDataSet.get("subjectScope") and subjectScope:
                                saveSet["subjectScope"] = subjectScope

                            if deliverMode != currDataSet.get("deliverMode") and deliverMode:
                                saveSet["deliverMode"] = deliverMode

                            if titleMaxLen != currDataSet.get("titleMaxLen") and titleMaxLen != None:
                                saveSet["titleMaxLen"] = titleMaxLen

                            if summaryMaxLen != currDataSet.get("summaryMaxLen") and summaryMaxLen != None:
                                saveSet["summaryMaxLen"] = summaryMaxLen

                            if coverSpec != currDataSet.get("coverSpec") and coverSpec:
                                saveSet["coverSpec"] = coverSpec

                            if imageSpec != currDataSet.get("imageSpec") and imageSpec:
                                saveSet["imageSpec"] = imageSpec

                            if imageMaxCount != currDataSet.get("imageMaxCount") and imageMaxCount != None:
                                saveSet["imageMaxCount"] = imageMaxCount

                            if allowSvgFlag != currDataSet.get("allowSvgFlag") and allowSvgFlag:
                                saveSet["allowSvgFlag"] = allowSvgFlag

                            if needAiLabelFlag != currDataSet.get("needAiLabelFlag") and needAiLabelFlag:
                                saveSet["needAiLabelFlag"] = needAiLabelFlag

                            if autoPublishFlag != currDataSet.get("autoPublishFlag") and autoPublishFlag:
                                saveSet["autoPublishFlag"] = autoPublishFlag

                            if limitNote != currDataSet.get("limitNote") and limitNote:
                                saveSet["limitNote"] = limitNote

                            if docUrl != currDataSet.get("docUrl") and docUrl:
                                saveSet["docUrl"] = docUrl

                            if enabled != currDataSet.get("enabled") and enabled:
                                saveSet["enabled"] = enabled

                            if label != currDataSet.get("label") and label:
                                saveSet["label"] = label

                            if memo != currDataSet.get("memo") and memo:
                                saveSet["memo"] = memo

                            if delFlag != currDataSet.get("delFlag") and delFlag:
                                saveSet["delFlag"] = delFlag

                            if saveSet:
                                #saveSet["delFlag"] = "0"
                                saveSet["modifyID"] = loginID
                                saveSet["modifyYMDHMS"] = misc.getTime()

                                #保存数据
                                tableName = comMysql.tablename_convertor_ch_platform()
                                rtn = comMysql.update_ch_platform(tableName,recID,saveSet)
                                rtnData["rtn"] = str(rtn)

                                if rtn < 0:
                                    _LOG.warning(f"D: rtn:{rtn},saveSet:{saveSet}")
                                else:
                                    if _DEBUG:
                                        pass
                                        _LOG.info(f"D: rtn:{rtn}")

                                result = rtnData

                        else:
                            #BT
                            errCode = "BT"

                    else:
                        #CB
                        errCode = "CB"

                else:
                    #data invalid
                    errCode = "BA"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST查询代码
def funcPlatformQry(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID

            #权限检查

            if errCode == "B0": #
                #获取查询输入参数
                recID = dataSet.get("recID", "")

                #houseID = dataSet.get("houseID", "")

                forceFlashFlag = dataSet.get("forceFlashFlag",comGD._CONST_NO) #是否强制查询(刷新)标记

                searchOption = dataSet.get("searchOption")

                mode = dataSet.get("mode", "full")

                #limitNum = dataSet.get("limitNum",0)

                #权限检查/功能检测

                rightCheckFlag = True

                if rightCheckFlag:

                    #生成indexKey
                    indexKeyDataSet = {} #查询生成index的因素
                    if recID:
                        indexKeyDataSet["recID"] = recID
                    if searchOption:
                        indexKeyDataSet["searchOption"] = searchOption
                    if mode:
                        indexKeyDataSet["mode"] = mode

                    #if limitNum:
                        #indexKeyDataSet["limitNum"] = limitNum

                    sessionID = sessionIDSet.get("sessionID", "")
                    indexKey = genBufferIndexKey(CMD, sessionID, indexKeyDataSet) 
                    beginNum = int(dataSet.get("beginNum", comGD._DEF_BUFFER_DATA_BEGIN_NUM)) 
                    endNum = int(dataSet.get("endNum", comGD._DEF_BUFFER_DATA_END_NUM)) 

                    #判断数据是否在缓冲区:
                    if not(useQueryBufferFlag and chkBufferExist(indexKey)) or forceFlashFlag == comGD._CONST_YES:

                        if searchOption:
                            currDataList = []
                            tableName = comMysql.tablename_convertor_ch_platform()
                            allDataList = comMysql.query_ch_platform(tableName,mode = mode)
                            allowList = ["description", "label"] #筛选字段
                            serachResultSet = comFC.handleSearchOption(searchOption,allowList, allDataList)
                            if serachResultSet["rtn"] == "B0":
                                currDataList = serachResultSet.get("data", [])
                        else:
                            if recID:
                                tableName = comMysql.tablename_convertor_ch_platform()
                                currDataList = comMysql.query_ch_platform(tableName,recID,mode = mode)
                            else:
                                tableName = comMysql.tablename_convertor_ch_platform()
                                currDataList = comMysql.query_ch_platform(tableName)

                        dataList = []

                        for currDataSet in currDataList:
                            aSet = {}

                            #需要把文件转移到public domain
                            #appendixFileID00 =  currDataSet.get("appendixFileID00", "")
                            #appendixFileID00 = getTempLocation(appendixFileID00, privateFlag = True)

                            #if mode == "full":
                                #aSet["houseID"] = currDataSet.get("houseID", "")

                            aSet["recID"] = currDataSet.get("recID","")
                            aSet["platformCode"] = currDataSet.get("platformCode","")
                            aSet["platformName"] = currDataSet.get("platformName","")
                            aSet["subjectScope"] = currDataSet.get("subjectScope","")
                            aSet["deliverMode"] = currDataSet.get("deliverMode","")
                            aSet["titleMaxLen"] = currDataSet.get("titleMaxLen","")
                            aSet["summaryMaxLen"] = currDataSet.get("summaryMaxLen","")
                            aSet["coverSpec"] = currDataSet.get("coverSpec","")
                            aSet["imageSpec"] = currDataSet.get("imageSpec","")
                            aSet["imageMaxCount"] = currDataSet.get("imageMaxCount","")
                            aSet["allowSvgFlag"] = currDataSet.get("allowSvgFlag","")
                            aSet["needAiLabelFlag"] = currDataSet.get("needAiLabelFlag","")
                            aSet["autoPublishFlag"] = currDataSet.get("autoPublishFlag","")
                            aSet["limitNote"] = currDataSet.get("limitNote","")
                            aSet["docUrl"] = currDataSet.get("docUrl","")
                            aSet["enabled"] = currDataSet.get("enabled","")
                            aSet["label"] = currDataSet.get("label","")
                            aSet["memo"] = currDataSet.get("memo","")
                            aSet["regID"] = currDataSet.get("regID","")
                            aSet["regYMDHMS"] = currDataSet.get("regYMDHMS","")
                            aSet["modifyID"] = currDataSet.get("modifyID","")
                            aSet["modifyYMDHMS"] = currDataSet.get("modifyYMDHMS","")
                            aSet["delFlag"] = currDataSet.get("delFlag","")

                            dataList.append(aSet)

                        #临时缓存机制,改进型, 2023/10/16
                        indexKey = putQuery2Buffer(indexKey, dataList) #存放数据到临时缓冲区去

                    rtnData = getQueryBufferComplte(indexKey, beginNum = beginNum,  endNum = endNum)

                    #rtnData["limitNum"] = limitNum

                    result = rtnData

                else:
                    errCode = "BT"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result




#platform(ch_platform) CRUD end


#renderjob(ch_render_job) CRUD begin



#Server REST增加代码
def funcRenderjobAdd(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:
        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID
            #权限检查

            if errCode == "B0": #
                #data validation check
                dataValidFlag = True
                if dataValidFlag:
                    saveSet = {}
                    saveSet["jobCode"] = dataSet.get("jobCode", "") 
                    saveSet["topicID"] = dataSet.get("topicID", "") 
                    saveSet["layoutCode"] = dataSet.get("layoutCode", "") 
                    saveSet["platform"] = dataSet.get("platform", "") 
                    saveSet["jobStatus"] = dataSet.get("jobStatus", "") 
                    saveSet["inputHash"] = dataSet.get("inputHash", "") 
                    saveSet["progress"] = dataSet.get("progress", "") 
                    saveSet["errMsg"] = dataSet.get("errMsg", "") 
                    saveSet["startYMDHMS"] = dataSet.get("startYMDHMS", "") 
                    saveSet["finishYMDHMS"] = dataSet.get("finishYMDHMS", "") 
                    saveSet["costMs"] = dataSet.get("costMs", "") 
                    saveSet["ownerID"] = dataSet.get("ownerID", "") 
                    saveSet["label"] = dataSet.get("label", "") 
                    saveSet["memo"] = dataSet.get("memo", "") 
                    saveSet["delFlag"] = dataSet.get("delFlag", "0") 
                    saveSet["regID"] = loginID
                    saveSet["regYMDHMS"] = misc.getTime()

                    tableName = comMysql.tablename_convertor_ch_render_job()
                    recID = comMysql.insert_ch_render_job(tableName,saveSet)
                    rtnData["recID"] = str(recID)

                    if recID <= 0:
                        #记录添加失败
                        errCode = "CG"
                        _LOG.warning(f"rtn:{recID},saveSet:{saveSet}")
                    else:
                        if _DEBUG:
                            pass
                            _LOG.info(f"D: recID:{recID}")

                    result = rtnData

                else:
                    #data invalid
                    errCode = "BA"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST删除代码
def funcRenderjobDel(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID
            #权限检查

            if errCode == "B0": #
                recID = dataSet.get("recID", "")
                tableName = comMysql.tablename_convertor_ch_render_job()
                currDataList = comMysql.query_ch_render_job(tableName,recID)
                if len(currDataList) == 1:
                    saveSet = {}
                    saveSet["modifyID"] = loginID
                    saveSet["modifyYMDHMS"] = misc.getTime()
                    #saveSet["delFlag"] = "1"

                    rtn = comMysql.delete_ch_render_job(tableName,recID)
                    rtnData["rtn"] = str(rtn)

                    if _DEBUG:
                        _LOG.info(f"D: rtn:{rtn}")

                    result = rtnData

                else:
                    errCode = "CB"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST修改代码
def funcRenderjobModify(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID

            #权限检查/功能检测

            if errCode == "B0": #
                #data validation check
                dataValidFlag = True

                jobCode = dataSet.get("jobCode") 
                topicID = dataSet.get("topicID") 
                layoutCode = dataSet.get("layoutCode") 
                platform = dataSet.get("platform") 
                jobStatus = dataSet.get("jobStatus") 
                inputHash = dataSet.get("inputHash") 
                progress = dataSet.get("progress") 
                errMsg = dataSet.get("errMsg") 
                startYMDHMS = dataSet.get("startYMDHMS") 
                finishYMDHMS = dataSet.get("finishYMDHMS") 
                costMs = dataSet.get("costMs") 
                ownerID = dataSet.get("ownerID") 
                label = dataSet.get("label") 
                memo = dataSet.get("memo") 
                delFlag = dataSet.get("delFlag") 
                #data valid 检查

                if dataValidFlag:
                    #当前记录获取
                    recID = dataSet.get("recID", "")

                    tableName = comMysql.tablename_convertor_ch_render_job()
                    currDataList = comMysql.query_ch_render_job(tableName,recID)

                    if len(currDataList) == 1:
                        currDataSet = currDataList[0]

                        #权限或其他检查
                        if errCode == "B0": #

                            saveSet = {}

                            if jobCode != currDataSet.get("jobCode") and jobCode:
                                saveSet["jobCode"] = jobCode

                            if topicID != currDataSet.get("topicID") and topicID != None:
                                saveSet["topicID"] = topicID

                            if layoutCode != currDataSet.get("layoutCode") and layoutCode:
                                saveSet["layoutCode"] = layoutCode

                            if platform != currDataSet.get("platform") and platform:
                                saveSet["platform"] = platform

                            if jobStatus != currDataSet.get("jobStatus") and jobStatus:
                                saveSet["jobStatus"] = jobStatus

                            if inputHash != currDataSet.get("inputHash") and inputHash:
                                saveSet["inputHash"] = inputHash

                            if progress != currDataSet.get("progress") and progress != None:
                                saveSet["progress"] = progress

                            if errMsg != currDataSet.get("errMsg") and errMsg:
                                saveSet["errMsg"] = errMsg

                            if startYMDHMS != currDataSet.get("startYMDHMS") and startYMDHMS:
                                saveSet["startYMDHMS"] = startYMDHMS

                            if finishYMDHMS != currDataSet.get("finishYMDHMS") and finishYMDHMS:
                                saveSet["finishYMDHMS"] = finishYMDHMS

                            if costMs != currDataSet.get("costMs") and costMs != None:
                                saveSet["costMs"] = costMs

                            if ownerID != currDataSet.get("ownerID") and ownerID:
                                saveSet["ownerID"] = ownerID

                            if label != currDataSet.get("label") and label:
                                saveSet["label"] = label

                            if memo != currDataSet.get("memo") and memo:
                                saveSet["memo"] = memo

                            if delFlag != currDataSet.get("delFlag") and delFlag:
                                saveSet["delFlag"] = delFlag

                            if saveSet:
                                #saveSet["delFlag"] = "0"
                                saveSet["modifyID"] = loginID
                                saveSet["modifyYMDHMS"] = misc.getTime()

                                #保存数据
                                tableName = comMysql.tablename_convertor_ch_render_job()
                                rtn = comMysql.update_ch_render_job(tableName,recID,saveSet)
                                rtnData["rtn"] = str(rtn)

                                if rtn < 0:
                                    _LOG.warning(f"D: rtn:{rtn},saveSet:{saveSet}")
                                else:
                                    if _DEBUG:
                                        pass
                                        _LOG.info(f"D: rtn:{rtn}")

                                result = rtnData

                        else:
                            #BT
                            errCode = "BT"

                    else:
                        #CB
                        errCode = "CB"

                else:
                    #data invalid
                    errCode = "BA"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST查询代码
def funcRenderjobQry(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID

            #权限检查

            if errCode == "B0": #
                #获取查询输入参数
                recID = dataSet.get("recID", "")

                #houseID = dataSet.get("houseID", "")

                #★ 2026-09-22 手改(前端 P-06 渲染任务筛选需要; 底层 query_ch_render_job 已支持这些入参):
                #  透传 jobCode / topicID / jobStatus / platform / ownerID / beginYMDHMS / endYMDHMS / order。
                #  ⚠ crudApi.py 生成区由 tools/mergeCrudApi.py 覆盖 —— 重跑生成器后本段需重做(见附录 B R-28)。
                jobCode = dataSet.get("jobCode", "")
                topicID = dataSet.get("topicID", "")
                jobStatus = str(dataSet.get("jobStatus", "")).upper()
                platform = dataSet.get("platform", "")
                ownerID = dataSet.get("ownerID", "")
                beginYMDHMS = dataSet.get("beginYMDHMS", "")
                endYMDHMS = dataSet.get("endYMDHMS", "")
                order = dataSet.get("order", "")

                forceFlashFlag = dataSet.get("forceFlashFlag",comGD._CONST_NO) #是否强制查询(刷新)标记

                searchOption = dataSet.get("searchOption")

                mode = dataSet.get("mode", "full")

                #limitNum = dataSet.get("limitNum",0)

                #权限检查/功能检测

                rightCheckFlag = True

                if rightCheckFlag:

                    #生成indexKey
                    indexKeyDataSet = {} #查询生成index的因素
                    if recID:
                        indexKeyDataSet["recID"] = recID
                    #★ 2026-09-22: 过滤条件必须进入 indexKey, 否则不同筛选组合会命中同一查询缓冲(取到别的组合的数据)
                    if jobCode:
                        indexKeyDataSet["jobCode"] = jobCode
                    if topicID:
                        indexKeyDataSet["topicID"] = topicID
                    if jobStatus:
                        indexKeyDataSet["jobStatus"] = jobStatus
                    if platform:
                        indexKeyDataSet["platform"] = platform
                    if ownerID:
                        indexKeyDataSet["ownerID"] = ownerID
                    if beginYMDHMS:
                        indexKeyDataSet["beginYMDHMS"] = beginYMDHMS
                    if endYMDHMS:
                        indexKeyDataSet["endYMDHMS"] = endYMDHMS
                    if order:
                        indexKeyDataSet["order"] = order
                    if searchOption:
                        indexKeyDataSet["searchOption"] = searchOption
                    if mode:
                        indexKeyDataSet["mode"] = mode

                    #if limitNum:
                        #indexKeyDataSet["limitNum"] = limitNum

                    sessionID = sessionIDSet.get("sessionID", "")
                    indexKey = genBufferIndexKey(CMD, sessionID, indexKeyDataSet) 
                    beginNum = int(dataSet.get("beginNum", comGD._DEF_BUFFER_DATA_BEGIN_NUM)) 
                    endNum = int(dataSet.get("endNum", comGD._DEF_BUFFER_DATA_END_NUM)) 

                    #判断数据是否在缓冲区:
                    if not(useQueryBufferFlag and chkBufferExist(indexKey)) or forceFlashFlag == comGD._CONST_YES:

                        if searchOption:
                            currDataList = []
                            tableName = comMysql.tablename_convertor_ch_render_job()
                            allDataList = comMysql.query_ch_render_job(tableName,mode = mode)
                            allowList = ["description", "label"] #筛选字段
                            serachResultSet = comFC.handleSearchOption(searchOption,allowList, allDataList)
                            if serachResultSet["rtn"] == "B0":
                                currDataList = serachResultSet.get("data", [])
                        else:
                            #★ 2026-09-22 手改: 统一一次带过滤的查询(空值与 recID=0 由数据层自动跳过条件)
                            tableName = comMysql.tablename_convertor_ch_render_job()
                            currDataList = comMysql.query_ch_render_job(tableName,recID,
                                                                        jobCode = jobCode,
                                                                        topicID = topicID,
                                                                        jobStatus = jobStatus,
                                                                        platform = platform,
                                                                        ownerID = ownerID,
                                                                        beginYMDHMS = beginYMDHMS,
                                                                        endYMDHMS = endYMDHMS,
                                                                        mode = mode,
                                                                        order = (order if order else "create"))

                        dataList = []

                        for currDataSet in currDataList:
                            aSet = {}

                            #需要把文件转移到public domain
                            #appendixFileID00 =  currDataSet.get("appendixFileID00", "")
                            #appendixFileID00 = getTempLocation(appendixFileID00, privateFlag = True)

                            #if mode == "full":
                                #aSet["houseID"] = currDataSet.get("houseID", "")

                            aSet["recID"] = currDataSet.get("recID","")
                            aSet["jobCode"] = currDataSet.get("jobCode","")
                            aSet["topicID"] = currDataSet.get("topicID","")
                            aSet["layoutCode"] = currDataSet.get("layoutCode","")
                            aSet["platform"] = currDataSet.get("platform","")
                            aSet["jobStatus"] = currDataSet.get("jobStatus","")
                            aSet["inputHash"] = currDataSet.get("inputHash","")
                            aSet["progress"] = currDataSet.get("progress","")
                            aSet["errMsg"] = currDataSet.get("errMsg","")
                            aSet["startYMDHMS"] = currDataSet.get("startYMDHMS","")
                            aSet["finishYMDHMS"] = currDataSet.get("finishYMDHMS","")
                            aSet["costMs"] = currDataSet.get("costMs","")
                            aSet["ownerID"] = currDataSet.get("ownerID","")
                            aSet["label"] = currDataSet.get("label","")
                            aSet["memo"] = currDataSet.get("memo","")
                            aSet["regID"] = currDataSet.get("regID","")
                            aSet["regYMDHMS"] = currDataSet.get("regYMDHMS","")
                            aSet["modifyID"] = currDataSet.get("modifyID","")
                            aSet["modifyYMDHMS"] = currDataSet.get("modifyYMDHMS","")
                            aSet["delFlag"] = currDataSet.get("delFlag","")

                            dataList.append(aSet)

                        #临时缓存机制,改进型, 2023/10/16
                        indexKey = putQuery2Buffer(indexKey, dataList) #存放数据到临时缓冲区去

                    rtnData = getQueryBufferComplte(indexKey, beginNum = beginNum,  endNum = endNum)

                    #rtnData["limitNum"] = limitNum

                    result = rtnData

                else:
                    errCode = "BT"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result




#renderjob(ch_render_job) CRUD end


#artifact(ch_artifact) CRUD begin



#Server REST增加代码
def funcArtifactAdd(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:
        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID
            #权限检查

            if errCode == "B0": #
                #data validation check
                dataValidFlag = True
                if dataValidFlag:
                    saveSet = {}
                    saveSet["artifactKey"] = dataSet.get("artifactKey", "") 
                    saveSet["jobID"] = dataSet.get("jobID", "") 
                    saveSet["topicID"] = dataSet.get("topicID", "") 
                    saveSet["kind"] = dataSet.get("kind", "") 
                    saveSet["platform"] = dataSet.get("platform", "") 
                    saveSet["fileID"] = dataSet.get("fileID", "") 
                    saveSet["thumbnailID"] = dataSet.get("thumbnailID", "") 
                    saveSet["seqNo"] = dataSet.get("seqNo", "") 
                    saveSet["artifactVer"] = dataSet.get("artifactVer", "") 
                    saveSet["specNote"] = dataSet.get("specNote", "") 
                    saveSet["sizeBytes"] = dataSet.get("sizeBytes", "") 
                    saveSet["artifactStatus"] = dataSet.get("artifactStatus", "") 
                    saveSet["expireYMDHMS"] = dataSet.get("expireYMDHMS", "") 
                    saveSet["label"] = dataSet.get("label", "") 
                    saveSet["memo"] = dataSet.get("memo", "") 
                    saveSet["delFlag"] = dataSet.get("delFlag", "0") 
                    saveSet["regID"] = loginID
                    saveSet["regYMDHMS"] = misc.getTime()

                    tableName = comMysql.tablename_convertor_ch_artifact()
                    recID = comMysql.insert_ch_artifact(tableName,saveSet)
                    rtnData["recID"] = str(recID)

                    if recID <= 0:
                        #记录添加失败
                        errCode = "CG"
                        _LOG.warning(f"rtn:{recID},saveSet:{saveSet}")
                    else:
                        if _DEBUG:
                            pass
                            _LOG.info(f"D: recID:{recID}")

                    result = rtnData

                else:
                    #data invalid
                    errCode = "BA"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST删除代码
def funcArtifactDel(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID
            #权限检查

            if errCode == "B0": #
                recID = dataSet.get("recID", "")
                tableName = comMysql.tablename_convertor_ch_artifact()
                currDataList = comMysql.query_ch_artifact(tableName,recID)
                if len(currDataList) == 1:
                    saveSet = {}
                    saveSet["modifyID"] = loginID
                    saveSet["modifyYMDHMS"] = misc.getTime()
                    #saveSet["delFlag"] = "1"

                    rtn = comMysql.delete_ch_artifact(tableName,recID)
                    rtnData["rtn"] = str(rtn)

                    if _DEBUG:
                        _LOG.info(f"D: rtn:{rtn}")

                    result = rtnData

                else:
                    errCode = "CB"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST修改代码
def funcArtifactModify(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID

            #权限检查/功能检测

            if errCode == "B0": #
                #data validation check
                dataValidFlag = True

                artifactKey = dataSet.get("artifactKey") 
                jobID = dataSet.get("jobID") 
                topicID = dataSet.get("topicID") 
                kind = dataSet.get("kind") 
                platform = dataSet.get("platform") 
                fileID = dataSet.get("fileID") 
                thumbnailID = dataSet.get("thumbnailID") 
                seqNo = dataSet.get("seqNo") 
                artifactVer = dataSet.get("artifactVer") 
                specNote = dataSet.get("specNote") 
                sizeBytes = dataSet.get("sizeBytes") 
                artifactStatus = dataSet.get("artifactStatus") 
                expireYMDHMS = dataSet.get("expireYMDHMS") 
                label = dataSet.get("label") 
                memo = dataSet.get("memo") 
                delFlag = dataSet.get("delFlag") 
                #data valid 检查

                if dataValidFlag:
                    #当前记录获取
                    recID = dataSet.get("recID", "")

                    tableName = comMysql.tablename_convertor_ch_artifact()
                    currDataList = comMysql.query_ch_artifact(tableName,recID)

                    if len(currDataList) == 1:
                        currDataSet = currDataList[0]

                        #权限或其他检查
                        if errCode == "B0": #

                            saveSet = {}

                            if artifactKey != currDataSet.get("artifactKey") and artifactKey:
                                saveSet["artifactKey"] = artifactKey

                            if jobID != currDataSet.get("jobID") and jobID != None:
                                saveSet["jobID"] = jobID

                            if topicID != currDataSet.get("topicID") and topicID != None:
                                saveSet["topicID"] = topicID

                            if kind != currDataSet.get("kind") and kind:
                                saveSet["kind"] = kind

                            if platform != currDataSet.get("platform") and platform:
                                saveSet["platform"] = platform

                            if fileID != currDataSet.get("fileID") and fileID:
                                saveSet["fileID"] = fileID

                            if thumbnailID != currDataSet.get("thumbnailID") and thumbnailID:
                                saveSet["thumbnailID"] = thumbnailID

                            if seqNo != currDataSet.get("seqNo") and seqNo != None:
                                saveSet["seqNo"] = seqNo

                            if artifactVer != currDataSet.get("artifactVer") and artifactVer != None:
                                saveSet["artifactVer"] = artifactVer

                            if specNote != currDataSet.get("specNote") and specNote:
                                saveSet["specNote"] = specNote

                            if sizeBytes != currDataSet.get("sizeBytes") and sizeBytes != None:
                                saveSet["sizeBytes"] = sizeBytes

                            if artifactStatus != currDataSet.get("artifactStatus") and artifactStatus:
                                saveSet["artifactStatus"] = artifactStatus

                            if expireYMDHMS != currDataSet.get("expireYMDHMS") and expireYMDHMS:
                                saveSet["expireYMDHMS"] = expireYMDHMS

                            if label != currDataSet.get("label") and label:
                                saveSet["label"] = label

                            if memo != currDataSet.get("memo") and memo:
                                saveSet["memo"] = memo

                            if delFlag != currDataSet.get("delFlag") and delFlag:
                                saveSet["delFlag"] = delFlag

                            if saveSet:
                                #saveSet["delFlag"] = "0"
                                saveSet["modifyID"] = loginID
                                saveSet["modifyYMDHMS"] = misc.getTime()

                                #保存数据
                                tableName = comMysql.tablename_convertor_ch_artifact()
                                rtn = comMysql.update_ch_artifact(tableName,recID,saveSet)
                                rtnData["rtn"] = str(rtn)

                                if rtn < 0:
                                    _LOG.warning(f"D: rtn:{rtn},saveSet:{saveSet}")
                                else:
                                    if _DEBUG:
                                        pass
                                        _LOG.info(f"D: rtn:{rtn}")

                                result = rtnData

                        else:
                            #BT
                            errCode = "BT"

                    else:
                        #CB
                        errCode = "CB"

                else:
                    #data invalid
                    errCode = "BA"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST查询代码
def funcArtifactQry(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID

            #权限检查

            if errCode == "B0": #
                #获取查询输入参数
                recID = dataSet.get("recID", "")

                #houseID = dataSet.get("houseID", "")

                #★ 2026-09-22 手改(前端 P-07 产物台账筛选需要; 底层 query_ch_artifact 已支持这些入参):
                #  透传 jobID / topicID / kind / platform / artifactStatus / order。
                #  ⚠ crudApi.py 生成区由 tools/mergeCrudApi.py 覆盖 —— 重跑生成器后本段需重做(见附录 B R-28)。
                jobID = dataSet.get("jobID", "")
                topicID = dataSet.get("topicID", "")
                kind = dataSet.get("kind", "")
                platform = dataSet.get("platform", "")
                artifactStatus = dataSet.get("artifactStatus", "")
                order = dataSet.get("order", "")

                forceFlashFlag = dataSet.get("forceFlashFlag",comGD._CONST_NO) #是否强制查询(刷新)标记

                searchOption = dataSet.get("searchOption")

                mode = dataSet.get("mode", "full")

                #limitNum = dataSet.get("limitNum",0)

                #权限检查/功能检测

                rightCheckFlag = True

                if rightCheckFlag:

                    #生成indexKey
                    indexKeyDataSet = {} #查询生成index的因素
                    if recID:
                        indexKeyDataSet["recID"] = recID
                    #★ 2026-09-22: 过滤条件必须进入 indexKey, 否则不同筛选组合会命中同一查询缓冲(取到别的组合的数据)
                    if jobID:
                        indexKeyDataSet["jobID"] = jobID
                    if topicID:
                        indexKeyDataSet["topicID"] = topicID
                    if kind:
                        indexKeyDataSet["kind"] = kind
                    if platform:
                        indexKeyDataSet["platform"] = platform
                    if artifactStatus:
                        indexKeyDataSet["artifactStatus"] = artifactStatus
                    if order:
                        indexKeyDataSet["order"] = order
                    if searchOption:
                        indexKeyDataSet["searchOption"] = searchOption
                    if mode:
                        indexKeyDataSet["mode"] = mode

                    #if limitNum:
                        #indexKeyDataSet["limitNum"] = limitNum

                    sessionID = sessionIDSet.get("sessionID", "")
                    indexKey = genBufferIndexKey(CMD, sessionID, indexKeyDataSet) 
                    beginNum = int(dataSet.get("beginNum", comGD._DEF_BUFFER_DATA_BEGIN_NUM)) 
                    endNum = int(dataSet.get("endNum", comGD._DEF_BUFFER_DATA_END_NUM)) 

                    #判断数据是否在缓冲区:
                    if not(useQueryBufferFlag and chkBufferExist(indexKey)) or forceFlashFlag == comGD._CONST_YES:

                        if searchOption:
                            currDataList = []
                            tableName = comMysql.tablename_convertor_ch_artifact()
                            allDataList = comMysql.query_ch_artifact(tableName,mode = mode)
                            allowList = ["description", "label"] #筛选字段
                            serachResultSet = comFC.handleSearchOption(searchOption,allowList, allDataList)
                            if serachResultSet["rtn"] == "B0":
                                currDataList = serachResultSet.get("data", [])
                        else:
                            #★ 2026-09-22 手改: 统一一次带过滤的查询(空值与 recID=0 由数据层自动跳过条件)
                            tableName = comMysql.tablename_convertor_ch_artifact()
                            currDataList = comMysql.query_ch_artifact(tableName,recID,
                                                                     jobID = jobID,
                                                                     topicID = topicID,
                                                                     kind = kind,
                                                                     platform = platform,
                                                                     artifactStatus = artifactStatus,
                                                                     mode = mode,
                                                                     order = (order if order else "create"))

                        dataList = []

                        for currDataSet in currDataList:
                            aSet = {}

                            #需要把文件转移到public domain
                            #appendixFileID00 =  currDataSet.get("appendixFileID00", "")
                            #appendixFileID00 = getTempLocation(appendixFileID00, privateFlag = True)

                            #if mode == "full":
                                #aSet["houseID"] = currDataSet.get("houseID", "")

                            aSet["recID"] = currDataSet.get("recID","")
                            aSet["artifactKey"] = currDataSet.get("artifactKey","")
                            aSet["jobID"] = currDataSet.get("jobID","")
                            aSet["topicID"] = currDataSet.get("topicID","")
                            aSet["kind"] = currDataSet.get("kind","")
                            aSet["platform"] = currDataSet.get("platform","")
                            aSet["fileID"] = currDataSet.get("fileID","")
                            aSet["thumbnailID"] = currDataSet.get("thumbnailID","")
                            aSet["seqNo"] = currDataSet.get("seqNo","")
                            aSet["artifactVer"] = currDataSet.get("artifactVer","")
                            aSet["specNote"] = currDataSet.get("specNote","")
                            aSet["sizeBytes"] = currDataSet.get("sizeBytes","")
                            aSet["artifactStatus"] = currDataSet.get("artifactStatus","")
                            aSet["expireYMDHMS"] = currDataSet.get("expireYMDHMS","")
                            aSet["label"] = currDataSet.get("label","")
                            aSet["memo"] = currDataSet.get("memo","")
                            aSet["regID"] = currDataSet.get("regID","")
                            aSet["regYMDHMS"] = currDataSet.get("regYMDHMS","")
                            aSet["modifyID"] = currDataSet.get("modifyID","")
                            aSet["modifyYMDHMS"] = currDataSet.get("modifyYMDHMS","")
                            aSet["delFlag"] = currDataSet.get("delFlag","")

                            dataList.append(aSet)

                        #临时缓存机制,改进型, 2023/10/16
                        indexKey = putQuery2Buffer(indexKey, dataList) #存放数据到临时缓冲区去

                    rtnData = getQueryBufferComplte(indexKey, beginNum = beginNum,  endNum = endNum)

                    #rtnData["limitNum"] = limitNum

                    result = rtnData

                else:
                    errCode = "BT"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result




#artifact(ch_artifact) CRUD end


#account(ch_account) CRUD begin


#★ 2026-09-22 手改(凭据加密写入; 前端 Step 15 / 附录 B R-30):
#  前端只提交**明文 appSecret**, 由本层调用 common/credentialCipher(AES-256-GCM) 加密后写入
#  credentialCipher/credentialIV。**明文永不落库、不入日志、不回显**; 无密钥/加密失败时显式拒绝落库(F0),
#  绝不静默把明文写进 credentialCipher。
#  ⚠ crudApi.py 生成区由 tools/mergeCrudApi.py 覆盖 —— 重跑生成器后本段需按 R-30 重做。
def _applyAccountSecret(saveSet, dataSet, rtnErrMsgList):
    """明文 appSecret -> 加密写入 saveSet["credentialCipher"]/["credentialIV"]。
       未提供 appSecret 时保持原样(兼容 credentialCipher/credentialIV 直传的旧调用)。
       出参: "" 表示成功; 非空为错误码(F0)。失败原因追加到 rtnErrMsgList(**只写原因, 绝不写明文**)。"""
    plainSecret = dataSet.get("appSecret") or ""
    plainSecret = plainSecret.strip() if isinstance(plainSecret, str) else str(plainSecret).strip()
    if not plainSecret:
        return ""

    try:
        #函数内延迟导入: 不触碰生成区头部 import 段(重跑生成器不影响本函数)
        from common import credentialCipher as comCipher
        encRtn = comCipher.encrypt(plainSecret)
    except Exception as e:
        rtnErrMsgList.append(f"凭据加密失败({type(e).__name__}): 未写入 credentialCipher, 明文未落库; "
                             f"请检查环境变量 CH_CREDENTIAL_KEY 是否已配置")
        return "F0"

    cipher = str((encRtn or {}).get("cipher") or "")
    iv = str((encRtn or {}).get("iv") or "")
    if not cipher or not iv:
        rtnErrMsgList.append("凭据加密返回空 cipher/iv: 未写入 credentialCipher, 明文未落库")
        return "F0"

    saveSet["credentialCipher"] = cipher
    saveSet["credentialIV"] = iv
    return ""


#Server REST增加代码
def funcAccountAdd(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:
        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID
            #权限检查

            if errCode == "B0": #
                #data validation check
                dataValidFlag = True
                if dataValidFlag:
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
                    #★ 2026-09-23 手改(第三方账号管理/归属隔离): 非管理员(operator/customer)**强制**归属 = 登录 loginID,
                    #  一律忽略前端传入的 ownerID; 管理员(administrator/manager)维持「可指定」行为。
                    #  见 plan/前端开发计划.md「第三方账号管理」。
                    if comFC.chkIsManager(roleName):
                        saveSet["ownerID"] = dataSet.get("ownerID", "") 
                    else:
                        saveSet["ownerID"] = loginID 
                    saveSet["label"] = dataSet.get("label", "") 
                    saveSet["memo"] = dataSet.get("memo", "") 
                    saveSet["delFlag"] = dataSet.get("delFlag", "0") 
                    saveSet["regID"] = loginID
                    saveSet["regYMDHMS"] = misc.getTime()

                    #★ 2026-09-22 手改(凭据加密写入): 明文 appSecret -> credentialCipher/credentialIV;
                    #  加密失败则拒绝落库(不静默写明文), 明文不入日志。
                    secretErr = _applyAccountSecret(saveSet, dataSet, rtnErrMsgList)
                    if secretErr:
                        errCode = secretErr
                    else:
                        tableName = comMysql.tablename_convertor_ch_account()
                        recID = comMysql.insert_ch_account(tableName,saveSet)
                        rtnData["recID"] = str(recID)

                        if recID <= 0:
                            #记录添加失败(★ 不打印 saveSet: 其中含 credentialCipher/credentialIV)
                            errCode = "CG"
                            _LOG.warning(f"rtn:{recID}")
                        else:
                            if _DEBUG:
                                pass
                                _LOG.info(f"D: recID:{recID}")

                        result = rtnData

                else:
                    #data invalid
                    errCode = "BA"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST删除代码
def funcAccountDel(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID
            #权限检查

            if errCode == "B0": #
                recID = dataSet.get("recID", "")
                tableName = comMysql.tablename_convertor_ch_account()
                currDataList = comMysql.query_ch_account(tableName,recID)
                #★ 2026-09-23 手改(第三方账号管理/归属隔离): 非管理员仅可删除**本人**账号;
                #  越权一律 BG(不区分「不存在」与「不是你的」, 避免存在性探测); 查不到仍 CB; 管理员维持全量。
                #  见 plan/前端开发计划.md「第三方账号管理」。
                currOwnerID = str(currDataList[0].get("ownerID", "")) if len(currDataList) == 1 else ""
                if len(currDataList) == 1 and (not comFC.chkIsManager(roleName)) and currOwnerID != loginID:
                    errCode = "BG"
                elif len(currDataList) == 1:
                    saveSet = {}
                    saveSet["modifyID"] = loginID
                    saveSet["modifyYMDHMS"] = misc.getTime()
                    #saveSet["delFlag"] = "1"

                    rtn = comMysql.delete_ch_account(tableName,recID)
                    rtnData["rtn"] = str(rtn)

                    if _DEBUG:
                        _LOG.info(f"D: rtn:{rtn}")

                    result = rtnData

                else:
                    errCode = "CB"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST修改代码
def funcAccountModify(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID

            #权限检查/功能检测

            if errCode == "B0": #
                #data validation check
                dataValidFlag = True

                accountCode = dataSet.get("accountCode") 
                platform = dataSet.get("platform") 
                accountName = dataSet.get("accountName") 
                subjectType = dataSet.get("subjectType") 
                verifiedFlag = dataSet.get("verifiedFlag") 
                capability = dataSet.get("capability") 
                appID = dataSet.get("appID") 
                credentialCipher = dataSet.get("credentialCipher") 
                credentialIV = dataSet.get("credentialIV") 
                expireYMDHMS = dataSet.get("expireYMDHMS") 
                healthStatus = dataSet.get("healthStatus") 
                lastCheckYMDHMS = dataSet.get("lastCheckYMDHMS") 
                lastUseYMDHMS = dataSet.get("lastUseYMDHMS") 
                ownerID = dataSet.get("ownerID") 
                label = dataSet.get("label") 
                memo = dataSet.get("memo") 
                delFlag = dataSet.get("delFlag") 
                #data valid 检查

                if dataValidFlag:
                    #当前记录获取
                    recID = dataSet.get("recID", "")

                    tableName = comMysql.tablename_convertor_ch_account()
                    currDataList = comMysql.query_ch_account(tableName,recID)

                    if len(currDataList) == 1:
                        currDataSet = currDataList[0]

                        #权限或其他检查
                        #★ 2026-09-23 手改(第三方账号管理/归属隔离): 非管理员仅可修改**本人**账号,
                        #  越权一律 BG(不区分「不存在」与「不是你的」, 避免存在性探测); 管理员维持全量。
                        #  见 plan/前端开发计划.md「第三方账号管理」。
                        if (not comFC.chkIsManager(roleName)) and (str(currDataSet.get("ownerID", "")) != loginID):
                            errCode = "BG"
                        elif errCode == "B0": #

                            saveSet = {}

                            if accountCode != currDataSet.get("accountCode") and accountCode:
                                saveSet["accountCode"] = accountCode

                            if platform != currDataSet.get("platform") and platform:
                                saveSet["platform"] = platform

                            if accountName != currDataSet.get("accountName") and accountName:
                                saveSet["accountName"] = accountName

                            if subjectType != currDataSet.get("subjectType") and subjectType:
                                saveSet["subjectType"] = subjectType

                            if verifiedFlag != currDataSet.get("verifiedFlag") and verifiedFlag:
                                saveSet["verifiedFlag"] = verifiedFlag

                            if capability != currDataSet.get("capability") and capability:
                                saveSet["capability"] = capability

                            if appID != currDataSet.get("appID") and appID:
                                saveSet["appID"] = appID

                            if credentialCipher != currDataSet.get("credentialCipher") and credentialCipher:
                                saveSet["credentialCipher"] = credentialCipher

                            if credentialIV != currDataSet.get("credentialIV") and credentialIV:
                                saveSet["credentialIV"] = credentialIV

                            if expireYMDHMS != currDataSet.get("expireYMDHMS") and expireYMDHMS:
                                saveSet["expireYMDHMS"] = expireYMDHMS

                            if healthStatus != currDataSet.get("healthStatus") and healthStatus:
                                saveSet["healthStatus"] = healthStatus

                            if lastCheckYMDHMS != currDataSet.get("lastCheckYMDHMS") and lastCheckYMDHMS:
                                saveSet["lastCheckYMDHMS"] = lastCheckYMDHMS

                            if lastUseYMDHMS != currDataSet.get("lastUseYMDHMS") and lastUseYMDHMS:
                                saveSet["lastUseYMDHMS"] = lastUseYMDHMS

                            #★ 2026-09-23 手改(第三方账号管理/归属隔离): 非管理员**不允许**修改归属
                            #  (前端传的 ownerID 一律忽略, 归属由服务端按登录 loginID 派生);
                            #  管理员维持「非空且与当前值不同才写」语义。见 plan/前端开发计划.md。
                            if comFC.chkIsManager(roleName) and ownerID != currDataSet.get("ownerID") and ownerID:
                                saveSet["ownerID"] = ownerID

                            if label != currDataSet.get("label") and label:
                                saveSet["label"] = label

                            if memo != currDataSet.get("memo") and memo:
                                saveSet["memo"] = memo

                            if delFlag != currDataSet.get("delFlag") and delFlag:
                                saveSet["delFlag"] = delFlag

                            #★ 2026-09-22 手改(凭据加密写入): 明文 appSecret -> credentialCipher/credentialIV;
                            #  加密失败(如未配置 CH_CREDENTIAL_KEY)则拒绝更新并回显 F0(明文绝不落库/不日志)。
                            secretErr = _applyAccountSecret(saveSet, dataSet, rtnErrMsgList)
                            if secretErr:
                                errCode = secretErr

                            if saveSet and errCode == "B0":
                                #saveSet["delFlag"] = "0"
                                saveSet["modifyID"] = loginID
                                saveSet["modifyYMDHMS"] = misc.getTime()

                                #保存数据
                                tableName = comMysql.tablename_convertor_ch_account()
                                rtn = comMysql.update_ch_account(tableName,recID,saveSet)
                                rtnData["rtn"] = str(rtn)

                                if rtn < 0:
                                    #★ 不打印 saveSet: 其中含 credentialCipher/credentialIV
                                    _LOG.warning(f"D: rtn:{rtn}")
                                else:
                                    if _DEBUG:
                                        pass
                                        _LOG.info(f"D: rtn:{rtn}")

                                result = rtnData

                        else:
                            #BT
                            errCode = "BT"

                    else:
                        #CB
                        errCode = "CB"

                else:
                    #data invalid
                    errCode = "BA"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST查询代码
def funcAccountQry(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID

            #权限检查

            if errCode == "B0": #
                #获取查询输入参数
                recID = dataSet.get("recID", "")

                #houseID = dataSet.get("houseID", "")

                #★ 2026-09-22 手改(前端 P-11 账号管理筛选需要; 底层 query_ch_account 已支持这些入参):
                #  透传 accountCode / platform / healthStatus / ownerID / order。
                #  ⚠ crudApi.py 生成区由 tools/mergeCrudApi.py 覆盖 —— 重跑生成器后本段需重做(见附录 B R-28)。
                accountCode = dataSet.get("accountCode", "")
                platform = dataSet.get("platform", "")
                healthStatus = str(dataSet.get("healthStatus", "")).upper()
                #★ 2026-09-23 手改(第三方账号管理/归属隔离): 非管理员**强制** ownerID = 登录 loginID
                #  (覆盖前端入参, 前端传别人的 ownerID 也无效); 管理员不放该条件(维持全量台账视角)。
                #  ★ ownerID 必须在下方 indexKeyDataSet 之前落定, 否则不同用户会命中同一查询缓冲。
                if comFC.chkIsManager(roleName):
                    ownerID = dataSet.get("ownerID", "")
                else:
                    ownerID = loginID
                order = dataSet.get("order", "")

                forceFlashFlag = dataSet.get("forceFlashFlag",comGD._CONST_NO) #是否强制查询(刷新)标记

                searchOption = dataSet.get("searchOption")

                mode = dataSet.get("mode", "full")

                #limitNum = dataSet.get("limitNum",0)

                #权限检查/功能检测

                rightCheckFlag = True

                if rightCheckFlag:

                    #生成indexKey
                    indexKeyDataSet = {} #查询生成index的因素
                    if recID:
                        indexKeyDataSet["recID"] = recID
                    #★ 2026-09-22: 过滤条件必须进入 indexKey, 否则不同筛选组合会命中同一查询缓冲(取到别的组合的数据)
                    if accountCode:
                        indexKeyDataSet["accountCode"] = accountCode
                    if platform:
                        indexKeyDataSet["platform"] = platform
                    if healthStatus:
                        indexKeyDataSet["healthStatus"] = healthStatus
                    if ownerID:
                        indexKeyDataSet["ownerID"] = ownerID
                    if order:
                        indexKeyDataSet["order"] = order
                    if searchOption:
                        indexKeyDataSet["searchOption"] = searchOption
                    if mode:
                        indexKeyDataSet["mode"] = mode

                    #if limitNum:
                        #indexKeyDataSet["limitNum"] = limitNum

                    sessionID = sessionIDSet.get("sessionID", "")
                    indexKey = genBufferIndexKey(CMD, sessionID, indexKeyDataSet) 
                    beginNum = int(dataSet.get("beginNum", comGD._DEF_BUFFER_DATA_BEGIN_NUM)) 
                    endNum = int(dataSet.get("endNum", comGD._DEF_BUFFER_DATA_END_NUM)) 

                    #判断数据是否在缓冲区:
                    if not(useQueryBufferFlag and chkBufferExist(indexKey)) or forceFlashFlag == comGD._CONST_YES:

                        if searchOption:
                            currDataList = []
                            tableName = comMysql.tablename_convertor_ch_account()
                            allDataList = comMysql.query_ch_account(tableName,mode = mode)
                            allowList = ["description", "label"] #筛选字段
                            serachResultSet = comFC.handleSearchOption(searchOption,allowList, allDataList)
                            if serachResultSet["rtn"] == "B0":
                                currDataList = serachResultSet.get("data", [])
                            #★ 2026-09-23 手改(第三方账号管理/归属隔离): searchOption 分支是「全表拉取 + 客户端筛选」,
                            #  不受 query_ch_account 的 ownerID 条件约束 —— 必须在此对结果集**二次按归属过滤**,
                            #  否则非管理员可经该分支跨用户读全表。见 plan/前端开发计划.md。
                            if ownerID:
                                currDataList = [x for x in currDataList if str(x.get("ownerID", "")) == ownerID]
                        else:
                            if recID:
                                tableName = comMysql.tablename_convertor_ch_account()
                                currDataList = comMysql.query_ch_account(tableName,recID,
                                                                         accountCode = accountCode,
                                                                         platform = platform,
                                                                         healthStatus = healthStatus,
                                                                         ownerID = ownerID,
                                                                         mode = mode,
                                                                         order = (order if order else "create"))
                            else:
                                #★ 2026-09-22 手改: 统一一次带过滤的查询(空值与 recID=0 由数据层自动跳过条件)
                                tableName = comMysql.tablename_convertor_ch_account()
                                currDataList = comMysql.query_ch_account(tableName,
                                                                         accountCode = accountCode,
                                                                         platform = platform,
                                                                         healthStatus = healthStatus,
                                                                         ownerID = ownerID,
                                                                         mode = mode,
                                                                         order = (order if order else "create"))

                        dataList = []

                        for currDataSet in currDataList:
                            aSet = {}

                            #需要把文件转移到public domain
                            #appendixFileID00 =  currDataSet.get("appendixFileID00", "")
                            #appendixFileID00 = getTempLocation(appendixFileID00, privateFlag = True)

                            #if mode == "full":
                                #aSet["houseID"] = currDataSet.get("houseID", "")

                            aSet["recID"] = currDataSet.get("recID","")
                            aSet["accountCode"] = currDataSet.get("accountCode","")
                            aSet["platform"] = currDataSet.get("platform","")
                            aSet["accountName"] = currDataSet.get("accountName","")
                            aSet["subjectType"] = currDataSet.get("subjectType","")
                            aSet["verifiedFlag"] = currDataSet.get("verifiedFlag","")
                            aSet["capability"] = currDataSet.get("capability","")
                            aSet["appID"] = currDataSet.get("appID","")
                            aSet["credentialCipher"] = currDataSet.get("credentialCipher","")
                            aSet["credentialIV"] = currDataSet.get("credentialIV","")
                            aSet["expireYMDHMS"] = currDataSet.get("expireYMDHMS","")
                            aSet["healthStatus"] = currDataSet.get("healthStatus","")
                            aSet["lastCheckYMDHMS"] = currDataSet.get("lastCheckYMDHMS","")
                            aSet["lastUseYMDHMS"] = currDataSet.get("lastUseYMDHMS","")
                            aSet["ownerID"] = currDataSet.get("ownerID","")
                            aSet["label"] = currDataSet.get("label","")
                            aSet["memo"] = currDataSet.get("memo","")
                            aSet["regID"] = currDataSet.get("regID","")
                            aSet["regYMDHMS"] = currDataSet.get("regYMDHMS","")
                            aSet["modifyID"] = currDataSet.get("modifyID","")
                            aSet["modifyYMDHMS"] = currDataSet.get("modifyYMDHMS","")
                            aSet["delFlag"] = currDataSet.get("delFlag","")

                            dataList.append(aSet)

                        #临时缓存机制,改进型, 2023/10/16
                        indexKey = putQuery2Buffer(indexKey, dataList) #存放数据到临时缓冲区去

                    rtnData = getQueryBufferComplte(indexKey, beginNum = beginNum,  endNum = endNum)

                    #rtnData["limitNum"] = limitNum

                    result = rtnData

                else:
                    errCode = "BT"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result




#account(ch_account) CRUD end


#publishrecord(ch_publish_record) CRUD begin



#Server REST增加代码
def funcPublishrecordAdd(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:
        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID
            #权限检查

            if errCode == "B0": #
                #data validation check
                dataValidFlag = True
                if dataValidFlag:
                    saveSet = {}
                    saveSet["idempotencyKey"] = dataSet.get("idempotencyKey", "") 
                    saveSet["artifactId"] = dataSet.get("artifactId", "") 
                    saveSet["topicID"] = dataSet.get("topicID", "") 
                    saveSet["accountID"] = dataSet.get("accountID", "") 
                    saveSet["platform"] = dataSet.get("platform", "") 
                    saveSet["deliverMode"] = dataSet.get("deliverMode", "") 
                    saveSet["requestJson"] = dataSet.get("requestJson", "") 
                    saveSet["responseJson"] = dataSet.get("responseJson", "") 
                    saveSet["errcode"] = dataSet.get("errcode", "") 
                    saveSet["errmsg"] = dataSet.get("errmsg", "") 
                    saveSet["success"] = dataSet.get("success", "") 
                    saveSet["remoteID"] = dataSet.get("remoteID", "") 
                    saveSet["operator"] = dataSet.get("operator", "") 
                    saveSet["pushedYMDHMS"] = dataSet.get("pushedYMDHMS", "") 
                    saveSet["label"] = dataSet.get("label", "") 
                    saveSet["memo"] = dataSet.get("memo", "") 
                    saveSet["delFlag"] = dataSet.get("delFlag", "0") 
                    saveSet["regID"] = loginID
                    saveSet["regYMDHMS"] = misc.getTime()

                    tableName = comMysql.tablename_convertor_ch_publish_record()
                    recID = comMysql.insert_ch_publish_record(tableName,saveSet)
                    rtnData["recID"] = str(recID)

                    if recID <= 0:
                        #记录添加失败
                        errCode = "CG"
                        _LOG.warning(f"rtn:{recID},saveSet:{saveSet}")
                    else:
                        if _DEBUG:
                            pass
                            _LOG.info(f"D: recID:{recID}")

                    result = rtnData

                else:
                    #data invalid
                    errCode = "BA"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST删除代码
def funcPublishrecordDel(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID
            #权限检查

            if errCode == "B0": #
                recID = dataSet.get("recID", "")
                tableName = comMysql.tablename_convertor_ch_publish_record()
                currDataList = comMysql.query_ch_publish_record(tableName,recID)
                if len(currDataList) == 1:
                    saveSet = {}
                    saveSet["modifyID"] = loginID
                    saveSet["modifyYMDHMS"] = misc.getTime()
                    #saveSet["delFlag"] = "1"

                    rtn = comMysql.delete_ch_publish_record(tableName,recID)
                    rtnData["rtn"] = str(rtn)

                    if _DEBUG:
                        _LOG.info(f"D: rtn:{rtn}")

                    result = rtnData

                else:
                    errCode = "CB"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST修改代码
def funcPublishrecordModify(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID

            #权限检查/功能检测

            if errCode == "B0": #
                #data validation check
                dataValidFlag = True

                idempotencyKey = dataSet.get("idempotencyKey") 
                artifactId = dataSet.get("artifactId") 
                topicID = dataSet.get("topicID") 
                accountID = dataSet.get("accountID") 
                platform = dataSet.get("platform") 
                deliverMode = dataSet.get("deliverMode") 
                requestJson = dataSet.get("requestJson") 
                responseJson = dataSet.get("responseJson") 
                errcode = dataSet.get("errcode") 
                errmsg = dataSet.get("errmsg") 
                success = dataSet.get("success") 
                remoteID = dataSet.get("remoteID") 
                operator = dataSet.get("operator") 
                pushedYMDHMS = dataSet.get("pushedYMDHMS") 
                label = dataSet.get("label") 
                memo = dataSet.get("memo") 
                delFlag = dataSet.get("delFlag") 
                #data valid 检查

                if dataValidFlag:
                    #当前记录获取
                    recID = dataSet.get("recID", "")

                    tableName = comMysql.tablename_convertor_ch_publish_record()
                    currDataList = comMysql.query_ch_publish_record(tableName,recID)

                    if len(currDataList) == 1:
                        currDataSet = currDataList[0]

                        #权限或其他检查
                        if errCode == "B0": #

                            saveSet = {}

                            if idempotencyKey != currDataSet.get("idempotencyKey") and idempotencyKey:
                                saveSet["idempotencyKey"] = idempotencyKey

                            if artifactId != currDataSet.get("artifactId") and artifactId != None:
                                saveSet["artifactId"] = artifactId

                            if topicID != currDataSet.get("topicID") and topicID != None:
                                saveSet["topicID"] = topicID

                            if accountID != currDataSet.get("accountID") and accountID != None:
                                saveSet["accountID"] = accountID

                            if platform != currDataSet.get("platform") and platform:
                                saveSet["platform"] = platform

                            if deliverMode != currDataSet.get("deliverMode") and deliverMode:
                                saveSet["deliverMode"] = deliverMode

                            if requestJson != currDataSet.get("requestJson") and requestJson:
                                saveSet["requestJson"] = requestJson

                            if responseJson != currDataSet.get("responseJson") and responseJson:
                                saveSet["responseJson"] = responseJson

                            if errcode != currDataSet.get("errcode") and errcode != None:
                                saveSet["errcode"] = errcode

                            if errmsg != currDataSet.get("errmsg") and errmsg:
                                saveSet["errmsg"] = errmsg

                            if success != currDataSet.get("success") and success:
                                saveSet["success"] = success

                            if remoteID != currDataSet.get("remoteID") and remoteID:
                                saveSet["remoteID"] = remoteID

                            if operator != currDataSet.get("operator") and operator:
                                saveSet["operator"] = operator

                            if pushedYMDHMS != currDataSet.get("pushedYMDHMS") and pushedYMDHMS:
                                saveSet["pushedYMDHMS"] = pushedYMDHMS

                            if label != currDataSet.get("label") and label:
                                saveSet["label"] = label

                            if memo != currDataSet.get("memo") and memo:
                                saveSet["memo"] = memo

                            if delFlag != currDataSet.get("delFlag") and delFlag:
                                saveSet["delFlag"] = delFlag

                            if saveSet:
                                #saveSet["delFlag"] = "0"
                                saveSet["modifyID"] = loginID
                                saveSet["modifyYMDHMS"] = misc.getTime()

                                #保存数据
                                tableName = comMysql.tablename_convertor_ch_publish_record()
                                rtn = comMysql.update_ch_publish_record(tableName,recID,saveSet)
                                rtnData["rtn"] = str(rtn)

                                if rtn < 0:
                                    _LOG.warning(f"D: rtn:{rtn},saveSet:{saveSet}")
                                else:
                                    if _DEBUG:
                                        pass
                                        _LOG.info(f"D: rtn:{rtn}")

                                result = rtnData

                        else:
                            #BT
                            errCode = "BT"

                    else:
                        #CB
                        errCode = "CB"

                else:
                    #data invalid
                    errCode = "BA"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST查询代码
def funcPublishrecordQry(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID

            #权限检查

            if errCode == "B0": #
                #获取查询输入参数
                recID = dataSet.get("recID", "")

                #houseID = dataSet.get("houseID", "")

                #★ 2026-09-22 手改(前端 P-10 投递/发布记录筛选需要; 底层 query_ch_publish_record 已支持这些入参):
                #  透传 idempotencyKey / artifactID / topicID / accountID / platform / success / beginYMDHMS /
                #  endYMDHMS / order。
                #  ★ accountID: 前端 P-11 删除账号前展示「关联发布记录数」需要(附录 B R-31)。
                #  ⚠ crudApi.py 生成区由 tools/mergeCrudApi.py 覆盖 —— 重跑生成器后本段需重做(见附录 B R-28)。
                idempotencyKey = dataSet.get("idempotencyKey", "")
                artifactID = dataSet.get("artifactID", "")
                topicID = dataSet.get("topicID", "")
                accountID = dataSet.get("accountID", "")
                platform = dataSet.get("platform", "")
                success = dataSet.get("success", "")
                beginYMDHMS = dataSet.get("beginYMDHMS", "")
                endYMDHMS = dataSet.get("endYMDHMS", "")
                order = dataSet.get("order", "")

                forceFlashFlag = dataSet.get("forceFlashFlag",comGD._CONST_NO) #是否强制查询(刷新)标记

                searchOption = dataSet.get("searchOption")

                mode = dataSet.get("mode", "full")

                #limitNum = dataSet.get("limitNum",0)

                #权限检查/功能检测

                rightCheckFlag = True

                if rightCheckFlag:

                    #生成indexKey
                    indexKeyDataSet = {} #查询生成index的因素
                    if recID:
                        indexKeyDataSet["recID"] = recID
                    #★ 2026-09-22: 过滤条件必须进入 indexKey, 否则不同筛选组合会命中同一查询缓冲(取到别的组合的数据)
                    if idempotencyKey:
                        indexKeyDataSet["idempotencyKey"] = idempotencyKey
                    if artifactID:
                        indexKeyDataSet["artifactID"] = artifactID
                    if topicID:
                        indexKeyDataSet["topicID"] = topicID
                    if accountID:
                        indexKeyDataSet["accountID"] = accountID
                    if platform:
                        indexKeyDataSet["platform"] = platform
                    if success:
                        indexKeyDataSet["success"] = success
                    if beginYMDHMS:
                        indexKeyDataSet["beginYMDHMS"] = beginYMDHMS
                    if endYMDHMS:
                        indexKeyDataSet["endYMDHMS"] = endYMDHMS
                    if order:
                        indexKeyDataSet["order"] = order
                    if searchOption:
                        indexKeyDataSet["searchOption"] = searchOption
                    if mode:
                        indexKeyDataSet["mode"] = mode

                    #if limitNum:
                        #indexKeyDataSet["limitNum"] = limitNum

                    sessionID = sessionIDSet.get("sessionID", "")
                    indexKey = genBufferIndexKey(CMD, sessionID, indexKeyDataSet) 
                    beginNum = int(dataSet.get("beginNum", comGD._DEF_BUFFER_DATA_BEGIN_NUM)) 
                    endNum = int(dataSet.get("endNum", comGD._DEF_BUFFER_DATA_END_NUM)) 

                    #判断数据是否在缓冲区:
                    if not(useQueryBufferFlag and chkBufferExist(indexKey)) or forceFlashFlag == comGD._CONST_YES:

                        if searchOption:
                            currDataList = []
                            tableName = comMysql.tablename_convertor_ch_publish_record()
                            allDataList = comMysql.query_ch_publish_record(tableName,mode = mode)
                            allowList = ["description", "label"] #筛选字段
                            serachResultSet = comFC.handleSearchOption(searchOption,allowList, allDataList)
                            if serachResultSet["rtn"] == "B0":
                                currDataList = serachResultSet.get("data", [])
                        else:
                            if recID:
                                tableName = comMysql.tablename_convertor_ch_publish_record()
                                currDataList = comMysql.query_ch_publish_record(tableName,recID,
                                                                                idempotencyKey = idempotencyKey,
                                                                                artifactID = artifactID,
                                                                                topicID = topicID,
                                                                                accountID = accountID,
                                                                                platform = platform,
                                                                                success = success,
                                                                                beginYMDHMS = beginYMDHMS,
                                                                                endYMDHMS = endYMDHMS,
                                                                                mode = mode,
                                                                                order = (order if order else "create"))
                            else:
                                #★ 2026-09-22 手改: 统一一次带过滤的查询(空值与 recID=0 由数据层自动跳过条件)
                                tableName = comMysql.tablename_convertor_ch_publish_record()
                                currDataList = comMysql.query_ch_publish_record(tableName,
                                                                                idempotencyKey = idempotencyKey,
                                                                                artifactID = artifactID,
                                                                                topicID = topicID,
                                                                                accountID = accountID,
                                                                                platform = platform,
                                                                                success = success,
                                                                                beginYMDHMS = beginYMDHMS,
                                                                                endYMDHMS = endYMDHMS,
                                                                                mode = mode,
                                                                                order = (order if order else "create"))

                        dataList = []

                        for currDataSet in currDataList:
                            aSet = {}

                            #需要把文件转移到public domain
                            #appendixFileID00 =  currDataSet.get("appendixFileID00", "")
                            #appendixFileID00 = getTempLocation(appendixFileID00, privateFlag = True)

                            #if mode == "full":
                                #aSet["houseID"] = currDataSet.get("houseID", "")

                            aSet["recID"] = currDataSet.get("recID","")
                            aSet["idempotencyKey"] = currDataSet.get("idempotencyKey","")
                            aSet["artifactId"] = currDataSet.get("artifactId","")
                            aSet["topicID"] = currDataSet.get("topicID","")
                            aSet["accountID"] = currDataSet.get("accountID","")
                            aSet["platform"] = currDataSet.get("platform","")
                            aSet["deliverMode"] = currDataSet.get("deliverMode","")
                            aSet["requestJson"] = currDataSet.get("requestJson","")
                            aSet["responseJson"] = currDataSet.get("responseJson","")
                            aSet["errcode"] = currDataSet.get("errcode","")
                            aSet["errmsg"] = currDataSet.get("errmsg","")
                            aSet["success"] = currDataSet.get("success","")
                            aSet["remoteID"] = currDataSet.get("remoteID","")
                            aSet["operator"] = currDataSet.get("operator","")
                            aSet["pushedYMDHMS"] = currDataSet.get("pushedYMDHMS","")
                            aSet["label"] = currDataSet.get("label","")
                            aSet["memo"] = currDataSet.get("memo","")
                            aSet["regID"] = currDataSet.get("regID","")
                            aSet["regYMDHMS"] = currDataSet.get("regYMDHMS","")
                            aSet["modifyID"] = currDataSet.get("modifyID","")
                            aSet["modifyYMDHMS"] = currDataSet.get("modifyYMDHMS","")
                            aSet["delFlag"] = currDataSet.get("delFlag","")

                            dataList.append(aSet)

                        #临时缓存机制,改进型, 2023/10/16
                        indexKey = putQuery2Buffer(indexKey, dataList) #存放数据到临时缓冲区去

                    rtnData = getQueryBufferComplte(indexKey, beginNum = beginNum,  endNum = endNum)

                    #rtnData["limitNum"] = limitNum

                    result = rtnData

                else:
                    errCode = "BT"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result




#publishrecord(ch_publish_record) CRUD end


#mcptoken(ch_mcp_token) CRUD begin



#Server REST增加代码
def funcMcptokenAdd(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:
        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID
            #权限检查

            if errCode == "B0": #
                #data validation check
                dataValidFlag = True
                if dataValidFlag:
                    saveSet = {}
                    saveSet["tokenHash"] = dataSet.get("tokenHash", "") 
                    saveSet["tokenName"] = dataSet.get("tokenName", "") 
                    saveSet["tokenScope"] = dataSet.get("tokenScope", "") 
                    saveSet["projectCode"] = dataSet.get("projectCode", "") 
                    saveSet["transport"] = dataSet.get("transport", "") 
                    saveSet["lastUseYMDHMS"] = dataSet.get("lastUseYMDHMS", "") 
                    saveSet["useCount"] = dataSet.get("useCount", "") 
                    saveSet["revokedYMDHMS"] = dataSet.get("revokedYMDHMS", "") 
                    saveSet["ownerID"] = dataSet.get("ownerID", "") 
                    saveSet["label"] = dataSet.get("label", "") 
                    saveSet["memo"] = dataSet.get("memo", "") 
                    saveSet["delFlag"] = dataSet.get("delFlag", "0") 
                    saveSet["regID"] = loginID
                    saveSet["regYMDHMS"] = misc.getTime()

                    tableName = comMysql.tablename_convertor_ch_mcp_token()
                    recID = comMysql.insert_ch_mcp_token(tableName,saveSet)
                    rtnData["recID"] = str(recID)

                    if recID <= 0:
                        #记录添加失败
                        errCode = "CG"
                        _LOG.warning(f"rtn:{recID},saveSet:{saveSet}")
                    else:
                        if _DEBUG:
                            pass
                            _LOG.info(f"D: recID:{recID}")

                    result = rtnData

                else:
                    #data invalid
                    errCode = "BA"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST删除代码
def funcMcptokenDel(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID
            #权限检查

            if errCode == "B0": #
                recID = dataSet.get("recID", "")
                tableName = comMysql.tablename_convertor_ch_mcp_token()
                currDataList = comMysql.query_ch_mcp_token(tableName,recID)
                if len(currDataList) == 1:
                    saveSet = {}
                    saveSet["modifyID"] = loginID
                    saveSet["modifyYMDHMS"] = misc.getTime()
                    #saveSet["delFlag"] = "1"

                    rtn = comMysql.delete_ch_mcp_token(tableName,recID)
                    rtnData["rtn"] = str(rtn)

                    if _DEBUG:
                        _LOG.info(f"D: rtn:{rtn}")

                    result = rtnData

                else:
                    errCode = "CB"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST修改代码
def funcMcptokenModify(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID

            #权限检查/功能检测

            if errCode == "B0": #
                #data validation check
                dataValidFlag = True

                tokenHash = dataSet.get("tokenHash") 
                tokenName = dataSet.get("tokenName") 
                tokenScope = dataSet.get("tokenScope") 
                projectCode = dataSet.get("projectCode") 
                transport = dataSet.get("transport") 
                lastUseYMDHMS = dataSet.get("lastUseYMDHMS") 
                useCount = dataSet.get("useCount") 
                revokedYMDHMS = dataSet.get("revokedYMDHMS") 
                ownerID = dataSet.get("ownerID") 
                label = dataSet.get("label") 
                memo = dataSet.get("memo") 
                delFlag = dataSet.get("delFlag") 
                #data valid 检查

                if dataValidFlag:
                    #当前记录获取
                    recID = dataSet.get("recID", "")

                    tableName = comMysql.tablename_convertor_ch_mcp_token()
                    currDataList = comMysql.query_ch_mcp_token(tableName,recID)

                    if len(currDataList) == 1:
                        currDataSet = currDataList[0]

                        #权限或其他检查
                        if errCode == "B0": #

                            saveSet = {}

                            if tokenHash != currDataSet.get("tokenHash") and tokenHash:
                                saveSet["tokenHash"] = tokenHash

                            if tokenName != currDataSet.get("tokenName") and tokenName:
                                saveSet["tokenName"] = tokenName

                            if tokenScope != currDataSet.get("tokenScope") and tokenScope:
                                saveSet["tokenScope"] = tokenScope

                            if projectCode != currDataSet.get("projectCode") and projectCode:
                                saveSet["projectCode"] = projectCode

                            if transport != currDataSet.get("transport") and transport:
                                saveSet["transport"] = transport

                            if lastUseYMDHMS != currDataSet.get("lastUseYMDHMS") and lastUseYMDHMS:
                                saveSet["lastUseYMDHMS"] = lastUseYMDHMS

                            if useCount != currDataSet.get("useCount") and useCount != None:
                                saveSet["useCount"] = useCount

                            if revokedYMDHMS != currDataSet.get("revokedYMDHMS") and revokedYMDHMS:
                                saveSet["revokedYMDHMS"] = revokedYMDHMS

                            if ownerID != currDataSet.get("ownerID") and ownerID:
                                saveSet["ownerID"] = ownerID

                            if label != currDataSet.get("label") and label:
                                saveSet["label"] = label

                            if memo != currDataSet.get("memo") and memo:
                                saveSet["memo"] = memo

                            if delFlag != currDataSet.get("delFlag") and delFlag:
                                saveSet["delFlag"] = delFlag

                            if saveSet:
                                #saveSet["delFlag"] = "0"
                                saveSet["modifyID"] = loginID
                                saveSet["modifyYMDHMS"] = misc.getTime()

                                #保存数据
                                tableName = comMysql.tablename_convertor_ch_mcp_token()
                                rtn = comMysql.update_ch_mcp_token(tableName,recID,saveSet)
                                rtnData["rtn"] = str(rtn)

                                if rtn < 0:
                                    _LOG.warning(f"D: rtn:{rtn},saveSet:{saveSet}")
                                else:
                                    if _DEBUG:
                                        pass
                                        _LOG.info(f"D: rtn:{rtn}")

                                result = rtnData

                        else:
                            #BT
                            errCode = "BT"

                    else:
                        #CB
                        errCode = "CB"

                else:
                    #data invalid
                    errCode = "BA"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST查询代码
def funcMcptokenQry(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID

            #权限检查

            if errCode == "B0": #
                #获取查询输入参数
                recID = dataSet.get("recID", "")

                #houseID = dataSet.get("houseID", "")

                #★ 2026-09-22 手改(前端 P-13 设置页令牌列表筛选需要; 底层 query_ch_mcp_token 已支持这些入参):
                #  透传 tokenHash / tokenName / tokenScope / projectCode / order。
                #  ⚠ crudApi.py 生成区由 tools/mergeCrudApi.py 覆盖 —— 重跑生成器后本段需重做(见附录 B R-28)。
                tokenHash = dataSet.get("tokenHash", "")
                tokenName = dataSet.get("tokenName", "")
                tokenScope = dataSet.get("tokenScope", "")
                projectCode = dataSet.get("projectCode", "")
                order = dataSet.get("order", "")

                forceFlashFlag = dataSet.get("forceFlashFlag",comGD._CONST_NO) #是否强制查询(刷新)标记

                searchOption = dataSet.get("searchOption")

                mode = dataSet.get("mode", "full")

                #limitNum = dataSet.get("limitNum",0)

                #权限检查/功能检测

                rightCheckFlag = True

                if rightCheckFlag:

                    #生成indexKey
                    indexKeyDataSet = {} #查询生成index的因素
                    if recID:
                        indexKeyDataSet["recID"] = recID
                    #★ 2026-09-22: 过滤条件必须进入 indexKey, 否则不同筛选组合会命中同一查询缓冲(取到别的组合的数据)
                    if tokenHash:
                        indexKeyDataSet["tokenHash"] = tokenHash
                    if tokenName:
                        indexKeyDataSet["tokenName"] = tokenName
                    if tokenScope:
                        indexKeyDataSet["tokenScope"] = tokenScope
                    if projectCode:
                        indexKeyDataSet["projectCode"] = projectCode
                    if order:
                        indexKeyDataSet["order"] = order
                    if searchOption:
                        indexKeyDataSet["searchOption"] = searchOption
                    if mode:
                        indexKeyDataSet["mode"] = mode

                    #if limitNum:
                        #indexKeyDataSet["limitNum"] = limitNum

                    sessionID = sessionIDSet.get("sessionID", "")
                    indexKey = genBufferIndexKey(CMD, sessionID, indexKeyDataSet) 
                    beginNum = int(dataSet.get("beginNum", comGD._DEF_BUFFER_DATA_BEGIN_NUM)) 
                    endNum = int(dataSet.get("endNum", comGD._DEF_BUFFER_DATA_END_NUM)) 

                    #判断数据是否在缓冲区:
                    if not(useQueryBufferFlag and chkBufferExist(indexKey)) or forceFlashFlag == comGD._CONST_YES:

                        if searchOption:
                            currDataList = []
                            tableName = comMysql.tablename_convertor_ch_mcp_token()
                            allDataList = comMysql.query_ch_mcp_token(tableName,mode = mode)
                            allowList = ["description", "label"] #筛选字段
                            serachResultSet = comFC.handleSearchOption(searchOption,allowList, allDataList)
                            if serachResultSet["rtn"] == "B0":
                                currDataList = serachResultSet.get("data", [])
                        else:
                            if recID:
                                tableName = comMysql.tablename_convertor_ch_mcp_token()
                                currDataList = comMysql.query_ch_mcp_token(tableName,recID,mode = mode)
                            else:
                                tableName = comMysql.tablename_convertor_ch_mcp_token()
                                currDataList = comMysql.query_ch_mcp_token(tableName)

                        dataList = []

                        for currDataSet in currDataList:
                            aSet = {}

                            #需要把文件转移到public domain
                            #appendixFileID00 =  currDataSet.get("appendixFileID00", "")
                            #appendixFileID00 = getTempLocation(appendixFileID00, privateFlag = True)

                            #if mode == "full":
                                #aSet["houseID"] = currDataSet.get("houseID", "")

                            aSet["recID"] = currDataSet.get("recID","")
                            aSet["tokenHash"] = currDataSet.get("tokenHash","")
                            aSet["tokenName"] = currDataSet.get("tokenName","")
                            aSet["tokenScope"] = currDataSet.get("tokenScope","")
                            aSet["projectCode"] = currDataSet.get("projectCode","")
                            aSet["transport"] = currDataSet.get("transport","")
                            aSet["lastUseYMDHMS"] = currDataSet.get("lastUseYMDHMS","")
                            aSet["useCount"] = currDataSet.get("useCount","")
                            aSet["revokedYMDHMS"] = currDataSet.get("revokedYMDHMS","")
                            aSet["ownerID"] = currDataSet.get("ownerID","")
                            aSet["label"] = currDataSet.get("label","")
                            aSet["memo"] = currDataSet.get("memo","")
                            aSet["regID"] = currDataSet.get("regID","")
                            aSet["regYMDHMS"] = currDataSet.get("regYMDHMS","")
                            aSet["modifyID"] = currDataSet.get("modifyID","")
                            aSet["modifyYMDHMS"] = currDataSet.get("modifyYMDHMS","")
                            aSet["delFlag"] = currDataSet.get("delFlag","")

                            dataList.append(aSet)

                        #临时缓存机制,改进型, 2023/10/16
                        indexKey = putQuery2Buffer(indexKey, dataList) #存放数据到临时缓冲区去

                    rtnData = getQueryBufferComplte(indexKey, beginNum = beginNum,  endNum = endNum)

                    #rtnData["limitNum"] = limitNum

                    result = rtnData

                else:
                    errCode = "BT"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result




#mcptoken(ch_mcp_token) CRUD end


#auditlog(ch_audit_log) CRUD begin



#Server REST增加代码
def funcAuditlogAdd(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:
        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID
            #权限检查

            if errCode == "B0": #
                #data validation check
                dataValidFlag = True
                if dataValidFlag:
                    saveSet = {}
                    saveSet["actor"] = dataSet.get("actor", "") 
                    saveSet["source"] = dataSet.get("source", "") 
                    saveSet["action"] = dataSet.get("action", "") 
                    saveSet["targetType"] = dataSet.get("targetType", "") 
                    saveSet["targetID"] = dataSet.get("targetID", "") 
                    saveSet["payloadDigest"] = dataSet.get("payloadDigest", "") 
                    saveSet["result"] = dataSet.get("result", "") 
                    saveSet["errMsg"] = dataSet.get("errMsg", "") 
                    saveSet["costMs"] = dataSet.get("costMs", "") 
                    saveSet["ipAddr"] = dataSet.get("ipAddr", "") 
                    saveSet["label"] = dataSet.get("label", "") 
                    saveSet["memo"] = dataSet.get("memo", "") 
                    saveSet["delFlag"] = dataSet.get("delFlag", "0") 
                    saveSet["regID"] = loginID
                    saveSet["regYMDHMS"] = misc.getTime()

                    tableName = comMysql.tablename_convertor_ch_audit_log()
                    recID = comMysql.insert_ch_audit_log(tableName,saveSet)
                    rtnData["recID"] = str(recID)

                    if recID <= 0:
                        #记录添加失败
                        errCode = "CG"
                        _LOG.warning(f"rtn:{recID},saveSet:{saveSet}")
                    else:
                        if _DEBUG:
                            pass
                            _LOG.info(f"D: recID:{recID}")

                    result = rtnData

                else:
                    #data invalid
                    errCode = "BA"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST删除代码
def funcAuditlogDel(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID
            #权限检查

            if errCode == "B0": #
                recID = dataSet.get("recID", "")
                tableName = comMysql.tablename_convertor_ch_audit_log()
                currDataList = comMysql.query_ch_audit_log(tableName,recID)
                if len(currDataList) == 1:
                    saveSet = {}
                    saveSet["modifyID"] = loginID
                    saveSet["modifyYMDHMS"] = misc.getTime()
                    #saveSet["delFlag"] = "1"

                    rtn = comMysql.delete_ch_audit_log(tableName,recID)
                    rtnData["rtn"] = str(rtn)

                    if _DEBUG:
                        _LOG.info(f"D: rtn:{rtn}")

                    result = rtnData

                else:
                    errCode = "CB"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST修改代码
def funcAuditlogModify(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID

            #权限检查/功能检测

            if errCode == "B0": #
                #data validation check
                dataValidFlag = True

                actor = dataSet.get("actor") 
                source = dataSet.get("source") 
                action = dataSet.get("action") 
                targetType = dataSet.get("targetType") 
                targetID = dataSet.get("targetID") 
                payloadDigest = dataSet.get("payloadDigest") 
                #★ 2026-09-22 既有缺陷修复: 本函数用 `result` 作返回容器, 原生成件把字段值也赋给 result
                #  (str 覆盖 dict -> 收尾赋值抛 TypeError -> 恒返回 ERR_GENERAL), 故字段值改名 resultFlag。
                resultFlag = dataSet.get("result") 
                errMsg = dataSet.get("errMsg") 
                costMs = dataSet.get("costMs") 
                ipAddr = dataSet.get("ipAddr") 
                label = dataSet.get("label") 
                memo = dataSet.get("memo") 
                delFlag = dataSet.get("delFlag") 
                #data valid 检查

                if dataValidFlag:
                    #当前记录获取
                    recID = dataSet.get("recID", "")

                    tableName = comMysql.tablename_convertor_ch_audit_log()
                    currDataList = comMysql.query_ch_audit_log(tableName,recID)

                    if len(currDataList) == 1:
                        currDataSet = currDataList[0]

                        #权限或其他检查
                        if errCode == "B0": #

                            saveSet = {}

                            if actor != currDataSet.get("actor") and actor:
                                saveSet["actor"] = actor

                            if source != currDataSet.get("source") and source:
                                saveSet["source"] = source

                            if action != currDataSet.get("action") and action:
                                saveSet["action"] = action

                            if targetType != currDataSet.get("targetType") and targetType:
                                saveSet["targetType"] = targetType

                            if targetID != currDataSet.get("targetID") and targetID:
                                saveSet["targetID"] = targetID

                            if payloadDigest != currDataSet.get("payloadDigest") and payloadDigest:
                                saveSet["payloadDigest"] = payloadDigest

                            if resultFlag != currDataSet.get("result") and resultFlag:
                                saveSet["result"] = resultFlag

                            if errMsg != currDataSet.get("errMsg") and errMsg:
                                saveSet["errMsg"] = errMsg

                            if costMs != currDataSet.get("costMs") and costMs != None:
                                saveSet["costMs"] = costMs

                            if ipAddr != currDataSet.get("ipAddr") and ipAddr:
                                saveSet["ipAddr"] = ipAddr

                            if label != currDataSet.get("label") and label:
                                saveSet["label"] = label

                            if memo != currDataSet.get("memo") and memo:
                                saveSet["memo"] = memo

                            if delFlag != currDataSet.get("delFlag") and delFlag:
                                saveSet["delFlag"] = delFlag

                            if saveSet:
                                #saveSet["delFlag"] = "0"
                                saveSet["modifyID"] = loginID
                                saveSet["modifyYMDHMS"] = misc.getTime()

                                #保存数据
                                tableName = comMysql.tablename_convertor_ch_audit_log()
                                rtn = comMysql.update_ch_audit_log(tableName,recID,saveSet)
                                rtnData["rtn"] = str(rtn)

                                if rtn < 0:
                                    _LOG.warning(f"D: rtn:{rtn},saveSet:{saveSet}")
                                else:
                                    if _DEBUG:
                                        pass
                                        _LOG.info(f"D: rtn:{rtn}")

                                result = rtnData

                        else:
                            #BT
                            errCode = "BT"

                    else:
                        #CB
                        errCode = "CB"

                else:
                    #data invalid
                    errCode = "BA"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST查询代码
def funcAuditlogQry(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID

            #权限检查

            if errCode == "B0": #
                #获取查询输入参数
                recID = dataSet.get("recID", "")

                #houseID = dataSet.get("houseID", "")

                #★ 2026-09-22 手改(前端 P-12 审计日志筛选需要; 底层 query_ch_audit_log 已支持这些入参):
                #  透传 actor / action / result / source / targetType / targetID / ipAddr /
                #  beginYMDHMS / endYMDHMS / order。
                #  ★ ipAddr: 等值匹配(附录 B R-32, 2026-09-22 补)。
                #  ⚠ crudApi.py 生成区由 tools/mergeCrudApi.py 覆盖 —— 重跑生成器后本段需重做(见附录 B R-28)。
                actor = dataSet.get("actor", "")
                action = dataSet.get("action", "")
                #★ 注意: 本函数用 `result` 作为返回容器, 故筛选用 `resultFlag` 命名, 严禁覆盖 result
                resultFlag = dataSet.get("result", "")
                source = dataSet.get("source", "")
                targetType = dataSet.get("targetType", "")
                targetID = dataSet.get("targetID", "")
                ipAddr = dataSet.get("ipAddr", "")
                beginYMDHMS = dataSet.get("beginYMDHMS", "")
                endYMDHMS = dataSet.get("endYMDHMS", "")
                order = dataSet.get("order", "")

                forceFlashFlag = dataSet.get("forceFlashFlag",comGD._CONST_NO) #是否强制查询(刷新)标记

                searchOption = dataSet.get("searchOption")

                mode = dataSet.get("mode", "full")

                #limitNum = dataSet.get("limitNum",0)

                #权限检查/功能检测

                rightCheckFlag = True

                if rightCheckFlag:

                    #生成indexKey
                    indexKeyDataSet = {} #查询生成index的因素
                    if recID:
                        indexKeyDataSet["recID"] = recID
                    #★ 2026-09-22: 过滤条件必须进入 indexKey, 否则不同筛选组合会命中同一查询缓冲(取到别的组合的数据)
                    if actor:
                        indexKeyDataSet["actor"] = actor
                    if action:
                        indexKeyDataSet["action"] = action
                    if resultFlag:
                        indexKeyDataSet["result"] = resultFlag
                    if source:
                        indexKeyDataSet["source"] = source
                    if targetType:
                        indexKeyDataSet["targetType"] = targetType
                    if targetID:
                        indexKeyDataSet["targetID"] = targetID
                    if ipAddr:
                        indexKeyDataSet["ipAddr"] = ipAddr
                    if beginYMDHMS:
                        indexKeyDataSet["beginYMDHMS"] = beginYMDHMS
                    if endYMDHMS:
                        indexKeyDataSet["endYMDHMS"] = endYMDHMS
                    if order:
                        indexKeyDataSet["order"] = order
                    if searchOption:
                        indexKeyDataSet["searchOption"] = searchOption
                    if mode:
                        indexKeyDataSet["mode"] = mode

                    #if limitNum:
                        #indexKeyDataSet["limitNum"] = limitNum

                    sessionID = sessionIDSet.get("sessionID", "")
                    indexKey = genBufferIndexKey(CMD, sessionID, indexKeyDataSet) 
                    beginNum = int(dataSet.get("beginNum", comGD._DEF_BUFFER_DATA_BEGIN_NUM)) 
                    endNum = int(dataSet.get("endNum", comGD._DEF_BUFFER_DATA_END_NUM)) 

                    #判断数据是否在缓冲区:
                    if not(useQueryBufferFlag and chkBufferExist(indexKey)) or forceFlashFlag == comGD._CONST_YES:

                        if searchOption:
                            currDataList = []
                            tableName = comMysql.tablename_convertor_ch_audit_log()
                            allDataList = comMysql.query_ch_audit_log(tableName,mode = mode)
                            allowList = ["description", "label"] #筛选字段
                            serachResultSet = comFC.handleSearchOption(searchOption,allowList, allDataList)
                            if serachResultSet["rtn"] == "B0":
                                currDataList = serachResultSet.get("data", [])
                        else:
                            if recID:
                                tableName = comMysql.tablename_convertor_ch_audit_log()
                                currDataList = comMysql.query_ch_audit_log(tableName,recID,
                                                                           actor = actor,
                                                                           action = action,
                                                                           result = resultFlag,
                                                                           source = source,
                                                                           targetType = targetType,
                                                                           targetID = targetID,
                                                                           ipAddr = ipAddr,
                                                                           beginYMDHMS = beginYMDHMS,
                                                                           endYMDHMS = endYMDHMS,
                                                                           mode = mode,
                                                                           order = (order if order else "create"))
                            else:
                                #★ 2026-09-22 手改: 统一一次带过滤的查询(空值与 recID=0 由数据层自动跳过条件)
                                tableName = comMysql.tablename_convertor_ch_audit_log()
                                currDataList = comMysql.query_ch_audit_log(tableName,
                                                                           actor = actor,
                                                                           action = action,
                                                                           result = resultFlag,
                                                                           source = source,
                                                                           targetType = targetType,
                                                                           targetID = targetID,
                                                                           ipAddr = ipAddr,
                                                                           beginYMDHMS = beginYMDHMS,
                                                                           endYMDHMS = endYMDHMS,
                                                                           mode = mode,
                                                                           order = (order if order else "create"))

                        dataList = []

                        for currDataSet in currDataList:
                            aSet = {}

                            #需要把文件转移到public domain
                            #appendixFileID00 =  currDataSet.get("appendixFileID00", "")
                            #appendixFileID00 = getTempLocation(appendixFileID00, privateFlag = True)

                            #if mode == "full":
                                #aSet["houseID"] = currDataSet.get("houseID", "")

                            aSet["recID"] = currDataSet.get("recID","")
                            aSet["actor"] = currDataSet.get("actor","")
                            aSet["source"] = currDataSet.get("source","")
                            aSet["action"] = currDataSet.get("action","")
                            aSet["targetType"] = currDataSet.get("targetType","")
                            aSet["targetID"] = currDataSet.get("targetID","")
                            aSet["payloadDigest"] = currDataSet.get("payloadDigest","")
                            aSet["result"] = currDataSet.get("result","")
                            aSet["errMsg"] = currDataSet.get("errMsg","")
                            aSet["costMs"] = currDataSet.get("costMs","")
                            aSet["ipAddr"] = currDataSet.get("ipAddr","")
                            aSet["label"] = currDataSet.get("label","")
                            aSet["memo"] = currDataSet.get("memo","")
                            aSet["regID"] = currDataSet.get("regID","")
                            aSet["regYMDHMS"] = currDataSet.get("regYMDHMS","")
                            aSet["modifyID"] = currDataSet.get("modifyID","")
                            aSet["modifyYMDHMS"] = currDataSet.get("modifyYMDHMS","")
                            aSet["delFlag"] = currDataSet.get("delFlag","")

                            dataList.append(aSet)

                        #临时缓存机制,改进型, 2023/10/16
                        indexKey = putQuery2Buffer(indexKey, dataList) #存放数据到临时缓冲区去

                    rtnData = getQueryBufferComplte(indexKey, beginNum = beginNum,  endNum = endNum)

                    #rtnData["limitNum"] = limitNum

                    result = rtnData

                else:
                    errCode = "BT"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result




#auditlog(ch_audit_log) CRUD end


#----- CMD 注册表(依据 config/basicSettings.py::_CRUD_TITLES 派生, 与上方处理器同名同序) -----
#说明: key 为对外命令字({title}{add|del|modify|qry}), value 为生成器产出的处理器对象;
#      本段由 tools/mergeCrudApi.py 生成, 请勿手改。
CMD_MAP = {
    "layoutadd": funcLayoutAdd,
    "layoutdel": funcLayoutDel,
    "layoutmodify": funcLayoutModify,
    "layoutqry": funcLayoutQry,

    "platformadd": funcPlatformAdd,
    "platformdel": funcPlatformDel,
    "platformmodify": funcPlatformModify,
    "platformqry": funcPlatformQry,

    "renderjobadd": funcRenderjobAdd,
    "renderjobdel": funcRenderjobDel,
    "renderjobmodify": funcRenderjobModify,
    "renderjobqry": funcRenderjobQry,

    "artifactadd": funcArtifactAdd,
    "artifactdel": funcArtifactDel,
    "artifactmodify": funcArtifactModify,
    "artifactqry": funcArtifactQry,

    "accountadd": funcAccountAdd,
    "accountdel": funcAccountDel,
    "accountmodify": funcAccountModify,
    "accountqry": funcAccountQry,

    "publishrecordadd": funcPublishrecordAdd,
    "publishrecorddel": funcPublishrecordDel,
    "publishrecordmodify": funcPublishrecordModify,
    "publishrecordqry": funcPublishrecordQry,

    "mcptokenadd": funcMcptokenAdd,
    "mcptokendel": funcMcptokenDel,
    "mcptokenmodify": funcMcptokenModify,
    "mcptokenqry": funcMcptokenQry,

    "auditlogadd": funcAuditlogAdd,
    "auditlogdel": funcAuditlogDel,
    "auditlogmodify": funcAuditlogModify,
    "auditlogqry": funcAuditlogQry,
}

#===== auto-generated crud sections end =====


if __name__ == "__main__":
    pass
    print("crudApi CMD_MAP total:", len(CMD_MAP))  # noqa: F821  (生成区填充后才有定义)
