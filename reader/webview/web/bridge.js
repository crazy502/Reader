(function () {
  "use strict";

  const shell = document.getElementById("appShell");
  const enableHoverButton = document.getElementById("pocEnableHover");
  const workNote = document.getElementById("pocWorkNote");
  const noteStatus = document.getElementById("pocNoteStatus");
  const t = (key, values) => window.notebookPocI18n.t(key, values);

  const pocState = {
    appMode: "work",
    bridgeReady: false,
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
      bridgeState: pocState.bridgeReady ? "ready" : "pending",
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
    const reading = window.notebookReader?.getCloseSnapshot?.() || {};
    return {
      work_note: workNote.value,
      reading_theme: window.notebookPrototype.getState().theme || pocState.readingTheme,
      book_id: reading.book_id || null,
      char_position: Number(reading.char_position) || 0,
    };
  }

  function onPythonNotification(payload) {
    pocState.lastNotification = payload;
    return true;
  }

  window.notebookPoc = {
    getState,
    getLastNotification: () => pocState.lastNotification,
    onPythonNotification,
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
      await requireBridge().enable_hover_reading();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error(t("hoverEnableFailed", { message }));
    }
  });

  document.addEventListener("keydown", (event) => {
    if (!(event.altKey && event.key.toLowerCase() === "q")) return;
    event.preventDefault();
    setAppMode("work", "alt-q");
    void saveWorkNote();
    try {
      requireBridge().disable_hover_reading().catch((error) => {
        console.error(t("altQFailed", { message: String(error) }));
      });
    } catch (error) {
      console.error(t("altQFailed", { message: String(error) }));
    }
  });

  window.addEventListener("pywebviewready", () => {
    pocState.bridgeReady = true;
  });
})();
