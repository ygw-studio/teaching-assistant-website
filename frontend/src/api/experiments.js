import { apiRequest } from './request'

export const experimentApi = {
  detail: (id) => apiRequest(`/experiments/${encodeURIComponent(id)}`),
  save: (id, payload) =>
    apiRequest(`/experiments/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  uploadHandout: (id, file) =>
    apiRequest(`/experiments/${encodeURIComponent(id)}/handout?filename=${encodeURIComponent(file.name)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/pdf' },
      body: file,
    }),
  handout: (id) => apiRequest(`/experiments/${encodeURIComponent(id)}/handout`, {}, 'blob'),
  removeHandout: (id) => apiRequest(`/experiments/${encodeURIComponent(id)}/handout`, { method: 'DELETE' }),
}
