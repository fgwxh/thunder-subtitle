# thunder-subtitle-cli

一个用于"迅雷字幕（Xunlei/Thunder）字幕接口"的搜索/下载工具，支持命令行子命令，也支持默认进入 TUI（交互菜单）。

> **项目来源**：本项目基于 [thunder-subtitle](https://github.com/ZeroDevi1/thunder-subtitle) 进行二次开发和功能扩展。

## 系统兼容性

本项目当前仅在以下平台部署测试成功：
- Windows 10
- Windows 11
- 飞牛服务器
- 其他平台请自行测试

## 安装与运行（uv）

仓库根目录就是本 README 所在目录。

在仓库根目录运行：

```bash
uv sync
```

## 构建可执行文件（二进制）

可以使用 PyInstaller 构建当前平台的单文件可执行程序（注意：**无法在一台机器上交叉编译出三端可执行文件**，Linux/Windows/macOS 需要分别在对应系统上构建；本仓库也提供了 GitHub Actions 自动构建）。

### 1) 本地构建（当前系统）

```bash
# 安装包含构建工具的依赖（pyinstaller 在 dev 组）
uv sync --group dev

# 生成 dist/thunder-subtitle（Windows 下为 dist/thunder-subtitle.exe）
uv run python scripts/build_exe.py
```

输出目录：`dist/`

### 2) GitHub Actions 三端构建（推荐）

工作流：`.github/workflows/build-binaries.yml`

- 手动触发：在 GitHub Actions 页面点击 “Run workflow”
- 自动发布：推送 tag（例如 `v0.1.0`）会自动在 Linux/Windows/macOS 三端构建并把产物上传到 Release

### 运行方式

### 方式一：Web UI 界面（推荐）

提供现代化的 Web 界面，支持可视化操作，包含以下功能：
- 📁 视频目录扫描（自动识别视频文件）
- 🔍 字幕搜索（关键词搜索、结果预览）
- 📦 批量下载（自动为目录中的视频下载字幕）
- 📜 下载历史（查看和管理下载记录）
- ⚙️ 配置管理（目录设置、搜索过滤、下载参数）

启动 Web UI：

```bash
uv sync
uv run python scripts/run_web_ui.py
```

或者直接使用 streamlit：

```bash
uv run streamlit run src/thunder_subtitle_cli/web_ui.py
```

浏览器访问：http://localhost:8501

### FastAPI Web UI（推荐，Docker部署使用）

提供更轻量、更快速的Web界面，支持所有核心功能：

启动命令：

```bash
uv sync
uv run python run_fastapi_ui.py
```

浏览器访问：http://localhost:8010

详细使用说明请参考 [WEB_UI_README.md](file:///d:/my%20workers/thunder-subtitle-main/WEB_UI_README.md)

### 方式二：命令行 TUI 模式

在交互式终端（TTY）里，无参数运行会进入菜单（搜索 / 下载 / 批量下载 / 退出）：

```bash
uv run thunder-subtitle
```

也可以显式进入：

```bash
uv run thunder-subtitle tui
```

TUI 模式下默认下载目录是 `./subs`（会在流程中提示可输入覆盖）。

### 方式三：命令行子命令（脚本化/自动化用）

```bash
# 搜索
uv run thunder-subtitle search "Movie.Name.2023"

# 下载（默认取评分最高的一个）
uv run thunder-subtitle download "Movie.Name.2023" --out-dir ./subs

# 批量交互多选下载（每个 query 单独选择）
uv run thunder-subtitle batch "Movie1" "Movie2" --out-dir ./subs
```

## SMB 辅助脚本：生成哆啦A梦集数文件列表

脚本会连接 SMB 共享目录，列出当前目录中匹配 `第XXXX话 *.mp4` 的文件名，并将结果写到本地文本文件。

脚本：
- `scripts/smb_list_doraemon.py`

环境变量（不要把密码写进仓库；可参考 `.env.example`）：
- `SMB_HOST`（默认：`192.168.0.21`）
- `SMB_SHARE`（默认：`Video`）
- `SMB_DIR`（默认：`动漫/哆啦A梦`）
- `SMB_USER`（默认：`ZeroDevi1`）
- `SMB_PASS`（必填）
- `OUTPUT_PATH`（默认：`out/episode_list.txt`）

运行示例：
```bash
uv sync
SMB_PASS='***' uv run python scripts/smb_list_doraemon.py
```

## 版本发布（可选）

推送 tag（例如 `v0.1.0`）后，GitHub Actions 会自动在 Linux/Windows/macOS 三端构建可执行文件并发布到 Release：

```bash
git tag v0.1.0
git push origin v0.1.0
```

## SMB 配置说明

Web UI 的 SMB 功能支持连接 NAS 或其他 SMB 服务器，批量扫描视频文件并下载字幕。

### 基本概念

| 参数 | 说明 |
|------|------|
| **服务器地址** | SMB 服务器的 IP 地址或主机名 |
| **端口** | SMB 端口，默认 445 |
| **共享名称** | SMB 共享文件夹的名称 |
| **用户名/密码** | SMB 访问凭据 |
| **扫描路径** | 共享文件夹内的相对路径（不含共享名称） |

### 群晖 NAS 配置示例

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

### 飞牛 NAS 配置示例

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

### 其他服务器通用规则

1. **确定共享名称对应的实际路径**
   - 在 SMB 服务器上查看共享文件夹设置
   - 例如：共享名 `share` 对应 `/data/share`

2. **计算相对路径**
   - 要访问的实际路径：`/data/share/movies/2024`
   - 扫描路径填写：`movies/2024`

3. **路径分隔符**
   - 使用正斜杠 `/` 或反斜杠 `\` 均可
   - 程序会自动处理

### 常见问题

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

## Docker部署

本项目已发布到Docker Hub，您可以直接使用Docker镜像进行部署。

### Docker Hub仓库地址

[https://hub.docker.com/r/fgwxh123/thunder-subtitle](https://hub.docker.com/r/fgwxh123/thunder-subtitle)

### 部署示例

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

### 访问方式

部署完成后，通过以下地址访问Web UI：

http://localhost:8010

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
