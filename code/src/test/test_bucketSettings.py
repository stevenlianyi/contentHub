#! /usr/bin/env python3
#encoding: utf-8

#Filename: test_bucketSettings.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   多 Bucket 能力单元测试与兼容性验收
#对应 plan/ylwz文件服务多Bucket.md:
#  7.1 单元测试 U1-U9; 7.3 回归验收 A2/A3; I13(F9A0 诊断) 的本地可跑子集
#
#运行方式(工作目录须为 code/src):
#   python test/test_bucketSettings.py
#
#说明: 本套用例只依赖 config 层与适配器常量, 不需要 MySQL/Redis/云 AK, 可离线全跑。

import os
import sys
import unittest

#把 code/src 加入 sys.path, 保证直接执行本文件时也能 import config/common
_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from config import basicSettings as settings
from config import aliyunSettings
from config import tencentSettings
from config import bucketSettings as comBucket


class BucketSettingsTestCase(unittest.TestCase):
    """配置层多桶解析(U1-U9)"""

    #—— U1 ——
    def testU1_getBucketInfoAliossByCode(self):
        info = comBucket.getBucketInfo("ALIOSS", bucketCode="media")
        self.assertEqual("media", info["bucketCode"])
        #物理桶名随环境而定(server_02 的 media 与 artifact 共用 contenthub-private), 故从配置取期望值
        self.assertEqual(aliyunSettings.ALIYUN_OSS_BUCKETS["Buckets"]["media"]["BucketName"], info["bucketName"])
        self.assertEqual("media/", info["pathPrefix"])
        self.assertEqual("private", info["access"])

    #—— U2 ——
    def testU2_getBucketInfoAliossDefault(self):
        info = comBucket.getBucketInfo("ALIOSS")
        self.assertEqual(aliyunSettings.ALIYUN_OSS_SERVICE["DefaultBucketCode"], info["bucketCode"])
        self.assertEqual(aliyunSettings.ALIYUN_OSS_SERVICE["BucketName"], info["bucketName"])
        self.assertEqual("", info["pathPrefix"])

    #—— U3 ——
    def testU3_getBucketInfoTencentPrivate(self):
        info = comBucket.getBucketInfo("TENCENT", privateFlag=True)
        self.assertEqual("private", info["bucketCode"])
        self.assertEqual(tencentSettings.TECENT_COS_SERVICE["privateBucketName"], info["bucketName"])

    #—— U4 ——
    def testU4_getBucketInfoTencentPublic(self):
        info = comBucket.getBucketInfo("TENCENT", privateFlag=False)
        self.assertEqual("public", info["bucketCode"])
        self.assertEqual(tencentSettings.TECENT_COS_SERVICE["bucketName"], info["bucketName"])

    #—— U5: 决策 6.2① bucketCode 优先于 privateFlag ——
    def testU5_bucketCodePriorityOverPrivateFlag(self):
        info = comBucket.getBucketInfo("ALIOSS", bucketCode="media", privateFlag=True)
        self.assertEqual("media", info["bucketCode"])
        info2 = comBucket.getBucketInfo("TENCENT", bucketCode="media", privateFlag=False)
        self.assertEqual("media", info2["bucketCode"])
        self.assertEqual("xjy-media-home", info2["bucketName"])

    #—— U6: 决策 6.4 未知桶码报错 ——
    def testU6_unknownBucketCodeRaises(self):
        with self.assertRaises(comBucket.BucketConfigError):
            comBucket.getBucketInfo("ALIOSS", bucketCode="notexist")
        with self.assertRaises(comBucket.BucketConfigError):
            comBucket.getBucketInfo("TENCENT", bucketCode="notexist")
        #读取路径必须保持宽容: 未知桶码不报错, 回落默认桶(否则历史数据大面积不可读)
        snapshot = comBucket.resolveBucketBySnapshot("ALIOSS", bucketCode="notexist")
        self.assertEqual(comBucket.getDefaultBucketCode("ALIOSS"), snapshot["bucketCode"])

    #—— U7: STS Resource 自动覆盖全部桶 ——
    def testU7_stsResourceCoversAllBuckets(self):
        buckets = aliyunSettings.ALIYUN_OSS_BUCKETS["Buckets"]
        resource = aliyunSettings.ALIYUN_OSS_SERVICE["stsPolicyData"]["Statement"][0]["Resource"]
        self.assertEqual(len(buckets) * 2, len(resource))
        self.assertEqual(sorted(aliyunSettings._genStsResource(buckets)), sorted(resource))
        for _code, b in buckets.items():
            self.assertIn(f"acs:oss:*:*:{b['BucketName']}", resource)
            self.assertIn(f"acs:oss:*:*:{b['BucketName']}/*", resource)

    #—— U8: 按物理桶名反查桶码 ——
    def testU8_resolveBucketBySnapshot(self):
        #注意: media 与 artifact 可能共用同一物理桶(server_02 为 contenthub-private), 反查只取首个匹配,
        #故用物理名唯一且可预期的 public 桶验证反查能力
        publicName = aliyunSettings.ALIYUN_OSS_BUCKETS["Buckets"]["public"]["BucketName"]
        info = comBucket.resolveBucketBySnapshot("ALIOSS", storageBucket=publicName)
        self.assertEqual("public", info["bucketCode"])
        self.assertEqual(publicName, info["bucketName"])

    #—— U9: 快照为空回落默认桶 ——
    def testU9_resolveBucketBySnapshotEmpty(self):
        info = comBucket.resolveBucketBySnapshot("ALIOSS")
        self.assertEqual(comBucket.getDefaultBucketCode("ALIOSS"), info["bucketCode"])
        #TENCENT 默认桶为 private, 与旧版 privateFlag 默认语义一致
        info2 = comBucket.resolveBucketBySnapshot("TENCENT")
        self.assertEqual("private", info2["bucketCode"])

    #—— 决策 6.2① 组合优先级: 桶码 > 物理桶名快照 > 默认 ——
    def testSnapshotPriority(self):
        #storageBucket 指向默认桶(反查本会得到 default), 传入 bucketCode=media 时必须由 bucketCode 胜出
        defaultName = aliyunSettings.ALIYUN_OSS_BUCKETS["Buckets"][
            aliyunSettings.ALIYUN_OSS_BUCKETS["DefaultBucketCode"]]["BucketName"]
        info = comBucket.resolveBucketBySnapshot("ALIOSS", storageBucket=defaultName, bucketCode="media")
        self.assertEqual("media", info["bucketCode"])

    #—— 多逻辑桶复用同一物理桶: 读取路径按 objectName 前缀消歧 ——
    #(server_02: media 与 artifact 共用 contenthub-private, 前缀分别为 media/ 与 artifact/)
    def testSnapshotDisambiguatesSharedBucket(self):
        buckets = aliyunSettings.ALIYUN_OSS_BUCKETS["Buckets"]
        if buckets["media"]["BucketName"] != buckets["artifact"]["BucketName"]:
            self.skipTest("当前环境 media/artifact 未复用同一物理桶")
        shared = buckets["media"]["BucketName"]
        #只有物理桶名快照时, 凭对象键前缀命中 artifact, 且不再二次拼前缀
        info = comBucket.resolveBucketBySnapshot("ALIOSS", shared, objectName="artifact/x.jpg")
        self.assertEqual("artifact", info["bucketCode"])
        self.assertEqual("artifact/x.jpg", comBucket.applyPathPrefix(info, "artifact/x.jpg"))
        info2 = comBucket.resolveBucketBySnapshot("ALIOSS", shared, objectName="media/x.jpg")
        self.assertEqual("media", info2["bucketCode"])
        #不传 objectName 时维持旧行为(首个匹配), 既有调用方不受影响
        info3 = comBucket.resolveBucketBySnapshot("ALIOSS", shared)
        self.assertEqual("media", info3["bucketCode"])

    #—— 决策 6.5: SELFFILE 仅做语义预留 ——
    def testSelffileSemanticsReserved(self):
        info = comBucket.getBucketInfo("SELFFILE", bucketCode="media")
        self.assertEqual("default", info["bucketCode"])
        self.assertEqual("local", info["bucketName"])
        self.assertEqual({}, comBucket.listBuckets("SELFFILE"))
        self.assertFalse(comBucket.isMultiBucketSupported("SELFFILE"))

    #—— 路径前缀幂等(A7/I3) ——
    def testApplyPathPrefixIdempotent(self):
        info = comBucket.getBucketInfo("ALIOSS", bucketCode="media")
        self.assertEqual("media/x.jpg", comBucket.applyPathPrefix(info, "x.jpg"))
        self.assertEqual("media/x.jpg", comBucket.applyPathPrefix(info, "media/x.jpg"))
        defaultInfo = comBucket.getBucketInfo("ALIOSS")
        self.assertEqual("x.jpg", comBucket.applyPathPrefix(defaultInfo, "x.jpg"))

    #—— A2: 配置向后兼容 ——
    def testA2_configBackwardCompatible(self):
        self.assertTrue(aliyunSettings.ALIYUN_OSS_SERVICE["BucketName"])
        self.assertEqual(aliyunSettings.ALIYUN_OSS_BUCKETS["Buckets"][
            aliyunSettings.ALIYUN_OSS_BUCKETS["DefaultBucketCode"]]["BucketName"],
            aliyunSettings.ALIYUN_OSS_SERVICE["BucketName"])
        #TENCENT 兼容别名语义与旧版一致
        svc = tencentSettings.TECENT_COS_SERVICE
        self.assertEqual(svc["Buckets"]["private"]["BucketName"], svc["privateBucketName"])
        self.assertEqual(svc["Buckets"]["private"]["Url"], svc["privateUrl"])
        self.assertEqual(svc["Buckets"]["public"]["BucketName"], svc["bucketName"])
        self.assertEqual(svc["Buckets"]["public"]["Url"], svc["url"])

    #—— A3: 适配器常量兼容 ——
    def testA3_adapterConstantsCompatible(self):
        from common import aliyunOSS as OSS
        from common import tencentCOS as COS
        self.assertEqual(aliyunSettings.ALIYUN_OSS_SERVICE["BucketName"], OSS.BucketNamePrivate)
        self.assertEqual(tencentSettings.TECENT_COS_SERVICE["privateBucketName"], COS.privateBucketName)
        self.assertEqual(tencentSettings.TECENT_COS_SERVICE["bucketName"], COS.bucketName)

    #—— A1: 适配器签名尾部追加参数, 旧调用零改动(R4) ——
    def testA1_adapterSignaturesAppendOnly(self):
        import inspect
        from common import aliyunOSS as OSS
        from common import tencentCOS as COS
        from common import selfFileCommon as SF
        expected = {
            OSS.uploadFile: ["objName", "fileName", "downloadName", "bucketCode"],
            OSS.downloadFile: ["objName", "fileName", "bucketCode"],
            OSS.existFile: ["objName", "bucketCode"],
            OSS.deleteFile: ["objName", "bucketCode"],
            OSS.getFileInfo: ["objName", "bucketCode"],
            OSS.genFileTempUrl: ["objName", "timeOut", "bucketCode"],
            OSS.genFileUploadUrl: ["objName", "timeOut", "bucketCode"],
            OSS.genSTSToken: ["objName", "sessionName", "bucketCode"],
            COS.uploadFile: ["keyName", "fileName", "privateFlag", "bucketCode"],
            COS.downloadFile: ["keyName", "fileName", "privateFlag", "bucketCode"],
            COS.existFile: ["keyName", "privateFlag", "bucketCode"],
            COS.getFileInfo: ["keyName", "privateFlag", "bucketCode"],
            COS.deleteFile: ["keyName", "privateFlag", "bucketCode"],
            COS.setFileAccess: ["keyName", "accessRight", "privateFlag", "bucketCode"],
            COS.genFileTempUrl: ["keyName", "privateFlag", "bucketCode"],
            COS.genFilePublicUrl: ["keyName", "privateFlag", "bucketCode"],
            COS.listFiles: ["maxNum", "privateFlag", "bucketCode"],
            SF.uploadFile: ["fileInfo", "privateFlag", "bucketCode"],
            SF.deleteFile: ["fileID", "privateFlag", "bucketCode"],
        }
        for func, names in expected.items():
            params = list(inspect.signature(func).parameters.keys())
            self.assertEqual(names, params, f"{func.__name__} 签名不符合「仅尾部追加」约束")

    #—— I13: F9A0 诊断(本地可跑: 用同源摘要生成 token, 不依赖 Redis) ——
    def testI13_f9a0Diagnostics(self):
        try:
            from main import ylwzRecvFiles as recv
            from common import funcCommon as comFC
        except Exception as e:
            self.skipTest(f"跳过 F9A0 用例(依赖未就绪): {e}")

        self.assertIn("F9A0", recv.urlPathMap)
        YMDHMS = "20260918120000"
        token = comFC.genDigest(settings.GEN_DIGIST_KEY, "F9A0", YMDHMS)
        rtn = recv.cmdF9A0("F9A0", {"token": token, "YMDHMS": YMDHMS, "fileSystem": "ALIOSS"}, {})
        self.assertEqual("B0", rtn.get("errCode"))
        self.assertEqual("ALIOSS", rtn.get("fileSystem"))
        self.assertEqual(aliyunSettings.ALIYUN_OSS_SERVICE["DefaultBucketCode"], rtn.get("defaultBucketCode"))
        codes = [b["bucketCode"] for b in rtn.get("buckets", [])]
        self.assertEqual(sorted(aliyunSettings.ALIYUN_OSS_BUCKETS["Buckets"].keys()), sorted(codes))
        #确认不泄露密钥字段
        dumped = str(rtn)
        for secret in ["AccessKeySecret", "AccessKeyId", "roleArn", "Endpoint"]:
            self.assertNotIn(secret, dumped)


if __name__ == "__main__":
    unittest.main(verbosity=2)
