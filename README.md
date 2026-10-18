# Notebook

Notebook 是一款面向 Windows 的轻量本地小说阅读器，使用 Python、pywebview 和 Microsoft Edge WebView2 构建。它支持 TXT 与 EPUB，以连续滚动方式阅读，并把工作便笺和小说阅读保持为两个相互独立的应用模式。

Notebook 专注于本地阅读、书架管理和阅读位置恢复，不依赖在线书库，也不以复杂的电子书管理功能为目标。

## 核心交互

```text
mode
├─ WORK_MODE                 工作便笺
└─ READ_MODE                 阅读区域
   └─ read_page
      ├─ BOOKSHELF_PAGE      书架
      └─ BOOK_PAGE           小说正文
```

- 程序启动后默认显示 `WORK_MODE`，工作便笺会自动保存。
- 用户点击“启用悬停阅读”后，鼠标进入主窗口约 400ms 会恢复 `READ_MODE`。
- 鼠标离开主窗口会尽快返回 `WORK_MODE`；再次进入时恢复此前的书架或正文页面。
- `Alt+Q` 会立即禁用悬停阅读并返回 `WORK_MODE`，但不会清空书架、当前书籍或阅读位置。
- 原生文件选择对话框打开期间会暂停 hover 检测，避免打断文件操作。

`BOOKSHELF_PAGE` 和 `BOOK_PAGE` 都属于 `READ_MODE`，不是独立的第三种应用模式。

## 已实现功能

### TXT 与 EPUB

- 支持 UTF-8、UTF-8-SIG、GBK 和 GB18030 编码的 TXT。
- 支持 EPUB 2 / EPUB 3，按 OPF spine 顺序提取正文并转换为连续纯文本。
- 识别常见的中文、英文 TXT 章节标题。
- 使用 EPUB 导航、NCX、文档标题等信息构建章节目录，并支持章节跳转。

### 书架与阅读进度

- 从书架添加 TXT 或 EPUB；添加后保持在书架，不自动进入正文。
- 从阅读页的菜单选择“打开文件”时，可以导入并直接阅读。
- 点击封面开始或继续阅读；切换书籍前保存当前书籍位置。
- 支持修改显示书名、重新定位已移动的文件以及移除书架记录。
- 同一路径重复导入不会建立重复记录，移除记录不会删除原始小说文件。
- 每本书独立保存章节、`char_position`、正文长度和最近阅读时间。
- 阅读位置使用 Python Unicode code point 偏移，前端会处理 JavaScript UTF-16 与该位置之间的映射。

### 阅读界面与工作便笺

- 提供经典、纯白、护眼绿、羊皮纸和浅灰五种阅读主题。
- 支持字号与行距调整；当前只有阅读主题会跨启动持久化。
- 工作便笺独立于小说内容和阅读主题，停止输入后自动保存。
- 支持关闭前保存当前便笺、主题和阅读位置。
- 中英文界面文字由 Python 和前端 i18n 资源统一提供。

## 技术架构

Notebook 的桌面窗口由 pywebview 创建，并明确使用 Microsoft Edge WebView2（`edgechromium`）作为渲染后端。

```text
Python
├─ 应用入口与窗口生命周期
├─ Windows 原生 hover 检测
├─ TXT / EPUB 解析
├─ 书架、主题和便笺持久化
└─ pywebview JavaScript bridge
       ↕
HTML / CSS / JavaScript
├─ WORK_MODE 与 READ_MODE 界面
├─ 书架和阅读器
├─ 章节目录与主题设置
└─ Unicode 阅读位置映射
```

PyInstaller 构建会把 Python 解释器、Python 模块、前端资源和 pywebview 所需 DLL 打包为一个 EXE。WebView2 Runtime 是 Windows 上独立安装的系统运行组件，不包含在 EXE 中。

## 运行环境

- Windows 10 或 Windows 11
- Python 3.10 或更高版本（仅源码运行和开发需要）
- Microsoft Edge WebView2 Runtime

Node.js 仅用于运行保留的 JavaScript 单元测试，不是启动 Notebook 的依赖。

## 创建虚拟环境并安装依赖

建议在项目根目录使用独立的 `.venv`。先确认当前 Python 版本不低于 3.10：

```powershell
python --version
python -m venv .venv
```

如果 Windows 上使用 Python Launcher，也可以执行：

```powershell
py -3 -m venv .venv
```

在 PowerShell 中激活虚拟环境并安装正式运行依赖：

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\requirements.txt
```

`requirements.txt` 当前安装 `pywebview==6.2.1` 及其传递依赖。如需运行测试或构建 EXE，安装开发依赖即可；`requirements-dev.txt` 已包含正式运行依赖：

```powershell
python -m pip install -r .\requirements-dev.txt
```

## 从源码启动

### 已激活 `.venv`

```powershell
python .\main.py
```

也可以使用模块入口：

```powershell
python -m reader.webview
```

### 不激活 `.venv`

直接指定虚拟环境中的解释器：

```powershell
.\.venv\Scripts\python.exe .\main.py
```

如果没有激活虚拟环境，`python` 通常会解析为 PATH 中的系统 Python。系统 Python 若没有安装本项目依赖，会在导入 `webview` 时出现 `ModuleNotFoundError`，因此 `python .\main.py` 可能无法启动。这不表示入口损坏，只表示当前命令使用了错误的 Python 环境。

项目不会修改系统 Python，也不会在启动时自动安装依赖。可以通过激活 `.venv`，或明确使用 `.\.venv\Scripts\python.exe`，保证运行的是安装过依赖的解释器。

如果 Microsoft Edge WebView2 Runtime 缺失，程序会显示运行时缺失提示并退出；仅安装 Python 依赖不能替代 WebView2 Runtime。

## 构建 Windows EXE

先安装 `requirements-dev.txt`，然后在项目根目录执行：

```powershell
python -m PyInstaller --noconfirm --clean .\Notebook.spec
```

未激活虚拟环境时可以使用：

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean .\Notebook.spec
```

输出文件为：

```text
dist\Notebook.exe
```

`Notebook.exe` 已包含运行 Notebook 所需的 Python 解释器和 Python 依赖，因此目标机器不需要额外安装 Python。目标机器仍需安装 Microsoft Edge WebView2 Runtime，程序才能创建 WebView2 窗口。

## 基本使用

1. 启动后在工作便笺中记录内容，停止输入后自动保存。
2. 点击“启用悬停阅读”，鼠标停留在窗口内约 400ms 后进入阅读区域。
3. 在书架点击“添加书籍”，选择 TXT 或 EPUB；添加后仍停留在书架。
4. 点击书籍封面开始或继续阅读，使用左上角返回按钮回到书架。
5. 点击顶部章节标题打开目录；更多菜单可打开文件、切换主题或调整字号和行距。
6. 阅读位置会在滚动停止、切换书籍和关闭程序时保存。
7. 鼠标移出窗口会返回工作便笺；按 `Alt+Q` 会同时禁用悬停阅读。

## 数据存储

源码运行与打包后的 EXE 使用同一个正式数据目录：

```text
%APPDATA%\Notebook\
├─ bookshelf.json
├─ reader_config.json
└─ work_note.txt
```

| 文件 | 内容 |
| --- | --- |
| `bookshelf.json` | 书架记录、`active_book_id` 以及每本书的章节、`char_position`、正文长度和最近阅读时间 |
| `reader_config.json` | 全局阅读主题 `reading_theme` |
| `work_note.txt` | UTF-8 工作便笺 |

`bookshelf.json` 是书架和阅读进度的唯一可写来源。JSON 与便笺保存均使用同目录临时文件再替换目标文件，避免写入过程中留下半个文件。

Notebook 只使用 `%APPDATA%\Notebook` 作为正式用户数据目录，不会自动扫描或迁移其他旧版本数据目录，也不会把原始 TXT/EPUB 复制进数据目录。

## 项目结构

```text
Reader/
├─ main.py                    正式源码入口
├─ Notebook.spec             PyInstaller onefile 打包配置
├─ reader/
│  ├─ core/                  TXT 解析、书架/独立进度模型、便笺原子写入
│  ├─ loaders/               EPUB 解析与加载
│  ├─ i18n/                  Python 核心与加载器文案
│  └─ webview/
│     ├─ __main__.py         python -m reader.webview 入口
│     ├─ app.py              资源定位、窗口创建与 WebView2 启动
│     ├─ controller.py       窗口生命周期、hover 检测和 JavaScript bridge
│     ├─ storage.py          书架、主题和便笺持久化
│     ├─ novel_engine.py     小说会话、阅读位置和正文渲染数据
│     ├─ i18n.py             WebView2 控制层文案
│     └─ web/                正式 HTML、CSS、JavaScript 与前端 i18n
├─ tests/                    核心 Python 与 JavaScript 测试
├─ requirements.txt         正式运行依赖
└─ requirements-dev.txt     测试与 PyInstaller 依赖
```

`build/`、`dist/`、`.venv/`、缓存、本地数据和本地小说均由 `.gitignore` 排除。

## 测试

Python 关键测试：

```powershell
python -m pytest -p no:cacheprovider -q
```

Unicode 位置映射和前端 i18n 测试：

```powershell
node --test .\tests\test_char_position.js .\tests\test_web_i18n.js
```

测试覆盖 TXT/EPUB 加载、书架添加和移除、独立进度、Unicode `char_position` 映射、主题和便笺持久化、关闭保存及 hover 状态逻辑。

## 当前限制

- 仅支持 Windows、TXT 和 EPUB，不支持 DRM EPUB、MOBI 或 AZW3。
- EPUB 会转换为连续纯文本，不还原原始 CSS、图片、字体、复杂脚注或固定版式。
- 非规范 EPUB 或复杂目录锚点可能回退为文档级章节。
- 当前正文会构建整本书的 DOM，极端超大文件可能占用较多内存。
- 字号和行距只在当前运行期间生效；跨启动持久化的阅读设置目前只有主题。
- 文件移动后需要手动重新定位，并选择与原记录相同的文件格式。
- 没有系统托盘；`Alt+Q` 是应用内快捷键。
- PyInstaller onefile 每次启动都需要把内置资源释放到临时目录，启动速度可能慢于源码运行。
