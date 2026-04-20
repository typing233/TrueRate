# TrueRate - 极简项目管理与财务核算工具

## 项目简介

TrueRate 是一款将极简项目管理与财务核算无缝绑定的工具，帮助你追踪时间投入，算清每一个项目的真实时薪，拒绝瞎忙。

通过 TrueRate，你可以：
- 创建极简的项目卡片并添加基础的待办任务
- 通过任务旁边的一键计时器记录实际工作耗时
- 为项目设定总预算或时薪标准
- 自动计算并展示项目的真实时薪与盈亏状态
- 将项目明细和应收金额一键导出为干净的 PDF 账单

## 功能特性

### 📊 仪表盘统计
- 总项目数、任务完成情况一目了然
- 总工作时长和总收款金额实时统计
- 整体时薪计算，帮助你了解自己的时间价值
- 运行中的计时器状态监控

### 📁 项目管理
- 创建、编辑、删除项目
- 为项目设置预算和时薪标准
- 记录项目的已收款金额
- 查看项目详情和统计数据

### ✅ 任务管理
- 为项目添加待办任务
- 标记任务完成状态
- 查看任务的累计工作时长
- 删除不需要的任务

### ⏱️ 计时器功能
- 一键开始/停止任务计时
- 实时显示计时时长
- 支持多个任务同时计时
- 自动记录开始和结束时间

### 💰 财务核算
- 自动计算项目真实时薪（已收款金额 / 总工作时长）
- 根据设定的时薪标准判断盈亏状态（盈利/亏损）
- 根据设定的预算判断是否超出预算
- 计算具体的盈亏金额

### 📄 PDF 账单导出
- 一键导出项目详细账单
- 包含项目基本信息、任务列表、时间记录
- 清晰展示财务统计数据
- 专业的 PDF 格式，方便分享和存档

## 技术栈

### 后端
- **Python 3.8+**
- **FastAPI** - 现代、快速（高性能）的 Web 框架
- **SQLAlchemy** - Python SQL 工具包和 ORM
- **Pydantic** - 数据验证和设置管理
- **SQLite** - 轻量级关系型数据库
- **ReportLab** - PDF 生成库

### 前端
- **HTML5** - 页面结构
- **Tailwind CSS** - 实用优先的 CSS 框架
- **原生 JavaScript** - 交互逻辑
- **响应式设计** - 支持桌面和移动设备

## 项目结构

```
TrueRate/
├── main.py              # FastAPI 主应用文件
├── database.py          # 数据库配置
├── models.py            # SQLAlchemy 数据模型
├── schemas.py           # Pydantic 数据模型
├── requirements.txt     # Python 依赖包
├── README.md           # 项目说明文档
├── templates/          # HTML 模板目录
│   └── index.html      # 前端界面
├── static/             # 静态文件目录
├── temp/               # 临时文件目录（运行时生成）
└── truerate.db         # SQLite 数据库文件（运行时生成）
```

## 安装部署

### 环境要求
- Python 3.8 或更高版本
- pip 包管理器

### 安装步骤

1. **克隆项目**（如果使用版本控制）或直接进入项目目录
```bash
cd TrueRate
```

2. **创建虚拟环境（推荐）**
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

3. **安装依赖包**
```bash
pip install -r requirements.txt
```

### 启动服务

#### 方式一：使用 uvicorn 命令（推荐开发环境）
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### 方式二：直接运行 Python 文件
```bash
python main.py
```

#### 方式三：使用 systemctl（生产环境）
创建服务文件 `/etc/systemd/system/truerate.service`：
```ini
[Unit]
Description=TrueRate 项目管理工具
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/TrueRate
Environment="PATH=/path/to/TrueRate/venv/bin"
ExecStart=/path/to/TrueRate/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl enable truerate
sudo systemctl start truerate
```

### 访问应用

启动服务后，在浏览器中访问以下地址：

- **主页**：http://localhost:8000
- **API 文档（自动生成）**：http://localhost:8000/docs
- **备用 API 文档**：http://localhost:8000/redoc

## 使用说明

### 快速开始

1. **创建第一个项目**
   - 点击导航栏的"项目管理"
   - 点击"新建项目"按钮
   - 填写项目名称（必填）、描述、预算、时薪标准、已收款金额
   - 点击"创建"按钮

2. **添加任务**
   - 在项目卡片上点击"添加任务"按钮
   - 或进入项目详情页点击"添加任务"
   - 填写任务名称和描述
   - 点击"创建"按钮

3. **开始计时**
   - 进入"计时器"页面
   - 或在项目详情页的任务列表中
   - 点击任务旁边的"开始"按钮
   - 计时器开始运行，实时显示时长

4. **停止计时**
   - 点击运行中的计时器的"停止"按钮
   - 系统自动计算并记录工作时长

5. **查看统计**
   - 进入"仪表盘"页面查看整体统计
   - 进入项目详情页查看单个项目的详细统计
   - 系统自动计算真实时薪和盈亏状态

6. **导出 PDF 账单**
   - 进入项目详情页
   - 点击"导出 PDF"按钮
   - 系统自动生成并下载 PDF 账单

### 详细功能说明

#### 项目设置

- **预算**：设定项目的总预算金额，系统会对比已收款金额判断是否超出预算
- **时薪标准**：设定你的期望时薪，系统会对比真实时薪判断盈亏状态
- **已收款金额**：记录项目实际收到的款项，用于计算真实时薪

#### 真实时薪计算

真实时薪 = 已收款金额 ÷ 总工作时长

- 当真实时薪 ≥ 设定的时薪标准时，状态为"盈利"
- 当真实时薪 < 设定的时薪标准时，状态为"亏损"

#### 盈亏金额计算

盈亏金额 = (真实时薪 - 时薪标准) × 总工作时长

或（当使用预算而非时薪标准时）：

盈亏金额 = 已收款金额 - 预算金额

## API 接口说明

### 仪表盘统计
- `GET /api/dashboard` - 获取仪表盘统计数据

### 项目管理
- `GET /api/projects/` - 获取项目列表
- `POST /api/projects/` - 创建新项目
- `GET /api/projects/{project_id}` - 获取单个项目详情
- `PUT /api/projects/{project_id}` - 更新项目信息
- `DELETE /api/projects/{project_id}` - 删除项目
- `GET /api/projects/{project_id}/pdf/` - 导出项目 PDF 账单

### 任务管理
- `GET /api/tasks/` - 获取任务列表（可按项目过滤）
- `POST /api/tasks/` - 创建新任务
- `GET /api/tasks/{task_id}` - 获取单个任务详情
- `PUT /api/tasks/{task_id}` - 更新任务信息
- `DELETE /api/tasks/{task_id}` - 删除任务

### 计时器
- `POST /api/timer/start/{task_id}` - 开始任务计时
- `PUT /api/timer/stop/{time_entry_id}` - 停止计时
- `GET /api/timer/running/` - 获取所有运行中的计时器
- `GET /api/time-entries/` - 获取时间记录列表（可按项目或任务过滤）

## 数据库说明

### 数据表结构

#### projects（项目表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键，自增 |
| name | String | 项目名称 |
| description | String | 项目描述 |
| budget | Float | 总预算 |
| hourly_rate | Float | 时薪标准 |
| received_amount | Float | 已收款金额 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

#### tasks（任务表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键，自增 |
| title | String | 任务标题 |
| description | String | 任务描述 |
| is_completed | Boolean | 是否完成 |
| project_id | Integer | 关联项目ID |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

#### time_entries（时间记录表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键，自增 |
| start_time | DateTime | 开始时间 |
| end_time | DateTime | 结束时间 |
| duration | Float | 持续时间（小时） |
| is_running | Boolean | 是否运行中 |
| task_id | Integer | 关联任务ID |
| project_id | Integer | 关联项目ID |
| description | String | 描述 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

## 常见问题

### Q: 数据存储在哪里？
A: 数据存储在 SQLite 数据库文件 `truerate.db` 中，位于项目根目录。如需备份，直接复制此文件即可。

### Q: 如何修改端口号？
A: 在启动命令中修改 `--port` 参数，例如：
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

### Q: 支持多用户吗？
A: 当前版本是单用户设计，所有数据共享。如需多用户支持，可以基于此版本扩展，添加用户认证和数据隔离功能。

### Q: 如何迁移到其他数据库（如 PostgreSQL）？
A: 修改 `database.py` 中的 `DATABASE_URL` 连接字符串，安装对应的数据库驱动包（如 `psycopg2-binary`），SQLAlchemy 会处理数据库差异。

### Q: 计时器可以跨天运行吗？
A: 是的，计时器可以跨天运行，停止时会自动计算准确的时长（以小时为单位，精确到秒）。

## 更新日志

### v1.0.0
- 初始版本发布
- 实现项目管理功能
- 实现任务管理功能
- 实现计时器功能
- 实现财务核算和真实时薪计算
- 实现 PDF 账单导出
- 提供响应式前端界面
- 自动生成 API 文档

## 许可证

MIT License

## 联系方式

如有问题或建议，欢迎提交 Issue 或 Pull Request。

---

**TrueRate** - 算清每一小时的价值，拒绝瞎忙。
