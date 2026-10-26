import test from "node:test";
import assert from "node:assert/strict";
import { handle, cleanQuery, forgetToken } from "./worker.js";

function memoryCache() {
  const store = new Map();
  return {
    match: async (req) => store.get(req.url)?.clone(),
    put: async (req, res) => { store.set(req.url, res); },
  };
}
const ctx = { waitUntil: () => {} };

function upstream(calls) {
  return async (url, options = {}) => {
    calls.push({ url: String(url), options });
    if (String(url).endsWith("/v4/login")) {
      return new Response(JSON.stringify({ data: { token: "T" } }), { status: 200 });
    }
    return new Response(JSON.stringify({ data: { name: "Show" } }), { status: 200 });
  };
}

const get = (path) => new Request(`https://relay.example${path}`);

test("only the lookups Nextup makes get through", async () => {
  const deps = { fetch: upstream([]), cache: memoryCache() };
  assert.equal((await handle(get("/v4/user/favorites"), { TVDB_KEY: "k" }, ctx, deps)).status, 404);
  assert.equal((await handle(get("/v4/series/1/extended"), { TVDB_KEY: "k" }, ctx, deps)).status, 200);
  assert.equal((await handle(new Request("https://relay.example/v4/search", { method: "POST" }), { TVDB_KEY: "k" }, ctx, deps)).status, 405);
});

test("the key goes to TheTVDB and never back to the caller", async () => {
  forgetToken();
  const calls = [];
  const deps = { fetch: upstream(calls), cache: memoryCache() };
  const resp = await handle(get("/v4/series/1/extended?short=true"), { TVDB_KEY: "secret-key" }, ctx, deps);
  assert.ok(!(await resp.text()).includes("secret-key"));
  assert.ok(calls[0].options.body.includes("secret-key"));
});

test("a repeated lookup is answered from the cache", async () => {
  const calls = [];
  const deps = { fetch: upstream(calls), cache: memoryCache() };
  await handle(get("/v4/series/1/extended"), { TVDB_KEY: "k" }, { waitUntil: (p) => p }, deps);
  await new Promise((r) => setTimeout(r, 5));
  const before = calls.length;
  await handle(get("/v4/series/1/extended"), { TVDB_KEY: "k" }, ctx, deps);
  assert.equal(calls.length, before);
});

test("lookups past the limit are refused", async () => {
  const deps = { fetch: upstream([]), cache: memoryCache() };
  const env = { TVDB_KEY: "k", LIMITER: { limit: async () => ({ success: false }) } };
  const resp = await handle(get("/v4/series/2/extended"), env, ctx, deps);
  assert.equal(resp.status, 429);
});

test("odd parameters are dropped and sizes capped", () => {
  const out = cleanQuery(new URL("https://x/?query=abc&limit=500&page=2&evil=1&short=true").searchParams);
  assert.equal(out.toString(), "query=abc&limit=20&page=2&short=true");
});

test("filter parameters are checked and passed in a fixed order", () => {
  const out = cleanQuery(new URL("https://x/?year=2026&sort=firstAired&sortType=desc&country=usa&lang=eng&sort2=x").searchParams);
  assert.equal(out.toString(), "country=usa&lang=eng&sort=firstAired&sortType=desc&year=2026");
  assert.equal(cleanQuery(new URL("https://x/?sort=drop&year=20x6&country=us").searchParams).toString(), "");
});
