#!/usr/bin/env python3
"""
多智能体治理 Dashboard 服务
启动 Flask 应用提供 API 和 Web UI
"""

import os
import sys
from flask import Flask, send_from_directory, redirect

# 添加父目录到路径以便导入 multi_agent
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multi_agent.api import multi_agent_bp

# 创建 Flask 应用
app = Flask(__name__, 
            static_folder='static',
            static_url_path='/static',
            template_folder='templates')

# 注册多智能体 Blueprint
app.register_blueprint(multi_agent_bp)

# Dashboard 首页
@app.route('/')
def dashboard_index():
    """重定向到 Dashboard UI"""
    return redirect('/multi-agent')

@app.route('/multi-agent')
def dashboard_ui():
    """Dashboard Web UI"""
    from flask import render_template
    try:
        return render_template('dashboard.html')
    except Exception as e:
        return f"Dashboard UI Error: {e}", 500

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='多智能体治理 Dashboard')
    parser.add_argument('--host', default='127.0.0.1', help='监听地址')
    parser.add_argument('--port', type=int, default=8787, help='端口号')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    
    args = parser.parse_args()
    
    print(f"启动多智能体 Dashboard 服务...")
    print(f"  地址：http://{args.host}:{args.port}")
    print(f"  API:  http://{args.host}:{args.port}/api/multi-agent")
    print(f"  UI:   http://{args.host}:{args.port}/multi-agent")
    print()
    
    app.run(host=args.host, port=args.port, debug=args.debug)
