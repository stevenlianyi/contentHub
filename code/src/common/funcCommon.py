#!/usr/bin/env python3
#encoding: utf-8

#Filename: funcCommon.py  
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com  
#Date: 2019-08-02
#Description:   这个应用的通用函数

_VERSION="20260920"


import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

#import time
import hashlib
import uuid
import random
import pathlib

import re

import requests

from PIL import Image #图片

#import numpy as np

#global defintion/common var etc.
from common import globalDefinition as comGD

#code/decode functions
#from common import codingDecoding as comCD

#common functions(log,time,string, json etc)
from common import miscCommon as misc

# 身份证校验改为内置实现(见 _validateChinaResidentID), 不再依赖外部 id_validator 包。

#setting files
from config import basicSettings as settings
# from config import selfFileSettings as selfSettings

_processorPID = os.getpid()

#common function:
#错误消息表与统一返回封装已抽取到 common/errMsgCommon.py(SP1.5, 见 plan/chAPIPost分拆方案.md 7.3/7.4):
#  - 抽取原因: 错误消息段(约 430 行)与 funcCommon 其余部分零耦合, 且 contentHub 需新增 msgKey;
#  - 兼容策略: 此处 re-export, 既有引用方(25 个文件, 含 12 份生成产物)与 funcCommon 内部调用零改动;
#  - CI 约束 C4: 本文件不得再出现 CONST_ERROR_wordList 的定义(只允许这一处 re-export)。
from common.errMsgCommon import (  # noqa: F401
    CONST_ERROR_wordList,
    rtnMSG,
    getErrMsg,
    transOtherMsg,
    TRANS_OTHER_MSG,
)
#common function end


#common function:
#错误消息表(CONST_ERROR_wordList)与统一返回封装(rtnMSG/getErrMsg/transOtherMsg/TRANS_OTHER_MSG)
#已抽取到 common/errMsgCommon.py; re-export 见本文件顶部 import 段(SP1.5)。

def calTableYMD(beginYMDHM, endYMDHM):
    result = []
    if endYMDHM > beginYMDHM:
        beginY = int(beginYMDHM[0:4])
        beginM = int(beginYMDHM[4:6])
        endY = int(endYMDHM[0:4])
        endM = int(endYMDHM[4:6])

        for Y in range(beginY,  endY+1):
            if beginY == endY:
                endMonth = endM+1
                for M in range(beginM, endMonth):
                    tableYM = "%04d%02d" % (beginY, M) 
                    result.append(tableYM)
            else:
                if Y == endY:
                    beginMonth = 1
                    endMonth = endM+1
                elif Y == beginY:
                    beginMonth = beginM
                    endMonth = 13
                else:
                    beginMonth = 1
                    endMonth = 13
                for M in range(beginMonth, endMonth):
                    tableYM = "%04d%02d" % (Y, M) 
                    result.append(tableYM)
    return result


def calTableYear(beginYMDHM, endYMDHM):
    result = []
    if endYMDHM > beginYMDHM:
        beginY = int(beginYMDHM[0:4])
        endY = int(endYMDHM[0:4])

        for Y in range(beginY, endY + 1):
            tableY = "%04d" % (Y)
            result.append(tableY)
    return result

        
#把相近的两个地理位置数据做个简单迁移,避免显示重叠
def shiftPosition(lat1, lng1, lat2, lng2):
    dataType = misc.isStr(lat1)
    vectorScale = 10000
    newLat1 = float(lat1) * vectorScale
    newLng1 = float(lng1) * vectorScale
    newLat2 = float(lat2) * vectorScale
    newLng2 = float(lng2) * vectorScale
    if (int(newLat1) == int(newLat2)) and (int(newLng1) == int(newLng2)):
        shiftPosition = random.randint(0, 10) 
        newLat2 += shiftPosition
        shiftPosition = random.randint(0, 10) 
        newLng2 += shiftPosition
    if dataType:
        result = str(newLat1/vectorScale), str(newLng1/vectorScale), str(newLat2/vectorScale), str(newLng2/vectorScale)
    else:
        result = (newLat1/vectorScale), (newLng1/vectorScale), (newLat2/vectorScale), (newLng2/vectorScale)
    return result
    
    
#把list数据缩减到要求的长度以内,会根据要求的长度和实际长度,挑选一些值,抛弃一些值, 适合比较平滑的数据
def compressList(dataList, requestLen):
    result = []
    actualLen = len(dataList)
    compressRate = int((actualLen + requestLen -1)/requestLen)
    if (compressRate) >= 2:
        #两倍长度以上,直接压缩
        for i in range(0, actualLen, compressRate):
            result.append(dataList[i])
    else:
        result = dataList
    return result


def genDigest(d1,  d2 = "",  d3 = "",  d4 = "", d5 ="",method="md5"):
    # for var in (d1, d2, d3, d4, d5):
    #     if isinstance(var, str):
    #         var = var.encode("UTF-8") 
  
    tempStr = (d1+d2+d3+d4+d5+comGD._DEF_COMM_HASH_KEY_FOR_ALL).encode("UTF-8")
    if method=="md5":
        result = hashlib.md5(tempStr).hexdigest()
    else:
        result = hashlib.blake2b(tempStr, digest_size=16).hexdigest()
    # if isinstance(result, bytes):
    #     result = result.decode("UTF-8")
    return result 
    
    
# 通用字段校验 helpers
def _chkLength(data, lang, errKey, minLen=None, maxLen=None):
    """通用长度校验, 返回统一的 {'rtn','msg','data'} 结构。
    minLen/maxLen 为 None 表示不限制该边界。"""
    result = {"rtn": True, "msg": "", "data": {}}
    data = data or ""
    n = len(data)
    if (minLen is not None and n < minLen) or (maxLen is not None and n > maxLen):
        result["rtn"] = False
        result["msg"] = getErrMsg(errKey, lang=lang)
    return result


# 中国大陆 18 位居民身份证校验(GB 11643-1999): 内置实现, 不依赖外部包。
_CHINA_ID_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
_CHINA_ID_CHECKCODES = "10X98765432"

def _validateChinaResidentID(idno):
    """校验 18 位居民身份证号, 合法返回 dict, 非法返回 None。"""
    if not isinstance(idno, str):
        return None
    idno = idno.strip().upper()
    if len(idno) != 18 or not idno[:17].isdigit():
        return None
    # 校验位
    s = sum(int(idno[i]) * _CHINA_ID_WEIGHTS[i] for i in range(17))
    if _CHINA_ID_CHECKCODES[s % 11] != idno[17]:
        return None
    # 出生日期合法性
    try:
        import datetime
        datetime.date(int(idno[6:10]), int(idno[10:12]), int(idno[12:14]))
    except Exception:
        return None
    seq = int(idno[14:17])
    return {
        "birthday": idno[6:14],
        "address": idno[0:6],
        "length": "18",
        "sex": "M" if seq % 2 == 1 else "F",
    }


#check 身份证信息
def chkPersonalID(data, lang):
    result = {"rtn": True, "msg": "", "data": {}}
    # 失败即关闭(fail-closed): 不再用 bare except 静默放过非法证件
    rtnData = _validateChinaResidentID(data)
    if rtnData is None:
        result["rtn"] = False
        result["msg"] = getErrMsg("ERR_PID", lang=lang)
    else:
        result["data"]["birthday"] = rtnData["birthday"]
        result["data"]["address"] = rtnData["address"]
        result["data"]["length"] = rtnData["length"]
        result["data"]["sex"] = rtnData["sex"]
    return result


#check 姓名
def chkPersonalName(data, lang):
    return _chkLength(data, lang, "ERR_NAME",
                      comGD._DEF_PERSONAL_NAME_MIN_LENGTH,
                      comGD._DEF_PERSONAL_NAME_MAX_LENGTH)


#check TEl
def chkTelNo(data, lang):
    return _chkLength(data, lang, "ERR_TEL",
                      comGD._DEF_TEL_NO_MIN_LENGTH, None)


#check China mobile phone number
chinaMobilePhoneNoRule = re.compile(r'\(?1\d{2,3}[)-]?\d{7,8}')
def chkChinaMobileNo(data, lang = "EN"):
    result = {"rtn":True, "msg":"", "data":{}}
    m = chinaMobilePhoneNoRule.match(data)
    if m:
        result["rtn"] = True   
    else:
        result["rtn"] = False
        result["msg"] = getErrMsg("ERR_TEL", lang = lang)        
    return result


#check 城市信息
def chkCityName(data, lang):
    return _chkLength(data, lang, "ERR_CITY",
                      comGD._DEF_CITY_NAME_MIN_LENGTH,
                      comGD._DEF_CITY_NAME_MAX_LENGTH)


#check 区县信息
def chkAreaName(data, lang):
    return _chkLength(data, lang, "ERR_AREA",
                      comGD._DEF_AREA_NAME_MIN_LENGTH,
                      comGD._DEF_AREA_NAME_MAX_LENGTH)


#check 地址信息
def chkAddrName(data, lang):
    return _chkLength(data, lang, "ERR_ADDR",
                      comGD._DEF_ADDR_MIN_LENGTH, None)


#check 完整地址信息
def chkWholeAddr(data, lang):
    return _chkLength(data, lang, "ERR_WADDR",
                      comGD._DEF_ADDR_MIN_LENGTH, None)


#check 邮箱信息
def chkEmailAddr(data, lang):
    result = {"rtn":True, "msg":"", "data":{}}
    # 基本形态校验: 必须含 @ 与顶级域(含.), 且各部分不含空白与多余 @
    ruleStr = r'^[^@\s]+@[^@\s]+\.[^@\s]+$'
    if re.match(ruleStr, data):
        result["rtn"] = True
    else:
        result["rtn"] = False
        result["msg"] = getErrMsg("ERR_EMAIL", lang = lang)
    return result
    

CMDMap = {
    #用户注册
    comGD._DEF_PID_LABEL:chkPersonalID, 
    comGD._DEF_PERSONAL_NAME_LABEL:chkPersonalName, 
    comGD._DEF_TEL_LABEL:chkTelNo, 
    comGD._DEF_CITY_NAME_LABEL:chkCityName, 
    comGD._DEF_AREA_NAME_LABEL:chkAreaName, 
    comGD._DEF_WHOLE_ADDR_LABEL:chkWholeAddr, 
    comGD._DEF_EMAIL_LABEL:chkEmailAddr, 
    }

#check 地址,姓名,身份证号等的有消息
def chkDataValidataion(data, dataType, lang = "CN"):
    result = {"rtn":True, "msg":"", "data":{}}
    if dataType in CMDMap:
        result = CMDMap[dataType](data, lang)
    
    return result

def chkLoginIDPasswd(loginID, passwd):
    result = "B0"
    if loginID == "":
        result = "B1"
        if passwd == "":
            result = "B3"  # loginID为空 + 密码为空，优先报密码为空
    elif len(loginID) <= comGD._DEF_REDIS_USER_ID_LENGTH:
        result = "B2"
        if passwd == "":
            result = "B3"  # ID太短 + 密码为空，优先报密码为空
    elif passwd == "":
        result = "B3"
    return result


#模仿前端生成passwd方式
# 前端的passwd计算方法
# passwd(用户输入的)+loginID 然后再md5
def genLoginIDPasswd(loginID, passwd):
    result = ""
    
    newPasswd = passwd + loginID
    result = hashlib.md5(newPasswd.encode("utf-8")).hexdigest()

    return result

    
def getProvince(cityName):
    result = ""
    return result


#身份证脱敏处理
def PIDConvertor(personID):
    result = personID
    nLen = len(personID)
    if nLen >=comGD._DEF_PID_ID_MIN_LENGTH and nLen <= comGD._DEF_PID_ID_MAX_LENGTH:
        result = personID[0:12]+"XXXX"+personID[17:]
    return result


#处理搜索问题, 把keyword转换为 handleKeyword 所需要的格式
#空格分隔的是 or, + 分隔的是 and
def keyword2option(keyword):
    result = {}
    logic = comGD._DEF_GE_LOGIC_OR
    keyList = []
    if "+" in keyword:
        logic = comGD._DEF_GE_LOGIC_AND
        aList = keyword.split("+")
    else:
        logic = comGD._DEF_GE_LOGIC_OR
        aList = keyword.split(" ")
    for key in aList:
        key = key.strip()
        if key:
            keyList.append(key)

    result["logic"] = logic
    result["keyList"] = keyList
    return result


#处理搜索问题, 支持and, or, not 和全局搜索
#ruleSet 格式
#{"logic":"AND","keyList":["\u5c71\u4e1c\u7701","\u6dc4\u535a\u5e02"]}
#allowlList: ["projectName","rules"]
def handleKeyword(ruleSet,allowList,dataList):
    result = {"rtn":"B0", "data":[]} 
    try:
        rtnData = []
        logic = (ruleSet.get("logic", "")).upper()
        keyList = ruleSet.get("keyList",[])
        if logic == comGD._DEF_GE_LOGIC_AND:
            ruleNum = len(keyList)
            if ruleNum > 0:
                for data in dataList:
                    aList = []
                    for dictKey in allowList:
                        val = data.get(dictKey)
                        try:
                            val = misc.jsonLoads(val)
                        except:
                            pass
                        if isinstance(val,list):
                            val = ",".join(val)
                        if isinstance(val,bytes):
                            val = val.decode()
                        aList.append(val)
                    strT = " ".join(aList) 
                    ruleCount = 0
                    for key in keyList:
                        if key in strT:
                            ruleCount += 1
                        else:
                            break
                    if ruleCount == ruleNum:
                        rtnData.append(data)
                result["data"] = rtnData
            else:
                result["rtn"] = "BK"
        elif logic == comGD._DEF_GE_LOGIC_OR:
            for data in dataList:
                aList = []
                for dictKey in allowList:
                    val = data.get(dictKey)
                    try:
                        val = misc.jsonLoads(val)
                    except:
                        pass
                    if isinstance(val,list):
                        val = ",".join(val)
                    if isinstance(val,bytes):
                        val = val.decode()
                    aList.append(val)
                strT = " ".join(aList) 
                for key in keyList:
                    if key in strT:
                        rtnData.append(data)
            result["data"] = rtnData
        else:
            pass
    except:
        result["rtn"] = "BK"
    return result


#处理搜索问题, 支持and, or, not 和全局搜索
#ruleSet 格式
#"searchOption":{"logic":"AND","optionList":[{"province":"\u5c71\u4e1c\u7701"},{"city":"\u6dc4\u535a\u5e02"},{"area":"\u6dc4\u5ddd\u533a"}]}
def handleSearchOption(ruleSet, allowList, dataList):
    result = {"rtn":"B0", "data":[]}
    hitKeyFlag = False
    try:
        rtnData = []
        logic = (ruleSet.get("logic", "")).upper()
        if logic == comGD._DEF_GE_LOGIC_AND:
            optionList = ruleSet.get("optionList", [])
            ruleNum = len(optionList)
            if ruleNum > 0:
                for data in dataList:
                    ruleCount = 0
                    for rule in optionList:
                        for ruleKey, ruleVal in rule.items():
                            if ruleKey in allowList:
                                hitKeyFlag = True
                                dataVal = data.get(ruleKey)
                                if ruleVal in dataVal:
                                    ruleCount += 1
                    if ruleCount == ruleNum:
                        rtnData.append(data)
                result["data"]  = rtnData
            else:
                result["rtn"] = "BK"
        elif logic == comGD._DEF_GE_LOGIC_OR:
            optionList = ruleSet.get("optionList", [])
            ruleNum = len(optionList)
            if ruleNum > 0:
                for data in dataList:
                    ruleCount = 0
                    for rule in optionList:
                        for ruleKey, ruleVal in rule.items():
                            if ruleKey in allowList:
                                hitKeyFlag = True
                                dataVal = data.get(ruleKey)
                                if ruleVal in dataVal:
                                    ruleCount = ruleNum
                                    break
                        if ruleCount == ruleNum:
                            break
                    if ruleCount == ruleNum:
                        rtnData.append(data)
                result["data"]  = rtnData
            else:
                result["rtn"] = "BK"
        elif logic == comGD._DEF_GE_LOGIC_NOT:
            optionList = ruleSet.get("optionList", [])
            ruleNum = len(optionList)
            if ruleNum > 0:
                for data in dataList:
                    ruleCount = 0
                    for rule in optionList:
                        for ruleKey, ruleVal in rule.items():
                            if ruleKey in allowList:
                                hitKeyFlag = True
                                dataVal = data.get(ruleKey)
                                if ruleVal not in dataVal:
                                    ruleCount += 1
                    if ruleCount == ruleNum:
                        rtnData.append(data)
                result["data"]  = rtnData
            else:
                result["rtn"] = "BK"
        elif logic == comGD._DEF_GE_LOGIC_ALL:
            option = ruleSet.get("option")
            for data in dataList:
                if option:
                    for dataKey,  dataVal in data.items():
                        if dataKey in allowList:
                            hitKeyFlag = True
                            if option in dataVal:
                                rtnData.append(data)
                                break
                else:
                    rtnData.append(data)
                    #result["rtn"] = "BK"
            result["data"]  = rtnData
            
        if hitKeyFlag == False:
            #条件不在allowList
            result["data"]  = dataList
    except:
        result["rtn"] = "BK"
    return result
     
    
def chkIsRegisterUser(roleName):
    result = False
    if roleName in ["customer","operator", "manager", "administrator"]:
        result = True
    return result

def chkIsCustomer(roleName):
    result = False
    if roleName in ["customer"]:
        result = True
    return result

def chkIsOperator(roleName):
    result = False
    if roleName in ["administrator", "manager", "operator"]:
        result = True
    return result

def chkIsOperatorOnly(roleName):
    result = False
    if roleName in ["operator"]:
        result = True
    return result

def chkIsManager(roleName):
    result = False
    if roleName in ["administrator", "manager"]:
        result = True
    return result
    

def getExpireTime(roleName):
    result = comGD._DEF_OPERATOR_SESSION_EXPIRE_TIME
    if roleName in ["owner"]:
        result = comGD._DEF_USER_SESSION_EXPIRE_TIME
    return result
        

#文件系统请求方式        
def fileServerRequest(serverName, dataSet):
    result = {}
    try:
        url = settings.FILE_SERVER_URL.get(serverName)
        header = {"content-type":"application/json"}
        payload = misc.jsonDumps(dataSet)
        r = requests.post(url, data=payload, headers = header) 
        if r.status_code == requests.codes.ok:
            result =misc.jsonLoads(r.text)
    except:
        pass
        
    return result
    

def getRandomList(listNum,  maxNum):
    result = []
    selectList = []
    count = 0
    num = 0 
    if maxNum > 1:
        while True:
            nT1 = random.randint(0, maxNum-1)
            if nT1 not in selectList:
                selectList.append(nT1) #随机内容
                num += 1
            count += 1
            if (num >= listNum) or (count > (listNum *10)):
                break
    elif maxNum == 1:
        selectList = [0]
    result = selectList
    return result
    

def convertRandomList(dataList):
    result = []
    nLen = len(dataList)
    selectList = getRandomList(nLen, nLen)
    for i in selectList:
        result.append(dataList[i])
    return result 
    
    
def getRandomDrop(molecules, denominators):
    result = True
    nT1 = random.randint(0, denominators)
    if nT1 <= molecules: #随机抛弃1/4内容
        result = True
    else:
        result = False
    return result
    
  
#递归遍历某个目录的所有文件
def getFilePathList(dirPath):
    """
    递归遍历目录，返回所有路径的简单列表
    """
    result = []
    
    for item in os.listdir(dirPath):
        itemPath = os.path.join(dirPath, item)
        result.append(itemPath)  # 添加当前项
        
        if os.path.isdir(itemPath):
            # 递归遍历子目录并合并结果
            result.extend(getFilePathList(itemPath))
    
    return result


def getStructuredDirInfo(dirPath):
    """
    递归遍历目录，返回结构化的结果
    
    Returns:
        dict: 包含文件和目录信息的字典
    """
    result = {
        'files': [],
        'directories': []
    }
    
    for item in os.listdir(dirPath):
        itemPath = os.path.join(dirPath, item)
        
        if os.path.isdir(itemPath):
            # 添加目录信息
            dirInfo = {
                'path': itemPath,
                'name': item,
                'type': 'directory'
            }
            result['directories'].append(dirInfo)
            
            # 递归遍历子目录并合并结果
            sub_result = getStructuredDirInfo(itemPath)
            result['files'].extend(sub_result['files'])
            result['directories'].extend(sub_result['directories'])
        else:
            # 添加文件信息
            fileInfo = {
                'path': itemPath,
                'name': item,
                'type': 'file',
                'size': os.path.getsize(itemPath) if os.path.exists(itemPath) else 0
            }
            result['files'].append(fileInfo)
    
    return result


#获取某个目录下的文件名
def getFileNameList(dirName, extName=None,extNameList=[]):
    result = []
    if extName:
        extNameList.append(extName)
    # 遍历所有文件和目录（包括子目录）
    dirInfo = getStructuredDirInfo(dirName)
    fileInfoList = dirInfo.get("files",[])
    for fileInfo in fileInfoList:
        filePath = fileInfo.get("path")
        validFlag = False
        if extNameList:
            for extName in extNameList:
                if filePath.endswith(extName):
                    validFlag = True
                    break
        else:
            validFlag = True
        if validFlag:
            result.append(filePath)
    return result


#获取某个目录下的子目录名称
def getDirNameList(dirName):
    result = []
    for root,  dirs,  files in os.walk(dirName):
        for dir in dirs:
            currDirName = os.path.join(root, dir)
            currDirName = pathlib.Path(currDirName).as_posix()
            result.append(currDirName)
    return result


#建立目录
def createDir(dirName):
    if not os.path.exists(dirName):
        os.makedirs(dirName)


#生成临时文件名
def genTempFileName(extName = "",prefix="",tail="",body=""):
    result = ""
    tempDir = os.path.join(settings.LOCAL_FILE_SERVER_BASE,  "output")
    createDir(tempDir)

    if body:
        fileBodyName = prefix + "_" + body + "_" + tail 
    else:
        fileBodyName = str(uuid.uuid4()).replace("-","") 
    fileName = fileBodyName

    while True:
        tempFileName = fileName + extName
        tempFileName = os.path.join(tempDir, tempFileName)
        tempFileName = pathlib.Path(tempFileName).as_posix()
        if os.path.exists(tempFileName) == False:
            result = tempFileName
            break
        fileName = fileBodyName + "_" + str(random.randint(1000,9999))
    return result


#生成相应的url
def genTempFileUrl(filePath):
    result = ""
    baseUrl = settings.LOCAL_FILE_SERVER_PATH +"output/"
    basedir,fileName = os.path.split(filePath)
    result = baseUrl + fileName
    return result
    
    
def downloadFile(url,  fileName):
    result = 0
    r = requests.get(url)
    if r.status_code == 200:
        try:
            with open(fileName, "wb") as hFile:
                hFile.write(r.content)
            result = os.path.getsize(fileName)
        except:
            pass
    return result
    

#向ylwz文件服务器上传文件,返回的是一个含url的字典
def sendFile(filePath, description = "file"):
    result = {}
    
    url = settings.FILE_UPLOAD_URL
    try:
        #fileName = os.path.basename(filePath)

        with open(filePath, 'rb') as f:
            multipart_form_data = {
                'file': (filePath, f),
                'description': ('', str(description)),
            }

            r = requests.post(url, files=multipart_form_data)
        if r.status_code == requests.codes.ok:
            rtnData = misc.jsonLoads(r.text)
        
            result = rtnData
        
    except Exception as e:
        pass

    return result


#copy file to private network, and change the url, new version
def save2newLocation(fileID,  objectName=None, requestType = "", prefix = "", 
                     privateFlag = False, compressFlag = comGD._CONST_NO):
    result = fileID
    try:

        fileInfoData = {}

        fileInfoData["CMD"] = "F0A0"
        fileInfoData["serverName"] = settings._SYS_SERVER_NAME

        fileInfoData["fileID"] = fileID
        if objectName:
            fileInfoData["objectName"] = objectName
        if requestType:
            fileInfoData["requestType"] = requestType
        if prefix:
            fileInfoData["prefix"] = prefix
        fileInfoData["privateFlag"] = privateFlag
        fileInfoData["compressFlag"] = compressFlag

        fileInfoData["YMDHMS"] = misc.getTime()

        fileInfoData["token"] = genDigest(settings.GEN_DIGIST_KEY, fileInfoData["CMD"], fileInfoData["YMDHMS"])

        rtnData = fileServerRequest(settings._SYS_SERVER_NAME, fileInfoData)
        if rtnData:
            if rtnData.get("errCode") == "B0":
                fileUrl = rtnData.get("fileUrl")
                if fileUrl:
                    result = fileUrl
                pass

    except Exception as e:
        errMsg = f"PID: {_processorPID},errMsg:{str(e)}"
        # _LOG.error(f"{errMsg}, {traceback.format_exc()}")

    return result


#把文件ID转成临时url
def getTempLocation(fileID, privateFlag = True,localAccess = False,localAddress = False,targetFileName="",sourceServerAddr="",urlResult=True):
    result = fileID
    try:
        serverName = settings._SYS_SERVER_NAME

        fileInfoData = {}
        fileInfoData["CMD"] = "F7A0" #把文件转存到本地临时目录
        fileInfoData["fileID"] = fileID
        fileInfoData["fileSystem"] = settings.FILE_SYSTEM_MODE
        fileInfoData["privateFlag"] = privateFlag
        fileInfoData["localAccess"] = localAccess
        fileInfoData["localAddress"] = localAddress
        fileInfoData["targetFileName"] = targetFileName
        fileInfoData["sourceServerAddr"] = sourceServerAddr

        fileInfoData["YMDHMS"] = misc.getTime()
        fileInfoData["token"] = genDigest(settings.GEN_DIGIST_KEY, fileInfoData["CMD"], fileInfoData["YMDHMS"])
        rtnSet = fileServerRequest(serverName, fileInfoData)
        if rtnSet:
            if rtnSet.get("CMD")[2:4] == "B0":
                if urlResult:
                    result = rtnSet.get("fileUrl")
                else:
                    result = rtnSet.get("fileUrl")
                if result == None:
                    result = ""

        if _DEBUG:
            _LOG.info(f"DEBUG: getTempLocation, FILE_SYSTEM_MODE:[{FILE_SYSTEM_MODE}] fileID:[{fileID}] result:[{result}]")
    
    except Exception as e:
        errMsg = f"PID: {_processorPID},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

    return result


def currencyConvert(currency):
    result = {}
    if currency not in comGD._DEF_CURRENCY_UNITS:
        currency = comGD._DEF_CURRENCY_DEFAULT
    result["unit"] = comGD._DEF_CURRENCY_UNITS[currency]["unit"]
    result["rate"] = comGD._DEF_CURRENCY_UNITS[currency]["rate"]
    return result


def writeData2csv(dataList):
    result = ("","")
    filePath = genTempFileName(".csv")
    fileUrl = genTempFileUrl(filePath)
    dataLen = len(dataList)
    if dataLen > 0:
        #generate title
        data = dataList[0]
        keys = data.keys()
        strT = ",".join(keys)
        #write to file
        with open(filePath,"w",encoding = "utf-8") as hFile:
            hFile.write(strT)
            hFile.write("\n")
            for data in dataList:
                aList = []
                for key in keys:
                    val = str(data[key])
                    # 如果值包含逗号、引号或换行，用双引号包裹并转义内部引号
                    if ',' in val or '"' in val or '\n' in val:
                        val = '"' + val.replace('"', '""') + '"'
                    aList.append(val)
                strT = ",".join(aList)
                hFile.write(strT)
                hFile.write("\n")
        result = (filePath,fileUrl)
    return result


def date2YMD(dateString):
    result = dateString
    aList = dateString.split("-")
    YMDList = []
    for val in aList:
        val = int(val)
        YMDList.append(val)
    if len(YMDList) == 3:
        result = f"{YMDList[0]:04d}{YMDList[1]:02d}{YMDList[2]:02d}"
    return result


def YMD2Date(YMD):
    result = YMD
    if len(YMD) == 8:
        result = YMD[0:4] + "-" + YMD[4:6] + "-" + YMD[6:8]
    return result


'''
1mb = 1 month before
1ma = 1 month after
'''
# 1mb=1 month before
def decodeRequireDate(requireDate):
    beforeAfterFlag = None
    YMD = None
    requireDate = requireDate.lower()
    try:
        if len(requireDate) >= 3:
            beforeAfterChar = requireDate[-1]
            if beforeAfterChar == "b":
                beforeAfterFlag = ">="
            else:
                beforeAfterFlag = "<="
            unitChar = requireDate[-2]
            if unitChar == "m":
                days = 30
            elif unitChar == "y":
                days = 365
            else:
                days = 1
            val = int(requireDate[0:-2])
            actualDays = val * days               
            YMD = misc.getPassday(actualDays)
    except:
        pass
    return beforeAfterFlag, YMD


'''
文件大小单位换算
'''
def fileSize2text(size):
    result = 0
    try:
        size = float(size)
        units = ["B","KB","MB","GB","TB","PB"]
        unitSize = 1024
        for i in range(len(units)):
            if (size/unitSize) < 1:
                result = "%.1f%s"% (size,units[i])
                break
            size = size/unitSize
    except:
        pass
    return result


def calcQuarterByDate(dateType,beginDate,endDate):
    result = {}
    result["EN"] = []
    result["CN"] = []
    result["quarterNum"] = 0
    try:
        if dateType == "YMD":
            beginYM = beginDate[0:6]
            endYM = endDate[0:6]
        else:
            beginYM = beginDate
            endYM = endDate
        beginY = int(beginYM[0:4])
        beginM = int(beginYM[4:6])
        endY = int(endYM[0:4])
        endM = int(endYM[4:6])
        currY = beginY
        currM = beginM
        quarterNum = 0
        while True:
            if currM >= 1 and currM <= 3:
                currQ = 1
                currCQ = "一"
            elif currM >= 4 and currM <= 6:
                currQ = 2
                currCQ = "二"
            elif currM >= 7 and currM <= 9:
                currQ = 3
                currCQ = "三"
            else:
                currQ = 4
                currCQ = "四"
            currYQ = str(currY) + str(currQ)
            if currYQ not in result["EN"]:
                quarterNum += 1
                currCYQ = f"{currY}年度第{currCQ}季度"
                result["EN"].append(currYQ)
                result["CN"].append(currCYQ)
            if currY == endY and currM == endM:
                break
            currM += 1
            if currM > 12:
                currM = 1
                currY += 1
        result["quarterNum"] = quarterNum
    except Exception as e:
        errMsg = f"PID: {_processorPID},errMsg:{str(e)}"
        # _LOG.error(f"{errMsg}, {traceback.format_exc()}")

    return result


#根据模板和{}占位符生成字符串
def dynamicFormat(template, dataList):
    result = ""
    # 统计占位符数量（注意：需确保模板无转义字符）
    try:
        placeHoldersNum = template.count('{}')
        if len(dataList) == placeHoldersNum:
            result = template.format(*dataList)
    except Exception as e:
        errMsg = f"PID: {_processorPID},errMsg:{str(e)}"
        # _LOG.error(f"{errMsg}, {traceback.format_exc()}")

    return result


#根据keyList 检查data中是否包含keyList中的所有key, 而且符合key 的顺序
def ifMatchKeys(data, keyList):
    result = False
    try:
        currString = data
        count = len(keyList)
        for key in keyList:
            pos = currString.find(key)
            if pos >= 0:
                pos = currString.find(":")
                if pos >=0:
                    pos += 1
                    currString = currString[pos:]
                count -= 1
            else:
                break
        if count == 0:
            result = True
    except Exception as e:
        errMsg = f"PID: {_processorPID},errMsg:{str(e)}"
        # _LOG.error(f"{errMsg}, {traceback.format_exc()}")
    return result


#检查数据是否来源于可信domain
def chkTrustDomain(url):
    result = False
    try:
        url = str(url)
        if url.startswith("http://") or url.startswith("https://"):
            for trustDomain in settings.TRUST_DOMAIN_LIST:
                if url.startswith(trustDomain):
                    result = True
                    break
        else:
            result = True
    except Exception as e:
        errMsg = f"PID: {_processorPID},errMsg:{str(e)}"
        # _LOG.error(f"{errMsg}, {traceback.format_exc()}")
    return result


urlPattern = re.compile(r'(?i)(<script|<iframe|<object|<embed|javascript:|vbscript:|data:|active\w+)', re.IGNORECASE)
def isSafeUrl(url):
    global urlPattern
    result = False
    try:
        # 定义一个正则表达式，用于匹配可能的注入模式
        # 这个正则表达式可能需要根据你的具体需求进行调整
        
        # 使用正则表达式检查URL
        if not urlPattern.search(url):
            result = True
              # URL不包含潜在的注入模式，安全
    except Exception as e:
        errMsg = f"PID: {_processorPID},errMsg:{str(e)}"
    return result  # URL看起来是安全的


#上传内容格式检查, 主要是是否含html和其他url等
def uploadContentCheck(content):
    result = True
    try:
        if isinstance(content,str):
            if content:
                result = isSafeUrl(content)

    except Exception as e:
        errMsg = f"PID: {_processorPID},errMsg:{str(e)}"
        # _LOG.error(f"{errMsg}, {traceback.format_exc()}")
    return result


def list2dict(keyList,valList):
    result = {}
    try:
        keyLen = len(keyList)
        valLen = len(valList)
        if keyLen == valLen:
            for i in range(keyLen):
                key = keyList[i]
                val = valList[i]
                result[key] = val
    except:
        pass
    return result


#用于取出多重字典中的所有键，如果遇到列表则忽略
def extractDictKeys(data):
    """
    递归提取字典中的所有键，遇到列表则忽略
    参数:
        data: 输入数据（字典或包含字典的结构）
    返回:
        set: 包含所有键的集合
    """
    result = []
    try:
        keys = set()
        if isinstance(data, dict):
            for key, value in data.items():
                keys.add(key)
                # 递归处理字典值
                keys.update(extractDictKeys(value))
        elif isinstance(data, list):
            # 忽略列表，不进行处理
            pass
        # 其他类型（如字符串、数字等）不需要处理
        result = list(keys)
    except:
        pass
    
    return result


#把欧洲格式的小数点","转换为标准的浮点数
def euroFloat(val):
    result = 0.0
    try:
        newVal = val.replace(",",".")
        result = float(newVal)
    except:
        pass
    return result


#生成外部会话ID, 格式: YLWZ_<UUID>
def genExtSessionID():
    result = ""
    try:
        currUUID = str(uuid.uuid4()).replace("-","") 
        result = "ylwz_" + currUUID
    except:
        pass
    return result


#判断某天是否公共假期
'''
本地保存一个文件, 这样可以, 一天清理一次, 主要是处理三天前的数据
首先判断本地是否保存了数据, 然后考虑是否需要从网络更新
'''
_localIsPublucHolidayFileName = "publicholiday.json"
def isPublicHoliday(YMD):
    result = False
    currYMDHMS = misc.getTime()
    saveData = misc.loadJsonData(_localIsPublucHolidayFileName,"dict")
    if saveData:
        saveFlag = False
        saveYMDHMS = saveData.get("YMDHMS","")
        holidayInfoData = saveData.get("data",{})
        if saveYMDHMS[0:8] != currYMDHMS[0:8]:
            #日期不同需要清理数据
            passYMDHMS = misc.getPassday(3) + "000000"
            currKeys = list(holidayInfoData.keys())
            for key in currKeys:
                if key < passYMDHMS:
                    del holidayInfoData[key]
                    saveFlag = True
                    saveData["YMDHMS"] = currYMDHMS
        if YMD in holidayInfoData:
            result = holidayInfoData[YMD]["isHoliday"]
        else:
            #调用外部接口
            holidayInfo = getPublicHolidayInfo(YMD)
            if holidayInfo:
                saveData["data"][YMD] = holidayInfo
                result = holidayInfo.get("isHoliday")
                saveFlag = True

        if saveFlag:
            misc.saveJsonData(_localIsPublucHolidayFileName, saveData,indent = 2)
    else:
        #调用外部接口
        holidayInfo = getPublicHolidayInfo(YMD)
        if holidayInfo:
            saveData = {}
            saveData["data"] = {}
            saveData["YMDHMS"] = currYMDHMS
            result = holidayInfo.get("isHoliday")
            saveData["data"][YMD] = holidayInfo
            misc.saveJsonData(_localIsPublucHolidayFileName, saveData,indent = 2)

    return result


#利用外部接口获取公共假日信息
'''
利用外部的接口
https://github.com/Haoshenqi0123/holiday
https://api.haoshenqi.top/holiday?date=2023-10-01
[{
        "date": "2019-05-01",
        "year": 2019,
        "month": 5,
        "day": 1,
        "status": 3
    }]
status: 0普通工作日1周末双休日2需要补班的工作日3法定节假日
'''
def getPublicHolidayInfo(YMD):
    result = {"isHoliday":True}
    try:
        url = "http://api.haoshenqi.top/holiday"
        currDate = YMD[0:4] + "-" + YMD[4:6] + "-" + YMD[6:8]
        header = {"content-type":"application/json"}
        url = url + "?date=" + currDate
        r = requests.get(url,headers = header) 
        if r.status_code == requests.codes.ok:
            dataList = misc.jsonLoads(r.text)
            if dataList:
                currDataSet = dataList[0]
                status = currDataSet.get("status")
                result["status"] = status
                result["date"] = currDataSet.get("date")
                if status == 0:
                    result["isHoliday"] = False
                else:
                    result["isHoliday"] = True
    except:
        pass

    return result


#mindgram function begin

#生成缩略图
def genThumbnailImage(imgPath,newPath,newSize):
    result = False
    try:
        img = Image.open(imgPath)
        
        # 如果图片有透明通道（RGBA模式），转换时保留
        if img.mode == 'RGBA':
            # 缩略图方法会保持模式不变
            img.thumbnail(newSize, Image.Resampling.LANCZOS)
            # 保存时明确指定PNG格式（或其他支持透明的格式）
            img.save(newPath, format='PNG')
        else:
            img.thumbnail(newSize, Image.Resampling.LANCZOS)
            img.save(newPath)
            
        result = True
    except:
        pass
    return result


def genThumbnailName(filepath,addtionStr="_thumb"):
    result = ""
    try:
        # directory = os.path.dirname(filepath)  # /data/v1
        basename = os.path.basename(filepath)  # test.txt
        # 分离文件名和扩展名
        name, ext = os.path.splitext(basename)  # test, .txt
        result = f"{name}{addtionStr}{ext}"  # test_thumb.txt
    except:
        pass
    return result


def convertFilePath(filepath):
    """
    将文件路径转换为缩略图路径
    例如: /data/v1/test.txt -> /data/v1/text_thumb.txt
    """
    result = ""
    directory = os.path.dirname(filepath)  # /data/v1
    
    # 构造新文件名
    new_basename = genThumbnailName(filepath)  # test_thumb.txt
    
    # 组合新路径
    result = os.path.join(directory, new_basename)
    result = pathlib.Path(result).as_posix()
    return result


def countYPatterns(s):
    """
    计算字符串中连续'Y'的最大个数，以及从最后一个'Y'开始向后的'Y'个数
    
    参数:
        s: 输入的字符串
    
    返回:
        tuple: (最大连续Y的个数, 从最后Y开始向后的Y个数)
    """
    if not s:
        return 0, 0, 0
    
    max_consecutive = 0
    current_consecutive = 0
    totalY= 0 
    
    # 计算最大连续Y的个数
    s = s.upper()
    for char in s:
        if char == 'Y':
            current_consecutive += 1
            totalY += 1
            max_consecutive = max(max_consecutive, current_consecutive)
        else:
            current_consecutive = 0
    
    # 从最后一个Y开始向后计算Y的个数
    count_from_last = 0
    # 从字符串末尾向前遍历
    for char in reversed(s):
        if char == 'Y':
            count_from_last += 1
        else:
            break  # 遇到非Y就停止
    
    return max_consecutive, totalY, count_from_last


#mindgram function end


def test():
    # 示例
    filePath = "funcCommon.py"
    rtnData = sendFile(filePath)
    fileID = rtnData.get("fileUrl","")
    if fileID:
        rtn = save2newLocation(fileID,filePath)

    pass

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pass
        import platform
        if platform.system()=='Linux':
            import pdb
            pdb.set_trace()
    
    test()
