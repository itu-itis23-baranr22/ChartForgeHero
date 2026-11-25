// A classic script beside the page's modules: when the editor has not started a moment after the page
// loaded (a module that failed to load or to run), it says what to do instead of leaving "Loading…".
"use strict";

window.addEventListener("load", () => {
  setTimeout(() => {
    if (window.chartgenDebug) return; // app.js ran
    const box = document.createElement("div");
    box.className = "boot-failed";
    box.setAttribute("role", "alert");
    const title = document.createElement("h1");
    title.textContent = "The editor did not start";
    const what = document.createElement("p");
    what.textContent = "Reload the page with Ctrl+Shift+R, which skips the copies the browser kept. If it still does not start, "
      + "press F12, open the Console tab and copy the red error: it says what went wrong.";
    box.append(title, what);
    document.body.prepend(box);
  }, 2000);
});
