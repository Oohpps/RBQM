# RBQM 中心数据风险管理平台

这是一个面向临床研究数据管理（DM）视角的 RBQM 页面平台，用于上传临床研究数据、预览并映射字段、计算 KRI、识别风险信号、排序中心风险，并生成行动跟踪与导出文件。

当前项目采用：

- 后端：FastAPI
- 前端：Vue 3 + TypeScript + Vite
- 数据处理：Python / pandas

## 项目结构

```text
backend/              FastAPI 后端接口与静态前端托管
rbqm/                 RBQM 领域逻辑、数据读取、指标计算、导出
app.py                兼容入口，继续 re-export RBQM 公共能力
frontend/             Vue 3 + TypeScript 前端源码
frontend/src/         Vue 页面、组件、API 封装、配置和类型
frontend/assets/      前端静态资产，例如 rbqm-logo.png
frontend/dist/        Vite build 后生成的静态产物，由后端托管
tests/                后端逻辑回归测试
requirements.txt      Python 运行依赖
```

`frontend/dist/` 是生成目录，不提交到仓库。给最终用户发包前，需要由开发者先执行前端 build。

## 用户启动方式

最终用户电脑只需要 Python 环境，不需要 Node.js。

开发者提前构建好 `frontend/dist/` 后，用户在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

然后在浏览器打开：

```text
http://127.0.0.1:8000
```

## 开发者前端构建

开发者机器需要安装 Node.js。首次安装依赖并构建：

```powershell
cd frontend
npm.cmd install
npm.cmd run build
```

构建成功后会生成：

```text
frontend/dist/
```

后端会托管这个目录中的静态文件。前端请求后端接口时使用同源相对路径，例如 `/api/state`、`/api/upload/preview`、`/api/upload/commit`，因此用户启动后端后即可直接访问完整页面。

开发调试前端时可运行：

```powershell
cd frontend
npm.cmd run dev
```

## 后端启动

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

后端 API 与生产前端静态页面使用同一个服务地址。

## 验证命令

后端语法检查：

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py backend\main.py
```

后端回归测试：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_field_mapping tests.test_kri_switches
```

前端类型检查与生产构建：

```powershell
cd frontend
npm.cmd run build
```

## 主要功能

- 上传 CSV、XLSX、XLS 临床研究数据文件
- 上传后先预览文件，再通过字段映射向导明确指定数据域和字段
- 支持使用内置示例数据快速预览
- 计算中心级 KRI 指标和风险评分
- 开关单个 KRI 指标或整体关闭 KRI 阈值评分
- 按中心风险排序
- 生成风险信号清单和行动跟踪表
- 导出 RBQM 审查包 Excel
- 支持中英文切换和浅色/深色主题

## 推荐数据字段

应用支持较宽松的列名匹配，但真实项目建议通过字段映射向导显式指定字段。

建议上传数据包含以下字段：

- 受试者：`subject_id`, `site_id`, `country`, `status`
- 访视 / EDC：`subject_id`, `site_id`, `visit_date`, `data_entry_date`, `form_status`
- Query：`subject_id`, `site_id`, `query_status`, `opened_date`, `closed_date`, `age_days`
- AE / SAE：`subject_id`, `site_id`, `serious`, `severity`, `outcome`, `start_date`
- 实验室：`subject_id`, `site_id`, `result`, `lln`, `uln`, `reviewed`
- 方案偏离：`subject_id`, `site_id`, `severity`, `status`, `deviation_date`

如果未上传文件，系统会默认使用内置示例数据。

## 打包注意事项

发给最终用户前，应包含：

- Python 后端代码：`backend/`, `rbqm/`, `app.py`
- 构建后的前端产物：`frontend/dist/`
- 运行依赖：`requirements.txt`
- 必要文档：`README.md`

不要打包：

- `.venv/`
- `frontend/node_modules/`
- 上传的真实临床研究数据
- 本地生成的 Excel 导出文件
