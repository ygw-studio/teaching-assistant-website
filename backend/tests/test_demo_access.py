import importlib
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from fastapi.testclient import TestClient


class DemoAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.previous_env = {
            key: os.environ.get(key)
            for key in ("DATABASE_PATH", "APP_ENV", "ENABLE_LOCAL_DEMO_ACCESS")
        }
        os.environ["DATABASE_PATH"] = str(Path(cls.temp_dir.name) / "demo-test.db")
        os.environ["APP_ENV"] = "development"
        os.environ["ENABLE_LOCAL_DEMO_ACCESS"] = "true"
        cls.main = importlib.import_module("app.main")
        cls.main.init_database()
        cls.main.classroom.init_classroom()
        cls.client = TestClient(
            cls.main.app,
            base_url="http://127.0.0.1:8001",
            client=("127.0.0.1", 12345),
            headers={"Origin": "http://127.0.0.1:4173"},
        )

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        for key, value in cls.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        cls.temp_dir.cleanup()

    def test_local_demo_sessions_keep_role_permissions(self):
        self.assertEqual(self.client.get("/api/v1/auth/demo-mode").json(), {"enabled": True})
        for role in ("student", "teacher", "admin"):
            response = self.client.post("/api/v1/auth/demo-session", json={"role": role})
            self.assertEqual(response.status_code, 200)
            token = response.json()["access_token"]
            current = self.client.get(
                "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
            )
            self.assertEqual(current.json()["role"], role)

    def test_notebook_api_auth_context_audit_and_production_guard(self):
        token = self.client.post("/api/v1/auth/demo-session", json={"role": "student"}).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"code": "x = 1", "notebook_id": "test-notebook", "cell_id": "cell-1", "resource_id": "scratch", "course_id": "data-structures-python", "lesson_id": "ds-1-1"}
        result = {"outputs": [], "execution_count": 1, "exit_code": 0, "duration_ms": 15, "kernel_reset": False}
        with patch.object(self.main.notebook_pool, "execute", return_value=result) as execute:
            self.assertEqual(self.client.post("/api/v1/notebooks/execute", json=payload).status_code, 401)
            response = self.client.post("/api/v1/notebooks/execute", json=payload, headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(execute.call_args.args[0], ("20250001", "scratch", "test-notebook"))
            with patch.object(self.main, "APP_ENV", "production"):
                self.assertEqual(self.client.post("/api/v1/notebooks/execute", json=payload, headers=headers).status_code, 503)
            with patch.object(self.main, "get_execution_mode", return_value="docker"):
                self.assertEqual(self.client.post("/api/v1/notebooks/execute", json=payload, headers=headers).status_code, 503)
            self.assertEqual(execute.call_count, 1)
        from app.database import get_connection
        import json
        with get_connection() as connection:
            row = connection.execute("SELECT id, metadata FROM audit_events WHERE account_id = ? AND event_type = 'code.executed' ORDER BY created_at DESC LIMIT 1", ("20250001",)).fetchone()
        metadata = json.loads(row["metadata"])
        self.assertEqual(metadata["cell_id"], "cell-1")
        self.assertEqual(metadata["runtime"], "jupyter")
        self.assertEqual(metadata["course_id"], "data-structures-python")
        self.assertTrue(metadata["started_at"])
        with get_connection() as connection:
            connection.execute("DELETE FROM audit_events WHERE id = ?", (row["id"],))

    def test_code_drafts_survive_reload_without_crossing_accounts(self):
        student_token = self.client.post(
            "/api/v1/auth/demo-session", json={"role": "student"}
        ).json()["access_token"]
        teacher_token = self.client.post(
            "/api/v1/auth/demo-session", json={"role": "teacher"}
        ).json()["access_token"]
        admin_token = self.client.post(
            "/api/v1/auth/demo-session", json={"role": "admin"}
        ).json()["access_token"]
        student_headers = {"Authorization": f"Bearer {student_token}"}
        teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        path = "/api/v1/code-drafts/experiment/guess-number"

        self.assertEqual(self.client.get(path, headers=student_headers).status_code, 204)
        first = self.client.put(path, json={"code": "print('你好')", "stdin": "42"}, headers=student_headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["code"], "print('你好')")
        self.assertTrue(first.json()["created_at"])
        self.assertEqual(self.client.get(path, headers=student_headers).json()["stdin"], "42")
        self.main.init_database()
        self.assertEqual(self.client.get(path, headers=student_headers).json()["code"], "print('你好')")
        self.assertEqual(
            self.client.put(path, json={"code": "", "stdin": ""}, headers=student_headers).json()["code"],
            "",
        )
        self.assertEqual(self.client.get(path, headers=teacher_headers).status_code, 403)
        self.assertEqual(self.client.get(path).status_code, 401)

        created = self.client.post("/api/v1/auth/users", json={
            "account_id": "draft-test-student", "password": "TestPass123!", "role": "student",
            "name": "草稿测试学生", "phone": "13900000043",
        }, headers=admin_headers)
        self.assertEqual(created.status_code, 201)
        second_token = self.client.post("/api/v1/auth/login", json={
            "account_id": "draft-test-student", "password": "TestPass123!",
        }).json()["access_token"]
        second_headers = {"Authorization": f"Bearer {second_token}"}
        self.assertEqual(self.client.get(path, headers=second_headers).status_code, 204)
        self.assertEqual(self.client.get(path, headers=student_headers).json()["code"], "")

        lesson_id = self.client.get(
            "/api/v1/courses/data-structures-python", headers=student_headers
        ).json()["chapters"][0]["lessons"][0]["id"]
        lesson_path = f"/api/v1/code-drafts/lesson/{lesson_id}"
        lesson_draft = self.client.put(
            lesson_path, json={"code": "print('lesson')", "stdin": ""}, headers=student_headers
        )
        self.assertEqual(lesson_draft.status_code, 200)
        self.assertEqual(self.client.get(lesson_path, headers=student_headers).json()["code"], "print('lesson')")
        self.assertEqual(self.client.get(lesson_path, headers=second_headers).status_code, 204)

    def test_code_run_records_its_exercise_context(self):
        admin_token = self.client.post(
            "/api/v1/auth/demo-session", json={"role": "admin"}
        ).json()["access_token"]
        created = self.client.post("/api/v1/auth/users", json={
            "account_id": "run-test-student", "password": "TestPass123!", "role": "student",
            "name": "运行测试学生", "phone": "13900000044",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        self.assertEqual(created.status_code, 201)
        student_token = self.client.post("/api/v1/auth/login", json={
            "account_id": "run-test-student", "password": "TestPass123!",
        }).json()["access_token"]
        headers = {"Authorization": f"Bearer {student_token}"}
        lesson_id = self.client.get(
            "/api/v1/courses/data-structures-python", headers=headers
        ).json()["chapters"][0]["lessons"][0]["id"]
        payload = {
            "code": "print('ready')", "stdin": "", "scope": "experiment",
            "resource_id": "guess-number", "course_id": "data-structures-python",
            "lesson_id": lesson_id,
        }
        self.assertEqual(
            self.client.post("/api/v1/execute", json={**payload, "resource_id": None}, headers=headers).status_code,
            422,
        )
        result = self.client.post("/api/v1/execute", json=payload, headers=headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["stdout"].strip(), "ready")

        from app.database import get_connection
        import json

        with get_connection() as connection:
            row = connection.execute(
                "SELECT resource_type, resource_id, metadata FROM audit_events "
                "WHERE account_id = ? AND event_type = 'code.executed'",
                ("run-test-student",),
            ).fetchone()
        self.assertEqual((row["resource_type"], row["resource_id"]), ("experiment", "guess-number"))
        self.assertEqual(json.loads(row["metadata"])["lesson_id"], lesson_id)

    def test_demo_access_is_closed_when_not_local_or_not_enabled(self):
        remote = TestClient(
            self.main.app,
            base_url="http://127.0.0.1:8001",
            client=("203.0.113.5", 12345),
        )
        self.assertEqual(remote.get("/api/v1/auth/demo-mode").json(), {"enabled": False})
        self.assertEqual(
            remote.post("/api/v1/auth/demo-session", json={"role": "admin"}).status_code,
            404,
        )
        remote.close()

        os.environ["ENABLE_LOCAL_DEMO_ACCESS"] = "false"
        try:
            self.assertEqual(self.client.get("/api/v1/auth/demo-mode").json(), {"enabled": False})
            self.assertEqual(
                self.client.post("/api/v1/auth/demo-session", json={"role": "admin"}).status_code,
                404,
            )
        finally:
            os.environ["ENABLE_LOCAL_DEMO_ACCESS"] = "true"

        self.main.APP_ENV = "production"
        try:
            self.assertEqual(self.client.get("/api/v1/auth/demo-mode").json(), {"enabled": False})
            self.assertEqual(
                self.client.post("/api/v1/auth/demo-session", json={"role": "admin"}).status_code,
                404,
            )
        finally:
            self.main.APP_ENV = "development"

    def test_teacher_pdf_handout_is_available_to_student(self):
        teacher_token = self.client.post(
            "/api/v1/auth/demo-session", json={"role": "teacher"}
        ).json()["access_token"]
        student_token = self.client.post(
            "/api/v1/auth/demo-session", json={"role": "student"}
        ).json()["access_token"]
        teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
        student_headers = {"Authorization": f"Bearer {student_token}"}
        path = "/api/v1/experiments/pdf-handout-test"
        guide = {
            "title": "课堂实验",
            "description": "课前准备",
            "guide_title": "实验讲义",
            "objective": "学习 Python",
            "requirements": ["阅读讲义", "运行代码"],
            "tips": "先看左侧",
        }
        self.assertEqual(
            self.client.put(path, json=guide, headers=teacher_headers).status_code, 200
        )
        pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
        upload_path = f"{path}/handout?filename=class.pdf"
        self.assertEqual(
            self.client.put(
                upload_path, content=pdf, headers={**teacher_headers, "Content-Type": "application/pdf"}
            ).status_code,
            200,
        )
        detail = self.client.get(path, headers=student_headers)
        self.assertEqual(detail.json()["handout_name"], "class.pdf")
        download = self.client.get(f"{path}/handout", headers=student_headers)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.headers["content-type"], "application/pdf")
        self.assertEqual(download.content, pdf)
        self.assertEqual(
            self.client.put(
                upload_path, content=pdf, headers={**student_headers, "Content-Type": "application/pdf"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.put(
                upload_path, content=b"not a PDF", headers={**teacher_headers, "Content-Type": "application/pdf"}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.put(
                upload_path, content=pdf + b"x" * (10 * 1024 * 1024), headers={**teacher_headers, "Content-Type": "application/pdf"}
            ).status_code,
            413,
        )
        self.assertEqual(
            self.client.delete(f"{path}/handout", headers=student_headers).status_code,
            403,
        )
        self.assertEqual(
            self.client.delete(f"{path}/handout", headers=teacher_headers).status_code,
            204,
        )
        self.assertIsNone(self.client.get(path, headers=student_headers).json()["handout_name"])
        self.assertEqual(
            self.client.get(f"{path}/handout", headers=student_headers).status_code,
            404,
        )

    def test_data_structure_chapter_and_teacher_handout(self):
        student_token = self.client.post(
            "/api/v1/auth/demo-session", json={"role": "student"}
        ).json()["access_token"]
        teacher_token = self.client.post(
            "/api/v1/auth/demo-session", json={"role": "teacher"}
        ).json()["access_token"]
        student_headers = {"Authorization": f"Bearer {student_token}"}
        teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
        path = "/api/v1/courses/data-structures-python"
        course_response = self.client.get(path, headers=student_headers)
        self.assertEqual(course_response.status_code, 200)
        course = course_response.json()
        self.assertEqual(len(course["chapters"]), 8)
        for item in course["chapters"]:
            chapter_path = f"{path}/chapters/{item['id']}"
            self.assertTrue(item["handout_name"].endswith(".pptx"))
            self.assertTrue(item["preview_name"].endswith(".pdf"))
            self.assertTrue(item["resources_name"].endswith(".zip"))
            self.assertTrue(self.client.get(f"{chapter_path}/handout/preview", headers=student_headers).content.startswith(b"%PDF-"))
            self.assertEqual(self.client.get(f"{chapter_path}/resources", headers=student_headers).status_code, 403)
            resource_response = self.client.get(f"{chapter_path}/resources", headers=teacher_headers)
            self.assertEqual(resource_response.status_code, 200)
            self.assertTrue(resource_response.content.startswith(b"PK"))
            self.assertEqual(resource_response.headers["content-type"], "application/zip")
            self.assertTrue(all(not lesson["quiz_answer"] for lesson in item["lessons"]))
        self.assertEqual(self.client.get(f"{path}/chapters/ds-chapter-2/resources").status_code, 401)
        self.assertEqual(self.client.get(f"{path}/chapters/missing/resources", headers=student_headers).status_code, 403)
        self.assertEqual(self.client.get(f"{path}/chapters/missing/resources", headers=teacher_headers).status_code, 404)
        chapter = course["chapters"][0]
        self.assertEqual(chapter["id"], "ds-chapter-1")
        self.assertEqual(len(chapter["lessons"]), 6)
        self.assertTrue(all(not lesson["quiz_answer"] for lesson in chapter["lessons"]))
        teacher_course = self.client.get(path, headers=teacher_headers).json()
        self.assertTrue(all(lesson["quiz_answer"] in lesson["quiz_options"] for lesson in teacher_course["chapters"][0]["lessons"]))
        self.assertEqual(chapter["handout_name"], "第1章 绪论.pptx")
        self.assertEqual(chapter["preview_name"], "第1章 绪论.pdf")
        handout_path = f"{path}/chapters/ds-chapter-1/handout"
        self.assertTrue(self.client.get(handout_path, headers=student_headers).content.startswith(b"PK"))
        preview_path = f"{handout_path}/preview"
        self.assertTrue(self.client.get(preview_path, headers=student_headers).content.startswith(b"%PDF-"))

        pdf = b"%PDF-1.4\n%%EOF"
        preview_upload = f"{preview_path}?filename=updated.pdf"
        self.assertEqual(self.client.put(preview_upload, content=pdf, headers={**student_headers, "Content-Type": "application/pdf"}).status_code, 403)
        self.assertEqual(self.client.put(preview_upload, content=b"bad", headers={**teacher_headers, "Content-Type": "application/pdf"}).status_code, 400)
        self.assertEqual(self.client.put(preview_upload, content=pdf, headers={**teacher_headers, "Content-Type": "application/pdf"}).status_code, 200)
        self.assertEqual(self.client.get(preview_path, headers=student_headers).content, pdf)

        pptx = self.client.get(handout_path, headers=student_headers).content
        pptx_headers = {**teacher_headers, "Content-Type": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}
        self.assertEqual(self.client.put(f"{handout_path}?filename=new.pptx", content=pptx, headers=pptx_headers).status_code, 200)
        self.assertIsNone(self.client.get(path, headers=student_headers).json()["chapters"][0]["preview_name"])
        self.assertEqual(self.client.get(preview_path, headers=student_headers).status_code, 404)
        self.assertEqual(self.client.put(preview_upload, content=pdf, headers={**teacher_headers, "Content-Type": "application/pdf"}).status_code, 200)
        self.assertEqual(self.client.get(path, headers=student_headers).json()["chapters"][0]["preview_name"], "updated.pdf")
        self.assertEqual(self.client.delete(preview_path, headers=student_headers).status_code, 403)
        self.assertEqual(self.client.delete(preview_path, headers=teacher_headers).status_code, 204)
        self.main.init_database()
        self.assertIsNone(self.client.get(path, headers=student_headers).json()["chapters"][0]["preview_name"])
        self.assertEqual(self.client.get(preview_path, headers=student_headers).status_code, 404)

        upload_path = f"{handout_path}?filename=teacher.pdf"
        upload_headers = {**teacher_headers, "Content-Type": "application/pdf"}
        self.assertEqual(self.client.put(upload_path, content=pdf, headers={**student_headers, "Content-Type": "application/pdf"}).status_code, 403)
        self.assertEqual(self.client.put(upload_path, content=b"bad", headers=upload_headers).status_code, 400)
        self.assertEqual(self.client.put(upload_path, content=pdf, headers=upload_headers).status_code, 200)
        self.assertEqual(self.client.get(handout_path, headers=student_headers).content, pdf)
        updated = self.client.get(path, headers=teacher_headers).json()
        self.assertEqual(updated["chapters"][0]["handout_name"], "teacher.pdf")
        self.assertEqual(updated["chapters"][0]["preview_name"], "teacher.pdf")
        self.assertEqual(self.client.get(preview_path, headers=student_headers).content, pdf)
        updated["title"] = "教师修订的数据结构课程"
        self.assertEqual(self.client.put(path, json=updated, headers=teacher_headers).status_code, 200)
        self.assertEqual(self.client.get(path, headers=student_headers).json()["chapters"][0]["handout_name"], "teacher.pdf")
        self.assertEqual(self.client.delete(handout_path, headers=student_headers).status_code, 403)
        self.assertEqual(self.client.delete(handout_path, headers=teacher_headers).status_code, 204)
        self.main.init_database()
        preserved = self.client.get(path, headers=student_headers).json()
        self.assertIsNone(preserved["chapters"][0]["handout_name"])
        self.assertEqual(preserved["title"], "教师修订的数据结构课程")

    def test_quiz_progress_survives_reload_and_is_account_scoped(self):
        student_token = self.client.post(
            "/api/v1/auth/demo-session", json={"role": "student"}
        ).json()["access_token"]
        teacher_token = self.client.post(
            "/api/v1/auth/demo-session", json={"role": "teacher"}
        ).json()["access_token"]
        admin_token = self.client.post(
            "/api/v1/auth/demo-session", json={"role": "admin"}
        ).json()["access_token"]
        student_headers = {"Authorization": f"Bearer {student_token}"}
        teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        course_path = "/api/v1/courses/data-structures-python"
        lesson = self.client.get(course_path, headers=teacher_headers).json()["chapters"][0]["lessons"][0]
        quiz_path = f"{course_path}/lessons/{lesson['id']}/quiz"
        progress_path = f"{course_path}/progress"
        wrong_answer = next(option for option in lesson["quiz_options"] if option != lesson["quiz_answer"])

        self.assertEqual(self.client.get(progress_path, headers=student_headers).json(), [])
        self.assertEqual(self.client.post(quiz_path, json={"answer": "not-an-option"}, headers=student_headers).status_code, 400)
        wrong = self.client.post(quiz_path, json={"answer": wrong_answer}, headers=student_headers)
        self.assertEqual(wrong.status_code, 200)
        self.assertFalse(wrong.json()["correct"])
        self.assertFalse(wrong.json()["completed"])
        self.assertEqual(wrong.json()["attempt_count"], 1)
        self.assertEqual(self.client.get(progress_path, headers=student_headers).json(), [])

        correct = self.client.post(quiz_path, json={"answer": lesson["quiz_answer"]}, headers=student_headers)
        self.assertEqual(correct.status_code, 200)
        self.assertTrue(correct.json()["correct"])
        self.assertTrue(correct.json()["completed"])
        self.assertEqual(correct.json()["attempt_count"], 2)
        completed_at = correct.json()["completed_at"]
        self.assertEqual(self.client.get(progress_path, headers=student_headers).json(), [
            {"lesson_id": lesson["id"], "completed_at": completed_at}
        ])
        self.main.init_database()
        self.assertEqual(self.client.get(progress_path, headers=student_headers).json()[0]["completed_at"], completed_at)

        created = self.client.post("/api/v1/auth/users", json={
            "account_id": "quiz-test-student", "password": "TestPass123!", "role": "student",
            "name": "独立学生", "phone": "13900000042",
        }, headers=admin_headers)
        self.assertEqual(created.status_code, 201)
        second_token = self.client.post("/api/v1/auth/login", json={
            "account_id": "quiz-test-student", "password": "TestPass123!",
        }).json()["access_token"]
        second_headers = {"Authorization": f"Bearer {second_token}"}
        self.assertEqual(self.client.get(progress_path, headers=second_headers).json(), [])
        self.assertEqual(self.client.post(quiz_path, json={"answer": lesson["quiz_answer"]}, headers=teacher_headers).status_code, 403)

        from app.database import create_conversation, get_connection, save_message, write_audit_event

        write_audit_event("20250001", "code.executed", "python", metadata={"exit_code": 0, "duration_ms": 10})
        conversation = create_conversation("20250001", "学习问题")
        save_message(conversation["id"], "20250001", "user", "为什么这样运行？")
        overview_response = self.client.get("/api/v1/students/me/overview", headers=student_headers)
        self.assertEqual(overview_response.status_code, 200)
        overview = overview_response.json()
        self.assertGreaterEqual(overview["total_lessons"], 6)
        self.assertEqual(overview["completed_lessons"], 1)
        self.assertEqual(set(overview), {"courses", "completed_lessons", "total_lessons"})
        course_summary = next(item for item in overview["courses"] if item["id"] == "data-structures-python")
        self.assertEqual(course_summary["completed_lessons"], 1)
        self.assertNotEqual(course_summary["next_lesson"]["id"], lesson["id"])
        second_overview = self.client.get("/api/v1/students/me/overview", headers=second_headers).json()
        self.assertEqual(second_overview["completed_lessons"], 0)
        self.assertEqual(set(second_overview), {"courses", "completed_lessons", "total_lessons"})
        self.assertEqual(self.client.get("/api/v1/students/me/overview", headers=teacher_headers).status_code, 403)

        with get_connection() as connection:
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM audit_events WHERE account_id = ? AND event_type = 'code.executed'",
                ("20250001",),
            ).fetchone()[0], 1)
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM chat_messages WHERE account_id = ? AND role = 'user'",
                ("20250001",),
            ).fetchone()[0], 1)
            rows = connection.execute(
                "SELECT account_id, course_id, chapter_id, lesson_id, answer, is_correct, created_at "
                "FROM lesson_quiz_attempts WHERE lesson_id = ? ORDER BY created_at, rowid",
                (lesson["id"],),
            ).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual([row["is_correct"] for row in rows], [0, 1])
        self.assertTrue(all(row["created_at"] and row["course_id"] == "data-structures-python" for row in rows))


if __name__ == "__main__":
    unittest.main()
