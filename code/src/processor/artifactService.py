#! /usr/bin/env python3
#encoding: utf-8:

#Filename: artifactService.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub C6 素材包 ZIP 导出业务服务(SP4b · 主计划 5.5 P3-2 / 7.8 素材包合规验收 12 项)。

#职责(只做「素材包导出」, **绝不投递、绝不发布**):
#  1) 取数: 主题 + 附图 + 版式 + 平台(复用 processor/renderService.py 的既有取数实现, 不造第二份);
#  2) 产物来源: 优先调用方显式传入 products; 否则按 jobID / artifactID 列表取 ch_artifact 中
#     **READY** 的产物(swipe 卡片 / 长图切片), 逐张落本地(有 localPath 直接用, 否则经文件门面 download);
#  3) ★ 导出前**必须**复用 processor/complianceService.py 完成主计划 7.8 的自动可判定项校验
#     (图片数量 / 命名与顺序 / 比例统一 / 单张规格 / 超长图已切分 / 标题 / 正文 / AI 标识 / 敏感词);
#     **未过校验一律不出包**(不做任何降级/兜底导出);
#  4) 按 7.8 组装 ZIP: 有序图片(01_、02_…, 顺序即 App 内左右滑动浏览顺序) + title.txt + content.txt
#     (含 # 话题标签, 必要时正文尾部含 AI 创作标识) + manifest.json(主题编码/生成时间/版式/平台/文件清单与校验值)
#     + COPYRIGHT.txt(来源/时期 + 版权提示) + RISK_NOTICE.txt(风险告知) + SWIPE_TIPS.txt(滑动可用性提示);
#  5) ZIP 经 common/fileStorageCommon.py 上传返回 fileID(红线 R2; 出参经 chCommon.fillFileUrls 转 URL)。
#
#★ 规则单一来源(硬约束): 平台规格与 swipe 专项一律**复用** complianceService(其内部再复用
#  base.checkPlatformSpec / xiaohongshu.validateSwipeSpec); 本文件**不重写任何规格/合规规则**,
#  也不重复实现素材包清单 —— 清单/manifest 草稿复用适配器的 package()(SP3b 已产出)。
#
#★ 投递红线: 本文件**不含任何投递/发布调用**(无 deliver / publishService / freepublish / draft_add);
#  小红书素材包只导出, 由用户手动在官方创作服务平台发布。
#
#★ 分层契约(强制单向): 接入层(main/) -> 业务层(processor/) -> 引擎层(engine/) -> 公共层(common/);
#  本文件属业务处理器层, 只依赖 processor/ 同层、engine/ 与 common/; **严禁 import main/subfunc**。
#
#★ 错误码(contenthub msgKey; 见 code/src/plan.md §4): 素材包属 D/E 段语义(C4 必填 / C7 取值非法 /
#  CB 无此记录 / D3 上传失败 / D4 文件不存在 / E3 ZIP 生成失败), 合规不通过则**透传** complianceService 的原始错误码。

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

import hashlib
import json
import re
import shutil
import tempfile
import traceback
import zipfile

#global defintion/common var etc.
from common import globalDefinition as comGD

#common functions(log,time,string, json etc)
from common import miscCommon as misc

#数据层唯一入口(红线 R1): 本文件只读 ch_artifact / ch_topic / ch_layout / ch_platform
from common import mysqlCommon as comMysql

#跨域业务公共件(fileID -> URL)
from common import chCommon as comCh

#文件门面(红线 R2): ZIP 上传与产物下载的唯一出口(本文件不出现任何厂商分支)
from common import fileStorageCommon as comFS

#业务层同层服务(取主题/附图/版式/平台复用渲染编排既有实现; 合规校验复用 C8)
from processor import complianceService

from processor import renderService

#平台适配层: 素材包清单 / manifest 草稿复用适配器 package()(SP3b 已产出, 不在本文件重造)
from processor import platformAdapter

#引擎层: specJson 解析(与 topicrender 同一套键)
from engine import layoutEngine


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    try:
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None


#===== 错误码与常量 begin =====

ERR_OK = "B0"
ERR_FIELD_MISSING = "C4"
ERR_FIELD_INVALID = "C7"
ERR_NO_RECORD = "CB"
ERR_UPLOAD_FAILED = "D3"        #ZIP 上传失败
ERR_FILE_NOT_FOUND = "D4"       #产物文件不存在/取回失败
ERR_ARTIFACT_FAILED = "E3"      #ZIP 生成失败

#素材包平台(缺省小红书: 唯一素材包平台; 通用 HTML 亦为 asset_pack 但不产图集素材包)
DEFAULT_PLATFORM_CODE = "xiaohongshu"

#★ ZIP 内固定文本条目(主计划 7.8 第 3/4/6/7/8/11 项)
ZIP_ENTRY_TITLE = "title.txt"
ZIP_ENTRY_CONTENT = "content.txt"
ZIP_ENTRY_MANIFEST = "manifest.json"
ZIP_ENTRY_COPYRIGHT = "COPYRIGHT.txt"
ZIP_ENTRY_RISK_NOTICE = "RISK_NOTICE.txt"
ZIP_ENTRY_SWIPE_TIPS = "SWIPE_TIPS.txt"

ZIP_TEXT_ENTRY_LIST = [
    ZIP_ENTRY_TITLE, ZIP_ENTRY_CONTENT, ZIP_ENTRY_MANIFEST,
    ZIP_ENTRY_COPYRIGHT, ZIP_ENTRY_RISK_NOTICE, ZIP_ENTRY_SWIPE_TIPS,
]

#素材包所需文件条目清单(供静态验收 S27 与出参自描述; 图片条目动态追加在最前)
ZIP_STRUCTURE_SPEC = [
    {"item": "images", "desc": "有序图片(01_、02_…), 顺序即 App 内左右滑动浏览顺序, 与附图 sortOrder 一致"},
    {"item": ZIP_ENTRY_TITLE, "desc": "标题(<= ch_platform.titleMaxLen)"},
    {"item": ZIP_ENTRY_CONTENT, "desc": "正文(含 # 话题标签; aiFlag=1 且平台强制时尾部含 AI 创作标识)"},
    {"item": ZIP_ENTRY_MANIFEST, "desc": "主题编码/生成时间/版式/平台/文件清单与校验值(sha256)"},
    {"item": ZIP_ENTRY_COPYRIGHT, "desc": "来源/时期信息 + 版权提示"},
    {"item": ZIP_ENTRY_RISK_NOTICE, "desc": "风险告知(须在官方创作服务平台手动发布, 禁止第三方自动发布)"},
    {"item": ZIP_ENTRY_SWIPE_TIPS, "desc": "滑动可用性提示(图片显示区域内滑动; 老版本 App 需 8.0+)"},
]

#★ 风险告知文本(7.8 第 8 项; 素材包内必含, 一次定稿避免多处措辞漂移)
RISK_NOTICE_TEXT = (
    "【风险告知】\n"
    "1. 本素材包需在官方创作服务平台**手动发布**, 禁止第三方自动发布。\n"
    "2. 本工具仅生成素材(图片与文案), 不提供、也不允许任何自动发布/投递能力。\n"
    "3. 使用第三方自动发布工具可能导致账号被限流、禁言或封禁, 并连带矩阵账号, 请勿尝试。\n"
    "4. 请自行核对平台最新规则(图片数量 / 比例 / 大小可能随平台调整)。\n"
)

#★ 滑动可用性提示(7.8 第 11 项)
SWIPE_TIPS_TEXT = (
    "【滑动可用性提示】\n"
    "1. 滑动浏览须在**图片显示区域内**操作: 标题栏、评论区等区域的滑动无效。\n"
    "2. 原生左右滑动手势需小红书 App **8.0 及以上**版本; 老版本请左右点击图片切换。\n"
    "3. 图片顺序即 App 内左右滑动浏览顺序, 请勿调整 ZIP 内图片文件名顺序。\n"
)

#★ 版权提示模板(7.8 第 7 项; 来源/时期取自主题记录, 缺失时给出提示语)
COPYRIGHT_TEMPLATE = (
    "【版权提示】\n"
    "内容来源: {source}\n"
    "内容时期: {period}\n"
    "作者/署名: {author}\n"
    "生成工具: contentHub 内容中枢(素材包导出)\n"
    "说明: 以上信息由主题记录带入, 请核对图片来源与授权情况后再发布; "
    "若含第三方图片/素材, 请确认已取得合法授权, 否则请先替换后再使用。\n"
)

#★ AI 创作标识(7.8 第 5 项: aiFlag=1 且 ch_platform.needAiLabelFlag=1 时, 正文尾部必须含标识)
DEFAULT_AI_LABEL_TEXT = "（本内容由 AI 生成, 已按平台要求标注）"

#ZIP 内图片条目扩展名缺省
DEFAULT_IMAGE_EXT = ".png"

#图片条目名安全化: 保留中英文/数字/下划线/连字符/点, 其余替换为下划线
_UNSAFE_NAME_PATTERN = re.compile(r"[^\w\-\.\u4e00-\u9fff]")
#已有「序号_」前缀(避免与打包序号重复)
_SEQ_PREFIX_PATTERN = re.compile(r"^\d{1,3}[_\-]")
#话题标签分隔符(中英文逗号/分号/空白)
_TAG_SPLIT_PATTERN = re.compile(r"[,，;；\s]+")

#===== 错误码与常量 end =====


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


def _fieldLabel(fieldName):
    return f"{fieldName}(artifactpack)"


def _ok(data = None, errMsgList = None):
    return {"errCode": ERR_OK, "field": "", "errMsgList": errMsgList or [], "data": data or {}}


def _err(errCode, rtnField, errMsgList = None, data = None):
    return {"errCode": errCode, "field": rtnField, "errMsgList": errMsgList or [], "data": data or {}}


def _logInfo(message):
    if _LOG:
        _LOG.info(f"PID:{_processorPID}, {message}")


def _logWarn(message):
    if _LOG:
        _LOG.warning(f"W: PID:{_processorPID}, {message}")


def _logError(message):
    if _LOG:
        _LOG.error(f"PID:{_processorPID}, {message}")


def _sha256File(localPath):
    """文件 sha256(流式, 避免大图整块读入内存)"""
    digester = hashlib.sha256()
    with open(localPath, "rb") as hFile:
        while True:
            chunk = hFile.read(1024 * 1024)
            if not chunk:
                break
            digester.update(chunk)
    return digester.hexdigest()


def combineCheckSum(sha256List):
    """素材包整体校验值: sha256(按顺序拼接各文件 sha256)(与适配器 manifestDraft.checkSum 同口径)"""
    digester = hashlib.sha256()
    for value in sha256List or []:
        digester.update(_toStr(value).encode("utf-8"))
    return digester.hexdigest()


def parseSpecNote(specNote):
    """把 ch_artifact.specNote('1080x1440') 解析为 (width, height); 解析失败返回 (0, 0)"""
    matched = re.search(r"(\d+)\s*[xX*]\s*(\d+)", _toStr(specNote))
    if not matched:
        return 0, 0
    return int(matched.group(1)), int(matched.group(2))

#===== 通用小工具 end =====


#===== ZIP 条目组装(纯函数, 便于静态与离线验证) begin =====

def buildImageEntryName(seqNo, fileName = "", fileExt = ""):
    """★ 图片条目名(7.8 第 2 项): 有序命名 01_、02_…; 顺序即 App 内左右滑动浏览顺序。
       形如 `01_<原名去序号前缀><ext>`; 原名缺失时退化为 `01_image.png`。"""
    seq = _toInt(seqNo, 0) or 1
    baseName = os.path.basename(_toStr(fileName)) or "image"
    stem, ext = os.path.splitext(baseName)
    if not ext:
        ext = _toStr(fileExt) or DEFAULT_IMAGE_EXT
        if not ext.startswith("."):
            ext = "." + ext
    stem = _SEQ_PREFIX_PATTERN.sub("", stem)
    stem = _UNSAFE_NAME_PATTERN.sub("_", stem).strip("_") or "image"
    return f"{seq:02d}_{stem}{ext}"


def buildTitleText(topicRecord):
    """title.txt: 标题原样(长度已由合规校验按 ch_platform.titleMaxLen 判定)"""
    return _toStr((topicRecord or {}).get("title"))


def parseTagList(tagList):
    """话题标签解析: 支持数组或 'a,b,c' / 'a b c' 串"""
    if isinstance(tagList, (list, tuple)):
        return [_toStr(item) for item in tagList if _toStr(item)]
    return [item for item in _TAG_SPLIT_PATTERN.split(_toStr(tagList)) if item]


def buildContentText(topicRecord, platformRecord = None):
    """content.txt(7.8 第 4/5 项): 正文 + # 话题标签; aiFlag=1 且平台强制 AI 标识时正文尾部补标识。"""
    topicRecord = topicRecord if isinstance(topicRecord, dict) else {}
    parts = []
    description = _toStr(topicRecord.get("description"))
    if description:
        parts.append(description)

    tagList = parseTagList(topicRecord.get("tagList"))
    if tagList:
        parts.append(" ".join(f"#{tag}" for tag in tagList))

    normalized = platformAdapter.base.normalizePlatformRecord(platformRecord)
    needAiLabel = _toStr(normalized.get("needAiLabelFlag")) == "1"
    if _toStr(topicRecord.get("aiFlag")) == "1" and needAiLabel:
        blob = _toStr(topicRecord.get("summary")) + " " + description
        if not _toStr(topicRecord.get("aiLabel")) and \
                not any(marker in blob for marker in complianceService.AI_LABEL_MARKER_LIST):
            parts.append(DEFAULT_AI_LABEL_TEXT)

    return "\n\n".join(parts)


def buildCopyrightText(topicRecord):
    """COPYRIGHT.txt(7.8 第 7 项): 来源/时期信息 + 版权提示"""
    topicRecord = topicRecord if isinstance(topicRecord, dict) else {}
    return COPYRIGHT_TEMPLATE.format(
        source = _toStr(topicRecord.get("source")) or "(主题未填写来源)",
        period = _toStr(topicRecord.get("period")) or "(主题未填写时期)",
        author = _toStr(topicRecord.get("author")) or "(主题未填写作者)",
    )


def buildRiskNoticeText():
    """RISK_NOTICE.txt(7.8 第 8 项): 风险告知("须手动发布 / 禁止第三方自动发布")"""
    return RISK_NOTICE_TEXT


def buildSwipeTipsText():
    """SWIPE_TIPS.txt(7.8 第 11 项): 滑动可用性提示"""
    return SWIPE_TIPS_TEXT

#===== ZIP 条目组装 end =====


#===== 产物取数(ch_artifact / 调用方显式传入) begin =====

def _normalizeArtifactIDList(dataSet):
    """artifactID / artifactIDs: 支持数组或逗号分隔串"""
    value = dataSet.get("artifactIDs")
    if value is None:
        value = dataSet.get("artifactID")
    if isinstance(value, (list, tuple)):
        return [_toInt(item, 0) for item in value if _toInt(item, 0) > 0]
    return [_toInt(item, 0) for item in re.split(r"[,，\s]+", _toStr(value)) if _toInt(item, 0) > 0]


def loadReadyArtifactRecords(dataSet, platformCode):
    """★ 取 ch_artifact 中 READY 的产物记录(按 jobID 或 artifactID 列表)。
       - 只取 READY(过期/未就绪一律排除);
       - 返回 (recordList, errRtn); 无记录 -> CB, 读取异常 -> CB(带原因)。"""
    jobID = _toInt(dataSet.get("jobID"), 0)
    artifactIDList = _normalizeArtifactIDList(dataSet)
    if jobID <= 0 and not artifactIDList:
        return [], _err(ERR_FIELD_MISSING, _fieldLabel("jobID"),
                        ["jobID 与 artifactID 至少需要一个(或直接传入 products)"])

    tableName = comMysql.tablename_convertor_ch_artifact()
    querySet = {"artifactStatus": renderService.ARTIFACT_STATUS_READY, "mode": "full"}
    if jobID > 0:
        querySet["jobID"] = jobID
    if _toStr(platformCode):
        querySet["platform"] = _toStr(platformCode)

    try:
        rows = comMysql.query_ch_artifact(tableName, **querySet)
    except Exception as e:
        _logError(f"产物台账读取失败 jobID:{jobID}, platform:{platformCode}, errMsg:{e}, {traceback.format_exc()}")
        return [], _err(ERR_NO_RECORD, _fieldLabel("ch_artifact"),
                        [f"产物台账读取失败: {str(e)}"])

    recordList = [row for row in (rows or []) if isinstance(row, dict)]
    if artifactIDList:
        idSet = set(artifactIDList)
        recordList = [row for row in recordList if _toInt(row.get("recID"), 0) in idSet]
    if not recordList:
        return [], _err(ERR_NO_RECORD, _fieldLabel("ch_artifact"),
                        [f"无 READY 产物记录: jobID={jobID}, artifactIDs={artifactIDList}, platform={platformCode}"])

    recordList.sort(key = lambda data: (_toInt(data.get("seqNo"), 1), _toInt(data.get("recID"), 0)))
    return recordList, None


def buildProductsFromRecords(recordList, topicRecord):
    """ch_artifact 记录 -> products(与适配器 render 出参同形态, 供合规校验与清单复用)"""
    topicCode = _toStr((topicRecord or {}).get("topicCode"))
    products = []
    for index, record in enumerate(recordList or []):
        seqNo = _toInt(record.get("seqNo"), index + 1) or (index + 1)
        kind = _toStr(record.get("kind")) or "png"
        width, height = parseSpecNote(record.get("specNote"))
        products.append({
            "seqNo": seqNo,
            "kind": kind,
            "fileID": _toStr(record.get("fileID")),
            "thumbnailID": _toStr(record.get("thumbnailID")),
            "artifactKey": _toStr(record.get("artifactKey")),
            "artifactVer": _toInt(record.get("artifactVer"), 1),
            "artifactId": _toInt(record.get("recID"), 0),
            "fileUrl": "",
            "localPath": "",
            "fileName": f"{topicCode or 'asset'}_{seqNo:02d}.{kind}",
            "width": width,
            "height": height,
            "sizeBytes": _toInt(record.get("sizeBytes"), 0),
            "sha256": "",
            "isCover": "1" if seqNo == 1 else "0",
            "sourceFileID": "",
            "caption": "",
            "layoutType": "",
            "platform": _toStr(record.get("platform")),
        })
    return products


def materializeProduct(product, workDir):
    """把产物落到本地可打包文件: 已有 localPath 且存在则沿用, 否则经文件门面按 fileID 取回。
       出参: (localPath, errMsg); 失败 errMsg 非空。"""
    localPath = _toStr(product.get("localPath"))
    if localPath and os.path.isfile(localPath):
        return localPath, ""

    fileID = _toStr(product.get("fileID"))
    if not fileID:
        return "", "产物缺少 fileID 且无本地文件"

    fileName = os.path.basename(_toStr(product.get("fileName"))) or f"artifact_{_toInt(product.get('seqNo'), 1):02d}.bin"
    targetPath = os.path.join(workDir, fileName)
    try:
        savedPath = comFS.downloadFile(fileID, targetPath)
    except Exception as e:
        _logWarn(f"产物取回失败 fileID:{fileID}, errMsg:{e}")
        savedPath = ""
    if not savedPath or not os.path.isfile(savedPath):
        return "", f"产物取回失败: fileID={fileID}"
    return savedPath, ""

#===== 产物取数 end =====


#===== 合规闸门(★ 复用 complianceService, 不重写规则) begin =====

def runCompliance(topicRecord, assetList, platformRecord, layoutRecord, overrideSpec, products):
    """★ 导出前合规校验(7.8 自动可判定项): 一律复用 complianceService.evaluateCompliance —— 其内部再复用
       base.checkPlatformSpec(平台规格) 与 xiaohongshu.validateSwipeSpec(swipe 专项), 本文件不新增规则表。
       入参 topicRecord 为**导出用的生效主题**(正文已含话题标签与必要的 AI 标识), 保证「校验的就是导出的内容」。
       出参: complianceService 的 {errCode, field, errMsgList, data}。"""
    return complianceService.evaluateCompliance(topicRecord, assetList, platformRecord,
                                                layoutRecord, overrideSpec, products = products)

#===== 合规闸门 end =====


#===== ZIP 组装 begin =====

def buildManifest(topicRecord, meta, imageEntries, checkSum, packageKind):
    """manifest.json(7.8 第 6 项): 主题编码 / 生成时间 / 版式 / 平台 / 文件清单与校验值(sha256)"""
    return {
        "topicCode": _toStr((topicRecord or {}).get("topicCode")),
        "topicID": _toStr((topicRecord or {}).get("recID")),
        "title": _toStr((topicRecord or {}).get("title")),
        "generatedAt": misc.getTime(),
        "layoutCode": _toStr(meta.get("layoutCode")),
        "layoutType": _toStr(meta.get("layoutType")),
        "platform": _toStr(meta.get("platform")),
        "packageKind": packageKind,
        "deliverMode": "asset_pack",
        "imageCount": len(imageEntries),
        "size": _toStr(meta.get("size")) or "1080x1440",
        "ratio": _toStr(meta.get("ratio")) or "3:4",
        "fileList": imageEntries,
        "extraFileList": list(ZIP_TEXT_ENTRY_LIST),
        "checkSum": checkSum,
        "checkSumMethod": "sha256(按 seqNo 拼接各图片文件 sha256)",
        "note": "本素材包须在官方创作服务平台手动发布, 禁止第三方自动发布",
    }


def writeZipPackage(zipPath, imageEntries, textEntries):
    """按 7.8 组装 ZIP: 有序图片在前, 固定文本条目随后。
       出参: (zipSizeBytes, errMsg)。文本一律 UTF-8 写入, 避免 Windows 下编码漂移。"""
    try:
        with zipfile.ZipFile(zipPath, "w", zipfile.ZIP_DEFLATED) as zipFile:
            for entry in imageEntries:
                zipFile.write(entry["localPath"], arcname = entry["entryName"])
            for entryName, text in textEntries:
                zipFile.writestr(entryName, _toStr(text).encode("utf-8"))
    except Exception as e:
        _logError(f"素材包 ZIP 生成失败 zipPath:{zipPath}, errMsg:{e}, {traceback.format_exc()}")
        return 0, f"ZIP 生成失败: {str(e)}"

    if not os.path.isfile(zipPath):
        return 0, "ZIP 生成失败: 未产出文件"
    return os.path.getsize(zipPath), ""

#===== ZIP 组装 end =====


#===== 业务入口: artifactpack begin =====

def exportAssetPack(dataSet, sessionIDSet = None):
    """素材包 ZIP 导出(artifactpack): 取主题 + 附图 + 版式 + 平台 -> 产物 -> **合规闸门** -> 组装 ZIP -> 上传。
       入参(dataSet):
         topicID / recID / topicCode   必填(其一)
         jobID                         可选: 取该渲染任务的 READY 产物作为素材包图片
         artifactID / artifactIDs      可选: 取指定产物(数组或逗号分隔串)
         products                      可选: 调用方直接传入已渲染产物(优先于台账取数)
         layoutCode                    可选(用于 swipe 专项校验与 manifest 版式信息)
         platform                      可选平台编码(缺省 xiaohongshu)
         specOverride / overrideSpec   可选渲染覆盖参数(与 topicrender 同键)
         sensitiveWords                可选敏感词表(透传 complianceService)
         objectDir                     可选产物落盘临时目录(诊断/冒烟用)
       出参: {"errCode","field","errMsgList","data"}, data 含 fileID/fileUrl/manifest/entryList/checkSum 等。
       ★ 只导出、不投递: 全程不调用任何投递/发布能力。"""
    if not isinstance(dataSet, dict):
        dataSet = {}
    sessionIDSet = sessionIDSet if isinstance(sessionIDSet, dict) else {}

    #1) 取主题(复用渲染编排的取数实现)
    topicRecord, errRtn = renderService._fetchTopic(dataSet)
    if errRtn is not None:
        return errRtn
    topicID = _toStr(topicRecord.get("recID"))

    #2) 版式(可选) + 平台解析(请求 > 版式 > 缺省小红书)
    layoutRecord = None
    layoutCode = _toStr(dataSet.get("layoutCode"))
    if layoutCode:
        try:
            layoutRecord = layoutEngine.loadLayoutRecord(layoutCode)
        except layoutEngine.LayoutEngineError as e:
            return _err(e.errCode, e.field or _fieldLabel("layoutCode"), [e.message])

    platformCode = (_toStr(dataSet.get("platform")) or _toStr((layoutRecord or {}).get("platform"))
                    or DEFAULT_PLATFORM_CODE)
    platformRecord, platformErr = renderService._fetchPlatformRecord(platformCode)
    if platformErr is not None:
        return platformErr

    #3) 产物: 调用方显式传入 > ch_artifact(READY)
    products = dataSet.get("products")
    if not isinstance(products, (list, tuple)) or not products:
        recordList, recordErr = loadReadyArtifactRecords(dataSet, platformCode)
        if recordErr is not None:
            return recordErr
        products = buildProductsFromRecords(recordList, topicRecord)
    products = [dict(item) for item in products if isinstance(item, dict)]
    if not products:
        return _err(ERR_NO_RECORD, _fieldLabel("products"), ["素材包无可用产物(products 为空)"])

    #4) 附图(供 swipe 专项校验; 失败降级为空并记日志, 不阻断)
    assetList = []
    try:
        assetList, assetErr = renderService._fetchAssets(topicID)
        if assetErr is None:
            assetList = renderService._mergeAssetMeta(assetList)
        else:
            assetList = []
            _logWarn(f"artifactpack 附图查询失败(降级为空) topicID:{topicID}, errMsg:{assetErr.get('errMsgList')}")
    except Exception as e:
        assetList = []
        _logWarn(f"artifactpack 附图查询异常(降级为空) topicID:{topicID}, errMsg:{e}")

    #5) 生效主题(正文含话题标签与必要的 AI 标识) —— 合规校验的就是导出的内容
    overrideSpec = renderService._resolveOverrideSpec(dataSet)
    exportTopic = dict(topicRecord)
    exportTopic["description"] = buildContentText(topicRecord, platformRecord)

    #6) ★ 合规闸门(未过校验一律不出包)
    complianceRtn = runCompliance(exportTopic, assetList, platformRecord, layoutRecord,
                                  overrideSpec, products)
    if complianceRtn.get("errCode") != ERR_OK:
        _logWarn(f"artifactpack 未过合规校验, 拒绝出包 topicID:{topicID}, "
                 f"errCode:{complianceRtn.get('errCode')}, errMsg:{complianceRtn.get('errMsgList')}")
        data = dict(complianceRtn.get("data") or {})
        data.update({"topicID": topicID, "topicCode": _toStr(topicRecord.get("topicCode")),
                     "platform": platformCode, "packaged": "0"})
        return _err(complianceRtn.get("errCode", ERR_FIELD_INVALID),
                    complianceRtn.get("field") or _fieldLabel("compliance"),
                    complianceRtn.get("errMsgList"), data)
    complianceData = complianceRtn.get("data") or {}

    #7) 落本地 + 逐张校验值(图片条目有序: 01_、02_…)
    workDir = _toStr(dataSet.get("objectDir"))
    tempDir = ""
    if not workDir:
        tempDir = tempfile.mkdtemp(prefix = "ch_assetpack_")
        workDir = tempDir
    elif not os.path.isdir(workDir):
        os.makedirs(workDir, exist_ok = True)

    try:
        imageEntries = []
        for index, product in enumerate(products):
            seqNo = _toInt(product.get("seqNo"), index + 1) or (index + 1)
            localPath, materializeErr = materializeProduct(product, workDir)
            if materializeErr:
                return _err(ERR_FILE_NOT_FOUND, _fieldLabel("products"),
                            [f"第 {seqNo} 张产物不可用: {materializeErr}"])
            entryName = buildImageEntryName(seqNo, product.get("fileName"),
                                            os.path.splitext(localPath)[1])
            imageEntries.append({
                "seqNo": seqNo,
                "entryName": entryName,
                "fileName": _toStr(product.get("fileName")),
                "localPath": localPath,
                "fileID": _toStr(product.get("fileID")),
                "artifactKey": _toStr(product.get("artifactKey")),
                "width": _toInt(product.get("width"), 0),
                "height": _toInt(product.get("height"), 0),
                "sizeBytes": os.path.getsize(localPath),
                "sha256": _sha256File(localPath),
                "isCover": _toStr(product.get("isCover")) or ("1" if seqNo == 1 else "0"),
            })

        imageEntries.sort(key = lambda data: data["seqNo"])
        checkSum = combineCheckSum([entry["sha256"] for entry in imageEntries])

        #8) manifest.json(7.8 第 6 项)
        meta = {
            "layoutCode": layoutCode or _toStr(complianceData.get("layoutCode")),
            "layoutType": _toStr((layoutRecord or {}).get("layoutType")) or _toStr(complianceData.get("layoutType")),
            "platform": platformCode,
            "size": "1080x1440",
            "ratio": "3:4",
        }
        packageKind = f"{platformCode}_asset_pack_zip"
        manifest = buildManifest(topicRecord, meta, imageEntries, checkSum, packageKind)

        #9) 组装 ZIP(图片 -> 文本)
        zipFileName = f"{_toStr(topicRecord.get('topicCode')) or 'asset'}_{misc.getTime()}_assetpack.zip"
        zipPath = os.path.join(workDir, zipFileName)
        zipSizeBytes, zipErr = writeZipPackage(zipPath, imageEntries, [
            (ZIP_ENTRY_TITLE, buildTitleText(topicRecord)),
            (ZIP_ENTRY_CONTENT, exportTopic.get("description")),
            (ZIP_ENTRY_MANIFEST, json.dumps(manifest, ensure_ascii = False, indent = 2)),
            (ZIP_ENTRY_COPYRIGHT, buildCopyrightText(topicRecord)),
            (ZIP_ENTRY_RISK_NOTICE, buildRiskNoticeText()),
            (ZIP_ENTRY_SWIPE_TIPS, buildSwipeTipsText()),
        ])
        if zipErr:
            return _err(ERR_ARTIFACT_FAILED, _fieldLabel("zipPath"), [zipErr])

        #10) 上传(红线 R2: 只经文件门面, 无厂商分支) -> fileID
        fileID = comFS.saveFile(zipPath, objectName = zipFileName, privateFlag = True,
                                bucketCode = comFS.chDefaultBucketCode())
        if not fileID:
            return _err(ERR_UPLOAD_FAILED, _fieldLabel("fileID"), ["素材包 ZIP 上传失败"])

        zipSha256 = _sha256File(zipPath)
        resultData = {
            "packageKind": packageKind,
            "deliverMode": "asset_pack",
            "platform": platformCode,
            "topicID": topicID,
            "topicCode": _toStr(topicRecord.get("topicCode")),
            "layoutCode": layoutCode,
            "jobID": _toInt(dataSet.get("jobID"), 0),
            "fileID": _toStr(fileID),
            "fileName": zipFileName,
            "localZipPath": zipPath,
            "zipSizeBytes": zipSizeBytes,
            "zipSha256": zipSha256,
            "imageCount": len(imageEntries),
            "entryList": [{key: value for key, value in entry.items() if key != "localPath"}
                          for entry in imageEntries],
            "extraEntryList": list(ZIP_TEXT_ENTRY_LIST),
            "manifest": manifest,
            "checkSum": checkSum,
            "checkSumMethod": manifest.get("checkSumMethod"),
            "compliance": {"passed": _toStr(complianceData.get("passed")),
                           "issueCount": _toInt(complianceData.get("issueCount"), 0),
                           "errorCount": _toInt(complianceData.get("errorCount"), 0),
                           "warningCount": _toInt(complianceData.get("warningCount"), 0),
                           "issues": complianceData.get("issues") or []},
            "exportedAt": misc.getTime(),
            "note": "★ 只导出不投递: 素材包须在官方创作服务平台手动发布",
        }
        #出参 fileID -> fileUrl(与其它域一致)
        try:
            comCh.fillFileUrls(resultData, fileFields = ["fileID"])
        except Exception as e:
            _logWarn(f"素材包 fileID 转 URL 失败, errMsg:{e}")

        _logInfo(f"artifactpack 成功 topicID:{topicID}, platform:{platformCode}, "
                 f"images:{len(imageEntries)}, zipSizeBytes:{zipSizeBytes}, fileID:{fileID}")
        return _ok(resultData)
    finally:
        if tempDir and os.path.isdir(tempDir):
            shutil.rmtree(tempDir, ignore_errors = True)

#===== 业务入口结束 =====


if __name__ == "__main__":
    pass
    #本地自测(不连库/不联网): 只验证纯函数与 ZIP 条目组装
    print("ZIP_TEXT_ENTRY_LIST:", ZIP_TEXT_ENTRY_LIST)
    print("buildImageEntryName:", buildImageEntryName(2, "SMOKE_TOPIC_0001_02_card.png"))
    print("buildImageEntryName(fallback):", buildImageEntryName(1, ""))
    print("buildContentText:", buildContentText(
        {"description": "正文", "tagList": "citywalk,摄影", "aiFlag": "1"},
        {"platformCode": "xiaohongshu", "needAiLabelFlag": "1"}))
    print("combineCheckSum:", combineCheckSum(["a", "b"])[:16])
