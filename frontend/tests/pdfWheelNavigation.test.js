import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createPdfWheelHandler } from '../src/pdfWheelNavigation.js'

function setup(options = {}) {
  let time = 0
  const state = { page: 2, totalPages: 5, busy: false, error: '', ...options }
  const viewport = { clientHeight: 300, scrollHeight: 300, scrollTop: 0 }
  const turns = []
  const handler = createPdfWheelHandler({
    viewport, getState: () => state, now: () => time,
    changePage: (page, direction) => { turns.push([page, direction]); state.page = page },
  })
  const wheel = (deltaY, overrides = {}, delay = 0) => {
    time += delay
    const event = {
      deltaY, deltaX: 0, deltaMode: 0, cancelable: true, prevented: false,
      preventDefault() { this.prevented = true }, ...overrides,
    }
    handler(event)
    return event
  }
  return { state, viewport, turns, wheel }
}

test('wheel down and up each turn one page after separate gestures', () => {
  const { wheel, turns } = setup()
  assert.equal(wheel(120).prevented, true)
  assert.equal(wheel(-120, {}, 400).prevented, true)
  assert.deepEqual(turns, [[3, 1], [2, -1]])
})

test('one large wheel movement and its inertial tail do not skip pages', () => {
  const { wheel, turns } = setup()
  wheel(2000)
  for (let i = 0; i < 30; i++) assert.equal(wheel(30, {}, 20).prevented, true)
  assert.deepEqual(turns, [[3, 1]])
  wheel(120, {}, 200)
  assert.deepEqual(turns, [[3, 1], [4, 1]])
})

test('small touchpad deltas accumulate, but an idle pause resets them', () => {
  const { wheel, turns } = setup()
  wheel(20)
  wheel(20, {}, 200)
  assert.equal(turns.length, 0)
  wheel(20, {}, 20)
  assert.deepEqual(turns, [[3, 1]])
})

test('opposite small deltas do not combine into an accidental page turn', () => {
  const { wheel, turns } = setup()
  wheel(30)
  wheel(-20, {}, 20)
  assert.equal(turns.length, 0)
  wheel(-20, {}, 20)
  assert.deepEqual(turns, [[1, -1]])
})

test('line and page wheel units are normalized', () => {
  for (const deltaMode of [1, 2]) {
    const { wheel, turns } = setup()
    wheel(deltaMode === 1 ? 3 : 1, { deltaMode })
    assert.deepEqual(turns, [[3, 1]])
  }
})

test('an enlarged sheet scrolls before paging at its bottom or top', () => {
  const { wheel, viewport, turns } = setup()
  viewport.scrollHeight = 600
  wheel(200)
  assert.equal(viewport.scrollTop, 200)
  wheel(200, {}, 20)
  assert.equal(viewport.scrollTop, 300)
  assert.equal(turns.length, 0)
  wheel(120, {}, 250)
  assert.deepEqual(turns, [[3, 1]])
  viewport.scrollTop = 100
  wheel(-120, {}, 400)
  assert.equal(viewport.scrollTop, 0)
  assert.equal(turns.length, 1)
  wheel(-120, {}, 250)
  assert.deepEqual(turns, [[3, 1], [2, -1]])
})

test('first and last boundaries allow the surrounding page to scroll', () => {
  const first = setup({ page: 1 })
  assert.equal(first.wheel(-120).prevented, false)
  assert.equal(first.turns.length, 0)
  const last = setup({ page: 5 })
  assert.equal(last.wheel(120).prevented, false)
  assert.equal(last.turns.length, 0)
})

test('the surrounding page is not trapped when a one-page PDF is at its boundary', () => {
  const { wheel, turns } = setup({ page: 1, totalPages: 1 })
  assert.equal(wheel(120).prevented, false)
  assert.equal(wheel(-120, {}, 200).prevented, false)
  assert.equal(turns.length, 0)
})

test('rendering suppresses page changes and unloaded or failed PDFs do not capture scroll', () => {
  const rendering = setup({ busy: true })
  assert.equal(rendering.wheel(120).prevented, true)
  assert.equal(rendering.turns.length, 0)
  for (const state of [{ totalPages: 0 }, { error: 'failed' }]) {
    const { wheel, turns } = setup(state)
    assert.equal(wheel(120).prevented, false)
    assert.equal(turns.length, 0)
  }
})

test('browser zoom, horizontal scroll and non-cancelable events are untouched', () => {
  for (const overrides of [{ ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { deltaX: 200 }, { cancelable: false }]) {
    const { wheel, turns } = setup()
    assert.equal(wheel(100, overrides).prevented, false)
    assert.equal(turns.length, 0)
  }
})
