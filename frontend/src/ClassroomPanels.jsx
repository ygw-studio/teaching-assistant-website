import React, { useEffect, useState } from 'react'
import { classroomApi, qwenApi, dateText, durationText } from './api/classroom'
import { courseApi } from './api/chapters'
import { authApi } from './api/auth'
import { flushLearning } from './learningTracker'
import QwenApiGuide from './QwenApiGuide.jsx'

export function QwenKeySettings() {
  const [status, setStatus] = useState(null)
  const [key, setKey] = useState('')
  const [model, setModel] = useState('qwen-plus')
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  useEffect(() => { qwenApi.status().then(value => { setStatus(value); setModel(value.model) }).catch(error => setMessage(error.message)) }, [])
  const save = async event => {
    event.preventDefault(); setBusy(true); setMessage('')
    try { const value = await qwenApi.bind({ api_key: key.trim(), model, free_only_confirmed: confirmed }); setStatus(value); setKey(''); setMessage('已绑定。首次聊天时会验证调用；绑定本身不消耗额度。') }
    catch (error) { setMessage(error.message) }
    finally { setBusy(false) }
  }
  const remove = async () => {
    if (!window.confirm('解除绑定后将不能调用个人千问接口，已有聊天记录保留。确定继续吗？')) return
    setBusy(true)
    try { await qwenApi.remove(); setStatus({ bound: false }); setKey(''); setMessage('已解除绑定') } catch (error) { setMessage(error.message) } finally { setBusy(false) }
  }
  return <section className="panel classroom-panel qwen-settings">
    <div className="panel-heading"><div><h3>个人千问 API</h3><p>{status?.bound ? `已绑定 · ${status.model}` : '未绑定'}</p></div>{status?.bound && <button type="button" onClick={remove} disabled={busy}>解除绑定</button>}</div>
    <QwenApiGuide />
    <form onSubmit={save} className="classroom-form">
      <label>百炼 API Key<input type="password" autoComplete="off" value={key} onChange={event => setKey(event.target.value)} placeholder={status?.bound ? '输入新的 Key 可替换，原 Key 不会回显' : 'sk-…'} required maxLength={503} disabled={busy} /></label>
      <label>模型编号<input value={model} onChange={event => setModel(event.target.value)} required maxLength={95} disabled={busy} /></label>
      <label className="classroom-check"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} required />我已在百炼为所选模型开启“免费额度用完即停”</label>
      <p className="classroom-note">额度可能到期或耗尽；网站无法读取或替你保证百炼的计费开关。请使用北京地域的通用 API Key。你的提问、回复和使用时间会保存在本平台，供有权限的教师、管理员查看；Key 不进入日志或导出。</p>
      <div className="classroom-actions"><button className="classroom-primary" type="submit" disabled={busy}>{busy ? '保存中…' : '绑定个人 Key'}</button><a href="https://bailian.console.aliyun.com/cn-beijing/costing-balance/free-quota" target="_blank" rel="noreferrer">百炼免费额度</a></div>
      {message && <p role="status">{message}</p>}
    </form>
  </section>
}

const emptyTask = { course_id: '', chapter_id: '', title: '', instructions: '', initial_code: '', stdin: '', deadline_at: '', is_published: true }
const localDateInput = value => value ? new Date(new Date(value).getTime() - new Date(value).getTimezoneOffset() * 60000).toISOString().slice(0, 16) : ''

export function AssignmentManager() {
  const [courses, setCourses] = useState([])
  const [tasks, setTasks] = useState([])
  const [chapters, setChapters] = useState([])
  const [id, setId] = useState(null)
  const [form, setForm] = useState(emptyTask)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const load = () => classroomApi.tasks().then(setTasks)
  useEffect(() => { classroomApi.courses().then(values => { setCourses(values); setForm(old => ({ ...old, course_id: values[0]?.id || '' })) }).catch(error => setMessage(error.message)); load().catch(error => setMessage(error.message)) }, [])
  useEffect(() => { let active = true; if (form.course_id) courseApi.detail(form.course_id).then(value => { if (active) setChapters(value.chapters) }).catch(error => setMessage(error.message)); return () => { active = false } }, [form.course_id])
  const edit = task => { setId(task.id); setForm({ ...task, chapter_id: task.chapter_id || '', deadline_at: localDateInput(task.deadline_at), is_published: !!task.is_published }); setMessage('') }
  const save = async event => {
    event.preventDefault(); setBusy(true); setMessage('')
    try { const saved = await classroomApi.saveTask(id, { ...form, chapter_id: form.chapter_id || null, deadline_at: form.deadline_at ? new Date(form.deadline_at).toISOString() : null }); edit(saved); await load(); setMessage('已保存。截止时间变更对已有做题记录也生效，题目内容历史版本保留。') } catch (error) { setMessage(error.message) } finally { setBusy(false) }
  }
  return <div className="page classroom-management">
    <section className="panel classroom-panel"><div className="panel-heading"><div><h3>课堂习题与作业</h3><p>发布到学生端“在线练习”，支持截止时间</p></div><button type="button" onClick={() => { setId(null); setForm({ ...emptyTask, course_id: courses[0]?.id || '' }); setMessage('') }}>新建习题</button></div>
      <div className="classroom-task-list">{tasks.map(task => <button type="button" className={id === task.id ? 'selected' : ''} key={task.id} onClick={() => edit(task)}><strong>{task.title}</strong><span>{task.course_title} · 截止 {dateText(task.deadline_at)} · {task.is_published ? '已发布' : '已撤回'}</span></button>)}{!tasks.length && <p>还没有习题。填写下方内容后发布。</p>}</div>
      <form onSubmit={save} className="classroom-form">
        <label>所属课程<select value={form.course_id} disabled={!!id || busy} onChange={event => setForm({ ...form, course_id: event.target.value, chapter_id: '' })} required><option value="">选择课程</option>{courses.map(course => <option key={course.id} value={course.id}>{course.title}</option>)}</select></label>
        <label>关联章节<select value={form.chapter_id} disabled={busy} onChange={event => setForm({ ...form, chapter_id: event.target.value })}><option value="">不限定章节</option>{chapters.map(chapter => <option key={chapter.id} value={chapter.id}>{chapter.title}</option>)}</select></label>
        <label>习题标题<input required maxLength={200} value={form.title} disabled={busy} onChange={event => setForm({ ...form, title: event.target.value })} /></label>
        <label>题目要求<textarea required rows={5} maxLength={12000} value={form.instructions} disabled={busy} onChange={event => setForm({ ...form, instructions: event.target.value })} /></label>
        <label>初始 Python 代码或 Notebook 内容<textarea rows={6} maxLength={190000} value={form.initial_code} disabled={busy} onChange={event => setForm({ ...form, initial_code: event.target.value })} /></label>
        <label>默认标准输入<textarea rows={2} maxLength={20000} value={form.stdin} disabled={busy} onChange={event => setForm({ ...form, stdin: event.target.value })} /></label>
        <label>截止日期与时间（本机时区）<input type="datetime-local" value={form.deadline_at} disabled={busy} onChange={event => setForm({ ...form, deadline_at: event.target.value })} /></label>
        <label className="classroom-check"><input type="checkbox" checked={form.is_published} disabled={busy} onChange={event => setForm({ ...form, is_published: event.target.checked })} />发布给学生（取消勾选即撤回，不删除历史记录）</label>
        <button type="submit" className="classroom-primary" disabled={busy || !courses.length}>{busy ? '保存中…' : '保存习题'}</button>
        {message && <p role="status">{message}</p>}{!courses.length && <p>尚未分配课程，请联系管理员。</p>}
      </form>
    </section>
  </div>
}

export function StudentRecords({ admin = false }) {
  const [records, setRecords] = useState([])
  const [events, setEvents] = useState([])
  const [detail, setDetail] = useState(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [rawOpen, setRawOpen] = useState(false)
  const refresh = async () => { setBusy(true); try { const [values, rows] = await Promise.all([classroomApi.records(), classroomApi.events()]); setRecords(values); setEvents(rows); setMessage('') } catch (error) { setMessage(error.message) } finally { setBusy(false) } }
  useEffect(() => { refresh(); const timer = window.setInterval(refresh, 30000); return () => window.clearInterval(timer) }, [])
  const open = async id => { try { setDetail(await classroomApi.detail(id)); setMessage('') } catch (error) { setMessage(error.message) } }
  const exportData = async () => { try { const blob = await classroomApi.export(); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = 'learning-events.csv'; link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 30000) } catch (error) { setMessage(error.message) } }
  const clean = async () => { try { const result = await classroomApi.clean(); setMessage(`已处理 ${result.processed} 条记录，原始数据完整保留。`); } catch (error) { setMessage(error.message) } }
  return <div className="page classroom-management">
    <section className="panel classroom-panel"><div className="panel-heading"><div><h3>{admin ? '平台学习记录' : '学生做题记录'}</h3><p>{admin ? '全平台业务记录，不包含个人 API Key' : '仅展示你负责课程中的学生记录'} · 自动刷新 30 秒</p></div><div className="classroom-actions"><button type="button" onClick={refresh} disabled={busy}>刷新</button><button type="button" onClick={exportData}>导出 CSV</button>{admin && <button type="button" onClick={clean}>运行简单清理</button>}</div></div>
      {message && <p role="status">{message}</p>}
      <div className="classroom-table"><table><thead><tr><th>学生</th><th>习题</th><th>学习时长</th><th>做题经过</th><th>运行 / AI 提问</th><th>提交</th><th>详情</th></tr></thead><tbody>{records.map(row => <tr key={row.id}><td>{row.name}<small>{row.account_id}</small></td><td>{row.title}</td><td>{durationText(row.learning_ms)}</td><td>{durationText(row.elapsed_ms)}</td><td>{row.run_count} / {row.ai_count}</td><td>{row.first_submitted_at ? dateText(row.first_submitted_at) : '未提交'}</td><td><button type="button" onClick={() => open(row.id)}>查看</button></td></tr>)}</tbody></table></div>{!records.length && <p>暂无真实做题记录，学生选择老师发布的习题后会开始记录。</p>}
      <details open={rawOpen} onToggle={event => setRawOpen(event.currentTarget.open)}><summary>原始行为明细（最近 200 条）</summary><div className="classroom-table"><table><thead><tr><th>发生时间</th><th>学生</th><th>行为</th><th>课程 / 习题</th><th>内容</th></tr></thead><tbody>{events.map(row => <tr key={row.event_id}><td>{dateText(row.occurred_at)}</td><td>{row.account_id}</td><td>{row.event_type}</td><td>{row.course_id || '未关联'} / {row.assignment_id || '自由操作'}</td><td><details><summary>字段</summary><pre>{JSON.stringify(row, null, 2)}</pre></details></td></tr>)}</tbody></table></div></details>
    </section>
    {detail && <section className="panel classroom-panel"><div className="panel-heading"><h3>{detail.attempt.task.title} · 本次做题详情</h3><button type="button" onClick={() => setDetail(null)}>收起</button></div>
      <details open><summary>AI 对话</summary>{detail.chat.messages.map(item => <div className="classroom-chat-record" key={item.id}><strong>{item.role === 'user' ? '学生' : 'AI'} · {dateText(item.created_at)}</strong><pre>{item.content}</pre></div>)}{!detail.chat.messages.length && <p>本题暂无 AI 对话。</p>}</details>
      <details><summary>代码版本与提交</summary>{detail.snapshots.map(item => <div key={item.id}><h4>{item.reason} · {dateText(item.created_at)}</h4><pre>{item.code}</pre></div>)}</details>
      <details><summary>本次行为时间线</summary>{detail.events.map(item => <p key={item.event_id}>{dateText(item.occurred_at)} · {item.event_type}</p>)}</details>
    </section>}
    {admin && <CourseAccess />}
  </div>
}

function CourseAccess() {
  const [courses, setCourses] = useState([])
  const [users, setUsers] = useState([])
  const [courseId, setCourseId] = useState('')
  const [access, setAccess] = useState({ teachers: [], students: [] })
  const [message, setMessage] = useState('')
  useEffect(() => { classroomApi.courses().then(values => { setCourses(values); setCourseId(values[0]?.id || '') }).catch(error => setMessage(error.message)); authApi.users().then(setUsers).catch(error => setMessage(error.message)) }, [])
  useEffect(() => { let active = true; if (courseId) classroomApi.access(courseId).then(value => { if (active) setAccess(value) }).catch(error => setMessage(error.message)); return () => { active = false } }, [courseId])
  const toggle = (type, account) => setAccess(old => ({ ...old, [type]: old[type].includes(account) ? old[type].filter(id => id !== account) : [...old[type], account] }))
  const save = async () => { try { await classroomApi.saveAccess(courseId, access); setMessage('课程归属与学生名单已保存') } catch (error) { setMessage(error.message) } }
  return <section className="panel classroom-panel"><details><summary>课程负责人和学生名单</summary><div className="classroom-form"><label>课程<select value={courseId} onChange={event => setCourseId(event.target.value)}>{courses.map(course => <option key={course.id} value={course.id}>{course.title}</option>)}</select></label>{['teachers', 'students'].map(type => <fieldset key={type}><legend>{type === 'teachers' ? '负责教师' : '课程学生'}</legend>{users.filter(user => user.role === (type === 'teachers' ? 'teacher' : 'student') && user.is_active).map(user => <label className="classroom-check" key={user.account_id}><input type="checkbox" checked={access[type].includes(user.account_id)} onChange={() => toggle(type, user.account_id)} />{user.name}（{user.account_id}）</label>)}</fieldset>)}<button type="button" onClick={save} disabled={!courseId}>保存归属与名单</button>{message && <p role="status">{message}</p>}</div></details></section>
}
