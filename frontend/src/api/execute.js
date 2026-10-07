import { apiRequest } from './request'

export const executeApi = {
  runCell: (payload) => apiRequest('/notebooks/execute', { method: 'POST', body: JSON.stringify(payload) }),
  restartNotebook: (id, resourceId) => apiRequest(`/notebooks/${encodeURIComponent(id)}/restart`, {
    method: 'POST', body: JSON.stringify({ resource_id: resourceId }),
  }),
  run: (code, language = 'python', stdin = '', context = {}) =>
    apiRequest('/execute', {
      method: 'POST',
      body: JSON.stringify({ code, language, stdin, ...context }),
    }),
}
