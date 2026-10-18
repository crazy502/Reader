# Notebook

Notebook 是一款面向 Windows 的轻量本地小说阅读器，使用 Python、pywebview 和 Microsoft Edge WebView2 构建。它支持 TXT 与 EPUB，采用连续滚动阅读，并将工作便笺与小说阅读保持为两个相互独立的应用模式。

## 核心设计

```text
mode
├─ WORK_MODE                 工作便笺
└─ READ_MODE                 阅读区域
   └─ read_page
      ├─ BOOKSHELF_PAGE      书架
      └─ BOOK_PAGE           小说正文
```

程序启动时显示 `WORK_MODE`。启用悬停阅读后，鼠标进入窗口约 400ms 切换到阅读区域，离开窗口后立即返回工作便笺；`Alt+Q` 会关闭悬停阅读并回到工作便笺。模式切换不会清空书架、当前小说或阅读位置。

## 已实现功能

- 读取 UTF-8、UTF-8-SIG、GBK 和 GB18030 编码的 TXT。
- 读取 EPUB 2 / EPUB 3，并按 OPF spine 顺序提取连续纯文本。
- 识别常见中英文章节标题，提供章节目录和章节跳转。
- 本地书架支持添加、重命名、重新定位和移除书籍记录。
- 同一路径重复导入不会重复建档；移除书架记录不会删除原文件。
- 每本书独立保存 `char_position`、章节和最近阅读时间。
- 提供经典、白色、护眼、羊皮纸和浅灰五种阅读主题。
- 工作便笺自动保存，并与阅读主题和小说内容相互独立。
- 支持 hover 切换、`Alt+Q`、关闭前保存和原生文件选择。
- 中英文界面文案由 i18n 资源统一提供。

## 运行环境

- Windows 10 / 11
- Python 3.10 或更高版本
- Microsoft Edge WebView2 Runtime

安装正式运行依赖：

```powershell
python -m pip install -r .\requirements.txt
```

如需运行测试或构建 EXE：

```powershell
python -m pip install -r .\requirements-dev.txt
```

JavaScript 单元测试还需要本机提供 Node.js。

## 从源码启动

在项目根目录执行：

```powershell
python .\main.py
```

也可以使用模块入口：

```powershell
python -m reader.webview
```

## 构建 Windows EXE

Notebook 使用唯一的 PyInstaller onefile 配置：

```powershell
python -m PyInstaller --noconfirm --clean .\Notebook.spec
```

输出文件：

```text
dist\Notebook.exe
```

打包后的程序不需要另外安装 Python，但系统仍需提供 Microsoft Edge WebView2 Runtime。

## 基本使用

1. 启动后在工作便笺中记录内容，停止输入后会自动保存。
2. 点击“启用悬停阅读”，将鼠标移入窗口进入书架。
3. 点击“添加书籍”选择 TXT 或 EPUB；添加后仍停留在书架。
4. 点击封面开始或继续阅读，使用返回按钮回到书架。
5. 点击当前章节打开目录并跳转；更多菜单可切换主题或直接打开文件。
6. 阅读位置会在滚动停止、切换书籍和关闭程序时保存。
7. 按 `Alt+Q` 可立即关闭悬停阅读并返回工作便笺。

## 数据存储

源码和 EXE 都使用同一个正式数据目录：

```text
%APPDATA%\Notebook\
├─ bookshelf.json
├─ reader_config.json
└─ work_note.txt
```

`bookshelf.json` 是书架和每本书阅读进度的唯一可写来源；`reader_config.json` 保存阅读主题；`work_note.txt` 保存 UTF-8 工作便笺。

Notebook 不会自动读取或迁移旧版 `%APPDATA%\Reader`、`%APPDATA%\Notebook-Web-Preview` 或项目根目录 `data\` 中的数据。

## 项目结构

```text
Reader/
├─ main.py                    正式源码入口
├─ Notebook.spec             PyInstaller onefile 配置
├─ reader/
│  ├─ core/                  书架、进度、便笺和小说模型
│  ├─ loaders/               TXT/EPUB 加载
│  ├─ i18n/                  加载器与核心模块文案
│  └─ webview/
│     ├─ app.py              WebView2 应用入口
│     ├─ controller.py       窗口、hover 与 JavaScript bridge
│     ├─ storage.py          书架、主题和便笺持久化
│     ├─ novel_engine.py     正文载入与分块数据
│     └─ web/                HTML、CSS、JavaScript 和前端 i18n
├─ tests/                    核心 Python 与 JavaScript 测试
├─ requirements.txt         正式运行依赖
└─ requirements-dev.txt     测试与打包依赖
```

## 测试

```powershell
python -m pytest -p no:cacheprovider -q
node --test .\tests\test_char_position.js .\tests\test_web_i18n.js
```

测试覆盖 TXT/EPUB 加载、书架与独立进度、Unicode `char_position` 映射、主题和便笺持久化、WebView2 入口、关闭保存及 hover 状态逻辑。

## 当前限制

- 仅支持 TXT 和 EPUB，不支持 DRM EPUB、MOBI 或 AZW3。
- EPUB 会转换为连续纯文本，不还原原始 CSS、图片、字体、复杂脚注或固定版式。
- 非规范 EPUB 或复杂目录锚点可能回退为文档级章节。
- 当前正文会构建整本书的 DOM，极端超大文件可能占用较多内存。
- 文件移动后需要手动重新定位，并选择与原记录相同的文件格式。
- 没有系统托盘；`Alt+Q` 是应用内快捷键。
- PyInstaller onefile 首次启动时需要解压资源，通常比后续启动稍慢。
