"""Classroom assignments and immutable, account-scoped learning events."""
import csv
import io
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from .database import get_connection, utc_now


def init_classroom():
    with get_connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS course_staff (
            course_id TEXT NOT NULL REFERENCES courses(id),
            account_id TEXT NOT NULL REFERENCES users(account_id),
            PRIMARY KEY(course_id, account_id));
        CREATE TABLE IF NOT EXISTS course_students (
            course_id TEXT NOT NULL REFERENCES courses(id),
            account_id TEXT NOT NULL REFERENCES users(account_id),
            PRIMARY KEY(course_id, account_id));
        CREATE TABLE IF NOT EXISTS classroom_migrations (name TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS assignments (
            id TEXT PRIMARY KEY, course_id TEXT NOT NULL REFERENCES courses(id),
            chapter_id TEXT, title TEXT NOT NULL, instructions TEXT NOT NULL,
            initial_code TEXT NOT NULL, stdin TEXT NOT NULL DEFAULT '',
            deadline_at TEXT, is_published INTEGER NOT NULL DEFAULT 1,
            version INTEGER NOT NULL, teacher_id TEXT NOT NULL REFERENCES users(account_id),
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS assignment_versions (
            assignment_id TEXT NOT NULL REFERENCES assignments(id), version INTEGER NOT NULL,
            snapshot TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY(assignment_id, version));
        CREATE TABLE IF NOT EXISTS task_attempts (
            id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES users(account_id),
            assignment_id TEXT NOT NULL REFERENCES assignments(id), task_version INTEGER NOT NULL,
            started_at TEXT NOT NULL, first_submitted_at TEXT,
            UNIQUE(account_id, assignment_id));
        CREATE TABLE IF NOT EXISTS task_submissions (
            id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES task_attempts(id),
            request_id TEXT NOT NULL UNIQUE, code TEXT NOT NULL, stdin TEXT NOT NULL,
            created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS code_snapshots (
            id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES task_attempts(id),
            reason TEXT NOT NULL, cell_id TEXT, code TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS learning_events (
            event_id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES users(account_id),
            course_id TEXT, assignment_id TEXT, attempt_id TEXT, session_id TEXT NOT NULL,
            event_type TEXT NOT NULL, occurred_at TEXT NOT NULL, received_at TEXT NOT NULL,
            metadata TEXT NOT NULL, quality_flags TEXT NOT NULL DEFAULT '[]');
        CREATE INDEX IF NOT EXISTS idx_learning_account_time ON learning_events(account_id, occurred_at);
        CREATE INDEX IF NOT EXISTS idx_learning_course_time ON learning_events(course_id, received_at);
        CREATE INDEX IF NOT EXISTS idx_learning_attempt ON learning_events(attempt_id, received_at);
        CREATE TABLE IF NOT EXISTS learning_events_clean (
            event_id TEXT PRIMARY KEY REFERENCES learning_events(event_id),
            occurred_at_utc TEXT NOT NULL, quality_flags TEXT NOT NULL, processed_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS conversation_tasks (
            conversation_id TEXT PRIMARY KEY REFERENCES conversations(id),
            account_id TEXT NOT NULL REFERENCES users(account_id), attempt_id TEXT,
            course_id TEXT, UNIQUE(account_id, attempt_id));
        CREATE TABLE IF NOT EXISTS personal_ai_keys (
            account_id TEXT PRIMARY KEY REFERENCES users(account_id), encrypted_key TEXT NOT NULL,
            model TEXT NOT NULL, updated_at TEXT NOT NULL);
        """)
        # One-time association of the existing demo classroom; never re-enrol on restart.
        if not db.execute("SELECT 1 FROM classroom_migrations WHERE name='existing-classroom-v1'").fetchone():
            course = db.execute("SELECT id FROM courses WHERE id='data-structures-python'").fetchone()
            teacher = db.execute("SELECT account_id FROM users WHERE account_id='T2025001' AND role='teacher'").fetchone()
            if course and teacher:
                db.execute("INSERT OR IGNORE INTO course_staff VALUES (?,?)", (course[0], teacher[0]))
                db.execute("INSERT OR IGNORE INTO course_students SELECT ?,account_id FROM users WHERE role='student'", (course[0],))
                for row in db.execute("SELECT * FROM experiments WHERE teacher_id=?", (teacher[0],)).fetchall():
                    now = utc_now()
                    instructions = row['objective'] + '\n' + '\n'.join(json.loads(row['requirements']))
                    task = dict(id=row['id'], course_id=course[0], chapter_id=None, title=row['title'],
                                instructions=instructions, initial_code='', stdin='', deadline_at=None,
                                is_published=True, version=1, teacher_id=teacher[0], created_at=now, updated_at=now)
                    db.execute("INSERT OR IGNORE INTO assignments VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               tuple(task[key] for key in ('id','course_id','chapter_id','title','instructions','initial_code','stdin','deadline_at','is_published','version','teacher_id','created_at','updated_at')))
                    db.execute("INSERT OR IGNORE INTO assignment_versions VALUES (?,?,?,?)", (task['id'], 1, json.dumps(task, ensure_ascii=False), now))
            db.execute("INSERT INTO classroom_migrations VALUES ('existing-classroom-v1')")


def course_ids(user):
    with get_connection() as db:
        if user['role'] == 'admin':
            return [row[0] for row in db.execute('SELECT id FROM courses')]
        table = 'course_staff' if user['role'] == 'teacher' else 'course_students'
        return [row[0] for row in db.execute(f'SELECT course_id FROM {table} WHERE account_id=?', (user['account_id'],))]


def require_course(user, course_id, manage=False):
    if manage and user['role'] == 'student':
        raise HTTPException(403, '学生不能维护课堂习题')
    if course_id not in course_ids(user):
        raise HTTPException(403, '当前账号未被分配到这门课程')


def get_attempt(user, attempt_id):
    with get_connection() as db:
        row = db.execute('SELECT a.*,t.course_id,t.deadline_at,t.is_published,t.title task_title '
                         'FROM task_attempts a JOIN assignments t ON t.id=a.assignment_id WHERE a.id=?', (attempt_id,)).fetchone()
        if not row:
            raise HTTPException(404, '做题记录不存在')
        result = dict(row)
        if user['role'] == 'student' and result['account_id'] != user['account_id']:
            raise HTTPException(403, '只能访问自己的做题记录')
        require_course(user, result['course_id'])
        version = db.execute('SELECT snapshot FROM assignment_versions WHERE assignment_id=? AND version=?',
                             (result['assignment_id'], result['task_version'])).fetchone()
        result['task'] = json.loads(version[0])
        result['task']['deadline_at'] = result['deadline_at']
        result['task']['is_published'] = bool(result['is_published'])
        return result


def record_event(user, event_type, metadata=None, attempt_id=None, course_id=None, event_id=None, occurred_at=None, session_id='server'):
    assignment_id = None
    if attempt_id:
        attempt = get_attempt(user, attempt_id)
        assignment_id, course_id = attempt['assignment_id'], attempt['course_id']
    elif course_id:
        require_course(user, course_id)
    now = datetime.now(timezone.utc)
    original = occurred_at or now.isoformat()
    parsed = datetime.fromisoformat(original.replace('Z', '+00:00'))
    flags = []
    if parsed.tzinfo is None:
        flags.append('timezone_missing')
        parsed = parsed.replace(tzinfo=timezone.utc)
    if abs((parsed - now).total_seconds()) > 300:
        flags.append('clock_skew_or_delayed_delivery')
    with get_connection() as db:
        existing = db.execute('SELECT account_id FROM learning_events WHERE event_id=?', (event_id,)).fetchone() if event_id else None
        if existing and existing[0] != user['account_id']:
            raise HTTPException(409, '事件编号冲突')
        cursor = db.execute('INSERT OR IGNORE INTO learning_events VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                            (event_id or str(uuid4()), user['account_id'], course_id, assignment_id, attempt_id,
                             session_id, event_type, original, now.isoformat(), json.dumps(metadata or {}, ensure_ascii=False), json.dumps(flags)))
        return cursor.rowcount


def save_code_snapshot(user, attempt_id, code, reason, cell_id=None):
    get_attempt(user, attempt_id)
    snapshot_id = str(uuid4())
    with get_connection() as db:
        db.execute('INSERT INTO code_snapshots VALUES (?,?,?,?,?,?)', (snapshot_id, attempt_id, reason, cell_id, code, utc_now()))
    return snapshot_id


def union_duration(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    return round(sum((end - start).total_seconds() * 1000 for start, end in merged))


def activity_totals(rows):
    visible, ai = [], []
    for row in rows:
        if row['event_type'] != 'activity.interval' or json.loads(row['quality_flags']):
            continue
        data = json.loads(row['metadata'])
        end = datetime.fromisoformat(row['occurred_at'].replace('Z', '+00:00')).astimezone(timezone.utc)
        for key, target in [('visible_ms', visible), ('ai_visible_ms', ai)]:
            value = max(0, min(float(data.get(key, 0)), 90000))
            if value:
                target.append((end - timedelta(milliseconds=value), end))
    return {'learning_ms': union_duration(visible), 'ai_panel_ms': union_duration(ai)}


def clean_events():
    count = 0
    with get_connection() as db:
        for row in db.execute('SELECT * FROM learning_events').fetchall():
            flags = json.loads(row['quality_flags'])
            if not row['course_id']:
                flags.append('course_missing')
            if not row['attempt_id'] and row['event_type'].startswith(('run.', 'ai.')):
                flags.append('task_attempt_missing')
            stamp = datetime.fromisoformat(row['occurred_at'].replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            db.execute('INSERT INTO learning_events_clean VALUES (?,?,?,?) ON CONFLICT(event_id) DO UPDATE SET '
                       'occurred_at_utc=excluded.occurred_at_utc,quality_flags=excluded.quality_flags,processed_at=excluded.processed_at',
                       (row['event_id'], stamp.astimezone(timezone.utc).isoformat(), json.dumps(sorted(set(flags))), utc_now()))
            count += 1
    return count


class AssignmentInput(BaseModel):
    course_id: str = Field(min_length=1, max_length=100)
    chapter_id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    instructions: str = Field(min_length=1, max_length=12000)
    initial_code: str = Field(default='', max_length=190000)
    stdin: str = Field(default='', max_length=20000)
    deadline_at: datetime | None = None
    is_published: bool = True


class SubmissionInput(BaseModel):
    request_id: str = Field(min_length=1, max_length=100)
    code: str = Field(max_length=190000)
    stdin: str = Field(default='', max_length=20000)


class LearningEventInput(BaseModel):
    event_id: str = Field(min_length=1, max_length=100)
    event_type: str = Field(min_length=1, max_length=64)
    occurred_at: datetime
    session_id: str = Field(min_length=1, max_length=100)
    course_id: str | None = None
    attempt_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class BatchInput(BaseModel):
    events: list[LearningEventInput] = Field(max_length=100)


class AccessInput(BaseModel):
    teachers: list[str] = Field(max_length=100)
    students: list[str] = Field(max_length=500)


CLIENT_EVENTS = {'page.open','page.leave','page.hidden','page.visible','ui.click','ui.scroll','lecture.page',
                 'lecture.zoom','notebook.edit','notebook.paste','notebook.focus','notebook.blur',
                 'notebook.cell_added','notebook.cell_deleted','notebook.cell_moved','notebook.cell_type',
                 'notebook.imported','notebook.exported','notebook.restored','notebook.output_cleared',
                 'ai.open','ai.close','ai.copy','activity.interval','task.selected'}
CLIENT_METADATA = {'page','action','cell_id','input_type','chars','scroll_top','scroll_left','visible_ms',
                   'ai_visible_ms','sequence','filename','page_number','total_pages','zoom','panel','scope',
                   'resource_id','lesson_id','is_visible','x','y','button','count'}


def create_router(require_roles, rate_limit):
    router = APIRouter(prefix='/api/v1/classroom', tags=['课堂习题与学习记录'])
    everyone = require_roles('student','teacher','admin')
    teaching = require_roles('teacher','admin')
    student_only = require_roles('student')

    @router.get('/courses')
    def assigned_courses(user=Depends(everyone)):
        ids = course_ids(user)
        with get_connection() as db:
            return [dict(row) for row in db.execute('SELECT id,title FROM courses').fetchall() if row['id'] in ids]

    @router.get('/access/{course_id}')
    def access_detail(course_id, user=Depends(require_roles('admin'))):
        with get_connection() as db:
            return {key: [row[0] for row in db.execute(f'SELECT account_id FROM {table} WHERE course_id=?', (course_id,))]
                    for key, table in [('teachers','course_staff'),('students','course_students')]}

    @router.put('/access/{course_id}')
    def update_access(course_id, payload: AccessInput, user=Depends(require_roles('admin'))):
        require_course(user, course_id)
        with get_connection() as db:
            for role, accounts in [('teacher',payload.teachers),('student',payload.students)]:
                for account in accounts:
                    if not db.execute('SELECT 1 FROM users WHERE account_id=? AND role=? AND is_active=1', (account,role)).fetchone():
                        raise HTTPException(422, '分配的账号不存在、已停用或身份不匹配')
            for table, accounts in [('course_staff',payload.teachers),('course_students',payload.students)]:
                db.execute(f'DELETE FROM {table} WHERE course_id=?', (course_id,))
                db.executemany(f'INSERT INTO {table} VALUES (?,?)', [(course_id,account) for account in set(accounts)])
        record_event(user,'course.access_changed',{'teacher_count':len(set(payload.teachers)),'student_count':len(set(payload.students))},course_id=course_id)
        return payload.model_dump()

    @router.get('/assignments')
    def assignments(user=Depends(everyone)):
        ids = course_ids(user)
        with get_connection() as db:
            rows = db.execute('SELECT t.*,c.title course_title FROM assignments t JOIN courses c ON c.id=t.course_id ORDER BY t.updated_at DESC').fetchall()
            attempted = {row[0] for row in db.execute('SELECT assignment_id FROM task_attempts WHERE account_id=?',(user['account_id'],))}
            return [dict(row) for row in rows if row['course_id'] in ids and (user['role'] != 'student' or row['is_published'] or row['id'] in attempted)]

    def save_assignment(payload, user, task_id=None):
        require_course(user, payload.course_id, manage=True)
        if payload.deadline_at and payload.deadline_at.tzinfo is None:
            raise HTTPException(422, '截止时间必须包含时区')
        now = utc_now()
        data = payload.model_dump(mode='json')
        data['deadline_at'] = payload.deadline_at.astimezone(timezone.utc).isoformat() if payload.deadline_at else None
        with get_connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if payload.chapter_id and not db.execute('SELECT 1 FROM chapters WHERE id=? AND course_id=?', (payload.chapter_id,payload.course_id)).fetchone():
                raise HTTPException(422,'章节不属于所选课程')
            old = db.execute('SELECT * FROM assignments WHERE id=?', (task_id,)).fetchone() if task_id else None
            if task_id and not old:
                raise HTTPException(404,'习题不存在')
            if old:
                require_course(user,old['course_id'],manage=True)
                if payload.course_id != old['course_id']:
                    raise HTTPException(422,'已有习题不能迁移课程；请在目标课程新建')
            data.update(id=task_id or str(uuid4()),version=old['version'] + 1 if old else 1,
                        teacher_id=old['teacher_id'] if old else user['account_id'],created_at=old['created_at'] if old else now,updated_at=now)
            columns = ('id','course_id','chapter_id','title','instructions','initial_code','stdin','deadline_at','is_published','version','teacher_id','created_at','updated_at')
            db.execute('INSERT INTO assignments VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET '
                       'chapter_id=excluded.chapter_id,title=excluded.title,instructions=excluded.instructions,initial_code=excluded.initial_code,'
                       'stdin=excluded.stdin,deadline_at=excluded.deadline_at,is_published=excluded.is_published,version=excluded.version,updated_at=excluded.updated_at',tuple(data[key] for key in columns))
            db.execute('INSERT INTO assignment_versions VALUES (?,?,?,?)',(data['id'],data['version'],json.dumps(data,ensure_ascii=False),now))
        record_event(user,'task.updated' if old else 'task.created',{'assignment_id':data['id'],'version':data['version']},course_id=data['course_id'])
        return data

    @router.post('/assignments',status_code=201)
    def create_assignment(payload: AssignmentInput,user=Depends(teaching)):
        return save_assignment(payload,user)

    @router.put('/assignments/{task_id}')
    def update_assignment(task_id,payload: AssignmentInput,user=Depends(teaching)):
        return save_assignment(payload,user,task_id)

    @router.post('/assignments/{task_id}/start')
    def start_assignment(task_id,user=Depends(student_only)):
        with get_connection() as db:
            task = db.execute('SELECT * FROM assignments WHERE id=?',(task_id,)).fetchone()
            old = db.execute('SELECT id FROM task_attempts WHERE assignment_id=? AND account_id=?',(task_id,user['account_id'])).fetchone()
            if not task or (not task['is_published'] and not old):
                raise HTTPException(404,'习题不存在或已撤回')
            require_course(user,task['course_id'])
            attempt_id = str(uuid4())
            db.execute('INSERT OR IGNORE INTO task_attempts VALUES (?,?,?,?,?,NULL)',(attempt_id,user['account_id'],task_id,task['version'],utc_now()))
            attempt = db.execute('SELECT id FROM task_attempts WHERE account_id=? AND assignment_id=?',(user['account_id'],task_id)).fetchone()
            created = attempt[0] == attempt_id
        if created:
            record_event(user,'task.started',{'task_version':task['version']},attempt_id=attempt[0])
        return get_attempt(user,attempt[0])

    @router.post('/attempts/{attempt_id}/submit')
    def submit(attempt_id,payload: SubmissionInput,user=Depends(student_only)):
        attempt = get_attempt(user,attempt_id)
        now = datetime.now(timezone.utc)
        with get_connection() as db:
            existing = db.execute('SELECT s.* FROM task_submissions s WHERE s.request_id=?',(payload.request_id,)).fetchone()
            if existing:
                if existing['attempt_id'] != attempt_id:
                    raise HTTPException(409,'提交编号冲突')
                return dict(existing)
            # Acquire the write lock before re-reading the authoritative deadline.
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT * FROM task_submissions WHERE request_id=?',(payload.request_id,)).fetchone()
            if existing:
                if existing['attempt_id'] != attempt_id:
                    raise HTTPException(409,'提交编号冲突')
                return dict(existing)
            task = db.execute('SELECT is_published,deadline_at FROM assignments WHERE id=?',(attempt['assignment_id'],)).fetchone()
            now = datetime.now(timezone.utc)
            if not task['is_published']:
                raise HTTPException(409,'老师已撤回这道习题')
            if task['deadline_at'] and datetime.fromisoformat(task['deadline_at']) <= now:
                raise HTTPException(409,'已超过作业截止时间；请联系老师延期后提交')
            submission = dict(id=str(uuid4()),attempt_id=attempt_id,request_id=payload.request_id,code=payload.code,stdin=payload.stdin,created_at=now.isoformat())
            db.execute('INSERT INTO task_submissions VALUES (?,?,?,?,?,?)',tuple(submission.values()))
            db.execute('UPDATE task_attempts SET first_submitted_at=COALESCE(first_submitted_at,?) WHERE id=?',(submission['created_at'],attempt_id))
            snapshot_id = str(uuid4())
            db.execute('INSERT INTO code_snapshots VALUES (?,?,?,?,?,?)',(snapshot_id,attempt_id,'submission',None,payload.code,submission['created_at']))
        record_event(user,'task.submitted',{'submission_id':submission['id'],'snapshot_id':snapshot_id},attempt_id=attempt_id)
        return submission

    @router.post('/events')
    def ingest(payload: BatchInput,user=Depends(student_only)):
        rate_limit('learning-events',str(user['account_id']),limit=120,window_seconds=60)
        if len(payload.model_dump_json()) > 100000:
            raise HTTPException(413,'事件批次过大')
        values = []
        attempts = {}
        allowed_courses = course_ids(user)
        now = datetime.now(timezone.utc)
        for item in payload.events:
            if item.event_type not in CLIENT_EVENTS:
                raise HTTPException(422,'客户端事件类型无效')
            if any(key not in CLIENT_METADATA for key in item.metadata) or len(json.dumps(item.metadata)) > 4000:
                raise HTTPException(422,'事件字段不允许或过大；不得上传密钥、密码或聊天输入草稿')
            if any(not isinstance(value,(str,int,float,bool,type(None))) or (isinstance(value,str) and len(value)>300) for value in item.metadata.values()):
                raise HTTPException(422,'客户端事件字段只允许简短文本、数字或布尔值')
            for key in ('visible_ms','ai_visible_ms'):
                value = item.metadata.get(key,0)
                if not isinstance(value,(int,float)) or not 0 <= value <= 90000:
                    raise HTTPException(422,'时间片段无效')
            assignment_id,course_id = None,item.course_id
            if item.attempt_id:
                if item.attempt_id not in attempts:
                    attempts[item.attempt_id] = get_attempt(user,item.attempt_id)
                attempt = attempts[item.attempt_id]
                assignment_id,course_id = attempt['assignment_id'],attempt['course_id']
            elif course_id and course_id not in allowed_courses:
                raise HTTPException(403,'事件不属于当前学生的课程')
            occurred = item.occurred_at
            flags = []
            if occurred.tzinfo is None:
                flags.append('timezone_missing'); occurred = occurred.replace(tzinfo=timezone.utc)
            if abs((occurred-now).total_seconds()) > 300:
                flags.append('clock_skew_or_delayed_delivery')
            values.append((item.event_id,user['account_id'],course_id,assignment_id,item.attempt_id,item.session_id,
                           item.event_type,item.occurred_at.isoformat(),now.isoformat(),json.dumps(item.metadata,ensure_ascii=False),json.dumps(flags)))
        with get_connection() as db:
            db.execute('BEGIN IMMEDIATE')
            for value in values:
                existing = db.execute('SELECT account_id FROM learning_events WHERE event_id=?',(value[0],)).fetchone()
                if existing and existing[0] != user['account_id']:
                    raise HTTPException(409,'事件编号冲突')
            before = db.total_changes
            db.executemany('INSERT OR IGNORE INTO learning_events VALUES (?,?,?,?,?,?,?,?,?,?,?)',values)
            accepted = db.total_changes - before
        return {'accepted':accepted,'duplicates':len(payload.events)-accepted}

    @router.get('/me/time')
    def my_time(user=Depends(student_only)):
        with get_connection() as db:
            rows = db.execute('SELECT * FROM learning_events WHERE account_id=? AND event_type=?',(user['account_id'],'activity.interval')).fetchall()
        return activity_totals(rows)

    @router.get('/attempts/{attempt_id}/chat')
    def attempt_chat(attempt_id,user=Depends(everyone)):
        get_attempt(user,attempt_id)
        with get_connection() as db:
            conversation = db.execute('SELECT conversation_id FROM conversation_tasks WHERE attempt_id=?',(attempt_id,)).fetchone()
            messages = [dict(row) for row in db.execute('SELECT id,role,content,created_at FROM chat_messages WHERE conversation_id=? ORDER BY created_at,id',(conversation[0],))] if conversation else []
        return {'conversation_id':conversation[0] if conversation else None,'messages':messages}

    def visible_rows(user,table):
        ids = course_ids(user)
        with get_connection() as db:
            if table == 'learning_events':
                return [dict(row) for row in db.execute('SELECT * FROM learning_events ORDER BY received_at DESC').fetchall()
                        if user['role'] == 'admin' or row['course_id'] in ids]
            return [dict(row) for row in db.execute('SELECT a.*,t.course_id,t.title,u.name FROM task_attempts a '
                    'JOIN assignments t ON t.id=a.assignment_id JOIN users u ON u.account_id=a.account_id ORDER BY a.started_at DESC').fetchall() if row['course_id'] in ids]

    @router.get('/records')
    def records(user=Depends(teaching)):
        raw = visible_rows(user,'learning_events')
        result = []
        for row in visible_rows(user,'task_attempts'):
            selected = [event for event in raw if event['attempt_id'] == row['id']]
            row.update(activity_totals(selected))
            row['run_count'] = sum(event['event_type'] == 'run.started' for event in selected)
            row['ai_count'] = sum(event['event_type'] == 'ai.sent' for event in selected)
            row['ai_wait_ms'] = sum(json.loads(event['metadata']).get('wait_ms',0) for event in selected if event['event_type'] in {'ai.replied','ai.failed'})
            row['elapsed_ms'] = round((datetime.fromisoformat(row['first_submitted_at'] or utc_now()) - datetime.fromisoformat(row['started_at'])).total_seconds()*1000)
            result.append(row)
        return result

    @router.get('/records/{attempt_id}')
    def record_detail(attempt_id,user=Depends(teaching)):
        attempt = get_attempt(user,attempt_id)
        with get_connection() as db:
            events = [dict(row) for row in db.execute('SELECT * FROM learning_events WHERE attempt_id=? ORDER BY received_at,event_id',(attempt_id,))]
            snapshots = [dict(row) for row in db.execute('SELECT * FROM code_snapshots WHERE attempt_id=? ORDER BY created_at,id',(attempt_id,))]
            submissions = [dict(row) for row in db.execute('SELECT * FROM task_submissions WHERE attempt_id=? ORDER BY created_at,id',(attempt_id,))]
        return {'attempt':attempt,'events':events,'snapshots':snapshots,'submissions':submissions,'chat':attempt_chat(attempt_id,user)}

    @router.get('/events')
    def events(limit: int = 200,user=Depends(teaching)):
        return visible_rows(user,'learning_events')[:max(1,min(limit,1000))]

    @router.get('/events/export')
    def export(user=Depends(teaching)):
        rows = visible_rows(user,'learning_events')
        output = io.StringIO()
        fields = ['event_id','account_id','course_id','assignment_id','attempt_id','session_id','event_type','occurred_at','received_at','metadata','quality_flags']
        writer = csv.DictWriter(output,fieldnames=fields); writer.writeheader()
        for row in rows:
            # Prevent spreadsheet formula injection without mutating database values.
            writer.writerow({key:("'" + str(row[key]) if str(row[key] or '').startswith(('=','+','-','@')) else row[key]) for key in fields})
        return Response('\ufeff'+output.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="learning-events.csv"'})

    @router.post('/events/clean')
    def process(user=Depends(require_roles('admin'))):
        count = clean_events()
        return {'processed':count,'raw_preserved':True}

    return router
