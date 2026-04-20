from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta
from typing import List, Optional
import os
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 注册中文字体
CHINESE_FONT_PATH = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
if os.path.exists(CHINESE_FONT_PATH):
    pdfmetrics.registerFont(TTFont('ChineseFont', CHINESE_FONT_PATH))
    DEFAULT_FONT = 'ChineseFont'
else:
    # 如果没有中文字体，使用默认字体
    DEFAULT_FONT = 'Helvetica'

from database import engine, get_db, Base
from models import Project, Task, TimeEntry
from schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse,
    TaskCreate, TaskUpdate, TaskResponse,
    TimeEntryCreate, TimeEntryUpdate, TimeEntryResponse,
    DashboardStats
)

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TrueRate - 极简项目管理与财务核算工具",
    description="将极简项目管理与财务核算无缝绑定的工具，追踪时间投入，算清每一个项目的真实时薪",
    version="1.0.0"
)

# 挂载静态文件目录
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 模板目录
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
if not os.path.exists(templates_dir):
    os.makedirs(templates_dir)
templates = Jinja2Templates(directory=templates_dir)

# 辅助函数：计算项目总时长
def calculate_project_duration(db: Session, project_id: int) -> float:
    time_entries = db.query(TimeEntry).filter(
        TimeEntry.project_id == project_id,
        TimeEntry.is_running == False
    ).all()
    total_duration = sum(entry.duration for entry in time_entries)
    return total_duration

# 辅助函数：计算项目真实时薪和盈亏状态
MIN_HOURS_FOR_CALCULATION = 0.01  # 最小时长阈值：0.01 小时 = 36 秒

def calculate_project_stats(db: Session, project: Project) -> dict:
    total_duration = calculate_project_duration(db, project.id)
    received_amount = project.received_amount or 0.0
    
    actual_hourly_rate = None
    profit_status = None
    profit_amount = None
    
    # 只有当总时长大于等于最小阈值且已收款金额大于 0 时，才计算真实时薪
    if total_duration >= MIN_HOURS_FOR_CALCULATION and received_amount > 0:
        actual_hourly_rate = received_amount / total_duration
        
        if project.hourly_rate is not None:
            if actual_hourly_rate >= project.hourly_rate:
                profit_status = "盈利"
                profit_amount = (actual_hourly_rate - project.hourly_rate) * total_duration
            else:
                profit_status = "亏损"
                profit_amount = (actual_hourly_rate - project.hourly_rate) * total_duration
        elif project.budget is not None:
            if received_amount >= project.budget:
                profit_status = "超出预算"
                profit_amount = received_amount - project.budget
            else:
                profit_status = "低于预算"
                profit_amount = received_amount - project.budget
        else:
            profit_status = "已完成"
            profit_amount = received_amount
    elif total_duration > 0 and received_amount > 0:
        # 时长不足最小阈值时，显示提示信息
        profit_status = "时长不足"
        profit_amount = None
    
    return {
        "total_duration": total_duration,
        "actual_hourly_rate": actual_hourly_rate,
        "profit_status": profit_status,
        "profit_amount": profit_amount
    }

# 主页路由
@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_path = os.path.join(templates_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>TrueRate API 服务正在运行</h1><p>请访问 <a href='/docs'>/docs</a> 查看 API 文档</p>")

# 仪表盘统计
@app.get("/api/dashboard", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    # 获取所有项目
    projects = db.query(Project).all()
    
    total_projects = len(projects)
    total_tasks = db.query(Task).count()
    total_completed_tasks = db.query(Task).filter(Task.is_completed == True).count()
    
    # 计算总时长和总收款
    total_duration = 0.0
    total_received_amount = 0.0
    recent_projects = []
    
    for project in projects:
        stats = calculate_project_stats(db, project)
        total_duration += stats["total_duration"]
        total_received_amount += project.received_amount or 0.0
        
        # 构建项目响应
        project_response = ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            budget=project.budget,
            hourly_rate=project.hourly_rate,
            received_amount=project.received_amount,
            created_at=project.created_at,
            updated_at=project.updated_at,
            tasks=[],
            **stats
        )
        recent_projects.append(project_response)
    
    # 按更新时间排序，取最近的5个项目
    recent_projects.sort(key=lambda x: x.updated_at, reverse=True)
    recent_projects = recent_projects[:5]
    
    # 计算整体时薪
    overall_hourly_rate = None
    if total_duration > 0:
        overall_hourly_rate = total_received_amount / total_duration
    
    return DashboardStats(
        total_projects=total_projects,
        total_tasks=total_tasks,
        total_completed_tasks=total_completed_tasks,
        total_duration=total_duration,
        total_received_amount=total_received_amount,
        overall_hourly_rate=overall_hourly_rate,
        recent_projects=recent_projects
    )

# 项目管理 API
@app.post("/api/projects/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    db_project = Project(**project.model_dump())
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    
    stats = calculate_project_stats(db, db_project)
    return ProjectResponse(
        id=db_project.id,
        name=db_project.name,
        description=db_project.description,
        budget=db_project.budget,
        hourly_rate=db_project.hourly_rate,
        received_amount=db_project.received_amount,
        created_at=db_project.created_at,
        updated_at=db_project.updated_at,
        tasks=[],
        **stats
    )

@app.get("/api/projects/", response_model=List[ProjectResponse])
def read_projects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    projects = db.query(Project).offset(skip).limit(limit).all()
    
    project_responses = []
    for project in projects:
        stats = calculate_project_stats(db, project)
        
        # 构建任务列表
        tasks_response = []
        for task in project.tasks:
            tasks_response.append(TaskResponse(
                id=task.id,
                title=task.title,
                description=task.description,
                is_completed=task.is_completed,
                project_id=task.project_id,
                created_at=task.created_at,
                updated_at=task.updated_at,
                time_entries=[
                    TimeEntryResponse(
                        id=te.id,
                        start_time=te.start_time,
                        end_time=te.end_time,
                        duration=te.duration,
                        is_running=te.is_running,
                        project_id=te.project_id,
                        task_id=te.task_id,
                        description=te.description,
                        created_at=te.created_at,
                        updated_at=te.updated_at
                    ) for te in task.time_entries
                ]
            ))
        
        project_responses.append(ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            budget=project.budget,
            hourly_rate=project.hourly_rate,
            received_amount=project.received_amount,
            created_at=project.created_at,
            updated_at=project.updated_at,
            tasks=tasks_response,
            **stats
        ))
    
    return project_responses

@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
def read_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    stats = calculate_project_stats(db, project)
    
    # 构建任务列表
    tasks_response = []
    for task in project.tasks:
        tasks_response.append(TaskResponse(
            id=task.id,
            title=task.title,
            description=task.description,
            is_completed=task.is_completed,
            project_id=task.project_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
            time_entries=[
                TimeEntryResponse(
                    id=te.id,
                    start_time=te.start_time,
                    end_time=te.end_time,
                    duration=te.duration,
                    is_running=te.is_running,
                    project_id=te.project_id,
                    task_id=te.task_id,
                    description=te.description,
                    created_at=te.created_at,
                    updated_at=te.updated_at
                ) for te in task.time_entries
            ]
        ))
    
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        budget=project.budget,
        hourly_rate=project.hourly_rate,
        received_amount=project.received_amount,
        created_at=project.created_at,
        updated_at=project.updated_at,
        tasks=tasks_response,
        **stats
    )

@app.put("/api/projects/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, project: ProjectUpdate, db: Session = Depends(get_db)):
    db_project = db.query(Project).filter(Project.id == project_id).first()
    if db_project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    update_data = project.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_project, key, value)
    
    db.commit()
    db.refresh(db_project)
    
    stats = calculate_project_stats(db, db_project)
    return ProjectResponse(
        id=db_project.id,
        name=db_project.name,
        description=db_project.description,
        budget=db_project.budget,
        hourly_rate=db_project.hourly_rate,
        received_amount=db_project.received_amount,
        created_at=db_project.created_at,
        updated_at=db_project.updated_at,
        tasks=[],
        **stats
    )

@app.delete("/api/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    db_project = db.query(Project).filter(Project.id == project_id).first()
    if db_project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    db.delete(db_project)
    db.commit()
    return {"message": "项目已删除"}

# 任务管理 API
@app.post("/api/tasks/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    # 检查项目是否存在
    project = db.query(Project).filter(Project.id == task.project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    db_task = Task(**task.model_dump())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    
    return TaskResponse(
        id=db_task.id,
        title=db_task.title,
        description=db_task.description,
        is_completed=db_task.is_completed,
        project_id=db_task.project_id,
        created_at=db_task.created_at,
        updated_at=db_task.updated_at,
        time_entries=[]
    )

@app.get("/api/tasks/", response_model=List[TaskResponse])
def read_tasks(project_id: Optional[int] = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(Task)
    if project_id:
        query = query.filter(Task.project_id == project_id)
    
    tasks = query.offset(skip).limit(limit).all()
    
    task_responses = []
    for task in tasks:
        task_responses.append(TaskResponse(
            id=task.id,
            title=task.title,
            description=task.description,
            is_completed=task.is_completed,
            project_id=task.project_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
            time_entries=[
                TimeEntryResponse(
                    id=te.id,
                    start_time=te.start_time,
                    end_time=te.end_time,
                    duration=te.duration,
                    is_running=te.is_running,
                    project_id=te.project_id,
                    task_id=te.task_id,
                    description=te.description,
                    created_at=te.created_at,
                    updated_at=te.updated_at
                ) for te in task.time_entries
            ]
        ))
    
    return task_responses

@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
def read_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        is_completed=task.is_completed,
        project_id=task.project_id,
        created_at=task.created_at,
        updated_at=task.updated_at,
        time_entries=[
            TimeEntryResponse(
                id=te.id,
                start_time=te.start_time,
                end_time=te.end_time,
                duration=te.duration,
                is_running=te.is_running,
                project_id=te.project_id,
                task_id=te.task_id,
                description=te.description,
                created_at=te.created_at,
                updated_at=te.updated_at
            ) for te in task.time_entries
        ]
    )

@app.put("/api/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, task: TaskUpdate, db: Session = Depends(get_db)):
    db_task = db.query(Task).filter(Task.id == task_id).first()
    if db_task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    update_data = task.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_task, key, value)
    
    db.commit()
    db.refresh(db_task)
    
    return TaskResponse(
        id=db_task.id,
        title=db_task.title,
        description=db_task.description,
        is_completed=db_task.is_completed,
        project_id=db_task.project_id,
        created_at=db_task.created_at,
        updated_at=db_task.updated_at,
        time_entries=[
            TimeEntryResponse(
                id=te.id,
                start_time=te.start_time,
                end_time=te.end_time,
                duration=te.duration,
                is_running=te.is_running,
                project_id=te.project_id,
                task_id=te.task_id,
                description=te.description,
                created_at=te.created_at,
                updated_at=te.updated_at
            ) for te in db_task.time_entries
        ]
    )

@app.delete("/api/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    db_task = db.query(Task).filter(Task.id == task_id).first()
    if db_task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    db.delete(db_task)
    db.commit()
    return {"message": "任务已删除"}

# 计时器 API
@app.post("/api/timer/start/{task_id}", response_model=TimeEntryResponse, status_code=status.HTTP_201_CREATED)
def start_timer(task_id: int, time_entry: Optional[TimeEntryCreate] = None, db: Session = Depends(get_db)):
    # 检查任务是否存在
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 检查是否有正在运行的计时器
    existing_running = db.query(TimeEntry).filter(
        and_(
            TimeEntry.task_id == task_id,
            TimeEntry.is_running == True
        )
    ).first()
    
    if existing_running:
        raise HTTPException(status_code=400, detail="该任务已有正在运行的计时器")
    
    # 创建新的时间记录
    time_entry_data = time_entry.model_dump() if time_entry else {}
    db_time_entry = TimeEntry(
        task_id=task_id,
        project_id=task.project_id,
        start_time=datetime.utcnow(),
        is_running=True,
        **time_entry_data
    )
    db.add(db_time_entry)
    db.commit()
    db.refresh(db_time_entry)
    
    return TimeEntryResponse(
        id=db_time_entry.id,
        start_time=db_time_entry.start_time,
        end_time=db_time_entry.end_time,
        duration=db_time_entry.duration,
        is_running=db_time_entry.is_running,
        project_id=db_time_entry.project_id,
        task_id=db_time_entry.task_id,
        description=db_time_entry.description,
        created_at=db_time_entry.created_at,
        updated_at=db_time_entry.updated_at
    )

@app.put("/api/timer/stop/{time_entry_id}", response_model=TimeEntryResponse)
def stop_timer(time_entry_id: int, db: Session = Depends(get_db)):
    db_time_entry = db.query(TimeEntry).filter(TimeEntry.id == time_entry_id).first()
    if db_time_entry is None:
        raise HTTPException(status_code=404, detail="时间记录不存在")
    
    if not db_time_entry.is_running:
        raise HTTPException(status_code=400, detail="该计时器已经停止")
    
    # 停止计时器，计算持续时间
    end_time = datetime.utcnow()
    duration = (end_time - db_time_entry.start_time).total_seconds() / 3600  # 转换为小时
    
    db_time_entry.end_time = end_time
    db_time_entry.duration = duration
    db_time_entry.is_running = False
    
    db.commit()
    db.refresh(db_time_entry)
    
    return TimeEntryResponse(
        id=db_time_entry.id,
        start_time=db_time_entry.start_time,
        end_time=db_time_entry.end_time,
        duration=db_time_entry.duration,
        is_running=db_time_entry.is_running,
        project_id=db_time_entry.project_id,
        task_id=db_time_entry.task_id,
        description=db_time_entry.description,
        created_at=db_time_entry.created_at,
        updated_at=db_time_entry.updated_at
    )

@app.get("/api/timer/running/", response_model=List[TimeEntryResponse])
def get_running_timers(db: Session = Depends(get_db)):
    running_timers = db.query(TimeEntry).filter(TimeEntry.is_running == True).all()
    
    timer_responses = []
    for timer in running_timers:
        timer_responses.append(TimeEntryResponse(
            id=timer.id,
            start_time=timer.start_time,
            end_time=timer.end_time,
            duration=timer.duration,
            is_running=timer.is_running,
            project_id=timer.project_id,
            task_id=timer.task_id,
            description=timer.description,
            created_at=timer.created_at,
            updated_at=timer.updated_at
        ))
    
    return timer_responses

@app.get("/api/time-entries/", response_model=List[TimeEntryResponse])
def read_time_entries(
    project_id: Optional[int] = None,
    task_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(TimeEntry)
    if project_id:
        query = query.filter(TimeEntry.project_id == project_id)
    if task_id:
        query = query.filter(TimeEntry.task_id == task_id)
    
    time_entries = query.offset(skip).limit(limit).all()
    
    entry_responses = []
    for entry in time_entries:
        entry_responses.append(TimeEntryResponse(
            id=entry.id,
            start_time=entry.start_time,
            end_time=entry.end_time,
            duration=entry.duration,
            is_running=entry.is_running,
            project_id=entry.project_id,
            task_id=entry.task_id,
            description=entry.description,
            created_at=entry.created_at,
            updated_at=entry.updated_at
        ))
    
    return entry_responses

# PDF 账单导出 API
@app.get("/api/projects/{project_id}/pdf/")
def export_project_pdf(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 计算项目统计
    stats = calculate_project_stats(db, project)
    
    # 创建 PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    # 创建支持中文的样式
    styles = getSampleStyleSheet()
    
    # 标题样式（支持中文）
    title_style = ParagraphStyle(
        'ChineseTitle',
        parent=styles['Title'],
        fontName=DEFAULT_FONT,
        fontSize=24,
        spaceAfter=12
    )
    
    # 标题2样式（支持中文）
    heading2_style = ParagraphStyle(
        'ChineseHeading2',
        parent=styles['Heading2'],
        fontName=DEFAULT_FONT,
        fontSize=18,
        spaceAfter=12
    )
    
    # 标题
    title = Paragraph(f"项目账单: {project.name}", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    # 项目信息
    project_info = [
        ["项目名称", project.name],
        ["项目描述", project.description or "无"],
        ["创建时间", project.created_at.strftime("%Y-%m-%d %H:%M:%S")],
        ["更新时间", project.updated_at.strftime("%Y-%m-%d %H:%M:%S")],
    ]
    
    if project.budget:
        project_info.append(["总预算", f"¥{project.budget:.2f}"])
    if project.hourly_rate:
        project_info.append(["时薪标准", f"¥{project.hourly_rate:.2f}/小时"])
    project_info.append(["已收款金额", f"¥{project.received_amount:.2f}"])
    project_info.append(["总工作时长", f"{stats['total_duration']:.2f} 小时"])
    
    if stats['actual_hourly_rate']:
        project_info.append(["真实时薪", f"¥{stats['actual_hourly_rate']:.2f}/小时"])
    if stats['profit_status']:
        project_info.append(["盈亏状态", stats['profit_status']])
    if stats['profit_amount']:
        project_info.append(["盈亏金额", f"¥{stats['profit_amount']:.2f}"])
    
    project_table = Table(project_info, colWidths=[2*inch, 4*inch])
    project_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), DEFAULT_FONT),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(project_table)
    elements.append(Spacer(1, 24))
    
    # 任务列表
    if project.tasks:
        tasks_title = Paragraph("任务列表", heading2_style)
        elements.append(tasks_title)
        elements.append(Spacer(1, 12))
        
        tasks_data = [["任务名称", "状态", "总时长", "创建时间"]]
        for task in project.tasks:
            task_duration = sum(te.duration for te in task.time_entries if not te.is_running)
            status = "已完成" if task.is_completed else "进行中"
            tasks_data.append([
                task.title,
                status,
                f"{task_duration:.2f} 小时",
                task.created_at.strftime("%Y-%m-%d %H:%M:%S")
            ])
        
        tasks_table = Table(tasks_data, colWidths=[2*inch, 1*inch, 1.5*inch, 2*inch])
        tasks_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), DEFAULT_FONT),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(tasks_table)
        elements.append(Spacer(1, 24))
    
    # 时间记录
    if project.time_entries:
        time_entries_title = Paragraph("时间记录", heading2_style)
        elements.append(time_entries_title)
        elements.append(Spacer(1, 12))
        
        time_entries_data = [["开始时间", "结束时间", "时长", "状态", "描述"]]
        for entry in project.time_entries:
            status = "运行中" if entry.is_running else "已完成"
            end_time = entry.end_time.strftime("%Y-%m-%d %H:%M:%S") if entry.end_time else "进行中"
            duration = f"{entry.duration:.2f} 小时" if not entry.is_running else "计算中"
            time_entries_data.append([
                entry.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                end_time,
                duration,
                status,
                entry.description or "无"
            ])
        
        time_entries_table = Table(time_entries_data, colWidths=[1.5*inch, 1.5*inch, 1*inch, 0.8*inch, 1.5*inch])
        time_entries_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), DEFAULT_FONT),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(time_entries_table)
    
    # 生成 PDF
    doc.build(elements)
    buffer.seek(0)
    
    # 保存到临时文件
    temp_dir = os.path.join(os.path.dirname(__file__), "temp")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    
    pdf_path = os.path.join(temp_dir, f"project_{project_id}_bill.pdf")
    with open(pdf_path, "wb") as f:
        f.write(buffer.getvalue())
    
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"{project.name}_账单.pdf"
    )

# 启动服务器
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
