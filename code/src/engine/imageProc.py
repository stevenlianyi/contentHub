#! /usr/bin/env python3
#encoding: utf-8

#Filename: imageProc.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 渲染期图像处理公共件(Pillow, SP2c · C4 版式引擎)。

#★ 与 processor/assetService.py 的分工(契约, 必须遵守, 禁止重复实现):
#
#  assetService(业务层) = **入库前**的处理, 面向「素材本体」:
#      - 规格裁剪(settings.MAX_PIC_SIZE)/ 缩略图(settings.THUMBNAIL_SIZE)/ EXIF 剥离;
#      - contentHash 内容级去重; 上传后落 ch_asset 并写 fileSystem/storageBucket 快照。
#    入口: processImageForUpload / fitImageToMaxSize / stripExif / uploadAssetFile ...
#
#  imageProc(引擎层, 本文件) = **渲染期**的派生, 面向「某个版式/平台的目标规格」, 不写 ch_asset:
#      - 封面 900x500 裁切(公众号标题图规格);
#      - swipe / 长图统一 1080x1440 卡片(比例统一, 避免平台强制缩放);
#      - 长图按 sliceHeight 切片(小红书禁止直接上传超长原图);
#      - 派生结果经 fileStorageCommon 上传后返回新的 fileID(供 ch_artifact 登记, SP3)。
#    本文件**不**做入库前裁剪/EXIF/缩略图(那是 assetService 的职责), 也**不**改 ch_asset。
#
#红线 R2: 文件只经 common/fileStorageCommon.py(禁厂商分支); Pillow 采用函数内延迟导入。

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

import tempfile

#global defintion/common var etc.
from common import globalDefinition as comGD

#common functions(log,time,string, json etc)
from common import miscCommon as misc


_processorPID = os.getpid()

if "_LOG" not in dir() or not _LOG:
    try:
        _LOG = misc.setLogNew(comGD._DEF_LOG_CH_WEBAPI_TITLE, comGD._DEF_LOG_CH_WEB_API_NAME)
    except Exception:
        _LOG = None


#===== 规格常量(渲染期目标规格, 与 ch_layout.specJson / ch_platform 口径一致) begin =====

#公众号标题图规格(见 ch_platform.coverSpec / initSeed wechat_mp)
DEFAULT_COVER_SIZE = (900, 500)
#小红书/公众号正文图统一卡片规格(见 initSeed imageSpec)
DEFAULT_CARD_SIZE = (1080, 1440)
#长图默认切片高度(见 initSeed longimage_v1 specJson.sliceHeight)
DEFAULT_SLICE_HEIGHT = 1440

#卡片适配模式: cover=等比填满后居中裁切(不留白) / contain=等比缩放后留白居中
FIT_MODE_COVER = "cover"
FIT_MODE_CONTAIN = "contain"

#图片扩展名(与 assetService.IMAGE_EXT_LIST 同口径; 本层只处理图片, 其余原样返回)
IMAGE_EXT_LIST = ["jpg", "jpeg", "png", "webp", "bmp", "gif"]

#===== 规格常量 end =====


#===== 通用小工具 begin =====

def _toStr(value):
    """None/数字/任意 -> 去空白字符串"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def isImagePath(localPath):
    """按扩展名判断是否图片(非图片不处理, 原样返回)"""
    fileExt = os.path.splitext(_toStr(localPath))[1].lstrip(".").lower()
    return fileExt in IMAGE_EXT_LIST


def parseSize(size, default = DEFAULT_CARD_SIZE):
    """把 '1080x1440' / (1080, 1440) / [1080, 1440] 解析为 (width, height); 非法回落 default"""
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


def parseRatio(ratio, default = (3, 4)):
    """把 '3:4' / '3x4' 解析为 (w, h) 比例对; 非法回落 default(小红书 3:4)"""
    text = _toStr(ratio).replace("x", ":").replace("/", ":")
    if ":" in text:
        parts = text.split(":")
        if len(parts) == 2:
            try:
                w, h = int(parts[0]), int(parts[1])
                if w > 0 and h > 0:
                    return w, h
            except Exception:
                pass
    return default


def _openImage(localPath):
    """延迟导入 Pillow 并打开图片; 失败返回 None(不抛异常)"""
    try:
        from PIL import Image
        return Image.open(localPath)
    except Exception as e:
        if _LOG:
            _LOG.warning(f"W: PID:{_processorPID}, imageProc open image failed, localPath:{localPath}, errMsg:{str(e)}")
        return None

#===== 通用小工具 end =====


#===== 渲染期派生处理 begin =====

def probeSize(localPath):
    """探测图片尺寸, 返回 (width, height); 非图片/失败返回 (0, 0)"""
    if not localPath or not os.path.isfile(localPath) or not isImagePath(localPath):
        return 0, 0
    im = _openImage(localPath)
    if im is None:
        return 0, 0
    try:
        width, height = im.size
        return int(width), int(height)
    except Exception:
        return 0, 0
    finally:
        try:
            im.close()
        except Exception:
            pass


def fitToSize(localPath, size = DEFAULT_CARD_SIZE, mode = FIT_MODE_COVER, outPath = ""):
    """把图片适配到固定目标尺寸(渲染期派生: swipe/长图统一比例, 避免平台强制缩放)。
       入参:
         size   '1080x1440' 或 (w, h)
         mode   cover=等比填满后居中裁切(默认, 无留白) / contain=等比缩放后白底居中
       出参: (outPath, width, height); 非图片/失败返回 (localPath, 0, 0)。
       说明: 与 assetService.fitImageToMaxSize(只缩不放、按入库上限)不同 —— 本函数按渲染目标
             规格做「确定性归一」, 小图允许放大到目标卡片, 保证整篇比例严格一致。"""
    targetWidth, targetHeight = parseSize(size)
    if not localPath or not os.path.isfile(localPath) or not isImagePath(localPath):
        return localPath, 0, 0

    im = _openImage(localPath)
    if im is None:
        return localPath, 0, 0

    try:
        from PIL import Image

        srcWidth, srcHeight = im.size
        if srcWidth <= 0 or srcHeight <= 0:
            return localPath, 0, 0

        if mode == FIT_MODE_CONTAIN:
            scale = min(targetWidth / srcWidth, targetHeight / srcHeight)
        else:
            scale = max(targetWidth / srcWidth, targetHeight / srcHeight)

        newWidth = max(1, int(round(srcWidth * scale)))
        newHeight = max(1, int(round(srcHeight * scale)))
        resized = im.convert("RGB").resize((newWidth, newHeight), Image.LANCZOS)

        left = max(0, (newWidth - targetWidth) // 2)
        top = max(0, (newHeight - targetHeight) // 2)
        canvas = resized.crop((left, top, left + targetWidth, top + targetHeight))

        if not outPath:
            fd, outPath = tempfile.mkstemp(suffix = ".jpg", prefix = "ch_render_card_")
            os.close(fd)

        canvas.save(outPath, "JPEG", quality = 92)
        return outPath, targetWidth, targetHeight
    except Exception as e:
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, imageProc fitToSize failed, localPath:{localPath}, errMsg:{str(e)}")
        return localPath, 0, 0
    finally:
        try:
            im.close()
        except Exception:
            pass


def cropCover(localPath, size = DEFAULT_COVER_SIZE, outPath = ""):
    """封面裁切(公众号标题图 900x500): 等比填满后居中裁切。
       出参: (outPath, width, height); 失败返回 (localPath, 0, 0)。"""
    return fitToSize(localPath, size = size, mode = FIT_MODE_COVER, outPath = outPath)


def sliceLongImage(localPath, sliceHeight = DEFAULT_SLICE_HEIGHT, sliceWidth = 0, outDir = ""):
    """长图切片(小红书禁止直接上传超长原图, 须按 1080x1440 切分)。
       出参: {"slices": [{"path", "seqNo", "offsetY", "height", "isLast"}], "width", "height", "sliceCount"}
       说明: 只做「按高度纵向切分」; 与本文件 fitToSize 组合可先统一宽度再切分。
             切不了(非图片/失败)返回空 slices。"""
    result = {"slices": [], "width": 0, "height": 0, "sliceCount": 0}
    if not localPath or not os.path.isfile(localPath) or not isImagePath(localPath):
        return result

    im = _openImage(localPath)
    if im is None:
        return result

    try:
        width, height = im.size
        if sliceWidth and sliceWidth > 0 and width != sliceWidth:
            #宽度不一致时先按目标宽度等比缩放(避免切片宽度参差)
            im = im.convert("RGB").resize((sliceWidth, max(1, int(round(height * sliceWidth / width)))))
            width, height = im.size

        sliceHeight = int(sliceHeight) if int(sliceHeight) > 0 else DEFAULT_SLICE_HEIGHT
        if not outDir:
            outDir = tempfile.mkdtemp(prefix = "ch_render_slice_")
        elif not os.path.isdir(outDir):
            os.makedirs(outDir, exist_ok = True)

        slices = []
        offsetY = 0
        seqNo = 1
        while offsetY < height:
            bottom = min(height, offsetY + sliceHeight)
            piece = im.crop((0, offsetY, width, bottom))
            piecePath = os.path.join(outDir, f"slice_{seqNo:03d}.jpg")
            piece.save(piecePath, "JPEG", quality = 92)
            slices.append({"path": piecePath, "seqNo": seqNo, "offsetY": offsetY,
                           "height": bottom - offsetY, "isLast": "1" if bottom >= height else "0"})
            offsetY = bottom
            seqNo += 1

        result.update({"slices": slices, "width": width, "height": height, "sliceCount": len(slices)})
        return result
    except Exception as e:
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, imageProc sliceLongImage failed, localPath:{localPath}, errMsg:{str(e)}")
        return result
    finally:
        try:
            im.close()
        except Exception:
            pass

#===== 渲染期派生处理 end =====


#===== 文件门面(红线 R2: 只经 fileStorageCommon) begin =====

def fetchLocalCopy(fileID, storageBucket = "", targetPath = ""):
    """把 fileID 取回本地临时文件(渲染期需要本地像素才能派生)。
       返回本地路径; 失败返回 ""。文件门面延迟导入。"""
    if not fileID or not isinstance(fileID, str):
        return ""
    try:
        from common import fileStorageCommon as comFS
        if not targetPath:
            fd, targetPath = tempfile.mkstemp(prefix = "ch_render_src_")
            os.close(fd)
        return comFS.downloadFile(fileID, targetPath, privateFlag = True, bucketCode = storageBucket) or ""
    except Exception as e:
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, imageProc fetchLocalCopy failed, fileID:{fileID}, errMsg:{str(e)}")
        return ""


def deriveToStorage(localPath, objectName = "", privateFlag = True, storageBucket = ""):
    """把渲染期派生出的本地文件上传, 返回新 fileID; 失败返回 ""。文件门面延迟导入(红线 R2)。"""
    if not localPath or not os.path.isfile(localPath):
        return ""
    try:
        from common import fileStorageCommon as comFS
        if not storageBucket:
            storageBucket = comFS.chDefaultBucketCode()
        return comFS.saveFile(localPath, objectName = objectName, privateFlag = privateFlag,
                              bucketCode = storageBucket) or ""
    except Exception as e:
        if _LOG:
            _LOG.error(f"PID:{_processorPID}, imageProc deriveToStorage failed, localPath:{localPath}, errMsg:{str(e)}")
        return ""


def cleanupTempFiles(pathList):
    """清理渲染期产生的临时文件(失败不抛异常)"""
    for tmpPath in pathList or []:
        if tmpPath and os.path.isfile(tmpPath):
            try:
                os.remove(tmpPath)
            except Exception:
                pass

#===== 文件门面 end =====


if __name__ == "__main__":
    pass
    #本地自测(不连库/不连文件服务): 只验证纯函数
    print("parseSize('1080x1440'):", parseSize("1080x1440"))
    print("parseRatio('3:4'):", parseRatio("3:4"))
    print("DEFAULT_COVER_SIZE:", DEFAULT_COVER_SIZE, "DEFAULT_CARD_SIZE:", DEFAULT_CARD_SIZE)
