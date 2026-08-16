# TXT 小说阅读器 MVP

纯 Python/Tkinter 的 Windows TXT 小说阅读器：章节识别、连续滚动阅读、字符位置进度恢复，以及鼠标离开窗口时切换到工作便笺模式。

## 运行

需要 Windows 上自带 Tk 的 Python 3：

```powershell
python main.py
```

可选打包：

```powershell
pyinstaller --onefile --windowed main.py
```

阅读进度保存于 `data/reader_config.json`，以当前视口顶部附近的全文字符位置为准。滚动停止约 700ms 后自动保存，离开窗口、关闭程序和切换小说时立即保存。

## 当前范围

仅支持 TXT，不含书架、EPUB、目录侧栏、全局热键、系统托盘与自定义设置页。`Alt+Q` 是窗口获得焦点时可用的应用内快捷键。
