"""
多智能体治理系统

提供 Agent 编排、任务调度、审批 Gating、审计日志等核心功能
"""

from .models import (
    Agent, AgentStatus,
    Task, TaskStatus, TaskPriority,
    Approval, ApprovalStatus,
    RiskLevel,
    AuditLog,
    RiskAlert,
)
from .registry import AgentRegistry, get_registry
from .queue import TaskQueue, get_queue
from .approvals import ApprovalGate, get_gate
from .audit import AuditLogger, get_logger


__all__ = [
    # Models
    "Agent", "AgentStatus",
    "Task", "TaskStatus", "TaskPriority",
    "Approval", "ApprovalStatus",
    "RiskLevel",
    "AuditLog",
    "RiskAlert",
    # Registry
    "AgentRegistry", "get_registry",
    # Queue
    "TaskQueue", "get_queue",
    # Approvals
    "ApprovalGate", "get_gate",
    # Audit
    "AuditLogger", "get_logger",
]

__version__ = "0.1.0"
