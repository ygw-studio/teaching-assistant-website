from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request


BASE_URL = "http://127.0.0.1:8001/api/v1"


def request(method: str, path: str, body: dict | None = None, token: str | None = None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body else None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = resp.read().decode("utf-8")
            return resp.status, json.loads(text) if text else None
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        return exc.code, text


def login(account_id: str, password: str, role: str) -> dict:
    status, data = request(
        "POST",
        "/auth/login",
        {
            "account_id": account_id,
            "password": password,
            "expected_role": role,
        },
    )
    if status != 200 or not isinstance(data, dict):
        raise RuntimeError(f"{role} login failed: {status} {data}")
    return data


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    try:
        status, health = request("GET", "/health")
        results.append(("后端健康检查", status == 200 and health == {"status": "ok"}, str(health)))

        student = login("20250001", "Student@2025", "student")
        teacher = login("T2025001", "Teacher@2025", "teacher")
        admin = login("admin", "Admin@2025", "admin")
        results.append(("学生登录", True, student["user"]["name"]))
        results.append(("教师登录", True, teacher["user"]["name"]))
        results.append(("管理员登录", True, admin["user"]["name"]))

        status, course = request("GET", "/courses/python-basic", token=student["access_token"])
        ok_course = status == 200 and isinstance(course, dict) and len(course.get("chapters", [])) > 0
        course_msg = course.get("title", "") if isinstance(course, dict) else str(course)
        results.append(("学生读取课程", ok_course, course_msg))

        status, users = request("GET", "/auth/users", token=admin["access_token"])
        results.append(("管理员查看账号", status == 200 and isinstance(users, list), f"{len(users) if isinstance(users, list) else 0} 个账号"))

        status, forbidden = request("GET", "/auth/users", token=student["access_token"])
        results.append(("学生权限隔离", status == 403, f"HTTP {status}"))

        status, experiment = request("GET", "/experiments/guess-number", token=teacher["access_token"])
        ok_experiment = status == 200 and isinstance(experiment, dict) and bool(experiment.get("guide_title"))
        exp_msg = experiment.get("guide_title", "") if isinstance(experiment, dict) else str(experiment)
        results.append(("实验指导读取", ok_experiment, exp_msg))

        status, execution = request(
            "POST",
            "/execute",
            {
                "language": "python",
                "code": 'for i in range(1, 4): print(f"这是第 {i} 次循环")',
                "stdin": "",
            },
            token=student["access_token"],
        )
        stdout = execution.get("stdout", "") if isinstance(execution, dict) else ""
        ok_execute = status == 200 and isinstance(execution, dict) and execution.get("exit_code") == 0 and "这是第 1 次循环" in stdout
        results.append(("在线 Python 中文输出", ok_execute, stdout.strip().replace("\n", " / ")))

    except Exception as exc:  # noqa: BLE001
        results.append(("自检脚本异常", False, str(exc)))

    for name, ok, detail in results:
        mark = "OK" if ok else "FAIL"
        print(f"[{mark}] {name}: {detail}")

    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
