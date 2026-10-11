"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const mapping = require("../web/char-position.js");

const samples = [
  "普通中文\n空格  缩进",
  "A🙂B",
  "音乐𝄞结束",
  "扩展汉字𠀀与 emoji 🚉",
  "\r\n\t　混合空白",
];

test("Python code-point offsets round-trip through DOM UTF-16 offsets", () => {
  for (const sample of samples) {
    const length = [...sample].length;
    for (let position = 0; position <= length; position += 1) {
      const utf16 = mapping.codePointToUtf16Offset(sample, position);
      assert.equal(mapping.utf16ToCodePointOffset(sample, utf16), position);
      assert.equal(mapping.roundTrip(sample, position), position);
    }
  }
});

test("UTF-16 offsets inside surrogate pairs clamp backward", () => {
  const sample = "前🙂后";
  assert.equal(sample.length, 4);
  assert.equal(mapping.utf16ToCodePointOffset(sample, 1), 1);
  assert.equal(mapping.utf16ToCodePointOffset(sample, 2), 1);
  assert.equal(mapping.utf16ToCodePointOffset(sample, 3), 2);
});

test("out-of-range offsets are clamped", () => {
  assert.equal(mapping.codePointToUtf16Offset("🙂", -10), 0);
  assert.equal(mapping.codePointToUtf16Offset("🙂", 20), 2);
  assert.equal(mapping.utf16ToCodePointOffset("🙂", -10), 0);
  assert.equal(mapping.utf16ToCodePointOffset("🙂", 20), 1);
});
