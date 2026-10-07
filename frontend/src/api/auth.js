import { apiRequest } from './request'

export const authApi = {
  login: (payload) =>
    apiRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  register: (payload) =>
    apiRequest('/auth/users', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  users: () => apiRequest('/auth/users'),
  me: () => apiRequest('/auth/me'),
  logout: (options = {}) =>
    apiRequest('/auth/logout', {
      ...options,
      method: 'POST',
    }),
  changePassword: (payload) =>
    apiRequest('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
}
