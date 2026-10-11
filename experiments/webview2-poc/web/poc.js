(function () {
  "use strict";

  const shell = document.getElementById("appShell");
  const bridgePanel = document.querySelector(".poc-bridge-panel");
  const bridgeStatus = document.getElementById("pocBridgeStatus");
  const enableHoverButton = document.getElementById("pocEnableHover");
  const bridgeTestButton = document.getElementById("pocBridgeTest");
  const workNote = document.getElementById("pocWorkNote");
  const noteStatus = document.getElementById("pocNoteStatus");
  const t = (key, values) => window.notebookPocI18n.t(key, values);

  const pocState = {
    appMode: "work",
    bridgeReady: false,
    bridgeResult: null,
    lastNotification: null,
    previewEnabled: false,
    readingTheme: "classic",
    noteTimer: null,
  };

  function decodeEnvelope(value) {
    if (typeof value !== "string") return value;
    if (!value.startsWith("b64:")) return JSON.parse(value);
    const binary = atob(value.slice(4));
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  }

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
    if (!api) throw new Error(t("bridgeUnavailable"));
    return api;
  }

  async function saveWorkNote() {
    if (!pocState.previewEnabled) return true;
    window.clearTimeout(pocState.noteTimer);
    noteStatus.textContent = t("noteSaving");
    try {
      const raw = await requireBridge().save_preview_note(workNote.value);
      decodeEnvelope(raw);
      noteStatus.textContent = t("noteSaved");
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      noteStatus.textContent = t("noteSaveFailed", { message });
      return false;
    }
  }

  function scheduleWorkNoteSave() {
    if (!pocState.previewEnabled) return;
    window.clearTimeout(pocState.noteTimer);
    noteStatus.textContent = t("noteSaving");
    pocState.noteTimer = window.setTimeout(() => void saveWorkNote(), 700);
  }

  function bootstrap(snapshot) {
    if (!snapshot?.enabled) return false;
    pocState.previewEnabled = true;
    pocState.readingTheme = snapshot.reading_theme || "classic";
    document.body.classList.add("preview-live");
    workNote.value = snapshot.work_note || "";
    noteStatus.textContent = t("noteReady");
    window.notebookPrototype.bootstrapPreview(snapshot);
    return true;
  }

  function snapshotForClose() {
    const reading = window.notebookPhase2?.getCloseSnapshot?.() || {};
    return {
      work_note: workNote.value,
      reading_theme: window.notebookPrototype.getState().theme || pocState.readingTheme,
      book_id: reading.book_id || null,
      char_position: Number(reading.char_position) || 0,
    };
  }

  async function runBridgeTest() {
    setStatus(t("bridgeTesting"), "pending");
    try {
      const api = requireBridge();
      const [ping, info] = await Promise.all([
        api.ping("hello-from-javascript"),
        api.get_app_info(),
      ]);
      pocState.bridgeResult = { ping, info };
      const backend = info.renderer || "unknown";
      setStatus(t("bridgeOkay", { backend, reply: ping.reply }), "ok");
      return pocState.bridgeResult;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      pocState.bridgeResult = { error: message };
      setStatus(t("bridgeFailed", { message }), "error");
      return pocState.bridgeResult;
    }
  }

  function onPythonNotification(payload) {
    pocState.lastNotification = payload;
    const message = payload && payload.message ? payload.message : t("pythonNotification");
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
    themeChoices.find((button) => button.getAttribute("aria-label") === t("themeEyeCare"))?.click();
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

  window.notebookPreview = {
    bootstrap,
    saveWorkNote,
    snapshotForClose,
  };

  workNote.addEventListener("input", scheduleWorkNoteSave);

  enableHoverButton.addEventListener("click", async () => {
    try {
      await saveWorkNote();
      const result = await requireBridge().enable_hover_reading();
      setStatus(result.message || t("hoverEnabledFallback"), "ok");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setStatus(t("hoverEnableFailed", { message }), "error");
    }
  });

  bridgeTestButton.addEventListener("click", runBridgeTest);

  document.addEventListener("keydown", (event) => {
    if (!(event.altKey && event.key.toLowerCase() === "q")) return;
    event.preventDefault();
    setAppMode("work", "alt-q");
    void saveWorkNote();
    try {
      requireBridge()
        .disable_hover_reading()
        .then((result) => setStatus(result.message || t("hoverDisabledFallback"), "ok"))
        .catch((error) => setStatus(t("altQFailed", { message: String(error) }), "error"));
    } catch (error) {
      setStatus(t("altQFailed", { message: String(error) }), "error");
    }
  });

  window.addEventListener("pywebviewready", () => {
    pocState.bridgeReady = true;
    setStatus(t("bridgeReady"), "ok");
  });
})();
