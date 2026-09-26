#! /usr/bin/env python3
#encoding: utf-8

#Filename: inlineStyle.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 微信内联化公共件(SP3a · C5 平台适配层, 主计划 P2-2)。

#职责(把已渲染的 HTML 片段转成「公众号正文可用」的形态):
#  1) 全量内联样式化: 把模板里 <style> 块中依赖选择器的样式全部下沉为元素内联 style
#     (微信会清洗 class 与 <style>, 只认元素内联样式);
#  2) class 清洗: 输出 HTML 不残留任何 class 依赖(可保留无害的 data-* 属性);
#  3) 外链图片策略: resolveImageUrl(...) 为**统一出口** ——
#       已是平台可显示地址 -> 原样返回; 需转存(非平台显示域)且本轮无凭据 -> 显式返回 E4,
#       **绝不静默保留外链**(实际转存归 SP4, 凭据就绪后在此接上);
#  4) 交互降级: carousel 的自实现交互(script/翻页按钮)在平台不允许脚本时降级为
#     **复用 SP2c 已产出的静态图集兜底节点**(公众号对 SVG/脚本兼容不稳)。

#★ 分层契约(强制单向): 本文件属引擎层(engine/), 只允许标准库依赖;
#  **不得 import processor/ 或 subfunc/**(引擎层不反向依赖业务层/接入层);
#  平台差异(显示域白名单等)一律由**适配器**以参数传入, 本文件不硬编码任何平台专属域名(plan.md §4 模板约定)。
#
#★ 零网络红线(SP3a): 本文件不做任何网络请求、不做图片转存; 需要凭据的能力一律显式报错。
#
#错误码(contenthub msgKey; 渲染/产物类一律 E 段):
#  E1 渲染失败(输入为空/内部异常) | E4 外链图片需转存但凭据缺失
#
#说明: 本模块刻意只依赖标准库(re/os/sys), 以便 test/test_ch_phase0_static.py 在
#      「不安装第三方依赖」的前提下直接 exec 其源码做行为断言(S23)。

_VERSION="20260919"


import os
import sys

try:
    _srcDir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # .../code/src
    if _srcDir not in sys.path:
        sys.path.insert(0, _srcDir)
except NameError:
    #被 exec(compile(source)) 到隔离命名空间时可能没有 __file__; 本模块不依赖项目模块, 直接跳过
    pass

import re


#===== 常量与错误码 begin =====

#错误码落点(common/errMsgCommon.py::_CH_ERROR_WORD 的 contenthub E 段, 渲染与产物)
ERR_RENDER_FAILED = "E1"                 #渲染失败(输入为空等)
ERR_IMAGE_TRANSFER_REQUIRED = "E4"       #外链图片需转存但凭据缺失(绝不静默保留外链)

#平台「可显示地址」通配符: 适配器用 ["*"] 表示「任意 http(s) 均可显示」(通用形态)
ANY_HOST_TOKEN = "*"

#===== 常量与错误码 end =====


#===== 通用小工具 begin =====

def _toStr(value):
    """None/数字/任意 -> 去空白字符串"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _fieldLabel(fieldName, platformCode = ""):
    """字段名 + 位置(适配器上下文), 用于错误提示「标明字段名与位置」"""
    if platformCode:
        return f"{fieldName}(platform:{platformCode})"
    return f"{fieldName}(inlineStyle)"


def _err(errCode, rtnField, errMsgList = None, data = None):
    return {"errCode": errCode, "field": rtnField, "errMsgList": errMsgList or [], "data": data or {}}


def _ok(data = None, errMsgList = None):
    return {"errCode": "B0", "field": "", "errMsgList": errMsgList or [], "data": data or {}}

#===== 通用小工具 end =====


#===== 正则 begin =====

_STYLE_BLOCK_PATTERN = re.compile(r"<style\b[^>]*>(.*?)</style>", re.IGNORECASE | re.DOTALL)
_CSS_COMMENT_PATTERN = re.compile(r"/\*.*?\*/", re.DOTALL)
_CSS_RULE_PATTERN = re.compile(r"([^{}]+)\{([^{}]*)\}")
_IMG_TAG_PATTERN = re.compile(r"<img\b[^>]*?/?>", re.IGNORECASE | re.DOTALL)
_IMG_SRC_PATTERN = re.compile(r"<img\b[^>]*?\bsrc\s*=\s*(\"([^\"]*)\"|'([^']*)')", re.IGNORECASE | re.DOTALL)
_STYLE_ATTR_PATTERN = re.compile(r"""style\s*=\s*("([^"]*)"|'([^']*)')""", re.IGNORECASE)
_CLASS_ATTR_PATTERN = re.compile(r"""\s+class\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""", re.IGNORECASE)
_CLASS_TOKEN_PATTERN = re.compile(r"""\bclass\s*=""", re.IGNORECASE)
_SCRIPT_BLOCK_PATTERN = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)

#carousel 版式的交互节点与静态兜底节点(SP2c 模板固定产出, data-* 即契约):
#  交互节点以 data-interactive="1" 唯一定位(避免降级后给兜底节点补 data-layout 时被误匹配)
_INTERACTIVE_SECTION_PATTERN = re.compile(
    r'<section\b[^>]*data-interactive="1"[^>]*>.*?</section>', re.IGNORECASE | re.DOTALL)
_FALLBACK_SECTION_PATTERN = re.compile(
    r'<section\b[^>]*data-carousel-fallback="static"[^>]*>.*?</section>', re.IGNORECASE | re.DOTALL)
_OPENING_TAG_PATTERN = re.compile(r"(<section\b[^>]*?)(/?>)", re.IGNORECASE | re.DOTALL)

#===== 正则 end =====


#===== style 属性合并 begin =====

def mergeStyleDecls(existingStyle, extraDecls):
    """把 extraDecls 合并进已有 style 串(按属性名去重, 不覆盖既有声明); 返回合并后的 style 串"""
    existingStyle = _toStr(existingStyle).rstrip(";")
    haveSet = set()
    for part in existingStyle.split(";"):
        if ":" in part:
            haveSet.add(part.split(":", 1)[0].strip().lower())

    extraList = []
    for part in _toStr(extraDecls).split(";"):
        part = part.strip()
        if not part or ":" not in part:
            continue
        name = part.split(":", 1)[0].strip().lower()
        if name in haveSet:
            continue
        haveSet.add(name)
        extraList.append(part)

    if not extraList:
        return existingStyle
    if existingStyle:
        return existingStyle + ";" + ";".join(extraList)
    return ";".join(extraList)

#===== style 属性合并 end =====


#===== <style> 下沉内联 begin =====

def collectSinkableRules(html):
    """收集可下沉的 CSS 规则。入参: HTML 串; 出参: (imgDeclsList, droppedRuleCount)。
       只支持「选择器全部指向 img」的规则(如 [data-layout="stack_v1"] img{max-width:100%});
       其余选择器(伪元素/复杂后代选择器)无法安全内联, 计入 droppedRuleCount 后丢弃。"""
    imgDeclsList = []
    droppedRuleCount = 0

    for styleBody in _STYLE_BLOCK_PATTERN.findall(html):
        body = _CSS_COMMENT_PATTERN.sub("", styleBody)
        for selector, decls in _CSS_RULE_PATTERN.findall(body):
            selector = selector.strip()
            decls = decls.strip()
            if not decls:
                continue
            parts = [seg.strip() for seg in selector.split(",") if seg.strip()]
            if parts and all("img" in seg.lower() and "::" not in seg for seg in parts):
                imgDeclsList.append(decls)
            else:
                droppedRuleCount += 1

    return imgDeclsList, droppedRuleCount


def _sinkImgStyle(tagHtml, decls):
    """把 decls 合并进单个 <img> 标签的 style 属性(无则新增)"""
    matched = _STYLE_ATTR_PATTERN.search(tagHtml)
    if matched:
        existing = matched.group(2) if matched.group(2) is not None else matched.group(3)
        merged = mergeStyleDecls(existing, decls)
        return tagHtml[:matched.start()] + f'style="{merged}"' + tagHtml[matched.end():]

    if tagHtml.endswith("/>"):
        return tagHtml[:-2].rstrip() + f' style="{decls}"/>'
    return tagHtml[:-1].rstrip() + f' style="{decls}">'


def inlineCss(html):
    """把 <style> 块中指向 img 的样式下沉为元素内联 style, 并移除 <style> 块。
       出参: (html, droppedRuleCount)。说明: 移除 <style> 是因为微信会清洗样式表, 保留无意义。"""
    html = html if isinstance(html, str) else ""
    imgDeclsList, droppedRuleCount = collectSinkableRules(html)

    if imgDeclsList:
        combined = ";".join(imgDeclsList)

        def _replaceImg(matched):
            return _sinkImgStyle(matched.group(0), combined)

        html = _IMG_TAG_PATTERN.sub(_replaceImg, html)

    html = _STYLE_BLOCK_PATTERN.sub("", html)
    return html, droppedRuleCount

#===== <style> 下沉内联 end =====


#===== class 清洗 begin =====

def stripClassAttributes(html):
    """清除全部 class="..." 属性(微信会清洗 class; 布局一律靠内联 style + data-* 表达)"""
    html = html if isinstance(html, str) else ""
    return _CLASS_ATTR_PATTERN.sub("", html)


def hasClassDependency(html):
    """判断 HTML 是否仍残留 class 依赖(供断言/诊断)"""
    html = html if isinstance(html, str) else ""
    return bool(_CLASS_TOKEN_PATTERN.search(html))

#===== class 清洗 end =====


#===== 交互降级(carousel -> 静态图集兜底) begin =====

def stripScriptBlocks(html):
    """移除全部 <script>...</script>(平台不允许脚本时的降级动作)"""
    html = html if isinstance(html, str) else ""
    return _SCRIPT_BLOCK_PATTERN.sub("", html)


def _markDegradedFallbackTag(sectionHtml):
    """给静态兜底节点的开标签补上降级标记(保留原 data-carousel-fallback 以便溯源)"""
    matched = _OPENING_TAG_PATTERN.match(sectionHtml)
    if not matched:
        return sectionHtml
    openingTag = matched.group(1)
    if "data-degraded" not in openingTag:
        openingTag += ' data-layout="carousel_v1" data-interactive="0" data-degraded="static_fallback"'
    return openingTag + matched.group(2) + sectionHtml[matched.end():]


def degradeCarouselInteraction(html):
    """carousel 交互节点降级(主计划 P2-2):
       移除自实现交互(script / 翻页按钮所在节点), **复用 SP2c 已产出的静态图集兜底节点**
       (data-carousel-fallback="static")作为可见内容, 并把它标记为 carousel 根节点。
       出参: (html, degradedFlag)。非 carousel 内容原样返回。"""
    html = html if isinstance(html, str) else ""
    if "data-carousel-slide" not in html:
        return html, False

    content = html

    #1) 先移除交互节点(自实现交互 + 翻页按钮 + script 都在其中):
    #   必须在给兜底节点补 data-layout="carousel_v1" 之前完成, 否则会被交互选择器误匹配。
    interactiveMatch = _INTERACTIVE_SECTION_PATTERN.search(content)
    if interactiveMatch:
        content = content[:interactiveMatch.start()] + content[interactiveMatch.end():]

    #2) 复用 SP2c 已产出的静态图集兜底节点, 并标记其为降级(carousel)根节点
    fallbackMatch = _FALLBACK_SECTION_PATTERN.search(content)
    if fallbackMatch:
        markedFallback = _markDegradedFallbackTag(fallbackMatch.group(0))
        content = content[:fallbackMatch.start()] + markedFallback + content[fallbackMatch.end():]

    #3) 兜底: 无论走哪条路径, 平台不允许脚本时输出都不得残留 <script>
    content = stripScriptBlocks(content)
    return content, True

#===== 交互降级 end =====


#===== 外链图片策略(统一出口) begin =====

def extractHost(url):
    """从 http(s) URL 中取出 host(小写, 去端口); 非法返回 \"\""""
    text = _toStr(url)
    matched = re.match(r"^https?://([^/?#]+)", text, re.IGNORECASE)
    if not matched:
        return ""
    host = matched.group(1).split("@")[-1].split(":")[0].strip().lower()
    return host


def resolveImageUrl(imageUrl, displayHostList = None, allowAnyHost = False, transferFunc = None):
    """★ 外链图片统一出口(主计划 P2-2; SP4a 补齐「真实转存」分支):
         - 空串                       -> B0(原样)
         - 非 http(s)(相对/本地/fileID) -> B0 但标记 needUpload(不属「外链」范畴, 由上传链路处理)
         - http(s) 且 host 在平台显示域 -> B0(原样)
         - http(s) 且需转存:
             · transferFunc 就绪(SP4a 凭据就绪, 由适配器/业务层注入) -> 调用转存并返回**平台地址**(B0);
             · transferFunc 缺失/抛异常 -> E4(显式报错, **绝不静默保留外链**)
       入参 displayHostList 由**适配器**提供(平台差异不在本文件硬编码); allowAnyHost=True 时任意 http(s) 均视为可显示;
            transferFunc 由**业务层/适配器**注入(引擎层只回调, 不自行发起网络请求 —— 保持本文件仅标准库依赖)。
       出参: {"errCode","field","errMsgList","url","host","needTransfer","needUpload","transferred","reason"}"""
    url = _toStr(imageUrl)
    result = {"errCode": "B0", "field": "", "errMsgList": [], "url": url, "host": "",
              "needTransfer": False, "needUpload": False, "transferred": False, "reason": ""}

    if not url:
        return result

    lowerUrl = url.lower()
    if not (lowerUrl.startswith("http://") or lowerUrl.startswith("https://")):
        #非 http(s): 相对路径/本地路径/裸 fileID —— 不属于外链策略范畴, 交由上传链路处理, 不阻断
        result["needUpload"] = True
        result["reason"] = "非 http(s) 地址(本地/相对路径或 fileID), 待上传链路处理"
        return result

    host = extractHost(url)
    result["host"] = host

    if allowAnyHost:
        return result

    hostList = [(_toStr(item)).lower() for item in (displayHostList or []) if _toStr(item)]
    if ANY_HOST_TOKEN in hostList:
        return result
    if host and host in hostList:
        return result

    #非平台显示域 -> 需转存
    result["needTransfer"] = True
    if transferFunc is not None:
        #★ SP4a 真实转存分支: 回调由业务层/适配器提供(引擎层不发起网络请求)
        try:
            newUrl = _toStr(transferFunc(url))
        except Exception as e:
            newUrl = ""
            transferErr = str(e)
        else:
            transferErr = ""
        if newUrl:
            result["url"] = newUrl
            result["transferred"] = True
            result["reason"] = f"外链图片已转存至平台(host={extractHost(newUrl) or 'unknown'})"
            return result
        result["errCode"] = ERR_IMAGE_TRANSFER_REQUIRED
        result["field"] = _fieldLabel("fileUrl")
        result["reason"] = f"外链图片转存失败(host={host or 'unknown'}): {transferErr or '转存未返回地址'}"
        result["errMsgList"] = [
            f"外链图片需转存至平台但转存失败: {url} (允许显示域={hostList}); "
            f"原因:{transferErr or '转存未返回地址'}; 绝不静默保留外链"
        ]
        return result

    result["errCode"] = ERR_IMAGE_TRANSFER_REQUIRED
    result["field"] = _fieldLabel("fileUrl")
    result["reason"] = f"外链图片需转存至平台(host={host or 'unknown'}), 凭据/转存通道缺失"
    result["errMsgList"] = [
        f"外链图片需转存至平台但凭据缺失: {url} (允许显示域={hostList}); 不静默保留外链"
    ]
    return result


def extractImageSrcList(html):
    """提取 HTML 中所有 <img src="..."> 的地址(保持出现顺序)"""
    html = html if isinstance(html, str) else ""
    srcList = []
    for matched in _IMG_SRC_PATTERN.finditer(html):
        src = matched.group(2) if matched.group(2) is not None else matched.group(3)
        srcList.append(src)
    return srcList

#===== 外链图片策略 end =====


#===== 统一出口 begin =====

def inlineHtml(html, displayHostList = None, degradeInteraction = False, allowAnyHost = False, transferFunc = None):
    """★ 统一出口: class 清洗 + <style> 下沉内联 + 外链图片策略 + (可选)carousel 交互降级。
       出参: {"errCode","field","errMsgList","data":{"content","imageCount","needUploadCount",
              "transferredImageCount","degraded","droppedRuleCount","classDependency","transferRequired"}}。
       - transferFunc 就绪时: 外链图片经回调转存并把 src **替换为平台地址**(SP4a 真实转存分支);
       - 转存失败或未注入 transferFunc: 整体返回 E4, 不返回内容(绝不静默保留外链)。"""
    content = html if isinstance(html, str) else ""
    if not content.strip():
        return _err(ERR_RENDER_FAILED, _fieldLabel("content"), ["内联化输入为空"])

    degraded = False
    if degradeInteraction:
        content, degraded = degradeCarouselInteraction(content)

    content, droppedRuleCount = inlineCss(content)
    content = stripClassAttributes(content)

    imageCount = 0
    needUploadCount = 0
    transferredCount = 0
    for src in extractImageSrcList(content):
        rtn = resolveImageUrl(src, displayHostList = displayHostList, allowAnyHost = allowAnyHost,
                              transferFunc = transferFunc)
        if rtn.get("errCode") != "B0":
            return _err(rtn.get("errCode"), rtn.get("field"),
                        rtn.get("errMsgList"), {"transferRequired": src, "host": rtn.get("host", "")})
        newUrl = _toStr(rtn.get("url"))
        if rtn.get("transferred") and newUrl and newUrl != src:
            content = content.replace(src, newUrl)
            transferredCount += 1
        imageCount += 1
        if rtn.get("needUpload"):
            needUploadCount += 1

    data = {
        "content": content,
        "imageCount": imageCount,
        "needUploadCount": needUploadCount,
        "transferredImageCount": transferredCount,
        "degraded": degraded,
        "droppedRuleCount": droppedRuleCount,
        "classDependency": hasClassDependency(content),
    }
    return _ok(data)

#===== 统一出口 end =====


if __name__ == "__main__":
    pass
    #本地自测(不连库/不联网): 只验证纯函数
    print("resolveImageUrl mmbiz:", resolveImageUrl("https://mmbiz.qpic.cn/a.jpg", ["mmbiz.qpic.cn"])["errCode"])
    print("resolveImageUrl external:", resolveImageUrl("https://example.com/a.jpg", ["mmbiz.qpic.cn"])["errCode"])
    print("resolveImageUrl local:", resolveImageUrl("d:/tmp/a.jpg", ["mmbiz.qpic.cn"])["errCode"])
    _sample = '<style>[data-layout="stack_v1"] img{max-width:100%;}</style><p class="x"><img class="c" src="https://mmbiz.qpic.cn/a.jpg" style="width:100%;"/></p>'
    print("inlineHtml:", inlineHtml(_sample, ["mmbiz.qpic.cn"])["data"])
