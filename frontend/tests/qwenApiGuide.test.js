import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { QWEN_API_GUIDE_STEPS } from '../src/qwenApiGuideSteps.js'

test('the guide contains five distinct steps in the supplied order', () => {
  assert.deepEqual(QWEN_API_GUIDE_STEPS.map(step => step.number), [1, 2, 3, 4, 5])
  assert.equal(new Set(QWEN_API_GUIDE_STEPS.map(step => step.image)).size, 5)
  for (const step of QWEN_API_GUIDE_STEPS) {
    assert.ok(step.title && step.description)
    assert.match(step.image, /^guides\/qwen-api\/step-[1-5]\.png$/)
  }
})

test('all tutorial images exist and reserve their actual PNG dimensions', async () => {
  for (const step of QWEN_API_GUIDE_STEPS) {
    const png = await readFile(new URL(`../public/${step.image}`, import.meta.url))
    assert.equal(png.subarray(0, 8).toString('hex'), '89504e470d0a1a0a')
    assert.equal(png.readUInt32BE(16), step.width)
    assert.equal(png.readUInt32BE(20), step.height)
  }
})
