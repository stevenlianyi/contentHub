// ============================================================
// sessionID 本地读写（自基线工程 src/utils/accessToken.js 移植）
// ------------------------------------------------------------
// 相对基线的修复：
//   removeAccessToken 只删除 tokenTableName 这一个键，
//   不得使用 sessionStorage.clear()（基线 accessToken.js:36 会连带抹掉其他页面偏好数据）。
// 注意：sessionID 同时会写入请求体（计划 §2.4.2），本文件只负责本地持久化。
// ============================================================
import { storage, tokenTableName } from '@/config/settings'

function resolveStorage() {
  if (storage === 'localStorage') return localStorage
  if (storage === 'sessionStorage') return sessionStorage
  return localStorage
}

export function getAccessToken() {
  try {
    return resolveStorage().getItem(tokenTableName)
  } catch (error) {
    console.error('[accessToken] 读取会话失败：', error)
    return null
  }
}

export function setAccessToken(accessToken) {
  try {
    resolveStorage().setItem(tokenTableName, accessToken)
  } catch (error) {
    console.error('[accessToken] 写入会话失败：', error)
  }
}

export function removeAccessToken() {
  try {
    resolveStorage().removeItem(tokenTableName)
  } catch (error) {
    console.error('[accessToken] 清除会话失败：', error)
  }
}
