(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.NotebookCharPosition = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function clampInteger(value, minimum, maximum) {
    const numeric = Number.isFinite(Number(value)) ? Math.trunc(Number(value)) : minimum;
    return Math.min(maximum, Math.max(minimum, numeric));
  }

  function codePointLength(text) {
    let length = 0;
    for (const _symbol of String(text)) length += 1;
    return length;
  }

  function codePointToUtf16Offset(text, codePointOffset) {
    const value = String(text);
    const target = clampInteger(codePointOffset, 0, codePointLength(value));
    let codePoints = 0;
    let utf16 = 0;
    for (const symbol of value) {
      if (codePoints >= target) break;
      utf16 += symbol.length;
      codePoints += 1;
    }
    return utf16;
  }

  function utf16ToCodePointOffset(text, utf16Offset) {
    const value = String(text);
    const target = clampInteger(utf16Offset, 0, value.length);
    let codePoints = 0;
    let utf16 = 0;
    for (const symbol of value) {
      const next = utf16 + symbol.length;
      // A DOM offset in the middle of a surrogate pair is clamped backward.
      if (next > target) break;
      utf16 = next;
      codePoints += 1;
      if (utf16 === target) break;
    }
    return codePoints;
  }

  function roundTrip(text, codePointOffset) {
    const utf16 = codePointToUtf16Offset(text, codePointOffset);
    return utf16ToCodePointOffset(text, utf16);
  }

  return {
    codePointLength,
    codePointToUtf16Offset,
    roundTrip,
    utf16ToCodePointOffset,
  };
});
