// The page's API client (E.2 cache fix): a server of another API version is reported, not misread.

import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { API_VERSION, ApiError, api, versionProblem } from "../../chartgen/editor/static/api.js";

const realFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = realFetch; });

function answer(body, status, version) {
  const headers = version === undefined ? {} : { "X-Chartgen-Api": String(version) };
  globalThis.fetch = async () => new Response(JSON.stringify(body), { status, headers });
}

test("the same version is no problem; another one says what to do", () => {
  assert.equal(versionProblem(String(API_VERSION)), null);
  assert.match(versionProblem(String(API_VERSION + 1)), /^The editor was updated after this page was opened\. Reload the page/);
  assert.match(versionProblem(String(API_VERSION - 1)), /^This page is newer than the editor server that is running\./);
  assert.match(versionProblem(null), /^This page is newer/); // E.1 and older servers send no number
});

test("an answer from a server of another version is an outdated error, even a 404", async () => {
  answer({ error: "Not Found" }, 404, null);
  await assert.rejects(api.op("Song", {}), (error) => error instanceof ApiError && error.outdated && /newer than the editor server/.test(error.message));
  answer({ songs: [] }, 200, API_VERSION + 1);
  await assert.rejects(api.songs(), (error) => error.outdated && /Reload the page/.test(error.message));
});

test("an answer of this version passes, and a refusal keeps its own words", async () => {
  answer({ root: "x", songs: [] }, 200, API_VERSION);
  assert.deepEqual(await api.songs(), { root: "x", songs: [] });
  answer({ error: "There is nothing to undo.", stale: false }, 409, API_VERSION);
  await assert.rejects(api.undo("Song", 3), (error) => !error.outdated && error.message === "There is nothing to undo." && error.status === 409);
});
