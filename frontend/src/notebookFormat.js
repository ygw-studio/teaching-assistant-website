export const MAX_CELLS = 50

export function createCell(cellType = 'code', source = '') {
  return { id: crypto.randomUUID(), cell_type: cellType, source, metadata: {}, outputs: [], execution_count: null }
}

export function readNotebook(value = '') {
  let notebook
  try { notebook = JSON.parse(value) } catch (_) { return [createCell('code', value)] }
  if (notebook?.nbformat !== 4 || !Array.isArray(notebook.cells)) return [createCell('code', value)]
  if (notebook.cells.length > MAX_CELLS) throw new Error(`最多支持 ${MAX_CELLS} 个单元格。`)
  const ids = new Set()
  const cells = notebook.cells.map((cell) => {
    if (!['code', 'markdown', 'raw'].includes(cell.cell_type)) throw new Error('单元格类型无效。')
    const source = Array.isArray(cell.source) ? cell.source.join('') : cell.source
    if (typeof source !== 'string') throw new Error('单元格内容无效。')
    const next = createCell(cell.cell_type === 'raw' ? 'markdown' : cell.cell_type, source)
    if (typeof cell.id === 'string' && /^[a-zA-Z0-9_-]{1,64}$/.test(cell.id) && !ids.has(cell.id)) next.id = cell.id
    ids.add(next.id)
    return next
  })
  return cells.length ? cells : [createCell()]
}

export function writeNotebook(cells, includeOutputs = false) {
  return JSON.stringify({
    nbformat: 4, nbformat_minor: 5,
    metadata: { kernelspec: { name: 'python3', display_name: 'Python 3 (ipykernel)', language: 'python' }, language_info: { name: 'python' } },
    cells: cells.map((cell) => ({
      id: cell.id, cell_type: cell.cell_type, source: cell.source, metadata: cell.metadata || {},
      ...(cell.cell_type === 'code' ? { outputs: includeOutputs ? cell.outputs || [] : [], execution_count: includeOutputs ? cell.execution_count : null } : {}),
    })),
  })
}
