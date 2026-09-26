#! /usr/bin/env python3
#encoding: utf-8

#Filename: globalDefinition.py  
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com  
#Date: 2019-08-01
#Description:   定义全局常量

_VERSION="20260904"

#导入具体应用的全局变量

#common const definiation
_CONST_YES = "Y"
_CONST_NO = "N"

#language
_DEF_DEFAULT_LANGUAGE = "CN"

#common msg key words
_DEF_COMM_CODINGTYPE_NAME = "codingType"
_DEF_COMM_DATA_PACKAGE_NAME = "data"

_DEF_COMM_CODING_TYPE_JSON = "JSON" #
_DEF_COMM_CODING_TYPE_BCD = "BCD"
_DEF_COMM_CODING_TYPE_B6400 = "B64.00" #standard base64
_DEF_COMM_CODING_TYPE_B6401 = "B64.01" #加密的base64,simpleEncode
_DEF_COMM_CODING_TYPE_B6402 = "B64.02"
_DEF_COMM_CODING_TYPE_B64C1 = "B64.C1"

_DEF_COMM_CODING_TYPE_JSON_NUM = "0" #上面类型的对应数字表示
_DEF_COMM_CODING_TYPE_BCD_NUM = "1"
_DEF_COMM_CODING_TYPE_B6400_NUM = "2"
_DEF_COMM_CODING_TYPE_B6401_NUM = "3"
_DEF_COMM_CODING_TYPE_B6402_NUM = "4"
_DEF_COMM_CODING_TYPE_B64C1_NUM = "5"

_DEF_COMM_HASH_KEY_FOR_ALL = "THISISSTEVENCODE"

#redis key prefix
_DEF_REDIS_SYS_LEVEL1 = "SYS" #系统相关
_DEF_REDIS_USER_LEVEL1 = "USER" #用户相关
_DEF_REDIS_DEVICE_LEVEL1 = "DEV" #设备相关
_DEF_REDIS_TIMER_LEVEL1 = "TIMER" #定时相关
_DEF_REDIS_DATA_LEVEL1 = "DATA" #数据相关
_DEF_REDIS_FILE_LEVEL1 = "FILE" #文件相关
_DEF_REDIS_STAT_LEVEL1 = "STAT" #统计数据
_DEF_REDIS_CHANNEL_LEVEL1 = "CHANNEL" #频道相关
_DEF_REDIS_FORM_LEVEL1 = "FORM" #表单相关
_DEF_REDIS_FORM_HISTORY = "HISTORY" #历史数据相关
_DEF_REDIS_BUFFER_LEVEL1 = "BUFFER" #数据临时缓冲区

 
_DEF_REDIS_SYS_CONN_INTERVAL = "connInterval"
_DEF_REDIS_SYS_CONFIG = "CONFIG"

_DEF_REDIS_SYS_CONN_DEFAULT="default"
_DEF_REDIS_SYS_CONN_HIGH="high"
_DEF_REDIS_SYS_CONN_LOW="low"
_DEF_REDIS_SYS_CONN_RATE="rate"

_DEF_DATA_SMS_NAME = "SMS"
_DEF_DATA_SMS_CODE_KEEP_TIME = (10*60) #保存10分钟

_DEF_REDIS_USER_USER_ID = "userID"

#ip flood 
_DEF_REDIS_DATA_IP_COUNT = "IPCOUNT"
_DEF_REDIS_DATA_IP_TIME = "IPTIME"
_DEF_REDIS_DATA_IP_TIME_THRESOLD = 300 #五分钟
_DEF_REDIS_DATA_IP_VISITS = (_DEF_REDIS_DATA_IP_TIME_THRESOLD * 2) #五分钟
_DEF_REDIS_DATA_IP_EXPIRE_TIME = (30*24*60*60) #30天

#给客户端提供的在线存储
_DEF_REDIS_USER_DATA_SAVE_NAME = "USER_SAVE"

_DEF_REDIS_DEV_DEVICE_ID = "devID"

_DEF_REDIS_DEV_MAID="MAID"
_DEF_REDIS_DEV_MAID_PIDLIST="PIDList"

_DEF_REDIS_DEV_MAID_PID="MAID_PID"
_DEF_REDIS_DEV_MAID_PID_CONN_INTERVAL="connInterval"


_DEF_REDIS_DEV_TYPE_ID="typeID"
_DEF_REDIS_DEV_TYPE_ID_INFO="info"
_DEF_REDIS_DEV_TYPE_ID_CONFIG="config"
_DEF_REDIS_DEV_TYPE_ID_INST_SET="instSet"

_DEF_REDIS_DEV_CMD_SET="cmdSet"

# CMD channel 
_DEF_REDIS_CHANNEL_MAIN = "MAIN"

#二级系统参数 _DEF_REDIS_SYS_LEVEL1对应的
_DEF_REDIS_SYS_STATUS = "STATUS"
_DEF_REDIS_SYS_MSG_SEQ_NUM = "MSG_SEQ_NUM"
_DEF_REDIS_SYS_KICKOFF_TIMESTAMP = "KICKOFF_TIMESTAMP"
_DEF_REDIS_SYS_KICKOFF_HUMANTIME = "KICKOFF_HUMANTIME"

#二级系统参数 _DEF_REDIS_DATA_LEVEL1对应的
_DEF_REDIS_DATA_TYPE_QUEUE = "QUEUE"
_DEF_REDIS_DATA_TYPE_STAT = "STAT"
_DEF_REDIS_DATA_TYPE_MSG_RECV = "MSG_RECV"

#redis init log
_DEF_REDIS_LOG_TITLE = "INIT_V1"
_DEF_REDIS_LOG_NAME = "initlog"

#redis user database key
_DEF_REDIS_USER_DB_USER_BASIC = "BASIC"
_DEF_REDIS_USER_DB_USER_WARN = "WARN" #Warning list
_DEF_REDIS_USER_DB_USER_NAME = "userName"
_DEF_REDIS_USER_DB_PASSWORD = "password"
_DEF_REDIS_USER_DB_ASSETS_ID = "assetsID" #资产ID
_DEF_REDIS_USER_DB_WECHAT_OPENID = "weChatOpenID" #某个用户对应的微信小程序openID
_DEF_REDIS_USER_DB_WECHAT_CODE = "weChatCode" #微信小程序 code对应的openid 和sessionkey
_DEF_REDIS_USER_DB_OPENID_LOGINID = "openID_loginID" #微信小程序openid 对应的 loginID
_DEF_REDIS_USER_WECHAT_CODE_KEEP_TIME = (60*10) #微信小程序 code 保存时间
_DEF_REDIS_USER_DB_DELETE_FLAG = "delFlag"
_DEF_REDIS_USER_DB_DELETE_TRUE = "1"
_DEF_REDIS_USER_DB_DELETE_FALSE = "0"
_DEF_REDIS_USER_DB_DELETE_DATE = "delYMDHMS"
_DEF_REDIS_USER_DB_UPDATE_DATE = "updateYMDHMS"
#_DEF_REDIS_USER_DB_USER_SALT = "userSalt"
_DEF_REDIS_USER_DB_ACTIVE = "active"
_DEF_REDIS_USER_DB_DEV_LIST = "devList"
_DEF_REDIS_USER_DB_FRIEND_LIST = "friendList"
_DEF_REDIS_USER_DB_CHAT_LIST = "chatList"
_DEF_REDIS_USER_DB_CMD_LIST = "cmdList"
_DEF_REDIS_USER_DB_POSITION = "position"
_DEF_REDIS_USER_DB_SESSIONID_LIST = "sessionIDList"
_DEF_REDIS_USER_DB_REG_TIME = "regTime"
_DEF_REDIS_USER_DB_LAST_CONN_TIME = "lastConnTime"
_DEF_REDIS_USER_DB_SCHEDULE_TASK = "scheduleTask"
_DEF_REDIS_USER_DB_DAYTIME_TASK = "dayTimeTask"

#default user
_DEF_REDIS_USER_DEFAULT_USER_NAME = "000000"
_DEF_REDIS_USER_DEFAULT_PASSWORD = "000000"

_DEF_REDIS_USER_ID_LENGTH = 5

_DEF_USER_SESSION_EXPIRE_TIME = (30*60) #用户进程过期时间默认是30分钟
_DEF_OPERATOR_SESSION_EXPIRE_TIME = (30*60) #操作进程过期时间默认是30分钟

#是否允许用户的其他数据保存
_DEF_REDIS_USER_SAVE_NON_PROTECT_KEYS = True
#用户信息中受包含的关键词, 全部小写保护,
_DEF_REDIS_USER_PROTECT_KEYS_LIST =set ([
  "username", "userid", "loginid","user", "name","realname","openid", "regopenid", "modifyopenid", "regid", "modifyid",  "updateid", "updateopenid", "master", "masterid", 
  "passwd", "password", 
  "rolename", "ruleinfo", 
  "avatarid", "mobilephoneno", "province", "city", "area", "address", "addr", 
  "chiefvillageidlist", 
  "email", 
  "pid", 
  "photoid", "photoidfront", "photoidback", "photo", "faceid", 
  "regymdhms", "ymdhms", "modifyymdhms",  "updateymdhms", "lastloginymdhms", "passwordymdhms", 
  "delflag", 
])

#用户信息中不主动给用户的数据
_DEF_REDIS_USER_NOSHOW_KEYS_LIST =set ([
  "realname","modifyid",  "updateid", "updateopenid", "master", "masterid", 
  "passwd", "password", 
  "rolename", "ruleinfo", 
  "pid", 
  "photoid", "photoidfront", "photoidback", "photo", 
  "regymdhms",  "modifyymdhms",  "updateymdhms", "lastloginymdhms", "passwordymdhms", 
  "delflag", 
])


# FILE

_DEF_FILE_INDEX_NAME = "INDEX"
_DEF_FILE_INDEX_FILEID = "FILEID"

_DEF_FILE_REQUEST_TYPE_THUMBNAIL = "thumbnail" #缩略图请求类型

_CONST_MAXSALT_SIMPLELEN="128"

#buffer二级
_DEF_BUFFER_DATA_NAME = "DATA" #数据存储区域
_DEF_BUFFER_STEP_NAME = "STEP" #数据存取的位置区域
_DEF_BUFFER_KEY_TYPE_NAME = "KEYTYPE" #关键词存储区域

_DEF_BUFFER_DATA_KEEP_TIME = 900 #查询缓冲区保存时间, 默认是60*15 15分钟, 900秒
_DEF_BUFFER_DATA_BEGIN_NUM = 0 # 默认一次提供5000个数据
_DEF_BUFFER_DATA_END_NUM = 9999 #默认一次提供10000个数据


#支付相关
#currency 币种,最小单位换算关系
_DEF_CURRENCY_AUD = "AUD" #澳大利亚元
_DEF_CURRENCY_CAD = "CAD" #加拿大元 
_DEF_CURRENCY_CHF = "CHF" #瑞士法郎
_DEF_CURRENCY_CNY = "CNY" #人民币
_DEF_CURRENCY_EUR = "EUR" #欧元
_DEF_CURRENCY_GBP = "GBP" #英镑
_DEF_CURRENCY_HKD = "HKD" #港币
_DEF_CURRENCY_IDR = "IDR" #印尼盾
_DEF_CURRENCY_JPY = "JPY" #日元
_DEF_CURRENCY_KRW = "KRW" #韩国元 
_DEF_CURRENCY_MYR = "MYR" #马来西亚林吉特 
_DEF_CURRENCY_NZD = "NZD" #新西兰元
_DEF_CURRENCY_PHP = "PHP" #菲律宾比索 
_DEF_CURRENCY_SGD = "SGD" #新加坡元 
_DEF_CURRENCY_SUR = "SUR" #俄罗斯卢布
_DEF_CURRENCY_THB = "THB" #泰铢 
_DEF_CURRENCY_USD = "USD" #美元

_DEF_CURRENCY_DEFAULT = _DEF_CURRENCY_CNY #默认币种

_DEF_CURRENCY_UNITS = {
    "CN":{
    _DEF_CURRENCY_AUD:{"unit":"澳元","rate":100},
    _DEF_CURRENCY_CAD:{"unit":"加元","rate":100},
    _DEF_CURRENCY_CHF:{"unit":"法郎","rate":100},
    _DEF_CURRENCY_CNY:{"unit":"元","rate":100},
    _DEF_CURRENCY_EUR:{"unit":"欧元","rate":100},
    _DEF_CURRENCY_GBP:{"unit":"英镑","rate":100},
    _DEF_CURRENCY_HKD:{"unit":"元","rate":100},
    _DEF_CURRENCY_IDR:{"unit":"盾","rate":1},
    _DEF_CURRENCY_JPY:{"unit":"日元","rate":1},
    _DEF_CURRENCY_KRW:{"unit":"韩元","rate":1},
    _DEF_CURRENCY_MYR:{"unit":"吉特","rate":1},
    _DEF_CURRENCY_NZD:{"unit":"新西兰元","rate":100},
    _DEF_CURRENCY_PHP:{"unit":"比索","rate":100},
    _DEF_CURRENCY_SGD:{"unit":"元","rate":100},
    _DEF_CURRENCY_SUR:{"unit":"卢布","rate":100},
    _DEF_CURRENCY_THB:{"unit":"铢","rate":100},
    _DEF_CURRENCY_USD:{"unit":"美元","rate":100},
  },
}["CN"]


#"payType CHAR(16) NOT NULL,",  #支付形式, 现金, 零钱, 银行卡, .信用卡.. ... 
_DEF_PAYTYPE_CASH = "CASH"
_DEF_PAYTYPE_POCKET = "POCKET"
_DEF_PAYTYPE_DEBIT = "DEBIT"
_DEF_PAYTYPE_CREDIT = "CREDIT"

#"payPlatform CHAR(16) NOT NULL,",  #支付平台, 微信, 支付宝, 工商银行等 
_DEF_PAYTYPE_WEXIN = "WEIXIN"
_DEF_PAYTYPE_ALIPAY = "ALIPAY"
_DEF_PAYTYPE_BANK_ICBC = "BANK_ICBC"
_DEF_PAYTYPE_BANK_BOC = "BANK_BOC"
_DEF_PAYTYPE_BANK_COB = "BANK_COB"

#订单类型
#"orderType CHAR(16) NOT NULL,",  #订单类型, 定金, 订金, 余款
_DEF_ORDER_TYPE_DOWNPAYMENT = "DOWNPAYMENT"
_DEF_ORDER_TYPE_DEPOSITE  = "DEPOSITE" #定金
_DEF_ORDER_TYPE_BALANCE  = "BALANCE" #余款
_DEF_ORDER_TYPE_REFUND  = "REFUND" #退款

#订单状态
_DEF_ODRER_STATUS_OPEN = "OPEN" #新发起
_DEF_ORDER_STATUS_CLOSE = "CLOSE" #关闭
_DEF_ORDER_STATUS_INPROGRSS = "INPROGRSS" #过程中
_DEF_ORDER_STATUS_CANCEL = "CANCEL" #删除 
_DEF_ORDER_STATUS_ERROR = "ERROR" #错误 

#general definitions 
_DEF_GE_LOGIC_AND = "AND"
_DEF_GE_LOGIC_OR = "OR"
_DEF_GE_LOGIC_NOT = "NOT"
_DEF_GE_LOGIC_ALL = "ALL"


_DEF_WECHAT_PAY_STATYS_CREATE = "C"  #建立 #weixin 
_DEF_WECHAT_PAY_STATYS_SUCCESS = "S" #成功
_DEF_WECHAT_PAY_STATYS_RECALL = "R" #回退
_DEF_WECHAT_PAY_STATYS_REFUND = "U" #退款
_DEF_WECHAT_PAY_STATYS_CALLBACK_RECEIVED = "B" #数据收到
_DEF_WECHAT_PAY_STATYS_CALLBACK_CREATE = "A" #call back 建立

#微信支付v3定义
_DEF_WECHAT_PAY_STATYS_PENDING = "P"  #待支付/待处理
_DEF_WECHAT_PAY_STATYS_FAILED = "F" #支付失败/退款失败
_DEF_WECHAT_PAY_STATYS_CLOSED = "C" #支付/退款关闭
_DEF_WECHAT_PAY_TIMEOUT = 10 #微信支付超时时间，单位秒
#微信支付成功失败原因定义
_DEF_WECHAT_PAY_ORDER_NOT_FOUND = "订单不存在"
_DEF_WECHAT_PAY_ORDER_STATUS_INVALID = "订单状态无效"
_DEF_WECHAT_PAY_BUSINESS_FAILED = "微信统一下单失败"
_DEF_WECHAT_PAY_SIGN_VERIFY_FAILED = "签名验证失败"
_DEF_WECHAT_PAY_NETWORK_TIMEOUT = "网络连接超时"
_DEF_WECHAT_PAY_HTTP_ERROR = "HTTP请求失败"
_DEF_WECHAT_PAY_UNKNOWN_ERROR = "系统繁忙，请稍后重试"
_DEF_WECHAT_PAY_ORDER_ALREADY_PAID = "订单已支付"
_DEF_WECHAT_PAY_ORDER_ALREADY_REFUND = "订单已退款"
_DEF_WECHAT_PAY_ORDER_ALREADY_CLOSED = "订单已关闭"
_DEF_WECHAT_PAY_ORDER_ALREADY_CANCELLED = "订单已取消"
_DEF_WECHAT_PAY_ORDER_PAYED_FAILED = "订单支付失败"
_DEF_WECHAT_PAY_ORDER_REFUND_ABNORMAL = "订单退款异常"

#通用mysql相关
_DEF_DEFAULT_REGID = "system" #默认用户保存id

#微信小程序物流服务状态定义
_DEF_MINIPROGRAM_EXPRESS_ORDER_STATUS = {
    "PENDING": 0,      # 待取件
    "PICKED": 1,       # 已揽收
    "TRANSIT": 2,      # 运输中
    "DELIVERING": 3,   # 派送中
    "SIGNED": 4,       # 已签收
    "CANCELLED": 5,    # 已取消
    "ERROR": 6,        # 异常
}
_DEF_MINIPROGRAM_EXPRESS_ORDER_STATUS_TEXT = {
    0: "待取件",
    1: "已揽收",
    2: "运输中",
    3: "派送中",
    4: "已签收",
    5: "已取消",
    6: "异常",
    7: "已结算",
    8: "已出单",
}

# action_type 到订单状态的映射
# 订单状态码含义：0-待取件，1-已揽收，2-运输中，3-派送中，4-已签收，5-已取消，6-异常
_DEF_MINIPROGRAM_EXPRESS_ACTION_STATUS_MAP = {
    # 已签收相关
    300003: {"code": 4, "text": "已签收"},
    
    # 派送中相关
    300002: {"code": 3, "text": "派送中"},
    
    # 运输中相关
    200001: {"code": 2, "text": "运输中"},
    
    # 已揽收相关
    100001: {"code": 1, "text": "已揽收"},
    100003: {"code": 1, "text": "已揽收"},  # 已分配快递员
    
    # 已取消相关
    400001: {"code": 5, "text": "已取消"},
    
    # 异常相关
    100002: {"code": 6, "text": "异常"},  # 揽件失败
    300004: {"code": 6, "text": "异常"},  # 签收失败
    400002: {"code": 6, "text": "异常"},  # 订单滞留
}

_DEF_MAX_QUERY_LIMIT_NUM = 20000 #默认最多允许搜索数据个数
_DEF_MIN_QUERY_LIMIT_NUM = 1000 #默认最少允许搜索数据个数
_DEF_MAX_DISP_LIMIT_NUM = 1000 #默认最多显示数据个数
_DEF_BATCH_QUERY_LIMIT_NUM = 10000 #默认每次查询数据个数


_DEF_NICKNAME_PREFIX = "user"
_DEF_NICKNAME_LEN = 12

_DEF_ADDR_MIN_LENGTH = 10 #地址最小长度

_DEF_PID_LABEL ="PID"
_DEF_PID_ID_MIN_LENGTH = 18 #身份证长度
_DEF_PID_ID_MAX_LENGTH = 18 #身份证长度

_DEF_TEL_NO_MIN_LENGTH = 8 #电话号码长度
_DEF_TEL_NO_MAX_LENGTH = 20 #电话号码长度

_DEF_PERSONAL_NAME_LABEL = "PNAME"
_DEF_PERSONAL_NAME_MIN_LENGTH = 2 #姓名最小2个汉字
_DEF_PERSONAL_NAME_MAX_LENGTH = 20 #姓名最长20个汉字

_DEF_TEL_LABEL = "TEL"

_DEF_CITY_NAME_LABEL ="CNAME"
_DEF_CITY_NAME_MIN_LENGTH = 2 #城市名称最少2个汉字
_DEF_CITY_NAME_MAX_LENGTH = 15 #城市最长15个汉字

_DEF_AREA_NAME_LABEL ="ANAME"
_DEF_AREA_NAME_MIN_LENGTH = 2 #区县名称最少2个汉字
_DEF_AREA_NAME_MAX_LENGTH = 15 #区县最长15个汉字

_DEF_EMAIL_LABEL ="EMAIL"

_DEF_WHOLE_ADDR_LABEL ="WADDR"


#通用 mysql 日志(被 common/mysqlCommon.py、common/chCommon.py 使用)
_DEF_GENRAL_MYSQL_LOG_NAME = "mysqllog"
_DEF_LOG_TRANS_MYSQL_LOG = "transfermysqllog"

_DEF_CH_MSG_QUEUE_MYSQL_TITLE ="CH_MYSQL" #消息队列日志标题

#渲染任务通知队列(与 CH_MYSQL 同款 key 组装; 由 schedule/renderWorker.py 阻塞消费,
#transferCHMysql.py 的 CH_MYSQL 为账号落库队列, 二者相互独立、互不干扰)
_DEF_CH_MSG_QUEUE_RENDER_TITLE ="CH_RENDER" #渲染任务队列标题

#contentHub(内容中枢) begin
#说明: 本节为 contentHub 纯追加常量, 不改动上方任何既有常量;
#      mcpapi/mcp_entry.py 与 mcpapi/mcpPost.py 引用前两个, common/chServerCommon.py 引用第三个

#logs
_DEF_LOG_CH_MCP_TITLE = "CHMCP"
_DEF_LOG_CH_MCP_NAME = "chmcplog"
_DEF_LOG_CH_TEST_NAME = "chtestlog"
_DEF_LOG_CH_RENDER_NAME = "chrenderlog"
_DEF_LOG_CH_RENDER_TITLE = "RENDER"

#Web 入口日志(对齐上方通用 mysql 日志名)
#由 main/chAPI.py 与 main/chAPIPost.py 共用同一个 logger(同名 logger 幂等, 见 miscCommon.setLogNew)
_DEF_LOG_CH_WEBAPI_TITLE = "CHAPI"
_DEF_LOG_CH_WEB_API_NAME = "chweblog"

#contentHub end
