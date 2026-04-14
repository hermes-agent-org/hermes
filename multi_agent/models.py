"""
多智能体治理 - 数据模型

定义 Agent、Task、Approval 等核心数据模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import json


class AgentStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    PAUSED = "paused"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    BLOCKED = "blocked"
    RETRYING = "retrying"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SNOOZED = "snoozed"
    EXPIRED = "expired"


@dataclass
class Agent:
    """Agent 状态模型"""
    agent_id: str
    role: str
    department: str = "general"
    status: AgentStatus = AgentStatus.OFFLINE
    current_task: Optional[str] = None
    success_rate: float = 1.0
    queue_length: int = 0
    last_heartbeat: Optional[datetime] = None
    recent_incidents: List[Dict] = field(default_factory=list)
    open_approvals: int = 0
    tools_in_use: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "department": self.department,
            "status": self.status.value,
            "current_task": self.current_task,
            "success_rate": self.success_rate,
            "queue_length": self.queue_length,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "recent_incidents": self.recent_incidents[-10:],
            "open_approvals": self.open_approvals,
            "tools_in_use": self.tools_in_use,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Agent":
        last_heartbeat = None
        if data.get("last_heartbeat"):
            last_heartbeat = datetime.fromisoformat(data["last_heartbeat"])
        created_at = datetime.fromisoformat(data.get("created_at", datetime.now().isoformat()))
        return cls(
            agent_id=data["agent_id"],
            role=data["role"],
            department=data.get("department", "general"),
            status=AgentStatus(data.get("status", "offline")),
            current_task=data.get("current_task"),
            success_rate=data.get("success_rate", 1.0),
            queue_length=data.get("queue_length", 0),
            last_heartbeat=last_heartbeat,
            recent_incidents=data.get("recent_incidents", []),
            open_approvals=data.get("open_approvals", 0),
            tools_in_use=data.get("tools_in_use", []),
            created_at=created_at,
            metadata=data.get("metadata", {}),
        )


@dataclass
class Task:
    """任务模型"""
    task_id: str
    source_agent: str
    task_type: str
    description: str
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.QUEUED
    current_step: str = ""
    last_action: str = ""
    next_action: str = ""
    waiting_approval: bool = False
    approval_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    log_entries: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "source_agent": self.source_agent,
            "task_type": self.task_type,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "current_step": self.current_step,
            "last_action": self.last_action,
            "next_action": self.next_action,
            "waiting_approval": self.waiting_approval,
            "approval_id": self.approval_id,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "log_entries": self.log_entries[-50:],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Task":
        created_at = datetime.fromisoformat(data.get("created_at", datetime.now().isoformat()))
        started_at = None
        if data.get("started_at"):
            started_at = datetime.fromisoformat(data["started_at"])
        completed_at = None
        if data.get("completed_at"):
            completed_at = datetime.fromisoformat(data["completed_at"])
        return cls(
            task_id=data["task_id"],
            source_agent=data["source_agent"],
            task_type=data["task_type"],
            description=data.get("description", ""),
            priority=TaskPriority(data.get("priority", "normal")),
            status=TaskStatus(data.get("status", "queued")),
            current_step=data.get("current_step", ""),
            last_action=data.get("last_action", ""),
            next_action=data.get("next_action", ""),
            waiting_approval=data.get("waiting_approval", False),
            approval_id=data.get("approval_id"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            created_at=created_at,
            started_at=started_at,
            completed_at=completed_at,
            result=data.get("result"),
            error=data.get("error"),
            log_entries=data.get("log_entries", []),
            metadata=data.get("metadata", {}),
        )

    def add_log(self, action: str, details: str = "", level: str = "info"):
        self.log_entries.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details,
            "level": level,
        })


@dataclass
class Approval:
    """审批模型"""
    approval_id: str
    requested_by: str
    action_type: str
    risk_level: RiskLevel
    target_object: str
    preview_content: str
    reason: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    decision_reason: Optional[str] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "approval_id": self.approval_id,
            "requested_by": self.requested_by,
            "action_type": self.action_type,
            "risk_level": self.risk_level.value,
            "target_object": self.target_object,
            "preview_content": self.preview_content,
            "reason": self.reason,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "decided_by": self.decided_by,
            "decision_reason": self.decision_reason,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Approval":
        created_at = datetime.fromisoformat(data.get("created_at", datetime.now().isoformat()))
        decided_at = None
        if data.get("decided_at"):
            decided_at = datetime.fromisoformat(data["decided_at"])
        expires_at = None
        if data.get("expires_at"):
            expires_at = datetime.fromisoformat(data["expires_at"])
        return cls(
            approval_id=data["approval_id"],
            requested_by=data["requested_by"],
            action_type=data["action_type"],
            risk_level=RiskLevel(data.get("risk_level", "medium")),
            target_object=data["target_object"],
            preview_content=data.get("preview_content", ""),
            reason=data.get("reason", ""),
            status=ApprovalStatus(data.get("status", "pending")),
            created_at=created_at,
            decided_at=decided_at,
            decided_by=data.get("decided_by"),
            decision_reason=data.get("decision_reason"),
            expires_at=expires_at,
            metadata=data.get("metadata", {}),
        )

    def is_expired(self) -> bool:
        if self.expires_at and datetime.now() > self.expires_at:
            return True
        return False


@dataclass
class AuditLog:
    """审计日志模型"""
    log_id: str
    event_type: str
    actor: str
    action: str
    target: Optional[str]
    details: Dict[str, Any]
    risk_level: RiskLevel = RiskLevel.LOW
    created_at: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "log_id": self.log_id,
            "event_type": self.event_type,
            "actor": self.actor,
            "action": self.action,
            "target": self.target,
            "details": self.details,
            "risk_level": self.risk_level.value,
            "created_at": self.created_at.isoformat(),
            "session_id": self.session_id,
        }


@dataclass
class RiskAlert:
    """风险告警模型"""
    alert_id: str
    alert_type: str
    severity: RiskLevel
    message: str
    source: str
    created_at: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolution: Optional[str] = None
    related_task_id: Optional[str] = None
    related_agent_id: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type,
            "severity": self.severity.value,
            "message": self.message,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution": self.resolution,
            "related_task_id": self.related_task_id,
            "related_agent_id": self.related_agent_id,
        }
