from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


BASE_DIR = Path(__file__).resolve().parent


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url
    return f"sqlite:///{BASE_DIR / 'deploy_lab.db'}"


DATABASE_URL = _database_url()
CONNECT_ARGS = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=CONNECT_ARGS, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=160)
    status: str = Field(default="queued", pattern="^(queued|running|done)$")
    notes: str = ""


class TaskRead(BaseModel):
    id: int
    title: str
    status: str
    notes: str
    created_at: datetime


class HealthRead(BaseModel):
    ok: bool
    app: str
    database: str
    utc: datetime


class StatsRead(BaseModel):
    total: int
    queued: int
    running: int
    done: int


def create_app() -> FastAPI:
    app = FastAPI(title=os.getenv("APP_NAME", "Deploy Lab API"))

    cors_origins = {
        value.strip()
        for value in (
            os.getenv("FRONTEND_URL", ""),
            os.getenv("CORS_ORIGIN", ""),
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        )
        if value.strip()
    }
    if "*" in cors_origins:
        allow_origins = ["*"]
        allow_credentials = False
    else:
        allow_origins = sorted(cors_origins)
        allow_credentials = True

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def startup() -> None:
        Base.metadata.create_all(bind=engine)
        _seed_if_empty()

    @app.get("/health", response_model=HealthRead)
    def health() -> HealthRead:
        with db_session() as db:
            db.execute(select(func.count(Task.id))).scalar_one()
        return HealthRead(
            ok=True,
            app=os.getenv("APP_NAME", "Deploy Lab API"),
            database="postgres" if "postgres" in DATABASE_URL else "sqlite",
            utc=datetime.now(timezone.utc),
        )

    @app.get("/api/tasks", response_model=list[TaskRead])
    def list_tasks() -> list[TaskRead]:
        with db_session() as db:
            rows = db.scalars(select(Task).order_by(Task.id)).all()
            return [TaskRead.model_validate(row, from_attributes=True) for row in rows]

    @app.post("/api/tasks", response_model=TaskRead, status_code=201)
    def create_task(payload: TaskCreate) -> TaskRead:
        with db_session() as db:
            task = Task(title=payload.title, status=payload.status, notes=payload.notes)
            db.add(task)
            db.commit()
            db.refresh(task)
            return TaskRead.model_validate(task, from_attributes=True)

    @app.patch("/api/tasks/{task_id}/status/{status}", response_model=TaskRead)
    def update_status(task_id: int, status: str) -> TaskRead:
        if status not in {"queued", "running", "done"}:
            raise HTTPException(status_code=422, detail="Invalid status")
        with db_session() as db:
            task = db.get(Task, task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            task.status = status
            db.commit()
            db.refresh(task)
            return TaskRead.model_validate(task, from_attributes=True)

    @app.get("/api/stats", response_model=StatsRead)
    def stats() -> StatsRead:
        with db_session() as db:
            rows = db.scalars(select(Task)).all()
            counts = {"queued": 0, "running": 0, "done": 0}
            for task in rows:
                counts[task.status] = counts.get(task.status, 0) + 1
            return StatsRead(total=len(rows), **counts)

    return app


@contextmanager
def db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_if_empty() -> None:
    with db_session() as db:
        count = db.execute(select(func.count(Task.id))).scalar_one()
        if count:
            return
        db.add_all(
            [
                Task(title="Provision database", status="done", notes="Neon or local SQLite"),
                Task(title="Deploy API", status="running", notes="Railway/Render target"),
                Task(title="Deploy dashboard", status="queued", notes="Vercel target"),
            ]
        )
        db.commit()


app = create_app()
