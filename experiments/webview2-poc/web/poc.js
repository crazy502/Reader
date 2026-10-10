(function () {
  "use strict";

  const shell = document.getElementById("appShell");
  const bridgePanel = document.querySelector(".poc-bridge-panel");
  const bridgeStatus = document.getElementById("pocBridgeStatus");
  const enableHoverButton = document.getElementById("pocEnableHover");
  const bridgeTestButton = document.getElementById("pocBridgeTest");

  const pocState = {
    appMode: "work",
    bridgeReady: false,
    bridgeResult: null,
    lastNotification: null,
  };

  function setStatus(message, state = "pending") {
    bridgeStatus.textContent = message;
    bridgePanel.dataset.state = state;
    bridgePanel.title = message;
  }

  function setAppMode(mode, source = "python") {
    const normalized = mode === "read" ? "read" : "work";
    pocState.appMode = normalized;
    shell.dataset.appMode = normalized;
    shell.dataset.modeSource = source;
    return getState();
  }

  function getState() {
    const readingScroll = document.getElementById("readingScroll");
    return {
      appMode: pocState.appMode,
      readPage: document.getElementById("bookPage").classList.contains("is-active")
        ? "book"
        : "shelf",
      bridgeReady: pocState.bridgeReady,
      bridgeState: bridgePanel.dataset.state || "pending",
      readingScrollTop: Math.round(readingScroll.scrollTop),
      viewport: { width: window.innerWidth, height: window.innerHeight },
      userAgent: navigator.userAgent,
    };
  }

  function requireBridge() {
    const api = window.pywebview && window.pywebview.api;
    if (!api) throw new Error("Python bridge 尚未就绪，请稍后重试。 ");
    return api;
  }

  async function runBridgeTest() {
    setStatus("正在进行异步通信…", "pending");
    try {
      const api = requireBridge();
      const [ping, info] = await Promise.all([
        api.ping("hello-from-javascript"),
        api.get_app_info(),
      ]);
      pocState.bridgeResult = { ping, info };
      const backend = info.renderer || "unknown";
      setStatus(`通信正常 · ${backend} · ${ping.reply}`, "ok");
      return pocState.bridgeResult;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      pocState.bridgeResult = { error: message };
      setStatus(`通信失败：${message}`, "error");
      return pocState.bridgeResult;
    }
  }

  function onPythonNotification(payload) {
    pocState.lastNotification = payload;
    const message = payload && payload.message ? payload.message : "收到 Python 主动通知";
    setStatus(message, payload && payload.ok === false ? "error" : "ok");
    return true;
  }

  function runPrototypeSmoke() {
    const results = {};
    document.getElementById("backToShelf").click();
    results.bookshelf = document.getElementById("bookshelfPage").classList.contains("is-active");

    const firstCover = document.querySelector(".book-cover");
    firstCover?.click();
    results.openBook = document.getElementById("bookPage").classList.contains("is-active");

    document.getElementById("chapterTrigger").click();
    const chapterPanel = document.getElementById("chapterPanel");
    results.chapterPanel = !chapterPanel.hidden;
    document.querySelector(".chapter-item")?.click();
    results.chapterJump = chapterPanel.hidden;

    document.getElementById("readerMenuButton").click();
    const readerMenu = document.getElementById("readerMenu");
    results.readerMenu = !readerMenu.hidden;
    const themeChoices = [...document.querySelectorAll(".theme-choice")];
    themeChoices.find((button) => button.getAttribute("aria-label") === "护眼绿")?.click();
    results.theme = document.getElementById("bookPage").dataset.theme === "eye_care";

    const readingScroll = document.getElementById("readingScroll");
    readingScroll.scrollTop = 360;
    readingScroll.dispatchEvent(new Event("scroll"));
    results.continuousScroll =
      readingScroll.scrollHeight > readingScroll.clientHeight && readingScroll.scrollTop > 0;
    results.allPassed = Object.values(results).every(Boolean);
    return results;
  }

  window.notebookPoc = {
    getState,
    getBridgeResult: () => pocState.bridgeResult,
    getLastNotification: () => pocState.lastNotification,
    onPythonNotification,
    runBridgeTest,
    runPrototypeSmoke,
    setAppMode,
  };

  enableHoverButton.addEventListener("click", async () => {
    try {
      const result = await requireBridge().enable_hover_reading();
      setStatus(result.message || "悬停阅读已启用", "ok");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setStatus(`无法启用悬停阅读：${message}`, "error");
    }
  });

  bridgeTestButton.addEventListener("click", runBridgeTest);

  document.addEventListener("keydown", (event) => {
    if (!(event.altKey && event.key.toLowerCase() === "q")) return;
    event.preventDefault();
    setAppMode("work", "alt-q");
    try {
      requireBridge()
        .disable_hover_reading()
        .then((result) => setStatus(result.message || "已退出悬停阅读", "ok"))
        .catch((error) => setStatus(`Alt+Q 通信失败：${String(error)}`, "error"));
    } catch (error) {
      setStatus(`Alt+Q 通信失败：${String(error)}`, "error");
    }
  });

  window.addEventListener("pywebviewready", () => {
    pocState.bridgeReady = true;
    setStatus("Python bridge 已就绪", "ok");
  });
})();
