#! /usr/bin/env python3
#encoding: utf-8

#Filename: bucketSettings.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-17
#Description:   多 Bucket 统一解析器 —— 全项目唯一的桶解析入口(纯函数, 无副作用)
#
#见 plan/ylwz文件服务多Bucket.md 第 3.4 节:
#  - getBucketInfo      写入路径: 解析优先级 bucketCode > privateFlag(仅 TENCENT) > DefaultBucketCode
#  - resolveBucketBySnapshot  读取路径: 优先按落库快照路由, 快照缺失回落到默认桶(兼容旧数据)
#  - listBuckets        列出当前环境可用逻辑桶
#
#归一化输出(供适配器/服务层统一消费):
#  {"bucketCode","bucketName","access","pathPrefix","urlBase","fileSystem"}
#
#相对方案原文的两处必要修正(已在本文件实现并加注释):
#  1. SELFFILE 等非多桶后端: _services() 中不存在对应服务, 直接取会 KeyError。
#     按决策 6.5「SELFFILE 仅做语义预留」, 一律解析为 default 桶(物理名 local)。
#  2. 未知 bucketCode: 写入路径**报错**(决策 6.4, 写错桶代价远高于报错); 读取路径保持宽容(不破坏历史数据)。

_VERSION="20260918"


import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

from config import basicSettings as settings


ALIOSS = "ALIOSS"
TENCENT = "TENCENT"
SELFFILE = "SELFFILE"

#支持多桶的后端
_MULTI_BUCKET_MODES = (ALIOSS, TENCENT)

#SELFFILE 的语义预留桶(决策 6.5): 一律 default, 物理名与 ch_asset.storageBucket 的本地约定对齐
_SELFFILE_BUCKET_NAME = "local"
_SELFFILE_BUCKET_CODE = "default"

#TENCENT 的 privateFlag 旧语义映射
_TENCENT_PRIVATE_CODE = "private"
_TENCENT_PUBLIC_CODE = "public"


class BucketConfigError(ValueError):
    """桶配置错误(未知桶码/桶未定义等), 写入路径需显式拒绝而非静默回落"""
    pass


def _services():
    """延迟取配置, 避免与 config 包初始化顺序耦合"""
    from config import aliyunSettings, tencentSettings
    return {
        ALIOSS: aliyunSettings.ALIYUN_OSS_SERVICE,
        TENCENT: tencentSettings.TECENT_COS_SERVICE,
    }


def isMultiBucketSupported(fileSystem=""):
    """该后端是否支持多桶"""
    return (fileSystem or settings.FILE_SYSTEM_MODE) in _MULTI_BUCKET_MODES


def _selffileBucketInfo(fileSystem=SELFFILE):
    """非多桶后端的语义预留桶"""
    return {
        "bucketCode": _SELFFILE_BUCKET_CODE,
        "bucketName": _SELFFILE_BUCKET_NAME,
        "access": "private",
        "pathPrefix": "",
        "urlBase": "",
        "fileSystem": fileSystem,
    }


def _normBucketInfo(fileSystem, bucketCode, rawBucket):
    """把配置里的原始桶定义归一化为统一结构(兼容 ALIOSS 的 UrlBase 与 TENCENT 的 Url)"""
    rawBucket = rawBucket or {}
    return {
        "bucketCode": bucketCode,
        "bucketName": rawBucket.get("BucketName", ""),
        "access": rawBucket.get("Access", "private"),
        "pathPrefix": rawBucket.get("PathPrefix", "") or "",
        "urlBase": rawBucket.get("UrlBase", rawBucket.get("Url", "")) or "",
        "fileSystem": fileSystem,
    }


def listBuckets(fileSystem=""):
    """列出当前环境(或指定后端)的逻辑桶原始定义 {bucketCode: {BucketName, Access, PathPrefix, ...}}
    非多桶后端返回空 dict"""
    fileSystem = fileSystem or settings.FILE_SYSTEM_MODE
    if not isMultiBucketSupported(fileSystem):
        return {}
    svc = _services().get(fileSystem, {})
    buckets = svc.get("Buckets", {}) if isinstance(svc, dict) else {}
    return buckets or {}


def getDefaultBucketCode(fileSystem=""):
    """取该后端的默认逻辑桶码"""
    fileSystem = fileSystem or settings.FILE_SYSTEM_MODE
    if not isMultiBucketSupported(fileSystem):
        return _SELFFILE_BUCKET_CODE
    svc = _services().get(fileSystem, {})
    if isinstance(svc, dict) and svc.get("DefaultBucketCode"):
        return svc["DefaultBucketCode"]
    buckets = listBuckets(fileSystem)
    return list(buckets.keys())[0] if buckets else _SELFFILE_BUCKET_CODE


def listBucketInfos(fileSystem=""):
    """列出归一化后的桶信息清单(供 F9A0 诊断使用, 不含任何密钥)"""
    fileSystem = fileSystem or settings.FILE_SYSTEM_MODE
    if not isMultiBucketSupported(fileSystem):
        return [_selffileBucketInfo(fileSystem)]
    buckets = listBuckets(fileSystem)
    return [_normBucketInfo(fileSystem, code, raw) for code, raw in buckets.items()]


def getBucketInfo(fileSystem="", bucketCode="", privateFlag=False):
    """写入路径的桶解析(决策 6.2①: bucketCode 优先, privateFlag 仅作 fallback)
    返回 {"bucketCode","bucketName","access","pathPrefix","urlBase","fileSystem"}
    未知 bucketCode: 抛 BucketConfigError(决策 6.4, 不静默回落)
    """
    fileSystem = fileSystem or settings.FILE_SYSTEM_MODE
    if not isMultiBucketSupported(fileSystem):
        #决策 6.5: 非多桶后端一律 default
        return _selffileBucketInfo(fileSystem)

    svc = _services().get(fileSystem, {})
    buckets = svc.get("Buckets", {}) if isinstance(svc, dict) else {}

    if bucketCode:
        if bucketCode not in buckets:
            raise BucketConfigError(
                f"unknown bucketCode: '{bucketCode}' for fileSystem: '{fileSystem}', "
                f"available: {sorted(buckets.keys())}")
        code = bucketCode
    elif fileSystem == TENCENT:
        #旧语义 fallback: privateFlag=True → private, False → public
        code = _TENCENT_PRIVATE_CODE if privateFlag else _TENCENT_PUBLIC_CODE
        if code not in buckets:
            code = getDefaultBucketCode(fileSystem)
    elif fileSystem == ALIOSS:
        #决策 6.3: ALIOSS 接受并忽略 privateFlag, 消除「传了没用」的隐式陷阱
        code = getDefaultBucketCode(fileSystem)
    else:
        code = getDefaultBucketCode(fileSystem)

    if code not in buckets:
        raise BucketConfigError(
            f"bucketCode: '{code}' not defined for fileSystem: '{fileSystem}', "
            f"available: {sorted(buckets.keys())}")

    return _normBucketInfo(fileSystem, code, buckets[code])


def _pickSharedBucket(fields, objectName=""):
    """多个逻辑桶复用同一物理桶时的消歧, fields 为 [(bucketCode, rawBucket), ...]
    优先级: 对象键前缀命中 > 空前缀桶 > 首个匹配(维持旧行为)
    必要性: 适配器在读取时也会按 pathPrefix 幂等补前缀, 桶码选错会把已含其它前缀的
            对象键拼成错误 key(例: artifact/x.jpg → media/artifact/x.jpg), 导致读不到。
    """
    if objectName:
        for code, raw in fields:
            prefix = (raw or {}).get("PathPrefix", "") or ""
            if prefix and objectName.startswith(prefix):
                return code, raw
        #空前缀桶等价于「不补前缀」, 对已含前缀的对象键最安全
        for code, raw in fields:
            if not ((raw or {}).get("PathPrefix", "") or ""):
                return code, raw
    return fields[0]


def resolveBucketBySnapshot(fileSystem, storageBucket="", bucketCode="", privateFlag=True, objectName=""):
    """读取路径的桶路由: bucketCode 优先, 其次按 storageBucket(物理桶名) 反查, 最后回落默认桶
    (旧数据无桶快照时回落默认桶 → 读得到)
    privateFlag 仅在完全无快照时参与回落(TENCENT 旧语义: True → private)
    objectName: 可选, 对象键(读取路径请传 fileID)。仅在「多个逻辑桶码复用同一物理桶」时用于消歧;
                传入不会改变既有正确结果(前缀命中或补空前缀均为幂等)
    ★ 2026-09-24: 无 bucketCode、也无 storageBucket(或物理桶名无法区分)时, 先按对象键前缀命中逻辑桶,
      再回落默认桶。原因: ch_topic_asset / ch_topic 等出参没有 storageBucket 列, 只能靠对象键前缀
      判定归属; server_02 的 media 与 artifact 复用同一物理桶 contenthub-private, 仅凭物理桶名
      无法区分。写入侧已改为「落库对象键含路径前缀」(fileStorageCommon.objectKeyWithBucketPrefix),
      因此带前缀的键是自描述的; 历史无前缀对象键匹配不到任何前缀 → 行为与改造前一致。
    """
    fileSystem = fileSystem or settings.FILE_SYSTEM_MODE
    if not isMultiBucketSupported(fileSystem):
        return _selffileBucketInfo(fileSystem)

    buckets = listBuckets(fileSystem)

    if bucketCode and bucketCode in buckets:
        return _normBucketInfo(fileSystem, bucketCode, buckets[bucketCode])

    if storageBucket:
        fields = [(code, raw) for code, raw in buckets.items()
                  if (raw or {}).get("BucketName") == storageBucket]
        if fields:
            code, raw = _pickSharedBucket(fields, objectName)
            return _normBucketInfo(fileSystem, code, raw)

    #★ 2026-09-24: 无快照可用(或快照无法区分)时, 按对象键前缀命中逻辑桶(前缀即归属, 自描述);
    #  历史无前缀对象键匹配不到任何前缀 → 仍回落默认桶, 旧数据读取行为不变。
    if objectName:
        for code, raw in buckets.items():
            prefix = (raw or {}).get("PathPrefix", "") or ""
            if prefix and objectName.startswith(prefix):
                return _normBucketInfo(fileSystem, code, raw)

    return getBucketInfo(fileSystem, "", privateFlag)


def applyPathPrefix(bucketInfo, objectName):
    """给对象键补逻辑桶的路径前缀(幂等: 已带前缀则不重复拼接)
    设计说明: 适配器与本函数共用同一实现, 服务层先用本函数算出最终 objectName 并落库,
    适配器侧再次调用不会二次拼接 → 满足「落库 objectName 已含路径前缀」的约定
    """
    if not objectName:
        return objectName
    prefix = (bucketInfo or {}).get("pathPrefix", "") or ""
    if prefix and not objectName.startswith(prefix):
        return prefix + objectName
    return objectName


if __name__ == "__main__":
    print("_SYS FILE_SYSTEM_MODE:", settings.FILE_SYSTEM_MODE)
    print("ALIOSS buckets:", sorted(listBuckets(ALIOSS).keys()))
    print("ALIOSS default:", getBucketInfo(ALIOSS))
    print("TENCENT private:", getBucketInfo(TENCENT, privateFlag=True))
    print("TENCENT public:", getBucketInfo(TENCENT, privateFlag=False))
    print("ALIOSS media:", getBucketInfo(ALIOSS, "media"))
    print("SELFFILE:", getBucketInfo(SELFFILE))
