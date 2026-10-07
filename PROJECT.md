# 知序编程学习平台项目说明

> 本文是早期原型的历史说明，部分登录、AI 配置、端口和数据存储描述已经过时。当前启动方式以根目录 README.md 为准，三版本入口、课堂习题和个人千问说明见 docs/。

## 项目定位

本项目是一个高校编程教学辅助平台原型，名称为“知序”。平台面向学生、教师和管理员三类角色，核心目标是把课程学习、在线编程练习、AI 助教、实验指导和教学管理放到同一个系统中。

当前项目已经具备前后端基本联通能力：

- 学生端：课程首页、课程学习、在线 Python 练习、学习数据、AI 助教。
- 教师端：教学概览、课程管理、实验管理、作业管理、学生记录。
- 管理员端：平台概览、用户管理、角色权限、系统设置。
- 后端接口：健康检查、Python 代码执行、实验指导保存与读取、AI 对话、聊天记录保存。

## 技术栈

### 前端

- React
- Vite
- Lucide React 图标库
- 原生 CSS 样式

前端目录：`frontend/`

### 后端

- Python
- FastAPI
- Uvicorn
- SQLite
- httpx
- python-dotenv

后端目录：`backend/`

## 目录结构

```text
.
├── frontend/              # 前端 React + Vite 应用
│   ├── src/
│   │   ├── App.jsx        # 主要页面、角色切换和交互逻辑
│   │   ├── styles.css     # 页面样式
│   │   └── api/           # 前端接口封装
│   ├── package.json
│   └── vite.config.js
├── backend/               # 后端 FastAPI 服务
│   ├── app/
│   │   ├── main.py        # API 路由和业务入口
│   │   └── database.py    # SQLite 数据库读写
│   ├── data/              # 本地数据库文件，已被忽略提交
│   ├── runtime/           # 在线代码执行临时目录，已被忽略提交
│   ├── requirements.txt
│   └── run.py
├── tools/                 # 辅助工具目录
├── src/                   # 当前保留目录，后续可根据实际用途整理
├── .gitignore
└── PROJECT.md
```

## 启动方式

### 1. 启动后端

进入后端目录：

```bash
cd backend
pip install -r requirements.txt
python run.py
```

默认服务地址：

```text
http://127.0.0.1:8000
```

健康检查：

```text
http://127.0.0.1:8000/api/v1/health
```

### 2. 启动前端

进入前端目录：

```bash
cd frontend
npm install
npm run dev
```

默认访问地址：

```text
http://localhost:5173
```

前端默认请求后端地址：

```text
http://localhost:8000/api/v1
```

如需修改后端地址，可在前端环境变量中设置：

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## 后端配置

AI 助教现在走平台统一管理的后端接口。后端启动前，需要在 `backend/.env` 中配置：

```env
AI_PROVIDER_NAME=知序平台AI服务
AI_API_URL=https://api.deepseek.com/chat/completions
AI_API_KEY=你的平台统一AI密钥
AI_MODEL=deepseek-v4-flash
```

说明：

- 前端始终调用知序后端的 `/api/v1/ai/chat`。
- 平台统一在后端保存和使用 API Key，学生端不直接接触 Key。
- 如需切换到其他兼容 OpenAI Chat Completions 协议的模型服务，只需修改 `AI_API_URL`、`AI_API_KEY`、`AI_MODEL`。
- 为兼容旧版本，后端仍支持回退读取 `DEEPSEEK_API_URL`、`DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL`。

如果没有配置 `AI_API_KEY`，其他接口仍可使用，但 AI 对话接口会返回“后端尚未配置平台 AI 接口密钥”。

## 主要接口

### 基础接口

- `GET /api/v1/health`：后端健康检查。

### 在线代码执行

- `POST /api/v1/execute`

请求内容：

```json
{
  "code": "print('hello')",
  "language": "python",
  "stdin": ""
}
```

返回内容包括标准输出、错误输出、退出码和运行耗时。

注意：当前执行器是开发原型，会在后端所在系统中直接运行学生提交的 Python 代码，并限制单次运行 10 秒。正式部署前必须替换为 Docker 沙箱、Judge0 或其他隔离执行环境。

### 实验指导

- `GET /api/v1/experiments/{experiment_id}`：读取实验指导。
- `PUT /api/v1/experiments/{experiment_id}`：教师保存并发布实验指导。

教师端“实验管理”保存后，学生端在线练习页面可读取对应实验指导。

### AI 助教

- `POST /api/v1/ai/chat`：发送学生问题并获取 AI 回复。
- `GET /api/v1/ai/conversations/{account_id}`：读取某个账号的会话列表。
- `GET /api/v1/ai/conversations/{account_id}/{conversation_id}/messages`：读取某个会话的消息记录。

聊天记录保存在：

```text
backend/data/chat_records.db
```

### AI 助教首次开通需求

后续 AI 助教应增加“首次打开注册/开通”流程：

1. 学生第一次打开 AI 助教时，先显示注册或开通界面。
2. 学生只需要注册或填写本平台的学习账号，不需要自己去大模型平台复制 API Key。
3. 平台后台使用统一配置的大模型 API Key 调用 DeepSeek、通义千问等模型服务。
4. 每次学生向 AI 助教发送问题时，后端同时完成两件事：
   - 将学生问题、课程上下文和必要历史记录发送给大模型。
   - 将学生账号、会话、学生问题、AI 回复、时间等完整保存到后台数据库。
5. 教师端后续可按学生账号查看 AI 助教互动记录，用于了解学生学习问题和辅导过程。

推荐调用链路：

```text
学生浏览器
  -> 知序后端 API
  -> 大模型服务
  -> 知序后端保存聊天记录
  -> 返回 AI 回复给学生
```

注意：不要让前端直接保存或调用平台的大模型 API Key。API Key 应只放在后端环境变量或安全配置中，前端只提交学生账号、问题内容和会话信息。

## 当前账号与权限状态

当前前端是演示登录模式，不是真实认证系统：

- 学生演示账号：`20250001`
- 教师演示账号：`T2025001`
- 管理员演示账号：`admin`
- 密码：演示环境中可输入任意内容

登录信息保存在浏览器 `localStorage` 中：

- `auth_user`
- `account_id`
- `access_token`

后续接入正式登录系统时，应改为后端签发 JWT，并由后端根据真实账号与角色判断权限。

## 数据存储

当前使用 SQLite 保存聊天记录和实验指导。

数据库初始化逻辑位于：

```text
backend/app/database.py
```

主要数据表：

- `conversations`：AI 对话会话。
- `chat_messages`：AI 对话消息。
- `experiments`：教师发布的实验指导。

`backend/data/` 已在 `.gitignore` 中忽略，避免把本地数据库提交到代码仓库。

## 开发重点

### 前端修改入口

- 页面结构和主要交互：`frontend/src/App.jsx`
- 全局样式：`frontend/src/styles.css`
- 后端请求封装：`frontend/src/api/`

如果继续扩展功能，建议逐步把 `App.jsx` 中的大组件拆分到独立文件，避免单文件过大。

### 后端修改入口

- API 路由和业务逻辑：`backend/app/main.py`
- 数据库连接和数据表操作：`backend/app/database.py`

如果继续扩展用户、课程、作业等真实业务，建议新增独立模块，不要把所有接口都继续堆在 `main.py` 中。

## 已知限制

- 登录与权限仍是前端演示逻辑，没有真实鉴权。
- 在线 Python 执行器尚未沙箱隔离，不适合生产环境。
- AI 助教依赖外部模型服务和有效 API Key。
- AI 助教首次注册/开通流程尚未实现，目前仍使用演示账号直接聊天。
- 课程、作业、学习数据多数仍是前端静态演示数据。
- 教师端和管理员端部分页面还是功能原型，尚未全部接入真实后端。
- 本地 README 文件可能存在中文编码显示问题，建议后续统一保存为 UTF-8。

## 后续建议

1. 接入正式用户体系，完成学生、教师、管理员的真实登录和权限控制。
2. 增加 AI 助教首次注册/开通界面，并把开通状态与学生账号绑定。
3. 后端统一管理大模型 API Key，支持后续切换 DeepSeek、通义千问等模型服务。
4. 教师端增加 AI 互动记录查看页面，可按学生、课程、时间筛选。
5. 将在线代码执行改造为安全沙箱。
6. 为课程、章节、知识点、作业和提交记录设计后端数据表。
7. 拆分前端页面组件，降低 `App.jsx` 维护压力。
8. 增加后端接口测试和前端关键流程测试。
9. 整理并统一所有 Markdown 文件编码为 UTF-8。
