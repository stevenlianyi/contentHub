#! /usr/bin/env python3
#encoding: utf-8:

#Filename: assetService.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub C3 素材图库业务服务(SP2b 落点, 见主计划 2.2 C3 / 5.3 P1-5·P1-6)。
#
#职责(纯业务, 不涉 HTTP 报文封装):
#  1) 素材上传落库(ch_asset)              —— 只经 common/mysqlCommon.py(红线 R1, 禁裸 SQL);
#  2) contentHash 内容级去重              —— sha256(原始字节) 命中即复用既有素材(幂等, 不产生重复数据);
#  3) 规格裁剪 + 缩略图 + EXIF 剥离       —— 尺寸口径取 settings.MAX_PIC_SIZE / settings.THUMBNAIL_SIZE;
#  4) fileSystem / storageBucket 快照      —— 落库时记录后端与桶, 供多桶读取路由(历史文件可读);
#  5) 素材元信息 CRUD + 附图绑定(ch_topic_asset):
#       assetKey = {topicID}:{fileID} 幂等; sortOrder 排序(越小越靠前); usageType 语义(cover/body/inline);
#  6) 出参统一经 common/chCommon.py::fillFileUrls 把 fileID 转 URL。
#
#三后端切换(红线 R2): 只经 common/fileStorageCommon.py 的门面(saveFile / saveWithThumbnail /
#  getFileInfo / delFile / resolveBucket), 本文件不得出现任何厂商分支判断(oss/cos/selffile 之一)。
#
#返回契约(供 main/subfunc/assetApi.py 直接映射为 HTTP 报文):
#  {"errCode": <"B0"=通过 / C·D 段错误码>, "field": <出错字段描述>, "errMsgList": [<原因>], "data": {...}}
#
#错误码落点(均为 common/errMsgCommon.py 的 contenthub 消息键, C 段=通用与字段校验 / D 段=文件与素材):
#  C4 必填缺失 | C5 字段超长 | C6 数值/区间越界 | C7 取值非法
#  CA 重复记录 | CB 无此记录 | D0 文件类型不允许 | D1 文件超出限制 | D3 文件上传失败 | D4 文件不存在
#
#设计约束:
#  - 本模块不 import main/subfunc/*(避免 processor <-> 接入层的循环依赖; 分层单向);
#  - 文件门面与图像库(Pillow)按 chCommon 既有约定「函数内延迟导入」—— fileStorageCommon 会牵出
#    云厂商 SDK, Pillow 仅图像处理路径需要; 保证只做数据库操作的调用方不被动依赖这些依赖。

_VERSION="20260923"

import hashlib
import os
import re
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../code/src
if parentdir not in sys.path:
    sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import tempfile
import traceback

#global defintion/common var etc.
from common import globalDefinition as comGD

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#数据层唯一入口(红线 R1)
from common import mysqlCommon as comMysql

#跨域业务公共件(幂等写入 + fileID -> URL)
from common import chCommon as comCh

from common import fileStorageCommon as comFS

#setting files
from config import basicSettings as settings


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    #与接入层共用同一 logger(同名 logger 唯一, miscCommon.setLogNew 内部有 handlers 判重)
    try:
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None

_DEBUG = settings._DEBUG


#===== 表与字段常量 begin =====

ASSET_TABLE = "ch_asset"
TOPIC_ASSET_TABLE = "ch_topic_asset"

#ch_asset 字段顺序(唯一数据源: database/ch_asset.txt), 仅用于「字段名 + 位置」的错误提示
ASSET_FIELD_ORDER = [
    "recID", "fileID", "thumbnailID", "contentHash", "fileSystem", "storageBucket",
    "storagePath", "objectName", "origName", "mimeType", "fileExt", "origSizeBytes",
    "width", "height", "derivedFileID", "derivedThumbID", "derivedWidth", "derivedHeight",
    "derivedSizeBytes", "exifStripped", "processStatus", "errMsg", "ownerID", "label",
    "memo", "regID", "regYMDHMS", "modifyID", "modifyYMDHMS", "delFlag",
]

#ch_topic_asset 字段顺序(唯一数据源: database/ch_topic_asset.txt)
TOPIC_ASSET_FIELD_ORDER = [
    "recID", "assetKey", "topicID", "fileID", "caption", "usageType", "sortOrder",
    "label", "memo", "regID", "regYMDHMS", "modifyID", "modifyYMDHMS", "delFlag",
]

#字段长度上限(与 database/ch_*.txt 的列宽一致)
ASSET_KEY_MAX_LEN = 400
ORIG_NAME_MAX_LEN = 255
OBJECT_NAME_MAX_LEN = 255
MIME_TYPE_MAX_LEN = 64
FILE_EXT_MAX_LEN = 16
CONTENT_HASH_MAX_LEN = 64
CAPTION_MAX_LEN = 512
LABEL_MAX_LEN = 32
MEMO_MAX_LEN = 200

#sortOrder 区间(SMALLINT NOT NULL DEFAULT 100; 越小越靠前)
SORT_ORDER_DEFAULT = 100
SORT_ORDER_MIN = 0
SORT_ORDER_MAX = 32767

#usageType 语义(主计划 3.4 附图绑定): cover=封面 / body=正文 / inline=内联
USAGE_TYPE_LIST = ["cover", "body", "inline"]
USAGE_TYPE_DEFAULT = "body"

#处理状态(生成器默认 'RAW'; 裁剪/缩略图/EXIF 剥离成功后为 PROCESSED, 失败为 FAILED)
PROCESS_STATUS_LIST = ["RAW", "PROCESSED", "FAILED"]
PROCESS_STATUS_DEFAULT = "RAW"
PROCESS_STATUS_DONE = "PROCESSED"
PROCESS_STATUS_FAILED = "FAILED"

#EXIF 剥离标记
EXIF_STRIPPED_NO = "0"
EXIF_STRIPPED_YES = "1"

#按图片处理的扩展名(裁剪 / 缩略图 / EXIF 剥离仅对图片生效; 非图片一律降级为原样上传)
IMAGE_EXT_LIST = ["jpg", "jpeg", "png", "webp", "bmp", "gif"]

#幂等键分隔符: assetKey = {topicID}:{fileID}
ASSET_KEY_SEPARATOR = ":"

#删除标记(红线: delFlag 一律 "0"/"1", 不是 comGD._CONST_NO/_CONST_YES)
DEL_FLAG_NORMAL = "0"
DEL_FLAG_DELETED = "1"

#错误码落点(common/errMsgCommon.py::_CH_ERROR_WORD 的 contenthub C/D 段)
ERR_FIELD_MISSING = "C4"
ERR_FIELD_TOO_LONG = "C5"
ERR_FIELD_OUT_OF_RANGE = "C6"
ERR_FIELD_INVALID = "C7"
ERR_DUPLICATE = "CA"
ERR_NO_RECORD = "CB"
ERR_FILE_TYPE = "D0"
ERR_FILE_LIMIT = "D1"
ERR_FILE_UPLOAD = "D3"
ERR_FILE_NOT_FOUND = "D4"

#===== 表与字段常量 end =====


#===== 通用小工具 begin =====

def _toStr(value):
    """None/数字/任意 -> 去空白字符串"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _fieldLabel(fieldName):
    """字段名 + 位置(在所属表中的序号, 从 1 开始), 用于错误提示「标明字段名与位置」"""
    try:
        pos = ASSET_FIELD_ORDER.index(fieldName) + 1
    except ValueError:
        try:
            pos = TOPIC_ASSET_FIELD_ORDER.index(fieldName) + 1
        except ValueError:
            pos = 0
    return f"{fieldName}(字段#{pos})"


def _ok(data = None, errMsgList = None):
    """业务成功返回"""
    return {"errCode": "B0", "field": "", "errMsgList": errMsgList or [], "data": data or {}}


def _err(errCode, rtnField, errMsgList = None, data = None):
    """业务失败返回(可携带回显数据)"""
    return {"errCode": errCode, "field": rtnField, "errMsgList": errMsgList or [], "data": data or {}}


def _tableName():
    """表名一律经 mysqlCommon 的转名函数取得"""
    return comMysql.tablename_convertor_ch_asset()


def _topicAssetTableName():
    return comMysql.tablename_convertor_ch_topic_asset()


def _loginID(sessionIDSet):
    """从会话上下文取 loginID(缺省用系统默认自动 loginID, 与基线一致)"""
    if isinstance(sessionIDSet, dict):
        loginID = _toStr(sessionIDSet.get("loginID"))
        if loginID:
            return loginID
    return settings.SYS_DEFAULT_AUTO_LOGINID


def _fillFileUrls(data):
    """出参统一经 chCommon.fillFileUrls 转换 fileID -> URL(库内只存 fileID)"""
    try:
        return comCh.fillFileUrls(data)
    except Exception as e:
        if _LOG:
            _LOG.warning(f"W: PID:{_processorPID}, fillAssetFileUrls failed, errMsg:{str(e)}")
        return data

#===== 通用小工具 end =====


#===== 内容指纹 begin =====

def computeContentHashFromBytes(rawBytes):
    """contentHash = sha256(原始字节) 的十六进制串(内容级去重依据)。

    先对「原始字节」求哈希, 再谈规格裁剪 —— 同一张图经不同程度压缩后 hash 不同,
    但同一份原始文件重复上传必定命中; 这正是主计划 3.4 的去重口径。
    """
    if rawBytes is None:
        return ""
    if isinstance(rawBytes, str):
        rawBytes = rawBytes.encode("utf-8")
    return hashlib.sha256(rawBytes).hexdigest()


def computeContentHash(localPath):
    """按本地文件计算 contentHash; 文件不存在/不可读返回 \"\"(调用方按 D4 处理)"""
    if not localPath or not os.path.isfile(localPath):
        return ""
    hashObj = hashlib.sha256()
    try:
        with open(localPath, "rb") as hFile:
            while True:
                chunk = hFile.read(1024 * 1024)
                if not chunk:
                    break
                hashObj.update(chunk)
    except Exception as e:
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, computeContentHash failed, localPath:{localPath}, errMsg:{str(e)}")
        return ""
    return hashObj.hexdigest()

#===== 内容指纹 end =====


#===== 图像处理(裁剪 / EXIF 剥离 / 缩略图) begin =====
#口径(契约, 写死):
#  - 规格裁剪: 超 settings.MAX_PIC_SIZE 时等比缩放到区间内(只缩不放, 避免小图被放大失真);
#  - EXIF 剥离: 重建像素后另存, 不拷贝 exif 元数据(PIL 默认不写 exif);
#  - 缩略图: 由 common/fileStorageCommon.buildThumbnail 统一生成(settings.THUMBNAIL_SIZE);
#  - 以上任一环节失败一律「降级为原文件 + 记日志」, 不上抛异常、不阻断上传(EXIF 剥离非硬门槛)。

def isImagePath(localPath):
    """按扩展名判断是否图片(Pillow 缺失或非图片时一律走原样上传)"""
    fileExt = os.path.splitext(_toStr(localPath))[1].lstrip(".").lower()
    return fileExt in IMAGE_EXT_LIST


def _openImage(localPath):
    """延迟导入 Pillow 并打开图片; 失败返回 None(不抛异常)"""
    try:
        from PIL import Image
        return Image.open(localPath)
    except Exception as e:
        if _LOG:
            _LOG.warning(f"W: PID:{_processorPID}, open image failed, localPath:{localPath}, errMsg:{str(e)}")
        return None


def stripExif(localPath, outPath = ""):
    """EXIF 剥离: 重建像素后另存(不携带 exif / GPS 等元数据)。
       返回剥离后的文件路径; 失败或非图片返回 ""。"""
    if not isImagePath(localPath):
        return ""
    im = _openImage(localPath)
    if im is None:
        return ""

    if not outPath:
        fd, outPath = tempfile.mkstemp(suffix = ".jpg", prefix = "ch_asset_exif_")
        os.close(fd)

    try:
        im.convert("RGB").save(outPath, "JPEG", quality = 95)
        return outPath
    except Exception as e:
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, stripExif failed, localPath:{localPath}, errMsg:{str(e)}")
        return ""
    finally:
        try:
            im.close()
        except Exception:
            pass


def fitImageToMaxSize(localPath, maxSize = None, outPath = ""):
    """规格裁剪: 超过 maxSize(缺省 settings.MAX_PIC_SIZE) 时等比缩放到区间内。
       返回 (裁剪后路径, 宽度, 高度); 未超限/非图片/失败时返回 (localPath, 原宽高或 0, 0)。"""
    if not maxSize:
        maxSize = settings.MAX_PIC_SIZE
    if not maxSize or not isImagePath(localPath):
        return localPath, 0, 0

    im = _openImage(localPath)
    if im is None:
        return localPath, 0, 0

    try:
        width, height = im.size
        maxWidth, maxHeight = int(maxSize[0]), int(maxSize[1])
        if width <= maxWidth and height <= maxHeight:
            return localPath, width, height

        if not outPath:
            fd, outPath = tempfile.mkstemp(suffix = ".jpg", prefix = "ch_asset_resize_")
            os.close(fd)

        im.thumbnail((maxWidth, maxHeight))
        newWidth, newHeight = im.size
        im.convert("RGB").save(outPath, "JPEG", quality = 95)
        return outPath, newWidth, newHeight
    except Exception as e:
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, fitImageToMaxSize failed, localPath:{localPath}, errMsg:{str(e)}")
        return localPath, 0, 0
    finally:
        try:
            im.close()
        except Exception:
            pass


def processImageForUpload(localPath, maxSize = None):
    """上传前处理: 先规格裁剪(内置 EXIF 剥离, 另存即丢元数据) -> 再缩略图。
       返回 dict:
         {"path": 待上传文件路径, "width": int, "height": int,
          "exifStripped": "0"/"1", "processStatus": "RAW"/"PROCESSED"/"FAILED",
          "tempList": [需清理的临时文件], "errMsg": str}
       说明: 非图片 / Pillow 缺失 / 处理失败一律降级为原文件(processStatus=RAW), 不阻断上传。"""
    result = {"path": localPath, "width": 0, "height": 0,
              "exifStripped": EXIF_STRIPPED_NO, "processStatus": PROCESS_STATUS_DEFAULT,
              "tempList": [], "errMsg": ""}

    if not isImagePath(localPath):
        return result

    try:
        processedPath, width, height = fitImageToMaxSize(localPath, maxSize)
        if processedPath and processedPath != localPath:
            result["path"] = processedPath
            result["tempList"].append(processedPath)
            result["exifStripped"] = EXIF_STRIPPED_YES
            result["processStatus"] = PROCESS_STATUS_DONE
        elif width > 0 and height > 0:
            #未超限但尺寸可读: 尺寸信息仍要落库
            result["width"], result["height"] = width, height
            result["processStatus"] = PROCESS_STATUS_DONE
    except Exception as e:
        result["processStatus"] = PROCESS_STATUS_FAILED
        result["errMsg"] = f"图像规格处理失败: {str(e)}"
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, processImageForUpload failed, localPath:{localPath}, errMsg:{str(e)}")

    return result


def removeTempFiles(tempList):
    """清理处理过程中产生的临时文件(失败不抛异常)"""
    for tmpPath in tempList or []:
        if tmpPath and os.path.isfile(tmpPath):
            try:
                os.remove(tmpPath)
            except Exception:
                pass

#===== 图像处理 end =====


#===== 上传(三后端统一门面) begin =====

def _resolveStorageBucket(fileSystem = ""):
    """取当前后端解析出的**物理桶名**(多桶读取路由用); 语义对齐 ylwzRecvFiles.cmdF0A0:
       延迟导入 fileStorageCommon(会牵出云厂商 SDK); 解析失败回落 \"\"(读取时回落默认桶)。"""
    try:
        from common import fileStorageCommon as comFS
        bucketCode = comFS.chDefaultBucketCode(fileSystem or settings.FILE_SYSTEM_MODE)
        bucketInfo = comFS.resolveBucket(fileSystem or settings.FILE_SYSTEM_MODE, bucketCode = bucketCode)
        if isinstance(bucketInfo, dict):
            return _toStr(bucketInfo.get("bucketName"))
    except Exception as e:
        if _LOG:
            _LOG.warning(f"W: PID:{_processorPID}, resolveStorageBucket failed, errMsg:{str(e)}")
    return ""


def _normalizeFileExt(fileExt = ""):
    """归一扩展名: 兼容 "jpg" / ".JPG" 两种写法; 非法(空/非字母数字/超长)返回 \"\""""
    fileExt = _toStr(fileExt).strip().lstrip(".").lower()
    if fileExt and re.match(r"^[a-z0-9]{1,16}$", fileExt):
        return fileExt
    return ""


def _ensureObjectExt(objectName, fileExt = "", origName = "", localPath = ""):
    """给对象键补齐扩展名(末尾已有扩展名则原样返回, 不臆造)。

    背景(2026-09-24 线上现象「主文件丢扩展名、缩略图有扩展名」):
      上传通道 ylwzRecvFiles.fileHandler → modifyFileName() 曾把 nginx 落下的临时文件改名成
      「无扩展名的 UUID」(如 /data/webserver/temp/8/b16cxxxx), 故 localPath 的 basename 曾天然无扩展名。
      · ylwzRecvFiles.cmdF0A0 旧链路对此有补偿(「如果nginx存储的文件没有扩展名, 用原来名字的扩展名」);
      · contentHub 的 assetadd 路径此前直接用 basename(localPath) 组成对象键 → 丢扩展名;
      · 而 fileStorageCommon.saveWithThumbnail 的缩略图键硬编码 "_thumbnail.jpg" → 缩略图反而有扩展名。
    现状: modifyFileName() 已改为保留扩展名(新收到的文件 localPath 自带扩展名), 本函数仍作为兜底保留 ——
      覆盖「调用方显式传无扩展名 objectName」「前端未回传 fileExt」「接不接受上传通道变化的其它调用方」。
    扩展名取值优先级: fileExt(前端回传) > origName > localPath; 三者都给不出时不补(不臆造类型)。
    """
    objectName = _toStr(objectName)
    if not objectName or os.path.splitext(objectName)[1]:
        return objectName
    ext = (_normalizeFileExt(fileExt)
           or _normalizeFileExt(os.path.splitext(_toStr(origName))[1])
           or _normalizeFileExt(os.path.splitext(_toStr(localPath))[1]))
    if not ext:
        return objectName
    return f"{objectName}.{ext}"


def uploadAssetFile(localPath, objectName = "", origName = "", processFlag = True, maxSize = None,
                    fileExt = ""):
    """上传素材文件(三后端切换由 common/fileStorageCommon.py 门面承担, 本层无厂商分支)。
       返回 dict:
         {"fileID", "thumbnailID", "fileSystem", "storageBucket", "objectName", "origName",
          "width", "height", "exifStripped", "processStatus", "origSizeBytes", "errMsg"}
       fileID 为空表示上传失败(调用方按 D3 处理)。"""
    result = {"fileID": "", "thumbnailID": "", "fileSystem": settings.FILE_SYSTEM_MODE,
              "storageBucket": "", "objectName": "", "origName": "", "width": 0, "height": 0,
              "exifStripped": EXIF_STRIPPED_NO, "processStatus": PROCESS_STATUS_DEFAULT,
              "origSizeBytes": 0, "errMsg": ""}

    tempList = []
    try:
        if not os.path.isfile(localPath):
            result["errMsg"] = f"文件不存在: {localPath}"
            return result

        result["origSizeBytes"] = os.path.getsize(localPath)
        result["origName"] = origName or os.path.basename(localPath)
        #对象键一律补齐扩展名: 上传通道落下的临时文件是无扩展名 UUID, 直接取 basename 会丢扩展名
        result["objectName"] = _ensureObjectExt(
            objectName or f"{misc.getTime()}_{os.path.basename(localPath)}",
            fileExt, result["origName"], localPath)

        uploadPath = localPath
        if processFlag:
            processInfo = processImageForUpload(localPath, maxSize)
            tempList = processInfo.get("tempList", [])
            uploadPath = processInfo.get("path", localPath)
            result["width"] = processInfo.get("width", 0)
            result["height"] = processInfo.get("height", 0)
            result["exifStripped"] = processInfo.get("exifStripped", EXIF_STRIPPED_NO)
            result["processStatus"] = processInfo.get("processStatus", PROCESS_STATUS_DEFAULT)
            result["errMsg"] = processInfo.get("errMsg", "")

        # from common import fileStorageCommon as comFS

        bucketCode = comFS.chDefaultBucketCode(result["fileSystem"])
        #★ 2026-09-24: 对象键补逻辑桶路径前缀(幂等), 使落库 fileID == objectName == 真实 OSS/COS 键。
        #  若不补, 记录只剩 storageBucket(物理桶名)可用; server_02 的 media/artifact 复用同一物理桶
        #  contenthub-private 时会被消歧成 media → 预签名 URL 指向 media/xxx → 图片 404, 素材图库看不到。
        result["objectName"] = comFS.objectKeyWithBucketPrefix(result["objectName"],
                                                               result["fileSystem"], bucketCode, True)
        fileID, thumbnailID = comFS.saveWithThumbnail(uploadPath, result["objectName"],
                                                      privateFlag = True, bucketCode = bucketCode)
        result["fileID"] = _toStr(fileID)
        result["thumbnailID"] = _toStr(thumbnailID)
        result["storageBucket"] = _resolveStorageBucket(result["fileSystem"])

        if not result["fileID"] and _LOG:
            _LOG.error(f"PID:{_processorPID}, uploadAssetFile 上传失败, localPath:{localPath}")
    except Exception as e:
        traceMsg = traceback.format_exc()
        result["processStatus"] = PROCESS_STATUS_FAILED
        result["errMsg"] = f"素材上传异常: {str(e)}"
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, uploadAssetFile errMsg:{e},{traceMsg}")
    finally:
        removeTempFiles(tempList)

    return result


def buildThumbnailForUpload(localPath):
    """单独生成缩略图本地文件(口径 settings.THUMBNAIL_SIZE); 失败返回 ""。
       说明: 主上传路径走 fileStorageCommon.saveWithThumbnail, 由其内部生成并上传缩略图;
             本函数供「先登记后上传」/诊断等需要单独产出缩略图的场景使用。"""
    try:
        # from common import fileStorageCommon as comFS
        return comFS.buildThumbnail(localPath, settings.THUMBNAIL_SIZE)
    except Exception as e:
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, buildThumbnailForUpload failed, localPath:{localPath}, errMsg:{str(e)}")
        return ""

#===== 上传 end =====


#===== 字段校验与归一 begin =====

def validateAssetFields(dataSet, mode = "add", currDataSet = None):
    """素材字段校验 + 归一(纯函数: 不触库、不 IO, 便于静态/单测)。
       入参:
         dataSet       请求数据
         mode          "add" 必填项按新增规则; "modify" 未提供的字段跳过校验(局部更新)
         currDataSet   修改场景的当前记录
       出参: (errCode, rtnField, rtnErrMsgList, saveSet)
         saveSet 仅含需要落库的字段(不含 contentHash / fileID / fileSystem 等由上传流程回填的字段)。
    """
    errList = []
    saveSet = {}
    currDataSet = currDataSet or {}
    isAdd = (mode == "add")

    def addErr(errCode, fieldName, errMsg):
        errList.append((errCode, _fieldLabel(fieldName), errMsg))

    if not isinstance(dataSet, dict):
        return ERR_FIELD_MISSING, _fieldLabel("dataSet"), ["请求数据为空或格式非法"], saveSet

    #1) 元信息字段长度
    for fieldName, maxLen in (("origName", ORIG_NAME_MAX_LEN), ("objectName", OBJECT_NAME_MAX_LEN),
                              ("mimeType", MIME_TYPE_MAX_LEN), ("fileExt", FILE_EXT_MAX_LEN),
                              ("caption", CAPTION_MAX_LEN), ("label", LABEL_MAX_LEN),
                              ("memo", MEMO_MAX_LEN)):
        value = _toStr(dataSet.get(fieldName))
        if value:
            if len(value) > maxLen:
                addErr(ERR_FIELD_TOO_LONG, fieldName,
                       f"{fieldName} 长度={len(value)} 超上限 {maxLen}")
            else:
                saveSet[fieldName] = value.lower() if fieldName == "fileExt" else value

    #2) processStatus / exifStripped(取值合法性)
    processStatus = _toStr(dataSet.get("processStatus")).upper()
    if processStatus:
        if processStatus not in PROCESS_STATUS_LIST:
            addErr(ERR_FIELD_INVALID, "processStatus",
                   f"processStatus 取值非法: {processStatus}, 允许值={PROCESS_STATUS_LIST}")
        else:
            saveSet["processStatus"] = processStatus

    exifStripped = _toStr(dataSet.get("exifStripped"))
    if exifStripped:
        if exifStripped not in (EXIF_STRIPPED_NO, EXIF_STRIPPED_YES):
            addErr(ERR_FIELD_INVALID, "exifStripped",
                   f"exifStripped 取值非法: {exifStripped}, 允许值=['0','1']")
        else:
            saveSet["exifStripped"] = exifStripped

    #3) contentHash 格式(64 位十六进制; 由上传流程计算, 允许调用方直接登记)
    contentHash = _toStr(dataSet.get("contentHash")).lower()
    if contentHash:
        if len(contentHash) != CONTENT_HASH_MAX_LEN or not re.match(r"^[0-9a-f]{64}$", contentHash):
            addErr(ERR_FIELD_INVALID, "contentHash",
                   f"contentHash 格式非法(应为 64 位十六进制 sha256): {contentHash[:16]}...")
        else:
            saveSet["contentHash"] = contentHash
    elif isAdd and not _toStr(dataSet.get("localPath")):
        #既没给本地文件(由上传流程算 hash)也没给 contentHash -> 无法保证内容级去重
        addErr(ERR_FIELD_MISSING, "contentHash",
               "contentHash 为必填字段(或改传 localPath 由服务端计算)")

    #4) 数值列(生成器对数值列异常置 0; 业务层统一约定 0 = 未设置)
    for fieldName in ("width", "height", "derivedWidth", "derivedHeight", "origSizeBytes"):
        if _toStr(dataSet.get(fieldName)) != "":
            saveSet[fieldName] = comMysql.toIntSafe(dataSet.get(fieldName), 0)

    #5) 其余透传字段(空值不落库, 与生成器对空值的跳过语义保持一致)
    for fieldName in ("storagePath", "derivedFileID", "derivedThumbID", "errMsg"):
        value = _toStr(dataSet.get(fieldName))
        if value:
            saveSet[fieldName] = value

    #6) 修改场景的当前记录用于差异提示(不改动字段本身)
    if mode == "modify" and not saveSet and not errList:
        addErr(ERR_FIELD_MISSING, "dataSet", "没有任何需要更新的字段")

    if errList:
        errCode, rtnField, _errMsg = errList[0]
        return errCode, rtnField, [item[2] for item in errList], saveSet

    return "B0", "", [], saveSet


def validateTopicAssetFields(dataSet, mode = "add", currDataSet = None):
    """附图绑定字段校验 + 归一(纯函数)。
       assetKey = {topicID}:{fileID} 由本函数派生, 是 ch_topic_asset 的唯一幂等键。
       出参: (errCode, rtnField, rtnErrMsgList, saveSet, assetKey)"""
    errList = []
    saveSet = {}
    currDataSet = currDataSet or {}
    assetKey = ""
    isAdd = (mode == "add")

    def addErr(errCode, fieldName, errMsg):
        errList.append((errCode, _fieldLabel(fieldName), errMsg))

    if not isinstance(dataSet, dict):
        return ERR_FIELD_MISSING, _fieldLabel("dataSet"), ["请求数据为空或格式非法"], saveSet, assetKey

    #1) topicID(必填, 关联 ch_topic.recID)
    topicID = _toStr(dataSet.get("topicID"))
    if topicID:
        topicIDNum = comMysql.toIntSafe(topicID, 0)
        if topicIDNum <= 0:
            addErr(ERR_FIELD_INVALID, "topicID", f"topicID 非法(应为正整数): {topicID}")
        else:
            saveSet["topicID"] = topicIDNum
    elif isAdd:
        addErr(ERR_FIELD_MISSING, "topicID", "topicID 为必填字段(关联 ch_topic.recID)")

    #2) fileID(必填, 关联 ch_asset.fileID)
    fileID = _toStr(dataSet.get("fileID"))
    if fileID:
        saveSet["fileID"] = fileID
    elif isAdd:
        addErr(ERR_FIELD_MISSING, "fileID", "fileID 为必填字段(关联 ch_asset.fileID)")

    #3) assetKey 幂等键: 由 topicID + fileID 派生(幂等键拼接见主计划 §4)
    currTopicID = _toStr(currDataSet.get("topicID")) or _toStr(saveSet.get("topicID"))
    currFileID = _toStr(currDataSet.get("fileID")) or _toStr(saveSet.get("fileID"))
    if currTopicID and currFileID:
        assetKey = f"{currTopicID}{ASSET_KEY_SEPARATOR}{currFileID}"
        if len(assetKey) > ASSET_KEY_MAX_LEN:
            addErr(ERR_FIELD_TOO_LONG, "assetKey",
                   f"assetKey 长度={len(assetKey)} 超上限 {ASSET_KEY_MAX_LEN}")
        else:
            saveSet["assetKey"] = assetKey

    #4) usageType 语义(cover / body / inline)
    usageType = _toStr(dataSet.get("usageType")).lower()
    if usageType:
        if usageType not in USAGE_TYPE_LIST:
            addErr(ERR_FIELD_INVALID, "usageType",
                   f"usageType 取值非法: {usageType}, 允许值={USAGE_TYPE_LIST}")
        else:
            saveSet["usageType"] = usageType

    #5) sortOrder 排序(越小越靠前)
    if _toStr(dataSet.get("sortOrder")) != "":
        sortOrder = comMysql.toIntSafe(dataSet.get("sortOrder"), SORT_ORDER_DEFAULT)
        if sortOrder < SORT_ORDER_MIN or sortOrder > SORT_ORDER_MAX:
            addErr(ERR_FIELD_OUT_OF_RANGE, "sortOrder",
                   f"sortOrder 取值={sortOrder} 超出区间 [{SORT_ORDER_MIN}, {SORT_ORDER_MAX}]")
        else:
            saveSet["sortOrder"] = sortOrder

    #6) caption / label / memo(空值不落库)
    for fieldName, maxLen in (("caption", CAPTION_MAX_LEN), ("label", LABEL_MAX_LEN),
                              ("memo", MEMO_MAX_LEN)):
        value = _toStr(dataSet.get(fieldName))
        if value:
            if len(value) > maxLen:
                addErr(ERR_FIELD_TOO_LONG, fieldName,
                       f"{fieldName} 长度={len(value)} 超上限 {maxLen}")
            else:
                saveSet[fieldName] = value

    if errList:
        errCode, rtnField, _errMsg = errList[0]
        return errCode, rtnField, [item[2] for item in errList], saveSet, assetKey

    return "B0", "", [], saveSet, assetKey

#===== 字段校验与归一 end =====


#===== 内部查询 begin =====

def _queryOneAsset(recID = "", fileID = "", contentHash = ""):
    """按 recID / fileID / contentHash 取唯一素材记录; 未命中/歧义返回 None"""
    tableName = _tableName()
    dataList = []
    if recID:
        dataList = comMysql.query_ch_asset(tableName, recID = recID)
    elif fileID:
        dataList = comMysql.query_ch_asset(tableName, fileID = fileID)
    elif contentHash:
        dataList = comMysql.query_ch_asset(tableName, contentHash = contentHash)

    if len(dataList) == 1:
        return dataList[0]
    return None


def _queryOneTopicAsset(recID = "", assetKey = "", topicID = "", fileID = ""):
    """按 recID / assetKey(topicID+fileID) 取唯一附图绑定记录; 未命中/歧义返回 None"""
    tableName = _topicAssetTableName()
    dataList = []
    if recID:
        dataList = comMysql.query_ch_topic_asset(tableName, recID = recID)
    elif topicID and fileID:
        dataList = comMysql.query_ch_topic_asset(tableName, topicID = topicID, fileID = fileID)
    elif assetKey:
        parts = assetKey.split(ASSET_KEY_SEPARATOR, 1)
        if len(parts) == 2 and parts[0].isdigit():
            dataList = comMysql.query_ch_topic_asset(tableName, topicID = parts[0], fileID = parts[1])

    if len(dataList) == 1:
        return dataList[0]
    return None

#===== 内部查询 end =====


#===== 素材(ch_asset)业务入口 begin =====

def addAsset(dataSet, sessionIDSet = None):
    """上传并登记素材(contentHash 内容级去重: 命中即复用既有素材, 不产生重复数据)。
       入参:
         localPath   本地待上传文件路径(服务端负责裁剪 / EXIF 剥离 / 缩略图 / 上传)
         或 fileID + contentHash  直接登记「已存在于文件服务」的素材(不重复上传)
       流程: 校验 -> contentHash 去重 -> 上传(三后端门面) -> 幂等落库。"""
    if not isinstance(dataSet, dict):
        dataSet = {}

    loginID = _loginID(sessionIDSet)

    errCode, rtnField, errMsgList, saveSet = validateAssetFields(dataSet, mode = "add")
    if errCode != "B0":
        return _err(errCode, rtnField, errMsgList)

    #1) 内容级去重: 命中即复用(幂等), 直接返回既有记录
    contentHash = _toStr(saveSet.get("contentHash"))
    if contentHash:
        existAsset = _queryOneAsset(contentHash = contentHash)
        if existAsset:
            return _ok(_fillFileUrls({
                "recID": _toStr(existAsset.get("recID")),
                "fileID": _toStr(existAsset.get("fileID")),
                "thumbnailID": _toStr(existAsset.get("thumbnailID")),
                "contentHash": contentHash,
                "dedupHit": "1",
                "data": existAsset,
            }))

    #2) 上传(有 localPath 才走上传; 否则为「已存在文件」直接登记)
    localPath = _toStr(dataSet.get("localPath"))
    if localPath:
        if not os.path.isfile(localPath):
            return _err(ERR_FILE_NOT_FOUND, _fieldLabel("fileID"), [f"本地文件不存在: {localPath}"])

        serverHash = computeContentHash(localPath)
        if not contentHash:
            contentHash = serverHash
            saveSet["contentHash"] = contentHash
        elif serverHash and serverHash != contentHash:
            return _err(ERR_FIELD_INVALID, _fieldLabel("contentHash"),
                        ["contentHash 与本地文件实际内容不一致(疑似篡改或错传)"])

        uploadInfo = uploadAssetFile(localPath, _toStr(saveSet.get("objectName")),
                                     _toStr(saveSet.get("origName")),
                                     fileExt = _toStr(saveSet.get("fileExt")))
        if not uploadInfo.get("fileID"):
            return _err(ERR_FILE_UPLOAD, _fieldLabel("fileID"),
                        [f"素材上传失败: {uploadInfo.get('errMsg') or '文件服务未返回 fileID'}"])

        saveSet["fileID"] = uploadInfo.get("fileID")
        saveSet["thumbnailID"] = uploadInfo.get("thumbnailID", "")
        saveSet["fileSystem"] = uploadInfo.get("fileSystem", settings.FILE_SYSTEM_MODE)
        saveSet["storageBucket"] = uploadInfo.get("storageBucket", "")
        saveSet["objectName"] = uploadInfo.get("objectName", "")
        saveSet["origName"] = uploadInfo.get("origName", "")
        saveSet["origSizeBytes"] = uploadInfo.get("origSizeBytes", 0)
        saveSet["exifStripped"] = uploadInfo.get("exifStripped", EXIF_STRIPPED_NO)
        saveSet["processStatus"] = uploadInfo.get("processStatus", PROCESS_STATUS_DEFAULT)
        if uploadInfo.get("width"):
            saveSet["width"] = uploadInfo.get("width")
        if uploadInfo.get("height"):
            saveSet["height"] = uploadInfo.get("height")
    else:
        #直接登记: 必须给 fileID(已由其他链路上传完毕)
        fileID = _toStr(dataSet.get("fileID"))
        if not fileID:
            return _err(ERR_FIELD_MISSING, _fieldLabel("fileID"),
                        ["fileID 为必填字段(或改传 localPath 由服务端上传)"])
        if not comMysql.toIntSafe(dataSet.get("origSizeBytes"), 0) and not _toStr(dataSet.get("mimeType")):
            #登记路径不强制文件元信息, 但补一个默认处理状态
            pass
        saveSet["fileID"] = fileID
        saveSet["fileSystem"] = _toStr(dataSet.get("fileSystem")) or settings.FILE_SYSTEM_MODE
        saveSet.setdefault("storageBucket", _toStr(dataSet.get("storageBucket")))
        saveSet.setdefault("thumbnailID", _toStr(dataSet.get("thumbnailID")))

    #3) 回填系统字段
    saveSet.setdefault("processStatus", PROCESS_STATUS_DEFAULT)
    saveSet.setdefault("exifStripped", EXIF_STRIPPED_NO)
    saveSet.setdefault("origSizeBytes", 0)
    saveSet["ownerID"] = loginID
    saveSet["regID"] = loginID
    saveSet["regYMDHMS"] = misc.getTime()
    saveSet["delFlag"] = DEL_FLAG_NORMAL

    return _saveAsset(saveSet, contentHash, loginID, mode = "add")


def modifyAsset(dataSet, sessionIDSet = None):
    """修改素材元信息(按 recID 或 fileID 定位; 局部更新, 未提供字段不校验不改动)。
       说明: fileID / contentHash / fileSystem 为落库快照, 不可改(改则 C7)。"""
    if not isinstance(dataSet, dict):
        dataSet = {}

    loginID = _loginID(sessionIDSet)

    currDataSet = _queryOneAsset(_toStr(dataSet.get("recID")), _toStr(dataSet.get("fileID")))
    if not currDataSet:
        return _err(ERR_NO_RECORD, _fieldLabel("recID"),
                    [f"无此素材记录: recID={_toStr(dataSet.get('recID'))}, "
                     f"fileID={_toStr(dataSet.get('fileID'))}"])

    #落库快照字段不可改
    for fieldName in ("fileID", "contentHash", "fileSystem"):
        newValue = _toStr(dataSet.get(fieldName))
        if newValue and newValue != _toStr(currDataSet.get(fieldName)):
            return _err(ERR_FIELD_INVALID, _fieldLabel(fieldName),
                        [f"{fieldName} 不可修改(素材落库快照字段)"])

    errCode, rtnField, errMsgList, saveSet = validateAssetFields(
        dataSet, mode = "modify", currDataSet = currDataSet)
    if errCode != "B0":
        return _err(errCode, rtnField, errMsgList,
                    {"recID": _toStr(currDataSet.get("recID")),
                     "fileID": _toStr(currDataSet.get("fileID"))})

    recID = _toStr(currDataSet.get("recID"))
    saveSet["modifyID"] = loginID
    saveSet["modifyYMDHMS"] = misc.getTime()

    tableName = _tableName()
    try:
        rtn = comMysql.update_ch_asset(tableName, recID, saveSet)
    except Exception as e:
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, modifyAsset recID:{recID}, errMsg:{str(e)}")
        return _err("ERR_GENERAL", "", [f"素材更新异常: {str(e)}"])

    if rtn is None:
        return _err("ERR_GENERAL", "", [f"素材更新失败: recID={recID}"])

    return _ok(_fillFileUrls({"recID": recID, "fileID": _toStr(currDataSet.get("fileID"))}))


def deleteAsset(dataSet, sessionIDSet = None):
    """删除素材(软删除: delFlag="1", 与 query_ch_asset 的 delFlag 过滤一致)。
       说明: 只标记记录, 不删文件服务上的对象; 解绑附图由 deleteTopicAsset 负责。"""
    if not isinstance(dataSet, dict):
        dataSet = {}

    loginID = _loginID(sessionIDSet)

    currDataSet = _queryOneAsset(_toStr(dataSet.get("recID")), _toStr(dataSet.get("fileID")))
    if not currDataSet:
        return _err(ERR_NO_RECORD, _fieldLabel("recID"),
                    [f"无此素材记录: recID={_toStr(dataSet.get('recID'))}, "
                     f"fileID={_toStr(dataSet.get('fileID'))}"])

    recID = _toStr(currDataSet.get("recID"))
    tableName = _tableName()
    saveSet = {"delFlag": DEL_FLAG_DELETED, "modifyID": loginID, "modifyYMDHMS": misc.getTime()}
    rtn = comMysql.update_ch_asset(tableName, recID, saveSet)

    return _ok({"recID": recID, "fileID": _toStr(currDataSet.get("fileID")), "rtn": str(rtn)})


def queryAsset(dataSet, sessionIDSet = None):
    """素材查询(mode=short 走关键列: recID/fileID/thumbnailID/fileExt/origSizeBytes/width/height/processStatus)。
       出参统一经 chCommon.fillFileUrls 把 fileID 转 URL。"""
    if not isinstance(dataSet, dict):
        dataSet = {}

    tableName = _tableName()
    mode = _toStr(dataSet.get("mode")) or "full"
    order = _toStr(dataSet.get("order")) or "create"

    kwargs = {
        "recID": _toStr(dataSet.get("recID")),
        "fileID": _toStr(dataSet.get("fileID")),
        "contentHash": _toStr(dataSet.get("contentHash")),
        "fileSystem": _toStr(dataSet.get("fileSystem")),
        "processStatus": _toStr(dataSet.get("processStatus")),
        "ownerID": _toStr(dataSet.get("ownerID")),
        #★ 2026-09-20: 素材图库 P-04 的「搜索(origName/objectName)」「类型(fileExt)」筛选
        "keyword": _toStr(dataSet.get("keyword")),
        "fileExt": _toStr(dataSet.get("fileExt")),
        "mode": mode,
        "order": order,
    }
    limitNum = _toStr(dataSet.get("limitNum"))
    if limitNum != "":
        kwargs["limitNum"] = limitNum

    try:
        dataList = comMysql.query_ch_asset(tableName, **kwargs)
    except Exception as e:
        return _err("ERR_GENERAL", "", [f"素材查询失败: {str(e)}"])

    return _ok(_fillFileUrls({"data": dataList, "total": len(dataList)}))


def _saveAsset(saveSet, contentHash, loginID, mode = "add", recID = ""):
    """素材落库: 新增按 contentHash 幂等 upsert(contentHash 为 UNIQUE, 内容级去重) / 修改按 recID 定向更新"""
    tableName = _tableName()

    try:
        if mode == "add":
            recID = _toStr(comCh.upsertByUniqueKey(
                tableName, contentHash, saveSet,
                lambda t, v: comMysql.query_ch_asset(t, contentHash = v),
                comMysql.insert_ch_asset,
                comMysql.update_ch_asset))
        else:
            rtn = comMysql.update_ch_asset(tableName, recID, saveSet)
            if rtn is None:
                return _err("ERR_GENERAL", "", [f"素材更新失败: recID={recID}"])
    except Exception as e:
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, _saveAsset mode:{mode}, errMsg:{str(e)}")
        return _err("ERR_GENERAL", "", [f"素材保存异常: {str(e)}"])

    if not recID or comMysql.toIntSafe(recID, 0) <= 0:
        return _err(ERR_DUPLICATE if mode == "add" else ERR_NO_RECORD, _fieldLabel("contentHash"),
                    [f"素材落库失败(mode={mode}, contentHash={contentHash[:16]}...)"])

    assetRecord = _queryOneAsset(recID = recID)
    if not assetRecord:
        return _err(ERR_NO_RECORD, _fieldLabel("recID"), [f"素材落库后回读失败: recID={recID}"])

    rtnData = {"recID": str(recID),
               "fileID": _toStr(assetRecord.get("fileID")),
               "thumbnailID": _toStr(assetRecord.get("thumbnailID")),
               "contentHash": _toStr(assetRecord.get("contentHash")),
               "fileSystem": _toStr(assetRecord.get("fileSystem")),
               "processStatus": _toStr(assetRecord.get("processStatus")),
               "dedupHit": "0",
               "data": assetRecord}

    return _ok(_fillFileUrls(rtnData))

#===== 素材业务入口 end =====


#===== 附图绑定(ch_topic_asset)业务入口 begin =====

def addTopicAsset(dataSet, sessionIDSet = None):
    """附图绑定: assetKey = {topicID}:{fileID} 幂等(重复绑定同一素材不产生重复记录)。
       绑定后同一 usageType(cover) 只保留一条: 新封面会把旧封面降级为 body。"""
    if not isinstance(dataSet, dict):
        dataSet = {}

    loginID = _loginID(sessionIDSet)

    errCode, rtnField, errMsgList, saveSet, assetKey = validateTopicAssetFields(dataSet, mode = "add")
    if errCode != "B0":
        return _err(errCode, rtnField, errMsgList)

    saveSet.setdefault("usageType", USAGE_TYPE_DEFAULT)
    saveSet.setdefault("sortOrder", SORT_ORDER_DEFAULT)
    saveSet["regID"] = loginID
    saveSet["regYMDHMS"] = misc.getTime()
    saveSet["delFlag"] = DEL_FLAG_NORMAL

    #封面唯一: 同一主题的新封面把旧封面降级为 body(usageType 语义约束)
    if _toStr(saveSet.get("usageType")) == "cover":
        demoteOtherCoverAssets(saveSet.get("topicID"), _toStr(saveSet.get("fileID")), loginID)

    return _saveTopicAsset(saveSet, assetKey, saveSet.get("topicID"), _toStr(saveSet.get("fileID")))


def modifyTopicAsset(dataSet, sessionIDSet = None):
    """修改附图绑定(按 recID 或 assetKey 定位): caption / usageType / sortOrder / label / memo 可改;
       topicID / fileID / assetKey 为幂等键, 不可改(改则 C7);
       传 orderList 时批量重排该主题下的附图顺序。"""
    if not isinstance(dataSet, dict):
        dataSet = {}

    loginID = _loginID(sessionIDSet)
    tableName = _topicAssetTableName()

    recID = _toStr(dataSet.get("recID"))
    assetKey = _toStr(dataSet.get("assetKey"))
    currDataSet = _queryOneTopicAsset(recID = recID, assetKey = assetKey)
    if not currDataSet:
        return _err(ERR_NO_RECORD, _fieldLabel("recID"),
                    [f"无此附图绑定记录: recID={recID}, assetKey={assetKey}"])

    recID = _toStr(currDataSet.get("recID"))

    #幂等键不可改
    for fieldName in ("topicID", "fileID", "assetKey"):
        newValue = _toStr(dataSet.get(fieldName))
        if newValue and newValue != _toStr(currDataSet.get(fieldName)):
            return _err(ERR_FIELD_INVALID, _fieldLabel(fieldName),
                        [f"{fieldName} 不可修改(附图绑定的幂等键)"])

    errCode, rtnField, errMsgList, saveSet, _assetKey = validateTopicAssetFields(
        dataSet, mode = "modify", currDataSet = currDataSet)
    if errCode != "B0":
        return _err(errCode, rtnField, errMsgList)

    saveSet.pop("assetKey", None)
    saveSet.pop("topicID", None)
    saveSet.pop("fileID", None)

    #封面唯一: 改判为 cover 时把旧封面降级为 body
    if _toStr(saveSet.get("usageType")) == "cover":
        demoteOtherCoverAssets(currDataSet.get("topicID"), _toStr(currDataSet.get("fileID")), loginID)

    if saveSet:
        saveSet["modifyID"] = loginID
        saveSet["modifyYMDHMS"] = misc.getTime()
        rtn = comMysql.update_ch_topic_asset(tableName, recID, saveSet)
        if rtn is None:
            return _err("ERR_GENERAL", "", [f"附图绑定更新失败: recID={recID}"])

    #批量重排(sortOrder 排序: 越小越靠前)
    orderList = dataSet.get("orderList")
    if isinstance(orderList, list) and orderList:
        reorderTopicAssets(currDataSet.get("topicID"), orderList, loginID)

    return _ok(_fillFileUrls({"recID": recID, "assetKey": _toStr(currDataSet.get("assetKey"))}))


def deleteTopicAsset(dataSet, sessionIDSet = None):
    """解绑附图(软删除: delFlag="1"); 只解绑关联, 不动 ch_asset 里的素材本体。"""
    if not isinstance(dataSet, dict):
        dataSet = {}

    loginID = _loginID(sessionIDSet)
    tableName = _topicAssetTableName()

    currDataSet = _queryOneTopicAsset(_toStr(dataSet.get("recID")), _toStr(dataSet.get("assetKey")))
    if not currDataSet:
        return _err(ERR_NO_RECORD, _fieldLabel("recID"),
                    [f"无此附图绑定记录: recID={_toStr(dataSet.get('recID'))}, "
                     f"assetKey={_toStr(dataSet.get('assetKey'))}"])

    recID = _toStr(currDataSet.get("recID"))
    saveSet = {"delFlag": DEL_FLAG_DELETED, "modifyID": loginID, "modifyYMDHMS": misc.getTime()}
    rtn = comMysql.update_ch_topic_asset(tableName, recID, saveSet)

    return _ok({"recID": recID, "assetKey": _toStr(currDataSet.get("assetKey")), "rtn": str(rtn)})


def queryTopicAsset(dataSet, sessionIDSet = None):
    """附图查询: 按 topicID 列该主题附图(sortOrder 升序) / 按 recID / fileID / usageType 精查。
       出参统一经 chCommon.fillFileUrls 把 fileID 转 URL。"""
    if not isinstance(dataSet, dict):
        dataSet = {}

    tableName = _topicAssetTableName()
    mode = _toStr(dataSet.get("mode")) or "full"

    kwargs = {
        "recID": _toStr(dataSet.get("recID")),
        "topicID": _toStr(dataSet.get("topicID")),
        "fileID": _toStr(dataSet.get("fileID")),
        "usageType": _toStr(dataSet.get("usageType")).lower(),
        "mode": mode,
        "order": _toStr(dataSet.get("order")) or "create",
    }
    limitNum = _toStr(dataSet.get("limitNum"))
    if limitNum != "":
        kwargs["limitNum"] = limitNum

    try:
        dataList = comMysql.query_ch_topic_asset(tableName, **kwargs)
    except Exception as e:
        return _err("ERR_GENERAL", "", [f"附图查询失败: {str(e)}"])

    #sortOrder 排序(越小越靠前); 显式在业务层排序, 不依赖数据层 order 取值口径
    if _toStr(dataSet.get("order")).lower() in ("", "sort", "sortorder"):
        dataList.sort(key = lambda data: comMysql.toIntSafe(data.get("sortOrder"), SORT_ORDER_DEFAULT))

    return _ok(_fillFileUrls({"data": dataList, "total": len(dataList)}))


def reorderTopicAssets(topicID, orderList, loginID = ""):
    """批量重排某主题下附图的 sortOrder(越小越靠前)。
       orderList 元素: {"recID": x, "sortOrder": n} 或 {"fileID": f, "sortOrder": n}。
       返回 {"updated": n}。单个失败不中断其余(记 error 日志)。"""
    tableName = _topicAssetTableName()
    updatedNum = 0

    for item in orderList or []:
        if not isinstance(item, dict):
            continue
        sortOrder = comMysql.toIntSafe(item.get("sortOrder"), SORT_ORDER_DEFAULT)
        if sortOrder < SORT_ORDER_MIN or sortOrder > SORT_ORDER_MAX:
            continue

        recID = _toStr(item.get("recID"))
        if not recID and _toStr(item.get("fileID")):
            dataSet = _queryOneTopicAsset(topicID = _toStr(topicID), fileID = _toStr(item.get("fileID")))
            recID = _toStr((dataSet or {}).get("recID"))
        if not recID:
            continue

        saveSet = {"sortOrder": sortOrder, "modifyID": loginID, "modifyYMDHMS": misc.getTime()}
        try:
            comMysql.update_ch_topic_asset(tableName, recID, saveSet)
            updatedNum += 1
        except Exception as e:
            if _LOG:
                _LOG.error(f"PID:{_processorPID}, reorderTopicAssets recID:{recID}, errMsg:{str(e)}")

    return {"updated": updatedNum}


def demoteOtherCoverAssets(topicID, keepFileID, loginID = ""):
    """封面唯一约束: 把该主题下非 keepFileID 的 cover 全部降级为 body。
       返回 {"demoted": n}。"""
    tableName = _topicAssetTableName()
    demotedNum = 0

    try:
        coverList = comMysql.query_ch_topic_asset(tableName, topicID = _toStr(topicID),
                                                  usageType = "cover", mode = "short")
    except Exception as e:
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, demoteOtherCoverAssets topicID:{topicID}, errMsg:{str(e)}")
        return {"demoted": 0}

    for data in coverList:
        if _toStr(data.get("fileID")) == _toStr(keepFileID):
            continue
        recID = _toStr(data.get("recID"))
        saveSet = {"usageType": "body", "modifyID": loginID, "modifyYMDHMS": misc.getTime()}
        try:
            comMysql.update_ch_topic_asset(tableName, recID, saveSet)
            demotedNum += 1
        except Exception as e:
            if _LOG:
                _LOG.error(f"PID:{_processorPID}, demote cover recID:{recID}, errMsg:{str(e)}")

    return {"demoted": demotedNum}


def _saveTopicAsset(saveSet, assetKey, topicID, fileID):
    """附图绑定落库: assetKey 幂等 upsert(命中更新 / 未命中插入)"""
    tableName = _topicAssetTableName()

    try:
        recID = _toStr(comCh.upsertByUniqueKey(
            tableName, assetKey, saveSet,
            lambda t, v: comMysql.query_ch_topic_asset(t, topicID = topicID, fileID = fileID),
            comMysql.insert_ch_topic_asset,
            comMysql.update_ch_topic_asset))
    except Exception as e:
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, _saveTopicAsset assetKey:{assetKey}, errMsg:{str(e)}")
        return _err("ERR_GENERAL", "", [f"附图绑定保存异常: {str(e)}"])

    if not recID or comMysql.toIntSafe(recID, 0) <= 0:
        return _err(ERR_DUPLICATE, _fieldLabel("assetKey"), [f"附图绑定落库失败: assetKey={assetKey}"])

    topicAssetRecord = _queryOneTopicAsset(recID = recID)
    if not topicAssetRecord:
        return _err(ERR_NO_RECORD, _fieldLabel("recID"), [f"附图绑定落库后回读失败: recID={recID}"])

    rtnData = {"recID": str(recID),
               "assetKey": _toStr(topicAssetRecord.get("assetKey")),
               "topicID": _toStr(topicAssetRecord.get("topicID")),
               "fileID": _toStr(topicAssetRecord.get("fileID")),
               "usageType": _toStr(topicAssetRecord.get("usageType")),
               "sortOrder": _toStr(topicAssetRecord.get("sortOrder")),
               "data": topicAssetRecord}

    return _ok(_fillFileUrls(rtnData))

#===== 附图绑定业务入口 end =====


if __name__ == "__main__":
    pass
    #本地自测(不连库): 只验证纯函数
    print("computeContentHashFromBytes:", computeContentHashFromBytes(b"contenthub"))
    print("isImagePath a.jpg:", isImagePath("a.jpg"), "| a.txt:", isImagePath("a.txt"))
    print("validateAssetFields:", validateAssetFields({"contentHash": "a" * 64}, mode = "add"))
    print("validateTopicAssetFields:", validateTopicAssetFields({"topicID": 1, "fileID": "f1"}, mode = "add"))
