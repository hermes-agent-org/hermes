"""
多智能体治理 - 审批 Gating 系统

管理高风险动作的审批流程
"""

import json
import uuid
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from pathlib import Path

from .models import Approval, ApprovalStatus, RiskLevel


class ApprovalGate:
    """
    审批 Gating 系统
    
    负责：
    - 审批请求创建
    - 风险评估
    - 审批决策
    - 自动过期
    """

    # 高风险动作定义
    HIGH_RISK_ACTIONS = {
        "wechat_push": RiskLevel.MEDIUM,
        "email_send": RiskLevel.MEDIUM,
        "sms_send": RiskLevel.MEDIUM,
        "file_delete": RiskLevel.HIGH,
        "publish": RiskLevel.HIGH,
        "deploy": RiskLevel.HIGH,
        "price_change": RiskLevel.MEDIUM,
        "batch_operation": RiskLevel.MEDIUM,
        "irreversible_action": RiskLevel.HIGH,
    }

    def __init__(self, state_path: str = "~/.hermes/multi_agent/approvals.json"):
        self.state_path = Path(state_path).expanduser()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._approvals: Dict[str, Approval] = {}
        self._lock = threading.RLock()
        self._subscribers: List[Callable] = []
        self._auto_approve_patterns: List[str] = []
        self._load_state()

    def _load_state(self):
        """从磁盘加载状态"""
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for approval_data in data.get("approvals", []):
                        approval = Approval.from_dict(approval_data)
                        self._approvals[approval.approval_id] = approval
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[ApprovalGate] 加载状态失败：{e}")

    def _save_state(self):
        """保存状态到磁盘"""
        with self._lock:
            data = {
                "updated_at": datetime.now().isoformat(),
                "approvals": [a.to_dict() for a in self._approvals.values()],
            }
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    def _notify(self, event: str, approval: Approval):
        """通知订阅者"""
        for callback in self._subscribers:
            try:
                callback(event, approval)
            except Exception as e:
                print(f"[ApprovalGate] 通知回调失败：{e}")

    def subscribe(self, callback: Callable):
        """订阅审批事件"""
        self._subscribers.append(callback)

    def get_risk_level(self, action_type: str) -> RiskLevel:
        """获取动作的风险等级"""
        return self.HIGH_RISK_ACTIONS.get(action_type, RiskLevel.LOW)

    def requires_approval(self, action_type: str) -> bool:
        """判断是否需要审批"""
        return action_type in self.HIGH_RISK_ACTIONS

    def request_approval(self, requested_by: str, action_type: str,
                        target_object: str, preview_content: str,
                        reason: str = "", metadata: Optional[Dict] = None,
                        expires_in_minutes: int = 60) -> Approval:
        """
        请求审批
        
        Args:
            requested_by: 请求者 (Agent ID)
            action_type: 动作类型
            target_object: 目标对象
            preview_content: 预览内容
            reason: 请求原因
            metadata: 额外元数据
            expires_in_minutes: 过期时间（分钟）
        
        Returns:
            审批对象
        """
        risk_level = self.get_risk_level(action_type)
        approval_id = str(uuid.uuid4())[:8]
        
        approval = Approval(
            approval_id=approval_id,
            requested_by=requested_by,
            action_type=action_type,
            risk_level=risk_level,
            target_object=target_object,
            preview_content=preview_content,
            reason=reason or f"执行 {action_type} 操作",
            expires_at=datetime.now() + timedelta(minutes=expires_in_minutes),
            metadata=metadata or {},
        )
        
        with self._lock:
            self._approvals[approval_id] = approval
            self._save_state()
        
        self._notify("approval_requested", approval)
        return approval

    def approve(self, approval_id: str, decided_by: str = "user",
                reason: str = "") -> bool:
        """批准审批"""
        with self._lock:
            if approval_id not in self._approvals:
                return False
            
            approval = self._approvals[approval_id]
            
            if approval.status != ApprovalStatus.PENDING:
                return False
            
            if approval.is_expired():
                approval.status = ApprovalStatus.EXPIRED
                self._save_state()
                return False
            
            approval.status = ApprovalStatus.APPROVED
            approval.decided_at = datetime.now()
            approval.decided_by = decided_by
            approval.decision_reason = reason or "用户批准"
            
            self._save_state()
        
        self._notify("approval_approved", approval)
        return True

    def reject(self, approval_id: str, decided_by: str = "user",
               reason: str = "") -> bool:
        """拒绝审批"""
        with self._lock:
            if approval_id not in self._approvals:
                return False
            
            approval = self._approvals[approval_id]
            
            if approval.status != ApprovalStatus.PENDING:
                return False
            
            approval.status = ApprovalStatus.REJECTED
            approval.decided_at = datetime.now()
            approval.decided_by = decided_by
            approval.decision_reason = reason or "用户拒绝"
            
            self._save_state()
        
        self._notify("approval_rejected", approval)
        return True

    def snooze(self, approval_id: str, minutes: int = 30) -> bool:
        """稍后处理"""
        with self._lock:
            if approval_id not in self._approvals:
                return False
            
            approval = self._approvals[approval_id]
            
            if approval.status != ApprovalStatus.PENDING:
                return False
            
            approval.status = ApprovalStatus.SNOOZED
            approval.expires_at = datetime.now() + timedelta(minutes=minutes)
            
            self._save_state()
        
        self._notify("approval_snoozed", approval)
        return True

    def get_approval(self, approval_id: str) -> Optional[Approval]:
        """获取审批详情"""
        return self._approvals.get(approval_id)

    def list_pending(self) -> List[Approval]:
        """列出待审批事项"""
        with self._lock:
            pending = [a for a in self._approvals.values() 
                      if a.status == ApprovalStatus.PENDING and not a.is_expired()]
        return sorted(pending, key=lambda a: a.created_at)

    def list_by_requester(self, requested_by: str) -> List[Approval]:
        """按请求者列出审批"""
        with self._lock:
            return [a for a in self._approvals.values() 
                   if a.requested_by == requested_by]

    def cleanup_expired(self) -> int:
        """清理过期审批"""
        cleaned = 0
        with self._lock:
            for approval_id, approval in list(self._approvals.items()):
                if approval.is_expired() and approval.status == ApprovalStatus.PENDING:
                    approval.status = ApprovalStatus.EXPIRED
                    cleaned += 1
            if cleaned:
                self._save_state()
        return cleaned

    def get_dashboard_summary(self) -> Dict:
        """获取 Dashboard 摘要"""
        with self._lock:
            approvals = list(self._approvals.values())
            pending = [a for a in approvals if a.status == ApprovalStatus.PENDING and not a.is_expired()]
            
            by_risk = {"low": 0, "medium": 0, "high": 0, "critical": 0}
            for a in pending:
                by_risk[a.risk_level.value] += 1
            
            return {
                "pending_count": len(pending),
                "by_risk_level": by_risk,
                "pending_items": [a.to_dict() for a in 
                                 sorted(pending, key=lambda x: x.created_at)],
                "recent_decisions": [a.to_dict() for a in 
                                    sorted([a for a in approvals 
                                           if a.status in [ApprovalStatus.APPROVED, 
                                                          ApprovalStatus.REJECTED]],
                                          key=lambda x: x.decided_at, reverse=True)[:10]],
            }


# 全局单例
_gate: Optional[ApprovalGate] = None


def get_gate(state_path: str = "~/.hermes/multi_agent/approvals.json") -> ApprovalGate:
    """获取全局 ApprovalGate 单例"""
    global _gate
    if _gate is None:
        _gate = ApprovalGate(state_path)
    return _gate
