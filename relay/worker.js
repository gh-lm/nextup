/* Nextup's TheTVDB relay. It holds the key as a Cloudflare secret and passes on only the lookups Nextup makes. */
const UPSTREAM = "https://api4.thetvdb.com";
const ALLOWED = [
  /^\/v4\/search$/,
  /^\/v4\/search\/remoteid\/\d+$/,
  /^\/v4\/series\/\d+\/extended$/,
  /^\/v4\/series\/\d+\/episodes\/default\/eng$/,
  /^\/v4\/series\/\d+\/translations\/eng$/,
  /^\/v4\/movies\/\d+\/extended$/,
  /^\/v4\/movies\/\d+\/translations\/eng$/,
];
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

export async function handle(request, env, ctx, deps = {}) {
  const fetchImpl = deps.fetch || fetch;
  const cache = deps.cache || caches.default;
  if (request.method !== "GET") return reply(405, { status: "failure", message: "Only GET." });
  const url = new URL(request.url);
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
