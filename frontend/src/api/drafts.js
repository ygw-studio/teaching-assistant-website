import { apiRequest } from './request'

const pathFor = (scope, resourceId) =>
  `/code-drafts/${encodeURIComponent(scope)}/${encodeURIComponent(resourceId)}`

export const draftApi = {
  get: (scope, resourceId) => apiRequest(pathFor(scope, resourceId)),
  save: (scope, resourceId, code, stdin, options = {}) =>
    apiRequest(pathFor(scope, resourceId), {
      method: 'PUT',
      body: JSON.stringify({ code, stdin }),
      ...options,
    }),
}
