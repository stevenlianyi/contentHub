#! /usr/bin/env python3
#encoding: utf-8:

#Filename: assetApi.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub 素材业务域接入端点(见 plan/chAPIPost分拆方案.md 3.1 / 4.1)。
#
#约定(命名即契约, G6): 本模块只暴露模块级 `CMD_MAP = {"cmd小写": 处理函数}`, 不自行修改全局注册表。
#处理函数统一签名 func(CMD, dataSet, sessionIDSet), 由聚合器(subfunc/__init__.py)合并进注册表。
#
#★ SP2b(C3 素材图库)职责变更:
#  ch_asset / ch_topic_asset 的 8 个 CRUD 端点(asset{add|del|modify|qry} +
#  topicasset{add|del|modify|qry})**由本模块接管**, 内部统一走 processor/assetService.py,
#  以便「contentHash 内容级去重 / 规格裁剪 / EXIF 剥离 / 缩略图 / fileSystem 快照 /
#  assetKey 幂等 / sortOrder 排序 / usageType 语义」在 HTTP 路径上真实生效。
#  为此 tools/mergeCrudApi.py 已把这两张表列入 EXCLUDED_TABLE_LIST, crudApi 只装配其余 8 张表(32 条 CMD);
#  若两侧同时登记同名 CMD, 聚合器的 V1 冲突校验会在导入期直接抛 RuntimeError(服务起不来)。
#  端点总数不变: 69 = crud 32 + 主题域 8(topicrender 归渲染域) + 素材域 9
#                    + 渲染域 1 + 账号域 16 + 其余业务域 3(publishpush / publishcheck / mcpinvoke)。
#
#本层职责边界: 只做「会话上下文抽取 + 报文封装 + 异常兜底」, 业务规则一律在 assetService 内;
#  严禁在本文件拼 SQL / 直接调 mysqlCommon(红线 R1)—— 数据访问只经 assetService。
#
#★ SP4b(P3-2): artifactpack(素材包 ZIP 导出)已落地 → processor/artifactService.py;
#  素材域占位清单已清空(PLACEHOLDER_CMD_LIST = [])。

_VERSION="20260919"


import os
import sys

_mainDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../code/src/main
_srcDir = os.path.dirname(_mainDir)                                     # .../code/src
for _path in (_srcDir, _mainDir):
    if _path not in sys.path:
        sys.path.insert(0, _path)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

from subfunc import apiCommon

from processor import assetService

#★ SP4b(P3-2 素材包 ZIP 导出): artifactpack 的真实实现落在 processor/artifactService.py
#  (合规闸门复用 processor/complianceService.py, 素材包清单复用 SP3b 适配器 package(), ZIP 经文件门面上传);
#  本文件只做接入层封装(沿用 _serviceResult 范式), **不新增 CMD**。
from processor import artifactService


#本模块接管的 8 个业务端点(供诊断/静态校验使用, 不参与注册表合并)
ASSET_CMD_LIST = [
    "assetadd", "assetdel", "assetmodify", "assetqry",
    "topicassetadd", "topicassetdel", "topicassetmodify", "topicassetqry",
]


def _serviceResult(CMD, dataSet, sessionIDSet, serviceFunc):
    """统一收口: 调用 assetService 并把业务返回映射为 HTTP 报文(零业务, 只做封装/兜底)"""
    try:
        sessionCtx = apiCommon.genSessionContext(dataSet, sessionIDSet)
        rtn = serviceFunc(dataSet, sessionIDSet)
        if not isinstance(rtn, dict):
            rtn = {}

        return apiCommon.genRtnResult(CMD,
                                      errCode = rtn.get("errCode", "C1"),
                                      rtnField = rtn.get("field", ""),
                                      lang = sessionCtx["lang"],
                                      msgKey = sessionCtx["msgKey"],
                                      rtnErrMsgList = rtn.get("errMsgList"),
                                      rtnData = rtn.get("data"))
    except Exception as e:
        return apiCommon.genErrResult(CMD, e)


#素材(asset): contentHash 内容级去重 + 规格裁剪 + EXIF 剥离 + 缩略图 + fileSystem 快照
def funcAssetAdd(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, assetService.addAsset)


def funcAssetDel(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, assetService.deleteAsset)


def funcAssetModify(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, assetService.modifyAsset)


def funcAssetQry(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, assetService.queryAsset)


#主题附图绑定(topicasset): assetKey = {topicID}:{fileID} 幂等 + sortOrder 排序 + usageType 语义
def funcTopicassetAdd(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, assetService.addTopicAsset)


def funcTopicassetDel(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, assetService.deleteTopicAsset)


def funcTopicassetModify(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, assetService.modifyTopicAsset)


def funcTopicassetQry(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, assetService.queryTopicAsset)


#素材打包(artifactpack): ★ SP4b(P3-2) 已落地 —— 按主计划 7.8 导出「小红书素材包 ZIP」
#  取 ch_artifact 的 READY 产物(或调用方显式传入 products) -> **合规闸门(未过校验不出包)**
#  -> 组装 ZIP(有序图片 01_/02_… + title.txt + content.txt + manifest.json + COPYRIGHT.txt
#             + RISK_NOTICE.txt + SWIPE_TIPS.txt) -> 经文件门面上传返回 fileID。
#  ★ 只导出不投递(deliverMode=asset_pack); 小红书一律不投递、不发布。
def funcArtifactPack(CMD, dataSet, sessionIDSet):
    return _serviceResult(CMD, dataSet, sessionIDSet, artifactService.exportAssetPack)


CMD_MAP = {
    "assetadd": funcAssetAdd,
    "assetdel": funcAssetDel,
    "assetmodify": funcAssetModify,
    "assetqry": funcAssetQry,

    "topicassetadd": funcTopicassetAdd,
    "topicassetdel": funcTopicassetDel,
    "topicassetmodify": funcTopicassetModify,
    "topicassetqry": funcTopicassetQry,

    "artifactpack": funcArtifactPack,
}

#占位端点清单(供诊断/落地跟踪使用, 不参与注册表合并)
#★ SP4b: artifactpack 已落地(素材域占位清空; 端点总数仍 69, 不新增 CMD)
PLACEHOLDER_CMD_LIST = []


if __name__ == "__main__":
    pass
    print("assetApi CMD_MAP keys:", list(CMD_MAP.keys()))
    print("assetApi ASSET_CMD_LIST:", ASSET_CMD_LIST)
