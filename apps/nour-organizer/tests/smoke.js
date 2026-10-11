const assert = require("assert");
const { categorizeFile, groupDuplicatesBySize, formatBytes } = require("../lib/core");

assert.strictEqual(categorizeFile("a.jpg"), "Images");
assert.strictEqual(categorizeFile("b.MP4"), "Videos");
assert.strictEqual(categorizeFile("c.pdf"), "Documents");
assert.strictEqual(categorizeFile("d.exe"), "Programs");
assert.strictEqual(categorizeFile("e.zip"), "Archives");
assert.strictEqual(categorizeFile("f.unknown"), "Others");

const groups = groupDuplicatesBySize([
  { path: "a", size: 10 },
  { path: "b", size: 10 },
  { path: "c", size: 5 },
]);
assert.strictEqual(groups.length, 1);
assert.strictEqual(groups[0].length, 2);
assert.strictEqual(formatBytes(0), "0 B");
assert.ok(formatBytes(1536).includes("KB"));

console.log("smoke OK: categorize + duplicates + formatBytes");
