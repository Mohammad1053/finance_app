// Resolve the saved theme ("light", "dark" or "system") to a concrete mode.
// It runs in <head>, before the page is painted, so there is no flash of the wrong theme.
(function () {
  var root = document.documentElement;
  var theme = root.dataset.theme || "light";
  var query = window.matchMedia("(prefers-color-scheme: dark)");

  function apply() {
    var dark = theme === "dark" || (theme === "system" && query.matches);
    root.dataset.mode = dark ? "dark" : "light";
  }

  apply();
  // In "system" mode, follow the operating system live
  if (theme === "system") query.addEventListener("change", apply);
})();