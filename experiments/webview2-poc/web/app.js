(function () {
  "use strict";

  const coverPalette = [
    "#DDD2BD",
    "#D5E1D0",
    "#D7E2EA",
    "#E8D5D5",
    "#E9DFC1",
    "#DDD6E8",
  ];

  const themes = [
    { id: "classic", name: "经典", color: "#F6F1E7" },
    { id: "white", name: "纯白", color: "#FFFFFF" },
    { id: "eye_care", name: "护眼绿", color: "#EAF4DF" },
    { id: "parchment", name: "羊皮纸", color: "#F3E7C9" },
    { id: "light_gray", name: "浅灰", color: "#F3F3F3" },
  ];

  const chapterTitles = [
    "雨停之前",
    "旧城来信",
    "没有名字的车站",
    "微光穿过长街",
    "地图之外",
    "凌晨四点的灯",
    "一封迟到的回信",
    "沿河而行",
    "沉默的钟声",
    "远山如黛",
    "月台上的陌生人",
    "冬日回声",
    "一场缓慢的告别",
    "风从北方来",
    "深夜书房",
    "星光落在屋檐",
    "旅人的旧梦",
    "长路将尽",
    "门后的世界",
    "黎明前的约定",
    "神明降临",
    "被遗忘的名字",
    "归途",
    "明日仍会到来",
  ];

  const paragraphBank = [
    "城里的雨下了整整一个星期。沿街的梧桐被洗得发亮，枝叶低垂，偶尔有水珠从叶尖落下，在青石路上碎成极轻的一声。林默把窗推开一条缝，潮湿的风带着泥土和旧木头的气味钻进屋里。",
    "他已经很久没有这样安静地坐着了。桌上那封信被折了三次，纸边微微起毛，像是被人反复打开又合上。信里没有日期，也没有署名，只有一句话：请在第一班列车到站以前，回到我们曾经告别的地方。",
    "记忆并不总按时间排列。它更像一间光线昏暗的仓库，某个寻常的声音、气味或者动作，都可能碰落一只多年未曾打开的纸箱。尘埃散去之后，里面的东西仍保持着离开时的模样。",
    "河水从城南绕过，向更远的平原流去。小时候，他们常坐在堤岸上猜测河的尽头。有人说那里是海，有人说是另一座一模一样的城市，住着一群做着相反选择的人。",
    "夜色落下来时，街边的店铺一盏接一盏亮起灯。玻璃窗上浮着薄薄的雾，人影在里面缓慢移动。林默穿过人群，忽然觉得每个人都怀揣着一段无人知晓的故事，只是彼此礼貌地保持沉默。",
    "车站的钟比城里的时间慢了七分钟。候车室里只有几排旧木椅，一个戴灰帽子的老人正在读报。纸张翻动的声音很轻，却让空旷的大厅显得更加安静。",
    "广播响过两次，声音因为年代久远而有些失真。站台尽头亮起一束白光，铁轨先是轻轻震动，随后传来列车穿过夜雾的低鸣。那一刻，他终于明白自己一直在等待什么。",
    "她从第三节车厢下来，手里仍提着那只深蓝色的旧箱子。许多年过去，她的步子比从前慢了一些，目光却没有改变。她站在人群之外，像从一张褪色的照片里走进现实。",
    "两个人隔着不远的距离，没有立刻说话。有些重逢需要先让时间从中间经过，让那些准备了太久的句子失去锋利的边缘，才能被真正说出口。",
    "天快亮时，雨终于停了。东方的云层露出一线浅金色，屋顶和树梢都被照亮。城市仍旧是原来的城市，但他们知道，有些事情已经悄悄改变。",
    "后来他常想，如果那封信晚到一天，或者他在路口多停留几分钟，故事会不会走向另一个方向。可生活从不给人观看另一种结局的机会，它只留下眼前这条路，让人继续向前。",
    "他们沿着河岸往回走，谈起这些年读过的书、住过的房间，以及一些已经记不起名字的人。晨风吹动她的衣角，河面泛起细密的光，像无数未写完的句子。",
  ];

  let books = [
    {
      id: "book-shenming-game",
      title: "神明游戏",
      format: "TXT",
      progress: 0.63,
      chapterIndex: 14,
      lastOpened: 6,
      missing: false,
    },
    {
      id: "book-three-body",
      title: "三体",
      format: "EPUB",
      progress: 0.28,
      chapterIndex: 6,
      lastOpened: 4,
      missing: false,
    },
    {
      id: "book-long-title",
      title: "在漫长的季节里等待一场迟来的雪",
      format: "EPUB",
      progress: 0.12,
      chapterIndex: 2,
      lastOpened: 3,
      missing: false,
    },
    {
      id: "book-night-voyage",
      title: "夜航船",
      format: "TXT",
      progress: 0.84,
      chapterIndex: 20,
      lastOpened: 8,
      missing: false,
    },
    {
      id: "book-human-world",
      title: "人间草木",
      format: "EPUB",
      progress: 0.47,
      chapterIndex: 10,
      lastOpened: 5,
      missing: false,
    },
    {
      id: "book-lost-file",
      title: "被遗忘的海岸与最后一座灯塔",
      format: "TXT",
      progress: 0.36,
      chapterIndex: 8,
      lastOpened: 2,
      missing: true,
    },
  ];

  const state = {
    activeBookId: "book-night-voyage",
    currentPage: null,
    theme: "classic",
    fontSize: 18,
    lineHeight: 1.95,
    contextBookId: null,
    dialogConfirm: null,
    toastTimer: null,
    scrollFrame: null,
    addedCount: 0,
    externalAdapter: null,
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

  function chapterLabel(index) {
    return `第${toChineseNumber(index + 1)}章 · ${chapterTitles[index]}`;
  }

  function displayChapterLabel(book, index) {
    if (book?.external && Array.isArray(book.chapters) && book.chapters.length) {
      const chapter = book.chapters[clamp(index, 0, book.chapters.length - 1)];
      return chapter.title;
    }
    return chapterLabel(clamp(index, 0, chapterTitles.length - 1));
  }

  function toChineseNumber(number) {
    const digits = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"];
    if (number < 10) return digits[number];
    if (number === 10) return "十";
    if (number < 20) return `十${digits[number - 10]}`;
    const tens = Math.floor(number / 10);
    const ones = number % 10;
    return `${digits[tens]}十${ones ? digits[ones] : ""}`;
  }

  function renderShelf() {
    elements.bookGrid.replaceChildren();
    const orderedBooks = [...books].sort((left, right) => right.lastOpened - left.lastOpened);

    orderedBooks.forEach((book) => {
      const card = document.createElement("article");
      card.className = `book-card${book.id === state.activeBookId ? " is-current" : ""}`;
      card.dataset.bookId = book.id;

      const cover = document.createElement("div");
      cover.className = "book-cover";
      cover.style.backgroundColor = stableColor(book.id);
      cover.tabIndex = 0;
      cover.setAttribute("role", "button");
      cover.setAttribute("aria-label", `${book.title}，阅读进度 ${Math.round(book.progress * 100)}%`);

      if (book.id === state.activeBookId) {
        const marker = document.createElement("span");
        marker.className = "current-marker";
        marker.textContent = "正在阅读";
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
      menuButton.setAttribute("aria-label", `${book.title} 管理菜单`);
      menuButton.addEventListener("click", (event) => {
        event.stopPropagation();
        const rect = menuButton.getBoundingClientRect();
        openBookContextMenu(book.id, rect.right - 150, rect.bottom + 2);
      });
      cover.appendChild(menuButton);

      if (book.missing) {
        const missing = document.createElement("span");
        missing.className = "missing-badge";
        missing.textContent = "⚠ 文件丢失";
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
      chapter.textContent = `第${book.chapterIndex + 1}章`;
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

  function renderArticle(book) {
    elements.readingArticle.replaceChildren();

    const kicker = document.createElement("p");
    kicker.className = "novel-kicker";
    kicker.textContent = "NOTEBOOK READING";
    const title = document.createElement("h1");
    title.className = "novel-title";
    title.textContent = book.title;
    elements.readingArticle.append(kicker, title);

    chapterTitles.forEach((chapterTitle, chapterIndex) => {
      const section = document.createElement("section");
      section.className = "chapter-section";
      section.dataset.chapterIndex = String(chapterIndex);
      section.id = `chapter-${chapterIndex}`;
      const heading = document.createElement("h2");
      heading.textContent = chapterLabel(chapterIndex);
      section.appendChild(heading);

      for (let paragraphIndex = 0; paragraphIndex < 4; paragraphIndex += 1) {
        const paragraph = document.createElement("p");
        const bankIndex = (chapterIndex * 3 + paragraphIndex) % paragraphBank.length;
        paragraph.textContent = paragraphBank[bankIndex];
        section.appendChild(paragraph);
      }
      elements.readingArticle.appendChild(section);
    });
  }

  function openBook(bookId) {
    const nextBook = books.find((book) => book.id === bookId);
    if (!nextBook) return;
    if (nextBook.missing) {
      promptRelocate(nextBook.id);
      return;
    }

    if (state.currentPage === "book") saveCurrentProgress();
    state.activeBookId = nextBook.id;
    nextBook.lastOpened = Date.now();
    state.currentPage = "book";
    closeTransientUi();
    if (nextBook.external && state.externalAdapter) {
      showPage("book");
      updateChapterHeader(nextBook.chapterIndex);
      Promise.resolve(state.externalAdapter.openBook(nextBook)).catch((error) => {
        state.externalAdapter.reportError?.(error);
      });
      return;
    }
    renderArticle(nextBook);
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
    const sections = [...elements.readingArticle.querySelectorAll(".chapter-section")];
    if (!sections.length) return 0;
    const threshold = elements.readingScroll.scrollTop + 100;
    let selected = 0;
    sections.forEach((section, index) => {
      if (section.offsetTop <= threshold) selected = index;
    });
    return selected;
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
    elements.chapterList.replaceChildren();
    chapterTitles.forEach((title, index) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = `chapter-item${index === book.chapterIndex ? " is-current" : ""}`;
      item.dataset.chapterIndex = String(index);
      const number = document.createElement("span");
      number.className = "chapter-number";
      number.textContent = String(index + 1).padStart(2, "0");
      const name = document.createElement("span");
      name.className = "chapter-name";
      name.textContent = `第${toChineseNumber(index + 1)}章 · ${title}`;
      item.append(number, name);
      item.addEventListener("click", () => jumpToChapter(index));
      elements.chapterList.appendChild(item);
    });
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
    const target = elements.readingArticle.querySelector(`[data-chapter-index="${index}"]`);
    if (!book || !target) return;
    book.chapterIndex = index;
    elements.readingScroll.scrollTop = Math.max(0, target.offsetTop - 18);
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

  function applyTheme(themeId) {
    state.theme = themes.some((theme) => theme.id === themeId) ? themeId : "classic";
    elements.bookPage.dataset.theme = state.theme;
    renderThemes();
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
      title: "修改显示书名",
      message: "只修改书架中的显示名称，不会更改磁盘上的原文件名。",
      inputValue: book.title,
      confirmLabel: "保存",
      onConfirm(value) {
        const title = value.trim();
        if (!title) return false;
        book.title = title;
        renderShelf();
        showToast("显示书名已更新");
        return true;
      },
    });
  }

  function promptRelocate(bookId) {
    const book = books.find((item) => item.id === bookId);
    if (!book) return;
    openDialog({
      title: "找不到原文件",
      message: `“${book.title}”的原文件可能已被移动或删除。此原型会模拟重新定位成功。`,
      showInput: false,
      confirmLabel: "重新定位",
      onConfirm() {
        book.missing = false;
        book.lastOpened = Date.now();
        renderShelf();
        showToast("已模拟重新定位文件");
        return true;
      },
    });
  }

  function promptRemove(bookId) {
    const book = books.find((item) => item.id === bookId);
    if (!book) return;
    openDialog({
      title: "从书架移除",
      message: `只移除“${book.title}”的书架记录，不会删除磁盘上的原文件。`,
      showInput: false,
      confirmLabel: "移除",
      onConfirm() {
        books = books.filter((item) => item.id !== book.id);
        if (state.activeBookId === book.id) state.activeBookId = books[0]?.id || null;
        renderShelf();
        showToast("已从书架移除");
        return true;
      },
    });
  }

  function openDialog({
    title,
    message,
    inputValue = "",
    showInput = true,
    confirmLabel = "确认",
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

  function addSimulatedBook({ openAfterAdd = false } = {}) {
    state.addedCount += 1;
    const book = {
      id: `simulated-added-book-${state.addedCount}`,
      title: state.addedCount === 1 ? "新加入的远方来信" : `新加入的书 ${state.addedCount}`,
      format: state.addedCount % 2 ? "EPUB" : "TXT",
      progress: 0,
      chapterIndex: 0,
      lastOpened: Date.now(),
      missing: false,
    };
    books.push(book);
    renderShelf();
    showToast(`已模拟添加 ${book.format}：《${book.title}》`);
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
      closeTransientUi();
      showPage("shelf");
    });
    elements.addBookButton.addEventListener("click", () => {
      if (state.externalAdapter) state.externalAdapter.selectLocalBook(false);
      else addSimulatedBook();
    });
    elements.emptyAddButton.addEventListener("click", () => {
      if (state.externalAdapter) state.externalAdapter.selectLocalBook(false);
      else addSimulatedBook();
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
      else addSimulatedBook({ openAfterAdd: true });
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
    applyTheme(state.theme);
    applyReadingSettings();
    const book = activeBook();
    if (book) openBook(book.id);
    else showPage("shelf");
  }

  function registerExternalAdapter(adapter) {
    state.externalAdapter = adapter;
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
      chapters: metadata.chapters || [],
      textLength: metadata.text_length || 0,
      charPosition: metadata.char_position || 0,
      lastOpened: Date.now(),
      missing: false,
      external: true,
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

  window.notebookPrototype = {
    activateExternalBook,
    activeBook,
    elements,
    getState: () => ({ ...state, externalAdapter: Boolean(state.externalAdapter) }),
    openBook,
    registerExternalAdapter,
    renderShelf,
    showPage,
    showToast,
    updateExternalBook,
    upsertExternalBook,
  };

  initialize();
})();
