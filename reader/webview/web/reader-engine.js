(function () {
  "use strict";

  const prototype = window.notebookPrototype;
  const positionMap = window.NotebookCharPosition;
  const i18n = window.notebookPocI18n;
  const t = (key, values) => i18n.t(key, values);
  const elements = prototype.elements;
  const loadingOverlay = document.getElementById("previewReaderLoading");
  const loadingDetail = document.getElementById("previewLoadingDetail");
  const cancelLoadingButton = document.getElementById("previewCancelLoading");

  document.querySelectorAll("[data-poc-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.pocI18n);
  });
  document.querySelectorAll("[data-poc-i18n-aria]").forEach((node) => {
    node.setAttribute("aria-label", t(node.dataset.pocI18nAria));
  });

  const state = {
    currentBookId: null,
    renderedBookId: null,
    metadata: new Map(),
    fragments: [],
    chapters: [],
    rendering: false,
    renderToken: 0,
    openToken: 0,
    positionAnchor: 0,
    savedPosition: 0,
    saveTimer: null,
    resizeTimer: null,
    scrollFrame: null,
  };

  function bridge() {
    const api = window.pywebview?.api;
    if (!api) throw new Error(t("bridgeUnavailable"));
    return api;
  }

  async function callPython(method, ...args) {
    const value = await bridge()[method](...args);
    if (typeof value !== "string") return value;
    if (!value.startsWith("b64:")) return JSON.parse(value);
    const binary = atob(value.slice(4));
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  }

  function nextFrame() {
    return new Promise((resolve) => requestAnimationFrame(resolve));
  }

  async function settledFrame() {
    await nextFrame();
    await nextFrame();
  }

  function isExternalBookVisible() {
    const active = prototype.activeBook();
    return (
      state.currentBookId !== null &&
      active?.external === true &&
      active.id === state.currentBookId &&
      prototype.getState().currentPage === "book" &&
      window.notebookPoc?.getState().appMode === "read" &&
      document.getElementById("bookPage").classList.contains("is-active")
    );
  }

  function reportError(error) {
    const message = error instanceof Error ? error.message : String(error);
    if (message === t("renderSuperseded")) return;
    prototype.showToast(t("loadFailed", { message }));
  }

  async function selectLocalBook(openAfterAdd) {
    try {
      const result = await callPython("select_novel", openAfterAdd ? "open" : "add");
      if (!result.ok) {
        if (result.cancelled) {
          prototype.showToast(t("cancelled"));
          return;
        }
        throw new Error(result.error || t("unknownError"));
      }
      const metadata = result.book;
      state.metadata.set(metadata.book_id, metadata);
      prototype.upsertExternalBook(metadata, { openAfterAdd });
      prototype.showToast(
        t(openAfterAdd ? "loadedNovel" : "addedNovel", { title: metadata.title }),
      );
    } catch (error) {
      reportError(error);
    }
  }

  function assertOpenToken(token) {
    if (token !== null && token !== state.openToken) {
      throw new Error(t("renderSuperseded"));
    }
  }

  function showLoading(book) {
    loadingDetail.textContent = t("openingBook", { title: book.title });
    prototype.showPage("book");
    loadingOverlay.hidden = false;
  }

  function hideLoading() {
    loadingOverlay.hidden = true;
  }

  function createFragmentNode(fragment) {
    const node = document.createElement(fragment.kind === "heading" ? "h2" : "div");
    node.className = `poc-reader-fragment poc-reader-fragment-${fragment.kind}`;
    node.dataset.pyStart = String(fragment.start);
    node.dataset.pyEnd = String(fragment.end);
    node.dataset.chapterIndex = String(fragment.chapter_index);
    node.dataset.renderStrategy = "chunked";
    node.appendChild(document.createTextNode(fragment.text));
    return node;
  }

  function validatePayload(payload) {
    let cursor = 0;
    for (const fragment of payload.fragments) {
      if (fragment.start !== cursor || fragment.end - fragment.start !== positionMap.codePointLength(fragment.text)) {
        throw new Error(t("payloadNonContiguous"));
      }
      cursor = fragment.end;
    }
    if (cursor !== payload.text_length) {
      throw new Error(t("payloadIncomplete"));
    }
  }

  async function renderPayload(payload, operationStarted, openToken = null) {
    const token = ++state.renderToken;
    state.rendering = true;
    state.fragments = [];
    state.chapters = payload.chapters;
    elements.readingArticle.className = "reading-column poc-reader-document poc-reader-document-chunked";
    elements.readingArticle.replaceChildren();
    let firstVisibleMs = null;
    let insertCpuMs = 0;
    const domStarted = performance.now();

    // Keep incremental first paint while limiting cumulative full-document
    // layout to roughly eight passes for multi-million-character books.
    const batchSize = Math.max(24, Math.ceil(payload.fragments.length / 8));
    for (let offset = 0; offset < payload.fragments.length; offset += batchSize) {
      if (token !== state.renderToken) throw new Error(t("renderSuperseded"));
      assertOpenToken(openToken);
      const insertStarted = performance.now();
      const documentFragment = document.createDocumentFragment();
      for (const fragment of payload.fragments.slice(offset, offset + batchSize)) {
        documentFragment.appendChild(createFragmentNode(fragment));
      }
      elements.readingArticle.appendChild(documentFragment);
      insertCpuMs += performance.now() - insertStarted;
      await nextFrame();
      if (firstVisibleMs === null) {
        await nextFrame();
        firstVisibleMs = performance.now() - operationStarted;
      }
    }

    assertOpenToken(openToken);

    const layoutStarted = performance.now();
    const scrollHeight = elements.readingScroll.scrollHeight;
    const layoutMs = performance.now() - layoutStarted;
    state.fragments = [...elements.readingArticle.querySelectorAll(".poc-reader-fragment")];
    state.rendering = false;
    return {
      dom_build_ms: performance.now() - domStarted,
      dom_insert_cpu_ms: insertCpuMs,
      first_visible_ms: firstVisibleMs ?? performance.now() - operationStarted,
      layout_force_ms: layoutMs,
      node_count: state.fragments.length,
      scroll_height: scrollHeight,
    };
  }

  function fragmentForPosition(position) {
    if (!state.fragments.length) return null;
    const target = Math.max(0, Math.trunc(position));
    let low = 0;
    let high = state.fragments.length;
    while (low < high) {
      const middle = (low + high) >> 1;
      if (Number(state.fragments[middle].dataset.pyEnd) <= target) low = middle + 1;
      else high = middle;
    }
    return state.fragments[Math.min(low, state.fragments.length - 1)];
  }

  function firstTextNode(node) {
    if (!node) return null;
    if (node.nodeType === Node.TEXT_NODE) return node;
    const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
    return walker.nextNode();
  }

  function fallbackTopFragment() {
    const scrollRect = elements.readingScroll.getBoundingClientRect();
    for (const fragment of state.fragments) {
      const rect = fragment.getBoundingClientRect();
      if (rect.bottom > scrollRect.top + 2) return fragment;
    }
    return state.fragments[state.fragments.length - 1] || null;
  }

  function topCharPosition() {
    if (!state.fragments.length || state.rendering) {
      return state.positionAnchor;
    }
    const scrollRect = elements.readingScroll.getBoundingClientRect();
    const articleRect = elements.readingArticle.getBoundingClientRect();
    const x = Math.min(scrollRect.right - 8, Math.max(scrollRect.left + 8, articleRect.left + 6));
    const y = Math.min(scrollRect.bottom - 4, scrollRect.top + 8);
    let range = null;
    if (document.caretPositionFromPoint) {
      const caret = document.caretPositionFromPoint(x, y);
      if (caret) {
        range = document.createRange();
        range.setStart(caret.offsetNode, caret.offset);
        range.collapse(true);
      }
    } else if (document.caretRangeFromPoint) {
      range = document.caretRangeFromPoint(x, y);
    }
    let container = range?.startContainer || null;
    let fragment =
      container?.nodeType === Node.ELEMENT_NODE
        ? container.closest?.(".poc-reader-fragment")
        : container?.parentElement?.closest(".poc-reader-fragment");
    if (!fragment) fragment = fallbackTopFragment();
    if (!fragment) return state.positionAnchor;
    const start = Number(fragment.dataset.pyStart);
    const end = Number(fragment.dataset.pyEnd);
    const textNode = firstTextNode(fragment);
    let utf16Offset = 0;
    if (range && textNode && range.startContainer === textNode) {
      utf16Offset = range.startOffset;
    }
    const local = textNode
      ? positionMap.utf16ToCodePointOffset(textNode.data, utf16Offset)
      : 0;
    return Math.min(end, Math.max(start, start + local));
  }

  async function restorePosition(position, { updateAnchor = true } = {}) {
    if (!state.fragments.length) return 0;
    const metadata = state.metadata.get(state.currentBookId);
    const textLength = metadata?.text_length || Number(state.fragments.at(-1).dataset.pyEnd);
    const target = Math.min(textLength, Math.max(0, Math.trunc(position)));
    const fragment = fragmentForPosition(target);
    const textNode = firstTextNode(fragment);
    if (!fragment || !textNode) return 0;
    const localCodePoints = Math.min(
      positionMap.codePointLength(textNode.data),
      Math.max(0, target - Number(fragment.dataset.pyStart)),
    );
    const utf16Offset = positionMap.codePointToUtf16Offset(textNode.data, localCodePoints);

    elements.readingScroll.scrollTop = Math.max(0, fragment.offsetTop - 8);
    await nextFrame();
    const range = document.createRange();
    range.setStart(textNode, utf16Offset);
    range.collapse(true);
    const rect = range.getBoundingClientRect();
    const scrollRect = elements.readingScroll.getBoundingClientRect();
    if (Number.isFinite(rect.top)) {
      elements.readingScroll.scrollTop += rect.top - scrollRect.top - 8;
    }
    await settledFrame();
    if (updateAnchor) state.positionAnchor = target;
    return topCharPosition();
  }

  function chapterIndexAt(position) {
    if (!state.chapters.length) return 0;
    let low = 0;
    let high = state.chapters.length;
    while (low < high) {
      const middle = (low + high) >> 1;
      if (state.chapters[middle].start_char <= position) low = middle + 1;
      else high = middle;
    }
    return Math.max(0, low - 1);
  }

  function updateBookDisplay(position) {
    const metadata = state.metadata.get(state.currentBookId);
    if (!metadata) return;
    const chapterIndex = chapterIndexAt(position);
    prototype.updateExternalBook(state.currentBookId, {
      charPosition: position,
      textLength: metadata.text_length,
      chapterIndex,
    });
  }

  function schedulePositionSave() {
    window.clearTimeout(state.saveTimer);
    state.saveTimer = window.setTimeout(() => {
      void saveCurrentPosition();
    }, 700);
  }

  async function saveCurrentPosition() {
    if (!state.currentBookId || state.rendering || !isExternalBookVisible()) {
      return state.positionAnchor;
    }
    const position = topCharPosition();
    state.positionAnchor = position;
    state.savedPosition = position;
    updateBookDisplay(position);
    await callPython("save_position", state.currentBookId, position);
    return position;
  }

  async function saveCurrentAnchor() {
    if (!state.currentBookId || state.rendering) return state.positionAnchor;
    const bookId = state.currentBookId;
    const position = isExternalBookVisible() ? topCharPosition() : state.positionAnchor;
    state.positionAnchor = position;
    state.savedPosition = position;
    updateBookDisplay(position);
    await callPython("save_position", bookId, position);
    return position;
  }

  async function loadAndRenderBook(book, options = {}) {
    const openToken = options.openToken ?? null;
    const metadata = state.metadata.get(book.id) || {
      book_id: book.id,
      title: book.title,
      text_length: book.textLength,
      char_position: book.charPosition,
      chapter_index: book.chapterIndex,
      chapters: book.chapters,
    };
    state.metadata.set(book.id, metadata);
    state.currentBookId = book.id;
    if (options.activate !== false) prototype.activateExternalBook(book.id);

    const operationStarted = performance.now();
    const heapBefore = performance.memory?.usedJSHeapSize ?? null;
    const bridgeStarted = performance.now();
    const payload = await callPython("get_render_payload", book.id);
    assertOpenToken(openToken);
    const bridgeMs = performance.now() - bridgeStarted;
    validatePayload(payload);
    const { fragments: _transferredFragments, ...payloadMetadata } = payload;
    state.metadata.set(book.id, payloadMetadata);
    const renderMetrics = await renderPayload(payload, operationStarted, openToken);
    state.renderedBookId = book.id;
    const restored = await restorePosition(payload.char_position || 0);
    assertOpenToken(openToken);
    state.savedPosition = payload.char_position || 0;
    updateBookDisplay(restored);
    const heapAfter = performance.memory?.usedJSHeapSize ?? null;
    const metrics = {
      strategy: "chunked",
      text_length: payload.text_length,
      chapter_count: payload.chapter_count,
      fragment_count: payload.fragment_count,
      parse_ms: payload.parse_ms,
      bridge_roundtrip_ms: bridgeMs,
      payload_prepare_ms: payload.payload_prepare_ms,
      transfer_and_serialization_estimate_ms: Math.max(
        0,
        bridgeMs - payload.payload_prepare_ms,
      ),
      ...renderMetrics,
      restored_position: restored,
      js_heap_before: heapBefore,
      js_heap_after: heapAfter,
      js_heap_delta_bytes:
        heapBefore === null || heapAfter === null ? null : heapAfter - heapBefore,
    };
    return metrics;
  }

  async function openExternalBook(book) {
    window.clearTimeout(state.saveTimer);
    if (
      state.renderedBookId === book.id &&
      state.currentBookId === book.id &&
      state.fragments.length
    ) {
      prototype.activateExternalBook(book.id);
      hideLoading();
      elements.readingScroll.focus({ preventScroll: true });
      return;
    }
    const token = ++state.openToken;
    ++state.renderToken;
    try {
      if (state.currentBookId && state.currentBookId !== book.id) {
        await saveCurrentAnchor();
      }
      assertOpenToken(token);
      showLoading(book);
      let prepared = book;
      if (book.persisted) {
        const metadata = await callPython("prepare_preview_book", book.id);
        assertOpenToken(token);
        prepared = prototype.upsertExternalBook(metadata);
        state.metadata.set(book.id, metadata);
      }
      await loadAndRenderBook(prepared, {
        activate: false,
        openToken: token,
      });
      assertOpenToken(token);
      if (book.persisted) {
        const committed = await callPython("commit_preview_book", book.id);
        assertOpenToken(token);
        prototype.updateExternalBook(book.id, {
          chapterIndex: committed.chapter_index,
          charPosition: committed.char_position,
          textLength: committed.text_length,
          lastOpened: committed.last_opened_at,
          missing: false,
        });
      }
      prototype.activateExternalBook(book.id);
      prototype.renderShelf();
      hideLoading();
      elements.readingScroll.focus({ preventScroll: true });
    } catch (error) {
      if (token === state.openToken) {
        state.currentBookId = null;
        state.renderedBookId = null;
        state.fragments = [];
        state.positionAnchor = 0;
        state.rendering = false;
        hideLoading();
        prototype.showPage("shelf");
      }
      throw error;
    }
  }

  function updateReadingState(book) {
    if (state.rendering || state.currentBookId !== book.id || !isExternalBookVisible()) return;
    const position = topCharPosition();
    state.positionAnchor = position;
    updateBookDisplay(position);
    schedulePositionSave();
  }

  function currentChapterIndex(book) {
    if (book.id !== state.currentBookId) return book.chapterIndex || 0;
    return chapterIndexAt(topCharPosition());
  }

  function renderChapterList(book, container, jumpHandler) {
    container.replaceChildren();
    const current = currentChapterIndex(book);
    for (const chapter of state.chapters) {
      const item = document.createElement("button");
      item.type = "button";
      item.className = `chapter-item${chapter.index === current ? " is-current" : ""}`;
      item.dataset.chapterIndex = String(chapter.index);
      const number = document.createElement("span");
      number.className = "chapter-number";
      number.textContent = String(chapter.index + 1).padStart(2, "0");
      const name = document.createElement("span");
      name.className = "chapter-name";
      name.textContent = chapter.title;
      item.append(number, name);
      item.addEventListener("click", () => jumpHandler(chapter.index));
      container.appendChild(item);
    }
  }

  async function jumpToChapter(book, index) {
    if (book.id !== state.currentBookId || !state.chapters.length) return;
    const chapter = state.chapters[Math.min(state.chapters.length - 1, Math.max(0, index))];
    await restorePosition(chapter.start_char);
    updateBookDisplay(chapter.start_char);
    await saveCurrentPosition();
  }

  function cancelLoad() {
    ++state.openToken;
    ++state.renderToken;
    if (state.rendering) {
      state.currentBookId = null;
      state.renderedBookId = null;
      state.fragments = [];
      state.positionAnchor = 0;
    }
    state.rendering = false;
    hideLoading();
  }

  async function renameBook(bookId, title) {
    try {
      const updated = await callPython("rename_preview_book", bookId, title);
      prototype.updateExternalBook(bookId, { title: updated.title });
      const metadata = state.metadata.get(bookId);
      if (metadata) metadata.title = updated.title;
      prototype.renderShelf();
      prototype.showToast(t("renameSucceeded"));
      return updated;
    } catch (error) {
      reportError(error);
      return null;
    }
  }

  async function relocateBook(bookId) {
    try {
      const result = await callPython("relocate_preview_book", bookId);
      if (!result.ok || result.cancelled) return null;
      prototype.updateExternalBook(bookId, {
        missing: false,
        filePath: result.book.file_path,
      });
      if (state.renderedBookId === bookId) {
        const metadata = state.metadata.get(bookId);
        if (metadata) metadata.path = result.book.file_path;
      } else {
        state.metadata.delete(bookId);
      }
      prototype.renderShelf();
      prototype.showToast(t("relocatedSucceeded"));
      return result.book;
    } catch (error) {
      reportError(error);
      return null;
    }
  }

  async function removeBook(bookId) {
    try {
      await callPython("remove_preview_book", bookId);
      prototype.removeExternalBook(bookId);
      state.metadata.delete(bookId);
      if (state.currentBookId === bookId) {
        state.currentBookId = null;
        state.renderedBookId = null;
        state.fragments = [];
      }
      prototype.showToast(t("removedSucceeded"));
      return true;
    } catch (error) {
      reportError(error);
      return false;
    }
  }

  async function saveTheme(theme) {
    return callPython("save_preview_theme", theme);
  }

  function adapter() {
    return {
      cancelLoad,
      currentChapterIndex,
      jumpToChapter,
      openBook: openExternalBook,
      relocateBook,
      removeBook,
      renameBook,
      renderChapterList,
      reportError,
      saveCurrentProgress: () => void saveCurrentPosition(),
      saveTheme,
      selectLocalBook,
      updateReadingState,
    };
  }

  async function restoreAfterReflow(anchor) {
    if (!state.currentBookId || !state.fragments.length || state.rendering) return;
    await restorePosition(anchor);
    updateBookDisplay(anchor);
  }

  function bindReflowProtection() {
    for (const input of [document.getElementById("fontSizeRange"), document.getElementById("lineHeightRange")]) {
      input?.addEventListener(
        "input",
        () => {
          if (!state.currentBookId || !isExternalBookVisible()) return;
          const anchor = topCharPosition();
          window.setTimeout(() => void restoreAfterReflow(anchor), 0);
        },
        true,
      );
    }
    document.getElementById("resetSettings")?.addEventListener(
      "click",
      () => {
        if (!state.currentBookId || !isExternalBookVisible()) return;
        const anchor = topCharPosition();
        window.setTimeout(() => void restoreAfterReflow(anchor), 0);
      },
      true,
    );
    document.getElementById("themeGrid")?.addEventListener(
      "click",
      () => {
        if (!state.currentBookId || !isExternalBookVisible()) return;
        const anchor = topCharPosition();
        window.setTimeout(() => void restoreAfterReflow(anchor), 0);
      },
      true,
    );
    window.addEventListener("resize", () => {
      if (!state.currentBookId || !isExternalBookVisible()) return;
      const anchor = state.positionAnchor || topCharPosition();
      window.clearTimeout(state.resizeTimer);
      state.resizeTimer = window.setTimeout(() => void restoreAfterReflow(anchor), 90);
    });
  }

  elements.readingScroll.addEventListener("scroll", () => {
    if (!state.currentBookId || state.rendering || state.scrollFrame !== null) return;
    state.scrollFrame = requestAnimationFrame(() => {
      state.scrollFrame = null;
      if (!isExternalBookVisible()) return;
      const position = topCharPosition();
      state.positionAnchor = position;
      updateBookDisplay(position);
    });
  });

  cancelLoadingButton?.addEventListener("click", () => {
    cancelLoad();
    prototype.showPage("shelf");
  });

  bindReflowProtection();
  prototype.registerExternalAdapter(adapter());

  window.notebookReader = {
    getState: () => ({
      currentBookId: state.currentBookId,
      renderedBookId: state.renderedBookId,
      strategy: "chunked",
      topPosition: topCharPosition(),
      fragmentCount: state.fragments.length,
      rendering: state.rendering,
    }),
    getCloseSnapshot: () => ({
      book_id: state.currentBookId,
      char_position:
        state.currentBookId && !state.rendering && isExternalBookVisible()
          ? topCharPosition()
          : state.positionAnchor,
    }),
    saveCurrentPosition,
    topCharPosition,
  };
})();
