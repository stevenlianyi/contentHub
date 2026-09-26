#! /usr/bin/env python3
#encoding: utf-8:

#Filename: xiaohongshu.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 小红书平台适配器(SP3b · C5 小红书产物渲染, 主计划 2.4 / 2.6 / 5.4 P2-3 / 7.8)。

#职责(只做「形态转换」, 业务编排留在 processor/renderService.py):
#  1) render      按 layoutType 分派 ——
#        swipe     每张卡片一屏 -> N 张 1080x1440 PNG(seqNo 递增, 第 1 张封面标记),
#                  按附图 sortOrder 编排; **只切分 + 排序 + 统一比例, 不自实现滑动交互**(platform_native);
#        longimage 整页长图 -> 按 sliceHeight(默认 1440) 切分为多张(**禁止直接产出超长单图**);
#        stack     小红书形态为长图 -> 走 longimage 管线(覆盖 maxWidth 到卡片宽度后整页截图切片);
#        carousel  ★ 小红书不接收 HTML, 且 carousel 交互属公众号自实现 -> **显式返回不可用错误(C7)**,
#                  绝不静默转换为长图/图集;
#  2) validate    平台规格校验(数据驱动 ch_platform): 标题必填/超长、摘要超长、图片数量上限;
#                  swpse 另有 2.6.3 强制校验(比例统一/张数/单张大小/格式);
#  3) package     素材包清单(有序文件列表 + manifest 草稿: 主题编码/生成时间/版式/平台/校验值);
#                 ★ ZIP 打包与导出归 SP4, 本轮只出清单;
#  4) deliver     ★ 本轮**一律返回「未实现」显式错误**(投递归 SP4), 继承自基类, 不覆写;
#  5) checkHealth 只读 ch_account 与配置态, **不发任何网络请求**。
#
#★ 平台红线(不可逾越): **不引入任何小红书自动发布/投递代码路径** —— 本文件不含任何平台 API 调用、
#  不含平台凭据与投递接口; deliver 一律显式未实现。小红书素材包只导出, 由用户手动在官方平台发布。
#
#★ swipe 强制校验(主计划 2.6.3): 比例统一(uniformRatio, 非目标比例一律**显式报错 D1**,
#  **不静默裁切/缩放掩盖**)、张数 ≤ ch_platform.imageMaxCount(18)、单张 ≤ 20MB、格式 JPG/PNG。
#
#★ 零对外网络(SP3b): 只做本地渲染(HTML 内本地图片内联为 data URI) + 本地/对象存储产物上传;
#  不调小红书任何接口。
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

import tempfile
import traceback

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#数据层唯一入口(红线 R1): 本文件只读 ch_account(健康巡检)
from common import mysqlCommon as comMysql

#平台适配契约
from processor.platformAdapter import base

#引擎层(单向依赖: processor -> engine)
from engine import layoutEngine

from engine import imageProc

from engine import htmlToImage


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    try:
        from common import globalDefinition as comGD
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None


#===== 平台专属常量 begin =====

#平台编码与投递形态(与 ch_platform.platformCode / deliverMode 一致; deliverMode=asset_pack = 只导出不投递)
PLATFORM_CODE = "xiaohongshu"
DELIVER_MODE = "asset_pack"

#小红书产物规格(见 ch_platform(imageSpec=1080x1440) / ch_layout.specJson)
DEFAULT_CARD_SIZE = (1080, 1440)
DEFAULT_SLICE_HEIGHT = 1440
DEFAULT_RATIO = (3, 4)
DEFAULT_MAX_SIZE_PER_IMAGE_MB = 20
DEFAULT_FORMAT_LIST = ["jpg", "png"]
RATIO_TOLERANCE = 0.02

#支持的 layoutType(小红书形态): swipe=原生多图集 / longimage=长图 / stack=小红书形态为长图
#★ carousel 不在其中: 小红书不接收 HTML, 且轮播交互为公众号自实现 -> 显式 C7
SUPPORTED_LAYOUT_TYPE_LIST = ["swipe", "longimage", "stack"]
UNAVAILABLE_LAYOUT_TYPE_LIST = ["carousel"]

#素材包 manifest 生成时间
MANIFEST_NOTE = "本轮只输出素材包清单与 manifest 草稿; ZIP 打包与导出归 SP4; 本素材包须在官方创作服务平台手动发布"

#错误码(contenthub msgKey; 渲染/产物类一律 E 段, 不占用 C*/D*/F*/G* 段 —— 见 code/src/plan.md §4)
ERR_TEMPLATE_NOT_FOUND = "E0"        #版式不支持/模板缺失
ERR_RENDER_FAILED = "E1"             #渲染失败
ERR_SCREENSHOT_TIMEOUT = "E2"        #截图超时
ERR_ARTIFACT_FAILED = "E3"           #产物生成失败(长图超上限/切片失败)
ERR_FILE_TYPE = "D0"                 #文件类型不允许(格式非 JPG/PNG)
ERR_IMAGE_SPEC = "D1"                #图片尺寸/比例不符合平台规格

#===== 平台专属常量 end =====


#===== 版式分派: swipe 强制校验(主计划 2.6.3) begin =====

def validateSwipeSpec(assetList, spec, imageMaxCount = 0):
    """★ swipe 强制校验(主计划 2.6.3):
         1) 比例统一: 整篇同一比例(与 spec.ratio / 默认 3:4 比对), **非目标比例一律显式报错(D1), 不静默裁切**;
         2) 张数上限: ≤ min(spec.maxCount, ch_platform.imageMaxCount);
         3) 单张大小: ≤ spec.maxSizePerImageMB(默认 20MB);
         4) 格式: spec.format(默认 jpg/png)。
       出参: base 风格 {"errCode","field","errMsgList","data"}。尺寸未知时不误报(交由渲染期归一后再判)。"""
    assetList = assetList if isinstance(assetList, (list, tuple)) else []
    spec = spec if isinstance(spec, dict) else {}

    ratioW, ratioH = layoutEngine.parseRatio(spec.get("ratio"), DEFAULT_RATIO)
    targetRatio = (ratioW / ratioH) if ratioH else 0.75
    maxCount = base._toInt(spec.get("maxCount"), 18)
    if imageMaxCount and imageMaxCount > 0:
        maxCount = min(maxCount, imageMaxCount) if maxCount > 0 else imageMaxCount
    minCount = base._toInt(spec.get("minCount"), 1)
    maxSizeMB = base._toInt(spec.get("maxSizePerImageMB"), DEFAULT_MAX_SIZE_PER_IMAGE_MB)

    formatList = spec.get("format")
    if isinstance(formatList, (list, tuple)):
        formatList = [base._toStr(item).lower() for item in formatList if base._toStr(item)]
    else:
        formatList = list(DEFAULT_FORMAT_LIST)

    count = len(assetList)
    errCode = ""
    fieldName = ""
    errMsgList = []

    def addErr(code, fieldLabel, message):
        nonlocal errCode, fieldName
        if not errCode:
            errCode = code
            fieldName = fieldLabel
        errMsgList.append(message)

    if minCount > 0 and count < minCount:
        addErr(base.ERR_FIELD_OUT_OF_RANGE, base._fieldLabel("imageCount", PLATFORM_CODE),
               f"小红书滑动多图集至少 {minCount} 张, 当前 {count} 张")
    if maxCount > 0 and count > maxCount:
        addErr(base.ERR_FIELD_OUT_OF_RANGE, base._fieldLabel("imageMaxCount", PLATFORM_CODE),
               f"图片数 {count} 超小红书上限 {maxCount}(ch_platform.imageMaxCount / specJson.maxCount)")

    for idx, item in enumerate(assetList):
        if not isinstance(item, dict):
            continue
        seqLabel = f"第 {idx + 1} 张"

        fileExt = base._toStr(item.get("fileExt")).lower()
        if formatList and fileExt and fileExt not in formatList:
            addErr(ERR_FILE_TYPE, base._fieldLabel("specJson.format", PLATFORM_CODE),
                   f"{seqLabel}格式 {fileExt} 不在允许范围 {formatList}")

        sizeBytes = base._toInt(item.get("origSizeBytes"), 0)
        if maxSizeMB > 0 and sizeBytes > maxSizeMB * 1024 * 1024:
            addErr(ERR_IMAGE_SPEC, base._fieldLabel("specJson.maxSizePerImageMB", PLATFORM_CODE),
                   f"{seqLabel}大小 {sizeBytes} 字节 超单张上限 {maxSizeMB}MB")

        sourceWidth = base._toInt(item.get("width"), 0)
        sourceHeight = base._toInt(item.get("height"), 0)
        if sourceWidth > 0 and sourceHeight > 0:
            if abs((sourceWidth / sourceHeight) - targetRatio) > RATIO_TOLERANCE:
                addErr(ERR_IMAGE_SPEC, base._fieldLabel("specJson.uniformRatio", PLATFORM_CODE),
                       f"{seqLabel}比例 {sourceWidth}x{sourceHeight} 与整篇 {ratioW}:{ratioH} 不一致"
                       f"(小红书要求整篇单一比例, 混用会导致滑动时画面跳动; **不静默裁切**, 请先统一源图比例)")

    if errCode:
        return base._err(errCode, fieldName, errMsgList)
    return base._ok({"cardCount": count, "ratio": f"{ratioW}:{ratioH}", "maxCount": maxCount,
                     "maxSizePerImageMB": maxSizeMB, "format": formatList})

#===== swipe 强制校验 end =====


class XiaohongshuAdapter(base.PlatformAdapter):
    """小红书适配器(deliverMode=asset_pack; 只导出素材包, **无任何自动发布/投递路径**)。"""

    platformCode = PLATFORM_CODE
    deliverMode = DELIVER_MODE

    #----- 契约: render -----

    def render(self, topicData, layoutRecord, assetList, overrideSpec = None, options = None):
        """按 layoutType 分派为小红书形态产物(多张 PNG)。
           出参 data: {"outputKind","content","meta","products","platformCode","deliverMode"}。"""
        options = options if isinstance(options, dict) else {}
        assetList = assetList if isinstance(assetList, (list, tuple)) else []
        layoutRecord = layoutRecord if isinstance(layoutRecord, dict) else {}

        #1) 平台规格前置校验(标题/摘要/数量; 失败直接返回, 不做无效渲染)
        validateRtn = self.validate(topicData, assetList)
        if validateRtn.get("errCode") != base.ERR_OK:
            return validateRtn

        layoutType = base._toStr(layoutRecord.get("layoutType")).lower()

        #2) ★ carousel 在小红书不可用: 不接收 HTML, 轮播交互属公众号自实现 -> 显式报错(不得静默转换)
        if layoutType in UNAVAILABLE_LAYOUT_TYPE_LIST:
            return base._err(base.ERR_FIELD_INVALID, base._fieldLabel("layoutType", PLATFORM_CODE),
                             [f"carousel 版式不可用于小红书: 平台不接收 HTML, 且轮播交互为公众号自实现; "
                              f"请改用 swipe(原生多图集)/longimage(长图)/stack(小红书形态为长图)"])

        if layoutType not in SUPPORTED_LAYOUT_TYPE_LIST:
            return base._err(ERR_TEMPLATE_NOT_FOUND, base._fieldLabel("layoutType", PLATFORM_CODE),
                             [f"小红书不支持的 layoutType: {layoutType}, 允许值={SUPPORTED_LAYOUT_TYPE_LIST}"])

        if not assetList:
            return base._err(base.ERR_FIELD_MISSING, base._fieldLabel("assetList", PLATFORM_CODE),
                             ["小红书产物至少需要 1 张附图"])

        spec = layoutEngine.resolveSpec(layoutRecord, overrideSpec)

        try:
            if layoutType == "swipe":
                return self._renderSwipe(topicData, layoutRecord, assetList, overrideSpec, spec, options)
            #longimage 与 stack(小红书形态为长图) 都走长图管线
            return self._renderLongImage(topicData, layoutRecord, assetList, overrideSpec, spec, options, layoutType)
        except htmlToImage.HtmlToImageError as e:
            return base._err(e.errCode, e.field or base._fieldLabel("screenshot", PLATFORM_CODE), [e.message])
        except layoutEngine.LayoutEngineError as e:
            return base._err(e.errCode, e.field or base._fieldLabel("layoutCode", PLATFORM_CODE), [e.message])
        except Exception as e:
            if _LOG:
                _LOG.error(f"PID:{_processorPID}, xiaohongshu render failed, layoutType:{layoutType}, "
                           f"errMsg:{e}, {traceback.format_exc()}")
            return base._err(ERR_RENDER_FAILED, base._fieldLabel("layoutCode", PLATFORM_CODE),
                             [f"小红书形态渲染异常: {str(e)}"])

    #----- 渲染实现: swipe(原生多图集, 每张卡片一屏) -----

    def _renderSwipe(self, topicData, layoutRecord, assetList, overrideSpec, spec, options):
        cardWidth, cardHeight = layoutEngine.parseSize(spec.get("size"), DEFAULT_CARD_SIZE)

        #★ 2.6.3 强制校验(比例统一/张数/单张大小/格式): 不通过直接显式报错, 不静默裁切
        checkRtn = validateSwipeSpec(assetList, spec, imageMaxCount = self.imageMaxCount)
        if checkRtn.get("errCode") != base.ERR_OK:
            return checkRtn

        #引擎渲染(完整文档; embedMode=False), 得到 N 张等比例卡片(含 seqNo/封面标记)
        rendered = layoutEngine.renderLayout(layoutRecord, topicData, assetList, overrideSpec, embedMode = False)
        html = rendered.get("content") or ""
        meta = dict(rendered.get("meta") or {})
        cards = meta.get("cards") or []

        outDir = self._resolveOutDir(options, "ch_xhs_swipe_")
        selectorList = [{"seqNo": base._toInt(card.get("seqNo"), idx + 1),
                         "selector": f'[data-swipe-card="1"][data-seqno="{base._toInt(card.get("seqNo"), idx + 1)}"]'}
                        for idx, card in enumerate(cards)]

        shot = htmlToImage.renderCardsFromHtml(html, selectorList, outDir = outDir,
                                               viewport = (cardWidth, cardHeight),
                                               deviceScaleFactor = base._toInt(options.get("deviceScaleFactor"), 1) or 1,
                                               timeoutMs = base._toInt(options.get("timeoutMs"), htmlToImage.DEFAULT_RENDER_TIMEOUT_MS))
        imageMap = {base._toInt(img.get("seqNo"), 0): img for img in (shot.get("images") or [])}

        products = []
        for idx, card in enumerate(cards):
            seqNo = base._toInt(card.get("seqNo"), idx + 1)
            img = imageMap.get(seqNo) or {}
            product = self._buildProduct(topicData, layoutType = "swipe", seqNo = seqNo,
                                         localPath = img.get("path"), width = img.get("width"),
                                         height = img.get("height"), isCover = card.get("isCover"),
                                         sourceFileID = card.get("fileID"), caption = card.get("caption"),
                                         objectNameHint = "cover" if card.get("isCover") == "1" else "card")
            products.append(product)

        meta.update({
            "platformCode": self.platformCode,
            "platformName": self.platformRecord.get("platformName"),
            "deliverMode": self.deliverMode,
            "adapter": self.__class__.__name__,
            "artifactKind": "png_cards",
            "mechanism": meta.get("mechanism") or "platform_native",
            "cardCount": len(products),
            "size": f"{cardWidth}x{cardHeight}",
            "ratio": meta.get("ratio") or f"{DEFAULT_RATIO[0]}:{DEFAULT_RATIO[1]}",
            "productCount": len(products),
            "fontInfo": shot.get("fontInfo") or {},
            "specCheck": "passed",
            "networkRequest": "0",
        })
        meta["renderOutputKind"] = rendered.get("outputKind")

        return base._ok({
            "outputKind": "png",
            "content": html,
            "meta": meta,
            "products": products,
            "platformCode": self.platformCode,
            "deliverMode": self.deliverMode,
        })

    #----- 渲染实现: longimage / stack(小红书形态为长图) -----

    def _renderLongImage(self, topicData, layoutRecord, assetList, overrideSpec, spec, options, layoutType):
        cardWidth, cardHeight = layoutEngine.parseSize(spec.get("size"), DEFAULT_CARD_SIZE)
        sliceHeight = base._toInt(spec.get("sliceHeight"), cardHeight or DEFAULT_SLICE_HEIGHT) or DEFAULT_SLICE_HEIGHT
        maxTotalHeight = base._toInt(spec.get("maxTotalHeight"), 0)

        #stack 在小红书形态为长图: 把主题正文宽度归一到卡片宽度, 再整页截图切片
        renderSpec = overrideSpec
        if layoutType == "stack":
            merged = {}
            if isinstance(overrideSpec, dict):
                merged.update(overrideSpec)
            merged.setdefault("maxWidth", f"{cardWidth}px")
            renderSpec = merged

        rendered = layoutEngine.renderLayout(layoutRecord, topicData, assetList, renderSpec, embedMode = False)
        html = rendered.get("content") or ""
        meta = dict(rendered.get("meta") or {})

        outDir = self._resolveOutDir(options, "ch_xhs_long_")
        shot = htmlToImage.renderLongImageSlices(html, sliceHeight = sliceHeight, outDir = outDir,
                                                 viewport = (cardWidth, cardHeight),
                                                 deviceScaleFactor = base._toInt(options.get("deviceScaleFactor"), 1) or 1,
                                                 timeoutMs = base._toInt(options.get("timeoutMs"), htmlToImage.DEFAULT_RENDER_TIMEOUT_MS),
                                                 maxTotalHeight = maxTotalHeight)

        products = []
        for sliceInfo in shot.get("slices") or []:
            seqNo = base._toInt(sliceInfo.get("seqNo"), len(products) + 1)
            product = self._buildProduct(topicData, layoutType = layoutType, seqNo = seqNo,
                                         localPath = sliceInfo.get("path"), width = shot.get("fullWidth"),
                                         height = sliceInfo.get("height"), isCover = "1" if seqNo == 1 else "0",
                                         sourceFileID = "", caption = "",
                                         objectNameHint = "slice")
            products.append(product)

        meta.update({
            "platformCode": self.platformCode,
            "platformName": self.platformRecord.get("platformName"),
            "deliverMode": self.deliverMode,
            "adapter": self.__class__.__name__,
            "artifactKind": "png_slices",
            "sourceLayoutType": layoutType,
            "sliceHeight": sliceHeight,
            "sliceCount": len(products),
            "fullWidth": shot.get("fullWidth"),
            "fullHeight": shot.get("fullHeight"),
            "size": f"{cardWidth}x{cardHeight}",
            "productCount": len(products),
            "fontInfo": shot.get("fontInfo") or {},
            "specCheck": "passed",
            "networkRequest": "0",
        })
        meta["renderOutputKind"] = rendered.get("outputKind")

        return base._ok({
            "outputKind": "png",
            "content": html,
            "meta": meta,
            "products": products,
            "platformCode": self.platformCode,
            "deliverMode": self.deliverMode,
        })

    #----- 内部: 产物记录与输出目录 -----

    def _resolveOutDir(self, options, prefix):
        outDir = base._toStr(options.get("productDir"))
        if not outDir:
            outDir = tempfile.mkdtemp(prefix = prefix)
        elif not os.path.isdir(outDir):
            os.makedirs(outDir, exist_ok = True)
        return outDir

    def _buildProduct(self, topicData, layoutType, seqNo, localPath, width, height,
                      isCover, sourceFileID, caption, objectNameHint):
        """构造单条产物记录: 本地落盘 -> 经 fileStorageCommon 上传 -> 返回 fileID(台账写入归 SP3c, 本轮不写库)。"""
        topicData = topicData if isinstance(topicData, dict) else {}
        topicCode = base._toStr(topicData.get("topicCode")) or base._toStr(topicData.get("recID"))
        objectName = f"{topicCode or 'xhs'}_{int(seqNo):02d}_{objectNameHint}.png"
        fileID = htmlToImage.uploadArtifact(localPath, objectName = objectName, privateFlag = True)

        return {
            "seqNo": int(seqNo),
            "kind": "png",
            "fileID": fileID,
            "fileUrl": "",
            "localPath": localPath,
            "fileName": objectName,
            "width": base._toInt(width, 0),
            "height": base._toInt(height, 0),
            "sizeBytes": htmlToImage.fileSizeBytes(localPath),
            "sha256": htmlToImage.computeFileSha256(localPath),
            "isCover": base._toStr(isCover) or "0",
            "sourceFileID": base._toStr(sourceFileID),
            "caption": base._toStr(caption),
            "layoutType": layoutType,
            "platform": self.platformCode,
        }

    #----- 契约: validate -----

    def validate(self, topicData, assetList, platformRecord = None):
        """平台规格校验(数据驱动 ch_platform; 小红书口径):
           - 标题: 必填 + ≤ titleMaxLen(小红书 20);
           - 摘要: ≤ summaryMaxLen;
           - 图片数量: ≤ imageMaxCount(小红书 18);
           ★ 不做 coverSpec/imageSpec 精确像素判定 —— 小红书产物一律在渲染期归一到 1080x1440,
             比例一致性由 validateSwipeSpec 按**比例**判定(见 2.6.3), 避免对 3:4 但非 1080 的源图误报。"""
        record = platformRecord if isinstance(platformRecord, dict) else self.platformRecord
        normalized = base.normalizePlatformRecord(record)
        topicData = topicData if isinstance(topicData, dict) else {}
        assetList = assetList if isinstance(assetList, (list, tuple)) else []

        errCode = ""
        fieldName = ""
        errMsgList = []

        def addErr(code, fieldLabel, message):
            nonlocal errCode, fieldName
            if not errCode:
                errCode = code
                fieldName = fieldLabel
            errMsgList.append(message)

        title = base._toStr(topicData.get("title"))
        titleMaxLen = base._toInt(normalized.get("titleMaxLen"), 0)
        if not title:
            addErr(base.ERR_FIELD_MISSING, base._fieldLabel("title", PLATFORM_CODE), "title 为必填字段")
        elif titleMaxLen > 0 and len(title) > titleMaxLen:
            addErr(base.ERR_FIELD_TOO_LONG, base._fieldLabel("title", PLATFORM_CODE),
                   f"title 长度={len(title)} 超小红书上限 {titleMaxLen}")

        summary = base._toStr(topicData.get("summary"))
        summaryMaxLen = base._toInt(normalized.get("summaryMaxLen"), 0)
        if summary and summaryMaxLen > 0 and len(summary) > summaryMaxLen:
            addErr(base.ERR_FIELD_TOO_LONG, base._fieldLabel("summary", PLATFORM_CODE),
                   f"summary 长度={len(summary)} 超小红书上限 {summaryMaxLen}")

        imageMaxCount = base._toInt(normalized.get("imageMaxCount"), 0)
        if imageMaxCount > 0 and len(assetList) > imageMaxCount:
            addErr(base.ERR_FIELD_OUT_OF_RANGE, base._fieldLabel("imageMaxCount", PLATFORM_CODE),
                   f"图片数 {len(assetList)} 超小红书上限 {imageMaxCount}")

        if errCode:
            return base._err(errCode, fieldName, errMsgList, {"platformCode": self.platformCode})
        return base._ok({"platformCode": self.platformCode, "imageCount": len(assetList)})

    #----- 契约: package -----

    def package(self, renderResult, topicData, assetList, options = None):
        """素材包清单(有序文件列表 + manifest 草稿: 主题编码/生成时间/版式/平台/校验值)。
           ★ 本轮只出清单, **不做 ZIP 打包**(ZIP 与导出归 SP4)。"""
        renderResult = renderResult if isinstance(renderResult, dict) else {}
        topicData = topicData if isinstance(topicData, dict) else {}

        products = renderResult.get("products")
        if not isinstance(products, (list, tuple)):
            products = []
        meta = renderResult.get("meta") or {}

        #有序文件列表(按 seqNo 升序; 顺序即 App 内左右滑动浏览顺序)
        itemList = []
        for product in sorted([item for item in products if isinstance(item, dict)],
                              key = lambda data: base._toInt(data.get("seqNo"), 0)):
            itemList.append({
                "seqNo": base._toInt(product.get("seqNo"), 0),
                "fileName": base._toStr(product.get("fileName")),
                "fileID": base._toStr(product.get("fileID")),
                "width": base._toInt(product.get("width"), 0),
                "height": base._toInt(product.get("height"), 0),
                "sizeBytes": base._toInt(product.get("sizeBytes"), 0),
                "sha256": base._toStr(product.get("sha256")),
                "isCover": base._toStr(product.get("isCover")) or "0",
            })

        #manifest 草稿(主计划 7.8: 含主题编码/生成时间/版式/平台/文件清单与校验值)
        checkSum = hashlib_sha256_of_list([item.get("sha256") for item in itemList])
        manifest = {
            "topicCode": base._toStr(topicData.get("topicCode")),
            "topicID": base._toStr(topicData.get("recID")),
            "title": base._toStr(topicData.get("title")),
            "generatedAt": misc.getTime(),
            "layoutCode": base._toStr(meta.get("layoutCode")),
            "layoutType": base._toStr(meta.get("layoutType")),
            "platform": self.platformCode,
            "imageCount": len(itemList),
            "size": base._toStr(meta.get("size")) or "1080x1440",
            "ratio": base._toStr(meta.get("ratio")) or "3:4",
            "fileList": itemList,
            "checkSum": checkSum,
            "checkSumMethod": "sha256(按 seqNo 拼接各文件 sha256)",
        }

        plan = {
            "platformCode": self.platformCode,
            "deliverMode": self.deliverMode,
            "packageKind": "xiaohongshu_asset_pack",
            "itemList": itemList,
            "manifestDraft": manifest,
            "manifestRequired": True,
            "imageCount": len(itemList),
            "zipPacked": False,
            "note": MANIFEST_NOTE,
        }
        return base._ok(plan)

    #----- 契约: checkHealth(只读, 零网络) -----

    def checkHealth(self, sessionIDSet = None):
        """只读 ch_account 与配置态, **不发任何网络请求**(小红书只导出素材包, 无需平台凭据)"""
        accountList = []
        errMsg = ""
        try:
            tableName = comMysql.tablename_convertor_ch_account()
            accountList = comMysql.query_ch_account(tableName, platform = self.platformCode, mode = "full")
        except Exception as e:
            errMsg = str(e)
            if _LOG:
                _LOG.warning(f"W: PID:{_processorPID}, xiaohongshu checkHealth 读取 ch_account 失败, errMsg:{str(e)}")

        healthStatusList = sorted({base._toStr(item.get("healthStatus")) or "UNKNOWN"
                                   for item in accountList if isinstance(item, dict)})

        return base._ok({
            "platformCode": self.platformCode,
            "deliverMode": self.deliverMode,
            "credentialConfigured": "1",
            "credentialMissingList": [],
            "accountCount": len(accountList),
            "healthStatusList": healthStatusList,
            "networkRequest": "0",
            "checkedAt": misc.getTime(),
            "errMsg": errMsg,
            "note": "小红书只导出素材包(asset_pack), 无自动发布/投递路径, 无需平台凭据",
        })


def hashlib_sha256_of_list(valueList):
    """素材包整体校验值: sha256(按顺序拼接各文件 sha256)"""
    import hashlib
    digester = hashlib.sha256()
    for value in valueList or []:
        digester.update(base._toStr(value).encode("utf-8"))
    return digester.hexdigest()


if __name__ == "__main__":
    pass
    #本地自测(不连库/不联网): 只验证纯函数与契约
    _adapter = XiaohongshuAdapter({"platformCode": "xiaohongshu", "titleMaxLen": 20, "imageMaxCount": 18})
    print("platformCode:", _adapter.platformCode, "deliverMode:", _adapter.deliverMode)
    print("validate(empty title):", _adapter.validate({}, [])["errCode"])
    print("validateSwipeSpec(ratio mix):",
          validateSwipeSpec([{"width": 1080, "height": 1440}, {"width": 1080, "height": 1080}],
                            {"ratio": "3:4", "maxCount": 18, "uniformRatio": True})["errCode"])
    print("deliver:", _adapter.deliver({})["errCode"])
