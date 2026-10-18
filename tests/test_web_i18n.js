"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const webRoot = path.resolve(__dirname, "..", "reader", "webview", "web");
const checkedFiles = ["index.html", "app.js", "bridge.js", "reader-engine.js"]
  .map((name) => path.join(webRoot, name));

function catalogueFor(source, language) {
  const context = {
    document: { documentElement: { lang: language === "en-US" ? "en" : "zh-CN" } },
    window: {},
  };
  vm.runInNewContext(source, context, { filename: "messages.js" });
  return context.window.notebookI18n;
}

function referencedKeys(files) {
  const keys = new Set();
  for (const file of files) {
    const source = fs.readFileSync(file, "utf8");
    for (const pattern of [/data-i18n(?:-aria)?="([^"]+)"/g, /\bt\("([^"]+)"/g]) {
      for (const match of source.matchAll(pattern)) keys.add(match[1]);
    }
  }
  return [...keys].sort();
}

for (const language of ["zh-CN", "en-US"]) {
  test(`${language} contains every referenced UI message`, () => {
    const source = fs.readFileSync(path.join(webRoot, "i18n", "messages.js"), "utf8");
    const i18n = catalogueFor(source, language);
    const missing = referencedKeys(checkedFiles).filter((key) => i18n.t(key) === key);
    assert.deepEqual(missing, []);
  });
}
