#!/usr/bin/env python3
"""
启动FastAPI Web UI
"""

import sys
import signal
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from thunder_subtitle_cli.web_ui_fastapi import run_server

import os

def signal_handler(signum, frame):
    """处理信号，优雅退出"""
    print("\n正在退出...")
    sys.exit(0)

if __name__ == "__main__":
    # 注册信号处理函数
    signal.signal(signal.SIGINT, signal_handler)  # CTRL+C
    signal.signal(signal.SIGTERM, signal_handler)  # 终止信号
    
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8010"))
    
    try:
        run_server(host=host, port=port)
    except KeyboardInterrupt:
        print("\n已手动退出")
        sys.exit(0)