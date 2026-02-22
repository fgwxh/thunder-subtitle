# thunder-subtitle-cli

一个用于"迅雷字幕（Xunlei/Thunder）字幕接口"的搜索/下载工具，支持命令行子命令，也支持默认进入 TUI（交互菜单），同时支持docker部署。

> **项目来源**：本项目基于 [thunder-subtitle](https://github.com/ZeroDevi1/thunder-subtitle) 进行二次开发和功能扩展。

## 项目概述

### 近期更新

#### 功能添加
- **自定义视频文件类型**：在 Web UI 中可配置要扫描的视频文件类型，支持添加自定义视频扩展名
- **可执行文件构建**：提供包含 FastAPI Web UI 功能的可执行文件构建配置
- **Docker 部署支持**：优化 Dockerfile，支持快速容器化部署，镜像体积更小
- **启动提示优化**：启动时显示清晰的可访问地址，避免 0.0.0.0 无法访问的困惑

#### 问题修复
- **CTRL+C 退出错误**：修复了按 CTRL+C 退出时出现的 ImportError 错误
- **命令行显示问题**：修复了在某些命令行环境中显示乱码的问题
- **隐私信息清理**：清理了项目中的 API 密钥和默认 SMB 配置等敏感信息
- **Docker 构建问题**：优化 Dockerfile 构建流程，解决各种构建失败问题

### 系统兼容性

本项目当前仅在以下平台部署测试成功：
- Windows 10
- Windows 11
- 飞牛服务器
- 其他平台请自行测试

## 快速开始

### 安装与运行（uv）

仓库根目录就是本 README 所在目录。


### 运行方式

#### 0. 可执行文件（推荐，无需安装依赖）

如果您不想安装任何依赖，可直接使用本项目提供的可执行文件：

1. **下载**：从项目发布页面下载 `thunder-subtitle-fastapi.exe` 文件
2. **运行**：双击可执行文件即可启动服务
3. **访问**：打开浏览器，访问 `http://localhost:8010` 进入 Web UI

**优势**：
- 无需安装 Python 或任何依赖
- 一键启动，操作简单
- 包含所有核心功能
- 支持 Windows 32位和64位系统

#### 1. 传统Web UI 界面

##### 1.1 Streamlit Web UI（功能较少）

提供现代化的 Web 界面，支持可视化操作，包含以下功能：
- 📁 视频目录扫描（自动识别视频文件）
- 🔍 字幕搜索（关键词搜索、结果预览）
- 📦 批量下载（自动为目录中的视频下载字幕）
- 📜 下载历史（查看和管理下载记录）
- ⚙️ 配置管理（目录设置、搜索过滤、下载参数）

###### 启动方式

**方式一：使用uv（推荐）**

```bash
# 以管理员模式打开CMD终端，进入项目的根目录后，执行以下命令
uv add streamlit
uv add "streamlit<1.30"
uv run streamlit run src/thunder_subtitle_cli/web_ui.py
```

**方式二：使用虚拟环境（避免环境冲突）**

```bash
# 以管理员模式打开CMD终端，进入项目的根目录后，执行以下命令

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境并安装依赖
# Windows
venv\Scripts\activate && pip install streamlit fastapi uvicorn jinja2 python-multipart httpx typer rich questionary pysmb openai watchdog
# Linux/macOS
source venv/bin/activate && pip install streamlit fastapi uvicorn jinja2 python-multipart httpx typer rich questionary pysmb openai watchdog

# 运行Web UI
streamlit run src/thunder_subtitle_cli/web_ui.py
```

**访问地址**：http://localhost:8501

##### 1.2 FastAPI Web UI（推荐，功能全面、支持AI评估字幕、支持Docker部署使用）

提供更轻量、更快速的Web界面，支持所有核心功能：

###### 与Streamlit Web UI的区别和优势

| 特性 | FastAPI Web UI | Streamlit Web UI |
|------|---------------|------------------|
| **性能** | ⚡ 更轻量、启动更快 | 相对较重、启动较慢 |
| **资源占用** | 📦 内存占用低 | 内存占用较高 |
| **部署友好** | 🐳 适合Docker容器化部署 | 容器化部署相对复杂 |
| **响应速度** | 🚀 API响应更快 | 页面渲染较慢 |
| **定制性** | 🎨 高度可定制 | 定制性相对有限 |
| **适合场景** | 生产环境、服务器部署 | 开发测试、快速原型 |

###### 为什么选择FastAPI Web UI：
- **更适合服务器环境**：资源占用低，运行稳定
- **Docker部署最佳选择**：镜像体积小，启动迅速
- **API性能优势**：基于FastAPI框架，API响应速度快
- **更轻量的前端**：使用原生HTML/CSS/JavaScript，加载更快
- **同等功能**：支持所有核心功能，包括字幕搜索、批量下载、AI评估等

###### 启动方式

**方式一：使用uv（推荐）**

```bash
# 以管理员模式打开CMD终端，进入项目的根目录后，执行以下命令

uv sync
uv run python run_fastapi_ui.py
```

**方式二：使用虚拟环境（避免环境冲突）**

```bash
# 以管理员模式打开CMD终端，进入项目的根目录后，执行以下命令

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境并安装依赖
# Windows
venv\Scripts\activate && pip install fastapi uvicorn jinja2 python-multipart httpx typer rich questionary pysmb openai watchdog
# Linux/macOS
source venv/bin/activate && pip install fastapi uvicorn jinja2 python-multipart httpx typer rich questionary pysmb openai watchdog

# 运行FastAPI Web UI

# 方式1：激活虚拟环境后运行
python run_fastapi_ui.py

# 方式2：直接使用虚拟环境Python（推荐，避免激活问题）
.\venv\Scripts\python.exe run_fastapi_ui.py
```

**方式三：桌面端Docker 容器部署  **

```bash
# 构建镜像
docker build -t thunder-subtitle .

# 运行容器
docker run -p 8010:8010 --rm fgwxh123/thunder-subtitle:latest

```

构建完成后访问：
- 本机访问：http://localhost:8010
- 服务器部署：http://你的服务器IP:8010

详细使用说明请参考 [WEB_UI_README.md](file:///d:/my%20workers/thunder-subtitle-main/WEB_UI_README.md)

#### 2. 命令行模式

##### 2.1 TUI 交互模式

在交互式终端（TTY）里，无参数运行会进入菜单（搜索 / 下载 / 批量下载 / 退出）：

```bash
uv run thunder-subtitle
```

也可以显式进入：

```bash
uv run thunder-subtitle tui
```

TUI 模式下默认下载目录是 `./subs`（会在流程中提示可输入覆盖）。

##### 2.2 命令行子命令（脚本化/自动化用）

```bash
# 搜索
uv run thunder-subtitle search "Movie.Name.2023"

# 下载（默认取评分最高的一个）
uv run thunder-subtitle download "Movie.Name.2023" --out-dir ./subs

# 批量交互多选下载（每个 query 单独选择）
uv run thunder-subtitle batch "Movie1" "Movie2" --out-dir ./subs
```

## 核心功能

### 1. 字幕搜索与下载
- 支持关键词搜索
- 支持结果预览
- 支持批量下载
- 支持自动为视频文件匹配字幕

### 2. 视频目录扫描
- 自动识别视频文件
- 支持递归扫描子目录
- 支持多种视频格式
- **自定义视频文件类型**：可在 Web UI 中配置要扫描的视频文件类型，支持添加自定义视频扩展名

### 3. AI 字幕评估
- 基于规则的评估
- 基于AI的智能评估
- 支持多种评估维度

### 4. SMB 网络存储支持
- 连接NAS或其他SMB服务器
- 批量扫描网络视频文件
- 远程下载字幕到网络存储

### 5. 下载历史管理
- 查看历史下载记录
- 管理已下载字幕
- 支持导出历史记录

## 部署指南

### 1. Docker部署

本项目已发布到Docker Hub，您可以直接使用Docker镜像进行部署。

#### Docker Hub仓库地址

[https://hub.docker.com/r/fgwxh123/thunder-subtitle](https://hub.docker.com/r/fgwxh123/thunder-subtitle)

#### 部署示例

使用docker-compose部署：

```yaml
services:
  thunder-subtitle:
    image: fgwxh123/thunder-subtitle
    ports:
      - "8010:8010"
    environment:
      - HOST=0.0.0.0
      - PORT=8010
    volumes:
      - ./subtitles:/app/subtitles
    restart: unless-stopped
```

#### 访问方式

部署完成后，通过以下地址访问Web UI：

http://localhost:8010

### 2. 构建可执行文件（二进制）

可以使用 PyInstaller 构建当前平台的单文件可执行程序（注意：**无法在一台机器上交叉编译出三端可执行文件**，Linux/Windows/macOS 需要分别在对应系统上构建；本仓库也提供了 GitHub Actions 自动构建）。

#### 2.1 本地构建（当前系统）

```bash
# 安装包含构建工具的依赖（pyinstaller 在 dev 组）
uv sync --group dev

# 生成 dist/thunder-subtitle（Windows 下为 dist/thunder-subtitle.exe）
uv run python scripts/build_exe.py
```

输出目录：`dist/`

#### 2.2 构建包含 FastAPI Web UI 的可执行文件

本项目还提供了包含 FastAPI Web UI 功能的可执行文件构建配置：

```bash
# 构建包含 FastAPI Web UI 的可执行文件
uv run python -m PyInstaller --noconfirm --clean packaging/thunder-subtitle-fastapi.spec
```

输出目录：`dist/`

生成的可执行文件：`thunder-subtitle-fastapi.exe`（Windows）

### 2.3 可执行文件使用说明

1. **无需安装依赖**：可执行文件已包含所有必要的依赖，直接运行即可
2. **启动方式**：双击可执行文件或在命令行中运行
3. **访问地址**：http://localhost:8010
4. **功能完整**：包含所有 Web UI 功能，包括视频扫描、字幕搜索、批量下载、AI 评估等
5. **跨平台兼容**：Windows 32位和64位系统均可运行

### 2.4 常见问题

**Q: 运行可执行文件时命令行显示乱码或不正常**

A: 已修复，可执行文件现在使用纯文本输出，在任何命令行环境中都能正常显示。

**Q: 按 CTRL+C 退出时出现错误**

A: 已修复，现在按 CTRL+C 退出时会优雅退出，无错误信息。

**Q: 可执行文件是否包含所有功能**

A: 是的，可执行文件包含所有核心功能，包括：
- 本地视频检索和扫描
- 字幕搜索和下载
- AI 字幕评估
- SMB 网络存储支持
- 自定义视频文件类型

**Q: 其他用户下载使用可执行文件时，是否需要安装其他依赖环境**

A: 不需要，可执行文件已完全独立，包含所有必要的依赖，直接运行即可使用所有功能。

#### 2.5 GitHub Actions 三端构建（推荐）

工作流：`.github/workflows/build-binaries.yml`

- 手动触发：在 GitHub Actions 页面点击 "Run workflow"
- 自动发布：推送 tag（例如 `v0.1.0`）会自动在 Linux/Windows/macOS 三端构建并把产物上传到 Release

## 配置说明

### SMB 配置

Web UI 的 SMB 功能支持连接 NAS 或其他 SMB 服务器，批量扫描视频文件并下载字幕。

#### 基本概念

| 参数 | 说明 |
|------|------|
| **服务器地址** | SMB 服务器的 IP 地址或主机名 |
| **端口** | SMB 端口，默认 445 |
| **共享名称** | SMB 共享文件夹的名称 |
| **用户名/密码** | SMB 访问凭据 |
| **扫描路径** | 共享文件夹内的相对路径（不含共享名称） |

#### 配置示例

##### 群晖 NAS 配置

假设群晖 NAS 的 SMB 配置如下：
- IP 地址：`192.168.1.x`
- 共享文件夹：`video`（对应 `/volume1/video`）
- 要扫描的目录：`/volume1/video/movies/动作片`

**Web UI 填写方式**：
```
服务器地址：192.168.1.x
端口：445
共享名称：video
扫描路径：movies/动作片
```

**说明**：
- 共享名称 `video` 已对应到 `/volume1/video`
- 扫描路径只需填写 `movies/动作片`（不需要 `/volume1/video/` 前缀）

##### 飞牛 NAS 配置

假设飞牛 NAS 的 SMB 配置如下：
- IP 地址：`192.168.x.x`
- 共享文件夹：`media`（对应 `/vol1/1000/media`）
- 要扫描的目录：`/vol1/1000/media/movies/hd`

**Web UI 填写方式**：
```
服务器地址：192.168.x.x
端口：445
共享名称：media
扫描路径：movies/hd
```

**说明**：
- 共享名称 `media` 已对应到 `/vol1/1000/media`
- 扫描路径只需填写 `movies/hd`（不需要 `media/` 前缀）

#### 通用配置规则

1. **确定共享名称对应的实际路径**
   - 在 SMB 服务器上查看共享文件夹设置
   - 例如：共享名 `share` 对应 `/data/share`

2. **计算相对路径**
   - 要访问的实际路径：`/data/share/movies/2024`
   - 扫描路径填写：`movies/2024`

3. **路径分隔符**
   - 使用正斜杠 `/` 或反斜杠 `\` 均可
   - 程序会自动处理

#### 常见问题

**Q: 扫描时提示 "Unable to open directory"**

A: 检查以下几点：
1. 扫描路径是否包含共享名称（应该去掉）
2. 用户是否有该目录的读取权限
3. 路径是否存在

**Q: 如何确定共享名称？**

A: 
- Windows：在文件资源管理器地址栏输入 `\\服务器IP`，显示的文件夹名即共享名
- 群晖：控制面板 → 文件服务 → SMB → 共享文件夹
- 飞牛：存储管理 → 共享文件夹

**Q: 如何测试连接？**

A: 点击 Web UI 中的"测试连接"按钮，成功后会显示连接正常。

### SMB 辅助脚本：生成哆啦A梦集数文件列表

脚本会连接 SMB 共享目录，列出当前目录中匹配 `第XXXX话 *.mp4` 的文件名，并将结果写到本地文本文件。

脚本：
- `scripts/smb_list_doraemon.py`

环境变量（不要把密码写进仓库；可参考 `.env.example`）：
- `SMB_HOST`（默认：空字符串，必填）
- `SMB_SHARE`（默认：空字符串，必填）
- `SMB_DIR`（默认：空字符串，必填）
- `SMB_USER`（默认：空字符串，必填）
- `SMB_PASS`（必填）
- `OUTPUT_PATH`（默认：`out/episode_list.txt`）

运行示例：
```bash
uv sync
SMB_PASS='***' uv run python scripts/smb_list_doraemon.py
```

## 版本发布

推送 tag（例如 `v0.1.0`）后，GitHub Actions 会自动在 Linux/Windows/macOS 三端构建可执行文件并发布到 Release：

```bash
git tag v0.1.0
git push origin v0.1.0
```

## 法律声明

### 使用目的
本项目仅用于个人学习和研究目的，旨在提供字幕搜索和下载的技术实现参考。

### 版权声明
本项目基于 [thunder-subtitle](https://github.com/ZeroDevi1/thunder-subtitle) 进行二次开发和功能扩展，遵循原项目的开源协议。

项目中使用的第三方库和资源均遵循各自的许可证协议。

### 免责声明
1. **字幕内容责任**：本项目本身不存储、提供或分发任何字幕内容，所有字幕均来自第三方服务。用户应确保在使用字幕时遵守相关法律法规，尊重版权所有者的权益。

2. **使用风险**：用户应自行承担使用本项目的风险，项目作者不对因使用本项目而产生的任何直接或间接损失负责。

3. **合规性**：用户在使用本项目时，应遵守所在国家或地区的法律法规，不得用于任何违法用途。

### 合规性提示
- 本项目仅提供技术实现，不鼓励或支持任何侵犯版权的行为
- 请在下载和使用字幕时，确保符合相关法律法规和版权要求
- 建议仅为个人合法拥有的视频内容下载和使用字幕

### 责任限制
在法律允许的最大范围内，项目作者不对本项目的任何使用或误用承担责任。用户应自行判断并承担使用本项目的全部风险和责任。
