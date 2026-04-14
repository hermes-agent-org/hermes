"""
多智能体治理 - API 端点

提供 REST API 用于 Dashboard 访问
"""

import json
from datetime import datetime
from typing import Optional
from pathlib import Path

from flask import Blueprint, jsonify, request

from .registry import get_registry
from .queue import get_queue
from .approvals import get_gate
from .audit import get_logger
from .models import RiskLevel


# 创建 Blueprint
multi_agent_bp = Blueprint('multi_agent', __name__, url_prefix='/api/multi-agent')


@multi_agent_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    """获取 Dashboard 概览数据"""
    registry = get_registry()
    queue = get_queue()
    gate = get_gate()
    logger = get_logger()
    
    return jsonify({
        "status": "ok",
        "updated_at": datetime.now().isoformat(),
        "agents": registry.get_dashboard_summary(),
        "tasks": queue.get_dashboard_summary(),
        "approvals": gate.get_dashboard_summary(),
        "audit": logger.get_dashboard_summary(),
    })


# ============ Agents API ============

@multi_agent_bp.route('/agents', methods=['GET'])
def list_agents():
    """列出所有 Agent"""
    status = request.args.get('status')
    department = request.args.get('department')
    
    registry = get_registry()
    agents = registry.list_agents(
        status=status,
        department=department
    )
    
    return jsonify({
        "count": len(agents),
        "agents": [a.to_dict() for a in agents],
    })


@multi_agent_bp.route('/agents/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    """获取 Agent 详情"""
    registry = get_registry()
    agent = registry.get_agent(agent_id)
    
    if not agent:
        return jsonify({"error": "Agent not found"}), 404
    
    return jsonify(agent.to_dict())


@multi_agent_bp.route('/agents/<agent_id>/pause', methods=['POST'])
def pause_agent(agent_id):
    """暂停 Agent"""
    registry = get_registry()
    registry.pause(agent_id)
    
    logger = get_logger()
    logger.log_agent_action(agent_id, "pause", agent_id)
    
    return jsonify({"status": "ok", "agent_id": agent_id})


@multi_agent_bp.route('/agents/<agent_id>/resume', methods=['POST'])
def resume_agent(agent_id):
    """恢复 Agent"""
    registry = get_registry()
    registry.resume(agent_id)
    
    logger = get_logger()
    logger.log_agent_action(agent_id, "resume", agent_id)
    
    return jsonify({"status": "ok", "agent_id": agent_id})


@multi_agent_bp.route('/agents/<agent_id>/heartbeat', methods=['POST'])
def agent_heartbeat(agent_id):
    """Agent 心跳"""
    registry = get_registry()
    success = registry.heartbeat(agent_id)
    
    if not success:
        return jsonify({"error": "Agent not registered"}), 404
    
    return jsonify({"status": "ok", "agent_id": agent_id})


# ============ Tasks API ============

@multi_agent_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """列出任务"""
    status = request.args.get('status')
    source = request.args.get('source')
    limit = request.args.get('limit', 50, type=int)
    
    queue = get_queue()
    tasks = queue.list_tasks(
        status=status,
        source_agent=source,
        limit=limit
    )
    
    return jsonify({
        "count": len(tasks),
        "tasks": [t.to_dict() for t in tasks],
    })


@multi_agent_bp.route('/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    """获取任务详情"""
    queue = get_queue()
    task = queue.get_task(task_id)
    
    if not task:
        return jsonify({"error": "Task not found"}), 404
    
    return jsonify(task.to_dict())


@multi_agent_bp.route('/tasks', methods=['POST'])
def create_task():
    """创建新任务"""
    data = request.json
    
    if not data:
        return jsonify({"error": "Missing request body"}), 400
    
    required = ['source_agent', 'task_type', 'description']
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400
    
    queue = get_queue()
    task = queue.create_task(
        source_agent=data['source_agent'],
        task_type=data['task_type'],
        description=data['description'],
        priority=data.get('priority', 'normal'),
        metadata=data.get('metadata'),
    )
    
    logger = get_logger()
    logger.log_task_created(
        task.task_id, 
        task.source_agent, 
        task.task_type
    )
    
    return jsonify(task.to_dict()), 201


@multi_agent_bp.route('/tasks/<task_id>/cancel', methods=['POST'])
def cancel_task(task_id):
    """取消任务"""
    data = request.json or {}
    reason = data.get('reason', '用户取消')
    
    queue = get_queue()
    success = queue.cancel_task(task_id, reason)
    
    if not success:
        return jsonify({"error": "Task not found or cannot be cancelled"}), 400
    
    return jsonify({"status": "ok", "task_id": task_id})


# ============ Approvals API ============

@multi_agent_bp.route('/approvals', methods=['GET'])
def list_approvals():
    """列出审批"""
    pending_only = request.args.get('pending', 'false').lower() == 'true'
    
    gate = get_gate()
    
    if pending_only:
        approvals = gate.list_pending()
    else:
        approvals = list(gate._approvals.values())
    
    return jsonify({
        "count": len(approvals),
        "approvals": [a.to_dict() for a in approvals],
    })


@multi_agent_bp.route('/approvals/<approval_id>', methods=['GET'])
def get_approval(approval_id):
    """获取审批详情"""
    gate = get_gate()
    approval = gate.get_approval(approval_id)
    
    if not approval:
        return jsonify({"error": "Approval not found"}), 404
    
    return jsonify(approval.to_dict())


@multi_agent_bp.route('/approvals/<approval_id>/approve', methods=['POST'])
def approve(approval_id):
    """批准审批"""
    data = request.json or {}
    reason = data.get('reason', '')
    
    gate = get_gate()
    success = gate.approve(approval_id, "user", reason)
    
    if not success:
        return jsonify({"error": "Approval not found or cannot be approved"}), 400
    
    logger = get_logger()
    logger.log_approval_decided(approval_id, "user", True)
    
    return jsonify({"status": "ok", "approval_id": approval_id, "decision": "approved"})


@multi_agent_bp.route('/approvals/<approval_id>/reject', methods=['POST'])
def reject(approval_id):
    """拒绝审批"""
    data = request.json or {}
    reason = data.get('reason', '')
    
    gate = get_gate()
    success = gate.reject(approval_id, "user", reason)
    
    if not success:
        return jsonify({"error": "Approval not found or cannot be rejected"}), 400
    
    logger = get_logger()
    logger.log_approval_decided(approval_id, "user", False)
    
    return jsonify({"status": "ok", "approval_id": approval_id, "decision": "rejected"})


@multi_agent_bp.route('/approvals/<approval_id>/snooze', methods=['POST'])
def snooze(approval_id):
    """稍后处理"""
    data = request.json or {}
    minutes = data.get('minutes', 30)
    
    gate = get_gate()
    success = gate.snooze(approval_id, minutes)
    
    if not success:
        return jsonify({"error": "Approval not found or cannot be snoozed"}), 400
    
    return jsonify({"status": "ok", "approval_id": approval_id, "snoozed_minutes": minutes})


# ============ Audit API ============

@multi_agent_bp.route('/audit', methods=['GET'])
def list_audit_logs():
    """查询审计日志"""
    event_type = request.args.get('event_type')
    actor = request.args.get('actor')
    target = request.args.get('target')
    limit = request.args.get('limit', 100, type=int)
    
    logger = get_logger()
    logs = logger.query(
        event_type=event_type,
        actor=actor,
        target=target,
        limit=limit
    )
    
    return jsonify({
        "count": len(logs),
        "logs": [l.to_dict() for l in logs],
    })


@multi_agent_bp.route('/audit/recent', methods=['GET'])
def get_recent_audit():
    """获取最近日志"""
    limit = request.args.get('limit', 50, type=int)
    
    logger = get_logger()
    logs = logger.get_recent(limit)
    
    return jsonify({
        "count": len(logs),
        "logs": [l.to_dict() for l in logs],
    })


# ============ Health API ============

@multi_agent_bp.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
    })
