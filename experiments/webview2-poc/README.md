# Notebook WebView2 PoC

这是与正式 Tkinter 应用完全隔离的技术实验，用于验证：

- pywebview 是否实际选择 Edge Chromium / WebView2；
- Kindle 风格 HTML 原型能否在独立 Windows 桌面窗口运行；
- JavaScript 调用 Python API，以及 Python 主动通知前端；
- 通过 Win32 原生窗口矩形而不是网页 `mouseleave` 判断 hover 边界；
- `WORK_MODE`、`READ_MODE` 与内部书架/阅读页状态能否独立存在。

实验不会读取或写入 `bookshelf.json`、`reader_config.json` 或 `work_note.txt`。

## 安装

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\experiments\webview2-poc\requirements.txt
```

## 启动

```powershell
.\.venv\Scripts\python.exe .\experiments\webview2-poc\poc.py
```

窗口标题应为 `Notebook WebView2 PoC`。启动默认显示模拟工作便笺；点击“启用悬停阅读”后，指针在原生窗口内持续约 400ms 才显示阅读区域，移出完整原生窗口后尽快恢复工作模式。`Alt+Q` 会禁用 hover 并立即显示工作模式。

## 自动冒烟

```powershell
.\.venv\Scripts\python.exe .\experiments\webview2-poc\poc.py --smoke-test
```

冒烟模式会打开真实 WebView2 窗口，验证原型主要 DOM 交互、JS→Python bridge、Python→JS 通知和两个窗口尺寸。它还会在不移动系统光标的情况下短暂移动实验窗口，以实测 Win32 原生窗口边界的进入/离开判断，然后恢复位置并自动关闭。物理鼠标操作手感仍需正常启动后人工验证。

## 资源加载

`web/index.html`、`style.css`、`app.js` 是现有原型的实验副本；`poc.css` 与 `poc.js` 只增加 PoC 状态和通信界面。pywebview 对本地入口启用受控的进程内 loopback 静态资源服务，不访问 CDN 或远程资源。
