#! /usr/bin/env python3
#encoding: utf-8
# 2019-09-01 steven
# 2026-09-18 S3 支线: redis-py 6.4.0 兼容修复 + Redis 8.10 命令族补齐

_VERSION = "20260918"

# 版本标注约定:
#   [Rn.n+]  该命令引入(或推荐使用)的 Redis 版本, 需服务端 >= 对应版本
#   [alias]  保留旧方法名作为兼容别名
#   未标注版本的命令在 Redis 5.0 及更早版本即可用, 保持向后兼容
#
# 兼容策略: 仅做版本注释标注, 不内置 try/except 容错;
#           服务端版本不支持时, 由 redis-py 底层抛出异常.
#
# 接口约定: dbW 主库(写) / dbR 从库(读); 返回 redis-py 原始结果.
# 订阅说明: subscribe/psubscribe/ssubscribe 返回的 PubSub 对象独占连接,
#           不能复用执行普通命令, 也不能放入 pipeline.
# 管道限制: 下列命令不可放入 pipeline ——
#           subscribe/unsubscribe/psubscribe/punsubscribe/ssubscribe/sunsubscribe,
#           scan_iter 系(阻塞生成器), select/hello/reset/monitor/wait.

import redis


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


class RedisHandle:
    def __init__(self, dbW, dbR):
        self.dbW = dbW
        self.dbR = dbR

    # ============================================================
    # 连接管理 (Connect)
    # ============================================================
    def ping(self):
        # PING; 连通性检测, 正常返回 True
        return self.dbW.ping()
    def echo(self, value):
        # ECHO message; 回显给定字符串
        return self.dbW.echo(value)
    def auth(self, password, username=None):
        # AUTH [username] password; ACL 用户名需 [R6.0+]
        return self.dbW.auth(password, username)
    def quit(self):
        # QUIT; 关闭连接(连接池场景下等价断开当前连接)
        return self.dbW.disconnect()
    def close(self):
        # CLOSE; 同 quit()
        return self.dbW.disconnect()
    def swapdb(self, first, second):
        # [R4.0+] SWAPDB index1 index2; 原子交换两个数据库
        return self.dbW.swapdb(first, second)
    def info(self, section=None):
        # INFO [section]; 服务器信息, 走从库
        return self.dbR.info(section)
    def config_get(self, pattern="*"):
        # CONFIG GET parameter
        return self.dbR.config_get(pattern)
    def config_set(self, name, value):
        # CONFIG SET parameter value
        return self.dbW.config_set(name, value)
    def config_rewrite(self):
        # CONFIG REWRITE; 将运行时配置写回配置文件
        return self.dbW.config_rewrite()
    def config_resetstat(self):
        # CONFIG RESETSTAT; 重置统计信息
        return self.dbW.config_resetstat()
    def client_list(self, *args, **kwargs):
        # CLIENT LIST; 列出当前连接
        return self.dbR.client_list(*args, **kwargs)
    def client_kill(self, address):
        # CLIENT KILL addr:port; 关闭指定连接
        return self.dbW.client_kill(address)
    def client_id(self):
        # CLIENT ID; 当前连接的唯一 ID
        return self.dbW.client_id()
    def client_info(self):
        # CLIENT INFO; 当前连接信息
        return self.dbR.client_info()
    def client_setname(self, name):
        # CLIENT SETNAME connection-name
        return self.dbW.client_setname(name)
    def client_getname(self):
        # CLIENT GETNAME
        return self.dbR.client_getname()
    def client_no_evict(self, mode):
        # [R7.0+] CLIENT NO-EVICT on|off; 连接级是否允许被驱逐
        return self.dbW.client_no_evict(mode)
    def client_pause(self, timeout, all=False):
        # [R2.9.50+] CLIENT PAUSE timeout [ALL|WRITE]
        return self.dbW.client_pause(timeout, all=all)
    def client_unpause(self):
        # CLIENT UNPAUSE
        return self.dbW.client_unpause()
    def client_unblock(self, client_id, error=False):
        # [R5.0+] CLIENT UNBLOCK client-id [TIMEOUT|ERROR]
        return self.dbW.client_unblock(client_id, error=error)
    def client_tracking_on(self, *args, **kwargs):
        # [R6.0+] CLIENT TRACKING ON ...
        return self.dbW.client_tracking_on(*args, **kwargs)
    def client_tracking_off(self, *args, **kwargs):
        # [R6.0+] CLIENT TRACKING OFF
        return self.dbW.client_tracking_off(*args, **kwargs)
    def client_trackinginfo(self):
        # [R6.0+] CLIENT TRACKINGINFO
        return self.dbR.client_trackinginfo()
    def wait(self, num_replicas, timeout):
        # WAIT numreplicas timeout; 阻塞等待写命令复制到指定副本数
        return self.dbW.wait(num_replicas, timeout)
    def waitaof(self, num_local, num_replicas, timeout):
        # [R7.2+] WAITAOF numlocal numreplicas timeout; 等待 AOF 落盘
        return self.dbW.waitaof(num_local, num_replicas, timeout)
    def reset(self):
        # [R6.2+] RESET; 重置当前连接状态
        return self.dbW.reset()
    def hello(self):
        # [R6.0+] HELLO; 协议握手(redis-py 6.4 无参)
        return self.dbW.hello()
    def memory_usage(self, key, samples=None):
        # [R4.0+] MEMORY USAGE key [SAMPLES count]
        return self.dbR.execute_command("MEMORY", "USAGE", key) if samples is None \
            else self.dbR.execute_command("MEMORY", "USAGE", key, "SAMPLES", samples)
    def memory_stats(self):
        # [R4.0+] MEMORY STATS
        return self.dbR.execute_command("MEMORY", "STATS")
    def command_info(self, *args):
        # COMMAND INFO [command-name ...]
        return self.dbR.execute_command("COMMAND", "INFO", *args)
    def command_count(self):
        # COMMAND COUNT
        return self.dbR.execute_command("COMMAND", "COUNT")
    def command_list(self, *args):
        # COMMAND LIST [FILTERBY MODULE|ACLCAT|PATTERN value]
        return self.dbR.execute_command("COMMAND", "LIST", *args)
    def command_getkeys(self, command, *args):
        # COMMAND GETKEYS command [arg ...]
        return self.dbR.execute_command("COMMAND", "GETKEYS", command, *args)
    def command_docs(self, *args):
        # [R7.0+] COMMAND DOCS [command-name ...]
        return self.dbR.execute_command("COMMAND", "DOCS", *args)
    def role(self):
        # ROLE; 返回当前实例角色
        return self.dbR.role()
    def replicaof(self, host, port):
        # REPLICAOF host port; 将当前实例设为指定实例的副本
        return self.dbW.replicaof(host, port)
    def slaveof(self, host, port):
        # [alias] SLAVEOF host port; 旧命令名, 等价 REPLICAOF
        return self.dbW.slaveof(host, port)
    def failover(self, *args):
        # [R6.2+] FAILOVER [TO host port] [FORCE|ABORT|TIMEOUT ms]; 薄透传
        return self.dbW.execute_command("FAILOVER", *args)

    # ============================================================
    # Key 相关命令
    # ============================================================
    def exists(self, key):
        # exits key 测试指定key是否存在，返回1表示存在，0不存在
        return self.dbR.exists(key)
    def delete(self, * keys):
        # del key1 key2 ....keyN  删除给定key,返回删除key的数目，0表示给定key都不存在
        return self.dbW.delete(* keys)
    def type(self, key):
        # type key 返回给定key的value类型。返回 none 表示不存在，key有string字符类型，list 链表类型 set 无序集合类型等...
        return self.dbR.type(key)
    def keys(self, pattern):
        # keys pattern 返回匹配指定模式的所有key（支持*，？，[abc ]的方式）
        return self.dbR.keys(pattern)
    def scan(self, cursor=0, match=None, count=None, _type=None):
        # SCAN cursor [MATCH pattern] [COUNT count] [TYPE type]
        # 注意: 第2个位置参数必须是 match (redisCommon.scan(cursor, dbKey) 依赖此位置)
        return self.dbR.scan(cursor, match, count, _type)
    def scan_iter(self, match=None, count=None, _type=None):
        # SCAN 游标增量迭代生成器; 阻塞式, 不可放入 pipeline
        return self.dbR.scan_iter(match=match, count=count, _type=_type)
    def randomkey(self):
        # randomkey 返回从当前数据库中随机选择的一个key,如果当前数据库是空的，返回空串
        return self.dbR.randomkey()
    def rename(self, oldkey, newkey):
        # rename oldkey newkey 原子的重命名一个key,如果newkey存在，将会被覆盖，返回1表示成功，0失败。失败可能是oldkey不存在或者和newkey相同
        return self.dbW.rename(oldkey, newkey)
    def renamenx(self, oldkey, newkey):
        # renamenx oldkey newkey 同上，但是如果newkey存在返回失败
        return self.dbW.renamenx(oldkey, newkey)
    def dbsize(self):
        # dbsize 返回当前数据库的key数量
        return self.dbR.dbsize()
    def expire(self, key, seconds):
        # expire key seconds 为key指定过期时间，单位是秒。返回1成功，0表示key已经设置过过期时间或者不存在
        return self.dbW.expire(key, seconds)
    def expireat(self, key, when):
        # EXPIREAT key timestamp; 指定绝对过期时间(秒级 unix 时间戳)
        return self.dbW.expireat(key, when)
    def pexpire(self, key, milliseconds):
        # PEXPIRE key milliseconds; 毫秒级相对过期
        return self.dbW.pexpire(key, milliseconds)
    def pexpireat(self, key, when):
        # PEXPIREAT key milliseconds-timestamp; 毫秒级绝对过期
        return self.dbW.pexpireat(key, when)
    def expiretime(self, key):
        # [R7.0+] EXPIRETIME key; 返回绝对过期时间戳(秒)
        return self.dbR.expiretime(key)
    def pexpiretime(self, key):
        # [R7.0+] PEXPIRETIME key; 返回绝对过期时间戳(毫秒)
        return self.dbR.pexpiretime(key)
    def ttl(self, key):
        # ttl key 返回设置了过期时间的key的剩余过期秒数， -1表示key不存在或者没有设置过过期时间
        return self.dbR.ttl(key)
    def pttl(self, key):
        # PTTL key; 返回剩余过期毫秒数
        return self.dbR.pttl(key)
    def persist(self, key):
        # PERSIST key; 移除 key 的过期时间, 成功返回 1
        return self.dbW.persist(key)
    def unlink(self, *keys):
        # [R4.0+] UNLINK key [key ...]; 异步(非阻塞)删除
        return self.dbW.unlink(*keys)
    def touch(self, *keys):
        # [R3.2.1+] TOUCH key [key ...]; 更新访问时间, 返回被更新的 key 数
        return self.dbW.touch(*keys)
    def dump(self, key):
        # DUMP key; 序列化并返回值的二进制快照
        return self.dbR.dump(key)
    def restore(self, key, ttl, value, replace=False):
        # RESTORE key ttl serialized-value [REPLACE]; 反序列化写入
        return self.dbW.restore(key, ttl, value, replace=replace)
    def object(self, infotype, key):
        # OBJECT ENCODING|REFCOUNT|IDLETIME|FREQ key (redis-py 6.4 签名为两参数)
        return self.dbR.object(infotype, key)
    def object_encoding(self, key):
        # OBJECT ENCODING key; 值的内部编码
        return self.dbR.object("ENCODING", key)
    def object_refcount(self, key):
        # OBJECT REFCOUNT key; 值的引用计数
        return self.dbR.object("REFCOUNT", key)
    def object_idletime(self, key):
        # OBJECT IDLETIME key; 空闲秒数
        return self.dbR.object("IDLETIME", key)
    def object_freq(self, key):
        # OBJECT FREQ key; 需 maxmemory-policy 为 LFU
        return self.dbR.object("FREQ", key)
    def copy(self, source, destination, destination_db=None, replace=False):
        # [R6.2+] COPY source destination [DB destination-db] [REPLACE]
        return self.dbW.copy(source, destination, destination_db=destination_db, replace=replace)
    def sort(self, key, *args, **kwargs):
        # SORT key [BY|LIMIT|GET|ASC|DESC|ALPHA] [STORE destination]
        # 可带 STORE 落盘写操作, 故归 dbW
        return self.dbW.sort(key, *args, **kwargs)
    def sort_ro(self, key, *args, **kwargs):
        # [R7.0+] SORT_RO key [...]; 只读版 SORT, 归 dbR
        return self.dbR.sort_ro(key, *args, **kwargs)
    def select(self, dbType, dbindex):
        # select db-index 通过索引选择数据库，默认连接的数据库所有是0,默认数据库数是16个。返回1表示成功，0失败
        #dbType: R从库，W主库（默认）
        if dbType == "R":
            db = self.dbR
        else:
            db = self.dbW
        return db.select(dbindex)
    def move(self, key, dbindex):
        # move key db-index  将key从当前数据库移动到指定数据库。返回1成功。0 如果key不存在，或者已经在指定数据库中
        return self.dbW.move(key, dbindex)
    def flushdb(self, asynchronous=False):
        # 修正: 原签名误带 key 参数且为空实现; FLUSHDB 高危, 慎用
        return self.dbW.flushdb(asynchronous=asynchronous)
    def flushall(self, asynchronous=False):
        # 修正: 同上; FLUSHALL 高危, 更加慎用
        return self.dbW.flushall(asynchronous=asynchronous)

    # ============================================================
    # String 相关命令
    # ============================================================
    def set(self, key, value, ex=None, px=None, nx=False, xx=False,
            keepttl=False, get=False, exat=None, pxat=None):
        # SET key value [EX s|PX ms|EXAT ts|PXAT ts|KEEPTTL] [NX|XX] [GET]
        # 原 set(key, value) 调用不变, 新增选项均为可选
        return self.dbW.set(key, value, ex=ex, px=px, nx=nx, xx=xx,
                            keepttl=keepttl, get=get, exat=exat, pxat=pxat)
    def setnx(self, key, value):
        # [alias] SETNX; redis-py 推荐 SET ... NX, 此处保持原有 1/0 返回语义
        return 1 if self.dbW.set(key, value, nx=True) else 0
    def setex(self, key, time, value):
        # SETEX key seconds value; 设置值并附带秒级过期
        return self.dbW.setex(key, time, value)
    def psetex(self, key, time_ms, value):
        # PSETEX key milliseconds value; 设置值并附带毫秒级过期
        return self.dbW.psetex(key, time_ms, value)
    def get(self, key):
        # get key 获取key对应的string值,如果key不存在返回nil
        return self.dbR.get(key)
    def getset(self, key, value):
        # getset key value  设置key的值，并返回key的旧值。如果key不存在返回nil
        # 注意: GETSET 自 Redis 6.2 起被 SET ... GET 取代; 此处保留原命令以兼容 5.0 服务端
        return self.dbW.getset(key, value)
    def getdel(self, key):
        # [R6.2+] GETDEL key; 取值并删除
        return self.dbW.getdel(key)
    def getex(self, key, ex=None, px=None, exat=None, pxat=None, persist=False):
        # [R6.2+] GETEX key [EX s|PX ms|EXAT ts|PXAT ts|PERSIST]; 取值并调整过期
        return self.dbW.getex(key, ex=ex, px=px, exat=exat, pxat=pxat, persist=persist)
    def mget(self, *keys):
        # mget key1 key2 ... keyN 一次获取多个key的值，如果对应key不存在，则对应返回nil。下面是个实验, nonexisting不存在，对应返回nil
        return self.dbR.mget(*keys)
    def mset(self, mappings):
        # mset key1 value1 ... keyN valueN 一次设置多个key的值，成功返回1表示所有的值都设置了，失败返回0表示没有任何值被设置
        return self.dbW.mset(mappings)
    def msetnx(self, mappings):
        # msetnx key1 value1 ... keyN valueN 同上，但是不会覆盖已经存在的key
        return self.dbW.msetnx(mappings)
    def incr(self, key):
        # incr key 对key的值做加加操作,并返回新的值。注意incr一个不是int的value会返回错误，incr一个不存在的key，则设置key为1
        return self.dbW.incr(key)
    def decr(self, key):
        # decr key 同上，但是做的是减减操作，decr一个不存在key，则设置key为-1
        return self.dbW.decr(key)
    def incrby(self, key, integer):
        # incrby key integer 同incr，加指定值 ，key不存在时候会设置key，并认为原来的value是 0
        return self.dbW.incrby(key, integer)
    def decrby(self, key, integer):
        # decrby key integer 同decr，减指定值。decrby完全是为了可读性，我们完全可以通过incrby一个负值来实现同样效果，反之一样。
        return self.dbW.decrby(key, integer)
    def incrbyfloat(self, key, amount):
        # [R2.6+] INCRBYFLOAT key increment; 浮点自增
        return self.dbW.incrbyfloat(key, amount)
    def append(self, key, value):
        # append key value  给指定key的字符串值追加value,返回新字符串值的长度。
        return self.dbW.append(key, value)
    def setrange(self, key, offset, value):
        # SETRANGE key offset value; 从偏移量起覆盖写入
        return self.dbW.setrange(key, offset, value)
    def getrange(self, key, start, end):
        # GETRANGE key start end; 截取子串(不修改原值)
        return self.dbR.getrange(key, start, end)
    def substr(self, key, start, end=-1):
        # [alias] SUBSTR; 内部改 GETRANGE(等价, Redis 2.0+), 保留方法名
        return self.dbR.getrange(key, start, end)
    def strlen(self, key):
        # STRLEN key; 值长度
        return self.dbR.strlen(key)
    def lcs(self, key1, key2, len=False, idx=False, minmatchlen=0, withmatchlen=False):
        # [R7.0+] LCS key1 key2 [LEN|IDX|MINMATCHLEN n|WITHMATCHLEN]; 最长公共子串
        return self.dbR.lcs(key1, key2, len=len, idx=idx,
                            minmatchlen=minmatchlen, withmatchlen=withmatchlen)
    def msetex(self, *args):
        # [R8.4+] MSETEX key value [...] [EX|PX|EXAT|PXAT|KEEPTTL] [NX|XX]
        # redis-py 6.4.0 无便捷方法, 薄透传; 需服务端 >= 8.4
        return self.dbW.execute_command("MSETEX", *args)
    def delex(self, key, *args):
        # [R8.4+] DELEX key [IFEQ v|IFNE v|IFGT v|IFLT v]; 条件删除; 薄透传
        return self.dbW.execute_command("DELEX", key, *args)
    def digest(self, key):
        # [R8.4+] DIGEST key; 返回值摘要; 薄透传
        return self.dbR.execute_command("DIGEST", key)
    def increx(self, key, *args):
        # [R8.8+] INCREX key [...]; 自增并设置过期; 薄透传
        return self.dbW.execute_command("INCREX", key, *args)

    # ============================================================
    # List 相关命令
    # redis的list类型其实就是一个每个子元素都是string类型的双向链表。我们可以通过push,pop操作从链表的头部或者尾部添加删除元素。这使得list既可以用作栈，也可以用作队列。
    # ============================================================
    def lpush(self, key, *values):
        # lpush key string 在key对应list的头部添加字符串元素，返回list长度; 支持多值
        return self.dbW.lpush(key, *values)
    def rpush(self, key, *values):
        # rpush key string 同上，在尾部添加; 支持多值
        return self.dbW.rpush(key, *values)
    def lpushx(self, key, *values):
        # LPUSHX key value [...]; 仅当 key 存在时头部插入
        return self.dbW.lpushx(key, *values)
    def rpushx(self, key, *values):
        # RPUSHX key value [...]; 仅当 key 存在时尾部插入
        return self.dbW.rpushx(key, *values)
    def llen(self, key):
        # llen key 返回key对应list的长度，key不存在返回0,如果key对应类型不是list返回错误
        return self.dbR.llen(key)
    def lrange(self, key, start, end):
        # lrange key start end 返回指定区间内的元素，下标从0开始，负值表示从后面计算，-1表示倒数第一个元素 ，key不存在返回空列表
        return self.dbR.lrange(key, start, end)
    def ltrim(self, key, start, end):
        # ltrim key start end  截取list，保留指定区间内元素，成功返回1，key不存在返回错误
        return self.dbW.ltrim(key, start, end)
    def lset(self, key, index, value):
        # lset key index value 设置list中指定下标的元素值，成功返回1，key或者下标不存在返回错误
        return self.dbW.lset(key, index, value)
    def lindex(self, key, index):
        # LINDEX key index; 取指定下标元素
        return self.dbR.lindex(key, index)
    def linsert(self, key, where, refvalue, value):
        # LINSERT key BEFORE|AFTER pivot value; 在参考元素前后插入
        return self.dbW.linsert(key, where, refvalue, value)
    def lrem(self, key, count, value):
        # lrem key count value 从key对应list中删除count个和value相同的元素。count为0时候删除全部
        return self.dbW.lrem(key, count, value)
    def lpop(self, key, count=None):
        # lpop key 从list的头部删除元素，并返回删除元素。
        # [R6.2+] 可选 count 返回多个元素
        if count is None:
            return self.dbW.lpop(key)
        return self.dbW.lpop(key, count)
    def rpop(self, key, count=None):
        # rpop 同上，但是从尾部删除; [R6.2+] 可选 count
        if count is None:
            return self.dbW.rpop(key)
        return self.dbW.rpop(key, count)
    def lpos(self, key, element, rank=None, count=None, maxlen=None):
        # [R6.0.6+] LPOS key element [RANK r] [COUNT n] [MAXLEN m]
        return self.dbR.lpos(key, element, rank=rank, count=count, maxlen=maxlen)
    def blpop(self, keysList, timeout):
        # blpop key1...keyN timeout 从左到右扫描返回对第一个非空list进行lpop操作并返回，timeout为0表示一直阻塞。
        return self.dbW.blpop(keysList, timeout)
    def brpop(self, keysList, timeout):
        # brpop 同blpop，一个是从头部删除一个是从尾部删除
        return self.dbW.brpop(keysList, timeout)
    def rpoplpush(self, srckey, destkey):
        # rpoplpush srckey destkey 从srckey对应list的尾部移除元素并添加到destkey对应list的头部,最后返回被移除的元素值，整个操作是原子的。
        return self.dbW.rpoplpush(srckey, destkey)
    def brpoplpush(self, source, destination, timeout=0):
        # BRPOPLPUSH source destination timeout; 阻塞版 RPOPLPUSH
        return self.dbW.brpoplpush(source, destination, timeout)
    def lmove(self, first_list, second_list, src="LEFT", dest="RIGHT"):
        # [R6.2+] LMOVE source destination LEFT|RIGHT LEFT|RIGHT
        return self.dbW.lmove(first_list, second_list, src, dest)
    def blmove(self, first_list, second_list, timeout, src="LEFT", dest="RIGHT"):
        # [R6.2+] BLMOVE source destination LEFT|RIGHT LEFT|RIGHT timeout
        return self.dbW.blmove(first_list, second_list, timeout, src, dest)
    def lmpop(self, keys, direction="LEFT", count=1):
        # [R7.0+] LMPOP numkeys key [key ...] LEFT|RIGHT [COUNT n]
        return self.dbW.lmpop(len(keys), *keys, direction=direction.upper(), count=count)
    def blmpop(self, timeout, keys, direction="LEFT", count=1):
        # [R7.0+] BLMPOP timeout numkeys key [key ...] LEFT|RIGHT [COUNT n]
        return self.dbW.blmpop(timeout, len(keys), *keys, direction=direction.upper(), count=count)
    def lmovem(self, *args):
        # [R8.10+] LMOVEM; redis-py 6.4.0 无便捷方法, 薄透传
        return self.dbW.execute_command("LMOVEM", *args)
    def blmovem(self, *args):
        # [R8.10+] BLMOVEM; 薄透传
        return self.dbW.execute_command("BLMOVEM", *args)

    # ============================================================
    # Set 相关命令
    # redis的set是string类型的无序集合, 最大可含 2^32-1 个元素; 支持并集/交集/差集。
    # ============================================================
    def sadd(self, key, *members):
        # sadd key member [member ...] 添加元素, 返回新增个数; 支持多值
        return self.dbW.sadd(key, *members)
    def srem(self, key, *members):
        # srem key member [member ...] 移除元素, 返回移除个数; 支持多值
        return self.dbW.srem(key, *members)
    def spop(self, key, count=None):
        # spop key 删除并返回set中随机元素; [R3.2+] 可选 count
        if count is None:
            return self.dbW.spop(key)
        return self.dbW.spop(key, count)
    def srandmember(self, key, count=None):
        # srandmember key 随机取元素不删除; 可选 count
        if count is None:
            return self.dbR.srandmember(key)
        return self.dbR.srandmember(key, count)
    def smove(self, srckey, dstkey, member):
        # smove srckey dstkey member 原子地在集合间移动成员
        return self.dbW.smove(srckey, dstkey, member)
    def scard(self, key):
        # scard key 返回set的元素个数，如果set是空或者key不存在返回0
        return self.dbR.scard(key)
    def sismember(self, key, member):
        # sismember key member 判断member是否在set中，存在返回1，0表示不存在或者key不存在
        return self.dbR.sismember(key, member)
    def smismember(self, key, *members):
        # [R6.2+] SMISMEMBER key member [member ...]; 批量判断成员
        return self.dbR.execute_command("SMISMEMBER", key, *members)
    def sinter(self, *keys):
        # sinter key1 key2...keyN 返回所有给定key的交集
        return self.dbR.sinter(*keys)
    def sinterstore(self, dstkey, *keys):
        # sinterstore dstkey key1...keyN 同sinter，但是会同时将交集存到dstkey下
        return self.dbW.sinterstore(dstkey, *keys)
    def sintercard(self, keys, limit=0):
        # [R7.0+] SINTERCARD numkeys key [key ...] [LIMIT limit]
        return self.dbR.sintercard(len(keys), keys, limit=limit)
    def sunion(self, *keys):
        # sunion key1 key2...keyN 返回所有给定key的并集
        return self.dbR.sunion(*keys)
    def sunionstore(self, dstkey, *keys):
        # sunionstore dstkey key1...keyN 同sunion，并同时保存并集到dstkey下
        return self.dbW.sunionstore(dstkey, *keys)
    def sdiff(self, *keys):
        # sdiff key1 key2...keyN 返回所有给定key的差集
        return self.dbR.sdiff(*keys)
    def sdiffstore(self, dstkey, *keys):
        # sdiffstore dstkey key1...keyN 同sdiff，并同时保存差集到dstkey下
        return self.dbW.sdiffstore(dstkey, *keys)
    def smembers(self, key):
        # smembers key 返回key对应set的所有元素，结果是无序的
        return self.dbR.smembers(key)
    def sscan(self, key, cursor=0, match=None, count=None):
        # SSCAN key cursor [MATCH pattern] [COUNT count]
        return self.dbR.sscan(key, cursor, match, count)
    def sscan_iter(self, key, match=None, count=None):
        # SSCAN 游标增量迭代生成器; 阻塞式, 不可放入 pipeline
        return self.dbR.sscan_iter(key, match=match, count=count)
    def sunioncard(self, keys):
        # [R8.10+] SUNIONCARD numkeys key [key ...]; redis-py 6.4.0 无便捷方法, 走 execute_command
        return self.dbR.execute_command("SUNIONCARD", len(keys), *keys)
    def sdiffcard(self, keys):
        # [R8.10+] SDIFFCARD numkeys key [key ...]; redis-py 6.4.0 无便捷方法, 走 execute_command
        return self.dbR.execute_command("SDIFFCARD", len(keys), *keys)

    # ============================================================
    # Sorted set 相关命令
    # 每个元素关联一个 double 类型的 score, 按 score 有序。
    # ============================================================
    def zadd(self, key, score=None, member=None, mapping=None,
             nx=False, xx=False, ch=False, incr=False, gt=False, lt=False):
        # ZADD key [NX|XX] [GT|LT] [CH] [INCR] score member [...]
        # 原 zadd(key, score, member) 调用不变; GT/LT/INCR 需 [R6.2+]
        if mapping is None:
            mapping = {member: score}
        return self.dbW.zadd(key, mapping, nx=nx, xx=xx, ch=ch, incr=incr, gt=gt, lt=lt)
    def zrem(self, key, *members):
        # zrem key member [member ...] 删除元素, 返回删除个数; 支持多值
        return self.dbW.zrem(key, *members)
    def zincrby(self, key, incr, member):
        # zincrby key incr member 增加对应member的score值。返回更新后的score值
        return self.dbW.zincrby(key, incr, member)
    def zrank(self, key, member, withscore=False):
        # zrank key member 返回指定元素在集合中的排名(从小到大); [R7.2+] 可选 withscore
        return self.dbR.zrank(key, member, withscore)
    def zrevrank(self, key, member, withscore=False):
        # zrevrank key member 同上,但是集合中元素是按score从大到小排序; [R7.2+] 可选 withscore
        return self.dbR.zrevrank(key, member, withscore)
    def zrange(self, key, startScore, endScore):
        # zrange key start end 类似lrange操作从集合中取指定区间的元素。返回的是有序结果
        return self.dbR.zrange(key, startScore, endScore)
    def zrevrange(self, key, startScore, endScore):
        # zrevrange key start end 同上，返回结果是按score逆序的
        return self.dbR.zrevrange(key, startScore, endScore)
    def zrangebyscore(self, key, minScore, maxScore, start=None, num=None, withscores=False):
        # zrangebyscore key min max [WITHSCORES] [LIMIT offset count]
        return self.dbR.zrangebyscore(key, minScore, maxScore, start, num, withscores)
    def zrevrangebyscore(self, key, maxScore, minScore, start=None, num=None, withscores=False):
        # ZREVRANGEBYSCORE key max min [WITHSCORES] [LIMIT offset count]
        return self.dbR.zrevrangebyscore(key, maxScore, minScore, start, num, withscores)
    def zrangebylex(self, key, minLex, maxLex, start=None, num=None):
        # ZRANGEBYLEX key min max [LIMIT offset count]
        return self.dbR.zrangebylex(key, minLex, maxLex, start, num)
    def zrevrangebylex(self, key, maxLex, minLex, start=None, num=None):
        # ZREVRANGEBYLEX key max min [LIMIT offset count]
        return self.dbR.zrevrangebylex(key, maxLex, minLex, start, num)
    def zlexcount(self, key, minLex, maxLex):
        # ZLEXCOUNT key min max; 统计字典区间元素数
        return self.dbR.zlexcount(key, minLex, maxLex)
    def zremrangebylex(self, key, minLex, maxLex):
        # ZREMRANGEBYLEX key min max; 按字典区间删除
        return self.dbW.zremrangebylex(key, minLex, maxLex)
    def zcount(self, key, minScore, maxScore):
        # zcount key min max 返回集合中score在给定区间的数量
        return self.dbR.zcount(key, minScore, maxScore)
    def zcard(self, key):
        # zcard key 返回集合中元素个数
        return self.dbR.zcard(key)
    def zscore(self, key, element):
        # zscore key element  返回给定元素对应的score
        return self.dbR.zscore(key, element)
    def zmscore(self, key, *members):
        # [R6.2+] ZMSCORE key member [member ...]; 批量取 score
        return self.dbR.execute_command("ZMSCORE", key, *members)
    def zrandmember(self, key, count=None, withscores=False):
        # [R6.2+] ZRANDMEMBER key [count [WITHSCORES]]
        return self.dbR.zrandmember(key, count, withscores)
    def zpopmin(self, key, count=None):
        # [R5.0+] ZPOPMIN key [count]; 弹出最小 score 元素
        return self.dbW.zpopmin(key, count)
    def zpopmax(self, key, count=None):
        # [R5.0+] ZPOPMAX key [count]; 弹出最大 score 元素
        return self.dbW.zpopmax(key, count)
    def bzpopmin(self, keys, timeout=0):
        # [R5.0+] BZPOPMIN key [key ...] timeout; 阻塞版 ZPOPMIN
        return self.dbW.bzpopmin(keys, timeout)
    def bzpopmax(self, keys, timeout=0):
        # [R5.0+] BZPOPMAX key [key ...] timeout; 阻塞版 ZPOPMAX
        return self.dbW.bzpopmax(keys, timeout)
    def zunion(self, keys, aggregate=None, weights=None, withscores=False):
        # [R6.2+] ZUNION numkeys key [key ...] [WEIGHTS ...] [AGGREGATE SUM|MIN|MAX] [WITHSCORES]
        return self.dbR.zunion(keys, aggregate=aggregate, weights=weights, withscores=withscores)
    def zunionstore(self, dest, keys, aggregate=None, weights=None):
        # [R6.2+] ZUNIONSTORE destination numkeys key [key ...] [WEIGHTS ...] [AGGREGATE ...]
        return self.dbW.zunionstore(dest, keys, aggregate=aggregate, weights=weights)
    def zinter(self, keys, aggregate=None, weights=None, withscores=False):
        # [R6.2+] ZINTER numkeys key [key ...] [WEIGHTS ...] [AGGREGATE ...] [WITHSCORES]
        return self.dbR.zinter(keys, aggregate=aggregate, weights=weights, withscores=withscores)
    def zinterstore(self, dest, keys, aggregate=None, weights=None):
        # [R6.2+] ZINTERSTORE destination numkeys key [key ...] [WEIGHTS ...] [AGGREGATE ...]
        return self.dbW.zinterstore(dest, keys, aggregate=aggregate, weights=weights)
    def zdiff(self, keys, withscores=False):
        # [R6.2+] ZDIFF numkeys key [key ...] [WITHSCORES]
        return self.dbR.zdiff(keys, withscores=withscores)
    def zdiffstore(self, dest, keys):
        # [R6.2+] ZDIFFSTORE destination numkeys key [key ...]
        return self.dbW.zdiffstore(dest, keys)
    def zrangestore(self, dest, src, start, end, byscore=False, bylex=False,
                    desc=False, offset=None, num=None):
        # [R6.2+] ZRANGESTORE dst src min max [BYSCORE|BYLEX] [REV] [LIMIT offset count]
        return self.dbW.zrangestore(dest, src, start, end, byscore=byscore, bylex=bylex,
                                    desc=desc, offset=offset, num=num)
    def zintercard(self, keys, limit=0):
        # [R7.0+] ZINTERCARD numkeys key [key ...] [LIMIT limit]
        return self.dbR.zintercard(len(keys), keys, limit=limit)
    def zmpop(self, keys, min=False, max=False, count=1):
        # [R7.0+] ZMPOP numkeys key [key ...] MIN|MAX [COUNT count]; min/max 二选一
        return self.dbW.zmpop(len(keys), keys, min=min, max=max, count=count)
    def bzmpop(self, timeout, keys, min=False, max=False, count=1):
        # [R7.0+] BZMPOP timeout numkeys key [key ...] MIN|MAX [COUNT count]; min/max 二选一
        return self.dbW.bzmpop(timeout, len(keys), keys, min=min, max=max, count=count)
    def zremrangebyrank(self, key, minRank, maxRank):
        # zremrangebyrank key min max 删除集合中排名在给定区间的元素
        return self.dbW.zremrangebyrank(key, minRank, maxRank)
    def zremrangebyscore(self, key, minScore, maxScore):
        # zremrangebyscore key min max 删除集合中score在给定区间的元素
        return self.dbW.zremrangebyscore(key, minScore, maxScore)
    def zscan(self, key, cursor=0, match=None, count=None):
        # ZSCAN key cursor [MATCH pattern] [COUNT count]
        return self.dbR.zscan(key, cursor, match, count)
    def zscan_iter(self, key, match=None, count=None):
        # ZSCAN 游标增量迭代生成器; 阻塞式, 不可放入 pipeline
        return self.dbR.zscan_iter(key, match=match, count=count)

    # ============================================================
    # Hash 相关命令
    # redis hash 是 string 类型的 field 和 value 的映射表, 适合存储对象。
    # ============================================================
    def hset(self, key, field=None, value=None, mapping=None):
        # hset key field value 设置hash field为指定值; 也支持 mapping 多字段写法
        if mapping is not None:
            return self.dbW.hset(key, mapping=mapping)
        return self.dbW.hset(key, field, value)
    def hget(self, key, field):
        # hget key field  获取指定的hash field
        return self.dbR.hget(key, field)
    def hmget(self, key, *fileds):
        # hmget key field1....fieldN 获取全部指定的hash field
        return self.dbR.hmget(key, *fileds)
    def hmset(self, key, mapping):
        # [alias] HMSET 自 Redis 4.0 起废弃; 内部改 HSET 多字段写法(redis-py 推荐)
        # 注意: HSET 返回新增字段数, 为保持旧 HMSET 语义此处统一返回 True
        self.dbW.hset(key, mapping=mapping)
        return True
    def hsetnx(self, key, field, value):
        # HSETNX key field value; field 不存在时才设置
        return self.dbW.hsetnx(key, field, value)
    def hincrby(self, key, field, integer):
        # hincrby key field integer 将指定的hash field 加上给定值
        return self.dbW.hincrby(key, field, integer)
    def hincrbyfloat(self, key, field, amount):
        # [R2.6+] HINCRBYFLOAT key field increment; 浮点自增
        return self.dbW.hincrbyfloat(key, field, amount)
    def hexists(self, key, field):
        # hexists key field 测试指定field是否存在
        return self.dbR.hexists(key, field)
    def hdel(self, key, *fields):
        # hdel key field [field ...] 删除指定的hash field; 支持多字段
        return self.dbW.hdel(key, *fields)
    def hlen(self, key):
        # hlen key 返回指定hash的field数量
        return self.dbR.hlen(key)
    def hstrlen(self, key, field):
        # [R3.2+] HSTRLEN key field; field 值长度
        return self.dbR.hstrlen(key, field)
    def hkeys(self, key):
        # hkeys key 返回hash的所有field
        return self.dbR.hkeys(key)
    def hvals(self, key):
        # hvals key 返回hash的所有value
        return self.dbR.hvals(key)
    def hgetall(self, key):
        # hgetall 返回hash的所有field和value
        return self.dbR.hgetall(key)
    def hrandfield(self, key, count=None, withvalues=False):
        # [R6.2+] HRANDFIELD key [count [WITHVALUES]]
        return self.dbR.hrandfield(key, count, withvalues)
    def hscan(self, key, cursor=0, match=None, count=None):
        # HSCAN key cursor [MATCH pattern] [COUNT count]
        return self.dbR.hscan(key, cursor, match, count)
    def hscan_iter(self, key, match=None, count=None):
        # HSCAN 游标增量迭代生成器; 阻塞式, 不可放入 pipeline
        return self.dbR.hscan_iter(key, match=match, count=count)
    def hexpire(self, key, seconds, *fields, **kwargs):
        # [R7.4+] HEXPIRE key seconds [NX|XX|GT|LT] FIELDS numfields field [...]; 字段级过期
        return self.dbW.hexpire(key, seconds, *fields, **kwargs)
    def hpexpire(self, key, milliseconds, *fields, **kwargs):
        # [R7.4+] HPEXPIRE key milliseconds [NX|XX|GT|LT] FIELDS numfields field [...]
        return self.dbW.hpexpire(key, milliseconds, *fields, **kwargs)
    def hexpireat(self, key, when, *fields, **kwargs):
        # [R7.4+] HEXPIREAT key unix-time-seconds [NX|XX|GT|LT] FIELDS numfields field [...]
        return self.dbW.hexpireat(key, when, *fields, **kwargs)
    def hpexpireat(self, key, when, *fields, **kwargs):
        # [R7.4+] HPEXPIREAT key unix-time-milliseconds [NX|XX|GT|LT] FIELDS numfields field [...]
        return self.dbW.hpexpireat(key, when, *fields, **kwargs)
    def hexpiretime(self, key, *fields):
        # [R7.4+] HEXPIRETIME key FIELDS numfields field [...]; 返回绝对过期时间戳(秒)
        return self.dbR.hexpiretime(key, *fields)
    def hpexpiretime(self, key, *fields):
        # [R7.4+] HPEXPIRETIME key FIELDS numfields field [...]
        return self.dbR.hpexpiretime(key, *fields)
    def httl(self, key, *fields):
        # [R7.4+] HTTL key FIELDS numfields field [...]
        return self.dbR.httl(key, *fields)
    def hpttl(self, key, *fields):
        # [R7.4+] HPTTL key FIELDS numfields field [...]
        return self.dbR.hpttl(key, *fields)
    def hpersist(self, key, *fields):
        # [R7.4+] HPERSIST key FIELDS numfields field [...]; 移除字段级过期
        return self.dbW.hpersist(key, *fields)
    def hgetdel(self, key, *fields):
        # [R8.0+] HGETDEL key FIELDS numfields field [...]; 字段级取值并删除
        return self.dbW.execute_command("HGETDEL", key, "FIELDS", len(fields), *fields)
    def hgetex(self, key, *fields, **kwargs):
        # [R8.0+] HGETEX key [EX|PX|EXAT|PXAT|PERSIST] FIELDS numfields field [...]
        # 参数透传: ex/px/exat/pxat/persist 见 doc/redisCommandCoverage.md
        return self.dbW.hgetex(key, *fields, **kwargs)
    def hsetex(self, key, **kwargs):
        # [R8.0+] HSETEX key [EX|PX|EXAT|PXAT|KEEPTTL] [FNX|FXX] FIELDS numfields field value [...]
        # 参数透传: key/value/mapping/items/ex/px/exat/pxat/data_persist_option/keepttl
        return self.dbW.hsetex(key, **kwargs)

    # ============================================================
    # Streams 相关命令 [R5.0+]
    # ============================================================
    def xadd(self, key, fields, id="*", maxlen=None, approximate=True,
             nomkstream=False, minid=None, limit=None):
        # XADD key [NOMKSTREAM] [MAXLEN|MINID [=|~] threshold [LIMIT count]] *|id field value [...]
        return self.dbW.xadd(key, fields, id=id, maxlen=maxlen, approximate=approximate,
                             nomkstream=nomkstream, minid=minid, limit=limit)
    def xlen(self, key):
        # XLEN key; 流长度
        return self.dbR.xlen(key)
    def xrange(self, key, min="-", max="+", count=None):
        # XRANGE key start end [COUNT count]
        return self.dbR.xrange(key, min=min, max=max, count=count)
    def xrevrange(self, key, max="+", min="-", count=None):
        # XREVRANGE key end start [COUNT count]
        return self.dbR.xrevrange(key, max=max, min=min, count=count)
    def xdel(self, key, *ids):
        # XDEL key ID [ID ...]; 删除消息
        return self.dbW.xdel(key, *ids)
    def xtrim(self, key, maxlen=None, approximate=True, minid=None, limit=None):
        # XTRIM key MAXLEN|MINID [=|~] threshold [LIMIT count]
        return self.dbW.xtrim(key, maxlen=maxlen, approximate=approximate,
                              minid=minid, limit=limit)
    def xread(self, streams, count=None, block=None):
        # XREAD [COUNT count] [BLOCK ms] STREAMS key [key ...] id [id ...]
        return self.dbR.xread(streams, count=count, block=block)
    def xreadgroup(self, groupname, consumername, streams, count=None, block=None, noack=False):
        # XREADGROUP GROUP group consumer [COUNT count] [BLOCK ms] [NOACK] STREAMS key [...] id [...]
        return self.dbW.xreadgroup(groupname, consumername, streams,
                                   count=count, block=block, noack=noack)
    def xack(self, key, groupname, *ids):
        # XACK key group ID [ID ...]; 确认消息
        return self.dbW.xack(key, groupname, *ids)
    def xpending(self, key, groupname, start=None, end=None, count=None,
                 consumername=None, idle=None):
        # XPENDING key group [[IDLE min-idle-time] start end count [consumer]]
        return self.dbR.xpending(key, groupname, start=start, end=end, count=count,
                                 consumername=consumername, idle=idle)
    def xpending_range(self, key, groupname, start=None, end=None, count=None,
                       consumername=None, idle=None):
        # XPENDING 扩展形式(明细); redis-py 6.4 便捷方法
        return self.dbR.xpending_range(key, groupname, start=start, end=end, count=count,
                                       consumername=consumername, idle=idle)
    def xgroup_create(self, key, groupname, id="$", mkstream=False, entries_read=None):
        # XGROUP CREATE key group id|$ [MKSTREAM] [ENTRIESREAD n]
        return self.dbW.xgroup_create(key, groupname, id=id, mkstream=mkstream,
                                      entries_read=entries_read)
    def xgroup_destroy(self, key, groupname):
        # XGROUP DESTROY key group
        return self.dbW.xgroup_destroy(key, groupname)
    def xgroup_setid(self, key, groupname, id, entries_read=None):
        # XGROUP SETID key group id|$ [ENTRIESREAD n]
        return self.dbW.xgroup_setid(key, groupname, id=id, entries_read=entries_read)
    def xgroup_delconsumer(self, key, groupname, consumername):
        # XGROUP DELCONSUMER key group consumer
        return self.dbW.xgroup_delconsumer(key, groupname, consumername)
    def xgroup_createconsumer(self, key, groupname, consumername):
        # [R6.2+] XGROUP CREATECONSUMER key group consumer
        return self.dbW.xgroup_createconsumer(key, groupname, consumername)
    def xclaim(self, key, groupname, consumername, min_idle_time, message_ids,
               idle=None, time=None, retrycount=None, force=False, justid=False):
        # XCLAIM key group consumer min-idle-time ID [...] [IDLE ms] [TIME ts] [RETRYCOUNT n] [FORCE] [JUSTID]
        return self.dbW.xclaim(key, groupname, consumername, min_idle_time, message_ids,
                               idle=idle, time=time, retrycount=retrycount,
                               force=force, justid=justid)
    def xautoclaim(self, key, groupname, consumername, min_idle_time,
                   start_id="0-0", count=None, justid=False):
        # [R6.2+] XAUTOCLAIM key group consumer min-idle-time start [COUNT count] [JUSTID]
        return self.dbW.xautoclaim(key, groupname, consumername, min_idle_time,
                                   start_id=start_id, count=count, justid=justid)
    def xinfo_stream(self, key, full=False):
        # XINFO STREAM key [FULL [COUNT count]]
        return self.dbR.xinfo_stream(key, full=full)
    def xinfo_groups(self, key):
        # XINFO GROUPS key
        return self.dbR.xinfo_groups(key)
    def xinfo_consumers(self, key, groupname):
        # XINFO CONSUMERS key group
        return self.dbR.xinfo_consumers(key, groupname)
    def xackdel(self, key, groupname, *ids, **kwargs):
        # [R8.2+] XACKDEL key group [KEEPREF|DELREF|ACKED] ID [...]; redis-py 6.4 便捷方法
        return self.dbW.xackdel(key, groupname, *ids, **kwargs)
    def xdelex(self, key, *ids, **kwargs):
        # [R8.2+] XDELEX key [KEEPREF|DELREF|ACKED] ID [...]; redis-py 6.4 便捷方法
        return self.dbW.xdelex(key, *ids, **kwargs)
    def xcfgset(self, *args):
        # [R8.6+] XCFGSET key [IDMP-DURATION s] [IDMP-MAXLEN n]; 薄透传
        return self.dbW.execute_command("XCFGSET", *args)
    def xnack(self, *args):
        # [R8.8+] XNACK; 薄透传
        return self.dbW.execute_command("XNACK", *args)

    # ============================================================
    # Bitmap / HyperLogLog / Geo
    # ============================================================
    def setbit(self, key, offset, value):
        # [R2.6+] SETBIT key offset value; 位图置位, 返回旧位值
        return self.dbW.setbit(key, offset, value)
    def getbit(self, key, offset):
        # [R2.6+] GETBIT key offset
        return self.dbR.getbit(key, offset)
    def bitcount(self, key, start=None, end=None, mode=None):
        # [R2.6+] BITCOUNT key [start end [BYTE|BIT]]
        return self.dbR.bitcount(key, start, end, mode)
    def bitop(self, operation, dest, *keys):
        # [R2.6+] BITOP AND|OR|XOR|NOT destkey key [key ...]
        return self.dbW.bitop(operation, dest, *keys)
    def bitpos(self, key, bit, start=None, end=None, mode=None):
        # [R2.8.7+] BITPOS key bit [start [end [BYTE|BIT]]]
        return self.dbR.bitpos(key, bit, start, end, mode)
    def bitfield(self, key, *args):
        # [R3.2+] BITFIELD key [GET|SET|INCRBY|OVERFLOW ...]; 薄透传
        return self.dbW.execute_command("BITFIELD", key, *args)
    def bitfield_ro(self, key, *args):
        # [R6.0+] BITFIELD_RO key GET encoding offset [...]; 只读, 归 dbR
        return self.dbR.execute_command("BITFIELD_RO", key, *args)
    def pfadd(self, key, *values):
        # [R2.8.9+] PFADD key [element [element ...]]; HyperLogLog 基数估计
        return self.dbW.pfadd(key, *values)
    def pfcount(self, *keys):
        # [R2.8.9+] PFCOUNT key [key ...]
        return self.dbR.pfcount(*keys)
    def pfmerge(self, dest, *sourcekeys):
        # [R2.8.9+] PFMERGE destkey [sourcekey ...]
        return self.dbW.pfmerge(dest, *sourcekeys)
    def geoadd(self, key, values, nx=False, xx=False, ch=False):
        # [R3.2+] GEOADD key [NX|XX] [CH] longitude latitude member [...]
        return self.dbW.geoadd(key, values, nx=nx, xx=xx, ch=ch)
    def geopos(self, key, *members):
        # [R3.2+] GEOPOS key member [member ...]
        return self.dbR.geopos(key, *members)
    def geodist(self, key, place1, place2, unit=None):
        # [R3.2+] GEODIST key member1 member2 [M|KM|FT|MI]
        return self.dbR.geodist(key, place1, place2, unit)
    def geohash(self, key, *members):
        # [R3.2+] GEOHASH key member [member ...]
        return self.dbR.geohash(key, *members)
    def georadius(self, *args, **kwargs):
        # [R3.2+] GEORADIUS key ... (R7.0 起不推荐, 建议 GEOSEARCH); 可带 STORE 归 dbW
        return self.dbW.georadius(*args, **kwargs)
    def georadiusbymember(self, *args, **kwargs):
        # [R3.2+] GEORADIUSBYMEMBER key member ... (R7.0 起不推荐, 建议 GEOSEARCH)
        return self.dbW.georadiusbymember(*args, **kwargs)
    def geosearch(self, *args, **kwargs):
        # [R6.2+] GEOSEARCH key ...; 统一的地理搜索
        return self.dbR.geosearch(*args, **kwargs)
    def geosearchstore(self, *args, **kwargs):
        # [R6.2+] GEOSEARCHSTORE destination source ...
        return self.dbW.geosearchstore(*args, **kwargs)

    # ============================================================
    # 事务 / 管道
    # ============================================================
    def pipeline(self, transaction=True, shard_hint=None):
        # 返回事务型(transaction=True, MULTI/EXEC)或普通命令缓冲管道
        return self.dbW.pipeline(transaction=transaction, shard_hint=shard_hint)
    def watch(self, *keys):
        # [R2.2+] WATCH key [key ...]; 乐观锁监视
        return self.dbW.watch(*keys)
    def unwatch(self):
        # UNWATCH; 取消监视
        return self.dbW.unwatch()
    def transaction(self, func, *watches, **kwargs):
        # 回调式事务: 内部执行 MULTI/EXEC
        return self.dbW.transaction(func, *watches, **kwargs)
    def multi(self):
        # MULTI/EXEC 语义: 返回事务型管道, execute() 触发 EXEC, reset() 等价 DISCARD
        return self.dbW.pipeline(transaction=True)
    def execute_command(self, *args, **kwargs):
        # 原生命令透传(写库); 用于 redis-py 未封装的服务端命令
        return self.dbW.execute_command(*args, **kwargs)

    # ============================================================
    # 发布订阅
    # 注意: subscribe/psubscribe/ssubscribe 返回的 PubSub 对象独占连接,
    #       不能复用执行普通命令, 也不能放入 pipeline。
    # ============================================================
    def subscribe(self, *channel):
        # SUBSCRIBE channel [channel ...]; [恢复] 原代码被注释
        return self.dbW.pubsub().subscribe(*channel)
    def unsubscribe(self, *channel):
        # UNSUBSCRIBE [channel [channel ...]]; [恢复] 原代码被注释
        return self.dbW.pubsub().unsubscribe(*channel)
    def psubscribe(self, *pattern):
        # [修复 B1] redis.Redis 无 psubscribe 方法, 必须经 pubsub() 返回的 PubSub 对象
        return self.dbW.pubsub().psubscribe(*pattern)
    def punsubscribe(self, *pattern):
        # [修复 B2] 同上, 必须经 PubSub 对象
        return self.dbW.pubsub().punsubscribe(*pattern)
    def pubsub(self, **kwargs):
        # [修复 B3] redis-py 签名为 pubsub(**kwargs), 不接受位置参数
        return self.dbW.pubsub(**kwargs)
    def publish(self, channel, message):
        # PUBLISH channel message 将信息发送到指定的频道。
        return self.dbW.publish(channel, message)
    def pubsub_channels(self, *args):
        # PUBSUB CHANNELS [pattern]; 查看活跃频道
        return self.dbR.pubsub_channels(*args)
    def pubsub_numsub(self, *args):
        # PUBSUB NUMSUB [channel ...]; 查看频道订阅数
        return self.dbR.pubsub_numsub(*args)
    def pubsub_numpat(self):
        # PUBSUB NUMPAT; 查看模式订阅数
        return self.dbR.pubsub_numpat()
    def spublish(self, channel, message):
        # [R7.0+] SPUBLISH shardchannel message; 分片发布
        return self.dbW.spublish(channel, message)
    def ssubscribe(self, *channel):
        # [R7.0+] SSUBSCRIBE shardchannel [shardchannel ...]; 分片订阅(独占连接)
        return self.dbW.pubsub().ssubscribe(*channel)
    def sunsubscribe(self, *channel):
        # [R7.0+] SUNSUBSCRIBE [shardchannel [shardchannel ...]]
        return self.dbW.pubsub().sunsubscribe(*channel)
    def pubsub_shardchannels(self, *args):
        # [R7.0+] PUBSUB SHARDCHANNELS [pattern]
        return self.dbR.pubsub_shardchannels(*args)
    def pubsub_shardnumsub(self, *args):
        # [R7.0+] PUBSUB SHARDNUMSUB [shardchannel ...]
        return self.dbR.pubsub_shardnumsub(*args)
    def get_message(self, pubsubObj, timeout=0):
        # 从订阅对象取一条消息; timeout=0 表示非阻塞
        if timeout:
            return pubsubObj.get_message(timeout=timeout)
        return pubsubObj.get_message()
    def get_sharded_message(self, pubsubObj, timeout=0):
        # [R7.0+] 从分片订阅对象取一条消息; timeout=0 表示非阻塞
        if timeout:
            return pubsubObj.get_sharded_message(timeout=timeout)
        return pubsubObj.get_sharded_message()

    # ============================================================
    # 脚本与函数
    # ============================================================
    def eval(self, script, numkeys, *keys_and_args):
        # [R2.6+] EVAL script numkeys key [key ...] arg [arg ...]; 归 dbW
        return self.dbW.eval(script, numkeys, *keys_and_args)
    def evalsha(self, sha, numkeys, *keys_and_args):
        # [R2.6+] EVALSHA sha1 numkeys key [key ...] arg [arg ...]; 归 dbW
        return self.dbW.evalsha(sha, numkeys, *keys_and_args)
    def eval_ro(self, script, numkeys, *keys_and_args):
        # [R7.0+] EVAL_RO ...; 只读, 归 dbR
        return self.dbR.eval_ro(script, numkeys, *keys_and_args)
    def evalsha_ro(self, sha, numkeys, *keys_and_args):
        # [R7.0+] EVALSHA_RO ...; 只读, 归 dbR
        return self.dbR.evalsha_ro(sha, numkeys, *keys_and_args)
    def script_load(self, script):
        # SCRIPT LOAD script; 返回 sha1
        return self.dbW.script_load(script)
    def script_exists(self, *shas):
        # SCRIPT EXISTS sha1 [sha1 ...]; 归 dbR
        return self.dbR.script_exists(*shas)
    def script_flush(self, *args):
        # SCRIPT FLUSH [ASYNC|SYNC]
        return self.dbW.script_flush(*args)
    def script_kill(self):
        # SCRIPT KILL; 终止正在运行的脚本
        return self.dbW.script_kill()
    def script_debug(self, mode):
        # [R3.2+] SCRIPT DEBUG YES|SYNC|NO
        return self.dbW.script_debug(mode)
    def register_script(self, script):
        # 返回可复用的 redis.client.Script 对象(内部缓存 sha1)
        return self.dbW.register_script(script)
    def fcall(self, func, numkeys, *keys_and_args):
        # [R7.0+] FCALL function numkeys key [key ...] arg [arg ...]
        return self.dbW.fcall(func, numkeys, *keys_and_args)
    def fcall_ro(self, func, numkeys, *keys_and_args):
        # [R7.0+] FCALL_RO ...; 只读, 归 dbR
        return self.dbR.fcall_ro(func, numkeys, *keys_and_args)
    def function_load(self, code, replace=False):
        # [R7.0+] FUNCTION LOAD [REPLACE] function-code
        return self.dbW.function_load(code, replace=replace)
    def function_delete(self, library_name):
        # [R7.0+] FUNCTION DELETE library-name
        return self.dbW.function_delete(library_name)
    def function_flush(self, *args):
        # [R7.0+] FUNCTION FLUSH [ASYNC|SYNC]
        return self.dbW.function_flush(*args)
    def function_list(self, library_name=None, withcode=False):
        # [R7.0+] FUNCTION LIST [LIBRARYNAME name] [WITHCODE]; 归 dbR
        return self.dbR.function_list(library_name=library_name, withcode=withcode)
    def function_dump(self):
        # [R7.0+] FUNCTION DUMP; 归 dbR
        return self.dbR.function_dump()
    def function_restore(self, payload, policy=None):
        # [R7.0+] FUNCTION RESTORE serialized-value [FLUSH|APPEND|REPLACE]
        return self.dbW.function_restore(payload, policy=policy)
    def function_kill(self):
        # [R7.0+] FUNCTION KILL
        return self.dbW.function_kill()
    def function_stats(self):
        # [R7.0+] FUNCTION STATS; 归 dbR
        return self.dbR.function_stats()

    # ============================================================
    # 服务器管理
    # ============================================================
    def save(self):
        # save 人工保存数据到硬盘
        return self.dbW.save()
    def bgsave(self, schedule=True):
        # BGSAVE [SCHEDULE]; 后台异步存盘
        return self.dbW.bgsave(schedule=schedule)
    def bgrewriteaof(self):
        # BGREWRITEAOF; 后台重写 AOF
        return self.dbW.bgrewriteaof()
    def lastsave(self):
        # LASTSAVE; 上次成功存盘的 unix 时间戳
        return self.dbR.lastsave()
    def shutdown(self, save=False, nosave=False, now=False, force=False, abort=False):
        # SHUTDOWN [NOSAVE|SAVE] [NOW] [FORCE] [ABORT]; 高危, 慎用
        return self.dbW.shutdown(save=save, nosave=nosave, now=now, force=force, abort=abort)
    def time(self):
        # TIME; 返回服务端 [秒, 微秒]
        return self.dbW.time()
    def debug_object(self, key):
        # DEBUG OBJECT key; 调试用
        return self.dbR.execute_command("DEBUG", "OBJECT", key)
    def slowlog_get(self, num=None):
        # SLOWLOG GET [count]
        return self.dbR.slowlog_get(num)
    def slowlog_len(self):
        # SLOWLOG LEN
        return self.dbR.slowlog_len()
    def slowlog_reset(self):
        # SLOWLOG RESET
        return self.dbW.slowlog_reset()
    def migrate(self, *args, **kwargs):
        # MIGRATE host port key destination-db timeout [COPY] [REPLACE] [AUTH pw]; 薄透传
        return self.dbW.migrate(*args, **kwargs)
    def monitor(self):
        # MONITOR; 返回实时命令流对象(独占连接), 调试用
        return self.dbW.monitor()
    def lolwut(self, *args, **kwargs):
        # LOLWUT [VERSION ...]; 打印彩蛋版本信息
        return self.dbR.lolwut(*args, **kwargs)

    # ============================================================
    # Array 数据结构 [R8.8+] (实验性; redis-py 6.4.0 无封装, 全部薄透传)
    # ============================================================
    def arcount(self, key, *args):
        # [R8.8+] ARCOUNT key [...]; 实验性
        return self.dbR.execute_command("ARCOUNT", key, *args)
    def ardel(self, key, *args):
        # [R8.8+] ARDEL key [...]; 实验性
        return self.dbW.execute_command("ARDEL", key, *args)
    def ardelrange(self, key, *args):
        # [R8.8+] ARDELRANGE key [...]; 实验性
        return self.dbW.execute_command("ARDELRANGE", key, *args)
    def arget(self, key, *args):
        # [R8.8+] ARGET key [...]; 实验性
        return self.dbR.execute_command("ARGET", key, *args)
    def argetrange(self, key, *args):
        # [R8.8+] ARGETRANGE key [...]; 实验性
        return self.dbR.execute_command("ARGETRANGE", key, *args)
    def argrep(self, key, *args):
        # [R8.8+] ARGREP key [...]; 实验性
        return self.dbR.execute_command("ARGREP", key, *args)
    def arinfo(self, key, *args):
        # [R8.8+] ARINFO key [...]; 实验性
        return self.dbR.execute_command("ARINFO", key, *args)
    def arinsert(self, key, *args):
        # [R8.8+] ARINSERT key [...]; 实验性
        return self.dbW.execute_command("ARINSERT", key, *args)
    def arlastitems(self, key, *args):
        # [R8.8+] ARLASTITEMS key [...]; 实验性
        return self.dbR.execute_command("ARLASTITEMS", key, *args)
    def arlen(self, key, *args):
        # [R8.8+] ARLEN key [...]; 实验性
        return self.dbR.execute_command("ARLEN", key, *args)
    def armget(self, key, *args):
        # [R8.8+] ARMGET key [...]; 实验性
        return self.dbR.execute_command("ARMGET", key, *args)
    def armset(self, key, *args):
        # [R8.8+] ARMSET key [...]; 实验性
        return self.dbW.execute_command("ARMSET", key, *args)
    def arnext(self, key, *args):
        # [R8.8+] ARNEXT key [...]; 实验性
        return self.dbW.execute_command("ARNEXT", key, *args)
    def arop(self, key, *args):
        # [R8.8+] AROP key [...]; 实验性
        return self.dbW.execute_command("AROP", key, *args)
    def arring(self, key, *args):
        # [R8.8+] ARRING key [...]; 实验性
        return self.dbW.execute_command("ARRING", key, *args)
    def arscan(self, key, *args):
        # [R8.8+] ARSCAN key [...]; 实验性
        return self.dbR.execute_command("ARSCAN", key, *args)
    def arseek(self, key, *args):
        # [R8.8+] ARSEEK key [...]; 实验性
        return self.dbW.execute_command("ARSEEK", key, *args)
    def arset(self, key, *args):
        # [R8.8+] ARSET key [...]; 实验性
        return self.dbW.execute_command("ARSET", key, *args)


class PipeHandle(RedisHandle):
    def __init__(self, redisHandle, transaction=True):
        #输入redis db对象
        # transaction=True 时 EXEC 原子提交; False 时仅命令缓冲批量发送
        self.dbW = redisHandle.dbW.pipeline(transaction=transaction)
        self.dbR = self.dbW

    def execute(self):
        return self.dbW.execute()

    def reset(self):
        # 丢弃缓冲, 等价 DISCARD
        return self.dbW.reset()


if __name__ == "__main__":
    dbW = getRedisDB(host="127.0.0.1",port=16379,db=15)
    dbR = getRedisDB(host="127.0.0.1",port=16379,db=15)
    redisDB = RedisHandle(dbW=dbW,dbR=dbR)
    pipeHandle = PipeHandle(redisDB)
    print (dbW)
    print (dbR)
    print (redisDB)
    print (pipeHandle)

    # 订阅示例: PubSub 对象独占连接, 需循环 get_message 取消息
    # pubsubObj = redisDB.pubsub()
    # pubsubObj.subscribe("ch_demo")
    # while True:
    #     message = redisDB.get_message(pubsubObj, timeout=1)
    #     if message:
    #         print(message)

    # 反射自测: 核对封装依赖的 redis-py 方法是否存在(重点 B1/B2/B3 修复点)
    dependMethods = ["pubsub", "publish", "pubsub_channels", "pubsub_numsub", "spublish",
                     "set", "getrange", "setnx", "hset", "hexpire", "xadd", "geoadd"]
    missing = [m for m in dependMethods if not hasattr(dbW, m)]
    print ("redis-py missing methods:", missing)

