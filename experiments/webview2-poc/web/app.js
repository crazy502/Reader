(function () {
  "use strict";

  const t = (key, values) => window.notebookPocI18n.t(key, values);

  const coverPalette = [
    "#DDD2BD",
    "#D5E1D0",
    "#D7E2EA",
    "#E8D5D5",
    "#E9DFC1",
    "#DDD6E8",
  ];

  const themes = [
    { id: "classic", name: t("themeClassic"), color: "#F6F1E7" },
    { id: "white", name: t("themeWhite"), color: "#FFFFFF" },
    { id: "eye_care", name: t("themeEyeCare"), color: "#EAF4DF" },
    { id: "parchment", name: t("themeParchment"), color: "#F3E7C9" },
    { id: "light_gray", name: t("themeLightGray"), color: "#F3F3F3" },
  ];

  let books = [];

  const state = {
    activeBookId: null,
    currentPage: null,
    theme: "classic",
    fontSize: 18,
    lineHeight: 1.95,
    contextBookId: null,
    dialogConfirm: null,
    toastTimer: null,
    scrollFrame: null,
    externalAdapter: null,
    prototypeAdapter: null,
  };

  const elements = {
    appShell: document.getElementById("appShell"),
    bookshelfPage: document.getElementById("bookshelfPage"),
    bookPage: document.getElementById("bookPage"),
    bookGrid: document.getElementById("bookGrid"),
    emptyState: document.getElementById("emptyState"),
    shelfScroll: document.getElementById("shelfScroll"),
    addBookButton: document.getElementById("addBookButton"),
    emptyAddButton: document.getElementById("emptyAddButton"),
    backToShelf: document.getElementById("backToShelf"),
    chapterTrigger: document.getElementById("chapterTrigger"),
    navChapterTitle: document.getElementById("navChapterTitle"),
    readerMenuButton: document.getElementById("readerMenuButton"),
    readerMenu: document.getElementById("readerMenu"),
    readingScroll: document.getElementById("readingScroll"),
    readingArticle: document.getElementById("readingArticle"),
    readerProgressFill: document.getElementById("readerProgressFill"),
    readerProgressText: document.getElementById("readerProgressText"),
    mockOpenFile: document.getElementById("mockOpenFile"),
    themeGrid: document.getElementById("themeGrid"),
    fontSizeRange: document.getElementById("fontSizeRange"),
    fontSizeValue: document.getElementById("fontSizeValue"),
    lineHeightRange: document.getElementById("lineHeightRange"),
    lineHeightValue: document.getElementById("lineHeightValue"),
    resetSettings: document.getElementById("resetSettings"),
    chapterScrim: document.getElementById("chapterScrim"),
    chapterPanel: document.getElementById("chapterPanel"),
    closeChapters: document.getElementById("closeChapters"),
    chapterList: document.getElementById("chapterList"),
    bookContextMenu: document.getElementById("bookContextMenu"),
    modalBackdrop: document.getElementById("modalBackdrop"),
    dialogTitle: document.getElementById("dialogTitle"),
    dialogMessage: document.getElementById("dialogMessage"),
    dialogInputWrap: document.getElementById("dialogInputWrap"),
    dialogInput: document.getElementById("dialogInput"),
    dialogCancel: document.getElementById("dialogCancel"),
    dialogConfirm: document.getElementById("dialogConfirm"),
    toast: document.getElementById("toast"),
  };

  function activeBook() {
    return books.find((book) => book.id === state.activeBookId) || books[0] || null;
  }

  function stableColor(bookId) {
    let hash = 2166136261;
    for (let index = 0; index < bookId.length; index += 1) {
      hash ^= bookId.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return coverPalette[(hash >>> 0) % coverPalette.length];
  }

  function clamp(value, minimum, maximum) {
    return Math.min(maximum, Math.max(minimum, value));
  }

  function displayChapterLabel(book, index) {
    if (book?.external && Array.isArray(book.chapters) && book.chapters.length) {
      const chapter = book.chapters[clamp(index, 0, book.chapters.length - 1)];
      return chapter.title;
    }
    return state.prototypeAdapter?.chapterLabel(index) || "";
  }

  function renderShelf() {
    elements.bookGrid.replaceChildren();
    const openedAt = (book) => {
      if (typeof book.lastOpened === "number") return book.lastOpened;
      const parsed = Date.parse(book.lastOpened || "");
      return Number.isFinite(parsed) ? parsed : 0;
    };
    const orderedBooks = [...books].sort((left, right) => openedAt(right) - openedAt(left));

    orderedBooks.forEach((book) => {
      const card = document.createElement("article");
      card.className = `book-card${book.id === state.activeBookId ? " is-current" : ""}`;
      card.dataset.bookId = book.id;

      const cover = document.createElement("div");
      cover.className = "book-cover";
      cover.style.backgroundColor = stableColor(book.id);
      cover.tabIndex = 0;
      cover.setAttribute("role", "button");
      cover.setAttribute(
        "aria-label",
        t("bookProgressAria", {
          title: book.title,
          progress: Math.round(book.progress * 100),
        }),
      );

      if (book.id === state.activeBookId) {
        const marker = document.createElement("span");
        marker.className = "current-marker";
        marker.textContent = t("currentlyReading");
        cover.appendChild(marker);
      }

      const title = document.createElement("span");
      title.className = "cover-title";
      title.textContent = book.title;
      cover.appendChild(title);

      const menuButton = document.createElement("button");
      menuButton.type = "button";
      menuButton.className = "card-menu-button";
      menuButton.textContent = "⋯";
      menuButton.setAttribute("aria-label", t("bookMenuAria", { title: book.title }));
      menuButton.addEventListener("click", (event) => {
        event.stopPropagation();
        const rect = menuButton.getBoundingClientRect();
        openBookContextMenu(book.id, rect.right - 150, rect.bottom + 2);
      });
      cover.appendChild(menuButton);

      if (book.missing) {
        const missing = document.createElement("span");
        missing.className = "missing-badge";
        missing.textContent = t("missingFileBadge");
        cover.appendChild(missing);
      }

      const activate = () => {
        if (book.missing) {
          promptRelocate(book.id);
          return;
        }
        openBook(book.id);
      };
      cover.addEventListener("click", (event) => {
        if (!event.target.closest(".card-menu-button")) activate();
      });
      cover.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          activate();
        }
      });
      card.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        openBookContextMenu(book.id, event.clientX, event.clientY);
      });

      const meta = document.createElement("div");
      meta.className = "book-meta";
      const metaRow = document.createElement("div");
      metaRow.className = "book-meta-row";
      const chapter = document.createElement("span");
      chapter.className = "book-caption";
      chapter.textContent = t("chapterShort", { index: book.chapterIndex + 1 });
      const percentage = document.createElement("span");
      percentage.textContent = `${Math.round(book.progress * 100)}%`;
      metaRow.append(chapter, percentage);

      const progressTrack = document.createElement("div");
      progressTrack.className = "book-progress-track";
      const progressFill = document.createElement("span");
      progressFill.style.width = `${clamp(book.progress, 0, 1) * 100}%`;
      progressTrack.appendChild(progressFill);
      meta.append(metaRow, progressTrack);

      card.append(cover, meta);
      elements.bookGrid.appendChild(card);
    });

    const isEmpty = orderedBooks.length === 0;
    elements.bookGrid.hidden = isEmpty;
    elements.emptyState.hidden = !isEmpty;
  }

  function openBook(bookId) {
    const nextBook = books.find((book) => book.id === bookId);
    if (!nextBook) return;
    if (nextBook.missing) {
      promptRelocate(nextBook.id);
      return;
    }

    if (state.currentPage === "book") saveCurrentProgress();
    closeTransientUi();
    if (nextBook.external && state.externalAdapter) {
      Promise.resolve(state.externalAdapter.openBook(nextBook)).catch((error) => {
        state.externalAdapter.reportError?.(error);
      });
      return;
    }
    state.activeBookId = nextBook.id;
    nextBook.lastOpened = Date.now();
    state.currentPage = "book";
    if (!state.prototypeAdapter) return;
    state.prototypeAdapter.renderArticle(nextBook, elements.readingArticle);
    updateChapterHeader(nextBook.chapterIndex);
    showPage("book");

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const maximum = Math.max(
          0,
          elements.readingScroll.scrollHeight - elements.readingScroll.clientHeight,
        );
        elements.readingScroll.scrollTop = maximum * clamp(nextBook.progress, 0, 1);
        updateReadingState();
        elements.readingScroll.focus({ preventScroll: true });
      });
    });
  }

  function showPage(pageName) {
    const showBook = pageName === "book";
    elements.bookPage.classList.toggle("is-active", showBook);
    elements.bookshelfPage.classList.toggle("is-active", !showBook);
    state.currentPage = pageName;
    if (!showBook) {
      renderShelf();
      requestAnimationFrame(() => {
        const current = elements.bookGrid.querySelector(".book-card.is-current");
        if (current) current.scrollIntoView({ block: "nearest" });
      });
    }
  }

  function saveCurrentProgress() {
    const book = activeBook();
    if (!book || state.currentPage !== "book") return;
    if (book.external && state.externalAdapter) {
      state.externalAdapter.saveCurrentProgress(book);
      return;
    }
    const maximum = elements.readingScroll.scrollHeight - elements.readingScroll.clientHeight;
    book.progress = maximum > 0 ? clamp(elements.readingScroll.scrollTop / maximum, 0, 1) : 0;
    book.chapterIndex = currentChapterIndex();
  }

  function currentChapterIndex() {
    const book = activeBook();
    if (book?.external && state.externalAdapter) {
      return state.externalAdapter.currentChapterIndex(book);
    }
    return state.prototypeAdapter?.currentChapterIndex(elements) || 0;
  }

  function updateReadingState() {
    const book = activeBook();
    if (!book) return;
    if (book.external && state.externalAdapter) {
      state.externalAdapter.updateReadingState(book);
      return;
    }
    const maximum = elements.readingScroll.scrollHeight - elements.readingScroll.clientHeight;
    book.progress = maximum > 0 ? clamp(elements.readingScroll.scrollTop / maximum, 0, 1) : 0;
    book.chapterIndex = currentChapterIndex();
    const percentage = Math.round(book.progress * 100);
    elements.readerProgressFill.style.width = `${percentage}%`;
    elements.readerProgressText.textContent = `${percentage}%`;
    updateChapterHeader(book.chapterIndex);

    const selected = elements.chapterList.querySelector(".chapter-item.is-current");
    if (selected && Number(selected.dataset.chapterIndex) !== book.chapterIndex) {
      renderChapterList();
    }
  }

  function updateChapterHeader(index) {
    elements.navChapterTitle.textContent = displayChapterLabel(activeBook(), index);
  }

  function renderChapterList() {
    const book = activeBook();
    if (!book) return;
    if (book.external && state.externalAdapter) {
      state.externalAdapter.renderChapterList(book, elements.chapterList, jumpToChapter);
      return;
    }
    state.prototypeAdapter?.renderChapterList(
      book,
      elements.chapterList,
      jumpToChapter,
    );
  }

  function openChapterPanel() {
    hideReaderMenu();
    renderChapterList();
    elements.chapterScrim.hidden = false;
    elements.chapterPanel.hidden = false;
    requestAnimationFrame(() => {
      const current = elements.chapterList.querySelector(".chapter-item.is-current");
      if (current) current.scrollIntoView({ block: "center" });
    });
  }

  function closeChapterPanel() {
    elements.chapterScrim.hidden = true;
    elements.chapterPanel.hidden = true;
  }

  function jumpToChapter(index) {
    const book = activeBook();
    if (book?.external && state.externalAdapter) {
      state.externalAdapter.jumpToChapter(book, index);
      closeChapterPanel();
      return;
    }
    if (!book || !state.prototypeAdapter) return;
    book.chapterIndex = index;
    state.prototypeAdapter.jumpToChapter(index, elements);
    closeChapterPanel();
    updateReadingState();
  }

  function renderThemes() {
    elements.themeGrid.replaceChildren();
    themes.forEach((theme) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `theme-choice${state.theme === theme.id ? " is-selected" : ""}`;
      button.setAttribute("aria-label", theme.name);
      const swatch = document.createElement("span");
      swatch.className = "theme-swatch";
      swatch.style.backgroundColor = theme.color;
      const label = document.createElement("small");
      label.textContent = theme.name;
      button.append(swatch, label);
      button.addEventListener("click", () => applyTheme(theme.id));
      elements.themeGrid.appendChild(button);
    });
  }

  function applyTheme(themeId, persist = true) {
    state.theme = themes.some((theme) => theme.id === themeId) ? themeId : "classic";
    elements.bookPage.dataset.theme = state.theme;
    renderThemes();
    if (persist && state.externalAdapter?.saveTheme) {
      Promise.resolve(state.externalAdapter.saveTheme(state.theme)).catch((error) => {
        state.externalAdapter.reportError?.(error);
      });
    }
  }

  function applyReadingSettings() {
    elements.bookPage.style.setProperty("--reader-font-size", `${state.fontSize}px`);
    elements.bookPage.style.setProperty("--reader-line-height", String(state.lineHeight));
    elements.fontSizeRange.value = String(state.fontSize);
    elements.fontSizeValue.value = String(state.fontSize);
    elements.lineHeightRange.value = String(state.lineHeight);
    elements.lineHeightValue.value = state.lineHeight.toFixed(2);
  }

  function toggleReaderMenu() {
    closeChapterPanel();
    closeBookContextMenu();
    elements.readerMenu.hidden = !elements.readerMenu.hidden;
    elements.readerMenuButton.setAttribute("aria-expanded", String(!elements.readerMenu.hidden));
  }

  function hideReaderMenu() {
    elements.readerMenu.hidden = true;
    elements.readerMenuButton.setAttribute("aria-expanded", "false");
  }

  function openBookContextMenu(bookId, requestedX, requestedY) {
    hideReaderMenu();
    state.contextBookId = bookId;
    elements.bookContextMenu.hidden = false;
    const shellRect = elements.appShell.getBoundingClientRect();
    const menuRect = elements.bookContextMenu.getBoundingClientRect();
    const x = clamp(requestedX - shellRect.left, 8, shellRect.width - menuRect.width - 8);
    const y = clamp(requestedY - shellRect.top, 8, shellRect.height - menuRect.height - 8);
    elements.bookContextMenu.style.left = `${x}px`;
    elements.bookContextMenu.style.top = `${y}px`;
  }

  function closeBookContextMenu() {
    elements.bookContextMenu.hidden = true;
    state.contextBookId = null;
  }

  function promptRename(bookId) {
    const book = books.find((item) => item.id === bookId);
    if (!book) return;
    openDialog({
      title: t("renameTitle"),
      message: t("renameMessage"),
      inputValue: book.title,
      confirmLabel: t("save"),
      onConfirm(value) {
        const title = value.trim();
        if (!title) return false;
        if (book.external && state.externalAdapter?.renameBook) {
          void state.externalAdapter.renameBook(book.id, title);
          return true;
        }
        book.title = title;
        renderShelf();
        showToast(t("renameSucceeded"));
        return true;
      },
    });
  }

  function promptRelocate(bookId) {
    const book = books.find((item) => item.id === bookId);
    if (!book) return;
    openDialog({
      title: t("relocateTitle"),
      message: t("relocateMessage", { title: book.title }),
      showInput: false,
      confirmLabel: t("relocate"),
      onConfirm() {
        if (book.external && state.externalAdapter?.relocateBook) {
          void state.externalAdapter.relocateBook(book.id);
          return true;
        }
        book.missing = false;
        book.lastOpened = Date.now();
        renderShelf();
        showToast(t("relocatedSucceeded"));
        return true;
      },
    });
  }

  function promptRemove(bookId) {
    const book = books.find((item) => item.id === bookId);
    if (!book) return;
    openDialog({
      title: t("removeTitle"),
      message: t("removeMessage", { title: book.title }),
      showInput: false,
      confirmLabel: t("remove"),
      onConfirm() {
        if (book.external && state.externalAdapter?.removeBook) {
          void state.externalAdapter.removeBook(book.id);
          return true;
        }
        books = books.filter((item) => item.id !== book.id);
        if (state.activeBookId === book.id) state.activeBookId = books[0]?.id || null;
        renderShelf();
        showToast(t("removedSucceeded"));
        return true;
      },
    });
  }

  function openDialog({
    title,
    message,
    inputValue = "",
    showInput = true,
    confirmLabel = t("confirm"),
    onConfirm,
  }) {
    closeBookContextMenu();
    elements.dialogTitle.textContent = title;
    elements.dialogMessage.textContent = message;
    elements.dialogInputWrap.hidden = !showInput;
    elements.dialogInput.value = inputValue;
    elements.dialogConfirm.textContent = confirmLabel;
    state.dialogConfirm = onConfirm;
    elements.modalBackdrop.hidden = false;
    requestAnimationFrame(() => {
      if (showInput) {
        elements.dialogInput.focus();
        elements.dialogInput.select();
      } else {
        elements.dialogConfirm.focus();
      }
    });
  }

  function closeDialog() {
    elements.modalBackdrop.hidden = true;
    state.dialogConfirm = null;
  }

  function confirmDialog() {
    if (typeof state.dialogConfirm !== "function") return;
    const shouldClose = state.dialogConfirm(elements.dialogInput.value);
    if (shouldClose !== false) closeDialog();
  }

  function addPrototypeBook({ openAfterAdd = false } = {}) {
    const book = state.prototypeAdapter?.createBook();
    if (!book) return null;
    books.push(book);
    renderShelf();
    showToast(t("demoBookAdded", { format: book.format, title: book.title }));
    if (openAfterAdd) openBook(book.id);
    return book;
  }

  function showToast(message) {
    elements.toast.textContent = message;
    elements.toast.classList.add("is-visible");
    window.clearTimeout(state.toastTimer);
    state.toastTimer = window.setTimeout(() => {
      elements.toast.classList.remove("is-visible");
    }, 1800);
  }

  function closeTransientUi() {
    hideReaderMenu();
    closeChapterPanel();
    closeBookContextMenu();
    if (!elements.modalBackdrop.hidden) closeDialog();
  }

  function bindEvents() {
    elements.backToShelf.addEventListener("click", () => {
      saveCurrentProgress();
      state.externalAdapter?.cancelLoad?.();
      closeTransientUi();
      showPage("shelf");
    });
    elements.addBookButton.addEventListener("click", () => {
      if (state.externalAdapter) state.externalAdapter.selectLocalBook(false);
      else addPrototypeBook();
    });
    elements.emptyAddButton.addEventListener("click", () => {
      if (state.externalAdapter) state.externalAdapter.selectLocalBook(false);
      else addPrototypeBook();
    });
    elements.chapterTrigger.addEventListener("click", openChapterPanel);
    elements.closeChapters.addEventListener("click", closeChapterPanel);
    elements.chapterScrim.addEventListener("click", closeChapterPanel);
    elements.readerMenuButton.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleReaderMenu();
    });
    elements.readerMenu.addEventListener("click", (event) => event.stopPropagation());
    elements.mockOpenFile.addEventListener("click", () => {
      hideReaderMenu();
      if (state.externalAdapter) state.externalAdapter.selectLocalBook(true);
      else addPrototypeBook({ openAfterAdd: true });
    });
    elements.fontSizeRange.addEventListener("input", () => {
      state.fontSize = Number(elements.fontSizeRange.value);
      applyReadingSettings();
      updateReadingState();
    });
    elements.lineHeightRange.addEventListener("input", () => {
      state.lineHeight = Number(elements.lineHeightRange.value);
      applyReadingSettings();
      updateReadingState();
    });
    elements.resetSettings.addEventListener("click", () => {
      state.fontSize = 18;
      state.lineHeight = 1.95;
      applyReadingSettings();
      updateReadingState();
    });
    elements.readingScroll.addEventListener("scroll", () => {
      if (state.scrollFrame !== null) return;
      state.scrollFrame = requestAnimationFrame(() => {
        state.scrollFrame = null;
        updateReadingState();
      });
    });
    elements.bookContextMenu.addEventListener("click", (event) => {
      const actionButton = event.target.closest("[data-action]");
      if (!actionButton || !state.contextBookId) return;
      const bookId = state.contextBookId;
      const action = actionButton.dataset.action;
      if (action === "rename") promptRename(bookId);
      if (action === "relocate") promptRelocate(bookId);
      if (action === "remove") promptRemove(bookId);
    });
    elements.dialogCancel.addEventListener("click", closeDialog);
    elements.dialogConfirm.addEventListener("click", confirmDialog);
    elements.dialogInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") confirmDialog();
    });
    elements.modalBackdrop.addEventListener("click", (event) => {
      if (event.target === elements.modalBackdrop) closeDialog();
    });
    document.addEventListener("click", (event) => {
      if (!event.target.closest("#readerMenu") && !event.target.closest("#readerMenuButton")) {
        hideReaderMenu();
      }
      if (!event.target.closest("#bookContextMenu") && !event.target.closest(".card-menu-button")) {
        closeBookContextMenu();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      if (!elements.modalBackdrop.hidden) closeDialog();
      else if (!elements.chapterPanel.hidden) closeChapterPanel();
      else {
        hideReaderMenu();
        closeBookContextMenu();
      }
    });
  }

  function initialize() {
    bindEvents();
    renderShelf();
    renderThemes();
    applyTheme(state.theme, false);
    applyReadingSettings();
    const book = activeBook();
    if (book) openBook(book.id);
    else showPage("shelf");
  }

  function registerExternalAdapter(adapter) {
    state.externalAdapter = adapter;
  }

  function registerPrototypeAdapter(adapter) {
    state.prototypeAdapter = adapter;
  }

  function bootstrapDemo() {
    const snapshot = state.prototypeAdapter?.bootstrap?.();
    if (!snapshot) return false;
    books = snapshot.books.map((book) => ({ ...book }));
    state.activeBookId = snapshot.activeBookId || books[0]?.id || null;
    renderShelf();
    const book = activeBook();
    if (book) openBook(book.id);
    else showPage("shelf");
    return true;
  }

  function upsertExternalBook(metadata, { openAfterAdd = false } = {}) {
    const existing = books.find((book) => book.id === metadata.book_id);
    const book = {
      id: metadata.book_id,
      title: metadata.title,
      format: metadata.format,
      progress:
        metadata.text_length > 0 ? metadata.char_position / metadata.text_length : 0,
      chapterIndex: metadata.chapter_index || 0,
      chapters: metadata.chapters || existing?.chapters || [],
      textLength: metadata.text_length ?? existing?.textLength ?? 0,
      charPosition: metadata.char_position ?? existing?.charPosition ?? 0,
      lastOpened: metadata.last_opened_at || existing?.lastOpened || 0,
      missing: metadata.missing === true,
      external: true,
      persisted: metadata.persisted === true,
    };
    if (existing) Object.assign(existing, book);
    else books.push(book);
    renderShelf();
    if (openAfterAdd) openBook(book.id);
    return book;
  }

  function updateExternalBook(bookId, patch) {
    const book = books.find((item) => item.id === bookId);
    if (!book) return null;
    Object.assign(book, patch);
    if (book.textLength > 0 && Number.isFinite(book.charPosition)) {
      book.progress = clamp(book.charPosition / book.textLength, 0, 1);
    }
    if (book.id === state.activeBookId) {
      const percentage = Math.round(book.progress * 100);
      elements.readerProgressFill.style.width = `${percentage}%`;
      elements.readerProgressText.textContent = `${percentage}%`;
      updateChapterHeader(book.chapterIndex);
    }
    return book;
  }

  function activateExternalBook(bookId) {
    const book = books.find((item) => item.id === bookId && item.external);
    if (!book) return null;
    state.activeBookId = bookId;
    state.currentPage = "book";
    showPage("book");
    return book;
  }

  function bootstrapPreview(snapshot) {
    if (!snapshot?.enabled) return false;
    books = (snapshot.books || []).map((metadata) => ({
      id: metadata.book_id,
      title: metadata.title,
      format: metadata.format,
      progress: Number(metadata.progress) || 0,
      chapterIndex: Number(metadata.chapter_index) || 0,
      chapterTitle: metadata.chapter_title || "",
      chapters: [],
      textLength: Number(metadata.text_length) || 0,
      charPosition: Number(metadata.char_position) || 0,
      lastOpened: metadata.last_opened_at || "",
      missing: metadata.missing === true,
      external: true,
      persisted: true,
    }));
    state.activeBookId = snapshot.active_book_id || null;
    state.currentPage = "shelf";
    applyTheme(snapshot.reading_theme || "classic", false);
    showPage("shelf");
    return true;
  }

  function removeExternalBook(bookId) {
    books = books.filter((book) => book.id !== bookId);
    if (state.activeBookId === bookId) state.activeBookId = null;
    renderShelf();
  }

  window.notebookPrototype = {
    activateExternalBook,
    activeBook,
    bootstrapDemo,
    bootstrapPreview,
    elements,
    getState: () => ({
      ...state,
      externalAdapter: Boolean(state.externalAdapter),
      prototypeAdapter: Boolean(state.prototypeAdapter),
    }),
    getBooks: () => books.map((book) => ({ ...book })),
    openBook,
    registerExternalAdapter,
    registerPrototypeAdapter,
    removeExternalBook,
    renderShelf,
    showPage,
    showToast,
    updateExternalBook,
    upsertExternalBook,
  };

  initialize();
})();
