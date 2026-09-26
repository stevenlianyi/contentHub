#! /usr/bin/env python3
#encoding: utf-8

#Filename: layoutEngine.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 版式调度引擎(唯一渲染入口, SP2c · C4 版式引擎)。

#职责:
#  1) 读 ch_layout(只经 common/mysqlCommon.py, 红线 R1)取版式定义;
#  2) 注入 specJson(版式参数, 见 tools/initSeed.py 的 4 套权威取值) -> Jinja2 服务端渲染;
#  3) 按 layoutType 分派 stack / carousel / longimage / swipe 四套模板;
#  4) 返回 {"outputKind", "content", "meta"}; 失败抛 LayoutEngineError(contenthub E 段错误码)。
#
#★ 分层契约(强制单向): 接入层 -> 业务层(processor/) -> 引擎层(engine/) -> 公共层(common/)
#  本文件 **不得 import processor/ 或 subfunc/**。主题(主题服务出参)与附图(素材服务出参)由业务层
#  (processor/renderService.py)取好后作为入参传入, 本层只做「渲染」, 不回头调业务层。
#
#★ 4 类版式的本质区别(主计划 2.6, 禁止合并或互替):
#  - stack      纵向顺序阅读(HTML; 公众号长文)                 —— 本项目渲染
#  - carousel   页面内自实现交互(HTML+JS; 含静态图集兜底)        —— 本项目渲染交互
#  - longimage  多图纵向拼接为 1 张长图, 输出切片参数             —— 本轮只出蓝图+切片计划, 截图属 SP3
#  - swipe      平台原生左右滑动(N 张等比例卡片; 仅小红书)        —— 只切分+排序+统一比例, **不自实现交互**
#  carousel_v1 不可用于小红书(不收 HTML); swipe_v1 不可用于公众号(无原生多图滑动)。
#
#★ 入参出参约定(与 processor/renderService.py 对齐):
#  topicData  = topicService.queryTopic 出参里的单条记录(含 title/summary/description/author/.../coverUrl)
#  assetList  = assetService.queryTopicAsset 出参里的记录列表(含 caption/usageType/sortOrder/fileID/fileUrl,
#               若业务层已合并 ch_asset 元信息则含 width/height)
#  出参 meta  结构见各 _renderXxx 的组装(供前端/SP3 截图消费)

_VERSION="20260919"


import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../code/src
if parentdir not in sys.path:
    sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import traceback

#global defintion/common var etc.
from common import globalDefinition as comGD

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#数据层唯一入口(红线 R1): 本层只读 ch_layout
from common import mysqlCommon as comMysql

#setting files
from config import basicSettings as settings


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    try:
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None

_DEBUG = settings._DEBUG


#===== 路径与版式常量 begin =====

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))          # .../code/src/engine
TEMPLATES_DIR = os.path.join(ENGINE_DIR, "templates")            # .../code/src/engine/templates

#layoutType -> 模板目录(一一对应; S22 静态锁定)
LAYOUT_TYPE_TEMPLATE_MAP = {
    "stack":     "stack_v1",
    "carousel":  "carousel_v1",
    "longimage": "longimage_v1",
    "swipe":     "swipe_v1",
}
SUPPORTED_LAYOUT_TYPE_LIST = list(LAYOUT_TYPE_TEMPLATE_MAP.keys())

#预览页模板(kind -> 模板相对路径); kind 由请求可选参数 previewKind 指定
PREVIEW_TEMPLATE_MAP = {
    "wechat":      "preview/wechat_mp.html",
    "wechat_mp":   "preview/wechat_mp.html",
    "xiaohongshu": "preview/xiaohongshu.html",
    "xhs":         "preview/xiaohongshu.html",
}
PREVIEW_PLATFORM_NAME = {
    "wechat":      "微信公众号",
    "wechat_mp":   "微信公众号",
    "xiaohongshu": "小红书",
    "xhs":         "小红书",
}

#渲染期默认卡片规格(与 initSeed 的 1080x1440 一致; 可由 spec.size 覆盖)
DEFAULT_CARD_SIZE = (1080, 1440)
DEFAULT_RATIO = (3, 4)

#错误码落点(common/errMsgCommon.py::_CH_ERROR_WORD 的 contenthub E 段, 渲染与产物)
ERR_TEMPLATE_NOT_FOUND = "E0"    #版式/模板缺失
ERR_RENDER_FAILED = "E1"         #渲染失败(含 spec 校验不通过)
ERR_ARTIFACT_FAILED = "E3"       #产物生成失败(长图超上限等)

#===== 路径与版式常量 end =====


#===== 引擎异常 begin =====

class LayoutEngineError(Exception):
    """版式引擎异常: 携带 contenthub E 段错误码, 由业务层(renderService)映射为 HTTP 报文"""
    def __init__(self, errCode, message, field = ""):
        super().__init__(message)
        self.errCode = errCode
        self.field = field
        self.message = message

#===== 引擎异常 end =====


#===== 通用小工具 begin =====

def _toStr(value):
    """None/数字/任意 -> 去空白字符串"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _toInt(value, default = 0):
    try:
        return int(float(_toStr(value)))
    except Exception:
        return default


def _toBool(value):
    """宽松布尔: True/"true"/"1"/1 视为真"""
    if isinstance(value, bool):
        return value
    return _toStr(value).lower() in ("1", "true", "yes", "on")


def _fieldLabel(fieldName):
    """字段名 + 所在表(ch_layout), 用于错误提示「标明字段名与位置」"""
    return f"{fieldName}(ch_layout)"


def parseSize(size, default = DEFAULT_CARD_SIZE):
    """把 '1080x1440' / (1080, 1440) 解析为 (width, height); 非法回落 default"""
    if isinstance(size, (tuple, list)) and len(size) == 2:
        try:
            return int(size[0]), int(size[1])
        except Exception:
            return default
    text = _toStr(size).lower().replace("*", "x")
    if "x" in text:
        parts = text.split("x")
        if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
            return int(parts[0]), int(parts[1])
    return default


def parseRatio(ratio, default = DEFAULT_RATIO):
    """把 '3:4' 解析为 (w, h); 非法回落 default"""
    text = _toStr(ratio).replace("x", ":").replace("/", ":")
    if ":" in text:
        parts = text.split(":")
        if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
            w, h = int(parts[0]), int(parts[1])
            if w > 0 and h > 0:
                return w, h
    return default

#===== 通用小工具 end =====


#===== 版式定义读取 begin =====

def loadLayoutRecord(layoutCode):
    """按 layoutCode 读 ch_layout(只经 mysqlCommon); 未命中/停用/不支持 -> LayoutEngineError"""
    layoutCode = _toStr(layoutCode)
    if not layoutCode:
        raise LayoutEngineError(ERR_TEMPLATE_NOT_FOUND, "layoutCode 为空", _fieldLabel("layoutCode"))

    tableName = comMysql.tablename_convertor_ch_layout()
    try:
        dataList = comMysql.query_ch_layout(tableName, layoutCode = layoutCode, mode = "full")
    except Exception as e:
        raise LayoutEngineError(ERR_RENDER_FAILED, f"版式读取失败: {layoutCode}, errMsg:{str(e)}",
                                _fieldLabel("layoutCode"))

    if not dataList:
        raise LayoutEngineError(ERR_TEMPLATE_NOT_FOUND, f"版式不存在: {layoutCode}", _fieldLabel("layoutCode"))

    layoutRecord = dataList[0]
    if _toStr(layoutRecord.get("enabled")) == "0":
        raise LayoutEngineError(ERR_RENDER_FAILED, f"版式已停用: {layoutCode}", _fieldLabel("enabled"))

    layoutType = _toStr(layoutRecord.get("layoutType")).lower()
    if layoutType not in LAYOUT_TYPE_TEMPLATE_MAP:
        raise LayoutEngineError(ERR_TEMPLATE_NOT_FOUND,
                                f"不支持的 layoutType: {layoutType}, 允许值={SUPPORTED_LAYOUT_TYPE_LIST}",
                                _fieldLabel("layoutType"))

    return layoutRecord


def resolveSpec(layoutRecord, overrideSpec = None):
    """解析 specJson 并叠加渲染覆盖参数(overrideSpec 支持 dict 或 JSON 字符串)。
       合并结果为普通 dict, 供模板以 spec.xxx 消费(键名一律沿用 initSeed 的既有取值, 不另造一套)。"""
    spec = {}
    raw = _toStr((layoutRecord or {}).get("specJson"))
    if raw:
        try:
            loaded = misc.jsonLoads(raw)
            if isinstance(loaded, dict):
                spec = dict(loaded)
        except Exception as e:
            if _LOG:
                _LOG.warning(f"W: PID:{_processorPID}, specJson 解析失败, errMsg:{str(e)}")

    if isinstance(overrideSpec, dict):
        for key, value in overrideSpec.items():
            spec[key] = value
    elif isinstance(overrideSpec, str) and overrideSpec.strip():
        try:
            loaded = misc.jsonLoads(overrideSpec)
            if isinstance(loaded, dict):
                spec.update(loaded)
        except Exception as e:
            if _LOG:
                _LOG.warning(f"W: PID:{_processorPID}, overrideSpec 解析失败, errMsg:{str(e)}")

    return spec


def _resolveTemplateName(layoutRecord, layoutType):
    """校验 layoutType 与模板目录一一对应并返回模板相对路径(缺失/错配 -> E0)"""
    expectedDir = LAYOUT_TYPE_TEMPLATE_MAP.get(layoutType)
    if not expectedDir:
        raise LayoutEngineError(ERR_TEMPLATE_NOT_FOUND,
                                f"不支持的 layoutType: {layoutType}", _fieldLabel("layoutType"))

    expectedName = f"{expectedDir}/index.html"

    templatePath = _toStr((layoutRecord or {}).get("templatePath")).replace("\\", "/")
    if templatePath and not templatePath.endswith(expectedName):
        raise LayoutEngineError(ERR_TEMPLATE_NOT_FOUND,
                                f"templatePath 与 layoutType 不匹配: {templatePath} 应为 .../{expectedName}",
                                _fieldLabel("templatePath"))

    absPath = os.path.join(TEMPLATES_DIR, expectedName)
    if not os.path.isfile(absPath):
        raise LayoutEngineError(ERR_TEMPLATE_NOT_FOUND, f"版式模板缺失: {expectedName}",
                                _fieldLabel("templatePath"))

    return expectedName

#===== 版式定义读取 end =====


#===== 数据归一(主题/附图) begin =====

def _normalizeTopic(topicData):
    """把主题记录(mysql 行/topicService 出参)归一为模板上下文里的 topic 视图"""
    topicData = topicData if isinstance(topicData, dict) else {}

    tagValue = topicData.get("tagList", "")
    if isinstance(tagValue, (list, tuple)):
        tagList = [_toStr(t) for t in tagValue if _toStr(t)]
    else:
        tagList = [_toStr(t) for t in _toStr(tagValue).replace("，", ",").split(",") if _toStr(t)]

    description = _toStr(topicData.get("description"))
    paragraphs = [line.strip() for line in description.replace("\r\n", "\n").replace("\r", "\n").split("\n") if line.strip()]

    return {
        "topicID": _toStr(topicData.get("recID")),
        "topicCode": _toStr(topicData.get("topicCode")),
        "title": _toStr(topicData.get("title")),
        "summary": _toStr(topicData.get("summary")),
        "description": description,
        "paragraphs": paragraphs,
        "author": _toStr(topicData.get("author")),
        "location": _toStr(topicData.get("location")),
        "source": _toStr(topicData.get("source")),
        "period": _toStr(topicData.get("period")),
        "categoryCode": _toStr(topicData.get("categoryCode")),
        "status": _toStr(topicData.get("status")),
        "wordCount": _toStr(topicData.get("wordCount")),
        "aiFlag": _toStr(topicData.get("aiFlag")),
        "tagList": tagList,
        "coverFileID": _toStr(topicData.get("coverFileID")),
        "coverUrl": _toStr(topicData.get("coverUrl")),
        "coverThumbID": _toStr(topicData.get("coverThumbID")),
        "coverThumbUrl": _toStr(topicData.get("coverThumbUrl")),
        "descriptionFileID": _toStr(topicData.get("descriptionFileID")),
        "descriptionUrl": _toStr(topicData.get("descriptionUrl")),
    }


def _normalizeAssets(assetList, layoutType = ""):
    """把附图绑定列表(assetService 出参)归一为模板上下文里的 assets 视图。
       - 按 sortOrder 升序(越小越靠前); 缺省 100;
       - 重新编 seqNo(1..N, 即阅读/滑动顺序);
       - 保留图注(caption)/用途(usageType)/URL, 以及可选 width/height(ch_asset 元信息)。
       说明: swipe 的「封面置顶」在 _renderSwipe 内单独处理, 本函数保持通用排序语义。"""
    if not isinstance(assetList, (list, tuple)):
        return []

    normalized = []
    for item in assetList:
        if not isinstance(item, dict):
            continue
        normalized.append({
            "fileID": _toStr(item.get("fileID")),
            "fileUrl": _toStr(item.get("fileUrl")),
            "thumbnailID": _toStr(item.get("thumbnailID")),
            "thumbnailUrl": _toStr(item.get("thumbnailUrl")),
            "caption": _toStr(item.get("caption")),
            "usageType": _toStr(item.get("usageType")) or "body",
            "sortOrder": _toInt(item.get("sortOrder"), 100),
            "width": _toInt(item.get("width"), 0),
            "height": _toInt(item.get("height"), 0),
            "fileExt": _toStr(item.get("fileExt")).lower(),
            "origSizeBytes": _toInt(item.get("origSizeBytes"), 0),
        })

    normalized.sort(key = lambda data: data["sortOrder"])
    for idx, data in enumerate(normalized):
        data["seqNo"] = idx + 1

    return normalized

#===== 数据归一 end =====


#===== Jinja2 环境 begin =====

_TEMPLATE_ENV = None


def getTemplateEnv():
    """获取(并缓存)Jinja2 环境; 模板目录为 engine/templates。Jinja2 采用延迟导入。"""
    global _TEMPLATE_ENV
    if _TEMPLATE_ENV is not None:
        return _TEMPLATE_ENV

    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
    except Exception as e:
        raise LayoutEngineError(ERR_RENDER_FAILED, f"Jinja2 不可用: {str(e)}")

    if not os.path.isdir(TEMPLATES_DIR):
        raise LayoutEngineError(ERR_TEMPLATE_NOT_FOUND, f"模板目录缺失: {TEMPLATES_DIR}")

    _TEMPLATE_ENV = Environment(
        loader = FileSystemLoader(TEMPLATES_DIR),
        autoescape = select_autoescape(["html", "xml"]),
        trim_blocks = True,
        lstrip_blocks = True,
        keep_trailing_newline = False,
    )
    return _TEMPLATE_ENV


def _renderTemplate(templateName, context):
    """渲染单个模板; 模板缺失 -> E0, 其它异常 -> E1"""
    try:
        env = getTemplateEnv()
        template = env.get_template(templateName)
        content = template.render(**context)
    except LayoutEngineError:
        raise
    except Exception as e:
        try:
            from jinja2 import TemplateNotFound
            if isinstance(e, TemplateNotFound):
                raise LayoutEngineError(ERR_TEMPLATE_NOT_FOUND, f"版式模板缺失: {templateName}")
        except LayoutEngineError:
            raise
        except Exception:
            pass
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, 模板渲染失败 {templateName}, errMsg:{e}, {traceback.format_exc()}")
        raise LayoutEngineError(ERR_RENDER_FAILED, f"渲染失败({templateName}): {str(e)}")

    if not content or not content.strip():
        raise LayoutEngineError(ERR_RENDER_FAILED, f"渲染结果为空: {templateName}")

    return content

#===== Jinja2 环境 end =====


#===== 分派: stack 上下展示 begin =====

def _renderStack(layoutRecord, topic, assets, spec, meta, embedMode = False):
    """纵向顺序阅读: 标题 -> 简介 -> 正文 -> 附图(按 sortOrder)。
       HTML 结构以 data-* 与内联样式表达, 不依赖 class 语义(为 SP3 微信内联化留余地)。"""
    templateName = _resolveTemplateName(layoutRecord, "stack")

    meta.update({
        "template": "stack_v1",
        "blocks": ["title", "summary", "body", "assets"],
        "imageCount": len(assets),
        "maxWidth": _toStr(spec.get("maxWidth")) or "750px",
        "fontSize": _toStr(spec.get("fontSize")) or "16px",
        "lineHeight": _toStr(spec.get("lineHeight")) or "1.75",
        "paragraphGap": _toStr(spec.get("paragraphGap")) or "16px",
    })

    context = {
        "pageTitle": topic.get("title") or "contentHub",
        "embedMode": embedMode,
        "layout": {"layoutCode": meta.get("layoutCode"), "layoutType": "stack",
                   "platform": meta.get("platform"), "outputKind": meta.get("outputKind")},
        "topic": topic,
        "assets": assets,
        "spec": spec,
        "meta": meta,
    }
    return _renderTemplate(templateName, context)

#===== 分派: stack end =====


#===== 分派: carousel 左右轮播 begin =====

def _renderCarousel(layoutRecord, topic, assets, spec, meta, embedMode = False):
    """页面内自实现交互(HTML+JS) + **静态图集兜底必须产出**(公众号 SVG 不稳)。
       spec 键: size / ratio / maxCount / allowSvg / needStaticFallback。"""
    templateName = _resolveTemplateName(layoutRecord, "carousel")

    cardWidth, cardHeight = parseSize(spec.get("size"), DEFAULT_CARD_SIZE)
    maxCount = _toInt(spec.get("maxCount"), 9)
    needStaticFallback = _toBool(spec.get("needStaticFallback"))
    allowSvg = _toBool(spec.get("allowSvg"))

    slideList = assets[:maxCount] if maxCount > 0 else list(assets)
    if len(assets) > len(slideList) and _LOG:
        _LOG.warning(f"W: PID:{_processorPID}, carousel 附图数 {len(assets)} 超 maxCount {maxCount}, 仅渲染前 {maxCount} 张")

    fallbackList = list(slideList)
    #兜底是硬交付: 即便 spec 未置 needStaticFallback, 也始终产出静态图集节点(公众号 SVG 不稳)
    meta.update({
        "template": "carousel_v1",
        "interactive": True,
        "staticFallback": True,
        "needStaticFallback": needStaticFallback or True,
        "allowSvg": allowSvg,
        "slideCount": len(slideList),
        "fallbackCount": len(fallbackList),
        "size": f"{cardWidth}x{cardHeight}",
        "ratio": _toStr(spec.get("ratio")) or "3:4",
        "maxCount": maxCount,
    })

    context = {
        "pageTitle": topic.get("title") or "contentHub",
        "embedMode": embedMode,
        "layout": {"layoutCode": meta.get("layoutCode"), "layoutType": "carousel",
                   "platform": meta.get("platform"), "outputKind": meta.get("outputKind")},
        "topic": topic,
        "assets": assets,
        "spec": spec,
        "meta": meta,
        "slideList": slideList,
        "fallbackList": fallbackList,
        "cardWidth": cardWidth,
        "cardHeight": cardHeight,
    }
    return _renderTemplate(templateName, context)

#===== 分派: carousel end =====


#===== 分派: longimage 长图拼接 begin =====

def planLongImageSlices(totalHeight, sliceHeight, maxTotalHeight = 0):
    """长图切片计划: 返回 [{"seqNo", "offsetY", "height", "isLast"}]。
       越界(超 maxTotalHeight)抛 E3 —— 小红书禁止直接上传超长原图。"""
    totalHeight = _toInt(totalHeight, 0)
    sliceHeight = _toInt(sliceHeight, 0) or 1440
    if maxTotalHeight and totalHeight > maxTotalHeight:
        raise LayoutEngineError(ERR_ARTIFACT_FAILED,
                                f"长图总高 {totalHeight} 超上限 {maxTotalHeight}")

    slices = []
    seqNo = 1
    offsetY = 0
    while offsetY < totalHeight:
        height = min(sliceHeight, totalHeight - offsetY)
        slices.append({"seqNo": seqNo, "offsetY": offsetY, "height": height,
                       "isLast": "1" if offsetY + height >= totalHeight else "0"})
        offsetY += height
        seqNo += 1
    return slices


def _renderLongimage(layoutRecord, topic, assets, spec, meta, embedMode = False):
    """多图纵向拼接方案 + 输出切片参数(本轮不做实际截图, Playwright 属 SP3)。
       spec 键: size / ratio / sliceHeight / maxTotalHeight。"""
    templateName = _resolveTemplateName(layoutRecord, "longimage")

    cardWidth, cardHeight = parseSize(spec.get("size"), DEFAULT_CARD_SIZE)
    sliceHeight = _toInt(spec.get("sliceHeight"), cardHeight or 1440)
    maxTotalHeight = _toInt(spec.get("maxTotalHeight"), 21600)

    #每张附图贡献一张等比例卡片(1080x1440); 标题/正文区间高度由 SP3 截图实测补齐
    cardTotalHeight = cardHeight * len(assets)
    if cardTotalHeight <= 0:
        cardTotalHeight = sliceHeight

    if cardTotalHeight > maxTotalHeight:
        raise LayoutEngineError(ERR_ARTIFACT_FAILED,
                                f"长图总高 {cardTotalHeight} 超上限 {maxTotalHeight}(须先切分)",
                                _fieldLabel("specJson.maxTotalHeight"))

    slices = planLongImageSlices(cardTotalHeight, sliceHeight, maxTotalHeight)

    meta.update({
        "template": "longimage_v1",
        "size": f"{cardWidth}x{cardHeight}",
        "ratio": _toStr(spec.get("ratio")) or "3:4",
        "sliceHeight": sliceHeight,
        "maxTotalHeight": maxTotalHeight,
        "estimatedTotalHeight": cardTotalHeight,
        "sliceCount": len(slices),
        "slices": slices,
        "imageCount": len(assets),
        "note": "本轮只输出拼接蓝图与切片参数; 实际整页截图(Playwright)属 SP3",
    })

    context = {
        "pageTitle": topic.get("title") or "contentHub",
        "embedMode": embedMode,
        "layout": {"layoutCode": meta.get("layoutCode"), "layoutType": "longimage",
                   "platform": meta.get("platform"), "outputKind": meta.get("outputKind")},
        "topic": topic,
        "assets": assets,
        "spec": spec,
        "meta": meta,
        "slices": slices,
        "cardWidth": cardWidth,
        "cardHeight": cardHeight,
    }
    return _renderTemplate(templateName, context)

#===== 分派: longimage end =====


#===== 分派: swipe 左右滑动多图集 begin =====

def _renderSwipe(layoutRecord, topic, assets, spec, meta, embedMode = False):
    """N 张等比例卡片: seqNo 递增、第 1 张为封面标记、按 sortOrder 编排、比例统一校验。
       **平台原生交互** —— 项目侧只切分+排序+统一比例, 不得自实现滑动交互。
       spec 键: size / ratio / maxCount / minCount / uniformRatio / maxSizePerImageMB /
                format / sortable / coverFlag。"""
    templateName = _resolveTemplateName(layoutRecord, "swipe")

    cardWidth, cardHeight = parseSize(spec.get("size"), DEFAULT_CARD_SIZE)
    ratioW, ratioH = parseRatio(spec.get("ratio"), DEFAULT_RATIO)
    maxCount = _toInt(spec.get("maxCount"), 18)
    minCount = _toInt(spec.get("minCount"), 1)
    uniformRatio = _toBool(spec.get("uniformRatio"))
    coverFlag = _toBool(spec.get("coverFlag"))
    sortable = _toBool(spec.get("sortable"))
    maxSizePerImageMB = _toInt(spec.get("maxSizePerImageMB"), 0)
    allowedFormatList = spec.get("format")
    if not isinstance(allowedFormatList, (list, tuple)):
        allowedFormatList = []

    if len(assets) > maxCount:
        raise LayoutEngineError(ERR_RENDER_FAILED,
                                f"附图数 {len(assets)} 超 swipe 上限 {maxCount}",
                                _fieldLabel("specJson.maxCount"))
    if len(assets) < minCount:
        raise LayoutEngineError(ERR_RENDER_FAILED,
                                f"附图数 {len(assets)} 低于 swipe 下限 {minCount}",
                                _fieldLabel("specJson.minCount"))

    #按 sortOrder 编排(assets 已升序); 有 cover 时把它稳定置顶(第 1 张为封面)
    cardList = list(assets)
    coverIndex = -1
    for idx, data in enumerate(cardList):
        if data.get("usageType") == "cover":
            coverIndex = idx
            break
    if coverIndex > 0:
        cardList.insert(0, cardList.pop(coverIndex))

    #比例统一校验(对已知源尺寸的卡片; 未知尺寸无从校验, 记录 ratioOk=unknown);
    #★ 输出卡片尺寸一律为统一后的目标 size(1080x1440) —— 源图由 imageProc.fitToSize 在渲染期派生归一,
    #  故 meta.cards 的 width/height 恒等, 源尺寸另记 sourceWidth/sourceHeight 供溯源。
    tolerance = 0.02
    targetRatio = ratioW / ratioH
    cards = []
    for idx, data in enumerate(cardList):
        #单张格式/大小约束(spec.format / spec.maxSizePerImageMB; 元信息缺失则跳过, 不阻断)
        fileExt = _toStr(data.get("fileExt")).lower()
        formatList = [str(fmt).lower() for fmt in allowedFormatList]
        if formatList and fileExt and fileExt not in formatList:
            raise LayoutEngineError(ERR_RENDER_FAILED,
                                    f"第 {idx + 1} 张格式 {fileExt} 不在允许范围 {formatList}",
                                    _fieldLabel("specJson.format"))
        sizeBytes = _toInt(data.get("origSizeBytes"), 0)
        if maxSizePerImageMB > 0 and sizeBytes > maxSizePerImageMB * 1024 * 1024:
            raise LayoutEngineError(ERR_RENDER_FAILED,
                                    f"第 {idx + 1} 张大小 {sizeBytes} 字节 超单张上限 {maxSizePerImageMB}MB",
                                    _fieldLabel("specJson.maxSizePerImageMB"))

        sourceWidth = _toInt(data.get("width"), 0)
        sourceHeight = _toInt(data.get("height"), 0)
        ratioOk = "1"
        if sourceWidth > 0 and sourceHeight > 0:
            if abs((sourceWidth / sourceHeight) - targetRatio) > tolerance:
                ratioOk = "0"
                if uniformRatio:
                    raise LayoutEngineError(ERR_RENDER_FAILED,
                                            f"第 {idx + 1} 张比例 {sourceWidth}x{sourceHeight} 与整篇 {ratioW}:{ratioH} 不一致",
                                            _fieldLabel("specJson.uniformRatio"))
        else:
            ratioOk = "unknown"

        isCover = "1" if (coverFlag and idx == 0) else "0"
        cards.append({
            "seqNo": idx + 1,
            "fileID": data.get("fileID", ""),
            "fileUrl": data.get("fileUrl", ""),
            "thumbnailUrl": data.get("thumbnailUrl", ""),
            "caption": data.get("caption", ""),
            "usageType": data.get("usageType", "body"),
            "sortOrder": data.get("sortOrder", 100),
            "isCover": isCover,
            "width": cardWidth,
            "height": cardHeight,
            "sourceWidth": sourceWidth,
            "sourceHeight": sourceHeight,
            "ratio": f"{ratioW}:{ratioH}",
            "ratioOk": ratioOk,
        })

    meta.update({
        "template": "swipe_v1",
        "mechanism": "platform_native",       #平台原生交互, 本项目不自实现
        "size": f"{cardWidth}x{cardHeight}",
        "ratio": f"{ratioW}:{ratioH}",
        "maxCount": maxCount,
        "minCount": minCount,
        "uniformRatio": uniformRatio,
        "coverFlag": coverFlag,
        "sortable": sortable,
        "maxSizePerImageMB": maxSizePerImageMB,
        "format": list(allowedFormatList),
        "cardCount": len(cards),
        "coverFileID": cards[0]["fileID"] if cards else "",
        "cards": cards,
    })

    context = {
        "pageTitle": topic.get("title") or "contentHub",
        "embedMode": embedMode,
        "layout": {"layoutCode": meta.get("layoutCode"), "layoutType": "swipe",
                   "platform": meta.get("platform"), "outputKind": meta.get("outputKind")},
        "topic": topic,
        "assets": assets,
        "spec": spec,
        "meta": meta,
        "cards": cards,
        "cardWidth": cardWidth,
        "cardHeight": cardHeight,
    }
    return _renderTemplate(templateName, context)

#===== 分派: swipe end =====


_DISPATCH_MAP = {
    "stack":     _renderStack,
    "carousel":  _renderCarousel,
    "longimage": _renderLongimage,
    "swipe":     _renderSwipe,
}


#===== 对外渲染入口 begin =====

def renderLayout(layoutRecord, topicData, assetList, overrideSpec = None, embedMode = False):
    """★ 唯一渲染入口: 版式定义 + 主题 + 附图 -> {"outputKind", "content", "meta"}。
       入参:
         layoutRecord  ch_layout 记录(dict; 由 loadLayoutRecord 取得, 或测试直接构造)
         topicData     主题记录(topicService 出参里的单条)
         assetList     附图绑定列表(assetService 出参; 含 caption/usageType/sortOrder/fileID/fileUrl)
         overrideSpec  可选渲染覆盖参数(dict 或 JSON 字符串), 叠加在 specJson 之上
         embedMode     True=只输出片段(供站内预览嵌入手机框); False=输出完整 HTML 文档
       失败抛 LayoutEngineError(contenthub E 段)。"""
    if not isinstance(layoutRecord, dict):
        raise LayoutEngineError(ERR_TEMPLATE_NOT_FOUND, "版式定义为空", _fieldLabel("layoutRecord"))

    layoutType = _toStr(layoutRecord.get("layoutType")).lower()
    renderFunc = _DISPATCH_MAP.get(layoutType)
    if renderFunc is None:
        raise LayoutEngineError(ERR_TEMPLATE_NOT_FOUND,
                                f"不支持的 layoutType: {layoutType}, 允许值={SUPPORTED_LAYOUT_TYPE_LIST}",
                                _fieldLabel("layoutType"))

    spec = resolveSpec(layoutRecord, overrideSpec)
    topic = _normalizeTopic(topicData)
    assets = _normalizeAssets(assetList, layoutType)

    meta = {
        "layoutCode": _toStr(layoutRecord.get("layoutCode")),
        "layoutName": _toStr(layoutRecord.get("layoutName")),
        "layoutType": layoutType,
        "platform": _toStr(layoutRecord.get("platform")),
        "engine": _toStr(layoutRecord.get("engine")) or "jinja2",
        "outputKind": _toStr(layoutRecord.get("outputKind")) or "html",
        "templateVer": _toStr(layoutRecord.get("templateVer")) or "v1",
        "templatePath": _toStr(layoutRecord.get("templatePath")),
        "spec": spec,
        "assetCount": len(assets),
        "renderAt": misc.getTime(),
    }
    meta["topicID"] = topic.get("topicID")

    content = renderFunc(layoutRecord, topic, assets, spec, meta, embedMode)

    return {"outputKind": meta.get("outputKind") or "html", "content": content, "meta": meta}


def renderPreview(previewKind, renderedContent, topic, meta):
    """站内预览(P1-8): 用微信/小红书手机框模拟页包裹已渲染片段。
       出参 fileID 一律已由业务层经 fillFileUrls 转换(本层不再触库/触文件)。"""
    previewKind = _toStr(previewKind).lower()
    templateName = PREVIEW_TEMPLATE_MAP.get(previewKind)
    if not templateName:
        raise LayoutEngineError(ERR_TEMPLATE_NOT_FOUND,
                                f"不支持的预览形态: {previewKind}, 允许值={sorted(set(PREVIEW_TEMPLATE_MAP.keys()))}",
                                "previewKind")

    absPath = os.path.join(TEMPLATES_DIR, templateName)
    if not os.path.isfile(absPath):
        raise LayoutEngineError(ERR_TEMPLATE_NOT_FOUND, f"预览模板缺失: {templateName}")

    context = {
        "pageTitle": (topic or {}).get("title") or "contentHub 预览",
        "embedMode": False,
        "platformName": PREVIEW_PLATFORM_NAME.get(previewKind, previewKind),
        "previewKind": previewKind,
        "layoutFragment": renderedContent or "",
        "topic": topic or {},
        "meta": meta or {},
        "spec": (meta or {}).get("spec", {}),
    }
    return _renderTemplate(templateName, context)


def renderTopic(topicID, layoutCode, topicData, assetList, overrideSpec = None, options = None):
    """高层次入口: 读 ch_layout + 渲染; options 支持 embedMode / previewKind。
       说明: 主题与附图数据由业务层取好后传入(遵守单向依赖, 本层不回头调 processor)。
       previewKind 命中时, 用 preview/ 手机框模板包裹渲染片段。"""
    options = options if isinstance(options, dict) else {}

    layoutRecord = loadLayoutRecord(layoutCode)

    previewKind = _toStr(options.get("previewKind")).lower()
    embedMode = _toBool(options.get("embedMode"))

    if previewKind:
        inner = renderLayout(layoutRecord, topicData, assetList, overrideSpec, embedMode = True)
        previewHtml = renderPreview(previewKind, inner.get("content", ""),
                                    _normalizeTopic(topicData), inner.get("meta"))
        inner["content"] = previewHtml
        inner["meta"]["previewKind"] = previewKind
        inner["meta"]["renderOutputKind"] = inner.get("outputKind")
        return inner

    return renderLayout(layoutRecord, topicData, assetList, overrideSpec, embedMode = embedMode)

#===== 对外渲染入口 end =====


if __name__ == "__main__":
    pass
    #本地自测(不连库): 只验证纯函数
    print("LAYOUT_TYPE_TEMPLATE_MAP:", LAYOUT_TYPE_TEMPLATE_MAP)
    print("parseSize('1080x1440'):", parseSize("1080x1440"))
    print("parseRatio('3:4'):", parseRatio("3:4"))
    print("planLongImageSlices(2880,1440,21600):", planLongImageSlices(2880, 1440, 21600))
    print("templatesDir exists:", os.path.isdir(TEMPLATES_DIR))
