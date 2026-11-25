// The editor's JSON API on the local server.

async function get(path) {
  let response;
  try {
    response = await fetch(path, { headers: { Accept: "application/json" } });
  } catch {
    throw new Error("The editor server is not reachable. Is `chartgen edit` still running?");
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `${response.status} ${response.statusText}`);
  return body;
}

const song = (id) => `/api/songs/${encodeURIComponent(id)}`;

export const api = {
  songs: () => get("/api/songs"),
  chart: (id) => get(`${song(id)}/chart`),
  info: (id) => get(`${song(id)}/info`),
  audioUrl: (id, file) => `${song(id)}/audio/${encodeURIComponent(file)}`,
};
