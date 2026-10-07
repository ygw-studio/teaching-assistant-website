# 知序前端

高校 Python 教学辅助平台的前端应用，包含学生端、教师端和管理员端页面。

## 技术栈

- React
- Vite
- Lucide React

## 本地启动

```bash
npm install
npm run dev
```

开发地址：`http://localhost:5173`

前端会请求后端的 `/api/v1` 接口。请先启动 `../backend`，并在 `.env` 中配置：

```env
VITE_API_BASE_URL=http://localhost:8001/api/v1
```

上线部署时，把 `VITE_API_BASE_URL` 改成正式域名对应的 API 地址，例如：

```env
VITE_API_BASE_URL=https://teach.example.edu.cn/api/v1
```
