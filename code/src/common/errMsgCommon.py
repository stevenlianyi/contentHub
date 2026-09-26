#! /usr/bin/env python3
#encoding: utf-8

#Filename: errMsgCommon.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub(内容中枢) 错误消息表与统一返回报文封装(SP1.5 从 common/funcCommon.py 抽取)。
#抽取依据: plan/chAPIPost分拆方案.md 7.3(错误消息段与 funcCommon 其余部分零耦合, 且 contentHub 需新增 msgKey,
#         继续塞入会让 funcCommon.py 继续膨胀); 7.4 迁移四步; 决策 12.4(立即抽取) / 12.6(DEFAULT_MSG_KEY=contenthub) /
#         12.5(getErrMsg/transOtherMsg 保留但标注 deprecated)。
#
#设计约束:
#  1) 本模块「零依赖」: 不 import settings / globalDefinition / 任何第三方库(仅依赖内置类型),
#     因此可被 main/、common/、database/ 任意层安全引用, 且不会与 funcCommon 形成循环依赖;
#  2) common/funcCommon.py 顶部做 re-export, 既有引用方(25 个文件, 含 12 份生成产物)零改动;
#  3) CI 约束 C4: funcCommon.py 中不得再出现 CONST_ERROR_wordList 的定义。
#
#错误码规划(R9: 新码段与既有 B*/C[字母]*/D[字母]* 段零重叠):
#  C0-C9 通用与字段校验  |  D0-D9 文件与素材  |  E0-E9 渲染与产物
#  F0-F9 投递            |  G0-G9 MCP 与令牌
#其中 C2 为「占位端点专用」错误码(SP1.5 已登记但尚未实现的端点统一返回 C2, 保证不 404、不静默)。

_VERSION="20260918"


#common function:
#如果执行失败或者异常返回消息定义
CONST_ERROR_wordList = {
    "default":{
        "EN":{
            "OK" :'success',
            "ERR_UPDATE" :'exception. check the updated value.',
            "ERR_FIELD" :'exception. the field %s not found or null.',
            "ERR_TOKEN" :'exception. token or format error.',
            "ERR_SESSION" :'exception. session or format error.',
            
            "ERR_DEVID" :"%s - it's a invalid device ID.",
            "ERR_LOGIN" :"login fail, no user or password wrong",
            "ERR_NO_REG" :"%s - it should be registered firstly.",
            "ERR_REPEAT_REG" :"%s - it has beed registered.",
            "ERR_INVALID":"exception. data in valid", 
            "ERR_WARN":"warning. cells status is not correct, pls check... ", 
            "ERR_GENERAL":"exception. unknow error. %s", 
            "ERR_NOCMD":"data format ERROR, no CMD", 
            "ERR_IPFLOOD":"too many visits", 
            "ERR_BUCKET":"unknown or invalid bucketCode: %s", 

            "ERR_PID":"personal ID is invalid, format error", 
            "ERR_TEL":"telephone number is too short, format error", 
            "ERR_NAME":"name is too short, format error", 
            "ERR_HOTELNAME":"hotel name is too short, format error", 
            "ERR_ADDR":"address is too short, format error", 
            "ERR_EMAIL":"email format error", 
            "ERR_CITY":"city name length error, pls check", 
            "ERR_AREA":"area name length error, pls check", 
            "ERR_WADDR":"whole address is too short, pls check", 
            
            "WARN_FACE":"face might not match with ID", 
            
            "B0":"success.",
            "B1":"loginID is invalid.",
            "B2":"loginID is too short.",
            "B3":"passwd is invalid.",
            "B4":"loginID is already exist.",
            "B5":"loginID or passwd is invalid.",
            "B6":"new passwd is invalid.",
            "B7":"new loginID is invalid.",
            "B8":"exception. sessionID or format error.",
            "B9":"alreay exist with same name and address, conflict.",
            "BA":"data is invalid %s.",
            "BE":"user need to be registered.",
            "BF":"mini program code error.",
            "BG":"access denied.",
            "BH":"Due fee, please recharge.",
            "BI":"recID is invalid.",
            "BK":"search option format error.",
            "BL":"file upload error. %s",
            "BM":"verify code is invalid or password is wrong, pls try to reset password",
            "BN":"verify code send error %s",
            "BO":"key or val error",
            "BP":"superiorID is invalid",
            "BQ":"category is invalid", 
            "BS":"this app don's support resistration",        
            "BT":"you dont' have right to access",       
            "BU":"wechat pay process error",    
            "BV":"face might not match with ID",    
            "BW":"mobile numer is wrong, or could not find",    
            "BX":"no code or wrong code, or no openID is wrong",    
            "BY":"no openID or wrong openID",    
            "BZ":"exception. token or format error.",    
            "CA":"repeat record,pls check",    
            "CB":"no record,pls check",    
            "CC":"expired, re-query",    
            "CD":"only register user could apply",    
            "CE":"invalid visitYMD",    
            "CF":"mobile, name might not match with ID",    
            "CG":"insert record error",    
            "CH":"templateID error",    
            "CU":"update record error",    
            "CV":"delete record error",    
            "DA":"device is not online!!!",    
            "DB":"send cmd to device fail,fail count:[%s]",    
            "EA":"pls select projectID",    
            "EL":"The uploaded data content or format is incorrect, please check!",    
        }, 
        "CN":{
            "OK" :'成功',
            "ERR_UPDATE" :'exception. check the updated value.',
            "ERR_FIELD" :'exception. the field %s not found or null.',
            "ERR_TOKEN" :'exception. token or format error.',
            "ERR_SESSION" :'exception. session or format error.',
            
            "ERR_DEVID" :"%s - it's a invalid device ID.",
            "ERR_LOGIN" :"login fail, no user or password wrong",
            "ERR_NO_REG" :"%s - it should be registered firstly.",
            "ERR_REPEAT_REG" :"%s - it has beed registered.",
            "ERR_INVALID":"exception. data in valid", 
            "ERR_WARN":"warning. cells status is not correct, pls check... ", 
            "ERR_GENERAL":"exception. unknow error. %s", 
            "ERR_NOCMD":"权限错误，请联系管理员", 
            "ERR_IPFLOOD":"短时期太多访问", 
            "ERR_BUCKET":"未知的桶编码: %s", 
            
            "ERR_PID":"身份证号码是无效的", 
            "ERR_TEL":"电话号码太短,少于8位,请查看", 
            "ERR_NAME":"姓名太短,少于2个汉字,请查看", 
            "ERR_HOTELNAME":"酒店名称,少于3个汉字,请查看", 
            "ERR_ADDR":"地址信息太短,少于5个汉字,请查看", 
            "ERR_EMAIL":"email地址不对,请查看", 
            "ERR_CITY":"城市名称长度不对,请查看", 
            "ERR_AREA":"区县名称长度不对,请查看", 
            "ERR_WADDR":"完整地址太短,请查看", 

            "WARN_FACE":"人脸和身份证可能不匹配,请查验", 

            "B0":"成功",
            "B1":"登录账号不存在",
            "B2":"登录账号太短,不少于6个字符",
            "B3":"密码错",
            "B4":"登录账号重复",
            "B5":"登录账号或者密码错",
            "B6":"新密码错",
            "B7":"新登录账号无效",
            "B8":"sessionID 无效",
            "B9":"已经存在,不能新增",
            "BA":"数据格式有问题, %s.",
            "BE":"用户没有注册,或者限制注册",   
            "BF":"小程序 code error.",
            "BG":"您的权限不足",
            "BH":"您已经欠费,请充值",
            "BI":"recID 无效.",
            "BK":"搜索逻辑格式错误",
            "BL":"文件上传失败. %s",
            "BM":"校验码无效,或者是用户密码错误,建议尝试密码找回",
            "BN":"验证码发送失败, %s",
            "BO":"key 或者 val 无效",
            "BP":"superiorID 错误",
            "BQ":"category 错误",
            "BR":"你没有登录此小程序的权限",        
            "BS":"不支持注册功能",        
            "BT":"无权访问", 
            "BU":"微信支付出现问题",    
            "BV":"人脸和身份证可能不匹配,请查验",    
            "BW":"手机号码错误, 或者找不到",    
            "BX":"没有小程序code,或者是code错误,导致openID不正确",    
            "BY":"没有小程序openID,或者是生成的openID错误",      
            "BZ":"token错误",    
            "CA":"重复的记录,请检查",    
            "CB":"无此的记录,请检查",    
            "CC":"数据过期,请重新查询",    
            "CD":"只有注册用户可以申请,请先注册",    
            "CF":"手机号,身份证, 姓名不匹配",    
            "CG":"记录添加失败",    
            "CU":"记录更新失败",    
            "CV":"记录删除失败",    
            "DA":"设备不在线!!!",    
            "DB":"发送命令失败,失败次数:[%s]",    
            "EA":"请选择项目",    
            "EL":"上传的数据内容或者格式错误,请检查!",    
        }
    },
    "account":{
        "EN":{
            "OK" :'success',
            "ERR_UPDATE" :'exception. check the updated value.',
            "ERR_FIELD" :'exception. the field %s not found or null.',
            "ERR_TOKEN" :'exception. token or format error.',
            "ERR_SESSION" :'exception. session or format error.',
            
            "ERR_DEVID" :"%s - it's a invalid device ID.",
            "ERR_LOGIN" :"login fail, no user or password wrong",
            "ERR_NO_REG" :"%s - it should be registered firstly.",
            "ERR_REPEAT_REG" :"%s - it has beed registered.",
            "ERR_INVALID":"exception. data in valid", 
            "ERR_WARN":"warning. cells status is not correct, pls check... ", 
            "ERR_GENERAL":"exception. unknow error. %s", 
            "ERR_NOCMD":"data format ERROR, no CMD", 
            "ERR_IPFLOOD":"too many visits", 
            "ERR_BUCKET":"unknown or invalid bucketCode: %s", 

            "ERR_PID":"personal ID is invalid, format error", 
            "ERR_TEL":"telephone number is too short, format error", 
            "ERR_NAME":"name is too short, format error", 
            "ERR_HOTELNAME":"hotel name is too short, format error", 
            "ERR_ADDR":"address is too short, format error", 
            "ERR_EMAIL":"email format error", 
            "ERR_CITY":"city name length error, pls check", 
            "ERR_AREA":"area name length error, pls check", 
            "ERR_WADDR":"whole address is too short, pls check", 
            
            "WARN_FACE":"face might not match with ID", 
            
            "B0":"success.",
            "B1":"loginID is invalid.",
            "B2":"loginID is too short.",
            "B3":"passwd is invalid.",
            "B4":"loginID is already exist.",
            "B5":"loginID or passwd is invalid.",
            "B6":"new passwd is invalid.",
            "B7":"new loginID is invalid.",
            "B8":"exception. sessionID or format error.",
            "B9":"alreay exist with same name and address, conflict.",
            "BA":"data is invalid %s.",
            "BE":"user need to be registered.",
            "BF":"mini program code error.",
            "BG":"access denied.",
            "BH":"Due fee, please recharge.",
            "BI":"recID is invalid.",
            "BK":"search option format error.",
            "BL":"file upload error. %s",
            "BM":"verify code is invalid",
            "BN":"verify code send error %s",
            "BO":"key or val error",
            "BP":"superiorID is invalid",
            "BQ":"category is invalid", 
            "BS":"this app don's support resistration",        
            "BT":"you dont' have right to access",       
            "BU":"wechat pay process error",    
            "BV":"face might not match with ID",    
            "BW":"mobile numer is wrong, or could not find",    
            "BX":"no code or wrong code, or no openID is wrong",    
            "BY":"no openID or wrong openID",    
            "BZ":"exception. token or format error.",    
            "CA":"repeat record,pls check",    
            "CB":"no record,pls check",    
            "CC":"expired, re-query",    
            "CD":"only register user could apply",    
            "CE":"invalid visitYMD",    
            "CF":"mobile, name might not match with ID",    
            "CG":"insert record error",    
            "CH":"templateID error",    
            "CI":"backbone service is offline",    
            "CU":"update record error",    
            "CV":"delete record error",    
            "CS":"The message has been sent too many times in a short period, please try again later.",     
        }, 
        "CN":{
            "OK" :'成功',
            "ERR_UPDATE" :'exception. check the updated value.',
            "ERR_FIELD" :'exception. the field %s not found or null.',
            "ERR_TOKEN" :'错误, token,内部错误或者是格式错误.',
            "ERR_SESSION" :'错误, session,内部错误或者是格式错误.',
            
            "ERR_DEVID" :"%s - it's a invalid device ID.",
            "ERR_LOGIN" :"login fail, no user or password wrong",
            "ERR_NO_REG" :"%s - it should be registered firstly.",
            "ERR_REPEAT_REG" :"%s - it has beed registered.",
            "ERR_INVALID":"exception. data in valid", 
            "ERR_WARN":"warning. cells status is not correct, pls check... ", 
            "ERR_GENERAL":"错误, 严重错误. %s", 
            "ERR_NOCMD":"权限错误，请联系管理员", 
            "ERR_IPFLOOD":"短时期太多访问", 
            
            "ERR_PID":"身份证号码是无效的", 
            "ERR_TEL":"电话号码太短,少于8位,请查看", 
            "ERR_NAME":"姓名太短,少于2个汉字,请查看", 
            "ERR_HOTELNAME":"酒店名称,少于3个汉字,请查看", 
            "ERR_ADDR":"地址信息太短,少于5个汉字,请查看", 
            "ERR_EMAIL":"email地址不对,请查看", 
            "ERR_CITY":"城市名称长度不对,请查看", 
            "ERR_AREA":"区县名称长度不对,请查看", 
            "ERR_WADDR":"完整地址太短,请查看", 

            "WARN_FACE":"人脸和身份证可能不匹配,请查验", 

            "B0":"成功",
            "B1":"登录账号不存在",
            "B2":"登录账号太短,不少于6个字符",
            "B3":"密码错",
            "B4":"登录账号重复",
            "B5":"登录账号或者密码错",
            "B6":"新密码错",
            "B7":"新登录账号无效",
            "B8":"sessionID 无效",
            "B9":"已经存在,不能新增",
            "BA":"数据格式有问题, %s.",
            "BE":"用户没有注册,或者限制注册",   
            "BF":"小程序 code error.",
            "BG":"您的权限不足",
            "BH":"您已经欠费,请充值",
            "BI":"recID 无效.",
            "BK":"搜索逻辑格式错误",
            "BL":"文件上传失败. %s",
            "BM":"校验码无效",
            "BN":"验证码发送失败, %s",
            "BO":"key 或者 val 无效",
            "BP":"superiorID 错误",
            "BQ":"category 错误",
            "BR":"你没有登录此小程序的权限",        
            "BS":"不支持注册功能",        
            "BT":"无权访问", 
            "BU":"微信支付出现问题",    
            "BV":"人脸和身份证可能不匹配,请查验",    
            "BW":"手机号码错误, 或者找不到",    
            "BX":"没有小程序code,或者是code错误,导致openID不正确",    
            "BY":"没有小程序openID,或者是生成的openID错误",      
            "BZ":"token错误",    
            "CA":"重复的记录,请检查",    
            "CB":"无此的记录,请检查",    
            "CC":"数据过期,请重新查询",    
            "CD":"只有注册用户可以申请,请先注册",    
            "CF":"手机号,身份证, 姓名不匹配",    
            "CG":"记录添加失败",    
            "CH":"templateID 错误",    
            "CI":"基础服务请求失败",    
            "CU":"记录更新失败",    
            "CV":"记录删除失败",    
            "CS":"短信短时间发送次数太多, 请稍后再发",     
        }
    },
}

#===== contentHub 专用消息键 begin =====
#说明(决策 12.4/12.6):
#  1) contenthub 表不重复维护 70+ 条历史错误码, 而是以 default 表为底 -> 叠加 account 表
#     (补齐 default 中缺失的 CI/CS/BR 等码) -> 再叠加下方 contentHub 新码段, 保证单一事实来源、不会漏码;
#  2) 本表只增量追加, 不修改 default/account/mindgram_msg 的任何既有内容;
#  3) 新码段一律「字母+数字」, 与既有段零重叠(R9)。
_CH_ERROR_WORD = {
    "EN": {
        #C 段: 通用 + 字段校验
        "C0": "success.",
        "C1": "request failed.",
        "C2": "not implemented yet.",
        "C3": "downstream service is unavailable.",
        "C4": "required field is missing: %s.",
        "C5": "field is too long: %s.",
        "C6": "numeric value is out of range: %s.",
        "C7": "invalid value: %s.",
        "C8": "no such record, pls check.",
        "C9": "duplicated record, pls check.",
        #D 段: 文件与素材
        "D0": "file type is not allowed.",
        "D1": "file exceeds the size or dimension limit.",
        "D2": "duplicated content.",
        "D3": "file upload failed. %s",
        "D4": "file not found. %s",
        #E 段: 渲染与产物
        "E0": "layout template not found. %s",
        "E1": "render failed. %s",
        "E2": "screenshot timeout. %s",
        "E3": "artifact generation failed. %s",
        "E4": "external image needs to be transferred to the platform but credentials are missing. %s",
        #F 段: 投递(SP4a 起启用; F0 覆盖「未配置/解密失败/已过期/未认证」, 一律明确回显不静默)
        "F0": "credential is invalid, missing or expired.",
        "F1": "idempotency hit, already delivered.",
        "F2": "rate limit exceeded, pls retry later.",
        "F3": "platform rejected the request.",
        "F4": "manual confirmation is required before delivery.",
        "F5": "revoke window has expired.",
        "F6": "auto publish is not enabled (manual confirmation required).",
        #G 段: MCP 与令牌(SP4b 追加 G2/G3: mcpinvoke 薄入口的工具路由与下游转发)
        "G0": "token is invalid.",
        "G1": "token scope is not enough.",
        "G2": "unknown MCP tool.",
        "G3": "downstream service call failed.",
    },
    "CN": {
        #C 段: 通用 + 字段校验
        "C0": "成功",
        "C1": "请求失败",
        "C2": "该端点尚未实现",
        "C3": "下游服务不可用",
        "C4": "缺少必填字段: %s",
        "C5": "字段超长: %s",
        "C6": "数值超出允许范围: %s",
        "C7": "取值非法: %s",
        "C8": "无此的记录,请检查",
        "C9": "记录重复,请检查",
        #D 段: 文件与素材
        "D0": "文件类型不允许",
        "D1": "文件超出大小或尺寸限制",
        "D2": "内容重复",
        "D3": "文件上传失败. %s",
        "D4": "文件不存在. %s",
        #E 段: 渲染与产物
        "E0": "版式模板缺失: %s",
        "E1": "渲染失败: %s",
        "E2": "截图超时: %s",
        "E3": "产物生成失败: %s",
        "E4": "外链图片需转存至平台但凭据缺失: %s",
        #F 段: 投递(SP4a 起启用; F0 覆盖「未配置/解密失败/已过期/未认证」, 一律明确回显不静默)
        "F0": "凭据无效、缺失或已过期",
        "F1": "幂等命中, 已投递",
        "F2": "请求过于频繁, 请稍后再试",
        "F3": "平台拒绝了本次请求",
        "F4": "投递前需要人工二次确认",
        "F5": "已超出撤销窗, 不可撤销",
        "F6": "自动发布能力未开启(须人工确认后发布)",
        #G 段: MCP 与令牌(SP4b 追加 G2/G3: mcpinvoke 薄入口的工具路由与下游转发)
        "G0": "令牌无效",
        "G1": "令牌权限不足",
        "G2": "未知的 MCP 工具",
        "G3": "下游服务调用失败",
    },
}

CONST_ERROR_wordList["contenthub"] = {}
for _lang in ("EN", "CN"):
    #以 default 为底 -> 叠加 account -> 叠加 contentHub 新码段
    _wordList = dict(CONST_ERROR_wordList["default"].get(_lang, {}))
    _wordList.update(CONST_ERROR_wordList["account"].get(_lang, {}))
    _wordList.update(_CH_ERROR_WORD.get(_lang, {}))
    CONST_ERROR_wordList["contenthub"][_lang] = _wordList
#===== contentHub 专用消息键 end =====


#生成器产物(database/auto_generated/auto_gen_code_ch_*.py)硬编码 msgKey="applicationMsgKey",
#而 contentHub 统一使用 "contenthub"; 这里用别名归一, 保证生成件零改动且错误码不再静默回落 default。
MSG_KEY_ALIAS = {
    "applicationMsgKey": "contenthub",
}

#contentHub 命令处理器的默认消息键(供 main/subfunc/apiCommon.py 使用)
DEFAULT_MSG_KEY = "contenthub"


def resolveMsgKey(msgKey):
    """msgKey 归一: 别名 -> 真实键; 未知键回落 default(与基线 rtnMSG 的回落行为保持一致)"""
    result = MSG_KEY_ALIAS.get(msgKey, msgKey)
    if result not in CONST_ERROR_wordList:
        result = "default"
    return result


def rtnMSG(errCode, field = '', lang = "CN", msgKey = "default"):
    """统一返回报文封装。逻辑与基线 common/funcCommon.py 的 rtnMSG 完全一致,
       仅增加一步 msgKey 别名归一(applicationMsgKey -> contenthub)。
       返回 {"MSG": {"errCode", "content"}, "msgKey"}; errCode == "ERROR" 时以 field 作为错误码。"""
    result = {}

    if errCode == "ERROR": #修正一个错误
        errCode = field

    msgKey = resolveMsgKey(msgKey)
    if lang not in CONST_ERROR_wordList[msgKey]:
        lang = "EN"
    wordList = CONST_ERROR_wordList[msgKey][lang]

    if errCode in wordList:
        word = wordList[errCode]
        if len(word.split('%s')) > 1:
            word = word % (field)
    else:
        word = f'exception. unknow error ID,errCode:{errCode},field:{field}'

    result["MSG"] = {"errCode": str(errCode), "content": word}
    result["msgKey"] = msgKey

    return result


#deprecated: 基线缺陷 E1(索引层级与 rtnMSG 不一致)按决策 12.5 保留未修 —— 全仓无外部调用方,
#            删除风险大于收益; 新代码请统一使用 rtnMSG 的 MSG 结构。
def getErrMsg(errCode, field = "", lang = "CN", msgKey = "default"):
    result = ""
    wordList = CONST_ERROR_wordList[resolveMsgKey(msgKey)]
    if lang not in wordList:
        lang = "EN"
    if errCode in wordList[lang]:
        word = wordList[lang][errCode]
        if len(word.split('%s')) > 1:
            word = word % (field)
    else:
        word = f'exception. unknow error ID,errCode:{errCode},field:{field}'
    result = word

    return result


#其他系统的消息翻译
TRANS_OTHER_MSG = {
    "EN-CN": {
        "the number of sms messages sent from a single mobile number every day exceeds the upper limit": "向对应号码发送的短信数量超过当日最大数量",
    },
    "CN-EN": {
    },
}


def transOtherMsg(msg, lang):
    result = msg
    if lang == "CN":
        transTag = "EN-CN"
    else:
        transTag = "CN-EN"
    newMsg = TRANS_OTHER_MSG[transTag].get(msg)
    if newMsg:
        result = newMsg
    return result


if __name__ == "__main__":
    pass
    print("errMsgCommon msgKeyList:", list(CONST_ERROR_wordList.keys()))
    print("contenthub EN keys:", len(CONST_ERROR_wordList["contenthub"]["EN"]))
    print("sample:", rtnMSG("C2", "", "CN", "applicationMsgKey"))
