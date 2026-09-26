# chAPIPost 服务拆分方案（subfunc 目录）

| 项 | 内容 |
|---|---|
| 支线编号 | **S2** |
| 目标 | 在 `main/` 下新建 `subfunc/` 目录，把账号服务相关接口与新增业务接口拆为独立文件，经聚合层统一暴露 |
| 涉及文件 | `code/src/main/chAPIPost.py`（新建/重构）、`code/src/main/subfunc/*`、`code/src/common/funcCommon.py`（错误消息部分评估） |
| 基线参考 | `ylwzProject/museum/code/src/main/museumAPIPost.py`（≈11,810 行）、`main/museumAPI.py`、`common/museumCommon.py`、`common/funcCommon.py` |
| 类型 | **并行支线**（**必须先于主计划 C1 开工**） |
| 优先级 | **P1（关键前置）** |
| 预估工时 | **11.0 人天** |
| 版本 | v1.0 · 2026-09-17 |

---

## 1. 背景与现状度量

### 1.1 「主代码过于庞大」的具体程度（实测）

| 排名 | 文件 | 大小 | 行数 |
|---|---|---|---|
| 1 | `main/museumAPIPost.py` | **469.09 KB** | **≈11,810 行** |
| 2 | `common/mysqlCommon.py` | 274.19 KB | ≈8,600 行 |
| 3 | `database/mysqlCodeGenerator.py` | 88.85 KB | — |
| 4 | `common/funcCommon.py` | 62.62 KB | **1,823 行** |
| 5 | `common/museumCommon.py` | 40.98 KB | **1,220 行** |

- `museumAPIPost.py` 是第 2 名的 **1.7 倍**，约等于整个 `common/` 目录（15 个文件）之和的 **1.4 倍**。
- 文件内共 **123 个 `def`**，其中 **91 个 CMD 处理函数**通过 `urlPathMap` 注册。
- 单文件承载 **全部 91 个对外 CMD**，是名副其实的「巨型入口」。

### 1.2 文件内部结构（含天然分段）

| 行号 | 内容 |
|---|---|
| 1–55 | 文件头 + import 段（**注意第 4 行残留旧文件名 `mindgramAPIPost.py`**） |
| 60–103 | 全局变量：`_processorPID`、`HOME_DIR`、`_DEBUG`、`useQueryBufferFlag`、`FILE_SYSTEM_MODE`、`ACCOUNT_SERVICE_URL`(L95)、`FILE_SERVER_URL`、`gSourceServerAddr`(L103) |
| 107–628 | `# command part begin` … `end`（缓冲段 L222、上传文件段 L225–388、ntn common 段 L602–626） |
| 631–2336 | `#user related begin` … `end`（**账号/用户/会话 CMD 处理函数，拆分重点**） |
| 2394–2497 | `#sw upgrade related begin` … `end` |
| 2500–2602 | `funcGenUserSessionID`（无标注段） |
| 2605–2997 | `#application functions begin` … `end` |
| 2997–11362 | `#museum HTTP interface functions begin` … `end`（**17 张表 × 4 个 CRUD = 68 个函数**，内部另有 17 组「每表一注释块」） |
| 11367–11542 | `#===== main entrace ======` → **`urlPathMap`（dict，91 条）** |
| 11545–11549 | `CMDMapKeyList`（由 `urlPathMap` 的 key 派生） |
| 11552–11622 | `dataFormatConvertor` / `dataTrustDomainCheck` / `uploadContentCheck` 等入参处理 |
| 11625–11676 | `calUserCMDMapKeyList`（**权限 / 会话校验中枢**） |
| 11680–11792 | `def post(...)`（程序入口） |
| 11795–11810 | `if __name__ == "__main__":` 本地调试入口 |

**关键事实：文件中不存在 `#region` 或等价标记，但存在成对的 `# xxx begin/end` 注释 —— 这些即为可直接沿用的模块边界。**

### 1.3 注册与调用机制（实测）

```python
# L11368 起
urlPathMap = {
    "login":  funcUserLogin,     # L11389
    "logout": funcUserLogout,    # L11391
    ...
}
CMDMapKeyList = []                                   # L11545
for k, v in urlPathMap.items():                      # L11548-11549
    CMDMapKeyList.append(k)

# L11761 调用（统一签名）
rtnData = urlPathMap[CMD](CMD, dataSet, sessionIDSet)
```

- 结构：`dict`，`"CMD小写字符串" → 函数对象`，共 **91 条**。
- 所有处理函数**统一签名** `func(CMD, dataSet, sessionIDSet)`。
- `main/museumAPI.py`（152 行，Flask 门面）第 27 行 `import museumAPIPost as userApp`，在 `/museumapi/<urlPath>` 路由中调用 `userApp.post(urlPath, dataSet, IP, environSet, appType)`（L96/108/119）。
- `main/museumRun.py` 为独立批处理入口，**不 import** `museumAPI` / `museumAPIPost`。

### 1.4 91 个 CMD 的构成

| 类别 | 数量 | 行号区间 | 说明 |
|---|---|---|---|
| A. 用户 / 账号 / 会话 | **23** | L11371–11433 | `chkuserexist / registration / useradd / userdel / usermodify / usersearch / getuserinfo / login / logout / smsrequest / smsverify / resetpasswd / userinfoqry / passwdvalidcheck / usersavedata / usergetdata / generalnext / serverversionqry / swupload / hwinforeport / gethwinfo / getomcinfo / genusersessionid` |
| B. 17 张业务表 CRUD | **68** | L11440–11539 | 每表 `add/del/modify/qry` 4 个 |
| | **91** | | |

### 1.5 账号 / 权限相关逻辑清单（拆分重点）

> 说明：用户描述的 `accoutService` 在代码中**不存在同名变量**；账号服务实为通过常量 `ACCOUNT_SERVICE_URL`（L95）以 HTTP 方式访问的外部服务，配置项为 `settings.ACCOUNT_SERVICE_URL`、`settings.accountServiceDefaultLoginID`、`settings.accountServiceDefaultRoleName`、`settings.ROLE_ACCOUNT_ROLE`、`settings.ROLE_CMD_LIST`、`settings.NO_SESSIONID_CMD_LIST`。

**账号服务封装函数**（`# command part` 段）

| 函数 | 行号 | 职责 | 下游 CMD |
|---|---|---|---|
| `getUserInfo(loginID, sessionID)` | 460 | 取用户基本信息 | `A3A0` |
| `chkIsAuthenticatedUser(orgID)` | 493 | 是否认证用户 | — |
| `chkIsInService(inService, activeFlag)` | 510 | 是否在服务中 | — |
| `getUserInfoMysql(loginID)` | 526 | 本地库取用户信息 | — |
| `modifyUserRoleName(loginID, roleName, sessionID)` | 545 | 修改角色 | `AEA0` |
| `accChkUserExist(loginID)` | 575 | 账号服务侧存在性 | `AIA0` |
| `getEnabledDeviceList()` | 603 | 启用设备清单（Redis） | — |

**CMD 处理函数**（`#user related` 段）

| 函数 | 行号 | CMD |
|---|---|---|
| `funcChkUserExist` | 634 | `chkuserexist` |
| `funcUserRegistration` | 696 | `registration` |
| `funcUserLogin` | 772 | `login` |
| `funcUserAdd` | 869 | `useradd` |
| `funcUserDelete` | 976 | `userdel` |
| `funcUserModify` | 1055 | `usermodify` |
| `funcUserLogout` | 1175 | `logout` |
| `funcUserSearch` | 1240 | `usersearch`（旧 Redis 版） |
| `funcUserSearchMysql` | 1342 | `usersearch` / `userinfoqry` |
| `funcGetUserInfo` | 1614 | `getuserinfo`（旧版） |
| `funcGetUserInfoMysql` | 1672 | `getuserinfo` |
| `funcSMSRequest` | 1834 | `smsrequest` |
| `funcSMSVerify` | 1888 | `smsverify` |
| `funcResetPasswd` | 1946 | `resetpasswd` |
| `funcUserInfoQuery` | 2002 | `userinfoqry` |
| `funcPasswdValidCheck` | 2103 | `passwdvalidcheck` |
| `funcUserSaveData` | 2160 | `usersavedata` |
| `funcUserGetData` | 2219 | `usergetdata` |
| `funcGenUserSessionID` | 2500 | `genusersessionid` |

**权限 / 会话校验中枢**

| 函数 | 行号 | 职责 |
|---|---|---|
| `calUserCMDMapKeyList(dataSet, CMDList)` | 11625 | 向账号服务发 `GAA0` 取 `sessionIDSet`，与 `settings.ROLE_CMD_LIST` 求交集做权限判定（无权限返回 `B8`） |
| `post()` 内联段 | 11732–11745 | 无 sessionID 命令走 `settings.NO_SESSIONID_CMD_LIST`，否则调 `calUserCMDMapKeyList`；再做 `activeFlag` 停用判断（`BT`） |

**账号服务侧 CMD 码汇总**：`A0A0`（登录/注册）、`A2A0`（生成会话）、`A3A0`（取用户信息）、`A5A0`（登出）、`AIA0`（存在性）、`AEA0`（改角色）、`GAA0`（取会话 + 功能清单）。

### 1.6 重复度证据（抽公共层的直接依据）

**统一模式**（每个 CMD 处理函数都遵守）：

```text
固定头部变量声明（result/errCode/rtnCMD/rtnField/rtnData/msgData）
  → lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
  → 取 sessionIDSet 中的 openID / roleName / loginID
  → 业务逻辑
  → rtnSet = comFC.rtnMSG(errCode, rtnField, lang, msgKey)
  → result["CMD"/"msgKey"/"MSG"/"errCode"] 组装
  → except: _LOG.error(f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}") + traceback
```

- `funcUserRegistration`（L696–768）与 `funcUserLogin`（L772–855）**几乎逐行相同**：都转发 `A0A0`、都用 `settings.accountServiceDefaultRoleName` 修正 `visitor` 角色、都走 `comDB.putMsg2Queue(...)` 落库。
- `funcUserSearch`(L1240) 与 `funcUserSearchMysql`(L1342)、`funcGetUserInfo`(L1614) 与 `funcGetUserInfoMysql`(L1672) 存在**新旧双版本并存**，是历史包袱而非设计。

**可抽取的公共件**（事实层面已独立存在）：`rtnMSG` 返回封装、`sessionIDSet` 解析、账号服务 HTTP 转发、`lang`/`msgKey` 取值、`except` 兜底日志、`indexKey` 分页入参组装。

### 1.7 现状问题清单

| # | 问题 | 影响 |
|---|---|---|
| P1 | 单文件 11,810 行 / 91 个 CMD | 定位困难、冲突高发（多人并行必冲突）、review 成本极高 |
| P2 | 账号逻辑与业务 CRUD 混在一起 | 权限链路改动需在巨型文件中穿行，回归面无法界定 |
| P3 | 大量重复样板（头部声明 / rtnMSG / except） | 新增一个接口需复制 30+ 行，易漏项 |
| P4 | 新旧双版本函数并存 | 注册表指向哪一个不直观，易改错版本 |
| P5 | `common/museumCommon.py`（1,220 行）已抽出部分公共件，但 `museumAPIPost.py` **完全未 import 它**（17 处仅为注释引用） | 抽出的公共层形同虚设，重复代码继续增长 |
| P6 | 文件头残留旧名 `mindgramAPIPost.py` | 说明该文件已多次改名迁移，历史包袱重 |
| P7 | 无明确的模块边界声明 | 只能靠注释定位，无法用工具（导入图）约束 |

---

## 2. 拆分目标与原则

### 2.1 目标

1. **单文件不再承载全部端点**：`chAPIPost.py` 只保留「聚合 + 主流程」职责，目标 ≤ 400 行。
2. **按业务域切分**：账号域独立成文件，业务域各自独立，CRUD 生成件独立。
3. **公共件下沉**：入参处理、返回封装、会话解析、账号服务客户端统一到公共模块，消除样板。
4. **聚合零遗漏**：注册表由各模块声明后合并，**导入期自动检测 CMD 冲突与缺失**。
5. **行为等价**：拆分前后 91 个 CMD 的入参、出参、错误码**完全一致**。

### 2.2 拆分原则

| # | 原则 | 说明 |
|---|---|---|
| G1 | **一个模块 = 一个业务域** | 账号 / 主题 / 素材 / 渲染 / 投递 / 合规 / MCP / CRUD |
| G2 | **单向依赖** | `chAPIPost → subfunc → (context、common/*)`；**subfunc 内部禁止 import chAPIPost** |
| G3 | **模块只声明，不注册** | 每个模块暴露 `CMD_MAP: dict`，由聚合层合并；模块自身不修改全局 `urlPathMap` |
| G4 | **公共件先下沉，再搬业务** | 先抽 `apiCommon`，再迁移业务函数，避免搬完再重构两次 |
| G5 | **一次只搬一个域，搬完即回归** | 不做「大爆炸式」重排 |
| G6 | **命名即契约** | 文件名 `{domain}Api.py`，导出名 `CMD_MAP` / `ACCOUNT_CMDS` 等固定后缀，便于聚合器遍历 |
| G7 | **不引入框架** | 保持「dict 注册 + 统一签名」的既有范式，零学习成本 |
| G8 | **旧名清理显式化** | 删除新旧双版本函数时，必须在迁移清单中逐条登记（见 8.3） |

---

## 3. 目录结构设计

```text
code/src/main/
├── chAPI.py                    # Flask 门面（对齐 museumAPI.py）：路由 /chapi/<urlPath>，调 chAPIPost.post()
├── chAPIPost.py                # ★ 瘦入口（目标 ≤400 行）：聚合 urlPathMap + post() 主流程 + 权限校验
└── subfunc/                    # ★ 新增
    ├── __init__.py             # 聚合导出：MODULE_MAPS / CMD_MAP / getUrlPathMap() / __all__
    ├── context.py              # 公共依赖与全局单例（settings / comGD / comFC / comDB / comMysql / _LOG / _processorPID）
    ├── apiCommon.py            # 入参处理 + 统一返回 + 异常兜底 + 分页入参（消除样板）
    ├── accountApi.py           # 账号 / 用户 / 会话（23 个 CMD）★ 拆分重点
    ├── accountSvcClient.py     # 账号服务 HTTP 客户端（A0A0/A2A0/A3A0/A5A0/AIA0/AEA0/GAA0 封装）
    ├── crudApi.py              # 生成器产出的 48 个 CRUD 处理函数（装配件，非手写）
    ├── topicApi.py             # 新增：主题业务接口
    ├── assetApi.py             # 新增：素材业务接口
    ├── renderApi.py            # 新增：渲染与产物接口
    ├── publishApi.py           # 新增：投递与素材包接口
    ├── complianceApi.py        # 新增：合规校验接口
    └── mcpApi.py               # 新增：仅承载 /chapi 侧 mcpinvoke 薄入口（MCP 协议层已独立为 code/src/mcpapi/ 包，见 6.4）
```

### 3.1 各文件职责与目标规模

| 文件 | 职责 | 目标行数 | 来源 |
|---|---|---|---|
| `chAPIPost.py` | 聚合注册表、`post()` 主流程、权限与会话校验、域名/格式校验 | ≤ 400 | 现 L11367-11810 的主体 |
| `subfunc/context.py` | 公共依赖与全局单例，供所有子模块统一 import | ≤ 150 | 现 L14-103 |
| `subfunc/apiCommon.py` | `genRtnResult` / `genErrResult` / 入参解析 / 兜底日志 / 分页入参 | ≤ 300 | 现 L11552-11622 + 各函数样板 |
| `subfunc/accountSvcClient.py` | 账号服务 HTTP 转发（含角色映射 `settings.ROLE_ACCOUNT_ROLE`） | ≤ 350 | 现 L460-628 |
| `subfunc/accountApi.py` | 23 个账号/会话 CMD 处理函数 | ≤ 900 | 现 L631-2336 + L2500-2602 |
| `subfunc/crudApi.py` | 48 个 `func<Title>{Add/Del/Modify/Qry}` | 由生成器决定（装配） | 生成器产物合并 |
| `subfunc/{domain}Api.py` | 各业务域新增接口 | 每个 ≤ 400 | 新建 |
| `subfunc/__init__.py` | 聚合 + 冲突/缺失检测 | ≤ 150 | 新建 |

> **规模校验**：拆分后最大文件（`accountApi.py` ≤900 行）约为原文件的 **7.6%**；`chAPIPost.py` 约为 **3.4%**。

---

## 4. 模块划分原则与映射

### 4.1 划分原则

1. **按「对外契约」而非「内部实现」划分**：一个模块的边界 = 它独占的 CMD 集合。同一 CMD 只能属于一个模块（由 G3 + 聚合器强制）。
2. **账号域单独成模块**：因为它跨业务（所有 CMD 的权限判定都依赖它），且改动风险最高。
3. **生成件与手写件分离**：`crudApi.py` 是生成器产物的落点，**人不可手改**；手写逻辑一律进 `{domain}Api.py`，避免下次重跑生成器覆盖手写代码。
4. **新接口按域拆**：contentHub 新增的 6 个业务端点（`topicrender` / `artifactpack` / `publishpush` / `publishcheck` / `accounthealth` / `mcpinvoke`）各归其域，不堆在一个 `miscApi.py`。
5. **抽象层级一致**：模块内只放 CMD 处理函数与其私有辅助函数，不放跨域公共件（公共件必须下沉到 `apiCommon` / `context`）。

### 4.2 边界映射表（museum 段 → 新模块）

| museum 原位置 | 行号 | 新归属 |
|---|---|---|
| 文件头 + import + 全局变量 | 1–103 | `subfunc/context.py`（+ `chAPIPost.py` 少量） |
| `# command part` 缓冲段 | 107–222 | `subfunc/apiCommon.py` |
| `# command part` 上传文件段 | 225–388 | `subfunc/apiCommon.py`（或独立 `uploadApi.py`，视体量） |
| `# command part` ntn common 段 + 账号服务封装 | 460–628 | `subfunc/accountSvcClient.py` |
| `#user related` 全部 | 631–2336 | `subfunc/accountApi.py` |
| `#sw upgrade related` | 2394–2497 | `subfunc/accountApi.py`（设备/版本类，可拆 `sysApi.py`） |
| `funcGenUserSessionID` | 2500–2602 | `subfunc/accountApi.py` |
| `#application functions` | 2605–2997 | 按语义拆分（通用/工具类 → `apiCommon.py`；业务类 → 对应域） |
| `#museum HTTP interface functions`（17 表 × 4） | 2997–11362 | `subfunc/crudApi.py`（contentHub 为 12 表 × 4 = 48） |
| `urlPathMap` | 11367–11542 | **拆解为各模块的 `CMD_MAP`**，由 `subfunc/__init__.py` 合并 |
| `CMDMapKeyList` | 11545–11549 | `subfunc/__init__.py` 派生 |
| 入参处理三函数 | 11552–11622 | `subfunc/apiCommon.py` |
| `calUserCMDMapKeyList` | 11625–11676 | `subfunc/accountApi.py`（或 `chAPIPost.py`，见 4.3） |
| `post()` | 11680–11792 | **`chAPIPost.py`**（主流程，不拆） |

### 4.3 边界争议点的裁定

| 争议 | 裁定 | 理由 |
|---|---|---|
| `calUserCMDMapKeyList` 放 `accountApi` 还是 `chAPIPost`？ | **放 `subfunc/accountApi.py`**，由 `chAPIPost.post()` 调用 | 它是账号服务的业务逻辑；`post()` 只做编排 |
| `dataFormatConvertor` / `dataTrustDomainCheck` / `uploadContentCheck` | **放 `subfunc/apiCommon.py`** | 三者是入参预处理，与业务域无关 |
| 生成器产出的 REST 函数 | **放 `subfunc/crudApi.py`**，标记为「装配件，禁止手改」 | 与手写逻辑物理隔离，重跑生成器不冲突 |
| `funcUserSearch` / `funcGetUserInfo` 等**旧版本** | **迁移时废弃**（见 8.3），只保留 `*Mysql` 版本 | 消除双版本歧义；废弃需逐条登记并回归 |
| `post()` 是否可再拆 | **不拆** | 它是唯一的编排点，拆散会失去「一眼看全流程」的价值；控制在 ≤150 行 |

---

## 5. 接口聚合方式

### 5.1 约定

每个子模块必须暴露模块级 `CMD_MAP: dict`（`"cmd小写" → 函数对象`），**不得**自行修改全局注册表。

```python
# subfunc/accountApi.py
CMD_MAP = {
    "login":  funcUserLogin,
    "logout": funcUserLogout,
    # ...
}
CRUD_GENERATED = False   # 标记是否为生成件
```

### 5.2 聚合器（`subfunc/__init__.py`）

```python
from subfunc import context
from subfunc import apiCommon
from subfunc import accountSvcClient
from subfunc import accountApi
from subfunc import crudApi
from subfunc import topicApi, assetApi, renderApi, publishApi, complianceApi, mcpApi

# 注册顺序即声明顺序；顺序不影响路由（dict 精确匹配）
MODULE_MAPS = {
    "account":    accountApi.CMD_MAP,
    "crud":       crudApi.CMD_MAP,
    "topic":      topicApi.CMD_MAP,
    "asset":      assetApi.CMD_MAP,
    "render":     renderApi.CMD_MAP,
    "publish":    publishApi.CMD_MAP,
    "compliance": complianceApi.CMD_MAP,
    "mcp":        mcpApi.CMD_MAP,
}

def getUrlPathMap():
    """合并全部子模块的 CMD_MAP，导入期即检测冲突"""
    merged, owner = {}, {}
    for domain, m in MODULE_MAPS.items():
        for cmd, fn in m.items():
            if cmd in merged:
                raise RuntimeError(
                    f"[subfunc] CMD 冲突: '{cmd}' 同时定义于 '{owner[cmd]}' 与 '{domain}'")
            if not callable(fn):
                raise TypeError(f"[subfunc] CMD '{cmd}' 的处理函数不可调用: {type(fn)}")
            merged[cmd] = fn
            owner[cmd] = domain
    return merged

CMD_MAP    = getUrlPathMap()
CMD_LIST   = list(CMD_MAP.keys())
CMD_OWNER  = {c: d for d, m in MODULE_MAPS.items() for c in m}   # 诊断用：CMD → 所属模块

__all__ = ["context", "apiCommon", "accountSvcClient",
           "MODULE_MAPS", "CMD_MAP", "CMD_LIST", "CMD_OWNER", "getUrlPathMap"]
```

### 5.3 聚合方式的两种形态（决策点）

| 方式 | 写法 | 优点 | 缺点 | 建议 |
|---|---|---|---|---|
| **A. 显式聚合（推荐）** | `from subfunc import CMD_MAP` + `getUrlPathMap()` | 可做冲突/类型/缺失检测；导入图清晰 | 需维护 `MODULE_MAPS` 一行 | **采用** |
| B. 通配聚合 | `from subfunc import *`（依赖 `__all__`） | 写法最短 | 无法做导入期校验；符号来源不透明；易被后续 `import *` 污染 | 作为语法糖保留，**不用于注册表** |

`chAPIPost.py` 的接入：

```python
# main/chAPIPost.py
from subfunc import CMD_MAP as SUBFUNC_CMD_MAP, CMD_LIST as SUBFUNC_CMD_LIST, CMD_OWNER

urlPathMap  = dict(SUBFUNC_CMD_MAP)      # 聚合后即为完整注册表
CMDMapKeyList = list(SUBFUNC_CMD_LIST)   # 由聚合结果派生，不再逐个手写

def post(urlPath, dataSet, IP, environSet, appType):
    ...
    rtnData = urlPathMap[CMD](CMD, dataSet, sessionIDSet)
```

### 5.4 聚合期的三道校验

| # | 校验 | 目的 |
|---|---|---|
| V1 | CMD 冲突检测（同一 CMD 出现在两个模块） | 防止静默覆盖 |
| V2 | 处理函数可调用性检测 | 防止误写常量/字符串 |
| V3 | **与配置的完整比对**（`CMDMapKeyList` ⊇ `ROLE_CMD_LIST` 全集 ∪ `NO_SESSIONID_CMD_LIST`） | 防止「配置里声明了权限但端点不存在」或反之 |

> V3 是关键：`ROLE_CMD_LIST` / `NO_SESSIONID_CMD_LIST` 是权限配置的事实来源，注册表与配置不一致会导致「授权但 404」或「存在但无权限校验」这类隐蔽缺陷。

---

## 6. 依赖处理

### 6.1 依赖方向（强制单向）

```text
main/chAPI.py
      │ import
      ▼
main/chAPIPost.py ── import ──► main/subfunc/*
                                      │
                                      ├─ import ──► main/subfunc/context.py（共享单例）
                                      └─ import ──► common/*（funcCommon / mysqlCommon / redisCommon / …）
```

**禁止**：`subfunc/*` 反向 import `chAPIPost` 或 `chAPI`（否则循环）。

### 6.2 `context.py` 集中共享依赖

现状是每个函数在文件顶部共享的全局变量（L60–103）散落使用。拆分后统一收敛：

```python
# subfunc/context.py
from config import basicSettings as settings
from common import globalDefinition as comGD
from common import funcCommon  as comFC
from common import miscCommon  as misc
from common import redisCommon as comDB
from common import mysqlCommon as comMysql
from common import chCommon    as comCh

ACCOUNT_SERVICE_URL  = settings.ACCOUNT_SERVICE_URL
FILE_SERVER_URL      = settings.FILE_SERVER_URL
FILE_SYSTEM_MODE     = settings.FILE_SYSTEM_MODE

_processorPID = os.getpid()
_LOG          = misc.setLogNew("chAPI", "chAPI.log")
```

各子模块统一 `from subfunc import context as ctx`，避免每个文件重复 import 与重复初始化（尤其 `setLogNew` 重复调用会产生多个 handler）。

### 6.3 循环依赖规避

| 场景 | 处理 |
|---|---|
| `accountSvcClient` 需要 `apiCommon` 的返回封装 | `accountSvcClient` 只做 HTTP 转发并返回原始 dict；封装由调用方（`accountApi`）负责 → 二者无相互依赖 |
| `crudApi` 需要 `apiCommon` 的入参处理 | 单向 `crudApi → apiCommon`，OK |
| `accountApi` 需要 `accountSvcClient` + `apiCommon` | 单向，OK |
| `apiCommon` 需要业务域逻辑 | **不允许**；`apiCommon` 必须保持「零业务」 |
| 某域需调用另一域 | 通过 `context` 调用 `common/` 下已下沉的服务（如 `common/chCommon.py`），**不做 subfunc 之间的横向 import** |

> **`apiCommon` 零业务**是防止它演变成第二个巨型文件的关键约束。

### 6.4 与主计划既有模块的关系

| 主计划中的模块 | 与本方案的关系 |
|---|---|
| `common/chCommon.py`（★新增，对齐 `museumCommon`） | 承接**跨域业务公共件**（会话解析、缓冲、文件服务、`genRtnResult`/`genErrResult`）；`subfunc/apiCommon.py` 是**HTTP 层**公共件，两者分层不同，不得混淆 |
| `common/accountClient.py`（★新增） | 账号服务客户端；`subfunc/accountSvcClient.py` 若体量小，可直接复用 `common/accountClient.py`，避免双份实现（**建议先合并为一个**，见决策 12.2） |
| `code/src/mcpapi/`（★新增，MCP 服务独立包） | **MCP 协议层与工具实现不在 `subfunc/` 内**。`mcpapi/mcp_entry.py`（入口层）+ `mcpPost.py`（实现层）+ `common/chServerCommon.py`（REST 客户端）构成独立包，对标 `gitData/stock_rotation_strategy/src/mcpapi`。`subfunc/mcpApi.py` 因此**收窄为 `/chapi` 侧的 `mcpinvoke` 薄入口**，仅做 REST 转发，不承载协议解析与工具注册表（主计划 9.6 节） |
| `common/chServerCommon.py`（★新增） | MCP 层访问 `/chapi` 的唯一数据入口（对标 `ylwzStockCommon.py`）；`subfunc/` 内**不得**重复实现同类客户端 |
| `main/chAPIPost.py`（主计划目录树已列出） | 本方案的改造对象；**不新增目录**，只新增 `main/subfunc/` |
| `main/chAPI.py`（Flask 门面） | 保持不变，只调 `chAPIPost.post()` |

> **重要发现**：`common/museumCommon.py`（1,220 行）本意就是抽公共层，但 `museumAPIPost.py` **完全未 import 它**（17 处仅为注释）。→ **contentHub 必须避免重蹈覆辙**：若 `chCommon.py` 建了却不用，拆分即失败。本方案要求在 S2-2（公共层抽取）完成后**强制删除重复实现**，并加 CI 检查（见 9.3）。

---

## 7. `funcCommon.py` 错误消息部分的调整评估

### 7.1 现状事实

| 项 | 事实 |
|---|---|
| `funcCommon.py` 规模 | 62.62 KB / **1,823 行** |
| 错误消息表 | `CONST_ERROR_wordList`，**L57–486**（约 430 行） |
| 结构 | **三层嵌套 dict**：`msgKey → lang → {errCode: template}` |
| msgKey 数量 | **3 个**：`default`(L58-202) / `account`(L203-344) / `mindgram_msg`(L345-485) |
| 语言 | **2 种**：`EN` / `CN`，每语言每 msgKey 约 70–80 条 |
| 占位符 | `%s`，由 `rtnMSG` 用 `word % field` 填充 |
| 相关函数 | `rtnMSG`(L489)、`getErrMsg`(L514)、`transOtherMsg`(L539)、附表 `TRANS_OTHER_MSG`(L531-537) |
| **`rtnMSG` 引用方** | **25 个文件**（含 `main/museumAPIPost.py`、`main/ylwzRecvFiles.py`、`common/museumCommon.py`、`common/miniProgramCommon.py`、`common/mysqlHandle.py`、`common/deepseekCommon.py`、`database/mysqlCodeGenerator.py`、18 个 `database/auto_generated/*`） |
| `getErrMsg` / `transOtherMsg` / `CONST_ERROR_wordList` 引用方 | **各 1 个（仅自身定义处，无外部调用）** |
| `rtnMSG` 依赖 | **仅依赖本文件的 `CONST_ERROR_wordList`**，**不依赖** `globalDefinition` / `basicSettings` |
| 循环依赖风险 | **无**：`globalDefinition.py` 无任何 import（纯常量）；`basicSettings.py` 只 import `os/sys` + `local_settings`，**不 import `funcCommon`** → `funcCommon → globalDefinition/basicSettings` 为单向 |
| 耦合度 | 错误消息段（L57–548）与文件其余部分**耦合极弱**，不消费 `comGD` / `settings` |

### 7.2 发现的两个既有缺陷（仅记录，决策后处理）

| # | 缺陷 | 位置 | 影响 |
|---|---|---|---|
| E1 | `getErrMsg` 索引层级与 `rtnMSG` 不一致：`if errCode in wordList[lang]: word = wordList[errCode]` | `funcCommon.py` L519-520 | 该函数**无外部调用**，故当前无实际影响；若被启用会取不到词 |
| E2 | `common/museumCommon.py` 的 `DEFAULT_MSG_KEY = "applicationMsgKey"` 与实际使用的 `msgKey="account"` **不一致** | `museumCommon.py` L72 | 导致 `museumCommon` 的封装与主文件行为不一致，进一步解释了「建了却不用」 |

### 7.3 调整评估结论

| 问题 | 评估 |
|---|---|
| 错误消息表是否该留在 `funcCommon.py`？ | **不该**。理由：① 与文件其余部分零耦合；② 占 1/4 体积且形态单一（纯数据）；③ contentHub 需新增 `contenthub` msgKey，继续塞入会让 `funcCommon.py` 继续膨胀；④ `rtnMSG` 是高扇出（25 个引用方）的稳定契约，独立后反而更易演进 |
| 拆分是否安全？ | **安全且零改动**。只需在新模块定义 `CONST_ERROR_wordList` + `rtnMSG`，并在 `funcCommon.py` 顶部保留 `from common.errMsgCommon import rtnMSG, getErrMsg, transOtherMsg, CONST_ERROR_wordList  # noqa: F401`，**25 个调用方一行都不用改** |
| 是否有循环依赖风险？ | **无**（已实测：上游均为纯常量/配置，单向） |
| 是否必须现在做？ | **不是必须**。属「顺手做掉、收益长期」的项。若资源紧张可延后，但**contentHub 新建时必须二选一**：要么抽独立模块，要么明确禁止再往 `funcCommon.py` 加消息表 |

### 7.4 建议方案

```text
common/
├── errMsgCommon.py        # ★ 新增：CONST_ERROR_wordList + rtnMSG / getErrMsg / transOtherMsg + TRANS_OTHER_MSG
└── funcCommon.py          # 保留 re-export，25 个调用方零改动
```

**迁移 4 步**：

| # | 步骤 | 动作 |
|---|---|---|
| 1 | 新建 `common/errMsgCommon.py` | 原样搬移 L57–548（`CONST_ERROR_wordList` / `rtnMSG` / `getErrMsg` / `transOtherMsg` / `TRANS_OTHER_MSG`），**不改一行逻辑** |
| 2 | `funcCommon.py` 顶部加 re-export | `from common.errMsgCommon import *  # noqa: F401,F403`（并显式列出 4 个符号，兼容静态检查） |
| 3 | 新增 `contenthub` msgKey | 在 `errMsgCommon.py` 追加 `"contenthub": {"EN": {...}, "CN": {...}}`，承载 `ch_*` 业务错误码 |
| 4 | 缺陷修复（可选，独立提交） | E1 索引修正；E2 统一 `DEFAULT_MSG_KEY`（需与调用方对齐后一次性改） |

**错误码规划建议**（contentHub 新增）：

| 段 | 用途 | 示例 |
|---|---|---|
| `C0`–`C9` | 通用成功/失败 | `C0` 成功 |
| `CA`–`CZ` | 字段校验类 | `CA` 必填缺失、`CB` 超长、`CC` 数值越界 |
| `D0`–`D9` | 文件/素材类 | `D0` 文件类型不允许、`D1` 超出规格、`D2` 内容重复 |
| `E0`–`E9` | 渲染/产物类 | `E0` 模板缺失、`E1` 渲染失败、`E2` 截图超时 |
| `F0`–`F9` | 投递类 | `F0` 凭据失效、`F1` 幂等命中、`F2` 频率超限、`F3` 平台拒绝 |
| `G0`–`G9` | MCP/令牌类 | `G0` 令牌无效、`G1` scope 不足 |

---

## 8. 迁移步骤

### 8.1 前置说明

> **contentHub 是新项目，`main/chAPIPost.py` 尚不存在。** 因此本方案有两种适用形态：
>
> - **形态 A（推荐，contentHub 采用）**：**按拆分结构直接新建** —— 不复制 museum 的巨型文件，而是先建 `subfunc/` 骨架，再把 museum 的实现**分域搬运**过来。**这与「先堆再拆」相比可省约 40% 工时，且不产生任何返工。**
> - **形态 B（备用，若 museum 侧也要治旧文件）**：对既有 `museumAPIPost.py` 做**增量迁移**，第 8.3 节的步骤同样适用，只是多一步「保留旧文件并行运行」。

### 8.2 形态 A：contentHub 新建步骤

| # | 步骤 | 内容 | 验收 |
|---|---|---|---|
| S2-1 | 建骨架 | 建 `main/subfunc/` 与 11 个文件（含空 `CMD_MAP = {}`），`chAPIPost.py` 写聚合骨架 | `python -c "from subfunc import CMD_MAP; print(len(CMD_MAP))"` → 0，无报错 |
| S2-2 | 公共层下沉 | 实现 `context.py` + `apiCommon.py`（`genRtnResult` / `genErrResult` / 入参解析 / 兜底日志 / 分页入参） | 单元测试：给定输入生成与 museum 一致的返回结构 |
| S2-3 | 账号域搬运 | 实现 `accountSvcClient.py`（7 个封装函数）+ `accountApi.py`（23 个 CMD） | 23 个 CMD 全注册；登录/登出/取用户信息冒烟通过 |
| S2-4 | CRUD 装配 | 生成器产出 48 个 REST 函数合并进 `subfunc/crudApi.py`，登记 `CMD_MAP` | 48 个 CMD 全注册；`ROLE_CMD_LIST` 覆盖校验（V3）通过 |
| S2-5 | 业务域新建 | 按域建 `topicApi/assetApi/renderApi/publishApi/complianceApi/mcpApi`，登记 6 个业务端点 | 每域 `CMD_MAP` 非空且无冲突 |
| S2-6 | 错误消息 | 抽取 `common/errMsgCommon.py` + 新增 `contenthub` msgKey + `funcCommon` re-export | 25 个既有引用方零改动（A1 验收） |
| S2-7 | 主流程收口 | `chAPIPost.py` 实现 `post()`（会话/权限/停用/域名校验 → 分发 → 兜底） | 与博物馆侧行为逐项对齐 |
| S2-8 | 全量回归 | 91（或 contentHub 实际数）个 CMD 逐一冒烟 + 权限矩阵校验 | 见第 9 章验收清单 |

### 8.3 旧版本函数的废弃登记（形态 A/B 通用）

museum 中存在新旧双版本，**必须逐条显式登记**，禁止「顺手删」：

| 废弃函数 | 行号 | 保留版本 | 处置 |
|---|---|---|---|
| `funcUserSearch` | 1240 | `funcUserSearchMysql` (1342) | 迁移时废弃，注册表指向 `*Mysql` |
| `funcGetUserInfo` | 1614 | `funcGetUserInfoMysql` (1672) | 同上 |
| `getErrMsg` / `transOtherMsg` | `funcCommon.py` L514/L539 | 无替代（无外部调用） | 迁移时不带入 `contenthub`（或保留但标注 deprecated），由决策 12.4 裁定 |
| `F3A0` / `F5A0`（文件服务） | `ylwzRecvFiles.py` L1369/L1373 已注释 | — | 与新项目无关 |

**废弃流程**：登记 → 确认无调用方（全仓搜索）→ 在新结构中不迁移 → 回归验证对应 CMD 行为不变。

### 8.4 形态 B：既有巨型文件的增量迁移（备用）

| # | 步骤 | 说明 |
|---|---|---|
| 1 | 建 `subfunc/` 骨架，与旧文件**并存** | 旧文件不改动，风险为零 |
| 2 | 抽 `apiCommon`，旧函数**逐步改为调用**新公共件 | 一次改一类样板，改完即回归 |
| 3 | 搬一个域 → 在新模块登记 `CMD_MAP` → 旧 `urlPathMap` 条目**指向新函数** | 逐个域切换，可随时暂停 |
| 4 | **双注册等价校验**（关键） | `assert set(新聚合CMD) == set(旧urlPathMap.keys())`，且逐 CMD `旧 fn is 新 fn` 或行为等价 |
| 5 | 全部域搬完后，删除旧函数体与旧 `urlPathMap` | 单次提交，便于回滚 |
| 6 | 清理文件头残留旧名（`mindgramAPIPost.py`） | 文档卫生 |

---

## 9. 验证与验收

### 9.1 结构验收

| # | 检查项 | 期望 |
|---|---|---|
| A1 | `chAPIPost.py` 行数 | ≤ 400 |
| A2 | 最大 subfunc 文件行数 | ≤ 900（`accountApi.py`） |
| A3 | `subfunc/` 内是否存在横向 import | 无 |
| A4 | `subfunc/` 是否 import `chAPIPost` | 无（循环依赖检查） |
| A5 | `apiCommon` 是否含业务逻辑 | 无 |
| A6 | `CMD_OWNER` 是否覆盖全部 CMD | 100% |

### 9.2 功能等价验收

| # | 检查项 | 方式 | 期望 |
|---|---|---|---|
| B1 | CMD 全集一致 | 对比迁移前后注册表 key 集合 | 完全一致（除显式废弃项） |
| B2 | 每个 CMD 入参兼容 | 逐个发送与迁移前相同的报文 | 返回结构 / `errCode` 一致 |
| B3 | 权限矩阵 | 4 类角色逐一请求全部 CMD | 可用集合与 `ROLE_CMD_LIST` 完全一致 |
| B4 | 免登录端点 | `NO_SESSIONID_CMD_LIST` 不带 sessionID 请求 | 正常返回 |
| B5 | 停用账号 | `activeFlag` 为停用态请求 | 返回 `BT` |
| B6 | 异常兜底 | 构造内部异常 | 返回 `ERROR` 结构且日志含 `PID/CMD/errMsg` |
| B7 | 废弃函数确认 | 全仓搜索废弃函数名 | 无调用方 |
| B8 | 聚合期校验 | 人为制造 CMD 冲突 | 导入期抛 `RuntimeError`（不静默） |

### 9.3 CI 侧约束（防回退）

| # | 检查 | 目的 |
|---|---|---|
| C1 | `main/chAPIPost.py` 行数 > 500 则失败 | 防止重新膨胀 |
| C2 | `subfunc/` 单文件 > 1000 行则失败 | 防止新巨型文件 |
| C3 | `subfunc/` 中出现 `import chAPIPost` 则失败 | 防循环 |
| C4 | `funcCommon.py` 中出现 `CONST_ERROR_wordList` 定义（非 re-export）则失败 | 防错误消息回流 |
| C5 | `chCommon.py` 存在但 `chAPIPost.py` 未 import 则失败 | **防止重蹈 `museumCommon` 建而不用** |

### 9.4 验收清单（对应主计划）

| # | 检查项 | 期望 |
|---|---|---|
| 1 | 主计划 Phase 0 验收 10 项 | 全过 |
| 2 | S2-8 全量 CMD 冒烟 | 通过 |
| 3 | 权限矩阵与配置一致 | 通过 |
| 4 | 结构验收 A1–A6 | 通过 |
| 5 | CI 约束 C1–C5 | 全部生效 |

---

## 10. 风险与应对

| # | 风险 | 等级 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | 拆分后**行为漂移**（错误码 / 返回结构不一致） | 高 | 前端与 Agent 调用方全部受影响 | 逐域迁移 + B1/B2 等价验收；废弃项逐条登记 |
| R2 | CMD 注册遗漏 | 高 | 端点 404，且「配置有权限但无端点」难排查 | 聚合器 V1/V2/V3 三道校验，导入期即失败 |
| R3 | **公共层建而不用**（重蹈 `museumCommon` 覆辙） | 高 | 拆分名义完成、实际继续堆 | CI 约束 C5；`apiCommon` 零业务约束（G-6.3） |
| R4 | 循环依赖 | 中 | 导入失败或难以维护 | 单向依赖 + CI C3 |
| R5 | `funcCommon.rtnMSG` 迁移影响 25 个引用方 | 中 | 大面积 import 失败 | **re-export 方案**，调用方零改动 + A1 验收 |
| R6 | 生成件与手写件混放被覆盖 | 中 | 重跑生成器丢失手写代码 | `crudApi.py` 独立 + 文件头「禁止手改」标记 |
| R7 | 拆分粒度过细导致文件爆炸 | 中 | 维护成本反升 | 粒度以「独占 CMD 集合」为准；单域小于 3 个 CMD 不单独成文件 |
| R8 | 旧版本函数删除引发隐性依赖 | 中 | 个别调用失败 | B7 全仓搜索确认 + 逐条登记 |
| R9 | 错误码规划与 museum 既有码冲突 | 低 | 前端提示错乱 | 新码段（C/D/E/F/G）与旧码段不重叠；`contenthub` msgKey 独立 |
| R10 | `DEFAULT_MSG_KEY` 历史不一致被带入 | 低 | 消息 key 取错导致回退英文 | 决策 12.4 一次性裁定并单测锁定 |

---

## 11. 工作量与排期

| 阶段 | 任务 | 交付物 | 工时 |
|---|---|---|---|
| S2-1 | 目录骨架 + 聚合器 + 三道校验 | `subfunc/` 11 文件 + `getUrlPathMap()` | 1.0 |
| S2-2 | `context.py` + `apiCommon.py` 公共层下沉 | 零业务公共件 + 单测 | 2.0 |
| S2-3 | 账号域：`accountSvcClient.py` + `accountApi.py`（23 CMD + 7 封装） | 账号域模块 | 2.0 |
| S2-4 | `crudApi.py` 装配（48 CMD）+ 配置一致性校验（V3） | CRUD 模块 | 1.5 |
| S2-5 | 6 个业务域模块骨架与注册（`topic/asset/render/publish/compliance/mcp`） | 业务域模块 | 1.5 |
| S2-6 | `errMsgCommon.py` 抽取 + `contenthub` msgKey + re-export | 独立错误消息模块 | 1.0 |
| S2-7 | `chAPIPost.py` 主流程收口（`post()` + 权限/停用/域名校验） | 瘦入口 | 1.0 |
| S2-8 | 全量回归 + 权限矩阵 + 结构验收 + CI 约束 | 回归与验收报告 | 1.0 |
| | | **合计** | **11.0 人天** |

**排期建议**：**必须在主计划 C1（接入与权限）开工之前完成 S2-1~S2-3**，否则 C1 会直接在 `chAPIPost.py` 里堆代码，拆分成本翻倍。S2-4~S2-8 可与 C1/C2 穿插进行。

| 里程碑 | 内容 | 时点 |
|---|---|---|
| S2-M1 | 骨架 + 聚合器 + 公共层就绪（S2-1、S2-2） | Phase 0 期间 |
| S2-M2 | 账号域 + 主流程跑通（S2-3、S2-7） | **C1 开工前** |
| S2-M3 | CRUD 装配 + 全量回归 + CI 约束（S2-4~S2-8） | Phase 1 内 |

---

## 12. 与主计划的关系

| 维度 | 说明 |
|---|---|
| **依赖方向** | 主计划 **C1（接入与权限）依赖 S2**：`main/chAPIPost.py` 的结构与 `subfunc/` 骨架必须先定，C1 才有落点 |
| **被谁依赖** | C1 接入与权限、C2–C8 全部新增端点（6 个业务端点各归其域）、Phase 3 的 C7 MCP（`subfunc/mcpApi.py` **仅保留 `/chapi` 侧 `mcpinvoke` 薄入口**；MCP 协议与工具实现已独立为 `code/src/mcpapi/` 包，其只读层已提前交付，见主计划 9.6 节） |
| **阻塞性** | **对 C1 是强前置**；对 Phase 0 不阻塞（Phase 0 不涉及 HTTP 层） |
| **优先级** | **P1（关键前置）**，优先级高于 S1（多 Bucket）；两者可与 Phase 0 并行，但 S2 必须在 C1 前收口 S2-M2 |
| **与三条红线的关系** | 强化 **R1（生成器链路）**：`crudApi.py` 作为生成件落点，与手写逻辑物理隔离，保证重跑生成器不覆盖手写代码；强化 **R2（禁止硬编码分支）**：`apiCommon` 零业务约束避免公共层退化为分支堆积处 |
| **对主计划的影响** | 主计划 3.7 节目录结构需在 `main/` 下补 `subfunc/` 子树；5.3 节 P1-1 任务需拆为「S2 骨架（前置）+ C1 业务接入」两步；C1 工时从 3.0 人天调整为 **2.0 人天**（骨架由 S2 承担） |

### 12.1 待拍板事项

| # | 事项 | 选项 | 建议 |
|---|---|---|---|
| 12.1 | 聚合方式 | A. 显式 `getUrlPathMap()`；B. `from subfunc import *` | **A**（可做冲突/缺失校验） |
| 12.2 | `subfunc/accountSvcClient.py` 与 `common/accountClient.py` 是否合并 | 合并 / 各自独立 | **合并为一个 `common/accountClient.py`**，`subfunc` 侧仅做薄封装，避免双份实现 |
| 12.3 | `crudApi.py` 是否按表再拆（每表一文件） | 单文件 / 每表一文件 | **单文件**（12 表 × 4 = 48 个，体量可控；按表拆会产生 12 个小文件） |
| 12.4 | `errMsgCommon.py` 抽取时机 | 立即（S2-6）/ 延后 | **立即**（一次性成本 1.0 人天，避免后续继续往 `funcCommon.py` 堆） |
| 12.5 | `getErrMsg` / `transOtherMsg` 是否保留 | 保留 / 废弃 | **保留但标注 deprecated**（无外部调用，删除风险大于收益） |
| 12.6 | `DEFAULT_MSG_KEY` 统一值 | `account` / `contenthub` / 保留现状 | **`contenthub`**（contentHub 独立 msgKey，与 museum 解耦） |
| 12.7 | `museumCommon` 建而不用的教训是否落到 CI | 加检查 / 不加 | **加**（CI 约束 C5） |

---

> 编制日期：2026-09-17 ｜ 基线实测：`ylwzProject/museum/code/src`（只读核实，事实条目均带行号）
> 关联文档：`plan/contentHub开发计划.md`（主计划）、`plan/ylwz文件服务多Bucket.md`（另一支线）
