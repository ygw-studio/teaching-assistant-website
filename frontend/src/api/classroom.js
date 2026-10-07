import { apiRequest } from './request.js'

export const classroomApi = {
  courses: () => apiRequest('/classroom/courses'),
  tasks: () => apiRequest('/classroom/assignments'),
  saveTask: (id, value) => apiRequest(`/classroom/assignments${id ? `/${encodeURIComponent(id)}` : ''}`, { method: id ? 'PUT' : 'POST', body: JSON.stringify(value) }),
  start: id => apiRequest(`/classroom/assignments/${encodeURIComponent(id)}/start`, { method: 'POST' }),
  submit: (id, value) => apiRequest(`/classroom/attempts/${encodeURIComponent(id)}/submit`, { method: 'POST', body: JSON.stringify(value) }),
  chat: id => apiRequest(`/classroom/attempts/${encodeURIComponent(id)}/chat`),
  time: () => apiRequest('/classroom/me/time'),
  records: () => apiRequest('/classroom/records'),
  detail: id => apiRequest(`/classroom/records/${encodeURIComponent(id)}`),
  events: () => apiRequest('/classroom/events?limit=200'),
  clean: () => apiRequest('/classroom/events/clean', { method: 'POST' }),
  export: () => apiRequest('/classroom/events/export', {}, 'blob'),
  access: id => apiRequest(`/classroom/access/${encodeURIComponent(id)}`),
  saveAccess: (id, value) => apiRequest(`/classroom/access/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(value) }),
}

export const qwenApi = {
  status: () => apiRequest('/ai/key'),
  bind: value => apiRequest('/ai/key', { method: 'PUT', body: JSON.stringify(value) }),
  remove: () => apiRequest('/ai/key', { method: 'DELETE' }),
}

export const durationText = ms => {
  const seconds = Math.floor(Math.max(0, ms || 0) / 1000)
  return `${Math.floor(seconds / 3600)}小时${Math.floor(seconds / 60) % 60}分${seconds % 60}秒`
}

export const dateText = value => value ? new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) : '不限'
