#! /usr/bin/env python3
#encoding: utf-8:

#Filename: credentialCipher.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-19
#Description:   contentHub 凭据加解密公共件(SP4a · C6 投递链路前置, 主计划 6.4 R-19 / P3-1)。
#
#职责(对称接口, AES-256-GCM):
#  1) encrypt(plainText)  -> {"cipher": base64(cipher+tag), "iv": base64(iv), "alg": "AES-256-GCM"}
#  2) decrypt(cipher, iv) -> 明文串(解密失败/密钥缺失/篡改一律显式报错, **绝不静默降级**)
#  3) getMasterKey()      -> 32 字节密钥(经**环境变量** CH_CREDENTIAL_KEY 注入, 本机无 KMS)
#
#★ 密钥红线(主计划 R-19, 见 code/src/plan.md §4「凭据加密方案与密钥来源」):
#  - 密钥**不入库**(ch_account 只存 credentialCipher/credentialIV, 明文与密钥永不落库);
#  - 密钥**不入代码库**(本文件不含任何密钥字面量, 仅读环境变量);
#  - 审计/日志中不得出现凭据明文(调用方需用 maskSecret 脱敏);
#  - 无密钥时**不崩溃**: encrypt/decrypt 抛 CredentialCipherError(携带 contenthub 错误码 F0),
#    由业务层(publishService)映射为明确报文。
#
#密钥格式(环境变量 CH_CREDENTIAL_KEY, 按序尝试, 命中 32 字节即采用):
#  ① 64 位十六进制串; ② base64(解出 32 字节); ③ 32 字节原文;
#  ④ 长度 >=16 的口令串 -> sha256 派生 32 字节(便于本机自验; 生产建议直接给 32 字节随机值)
#
#★ 分层契约: 本文件属公共层(common/), 只依赖标准库;**cryptography 采取函数内延迟导入**,
#  保证「未安装 cryptography」时本模块仍可被 import(import 不失败), 仅在实际加解密时报错。
#
#错误码(contenthub msgKey): F0 凭据无效/缺失/解密失败/密钥未配置(投递段; 见 common/errMsgCommon.py)

_VERSION="20260919"


import base64
import hashlib
import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parentdir not in sys.path:
    sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #setdefaultencoding('utf-8')


#===== 常量与错误码 begin =====

#错误码落点(common/errMsgCommon.py::_CH_ERROR_WORD 的 contenthub F 段, 投递)
ERR_CREDENTIAL = "F0"            #凭据无效/缺失/过期/解密失败/密钥未配置

#密钥环境变量名(**唯一来源**, 不落代码库)
KEY_ENV_NAME = "CH_CREDENTIAL_KEY"

#AES-256-GCM 参数
ALGORITHM = "AES-256-GCM"
KEY_BYTES = 32                   #AES-256
IV_BYTES = 12                    #GCM 推荐 96bit
MIN_PASSPHRASE_BYTES = 16        #口令派生最小长度

#===== 常量与错误码 end =====


#===== 异常 begin =====

class CredentialCipherError(Exception):
    """凭据加解密异常: 携带 contenthub 错误码(一律 F0), 由业务层映射为 HTTP 报文"""
    def __init__(self, errCode, message, field = ""):
        super().__init__(message)
        self.errCode = errCode
        self.field = field
        self.message = message

#===== 异常 end =====


#===== 通用小工具 begin =====

def _toStr(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _b64e(rawBytes):
    return base64.b64encode(rawBytes).decode("ascii")


def _b64d(text):
    return base64.b64decode(_toStr(text).encode("ascii"))


def _loadAesGcm(keyBytes):
    """延迟导入 cryptography 的 AESGCM(未安装时显式报错, 不静默降级)"""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.exceptions import InvalidTag
    except Exception as e:
        raise CredentialCipherError(ERR_CREDENTIAL,
                                    f"加密依赖 cryptography 不可用: {str(e)} (请 pip install cryptography)")
    return AESGCM(keyBytes), InvalidTag

#===== 通用小工具 end =====


#===== 密钥解析 begin =====

def decodeKeyMaterial(rawKey):
    """把环境变量/入参的原样密钥归一为 32 字节; 无法归一返回 b""(调用方报错)"""
    text = _toStr(rawKey)
    if not text:
        return b""

    #① 十六进制(64 位)
    try:
        hexBytes = bytes.fromhex(text)
        if len(hexBytes) == KEY_BYTES:
            return hexBytes
    except Exception:
        pass

    #② base64
    try:
        b64Bytes = base64.b64decode(text, validate = True)
        if len(b64Bytes) == KEY_BYTES:
            return b64Bytes
    except Exception:
        pass

    #③ 32 字节原文
    rawBytes = text.encode("utf-8")
    if len(rawBytes) == KEY_BYTES:
        return rawBytes

    #④ 口令派生(>=16 字节)
    if len(rawBytes) >= MIN_PASSPHRASE_BYTES:
        return hashlib.sha256(rawBytes).digest()

    return b""


def isKeyConfigured(rawKey = None):
    """密钥是否已配置(环境变量或入参); 供诊断/健康检查使用, 不抛异常"""
    if rawKey is None:
        rawKey = os.getenv(KEY_ENV_NAME, "")
    return bool(decodeKeyMaterial(rawKey))


def getMasterKey(rawKey = None):
    """取 32 字节主密钥: 缺省读环境变量 CH_CREDENTIAL_KEY。
       ★ 密钥不落库、不入代码库; 未配置/非法时抛 CredentialCipherError(F0), **不静默降级**。"""
    if rawKey is None:
        rawKey = os.getenv(KEY_ENV_NAME, "")

    keyBytes = decodeKeyMaterial(rawKey)
    if not keyBytes:
        raise CredentialCipherError(ERR_CREDENTIAL,
                                    f"凭据密钥未配置或非法: 请设置环境变量 {KEY_ENV_NAME}"
                                    f"(64 位 hex / base64(32字节) / 32字节原文 / >=16字节口令)")
    return keyBytes

#===== 密钥解析 end =====


#===== 加解密 begin =====

def encrypt(plainText, rawKey = None, aad = None):
    """AES-256-GCM 加密。
       入参: plainText 明文串; rawKey 可选(缺省取环境变量); aad 可选附加认证数据(串)。
       出参: {"cipher": base64(密文+认证标签), "iv": base64(iv), "alg": "AES-256-GCM"}
       ★ 只返回密文与 IV, 不含任何明文/密钥; 空明文视为非法入参(F0)。"""
    text = _toStr(plainText)
    if not text:
        raise CredentialCipherError(ERR_CREDENTIAL, "待加密凭据为空")

    keyBytes = getMasterKey(rawKey)
    aesGcm, _invalidTag = _loadAesGcm(keyBytes)

    iv = os.urandom(IV_BYTES)
    aadBytes = _toStr(aad).encode("utf-8") if aad else None
    cipherBytes = aesGcm.encrypt(iv, text.encode("utf-8"), aadBytes)

    return {"cipher": _b64e(cipherBytes), "iv": _b64e(iv), "alg": ALGORITHM}


def decrypt(cipherText, iv, rawKey = None, aad = None):
    """AES-256-GCM 解密(与 encrypt 对称)。
       入参: cipherText(base64 密文+标签) / iv(base64) / rawKey 可选 / aad 可选。
       ★ 解密失败(GCM 认证不通过/密文被篡改/密钥不匹配/密钥缺失)一律抛 CredentialCipherError(F0)。"""
    cipherText = _toStr(cipherText)
    iv = _toStr(iv)
    if not cipherText or not iv:
        raise CredentialCipherError(ERR_CREDENTIAL, "凭据密文或 IV 为空(凭据未写入或已损坏)")

    keyBytes = getMasterKey(rawKey)
    aesGcm, invalidTag = _loadAesGcm(keyBytes)

    try:
        ivBytes = _b64d(iv)
        cipherBytes = _b64d(cipherText)
    except Exception as e:
        raise CredentialCipherError(ERR_CREDENTIAL, f"凭据密文/IV 非合法 base64: {str(e)}")

    aadBytes = _toStr(aad).encode("utf-8") if aad else None
    try:
        plainBytes = aesGcm.decrypt(ivBytes, cipherBytes, aadBytes)
    except invalidTag:
        raise CredentialCipherError(ERR_CREDENTIAL,
                                    "凭据解密失败: GCM 认证不通过(密文被篡改或密钥不匹配)")
    except Exception as e:
        raise CredentialCipherError(ERR_CREDENTIAL, f"凭据解密失败: {str(e)}")

    try:
        return plainBytes.decode("utf-8")
    except Exception:
        raise CredentialCipherError(ERR_CREDENTIAL, "凭据解密结果非 UTF-8 文本")

#===== 加解密 end =====


#===== 脱敏与摘要 begin =====

def maskSecret(text, keepHead = 2, keepTail = 2):
    """凭据脱敏(日志/审计用): 只保留首尾少量字符; 空串返回 \"\"。
       ★ 审计与日志中不得出现凭据明文 —— 调用方应统一经本函数处理。"""
    text = _toStr(text)
    if not text:
        return ""
    keepHead = max(int(keepHead or 0), 0)
    keepTail = max(int(keepTail or 0), 0)
    if len(text) <= keepHead + keepTail:
        return "*" * len(text)
    return text[:keepHead] + "*" * (len(text) - keepHead - keepTail) + text[-keepTail:]


def sha256Hex(text):
    """sha256 hexdigest(明文摘要口径; 供审计 payloadDigest 复用)"""
    if text is None:
        text = ""
    if not isinstance(text, str):
        text = str(text)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

#===== 脱敏与摘要 end =====


if __name__ == "__main__":
    pass
    #本地自测(不连库/不联网): 只验证加解密往返与无密钥行为
    print("keyConfigured:", isKeyConfigured())
    try:
        #自造口令做往返(仅本机自测, 不写任何真实凭据)
        _key = "local-self-test-passphrase-0123456789"
        _rtn = encrypt("demo-secret-42", rawKey = _key)
        print("cipher len:", len(_rtn["cipher"]), "iv len:", len(_rtn["iv"]))
        print("roundtrip:", decrypt(_rtn["cipher"], _rtn["iv"], rawKey = _key) == "demo-secret-42")
        print("masked:", maskSecret("demo-secret-42"))
    except CredentialCipherError as e:
        print("CredentialCipherError:", e.errCode, e.message)
