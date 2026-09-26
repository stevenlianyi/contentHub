#! /usr/bin/env python3
#encoding: utf-8

#Filename: wechatMp.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 微信公众号平台适配器(SP3a · C5 形态转换 / SP4a · C6 通道调用, 主计划 2.5 / 5.4 P3-1)。

#职责(只做「形态转换 + 通道调用」, 业务编排留在 processor/publishService.py):
#  1) render      公众号形态产物: 引擎片段 -> 内联样式化 + class 清洗 + 外链图片策略
#                 + carousel 交互降级(allowSvgFlag="0" 时复用静态图集兜底节点);
#                 ★ SP4a: options.transferFunc 就绪时, 外链图片**真实转存**为 mmbiz.qpic.cn(补齐 E4 分支);
#  2) validate    按 ch_platform(wechat_mp) 数据驱动校验: 标题/摘要上限、封面 900x500、
#                 正文图规格 1080x1440、图片数量上限(校验逻辑在 base.checkPlatformSpec);
#  3) package     草稿载荷清单(包含 title/digest/content/images/cover, 供 deliver 投递);
#  4) deliver     ★ SP4a 起实现「通道调用」: 封面素材上传(material/add_material) + 新建草稿(draft/add);
#                 **仅做通道调用**; 幂等/二次确认/撤销窗/合规/落库一律由 publishService 编排;
#                 正式发布(freepublish/submit)由 publishService 在**人工确认 + 显式开关**通过后
#                 调 submitFreePublish 完成, deliver 本身**绝不群发**(推送≠发布);
#  5) checkHealth 只读 ch_account 配置态, **不发任何网络请求**;
#     ★ 2026-09-24: 凭据是否配置只看 ch_account.credentialCipher(用户录入 + 加密落库),
#       不再以环境变量 CH_WECHAT_APPID/APPSECRET 判定(见 publishService.decryptAccountCredential 注释)。
#
#★ 平台差异集中在本文件(模板不得出现平台专属域名 —— plan.md §4 模板约定):
#  DISPLAY_HOST_LIST = 微信正文图「已是平台可显示地址」的域白名单(mmbiz.qpic.cn);
#  非白名单 http(s) 外链在**无凭据/未注入 transferFunc** 时由 engine/inlineStyle.resolveImageUrl
#  显式返回 E4(**绝不静默保留外链**); 凭据就绪时由本文件的转存通道真实上传为 mmbiz.qpic.cn 地址。
#
#★ 网络边界(SP4a): 本文件是「平台通道调用」的落点 —— 只调微信开放平台接口
#  (access_token / material/add_material / media/uploadimg / draft/add / freepublish/submit);
#  凭据由 publishService 解密后经 options 传入(本文件**不读库、不解密、不落库**)。
#
#★ 分层契约: 本文件属业务处理器层(processor/), 只依赖 engine/ 与 common/, 不 import main/subfunc。

_VERSION="20260919"


import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # .../code/src
if parentdir not in sys.path:
    sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import json
import traceback
import uuid
import urllib.error
import urllib.parse
import urllib.request

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#数据层唯一入口(红线 R1): 本文件只读 ch_account(健康巡检)
from common import mysqlCommon as comMysql

#setting files(接口配置态: 基址/路径/超时/开关; ★ 凭据不取本文件, 一律来自 ch_account)
from config import wechatSettings

#平台适配契约
from processor.platformAdapter import base

#引擎层(单向依赖: processor -> engine)
from engine import layoutEngine

from engine import inlineStyle


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    #与接入层共用同一 logger(同名 logger 唯一, miscCommon.setLogNew 内部有 handlers 判重)
    try:
        from common import globalDefinition as comGD
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None


#===== 平台专属常量 begin =====

#平台编码与投递形态(与 ch_platform.platformCode / deliverMode 一致)
PLATFORM_CODE = "wechat_mp"
DELIVER_MODE = "draft_box"

#★ 平台差异: 微信正文图「可直接显示」的域白名单。
#  非白名单外链需转存到微信 CDN(mmbiz.qpic.cn)后才能在正文显示:
#    - 无凭据/未注入 transferFunc -> engine/inlineStyle.resolveImageUrl 显式 E4(绝不静默保留外链);
#    - 凭据就绪(SP4a) -> render 经 options.transferFunc 真实转存, deliver 侧再校验无残留外链。
DISPLAY_HOST_LIST = ["mmbiz.qpic.cn"]

#通道调用相关常量(SP4a · C6 投递)
DEFAULT_HTTP_TIMEOUT = 15                       #秒(可被 options.timeout / wechatSettings 覆盖)
DEFAULT_ARTICLE_IMAGE_MEDIA_TYPE = "image"      #material/add_material 的 type
DEFAULT_COVER_SHOW_FLAG = 1                     #草稿封面展示开关
#access_token 失效类 errcode(命中即按 F0「凭据无效」回显, 由 publishService 触发刷新/告警)
TOKEN_INVALID_ERRCODE_LIST = [40001, 40014, 40125, 42001, 41001, 40003]

#投递通道错误码(contenthub F 段; 与 common/errMsgCommon.py 一致)
ERR_CREDENTIAL = "F0"           #凭据缺失/无效/过期
ERR_PLATFORM_REJECTED = "F3"    #平台拒绝了本次请求
ERR_FIELD_MISSING = "C4"        #必填缺失(如 accessToken/封面)
ERR_IMAGE_TRANSFER_REQUIRED = "E4"   #仍有外链未转存(绝不静默保留)

#===== 平台专属常量 end =====


class WechatMpAdapter(base.PlatformAdapter):
    """微信公众号适配器(deliverMode=draft_box)。"""

    platformCode = PLATFORM_CODE
    deliverMode = DELIVER_MODE

    #----- 契约: render -----

    def render(self, topicData, layoutRecord, assetList, overrideSpec = None, options = None):
        """引擎片段 -> 公众号形态产物(内联样式 + 无 class + 交互降级 + 外链图片策略)。
           出参 data: {"outputKind","content","meta","platformCode","deliverMode"}。"""
        options = options if isinstance(options, dict) else {}
        assetList = assetList if isinstance(assetList, (list, tuple)) else []

        #1) 平台规格前置校验(失败直接返回, 不做无效渲染)
        validateRtn = self.validate(topicData, assetList)
        if validateRtn.get("errCode") != base.ERR_OK:
            return validateRtn

        #2) 引擎渲染(片段形态: embedMode=True, 供内联化与站内预览包裹)
        try:
            rendered = layoutEngine.renderLayout(layoutRecord, topicData, assetList,
                                                 overrideSpec, embedMode = True)
        except layoutEngine.LayoutEngineError as e:
            return base._err(e.errCode, e.field or base._fieldLabel("layoutCode", self.platformCode), [e.message])
        except Exception as e:
            if _LOG:
                _LOG.error(f"PID:{_processorPID}, wechatMp render failed, errMsg:{e}, {traceback.format_exc()}")
            return base._err(base.ERR_RENDER_FAILED, base._fieldLabel("layoutCode", self.platformCode),
                             [f"公众号形态渲染异常: {str(e)}"])

        #3) 内联化 + class 清洗 + 外链图片策略 + 交互降级(公众号 allowSvgFlag="0" -> 降级为静态图集兜底)
        #   ★ SP4a: 若业务层(publishService)在凭据就绪后注入 options.transferFunc, 则外链图片**真实转存**
        #   为 mmbiz.qpic.cn 可显示地址(补齐 §4 中 E4 的真实实现分支); 未注入时保持 SP3a 显式 E4 行为。
        needDegrade = (self.allowSvgFlag != "1")
        transferFunc = options.get("transferFunc")
        inlineRtn = inlineStyle.inlineHtml(rendered.get("content", ""),
                                           displayHostList = DISPLAY_HOST_LIST,
                                           degradeInteraction = needDegrade,
                                           transferFunc = transferFunc)
        if inlineRtn.get("errCode") != base.ERR_OK:
            return base._err(inlineRtn.get("errCode"), inlineRtn.get("field"),
                             inlineRtn.get("errMsgList"), inlineRtn.get("data"))
        inlineData = inlineRtn.get("data") or {}
        content = inlineData.get("content", "")

        #4) 出参 meta(保留引擎 meta, 叠加平台适配信息)
        meta = dict(rendered.get("meta") or {})
        meta.update({
            "platformCode": self.platformCode,
            "platformName": self.platformRecord.get("platformName"),
            "deliverMode": self.deliverMode,
            "adapter": self.__class__.__name__,
            "inlineStyled": "1",
            "classFree": "0" if inlineData.get("classDependency") else "1",
            "interactionDegraded": "1" if inlineData.get("degraded") else "0",
            "imageCount": inlineData.get("imageCount", 0),
            "needUploadCount": inlineData.get("needUploadCount", 0),
            "transferredImageCount": inlineData.get("transferredImageCount", 0),
            "specCheck": "passed",
            "coverSpec": self.coverSpec,
            "imageSpec": self.imageSpec,
            "imageMaxCount": self.imageMaxCount,
            #SP4a: 注入转存通道后 render 会真实调微信接口; 未注入时仍为零网络(SP3a 行为不变)
            "networkRequest": "1" if transferFunc else "0",
        })
        meta["renderOutputKind"] = rendered.get("outputKind")

        #5) 站内预览(P1-8): 用微信手机框包裹**已降级**的平台片段
        previewKind = base._toStr(options.get("previewKind"))
        if previewKind:
            content = layoutEngine.renderPreview(previewKind, content, topicData, meta)
            meta["previewKind"] = previewKind

        return base._ok({
            "outputKind": "html",
            "content": content,
            "meta": meta,
            "platformCode": self.platformCode,
            "deliverMode": self.deliverMode,
        })

    #----- 契约: validate -----

    def validate(self, topicData, assetList, platformRecord = None):
        """平台规格校验(数据驱动: ch_platform 的 titleMaxLen/summaryMaxLen/coverSpec/imageSpec/imageMaxCount)"""
        record = platformRecord if isinstance(platformRecord, dict) else self.platformRecord
        return base.checkPlatformSpec(record, topicData, assetList)

    #----- 契约: package -----

    def package(self, renderResult, topicData, assetList, options = None):
        """草稿载荷清单(结构化, 供 deliver 通道投递; 不落盘)。
           ★ SP4a: 载荷含 content(内联样式 HTML)/images(正文图地址)/cover(封面地址或 fileID),
             供 deliver 做素材上传与 draft/add; 幂等/二次确认/落库由 publishService 编排。"""
        renderResult = renderResult if isinstance(renderResult, dict) else {}
        topicData = topicData if isinstance(topicData, dict) else {}
        assetList = assetList if isinstance(assetList, (list, tuple)) else []

        content = base._toStr(renderResult.get("content"))
        summary = base._toStr(topicData.get("summary"))
        if self.summaryMaxLen > 0 and len(summary) > self.summaryMaxLen:
            summary = summary[:self.summaryMaxLen]

        #封面(usageType=cover)优先; 收起 fileUrl/fileID(供 deliver 上传素材拿 thumb_media_id)
        coverAsset = {}
        for item in assetList:
            if isinstance(item, dict) and base._toStr(item.get("usageType")).lower() == "cover":
                coverAsset = item
                break

        #正文图清单(供 deliver 校验是否仍残留未转存外链)
        imageList = []
        for item in assetList:
            if not isinstance(item, dict):
                continue
            if base._toStr(item.get("usageType")).lower() == "cover":
                continue
            imageList.append({
                "fileID": base._toStr(item.get("fileID")),
                "url": base._toStr(item.get("fileUrl")) or base._toStr(item.get("url")),
                "caption": base._toStr(item.get("caption")),
                "sortOrder": base._toInt(item.get("sortOrder"), 0),
            })

        plan = {
            "platformCode": self.platformCode,
            "deliverMode": self.deliverMode,
            "packageKind": "wechat_draft_payload",
            "title": base._toStr(topicData.get("title")),
            "author": base._toStr(topicData.get("author")),
            "digest": summary,
            "content": content,
            "contentLength": len(content),
            "imageCount": len(imageList),
            "imageList": imageList,
            "coverFileID": base._toStr(coverAsset.get("fileID")),
            "coverUrl": base._toStr(coverAsset.get("fileUrl")) or base._toStr(coverAsset.get("url")),
            "coverSpec": self.coverSpec,
            "thumbMediaIdRequired": True,
            "displayHostList": list(DISPLAY_HOST_LIST),
            "note": "草稿载荷清单; 通道投递由 deliver 执行, 幂等/二次确认/撤销窗/合规/落库由 publishService 编排",
        }
        return base._ok(plan)

    #----- 契约: deliver(SP4a 通道调用) -----

    def deliver(self, packageResult = None, options = None):
        """★ 投递通道(SP4a · C6 通道调用, deliverMode=draft_box):
             - 封面素材上传(material/add_material)拿 thumb_media_id;
             - 新建草稿(draft/add)并把 media_id 作为 remoteID 回传;
             - **仅做通道调用**: 幂等/二次确认/撤销窗/合规/落库一律由 publishService 编排;
             - **绝不群发**: 正式发布(freepublish/submit)由 publishService 在人工确认 + 显式开关
               通过后调 submitFreePublish 完成(推送≠发布);
             - 未提供 accessToken -> 显式 F0; 正文仍有未转存外链 -> 显式 E4(绝不静默保留)。
           入参 options: {"accessToken","timeout","transferFunc"(可选, deliver 内兜底转正文图)}
           出参 data: {"remoteID","draftMediaID","errcode","errmsg","transferredImageCount","contentLength"}"""
        options = options if isinstance(options, dict) else {}
        accessToken = base._toStr(options.get("accessToken"))
        if not accessToken:
            return base._err(ERR_CREDENTIAL, base._fieldLabel("accessToken", self.platformCode),
                             ["access_token 缺失: 凭据未就绪, 不能投递(请先完成凭据解密与换取)"])

        payload = self._resolvePayload(packageResult)
        if not payload:
            return base._err(ERR_FIELD_MISSING, base._fieldLabel("packageResult", self.platformCode),
                             ["草稿载荷为空: 请先经 package() 产出载荷清单"])

        timeout = base._toInt(options.get("timeout"), 0) or base._toInt(
            getattr(wechatSettings, "WECHAT_HTTP_TIMEOUT", DEFAULT_HTTP_TIMEOUT), DEFAULT_HTTP_TIMEOUT)

        content = base._toStr(payload.get("content"))
        #1) 正文图兜底转存(render 期已注入 transferFunc 时通常无需再转; 此处防漏网外链)
        transferFunc = options.get("transferFunc")
        transferredCount = 0
        if transferFunc:
            content, transferredCount = self._transferContentImages(content, transferFunc)
        remainList = listExternalImageUrls(content, DISPLAY_HOST_LIST)
        if remainList:
            return base._err(ERR_IMAGE_TRANSFER_REQUIRED, base._fieldLabel("content", self.platformCode),
                             [f"正文仍存在未转存外链图片({len(remainList)} 张), 拒绝投递: {remainList[:3]}"])

        #2) 封面素材上传(thumb_media_id 必需)
        coverBytes, coverName, coverErr = self._loadCoverBytes(payload)
        if coverErr:
            return base._err(ERR_FIELD_MISSING, base._fieldLabel("coverUrl", self.platformCode), [coverErr])

        materialRtn = addMaterial(accessToken, coverBytes, coverName,
                                  mediaType = DEFAULT_ARTICLE_IMAGE_MEDIA_TYPE, timeout = timeout)
        if materialRtn.get("errCode") != base.ERR_OK:
            return materialRtn
        thumbMediaID = base._toStr((materialRtn.get("data") or {}).get("mediaID"))

        #3) 新建草稿
        article = {
            "title": base._toStr(payload.get("title")),
            "author": base._toStr(payload.get("author")),
            "digest": base._toStr(payload.get("digest")),
            "content": content,
            "content_source_url": base._toStr(payload.get("contentSourceUrl")),
            "thumb_media_id": thumbMediaID,
            "need_open_comment": 0,
            "only_fans_can_comment": 0,
            "show_cover_pic": DEFAULT_COVER_SHOW_FLAG,
        }
        draftRtn = addDraft(accessToken, article, timeout = timeout)
        if draftRtn.get("errCode") != base.ERR_OK:
            return draftRtn

        draftData = draftRtn.get("data") or {}
        return base._ok({
            "remoteID": base._toStr(draftData.get("mediaID")),
            "draftMediaID": base._toStr(draftData.get("mediaID")),
            "thumbMediaID": thumbMediaID,
            "errcode": base._toInt(draftData.get("errcode"), 0),
            "errmsg": base._toStr(draftData.get("errmsg")),
            "transferredImageCount": transferredCount,
            "contentLength": len(content),
            "platformCode": self.platformCode,
            "deliverMode": self.deliverMode,
        })

    #----- deliver 内部辅助 -----

    @staticmethod
    def _resolvePayload(packageResult):
        """兼容两种入参: package() 的完整出参({"errCode","data":plan}) 或 plan 本体"""
        if not isinstance(packageResult, dict):
            return {}
        if base._toStr(packageResult.get("packageKind")):
            return packageResult
        data = packageResult.get("data")
        if isinstance(data, dict) and data:
            return data
        return {}

    def _transferContentImages(self, content, transferFunc):
        """正文图兜底转存: 逐个外链经 transferFunc 转存并替换 src; 返回 (新 content, 转存张数)"""
        content = content if isinstance(content, str) else ""
        if not content:
            return content, 0
        transferredCount = 0
        for src in inlineStyle.extractImageSrcList(content):
            rtn = inlineStyle.resolveImageUrl(src, displayHostList = DISPLAY_HOST_LIST,
                                              transferFunc = transferFunc)
            newUrl = base._toStr(rtn.get("url"))
            if rtn.get("errCode") == base.ERR_OK and newUrl and newUrl != src:
                content = content.replace(src, newUrl)
                transferredCount += 1
        return content, transferredCount

    def _loadCoverBytes(self, payload):
        """取封面图片字节: 优先 http(s) 直下; 否则用 fileID 经文件门面换临时地址再下。
           出参 (bytes, fileName, errMsg); 失败时 errMsg 非空。"""
        coverUrl = base._toStr(payload.get("coverUrl"))
        coverFileID = base._toStr(payload.get("coverFileID"))

        if not coverUrl and coverFileID:
            try:
                from common import fileStorageCommon as comFS
                coverUrl = base._toStr(comFS.getTempLocation(coverFileID))
            except Exception as e:
                return b"", "", f"封面 fileID 换地址失败: {str(e)}"

        if not coverUrl:
            return b"", "", "封面缺失: 请为主题绑定 usageType=cover 的封面图"

        #已是微信显示域时仍必须上传素材拿 thumb_media_id, 故这里一律下载原始字节
        try:
            imageBytes, contentType = downloadImageBytes(coverUrl)
        except Exception as e:
            return b"", "", f"封面下载失败: {str(e)}"

        fileName = coverFileName(coverUrl, contentType)
        return imageBytes, fileName, ""

    #----- 通道原语(供业务层 publishService 编排调用; 本层不做业务判定) -----

    def fetchAccessToken(self, appID, appSecret, timeout = None):
        """通道原语: 单次换取 access_token(进程内缓存与提前刷新在 publishService)"""
        return fetchAccessToken(appID, appSecret, timeout = timeout)

    def buildTransferFunc(self, accessToken, timeout = None):
        """通道原语: 构造外链图片转存回调(供 render 注入 engine/inlineStyle.resolveImageUrl 的 transferFunc)"""
        return buildTransferFunc(accessToken, timeout = timeout)

    def submitFreePublish(self, accessToken, mediaID, timeout = None):
        """通道原语: 提交发布(freepublish/submit)。
           ★ 仅 publishService 在「人工二次确认 + autoPublishFlag=1 + 配置开关=1」三重闸门通过后调用;
           deliver 本身**绝不群发**(推送≠发布)。"""
        return submitFreePublish(accessToken, mediaID, timeout = timeout)

    #----- 契约: checkHealth(只读, 零网络) -----

    def checkHealth(self, sessionIDSet = None):
        """凭据/账号健康巡检: 只读 ch_account 配置态, **不发任何网络请求**
           ★ 2026-09-24 手改(凭据来源收口): 凭据是否配置**只看 ch_account.credentialCipher**
             (用户录入 + 加密落库), 不再以环境变量 CH_WECHAT_APPID/APPSECRET 判定。"""
        accountList = []
        errMsg = ""
        try:
            tableName = comMysql.tablename_convertor_ch_account()
            accountList = comMysql.query_ch_account(tableName, platform = self.platformCode, mode = "full")
        except Exception as e:
            errMsg = str(e)
            if _LOG:
                _LOG.warning(f"W: PID:{_processorPID}, wechatMp checkHealth 读取 ch_account 失败, errMsg:{str(e)}")

        cipheredList = [item for item in accountList
                        if isinstance(item, dict) and base._toStr(item.get("credentialCipher"))]
        #未录入凭据的账号清单(仅报账号标识, 不出现任何凭据明/密文)
        missingList = [(base._toStr(item.get("accountCode")) or f"recID={base._toStr(item.get('recID'))}")
                       for item in accountList
                       if isinstance(item, dict) and not base._toStr(item.get("credentialCipher"))]

        healthStatusList = sorted({base._toStr(item.get("healthStatus")) or "UNKNOWN"
                                   for item in accountList if isinstance(item, dict)})

        return base._ok({
            "platformCode": self.platformCode,
            "deliverMode": self.deliverMode,
            "credentialConfigured": "1" if cipheredList else "0",
            "credentialSource": "ch_account.credentialCipher",
            "credentialMissingList": missingList,
            "accountCount": len(accountList),
            "healthStatusList": healthStatusList,
            "networkRequest": "0",
            "checkedAt": misc.getTime(),
            "errMsg": errMsg,
        })


#===== 通道调用(SP4a · C6 投递; 仅本文件持有平台差异) begin =====
#说明: 以下为微信开放平台的「通道原语」, 由 publishService 编排调用(凭据/幂等/确认/落库在业务层);
#       access_token 的缓存与提前刷新在 publishService(业务层), 本文件只负责单次换取与调用。

def buildApiUrl(pathKey, accessToken = ""):
    """拼接开放平台接口地址(基址与路径常量集中取自 config/wechatSettings.py)"""
    baseUrl = base._toStr(getattr(wechatSettings, "WECHAT_API_BASE", "")).rstrip("/")
    pathMap = getattr(wechatSettings, "WECHAT_API_PATH", {}) or {}
    path = base._toStr(pathMap.get(pathKey))
    if not baseUrl or not path:
        raise RuntimeError(f"微信接口地址未配置: base={baseUrl}, pathKey={pathKey}")
    url = baseUrl + path
    if accessToken:
        url += "?access_token=" + urllib.parse.quote(base._toStr(accessToken))
    return url


def _httpTimeout(timeout):
    timeout = base._toInt(timeout, 0)
    if timeout <= 0:
        timeout = base._toInt(getattr(wechatSettings, "WECHAT_HTTP_TIMEOUT", DEFAULT_HTTP_TIMEOUT),
                              DEFAULT_HTTP_TIMEOUT)
    return timeout


def httpRequest(method, url, dataBytes = None, headers = None, timeout = None):
    """低层 HTTP 调用(urllib 标准库; 便于静态/冒烟阶段桩替换)。
       出参: (httpStatus, bodyBytes, errMsg); 网络异常返回 (0, b"", errMsg), 不抛裸异常。"""
    request = urllib.request.Request(url, data = dataBytes, headers = headers or {}, method = method)
    try:
        with urllib.request.urlopen(request, timeout = _httpTimeout(timeout)) as response:
            return int(getattr(response, "status", 200) or 200), response.read(), ""
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
        except Exception:
            body = b""
        return int(getattr(e, "code", 0) or 0), body, f"HTTPError:{getattr(e, 'code', '')}"
    except Exception as e:
        return 0, b"", str(e)


def _decodeJson(bodyBytes):
    try:
        return json.loads((bodyBytes or b"").decode("utf-8"))
    except Exception:
        return None


def _platformErrRtn(jsonData, fieldName, defaultErrCode = ERR_PLATFORM_REJECTED):
    """平台返回 errcode != 0 -> 统一错误出参(access_token 失效类按 F0 回显, 其余 F3)"""
    errcode = base._toInt((jsonData or {}).get("errcode"), 0)
    errmsg = base._toStr((jsonData or {}).get("errmsg"))
    errCode = ERR_CREDENTIAL if errcode in TOKEN_INVALID_ERRCODE_LIST else defaultErrCode
    return base._err(errCode, base._fieldLabel(fieldName, PLATFORM_CODE),
                     [f"微信接口返回 errcode={errcode}, errmsg={errmsg or '(空)'}"],
                     {"errcode": errcode, "errmsg": errmsg})


def _buildMultipartBody(fields, files, boundary):
    """构造 multipart/form-data 请求体(fields: [(name,value)]; files: [(name,fileName,contentType,bytes)])"""
    chunks = []
    for name, value in (fields or []):
        chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n"
                      f"{base._toStr(value)}\r\n".encode("utf-8"))
    for name, fileName, contentType, fileBytes in (files or []):
        chunks.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; "
                       f"filename=\"{fileName}\"\r\nContent-Type: {contentType}\r\n\r\n").encode("utf-8"))
        chunks.append(fileBytes or b"")
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks)


def _multipartHeaders(boundary):
    return {"Content-Type": f"multipart/form-data; boundary={boundary}"}


def fetchAccessToken(appID, appSecret, timeout = None):
    """换取 access_token(单次调用; 缓存与提前刷新在 publishService)。
       出参 data: {"accessToken","expiresIn","httpStatus"}; 失败按 R-03 明确回显(F0)。"""
    appID = base._toStr(appID)
    appSecret = base._toStr(appSecret)
    if not appID or not appSecret:
        return base._err(ERR_CREDENTIAL, base._fieldLabel("appID", PLATFORM_CODE),
                         ["appID/appSecret 未配置: 无法换取 access_token(R-03 凭据缺失)"])

    try:
        url = buildApiUrl("accessToken")
    except Exception as e:
        return base._err(ERR_PLATFORM_REJECTED, base._fieldLabel("accessToken", PLATFORM_CODE), [str(e)])

    query = urllib.parse.urlencode({"grant_type": "client_credential", "appid": appID, "secret": appSecret})
    status, body, errMsg = httpRequest("GET", url + "?" + query, timeout = timeout)
    jsonData = _decodeJson(body)
    if jsonData is None:
        return base._err(ERR_PLATFORM_REJECTED, base._fieldLabel("accessToken", PLATFORM_CODE),
                         [f"access_token 响应非法(httpStatus={status}, errMsg={errMsg or '(空)'})"])

    if base._toInt(jsonData.get("errcode"), 0) != 0:
        return _platformErrRtn(jsonData, "accessToken", defaultErrCode = ERR_CREDENTIAL)

    accessToken = base._toStr(jsonData.get("access_token"))
    if not accessToken:
        return base._err(ERR_CREDENTIAL, base._fieldLabel("accessToken", PLATFORM_CODE),
                         ["access_token 响应缺少 access_token 字段"])
    return base._ok({"accessToken": accessToken, "expiresIn": base._toInt(jsonData.get("expires_in"), 0),
                     "httpStatus": status})


def uploadArticleImage(accessToken, imageBytes, fileName, timeout = None):
    """上传图文消息内的图片(media/uploadimg, 不占素材库配额) -> 返回 mmbiz.qpic.cn 地址。
       出参 data: {"url","httpStatus"}。"""
    if not base._toStr(accessToken):
        return base._err(ERR_CREDENTIAL, base._fieldLabel("accessToken", PLATFORM_CODE), ["access_token 为空"])
    if not imageBytes:
        return base._err(ERR_FIELD_MISSING, base._fieldLabel("imageBytes", PLATFORM_CODE), ["图片字节为空"])

    try:
        url = buildApiUrl("uploadImg", accessToken)
    except Exception as e:
        return base._err(ERR_PLATFORM_REJECTED, base._fieldLabel("uploadImg", PLATFORM_CODE), [str(e)])

    boundary = "----contentHub" + uuid.uuid4().hex
    body = _buildMultipartBody(None, [("media", fileName or "image.jpg", guessContentType(fileName), imageBytes)],
                               boundary)
    status, respBody, errMsg = httpRequest("POST", url, dataBytes = body,
                                           headers = _multipartHeaders(boundary), timeout = timeout)
    jsonData = _decodeJson(respBody)
    if jsonData is None:
        return base._err(ERR_PLATFORM_REJECTED, base._fieldLabel("uploadImg", PLATFORM_CODE),
                         [f"uploadimg 响应非法(httpStatus={status}, errMsg={errMsg or '(空)'})"])
    if base._toInt(jsonData.get("errcode"), 0) != 0:
        return _platformErrRtn(jsonData, "uploadImg")

    imageUrl = base._toStr(jsonData.get("url"))
    if not imageUrl:
        return base._err(ERR_PLATFORM_REJECTED, base._fieldLabel("uploadImg", PLATFORM_CODE),
                         ["uploadimg 未返回 url"])
    return base._ok({"url": imageUrl, "httpStatus": status})


def addMaterial(accessToken, imageBytes, fileName, mediaType = DEFAULT_ARTICLE_IMAGE_MEDIA_TYPE, timeout = None):
    """新增永久素材(material/add_material) -> 返回 media_id(草稿封面 thumb_media_id 必需)。
       出参 data: {"mediaID","url","httpStatus"}。"""
    if not base._toStr(accessToken):
        return base._err(ERR_CREDENTIAL, base._fieldLabel("accessToken", PLATFORM_CODE), ["access_token 为空"])
    if not imageBytes:
        return base._err(ERR_FIELD_MISSING, base._fieldLabel("coverBytes", PLATFORM_CODE), ["封面图片字节为空"])

    try:
        url = buildApiUrl("materialAdd", accessToken)
    except Exception as e:
        return base._err(ERR_PLATFORM_REJECTED, base._fieldLabel("materialAdd", PLATFORM_CODE), [str(e)])

    boundary = "----contentHub" + uuid.uuid4().hex
    body = _buildMultipartBody([("type", mediaType or DEFAULT_ARTICLE_IMAGE_MEDIA_TYPE)],
                               [("media", fileName or "cover.jpg", guessContentType(fileName), imageBytes)],
                               boundary)
    status, respBody, errMsg = httpRequest("POST", url, dataBytes = body,
                                           headers = _multipartHeaders(boundary), timeout = timeout)
    jsonData = _decodeJson(respBody)
    if jsonData is None:
        return base._err(ERR_PLATFORM_REJECTED, base._fieldLabel("materialAdd", PLATFORM_CODE),
                         [f"add_material 响应非法(httpStatus={status}, errMsg={errMsg or '(空)'})"])
    if base._toInt(jsonData.get("errcode"), 0) != 0:
        return _platformErrRtn(jsonData, "materialAdd")

    mediaID = base._toStr(jsonData.get("media_id"))
    if not mediaID:
        return base._err(ERR_PLATFORM_REJECTED, base._fieldLabel("materialAdd", PLATFORM_CODE),
                         ["add_material 未返回 media_id"])
    return base._ok({"mediaID": mediaID, "url": base._toStr(jsonData.get("url")), "httpStatus": status})


def addDraft(accessToken, article, timeout = None):
    """新建草稿(draft/add, 本项目公众号交付形态的终点) -> media_id。
       出参 data: {"mediaID","errcode","errmsg","httpStatus"}。"""
    if not base._toStr(accessToken):
        return base._err(ERR_CREDENTIAL, base._fieldLabel("accessToken", PLATFORM_CODE), ["access_token 为空"])
    if not isinstance(article, dict) or not base._toStr(article.get("thumb_media_id")):
        return base._err(ERR_FIELD_MISSING, base._fieldLabel("thumb_media_id", PLATFORM_CODE),
                         ["草稿缺少封面素材 thumb_media_id"])

    try:
        url = buildApiUrl("draftAdd", accessToken)
    except Exception as e:
        return base._err(ERR_PLATFORM_REJECTED, base._fieldLabel("draftAdd", PLATFORM_CODE), [str(e)])

    body = json.dumps({"articles": [article]}, ensure_ascii = False).encode("utf-8")
    status, respBody, errMsg = httpRequest("POST", url, dataBytes = body,
                                           headers = {"Content-Type": "application/json; charset=utf-8"},
                                           timeout = timeout)
    jsonData = _decodeJson(respBody)
    if jsonData is None:
        return base._err(ERR_PLATFORM_REJECTED, base._fieldLabel("draftAdd", PLATFORM_CODE),
                         [f"draft/add 响应非法(httpStatus={status}, errMsg={errMsg or '(空)'})"])
    if base._toInt(jsonData.get("errcode"), 0) != 0:
        return _platformErrRtn(jsonData, "draftAdd")

    mediaID = base._toStr(jsonData.get("media_id"))
    if not mediaID:
        return base._err(ERR_PLATFORM_REJECTED, base._fieldLabel("draftAdd", PLATFORM_CODE),
                         ["draft/add 未返回 media_id"])
    return base._ok({"mediaID": mediaID, "errcode": 0, "errmsg": "ok", "httpStatus": status})


def submitFreePublish(accessToken, mediaID, timeout = None):
    """★ 提交发布(freepublish/submit, 仅认证企业号/服务号可用)。
       **本函数不得被默认调用**: 必须由 publishService 在「人工二次确认 + ch_platform.autoPublishFlag=1
       + 配置开关 WECHAT_AUTO_PUBLISH_ENABLED=1」三重条件通过后才调用(推送≠发布, 绝不默认群发)。"""
    if not base._toStr(accessToken) or not base._toStr(mediaID):
        return base._err(ERR_FIELD_MISSING, base._fieldLabel("mediaID", PLATFORM_CODE),
                         ["access_token 或 media_id 为空"])

    try:
        url = buildApiUrl("freePublishSubmit", accessToken)
    except Exception as e:
        return base._err(ERR_PLATFORM_REJECTED, base._fieldLabel("freePublishSubmit", PLATFORM_CODE), [str(e)])

    body = json.dumps({"media_id": base._toStr(mediaID)}, ensure_ascii = False).encode("utf-8")
    status, respBody, errMsg = httpRequest("POST", url, dataBytes = body,
                                           headers = {"Content-Type": "application/json; charset=utf-8"},
                                           timeout = timeout)
    jsonData = _decodeJson(respBody)
    if jsonData is None:
        return base._err(ERR_PLATFORM_REJECTED, base._fieldLabel("freePublishSubmit", PLATFORM_CODE),
                         [f"freepublish/submit 响应非法(httpStatus={status}, errMsg={errMsg or '(空)'})"])
    if base._toInt(jsonData.get("errcode"), 0) != 0:
        return _platformErrRtn(jsonData, "freePublishSubmit")

    return base._ok({"publishID": base._toStr(jsonData.get("publish_id")), "errcode": 0, "errmsg": "ok"})


def downloadImageBytes(imageUrl, timeout = None):
    """下载外链图片字节(转存前置); 非 http(s) 显式报错。
       出参: (imageBytes, contentType)。"""
    imageUrl = base._toStr(imageUrl)
    if not (imageUrl.lower().startswith("http://") or imageUrl.lower().startswith("https://")):
        raise RuntimeError(f"仅支持 http(s) 外链图片转存: {imageUrl}")
    request = urllib.request.Request(imageUrl, headers = {"User-Agent": "contentHub/1.0"})
    with urllib.request.urlopen(request, timeout = _httpTimeout(timeout)) as response:
        imageBytes = response.read()
        contentType = base._toStr(response.headers.get_content_type()) or "image/jpeg"
    return imageBytes, contentType


#常见图片扩展名 -> Content-Type(不引入第三方依赖)
_CONTENT_TYPE_MAP = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp",
}


def guessContentType(fileName):
    ext = base._toStr(fileName).rsplit(".", 1)[-1].lower() if "." in base._toStr(fileName) else ""
    return _CONTENT_TYPE_MAP.get(ext, "image/jpeg")


def coverFileName(imageUrl, contentType = ""):
    """由图片地址/Content-Type 推一个安全的文件名(供 multipart 上传)"""
    imageUrl = base._toStr(imageUrl)
    fileName = urllib.parse.unquote(imageUrl.split("?")[0].rsplit("/", 1)[-1]) or "cover.jpg"
    if "." not in fileName:
        ext = "jpg"
        for key, value in _CONTENT_TYPE_MAP.items():
            if value == base._toStr(contentType):
                ext = key
                break
        fileName = fileName + "." + ext
    return fileName[:80]


def listExternalImageUrls(content, displayHostList = None):
    """列出正文中「非平台显示域」的 http(s) 图片地址(供 deliver 拒绝残留外链); 非 http(s)/fileID 不计入"""
    content = content if isinstance(content, str) else ""
    hostList = [base._toStr(item).lower() for item in (displayHostList or []) if base._toStr(item)]
    externalList = []
    for src in inlineStyle.extractImageSrcList(content):
        lowerUrl = src.lower()
        if not (lowerUrl.startswith("http://") or lowerUrl.startswith("https://")):
            continue
        if inlineStyle.ANY_HOST_TOKEN in hostList:
            continue
        atHost = (inlineStyle.extractHost(src) or "").lower()
        if atHost and atHost in hostList:
            continue
        externalList.append(src)
    return externalList


def buildTransferFunc(accessToken, timeout = None, displayHostList = None):
    """构造「转存回调」(供 engine/inlineStyle.resolveImageUrl 的 transferFunc 使用):
       外链图片 -> media/uploadimg -> 返回 mmbiz.qpic.cn 地址(同 URL 结果本地缓存, 避免重复上传)。
       ★ 回调抛异常时 resolveImageUrl 会保留 E4 语义(绝不静默保留外链)。
       出参: transferFunc(imageUrl) -> newUrl。"""
    hostList = displayHostList if displayHostList is not None else DISPLAY_HOST_LIST
    cache = {}

    def _transfer(imageUrl):
        imageUrl = base._toStr(imageUrl)
        if not imageUrl:
            return ""
        if imageUrl in cache:
            return cache[imageUrl]

        #已是平台显示域: 无需转存
        decideRtn = inlineStyle.resolveImageUrl(imageUrl, displayHostList = hostList)
        if decideRtn.get("errCode") == base.ERR_OK and not decideRtn.get("needTransfer"):
            cache[imageUrl] = imageUrl
            return imageUrl

        imageBytes, contentType = downloadImageBytes(imageUrl, timeout = timeout)
        uploadRtn = uploadArticleImage(accessToken, imageBytes, coverFileName(imageUrl, contentType), timeout = timeout)
        if uploadRtn.get("errCode") != base.ERR_OK:
            raise RuntimeError("图片转存失败: " + ";".join(uploadRtn.get("errMsgList") or [uploadRtn.get("errCode")]))

        newUrl = base._toStr((uploadRtn.get("data") or {}).get("url"))
        if not newUrl:
            raise RuntimeError("图片转存未返回平台地址")
        cache[imageUrl] = newUrl
        return newUrl

    return _transfer

#===== 通道调用 end =====


if __name__ == "__main__":
    pass
    #本地自测(不连库/不联网): 只验证纯函数
    _adapter = WechatMpAdapter({"platformCode": "wechat_mp", "titleMaxLen": 64, "coverSpec": "900x500"})
    print("platformCode:", _adapter.platformCode, "deliverMode:", _adapter.deliverMode)
    print("validate(empty title):", _adapter.validate({}, [])["errCode"])
    print("deliver(no token):", _adapter.deliver({}, {})["errCode"])
    print("listExternalImageUrls:", listExternalImageUrls(
        '<img src="https://example.com/a.jpg"/><img src="https://mmbiz.qpic.cn/b.jpg"/>', DISPLAY_HOST_LIST))
