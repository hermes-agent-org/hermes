#!/usr/bin/env python3
"""
多智能体治理 - 任务追踪工具

用法:
    python multi_agent_task.py create <source> <type> <description>
    python multi_agent_task.py start <task_id> [step]
    python multi_agent_task.py update <task_id> --step=X --action=X --next=X
    python multi_agent_task.py complete <task_id> <result>
    python multi_agent_task.py fail <task_id> <error>
    python multi_agent_task.py status <task_id>
    python multi_agent_task.py list [--status=X]
"""

import sys
import json
import urllib.request
import urllib.error
from urllib.parse import urlencode

BASE = "http://127.0.0.1:8787/api/multi-agent"


def api_call(path, method="GET", data=None):
    """调用 API"""
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    
    if data:
        data = json.dumps(data).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP 错误 {e.code}: {e.reason}")
        try:
            error = json.loads(e.read().decode('utf-8'))
            print(f"   详情：{error.get('error', '未知错误')}")
        except:
            pass
        sys.exit(1)
    except Exception as e:
        print(f"❌ 错误：{e}")
        sys.exit(1)


def create_task(source, task_type, description, priority="normal"):
    """创建任务"""
    data = {
        "source_agent": source,
        "task_type": task_type,
        "description": description,
        "priority": priority,
    }
    result = api_call("/tasks", "POST", data)
    print(f"✅ 任务已创建")
    print(f"   ID: {result['task_id']}")
    print(f"   类型：{result['task_type']}")
    print(f"   描述：{result['description']}")
    print(f"   状态：{result['status']}")
    print(f"   优先级：{result['priority']}")
    return result


def start_task(task_id, step=""):
    """开始任务"""
    # 需要直接调用内部 API，这里简化处理
    print(f"⚠️  开始任务功能需要直接调用内部 API")
    print(f"   请使用 Python 代码调用 queue.start_task('{task_id}', '{step}')")


def complete_task(task_id, result_text):
    """完成任务"""
    print(f"⚠️  完成任务功能需要直接调用内部 API")
    print(f"   请使用 Python 代码调用 queue.complete_task('{task_id}', '{result_text}')")


def fail_task(task_id, error_text):
    """任务失败"""
    print(f"⚠️  任务失败功能需要直接调用内部 API")
    print(f"   请使用 Python 代码调用 queue.fail_task('{task_id}', '{error_text}')")


def get_status(task_id):
    """获取任务状态"""
    result = api_call(f"/tasks/{task_id}")
    print(f"📋 任务状态")
    print(f"   ID: {result['task_id']}")
    print(f"   类型：{result['task_type']}")
    print(f"   描述：{result['description']}")
    print(f"   状态：{result['status']}")
    print(f"   当前步骤：{result.get('current_step', '-')}")
    print(f"   上一步：{result.get('last_action', '-')}")
    print(f"   下一步：{result.get('next_action', '-')}")
    if result.get('error'):
        print(f"   错误：{result['error']}")
    if result.get('result'):
        print(f"   结果：{result['result']}")
    return result


def list_tasks(status=None):
    """列出任务"""
    path = "/tasks"
    if status:
        path += f"?status={status}"
    
    result = api_call(path)
    tasks = result.get('tasks', [])
    
    if not tasks:
        print("📭 没有任务")
        return
    
    print(f"📋 任务列表 ({len(tasks)} 个)")
    print()
    
    for task in tasks[:10]:
        status_icon = {"done": "✅", "running": "🔄", "queued": "⏳", "failed": "❌"}.get(task['status'], "•")
        print(f"{status_icon} [{task['task_id']}] {task['task_type']}")
        print(f"   {task['description']}")
        print(f"   状态：{task['status']} | 来源：{task['source_agent']}")
        print()
    
    if len(tasks) > 10:
        print(f"... 还有 {len(tasks) - 10} 个任务，请使用 status 参数筛选")


def create_approval(requester, action_type, target, content, reason, risk="medium"):
    """创建审批请求"""
    data = {
        "requested_by": requester,
        "action_type": action_type,
        "target_object": target,
        "preview_content": content,
        "reason": reason,
        "risk_level": risk,
    }
    # 需要内部 API
    print(f"⚠️  审批请求功能需要直接调用内部 API")
    print(f"   请使用 Python 代码调用 gate.request_approval(...)")


def list_approvals(pending_only=True):
    """列出审批"""
    path = "/approvals"
    if pending_only:
        path += "?pending=true"
    
    result = api_call(path)
    approvals = result.get('approvals', [])
    
    if not approvals:
        print("✅ 没有待审批事项")
        return
    
    print(f"📋 待审批事项 ({len(approvals)} 个)")
    print()
    
    for a in approvals:
        risk_icon = {"low": "🟢", "medium": "🟡", "high": "🔴", "critical": "🔴"}.get(a['risk_level'], "•")
        print(f"{risk_icon} [{a['approval_id']}] {a['action_type']}")
        print(f"   请求者：{a['requested_by']}")
        print(f"   原因：{a['reason']}")
        print(f"   风险等级：{a['risk_level']}")
        print(f"   创建时间：{a['created_at']}")
        print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "create":
        if len(sys.argv) < 5:
            print("用法：create <source_agent> <task_type> <description> [priority]")
            sys.exit(1)
        create_task(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else "normal")
    
    elif cmd == "start":
        if len(sys.argv) < 3:
            print("用法：start <task_id> [step]")
            sys.exit(1)
        start_task(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    
    elif cmd == "complete":
        if len(sys.argv) < 4:
            print("用法：complete <task_id> <result>")
            sys.exit(1)
        complete_task(sys.argv[2], sys.argv[3])
    
    elif cmd == "fail":
        if len(sys.argv) < 4:
            print("用法：fail <task_id> <error>")
            sys.exit(1)
        fail_task(sys.argv[2], sys.argv[3])
    
    elif cmd == "status":
        if len(sys.argv) < 3:
            print("用法：status <task_id>")
            sys.exit(1)
        get_status(sys.argv[2])
    
    elif cmd == "list":
        status = None
        if "--status=" in sys.argv:
            status = sys.argv[sys.argv.index("--status=") + 1].split("=")[1] if "=" in sys.argv[sys.argv.index("--status=")] else None
        for arg in sys.argv:
            if arg.startswith("--status="):
                status = arg.split("=")[1]
        list_tasks(status)
    
    elif cmd == "approvals":
        list_approvals()
    
    elif cmd == "help":
        print(__doc__)
    
    else:
        print(f"未知命令：{cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
