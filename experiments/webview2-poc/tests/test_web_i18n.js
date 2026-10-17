"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const checkedFiles = [
  path.join(root, "web", "index.html"),
  path.join(root, "web", "app.js"),
  path.join(root, "web", "prototype-app.js"),
  path.join(root, "web", "poc.js"),
  path.join(root, "web", "reader-engine.js"),
  path.join(root, "web", "reader-benchmark.js"),
];

function catalogueFor(source, language) {
  const context = {
    document: { documentElement: { lang: language === "en-US" ? "en" : "zh-CN" } },
    window: {},
  };
  vm.runInNewContext(source, context, { filename: "messages.js" });
  return context.window.notebookPocI18n;
}

function referencedKeys(files) {
  const keys = new Set();
  for (const file of files) {
    const source = fs.readFileSync(file, "utf8");
    for (const pattern of [
      /data-poc-i18n(?:-aria)?="([^"]+)"/g,
      /\bt\("([^"]+)"/g,
    ]) {
      for (const match of source.matchAll(pattern)) keys.add(match[1]);
    }
  }
  return [...keys].sort();
}

for (const language of ["zh-CN", "en-US"]) {
  test(`experiment ${language} contains every referenced UI message`, () => {
    const source = fs.readFileSync(
      path.join(root, "web", "src", "i18n", "messages.js"),
      "utf8",
    );
    const i18n = catalogueFor(source, language);
    const missing = referencedKeys(checkedFiles).filter((key) => i18n.t(key) === key);
    assert.deepEqual(missing, []);
  });

  test(`formal WebView2 ${language} contains every referenced UI message`, () => {
    const formalRoot = path.resolve(root, "..", "..", "reader", "webview", "web");
    const source = fs.readFileSync(
      path.join(formalRoot, "i18n", "messages.js"),
      "utf8",
    );
    const formalFiles = [
      path.join(formalRoot, "index.html"),
      path.join(formalRoot, "app.js"),
      path.join(formalRoot, "bridge.js"),
      path.join(formalRoot, "reader-engine.js"),
    ];
    const i18n = catalogueFor(source, language);
    const missing = referencedKeys(formalFiles).filter((key) => i18n.t(key) === key);
    assert.deepEqual(missing, []);
  });
}
