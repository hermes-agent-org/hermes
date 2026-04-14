"""
多智能体治理 - 审计日志系统

记录所有关键动作和决策
"""

import json
import uuid
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
from collections import defaultdict

from .models import AuditLog, RiskLevel


class AuditLogger:
    """
    审计日志系统
    
    负责：
    - 记录所有关键事件
    - 日志查询
    - 日志归档
    """

    def __init__(self, state_path: str = "~/.hermes/multi_agent/audit_logs.json",
                 max_logs: int = 10000):
        self.state_path = Path(state_path).expanduser()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._logs: List[AuditLog] = []
        self._max_logs = max_logs
        self._lock = threading.RLock()
        self._load_state()

    def _load_state(self):
        """从磁盘加载状态"""
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for log_data in data.get("logs", []):
                        log = AuditLog(**log_data)
                        self._logs.append(log)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[AuditLogger] 加载状态失败：{e}")

    def _save_state(self):
        """保存状态到磁盘"""
        with self._lock:
            data = {
                "updated_at": datetime.now().isoformat(),
                "logs": [log.to_dict() for log in self._logs[-self._max_logs:]],
            }
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    def log(self, event_type: str, actor: str, action: str,
            target: Optional[str] = None, details: Optional[Dict] = None,
            risk_level: RiskLevel = RiskLevel.LOW,
            session_id: Optional[str] = None) -> AuditLog:
        """
        记录审计日志
        
        Args:
            event_type: 事件类型
            actor: 执行者
            action: 动作
            target: 目标对象
            details: 详细信息
            risk_level: 风险等级
            session_id: 会话 ID
        
        Returns:
            创建的审计日志
        """
        log_id = str(uuid.uuid4())[:8]
        log = AuditLog(
            log_id=log_id,
            event_type=event_type,
            actor=actor,
            action=action,
            target=target,
            details=details or {},
            risk_level=risk_level,
            session_id=session_id,
        )
        
        with self._lock:
            self._logs.append(log)
            if len(self._logs) > self._max_logs:
                self._logs = self._logs[-self._max_logs:]
            self._save_state()
        
        return log

    def log_task_created(self, task_id: str, source_agent: str, 
                         task_type: str, session_id: str = None):
        """记录任务创建"""
        return self.log(
            event_type="task",
            actor=source_agent,
            action="create_task",
            target=task_id,
            details={"task_type": task_type},
            session_id=session_id,
        )

    def log_task_completed(self, task_id: str, source_agent: str,
                           success: bool, session_id: str = None):
        """记录任务完成"""
        return self.log(
            event_type="task",
            actor=source_agent,
            action="complete_task" if success else "fail_task",
            target=task_id,
            details={"success": success},
            session_id=session_id,
        )

    def log_approval_requested(self, approval_id: str, requester: str,
                                action_type: str, session_id: str = None):
        """记录审批请求"""
        return self.log(
            event_type="approval",
            actor=requester,
            action="request_approval",
            target=approval_id,
            details={"action_type": action_type},
            risk_level=RiskLevel.MEDIUM,
            session_id=session_id,
        )

    def log_approval_decided(self, approval_id: str, decider: str,
                              approved: bool, session_id: str = None):
        """记录审批决策"""
        return self.log(
            event_type="approval",
            actor=decider,
            action="approve" if approved else "reject",
            target=approval_id,
            details={"approved": approved},
            session_id=session_id,
        )

    def log_agent_registered(self, agent_id: str, role: str,
                              department: str, session_id: str = None):
        """记录 Agent 注册"""
        return self.log(
            event_type="agent",
            actor="system",
            action="register_agent",
            target=agent_id,
            details={"role": role, "department": department},
            session_id=session_id,
        )

    def log_agent_action(self, agent_id: str, action: str,
                          target: str, details: Dict = None,
                          session_id: str = None):
        """记录 Agent 动作"""
        return self.log(
            event_type="agent_action",
            actor=agent_id,
            action=action,
            target=target,
            details=details or {},
            session_id=session_id,
        )

    def log_risk_event(self, event_type: str, source: str,
                        message: str, severity: RiskLevel,
                        details: Dict = None, session_id: str = None):
        """记录风险事件"""
        return self.log(
            event_type="risk",
            actor=source,
            action=event_type,
            target=None,
            details={"message": message, **(details or {})},
            risk_level=severity,
            session_id=session_id,
        )

    def query(self, event_type: Optional[str] = None,
              actor: Optional[str] = None,
              target: Optional[str] = None,
              risk_level: Optional[RiskLevel] = None,
              since: Optional[datetime] = None,
              until: Optional[datetime] = None,
              limit: int = 100) -> List[AuditLog]:
        """
        查询审计日志
        
        Args:
            event_type: 按事件类型筛选
            actor: 按执行者筛选
            target: 按目标筛选
            risk_level: 按风险等级筛选
            since: 起始时间
            until: 结束时间
            limit: 返回数量限制
        
        Returns:
            审计日志列表
        """
        with self._lock:
            logs = self._logs.copy()
        
        if event_type:
            logs = [l for l in logs if l.event_type == event_type]
        if actor:
            logs = [l for l in logs if l.actor == actor]
        if target:
            logs = [l for l in logs if l.target == target]
        if risk_level:
            logs = [l for l in logs if l.risk_level == risk_level]
        if since:
            logs = [l for l in logs if l.created_at >= since]
        if until:
            logs = [l for l in logs if l.created_at <= until]
        
        logs.sort(key=lambda l: l.created_at, reverse=True)
        return logs[:limit]

    def get_recent(self, limit: int = 50) -> List[AuditLog]:
        """获取最近的日志"""
        return self.query(limit=limit)

    def get_dashboard_summary(self) -> Dict:
        """获取 Dashboard 摘要"""
        with self._lock:
            logs = self._logs
            
            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_logs = [l for l in logs if l.created_at >= today_start]
            
            by_event_type = defaultdict(int)
            by_risk_level = defaultdict(int)
            for log in today_logs:
                by_event_type[log.event_type] += 1
                by_risk_level[log.risk_level.value] += 1
            
            high_risk = [l.to_dict() for l in logs 
                        if l.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]]
            
            return {
                "total_logs": len(logs),
                "today_count": len(today_logs),
                "by_event_type": dict(by_event_type),
                "by_risk_level": dict(by_risk_level),
                "high_risk_events": sorted(high_risk, 
                                          key=lambda x: x["created_at"], 
                                          reverse=True)[:20],
                "recent_logs": [l.to_dict() for l in 
                               sorted(logs, key=lambda x: x.created_at, 
                                     reverse=True)[:50]],
            }

    def cleanup_old(self, days: int = 30) -> int:
        """清理旧日志"""
        cutoff = datetime.now() - timedelta(days=days)
        with self._lock:
            original_count = len(self._logs)
            self._logs = [l for l in self._logs if l.created_at >= cutoff]
            cleaned = original_count - len(self._logs)
            if cleaned:
                self._save_state()
        return cleaned


# 全局单例
_logger: Optional[AuditLogger] = None


def get_logger(state_path: str = "~/.hermes/multi_agent/audit_logs.json") -> AuditLogger:
    """获取全局 AuditLogger 单例"""
    global _logger
    if _logger is None:
        _logger = AuditLogger(state_path)
    return _logger
