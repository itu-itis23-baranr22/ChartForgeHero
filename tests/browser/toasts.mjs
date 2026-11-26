// Reading the editor's notifications (toast.js) in the browser scripts: what a box says and where it sits.

/** The notification of one subject ("save", "copy", ...), as the page shows it, or null when there is none. */
export async function toastOf(page, channel) {
  const box = page.locator(`.toasts .toast[data-channel="${channel}"]:not(.out)`);
  if (!(await box.count())) return null;
  return box.evaluate((el) => {
    const text = (selector) => {
      const found = el.querySelector(selector);
      return found ? found.textContent : null;
    };
    const rect = (node) => {
      const r = node.getBoundingClientRect();
      return { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
    };
    const overlaps = (selector) => {
      const other = document.querySelector(selector);
      if (!other) return false;
      const a = el.getBoundingClientRect();
      const b = other.getBoundingClientRect();
      return a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
    };
    const style = (selector) => {
      const found = el.querySelector(selector);
      return found ? Number.parseFloat(getComputedStyle(found).fontSize) : null;
    };
    const r = rect(el);
    return {
      tone: ["success", "warning", "error"].find((t) => el.classList.contains(t)) || null,
      role: el.getAttribute("role"),
      icon: el.querySelector(".mark svg") ? el.querySelector(".mark svg").getAttribute("aria-label") : null,
      title: text(".title"),
      text: text(".text"),
      pathLabel: text(".plabel"),
      pathShown: text(".path code"),
      path: el.querySelector(".path code") ? el.querySelector(".path code").title : null,
      actions: [...el.querySelectorAll(".acts button")].map((b) => b.textContent),
      closable: Boolean(el.querySelector("button.close")),
      titlePx: style(".title"),
      textPx: style(".text"),
      inView: r.left >= 0 && r.top >= 0 && r.right <= innerWidth && r.bottom <= innerHeight,
      overProblems: overlaps("aside.right"),
      overTransport: overlaps("footer.bot"),
      overHeader: overlaps("header.top"),
      width: Math.round(r.right - r.left),
    };
  });
}

/** Waits for the notification of a subject to be gone (closed, or gone by itself). */
export async function toastGone(page, channel, timeout = 5000) {
  await page.locator(`.toasts .toast[data-channel="${channel}"]`).waitFor({ state: "detached", timeout });
}
