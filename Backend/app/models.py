from sqlalchemy import (
    Column, Integer, String, Text, DateTime, JSON,
    ForeignKey, Float, Boolean, Enum as SQLEnum
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base
import enum


# --- Enums ---

class ObligationStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ADDRESSED = "addressed"
    OVERDUE = "overdue"
    NOT_APPLICABLE = "not_applicable"


class RiskLevel(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class MonitoringRunStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


# --- Existing Tables (preserved) ---

class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="uploaded")  # uploaded, processing, completed, failed
    extracted_data = Column(JSON, nullable=True)  # Will store clauses, risks
    raw_text = Column(Text, nullable=True)
    layout_analysis = Column(JSON, nullable=True)  # LayoutLMv3 results


class RegulatoryUpdate(Base):
    __tablename__ = "regulatory_updates"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    source = Column(String)  # e.g., 'RBI'
    published_date = Column(DateTime(timezone=True))
    summary = Column(Text)
    link = Column(String, unique=True)  # Unique to avoid duplicates
    category = Column(String, nullable=True)  # e.g., 'Master Direction', 'Circular', 'Notification'
    full_text = Column(Text, nullable=True)  # Full scraped content
    obligations = Column(JSON, nullable=True)  # Extracted obligations (legacy field)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    is_processed = Column(Boolean, default=False)

    # Relationships
    extracted_obligations = relationship("Obligation", back_populates="regulatory_update")


# --- New Tables ---

class Obligation(Base):
    """Individual regulatory obligation extracted from a RegulatoryUpdate."""
    __tablename__ = "obligations"

    id = Column(Integer, primary_key=True, index=True)
    regulatory_update_id = Column(Integer, ForeignKey("regulatory_updates.id"), nullable=False)
    text = Column(Text, nullable=False)  # The obligation text
    deadline = Column(String, nullable=True)  # Deadline description or date
    severity = Column(String, default=RiskLevel.MEDIUM.value)
    category = Column(String, nullable=True)  # e.g., 'Capital Adequacy', 'KYC', 'Lending'
    affected_entity = Column(String, nullable=True)  # e.g., 'Commercial Banks', 'NBFCs'
    status = Column(String, default=ObligationStatus.PENDING.value)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    regulatory_update = relationship("RegulatoryUpdate", back_populates="extracted_obligations")
    impact_assessments = relationship("ImpactAssessment", back_populates="obligation")


class ImpactAssessment(Base):
    """Impact assessment for a specific obligation."""
    __tablename__ = "impact_assessments"

    id = Column(Integer, primary_key=True, index=True)
    obligation_id = Column(Integer, ForeignKey("obligations.id"), nullable=False)
    affected_policies = Column(JSON, nullable=True)  # List of policy names/IDs affected
    risk_level = Column(String, default=RiskLevel.MEDIUM.value)
    action_items = Column(JSON, nullable=True)  # List of required actions
    estimated_effort = Column(String, nullable=True)  # e.g., "2-4 weeks"
    affected_departments = Column(JSON, nullable=True)  # e.g., ["Compliance", "Risk"]
    assessment_notes = Column(Text, nullable=True)
    assessed_at = Column(DateTime(timezone=True), server_default=func.now())
    assessed_by = Column(String, default="ai_agent")  # 'ai_agent' or user ID

    # Relationships
    obligation = relationship("Obligation", back_populates="impact_assessments")


class ComplianceReport(Base):
    """Generated compliance reports from the multi-agent pipeline."""
    __tablename__ = "compliance_reports"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    report_type = Column(String, default="full_cycle")  # 'full_cycle', 'impact_only', 'obligation_only'
    content = Column(JSON, nullable=False)  # Structured report content
    summary = Column(Text, nullable=True)  # Executive summary
    total_obligations = Column(Integer, default=0)
    critical_findings = Column(Integer, default=0)
    agent_run_id = Column(String, nullable=True)  # For tracing
    generated_at = Column(DateTime(timezone=True), server_default=func.now())


class MonitoringRun(Base):
    """Tracks each LRR monitoring run."""
    __tablename__ = "monitoring_runs"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default=MonitoringRunStatus.RUNNING.value)
    source = Column(String, default="rbi")  # Which source was polled
    updates_found = Column(Integer, default=0)
    obligations_extracted = Column(Integer, default=0)
    errors = Column(JSON, nullable=True)  # List of error messages
    run_metadata = Column(JSON, nullable=True)  # Additional run info


class GuardrailEvent(Base):
    """Audit trail for all guardrail validations."""
    __tablename__ = "guardrail_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, nullable=False)  # 'input_validation', 'output_validation'
    validator_name = Column(String, nullable=True)  # Which validator triggered
    input_text = Column(Text, nullable=True)  # Truncated input
    output_text = Column(Text, nullable=True)  # Truncated output
    passed = Column(Boolean, default=True)
    violation_details = Column(JSON, nullable=True)
    action_taken = Column(String, nullable=True)  # 'blocked', 'warning_appended', 'passed'
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
