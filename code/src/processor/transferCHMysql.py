#! /usr/bin/env python3
#encoding: utf-8

#Filename: transferCHMysql.py 
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com  
#Date: 2026-09-20
#Description:   contentHub 后台异步落库处理器: 消费 Redis 队列(comGD._DEF_CH_MSG_QUEUE_MYSQL_TITLE,
#               由 main/subfunc/accountApi.py::_saveMsg2Queue 投递)中的 registration / login 报文,
#               取账号服务(A3A0)用户数据后同步写入 USER_BASIC; 另承接长耗时查询结果的 Redis 缓冲转存
#               (funcPutDataBufferList)。
#
#移植与改造说明(自 museum transferMuseumMysql.py 移植):
#  1) USERBASIC 段: 写入字段与 contentHub 的 USER_BASIC 表逐列对齐
#     (定义文件 database/userBasic.txt, 建表 common/mysqlCommon.createUserBasic(), 共 45 列;
#      读写一律走 common/mysqlCommon 的 user family, 不自拼 SQL);
#  2) mindgram 业务域(mgmoodpostadd / emojisetadd / emojisetdel / emojisetmodify)已整体删除 ——
#     contentHub 不承载该域, 其依赖的 mgmood/mgWeeklyReel/mgEmoji* 数据层与配置项在本工程均不存在;
#  3) 不再引用本工程未定义的配置项(REGISTRATION_NOTIFICATION_USER_LIST 见其定义处注释)。

_VERSION="20260920"

_DEBUG=True

import os
import sys
from typing import Any
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)

import traceback
import copy

#global defintion/common var etc.
from common import globalDefinition as comGD

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#common functions(database operation)
from common import redisCommon as comDB

from common import mysqlCommon as comMysql

#账号服务 HTTP 客户端: 公共层唯一出口(组包 / 超时 / 异常收敛均在其内), 本文件不再自建 HTTP 调用
from common import accountClient as comAcc

# from common import whooshCommon as comSearch

#注: 文件存储一律经 common/fileStorageCommon.py 门面(红线 R2: 配置驱动, 禁厂商分支),
#    故本文件不 import 任何厂商适配器(aliyunOSS / tencentCOS / selfFileCommon)

# from common import aliyunSMS as SMS

#from common import codingDecoding as comCD

#setting files
# from config import settings as settings
from config import basicSettings as settings


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    _LOG = misc.setLogNew("TRANS", comGD._DEF_LOG_TRANS_MYSQL_LOG)

systemVersion = str(sys.version_info.major) + "." + str(sys.version_info.minor ) + "." + str(sys.version_info.micro )
_LOG.info(f"PID:{_processorPID}, python version:{systemVersion}, main code version:{_VERSION}")


# comSearchWhooshFlag = settings.comSearchWhooshFlag

#注册通知用户清单: museum 在 settings 中登记该配置项并据此发短信, contentHub 未移植短信通知能力,
#本工程 basicSettings 亦未定义该项 —— 故以空表兜底(避免导入期 AttributeError);
#后续如需恢复注册通知, 在 config/basicSettings.py 中补上 REGISTRATION_NOTIFICATION_USER_LIST 即可生效。
REGISTRATION_NOTIFICATION_USER_LIST = getattr(settings, "REGISTRATION_NOTIFICATION_USER_LIST", [])


# command part begin

#原 museum 的文件处理段(urlSaveFileUpload / save2newLocation / generateThumbnail /
#save2newLocationWithThumbail / delPermanentFile / getTempLocation)已整体删除, 原因:
#  1) 该段按 FILE_SYSTEM_MODE 硬编码 FASTDFS/ALIOSS/TENCENT/NGINX 四路分支, 违反红线 R2
#     (contentHub 的文件后端为 ALIOSS/TENCENT/SELFFILE, 且「一律经 fileStorageCommon 门面」),
#     且缺 SELFFILE 分支, 在 local/home 环境会静默返回原 fileID;
#  2) 该段依赖 museum 的 Redis 文件登记表(comDB.getFileInfo/delFileInfo), contentHub 不采用;
#  3) 本文件在 contentHub 无任何调用方(仅本 processor 自身), 属死代码。
#
#后续本 processor 如需文件操作, 按计划 §3.3.6「模式B: 进程内直连」(批处理/后台 worker)调用:
#  from common import fileStorageCommon as comFS
#    comFS.saveFile(localPath, objectName, privateFlag, bucketCode)      # 上传, 返回 fileID
#    comFS.saveWithThumbnail(localPath, objectName, privateFlag)         # 上传 + 本进程 PIL 缩略图
#    comFS.delFile(fileID, privateFlag, bucketCode)                      # 删除
#    comFS.getTempLocation(fileID, privateFlag, localAccess, ...)        # fileID -> URL(支持多桶)
#出参 fileID 转 URL 一律经 common/chCommon.py::fillFileUrls; Web 同步请求侧另可用「模式A」
#(common/funcCommon.py::save2newLocation / getTempLocation, 走文件服务 F0A0/F7A0)。


#user relate begin

#取账号服务用户信息(A3A0), 供写入 USER_BASIC 使用
def getUserInfo(loginID,sessionID):
    """账号服务 A3A0 取用户信息。

    ★ 与 museum 的差异(本工程口径):
      1) HTTP 调用统一走公共层 common/accountClient.py(唯一出口, 带 30s 超时与异常收敛),
         不再自建 requests.post 直连(原实现无超时、except 空吞、且与 accountSvcClient 重复);
      2) roleName 归一: 不在 settings.ROLE_CMD_LIST 内的角色回落 settings.accountServiceDefaultRoleName
         (与 subfunc/accountSvcClient.py::normalizeRoleName 同口径 —— 本层为 processor, 不反向 import subfunc);
      3) 性别口径: USER_BASIC 列名为 gender, 账号服务可能回 sex; 取 gender 优先、缺省回落 sex
         (原实现写反: 取到 gender 反而改读 sex, 会把值覆盖为空)。

    出参: 成功 = 账号服务回包字典(整包返回, USER_BASIC 的 openID/avatarID/mobilePhoneNo/... 等列依赖);
          失败(非 200 / 非 JSON / errCode != B0) = 空字典。
    """
    result = comAcc.accountServiceRequest(comAcc.ACCOUNT_SVC_CMD_USER_INFO,
                                          {"loginID": loginID, "sessionID": sessionID})

    if not isinstance(result, dict) or result.get("errCode") != "B0":
        return {}

    roleName = result.get("roleName", "")
    if roleName not in settings.ROLE_CMD_LIST:
        roleName = settings.accountServiceDefaultRoleName #修改默认的用户角色, modify default rolename
    result["roleName"] = roleName

    gender = result.get("gender", "") or result.get("sex", "")
    result["gender"] = gender

    return result


#写入用户数据库 mysql
def writeUser2UserBasic(dataSet,operatorLoginID):
    result = -1
    try:
        loginID = dataSet.get("loginID")
        #USER_BASIC 的列名为 openID(mysqlCommon.insertUserBasic / updateUserBasic 亦按 openID 读写);
        #仅当账号服务回包未给 openID 时, 才回落到 museum 旧报文字段 regOpenID
        openID = dataSet.get("openID", "") or dataSet.get("regOpenID", "")
        passwd = dataSet.get("passwd", "")
        roleName = dataSet.get("roleName", "")
        nickName = dataSet.get("nickName", "")
        realName = dataSet.get("realName", "")
        gender = dataSet.get("gender", "")
        avatarID = dataSet.get("avatarID", "")
        masterID = dataSet.get("masterID", "")
        mobilePhoneNo = dataSet.get("mobilePhoneNo", "")
        province = dataSet.get("province", "")
        city = dataSet.get("city", "")
        area = dataSet.get("area", "")
        address = dataSet.get("address", "")
        email = dataSet.get("email", "")
        PID = dataSet.get("PID", "")
        photoIDFront = dataSet.get("photoIDFront", "")
        photoIDBack = dataSet.get("photoIDBack", "")
        photoID = dataSet.get("photoID", "")
        delFlag = dataSet.get("delFlag", "")
        activeFlag = dataSet.get("activeFlag", comGD._CONST_YES)
        # regID = dataSet.get("regID", "")
        # regYMDHMS = dataSet.get("regYMDHMS", "")
        regPosition = dataSet.get("regPosition", "")
        updateYMDHMS = dataSet.get("updateYMDHMS", "")
        lastOpenID = dataSet.get("lastOpenID", "")
        lastLoginYMDHMS = dataSet.get("lastLoginYMDHMS", "")
        # modifyID = dataSet.get("modifyID", "")
        # modifyYMDHMS = dataSet.get("modifyYMDHMS", "")
        passwdYMDHMS = dataSet.get("passwdYMDHMS", "")

        #extend items begin
        extSessionID: Any = dataSet.get("extSessionID") 
        extStartYMDHMS = dataSet.get("extStartYMDHMS") 
        extLeaveYMDHMS = dataSet.get("extLeaveYMDHMS") 
        extJobPosition = dataSet.get("extJobPosition") 
        extDepartment = dataSet.get("extDepartment") 
        extOrgName = dataSet.get("extOrgName") 
        extOrgID = dataSet.get("extOrgID") 
        extInService = dataSet.get("extInService") 
        extJobLabel = dataSet.get("extJobLabel") 
        extJobDetail = dataSet.get("extJobDetail") 
        extBrief = dataSet.get("extBrief") 
        extManualTagList = dataSet.get("extManualTagList") 
        extManagementAreaList = dataSet.get("extManagementAreaList") 
        extMemo = dataSet.get("extMemo") 
        #extend items end

        mysqlDataList = comMysql.queryUserBasic(loginID)
        saveSet = {}
        if len(mysqlDataList) == 1:
            #exist, update
            currDataSet = mysqlDataList[0]
            
            if openID != currDataSet.get("openID"):
                saveSet["openID"] = openID
            if passwd != currDataSet.get("passwd"):
                saveSet["passwd"] = passwd
            if roleName != currDataSet.get("roleName"):
                saveSet["roleName"] = roleName
            if nickName != currDataSet.get("nickName"):
                saveSet["nickName"] = nickName
            if realName != currDataSet.get("realName"):
                saveSet["realName"] = realName
            if gender != currDataSet.get("gender"):
                saveSet["gender"] = gender
            if avatarID != currDataSet.get("avatarID"):
                saveSet["avatarID"] = avatarID
            if masterID != currDataSet.get("masterID"):
                saveSet["masterID"] = masterID
            if mobilePhoneNo != currDataSet.get("mobilePhoneNo"):
                saveSet["mobilePhoneNo"] = mobilePhoneNo
            if province != currDataSet.get("province"):
                saveSet["province"] = province
            if city != currDataSet.get("city"):
                saveSet["city"] = city
            if area != currDataSet.get("area"):
                saveSet["area"] = area
            if address != currDataSet.get("address"):
                saveSet["address"] = address
            if email != currDataSet.get("email"):
                saveSet["email"] = email
            if PID != currDataSet.get("PID"):
                saveSet["PID"] = PID
            if photoIDFront != currDataSet.get("photoIDFront"):
                saveSet["photoIDFront"] = photoIDFront
            if photoIDBack != currDataSet.get("photoIDBack"):
                saveSet["photoIDBack"] = photoIDBack
            if photoID != currDataSet.get("photoID"):
                saveSet["photoID"] = photoID
            if delFlag != currDataSet.get("delFlag"):
                saveSet["delFlag"] = delFlag
            if activeFlag != currDataSet.get("activeFlag"):
                saveSet["activeFlag"] = activeFlag
            # if regYMDHMS != currDataSet.get("regYMDHMS"):
            #     saveSet["regYMDHMS"] = regYMDHMS
            # if regID != currDataSet.get("regID"):
            #     saveSet["regID"] = regID
            if regPosition != currDataSet.get("regPosition"):
                saveSet["regPosition"] = regPosition
            if updateYMDHMS != currDataSet.get("updateYMDHMS"):
                saveSet["updateYMDHMS"] = updateYMDHMS
            if lastOpenID != currDataSet.get("lastOpenID"):
                saveSet["lastOpenID"] = lastOpenID
            if lastLoginYMDHMS != currDataSet.get("lastLoginYMDHMS"):
                saveSet["lastLoginYMDHMS"] = lastLoginYMDHMS
            # if modifyID != currDataSet.get("modifyID"):
            #     saveSet["modifyID"] = modifyID
            # if modifyYMDHMS != currDataSet.get("modifyYMDHMS"):
            #     saveSet["modifyYMDHMS"] = modifyYMDHMS
            if passwdYMDHMS != currDataSet.get("passwdYMDHMS"):
                saveSet["passwdYMDHMS"] = passwdYMDHMS

            #extend items begin
            if extSessionID != currDataSet.get("extSessionID") and extSessionID:
                saveSet["extSessionID"] = extSessionID

            if extStartYMDHMS != currDataSet.get("extStartYMDHMS") and extStartYMDHMS:
                saveSet["extStartYMDHMS"] = extStartYMDHMS

            if extLeaveYMDHMS != currDataSet.get("extLeaveYMDHMS") and extLeaveYMDHMS:
                saveSet["extLeaveYMDHMS"] = extLeaveYMDHMS

            if extJobPosition != currDataSet.get("extJobPosition") and extJobPosition:
                saveSet["extJobPosition"] = extJobPosition

            if extDepartment != currDataSet.get("extDepartment") and extDepartment:
                saveSet["extDepartment"] = extDepartment

            if extOrgName != currDataSet.get("extOrgName") and extOrgName:
                saveSet["extOrgName"] = extOrgName

            if extOrgID != currDataSet.get("extOrgID") and extOrgID:
                saveSet["extOrgID"] = extOrgID

            if extInService != currDataSet.get("extInService") and extInService:
                saveSet["extInService"] = extInService

            if extJobLabel != currDataSet.get("extJobLabel") and extJobLabel:
                saveSet["extJobLabel"] = extJobLabel

            if extJobDetail != currDataSet.get("extJobDetail") and extJobDetail:
                saveSet["extJobDetail"] = extJobDetail

            if extBrief != currDataSet.get("extBrief") and extBrief:
                saveSet["extBrief"] = extBrief

            if extManualTagList != currDataSet.get("extManualTagList") and extManualTagList:
                saveSet["extManualTagList"] = extManualTagList

            if extManagementAreaList != currDataSet.get("extManagementAreaList") and extManagementAreaList:
                saveSet["extManagementAreaList"] = extManagementAreaList

            if extMemo != currDataSet.get("extMemo") and extMemo:
                saveSet["extMemo"] = extMemo

            #extend items end
        
            if saveSet:
                saveSet["modifyID"] = operatorLoginID
                saveSet["modifyYMDHMS"] = misc.getTime()

                result = comMysql.updateUserBasic(loginID, saveSet)
                if result < 0:
                    _LOG.warning(f"update loginID:{loginID},{saveSet}")
                
        else:
            saveSet["openID"] = openID
            saveSet["passwd"] = passwd
            saveSet["roleName"] = roleName
            saveSet["nickName"] = nickName
            saveSet["realName"] = realName
            saveSet["gender"] = gender
            saveSet["avatarID"] = avatarID
            saveSet["masterID"] = masterID
            saveSet["mobilePhoneNo"] = mobilePhoneNo
            saveSet["province"] = province
            saveSet["city"] = city
            saveSet["area"] = area
            saveSet["address"] = address
            saveSet["email"] = email
            saveSet["PID"] = PID
            saveSet["photoIDFront"] = photoIDFront
            saveSet["photoIDBack"] = photoIDBack
            saveSet["photoID"] = photoID
            saveSet["delFlag"] = delFlag
            saveSet["activeFlag"] = activeFlag
            # saveSet["regYMDHMS"] = regYMDHMS
            # saveSet["regID"] = regID
            saveSet["regPosition"] = regPosition
            saveSet["updateYMDHMS"] = updateYMDHMS
            saveSet["lastOpenID"] = lastOpenID
            saveSet["lastLoginYMDHMS"] = lastLoginYMDHMS
            # saveSet["modifyID"] = modifyID
            # saveSet["modifyYMDHMS"] = modifyYMDHMS
            saveSet["passwdYMDHMS"] = passwdYMDHMS
    
            #extend items begin
            saveSet["extSessionID"] = extSessionID
            saveSet["extStartYMDHMS"] = extStartYMDHMS
            saveSet["extLeaveYMDHMS"] = extLeaveYMDHMS
            saveSet["extJobPosition"] = extJobPosition
            saveSet["extDepartment"] = extDepartment
            saveSet["extOrgName"] = extOrgName
            saveSet["extOrgID"] = extOrgID
            saveSet["extInService"] = extInService
            saveSet["extJobLabel"] = extJobLabel
            saveSet["extJobDetail"] = extJobDetail
            saveSet["extBrief"] = extBrief
            saveSet["extManualTagList"] = extManualTagList
            saveSet["extManagementAreaList"] = extManagementAreaList
            saveSet["extMemo"] = extMemo

            #extend items end
    
            saveSet["regID"] = operatorLoginID
            saveSet["regYMDHMS"] = misc.getTime()

            result = comMysql.insertUserBasic(loginID, saveSet)
            if result < 0:
                _LOG.warning(f"insert loginID:{loginID},{saveSet}")

    except Exception as e:
        errMsg = f"PID: {_processorPID},dataSet:{dataSet},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

    return result


#common func end

#用户自己注册或者管理员添加,同步到mysql
def funcUserRegistration(dataSet):
    result = 0

    operatorLoginID = dataSet.get("loginID")

    inputData = dataSet.get("data")
    outputData = dataSet.get("rtnData")

    loginID = inputData.get("loginID")
    outputLoginID = outputData.get("loginID")
    outputOpenID = outputData.get("openID")
    
    if not loginID and outputLoginID: #小程序登录情况
        loginID = outputLoginID
        _LOG.warning(f"funcUserRegistration, loginID is empty, use outputLoginID:{outputLoginID}")
    
    sessionID = outputData.get("sessionID")
    if not sessionID:
        sessionID = inputData.get("sessionID")

    rtnErrCode = outputData.get("errCode")

    try:
        if loginID  and rtnErrCode=="B0":
            result = 1

            #同步数据到mysql
            userInfo = getUserInfo(loginID,sessionID)
            if userInfo:
                saveSet = copy.deepcopy(userInfo)
                if "passwd" in userInfo:
                    del userInfo["passwd"]
                if _DEBUG:
                    _LOG.info(f"DEBUG: userInfo:{userInfo}")

                rtn = writeUser2UserBasic(saveSet,operatorLoginID)
                _LOG.info(f"D: writeUser2UserBasic,rtn: {rtn}")
                
            #通知管理员处理
            # for userID in REGISTRATION_NOTIFICATION_USER_LIST:
            #     SMS.infoSMS(userID,loginID)
            #     if _DEBUG:
            #         _LOG.info(f"D: funcUserRegistration, userID:{userID}, loginID:{loginID}")
                pass

    except Exception as e:
        errMsg = f"PID: {_processorPID},dataSet:{dataSet},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

    return result



#用户登录,检测用户数据是否存在, 如果不存在,就同步到mysql
def funcUserLogin(dataSet):
    result = 0

    operatorLoginID = dataSet.get("loginID")

    inputData = dataSet.get("data")
    outputData = dataSet.get("rtnData")

    loginID = inputData.get("loginID")
    outputLoginID = outputData.get("loginID")
    
    if not loginID and outputLoginID: #小程序登录情况
        loginID = outputLoginID
        _LOG.warning(f"funcUserLogin, loginID is empty, use outputLoginID:{outputLoginID}")

    sessionID = outputData.get("sessionID")
    if not sessionID:
        sessionID = inputData.get("sessionID")

    rtnErrCode = outputData.get("errCode")

    try:
        if loginID and rtnErrCode=="B0":
            result = 1
            
            #检测用户是否存在(mysql)
            currDataList = comMysql.queryUserBasic(loginID)
            userInfo = getUserInfo(loginID,sessionID)

            #比较一些关键参数
            saveFlag = False
            if userInfo and not currDataList:
                saveFlag = True
            elif userInfo and currDataList:
                currDataSet = currDataList[0]
                #roleName,
                if userInfo.get("roleName") != currDataSet.get("roleName"):
                    saveFlag = True
                elif userInfo.get("realName") != currDataSet.get("realName"):
                    saveFlag = True
                elif userInfo.get("mobilePhoneNo") != currDataSet.get("mobilePhoneNo"):
                    saveFlag = True
            else:
                pass
            
            if saveFlag:
                saveSet = copy.deepcopy(userInfo)
                if "passwd" in userInfo:
                    del userInfo["passwd"]
                if _DEBUG:
                    _LOG.info(f"DEBUG: userInfo:{userInfo}")

                rtn = writeUser2UserBasic(saveSet,operatorLoginID)
                _LOG.info(f"D: writeUser2UserBasic,rtn: {rtn}")
                
                pass

    except Exception as e:
        errMsg = f"PID: {_processorPID},dataSet:{dataSet},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

    return result


#用户删除,同步到mysql
def funcUserDel(dataSet):
    result = 0

    operatorLoginID = dataSet.get("loginID")

    inputData = dataSet.get("data")
    outputData = dataSet.get("rtnData")

    loginID = inputData.get("loginID")
    sessionID = inputData.get("sessionID")

    rtnErrCode = outputData.get("errCode")

    try:
        if loginID and rtnErrCode=="B0":
            result = 1

            #同步数据到mysql
            userInfo = getUserInfo(loginID,sessionID)
            if userInfo:
                dataList = comMysql.queryUserBasic(loginID = loginID)
                if dataList:
                    #delete
                    rtn = comMysql.deleteUserBasic(loginID)
                    if rtn < 0:
                        _LOG.warning(f"user delete:{loginID}")

    except Exception as e:
        errMsg = f"PID: {_processorPID},dataSet:{dataSet},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

    return result


#用户数据修改,同步到mysql
def funcUserModify(dataSet):
    result = 0

    operatorLoginID = dataSet.get("loginID")

    inputData = dataSet.get("data")
    outputData = dataSet.get("rtnData")

    loginID = inputData.get("loginID")
    sessionID = inputData.get("sessionID")

    rtnErrCode = outputData.get("errCode")

    try:
        if loginID and rtnErrCode=="B0":
            result = 1

            #同步数据到mysql
            userInfo = getUserInfo(loginID,sessionID)
            if userInfo:
                saveSet = userInfo

                rtn = writeUser2UserBasic(saveSet,operatorLoginID)
                _LOG.info(f"D: writeUser2UserBasic,rtn: {rtn}")

    except Exception as e:
        errMsg = f"PID: {_processorPID},dataSet:{dataSet},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

    return result

#user relate end

# command part end



# buffer相关, 考虑到部分查询数据较多, 因此查询结果先缓存到redis,然后根据用户要求取出,
# 这个是一个异步代码, 保证后台的速度
def funcPutDataBufferList(dataSet):
    indexKey = dataSet.get("indexKey")
    dataList = dataSet.get("data")
    comDB.delDataBuffer(indexKey)
    rtn =  comDB.putAllDataBuffer(indexKey, dataList)
    result = len(dataList)
    return result


#mindgram 业务域处理(原 museum 的 mgmoodpostadd 心情打卡/周报, emojisetadd/emojisetdel/
#emojisetmodify 表情集维护)已按 contentHub 口径整体移除: contentHub 不承载该业务域,
#其依赖的 comMysql.mgWeeklyReel / mgEmojiSet / mgEmojiItem 数据层、comDB.setLastUserMood
#与 settings.MINDGRAM_EMOJI_SET_DATA 在本工程均不存在。


def checkDatabaseExists():
    pass


def funcProcTransferData(CMD,transSet):
    result = 0
    totalHandledData = 0
    try:

        if CMD == "registration": 
            totalHandledData = funcUserRegistration(transSet)

        elif CMD == "login": 
            totalHandledData = funcUserLogin(transSet)

        elif CMD == "useradd": 
            totalHandledData = funcUserRegistration(transSet)

        elif CMD == "userdel": 
            totalHandledData = funcUserDel(transSet)

        elif CMD == "usermodify": 
            totalHandledData = funcUserModify(transSet)

        elif CMD == "putdatabufferlist": 
            totalHandledData = funcPutDataBufferList(transSet)

        #注: 原 museum 的 mindgram 命令(mgmoodpostadd / emojisetadd / emojisetdel /
        #emojisetmodify)已随对应处理函数一并移除, contentHub 亦无对应生产者。

        else:
            if _DEBUG:
                _LOG.info(f"S: total {CMD}: nothing to do")
        result = totalHandledData
    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")
    return result


def procTransferData():
    checkDatabaseExists()

    while True: 
        CMD=""
        try:
            transSet = comDB.getMsg2Queue(comGD._DEF_CH_MSG_QUEUE_MYSQL_TITLE)
            if transSet:
                CMD = transSet.get("CMD","")
                CMD = CMD.lower()
                #transfer data receive
                if _DEBUG:
                    # _LOG.info(f"R: CMD:{CMD}") 
                    msg = misc.jsonDumps(transSet)
                    _LOG.info(f"R: CMD: {CMD} '{msg}'") 
                totalHandledData = funcProcTransferData(CMD,transSet)
                if _DEBUG:
                    _LOG.info(f"S: total {CMD}: {totalHandledData}")

            else:
                misc.time.sleep(0.1) #避免占用CPU资源

        except Exception as e:
            errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
            _LOG.error(f"{errMsg}, {traceback.format_exc()}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        pass
        import platform
        if platform.system()=='Linux':
            import pdb
            pdb.set_trace()
            CMD=sys.argv[1]
            msg = sys.argv[2]
            dataSet = misc.jsonLoads(msg)
            funcProcTransferData(CMD,dataSet) 
            breakFlag = True
            if breakFlag:
                sys.exit(0)
            pass
    
    procTransferData()
