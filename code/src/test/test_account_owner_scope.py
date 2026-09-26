#! /usr/bin/env python3
#encoding: utf-8

#Filename: test_account_owner_scope.py
#Description: 「第三方账号管理」(P-14 /my-accounts) 账号归属隔离 与 凭据巡检归属收窄 的回归测试。
#  覆盖: 1) 归属读隔离(含 searchOption 越权旁路) / 2) 写入归属强制 / 3) 归属写隔离(BG) /
#        4) 管理员(administrator/manager)超管例外 / 5) 巡检与汇总按归属收窄 + 定时任务缺省全量 /
#        6) ROLE_CMD_LIST 授权面(operator/customer 有, visitor 无) + V3 完整性(端点总数仍 72)。
#  运行: cd code/src && python test/test_account_owner_scope.py   (退出码 0=全过)
#  ★ 不连数据库/Redis: 导入期 stub 掉 config.mysqlSettings(避免 mysqlHandle 真连库)并按「独立模块名」
#    加载真实 schedule/credentialCheck.py(不触发 runOnce 的 Redis 锁与心跳), 数据层函数替换为内存实现 ——
#    跑的仍是 crudApi / credentialCheck / accountApi 的**真实处理器代码路径**。
#  来源: plan/前端开发计划.md 附录 B R-35(归属隔离) / 附录 G v1.10。

import os
import sys
import types

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC_DIR)

#===== 导入期 stub: 避免连库 =====
_stubMS = types.ModuleType("config.mysqlSettings")
_stubMS.mysqlDB = None
_stubMS.MYSQL_READ_DB = "stub_db"
sys.modules["config.mysqlSettings"] = _stubMS

#===== 导入期 stub: schedule.credentialCheck(accountApi 函数内延迟导入) =====
CAPTURE = {}
_credStub = types.ModuleType("schedule.credentialCheck")
def _stubRunOnce(dataSet = None, fetchAccessTokenFunc = None):
    CAPTURE["runOnce_dataSet"] = dict(dataSet or {})
    return {"total": 0, "checked": 0, "ok": 0, "expiring": 0, "invalid": 0, "unknown": 0,
            "skipped": 0, "degraded": 0, "warnDays": 7, "items": [], "alertSummary": {},
            "checkedAt": "20260923120000"}
_credStub.runOnce = _stubRunOnce
sys.modules["schedule.credentialCheck"] = _credStub

from main.subfunc import crudApi
from main.subfunc import accountApi
from common import mysqlCommon as comMysql

FAIL_LIST = []
PASS_COUNT = [0]

def check(title, ok, detail = ""):
    if ok:
        PASS_COUNT[0] += 1
        print("[PASS] %s %s" % (title, detail))
    else:
        FAIL_LIST.append(title)
        print("[FAIL] %s %s" % (title, detail))

#===== 内存数据层 =====
DB = {
    # recID -> 记录
    "11": {"recID": "11", "accountCode": "A-11", "accountName": "李思远的号", "platform": "wechat_mp",
           "ownerID": "lisiyuan", "healthStatus": "OK", "expireYMDHMS": "", "label": "本人"},
    "12": {"recID": "12", "accountCode": "A-12", "accountName": "别人的号", "platform": "wechat_mp",
           "ownerID": "chenlh", "healthStatus": "INVALID", "expireYMDHMS": "", "label": "他人"},
    "13": {"recID": "13", "accountCode": "A-13", "accountName": "周敏的号", "platform": "wechat_mp",
           "ownerID": "zhoumin", "healthStatus": "EXPIRING", "expireYMDHMS": "", "label": "他人2"},
}
CAPTURE["query_kwargs"] = []
CAPTURE["insert_saveSet"] = None
CAPTURE["update_called"] = None
CAPTURE["delete_called"] = None

def fake_table_name():
    return "ch_account"

def fake_query_ch_account(tableName, recID = "0", accountCode = "", platform = "",
                          healthStatus = "", ownerID = "", delFlag = "0", mode = "full",
                          order = "create", limitNum = 0):
    CAPTURE["query_kwargs"].append({"recID": str(recID), "ownerID": str(ownerID), "platform": str(platform),
                                    "healthStatus": str(healthStatus), "mode": str(mode)})
    rows = list(DB.values())
    if str(recID) not in ("", "0"):
        rows = [r for r in rows if str(r.get("recID")) == str(recID)]
    if ownerID:
        rows = [r for r in rows if str(r.get("ownerID", "")) == str(ownerID)]
    if platform:
        rows = [r for r in rows if str(r.get("platform", "")) == str(platform)]
    if healthStatus:
        rows = [r for r in rows if str(r.get("healthStatus", "")) == str(healthStatus)]
    return [dict(r) for r in rows]

def fake_insert_ch_account(tableName, saveSet):
    CAPTURE["insert_saveSet"] = dict(saveSet)
    return 9001

def fake_update_ch_account(tableName, recID, saveSet):
    CAPTURE["update_called"] = {"recID": str(recID), "saveSet": dict(saveSet)}
    return 1

def fake_delete_ch_account(tableName, recID):
    CAPTURE["delete_called"] = str(recID)
    return 1

comMysql.query_ch_account = fake_query_ch_account
comMysql.insert_ch_account = fake_insert_ch_account
comMysql.update_ch_account = fake_update_ch_account
comMysql.delete_ch_account = fake_delete_ch_account
comMysql.tablename_convertor_ch_account = fake_table_name

#查询缓冲: 关闭真实实现(避免 Redis), 用内存捕获被写入的行
BUFFER = {}
crudApi.chkBufferExist = lambda indexKey: False
crudApi.putQuery2Buffer = lambda indexKey, dataList: (BUFFER.__setitem__("rows", [dict(r) for r in dataList]), indexKey)[1]
crudApi.genBufferIndexKey = lambda CMD, sessionID, indexKeyDataSet: "IK|%s|%s|%s" % (CMD, sessionID, repr(sorted(indexKeyDataSet.items())))
crudApi.getQueryBufferComplte = lambda indexKey, beginNum = 0, endNum = 0: {"data": BUFFER.get("rows", []), "total": len(BUFFER.get("rows", []))}

def reset():
    CAPTURE["query_kwargs"] = []
    CAPTURE["insert_saveSet"] = None
    CAPTURE["update_called"] = None
    CAPTURE["delete_called"] = None
    BUFFER.clear()

def sess(loginID, roleName):
    return {"loginID": loginID, "roleName": roleName, "openID": "op-%s" % loginID, "sessionID": "sid-%s" % loginID}

print("=" * 78)
print("验收 1) 归属读隔离 —— 非管理员 accountqry 强制 ownerID = loginID")
print("=" * 78)
#--- operator 请求里传别人的 ownerID='chenlh' -> 必须被覆盖为 lisiyuan
reset()
res = crudApi.funcAccountQry("accountqry", {"ownerID": "chenlh", "mode": "full"}, sess("lisiyuan", "operator"))
rows = BUFFER.get("rows", [])
owners = sorted(set(str(r.get("ownerID", "")) for r in rows))
check("operator 传他人 ownerID 被忽略", owners == ["lisiyuan"], "返回行归属=%s, errCode=%s" % (owners, res.get("errCode")))
check("operator 查询条件 ownerID 被强制", CAPTURE["query_kwargs"][-1]["ownerID"] == "lisiyuan",
      "实际 query ownerID=%r" % CAPTURE["query_kwargs"][-1]["ownerID"])

#--- customer 同理
reset()
crudApi.funcAccountQry("accountqry", {"ownerID": "zhoumin", "mode": "full"}, sess("wangys", "customer"))
check("customer 传他人 ownerID 被忽略", BUFFER.get("rows", []) == [],
      "返回行数=%d(库中无 wangys 记录)" % len(BUFFER.get("rows", [])))
check("customer 查询条件 ownerID 被强制", CAPTURE["query_kwargs"][-1]["ownerID"] == "wangys",
      "实际 query ownerID=%r" % CAPTURE["query_kwargs"][-1]["ownerID"])

print()
print("=" * 78)
print("验收 6) searchOption 旁路 —— 非管理员不得跨用户读全表(需求未覆盖的越权缺口)")
print("=" * 78)
reset()
crudApi.funcAccountQry("accountqry", {"mode": "full",
                                      "searchOption": {"keyword": "号", "allowList": ["label", "description"]}},
                       sess("lisiyuan", "operator"))
rows = BUFFER.get("rows", [])
owners = sorted(set(str(r.get("ownerID", "")) for r in rows))
check("searchOption 分支二次按归属过滤", owners == ["lisiyuan"], "返回行归属=%s(全表 3 条)" % owners)

print()
print("=" * 78)
print("验收 2) 写入归属 —— accountadd 非管理员强制 ownerID = loginID")
print("=" * 78)
reset()
crudApi.funcAccountAdd("accountadd", {"accountCode": "A-99", "platform": "wechat_mp", "accountName": "n",
                                      "subjectType": "personal", "capability": "draft_box",
                                      "ownerID": "chenlh"}, sess("lisiyuan", "operator"))
check("operator 新增落库 ownerID=本人", (CAPTURE["insert_saveSet"] or {}).get("ownerID") == "lisiyuan",
      "saveSet.ownerID=%r(请求传的是 chenlh)" % (CAPTURE["insert_saveSet"] or {}).get("ownerID"))

print()
print("=" * 78)
print("验收 3) 归属写隔离 —— accountmodify / accountdel 越权返回 BG")
print("=" * 78)
reset()
res = crudApi.funcAccountModify("accountmodify", {"recID": "12", "accountName": "改名"}, sess("lisiyuan", "operator"))
check("operator 改他人账号 -> BG", res.get("errCode") == "BG", "errCode=%s, MSG=%s" % (res.get("errCode"), (res.get("MSG") or {}).get("content")))
check("operator 改他人账号未触发 update", CAPTURE["update_called"] is None, "update_called=%r" % CAPTURE["update_called"])

reset()
res = crudApi.funcAccountDel("accountdel", {"recID": "12"}, sess("lisiyuan", "operator"))
check("operator 删他人账号 -> BG", res.get("errCode") == "BG", "errCode=%s" % res.get("errCode"))
check("operator 删他人账号未触发 delete", CAPTURE["delete_called"] is None, "delete_called=%r" % CAPTURE["delete_called"])

reset()
res = crudApi.funcAccountModify("accountmodify", {"recID": "11", "accountName": "改名", "ownerID": "chenlh"},
                                sess("lisiyuan", "operator"))
check("operator 改本人账号 -> B0", res.get("errCode") == "B0", "errCode=%s" % res.get("errCode"))
check("operator 改本人账号忽略 ownerID 入参(不允许改归属)",
      "ownerID" not in (CAPTURE["update_called"] or {}).get("saveSet", {}),
      "update saveSet keys=%s" % sorted((CAPTURE["update_called"] or {}).get("saveSet", {}).keys()))

reset()
res = crudApi.funcAccountDel("accountdel", {"recID": "11"}, sess("lisiyuan", "operator"))
check("operator 删本人账号 -> B0 且触发 delete", res.get("errCode") == "B0" and CAPTURE["delete_called"] == "11",
      "errCode=%s, delete_called=%r" % (res.get("errCode"), CAPTURE["delete_called"]))

reset()
res = crudApi.funcAccountDel("accountdel", {"recID": "999"}, sess("lisiyuan", "operator"))
check("查不到记录仍返回 CB(不因归属改造而变)", res.get("errCode") == "CB", "errCode=%s" % res.get("errCode"))

print()
print("=" * 78)
print("验收 4) 管理员例外 —— administrator / manager 为超管视角")
print("=" * 78)
reset()
res = crudApi.funcAccountQry("accountqry", {"mode": "full"}, sess("chenlh", "administrator"))
owners = sorted(set(str(r.get("ownerID", "")) for r in BUFFER.get("rows", [])))
check("administrator 不传 ownerID -> 全量", owners == ["chenlh", "lisiyuan", "zhoumin"], "返回归属=%s" % owners)
check("administrator 查询条件 ownerID 为空(不放该条件)", CAPTURE["query_kwargs"][-1]["ownerID"] == "",
      "实际 query ownerID=%r" % CAPTURE["query_kwargs"][-1]["ownerID"])

reset()
res = crudApi.funcAccountModify("accountmodify", {"recID": "11", "accountName": "管理员改名", "ownerID": "zhoumin"},
                                sess("chenlh", "administrator"))
check("administrator 可改任意账号", res.get("errCode") == "B0" and CAPTURE["update_called"] is not None,
      "errCode=%s" % res.get("errCode"))
check("administrator 可指定归属", (CAPTURE["update_called"] or {}).get("saveSet", {}).get("ownerID") == "zhoumin",
      "update saveSet.ownerID=%r" % (CAPTURE["update_called"] or {}).get("saveSet", {}).get("ownerID"))

reset()
res = crudApi.funcAccountDel("accountdel", {"recID": "12"}, sess("zhoumin", "manager"))
check("manager 可删任意账号", res.get("errCode") == "B0" and CAPTURE["delete_called"] == "12",
      "errCode=%s, delete_called=%r" % (res.get("errCode"), CAPTURE["delete_called"]))

reset()
res = crudApi.funcAccountAdd("accountadd", {"accountCode": "A-88", "platform": "wechat_mp", "accountName": "n",
                                            "subjectType": "personal", "capability": "draft_box",
                                            "ownerID": "chenlh"}, sess("chenlh", "administrator"))
check("administrator 新增可指定归属", (CAPTURE["insert_saveSet"] or {}).get("ownerID") == "chenlh",
      "saveSet.ownerID=%r" % (CAPTURE["insert_saveSet"] or {}).get("ownerID"))

print()
print("=" * 78)
print("验收 5) 巡检归属收窄(方案甲) + 定时任务缺省全量")
print("=" * 78)
#--- fetchAccountList: 缺省无 ownerID; 显式传入才收窄
#  ★ 真实模块以独立模块名加载(不污染 sys.modules['schedule.credentialCheck'] 的桩),
#    仅用于验证 fetchAccountList / main() 的源码口径, 不触发 runOnce 的 Redis 锁与心跳。
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "ch_credentialcheck_real", os.path.join(SRC_DIR, "schedule", "credentialCheck.py"))
credentialCheck = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(credentialCheck)

reset()
credentialCheck.fetchAccountList({})
last = CAPTURE["query_kwargs"][-1]
check("fetchAccountList({}) 不含 ownerID(全量)", "ownerID" in last and last["ownerID"] == "",
      "query ownerID=%r" % last["ownerID"])

reset()
credentialCheck.fetchAccountList({"ownerID": "lisiyuan"})
last = CAPTURE["query_kwargs"][-1]
check("fetchAccountList({ownerID}) 收窄生效", last["ownerID"] == "lisiyuan", "query ownerID=%r" % last["ownerID"])

#--- accountApi.funcAccountHealth: 注入 scopeOwner
reset()
CAPTURE.pop("runOnce_dataSet", None)
res = accountApi.funcAccountHealth("accounthealth", {"action": "check"}, sess("lisiyuan", "operator"))
check("非管理员巡传入参 ownerID=loginID", CAPTURE.get("runOnce_dataSet", {}).get("ownerID") == "lisiyuan",
      "runOnce dataSet=%s" % CAPTURE.get("runOnce_dataSet"))
check("非管理员汇总也收窄(healthSummary 非全站)", CAPTURE["query_kwargs"][-1]["ownerID"] == "lisiyuan",
      "汇总 query ownerID=%r" % CAPTURE["query_kwargs"][-1]["ownerID"])
_summary = (res.get("data") or {}).get("healthSummary") or res.get("healthSummary")
check("非管理员巡检返回 healthSummary 且只计本人账号", _summary is not None and _summary.get("total") == 1,
      "healthSummary=%s(库内共 3 条, 本人 1 条)" % _summary)

reset()
CAPTURE.pop("runOnce_dataSet", None)
accountApi.funcAccountHealth("accounthealth", {"action": "check"}, sess("chenlh", "administrator"))
check("管理员巡传入参 ownerID 为空(全量)", CAPTURE.get("runOnce_dataSet", {}).get("ownerID") == "",
      "runOnce dataSet=%s" % CAPTURE.get("runOnce_dataSet"))
check("管理员汇总不收窄", CAPTURE["query_kwargs"][-1]["ownerID"] == "",
      "汇总 query ownerID=%r" % CAPTURE["query_kwargs"][-1]["ownerID"])

#--- credentialCheck.main() 构造的 dataSet 不含 ownerID(定时任务语义不变)
import inspect
mainSrc = inspect.getsource(credentialCheck.main)
check("定时任务 main() 不构造 ownerID(缺省全量)", "ownerID" not in mainSrc, "main() 源码中无 ownerID")

print()
print("=" * 78)
print("验收 7) 授权面(ROLE_CMD_LIST) —— operator/customer 已授权, visitor 未授权")
print("=" * 78)
from config import basicSettings as settings
for role, cmds in (("operator", ["accountadd", "accountmodify", "accountdel", "accountqry", "accounthealth"]),
                   ("customer", ["accountadd", "accountmodify", "accountdel", "accountqry", "accounthealth"])):
    allow = settings.ROLE_CMD_LIST.get(role, [])
    missing = [c for c in cmds if c not in allow]
    check("%s 已获账号域授权" % role, not missing, "缺失=%s" % missing)

visitorAllow = settings.ROLE_CMD_LIST.get("visitor", [])
leaked = [c for c in visitorAllow if str(c).startswith("account")]
check("visitor 未获任何 account* 授权", not leaked, "越权项=%s" % leaked)

#--- V3 完整性校验: 不新增 CMD, 端点总数仍 72
allCmds = set()
for cmdList in settings.ROLE_CMD_LIST.values():
    allCmds.update(cmdList)
allCmds.update(settings.NO_SESSIONID_CMD_LIST)
from subfunc import CMD_MAP  # noqa: F401  (导入即触发 V1/V2/V3 校验)
registered = set(CMD_MAP.keys())
unknown = sorted(c for c in allCmds if c not in registered)
check("ROLE_CMD_LIST ∪ NO_SESSIONID 全部已注册(V3 通过)", not unknown, "未注册=%s" % unknown)
check("端点总数仍 72", len(registered) == 72, "实际=%d" % len(registered))

print()
print("=" * 78)
print("汇总: pass=%d, fail=%d" % (PASS_COUNT[0], len(FAIL_LIST)))
if FAIL_LIST:
    print("失败项: %s" % FAIL_LIST)
print("=" * 78)
sys.exit(1 if FAIL_LIST else 0)
