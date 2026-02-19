"""
目录监控模块
监控指定目录，自动为新视频文件下载字幕
"""
from __future__ import annotations

import asyncio
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, List, Dict, Any
from datetime import datetime

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False


@dataclass
class WatchDirectory:
    """监控目录配置"""
    path: str
    enabled: bool = True
    file_types: List[str] = field(default_factory=lambda: [
        ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".rmvb", ".rm"
    ])
    output_dir: str = ""
    use_ai: bool = False


@dataclass
class WatcherEvent:
    """监控事件"""
    event_type: str
    file_path: str
    timestamp: str
    status: str
    message: str


class VideoFileHandler(FileSystemEventHandler):
    """视频文件事件处理器"""
    
    def __init__(
        self,
        watch_dir: WatchDirectory,
        on_new_file: Callable[[str, WatchDirectory], None],
        file_types: List[str]
    ):
        super().__init__()
        self.watch_dir = watch_dir
        self.on_new_file = on_new_file
        self.file_types = [ft.lower() for ft in file_types]
        self._processed_files = set()
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        file_path = event.src_path
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext not in self.file_types:
            return
        
        file_key = f"{file_path}_{os.path.getmtime(file_path) if os.path.exists(file_path) else 0}"
        
        if file_key in self._processed_files:
            return
        
        time.sleep(2)
        
        if not os.path.exists(file_path):
            return
        
        try:
            while True:
                try:
                    with open(file_path, 'rb') as f:
                        f.read(1)
                    break
                except (IOError, PermissionError):
                    time.sleep(1)
        except Exception:
            return
        
        self._processed_files.add(file_key)
        self.on_new_file(file_path, self.watch_dir)


class DirectoryWatcher:
    """目录监控器"""
    
    VIDEO_EXTENSIONS = [
        ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".rmvb", ".rm",
        ".ts", ".m2ts", ".vob", ".ogm", ".mpg", ".mpeg", ".3gp", ".3g2", ".f4v"
    ]
    
    def __init__(self):
        self._observers: Dict[str, Observer] = {}
        self._watch_dirs: Dict[str, WatchDirectory] = {}
        self._event_callback: Optional[Callable[[WatcherEvent], None]] = None
        self._process_callback: Optional[Callable[[str, WatchDirectory], None]] = None
        self._running = False
        self._event_log: List[WatcherEvent] = []
        self._lock = threading.Lock()
    
    def set_event_callback(self, callback: Callable[[WatcherEvent], None]):
        """设置事件回调"""
        self._event_callback = callback
    
    def set_process_callback(self, callback: Callable[[str, WatchDirectory], None]):
        """设置处理回调"""
        self._process_callback = callback
    
    def is_available(self) -> bool:
        """检查监控功能是否可用"""
        return HAS_WATCHDOG
    
    def add_watch_directory(self, watch_dir: WatchDirectory) -> bool:
        """添加监控目录"""
        if not HAS_WATCHDOG:
            return False
        
        path = os.path.abspath(watch_dir.path)
        
        if not os.path.isdir(path):
            return False
        
        if path in self._watch_dirs:
            return False
        
        self._watch_dirs[path] = watch_dir
        
        if self._running and watch_dir.enabled:
            self._start_observer(path, watch_dir)
        
        self._log_event("add", path, "success", f"添加监控目录: {path}")
        return True
    
    def remove_watch_directory(self, path: str) -> bool:
        """移除监控目录"""
        path = os.path.abspath(path)
        
        if path not in self._watch_dirs:
            return False
        
        if path in self._observers:
            self._stop_observer(path)
        
        del self._watch_dirs[path]
        self._log_event("remove", path, "success", f"移除监控目录: {path}")
        return True
    
    def update_watch_directory(self, watch_dir: WatchDirectory) -> bool:
        """更新监控目录配置"""
        path = os.path.abspath(watch_dir.path)
        
        if path not in self._watch_dirs:
            return self.add_watch_directory(watch_dir)
        
        self._watch_dirs[path] = watch_dir
        
        if self._running:
            if path in self._observers:
                self._stop_observer(path)
            
            if watch_dir.enabled:
                self._start_observer(path, watch_dir)
        
        self._log_event("update", path, "success", f"更新监控目录配置: {path}")
        return True
    
    def get_watch_directories(self) -> List[Dict[str, Any]]:
        """获取所有监控目录"""
        result = []
        for path, watch_dir in self._watch_dirs.items():
            result.append({
                "path": path,
                "enabled": watch_dir.enabled,
                "file_types": watch_dir.file_types,
                "output_dir": watch_dir.output_dir,
                "use_ai": watch_dir.use_ai,
                "is_watching": path in self._observers
            })
        return result
    
    def start(self):
        """启动监控"""
        if not HAS_WATCHDOG:
            self._log_event("start", "", "error", "watchdog库未安装，无法启动监控")
            return False
        
        if self._running:
            return True
        
        self._running = True
        
        for path, watch_dir in self._watch_dirs.items():
            if watch_dir.enabled:
                self._start_observer(path, watch_dir)
        
        self._log_event("start", "", "success", "目录监控已启动")
        return True
    
    def stop(self):
        """停止监控"""
        if not self._running:
            return
        
        self._running = False
        
        for path in list(self._observers.keys()):
            self._stop_observer(path)
        
        self._log_event("stop", "", "success", "目录监控已停止")
    
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running
    
    def get_event_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取事件日志"""
        with self._lock:
            events = self._event_log[-limit:]
            return [
                {
                    "event_type": e.event_type,
                    "file_path": e.file_path,
                    "timestamp": e.timestamp,
                    "status": e.status,
                    "message": e.message
                }
                for e in events
            ]
    
    def _start_observer(self, path: str, watch_dir: WatchDirectory):
        """启动单个目录的监控"""
        if path in self._observers:
            return
        
        handler = VideoFileHandler(
            watch_dir=watch_dir,
            on_new_file=self._on_new_file,
            file_types=watch_dir.file_types
        )
        
        observer = Observer()
        observer.schedule(handler, path, recursive=True)
        observer.start()
        
        self._observers[path] = observer
        self._log_event("watch", path, "success", f"开始监控目录: {path}")
    
    def _stop_observer(self, path: str):
        """停止单个目录的监控"""
        if path not in self._observers:
            return
        
        observer = self._observers[path]
        observer.stop()
        observer.join(timeout=5)
        
        del self._observers[path]
        self._log_event("unwatch", path, "success", f"停止监控目录: {path}")
    
    def _on_new_file(self, file_path: str, watch_dir: WatchDirectory):
        """处理新文件事件"""
        self._log_event("new_file", file_path, "pending", f"检测到新文件: {os.path.basename(file_path)}")
        
        if self._process_callback:
            try:
                import asyncio
                if asyncio.iscoroutinefunction(self._process_callback):
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.run_coroutine_threadsafe(
                                self._process_callback(file_path, watch_dir),
                                loop
                            )
                        else:
                            asyncio.run(self._process_callback(file_path, watch_dir))
                    except RuntimeError:
                        asyncio.run(self._process_callback(file_path, watch_dir))
                else:
                    self._process_callback(file_path, watch_dir)
            except Exception as e:
                self._log_event("error", file_path, "error", f"处理文件失败: {str(e)}")
    
    def _log_event(self, event_type: str, file_path: str, status: str, message: str):
        """记录事件日志"""
        event = WatcherEvent(
            event_type=event_type,
            file_path=file_path,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status=status,
            message=message
        )
        
        with self._lock:
            self._event_log.append(event)
            if len(self._event_log) > 500:
                self._event_log = self._event_log[-500:]
        
        if self._event_callback:
            try:
                self._event_callback(event)
            except Exception:
                pass


watcher = DirectoryWatcher()
