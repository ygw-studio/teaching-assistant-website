import React, { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { ArrowDown, ArrowUp, ChevronDown, FileCode2, Play, Plus, RotateCcw, Trash2 } from 'lucide-react'
import { executeApi } from './api/execute'
import { createCell, MAX_CELLS, readNotebook, writeNotebook } from './notebookFormat'
import { trackLearning } from './learningTracker'

function readDraft(value) {
  try { return readNotebook(value) } catch (_) { return [createCell('code', value)] }
}

function CellOutput({ output }) {
  if (output.output_type === 'stream') return <pre className={output.name === 'stderr' ? 'notebook-error' : ''}>{output.text}</pre>
  if (output.output_type === 'error') return <pre className="notebook-error">{output.traceback?.join('\n') || `${output.ename}: ${output.evalue}`}</pre>
  const data = output.data || {}
  const mime = data['image/png'] ? 'image/png' : data['image/jpeg'] ? 'image/jpeg' : null
  if (mime) return <img src={`data:${mime};base64,${data[mime]}`} alt="单元格运行生成的图表" />
  return data['text/plain'] ? <pre>{data['text/plain']}</pre> : null
}

const Notebook = forwardRef(function Notebook({ value, name, defaultCode, onChange, onFlush, stdin, onStdinChange, resourceId, courseId, lessonId, attemptId, onRunningChange, draftStatus, extraActions }, ref) {
  const [cells, setCells] = useState(() => readDraft(value))
  const cellsRef = useRef(cells)
  const savedValue = useRef(value)
  const sessionId = useRef(crypto.randomUUID())
  const busyRef = useRef(false)
  const mounted = useRef(true)
  const fileInput = useRef(null)
  const [runningCell, setRunningCell] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [editingMarkdown, setEditingMarkdown] = useState(null)

  useEffect(() => {
    if (savedValue.current !== value) {
      savedValue.current = value
      cellsRef.current = readDraft(value)
      setCells(cellsRef.current)
    }
  }, [value])

  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])

  const displayCells = (next) => {
    cellsRef.current = next
    if (mounted.current) setCells(next)
  }

  const saveCells = (next) => {
    const encoded = writeNotebook(next)
    if (encoded.length > 190000) { setMessage('笔记本代码太长，请拆成多个笔记本。'); return }
    displayCells(next)
    savedValue.current = encoded
    onChange(encoded)
  }

  const changeCell = (id, patch) => saveCells(cellsRef.current.map((cell) => cell.id === id ? { ...cell, ...patch } : cell))

  const addCell = (cellType = 'code') => {
    if (cellsRef.current.length >= MAX_CELLS) { setMessage(`最多支持 ${MAX_CELLS} 个单元格。`); return }
    const cell = createCell(cellType)
    saveCells([...cellsRef.current, cell])
    trackLearning('notebook.cell_added', { cell_id: cell.id, input_type: cellType })
    if (cellType === 'markdown') setEditingMarkdown(cell.id)
  }

  const moveCell = (index, offset) => {
    const next = [...cellsRef.current]
    ;[next[index], next[index + offset]] = [next[index + offset], next[index]]
    saveCells(next)
    trackLearning('notebook.cell_moved', { cell_id: next[index + offset].id, count: offset })
  }

  const setRunning = (next) => {
    busyRef.current = next
    if (mounted.current) { setBusy(next); onRunningChange(next) }
  }

  const runCells = async (ids) => {
    if (busyRef.current) return
    setRunning(true)
    setMessage('')
    onFlush()
    try {
      for (const id of ids) {
        if (!mounted.current) break
        const cell = cellsRef.current.find((item) => item.id === id)
        if (!cell || cell.cell_type !== 'code' || !cell.source.trim()) continue
        setRunningCell(id)
        const result = await executeApi.runCell({ code: cell.source, stdin, notebook_id: sessionId.current, cell_id: id, resource_id: resourceId, course_id: courseId, lesson_id: lessonId || null, attempt_id: attemptId || null, notebook_source: writeNotebook(cellsRef.current) })
        if (!mounted.current) break
        displayCells(cellsRef.current.map((item) => item.id === id ? { ...item, outputs: result.outputs, execution_count: result.execution_count } : item))
        if (result.kernel_reset) setMessage('内核已停止，变量已清空；请从前面的单元格重新运行。')
        if (result.exit_code !== 0) break
      }
    } catch (error) {
      if (mounted.current) setMessage(error.message)
    } finally {
      if (mounted.current) setRunningCell(null)
      setRunning(false)
    }
  }

  useImperativeHandle(ref, () => ({ runAll: () => runCells(cellsRef.current.filter((cell) => cell.cell_type === 'code').map((cell) => cell.id)) }))

  const restartKernel = async () => {
    if (busyRef.current) return false
    setRunning(true)
    try {
      await executeApi.restartNotebook(sessionId.current, resourceId)
      displayCells(cellsRef.current.map((cell) => ({ ...cell, outputs: [], execution_count: null })))
      setMessage('内核已重启，变量已清空。')
      return true
    } catch (error) { setMessage(error.message); return false }
    finally { setRunning(false) }
  }

  const exportNotebook = () => {
    trackLearning('notebook.exported', { filename: name })
    const url = URL.createObjectURL(new Blob([writeNotebook(cellsRef.current, true)], { type: 'application/x-ipynb+json' }))
    const link = document.createElement('a')
    link.href = url
    link.download = name
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 30000)
  }

  const importNotebook = async (event) => {
    const file = event.target.files[0]
    event.target.value = ''
    if (!file) return
    try {
      if (file.size > 2000000) throw new Error('文件超过 2 MB，请先移除过大的输出。')
      const text = await file.text()
      const raw = JSON.parse(text)
      if (raw.nbformat !== 4 || !Array.isArray(raw.cells)) throw new Error('请选择有效的 .ipynb 文件。')
      const next = readNotebook(text)
      if (writeNotebook(next).length > 190000) throw new Error('笔记本代码太长，请拆分后导入。')
      if (cellsRef.current.some((cell) => cell.source.trim()) && !window.confirm('导入会替换当前笔记本，请先导出需要保留的内容。确定继续吗？')) return
      if (await restartKernel()) { saveCells(next); trackLearning('notebook.imported', { filename: file.name, count: next.length }); setMessage('笔记本已导入；运行单元格后即可恢复变量。') }
    } catch (error) { setMessage(error.message) }
  }

  const restoreNotebook = async () => {
    if (!window.confirm('确定恢复初始笔记本？当前内容会被替换。')) return
    if (await restartKernel()) { saveCells([createCell('code', defaultCode)]); trackLearning('notebook.restored') }
  }

  return <section className="lab-workbench lab-notebook" aria-label="Jupyter Notebook 实践区">
    <header className="notebook-heading"><div><FileCode2 size={17} /><strong>{name}</strong></div>{extraActions}</header>
    <div className="notebook-toolbar">
      <button type="button" onClick={() => addCell()} disabled={busy}><Plus size={14} />代码</button>
      <button type="button" onClick={() => addCell('markdown')} disabled={busy}><Plus size={14} />文字</button>
      <button type="button" onClick={restartKernel} disabled={busy}><RotateCcw size={14} />重启内核</button>
      <details className="notebook-file-menu" onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false }}>
        <summary>文件<ChevronDown size={13} /></summary>
        <div onClick={(event) => { if (event.target.closest('button')) event.currentTarget.closest('details').open = false }}>
          <button type="button" onClick={() => fileInput.current.click()} disabled={busy}>导入 .ipynb</button>
          <button type="button" onClick={exportNotebook}>导出 .ipynb</button>
          <button type="button" onClick={() => { displayCells(cellsRef.current.map((cell) => ({ ...cell, outputs: [] }))); trackLearning('notebook.output_cleared') }} disabled={busy}>清空输出</button>
          <button type="button" onClick={restoreNotebook} disabled={busy}>恢复初始笔记本</button>
        </div>
      </details>
      <input ref={fileInput} type="file" accept=".ipynb,application/json" aria-label="导入 Notebook 文件" hidden onChange={importNotebook} />
      <span className="notebook-kernel" role="status">Python 3 · {busy ? '运行中' : '空闲'}</span>
    </div>
    {message && <p className="notebook-message" role="status">{message}</p>}
    <div className="notebook-scroll">
      {cells.map((cell, index) => <article className={`notebook-cell ${runningCell === cell.id ? 'executing' : ''}`} key={cell.id} aria-label={`第 ${index + 1} 个单元格`}>
        <div className="notebook-cell-tools">
          <span className="notebook-count">{cell.cell_type === 'code' ? `In [${runningCell === cell.id ? '*' : cell.execution_count ?? ' '}]` : 'Markdown'}</span>
          <select aria-label={`第 ${index + 1} 个单元格类型`} value={cell.cell_type} disabled={busy} onChange={(event) => { changeCell(cell.id, { cell_type: event.target.value, outputs: [], execution_count: null }); setEditingMarkdown(cell.id); trackLearning('notebook.cell_type', { cell_id: cell.id, input_type: event.target.value }) }}><option value="code">代码</option><option value="markdown">文字</option></select>
          {cell.cell_type === 'code' ? <button type="button" onClick={() => runCells([cell.id])} disabled={busy || !cell.source.trim()} aria-label={`运行第 ${index + 1} 个单元格`}><Play size={14} /></button>
            : <button type="button" disabled={busy} onClick={() => setEditingMarkdown(editingMarkdown === cell.id ? null : cell.id)}>{editingMarkdown === cell.id ? '预览' : '编辑'}</button>}
          <button type="button" disabled={busy || index === 0} onClick={() => moveCell(index, -1)} aria-label={`上移第 ${index + 1} 个单元格`}><ArrowUp size={14} /></button>
          <button type="button" disabled={busy || index === cells.length - 1} onClick={() => moveCell(index, 1)} aria-label={`下移第 ${index + 1} 个单元格`}><ArrowDown size={14} /></button>
          <button type="button" disabled={busy || cells.length === 1} aria-label={`删除第 ${index + 1} 个单元格`} onClick={() => { if (!cell.source.trim() || window.confirm('确定删除这个单元格？')) { saveCells(cellsRef.current.filter((item) => item.id !== cell.id)); trackLearning('notebook.cell_deleted', { cell_id: cell.id }) } }}><Trash2 size={14} /></button>
        </div>
        {cell.cell_type === 'markdown' && editingMarkdown !== cell.id
          ? <div className="notebook-markdown"><ReactMarkdown components={{ img: ({ alt }) => <span>{alt || '图片'}</span> }}>{cell.source || '空文本单元格'}</ReactMarkdown></div>
          : <textarea className="notebook-editor" aria-label={`第 ${index + 1} 个${cell.cell_type === 'code' ? '代码' : '文本'}单元格`} value={cell.source} rows={Math.max(4, Math.min(20, cell.source.split('\n').length + 1))} disabled={busy} spellCheck="false" onChange={(event) => { changeCell(cell.id, { source: event.target.value }); trackLearning('notebook.edit', { cell_id: cell.id, chars: event.target.value.length, input_type: event.nativeEvent.inputType || 'input' }) }}
            onFocus={() => trackLearning('notebook.focus', { cell_id: cell.id })} onBlur={() => trackLearning('notebook.blur', { cell_id: cell.id })} onPaste={(event) => trackLearning('notebook.paste', { cell_id: cell.id, chars: event.clipboardData.getData('text/plain').length })}
            onKeyDown={(event) => { if ((event.shiftKey || event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); if (cell.cell_type === 'code') runCells([cell.id]); else setEditingMarkdown(null) } }} />}
        {!!cell.outputs?.length && <div className="notebook-cell-output" aria-live="polite">{cell.outputs.map((output, outputIndex) => <CellOutput key={outputIndex} output={output} />)}</div>}
      </article>)}
    </div>
    <footer className="notebook-footer"><span role="status">{draftStatus}</span><details><summary>标准输入</summary><label>每行一次输入<textarea aria-label="Notebook 标准输入" value={stdin} disabled={busy} onChange={(event) => onStdinChange(event.target.value)} /></label></details></footer>
  </section>
})

export default Notebook
