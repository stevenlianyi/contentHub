# redisHandle.py 命令集现代化升级方案

| 项 | 内容 |
|---|---|
| 支线编号 | **S3** |
| 目标文件 | `code/src/common/redisHandle.py`（唯一代码改动点） |
| 新增产物 | `doc/redisCommandCoverage.md`（命令覆盖对照文档） |
| 关联文件（只读，不改动） | `code/src/config/redisSettings.py`、`code/src/common/redisCommon.py` |
| 运行环境 | Python 3.13.11 + **redis-py 6.4.0**（实测），项目无 requirements.py/setup.py，不新增依赖 |
| Redis 基线 | **8.10（当前最新稳定版，Q3 2026）**，兼容回溯至 5.0 |
| 类型 | **独立支线**（不阻塞主干，仅向下扩展能力） |
| 优先级 | **P2** |
| 预估工时 | **3.0 人天** |
| 版本 | v1.0 · 2026-09-18 |
| 状态 | **方案冻结，待执行**（IDE 客户端多次崩溃，先落盘文档） |

> 说明：用户原始需求中提到的 `redisHandler.py` 为笔误，实际目标文件为 **`code/src/common/redisHandle.py`**，已确认在现有文件上补充，不新建文件。

---

## 1. 背景与现状（实测事实）

### 1.1 现状结论一句话

> 现有 `redisHandle.py` 是 **Redis 5.0 时代 + redis-py 3.x 风格**的封装：`getRedisDB()` 连接工厂 + `RedisHandle` 读写分离 + `PipeHandle` 管道继承，共约 **70 个方法**，仅覆盖 Key/String/List/Set/ZSet/Hash 基础命令与少量发布订阅命令；**且存在 3 处会在 redis-py 6.4.0 下直接报错的真实 Bug**（详见 1.4）。

### 1.2 文件结构与事实清单

| # | 事实 | 位置 |
|---|---|---|
| F1 | 文件头 `#! /usr/bin/env python`（旧式 shebang）、`_VERSION="20230726"`、`import redis` 未加版本约束 | `redisHandle.py` L1–L7 |
| F2 | `getRedisDB(host, port, db, username="", passwd="")`：用 `redis.ConnectionPool` + `redis.Redis(connection_pool=...)`，按「无密码 / 有密码无用户名 / 有密码有用户名」三分支构造 | L9–L17 |
| F3 | `class RedisHandle.__init__(self, dbW, dbR)`：**读写分离**，`dbW` 主库写、`dbR` 从库读 | L20–L23 |
| F4 | Key 段方法：`save / exists / delete / type / keys / scan / randomkey / rename / renamenx / dbsize / expire / ttl / select / move / flushdb / flushall` | L25–L80 |
| F5 | **`flushdb(self, key)` 与 `flushall(self, key)` 是空实现**（`return None`），且签名多了一个无用的 `key` 参数 | L75–L80 |
| F6 | String 段：`set / setnx / get / getset / mget / mset / msetnx / incr / decr / incrby / decrby / append / substr` | L82–L121 |
| F7 | List 段：`lpush / rpush / llen / lrange / ltrim / lset / lrem / lpop / rpop / blpop / brpop / rpoplpush`（`lpush/rpush` 仅接受**单个** value） | L123–L164 |
| F8 | Set 段：`sadd / srem / spop / srandmember / smove / scard / sismember / sinter / sinterstore / sunion / sunionstore / sdiff / sdiffstore / smembers` | L166–L213 |
| F9 | ZSet 段：`zadd / zrem / zincrby / zrank / zrevrank / zrange / zrevrange / zrangebyscore / zcount / zcard / zscore / zremrangebyrank / zremrangebyscore`；`zadd` 仅支持单 member（`{member: score}`） | L215–L257 |
| F10 | Hash 段：`hset / hget / hmget / hmset / hincrby / hexists / hdel / hlen / hkeys / hvals / hgetall` | L259–L295 |
| F11 | 发布订阅段：`psubscribe / pubsub / publish / punsubscribe`；`subscribe` 与 `unsubscribe` **被注释掉** | L297–L321 |
| F12 | `class PipeHandle(RedisHandle)`：`__init__(self, redisHandle)` 用 `redisHandle.dbW.pipeline()`；仅 `execute()` 一方法 | L324–L331 |
| F13 | `__main__` 自测块连接 `127.0.0.1:16379 db=15`，仅 `print` 对象，**不做功能验证** | L333–L341 |

### 1.3 历史遗留问题清单

| # | 问题 | 性质 | 影响 |
|---|---|---|---|
| P1 | `hmset()` 直接调用 `dbW.hmset(...)`，而 redis-py 自 **4.0.0** 起已将 `hmset` 标记 `@deprecated_function` | 废弃 API | 触发 DeprecationWarning，未来版本可能移除 |
| P2 | `setnx()` 直接调用 `dbW.setnx(...)`，redis-py 推荐 `SET ... NX` | 旧写法 | 与 `set` 的扩展选项割裂 |
| P3 | `substr()` 直接调用 `dbR.substr(...)`，`SUBSTR` 已被 `GETRANGE` 取代 | 废弃命令 | 语义等价，但不再是推荐写法 |
| P4 | `getset()` 直接调用 `dbW.getset(...)`，`GETSET` 自 **Redis 6.2** 起被 `SET ... GET` 取代 | 废弃命令 | **不能改内部实现**（`SET ... GET` 需服务端 ≥ 6.2，会破坏 5.0 兼容），只能注释标注 |
| P5 | `flushdb/flushall` 空实现 + 错误签名（见 F5） | 功能缺失 | 调用无效，且传参错误 |
| P6 | `subscribe/unsubscribe` 被注释（见 F11） | 功能缺失 | 无法订阅普通频道 |
| P7 | 命令覆盖率低：缺 Streams / Bitmap / HyperLogLog / Geo / 事务 / 脚本 / 函数 等整个类别 | 功能缺失 | 业务只能用 `dbMainW/dbMainR` 绕过封装直调原生方法 |

### 1.4 redis-py 6.4.0 实测发现的**真实 Bug**（必须修复）

| # | 现状代码 | 实测结果 | 结论 |
|---|---|---|---|
| **B1** | `def psubscribe(self, *pattern): return self.dbW.psubscribe(*pattern)` | `redis.Redis` 类**没有** `psubscribe` 方法（361 个公开方法中不存在），仅 `redis.client.PubSub` 有 | **`AttributeError`**，必须改为 `self.dbW.pubsub().psubscribe(...)` |
| **B2** | `def punsubscribe(self, *pattern): return self.dbW.punsubscribe(*pattern)` | `redis.Redis` 类**没有** `punsubscribe` 方法 | **`AttributeError`**，同上 |
| **B3** | `def pubsub(self, *argument): return self.dbW.pubsub(*argument)` | redis-py 签名为 `pubsub(**kwargs)`，**不接受位置参数** | **`TypeError`**，须改为 `pubsub(self, **kwargs)` |

> 补充：`redis.client.PubSub` 的可用方法实测为 —— `subscribe / unsubscribe / psubscribe / punsubscribe / ssubscribe / sunsubscribe / get_message / get_sharded_message / listen / ping / parse_response / close / subscribed / reset / execute_command`。
>
> 因此**「订阅连接是独占的」**：`subscribe/psubscribe/ssubscribe` 返回的 `PubSub` 对象不能复用执行普通命令，也不能放进 pipeline。

---

## 2. 目标与范围

### 2.1 目标

1. 修复 1.3 的历史遗留问题与 1.4 的真实 Bug，**保留所有旧方法名作为兼容别名**。
2. 以 Redis 8.10 为基线，按类别补齐缺失命令，覆盖：**数据结构操作、连接管理、事务、管道、发布订阅、脚本执行**。
3. 每个新增命令在注释中标注 **引入版本** 与 **服务端最低版本要求**。
4. 保持现有接口风格：小写方法名、单行命令注释、`dbW` 写 / `dbR` 读、返回 redis-py 原始结果。

### 2.2 明确不做

- ❌ 不改动 `redisCommon.py` / `redisSettings.py` / `globalDefinition.py`。
- ❌ 不重命名、不删除任何既有方法。
- ❌ 不引入运行时 `try/except` 容错（用户明确选择「**仅注释标注**」，命令不支持时由底层抛异常）。
- ❌ 不默认启用 `decode_responses=True`（会改变现有 bytes 处理逻辑）。
- ❌ 不新增第三方依赖。

---

## 3. 兼容性契约（**不可破坏**）

> 依据：跨文件检索确认，全库仅 `redisSettings.py` 直接引用 `redisHandle`，`redisCommon.py` 间接使用。

| # | 契约 | 依据 |
|---|---|---|
| C1 | `getRedisDB(host, port, db, username="", passwd="")`：前 3 个位置参数 + 2 个关键字参数必须保持；返回值须可直接当 redis-py 客户端使用 | `redisSettings.py` L114/116/120/122 |
| C2 | `RedisHandle(dbW=..., dbR=...)` 必须支持关键字传参 | `redisSettings.py` L124 |
| C3 | `PipeHandle(RedisHandle实例)` 必须支持**位置**传参，内部读取 `.dbW` 并 `.pipeline()` | `redisSettings.py` L125 |
| C4 | `RedisHandle.scan(cursor, match, count)` 的**第 2 个位置参数必须是 `match`**（被 `redisMainDB.scan(cursor, dbKey)` 以位置方式调用） | `redisCommon.py` L68/70/84/87 |
| C5 | `redisCommon.py` 顶层依赖的变量名：`dbMainW / dbMainR / redisMainDB / redisPipe` | `redisCommon.py` L34–L38 |
| C6 | `PipeHandle` 实例须支持 `set / expire / lpush / rpush / execute`（缓冲后统一 `execute()` 提交） | `redisCommon.py` L187–192/330/855 |
| C7 | 无任何测试文件覆盖 Redis 封装（`code/src/test/` 下两个测试均声明「不依赖 Redis」） | `test/test_storage_selffile.py`、`test/test_bucketSettings.py` |

### 3.1 无调用点的方法（可安全改造，但仍保留旧名）

`hmset / setnx / getset / substr / flushdb / flushall / psubscribe / pubsub / punsubscribe / publish / blpop / brpop / zadd / randomkey / select / move / subscribe / unsubscribe` —— 经全库检索，**均无 `RedisHandle` 层面的调用者**（真实调用走 `dbMainW/dbMainR` 原生对象或 `redisMainDB.scan/save`）。

---

## 4. 版本标注约定

文件头新增统一约定说明，注释内统一使用：

```python
_VERSION = "20260918"

# 版本标注约定:
#   [Rn.n+]  该命令引入(或推荐使用)的 Redis 版本, 需服务端 >= 对应版本
#   [alias]  保留旧方法名作为兼容别名
#   未标注版本的命令在 Redis 5.0 及更早版本即可用, 保持向后兼容
#
# 兼容策略: 仅做版本注释标注, 不内置 try/except 容错;
#           服务端版本不支持时, 由 redis-py 底层抛出异常.
```

| 标注 | 含义 |
|---|---|
| `[R6.0+]` | 需服务端 ≥ Redis 6.0 |
| `[R6.2+]` | 需服务端 ≥ Redis 6.2 |
| `[R7.0+]` / `[R7.4+]` | 需服务端 ≥ Redis 7.0 / 7.4 |
| `[R8.0+]` `[R8.2+]` `[R8.4+]` `[R8.6+]` `[R8.8+]` `[R8.10+]` | 需服务端 ≥ 对应 8.x 版本 |
| `[alias]` | 兼容别名，不推荐新代码使用 |

---

## 5. 命令覆盖对照

> 图例：**已有** = 现有代码已实现；**修复** = 已有但需改造；**新增** = 本次补充。
> redis-py 无便捷方法的命令，统一用 `self.dbW.execute_command("CMD", ...)` / `self.dbR.execute_command(...)` 承载（表中标 `execute_command`）。

### 5.1 连接管理（Connect）

| 命令 | 状态 | 版本 | 封装方法 / 备注 |
|---|---|---|---|
| PING | 新增 | — | `ping()` → `dbW.ping()` |
| ECHO | 新增 | — | `echo(value)` |
| AUTH | 新增 | — | `auth(password, username=None)`（ACL 用户名需 ≥ R6.0） |
| QUIT / CLOSE | 新增 | — | `quit()` / `close()` |
| SELECT | 已有 | — | 保持原签名 `select(dbType, dbindex)` |
| SWAPDB | 新增 | R4.0+ | `swapdb(first, second)` |
| INFO | 新增 | — | `info(section=None)` → `dbR` |
| DBSIZE | 已有 | — | — |
| CONFIG GET/SET/REWRITE/RESETSTAT | 新增 | — | `config_get` / `config_set` / `config_rewrite` / `config_resetstat` |
| CLIENT LIST/KILL/ID/INFO/SETNAME/GETNAME/NO-EVICT/PAUSE/UNPAUSE/UNBLOCK/TRACKING* | 新增 | 部分 R6.0+ | `client_list` / `client_kill` / `client_id` / `client_info` / `client_setname` / `client_getname` / `client_no_evict` / `client_pause` / `client_unpause` / `client_unblock` / `client_tracking_on` / `client_tracking_off` / `client_trackinginfo` |
| WAIT / WAITAOF | 新增 | WAITAOF 需 R7.2+ | `wait(num_replicas, timeout)` / `waitaof(num_local, num_replicas, timeout)` |
| RESET | 新增 | R6.2+ | `reset()` |
| HELLO | 新增 | R6.0+ | `hello()`（redis-py 6.4 无参） |
| MEMORY USAGE / STATS | 新增 | R4.0+ | `memory_usage(key, samples=None)` / `memory_stats()` |
| COMMAND INFO/COUNT/LIST/GETKEYS/DOCS | 新增 | 部分 R7.0+ | `command_info` / `command_count` / `command_list` / `command_getkeys` / `command_docs` |
| ROLE / REPLICAOF(SLAVEOF) / FAILOVER | 新增 | FAILOVER 需 R6.2+ | `role()` / `replicaof(host, port)` / `slaveof` / `failover()` |

### 5.2 Key

| 命令 | 状态 | 版本 | 备注 |
|---|---|---|---|
| EXISTS / DEL / TYPE / KEYS / SCAN / RANDOMKEY / RENAME / RENAMENX / DBSIZE / EXPIRE / TTL / MOVE | 已有 | — | 保持签名；`scan` 增补可选 `_type`（置于末尾，兼容 C4） |
| FLUSHDB / FLUSHALL | **修复** | — | 修正错误签名（去掉 `key`）并落地真实调用；**慎用** |
| UNLINK | 新增 | R4.0+ | 异步删除 |
| TOUCH | 新增 | R3.2.1+ | 更新访问时间 |
| EXPIREAT / PEXPIRE / PEXPIREAT | 新增 | — | — |
| EXPIRETIME / PEXPIRETIME | 新增 | R7.0+ | 返回绝对过期时间戳 |
| PTTL | 新增 | — | — |
| PERSIST | 新增 | — | — |
| DUMP / RESTORE | 新增 | — | `dump` → `dbR`；`restore` → `dbW` |
| OBJECT ENCODING/REFCOUNT/FREQ/IDLETIME | 新增 | FREQ 需 LFU | `object(infotype, key)` + 4 个便捷方法 |
| COPY | 新增 | R6.2+ | `copy(source, destination, destination_db=None, replace=False)` |
| SORT / SORT_RO | 新增 | SORT_RO 需 R7.0+ | `sort` → `dbW`（可带 store）；`sort_ro` → `dbR` |
| SCAN_ITER | 新增 | — | 游标增量迭代生成器 |

### 5.3 String

| 命令 | 状态 | 版本 | 备注 |
|---|---|---|---|
| SET | **增强** | — | 增补 `ex/px/nx/xx/keepttl/get/exat/pxat`，原 `set(key, value)` 调用不变 |
| GET / MGET / MSET / MSETNX / INCR / DECR / INCRBY / DECRBY / APPEND | 已有 | — | — |
| SETNX | **修复** | — | 改 `set(key, value, nx=True)`，**保持返回 1/0 语义** |
| GETSET | **仅注释** | Redis 6.2 起废弃 | 保持 `GETSET` 原命令（`SET ... GET` 需 ≥6.2，会破坏 5.0） |
| SUBSTR | **修复** | — | 内部改 `getrange(key, start, end)`，保留方法名 |
| SETEX / PSETEX | 新增 | — | — |
| SETRANGE / GETRANGE / STRLEN | 新增 | — | — |
| GETDEL | 新增 | R6.2+ | 取值并删除 |
| GETEX | 新增 | R6.2+ | 取值并设置/清除过期 |
| INCRBYFLOAT | 新增 | R2.6+ | — |
| LCS | 新增 | R7.0+ | 最长公共子串 |
| MSETEX | 新增 | **R8.4+** | `execute_command("MSETEX", ...)` |
| DELEX | 新增 | **R8.4+** | 条件删除；`execute_command("DELEX", ...)` |
| DIGEST | 新增 | **R8.4+** | 值摘要；`execute_command("DIGEST", ...)` |
| INCREX | 新增 | **R8.8+** | 自增并设过期；`execute_command("INCREX", ...)` |

### 5.4 List

| 命令 | 状态 | 版本 | 备注 |
|---|---|---|---|
| LPUSH / RPUSH | **增强** | — | 改为 `*values`（单值调用仍兼容） |
| LPUSHX / RPUSHX | 新增 | — | — |
| LLEN / LRANGE / LTRIM / LSET / LREM / RPOPLPUSH | 已有 | — | — |
| LPOP / RPOP | **增强** | — | 增补可选 `count`（R6.2+ 支持 count） |
| LINDEX | 新增 | — | — |
| LINSERT | 新增 | — | — |
| LPOS | 新增 | R6.0.6+ | — |
| LMOVE / BLMOVE | 新增 | R6.2+ | `lmove(src, dst, srcDir, destDir)` |
| BRPOPLPUSH | 新增 | — | 阻塞版 RPOPLPUSH |
| LMPOP / BLMPOP | 新增 | R7.0+ | 多 key 弹出（`direction` 为必填关键字） |
| LMOVEM / BLMOVEM | 新增 | **R8.10+** | 批量移动；redis-py 无便捷方法，`execute_command` |

### 5.5 Set

| 命令 | 状态 | 版本 | 备注 |
|---|---|---|---|
| SADD / SREM | **增强** | — | 改为 `*members`（单值调用仍兼容） |
| SPOP / SRANDMEMBER | **增强** | — | 增补可选 `count` |
| SMOVE / SCARD / SISMEMBER / SINTER / SINTERSTORE / SUNION / SUNIONSTORE / SDIFF / SDIFFSTORE / SMEMBERS | 已有 | — | — |
| SMISMEMBER | 新增 | R6.2+ | 批量判断成员 |
| SINTERCARD | 新增 | R7.0+ | `sintercard(keys, limit=0)` |
| SSCAN / SSCAN_ITER | 新增 | — | — |
| SUNIONCARD | 新增 | **R8.10+** | `execute_command("SUNIONCARD", ...)` |
| SDIFFCARD | 新增 | **R8.10+** | `execute_command("SDIFFCARD", ...)` |

### 5.6 Sorted Set

| 命令 | 状态 | 版本 | 备注 |
|---|---|---|---|
| ZADD | **增强** | — | 增补 `nx/xx/ch/incr/gt/lt`（GT/LT/INCR 需 R6.2+），原调用不变 |
| ZREM / ZINCRBY / ZRANK / ZREVRANK / ZRANGE / ZREVRANGE / ZRANGEBYSCORE / ZCOUNT / ZCARD / ZSCORE / ZREMRANGEBYRANK / ZREMRANGEBYSCORE | 已有 | — | `zrem` 改 `*members`，单值仍兼容 |
| ZREVRANGEBYSCORE | 新增 | — | — |
| ZRANGEBYLEX / ZREVRANGEBYLEX / ZLEXCOUNT / ZREMRANGEBYLEX | 新增 | — | — |
| ZMSCORE | 新增 | R6.2+ | 批量取 score |
| ZPOPMIN / ZPOPMAX | 新增 | R5.0+ | — |
| BZPOPMIN / BZPOPMAX | 新增 | R5.0+ | 阻塞版 |
| ZRANDMEMBER | 新增 | R6.2+ | — |
| ZUNION / ZUNIONSTORE / ZINTER / ZINTERSTORE / ZDIFF / ZDIFFSTORE | 新增 | R6.2+ | — |
| ZRANGESTORE | 新增 | R6.2+ | — |
| ZINTERCARD | 新增 | R7.0+ | `zintercard(keys, limit=0)` |
| ZMPOP / BZMPOP | 新增 | R7.0+ | 多 key 弹出（`min`/`max` 二选一） |
| ZSCAN / ZSCAN_ITER | 新增 | — | — |

### 5.7 Hash

| 命令 | 状态 | 版本 | 备注 |
|---|---|---|---|
| HSET | **增强** | — | 增补 `mapping` 多字段写法；原 `hset(key, field, value)` 不变 |
| HMSET | **修复** | Redis 4.0 起废弃 | 内部改 `hset(key, mapping=mapping)`，**保留 `hmset` 方法名**，返回 `True` 保持旧语义 |
| HGET / HMGET / HINCRBY / HEXISTS / HLEN / HKEYS / HVALS / HGETALL | 已有 | — | — |
| HDEL | **增强** | — | 改为 `*fields`（单字段仍兼容） |
| HSETNX / HSTRLEN / HINCRBYFLOAT | 新增 | — | — |
| HRANDFIELD | 新增 | R6.2+ | — |
| HSCAN / HSCAN_ITER | 新增 | — | — |
| HEXPIRE / HPEXPIRE / HEXPIREAT / HPEXPIREAT | 新增 | R7.4+ | 字段级过期 |
| HEXPIRETIME / HPEXPIRETIME / HTTL / HPTTL / HPERSIST | 新增 | R7.4+ | 字段级 TTL 查询 |
| HGETDEL / HGETEX / HSETEX | 新增 | **R8.0+** | 字段级取值删除/取值设过期/设置设过期 |

### 5.8 Streams（现完全缺失）

| 命令 | 状态 | 版本 | 备注 |
|---|---|---|---|
| XADD / XLEN / XRANGE / XREVRANGE | 新增 | R5.0+ | — |
| XDEL / XTRIM | 新增 | R5.0+ | — |
| XREAD / XREADGROUP | 新增 | R5.0+ | — |
| XACK / XPENDING / XPENDING_RANGE | 新增 | R5.0+ | — |
| XGROUP CREATE/DESTROY/SETID/DELCONSUMER/CREATECONSUMER | 新增 | R5.0+ / CREATECONSUMER R6.2+ | — |
| XCLAIM / XAUTOCLAIM | 新增 | XAUTOCLAIM R6.2+ | — |
| XINFO STREAM/GROUPS/CONSUMERS | 新增 | R5.0+ | — |
| XACKDEL / XDELEX | 新增 | **R8.2+** | redis-py 有便捷方法 |
| XCFGSET | 新增 | **R8.6+** | `execute_command` |
| XNACK | 新增 | **R8.8+** | `execute_command` |

### 5.9 Bitmap / HyperLogLog / Geo（现完全缺失）

| 命令 | 状态 | 版本 | 备注 |
|---|---|---|---|
| SETBIT / GETBIT / BITCOUNT / BITOP / BITPOS | 新增 | R2.6+ / BITPOS R2.8.7+ | — |
| BITFIELD / BITFIELD_RO | 新增 | R3.2+ / BITFIELD_RO R6.0+ | — |
| PFADD / PFCOUNT / PFMERGE | 新增 | R2.8.9+ | — |
| GEOADD / GEOPOS / GEODIST / GEOHASH | 新增 | R3.2+ | — |
| GEORADIUS / GEORADIUSBYMEMBER | 新增 | R3.2+（R7.0 起不推荐，改用 GEOSEARCH） | 归 `dbW`（可带 store） |
| GEOSEARCH / GEOSEARCHSTORE | 新增 | R6.2+ | — |

### 5.10 事务 / 管道

| 能力 | 状态 | 版本 | 备注 |
|---|---|---|---|
| WATCH / UNWATCH | 新增 | R2.2+ 起 | `watch(*keys)` / `unwatch()` |
| MULTI / EXEC / DISCARD | 新增 | — | 通过 `pipeline(transaction=True)` 实现；`multi()` 返回事务型管道对象 |
| TRANSACTION | 新增 | — | `transaction(func, *watches)` 回调式事务 |
| PIPELINE | 新增 | — | `pipeline(transaction=True, shard_hint=None)` 工厂方法 |
| `PipeHandle.__init__` | **增强** | — | 增补可选 `transaction=True`，默认值保持原行为 |
| `PipeHandle.reset` / `discard` | 新增 | — | 丢弃缓冲（等价 DISCARD） |

> **不支持管道的命令**（不得放入 pipeline，需在 `PipeHandle` 注释说明）：`subscribe / unsubscribe / psubscribe / punsubscribe / ssubscribe / sunsubscribe / psubscribe`、`scan_iter` 系（阻塞生成器）、`select / hello / reset / monitor / wait`。

### 5.11 发布订阅

| 命令 | 状态 | 版本 | 备注 |
|---|---|---|---|
| SUBSCRIBE / UNSUBSCRIBE | **恢复** | — | 原代码被注释；改为 `self.dbW.pubsub().subscribe(...)` |
| PSUBSCRIBE / PUNSUBSCRIBE | **修复（Bug B1/B2）** | — | 改为 `self.dbW.pubsub().psubscribe(...)` |
| PUBSUB | **修复（Bug B3）** | — | 改为 `pubsub(**kwargs)` |
| PUBLISH | 已有 | — | — |
| PUBSUB CHANNELS/NUMSUB/NUMPAT | 新增 | — | `pubsub_channels` / `pubsub_numsub` / `pubsub_numpat` |
| SPUBLISH | 新增 | R7.0+ | 分片发布 |
| SSUBSCRIBE / SUNSUBSCRIBE | 新增 | R7.0+ | 分片订阅，`pubsub().ssubscribe(...)` |
| PUBSUB SHARDCHANNELS / SHARDNUMSUB | 新增 | R7.0+ | — |
| GET_MESSAGE / GET_SHARDED_MESSAGE | 新增 | 分片需 R7.0+ | `get_message(pubsubObj, timeout=0)` 取消息 |
| `__main__` 订阅示例 | 新增 | — | 演示「独占连接 + 循环取消息」 |

### 5.12 脚本与函数

| 命令 | 状态 | 版本 | 备注 |
|---|---|---|---|
| EVAL / EVALSHA | 新增 | R2.6+ / R2.6+ | 归 `dbW` |
| EVAL_RO / EVALSHA_RO | 新增 | R7.0+ | 归 `dbR`（只读） |
| SCRIPT LOAD / EXISTS / FLUSH / KILL / DEBUG | 新增 | SCRIPT DEBUG R3.2+ | `script_exists` → `dbR`，其余 `dbW` |
| REGISTER_SCRIPT | 新增 | — | 返回可复用 `Script` 对象 |
| FCALL / FCALL_RO | 新增 | R7.0+ | 函数调用 |
| FUNCTION LOAD / DELETE / FLUSH / LIST / DUMP / RESTORE / KILL / STATS | 新增 | R7.0+ | `function_list`/`function_stats`/`function_dump` → `dbR`，其余 `dbW` |

### 5.13 服务器管理

| 命令 | 状态 | 版本 | 备注 |
|---|---|---|---|
| SAVE | 已有 | — | — |
| BGSAVE / BGREWRITEAOF / LASTSAVE | 新增 | — | — |
| SHUTDOWN | 新增 | — | **高危，慎用**；支持 `save/nosave/now/force/abort` |
| TIME | 新增 | — | — |
| DEBUG OBJECT | 新增 | — | — |
| SLOWLOG GET/LEN/RESET | 新增 | — | — |
| MIGRATE | 新增 | — | — |
| MONITOR | 新增 | — | 调试用 |
| LOLWUT | 新增 | — | — |

### 5.14 Redis 8.8 新增 Array 数据结构命令族（可选）

> **R8.8+ 全新数据结构**，共 18 条：`ARCOUNT / ARDEL / ARDELRANGE / ARGET / ARGETRANGE / ARGREP / ARINFO / ARINSERT / ARLASTITEMS / ARLEN / ARMGET / ARMSET / ARNEXT / AROP / ARRING / ARSCAN / ARSEEK / ARSET`。
>
> redis-py 6.4.0 **无任何封装**，全部以薄透传实现（`execute_command("ARXXX", key, *args)`）。因命令较新且参数复杂，建议单独成节并标注「实验性 / 需服务端 ≥ 8.8」。

---

## 6. 实施方案

### 6.1 连接工厂改造（保持签名向后兼容）

```python
def getRedisDB(host, port, db, username="", passwd="",
               decodeResponses=False, socketTimeout=None, socketConnectTimeout=None,
               healthCheckInterval=0, maxConnections=None, retryOnTimeout=False):
    """创建 Redis 连接(连接池)。
    新增参数均为可选, 默认值保持原行为, 对现有调用方零影响。
    """
    poolArgs = {"host": host, "port": port, "db": db}
    if username == "" and passwd != "":
        poolArgs["password"] = passwd
    elif username != "" or passwd != "":
        poolArgs["username"] = username
        poolArgs["password"] = passwd
    if decodeResponses:
        poolArgs["decode_responses"] = True
    if socketTimeout:
        poolArgs["socket_timeout"] = socketTimeout
    if socketConnectTimeout:
        poolArgs["socket_connect_timeout"] = socketConnectTimeout
    if healthCheckInterval:
        poolArgs["health_check_interval"] = healthCheckInterval
    if maxConnections:
        poolArgs["max_connections"] = maxConnections
    if retryOnTimeout:
        poolArgs["retry_on_timeout"] = True
    redisPool = redis.ConnectionPool(**poolArgs)
    return redis.Redis(connection_pool=redisPool)
```

> 已实测：`ConnectionPool(..., decode_responses=True, socket_timeout=2, health_check_interval=30, max_connections=8, retry_on_timeout=True)` 可正常构造。

### 6.2 兼容修复（安全内部改写 + 保留旧名）

```python
def setnx(self, key, value):
    # [alias] SETNX; redis-py 推荐 SET ... NX, 此处保持原有 1/0 返回语义
    return 1 if self.dbW.set(key, value, nx=True) else 0

def hmset(self, key, mapping):
    # [alias] HMSET 自 Redis 4.0 起废弃; 内部改 HSET 多字段写法(redis-py 推荐)
    # 注意: HSET 返回新增字段数, 为保持旧 HMSET 语义此处统一返回 True
    self.dbW.hset(key, mapping=mapping)
    return True

def substr(self, key, start, end=-1):
    # [alias] SUBSTR; 内部改 GETRANGE(等价, Redis 2.0+)
    return self.dbR.getrange(key, start, end)

def getset(self, key, value):
    # GETSET 自 Redis 6.2 起被 SET ... GET 取代; 此处保留原命令以兼容 5.0 服务端
    return self.dbW.getset(key, value)

def flushdb(self, asynchronous=False):
    # 修正: 原签名误带 key 参数且为空实现; FLUSHDB 高危, 慎用
    return self.dbW.flushdb(asynchronous=asynchronous)

def flushall(self, asynchronous=False):
    # 修正: 同上; FLUSHALL 高危, 更加慎用
    return self.dbW.flushall(asynchronous=asynchronous)
```

### 6.3 发布订阅修复（Bug B1/B2/B3）

```python
def subscribe(self, *channels):
    # SUBSCRIBE channel [...] ; 订阅连接独占, 不能复用执行普通命令
    return self.dbW.pubsub().subscribe(*channels)

def unsubscribe(self, *channels):
    return self.dbW.pubsub().unsubscribe(*channels)

def psubscribe(self, *patterns):
    # [修复 B1] redis.Redis 无 psubscribe 方法, 必须经 PubSub 对象
    return self.dbW.pubsub().psubscribe(*patterns)

def punsubscribe(self, *patterns):
    # [修复 B2]
    return self.dbW.pubsub().punsubscribe(*patterns)

def pubsub(self, **kwargs):
    # [修复 B3] redis-py 签名为 pubsub(**kwargs), 不接受位置参数
    return self.dbW.pubsub(**kwargs)

def ssubscribe(self, *channels):
    # [R7.0+] 分片订阅
    return self.dbW.pubsub().ssubscribe(*channels)

def sunsubscribe(self, *channels):
    # [R7.0+]
    return self.dbW.pubsub().sunsubscribe(*channels)

def get_message(self, pubsubObj, timeout=0):
    # 从订阅对象取一条消息; timeout=0 表示非阻塞
    if timeout:
        return pubsubObj.get_message(timeout=timeout)
    return pubsubObj.get_message()
```

### 6.4 管道与事务

```python
def pipeline(self, transaction=True, shard_hint=None):
    # 返回事务型(transaction=True, MULTI/EXEC)或普通命令缓冲管道
    return self.dbW.pipeline(transaction=transaction, shard_hint=shard_hint)

def watch(self, *keys):
    return self.dbW.watch(*keys)

def unwatch(self):
    return self.dbW.unwatch()

def transaction(self, func, *watches, **kwargs):
    # 回调式事务: 内部执行 MULTI/EXEC
    return self.dbW.transaction(func, *watches, **kwargs)

def multi(self):
    # MULTI/EXEC 语义: 返回事务型管道, execute() 触发 EXEC, reset() 等价 DISCARD
    return self.dbW.pipeline(transaction=True)


class PipeHandle(RedisHandle):
    def __init__(self, redisHandle, transaction=True):
        # transaction=True 时 EXEC 原子提交; False 时仅命令缓冲批量发送
        self.dbW = redisHandle.dbW.pipeline(transaction=transaction)
        self.dbR = self.dbW

    def execute(self):
        return self.dbW.execute()

    def reset(self):
        # 丢弃缓冲, 等价 DISCARD
        return self.dbW.reset()
```

### 6.5 版本标注示例

```python
def lmpop(self, keys, direction="LEFT", count=1):
    # [R7.0+] LMPOP numkeys key [key ...] LEFT|RIGHT [COUNT n]; 需服务端 >= 7.0
    return self.dbW.lmpop(len(keys), *keys, direction=direction.upper(), count=count)

def sunioncard(self, keys):
    # [R8.10+] SUNIONCARD; redis-py 6.4.0 无便捷方法, 走 execute_command
    # 需服务端 >= 8.10
    return self.dbR.execute_command("SUNIONCARD", len(keys), *keys)

def increx(self, key, *args):
    # [R8.8+] INCREX; redis-py 6.4.0 无便捷方法; 需服务端 >= 8.8
    return self.dbW.execute_command("INCREX", key, *args)
```

---

## 7. 分阶段任务清单

> 与执行计划 todo 一一对应，按依赖顺序推进。

| # | 任务 ID | 内容 | 依赖 |
|---|---|---|---|
| 1 | `analyze-callsites` | 梳理 `getRedisDB/RedisHandle/PipeHandle` 及 `hmset/setnx/getset/substr/flushdb` 全部调用点，输出兼容性约束清单（**已完成**，见第 3 节） | — |
| 2 | `compat-repair` | 修复 `hmset/setnx/substr/flushdb/flushall` 并保留旧名；修复 `subscribe/unsubscribe/psubscribe/punsubscribe/pubsub`（Bug B1–B3）；更新 `_VERSION`；增强 `getRedisDB` | 1 |
| 3 | `key-string-cmds` | 补 Key 与 String 缺失命令（`unlink/touch/persist/pttl/copy/sort`、`setex/setrange/getrange/getdel/getex/incrbyfloat` 等），含 8.4/8.8 新命令 | 2 |
| 4 | `collection-cmds` | 补 List/Set/ZSet/Hash 缺失命令（`lpos/lmove/lmpop`、`smismember/sintercard/sunioncard`、`zmscore/zpopmin/zunion/zrangestore`、`hrandfield/hscan` 等） | 2 |
| 5 | `tx-pipe-pubsub` | 事务与管道封装（`multi/exec/watch/unwatch`、`pipeline` 工厂）；完善发布订阅（`subscribe/ssubscribe/spublish/get_message`） | 2 |
| 6 | `scripts-conn-cmds` | 脚本与函数、连接与服务器管理命令（`eval/evalsha/script_*/function_*`、`ping/info/config/client_*/bgsave/time` 等） | 2 |
| 7 | `streams-bitmap-cmds` | Streams / Bitmap / HyperLogLog / Geo 命令 | 2 |
| 8 | `verify-and-doc` | 引用校验、更新 `__main__` 自测块、输出 `doc/redisCommandCoverage.md` | 3–7 |

---

## 8. 验收与验证方法

### 8.1 静态校验（无服务端）

1. `python -m py_compile code/src/common/redisHandle.py` —— 语法通过。
2. `python -c "import sys; sys.path.insert(0,'code/src'); from common import redisHandle; print(redisHandle._VERSION)"` —— 模块可导入。
3. 反射核对：以 `redis.Redis` / `redis.client.PubSub` 的实测方法清单为准，逐条断言封装方法内部调用的方法名存在（**重点覆盖 B1/B2/B3 修复点**）。
4. 引用校验：用 LSP 对 `redisHandle.py` 内 `hmset/setnx/substr/flushdb/flushall/scan` 做定义与引用检索，确认 `redisCommon.py` 的 `redisMainDB.scan(cursor, dbKey)` 与 `redisPipe.set/expire/rpush/execute` 调用未受影响。

### 8.2 契约回归（无服务端，Mock）

构造一个 `unittest.mock.MagicMock` 作为 `dbW/dbR` 注入 `RedisHandle`，断言：
- `hmset("k", {"a": 1})` → 内部调用 `dbW.hset("k", mapping={"a": 1})` 且返回 `True`；
- `setnx("k", "v")` → 内部调用 `dbW.set("k", "v", nx=True)` 且返回 `1`/`0`；
- `substr("k", 0, 2)` → 内部调用 `dbR.getrange("k", 0, 2)`；
- `psubscribe("p*")` → 内部调用 `dbW.pubsub().psubscribe("p*")`；
- `PipeHandle(redisHandle)` 默认以 `transaction=True` 调用 `pipeline()`。

### 8.3 联调验证（需真实 Redis，可选）

若具备 Redis 8.x 实例，按「数据结构 → 事务/管道 → 发布订阅 → 脚本 → Streams/Bitmap/HLL/Geo」顺序冒烟；对 8.x 新命令（`INCREX/MSETEX/DELEX/DIGEST/SUNIONCARD/SDIFFCARD/LMOVEM/AR*`）在 **<8.x 服务端** 上应显式抛异常（符合「仅注释标注」策略，非缺陷）。

---

## 9. 风险与回滚

| 风险 | 等级 | 应对 |
|---|---|---|
| 改动量大（单文件新增数百方法）导致误改既有方法 | 中 | 既有方法体仅在「兼容修复」清单内改动，其余**只追加不改写**；用 LSP 引用校验兜底 |
| `hmset` 返回值由 `'OK'` 变为 `True` | 低 | 无调用点；已注释说明；如需严格等价可改回 `dbW.hmset` |
| `flushdb/flushall` 签名变更（去掉 `key`） | 低 | 无调用点；已注释说明 |
| `setnx` 返回值语义变化（bool → int） | 低 | 已在实现中显式转换保持 1/0 |
| 新增命令需高版本服务端，误用报错 | 中 | 全部标注 `[Rn.n+]`；文档第 5 节给出对照表 |
| `decode_responses` 误开启改变返回类型 | 中 | 默认 `False`，仅显式传参时生效 |
| Array 族（8.8）命令较新、参数复杂 | 低 | 单独成节并标注「实验性」，薄透传不做参数校验 |

**回滚**：本次仅改动 `code/src/common/redisHandle.py` 与新增 `doc/redisCommandCoverage.md`，`git checkout -- code/src/common/redisHandle.py` 即可完全回滚；调用链下游无需任何处理。

---

## 10. 附：redis-py 6.4.0 实测方法清单（节选核对结论）

- `redis.Redis` 公开方法 **361** 个。
- **不存在**于 `redis.Redis`：`subscribe / unsubscribe / psubscribe / punsubscribe`（须经 `pubsub()` 返回的 `PubSub` 对象）。
- **不存在**便捷封装（须 `execute_command`）：`sunioncard / sdiffcard / lmovem / blmovem / increx / msetex / delex / digest / xcfgset / xnack` 及全部 `ar*` Array 命令。
- **存在**便捷封装且需按签名调用（易错点）：
  - `lmpop(num_keys, *keys, direction, count=1)` —— `direction` 为**必填关键字**；
  - `blmpop(timeout, numkeys, *keys, direction, count=1)`；
  - `zmpop(num_keys, keys, min=False, max=False, count=1)` —— `min/max` **二选一**，同时传或都不传会 `DataError`；
  - `bzmpop(timeout, numkeys, keys, min=False, max=False, count=1)`；
  - `sintercard(numkeys, keys, limit=0)` / `zintercard(numkeys, keys, limit=0)`；
  - `hsetex(name, key=None, value=None, mapping=None, items=None, ex, px, exat, pxat, data_persist_option, keepttl)`；
  - `hgetex(name, *keys, ex, px, exat, pxat, persist=False)`；
  - `hexpire(name, seconds, *fields, nx, xx, gt, lt)`；
  - `xackdel(name, groupname, *ids, ref_policy=None)` / `xdelex(name, *ids, ref_policy=None)`；
  - `object(infotype, key)`（两参数，非单参数）。

---

*文档版本 v1.0 · 2026-09-18 · 因 IDE 客户端多次崩溃，方案先行冻结落盘，待环境稳定后按第 7 节顺序执行。*
