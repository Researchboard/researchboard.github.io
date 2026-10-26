/* ResearchBoard blog: post filter + copy link */
(function () {
  "use strict";
  document.querySelectorAll("[data-filter]").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("[data-filter]").forEach((x) => x.classList.toggle("on", x === b));
    const f = b.dataset.filter;
    document.querySelectorAll(".post-card").forEach((c) => { c.hidden = f !== "all" && c.dataset.kind !== f; });
  }));
  document.querySelectorAll("[data-copy]").forEach((b) => b.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(b.dataset.copy); b.textContent = "Copied ✓"; }
    catch (_) { b.textContent = "Copy failed"; }
    setTimeout(() => { b.textContent = "Copy link"; }, 1800);
  }));
})();
