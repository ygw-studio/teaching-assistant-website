import test from 'node:test'
import assert from 'node:assert/strict'
import { PLATFORM_EDITIONS, getPlatformEdition, editionUrl, readEditionToken, saveEditionSession, clearEditionSession } from '../src/platformEdition.js'
import { requestHeaders } from '../src/api/request.js'

const makeStorage = () => {
  const data = new Map()
  return { getItem: key => data.get(key) || null, setItem: (key, value) => data.set(key, value), removeItem: key => data.delete(key) }
}

test('each edition has its own path; root and old URLs enter the student edition', () => {
  for (const edition of Object.keys(PLATFORM_EDITIONS)) {
    assert.equal(getPlatformEdition(`/${edition}`), edition)
    assert.equal(getPlatformEdition(`/${edition}/`), edition)
  }
  for (const path of ['/', '/frontend/dist/', '/unknown', '/constructor', '/teacher-imitation']) {
    assert.equal(getPlatformEdition(path), 'student')
  }
})

test('canonical URLs preserve course query parameters and hashes', () => {
  assert.equal(editionUrl({ pathname: '/', search: '?chapter=ds-1', hash: '#lesson' }), '/student?chapter=ds-1#lesson')
  assert.equal(editionUrl({ pathname: '/teacher/', search: '?v=2' }), '/teacher?v=2')
  assert.equal(editionUrl({ pathname: '/admin' }), '/admin')
})

test('three editions can retain separate sessions at the same time', () => {
  const storage = makeStorage()
  for (const role of Object.keys(PLATFORM_EDITIONS)) saveEditionSession({ role }, `token-${role}`, role, storage)
  for (const role of Object.keys(PLATFORM_EDITIONS)) assert.equal(readEditionToken(role, storage), `token-${role}`)
  clearEditionSession('teacher', storage)
  assert.equal(readEditionToken('teacher', storage), null)
  assert.equal(readEditionToken('student', storage), 'token-student')
  assert.equal(readEditionToken('admin', storage), 'token-admin')
})

test('wrong-role sessions cannot be stored in an edition', () => {
  const storage = makeStorage()
  assert.throws(() => saveEditionSession({ role: 'admin' }, 'token', 'student', storage))
  assert.throws(() => saveEditionSession({ role: 'teacher' }, 'token', 'admin', storage))
  assert.throws(() => saveEditionSession({ role: 'student' }, '', 'student', storage))
  assert.equal(readEditionToken('student', storage), null)
})

test('old global demo sessions are not reused by any edition', () => {
  const storage = makeStorage()
  storage.setItem('access_token', 'old-demo-admin')
  for (const edition of Object.keys(PLATFORM_EDITIONS)) assert.equal(readEditionToken(edition, storage), null)
  assert.equal(readEditionToken('unknown', storage), null)
})

test('requests select the matching edition token instead of the global token', () => {
  const oldLocation = globalThis.location
  const oldStorage = globalThis.localStorage
  try {
    globalThis.localStorage = makeStorage()
    globalThis.localStorage.setItem('access_token', 'old-global-token')
    for (const role of Object.keys(PLATFORM_EDITIONS)) saveEditionSession({ role }, `token-${role}`, role)
    for (const role of Object.keys(PLATFORM_EDITIONS)) {
      globalThis.location = { pathname: `/${role}` }
      const headers = requestHeaders()
      assert.equal(headers.get('X-Platform-Edition'), role)
      assert.equal(headers.get('Authorization'), `Bearer token-${role}`)
    }
  } finally {
    globalThis.location = oldLocation
    globalThis.localStorage = oldStorage
  }
})

test('exit flushing preserves explicitly pinned student credentials', () => {
  const oldLocation = globalThis.location
  const oldStorage = globalThis.localStorage
  try {
    globalThis.location = { pathname: '/admin' }
    globalThis.localStorage = makeStorage()
    saveEditionSession({ role: 'admin' }, 'admin-token', 'admin')
    const headers = requestHeaders({ Authorization: 'Bearer captured-student-token', 'X-Platform-Edition': 'student', 'Content-Type': 'text/plain' })
    assert.equal(headers.get('Authorization'), 'Bearer captured-student-token')
    assert.equal(headers.get('X-Platform-Edition'), 'student')
    assert.equal(headers.get('Content-Type'), 'text/plain')
    const anonymous = requestHeaders({ 'X-Platform-Edition': 'teacher' })
    assert.equal(anonymous.has('Authorization'), false)
  } finally {
    globalThis.location = oldLocation
    globalThis.localStorage = oldStorage
  }
})
