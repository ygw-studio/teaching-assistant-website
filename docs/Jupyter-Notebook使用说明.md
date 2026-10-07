# Jupyter Notebook 课堂实践

在线练习现在采用左侧讲义、右侧 Notebook 的布局。Python 语言没有更换，右侧执行方式改为真实的 IPython/Jupyter 内核。

## 学生操作

- 点击“代码”或“文字”添加单元格，文字支持 Markdown 预览。
- 单元格的播放按钮、Shift+Enter 或 Ctrl+Enter 运行当前代码；页面顶部“运行全部”按顺序执行，遇到错误停止。
- 同一个笔记本中的单元格共享变量，输出和 matplotlib 图表显示在各自单元格下方。
- “标准输入”仍采用每行一次输入，运行 input() 前填写；输入不足会显示 EOFError，不会无限等待。
- 修改的单元格结构和代码自动存入当前账号原有的 code_drafts 表。旧 Python 草稿会转为一个单元格，不直接丢弃。
- 文件菜单支持导入、导出 .ipynb；导出包含当前输出。为控制数据库体积，自动草稿只存代码和文字，不存图表输出。
- 重启内核清空变量。刷新页面会开启新的内核会话，已保存的代码还在，但需重新运行才能恢复变量。

## 后端记录与限制

每次单元格运行写入 audit_events，记录账号、课程、知识点、练习、Notebook 标识、单元格标识、执行次数、开始时间、耗时及退出状态。

内核按登录账号、练习标识与会话标识隔离；最多同时启动 8 个，闲置约 10 分钟回收。单次执行沿用 EXECUTION_TIMEOUT_SECONDS，超时或输出超过 2 MB 会终止内核。

当前真实内核仅允许 APP_ENV=development 且 CODE_EXECUTION_MODE=local。本机运行不等于安全沙箱，学生代码仍可能访问本机文件；生产或 Docker 模式下接口会拒绝启动本机内核。学校服务器上线前需另外配置隔离的 Jupyter 容器或 JupyterHub，不能把本机内核直接暴露给学生。

## 验证命令

```powershell
cd backend
.venv/Scripts/python.exe -m unittest discover -s tests -v
cd ../frontend
npm test
npm run build
```

运行通信使用官方 [Jupyter Client](https://jupyter-client.readthedocs.io/en/latest/api/jupyter_client.html) 的内核管理与 execute_interactive 接口，没有把网页直接连接到无认证的 Jupyter 服务。
