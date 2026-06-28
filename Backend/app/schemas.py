from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


# --- Enums ---

class ObligationStatusEnum(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ADDRESSED = "addressed"
    OVERDUE = "overdue"
    NOT_APPLICABLE = "not_applicable"


class RiskLevelEnum(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# --- Contract Schemas (preserved) ---

class ContractBase(BaseModel):
    filename: str


class ContractCreate(ContractBase):
    pass


class ContractResponse(ContractBase):
    id: int
    uploaded_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    extracted_data: Optional[Dict[str, Any]] = None
    layout_analysis: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# --- Regulatory Update Schemas ---

class RegulatoryUpdateResponse(BaseModel):
    id: int
    title: str
    source: str
    published_date: datetime
    summary: str
    link: str
    category: Optional[str] = None
    obligations: Optional[List[Dict[str, Any]]] = None
    is_processed: bool = False
    fetched_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Obligation Schemas ---

class ObligationBase(BaseModel):
    text: str
    deadline: Optional[str] = None
    severity: RiskLevelEnum = RiskLevelEnum.MEDIUM
    category: Optional[str] = None
    affected_entity: Optional[str] = None


class ObligationCreate(ObligationBase):
    regulatory_update_id: int


class ObligationResponse(ObligationBase):
    id: int
    regulatory_update_id: int
    status: ObligationStatusEnum = ObligationStatusEnum.PENDING
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ObligationStatusUpdate(BaseModel):
    status: ObligationStatusEnum


# --- Impact Assessment Schemas ---

class ImpactAssessmentBase(BaseModel):
    affected_policies: Optional[List[str]] = None
    risk_level: RiskLevelEnum = RiskLevelEnum.MEDIUM
    action_items: Optional[List[Dict[str, Any]]] = None
    estimated_effort: Optional[str] = None
    affected_departments: Optional[List[str]] = None
    assessment_notes: Optional[str] = None


class ImpactAssessmentCreate(ImpactAssessmentBase):
    obligation_id: int


class ImpactAssessmentResponse(ImpactAssessmentBase):
    id: int
    obligation_id: int
    assessed_at: datetime
    assessed_by: str = "ai_agent"

    class Config:
        from_attributes = True


# --- Compliance Report Schemas ---

class ComplianceReportResponse(BaseModel):
    id: int
    title: str
    report_type: str
    content: Dict[str, Any]
    summary: Optional[str] = None
    total_obligations: int = 0
    critical_findings: int = 0
    generated_at: datetime

    class Config:
        from_attributes = True


# --- Monitoring Schemas ---

class MonitoringStatusResponse(BaseModel):
    is_running: bool
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None
    updates_found_last_run: int = 0
    next_run_at: Optional[datetime] = None
    poll_interval_hours: int = 6


class MonitoringRunResponse(BaseModel):
    id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    source: str
    updates_found: int = 0
    obligations_extracted: int = 0
    errors: Optional[List[str]] = None

    class Config:
        from_attributes = True


# --- LRR Dashboard ---

class LRRDashboardStats(BaseModel):
    total_regulatory_updates: int = 0
    total_obligations: int = 0
    pending_obligations: int = 0
    critical_obligations: int = 0
    high_risk_obligations: int = 0
    total_impact_assessments: int = 0
    total_reports: int = 0
    monitoring_active: bool = False
    last_monitoring_run: Optional[datetime] = None


# --- Agent Schemas ---

class AgentRequest(BaseModel):
    query: str
    run_full_pipeline: bool = False  # If true, runs the complete LRR cycle


class AgentResponse(BaseModel):
    response: str
    sources: Optional[List[str]] = None
    agent_used: Optional[str] = None
    guardrail_applied: bool = False
    processing_steps: Optional[List[Dict[str, Any]]] = None


class AgentInfo(BaseModel):
    name: str
    description: str
    capabilities: List[str]
    tools: List[str]


# --- Guardrail Schemas ---

class GuardrailEventResponse(BaseModel):
    id: int
    event_type: str
    validator_name: Optional[str] = None
    passed: bool
    violation_details: Optional[Dict[str, Any]] = None
    action_taken: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class ValidationResult(BaseModel):
    is_valid: bool
    original_text: str
    validated_text: str
    violations: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# --- Full LRR Cycle Response ---

class LRRCycleResponse(BaseModel):
    monitoring_run_id: int
    updates_found: int
    obligations_extracted: int
    impact_assessments_created: int
    report_id: Optional[int] = None
    summary: str
    errors: List[str] = Field(default_factory=list)
