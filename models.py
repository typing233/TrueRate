from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    budget = Column(Float, nullable=True)  # 总预算
    hourly_rate = Column(Float, nullable=True)  # 时薪标准
    received_amount = Column(Float, default=0.0)  # 已收款金额
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系：一个项目有多个任务
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    
    # 关系：一个项目有多个时间记录（通过任务）
    time_entries = relationship("TimeEntry", back_populates="project", cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    is_completed = Column(Boolean, default=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系：一个任务属于一个项目
    project = relationship("Project", back_populates="tasks")
    
    # 关系：一个任务有多个时间记录
    time_entries = relationship("TimeEntry", back_populates="task", cascade="all, delete-orphan")

class TimeEntry(Base):
    __tablename__ = "time_entries"

    id = Column(Integer, primary_key=True, index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    duration = Column(Float, default=0.0)  # 持续时间，单位：小时
    is_running = Column(Boolean, default=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系：一个时间记录属于一个任务
    task = relationship("Task", back_populates="time_entries")
    
    # 关系：一个时间记录属于一个项目
    project = relationship("Project", back_populates="time_entries")
