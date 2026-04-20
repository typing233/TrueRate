from pydantic import BaseModel, Field, EmailStr
from datetime import datetime, date
from typing import Optional, List

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=100)

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100)

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenPayload(BaseModel):
    sub: Optional[int] = None
    exp: Optional[datetime] = None

class TagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    color: Optional[str] = Field("#6366f1", min_length=7, max_length=7)
    description: Optional[str] = Field(None, max_length=200)

class TagCreate(TagBase):
    pass

class TagUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    color: Optional[str] = Field(None, min_length=7, max_length=7)
    description: Optional[str] = Field(None, max_length=200)

class TagResponse(TagBase):
    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ProjectTagsUpdate(BaseModel):
    tag_ids: List[int] = []

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
    owner_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

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
    owner_id: int
    created_at: datetime
    updated_at: datetime
    time_entries: List[TimeEntryResponse] = []

    class Config:
        from_attributes = True

class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    budget: Optional[float] = Field(None, ge=0)
    hourly_rate: Optional[float] = Field(None, ge=0)
    received_amount: Optional[float] = Field(0.0, ge=0)

class ProjectCreate(ProjectBase):
    tag_ids: Optional[List[int]] = []

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    budget: Optional[float] = Field(None, ge=0)
    hourly_rate: Optional[float] = Field(None, ge=0)
    received_amount: Optional[float] = Field(None, ge=0)

class ProjectResponse(ProjectBase):
    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime
    tasks: List[TaskResponse] = []
    tags: List[TagResponse] = []
    total_duration: float = 0.0
    actual_hourly_rate: Optional[float] = None
    profit_status: Optional[str] = None
    profit_amount: Optional[float] = None

    class Config:
        from_attributes = True

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

class PeriodStatsRequest(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    period_type: Optional[str] = Field("week", description="可选值: week, month, quarter, year, custom")

class HourlyRateTrendItem(BaseModel):
    date: str
    hourly_rate: Optional[float]
    total_duration: float
    total_received: float

class ProjectStatsItem(BaseModel):
    project_id: int
    project_name: str
    total_duration: float
    total_received: float
    hourly_rate: Optional[float]

class TagStatsItem(BaseModel):
    tag_id: int
    tag_name: str
    tag_color: str
    total_duration: float
    total_received: float
    project_count: int

class PeriodStatsResponse(BaseModel):
    start_date: date
    end_date: date
    period_type: str
    total_duration: float
    total_received_amount: float
    overall_hourly_rate: Optional[float]
    total_projects: int
    total_tasks: int
    total_completed_tasks: int
    hourly_rate_trend: List[HourlyRateTrendItem]
    project_stats: List[ProjectStatsItem]
    tag_stats: List[TagStatsItem]

    class Config:
        from_attributes = True
