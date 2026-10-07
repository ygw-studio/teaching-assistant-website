import asyncio
from io import BytesIO
from collections import defaultdict, deque
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal
from uuid import uuid4
from urllib.parse import quote
from zipfile import BadZipFile, ZipFile

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.database import (
    authenticate_user,
    change_password,
    conversation_belongs_to_account,
    create_conversation,
    create_session,
    create_user,
    delete_experiment_handout,
    delete_chapter_handout,
    delete_chapter_handout_preview,
    get_chapter_handout,
    get_chapter_resources,
    get_chapter_handout_preview,
    get_code_draft,
    get_course_progress,
    get_student_overview,
    get_user_for_session,
    init_database,
    get_experiment,
    get_experiment_handout,
    get_experiment_handout_name,
    get_course_tree,
    get_user,
    list_users,
    list_conversations,
    list_courses,
    list_messages,
    save_message,
    save_experiment,
    save_experiment_handout,
    save_chapter_handout,
    save_chapter_handout_preview,
    save_course_tree,
    save_code_draft,
    submit_lesson_quiz,
    revoke_session,
    write_audit_event,
    utc_now,
)
from app.notebooks import notebook_pool
from app import classroom, qwen

RUNTIME_ROOT = Path(__file__).resolve().parents[1] / "runtime"
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
APP_ENV = os.getenv("APP_ENV", "development").lower()


def get_cors_origins() -> list[str]:
    configured = os.getenv("CORS_ORIGINS", "").strip()
    if configured:
        return [item.strip() for item in configured.split(",") if item.strip()]
    if APP_ENV == "production":
        return []
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]


DEMO_ACCOUNTS = {
    "student": "20250001",
    "teacher": "T2025001",
    "admin": "admin",
}


def local_demo_enabled(request: Request) -> bool:
    origin = request.headers.get("origin")
    return (
        APP_ENV == "development"
        and "x-platform-edition" not in request.headers
        and os.getenv("ENABLE_LOCAL_DEMO_ACCESS", "false").lower() in {"1", "true", "yes"}
        and request.client is not None
        and request.client.host == "127.0.0.1"
        and request.headers.get("host", "").split(":")[0] in {"127.0.0.1", "localhost"}
        and (origin is None or origin in {
            "http://127.0.0.1:4173",
            "http://localhost:4173",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        })
    )


app = FastAPI(title="知序教学平台 API", version="0.2.0")
init_database()
classroom.init_classroom()
auth_scheme = HTTPBearer(auto_error=False)
RATE_LIMIT_BUCKETS: dict[tuple[str, str], deque[float]] = defaultdict(deque)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserResponse(BaseModel):
    account_id: str
    role: Literal["student", "teacher", "admin"]
    name: str
    phone: str
    detail: str
    is_active: bool


class LoginRequest(BaseModel):
    account_id: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)
    expected_role: Literal["student", "teacher", "admin"] | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: str
    user: UserResponse


class DemoSessionRequest(BaseModel):
    role: Literal["student", "teacher", "admin"]


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class CreateUserRequest(BaseModel):
    account_id: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=256)
    role: Literal["student", "teacher", "admin"]
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(default="", max_length=30)
    detail: str = Field(default="", max_length=200)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    account_id: str = Field(min_length=1, max_length=100)
    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=8000)
    context: str | None = Field(default=None, max_length=12000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    attempt_id: str | None = Field(default=None, max_length=100)
    course_id: str | None = Field(default=None, max_length=100)


class ChatResponse(BaseModel):
    response: str
    model: str
    conversation_id: str
    created_at: str


class ConversationResponse(BaseModel):
    id: str
    account_id: str
    title: str
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    account_id: str
    role: str
    content: str
    created_at: str


class ExecuteRequest(BaseModel):
    code: str = Field(min_length=1, max_length=200_000)
    language: Literal["python"] = "python"
    stdin: str = Field(default="", max_length=20_000)
    scope: Literal["experiment", "lesson"] | None = None
    resource_id: str | None = Field(default=None, min_length=1, max_length=100)
    course_id: str | None = Field(default=None, min_length=1, max_length=100)
    lesson_id: str | None = Field(default=None, min_length=1, max_length=100)
    attempt_id: str | None = Field(default=None, max_length=100)


class ExecuteResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int


class NotebookExecuteRequest(ExecuteRequest):
    notebook_id: str = Field(min_length=1, max_length=100)
    cell_id: str = Field(min_length=1, max_length=64)
    resource_id: str = Field(min_length=1, max_length=100)
    notebook_source: str | None = Field(default=None, max_length=190000)


class NotebookRestartRequest(BaseModel):
    resource_id: str = Field(min_length=1, max_length=100)


class CodeDraftRequest(BaseModel):
    code: str = Field(max_length=200_000)
    stdin: str = Field(default="", max_length=20_000)


class CodeDraftResponse(CodeDraftRequest):
    scope: Literal["experiment", "lesson"]
    resource_id: str
    created_at: str
    updated_at: str


class ExperimentGuideRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    guide_title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=4000)
    requirements: list[str] = Field(min_length=1, max_length=20)
    tips: str = Field(default="", max_length=4000)
    teacher_id: str = Field(default="", max_length=100)
    teacher_name: str = Field(default="", max_length=100)


class ExperimentGuideResponse(ExperimentGuideRequest):
    id: str
    updated_at: str
    handout_name: str | None = None


class CourseSummaryResponse(BaseModel):
    id: str
    title: str
    description: str
    updated_at: str


class LessonPayload(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    lead: str = Field(default="", max_length=4000)
    concept: str = Field(default="", max_length=8000)
    syntax_title: str = Field(default="", max_length=200)
    code: str = Field(default="", max_length=20000)
    steps: list[list[str]] = Field(default_factory=list, max_length=10)
    is_coding: bool = False
    practice_code: str = Field(default="", max_length=20000)
    stdin: str = Field(default="", max_length=20000)
    quiz_question: str = Field(default="", max_length=1000)
    quiz_options: list[str] = Field(default_factory=list, max_length=8)
    quiz_answer: str = Field(default="", max_length=500)
    minutes: int = Field(default=10, ge=1, le=180)


class ChapterPayload(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    handout_name: str | None = None
    preview_name: str | None = None
    resources_name: str | None = None
    lessons: list[LessonPayload] = Field(default_factory=list, max_length=100)


class CourseTreePayload(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    chapters: list[ChapterPayload] = Field(default_factory=list, max_length=50)


class CourseTreeResponse(CourseTreePayload):
    updated_at: str


class QuizAnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=500)


class QuizResultResponse(BaseModel):
    correct: bool
    completed: bool
    completed_at: str | None
    attempt_count: int


class NextLessonResponse(BaseModel):
    id: str
    title: str
    chapter_title: str


class StudentCourseOverviewResponse(BaseModel):
    id: str
    title: str
    total_lessons: int
    completed_lessons: int
    next_lesson: NextLessonResponse | None


class StudentOverviewResponse(BaseModel):
    courses: list[StudentCourseOverviewResponse]
    completed_lessons: int
    total_lessons: int


SYSTEM_PROMPT = """你是“知序”高校编程教学平台的 AI 助教。
你的主要用户是正在学习 Python、数据结构与算法的大学生。

回答要求：
1. 使用简洁、清晰的中文，优先启发学生思考。
2. 解释代码时指出原理、错误原因和修改方向。
3. 除非学生明确要求，不直接给出完整作业答案。
4. 对不确定的信息明确说明，不编造课程内容。
5. 若提供代码，使用 Markdown 代码块。
"""


def get_ai_api_url() -> str:
    raw_url = os.getenv(
        "AI_API_URL",
        os.getenv(
            "DEEPSEEK_API_URL",
            "https://api.deepseek.com/chat/completions",
        ),
    )
    normalized = raw_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def get_ai_model() -> str:
    return os.getenv(
        "AI_MODEL",
        os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
    )


def get_ai_api_key() -> str:
    return os.getenv(
        "AI_API_KEY",
        os.getenv("DEEPSEEK_API_KEY", ""),
    ).strip()


def get_ai_provider_name() -> str:
    return os.getenv(
        "AI_PROVIDER_NAME",
        os.getenv("AI_PROVIDER", "知序平台 AI 服务"),
    )


def unauthorized_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录已失效，请重新登录。",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_platform_edition(request: Request) -> str | None:
    edition = request.headers.get("x-platform-edition")
    if edition is not None and edition not in DEMO_ACCOUNTS:
        raise HTTPException(status_code=422, detail="无效的平台版本。")
    return edition


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
) -> dict[str, str | bool]:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise unauthorized_exception()
    user = get_user_for_session(credentials.credentials)
    if not user:
        raise unauthorized_exception()
    edition = get_platform_edition(request)
    if edition and user["role"] != edition:
        raise HTTPException(status_code=403, detail="当前账号不能访问此版本，请使用对应身份登录。")
    return user


def require_roles(*allowed_roles: str):
    async def guard(
        request: Request,
        current_user: dict[str, str | bool] = Depends(get_current_user),
    ) -> dict[str, str | bool]:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="当前账号没有执行此操作的权限。",
            )
        course_id = request.path_params.get('course_id')
        if current_user['role'] == 'teacher' and course_id and request.method in {'PUT','DELETE'} and get_course_tree(course_id):
            classroom.require_course(current_user,course_id,manage=True)
        return current_user

    return guard


def require_own_account(
    current_user: dict[str, str | bool], account_id: str
) -> None:
    if current_user["account_id"] != account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只能访问自己的学习与对话记录。",
        )


def normalize_phone(phone: str) -> str:
    return "".join(character for character in phone.strip() if character.isdigit())


def require_valid_phone(phone: str) -> str:
    normalized = normalize_phone(phone)
    if len(normalized) != 11 or not normalized.startswith("1"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="请输入 11 位大陆手机号。",
        )
    return normalized


def enforce_rate_limit(
    scope: str, account_id: str, limit: int, window_seconds: int
) -> None:
    now = time.monotonic()
    bucket = RATE_LIMIT_BUCKETS[(scope, account_id)]
    while bucket and now - bucket[0] >= window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="操作过于频繁，请稍后再试。",
        )
    bucket.append(now)


@app.post("/api/v1/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request) -> dict:
    edition = get_platform_edition(request)
    expected_role = edition or payload.expected_role
    account_id = payload.account_id.strip()
    user = authenticate_user(account_id, payload.password)
    if not user or (
        expected_role and user["role"] != expected_role
    ) or (
        edition and payload.expected_role and payload.expected_role != edition
    ):
        write_audit_event(account_id, "auth.login_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号、密码或身份不正确。",
        )
    session = create_session(account_id)
    write_audit_event(account_id, "auth.login_succeeded")
    return {"token_type": "bearer", "user": user, **session}


@app.get("/api/v1/auth/demo-mode")
async def demo_mode(request: Request) -> dict[str, bool]:
    return {"enabled": local_demo_enabled(request)}


@app.post("/api/v1/auth/demo-session", response_model=LoginResponse)
async def demo_session(payload: DemoSessionRequest, request: Request) -> dict:
    if not local_demo_enabled(request):
        raise HTTPException(status_code=404, detail="本机体验入口未启用")
    account_id = DEMO_ACCOUNTS[payload.role]
    user = get_user(account_id)
    if not user or not user["is_active"] or user["role"] != payload.role:
        raise HTTPException(status_code=503, detail="演示账号不可用")
    enforce_rate_limit("demo-session", request.client.host, limit=20, window_seconds=60)
    session = create_session(account_id)
    write_audit_event(account_id, "auth.demo_session_started")
    return {"token_type": "bearer", "user": user, **session}


@app.get("/api/v1/auth/me", response_model=UserResponse)
async def current_user(
    user: dict[str, str | bool] = Depends(get_current_user),
) -> dict[str, str | bool]:
    return user


@app.post("/api/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
    user: dict[str, str | bool] = Depends(get_current_user),
) -> None:
    revoke_session(credentials.credentials if credentials else "")
    write_audit_event(str(user["account_id"]), "auth.logout")


@app.post("/api/v1/auth/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def update_password(
    payload: ChangePasswordRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
    user: dict[str, str | bool] = Depends(get_current_user),
) -> None:
    changed = change_password(
        str(user["account_id"]),
        payload.current_password,
        payload.new_password,
        credentials.credentials if credentials else "",
    )
    if not changed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前密码不正确。",
        )
    write_audit_event(str(user["account_id"]), "auth.password_changed")


@app.post("/api/v1/auth/users", response_model=UserResponse, status_code=201)
async def register_user(
    payload: CreateUserRequest,
    user: dict[str, str | bool] = Depends(require_roles("admin")),
) -> dict[str, str | bool]:
    phone = require_valid_phone(payload.phone) if payload.phone.strip() else ""
    try:
        created = create_user(
            payload.account_id,
            payload.password,
            payload.role,
            payload.name,
            payload.detail,
            phone,
        )
    except sqlite3.IntegrityError as exc:
        if "users.phone" in str(exc) or "idx_users_phone_unique" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="该手机号已绑定其他账号。",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该账号已存在。",
        ) from exc
    write_audit_event(
        str(user["account_id"]),
        "user.created",
        "user",
        payload.account_id,
        {"role": payload.role},
    )
    return created


@app.get("/api/v1/auth/users", response_model=list[UserResponse])
async def users(
    _user: dict[str, str | bool] = Depends(require_roles("admin")),
) -> list[dict[str, str | bool]]:
    return list_users()


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "message": "Welcome to 知序教学平台 API",
        "docs": "/docs",
        "frontend": "http://127.0.0.1:4173/frontend/dist/",
    }


def decode_process_output(output: bytes | str | None) -> str:
    if output is None:
        return ""
    if isinstance(output, str):
        return output

    for encoding in ("utf-8", "gb18030"):
        try:
            return output.decode(encoding)
        except UnicodeDecodeError:
            continue
    return output.decode("utf-8", errors="replace")


def get_execution_mode() -> str:
    default_mode = "docker" if APP_ENV == "production" else "local"
    return os.getenv("CODE_EXECUTION_MODE", default_mode).strip().lower()


def get_execution_timeout_seconds() -> int:
    try:
        return max(1, min(int(os.getenv("EXECUTION_TIMEOUT_SECONDS", "10")), 30))
    except ValueError:
        return 10


def run_python(code: str, stdin: str) -> ExecuteResponse:
    started = time.perf_counter()
    mode = get_execution_mode()
    timeout_seconds = get_execution_timeout_seconds()

    if mode == "local" and APP_ENV == "production":
        return ExecuteResponse(
            stdout="",
            stderr="生产环境禁止直接在 API 服务器上运行学生代码，请启用 Docker 沙箱。",
            exit_code=126,
            duration_ms=0,
        )
    if mode not in {"local", "docker"}:
        return ExecuteResponse(
            stdout="",
            stderr="在线 Python 暂未启用，请联系管理员配置代码运行沙箱。",
            exit_code=126,
            duration_ms=0,
        )

    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    script_path = RUNTIME_ROOT / f"{uuid4().hex}.py"
    script_path.write_text(code, encoding="utf-8")

    if mode == "docker":
        image = os.getenv("CODE_RUNNER_IMAGE", "python:3.12-alpine").strip()
        mount = f"type=bind,src={script_path.resolve()},dst=/workspace/main.py,readonly"
        command = [
            "docker",
            "run",
            "--rm",
            "--interactive",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=16m",
            "--pids-limit",
            "64",
            "--memory",
            "128m",
            "--cpus",
            "0.5",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "65534:65534",
            "--workdir",
            "/workspace",
            "--mount",
            mount,
            image,
            "python",
            "-I",
            "-X",
            "utf8",
            "/workspace/main.py",
        ]
    else:
        command = [sys.executable, "-I", "-X", "utf8", str(script_path)]

    try:
        result = subprocess.run(
            command,
            cwd=RUNTIME_ROOT,
            input=stdin.encode("utf-8"),
            capture_output=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        return ExecuteResponse(
            stdout="",
            stderr="未找到 Docker。生产环境请安装 Docker 并预先拉取代码运行镜像。",
            exit_code=127,
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
    except subprocess.TimeoutExpired as exc:
        return ExecuteResponse(
            stdout=decode_process_output(exc.stdout),
            stderr=f"程序运行超过 {timeout_seconds} 秒，已自动终止。",
            exit_code=124,
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
    finally:
        try:
            script_path.unlink(missing_ok=True)
        except OSError:
            # Some restricted Windows hosts defer cleanup until the process exits.
            pass

    return ExecuteResponse(
        stdout=decode_process_output(result.stdout),
        stderr=decode_process_output(result.stderr),
        exit_code=result.returncode,
        duration_ms=round((time.perf_counter() - started) * 1000),
    )


@app.post("/api/v1/execute", response_model=ExecuteResponse)
async def execute(
    payload: ExecuteRequest,
    user: dict[str, str | bool] = Depends(
        require_roles("student", "teacher", "admin")
    ),
) -> ExecuteResponse:
    account_id = str(user["account_id"])
    if bool(payload.scope) != bool(payload.resource_id):
        raise HTTPException(status_code=422, detail="练习类型和练习标识必须同时提供")
    enforce_rate_limit("execute", account_id, limit=12, window_seconds=60)
    run_id = str(uuid4())
    if payload.attempt_id:
        validate_attempt_execution(user,payload)
        snapshot = classroom.save_code_snapshot(user,payload.attempt_id,payload.code,'run')
        classroom.record_event(user,'run.started',{'run_id':run_id,'snapshot_id':snapshot,'runtime':'python'},payload.attempt_id)
    result = await asyncio.to_thread(run_python, payload.code, payload.stdin)
    if payload.attempt_id:
        classroom.record_event(user,'run.finished',{'run_id':run_id,'exit_code':result.exit_code,'duration_ms':result.duration_ms,
                                                   'stdout':result.stdout[:20000],'stderr':result.stderr[:20000],
                                                   'output_truncated':len(result.stdout)>20000 or len(result.stderr)>20000},payload.attempt_id)
    write_audit_event(
        account_id,
        "code.executed",
        payload.scope or "python",
        payload.resource_id or "",
        metadata={
            "exit_code": result.exit_code,
            "duration_ms": result.duration_ms,
            "course_id": payload.course_id,
            "lesson_id": payload.lesson_id,
            "context_source": "client" if payload.scope else None,
        },
    )
    return result


def require_local_notebook():
    if APP_ENV != "development" or get_execution_mode() != "local":
        raise HTTPException(status_code=503, detail="Notebook 本机内核只用于开发；上线前必须配置隔离的 Jupyter 沙箱，不能直接运行在学校服务器上。")


def validate_attempt_execution(user,payload):
    attempt = classroom.get_attempt(user,payload.attempt_id)
    if attempt['account_id'] != user['account_id'] or attempt['assignment_id'] != payload.resource_id:
        raise HTTPException(403,'只能运行自己当前习题的代码')
    if payload.course_id and payload.course_id != attempt['course_id']:
        raise HTTPException(422,'运行课程与当前习题不一致')


@app.post("/api/v1/notebooks/execute")
async def notebook_execute(payload: NotebookExecuteRequest, user=Depends(require_roles("student", "teacher", "admin"))):
    require_local_notebook()
    account_id = str(user["account_id"])
    enforce_rate_limit("notebook", account_id, limit=60, window_seconds=60)
    started_at = utc_now()
    run_id = str(uuid4())
    if payload.attempt_id:
        validate_attempt_execution(user,payload)
        snapshot = classroom.save_code_snapshot(user,payload.attempt_id,payload.notebook_source or payload.code,'run',payload.cell_id)
        classroom.record_event(user,'run.started',{'run_id':run_id,'snapshot_id':snapshot,'runtime':'jupyter','cell_id':payload.cell_id},payload.attempt_id)
    try:
        result = await asyncio.to_thread(notebook_pool.execute, (account_id, payload.resource_id, payload.notebook_id), payload.code, payload.stdin, get_execution_timeout_seconds())
    except Exception as error:
        if payload.attempt_id:
            classroom.record_event(user,'run.failed',{'run_id':run_id,'error_type':'kernel_unavailable'},payload.attempt_id)
        raise HTTPException(status_code=503, detail="Jupyter 内核启动或连接失败，请重启内核后重试。") from error
    if payload.attempt_id:
        encoded_outputs = json.dumps(result['outputs'],ensure_ascii=False)
        classroom.record_event(user,'run.finished',{'run_id':run_id,'cell_id':payload.cell_id,'exit_code':result['exit_code'],
            'duration_ms':result['duration_ms'],'output_preview':encoded_outputs[:20000],'output_truncated':len(encoded_outputs)>20000},payload.attempt_id)
    write_audit_event(account_id, "code.executed", "experiment", payload.resource_id, metadata={
        "runtime": "jupyter", "notebook_id": payload.notebook_id, "cell_id": payload.cell_id,
        "execution_count": result["execution_count"], "exit_code": result["exit_code"],
        "duration_ms": result["duration_ms"], "kernel_reset": result["kernel_reset"],
        "course_id": payload.course_id, "lesson_id": payload.lesson_id, "started_at": started_at,
    })
    return result


@app.post("/api/v1/notebooks/{notebook_id}/restart")
async def notebook_restart(notebook_id: str, payload: NotebookRestartRequest, user=Depends(require_roles("student", "teacher", "admin"))):
    require_local_notebook()
    if not 1 <= len(notebook_id) <= 100:
        raise HTTPException(status_code=422, detail="Notebook 标识无效")
    account_id = str(user["account_id"])
    await asyncio.to_thread(notebook_pool.restart, (account_id, payload.resource_id, notebook_id))
    write_audit_event(account_id, "notebook.kernel_restarted", "experiment", payload.resource_id, metadata={"notebook_id": notebook_id})
    return {"restarted": True}


@app.on_event("shutdown")
async def close_notebook_kernels():
    await asyncio.to_thread(notebook_pool.close_all)


@app.get(
    "/api/v1/code-drafts/{scope}/{resource_id}",
    response_model=CodeDraftResponse,
)
async def code_draft(
    scope: Literal["experiment", "lesson"],
    resource_id: str,
    user: dict[str, str | bool] = Depends(require_roles("student")),
) -> dict | Response:
    if not 1 <= len(resource_id) <= 100:
        raise HTTPException(status_code=422, detail="练习标识长度无效")
    draft = get_code_draft(str(user["account_id"]), scope, resource_id)
    return draft if draft else Response(status_code=204)


@app.put(
    "/api/v1/code-drafts/{scope}/{resource_id}",
    response_model=CodeDraftResponse,
)
async def update_code_draft(
    scope: Literal["experiment", "lesson"],
    resource_id: str,
    payload: CodeDraftRequest,
    user: dict[str, str | bool] = Depends(require_roles("student")),
) -> dict:
    if not 1 <= len(resource_id) <= 100:
        raise HTTPException(status_code=422, detail="练习标识长度无效")
    return save_code_draft(
        str(user["account_id"]), scope, resource_id, payload.code, payload.stdin
    )


@app.get("/api/v1/courses", response_model=list[CourseSummaryResponse])
async def courses(
    _user: dict[str, str | bool] = Depends(get_current_user),
) -> list[dict[str, str]]:
    return list_courses()


@app.get("/api/v1/courses/{course_id}", response_model=CourseTreeResponse)
async def course_detail(
    course_id: str,
    user: dict[str, str | bool] = Depends(get_current_user),
) -> dict:
    course = get_course_tree(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    if user["role"] == "student":
        for chapter in course["chapters"]:
            for lesson in chapter["lessons"]:
                lesson["quiz_answer"] = ""
    return course


@app.get("/api/v1/courses/{course_id}/progress")
async def course_progress(
    course_id: str,
    user: dict[str, str | bool] = Depends(require_roles("student")),
) -> list[dict[str, str]]:
    if not get_course_tree(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")
    return get_course_progress(str(user["account_id"]), course_id)


@app.get("/api/v1/students/me/overview", response_model=StudentOverviewResponse)
async def student_overview(
    user: dict[str, str | bool] = Depends(require_roles("student")),
) -> dict:
    return get_student_overview(str(user["account_id"]))


@app.post(
    "/api/v1/courses/{course_id}/lessons/{lesson_id}/quiz",
    response_model=QuizResultResponse,
)
async def answer_lesson_quiz(
    course_id: str,
    lesson_id: str,
    payload: QuizAnswerRequest,
    user: dict[str, str | bool] = Depends(require_roles("student")),
) -> dict:
    enforce_rate_limit("lesson-quiz", str(user["account_id"]), limit=30, window_seconds=60)
    try:
        result = submit_lesson_quiz(
            str(user["account_id"]), course_id, lesson_id, payload.answer
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="知识点不存在")
    return result


@app.put("/api/v1/courses/{course_id}", response_model=CourseTreeResponse)
async def update_course(
    course_id: str,
    payload: CourseTreePayload,
    user: dict[str, str | bool] = Depends(require_roles("teacher", "admin")),
) -> dict:
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    data["id"] = course_id
    if not data["chapters"]:
        raise HTTPException(status_code=400, detail="至少需要一个章节")
    for chapter in data["chapters"]:
        if not chapter["lessons"]:
            raise HTTPException(status_code=400, detail="每个章节至少需要一个知识点")
        for lesson in chapter["lessons"]:
            if lesson["quiz_options"] and lesson["quiz_answer"] not in lesson["quiz_options"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"{lesson['title']} 的正确答案必须在选项中",
                )
    saved = save_course_tree(data)
    if user['role'] == 'teacher':
        from app.database import get_connection
        with get_connection() as connection:
            connection.execute('INSERT OR IGNORE INTO course_staff VALUES (?,?)',(course_id,user['account_id']))
    write_audit_event(
        str(user["account_id"]),
        "course.updated",
        "course",
        course_id,
    )
    return saved


def chapter_exists(course_id: str, chapter_id: str) -> bool:
    course = get_course_tree(course_id)
    return bool(course and any(chapter["id"] == chapter_id for chapter in course["chapters"]))


@app.put("/api/v1/courses/{course_id}/chapters/{chapter_id}/handout")
async def upload_chapter_handout(
    course_id: str,
    chapter_id: str,
    filename: str,
    request: Request,
    user: dict[str, str | bool] = Depends(require_roles("teacher", "admin")),
) -> dict[str, str]:
    if not chapter_exists(course_id, chapter_id):
        raise HTTPException(status_code=404, detail="请先保存该章节")
    extension = Path(filename).suffix.lower()
    if not filename or len(filename) > 200 or extension not in {".pdf", ".pptx"} or any(char in filename for char in ("/", "\\", "\x00")):
        raise HTTPException(status_code=400, detail="只支持文件名正常的 PDF 或 PPTX 讲义")
    media_type = "application/pdf" if extension == ".pdf" else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    if request.headers.get("content-type", "").split(";")[0].lower() != media_type:
        raise HTTPException(status_code=415, detail="文件类型与扩展名不一致")
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 15 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="讲义不能超过 15 MB")
        chunks.append(chunk)
    content = b"".join(chunks)
    if extension == ".pdf":
        valid = content.startswith(b"%PDF-")
    else:
        try:
            with ZipFile(BytesIO(content)) as package:
                valid = "ppt/presentation.xml" in package.namelist()
        except BadZipFile:
            valid = False
    if not valid:
        raise HTTPException(status_code=400, detail="文件内容不是有效讲义")
    save_chapter_handout(course_id, chapter_id, filename, content)
    write_audit_event(str(user["account_id"]), "course.handout_uploaded", "chapter", chapter_id)
    return {"filename": filename}


@app.get("/api/v1/courses/{course_id}/chapters/{chapter_id}/resources")
async def download_chapter_resources(
    course_id: str,
    chapter_id: str,
    _user: dict[str, str | bool] = Depends(require_roles("teacher", "admin")),
) -> Response:
    resources = get_chapter_resources(course_id, chapter_id)
    if not resources or not chapter_exists(course_id, chapter_id):
        raise HTTPException(status_code=404, detail="本章暂无配套资源")
    return Response(
        content=resources["content"],
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(resources['filename'])}"},
    )


@app.get("/api/v1/courses/{course_id}/chapters/{chapter_id}/handout")
async def download_chapter_handout(
    course_id: str,
    chapter_id: str,
    _user: dict[str, str | bool] = Depends(get_current_user),
) -> Response:
    handout = get_chapter_handout(course_id, chapter_id)
    if not handout or not chapter_exists(course_id, chapter_id):
        raise HTTPException(status_code=404, detail="该章节暂无讲义")
    media_type = "application/pdf" if handout["filename"].lower().endswith(".pdf") else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    return Response(
        content=handout["content"],
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(handout['filename'])}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@app.delete("/api/v1/courses/{course_id}/chapters/{chapter_id}/handout", status_code=204)
async def remove_chapter_handout(
    course_id: str,
    chapter_id: str,
    user: dict[str, str | bool] = Depends(require_roles("teacher", "admin")),
) -> Response:
    if not delete_chapter_handout(course_id, chapter_id):
        raise HTTPException(status_code=404, detail="该章节暂无讲义")
    write_audit_event(str(user["account_id"]), "course.handout_removed", "chapter", chapter_id)
    return Response(status_code=204)


@app.put("/api/v1/courses/{course_id}/chapters/{chapter_id}/handout/preview")
async def upload_chapter_handout_preview(
    course_id: str,
    chapter_id: str,
    filename: str,
    request: Request,
    user: dict[str, str | bool] = Depends(require_roles("teacher", "admin")),
) -> dict[str, str]:
    if not chapter_exists(course_id, chapter_id) or not get_chapter_handout(course_id, chapter_id):
        raise HTTPException(status_code=404, detail="请先保存该章节的原版课件")
    if not filename or len(filename) > 200 or not filename.lower().endswith(".pdf") or any(char in filename for char in ("/", "\\", "\x00")):
        raise HTTPException(status_code=400, detail="预览文件必须是 PDF")
    if request.headers.get("content-type", "").split(";")[0].lower() != "application/pdf":
        raise HTTPException(status_code=415, detail="只支持 PDF 文件")
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 15 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="预览 PDF 不能超过 15 MB")
        chunks.append(chunk)
    content = b"".join(chunks)
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="文件内容不是有效 PDF")
    save_chapter_handout_preview(course_id, chapter_id, filename, content)
    write_audit_event(str(user["account_id"]), "course.handout_preview_uploaded", "chapter", chapter_id)
    return {"filename": filename}


@app.get("/api/v1/courses/{course_id}/chapters/{chapter_id}/handout/preview")
async def download_chapter_handout_preview(
    course_id: str,
    chapter_id: str,
    _user: dict[str, str | bool] = Depends(get_current_user),
) -> Response:
    preview = get_chapter_handout_preview(course_id, chapter_id)
    if not preview or not chapter_exists(course_id, chapter_id):
        raise HTTPException(status_code=404, detail="该章节暂无可预览的 PDF 讲义")
    return Response(
        content=preview["content"],
        media_type="application/pdf",
        headers={"Content-Disposition": "inline", "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


@app.delete("/api/v1/courses/{course_id}/chapters/{chapter_id}/handout/preview", status_code=204)
async def remove_chapter_handout_preview(
    course_id: str,
    chapter_id: str,
    user: dict[str, str | bool] = Depends(require_roles("teacher", "admin")),
) -> Response:
    if not delete_chapter_handout_preview(course_id, chapter_id):
        raise HTTPException(status_code=404, detail="该章节没有单独上传的预览 PDF")
    write_audit_event(str(user["account_id"]), "course.handout_preview_removed", "chapter", chapter_id)
    return Response(status_code=204)


@app.get(
    "/api/v1/experiments/{experiment_id}",
    response_model=ExperimentGuideResponse,
)
async def experiment_detail(
    experiment_id: str,
    _user: dict[str, str | bool] = Depends(get_current_user),
) -> dict:
    experiment = get_experiment(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="实验指导不存在")
    experiment["requirements"] = json.loads(experiment["requirements"])
    experiment["handout_name"] = get_experiment_handout_name(experiment_id)
    return experiment


@app.put(
    "/api/v1/experiments/{experiment_id}",
    response_model=ExperimentGuideResponse,
)
async def update_experiment(
    experiment_id: str,
    payload: ExperimentGuideRequest,
    user: dict[str, str | bool] = Depends(require_roles("teacher", "admin")),
) -> dict:
    experiment = save_experiment(
        experiment_id=experiment_id,
        title=payload.title,
        description=payload.description,
        guide_title=payload.guide_title,
        objective=payload.objective,
        requirements=json.dumps(payload.requirements, ensure_ascii=False),
        tips=payload.tips,
        teacher_id=str(user["account_id"]),
        teacher_name=str(user["name"]),
    )
    experiment["requirements"] = json.loads(experiment["requirements"])
    experiment["handout_name"] = get_experiment_handout_name(experiment_id)
    write_audit_event(
        str(user["account_id"]),
        "experiment.updated",
        "experiment",
        experiment_id,
    )
    return experiment


@app.put("/api/v1/experiments/{experiment_id}/handout")
async def upload_experiment_handout(
    experiment_id: str,
    filename: str,
    request: Request,
    user: dict[str, str | bool] = Depends(require_roles("teacher", "admin")),
) -> dict[str, str]:
    if not get_experiment(experiment_id):
        raise HTTPException(status_code=404, detail="请先保存实验指导")
    if (
        not filename
        or len(filename) > 200
        or not filename.lower().endswith(".pdf")
        or any(char in filename for char in ("/", "\\", "\x00"))
    ):
        raise HTTPException(status_code=400, detail="只支持文件名正常的 PDF 讲义")
    if request.headers.get("content-type", "").split(";")[0].lower() != "application/pdf":
        raise HTTPException(status_code=415, detail="只支持 PDF 文件")

    max_bytes = 10 * 1024 * 1024
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(status_code=413, detail="讲义不能超过 10 MB")
        chunks.append(chunk)
    content = b"".join(chunks)
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="文件内容不是有效 PDF")
    save_experiment_handout(experiment_id, filename, content)
    write_audit_event(str(user["account_id"]), "experiment.handout_uploaded", "experiment", experiment_id)
    return {"filename": filename}


@app.get("/api/v1/experiments/{experiment_id}/handout")
async def download_experiment_handout(
    experiment_id: str,
    _user: dict[str, str | bool] = Depends(get_current_user),
) -> Response:
    handout = get_experiment_handout(experiment_id)
    if not handout:
        raise HTTPException(status_code=404, detail="尚未上传 PDF 讲义")
    return Response(
        content=handout["content"],
        media_type="application/pdf",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


@app.delete("/api/v1/experiments/{experiment_id}/handout", status_code=204)
async def remove_experiment_handout(
    experiment_id: str,
    user: dict[str, str | bool] = Depends(require_roles("teacher", "admin")),
) -> Response:
    if not delete_experiment_handout(experiment_id):
        raise HTTPException(status_code=404, detail="该实验没有 PDF 讲义")
    write_audit_event(str(user["account_id"]), "experiment.handout_removed", "experiment", experiment_id)
    return Response(status_code=204)


@app.get(
    "/api/v1/ai/conversations/{account_id}",
    response_model=list[ConversationResponse],
)
async def conversations(
    account_id: str,
    current_user: dict[str, str | bool] = Depends(get_current_user),
) -> list[dict[str, str]]:
    require_own_account(current_user, account_id)
    return list_conversations(account_id)


@app.get(
    "/api/v1/ai/conversations/{account_id}/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
async def conversation_messages(
    account_id: str,
    conversation_id: str,
    current_user: dict[str, str | bool] = Depends(get_current_user),
) -> list[dict[str, str]]:
    require_own_account(current_user, account_id)
    if not conversation_belongs_to_account(conversation_id, account_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return list_messages(conversation_id, account_id)


@app.post("/api/v1/ai/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: dict[str, str | bool] = Depends(
        require_roles("student", "teacher")
    ),
) -> ChatResponse:
    require_own_account(current_user, payload.account_id)
    enforce_rate_limit(
        "ai", str(current_user["account_id"]), limit=20, window_seconds=60
    )
    result = await qwen.chat(current_user,payload.message,payload.conversation_id,payload.attempt_id,payload.course_id)
    return ChatResponse(**result)


app.include_router(classroom.create_router(require_roles,enforce_rate_limit))
app.include_router(qwen.create_key_router(require_roles))
