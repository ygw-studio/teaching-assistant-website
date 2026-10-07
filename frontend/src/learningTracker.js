import { apiRequest } from './api/request.js'
import { readEditionToken } from './platformEdition.js'

export function createEventQueue({ send, storage, key, now = () => new Date(), id = () => crypto.randomUUID() }) {
  let queue = []
  let delivery = null
  let saveTimer
  try { queue = JSON.parse(storage.getItem(key) || '[]'); if (!Array.isArray(queue)) queue = [] } catch { queue = [] }
  const persist = () => { clearTimeout(saveTimer); try { storage.setItem(key, JSON.stringify(queue)) } catch { window.dispatchEvent(new Event('learning-storage-full')) } }
  return {
    push(value) { const event = { event_id: id(), occurred_at: now().toISOString(), ...value }; queue.push(event); clearTimeout(saveTimer); saveTimer = setTimeout(persist, 500); return event },
    persist,
    pending: () => queue,
    flush(keepalive = false) {
      persist()
      if (delivery) return delivery
      if (!queue.length) return Promise.resolve()
      delivery = (async () => {
        while (queue.length) {
          const batch = queue.slice(0, 50)
          await send(batch, keepalive)
          const completed = new Set(batch.map(event => event.event_id))
          queue = queue.filter(event => !completed.has(event.event_id))
          persist()
          if (keepalive) break
        }
      })().finally(() => { delivery = null })
      return delivery
    },
  }
}

let current = null
export const trackLearning = (eventType, metadata = {}) => current?.record(eventType, metadata)
export const setLearningContext = context => current?.setContext(context)
export const setAiPanelVisible = open => current?.setAi(open)
export const flushLearning = () => current?.checkpointAndFlush() || Promise.resolve()
export async function endLearningTracker() {
  const owner = current
  current = null
  if (owner) await owner.stop()
}

export function startLearningTracker(user) {
  current?.stop()
  current = null
  if (user?.role !== 'student') return () => {}
  let tab = sessionStorage.getItem('learning-tab-id')
  if (!tab) { tab = crypto.randomUUID(); sessionStorage.setItem('learning-tab-id', tab) }
  const token = readEditionToken('student')
  const sendEvents = (events, keepalive = false) => apiRequest('/classroom/events', { method: 'POST', headers: { Authorization: `Bearer ${token}`, 'X-Platform-Edition': 'student' }, body: JSON.stringify({ events }), keepalive })
  let context = { page: 'home', courseId: null, attemptId: null }
  let last = performance.now()
  let visible = !document.hidden
  let aiOpen = false
  let stopped = false
  let checkpointSequence = 0
  const queue = createEventQueue({ storage: localStorage, key: `learning-events-v1:${user.accountId}:${tab}`,
    send: sendEvents,
  })
  const record = (eventType, metadata = {}) => queue.push({ event_type: eventType, session_id: tab, course_id: context.courseId || null,
    attempt_id: context.attemptId || null, metadata: { page: context.page, ...metadata } })
  const checkpoint = () => {
    const at = performance.now()
    const elapsed = Math.min(90000, Math.max(0, at - last))
    last = at
    if (visible && elapsed > 0) record('activity.interval', { visible_ms: Math.round(elapsed), ai_visible_ms: aiOpen ? Math.round(elapsed) : 0, sequence: ++checkpointSequence })
  }
  const flush = async keepalive => {
    try { await queue.flush(keepalive); window.dispatchEvent(new Event('learning-records-flushed')) } catch { /* Original event IDs remain queued for retry. */ }
  }
  const recover = async () => {
    const prefix = `learning-events-v1:${user.accountId}:`
    const ownKey = prefix + tab
    const keys = []
    for (let index = 0; index < localStorage.length; index++) { const key = localStorage.key(index); if (key?.startsWith(prefix) && key !== ownKey) keys.push(key) }
    for (const key of keys) {
      if (stopped) return
      try {
        const saved = JSON.parse(localStorage.getItem(key) || '[]')
        if (!Array.isArray(saved) || !saved.length) continue
        for (let offset = 0; offset < saved.length; offset += 50) {
          if (stopped) return
          const batch = saved.slice(offset, offset + 50)
          await sendEvents(batch)
          const ids = new Set(batch.map(event => event.event_id))
          const latest = JSON.parse(localStorage.getItem(key) || '[]')
          localStorage.setItem(key, JSON.stringify(latest.filter(event => !ids.has(event.event_id))))
        }
        window.dispatchEvent(new Event('learning-records-flushed'))
      } catch { /* A later login / network recovery retries the original IDs. */ }
    }
  }
  const visibility = () => { checkpoint(); visible = !document.hidden; record(visible ? 'page.visible' : 'page.hidden', { is_visible: visible }); flush(true) }
  const click = event => {
    const button = event.target.closest?.('button,summary,a')
    if (!button) return
    record('ui.click', { action: (button.getAttribute('aria-label') || button.textContent || '').trim().slice(0, 80), x: Math.round(event.clientX), y: Math.round(event.clientY) })
  }
  const scrollTimes = new WeakMap()
  const scroll = event => {
    const target = event.target === document ? document.scrollingElement : event.target
    if (!target || typeof target.scrollTop !== 'number') return
    const at = performance.now()
    if (at - (scrollTimes.get(target) || -1000) < 750) return
    scrollTimes.set(target, at)
    record('ui.scroll', { scroll_top: Math.round(target.scrollTop), scroll_left: Math.round(target.scrollLeft) })
  }
  const leave = (keepalive = true) => { checkpoint(); visible = false; record('page.leave'); queue.persist(); return flush(keepalive) }
  const hide = () => leave(true)
  const timer = window.setInterval(() => { checkpoint(); flush(false) }, 15000)
  const online = () => { flush(false); recover() }
  const show = event => { if (event.persisted) { last = performance.now(); visible = !document.hidden; record('page.open'); online() } }
  document.addEventListener('visibilitychange', visibility)
  document.addEventListener('click', click, true)
  document.addEventListener('scroll', scroll, true)
  window.addEventListener('pagehide', hide)
  window.addEventListener('online', online)
  window.addEventListener('pageshow', show)
  current = {
    record,
    setContext(next) { if (context.page === next.page && context.courseId === next.courseId && context.attemptId === next.attemptId) return; checkpoint(); record('page.leave'); context = next; record('page.open') },
    setAi(open) { if (aiOpen === open) return; checkpoint(); aiOpen = open; record(open ? 'ai.open' : 'ai.close') },
    async checkpointAndFlush() { checkpoint(); await flush(false) },
    stop() {
      if (stopped) return
      stopped = true; const delivered = leave(false); window.clearInterval(timer)
      document.removeEventListener('visibilitychange', visibility)
      document.removeEventListener('click', click, true)
      document.removeEventListener('scroll', scroll, true)
      window.removeEventListener('pagehide', hide); window.removeEventListener('online', online)
      window.removeEventListener('pageshow', show)
      return delivered
    },
  }
  record('page.open'); flush(false); recover()
  const owner = current
  return () => { owner.stop(); if (current === owner) current = null }
}
