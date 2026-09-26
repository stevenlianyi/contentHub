# redisHandle.py 命令覆盖对照文档

| 项 | 内容 |
|---|---|
| 目标文件 | `code/src/common/redisHandle.py` |
| 文档版本 | v1.0 · 2026-09-18 |
| 运行基线 | Python 3.13 + redis-py 6.4.0；Redis 8.10（兼容回溯至 5.0） |
| `_VERSION` | `20260918` |
| 上游方案 | `plan/redisHandler.py重构计划.md`（S3 支线） |

> 图例：**已有** = 原实现保留；**增强** = 原方法扩展可选参数（旧调用不变）；**修复** = 历史遗留问题/Bug 修正；**新增** = 本次补充。
> 标注 `[Rn.n+]` 表示需服务端 ≥ 对应版本；`[alias]` 表示保留旧方法名作为兼容别名。

## 0. 本次兼容修复清单（对应方案 1.3 / 1.4）

| # | 方法 | 变更 | 说明 |
|---|---|---|---|
| P1 | `hmset` | **修复** | 内部改 `hset(key, mapping=...)`；保持返回 `True`（旧语义） |
| P2 | `setnx` | **修复** | 内部改 `set(key, value, nx=True)`；显式返回 `1/0` |
| P3 | `substr` | **修复** | 内部改 `getrange(key, start, end)`，保留方法名；`end` 默认 `-1` |
| P4 | `getset` | **仅注释** | 保留 `GETSET` 原命令（`SET ... GET` 需 ≥6.2，会破坏 5.0 兼容） |
| P5 | `flushdb` | **修复** | 去掉多余 `key` 参数，落地真实调用 `flushdb(asynchronous=False)` |
| P5 | `flushall` | **修复** | 同上，`flushall(asynchronous=False)` |
| P6 | `subscribe` / `unsubscribe` | **恢复** | 原被注释；改为 `dbW.pubsub().subscribe(...)` |
| B1 | `psubscribe` | **修复** | `redis.Redis` 无此方法 → `dbW.pubsub().psubscribe(...)` |
| B2 | `punsubscribe` | **修复** | 同上 → `dbW.pubsub().punsubscribe(...)` |
| B3 | `pubsub` | **修复** | 签名改 `pubsub(self, **kwargs)`（redis-py 不接受位置参数） |

## 1. 连接管理（Connect）

| 命令 | 状态 | 版本 | 方法 |
|---|---|---|---|
| PING / ECHO / AUTH | 新增 | AUTH 用户名需 R6.0+ | `ping` / `echo` / `auth` |
| QUIT / CLOSE | 新增 | — | `quit` / `close`（内部 `disconnect()`） |
| SELECT | 已有 | — | `select(dbType, dbindex)`（签名不变） |
| SWAPDB | 新增 | R4.0+ | `swapdb` |
| INFO / DBSIZE | 新增 / 已有 | — | `info(section=None)` → dbR |
| CONFIG GET/SET/REWRITE/RESETSTAT | 新增 | — | `config_get` / `config_set` / `config_rewrite` / `config_resetstat` |
| CLIENT LIST/KILL/ID/INFO/SETNAME/GETNAME/NO-EVICT/PAUSE/UNPAUSE/UNBLOCK/TRACKING* | 新增 | 部分 R6.0+ | `client_list` / `client_kill` / `client_id` / `client_info` / `client_setname` / `client_getname` / `client_no_evict` / `client_pause` / `client_unpause` / `client_unblock` / `client_tracking_on` / `client_tracking_off` / `client_trackinginfo` |
| WAIT / WAITAOF | 新增 | WAITAOF 需 R7.2+ | `wait` / `waitaof` |
| RESET | 新增 | R6.2+ | `reset` |
| HELLO | 新增 | R6.0+ | `hello` |
| MEMORY USAGE/STATS | 新增 | R4.0+ | `memory_usage` / `memory_stats`（execute_command） |
| COMMAND INFO/COUNT/LIST/GETKEYS/DOCS | 新增 | DOCS 需 R7.0+ | `command_info` / `command_count` / `command_list` / `command_getkeys` / `command_docs`（execute_command） |
| ROLE / REPLICAOF(SLAVEOF) / FAILOVER | 新增 | FAILOVER 需 R6.2+ | `role` / `replicaof` / `slaveof` / `failover`（execute_command） |

## 2. Key

| 命令 | 状态 | 版本 | 方法 |
|---|---|---|---|
| EXISTS / DEL / TYPE / KEYS / SCAN / RANDOMKEY / RENAME / RENAMENX / DBSIZE / EXPIRE / TTL / MOVE | 已有 | — | `scan` 末尾增补可选 `_type`；第 2 位置参数仍为 `match`（C4 契约） |
| FLUSHDB / FLUSHALL | **修复** | — | 修正签名并落地调用 |
| UNLINK | 新增 | R4.0+ | `unlink(*keys)` |
| TOUCH | 新增 | R3.2.1+ | `touch(*keys)` |
| EXPIREAT / PEXPIRE / PEXPIREAT | 新增 | — | `expireat` / `pexpire` / `pexpireat` |
| EXPIRETIME / PEXPIRETIME | 新增 | R7.0+ | `expiretime` / `pexpiretime` |
| PTTL / PERSIST | 新增 | — | `pttl` / `persist` |
| DUMP / RESTORE | 新增 | — | `dump` → dbR；`restore` → dbW |
| OBJECT ENCODING/REFCOUNT/FREQ/IDLETIME | 新增 | FREQ 需 LFU | `object(infotype, key)` + `object_encoding` / `object_refcount` / `object_idletime` / `object_freq` |
| COPY | 新增 | R6.2+ | `copy(source, destination, destination_db=None, replace=False)` |
| SORT / SORT_RO | 新增 | SORT_RO 需 R7.0+ | `sort` → dbW；`sort_ro` → dbR |
| SCAN_ITER | 新增 | — | `scan_iter`（阻塞生成器，不可入 pipeline） |

## 3. String

| 命令 | 状态 | 版本 | 方法 |
|---|---|---|---|
| SET | **增强** | — | 增补 `ex/px/nx/xx/keepttl/get/exat/pxat`；`set(key, value)` 不变 |
| SETNX | **修复** | — | `set(nx=True)`，返回 1/0 |
| GETSET | **仅注释** | Redis 6.2 起废弃 | 保留原命令 |
| SUBSTR | **修复** | — | 内部 `getrange` |
| GET / MGET / MSET / MSETNX / INCR / DECR / INCRBY / DECRBY / APPEND | 已有 | — | — |
| SETEX / PSETEX / SETRANGE / GETRANGE / STRLEN | 新增 | — | 同名方法 |
| GETDEL / GETEX | 新增 | R6.2+ | `getdel` / `getex` |
| INCRBYFLOAT | 新增 | R2.6+ | `incrbyfloat` |
| LCS | 新增 | R7.0+ | `lcs` |
| MSETEX / DELEX / DIGEST | 新增 | **R8.4+** | `msetex` / `delex` / `digest`（execute_command） |
| INCREX | 新增 | **R8.8+** | `increx`（execute_command） |

## 4. List

| 命令 | 状态 | 版本 | 方法 |
|---|---|---|---|
| LPUSH / RPUSH | **增强** | — | 改 `*values`（单值兼容） |
| LPUSHX / RPUSHX | 新增 | — | 同名方法 |
| LPOP / RPOP | **增强** | count 需 R6.2+ | 增补可选 `count` |
| LLEN / LRANGE / LTRIM / LSET / LREM / RPOPLPUSH | 已有 | — | — |
| LINDEX / LINSERT | 新增 | — | `lindex` / `linsert` |
| LPOS | 新增 | R6.0.6+ | `lpos` |
| LMOVE / BLMOVE | 新增 | R6.2+ | `lmove` / `blmove` |
| BRPOPLPUSH | 新增 | — | `brpoplpush` |
| LMPOP / BLMPOP | 新增 | R7.0+ | `lmpop(keys, direction, count)` / `blmpop(timeout, keys, ...)` |
| LMOVEM / BLMOVEM | 新增 | **R8.10+** | `lmovem` / `blmovem`（execute_command） |

## 5. Set

| 命令 | 状态 | 版本 | 方法 |
|---|---|---|---|
| SADD / SREM | **增强** | — | 改 `*members`（单值兼容） |
| SPOP / SRANDMEMBER | **增强** | — | 增补可选 `count` |
| SMOVE / SCARD / SISMEMBER / SINTER / SINTERSTORE / SUNION / SUNIONSTORE / SDIFF / SDIFFSTORE / SMEMBERS | 已有 | — | — |
| SMISMEMBER | 新增 | R6.2+ | `smismember`（execute_command） |
| SINTERCARD | 新增 | R7.0+ | `sintercard(keys, limit=0)` |
| SSCAN / SSCAN_ITER | 新增 | — | `sscan` / `sscan_iter` |
| SUNIONCARD / SDIFFCARD | 新增 | **R8.10+** | `sunioncard` / `sdiffcard`（execute_command） |

## 6. Sorted Set

| 命令 | 状态 | 版本 | 方法 |
|---|---|---|---|
| ZADD | **增强** | GT/LT/INCR 需 R6.2+ | 增补 `nx/xx/ch/incr/gt/lt`；`zadd(key, score, member)` 不变 |
| ZREM | **增强** | — | 改 `*members` |
| ZRANK / ZREVRANK | **增强** | withscore 需 R7.2+ | 增补可选 `withscore` |
| ZRANGEBYSCORE | **增强** | — | 增补 `start/num/withscores` |
| ZINCRBY / ZRANGE / ZREVRANGE / ZCOUNT / ZCARD / ZSCORE / ZREMRANGEBYRANK / ZREMRANGEBYSCORE | 已有 | — | — |
| ZREVRANGEBYSCORE / ZRANGEBYLEX / ZREVRANGEBYLEX / ZLEXCOUNT / ZREMRANGEBYLEX | 新增 | — | 同名方法 |
| ZMSCORE | 新增 | R6.2+ | `zmscore`（execute_command） |
| ZPOPMIN / ZPOPMAX / BZPOPMIN / BZPOPMAX | 新增 | R5.0+ | 同名方法 |
| ZRANDMEMBER | 新增 | R6.2+ | `zrandmember` |
| ZUNION / ZUNIONSTORE / ZINTER / ZINTERSTORE / ZDIFF / ZDIFFSTORE / ZRANGESTORE | 新增 | R6.2+ | 同名方法 |
| ZINTERCARD | 新增 | R7.0+ | `zintercard(keys, limit=0)` |
| ZMPOP / BZMPOP | 新增 | R7.0+ | `zmpop` / `bzmpop`（min/max 二选一） |
| ZSCAN / ZSCAN_ITER | 新增 | — | `zscan` / `zscan_iter` |

## 7. Hash

| 命令 | 状态 | 版本 | 方法 |
|---|---|---|---|
| HSET | **增强** | — | 增补 `mapping` 多字段写法；`hset(key, field, value)` 不变 |
| HMSET | **修复** | Redis 4.0 起废弃 | 内部 `hset(mapping=...)`，保留方法名，返回 `True` |
| HDEL | **增强** | — | 改 `*fields` |
| HGET / HMGET / HINCRBY / HEXISTS / HLEN / HKEYS / HVALS / HGETALL | 已有 | — | — |
| HSETNX / HSTRLEN / HINCRBYFLOAT | 新增 | — | 同名方法 |
| HRANDFIELD | 新增 | R6.2+ | `hrandfield` |
| HSCAN / HSCAN_ITER | 新增 | — | `hscan` / `hscan_iter` |
| HEXPIRE / HPEXPIRE / HEXPIREAT / HPEXPIREAT | 新增 | R7.4+ | 同名方法（`**kwargs` 透传 NX/XX/GT/LT） |
| HEXPIRETIME / HPEXPIRETIME / HTTL / HPTTL / HPERSIST | 新增 | R7.4+ | 同名方法 |
| HGETDEL / HGETEX / HSETEX | 新增 | **R8.0+** | `hgetdel`（execute_command）/ `hgetex` / `hsetex`（`**kwargs` 透传） |

## 8. Streams

| 命令 | 状态 | 版本 | 方法 |
|---|---|---|---|
| XADD / XLEN / XRANGE / XREVRANGE / XDEL / XTRIM | 新增 | R5.0+ | 同名方法 |
| XREAD / XREADGROUP | 新增 | R5.0+ | `xread` / `xreadgroup` |
| XACK / XPENDING / XPENDING_RANGE | 新增 | R5.0+ | `xack` / `xpending` / `xpending_range` |
| XGROUP CREATE/DESTROY/SETID/DELCONSUMER/CREATECONSUMER | 新增 | CREATECONSUMER 需 R6.2+ | `xgroup_create` / `xgroup_destroy` / `xgroup_setid` / `xgroup_delconsumer` / `xgroup_createconsumer` |
| XCLAIM / XAUTOCLAIM | 新增 | XAUTOCLAIM 需 R6.2+ | `xclaim` / `xautoclaim` |
| XINFO STREAM/GROUPS/CONSUMERS | 新增 | R5.0+ | `xinfo_stream` / `xinfo_groups` / `xinfo_consumers` |
| XACKDEL / XDELEX | 新增 | **R8.2+** | `xackdel` / `xdelex`（`**kwargs` 透传） |
| XCFGSET | 新增 | **R8.6+** | `xcfgset`（execute_command） |
| XNACK | 新增 | **R8.8+** | `xnack`（execute_command） |

## 9. Bitmap / HyperLogLog / Geo

| 命令 | 状态 | 版本 | 方法 |
|---|---|---|---|
| SETBIT / GETBIT / BITCOUNT / BITOP | 新增 | R2.6+ | 同名方法 |
| BITPOS | 新增 | R2.8.7+ | `bitpos` |
| BITFIELD / BITFIELD_RO | 新增 | R3.2+ / BITFIELD_RO 需 R6.0+ | `bitfield` → dbW；`bitfield_ro` → dbR（execute_command） |
| PFADD / PFCOUNT / PFMERGE | 新增 | R2.8.9+ | 同名方法 |
| GEOADD / GEOPOS / GEODIST / GEOHASH | 新增 | R3.2+ | 同名方法 |
| GEORADIUS / GEORADIUSBYMEMBER | 新增 | R3.2+（R7.0 起不推荐） | 同名方法，归 dbW |
| GEOSEARCH / GEOSEARCHSTORE | 新增 | R6.2+ | `geosearch` → dbR；`geosearchstore` → dbW |

## 10. 事务 / 管道

| 能力 | 状态 | 版本 | 方法 / 说明 |
|---|---|---|---|
| WATCH / UNWATCH | 新增 | R2.2+ | `watch(*keys)` / `unwatch()` |
| PIPELINE | 新增 | — | `pipeline(transaction=True, shard_hint=None)` |
| MULTI / EXEC / DISCARD | 新增 | — | `multi()` 返回事务型管道；`execute()` 触发 EXEC；`reset()` 等价 DISCARD |
| 回调式事务 | 新增 | — | `transaction(func, *watches)` |
| `PipeHandle.__init__` | **增强** | — | 增补可选 `transaction=True`，默认值保持原行为 |
| `PipeHandle.reset` | 新增 | — | 丢弃缓冲 |

> **不支持管道的命令**：`subscribe / unsubscribe / psubscribe / punsubscribe / ssubscribe / sunsubscribe`、`scan_iter` 系（阻塞生成器）、`select / hello / reset / monitor / wait`。

## 11. 发布订阅

| 命令 | 状态 | 版本 | 方法 |
|---|---|---|---|
| SUBSCRIBE / UNSUBSCRIBE | **恢复** | — | `subscribe` / `unsubscribe` |
| PSUBSCRIBE / PUNSUBSCRIBE | **修复 B1/B2** | — | `psubscribe` / `punsubscribe` |
| PUBSUB | **修复 B3** | — | `pubsub(**kwargs)` |
| PUBLISH | 已有 | — | `publish` |
| PUBSUB CHANNELS/NUMSUB/NUMPAT | 新增 | — | `pubsub_channels` / `pubsub_numsub` / `pubsub_numpat` |
| SPUBLISH | 新增 | R7.0+ | `spublish` |
| SSUBSCRIBE / SUNSUBSCRIBE | 新增 | R7.0+ | `ssubscribe` / `sunsubscribe` |
| PUBSUB SHARDCHANNELS/SHARDNUMSUB | 新增 | R7.0+ | `pubsub_shardchannels` / `pubsub_shardnumsub` |
| GET_MESSAGE / GET_SHARDED_MESSAGE | 新增 | 分片需 R7.0+ | `get_message` / `get_sharded_message` |

## 12. 脚本与函数

| 命令 | 状态 | 版本 | 方法 |
|---|---|---|---|
| EVAL / EVALSHA | 新增 | R2.6+ | 同名方法 → dbW |
| EVAL_RO / EVALSHA_RO | 新增 | R7.0+ | 同名方法 → dbR |
| SCRIPT LOAD / EXISTS / FLUSH / KILL / DEBUG | 新增 | DEBUG 需 R3.2+ | `script_load` / `script_exists`(dbR) / `script_flush` / `script_kill` / `script_debug` |
| REGISTER_SCRIPT | 新增 | — | `register_script` 返回可复用 `Script` 对象 |
| FCALL / FCALL_RO | 新增 | R7.0+ | `fcall` → dbW；`fcall_ro` → dbR |
| FUNCTION LOAD/DELETE/FLUSH/LIST/DUMP/RESTORE/KILL/STATS | 新增 | R7.0+ | `function_list`/`function_stats`/`function_dump` → dbR，其余 dbW |

## 13. 服务器管理

| 命令 | 状态 | 版本 | 方法 |
|---|---|---|---|
| SAVE | 已有 | — | `save` |
| BGSAVE / BGREWRITEAOF / LASTSAVE | 新增 | — | `bgsave` / `bgrewriteaof` / `lastsave` |
| SHUTDOWN | 新增 | — | `shutdown(...)`（**高危，慎用**） |
| TIME | 新增 | — | `time` |
| DEBUG OBJECT | 新增 | — | `debug_object`（execute_command） |
| SLOWLOG GET/LEN/RESET | 新增 | — | `slowlog_get` / `slowlog_len` / `slowlog_reset` |
| MIGRATE | 新增 | — | `migrate`（透传） |
| MONITOR | 新增 | — | `monitor`（独占连接） |
| LOLWUT | 新增 | — | `lolwut` |

## 14. Array 数据结构 [R8.8+]（实验性）

`ARCOUNT / ARDEL / ARDELRANGE / ARGET / ARGETRANGE / ARGREP / ARINFO / ARINSERT / ARLASTITEMS / ARLEN / ARMGET / ARMSET / ARNEXT / AROP / ARRING / ARSCAN / ARSEEK / ARSET`

对应方法 `arcount / ardel / ... / arset`，全部以 `execute_command` 薄透传，参数不校验，需服务端 ≥ 8.8。

---

## 15. 兼容性契约（不可破坏）

| # | 契约 | 校验结果 |
|---|---|---|
| C1 | `getRedisDB(host, port, db, username="", passwd="")` 前 3 位置参数 + 2 关键字参数保持 | 通过（新增参数全部为可选） |
| C2 | `RedisHandle(dbW=..., dbR=...)` 支持关键字传参 | 通过 |
| C3 | `PipeHandle(RedisHandle实例)` 支持位置传参 | 通过（`transaction` 有默认值） |
| C4 | `RedisHandle.scan` 第 2 位置参数必须为 `match` | 通过（`cursor, match, count, _type`） |
| C5 | 顶层变量名 `dbMainW / dbMainR / redisMainDB / redisPipe` | 未改动 |
| C6 | `PipeHandle` 支持 `set / expire / lpush / rpush / execute` | 通过（继承 + 缓冲） |

## 16. 验证记录（2026-09-18）

1. `python -m py_compile code/src/common/redisHandle.py` —— **通过**。
2. AST 反射：`RedisHandle` 共 **326** 个方法，原 **85** 个方法 **零缺失、零重名**；`PipeHandle` 3 个方法。
3. 签名断言：C1/C2/C3/C4 全部符合预期；`_VERSION == "20260918"`。
4. `__main__` 自测块新增「反射自测」：打印 redis-py 中缺失的依赖方法（重点覆盖 B1/B2/B3 修复点）。

> **未执行项**：因当前环境未安装 redis-py（离线无法 pip 安装），方案 8.1.3 的「以 `redis.Redis` 实测方法清单逐条断言」与 8.3 的真实 Redis 联调暂未运行；待具备 redis-py 6.4.0 环境后补跑。
