#! /usr/bin/env python3
#encoding: utf-8

#Filename: __init__.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 渲染引擎层(engine/)包声明(C4 版式引擎, SP2c 落点)。

#★ 分层契约(强制单向, 与 processor/__init__.py 一致; 见 code/src/plan.md §3/§4):
#    接入层(main/) -> 业务处理器层(processor/) -> 引擎层(engine/) -> 公共层(common/)
#
#  本层只做「版式调度 + 模板渲染 + 渲染期图像派生」, 约束如下:
#    1) 只依赖公共层(common/)——数据只经 common/mysqlCommon.py(读 ch_layout), 文件只经
#       common/fileStorageCommon.py; 禁裸 SQL(红线 R1)、禁厂商分支(红线 R2);
#    2) **不得 import processor/ 或 subfunc/**(否则破坏单向依赖, 形成反向/循环依赖)——
#       主题与附图数据由业务层取好后传入(见 engine/layoutEngine.py 的入参约定);
#    3) 错误码统一 contenthub msgKey 的 E 段(渲染与产物): E0 模板缺失 / E1 渲染失败 /
#       E2 截图超时(SP3) / E3 产物生成失败;
#    4) 渲染层禁止直接拼 SQL 查询, 一律经 mysqlCommon 的 query_ch_* 系列。
#
#本轮(SP2c)落点:
#  - layoutEngine.py      版式调度(唯一渲染入口): 读 ch_layout -> 注入 specJson -> Jinja2 渲染
#  - imageProc.py         渲染期派生图像处理(Pillow): 封面 900x500 裁切 / 卡片 1080x1440 统一 /
#                         长图切片; 与 processor/assetService.py 的「入库前处理」明确分工
#  - templates/           4 套内置版式模板(stack_v1 / carousel_v1 / longimage_v1 / swipe_v1)
#                         + partials/base.html(共用骨架) + preview/(站内手机框模拟预览)
#
#后续子计划: C5 平台适配(inlineStyle.py 微信内联化 / htmlToImage.py Playwright 截图) 属 SP3。

_VERSION="20260919"
