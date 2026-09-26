#! /usr/bin/env python3
#encoding: utf-8

#Filename: generic.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 通用平台适配器(SP3a · C5, 主计划 2.5 / 5.4 P2-4)。

#★ 降级实现声明(主计划 5.4 缓冲建议, 已按允许范围执行):
#  本适配器的 **HTML 导出复用 stack_v1 已渲染输出**(即降级实现: 不再单独实现一套通用版式),
#  仅在其上做「内联样式化 + class 清洗 + 任意外链放行」, 并额外提供 Markdown / JSON 结构化导出。
#  引入独立通用版式的增强版归后续子计划; 本轮以此降级换取 1 人天缓冲(见主计划 5.4 注)。
#
#职责(只做「形态转换 + 通道调用」, 业务编排留在 processor/renderService.py):
#  1) render      exportKind ∈ {html, markdown, json}:
#                   html     -> 复用 stack_v1 片段(内联化后输出; 任意 http(s) 外链放行)
#                   markdown -> 由主题 + 附图生成 Markdown
#                   json     -> {topic, assets, meta} 结构化 JSON
#  2) validate    按 ch_platform(generic) 数据驱动校验(标题/摘要上限、图片数量上限; 无封面/正文图规格约束);
#  3) package     素材包清单(本轮只出清单, 不落盘; ZIP 归 SP4);
#  4) deliver     ★ 本轮**一律返回「未实现」显式错误**(投递归 SP4), 继承自基类, 不覆写;
#  5) checkHealth 只读配置态, **不发任何网络请求**(通用形态无需凭据)。
#
#★ 通用形态的平台差异: 任意 http(s) 地址均视为可显示(DISPLAY_HOST_LIST=["*"], allowAnyHost=True)。
#
#★ 零网络红线(SP3a) + 分层契约: 只依赖 engine/ 与 common/, 不 import main/subfunc。

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

import traceback

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#平台适配契约
from processor.platformAdapter import base

#引擎层(单向依赖: processor -> engine)
from engine import layoutEngine

from engine import inlineStyle


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    try:
        from common import globalDefinition as comGD
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None


#===== 平台专属常量 begin =====

PLATFORM_CODE = "generic"
DELIVER_MODE = "asset_pack"

#★ 平台差异: 通用形态任意 http(s) 地址均可显示(不触发转存判定)
DISPLAY_HOST_LIST = ["*"]
ANY_HOST = True

#通用导出的三种形态(与 ch_platform.limitNote「站内预览/导出/第三方站点」定位一致)
EXPORT_KIND_LIST = ["html", "markdown", "json"]

#===== 平台专属常量 end =====


def buildMarkdown(topicData, assetList):
    """由主题 + 附图生成 Markdown(标题/摘要/元信息/正文/附图/话题标签)"""
    topicData = topicData if isinstance(topicData, dict) else {}
    assetList = assetList if isinstance(assetList, (list, tuple)) else []

    lines = []
    title = base._toStr(topicData.get("title"))
    if title:
        lines.append(f"# {title}")

    summary = base._toStr(topicData.get("summary"))
    if summary:
        lines.append(f"> {summary}")

    metaBits = []
    for label, key in (("作者", "author"), ("来源", "source"), ("地点", "location"), ("时期", "period")):
        value = base._toStr(topicData.get(key))
        if value:
            metaBits.append(f"{label}: {value}")
    if metaBits:
        lines.append(" / ".join(metaBits))

    description = base._toStr(topicData.get("description")).replace("\r\n", "\n").replace("\r", "\n")
    for para in [item.strip() for item in description.split("\n") if item.strip()]:
        lines.append(para)

    for idx, item in enumerate(assetList):
        if not isinstance(item, dict):
            continue
        url = base._toStr(item.get("fileUrl"))
        caption = base._toStr(item.get("caption"))
        lines.append(f"![{caption or ('图' + str(idx + 1))}]({url})")
        if caption:
            lines.append(f"*{caption}*")

    tagList = topicData.get("tagList")
    if isinstance(tagList, (list, tuple)):
        tagList = [base._toStr(tag) for tag in tagList if base._toStr(tag)]
    else:
        tagList = [base._toStr(tag) for tag in base._toStr(tagList).replace("，", ",").split(",") if base._toStr(tag)]
    if tagList:
        lines.append(" ".join(f"#{tag}" for tag in tagList))

    return "\n\n".join(lines)


class GenericAdapter(base.PlatformAdapter):
    """通用平台适配器(deliverMode=asset_pack); HTML 导出为**复用 stack_v1 输出**的降级实现。"""

    platformCode = PLATFORM_CODE
    deliverMode = DELIVER_MODE

    #----- 契约: render -----

    def render(self, topicData, layoutRecord, assetList, overrideSpec = None, options = None):
        """通用形态产物(html / markdown / json); 出参 data 同 wechatMp(含 outputKind/content/meta)。"""
        options = options if isinstance(options, dict) else {}
        assetList = assetList if isinstance(assetList, (list, tuple)) else []

        exportKind = base._toStr(options.get("exportKind")).lower() or "html"
        if exportKind not in EXPORT_KIND_LIST:
            return base._err(base.ERR_FIELD_INVALID, base._fieldLabel("exportKind", self.platformCode),
                             [f"exportKind 取值非法: {exportKind}, 允许值={EXPORT_KIND_LIST}"])

        #1) 平台规格前置校验(generic 无封面/正文图规格约束, 仅标题/摘要/数量)
        validateRtn = self.validate(topicData, assetList)
        if validateRtn.get("errCode") != base.ERR_OK:
            return validateRtn

        #2) 引擎渲染(片段形态; html 导出复用 stack_v1 输出 —— 降级实现)
        try:
            rendered = layoutEngine.renderLayout(layoutRecord, topicData, assetList,
                                                 overrideSpec, embedMode = True)
        except layoutEngine.LayoutEngineError as e:
            return base._err(e.errCode, e.field or base._fieldLabel("layoutCode", self.platformCode), [e.message])
        except Exception as e:
            if _LOG:
                _LOG.error(f"PID:{_processorPID}, generic render failed, errMsg:{e}, {traceback.format_exc()}")
            return base._err(base.ERR_RENDER_FAILED, base._fieldLabel("layoutCode", self.platformCode),
                             [f"通用形态渲染异常: {str(e)}"])

        #3) 内联化 + class 清洗(通用形态不降级交互, 任意外链放行)
        inlineRtn = inlineStyle.inlineHtml(rendered.get("content", ""),
                                          displayHostList = DISPLAY_HOST_LIST,
                                          degradeInteraction = False,
                                          allowAnyHost = ANY_HOST)
        if inlineRtn.get("errCode") != base.ERR_OK:
            return base._err(inlineRtn.get("errCode"), inlineRtn.get("field"),
                             inlineRtn.get("errMsgList"), inlineRtn.get("data"))
        inlineData = inlineRtn.get("data") or {}
        htmlContent = inlineData.get("content", "")

        #4) 按导出形态产出 content / outputKind
        outputKind = "html"
        content = htmlContent
        if exportKind == "markdown":
            outputKind = "markdown"
            content = buildMarkdown(topicData, assetList)
        elif exportKind == "json":
            outputKind = "json"
            content = misc.jsonDumps({
                "topic": topicData if isinstance(topicData, dict) else {},
                "assets": assetList,
                "meta": rendered.get("meta") or {},
                "exportedAt": misc.getTime(),
            }, indent = 2)

        meta = dict(rendered.get("meta") or {})
        meta.update({
            "platformCode": self.platformCode,
            "platformName": self.platformRecord.get("platformName"),
            "deliverMode": self.deliverMode,
            "adapter": self.__class__.__name__,
            "exportKind": exportKind,
            "inlineStyled": "1",
            "classFree": "0" if inlineData.get("classDependency") else "1",
            "imageCount": inlineData.get("imageCount", 0),
            "specCheck": "passed",
            "degradedImpl": "stack_v1_reuse",
            "networkRequest": "0",
        })
        meta["renderOutputKind"] = rendered.get("outputKind")

        previewKind = base._toStr(options.get("previewKind"))
        if previewKind and outputKind == "html":
            content = layoutEngine.renderPreview(previewKind, content, topicData, meta)
            meta["previewKind"] = previewKind

        return base._ok({
            "outputKind": outputKind,
            "content": content,
            "meta": meta,
            "platformCode": self.platformCode,
            "deliverMode": self.deliverMode,
        })

    #----- 契约: validate -----

    def validate(self, topicData, assetList, platformRecord = None):
        """通用形态校验(数据驱动; generic 的 coverSpec/imageSpec 为空, 故只剩标题/摘要/数量约束)"""
        record = platformRecord if isinstance(platformRecord, dict) else self.platformRecord
        return base.checkPlatformSpec(record, topicData, assetList)

    #----- 契约: package -----

    def package(self, renderResult, topicData, assetList, options = None):
        """素材包清单(本轮只出结构化清单, 不落盘; ZIP 打包与 manifest 落盘归 SP4)"""
        renderResult = renderResult if isinstance(renderResult, dict) else {}
        content = base._toStr(renderResult.get("content"))
        itemList = [{"seqNo": idx + 1,
                     "fileID": base._toStr((item or {}).get("fileID")),
                     "fileUrl": base._toStr((item or {}).get("fileUrl")),
                     "caption": base._toStr((item or {}).get("caption"))}
                    for idx, item in enumerate(assetList or []) if isinstance(item, dict)]

        plan = {
            "platformCode": self.platformCode,
            "deliverMode": self.deliverMode,
            "packageKind": "generic_asset_pack",
            "title": base._toStr((topicData or {}).get("title")),
            "contentLength": len(content),
            "imageCount": len(itemList),
            "itemList": itemList,
            "manifestRequired": True,
            "note": "本轮只输出素材包清单, 不落盘(artifactpack 与 ZIP 投递归 SP4)",
        }
        return base._ok(plan)

    #----- 契约: checkHealth(只读, 零网络) -----

    def checkHealth(self, sessionIDSet = None):
        """通用形态无需凭据; 只读配置态, **不发任何网络请求**"""
        return base._ok({
            "platformCode": self.platformCode,
            "deliverMode": self.deliverMode,
            "credentialConfigured": "1",
            "credentialMissingList": [],
            "accountCount": 0,
            "healthStatusList": [],
            "networkRequest": "0",
            "checkedAt": misc.getTime(),
            "note": "通用形态(站内预览/导出)无需平台凭据",
        })


if __name__ == "__main__":
    pass
    #本地自测(不连库/不联网): 只验证纯函数
    print("markdown sample:", buildMarkdown({"title": "标题", "description": "第一段\n\n第二段",
                                             "tagList": "a,b"}, [{"fileUrl": "https://x/a.jpg", "caption": "图注"}]))
    _adapter = GenericAdapter({"platformCode": "generic", "titleMaxLen": 128})
    print("deliver:", _adapter.deliver({})["errCode"])
