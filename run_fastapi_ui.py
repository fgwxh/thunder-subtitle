#!/usr/bin/env python3
"""
启动FastAPI Web UI
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from thunder_subtitle_cli.web_ui_fastapi import run_server

import os

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8010"))
    run_server(host=host, port=port)