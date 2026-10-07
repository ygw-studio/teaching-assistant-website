import { apiRequest } from './request'

export const courseApi = {
  list: () => apiRequest('/courses'),
  detail: (id = 'data-structures-python') => apiRequest(`/courses/${encodeURIComponent(id)}`),
  progress: (id) => apiRequest(`/courses/${encodeURIComponent(id)}/progress`),
  submitQuiz: (courseId, lessonId, answer) =>
    apiRequest(`/courses/${encodeURIComponent(courseId)}/lessons/${encodeURIComponent(lessonId)}/quiz`, {
      method: 'POST',
      body: JSON.stringify({ answer }),
    }),
  save: (id, payload) =>
    apiRequest(`/courses/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  handout: (courseId, chapterId) =>
    apiRequest(`/courses/${encodeURIComponent(courseId)}/chapters/${encodeURIComponent(chapterId)}/handout`, {}, 'blob'),
  resources: (courseId, chapterId) =>
    apiRequest(`/courses/${encodeURIComponent(courseId)}/chapters/${encodeURIComponent(chapterId)}/resources`, {}, 'blob'),
  handoutPreview: (courseId, chapterId) =>
    apiRequest(`/courses/${encodeURIComponent(courseId)}/chapters/${encodeURIComponent(chapterId)}/handout/preview`, {}, 'blob'),
  uploadHandout: (courseId, chapterId, file) =>
    apiRequest(`/courses/${encodeURIComponent(courseId)}/chapters/${encodeURIComponent(chapterId)}/handout?filename=${encodeURIComponent(file.name)}`, {
      method: 'PUT',
      headers: { 'Content-Type': file.name.toLowerCase().endsWith('.pdf') ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.presentationml.presentation' },
      body: file,
    }),
  removeHandout: (courseId, chapterId) =>
    apiRequest(`/courses/${encodeURIComponent(courseId)}/chapters/${encodeURIComponent(chapterId)}/handout`, { method: 'DELETE' }),
  uploadHandoutPreview: (courseId, chapterId, file) =>
    apiRequest(`/courses/${encodeURIComponent(courseId)}/chapters/${encodeURIComponent(chapterId)}/handout/preview?filename=${encodeURIComponent(file.name)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/pdf' },
      body: file,
    }),
  removeHandoutPreview: (courseId, chapterId) =>
    apiRequest(`/courses/${encodeURIComponent(courseId)}/chapters/${encodeURIComponent(chapterId)}/handout/preview`, { method: 'DELETE' }),
}
