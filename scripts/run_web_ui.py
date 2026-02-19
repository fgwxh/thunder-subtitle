import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

import streamlit.cli as cli

if __name__ == "__main__":
    sys.argv = [
        "streamlit",
        "run",
        str(project_root / "src" / "thunder_subtitle_cli" / "web_ui.py"),
        "--server.port",
        "8501",
        "--server.address",
        "localhost",
    ]
    cli.main()
