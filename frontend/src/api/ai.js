import { apiRequest } from './request'

export const aiApi = {
  chat: ({ accountId, conversationId, message, context, history, attemptId, courseId }) =>
    apiRequest('/ai/chat', {
      method: 'POST',
      body: JSON.stringify({
        account_id: accountId,
        conversation_id: conversationId,
        message,
        context,
        history,
        attempt_id: attemptId,
        course_id: courseId,
      }),
    }),
  conversations: (accountId) =>
    apiRequest(`/ai/conversations/${encodeURIComponent(accountId)}`),
  messages: (accountId, conversationId) =>
    apiRequest(
      `/ai/conversations/${encodeURIComponent(accountId)}/${encodeURIComponent(conversationId)}/messages`,
    ),
}
