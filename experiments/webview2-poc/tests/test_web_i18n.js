"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const messagesSource = fs.readFileSync(
  path.join(root, "web", "src", "i18n", "messages.js"),
  "utf8",
);
const checkedFiles = [
  path.join(root, "web", "index.html"),
  path.join(root, "web", "app.js"),
  path.join(root, "web", "prototype-app.js"),
  path.join(root, "web", "poc.js"),
  path.join(root, "web", "reader-engine.js"),
  path.join(root, "web", "reader-benchmark.js"),
];

function catalogueFor(language) {
  const context = {
    document: { documentElement: { lang: language === "en-US" ? "en" : "zh-CN" } },
    window: {},
  };
  vm.runInNewContext(messagesSource, context, { filename: "messages.js" });
  return context.window.notebookPocI18n;
}

function referencedKeys() {
  const keys = new Set();
  for (const file of checkedFiles) {
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
  test(`${language} contains every referenced UI message`, () => {
    const i18n = catalogueFor(language);
    const missing = referencedKeys().filter((key) => i18n.t(key) === key);
    assert.deepEqual(missing, []);
  });
}
