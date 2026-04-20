from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

# 时间记录相关的 Pydantic 模型
class TimeEntryBase(BaseModel):
    task_id: Optional[int] = None
    description: Optional[str] = None

class TimeEntryCreate(TimeEntryBase):
    pass

class TimeEntryUpdate(BaseModel):
    end_time: Optional[datetime] = None
    description: Optional[str] = None

class TimeEntryResponse(TimeEntryBase):
    id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: float
    is_running: bool
    project_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# 任务相关的 Pydantic 模型
class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None

class TaskCreate(TaskBase):
    project_id: int

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_completed: Optional[bool] = None

class TaskResponse(TaskBase):
    id: int
    is_completed: bool
    project_id: int
    created_at: datetime
    updated_at: datetime
    time_entries: List[TimeEntryResponse] = []

    class Config:
        from_attributes = True

# 项目相关的 Pydantic 模型
class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    budget: Optional[float] = Field(None, ge=0)
    hourly_rate: Optional[float] = Field(None, ge=0)
    received_amount: Optional[float] = Field(0.0, ge=0)

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    budget: Optional[float] = Field(None, ge=0)
    hourly_rate: Optional[float] = Field(None, ge=0)
    received_amount: Optional[float] = Field(None, ge=0)

class ProjectResponse(ProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime
    tasks: List[TaskResponse] = []
    total_duration: float = 0.0
    actual_hourly_rate: Optional[float] = None
    profit_status: Optional[str] = None
    profit_amount: Optional[float] = None

    class Config:
        from_attributes = True

# 仪表盘统计数据模型
class DashboardStats(BaseModel):
    total_projects: int
    total_tasks: int
    total_completed_tasks: int
    total_duration: float
    total_received_amount: float
    overall_hourly_rate: Optional[float] = None
    recent_projects: List[ProjectResponse] = []

    class Config:
        from_attributes = True
