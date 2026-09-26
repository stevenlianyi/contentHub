#! /usr/bin/env python3
#encoding: utf-8

#Filename: wechatSettings.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub 微信公众号(服务号/订阅号)凭据与接口配置。
#
#本期(SP1)只留结构, **不填真实值**:
#  - ★ 2026-09-24 口径变更(凭据来源收口): 公众号 appID/appSecret **不再由环境变量作为凭据来源**;
#    平台凭据一律由用户在「第三方账号管理」(/my-accounts) 或「账号管理」(/accounts) 页录入,
#    经 main/subfunc/crudApi.py::_applyAccountSecret 以 AES-256-GCM 加密写入
#    ch_account.credentialCipher/credentialIV(明文不落库、不回显); 读取端见
#    processor/publishService.py::decryptAccountCredential(**无环境变量回落**)。
#    WECHAT_APP_ID / WECHAT_APP_SECRET 两个常量**仅为兼容保留**(S9 静态断言 + 回调/运维自检),
#    业务链路不得再作为凭据使用。
#  - 本文件仅承载"接口级"配置(接口基址、接口路径、模板 ID、开关与窗口), 供 Phase 3 投递模块使用;
#  - 凭据加密**主密钥**仍走环境变量 CH_CREDENTIAL_KEY(密钥不入库、不入代码库, 见 common/credentialCipher.py)。
#
#配置文件约定: 全部按 _SYS 映射取值, 切换环境不改业务代码。

_VERSION="20260918"

import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)

from config import local_settings as local_settings

_SYS = local_settings._SYS


#开放平台接口基址(不带尾斜杠); 需要走代理时可在此按环境覆盖
WECHAT_API_BASE = {
    "local":"https://api.weixin.qq.com",
    "server_01":"https://api.weixin.qq.com",
    "server_02":"https://api.weixin.qq.com",
    "test_server":"https://api.weixin.qq.com",
    "home":"https://api.weixin.qq.com",
    }[_SYS]


#接口路径(常量, 与官方文档一致; 集中定义避免散落在业务代码里)
WECHAT_API_PATH = {
    #获取 access_token
    "accessToken":       "/cgi-bin/token",
    #新增永久素材(正文图/封面图 转存 mmbiz.qpic.cn 后使用)
    "materialAdd":       "/cgi-bin/material/add_material",
    #上传图文消息内的图片(不占用素材库配额)
    "uploadImg":         "/cgi-bin/media/uploadimg",
    #新建草稿(P0: 本项目公众号交付形态的终点)
    "draftAdd":          "/cgi-bin/draft/add",
    #提交发布(仅认证企业号/服务号可用; 个人号自2025年7月起已回收)
    "freePublishSubmit": "/cgi-bin/freepublish/submit",
}


#公众号 appID(★ 2026-09-24 起**不再作为凭据来源**, 见文件头; 常量保留仅为兼容)
#真实取值请在该账号记录的 ch_account.appID 中维护(用户在账号页录入, 与 AppSecret 成对)
WECHAT_APP_ID = {
    "local":       os.getenv("CH_WECHAT_APPID", ""),
    "server_01":   os.getenv("CH_WECHAT_APPID", ""),
    "server_02":   os.getenv("CH_WECHAT_APPID", ""),
    "test_server": os.getenv("CH_WECHAT_APPID", ""),
    "home":        os.getenv("CH_WECHAT_APPID", ""),
    }[_SYS]


#公众号 appSecret(★ 2026-09-24 起**不再作为凭据来源**: 不取本环境变量做兜底)
#平台凭据请在「第三方账号管理」页为账号录入, 由服务端加密落 ch_account.credentialCipher;
#本常量保留仅为兼容(禁止写死在代码库)
WECHAT_APP_SECRET = {
    "local":       os.getenv("CH_WECHAT_APPSECRET", ""),
    "server_01":   os.getenv("CH_WECHAT_APPSECRET", ""),
    "server_02":   os.getenv("CH_WECHAT_APPSECRET", ""),
    "test_server": os.getenv("CH_WECHAT_APPSECRET", ""),
    "home":        os.getenv("CH_WECHAT_APPSECRET", ""),
    }[_SYS]


#服务器配置 Token 与消息加解密密钥(接收平台事件回调时校验用), 同样走环境变量
WECHAT_SERVER_TOKEN = {
    "local":       os.getenv("CH_WECHAT_TOKEN", ""),
    "server_01":   os.getenv("CH_WECHAT_TOKEN", ""),
    "server_02":   os.getenv("CH_WECHAT_TOKEN", ""),
    "test_server": os.getenv("CH_WECHAT_TOKEN", ""),
    "home":        os.getenv("CH_WECHAT_TOKEN", ""),
    }[_SYS]

WECHAT_ENCODING_AES_KEY = {
    "local":       os.getenv("CH_WECHAT_AESKEY", ""),
    "server_01":   os.getenv("CH_WECHAT_AESKEY", ""),
    "server_02":   os.getenv("CH_WECHAT_AESKEY", ""),
    "test_server": os.getenv("CH_WECHAT_AESKEY", ""),
    "home":        os.getenv("CH_WECHAT_AESKEY", ""),
    }[_SYS]


#模板消息 ID(可选能力, Phase 3 视需要启用; 预留结构, 不填真实值)
WECHAT_TEMPLATE_ID = {
    "publishResult": {
        "local":"", "server_01":"", "server_02":"", "test_server":"", "home":"",
        }[_SYS],
    "credentialExpire": {
        "local":"", "server_01":"", "server_02":"", "test_server":"", "home":"",
        }[_SYS],
}


#默认请求超时(秒)与 access_token 提前刷新秒数(避免临界期失效)
WECHAT_HTTP_TIMEOUT = 15
WECHAT_TOKEN_REFRESH_AHEAD_SECONDS = 300


#★ SP4a(C6 投递链路) 开关与窗口 —— 推送≠发布(主计划 1.3 结论一 / 7.2 U-13·U-14):
#  - 正式发布(freepublish/submit)默认**关闭**, 且必须人工二次确认; 三重条件同时满足才允许调用:
#      ① ch_platform.autoPublishFlag = "1"; ② 本开关为真; ③ 请求显式携带 autoPublishConfirm=1
#  - 撤销窗(秒): 投递成功后 N 秒内允许撤销(用发布记录状态 + 时间判断实现, 不依赖 Redis)
WECHAT_AUTO_PUBLISH_ENABLED = {
    "local":       os.getenv("CH_WECHAT_AUTO_PUBLISH", "0") == "1",
    "server_01":   os.getenv("CH_WECHAT_AUTO_PUBLISH", "0") == "1",
    "server_02":   os.getenv("CH_WECHAT_AUTO_PUBLISH", "0") == "1",
    "test_server": os.getenv("CH_WECHAT_AUTO_PUBLISH", "0") == "1",
    "home":        os.getenv("CH_WECHAT_AUTO_PUBLISH", "0") == "1",
    }[_SYS]

WECHAT_REVOKE_WINDOW_SECONDS = 60


#凭据加密主密钥的环境变量名(密钥不入库、不入代码库; 本机无 KMS, 见 common/credentialCipher.py)
WECHAT_CREDENTIAL_KEY_ENV = "CH_CREDENTIAL_KEY"


_DEBUG = True  #预设trace开关，禁止修改

if __name__ == "__main__":
    pass
    # import pdb
    # pdb.set_trace()
    print ("_SYS", _SYS)
    print ("WECHAT_API_BASE", WECHAT_API_BASE)
    print ("WECHAT_APP_ID", WECHAT_APP_ID)
    print ("WECHAT_APP_SECRET(configured)", bool(WECHAT_APP_SECRET))
    print ("WECHAT_API_PATH", WECHAT_API_PATH)
    print ("WECHAT_AUTO_PUBLISH_ENABLED", WECHAT_AUTO_PUBLISH_ENABLED)
    print ("WECHAT_REVOKE_WINDOW_SECONDS", WECHAT_REVOKE_WINDOW_SECONDS)
    print ("WECHAT_CREDENTIAL_KEY_ENV", WECHAT_CREDENTIAL_KEY_ENV)
