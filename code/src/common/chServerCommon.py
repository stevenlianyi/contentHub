#!/usr/bin/env python3
#encoding: utf-8

#Filename: chServerCommon.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-17
#Description:   contentHub(内容中枢) 相关的接口
#所有接口均为 RESTful 接口, 由 main/chAPI.py 的 /chapi/<urlPath> 提供
#参照 ylwzStockCommon.py 的结构与实现模式
# 1. 主题 / 主题附图 查询接口
# 2. 版式 / 平台能力矩阵 查询接口
# 3. 渲染任务 / 渲染产物 查询接口
# 4. 投递(发布)记录 查询接口
# 5. 分页缓冲续取接口(generalnext)
#说明: 本文件为 MCP 只读工具的数据入口, 不承载任何业务计算,
#      所有过滤/校验/文件URL转换均由下游 /chapi 完成


_VERSION="20260917"


import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import traceback
import requests

from common import globalDefinition as comGD
from common import miscCommon as misc

from config import basicSettings as settings


if "_LOG" not in dir() or not _LOG:
    logDir = os.path.join(getattr(settings, "_HOME_DIR", ""), "log")
    _LOG = misc.setLogNew("CH", comGD._DEF_LOG_CH_TEST_NAME, logDir)


#common begin
_processorPID = os.getpid()

#REST请求超时时间(秒), 防止下游无响应时长时间挂起
_HTTP_REQUEST_TIMEOUT = 30

#contentHub REST 接口表: cmd小写 -> {method, description, host, port, headers, urlPath, params}
#urlPath 规则与 ylwz 既有约定一致: "<路由前缀>/<cmd>", 本项目路由前缀为 chapi
#说明: 本期仅登记 MCP 只读所需命令; 写入/渲染/投递类命令在对应能力开放时再追加
CH_API_URL_DATA = {
    #common
    "generalnext":
    {
        "method":"post",
        "description":"获取后续数据",
        "host":"",
        "port":80,
        "headers":{"content-type": "application/json"},
        "urlPath":"chapi/generalnext",
        "params":{}
    },
    #topic
    "topicqry":
    {
        "method":"post",
        "description":"查询主题信息",
        "host":"",
        "port":80,
        "headers":{"content-type": "application/json"},
        "urlPath":"chapi/topicqry",
        "params":{}
    },
    "topicassetqry":
    {
        "method":"post",
        "description":"查询主题附图关联信息",
        "host":"",
        "port":80,
        "headers":{"content-type": "application/json"},
        "urlPath":"chapi/topicassetqry",
        "params":{}
    },
    #layout / platform
    "layoutqry":
    {
        "method":"post",
        "description":"查询版式模板信息",
        "host":"",
        "port":80,
        "headers":{"content-type": "application/json"},
        "urlPath":"chapi/layoutqry",
        "params":{}
    },
    "platformqry":
    {
        "method":"post",
        "description":"查询平台能力矩阵信息",
        "host":"",
        "port":80,
        "headers":{"content-type": "application/json"},
        "urlPath":"chapi/platformqry",
        "params":{}
    },
    #render job / artifact
    "renderjobqry":
    {
        "method":"post",
        "description":"查询渲染任务信息",
        "host":"",
        "port":80,
        "headers":{"content-type": "application/json"},
        "urlPath":"chapi/renderjobqry",
        "params":{}
    },
    "artifactqry":
    {
        "method":"post",
        "description":"查询渲染产物信息",
        "host":"",
        "port":80,
        "headers":{"content-type": "application/json"},
        "urlPath":"chapi/artifactqry",
        "params":{}
    },
    #publish record
    "publishrecordqry":
    {
        "method":"post",
        "description":"查询投递(发布)记录信息",
        "host":"",
        "port":80,
        "headers":{"content-type": "application/json"},
        "urlPath":"chapi/publishrecordqry",
        "params":{}
    },
}
#common end

#查询类命令清单: 命中后由 handleQueryResult 解析 indexKey 分页信息
QUERY_CMD_LIST = [
    "topicqry",
    "topicassetqry",
    "layoutqry",
    "platformqry",
    "renderjobqry",
    "artifactqry",
    "publishrecordqry",
    ]


class ChServer:
    _HOST = '127.0.0.1'
    _PORT = 80
    _ROOT_PATH = ""
    _errMsg = ""
    _indexKey = ""
    _indexBeginNum = 0
    _indexEndNum = 0
    _indexTotal = 0
    _restNum = 0
    _responseCode = 0


    def __init__(self,host="",port=80,sessionID="",rootPath=""):
        self._HOST = host
        self._PORT = port
        self._sessionID = sessionID
        self._ROOT_PATH = rootPath

    def getRequest(self,url,paramsData,headers={"content-type": "application/json"},authFlag=True):
        result = {}

        rtnData = {}

        try:
            if authFlag:
                paramsData["sessionID"] = self._sessionID
                pass
            r = requests.get(url, params = paramsData, headers = headers, timeout = _HTTP_REQUEST_TIMEOUT)
            if r.status_code == 200:
                try:
                    rtnData["data"] = misc.jsonLoads(r.content)
                except:
                    rtnData["data"] = r.content
            else:
                self._responseCode = r.status_code
                pass

            rtnData["status"] = r.status_code
            result = rtnData

        except Exception as e:
            errMsg = f"PID: {_processorPID},errMsg:{str(e),traceback.format_exc()}"
            self._errMsg = errMsg

        return result

    def postRequest(self,url,requestData,paramsData={},headers={"content-type": "application/json"},authFlag=True):
        result = {}

        rtnData = {}
        try:
            if authFlag:
                requestData["sessionID"] = self._sessionID
                pass
            payload = misc.jsonDumps(requestData)

            if paramsData:
                r = requests.post(url, data = payload, params=paramsData,headers = headers, timeout = _HTTP_REQUEST_TIMEOUT)
            else:
                r = requests.post(url, data = payload, headers = headers, timeout = _HTTP_REQUEST_TIMEOUT)

            if r.status_code == 200:
                try:
                    rtnData["data"] = misc.jsonLoads(r.content)
                except:
                    rtnData["data"] = r.content
            else:
                self._responseCode = r.status_code
                pass

            rtnData["status"] = r.status_code
            result = rtnData

        except Exception as e:
            errMsg = f"PID: {_processorPID},errMsg:{str(e),traceback.format_exc()}"
            self._errMsg = errMsg

        return result

    def query(self,cmd,requestData={},paramsData={},authFlag=True):
        result = {}
        try:
            cmd = cmd.lower()
            requestTypeData = CH_API_URL_DATA.get(cmd)
            if requestTypeData:
                method = requestTypeData["method"]
                host = requestTypeData["host"]
                port = requestTypeData["port"]
                urlPath = requestTypeData["urlPath"]
                localParams = requestTypeData["params"]

                if not paramsData and localParams:
                    paramsData = localParams

                if self._HOST: #如果class初始化指定了IP就用指定的IP
                    host = self._HOST

                if self._PORT:
                    port = self._PORT

                if self._ROOT_PATH:
                    url = "http://" + host + ":" + str(port) + "/" + self._ROOT_PATH + "/" + urlPath
                else:
                    url = "http://" + host + ":" + str(port) + "/" + urlPath

                if method == "post":
                    result = self.postRequest(url,requestData,paramsData)
                else:
                    result = self.getRequest(url,paramsData)

                #处理qry命令
                if cmd in QUERY_CMD_LIST:
                    self.handleQueryResult(cmd,result)

        except Exception as e:
            errMsg = f"PID: {_processorPID},errMsg:{str(e),traceback.format_exc()}"
            self._errMsg = errMsg

        return result

    ##处理查询结果
    def handleQueryResult(self,cmd,dataSet):
        result = False
        try:
            if dataSet and "data" in dataSet:
                data = dataSet["data"]
                if data:
                    self._indexKey = data.get("indexKey","")
                    self._indexTotal = int(data.get("total",0))
                    self._indexBeginNum = int(data.get("beginNum",0))
                    self._indexEndNum = int(data.get("endNum",0))
                    self._restNum = self._indexTotal - self._indexEndNum - 1
        except Exception as e:
            errMsg = f"PID: {_processorPID},errMsg:{str(e),traceback.format_exc()}"
            self._errMsg = errMsg

        return result

    ##获取剩余数据条数
    def getRestNum(self):
        return self._restNum

    #获取下一批数据
    def getNext(self,num = 100):
        result = []
        try:
            nextBeginNum = self._indexEndNum + 1
            nextEndNum = nextBeginNum + num - 1
            if nextEndNum > self._indexTotal:
                nextEndNum = self._indexTotal
            querySet = {"indexKey":self._indexKey,"beginNum":nextBeginNum,"endNum":nextEndNum}
            cmd = "generalnext"
            result = self.query(cmd,querySet)
        except Exception as e:
            errMsg = f"PID: {_processorPID},errMsg:{str(e),traceback.format_exc()}"
            self._errMsg = errMsg
        return result

    #应用部分 begin
    #主题
    def searchTopics(self,topicCode="",title="",status="",publishStatus="",categoryCode="",ownerID="",mode="",limitNum=0):
        """查询主题列表"""
        result = []
        try:
            cmd = "topicqry"
            querySet = {"topicCode":topicCode,"title":title,"status":status,
                        "publishStatus":publishStatus,"categoryCode":categoryCode,
                        "ownerID":ownerID,"mode":mode,"limitNum":limitNum}
            result = self.query(cmd,querySet)
        except Exception as e:
            errMsg = f"PID: {_processorPID},errMsg:{str(e),traceback.format_exc()}"
            self._errMsg = errMsg
        return result

    #主题详情(按主题编码或记录ID单条查询)
    def getTopic(self,topicCode="",recID="",mode="",limitNum=0):
        """查询单条主题详情"""
        result = []
        try:
            cmd = "topicqry"
            querySet = {"topicCode":topicCode,"recID":recID,"mode":mode,"limitNum":limitNum}
            result = self.query(cmd,querySet)
        except Exception as e:
            errMsg = f"PID: {_processorPID},errMsg:{str(e),traceback.format_exc()}"
            self._errMsg = errMsg
        return result

    #主题附图
    def readTopicAssetList(self,topicID="",fileID="",usageType="",limitNum=0):
        """查询主题附图清单"""
        result = []
        try:
            cmd = "topicassetqry"
            querySet = {"topicID":topicID,"fileID":fileID,"usageType":usageType,"limitNum":limitNum}
            result = self.query(cmd,querySet)
        except Exception as e:
            errMsg = f"PID: {_processorPID},errMsg:{str(e),traceback.format_exc()}"
            self._errMsg = errMsg
        return result

    #版式
    def readLayoutList(self,platform="",layoutType="",layoutCode="",enabled="",limitNum=0):
        """查询版式模板清单"""
        result = []
        try:
            cmd = "layoutqry"
            querySet = {"platform":platform,"layoutType":layoutType,
                        "layoutCode":layoutCode,"enabled":enabled,"limitNum":limitNum}
            result = self.query(cmd,querySet)
        except Exception as e:
            errMsg = f"PID: {_processorPID},errMsg:{str(e),traceback.format_exc()}"
            self._errMsg = errMsg
        return result

    #平台能力矩阵
    def readPlatformList(self,platformCode="",enabled="",limitNum=0):
        """查询平台能力矩阵清单"""
        result = []
        try:
            cmd = "platformqry"
            querySet = {"platformCode":platformCode,"enabled":enabled,"limitNum":limitNum}
            result = self.query(cmd,querySet)
        except Exception as e:
            errMsg = f"PID: {_processorPID},errMsg:{str(e),traceback.format_exc()}"
            self._errMsg = errMsg
        return result

    #渲染任务
    def readRenderJobList(self,jobCode="",topicID="",jobStatus="",platform="",limitNum=0):
        """查询渲染任务清单"""
        result = []
        try:
            cmd = "renderjobqry"
            querySet = {"jobCode":jobCode,"topicID":topicID,"jobStatus":jobStatus,
                        "platform":platform,"limitNum":limitNum}
            result = self.query(cmd,querySet)
        except Exception as e:
            errMsg = f"PID: {_processorPID},errMsg:{str(e),traceback.format_exc()}"
            self._errMsg = errMsg
        return result

    #渲染产物
    def readArtifactList(self,topicID="",jobID="",kind="",platform="",artifactStatus="",limitNum=0):
        """查询渲染产物清单"""
        result = []
        try:
            cmd = "artifactqry"
            querySet = {"topicID":topicID,"jobID":jobID,"kind":kind,
                        "platform":platform,"artifactStatus":artifactStatus,"limitNum":limitNum}
            result = self.query(cmd,querySet)
        except Exception as e:
            errMsg = f"PID: {_processorPID},errMsg:{str(e),traceback.format_exc()}"
            self._errMsg = errMsg
        return result

    #投递(发布)记录
    def readPublishRecordList(self,topicID="",artifactId="",platform="",success="",operator="",limitNum=0):
        """查询投递(发布)记录清单"""
        result = []
        try:
            cmd = "publishrecordqry"
            querySet = {"topicID":topicID,"artifactId":artifactId,"platform":platform,
                        "success":success,"operator":operator,"limitNum":limitNum}
            result = self.query(cmd,querySet)
        except Exception as e:
            errMsg = f"PID: {_processorPID},errMsg:{str(e),traceback.format_exc()}"
            self._errMsg = errMsg
        return result

    #应用部分 end


if __name__ == "__main__":
    pass
    # import pdb
    # pdb.set_trace()
    print("CH_API_URL_DATA keys:", list(CH_API_URL_DATA.keys()))
    print("QUERY_CMD_LIST:", QUERY_CMD_LIST)
