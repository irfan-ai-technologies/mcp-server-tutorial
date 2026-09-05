/* Theme toggle. Three states: system (no attribute), light, dark.
   Deliberately tiny — a chapter must work with JavaScript disabled. */
(function () {
  var KEY = "mcp-book-theme";
  var root = document.documentElement;

  try {
    var saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") root.setAttribute("data-theme", saved);
  } catch (e) { /* private mode, file://, blocked storage — ignore */ }

  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-theme-toggle]");
    if (!btn) return;

    var current = root.getAttribute("data-theme");
    var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    var next;

    if (!current) next = prefersDark ? "light" : "dark";
    else if (current === "dark") next = "light";
    else next = "dark";

    root.setAttribute("data-theme", next);
    try { localStorage.setItem(KEY, next); } catch (e) { /* ignore */ }
  });
})();
