import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { aiApi } from './api/ai'
import { authApi } from './api/auth'
import { courseApi } from './api/chapters'
import { executeApi } from './api/execute'
import { experimentApi } from './api/experiments'
import { learningApi } from './api/learning'
import { useCodeDrafts } from './useCodeDrafts'
import PdfPreview from './PdfPreview'
import Notebook from './Notebook'
import { classroomApi, qwenApi, dateText } from './api/classroom'
import { AssignmentManager, StudentRecords, QwenKeySettings } from './ClassroomPanels'
import { startLearningTracker, endLearningTracker, setLearningContext as updateLearningContext, trackLearning, setAiPanelVisible, flushLearning } from './learningTracker'
import { PLATFORM_EDITIONS, getPlatformEdition, editionUrl, editionSessionKey, readEditionToken, saveEditionSession, clearEditionSession } from './platformEdition'
import {
  ArrowRight, BarChart3, Bell, BookOpen, Bot, Check, ChevronDown,
  ChevronRight, CircleUserRound, ClipboardList, Clock3, Code2, Flame, GraduationCap,
  Database, Eye, EyeOff, FileCode2, FileText, Folder, Home, Lightbulb, ListChecks,
  Menu, MessageCircle, MonitorPlay, LogOut, Play, Search, Send, Settings,
  Shield, Sparkles, Target, Terminal, Trophy, Users, X, Zap,
} from 'lucide-react'

const AI_ASSISTANT_POSITION_KEY = 'ai_assistant_position_v3'

function normalizeCourse(rawCourse) {
  const lessons = {}
  const normalizedChapters = rawCourse.chapters.map((chapter) => ({
    id: chapter.id,
    title: chapter.title,
    handoutName: chapter.handout_name,
    previewName: chapter.preview_name,
    resourcesName: chapter.resources_name,
    points: chapter.lessons.map((lesson) => {
      lessons[lesson.id] = {
        title: lesson.title,
        lead: lesson.lead,
        concept: lesson.concept,
        syntaxTitle: lesson.syntax_title,
        code: lesson.code,
        steps: lesson.steps,
        isCoding: lesson.is_coding,
        practiceCode: lesson.practice_code,
        stdin: lesson.stdin,
        quiz: {
          question: lesson.quiz_question,
          options: lesson.quiz_options,
          answer: lesson.quiz_answer,
        },
        minutes: lesson.minutes,
      }
      return { id: lesson.id, title: lesson.title }
    }),
  }))
  return {
    id: rawCourse.id,
    title: rawCourse.title,
    description: rawCourse.description,
    chapters: normalizedChapters,
    lessons,
  }
}

const roleConfig = {
  student: {
    label: '学生',
    defaultPage: 'home',
    navCaption: '学习空间',
    navItems: [
      { id: 'home', label: '学习首页', icon: Home },
      { id: 'course', label: '课程学习', icon: BookOpen },
      { id: 'practice', label: '在线练习', icon: Code2 },
    ],
  },
  teacher: {
    label: '教师',
    defaultPage: 'teacher-home',
    navCaption: '教学管理',
    navItems: [
      { id: 'teacher-home', label: '教师首页', icon: Home },
      { id: 'course-manage', label: '课程管理', icon: BookOpen },
      { id: 'experiment-manage', label: '实验任务', icon: FileCode2 },
      { id: 'assignment-manage', label: '作业管理', icon: ClipboardList },
      { id: 'student-records', label: '学生记录', icon: BarChart3 },
    ],
  },
  admin: {
    label: '管理员',
    defaultPage: 'admin-home',
    navCaption: '系统管理',
    navItems: [
      { id: 'admin-home', label: '管理首页', icon: Home },
      { id: 'user-manage', label: '用户管理', icon: Users },
      { id: 'role-manage', label: '角色权限', icon: Shield },
      { id: 'system-settings', label: '系统设置', icon: Settings },
      { id: 'platform-records', label: '学习数据', icon: Database },
    ],
  },
}

function Brand({ edition = 'student' }) {
  return (
    <div className="brand">
      <div className="brand-mark"><GraduationCap size={23} /></div>
      <div><strong>知序</strong><span>{edition === 'student' ? '教学辅助平台' : `教学辅助平台 · ${PLATFORM_EDITIONS[edition].label}`}</span></div>
    </div>
  )
}

function Sidebar({ page, setPage, collapsed, setCollapsed, user, onLogout }) {
  const config = roleConfig[user.role]
  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-top">
        <Brand edition={user.role} />
        <button aria-label="折叠菜单" className="icon-button collapse-button" onClick={() => setCollapsed(!collapsed)}>
          <Menu size={19} />
        </button>
      </div>
      <nav>
        <p className="nav-caption">{config.navCaption}</p>
        {config.navItems.map((item) => {
          const Icon = item.icon
          return (
            <button
              key={item.id}
              className={`nav-item ${page === item.id ? 'active' : ''}`}
              aria-label={item.label}
              title={item.label}
              onClick={() => setPage(item.id)}
            >
              <Icon size={19} />
              <span>{item.label}</span>
            </button>
          )
        })}
        <p className="nav-caption second">个人</p>
        <button className={`nav-item ${page === 'profile' ? 'active' : ''}`} aria-label="个人中心" title="个人中心" onClick={() => setPage('profile')}>
          <CircleUserRound size={19} /><span>个人中心</span>
        </button>
        <button className="nav-item" aria-label="退出登录" title="退出登录" onClick={onLogout}><LogOut size={19} /><span>退出登录</span></button>
      </nav>
      <div className="sidebar-user">
        <div className="avatar">{user.name.slice(0, 1)}</div>
        <div><strong>{user.name}</strong><span>{user.detail}</span></div>
        <ChevronRight size={16} />
      </div>
    </aside>
  )
}

function Header({ page, user, onLogout }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [dialog, setDialog] = useState(null)
  const [passwords, setPasswords] = useState({
    current: '',
    next: '',
    confirm: '',
  })
  const [passwordMessage, setPasswordMessage] = useState('')
  const titles = {
    home: [`你好，${user.name}`, '从真实进度继续学习'],
    course: ['课程学习', '阅读讲义并完成知识点小测'],
    practice: ['在线编程实验室', '用代码巩固每一个知识点'],
    'teacher-home': ['教师工作台', '查看课程与学生学习情况'],
    'course-manage': ['课程管理', '维护章节、知识点和实验内容'],
    'experiment-manage': ['实验管理', '编辑学生端实验题目与指导'],
    'assignment-manage': ['作业管理', '发布、批改与查看提交情况'],
    'student-records': ['学生记录', '查看学生与 AI 助手的交互记录'],
    'admin-home': ['系统管理台', '平台运行概况'],
    'user-manage': ['用户管理', '管理学生、教师与管理员账号'],
    'role-manage': ['角色权限', '配置不同身份的功能权限'],
    'system-settings': ['系统设置', '维护平台基础参数'],
    'platform-records': ['平台学习数据', '原始行为记录、数据处理与课程归属'],
    profile: ['个人主页', '查看账号绑定、权限与个人工作台'],
  }

  const openDialog = (type) => {
    setMenuOpen(false)
    setDialog(type)
    setPasswordMessage('')
    setPasswords({ current: '', next: '', confirm: '' })
  }

  const changePassword = async (event) => {
    event.preventDefault()
    if (!passwords.current || !passwords.next || !passwords.confirm) {
      setPasswordMessage('请完整填写密码信息')
      return
    }
    if (passwords.next.length < 6) {
      setPasswordMessage('新密码至少需要 6 位')
      return
    }
    if (passwords.next !== passwords.confirm) {
      setPasswordMessage('两次输入的新密码不一致')
      return
    }
    setPasswordMessage('正在修改密码...')
    try {
      await authApi.changePassword({
        current_password: passwords.current,
        new_password: passwords.next,
      })
      setPasswordMessage('密码修改成功')
      setTimeout(() => setDialog(null), 800)
    } catch (error) {
      setPasswordMessage(error.message || '密码修改失败，请稍后重试')
    }
  }

  return (
    <header className="topbar">
      <div><h1>{titles[page][0]}</h1><p>{titles[page][1]}</p></div>
      <div className="header-actions">
        <label className="search">
          <Search size={17} />
          <input placeholder="搜索课程、知识点..." />
          <kbd>⌘ K</kbd>
        </label>
        <button aria-label="通知" className="icon-button notification"><Bell size={19} /><i /></button>
        <div className="account-menu-wrap">
          <button
            className={`header-avatar account-trigger ${menuOpen ? 'active' : ''}`}
            aria-label="打开账户菜单"
            onClick={() => setMenuOpen((open) => !open)}
          >
            {user.name.slice(0, 1)}
          </button>
          {menuOpen && (
            <div className="account-dropdown">
              <div className="account-summary">
                <div className="avatar">{user.name.slice(0, 1)}</div>
                <div>
                  <strong>{user.name}</strong>
                  <span>{roleConfig[user.role].label} · {user.accountId}</span>
                </div>
              </div>
              <button onClick={() => openDialog('profile')}><CircleUserRound size={16} />个人资料</button>
              <button onClick={() => openDialog('password')}><Shield size={16} />修改密码</button>
              <div className="account-divider" />
              <button className="danger" onClick={onLogout}><LogOut size={16} />退出登录</button>
            </div>
          )}
        </div>
      </div>
      {dialog && (
        <div className="dialog-backdrop" onMouseDown={() => setDialog(null)}>
          <div className="account-dialog" onMouseDown={(event) => event.stopPropagation()}>
            <button className="dialog-close" aria-label="关闭" onClick={() => setDialog(null)}><X size={18} /></button>
            {dialog === 'profile' ? (
              <>
                <div className="dialog-avatar">{user.name.slice(0, 1)}</div>
                <h2>{user.name}</h2>
                <p>{roleConfig[user.role].label}账户</p>
                <div className="profile-list">
                  <div><span>登录账号</span><strong>{user.accountId}</strong></div>
                  <div><span>用户身份</span><strong>{roleConfig[user.role].label}</strong></div>
                  <div><span>所属信息</span><strong>{user.detail}</strong></div>
                </div>
              </>
            ) : (
              <form onSubmit={changePassword}>
                <h2>修改密码</h2>
                <p>为保障账号安全，请设置至少 6 位的新密码。</p>
                <label className="login-field"><span>当前密码</span><input type="password" value={passwords.current} onChange={(event) => setPasswords({ ...passwords, current: event.target.value })} /></label>
                <label className="login-field"><span>新密码</span><input type="password" value={passwords.next} onChange={(event) => setPasswords({ ...passwords, next: event.target.value })} /></label>
                <label className="login-field"><span>确认新密码</span><input type="password" value={passwords.confirm} onChange={(event) => setPasswords({ ...passwords, confirm: event.target.value })} /></label>
                {passwordMessage && <div className={`password-message ${passwordMessage.includes('成功') ? 'success' : ''}`}>{passwordMessage}</div>}
                <button className="login-submit" type="submit">确认修改</button>
              </form>
            )}
          </div>
        </div>
      )}
    </header>
  )
}

function StatCard({ icon: Icon, color, value, label, hint }) {
  return (
    <div className="stat-card">
      <div className={`stat-icon ${color}`}><Icon size={21} /></div>
      <div><strong>{value}</strong><span>{label}</span></div>
      <small>{hint}</small>
    </div>
  )
}

function useStudentOverview() {
  const [state, setState] = useState({ data: null, loading: true, error: '' })
  const [version, setVersion] = useState(0)

  useEffect(() => {
    let active = true
    setState((current) => ({ ...current, loading: true, error: '' }))
    learningApi.overview()
      .then((data) => { if (active) setState({ data, loading: false, error: '' }) })
      .catch((error) => { if (active) setState({ data: null, loading: false, error: error.message }) })
    return () => { active = false }
  }, [version])

  return { ...state, retry: () => setVersion((current) => current + 1) }
}

function OverviewStatus({ loading, error, retry }) {
  return <div className="page"><section className="panel overview-status" role="status">
    <p>{loading ? '正在读取课程进度...' : `课程进度读取失败：${error}`}</p>
    {!loading && <button type="button" className="outline-button" onClick={retry}>重新加载</button>}
  </section></div>
}

function HomePage({ setPage, onOpenCourse }) {
  const overview = useStudentOverview()
  if (overview.loading || overview.error) return <OverviewStatus {...overview} />

  const nextCourse = overview.data.courses.find((item) => item.next_lesson)
  const firstCourse = nextCourse || overview.data.courses[0]
  return (
    <div className="page home-page">
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow"><Sparkles size={14} /> 当前学习进度</span>
          <h2>{nextCourse ? <>继续学习 <em>{nextCourse.next_lesson.title}</em></> : <>开始你的 <em>课程学习</em></>}</h2>
          <p>{nextCourse ? `下一节位于${nextCourse.title}的“${nextCourse.next_lesson.chapter_title}”。阅读讲义并通过小测后，进度会自动保存。` : '选择一门课程，阅读教师讲义并完成知识点小测。'}</p>
          <button className="primary-button" onClick={() => firstCourse && onOpenCourse(firstCourse.id)} disabled={!firstCourse}>进入课程 <ArrowRight size={17} /></button>
        </div>
        <div className="hero-visual">
          <div className="code-window">
            <div className="window-dots"><i /><i /><i /></div>
            <code><span>while</span> energy &gt; <b>0</b>:</code>
            <code>　keep_learning()</code>
            <code>　energy -= <b>1</b></code>
          </div>
        </div>
      </section>

      <div className="content-grid">
        <section className="panel continue-panel">
          <div className="panel-heading"><div><h3>课程学习</h3><p>通过小测的知识点才计入进度</p></div></div>
          {overview.data.courses.length ? overview.data.courses.map((course) => {
            const progress = course.total_lessons ? Math.round(course.completed_lessons / course.total_lessons * 100) : 0
            return <CourseRow key={course.id} kind={course.id === 'data-structures-python' ? 'algo' : 'python'} code={course.id === 'data-structures-python' ? 'DS' : 'PY'}
              title={course.title} tag={progress === 100 ? '已完成' : course.completed_lessons ? '进行中' : '未开始'}
              detail={course.next_lesson?.chapter_title || '当前课程已学完'} progress={progress}
              count={`${course.completed_lessons} / ${course.total_lessons} 个知识点`} onClick={() => onOpenCourse(course.id)} />
          }) : <p className="overview-empty">教师尚未发布课程。</p>}
        </section>

      </div>

      <section className="panel recommendation">
        <div className="recommend-icon"><Lightbulb size={22} /></div>
        <div><strong>学习提示</strong><p>先看教师讲义，再在右侧运行代码；小测答对后会保存这一小节的完成状态。</p></div>
        <button className="outline-button" onClick={() => setPage('practice')}>进入练习 <ArrowRight size={15} /></button>
      </section>
    </div>
  )
}

function CourseRow({ kind, code, title, tag, detail, progress, count, onClick }) {
  return (
    <div className="course-row">
      <div className={`course-cover ${kind}`}><span>{code}</span></div>
      <div className="course-info">
        <div className="course-title"><strong>{title}</strong><span className={progress === 0 ? 'muted-tag' : ''}>{tag}</span></div>
        <p>{detail}</p>
        <div className="progress-line"><span style={{ width: `${progress}%` }} /></div>
        <small>{count}</small>
      </div>
      <button aria-label={`打开${title}`} className={`round-play ${progress === 0 ? 'light' : ''}`} onClick={onClick}>
        <Play size={18} fill="currentColor" />
      </button>
    </div>
  )
}

function CoursePage({ initialCourseId, onCourseChange, user }) {
  const [course, setCourse] = useState(() => ({ id: initialCourseId, title: '', chapters: [], lessons: {} }))
  const [courseId, setCourseId] = useState(initialCourseId)
  const [availableCourses, setAvailableCourses] = useState([])
  const [courseStatus, setCourseStatus] = useState('正在读取教师发布的课程内容...')
  const [courseLoadState, setCourseLoadState] = useState('loading')
  const [courseLoadVersion, setCourseLoadVersion] = useState(0)
  const [selected, setSelected] = useState('')
  const [done, setDone] = useState(new Set())
  const [openChapters, setOpenChapters] = useState(new Set())
  const [lessonMode, setLessonMode] = useState('learn')
  const [quizChoice, setQuizChoice] = useState('')
  const [quizMessage, setQuizMessage] = useState('')
  const [lessonOutput, setLessonOutput] = useState('Python 练习区就绪。点击运行后查看输出。')
  const [lessonRunning, setLessonRunning] = useState(false)
  const [quizSubmitting, setQuizSubmitting] = useState(false)
  const [handoutError, setHandoutError] = useState('')
  const [previewUrl, setPreviewUrl] = useState(null)
  const firstLessonId = course.chapters[0]?.points[0]?.id
  const currentLesson = course.lessons[selected] || course.lessons[firstLessonId]
  const lessonDraftEntries = useMemo(() => Object.entries(course.lessons).map(([id, lesson]) => ({
    id, code: lesson.practiceCode || lesson.code || '', defaultStdin: lesson.stdin || '',
  })), [course])
  const { drafts: lessonDrafts, status: lessonDraftStatus, updateDraft: updateLessonDraft, flushDraft: flushLessonDraft } =
    useCodeDrafts(user.accountId, 'lesson', lessonDraftEntries, courseLoadState === 'ready' ? selected : null)
  const selectedChapter = course.chapters.find((chapter) => chapter.points.some((point) => point.id === selected)) || course.chapters[0]
  const totalPoints = course.chapters.reduce((sum, chapter) => sum + chapter.points.length, 0)
  const completedPoints = course.chapters.reduce(
    (sum, chapter) => sum + chapter.points.filter((point) => done.has(point.id)).length,
    0,
  )
  const courseProgress = totalPoints ? Math.round((completedPoints / totalPoints) * 100) : 0
  const lessonCode = lessonDrafts[selected]?.code ?? currentLesson?.practiceCode ?? currentLesson?.code ?? ''
  const lessonStdin = lessonDrafts[selected]?.stdin ?? currentLesson?.stdin ?? ''

  useEffect(() => {
    let active = true
    courseApi.list().then((items) => { if (active) setAvailableCourses(items) }).catch(() => {})
    return () => { active = false }
  }, [])

  useEffect(() => {
    let active = true
    setCourseLoadState('loading')
    setCourseStatus('正在读取教师发布的课程内容...')
    Promise.all([courseApi.detail(courseId), courseApi.progress(courseId)])
      .then(([result, progress]) => {
        if (!active) return
        const nextCourse = normalizeCourse(result)
        setCourse(nextCourse)
        setCourseStatus(`已读取教师端发布内容，更新于 ${new Date(result.updated_at).toLocaleString('zh-CN')}`)
        setSelected(nextCourse.chapters[0]?.points[0]?.id || '')
        setOpenChapters(new Set(nextCourse.chapters[0] ? [nextCourse.chapters[0].id] : []))
        setDone(new Set(progress.map((item) => item.lesson_id)))
        setHandoutError('')
        setCourseLoadState('ready')
      })
      .catch((error) => {
        if (!active) return
        setCourseStatus(`课程读取失败：${error.message}`)
        setCourseLoadState('error')
      })
    return () => { active = false }
  }, [courseId, courseLoadVersion])

  const downloadHandout = async () => {
    const filename = selectedChapter?.handoutName
    if (!filename) return
    setHandoutError('')
    try {
      const blob = await courseApi.handout(course.id, selectedChapter.id)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 30000)
    } catch (error) {
      setHandoutError(`下载失败：${error.message}`)
    }
  }

  useEffect(() => {
    setLessonMode('learn')
    setQuizChoice('')
    setQuizMessage('')
    setLessonOutput('Python 练习区就绪。点击运行后查看输出。')
  }, [selected])

  useEffect(() => {
    let active = true
    let objectUrl = null
    setPreviewUrl(null)
    if (selectedChapter?.previewName) {
      courseApi.handoutPreview(course.id, selectedChapter.id)
        .then((blob) => {
          if (!active) return
          objectUrl = URL.createObjectURL(blob)
          setPreviewUrl(objectUrl)
        })
        .catch((error) => { if (active) setHandoutError(`讲义预览加载失败：${error.message}`) })
    }
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [course.id, selectedChapter?.id, selectedChapter?.previewName])

  const toggleChapter = (id) => {
    setOpenChapters((old) => {
      const next = new Set(old)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const getChapterProgress = (chapter) => {
    const completed = chapter.points.filter((point) => done.has(point.id)).length
    return Math.round((completed / chapter.points.length) * 100)
  }

  const updateLessonCode = (nextCode) => {
    updateLessonDraft(selected, { code: nextCode })
  }

  const runLessonCode = async () => {
    if (lessonRunning) return
    flushLessonDraft(selected)
    setLessonRunning(true)
    setLessonOutput(`正在运行 ${currentLesson.title} 的练习代码...\n`)
    try {
      const result = await executeApi.run(lessonCode, 'python', lessonStdin, {
        scope: 'lesson', resource_id: selected, course_id: course.id, lesson_id: selected,
      })
      const parts = []
      if (result.stdout) parts.push(result.stdout)
      if (result.stderr) parts.push(`[stderr]\n${result.stderr}`)
      parts.push(`\n进程已结束，退出代码 ${result.exit_code} · ${result.duration_ms}ms`)
      setLessonOutput(parts.join('\n'))
    } catch (error) {
      setLessonOutput(`运行失败：${error.message}`)
    } finally {
      setLessonRunning(false)
    }
  }

  const submitQuiz = async () => {
    if (!quizChoice) {
      setQuizMessage('请先选择一个答案。')
      return
    }
    setQuizSubmitting(true)
    setQuizMessage('正在检查答案...')
    try {
      const result = await courseApi.submitQuiz(courseId, selected, quizChoice)
      if (result.completed) setDone((old) => new Set([...old, selected]))
      setQuizMessage(result.correct ? '回答正确，本小节已完成并保存。' : '还不对，建议回到上面的讲解再看一遍。')
    } catch (error) {
      setQuizMessage(`提交失败：${error.message}。请重试，进度不会丢失。`)
    } finally {
      setQuizSubmitting(false)
    }
  }

  if (courseLoadState !== 'ready') {
    return <div className="page"><section className="panel management-panel"><p role="status">{courseStatus}</p>{courseLoadState === 'error' && <button type="button" className="primary-button" onClick={() => setCourseLoadVersion((value) => value + 1)}>重试加载</button>}</section></div>
  }

  return (
    <div className="course-layout">
      <aside className="chapter-panel">
        <label className="course-picker"><span>选择课程</span><select value={courseId} onChange={(event) => { setCourseId(event.target.value); onCourseChange(event.target.value) }} disabled={quizSubmitting || lessonRunning}>
          {(availableCourses.length ? availableCourses : [{ id: courseId, title: course.title }]).map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
        </select></label>
        <div className="chapter-title">
          <div className="course-cover python small"><span>{course.id === 'data-structures-python' ? 'DS' : 'PY'}</span></div>
          <div><strong>{course.title}</strong><span>课程进度 {courseProgress}%</span></div>
        </div>
        <p className="course-sync-status">{courseStatus}</p>
        <div className="progress-line chapter-progress"><span style={{ width: `${courseProgress}%` }} /></div>
        <div className="chapter-list">
          {course.chapters.map((chapter) => {
            const open = openChapters.has(chapter.id)
            const chapterProgress = getChapterProgress(chapter)
            return (
              <div key={chapter.id} className="chapter-block">
                <button className="chapter-button" onClick={() => toggleChapter(chapter.id)} disabled={quizSubmitting || lessonRunning}>
                  {open ? <ChevronDown size={17} /> : <ChevronRight size={17} />}
                  <span>{chapter.title}</span><small>{chapterProgress}%</small>
                </button>
                {open && chapter.points.map((point) => (
                  <button
                    className={`point-button ${selected === point.id ? 'selected' : ''}`}
                    key={point.id}
                    onClick={() => setSelected(point.id)}
                    disabled={quizSubmitting || lessonRunning}
                  >
                    <i className={done.has(point.id) ? 'complete' : ''}>{done.has(point.id) && <Check size={11} />}</i>
                    <span>{point.title}</span>
                  </button>
                ))}
              </div>
            )
          })}
        </div>
      </aside>
      <article className="lesson">
        <div className="lesson-breadcrumb"><span>{selectedChapter.title.split(' · ')[0]}</span><ChevronRight size={14} /><span>{selectedChapter.title.split(' · ')[1]}</span></div>
        <div className="lesson-header">
          <div>
            <h2>{currentLesson.title}</h2>
            <p className="lesson-lead">{currentLesson.lead}</p>
          </div>
          <span className={done.has(selected) ? 'lesson-status done' : 'lesson-status'}>{done.has(selected) ? '已完成' : '待小测'}</span>
        </div>
        {selectedChapter?.handoutName && <div className="course-handout-bar"><FileText size={18} /><span>教师课件：{selectedChapter.handoutName}</span><button type="button" onClick={() => downloadHandout()}>下载原版课件</button></div>}
        {previewUrl && <PdfPreview className="course-pdf-viewer" url={previewUrl} title={`${selectedChapter.previewName} 课程讲义预览`} />}
        {handoutError && <p className="lab-handout-error" role="alert">{handoutError}</p>}
        {currentLesson.isCoding && (
          <div className="lesson-tabs">
            <button className={lessonMode === 'learn' ? 'active' : ''} onClick={() => setLessonMode('learn')}>知识讲解</button>
            <button className={lessonMode === 'python' ? 'active' : ''} onClick={() => setLessonMode('python')}><Code2 size={14} /> Python 练习</button>
          </div>
        )}
        {lessonMode === 'learn' && (
          <>
            <div className="concept-card">
              <div className="concept-icon"><Lightbulb size={20} /></div>
              <div><strong>核心概念</strong><p>{currentLesson.concept}</p></div>
            </div>
            {currentLesson.code && <><h3>{currentLesson.syntaxTitle || '代码示例'}</h3>
            <div className="lesson-code">
              <div><span>Python</span><button onClick={() => navigator.clipboard?.writeText(currentLesson.code)}>复制代码</button></div>
              <pre>{currentLesson.code}</pre>
            </div></>}
            <h3>学习过程</h3>
            <div className="steps">
              {currentLesson.steps.map(([title, detail], index) => (
                <React.Fragment key={title}>
                  <Step number={String(index + 1)} title={title} detail={detail} />
                  {index < currentLesson.steps.length - 1 && <ChevronRight size={18} />}
                </React.Fragment>
              ))}
            </div>
          </>
        )}
        {lessonMode === 'python' && currentLesson.isCoding && (
          <section className="lesson-python-panel">
            <div className="lesson-python-toolbar">
              <div><FileCode2 size={15} /><strong>{currentLesson.title}.py</strong><span>{lessonDraftStatus}</span></div>
              <button className="run-button" onClick={runLessonCode} disabled={lessonRunning}><Play size={14} fill="currentColor" />{lessonRunning ? '运行中...' : '运行代码'}</button>
            </div>
            <div className="lesson-python-editor">
              <div className="line-numbers">{Array.from({ length: Math.max(8, lessonCode.split('\n').length) }, (_, i) => <span key={i}>{i + 1}</span>)}</div>
              <textarea value={lessonCode} onChange={(event) => updateLessonCode(event.target.value)} spellCheck="false" />
            </div>
            <div className="lesson-python-console">
              <label><span>标准输入</span><textarea value={lessonStdin} onChange={(event) => updateLessonDraft(selected, { stdin: event.target.value })} placeholder="需要 input() 时填在这里" /></label>
              <pre>{lessonOutput}</pre>
            </div>
          </section>
        )}
        <section className="lesson-quiz">
          <div className="quiz-heading">
            <div><strong>本节小测</strong><p>答对后才会标记完成这一小节。</p></div>
            {done.has(selected) && <span><Check size={13} /> 已通过</span>}
          </div>
          <h3>{currentLesson.quiz.question}</h3>
          <div className="quiz-options">
            {currentLesson.quiz.options.map((option) => (
              <button
                key={option}
                className={quizChoice === option ? 'selected' : ''}
                disabled={quizSubmitting}
                onClick={() => {
                  setQuizChoice(option)
                  setQuizMessage('')
                }}
              >
                {option}
              </button>
            ))}
          </div>
          {quizMessage && <p className={`quiz-message ${quizMessage.includes('正确') ? 'success' : ''}`}>{quizMessage}</p>}
          <button className={done.has(selected) ? 'done-button' : 'primary-button lesson-action'} onClick={submitQuiz} disabled={quizSubmitting}>
            <Check size={16} /> {quizSubmitting ? '正在提交...' : done.has(selected) ? '重新检查答案' : '提交答案并完成'}
          </button>
        </section>
        <div className="lesson-footer">
          <span><Clock3 size={15} /> 预计学习 {currentLesson.minutes} 分钟</span>
          <span><Target size={15} /> 当前课程进度 {courseProgress}%</span>
        </div>
      </article>
    </div>
  )
}

function Step({ number, title, detail }) {
  return <div><i>{number}</i><p><strong>{title}</strong><span>{detail}</span></p></div>
}

function PracticePage({ user, onContextChange }) {
  const previousExamples = [
    {
      id: 'scratch',
      title: '课堂自由练习',
      file: 'classroom.py',
      code: '',
      defaultStdin: '',
    },
    {
      id: 'guess-number',
      title: '猜数字游戏',
      difficulty: '基础',
      file: 'guess_number.py',
      description: '练习 while 循环与条件判断',
      guide: {
        title: '实验二：使用循环完成猜数字游戏',
        teacher: '张老师',
        updatedAt: '2026-06-15 09:30',
        objective: '掌握 while 循环、条件分支和用户输入的组合使用。',
        requirements: [
          '程序随机生成一个 1 到 100 之间的整数。',
          '用户可重复输入猜测，程序提示偏大或偏小。',
          '猜中后结束循环，并输出总尝试次数。',
        ],
        tips: '使用 random.randint(1, 100) 生成答案，并在循环体内更新 guess。',
      },
      defaultStdin: '50\n25\n42',
      code: `answer = 42
guess = 0
attempts = 0

while guess != answer:
    guess = int(input("请输入你的猜测："))
    attempts += 1
    if guess > answer:
        print("猜大了")
    elif guess < answer:
        print("猜小了")
    else:
        print(f"猜对了，一共尝试 {attempts} 次")
`,
    },
    {
      id: 'multiplication-table',
      title: '打印乘法表',
      difficulty: '基础',
      file: 'multiplication.py',
      description: '练习循环嵌套与格式化输出',
      guide: {
        title: '实验三：九九乘法表',
        teacher: '张老师',
        updatedAt: '2026-06-14 16:20',
        objective: '理解嵌套循环的执行顺序。',
        requirements: ['使用两层 for 循环。', '输出完整九九乘法表。', '保持列对齐。'],
        tips: '外层循环控制行，内层循环控制当前行的列数。',
      },
      code: `for row in range(1, 10):
    for col in range(1, row + 1):
        print(f"{col}×{row}={col * row}", end="\\t")
    print()
`,
      defaultStdin: '',
    },
    {
      id: 'character-frequency',
      title: '统计字符频率',
      difficulty: '进阶',
      file: 'frequency.py',
      description: '练习字符串、字典和循环',
      guide: {
        title: '实验四：字符频率统计',
        teacher: '张老师',
        updatedAt: '2026-06-13 11:10',
        objective: '使用字典完成数据计数。',
        requirements: ['接收一行文本。', '忽略空格。', '按字符输出出现次数。'],
        tips: '可使用 dictionary.get(char, 0) 简化计数逻辑。',
      },
      code: `text = input("请输入一段文本：")
frequency = {}

for char in text:
    if char != " ":
        frequency[char] = frequency.get(char, 0) + 1

print(frequency)
`,
      defaultStdin: 'hello python',
    },
  ]
  const [tasks, setTasks] = useState([])
  const [taskError, setTaskError] = useState('')
  const [activeProblem, setActiveProblem] = useState('scratch')
  const [attempt, setAttempt] = useState(null)
  const [attemptLoading, setAttemptLoading] = useState(false)
  const [submitMessage, setSubmitMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const submissionRequest = useRef(null)
  const problems = useMemo(() => [previousExamples[0], ...tasks.map(task => {
    const source = attempt?.assignment_id === task.id ? { ...attempt.task, deadline_at: task.deadline_at } : task
    return { ...source, code: source.initial_code, defaultStdin: source.stdin, file: 'classroom.ipynb' }
  })], [tasks, attempt])
  const currentProblem = problems.find(problem => problem.id === activeProblem) || problems[0]
  const draftEntries = problems.filter(problem => problem.id === 'scratch' || (problem.id === currentProblem.id && attempt?.assignment_id === problem.id))
  const { drafts, status: draftStatus, updateDraft, flushDraft } = useCodeDrafts(user.accountId, 'experiment', draftEntries, currentProblem.id)
  const [lectureCourseId, setLectureCourseId] = useState('data-structures-python')
  const [lectureCourses, setLectureCourses] = useState([])
  const [lectureCourse, setLectureCourse] = useState(null)
  const [lectureLessonId, setLectureLessonId] = useState('')
  const [lectureStatus, setLectureStatus] = useState('正在读取教师发布的课程讲义...')
  const [lectureHandoutUrl, setLectureHandoutUrl] = useState(null)
  const [lectureHandoutError, setLectureHandoutError] = useState('')
  const [lectureDirectoryOpen, setLectureDirectoryOpen] = useState(false)
  const notebookRef = useRef(null)
  const [running, setRunning] = useState(false)
  const [guideOpen, setGuideOpen] = useState(true)
  const [remoteGuide, setRemoteGuide] = useState(null)
  const [handoutUrl, setHandoutUrl] = useState(null)
  const [handoutError, setHandoutError] = useState('')
  const [ideTheme, setIdeTheme] = useState(() => localStorage.getItem('python_ide_theme') || 'light')
  const code = drafts[currentProblem.id]?.code ?? currentProblem.code
  const stdin = drafts[currentProblem.id]?.stdin ?? currentProblem.defaultStdin ?? ''
  const guide = remoteGuide || currentProblem.guide
  const lectureChapter = lectureCourse?.chapters.find((chapter) => chapter.lessons.some((lesson) => lesson.id === lectureLessonId)) || lectureCourse?.chapters[0]
  const lectureLesson = lectureChapter?.lessons.find((lesson) => lesson.id === lectureLessonId) || lectureChapter?.lessons[0]

  useEffect(() => {
    let active = true
    courseApi.list().then((items) => { if (active) setLectureCourses(items) }).catch(() => {})
    return () => { active = false }
  }, [])

  useEffect(() => {
    let active = true
    setLectureStatus('正在读取教师发布的课程讲义...')
    setLectureCourse(null)
    courseApi.detail(lectureCourseId)
      .then((result) => {
        if (!active) return
        setLectureCourse(result)
        const chapter = result.chapters.find(item => item.id === currentProblem.chapter_id) || result.chapters[0]
        setLectureLessonId(chapter?.lessons[0]?.id || '')
        setLectureStatus('')
      })
      .catch((error) => { if (active) setLectureStatus(`讲义读取失败：${error.message}`) })
    return () => { active = false }
  }, [lectureCourseId, currentProblem.chapter_id])

  useEffect(() => {
    let active = true
    let objectUrl = null
    setLectureHandoutUrl(null)
    setLectureHandoutError('')
    if (lectureChapter?.preview_name) {
      courseApi.handoutPreview(lectureCourse.id, lectureChapter.id)
        .then((blob) => {
          if (!active) return
          objectUrl = URL.createObjectURL(blob)
          setLectureHandoutUrl(objectUrl)
        })
        .catch((error) => { if (active) setLectureHandoutError(`课件加载失败：${error.message}`) })
    }
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [lectureCourse?.id, lectureChapter?.id, lectureChapter?.preview_name])

  useEffect(() => {
    localStorage.setItem('python_ide_theme', ideTheme)
  }, [ideTheme])

  useEffect(() => {
    let active = true
    let objectUrl = null
    setRemoteGuide(null)
    setHandoutUrl(null)
    setHandoutError('')
    if (currentProblem.id === 'scratch') return () => { active = false }
    experimentApi.detail(currentProblem.id)
      .then(async (result) => {
        if (!active) return
        setRemoteGuide({
          title: result.guide_title,
          teacher: result.teacher_name,
          updatedAt: new Date(result.updated_at).toLocaleString('zh-CN'),
          objective: result.objective,
          requirements: result.requirements,
          tips: result.tips,
          handoutName: result.handout_name,
        })
        if (result.handout_name) {
          try {
            const blob = await experimentApi.handout(currentProblem.id)
            if (!active) return
            objectUrl = URL.createObjectURL(blob)
            setHandoutUrl(objectUrl)
          } catch (error) {
            if (active) setHandoutError(`PDF 讲义加载失败：${error.message}`)
          }
        }
      })
      .catch(() => {})
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [currentProblem.id])

  const loadLectureExample = () => {
    if (!lectureLesson?.is_coding || running) return
    const exampleCode = lectureLesson.practice_code || lectureLesson.code
    const scratchCode = drafts.scratch?.code || ''
    if (scratchCode !== problems[0].code && scratchCode !== exampleCode && !window.confirm('这会替换自由练习中的现有代码，确定继续吗？')) return
    updateDraft('scratch', { code: exampleCode, stdin: lectureLesson.stdin || '' })
    setActiveProblem('scratch')
  }

  const downloadLectureHandout = async () => {
    const filename = lectureChapter?.handout_name
    if (!filename) return
    setLectureHandoutError('')
    try {
      const blob = await courseApi.handout(lectureCourse.id, lectureChapter.id)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 30000)
    } catch (error) {
      setLectureHandoutError(`课件下载失败：${error.message}`)
    }
  }

  const updateCode = (nextCode) => {
    updateDraft(currentProblem.id, { code: nextCode })
  }

  useEffect(() => {
    let active = true
    const load = () => classroomApi.tasks().then(values => { if (active) { setTasks(values); setTaskError('') } }).catch(error => { if (active) setTaskError(error.message) })
    load()
    const timer = window.setInterval(load, 15000)
    return () => { active = false; window.clearInterval(timer) }
  }, [user.accountId])

  useEffect(() => {
    let active = true
    setAttempt(null); setSubmitMessage(''); submissionRequest.current = null
    if (currentProblem.id === 'scratch') { setAttemptLoading(false); return () => { active = false } }
    setAttemptLoading(true)
    classroomApi.start(currentProblem.id).then(value => {
      if (!active) return
      setAttempt(value); setLectureCourseId(value.course_id)
      setSubmitMessage(value.first_submitted_at ? `已提交 · ${dateText(value.first_submitted_at)}` : '')
    }).catch(error => { if (active) setSubmitMessage(error.message) }).finally(() => { if (active) setAttemptLoading(false) })
    return () => { active = false }
  }, [currentProblem.id, user.accountId])

  useEffect(() => {
    onContextChange({ courseId: currentProblem.course_id || lectureCourseId, attemptId: attempt?.assignment_id === currentProblem.id ? attempt.id : null, taskTitle: currentProblem.title, lessonId: lectureLesson?.id || null })
  }, [currentProblem.id, attempt?.id, lectureCourseId, lectureLesson?.id, onContextChange])

  const submitTask = async () => {
    if (!attempt || submitting || running) return
    setSubmitting(true); setSubmitMessage('正在提交…')
    try {
      await flushDraft(currentProblem.id)
      await flushLearning()
      if (!submissionRequest.current || submissionRequest.current.code !== code || submissionRequest.current.stdin !== stdin) submissionRequest.current = { request_id: crypto.randomUUID(), code, stdin }
      const result = await classroomApi.submit(attempt.id, submissionRequest.current)
      submissionRequest.current = null
      setSubmitMessage(`提交成功 · ${dateText(result.created_at)}`)
    } catch (error) { setSubmitMessage(error.message) } finally { setSubmitting(false) }
  }

  const deadlinePassed = currentProblem.deadline_at && new Date(currentProblem.deadline_at).getTime() <= Date.now()


  return (
    <div className={`lab-workspace theme-${ideTheme} ${currentProblem.id !== 'scratch' || submitMessage || taskError ? 'with-task-status' : ''}`}>
      <header className="lab-header">
        <div className="lab-title">
          <h2>{currentProblem.title}</h2>
        </div>
        <div className="lab-actions">
          <label className="lab-practice-picker">习题<select value={currentProblem.id} onChange={(event) => setActiveProblem(event.target.value)} disabled={running || submitting}>{problems.map((problem) => <option key={problem.id} value={problem.id}>{problem.title}</option>)}</select></label>
          <span className="lab-connection">Python 3 练习环境</span>
          <button type="button" onClick={() => setIdeTheme((theme) => theme === 'light' ? 'dark' : 'light')}>
            <Settings size={16} />{ideTheme === 'light' ? '深色主题' : '浅色主题'}
          </button>
          <button type="button" aria-expanded={guideOpen} onClick={() => setGuideOpen((open) => !open)}>
            <BookOpen size={16} />{guideOpen ? '收起讲义' : '展开讲义'}
          </button>
          <button type="button" className="lab-run" onClick={() => notebookRef.current?.runAll()} disabled={running}>
            <Play size={16} fill="currentColor" />{running ? '运行中...' : '运行全部'}
          </button>
          {currentProblem.id !== 'scratch' && <button type="button" className="lab-run" onClick={submitTask} disabled={running || submitting || attemptLoading || !attempt || !!deadlinePassed || !currentProblem.is_published}>{submitting ? '提交中…' : '提交作业'}</button>}
        </div>
      </header>
      {(currentProblem.id !== 'scratch' || submitMessage || taskError) && <div className="classroom-task-status" role="status">{currentProblem.id !== 'scratch' && <span>截止：{dateText(currentProblem.deadline_at)}{deadlinePassed ? ' · 已截止' : ''}</span>}<span>{submitMessage || taskError}</span></div>}
      <div className={`lab-content ${guideOpen ? '' : 'guide-hidden'}`}>
        {guideOpen && (
          <aside className="lab-guide" aria-label="教师课堂讲义">
            <div className="lab-pane-heading">
              <div className="lab-lecture-heading"><BookOpen size={18} /><strong>{lectureChapter?.title || '课堂讲义'}</strong></div>
              <div className="lab-lecture-actions">
                <button type="button" aria-expanded={lectureDirectoryOpen} aria-controls="lab-lecture-directory" onClick={() => setLectureDirectoryOpen((open) => !open)}>目录</button>
                {lectureChapter && <details className="lab-lecture-menu" key={lectureChapter.id}
                  onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false }}
                  onKeyDown={(event) => { if (event.key === 'Escape') { event.currentTarget.open = false; event.currentTarget.querySelector('summary').focus() } }}>
                  <summary aria-label="讲义工具">更多<ChevronDown size={14} /></summary>
                  <div className="lab-lecture-menu-items" onClick={(event) => { if (event.target.closest('button')) event.currentTarget.closest('details').open = false }}>
                    {lectureChapter.handout_name && <button type="button" onClick={() => downloadLectureHandout()}>下载原版讲义</button>}
                    {lectureLesson?.is_coding && <button type="button" onClick={loadLectureExample} disabled={running}>载入本节示例</button>}
                  </div>
                </details>}
              </div>
            </div>
            <div className="lab-guide-scroll lab-lecture-body">
              {currentProblem.instructions && <section className="classroom-task-instructions"><h3>{currentProblem.title}</h3><p>{currentProblem.instructions}</p></section>}
              {lectureDirectoryOpen && <div className="lab-lecture-pickers" id="lab-lecture-directory">
                <label>课程<select value={lectureCourseId} onChange={(event) => setLectureCourseId(event.target.value)}>
                  {(lectureCourses.length ? lectureCourses : [{ id: lectureCourseId, title: '数据结构（Python）' }]).map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
                </select></label>
                {lectureCourse && <label>章节<select value={lectureChapter?.id || ''} onChange={(event) => {
                  const chapter = lectureCourse.chapters.find((item) => item.id === event.target.value)
                  setLectureLessonId(chapter?.lessons[0]?.id || '')
                  setLectureDirectoryOpen(false)
                }}>
                  {lectureCourse.chapters.map((chapter) => <option key={chapter.id} value={chapter.id}>{chapter.title}</option>)}
                </select></label>}
                {lectureChapter && <label>本章知识点<select value={lectureLesson?.id || ''} onChange={(event) => { setLectureLessonId(event.target.value); setLectureDirectoryOpen(false) }}>
                  {lectureChapter.lessons.map((lesson) => <option key={lesson.id} value={lesson.id}>{lesson.title}</option>)}
                </select></label>}
              </div>}
              {lectureStatus && <p className="lab-lecture-status" role="status">{lectureStatus}</p>}
              {lectureHandoutError && <p className="lab-handout-error" role="alert">{lectureHandoutError}</p>}
              {lectureChapter?.preview_name ? (
                <div className="lab-lecture-preview">
                  {lectureHandoutUrl
                    ? <PdfPreview className="lab-pdf-viewer" url={lectureHandoutUrl} title={`${lectureChapter.preview_name} 课堂讲义预览`} />
                    : !lectureHandoutError && <p className="lab-lecture-status" role="status">正在加载讲义…</p>}
                </div>
              ) : lectureLesson && <div className="lab-guide-article lab-lecture-article">
                <h3>{lectureLesson.title}</h3>
                {lectureLesson.lead && <p className="lab-lecture-lead">{lectureLesson.lead}</p>}
                <section><h4>讲义正文</h4><p>{lectureLesson.concept}</p></section>
                {lectureLesson.code && <section><h4>{lectureLesson.syntax_title || 'Python 示例'}</h4><pre className="lab-lecture-code">{lectureLesson.code}</pre></section>}
                {lectureLesson.steps?.length > 0 && <section><h4>学习步骤</h4><ol>{lectureLesson.steps.map(([title, detail], index) => <li key={`${title}-${index}`}><strong>{title}：</strong>{detail}</li>)}</ol></section>}
              </div>}
              {currentProblem.guide && <details className="lab-task-details">
                <summary>当前实验任务：{guide.title}</summary>
                <div className="lab-guide-article">
                  <p className="lab-guide-meta">{guide.teacher} · 更新于 {guide.updatedAt}</p>
                  {guide.handoutName && <div className="lab-pdf-title"><FileText size={16} /><strong>{guide.handoutName}</strong></div>}
                  {handoutUrl && <PdfPreview className="lab-pdf-viewer" url={handoutUrl} title={`${guide.handoutName} PDF 任务资料`} />}
                  {handoutError && <p className="lab-handout-error" role="alert">{handoutError}</p>}
                  <section><h4>任务目标</h4><p>{guide.objective}</p></section>
                  <section><h4>任务要求</h4><ol>{guide.requirements.map((item) => <li key={item}>{item}</li>)}</ol></section>
                  <div className="lab-tip"><Lightbulb size={18} /><div><strong>教师提示</strong><p>{guide.tips}</p></div></div>
                </div>
              </details>}
            </div>
          </aside>
        )}
        {currentProblem.id !== 'scratch' && (attemptLoading || !attempt) ? <div className="lab-workbench"><p role="status">{attemptLoading ? '正在恢复本次做题…' : '无法打开习题，请重新选择或联系老师。'}</p></div> : <Notebook ref={notebookRef} key={`${user.accountId}:${currentProblem.id}`} value={code} name={currentProblem.file.replace(/\.py$/, '.ipynb')} defaultCode={currentProblem.code}
          onChange={updateCode} onFlush={() => flushDraft(currentProblem.id)} stdin={stdin} onStdinChange={(next) => updateDraft(currentProblem.id, { stdin: next })}
          resourceId={currentProblem.id} courseId={currentProblem.course_id || lectureCourseId} lessonId={lectureLesson?.id} attemptId={attempt?.id} onRunningChange={setRunning} draftStatus={draftStatus}
          extraActions={attempt && <span className="classroom-note">题目版本 {attempt.task_version}</span>} />}
      </div>
    </div>
  )
}

function ProfilePage({ user, setPage }) {
  const roleLabel = roleConfig[user.role]?.label || user.role
  const roleCopy = {
    student: {
      title: '学生个人主页',
      summary: '查看个人信息，继续课程学习或进入在线练习。',
      actions: [
        [BookOpen, '继续课程学习', '查看讲义、知识点与课后小测', 'course'],
        [Terminal, '进入在线练习', '边看教师课堂讲义边写 Python', 'practice'],
      ],
    },
    teacher: {
      title: '教师工作档案',
      summary: '教师账号负责维护课堂讲义、实验任务和小测问题，学生端会读取老师发布的内容。',
      actions: [
        [BookOpen, '管理课程内容', '维护章节、知识点和小测', 'course-manage'],
        [FileCode2, '管理实验任务', '维护在线练习任务说明', 'experiment-manage'],
        [BarChart3, '查看学生记录', '查看后续汇总的学习行为', 'student-records'],
      ],
    },
    admin: {
      title: '管理员工作档案',
      summary: '管理员账号负责平台账号、角色权限和系统配置，保证学生与教师权限边界清晰。',
      actions: [
        [Users, '管理平台账号', '创建学生、教师和管理员账号', 'user-manage'],
        [Shield, '查看角色权限', '确认不同身份看到的功能', 'role-manage'],
        [Settings, '维护系统设置', '上线前配置安全与服务参数', 'system-settings'],
      ],
    },
  }[user.role]

  const recordItems = user.role === 'teacher'
    ? ['课程讲义修改会记录到教师账号', '实验任务发布会带上教师身份', '学生行为数据后续由教师端汇总查看']
    : ['账号创建会记录管理员操作者', '账号由管理员分配，使用账号和密码登录', '系统统计来自后端账号与课程接口']

  return (
    <div className="page profile-page">
      <section className="panel profile-hero-card">
        <div className="profile-avatar-large">{user.name.slice(0, 1)}</div>
        <div className="profile-identity">
          <span>{roleCopy.title}</span>
          <h2>{user.name}</h2>
          <p>{roleCopy.summary}</p>
          <div className="profile-tags">
            <i>{roleLabel}</i>
            <i>账号 {user.accountId}</i>
          </div>
        </div>
      </section>

      {user.role !== 'admin' && <QwenKeySettings />}

      <div className="profile-grid">
        <section className="panel profile-card">
          <div className="panel-heading"><div><h3>账号信息</h3><p>用于登录和身份确认</p></div><CircleUserRound size={20} /></div>
          <div className="profile-info-list">
            <div><span>登录账号</span><strong>{user.accountId}</strong></div>
            <div><span>当前身份</span><strong>{roleLabel}</strong></div>
            <div><span>所属信息</span><strong>{user.detail || '未填写'}</strong></div>
          </div>
        </section>

        <section className="panel profile-card">
          <div className="panel-heading"><div><h3>个人工作台</h3><p>按当前身份展示常用入口</p></div><Zap size={20} /></div>
          <div className="profile-action-list">
            {roleCopy.actions.map(([Icon, title, desc, target]) => (
              <button key={target} type="button" onClick={() => setPage(target)}>
                <Icon size={19} />
                <span><strong>{title}</strong><small>{desc}</small></span>
                <ChevronRight size={17} />
              </button>
            ))}
          </div>
        </section>
      </div>

      {user.role !== 'student' && <section className="panel profile-card profile-record-card">
        <div className="panel-heading"><div><h3>账号数据记录</h3><p>这里说明当前账号会产生哪些后台记录</p></div><Database size={20} /></div>
        <div className="profile-record-list">
          {recordItems.map((item, index) => (
            <div key={item}><span>{index + 1}</span><strong>{item}</strong></div>
          ))}
        </div>
      </section>}
      {user.role === 'student' && <p className="student-data-notice">平台会保存必要的学习操作，用于教学反馈和课程改进。</p>}
    </div>
  )
}

const editionLoginCopy = {
  student: {
    title: '看讲义，动手练习。',
    description: '学习课程、完成课堂习题，在 Notebook 中编写代码，与 AI 助教交流。',
    features: [[BookOpen, '课程讲义', '阅读老师发布的内容'], [Code2, 'Notebook 实践', '编写代码与运行验证'], [Bot, 'AI 助教', '使用个人千问 API']],
  },
  teacher: {
    title: '准备课堂，关注学习。',
    description: '管理课程讲义与知识点，发布有截止时间的习题，查看所授课程的学生学习记录。',
    features: [[BookOpen, '课程内容', '讲义与知识点管理'], [ClipboardList, '课堂作业', '发布习题与设置截止时间'], [BarChart3, '学生记录', '查看做题与 AI 交互情况']],
  },
  admin: {
    title: '独立管理，统一维护。',
    description: '管理平台账号、课程归属与学生名单，查看和导出全平台的学习行为数据。',
    features: [[Users, '账号管理', '管理三类用户账号'], [Shield, '课程归属', '设置教师与学生名单'], [Database, '学习数据', '查看、处理与导出记录']],
  },
}

function LoginPage({ onLogin, edition }) {
  const config = PLATFORM_EDITIONS[edition]
  const copy = editionLoginCopy[edition]
  const isStudent = edition === 'student'
  const accountLabel = isStudent ? '账号' : config.accountLabel
  const [account, setAccount] = useState('')
  const [password, setPassword] = useState('')
  const [passwordVisible, setPasswordVisible] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    if (!account.trim() || !password.trim()) {
      setError('请输入账号和密码')
      return
    }
    setError('')
    setSubmitting(true)
    try {
      const result = await authApi.login({
        account_id: account.trim(),
        password,
        expected_role: edition,
      })
      onLogin({
        accountId: result.user.account_id,
        role: result.user.role,
        name: result.user.name,
        phone: result.user.phone,
        detail: result.user.detail,
      }, result.access_token)
    } catch (loginError) {
      setError(loginError.message || '登录失败，请检查账号和密码')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className={`login-page edition-${edition}`}>
      <section className="login-showcase">
        <Brand edition={edition} />
        <div className="login-copy">
          {!isStudent && <span><Sparkles size={15} /> {config.label}</span>}
          <h1>{copy.title}</h1>
          <p>{copy.description}</p>
        </div>
        <div className="login-feature-row">
          {copy.features.map(([Icon, title, description]) => <div key={title}><Icon size={19} /><strong>{title}</strong><small>{description}</small></div>)}
        </div>
      </section>
      <section className="login-form-side">
        <form className="login-card" onSubmit={submit}>
          <div className="mobile-brand"><Brand edition={edition} /></div>
          {!isStudent && <div className="edition-badge">{config.label}</div>}
          <h2>{isStudent ? '欢迎登录' : `${roleConfig[edition].label}登录`}</h2>
          {!isStudent && <p>进入{roleConfig[edition].navCaption}</p>}
          <label className="login-field">
            <span>{accountLabel}</span>
            <input value={account} onChange={(event) => setAccount(event.target.value)} autoComplete="username" placeholder={`请输入${accountLabel}`} disabled={submitting} />
          </label>
          <div className="login-field">
            <label htmlFor="login-password"><span>密码</span></label>
            <div className="login-password-input">
              <input id="login-password" type={passwordVisible ? 'text' : 'password'} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" placeholder="请输入密码" disabled={submitting} />
              <button
                type="button"
                className="password-visibility-toggle"
                aria-label={passwordVisible ? '隐藏密码' : '显示密码'}
                aria-pressed={passwordVisible}
                aria-controls="login-password"
                title={passwordVisible ? '隐藏密码' : '显示密码'}
                onClick={() => setPasswordVisible(visible => !visible)}
                disabled={submitting}
              >
                {passwordVisible ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>
          {error && <div className="login-error" role="alert">{error}</div>}
          <button className="login-submit" type="submit" disabled={submitting}>{submitting ? '正在登录...' : isStudent ? '登录' : `登录${config.label}`} <ArrowRight size={17} /></button>
          {!isStudent && <div className="login-account-note">仅支持{roleConfig[edition].label}账号登录。</div>}
        </form>
      </section>
    </div>
  )
}

function ExperimentEditorPage({ user }) {
  const [experimentId, setExperimentId] = useState('guess-number')
  const [form, setForm] = useState({
    title: '猜数字游戏',
    description: '练习 while 循环与条件判断',
    guideTitle: '实验二：使用循环完成猜数字游戏',
    objective: '掌握 while 循环、条件分支和用户输入的组合使用。',
    requirements: '程序随机生成一个 1 到 100 之间的整数。\n用户可重复输入猜测，程序提示偏大或偏小。\n猜中后结束循环，并输出总尝试次数。',
    tips: '使用 random.randint(1, 100) 生成答案，并在循环体内更新 guess。',
  })
  const [status, setStatus] = useState('')
  const [handoutFile, setHandoutFile] = useState(null)
  const [handoutName, setHandoutName] = useState('')
  const handoutInputRef = useRef(null)

  useEffect(() => {
    let active = true
    setStatus('')
    setHandoutFile(null)
    setHandoutName('')
    if (handoutInputRef.current) handoutInputRef.current.value = ''
    experimentApi.detail(experimentId)
      .then((result) => {
        if (!active) return
        setForm({
          title: result.title,
          description: result.description,
          guideTitle: result.guide_title,
          objective: result.objective,
          requirements: result.requirements.join('\n'),
          tips: result.tips,
        })
        setHandoutName(result.handout_name || '')
      })
      .catch(() => {
        if (!active || experimentId === 'guess-number') return
        const title = { 'multiplication-table': '打印乘法表', 'character-frequency': '统计字符频率' }[experimentId]
        setForm({ title, description: '', guideTitle: '', objective: '', requirements: '', tips: '' })
      })
    return () => { active = false }
  }, [experimentId])

  const save = async (event) => {
    event.preventDefault()
    if (handoutFile && (!handoutFile.name.toLowerCase().endsWith('.pdf') || handoutFile.size > 10 * 1024 * 1024)) {
      setStatus('请选择不超过 10 MB 的 PDF 讲义')
      return
    }
    setStatus('正在保存...')
    try {
      await experimentApi.save(experimentId, {
        title: form.title,
        description: form.description,
        guide_title: form.guideTitle,
        objective: form.objective,
        requirements: form.requirements.split('\n').map((item) => item.trim()).filter(Boolean),
        tips: form.tips,
        teacher_id: user.accountId,
        teacher_name: user.name,
      })
      if (handoutFile) {
        await experimentApi.uploadHandout(experimentId, handoutFile)
        setHandoutName(handoutFile.name)
        setHandoutFile(null)
        if (handoutInputRef.current) handoutInputRef.current.value = ''
      }
      setStatus('实验任务已发布，学生端选择该练习后可查看任务说明')
    } catch (error) {
      setStatus(`发布未完成：${error.message}`)
    }
  }

  const removeHandout = async () => {
    if (!window.confirm(`确定移除“${handoutName}”吗？学生端将不再看到这份 PDF。`)) return
    setStatus('正在移除讲义...')
    try {
      await experimentApi.removeHandout(experimentId)
      setHandoutName('')
      setHandoutFile(null)
      if (handoutInputRef.current) handoutInputRef.current.value = ''
      setStatus('已移除 PDF 任务资料，文字说明仍然保留')
    } catch (error) {
      setStatus(`移除失败：${error.message}`)
    }
  }

  return (
    <div className="page experiment-editor-page">
      <form className="panel experiment-form" onSubmit={save}>
        <div className="panel-heading">
          <div><h3>实验任务管理</h3><p>模块位置：学生端“在线练习”的练习选择与任务详情</p></div>
          <button className="login-submit compact" type="submit">保存并发布</button>
        </div>
        <div className="teacher-module-note">
          <strong>这个模块负责什么？</strong>
          <p>这里维护猜数字等具体编程任务。上课时左侧默认显示的教师讲义，请到“课程管理”编辑章节、知识点和课件；不要把整章讲义放在实验任务里。</p>
        </div>
        <div className="experiment-form-grid">
          <label><span>实验标识</span><select value={experimentId} onChange={(event) => setExperimentId(event.target.value)}><option value="guess-number">猜数字游戏</option><option value="multiplication-table">打印乘法表</option><option value="character-frequency">统计字符频率</option></select></label>
          <label><span>实验名称</span><input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></label>
          <label className="wide"><span>简短说明</span><input value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
          <label className="wide"><span>指导标题</span><input value={form.guideTitle} onChange={(event) => setForm({ ...form, guideTitle: event.target.value })} /></label>
          <label className="wide"><span>实验目标</span><textarea value={form.objective} onChange={(event) => setForm({ ...form, objective: event.target.value })} /></label>
          <label className="wide"><span>实验要求（每行一条）</span><textarea value={form.requirements} onChange={(event) => setForm({ ...form, requirements: event.target.value })} /></label>
          <label className="wide"><span>教师提示</span><textarea value={form.tips} onChange={(event) => setForm({ ...form, tips: event.target.value })} /></label>
          <label className="wide"><span>实验任务 PDF 附件（可选，最多 10 MB；再次选择可替换）</span><input ref={handoutInputRef} type="file" accept="application/pdf,.pdf" onChange={(event) => setHandoutFile(event.target.files?.[0] || null)} /></label>
          {handoutName && <div className="experiment-handout-current"><span>当前已发布：{handoutName}</span><button type="button" onClick={removeHandout}>移除当前 PDF</button></div>}
        </div>
        {status && <div className={`editor-status ${status.includes('已发布') || status.startsWith('已移除') ? 'success' : ''}`}>{status}</div>}
      </form>
    </div>
  )
}

const createEmptyLesson = () => {
  const id = `lesson-${Date.now()}`
  return {
    id,
    title: '新知识点',
    lead: '请填写这一小节的导入说明。',
    concept: '请填写核心概念讲解。',
    syntax_title: '知识点示例',
    code: 'print("Hello")',
    steps: [['阅读讲义', '理解核心概念'], ['完成练习', '尝试运行代码'], ['回答小测', '通过后完成小节']],
    is_coding: true,
    practice_code: 'print("Hello")',
    stdin: '',
    quiz_question: '请填写本节小测问题。',
    quiz_options: ['选项 A', '选项 B', '选项 C'],
    quiz_answer: '选项 A',
    minutes: 10,
  }
}

function CourseEditorPage() {
  const [course, setCourse] = useState(null)
  const [courseId, setCourseId] = useState('data-structures-python')
  const [availableCourses, setAvailableCourses] = useState([])
  const [chapterIndex, setChapterIndex] = useState(0)
  const [lessonIndex, setLessonIndex] = useState(0)
  const [status, setStatus] = useState('正在读取课程内容...')
  const [handoutFile, setHandoutFile] = useState(null)
  const [previewFile, setPreviewFile] = useState(null)
  const [handoutBusy, setHandoutBusy] = useState(false)
  const [dirty, setDirty] = useState(false)
  const chapterHandoutInputRef = useRef(null)
  const chapterPreviewInputRef = useRef(null)

  useEffect(() => {
    courseApi.list().then(setAvailableCourses).catch(() => {})
  }, [])

  useEffect(() => {
    let active = true
    setCourse(null)
    setStatus('正在读取课程内容...')
    courseApi.detail(courseId)
      .then((result) => {
        if (!active) return
        setCourse(result)
        setChapterIndex(0)
        setLessonIndex(0)
        setHandoutFile(null)
        setPreviewFile(null)
        if (chapterHandoutInputRef.current) chapterHandoutInputRef.current.value = ''
        if (chapterPreviewInputRef.current) chapterPreviewInputRef.current.value = ''
        setDirty(false)
        setStatus(`已读取课程内容，更新于 ${new Date(result.updated_at).toLocaleString('zh-CN')}`)
      })
      .catch((error) => {
        if (!active) return
        setStatus(`课程读取失败：${error.message}`)
      })
    return () => { active = false }
  }, [courseId])

  if (!course) {
    return <div className="page management-page"><section className="panel management-panel"><label className="course-picker"><span>选择课程</span><select value={courseId} onChange={(event) => setCourseId(event.target.value)}>{(availableCourses.length ? availableCourses : [{ id: courseId, title: courseId }]).map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label><p>{status}</p></section></div>
  }

  const currentChapter = course.chapters[chapterIndex] || course.chapters[0]
  const currentLesson = currentChapter.lessons[lessonIndex] || currentChapter.lessons[0]

  const updateCourse = (patch) => { setDirty(true); setCourse((old) => ({ ...old, ...patch })) }
  const updateChapter = (patch) => {
    setDirty(true)
    setCourse((old) => ({
      ...old,
      chapters: old.chapters.map((chapter, index) => index === chapterIndex ? { ...chapter, ...patch } : chapter),
    }))
  }
  const updateLesson = (patch) => {
    setDirty(true)
    setCourse((old) => ({
      ...old,
      chapters: old.chapters.map((chapter, cIndex) => cIndex === chapterIndex ? {
        ...chapter,
        lessons: chapter.lessons.map((lesson, lIndex) => lIndex === lessonIndex ? { ...lesson, ...patch } : lesson),
      } : chapter),
    }))
  }

  const addChapter = () => {
    setDirty(true)
    const nextChapter = { id: `chapter-${Date.now()}`, title: '新章节', lessons: [createEmptyLesson()] }
    setCourse((old) => ({ ...old, chapters: [...old.chapters, nextChapter] }))
    setChapterIndex(course.chapters.length)
    setLessonIndex(0)
  }

  const deleteChapter = () => {
    if (course.chapters.length <= 1) {
      setStatus('至少保留一个章节')
      return
    }
    setDirty(true)
    setCourse((old) => ({ ...old, chapters: old.chapters.filter((_, index) => index !== chapterIndex) }))
    setChapterIndex(0)
    setLessonIndex(0)
  }

  const addLesson = () => {
    setDirty(true)
    setCourse((old) => ({
      ...old,
      chapters: old.chapters.map((chapter, index) => index === chapterIndex ? {
        ...chapter,
        lessons: [...chapter.lessons, createEmptyLesson()],
      } : chapter),
    }))
    setLessonIndex(currentChapter.lessons.length)
  }

  const deleteLesson = () => {
    if (currentChapter.lessons.length <= 1) {
      setStatus('每个章节至少保留一个知识点')
      return
    }
    setDirty(true)
    setCourse((old) => ({
      ...old,
      chapters: old.chapters.map((chapter, index) => index === chapterIndex ? {
        ...chapter,
        lessons: chapter.lessons.filter((_, lIndex) => lIndex !== lessonIndex),
      } : chapter),
    }))
    setLessonIndex(0)
  }

  const saveCourse = async (event) => {
    event.preventDefault()
    setStatus('正在保存课程内容...')
    try {
      const saved = await courseApi.save(course.id, course)
      setCourse(saved)
      setDirty(false)
      setStatus('已保存并发布，学生端刷新课程学习即可看到')
    } catch (error) {
      setStatus(`保存失败：${error.message}`)
    }
  }

  const uploadChapterHandout = async () => {
    if (!handoutFile) return
    if (!/\.(pdf|pptx)$/i.test(handoutFile.name) || handoutFile.size > 15 * 1024 * 1024) {
      setStatus('讲义仅支持 15 MB 以内的 PDF 或 PPTX 文件')
      return
    }
    setHandoutBusy(true)
    try {
      const result = await courseApi.uploadHandout(course.id, currentChapter.id, handoutFile)
      const previewName = result.filename.toLowerCase().endsWith('.pdf') ? result.filename : null
      setCourse((old) => ({ ...old, chapters: old.chapters.map((chapter, index) => index === chapterIndex ? { ...chapter, handout_name: result.filename, preview_name: previewName } : chapter) }))
      setHandoutFile(null)
      setPreviewFile(null)
      if (chapterHandoutInputRef.current) chapterHandoutInputRef.current.value = ''
      if (chapterPreviewInputRef.current) chapterPreviewInputRef.current.value = ''
      setStatus(previewName ? 'PDF 课件已上传，学生端可以直接预览。' : 'PPTX 已上传；要在网页里预览，请继续上传同一课件导出的 PDF。')
    } catch (error) {
      setStatus(`讲义上传失败：${error.message}；新增章节请先保存课程。`)
    } finally {
      setHandoutBusy(false)
    }
  }

  const removeChapterHandout = async () => {
    if (!window.confirm(`确定移除“${currentChapter.handout_name}”吗？`)) return
    setHandoutBusy(true)
    try {
      await courseApi.removeHandout(course.id, currentChapter.id)
      setCourse((old) => ({ ...old, chapters: old.chapters.map((chapter, index) => index === chapterIndex ? { ...chapter, handout_name: null, preview_name: null } : chapter) }))
      setPreviewFile(null)
      if (chapterPreviewInputRef.current) chapterPreviewInputRef.current.value = ''
      setStatus('本章讲义已移除。')
    } catch (error) {
      setStatus(`移除讲义失败：${error.message}`)
    } finally {
      setHandoutBusy(false)
    }
  }

  const uploadChapterPreview = async () => {
    if (!previewFile) return
    if (!previewFile.name.toLowerCase().endsWith('.pdf') || previewFile.size > 15 * 1024 * 1024) {
      setStatus('预览文件须为 15 MB 以内的 PDF')
      return
    }
    setHandoutBusy(true)
    try {
      const result = await courseApi.uploadHandoutPreview(course.id, currentChapter.id, previewFile)
      setCourse((old) => ({ ...old, chapters: old.chapters.map((chapter, index) => index === chapterIndex ? { ...chapter, preview_name: result.filename } : chapter) }))
      setPreviewFile(null)
      if (chapterPreviewInputRef.current) chapterPreviewInputRef.current.value = ''
      setStatus('预览 PDF 已发布，学生可在左侧直接翻页阅读。')
    } catch (error) {
      setStatus(`预览 PDF 上传失败：${error.message}`)
    } finally {
      setHandoutBusy(false)
    }
  }

  const removeChapterPreview = async () => {
    if (!window.confirm(`确定移除“${currentChapter.preview_name}”预览吗？原版课件仍会保留。`)) return
    setHandoutBusy(true)
    try {
      await courseApi.removeHandoutPreview(course.id, currentChapter.id)
      setCourse((old) => ({ ...old, chapters: old.chapters.map((chapter, index) => index === chapterIndex ? { ...chapter, preview_name: null } : chapter) }))
      setStatus('预览 PDF 已移除，原版课件仍可下载。')
    } catch (error) {
      setStatus(`移除预览失败：${error.message}`)
    } finally {
      setHandoutBusy(false)
    }
  }

  const stepsText = currentLesson.steps.map(([title, detail]) => `${title}|${detail}`).join('\n')
  const quizOptionsText = currentLesson.quiz_options.join('\n')

  return (
    <div className="page course-editor-page">
      <form className="panel course-editor" onSubmit={saveCourse}>
        <div className="panel-heading">
          <div><h3>课程讲义与知识点管理</h3><p>模块位置：学生端“课程学习”页面</p></div>
          <button className="login-submit compact" type="submit">保存并发布</button>
        </div>
        <div className="teacher-module-note course">
          <strong>这个模块负责什么？</strong>
          <p>这里维护上课要看的章节讲义和课件，学生端“课程学习”和“在线练习”左侧都会读取；每个知识点的小测与 Python 示例也在这里编辑。</p>
        </div>
        <label className="course-picker"><span>当前编辑课程</span><select value={courseId} onChange={(event) => {
          if (dirty && !window.confirm('当前有未保存的课程修改，确定切换课程吗？')) return
          setCourseId(event.target.value)
        }}>{(availableCourses.length ? availableCourses : [{ id: courseId, title: course.title }]).map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
        <div className="course-editor-top">
          <label><span>课程名称</span><input value={course.title} onChange={(event) => updateCourse({ title: event.target.value })} /></label>
          <label><span>课程说明</span><input value={course.description} onChange={(event) => updateCourse({ description: event.target.value })} /></label>
        </div>
        <div className="course-editor-layout">
          <aside className="course-tree-editor">
            <div className="tree-actions"><button type="button" onClick={addChapter}>新增章节</button><button type="button" onClick={deleteChapter}>删除章节</button></div>
            {course.chapters.map((chapter, cIndex) => (
              <div className={`tree-chapter ${chapterIndex === cIndex ? 'active' : ''}`} key={chapter.id}>
                <button type="button" onClick={() => { setChapterIndex(cIndex); setLessonIndex(0); setHandoutFile(null); setPreviewFile(null); if (chapterHandoutInputRef.current) chapterHandoutInputRef.current.value = ''; if (chapterPreviewInputRef.current) chapterPreviewInputRef.current.value = '' }}>{chapter.title}</button>
                {chapter.lessons.map((lesson, lIndex) => (
                  <button
                    type="button"
                    className={chapterIndex === cIndex && lessonIndex === lIndex ? 'selected' : ''}
                    key={lesson.id}
                    onClick={() => { setChapterIndex(cIndex); setLessonIndex(lIndex); setHandoutFile(null); setPreviewFile(null); if (chapterHandoutInputRef.current) chapterHandoutInputRef.current.value = ''; if (chapterPreviewInputRef.current) chapterPreviewInputRef.current.value = '' }}
                  >
                    {lesson.title}
                  </button>
                ))}
              </div>
            ))}
          </aside>
          <section className="course-lesson-editor">
            <div className="lesson-editor-actions">
              <button type="button" onClick={addLesson}>新增知识点</button>
              <button type="button" onClick={deleteLesson}>删除知识点</button>
            </div>
            <div className="experiment-form-grid">
              <div className="teacher-form-section wide">
                <h4>一、课程结构</h4>
                <p>学生端对应：课程学习左侧章节目录和知识点列表。</p>
              </div>
              <label className="wide"><span>章节标题</span><input value={currentChapter.title} onChange={(event) => updateChapter({ title: event.target.value })} /></label>
              <div className="teacher-form-section wide">
                <h4>本章课件与网页预览</h4>
                <p>PDF 上传后可直接在学生端预览。若原版是 PPTX，请先上传 PPTX，再从 PowerPoint 导出同一课件的 PDF 上传到下方预览栏。每个文件最多 15 MB。</p>
                {currentChapter.handout_name && <p>原版课件：{currentChapter.handout_name}</p>}
                {currentChapter.preview_name && <p>网页预览：{currentChapter.preview_name}</p>}
                <input ref={chapterHandoutInputRef} type="file" accept=".pdf,.pptx,application/pdf,application/vnd.openxmlformats-officedocument.presentationml.presentation" onChange={(event) => setHandoutFile(event.target.files?.[0] || null)} />
                <div className="chapter-handout-actions"><button type="button" disabled={!handoutFile || handoutBusy} onClick={uploadChapterHandout}>{handoutBusy ? '处理中...' : '上传或替换原版课件'}</button>{currentChapter.handout_name && <button type="button" disabled={handoutBusy} onClick={removeChapterHandout}>移除课件</button>}</div>
                {currentChapter.handout_name?.toLowerCase().endsWith('.pptx') && <div className="chapter-preview-upload"><strong>配套预览 PDF</strong><input ref={chapterPreviewInputRef} type="file" accept=".pdf,application/pdf" onChange={(event) => setPreviewFile(event.target.files?.[0] || null)} /><div className="chapter-handout-actions"><button type="button" disabled={!previewFile || handoutBusy} onClick={uploadChapterPreview}>上传或替换预览 PDF</button>{currentChapter.preview_name && <button type="button" disabled={handoutBusy} onClick={removeChapterPreview}>移除预览 PDF</button>}</div></div>}
              </div>
              <label><span>知识点标题</span><input value={currentLesson.title} onChange={(event) => updateLesson({ title: event.target.value })} /></label>
              <label><span>预计学习分钟</span><input type="number" value={currentLesson.minutes} onChange={(event) => updateLesson({ minutes: Number(event.target.value) || 10 })} /></label>

              <div className="teacher-form-section wide">
                <h4>二、讲义内容</h4>
                <p>学生端对应：知识讲解页的导入说明、核心概念、代码示例和学习步骤。</p>
              </div>
              <label className="wide"><span>导入说明</span><textarea value={currentLesson.lead} onChange={(event) => updateLesson({ lead: event.target.value })} /></label>
              <label className="wide"><span>核心概念 / 讲义正文</span><textarea value={currentLesson.concept} onChange={(event) => updateLesson({ concept: event.target.value })} /></label>
              <label><span>示例标题</span><input value={currentLesson.syntax_title} onChange={(event) => updateLesson({ syntax_title: event.target.value })} /></label>
              <label><span>是否包含编程练习</span><select value={currentLesson.is_coding ? 'yes' : 'no'} onChange={(event) => updateLesson({ is_coding: event.target.value === 'yes' })}><option value="yes">包含</option><option value="no">不包含</option></select></label>
              <label className="wide"><span>讲义代码示例</span><textarea value={currentLesson.code} onChange={(event) => updateLesson({ code: event.target.value })} /></label>
              <label className="wide"><span>学习步骤（每行：标题|说明）</span><textarea value={stepsText} onChange={(event) => updateLesson({ steps: event.target.value.split('\n').map((line) => line.split('|').map((part) => part.trim())).filter((parts) => parts[0]).map(([title, detail = '']) => [title, detail]) })} /></label>

              <div className="teacher-form-section wide">
                <h4>三、课程内 Python 练习</h4>
                <p>学生端对应：知识点内“Python 练习”标签页，不是在线练习的大实验。</p>
              </div>
              <label className="wide"><span>Python 练习初始代码</span><textarea value={currentLesson.practice_code} onChange={(event) => updateLesson({ practice_code: event.target.value })} /></label>
              <label className="wide"><span>标准输入示例</span><textarea value={currentLesson.stdin} onChange={(event) => updateLesson({ stdin: event.target.value })} /></label>

              <div className="teacher-form-section wide">
                <h4>四、完成本知识点的小测题</h4>
                <p>学生端对应：知识点最后的“本节小测”。学生答对后，才会标记完成这一小节。</p>
              </div>
              <label className="wide"><span>本节小测问题</span><input value={currentLesson.quiz_question} onChange={(event) => updateLesson({ quiz_question: event.target.value })} /></label>
              <label className="wide"><span>小测选项（每行一个）</span><textarea value={quizOptionsText} onChange={(event) => updateLesson({ quiz_options: event.target.value.split('\n').map((item) => item.trim()).filter(Boolean) })} /></label>
              <label className="wide"><span>正确答案（必须和某个选项完全一致）</span><input value={currentLesson.quiz_answer} onChange={(event) => updateLesson({ quiz_answer: event.target.value })} /></label>
            </div>
          </section>
        </div>
        {status && <div className={`editor-status ${status.startsWith('已保存') || status.startsWith('已读取') || status.includes('已发布') || status.includes('已上传') || status.includes('已移除') ? 'success' : ''}`}>{status}</div>}
      </form>
    </div>
  )
}

function UserManagementPage() {
  const [accounts, setAccounts] = useState([])
  const [form, setForm] = useState({
    account_id: '',
    password: '',
    role: 'student',
    name: '',
    phone: '',
    detail: '',
  })
  const [status, setStatus] = useState('正在读取账号列表...')
  const [saving, setSaving] = useState(false)

  const loadUsers = async () => {
    try {
      const result = await authApi.users()
      setAccounts(result)
      setStatus(`当前共有 ${result.length} 个账号`)
    } catch (error) {
      setStatus(`账号列表读取失败：${error.message}`)
    }
  }

  useEffect(() => {
    loadUsers()
  }, [])

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setStatus('正在创建账号...')
    try {
      await authApi.register(form)
      setForm((old) => ({ ...old, account_id: '', password: '', name: '', phone: '', detail: '' }))
      await loadUsers()
      setStatus('账号创建成功，已加入平台用户列表。')
    } catch (error) {
      setStatus(`创建失败：${error.message}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page user-management-page">
      <section className="panel management-panel admin-user-panel">
        <div className="panel-heading">
          <div><h3>创建平台账号</h3><p>学生、教师和管理员使用此处创建的账号与密码登录。</p></div>
        </div>
        <div className="teacher-module-note">
          <strong>账号会进入哪个模块？</strong>
          <p>学生登录后进入课程学习、在线练习和 AI 助教；教师进入课程与实验内容管理；管理员可继续管理账号和系统配置。账号使用账号和密码登录，无需绑定手机号。</p>
        </div>
        <form className="experiment-form-grid admin-user-form" onSubmit={submit}>
          <label><span>账号</span><input value={form.account_id} required onChange={(event) => setForm({ ...form, account_id: event.target.value })} placeholder="如：20250002 或 T2025002" /></label>
          <label><span>初始密码</span><input type="password" value={form.password} required minLength="8" onChange={(event) => setForm({ ...form, password: event.target.value })} placeholder="至少 8 位" /></label>
          <label><span>身份</span><select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}><option value="student">学生</option><option value="teacher">教师</option><option value="admin">管理员</option></select></label>
          <label><span>姓名</span><input value={form.name} required onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="如：王同学" /></label>
          <label><span>联系电话（选填）</span><input value={form.phone} inputMode="tel" maxLength="13" onChange={(event) => setForm({ ...form, phone: event.target.value })} placeholder="可留空" /></label>
          <label className="wide"><span>所属信息</span><input value={form.detail} onChange={(event) => setForm({ ...form, detail: event.target.value })} placeholder="如：计算机科学 2025级 / Python 程序设计课程" /></label>
          <button className="login-submit compact" type="submit" disabled={saving}>{saving ? '正在创建...' : '创建账号'}</button>
        </form>
        {status && <div className={`editor-status ${status.includes('成功') || status.startsWith('当前共有') ? 'success' : ''}`}>{status}</div>}
      </section>
      <section className="panel management-panel admin-user-list">
        <div className="panel-heading"><div><h3>已有账号</h3><p>这里只展示账号基本信息，不显示密码。</p></div><button className="text-action" type="button" onClick={loadUsers}>刷新列表</button></div>
        <div className="account-list-head"><span>账号</span><span>姓名</span><span>身份</span><span>联系电话</span><span>所属信息</span><span>状态</span></div>
        {accounts.map((account) => (
          <div className="account-list-row" key={account.account_id}>
            <strong>{account.account_id}</strong><span>{account.name}</span><span>{roleConfig[account.role]?.label || account.role}</span><span>{account.phone || '—'}</span><span>{account.detail || '—'}</span><span className={account.is_active ? 'active' : 'inactive'}>{account.is_active ? '启用' : '停用'}</span>
          </div>
        ))}
      </section>
    </div>
  )
}

function ManagementPage({ role, page }) {
  const [adminOverview, setAdminOverview] = useState({
    loading: false,
    refreshing: false,
    accounts: [],
    courses: [],
    error: '',
  })

  const loadAdminOverview = useCallback(async (silent = false) => {
    if (role !== 'admin') return
    setAdminOverview((old) => ({
      ...old,
      loading: !silent,
      refreshing: silent,
      error: '',
    }))
    try {
      const [accounts, courses] = await Promise.all([authApi.users(), courseApi.list()])
      setAdminOverview({
        loading: false,
        refreshing: false,
        accounts,
        courses,
        error: '',
      })
    } catch (error) {
      setAdminOverview((old) => ({
        ...old,
        loading: false,
        refreshing: false,
        error: error.message,
      }))
    }
  }, [role])

  useEffect(() => {
    if (role !== 'admin' || page !== 'admin-home') return

    let active = true
    const refresh = async (silent = false) => {
      if (!active) return
      await loadAdminOverview(silent)
    }

    refresh(false)
    const timer = window.setInterval(() => refresh(true), 30000)

    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [loadAdminOverview, role, page])

  const refreshAdminOverview = async () => {
    await loadAdminOverview(true)
  }

  const formatCount = (value) => new Intl.NumberFormat('zh-CN').format(value)
  const accounts = adminOverview.accounts
  const activeAccounts = accounts.filter((account) => account.is_active)
  const countByRole = (targetRole) => accounts.filter((account) => account.role === targetRole).length
  const adminStats = adminOverview.loading
    ? [
      [Users, '读取中', '注册用户'],
      [GraduationCap, '读取中', '学生账号'],
      [BookOpen, '读取中', '教师账号'],
      [Shield, '读取中', '管理员'],
    ]
    : [
      [Users, formatCount(accounts.length), '注册用户'],
      [GraduationCap, formatCount(countByRole('student')), '学生账号'],
      [BookOpen, formatCount(countByRole('teacher')), '教师账号'],
      [Shield, formatCount(countByRole('admin')), '管理员'],
    ]
  const adminItems = adminOverview.loading
    ? ['正在读取后端账号与课程数据...']
    : adminOverview.error
      ? [`真实数据读取失败：${adminOverview.error}`, '请确认后端服务正常，并使用管理员账号登录']
      : [
        `当前启用账号 ${formatCount(activeAccounts.length)} 个`,
        `当前课程 ${formatCount(adminOverview.courses.length)} 门`,
        '统计来源：后端账号接口与课程接口',
      ]

  const teacherPages = {
    'teacher-home': {
      title: '今日教学概览',
      panelCaption: '教师首页统计暂未接入真实学习记录',
      stats: [
        [Users, '待接入', '课程学生'],
        [BookOpen, '待接入', '进行中课程'],
        [ClipboardList, '待接入', '待批改作业'],
        [Bot, '待接入', '本周 AI 对话'],
      ],
      items: ['课程管理：已支持维护章节、知识点和小测', '实验管理：已支持维护在线练习的实验指导', '学生学习记录：后续接入真实学习行为数据'],
    },
    'course-manage': { title: '课程内容管理', panelCaption: '教师端可维护学生课程学习内容', items: ['数据结构（Python）'] },
    'experiment-manage': { title: '实验内容管理', panelCaption: '教师端可维护学生在线练习内容', items: ['编辑实验题目', '上传实验指导', '维护默认代码'] },
    'assignment-manage': { title: '作业与提交', panelCaption: '作业模块当前为预留入口', items: ['循环结构编程作业', '猜数字游戏实验', '本周综合练习'] },
    'student-records': { title: '学生交互记录', panelCaption: '学生行为记录后续从数据库汇总展示', items: ['AI 对话记录按账号保存', '代码运行记录进入后端行为日志', '知识点完成记录用于后续分析'] },
  }
  const adminPages = {
    'admin-home': {
      title: '平台运行概览',
      panelCaption: adminOverview.error ? '真实数据读取异常' : '当前统计来自后端真实数据',
      stats: adminStats,
      items: adminItems,
    },
    'user-manage': { title: '用户账号管理', panelCaption: '管理员可创建学生、教师和管理员账号', items: ['批量导入学生账号', '创建教师账号', '停用或恢复账号'] },
    'role-manage': { title: '角色与权限', panelCaption: '不同身份进入不同功能模块', items: ['学生：课程、练习、AI 助教', '教师：课程、作业、学生记录', '管理员：用户、角色、系统配置'] },
    'system-settings': { title: '系统基础设置', panelCaption: '上线前需要配置安全、备份和模型服务参数', items: ['学期与课程参数', 'AI 模型服务配置', '数据保留与备份策略'] },
  }
  const data = (role === 'teacher' ? teacherPages : adminPages)[page]
  const isAdminHome = role === 'admin' && page === 'admin-home'
  return (
    <div className="page management-page">
      {data.stats && (
        <section className="stats-row">
          {data.stats.map(([Icon, value, label], index) => (
            <StatCard key={label} icon={Icon} color={['blue', 'green', 'orange', 'purple'][index]} value={value} label={label} hint={isAdminHome ? (adminOverview.refreshing ? '正在刷新' : '后端统计') : '待接入'} />
          ))}
        </section>
      )}
      <section className="panel management-panel">
        <div className="panel-heading">
          <div><h3>{data.title}</h3><p>{data.panelCaption}</p></div>
          {isAdminHome && (
            <button className="text-action" type="button" onClick={refreshAdminOverview} disabled={adminOverview.loading || adminOverview.refreshing}>
              {adminOverview.loading || adminOverview.refreshing ? '刷新中...' : '刷新真实数据'}
            </button>
          )}
        </div>
        {data.items.map((item, index) => (
          <div className="management-row" key={item}>
            <span>{index + 1}</span><strong>{item}</strong><ChevronRight size={17} />
          </div>
        ))}
      </section>
    </div>
  )
}

function AiAssistant({ accountId, context, onConfigure }) {
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const [keyBound, setKeyBound] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const contextKey = context?.attemptId || `free:${context?.courseId || ''}`
  const contextRef = useRef(contextKey)
  contextRef.current = contextKey
  const [position, setPosition] = useState(() => {
    try {
      const saved = localStorage.getItem(AI_ASSISTANT_POSITION_KEY)
      if (!saved) return null
      const parsed = JSON.parse(saved)
      if (typeof parsed.xRatio !== 'number' || typeof parsed.yRatio !== 'number') return null
      return parsed
    } catch {
      return null
    }
  })
  const floatingRef = useRef(null)
  const dragRef = useRef(null)
  const suppressClickRef = useRef(false)
  const [viewport, setViewport] = useState(() => ({ width: window.innerWidth, height: window.innerHeight }))
  const buttonSize = 52
  const inset = 16
  const clampPosition = (x, y, width = window.innerWidth, height = window.innerHeight) => ({
    x: Math.max(8, Math.min(x, width - buttonSize - 8)),
    y: Math.max(8, Math.min(y, height - buttonSize - 8)),
  })
  const toRelativePosition = ({ x, y }) => ({
    xRatio: Math.max(0, Math.min(1, (x - 8) / Math.max(1, window.innerWidth - buttonSize - 16))),
    yRatio: Math.max(0, Math.min(1, (y - 8) / Math.max(1, window.innerHeight - buttonSize - 16))),
  })
  const buttonPosition = clampPosition(
    position ? 8 + position.xRatio * (viewport.width - buttonSize - 16) : viewport.width - buttonSize - inset,
    position ? 8 + position.yRatio * (viewport.height - buttonSize - 16) : viewport.height - buttonSize - inset,
    viewport.width,
    viewport.height,
  )
  const panelWidth = Math.min(340, viewport.width - 16)
  const panelHeight = Math.min(470, viewport.height - 80)
  const panelPosition = {
    left: Math.max(8, Math.min(buttonPosition.x + buttonSize - panelWidth, viewport.width - panelWidth - 8)),
    top: Math.max(8, Math.min(buttonPosition.y - panelHeight - 10, viewport.height - panelHeight - 8)),
    width: panelWidth,
    height: panelHeight,
  }
  const [messages, setMessages] = useState([
    { role: 'ai', text: '你好，你可以自由提问。' },
  ])

  useEffect(() => {
    let active = true
    const storageKey = `ai-conversation:${accountId}:${contextKey}`
    setHistoryLoading(true)
    setConversationId(null); setMessages([{ role: 'ai', text: '你好，你可以自由提问。' }]); setSending(false); setMessage('')
    const stored = localStorage.getItem(storageKey)
    const request = context?.attemptId ? classroomApi.chat(context.attemptId) : stored ? aiApi.messages(accountId, stored).then(items => ({ conversation_id: stored, messages: items })) : Promise.resolve(null)
    request.then(value => { if (active && value?.conversation_id) { setConversationId(value.conversation_id); setMessages(value.messages.map(item => ({ role: item.role === 'assistant' ? 'ai' : 'user', text: item.content }))) } }).catch(() => { if (active) localStorage.removeItem(storageKey) }).finally(() => { if (active) setHistoryLoading(false) })
    return () => { active = false }
  }, [accountId, contextKey])
  useEffect(() => { if (open) qwenApi.status().then(value => setKeyBound(value.bound)).catch(() => setKeyBound(false)); setAiPanelVisible(open) }, [open])

  useEffect(() => {
    const move = (event) => {
      if (!dragRef.current || event.pointerId !== dragRef.current.pointerId) return
      if (Math.hypot(event.clientX - dragRef.current.startX, event.clientY - dragRef.current.startY) > 4) {
        dragRef.current.moved = true
      }
      if (!dragRef.current.moved) return
      const nextPosition = clampPosition(
        event.clientX - dragRef.current.offsetX,
        event.clientY - dragRef.current.offsetY,
      )
      dragRef.current.nextPosition = toRelativePosition(nextPosition)
      setPosition(dragRef.current.nextPosition)
    }
    const stop = (event) => {
      if (!dragRef.current || event.pointerId !== dragRef.current.pointerId) return
      if (dragRef.current?.nextPosition) {
        localStorage.setItem(AI_ASSISTANT_POSITION_KEY, JSON.stringify(dragRef.current.nextPosition))
      }
      if (dragRef.current.moved) {
        suppressClickRef.current = true
        window.setTimeout(() => { suppressClickRef.current = false }, 0)
      }
      dragRef.current = null
    }
    const resize = () => {
      setViewport({ width: window.innerWidth, height: window.innerHeight })
    }

    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', stop)
    window.addEventListener('pointercancel', stop)
    window.addEventListener('resize', resize)
    return () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', stop)
      window.removeEventListener('pointercancel', stop)
      window.removeEventListener('resize', resize)
    }
  }, [])

  const startDrag = (event) => {
    if (!floatingRef.current || event.button !== 0) return
    const rect = floatingRef.current.getBoundingClientRect()
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
      moved: false,
    }
  }

  const send = async () => {
    const userMessage = message.trim()
    if (!userMessage || sending || historyLoading || !keyBound) return

    const sentContext = contextKey
    setMessages((old) => [...old, { role: 'user', text: userMessage }])
    setMessage('')
    setSending(true)

    try {
      const result = await aiApi.chat({
        accountId,
        conversationId,
        message: userMessage,
        attemptId: context?.attemptId || null,
        courseId: context?.courseId || null,
      })
      localStorage.setItem(`ai-conversation:${accountId}:${sentContext}`, result.conversation_id)
      if (contextRef.current !== sentContext) return
      setConversationId(result.conversation_id)
      setMessages((old) => [
        ...old,
        {
          role: 'ai',
          text: result.response,
          createdAt: result.created_at,
        },
      ])
    } catch (error) {
      if (contextRef.current !== sentContext) return
      setMessages((old) => [
        ...old,
        {
          role: 'ai',
          text: `暂时无法连接 AI 服务：${error.message}`,
        },
      ])
    } finally {
      if (contextRef.current === sentContext) setSending(false)
    }
  }

  return (
    <div
      ref={floatingRef}
      className={`ai-floating ${open ? 'open' : ''}`}
      style={position ? { left: buttonPosition.x, top: buttonPosition.y, right: 'auto', bottom: 'auto' } : undefined}
    >
      {open && (
        <div className="ai-panel" style={position ? { ...panelPosition, right: 'auto', bottom: 'auto' } : undefined}>
          <div className="ai-header">
            <div className="ai-avatar"><Bot size={19} /></div>
            <div>
              <strong>知序 AI 助教</strong>
              <span><i /> 账号 {accountId}</span>
            </div>
            <button aria-label="关闭 AI 助手" onMouseDown={(event) => event.stopPropagation()} onClick={() => setOpen(false)}><X size={18} /></button>
          </div>
          <div className="ai-context"><span>{keyBound ? '个人千问 API' : '请先绑定个人百炼 API Key'}</span><button type="button" onClick={() => { setOpen(false); onConfigure() }}>{keyBound ? '配置' : '去绑定'}</button></div>
          <div className="ai-messages">
            {messages.map((item, index) => <div key={index} className={`message ${item.role}`}>{item.text}{item.role === 'ai' && index > 0 && <button type="button" className="ai-copy" onClick={async () => { try { await navigator.clipboard.writeText(item.text); trackLearning('ai.copy', { count: item.text.length }) } catch { /* Clipboard permission is controlled by the browser. */ } }}>复制</button>}</div>)}
            {sending && <div className="message ai">正在思考...</div>}
          </div>
          <div className="ai-input">
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="输入你的问题..."
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  send()
                }
              }}
            />
            <button aria-label="发送" onClick={send} disabled={sending || historyLoading || !keyBound}><Send size={16} /></button>
          </div>
        </div>
      )}
      <button
        className={`ai-trigger ${open ? 'open' : ''}`}
        title={open ? '收起 AI 助教' : '打开 AI 助教'}
        aria-label={open ? '收起 AI 助教' : '打开 AI 助教'}
        aria-expanded={open}
        onPointerDown={startDrag}
        onClick={() => {
          if (!suppressClickRef.current) setOpen(!open)
        }}
      >
        {open ? <X size={22} /> : <MessageCircle size={23} />}
      </button>
    </div>
  )
}

const toAppUser = (remoteUser) => ({
  accountId: remoteUser.account_id,
  role: remoteUser.role,
  name: remoteUser.name,
  phone: remoteUser.phone,
  detail: remoteUser.detail,
})

export default function App() {
  const [edition] = useState(getPlatformEdition)
  const [user, setUser] = useState(null)
  const [page, setPage] = useState('home')
  const [selectedCourseId, setSelectedCourseId] = useState('data-structures-python')
  const [collapsed, setCollapsed] = useState(false)
  const [authReady, setAuthReady] = useState(false)
  const [practiceContext, setPracticeContext] = useState({})
  useEffect(() => startLearningTracker(user), [user?.accountId, user?.role])
  useEffect(() => { updateLearningContext({ page, courseId: page === 'practice' ? practiceContext.courseId : page === 'course' ? selectedCourseId : null, attemptId: page === 'practice' ? practiceContext.attemptId : null }) }, [page, selectedCourseId, practiceContext, user?.accountId])

  const login = useCallback((nextUser, accessToken) => {
    saveEditionSession(nextUser, accessToken, edition)
    setUser(nextUser)
    setPracticeContext({})
    setSelectedCourseId('data-structures-python')
    setPage(roleConfig[nextUser.role].defaultPage)
  }, [edition])

  const openCourse = useCallback((courseId) => {
    setSelectedCourseId(courseId)
    setPage('course')
  }, [])

  useEffect(() => {
    window.history.replaceState(null, '', editionUrl(window.location))
    document.title = edition === 'student' ? '知序教学辅助平台' : `知序 · ${PLATFORM_EDITIONS[edition].label}`
    let active = true
    const initialize = async () => {
      const accessToken = readEditionToken(edition)
      if (accessToken) {
        try {
          const remoteUser = await authApi.me()
          if (active) login(toAppUser(remoteUser), accessToken)
          return
        } catch (_) {
          if (active && readEditionToken(edition) === accessToken) clearEditionSession(edition)
        }
      }
    }

    initialize().finally(() => {
      if (active) setAuthReady(true)
    })

    return () => { active = false }
  }, [edition, login])

  useEffect(() => {
    if (!authReady) return
    const token = readEditionToken(edition)
    const syncSession = event => {
      if ((event.key === null || event.key === editionSessionKey(edition)) && readEditionToken(edition) !== token) {
        window.location.reload()
      }
    }
    window.addEventListener('storage', syncSession)
    return () => window.removeEventListener('storage', syncSession)
  }, [authReady, edition, user?.accountId])

  const logout = async () => {
    const token = readEditionToken(edition)
    try {
      await endLearningTracker()
      await authApi.logout({ headers: { Authorization: `Bearer ${token}`, 'X-Platform-Edition': edition } })
    } catch (_) {
      // The local session must still be cleared if the server is unavailable.
    } finally {
      if (readEditionToken(edition) === token) clearEditionSession(edition)
      setUser(null)
      setPage('home')
    }
  }

  const pageContent = useMemo(() => {
    if (!user) return null
    if (user.role === 'teacher' && page === 'course-manage') {
      return <CourseEditorPage user={user} />
    }
    if (user.role === 'teacher' && page === 'experiment-manage') {
      return <ExperimentEditorPage user={user} />
    }
    if (user.role === 'teacher' && page === 'assignment-manage') return <AssignmentManager />
    if (user.role === 'teacher' && page === 'student-records') return <StudentRecords />
    if (user.role === 'admin' && page === 'platform-records') return <StudentRecords admin />
    if (user.role === 'admin' && page === 'user-manage') {
      return <UserManagementPage />
    }
    if (page === 'profile') {
      return <ProfilePage user={user} setPage={setPage} />
    }
    if (user.role !== 'student') {
      return <ManagementPage role={user.role} page={page} />
    }
    if (page === 'course') return <CoursePage initialCourseId={selectedCourseId} onCourseChange={setSelectedCourseId} user={user} />
    if (page === 'practice') return <PracticePage key={user.accountId} user={user} onContextChange={setPracticeContext} />
    return <HomePage setPage={setPage} onOpenCourse={openCourse} />
  }, [page, user, selectedCourseId, openCourse])

  if (!authReady) {
    return <div className="auth-loading"><Brand edition={edition} /><p>{edition === 'student' ? '正在加载...' : `正在进入${PLATFORM_EDITIONS[edition].label}...`}</p></div>
  }

  if (!user) {
    return <LoginPage onLogin={login} edition={edition} />
  }

  return (
    <div className={`app ${collapsed ? 'sidebar-collapsed' : ''} ${page === 'practice' ? 'practice-active' : ''} role-${user.role}`}>
      <Sidebar
        page={page}
        setPage={setPage}
        collapsed={collapsed}
        setCollapsed={setCollapsed}
        user={user}
        onLogout={logout}
      />
      <main>{page !== 'practice' && <Header page={page} user={user} onLogout={logout} />}{pageContent}</main>
      {user.role === 'student' && <AiAssistant key={user.accountId} accountId={user.accountId} context={page === 'practice' ? practiceContext : { courseId: page === 'course' ? selectedCourseId : null }} onConfigure={() => setPage('profile')} />}
    </div>
  )
}
