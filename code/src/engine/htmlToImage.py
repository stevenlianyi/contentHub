#! /usr/bin/env python3
#encoding: utf-8:

#Filename: htmlToImage.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub HTML -> PNG 截图管线(SP3b · C5 小红书产物渲染, 主计划 P2-3)。

#职责(把已渲染的 HTML 片段/整页截成 PNG 产物, 供小红书卡片/长图切片使用):
#  1) 懒加载**单浏览器实例**(进程内复用, **串行渲染**, 用完经 closeBrowser 统一关闭);
#     每张卡片独立 context/page, headless 运行;
#  2) viewport 取 DEFAULT_CARD_SIZE(1080x1440) 或调用方传入的 specJson.size;
#     device_scale_factor 可配(默认 1, 保证像素 = CSS 像素, 输出精确 1080x1440);
#  3) 字体预加载 + waitForFonts: 注入中文字体栈 + 等待 document.fonts 就绪
#     (document.fonts.status === "loaded", 另有显式超时兜底), 并记录**实际使用字体**便于排查中文丢字;
#  4) HTML -> PNG: 元素级(selector)或整页(full_page); 长图整页截图 + 按 sliceHeight 切分(复用 engine/imageProc);
#  5) 产物先落本地临时目录, 再经 common/fileStorageCommon.py 上传(红线 R2; SELFFILE 模式可真实落盘验证);
#  6) 失败与超时映射为 contenthub 错误码: 截图超时 -> E2, 产物生成失败 -> E3(**不抛裸异常**)。
#
#★ 分层契约(强制单向): 本文件属引擎层(engine/), 只可依赖 common/ 与同层 engine/;
#  **不得 import processor/ 或 subfunc/**(引擎层不反向依赖业务层/接入层)。
#
#★ 零对外网络红线(SP3b): 不调小红书任何接口; 页面内 `<img>` 若为本地文件一律内联为 data URI,
#  保证「本地渲染」不依赖任何外部网络; 产物上传只到本项目文件服务(fileStorageCommon)。
#
#错误码(contenthub msgKey; 渲染/产物类一律 E 段 —— 见 code/src/plan.md §4):
#  E1 Playwright 不可用/浏览器启动失败 | E2 截图超时 | E3 产物生成失败

_VERSION="20260919"


import base64
import hashlib
import os
import re
import sys
import tempfile
import threading

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../code/src
if parentdir not in sys.path:
    sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

#common functions(log,time,string, json etc)
from common import globalDefinition as comGD

from common import miscCommon as misc

#同层引擎能力: 长图切片/尺寸探测(渲染期派生的唯一定义处, 本文件不重复实现)
from engine import imageProc


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    try:
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None


#===== 常量与错误码 begin =====

#截图规格(与 ch_layout.specJson / ch_platform.imageSpec 口径一致: 1080x1440 = 3:4)
DEFAULT_CARD_SIZE = (1080, 1440)
DEFAULT_SLICE_HEIGHT = 1440
DEFAULT_DEVICE_SCALE_FACTOR = 1

#渲染超时上限(保守策略: 单实例串行, 不做并发池; 超时统一映射 E2)
DEFAULT_RENDER_TIMEOUT_MS = 30000
DEFAULT_FONT_WAIT_TIMEOUT_MS = 8000

#中文字体栈: Windows 有微软雅黑; Linux 部署需另装(如 Noto Sans CJK SC / 文泉驿), 否则中文可能丢字
DEFAULT_FONT_FAMILY = ('"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",'
                       '"WenQuanYi Micro Hei","Heiti SC","SimSun",sans-serif')

#headless Chromium 启动参数(无色差/无滚动条; 容器内需 --no-sandbox)
DEFAULT_BROWSER_ARGS = [
    "--disable-gpu",
    "--no-sandbox",
    "--hide-scrollbars",
    "--force-color-profile=srgb",
    "--disable-dev-shm-usage",
]

#本地图片扩展名 -> MIME(内联为 data URI, 保证本地渲染零外部网络)
IMAGE_MIME_MAP = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".bmp": "image/bmp", ".gif": "image/gif",
}

#错误码落点(common/errMsgCommon.py::_CH_ERROR_WORD 的 contenthub E 段)
ERR_RENDER_FAILED = "E1"          #Playwright 不可用/浏览器启动失败
ERR_SCREENSHOT_TIMEOUT = "E2"     #截图超时
ERR_ARTIFACT_FAILED = "E3"        #产物生成失败(截图/切分失败)

#===== 常量与错误码 end =====


#===== 异常 begin =====

class HtmlToImageError(Exception):
    """截图管线异常: 携带 contenthub E 段错误码, 由适配器/业务层映射为 HTTP 报文"""
    def __init__(self, errCode, message, field = ""):
        super().__init__(message)
        self.errCode = errCode
        self.field = field
        self.message = message

#===== 异常 end =====


#===== 通用小工具 begin =====

def _toStr(value):
    """None/数字/任意 -> 去空白字符串"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def parseSize(size, default = DEFAULT_CARD_SIZE):
    """把 '1080x1440' / (1080, 1440) / [1080, 1440] 解析为 (width, height); 非法回落 default"""
    if isinstance(size, (tuple, list)) and len(size) == 2:
        try:
            width, height = int(size[0]), int(size[1])
            if width > 0 and height > 0:
                return width, height
        except Exception:
            return default
    text = _toStr(size).lower().replace("*", "x")
    if "x" in text:
        parts = text.split("x")
        if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
            width, height = int(parts[0]), int(parts[1])
            if width > 0 and height > 0:
                return width, height
    return default

#===== 通用小工具 end =====


#===== 本地图片内联(保证本地渲染零外部网络) begin =====

_IMG_TAG_PATTERN = re.compile(r"<img\b[^>]*?>", re.IGNORECASE | re.DOTALL)
_SRC_ATTR_PATTERN = re.compile(r"""\bsrc\s*=\s*("([^"]*)"|'([^']*)')""", re.IGNORECASE)


def toDataUri(localPath):
    """本地图片 -> data URI; 非文件/失败返回 \"\"。用于本地渲染时避免浏览器访问 file:// 被拦。"""
    path = _toStr(localPath)
    if path.lower().startswith("file://"):
        path = path[7:]
    if not path or not os.path.isfile(path):
        return ""
    fileExt = os.path.splitext(path)[1].lower()
    mime = IMAGE_MIME_MAP.get(fileExt)
    if not mime:
        return ""
    try:
        with open(path, "rb") as hFile:
            raw = hFile.read()
        return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")
    except Exception:
        return ""


def base64EncodeFile(localPath):
    """本地文件 -> (dataUri, mime); 失败返回 ("", "")"""
    path = _toStr(localPath)
    if path.lower().startswith("file://"):
        path = path[7:]
    if not path or not os.path.isfile(path):
        return "", ""
    mime = IMAGE_MIME_MAP.get(os.path.splitext(path)[1].lower(), "")
    if not mime:
        return "", ""
    try:
        with open(path, "rb") as hFile:
            raw = hFile.read()
        return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii"), mime
    except Exception:
        return "", ""


def inlineLocalImages(html):
    """把 HTML 中 `<img src>` 指向的**本地文件**内联为 data URI(其余 http(s)/data URI 原样保留)。
       目的: 本地/离线渲染不依赖任何外部网络, 也不受浏览器 file:// 同源策略限制。"""
    html = html if isinstance(html, str) else ""
    if not html:
        return html

    def _replaceImg(matchObj):
        tagHtml = matchObj.group(0)
        matched = _SRC_ATTR_PATTERN.search(tagHtml)
        if not matched:
            return tagHtml
        rawSrc = matched.group(2) if matched.group(2) is not None else matched.group(3)
        src = _toStr(rawSrc)
        if not src or src.lower().startswith("http://") or src.lower().startswith("https://") \
                or src.lower().startswith("data:"):
            return tagHtml
        dataUri = toDataUri(src)
        if not dataUri:
            return tagHtml
        quote = '"' if matched.group(2) is not None else "'"
        return tagHtml[:matched.start()] + f"src={quote}{dataUri}{quote}" + tagHtml[matched.end():]

    return _IMG_TAG_PATTERN.sub(_replaceImg, html)

#===== 本地图片内联 end =====


#===== 浏览器单实例管理(懒加载 + 串行 + 统一关闭) begin =====

_BROWSER = None
_PLAYWRIGHT = None
_PW_SYNC = None
_PW_TIMEOUT_ERROR = None
_RENDER_LOCK = threading.RLock()


def _loadPlaywright():
    """延迟导入 Playwright(未安装时给出 E1 而非裸 ImportError)"""
    global _PW_SYNC, _PW_TIMEOUT_ERROR
    if _PW_SYNC is not None:
        return
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    except Exception as e:
        raise HtmlToImageError(ERR_RENDER_FAILED, f"Playwright 不可用: {str(e)}", "playwright")
    _PW_SYNC = sync_playwright
    _PW_TIMEOUT_ERROR = PlaywrightTimeoutError


def getBrowser():
    """懒加载单浏览器实例(进程内复用); 失败抛 E1"""
    global _BROWSER, _PLAYWRIGHT
    with _RENDER_LOCK:
        if _BROWSER is not None:
            return _BROWSER
        _loadPlaywright()
        try:
            _PLAYWRIGHT = _PW_SYNC().start()
            _BROWSER = _PLAYWRIGHT.chromium.launch(headless = True, args = DEFAULT_BROWSER_ARGS)
        except Exception as e:
            try:
                if _PLAYWRIGHT is not None:
                    _PLAYWRIGHT.stop()
            except Exception:
                pass
            _PLAYWRIGHT = None
            _BROWSER = None
            raise HtmlToImageError(ERR_RENDER_FAILED, f"Chromium 启动失败: {str(e)}", "chromium")
        return _BROWSER


def closeBrowser():
    """关闭浏览器实例并释放 Playwright(进程退出/长驻任务收尾时调用); 幂等, 不抛异常"""
    global _BROWSER, _PLAYWRIGHT
    with _RENDER_LOCK:
        try:
            if _BROWSER is not None:
                _BROWSER.close()
        except Exception:
            pass
        _BROWSER = None
        try:
            if _PLAYWRIGHT is not None:
                _PLAYWRIGHT.stop()
        except Exception:
            pass
        _PLAYWRIGHT = None


def isBrowserAvailable():
    """诊断用: 浏览器是否可用(不启动时不产生副作用, 仅探测 getBrowser)"""
    try:
        getBrowser()
        return True
    except Exception:
        return False

#===== 浏览器单实例管理 end =====


#===== 字体预加载 + waitForFonts begin =====

def buildFontStyleTag(fontFamily = ""):
    """构造强制字体栈的 <style> 片段(注入到页面, 保证中文渲染不丢字)"""
    family = _toStr(fontFamily) or DEFAULT_FONT_FAMILY
    return f"<style>html,body,#__chRoot{{font-family:{family};}}</style>"


def waitForFonts(page, timeoutMs = DEFAULT_FONT_WAIT_TIMEOUT_MS):
    """★ 字体预加载: 等待 document.fonts 就绪(document.fonts.status === "loaded")。
       显式超时兜底 —— 超时不抛异常(继续截图), 但记录 timedOut, 便于排查中文丢字。
       出参: {"ready","timedOut","fontStatus","declaredFontFamilies","usedFontFamilies","timeoutMs"}"""
    timeoutMs = int(timeoutMs or DEFAULT_FONT_WAIT_TIMEOUT_MS)
    fontInfo = {"ready": False, "timedOut": False, "fontStatus": "",
                "declaredFontFamilies": [], "usedFontFamilies": [], "timeoutMs": timeoutMs}

    try:
        page.wait_for_function("() => !!(document.fonts && document.fonts.status === 'loaded')",
                               timeout = timeoutMs)
        fontInfo["ready"] = True
    except Exception:
        fontInfo["timedOut"] = True

    #兜底: 再显式等待 document.fonts.ready(即便上一步超时也尽量给字体机会)
    try:
        page.evaluate("() => (document.fonts && document.fonts.ready) ? 1 : 1")
    except Exception:
        pass

    try:
        fontInfo["fontStatus"] = _toStr(page.evaluate("() => (document.fonts && document.fonts.status) ? document.fonts.status : ''"))
        fontInfo["declaredFontFamilies"] = list(page.evaluate(
            "() => document.fonts ? Array.from(document.fonts).map(f => f.family) : []"))
    except Exception:
        pass

    #实际使用字体: 抽样若干代表性元素的 computed fontFamily(便于排查中文丢字)
    try:
        used = page.evaluate(
            "() => {const sel=['body','h1','h2','p','figure','figcaption','span','div'];"
            "const set=new Set();for(const s of sel){const el=document.querySelector(s);"
            "if(el){set.add(getComputedStyle(el).fontFamily);}}return Array.from(set);}")
        fontInfo["usedFontFamilies"] = list(used or [])
    except Exception:
        pass

    return fontInfo

#===== 字体预加载 end =====


#===== 核心截图 begin =====

def renderHtmlToImage(html, outPath = "", viewport = None, deviceScaleFactor = DEFAULT_DEVICE_SCALE_FACTOR,
                      fullPage = False, selector = "", timeoutMs = DEFAULT_RENDER_TIMEOUT_MS,
                      fontFamily = "", waitFonts = True, inlineImages = True):
    """HTML -> PNG 截图(元素级或整页)。
       入参:
         html             已渲染的 HTML(完整文档或片段)
         outPath          输出 PNG 路径(缺省落临时文件)
         viewport         (w, h) 或 '1080x1440'; 缺省 DEFAULT_CARD_SIZE
         deviceScaleFactor 缩放因子(默认 1 -> 输出像素 = CSS 像素)
         fullPage         True=整页长图截图; False=视口截图
         selector         非空时按 CSS 选择器做**元素级**截图(此时忽略 fullPage)
         timeoutMs        渲染/截图超时(超时 -> E2)
         fontFamily       强制字体栈(缺省 DEFAULT_FONT_FAMILY)
         waitFonts        是否等待字体就绪
         inlineImages     是否把本地图片内联为 data URI(保证零外部网络)
       出参: {"path","width","height","fullPage","selector","fontInfo"}
       失败: 抛 HtmlToImageError(E2 超时 / E3 产物生成失败 / E1 浏览器不可用)。"""
    _loadPlaywright()
    browser = getBrowser()

    width, height = parseSize(viewport, DEFAULT_CARD_SIZE)
    scale = float(deviceScaleFactor or DEFAULT_DEVICE_SCALE_FACTOR) or DEFAULT_DEVICE_SCALE_FACTOR
    timeoutMs = int(timeoutMs or DEFAULT_RENDER_TIMEOUT_MS)
    selector = _toStr(selector)
    content = inlineLocalImages(html) if inlineImages else (html if isinstance(html, str) else "")
    if not content.strip():
        raise HtmlToImageError(ERR_ARTIFACT_FAILED, "截图输入 HTML 为空", "content")

    if not outPath:
        fd, outPath = tempfile.mkstemp(suffix = ".png", prefix = "ch_shot_")
        os.close(fd)

    outWidth, outHeight = int(round(width * scale)), int(round(height * scale))
    fontInfo = {}

    #串行渲染: 单浏览器实例在进程内复用, 同一时刻只渲染一个页面
    with _RENDER_LOCK:
        context = None
        page = None
        try:
            context = browser.new_context(viewport = {"width": width, "height": height},
                                          device_scale_factor = scale)
            page = context.new_page()
            page.set_content(content, wait_until = "load", timeout = timeoutMs)

            #字体预加载(注入中文字体栈 + 等待 document.fonts 就绪)
            family = _toStr(fontFamily) or DEFAULT_FONT_FAMILY
            try:
                page.add_style_tag(content = f"html,body{{font-family:{family};}}")
            except Exception:
                pass
            if waitFonts:
                fontInfo = waitForFonts(page, timeoutMs = min(DEFAULT_FONT_WAIT_TIMEOUT_MS, timeoutMs))

            if selector:
                locator = page.locator(selector).first
                locator.wait_for(state = "visible", timeout = timeoutMs)
                box = locator.bounding_box(timeout = timeoutMs) or {}
                locator.screenshot(path = outPath, timeout = timeoutMs)
                outWidth = int(round(float(box.get("width", width)) * scale))
                outHeight = int(round(float(box.get("height", height)) * scale))
            elif fullPage:
                page.screenshot(path = outPath, full_page = True, timeout = timeoutMs)
                pageSize = page.evaluate(
                    "() => ({w: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),"
                    " h: Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)})") or {}
                outWidth = int(round(float(pageSize.get("w", width)) * scale))
                outHeight = int(round(float(pageSize.get("h", height)) * scale))
            else:
                page.screenshot(path = outPath, timeout = timeoutMs)
                outWidth, outHeight = int(round(width * scale)), int(round(height * scale))

        except Exception as e:
            if _PW_TIMEOUT_ERROR is not None and isinstance(e, _PW_TIMEOUT_ERROR):
                if _LOG:
                    _LOG.error(f"PID:{_processorPID}, htmlToImage 截图超时, errMsg:{str(e)}")
                raise HtmlToImageError(ERR_SCREENSHOT_TIMEOUT,
                                       f"截图超时(>{timeoutMs}ms): {str(e)}", "screenshot")
            if isinstance(e, HtmlToImageError):
                raise
            if _LOG:
                _LOG.error(f"PID:{_processorPID}, htmlToImage 截图失败, errMsg:{str(e)}")
            raise HtmlToImageError(ERR_ARTIFACT_FAILED, f"产物生成失败(截图): {str(e)}", "screenshot")
        finally:
            try:
                if page is not None:
                    page.close()
            except Exception:
                pass
            try:
                if context is not None:
                    context.close()
            except Exception:
                pass

    return {"path": outPath, "width": outWidth, "height": outHeight,
            "fullPage": bool(fullPage), "selector": selector, "fontInfo": fontInfo}


def renderCardsFromHtml(html, selectorList, outDir = "", viewport = None,
                        deviceScaleFactor = DEFAULT_DEVICE_SCALE_FACTOR,
                        timeoutMs = DEFAULT_RENDER_TIMEOUT_MS, fontFamily = "", waitFonts = True):
    """★ swipe 卡片渲染: 每张卡片一屏 -> 一张 PNG(**每张卡片独立 context/page**, 浏览器实例进程内复用)。
       入参 selectorList = [{"seqNo": 1, "selector": '[data-swipe-card="1"][data-seqno="1"]'}, ...]
       出参: {"images":[{"seqNo","selector","path","width","height"}], "fontInfo": {...}}
       失败: 抛 HtmlToImageError(E2/E3)。"""
    if not outDir:
        outDir = tempfile.mkdtemp(prefix = "ch_xhs_cards_")
    elif not os.path.isdir(outDir):
        os.makedirs(outDir, exist_ok = True)

    images = []
    fontInfo = {}
    for item in selectorList or []:
        seqNo = int(item.get("seqNo") or (len(images) + 1))
        selector = _toStr(item.get("selector"))
        outPath = os.path.join(outDir, f"card_{seqNo:03d}.png")
        shot = renderHtmlToImage(html, outPath = outPath, viewport = viewport,
                                 deviceScaleFactor = deviceScaleFactor, selector = selector,
                                 timeoutMs = timeoutMs, fontFamily = fontFamily, waitFonts = waitFonts)
        fontInfo = shot.get("fontInfo") or fontInfo
        images.append({"seqNo": seqNo, "selector": selector, "path": shot.get("path"),
                       "width": shot.get("width"), "height": shot.get("height")})

    return {"images": images, "fontInfo": fontInfo}


def renderLongImageSlices(html, sliceHeight = DEFAULT_SLICE_HEIGHT, outDir = "", viewport = None,
                          deviceScaleFactor = DEFAULT_DEVICE_SCALE_FACTOR,
                          timeoutMs = DEFAULT_RENDER_TIMEOUT_MS, fontFamily = "",
                          waitFonts = True, fullImagePath = "", maxTotalHeight = 0):
    """★ 长图渲染: 整页截图 -> 按 sliceHeight 切分(**禁止直接产出超长单图**)。
       切片复用 engine/imageProc.sliceLongImage(渲染期派生唯一定义处)。
       出参: {"fullImagePath","fullWidth","fullHeight","sliceHeight","sliceCount","slices","fontInfo"}
       失败: 抛 HtmlToImageError(E2 截图超时 / E3 产物生成失败或超总高上限)。"""
    width, height = parseSize(viewport, DEFAULT_CARD_SIZE)
    shot = renderHtmlToImage(html, outPath = fullImagePath, viewport = (width, height),
                             deviceScaleFactor = deviceScaleFactor, fullPage = True,
                             timeoutMs = timeoutMs, fontFamily = fontFamily, waitFonts = waitFonts)

    fullHeight = int(shot.get("height") or 0)
    fullWidth = int(shot.get("width") or width)
    maxTotalHeight = int(maxTotalHeight or 0)
    if maxTotalHeight > 0 and fullHeight > maxTotalHeight:
        raise HtmlToImageError(ERR_ARTIFACT_FAILED,
                               f"长图总高 {fullHeight} 超上限 {maxTotalHeight}(须先切分)",
                               "maxTotalHeight")

    sliceHeight = int(sliceHeight) if int(sliceHeight or 0) > 0 else DEFAULT_SLICE_HEIGHT
    if not outDir:
        outDir = tempfile.mkdtemp(prefix = "ch_xhs_slices_")
    elif not os.path.isdir(outDir):
        os.makedirs(outDir, exist_ok = True)

    sliceInfo = imageProc.sliceLongImage(shot.get("path"), sliceHeight = sliceHeight,
                                         sliceWidth = fullWidth, outDir = outDir)
    slices = sliceInfo.get("slices") or []
    if not slices:
        raise HtmlToImageError(ERR_ARTIFACT_FAILED, "长图切片失败(无切片产出)", "slices")

    return {"fullImagePath": shot.get("path"), "fullWidth": fullWidth, "fullHeight": fullHeight,
            "sliceHeight": sliceHeight, "sliceCount": len(slices), "slices": slices,
            "fontInfo": shot.get("fontInfo") or {}}

#===== 核心截图 end =====


#===== 产物上传与校验值(红线 R2: 只经 fileStorageCommon) begin =====

def uploadArtifact(localPath, objectName = "", privateFlag = True):
    """把本地 PNG 产物上传到文件服务, 返回 fileID; 失败返回 \"\"(不抛异常)。
       文件门面延迟导入 —— 该模块会牵出云厂商 SDK, 仅截图时不应强制依赖。"""
    if not localPath or not os.path.isfile(localPath):
        return ""
    try:
        from common import fileStorageCommon as comFS
        return comFS.saveFile(localPath, objectName = objectName, privateFlag = privateFlag,
                              bucketCode = comFS.chDefaultBucketCode()) or ""
    except Exception as e:
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, htmlToImage uploadArtifact failed, localPath:{localPath}, errMsg:{str(e)}")
        return ""


def computeFileSha256(localPath):
    """计算文件 sha256(素材包 manifest 校验值); 失败返回 \"\"。"""
    if not localPath or not os.path.isfile(localPath):
        return ""
    try:
        digester = hashlib.sha256()
        with open(localPath, "rb") as hFile:
            for chunk in iter(lambda: hFile.read(1024 * 1024), b""):
                digester.update(chunk)
        return digester.hexdigest()
    except Exception:
        return ""


def fileSizeBytes(localPath):
    """文件字节数; 失败返回 0"""
    try:
        return os.path.getsize(localPath) if localPath and os.path.isfile(localPath) else 0
    except Exception:
        return 0

#===== 产物上传与校验值 end =====


def cleanupTempDir(dirPath):
    """清理截图临时目录(失败不抛异常)"""
    if not dirPath or not os.path.isdir(dirPath):
        return
    try:
        import shutil
        shutil.rmtree(dirPath, ignore_errors = True)
    except Exception:
        pass


if __name__ == "__main__":
    pass
    #本地自测(不连库/不连文件服务): 只验证纯函数与浏览器可用性
    print("DEFAULT_CARD_SIZE:", DEFAULT_CARD_SIZE, "DEFAULT_SLICE_HEIGHT:", DEFAULT_SLICE_HEIGHT)
    print("parseSize('1080x1440'):", parseSize("1080x1440"))
    print("inlineLocalImages:", inlineLocalImages('<img src="d:/tmp/none.jpg"/>'))
    print("browser available:", isBrowserAvailable())
    closeBrowser()
