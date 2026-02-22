# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


# NOTE:
# - This spec lives under ./packaging/, and PyInstaller resolves relative paths
#   relative to the spec directory. Use absolute paths for reliability.
# - Avoid collect_submodules("prompt_toolkit"): it tries to import optional
#   contrib modules (e.g. SSH) that may require extra deps (asyncssh).
# PyInstaller does not define __file__ in the spec exec namespace.
# SPECPATH is the directory containing this spec file.
project_root = Path(SPECPATH).resolve().parent

# 收集所有必要的隐藏导入
hiddenimports: list[str] = []
hiddenimports += collect_submodules("questionary")
hiddenimports += collect_submodules("rich")
hiddenimports += collect_submodules("typer")
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("jinja2")
hiddenimports += collect_submodules("starlette")
hiddenimports += collect_submodules("pydantic")
hiddenimports += ["prompt_toolkit", "httpx", "watchdog", "openai"]
hiddenimports += ["smb", "nmb", "smb.base", "smb.smb", "smb.nmb", "smb.SMBConnection"]
hiddenimports += ["thunder_subtitle_cli", "thunder_subtitle_cli.web_ui_fastapi"]
hiddenimports += ["thunder_subtitle_cli.ai_evaluator", "thunder_subtitle_cli.directory_watcher"]
hiddenimports += ["thunder_subtitle_cli.client", "thunder_subtitle_cli.core", "thunder_subtitle_cli.models"]
hiddenimports += ["thunder_subtitle_cli.formatting", "thunder_subtitle_cli.selector", "thunder_subtitle_cli.util"]

# 收集静态文件和模板
datas = [
    (str(project_root / "static"), "static"),
    (str(project_root / "templates"), "templates"),
    (str(project_root / "ui_config.example.json"), "."),
    (str(project_root / "download_history.json"), "."),
]


# 添加 src 目录到分析路径
src_dir = project_root / "src"

a = Analysis(
    [str(project_root / "run_fastapi_ui.py")],
    pathex=[str(project_root), str(src_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="thunder-subtitle-fastapi",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
