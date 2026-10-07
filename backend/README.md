# 知序后端

提供账号、课程、Notebook、课堂习题、学习行为和个人千问接口。前端请求本后端，由后端使用当前用户绑定的百炼 API Key 调用千问。

## 配置

1. 将 `.env.example` 复制为 `.env`。
2. 设置数据库、运行环境和生产加密配置，参考 `.env.example`。
3. 学生在网页个人中心绑定自己的百炼 API Key，不要把学生 Key 写进 `.env` 或 Git。

```env
APP_ENV=development
DATABASE_PATH=E:/codex/教辅网站开发/backend/data/teaching-platform.db
```

说明：

- 前端始终调用知序后端的 `/api/v1/ai/chat`。
- Key 由本人绑定，后端加密保存，不回显或导出。学生须在百炼为所选模型开启免费额度用完即停。
- 个人千问固定使用北京百炼接口，模型编号在个人设置中填写，不允许客户端指定任意服务 URL。
- 个人千问不回退到平台 `AI_*` 或 `DEEPSEEK_*` 配置。

## 启动

```bash
pip install -r requirements.txt
python run.py
```

服务地址：`http://127.0.0.1:8001`；接口文档：`http://127.0.0.1:8001/docs`。

健康检查：`http://127.0.0.1:8001/api/v1/health`

## 在线 Python

学生端通过 `POST /api/v1/execute` 将代码和标准输入发送到后端，
后端使用 Python 3 执行并返回标准输出、错误输出、退出码和耗时。

当前执行器用于开发原型，限制单次运行 10 秒。正式部署时必须将该
接口替换为 Docker 沙箱或 Judge0，禁止直接在主 API 服务器进程所在
系统中执行学生代码。

## 实验指导

教师端“实验管理”页面通过以下接口保存指导内容：

- `GET /api/v1/experiments/{id}`
- `PUT /api/v1/experiments/{id}`

学生打开实验指导抽屉时会读取教师最后发布的版本。

## 聊天记录

聊天和课堂数据保存在 `DATABASE_PATH` 指定的 SQLite 数据库；当前工作区为 `backend/data/teaching-platform.db`：

- `conversations`：账号、会话标题、创建时间、最后交互时间
- `chat_messages`：账号、会话、消息角色、消息内容、精确发送时间

接口从 Bearer 登录凭证获取真实账号，不能只凭前端 account_id 访问他人记录。开发环境可以显式开启本机演示身份，正式环境禁用。

课堂、截止日期、数据采集、清理及安全边界详见 `../docs/课堂习题与个人千问使用说明.md`。
