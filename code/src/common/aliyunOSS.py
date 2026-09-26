#! /usr/bin/env python
#encoding: utf-8

#Filename: aliyunOSS.py
#Author: Steven Lian
#E-mail:  steven.lian@gmail.com  
#Date: 2019-09-28
#Description:   阿里云OSS功能(上传下载文件，获取文件信息，设置文件权限，生成文件临时下载url)
#升级问版本2, 支持auth V4
# https://www.alibabacloud.com/help/zh/oss/?spm=a2c63.p38356.help-sub-nav.2.11653967g4fHPZ
# https://github.com/aliyun/aliyun-oss-python-sdk
# pip3 install alibabacloud-oss-v2

_VERSION="20260728"

_DEBUG=True

import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import datetime 

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#setting files
from config import aliyunSettings as settings

# import oss2 as oss
import alibabacloud_oss_v2 as oss

# from aliyunsdkcore import client
# from aliyunsdksts.request.v20150401 import AssumeRoleRequest

# _DEBUG =  settings._DEBUG
_DEBUG = False
# command part begin

# 从环境变量中加载凭证信息，用于身份验证
# credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()

# 使用AccessKeyId和AccessKeySecret初始化凭证信息对象
credentials_provider = oss.credentials.StaticCredentialsProvider(settings.ALIYUN_OSS_SERVICE["AccessKeyId"], settings.ALIYUN_OSS_SERVICE["AccessKeySecret"])

# 加载SDK的默认配置，并设置凭证提供者
cfg = oss.config.load_default()
cfg.credentials_provider = credentials_provider

# 方式一： 只填写Region即可
# 填写Bucket所在地域。以华东1（杭州）为例，Region填写为cn-hangzhou
cfg.region = settings.ALIYUN_OSS_SERVICE["RegionId"]
 
# # 方式二： 直接填写Region和Endpoint
# # 填写Bucket所在地域。以华东1（杭州）为例，Region填写为cn-hangzhou
# cfg.region = 'cn-hangzhou'
# # 填写Bucket所在地域对应的公网Endpoint。以华东1（杭州）为例，Endpoint填写为'https://oss-cn-hangzhou.aliyuncs.com',
# # 如需指定为http协议，请在指定域名时填写为'http://oss-cn-hangzhou.aliyuncs.com'
# cfg.endpoint = 'https://oss-cn-hangzhou.aliyuncs.com'

# 使用配置好的信息创建OSS客户端
bucketClient = oss.Client(cfg)

# authWrite = oss.Auth(settings.ALIYUN_OSS_SERVICE["AccessKeyId"],settings.ALIYUN_OSS_SERVICE["AccessKeySecret"])
# authRead = oss.Auth(settings.ALIYUN_OSS_SERVICE["readOnlyAccessKeyId"],settings.ALIYUN_OSS_SERVICE["readOnlyAccessKeySecret"])
endpoint = settings.ALIYUN_OSS_SERVICE["Endpoint"]
endpointExternal = settings.ALIYUN_OSS_SERVICE["EndpointExternal"]
endpointInternal = settings.ALIYUN_OSS_SERVICE["EndpointInternal"]
# bucketWrite = oss.Bucket(authWrite, endpoint, settings.ALIYUN_OSS_SERVICE["BucketName"], connect_timeout = settings.ALIYUN_OSS_SERVICE["ConnTimeOut"])
# bucketWriteExternal = oss.Bucket(authWrite, endpointExternal, settings.ALIYUN_OSS_SERVICE["BucketName"], connect_timeout = settings.ALIYUN_OSS_SERVICE["ConnTimeOut"])
# bucketRead = oss.Bucket(authRead, endpoint, settings.ALIYUN_OSS_SERVICE["BucketName"], connect_timeout = settings.ALIYUN_OSS_SERVICE["ConnTimeOut"])
# bucketReadExternal = oss.Bucket(authRead, endpointExternal, settings.ALIYUN_OSS_SERVICE["BucketName"], connect_timeout = settings.ALIYUN_OSS_SERVICE["ConnTimeOut"])

#兼容保留: 默认桶物理名(等价于 getBucketInfo("ALIOSS")["bucketName"])
#⚠️ 新增/切换桶只改 config/aliyunSettings.py 的 Buckets, 不在本文件出现任何桶名字面量
BucketNamePrivate = settings.ALIYUN_OSS_SERVICE["BucketName"]


RESPONSE_STATUS_OK = "OK"


#—— 多桶解析 begin ——
#延迟 import config.bucketSettings, 避免与 config 包初始化顺序耦合(方案 A2)
def _resolveBucket(bucketCode=""):
    """按逻辑桶码解析目标桶, 返回归一化桶信息(bucketCode/bucketName/access/pathPrefix/urlBase)"""
    from config import bucketSettings as comBucket
    return comBucket.getBucketInfo("ALIOSS", bucketCode)


def _resolveBucketAndKey(objName, bucketCode=""):
    """解析目标桶并幂等补逻辑桶路径前缀, 返回 (bucketInfo, objectKey)。
    幂等性保证: 服务层落库的 objectName 已含前缀时, 这里不会二次拼接。
    """
    from config import bucketSettings as comBucket
    bucketInfo = comBucket.getBucketInfo("ALIOSS", bucketCode)
    return bucketInfo, comBucket.applyPathPrefix(bucketInfo, objName)
#—— 多桶解析 end ——

# <yourLocalFile>由本地文件路径加文件名包括后缀组成，例如/users/local/myfile.txt
_LOG = misc.setLogNew("ALIOSS", "recvfileslog")


#把本地文件上传
def uploadFile(objName, fileName,downloadName = "", bucketCode=""):
    result = False
    try:
        bucketInfo, objectKey = _resolveBucketAndKey(objName, bucketCode)
        requestObj =  oss.PutObjectRequest(
            bucket=bucketInfo["bucketName"],  # 存储空间名称(按 bucketCode 解析)
            key=objectKey,         # 对象名称(已含逻辑桶路径前缀)
        )
        # 准备请求头
        headers = {}
        if downloadName:
            # 设置 Content-Disposition 让浏览器以下载方式处理
            headers["Content-Disposition"] = f"attachment;filename={downloadName}"
            response = bucketClient.put_object_from_file(requestObj, fileName,headers=headers)
        else:
            response = bucketClient.put_object_from_file(requestObj, fileName)
        if response.status == RESPONSE_STATUS_OK:
            if existFile(objName, bucketCode=bucketCode):
                result = True
        if not result:
            _LOG.warning(f"response.status:{response.status}")
        
    except Exception as e:
        errMsg = f"errMsg:{str(e)}"
        _LOG.error(f"errMsg:{errMsg}")
        
    return result


#下载文件到本地 
def downloadFile(objName, fileName, bucketCode=""):
    result = False
    try:
        bucketInfo, objectKey = _resolveBucketAndKey(objName, bucketCode)
        requestObj =  oss.PutObjectRequest(
            bucket=bucketInfo["bucketName"],  # 存储空间名称(按 bucketCode 解析)
            key=objectKey,         # 对象名称
        )
        response = bucketClient.get_object_to_file(requestObj, fileName)
        if response.status == RESPONSE_STATUS_OK:
            result = True
        
    except Exception as e:
        errMsg = f"errMsg:{str(e)}"
        _LOG.error(f"errMsg:{errMsg}")
        
    return result


#判断文件是否存在
def existFile(objName, bucketCode=""):
    result = False
    try:
        # 使用 head_object 获取对象元数据，如果成功则文件存在
        bucketInfo, objectKey = _resolveBucketAndKey(objName, bucketCode)
        requestObj =  oss.PutObjectRequest(
            bucket=bucketInfo["bucketName"],  # 存储空间名称(按 bucketCode 解析)
            key=objectKey,         # 对象名称
        )
        response = bucketClient.head_object(requestObj)
        if response.status == RESPONSE_STATUS_OK:
            result = True
    except Exception as e:
        errMsg = f"未知错误: {str(e)}"
        _LOG.error(errMsg)
    return result


#删除文件
def deleteFile(objName, bucketCode=""):
    result = False
    try:
        bucketInfo, objectKey = _resolveBucketAndKey(objName, bucketCode)
        requestObj =  oss.PutObjectRequest(
            bucket=bucketInfo["bucketName"],  # 存储空间名称(按 bucketCode 解析)
            key=objectKey,         # 对象名称
        )
        response = bucketClient.delete_object(requestObj)
        result = True
        
    except Exception as e:
        errMsg = f"errMsg:{str(e)}"
        _LOG.error(f"errMsg:{errMsg}")
        
    return result


#设置文件存取权限
def setFileAccess(objName, accessRight, privateFlag = False, bucketCode=""):
    #privateFlag 仅为语义对齐(决策 6.3): ALIOSS 目标桶由 bucketCode 决定, 该形参接受但忽略
    result = False
    try:
        bucketInfo, objectKey = _resolveBucketAndKey(objName, bucketCode)
        #修正基线调用错位: SDK v2 为 put_object_acl(request), 原 (objName, accessRight) 会把 key 当 bucket
        requestObj = oss.PutObjectAclRequest(
            bucket=bucketInfo["bucketName"],  # 存储空间名称(按 bucketCode 解析)
            key=objectKey,         # 对象名称
            acl=accessRight,       # 对象ACL
        )
        response = bucketClient.put_object_acl(requestObj)
        result = response
        
    except Exception as e:
        errMsg = f"errMsg:{str(e)}"
        _LOG.error(f"errMsg:{errMsg}")
        
    return result


#获取文件信息
def getFileInfo(objName, bucketCode=""):
    result = {}
    try:
        # 使用 head_object 获取对象元数据，如果成功则文件存在
        bucketInfo, objectKey = _resolveBucketAndKey(objName, bucketCode)
        requestObj =  oss.PutObjectRequest(
            bucket=bucketInfo["bucketName"],  # 存储空间名称(按 bucketCode 解析)
            key=objectKey,         # 对象名称
        )
        response = bucketClient.head_object(requestObj)
        if response.status == RESPONSE_STATUS_OK:

            fileSize = response.content_length
            if fileSize:
                try:
                    fileSize = int(fileSize)
                except:
                    fileSize = 0
            result["fileSize"] = fileSize
            try:
                result["ETag"] = misc.jsonLoads(response.etag)
            except:            
                result["ETag"] = response.etag
             # 获取最后修改时间
            last_modified = response.last_modified
            YMDHMS_FORMAT = "%Y%m%d%H%M%S"
            result["modifyYMDHMS"] = last_modified.strftime(YMDHMS_FORMAT)
        
    except Exception as e:
        errMsg = f"errMsg:{str(e)}"
        _LOG.error(f"errMsg:{errMsg}")
        
    return result


#生成文件的临时下载url
def genFileTempUrl(objName, timeOut = settings.ALIYUN_OSS_SERVICE["DispTimeOut"], bucketCode=""):
    result = ""
    try:
        # 生成预签名URL，用于GET请求（下载）
        # 直接使用之前已经初始化好的 client 和 bucket_name
        bucketInfo, objectKey = _resolveBucketAndKey(objName, bucketCode)
        requestObj = oss.GetObjectRequest(
            bucket=bucketInfo["bucketName"],  # 存储空间名称(按 bucketCode 解析)
            key=objectKey          # 对象名称
        )
        expire = datetime.timedelta(seconds=timeOut)
        response = bucketClient.presign(requestObj,expires=expire)

        # V2的 presign 方法返回一个 PresignResult 对象，其中包含URL
        result = response.url

    except Exception as e:
        errMsg = f"errMsg:{str(e)}"
        _LOG.error(f"errMsg:{errMsg}")
        
    return result


#生成文件的临时上传url
def genFileUploadUrl(objName, timeOut = settings.ALIYUN_OSS_SERVICE["DispTimeOut"], bucketCode=""):
    result = ""
    try:

        bucketInfo, objectKey = _resolveBucketAndKey(objName, bucketCode)
        requestObj = oss.PutObjectRequest(
            bucket=bucketInfo["bucketName"],  # 存储空间名称(按 bucketCode 解析)
            key=objectKey          # 对象名称
        )
        expire = datetime.timedelta(seconds=timeOut)
        response = bucketClient.presign(requestObj,expires=expire)

        # V2的 presign 方法返回一个 PresignResult 对象，其中包含URL
        result = response.url
        
    except Exception as e:
        errMsg = f"errMsg:{str(e)}"
        _LOG.error(f"errMsg:{errMsg}")
        
    return result


# 通过阿里云STS为前端直接上传提供所需参数
def genSTSToken(objName,sessionName = "session_default", bucketCode=""):
    global endpoint
    result = {}
    try:
    
        # yourEndpoint填写Bucket所在地域对应的Endpoint。以华东1（杭州）为例，Endpoint填写为https://oss-cn-hangzhou.aliyuncs.com。
        # endpoint = "https://oss-cn-zhangjiakou.aliyuncs.com"
        # 阿里云账号AccessKey拥有所有API的访问权限，风险很高。强烈建议您创建并使用RAM用户进行API访问或日常运维，请登录RAM控制台创建RAM用户。
        access_key_id = settings.ALIYUN_OSS_SERVICE["stsAccessKeyId"]
        access_key_secret = settings.ALIYUN_OSS_SERVICE["stsAccessKeySecret"]
        region_id = settings.ALIYUN_OSS_SERVICE["RegionId"]
        stsRegionId = settings.ALIYUN_OSS_SERVICE["stsRegionId"]
        # 填写Bucket名称(按逻辑桶码解析, 缺省为默认桶); 策略 Resource 已在配置层按全部桶自动展开(方案 A5)
        bucketInfo = _resolveBucket(bucketCode)
        bucket_name = bucketInfo["bucketName"]
        # 填写Object完整路径，例如exampledir/exampleobject.txt。Object完整路径中不能包含Bucket名称。
        # object_name = 'exampledir/exampleobject.txt'
        # 您可以登录RAM控制台，在RAM角色管理页面，搜索创建的RAM角色后，单击RAM角色名称，在RAM角色详情界面查看和复制角色的ARN信息。
        # 填写角色的ARN信息。格式为acs:ram::$accountID:role/$roleName。
        # $accountID为阿里云账号ID。您可以通过登录阿里云控制台，将鼠标悬停在右上角头像的位置，直接查看和复制账号ID，或者单击基本资料查看账号ID。
        # $roleName为RAM角色名称。您可以通过登录RAM控制台，单击左侧导航栏的RAM角色管理，在RAM角色名称列表下进行查看。
        role_arn = settings.ALIYUN_OSS_SERVICE["roleArn"]

        # 创建权限策略。
        # 只允许对名称为examplebucket的Bucket下的所有资源执行GetObject操作。
        # policy_text = '{"Version": "1", "Statement": [{"Action": ["oss:GetObject"], "Effect": "Allow", "Resource": ["acs:oss:*:*:test-20220830/*"]}]}'
        policy_text = misc.jsonDumps(settings.ALIYUN_OSS_SERVICE["stsPolicyData"])

        clt = client.AcsClient(access_key_id, access_key_secret, region_id)
        req = AssumeRoleRequest.AssumeRoleRequest()

        # 设置返回值格式为JSON。
        req.set_accept_format('json')
        req.set_RoleArn(role_arn)
        # 自定义角色会话名称，用来区分不同的令牌，例如可填写为session-test。
        req.set_RoleSessionName(sessionName)
        req.set_Policy(policy_text)
        body = clt.do_action_with_exception(req)

        # 使用RAM用户的AccessKeyId和AccessKeySecret向STS申请临时访问凭证。
        token = misc.jsonLoads(oss.to_unicode(body))

        result["bucketName"] = bucket_name
        result["bucketCode"] = bucketInfo["bucketCode"]
        result["regionID"] = stsRegionId
        # result["uploadUrl"] = genFileUploadUrl(objName)
        result["securityToken"] = token['Credentials']['SecurityToken']
        result["accessKeyID"] = token['Credentials']['AccessKeyId']
        result["accessKeySecret"] = token['Credentials']['AccessKeySecret']
        result["expiration"] = token['Credentials']['Expiration']

    except Exception as e:
        errMsg = f"errMsg:{str(e)}"
        _LOG.error(f"errMsg:{errMsg}")

    return result


def testStsUpload():
    import requests
    objName = "aliyunOSS.py"
    rtnData = genSTSToken(objName)
    putUrl = genFileUploadUrl(objName)
    print(putUrl)
    # 通过签名URL上传文件，以requests为例说明。
    # 填写本地文件路径，例如D:\\exampledir\\examplefile.txt。
    headers = {}
    headers['Content-Type'] = 'text/txt'
    r = requests.put(putUrl, data=open(objName, 'rb').read(), headers=headers)  
    if r.status_code == 200:  # OK.  Everything worked as expected.  :)  :-)  :-)  :-)  :-)
        print ("Put to bucket successful!")  # This is what we wanted.  It worked.  :-)  :-)  :-)  :-)
    else:
        print (r.status_code)


def main():
    # testStsUpload()
    objName = "aliyunOSS.py"
    # rtnData = genSTSToken(objName)
    # putUrl = genFileUploadUrl(objName)
    # print(putUrl)
    # objName = "hotelPhoto-acab4a88-b7a4-46f9-abea-ca12df861cde"
    fileName = r"aliyunOSS.py"
    uploadFile(objName, fileName,fileName)
    # if existFile(objName):
    #     fileName = r"D:\data\aliyunOSS.py"
    #     downloadFile(objName, fileName)
    # objName = "hotelPhoto-acab4a88-b7a4-46f9-abea-ca12df861cde"
    # if existFile(objName):
    #     downloadUrl = genFileTempUrl(objName)

    # uploadUrl = genFileUploadUrl(objName)

    fileInfo = getFileInfo(objName)
    # deleteFile(objName)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pass
        import platform
        if platform.system()=='Linux':
            import pdb
            pdb.set_trace()
    main()



