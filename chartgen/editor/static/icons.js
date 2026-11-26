// One stroke icon set, 24 x 24, drawn here (no glyphs, no fonts).

const PATHS = {
  back: '<path d="M15 5l-7 7 7 7"/>',
  play: '<path d="M7 4.5v15l13-7.5z"/>',
  pause: '<path d="M6.5 4.5h4v15h-4zM13.5 4.5h4v15h-4z"/>',
  zoomIn: '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5M8.5 11h5M11 8.5v5"/>',
  zoomOut: '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5M8.5 11h5"/>',
  fit: '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"/>',
  alert: '<circle cx="12" cy="12" r="9" class="fill"/><path d="M12 7.5v5.5" class="cut"/><circle cx="12" cy="16.3" r="1.1" class="dot"/>',
  warn: '<path d="M12 3.2L22 20.5H2z" class="fill"/><path d="M12 9.5v5" class="cut"/><circle cx="12" cy="17.6" r="1.1" class="dot"/>',
  done: '<circle cx="12" cy="12" r="9" class="fill"/><path d="M7.8 12.3l2.9 2.9 5.5-5.9" class="cut"/>',
  close: '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
  copy: '<rect x="8.5" y="8.5" width="11" height="11" rx="1.5"/><path d="M15.5 8.5V6a1.5 1.5 0 0 0-1.5-1.5H6A1.5 1.5 0 0 0 4.5 6v8A1.5 1.5 0 0 0 6 15.5h2.5"/>',
  select: '<path d="M5 3l12 8-6 1.5L8.5 19z"/>',
  draw: '<path d="M4 20l1.3-4.6L15.6 5.1a2.1 2.1 0 0 1 3 3L8.3 18.4zM13.6 7.1l3 3"/>',
  undo: '<path d="M9 13.5L4.5 9 9 4.5"/><path d="M4.5 9H14a5.5 5.5 0 0 1 0 11h-3"/>',
  redo: '<path d="M15 13.5L19.5 9 15 4.5"/><path d="M19.5 9H10a5.5 5.5 0 0 0 0 11h3"/>',
  levels: '<path d="M12 4l8 4-8 4-8-4z"/><path d="M4 12l8 4 8-4"/><path d="M4 16l8 4 8-4"/>',
};

export function icon(name, label = "") {
  const aria = label ? `role="img" aria-label="${label}"` : 'aria-hidden="true"';
  return `<svg class="i" viewBox="0 0 24 24" ${aria}>${PATHS[name]}</svg>`;
}
