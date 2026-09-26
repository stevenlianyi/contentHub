#! /usr/bin/env python3
#encoding: utf-8

#Filename: initSeed.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub 种子数据灌入脚本(幂等, 可重复执行):
#  1) ch_platform: 3 条平台能力矩阵 —— wechat_mp(微信公众号) / xiaohongshu(小红书) / generic(通用HTML);
#  2) ch_layout:   4 条内置版式 —— stack_v1(上下) / carousel_v1(左右轮播) / longimage_v1(长图拼接) /
#                   swipe_v1(左右滑动多图集, 仅小红书).
#
#幂等实现: 统一走 common/chCommon.upsertByUniqueKey(生成器不支持 ON DUPLICATE KEY),
#          唯一键为 platformCode / layoutCode; 重复执行不会产生重复数据。
#数据要点(主计划 3.4.7 / 2.6.1):
#  - 小红书 imageMaxCount=18、needAiLabelFlag=1、autoPublishFlag=0(严禁第三方自动发布);
#  - swipe_v1 的 specJson 含 1080x1440 / 比例 3:4 / 上限 18 / 比例统一 / 单张 20MB。
#
#用法: cd code/src && python tools/initSeed.py

_VERSION="20260918"

import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)

from config import basicSettings as settings
from config import mysqlSettings as mysqlSettings

from common import miscCommon as misc
from common import mysqlCommon as comMysql
from common import chCommon as comCh

_processorPID = os.getpid()

_AUTO_LOGINID = settings.SYS_DEFAULT_AUTO_LOGINID


#平台能力矩阵种子(平台能做什么/不能做什么直接展示给用户, 数据来源即此表)
PLATFORM_SEED_LIST = [
    {
        "platformCode": "wechat_mp",
        "platformName": "微信公众号",
        "subjectScope": "个人订阅号/认证企业订阅号/认证服务号",
        "deliverMode": "draft_box",
        "titleMaxLen": 64,
        "summaryMaxLen": 200,
        "coverSpec": "900x500",
        "imageSpec": "1080x1440",
        "imageMaxCount": 20,
        "allowSvgFlag": "0",
        "needAiLabelFlag": "0",
        "autoPublishFlag": "0",
        "limitNote": "个人主体与未认证企业号自2025年7月起已被回收发布接口权限 本项目只能推草稿箱 最终群发须人工在后台完成",
        "docUrl": "https://developers.weixin.qq.com/doc/offiaccount/Draft_Box/Add_draft.html",
        "enabled": "1",
    },
    {
        "platformCode": "xiaohongshu",
        "platformName": "小红书",
        "subjectScope": "企业主体/品牌/服务商(需资质审核)",
        "deliverMode": "asset_pack",
        "titleMaxLen": 20,
        "summaryMaxLen": 1000,
        "coverSpec": "1080x1440",
        "imageSpec": "1080x1440",
        "imageMaxCount": 18,
        "allowSvgFlag": "0",
        "needAiLabelFlag": "1",
        "autoPublishFlag": "0",
        "limitNote": "严禁第三方自动发布与AI托管 本平台仅导出素材包; 整篇图片须比例统一 单张不超过20MB 超长图须按1080x1440切分",
        "docUrl": "",
        "enabled": "1",
    },
    {
        "platformCode": "generic",
        "platformName": "通用HTML",
        "subjectScope": "站内预览/导出/第三方站点",
        "deliverMode": "asset_pack",
        "titleMaxLen": 128,
        "summaryMaxLen": 400,
        "coverSpec": "",
        "imageSpec": "",
        "imageMaxCount": 50,
        "allowSvgFlag": "1",
        "needAiLabelFlag": "0",
        "autoPublishFlag": "0",
        "limitNote": "无平台限制 作为兜底与调试形态",
        "docUrl": "",
        "enabled": "1",
    },
]


#版式模板种子(layoutType: stack上下 / carousel左右轮播 / longimage长图 / swipe左右滑动浏览)
LAYOUT_SEED_LIST = [
    {
        "layoutCode": "stack_v1",
        "layoutName": "上下展示",
        "layoutType": "stack",
        "platform": "wechat_mp",
        "engine": "jinja2",
        "templatePath": "engine/templates/stack_v1/index.html",
        "templateVer": "v1",
        "outputKind": "html",
        "specJson": '{"maxWidth":"750px","fontSize":"16px","lineHeight":"1.75","paragraphGap":"16px"}',
        "builtinFlag": "1",
        "enabled": "1",
        "sortWeight": 10,
    },
    {
        "layoutCode": "carousel_v1",
        "layoutName": "左右轮播",
        "layoutType": "carousel",
        "platform": "wechat_mp",
        "engine": "jinja2",
        "templatePath": "engine/templates/carousel_v1/index.html",
        "templateVer": "v1",
        "outputKind": "html",
        #公众号无原生轮播 交互由本项目自实现(含静态图集兜底) 故 allowSvg 与 needStaticFallback 置位
        "specJson": '{"size":"1080x1440","ratio":"3:4","maxCount":9,"allowSvg":false,"needStaticFallback":true}',
        "builtinFlag": "1",
        "enabled": "1",
        "sortWeight": 20,
    },
    {
        "layoutCode": "longimage_v1",
        "layoutName": "长图拼接",
        "layoutType": "longimage",
        "platform": "xiaohongshu",
        "engine": "jinja2",
        "templatePath": "engine/templates/longimage_v1/index.html",
        "templateVer": "v1",
        "outputKind": "png",
        #严禁直接上传超长原图(会被强制缩放导致文字模糊) 故须按 sliceHeight 切分
        "specJson": '{"size":"1080x1440","ratio":"3:4","sliceHeight":1440,"maxTotalHeight":21600}',
        "builtinFlag": "1",
        "enabled": "1",
        "sortWeight": 30,
    },
    {
        "layoutCode": "swipe_v1",
        "layoutName": "左右滑动多图集",
        "layoutType": "swipe",
        "platform": "xiaohongshu",
        "engine": "jinja2",
        "templatePath": "engine/templates/swipe_v1/index.html",
        "templateVer": "v1",
        "outputKind": "png",
        #见主计划 2.6.1: 平台原生左右滑动 项目侧只负责切分+排序+比例统一
        "specJson": '{"size":"1080x1440","ratio":"3:4","maxCount":18,"minCount":1,"uniformRatio":true,"maxSizePerImageMB":20,"format":["jpg","png"],"sortable":true,"coverFlag":true}',
        "builtinFlag": "1",
        "enabled": "1",
        "sortWeight": 40,
    },
]


def genCommonSaveSet():
    """种子公共尾部字段(固定七字段中的注册/修改四列 + delFlag)"""
    nowYMDHMS = misc.getTime()
    saveSet = {
        "regID": _AUTO_LOGINID,
        "regYMDHMS": nowYMDHMS,
        "modifyID": _AUTO_LOGINID,
        "modifyYMDHMS": nowYMDHMS,
        #删除标记按库内约定用 "0"/"1"(与生成器 insert 的默认值、query_ch_* 的 delFlag="0" 过滤一致);
        #注意不要用 comGD._CONST_NO(其值为 "N", 语义是布尔否定, 不是本项目的 delFlag 取值)
        "delFlag": "0",
    }
    return saveSet


def seedPlatform():
    """灌入 ch_platform 种子(幂等, 唯一键 platformCode)"""
    tableName = comMysql.tablename_convertor_ch_platform()
    okCount = 0
    for seedSet in PLATFORM_SEED_LIST:
        platformCode = seedSet.get("platformCode")
        saveSet = dict(seedSet)
        saveSet.update(genCommonSaveSet())

        recID = comCh.upsertByUniqueKey(
            tableName, platformCode, saveSet,
            lambda t, v: comMysql.query_ch_platform(t, platformCode = v),
            comMysql.insert_ch_platform,
            comMysql.update_ch_platform)

        flag = "OK  " if recID else "FAIL"
        print(f"[initSeed] {flag} ch_platform {platformCode} -> recID:{recID}")
        if recID:
            okCount += 1

    return okCount, len(PLATFORM_SEED_LIST)


def seedLayout():
    """灌入 ch_layout 种子(幂等, 唯一键 layoutCode)"""
    tableName = comMysql.tablename_convertor_ch_layout()
    okCount = 0
    for seedSet in LAYOUT_SEED_LIST:
        layoutCode = seedSet.get("layoutCode")
        saveSet = dict(seedSet)
        saveSet.update(genCommonSaveSet())

        recID = comCh.upsertByUniqueKey(
            tableName, layoutCode, saveSet,
            lambda t, v: comMysql.query_ch_layout(t, layoutCode = v),
            comMysql.insert_ch_layout,
            comMysql.update_ch_layout)

        flag = "OK  " if recID else "FAIL"
        print(f"[initSeed] {flag} ch_layout {layoutCode} -> recID:{recID}")
        if recID:
            okCount += 1

    return okCount, len(LAYOUT_SEED_LIST)


def main():
    print(f"[initSeed] PID:{_processorPID}, _SYS:{settings._SYS}, FILE_SYSTEM_MODE:{settings.FILE_SYSTEM_MODE}")
    print(f"[initSeed] writeDB:{mysqlSettings.MYSQL_WRITE_DB}, readDB:{mysqlSettings.MYSQL_READ_DB}")

    if mysqlSettings.mysqlDB is None:
        print("[initSeed] 未建立数据库连接(MYSQL_SKIP_CONNECT=1): 请先关闭该开关再灌种子")
        return 1

    platformOk, platformTotal = seedPlatform()
    layoutOk, layoutTotal = seedLayout()

    print(f"[initSeed] done: ch_platform {platformOk}/{platformTotal}, ch_layout {layoutOk}/{layoutTotal}")
    return 0 if (platformOk == platformTotal and layoutOk == layoutTotal) else 1


if __name__ == "__main__":
    sys.exit(main())
