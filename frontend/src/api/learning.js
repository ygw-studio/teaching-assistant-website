import { apiRequest } from './request'

export const learningApi = {
  overview: () => apiRequest('/students/me/overview'),
}
