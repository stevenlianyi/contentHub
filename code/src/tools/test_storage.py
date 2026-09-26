#! /usr/bin/env python3
#encoding: utf-8

#Filename: test_storage.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   文件存储门面(common/fileStorageCommon.py)三后端联调脚本:
#对 ALIOSS / TENCENT / SELFFILE 各跑一遍 上传 -> 取链接 -> 下载 -> 删除。
#
#用途: 验证 D2 签名归一化 shim 与多桶解析在三个后端上都可用(主计划 T7 验收)。
#说明: 本脚本不修改任何业务数据; 上传的探针文件名带模式后缀, 跑完即删。
#      ALIOSS/TENCENT 需先在 config/*Settings.py 配好 AK 与桶, 未配置时该项会失败(属预期)。
#
#用法: cd code/src && python tools/test_storage.py

_VERSION="20260918"

import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)

import tempfile

from config import basicSettings as settings

from common import fileStorageCommon as comFS
from common import miscCommon as misc

_processorPID = os.getpid()

MODE_LIST = ["ALIOSS", "TENCENT", "SELFFILE"]


def probe(mode):
    """单后端探针: 上传 -> 取链接 -> 下载 -> 删除, 返回 (ok, 说明)"""
    localPath = os.path.join(tempfile.gettempdir(), f"ch_probe_{mode}_{misc.getTime()}.txt")
    targetPath = os.path.join(tempfile.gettempdir(), f"ch_probe_{mode}_{misc.getTime()}_back.txt")
    objectName = f"probe_{mode}_{misc.getTime()}.txt"

    with open(localPath, "w", encoding = "utf-8") as hFile:
        hFile.write("hello content-hub")

    resultList = []
    try:
        fileID = comFS.saveFile(localPath, objectName = objectName, mode = mode)
        resultList.append(f"upload={bool(fileID)}({fileID})")

        url = comFS.getFileTempUrl(fileID, mode = mode)
        resultList.append(f"url={bool(url)}")

        backPath = comFS.downloadFile(fileID, targetPath, mode = mode)
        resultList.append(f"download={bool(backPath)}")

        delFlag = comFS.delFile(fileID, mode = mode)
        resultList.append(f"delete={bool(delFlag)}")

        ok = bool(fileID) and bool(url) and bool(backPath) and bool(delFlag)
    except Exception as e:
        resultList.append(f"error={e}")
        ok = False

    for path in (localPath, targetPath):
        try:
            if os.path.isfile(path):
                os.remove(path)
        except Exception:
            pass

    return ok, ", ".join(resultList)


def main():
    print(f"[test_storage] PID:{_processorPID}, _SYS:{settings._SYS}, FILE_SYSTEM_MODE:{settings.FILE_SYSTEM_MODE}")

    okCount = 0
    for mode in MODE_LIST:
        ok, detail = probe(mode)
        flag = "OK  " if ok else "FAIL"
        print(f"[test_storage] {flag} {mode}: {detail}")
        if ok:
            okCount += 1

    print(f"[test_storage] done: ok={okCount}, total={len(MODE_LIST)}")
    return 0 if okCount == len(MODE_LIST) else 1


if __name__ == "__main__":
    sys.exit(main())
