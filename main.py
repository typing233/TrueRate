from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, case
from datetime import datetime, timedelta, date
from typing import List, Optional
from collections import defaultdict
import os
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

CHINESE_FONT_PATH = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
if os.path.exists(CHINESE_FONT_PATH):
    pdfmetrics.registerFont(TTFont('ChineseFont', CHINESE_FONT_PATH))
    DEFAULT_FONT = 'ChineseFont'
else:
    DEFAULT_FONT = 'Helvetica'

from database import engine, get_db, Base
from models import Project, Task, TimeEntry, User, Tag, project_tag
from schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse,
    TaskCreate, TaskUpdate, TaskResponse,
    TimeEntryCreate, TimeEntryUpdate, TimeEntryResponse,
    DashboardStats,
    UserCreate, UserLogin, UserResponse, Token,
    TagCreate, TagUpdate, TagResponse, ProjectTagsUpdate,
    PeriodStatsRequest, PeriodStatsResponse,
    HourlyRateTrendItem, ProjectStatsItem, TagStatsItem
)
from auth import (
    get_password_hash, authenticate_user, create_access_token,
    get_current_active_user, get_user_by_username, get_user_by_email
)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TrueRate - 极简项目管理与财务核算工具",
    description="将极简项目管理与财务核算无缝绑定的工具，追踪时间投入，算清每一个项目的真实时薪",
    version="1.0.0"
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
if not os.path.exists(templates_dir):
    os.makedirs(templates_dir)
templates = Jinja2Templates(directory=templates_dir)

MIN_HOURS_FOR_CALCULATION = 0.01

def calculate_project_duration(db: Session, project_id: int, owner_id: int) -> float:
    time_entries = db.query(TimeEntry).filter(
        TimeEntry.project_id == project_id,
        TimeEntry.owner_id == owner_id,
        TimeEntry.is_running == False
    ).all()
    total_duration = sum(entry.duration for entry in time_entries)
    return total_duration

def calculate_project_stats(db: Session, project: Project) -> dict:
    total_duration = calculate_project_duration(db, project.id, project.owner_id)
    received_amount = project.received_amount or 0.0
    
    actual_hourly_rate = None
    profit_status = None
    profit_amount = None
    
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
        profit_status = "时长不足"
        profit_amount = None
    
    return {
        "total_duration": total_duration,
        "actual_hourly_rate": actual_hourly_rate,
        "profit_status": profit_status,
        "profit_amount": profit_amount
    }

def build_task_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        is_completed=task.is_completed,
        project_id=task.project_id,
        owner_id=task.owner_id,
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
                owner_id=te.owner_id,
                description=te.description,
                created_at=te.created_at,
                updated_at=te.updated_at
            ) for te in task.time_entries
        ]
    )

def build_project_response(project: Project, db: Session) -> ProjectResponse:
    stats = calculate_project_stats(db, project)
    
    tasks_response = [build_task_response(task) for task in project.tasks]
    tags_response = [
        TagResponse(
            id=tag.id,
            name=tag.name,
            color=tag.color,
            description=tag.description,
            owner_id=tag.owner_id,
            created_at=tag.created_at,
            updated_at=tag.updated_at
        ) for tag in project.tags
    ]
    
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        budget=project.budget,
        hourly_rate=project.hourly_rate,
        received_amount=project.received_amount,
        owner_id=project.owner_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
        tasks=tasks_response,
        tags=tags_response,
        **stats
    )

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_path = os.path.join(templates_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>TrueRate API 服务正在运行</h1><p>请访问 <a href='/docs'>/docs</a> 查看 API 文档</p>")

@app.post("/api/auth/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    existing_user = get_user_by_username(db, username=user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已被注册"
        )
    
    existing_email = get_user_by_email(db, email=user_data.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册"
        )
    
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    access_token = create_access_token(subject=db_user.id)
    user_response = UserResponse(
        id=db_user.id,
        username=db_user.username,
        email=db_user.email,
        full_name=db_user.full_name,
        is_active=db_user.is_active,
        is_superuser=db_user.is_superuser,
        created_at=db_user.created_at,
        updated_at=db_user.updated_at
    )
    
    return Token(access_token=access_token, token_type="bearer", user=user_response)

@app.post("/api/auth/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, username=login_data.username, password=login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(subject=user.id)
    user_response = UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        updated_at=user.updated_at
    )
    
    return Token(access_token=access_token, token_type="bearer", user=user_response)

@app.get("/api/auth/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )

@app.get("/api/dashboard", response_model=DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    projects = db.query(Project).filter(Project.owner_id == current_user.id).all()
    
    total_projects = len(projects)
    total_tasks = db.query(Task).filter(Task.owner_id == current_user.id).count()
    total_completed_tasks = db.query(Task).filter(
        Task.owner_id == current_user.id,
        Task.is_completed == True
    ).count()
    
    total_duration = 0.0
    total_received_amount = 0.0
    valid_total_duration = 0.0
    valid_total_received = 0.0
    recent_projects = []
    
    for project in projects:
        stats = calculate_project_stats(db, project)
        project_duration = stats["total_duration"]
        project_received = project.received_amount or 0.0
        
        total_duration += project_duration
        total_received_amount += project_received
        
        if project_duration >= MIN_HOURS_FOR_CALCULATION and project_received > 0:
            valid_total_duration += project_duration
            valid_total_received += project_received
        
        project_response = build_project_response(project, db)
        recent_projects.append(project_response)
    
    recent_projects.sort(key=lambda x: x.updated_at, reverse=True)
    recent_projects = recent_projects[:5]
    
    overall_hourly_rate = None
    if valid_total_duration > 0 and valid_total_received > 0:
        overall_hourly_rate = valid_total_received / valid_total_duration
    
    return DashboardStats(
        total_projects=total_projects,
        total_tasks=total_tasks,
        total_completed_tasks=total_completed_tasks,
        total_duration=total_duration,
        total_received_amount=total_received_amount,
        overall_hourly_rate=overall_hourly_rate,
        recent_projects=recent_projects
    )

@app.post("/api/projects/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    project_data = project.model_dump(exclude={"tag_ids"})
    db_project = Project(**project_data, owner_id=current_user.id)
    
    if project.tag_ids:
        tags = db.query(Tag).filter(
            Tag.id.in_(project.tag_ids),
            Tag.owner_id == current_user.id
        ).all()
        db_project.tags = tags
    
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    
    return build_project_response(db_project, db)

@app.get("/api/projects/", response_model=List[ProjectResponse])
def read_projects(
    skip: int = 0,
    limit: int = 100,
    tag_ids: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(Project).filter(Project.owner_id == current_user.id)
    
    if tag_ids:
        query = query.join(project_tag).filter(project_tag.c.tag_id.in_(tag_ids))
    
    projects = query.offset(skip).limit(limit).all()
    
    return [build_project_response(project, db) for project in projects]

@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
def read_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    return build_project_response(project, db)

@app.put("/api/projects/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    project: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if db_project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    update_data = project.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_project, key, value)
    
    db.commit()
    db.refresh(db_project)
    
    return build_project_response(db_project, db)

@app.put("/api/projects/{project_id}/tags", response_model=ProjectResponse)
def update_project_tags(
    project_id: int,
    tags_data: ProjectTagsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if db_project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    tags = db.query(Tag).filter(
        Tag.id.in_(tags_data.tag_ids),
        Tag.owner_id == current_user.id
    ).all()
    
    db_project.tags = tags
    db.commit()
    db.refresh(db_project)
    
    return build_project_response(db_project, db)

@app.delete("/api/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if db_project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    db.delete(db_project)
    db.commit()
    return {"message": "项目已删除"}

@app.post("/api/tasks/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    task: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    project = db.query(Project).filter(
        Project.id == task.project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    db_task = Task(**task.model_dump(), owner_id=current_user.id)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    
    return build_task_response(db_task)

@app.get("/api/tasks/", response_model=List[TaskResponse])
def read_tasks(
    project_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(Task).filter(Task.owner_id == current_user.id)
    
    if project_id:
        query = query.filter(Task.project_id == project_id)
    
    tasks = query.offset(skip).limit(limit).all()
    
    return [build_task_response(task) for task in tasks]

@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
def read_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.owner_id == current_user.id
    ).first()
    
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return build_task_response(task)

@app.put("/api/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    task: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_task = db.query(Task).filter(
        Task.id == task_id,
        Task.owner_id == current_user.id
    ).first()
    
    if db_task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    update_data = task.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_task, key, value)
    
    db.commit()
    db.refresh(db_task)
    
    return build_task_response(db_task)

@app.delete("/api/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_task = db.query(Task).filter(
        Task.id == task_id,
        Task.owner_id == current_user.id
    ).first()
    
    if db_task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    db.delete(db_task)
    db.commit()
    return {"message": "任务已删除"}

@app.post("/api/timer/start/{task_id}", response_model=TimeEntryResponse, status_code=status.HTTP_201_CREATED)
def start_timer(
    task_id: int,
    time_entry: Optional[TimeEntryCreate] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.owner_id == current_user.id
    ).first()
    
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    existing_running = db.query(TimeEntry).filter(
        TimeEntry.task_id == task_id,
        TimeEntry.owner_id == current_user.id,
        TimeEntry.is_running == True
    ).first()
    
    if existing_running:
        raise HTTPException(status_code=400, detail="该任务已有正在运行的计时器")
    
    time_entry_data = time_entry.model_dump() if time_entry else {}
    db_time_entry = TimeEntry(
        task_id=task_id,
        project_id=task.project_id,
        owner_id=current_user.id,
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
        owner_id=db_time_entry.owner_id,
        description=db_time_entry.description,
        created_at=db_time_entry.created_at,
        updated_at=db_time_entry.updated_at
    )

@app.put("/api/timer/stop/{time_entry_id}", response_model=TimeEntryResponse)
def stop_timer(
    time_entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_time_entry = db.query(TimeEntry).filter(
        TimeEntry.id == time_entry_id,
        TimeEntry.owner_id == current_user.id
    ).first()
    
    if db_time_entry is None:
        raise HTTPException(status_code=404, detail="时间记录不存在")
    
    if not db_time_entry.is_running:
        raise HTTPException(status_code=400, detail="该计时器已经停止")
    
    end_time = datetime.utcnow()
    duration = (end_time - db_time_entry.start_time).total_seconds() / 3600
    
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
        owner_id=db_time_entry.owner_id,
        description=db_time_entry.description,
        created_at=db_time_entry.created_at,
        updated_at=db_time_entry.updated_at
    )

@app.get("/api/timer/running/", response_model=List[TimeEntryResponse])
def get_running_timers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    running_timers = db.query(TimeEntry).filter(
        TimeEntry.owner_id == current_user.id,
        TimeEntry.is_running == True
    ).all()
    
    return [
        TimeEntryResponse(
            id=timer.id,
            start_time=timer.start_time,
            end_time=timer.end_time,
            duration=timer.duration,
            is_running=timer.is_running,
            project_id=timer.project_id,
            task_id=timer.task_id,
            owner_id=timer.owner_id,
            description=timer.description,
            created_at=timer.created_at,
            updated_at=timer.updated_at
        ) for timer in running_timers
    ]

@app.get("/api/time-entries/", response_model=List[TimeEntryResponse])
def read_time_entries(
    project_id: Optional[int] = None,
    task_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(TimeEntry).filter(TimeEntry.owner_id == current_user.id)
    
    if project_id:
        query = query.filter(TimeEntry.project_id == project_id)
    if task_id:
        query = query.filter(TimeEntry.task_id == task_id)
    
    time_entries = query.offset(skip).limit(limit).all()
    
    return [
        TimeEntryResponse(
            id=entry.id,
            start_time=entry.start_time,
            end_time=entry.end_time,
            duration=entry.duration,
            is_running=entry.is_running,
            project_id=entry.project_id,
            task_id=entry.task_id,
            owner_id=entry.owner_id,
            description=entry.description,
            created_at=entry.created_at,
            updated_at=entry.updated_at
        ) for entry in time_entries
    ]

@app.post("/api/tags/", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
def create_tag(
    tag: TagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    existing_tag = db.query(Tag).filter(
        Tag.name == tag.name,
        Tag.owner_id == current_user.id
    ).first()
    
    if existing_tag:
        raise HTTPException(status_code=400, detail="标签名称已存在")
    
    db_tag = Tag(**tag.model_dump(), owner_id=current_user.id)
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    
    return TagResponse(
        id=db_tag.id,
        name=db_tag.name,
        color=db_tag.color,
        description=db_tag.description,
        owner_id=db_tag.owner_id,
        created_at=db_tag.created_at,
        updated_at=db_tag.updated_at
    )

@app.get("/api/tags/", response_model=List[TagResponse])
def read_tags(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    tags = db.query(Tag).filter(Tag.owner_id == current_user.id).offset(skip).limit(limit).all()
    
    return [
        TagResponse(
            id=tag.id,
            name=tag.name,
            color=tag.color,
            description=tag.description,
            owner_id=tag.owner_id,
            created_at=tag.created_at,
            updated_at=tag.updated_at
        ) for tag in tags
    ]

@app.get("/api/tags/{tag_id}", response_model=TagResponse)
def read_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    tag = db.query(Tag).filter(
        Tag.id == tag_id,
        Tag.owner_id == current_user.id
    ).first()
    
    if tag is None:
        raise HTTPException(status_code=404, detail="标签不存在")
    
    return TagResponse(
        id=tag.id,
        name=tag.name,
        color=tag.color,
        description=tag.description,
        owner_id=tag.owner_id,
        created_at=tag.created_at,
        updated_at=tag.updated_at
    )

@app.put("/api/tags/{tag_id}", response_model=TagResponse)
def update_tag(
    tag_id: int,
    tag: TagUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_tag = db.query(Tag).filter(
        Tag.id == tag_id,
        Tag.owner_id == current_user.id
    ).first()
    
    if db_tag is None:
        raise HTTPException(status_code=404, detail="标签不存在")
    
    update_data = tag.model_dump(exclude_unset=True)
    
    if "name" in update_data and update_data["name"] != db_tag.name:
        existing_tag = db.query(Tag).filter(
            Tag.name == update_data["name"],
            Tag.owner_id == current_user.id,
            Tag.id != tag_id
        ).first()
        if existing_tag:
            raise HTTPException(status_code=400, detail="标签名称已存在")
    
    for key, value in update_data.items():
        setattr(db_tag, key, value)
    
    db.commit()
    db.refresh(db_tag)
    
    return TagResponse(
        id=db_tag.id,
        name=db_tag.name,
        color=db_tag.color,
        description=db_tag.description,
        owner_id=db_tag.owner_id,
        created_at=db_tag.created_at,
        updated_at=db_tag.updated_at
    )

@app.delete("/api/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_tag = db.query(Tag).filter(
        Tag.id == tag_id,
        Tag.owner_id == current_user.id
    ).first()
    
    if db_tag is None:
        raise HTTPException(status_code=404, detail="标签不存在")
    
    db.delete(db_tag)
    db.commit()
    return {"message": "标签已删除"}

def get_date_range(period_type: str, start_date: Optional[date] = None, end_date: Optional[date] = None):
    today = date.today()
    
    if period_type == "week":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
    elif period_type == "month":
        start = today.replace(day=1)
        if today.month == 12:
            end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    elif period_type == "quarter":
        quarter = (today.month - 1) // 3 + 1
        start = today.replace(month=(quarter - 1) * 3 + 1, day=1)
        if quarter == 4:
            end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = today.replace(month=quarter * 3 + 1, day=1) - timedelta(days=1)
    elif period_type == "year":
        start = today.replace(month=1, day=1)
        end = today.replace(month=12, day=31)
    else:
        start = start_date or today
        end = end_date or today
    
    return start, end

@app.post("/api/stats/period", response_model=PeriodStatsResponse)
def get_period_stats(
    request: PeriodStatsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    start_date, end_date = get_date_range(
        request.period_type,
        request.start_date,
        request.end_date
    )
    
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    time_entries = db.query(TimeEntry).filter(
        TimeEntry.owner_id == current_user.id,
        TimeEntry.is_running == False,
        TimeEntry.start_time >= start_datetime,
        TimeEntry.start_time <= end_datetime
    ).all()
    
    projects = db.query(Project).filter(
        Project.owner_id == current_user.id
    ).all()
    
    project_map = {p.id: p for p in projects}
    
    total_duration = sum(te.duration for te in time_entries)
    total_received_amount = 0.0
    valid_duration = 0.0
    valid_received = 0.0
    
    project_stats_dict = defaultdict(lambda: {"duration": 0.0, "received": 0.0})
    daily_stats = defaultdict(lambda: {"duration": 0.0, "received": 0.0})
    tag_stats_dict = defaultdict(lambda: {"duration": 0.0, "received": 0.0, "projects": set()})
    
    for te in time_entries:
        project = project_map.get(te.project_id)
        if project:
            project_stats_dict[te.project_id]["duration"] += te.duration
            
            for tag in project.tags:
                tag_stats_dict[tag.id]["duration"] += te.duration
                tag_stats_dict[tag.id]["projects"].add(project.id)
        
        entry_date = te.start_time.date()
        daily_stats[entry_date]["duration"] += te.duration
    
    for project in projects:
        if project.received_amount:
            total_received_amount += project.received_amount
            
            project_duration = project_stats_dict[project.id]["duration"]
            if project_duration >= MIN_HOURS_FOR_CALCULATION:
                valid_duration += project_duration
                valid_received += project.received_amount
                
                project_stats_dict[project.id]["received"] = project.received_amount
                
                for tag in project.tags:
                    tag_stats_dict[tag.id]["received"] += project.received_amount
    
    overall_hourly_rate = None
    if valid_duration > 0 and valid_received > 0:
        overall_hourly_rate = valid_received / valid_duration
    
    total_projects = len(projects)
    total_tasks = db.query(Task).filter(Task.owner_id == current_user.id).count()
    total_completed_tasks = db.query(Task).filter(
        Task.owner_id == current_user.id,
        Task.is_completed == True
    ).count()
    
    hourly_rate_trend = []
    current_date = start_date
    while current_date <= end_date:
        day_duration = daily_stats[current_date]["duration"]
        day_received = daily_stats[current_date]["received"]
        
        day_hourly_rate = None
        if day_duration >= MIN_HOURS_FOR_CALCULATION and day_received > 0:
            day_hourly_rate = day_received / day_duration
        
        hourly_rate_trend.append(HourlyRateTrendItem(
            date=current_date.isoformat(),
            hourly_rate=day_hourly_rate,
            total_duration=day_duration,
            total_received=day_received
        ))
        current_date += timedelta(days=1)
    
    project_stats = []
    for project_id, stats in project_stats_dict.items():
        project = project_map.get(project_id)
        if project:
            hourly_rate = None
            if stats["duration"] >= MIN_HOURS_FOR_CALCULATION and stats["received"] > 0:
                hourly_rate = stats["received"] / stats["duration"]
            
            project_stats.append(ProjectStatsItem(
                project_id=project_id,
                project_name=project.name,
                total_duration=stats["duration"],
                total_received=stats["received"],
                hourly_rate=hourly_rate
            ))
    
    tags = db.query(Tag).filter(Tag.owner_id == current_user.id).all()
    tag_map = {t.id: t for t in tags}
    
    tag_stats = []
    for tag_id, stats in tag_stats_dict.items():
        tag = tag_map.get(tag_id)
        if tag:
            tag_stats.append(TagStatsItem(
                tag_id=tag_id,
                tag_name=tag.name,
                tag_color=tag.color,
                total_duration=stats["duration"],
                total_received=stats["received"],
                project_count=len(stats["projects"])
            ))
    
    return PeriodStatsResponse(
        start_date=start_date,
        end_date=end_date,
        period_type=request.period_type,
        total_duration=total_duration,
        total_received_amount=total_received_amount,
        overall_hourly_rate=overall_hourly_rate,
        total_projects=total_projects,
        total_tasks=total_tasks,
        total_completed_tasks=total_completed_tasks,
        hourly_rate_trend=hourly_rate_trend,
        project_stats=project_stats,
        tag_stats=tag_stats
    )

@app.get("/api/projects/{project_id}/pdf/")
def export_project_pdf(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    stats = calculate_project_stats(db, project)
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'ChineseTitle',
        parent=styles['Title'],
        fontName=DEFAULT_FONT,
        fontSize=24,
        spaceAfter=12
    )
    
    heading2_style = ParagraphStyle(
        'ChineseHeading2',
        parent=styles['Heading2'],
        fontName=DEFAULT_FONT,
        fontSize=18,
        spaceAfter=12
    )
    
    title = Paragraph(f"项目账单: {project.name}", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))
    
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
    
    doc.build(elements)
    buffer.seek(0)
    
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
