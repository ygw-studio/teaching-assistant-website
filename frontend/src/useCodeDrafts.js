import { useCallback, useEffect, useRef, useState } from 'react'
import { draftApi } from './api/drafts'

const SAVE_DELAY_MS = 800

const storageKey = (accountId, scope, resourceId) =>
  `code_draft_v1:${encodeURIComponent(accountId)}:${scope}:${encodeURIComponent(resourceId)}`

function readLocalDraft(accountId, scope, resourceId) {
  try {
    const saved = localStorage.getItem(storageKey(accountId, scope, resourceId))
      || (scope === 'experiment'
        ? localStorage.getItem(`practice_draft_v1:${encodeURIComponent(accountId)}:${encodeURIComponent(resourceId)}`)
        : null)
    const value = JSON.parse(saved)
    if (typeof value?.code !== 'string' || typeof value?.stdin !== 'string') return null
    return value
  } catch (_) {
    return null
  }
}

function writeLocalDraft(accountId, scope, resourceId, draft) {
  try {
    localStorage.setItem(storageKey(accountId, scope, resourceId), JSON.stringify(draft))
    return true
  } catch (_) {
    return false
  }
}

export function useCodeDrafts(accountId, scope, entries, activeResourceId) {
  const [drafts, setDrafts] = useState(() => Object.fromEntries(
    entries.map((entry) => [entry.id,
      readLocalDraft(accountId, scope, entry.id) || {
        code: entry.code, stdin: entry.defaultStdin || '', updated_at: '', pending: false,
      },
    ]),
  ))
  const [statuses, setStatuses] = useState(() => Object.fromEntries(
    entries.map((entry) => [entry.id,
      readLocalDraft(accountId, scope, entry.id) ? '已恢复本机草稿' : '编辑后自动保存',
    ]),
  ))
  const draftsRef = useRef(drafts)
  const timersRef = useRef(new Map())
  const requestsRef = useRef(new Map())
  const localWritesRef = useRef(new Map())

  const setStatus = useCallback((problemId, status) => {
    setStatuses((current) => ({ ...current, [problemId]: status }))
  }, [])

  useEffect(() => {
    const missing = entries.filter((entry) => !draftsRef.current[entry.id])
    if (missing.length) {
      const additions = Object.fromEntries(missing.map((entry) => [entry.id,
        readLocalDraft(accountId, scope, entry.id) || {
          code: entry.code, stdin: entry.defaultStdin || '', updated_at: '', pending: false,
        },
      ]))
      draftsRef.current = { ...draftsRef.current, ...additions }
      setDrafts(draftsRef.current)
      setStatuses((current) => ({ ...current, ...Object.fromEntries(missing.map((entry) => [
        entry.id, additions[entry.id].updated_at ? '已恢复本机草稿' : '编辑后自动保存',
      ])) }))
    }
  }, [accountId, scope, entries])

  const syncDraft = useCallback((problemId, draft, options = {}) => {
    const previous = requestsRef.current.get(problemId) || Promise.resolve()
    const request = previous.catch(() => {}).then(() =>
      draftApi.save(scope, problemId, draft.code, draft.stdin, options),
    )
    requestsRef.current.set(problemId, request)
    request.then((remote) => {
      if (draftsRef.current[problemId]?.updated_at === draft.updated_at) {
        const saved = { ...draftsRef.current[problemId], updated_at: remote.updated_at, pending: false }
        draftsRef.current = { ...draftsRef.current, [problemId]: saved }
        setDrafts(draftsRef.current)
        writeLocalDraft(accountId, scope, problemId, saved)
        setStatus(problemId, '已保存到当前账号')
      }
    }).catch(() => {
      if (draftsRef.current[problemId]?.updated_at === draft.updated_at) {
        setStatus(problemId, localWritesRef.current.get(problemId) === false
          ? '保存失败，请复制代码后重试'
          : '已保存在本机，服务器暂不可用')
      }
    }).finally(() => {
      if (requestsRef.current.get(problemId) === request) requestsRef.current.delete(problemId)
    })
    return request
  }, [accountId, scope, setStatus])

  const scheduleSync = useCallback((problemId, draft) => {
    const previous = timersRef.current.get(problemId)
    if (previous) window.clearTimeout(previous.timer)
    const timer = window.setTimeout(() => {
      timersRef.current.delete(problemId)
      syncDraft(problemId, draft)
    }, SAVE_DELAY_MS)
    timersRef.current.set(problemId, { timer, draft })
  }, [syncDraft])

  const updateDraft = useCallback((problemId, patch) => {
    const next = {
      ...draftsRef.current[problemId],
      ...patch,
      updated_at: new Date().toISOString(),
      pending: true,
    }
    draftsRef.current = { ...draftsRef.current, [problemId]: next }
    setDrafts(draftsRef.current)
    const stored = writeLocalDraft(accountId, scope, problemId, next)
    localWritesRef.current.set(problemId, stored)
    setStatus(problemId, stored ? '正在自动保存...' : '本机空间不足，正在同步服务器...')
    scheduleSync(problemId, next)
  }, [accountId, scope, scheduleSync, setStatus])

  const flushDraft = useCallback((problemId) => {
    const pending = timersRef.current.get(problemId)
    if (!pending) return requestsRef.current.get(problemId) || Promise.resolve()
    window.clearTimeout(pending.timer)
    timersRef.current.delete(problemId)
    return syncDraft(problemId, pending.draft)
  }, [syncDraft])

  useEffect(() => {
    if (!activeResourceId) return undefined
    let active = true
    draftApi.get(scope, activeResourceId).then((remote) => {
      if (!active) return
      const local = readLocalDraft(accountId, scope, activeResourceId)
      const unsynced = draftsRef.current[activeResourceId]?.pending
        ? draftsRef.current[activeResourceId]
        : local?.pending ? local : null
      if (!remote) {
        if (unsynced || local) {
          setStatus(activeResourceId, '正在同步本机草稿...')
          scheduleSync(activeResourceId, unsynced || local)
        }
        return
      }
      if (unsynced) {
        setStatus(activeResourceId, '正在同步本机草稿...')
        scheduleSync(activeResourceId, unsynced)
        return
      }
      const restored = { code: remote.code, stdin: remote.stdin, updated_at: remote.updated_at, pending: false }
      draftsRef.current = { ...draftsRef.current, [activeResourceId]: restored }
      setDrafts(draftsRef.current)
      writeLocalDraft(accountId, scope, activeResourceId, restored)
      setStatus(activeResourceId, '已恢复账号草稿')
    }).catch(() => {
      if (!active) return
      const unsynced = draftsRef.current[activeResourceId]
      if (unsynced?.pending) scheduleSync(activeResourceId, unsynced)
      setStatus(activeResourceId, localWritesRef.current.get(activeResourceId) === false
        ? '本机空间不足，正在同步服务器...'
        : '服务器暂不可用，修改会先保存在本机')
    })
    return () => { active = false }
  }, [accountId, scope, activeResourceId, scheduleSync, setStatus])

  useEffect(() => () => {
    for (const [problemId, pending] of timersRef.current) {
      window.clearTimeout(pending.timer)
      syncDraft(problemId, pending.draft, { keepalive: true })
    }
    timersRef.current.clear()
  }, [syncDraft])

  return {
    drafts,
    status: statuses[activeResourceId] || '编辑后自动保存',
    updateDraft,
    flushDraft,
  }
}
