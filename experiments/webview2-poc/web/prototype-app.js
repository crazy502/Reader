(function () {
  "use strict";

  const t = (key, values) => window.notebookPocI18n.t(key, values);
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
  const demoBooks = [
    { id: "book-shenming-game", title: "神明游戏", format: "TXT", progress: 0.63, chapterIndex: 14, lastOpened: 6, missing: false },
    { id: "book-three-body", title: "三体", format: "EPUB", progress: 0.28, chapterIndex: 6, lastOpened: 4, missing: false },
    { id: "book-long-title", title: "在漫长的季节里等待一场迟来的雪", format: "EPUB", progress: 0.12, chapterIndex: 2, lastOpened: 3, missing: false },
    { id: "book-night-voyage", title: "夜航船", format: "TXT", progress: 0.84, chapterIndex: 20, lastOpened: 8, missing: false },
    { id: "book-human-world", title: "人间草木", format: "EPUB", progress: 0.47, chapterIndex: 10, lastOpened: 5, missing: false },
    { id: "book-lost-file", title: "被遗忘的海岸与最后一座灯塔", format: "TXT", progress: 0.36, chapterIndex: 8, lastOpened: 2, missing: true },
  ];
  let addedCount = 0;

  function toChineseNumber(number) {
    const digits = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"];
    if (number < 10) return digits[number];
    if (number === 10) return "十";
    if (number < 20) return `十${digits[number - 10]}`;
    const tens = Math.floor(number / 10);
    const ones = number % 10;
    return `${digits[tens]}十${ones ? digits[ones] : ""}`;
  }

  function chapterLabel(index) {
    const bounded = Math.min(chapterTitles.length - 1, Math.max(0, Number(index) || 0));
    return `第${toChineseNumber(bounded + 1)}章 · ${chapterTitles[bounded]}`;
  }

  function renderArticle(book, article) {
    article.replaceChildren();
    const kicker = document.createElement("p");
    kicker.className = "novel-kicker";
    kicker.textContent = "NOTEBOOK READING";
    const title = document.createElement("h1");
    title.className = "novel-title";
    title.textContent = book.title;
    article.append(kicker, title);

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
      article.appendChild(section);
    });
  }

  function currentChapterIndex(elements) {
    const sections = [...elements.readingArticle.querySelectorAll(".chapter-section")];
    if (!sections.length) return 0;
    const threshold = elements.readingScroll.scrollTop + 100;
    let selected = 0;
    sections.forEach((section, index) => {
      if (section.offsetTop <= threshold) selected = index;
    });
    return selected;
  }

  function renderChapterList(book, container, jumpToChapter) {
    container.replaceChildren();
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
      container.appendChild(item);
    });
  }

  function jumpToChapter(index, elements) {
    const target = elements.readingArticle.querySelector(`[data-chapter-index="${index}"]`);
    if (!target) return;
    elements.readingScroll.scrollTop = Math.max(0, target.offsetTop - 18);
  }

  function createBook() {
    addedCount += 1;
    return {
      id: `simulated-added-book-${addedCount}`,
      title: addedCount === 1 ? t("demoBookFirst") : t("demoBookNumber", { index: addedCount }),
      format: addedCount % 2 ? "EPUB" : "TXT",
      progress: 0,
      chapterIndex: 0,
      lastOpened: Date.now(),
      missing: false,
    };
  }

  window.notebookPrototype.registerPrototypeAdapter({
    bootstrap: () => ({
      books: demoBooks.map((book) => ({ ...book })),
      activeBookId: "book-night-voyage",
    }),
    chapterLabel,
    createBook,
    currentChapterIndex,
    jumpToChapter,
    renderArticle,
    renderChapterList,
  });
})();
