#! /usr/bin/env python3
#encoding: utf-8

#Filename: fileStorageCommon.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   文件存储统一门面(三后端签名归一化 shim + 多桶解析贯穿)
#
#设计依据:
#  - plan/contentHub开发计划.md 3.3.3/3.3.4 (统一接口 + shim + 工厂门面)
#  - plan/ylwz文件服务多Bucket.md 4.5 D1 (saveFile/delFile/getTempLocation 尾部追加 bucketCode)
#
#约束:
#  1. 业务层只调本模块的函数, 不得直接 import 三个适配器(红线 R2: 文件后端配置驱动)
#  2. 三适配器源码保持与 ylwz 同源, 签名差异一律在本文件的 shim 内消化
#  3. 本模块不做任何桶名字面量判断, 桶选择全部经 config/bucketSettings.py

_VERSION="20260918"

import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#setting files
from config import basicSettings as settings

#多桶统一解析入口
from config import bucketSettings as comBucket

#三个后端适配器
from common import aliyunOSS as OSS
from common import tencentCOS as COS
from common import selfFileCommon as SF


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    _LOG = misc.setLogNew("FILESTORAGE", "filestoragelog")

_DEBUG = settings._DEBUG


#========== shim 层: 消化三适配器的签名/返回值差异 begin ==========
#说明: 适配器差异是客观事实(见主计划 D2), shim 只做「参数顺序/形态 + 返回值」归一,
#      不改适配器源码; 每个 shim 暴露统一方法: upload/download/exist/info/delete/tempUrl/listObjects

class _AliossShim:
    """aliyunOSS 实测签名: uploadFile(objName, fileName, downloadName=""), 返回 bool"""
    mode = "ALIOSS"

    @staticmethod
    def upload(localPath, objectName, privateFlag=False, bucketCode=""):
        return objectName if OSS.uploadFile(objectName, localPath, bucketCode=bucketCode) else ""

    @staticmethod
    def download(fileID, targetPath, privateFlag=False, bucketCode=""):
        return targetPath if OSS.downloadFile(fileID, targetPath, bucketCode=bucketCode) else ""

    @staticmethod
    def exist(fileID, privateFlag=False, bucketCode=""):
        return OSS.existFile(fileID, bucketCode=bucketCode)

    @staticmethod
    def info(fileID, privateFlag=False, bucketCode=""):
        return OSS.getFileInfo(fileID, bucketCode=bucketCode)

    @staticmethod
    def delete(fileID, privateFlag=False, bucketCode=""):
        return OSS.deleteFile(fileID, bucketCode=bucketCode)

    @staticmethod
    def tempUrl(fileID, privateFlag=False, targetFileName="", localAddress=False,
                sourceServerAddr="", bucketCode=""):
        return OSS.genFileTempUrl(fileID, bucketCode=bucketCode)

    @staticmethod
    def listObjects(maxNum=1000, privateFlag=False, bucketCode=""):
        #aliyunOSS 适配器未提供 listFiles, 保持现状返回空清单(需要时再补, 不臆造实现)
        return []


class _CosShim:
    """tencentCOS 实测签名与统一接口基本一致, 返回 bool"""
    mode = "TENCENT"

    @staticmethod
    def upload(localPath, objectName, privateFlag=False, bucketCode=""):
        return objectName if COS.uploadFile(objectName, localPath, privateFlag, bucketCode) else ""

    @staticmethod
    def download(fileID, targetPath, privateFlag=False, bucketCode=""):
        return targetPath if COS.downloadFile(fileID, targetPath, privateFlag, bucketCode) else ""

    @staticmethod
    def exist(fileID, privateFlag=False, bucketCode=""):
        return COS.existFile(fileID, privateFlag, bucketCode)

    @staticmethod
    def info(fileID, privateFlag=False, bucketCode=""):
        return COS.getFileInfo(fileID, privateFlag, bucketCode)

    @staticmethod
    def delete(fileID, privateFlag=False, bucketCode=""):
        return COS.deleteFile(fileID, privateFlag, bucketCode)

    @staticmethod
    def tempUrl(fileID, privateFlag=False, targetFileName="", localAddress=False,
                sourceServerAddr="", bucketCode=""):
        return COS.genFileTempUrl(fileID, privateFlag, bucketCode)

    @staticmethod
    def listObjects(maxNum=1000, privateFlag=False, bucketCode=""):
        return COS.listFiles(maxNum, privateFlag, bucketCode)


class _SelfShim:
    """selfFileCommon 实测签名: uploadFile(fileInfo) 返回生成的 fileID; downloadFile 返回落盘路径"""
    mode = "SELFFILE"

    @staticmethod
    def upload(localPath, objectName="", privateFlag=False, bucketCode=""):
        fileInfo = {
            "serverName": settings._SYS_SERVER_NAME,
            "fileSystem": "SELFFILE",
            "description": "",
            "fileName": localPath,
            "oldFileName": os.path.basename(objectName or localPath),
            "objectName": objectName or os.path.basename(localPath),
            "fileExtName": os.path.splitext(localPath)[1],
            "fileSize": os.path.getsize(localPath) if os.path.isfile(localPath) else 0,
            "fileUrl": "",
            "uploadYMDHMS": misc.getTime(),
            "requestType": "",
            "prefix": "",
            "compressFlag": "N",
            #多桶语义预留(决策 6.5): SELFFILE 一律 default 桶, 物理名 local
            "storageBucket": comBucket.getBucketInfo("SELFFILE")["bucketName"],
            "bucketCode": comBucket.getBucketInfo("SELFFILE")["bucketCode"],
        }
        return SF.uploadFile(fileInfo, privateFlag, bucketCode)

    @staticmethod
    def download(fileID, targetPath, privateFlag=False, bucketCode=""):
        return SF.downloadFile(fileID, targetPath, privateFlag, bucketCode=bucketCode)

    @staticmethod
    def exist(fileID, privateFlag=False, bucketCode=""):
        return SF.existFile(fileID, privateFlag, bucketCode)

    @staticmethod
    def info(fileID, privateFlag=False, bucketCode=""):
        return SF.getFileInfo(fileID, privateFlag, bucketCode)

    @staticmethod
    def delete(fileID, privateFlag=False, bucketCode=""):
        return SF.deleteFile(fileID, privateFlag, bucketCode)

    @staticmethod
    def tempUrl(fileID, privateFlag=False, targetFileName="", localAddress=False,
                sourceServerAddr="", bucketCode=""):
        return SF.genFileTempUrl(fileID, targetFileName, privateFlag, localAddress,
                                 sourceServerAddr=sourceServerAddr, bucketCode=bucketCode)

    @staticmethod
    def listObjects(maxNum=1000, privateFlag=False, bucketCode=""):
        return SF.listFiles(maxNum, privateFlag, bucketCode)


_SHIMS = {
    "ALIOSS": _AliossShim,
    "TENCENT": _CosShim,
    "SELFFILE": _SelfShim,
}

_ADAPTERS = {
    "ALIOSS": OSS,
    "TENCENT": COS,
    "SELFFILE": SF,
}
#========== shim 层 end ==========


def getStorageMode(mode=""):
    """解析当前文件后端(缺省取全局 FILE_SYSTEM_MODE)"""
    return mode or settings.FILE_SYSTEM_MODE


def getStorage(mode=""):
    """按 FILE_SYSTEM_MODE 返回对应适配器模块(对外兼容出口)"""
    return _ADAPTERS.get(getStorageMode(mode), SF)


def _getShim(mode=""):
    return _SHIMS.get(getStorageMode(mode), _SelfShim)


def resolveBucket(fileSystem="", storageBucket="", bucketCode="", privateFlag=True, objectName=""):
    """对外暴露桶解析能力(读取路径: 优先快照, 缺失回落默认桶)
    objectName: 可选, 对象键(fileID); 仅当多个逻辑桶码复用同一物理桶时用于消歧"""
    return comBucket.resolveBucketBySnapshot(fileSystem or getStorageMode(), storageBucket, bucketCode, privateFlag, objectName)


def getBucketInfo(fileSystem="", bucketCode="", privateFlag=False):
    """对外暴露桶解析能力(写入路径: 未知桶码抛 BucketConfigError)"""
    return comBucket.getBucketInfo(fileSystem or getStorageMode(), bucketCode, privateFlag)


def chDefaultBucketCode(fileSystem=""):
    """contentHub 这一「调用方」的缺省逻辑桶码(多桶写入路径缺省值)。

    设计(见 plan/ylwz文件服务多Bucket.md 与 contentHub 改造建议):
      - 非多桶后端(SELFFILE 等): 桶码无意义, 返回 ""(与改造前一致, 由适配器回落语义预留桶);
      - 多桶后端: 优先取 config.basicSettings.FILE_SYSTEM_BUCKET_NAME(本项目偏好桶, 如 "artifact");
        偏好为空时回落 bucketSettings 全局默认(不影响 recvFiles 对其他服务的默认);
      - 偏好桶码不在可用清单时, 显式抛 BucketConfigError(早失败, 不静默落错桶;
        复用决策 6.4「写错桶代价远高于报错」哲学)。
    该值与 _resolveStorageBucket / 各上传调用点共用, 保证「上云桶」与「落库快照」一致。
    """
    fileSystem = fileSystem or settings.FILE_SYSTEM_MODE
    if not comBucket.isMultiBucketSupported(fileSystem):
        return ""
    preferred = str(getattr(settings, "FILE_SYSTEM_BUCKET_NAME", "") or "").strip()
    if not preferred:
        return comBucket.getDefaultBucketCode(fileSystem)
    buckets = comBucket.listBuckets(fileSystem)
    if preferred not in buckets:
        raise comBucket.BucketConfigError(
            f"FILE_SYSTEM_BUCKET_NAME '{preferred}' 不在可用桶清单 {sorted(buckets.keys())} "
            f"(fileSystem='{fileSystem}')")
    return preferred


def chCheckStorageConfig():
    """启动自检: 校验 contentHub 项目缺省桶 basicSettings.FILE_SYSTEM_BUCKET_NAME 存在于可用桶清单。

    设计:
      - 非多桶后端(SELFFILE 等): 桶码无意义, 直接放行(返回 True);
      - 多桶后端且 FILE_SYSTEM_BUCKET_NAME 为空: 放行(回落 bucketSettings 全局默认, 由上传兜底);
      - 多桶后端且 FILE_SYSTEM_BUCKET_NAME 非空但不在可用桶清单: 抛 BucketConfigError,
        使进程在启动期即失败(不让错误推迟到第一次上传才暴露, 符合「写错桶代价远高于报错」)。
    与 chDefaultBucketCode 共用同一判定逻辑; 本函数供模块导入期/启动钩子调用。
    """
    fileSystem = settings.FILE_SYSTEM_MODE
    if not comBucket.isMultiBucketSupported(fileSystem):
        return True
    preferred = str(getattr(settings, "FILE_SYSTEM_BUCKET_NAME", "") or "").strip()
    if not preferred:
        return True
    buckets = comBucket.listBuckets(fileSystem)
    if preferred not in buckets:
        raise comBucket.BucketConfigError(
            f"[chCheckStorageConfig] FILE_SYSTEM_BUCKET_NAME '{preferred}' 不在可用桶清单 "
            f"{sorted(buckets.keys())} (fileSystem='{fileSystem}'), 请修正 basicSettings.py")
    return True


def listBucketInfos(fileSystem=""):
    """列出可用桶清单(诊断用, 不含密钥)"""
    return comBucket.listBucketInfos(fileSystem or getStorageMode())


#========== 业务层统一接口 begin ==========

def objectKeyWithBucketPrefix(objectName, mode="", bucketCode="", privateFlag=False):
    """给对象键补「逻辑桶路径前缀」(幂等), 对齐 ylwzRecvFiles.cmdF0A0 的落库口径。

    必要性(2026-09-24 server_02 现象: 素材图库/主题附图里新上传的图 URL 404):
      server_02 的 media 与 artifact 复用同一物理桶 contenthub-private, 只靠 bucketCode 在写入时区分;
      读取时记录的 storageBucket 只是**物理桶名**(contenthub-private 同时命中 media/artifact),
      无法区分, 只能靠对象键前缀消歧(bucketSettings._pickSharedBucket: 前缀命中 > 空前缀桶 > 首个匹配)。
      若落库的对象键不含前缀, 消歧会命中字典中靠前的 media(或直接回落默认桶) → URL 被签成
      media/xxx 或 另一个物理桶/xxx → 对象不存在 → 图片打不开。
    cmdF0A0(旧链路)已按「落库 objectName 已含路径前缀」实现(见 plan/ylwz文件服务多Bucket.md 3.4),
    本门面此前漏了这一步: 适配器只在 PUT 时补前缀, 回显给调用方落库的仍是未加前缀的键。
    幂等: 适配器侧再次 applyPathPrefix 不会二次拼接, 故 OSS/COS 对象键与改造前逐字节一致。
    """
    objectName = str(objectName or "")
    if not objectName:
        return objectName
    try:
        bucketInfo = comBucket.getBucketInfo(getStorageMode(mode), bucketCode, privateFlag)
    except comBucket.BucketConfigError as e:
        #未知桶码: 由适配器按其既有语义报错(此处不改变行为, 只记日志)
        if _LOG:
            _LOG.warning(f"W: PID:{_processorPID}, objectKeyWithBucketPrefix 桶解析失败, "
                         f"bucketCode:{bucketCode}, errMsg:{str(e)}")
        return objectName
    return comBucket.applyPathPrefix(bucketInfo, objectName)


def saveFile(localPath, objectName="", privateFlag=False, mode="", bucketCode=""):
    """保存文件, 返回 fileID(字符串), 失败返回 ""
    返回值约定: OSS/COS 回显**最终对象键**(已含逻辑桶路径前缀, 读取路由靠它消歧);
                SELFFILE 为适配器生成的 {分片}/file{uuid}(其桶前缀为空, 不受影响)
    """
    shim = _getShim(mode)
    objectName = objectKeyWithBucketPrefix(objectName, mode, bucketCode, privateFlag)
    fileID = shim.upload(localPath, objectName, privateFlag, bucketCode)
    if _DEBUG:
        _LOG.info(f"PID:{_processorPID}, saveFile mode:{shim.mode}, bucketCode:{bucketCode}, objectName:{objectName}, fileID:{fileID}")
    return fileID


def downloadFile(fileID, targetPath, privateFlag=False, mode="", bucketCode=""):
    """取回本地, 返回落盘路径, 失败返回 \"\""""
    return _getShim(mode).download(fileID, targetPath, privateFlag, bucketCode)


def existFile(fileID, privateFlag=False, mode="", bucketCode=""):
    """存在性检查"""
    return _getShim(mode).exist(fileID, privateFlag, bucketCode)


def getFileInfo(fileID, privateFlag=False, mode="", bucketCode=""):
    """取文件元信息(dict)"""
    return _getShim(mode).info(fileID, privateFlag, bucketCode)


def delFile(fileID, privateFlag=False, mode="", bucketCode=""):
    """删除文件(D1: 尾部可选参数 bucketCode)"""
    return _getShim(mode).delete(fileID, privateFlag, bucketCode)


def listFiles(maxNum=1000, privateFlag=False, mode="", bucketCode=""):
    """列文件清单"""
    return _getShim(mode).listObjects(maxNum, privateFlag, bucketCode)


def buildThumbnail(localPath, thumbSize=None):
    """生成缩略图, 返回缩略图文件路径; 失败返回 \"\""""
    result = ""
    try:
        from PIL import Image
        if not thumbSize:
            thumbSize = settings.THUMBNAIL_SIZE
        if not thumbSize:
            return ""
        fileRoot, _ext = os.path.splitext(localPath)
        thumbPath = f"{fileRoot}_thumbnail.jpg"
        im = Image.open(localPath)
        im.thumbnail(thumbSize)
        im = im.convert("RGB")
        im.save(thumbPath, "JPEG")
        im.close()
        result = thumbPath
    except Exception as e:
        _LOG.error(f"PID:{_processorPID}, buildThumbnail errMsg:{str(e)}")
    return result


def saveWithThumbnail(localPath, objectName="", privateFlag=False, mode="", bucketCode=""):
    """先出缩略图再存主图, 返回 (fileID, thumbnailID); 缩略图失败时 thumbnailID 为 ""

    缩略图键 = 主对象键去扩展名后 + "_thumbnail.jpg"(缩略图恒为 JPEG 编码), 与
    ylwzRecvFiles.cmdF0A0 的 `objRoot + "_thumbnail" + fileExt` 口径一致;
    此前硬编码 `objectName + "_thumbnail.jpg"`, 主键一旦带扩展名会拼出 "x.jpg_thumbnail.jpg"。
    """
    thumbPath = buildThumbnail(localPath)
    thumbnailID = ""
    if thumbPath:
        baseName = objectName or os.path.basename(localPath)
        thumbRoot = os.path.splitext(baseName)[0] or baseName
        thumbName = f"{thumbRoot}_thumbnail.jpg"
        thumbnailID = saveFile(thumbPath, thumbName, privateFlag, mode, bucketCode)
    fileID = saveFile(localPath, objectName, privateFlag, mode, bucketCode)
    return fileID, thumbnailID


def getFileTempUrl(fileID, privateFlag=False, targetFileName="", localAddress=False,
                   sourceServerAddr="", mode="", bucketCode=""):
    """fileID → 可访问 URL(不做本地中转)"""
    if not fileID or fileID[:4] == "http":
        return fileID
    return _getShim(mode).tempUrl(fileID, privateFlag, targetFileName, localAddress,
                                  sourceServerAddr, bucketCode)


def getTempLocation(fileID, privateFlag=True, localAccess=False, localAddress=False,
                    targetFileName="", sourceServerAddr="", mode="",
                    bucketCode="", storageBucket=""):
    """兼容旧体系入口(D1): fileID 已是 http 则原样返回;
    多桶路由优先级: 入参 bucketCode > 记录快照 storageBucket > 默认桶。
    说明: localAccess(云端本地中转)由 ylwzRecvFiles.getTempLocation 承担, 门面仅提供直连URL;
          localAddress/sourceServerAddr 仅对 SELFFILE 生效。
    """
    if not fileID or fileID[:4] == "http":
        return fileID
    fileSystem = getStorageMode(mode)
    #objectName=fileID: 多个逻辑桶共用同一物理桶时按对象键前缀消歧, 避免拼错前缀读不到
    bucketInfo = comBucket.resolveBucketBySnapshot(fileSystem, storageBucket, bucketCode, privateFlag, fileID)
    return _getShim(fileSystem).tempUrl(fileID, privateFlag, targetFileName, localAddress,
                                        sourceServerAddr, bucketInfo["bucketCode"])

#========== 业务层统一接口 end ==========


#========== 启动自检 begin ==========
# 模块导入期即校验 contentHub 项目缺省桶(FILE_SYSTEM_BUCKET_NAME)在可用桶清单内;
# 非多桶后端(SELFFILE)放行, 多桶后端配置非法则抛 BucketConfigError 使进程启动失败。
# 所有进程入口(chAPI / mcp_entry / schedule 等)均 transitively 导入本模块, 自检覆盖全进程。
chCheckStorageConfig()
#========== 启动自检 end ==========


if __name__ == "__main__":
    print("_SYS:", settings._SYS)
    print("FILE_SYSTEM_MODE:", settings.FILE_SYSTEM_MODE)
    print("buckets:", listBucketInfos())
