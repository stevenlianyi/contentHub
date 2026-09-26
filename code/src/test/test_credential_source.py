#! /usr/bin/env python3
#encoding: utf-8

#Filename: test_credential_source.py
#Description: 「平台凭据来源收口」回归测试(★ 2026-09-24): 公众号凭据(appID/appSecret)只来自
#  **用户录入**的 ch_account 密文, **不回落环境变量** CH_WECHAT_APPID / CH_WECHAT_APPSECRET。
#  覆盖:
#    1) 账号未录入凭据 → F0, 文案引导到「第三方账号管理」录入(即使环境变量有值也**不使用**);
#    2) appID 同样不回落环境变量(须与 AppSecret 成对取自同一条账号记录);
#    3) 正向: 服务端加密写入的密文可解密, source=ch_account.cipher, appID 取自记录(非环境变量);
#    4) wechatMp.checkHealth 的凭据判定改由 ch_account.credentialCipher 派生(仍零网络);
#    5) 静态红线: publishService 不再出现 WECHAT_APP_ID / WECHAT_APP_SECRET, 文案不再提环境变量;
#       而 config/wechatSettings.py 的同名常量**保留**(兼容 S9 静态断言), 只是不再作为凭据来源。
#  运行: cd code/src && python test/test_credential_source.py   (退出码 0=全过)
#  ★ 不连库/不联网: 导入期 stub config.mysqlSettings(避免 mysqlHandle 真连库), 数据层按需替换为内存实现;
#    加密主密钥 CH_CREDENTIAL_KEY 由本测试临时注入(仅本机自验, 非生产密钥)。
#  来源: plan/前端开发计划.md 附录 B R-36 / 附录 G v1.11。

import os
import re
import sys
import types

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC_DIR)

#===== 导入期 stub: 避免连库 =====
_stubMS = types.ModuleType("config.mysqlSettings")
_stubMS.mysqlDB = None
_stubMS.MYSQL_READ_DB = "stub_db"
sys.modules["config.mysqlSettings"] = _stubMS

from common import credentialCipher
from config import wechatSettings
from processor import publishService as publishSvc
from processor.platformAdapter import wechatMp as wechatMpMod
from processor.platformAdapter.wechatMp import WechatMpAdapter

FAIL_LIST = []
PASS_COUNT = [0]

def check(title, ok, detail = ""):
    if ok:
        PASS_COUNT[0] += 1
        print("[PASS] %s %s" % (title, detail))
    else:
        FAIL_LIST.append(title)
        print("[FAIL] %s %s" % (title, detail))

#本机自验用主密钥(64 位 hex = 32 字节; 非生产密钥, 仅写入本测试进程环境)
TEST_KEY_HEX = "5a1c9e07f3b28d6417ecaa905b3f8d12a4c7eb0196d3f8527ab4ce3168092fd7"
#环境变量"有值"哨兵: 若实现仍回落环境变量, 下列断言必失败
ENV_SECRET_SENTINEL = "env-should-never-be-used-0001"
ENV_APPID_SENTINEL = "wxenvshouldneverbeused"

def fakeEnvConfigured():
    """模拟「环境变量已配置凭据」: 直接把哨兵写进 wechatSettings 常量(等价于导出了对应环境变量)"""
    origin = (wechatSettings.WECHAT_APP_SECRET, wechatSettings.WECHAT_APP_ID)
    wechatSettings.WECHAT_APP_SECRET = ENV_SECRET_SENTINEL
    wechatSettings.WECHAT_APP_ID = ENV_APPID_SENTINEL
    return origin

def restoreEnv(origin):
    wechatSettings.WECHAT_APP_SECRET, wechatSettings.WECHAT_APP_ID = origin

def errText(errRtn):
    return ";".join((errRtn or {}).get("errMsgList") or [])

print("=" * 78)
print("1) 账号未录入凭据 -> F0(环境变量有值也不使用)")
print("=" * 78)
origin = fakeEnvConfigured()
try:
    credential, errRtn = publishSvc.decryptAccountCredential(
        {"recID": "1", "appID": "wx-record-1", "credentialCipher": "", "credentialIV": ""})
finally:
    restoreEnv(origin)
check("未录入凭据返回 F0 且不产出凭据", credential is None and (errRtn or {}).get("errCode") == "F0",
      "errCode=%s" % (errRtn or {}).get("errCode"))
msg = errText(errRtn)
check("文案引导用户到页面录入", "第三方账号管理" in msg, msg[:90])
check("文案不再提及环境变量/CH_WECHAT_APPSECRET",
      ("环境变量" not in msg) and ("CH_WECHAT_APPSECRET" not in msg), msg[:90])

print()
print("=" * 78)
print("2) appID 同样不回落环境变量(须与 AppSecret 同源)")
print("=" * 78)
os.environ["CH_CREDENTIAL_KEY"] = TEST_KEY_HEX
cipherRtn = credentialCipher.encrypt("demo-secret-42")
origin = fakeEnvConfigured()
try:
    credential, errRtn = publishSvc.decryptAccountCredential(
        {"recID": "2", "appID": "", "credentialCipher": cipherRtn["cipher"],
         "credentialIV": cipherRtn["iv"], "healthStatus": "OK"})
finally:
    restoreEnv(origin)
check("记录 appID 为空 -> F0(不取环境 appID)", credential is None and (errRtn or {}).get("errCode") == "F0",
      "errCode=%s" % (errRtn or {}).get("errCode"))
msg = errText(errRtn)
check("appID 文案引导页面填写且不提环境变量",
      ("第三方账号管理" in msg) and ("CH_WECHAT_APPID" not in msg), msg[:90])

print()
print("=" * 78)
print("3) 正向: 密文可解密, 凭据与 appID 均取自该账号记录")
print("=" * 78)
origin = fakeEnvConfigured()
try:
    credential, errRtn = publishSvc.decryptAccountCredential(
        {"recID": "3", "appID": "wx-record-3", "credentialCipher": cipherRtn["cipher"],
         "credentialIV": cipherRtn["iv"], "healthStatus": "OK", "expireYMDHMS": ""})
finally:
    restoreEnv(origin)
check("解密成功且无错误", credential is not None and errRtn is None, "errRtn=%s" % errRtn)
check("appSecret 来自 ch_account 密文(非环境变量哨兵)",
      (credential or {}).get("appSecret") == "demo-secret-42"
      and (credential or {}).get("appSecret") != ENV_SECRET_SENTINEL,
      "source=%s" % (credential or {}).get("source"))
check("source 标记为 ch_account.cipher", (credential or {}).get("source") == "ch_account.cipher",
      "source=%s" % (credential or {}).get("source"))
check("appID 取自记录而非环境变量", (credential or {}).get("appID") == "wx-record-3",
      "appID=%s" % (credential or {}).get("appID"))

print()
print("=" * 78)
print("4) wechatMp.checkHealth: 凭据判定改由 ch_account.credentialCipher 派生(零网络)")
print("=" * 78)
originQuery = wechatMpMod.comMysql.query_ch_account
adapter = WechatMpAdapter()
try:
    cases = [
        ("有账号已配置密文", [{"recID": "11", "accountCode": "WX-OK", "platform": "wechat_mp",
                               "credentialCipher": "abc", "credentialIV": "iv", "healthStatus": "OK"}], "1", []),
        ("账号均无密文", [{"recID": "12", "accountCode": "WX-EMPTY", "platform": "wechat_mp",
                           "credentialCipher": "", "credentialIV": "", "healthStatus": "UNKNOWN"}], "0", ["WX-EMPTY"]),
    ]
    for title, rows, expectConfigured, expectMissing in cases:
        wechatMpMod.comMysql.query_ch_account = lambda *args, **kwargs: [dict(r) for r in rows]
        rtn = adapter.checkHealth()
        data = rtn.get("data") or {}
        check("checkHealth(%s) credentialConfigured=%s" % (title, expectConfigured),
              (rtn.get("errCode") == "B0") and data.get("credentialConfigured") == expectConfigured,
              "data.credentialConfigured=%s" % data.get("credentialConfigured"))
        check("checkHealth(%s) missingList 由密文缺失派生" % title,
              (data.get("credentialMissingList") or []) == expectMissing,
              "missingList=%s" % data.get("credentialMissingList"))
        check("checkHealth(%s) 零网络且标记来源" % title,
              data.get("networkRequest") == "0" and data.get("credentialSource") == "ch_account.credentialCipher",
              "networkRequest=%s, source=%s" % (data.get("networkRequest"), data.get("credentialSource")))
finally:
    wechatMpMod.comMysql.query_ch_account = originQuery

print()
print("=" * 78)
print("5) 静态红线: 凭据链路不再引用环境凭据常量")
print("=" * 78)
publishPath = os.path.join(SRC_DIR, "processor", "publishService.py")
with open(publishPath, "r", encoding = "utf-8") as hFile:
    publishText = hFile.read()
check("publishService 不再引用 WECHAT_APP_SECRET", "WECHAT_APP_SECRET" not in publishText)
check("publishService 不再引用 WECHAT_APP_ID", "WECHAT_APP_ID" not in publishText)
#★ 注释/文档串中允许出现旧常量名(用于说明口径变更), 但**运行期取用**必须不存在
_credGetattrPattern = re.compile(r"getattr\(\s*wechatSettings\s*,\s*[\"']WECHAT_APP_(ID|SECRET)[\"']")
check("publishService 运行期不再从 wechatSettings 取用凭据常量",
      _credGetattrPattern.search(publishText) is None)
check("publishService 不再存在 source=\"env\" 的兜底分支", '"env"' not in publishText)
check("wechatSettings 同名常量保留(兼容 S9 静态断言)",
      hasattr(wechatSettings, "WECHAT_APP_ID") and hasattr(wechatSettings, "WECHAT_APP_SECRET"),
      "WECHAT_APP_ID=%r, WECHAT_APP_SECRET 类型=%s" % (wechatSettings.WECHAT_APP_ID, type(wechatSettings.WECHAT_APP_SECRET).__name__))
check("加密主密钥仍走环境变量 CH_CREDENTIAL_KEY(红线不变)",
      credentialCipher.KEY_ENV_NAME == "CH_CREDENTIAL_KEY", "KEY_ENV_NAME=%s" % credentialCipher.KEY_ENV_NAME)

print()
print("=" * 78)
print("汇总: pass=%d, fail=%d" % (PASS_COUNT[0], len(FAIL_LIST)))
if FAIL_LIST:
    print("失败项: %s" % FAIL_LIST)
print("=" * 78)
sys.exit(1 if FAIL_LIST else 0)
