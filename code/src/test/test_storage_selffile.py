#! /usr/bin/env python3
#encoding: utf-8

#Filename: test_storage_selffile.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   fileStorageCommon 门面 × SELFFILE 后端端到端冒烟
#对应 plan/ylwz文件服务多Bucket.md 7.2 I12(三后端一致性)的本地可跑子集:
#   SELFFILE 全链路 upload → exist → getTempUrl → getFileInfo → delete,
#   并验证决策 6.5「SELFFILE 一律解析为 default 桶(物理名 local)」。
#
#运行方式(工作目录须为 code/src):
#   python test/test_storage_selffile.py
#
#前置: 使用 config/basicSettings.py + selfFileSettings.py 的 local 路径(本项目 code/data/), 无需云 AK/Redis。

import os
import sys
import unittest

_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from config import basicSettings as settings
from config import selfFileSettings as sfSettings
from common import fileStorageCommon as fs


class SelfFileStorageTestCase(unittest.TestCase):

    @classmethod
    def tearDownClass(cls):
        """清理冒烟产生的探测文件(源文件 + 临时中转副本 + 存储副本)"""
        baseDir = sfSettings.LOCAL_FILE_SERVER_BASE
        for home, _dirs, files in os.walk(baseDir):
            for name in files:
                if name.startswith("probe_contenthub"):
                    try:
                        os.remove(os.path.join(home, name))
                    except OSError:
                        pass
        fileID = SelfFileStorageTestCase._fileID
        if fileID:
            for suffix in (".data", ".info"):
                probe = os.path.join(sfSettings.SELF_FILE_SERVER_STORAGE_DIR, fileID + suffix)
                if os.path.isfile(probe):
                    try:
                        os.remove(probe)
                    except OSError:
                        pass

    @classmethod
    def setUpClass(cls):
        #本地临时中转目录(线上由 web server 提供), 冒烟前确保存在
        for i in range(10):
            os.makedirs(os.path.join(sfSettings.LOCAL_FILE_SERVER_BASE,
                                     sfSettings.LOCAL_FILE_TEMP_WEB_DIR, str(i)), exist_ok=True)
        os.makedirs(sfSettings.SELF_FILE_SERVER_STORAGE_DIR, exist_ok=True)
        cls._fileID = ""

    def test00_precondition(self):
        """前置: local 环境必须是 SELFFILE, 且存储根目录可写"""
        self.assertEqual("SELFFILE", settings.FILE_SYSTEM_MODE)
        self.assertTrue(os.path.isdir(sfSettings.SELF_FILE_SERVER_STORAGE_DIR))

    def test01_saveFile(self):
        localPath = os.path.join(sfSettings.LOCAL_FILE_SERVER_BASE, "probe_contenthub.txt")
        with open(localPath, "w", encoding="utf-8") as hFile:
            hFile.write("hello content-hub multi-bucket")
        fileID = fs.saveFile(localPath, objectName="probe_contenthub.txt", mode="SELFFILE")
        self.assertTrue(fileID, "SELFFILE saveFile 应返回非空 fileID")
        SelfFileStorageTestCase._fileID = fileID

    def test02_existFile(self):
        self.assertTrue(fs.existFile(self._fileID, mode="SELFFILE"))

    def test03_getFileInfo(self):
        info = fs.getFileInfo(self._fileID, mode="SELFFILE")
        self.assertIsInstance(info, dict)
        self.assertEqual("probe_contenthub.txt", info.get("objectName"))
        #C4: 新写入的 .info 应含桶快照字段
        self.assertEqual("local", info.get("storageBucket"))
        self.assertEqual("default", info.get("bucketCode"))

    def test04_getTempUrl(self):
        url = fs.getFileTempUrl(self._fileID, mode="SELFFILE")
        self.assertTrue(url, "SELFFILE getFileTempUrl 应返回非空 url")
        self.assertIn("temp", url)
        #门面兼容入口(fileID 已是 http 则原样返回)
        self.assertEqual(url, fs.getTempLocation(url, mode="SELFFILE"))

    def test05_selffileBucketReserved(self):
        """决策 6.5: SELFFILE 传任意 bucketCode 一律解析为 default/local"""
        info = fs.getTempLocation(self._fileID, mode="SELFFILE",
                                 bucketCode="media", storageBucket="contenthub-media")
        self.assertTrue(info)
        self.assertEqual("local", fs.getBucketInfo("SELFFILE", "media")["bucketName"])

    def test06_deleteFile(self):
        self.assertTrue(fs.delFile(self._fileID, mode="SELFFILE"))
        self.assertFalse(fs.existFile(self._fileID, mode="SELFFILE"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
