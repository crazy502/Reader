# Notebook

Notebook 是一个面向 Windows 的轻量 TXT / EPUB 小说阅读器，使用 Python 标准库和 Tkinter 开发。当前版本采用整本书连续滚动模型，章节只作为识别与导航层，不参与分页。

## 环境要求

- Windows
- Python 3.10 或更高版本
- Python 安装需要包含 Tkinter（python.org 的标准 Windows 安装包默认包含）
- 运行时没有第三方 Python 依赖

当前 v0.1.0 Release Candidate 基线使用 Python 3.13 和 PyInstaller 6.22.1 验证。

## 运行

```powershell
python main.py
```

开发和测试依赖单独维护：

```powershell
python -m pip install -r requirements-dev.txt
pytest
```

## 构建 Windows EXE

仓库同时保留两种 PyInstaller 构建配置：

```powershell
# onedir：便于调试和排查打包问题
python -m PyInstaller --noconfirm --clean Notebook.spec

# onefile：生成可独立复制运行的单文件 Notebook.exe
python -m PyInstaller --noconfirm --clean Notebook-onefile.spec
```

onefile 产物位于 `dist\Notebook.exe`。构建配置不会打包 `book/`、`data/`、测试文件或个人用户数据。Windows EXE 已启用 Per-Monitor V2 DPI awareness，并由 PyInstaller 收集运行所需的 Tcl/Tk 资源。

## 已实现功能

- TXT 编码兼容：UTF-8、UTF-8-SIG、GBK、GB18030
- EPUB 2 / EPUB 3：按 OPF spine 顺序读取正文，并优先使用 NCX/nav 章节标题
- EPUB 转换为连续纯文本阅读，忽略图片和原始 CSS 排版
- 整本书在一个 Tkinter Text 中连续显示和自然换行
- 阅读区提供经典、白色、护眼、羊皮纸和浅灰五种固定主题，并自动恢复上次选择
- 鼠标滚轮连续滚动，↑ / ↓ 每次辅助滚动少量行
- 中文章节识别：章、节、卷、回、篇等
- 英文章节识别：`Chapter 1` 等
- 顶部显示当前章节，滚动越过章节边界时自动更新
- 临时章节目录、当前章节定位、数字和标题关键词搜索
- 点击章节后跳转到章节标题附近并立即保存进度
- 打开过的 TXT / EPUB 自动加入轻量书架，每本书独立保存阅读位置
- 书架以响应式文字封面卡片展示，按最近阅读排序并显示阅读百分比与当前章节
- 单击封面继续阅读，右键或“⋯”可修改显示书名、重新定位文件以及只移除书架记录
- 原文件丢失时保留封面记录，并在卡片上提供明确的重新定位入口
- 以每本书的全文 `char_position` 为核心保存和恢复阅读位置
- 滚动停止约 700ms 后防抖保存
- WORK_MODE 提供可编辑的本地工作便笺，停止输入约 700ms 后自动保存
- WORK_MODE 底部保留“启用悬停阅读”入口，编辑区会随窗口大小伸缩
- 启动默认停留在工作便笺；用户主动启用后才按鼠标移入/移出切换阅读
- 应用内 `Alt+Q` 关闭悬停阅读并立即返回可编辑的工作便笺
- 阅读窗口保持置顶

## 用户数据

开发模式下，阅读进度和工作便笺保存在：

```text
<项目目录>\data\reader_config.json
<项目目录>\data\bookshelf.json
<项目目录>\data\work_note.txt
```

PyInstaller frozen EXE 运行时保存在：

```text
%APPDATA%\Reader\reader_config.json
%APPDATA%\Reader\bookshelf.json
%APPDATA%\Reader\work_note.txt
```

为兼容已有版本，Notebook 继续使用 `%APPDATA%\Reader`。`reader_config.json` 只负责全局阅读主题；`bookshelf.json` 是当前书籍及每本书阅读进度的唯一数据源；工作便笺独立使用 UTF-8 文本保存。首次升级时会把旧配置中的最后一本书及其 `chapter_index / char_position` 幂等迁移到书架，迁移后不再向旧进度字段写入新位置。旧配置没有主题字段时继续使用原来的经典暖纸张配色。用户数据目录不存在时会自动创建。

## 目录结构

```text
Reader/
├─ main.py
├─ README.md
├─ requirements.txt
├─ requirements-dev.txt
├─ Notebook.spec
├─ Notebook-onefile.spec
├─ reader/
│  ├─ app.py
│  ├─ core/
│  │  ├─ bookshelf.py
│  │  ├─ config.py
│  │  ├─ novel_parser.py
│  │  ├─ progress.py
│  │  └─ work_note.py
│  ├─ loaders/
│  │  ├─ __init__.py
│  │  └─ epub_loader.py
│  ├─ ui/
│  │  ├─ bookshelf.py
│  │  ├─ reader_view.py
│  │  ├─ chapter_navigation.py
│  │  └─ work_view.py
│  ├─ platform/
│  │  ├─ dpi_awareness.py
│  │  └─ tk_runtime.py
│  └─ i18n/
│     ├─ zh_CN.py
│     └─ en_US.py
├─ book/
├─ data/
└─ tests/
```

## 已知限制

- 不支持 DRM 加密 EPUB，也不支持 MOBI、AZW3
- EPUB 暂不还原 CSS、图片、字体、复杂脚注、多栏或固定版式
- 非规范 EPUB 或同一 XHTML 内包含复杂目录锚点时，章节可能回退为文档级划分
- 书架不含真实封面图片、分类、标签、全文搜索、阅读统计或云同步
- 文件移动后需要在书架中手动执行“重新定位”，且第一版要求新文件格式与原记录一致
- `Alt+Q` 是应用内快捷键，不是系统全局快捷键
- 没有系统托盘和主题/字体设置界面
- 整本小说一次性加载到 Text，极端超大文件可能占用较多内存
- onefile 首次启动需要解压运行资源，启动速度可能略慢于 onedir

## Future

后续可在真实需求出现后增加书签等能力；当前书架保持轻量，不包含复杂图书管理功能。
