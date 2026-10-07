# Internal Trial Deployment

This project is ready for an internal school-network trial after the steps
below. It is not ready to expose directly to the public internet without a
reverse proxy, HTTPS, monitoring, and regular security review.

## 1. Server configuration

Create `backend/.env` from `.env.example`. For production, set at least:

```env
APP_ENV=production
DATABASE_PATH=D:/TeachingAssistant/data/teaching-platform.db
CORS_ORIGINS=https://teach.example.edu.cn
SESSION_TTL_HOURS=8
BOOTSTRAP_ADMIN_ACCOUNT=admin
BOOTSTRAP_ADMIN_PASSWORD=replace-with-a-strong-one-time-password
BOOTSTRAP_ADMIN_NAME=System Administrator
CODE_EXECUTION_MODE=docker
CODE_RUNNER_IMAGE=python:3.12-alpine
EXECUTION_TIMEOUT_SECONDS=10
```

`DATABASE_PATH` must point to a server data disk, outside the deployed source
directory. Back up that directory independently from the code.

The bootstrap admin is created only when it does not already exist. After the
first successful login, remove `BOOTSTRAP_ADMIN_PASSWORD` from the server
environment.

## 2. Code runner

Never set `CODE_EXECUTION_MODE=local` in production. Student code must run in
Docker, with Docker installed on the server and the runner image pre-pulled:

```powershell
docker pull python:3.12-alpine
```

The current runner disables network access, uses a read-only container file
system, runs as an unprivileged user, caps memory/CPU/processes, and terminates
code that exceeds the configured timeout. Test this from a non-admin student
account before opening the platform to a class.

## 3. Start services

Build the frontend, then serve `frontend/dist` through Nginx/IIS. Keep FastAPI
bound to `127.0.0.1` and proxy `/api/` to it. Configure HTTPS on the reverse
proxy; do not expose Uvicorn directly to the internet.

```powershell
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

## 4. Account setup

Development only seeds these local trial accounts:

| Role | Account | Password |
| --- | --- | --- |
| Student | `20250001` | `Student@2025` |
| Teacher | `T2025001` | `Teacher@2025` |
| Administrator | `admin` | `Admin@2025` |

Production does not seed these accounts. After the bootstrap administrator
signs in, create school accounts from the administrator **User Management**
screen. `POST /api/v1/auth/users` is also available for approved batch-import
tools.

## 5. Backup and monitoring

Create a daily scheduled task that runs:

```powershell
cd backend
python scripts/backup_database.py
```

Keep backup copies on a separate disk or server. Before each release, verify
the health endpoint, login, course editing permissions, AI chat, and Docker
code execution with one account for each role.
