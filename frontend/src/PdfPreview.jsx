import React, { useEffect, useRef, useState } from 'react'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { createPdfWheelHandler } from './pdfWheelNavigation'
import { trackLearning } from './learningTracker'

let pdfLibrary
const loadPdfLibrary = () => {
  pdfLibrary ||= import('pdfjs-dist').then((library) => {
    library.GlobalWorkerOptions.workerSrc = workerUrl
    return library
  })
  return pdfLibrary
}

export default function PdfPreview({ url, title, className = '' }) {
  const [document, setDocument] = useState(null)
  const [page, setPage] = useState(1)
  const [zoom, setZoom] = useState(1)
  const [width, setWidth] = useState(0)
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const frame = useRef(null)
  const canvas = useRef(null)
  const rendering = useRef(null)
  const preview = useRef(null)
  const wheelView = useRef(null)
  const wheelDestination = useRef(null)

  useEffect(() => {
    wheelView.current = { page, totalPages: document?.numPages || 0, busy, error }
  }, [document, page, busy, error])
  useEffect(() => { if (document) trackLearning('lecture.page', { page_number: page, total_pages: document.numPages, filename: title.slice(0, 300) }) }, [document, page, title])
  useEffect(() => { if (document) trackLearning('lecture.zoom', { zoom, filename: title.slice(0, 300) }) }, [document, zoom, title])

  useEffect(() => {
    const target = preview.current
    const handler = createPdfWheelHandler({
      viewport: frame.current,
      getState: () => wheelView.current,
      changePage: (nextPage, direction) => {
        wheelDestination.current = { page: nextPage, direction }
        setPage(nextPage)
      },
    })
    target.addEventListener('wheel', handler, { passive: false })
    return () => target.removeEventListener('wheel', handler)
  }, [url])

  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    observer.observe(frame.current)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    let active = true
    let task
    setDocument(null)
    setPage(1)
    setZoom(1)
    wheelDestination.current = null
    setError('')
    setBusy(true)
    loadPdfLibrary().then((library) => {
      if (!active) return
      task = library.getDocument({ url, isEvalSupported: false })
      return task.promise.then((loaded) => {
        if (active) setDocument(loaded)
      })
    }).catch((reason) => {
      if (active) {
        setError(`讲义预览失败：${reason.message}`)
        setBusy(false)
      }
    })
    return () => {
      active = false
      rendering.current?.cancel()
      task?.destroy().catch(() => {})
    }
  }, [url])

  useEffect(() => {
    if (!document || !width) return
    let active = true
    let task
    setBusy(true)
    setError('')
    const draw = async () => {
      const previous = rendering.current
      previous?.cancel()
      await previous?.promise.catch(() => {})
      const sheet = await document.getPage(page)
      if (!active) return
      const base = sheet.getViewport({ scale: 1 })
      const viewport = sheet.getViewport({ scale: Math.max(1, width - 24) / base.width * zoom })
      const ratio = Math.min(window.devicePixelRatio || 1, 2)
      canvas.current.width = Math.ceil(viewport.width * ratio)
      canvas.current.height = Math.ceil(viewport.height * ratio)
      canvas.current.style.width = `${viewport.width}px`
      canvas.current.style.height = `${viewport.height}px`
      task = sheet.render({
        canvasContext: canvas.current.getContext('2d'), viewport,
        transform: ratio === 1 ? null : [ratio, 0, 0, ratio, 0, 0],
      })
      rendering.current = task
      await task.promise
      if (active) {
        if (wheelDestination.current?.page === page) {
          frame.current.scrollTop = wheelDestination.current.direction < 0 ? frame.current.scrollHeight : 0
          wheelDestination.current = null
        }
        setBusy(false)
      }
    }
    draw().catch((reason) => {
      if (active && reason.name !== 'RenderingCancelledException') {
        setError(`讲义页面加载失败：${reason.message}`)
        setBusy(false)
      }
    })
    return () => {
      active = false
      task?.cancel()
    }
  }, [document, page, width, zoom])

  return (
    <section className={`pdf-preview ${className}`} aria-label={title} ref={preview}>
      <div className="pdf-preview-tools">
        <button type="button" disabled={!document || page <= 1} onClick={() => setPage((value) => value - 1)}>上一页</button>
        <span>{document ? `${page} / ${document.numPages} 页` : '正在读取讲义'}</span>
        <button type="button" disabled={!document || page >= document.numPages} onClick={() => setPage((value) => value + 1)}>下一页</button>
        <button type="button" disabled={!document || zoom <= 1} onClick={() => setZoom((value) => Math.max(1, value - 0.25))}>缩小</button>
        <button type="button" disabled={!document || zoom >= 2} onClick={() => setZoom((value) => Math.min(2, value + 0.25))}>放大</button>
      </div>
      {busy && <p className="pdf-preview-status" role="status">正在显示讲义…</p>}
      {error && <p className="pdf-preview-status" role="alert">{error}</p>}
      <div className="pdf-preview-page" ref={frame} aria-busy={busy}>
        <canvas ref={canvas} role="img" aria-label={`${title}，第 ${page} 页`} />
      </div>
    </section>
  )
}
