// The editor's JSON API on the local server. Changes go as JSON with the editor's own header (SPEC 49).

/** The API this page speaks: the same number as API_VERSION in chartgen/editor/server.py (a test checks). */
export const API_VERSION = 2;
const API_HEADER = "X-Chartgen-Api";

const UNREACHABLE = "The editor server is not reachable. Is `chartgen edit` still running?";

/**
 * An answer the server refused: its words, the HTTP status, whether the page's chart is out of date (stale),
 * and whether the page and the server are different versions of the editor (outdated).
 */
export class ApiError extends Error {
  constructor(message, status, stale = false, outdated = false) {
    super(message);
    this.status = status;
    this.stale = stale;
    this.outdated = outdated;
  }
}

/** What to do when the server speaks another API than this page: E.1 and older servers send no number. */
export function versionProblem(serverVersion) {
  const server = Number(serverVersion) || 1;
  if (server === API_VERSION) return null;
  return server > API_VERSION
    ? "The editor was updated after this page was opened. Reload the page to use the new version."
    : "This page is newer than the editor server that is running. Stop chartgen edit (Ctrl+C in its window), start it again, then reload the page.";
}

async function call(path, options = {}) {
  let response;
  try {
    response = await fetch(path, { ...options, headers: { Accept: "application/json", ...(options.headers || {}) } });
  } catch {
    throw new ApiError(UNREACHABLE, 0);
  }
  const problem = versionProblem(response.headers.get(API_HEADER));
  if (problem) throw new ApiError(problem, response.status, false, true);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(body.error || `${response.status} ${response.statusText}`, response.status, Boolean(body.stale));
  return body;
}

const get = (path) => call(path);
const post = (path, body) => call(path, {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-Chartgen-Editor": "1" },
  body: JSON.stringify(body),
});

const song = (id) => `/api/songs/${encodeURIComponent(id)}`;

export const api = {
  songs: () => get("/api/songs"),
  chart: (id) => get(`${song(id)}/chart`),
  info: (id) => get(`${song(id)}/info`),
  audioUrl: (id, file) => `${song(id)}/audio/${encodeURIComponent(file)}`,
  op: (id, body) => post(`${song(id)}/ops`, body),
  undo: (id, version) => post(`${song(id)}/undo`, { version }),
  redo: (id, version) => post(`${song(id)}/redo`, { version }),
  validate: (id) => post(`${song(id)}/validate`, {}),
};
