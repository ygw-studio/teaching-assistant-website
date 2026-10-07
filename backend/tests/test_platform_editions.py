import importlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient


class PlatformEditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.previous_env = {key: os.environ.get(key) for key in ("DATABASE_PATH", "ENABLE_LOCAL_DEMO_ACCESS")}
        os.environ["DATABASE_PATH"] = str(Path(cls.temp_dir.name) / "edition-test.db")
        os.environ["ENABLE_LOCAL_DEMO_ACCESS"] = "false"
        cls.main = importlib.import_module("app.main")
        cls.main.init_database()
        cls.main.classroom.init_classroom()
        from app.database import create_user

        cls.roles = ("student", "teacher", "admin")
        for index, role in enumerate(cls.roles):
            create_user(f"edition-{role}", "EditionTest123!", role, f"测试{role}", phone=f"1390000010{index}")
        cls.client = TestClient(cls.main.app, base_url="http://127.0.0.1:8001", client=("127.0.0.1", 12345))

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        for key, value in cls.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        cls.temp_dir.cleanup()

    def login(self, role, edition=None, **extra):
        return self.client.post("/api/v1/auth/login", json={
            "account_id": f"edition-{role}", "password": "EditionTest123!", **extra,
        }, headers={"X-Platform-Edition": edition or role})

    def test_login_only_accepts_matching_edition(self):
        for role in self.roles:
            for edition in self.roles:
                with self.subTest(role=role, edition=edition):
                    response = self.login(role, edition)
                    self.assertEqual(response.status_code, 200 if role == edition else 401)
                    if role == edition:
                        self.assertEqual(response.json()["user"]["role"], role)

    def test_payload_cannot_override_edition_and_bad_credentials_fail(self):
        self.assertEqual(self.login("admin", "student", expected_role="admin").status_code, 401)
        self.assertEqual(self.login("student", "student", expected_role="admin").status_code, 401)
        self.assertEqual(self.login("teacher", password="wrong-password").status_code, 401)
        self.assertEqual(self.login("student", "unknown").status_code, 422)

    def test_restored_tokens_are_checked_against_the_edition(self):
        for role in self.roles:
            token = self.login(role).json()["access_token"]
            for edition in self.roles:
                with self.subTest(role=role, edition=edition):
                    response = self.client.get("/api/v1/auth/me", headers={
                        "Authorization": f"Bearer {token}", "X-Platform-Edition": edition,
                    })
                    self.assertEqual(response.status_code, 200 if role == edition else 403)

    def test_forged_or_missing_header_does_not_grant_permissions(self):
        token = self.login("student").json()["access_token"]
        for edition in (None, "student", "admin"):
            headers = {"Authorization": f"Bearer {token}"}
            if edition:
                headers["X-Platform-Edition"] = edition
            self.assertEqual(self.client.get("/api/v1/auth/users", headers=headers).status_code, 403)
            self.assertEqual(self.client.get("/api/v1/classroom/events", headers=headers).status_code, 403)
        admin_token = self.login("admin").json()["access_token"]
        self.assertEqual(self.client.get("/api/v1/auth/users", headers={
            "Authorization": f"Bearer {admin_token}", "X-Platform-Edition": "admin",
        }).status_code, 200)

    def test_logout_only_revokes_the_current_session(self):
        tokens = {role: self.login(role).json()["access_token"] for role in self.roles}
        headers = {"Authorization": f"Bearer {tokens['teacher']}", "X-Platform-Edition": "teacher"}
        self.assertEqual(self.client.post("/api/v1/auth/logout", headers=headers).status_code, 204)
        for role in self.roles:
            response = self.client.get("/api/v1/auth/me", headers={
                "Authorization": f"Bearer {tokens[role]}", "X-Platform-Edition": role,
            })
            self.assertEqual(response.status_code, 401 if role == "teacher" else 200)

    def test_editions_never_allow_demo_role_switching(self):
        with patch.dict(os.environ, {"ENABLE_LOCAL_DEMO_ACCESS": "true"}), patch.object(self.main, "APP_ENV", "development"):
            for role in self.roles:
                headers = {"X-Platform-Edition": role}
                self.assertFalse(self.client.get("/api/v1/auth/demo-mode", headers=headers).json()["enabled"])
                self.assertEqual(self.client.post("/api/v1/auth/demo-session", json={"role": role}, headers=headers).status_code, 404)
        self.assertFalse(self.client.get("/api/v1/auth/demo-mode").json()["enabled"])

    def test_existing_api_clients_without_edition_header_still_require_auth(self):
        response = self.client.post("/api/v1/auth/login", json={
            "account_id": "edition-teacher", "password": "EditionTest123!", "expected_role": "teacher",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {response.json()['access_token']}",
        }).json()["role"], "teacher")

    def test_student_accounts_can_be_created_without_a_phone(self):
        token = self.login("admin").json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Platform-Edition": "admin"}
        for index, phone_fields in enumerate(({}, {"phone": ""}, {"phone": "   "})):
            payload = {
                "account_id": f"no-phone-{index}", "password": "AccountTest123!",
                "name": "无需手机号的学生", "role": "student", **phone_fields,
            }
            response = self.client.post("/api/v1/auth/users", json=payload, headers=headers)
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(response.json()["phone"], "")
            result = self.client.post("/api/v1/auth/login", json={
                "account_id": payload["account_id"], "password": payload["password"], "expected_role": "student",
            }, headers={"X-Platform-Edition": "student"})
            self.assertEqual(result.status_code, 200)
        duplicate = self.client.post("/api/v1/auth/users", json={
            "account_id": "no-phone-0", "password": "AccountTest123!", "name": "重复账号", "role": "student",
        }, headers=headers)
        self.assertEqual(duplicate.status_code, 409)
        student_token = self.login("student").json()["access_token"]
        self.assertEqual(self.client.post("/api/v1/auth/users", json=payload, headers={
            "Authorization": f"Bearer {student_token}", "X-Platform-Edition": "student",
        }).status_code, 403)

    def test_optional_phone_still_validates_existing_contact_data(self):
        token = self.login("admin").json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Platform-Edition": "admin"}
        payload = {"account_id": "optional-phone", "password": "AccountTest123!", "name": "可选联系方式", "role": "student"}
        self.assertEqual(self.client.post("/api/v1/auth/users", json={**payload, "phone": "123"}, headers=headers).status_code, 422)
        valid = self.client.post("/api/v1/auth/users", json={**payload, "phone": "13900000200"}, headers=headers)
        self.assertEqual(valid.status_code, 201)
        self.assertEqual(valid.json()["phone"], "13900000200")
        duplicate = self.client.post("/api/v1/auth/users", json={**payload, "account_id": "optional-phone-duplicate", "phone": "13900000200"}, headers=headers)
        self.assertEqual(duplicate.status_code, 409)


if __name__ == "__main__":
    unittest.main()
