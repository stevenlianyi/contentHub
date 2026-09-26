#!/usr/bin/env bash
#encoding: utf-8
#
#Filename: env_export.sh
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-23
#Description:   contentHub(内容中枢) 关键参数环境变量导出脚本。
#
#背景(主计划 R-19「口令/密钥不落代码库」):
#  config/ 下多处配置一律「环境变量优先」——敏感值(数据库口令、公众号凭据、
#  凭据加密主密钥)不写死在代码里, 由部署/运行环境注入。本脚本即「注入入口」,
#  集中导出这些变量, 避免逐个手工 export 或散落在各启动脚本中。
#
#★ 本代码库为私人 SVN 管理, 安全性有保证, 故允许在此登记环境变量取值;
#  但仍遵循两条红线:
#    1) 任何真实密钥只在此文件出现一次(SVN 私有), 不复制进业务代码;
#    2) 若无密钥, 变量留空即可 —— 程序按「未配置」安全降级(如 CH_CREDENTIAL_KEY
#       为空时投递链路返回 F0 并拒绝落库, 不会崩溃、不会明文落库)。
#
#★ 用法(必须 source, 才能影响当前 shell; 直接 bash 执行仅打印提示):
#     source /data/contenthub/doc/env_export.sh
#  或在启动脚本/守护进程前一行:
#     . /data/contenthub/doc/env_export.sh && /data/userbin/python3/bin/gunicorn ...
#
#★ 首次使用如提示权限不足(Windows 同步过来可能丢失可执行位):
#     chmod +x /data/contenthub/doc/env_export.sh
#
#变量登记依据(改代码时请同步本文件):
#  code/src/config/mysqlSettings.py      -> CH_MYSQL_WRITE_PASSWD / CH_MYSQL_READ_PASSWD / MYSQL_SKIP_CONNECT
#  code/src/config/wechatSettings.py     -> CH_WECHAT_APPID / APPSECRET / TOKEN / AESKEY / AUTO_PUBLISH
#  code/src/common/credentialCipher.py   -> CH_CREDENTIAL_KEY
#  code/src/config/mcpConfig.py          -> CONTENTHUB_SESSION_ID / MCP_AUTH_ISSUER_URL / MCP_AUTH_RESOURCE_SERVER_URL
#  code/src/schedule/renderWorker.py     -> CH_RENDER_WORKER_INTERVAL / CH_RENDER_WORKER_LIMIT
#  code/src/schedule/credentialCheck.py  -> CH_CREDENTIAL_EXPIRE_WARN_DAYS / CH_CREDENTIAL_CHECK_INTERVAL
#  code/src/config/opsSettings.py        -> CH_ARCHIVE_* / CH_OPS_ACTOR_LOGINID / CH_MONITOR_*


#=====================================================================
# 1. MySQL 数据库口令(mysqlSettings.py)
#    MYSQL_WRITE_HOST/USER/DB 等非敏感项仍由代码按 _SYS 决定, 此处只注入口令。
#=====================================================================

#写库口令(不设则回落到代码内开发默认值; 线上必须显式注入)
export CH_MYSQL_WRITE_PASSWD='your_password'

#读库口令(不设则回落写库口令; 读写同库时可不设)
export CH_MYSQL_READ_PASSWD='your_password'

#★ 仅在「无数据库环境」时开启(渲染 worker / MCP / CI 静态检查等无需直连库的进程):
#   置 1 后导入 mysqlSettings 不建连(mysqlDB=None), 避免导入期阻塞或失败。
#   ★ 有数据库的正常部署请保持「不导出本变量」(默认即建连)。
#export MYSQL_SKIP_CONNECT=1


#=====================================================================
# 2. 凭据加密主密钥(common/credentialCipher.py, AES-256-GCM)
#    ★ 用于 ch_account 中公众号 AppSecret 的加密/解密; 明文与密钥永不落库。
#    支持格式(按序尝试, 命中 32 字节即采用):
#      ① 64 位十六进制串  ② base64(32 字节)  ③ 32 字节原文  ④ >=16 字节口令(sha256 派生)
#    ★ 一旦有存量加密数据, 本密钥不可变更, 否则历史凭据无法解密。
#    生成示例: python3 -c "import secrets; print(secrets.token_hex(32))"
#=====================================================================

#★ 本机默认密钥(64 位 hex = 32 字节随机值, 按格式①命中直用)。
#★ 红线: 一旦 ch_account 内有存量加密凭据, 本值不可再变更, 否则历史凭据将无法解密(F0);
#   多环境(server_01/server_02/test_server/home)如需共享同一批账号凭据, 必须取同一值。
export CH_CREDENTIAL_KEY='your_securet'


#=====================================================================
# 3. 微信公众号凭据(wechatSettings.py)
#    ★★ 2026-09-24 口径变更(凭据来源收口): 公众号 AppID / AppSecret **不再从环境变量获取**,
#       业务链路(processor/publishService.py::decryptAccountCredential)已取消环境变量兜底。
#       平台凭据由用户在「第三方账号管理」(/my-accounts, 或管理员「账号管理」/accounts) 页录入,
#       经服务端 AES-256-GCM 加密写入 ch_account.credentialCipher / credentialIV(明文不落库、不回显)。
#       → 下方两个变量**仅为兼容保留**(常量仍在, 但不再作为凭据来源); 未录入凭据的账号在
#         巡检/投递时会显式返回 F0 并引导到页面录入(不静默降级)。
#    ★ 真正必须由环境变量注入的是第 2 节的**加密主密钥 CH_CREDENTIAL_KEY**(密钥不入库、不入代码库)。
#=====================================================================

#★ 已废弃为凭据来源(保留占位): 服务号/订阅号 AppID  → 改由 ch_account.appID 维护
export CH_WECHAT_APPID=''

#★ 已废弃为凭据来源(保留占位): 服务号/订阅号 AppSecret → 改由账号页录入并加密落库
export CH_WECHAT_APPSECRET=''

#★ 待填写: 服务器配置 Token(接收平台事件回调时校验用)
export CH_WECHAT_TOKEN=''

#★ 待填写: 消息加解密 EncodingAESKey
export CH_WECHAT_AESKEY=''

#正式发布(freepublish/submit)总开关: "1"=允许(仍需三条件同时满足), 缺省/其他=关闭
#★ 红线: 默认关闭, 开启需人工二次确认, 故此处默认注释掉。
#export CH_WECHAT_AUTO_PUBLISH='0'


#=====================================================================
# 4. MCP 服务(mcpConfig.py)
#=====================================================================

#contentHub REST 服务默认会话 sessionID(MCP 调用 /chapi 时的默认鉴权会话)
#注: 与 basicSettings.CH_API_SESSIONID 同源, 便于本地/服务间联调。
export CONTENTHUB_SESSION_ID='your_token'

#MCP OAuth 占位地址(无 auth_server_provider 时不触发 OAuth 流程; 缺省即下方取值, 可按需覆盖)
export MCP_AUTH_ISSUER_URL='http://127.0.0.1:8891'
export MCP_AUTH_RESOURCE_SERVER_URL='http://127.0.0.1:8891'


#=====================================================================
# 5. 渲染 worker(schedule/renderWorker.py)
#    不设则使用代码默认值(兜底轮询周期/单轮消费上限), 可按机器规格调整。
#=====================================================================

#队列阻塞超时 / 兜底轮询周期(秒)
#export CH_RENDER_WORKER_INTERVAL='30'

#单轮兜底最多消费 PENDING 任务数
#export CH_RENDER_WORKER_LIMIT='20'


#=====================================================================
# 6. 凭据巡检(schedule/credentialCheck.py)
#=====================================================================

#到期预警阈值(天): 到期日在该阈值内 -> EXPIRING
#export CH_CREDENTIAL_EXPIRE_WARN_DAYS='7'

#常驻巡检间隔(秒, 默认 3600)
#export CH_CREDENTIAL_CHECK_INTERVAL='3600'


#=====================================================================
# 7. 归档清理(config/opsSettings.py)
#=====================================================================

#审计日志保留期(月, 默认 24)
#export CH_ARCHIVE_AUDIT_RETAIN_MONTHS='24'

#分批大小(每批导出+删除记录数, 默认 5000)
#export CH_ARCHIVE_BATCH_SIZE='5000'

#单次运行最大批次数(护栏; 0=不限制, 默认 0)
#export CH_ARCHIVE_MAX_BATCH='0'

#导出格式: json.gz(默认) / csv
#export CH_ARCHIVE_EXPORT_FORMAT='json.gz'

#★ 破坏性操作总开关: "1"=真删, 缺省/0=dry-run(仅打印清单)
#   ★ 红线: 默认 dry-run, 真删必须显式确认, 故此处默认注释掉。
#export CH_ARCHIVE_EXECUTE='0'

#归档导出对象名前缀(默认 archive/audit/)
#export CH_ARCHIVE_EXPORT_OBJECT_PREFIX='archive/audit/'

#产物过期清理单次扫描上限(默认 20000)
#export CH_ARCHIVE_ARTIFACT_SCAN_LIMIT='20000'

#运维动作操作者标识(写 ch_audit_log.actor, 默认 charchive)
#export CH_OPS_ACTOR_LOGINID='charchive'


#=====================================================================
# 8. 监控告警(config/opsSettings.py)
#    全部可配, 不设即用代码默认阈值(见注释)。
#=====================================================================

#渲染失败率: N 分钟窗口内 FAILED 占比 > 阈值告警
#export CH_MONITOR_RENDER_WINDOW_MINUTES='15'
#export CH_MONITOR_RENDER_FAILURE_RATE='0.10'

#投递成功率: N 小时窗口内 success='0' 占比 > 阈值 或 连续失败次数 > 阈值
#export CH_MONITOR_PUBLISH_WINDOW_HOURS='24'
#export CH_MONITOR_PUBLISH_FAILURE_RATE='0.05'
#export CH_MONITOR_PUBLISH_CONSECUTIVE_FAIL='3'

#渲染队列积压: PENDING 最老任务等待 > N 分钟告警
#export CH_MONITOR_QUEUE_BACKLOG_MINUTES='15.0'

#存储用量: 使用率 > 阈值告警
#export CH_MONITOR_STORAGE_USAGE_RATE='0.80'

#定时任务: 最后成功时间超过 N 倍周期告警
#export CH_MONITOR_SCHEDULE_GRACE_FACTOR='1.5'

#审计日志量: 日增量环比突增 > N 倍告警
#export CH_MONITOR_AUDIT_GROWTH_FACTOR='3.0'

#定时任务周期(秒)表: archive / credentialCheck / dailyCheck
#export CH_MONITOR_PERIOD_ARCHIVE_SECONDS='86400'
#export CH_MONITOR_PERIOD_CREDENTIAL_SECONDS='3600'
#export CH_MONITOR_PERIOD_DAILYCHECK_SECONDS='86400'

#监控取数查询上限(防大表全量拉取)
#export CH_MONITOR_QUERY_LIMIT='20000'

#告警通道: log(默认, 仅落盘) / email / wecom(后两者为占位实现, 当前不发网络请求)
#export CH_MONITOR_ALERT_CHANNEL='log'

#监控报告与心跳落点(code/data/monitor/)
#export CH_MONITOR_DATA_DIR='/data/contenthub/src/data/monitor'


#=====================================================================
# 9. 使用提示
#=====================================================================

#直接执行(未 source)时给出提示: 子 shell 中的 export 不会影响父 shell。
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    echo "提示: 本脚本用于注入环境变量, 请用 source 加载后再启动服务:"
    echo "      source ${BASH_SOURCE[0]}"
    echo "      (当前为直接执行, 所设变量仅在本次子进程内有效, 不影响当前 shell)"
fi
