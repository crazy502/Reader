# Notebook WebView2 PoC

这是与正式 Tkinter 应用完全隔离的 Windows 技术实验。第二阶段在第一阶段的
WebView2、Python/JavaScript bridge 与原生窗口 hover 验证之上，复用正式
Notebook 的 `reader.loaders.load_novel()` 和 `Novel` / `Chapter` 模型来读取真实
TXT/EPUB。

实验不会读取或写入正式的 `bookshelf.json`、`reader_config.json`、
`work_note.txt`，也不会修改原始小说。性能 PoC 的状态仅在进程内保存；可用测试版
则使用独立的 `%APPDATA%\Notebook-Web-Preview\`，不会接触正式 Notebook 数据。

## 环境

- Windows 10/11
- Microsoft Edge WebView2 Runtime
- Python 项目虚拟环境
- `pywebview==6.2.1`（仅记录在本实验的 `requirements.txt`）

从项目根目录执行：

```powershell
cd F:\Reader
.\.venv\Scripts\python.exe -m pip install -r .\experiments\webview2-poc\requirements.txt
```

## 正常启动

```powershell
cd F:\Reader
.\.venv\Scripts\python.exe .\experiments\webview2-poc\poc.py
```

## 可用测试版

测试版启动命令：

```powershell
cd F:\Reader
.\.venv\Scripts\python.exe .\experiments\webview2-poc\preview.py
```

测试版提供真实 TXT/EPUB 书架、按书保存的 `char_position`、阅读主题和可编辑工作
便笺。书架“添加书籍”只建档；点击封面后才解析、完成整本低节点 DOM 构建并恢复
位置。用户数据固定隔离在：

```text
%APPDATA%\Notebook-Web-Preview\
├── bookshelf.json
├── reader_config.json
└── work_note.txt
```

测试版 onefile 构建命令：

```powershell
cd F:\Reader
.\.venv\Scripts\pyinstaller.exe --noconfirm --clean `
  --distpath .\experiments\webview2-poc\dist `
  --workpath .\experiments\webview2-poc\build `
  .\experiments\webview2-poc\Notebook-Web-Preview.spec
```

输出为 `experiments\webview2-poc\dist\Notebook-Web-Preview.exe`，不会覆盖正式
`Notebook.exe`。

启动默认仍为模拟 `WORK_MODE`。点击“启用悬停阅读”后：

- 指针进入完整原生窗口约 400ms 后显示 `READ_MODE`；
- 指针移出完整原生窗口后尽快返回 `WORK_MODE`；
- `Alt+Q` 禁用 hover 并立即进入 `WORK_MODE`；
- 阅读页右上角菜单的“打开文件”可选择 TXT/EPUB 并直接阅读；
- 书架“添加书籍”只加入实验书架，不主动开始阅读；
- 原生文件选择器打开期间，Win32 hover 采样暂停，关闭后重新建立指针基线。

阅读菜单中的实验区可以选择渲染策略、手动保存/恢复字符位置并查看最近一次
性能数据。

## 两种真实 DOM 策略

### A：`whole`

- Python 按段落/行生成覆盖整个 `Novel.text` 的连续切片；
- JavaScript 创建完整 `DocumentFragment` 后一次插入；
- DOM 节点量与段落数量同阶，用作整本 DOM 基准。

### B：`chunked`

- Python 按章节标题和最多 64K Python 字符的正文块生成连续切片；
- JavaScript 以最多约 8 批逐步插入；
- DOM 节点量与章节/文本块数量同阶；
- 第一批可先显示，但本实验没有实现虚拟滚动，也不会卸载已经插入的块。

两种策略都直接使用 `Novel.text` 切片，拼接后必须逐字符等于正式模型。没有用
章节 `content` 重组全文。

## 字符位置契约

持久位置语义始终是 Python `Novel.text` 的 Unicode code point 绝对索引。

- 每个 DOM 文本节点记录 `data-py-start` / `data-py-end`；
- 保存时使用 Chromium caret/Range 获取视口顶部文本节点和 UTF-16 offset；
- `char-position.js` 显式进行 Python code point 与 JavaScript UTF-16 code unit 转换；
- Emoji、扩展汉字和其他非 BMP 字符不会被当成两个 Python 字符；
- 恢复时二分定位文本片段，再用 collapsed Range 将该字符放回视口顶部附近；
- 滚动百分比只用于显示，不作为位置事实来源。

窗口宽度、字号、行距变化时，前端保留变更前的字符锚点，排版稳定后再按该字符
恢复。主题变更也执行同一保护检查。

## 自动检查命令

Python 编译与 JavaScript 语法：

```powershell
cd F:\Reader
.\.venv\Scripts\python.exe -m compileall -q main.py reader experiments\webview2-poc
node --check .\experiments\webview2-poc\web\app.js
node --check .\experiments\webview2-poc\web\poc.js
node --check .\experiments\webview2-poc\web\char-position.js
node --check .\experiments\webview2-poc\web\reader-engine.js
node --check .\experiments\webview2-poc\web\src\i18n\messages.js
```

Unicode 映射测试：

```powershell
node --test .\experiments\webview2-poc\tests\test_char_position.js
```

实验 Python 测试（包括正式 loader 生成 TXT/EPUB、精确切片和 A/B 位置）：

```powershell
.\.venv\Scripts\python.exe -m pytest .\experiments\webview2-poc\tests -q
```

第一阶段回归冒烟：

```powershell
.\.venv\Scripts\python.exe .\experiments\webview2-poc\poc.py --smoke-test
```

第二阶段小规模真实 DOM 冒烟：

```powershell
.\.venv\Scripts\python.exe .\experiments\webview2-poc\poc.py --phase2-smoke
```

50万、100万、300万字符各 3 次并取中位数：

```powershell
.\.venv\Scripts\python.exe .\experiments\webview2-poc\poc.py --benchmark --benchmark-runs 3
```

单独压力测试指定规模：

```powershell
.\.venv\Scripts\python.exe .\experiments\webview2-poc\poc.py --benchmark --benchmark-sizes 3000000 --benchmark-runs 1
```

正式 Notebook 回归：

```powershell
.\.venv\Scripts\python.exe -m pytest .\tests -q
```

## 测量范围

自动 WebView2 基准记录：

- 正式 TXT parser 的多次解析时间与中位数；
- Python API 返回到 JavaScript 解码完成的 bridge 往返时间；
- payload 准备时间及“往返减准备”的传输/序列化估计值；
- DOM 完整构建、同步插入 CPU 时间、首次可见时间和强制布局时间；
- DOM 节点数、章节跳转和字符恢复误差；
- 快速跳到 20%/50%/80%/96% 位置时的可见节点/空白检查；
- Python 主进程及其 WebView2 子进程的 working set 与累计 CPU 时间；
- Chromium `performance.memory` 可用时的 JS heap 样本。

bridge 内部序列化和进程间传输无法由 pywebview 分别计时，因此只报告组合值和
估计值。Windows working set 会受垃圾回收、Edge 进程复用与测试顺序影响，适合看
量级，不应当作稳定峰值或精确的策略归因。

报告写入：

```text
experiments/webview2-poc/reports/latest-phase2-smoke.json
experiments/webview2-poc/reports/latest-phase2-benchmark.json
```

测试样本由 `sample_data.py` 临时生成，覆盖 TXT、EPUB spine 顺序、多个 XHTML、
图片忽略与 Unicode；它们是符合格式的生成样本，不是真实用户小说。

## 仍需人工验证

- 真实用户 TXT/EPUB 的段落观感与标题合理性；
- 鼠标滚轮快速连续滚动手感，特别是 300 万字中后段；
- 原生文件对话框关闭后的 hover 主观体验；
- `WORK_MODE` / `READ_MODE` 往返是否符合日常使用预期；
- 长时间阅读后的 WebView2 内存回收情况。

本目录仍是实验，不是正式 Notebook 启动入口，也不包含正式迁移方案。
