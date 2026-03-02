"""SQLite database layer using SQLAlchemy async with aiosqlite."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Integer, String, Text,
    create_engine, event,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


# ── Table Definitions ────────────────────────────────────────

class TaskRow(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    repo_path = Column(String(1000), nullable=False)
    policy_path = Column(String(1000), default="configs/policy.yaml")
    status = Column(String(50), default="open")
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RunRow(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    status = Column(String(50), default="pending")
    current_state = Column(String(50), default="pending")
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)


class RunStateRow(Base):
    __tablename__ = "run_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("runs.id"), nullable=False)
    state = Column(String(50), nullable=False)
    entered_at = Column(DateTime, default=datetime.utcnow)
    exited_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    metadata_json = Column(Text, default="{}")


class AgentOutputRow(Base):
    __tablename__ = "agent_outputs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("runs.id"), nullable=False)
    agent_name = Column(String(100), nullable=False)
    output_json = Column(Text, nullable=False)
    schema_valid = Column(Integer, default=1)  # SQLite bool
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class ValidationResultRow(Base):
    __tablename__ = "validation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("runs.id"), nullable=False)
    tool_name = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    passed = Column(Integer, default=0)
    return_code = Column(Integer, default=0)
    duration_seconds = Column(Float, default=0.0)
    summary = Column(Text, default="")
    findings_count = Column(Integer, default=0)
    stdout_path = Column(String(1000), default="")
    stderr_path = Column(String(1000), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class RiskAssessmentRow(Base):
    __tablename__ = "risk_assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("runs.id"), nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String(20), nullable=False)
    explanation = Column(Text, default="")
    contributing_factors_json = Column(Text, default="[]")
    gate_recommendation = Column(String(50), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class DeploymentRow(Base):
    __tablename__ = "deployments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"), nullable=False)
    deployment_type = Column(String(50), default="canary")
    status = Column(String(50), default="pending")
    baseline_metrics_json = Column(Text, default="{}")
    canary_metrics_json = Column(Text, default="{}")
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    rollback_triggered = Column(Integer, default=0)
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)


class IncidentRow(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"), nullable=False)
    deployment_id = Column(String, ForeignKey("deployments.id"), nullable=True)
    anomaly_detected = Column(Integer, default=0)
    action_taken = Column(String(50), default="")
    summary = Column(Text, default="")
    postmortem_draft = Column(Text, default="")
    metrics_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)


class ArtifactRow(Base):
    __tablename__ = "artifacts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"), nullable=False)
    artifact_type = Column(String(50), nullable=False)
    file_path = Column(String(1000), nullable=False)
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Database Manager ──────────────────────────────────────────

class Database:
    """Manages SQLite database connections and operations."""

    def __init__(self, db_path: str = "control_tower.db"):
        self.db_path = db_path
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            connect_args={"check_same_thread": False},
        )
        # Enable WAL mode for better concurrency
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        self.SessionLocal = sessionmaker(bind=self.engine)

    def create_tables(self):
        """Create all tables."""
        Base.metadata.create_all(self.engine)

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    # ── Task Operations ───────────────────────────────────────

    def create_task(
        self,
        title: str,
        description: str,
        repo_path: str,
        policy_path: str = "configs/policy.yaml",
        metadata: dict[str, Any] | None = None,
    ) -> TaskRow:
        with self.get_session() as session:
            task = TaskRow(
                id=str(uuid.uuid4()),
                title=title,
                description=description,
                repo_path=repo_path,
                policy_path=policy_path,
                metadata_json=json.dumps(metadata or {}),
            )
            session.add(task)
            session.commit()
            session.refresh(task)
            return task

    def get_task(self, task_id: str) -> TaskRow | None:
        with self.get_session() as session:
            return session.query(TaskRow).filter(TaskRow.id == task_id).first()

    def list_tasks(self, limit: int = 50) -> list[TaskRow]:
        with self.get_session() as session:
            return session.query(TaskRow).order_by(TaskRow.created_at.desc()).limit(limit).all()

    # ── Run Operations ────────────────────────────────────────

    def create_run(self, task_id: str, metadata: dict[str, Any] | None = None) -> RunRow:
        with self.get_session() as session:
            run = RunRow(
                id=str(uuid.uuid4()),
                task_id=task_id,
                status="pending",
                current_state="pending",
                started_at=datetime.utcnow(),
                metadata_json=json.dumps(metadata or {}),
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return run

    def get_run(self, run_id: str) -> RunRow | None:
        with self.get_session() as session:
            return session.query(RunRow).filter(RunRow.id == run_id).first()

    def update_run_status(
        self, run_id: str, status: str, state: str | None = None, error: str | None = None
    ):
        with self.get_session() as session:
            run = session.query(RunRow).filter(RunRow.id == run_id).first()
            if run:
                run.status = status
                if state:
                    run.current_state = state
                if error:
                    run.error_message = error
                if status in ("completed", "failed", "blocked"):
                    run.finished_at = datetime.utcnow()
                session.commit()

    def list_runs(self, task_id: str | None = None, limit: int = 50) -> list[RunRow]:
        with self.get_session() as session:
            query = session.query(RunRow)
            if task_id:
                query = query.filter(RunRow.task_id == task_id)
            return query.order_by(RunRow.created_at.desc()).limit(limit).all()

    # ── Run State Operations ──────────────────────────────────

    def record_state_transition(
        self, run_id: str, state: str, metadata: dict[str, Any] | None = None
    ) -> RunStateRow:
        with self.get_session() as session:
            # Close previous state
            prev = (
                session.query(RunStateRow)
                .filter(RunStateRow.run_id == run_id, RunStateRow.exited_at.is_(None))
                .first()
            )
            now = datetime.utcnow()
            if prev:
                prev.exited_at = now
                if prev.entered_at:
                    prev.duration_seconds = (now - prev.entered_at).total_seconds()

            new_state = RunStateRow(
                run_id=run_id,
                state=state,
                entered_at=now,
                metadata_json=json.dumps(metadata or {}),
            )
            session.add(new_state)
            session.commit()
            session.refresh(new_state)
            return new_state

    # ── Agent Output Operations ───────────────────────────────

    def store_agent_output(
        self,
        run_id: str,
        agent_name: str,
        output: dict[str, Any],
        schema_valid: bool = True,
        retry_count: int = 0,
    ) -> AgentOutputRow:
        with self.get_session() as session:
            row = AgentOutputRow(
                run_id=run_id,
                agent_name=agent_name,
                output_json=json.dumps(output),
                schema_valid=1 if schema_valid else 0,
                retry_count=retry_count,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    # ── Validation Operations ─────────────────────────────────

    def store_validation_result(
        self,
        run_id: str,
        tool_name: str,
        status: str,
        passed: bool,
        return_code: int = 0,
        duration_seconds: float = 0.0,
        summary: str = "",
        findings_count: int = 0,
        stdout_path: str = "",
        stderr_path: str = "",
    ) -> ValidationResultRow:
        with self.get_session() as session:
            row = ValidationResultRow(
                run_id=run_id,
                tool_name=tool_name,
                status=status,
                passed=1 if passed else 0,
                return_code=return_code,
                duration_seconds=duration_seconds,
                summary=summary,
                findings_count=findings_count,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def get_validation_results(self, run_id: str) -> list[ValidationResultRow]:
        with self.get_session() as session:
            return (
                session.query(ValidationResultRow)
                .filter(ValidationResultRow.run_id == run_id)
                .all()
            )

    # ── Risk Assessment Operations ────────────────────────────

    def store_risk_assessment(
        self,
        run_id: str,
        risk_score: float,
        risk_level: str,
        explanation: str = "",
        contributing_factors: list[dict] | None = None,
        gate_recommendation: str = "",
    ) -> RiskAssessmentRow:
        with self.get_session() as session:
            row = RiskAssessmentRow(
                run_id=run_id,
                risk_score=risk_score,
                risk_level=risk_level,
                explanation=explanation,
                contributing_factors_json=json.dumps(contributing_factors or []),
                gate_recommendation=gate_recommendation,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    # ── Deployment Operations ─────────────────────────────────

    def create_deployment(
        self, run_id: str, deployment_type: str = "canary"
    ) -> DeploymentRow:
        with self.get_session() as session:
            row = DeploymentRow(
                id=str(uuid.uuid4()),
                run_id=run_id,
                deployment_type=deployment_type,
                status="pending",
                started_at=datetime.utcnow(),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def update_deployment(
        self,
        deployment_id: str,
        status: str | None = None,
        baseline_metrics: dict | None = None,
        canary_metrics: dict | None = None,
        rollback_triggered: bool = False,
    ):
        with self.get_session() as session:
            dep = session.query(DeploymentRow).filter(DeploymentRow.id == deployment_id).first()
            if dep:
                if status:
                    dep.status = status
                if baseline_metrics:
                    dep.baseline_metrics_json = json.dumps(baseline_metrics)
                if canary_metrics:
                    dep.canary_metrics_json = json.dumps(canary_metrics)
                if rollback_triggered:
                    dep.rollback_triggered = 1
                if status in ("completed", "failed", "rolled_back"):
                    dep.finished_at = datetime.utcnow()
                session.commit()

    # ── Incident Operations ───────────────────────────────────

    def create_incident(
        self,
        run_id: str,
        deployment_id: str | None = None,
        anomaly_detected: bool = False,
        action_taken: str = "",
        summary: str = "",
        postmortem_draft: str = "",
        metrics: list[dict] | None = None,
    ) -> IncidentRow:
        with self.get_session() as session:
            row = IncidentRow(
                id=str(uuid.uuid4()),
                run_id=run_id,
                deployment_id=deployment_id,
                anomaly_detected=1 if anomaly_detected else 0,
                action_taken=action_taken,
                summary=summary,
                postmortem_draft=postmortem_draft,
                metrics_json=json.dumps(metrics or []),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    # ── Artifact Operations ───────────────────────────────────

    def store_artifact(
        self,
        run_id: str,
        artifact_type: str,
        file_path: str,
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactRow:
        with self.get_session() as session:
            row = ArtifactRow(
                id=str(uuid.uuid4()),
                run_id=run_id,
                artifact_type=artifact_type,
                file_path=file_path,
                metadata_json=json.dumps(metadata or {}),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def get_artifacts(self, run_id: str) -> list[ArtifactRow]:
        with self.get_session() as session:
            return (
                session.query(ArtifactRow)
                .filter(ArtifactRow.run_id == run_id)
                .order_by(ArtifactRow.created_at)
                .all()
            )
