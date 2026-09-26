#! /usr/bin/env python3
#encoding: utf-8

#Filename: base.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 平台适配器抽象基类与统一契约(SP3a · C5 平台适配层, 主计划 2.5)。

#职责: 以统一抽象基类约定所有平台能力, 隔离平台差异。**五个方法即契约**:
#   render      形态转换: 引擎产物 -> 平台形态产物(如公众号内联样式 HTML)
#   validate    平台规格校验: 标题/摘要上限、封面规格、正文图规格、图片数量上限(数据源 ch_platform)
#   package     产物打包规划: 素材包/草稿载荷的结构化清单(不落盘)
#   deliver     投递通道: ★ 默认实现**一律返回「未实现」显式错误(C2)**; SP4a 起仅 wechat_mp(draft_box)
#               覆写本方法实现「通道调用」, 小红书/通用仍走默认实现(小红书平台红线: 不投递/不发布);
#               **业务编排(幂等/二次确认/撤销窗/合规/落库/审计)一律在 processor/publishService.py**
#   checkHealth 凭据/账号健康: 只读 ch_account 与配置态, **不发任何网络请求**
#
#★ 设计要点(主计划 2.5): 适配器只做「形态转换 + 通道调用」, 业务编排留在 processor/renderService.py;
#  新增平台只需「加一个适配器 + 一条 ch_platform 记录」, 不改主干(注册表见 ADAPTER_MODULE_MAP)。
#
#★ 分层契约(强制单向): 本包属业务处理器层(processor/), 只可依赖 engine/ 与 common/;
#  **严禁 import main/subfunc**(接入层); 引擎层(engine/)亦不得反向 import 本包。
#
#★ 零网络红线(SP3a): 本轮不调任何平台接口、不做图片转存、不做投递; 需要凭据的能力一律显式报错。
#
#★ 本文件刻意只依赖标准库(abc/json/os/re/sys), 以便 test/test_ch_phase0_static.py 在
#  「不安装第三方依赖」的前提下直接 exec 其源码, 对契约与规格校验做真行为断言(S23)。
#
#错误码(contenthub msgKey; 渲染/产物类一律 E 段, 不占用 C*/D*/F*/G* 段 —— 见 code/src/plan.md §4):
#  C2 deliver 未实现(投递归 SP4) | C4 必填缺失 | C5 字段超长 | C6 数值越界/超上限
#  C7 取值非法(平台已停用/无适配器) | CB 无此记录 | D1 图片尺寸不符平台规格
#  E1 渲染失败(适配器渲染/读取异常) | E4 外链图片需转存但凭据缺失
#
#「0 = 未设置」约定: ch_platform 的可空数值列(生成器对异常值置 0)一律按 0 = 未设置/不限制处理。

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

import abc


#===== 错误码 begin =====

ERR_OK = "B0"
ERR_NOT_IMPLEMENTED = "C2"           #★ deliver 未实现(投递归 SP4)
ERR_FIELD_MISSING = "C4"
ERR_FIELD_TOO_LONG = "C5"
ERR_FIELD_OUT_OF_RANGE = "C6"
ERR_FIELD_INVALID = "C7"
ERR_NO_RECORD = "CB"
ERR_IMAGE_SPEC = "D1"                #图片尺寸不符合平台规格
ERR_RENDER_FAILED = "E1"
ERR_IMAGE_TRANSFER_REQUIRED = "E4"   #外链图片需转存但凭据缺失(与 engine/inlineStyle.py 同码)

#===== 错误码 end =====


#===== 平台能力默认值 begin =====

#ch_platform 缺失/异常时的兜底(「0 = 未设置」: titleMaxLen/summaryMaxLen/imageMaxCount 为 0 视为不限制)
DEFAULT_TITLE_MAX_LEN = 64
DEFAULT_SUMMARY_MAX_LEN = 200
DEFAULT_IMAGE_MAX_COUNT = 20

#适配器注册表: platformCode -> (模块路径, 类名)。新增平台只在此追加一条 + 新增 ch_platform 记录。
#★ SP3b: 小红书(xiaohongshu)适配器已登记(SP3a 时为显式 C7)。它**只做形态转换(卡片/长图切分)与素材包清单**,
#  deliverMode=asset_pack, **不含任何自动发布/投递路径**(平台红线: 不得引入小红书自动发布任何代码路径)。
ADAPTER_MODULE_MAP = {
    "wechat_mp":   ("processor.platformAdapter.wechatMp", "WechatMpAdapter"),
    "generic":     ("processor.platformAdapter.generic", "GenericAdapter"),
    "xiaohongshu": ("processor.platformAdapter.xiaohongshu", "XiaohongshuAdapter"),
}

#===== 平台能力默认值 end =====


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


def _fieldLabel(fieldName, platformCode = ""):
    """字段名 + 位置(平台上下文), 用于错误提示「标明字段名与位置」"""
    if platformCode:
        return f"{fieldName}(ch_platform:{platformCode})"
    return f"{fieldName}(platformAdapter)"


def _ok(data = None, errMsgList = None):
    return {"errCode": ERR_OK, "field": "", "errMsgList": errMsgList or [], "data": data or {}}


def _err(errCode, rtnField, errMsgList = None, data = None):
    return {"errCode": errCode, "field": rtnField, "errMsgList": errMsgList or [], "data": data or {}}


def parseSizeSpec(sizeSpec, default = (0, 0)):
    """把 '900x500' / '1080*1440' / (1080,1440) 解析为 (width, height); 非法回落 default"""
    if isinstance(sizeSpec, (tuple, list)) and len(sizeSpec) == 2:
        try:
            return int(sizeSpec[0]), int(sizeSpec[1])
        except Exception:
            return default
    text = _toStr(sizeSpec).lower().replace("*", "x").replace("X", "x")
    if "x" in text:
        parts = text.split("x")
        if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
            return int(parts[0]), int(parts[1])
    return default

#===== 通用小工具 end =====


#===== 异常 begin =====

class PlatformAdapterError(Exception):
    """平台适配器异常: 携带 contenthub 错误码, 由业务层(renderService)映射为 HTTP 报文"""
    def __init__(self, errCode, message, field = ""):
        super().__init__(message)
        self.errCode = errCode
        self.field = field
        self.message = message

#===== 异常 end =====


#===== 平台记录归一 + 规格校验(纯函数, 供所有适配器复用) begin =====

def normalizePlatformRecord(platformRecord):
    """把 ch_platform 记录归一为适配器可消费的 dict(缺失列回落默认; 「0 = 未设置」)"""
    record = platformRecord if isinstance(platformRecord, dict) else {}
    normalized = {
        "platformCode": _toStr(record.get("platformCode")),
        "platformName": _toStr(record.get("platformName")),
        "deliverMode": _toStr(record.get("deliverMode")),
        "subjectScope": _toStr(record.get("subjectScope")),
        "titleMaxLen": _toInt(record.get("titleMaxLen"), DEFAULT_TITLE_MAX_LEN),
        "summaryMaxLen": _toInt(record.get("summaryMaxLen"), DEFAULT_SUMMARY_MAX_LEN),
        "coverSpec": _toStr(record.get("coverSpec")),
        "imageSpec": _toStr(record.get("imageSpec")),
        "imageMaxCount": _toInt(record.get("imageMaxCount"), DEFAULT_IMAGE_MAX_COUNT),
        "allowSvgFlag": _toStr(record.get("allowSvgFlag")) or "0",
        "needAiLabelFlag": _toStr(record.get("needAiLabelFlag")) or "0",
        "autoPublishFlag": _toStr(record.get("autoPublishFlag")) or "0",
        "limitNote": _toStr(record.get("limitNote")),
        "docUrl": _toStr(record.get("docUrl")),
        "enabled": _toStr(record.get("enabled")) or "1",
    }
    return normalized


def _findCoverAsset(assetList):
    """找出封面绑定(usageType=cover); 未命中返回 None"""
    for item in assetList or []:
        if isinstance(item, dict) and _toStr(item.get("usageType")).lower() == "cover":
            return item
    return None


def checkPlatformSpec(platformRecord, topicData, assetList):
    """★ 平台规格校验(数据驱动, 新增平台无需改代码 —— 规则全部来自 ch_platform 记录):
         - 标题: 必填 + 长度上限(titleMaxLen)
         - 摘要: 长度上限(summaryMaxLen)
         - 封面: coverSpec(如 900x500)与封面图实际尺寸一致
         - 正文图: imageSpec(如 1080x1440)与正文图实际尺寸一致(未知尺寸不误报)
         - 图片数量: ≤ imageMaxCount
       出参: {"errCode","field","errMsgList","data":{"issues":[...], "platformCode":...}}
       说明: 只对「已知尺寸」做规格判定(尺寸未知无从校验, 交由渲染期 imageProc 派生后再验)。"""
    normalized = normalizePlatformRecord(platformRecord)
    topicData = topicData if isinstance(topicData, dict) else {}
    assetList = assetList if isinstance(assetList, (list, tuple)) else []
    platformCode = normalized.get("platformCode")

    errList = []
    issues = []

    def addIssue(errCode, fieldName, message):
        errList.append((errCode, fieldName, message))
        issues.append({"errCode": errCode, "field": fieldName, "message": message})

    #1) 标题(必填 + 上限)
    title = _toStr(topicData.get("title"))
    titleMaxLen = _toInt(normalized.get("titleMaxLen"), 0)
    if not title:
        addIssue(ERR_FIELD_MISSING, _fieldLabel("title", platformCode), "title 为必填字段")
    elif titleMaxLen > 0 and len(title) > titleMaxLen:
        addIssue(ERR_FIELD_TOO_LONG, _fieldLabel("title", platformCode),
                 f"title 长度={len(title)} 超平台上限 {titleMaxLen}")

    #2) 摘要(上限)
    summary = _toStr(topicData.get("summary"))
    summaryMaxLen = _toInt(normalized.get("summaryMaxLen"), 0)
    if summary and summaryMaxLen > 0 and len(summary) > summaryMaxLen:
        addIssue(ERR_FIELD_TOO_LONG, _fieldLabel("summary", platformCode),
                 f"summary 长度={len(summary)} 超平台上限 {summaryMaxLen}")

    #3) 封面规格(coverSpec 非空且封面尺寸已知时才判定)
    coverSpecWidth, coverSpecHeight = parseSizeSpec(normalized.get("coverSpec"))
    if coverSpecWidth > 0 and coverSpecHeight > 0:
        coverAsset = _findCoverAsset(assetList)
        if coverAsset:
            coverWidth = _toInt(coverAsset.get("width"), 0)
            coverHeight = _toInt(coverAsset.get("height"), 0)
            if coverWidth > 0 and coverHeight > 0 and (coverWidth, coverHeight) != (coverSpecWidth, coverSpecHeight):
                addIssue(ERR_IMAGE_SPEC, _fieldLabel("coverSpec", platformCode),
                         f"封面尺寸 {coverWidth}x{coverHeight} 与平台规格 {coverSpecWidth}x{coverSpecHeight} 不一致"
                         f"(须由渲染期 imageProc 派生归一)")

    #4) 正文图规格(imageSpec 非空且尺寸已知时才判定)
    imageSpecWidth, imageSpecHeight = parseSizeSpec(normalized.get("imageSpec"))
    if imageSpecWidth > 0 and imageSpecHeight > 0:
        for idx, item in enumerate(assetList):
            if not isinstance(item, dict):
                continue
            if _toStr(item.get("usageType")).lower() == "cover":
                continue
            width = _toInt(item.get("width"), 0)
            height = _toInt(item.get("height"), 0)
            if width > 0 and height > 0 and (width, height) != (imageSpecWidth, imageSpecHeight):
                addIssue(ERR_IMAGE_SPEC, _fieldLabel("imageSpec", platformCode),
                         f"第 {idx + 1} 张正文图尺寸 {width}x{height} 与平台规格 "
                         f"{imageSpecWidth}x{imageSpecHeight} 不一致(须由渲染期 imageProc 派生归一)")

    #5) 图片数量上限
    imageMaxCount = _toInt(normalized.get("imageMaxCount"), 0)
    if imageMaxCount > 0 and len(assetList) > imageMaxCount:
        addIssue(ERR_FIELD_OUT_OF_RANGE, _fieldLabel("imageMaxCount", platformCode),
                 f"图片数 {len(assetList)} 超平台上限 {imageMaxCount}")

    data = {"platformCode": platformCode, "issues": issues, "issueCount": len(issues)}
    if errList:
        errCode, rtnField, _message = errList[0]
        return _err(errCode, rtnField, [item[2] for item in errList], data)

    return _ok(data)

#===== 平台记录归一 + 规格校验 end =====


#===== 适配器抽象基类 begin =====

class PlatformAdapter(abc.ABC):
    """平台适配器抽象基类(契约五方法)。

       子类须声明:
         platformCode   平台编码(与 ch_platform.platformCode 一致)
         deliverMode    投递形态(draft_box / asset_pack / api_publish)
       并实现 render / package / checkHealth; validate 有默认实现(走 ch_platform 数据驱动校验)。
       deliver 由基类实现: ★ 本轮一律显式返回「未实现」(C2), 投递归 SP4。
    """

    platformCode = ""
    deliverMode = ""

    def __init__(self, platformRecord = None):
        self.platformRecord = normalizePlatformRecord(platformRecord)
        if not self.platformRecord.get("platformCode"):
            self.platformRecord["platformCode"] = self.platformCode

    #----- ch_platform 能力只读视图(「0 = 未设置」) -----

    @property
    def titleMaxLen(self):
        return _toInt(self.platformRecord.get("titleMaxLen"), DEFAULT_TITLE_MAX_LEN)

    @property
    def summaryMaxLen(self):
        return _toInt(self.platformRecord.get("summaryMaxLen"), DEFAULT_SUMMARY_MAX_LEN)

    @property
    def coverSpec(self):
        return _toStr(self.platformRecord.get("coverSpec"))

    @property
    def imageSpec(self):
        return _toStr(self.platformRecord.get("imageSpec"))

    @property
    def imageMaxCount(self):
        return _toInt(self.platformRecord.get("imageMaxCount"), DEFAULT_IMAGE_MAX_COUNT)

    @property
    def allowSvgFlag(self):
        return _toStr(self.platformRecord.get("allowSvgFlag")) or "0"

    #----- 契约五方法 -----

    @abc.abstractmethod
    def render(self, topicData, layoutRecord, assetList, overrideSpec = None, options = None):
        """形态转换: 引擎产物 -> 平台形态产物; 出参 {"errCode","field","errMsgList","data":{...}}"""
        raise NotImplementedError

    def validate(self, topicData, assetList, platformRecord = None):
        """平台规格校验(默认实现: ch_platform 数据驱动); 子类可叠加专属规则"""
        record = platformRecord if isinstance(platformRecord, dict) else self.platformRecord
        return checkPlatformSpec(record, topicData, assetList)

    @abc.abstractmethod
    def package(self, renderResult, topicData, assetList, options = None):
        """产物打包规划(本轮只出结构化清单, 不落盘; ZIP/草稿载荷归 SP4)"""
        raise NotImplementedError

    def deliver(self, packageResult = None, options = None):
        """★ 投递通道(默认实现): 未实现投递的平台**一律显式返回未实现(C2)**, 不得静默成功。
           SP4a 起只有 wechat_mp(draft_box)覆写本方法(通道调用); 小红书/通用继续走此默认实现 ——
           小红书为平台红线: **不投递、不发布**(只导出素材包)。"""
        return _err(ERR_NOT_IMPLEMENTED, _fieldLabel("deliver", self.platformCode), [
            f"平台投递通道尚未实现: platformCode={self.platformCode}, "
            f"deliverMode={self.deliverMode or self.platformRecord.get('deliverMode')}"
        ])

    @abc.abstractmethod
    def checkHealth(self, sessionIDSet = None):
        """凭据/账号健康: 本轮只读 ch_account 与配置态, 不发任何网络请求"""
        raise NotImplementedError

#===== 适配器抽象基类 end =====


#===== 适配器工厂 begin =====

def listAdapterCodes():
    """已注册适配器清单(诊断/错误提示用; 新增平台只加一条 ch_platform 记录 + 一个适配器)"""
    return sorted(ADAPTER_MODULE_MAP.keys())


def getAdapter(platformCode, platformRecord = None):
    """按 platformCode 取适配器实例(延迟导入具体适配器, 避免包内循环依赖; 未注册返回 None)"""
    platformCode = _toStr(platformCode)
    entry = ADAPTER_MODULE_MAP.get(platformCode)
    if not entry:
        return None

    moduleName, className = entry
    module = __import__(moduleName, fromlist = [className])
    adapterClass = getattr(module, className)
    return adapterClass(platformRecord)

#===== 适配器工厂 end =====


if __name__ == "__main__":
    pass
    #本地自测(不连库/不联网): 只验证纯函数与契约
    print("adapters:", listAdapterCodes())
    print("parseSizeSpec('900x500'):", parseSizeSpec("900x500"))
    print("checkPlatformSpec(empty):", checkPlatformSpec({}, {}, [])["errCode"])
    print("deliver:", PlatformAdapter.__dict__["deliver"])
