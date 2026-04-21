from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Table
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

project_tag = Table(
    "project_tag",
    Base.metadata,
    Column("project_id", Integer, ForeignKey("projects.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True)
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="owner", cascade="all, delete-orphan")
    time_entries = relationship("TimeEntry", back_populates="owner", cascade="all, delete-orphan")
    tags = relationship("Tag", back_populates="owner", cascade="all, delete-orphan")

class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    color = Column(String, default="#6366f1")
    description = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="tags")
    projects = relationship("Project", secondary=project_tag, back_populates="tags")

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    budget = Column(Float, nullable=True)
    hourly_rate = Column(Float, nullable=True)
    received_amount = Column(Float, default=0.0)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="projects")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    time_entries = relationship("TimeEntry", back_populates="project", cascade="all, delete-orphan")
    tags = relationship("Tag", secondary=project_tag, back_populates="projects")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    is_completed = Column(Boolean, default=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="tasks")
    owner = relationship("User", back_populates="tasks")
    time_entries = relationship("TimeEntry", back_populates="task", cascade="all, delete-orphan")

class TimeEntry(Base):
    __tablename__ = "time_entries"

    id = Column(Integer, primary_key=True, index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    duration = Column(Float, default=0.0)
    is_running = Column(Boolean, default=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    task = relationship("Task", back_populates="time_entries")
    project = relationship("Project", back_populates="time_entries")
    owner = relationship("User", back_populates="time_entries")
