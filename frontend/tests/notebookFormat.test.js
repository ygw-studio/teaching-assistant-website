import test from 'node:test'
import assert from 'node:assert/strict'
import { createCell, readNotebook, writeNotebook } from '../src/notebookFormat.js'

test('legacy Python drafts become a single code cell without losing source', () => {
  const [cell] = readNotebook('x = 5\nprint("你好")')
  assert.equal(cell.source, 'x = 5\nprint("你好")')
  assert.equal(cell.cell_type, 'code')
})

test('notebooks round trip code and markdown while persisted drafts exclude stale outputs', () => {
  const cells = [createCell('code', 'x = 5'), createCell('markdown', '# 标题')]
  cells[0].outputs = [{ output_type: 'stream', name: 'stdout', text: '5' }]
  cells[0].execution_count = 1
  const saved = JSON.parse(writeNotebook(cells))
  assert.equal(saved.nbformat, 4)
  assert.deepEqual(saved.cells[0].outputs, [])
  assert.equal(saved.cells[0].execution_count, null)
  assert.deepEqual(readNotebook(writeNotebook(cells)).map(cell => cell.source), ['x = 5', '# 标题'])
  const exported = JSON.parse(writeNotebook(cells, true))
  assert.equal(exported.cells[0].outputs[0].text, '5')
  assert.equal(exported.cells[0].execution_count, 1)
  assert.equal('execution_count' in exported.cells[1], false)
})

test('imported array sources and duplicate ids are normalized', () => {
  const cells = readNotebook(JSON.stringify({ nbformat: 4, cells: [
    { id: 'same', cell_type: 'code', source: ['x = 1\n', 'x'] },
    { id: 'same', cell_type: 'markdown', source: 'notes' },
  ] }))
  assert.equal(cells[0].source, 'x = 1\nx')
  assert.notEqual(cells[0].id, cells[1].id)
})

test('empty notebooks remain editable and invalid or oversized imports are rejected', () => {
  assert.equal(readNotebook('{"nbformat":4,"cells":[]}').length, 1)
  assert.throws(() => readNotebook(JSON.stringify({ nbformat: 4, cells: Array(51).fill({ cell_type: 'code', source: '' }) })))
  assert.throws(() => readNotebook('{"nbformat":4,"cells":[{"cell_type":"script","source":""}]}'))
  assert.throws(() => readNotebook('{"nbformat":4,"cells":[{"cell_type":"code","source":17}]}'))
})
