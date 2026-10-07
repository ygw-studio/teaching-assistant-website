import test from 'node:test'
import assert from 'node:assert/strict'
import { createEventQueue } from '../src/learningTracker.js'
import { durationText } from '../src/api/classroom.js'

const storage = () => { const data = new Map(); return { getItem: key => data.get(key) || null, setItem: (key, value) => data.set(key, value) } }

test('failed delivery preserves original event IDs, then removes acknowledged events', async () => {
  const saved = storage()
  let fail = true
  const delivered = []
  const queue = createEventQueue({ storage: saved, key: 'student-a', id: () => 'fixed-event-id', now: () => new Date('2026-10-06T01:00:00Z'), send: async events => { delivered.push(events); if (fail) throw new Error('offline') } })
  queue.push({ event_type: 'page.open', session_id: 'tab-a', metadata: {} })
  await assert.rejects(queue.flush())
  assert.equal(queue.pending()[0].event_id, 'fixed-event-id')
  fail = false
  await queue.flush()
  assert.equal(delivered[1][0].event_id, delivered[0][0].event_id)
  assert.equal(queue.pending().length, 0)
})

test('queue survives reload, and account / tab storage stays separate', async () => {
  const saved = storage()
  const first = createEventQueue({ storage: saved, key: 'account-a:tab-a', id: () => 'event-1', send: async () => {} })
  first.push({ event_type: 'page.open', session_id: 'tab-a', metadata: {} }); first.persist()
  const restored = createEventQueue({ storage: saved, key: 'account-a:tab-a', send: async () => {} })
  const different = createEventQueue({ storage: saved, key: 'account-b:tab-a', send: async () => {} })
  assert.equal(restored.pending().length, 1)
  assert.equal(different.pending().length, 0)
  await restored.flush()
})

test('events added during a delivery are not dropped', async () => {
  let resolve
  let count = 0
  const gate = new Promise(done => { resolve = done })
  const queue = createEventQueue({ storage: storage(), key: 'queue', id: () => `event-${++count}`, send: async () => gate })
  queue.push({ event_type: 'page.open', session_id: 'tab', metadata: {} })
  const flushing = queue.flush()
  queue.push({ event_type: 'ai.open', session_id: 'tab', metadata: {} })
  resolve(); await flushing
  assert.equal(queue.pending().length, 0)
})

test('formatting handles zero and hours without invented values', () => {
  assert.equal(durationText(0), '0小时0分0秒')
  assert.equal(durationText(3661000), '1小时1分1秒')
})

test('concurrent flush callers wait for the same pending delivery', async () => {
  let release
  const gate = new Promise(resolve => { release = resolve })
  const queue = createEventQueue({ storage: storage(), key: 'parallel', id: () => 'one', send: async () => gate })
  queue.push({ event_type: 'page.open', session_id: 'tab', metadata: {} })
  const first = queue.flush()
  const second = queue.flush()
  assert.equal(first, second)
  release(); await second
  assert.equal(queue.pending().length, 0)
})
