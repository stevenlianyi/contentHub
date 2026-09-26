#! /usr/bin/env python3
#encoding: utf-8

#Filename: tencentSettings.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-17
#Description:   腾讯云COS 配置管理(多 Bucket 版)
# https://cloud.tencent.com/document/product/436/12269
# pip install -U cos-python-sdk-v5
#
#设计要点(见 plan/ylwz文件服务多Bucket.md 第 3.3 节):
#  1. 旧版 privateFlag=True 选 privateBucketName / False 选 bucketName 的隐式映射,
#     显式化为 private / public 两个 bucketCode, 并保留 privateFlag 旧语义作为 fallback
#  2. 兼容键 privateBucketName/privateUrl/bucketName/url 由 Buckets 派生, 消除双份维护
#  3. 默认桶显式声明: DefaultBucketCode(=private, 与旧版默认私有桶语义一致)

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


#—— 各环境的多桶定义 ——
#bucketCode: 业务域命名; Access: private/public; PathPrefix: 对象键前缀; Url: 桶访问域名
#⚠️ 下列物理桶名为方案示例值(占位), 上线前按各环境真实物理桶替换, 逻辑桶码保持不变即可
_TECENT_COS_BUCKETS_BY_SYS = {
"local":{
    "DefaultBucketCode":"private",
    "Buckets":{
        "private": {"BucketName":"xjy-private-home", "Access":"private", "PathPrefix":"",       "Url":"https://xjy-private-home.cos.ap-chengdu.myqcloud.com"},
        "public":  {"BucketName":"xjy-data-home",    "Access":"public",  "PathPrefix":"pub/",   "Url":"https://xjy-data-home.cos.ap-chengdu.myqcloud.com"},
        "media":   {"BucketName":"xjy-media-home",   "Access":"private", "PathPrefix":"media/", "Url":"https://xjy-media-home.cos.ap-chengdu.myqcloud.com"},
        },
    },
"server_01":{
    "DefaultBucketCode":"private",
    "Buckets":{
        "private": {"BucketName":"xjy-private-home", "Access":"private", "PathPrefix":"",       "Url":"https://xjy-private-home.cos.ap-chengdu.myqcloud.com"},
        "public":  {"BucketName":"xjy-test-home",    "Access":"public",  "PathPrefix":"pub/",   "Url":"https://xjy-test-home.cos.ap-chengdu.myqcloud.com"},
        "media":   {"BucketName":"xjy-media-home",   "Access":"private", "PathPrefix":"media/", "Url":"https://xjy-media-home.cos.ap-chengdu.myqcloud.com"},
        },
    },
"server_02":{
    "DefaultBucketCode":"private",
    "Buckets":{
        "private": {"BucketName":"xjy-private-home", "Access":"private", "PathPrefix":"",       "Url":"https://xjy-private-home.cos.ap-chengdu.myqcloud.com"},
        "public":  {"BucketName":"xjy-test-home",    "Access":"public",  "PathPrefix":"pub/",   "Url":"https://xjy-test-home.cos.ap-chengdu.myqcloud.com"},
        "media":   {"BucketName":"xjy-media-home",   "Access":"private", "PathPrefix":"media/", "Url":"https://xjy-media-home.cos.ap-chengdu.myqcloud.com"},
        },
    },
"home":{
    "DefaultBucketCode":"private",
    "Buckets":{
        "private": {"BucketName":"xjy-private-home", "Access":"private", "PathPrefix":"",       "Url":"https://xjy-private-home.cos.ap-chengdu.myqcloud.com"},
        "public":  {"BucketName":"xjy-data-home",    "Access":"public",  "PathPrefix":"pub/",   "Url":"https://xjy-data-home.cos.ap-chengdu.myqcloud.com"},
        "media":   {"BucketName":"xjy-media-home",   "Access":"private", "PathPrefix":"media/", "Url":"https://xjy-media-home.cos.ap-chengdu.myqcloud.com"},
        },
    },
}

TECENT_COS_BUCKETS = _TECENT_COS_BUCKETS_BY_SYS[_SYS]

_COS_BUCKETS = TECENT_COS_BUCKETS["Buckets"]
_COS_DEFAULT = TECENT_COS_BUCKETS["DefaultBucketCode"]


TECENT_COS_SERVICE = {
    "secretId":"YOUR secretId",
    "secretKey":"YOUR_CODE",
    "domainBase":"myqcloud.com",
    "regionId":"ap-chengdu",
    "connTimeOut":60,
    "dispTimeOut":1800,
    # ▼ 兼容别名(语义保持与旧版一致: privateFlag=True → private 桶)
    "privateBucketName": _COS_BUCKETS["private"]["BucketName"],
    "privateUrl":        _COS_BUCKETS["private"]["Url"],
    "bucketName":        _COS_BUCKETS["public"]["BucketName"],
    "url":               _COS_BUCKETS["public"]["Url"],
    # ▼ 新增
    "DefaultBucketCode": _COS_DEFAULT,
    "Buckets": _COS_BUCKETS,
}


if __name__ == "__main__":
    pass
    # import pdb
    # pdb.set_trace()
    print ("_SYS",_SYS)
    print ("_SYS_SERVER_NAME",_SYS_SERVER_NAME)
    print ("TECENT_COS_SERVICE",TECENT_COS_SERVICE)
