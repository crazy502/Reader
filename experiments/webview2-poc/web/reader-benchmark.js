(function () {
  "use strict";

  const core = window.notebookReaderBenchmarkCore;
  if (!core) return;
  const {
    callPython,
    elements,
    loadAndRenderBook,
    openExternalBook,
    positionMap,
    prototype,
    reportError,
    restorePosition,
    saveCurrentPosition,
    setMetrics,
    settledFrame,
    state,
    topCharPosition,
  } = core;
  const t = (key, values) => window.notebookPocI18n.t(key, values);
  const experimentState = {
    benchmark: { status: "idle", result: null, error: null },
    previewSmoke: { status: "idle", result: null, error: null },
  };

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

  async function runPreviewIntegrationSmoke() {
    experimentState.previewSmoke = { status: "running", result: null, error: null };
    try {
      const books = prototype.getBooks();
      if (books.length !== 2 || !books.every((book) => book.persisted)) {
        throw new Error("Preview smoke requires two persisted books.");
      }
      const first = books[0];
      const second = books[1];

      await openExternalBook(first);
      const firstMetadata = state.metadata.get(first.id);
      const firstTarget = Math.floor(firstMetadata.text_length * 0.31);
      await restorePosition(firstTarget);
      const firstSaved = await saveCurrentPosition();

      prototype.showPage("shelf");
      await openExternalBook(second);
      const secondMetadata = state.metadata.get(second.id);
      const secondTarget = Math.floor(secondMetadata.text_length * 0.69);
      await restorePosition(secondTarget);
      const secondSaved = await saveCurrentPosition();

      prototype.showPage("shelf");
      await openExternalBook(first);
      const firstRestored = topCharPosition();
      await callPython("save_preview_theme", "eye_care");
      const result = {
        ok:
          firstSaved > 0 &&
          secondSaved > 0 &&
          firstSaved !== secondSaved &&
          Math.abs(firstRestored - firstSaved) < 300,
        first: { saved: firstSaved, restored: firstRestored },
        second: { saved: secondSaved },
        active_book_id: first.id,
        fragment_count: state.fragments.length,
      };
      experimentState.previewSmoke = { status: "complete", result, error: null };
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      experimentState.previewSmoke = { status: "error", result: null, error: message };
      throw error;
    }
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
        exact_text_length: positionMap.codePointLength(renderedText) === metadata.text_length,
        unicode_markers_present: renderedText.includes("🙂") && renderedText.includes("𝄞"),
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
    experimentState.benchmark = { status: "running", result: null, error: null };
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
      experimentState.benchmark = { status: "complete", result, error: null };
      setMetrics(t("benchmarkDone"));
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      experimentState.benchmark = { status: "error", result: null, error: message };
      reportError(error);
      throw error;
    }
  }

  const strategySelect = document.getElementById("pocReaderStrategy");
  const saveButton = document.getElementById("pocReaderSave");
  const restoreButton = document.getElementById("pocReaderRestore");
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

  window.notebookPhase2 = {
    getBenchmarkState: () => experimentState.benchmark,
    getCloseSnapshot: () => window.notebookReader.getCloseSnapshot(),
    getPreviewSmokeState: () => experimentState.previewSmoke,
    getState: () => window.notebookReader.getState(),
    restorePosition,
    runAutomatedBenchmark,
    runIndependentBookStateTest,
    runGeneratedFormatSampleTest,
    runModePersistenceTest,
    runPreviewIntegrationSmoke,
    runReflowStabilityChecks,
    saveCurrentPosition,
    topCharPosition,
  };
})();
