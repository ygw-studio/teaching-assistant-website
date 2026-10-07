import json
import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from .data_structure_course import DATA_STRUCTURE_COURSE


WORKSPACE_DATABASE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "teaching-platform.db"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def get_database_path() -> Path:
    configured = os.getenv("DATABASE_PATH", "").strip()
    if configured:
        return Path(configured)

    app_data_dir = os.getenv("APP_DATA_DIR", "").strip()
    if app_data_dir:
        return Path(app_data_dir) / "teaching-platform.db"

    local_app_data = os.getenv("LOCALAPPDATA", "").strip()
    if os.name == "nt" and local_app_data and os.getenv(
        "APP_ENV", "development"
    ).lower() != "production":
        return Path(local_app_data) / "TeachingAssistant" / "data" / "teaching-platform.db"

    if os.getenv("APP_ENV", "development").lower() == "production":
        raise RuntimeError(
            "Production deployment requires DATABASE_PATH to point to a dedicated data disk."
        )
    return WORKSPACE_DATABASE_PATH


def get_session_ttl_hours() -> int:
    try:
        return max(1, min(int(os.getenv("SESSION_TTL_HOURS", "8")), 24 * 30))
    except ValueError:
        return 8


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    database_path = get_database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA synchronous = NORMAL")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_database() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_conversations_account
                ON conversations(account_id, updated_at DESC);

            CREATE TABLE IF NOT EXISTS chat_messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(conversation_id)
                    REFERENCES conversations(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON chat_messages(conversation_id, created_at);

            CREATE TABLE IF NOT EXISTS users (
                account_id TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('student', 'teacher', 'admin')),
                name TEXT NOT NULL,
                phone TEXT NOT NULL DEFAULT '',
                detail TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_users_role
                ON users(role, is_active);

            CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                FOREIGN KEY(account_id)
                    REFERENCES users(account_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_account
                ON auth_sessions(account_id, expires_at);

            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                account_id TEXT,
                event_type TEXT NOT NULL,
                resource_type TEXT NOT NULL DEFAULT '',
                resource_id TEXT NOT NULL DEFAULT '',
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(account_id)
                    REFERENCES users(account_id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_audit_events_account
                ON audit_events(account_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS code_drafts (
                account_id TEXT NOT NULL,
                scope TEXT NOT NULL CHECK(scope IN ('experiment', 'lesson')),
                resource_id TEXT NOT NULL,
                code TEXT NOT NULL,
                stdin TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(account_id, scope, resource_id),
                FOREIGN KEY(account_id) REFERENCES users(account_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS lesson_quiz_attempts (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                course_id TEXT NOT NULL,
                chapter_id TEXT NOT NULL,
                lesson_id TEXT NOT NULL,
                answer TEXT NOT NULL,
                is_correct INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(account_id) REFERENCES users(account_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_quiz_attempts_account_course
                ON lesson_quiz_attempts(account_id, course_id, created_at);

            CREATE INDEX IF NOT EXISTS idx_quiz_attempts_lesson
                ON lesson_quiz_attempts(account_id, course_id, lesson_id);

            CREATE TABLE IF NOT EXISTS lesson_progress (
                account_id TEXT NOT NULL,
                course_id TEXT NOT NULL,
                lesson_id TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                PRIMARY KEY(account_id, course_id, lesson_id),
                FOREIGN KEY(account_id) REFERENCES users(account_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                guide_title TEXT NOT NULL DEFAULT '',
                objective TEXT NOT NULL DEFAULT '',
                requirements TEXT NOT NULL DEFAULT '[]',
                tips TEXT NOT NULL DEFAULT '',
                teacher_id TEXT NOT NULL,
                teacher_name TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS experiment_handouts (
                experiment_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                content BLOB NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(experiment_id)
                    REFERENCES experiments(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS courses (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chapters (
                id TEXT PRIMARY KEY,
                course_id TEXT NOT NULL,
                title TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(course_id)
                    REFERENCES courses(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS lessons (
                id TEXT PRIMARY KEY,
                chapter_id TEXT NOT NULL,
                title TEXT NOT NULL,
                lead TEXT NOT NULL DEFAULT '',
                concept TEXT NOT NULL DEFAULT '',
                syntax_title TEXT NOT NULL DEFAULT '',
                code TEXT NOT NULL DEFAULT '',
                steps TEXT NOT NULL DEFAULT '[]',
                is_coding INTEGER NOT NULL DEFAULT 0,
                practice_code TEXT NOT NULL DEFAULT '',
                stdin TEXT NOT NULL DEFAULT '',
                quiz_question TEXT NOT NULL DEFAULT '',
                quiz_options TEXT NOT NULL DEFAULT '[]',
                quiz_answer TEXT NOT NULL DEFAULT '',
                minutes INTEGER NOT NULL DEFAULT 10,
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(chapter_id)
                    REFERENCES chapters(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chapter_handouts (
                course_id TEXT NOT NULL,
                chapter_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                content BLOB NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(course_id, chapter_id),
                FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chapter_handout_previews (
                course_id TEXT NOT NULL,
                chapter_id TEXT NOT NULL,
                filename TEXT NOT NULL DEFAULT '',
                content BLOB,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(course_id, chapter_id),
                FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chapter_resources (
                course_id TEXT NOT NULL,
                chapter_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                content BLOB NOT NULL,
                PRIMARY KEY(course_id, chapter_id),
                FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS course_import_versions (
                course_id TEXT NOT NULL,
                version TEXT NOT NULL,
                applied_at TEXT NOT NULL,
                PRIMARY KEY(course_id, version),
                FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
            );
            """
        )
        migrate_users_schema(connection)
        seed_data_structure_course(connection)
        seed_data_structure_preview(connection)
        seed_initial_users(connection)


def migrate_users_schema(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(users)").fetchall()
    }
    if "phone" not in columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN phone TEXT NOT NULL DEFAULT ''"
        )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone_unique
            ON users(phone)
            WHERE phone <> ''
        """
    )




def seed_data_structure_course(connection: sqlite3.Connection) -> None:
    course_id = DATA_STRUCTURE_COURSE["id"]
    version = "full-course-v1"
    exists = connection.execute(
        "SELECT 1 FROM courses WHERE id = ?", (course_id,)
    ).fetchone()
    imported = connection.execute(
        "SELECT 1 FROM course_import_versions WHERE course_id = ? AND version = ?",
        (course_id, version),
    ).fetchone()
    if exists and imported:
        return

    created = set()
    if not exists:
        save_course_tree_in_connection(connection, DATA_STRUCTURE_COURSE)
        created = {chapter["id"] for chapter in DATA_STRUCTURE_COURSE["chapters"]}
    else:
        # Upgrade only once; later teacher edits and deletions remain authoritative.
        next_order = connection.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM chapters WHERE course_id = ?", (course_id,)
        ).fetchone()[0]
        for chapter in DATA_STRUCTURE_COURSE["chapters"][1:]:
            if chapter_exists_in_connection(connection, course_id, chapter["id"]):
                continue
            insert_course_chapter(connection, course_id, chapter, next_order)
            created.add(chapter["id"])
            next_order += 1
        connection.execute(
            "UPDATE courses SET description = ? WHERE id = ? AND description = ?",
            (DATA_STRUCTURE_COURSE["description"], course_id,
             "依据教师课件《第1章 绪论》整理；后续章节由教师逐步发布。"),
        )
        if created:
            connection.execute("UPDATE courses SET updated_at = ? WHERE id = ?", (utc_now(), course_id))

    asset_root = Path(__file__).resolve().parents[1] / "assets" / "data-structures"
    materials = json.loads((asset_root / "source-material.json").read_text(encoding="utf-8"))
    for material in materials:
        number = material["number"]
        chapter_id = f"ds-chapter-{number}"
        if not chapter_exists_in_connection(connection, course_id, chapter_id):
            continue
        connection.execute(
            "INSERT INTO chapter_handouts (course_id, chapter_id, filename, content, updated_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(course_id, chapter_id) DO NOTHING",
            (course_id, chapter_id, material["handout_name"], (asset_root / f"chapter-{number}.pptx").read_bytes(), utc_now()),
        )
        connection.execute(
            "INSERT INTO chapter_resources (course_id, chapter_id, filename, content) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(course_id, chapter_id) DO NOTHING",
            (course_id, chapter_id, f"第{number}章 {material['title']}配套资源.zip",
             (asset_root / f"chapter-{number}-resources.zip").read_bytes()),
        )
    connection.execute(
        "INSERT INTO course_import_versions (course_id, version, applied_at) VALUES (?, ?, ?)",
        (course_id, version, utc_now()),
    )


def chapter_exists_in_connection(connection: sqlite3.Connection, course_id: str, chapter_id: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM chapters WHERE course_id = ? AND id = ?", (course_id, chapter_id)
    ).fetchone() is not None


def seed_data_structure_preview(connection: sqlite3.Connection) -> None:
    asset_root = Path(__file__).resolve().parents[1] / "assets" / "data-structures"
    for number in range(1, 9):
        chapter_id = f"ds-chapter-{number}"
        if connection.execute(
            "SELECT 1 FROM chapter_handout_previews WHERE course_id = ? AND chapter_id = ?",
            (DATA_STRUCTURE_COURSE["id"], chapter_id),
        ).fetchone():
            continue
        preview_path = asset_root / f"chapter-{number}.pdf"
        original_path = preview_path.with_suffix(".pptx")
        if not preview_path.is_file() or not original_path.is_file():
            continue
        original = connection.execute(
            "SELECT filename, content FROM chapter_handouts WHERE course_id = ? AND chapter_id = ?",
            (DATA_STRUCTURE_COURSE["id"], chapter_id),
        ).fetchone()
        if not original or original["content"] != original_path.read_bytes():
            continue
        connection.execute(
            "INSERT INTO chapter_handout_previews (course_id, chapter_id, filename, content, updated_at) VALUES (?, ?, ?, ?, ?)",
            (DATA_STRUCTURE_COURSE["id"], chapter_id, Path(original["filename"]).with_suffix(".pdf").name,
             preview_path.read_bytes(), utc_now()),
        )


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return f"scrypt$16384$8$1${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = stored_hash.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_b64decode(expected)),
        )
        return hmac.compare_digest(actual, _b64decode(expected))
    except (ValueError, TypeError):
        return False


def serialize_user(row: sqlite3.Row | dict) -> dict[str, str | bool]:
    return {
        "account_id": row["account_id"],
        "role": row["role"],
        "name": row["name"],
        "phone": row["phone"],
        "detail": row["detail"],
        "is_active": bool(row["is_active"]),
    }


def _create_user_in_connection(
    connection: sqlite3.Connection,
    account_id: str,
    password: str,
    role: str,
    name: str,
    detail: str,
    phone: str = "",
) -> dict[str, str | bool]:
    timestamp = utc_now()
    connection.execute(
        """
        INSERT INTO users (
            account_id, password_hash, role, name, phone, detail,
            is_active, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (
            account_id,
            hash_password(password),
            role,
            name,
            phone,
            detail,
            timestamp,
            timestamp,
        ),
    )
    return {
        "account_id": account_id,
        "role": role,
        "name": name,
        "phone": phone,
        "detail": detail,
        "is_active": True,
    }


def create_user(
    account_id: str,
    password: str,
    role: str,
    name: str,
    detail: str = "",
    phone: str = "",
) -> dict[str, str | bool]:
    if role not in {"student", "teacher", "admin"}:
        raise ValueError("不支持的用户角色")
    with get_connection() as connection:
        return _create_user_in_connection(
            connection,
            account_id.strip(),
            password,
            role,
            name.strip(),
            detail.strip(),
            phone.strip(),
        )


def seed_initial_users(connection: sqlite3.Connection) -> None:
    environment = os.getenv("APP_ENV", "development").lower()
    seed_demo_users = os.getenv("SEED_DEMO_USERS", "true").lower() == "true"

    if environment != "production" and seed_demo_users:
        demo_users = [
            ("20250001", "Student@2025", "student", "林同学", "计算机科学 2025级"),
            ("T2025001", "Teacher@2025", "teacher", "张老师", "Python 程序设计课程"),
            ("admin", "Admin@2025", "admin", "系统管理员", "平台运维管理"),
        ]
        for account_id, password, role, name, detail in demo_users:
            exists = connection.execute(
                "SELECT 1 FROM users WHERE account_id = ?", (account_id,)
            ).fetchone()
            if not exists:
                _create_user_in_connection(
                    connection, account_id, password, role, name, detail
                )
        return

    account_id = os.getenv("BOOTSTRAP_ADMIN_ACCOUNT", "").strip()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    if environment == "production" and account_id and password:
        exists = connection.execute(
            "SELECT 1 FROM users WHERE account_id = ?", (account_id,)
        ).fetchone()
        if not exists:
            _create_user_in_connection(
                connection,
                account_id,
                password,
                "admin",
                os.getenv("BOOTSTRAP_ADMIN_NAME", "系统管理员").strip() or "系统管理员",
                "平台运维管理",
            )


def get_user(account_id: str) -> dict[str, str | bool] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT account_id, role, name, phone, detail, is_active
            FROM users
            WHERE account_id = ?
            """,
            (account_id,),
        ).fetchone()
    return serialize_user(row) if row else None


def list_users() -> list[dict[str, str | bool]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT account_id, role, name, phone, detail, is_active
            FROM users
            ORDER BY role ASC, account_id ASC
            """
        ).fetchall()
    return [serialize_user(row) for row in rows]


def authenticate_user(
    account_id: str, password: str
) -> dict[str, str | bool] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT account_id, password_hash, role, name, phone, detail, is_active
            FROM users
            WHERE account_id = ?
            """,
            (account_id,),
        ).fetchone()
    if not row or not bool(row["is_active"]):
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return serialize_user(row)


def _hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(account_id: str) -> dict[str, str]:
    token = secrets.token_urlsafe(32)
    timestamp = datetime.now(timezone.utc)
    expires_at = timestamp + timedelta(hours=get_session_ttl_hours())
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM auth_sessions WHERE expires_at <= ?", (timestamp.isoformat(),)
        )
        connection.execute(
            """
            INSERT INTO auth_sessions (
                token_hash, account_id, created_at, expires_at, last_seen_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                _hash_session_token(token),
                account_id,
                timestamp.isoformat(),
                expires_at.isoformat(),
                timestamp.isoformat(),
            ),
        )
    return {"access_token": token, "expires_at": expires_at.isoformat()}


def get_user_for_session(token: str) -> dict[str, str | bool] | None:
    if not token:
        return None
    now = datetime.now(timezone.utc)
    token_hash = _hash_session_token(token)
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT users.account_id, users.role, users.name, users.phone, users.detail,
                   users.is_active, auth_sessions.expires_at
            FROM auth_sessions
            JOIN users ON users.account_id = auth_sessions.account_id
            WHERE auth_sessions.token_hash = ?
            """,
            (token_hash,),
        ).fetchone()
        if not row:
            return None
        if not bool(row["is_active"]) or parse_timestamp(row["expires_at"]) <= now:
            connection.execute(
                "DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,)
            )
            return None
        connection.execute(
            "UPDATE auth_sessions SET last_seen_at = ? WHERE token_hash = ?",
            (now.isoformat(), token_hash),
        )
    return serialize_user(row)


def revoke_session(token: str) -> None:
    if not token:
        return
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM auth_sessions WHERE token_hash = ?",
            (_hash_session_token(token),),
        )


def change_password(
    account_id: str,
    current_password: str,
    new_password: str,
    current_session_token: str,
) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT password_hash FROM users WHERE account_id = ? AND is_active = 1",
            (account_id,),
        ).fetchone()
        if not row or not verify_password(current_password, row["password_hash"]):
            return False
        connection.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE account_id = ?",
            (hash_password(new_password), utc_now(), account_id),
        )
        connection.execute(
            "DELETE FROM auth_sessions WHERE account_id = ? AND token_hash != ?",
            (account_id, _hash_session_token(current_session_token)),
        )
    return True


def write_audit_event(
    account_id: str | None,
    event_type: str,
    resource_type: str = "",
    resource_id: str = "",
    metadata: dict | None = None,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO audit_events (
                id, account_id, event_type, resource_type,
                resource_id, metadata, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                account_id,
                event_type,
                resource_type,
                resource_id,
                json.dumps(metadata or {}, ensure_ascii=False),
                utc_now(),
            ),
        )


def get_code_draft(account_id: str, scope: str, resource_id: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT scope, resource_id, code, stdin, created_at, updated_at
            FROM code_drafts
            WHERE account_id = ? AND scope = ? AND resource_id = ?
            """,
            (account_id, scope, resource_id),
        ).fetchone()
    return dict(row) if row else None


def save_code_draft(
    account_id: str, scope: str, resource_id: str, code: str, stdin: str
) -> dict:
    timestamp = utc_now()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO code_drafts
                (account_id, scope, resource_id, code, stdin, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_id, scope, resource_id) DO UPDATE SET
                code = excluded.code,
                stdin = excluded.stdin,
                updated_at = excluded.updated_at
            """,
            (account_id, scope, resource_id, code, stdin, timestamp, timestamp),
        )
    return get_code_draft(account_id, scope, resource_id)


def get_course_progress(account_id: str, course_id: str) -> list[dict[str, str]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT progress.lesson_id, progress.completed_at
            FROM lesson_progress AS progress
            JOIN lessons ON lessons.id = progress.lesson_id
            JOIN chapters ON chapters.id = lessons.chapter_id
            WHERE progress.account_id = ? AND progress.course_id = ?
              AND chapters.course_id = ?
            ORDER BY progress.completed_at
            """,
            (account_id, course_id, course_id),
        ).fetchall()
    return [dict(row) for row in rows]


def submit_lesson_quiz(
    account_id: str, course_id: str, lesson_id: str, answer: str
) -> dict[str, str | int | bool | None] | None:
    normalized_answer = answer.strip()
    with get_connection() as connection:
        lesson = connection.execute(
            """
            SELECT lessons.quiz_answer, lessons.quiz_options,
                   chapters.id AS chapter_id
            FROM lessons
            JOIN chapters ON chapters.id = lessons.chapter_id
            WHERE lessons.id = ? AND chapters.course_id = ?
            """,
            (lesson_id, course_id),
        ).fetchone()
        if not lesson:
            return None
        if not lesson["quiz_answer"].strip():
            raise ValueError("教师尚未设置本节小测答案。")
        if normalized_answer not in json.loads(lesson["quiz_options"]):
            raise ValueError("请选择本节小测提供的有效选项。")

        correct = normalized_answer == lesson["quiz_answer"].strip()
        timestamp = utc_now()
        connection.execute(
            """
            INSERT INTO lesson_quiz_attempts
                (id, account_id, course_id, chapter_id, lesson_id,
                 answer, is_correct, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()), account_id, course_id, lesson["chapter_id"],
                lesson_id, normalized_answer, int(correct), timestamp,
            ),
        )
        if correct:
            connection.execute(
                """
                INSERT OR IGNORE INTO lesson_progress
                    (account_id, course_id, lesson_id, completed_at)
                VALUES (?, ?, ?, ?)
                """,
                (account_id, course_id, lesson_id, timestamp),
            )
        progress = connection.execute(
            """
            SELECT completed_at FROM lesson_progress
            WHERE account_id = ? AND course_id = ? AND lesson_id = ?
            """,
            (account_id, course_id, lesson_id),
        ).fetchone()
        attempts = connection.execute(
            """
            SELECT COUNT(*) FROM lesson_quiz_attempts
            WHERE account_id = ? AND course_id = ? AND lesson_id = ?
            """,
            (account_id, course_id, lesson_id),
        ).fetchone()[0]
    return {
        "correct": correct,
        "completed": progress is not None,
        "completed_at": progress["completed_at"] if progress else None,
        "attempt_count": attempts,
    }


def get_student_overview(account_id: str) -> dict:
    with get_connection() as connection:
        course_rows = connection.execute(
            """
            SELECT courses.id, courses.title,
                   COUNT(lessons.id) AS total_lessons,
                   COUNT(progress.lesson_id) AS completed_lessons
            FROM courses
            LEFT JOIN chapters ON chapters.course_id = courses.id
            LEFT JOIN lessons ON lessons.chapter_id = chapters.id
            LEFT JOIN lesson_progress AS progress
                ON progress.course_id = courses.id
               AND progress.lesson_id = lessons.id
               AND progress.account_id = ?
            GROUP BY courses.id, courses.title
            ORDER BY courses.updated_at DESC, courses.title
            """,
            (account_id,),
        ).fetchall()
        courses = []
        for row in course_rows:
            next_lesson = connection.execute(
                """
                SELECT lessons.id, lessons.title, chapters.title AS chapter_title
                FROM chapters
                JOIN lessons ON lessons.chapter_id = chapters.id
                LEFT JOIN lesson_progress AS progress
                    ON progress.course_id = chapters.course_id
                   AND progress.lesson_id = lessons.id
                   AND progress.account_id = ?
                WHERE chapters.course_id = ? AND progress.lesson_id IS NULL
                ORDER BY chapters.sort_order, lessons.sort_order
                LIMIT 1
                """,
                (account_id, row["id"]),
            ).fetchone()
            courses.append({
                "id": row["id"],
                "title": row["title"],
                "total_lessons": row["total_lessons"],
                "completed_lessons": row["completed_lessons"],
                "next_lesson": dict(next_lesson) if next_lesson else None,
            })

    return {
        "courses": courses,
        "completed_lessons": sum(item["completed_lessons"] for item in courses),
        "total_lessons": sum(item["total_lessons"] for item in courses),
    }


def create_conversation(account_id: str, first_message: str) -> dict[str, str]:
    conversation_id = str(uuid4())
    timestamp = utc_now()
    title = first_message.strip().replace("\n", " ")[:40] or "新对话"
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO conversations (id, account_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (conversation_id, account_id, title, timestamp, timestamp),
        )
    return {
        "id": conversation_id,
        "account_id": account_id,
        "title": title,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def conversation_belongs_to_account(
    conversation_id: str, account_id: str
) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT 1 FROM conversations
            WHERE id = ? AND account_id = ?
            """,
            (conversation_id, account_id),
        ).fetchone()
    return row is not None


def save_message(
    conversation_id: str,
    account_id: str,
    role: str,
    content: str,
) -> dict[str, str]:
    message_id = str(uuid4())
    timestamp = utc_now()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO chat_messages
                (id, conversation_id, account_id, role, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                conversation_id,
                account_id,
                role,
                content,
                timestamp,
            ),
        )
        connection.execute(
            """
            UPDATE conversations SET updated_at = ?
            WHERE id = ? AND account_id = ?
            """,
            (timestamp, conversation_id, account_id),
        )
    return {
        "id": message_id,
        "conversation_id": conversation_id,
        "account_id": account_id,
        "role": role,
        "content": content,
        "created_at": timestamp,
    }


def list_conversations(account_id: str) -> list[dict[str, str]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, account_id, title, created_at, updated_at
            FROM conversations
            WHERE account_id = ?
            ORDER BY updated_at DESC
            """,
            (account_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_messages(
    conversation_id: str, account_id: str
) -> list[dict[str, str]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, conversation_id, account_id, role, content, created_at
            FROM chat_messages
            WHERE conversation_id = ? AND account_id = ?
            ORDER BY created_at ASC
            """,
            (conversation_id, account_id),
        ).fetchall()
    return [dict(row) for row in rows]


def get_experiment(experiment_id: str) -> dict[str, str] | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM experiments WHERE id = ?",
            (experiment_id,),
        ).fetchone()
    return dict(row) if row else None


def get_experiment_handout(experiment_id: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT filename, content FROM experiment_handouts WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchone()
    return dict(row) if row else None


def get_experiment_handout_name(experiment_id: str) -> str | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT filename FROM experiment_handouts WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchone()
    return row["filename"] if row else None


def save_experiment_handout(experiment_id: str, filename: str, content: bytes) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO experiment_handouts (experiment_id, filename, content, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(experiment_id) DO UPDATE SET
                filename = excluded.filename,
                content = excluded.content,
                updated_at = excluded.updated_at
            """,
            (experiment_id, filename, content, utc_now()),
        )


def delete_experiment_handout(experiment_id: str) -> bool:
    with get_connection() as connection:
        result = connection.execute(
            "DELETE FROM experiment_handouts WHERE experiment_id = ?",
            (experiment_id,),
        )
    return result.rowcount > 0


def save_experiment(
    experiment_id: str,
    title: str,
    description: str,
    guide_title: str,
    objective: str,
    requirements: str,
    tips: str,
    teacher_id: str,
    teacher_name: str,
) -> dict[str, str]:
    timestamp = utc_now()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO experiments (
                id, title, description, guide_title, objective,
                requirements, tips, teacher_id, teacher_name, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                guide_title = excluded.guide_title,
                objective = excluded.objective,
                requirements = excluded.requirements,
                tips = excluded.tips,
                teacher_id = excluded.teacher_id,
                teacher_name = excluded.teacher_name,
                updated_at = excluded.updated_at
            """,
            (
                experiment_id,
                title,
                description,
                guide_title,
                objective,
                requirements,
                tips,
                teacher_id,
                teacher_name,
                timestamp,
            ),
        )
    return get_experiment(experiment_id)


def list_courses() -> list[dict[str, str]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, title, description, updated_at
            FROM courses
            ORDER BY updated_at DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_course_tree(course_id: str) -> dict | None:
    with get_connection() as connection:
        course = connection.execute(
            """
            SELECT id, title, description, updated_at
            FROM courses
            WHERE id = ?
            """,
            (course_id,),
        ).fetchone()
        if not course:
            return None

        chapters = connection.execute(
            """
            SELECT id, title, sort_order
            FROM chapters
            WHERE course_id = ?
            ORDER BY sort_order ASC
            """,
            (course_id,),
        ).fetchall()
        chapter_items = []
        handouts = {
            row["chapter_id"]: row["filename"]
            for row in connection.execute(
                "SELECT chapter_id, filename FROM chapter_handouts WHERE course_id = ?",
                (course_id,),
            ).fetchall()
        }
        previews = {
            row["chapter_id"]: row["filename"]
            for row in connection.execute(
                "SELECT chapter_id, filename FROM chapter_handout_previews WHERE course_id = ? AND content IS NOT NULL",
                (course_id,),
            ).fetchall()
        }
        resources = {
            row["chapter_id"]: row["filename"]
            for row in connection.execute(
                "SELECT chapter_id, filename FROM chapter_resources WHERE course_id = ?", (course_id,)
            ).fetchall()
        }
        for chapter in chapters:
            lessons = connection.execute(
                """
                SELECT *
                FROM lessons
                WHERE chapter_id = ?
                ORDER BY sort_order ASC
                """,
                (chapter["id"],),
            ).fetchall()
            chapter_items.append(
                {
                    "id": chapter["id"],
                    "title": chapter["title"],
                    "handout_name": handouts.get(chapter["id"]),
                    "resources_name": resources.get(chapter["id"]),
                    "preview_name": previews.get(chapter["id"]) or (
                        handouts.get(chapter["id"])
                        if (handouts.get(chapter["id"]) or "").lower().endswith(".pdf")
                        else None
                    ),
                    "lessons": [
                        {
                            "id": lesson["id"],
                            "title": lesson["title"],
                            "lead": lesson["lead"],
                            "concept": lesson["concept"],
                            "syntax_title": lesson["syntax_title"],
                            "code": lesson["code"],
                            "steps": json.loads(lesson["steps"]),
                            "is_coding": bool(lesson["is_coding"]),
                            "practice_code": lesson["practice_code"],
                            "stdin": lesson["stdin"],
                            "quiz_question": lesson["quiz_question"],
                            "quiz_options": json.loads(lesson["quiz_options"]),
                            "quiz_answer": lesson["quiz_answer"],
                            "minutes": lesson["minutes"],
                        }
                        for lesson in lessons
                    ],
                }
            )

    return {
        "id": course["id"],
        "title": course["title"],
        "description": course["description"],
        "updated_at": course["updated_at"],
        "chapters": chapter_items,
    }


def insert_course_chapter(connection: sqlite3.Connection, course_id: str, chapter: dict, sort_order: int) -> None:
    connection.execute(
        "INSERT INTO chapters (id, course_id, title, sort_order) VALUES (?, ?, ?, ?)",
        (chapter["id"], course_id, chapter["title"], sort_order),
    )
    for lesson_index, lesson in enumerate(chapter["lessons"]):
        connection.execute(
            """INSERT INTO lessons (
                id, chapter_id, title, lead, concept, syntax_title,
                code, steps, is_coding, practice_code, stdin,
                quiz_question, quiz_options, quiz_answer, minutes, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (lesson["id"], chapter["id"], lesson["title"], lesson.get("lead", ""),
             lesson.get("concept", ""), lesson.get("syntax_title", ""), lesson.get("code", ""),
             json.dumps(lesson.get("steps", []), ensure_ascii=False), int(lesson.get("is_coding", False)),
             lesson.get("practice_code", ""), lesson.get("stdin", ""), lesson.get("quiz_question", ""),
             json.dumps(lesson.get("quiz_options", []), ensure_ascii=False), lesson.get("quiz_answer", ""),
             int(lesson.get("minutes", 10)), lesson_index),
        )


def save_course_tree_in_connection(connection: sqlite3.Connection, course: dict) -> dict:
    timestamp = utc_now()
    connection.execute(
        """
        INSERT INTO courses (id, title, description, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            updated_at = excluded.updated_at
        """,
        (
            course["id"],
            course["title"],
            course.get("description", ""),
            timestamp,
        ),
    )
    connection.execute("DELETE FROM chapters WHERE course_id = ?", (course["id"],))
    chapter_ids = [chapter["id"] for chapter in course["chapters"]]
    if chapter_ids:
        placeholders = ",".join("?" for _ in chapter_ids)
        connection.execute(
            f"DELETE FROM chapter_handouts WHERE course_id = ? AND chapter_id NOT IN ({placeholders})",
            (course["id"], *chapter_ids),
        )
        connection.execute(
            f"DELETE FROM chapter_handout_previews WHERE course_id = ? AND chapter_id NOT IN ({placeholders})",
            (course["id"], *chapter_ids),
        )
        connection.execute(
            f"DELETE FROM chapter_resources WHERE course_id = ? AND chapter_id NOT IN ({placeholders})",
            (course["id"], *chapter_ids),
        )
    else:
        connection.execute("DELETE FROM chapter_handouts WHERE course_id = ?", (course["id"],))
        connection.execute("DELETE FROM chapter_handout_previews WHERE course_id = ?", (course["id"],))
        connection.execute("DELETE FROM chapter_resources WHERE course_id = ?", (course["id"],))
    for chapter_index, chapter in enumerate(course["chapters"]):
        insert_course_chapter(connection, course["id"], chapter, chapter_index)
    return course


def save_course_tree(course: dict) -> dict:
    with get_connection() as connection:
        save_course_tree_in_connection(connection, course)
    return get_course_tree(course["id"])


def get_chapter_handout(course_id: str, chapter_id: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT filename, content FROM chapter_handouts WHERE course_id = ? AND chapter_id = ?",
            (course_id, chapter_id),
        ).fetchone()
    return dict(row) if row else None


def get_chapter_resources(course_id: str, chapter_id: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT filename, content FROM chapter_resources WHERE course_id = ? AND chapter_id = ?",
            (course_id, chapter_id),
        ).fetchone()
    return dict(row) if row else None


def save_chapter_handout(course_id: str, chapter_id: str, filename: str, content: bytes) -> None:
    with get_connection() as connection:
        connection.execute(
            """INSERT INTO chapter_handouts (course_id, chapter_id, filename, content, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(course_id, chapter_id) DO UPDATE SET
                   filename = excluded.filename, content = excluded.content, updated_at = excluded.updated_at""",
            (course_id, chapter_id, filename, content, utc_now()),
        )
        connection.execute(
            """INSERT INTO chapter_handout_previews (course_id, chapter_id, filename, content, updated_at)
               VALUES (?, ?, '', NULL, ?)
               ON CONFLICT(course_id, chapter_id) DO UPDATE SET
                   filename = '', content = NULL, updated_at = excluded.updated_at""",
            (course_id, chapter_id, utc_now()),
        )


def delete_chapter_handout(course_id: str, chapter_id: str) -> bool:
    with get_connection() as connection:
        result = connection.execute(
            "DELETE FROM chapter_handouts WHERE course_id = ? AND chapter_id = ?",
            (course_id, chapter_id),
        )
        if result.rowcount:
            connection.execute(
                "DELETE FROM chapter_handout_previews WHERE course_id = ? AND chapter_id = ?",
                (course_id, chapter_id),
            )
    return result.rowcount > 0


def get_chapter_handout_preview(course_id: str, chapter_id: str) -> dict | None:
    with get_connection() as connection:
        preview = connection.execute(
            "SELECT filename, content FROM chapter_handout_previews WHERE course_id = ? AND chapter_id = ? AND content IS NOT NULL",
            (course_id, chapter_id),
        ).fetchone()
        if preview:
            return dict(preview)
        original = connection.execute(
            "SELECT filename, content FROM chapter_handouts WHERE course_id = ? AND chapter_id = ?",
            (course_id, chapter_id),
        ).fetchone()
    return dict(original) if original and original["filename"].lower().endswith(".pdf") else None


def save_chapter_handout_preview(course_id: str, chapter_id: str, filename: str, content: bytes) -> None:
    with get_connection() as connection:
        connection.execute(
            """INSERT INTO chapter_handout_previews (course_id, chapter_id, filename, content, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(course_id, chapter_id) DO UPDATE SET
                   filename = excluded.filename, content = excluded.content, updated_at = excluded.updated_at""",
            (course_id, chapter_id, filename, content, utc_now()),
        )


def delete_chapter_handout_preview(course_id: str, chapter_id: str) -> bool:
    with get_connection() as connection:
        result = connection.execute(
            """UPDATE chapter_handout_previews SET filename = '', content = NULL, updated_at = ?
               WHERE course_id = ? AND chapter_id = ? AND content IS NOT NULL""",
            (utc_now(), course_id, chapter_id),
        )
    return result.rowcount > 0
