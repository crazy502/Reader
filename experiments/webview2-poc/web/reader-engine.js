(function () {
  "use strict";

  const prototype = window.notebookPrototype;
  const positionMap = window.NotebookCharPosition;
  const i18n = window.notebookPocI18n;
  const t = (key, values) => i18n.t(key, values);
  const elements = prototype.elements;
  const strategySelect = document.getElementById("pocReaderStrategy");
  const saveButton = document.getElementById("pocReaderSave");
  const restoreButton = document.getElementById("pocReaderRestore");
  const metricsOutput = document.getElementById("pocReaderMetrics");

  document.querySelectorAll("[data-poc-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.pocI18n);
  });

  const state = {
    currentBookId: null,
    renderedBookId: null,
    metadata: new Map(),
    fragments: [],
    chapters: [],
    strategy: "chunked",
    rendering: false,
    renderToken: 0,
    positionAnchor: 0,
    savedPosition: 0,
    saveTimer: null,
    resizeTimer: null,
    scrollFrame: null,
    lastMetrics: null,
    benchmark: { status: "idle", result: null, error: null },
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
      document.getElementById("bookPage").classList.contains("is-active")
    );
  }

  function setMetrics(value) {
    state.lastMetrics = value;
    if (!metricsOutput) return;
    metricsOutput.textContent =
      typeof value === "string" ? value : JSON.stringify(value, null, 2);
  }

  function reportError(error) {
    const message = error instanceof Error ? error.message : String(error);
    prototype.showToast(t("loadFailed", { message }));
    setMetrics({ error: message });
  }

  async function selectLocalBook(openAfterAdd) {
    setMetrics(t("loadingNovel"));
    try {
      const result = await callPython("select_novel", openAfterAdd ? "open" : "add");
      if (!result.ok) {
        if (result.cancelled) {
          prototype.showToast(t("cancelled"));
          setMetrics(t("performanceIdle"));
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
      if (!openAfterAdd) setMetrics(metadata);
    } catch (error) {
      reportError(error);
    }
  }

  function createFragmentNode(fragment, strategy) {
    const node = document.createElement(fragment.kind === "heading" ? "h2" : "div");
    node.className = `poc-reader-fragment poc-reader-fragment-${fragment.kind}`;
    node.dataset.pyStart = String(fragment.start);
    node.dataset.pyEnd = String(fragment.end);
    node.dataset.chapterIndex = String(fragment.chapter_index);
    node.dataset.renderStrategy = strategy;
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

  async function renderPayload(payload, operationStarted) {
    const strategy = payload.strategy;
    const token = ++state.renderToken;
    state.rendering = true;
    state.fragments = [];
    state.chapters = payload.chapters;
    elements.readingArticle.className = `reading-column poc-reader-document poc-reader-document-${strategy}`;
    elements.readingArticle.replaceChildren();
    let firstVisibleMs = null;
    let insertCpuMs = 0;
    const domStarted = performance.now();

    if (strategy === "whole") {
      const insertStarted = performance.now();
      const documentFragment = document.createDocumentFragment();
      for (const fragment of payload.fragments) {
        documentFragment.appendChild(createFragmentNode(fragment, strategy));
      }
      elements.readingArticle.appendChild(documentFragment);
      insertCpuMs += performance.now() - insertStarted;
      await settledFrame();
      firstVisibleMs = performance.now() - operationStarted;
    } else {
      // Keep incremental first paint while limiting cumulative full-document
      // layout to roughly eight passes for multi-million-character books.
      const batchSize = Math.max(24, Math.ceil(payload.fragments.length / 8));
      for (let offset = 0; offset < payload.fragments.length; offset += batchSize) {
        if (token !== state.renderToken) throw new Error(t("renderSuperseded"));
        const insertStarted = performance.now();
        const documentFragment = document.createDocumentFragment();
        for (const fragment of payload.fragments.slice(offset, offset + batchSize)) {
          documentFragment.appendChild(createFragmentNode(fragment, strategy));
        }
        elements.readingArticle.appendChild(documentFragment);
        insertCpuMs += performance.now() - insertStarted;
        await nextFrame();
        if (firstVisibleMs === null) {
          await nextFrame();
          firstVisibleMs = performance.now() - operationStarted;
        }
      }
    }

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
    if (!state.fragments.length || state.rendering || !isExternalBookVisible()) {
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
    }, 400);
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

  async function loadAndRenderBook(book, strategy = state.strategy, benchmark = false) {
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
    prototype.activateExternalBook(book.id);
    state.strategy = strategy;
    if (strategySelect) strategySelect.value = strategy;

    const operationStarted = performance.now();
    const resourcesBefore = benchmark ? await callPython("get_process_metrics") : null;
    const heapBefore = performance.memory?.usedJSHeapSize ?? null;
    setMetrics(t("buildingDom"));
    const bridgeStarted = performance.now();
    const payload = await callPython("get_render_payload", book.id, strategy);
    const bridgeMs = performance.now() - bridgeStarted;
    validatePayload(payload);
    const { fragments: _transferredFragments, ...payloadMetadata } = payload;
    state.metadata.set(book.id, payloadMetadata);
    const renderMetrics = await renderPayload(payload, operationStarted);
    state.renderedBookId = book.id;
    const restored = await restorePosition(payload.char_position || 0);
    state.savedPosition = payload.char_position || 0;
    updateBookDisplay(restored);
    const heapAfter = performance.memory?.usedJSHeapSize ?? null;
    const resourcesAfter = benchmark ? await callPython("get_process_metrics") : null;
    const resourceDelta =
      resourcesBefore?.available && resourcesAfter?.available
        ? {
            rss_bytes: resourcesAfter.rss_bytes - resourcesBefore.rss_bytes,
            python_rss_bytes:
              resourcesAfter.python_rss_bytes - resourcesBefore.python_rss_bytes,
            child_rss_bytes: resourcesAfter.child_rss_bytes - resourcesBefore.child_rss_bytes,
            cpu_seconds: resourcesAfter.cpu_seconds - resourcesBefore.cpu_seconds,
          }
        : null;
    const metrics = {
      strategy,
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
      process_before: resourcesBefore,
      process_after: resourcesAfter,
      process_delta: resourceDelta,
    };
    setMetrics(metrics);
    return metrics;
  }

  async function openExternalBook(book) {
    window.clearTimeout(state.saveTimer);
    if (
      state.renderedBookId === book.id &&
      state.currentBookId === book.id &&
      state.fragments.length
    ) {
      await restorePosition(book.charPosition || state.positionAnchor || 0);
      elements.readingScroll.focus({ preventScroll: true });
      return;
    }
    await loadAndRenderBook(book, state.strategy, false);
    elements.readingScroll.focus({ preventScroll: true });
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

  function adapter() {
    return {
      currentChapterIndex,
      jumpToChapter,
      openBook: openExternalBook,
      renderChapterList,
      reportError,
      saveCurrentProgress: () => void saveCurrentPosition(),
      selectLocalBook,
      updateReadingState,
    };
  }

  function visibleFragmentCount() {
    const viewport = elements.readingScroll.getBoundingClientRect();
    return state.fragments.filter((node) => {
      const rect = node.getBoundingClientRect();
      return rect.bottom > viewport.top && rect.top < viewport.bottom;
    }).length;
  }

  async function rapidScrollCheck() {
    const maximum = Math.max(0, elements.readingScroll.scrollHeight - elements.readingScroll.clientHeight);
    const samples = [];
    for (const ratio of [0.2, 0.5, 0.8, 0.96]) {
      elements.readingScroll.scrollTop = maximum * ratio;
      await settledFrame();
      samples.push({ ratio, visible_fragments: visibleFragmentCount() });
    }
    return {
      samples,
      blank_samples: samples.filter((sample) => sample.visible_fragments === 0).length,
    };
  }

  async function positionCycleCheck(target) {
    const restoredStarted = performance.now();
    await restorePosition(target);
    const first = topCharPosition();
    const restoreMs = performance.now() - restoredStarted;
    let current = first;
    let maximumCycleDrift = 0;
    for (let cycle = 0; cycle < 4; cycle += 1) {
      await restorePosition(current);
      const next = topCharPosition();
      maximumCycleDrift = Math.max(maximumCycleDrift, Math.abs(next - current));
      current = next;
    }
    return {
      requested: target,
      first_visible: first,
      initial_error_chars: Math.abs(first - target),
      maximum_cycle_drift_chars: maximumCycleDrift,
      restore_ms: restoreMs,
    };
  }

  async function chapterJumpCheck() {
    if (!state.chapters.length) return { chapter_jump_ms: 0, error_chars: 0 };
    const chapter = state.chapters[Math.floor(state.chapters.length * 0.72)];
    const started = performance.now();
    await restorePosition(chapter.start_char);
    const actual = topCharPosition();
    return {
      chapter_jump_ms: performance.now() - started,
      requested: chapter.start_char,
      actual,
      error_chars: Math.abs(actual - chapter.start_char),
    };
  }

  async function benchmarkOne(metadata, strategy) {
    const book = prototype.upsertExternalBook(metadata);
    state.metadata.set(metadata.book_id, metadata);
    state.currentBookId = metadata.book_id;
    prototype.showPage("book");
    const metrics = await loadAndRenderBook(book, strategy, true);
    const target = Math.floor(metadata.text_length * 0.61);
    metrics.position = await positionCycleCheck(target);
    metrics.chapter_jump = await chapterJumpCheck();
    metrics.rapid_scroll = await rapidScrollCheck();
    metrics.final_process = await callPython("get_process_metrics");
    return metrics;
  }

  function numericMedian(values) {
    const ordered = values.filter(Number.isFinite).sort((left, right) => left - right);
    if (!ordered.length) return null;
    const middle = Math.floor(ordered.length / 2);
    return ordered.length % 2
      ? ordered[middle]
      : (ordered[middle - 1] + ordered[middle]) / 2;
  }

  function summarizeRuns(runs) {
    const fields = [
      "bridge_roundtrip_ms",
      "transfer_and_serialization_estimate_ms",
      "dom_build_ms",
      "dom_insert_cpu_ms",
      "first_visible_ms",
      "layout_force_ms",
      "node_count",
      "scroll_height",
      "js_heap_delta_bytes",
    ];
    const summary = Object.fromEntries(
      fields.map((field) => [field, numericMedian(runs.map((run) => run[field]))]),
    );
    summary.process_rss_delta_bytes = numericMedian(
      runs.map((run) => run.process_delta?.rss_bytes),
    );
    summary.process_cpu_delta_seconds = numericMedian(
      runs.map((run) => run.process_delta?.cpu_seconds),
    );
    summary.position_error_chars = numericMedian(
      runs.map((run) => run.position?.initial_error_chars),
    );
    summary.chapter_jump_ms = numericMedian(
      runs.map((run) => run.chapter_jump?.chapter_jump_ms),
    );
    return summary;
  }

  async function runReflowStabilityChecks() {
    const metadata = state.metadata.get(state.currentBookId);
    if (!metadata) return null;
    const target = Math.floor(metadata.text_length * 0.47);
    await restorePosition(target);
    const stable = topCharPosition();
    const results = { baseline: stable };
    const bookPage = document.getElementById("bookPage");
    const originalFont = bookPage.style.getPropertyValue("--reader-font-size");
    const originalLine = bookPage.style.getPropertyValue("--reader-line-height");
    const originalTheme = bookPage.dataset.theme || "classic";

    bookPage.style.setProperty("--reader-font-size", "21px");
    await settledFrame();
    await restorePosition(stable);
    results.font_size_error_chars = Math.abs(topCharPosition() - stable);

    bookPage.style.setProperty("--reader-line-height", "2.2");
    await settledFrame();
    await restorePosition(stable);
    results.line_height_error_chars = Math.abs(topCharPosition() - stable);

    bookPage.dataset.theme = originalTheme === "eye_care" ? "classic" : "eye_care";
    await settledFrame();
    await restorePosition(stable);
    results.theme_error_chars = Math.abs(topCharPosition() - stable);

    if (originalFont) bookPage.style.setProperty("--reader-font-size", originalFont);
    else bookPage.style.removeProperty("--reader-font-size");
    if (originalLine) bookPage.style.setProperty("--reader-line-height", originalLine);
    else bookPage.style.removeProperty("--reader-line-height");
    bookPage.dataset.theme = originalTheme;
    await settledFrame();
    await restorePosition(stable);
    return results;
  }

  async function runIndependentBookStateTest() {
    const firstMeta = await callPython("prepare_synthetic_book", 90_000, 1);
    const secondMeta = await callPython("prepare_synthetic_book", 110_000, 1);
    const first = prototype.upsertExternalBook(firstMeta);
    const second = prototype.upsertExternalBook(secondMeta);
    state.metadata.set(firstMeta.book_id, firstMeta);
    state.metadata.set(secondMeta.book_id, secondMeta);

    await loadAndRenderBook(first, "chunked", false);
    const firstTarget = Math.floor(firstMeta.text_length * 0.31);
    await restorePosition(firstTarget);
    const firstSaved = await saveCurrentPosition();

    await loadAndRenderBook(second, "chunked", false);
    const secondTarget = Math.floor(secondMeta.text_length * 0.69);
    await restorePosition(secondTarget);
    const secondSaved = await saveCurrentPosition();

    const firstState = await callPython("get_book_state", firstMeta.book_id);
    const secondState = await callPython("get_book_state", secondMeta.book_id);
    await loadAndRenderBook(first, "chunked", false);
    const firstRestored = await restorePosition(firstState.char_position);
    await loadAndRenderBook(second, "chunked", false);
    const secondRestored = await restorePosition(secondState.char_position);
    return {
      first: { saved: firstSaved, restored: firstRestored },
      second: { saved: secondSaved, restored: secondRestored },
      independent:
        firstState.char_position !== secondState.char_position &&
        Math.abs(firstRestored - firstState.char_position) < 300 &&
        Math.abs(secondRestored - secondState.char_position) < 300,
    };
  }

  async function runGeneratedFormatSampleTest() {
    const samples = await callPython("prepare_generated_format_samples");
    const results = { generated_samples: samples.generated_samples, books: {} };
    for (const format of ["txt", "epub"]) {
      const metadata = samples[format];
      const book = prototype.upsertExternalBook(metadata);
      state.metadata.set(metadata.book_id, metadata);
      await loadAndRenderBook(book, "chunked", false);
      const renderedText = elements.readingArticle.textContent;
      const requested = Math.floor(metadata.text_length * 0.55);
      await restorePosition(requested);
      const restored = topCharPosition();
      results.books[format] = {
        format: metadata.format,
        chapter_count: metadata.chapter_count,
        chapter_titles: metadata.chapters.map((chapter) => chapter.title),
        text_length: metadata.text_length,
        dom_code_point_length: positionMap.codePointLength(renderedText),
        exact_text_length:
          positionMap.codePointLength(renderedText) === metadata.text_length,
        unicode_markers_present:
          renderedText.includes("🙂") && renderedText.includes("𝄞"),
        restored,
        restore_error_chars: Math.abs(restored - requested),
      };
    }
    results.ok = Object.values(results.books).every(
      (book) =>
        book.chapter_count === 3 &&
        book.exact_text_length &&
        book.unicode_markers_present &&
        book.restore_error_chars < 300,
    );
    return results;
  }

  async function runModePersistenceTest() {
    if (!state.currentBookId || !state.fragments.length) return { ok: false };
    const bookId = state.currentBookId;
    const firstNode = state.fragments[0];
    const positionBefore = await saveCurrentPosition();
    const storedBefore = await callPython("get_book_state", bookId);

    prototype.showPage("shelf");
    window.notebookPoc.setAppMode("work", "phase2-mode-test");
    await settledFrame();
    // This is intentionally gated while hidden; it must not persist zero.
    await saveCurrentPosition();
    const storedHidden = await callPython("get_book_state", bookId);

    window.notebookPoc.setAppMode("read", "phase2-mode-test");
    prototype.showPage("book");
    await restorePosition(positionBefore);
    const storedAfter = await callPython("get_book_state", bookId);
    return {
      same_dom_node: firstNode === state.fragments[0] && firstNode.isConnected,
      position_before: positionBefore,
      hidden_position: storedHidden.char_position,
      position_after: storedAfter.char_position,
      no_zero_overwrite:
        storedBefore.char_position === storedHidden.char_position &&
        storedHidden.char_position === storedAfter.char_position,
      ok:
        firstNode === state.fragments[0] &&
        firstNode.isConnected &&
        storedBefore.char_position === storedHidden.char_position &&
        storedHidden.char_position === storedAfter.char_position,
    };
  }

  async function runAutomatedBenchmark(options = {}) {
    const sizes = Array.isArray(options.sizes) ? options.sizes : [500_000, 1_000_000, 3_000_000];
    const repeats = Math.max(1, Number(options.repeats) || 3);
    state.benchmark = { status: "running", result: null, error: null };
    try {
      const result = { generated_at: new Date().toISOString(), repeats, books: [] };
      for (const size of sizes) {
        setMetrics(t("benchmarkRunning", { size: size.toLocaleString() }));
        const metadata = await callPython("prepare_synthetic_book", size, 3);
        const entry = { metadata, strategies: {} };
        for (const strategy of ["whole", "chunked"]) {
          const runs = [];
          for (let run = 0; run < repeats; run += 1) {
            runs.push(await benchmarkOne(metadata, strategy));
          }
          entry.strategies[strategy] = { runs, median: summarizeRuns(runs) };
        }
        result.books.push(entry);
      }
      result.format_samples = await runGeneratedFormatSampleTest();
      result.mode_persistence = await runModePersistenceTest();
      result.reflow_stability = await runReflowStabilityChecks();
      result.independent_books = await runIndependentBookStateTest();
      state.benchmark = { status: "complete", result, error: null };
      setMetrics(t("benchmarkDone"));
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      state.benchmark = { status: "error", result: null, error: message };
      reportError(error);
      throw error;
    }
  }

  function getBenchmarkState() {
    return state.benchmark;
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

  strategySelect?.addEventListener("change", async () => {
    const selected = strategySelect.value === "whole" ? "whole" : "chunked";
    state.strategy = selected;
    if (!state.currentBookId) return;
    const metadata = state.metadata.get(state.currentBookId);
    const current = topCharPosition();
    await callPython("save_position", state.currentBookId, current);
    metadata.char_position = current;
    const book = prototype.updateExternalBook(state.currentBookId, { charPosition: current });
    await loadAndRenderBook(book, selected, false);
  });

  saveButton?.addEventListener("click", async () => {
    if (!state.currentBookId) {
      prototype.showToast(t("noRealBook"));
      return;
    }
    const position = await saveCurrentPosition();
    prototype.showToast(t("positionSaved", { position }));
  });

  restoreButton?.addEventListener("click", async () => {
    if (!state.currentBookId) {
      prototype.showToast(t("noRealBook"));
      return;
    }
    const position = await restorePosition(state.savedPosition);
    prototype.showToast(t("positionRestored", { position }));
  });

  bindReflowProtection();
  prototype.registerExternalAdapter(adapter());
  if (metricsOutput) metricsOutput.textContent = t("performanceIdle");

  window.notebookPhase2 = {
    getBenchmarkState,
    getState: () => ({
      currentBookId: state.currentBookId,
      renderedBookId: state.renderedBookId,
      strategy: state.strategy,
      topPosition: topCharPosition(),
      fragmentCount: state.fragments.length,
      rendering: state.rendering,
    }),
    restorePosition,
    runAutomatedBenchmark,
    runIndependentBookStateTest,
    runGeneratedFormatSampleTest,
    runModePersistenceTest,
    runReflowStabilityChecks,
    saveCurrentPosition,
    topCharPosition,
  };
})();
