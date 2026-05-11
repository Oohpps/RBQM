# RBQM 中央数据风险管理平台

这是一个面向临床研究数据管理（DM）视角的 RBQM 页面平台，用于上传临床研究数据、计算 KRI、识别风险信号、排序中心风险，并生成行动跟踪与导出文件。

当前项目采用：

- 后端：FastAPI
- 前端：HTML + CSS + JavaScript
- 数据处理：Python / pandas

## 项目结构

```text
backend/              FastAPI 后端接口
frontend/             前端页面与静态资源
app.py                RBQM 数据处理与计算逻辑
requirements.txt      Python 依赖
```

说明：`app.py` 目前仍被后端引用，承担 RBQM 计算和数据处理逻辑，不要删除。

## 启动方式

解压项目后，在项目根目录执行以下命令。

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

然后在浏览器打开：

```text
http://127.0.0.1:8000
```

如果 PowerShell 不允许激活虚拟环境，可以使用下面的方式：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

## 功能

- 上传 CSV、XLSX、XLS 临床研究数据文件
- 自动识别常见数据域：受试者、访视 / EDC、Query、AE / SAE、实验室、方案偏离
- 计算中心级 KRI：完整性、及时性、Query 负荷、安全性复核、实验室与方案偏离
- 按风险评分对中心排序
- 生成风险信号清单和行动跟踪表
- 导出 RBQM 审查包 Excel
- 支持使用内置示例数据快速预览

## 推荐数据字段

应用支持较宽松的列名匹配。建议上传数据包含以下字段：

- 受试者：`subject_id`, `site_id`, `country`, `status`
- 访视 / EDC：`subject_id`, `site_id`, `visit_date`, `data_entry_date`, `form_status`
- Query：`subject_id`, `site_id`, `query_status`, `opened_date`, `closed_date`, `age_days`
- AE / SAE：`subject_id`, `site_id`, `serious`, `severity`, `outcome`, `start_date`
- 实验室：`subject_id`, `site_id`, `result`, `lln`, `uln`, `reviewed`
- 方案偏离：`subject_id`, `site_id`, `severity`, `status`, `deviation_date`

如果未上传文件，系统会自动使用内置示例数据。
