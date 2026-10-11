// Client-side search + filter (no network, works over file://).
const grid = document.getElementById("grid");
const q = document.getElementById("q");
const empty = document.getElementById("empty");
let active = "all";
const chips = [...document.querySelectorAll(".chip")];
function paintChips() { chips.forEach((c) => c.classList.toggle("on", c.dataset.f === active)); }
chips.forEach((c) => c.addEventListener("click", () => { active = c.dataset.f; paintChips(); render(); }));
q.addEventListener("input", render);
function card(i) {
  const lock = i.access === "accessible"
    ? '<span class="badge ok">✓ FREE</span>'
    : '<span class="badge lock">🔒 PRO</span>';
  const img = i.preview_image
    ? '<img class="thumb" src="' + i.preview_image + '" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">'
    : '<div class="thumb ph"><span>' + esc((i.type || "?").slice(0, 1).toUpperCase()) + '</span></div>';
  return '<a class="item" href="' + i.page + '">' +
    '<div class="num">#' + i.num + '</div>' + img +
    '<div class="item-top">' + lock + '<span class="tag">' + esc(i.category) + '</span></div>' +
    '<h3>' + esc(i.name) + '</h3>' +
    '<p class="muted">' + esc(i.type || "") + '</p></a>';
}
function esc(s) { return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
function render() {
  const term = q.value.trim().toLowerCase();
  const list = window.THREEUI_INDEX.filter((i) => {
    if (active === "accessible" && i.access !== "accessible") return false;
    if (active === "locked" && i.access !== "locked") return false;
    if (!["all", "accessible", "locked"].includes(active) && i.category !== active) return false;
    if (term && !(i.name + " " + i.slug + " " + i.category + " " + (i.type || "") + " #" + i.num + " " + i.num).toLowerCase().includes(term)) return false;
    return true;
  });
  grid.innerHTML = list.map(card).join("");
  empty.hidden = list.length > 0;
}
paintChips(); render();
