# 知序教学辅助网站

知序是一个面向高校 Python 教学场景的教学辅助网站，包含学生版、教师版、管理员版三个独立入口和工作台，共用后端与数据库，不在学生登录页提供其他身份的切换入口。

## 技术栈

- 前端：React + Vite
- 后端：FastAPI
- 数据库：SQLite
- AI 助教：兼容 OpenAI Chat Completions 协议的中文大模型接口
- 在线 Python：开发阶段使用后端所在机器的 Python，正式上线建议接入 Docker 沙箱

## 目录结构

```text
frontend/  前端项目
backend/   后端项目
docs/      测试报告与交接文档
tools/     冒烟测试和辅助脚本
```

## 本地启动

首次下载：

```powershell
git clone https://github.com/ygw-studio/teaching-assistant-website.git
cd teaching-assistant-website
```

先安装 Python 和 Node.js，然后在项目根目录分别打开两个终端。以下安装步骤用于新下载的项目；已有 `.env` 不要覆盖。

终端一，安装依赖并启动后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
$env:ENABLE_LOCAL_DEMO_ACCESS='false'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

终端二，安装依赖并启动前端：

```powershell
cd frontend
npm ci
npm run build
npm run preview -- --host 127.0.0.1 --port 4173 --strictPort
```

本地访问地址：

```text
学生版：http://127.0.0.1:4173/student
教师版：http://127.0.0.1:4173/teacher
管理员版：http://127.0.0.1:4173/admin
```

旧的根地址会进入学生版。每个入口仅接受对应身份的账号，可在不同标签页分别登录三个版本。

后端接口文档：

```text
http://127.0.0.1:8001/docs
```

## 测试账号

当前开发电脑另外创建了学生体验账号 `123456`，密码为 `123456`。该账号属于本地数据库，不会随源码上传；新下载的项目请使用下方首次初始化账号。原开发数据库及学习记录不受影响。

以下是开发数据库首次初始化的默认账号；已有账号和密码不会因为本次版本拆分而重置。上线前必须修改默认密码。

| 身份 | 账号 | 密码 |
| --- | --- | --- |
| 学生 | `20250001` | `Student@2025` |
| 教师 | `T2025001` | `Teacher@2025` |
| 管理员 | `admin` | `Admin@2025` |

## 测试

```powershell
.\backend\.venv\Scripts\python.exe .\tools\smoke_check.py
```

## 开发说明

继续开发前建议先阅读：

- `docs/同学接手开发交接说明.md`
- `backend/DEPLOYMENT.md`
- `docs/测试阶段性成果报告.md`

## 注意事项

- 本仓库保存源码、测试、教程图与课程资源，不包含现有账号数据、学生学习记录或个人 API Key；新环境会初始化独立数据库及默认课程
- 不要提交 `backend/.env`、数据库文件、运行日志、虚拟环境和 `node_modules`
- 学生在个人中心绑定自己的百炼 API Key，后端加密保存，接口不返回明文密钥；不要放进前端配置或提交到仓库
- 校内试运行前建议启用 Docker 沙箱运行学生代码
