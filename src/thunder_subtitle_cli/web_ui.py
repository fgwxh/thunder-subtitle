import sys
import os
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
if str(project_root / "src") not in sys.path:
    sys.path.insert(0, str(project_root / "src"))

import asyncio
import json
from datetime import datetime
from typing import Optional

import streamlit as st
from streamlit.runtime.scriptrunner import RerunData, RerunException

from thunder_subtitle_cli.client import ThunderClient, download_with_retries
from thunder_subtitle_cli.core import apply_filters, format_item_label
from thunder_subtitle_cli.models import ThunderSubtitleItem
from thunder_subtitle_cli.util import sanitize_component, ensure_unique_path


st.set_page_config(
    page_title="迅雷字幕搜索下载工具",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)


def init_session_state():
    if "search_history" not in st.session_state:
        st.session_state.search_history = []
    if "download_history" not in st.session_state:
        st.session_state.download_history = []
    if "selected_videos" not in st.session_state:
        st.session_state.selected_videos = []
    if "search_results" not in st.session_state:
        st.session_state.search_results = {}
    if "config" not in st.session_state:
        st.session_state.config = {
            "video_dir": "",
            "save_dir": "",
            "min_score": 0.0,
            "language": "",
            "timeout": 60.0,
            "retries": 2,
            "concurrency": 3
        }
    if "preview_state" not in st.session_state:
        st.session_state.preview_state = {
            "active_preview": None,  # 当前活跃的预览ID
            "preview_content": {}
        }


def load_config():
    config_file = Path("ui_config.json")
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                st.session_state.config.update(json.load(f))
        except Exception as e:
            st.warning(f"配置加载失败: {e}")


def save_config():
    config_file = Path("ui_config.json")
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(st.session_state.config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"配置保存失败: {e}")


def get_video_files(directory: str) -> list[Path]:
    video_extensions = {"*.mp4", "*.mkv", "*.avi", "*.mov", "*.wmv", "*.flv", "*.webm", "*.m4v"}
    video_dir = Path(directory)
    
    if not video_dir.exists() or not video_dir.is_dir():
        return []
    
    video_files = []
    for pattern in video_extensions:
        # 递归搜索当前目录及其所有子目录
        video_files.extend(video_dir.rglob(pattern))
        # 搜索大写扩展名
        video_files.extend(video_dir.rglob(pattern.upper()))
    
    return sorted(set(video_files))


def search_subtitles(query: str) -> list[ThunderSubtitleItem]:
    async def _search():
        client = ThunderClient()
        items = await client.search(query=query, timeout_s=20.0)
        items = sorted(items, key=lambda x: x.score, reverse=True)
        items = apply_filters(
            items,
            min_score=st.session_state.config.get("min_score") or None,
            lang=st.session_state.config.get("language") or None
        )
        return items[:50]
    
    return asyncio.run(_search())


def download_subtitle(item: ThunderSubtitleItem, save_dir: Path) -> Optional[Path]:
    async def _download():
        client = ThunderClient()
        
        # 下载字幕数据
        data = await download_with_retries(
            client,
            url=item.url,
            timeout_s=st.session_state.config.get("timeout", 60.0),
            retries=st.session_state.config.get("retries", 2)
        )
        
        # 生成简单文件名，避免编码问题
        import re
        import time
        
        # 使用时间戳和随机数生成唯一文件名
        timestamp = int(time.time() * 1000)
        ext = item.ext or "srt"
        short_name = f"subtitle_{timestamp}.{ext}"
        
        # 尝试保存到多个位置
        save_attempts = [
            (save_dir, "设置目录"),
            (Path.home() / "Downloads", "下载目录"),
            (Path.home() / "Desktop", "桌面目录"),
            (Path("D:\\subtitles"), "D盘根目录"),
            (Path("C:\\subtitles"), "C盘根目录"),
        ]
        
        # 保存失败的目录列表
        failed_dirs = []
        
        for target_dir, dir_name in save_attempts:
            try:
                # 确保目录存在
                target_dir.mkdir(parents=True, exist_ok=True)
                
                # 生成唯一路径
                path = ensure_unique_path(target_dir / short_name)
                
                # 检查路径长度
                if len(str(path)) > 250:
                    raise Exception(f"路径过长: {path}")
                
                # 直接尝试写入文件
                try:
                    with open(path, 'wb') as f:
                        f.write(data)
                    
                    # 保存成功
                    st.success(f"✅ 保存到 {dir_name}: {path}")
                    return path
                except PermissionError as e:
                    failed_dirs.append(f"{dir_name}: {e}")
                    
                    # 尝试使用临时文件然后移动
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                        tmp.write(data)
                        temp_path = Path(tmp.name)
                    
                    # 尝试移动文件
                    try:
                        import shutil
                        shutil.move(str(temp_path), str(path))
                        st.success(f"✅ 通过临时文件移动保存到 {dir_name}: {path}")
                        return path
                    except Exception as e:
                        failed_dirs.append(f"{dir_name} (移动): {e}")
                        temp_path.unlink(missing_ok=True)
                        continue
            except Exception as e:
                failed_dirs.append(f"{dir_name}: {e}")
                continue
        
        # 尝试临时文件
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                tmp.write(data)
                temp_path = Path(tmp.name)
                
                # 保存到临时目录成功
                st.info(f"✅ 保存到临时目录: {temp_path}")
                
                # 显示详细的权限诊断
                st.warning("\n" + "="*80 + "\n")
                st.warning("🔴  严重权限问题诊断")
                st.warning("\n" + "="*80 + "\n")
                st.warning("📋  失败的保存位置:")
                for fail in failed_dirs:
                    st.warning(f"- {fail}")
                st.warning("\n" + "="*80 + "\n")
                st.warning("�  可能的根本原因:")
                st.warning("1. **用户权限不足**: 当前用户可能不是管理员")
                st.warning("2. **防病毒软件阻止**: 防病毒软件可能设置为高防护模式")
                st.warning("3. **安全软件限制**: 其他安全软件可能限制文件系统访问")
                st.warning("4. **系统策略限制**: Windows组策略可能限制文件写入")
                st.warning("5. **磁盘权限问题**: 磁盘可能被设置为只读")
                st.warning("6. **网络驱动器问题**: 如果是网络驱动器，可能有额外限制")
                st.warning("\n" + "="*80 + "\n")
                st.warning("🛠️  紧急解决方案:")
                st.warning("\n" + "="*80 + "\n")
                st.warning("1. **使用管理员权限运行命令提示符**:")
                st.warning("   - 步骤1: 按 Win+R 打开运行窗口")
                st.warning("   - 步骤2: 输入 'cmd' 并按 Ctrl+Shift+Enter")
                st.warning("   - 步骤3: 在管理员命令提示符中运行:")
                st.warning("   - cd D:\\my workers\\thunder-subtitle-main")
                st.warning("   - python -m streamlit run src\\thunder_subtitle_cli\\web_ui.py --server.port 8502")
                st.warning("\n2. **检查防病毒软件设置**:")
                st.warning("   - 临时禁用防病毒软件")
                st.warning("   - 检查文件防护设置，添加本程序为信任")
                st.warning("\n3. **检查磁盘权限**:")
                st.warning("   - 右键点击磁盘 → 属性 → 安全")
                st.warning("   - 确保当前用户有写入权限")
                st.warning("\n4. **尝试不同的用户账户**:")
                st.warning("   - 登录到管理员账户")
                st.warning("   - 或创建一个新的用户账户")
                st.warning("\n" + "="*80 + "\n")
                st.warning("📌  临时解决方案:")
                st.warning(f"- 文件已保存到临时目录: {temp_path}")
                st.warning("- 请手动复制此文件到你需要的位置")
                st.warning("- 或使用文件资源管理器将文件移动到目标目录")
                st.warning("- 临时目录中的文件不会被自动删除")
                st.warning("\n" + "="*80 + "\n")
                st.warning("💡  技术提示:")
                st.warning("- 这是系统级权限问题，不是程序代码问题")
                st.warning("- 所有保存方法都已尝试，包括直接写入和临时文件移动")
                st.warning("- 临时目录是唯一可行的解决方案")
                st.warning("="*80)
                
                return temp_path
        except Exception as e:
            raise Exception(f"所有保存位置都失败: {e}")
    
    return asyncio.run(_download())


def preview_subtitle(item: ThunderSubtitleItem) -> Optional[str]:
    preview_id = f"{item.gcid}:{item.cid}"
    
    # 检查是否已经有该字幕的预览内容
    if preview_id in st.session_state.preview_state["preview_content"]:
        return st.session_state.preview_state["preview_content"][preview_id]
    
    async def _preview():
        client = ThunderClient()
        try:
            data = await client.download_bytes(url=item.url, timeout_s=10.0)
            content = data.decode('utf-8', errors='replace')
            total_length = len(content)
            
            # 增加预览字符数到5000，同时添加完整性指示
            if len(content) > 5000:
                preview_content = content[:5000] + f"\n\n...（预览已截断，完整字幕长度：{total_length} 字符）"
            else:
                preview_content = content + f"\n\n...（预览完整，字幕长度：{total_length} 字符）"
            
            # 保存预览内容到会话状态
            st.session_state.preview_state["preview_content"][preview_id] = preview_content
            return preview_content
        except Exception as e:
            error_msg = f"预览失败: {e}"
            st.session_state.preview_state["preview_content"][preview_id] = error_msg
            return error_msg
    
    return asyncio.run(_preview())


def render_sidebar():
    st.sidebar.title("⚙️ 设置")
    
    with st.sidebar.expander("目录设置", expanded=True):
        video_dir = st.text_input(
            "视频目录",
            value=st.session_state.config.get("video_dir", ""),
            help="包含视频文件的目录路径"
        )
        st.session_state.config["video_dir"] = video_dir
        
        save_dir = st.text_input(
            "字幕保存目录",
            value=st.session_state.config.get("save_dir", ""),
            help="字幕文件保存的目录路径"
        )
        st.session_state.config["save_dir"] = save_dir
    
    with st.sidebar.expander("搜索设置"):
        min_score = st.slider(
            "最低评分",
            min_value=0.0,
            max_value=10.0,
            value=st.session_state.config.get("min_score", 0.0),
            step=0.1
        )
        st.session_state.config["min_score"] = min_score
        
        language = st.text_input(
            "语言过滤",
            value=st.session_state.config.get("language", ""),
            help="留空表示不限制语言"
        )
        st.session_state.config["language"] = language
    
    with st.sidebar.expander("下载设置"):
        timeout = st.number_input(
            "下载超时（秒）",
            min_value=10,
            max_value=300,
            value=int(st.session_state.config.get("timeout", 60.0))
        )
        st.session_state.config["timeout"] = float(timeout)
        
        retries = st.number_input(
            "重试次数",
            min_value=0,
            max_value=10,
            value=st.session_state.config.get("retries", 2)
        )
        st.session_state.config["retries"] = retries
        
        concurrency = st.number_input(
            "并发数",
            min_value=1,
            max_value=20,
            value=st.session_state.config.get("concurrency", 3)
        )
        st.session_state.config["concurrency"] = concurrency
    
    if st.sidebar.button("💾 保存配置"):
        save_config()
        st.sidebar.success("配置已保存！")


def render_video_scanner():
    st.header("📁 视频目录扫描")
    
    video_dir = st.session_state.config.get("video_dir", "")
    
    if not video_dir:
        st.warning("请在侧边栏设置视频目录")
        return
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.info(f"扫描目录: {video_dir}")
    
    with col2:
        if st.button("🔄 扫描视频"):
            video_files = get_video_files(video_dir)
            st.session_state.selected_videos = video_files
            st.rerun()
    
    if st.session_state.selected_videos:
        st.subheader(f"找到 {len(st.session_state.selected_videos)} 个视频文件")
        
        # 使用简单的方式显示视频文件列表，避免 pandas/numpy 错误
        for idx, video_path in enumerate(st.session_state.selected_videos, 1):
            with st.expander(f"{idx}. {video_path.name}", expanded=False):
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"**路径:** {str(video_path)}")
                with col2:
                    size = f"{video_path.stat().st_size / 1024 / 1024:.2f} MB"
                    st.write(f"**大小:** {size}")
        
        st.success(f"✅ 扫描完成！找到 {len(st.session_state.selected_videos)} 个视频文件")


def render_subtitle_search():
    st.header("🔍 字幕搜索")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        query = st.text_input(
            "搜索关键词",
            placeholder="输入电影名称或关键词...",
            key="search_query"
        )
    
    with col2:
        search_button = st.button("🔎 搜索", type="primary")
    
    if search_button and query:
        with st.spinner("正在搜索字幕..."):
            results = search_subtitles(query)
            
            if results:
                st.session_state.search_results[query] = results
                st.success(f"找到 {len(results)} 个字幕")
            else:
                st.warning("未找到匹配的字幕")
    
    if st.session_state.search_results:
        st.subheader("搜索结果")
        
        # 添加临时保存目录选择
        st.markdown("**💾 保存设置**")
        col1, col2 = st.columns([2, 1])
        
        with col1:
            temp_save_dir = st.text_input(
                "临时保存目录",
                value=str(Path.home() / "Desktop"),
                help="选择一个你确定有写入权限的目录"
            )
        
        with col2:
            if st.button("📁 验证目录权限"):
                test_dir = Path(temp_save_dir)
                try:
                    test_dir.mkdir(parents=True, exist_ok=True)
                    if os.access(str(test_dir), os.W_OK):
                        st.success(f"✅ 目录可写: {test_dir}")
                    else:
                        st.error(f"❌ 目录不可写: {test_dir}")
                except Exception as e:
                    st.error(f"❌ 目录错误: {e}")
        
        st.markdown("---")
        
        for query, results in st.session_state.search_results.items():
            st.markdown(f"**搜索词: `{query}`** ({len(results)} 个结果)")
            
            # 添加表头
            header_col1, header_col2, header_col3, header_col4 = st.columns([4, 1, 1, 1])
            with header_col1:
                st.markdown("**文件名**")
            with header_col2:
                st.markdown("**类型**")
            with header_col3:
                st.markdown("**操作**")
            with header_col4:
                pass  # 占位
            
            # 显示字幕列表，每行一个
            for idx, item in enumerate(results):
                col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
                preview_id = f"{item.gcid}:{item.cid}"
                is_preview_active = st.session_state.preview_state["active_preview"] == preview_id
                
                with col1:
                    st.write(item.name)
                with col2:
                    st.write(item.ext or "srt")
                with col3:
                    if is_preview_active:
                        # 显示关闭预览按钮
                        if st.button("关闭预览", key=f"close_preview_{preview_id}", use_container_width=True):
                            st.session_state.preview_state["active_preview"] = None
                            st.rerun()
                    else:
                        # 显示预览按钮
                        if st.button("预览", key=f"preview_{preview_id}", use_container_width=True):
                            st.session_state.preview_state["active_preview"] = preview_id
                            st.rerun()
                with col4:
                    if st.button("下载", key=f"download_{preview_id}", use_container_width=True):
                        # 使用用户选择的临时保存目录
                        save_dir = Path(temp_save_dir)
                        
                        with st.spinner("正在下载..."):
                            try:
                                saved_path = download_subtitle(item, save_dir)
                                if saved_path:
                                    st.success(f"下载成功: {saved_path}")
                                    st.session_state.download_history.append({
                                        "name": item.name,
                                        "path": str(saved_path),
                                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    })
                                else:
                                    st.error("下载失败")
                            except Exception as e:
                                st.error(f"下载失败: {e}")
                
                # 显示预览内容
                if is_preview_active:
                    with st.expander("字幕预览", expanded=True):
                        with st.spinner("正在加载预览..."):
                            preview_content = preview_subtitle(item)
                            if preview_content:
                                # 使用大尺寸的代码块显示预览
                                st.code(preview_content, language="text", line_numbers=True)
                            else:
                                st.warning("无法预览此字幕")
            
            # 添加分隔线
            st.markdown("---")


def render_batch_download():
    st.header("📦 批量下载")
    
    video_dir = st.session_state.config.get("video_dir", "")
    
    # 添加临时保存目录选择
    st.markdown("**💾 保存设置**")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        temp_save_dir = st.text_input(
            "临时保存目录",
            value=str(Path.home() / "Desktop"),
            help="选择一个你确定有写入权限的目录"
        )
    
    with col2:
        if st.button("📁 验证目录权限"):
            test_dir = Path(temp_save_dir)
            try:
                test_dir.mkdir(parents=True, exist_ok=True)
                if os.access(str(test_dir), os.W_OK):
                    st.success(f"✅ 目录可写: {test_dir}")
                else:
                    st.error(f"❌ 目录不可写: {test_dir}")
            except Exception as e:
                st.error(f"❌ 目录错误: {e}")
    
    st.markdown("---")
    
    if not video_dir:
        st.warning("请在侧边栏设置视频目录")
        return
    
    if not st.session_state.selected_videos:
        st.info("请先在「视频目录扫描」页面扫描视频文件")
        return
    
    st.subheader(f"批量搜索 {len(st.session_state.selected_videos)} 个视频的字幕")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.info(f"视频目录: {video_dir}")
        st.info(f"字幕保存目录: {temp_save_dir}")
    
    with col2:
        if st.button("🚀 开始批量搜索"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            save_path = Path(temp_save_dir)
            save_path.mkdir(parents=True, exist_ok=True)
            
            total = len(st.session_state.selected_videos)
            success_count = 0
            fail_count = 0
            
            for idx, video_path in enumerate(st.session_state.selected_videos):
                video_name = video_path.stem
                status_text.text(f"正在搜索: {video_name} ({idx + 1}/{total})")
                
                try:
                    results = search_subtitles(video_name)
                    
                    if results:
                        best_subtitle = results[0]
                        saved_path = download_subtitle(best_subtitle, save_path)
                        
                        if saved_path:
                            success_count += 1
                            st.success(f"✅ {video_name} -> {saved_path.name}")
                            st.session_state.download_history.append({
                                "name": best_subtitle.name,
                                "path": str(saved_path),
                                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            })
                        else:
                            fail_count += 1
                            st.warning(f"⚠️ {video_name} 下载失败")
                    else:
                        fail_count += 1
                        st.warning(f"⚠️ {video_name} 未找到字幕")
                
                except Exception as e:
                    fail_count += 1
                    st.error(f"❌ {video_name} 错误: {e}")
                
                progress_bar.progress((idx + 1) / total)
            
            status_text.text(f"完成！成功: {success_count}, 失败: {fail_count}")
            st.balloons()


def render_download_history():
    st.header("📜 下载历史")
    
    if not st.session_state.download_history:
        st.info("暂无下载记录")
        return
    
    st.subheader(f"共 {len(st.session_state.download_history)} 条记录")
    
    # 使用展开面板显示下载历史，避免 dataframe 错误
    for idx, record in enumerate(reversed(st.session_state.download_history), 1):
        with st.expander(f"{idx}. {record['name']}", expanded=False):
            col1, col2 = st.columns([2, 1])
            with col1:
                st.write(f"**保存路径:**")
                st.code(record['path'], language="text")  # 使用代码块显示完整路径
            with col2:
                st.write(f"**下载时间:** {record['time']}")
                # 显示文件名和目录分离
                path_obj = Path(record['path'])
                st.write(f"**文件名:** {path_obj.name}")
                st.write(f"**目录:** {path_obj.parent}")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("🗑️ 清空历史"):
            st.session_state.download_history = []
            st.rerun()
    
    with col2:
        if st.button("📥 导出历史"):
            history_json = json.dumps(st.session_state.download_history, ensure_ascii=False, indent=2)
            st.download_button(
                label="下载历史记录",
                data=history_json,
                file_name=f"download_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )


def main():
    init_session_state()
    load_config()
    render_sidebar()
    
    page = st.sidebar.radio(
        "📋 功能导航",
        ["视频目录扫描", "字幕搜索", "批量下载", "下载历史"],
        label_visibility="collapsed"
    )
    
    st.title("🎬 迅雷字幕搜索下载工具")
    st.markdown("---")
    
    if page == "视频目录扫描":
        render_video_scanner()
    elif page == "字幕搜索":
        render_subtitle_search()
    elif page == "批量下载":
        render_batch_download()
    elif page == "下载历史":
        render_download_history()


if __name__ == "__main__":
    main()
