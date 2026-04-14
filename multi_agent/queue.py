"""
多智能体治理 - 任务队列系统

管理任务的创建、调度、状态追踪
"""

import json
import uuid
import threading
from datetime import datetime
from typing import Dict, List, Optional, Callable
from pathlib import Path
from collections import defaultdict

from .models import Task, TaskStatus, TaskPriority


class TaskQueue:
    """
    任务队列系统
    
    负责：
    - 任务创建
    - 优先级调度
    - 状态管理
    - 任务查询
    """

    def __init__(self, state_path: str = "~/.hermes/multi_agent/tasks.json"):
        self.state_path = Path(state_path).expanduser()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._tasks: Dict[str, Task] = {}
        self._queue: List[str] = []  # 任务 ID 队列
        self._lock = threading.RLock()
        self._subscribers: List[Callable] = []
        self._load_state()

    def _load_state(self):
        """从磁盘加载状态"""
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for task_data in data.get("tasks", []):
                        task = Task.from_dict(task_data)
                        self._tasks[task.task_id] = task
                        if task.status == TaskStatus.QUEUED:
                            self._queue.append(task.task_id)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[TaskQueue] 加载状态失败：{e}")

    def _save_state(self):
        """保存状态到磁盘"""
        with self._lock:
            data = {
                "updated_at": datetime.now().isoformat(),
                "tasks": [task.to_dict() for task in self._tasks.values()],
            }
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    def _notify(self, event: str, task: Task):
        """通知订阅者"""
        for callback in self._subscribers:
            try:
                callback(event, task)
            except Exception as e:
                print(f"[TaskQueue] 通知回调失败：{e}")

    def subscribe(self, callback: Callable):
        """订阅任务事件"""
        self._subscribers.append(callback)

    def create_task(self, source_agent: str, task_type: str, description: str,
                    priority: TaskPriority = TaskPriority.NORMAL,
                    metadata: Optional[Dict] = None) -> Task:
        """
        创建新任务
        
        Args:
            source_agent: 发起 Agent
            task_type: 任务类型
            description: 任务描述
            priority: 优先级
            metadata: 额外元数据
        
        Returns:
            创建的任务对象
        """
        task_id = str(uuid.uuid4())[:8]
        task = Task(
            task_id=task_id,
            source_agent=source_agent,
            task_type=task_type,
            description=description,
            priority=priority,
            status=TaskStatus.QUEUED,
            next_action="等待调度",
            metadata=metadata or {},
        )
        
        with self._lock:
            self._tasks[task_id] = task
            self._queue.append(task_id)
            self._queue.sort(key=lambda tid: self._tasks[tid].priority.value)
            self._save_state()
        
        self._notify("task_created", task)
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务详情"""
        return self._tasks.get(task_id)

    def list_tasks(self, status: Optional[TaskStatus] = None,
                   source_agent: Optional[str] = None,
                   limit: int = 50) -> List[Task]:
        """
        列出任务
        
        Args:
            status: 按状态筛选
            source_agent: 按发起 Agent 筛选
            limit: 返回数量限制
        
        Returns:
            任务列表
        """
        with self._lock:
            tasks = list(self._tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        if source_agent:
            tasks = [t for t in tasks if t.source_agent == source_agent]
        
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks[:limit]

    def start_task(self, task_id: str, current_step: str = "") -> bool:
        """开始执行任务"""
        with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            if task.status != TaskStatus.QUEUED:
                return False
            
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            task.current_step = current_step
            task.next_action = "执行中"
            task.add_log("started", f"开始执行，步骤：{current_step}")
            
            if task_id in self._queue:
                self._queue.remove(task_id)
            
            self._save_state()
        
        self._notify("task_started", task)
        return True

    def update_task(self, task_id: str, current_step: str = None,
                    last_action: str = None, next_action: str = None,
                    log_action: str = None, log_details: str = "") -> bool:
        """更新任务进度"""
        with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            if current_step:
                task.current_step = current_step
            if last_action:
                task.last_action = last_action
            if next_action:
                task.next_action = next_action
            if log_action:
                task.add_log(log_action, log_details)
            
            self._save_state()
        
        self._notify("task_updated", task)
        return True

    def complete_task(self, task_id: str, result: str = "") -> bool:
        """完成任务"""
        with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            task.status = TaskStatus.DONE
            task.completed_at = datetime.now()
            task.result = result
            task.add_log("completed", f"完成：{result}")
            
            self._save_state()
        
        self._notify("task_completed", task)
        return True

    def fail_task(self, task_id: str, error: str, retry: bool = False) -> bool:
        """任务失败"""
        with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            
            if retry and task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.RETRYING
                task.add_log("retry", f"重试 {task.retry_count}/{task.max_retries}: {error}", "warning")
                task.next_action = "重新执行"
            else:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                task.error = error
                task.add_log("failed", f"失败：{error}", "error")
            
            self._save_state()
        
        self._notify("task_failed", task)
        return True

    def cancel_task(self, task_id: str, reason: str = "") -> bool:
        """取消任务"""
        with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            if task.status in [TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                return False
            
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            task.add_log("cancelled", f"取消：{reason}", "warning")
            
            if task_id in self._queue:
                self._queue.remove(task_id)
            
            self._save_state()
        
        self._notify("task_cancelled", task)
        return True

    def request_approval(self, task_id: str, approval_id: str) -> bool:
        """请求审批"""
        with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            task.status = TaskStatus.WAITING_APPROVAL
            task.waiting_approval = True
            task.approval_id = approval_id
            task.next_action = "等待审批"
            task.add_log("waiting_approval", f"审批 ID: {approval_id}")
            
            self._save_state()
        
        self._notify("task_waiting_approval", task)
        return True

    def after_approval(self, task_id: str, approved: bool) -> bool:
        """审批后处理"""
        with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            
            if approved:
                task.status = TaskStatus.RUNNING
                task.waiting_approval = False
                task.approval_id = None
                task.next_action = "继续执行"
                task.add_log("approved", "审批通过")
            else:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                task.add_log("rejected", "审批拒绝", "warning")
            
            self._save_state()
        
        self._notify("task_approved" if approved else "task_rejected", task)
        return True

    def get_next_task(self) -> Optional[Task]:
        """获取下一个待执行任务（按优先级）"""
        with self._lock:
            if not self._queue:
                return None
            
            task_id = self._queue[0]
            return self._tasks.get(task_id)

    def get_queue_length(self) -> int:
        """获取队列长度"""
        return len(self._queue)

    def get_dashboard_summary(self) -> Dict:
        """获取 Dashboard 摘要"""
        with self._lock:
            tasks = list(self._tasks.values())
            by_status = defaultdict(int)
            for task in tasks:
                by_status[task.status.value] += 1
            
            today = datetime.now().date()
            today_tasks = [t for t in tasks 
                          if t.created_at.date() == today]
            today_completed = sum(1 for t in today_tasks 
                                 if t.status in [TaskStatus.DONE, TaskStatus.FAILED])
            
            return {
                "total_tasks": len(tasks),
                "by_status": dict(by_status),
                "queue_length": len(self._queue),
                "today_tasks": len(today_tasks),
                "today_completed": today_completed,
                "recent_tasks": [t.to_dict() for t in 
                                sorted(tasks, key=lambda x: x.created_at, reverse=True)[:10]],
            }


# 全局单例
_queue: Optional[TaskQueue] = None


def get_queue(state_path: str = "~/.hermes/multi_agent/tasks.json") -> TaskQueue:
    """获取全局 TaskQueue 单例"""
    global _queue
    if _queue is None:
        _queue = TaskQueue(state_path)
    return _queue
