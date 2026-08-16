# Reader

Reader 是一个面向 Windows 的轻量 TXT 小说阅读器，使用 Python 标准库和 Tkinter 开发。当前版本采用整本书连续滚动模型，章节只作为识别与导航层，不参与分页。

## 环境要求

- Windows
- Python 3.10 或更高版本
- Python 安装需要包含 Tkinter（python.org 的标准 Windows 安装包默认包含）
- 运行时没有第三方 Python 依赖

当前 Release 基线使用 Python 3.13 验证。

## 运行

```powershell
python main.py
```

开发和测试依赖单独维护：

```powershell
python -m pip install -r requirements-dev.txt
pytest
```

本仓库尚未执行正式 PyInstaller 打包，也尚未生成固定的 `.spec` 构建配置。

## 已实现功能

- TXT 编码兼容：UTF-8、UTF-8-SIG、GBK、GB18030
- 整本 TXT 在一个 Tkinter Text 中连续显示和自然换行
- 鼠标滚轮连续滚动，↑ / ↓ 每次辅助滚动少量行
- 中文章节识别：章、节、卷、回、篇等
- 英文章节识别：`Chapter 1` 等
- 顶部显示当前章节，滚动越过章节边界时自动更新
- 临时章节目录、当前章节定位、数字和标题关键词搜索
- 点击章节后跳转到章节标题附近并立即保存进度
- 以全文 `char_position` 为核心保存和恢复阅读位置
- 滚动停止约 700ms 后防抖保存
- 鼠标离开窗口时进入 WORK_MODE，返回并停留约 400ms 后恢复阅读
- 应用内 `Alt+Q` 切换 READ_MODE / WORK_MODE
- 阅读窗口保持置顶

## 用户数据

开发模式下，阅读进度保存在：

```text
<项目目录>\data\reader_config.json
```

后续 PyInstaller frozen EXE 运行时，阅读进度保存在：

```text
%APPDATA%\Reader\reader_config.json
```

小说文件路径、章节索引和当前视口顶部附近的字符位置会写入进度文件。用户数据目录不存在时会自动创建。

## 目录结构

```text
Reader/
├─ main.py
├─ README.md
├─ requirements.txt
├─ requirements-dev.txt
├─ reader/
│  ├─ app.py
│  ├─ core/
│  │  ├─ config.py
│  │  ├─ novel_parser.py
│  │  └─ progress.py
│  ├─ ui/
│  │  ├─ reader_view.py
│  │  ├─ chapter_navigation.py
│  │  └─ work_view.py
│  ├─ platform/
│  │  └─ tk_runtime.py
│  └─ i18n/
│     ├─ zh_CN.py
│     └─ en_US.py
├─ book/
├─ data/
└─ tests/
```

## 已知限制

- 当前只支持 TXT，不支持 EPUB
- 没有书架、书签、全文搜索、阅读统计或云同步
- `Alt+Q` 是应用内快捷键，不是系统全局快捷键
- 没有系统托盘和主题/字体设置界面
- 整本小说一次性加载到 Text，极端超大文件可能占用较多内存

## Future

后续可在真实需求出现后增加 EPUB、最近阅读或书架功能；当前 Release 基线不包含这些能力。
