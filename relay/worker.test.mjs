import test from "node:test";
import assert from "node:assert/strict";
import { handle, cleanQuery, forgetToken, slimShow, slimDiscover } from "./worker.js";

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

const motnShow = { title: "Severance", streamingOptions: { gb: [
  { service: { name: "Apple TV", imageSet: {} }, type: "subscription", link: "https://tv.apple.com/x", audios: [1] },
  { service: { name: "Apple TV" }, type: "subscription", link: "https://tv.apple.com/x" },
  { service: { name: "Prime Video" }, type: "addon", addon: { name: "Apple TV" }, link: "https://p/x" },
] } };

test("streaming answers are trimmed and repeats removed", () => {
  const out = slimShow(motnShow, "gb");
  assert.equal(out.options.length, 2);
  assert.deepEqual(out.options[1], { service: "Prime Video", type: "addon", link: "https://p/x", addon: "Apple TV" });
  assert.deepEqual(slimShow(motnShow, "us").options, []);
});

test("the streaming key goes upstream only, and answers are cached", async () => {
  const calls = [];
  const fetchImpl = async (url, options) => { calls.push({ url: String(url), options }); return new Response(JSON.stringify(motnShow), { status: 200 }); };
  const cache = memoryCache();
  const pending = [];
  const env = { MOTN_KEY: "motn-secret" };
  const c = { waitUntil: (p) => pending.push(p) };
  const resp = await handle(get("/motn/shows/tt11280740?country=GB"), env, c, { fetch: fetchImpl, cache });
  await Promise.all(pending);
  assert.equal(resp.status, 200);
  assert.ok(!(await resp.text()).includes("motn-secret"));
  assert.equal(calls[0].options.headers["X-API-Key"], "motn-secret");
  assert.equal(calls[0].url, "https://api.movieofthenight.com/v4/shows/tt11280740?country=gb");
  await handle(get("/motn/shows/tt11280740?country=gb"), env, c, { fetch: fetchImpl, cache });
  assert.equal(calls.length, 1);
});

test("streaming lookups are checked: id shape, country, key, limit", async () => {
  const deps = { fetch: async () => new Response("{}", { status: 200 }), cache: memoryCache() };
  assert.equal((await handle(get("/motn/shows/abc?country=gb"), { MOTN_KEY: "k" }, ctx, deps)).status, 404);
  assert.equal((await handle(get("/motn/shows/tt1"), { MOTN_KEY: "k" }, ctx, deps)).status, 400);
  assert.equal((await handle(get("/motn/shows/tt1?country=gb"), {}, ctx, deps)).status, 503);
  const env = { MOTN_KEY: "k", LIMITER_MOTN: { limit: async () => ({ success: false }) } };
  assert.equal((await handle(get("/motn/shows/tt2?country=gb"), env, ctx, deps)).status, 429);
});

test("coming-up lists join the services, date each title and list it once", () => {
  const body = {
    changes: [
      { showId: "1", timestamp: 1793257200, service: { name: "Netflix" } },
      { showId: "1", timestamp: 1793343600, service: { name: "Now" } },
      { showId: "2", timestamp: 1793343600, service: { name: "Netflix" } },
    ],
    shows: { 1: { imdbId: "tt11", title: "One", releaseYear: "2026", overview: "x".repeat(500) }, 2: { imdbId: "bad", title: "Two" } },
  };
  const out = slimDiscover(body, "upcoming", "gb");
  assert.equal(out.items.length, 1);
  assert.equal(out.items[0].date, "2026-10-29");
  assert.deepEqual(out.items[0].services, ["Netflix", "Now"]);
  assert.equal(out.items[0].overview.length, 300);
});

test("just-out lists are dated by the first day on a service, newest first", () => {
  const show = (imdb, since, name) => ({ imdbId: imdb, title: imdb, releaseYear: "2026", streamingOptions: { gb: [{ service: { name }, availableSince: since }] } });
  const out = slimDiscover({ shows: [show("tt1", 1792000000, "Netflix"), show("tt2", 1792500000, "Now"), { imdbId: "tt3", streamingOptions: { gb: [] } }] }, "out", "gb");
  assert.deepEqual(out.items.map((i) => i.imdb), ["tt2", "tt1"]);
  assert.deepEqual(out.items[0].services, ["Now"]);
});

test("discover lookups check their parameters and the key stays upstream", async () => {
  const calls = [];
  const fetchImpl = async (url, options) => { calls.push({ url: String(url), options }); return new Response(JSON.stringify({ changes: [], shows: {}, hasMore: false }), { status: 200 }); };
  const deps = { fetch: fetchImpl, cache: memoryCache() };
  const env = { MOTN_KEY: "k" };
  assert.equal((await handle(get("/motn/discover?country=gb&type=x&when=out"), env, ctx, deps)).status, 400);
  assert.equal((await handle(get("/motn/discover?country=gb&type=movie&when=later"), env, ctx, deps)).status, 400);
  assert.equal((await handle(get("/motn/discover?country=GB&type=series&when=upcoming"), env, ctx, deps)).status, 200);
  assert.ok(calls[0].url.includes("change_type=upcoming") && calls[0].url.includes("show_type=series") && calls[0].url.includes("country=gb"));
  assert.equal(calls[0].options.headers["X-API-Key"], "k");
  await handle(get("/motn/discover?country=gb&type=movie&when=out"), env, ctx, deps);
  assert.ok(calls[1].url.includes("/shows/search/filters") && calls[1].url.includes("order_by=release_date"));
});
