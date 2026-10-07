from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ["DATABASE_PATH"] = str(Path(temp_dir) / "phone-binding.db")
        os.environ["APP_ENV"] = "development"
        os.environ["SEED_DEMO_USERS"] = "true"

        from app.main import app

        client = TestClient(app)
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "account_id": "admin",
                "password": "Admin@2025",
                "expected_role": "admin",
            },
        )
        assert login_response.status_code == 200, login_response.text
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        first_response = client.post(
            "/api/v1/auth/users",
            headers=headers,
            json={
                "account_id": "20259901",
                "password": "Student@2025",
                "role": "student",
                "name": "测试学生一",
                "phone": "13800138000",
                "detail": "临时测试账号",
            },
        )
        assert first_response.status_code == 201, first_response.text
        assert first_response.json()["phone"] == "13800138000"

        duplicate_response = client.post(
            "/api/v1/auth/users",
            headers=headers,
            json={
                "account_id": "20259902",
                "password": "Student@2025",
                "role": "student",
                "name": "测试学生二",
                "phone": "13800138000",
                "detail": "临时测试账号",
            },
        )
        assert duplicate_response.status_code == 409, duplicate_response.text
        assert "手机号" in duplicate_response.json()["detail"]

    print("[OK] 手机号一人一号绑定校验通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
