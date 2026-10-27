/* Nextup's relay. It holds the TheTVDB and Movie of the Night keys as Cloudflare secrets and passes on only the lookups Nextup makes. */
const UPSTREAM = "https://api4.thetvdb.com";
const ALLOWED = [
  /^\/v4\/search$/,
  /^\/v4\/search\/remoteid\/\d+$/,
  /^\/v4\/series\/\d+\/extended$/,
  /^\/v4\/series\/\d+\/episodes\/default\/eng$/,
  /^\/v4\/series\/\d+\/translations\/eng$/,
  /^\/v4\/movies\/\d+\/extended$/,
  /^\/v4\/movies\/\d+\/translations\/eng$/,
  /^\/v4\/(movies|series)\/filter$/,
];
const MOTN_UPSTREAM = "https://api.movieofthenight.com";
const MOTN_ALLOWED = /^\/motn\/shows\/tt\d{1,10}$/;
const MOTN_UPCOMING = /^\/motn\/discover$/;
const UPCOMING_PAGES = 3;
const OUT_PAGES = 2;
const MOTN_SERVICES = ["netflix", "prime", "disney", "apple", "paramount", "now", "hulu"];
const MOTN_UPCOMING_SECONDS = 12 * 3600;
const MOTN_SECONDS = 7 * 86400;
const SEARCH_SECONDS = 3600;
const RECORD_SECONDS = 86400;
const TOKEN_SECONDS = 20 * 24 * 3600;

let token = null;
let tokenAt = 0;

export function forgetToken() {
  token = null;
}

function reply(status, body, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...extra },
  });
}

export function cleanQuery(params) {
  const out = new URLSearchParams();
  const query = (params.get("query") || "").slice(0, 100);
  if (query) out.set("query", query);
  const limit = parseInt(params.get("limit") || "", 10);
  if (limit > 0) out.set("limit", String(Math.min(limit, 20)));
  const page = parseInt(params.get("page") || "", 10);
  if (page >= 0 && page <= 50) out.set("page", String(page));
  if (params.get("short") === "true") out.set("short", "true");
  for (const key of ["country", "lang"]) {
    const value = params.get(key) || "";
    if (/^[a-z]{3}$/.test(value)) out.set(key, value);
  }
  const sort = params.get("sort") || "";
  if (["score", "firstAired", "name"].includes(sort)) out.set("sort", sort);
  const sortType = params.get("sortType") || "";
  if (["asc", "desc"].includes(sortType)) out.set("sortType", sortType);
  const year = params.get("year") || "";
  if (/^\d{4}$/.test(year)) out.set("year", year);
  return out;
}

async function login(env, fetchImpl) {
  const resp = await fetchImpl(`${UPSTREAM}/v4/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ apikey: env.TVDB_KEY }),
  });
  if (!resp.ok) throw new Error("login");
  token = (await resp.json()).data.token;
  tokenAt = Date.now();
}

async function upstream(url, env, fetchImpl) {
  for (let attempt = 0; attempt < 2; attempt++) {
    if (!token || Date.now() - tokenAt > TOKEN_SECONDS * 1000) await login(env, fetchImpl);
    const resp = await fetchImpl(url, { headers: { Authorization: `Bearer ${token}` } });
    if (resp.status !== 401) return resp;
    token = null;
  }
  throw new Error("auth");
}

export function slimShow(show, country) {
  const seen = new Set();
  const options = [];
  for (const o of (show.streamingOptions || {})[country] || []) {
    const entry = {
      service: String((o.service || {}).name || ""),
      type: String(o.type || ""),
      link: String(o.link || ""),
    };
    if (o.addon) entry.addon = String(o.addon.name || "");
    const id = `${entry.service}|${entry.type}|${entry.addon || ""}`;
    if (!entry.service || seen.has(id)) continue;
    seen.add(id);
    options.push(entry);
  }
  return { title: String(show.title || ""), options };
}

function posterOf(show) {
  const url = String((((show.imageSet || {}).verticalPoster) || {}).w240 || "");
  return url.startsWith("https://cdn.movieofthenight.com/") ? url : "";
}

export function slimDiscover(body, when, country) {
  const names = {};
  const dates = {};
  if (when === "upcoming") {
    for (const change of body.changes || []) {
      const key = change.showId;
      (names[key] = names[key] || new Set()).add(String((change.service || {}).name || ""));
      if (change.timestamp && !(dates[key] <= change.timestamp)) dates[key] = change.timestamp;
    }
  }
  const shows = when === "upcoming" ? Object.entries(body.shows || {}).map(([id, s]) => ({ ...s, id })) : body.shows || [];
  const seen = new Set();
  const items = [];
  for (const show of shows) {
    const imdb = String(show.imdbId || "");
    if (!/^tt\d{1,10}$/.test(imdb) || seen.has(imdb)) continue;
    let stamp = dates[show.id];
    let services = [...(names[show.id] || [])];
    if (when === "out") {
      const options = ((show.streamingOptions || {})[country] || []).filter((o) => o.availableSince);
      stamp = Math.min(...options.map((o) => o.availableSince));
      services = [...new Set(options.map((o) => String((o.service || {}).name || "")))];
    }
    if (!stamp || !Number.isFinite(stamp) || !services.length) continue;
    seen.add(imdb);
    items.push({
      imdb,
      title: String(show.title || ""),
      year: String(show.releaseYear || show.firstAirYear || ""),
      date: new Date(stamp * 1000).toISOString().slice(0, 10),
      services: services.filter(Boolean),
      overview: String(show.overview || "").slice(0, 300),
      poster: posterOf(show),
    });
  }
  items.sort((a, b) => (when === "out" ? b.date.localeCompare(a.date) : a.date.localeCompare(b.date)));
  return { items };
}

async function motnGet(path, env, fetchImpl) {
  const resp = await fetchImpl(`${MOTN_UPSTREAM}${path}`, { headers: { "X-API-Key": env.MOTN_KEY } });
  if (!resp.ok) throw new Error("motn");
  return resp.json();
}

async function handleUpcoming(request, env, ctx, deps, url) {
  const fetchImpl = deps.fetch || fetch;
  const cache = deps.cache || caches.default;
  const country = (url.searchParams.get("country") || "").toLowerCase();
  const kind = url.searchParams.get("type") || "";
  const when = url.searchParams.get("when") || "";
  if (!/^[a-z]{2}$/.test(country) || !["movie", "series"].includes(kind) || !["upcoming", "out"].includes(when)) {
    return reply(400, { status: "failure", message: "Country, type and when needed." });
  }
  if (!env.MOTN_KEY) return reply(503, { status: "failure", message: "Not available." });
  const catalogs = MOTN_SERVICES.join(",");
  const base = `country=${country}&catalogs=${catalogs}&show_type=${kind}`;
  const cacheKey = new Request(`${MOTN_UPSTREAM}/discover?${base}&when=${when}&v=2`);
  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  if (env.LIMITER_MOTN) {
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    const { success } = await env.LIMITER_MOTN.limit({ key: ip });
    if (!success) {
      return reply(429, { status: "failure", message: "Too many lookups. Try again in a minute." }, { "Retry-After": "60" });
    }
  }
  let body;
  try {
    if (when === "upcoming") {
      body = { changes: [], shows: {} };
      let cursor = "";
      for (let page = 0; page < UPCOMING_PAGES; page++) {
        const part = await motnGet(`/v4/changes?change_type=upcoming&item_type=show&order_direction=asc&${base}${cursor}`, env, fetchImpl);
        body.changes.push(...(part.changes || []));
        Object.assign(body.shows, part.shows || {});
        if (!part.hasMore || !part.nextCursor) break;
        cursor = `&cursor=${encodeURIComponent(part.nextCursor)}`;
      }
    } else {
      body = { shows: [] };
      const year = new Date(Date.now() - 90 * 86400000).getUTCFullYear();
      let cursor = "";
      for (let page = 0; page < OUT_PAGES; page++) {
        const part = await motnGet(`/v4/shows/search/filters?order_by=release_date&order_direction=desc&year_min=${year}&${base}${cursor}`, env, fetchImpl);
        body.shows.push(...(part.shows || []));
        if (!part.hasMore || !part.nextCursor) break;
        cursor = `&cursor=${encodeURIComponent(part.nextCursor)}`;
      }
    }
  } catch (err) {
    return reply(503, { status: "failure", message: "Streaming lookup is unavailable." }, { "Cache-Control": "no-store" });
  }
  const out = reply(200, slimDiscover(body, when, country), { "Cache-Control": `public, max-age=${MOTN_UPCOMING_SECONDS}` });
  ctx.waitUntil(cache.put(cacheKey, out.clone()));
  return out;
}

async function handleMotn(request, env, ctx, deps, url) {
  const fetchImpl = deps.fetch || fetch;
  const cache = deps.cache || caches.default;
  const country = (url.searchParams.get("country") || "").toLowerCase();
  if (!/^[a-z]{2}$/.test(country)) return reply(400, { status: "failure", message: "Country needed." });
  if (!env.MOTN_KEY) return reply(503, { status: "failure", message: "Not available." });
  const target = `${MOTN_UPSTREAM}/v4${url.pathname.slice(5)}?country=${country}`;
  const cacheKey = new Request(target);
  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  if (env.LIMITER_MOTN) {
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    const { success } = await env.LIMITER_MOTN.limit({ key: ip });
    if (!success) {
      return reply(429, { status: "failure", message: "Too many lookups. Try again in a minute." }, { "Retry-After": "60" });
    }
  }

  let resp;
  try {
    resp = await fetchImpl(target, { headers: { "X-API-Key": env.MOTN_KEY } });
  } catch (err) {
    return reply(502, { status: "failure", message: "Streaming lookup could not be reached." });
  }
  if (resp.status === 404) {
    const none = reply(200, { title: "", options: [] }, { "Cache-Control": "public, max-age=86400" });
    ctx.waitUntil(cache.put(cacheKey, none.clone()));
    return none;
  }
  if (!resp.ok) return reply(503, { status: "failure", message: "Streaming lookup is unavailable." }, { "Cache-Control": "no-store" });
  const out = reply(200, slimShow(await resp.json(), country), { "Cache-Control": `public, max-age=${MOTN_SECONDS}` });
  ctx.waitUntil(cache.put(cacheKey, out.clone()));
  return out;
}

export async function handle(request, env, ctx, deps = {}) {
  const fetchImpl = deps.fetch || fetch;
  const cache = deps.cache || caches.default;
  if (request.method !== "GET") return reply(405, { status: "failure", message: "Only GET." });
  const url = new URL(request.url);
  if (MOTN_ALLOWED.test(url.pathname)) return handleMotn(request, env, ctx, deps, url);
  if (MOTN_UPCOMING.test(url.pathname)) return handleUpcoming(request, env, ctx, deps, url);
  if (!ALLOWED.some((rule) => rule.test(url.pathname))) {
    return reply(404, { status: "failure", message: "Not available." });
  }
  const target = `${UPSTREAM}${url.pathname}?${cleanQuery(url.searchParams)}`;
  const cacheKey = new Request(target);

  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  if (env.LIMITER) {
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    const { success } = await env.LIMITER.limit({ key: ip });
    if (!success) {
      return reply(429, { status: "failure", message: "Too many lookups. Try again in a minute." }, { "Retry-After": "60" });
    }
  }

  let resp;
  try {
    resp = await upstream(target, env, fetchImpl);
  } catch (err) {
    return reply(502, { status: "failure", message: "TheTVDB could not be reached." });
  }
  const body = await resp.text();
  const seconds = url.pathname === "/v4/search" ? SEARCH_SECONDS : RECORD_SECONDS;
  const out = new Response(body, {
    status: resp.status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": resp.ok ? `public, max-age=${seconds}` : "no-store",
    },
  });
  if (resp.ok) ctx.waitUntil(cache.put(cacheKey, out.clone()));
  return out;
}

export default {
  fetch: (request, env, ctx) => handle(request, env, ctx),
};
