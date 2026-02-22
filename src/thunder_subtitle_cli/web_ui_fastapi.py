#!/usr/bin/env python3
"""
FastAPI Web UI for Thunder Subtitle
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from pydantic import BaseModel
import uvicorn

from thunder_subtitle_cli.client import ThunderClient
from thunder_subtitle_cli.models import ThunderSubtitleItem
from thunder_subtitle_cli.util import sanitize_component
from thunder_subtitle_cli.ai_evaluator import AIEvaluator, RuleBasedEvaluator, get_evaluator, extract_text, calculate_filename_similarity
from thunder_subtitle_cli.directory_watcher import watcher, WatchDirectory, HAS_WATCHDOG


class SafeJSONResponse(Response):
    """Safe JSON Response with correct Content-Length"""
    media_type = "application/json"
    
    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


def detect_and_convert_to_utf8(data: bytes) -> bytes:
    """
    Detect subtitle encoding and convert to UTF-8
    Returns UTF-8 encoded bytes
    """
    encodings_to_try = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'shift_jis', 'euc-jp', 'iso-8859-1']
    
    for encoding in encodings_to_try:
        try:
            text = data.decode(encoding)
            chinese_chars = [c for c in text if '\u4e00' <= c <= '\u9fff']
            
            if encoding == 'utf-8' or len(chinese_chars) > 0:
                if encoding != 'utf-8':
                    print(f"[Encoding] Converted from {encoding} to UTF-8 ({len(chinese_chars)} Chinese chars)")
                    return text.encode('utf-8')
                else:
                    return data
        except Exception:
            continue
    
    return data


# Create FastAPI app
app = FastAPI(title="Thunder Subtitle Web UI", version="1.0.0")

# Configure directories for both development and PyInstaller packaged environments
import sys

if getattr(sys, 'frozen', False):
    # Running as packaged executable
    BASE_DIR = Path(sys._MEIPASS)
else:
    # Running in development
    BASE_DIR = Path(__file__).parent.parent.parent

STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
CONFIG_FILE = BASE_DIR / "ui_config.json"

# Create necessary directories
STATIC_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)

# Configure templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Global config
config = {
    "video_dir": "",
    "save_dir": "",
    "min_score": 0.0,
    "language": "",
    "timeout": 60.0,
    "retries": 2
}

# Load config
def load_config():
    global config
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                config.update(loaded_config)
        except Exception as e:
            print(f"Failed to load config: {e}")
    else:
        # Check if example config exists
        example_config_file = BASE_DIR / "ui_config.example.json"
        if example_config_file.exists():
            try:
                with open(example_config_file, 'r', encoding='utf-8') as f:
                    example_config = json.load(f)
                    config.update(example_config)
                # Save to ui_config.json
                save_config()
                print("Initialized config from ui_config.example.json")
            except Exception as e:
                print(f"Failed to load example config: {e}")

# Save config
def save_config():
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Failed to save config: {e}")

# Initialize config
load_config()

HISTORY_FILE = BASE_DIR / "download_history.json"
_download_history: List[Dict[str, Any]] = []

def load_download_history():
    """Load download history from file"""
    global _download_history
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                _download_history = json.load(f)
        except Exception as e:
            print(f"Failed to load download history: {e}")
            _download_history = []

def save_download_history():
    """Save download history to file"""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(_download_history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Failed to save download history: {e}")

def add_download_history(item: Dict[str, Any]):
    """Add item to download history"""
    global _download_history
    _download_history.insert(0, item)
    if len(_download_history) > 100:
        _download_history = _download_history[:100]
    save_download_history()

def clean_subtitle_filename(name: str) -> str:
    """Clean subtitle filename, remove unwanted prefixes and suffixes"""
    import re
    
    clean_name = name
    
    prefixes_to_remove = [
        r'^hhd800\.com@',
        r'^hhd800@',
        r'^www\.[^@]+@',
        r'^[a-zA-Z0-9\-\.]+\.(com|net|org|cc|tv)@',
        r'^\[[^\]]+\]',
        r'^【[^】]+】',
    ]
    
    for pattern in prefixes_to_remove:
        clean_name = re.sub(pattern, '', clean_name, flags=re.IGNORECASE)
    
    code_patterns = [
        r'([A-Z]{2,6}[-_]\d{2,4})',
        r'([A-Z]{2,6}\d{2,4})',
        r'(SSIS[-_]?\d{3,4})',
        r'(SSNI[-_]?\d{3,4})',
        r'(SONE[-_]?\d{3,4})',
        r'(IPX[-_]?\d{3,4})',
        r'(IPZZ[-_]?\d{3,4})',
        r'(PRED[-_]?\d{3,4})',
        r'(STARS[-_]?\d{3,4})',
        r'(MIAA[-_]?\d{3,4})',
        r'(MIDE[-_]?\d{3,4})',
        r'(JUFD[-_]?\d{3,4})',
        r'(JUL[-_]?\d{3,4})',
        r'(JUQ[-_]?\d{3,4})',
        r'(JUY[-_]?\d{3,4})',
        r'(JUX[-_]?\d{3,4})',
        r'(PRED[-_]?\d{3,4})',
        r'(CAWD[-_]?\d{3,4})',
        r'(FSDSS[-_]?\d{3,4})',
        r'(FSD[-_]?\d{3,4})',
        r'(HND[-_]?\d{3,4})',
        r'(HND[-_]?\d{3,4})',
        r'(PPPD[-_]?\d{3,4})',
        r'(ABW[-_]?\d{3,4})',
        r'(ABP[-_]?\d{3,4})',
        r'(SDDE[-_]?\d{3,4})',
        r'(SDJS[-_]?\d{3,4})',
        r'(SDMU[-_]?\d{3,4})',
        r'(KIRE[-_]?\d{3,4})',
        r'(KTKL[-_]?\d{3,4})',
        r'(KTKC[-_]?\d{3,4})',
        r'(VEMA[-_]?\d{3,4})',
        r'(VENU[-_]?\d{3,4})',
        r'(VENZ[-_]?\d{3,4})',
        r'(GVG[-_]?\d{3,4})',
        r'(GIGL[-_]?\d{3,4})',
        r'(HBAD[-_]?\d{3,4})',
        r'(HND[-_]?\d{3,4})',
    ]
    
    for pattern in code_patterns:
        match = re.search(pattern, clean_name, re.IGNORECASE)
        if match:
            code = match.group(1).upper()
            code = re.sub(r'_', '-', code)
            return code
    
    clean_name = re.sub(r'[\[\]【】]', '', clean_name)
    clean_name = re.sub(r'\s+', ' ', clean_name).strip()
    
    if '.' in clean_name:
        clean_name = clean_name.rsplit('.', 1)[0]
    
    return clean_name if clean_name else name

load_download_history()

def init_watcher_from_config():
    """Initialize watcher from saved config"""
    watcher_config = config.get("directory_watcher", {})
    watch_dirs = watcher_config.get("watch_directories", [])
    
    for wd in watch_dirs:
        path = wd.get("path", "")
        if path and os.path.isdir(path):
            watch_dir = WatchDirectory(
                path=path,
                enabled=wd.get("enabled", True),
                file_types=wd.get("file_types", watcher_config.get("default_file_types", [])),
                output_dir=wd.get("output_dir", watcher_config.get("default_output_dir", "")),
                use_ai=wd.get("use_ai", watcher_config.get("use_ai_by_default", False))
            )
            watcher.add_watch_directory(watch_dir)
            print(f"[Watcher] Loaded directory: {path}")
    
    watcher.set_process_callback(process_new_video_file)
    
    if watcher_config.get("enabled", False) and watcher.get_watch_directories():
        watcher.start()
        print(f"[Watcher] Auto-started monitoring")

# Data models
class ConfigModel(BaseModel):
    video_dir: str = ""
    save_dir: str = ""
    min_score: float = 0.0
    language: str = ""
    timeout: float = 60.0
    retries: int = 2
    video_extensions: List[str] = [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v"]
    ai_evaluator: Optional[Dict[str, Any]] = None

class SearchRequest(BaseModel):
    keyword: str
    min_score: Optional[float] = None
    language: Optional[str] = None

# Helper functions
def ensure_unique_path(path: Path) -> Path:
    """Ensure path is unique, add number if file exists"""
    if not path.exists():
        return path
    
    base = path.stem
    ext = path.suffix
    parent = path.parent
    counter = 1
    
    while path.exists():
        path = parent / f"{base}_{counter}{ext}"
        counter += 1
    
    return path


# API Routes
@app.get("/")
async def root():
    """Home page"""
    try:
        html_file = TEMPLATES_DIR / "index.html"
        if html_file.exists():
            return FileResponse(
                path=str(html_file),
                media_type="text/html",
                headers={"Cache-Control": "no-cache"}
            )
        else:
            error_html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thunder Subtitle Web UI</title>
</head>
<body>
    <h1>File Not Found</h1>
    <p>index.html file does not exist</p>
</body>
</html>"""
            return SafeJSONResponse(content={"error": "File not found"}, status_code=404)
    except Exception as e:
        print(f"Error reading HTML file: {e}")
        return SafeJSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/test", response_class=HTMLResponse)
async def test_page():
    """Test page"""
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Test Page</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f5f5f5;
                padding: 20px;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .status {
                padding: 10px;
                margin: 10px 0;
                border-radius: 5px;
            }
            .success {
                background-color: #d4edda;
                color: #155724;
            }
            .info {
                background-color: #d1ecf1;
                color: #0c5460;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Test Page</h1>
            <div class="status success">
                <strong>Server is running normally</strong>
            </div>
            <div class="status info">
                <p><strong>Test 1:</strong> Basic page load - <span style="color: green;">Success</span></p>
                <p><strong>Test 2:</strong> HTML rendering - <span style="color: green;">Success</span></p>
                <p><strong>Test 3:</strong> CSS styles - <span style="color: green;">Success</span></p>
            </div>
            <h2>API Tests</h2>
            <div class="status info">
                <p><strong>Config API:</strong> <a href="/api/config" target="_blank">/api/config</a></p>
                <p><strong>Search API:</strong> POST /api/search</p>
                <p><strong>Scan API:</strong> POST /api/scan</p>
                <p><strong>Download API:</strong> POST /api/download</p>
            </div>
        </div>
    </body>
    </html>
    """)

@app.options("/{path:path}")
async def options_handler(path: str):
    """Handle OPTIONS requests for CORS"""
    return SafeJSONResponse(content={}, status_code=204)

@app.get("/favicon.ico")
async def favicon():
    """Return empty favicon"""
    return Response(content=b"", media_type="image/x-icon")

@app.get("/@vite/client")
async def vite_client():
    """Handle Vite dev tools requests"""
    return Response(content=b"", media_type="text/plain")

@app.get("/api/config")
async def get_config():
    """Get config"""
    return SafeJSONResponse(content=config)

@app.post("/api/config")
async def update_config(config_data: ConfigModel):
    """Update config"""
    global config
    data = config_data.dict(exclude_none=True)
    config.update(data)
    save_config()
    return SafeJSONResponse(content={"success": True, "config": config})


@app.post("/api/config/import")
async def import_config(request: Request):
    """Import full config"""
    global config
    try:
        data = await request.json()
        
        allowed_keys = [
            "video_dir", "save_dir", "min_score", "language", 
            "timeout", "retries", "concurrency",
            "ai_evaluator", "directory_watcher", "smb"
        ]
        
        imported_config = {}
        for key in allowed_keys:
            if key in data:
                imported_config[key] = data[key]
        
        config.update(imported_config)
        save_config()
        
        if "directory_watcher" in imported_config:
            init_watcher_from_config()
        
        return SafeJSONResponse(content={
            "success": True, 
            "message": "配置导入成功",
            "config": config
        })
    except Exception as e:
        return SafeJSONResponse(content={
            "success": False,
            "error": str(e)
        })


@app.post("/api/config/reset")
async def reset_config():
    """Reset config to default"""
    global config
    
    default_config = {
        "video_dir": "",
        "save_dir": "./subtitles",
        "min_score": 0.0,
        "language": "",
        "timeout": 60.0,
        "retries": 2,
        "concurrency": 3,
        "ai_evaluator": {
            "enabled": False,
            "api_key": "",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-chat"
        },
        "directory_watcher": {
            "enabled": False,
            "watch_directories": [],
            "default_output_dir": "./subtitles",
            "default_file_types": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".rmvb", ".rm", ".ts", ".m2ts"],
            "use_ai_by_default": False
        },
        "smb": {
            "host": "",
            "port": 445,
            "share": "",
            "user": "",
            "password": "",
            "dir_path": "",
            "output_dir": "",
            "file_types": [".mp4", ".avi", ".mkv", ".wmv", ".strm"],
            "recursive": True,
            "use_ai": False,
            "save_to_video_dir": False,
            "skip_built_in_sub": False,
            "enable_size_filter": False,
            "size_filters": []
        }
    }
    
    config = default_config
    save_config()
    
    if watcher:
        watcher.stop()
    
    return SafeJSONResponse(content={
        "success": True,
        "message": "配置已初始化",
        "config": config
    })


class AIConfigModel(BaseModel):
    enabled: bool = False
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"


@app.get("/api/ai-config")
async def get_ai_config():
    """Get AI evaluator config"""
    ai_config = config.get("ai_evaluator", {})
    return SafeJSONResponse(content={
        "success": True,
        "ai_config": ai_config
    })


@app.post("/api/ai-config")
async def update_ai_config(ai_config_data: AIConfigModel):
    """Update AI evaluator config"""
    global config
    config["ai_evaluator"] = ai_config_data.dict()
    save_config()
    return SafeJSONResponse(content={
        "success": True,
        "ai_config": config["ai_evaluator"]
    })


@app.post("/api/evaluate-subtitle")
async def evaluate_subtitle(request: Request):
    """Evaluate subtitle quality using AI"""
    try:
        data = await request.json()
        url = data.get("url", "")
        ext = data.get("ext", "srt")
        
        if not url:
            return SafeJSONResponse(content={
                "success": False,
                "error": "No URL provided"
            })
        
        client = ThunderClient()
        content_bytes = await client.download_bytes(url=url, timeout_s=config.get("timeout", 60.0))
        
        try:
            content = content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            content = content_bytes.decode('gbk', errors='ignore')
        
        evaluator = get_evaluator(config)
        result = evaluator.evaluate(content, ext)
        
        return SafeJSONResponse(content={
            "success": True,
            "result": {
                "available": result.available,
                "fluency": result.fluency,
                "accuracy": result.accuracy,
                "localization": result.localization,
                "professionalism": result.professionalism,
                "overall_score": result.overall_score,
                "is_machine_translation": result.is_machine_translation,
                "confidence": result.confidence,
                "issues": result.issues,
                "summary": result.summary,
                "elapsed_time": result.elapsed_time,
                "error": result.error
            }
        })
        
    except Exception as e:
        print(f"Evaluate subtitle error: {e}")
        import traceback
        traceback.print_exc()
        return SafeJSONResponse(content={
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/search")
async def search_subtitles(request: SearchRequest):
    """Search subtitles"""
    try:
        print(f"Search request: keyword={request.keyword}, min_score={request.min_score}, language={request.language}")
        client = ThunderClient()
        
        results = await client.search(query=request.keyword)
        
        print(f"Search results: {len(results)}")
        
        results = results[:50]
        
        subtitles = []
        for item in results:
            language_str = ", ".join(item.languages) if item.languages else "Unknown"
            
            subtitles.append({
                "gcid": item.gcid,
                "cid": item.cid,
                "name": item.name,
                "ext": item.ext,
                "url": item.url,
                "score": item.score,
                "language": language_str,
                "size": item.duration
            })
        
        print(f"Returning subtitles: {len(subtitles)}")
        
        response_data = {
            "success": True,
            "subtitles": subtitles,
            "count": len(subtitles)
        }
        
        return SafeJSONResponse(content=response_data)
    except Exception as e:
        print(f"Search error: {e}")
        import traceback
        traceback.print_exc()
        return SafeJSONResponse(content={
            "success": False,
            "error": str(e)
        }, status_code=500)

@app.post("/api/preview")
async def preview_subtitle(request: SearchRequest):
    """Preview subtitle"""
    try:
        client = ThunderClient()
        
        subtitle_data = await client.download_bytes(url=request.keyword)
        
        try:
            preview_text = subtitle_data.decode('utf-8')
        except:
            try:
                preview_text = subtitle_data.decode('gbk')
            except:
                preview_text = subtitle_data.decode('latin-1')
        
        lines = preview_text.split('\n')[:50]
        preview = '\n'.join(lines)
        
        return SafeJSONResponse(content={
            "success": True,
            "preview": preview
        })
    except Exception as e:
        print(f"Preview error: {e}")
        return SafeJSONResponse(content={
            "success": False,
            "error": str(e)
        }, status_code=500)

@app.post("/api/download")
async def download_subtitle(request: Request):
    """Download subtitle"""
    try:
        data = await request.json()
        url = data.get("url")
        name = data.get("name", "")
        ext = data.get("ext", "srt")
        video_name = data.get("video_name", "")
        
        if not url:
            raise HTTPException(status_code=400, detail="URL cannot be empty")
        
        client = ThunderClient()
        
        subtitle_data = await download_with_retries(
            client,
            url=url,
            timeout_s=config.get("timeout", 60.0),
            retries=config.get("retries", 2)
        )
        
        subtitle_data = detect_and_convert_to_utf8(subtitle_data)
        
        if video_name:
            if "." in video_name:
                base_name = video_name.rsplit(".", 1)[0]
            else:
                base_name = video_name
            filename = f"{base_name}.{ext}"
        elif name:
            if "." in name:
                filename = name
            else:
                filename = f"{name}.{ext}"
        else:
            import time
            timestamp = int(time.time() * 1000)
            filename = f"subtitle_{timestamp}.{ext}"
        
        save_dir = config.get("save_dir", "")
        print(f"Save directory config: {save_dir}")
        
        if save_dir:
            try:
                import os
                if not os.path.exists(save_dir):
                    os.makedirs(save_dir, exist_ok=True)
                    print(f"Created directory: {save_dir}")
                else:
                    print(f"Directory exists: {save_dir}")
                
                file_path = os.path.join(save_dir, filename)
                print(f"Save file path: {file_path}")
                
                with open(file_path, 'wb') as f:
                    f.write(subtitle_data)
                print(f"File saved successfully: {file_path}")
                
                return SafeJSONResponse(content={
                    "success": True,
                    "message": f"Subtitle saved to: {file_path}",
                    "file_path": file_path
                })
            except Exception as e:
                print(f"Failed to save file: {e}")
                import traceback
                traceback.print_exc()
                return SafeJSONResponse(content={
                    "success": False,
                    "error": f"Failed to save file: {e}",
                    "fallback": True
                })
        else:
            return Response(
                content=subtitle_data,
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}"
                }
            )
    except Exception as e:
        print(f"Download error: {e}")
        import traceback
        traceback.print_exc()
        return SafeJSONResponse(content={
            "success": False,
            "error": str(e)
        }, status_code=500)

@app.post("/api/batch-download")
async def batch_download_subtitles(request: Request):
    """Batch download subtitles"""
    try:
        data = await request.json()
        videos = data.get("videos", [])
        use_ai = data.get("use_ai", False)
        
        if not videos:
            return SafeJSONResponse(content={
                "success": False,
                "error": "No videos selected"
            })
        
        print(f"Batch download request: {len(videos)} videos, AI: {use_ai}")
        
        client = ThunderClient()
        evaluator = get_evaluator(config) if use_ai else None
        ai_enabled = use_ai and evaluator and evaluator.is_available()
        
        results = []
        success_count = 0
        fail_count = 0
        
        for video in videos:
            video_name = video.get("name", "")
            if "." in video_name:
                base_name = video_name.rsplit(".", 1)[0]
            else:
                base_name = video_name
            
            try:
                search_results = await client.search(query=base_name)
                
                if search_results:
                    best_subtitle = None
                    best_final_score = -1
                    
                    if ai_enabled:
                        print(f"  Using AI evaluation for {video_name}, evaluating {len(search_results)} subtitles...")
                        
                        async def evaluate_single_video_subtitle(sub, idx):
                            try:
                                filename_score = calculate_filename_similarity(video_name, sub.name)
                                
                                if filename_score == 0:
                                    return None
                                
                                sub_data = await download_with_retries(
                                    client,
                                    url=sub.url,
                                    timeout_s=config.get("timeout", 60.0),
                                    retries=1
                                )
                                
                                try:
                                    content = sub_data.decode('utf-8')
                                except UnicodeDecodeError:
                                    content = sub_data.decode('gbk', errors='ignore')
                                
                                eval_result = evaluator.evaluate(content, sub.ext or "srt")
                                
                                if eval_result.available:
                                    quality_score = eval_result.overall_score
                                    final_score = filename_score * 0.4 + quality_score * 0.6
                                    print(f"    评估字幕: {sub.name} -> 匹配度:{filename_score:.0f}% 质量分:{quality_score:.0f} 综合分:{final_score:.2f}")
                                    return {
                                        'sub': sub,
                                        'data': sub_data,
                                        'filename_score': filename_score,
                                        'quality_score': quality_score,
                                        'final_score': final_score,
                                        'is_machine': eval_result.is_machine_translation
                                    }
                                return None
                            except Exception as e:
                                print(f"    AI eval failed for {sub.name}: {e}")
                                return None
                        
                        batch_size = 5
                        all_eval_results = []
                        
                        for i in range(0, len(search_results), batch_size):
                            batch = search_results[i:i + batch_size]
                            tasks = [evaluate_single_video_subtitle(sub, idx) for idx, sub in enumerate(batch)]
                            batch_results = await asyncio.gather(*tasks)
                            all_eval_results.extend([r for r in batch_results if r is not None])
                        
                        if all_eval_results:
                            all_eval_results.sort(key=lambda x: x['final_score'], reverse=True)
                            best = all_eval_results[0]
                            best_subtitle = best['sub']
                            subtitle_data = best['data']
                            best_subtitle_ai_score = best['quality_score']
                            best_subtitle_is_mt = best['is_machine']
                            print(f"    Best: {best_subtitle.name} (匹配度:{best['filename_score']:.0f}% 综合分:{best['final_score']:.2f})")
                        else:
                            print(f"    所有字幕匹配度均为0，跳过下载")
                            results.append({
                                "video": video_name,
                                "status": "no_match",
                                "message": "所有字幕匹配度为0"
                            })
                            fail_count += 1
                            continue
                    else:
                        best_filename_score = 0
                        for sub in search_results:
                            filename_score = calculate_filename_similarity(video_name, sub.name)
                            if filename_score > best_filename_score:
                                best_filename_score = filename_score
                                best_subtitle = sub
                        
                        if best_subtitle and best_filename_score > 0:
                            print(f"    Best by filename: {best_subtitle.name} (匹配度:{best_filename_score:.0f}%)")
                        else:
                            print(f"    所有字幕匹配度均为0，跳过下载")
                            results.append({
                                "video": video_name,
                                "status": "no_match",
                                "message": "所有字幕匹配度为0"
                            })
                            fail_count += 1
                            continue
                        
                        subtitle_data = await download_with_retries(
                            client,
                            url=best_subtitle.url,
                            timeout_s=config.get("timeout", 60.0),
                            retries=config.get("retries", 2)
                        )
                        best_subtitle_ai_score = None
                        best_subtitle_is_mt = None
                    
                    subtitle_data = detect_and_convert_to_utf8(subtitle_data)
                    
                    ext = best_subtitle.ext or "srt"
                    filename = f"{base_name}.{ext}"
                    
                    save_dir = config.get("save_dir", "")
                    if save_dir:
                        import os
                        if not os.path.exists(save_dir):
                            os.makedirs(save_dir, exist_ok=True)
                        
                        file_path = os.path.join(save_dir, filename)
                        
                        with open(file_path, 'wb') as f:
                            f.write(subtitle_data)
                        
                        result_item = {
                            "video": video_name,
                            "subtitle": best_subtitle.name,
                            "status": "success",
                            "file_path": file_path,
                            "score": best_subtitle.score
                        }
                        
                        if ai_enabled and best_subtitle_ai_score is not None:
                            result_item["ai_score"] = best_subtitle_ai_score
                            result_item["is_machine_translation"] = best_subtitle_is_mt
                        
                        results.append(result_item)
                        success_count += 1
                        print(f"Success: {video_name} -> {filename}" + 
                              (f" (AI: {best_subtitle_ai_score})" if ai_enabled else ""))
                    else:
                        results.append({
                            "video": video_name,
                            "status": "failed",
                            "error": "Save directory not configured"
                        })
                        fail_count += 1
                else:
                    results.append({
                        "video": video_name,
                        "status": "not_found",
                        "error": "No subtitles found"
                    })
                    fail_count += 1
                    print(f"Not found: {video_name}")
                
            except Exception as e:
                results.append({
                    "video": video_name,
                    "status": "failed",
                    "error": str(e)
                })
                fail_count += 1
                print(f"Failed: {video_name} - {e}")
        
        return SafeJSONResponse(content={
            "success": True,
            "total": len(videos),
            "success_count": success_count,
            "fail_count": fail_count,
            "results": results,
            "ai_enabled": ai_enabled
        })
        
    except Exception as e:
        print(f"Batch download error: {e}")
        import traceback
        traceback.print_exc()
        return SafeJSONResponse(content={
            "success": False,
            "error": str(e)
        }, status_code=500)

@app.get("/api/download/file/{filename}")
async def download_file(filename: str):
    """Download saved file"""
    save_dir = Path(config.get("save_dir", ""))
    if not save_dir:
        raise HTTPException(status_code=400, detail="Save directory not configured")
    
    file_path = save_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type='text/plain'
    )

@app.post("/api/scan")
async def scan_videos():
    """Scan video files"""
    try:
        video_dir = config.get("video_dir", "")
        if not video_dir:
            return SafeJSONResponse(content={
                "success": False,
                "error": "Video directory not configured"
            })
        
        video_extensions = config.get("video_extensions", ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'])
        video_files = []
        
        video_path = Path(video_dir)
        if not video_path.exists():
            return SafeJSONResponse(content={
                "success": False,
                "error": "Video directory does not exist"
            })
        
        for ext in video_extensions:
            for file in video_path.rglob(f"*{ext}"):
                stat = file.stat()
                video_files.append({
                    "name": file.name,
                    "path": str(file),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })
        
        video_files.sort(key=lambda x: x["modified"], reverse=True)
        
        return SafeJSONResponse(content={
            "success": True,
            "video_files": video_files,
            "count": len(video_files)
        })
    except Exception as e:
        print(f"Scan error: {e}")
        import traceback
        traceback.print_exc()
        return SafeJSONResponse(content={
            "success": False,
            "error": str(e)
        }, status_code=500)


class WatchDirectoryModel(BaseModel):
    path: str
    enabled: bool = True
    file_types: List[str] = [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".rmvb", ".rm", ".ts", ".m2ts"]
    output_dir: str = ""
    use_ai: bool = False


@app.get("/api/watcher/status")
async def get_watcher_status():
    """Get directory watcher status"""
    return SafeJSONResponse(content={
        "success": True,
        "available": HAS_WATCHDOG,
        "running": watcher.is_running(),
        "watch_directories": watcher.get_watch_directories(),
        "event_log": watcher.get_event_log(20)
    })


@app.post("/api/watcher/start")
async def start_watcher():
    """Start directory watcher"""
    if not HAS_WATCHDOG:
        return SafeJSONResponse(content={
            "success": False,
            "error": "watchdog库未安装，请运行: pip install watchdog"
        })
    
    if watcher.is_running():
        return SafeJSONResponse(content={
            "success": True,
            "running": True,
            "message": "目录监控已在运行中"
        })
    
    if not watcher.get_watch_directories():
        watcher_config = config.get("directory_watcher", {})
        watch_dirs = watcher_config.get("watch_directories", [])
        for wd in watch_dirs:
            watch_dir = WatchDirectory(
                path=wd.get("path", ""),
                enabled=wd.get("enabled", True),
                file_types=wd.get("file_types", watcher_config.get("default_file_types", [])),
                output_dir=wd.get("output_dir", watcher_config.get("default_output_dir", "")),
                use_ai=wd.get("use_ai", watcher_config.get("use_ai_by_default", False))
            )
            watcher.add_watch_directory(watch_dir)
    
    watcher.set_process_callback(process_new_video_file)
    
    success = watcher.start()
    
    if success:
        save_watcher_config()
    
    return SafeJSONResponse(content={
        "success": success,
        "running": watcher.is_running(),
        "message": "目录监控已启动" if success else "启动失败"
    })


@app.post("/api/watcher/stop")
async def stop_watcher():
    """Stop directory watcher"""
    watcher.stop()
    return SafeJSONResponse(content={
        "success": True,
        "running": False,
        "message": "目录监控已停止"
    })


@app.get("/api/watcher/directories")
async def get_watch_directories():
    """Get all watch directories"""
    return SafeJSONResponse(content={
        "success": True,
        "directories": watcher.get_watch_directories()
    })


@app.post("/api/watcher/directories")
async def add_watch_directory(watch_dir: WatchDirectoryModel):
    """Add a watch directory"""
    if not os.path.isdir(watch_dir.path):
        return SafeJSONResponse(content={
            "success": False,
            "error": f"目录不存在: {watch_dir.path}"
        })
    
    wd = WatchDirectory(
        path=watch_dir.path,
        enabled=watch_dir.enabled,
        file_types=watch_dir.file_types,
        output_dir=watch_dir.output_dir,
        use_ai=watch_dir.use_ai
    )
    
    success = watcher.add_watch_directory(wd)
    
    if success:
        save_watcher_config()
    
    return SafeJSONResponse(content={
        "success": success,
        "message": "添加成功" if success else "添加失败，目录可能已存在"
    })


@app.delete("/api/watcher/directories")
async def remove_watch_directory(request: Request):
    """Remove a watch directory"""
    data = await request.json()
    path = data.get("path", "")
    
    success = watcher.remove_watch_directory(path)
    
    if success:
        save_watcher_config()
    
    return SafeJSONResponse(content={
        "success": success,
        "message": "移除成功" if success else "移除失败，目录不存在"
    })


@app.put("/api/watcher/directories")
async def update_watch_directory(watch_dir: WatchDirectoryModel):
    """Update a watch directory"""
    wd = WatchDirectory(
        path=watch_dir.path,
        enabled=watch_dir.enabled,
        file_types=watch_dir.file_types,
        output_dir=watch_dir.output_dir,
        use_ai=watch_dir.use_ai
    )
    
    success = watcher.update_watch_directory(wd)
    
    if success:
        save_watcher_config()
    
    return SafeJSONResponse(content={
        "success": success,
        "message": "更新成功" if success else "更新失败"
    })


@app.get("/api/watcher/events")
async def get_watcher_events(limit: int = 50):
    """Get watcher event log"""
    return SafeJSONResponse(content={
        "success": True,
        "events": watcher.get_event_log(limit)
    })


@app.get("/api/history")
async def get_download_history():
    """Get download history"""
    return SafeJSONResponse(content={
        "success": True,
        "history": _download_history
    })


@app.post("/api/history")
async def add_history_item(request: Request):
    """Add item to download history"""
    data = await request.json()
    add_download_history(data)
    return SafeJSONResponse(content={
        "success": True,
        "message": "添加成功"
    })


@app.delete("/api/history")
async def clear_download_history():
    """Clear download history"""
    global _download_history
    _download_history = []
    save_download_history()
    return SafeJSONResponse(content={
        "success": True,
        "message": "历史已清空"
    })


def save_watcher_config():
    """Save watcher configuration to config file"""
    global config
    
    watch_dirs = watcher.get_watch_directories()
    
    clean_watch_dirs = []
    for wd in watch_dirs:
        clean_watch_dirs.append({
            "path": wd["path"],
            "enabled": wd["enabled"],
            "file_types": wd["file_types"],
            "output_dir": wd["output_dir"],
            "use_ai": wd["use_ai"]
        })
    
    if "directory_watcher" not in config:
        config["directory_watcher"] = {}
    
    config["directory_watcher"]["watch_directories"] = clean_watch_dirs
    config["directory_watcher"]["enabled"] = watcher.is_running()
    save_config()
    print(f"[Watcher] Config saved: {len(clean_watch_dirs)} directories")


async def process_new_video_file(file_path: str, watch_dir: WatchDirectory):
    """Process a new video file detected by watcher"""
    try:
        print(f"[Watcher] Processing new file: {file_path}")
        
        file_name = os.path.basename(file_path)
        if "." in file_name:
            base_name = file_name.rsplit(".", 1)[0]
        else:
            base_name = file_name
        
        client = ThunderClient()
        search_results = await client.search(query=base_name)
        
        if not search_results:
            print(f"[Watcher] No subtitles found for: {file_name}")
            return
        
        print(f"[Watcher] Found {len(search_results)} subtitles for: {file_name}")
        
        best_subtitle = None
        subtitle_data = None
        
        if watch_dir.use_ai:
            print(f"[Watcher] AI evaluation enabled, checking availability...")
            evaluator = get_evaluator(config)
            print(f"[Watcher] Evaluator available: {evaluator.is_available()}")
            
            if evaluator.is_available():
                print(f"[Watcher] Starting parallel AI evaluation for top 10 subtitles...")
                
                async def evaluate_single_subtitle(sub, idx):
                    try:
                        filename_score = calculate_filename_similarity(file_name, sub.name)
                        
                        if filename_score == 0:
                            print(f"[Watcher] 跳过字幕: {sub.name} (匹配度:0%)")
                            return None
                        
                        sub_data = await download_with_retries(
                            client,
                            url=sub.url,
                            timeout_s=config.get("timeout", 60.0),
                            retries=1
                        )
                        
                        try:
                            content = sub_data.decode('utf-8')
                        except UnicodeDecodeError:
                            content = sub_data.decode('gbk', errors='ignore')
                        
                        eval_result = evaluator.evaluate(content, sub.ext or "srt")
                        
                        if eval_result.available:
                            quality_score = eval_result.overall_score
                            final_score = filename_score * 0.4 + quality_score * 0.6
                            print(f"[Watcher] 评估字幕: {sub.name} -> 匹配度:{filename_score:.0f}% 质量分:{quality_score:.0f} 综合分:{final_score:.2f}")
                            
                            return {
                                'sub': sub,
                                'data': sub_data,
                                'quality_score': quality_score,
                                'filename_score': filename_score,
                                'final_score': final_score,
                                'is_machine': eval_result.is_machine_translation,
                                'idx': idx
                            }
                        else:
                            return None
                    except Exception as e:
                        print(f"[Watcher] AI eval failed for {sub.name}: {e}")
                        return None
                
                print(f"[Watcher] Starting parallel AI evaluation for {len(search_results)} subtitles...")
                
                batch_size = 5
                all_results = []
                
                for i in range(0, len(search_results), batch_size):
                    batch = search_results[i:i + batch_size]
                    tasks = [
                        evaluate_single_subtitle(sub, idx) 
                        for idx, sub in enumerate(batch)
                    ]
                    batch_results = await asyncio.gather(*tasks)
                    all_results.extend([r for r in batch_results if r is not None])
                
                valid_results = all_results
                
                if valid_results:
                    valid_results.sort(key=lambda x: x['final_score'], reverse=True)
                    best = valid_results[0]
                    best_subtitle = best['sub']
                    subtitle_data = best['data']
                    best_final_score = best['final_score']
                    best_filename_score = best['filename_score']
                    best_quality_score = best['quality_score']
                    
                    print(f"[Watcher] Evaluated {len(valid_results)} subtitles in parallel")
                    print(f"[Watcher] Best subtitle selected: {best_subtitle.name} (匹配度:{best_filename_score:.0f}% 综合分:{best_final_score:.2f})")
                    
                    for r in valid_results[:3]:
                        print(f"[Watcher]   - {r['sub'].name}: 匹配度={r['filename_score']:.0f}% 质量分={r['quality_score']:.0f} 综合分={r['final_score']:.2f}")
                else:
                    print(f"[Watcher] 所有字幕匹配度均为0，跳过下载")
            else:
                print(f"[Watcher] AI evaluator not available, using filename matching")
        else:
            print(f"[Watcher] AI evaluation disabled for this directory")
        
        if not best_subtitle:
            best_filename_score = 0
            for sub in search_results:
                filename_score = calculate_filename_similarity(file_name, sub.name)
                if filename_score > best_filename_score:
                    best_filename_score = filename_score
                    best_subtitle = sub
            
            if best_subtitle and best_filename_score > 0:
                print(f"[Watcher] Best by filename: {best_subtitle.name} (匹配度:{best_filename_score:.0f}%)")
                subtitle_data = await download_with_retries(
                    client,
                    url=best_subtitle.url,
                    timeout_s=config.get("timeout", 60.0),
                    retries=config.get("retries", 2)
                )
            else:
                print(f"[Watcher] 所有字幕匹配度均为0，跳过下载")
                return
        
        subtitle_data = detect_and_convert_to_utf8(subtitle_data)
        
        output_dir = watch_dir.output_dir or config.get("save_dir", "./subtitles")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        content_preview = subtitle_data[:500].decode('utf-8', errors='ignore')
        
        if content_preview.strip().startswith('[Script Info]'):
            actual_ext = 'ass'
        elif content_preview.strip().startswith('{\\'):
            actual_ext = 'ssa'
        else:
            actual_ext = 'srt'
        
        ext = actual_ext
        
        clean_name = clean_subtitle_filename(base_name)
        subtitle_path = os.path.join(output_dir, f"{clean_name}.{ext}")
        
        with open(subtitle_path, 'wb') as f:
            f.write(subtitle_data)
        
        print(f"[Watcher] Subtitle saved: {subtitle_path} (cleaned name: {clean_name}, format: {actual_ext})")
        
        watcher._log_event("saved", subtitle_path, "success", f"字幕保存成功: {os.path.basename(subtitle_path)}")
        
        add_download_history({
            "name": f"{clean_name}.{ext}",
            "path": subtitle_path,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "watcher"
        })
        
    except Exception as e:
        print(f"[Watcher] Error processing file: {e}")
        import traceback
        traceback.print_exc()
        watcher._log_event("error", file_path, "error", f"处理文件失败: {str(e)}")


init_watcher_from_config()


# Helper function for retries
async def download_with_retries(
    client: ThunderClient,
    *,
    url: str,
    timeout_s: float,
    retries: int,
    retry_sleep_s: float = 0.5,
) -> bytes:
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return await client.download_bytes(url=url, timeout_s=timeout_s)
        except Exception as e:
            last_err = e
            if attempt < retries:
                await asyncio.sleep(retry_sleep_s)
    raise last_err

# ==================== SMB APIs ====================

def check_smb_available():
    """Check if pysmb is available"""
    try:
        from smb.SMBConnection import SMBConnection
        return True
    except ImportError:
        return False

class SizeFilterModel(BaseModel):
    file_type: str
    min_size: int = 0
    max_size: int = 0

class SmbConfigModel(BaseModel):
    host: str
    port: int = 445
    share: str
    user: str
    password: str
    dir_path: str = ""
    output_dir: str = ""
    file_types: List[str] = [".mp4", ".avi", ".mkv"]
    recursive: bool = True
    use_ai: bool = True
    save_to_video_dir: bool = False
    skip_built_in_sub: bool = False
    enable_size_filter: bool = False
    size_filters: List[SizeFilterModel] = []
    selected_videos: List[str] = []

@app.get("/api/smb/available")
async def api_smb_available():
    """Check if SMB is available"""
    return {"available": check_smb_available()}

@app.post("/api/smb/test")
async def api_smb_test(config: SmbConfigModel):
    """Test SMB connection"""
    if not check_smb_available():
        return {"success": False, "error": "pysmb库未安装，请运行: pip install pysmb"}
    
    try:
        from smb.SMBConnection import SMBConnection
        
        conn = SMBConnection(
            config.user,
            config.password,
            "thunder-subtitle-cli",
            config.host,
            use_ntlm_v2=True,
            is_direct_tcp=True,
        )
        
        ok = conn.connect(config.host, config.port)
        if ok:
            shares = conn.listShares()
            conn.close()
            share_names = [s.name for s in shares]
            return {"success": True, "shares": share_names}
        else:
            return {"success": False, "error": "连接失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def normalize_smb_path(dir_path: str) -> str:
    """Normalize SMB path to POSIX format"""
    parts = [p for p in dir_path.replace("\\", "/").split("/") if p]
    return "/" + "/".join(parts) if parts else "/"

def list_smb_recursive(conn, share: str, path: str, file_types: List[str], recursive: bool) -> List[Dict]:
    """Recursively list video files in SMB share"""
    results = []
    
    try:
        files = conn.listPath(share, path)
        
        for f in files:
            if f.filename in (".", ".."):
                continue
            
            full_path = f"{path}/{f.filename}" if path != "/" else f"/{f.filename}"
            
            if f.isDirectory:
                if recursive:
                    results.extend(list_smb_recursive(conn, share, full_path, file_types, recursive))
            else:
                ext = os.path.splitext(f.filename)[1].lower()
                if ext in file_types:
                    video_dir = os.path.dirname(full_path)
                    results.append({
                        "name": f.filename,
                        "path": full_path,
                        "dir": video_dir,
                        "size": f.file_size,
                        "ext": ext
                    })
    except Exception as e:
        print(f"[SMB] Error listing {path}: {e}")
    
    return results

@app.post("/api/smb/scan")
async def api_smb_scan(config: SmbConfigModel):
    """Scan SMB share for video files"""
    if not check_smb_available():
        return {"success": False, "error": "pysmb库未安装", "videos": []}
    
    try:
        from smb.SMBConnection import SMBConnection
        
        conn = SMBConnection(
            config.user,
            config.password,
            "thunder-subtitle-cli",
            config.host,
            use_ntlm_v2=True,
            is_direct_tcp=True,
        )
        
        ok = conn.connect(config.host, config.port)
        if not ok:
            return {"success": False, "error": "连接失败", "videos": []}
        
        share_path = normalize_smb_path(config.dir_path)
        videos = list_smb_recursive(conn, config.share, share_path, config.file_types, config.recursive)
        conn.close()
        
        if config.skip_built_in_sub:
            import re
            built_in_pattern = re.compile(r'-[UC]?C\b|-U-C\b', re.IGNORECASE)
            original_count = len(videos)
            videos = [v for v in videos if not built_in_pattern.search(v["name"])]
            skipped_count = original_count - len(videos)
            if skipped_count > 0:
                print(f"[SMB] 跳过 {skipped_count} 个自带字幕文件")
        
        if config.enable_size_filter and config.size_filters:
            size_filter_map = {sf.file_type: sf for sf in config.size_filters}
            
            filtered_videos = []
            for v in videos:
                ext = v["ext"]
                if ext in size_filter_map:
                    sf = size_filter_map[ext]
                    min_bytes = sf.min_size * 1024 * 1024 if sf.min_size > 0 else 0
                    max_bytes = sf.max_size * 1024 * 1024 if sf.max_size > 0 else None
                    
                    if min_bytes > 0 and v["size"] < min_bytes:
                        continue
                    if max_bytes and v["size"] > max_bytes:
                        continue
                filtered_videos.append(v)
            videos = filtered_videos
        
        return {"success": True, "videos": videos, "count": len(videos)}
    except Exception as e:
        return {"success": False, "error": str(e), "videos": []}

@app.post("/api/smb/download")
async def api_smb_download(smb_config: SmbConfigModel):
    """Batch download subtitles for SMB videos"""
    if not check_smb_available():
        return {"success": False, "error": "pysmb库未安装"}
    
    try:
        from smb.SMBConnection import SMBConnection
        
        conn = SMBConnection(
            smb_config.user,
            smb_config.password,
            "thunder-subtitle-cli",
            smb_config.host,
            use_ntlm_v2=True,
            is_direct_tcp=True,
        )
        
        ok = conn.connect(smb_config.host, smb_config.port)
        if not ok:
            return {"success": False, "error": "连接失败"}
        
        share_path = normalize_smb_path(smb_config.dir_path)
        videos = list_smb_recursive(conn, smb_config.share, share_path, smb_config.file_types, smb_config.recursive)
        
        if smb_config.selected_videos:
            selected_paths = set(smb_config.selected_videos)
            videos = [v for v in videos if v["path"] in selected_paths]
        
        if smb_config.skip_built_in_sub:
            import re
            built_in_pattern = re.compile(r'-[UC]?C\b|-U-C\b', re.IGNORECASE)
            original_count = len(videos)
            videos = [v for v in videos if not built_in_pattern.search(v["name"])]
            skipped_count = original_count - len(videos)
            if skipped_count > 0:
                print(f"[SMB] 跳过 {skipped_count} 个自带字幕文件")
        
        if not videos:
            conn.close()
            return {"success": True, "message": "未找到视频文件", "results": []}
        
        output_dir = smb_config.output_dir or config.get("save_dir", "./subtitles")
        if not output_dir:
            output_dir = "./subtitles"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        ai_evaluator = None
        if smb_config.use_ai:
            ai_evaluator = get_evaluator(config)
        
        results = []
        client = ThunderClient()
        
        for video in videos:
            video_name = os.path.splitext(video["name"])[0]
            clean_name = clean_subtitle_filename(video_name)
            
            try:
                search_results = await client.search(query=video_name)
                
                if not search_results:
                    results.append({
                        "video": video["name"],
                        "status": "no_subtitle",
                        "message": "未找到字幕"
                    })
                    continue
                
                best_subtitle = None
                subtitle_data = None
                
                if ai_evaluator and ai_evaluator.is_available():
                    print(f"[SMB] AI评估已启用，正在并发评估 {len(search_results)} 个字幕...")
                    
                    async def evaluate_single_smb_subtitle(item, idx):
                        try:
                            filename_score = calculate_filename_similarity(video["name"], item.name)
                            
                            if filename_score == 0:
                                return None
                            
                            data = await client.download_bytes(url=item.url)
                            text_content = data.decode('utf-8', errors='ignore')
                            text = extract_text(text_content, item.ext)
                            
                            if text:
                                result = ai_evaluator.evaluate(text[:2000], item.ext)
                                quality_score = result.overall_score
                                final_score = filename_score * 0.4 + quality_score * 0.6
                                print(f"[SMB] 评估字幕: {item.name} -> 匹配度:{filename_score:.0f}% 质量分:{quality_score:.0f} 综合分:{final_score:.2f}")
                                return {
                                    'sub': item,
                                    'data': data,
                                    'filename_score': filename_score,
                                    'quality_score': quality_score,
                                    'final_score': final_score
                                }
                            return None
                        except Exception as e:
                            print(f"[SMB] 评估字幕失败: {item.name} -> {e}")
                            return None
                    
                    batch_size = 5
                    all_eval_results = []
                    
                    for i in range(0, len(search_results), batch_size):
                        batch = search_results[i:i + batch_size]
                        tasks = [evaluate_single_smb_subtitle(item, idx) for idx, item in enumerate(batch)]
                        batch_results = await asyncio.gather(*tasks)
                        all_eval_results.extend([r for r in batch_results if r is not None])
                    
                    if all_eval_results:
                        all_eval_results.sort(key=lambda x: x['final_score'], reverse=True)
                        best = all_eval_results[0]
                        best_subtitle = best['sub']
                        subtitle_data = best['data']
                        print(f"[SMB] 最佳字幕: {best_subtitle.name} (匹配度:{best['filename_score']:.0f}% 综合分:{best['final_score']:.2f})")
                    else:
                        print(f"[SMB] 所有字幕匹配度均为0，跳过下载")
                else:
                    if ai_evaluator:
                        print(f"[SMB] AI评估器不可用: enabled={ai_evaluator.enabled}, has_key={bool(ai_evaluator.api_key)}")
                    
                    best_subtitle = None
                    best_score = 0
                    for item in search_results:
                        filename_score = calculate_filename_similarity(video["name"], item.name)
                        if filename_score > best_score:
                            best_score = filename_score
                            best_subtitle = item
                    
                    if best_subtitle and best_score > 0:
                        print(f"[SMB] 无AI评估，按文件名匹配选择: {best_subtitle.name} (匹配度:{best_score:.0f}%)")
                        subtitle_data = await client.download_bytes(url=best_subtitle.url)
                    else:
                        print(f"[SMB] 所有字幕匹配度均为0，跳过下载")
                        results.append({
                            "video": video["name"],
                            "status": "no_match",
                            "message": "所有字幕匹配度为0，跳过下载"
                        })
                        continue
                
                if not subtitle_data:
                    results.append({
                        "video": video["name"],
                        "status": "no_match",
                        "message": "无有效字幕"
                    })
                    continue
                
                subtitle_data = detect_and_convert_to_utf8(subtitle_data)
                
                content_preview = subtitle_data[:500].decode('utf-8', errors='ignore')
                if content_preview.strip().startswith('[Script Info]'):
                    ext = 'ass'
                elif content_preview.strip().startswith('{\\'):
                    ext = 'ssa'
                else:
                    ext = 'srt'
                
                if smb_config.save_to_video_dir and video.get("dir"):
                    video_dir = video["dir"]
                    smb_subtitle_dir = normalize_smb_path(video_dir)
                    smb_subtitle_path = f"{smb_subtitle_dir}/{clean_name}.{ext}"
                    
                    try:
                        temp_file = f"temp_subtitle_{clean_name}.{ext}"
                        with open(temp_file, 'wb') as f:
                            f.write(subtitle_data)
                        
                        with open(temp_file, 'rb') as f:
                            conn.storeFile(smb_config.share, smb_subtitle_path, f)
                        
                        import os as os_module
                        os_module.remove(temp_file)
                        
                        subtitle_path = f"\\\\{smb_config.host}\\{smb_config.share}{smb_subtitle_path}"
                    except Exception as smb_err:
                        print(f"[SMB] 写入SMB失败，保存到本地: {smb_err}")
                        smb_dir_path = os.path.join(output_dir, video_dir.lstrip("/"))
                        if not os.path.exists(smb_dir_path):
                            os.makedirs(smb_dir_path, exist_ok=True)
                        subtitle_path = os.path.join(smb_dir_path, f"{clean_name}.{ext}")
                        with open(subtitle_path, 'wb') as f:
                            f.write(subtitle_data)
                else:
                    subtitle_path = os.path.join(output_dir, f"{clean_name}.{ext}")
                    with open(subtitle_path, 'wb') as f:
                        f.write(subtitle_data)
                
                results.append({
                    "video": video["name"],
                    "status": "success",
                    "subtitle": f"{clean_name}.{ext}",
                    "path": subtitle_path
                })
                
                add_download_history({
                    "name": f"{clean_name}.{ext}",
                    "path": subtitle_path,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "smb"
                })
                
                print(f"[SMB] Downloaded: {video['name']} -> {clean_name}.{ext}")
                
            except Exception as e:
                results.append({
                    "video": video["name"],
                    "status": "error",
                    "message": str(e)
                })
                print(f"[SMB] Error processing {video['name']}: {e}")
        
        conn.close()
        return {"success": True, "results": results, "total": len(results)}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/smb/config")
async def api_get_smb_config():
    """Get SMB configuration"""
    smb_config = config.get("smb", {})
    return {"success": True, "config": smb_config}

@app.post("/api/smb/config")
async def api_save_smb_config(smb_config: Dict[str, Any]):
    """Save SMB configuration"""
    config["smb"] = smb_config
    save_config()
    return {"success": True}

# Run server
def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Start server"""
    print(f"Starting FastAPI server...")
    if host == "0.0.0.0":
        print(f"Access URL: http://127.0.0.1:{port} (本机访问)")
        print(f"           http://<你的本地IP>:{port} (局域网其他设备访问)")
    else:
        print(f"Access URL: http://{host}:{port}")
    print(f"Static directory: {STATIC_DIR}")
    print(f"Templates directory: {TEMPLATES_DIR}")
    print(f"Config file: {CONFIG_FILE}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        use_colors=False
    )

if __name__ == "__main__":
    run_server()
