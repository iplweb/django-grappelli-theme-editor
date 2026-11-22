// Keeps --gte-header-height in sync with Grappelli's fixed header, so a
// theme that changes the top bar's height can offset the content correctly.
(function () {
  "use strict";
  function track() {
    var header = document.getElementById("grp-header");
    if (!header) return;
    var root = document.documentElement;
    var update = function () {
      root.style.setProperty("--gte-header-height", header.offsetHeight + "px");
    };
    update();
    if (window.ResizeObserver) new ResizeObserver(update).observe(header);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", track);
  } else {
    track();
  }
})();
