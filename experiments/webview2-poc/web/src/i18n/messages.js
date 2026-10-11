(function () {
  "use strict";

  const catalogues = {
    "zh-CN": {
      renderStrategy: "渲染策略",
      strategyWhole: "A · 整本段落 DOM",
      strategyChunked: "B · 章节块分批 DOM",
      savePosition: "保存位置",
      restorePosition: "恢复位置",
      performanceTitle: "性能数据",
      performanceIdle: "尚未加载真实小说",
      loadingNovel: "正在解析并载入小说…",
      buildingDom: "正在构建正文…",
      loadedNovel: "已载入《{title}》",
      addedNovel: "已加入实验书架：《{title}》",
      cancelled: "已取消选择文件",
      loadFailed: "打开失败：{message}",
      bridgeUnavailable: "Python bridge 尚未就绪",
      positionSaved: "已保存字符位置 {position}",
      positionRestored: "已恢复到字符位置 {position}",
      noRealBook: "请先打开一部真实 TXT 或 EPUB",
      benchmarkRunning: "正在执行 {size} 字基准…",
      benchmarkDone: "性能基准完成",
      chapterNumber: "{index}",
      unknownError: "未知错误",
      payloadNonContiguous: "渲染数据的字符区间不连续",
      payloadIncomplete: "渲染数据没有完整覆盖 Novel.text",
      renderSuperseded: "本次渲染已被新的打开操作替代",
    },
    "en-US": {
      renderStrategy: "Rendering strategy",
      strategyWhole: "A · whole-book paragraph DOM",
      strategyChunked: "B · incremental chapter blocks",
      savePosition: "Save position",
      restorePosition: "Restore position",
      performanceTitle: "Performance",
      performanceIdle: "No real novel loaded",
      loadingNovel: "Parsing and loading novel…",
      buildingDom: "Building the document…",
      loadedNovel: "Loaded “{title}”",
      addedNovel: "Added to the experiment shelf: “{title}”",
      cancelled: "File selection cancelled",
      loadFailed: "Open failed: {message}",
      bridgeUnavailable: "Python bridge is not ready",
      positionSaved: "Saved character position {position}",
      positionRestored: "Restored character position {position}",
      noRealBook: "Open a real TXT or EPUB first",
      benchmarkRunning: "Benchmarking {size} characters…",
      benchmarkDone: "Benchmark complete",
      chapterNumber: "{index}",
      unknownError: "Unknown error",
      payloadNonContiguous: "Render payload ranges are not contiguous",
      payloadIncomplete: "Render payload does not fully cover Novel.text",
      renderSuperseded: "This render was superseded by a newer open request",
    },
  };

  const requested = document.documentElement.lang === "en" ? "en-US" : "zh-CN";

  function t(key, values = {}) {
    const template = catalogues[requested][key] || catalogues["zh-CN"][key] || key;
    return template.replace(/\{(\w+)\}/g, (_match, name) => String(values[name] ?? ""));
  }

  window.notebookPocI18n = { language: requested, t };
})();
