#! /usr/bin/env python
#encoding: utf-8

#Filename: aliyunSettings.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-17
#Description:   阿里云OSS 配置管理(多 Bucket 版)
#
#设计要点(见 plan/ylwz文件服务多Bucket.md 第 3.2 节):
#  1. 逻辑桶码(bucketCode) 与物理桶名解耦: 业务层只说 bucketCode, 物理名/路径前缀由配置决定
#  2. 公共认证共享: AK/Endpoint/超时留在服务级(_OSS_COMMON), 只有桶相关下沉到 Buckets
#  3. 兼容键保留: BucketName 为派生别名(= 默认桶物理名), 旧代码零改动
#  4. 默认桶显式声明: DefaultBucketCode
#
#⚠️ 红线: 默认桶物理名在改造前后必须保持不变, 否则存量 fileID 将大面积不可读

_VERSION="20260918"


import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

from config import local_settings as local_settings


#生产环境 rss | 测试环境 dss
_SYS = local_settings._SYS

_SYS_SERVER_NAME = local_settings._SYS_SERVER_NAME

_DEBUG = True  #预设trace开关，禁止修改


#—— 多桶公共部分(服务级, 各桶共享) ——
_OSS_COMMON = {
"local":{
    "RegionId":"cn-beijing",
    "roleArn":"acs:ram::your_aliyun_account_id:user/oss_access",
    "AccessKeyId":"your_appid",
    "AccessKeySecret":"your_securet",
    "readOnlyAccessKeyId":"your_appid",
    "readOnlyAccessKeySecret":"your_securet",
    "stsRegionId":"oss-cn-beijing",
    "stsAccessKeyId":"stskeyid",
    "stsAccessKeySecret":"stssecret",
    "Endpoint":"https://oss-cn-beijing.aliyuncs.com",
    "EndpointExternal":"https://oss-cn-beijing.aliyuncs.com",
    "EndpointInternal":"https://oss-cn-beijing-internal.aliyuncs.com",
    "ConnTimeOut":60,
    "DispTimeOut":1800,
    },
"server_01":{
    "RegionId":"cn-beijing",
    "roleArn":"acs:ram::your_aliyun_account_id:user/oss_access",
    "AccessKeyId":"your_appid",
    "AccessKeySecret":"your_securet",
    "readOnlyAccessKeyId":"your_appid",
    "readOnlyAccessKeySecret":"your_securet",
    "stsRegionId":"oss-cn-beijing",
    "stsAccessKeyId":"stskeyid",
    "stsAccessKeySecret":"stssecret",
    "Endpoint":"https://oss-cn-beijing.aliyuncs.com",
    "EndpointExternal":"https://oss-cn-beijing.aliyuncs.com",
    "EndpointInternal":"https://oss-cn-beijing-internal.aliyuncs.com",
    "ConnTimeOut":60,
    "DispTimeOut":1800,
    },
"server_02":{
    "RegionId":"cn-heyuan",
    "roleArn":"acs:ram::your_aliyun_account_id:role/aliyunosstokengeneratorrole",
    "AccessKeyId":"your_appid",
    "AccessKeySecret":"your_securet",
    "readOnlyAccessKeyId":"your_appid",
    "readOnlyAccessKeySecret":"your_securet",
    "stsRegionId":"oss-cn-heyuan",
    "stsAccessKeyId":"stskeyid",
    "stsAccessKeySecret":"stssecret",
    "Endpoint":"https://oss-cn-heyuan.aliyuncs.com",
    "EndpointExternal":"https://oss-cn-heyuan.aliyuncs.com",
    "EndpointInternal":"https://oss-cn-heyuan-internal.aliyuncs.com",
    "ConnTimeOut":60,
    "DispTimeOut":1800,
    },
"test_server":{
    "RegionId":"cn-heyuan",
    "roleArn":"acs:ram::your_aliyun_account_id:role/aliyunosstokengeneratorrole",
    "AccessKeyId":"your_appid",
    "AccessKeySecret":"your_securet",
    "readOnlyAccessKeyId":"your_appid",
    "readOnlyAccessKeySecret":"your_securet",
    "stsRegionId":"oss-cn-heyuan",
    "stsAccessKeyId":"stskeyid",
    "stsAccessKeySecret":"stssecret",
    "Endpoint":"https://oss-cn-heyuan.aliyuncs.com",
    "EndpointExternal":"https://oss-cn-heyuan.aliyuncs.com",
    "EndpointInternal":"https://oss-cn-heyuan-internal.aliyuncs.com",
    "ConnTimeOut":60,
    "DispTimeOut":1800,
    },
"home":{
    "RegionId":"cn-heyuan",
    "roleArn":"acs:ram::your_aliyun_account_id:role/aliyunosstokengeneratorrole",
    "AccessKeyId":"your_appid",
    "AccessKeySecret":"your_securet",
    "readOnlyAccessKeyId":"your_appid",
    "readOnlyAccessKeySecret":"your_securet",
    "stsRegionId":"oss-cn-heyuan",
    "stsAccessKeyId":"stskeyid",
    "stsAccessKeySecret":"stssecret",
    "Endpoint":"https://oss-cn-heyuan.aliyuncs.com",
    "EndpointExternal":"https://oss-cn-heyuan.aliyuncs.com",
    "EndpointInternal":"https://oss-cn-heyuan-internal.aliyuncs.com",
    "ConnTimeOut":60,
    "DispTimeOut":1800,
    },
}[_SYS]


#—— 各环境的多桶定义 ——
#bucketCode: 业务域命名(与 ch_asset 用途对齐); Access: private/public; PathPrefix: 对象键前缀
#⚠️ 除 server_02 外, 下列物理桶名仍为方案示例值(占位), 上线前按各环境真实物理桶替换, 逻辑桶码保持不变即可
_ALIYUN_OSS_BUCKETS_BY_SYS = {
"local":{
    "DefaultBucketCode":"default",
    "Buckets":{
        "default":  {"BucketName":"contenthub-private",  "Access":"private", "PathPrefix":"",          "UrlBase":""},
        "media":    {"BucketName":"contenthub-media",    "Access":"private", "PathPrefix":"media/",    "UrlBase":""},
        "artifact": {"BucketName":"contenthub-artifact", "Access":"private", "PathPrefix":"artifact/", "UrlBase":""},
        "public":   {"BucketName":"contenthub-public",   "Access":"public",  "PathPrefix":"pub/",      "UrlBase":"https://contenthub-public.oss-cn-beijing.aliyuncs.com"},
        },
    },
"server_01":{
    "DefaultBucketCode":"default",
    "Buckets":{
        "default":  {"BucketName":"contenthub-private",  "Access":"private", "PathPrefix":"",          "UrlBase":""},
        "media":    {"BucketName":"contenthub-media",    "Access":"private", "PathPrefix":"media/",    "UrlBase":""},
        "artifact": {"BucketName":"contenthub-artifact", "Access":"private", "PathPrefix":"artifact/", "UrlBase":""},
        "public":   {"BucketName":"contenthub-public",   "Access":"public",  "PathPrefix":"pub/",      "UrlBase":"https://contenthub-public.oss-cn-beijing.aliyuncs.com"},
        },
    },
#⚠️ server_02 已接入阿里云 OSS 真实桶(contenthub-private / private-mindgram / public-access-mindgram), 其余环境仍为占位值
#⚠️ 本环境默认桶物理名由占位值 contenthub-private 变为 private-mindgram:
#   若存量对象落在 contenthub-private 且记录无 bucketCode 快照, 读取时将回落到 private-mindgram。
#   上线前须确认存量 fileID 归属, 必要时先做桶归属回填(见 plan/ylwz文件服务多Bucket.md 第 5 章红线)。
#⚠️ media 与 artifact 共用物理桶 contenthub-private(前缀不同): 读取路由必须带 bucketCode,
#   仅凭 storageBucket 反查会命中 dict 中靠前的 media, 导致 artifact 对象被误加前缀。
"server_02":{
    "DefaultBucketCode":"default",
    "Buckets":{
        "default":  {"BucketName":"private-mindgram",       "Access":"private", "PathPrefix":"",          "UrlBase":""},
        "media":    {"BucketName":"contenthub-private",     "Access":"private", "PathPrefix":"media/",    "UrlBase":""},
        "artifact": {"BucketName":"contenthub-private",     "Access":"private", "PathPrefix":"artifact/", "UrlBase":""},
        "public":   {"BucketName":"public-access-mindgram", "Access":"public",  "PathPrefix":"pub/",      "UrlBase":"https://public-access-mindgram.oss-cn-heyuan.aliyuncs.com"},
        },
    },
"test_server":{
    "DefaultBucketCode":"default",
    "Buckets":{
        "default":  {"BucketName":"contenthub-private",  "Access":"private", "PathPrefix":"",          "UrlBase":""},
        "media":    {"BucketName":"contenthub-media",    "Access":"private", "PathPrefix":"media/",    "UrlBase":""},
        "artifact": {"BucketName":"contenthub-artifact", "Access":"private", "PathPrefix":"artifact/", "UrlBase":""},
        "public":   {"BucketName":"contenthub-public",   "Access":"public",  "PathPrefix":"pub/",      "UrlBase":"https://contenthub-public.oss-cn-heyuan.aliyuncs.com"},
        },
    },
"home":{
    "DefaultBucketCode":"default",
    "Buckets":{
        "default":  {"BucketName":"contenthub-private",  "Access":"private", "PathPrefix":"",          "UrlBase":""},
        "media":    {"BucketName":"contenthub-media",    "Access":"private", "PathPrefix":"media/",    "UrlBase":""},
        "artifact": {"BucketName":"contenthub-artifact", "Access":"private", "PathPrefix":"artifact/", "UrlBase":""},
        "public":   {"BucketName":"contenthub-public",   "Access":"public",  "PathPrefix":"pub/",      "UrlBase":"https://contenthub-public.oss-cn-heyuan.aliyuncs.com"},
        },
    },
}

ALIYUN_OSS_BUCKETS = _ALIYUN_OSS_BUCKETS_BY_SYS[_SYS]

_BUCKETS = ALIYUN_OSS_BUCKETS["Buckets"]
_DEFAULT_BUCKET_CODE = ALIYUN_OSS_BUCKETS["DefaultBucketCode"]


#—— STS 策略: Resource 按全部桶自动展开, 避免加桶后漏配 ——
def _genStsResource(buckets):
    """按全部逻辑桶展开 STS 策略 Resource, 每桶产出 桶本身 + 桶内对象 两条 ARN"""
    res = []
    for _code, b in buckets.items():
        name = b["BucketName"]
        res.append(f"acs:oss:*:*:{name}")
        res.append(f"acs:oss:*:*:{name}/*")
    return res


ALIYUN_OSS_SERVICE = dict(_OSS_COMMON)
ALIYUN_OSS_SERVICE.update({
    # ▼ 兼容别名: 等价于默认桶, 老代码 settings.ALIYUN_OSS_SERVICE["BucketName"] 继续可用
    "BucketName": _BUCKETS[_DEFAULT_BUCKET_CODE]["BucketName"],
    # ▼ 新增
    "DefaultBucketCode": _DEFAULT_BUCKET_CODE,
    "Buckets": _BUCKETS,
    "stsPolicyData": {
        "Version": "1",
        "Statement": [{
            "Effect": "Allow",
            "Action": ["oss:Put*"],
            "Resource": _genStsResource(_BUCKETS),   # ← 自动覆盖全部桶
            "Condition": {},
        }],
    },
})


if __name__ == "__main__":
    pass
    # import pdb
    # pdb.set_trace()
    print ("_SYS",_SYS)
    print ("_SYS_SERVER_NAME",_SYS_SERVER_NAME)
    print ("ALIYUN_OSS_SERVICE",ALIYUN_OSS_SERVICE)
