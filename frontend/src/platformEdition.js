export const PLATFORM_EDITIONS = Object.freeze({
  student: { path: '/student', label: '学生版', accountLabel: '学号' },
  teacher: { path: '/teacher', label: '教师版', accountLabel: '工号' },
  admin: { path: '/admin', label: '管理员版', accountLabel: '管理员账号' },
})

const isEdition = edition => Object.hasOwn(PLATFORM_EDITIONS, edition)

export function getPlatformEdition(pathname = globalThis.location?.pathname || '/') {
  const segment = pathname.split('/').filter(Boolean)[0]
  return isEdition(segment) ? segment : 'student'
}

export function editionUrl(location = globalThis.location) {
  return PLATFORM_EDITIONS[getPlatformEdition(location?.pathname)].path
    + (location?.search || '') + (location?.hash || '')
}

export const editionSessionKey = edition => isEdition(edition) ? `platform-session-v1:${edition}` : null

export function readEditionToken(edition = getPlatformEdition(), storage = globalThis.localStorage) {
  const key = editionSessionKey(edition)
  return key ? storage?.getItem(key) || null : null
}

export function saveEditionSession(user, token, edition = getPlatformEdition(), storage = globalThis.localStorage) {
  if (!isEdition(edition) || user.role !== edition || !token) {
    throw new Error('该账号不属于当前版本，请使用对应身份的账号登录。')
  }
  storage.setItem(editionSessionKey(edition), token)
}

export function clearEditionSession(edition = getPlatformEdition(), storage = globalThis.localStorage) {
  const key = editionSessionKey(edition)
  if (key) storage?.removeItem(key)
}
