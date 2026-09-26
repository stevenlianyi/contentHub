#! /usr/bin/env python
#encoding: utf-8

#Filename: tencentCOS.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-17
# https://cloud.tencent.com/document/product/436/12269
# pip install -U cos-python-sdk-v5
#Description:   腾讯云COS功能, 类似 阿里云OSS功能(多 Bucket 版)
#
#多桶改造(见 plan/ylwz文件服务多Bucket.md 第 4.3 节 B1-B5):
#  B1 桶名常量保留为兼容出口
#  B2 新增 _resolveBucket(privateFlag, bucketCode) 统一解析
#  B3 各处桶选择改为 _resolveBucket(...)["bucketName"]
#  B4 genFileTempUrl/genFilePublicUrl 域名改用 bucketInfo["urlBase"]
#  B5 全部对外函数尾部追加可选参数 bucketCode=""
#  追加对称能力: 对象键幂等补逻辑桶路径前缀(与 aliyunOSS 后端语义对齐, 默认桶前缀为空→零回归)

_VERSION="20260918"

_DEBUG=True

import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import traceback

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#setting files
from config import tencentSettings as settings

#tencent service
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client

if "_TESTLOG" not in dir() or not _TESTLOG:
    _TESTLOG = misc.setLogNew("TENCENT", "recvfileslog")
    systemVersion = str(sys.version_info.major) + "." + str(sys.version_info.minor ) + "." + str(sys.version_info.micro )
    _TESTLOG.info("python version:[%s], code version:[%s]" %(systemVersion, _VERSION))

_DEBUG =  settings._DEBUG
_DEBUG =  True
# command part

secretID = settings.TECENT_COS_SERVICE["secretId"]      # 替换为用户的 secretId
secretKey = settings.TECENT_COS_SERVICE["secretKey"]       # 替换为用户的 secretKey
regionID = settings.TECENT_COS_SERVICE["regionId"]      # 替换为用户的 Region https://cloud.tencent.com/document/product/436/6224
token = None                # 使用临时密钥需要传入 Token，默认为空，可不填
scheme = 'https'            # 指定使用 http/https 协议来访问 COS，默认为 https，可不填
#兼容保留出口(语义与旧版一致: privateFlag=True → privateBucketName)
#⚠️ 新增/切换桶只改 config/tencentSettings.py 的 Buckets, 不在本文件出现任何桶名字面量
bucketName = settings.TECENT_COS_SERVICE["bucketName"] 
privateBucketName =  settings.TECENT_COS_SERVICE["privateBucketName"] 

txCOSConfig = CosConfig(Region=regionID, SecretId=secretID, SecretKey=secretKey, Token=token, Scheme=scheme)

bucketWrite = CosS3Client(txCOSConfig)
bucketRead = CosS3Client(txCOSConfig)

# <yourLocalFile>由本地文件路径加文件名包括后缀组成，例如/users/local/myfile.txt


#—— 多桶解析 begin ——
#延迟 import config.bucketSettings, 避免与 config 包初始化顺序耦合(方案 B2)
def _resolveBucket(privateFlag = False, bucketCode = ""):
    """解析目标桶: bucketCode 优先, 缺失时按 privateFlag 旧语义回落(private→private / public→public)"""
    from config import bucketSettings as comBucket
    return comBucket.getBucketInfo("TENCENT", bucketCode, privateFlag)


def _resolveBucketAndKey(keyName, privateFlag = False, bucketCode = ""):
    """解析目标桶并幂等补逻辑桶路径前缀, 返回 (bucketInfo, objectKey)"""
    from config import bucketSettings as comBucket
    bucketInfo = comBucket.getBucketInfo("TENCENT", bucketCode, privateFlag)
    return bucketInfo, comBucket.applyPathPrefix(bucketInfo, keyName)
#—— 多桶解析 end ——


def uploadFile(keyName, fileName, privateFlag = False, bucketCode = ""):
    #_TESTLOG.info("%s: %s %s" % ("uploadFile", keyName, fileName, ))
    result = False
    try:
        bucketInfo, objectKey = _resolveBucketAndKey(keyName, privateFlag, bucketCode)
    
        response = bucketWrite.upload_file(
            Bucket = bucketInfo["bucketName"], 
            LocalFilePath = fileName, 
            Key = objectKey, 
            PartSize = 1, 
            MAXThread = 10, 
            EnableMD5 = False
            )

        #_TESTLOG.info("%s: %s %s %s" % ("uploadFile", keyName, fileName, str(response)))

        if isinstance(response, dict):
            ETag = response.get("ETag")
            if ETag:
                result = True
    except Exception as e:
        f = sys._getframe().f_back
        errMsg = '%s' % (keyName)
        #_TESTLOG.error( 'getTempLocation %s, %s' %(errMsg, traceback.format_exc()))

        pass
        
    return result

    
def downloadFile(keyName, fileName, privateFlag = False, bucketCode = ""):
    result = False
    try:
        bucketInfo, objectKey = _resolveBucketAndKey(keyName, privateFlag, bucketCode)

        response = bucketRead.get_object(
            Bucket = bucketInfo["bucketName"], 
            Key = objectKey
            )
        if response != {}:
            result = True
            response['Body'].get_stream_to_file(fileName)
            
    except:
        pass
        
    return result


def existFile(keyName, privateFlag = False, bucketCode = ""):
    result = False
    try:
        bucketInfo, objectKey = _resolveBucketAndKey(keyName, privateFlag, bucketCode)

        response = bucketRead.list_objects(
            Bucket = bucketInfo["bucketName"], 
            Prefix = objectKey
            )
        if response != {}:
            result = True
    except:
        pass
        
    return result


def getFileInfo(keyName, privateFlag = False, bucketCode = ""):
    result = {}
    try:
        bucketInfo, objectKey = _resolveBucketAndKey(keyName, privateFlag, bucketCode)

        response = bucketRead.list_objects(
            Bucket = bucketInfo["bucketName"], 
            Prefix = objectKey
            )
        if response != {}:
            result = response
    except:
        pass
        
    return result
    

def deleteFile(keyName, privateFlag = False, bucketCode = ""):
    result = False
    try:
        bucketInfo, objectKey = _resolveBucketAndKey(keyName, privateFlag, bucketCode)

        response = bucketRead.delete_object(
            Bucket = bucketInfo["bucketName"], 
            Key = objectKey
            )
        if response != {}:
            result = True
    except:
        pass
        
    return result


def setFileAccess(keyName, accessRight, privateFlag = False, bucketCode = ""):
    result = False
    try:
        bucketInfo, objectKey = _resolveBucketAndKey(keyName, privateFlag, bucketCode)

        #修正基线入参错位: put_object_acl(Bucket, Key, AccessControlPolicy={}), 原 ALC= 为无效关键字
        response = bucketWrite.put_object_acl(
            Bucket = bucketInfo["bucketName"], 
            Key = objectKey, 
            AccessControlPolicy = {"x-cos-acl": accessRight}
            )
        if response != {}:
            result = True
    except:
        pass
    return result


def genFileTempUrl(keyName, privateFlag = False, bucketCode = ""):
    result = ""
    try:
        bucketInfo, objectKey = _resolveBucketAndKey(keyName, privateFlag, bucketCode)

        response = bucketWrite.get_presigned_download_url(
            #Method = "PUT", 
            Bucket = bucketInfo["bucketName"], 
            Key = objectKey, 
            Expired=3600 #过期时间是1个小时
            )
        result = response
    except:
        pass
        
    return result
    

def genFilePublicUrl(keyName, privateFlag = False, bucketCode = ""):
    result = ""
    try:
        #域名(B4): 由逻辑桶解析得到, 不再写死 privateUrl/url
        bucketInfo, objectKey = _resolveBucketAndKey(keyName, privateFlag, bucketCode)
        baseUrl = bucketInfo["urlBase"]
        if baseUrl:
            result = baseUrl + "/" + objectKey
    except:
        pass
        
    return result
    
    
def listFiles(maxNum  = 1000,  privateFlag = False, bucketCode = ""):
    result = []
    total = 0
    nextMarker = None
    
    if maxNum >= 1000:
        maxKeys = 1000
    else:
        maxKeys = maxNum

    try:
        bucketInfo = _resolveBucket(privateFlag, bucketCode)
        localBucketName = bucketInfo["bucketName"]

        while True:
            if nextMarker == None:
                response = bucketRead.list_objects(
                        Bucket = localBucketName, 
                        MaxKeys = maxKeys, 
                        )
            else:
                response = bucketRead.list_objects(
                        Bucket = localBucketName, 
                        MaxKeys = maxKeys, 
                        Marker = nextMarker,                     
                        )
            if response != {}:
                partList = response.get("Contents", [])
                result += partList
                total += len(partList)
                nextMarker = response.get("NextMarker")
                isTruncated = response.get("IsTruncated")
                if isTruncated == "false" or total >= maxNum :
                    break 
            else:
                break
    except:
        pass
        
    return result
    
    
def main():
    if len(sys.argv) > 1:
        pass
        import platform
        if platform.system()=='Linux':
            import pdb
            pdb.set_trace()
    
    dataList = listFiles(500)
        
    keyName = "12345678901"
    keyName = "12345678903"
    fileName = r"D:\data\AI\hotel\hotel-1.jpg"
#    uploadFile(keyName, fileName, privateFlag = True)
#    fileName = r"D:\data\AI\hotel\hotel-0.jpg"
#    if getFileInfo(keyName):
#        downloadFile(keyName, fileName)
#    deleteFile(keyName)
#    objName = "hotelPhotoacab4a88-b7a4-46f9-abea-ca12df861cde"
    if existFile(keyName, privateFlag = True):
        genFileTempUrl(keyName, privateFlag = True)
    

if __name__ == "__main__":
    main()
