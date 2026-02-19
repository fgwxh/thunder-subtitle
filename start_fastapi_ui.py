#!/usr/bin/env python3
"""
快速启动 FastAPI Web UI 脚本
该脚本会检查并安装项目所需的依赖，然后启动服务
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, cwd=None, capture_output=True):
    """运行命令并返回结果"""
    print(f"执行命令: {' '.join(cmd)}")
    try:
        if capture_output:
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=600)  # 10分钟超时
        else:
            result = subprocess.run(cmd, cwd=cwd, capture_output=False, text=True)
        
        if result.returncode != 0:
            if capture_output:
                print(f"错误: {result.stderr}")
            return False
        if capture_output and result.stdout:
            print(f"输出: {result.stdout[:500]}..." if len(result.stdout) > 500 else f"输出: {result.stdout}")
        return True
    except Exception as e:
        print(f"执行命令时出错: {e}")
        return False

def main():
    """主函数"""
    print("快速启动 FastAPI Web UI")
    print("=" * 40)
    
    # 获取项目根目录
    project_root = Path(__file__).parent
    print(f"项目根目录: {project_root}")
    
    # 步骤1: 检查 Python
    print("\n步骤1: 检查 Python 安装...")
    if not run_command([sys.executable, "--version"]):
        print("错误: Python 未安装或不可用")
        input("按回车键退出...")
        return 1
    print("✅ Python 已安装")
    
    # 步骤2: 创建虚拟环境
    venv_dir = project_root / "venv"
    print(f"\n步骤2: 检查虚拟环境 ({venv_dir})...")
    if not venv_dir.exists():
        print("创建虚拟环境...")
        if not run_command([sys.executable, "-m", "venv", "venv"], cwd=project_root):
            print("错误: 创建虚拟环境失败")
            input("按回车键退出...")
            return 1
        print("✅ 虚拟环境创建成功")
    else:
        print("✅ 虚拟环境已存在")
    
    # 步骤3: 激活虚拟环境并安装依赖
    print("\n步骤3: 安装项目依赖...")
    
    # 根据系统选择 pip 路径
    if sys.platform.startswith("win32"):
        pip_path = venv_dir / "Scripts" / "pip.exe"
        python_path = venv_dir / "Scripts" / "python.exe"
    else:
        pip_path = venv_dir / "bin" / "pip"
        python_path = venv_dir / "bin" / "python"
    
    print(f"pip 路径: {pip_path}")
    print(f"Python 路径: {python_path}")
    
    # 检查 pip 是否存在
    if not pip_path.exists():
        print(f"错误: pip 不存在于 {pip_path}")
        input("按回车键退出...")
        return 1
    
    # 安装依赖
    print("开始安装依赖...")
    dependencies = [
        "httpx", "typer", "rich", "questionary", "pysmb",
        "fastapi", "uvicorn", "jinja2", "python-multipart", "openai", "watchdog"
    ]
    
    if not run_command([str(pip_path), "install"] + dependencies, cwd=project_root):
        print("错误: 安装依赖失败")
        input("按回车键退出...")
        return 1
    print("✅ 依赖安装成功")
    
    # 步骤4: 启动服务
    print("\n步骤4: 启动 FastAPI Web UI...")
    print("服务地址: http://localhost:8010")
    print("按 Ctrl+C 停止服务")
    print("=" * 40)
    
    # 启动服务
    service_cmd = [str(python_path), "run_fastapi_ui.py"]
    print(f"启动命令: {' '.join(service_cmd)}")
    
    try:
        # 不捕获输出，直接显示服务启动过程
        result = subprocess.run(service_cmd, cwd=project_root, capture_output=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\n服务已停止")
        return 0
    except Exception as e:
        print(f"启动服务时出错: {e}")
        input("按回车键退出...")
        return 1

if __name__ == "__main__":
    sys.exit(main())
