// Notifications (E.4, owner 2026-11-26): what a save or a copy to the game did, and why something was refused,
// as boxes over the lower right of the timeline. A success goes by itself after a few seconds, but not while the
// pointer or the focus is on it; a warning or an error stays until it is closed or one of its actions is used.
// One box per subject (channel): a new message on the same subject takes the old one's place, so they never pile
// up. The small facts of every edit ("Also changed: Hard 1 note") stay in the tool row's status line.

export const TONES = ["success", "warning", "error"];
const ICON = { success: "done", warning: "warn", error: "alert" };
const WORD = { success: "Done", warning: "Warning", error: "Error" };

/** The notifications without the page: what is shown, in which order, and when a success goes. */
export class Toasts {
  constructor({ setTimer = (run, ms) => setTimeout(run, ms), clearTimer = (timer) => clearTimeout(timer), now = () => Date.now() } = {}) {
    this.items = [];
    /** How long a success stays (ms); one with a path to copy stays longer. Tests shorten them. */
    this.durations = { success: 5000, path: 8000 };
    this.clock = { setTimer, clearTimer, now };
    this.listeners = new Set();
    this.nextId = 1;
  }

  /**
   * Shows `{ channel, tone, title, text?, pathLabel?, path?, pathShown?, actions? }` and returns it. `path` is what
   * "Copy path" copies, `pathShown` what is written (a shorter form of the same path); an action is
   * `{ label, run, primary? }` and closes the notification when used.
   */
  show(spec) {
    if (!TONES.includes(spec.tone)) throw new Error(`unknown tone: ${spec.tone}`);
    if (!spec.title) throw new Error("a notification needs a title");
    const channel = spec.channel || "general";
    const old = this.items.find((t) => t.channel === channel);
    const item = {
      id: this.nextId++, channel, tone: spec.tone, title: spec.title, text: spec.text || "",
      pathLabel: spec.pathLabel || "", path: spec.path || null, pathShown: spec.pathShown || spec.path || null,
      actions: spec.actions || [], replaces: old ? old.id : null,
      remaining: null, deadline: null, timer: null, paused: false,
    };
    if (item.tone === "success") item.remaining = item.path ? this.durations.path : this.durations.success;
    if (old) {
      this._stop(old);
      this.items[this.items.indexOf(old)] = item; // in the old one's place: nothing below it moves
    } else {
      this.items.push(item);
    }
    this._start(item);
    this._changed();
    return item;
  }

  find(id) {
    return this.items.find((t) => t.id === id) || null;
  }

  dismiss(id) {
    const item = this.find(id);
    if (!item) return;
    this._stop(item);
    this.items.splice(this.items.indexOf(item), 1);
    this._changed();
  }

  /** Closes every notification: another song or the song list was opened. */
  clear() {
    if (!this.items.length) return;
    for (const item of this.items) this._stop(item);
    this.items = [];
    this._changed();
  }

  /** The pointer or the focus is on it: a success waits. */
  pause(id) {
    const item = this.find(id);
    if (!item || item.remaining === null || item.paused) return;
    this._stop(item);
    item.remaining = Math.max(0, item.deadline - this.clock.now());
    item.paused = true;
  }

  /** The pointer and the focus left: a success goes after what was left of its time (at least a second). */
  resume(id) {
    const item = this.find(id);
    if (!item || !item.paused) return;
    item.paused = false;
    item.remaining = Math.max(item.remaining, 1000);
    this._start(item);
  }

  onChange(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  _start(item) {
    if (item.remaining === null || item.paused) return;
    item.deadline = this.clock.now() + item.remaining;
    item.timer = this.clock.setTimer(() => this.dismiss(item.id), item.remaining);
  }

  _stop(item) {
    if (item.timer !== null) this.clock.clearTimer(item.timer);
    item.timer = null;
  }

  _changed() {
    for (const listener of this.listeners) listener(this.items);
  }
}

/** Draws the notifications of `toasts` into `host` and keeps them in step; `icon(name, label)` is icons.js. */
export function mountToasts(toasts, host, icon) {
  const box = document.createElement("section");
  box.className = "toasts";
  box.setAttribute("aria-label", "Notifications");
  box.setAttribute("aria-live", "polite");
  host.append(box);
  const shown = new Map(); // id -> element
  const still = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

  toasts.onChange((items) => {
    const live = new Set(items.map((t) => t.id));
    for (const item of items) {
      if (shown.has(item.id)) continue;
      const element = draw(item, toasts, icon);
      const old = item.replaces !== null ? shown.get(item.replaces) : null;
      if (old) {
        old.replaceWith(element); // the same place, at once: no box slides out from under the pointer
        shown.delete(item.replaces);
      } else {
        box.append(element);
      }
      shown.set(item.id, element);
    }
    for (const [id, element] of shown) {
      if (live.has(id)) continue;
      shown.delete(id);
      if (still()) {
        element.remove();
        continue;
      }
      element.classList.add("out");
      setTimeout(() => element.remove(), 160);
    }
  });
  return box;
}

function draw(item, toasts, icon) {
  const element = document.createElement("div");
  element.className = `toast ${item.tone} in`;
  element.dataset.channel = item.channel;
  element.dataset.id = String(item.id);
  element.setAttribute("role", item.tone === "success" ? "status" : "alert");
  element.addEventListener("animationend", () => element.classList.remove("in"), { once: true });

  const mark = document.createElement("span");
  mark.className = "mark";
  mark.innerHTML = icon(ICON[item.tone], WORD[item.tone]);

  const body = document.createElement("div");
  body.className = "body";
  const title = document.createElement("p");
  title.className = "title";
  title.textContent = item.title;
  body.append(title);
  if (item.text) {
    const text = document.createElement("p");
    text.className = "text";
    text.textContent = item.text;
    body.append(text);
  }
  if (item.path) {
    if (item.pathLabel) {
      const label = document.createElement("p");
      label.className = "plabel";
      label.textContent = item.pathLabel;
      body.append(label);
    }
    const row = document.createElement("div");
    row.className = "path";
    const code = document.createElement("code");
    // a line may break after a folder separator, not in the middle of a song's name
    item.pathShown.split(/(?<=[\\/])/).forEach((part, index) => {
      if (index) code.append(document.createElement("wbr"));
      code.append(part);
    });
    code.title = item.path;
    const copy = document.createElement("button");
    copy.className = "copy-path";
    copy.innerHTML = icon("copy");
    copy.append("Copy path");
    copy.title = `Copy ${item.path}`;
    copy.addEventListener("click", () => copyPath(copy, code, item.path, icon));
    row.append(code, copy);
    body.append(row);
  }
  if (item.actions.length) {
    const acts = document.createElement("div");
    acts.className = "acts";
    for (const action of item.actions) {
      const button = document.createElement("button");
      button.textContent = action.label;
      if (action.primary) button.className = "primary";
      button.addEventListener("click", () => {
        toasts.dismiss(item.id);
        action.run();
      });
      acts.append(button);
    }
    body.append(acts);
  }

  const close = document.createElement("button");
  close.className = "close";
  close.title = "Dismiss";
  close.setAttribute("aria-label", `Dismiss: ${item.title}`);
  close.innerHTML = icon("close");
  close.addEventListener("click", () => toasts.dismiss(item.id));

  element.append(mark, body, close);
  element.addEventListener("pointerenter", () => toasts.pause(item.id));
  element.addEventListener("pointerleave", () => { if (!element.contains(document.activeElement)) toasts.resume(item.id); });
  element.addEventListener("focusin", () => toasts.pause(item.id));
  element.addEventListener("focusout", (e) => { if (!element.contains(e.relatedTarget) && !element.matches(":hover")) toasts.resume(item.id); });
  return element;
}

/** Copies the whole path; where the clipboard is refused, writes it out whole and selects it for Ctrl+C. */
async function copyPath(button, code, path, icon) {
  const say = (words, iconName) => {
    button.innerHTML = icon(iconName);
    button.append(words);
  };
  try {
    await navigator.clipboard.writeText(path);
    say("Copied", "done");
  } catch {
    code.textContent = path;
    const range = document.createRange();
    range.selectNodeContents(code);
    const selection = getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    say("Press Ctrl+C", "copy");
  }
  clearTimeout(button.restore);
  button.restore = setTimeout(() => say("Copy path", "copy"), 2000);
}
