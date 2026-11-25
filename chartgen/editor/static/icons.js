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
};

export function icon(name, label = "") {
  const aria = label ? `role="img" aria-label="${label}"` : 'aria-hidden="true"';
  return `<svg class="i" viewBox="0 0 24 24" ${aria}>${PATHS[name]}</svg>`;
}
