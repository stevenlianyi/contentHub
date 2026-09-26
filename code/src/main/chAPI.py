#! /usr/bin/env python3
#encoding: utf-8

#Filename: chAPI.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub(内容中枢) HTTP 门面(Flask), 对齐基线 main/museumAPI.py 范式。
#
#职责: 只做「HTTP 协议 <-> 业务报文」的转换, 不含任何业务逻辑:
#  - 路由 /chapi/<urlPath>(与 mcpapi/chServerCommon.py 的 urlPath 前缀保持同源);
#  - 取真实来源 IP(X-Forwarded-For)与来源服务器头(X-Server-Addr/Port/Protocol);
#  - 按 mimetype 三分支取 dataSet(multipart/form-data、application/json、其它原始报文);
#  - 调 chAPIPost.post() 并统一 jsonDumps 返回。
#
#启动: cd code/src/main && python chAPI.py   (或由 gunicorn/fcgi 以 application 为 WSGI app)

_VERSION="20260918"


from flask import Flask, request, Response

application = Flask(__name__)

import os
import sys

#main/ 与 code/src 同时入 sys.path: 保证 `import chAPIPost` / `from common import ...` 与 cwd 无关
_mainDir = os.path.dirname(os.path.abspath(__file__))
_srcDir = os.path.dirname(_mainDir)
for _path in (_srcDir, _mainDir):
    if _path not in sys.path:
        sys.path.insert(0, _path)

if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import traceback

from common import globalDefinition as comGD

from common import miscCommon as misc

import chAPIPost as userApp


_processorPID = os.getpid()

appName = "chAPI"
routeAddr = "/chapi/<urlPath>"
httpMethod = ["GET", "POST"]
appType = ""

_DEBUG = True

#日志: 与 chAPIPost/context 使用同一组常量 => 同一 logger 对象, 天然幂等(setLogNew 内置 handler 判重)
if "_LOG" not in dir() or not _LOG:
    _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)

#注入实现层, 保证全链路同一 logger
userApp.applyLog(_LOG)

systemVersion = str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro)
_LOG.info(f"PID:{_processorPID}, python version:{systemVersion}, start code version:{_VERSION}, main code version:{userApp._VERSION}")

_LOG.info(f"C: routeAddr:{routeAddr},methods:{httpMethod},appType:{appType},cmdTotal:{len(userApp.CMDMapKeyList)}")


@application.route(routeAddr, methods = httpMethod)
def main(urlPath):
    rtnSet = {}

    try:
        IP = request.remote_addr

        try:
            x_forward_for = request.headers.get('X-Forwarded-For', '')
            lastIP = ""
            aList = x_forward_for.split(",")
            for a in aList:
                if len(a) > 3:
                    lastIP = a
                    IP = lastIP
            if _DEBUG and lastIP:
                _LOG.info(f"DEBUG:{request.mimetype},{urlPath},{len(lastIP)},{lastIP}")

        except Exception:
            pass

        x_server_addr = request.headers.get('X-Server-Addr', '')
        x_server_port = request.headers.get('X-Server-Port', '')
        x_protocol_used = request.headers.get('X-Protocol-Used', '')

        environSet = {}
        environSet["REQUEST_METHOD"] = request.method
        environSet["CONTENT_LENGTH"] = request.content_length
        environSet["CONTENT_TYPE"] = request.content_type

        environSet["_x_server_addr"] = x_server_addr
        environSet["_x_server_port"] = x_server_port
        environSet["_x_protocol_used"] = x_protocol_used

        dataSet = {}
        if request.mimetype == "multipart/form-data":
            dataSet = request.form.to_dict(flat = False)

            rtnSet = userApp.post(urlPath, dataSet, IP, environSet, appType)

        elif request.mimetype == "application/json":
            dataSet = request.json

            rtnSet = userApp.post(urlPath, dataSet, IP, environSet, appType)
        else:
            if _DEBUG:
                _LOG.info(f"MR: {request.mimetype},{request.data}")

            try:
                dataSet = misc.jsonLoads(request.data)
                rtnSet = userApp.post(urlPath, dataSet, IP, environSet, appType)

                if _DEBUG:
                    _LOG.info(f"MS: {request.mimetype},{misc.jsonDumps(rtnSet)}")
            except Exception as e:
                errMsg = f"PID: {_processorPID},errMsg:{str(e)}"
                _LOG.error(f"{errMsg}, {traceback.format_exc()}")

    except Exception as e:
        errMsg = f"PID: {_processorPID},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

    #★ 2026-09-22 修复中文乱码(UTF-8 体被当作 GBK / 声明与字节不一致; 见前端计划附录 B R-33):
    #  出口固定返回 **纯 ASCII 转义** 的 JSON 字节, 并显式声明 "application/json; charset=utf-8"。
    #  为什么用 ensure_ascii=True: 中文以 \uXXXX 形式承载, ASCII 字节对任何编码/转码都**不变**,
    #  从而彻底消除"响应体是 GBK 字节、响应头声明 UTF-8"这类中间层(反向代理 / 旧入口 / locale 设置)
    #  引入的乱码 —— 浏览器按 JSON 规则解出 \uXXXX 即得到正确中文。
    #  代价: 中文报文体积约 +50%(网关若已对 application/json 开启 gzip 则基本无感)。
    #  注意: 仅本出口改; 日志路径(misc.jsonDumps 默认 ensure_ascii=False)保持不变。
    responseBody = misc.jsonDumps(rtnSet, ensure_ascii = True)

    return Response(responseBody.encode("ascii", "backslashreplace"), status = 200,
                    content_type = "application/json; charset=utf-8")


if __name__ == "__main__":
    application.run(host = '0.0.0.0')
