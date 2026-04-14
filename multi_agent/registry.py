"""
多智能体治理 - Agent 注册中心

管理 Agent 的注册、状态更新、心跳检测
"""

import json
import os
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

from .models import Agent, AgentStatus


class AgentRegistry:
    """
    Agent 注册中心
    
    负责：
    - Agent 注册/注销
    - 状态管理
    - 心跳检测
    - 在线 Agent 查询
    """

    def __init__(self, state_path: str = "~/.hermes/multi_agent/agents.json"):
        self.state_path = Path(state_path).expanduser()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._agents: Dict[str, Agent] = {}
        self._lock = threading.RLock()
        self._load_state()

    def _load_state(self):
        """从磁盘加载状态"""
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for agent_data in data.get("agents", []):
                        agent = Agent.from_dict(agent_data)
                        self._agents[agent.agent_id] = agent
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[AgentRegistry] 加载状态失败：{e}")

    def _save_state(self):
        """保存状态到磁盘"""
        with self._lock:
            data = {
                "updated_at": datetime.now().isoformat(),
                "agents": [agent.to_dict() for agent in self._agents.values()],
            }
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    def register(self, agent_id: str, role: str, department: str = "general",
                 tools: Optional[List[str]] = None, metadata: Optional[Dict] = None) -> Agent:
        """
        注册一个 Agent
        
        Args:
            agent_id: Agent 唯一标识
            role: 角色描述
            department: 所属部门
            tools: 可用工具列表
            metadata: 额外元数据
        
        Returns:
            注册后的 Agent 对象
        """
        with self._lock:
            if agent_id in self._agents:
                agent = self._agents[agent_id]
                agent.status = AgentStatus.ONLINE
                agent.last_heartbeat = datetime.now()
            else:
                agent = Agent(
                    agent_id=agent_id,
                    role=role,
                    department=department,
                    status=AgentStatus.ONLINE,
                    last_heartbeat=datetime.now(),
                    tools_in_use=tools or [],
                    metadata=metadata or {},
                )
                self._agents[agent_id] = agent
            
            self._save_state()
            return agent

    def unregister(self, agent_id: str):
        """注销一个 Agent"""
        with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id].status = AgentStatus.OFFLINE
                self._agents[agent_id].last_heartbeat = None
                self._save_state()

    def heartbeat(self, agent_id: str) -> bool:
        """
        更新 Agent 心跳
        
        Args:
            agent_id: Agent ID
        
        Returns:
            是否成功更新
        """
        with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id].last_heartbeat = datetime.now()
                if self._agents[agent_id].status == AgentStatus.OFFLINE:
                    self._agents[agent_id].status = AgentStatus.ONLINE
                self._save_state()
                return True
            return False

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """获取单个 Agent 信息"""
        return self._agents.get(agent_id)

    def list_agents(self, status: Optional[AgentStatus] = None,
                    department: Optional[str] = None) -> List[Agent]:
        """
        列出 Agent
        
        Args:
            status: 按状态筛选
            department: 按部门筛选
        
        Returns:
            Agent 列表
        """
        with self._lock:
            agents = list(self._agents.values())
        
        if status:
            agents = [a for a in agents if a.status == status]
        if department:
            agents = [a for a in agents if a.department == department]
        
        return agents

    def update_status(self, agent_id: str, status: AgentStatus):
        """更新 Agent 状态"""
        with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id].status = status
                self._save_state()

    def set_busy(self, agent_id: str, task_id: str):
        """设置 Agent 为忙碌状态"""
        with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id].status = AgentStatus.BUSY
                self._agents[agent_id].current_task = task_id
                self._save_state()

    def set_idle(self, agent_id: str):
        """设置 Agent 为空闲状态"""
        with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id].status = AgentStatus.ONLINE
                self._agents[agent_id].current_task = None
                self._save_state()

    def pause(self, agent_id: str):
        """暂停 Agent"""
        with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id].status = AgentStatus.PAUSED
                self._save_state()

    def resume(self, agent_id: str):
        """恢复 Agent"""
        with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id].status = AgentStatus.ONLINE
                self._save_state()

    def record_incident(self, agent_id: str, incident: Dict):
        """记录 Agent 事件"""
        with self._lock:
            if agent_id in self._agents:
                incident["timestamp"] = datetime.now().isoformat()
                self._agents[agent_id].recent_incidents.append(incident)
                if len(self._agents[agent_id].recent_incidents) > 20:
                    self._agents[agent_id].recent_incidents = \
                        self._agents[agent_id].recent_incidents[-20:]
                self._save_state()

    def update_success_rate(self, agent_id: str, success: bool):
        """更新 Agent 成功率"""
        with self._lock:
            if agent_id in self._agents:
                agent = self._agents[agent_id]
                current_rate = agent.success_rate
                agent.success_rate = current_rate * 0.95 + (1.0 if success else 0.0) * 0.05
                self._save_state()

    def get_online_count(self) -> int:
        """获取在线 Agent 数量"""
        with self._lock:
            return sum(1 for a in self._agents.values() 
                      if a.status in [AgentStatus.ONLINE, AgentStatus.BUSY])

    def check_stale_agents(self, timeout_seconds: int = 300) -> List[str]:
        """
        检查超时的 Agent
        
        Args:
            timeout_seconds: 超时阈值（秒）
        
        Returns:
            超时 Agent ID 列表
        """
        stale = []
        cutoff = datetime.now() - timedelta(seconds=timeout_seconds)
        
        with self._lock:
            for agent_id, agent in self._agents.items():
                if agent.last_heartbeat and agent.last_heartbeat < cutoff:
                    if agent.status in [AgentStatus.ONLINE, AgentStatus.BUSY]:
                        stale.append(agent_id)
                        agent.status = AgentStatus.OFFLINE
        
        if stale:
            self._save_state()
        
        return stale

    def get_dashboard_summary(self) -> Dict:
        """获取 Dashboard 摘要信息"""
        with self._lock:
            agents = list(self._agents.values())
            online = sum(1 for a in agents if a.status in [AgentStatus.ONLINE, AgentStatus.BUSY])
            paused = sum(1 for a in agents if a.status == AgentStatus.PAUSED)
            offline = sum(1 for a in agents if a.status == AgentStatus.OFFLINE)
            
            by_department = {}
            for agent in agents:
                dept = agent.department
                if dept not in by_department:
                    by_department[dept] = {"total": 0, "online": 0}
                by_department[dept]["total"] += 1
                if agent.status in [AgentStatus.ONLINE, AgentStatus.BUSY]:
                    by_department[dept]["online"] += 1
            
            return {
                "total_agents": len(agents),
                "online": online,
                "paused": paused,
                "offline": offline,
                "by_department": by_department,
                "agents": [a.to_dict() for a in agents],
            }


# 全局单例
_registry: Optional[AgentRegistry] = None


def get_registry(state_path: str = "~/.hermes/multi_agent/agents.json") -> AgentRegistry:
    """获取全局 AgentRegistry 单例"""
    global _registry
    if _registry is None:
        _registry = AgentRegistry(state_path)
    return _registry
