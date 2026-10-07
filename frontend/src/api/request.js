import { getPlatformEdition, readEditionToken } from '../platformEdition.js'

const API_BASE_URL =
  import.meta.env?.VITE_API_BASE_URL || 'http://localhost:8001/api/v1'

export function requestHeaders(initialHeaders) {
  const headers = new Headers(initialHeaders)
  if (!headers.has('X-Platform-Edition')) {
    headers.set('X-Platform-Edition', getPlatformEdition())
  }
  const token = readEditionToken(headers.get('X-Platform-Edition'))

  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  return headers
}

export async function apiRequest(path, options = {}, responseType = 'json') {
  const headers = requestHeaders(options.headers)
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    const detail = error.message || error.detail || '请求失败'
    const failure = new Error(typeof detail === 'string' ? detail : '请求字段不符合要求，请检查输入')
    failure.status = response.status
    throw failure
  }

  if (response.status === 204) {
    return null
  }

  if (responseType === 'blob') {
    return response.blob()
  }

  return response.json()
}
