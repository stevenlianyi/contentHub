#! /usr/bin/env python3
#encoding: utf-8

#Filename: test_sp2c_render_smoke.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub SP2c(C4 版式引擎) 真实渲染冒烟(不需要数据库/不需要文件服务)。

#本轮最有价值的验收: 用 fixture 样例数据(1 个主题 + 4 张样例附图, 本地生成的占位图)
#对 4 套版式模板各渲染一次, 产物写入 code/data/preview/, 并逐项断言:
#  - stack      : 标题 / 正文 / 图注 顺序正确
#  - carousel   : 有交互节点, 且有静态图集兜底节点(公众号 SVG 不稳)
#  - longimage  : 有切片参数(sliceHeight / sliceCount / slices)
#  - swipe      : seqNo 递增且第 1 张为封面、所有卡片尺寸一致; **不含任何交互脚本**
#另附 imageProc(渲染期派生)能力冒烟: 封面 900x500 裁切 / 卡片 1080x1440 统一 / 长图切片。
#
#★ SP3a 追加(平台产物, 零网络): 用样例主题对 wechat_mp 与 generic 两种平台产物渲染并断言:
#  - wechat_mp: 内联样式化(无 class 依赖 / 无 <style>)、图片落在平台显示域、deliver 凭据缺失显式报错(F0, SP4a 起为通道调用);
#  - wechat_mp carousel: 交互降级(carousel 的 script/按钮移除, 复用静态图集兜底节点);
#  - wechat_mp 外链图片: 非平台显示域 + 本轮无凭据 -> 显式 E4(绝不静默保留外链);
#  - generic: html(复用 stack_v1 的降级实现) / markdown / json 三形态 + 小红书适配器存在/deliver 未实现。
#
#★ SP3b 追加(小红书产物, **真实截图**: Playwright Chromium 已安装, 真跑不得只做静态检查):
#  - swipe_v1 : 产出张数 = 卡片数、每张像素精确 1080x1440、seqNo 递增、首张封面标记、比例统一;
#  - longimage: 整页长图截图 -> 切片数 = ceil(总高/sliceHeight) 且无超长单图;
#  - stack    : 小红书形态为长图 -> 同上;
#  - package  : 素材包清单有序 + manifest 草稿字段齐备;
#  - carousel : 小红书显式不可用(C7, 不静默转换); swipe 比例混用/超量 -> 显式 D1/C6(不静默裁切)。
#  产物落 code/data/preview/xiaohongshu/ 并打印实际像素尺寸证据。
#
#★ SP3c 追加(C8 合规校验 + ch_artifact 产物台账 + ch_render_job 渲染任务化; **桩替换数据层**):
#  - 敏感词命中返回**偏移区间**(多命中, 供前端直接高亮);
#  - needAiLabelFlag=1 且缺 AI 标识 -> 被拦(ERROR); 已标识 / 非强制平台 -> 放行;
#  - 规格违例(标题超长 C5 / 图片超量 C6 / 比例不统一 D1)命中问题清单且可定位(field/location);
#  - ch_artifact 幂等键形态 {jobID}:{kind}:{platform}:{seqNo} + upsertByUniqueKey 调用路径 + artifactVer 递增;
#  - job 状态机非法跃迁被拒(回显允许集); inputHash 相同 -> 复用分支命中(不重复渲染);
#  - Redis 不可用 -> 限流**降级**为进程内计数(degraded 标记可见), 不拒绝、不崩溃。
#  说明: 本机**无 MySQL/Redis 服务端**, 故台账/job/复用/降级均以「桩替换数据层/计数后端」验证(非连库执行)。
#  ★ 2026-09-24 追加(修复回归): 文档类形态(html/json)渲染完成后须登记**单件**产物(kind=html, seqNo=1)
#    并自动把主题状态 RENDERING -> RENDERED(修复前: 任务 DONE 但 ch_artifact 为空, 前端「查看产物」空态)。
#
#★ SP4a 追加(C6 投递链路; 本机无公众号凭据 -> **未端到端打通真实平台**):
#  - 凭据 AES-256-GCM 加解密**真实执行**(往返一致/密文≠明文/无密钥显式报错);
#  - 外链图片真实转存分支**真实执行**(inlineStyle.resolveImageUrl + transferFunc, 验证替换与失败保持 E4);
#  - 投递编排以「桩替换数据层 + 桩替换 HTTP 通道」验证(**桩验证**):
#    未过合规校验 -> 拒绝投递; 二次确认缺失/不匹配 -> F4; 幂等二次提交 -> F1 且不产生第二条记录;
#    撤销窗内可撤销 / 逾窗 F5 / 已撤销 F1; 投递失败 -> errcode+errmsg 落库 + 审计 FAIL;
#    自动发布默认关闭 -> F6 显式拒绝(绝不群发)。
#
#★ SP4b 追加(素材包 ZIP + MCP 薄入口 + 凭据巡检):
#  - 素材包 ZIP: **用 SP3b 的真实小红书产物打 ZIP**(结构/命名顺序/7.8 文本条目/manifest 字段/校验值全部**真实断言**),
#    并验证 ch_artifact 台账取数路径(桩台账 + **真实**按 fileID 取回)与「未过合规校验 -> 拒绝出包(不上传)」;
#  - MCP: **本轮不联调**(不启动 mcp_entry、不监听端口); 端口不变式固定 **8891** 由配置断言 + 静态 S27 锁定,
#    9.6.6 清单的 ①/②(服务端 401/拒绝)记为「未执行」, ③-⑩ 直调 mcpPost 实现层逐条验证(逐项标注 真实执行/桩验证);
#  - 凭据巡检: OK→EXPIRING→INVALID 三态 + R-03 分级告警 + 小红书跳过 + Redis 锁降级 + accounthealth 接线。
#
#★ SP4c 追加(归档清理 + 监控告警 + 巡检守护化; **桩替换数据层/文件门面**):
#  - 归档: dry-run 为默认(**不产生任何导出/删除调用**); 显式执行时**先导出上传成功再删除**且批次循环正确;
#  - 产物清理: 到期 -> **先置 artifactStatus=EXPIRED** -> 再 delFile; 删除失败不改变状态(不再二次变更)且不静默;
#  - 监控七项指标判定**纯函数**(真实执行): 恰在阈值 -> INFO, 越界 -> 对应级别(WARN/ERROR)分级正确;
#  - 告警通道: 日志通道落盘; email/wecom 为**占位实现**, 静态扫描 + 运行期断言均确认**不发任何网络请求**;
#  - 守护化入口: credentialCheck --loop(单实例 + Redis 锁可降级) / archive --execute / dailyCheck __main__。
#  - ★ 目录说明: SP4c 监控核心包由 monitor/ 重命名为 **chmonitor/**; **monitor/** 现为
#    由 museum/code/src/monitor 迁移并改造为 contentHub 口径的运维监控/守护层(零网络 / 剥离 museum 依赖与子进程原语)。
#
#用法: cd code/src && python test/test_sp2c_render_smoke.py

_VERSION="20260919"

import hashlib
import json
import math
import os
import re
import shutil
import sys
import threading

_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CODE_DIR = os.path.dirname(_SRC_DIR)
for _path in (_SRC_DIR, os.path.join(_SRC_DIR, "tools")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

#★ 冒烟不需要数据库: 本脚本不读 ch_layout/ch_topic, 只用 fixture 直接驱动渲染。
#  但 engine/layoutEngine.py 与业务层同源, 会 import common/mysqlCommon.py(其 import config/mysqlSettings
#  时在未设 MYSQL_SKIP_CONNECT 的情况下会尝试直连), 故在此设默认跳过开关, 保证脚本「开箱即跑、不依赖 DB」。
os.environ.setdefault("MYSQL_SKIP_CONNECT", "1")

#第三方: Pillow(占位图) / Jinja2(模板, 由 layoutEngine 延迟导入)
from PIL import Image, ImageDraw

#engine 层(唯一渲染入口) 与 渲染期图像派生
from engine import layoutEngine
from engine import imageProc
from engine import inlineStyle
from engine import htmlToImage

import datetime

#平台适配层(SP3a · C5): 适配器只做「形态转换」; 本轮零网络(不调平台接口/不转存/不投递)
from processor import platformAdapter

#SP3c: 合规服务(C8) 与 渲染编排(job 台账) 直取模块, 便于桩替换数据层做真实行为断言
from processor import complianceService as complianceSvc

from processor import renderService as renderSvc

#SP3c 修复回归(2026-09-24): 主题状态自动推进经 topicService(业务层不直写 ch_topic), 故这里桩替换其 modifyTopic
from processor import topicService as topicSvc

#SP4a: 投递链路(C6) 直取模块, 便于桩替换数据层/HTTP 通道做真实行为断言
from processor import publishService as publishSvc

#SP4b: 素材包 ZIP 导出 / 凭据巡检 直取模块(便于桩替换数据层做真实行为断言)
from processor import artifactService as artifactSvc

from schedule import credentialCheck as credCheck

#SP4c: 归档清理(schedule/archive.py) + 监控指标/告警(chmonitor/, 原 monitor/ 重命名) + 心跳(chmonitor/heartbeat.py)
#  说明: 本机无 MySQL/Redis 服务端, 归档真删/连库路径以「桩替换数据层 + 桩替换文件门面」验证(桩验证);
#        指标判定为纯函数(真实执行); 告警通道占位实现不发任何网络请求(静态 + 运行期断言)。
#  另有 monitor/: 由 museum/code/src/monitor 迁移改造为 contentHub 口径(零网络; 已剥离 museum 依赖与子进程原语)。
from schedule import archive as archiveSvc

from chmonitor import metrics as metricsSvc

from chmonitor import alertChannel as alertSvc

from chmonitor import heartbeat as heartbeatSvc

import tempfile

import zipfile

from common import credentialCipher as credCipher

from common import mysqlCommon as comMysql

from common import chCommon as comCh

#文件门面(SP4b: 素材包 ZIP 上传/取回的断言落点)
from common import fileStorageCommon as comFS

import ast


def _loadSeedList(seedName):
    """用 AST 读取 tools/initSeed.py 的权威种子列表(不执行模块, 保证「不需要数据库」前提)。
       说明: 不 import initSeed(其模块级会牵出 mysqlSettings, 无 MYSQL_SKIP_CONNECT 时会尝试连库)。"""
    seedPath = os.path.join(_SRC_DIR, "tools", "initSeed.py")
    tree = ast.parse(open(seedPath, "rb").read().decode("utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id == seedName:
            return [ast.literal_eval(element) for element in node.value.elts]
    raise RuntimeError(f"initSeed.py 中未找到 {seedName}")


LAYOUT_SEED_LIST = _loadSeedList("LAYOUT_SEED_LIST")
PLATFORM_SEED_LIST = _loadSeedList("PLATFORM_SEED_LIST")


def getPlatformSeed(platformCode):
    """取权威 ch_platform 种子(平台能力矩阵), 供适配器构造"""
    for seed in PLATFORM_SEED_LIST:
        if seed.get("platformCode") == platformCode:
            return dict(seed)
    raise RuntimeError(f"initSeed 中无 platformCode={platformCode} 的种子")


PREVIEW_DIR = os.path.join(_CODE_DIR, "data", "preview")
ASSET_DIR = os.path.join(PREVIEW_DIR, "assets")
DERIVED_DIR = os.path.join(PREVIEW_DIR, "derived")

_resultList = []


def record(name, ok, detail = ""):
    _resultList.append((name, ok, detail))
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {name}{('  -> ' + detail) if detail else ''}")


def writeText(filePath, text):
    with open(filePath, "w", encoding = "utf-8") as hFile:
        hFile.write(text)


#===== fixture 构造 begin =====

def makePlaceholderImages():
    """生成 4 张 3:4 样例附图(尺寸各异但比例统一), 返回 [{path, width, height}]"""
    os.makedirs(ASSET_DIR, exist_ok = True)
    specList = [
        ("asset_1.jpg", (1080, 1440), (220, 90, 90)),
        ("asset_2.jpg", (720, 960),   (90, 160, 220)),
        ("asset_3.jpg", (1200, 1600), (80, 180, 120)),
        ("asset_4.jpg", (900, 1200),  (200, 160, 60)),
    ]
    images = []
    for fileName, size, color in specList:
        filePath = os.path.join(ASSET_DIR, fileName)
        im = Image.new("RGB", size, color)
        drawer = ImageDraw.Draw(im)
        drawer.rectangle([10, 10, size[0] - 10, size[1] - 10], outline = (255, 255, 255), width = 6)
        im.save(filePath, "JPEG", quality = 92)
        images.append({"path": filePath, "width": size[0], "height": size[1]})
    return images


def buildFixtureTopic(images):
    """构造 1 个样例主题(字段与 topicService 出参一致)"""
    return {
        "recID": "1001",
        "topicCode": "SMOKE_TOPIC_0001",
        "title": "秋日citywalk路线推荐",
        "summary": "三条不绕路的城市漫步路线, 附拍照机位与咖啡补给点。",
        "description": "第一条路线从老码头出发, 沿江步道一路向北。\n\n第二条路线穿过老城区, 适合扫街与纪实。\n\n第三条路线串联三个公园, 适合慢跑与遛娃。",
        "coverFileID": "cover_f1",
        "coverUrl": images[0]["path"],
        "author": "内容中枢编辑部",
        "location": "上海",
        "source": "实地探访",
        "period": "2026秋",
        "tagList": "citywalk,摄影,咖啡",
        "status": "RENDERED",
        "wordCount": "2680",
        "aiFlag": "0",
    }


def buildFixtureAssets(images):
    """构造样例附图(含图注/usageType/sortOrder/尺寸); cover 故意放在 sortOrder 较后, 验证 swipe 置顶"""
    return [
        {"fileID": "f_body_1", "fileUrl": images[0]["path"], "caption": "老码头晨景",
         "usageType": "body", "sortOrder": 10, "width": images[0]["width"], "height": images[0]["height"]},
        {"fileID": "f_cover", "fileUrl": images[1]["path"], "caption": "封面主视觉",
         "usageType": "cover", "sortOrder": 50, "width": images[1]["width"], "height": images[1]["height"]},
        {"fileID": "f_body_2", "fileUrl": images[2]["path"], "caption": "老城区街角",
         "usageType": "body", "sortOrder": 20, "width": images[2]["width"], "height": images[2]["height"]},
        {"fileID": "f_body_3", "fileUrl": images[3]["path"], "caption": "公园慢跑道",
         "usageType": "body", "sortOrder": 30, "width": images[3]["width"], "height": images[3]["height"]},
    ]


def buildLayoutRecord(layoutType):
    """从权威种子取版式定义(含 specJson); 种子即契约, 保证模板消费的键与之对齐"""
    for seed in LAYOUT_SEED_LIST:
        if seed.get("layoutType") == layoutType:
            return dict(seed)
    raise RuntimeError(f"initSeed 中无 layoutType={layoutType} 的种子")

#===== fixture 构造 end =====


#===== 渲染与断言 begin =====

def renderOne(layoutType, topic, assets):
    layoutRecord = buildLayoutRecord(layoutType)
    rtn = layoutEngine.renderLayout(layoutRecord, topic, assets)
    content = rtn.get("content") or ""
    meta = rtn.get("meta") or {}

    outPath = os.path.join(PREVIEW_DIR, f"{layoutRecord.get('layoutCode')}.html")
    writeText(outPath, content)
    writeText(os.path.join(PREVIEW_DIR, f"{layoutRecord.get('layoutCode')}.meta.json"),
              json.dumps(meta, ensure_ascii = False, indent = 2))
    return layoutRecord, rtn, content, meta


def assertStack(content, meta, assets):
    errList = []
    if 'data-layout="stack_v1"' not in content:
        errList.append("缺少 stack 根节点")
    if 'data-block="title"' not in content:
        errList.append("缺少标题节点")

    titlePos = content.find("秋日citywalk路线推荐")
    bodyPos = content.find("data-block=\"body\"")
    if titlePos < 0:
        errList.append("标题文本未渲染")
    if bodyPos < 0:
        errList.append("缺少正文节点")

    #图注顺序须与 sortOrder 一致: 老码头晨景(10) -> 老城区街角(20) -> 公园慢跑道(30)
    captionOrder = [content.find("老码头晨景"), content.find("老城区街角"), content.find("公园慢跑道")]
    if -1 in captionOrder:
        errList.append(f"图注缺失: {captionOrder}")
    elif captionOrder != sorted(captionOrder):
        errList.append(f"图注顺序错误: {captionOrder}")

    #标题应在正文之前
    if titlePos >= 0 and bodyPos >= 0 and titlePos > bodyPos:
        errList.append("标题出现在正文之后")

    if meta.get("imageCount") != len(assets):
        errList.append(f"imageCount={meta.get('imageCount')} != {len(assets)}")

    record("strategy stack 结构断言", not errList, "; ".join(errList[:5]))


def assertCarousel(content, meta, assets):
    errList = []
    if 'data-interactive="1"' not in content:
        errList.append("缺少交互节点(data-interactive)")
    if "data-carousel-slide" not in content:
        errList.append("缺少轮播幻灯片节点")
    if "data-carousel-prev" not in content or "data-carousel-next" not in content:
        errList.append("缺少轮播控制按钮")
    if "<script" not in content:
        errList.append("缺少自实现交互脚本")

    #★ 静态图集兜底必须产出
    if 'data-carousel-fallback="static"' not in content:
        errList.append("缺少静态图集兜底节点")
    staticCount = len(re.findall(r"data-static-seqno=", content))
    if staticCount != len(assets):
        errList.append(f"静态兜底图数 {staticCount} != {len(assets)}")
    if meta.get("staticFallback") is not True:
        errList.append("meta.staticFallback 非 True")

    record("carousel 交互+静态兜底断言", not errList, "; ".join(errList[:5]))


def assertLongimage(content, meta, assets):
    errList = []
    if 'data-layout="longimage_v1"' not in content:
        errList.append("缺少 longimage 根节点")
    if "data-slice-seqno" not in content:
        errList.append("缺少切片节点")
    if int(meta.get("sliceHeight") or 0) <= 0:
        errList.append("缺少 sliceHeight")
    if int(meta.get("sliceCount") or 0) <= 0:
        errList.append("缺少 sliceCount")
    slices = meta.get("slices") or []
    if not slices:
        errList.append("缺少 slices 切片计划")
    else:
        offsetList = [s.get("offsetY") for s in slices]
        if offsetList != sorted(offsetList):
            errList.append(f"切片 offsetY 非递增: {offsetList}")
        if slices[0].get("offsetY") != 0:
            errList.append("首个切片 offsetY 非 0")
    if len(re.findall(r"data-slice-seqno=", content)) != len(slices):
        errList.append("切片节点数与 meta.slices 不一致")

    record("longimage 切片参数断言", not errList, "; ".join(errList[:5]))


def assertSwipe(content, meta, assets):
    errList = []
    if 'data-layout="swipe_v1"' not in content:
        errList.append("缺少 swipe 根节点")
    if 'data-mechanism="platform_native"' not in content:
        errList.append("缺少 platform_native 标记")

    #★ swipe 不得自实现交互
    if "<script" in content or "onclick" in content.lower():
        errList.append("swipe 出现了自实现交互(script/onclick)")

    cards = meta.get("cards") or []
    if len(cards) != len(assets):
        errList.append(f"卡片数 {len(cards)} != {len(assets)}")

    #seqNo 递增
    seqNoList = [c.get("seqNo") for c in cards]
    if seqNoList != list(range(1, len(cards) + 1)):
        errList.append(f"seqNo 非严格递增: {seqNoList}")

    #第 1 张为封面标记(且应为 usageType=cover 的那张)
    if not cards or cards[0].get("isCover") != "1":
        errList.append("第 1 张非封面")
    if not cards or cards[0].get("usageType") != "cover":
        errList.append("封面(usageType=cover)未置顶")

    #所有卡片尺寸一致
    sizeSet = {(c.get("width"), c.get("height")) for c in cards}
    if len(sizeSet) != 1:
        errList.append(f"卡片尺寸不一致: {sizeSet}")

    #比例统一校验通过
    if any(c.get("ratioOk") == "0" for c in cards):
        errList.append("存在比例不一致的卡片")

    if len(re.findall(r"data-swipe-card=", content)) != len(cards):
        errList.append("卡片节点数与 meta.cards 不一致")

    record("swipe 顺序/封面/等比例断言", not errList, "; ".join(errList[:6]))


def assertPreview(topic, assets):
    """站内预览(P1-8): 渲染片段 -> 微信/小红书手机框包裹"""
    errList = []
    layoutRecord = buildLayoutRecord("stack")
    inner = layoutEngine.renderLayout(layoutRecord, topic, assets, embedMode = True)
    if "<!DOCTYPE" in inner.get("content", ""):
        errList.append("embedMode 片段不应含完整文档头")

    for previewKind, frameToken in (("wechat", 'data-preview="wechat_mp"'), ("xiaohongshu", 'data-preview="xiaohongshu"')):
        html = layoutEngine.renderPreview(previewKind, inner.get("content", ""),
                                          layoutEngine._normalizeTopic(topic), inner.get("meta"))
        if frameToken not in html:
            errList.append(f"{previewKind} 预览缺少手机框节点")
        if "data-phone-screen" not in html:
            errList.append(f"{previewKind} 预览缺少屏幕容器")
        if topic.get("title") and topic["title"] not in html:
            errList.append(f"{previewKind} 预览缺少主题标题")
        writeText(os.path.join(PREVIEW_DIR, f"preview_{previewKind}.html"), html)

    record("站内预览 手机框断言", not errList, "; ".join(errList[:5]))


def assertImageProc(images):
    """渲染期派生图像处理能力: 封面 900x500 / 卡片 1080x1440 / 长图切片"""
    errList = []
    os.makedirs(DERIVED_DIR, exist_ok = True)

    coverPath, coverW, coverH = imageProc.cropCover(images[1]["path"],
                                                    outPath = os.path.join(DERIVED_DIR, "cover_900x500.jpg"))
    if (coverW, coverH) != (900, 500):
        errList.append(f"封面裁切尺寸 {coverW}x{coverH} != 900x500")

    cardPath, cardW, cardH = imageProc.fitToSize(images[0]["path"], size = "1080x1440",
                                                 outPath = os.path.join(DERIVED_DIR, "card_1080x1440.jpg"))
    if (cardW, cardH) != (1080, 1440):
        errList.append(f"卡片归一尺寸 {cardW}x{cardH} != 1080x1440")

    #造一张 1080x2880 长图并切片
    longPath = os.path.join(DERIVED_DIR, "long_1080x2880.jpg")
    Image.new("RGB", (1080, 2880), (60, 60, 90)).save(longPath, "JPEG", quality = 90)
    sliceInfo = imageProc.sliceLongImage(longPath, sliceHeight = 1440, sliceWidth = 1080,
                                         outDir = os.path.join(DERIVED_DIR, "slices"))
    if sliceInfo.get("sliceCount") != 2:
        errList.append(f"长图切片数 {sliceInfo.get('sliceCount')} != 2")

    #清理临时派生(保留目录占位)
    for path in (coverPath, cardPath):
        if path and os.path.isfile(path) and not path.startswith(DERIVED_DIR):
            imageProc.cleanupTempFiles([path])

    record("imageProc 渲染期派生素材", not errList, "; ".join(errList[:5]))


#===== SP3a 平台产物冒烟(wechat_mp / generic) begin =====

#平台样例主题的图片地址: 微信域(可直接显示) vs 非微信域外链(需转存, 本轮无凭据 -> E4)
MMBIZ_COVER_URL = "https://mmbiz.qpic.cn/sz_mmbiz_png/smoke_cover/0?wx_fmt=jpeg"
MMBIZ_BODY_URL_LIST = ["https://mmbiz.qpic.cn/sz_mmbiz_png/smoke_body_1/0?wx_fmt=jpeg",
                       "https://mmbiz.qpic.cn/sz_mmbiz_png/smoke_body_2/0?wx_fmt=jpeg"]
EXTERNAL_IMAGE_URL = "https://example.com/not-wechat-cdn.jpg"


def buildPlatformTopic():
    """平台产物冒烟样例主题(规格合规: 标题/摘要在 wechat_mp 上限内)"""
    return {
        "recID": "2001",
        "topicCode": "SMOKE_PLATFORM_0001",
        "title": "秋日citywalk路线推荐",
        "summary": "三条不绕路的城市漫步路线, 附拍照机位与咖啡补给点。",
        "description": "第一条路线从老码头出发, 沿江步道一路向北。\n\n第二条路线穿过老城区, 适合扫街与纪实。",
        "coverFileID": "pf_cover",
        "coverUrl": MMBIZ_COVER_URL,
        "author": "内容中枢编辑部",
        "location": "上海",
        "source": "实地探访",
        "period": "2026秋",
        "tagList": "citywalk,摄影",
        "status": "RENDERED",
        "aiFlag": "0",
    }


def buildPlatformAssets(bodyUrlList = None):
    """平台产物冒烟样例附图: 封面 900x500(合 wechat_mp coverSpec) + 正文图 1080x1440(合 imageSpec)"""
    bodyUrlList = bodyUrlList if bodyUrlList is not None else MMBIZ_BODY_URL_LIST
    assetList = [{"fileID": "pf_cover", "fileUrl": MMBIZ_COVER_URL, "caption": "封面主视觉",
                  "usageType": "cover", "sortOrder": 10, "width": 900, "height": 500}]
    for idx, url in enumerate(bodyUrlList):
        assetList.append({"fileID": f"pf_body_{idx + 1}", "fileUrl": url, "caption": f"正文图 {idx + 1}",
                          "usageType": "body", "sortOrder": 20 + idx * 10, "width": 1080, "height": 1440})
    return assetList


def assertWechatPlatformArtifact(topic, assets):
    """wechat_mp 产物: 内联样式(无 class/无 <style>) + 图片落在平台显示域 + deliver 未实现 + 零网络"""
    adapter = platformAdapter.getAdapter("wechat_mp", getPlatformSeed("wechat_mp"))
    if adapter is None:
        record("wechat_mp 平台产物断言", False, "未取到 WechatMpAdapter")
        return

    rtn = adapter.render(topic, buildLayoutRecord("stack"), assets)
    if rtn.get("errCode") != "B0":
        record("wechat_mp 平台产物断言", False, f"render 失败: {rtn.get('errCode')} {rtn.get('errMsgList')}")
        return

    errList = []
    data = rtn.get("data") or {}
    content = data.get("content") or ""
    meta = data.get("meta") or {}
    writeText(os.path.join(PREVIEW_DIR, "platform_wechat_mp_stack.html"), content)

    if "class=" in content:
        errList.append("残留 class 依赖")
    if "<script" in content:
        errList.append("残留 <script>")
    if "<style" in content:
        errList.append("残留 <style>")
    if "max-width:100%" not in content:
        errList.append("样式未下沉为内联 style")
    if 'data-block="title"' not in content:
        errList.append("缺少标题节点")
    if meta.get("platformCode") != "wechat_mp":
        errList.append(f"meta.platformCode={meta.get('platformCode')}")
    if meta.get("deliverMode") != "draft_box":
        errList.append(f"meta.deliverMode={meta.get('deliverMode')}")
    if meta.get("inlineStyled") != "1" or meta.get("classFree") != "1":
        errList.append("meta inlineStyled/classFree 标记不符")
    if meta.get("networkRequest") != "0":
        errList.append("meta.networkRequest 非 0(本轮零网络)")

    for src in re.findall(r'<img\b[^>]*?\bsrc="([^"]+)"', content):
        if "mmbiz.qpic.cn" not in src:
            errList.append(f"图片未落在平台显示域: {src}")

    #deliver ★SP4a: wechat_mp 已实现通道调用; 未提供 accessToken -> 显式 F0(不静默成功、不误判为未实现)
    deliverRtn = adapter.deliver({}, {})
    if deliverRtn.get("errCode") in ("B0", "C2") or not deliverRtn.get("errMsgList"):
        errList.append(f"deliver 应显式报错(凭据缺失 F0): {deliverRtn.get('errCode')}")
    packageRtn = adapter.package({"content": content}, topic, assets)
    if packageRtn.get("errCode") != "B0" \
            or (packageRtn.get("data") or {}).get("packageKind") != "wechat_draft_payload":
        errList.append("package 未产出草稿载荷清单")
    healthRtn = adapter.checkHealth()
    if healthRtn.get("errCode") != "B0" or (healthRtn.get("data") or {}).get("networkRequest") != "0":
        errList.append("checkHealth 非零网络或异常")

    record("wechat_mp 平台产物(内联/无class/图片域/deliver)", not errList, "; ".join(errList[:6]))


def assertWechatCarouselDegrade(topic, assets):
    """carousel 在公众号(allowSvgFlag=0)降级: 移除交互(script/按钮), 复用静态图集兜底节点"""
    adapter = platformAdapter.getAdapter("wechat_mp", getPlatformSeed("wechat_mp"))
    rtn = adapter.render(topic, buildLayoutRecord("carousel"), assets)
    if rtn.get("errCode") != "B0":
        record("wechat_mp carousel 交互降级断言", False, f"render 失败: {rtn.get('errCode')} {rtn.get('errMsgList')}")
        return

    errList = []
    content = (rtn.get("data") or {}).get("content") or ""
    meta = (rtn.get("data") or {}).get("meta") or {}
    writeText(os.path.join(PREVIEW_DIR, "platform_wechat_mp_carousel.html"), content)

    if "<script" in content:
        errList.append("降级后仍残留 <script>")
    if "data-carousel-controls" in content:
        errList.append("降级后仍残留翻页控件")
    if 'data-degraded="static_fallback"' not in content:
        errList.append("未复用静态图集兜底节点")
    if meta.get("interactionDegraded") != "1":
        errList.append("meta.interactionDegraded 非 1")

    record("wechat_mp carousel 交互降级断言", not errList, "; ".join(errList[:5]))


def assertWechatExternalImageBlocked(topic):
    """非平台显示域外链 + 本轮无凭据 -> 显式 E4(绝不静默保留外链)"""
    adapter = platformAdapter.getAdapter("wechat_mp", getPlatformSeed("wechat_mp"))
    rtn = adapter.render(topic, buildLayoutRecord("stack"), buildPlatformAssets([EXTERNAL_IMAGE_URL]))

    errList = []
    if rtn.get("errCode") != "E4":
        errList.append(f"未返回 E4: {rtn.get('errCode')}")
    if not rtn.get("errMsgList"):
        errList.append("缺少显式错误说明")
    record("wechat_mp 外链图片显式 E4 断言", not errList, "; ".join(errList[:5]))


def assertGenericPlatformArtifact(topic, assets):
    """generic 产物: html(复用 stack_v1 降级) / markdown / json 三形态 + deliver 未实现 + 无小红书适配器"""
    adapter = platformAdapter.getAdapter("generic", getPlatformSeed("generic"))
    if adapter is None:
        record("generic 平台产物断言", False, "未取到 GenericAdapter")
        return

    errList = []
    stackLayout = buildLayoutRecord("stack")

    htmlRtn = adapter.render(topic, stackLayout, assets, options = {"exportKind": "html"})
    if htmlRtn.get("errCode") != "B0":
        errList.append(f"html 失败: {htmlRtn.get('errCode')}")
    else:
        htmlContent = (htmlRtn.get("data") or {}).get("content") or ""
        htmlMeta = (htmlRtn.get("data") or {}).get("meta") or {}
        writeText(os.path.join(PREVIEW_DIR, "platform_generic_stack.html"), htmlContent)
        if "class=" in htmlContent:
            errList.append("html 残留 class")
        if htmlMeta.get("degradedImpl") != "stack_v1_reuse":
            errList.append("html 未标注「复用 stack_v1」的降级实现")

    mdRtn = adapter.render(topic, stackLayout, assets, options = {"exportKind": "markdown"})
    if mdRtn.get("errCode") != "B0" or (mdRtn.get("data") or {}).get("outputKind") != "markdown":
        errList.append(f"markdown 失败: {mdRtn.get('errCode')}")
    else:
        mdContent = mdRtn["data"]["content"]
        writeText(os.path.join(PREVIEW_DIR, "platform_generic_stack.md"), mdContent)
        if not mdContent.startswith(f"# {topic.get('title')}"):
            errList.append("markdown 缺少一级标题")

    jsonRtn = adapter.render(topic, stackLayout, assets, options = {"exportKind": "json"})
    if jsonRtn.get("errCode") != "B0" or (jsonRtn.get("data") or {}).get("outputKind") != "json":
        errList.append(f"json 失败: {jsonRtn.get('errCode')}")
    else:
        jsonContent = jsonRtn["data"]["content"]
        writeText(os.path.join(PREVIEW_DIR, "platform_generic_stack.json"), jsonContent)
        try:
            parsed = json.loads(jsonContent)
            if "topic" not in parsed or "assets" not in parsed:
                errList.append("json 缺少 topic/assets")
        except Exception as e:
            errList.append(f"json 不可解析: {e}")

    if adapter.deliver({}, {}).get("errCode") != "C2":
        errList.append("deliver 未返回 C2(未实现)")

    #★ SP3b: 小红书适配器已提供(只导出素材包, **无自动发布路径**); deliver 仍显式未实现(C2)
    xhsAdapter = platformAdapter.getAdapter("xiaohongshu", getPlatformSeed("xiaohongshu"))
    if xhsAdapter is None:
        errList.append("缺少小红书适配器(SP3b 应已提供)")
    elif xhsAdapter.deliver({}, {}).get("errCode") != "C2":
        errList.append("小红书 deliver 未返回 C2(未实现)")

    record("generic 平台产物(html/markdown/json)", not errList, "; ".join(errList[:6]))

#===== SP3a 平台产物冒烟 end =====


#===== SP3b 小红书真实截图冒烟(Playwright, 真跑) begin =====

#小红书真实产物输出目录(证据留存)
XHS_PREVIEW_DIR = os.path.join(PREVIEW_DIR, "xiaohongshu")

#截图超时上限(真实 Chromium 渲染, 保守上限; 4 张卡片串行)
XHS_RENDER_TIMEOUT_MS = 60000


def _xhsOptions():
    return {"productDir": XHS_PREVIEW_DIR, "deviceScaleFactor": 1, "timeoutMs": XHS_RENDER_TIMEOUT_MS}


def _probePixels(localPath):
    """读取 PNG 产物实际像素尺寸(证据), 返回 (width, height)"""
    try:
        with Image.open(localPath) as im:
            return int(im.size[0]), int(im.size[1])
    except Exception:
        return 0, 0


def assertXiaohongshuSwipe(topic, assets):
    """★ swipe_v1 真实截图: 产出张数 = 卡片数、每张像素精确 1080x1440、seqNo 递增、首张封面标记、比例统一"""
    adapter = platformAdapter.getAdapter("xiaohongshu", getPlatformSeed("xiaohongshu"))
    if adapter is None:
        record("小红书 swipe 真实截图断言", False, "未取到 XiaohongshuAdapter")
        return

    rtn = adapter.render(topic, buildLayoutRecord("swipe"), assets, options = _xhsOptions())
    if rtn.get("errCode") != "B0":
        record("小红书 swipe 真实截图断言", False, f"render 失败: {rtn.get('errCode')} {rtn.get('errMsgList')}")
        return

    errList = []
    data = rtn.get("data") or {}
    meta = data.get("meta") or {}
    products = data.get("products") or []

    if data.get("outputKind") != "png":
        errList.append(f"outputKind={data.get('outputKind')} != png")
    if len(products) != len(assets):
        errList.append(f"产物张数 {len(products)} != 卡片数 {len(assets)}")

    seqNoList = [int(item.get("seqNo") or 0) for item in products]
    if seqNoList != list(range(1, len(products) + 1)):
        errList.append(f"seqNo 非严格递增: {seqNoList}")
    if not products or products[0].get("isCover") != "1":
        errList.append("第 1 张非封面标记")

    #★ 每张像素精确 1080x1440(打印实际尺寸作为证据)
    for item in products:
        localPath = item.get("localPath")
        pixelW, pixelH = _probePixels(localPath)
        print(f"[xhs-swipe] seqNo={item.get('seqNo')} 记录尺寸={item.get('width')}x{item.get('height')} "
              f"实际像素={pixelW}x{pixelH} fileID={item.get('fileID')} -> {localPath}")
        if (pixelW, pixelH) != (1080, 1440):
            errList.append(f"seqNo={item.get('seqNo')} 实际像素 {pixelW}x{pixelH} != 1080x1440")
        if not item.get("fileID"):
            errList.append(f"seqNo={item.get('seqNo')} 缺少 fileID(未上传)")

    if 'data-mechanism="platform_native"' not in (data.get("content") or ""):
        errList.append("产物 HTML 缺少 platform_native 标记")
    if meta.get("networkRequest") != "0":
        errList.append("meta.networkRequest 非 0(本轮零对外网络)")
    #截图管线记录实际使用字体(便于排查中文丢字)
    if not (meta.get("fontInfo") or {}).get("usedFontFamilies"):
        errList.append("meta.fontInfo 未记录实际使用字体")

    record("小红书 swipe 真实截图(1080x1440/张数/seqNo/封面)", not errList, "; ".join(errList[:6]))
    return rtn


def _assertSlices(rtn, name, expectedWidth = 1080, sliceHeight = 1440):
    errList = []
    data = rtn.get("data") or {}
    meta = data.get("meta") or {}
    products = data.get("products") or []

    fullHeight = int(meta.get("fullHeight") or 0)
    expectedCount = int(math.ceil(fullHeight / sliceHeight)) if fullHeight > 0 else 0
    print(f"[{name}] fullHeight={fullHeight} sliceHeight={sliceHeight} "
          f"期望切片数=ceil({fullHeight}/{sliceHeight})={expectedCount} 实际={len(products)}")
    if expectedCount <= 0:
        errList.append("未取得长图实际总高(meta.fullHeight)")
    if len(products) != expectedCount:
        errList.append(f"切片数 {len(products)} != ceil(总高/sliceHeight) {expectedCount}")

    seqNoList = [int(item.get("seqNo") or 0) for item in products]
    if seqNoList != list(range(1, len(products) + 1)):
        errList.append(f"seqNo 非严格递增: {seqNoList}")

    totalSliceHeight = 0
    for item in products:
        localPath = item.get("localPath")
        pixelW, pixelH = _probePixels(localPath)
        totalSliceHeight += pixelH
        print(f"[{name}] seqNo={item.get('seqNo')} 记录尺寸={item.get('width')}x{item.get('height')} "
              f"实际像素={pixelW}x{pixelH} fileID={item.get('fileID')} -> {localPath}")
        #★ 无超长单图: 每切片高度 ≤ sliceHeight
        if pixelH > sliceHeight:
            errList.append(f"seqNo={item.get('seqNo')} 切片高 {pixelH} 超 sliceHeight {sliceHeight}(出现超长单图)")
        if pixelW != expectedWidth:
            errList.append(f"seqNo={item.get('seqNo')} 切片宽 {pixelW} != {expectedWidth}")
        if not item.get("fileID"):
            errList.append(f"seqNo={item.get('seqNo')} 缺少 fileID(未上传)")

    if fullHeight > 0 and totalSliceHeight != fullHeight:
        errList.append(f"切片高度之和 {totalSliceHeight} != 长图总高 {fullHeight}")
    if meta.get("networkRequest") != "0":
        errList.append("meta.networkRequest 非 0(本轮零对外网络)")

    record(f"{name} 真实截图(切片数=ceil(总高/sliceHeight)/无超长单图)", not errList, "; ".join(errList[:6]))
    return rtn


def assertXiaohongshuLongimage(topic, assets):
    """★ longimage_v1 真实截图: 整页长图 -> 按 1440 切分, 切片数 = ceil(总高/sliceHeight) 且无超长单图"""
    adapter = platformAdapter.getAdapter("xiaohongshu", getPlatformSeed("xiaohongshu"))
    if adapter is None:
        record("小红书 longimage 真实截图断言", False, "未取到 XiaohongshuAdapter")
        return None

    rtn = adapter.render(topic, buildLayoutRecord("longimage"), assets, options = _xhsOptions())
    if rtn.get("errCode") != "B0":
        record("小红书 longimage 真实截图断言", False, f"render 失败: {rtn.get('errCode')} {rtn.get('errMsgList')}")
        return None
    return _assertSlices(rtn, "小红书 longimage")


def assertXiaohongshuStackToLongimage(topic, assets):
    """★ stack 在小红书形态为长图: 走 longimage 管线(同上断言)"""
    adapter = platformAdapter.getAdapter("xiaohongshu", getPlatformSeed("xiaohongshu"))
    if adapter is None:
        record("小红书 stack→长图 真实截图断言", False, "未取到 XiaohongshuAdapter")
        return

    rtn = adapter.render(topic, buildLayoutRecord("stack"), assets, options = _xhsOptions())
    if rtn.get("errCode") != "B0":
        record("小红书 stack→长图 真实截图断言", False, f"render 失败: {rtn.get('errCode')} {rtn.get('errMsgList')}")
        return
    _assertSlices(rtn, "小红书 stack→长图")


def assertXiaohongshuPackage(topic, assets, swipeRtn):
    """★ package 素材包清单: 有序文件列表 + manifest 草稿(主题编码/生成时间/版式/平台/校验值)"""
    adapter = platformAdapter.getAdapter("xiaohongshu", getPlatformSeed("xiaohongshu"))
    if adapter is None or not swipeRtn:
        record("小红书 package 素材包清单断言", False, "缺少适配器或 swipe 产物")
        return

    packageRtn = adapter.package(swipeRtn.get("data") or {}, topic, assets)
    errList = []
    if packageRtn.get("errCode") != "B0":
        record("小红书 package 素材包清单断言", False, f"package 失败: {packageRtn.get('errCode')}")
        return

    plan = packageRtn.get("data") or {}
    itemList = plan.get("itemList") or []
    manifest = plan.get("manifestDraft") or {}

    if plan.get("packageKind") != "xiaohongshu_asset_pack":
        errList.append(f"packageKind={plan.get('packageKind')}")
    if plan.get("zipPacked") is not False:
        errList.append("本轮不应打包 ZIP(zipPacked 应为 False)")
    if len(itemList) != len(assets):
        errList.append(f"清单项数 {len(itemList)} != {len(assets)}")

    seqNoList = [int(item.get("seqNo") or 0) for item in itemList]
    if seqNoList != sorted(seqNoList) or seqNoList != list(range(1, len(itemList) + 1)):
        errList.append(f"清单未按 seqNo 有序: {seqNoList}")
    for item in itemList:
        if not item.get("fileName") or not item.get("fileID") or not item.get("sha256"):
            errList.append(f"清单项缺字段: seqNo={item.get('seqNo')}")
            break

    for key in ("topicCode", "generatedAt", "layoutType", "platform", "checkSum", "fileList"):
        if not manifest.get(key):
            errList.append(f"manifest 缺少字段: {key}")
    if manifest.get("platform") != "xiaohongshu":
        errList.append(f"manifest.platform={manifest.get('platform')}")

    writeText(os.path.join(XHS_PREVIEW_DIR, "package_manifest.json"),
              json.dumps(plan, ensure_ascii = False, indent = 2))
    record("小红书 package 清单有序且含 manifest 字段", not errList, "; ".join(errList[:6]))


def assertXiaohongshuCarouselUnavailable(topic, assets):
    """★ carousel 在小红书不可用: 显式报错(不得静默转换)"""
    adapter = platformAdapter.getAdapter("xiaohongshu", getPlatformSeed("xiaohongshu"))
    if adapter is None:
        record("小红书 carousel 不可用断言", False, "未取到 XiaohongshuAdapter")
        return

    rtn = adapter.render(topic, buildLayoutRecord("carousel"), assets, options = _xhsOptions())
    errList = []
    if rtn.get("errCode") != "C7":
        errList.append(f"未显式返回 C7: {rtn.get('errCode')}")
    if not rtn.get("errMsgList"):
        errList.append("缺少显式错误说明")
    record("小红书 carousel 显式不可用(C7, 不静默转换)", not errList, "; ".join(errList[:5]))


def assertXiaohongshuSwipeRatioGuard(topic):
    """★ swipe 比例不统一 -> 显式报错(不静默裁切); 张数超上限 -> C6"""
    adapter = platformAdapter.getAdapter("xiaohongshu", getPlatformSeed("xiaohongshu"))
    if adapter is None:
        record("小红书 swipe 比例/张数强校验断言", False, "未取到 XiaohongshuAdapter")
        return

    errList = []
    #构造 3:4 与 1:1 混用的附图(避免真截图: 校验应在渲染前拦截)
    mixedAssets = [
        {"fileID": "f_a", "fileUrl": "d:/nonexist/a.jpg", "usageType": "cover", "sortOrder": 10,
         "width": 1080, "height": 1440},
        {"fileID": "f_b", "fileUrl": "d:/nonexist/b.jpg", "usageType": "body", "sortOrder": 20,
         "width": 1080, "height": 1080},
    ]
    rtn = adapter.render(topic, buildLayoutRecord("swipe"), mixedAssets, options = _xhsOptions())
    if rtn.get("errCode") != "D1":
        errList.append(f"比例混用未显式返回 D1: {rtn.get('errCode')}")

    #张数超上限(19 > 18): 应在校验期拦截为 C6
    manyAssets = [{"fileID": f"f_{idx}", "fileUrl": "d:/nonexist/x.jpg", "usageType": "body",
                   "sortOrder": idx, "width": 1080, "height": 1440} for idx in range(19)]
    rtn2 = adapter.render(topic, buildLayoutRecord("swipe"), manyAssets, options = _xhsOptions())
    if rtn2.get("errCode") != "C6":
        errList.append(f"张数超上限未返回 C6: {rtn2.get('errCode')}")

    record("小红书 swipe 比例/张数强校验(不静默裁切)", not errList, "; ".join(errList[:5]))

#===== SP3b 小红书真实截图冒烟 end =====


#===== SP3c 合规校验 + 产物台账 + 渲染任务化冒烟 begin =====

def _raiseRedisDown(*_args, **_kwargs):
    """桩: 模拟 Redis 服务端不可用"""
    raise RuntimeError("redis server unavailable(smoke stub)")


def assertSensitiveWordOffsets():
    """★ 敏感词命中返回偏移区间(多命中, 供前端直接高亮)"""
    errList = []
    text = "前敏感词样例后敏感词样例尾"
    hits = complianceSvc.detectSensitiveWords(text, ["敏感词样例"])
    if len(hits) != 2:
        errList.append(f"多命中未生效: {hits}")
    else:
        for hit in hits:
            if text[hit["start"]:hit["end"]] != "敏感词样例":
                errList.append(f"偏移区间与实际命中不一致: {hit}")

    issues = complianceSvc.checkSensitiveWordIssues({"description": text}, ["敏感词样例"])
    print(f"[sp3c-word] hits={hits}")
    if len(issues) != 2:
        errList.append(f"问题项数 {len(issues)} != 2")
    if issues and not (issues[0].get("offsetStart") == 1 and issues[0].get("offsetEnd") == 6):
        errList.append(f"偏移区间不符: start={issues[0].get('offsetStart')}, end={issues[0].get('offsetEnd')}")
    if issues and issues[0].get("location") != "description[1,6]":
        errList.append(f"定位串不符: {issues[0].get('location')}")
    if issues and (issues[0].get("level") != complianceSvc.ISSUE_LEVEL_ERROR or not issues[0].get("errCode")):
        errList.append("敏感词问题级别/错误码缺失")
    record("SP3c 敏感词命中返回偏移区间(多命中)", not errList, "; ".join(errList[:5]))


def assertAiLabelGuard():
    """★ needAiLabelFlag=1 且缺 AI 标识 -> 被拦(ERROR); 已标识 / 非强制平台 -> 放行"""
    errList = []
    xhsSeed = getPlatformSeed("xiaohongshu")
    wechatSeed = getPlatformSeed("wechat_mp")
    if str(xhsSeed.get("needAiLabelFlag")) != "1":
        errList.append("小红书种子 needAiLabelFlag != 1")

    noLabel = {"title": "t", "description": "正文内容", "aiFlag": "1"}
    issues = complianceSvc.checkAiLabelIssues(xhsSeed, noLabel)
    if not issues or issues[0].get("level") != complianceSvc.ISSUE_LEVEL_ERROR:
        errList.append(f"缺标识未被拦: {issues}")
    if issues and issues[0].get("source") != complianceSvc.SOURCE_AI_LABEL:
        errList.append("AI 标识问题来源标记错误")

    if complianceSvc.checkAiLabelIssues(xhsSeed, {"title": "t", "description": "正文", "aiFlag": "1",
                                                 "aiLabel": "AI生成"}):
        errList.append("已提供 aiLabel 仍被拦")
    if complianceSvc.checkAiLabelIssues(xhsSeed, {"title": "t", "description": "本内容由AI生成, 仅供参考",
                                                 "aiFlag": "1"}):
        errList.append("正文含标识词仍被拦")
    if complianceSvc.checkAiLabelIssues(wechatSeed, noLabel):
        errList.append("非强制标识平台(wechat_mp)被误拦")
    record("SP3c needAiLabelFlag=1 缺标识被拦", not errList, "; ".join(errList[:5]))


def assertComplianceSpecViolations(layoutRecord):
    """★ 规格违例(标题超长/图片超量/比例不统一)命中问题清单且可定位"""
    errList = []
    xhsSeed = getPlatformSeed("xiaohongshu")

    topic = {"recID": "3001", "topicCode": "SP3C_SPEC", "title": "超长标题" * 10, "summary": "s",
             "description": "d", "aiFlag": "0"}
    mixedAssets = [
        {"fileID": "f0", "usageType": "cover", "sortOrder": 10, "width": 1080, "height": 1440},
        {"fileID": "f1", "usageType": "body", "sortOrder": 20, "width": 1080, "height": 1080},
        {"fileID": "f2", "usageType": "body", "sortOrder": 30, "width": 1080, "height": 1440},
    ]
    rtn = complianceSvc.evaluateCompliance(topic, mixedAssets, xhsSeed, layoutRecord)
    data = rtn.get("data") or {}
    issues = data.get("issues") or []
    print(f"[sp3c-spec] passed={data.get('passed')} errorCount={data.get('errorCount')} "
          f"issues={[(it.get('errCode'), it.get('location')) for it in issues]}")

    if data.get("passed") != "0":
        errList.append("规格违例未判为不通过(passed != 0)")
    titleIssues = [it for it in issues if str(it.get("field", "")).startswith("title")]
    if not titleIssues or titleIssues[0].get("errCode") != "C5":
        errList.append("标题超长未命中 C5")
    if not titleIssues or not titleIssues[0].get("location"):
        errList.append("标题问题不可定位(缺 location)")
    ratioIssues = [it for it in issues if str(it.get("location", "")).startswith("assetList[")]
    if not ratioIssues:
        errList.append("比例不统一未命中问题清单(应可定位到 assetList 下标)")
    if not any(it.get("errCode") == "D1" for it in issues):
        errList.append("比例不统一未落 D1")

    #图片超量(19 > ch_platform.imageMaxCount=18)
    manyAssets = [{"fileID": f"m{idx}", "usageType": "body", "sortOrder": idx,
                   "width": 1080, "height": 1440} for idx in range(19)]
    overRtn = complianceSvc.evaluateCompliance({"title": "t"}, manyAssets, xhsSeed, None)
    overIssues = (overRtn.get("data") or {}).get("issues") or []
    if not any(it.get("errCode") == "C6" for it in overIssues):
        errList.append("图片超量未命中 C6")
    record("SP3c 规格违例命中问题清单且可定位", not errList, "; ".join(errList[:6]))


def assertArtifactLedgerIdempotent():
    """★ ch_artifact 幂等键拼接正确(桩替换数据层, 断言 artifactKey 形态与 upsert 调用路径)"""
    errList = []
    calls = []
    origUpsert = comCh.upsertByUniqueKey
    origQueryArtifact = comMysql.query_ch_artifact
    try:
        comCh.upsertByUniqueKey = lambda tableName, uniqueValue, saveSet, queryFunc, insertFunc, updateFunc: (
            calls.append((tableName, uniqueValue, saveSet)) or 321)
        comMysql.query_ch_artifact = lambda *args, **kwargs: []

        saved = renderSvc.saveArtifacts(456, 1001, "xiaohongshu", [
            {"seqNo": 1, "kind": "png", "fileID": "fidA", "width": 1080, "height": 1440, "sizeBytes": 1000},
            {"seqNo": 2, "kind": "png", "fileID": "fidB", "width": 1080, "height": 1440, "sizeBytes": 2000},
        ])
    finally:
        comCh.upsertByUniqueKey = origUpsert
        comMysql.query_ch_artifact = origQueryArtifact

    expectKeys = ["456:png:xiaohongshu:1", "456:png:xiaohongshu:2"]
    realKeys = [item[1] for item in calls]
    print(f"[sp3c-artifact] artifactKeys={realKeys} status={[item[2].get('artifactStatus') for item in calls]}")
    if realKeys != expectKeys:
        errList.append(f"artifactKey 形态不符: {realKeys} != {expectKeys}")
    if any(item[0] != "ch_artifact" for item in calls):
        errList.append(f"upsert 未落在 ch_artifact: {[item[0] for item in calls]}")
    if any(item[2].get("artifactStatus") != "READY" for item in calls):
        errList.append("artifactStatus 应写 READY")
    if any(not item[2].get("expireYMDHMS") for item in calls):
        errList.append("expireYMDHMS 应写入(过期清理归 SP4, 本轮只写字段)")
    if [item[2].get("artifactVer") for item in calls] != [1, 1]:
        errList.append(f"初次写入 artifactVer 应为 1: {[item[2].get('artifactVer') for item in calls]}")
    if len(saved) != 2:
        errList.append(f"saveArtifacts 返回条数 {len(saved)} != 2")

    #同 job 重渲染 -> artifactVer +1
    bumpSets = []
    try:
        comCh.upsertByUniqueKey = lambda tableName, uniqueValue, saveSet, queryFunc, insertFunc, updateFunc: (
            bumpSets.append(saveSet) or 321)
        comMysql.query_ch_artifact = lambda *args, **kwargs: [
            {"recID": "9", "artifactKey": "456:png:xiaohongshu:1", "artifactVer": "3"}]
        renderSvc.saveArtifacts(456, 1001, "xiaohongshu", [
            {"seqNo": 1, "kind": "png", "fileID": "fidA2", "width": 1080, "height": 1440}])
    finally:
        comCh.upsertByUniqueKey = origUpsert
        comMysql.query_ch_artifact = origQueryArtifact
    if not bumpSets or bumpSets[0].get("artifactVer") != 4:
        errList.append(f"重渲染未递增 artifactVer: {[item.get('artifactVer') for item in bumpSets]}")
    record("SP3c ch_artifact 幂等键与写入路径", not errList, "; ".join(errList[:6]))


def assertJobStateMachine():
    """★ job 状态机非法跃迁被拒并回显允许集; 合法跃迁放行"""
    errList = []
    code, _field, message = renderSvc.checkJobStatusTransition("DONE", "RUNNING")
    if code != "C7":
        errList.append(f"DONE->RUNNING 未拒绝: {code}")
    if "允许跃迁" not in message:
        errList.append("非法跃迁未回显允许跃迁集")
    if renderSvc.checkJobStatusTransition("PENDING", "DONE")[0] != "C7":
        errList.append("PENDING->DONE(跳步) 未拒绝")
    for curr, new in (("PENDING", "RUNNING"), ("RUNNING", "DONE"), ("RUNNING", "FAILED"), ("FAILED", "PENDING")):
        if renderSvc.checkJobStatusTransition(curr, new)[0] != "":
            errList.append(f"合法跃迁 {curr}->{new} 被误拒")
    if "PENDING" not in renderSvc.JOB_STATUS_LIST or "DONE" not in renderSvc.JOB_STATUS_LIST:
        errList.append("JOB_STATUS_LIST 不完整")
    record("SP3c job 状态机非法跃迁被拒", not errList, "; ".join(errList[:5]))


def assertInputHashReuse(layoutRecord, platformSeed):
    """★ inputHash 相同 -> 复用分支命中(不重复渲染, 复用行为写进出参)"""
    errList = []
    topicRecord = {"recID": "4001", "topicCode": "SP3C_REUSE", "title": "复用标题", "summary": "s",
                   "description": "d", "coverFileID": "c1", "aiFlag": "0"}
    assetList = [{"fileID": "r1", "usageType": "cover", "sortOrder": 10, "width": 1080, "height": 1440}]
    inputHash = renderSvc.buildInputHash(topicRecord, layoutRecord, assetList, "xiaohongshu", None)

    originals = {
        "_fetchTopic": renderSvc._fetchTopic, "_fetchAssets": renderSvc._fetchAssets,
        "_mergeAssetMeta": renderSvc._mergeAssetMeta, "_fetchPlatformRecord": renderSvc._fetchPlatformRecord,
        "loadLayoutRecord": layoutEngine.loadLayoutRecord,
        "query_ch_render_job": comMysql.query_ch_render_job, "query_ch_artifact": comMysql.query_ch_artifact,
        "fillFileUrls": comCh.fillFileUrls,
    }
    try:
        renderSvc._fetchTopic = lambda dataSet: (topicRecord, None)
        renderSvc._fetchAssets = lambda topicID: (assetList, None)
        renderSvc._mergeAssetMeta = lambda aList: aList
        renderSvc._fetchPlatformRecord = lambda platformCode: (platformSeed, None)
        layoutEngine.loadLayoutRecord = lambda layoutCode: layoutRecord
        comMysql.query_ch_render_job = lambda *args, **kwargs: [
            {"recID": "88", "jobCode": "job_reuse", "inputHash": inputHash, "jobStatus": "DONE",
             "topicID": "4001", "platform": "xiaohongshu"}]
        comMysql.query_ch_artifact = lambda *args, **kwargs: [
            {"recID": "1", "artifactKey": "88:png:xiaohongshu:1", "fileID": "fidR", "seqNo": "1",
             "artifactVer": "1", "artifactStatus": "READY", "kind": "png"}]
        comCh.fillFileUrls = lambda aSet, fileFields = None, privateFlag = True: aSet

        rtn = renderSvc.renderTopic({"topicID": "4001", "layoutCode": "swipe_v1", "platform": "xiaohongshu"})
    finally:
        renderSvc._fetchTopic = originals["_fetchTopic"]
        renderSvc._fetchAssets = originals["_fetchAssets"]
        renderSvc._mergeAssetMeta = originals["_mergeAssetMeta"]
        renderSvc._fetchPlatformRecord = originals["_fetchPlatformRecord"]
        layoutEngine.loadLayoutRecord = originals["loadLayoutRecord"]
        comMysql.query_ch_render_job = originals["query_ch_render_job"]
        comMysql.query_ch_artifact = originals["query_ch_artifact"]
        comCh.fillFileUrls = originals["fillFileUrls"]

    data = rtn.get("data") or {}
    print(f"[sp3c-reuse] errCode={rtn.get('errCode')} reused={data.get('reused')} "
          f"jobID={data.get('jobID')} productCount={data.get('productCount')} inputHash={inputHash[:12]}...")
    if rtn.get("errCode") != "B0":
        errList.append(f"复用分支返回失败: {rtn.get('errCode')} {rtn.get('errMsgList')}")
    if data.get("reused") != "1":
        errList.append(f"未命中复用分支: reused={data.get('reused')}")
    if int(data.get("jobID") or 0) != 88:
        errList.append(f"复用未回显既有 jobID: {data.get('jobID')}")
    if data.get("productCount") != 1:
        errList.append(f"复用未回显既有产物数: {data.get('productCount')}")
    if not data.get("reuseReason"):
        errList.append("复用行为未写进出参(reuseReason 缺失)")
    record("SP3c inputHash 相同 -> 复用分支命中", not errList, "; ".join(errList[:6]))


def assertRateLimitDegrade():
    """★ Redis 不可用 -> 限流降级而非崩溃(degraded 标记可见)"""
    errList = []
    original = complianceSvc._redisCounterIncr
    try:
        complianceSvc._redisCounterIncr = _raiseRedisDown
        info = complianceSvc.checkPublishRateLimit("sp3c-acct", "xiaohongshu")
    finally:
        complianceSvc._redisCounterIncr = original

    print(f"[sp3c-ratelimit] {info}")
    if info.get("degraded") != "1":
        errList.append(f"未标记 degraded: {info}")
    if info.get("backend") != "memory":
        errList.append(f"降级后端非 memory: {info.get('backend')}")
    if info.get("allowed") != "1":
        errList.append("降级后不应直接拒绝")
    if int(info.get("count") or 0) <= 0:
        errList.append("降级后进程内计数未生效")

    issues = complianceSvc.checkRateLimitIssues(info)
    if not issues or issues[0].get("level") != complianceSvc.ISSUE_LEVEL_WARN:
        errList.append("降级未在问题清单中显式可见(WARN)")

    #真实调用(本机无 Redis 服务端): 不得崩溃, 返回结构完整
    realInfo = complianceSvc.checkPublishRateLimit("sp3c-acct-real", "xiaohongshu")
    print(f"[sp3c-ratelimit-real] backend={realInfo.get('backend')} degraded={realInfo.get('degraded')} "
          f"count={realInfo.get('count')}")
    if realInfo.get("allowed") not in ("0", "1"):
        errList.append(f"真实限流调用返回异常: {realInfo}")
    if not realInfo.get("backend"):
        errList.append("真实限流调用缺少 backend 标记")
    record("SP3c Redis 不可用 -> 限流降级而非崩溃", not errList, "; ".join(errList[:6]))


def _stubRenderOutlets(topicRecord, layoutRecord, platformSeed, uploadFileID = "stub_doc_fileid"):
    """桩替换 topicrender 的「取数 / 台账 / 上传 / 主题状态」出口(本机无库无文件服务, 但渲染编排真跑)。
       出参: (captured, restore); 断言结束后必须调用 restore() 复位。
       captured: products(传给 saveArtifacts 的产物清单) / jobStatusCalls / topicModifyCalls(每次主题状态改写入参)
                 / uploadObjectName / uploadFileExisted / uploadLocalPath"""
    captured = {"products": None, "jobStatusCalls": [], "topicModifyCalls": [], "topicModify": None,
                "uploadObjectName": "", "uploadFileExisted": False, "uploadLocalPath": ""}
    originals = {
        "_fetchTopic": renderSvc._fetchTopic, "_fetchAssets": renderSvc._fetchAssets,
        "_fetchPlatformRecord": renderSvc._fetchPlatformRecord, "_insertJob": renderSvc._insertJob,
        "updateJobStatus": renderSvc.updateJobStatus, "saveArtifacts": renderSvc.saveArtifacts,
        "findReusableJob": renderSvc.findReusableJob, "_renderViaAdapter": renderSvc._renderViaAdapter,
        "loadLayoutRecord": layoutEngine.loadLayoutRecord,
        "uploadArtifact": htmlToImage.uploadArtifact, "modifyTopic": topicSvc.modifyTopic,
    }

    renderSvc._fetchTopic = lambda dataSet: (topicRecord, None)
    renderSvc._fetchAssets = lambda topicID: ([], None)
    renderSvc._fetchPlatformRecord = lambda platformCode: (platformSeed, None)
    layoutEngine.loadLayoutRecord = lambda layoutCode: layoutRecord
    renderSvc.findReusableJob = lambda *args, **kwargs: None
    renderSvc._insertJob = lambda *args, **kwargs: 456
    renderSvc.updateJobStatus = lambda jobID, newStatus, **kwargs: (
        captured["jobStatusCalls"].append(newStatus)
        or {"errCode": "B0", "field": "", "errMsgList": [], "data": {}})

    def _captureArtifacts(jobID, topicID, platformCode, products, kind = "", expireDays = 0):
        captured["products"] = [dict(item) for item in (products or [])]
        first = captured["products"][0] if captured["products"] else {}
        return [{"artifactKey": renderSvc.buildArtifactKey(jobID, first.get("kind"), platformCode,
                                                          first.get("seqNo")),
                 "recID": 999, "artifactVer": 1, "fileID": first.get("fileID"), "seqNo": first.get("seqNo")}]

    renderSvc.saveArtifacts = _captureArtifacts

    def _captureUpload(localPath, objectName = "", privateFlag = True):
        captured["uploadObjectName"] = objectName
        captured["uploadLocalPath"] = localPath
        captured["uploadFileExisted"] = os.path.isfile(localPath)
        return uploadFileID

    htmlToImage.uploadArtifact = _captureUpload

    def _captureTopicModify(dataSet, sessionIDSet = None):
        captured["topicModifyCalls"].append(dict(dataSet))
        captured["topicModify"] = dict(dataSet)
        return {"errCode": "B0", "field": "", "errMsgList": [], "data": {"recID": dataSet.get("recID")}}

    topicSvc.modifyTopic = _captureTopicModify

    def restore():
        renderSvc._fetchTopic = originals["_fetchTopic"]
        renderSvc._fetchAssets = originals["_fetchAssets"]
        renderSvc._fetchPlatformRecord = originals["_fetchPlatformRecord"]
        renderSvc._insertJob = originals["_insertJob"]
        renderSvc.updateJobStatus = originals["updateJobStatus"]
        renderSvc.saveArtifacts = originals["saveArtifacts"]
        renderSvc.findReusableJob = originals["findReusableJob"]
        renderSvc._renderViaAdapter = originals["_renderViaAdapter"]
        layoutEngine.loadLayoutRecord = originals["loadLayoutRecord"]
        htmlToImage.uploadArtifact = originals["uploadArtifact"]
        topicSvc.modifyTopic = originals["modifyTopic"]

    return captured, restore


def assertDocumentArtifactRegistered():
    """★ 2026-09-24 修复回归(文档类形态产物 + 主题状态自动推进):
       公众号(wechat_mp)的 stack_v1 渲染(outputKind=html)适配器**不产 products**, 修复前
       saveArtifacts 被 products 空门控跳过 -> ch_artifact 无行 -> 前端产物页恒空态(现象: 任务 DONE 但无产物)。
       断言:
       ① 渲染成功后登记**单件**产物 kind=html / seqNo=1 / fileID 为上传返回值, 幂等键 {jobID}:html:{platform}:1;
       ② 落盘文件为可独立打开的 html(上传入参以 .html 结尾), 且上传后临时目录被清理;
       ③ 主题状态自动推进 RENDERING -> RENDERED(出参 statusAdvanced=1, 且只经 topicService.modifyTopic);
       ④ 通用平台 exportKind=markdown 同样留痕(kind=markdown, .md)。
       口径依据: 前端产物页直读 ch_artifact; 前端 Mock 的 ARTIFACT_KIND_BY_PLATFORM(wechat_mp -> html, 单件)。"""
    errList = []
    layoutRecord = buildLayoutRecord("stack")
    topicRecord = dict(buildPlatformTopic())
    topicRecord["recID"] = "6001"
    topicRecord["status"] = "RENDERING"     # 模拟前端提交渲染后的主题状态

    captured, restore = _stubRenderOutlets(topicRecord, layoutRecord, getPlatformSeed("wechat_mp"),
                                           uploadFileID = "stub_html_fileid")
    try:
        rtn = renderSvc.renderTopic({"topicID": "6001", "layoutCode": "stack_v1", "platform": "wechat_mp"})
    finally:
        restore()

    data = rtn.get("data") or {}
    products = captured["products"] or []
    first = products[0] if products else {}
    print(f"[sp3c-docartifact] errCode={rtn.get('errCode')} artifactCount={data.get('artifactCount')} "
          f"kind={first.get('kind')} seqNo={first.get('seqNo')} objectName={captured['uploadObjectName']} "
          f"statusAdvanced={data.get('statusAdvanced')} topicModifyStatus={(captured['topicModify'] or {}).get('status')}")

    if rtn.get("errCode") != "B0":
        errList.append(f"渲染失败: {rtn.get('errCode')} {rtn.get('errMsgList')}")
    if len(products) != 1:
        errList.append(f"文档类形态未登记单件产物: 产物数={len(products)}(修复前为 0)")
    if first.get("kind") != "html":
        errList.append(f"产物 kind 应为 html: {first.get('kind')}")
    if str(first.get("seqNo")) != "1":
        errList.append(f"单件产物 seqNo 应为 1: {first.get('seqNo')}")
    if first.get("fileID") != "stub_html_fileid":
        errList.append(f"产物 fileID 应为上传返回值: {first.get('fileID')}")
    if int(first.get("sizeBytes") or 0) <= 0:
        errList.append(f"产物未记录字节数: {first.get('sizeBytes')}")
    if not captured["uploadFileExisted"]:
        errList.append("上传前本地 html 文件不存在")
    if not str(captured["uploadObjectName"]).endswith(".html"):
        errList.append(f"上传对象名非 .html: {captured['uploadObjectName']}")
    if os.path.isdir(os.path.dirname(str(captured["uploadLocalPath"]))):
        errList.append(f"临时目录未清理: {captured['uploadLocalPath']}")
    if int(data.get("artifactCount") or 0) != 1:
        errList.append(f"出参 artifactCount={data.get('artifactCount')}(应 1)")
    if "DONE" not in captured["jobStatusCalls"]:
        errList.append(f"任务未收口 DONE: {captured['jobStatusCalls']}")
    if data.get("statusAdvanced") != "1":
        errList.append(f"主题状态未自动推进: statusAdvanced={data.get('statusAdvanced')}")
    if (captured["topicModify"] or {}).get("status") != "RENDERED" \
            or (captured["topicModify"] or {}).get("recID") != "6001":
        errList.append(f"主题状态推进入参不符: {captured['topicModify']}")
    record("SP3c 修复: 文档类形态(html)产物登记 + 主题状态自动推进 RENDERED", not errList, "; ".join(errList[:6]))

    #④ 通用平台 exportKind=markdown: kind=markdown + 落盘 .md(2026-09-24 扩 kind 取值后同样留痕)
    errList = []
    mdTopic = dict(topicRecord)
    mdTopic["recID"] = "6002"
    mdCaptured, mdRestore = _stubRenderOutlets(mdTopic, layoutRecord, getPlatformSeed("generic"),
                                              uploadFileID = "stub_md_fileid")
    try:
        mdRtn = renderSvc.renderTopic({"topicID": "6002", "layoutCode": "stack_v1",
                                       "platform": "generic", "exportKind": "markdown"})
    finally:
        mdRestore()

    mdProducts = mdCaptured["products"] or []
    mdFirst = mdProducts[0] if mdProducts else {}
    print(f"[sp3c-docartifact-md] errCode={mdRtn.get('errCode')} kind={mdFirst.get('kind')} "
          f"objectName={mdCaptured['uploadObjectName']} artifactCount={(mdRtn.get('data') or {}).get('artifactCount')}")
    if mdRtn.get("errCode") != "B0":
        errList.append(f"markdown 渲染失败: {mdRtn.get('errCode')} {mdRtn.get('errMsgList')}")
    if len(mdProducts) != 1 or mdFirst.get("kind") != "markdown":
        errList.append(f"markdown 形态未登记单件产物(kind=markdown): {mdProducts}")
    if mdFirst.get("fileID") != "stub_md_fileid":
        errList.append(f"markdown 产物 fileID 应为上传返回值: {mdFirst.get('fileID')}")
    if not str(mdCaptured["uploadObjectName"]).endswith(".md"):
        errList.append(f"markdown 上传对象名非 .md: {mdCaptured['uploadObjectName']}")
    record("SP3c 修复: markdown 形态产物登记(kind=markdown, .md)", not errList, "; ".join(errList[:6]))


def assertTopicStatusRollbackOnFail():
    """★ 2026-09-24 修复回归(渲染失败回落主题状态): 失败后主题不再永久卡在 RENDERING。
       覆盖三条出口:
       ① 平台配置不可用(渲染前置拦截) -> 主题回落 DRAFT 且出参回显 topicStatusRolledBack=1;
       ② 平台形态转换失败(渲染期失败) -> job FAILED + 主题回落 DRAFT + 无产物登记;
       ③ 主题非 RENDERING(如 DRAFT) -> 一律跳过(不产生多余写入)。"""
    errList = []
    layoutRecord = buildLayoutRecord("stack")
    topicRecord = dict(buildPlatformTopic())
    topicRecord["recID"] = "6101"
    topicRecord["status"] = "RENDERING"

    #① 平台不可用
    captured, restore = _stubRenderOutlets(topicRecord, layoutRecord, getPlatformSeed("wechat_mp"))
    try:
        renderSvc._fetchPlatformRecord = lambda platformCode: (
            None, {"errCode": "C7", "field": "platform", "errMsgList": ["平台已停用"], "data": {}})
        rtn1 = renderSvc.renderTopic({"topicID": "6101", "layoutCode": "stack_v1", "platform": "wechat_mp"})
    finally:
        restore()

    #② 渲染期失败(截图/产物类 E3)
    captured2, restore2 = _stubRenderOutlets(topicRecord, layoutRecord, getPlatformSeed("wechat_mp"))
    try:
        renderSvc._renderViaAdapter = lambda *args, **kwargs: (
            None, {"errCode": "E3", "field": "screenshot", "errMsgList": ["产物生成失败(截图)"], "data": {}})
        rtn2 = renderSvc.renderTopic({"topicID": "6101", "layoutCode": "stack_v1", "platform": "wechat_mp"})
    finally:
        restore2()

    #③ 主题非 RENDERING -> 跳过(不回落)
    captured3, restore3 = _stubRenderOutlets(topicRecord, layoutRecord, getPlatformSeed("wechat_mp"))
    try:
        renderSvc._fetchPlatformRecord = lambda platformCode: (
            None, {"errCode": "C7", "field": "platform", "errMsgList": ["平台已停用"], "data": {}})
        topicRecord["status"] = "DRAFT"
        rtn3 = renderSvc.renderTopic({"topicID": "6101", "layoutCode": "stack_v1", "platform": "wechat_mp"})
    finally:
        topicRecord["status"] = "RENDERING"
        restore3()

    print(f"[sp3c-rollback] platformErr={rtn1.get('errCode')}/{(rtn1.get('data') or {}).get('topicStatusRolledBack')} "
          f"renderErr={rtn2.get('errCode')}/{captured2['jobStatusCalls']}/"
          f"{(rtn2.get('data') or {}).get('topicStatusRolledBack')} skipCalls={len(captured3['topicModifyCalls'])}")

    if rtn1.get("errCode") != "C7":
        errList.append(f"平台不可用未按原错误码回显: {rtn1.get('errCode')}")
    if (rtn1.get("data") or {}).get("topicStatusRolledBack") != "1":
        errList.append(f"平台不可用未回显主题回落: {(rtn1.get('data') or {}).get('topicStatusRolledBack')}")
    if (captured["topicModify"] or {}).get("status") != "DRAFT":
        errList.append(f"平台不可用未把主题回落 DRAFT: {captured['topicModify']}")

    if rtn2.get("errCode") != "E3":
        errList.append(f"渲染失败错误码未透传: {rtn2.get('errCode')}")
    if "FAILED" not in captured2["jobStatusCalls"]:
        errList.append(f"任务未收口 FAILED: {captured2['jobStatusCalls']}")
    if (captured2["topicModify"] or {}).get("status") != "DRAFT":
        errList.append(f"渲染失败未把主题回落 DRAFT: {captured2['topicModify']}")
    if (rtn2.get("data") or {}).get("topicStatusRolledBack") != "1":
        errList.append(f"渲染失败未回显主题回落: {(rtn2.get('data') or {}).get('topicStatusRolledBack')}")
    if captured2["products"]:
        errList.append(f"失败任务不应登记产物: {captured2['products']}")

    if captured3["topicModifyCalls"]:
        errList.append(f"主题非 RENDERING 时不应改状态: {captured3['topicModifyCalls']}")
    if (rtn3.get("data") or {}).get("topicStatusRolledBack") != "0":
        errList.append(f"跳过回落时应回显 0: {(rtn3.get('data') or {}).get('topicStatusRolledBack')}")
    record("SP3c 修复: 渲染失败回落主题状态 RENDERING -> DRAFT(非 RENDERING 跳过)", not errList,
           "; ".join(errList[:6]))


def assertTopicStatusAdvanceOnReuse():
    """★ 2026-09-24 修复回归(复用分支同样收口主题状态):
       命中 inputHash 复用(不重复渲染)时, 本次渲染**已产出**(复用既有产物), 主题状态同样要
       RENDERING -> RENDERED; 否则「内容未变再次提交渲染」会把主题悬在 RENDERING(原始缺陷的另一入口)。"""
    errList = []
    layoutRecord = buildLayoutRecord("stack")
    topicRecord = dict(buildPlatformTopic())
    topicRecord["recID"] = "6003"
    topicRecord["status"] = "RENDERING"

    captured, restore = _stubRenderOutlets(topicRecord, layoutRecord, getPlatformSeed("wechat_mp"))
    originalFill = comCh.fillFileUrls
    try:
        renderSvc.findReusableJob = lambda *args, **kwargs: {
            "jobID": 88, "jobCode": "job_reuse_6003", "inputHash": "stub_input_hash",
            "artifacts": [{"seqNo": 1, "kind": "html", "fileID": "stub_reuse_fileid",
                           "thumbnailID": "", "artifactKey": "88:html:wechat_mp:1", "artifactVer": 1,
                           "artifactStatus": "READY", "specNote": "", "sizeBytes": 1024}]}
        comCh.fillFileUrls = lambda aSet, fileFields = None, privateFlag = True: aSet
        rtn = renderSvc.renderTopic({"topicID": "6003", "layoutCode": "stack_v1", "platform": "wechat_mp"})
    finally:
        comCh.fillFileUrls = originalFill
        restore()

    data = rtn.get("data") or {}
    print(f"[sp3c-reuse-status] errCode={rtn.get('errCode')} reused={data.get('reused')} "
          f"statusAdvanced={data.get('statusAdvanced')} topicModifyStatus={(captured['topicModify'] or {}).get('status')}")

    if rtn.get("errCode") != "B0" or data.get("reused") != "1":
        errList.append(f"复用分支未命中: errCode={rtn.get('errCode')} reused={data.get('reused')}")
    if data.get("statusAdvanced") != "1":
        errList.append(f"复用分支未推进主题状态: statusAdvanced={data.get('statusAdvanced')}")
    if (captured["topicModify"] or {}).get("status") != "RENDERED":
        errList.append(f"复用分支未把主题推进 RENDERED: {captured['topicModify']}")
    if captured["jobStatusCalls"]:
        errList.append(f"复用分支不应建任务/改任务状态: {captured['jobStatusCalls']}")
    record("SP3c 修复: 命中 inputHash 复用同样推进主题状态 RENDERED", not errList, "; ".join(errList[:6]))

#===== SP3c 冒烟 end =====


#===== SP4a 投递链路冒烟 begin =====
#★ 本机**无 MySQL/Redis 服务端, 且无公众号真实凭据**, 故:
#  - 凭据加解密为**真实执行**(AES-256-GCM 真加解密);
#  - 外链转存分支为**真实执行**(真实调用 inlineStyle.resolveImageUrl, transferFunc 为桩回调);
#  - 投递编排(合规闸门/幂等/二次确认/撤销窗/失败留痕)以「桩替换数据层 + 桩替换 HTTP 通道」验证(属**桩验证**);
#  - 结论中必须显式声明「未端到端打通真实平台」(无凭据)。

SP4A_TEST_KEY = "sp4a-smoke-passphrase-0123456789abcdef"
SP4A_APP_SECRET = "STUB-APPSECRET-SHOULD-NOT-LEAK"

SP4A_TOPIC = {
    "recID": "5001", "topicCode": "SP4A_PUSH", "title": "秋日citywalk路线推荐",
    "summary": "合规简介", "description": "正文内容, 无敏感词", "author": "内容中枢编辑部",
    "coverFileID": "c1", "aiFlag": "0", "status": "RENDERED",
}
SP4A_ASSETS = [
    {"fileID": "s_cover", "fileUrl": "https://mmbiz.qpic.cn/cover.jpg", "usageType": "cover",
     "sortOrder": 10, "width": 900, "height": 500},
    {"fileID": "s_body_1", "fileUrl": "https://mmbiz.qpic.cn/b1.jpg", "usageType": "body",
     "sortOrder": 20, "width": 1080, "height": 1440},
]


class Sp4aStubState:
    """SP4a 桩状态: 模拟 ch_publish_record / ch_account / ch_audit_log 的读写与捕获"""

    def __init__(self):
        self.records = {}
        self.auditRows = []
        self.accountUpdates = []
        self.deliverRtn = None
        self.deliverCallCount = 0
        self.adapter = None
        self.accountRecord = {}

    def queryPublishRecords(self, **kwargs):
        recID = int(kwargs.get("recID") or 0)
        key = str(kwargs.get("idempotencyKey") or "")
        if recID > 0:
            return [dict(row) for row in self.records.values() if int(row.get("recID") or 0) == recID]
        if key:
            return [dict(row) for row in self.records.values() if row.get("idempotencyKey") == key]
        return []

    def insertPublishRecord(self, saveSet):
        recID = len(self.records) + 1
        row = dict(saveSet)
        row["recID"] = recID
        self.records[recID] = row
        return recID

    def updatePublishRecord(self, recID, saveSet):
        row = self.records.get(int(recID))
        if row:
            row.update(saveSet)
        return 1

    def appendAudit(self, saveSet):
        self.auditRows.append(dict(saveSet))
        return len(self.auditRows)


def buildSp4aAccount():
    """构造 ch_account 记录: 凭据密文由 AES-256-GCM 真实加密(密钥为冒烟测试口令)"""
    plainSecret = json.dumps({"appSecret": SP4A_APP_SECRET}, ensure_ascii = False)
    encRtn = credCipher.encrypt(plainSecret, rawKey = SP4A_TEST_KEY)
    return {
        "recID": "77", "accountCode": "smoke_wx", "platform": "wechat_mp",
        "accountName": "冒烟公众号", "subjectType": "enterprise", "verifiedFlag": "1",
        "capability": "draft_box", "appID": "wx-smoke-appid",
        "credentialCipher": encRtn["cipher"], "credentialIV": encRtn["iv"],
        "expireYMDHMS": "20991231235959", "healthStatus": "OK",
    }


def buildSp4aAdapter(state):
    """桩替换微信通道(不真实联网): render/package/deliver/fetchAccessToken/submitFreePublish"""
    class _Sp4aFakeAdapter:
        platformCode = "wechat_mp"
        deliverMode = "draft_box"

        def fetchAccessToken(self, appID, appSecret, timeout = None):
            return {"errCode": "B0", "field": "", "errMsgList": [],
                    "data": {"accessToken": "STUB-TOKEN", "expiresIn": 7200}}

        def buildTransferFunc(self, accessToken, timeout = None):
            return None

        def render(self, topicData, layoutRecord, assetList, overrideSpec = None, options = None):
            return {"errCode": "B0", "field": "", "errMsgList": [],
                    "data": {"outputKind": "html", "content": "<p>stub</p>",
                             "meta": {"platformCode": "wechat_mp", "deliverMode": "draft_box"}}}

        def package(self, renderResult, topicData, assetList, options = None):
            return {"errCode": "B0", "field": "", "errMsgList": [],
                    "data": {"packageKind": "wechat_draft_payload",
                             "title": (topicData or {}).get("title"), "content": "<p>stub</p>",
                             "coverUrl": "https://mmbiz.qpic.cn/cover.jpg", "images": []}}

        def deliver(self, packageResult = None, options = None):
            state.deliverCallCount += 1
            if state.deliverRtn is not None:
                return state.deliverRtn
            return {"errCode": "B0", "field": "", "errMsgList": [],
                    "data": {"remoteID": "DRAFT-MEDIA-1", "errcode": 0, "errmsg": "ok",
                             "transferredImageCount": 0}}

        def submitFreePublish(self, accessToken, mediaID, timeout = None):
            return {"errCode": "B0", "field": "", "errMsgList": [], "data": {"publishID": "PUB-1"}}

    return _Sp4aFakeAdapter()


def runSp4aService(state, serviceFunc, dataSet, topicRecord = None, assetList = None):
    """在「桩替换数据层 + 桩替换 HTTP 通道」下执行 publishService 的业务入口"""
    topicRecord = SP4A_TOPIC if topicRecord is None else topicRecord
    assetList = SP4A_ASSETS if assetList is None else assetList
    layoutRecord = buildLayoutRecord("stack")
    platformSeed = getPlatformSeed("wechat_mp")

    originals = {
        "_fetchPlatformRecord": renderSvc._fetchPlatformRecord,
        "_fetchTopic": renderSvc._fetchTopic,
        "_fetchAssets": renderSvc._fetchAssets,
        "_mergeAssetMeta": renderSvc._mergeAssetMeta,
        "_resolveOverrideSpec": renderSvc._resolveOverrideSpec,
        "loadLayoutRecord": layoutEngine.loadLayoutRecord,
        "getAdapter": platformAdapter.getAdapter,
        "query_ch_account": comMysql.query_ch_account,
        "update_ch_account": comMysql.update_ch_account,
        "query_ch_artifact": comMysql.query_ch_artifact,
        "query_ch_publish_record": comMysql.query_ch_publish_record,
        "insert_ch_publish_record": comMysql.insert_ch_publish_record,
        "update_ch_publish_record": comMysql.update_ch_publish_record,
        "insert_ch_audit_log": comMysql.insert_ch_audit_log,
        "rateLimit": complianceSvc.checkPublishRateLimit,
    }
    try:
        renderSvc._fetchPlatformRecord = lambda platformCode: (platformSeed, None)
        renderSvc._fetchTopic = lambda dataSet2: (topicRecord, None)
        renderSvc._fetchAssets = lambda topicID: (assetList, None)
        renderSvc._mergeAssetMeta = lambda aList: aList
        renderSvc._resolveOverrideSpec = lambda dataSet2: None
        layoutEngine.loadLayoutRecord = lambda layoutCode: layoutRecord
        platformAdapter.getAdapter = lambda platformCode, platformRecord = None: state.adapter
        comMysql.query_ch_account = lambda *args, **kwargs: [state.accountRecord]
        comMysql.update_ch_account = lambda *args, **kwargs: (
            state.accountUpdates.append((args, kwargs)) or 1)
        comMysql.query_ch_artifact = lambda *args, **kwargs: []
        comMysql.query_ch_publish_record = lambda *args, **kwargs: state.queryPublishRecords(**kwargs)
        comMysql.insert_ch_publish_record = lambda tableName, saveSet: state.insertPublishRecord(saveSet)
        comMysql.update_ch_publish_record = lambda tableName, recID, saveSet: \
            state.updatePublishRecord(recID, saveSet)
        comMysql.insert_ch_audit_log = lambda tableName, saveSet: state.appendAudit(saveSet)
        #限流: 复用 SP3c 已验证的降级路径, 此处桩为「已放行」以免每条用例都去探 Redis
        complianceSvc.checkPublishRateLimit = lambda accountID, platformCode = "", limitCount = None, \
            windowSeconds = None: {"accountID": accountID, "platform": platformCode,
                                   "limitCount": 30, "windowSeconds": 3600, "count": 1,
                                   "allowed": "1", "backend": "memory", "degraded": "0", "errorMsg": ""}
        return serviceFunc(dataSet, {"loginID": "smoke", "roleName": "admin"})
    finally:
        renderSvc._fetchPlatformRecord = originals["_fetchPlatformRecord"]
        renderSvc._fetchTopic = originals["_fetchTopic"]
        renderSvc._fetchAssets = originals["_fetchAssets"]
        renderSvc._mergeAssetMeta = originals["_mergeAssetMeta"]
        renderSvc._resolveOverrideSpec = originals["_resolveOverrideSpec"]
        layoutEngine.loadLayoutRecord = originals["loadLayoutRecord"]
        platformAdapter.getAdapter = originals["getAdapter"]
        comMysql.query_ch_account = originals["query_ch_account"]
        comMysql.update_ch_account = originals["update_ch_account"]
        comMysql.query_ch_artifact = originals["query_ch_artifact"]
        comMysql.query_ch_publish_record = originals["query_ch_publish_record"]
        comMysql.insert_ch_publish_record = originals["insert_ch_publish_record"]
        comMysql.update_ch_publish_record = originals["update_ch_publish_record"]
        comMysql.insert_ch_audit_log = originals["insert_ch_audit_log"]
        complianceSvc.checkPublishRateLimit = originals["rateLimit"]


def buildSp4aState():
    """新建一套干净的桩状态 + 假适配器, 并把 token 缓存清空(用例间互不影响)"""
    state = Sp4aStubState()
    state.accountRecord = buildSp4aAccount()
    state.adapter = buildSp4aAdapter(state)
    publishSvc.clearAccessTokenCache()
    return state


def buildSp4aPushDataSet(state, nonce, extra = None):
    """构造一次合法投递请求(含二次确认参数)"""
    key = publishSvc.buildIdempotencyKey(0, 77, nonce)
    dataSet = {
        "action": "push", "platform": "wechat_mp", "topicID": "5001", "layoutCode": "stack_v1",
        "accountID": "77", "idempotencyKey": key,
        publishSvc.CONFIRM_FLAG_KEY: "1",
        publishSvc.CONFIRM_TOKEN_KEY: publishSvc.buildConfirmToken(key),
        "ownerID": "smoke", "_IP": "127.0.0.1",
    }
    if extra:
        dataSet.update(extra)
    return dataSet


def assertSp4aCredentialCipher():
    """★ 加密→解密往返一致、密文与明文不同、无密钥时不崩溃"""
    errList = []
    try:
        encRtn = credCipher.encrypt("PLAINTEXT-42", rawKey = SP4A_TEST_KEY)
        cipherText = encRtn.get("cipher", "")
        iv = encRtn.get("iv", "")
        print(f"[sp4a-cipher] alg={encRtn.get('alg')} cipherLen={len(cipherText)} ivLen={len(iv)}")
        if not cipherText or not iv:
            errList.append("encrypt 未返回 cipher/iv")
        if "PLAINTEXT" in cipherText:
            errList.append("密文中出现明文痕迹")
        if credCipher.decrypt(cipherText, iv, rawKey = SP4A_TEST_KEY) != "PLAINTEXT-42":
            errList.append("加解密往返不一致")
        if credCipher.maskSecret("abcdefghij") == "abcdefghij":
            errList.append("maskSecret 未脱敏")

        savedKey = os.environ.pop(credCipher.KEY_ENV_NAME, None)
        try:
            if credCipher.isKeyConfigured():
                errList.append("无密钥时 isKeyConfigured 仍为真")
            try:
                credCipher.encrypt("x")
                errList.append("无密钥时 encrypt 未显式报错")
            except credCipher.CredentialCipherError:
                pass
            except Exception as e:
                errList.append(f"无密钥时抛出非 CredentialCipherError: {type(e).__name__}")
        finally:
            if savedKey is not None:
                os.environ[credCipher.KEY_ENV_NAME] = savedKey
    except Exception as e:
        errList.append(f"凭据加解密断言失败: {e}")
    record("SP4a 凭据 AES-256-GCM 往返与无密钥行为", not errList, "; ".join(errList[:5]))


def assertSp4aAccountCredentialRoundtrip():
    """★ ch_account 凭据读写闭环: 加密写入(credentialCipher/credentialIV, 明文不落库) -> 读回解密一致"""
    errList = []
    captured = {}
    origUpdate = comMysql.update_ch_account
    try:
        comMysql.update_ch_account = lambda tableName, recID, saveSet: (
            captured.update({"recID": recID, "saveSet": saveSet}) or 1)
        recID, errRtn = publishSvc.saveAccountCredential(88, SP4A_APP_SECRET, appID = "wx-smoke-appid",
                                                         expireYMDHMS = "20991231235959",
                                                         rawKey = SP4A_TEST_KEY)
    finally:
        comMysql.update_ch_account = origUpdate

    saveSet = captured.get("saveSet") or {}
    print(f"[sp4a-account] recID={recID} err={errRtn} cipherLen={len(str(saveSet.get('credentialCipher') or ''))}")
    if errRtn or int(recID or 0) != 88:
        errList.append(f"凭据写入失败: {errRtn}")
    if not saveSet.get("credentialCipher") or not saveSet.get("credentialIV"):
        errList.append("未写入 credentialCipher/credentialIV")
    if SP4A_APP_SECRET in json.dumps(saveSet, ensure_ascii = False):
        errList.append("凭据明文落库(违反 R-19)")
    try:
        plainSecret = credCipher.decrypt(saveSet.get("credentialCipher"), saveSet.get("credentialIV"),
                                         rawKey = SP4A_TEST_KEY)
        if SP4A_APP_SECRET not in plainSecret:
            errList.append("读回解密结果与写入不一致")
    except Exception as e:
        errList.append(f"读回解密失败: {e}")
    record("SP4a ch_account 凭据读写闭环(密文落库/明文不落库)", not errList, "; ".join(errList[:5]))


def assertSp4aInlineTransferBranch():
    """★ 外链图片真实转存分支: transferFunc 就绪 -> 替换为平台地址; 转存失败 -> 仍显式 E4"""
    errList = []
    transferredUrl = "https://mmbiz.qpic.cn/transferred.jpg"

    def _transferOk(imageUrl):
        return transferredUrl

    def _transferFail(imageUrl):
        raise RuntimeError("stub transfer failure")

    rtn = inlineStyle.resolveImageUrl("https://example.com/a.jpg", ["mmbiz.qpic.cn"],
                                      transferFunc = _transferOk)
    print(f"[sp4a-transfer] errCode={rtn.get('errCode')} url={rtn.get('url')} transferred={rtn.get('transferred')}")
    if rtn.get("errCode") != "B0" or not rtn.get("transferred") or rtn.get("url") != transferredUrl:
        errList.append(f"转存成功后未返回平台地址: {rtn}")

    failRtn = inlineStyle.resolveImageUrl("https://example.com/a.jpg", ["mmbiz.qpic.cn"],
                                          transferFunc = _transferFail)
    if failRtn.get("errCode") != "E4":
        errList.append(f"转存失败未保持 E4: {failRtn.get('errCode')}")

    sample = '<p><img src="https://example.com/a.jpg"/></p>'
    inlineRtn = inlineStyle.inlineHtml(sample, ["mmbiz.qpic.cn"], transferFunc = _transferOk)
    inlineData = inlineRtn.get("data") or {}
    if inlineRtn.get("errCode") != "B0" or transferredUrl not in inlineData.get("content", ""):
        errList.append("inlineHtml 未把外链替换为转存后的平台地址")
    if inlineData.get("transferredImageCount") != 1:
        errList.append(f"transferredImageCount={inlineData.get('transferredImageCount')}")
    record("SP4a 外链图片真实转存分支(transferFunc)", not errList, "; ".join(errList[:5]))


def assertSp4aComplianceBlocks():
    """★ 未过合规校验(敏感词命中) -> 拒绝投递, 不调用通道, 且审计 FAIL 留痕"""
    errList = []
    state = buildSp4aState()
    dataSet = buildSp4aPushDataSet(state, "compliance")
    badTopic = dict(SP4A_TOPIC)
    badTopic["description"] = "这里有敏感词样例, 应被闸门拦截"

    rtn = runSp4aService(state, publishSvc.publishPush, dataSet, topicRecord = badTopic)
    print(f"[sp4a-compliance] errCode={rtn.get('errCode')} field={rtn.get('field')} "
          f"deliverCalls={state.deliverCallCount}")
    if rtn.get("errCode") != "C7":
        errList.append(f"未过合规校验未返回 C7(敏感词): {rtn.get('errCode')}")
    if state.deliverCallCount != 0:
        errList.append("未过合规校验仍调用了投递通道")
    if state.records:
        errList.append("未过合规校验仍写入了发布记录")
    if not state.auditRows or state.auditRows[0].get("result") != "FAIL":
        errList.append("合规拦截未留审计 FAIL")
    record("SP4a 未过合规校验 -> 拒绝投递", not errList, "; ".join(errList[:5]))


def assertSp4aConfirmRequired():
    """★ 二次确认必填: 缺失 confirmFlag/confirmToken -> F4, 且不落库、不投递"""
    errList = []
    state = buildSp4aState()
    dataSet = {"action": "push", "platform": "wechat_mp", "topicID": "5001",
               "layoutCode": "stack_v1", "accountID": "77"}

    rtn = runSp4aService(state, publishSvc.publishPush, dataSet)
    data = rtn.get("data") or {}
    print(f"[sp4a-confirm] errCode={rtn.get('errCode')} confirmToken={str(data.get('confirmToken'))[:12]}...")
    if rtn.get("errCode") != "F4":
        errList.append(f"二次确认缺失未返回 F4: {rtn.get('errCode')}")
    if not data.get("idempotencyKey") or not data.get("confirmToken"):
        errList.append("未回显 idempotencyKey/confirmToken(无法完成二次确认)")
    if state.deliverCallCount != 0 or state.records:
        errList.append("二次确认缺失仍产生副作用(投递/落库)")

    #令牌不匹配 -> 仍拒绝
    mismatched = buildSp4aPushDataSet(state, "confirm-bad")
    mismatched[publishSvc.CONFIRM_TOKEN_KEY] = "not-the-token"
    rtn2 = runSp4aService(state, publishSvc.publishPush, mismatched)
    if rtn2.get("errCode") != "F4":
        errList.append(f"确认令牌不匹配未返回 F4: {rtn2.get('errCode')}")
    record("SP4a 二次确认必填(缺失/不匹配 -> F4)", not errList, "; ".join(errList[:5]))


def assertSp4aIdempotency():
    """★ 幂等: 相同 idempotencyKey 二次提交被拒(F1)且不产生第二条发布记录"""
    errList = []
    state = buildSp4aState()
    dataSet = buildSp4aPushDataSet(state, "dup")

    firstRtn = runSp4aService(state, publishSvc.publishPush, dataSet)
    firstData = firstRtn.get("data") or {}
    print(f"[sp4a-idempotent-1] errCode={firstRtn.get('errCode')} remoteID={firstData.get('remoteID')} "
          f"records={len(state.records)}")
    if firstRtn.get("errCode") != "B0":
        errList.append(f"首次投递失败: {firstRtn.get('errCode')} {firstRtn.get('errMsgList')}")
    if len(state.records) != 1:
        errList.append(f"首次投递发布记录数 {len(state.records)} != 1")
    firstRecord = list(state.records.values())[0] if state.records else {}
    if firstRecord.get("success") != "1" or not firstRecord.get("remoteID"):
        errList.append(f"首次投递记录字段不完整: success={firstRecord.get('success')}, remoteID={firstRecord.get('remoteID')}")

    secondRtn = runSp4aService(state, publishSvc.publishPush, dict(dataSet))
    print(f"[sp4a-idempotent-2] errCode={secondRtn.get('errCode')} records={len(state.records)} "
          f"deliverCalls={state.deliverCallCount}")
    if secondRtn.get("errCode") != "F1":
        errList.append(f"二次提交未返回 F1: {secondRtn.get('errCode')}")
    if len(state.records) != 1:
        errList.append(f"二次提交产生了第二条发布记录(总 {len(state.records)})")
    if state.deliverCallCount != 1:
        errList.append(f"二次提交重复调用了投递通道(次数 {state.deliverCallCount})")
    record("SP4a 幂等: 二次提交被拒且不产生第二条记录", not errList, "; ".join(errList[:6]))


def assertSp4aRevokeWindow():
    """★ 撤销窗状态机: 窗内可撤销 / 逾窗拒绝 / 已撤销幂等"""
    errList = []
    state = buildSp4aState()
    pushRtn = runSp4aService(state, publishSvc.publishPush, buildSp4aPushDataSet(state, "revoke"))
    if pushRtn.get("errCode") != "B0":
        record("SP4a 撤销窗(窗内可撤销/逾窗拒绝)", False,
               f"前置投递失败: {pushRtn.get('errCode')} {pushRtn.get('errMsgList')}")
        return

    #窗内撤销
    revokeRtn = runSp4aService(state, publishSvc.revokePublish,
                               {"action": "revoke", "publishRecordID": "1"})
    revokeData = revokeRtn.get("data") or {}
    print(f"[sp4a-revoke-in] errCode={revokeRtn.get('errCode')} revoked={revokeData.get('revoked')} "
          f"elapsed={revokeData.get('elapsedSeconds')}s")
    if revokeRtn.get("errCode") != "B0" or revokeData.get("revoked") != "1":
        errList.append(f"窗内撤销失败: {revokeRtn.get('errCode')} {revokeRtn.get('errMsgList')}")
    if state.records.get(1, {}).get("delFlag") != "1":
        errList.append("撤销未把发布记录置 delFlag=1")
    if not any(row.get("action") == "publish.revoke" and row.get("result") == "OK"
               for row in state.auditRows):
        errList.append("撤销未留审计 OK")

    #逾窗: 造一条 120s 前推送的记录
    oldTime = (datetime.datetime.now() - datetime.timedelta(seconds = 120)).strftime("%Y%m%d%H%M%S")
    state.records[2] = {"recID": 2, "idempotencyKey": "0:77:old", "success": "1", "delFlag": "0",
                        "pushedYMDHMS": oldTime, "remoteID": "DRAFT-OLD"}
    overRtn = runSp4aService(state, publishSvc.revokePublish,
                             {"action": "revoke", "publishRecordID": "2"})
    print(f"[sp4a-revoke-over] errCode={overRtn.get('errCode')} "
          f"elapsed={(overRtn.get('data') or {}).get('elapsedSeconds')}s")
    if overRtn.get("errCode") != "F5":
        errList.append(f"逾窗撤销未返回 F5: {overRtn.get('errCode')}")
    if state.records.get(2, {}).get("delFlag") == "1":
        errList.append("逾窗记录仍被撤销")

    #已撤销 -> 幂等命中
    againRtn = runSp4aService(state, publishSvc.revokePublish,
                              {"action": "revoke", "publishRecordID": "1"})
    if againRtn.get("errCode") != "F1":
        errList.append(f"重复撤销未返回 F1: {againRtn.get('errCode')}")
    record("SP4a 撤销窗(窗内可撤销/逾窗拒绝)", not errList, "; ".join(errList[:6]))


def assertSp4aDeliverFailureAudited():
    """★ 投递失败路径: 平台 errcode/errmsg 落库 + 审计 FAIL 留痕 + 凭据明文不入审计"""
    errList = []
    state = buildSp4aState()
    state.deliverRtn = {"errCode": "F3", "field": "draftAdd(publishpush)",
                        "errMsgList": ["微信接口返回 errcode=45009, errmsg=api freq out of limit"],
                        "data": {"errcode": 45009, "errmsg": "api freq out of limit", "deliverErrCode": "F3"}}
    dataSet = buildSp4aPushDataSet(state, "fail")

    rtn = runSp4aService(state, publishSvc.publishPush, dataSet)
    print(f"[sp4a-fail] errCode={rtn.get('errCode')} records={len(state.records)} "
          f"auditFails={len([r for r in state.auditRows if r.get('result') == 'FAIL'])}")
    if rtn.get("errCode") != "F3":
        errList.append(f"投递失败未透出 F3: {rtn.get('errCode')}")
    savedRecord = list(state.records.values())[0] if state.records else {}
    if savedRecord.get("success") != "0":
        errList.append(f"投递失败未落库 success=0: {savedRecord.get('success')}")
    if "45009" not in str(savedRecord.get("errcode")) or "freq" not in str(savedRecord.get("errmsg")):
        errList.append(f"失败原因未可读落库: errcode={savedRecord.get('errcode')}, errmsg={savedRecord.get('errmsg')}")
    auditFails = [row for row in state.auditRows if row.get("result") == "FAIL"]
    if not auditFails:
        errList.append("投递失败未留审计 FAIL")
    elif not auditFails[-1].get("errMsg"):
        errList.append("审计 FAIL 缺少错误说明")
    #凭据红线: 审计/记录中不得出现凭据明文
    blob = json.dumps(state.auditRows, ensure_ascii = False) + json.dumps(state.records, ensure_ascii = False)
    if SP4A_APP_SECRET in blob:
        errList.append("审计/发布记录中出现凭据明文(违反 R-19)")
    record("SP4a 投递失败: 错误码+errmsg 落库 + 审计 FAIL", not errList, "; ".join(errList[:6]))


def assertSp4aAutoPublishDefaultOff():
    """★ 推送≠发布: freepublish 默认关闭, 请求自动发布 -> 显式 F6 拒绝且不投草稿"""
    errList = []
    state = buildSp4aState()
    dataSet = buildSp4aPushDataSet(state, "autopub", extra = {"autoPublish": "1"})

    rtn = runSp4aService(state, publishSvc.publishPush, dataSet)
    print(f"[sp4a-autopublish] errCode={rtn.get('errCode')} deliverCalls={state.deliverCallCount}")
    if rtn.get("errCode") != "F6":
        errList.append(f"自动发布未显式拒绝 F6: {rtn.get('errCode')}")
    if state.deliverCallCount != 0 or state.records:
        errList.append("自动发布被拒时仍产生了草稿投递/落库")

    #即便显式人工确认, 平台/配置未开仍拒绝(绝不默认群发)
    confirmed = buildSp4aPushDataSet(state, "autopub2",
                                     extra = {"autoPublish": "1", "autoPublishConfirm": "1"})
    rtn2 = runSp4aService(state, publishSvc.publishPush, confirmed)
    if rtn2.get("errCode") != "F6":
        errList.append(f"三重闸门未齐仍放行自动发布: {rtn2.get('errCode')}")
    record("SP4a 自动发布默认关闭 -> 显式拒绝(F6, 绝不群发)", not errList, "; ".join(errList[:5]))


def runSp4aSmoke():
    """SP4a 冒烟入口: 设置凭据密钥(仅本机自验)并逐项断言"""
    savedKey = os.environ.get(credCipher.KEY_ENV_NAME)
    os.environ[credCipher.KEY_ENV_NAME] = SP4A_TEST_KEY
    try:
        assertSp4aCredentialCipher()
        assertSp4aAccountCredentialRoundtrip()
        assertSp4aInlineTransferBranch()
        assertSp4aComplianceBlocks()
        assertSp4aConfirmRequired()
        assertSp4aIdempotency()
        assertSp4aRevokeWindow()
        assertSp4aDeliverFailureAudited()
        assertSp4aAutoPublishDefaultOff()
    finally:
        if savedKey is None:
            os.environ.pop(credCipher.KEY_ENV_NAME, None)
        else:
            os.environ[credCipher.KEY_ENV_NAME] = savedKey

#===== SP4a 投递链路冒烟 end =====


#===== SP4b 素材包 ZIP 导出冒烟(★ 用 SP3b 真实产物打 ZIP) begin =====
#★ 本机无 MySQL 服务端, 故「台账取数」为桩替换; 其余(合规校验 / 文件 sha256 / ZIP 组装 /
#  经文件门面真实上传与按 fileID 取回)均为**真实执行**。

ARTIFACT_DIR = os.path.join(_CODE_DIR, "data", "assetpack")

SP4B_ASSET_PACK_TEXT_ENTRIES = [
    "title.txt", "content.txt", "manifest.json",
    "COPYRIGHT.txt", "RISK_NOTICE.txt", "SWIPE_TIPS.txt",
]


def _buildPackAssets(count = 4):
    """素材包冒烟专用附图(全部 1080x1440 / 3:4): 保证 swipe 专项与超长图前置拦截均通过"""
    assetList = []
    for index in range(count):
        assetList.append({
            "fileID": f"pack_f{index + 1}",
            "fileUrl": os.path.join(ASSET_DIR, f"asset_{index + 1}.jpg"),
            "caption": f"素材包图 {index + 1}",
            "usageType": "cover" if index == 0 else "body",
            "sortOrder": 10 + index * 10,
            "width": 1080, "height": 1440,
        })
    return assetList


def _runArtifactPack(topicRecord, packAssets, layoutRecord, platformSeed, dataSet, extra = None):
    """在「桩替换取数」下执行 artifactService.exportAssetPack(合规/ZIP/上传均真实执行)"""
    originals = {
        "_fetchTopic": renderSvc._fetchTopic,
        "_fetchAssets": renderSvc._fetchAssets,
        "_mergeAssetMeta": renderSvc._mergeAssetMeta,
        "_fetchPlatformRecord": renderSvc._fetchPlatformRecord,
        "loadLayoutRecord": layoutEngine.loadLayoutRecord,
        "fillFileUrls": comCh.fillFileUrls,
        "query_ch_artifact": comMysql.query_ch_artifact,
    }
    try:
        renderSvc._fetchTopic = lambda dataSet2: (topicRecord, None)
        renderSvc._fetchAssets = lambda topicID: (packAssets, None)
        renderSvc._mergeAssetMeta = lambda aList: aList
        renderSvc._fetchPlatformRecord = lambda platformCode: (platformSeed, None)
        layoutEngine.loadLayoutRecord = lambda layoutCode: layoutRecord
        comCh.fillFileUrls = lambda aSet, fileFields = None, privateFlag = True: aSet
        if extra and extra.get("artifactRecords") is not None:
            comMysql.query_ch_artifact = lambda *args, **kwargs: extra["artifactRecords"]
        return artifactSvc.exportAssetPack(dataSet, {"loginID": "smoke"})
    finally:
        renderSvc._fetchTopic = originals["_fetchTopic"]
        renderSvc._fetchAssets = originals["_fetchAssets"]
        renderSvc._mergeAssetMeta = originals["_mergeAssetMeta"]
        renderSvc._fetchPlatformRecord = originals["_fetchPlatformRecord"]
        layoutEngine.loadLayoutRecord = originals["loadLayoutRecord"]
        comCh.fillFileUrls = originals["fillFileUrls"]
        comMysql.query_ch_artifact = originals["query_ch_artifact"]


def _assertZipStructure(rtn, expectedImageCount, topicRecord, name):
    """逐项断言 7.8 自动可判定项(ZIP 条目 / 命名与顺序 / manifest / 风险告知 / 校验值)"""
    errList = []
    data = rtn.get("data") or {}
    zipPath = data.get("localZipPath") or ""

    if rtn.get("errCode") != "B0":
        record(name, False, f"导出失败: {rtn.get('errCode')} {rtn.get('errMsgList')}")
        return

    if not data.get("fileID"):
        errList.append("未返回 fileID(未上传)")
    if data.get("deliverMode") != "asset_pack":
        errList.append(f"deliverMode={data.get('deliverMode')} != asset_pack")
    if (data.get("compliance") or {}).get("passed") != "1":
        errList.append(f"合规 passed={((data.get('compliance') or {}).get('passed'))}")
    if data.get("imageCount") != expectedImageCount:
        errList.append(f"imageCount={data.get('imageCount')} != {expectedImageCount}")
    if not zipPath or not os.path.isfile(zipPath):
        record(name, False, f"ZIP 未落盘: {zipPath}")
        return

    with zipfile.ZipFile(zipPath) as zipFile:
        names = zipFile.namelist()
        imageNames = [n for n in names if n not in SP4B_ASSET_PACK_TEXT_ENTRIES]
        textNames = [n for n in names if n in SP4B_ASSET_PACK_TEXT_ENTRIES]
        manifest = json.loads(zipFile.read("manifest.json").decode("utf-8"))
        titleText = zipFile.read("title.txt").decode("utf-8")
        contentText = zipFile.read("content.txt").decode("utf-8")
        riskText = zipFile.read("RISK_NOTICE.txt").decode("utf-8")
        swipeText = zipFile.read("SWIPE_TIPS.txt").decode("utf-8")
        copyrightText = zipFile.read("COPYRIGHT.txt").decode("utf-8")
        entrySha256 = {}
        for imageName in imageNames:
            entrySha256[imageName] = hashlib.sha256(zipFile.read(imageName)).hexdigest()

    #图片: 有序命名 01_/02_…(顺序即 App 内左右滑动浏览顺序)
    if len(imageNames) != expectedImageCount:
        errList.append(f"ZIP 图片数 {len(imageNames)} != {expectedImageCount}")
    for index, imageName in enumerate(imageNames):
        if not imageName.startswith(f"{index + 1:02d}_"):
            errList.append(f"图片命名未按序: {imageName}")
    if textNames != SP4B_ASSET_PACK_TEXT_ENTRIES:
        errList.append(f"文本条目不符: {textNames}")
    if names[:len(imageNames)] != imageNames or names[len(imageNames):] != SP4B_ASSET_PACK_TEXT_ENTRIES:
        errList.append(f"ZIP 条目顺序不符: {names}")

    #title.txt / content.txt(含话题标签)
    if titleText != topicRecord.get("title"):
        errList.append(f"title.txt={titleText!r}")
    if "#" not in contentText:
        errList.append("content.txt 缺少话题标签(#)")
    for tag in ("citywalk", "摄影"):
        if f"#{tag}" not in contentText:
            errList.append(f"content.txt 缺少话题标签: #{tag}")

    #风险告知(7.8 第 8 项) / 滑动提示(第 11 项) / 版权提示(第 7 项)
    for token in ("官方创作服务平台", "禁止第三方自动发布"):
        if token not in riskText:
            errList.append(f"RISK_NOTICE.txt 缺少: {token}")
    for token in ("图片显示区域", "8.0"):
        if token not in swipeText:
            errList.append(f"SWIPE_TIPS.txt 缺少: {token}")
    for token in (topicRecord.get("source"), topicRecord.get("period")):
        if token and token not in copyrightText:
            errList.append(f"COPYRIGHT.txt 缺少: {token}")

    #manifest.json: 主题编码 / 生成时间 / 版式 / 平台 / 文件清单与校验值
    for key in ("topicCode", "generatedAt", "layoutType", "platform", "fileList", "checkSum"):
        if not manifest.get(key):
            errList.append(f"manifest 缺少字段: {key}")
    if manifest.get("platform") != "xiaohongshu" or manifest.get("topicCode") != topicRecord.get("topicCode"):
        errList.append(f"manifest 平台/主题编码不符: {manifest.get('platform')}/{manifest.get('topicCode')}")
    if len(manifest.get("fileList") or []) != expectedImageCount:
        errList.append("manifest.fileList 条数不符")

    #校验值: manifest.checkSum = sha256(按序拼接各文件 sha256); 且条目 sha256 与实际文件一致
    digester = hashlib.sha256()
    for imageName in imageNames:
        digester.update(entrySha256[imageName].encode("utf-8"))
    if manifest.get("checkSum") != digester.hexdigest():
        errList.append("manifest.checkSum 与各文件 sha256 拼接不一致")
    for item in manifest.get("fileList") or []:
        if item.get("entryName") not in entrySha256 or item.get("sha256") != entrySha256.get(item.get("entryName")):
            errList.append(f"manifest 文件校验值不符: {item.get('entryName')}")
        if not item.get("sizeBytes"):
            errList.append(f"manifest 缺少 sizeBytes: {item.get('entryName')}")

    print(f"[sp4b-zip] {name}: entries={names}, checkSum={manifest.get('checkSum')[:16]}..., "
          f"fileID={data.get('fileID')}, zipSizeBytes={data.get('zipSizeBytes')}")
    record(name, not errList, "; ".join(errList[:6]))


def assertSp4bAssetPackZip(topic, products):
    """★ 素材包 ZIP: 用 SP3b 的真实小红书产物打 ZIP(合规/ZIP/上传/校验值和均真实执行)"""
    errList = []
    os.makedirs(ARTIFACT_DIR, exist_ok = True)
    if not products:
        record("SP4b 素材包 ZIP(真实产物: 结构/7.8 项/校验值)", False, "缺少 SP3b 真实产物")
        return

    packAssets = _buildPackAssets(len(products))
    layoutRecord = buildLayoutRecord("swipe")
    platformSeed = getPlatformSeed("xiaohongshu")

    #(a) products 直传(真实产物 localPath 直接打包)
    rtn = _runArtifactPack(topic, packAssets, layoutRecord, platformSeed,
                           {"topicID": "1001", "layoutCode": "swipe_v1", "platform": "xiaohongshu",
                            "products": products, "objectDir": ARTIFACT_DIR})
    _assertZipStructure(rtn, len(packAssets), topic, "SP4b 素材包 ZIP(真实产物: 结构/7.8 项/校验值)")

    #(b) ch_artifact 台账取数(桩替换台账 + **真实**按 fileID 从文件门面取回) + 命名顺序
    artifactRecords = []
    for index, product in enumerate(products):
        artifactRecords.append({
            "recID": index + 1, "artifactId": index + 1,
            "artifactKey": f"456:png:xiaohongshu:{product.get('seqNo')}",
            "jobID": "456", "kind": "png", "platform": "xiaohongshu",
            "fileID": product.get("fileID"), "seqNo": product.get("seqNo"),
            "artifactVer": "1", "specNote": f"{product.get('width')}x{product.get('height')}",
            "sizeBytes": str(product.get("sizeBytes") or 0),
            "artifactStatus": "READY", "delFlag": "0",
        })
    rtn2 = _runArtifactPack(topic, packAssets, layoutRecord, platformSeed,
                            {"topicID": "1001", "jobID": "456", "layoutCode": "swipe_v1",
                             "platform": "xiaohongshu", "objectDir": ARTIFACT_DIR},
                            extra = {"artifactRecords": artifactRecords})
    data2 = rtn2.get("data") or {}
    if rtn2.get("errCode") != "B0":
        errList.append(f"台账取数路径导出失败: {rtn2.get('errCode')} {rtn2.get('errMsgList')}")
    elif data2.get("imageCount") != len(packAssets):
        errList.append(f"台账路径 imageCount={data2.get('imageCount')} != {len(packAssets)}")
    print(f"[sp4b-zip-ledger] errCode={rtn2.get('errCode')} imageCount={data2.get('imageCount')} "
          f"fileID={data2.get('fileID')}")
    record("SP4b 素材包 ZIP(ch_artifact 台账取数 + 按 fileID 真实取回)", not errList, "; ".join(errList[:5]))


def assertSp4bAssetPackRefused(topic, products):
    """★ 未过合规校验 -> 拒绝出包(不生成 ZIP、不上传)"""
    errList = []
    if not products:
        record("SP4b 未过合规校验 -> 拒绝出包", False, "缺少 SP3b 真实产物")
        return

    packAssets = _buildPackAssets(len(products))
    layoutRecord = buildLayoutRecord("swipe")
    platformSeed = getPlatformSeed("xiaohongshu")

    badTopic = dict(topic)
    badTopic["description"] = "本段包含敏感词样例, 应当被合规闸门拦截"

    uploadCalls = []
    originalSave = comFS.saveFile
    try:
        comFS.saveFile = lambda *args, **kwargs: (uploadCalls.append(args) or "stub-file-id")
        rtn = _runArtifactPack(badTopic, packAssets, layoutRecord, platformSeed,
                               {"topicID": "1001", "layoutCode": "swipe_v1", "platform": "xiaohongshu",
                                "products": products, "objectDir": ARTIFACT_DIR})
    finally:
        comFS.saveFile = originalSave

    data = rtn.get("data") or {}
    print(f"[sp4b-refuse] errCode={rtn.get('errCode')} packaged={data.get('packaged')} "
          f"uploadCalls={len(uploadCalls)} passed={(data.get('compliance') or {}).get('passed')}")
    if rtn.get("errCode") != "C7":
        errList.append(f"敏感词未拦截为 C7: {rtn.get('errCode')}")
    if data.get("packaged") != "0":
        errList.append("未过校验仍标记出包")
    if uploadCalls:
        errList.append("未过校验仍上传了 ZIP(违反「未过校验不得出包」)")
    record("SP4b 未过合规校验 -> 拒绝出包", not errList, "; ".join(errList[:5]))

#===== SP4b 素材包 ZIP 冒烟 end =====


#===== SP4b MCP 接入冒烟(主计划 9.6.6 十项清单) begin =====
#★ 本轮口径(已确认): **不做联调** —— **不启动 MCP 服务、不监听端口**(监听端口仍固定为 8891, 由配置与静态验收锁定);
#  故 9.6.6 的第 ①/② 项(无 token 401 / 无效 token 拒绝)属**服务端鉴权中间件行为**, 本轮**未执行**,
#  其配置不变式(`token_verifier = CHTokenVerifier` + `AuthSettings` + 端口 8891)由静态 S27 + 本项配置断言覆盖。
#★ 真实执行(直调实现层, 不经网络): ④ 未知 tool -> ERR_NOCMD / ⑥ 缺必填参 -> BA;
#★ 桩验证: ③ 有效 token 放行(本机无 Redis 服务端 -> getSessionInfo 为桩);
#  ⑤ 工具越权 BT(鉴权上下文为桩) / ⑦ 正常查询 B0 / ⑧ 3 resource / ⑨ 下游不可达 ERROR / ⑩ 截断(下游 /chapi 为桩)。

#★ 监听端口不变式(8891): 与 config/mcpConfig.py 一致(避开 stock-mcp-server 的 8889 与早期占位口径 8890)
MCP_SERVER_PORT = 8891


def assertMcpServerPort():
    """配置不变式: MCP 监听端口固定 8891(本轮不做联调, 以配置+静态断言锁定)"""
    from config import mcpConfig
    errList = []
    if int(getattr(mcpConfig, "MCP_SERVER_PORT", 0) or 0) != MCP_SERVER_PORT:
        errList.append(f"mcpConfig.MCP_SERVER_PORT={getattr(mcpConfig, 'MCP_SERVER_PORT', None)} != {MCP_SERVER_PORT}")
    if str(getattr(mcpConfig, "MCP_TRANSPORT", "")) != "streamable-http":
        errList.append(f"MCP_TRANSPORT={getattr(mcpConfig, 'MCP_TRANSPORT', None)} != streamable-http")
    authIssuer = str(getattr(mcpConfig, "MCP_AUTH_ISSUER_URL", ""))
    if str(MCP_SERVER_PORT) not in authIssuer:
        errList.append(f"MCP_AUTH_ISSUER_URL 未指向 {MCP_SERVER_PORT}: {authIssuer}")
    print(f"[sp4b-mcp-port] MCP_SERVER_PORT={getattr(mcpConfig, 'MCP_SERVER_PORT', None)}, "
          f"transport={getattr(mcpConfig, 'MCP_TRANSPORT', None)}, issuer={authIssuer}")
    record("SP4b MCP 监听端口与传输不变式(8891 / streamable-http; 本轮不联调)", not errList, "; ".join(errList[:4]))


def _runAsyncCoroutine(coroFunc):
    """在独立线程内跑协程并取回结果(避免主线程已有事件循环时 asyncio.run 报错)"""
    resultBox = {}

    def _worker():
        import asyncio as _asyncio
        loop = _asyncio.new_event_loop()
        try:
            _asyncio.set_event_loop(loop)
            resultBox["value"] = loop.run_until_complete(coroFunc())
        except Exception as e:
            resultBox["error"] = f"{type(e).__name__}: {e}"
        finally:
            loop.close()

    thread = threading.Thread(target = _worker)
    thread.start()
    thread.join()
    return resultBox.get("value"), resultBox.get("error", "")


class _McpFakeToken:
    def __init__(self, roleName = "administrator", allowedTools = "", loginID = "smoke"):
        self.token = "smoke-token"
        self.client_id = loginID
        self.roleName = roleName
        self.allowedTools = allowedTools


class _McpFakeChServer:
    """桩下游 /chapi: 返回分页缓冲体 {indexKey,total,beginNum,endNum,data}"""

    def __init__(self, itemCount = 3):
        self.itemCount = itemCount

    def _payload(self, total = None):
        total = self.itemCount if total is None else total
        return {"data": {"indexKey": "smoke", "total": total, "beginNum": 0, "endNum": total - 1,
                         "data": [{"recID": str(i + 1), "topicCode": f"T{i + 1}"} for i in range(total)]},
                "status": 200}

    def searchTopics(self, **kwargs):
        return self._payload()

    def getTopic(self, **kwargs):
        return self._payload(1)

    def readTopicAssetList(self, **kwargs):
        return self._payload(2)

    def readLayoutList(self, **kwargs):
        return self._payload(4)

    def readPlatformList(self, **kwargs):
        return self._payload(3)

    def readRenderJobList(self, **kwargs):
        return self._payload(1)

    def readArtifactList(self, **kwargs):
        return self._payload(2)

    def readPublishRecordList(self, **kwargs):
        return self._payload(1)


def assertSp4bMcpChecklist():
    """★ 主计划 9.6.6 冒烟清单: **本轮不联调**(不启动服务/不监听端口) —— ①/② 服务端鉴权项未执行,
       其配置不变式由静态 S27 + assertMcpServerPort 覆盖; ③–⑩ 直调实现层逐条执行(真实执行/桩验证 逐项标注)"""
    errList = []
    evidence = []

    from mcpapi import mcpPost as mcpImpl
    import mcpapi.mcp_entry as mcpEntry

    if len(mcpImpl.toolPathMap) != 8:
        errList.append("MCP 只读 tool 数 != 8")

    #--- ① 无 token -> 401 / ② 无效 token -> 拒绝
    #  ★ 本轮**不联调**: 不启动 mcp_entry、不监听端口 -> ①② **未执行**(需真实服务端 + 鉴权中间件才能观测 HTTP 状态码)。
    #  仅校验其配置落点存在(协议接入能力已就绪), 并将该项显式记为「未执行」而非「通过」。
    if "_genAllowedTools" not in dir(mcpImpl) or not hasattr(mcpImpl, "CHTokenVerifier"):
        errList.append("MCP 鉴权实现缺失(CHTokenVerifier)")
    if not os.path.isfile(os.path.join(_SRC_DIR, "mcpapi", "mcp_entry.py")):
        errList.append("mcpapi/mcp_entry.py 缺失")
    evidence.append("①②未执行(本轮不联调)")

    #--- ③ 有效 token 放行(★ 桩验证: 本机无 Redis 服务端, getSessionInfo 为桩)
    originalGetSessionInfo = mcpImpl.comDB.getSessionInfo
    try:
        mcpImpl.comDB.getSessionInfo = lambda token: {"loginID": "smoke", "roleName": "administrator"}
        verifier = mcpImpl.CHTokenVerifier()
        accessTokenObj, verifyErr = _runAsyncCoroutine(lambda: verifier.verify_token("smoke-token"))
    finally:
        mcpImpl.comDB.getSessionInfo = originalGetSessionInfo
    evidence.append(f"③{'pass' if accessTokenObj else 'reject'}(桩:Redis){(' err=' + verifyErr) if verifyErr else ''}")
    if accessTokenObj is None or getattr(accessTokenObj, "roleName", "") != "administrator":
        errList.append("③ 有效 token(桩 Redis 会话)未放行")

    #--- ④ 未知 tool -> ERR_NOCMD(★ 真实执行)
    originalGetAccessToken = mcpImpl.get_access_token
    try:
        mcpImpl.get_access_token = lambda: _McpFakeToken()
        unknownRtn = mcpImpl.post("no_such_tool", {}, {})
    finally:
        mcpImpl.get_access_token = originalGetAccessToken
    evidence.append(f"④{unknownRtn.get('errCode')}")
    if unknownRtn.get("errCode") != "ERR_NOCMD":
        errList.append(f"④ 未知 tool 未返回 ERR_NOCMD: {unknownRtn.get('errCode')}")

    #--- ⑤ MCP_TOOL_LIST 越权 -> BT(★ 桩验证: 鉴权上下文 allowedTools 为桩)
    originalGetAccessToken = mcpImpl.get_access_token
    try:
        mcpImpl.get_access_token = lambda: _McpFakeToken(roleName = "operator", allowedTools = "list_platforms")
        forbiddenRtn = mcpImpl.post("search_topics", {}, {})
    finally:
        mcpImpl.get_access_token = originalGetAccessToken
    evidence.append(f"⑤{forbiddenRtn.get('errCode')}")
    if forbiddenRtn.get("errCode") != "BT":
        errList.append(f"⑤ 工具越权未返回 BT: {forbiddenRtn.get('errCode')}")

    #--- ⑥ 缺必填参 -> BA(★ 真实执行, 不触下游)
    originalGetAccessToken = mcpImpl.get_access_token
    try:
        mcpImpl.get_access_token = lambda: _McpFakeToken()
        missingRtn = mcpImpl.post("list_topic_assets", {}, {})
    finally:
        mcpImpl.get_access_token = originalGetAccessToken
    evidence.append(f"⑥{missingRtn.get('errCode')}")
    if missingRtn.get("errCode") != "BA":
        errList.append(f"⑥ 缺必填参未返回 BA: {missingRtn.get('errCode')}")

    #--- ⑦ 正常查询 -> B0 且 rtnData 含 total/returned/data(★ 桩验证: 下游 /chapi 为桩)
    originals = {"getChServer": mcpImpl.getChServer, "get_access_token": mcpImpl.get_access_token}
    try:
        mcpImpl.getChServer = lambda sessionID = "": _McpFakeChServer(3)
        mcpImpl.get_access_token = lambda: _McpFakeToken()
        okRtn = mcpImpl.post("search_topics", {"keyword": "秋日", "limit": 30}, {})
    finally:
        mcpImpl.getChServer = originals["getChServer"]
        mcpImpl.get_access_token = originals["get_access_token"]
    okData = okRtn.get("rtnData") or {}
    evidence.append(f"⑦{okRtn.get('errCode')}/total={okData.get('total')}/returned={okData.get('returned')}")
    if okRtn.get("errCode") != "B0":
        errList.append(f"⑦ 正常查询未返回 B0: {okRtn.get('errCode')}")
    for key in ("total", "returned", "data"):
        if key not in okData:
            errList.append(f"⑦ rtnData 缺少 {key}")

    #--- ⑧ 3 个 resource 读取 -> 合法 JSON(★ 桩验证: 下游为桩)
    originals = {"getChServer": mcpImpl.getChServer, "get_access_token": mcpImpl.get_access_token}
    try:
        mcpImpl.getChServer = lambda sessionID = "": _McpFakeChServer(3)
        mcpImpl.get_access_token = lambda: _McpFakeToken()
        resourceTexts = {
            "contenthub://platforms": mcpEntry.resource_platforms(),
            "contenthub://layouts": mcpEntry.resource_layouts(),
            "contenthub://topic/{topic_id}": mcpEntry.resource_topic("4001"),
        }
    finally:
        mcpImpl.getChServer = originals["getChServer"]
        mcpImpl.get_access_token = originals["get_access_token"]
    evidence.append(f"⑧{len(resourceTexts)}/3")
    for uri, text in resourceTexts.items():
        try:
            parsed = json.loads(text)
        except Exception as e:
            errList.append(f"⑧ resource 非法 JSON: {uri}, {e}")
            continue
        if not isinstance(parsed, dict) or "errCode" not in parsed:
            errList.append(f"⑧ resource 结构不符: {uri}")

    #--- ⑨ 下游不可达 -> ERROR(★ 桩验证: 桩注入下游异常)
    def _raiseDownstream(sessionID = ""):
        raise RuntimeError("chapi unreachable(smoke stub)")

    originalGetAccessToken = mcpImpl.get_access_token
    originalGetChServer = mcpImpl.getChServer
    try:
        mcpImpl.get_access_token = lambda: _McpFakeToken()
        mcpImpl.getChServer = _raiseDownstream
        errorRtn = mcpImpl.post("search_topics", {}, {})
    finally:
        mcpImpl.get_access_token = originalGetAccessToken
        mcpImpl.getChServer = originalGetChServer
    evidence.append(f"⑨{errorRtn.get('errCode')}")
    if errorRtn.get("errCode") != "ERROR":
        errList.append(f"⑨ 下游不可达未返回 ERROR: {errorRtn.get('errCode')}")

    #--- ⑩ 超 TOOL_RESULT_LIMIT -> returned < total(★ 桩验证: 下游为桩)
    originals = {"getChServer": mcpImpl.getChServer, "get_access_token": mcpImpl.get_access_token}
    try:
        mcpImpl.getChServer = lambda sessionID = "": _McpFakeChServer(50)
        mcpImpl.get_access_token = lambda: _McpFakeToken()
        truncRtn = mcpImpl.post("search_topics", {"limit": 10}, {})
    finally:
        mcpImpl.getChServer = originals["getChServer"]
        mcpImpl.get_access_token = originals["get_access_token"]
    truncData = truncRtn.get("rtnData") or {}
    evidence.append(f"⑩returned={truncData.get('returned')}/total={truncData.get('total')}")
    if int(truncData.get("returned") or 0) >= int(truncData.get("total") or 0):
        errList.append(f"⑩ 未截断: returned={truncData.get('returned')}, total={truncData.get('total')}")
    if int(truncData.get("returned") or 0) != 10:
        errList.append(f"⑩ 截断条数应等于 limit=10, 实为 {truncData.get('returned')}")

    print(f"[sp4b-mcp] {' '.join(evidence)}")
    record("SP4b MCP 9.6.6 清单(①②未执行[本轮不联调]; ③-⑩ 已逐项标注 真实执行/桩验证)",
           not errList, "; ".join(errList[:6]))

#===== SP4b MCP 接入冒烟 end =====


#===== SP4b 凭据巡检冒烟 begin =====

class _CredProbeAdapter:
    """桩: 巡检用平台适配器(仅需 fetchAccessToken)"""

    def fetchAccessToken(self, appID, appSecret, timeout = None):
        return {"errCode": "B0", "field": "", "errMsgList": [],
                "data": {"accessToken": "STUB", "expiresIn": 7200}}


def assertSp4bCredentialCheck():
    """★ 巡检三态(OK/EXPIRING/INVALID) + 小红书跳过 + R-03 分级告警 + 只读探活(不投递)"""
    errList = []
    evidence = []

    #1) 三态判定(纯函数, 真实执行)
    farExpire = "20991231235959"
    soonExpire = (datetime.datetime.now() + datetime.timedelta(days = 3)).strftime("%Y%m%d%H%M%S")
    expired = (datetime.datetime.now() - datetime.timedelta(days = 1)).strftime("%Y%m%d%H%M%S")
    statusMap = {
        "OK": credCheck.decideHealthStatus(farExpire, True),
        "EXPIRING": credCheck.decideHealthStatus(soonExpire, True),
        "INVALID": credCheck.decideHealthStatus(expired, True),
        "INVALID_PROBE": credCheck.decideHealthStatus(farExpire, False),
    }
    evidence.append(f"三态={statusMap}")
    if statusMap["OK"] != "OK" or statusMap["EXPIRING"] != "EXPIRING":
        errList.append(f"三态判定不符: {statusMap}")
    if statusMap["INVALID"] != "INVALID" or statusMap["INVALID_PROBE"] != "INVALID":
        errList.append(f"INVALID 判定不符: {statusMap}")

    #2) checkAccount 三态 + 跳过 + 告警分级(桩替换数据层/平台取数)
    updates = []
    originals = {
        "_fetchPlatformRecord": renderSvc._fetchPlatformRecord,
        "_mergeAssetMeta": renderSvc._mergeAssetMeta,
        "getAdapter": platformAdapter.getAdapter,
        "decrypt": publishSvc.decryptAccountCredential,
        "update_ch_account": comMysql.update_ch_account,
    }
    try:
        renderSvc._fetchPlatformRecord = lambda platformCode: (getPlatformSeed("wechat_mp"), None)
        platformAdapter.getAdapter = lambda platformCode, platformRecord = None: _CredProbeAdapter()
        publishSvc.decryptAccountCredential = lambda accountRecord: (
            {"appID": "wx-smoke", "appSecret": "stub", "healthStatus": "OK", "source": "ch_account.cipher"}, None)
        comMysql.update_ch_account = lambda tableName, recID, saveSet: (updates.append((recID, saveSet)) or 1)

        okRtn = credCheck.checkAccount({"recID": "77", "accountCode": "wx_ok", "platform": "wechat_mp",
                                        "expireYMDHMS": farExpire, "healthStatus": "UNKNOWN"})
        expiringRtn = credCheck.checkAccount({"recID": "78", "accountCode": "wx_exp", "platform": "wechat_mp",
                                              "expireYMDHMS": soonExpire, "healthStatus": "UNKNOWN"})
        invalidRtn = credCheck.checkAccount(
            {"recID": "79", "accountCode": "wx_bad", "platform": "wechat_mp", "expireYMDHMS": farExpire},
            fetchAccessTokenFunc = lambda appID, appSecret: {"errCode": "F0", "errMsgList": ["access_token 获取失败"]})
        skippedRtn = credCheck.checkAccount({"recID": "80", "accountCode": "xhs_1", "platform": "xiaohongshu",
                                             "healthStatus": "UNKNOWN"})
    finally:
        renderSvc._fetchPlatformRecord = originals["_fetchPlatformRecord"]
        renderSvc._mergeAssetMeta = originals["_mergeAssetMeta"]
        platformAdapter.getAdapter = originals["getAdapter"]
        publishSvc.decryptAccountCredential = originals["decrypt"]
        comMysql.update_ch_account = originals["update_ch_account"]

    evidence.append(f"巡检={okRtn.get('healthStatus')}/{expiringRtn.get('healthStatus')}/"
                    f"{invalidRtn.get('healthStatus')}/{skippedRtn.get('healthStatus')}")
    if okRtn.get("healthStatus") != "OK":
        errList.append(f"探活成功未置 OK: {okRtn}")
    if expiringRtn.get("healthStatus") != "EXPIRING":
        errList.append(f"阈值内未置 EXPIRING: {expiringRtn}")
    if invalidRtn.get("healthStatus") != "INVALID":
        errList.append(f"探活失败未置 INVALID: {invalidRtn}")
    if not skippedRtn.get("skipReason") or skippedRtn.get("probed"):
        errList.append(f"小红书未跳过并说明: {skippedRtn}")
    if skippedRtn.get("healthStatus") != "UNKNOWN":
        errList.append(f"跳过项不应改写健康状态: {skippedRtn.get('healthStatus')}")

    #分级告警(R-03): OK=INFO / EXPIRING=WARN / INVALID=ERROR
    if (okRtn.get("alertLevel"), expiringRtn.get("alertLevel"), invalidRtn.get("alertLevel")) != \
            ("INFO", "WARN", "ERROR"):
        errList.append(f"告警分级不符: {okRtn.get('alertLevel')}/{expiringRtn.get('alertLevel')}/"
                       f"{invalidRtn.get('alertLevel')}")

    #健康状态回写: OK/EXPIRING/INVALID 三态各回写一次; 跳过项不回写
    writtenStatus = [item[1].get("healthStatus") for item in updates]
    evidence.append(f"回写={writtenStatus}")
    if writtenStatus != ["OK", "EXPIRING", "INVALID"]:
        errList.append(f"健康状态回写不符: {writtenStatus}")
    if any(item[1].get("lastCheckYMDHMS") is None for item in updates):
        errList.append("未写入 lastCheckYMDHMS")
    if len(updates) != 3:
        errList.append(f"跳过项不应回写(回写次数 {len(updates)})")

    #3) runOnce 汇总 + Redis 降级(★ 真实调用: 本机无 Redis 服务端 -> degraded=1)
    originalsRun = {
        "query_ch_account": comMysql.query_ch_account,
        "_fetchPlatformRecord": renderSvc._fetchPlatformRecord,
        "getAdapter": platformAdapter.getAdapter,
        "decrypt": publishSvc.decryptAccountCredential,
        "update_ch_account": comMysql.update_ch_account,
    }
    try:
        comMysql.query_ch_account = lambda *args, **kwargs: [
            {"recID": "77", "accountCode": "wx_ok", "platform": "wechat_mp", "expireYMDHMS": farExpire},
            {"recID": "80", "accountCode": "xhs_1", "platform": "xiaohongshu", "healthStatus": "UNKNOWN"},
        ]
        renderSvc._fetchPlatformRecord = lambda platformCode: (getPlatformSeed("wechat_mp"), None)
        platformAdapter.getAdapter = lambda platformCode, platformRecord = None: _CredProbeAdapter()
        publishSvc.decryptAccountCredential = lambda accountRecord: (
            {"appID": "wx-smoke", "appSecret": "stub", "healthStatus": "OK"}, None)
        comMysql.update_ch_account = lambda tableName, recID, saveSet: 1
        stats = credCheck.runOnce({"useLock": "0"})
    finally:
        comMysql.query_ch_account = originalsRun["query_ch_account"]
        renderSvc._fetchPlatformRecord = originalsRun["_fetchPlatformRecord"]
        platformAdapter.getAdapter = originalsRun["getAdapter"]
        publishSvc.decryptAccountCredential = originalsRun["decrypt"]
        comMysql.update_ch_account = originalsRun["update_ch_account"]

    evidence.append(f"runOnce ok={stats.get('ok')}/skipped={stats.get('skipped')}/degraded={stats.get('degraded')}")
    if stats.get("total") != 2 or stats.get("ok") != 1 or stats.get("skipped") != 1:
        errList.append(f"runOnce 汇总不符: {stats}")
    if not (stats.get("alertSummary") or {}).get("INFO"):
        errList.append(f"runOnce 缺告警汇总: {stats.get('alertSummary')}")

    #Redis 不可用 -> 巡检锁降级(真实调用, 本机无 Redis 服务端)
    degradedStats = credCheck.runOnce({"accountID": -1})
    evidence.append(f"Redis降级 degraded={degradedStats.get('degraded')}")
    if str(degradedStats.get("degraded")) != "1":
        errList.append(f"Redis 不可用时未标记 degraded: {degradedStats.get('degraded')}")

    print(f"[sp4b-cred] {' '.join(evidence)}")
    record("SP4b 凭据巡检(三态/分级告警/小红书跳过/Redis 降级)", not errList, "; ".join(errList[:6]))


def assertSp4bAccountHealthEndpoint():
    """★ accounthealth 端点内接入巡检(不新增 CMD): action=check -> 触发 credentialCheck.runOnce"""
    errList = []
    mainDir = os.path.join(_SRC_DIR, "main")
    if mainDir not in sys.path:
        sys.path.insert(0, mainDir)

    originals = {"query_ch_account": comMysql.query_ch_account, "runOnce": credCheck.runOnce}
    try:
        import subfunc.accountApi as accountApi
        comMysql.query_ch_account = lambda *args, **kwargs: []
        credCheck.runOnce = lambda dataSet = None, fetchAccessTokenFunc = None: {
            "total": 1, "checked": 1, "ok": 1, "expiring": 0, "invalid": 0, "unknown": 0, "skipped": 0,
            "degraded": 1, "checkedAt": "20260919120000", "items": [], "alertSummary": {"INFO": 1}}
        rtn = accountApi.funcAccountHealth("accounthealth", {"action": "check", "platform": "wechat_mp"}, {})
    finally:
        comMysql.query_ch_account = originals["query_ch_account"]
        credCheck.runOnce = originals["runOnce"]

    checkResult = rtn.get("credentialCheck") if isinstance(rtn, dict) else None
    print(f"[sp4b-health] errCode={rtn.get('errCode') if isinstance(rtn, dict) else '?'} "
          f"checkResult={'1' if checkResult else '0'} healthSummary={rtn.get('healthSummary') if isinstance(rtn, dict) else None}")
    if not isinstance(rtn, dict) or rtn.get("errCode") != "B0":
        errList.append(f"accounthealth 返回异常: {rtn.get('errCode') if isinstance(rtn, dict) else rtn}")
    if not checkResult:
        errList.append("action=check 未触发凭据巡检")
    if not isinstance(rtn, dict) or not isinstance(rtn.get("healthSummary"), dict):
        errList.append("healthSummary 缺失")
    record("SP4b accounthealth 内接入巡检(不新增 CMD)", not errList, "; ".join(errList[:5]))

#===== SP4b 凭据巡检冒烟 end =====


#===== SP4c 归档清理 + 监控告警 冒烟 begin =====

def assertSp4cArchiveDryRunAndOrder():
    """★ SP4c 归档: dry-run 为默认(不产生任何导出/删除调用) + 显式执行时「先导出后删除」批次顺序正确。
       本机无 MySQL -> 数据层桩替换; 文件门面桩替换(不打真实网络)。"""
    errList = []
    evidence = []
    workDir = tempfile.mkdtemp(prefix = "ch_archive_smoke_")
    events = []
    rowsA = [{"recID": "1", "action": "topic.create", "regYMDHMS": "20200101000000"},
             {"recID": "2", "action": "publish.push", "regYMDHMS": "20200101000001"}]
    rowsB = [{"recID": "3", "action": "archive.audit_log", "regYMDHMS": "20200101000002"}]

    originals = {
        "query_ch_audit_log": comMysql.query_ch_audit_log,
        "delete_ch_audit_log": comMysql.delete_ch_audit_log,
        "saveFile": comFS.saveFile,
        "writeAudit": archiveSvc.auditService.writeAudit,
    }

    #--- 1) dry-run: 只打印清单, 不导出、不删除
    try:
        comMysql.query_ch_audit_log = lambda tableName, **kwargs: list(rowsA)
        comMysql.delete_ch_audit_log = lambda tableName, recID: (events.append(("delete", recID)) or 1)
        comFS.saveFile = lambda localPath, objectName = "", privateFlag = False, **kw: (
            events.append(("export", objectName)) or "file_dry")
        archiveSvc.auditService.writeAudit = lambda *a, **k: 1
        dryStats = archiveSvc.archiveAuditLog(dryRun = True, retainMonths = 24, batchSize = 2, workDir = workDir)
    finally:
        pass
    evidence.append(f"dryRun planRows={dryStats.get('planRows')}, events={len(events)}")
    if dryStats.get("mode") != "dry-run":
        errList.append(f"dry-run mode 不符: {dryStats.get('mode')}")
    if dryStats.get("planRows") != 2:
        errList.append(f"dry-run 计划清单条数不符: {dryStats.get('planRows')}")
    if events:
        errList.append(f"★ dry-run 不得产生任何导出/删除调用, 实为 {events}")

    #--- 2) execute: 先导出(含上传)成功 -> 再删除; 批次循环正确
    events.clear()
    queryBatches = [list(rowsA), list(rowsB), []]
    queryState = {"index": 0}

    def _fakeQueryAudit(tableName, **kwargs):
        index = queryState["index"]
        queryState["index"] += 1
        return queryBatches[index] if index < len(queryBatches) else []

    def _fakeSaveFile(localPath, objectName = "", privateFlag = False, **kw):
        events.append("export")
        return f"file{len(events)}"

    def _fakeDelete(tableName, recID):
        events.append("delete")
        return 1

    try:
        comMysql.query_ch_audit_log = _fakeQueryAudit
        comMysql.delete_ch_audit_log = _fakeDelete
        comFS.saveFile = _fakeSaveFile
        archiveSvc.auditService.writeAudit = lambda *a, **k: 1
        execStats = archiveSvc.archiveAuditLog(dryRun = False, retainMonths = 24, batchSize = 2, workDir = workDir)
    finally:
        comMysql.query_ch_audit_log = originals["query_ch_audit_log"]
        comMysql.delete_ch_audit_log = originals["delete_ch_audit_log"]
        comFS.saveFile = originals["saveFile"]
        archiveSvc.auditService.writeAudit = originals["writeAudit"]
        shutil.rmtree(workDir, ignore_errors = True)

    expectedEvents = ["export", "delete", "delete", "export", "delete"]
    evidence.append(f"execute batches={execStats.get('batches')}, exported={execStats.get('exported')}, "
                    f"deleted={execStats.get('deleted')}, events={events}")
    if events != expectedEvents:
        errList.append(f"★ 批次顺序不符(应先导出后删除): {events} != {expectedEvents}")
    if execStats.get("exported") != 3 or execStats.get("deleted") != 3:
        errList.append(f"归档统计不符: exported={execStats.get('exported')}, deleted={execStats.get('deleted')}")
    if execStats.get("batches") != 2:
        errList.append(f"分批次数不符: {execStats.get('batches')}")

    print(f"[sp4c-archive] {' '.join(evidence)}")
    record("SP4c 归档(dry-run 为默认 / 先导出后删除 / 批次循环)", not errList, "; ".join(errList[:4]))


def assertSp4cArtifactPurgeOrder():
    """★ SP4c 产物清理: 到期 -> 先置 artifactStatus=EXPIRED -> 再 delFile;
       删除失败不改变状态(保持已置的 EXPIRED, 不再二次变更)且不静默。"""
    errList = []
    evidence = []
    events = []
    expiredRows = [
        {"recID": "11", "fileID": "f11", "artifactStatus": "READY", "expireYMDHMS": "20000101000000"},
        {"recID": "12", "fileID": "f12", "artifactStatus": "READY", "expireYMDHMS": "20000101000000"},
    ]
    originals = {
        "query_ch_artifact": comMysql.query_ch_artifact,
        "update_ch_artifact": comMysql.update_ch_artifact,
        "delFile": comFS.delFile,
        "writeAudit": archiveSvc.auditService.writeAudit,
    }

    def _fakeUpdate(tableName, recID, saveSet):
        events.append(("EXPIRED", str(recID), saveSet.get("artifactStatus")))
        return 1

    def _fakeDelFile(fileID, *args, **kwargs):
        events.append(("delFile", fileID))
        return fileID != "f12"   #f12 删除失败

    #--- 1) dry-run: 不置状态、不删对象
    try:
        comMysql.query_ch_artifact = lambda tableName, **kwargs: list(expiredRows)
        comMysql.update_ch_artifact = _fakeUpdate
        comFS.delFile = _fakeDelFile
        archiveSvc.auditService.writeAudit = lambda *a, **k: 1
        dryStats = archiveSvc.purgeExpiredArtifacts(dryRun = True, batchSize = 5000)
    finally:
        pass
    if events:
        errList.append(f"★ 产物清理 dry-run 不得置状态/删对象, 实为 {events}")
    if dryStats.get("skipped") != 2:
        errList.append(f"产物清理 dry-run 计划条数不符: {dryStats.get('skipped')}")

    #--- 2) execute: 先置 EXPIRED 再 delFile; 删除失败保持原状态
    events.clear()
    try:
        comMysql.query_ch_artifact = lambda tableName, **kwargs: list(expiredRows)
        comMysql.update_ch_artifact = _fakeUpdate
        comFS.delFile = _fakeDelFile
        archiveSvc.auditService.writeAudit = lambda *a, **k: 1
        execStats = archiveSvc.purgeExpiredArtifacts(dryRun = False, batchSize = 5000)
    finally:
        comMysql.query_ch_artifact = originals["query_ch_artifact"]
        comMysql.update_ch_artifact = originals["update_ch_artifact"]
        comFS.delFile = originals["delFile"]
        archiveSvc.auditService.writeAudit = originals["writeAudit"]

    expectedEvents = [("EXPIRED", "11", "EXPIRED"), ("delFile", "f11"),
                      ("EXPIRED", "12", "EXPIRED"), ("delFile", "f12")]
    evidence.append(f"purged={execStats.get('purged')}, failed={execStats.get('failed')}, events={events}")
    if events != expectedEvents:
        errList.append(f"★ 产物清理顺序不符(应先置 EXPIRED 再 delFile): {events}")
    if execStats.get("purged") != 1 or execStats.get("failed") != 1:
        errList.append(f"产物清理统计不符: purged={execStats.get('purged')}, failed={execStats.get('failed')}")
    #删除失败不改状态: recID 12 只出现一次 EXPIRED 变更(无二次变更/无回退)
    expiredCount12 = sum(1 for item in events if item[0] == "EXPIRED" and item[1] == "12")
    if expiredCount12 != 1:
        errList.append(f"★ 删除失败后状态发生二次变更(应保持 EXPIRED): recID12 变更 {expiredCount12} 次")

    print(f"[sp4c-purge] {' '.join(evidence)}")
    record("SP4c 产物清理(先置 EXPIRED 后 delFile / 删除失败不改状态)", not errList, "; ".join(errList[:4]))


def assertSp4cMetricBoundaries():
    """★ SP4c 七项指标阈值边界值(恰在阈值/越界)分级正确(纯函数, 真实执行)"""
    errList = []
    evidence = []
    cases = [
        ("render@threshold", metricsSvc.evaluateRenderFailureRate(100, 10), "INFO"),
        ("render>threshold", metricsSvc.evaluateRenderFailureRate(100, 11), "ERROR"),
        ("publish@threshold", metricsSvc.evaluatePublishSuccessRate(100, 5), "INFO"),
        ("publish>threshold", metricsSvc.evaluatePublishSuccessRate(100, 6), "ERROR"),
        ("publish-consecutive", metricsSvc.evaluatePublishSuccessRate(100, 0, 3), "ERROR"),
        ("publish-consecutive-below", metricsSvc.evaluatePublishSuccessRate(100, 0, 2), "INFO"),
        ("backlog@threshold", metricsSvc.evaluateQueueBacklog(3, 15.0), "INFO"),
        ("backlog>threshold", metricsSvc.evaluateQueueBacklog(3, 15.1), "WARN"),
        ("credential-none", metricsSvc.evaluateCredentialHealth(0, 0), "INFO"),
        ("credential-expiring", metricsSvc.evaluateCredentialHealth(1, 0), "WARN"),
        ("credential-invalid", metricsSvc.evaluateCredentialHealth(0, 1), "ERROR"),
        ("storage@threshold", metricsSvc.evaluateStorageUsage(0.80), "INFO"),
        ("storage>threshold", metricsSvc.evaluateStorageUsage(0.81), "WARN"),
        ("storage-unknown", metricsSvc.evaluateStorageUsage(None), "INFO"),
        ("audit@factor", metricsSvc.evaluateAuditDailyGrowth(300, 100, 3.0), "INFO"),
        ("audit>factor", metricsSvc.evaluateAuditDailyGrowth(301, 100, 3.0), "WARN"),
    ]
    #定时任务: 恰在 1.5 周期 -> INFO; 超出 -> WARN
    nowDt = datetime.datetime(2026, 9, 19, 12, 0, 0)
    nowStr = nowDt.strftime("%Y%m%d%H%M%S")
    period = 3600
    atThreshold = (nowDt - datetime.timedelta(seconds = int(period * 1.5))).strftime("%Y%m%d%H%M%S")
    beyondThreshold = (nowDt - datetime.timedelta(seconds = int(period * 1.5) + 1)).strftime("%Y%m%d%H%M%S")
    cases.append(("scheduler@threshold", metricsSvc.evaluateSchedulerLastSuccess(atThreshold, period, nowYMDHMS = nowStr), "INFO"))
    cases.append(("scheduler>threshold", metricsSvc.evaluateSchedulerLastSuccess(beyondThreshold, period, nowYMDHMS = nowStr), "WARN"))
    cases.append(("scheduler-missing", metricsSvc.evaluateSchedulerLastSuccess("", period, nowYMDHMS = nowStr), "WARN"))

    for name, result, expected in cases:
        if result.get("level") != expected:
            errList.append(f"{name}: level={result.get('level')} != {expected}")
    for metricName in metricsSvc.METRIC_NAME_LIST:
        if metricName not in metricsSvc.METRIC_EVALUATOR_MAP:
            errList.append(f"指标 {metricName} 缺少判定函数登记")
    evidence.append(f"cases={len(cases)}, metrics={len(metricsSvc.METRIC_NAME_LIST)}")
    print(f"[sp4c-metrics] {' '.join(evidence)}")
    record("SP4c 七项指标阈值边界值分级(恰在阈值/越界)", not errList, "; ".join(errList[:4]))


def assertSp4cAlertChannelNoNetwork():
    """★ SP4c 告警通道为占位且**不发任何网络请求**(静态扫描 + 运行期断言);
       ★ 静态扫描覆盖 chmonitor/(监控核心)与 monitor/(museum 迁移改造层), 二者均须零网络。"""
    errList = []
    evidence = []
    forbidden = ["requests.", "urllib", "http.client", "urlopen", "socket."]
    for scanDirName, scanDir in (("chmonitor", os.path.join(_SRC_DIR, "chmonitor")),
                                 ("monitor", os.path.join(_SRC_DIR, "monitor"))):
        for fileName in sorted(os.listdir(scanDir)):
            if not fileName.endswith(".py"):
                continue
            with open(os.path.join(scanDir, fileName), "rb") as hFile:
                text = hFile.read().decode("utf-8", errors = "replace")
            for token in forbidden:
                if token in text:
                    errList.append(f"{scanDirName}/{fileName} 出现网络调用痕迹: {token}")
    #★ monitor/(museum 迁移改造层): 已剥离 museum 专属依赖与子进程原语
    museumMonitorDir = os.path.join(_SRC_DIR, "monitor")
    museumForbidden = ["museumSettings", "mu_crawl_run_log", "mu_translation_task", "subprocess"]
    museumText = ""
    for fileName in sorted(os.listdir(museumMonitorDir)):
        if not fileName.endswith(".py"):
            continue
        with open(os.path.join(museumMonitorDir, fileName), "rb") as hFile:
            oneText = hFile.read().decode("utf-8", errors = "replace")
        museumText += oneText
        for token in museumForbidden:
            if token in oneText:
                errList.append(f"monitor/{fileName} 残留 museum 依赖/子进程原语: {token}")
    if "chmonitor" not in museumText:
        errList.append("monitor/ 未复用 chmonitor(迁移改造口径不完整)")
    evidence.append(f"scan=chmonitor+monitor")

    sample = metricsSvc.evaluateRenderFailureRate(100, 30)
    alert = alertSvc.buildAlert(sample)
    logRtn = alertSvc.sendAlert(alert, alertSvc.CHANNEL_LOG)
    emailRtn = alertSvc.sendAlert(alert, alertSvc.CHANNEL_EMAIL)
    wecomRtn = alertSvc.sendAlert(alert, alertSvc.CHANNEL_WECOM)
    evidence.append(f"log={logRtn.get('sent')}, email={emailRtn.get('networkRequest')}/{emailRtn.get('sent')}, "
                    f"wecom={wecomRtn.get('networkRequest')}/{wecomRtn.get('sent')}")
    for name, rtn in (("log", logRtn), ("email", emailRtn), ("wecom", wecomRtn)):
        if rtn.get("networkRequest") != "0":
            errList.append(f"{name} 通道出现网络请求标记: {rtn.get('networkRequest')}")
    if emailRtn.get("sent") != 0 or wecomRtn.get("sent") != 0:
        errList.append("占位通道不应实际发送(sent 应为 0)")
    if logRtn.get("sent") != 1:
        errList.append("默认日志通道未落盘")
    if alertSvc.getAlertChannel().name != alertSvc.CHANNEL_LOG:
        errList.append(f"默认通道应为 log: {alertSvc.getAlertChannel().name}")

    print(f"[sp4c-alert] {' '.join(evidence)}")
    record("SP4c 告警通道为占位且无网络调用(静态+运行期)", not errList, "; ".join(errList[:4]))


def assertSp4cGuardEntry():
    """★ SP4c 守护化入口存在且单实例: credentialCheck --loop(Redis 锁可降级) + dailyCheck/archive 入口"""
    errList = []
    credPath = os.path.join(_SRC_DIR, "schedule", "credentialCheck.py")
    archivePath = os.path.join(_SRC_DIR, "schedule", "archive.py")
    dailyPath = os.path.join(_SRC_DIR, "chmonitor", "dailyCheck.py")
    museumMonitorPath = os.path.join(_SRC_DIR, "monitor", "monitor.py")
    museumAlertPath = os.path.join(_SRC_DIR, "monitor", "alert.py")

    def _read(filePath):
        with open(filePath, "rb") as hFile:
            return hFile.read().decode("utf-8", errors = "replace")

    credText = _read(credPath)
    for token in ["--loop", "--interval", "acquireCheckLock", "heartbeat.recordRun", "alertChannel"]:
        if token not in credText:
            errList.append(f"credentialCheck 缺少守护化要素: {token}")
    archiveText = _read(archivePath)
    for token in ["--execute", "acquireArchiveLock", "isDryRun"]:
        if token not in archiveText:
            errList.append(f"archive 缺少要素: {token}")
    if "__main__" not in _read(dailyPath):
        errList.append("chmonitor/dailyCheck.py 缺少 __main__ 入口")
    #★ monitor/(museum 迁移改造层) 入口齐备且复用 chmonitor
    museumMonitorText = _read(museumMonitorPath)
    if "__main__" not in museumMonitorText or "chmonitor" not in museumMonitorText:
        errList.append("monitor/monitor.py 缺少 __main__ 入口或未复用 chmonitor")
    if "run_alert" not in _read(museumAlertPath):
        errList.append("monitor/alert.py 缺少 run_alert 入口")

    #心跳可读写(真实执行, 落 code/data/monitor/)
    heartbeatSvc.recordSuccess(heartbeatSvc.JOB_DAILY_CHECK, note = "smoke")
    if not heartbeatSvc.getLastSuccess(heartbeatSvc.JOB_DAILY_CHECK):
        errList.append("心跳写入/读取失败")

    print(f"[sp4c-guard] credentialCheck=--loop, archive=--execute, dailyCheck=__main__, monitor(museum)=ok")
    record("SP4c 守护化入口存在且单实例(--loop / --execute / __main__)", not errList, "; ".join(errList[:4]))

#===== SP4c 归档清理 + 监控告警 冒烟 end =====


#===== 渲染与断言 end =====


def main():
    print(f"[smoke] srcDir:{_SRC_DIR}, previewDir:{PREVIEW_DIR}")
    print(f"[smoke] 版式种子: {[s.get('layoutCode') for s in LAYOUT_SEED_LIST]}")

    if os.path.isdir(PREVIEW_DIR):
        shutil.rmtree(PREVIEW_DIR, ignore_errors = True)
    os.makedirs(PREVIEW_DIR, exist_ok = True)

    images = makePlaceholderImages()
    topic = buildFixtureTopic(images)
    assets = buildFixtureAssets(images)

    #4 套版式各渲染一次
    _lr, stackRtn, stackContent, stackMeta = renderOne("stack", topic, assets)
    _lr, carouselRtn, carouselContent, carouselMeta = renderOne("carousel", topic, assets)
    _lr, longRtn, longContent, longMeta = renderOne("longimage", topic, assets)
    _lr, swipeRtn, swipeContent, swipeMeta = renderOne("swipe", topic, assets)

    #outputKind 与种子一致
    expectedKind = {s.get("layoutType"): s.get("outputKind") for s in LAYOUT_SEED_LIST}
    kindErr = []
    for layoutType, rtn in (("stack", stackRtn), ("carousel", carouselRtn),
                            ("longimage", longRtn), ("swipe", swipeRtn)):
        if rtn.get("outputKind") != expectedKind.get(layoutType):
            kindErr.append(f"{layoutType}:{rtn.get('outputKind')}!={expectedKind.get(layoutType)}")
    record("4 套版式 outputKind 与种子一致", not kindErr, "; ".join(kindErr))

    assertStack(stackContent, stackMeta, assets)
    assertCarousel(carouselContent, carouselMeta, assets)
    assertLongimage(longContent, longMeta, assets)
    assertSwipe(swipeContent, swipeMeta, assets)
    assertPreview(topic, assets)
    assertImageProc(images)

    #SP3a: 平台形态产物(wechat_mp 内联样式 HTML / generic HTML·Markdown·JSON), 零网络
    platformTopic = buildPlatformTopic()
    platformAssets = buildPlatformAssets()
    assertWechatPlatformArtifact(platformTopic, platformAssets)
    assertWechatCarouselDegrade(platformTopic, platformAssets)
    assertWechatExternalImageBlocked(platformTopic)
    assertGenericPlatformArtifact(platformTopic, platformAssets)

    #SP3b: 小红书产物真实截图(Playwright Chromium 真跑; 零对外网络)
    os.makedirs(XHS_PREVIEW_DIR, exist_ok = True)
    swipeRtn = assertXiaohongshuSwipe(topic, assets)
    assertXiaohongshuLongimage(topic, assets)
    assertXiaohongshuStackToLongimage(topic, assets)
    assertXiaohongshuPackage(topic, assets, swipeRtn)
    assertXiaohongshuCarouselUnavailable(topic, assets)
    assertXiaohongshuSwipeRatioGuard(topic)

    #SP3c: 合规校验(C8) + ch_artifact 台账 + ch_render_job 任务化
    #  说明: 本机无 MySQL/Redis 服务端, 台账/job/复用/降级均以「桩替换数据层/计数后端」验证(非连库执行)
    swipeLayoutRecord = buildLayoutRecord("swipe")
    assertSensitiveWordOffsets()
    assertAiLabelGuard()
    assertComplianceSpecViolations(swipeLayoutRecord)
    assertArtifactLedgerIdempotent()
    assertJobStateMachine()
    assertInputHashReuse(swipeLayoutRecord, getPlatformSeed("xiaohongshu"))
    assertRateLimitDegrade()
    #SP3c 修复回归(2026-09-24): 文档类形态(html/markdown)产物登记 + 主题状态自动推进/失败回落
    assertDocumentArtifactRegistered()
    assertTopicStatusRollbackOnFail()
    assertTopicStatusAdvanceOnReuse()

    #SP4a: C6 投递链路(凭据加解密真实执行; 投递编排以桩替换数据层/HTTP 通道验证 -> 属桩验证)
    runSp4aSmoke()

    #SP4b: 素材包 ZIP(用 SP3b 真实产物打 ZIP; 台账取数为桩, 合规/组装/上传/校验值为真实执行)
    sp4bProducts = (swipeRtn.get("data") or {}).get("products") or [] if isinstance(swipeRtn, dict) else []
    os.makedirs(ARTIFACT_DIR, exist_ok = True)
    assertSp4bAssetPackZip(topic, sp4bProducts)
    assertSp4bAssetPackRefused(topic, sp4bProducts)

    #SP4b: MCP(端口 8891, **本轮不联调**: 不启动服务/不监听端口)
    assertMcpServerPort()
    assertSp4bMcpChecklist()

    #SP4b: 凭据巡检三态/分级告警/小红书跳过/Redis 降级 + accounthealth 端点接入
    assertSp4bCredentialCheck()
    assertSp4bAccountHealthEndpoint()

    #SP4c: 归档清理(dry-run 默认 / 先导出后删除 / 产物先置 EXPIRED 后 delFile) + 监控七项边界 + 告警占位无网络
    #  说明: 归档真删/连库路径以「桩替换数据层 + 桩替换文件门面」验证(桩验证); 指标判定与告警通道为真实调用
    assertSp4cArchiveDryRunAndOrder()
    assertSp4cArtifactPurgeOrder()
    assertSp4cMetricBoundaries()
    assertSp4cAlertChannelNoNetwork()
    assertSp4cGuardEntry()

    #释放单浏览器实例(进程内复用, 用完统一关闭)
    try:
        from engine import htmlToImage
        htmlToImage.closeBrowser()
    except Exception:
        pass

    failList = [name for name, ok, _ in _resultList if not ok]
    print(f"[smoke] done: total={len(_resultList)}, pass={len(_resultList) - len(failList)}, fail={len(failList)}")
    print(f"[smoke] 产物目录: {PREVIEW_DIR}")
    if failList:
        print(f"[smoke] failed items: {', '.join(failList)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
