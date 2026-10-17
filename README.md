# Notebook

Notebook 是一款面向 Windows 的轻量本地小说阅读器，支持 TXT 和 EPUB。它采用连续滚动阅读，不做分页，也不把自己定位成复杂的电子书管理平台；核心目标是让阅读、临时工作记录和快速隐藏阅读内容保持简单、稳定、互不干扰。

项目目前同时保留两个可运行版本：

- **Tkinter 正式版**：稳定使用中的主版本，入口为 `main.py`。
- **WebView2 Preview**：生产实现位于 `reader/webview/`，并在 `experiments/webview2-poc/` 保留兼容入口、历史 PoC 和 benchmark。它已接入真实 TXT/EPUB、持久化和独立 EXE 打包，但尚未替代正式版。

## 核心设计

Notebook 将应用模式与阅读区域中的页面分开管理：

```text
mode
├─ WORK_MODE                 工作便笺
└─ READ_MODE                 阅读区域
   └─ read_page
      ├─ BOOKSHELF_PAGE      书架
      └─ BOOK_PAGE           小说正文
```

程序启动时默认显示 `WORK_MODE`。用户启用悬停阅读后，鼠标进入主窗口约 400ms 切换到 `READ_MODE`，离开窗口后尽快返回 `WORK_MODE`；`Alt+Q` 会立即关闭悬停阅读并回到工作便笺。书架和正文只是阅读区域内的两个页面，切换应用模式不会清空已加载的小说和阅读位置。

## 已实现功能

### 阅读与章节

- 读取 TXT，依次兼容 UTF-8、UTF-8-SIG、GBK 和 GB18030。
- 读取 EPUB 2 / EPUB 3，按 OPF spine 顺序提取正文，并优先使用 NCX 或 nav 中的章节标题。
- 将内容转换为连续纯文本阅读，支持自然换行、鼠标滚轮和方向键辅助滚动。
- 识别常见中文章、节、卷、回、篇标题以及 `Chapter 1` 等英文标题。
- 滚动时更新当前章节，并可从章节目录直接跳转。
- Tkinter 正式版的章节目录支持按标题搜索；Preview 使用阅读页内嵌章节面板。
- 提供经典、白色、护眼、羊皮纸和浅灰五种阅读主题，并恢复上次选择。

### 书架与进度

- 打开过的 TXT/EPUB 会进入本地书架，每本书独立保存阅读位置。
- 书架使用文字封面，显示当前章节和阅读百分比，并按最近阅读时间排序。
- 点击封面可打开或继续阅读；同一路径重复导入不会创建重复记录。
- 支持修改显示书名、重新定位已移动的文件，以及只移除书架记录而不删除原文件。
- 原文件缺失时保留书架记录，便于之后重新定位。
- 以整本书的 `char_position` 保存位置；阅读百分比仅用于展示。
- 滚动停止后自动保存，切换书籍或关闭窗口时也会保存当前状态。

### 工作便笺与悬停切换

- `WORK_MODE` 提供独立、可编辑的工作便笺，停止输入约 700ms 后自动保存。
- 阅读主题不会改变工作便笺的颜色、字体或内容。
- 悬停阅读默认关闭，需要用户在工作便笺中主动启用。
- 原生文件对话框打开期间会暂停 hover 切换，避免打断文件选择。
- `Alt+Q` 是应用内快捷键，不是系统全局快捷键。

## 两个版本的区别

| 项目 | Tkinter 正式版 | WebView2 Preview |
| --- | --- | --- |
| 状态 | 当前正式版本 | 独立测试版本，尚未替代正式版 |
| 源码入口 | `main.py` | `python -m reader.webview`；旧 `preview.py` 作为兼容入口保留 |
| UI 技术 | Python 标准库 + Tkinter | Python + pywebview + Microsoft Edge WebView2 |
| 正文渲染 | 单个持久化 `tk.Text` | WebView2 中的连续 DOM；默认使用分块插入策略 |
| 书架添加 | 当前会导入并直接打开正文 | 只加入书架，点击封面后才解析并打开 |
| 阅读页“打开文件” | 导入并直接阅读 | 导入并直接阅读 |
| 章节导航 | 临时章节目录，支持标题搜索 | 阅读页内嵌章节面板 |
| 窗口行为 | 主窗口保持置顶 | 普通 WebView2 窗口 |
| 打包配置 | onedir 与 onefile | 独立 onefile |
| 用户数据 | 源码运行使用 `data\`；EXE 使用 `%APPDATA%\Reader` | 正常运行使用 `%APPDATA%\Notebook-Web-Preview` |

Preview 复用正式版的 TXT/EPUB loader 和 `Novel` / `Chapter` 数据模型，但拥有独立的界面、存储目录和可执行文件。历史实验与验证细节见 [WebView2 Preview 说明](experiments/webview2-poc/README.md)。

## 运行环境与依赖

### 通用环境

- Windows 10 / 11
- Python 3.10 或更高版本
- 建议在项目虚拟环境中运行命令

### Tkinter 正式版

正式版没有第三方运行时依赖。Python 需要包含 Tkinter；python.org 提供的标准 Windows CPython 安装包默认包含它。

如需运行测试或自行打包，再安装开发依赖：

```powershell
python -m pip install -r .\requirements-dev.txt
```

### WebView2 Preview

Preview 另外需要：

- Microsoft Edge WebView2 Runtime
- `pywebview==6.2.1`

安装 Preview 的 Python 依赖：

```powershell
python -m pip install -r .\experiments\webview2-poc\requirements.txt
```

## 从源码启动

以下命令均在项目根目录执行。

启动 Tkinter 正式版：

```powershell
python .\main.py
```

启动 WebView2 Preview：

```powershell
python -m reader.webview
```

旧入口 `python .\experiments\webview2-poc\preview.py` 仍可使用；不带实验参数时会转到同一套正式 WebView2 生产实现。

如果使用仓库内的 `.venv`，可将上述 `python` 替换为 `.\.venv\Scripts\python.exe`。

## Windows EXE

### Tkinter 正式版

仓库提供两种 PyInstaller 配置：

```powershell
# onedir：输出到 dist\Notebook\Notebook.exe
python -m PyInstaller --noconfirm --clean .\Notebook.spec

# onefile：输出到 dist\Notebook.exe
python -m PyInstaller --noconfirm --clean .\Notebook-onefile.spec
```

运行打包产物不需要另外安装 Python。使用 onedir 版本时需要保留 `dist\Notebook\` 中的完整目录；onefile 版本可作为单个 `Notebook.exe` 运行。两种配置都会由 PyInstaller 收集所需的 Tcl/Tk 资源，并保留 Windows DPI 适配。

### WebView2 Preview

Preview 目前只提供独立的 onefile 配置。打包前需要同时安装根目录开发依赖和 Preview 依赖，然后执行：

```powershell
python -m PyInstaller --noconfirm --clean `
  --distpath .\experiments\webview2-poc\dist `
  --workpath .\experiments\webview2-poc\build `
  .\experiments\webview2-poc\Notebook-Web-Preview.spec
```

产物位于 `experiments\webview2-poc\dist\Notebook-Web-Preview.exe`，不会覆盖正式版的 `Notebook.exe`。运行该 EXE 不需要另装 Python，但系统仍必须提供 Microsoft Edge WebView2 Runtime。

## 基本使用

1. 启动后先在工作便笺中记录或编辑内容；便笺会自动保存。
2. 点击“启用悬停阅读”，将鼠标移入窗口进入阅读区域；移出窗口返回工作便笺。
3. 在书架中添加 TXT/EPUB。Preview 会停留在书架，点击封面后开始阅读；Tkinter 正式版当前会在选中文件后直接打开正文。
4. 点击书籍封面继续阅读，或从阅读页使用“打开文件”导入并直接阅读。
5. 使用返回按钮进入书架，使用当前章节入口打开目录并跳转章节。
6. 正常滚动即可更新进度；再次打开同一本书时会恢复到已保存的字符位置。
7. 随时按 `Alt+Q` 关闭悬停阅读并立即回到 `WORK_MODE`，小说、书架和进度不会因此清空。

## 数据存储

两个版本的数据完全隔离，不会自动迁移、同步或覆盖对方的数据。

### Tkinter 正式版

从源码运行时：

```text
<项目目录>\data\reader_config.json
<项目目录>\data\bookshelf.json
<项目目录>\data\work_note.txt
```

运行 PyInstaller EXE 时：

```text
%APPDATA%\Reader\reader_config.json
%APPDATA%\Reader\bookshelf.json
%APPDATA%\Reader\work_note.txt
```

为兼容已有版本，正式版继续使用 `%APPDATA%\Reader`。`reader_config.json` 保存全局阅读主题及旧版兼容配置；`bookshelf.json` 是当前书籍和每本书阅读进度的唯一可写来源；`work_note.txt` 保存 UTF-8 工作便笺。

### WebView2 Preview

无论从源码还是 EXE 启动，正常运行都使用：

```text
%APPDATA%\Notebook-Web-Preview\
├─ reader_config.json
├─ bookshelf.json
└─ work_note.txt
```

Preview 不读取或写入正式版的 `%APPDATA%\Reader` 和项目根目录 `data\`。即使两个版本导入同一本小说，也会分别维护书架记录和阅读进度。

## 项目结构

```text
Reader/
├─ main.py                         Tkinter 正式版入口
├─ reader/
│  ├─ app.py                      正式版状态与交互协调
│  ├─ core/                       书架、进度、配置、便笺和小说模型
│  ├─ loaders/                    TXT/EPUB 加载
│  ├─ ui/                         Tkinter 阅读、书架和工作便笺界面
│  ├─ webview/                    WebView2 控制器、存储、正文引擎与网页资源
│  ├─ platform/                   Windows DPI 与 Tcl/Tk 运行时适配
│  └─ i18n/                       正式版中英文界面文案
├─ experiments/webview2-poc/
│  ├─ preview.py                  旧 Preview 兼容入口
│  ├─ poc.py                      历史 PoC/benchmark 兼容控制器
│  ├─ benchmark_engine.py         模拟书籍与历史渲染 benchmark
│  ├─ web/                        历史实验网页资源
│  ├─ tests/                      WebView2 与兼容层检查
│  └─ Notebook-Web-Preview.spec   Preview onefile 配置
├─ prototypes/kindle-reader/      阅读界面的视觉参考原型
├─ tests/                         Tkinter 正式版测试
├─ data/                          正式版源码运行时的本地数据
├─ Notebook.spec                  正式版 onedir 配置
├─ Notebook-onefile.spec          正式版 onefile 配置
├─ requirements.txt               正式版运行依赖说明
└─ requirements-dev.txt           测试与打包依赖
```

## 当前状态与限制

- Tkinter 版本仍是根入口和正式版本；WebView2 的生产代码虽已迁入 `reader/webview/`，目前仍作为 Preview 用于真实使用体验和技术验证，没有正式数据迁移方案。
- 现有 `Notebook-Web-Preview.spec` 仍位于实验目录并保留原打包资源布局；本轮未迁移或修改打包配置。
- 当前仅支持 TXT 和 EPUB，不支持 DRM EPUB、MOBI 或 AZW3。
- EPUB 会被转换为连续纯文本，不还原原始 CSS、图片、字体、复杂脚注、多栏或固定版式。
- 非规范 EPUB 或同一 XHTML 内含复杂目录锚点时，章节可能回退为文档级划分。
- 书架保持轻量，不包含真实封面下载、分类、标签、全文搜索、阅读统计或云同步。
- Tkinter 正式版会将整本书放入一个 `tk.Text`；Preview 也会构建整本正文 DOM，尚未实现虚拟滚动或卸载已插入内容。极端超大文件可能占用较多内存。
- 文件移动后需要手动“重新定位”，并选择与原记录相同的文件格式。
- 当前没有系统托盘；PyInstaller onefile 首次启动时需要解压运行资源，通常会比 onedir 启动稍慢。
- Preview 仍需人工验证真实用户 TXT/EPUB 的段落与标题观感、超长文本快速滚动手感、原生文件对话框关闭后的 hover 体验、日常 `WORK_MODE` / `READ_MODE` 往返，以及长时间阅读后的 WebView2 内存回收情况。
